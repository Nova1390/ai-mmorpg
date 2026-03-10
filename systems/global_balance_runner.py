from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Tuple

from brain import FoodBrain, LLMBrain
from planner import Planner
from world import CAMP_ANCHOR_RADIUS, World


@dataclass(frozen=True)
class GlobalBalanceThresholds:
    min_legit_village_population: int = 2
    min_legit_leader_village_population: int = 3
    early_extinction_threshold_tick: int = 200
    early_mass_death_threshold_ratio: float = 0.5


@dataclass(frozen=True)
class GlobalBalanceScenarioConfig:
    name: str
    seed: int
    width: int = 72
    height: int = 72
    initial_population: int = 40
    ticks: int = 1200
    snapshot_interval: int = 10
    llm_enabled: bool = False
    llm_reflection_mode: str = "provider_with_stub_fallback"
    llm_stub_enabled: bool = True
    llm_force_local_stub: bool = False
    history_limit: int = 300
    food_multiplier: float = 1.0


def _safe_uid(value: Any) -> str:
    return str(value or "").strip()


def _village_id_to_uid(world: World) -> Dict[int, str]:
    mapping: Dict[int, str] = {}
    for village in getattr(world, "villages", []):
        if not isinstance(village, dict):
            continue
        vid = village.get("id", None)
        uid = _safe_uid(village.get("village_uid", ""))
        if isinstance(vid, int) and uid:
            mapping[int(vid)] = uid
    return mapping


def compute_village_support_map(world: World) -> Dict[str, int]:
    support: Dict[str, int] = {}
    id_to_uid = _village_id_to_uid(world)
    for agent in getattr(world, "agents", []):
        if not getattr(agent, "alive", False):
            continue
        status = str(getattr(agent, "village_affiliation_status", "") or "")
        home_uid = _safe_uid(getattr(agent, "home_village_uid", ""))
        primary_uid = _safe_uid(getattr(agent, "primary_village_uid", ""))
        fallback_uid = _safe_uid(id_to_uid.get(getattr(agent, "village_id", None), ""))
        uid = ""
        if status == "resident":
            uid = home_uid or primary_uid or fallback_uid
        elif status in {"attached", "transient"}:
            uid = primary_uid or home_uid or fallback_uid
        else:
            uid = primary_uid or home_uid or fallback_uid
        if uid:
            support[uid] = int(support.get(uid, 0)) + 1
    return support


def compute_implausibility_flags(*, metrics: Dict[str, Any], thresholds: GlobalBalanceThresholds) -> Dict[str, bool]:
    singleton_village_count = int(metrics.get("settlement_legitimacy", {}).get("singleton_village_count", 0))
    villages_under_legit = int(metrics.get("settlement_legitimacy", {}).get("villages_under_legit_threshold_count", 0))
    singleton_leader_count = int(metrics.get("leadership_legitimacy", {}).get("leaders_in_singleton_villages_count", 0))
    leaders_under_legit = int(metrics.get("leadership_legitimacy", {}).get("leaders_under_legit_threshold_count", 0))
    extinction_flag = bool(metrics.get("survival", {}).get("extinction", False))
    extinction_tick = metrics.get("survival", {}).get("extinction_tick", None)
    early_mass_death = bool(metrics.get("survival", {}).get("early_mass_death", False))

    return {
        "singleton_village_created": singleton_village_count > 0,
        "singleton_leader_created": singleton_leader_count > 0,
        "village_before_min_population_support": villages_under_legit > 0,
        "leadership_before_min_social_support": leaders_under_legit > 0,
        "early_mass_death": early_mass_death,
        "extinction_before_tick_threshold": bool(
            extinction_flag
            and isinstance(extinction_tick, int)
            and int(extinction_tick) <= int(thresholds.early_extinction_threshold_tick)
        ),
    }


def _apply_food_multiplier(world: World, multiplier: float) -> None:
    mul = float(multiplier)
    if abs(mul - 1.0) < 1e-9:
        return
    current_food = sorted(list(getattr(world, "food", set())), key=lambda p: (int(p[1]), int(p[0])))
    base_count = len(current_food)
    if base_count <= 0:
        return
    target_count = max(1, int(round(base_count * mul)))
    if target_count < base_count:
        world.food = set(current_food[:target_count])
        return
    additional = target_count - base_count
    for _ in range(additional):
        pos = world.find_random_free()
        if pos is None:
            break
        world.food.add((int(pos[0]), int(pos[1])))


def _setup_world(cfg: GlobalBalanceScenarioConfig) -> World:
    world = World(
        width=int(cfg.width),
        height=int(cfg.height),
        num_agents=int(cfg.initial_population),
        seed=int(cfg.seed),
        llm_enabled=bool(cfg.llm_enabled),
    )
    world.llm_sync_execution = bool(cfg.llm_enabled)
    world.llm_reflection_mode = str(cfg.llm_reflection_mode)
    world.llm_stub_enabled = bool(cfg.llm_stub_enabled)
    world.llm_force_local_stub = bool(cfg.llm_force_local_stub)
    if bool(cfg.llm_enabled):
        fallback = FoodBrain(vision_radius=8)
        planner = Planner(model="phi3")
        llm_brain = LLMBrain(planner=planner, fallback=fallback, think_every_ticks=20)
        for agent in getattr(world, "agents", []):
            if getattr(agent, "alive", False):
                agent.brain = llm_brain
    if hasattr(world, "metrics_collector"):
        world.metrics_collector.snapshot_interval = max(1, int(cfg.snapshot_interval))
    _apply_food_multiplier(world, float(cfg.food_multiplier))
    return world


def _camp_population_map(world: World) -> Dict[str, int]:
    result: Dict[str, int] = {}
    camps = getattr(world, "camps", {})
    if not isinstance(camps, dict):
        return result
    for camp_id, camp in camps.items():
        if not isinstance(camp, dict):
            continue
        cx = int(camp.get("x", 0))
        cy = int(camp.get("y", 0))
        near = 0
        for agent in getattr(world, "agents", []):
            if not getattr(agent, "alive", False):
                continue
            if abs(int(getattr(agent, "x", 0)) - cx) + abs(int(getattr(agent, "y", 0)) - cy) <= int(CAMP_ANCHOR_RADIUS):
                near += 1
        result[str(camp_id)] = int(near)
    return result


def run_global_balance_scenario(
    cfg: GlobalBalanceScenarioConfig,
    *,
    thresholds: Optional[GlobalBalanceThresholds] = None,
) -> Dict[str, Any]:
    thresholds = thresholds or GlobalBalanceThresholds()
    world = _setup_world(cfg)

    checkpoints = sorted(set([100, 250, 500, int(cfg.ticks)]))
    population_at_checkpoints: Dict[str, int] = {}

    initial_ids = {str(getattr(a, "agent_id", "")) for a in getattr(world, "agents", []) if getattr(a, "alive", False)}
    prev_alive_ids = set(initial_ids)
    death_tick_by_initial_id: Dict[str, int] = {}

    extinction_tick: Optional[int] = None
    pop_at_early_threshold: Optional[int] = None

    seen_village_ids: Dict[str, Dict[str, int]] = {}
    village_persistence_ticks: Dict[str, int] = {}
    village_max_support: Dict[str, int] = {}

    seen_leaders: Dict[str, Dict[str, Any]] = {}

    seen_camps: Dict[str, Dict[str, Any]] = {}

    for tick in range(1, max(0, int(cfg.ticks)) + 1):
        world.update()

        pop_now = int(len([a for a in getattr(world, "agents", []) if getattr(a, "alive", False)]))
        alive_ids = {str(getattr(a, "agent_id", "")) for a in getattr(world, "agents", []) if getattr(a, "alive", False)}

        if extinction_tick is None and pop_now <= 0:
            extinction_tick = int(tick)

        if int(tick) == int(thresholds.early_extinction_threshold_tick):
            pop_at_early_threshold = int(pop_now)

        for cp in checkpoints:
            if int(tick) == int(cp):
                population_at_checkpoints[str(cp)] = int(pop_now)

        died_now = prev_alive_ids.difference(alive_ids)
        for aid in died_now:
            if aid in initial_ids and aid not in death_tick_by_initial_id:
                death_tick_by_initial_id[aid] = int(tick)
        prev_alive_ids = alive_ids

        support_map = compute_village_support_map(world)

        for village in getattr(world, "villages", []):
            if not isinstance(village, dict):
                continue
            uid = _safe_uid(village.get("village_uid", ""))
            if not uid:
                uid = f"vid-{int(village.get('id', -1))}"
            support = int(support_map.get(uid, 0))
            if uid not in seen_village_ids:
                seen_village_ids[uid] = {
                    "creation_tick": int(tick),
                    "population_at_creation": int(support),
                }
            village_persistence_ticks[uid] = int(village_persistence_ticks.get(uid, 0)) + 1
            village_max_support[uid] = max(int(village_max_support.get(uid, 0)), int(support))

        id_to_uid = _village_id_to_uid(world)
        for agent in getattr(world, "agents", []):
            if not getattr(agent, "alive", False):
                continue
            if str(getattr(agent, "role", "")) != "leader":
                continue
            aid = str(getattr(agent, "agent_id", ""))
            if not aid or aid in seen_leaders:
                continue
            uid = _safe_uid(getattr(agent, "primary_village_uid", "")) or _safe_uid(getattr(agent, "home_village_uid", ""))
            if not uid:
                uid = _safe_uid(id_to_uid.get(getattr(agent, "village_id", None), ""))
            support = int(support_map.get(uid, 0)) if uid else 0
            seen_leaders[aid] = {
                "tick": int(tick),
                "village_uid": uid,
                "village_population_at_creation": int(support),
            }

        camp_pop_map = _camp_population_map(world)
        camps = getattr(world, "camps", {})
        if isinstance(camps, dict):
            for camp_id, camp in camps.items():
                cid = str(camp_id)
                cpop = int(camp_pop_map.get(cid, 0))
                active = bool(camp.get("active", False)) if isinstance(camp, dict) else False
                if cid not in seen_camps:
                    seen_camps[cid] = {
                        "created_tick": int(tick),
                        "max_population": int(cpop),
                        "active_ticks": 1 if active else 0,
                    }
                else:
                    seen_camps[cid]["max_population"] = max(int(seen_camps[cid].get("max_population", 0)), int(cpop))
                    if active:
                        seen_camps[cid]["active_ticks"] = int(seen_camps[cid].get("active_ticks", 0)) + 1

    final_alive_count = int(len([a for a in getattr(world, "agents", []) if getattr(a, "alive", False)]))
    for cp in checkpoints:
        if str(cp) in population_at_checkpoints:
            continue
        population_at_checkpoints[str(cp)] = int(final_alive_count) if int(cp) == int(cfg.ticks) else 0

    initial_lifespans = [int(death_tick_by_initial_id.get(aid, int(cfg.ticks))) for aid in sorted(initial_ids)]
    mean_time_to_death = float(mean(initial_lifespans)) if initial_lifespans else float(cfg.ticks)

    village_creation_ticks = [int(rec["creation_tick"]) for rec in seen_village_ids.values()]
    village_creation_pops = [int(rec["population_at_creation"]) for rec in seen_village_ids.values()]

    singleton_village_count = sum(1 for p in village_creation_pops if int(p) <= 1)
    under_legit_village_count = sum(1 for p in village_creation_pops if int(p) < int(thresholds.min_legit_village_population))

    leader_creation_ticks = [int(rec["tick"]) for rec in seen_leaders.values()]
    leader_creation_support = [int(rec["village_population_at_creation"]) for rec in seen_leaders.values()]
    singleton_leader_count = sum(1 for p in leader_creation_support if int(p) <= 1)
    under_legit_leader_count = sum(
        1 for p in leader_creation_support if int(p) < int(thresholds.min_legit_leader_village_population)
    )

    camp_max_pop = [int(rec.get("max_population", 0)) for rec in seen_camps.values()]
    camp_singleton_count = sum(1 for p in camp_max_pop if int(p) <= 1)

    final_summary = world.metrics_collector.latest() if hasattr(world, "metrics_collector") else {}
    history = world.metrics_collector.history(limit=int(cfg.history_limit)) if hasattr(world, "metrics_collector") else []

    world_block = final_summary.get("world", {}) if isinstance(final_summary, dict) else {}
    cog = final_summary.get("cognition_society", {}) if isinstance(final_summary, dict) else {}

    early_pop = int(pop_at_early_threshold if pop_at_early_threshold is not None else population_at_checkpoints.get(str(thresholds.early_extinction_threshold_tick), 0))
    initial_pop = max(1, int(cfg.initial_population))
    early_mass_death = bool(early_pop <= int(round(initial_pop * (1.0 - float(thresholds.early_mass_death_threshold_ratio)))))

    metrics: Dict[str, Any] = {
        "survival": {
            "population_at_checkpoints": dict(population_at_checkpoints),
            "final_population": int(world_block.get("population", 0)),
            "extinction": bool(extinction_tick is not None),
            "extinction_tick": int(extinction_tick) if isinstance(extinction_tick, int) else None,
            "mean_time_to_death_initial_cohort": float(mean_time_to_death),
            "initial_cohort_deaths": int(len(death_tick_by_initial_id)),
            "initial_cohort_size": int(len(initial_ids)),
            "avg_hunger_final": float(world_block.get("avg_hunger", 0.0)),
            "survival_pressure_avg": float(cog.get("survival_pressure_avg", 0.0)),
            "early_mass_death": bool(early_mass_death),
        },
        "camp_proto": {
            "proto_community_count_final": int(cog.get("proto_community_count", 0)),
            "proto_community_agents_final": int(cog.get("proto_community_agents", 0)),
            "camps_formed_count": int(len(seen_camps)),
            "active_camps_final": int(cog.get("active_camps_count", 0)),
            "camp_singleton_count": int(camp_singleton_count),
            "camp_singleton_ratio": float(camp_singleton_count / max(1, len(seen_camps))),
            "camp_population_avg_max": float(mean(camp_max_pop)) if camp_max_pop else 0.0,
            "camp_population_max": int(max(camp_max_pop)) if camp_max_pop else 0,
            "camp_lifecycle_global": dict(cog.get("camp_lifecycle_global", {})) if isinstance(cog.get("camp_lifecycle_global", {}), dict) else {},
            "camp_food_metrics": dict(cog.get("camp_food_metrics", {})) if isinstance(cog.get("camp_food_metrics", {}), dict) else {},
            "communication_knowledge_metrics": dict(cog.get("communication_knowledge_global", {})) if isinstance(cog.get("communication_knowledge_global", {}), dict) else {},
            "food_patch_metrics": {
                "food_patch_count": int(world_block.get("food_patch_count", 0)),
                "food_patch_total_area": int(world_block.get("food_patch_total_area", 0)),
                "food_patch_food_spawned": int(world_block.get("food_patch_food_spawned", 0)),
            },
        },
        "settlement_legitimacy": {
            "villages_formed_count": int(len(seen_village_ids)),
            "village_creation_ticks": list(sorted(village_creation_ticks)),
            "village_population_at_creation": list(village_creation_pops),
            "singleton_village_count": int(singleton_village_count),
            "villages_under_legit_threshold_count": int(under_legit_village_count),
            "min_legit_village_population": int(thresholds.min_legit_village_population),
            "max_village_population_support": int(max(village_max_support.values())) if village_max_support else 0,
            "village_persistence_ticks": dict(village_persistence_ticks),
        },
        "leadership_legitimacy": {
            "leaders_created_count": int(len(seen_leaders)),
            "leader_creation_ticks": list(sorted(leader_creation_ticks)),
            "leader_village_population_at_creation": list(leader_creation_support),
            "leaders_in_singleton_villages_count": int(singleton_leader_count),
            "leaders_under_legit_threshold_count": int(under_legit_leader_count),
            "min_legit_leader_village_population": int(thresholds.min_legit_leader_village_population),
        },
        "proto_specialization": dict(cog.get("proto_specialization_global", {})) if isinstance(cog.get("proto_specialization_global", {}), dict) else {},
        "economy_productivity": {
            "stored_food_final": int(world_block.get("stored_food", 0)),
            "total_food_gathered": int((final_summary.get("production", {}) if isinstance(final_summary.get("production", {}), dict) else {}).get("total_food_gathered", 0)),
            "task_completion_global": dict(cog.get("task_completion_diagnostics_global", {})) if isinstance(cog.get("task_completion_diagnostics_global", {}), dict) else {},
        },
    }

    flags = compute_implausibility_flags(metrics=metrics, thresholds=thresholds)

    return {
        "scenario": {
            "name": str(cfg.name),
            "seed": int(cfg.seed),
            "width": int(cfg.width),
            "height": int(cfg.height),
            "initial_population": int(cfg.initial_population),
            "ticks": int(cfg.ticks),
            "snapshot_interval": int(cfg.snapshot_interval),
            "llm_enabled": bool(cfg.llm_enabled),
            "llm_reflection_mode": str(cfg.llm_reflection_mode),
            "llm_stub_enabled": bool(cfg.llm_stub_enabled),
            "llm_force_local_stub": bool(cfg.llm_force_local_stub),
            "history_limit": int(cfg.history_limit),
            "food_multiplier": float(cfg.food_multiplier),
        },
        "analysis_thresholds": {
            "min_legit_village_population": int(thresholds.min_legit_village_population),
            "min_legit_leader_village_population": int(thresholds.min_legit_leader_village_population),
            "early_extinction_threshold_tick": int(thresholds.early_extinction_threshold_tick),
            "early_mass_death_threshold_ratio": float(thresholds.early_mass_death_threshold_ratio),
        },
        "metrics": metrics,
        "implausibility_flags": flags,
        "summary": final_summary,
        "history": history,
    }


def aggregate_global_balance_results(
    *,
    scenario_family: str,
    runs: Iterable[Dict[str, Any]],
    thresholds: GlobalBalanceThresholds,
) -> Dict[str, Any]:
    run_list = [r for r in runs if isinstance(r, dict)]

    def _collect(path: Tuple[str, ...], default: float = 0.0) -> List[float]:
        vals: List[float] = []
        for run in run_list:
            cur: Any = run
            for key in path:
                if not isinstance(cur, dict):
                    cur = None
                    break
                cur = cur.get(key)
            if isinstance(cur, (int, float)):
                vals.append(float(cur))
            else:
                vals.append(float(default))
        return vals

    village_singleton = _collect(("metrics", "settlement_legitimacy", "singleton_village_count"))
    leader_singleton = _collect(("metrics", "leadership_legitimacy", "leaders_in_singleton_villages_count"))
    extinct = _collect(("metrics", "survival", "extinction"))
    final_pop = _collect(("metrics", "survival", "final_population"))
    early_mass_death = _collect(("metrics", "survival", "early_mass_death"))
    camps_formed = _collect(("metrics", "camp_proto", "camps_formed_count"))
    active_camps = _collect(("metrics", "camp_proto", "active_camps_final"))
    camp_food_deposits = _collect(("metrics", "camp_proto", "camp_food_metrics", "camp_food_deposits"))
    camp_food_consumptions = _collect(("metrics", "camp_proto", "camp_food_metrics", "camp_food_consumptions"))
    local_food_pressure_events = _collect(("metrics", "camp_proto", "camp_food_metrics", "local_food_pressure_events"))
    pressure_backed_food_deliveries = _collect(("metrics", "camp_proto", "camp_food_metrics", "pressure_backed_food_deliveries"))
    pressure_served_ratio = _collect(("metrics", "camp_proto", "camp_food_metrics", "pressure_served_ratio"))
    communication_events = _collect(("metrics", "camp_proto", "communication_knowledge_metrics", "communication_events"))
    shared_food_knowledge_used = _collect(("metrics", "camp_proto", "communication_knowledge_metrics", "shared_food_knowledge_used_count"))
    shared_camp_knowledge_used = _collect(("metrics", "camp_proto", "communication_knowledge_metrics", "shared_camp_knowledge_used_count"))
    social_accept = _collect(("metrics", "camp_proto", "communication_knowledge_metrics", "social_knowledge_accept_count"))
    social_reject = _collect(("metrics", "camp_proto", "communication_knowledge_metrics", "social_knowledge_reject_count"))
    social_reject_survival = _collect(("metrics", "camp_proto", "communication_knowledge_metrics", "social_knowledge_reject_survival_priority"))
    direct_override_social = _collect(("metrics", "camp_proto", "communication_knowledge_metrics", "direct_overrides_social_count"))
    duplicate_suppressed = _collect(("metrics", "camp_proto", "communication_knowledge_metrics", "repeated_duplicate_share_suppressed_count"))

    return {
        "scenario_family": str(scenario_family),
        "analysis_thresholds": {
            "min_legit_village_population": int(thresholds.min_legit_village_population),
            "min_legit_leader_village_population": int(thresholds.min_legit_leader_village_population),
            "early_extinction_threshold_tick": int(thresholds.early_extinction_threshold_tick),
            "early_mass_death_threshold_ratio": float(thresholds.early_mass_death_threshold_ratio),
        },
        "runs": run_list,
        "aggregate": {
            "run_count": int(len(run_list)),
            "avg_final_population": float(mean(final_pop)) if final_pop else 0.0,
            "extinction_run_ratio": float(sum(1.0 for v in extinct if v > 0.5) / max(1, len(extinct))),
            "early_mass_death_ratio": float(sum(1.0 for v in early_mass_death if v > 0.5) / max(1, len(early_mass_death))),
            "singleton_village_run_ratio": float(sum(1.0 for v in village_singleton if v >= 1.0) / max(1, len(village_singleton))),
            "singleton_leader_run_ratio": float(sum(1.0 for v in leader_singleton if v >= 1.0) / max(1, len(leader_singleton))),
            "avg_camps_formed": float(mean(camps_formed)) if camps_formed else 0.0,
            "avg_active_camps_final": float(mean(active_camps)) if active_camps else 0.0,
            "avg_camp_food_deposits": float(mean(camp_food_deposits)) if camp_food_deposits else 0.0,
            "avg_camp_food_consumptions": float(mean(camp_food_consumptions)) if camp_food_consumptions else 0.0,
            "avg_local_food_pressure_events": float(mean(local_food_pressure_events)) if local_food_pressure_events else 0.0,
            "avg_pressure_backed_food_deliveries": float(mean(pressure_backed_food_deliveries)) if pressure_backed_food_deliveries else 0.0,
            "avg_pressure_served_ratio": float(mean(pressure_served_ratio)) if pressure_served_ratio else 0.0,
            "avg_communication_events": float(mean(communication_events)) if communication_events else 0.0,
            "avg_shared_food_knowledge_used": float(mean(shared_food_knowledge_used)) if shared_food_knowledge_used else 0.0,
            "avg_shared_camp_knowledge_used": float(mean(shared_camp_knowledge_used)) if shared_camp_knowledge_used else 0.0,
            "avg_social_knowledge_accept_count": float(mean(social_accept)) if social_accept else 0.0,
            "avg_social_knowledge_reject_count": float(mean(social_reject)) if social_reject else 0.0,
            "avg_social_knowledge_reject_survival_priority": float(mean(social_reject_survival)) if social_reject_survival else 0.0,
            "avg_direct_overrides_social_count": float(mean(direct_override_social)) if direct_override_social else 0.0,
            "avg_repeated_duplicate_share_suppressed_count": float(mean(duplicate_suppressed)) if duplicate_suppressed else 0.0,
        },
    }
