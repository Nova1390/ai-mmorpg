from __future__ import annotations

import copy
from contextlib import contextmanager
from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Tuple
from pathlib import Path

import agent as agent_module
from brain import FoodBrain, LLMBrain
from planner import Planner
import world as world_module
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
    parameter_overrides: Optional[Dict[str, float]] = None
    debug_construction_trace: bool = False
    debug_construction_trace_path: Optional[str] = None
    debug_construction_trace_max_agents: int = 3
    debug_construction_trace_max_sites: int = 2


def _scaled_int(base: Any, scale: float, *, min_value: int = 1) -> int:
    return max(int(min_value), int(round(float(base) * float(scale))))


@contextmanager
def _temporary_parameter_overrides(overrides: Optional[Dict[str, float]]) -> Any:
    params = dict(overrides or {})
    if not params:
        yield
        return

    touched: List[Tuple[Any, str, Any]] = []

    def _set(module: Any, attr: str, value: Any) -> None:
        if not hasattr(module, attr):
            return
        touched.append((module, attr, copy.deepcopy(getattr(module, attr))))
        setattr(module, attr, value)

    # Environment parameters.
    if "food_regeneration_rate" in params:
        scale = float(params["food_regeneration_rate"])
        _set(world_module, "FOOD_RESPAWN_PER_TICK", _scaled_int(world_module.FOOD_RESPAWN_PER_TICK, scale))
    if "wild_food_density" in params:
        scale = float(params["wild_food_density"])
        _set(world_module, "NUM_FOOD", _scaled_int(world_module.NUM_FOOD, scale))
    if "food_patch_cluster_strength" in params:
        scale = float(params["food_patch_cluster_strength"])
        _set(world_module, "FOOD_PATCH_DENSITY_MULTIPLIER", max(0.1, float(world_module.FOOD_PATCH_DENSITY_MULTIPLIER) * scale))
        _set(world_module, "FOOD_PATCH_EXTRA_INITIAL_FOOD_RATIO", max(0.0, float(world_module.FOOD_PATCH_EXTRA_INITIAL_FOOD_RATIO) * scale))
    if "food_patch_distribution_variance" in params:
        scale = float(params["food_patch_distribution_variance"])
        min_r = _scaled_int(world_module.FOOD_PATCH_MIN_RADIUS, max(0.5, scale), min_value=2)
        max_r = max(min_r + 1, _scaled_int(world_module.FOOD_PATCH_MAX_RADIUS, max(0.6, scale), min_value=min_r + 1))
        _set(world_module, "FOOD_PATCH_MIN_RADIUS", min_r)
        _set(world_module, "FOOD_PATCH_MAX_RADIUS", max_r)

    # Agent survival dynamics.
    if "hunger_decay_rate" in params:
        scale = float(params["hunger_decay_rate"])
        _set(agent_module, "BASE_HUNGER_DECAY_PER_TICK", max(0.01, float(agent_module.BASE_HUNGER_DECAY_PER_TICK) * scale))
    if "food_value_per_unit" in params:
        scale = float(params["food_value_per_unit"])
        _set(agent_module, "FOOD_EAT_GAIN", _scaled_int(agent_module.FOOD_EAT_GAIN, scale))
        _set(world_module, "FOOD_EAT_GAIN", _scaled_int(world_module.FOOD_EAT_GAIN, scale))
    if "critical_hunger_threshold" in params:
        _set(agent_module, "SURVIVAL_CRITICAL_HUNGER_FOR_SOCIAL_KNOWLEDGE", float(params["critical_hunger_threshold"]))
    if "eat_trigger_threshold" in params:
        _set(agent_module, "EAT_TRIGGER_BASE_THRESHOLD", int(round(float(params["eat_trigger_threshold"]))))

    # Agent continuity.
    if "routine_success_extension_ticks" in params:
        _set(agent_module, "ROUTINE_SUCCESS_EXTENSION_TICKS", max(0, int(round(float(params["routine_success_extension_ticks"])))))
    if "routine_persistence_bias" in params:
        scale = float(params["routine_persistence_bias"])
        base_ticks = dict(getattr(agent_module, "ROLE_TASK_PERSISTENCE_TICKS", {}))
        scaled = {
            str(k): max(0, int(round(float(v) * scale)))
            for k, v in base_ticks.items()
        }
        _set(agent_module, "ROLE_TASK_PERSISTENCE_TICKS", scaled)

    # Settlement stability.
    if "camp_food_buffer_capacity" in params:
        scale = float(params["camp_food_buffer_capacity"])
        _set(world_module, "CAMP_FOOD_CACHE_CAPACITY", _scaled_int(world_module.CAMP_FOOD_CACHE_CAPACITY, scale))
    if "camp_food_access_radius" in params:
        _set(world_module, "CAMP_FOOD_ACCESS_RADIUS", max(1, int(round(float(params["camp_food_access_radius"])))))
    if "house_domestic_food_capacity" in params:
        scale = float(params["house_domestic_food_capacity"])
        _set(world_module, "HOUSE_DOMESTIC_FOOD_CAPACITY", _scaled_int(world_module.HOUSE_DOMESTIC_FOOD_CAPACITY, scale))

    try:
        yield
    finally:
        for module, attr, value in reversed(touched):
            setattr(module, attr, value)


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
    world.debug_construction_trace_enabled = bool(cfg.debug_construction_trace)
    world.debug_construction_trace_path = str(cfg.debug_construction_trace_path or "")
    world.debug_construction_trace_max_agents = max(1, int(cfg.debug_construction_trace_max_agents))
    world.debug_construction_trace_max_sites = max(1, int(cfg.debug_construction_trace_max_sites))
    if world.debug_construction_trace_enabled and world.debug_construction_trace_path:
        try:
            trace_path = Path(world.debug_construction_trace_path)
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            trace_path.write_text("", encoding="utf-8")
        except Exception:
            world.debug_construction_trace_enabled = False
            world.debug_construction_trace_path = ""
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
    with _temporary_parameter_overrides(cfg.parameter_overrides):
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
                "social_encounter_metrics": dict(cog.get("social_encounter_global", {})) if isinstance(cog.get("social_encounter_global", {}), dict) else {},
                "lifespan_continuity_metrics": dict(cog.get("lifespan_continuity_global", {})) if isinstance(cog.get("lifespan_continuity_global", {}), dict) else {},
                "construction_situated_metrics": dict(cog.get("construction_situated_diagnostics", {})) if isinstance(cog.get("construction_situated_diagnostics", {}), dict) else {},
                "road_purpose_metrics": {
                    "road_built_with_purpose_count": int(cog.get("road_built_with_purpose_count", 0)),
                    "road_build_suppressed_no_purpose": int(cog.get("road_build_suppressed_no_purpose", 0)),
                    "road_build_suppressed_reasons": dict(cog.get("road_build_suppressed_reasons", {})) if isinstance(cog.get("road_build_suppressed_reasons", {}), dict) else {},
                },
                "settlement_progression_metrics": dict(cog.get("settlement_progression_metrics", {})) if isinstance(cog.get("settlement_progression_metrics", {}), dict) else {},
                "material_feasibility_metrics": dict(cog.get("material_feasibility_metrics", {})) if isinstance(cog.get("material_feasibility_metrics", {}), dict) else {},
                "food_patch_metrics": {
                    "food_patch_count": int(world_block.get("food_patch_count", 0)),
                    "food_patch_total_area": int(world_block.get("food_patch_total_area", 0)),
                    "food_patch_food_spawned": int(world_block.get("food_patch_food_spawned", 0)),
                },
            },
            "behavior_map": dict(cog.get("behavior_map_global", {})) if isinstance(cog.get("behavior_map_global", {}), dict) else {},
            "settlement_legitimacy": {
                "villages_formed_count": int(len(seen_village_ids)),
                "village_creation_ticks": list(sorted(village_creation_ticks)),
                "village_population_at_creation": list(village_creation_pops),
                "singleton_village_count": int(singleton_village_count),
                "villages_under_legit_threshold_count": int(under_legit_village_count),
                "min_legit_village_population": int(thresholds.min_legit_village_population),
                "max_village_population_support": int(max(village_max_support.values())) if village_max_support else 0,
                "village_persistence_ticks": dict(village_persistence_ticks),
                "settlement_bottleneck_diagnostics": dict(cog.get("settlement_bottleneck_diagnostics", {})) if isinstance(cog.get("settlement_bottleneck_diagnostics", {}), dict) else {},
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
                "parameter_overrides": dict(cfg.parameter_overrides or {}),
                "debug_construction_trace": bool(cfg.debug_construction_trace),
                "debug_construction_trace_path": str(cfg.debug_construction_trace_path or ""),
                "debug_construction_trace_max_agents": int(cfg.debug_construction_trace_max_agents),
                "debug_construction_trace_max_sites": int(cfg.debug_construction_trace_max_sites),
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
    domestic_food_stored = _collect(("metrics", "camp_proto", "camp_food_metrics", "domestic_food_stored_total"))
    domestic_food_consumed = _collect(("metrics", "camp_proto", "camp_food_metrics", "domestic_food_consumed_total"))
    house_food_utilization = _collect(("metrics", "camp_proto", "camp_food_metrics", "house_food_capacity_utilization"))
    houses_with_food = _collect(("metrics", "camp_proto", "camp_food_metrics", "houses_with_food"))
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
    confirmed_memory_reinforcements = _collect(("metrics", "camp_proto", "communication_knowledge_metrics", "confirmed_memory_reinforcements"))
    direct_memory_invalidations = _collect(("metrics", "camp_proto", "communication_knowledge_metrics", "direct_memory_invalidations"))
    avg_useful_memory_age = _collect(("metrics", "camp_proto", "lifespan_continuity_metrics", "avg_useful_memory_age"))
    repeated_successful_loop_count = _collect(("metrics", "camp_proto", "lifespan_continuity_metrics", "repeated_successful_loop_count"))
    routine_persistence_ticks = _collect(("metrics", "camp_proto", "lifespan_continuity_metrics", "routine_persistence_ticks"))
    routine_abandonment_after_failure = _collect(("metrics", "camp_proto", "lifespan_continuity_metrics", "routine_abandonment_after_failure"))
    routine_abandonment_after_success = _collect(("metrics", "camp_proto", "lifespan_continuity_metrics", "routine_abandonment_after_success"))
    average_agent_age_alive = _collect(("metrics", "camp_proto", "lifespan_continuity_metrics", "average_agent_age_alive"))
    encounter_events = _collect(("metrics", "camp_proto", "social_encounter_metrics", "total_encounter_events"))
    familiarity_relationships = _collect(("metrics", "camp_proto", "social_encounter_metrics", "familiarity_relationships_count"))
    avg_familiarity_score = _collect(("metrics", "camp_proto", "social_encounter_metrics", "avg_familiarity_score"))
    familiar_proximity_events = _collect(("metrics", "camp_proto", "social_encounter_metrics", "familiar_agent_proximity_events"))
    social_density_bias_applied = _collect(("metrics", "camp_proto", "social_encounter_metrics", "social_density_bias_applied_count"))
    familiar_comm_bonus = _collect(("metrics", "camp_proto", "social_encounter_metrics", "familiar_communication_bonus_applied"))
    familiar_zone_reinforcement = _collect(("metrics", "camp_proto", "social_encounter_metrics", "familiar_zone_reinforcement_events"))
    familiar_camp_bias = _collect(("metrics", "camp_proto", "social_encounter_metrics", "familiar_camp_support_bias_events"))
    familiar_loop_bonus = _collect(("metrics", "camp_proto", "social_encounter_metrics", "familiar_loop_continuity_bonus"))
    familiar_anchor_events = _collect(("metrics", "camp_proto", "social_encounter_metrics", "familiar_anchor_exploration_events"))
    familiar_zone_updates = _collect(("metrics", "camp_proto", "social_encounter_metrics", "familiar_zone_score_updates"))
    familiar_zone_decay = _collect(("metrics", "camp_proto", "social_encounter_metrics", "familiar_zone_score_decay"))
    familiar_zone_clamps = _collect(("metrics", "camp_proto", "social_encounter_metrics", "familiar_zone_saturation_clamps"))
    dense_bias_reductions = _collect(("metrics", "camp_proto", "social_encounter_metrics", "dense_area_social_bias_reductions"))
    familiar_zone_low_payoff_decay = _collect(("metrics", "camp_proto", "social_encounter_metrics", "familiar_zone_decay_due_to_low_payoff"))
    overcrowded_familiar_suppressed = _collect(("metrics", "camp_proto", "social_encounter_metrics", "overcrowded_familiar_bias_suppressed"))
    density_safe_loop_reduced = _collect(("metrics", "camp_proto", "social_encounter_metrics", "density_safe_loop_bonus_reduced_count"))
    road_built_with_purpose = _collect(("metrics", "camp_proto", "road_purpose_metrics", "road_built_with_purpose_count"))
    road_suppressed_no_purpose = _collect(("metrics", "camp_proto", "road_purpose_metrics", "road_build_suppressed_no_purpose"))
    construction_on_site_ticks = _collect(("metrics", "camp_proto", "construction_situated_metrics", "construction_on_site_work_ticks"))
    construction_offsite_blocked = _collect(("metrics", "camp_proto", "construction_situated_metrics", "construction_offsite_blocked_ticks"))
    construction_interrupted_survival = _collect(("metrics", "camp_proto", "construction_situated_metrics", "construction_interrupted_survival"))
    construction_interrupted_invalid = _collect(("metrics", "camp_proto", "construction_situated_metrics", "construction_interrupted_invalid_target"))
    village_creation_attempts = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "village_creation_attempts"))
    village_creation_blocked = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "village_creation_blocked_count"))
    camp_to_village_attempts = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "camp_to_village_transition_attempts"))
    camp_to_village_failures = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "camp_to_village_transition_failures"))
    independent_clusters = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "independent_cluster_count"))
    local_viable_camp_retained = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "local_viable_camp_retained_count"))
    distant_pull_suppressed = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "distant_cluster_pull_suppressed_count"))
    camp_absorption_events = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "camp_absorption_events"))
    mature_nucleus_detected = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "mature_nucleus_detected_count"))
    mature_nucleus_failed = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "mature_nucleus_failed_transition_count"))
    mature_nucleus_success = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "mature_nucleus_successful_transition_count"))
    cluster_ecological_avg = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "cluster_ecological_productivity_score", "avg"))
    cluster_inertia_events = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "cluster_inertia_events"))
    dominant_saturation_penalty = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "dominant_cluster_saturation_penalty_applied"))
    absorption_delay_events = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "camp_absorption_delay_events"))
    secondary_persistence_ticks = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "secondary_cluster_persistence_ticks"))
    exploration_shift_low_density = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "exploration_shift_due_to_low_density"))
    secondary_cluster_nonzero = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "cluster_population_distribution_summary", "secondary_cluster_nonzero_count"))
    secondary_nucleus_structure_count = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "secondary_nucleus_structure_count"))
    secondary_nucleus_build_support_events = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "secondary_nucleus_build_support_events"))
    secondary_nucleus_material_delivery_events = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "secondary_nucleus_material_delivery_events"))
    secondary_nucleus_materialization_ticks = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "secondary_nucleus_materialization_ticks"))
    secondary_nucleus_absorption_during_build = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "secondary_nucleus_absorption_during_build"))
    secondary_nucleus_materialization_success = _collect(("metrics", "settlement_legitimacy", "settlement_bottleneck_diagnostics", "secondary_nucleus_materialization_success"))
    secondary_nucleus_birth_count = _collect(("metrics", "behavior_map", "secondary_nucleus_lifecycle", "secondary_nucleus_birth_count"))
    secondary_nucleus_absorption_count = _collect(("metrics", "behavior_map", "secondary_nucleus_lifecycle", "secondary_nucleus_absorption_count"))
    secondary_nucleus_decay_count = _collect(("metrics", "behavior_map", "secondary_nucleus_lifecycle", "secondary_nucleus_decay_count"))
    secondary_nucleus_persistence_ticks = _collect(("metrics", "behavior_map", "secondary_nucleus_lifecycle", "secondary_nucleus_persistence_ticks"))
    secondary_nucleus_village_attempts = _collect(("metrics", "behavior_map", "secondary_nucleus_lifecycle", "secondary_nucleus_village_attempts"))
    secondary_nucleus_village_successes = _collect(("metrics", "behavior_map", "secondary_nucleus_lifecycle", "secondary_nucleus_village_successes"))
    house_cluster_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "house_cluster_count"))
    avg_houses_per_cluster = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "avg_houses_per_cluster"))
    house_cluster_growth_events = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "house_cluster_growth_events"))
    farm_sites_created = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "farm_sites_created"))
    farm_work_events = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "farm_work_events"))
    farm_abandoned = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "farm_abandoned"))
    farm_yield_events = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "farm_yield_events"))
    farm_productivity_score_avg = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "farm_productivity_score_avg"))
    agents_farming_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "agents_farming_count"))
    farm_candidate_detected_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "farm_candidate_detected_count"))
    farm_candidate_bootstrap_trigger_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "farm_candidate_bootstrap_trigger_count"))
    farm_candidate_rejected_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "farm_candidate_rejected_count"))
    early_farm_loop_persistence_ticks = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "early_farm_loop_persistence_ticks"))
    early_farm_loop_abandonment_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "early_farm_loop_abandonment_count"))
    first_harvest_after_farm_creation_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "first_harvest_after_farm_creation_count"))
    cultural_practices_created = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "cultural_practices_created"))
    cultural_practices_reinforced = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "cultural_practices_reinforced"))
    cultural_practices_decayed = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "cultural_practices_decayed"))
    active_cultural_practices = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "active_cultural_practices"))
    agents_using_cultural_memory_bias = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "agents_using_cultural_memory_bias"))
    productive_food_patch_practices = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "productive_food_patch_practices"))
    proto_farm_practices = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "proto_farm_practices"))
    construction_cluster_practices = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "construction_cluster_practices"))
    storage_built_after_cluster_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "storage_built_after_cluster_count"))
    storage_built_without_cluster_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "storage_built_without_cluster_count"))
    storage_emergence_attempts = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "storage_emergence_attempts"))
    storage_emergence_successes = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "storage_emergence_successes"))
    storage_deferred_due_to_low_house_cluster = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "storage_deferred_due_to_low_house_cluster")
    )
    storage_deferred_due_to_low_throughput = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "storage_deferred_due_to_low_throughput")
    )
    storage_deferred_due_to_low_buffer_pressure = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "storage_deferred_due_to_low_buffer_pressure")
    )
    storage_deferred_due_to_low_surplus = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "storage_deferred_due_to_low_surplus")
    )
    storage_built_in_mature_cluster_count = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "storage_built_in_mature_cluster_count")
    )
    storage_supporting_active_house_cluster_count = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "storage_supporting_active_house_cluster_count")
    )
    storage_relief_of_domestic_pressure_events = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "storage_relief_of_domestic_pressure_events")
    )
    storage_relief_of_camp_pressure_events = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "storage_relief_of_camp_pressure_events")
    )
    active_storage_construction_sites = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "active_storage_construction_sites"))
    storage_builder_commitment_retained_ticks = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "storage_builder_commitment_retained_ticks")
    )
    storage_material_delivery_events = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "storage_material_delivery_events")
    )
    storage_construction_progress_ticks = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "storage_construction_progress_ticks")
    )
    storage_construction_interrupted_survival = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "storage_construction_interrupted_survival")
    )
    storage_construction_interrupted_invalid = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "storage_construction_interrupted_invalid")
    )
    storage_construction_abandoned_count = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "storage_construction_abandoned_count")
    )
    storage_construction_completed_count = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "storage_construction_completed_count")
    )
    construction_material_delivery_events = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "construction_material_delivery_events")
    )
    construction_material_delivery_to_active_site = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "construction_material_delivery_to_active_site")
    )
    construction_material_delivery_drift_events = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "construction_material_delivery_drift_events")
    )
    construction_progress_ticks = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "construction_progress_ticks")
    )
    construction_progress_stalled_ticks = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "construction_progress_stalled_ticks")
    )
    construction_completion_events = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "construction_completion_events")
    )
    construction_abandonment_events = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "construction_abandonment_events")
    )
    local_food_surplus_rate = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "local_food_surplus_rate")
    )
    local_resource_surplus_rate = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "local_resource_surplus_rate")
    )
    buffer_saturation_events = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "buffer_saturation_events")
    )
    surplus_triggered_storage_attempts = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "surplus_triggered_storage_attempts")
    )
    surplus_storage_construction_completed = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "surplus_storage_construction_completed")
    )
    surplus_storage_abandoned = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "surplus_storage_abandoned")
    )
    secondary_nucleus_with_house_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "secondary_nucleus_with_house_count"))
    secondary_nucleus_house_growth_events = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "secondary_nucleus_house_growth_events"))
    population_alive = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "population_alive"))
    population_births_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "population_births_count"))
    population_deaths_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "population_deaths_count"))
    population_deaths_hunger_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "population_deaths_hunger_count"))
    population_deaths_exhaustion_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "population_deaths_exhaustion_count"))
    population_deaths_other_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "population_deaths_other_count"))
    population_deaths_hunger_age_0_199_count = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "population_deaths_hunger_age_0_199_count")
    )
    population_deaths_hunger_age_200_599_count = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "population_deaths_hunger_age_200_599_count")
    )
    population_deaths_hunger_age_600_plus_count = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "population_deaths_hunger_age_600_plus_count")
    )
    hunger_deaths_before_first_food_acquisition = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "hunger_deaths_before_first_food_acquisition")
    )
    agent_average_age = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "agent_average_age"))
    agent_median_age_at_death = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "agent_median_age_at_death"))
    agent_average_lifespan_at_death = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "agent_average_lifespan_at_death"))
    avg_time_spawn_to_first_food_acquisition = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "avg_time_spawn_to_first_food_acquisition")
    )
    avg_time_high_hunger_to_eat = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "avg_time_high_hunger_to_eat")
    )
    avg_food_acquisition_interval_ticks = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "avg_food_acquisition_interval_ticks")
    )
    avg_food_acquisition_distance = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "avg_food_acquisition_distance")
    )
    avg_food_consumption_interval_ticks = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "avg_food_consumption_interval_ticks")
    )
    failed_food_seeking_attempts = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "failed_food_seeking_attempts")
    )
    fallback_food_search_activations = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "fallback_food_search_activations")
    )
    early_life_food_inventory_acquisition_count = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "early_life_food_inventory_acquisition_count")
    )
    high_hunger_to_eat_events_started = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "high_hunger_to_eat_events_started")
    )
    agent_hunger_relapse_after_first_food_count = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "agent_hunger_relapse_after_first_food_count")
    )
    early_food_priority_overrides = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "early_food_priority_overrides")
    )
    medium_term_food_priority_overrides = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "medium_term_food_priority_overrides")
    )
    avg_local_food_inventory_per_agent = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "avg_local_food_inventory_per_agent")
    )
    food_seeking_time_ratio = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "food_seeking_time_ratio")
    )
    food_source_contention_events = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "food_source_contention_events")
    )
    food_source_depletion_events = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "food_source_depletion_events")
    )
    food_respawned_total_observed = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "food_respawned_total_observed")
    )
    avg_foraging_yield_per_trip = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "avg_foraging_yield_per_trip")
    )
    avg_farming_yield_per_cycle = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "avg_farming_yield_per_cycle")
    )
    food_move_time_ratio = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "food_move_time_ratio")
    )
    food_harvest_time_ratio = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "food_harvest_time_ratio")
    )
    avg_local_food_basin_accessible = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "avg_local_food_basin_accessible")
    )
    avg_local_food_pressure_ratio = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "avg_local_food_pressure_ratio")
    )
    avg_local_food_basin_competing_agents = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "avg_local_food_basin_competing_agents")
    )
    avg_distance_to_viable_food_from_proto = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "avg_distance_to_viable_food_from_proto")
    )
    local_food_basin_severe_pressure_ticks = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "local_food_basin_severe_pressure_ticks")
    )
    local_food_basin_collapse_events = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "local_food_basin_collapse_events")
    )
    proto_settlement_abandoned_due_to_food_pressure_count = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "proto_settlement_abandoned_due_to_food_pressure_count")
    )
    food_scarcity_adaptive_retarget_events = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "food_scarcity_adaptive_retarget_events")
    )
    food_gathered_total_observed = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "food_gathered_total_observed")
    )
    food_consumed_total_observed = _collect(
        ("metrics", "camp_proto", "settlement_progression_metrics", "food_consumed_total_observed")
    )
    deaths_before_first_house_completed = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "deaths_before_first_house_completed"))
    deaths_before_settlement_stability_threshold = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "deaths_before_settlement_stability_threshold"))
    population_collapse_events = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "population_collapse_events"))
    settlement_proto_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "settlement_proto_count"))
    settlement_stable_village_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "settlement_stable_village_count"))
    settlement_abandoned_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "settlement_abandoned_count"))
    first_house_completion_tick = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "first_house_completion_tick"))
    first_storage_completion_tick = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "first_storage_completion_tick"))
    first_road_completion_tick = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "first_road_completion_tick"))
    first_village_formalization_tick = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "first_village_formalization_tick"))
    storage_built_before_house_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "storage_built_before_house_count"))
    road_built_before_house_threshold_count = _collect(("metrics", "camp_proto", "settlement_progression_metrics", "road_built_before_house_threshold_count"))
    wood_available_world_total = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "wood_available_world_total"))
    wood_available_on_map = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "wood_available_on_map"))
    wood_in_agent_inventories = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "wood_in_agent_inventories"))
    wood_in_storage_buildings = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "wood_in_storage_buildings"))
    wood_in_construction_buffers = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "wood_in_construction_buffers"))
    wood_gathered_total = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "wood_gathered_total"))
    wood_respawned_total = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "wood_respawned_total"))
    wood_consumed_for_construction_total = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "wood_consumed_for_construction_total")
    )
    wood_shortage_events = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "wood_shortage_events"))
    avg_local_wood_pressure = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "avg_local_wood_pressure"))
    construction_sites_created = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "construction_sites_created"))
    construction_sites_created_house = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_sites_created_house")
    )
    construction_sites_created_storage = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_sites_created_storage")
    )
    active_construction_sites = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "active_construction_sites"))
    partially_built_sites_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "partially_built_sites_count")
    )
    construction_stalled_ticks_material = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_stalled_ticks")
    )
    construction_stalled_sites_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_stalled_sites_count")
    )
    construction_completed_count_material = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_completed_count")
    )
    construction_abandoned_count_material = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_abandoned_count")
    )
    construction_material_delivery_failures = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_material_delivery_failures")
    )
    construction_material_shortage_blocks = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_material_shortage_blocks")
    )
    houses_completed_count = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "houses_completed_count"))
    storage_attempts = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "storage_attempts"))
    storage_completed_count = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "storage_completed_count"))
    storage_completion_rate = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "storage_completion_rate"))
    construction_delivery_attempts = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_delivery_attempts")
    )
    construction_delivery_successes = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_delivery_successes")
    )
    construction_delivery_failures = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_delivery_failures")
    )
    construction_delivery_to_site_events = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_delivery_to_site_events")
    )
    construction_delivery_to_wrong_target_or_drift = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_delivery_to_wrong_target_or_drift")
    )
    construction_delivery_avg_distance_to_site = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_delivery_avg_distance_to_site")
    )
    construction_delivery_avg_distance_to_source = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_delivery_avg_distance_to_source")
    )
    storage_delivery_failures = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "storage_delivery_failures"))
    house_delivery_failures = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "house_delivery_failures"))
    storage_delivery_successes = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "storage_delivery_successes"))
    house_delivery_successes = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "house_delivery_successes"))
    construction_site_waiting_for_material_ticks = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_waiting_for_material_ticks")
    )
    construction_site_waiting_for_builder_ticks = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_waiting_for_builder_ticks")
    )
    construction_site_waiting_total_ticks = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_waiting_total_ticks")
    )
    construction_site_progress_active_ticks = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_progress_active_ticks")
    )
    construction_site_starved_cycles = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_starved_cycles")
    )
    storage_waiting_for_material_ticks = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "storage_waiting_for_material_ticks")
    )
    house_waiting_for_material_ticks = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "house_waiting_for_material_ticks")
    )
    storage_waiting_for_builder_ticks = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "storage_waiting_for_builder_ticks")
    )
    house_waiting_for_builder_ticks = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "house_waiting_for_builder_ticks")
    )
    construction_site_lifetime_ticks_avg = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_lifetime_ticks_avg")
    )
    construction_site_progress_before_abandon_avg = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_progress_before_abandon_avg")
    )
    construction_site_material_units_delivered_avg = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_material_units_delivered_avg")
    )
    construction_site_material_units_missing_avg = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_material_units_missing_avg")
    )
    construction_site_material_units_required_total = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_material_units_required_total")
    )
    construction_site_material_units_delivered_total = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_material_units_delivered_total")
    )
    construction_site_material_units_remaining = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_material_units_remaining")
    )
    construction_site_required_work_ticks_total = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_required_work_ticks_total")
    )
    construction_site_completed_work_ticks_total = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_completed_work_ticks_total")
    )
    construction_site_remaining_work_ticks = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_remaining_work_ticks")
    )
    construction_build_state_planned_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_build_state_planned_count")
    )
    construction_build_state_supplying_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_build_state_supplying_count")
    )
    construction_build_state_buildable_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_build_state_buildable_count")
    )
    construction_build_state_in_progress_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_build_state_in_progress_count")
    )
    construction_build_state_paused_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_build_state_paused_count")
    )
    construction_build_state_completed_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_build_state_completed_count")
    )
    construction_near_complete_sites_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_near_complete_sites_count")
    )
    builder_assigned_site_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "builder_assigned_site_count")
    )
    builder_site_arrival_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "builder_site_arrival_count")
    )
    builder_left_site_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "builder_left_site_count")
    )
    builder_left_site_before_completion_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "builder_left_site_before_completion_count")
    )
    builder_waiting_on_site_ticks_total = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "builder_waiting_on_site_ticks_total")
    )
    builder_on_site_ticks_total = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "builder_on_site_ticks_total")
    )
    builder_work_tick_applied_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "builder_work_tick_applied_count")
    )
    builder_survival_override_during_construction_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "builder_survival_override_during_construction_count")
    )
    builder_redirected_to_storage_during_construction_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "builder_redirected_to_storage_during_construction_count")
    )
    builder_commitment_created_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "builder_commitment_created_count")
    )
    builder_commitment_pause_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "builder_commitment_pause_count")
    )
    builder_commitment_resume_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "builder_commitment_resume_count")
    )
    builder_commitment_completed_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "builder_commitment_completed_count")
    )
    builder_commitment_abandoned_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "builder_commitment_abandoned_count")
    )
    builder_returned_to_same_site_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "builder_returned_to_same_site_count")
    )
    builder_commitment_duration_avg = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "builder_commitment_duration_avg")
    )
    builder_commitment_resume_delay_avg = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "builder_commitment_resume_delay_avg")
    )
    construction_site_buildable_ticks_total = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_buildable_ticks_total")
    )
    construction_site_idle_buildable_ticks_total = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_idle_buildable_ticks_total")
    )
    construction_site_buildable_but_idle_ticks_total = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_buildable_but_idle_ticks_total")
    )
    construction_site_waiting_materials_ticks_total = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_waiting_materials_ticks_total")
    )
    construction_site_in_progress_ticks_total = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_in_progress_ticks_total")
    )
    construction_site_distinct_builders_avg = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_distinct_builders_avg")
    )
    construction_site_work_ticks_per_builder_avg = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_work_ticks_per_builder_avg")
    )
    construction_site_delivery_to_work_gap_avg = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_delivery_to_work_gap_avg")
    )
    construction_site_active_age_ticks_avg = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_active_age_ticks_avg")
    )
    construction_site_first_builder_arrival_delay_avg = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_first_builder_arrival_delay_avg")
    )
    construction_site_material_ready_to_first_work_delay_avg = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_material_ready_to_first_work_delay_avg")
    )
    construction_site_completion_time_avg = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_site_completion_time_avg")
    )
    construction_time_first_delivery_to_completion_avg = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_time_first_delivery_to_completion_avg")
    )
    construction_time_first_progress_to_completion_avg = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_time_first_progress_to_completion_avg")
    )
    construction_time_first_work_to_completion_avg = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_time_first_work_to_completion_avg")
    )
    construction_completed_after_first_delivery_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_completed_after_first_delivery_count")
    )
    construction_completed_after_started_progress_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_completed_after_started_progress_count")
    )
    construction_completed_after_first_work_count = _collect(
        ("metrics", "camp_proto", "material_feasibility_metrics", "construction_completed_after_first_work_count")
    )
    house_completion_time_avg = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "house_completion_time_avg"))
    storage_completion_time_avg = _collect(("metrics", "camp_proto", "material_feasibility_metrics", "storage_completion_time_avg"))

    avg_final_population_value = float(mean(final_pop)) if final_pop else 0.0
    avg_confirmed_memory_reinforcements_value = float(mean(confirmed_memory_reinforcements)) if confirmed_memory_reinforcements else 0.0
    avg_direct_memory_invalidations_value = float(mean(direct_memory_invalidations)) if direct_memory_invalidations else 0.0
    avg_useful_memory_age_value = float(mean(avg_useful_memory_age)) if avg_useful_memory_age else 0.0
    avg_repeated_successful_loop_count_value = float(mean(repeated_successful_loop_count)) if repeated_successful_loop_count else 0.0
    avg_routine_persistence_ticks_value = float(mean(routine_persistence_ticks)) if routine_persistence_ticks else 0.0
    avg_routine_abandonment_after_failure_value = float(mean(routine_abandonment_after_failure)) if routine_abandonment_after_failure else 0.0
    avg_routine_abandonment_after_success_value = float(mean(routine_abandonment_after_success)) if routine_abandonment_after_success else 0.0
    average_agent_age_alive_value = float(mean(average_agent_age_alive)) if average_agent_age_alive else 0.0
    run_ticks = max((int((run.get("scenario", {}) or {}).get("ticks", 0)) for run in run_list), default=0)
    avg_confirmed_memory_reinforcements_per_agent = round(
        avg_confirmed_memory_reinforcements_value / float(max(1.0, avg_final_population_value)), 4
    )
    avg_direct_memory_invalidations_per_agent = round(
        avg_direct_memory_invalidations_value / float(max(1.0, avg_final_population_value)), 4
    )
    avg_confirmed_memory_reinforcements_per_alive_agent_tick = round(
        avg_confirmed_memory_reinforcements_value / float(max(1.0, avg_final_population_value * float(max(1, run_ticks)))),
        8,
    )
    avg_direct_memory_invalidations_per_alive_agent_tick = round(
        avg_direct_memory_invalidations_value / float(max(1.0, avg_final_population_value * float(max(1, run_ticks)))),
        8,
    )
    avg_confirmed_to_invalidated_memory_ratio = round(
        avg_confirmed_memory_reinforcements_value / float(max(1.0, avg_direct_memory_invalidations_value)),
        4,
    )
    avg_routine_success_to_failure_abandonment_ratio = round(
        avg_routine_abandonment_after_success_value / float(max(1.0, avg_routine_abandonment_after_failure_value)),
        4,
    )

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
            "avg_final_population": avg_final_population_value,
            "extinction_run_ratio": float(sum(1.0 for v in extinct if v > 0.5) / max(1, len(extinct))),
            "early_mass_death_ratio": float(sum(1.0 for v in early_mass_death if v > 0.5) / max(1, len(early_mass_death))),
            "singleton_village_run_ratio": float(sum(1.0 for v in village_singleton if v >= 1.0) / max(1, len(village_singleton))),
            "singleton_leader_run_ratio": float(sum(1.0 for v in leader_singleton if v >= 1.0) / max(1, len(leader_singleton))),
            "avg_camps_formed": float(mean(camps_formed)) if camps_formed else 0.0,
            "avg_active_camps_final": float(mean(active_camps)) if active_camps else 0.0,
            "avg_camp_food_deposits": float(mean(camp_food_deposits)) if camp_food_deposits else 0.0,
            "avg_camp_food_consumptions": float(mean(camp_food_consumptions)) if camp_food_consumptions else 0.0,
            "avg_domestic_food_stored_total": float(mean(domestic_food_stored)) if domestic_food_stored else 0.0,
            "avg_domestic_food_consumed_total": float(mean(domestic_food_consumed)) if domestic_food_consumed else 0.0,
            "avg_house_food_capacity_utilization": float(mean(house_food_utilization)) if house_food_utilization else 0.0,
            "avg_houses_with_food": float(mean(houses_with_food)) if houses_with_food else 0.0,
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
            "avg_confirmed_memory_reinforcements": avg_confirmed_memory_reinforcements_value,
            "avg_direct_memory_invalidations": avg_direct_memory_invalidations_value,
            "avg_useful_memory_age": avg_useful_memory_age_value,
            "avg_repeated_successful_loop_count": avg_repeated_successful_loop_count_value,
            "avg_routine_persistence_ticks": avg_routine_persistence_ticks_value,
            "avg_routine_abandonment_after_failure": avg_routine_abandonment_after_failure_value,
            "avg_routine_abandonment_after_success": avg_routine_abandonment_after_success_value,
            "avg_average_agent_age_alive": average_agent_age_alive_value,
            "average_agent_age_alive": average_agent_age_alive_value,
            "avg_confirmed_memory_reinforcements_per_agent": avg_confirmed_memory_reinforcements_per_agent,
            "avg_direct_memory_invalidations_per_agent": avg_direct_memory_invalidations_per_agent,
            "avg_confirmed_memory_reinforcements_per_alive_agent_tick": avg_confirmed_memory_reinforcements_per_alive_agent_tick,
            "avg_direct_memory_invalidations_per_alive_agent_tick": avg_direct_memory_invalidations_per_alive_agent_tick,
            "avg_confirmed_to_invalidated_memory_ratio": avg_confirmed_to_invalidated_memory_ratio,
            "avg_routine_success_to_failure_abandonment_ratio": avg_routine_success_to_failure_abandonment_ratio,
            "avg_total_encounter_events": float(mean(encounter_events)) if encounter_events else 0.0,
            "avg_familiarity_relationships_count": float(mean(familiarity_relationships)) if familiarity_relationships else 0.0,
            "avg_familiarity_score": float(mean(avg_familiarity_score)) if avg_familiarity_score else 0.0,
            "avg_familiar_agent_proximity_events": float(mean(familiar_proximity_events)) if familiar_proximity_events else 0.0,
            "avg_social_density_bias_applied_count": float(mean(social_density_bias_applied)) if social_density_bias_applied else 0.0,
            "avg_familiar_communication_bonus_applied": float(mean(familiar_comm_bonus)) if familiar_comm_bonus else 0.0,
            "avg_familiar_zone_reinforcement_events": float(mean(familiar_zone_reinforcement)) if familiar_zone_reinforcement else 0.0,
            "avg_familiar_camp_support_bias_events": float(mean(familiar_camp_bias)) if familiar_camp_bias else 0.0,
            "avg_familiar_loop_continuity_bonus": float(mean(familiar_loop_bonus)) if familiar_loop_bonus else 0.0,
            "avg_familiar_anchor_exploration_events": float(mean(familiar_anchor_events)) if familiar_anchor_events else 0.0,
            "avg_familiar_zone_score_updates": float(mean(familiar_zone_updates)) if familiar_zone_updates else 0.0,
            "avg_familiar_zone_score_decay": float(mean(familiar_zone_decay)) if familiar_zone_decay else 0.0,
            "avg_familiar_zone_saturation_clamps": float(mean(familiar_zone_clamps)) if familiar_zone_clamps else 0.0,
            "avg_dense_area_social_bias_reductions": float(mean(dense_bias_reductions)) if dense_bias_reductions else 0.0,
            "avg_familiar_zone_decay_due_to_low_payoff": float(mean(familiar_zone_low_payoff_decay)) if familiar_zone_low_payoff_decay else 0.0,
            "avg_overcrowded_familiar_bias_suppressed": float(mean(overcrowded_familiar_suppressed)) if overcrowded_familiar_suppressed else 0.0,
            "avg_density_safe_loop_bonus_reduced_count": float(mean(density_safe_loop_reduced)) if density_safe_loop_reduced else 0.0,
            "avg_road_built_with_purpose_count": float(mean(road_built_with_purpose)) if road_built_with_purpose else 0.0,
            "avg_road_build_suppressed_no_purpose": float(mean(road_suppressed_no_purpose)) if road_suppressed_no_purpose else 0.0,
            "avg_construction_on_site_work_ticks": float(mean(construction_on_site_ticks)) if construction_on_site_ticks else 0.0,
            "avg_construction_offsite_blocked_ticks": float(mean(construction_offsite_blocked)) if construction_offsite_blocked else 0.0,
            "avg_construction_interrupted_survival": float(mean(construction_interrupted_survival)) if construction_interrupted_survival else 0.0,
            "avg_construction_interrupted_invalid_target": float(mean(construction_interrupted_invalid)) if construction_interrupted_invalid else 0.0,
            "avg_village_creation_attempts": float(mean(village_creation_attempts)) if village_creation_attempts else 0.0,
            "avg_village_creation_blocked_count": float(mean(village_creation_blocked)) if village_creation_blocked else 0.0,
            "avg_independent_cluster_count": float(mean(independent_clusters)) if independent_clusters else 0.0,
            "avg_camp_to_village_transition_attempts": float(mean(camp_to_village_attempts)) if camp_to_village_attempts else 0.0,
            "avg_camp_to_village_transition_failures": float(mean(camp_to_village_failures)) if camp_to_village_failures else 0.0,
            "avg_local_viable_camp_retained_count": float(mean(local_viable_camp_retained)) if local_viable_camp_retained else 0.0,
            "avg_distant_cluster_pull_suppressed_count": float(mean(distant_pull_suppressed)) if distant_pull_suppressed else 0.0,
            "avg_camp_absorption_events": float(mean(camp_absorption_events)) if camp_absorption_events else 0.0,
            "avg_mature_nucleus_detected_count": float(mean(mature_nucleus_detected)) if mature_nucleus_detected else 0.0,
            "avg_mature_nucleus_failed_transition_count": float(mean(mature_nucleus_failed)) if mature_nucleus_failed else 0.0,
            "avg_mature_nucleus_successful_transition_count": float(mean(mature_nucleus_success)) if mature_nucleus_success else 0.0,
            "avg_cluster_ecological_productivity_score": float(mean(cluster_ecological_avg)) if cluster_ecological_avg else 0.0,
            "avg_cluster_inertia_events": float(mean(cluster_inertia_events)) if cluster_inertia_events else 0.0,
            "avg_dominant_cluster_saturation_penalty_applied": float(mean(dominant_saturation_penalty)) if dominant_saturation_penalty else 0.0,
            "avg_camp_absorption_delay_events": float(mean(absorption_delay_events)) if absorption_delay_events else 0.0,
            "avg_secondary_cluster_persistence_ticks": float(mean(secondary_persistence_ticks)) if secondary_persistence_ticks else 0.0,
            "avg_exploration_shift_due_to_low_density": float(mean(exploration_shift_low_density)) if exploration_shift_low_density else 0.0,
            "avg_secondary_cluster_nonzero_count": float(mean(secondary_cluster_nonzero)) if secondary_cluster_nonzero else 0.0,
            "avg_secondary_nucleus_structure_count": float(mean(secondary_nucleus_structure_count)) if secondary_nucleus_structure_count else 0.0,
            "avg_secondary_nucleus_build_support_events": float(mean(secondary_nucleus_build_support_events)) if secondary_nucleus_build_support_events else 0.0,
            "avg_secondary_nucleus_material_delivery_events": float(mean(secondary_nucleus_material_delivery_events)) if secondary_nucleus_material_delivery_events else 0.0,
            "avg_secondary_nucleus_materialization_ticks": float(mean(secondary_nucleus_materialization_ticks)) if secondary_nucleus_materialization_ticks else 0.0,
            "avg_secondary_nucleus_absorption_during_build": float(mean(secondary_nucleus_absorption_during_build)) if secondary_nucleus_absorption_during_build else 0.0,
            "avg_secondary_nucleus_materialization_success": float(mean(secondary_nucleus_materialization_success)) if secondary_nucleus_materialization_success else 0.0,
            "avg_secondary_nucleus_birth_count": float(mean(secondary_nucleus_birth_count)) if secondary_nucleus_birth_count else 0.0,
            "avg_secondary_nucleus_absorption_count": float(mean(secondary_nucleus_absorption_count)) if secondary_nucleus_absorption_count else 0.0,
            "avg_secondary_nucleus_decay_count": float(mean(secondary_nucleus_decay_count)) if secondary_nucleus_decay_count else 0.0,
            "avg_secondary_nucleus_persistence_ticks": float(mean(secondary_nucleus_persistence_ticks)) if secondary_nucleus_persistence_ticks else 0.0,
            "avg_secondary_nucleus_village_attempts": float(mean(secondary_nucleus_village_attempts)) if secondary_nucleus_village_attempts else 0.0,
            "avg_secondary_nucleus_village_successes": float(mean(secondary_nucleus_village_successes)) if secondary_nucleus_village_successes else 0.0,
            "avg_house_cluster_count": float(mean(house_cluster_count)) if house_cluster_count else 0.0,
            "avg_houses_per_cluster": float(mean(avg_houses_per_cluster)) if avg_houses_per_cluster else 0.0,
            "avg_house_cluster_growth_events": float(mean(house_cluster_growth_events)) if house_cluster_growth_events else 0.0,
            "avg_farm_sites_created": float(mean(farm_sites_created)) if farm_sites_created else 0.0,
            "avg_farm_work_events": float(mean(farm_work_events)) if farm_work_events else 0.0,
            "avg_farm_abandoned": float(mean(farm_abandoned)) if farm_abandoned else 0.0,
            "avg_farm_yield_events": float(mean(farm_yield_events)) if farm_yield_events else 0.0,
            "avg_farm_productivity_score_avg": float(mean(farm_productivity_score_avg)) if farm_productivity_score_avg else 0.0,
            "avg_agents_farming_count": float(mean(agents_farming_count)) if agents_farming_count else 0.0,
            "avg_farm_candidate_detected_count": float(mean(farm_candidate_detected_count)) if farm_candidate_detected_count else 0.0,
            "avg_farm_candidate_bootstrap_trigger_count": float(mean(farm_candidate_bootstrap_trigger_count)) if farm_candidate_bootstrap_trigger_count else 0.0,
            "avg_farm_candidate_rejected_count": float(mean(farm_candidate_rejected_count)) if farm_candidate_rejected_count else 0.0,
            "avg_early_farm_loop_persistence_ticks": float(mean(early_farm_loop_persistence_ticks)) if early_farm_loop_persistence_ticks else 0.0,
            "avg_early_farm_loop_abandonment_count": float(mean(early_farm_loop_abandonment_count)) if early_farm_loop_abandonment_count else 0.0,
            "avg_first_harvest_after_farm_creation_count": float(mean(first_harvest_after_farm_creation_count)) if first_harvest_after_farm_creation_count else 0.0,
            "avg_cultural_practices_created": float(mean(cultural_practices_created)) if cultural_practices_created else 0.0,
            "avg_cultural_practices_reinforced": float(mean(cultural_practices_reinforced)) if cultural_practices_reinforced else 0.0,
            "avg_cultural_practices_decayed": float(mean(cultural_practices_decayed)) if cultural_practices_decayed else 0.0,
            "avg_active_cultural_practices": float(mean(active_cultural_practices)) if active_cultural_practices else 0.0,
            "avg_agents_using_cultural_memory_bias": float(mean(agents_using_cultural_memory_bias)) if agents_using_cultural_memory_bias else 0.0,
            "avg_productive_food_patch_practices": float(mean(productive_food_patch_practices)) if productive_food_patch_practices else 0.0,
            "avg_proto_farm_practices": float(mean(proto_farm_practices)) if proto_farm_practices else 0.0,
            "avg_construction_cluster_practices": float(mean(construction_cluster_practices)) if construction_cluster_practices else 0.0,
            "avg_storage_built_after_cluster_count": float(mean(storage_built_after_cluster_count)) if storage_built_after_cluster_count else 0.0,
            "avg_storage_built_without_cluster_count": float(mean(storage_built_without_cluster_count)) if storage_built_without_cluster_count else 0.0,
            "avg_storage_emergence_attempts": float(mean(storage_emergence_attempts)) if storage_emergence_attempts else 0.0,
            "avg_storage_emergence_successes": float(mean(storage_emergence_successes)) if storage_emergence_successes else 0.0,
            "avg_storage_deferred_due_to_low_house_cluster": float(
                mean(storage_deferred_due_to_low_house_cluster)
            ) if storage_deferred_due_to_low_house_cluster else 0.0,
            "avg_storage_deferred_due_to_low_throughput": float(
                mean(storage_deferred_due_to_low_throughput)
            ) if storage_deferred_due_to_low_throughput else 0.0,
            "avg_storage_deferred_due_to_low_buffer_pressure": float(
                mean(storage_deferred_due_to_low_buffer_pressure)
            ) if storage_deferred_due_to_low_buffer_pressure else 0.0,
            "avg_storage_deferred_due_to_low_surplus": float(
                mean(storage_deferred_due_to_low_surplus)
            ) if storage_deferred_due_to_low_surplus else 0.0,
            "avg_storage_built_in_mature_cluster_count": float(
                mean(storage_built_in_mature_cluster_count)
            ) if storage_built_in_mature_cluster_count else 0.0,
            "avg_storage_supporting_active_house_cluster_count": float(
                mean(storage_supporting_active_house_cluster_count)
            ) if storage_supporting_active_house_cluster_count else 0.0,
            "avg_storage_relief_of_domestic_pressure_events": float(
                mean(storage_relief_of_domestic_pressure_events)
            ) if storage_relief_of_domestic_pressure_events else 0.0,
            "avg_storage_relief_of_camp_pressure_events": float(
                mean(storage_relief_of_camp_pressure_events)
            ) if storage_relief_of_camp_pressure_events else 0.0,
            "avg_active_storage_construction_sites": float(mean(active_storage_construction_sites)) if active_storage_construction_sites else 0.0,
            "avg_storage_builder_commitment_retained_ticks": float(
                mean(storage_builder_commitment_retained_ticks)
            ) if storage_builder_commitment_retained_ticks else 0.0,
            "avg_storage_material_delivery_events": float(mean(storage_material_delivery_events)) if storage_material_delivery_events else 0.0,
            "avg_storage_construction_progress_ticks": float(
                mean(storage_construction_progress_ticks)
            ) if storage_construction_progress_ticks else 0.0,
            "avg_storage_construction_interrupted_survival": float(
                mean(storage_construction_interrupted_survival)
            ) if storage_construction_interrupted_survival else 0.0,
            "avg_storage_construction_interrupted_invalid": float(
                mean(storage_construction_interrupted_invalid)
            ) if storage_construction_interrupted_invalid else 0.0,
            "avg_storage_construction_abandoned_count": float(
                mean(storage_construction_abandoned_count)
            ) if storage_construction_abandoned_count else 0.0,
            "avg_storage_construction_completed_count": float(
                mean(storage_construction_completed_count)
            ) if storage_construction_completed_count else 0.0,
            "avg_construction_material_delivery_events": float(
                mean(construction_material_delivery_events)
            ) if construction_material_delivery_events else 0.0,
            "avg_construction_material_delivery_to_active_site": float(
                mean(construction_material_delivery_to_active_site)
            ) if construction_material_delivery_to_active_site else 0.0,
            "avg_construction_material_delivery_drift_events": float(
                mean(construction_material_delivery_drift_events)
            ) if construction_material_delivery_drift_events else 0.0,
            "avg_construction_progress_ticks": float(mean(construction_progress_ticks)) if construction_progress_ticks else 0.0,
            "avg_construction_progress_stalled_ticks": float(
                mean(construction_progress_stalled_ticks)
            ) if construction_progress_stalled_ticks else 0.0,
            "avg_construction_completion_events": float(
                mean(construction_completion_events)
            ) if construction_completion_events else 0.0,
            "avg_construction_abandonment_events": float(
                mean(construction_abandonment_events)
            ) if construction_abandonment_events else 0.0,
            "avg_local_food_surplus_rate": float(mean(local_food_surplus_rate)) if local_food_surplus_rate else 0.0,
            "avg_local_resource_surplus_rate": float(mean(local_resource_surplus_rate)) if local_resource_surplus_rate else 0.0,
            "avg_buffer_saturation_events": float(mean(buffer_saturation_events)) if buffer_saturation_events else 0.0,
            "avg_surplus_triggered_storage_attempts": float(
                mean(surplus_triggered_storage_attempts)
            ) if surplus_triggered_storage_attempts else 0.0,
            "avg_surplus_storage_construction_completed": float(
                mean(surplus_storage_construction_completed)
            ) if surplus_storage_construction_completed else 0.0,
            "avg_surplus_storage_abandoned": float(mean(surplus_storage_abandoned)) if surplus_storage_abandoned else 0.0,
            "avg_secondary_nucleus_with_house_count": float(mean(secondary_nucleus_with_house_count)) if secondary_nucleus_with_house_count else 0.0,
            "avg_secondary_nucleus_house_growth_events": float(mean(secondary_nucleus_house_growth_events)) if secondary_nucleus_house_growth_events else 0.0,
            "avg_population_alive": float(mean(population_alive)) if population_alive else 0.0,
            "avg_population_births_count": float(mean(population_births_count)) if population_births_count else 0.0,
            "avg_population_deaths_count": float(mean(population_deaths_count)) if population_deaths_count else 0.0,
            "avg_population_deaths_hunger_count": float(mean(population_deaths_hunger_count)) if population_deaths_hunger_count else 0.0,
            "avg_population_deaths_exhaustion_count": float(mean(population_deaths_exhaustion_count)) if population_deaths_exhaustion_count else 0.0,
            "avg_population_deaths_other_count": float(mean(population_deaths_other_count)) if population_deaths_other_count else 0.0,
            "avg_population_deaths_hunger_age_0_199_count": float(
                mean(population_deaths_hunger_age_0_199_count)
            ) if population_deaths_hunger_age_0_199_count else 0.0,
            "avg_population_deaths_hunger_age_200_599_count": float(
                mean(population_deaths_hunger_age_200_599_count)
            ) if population_deaths_hunger_age_200_599_count else 0.0,
            "avg_population_deaths_hunger_age_600_plus_count": float(
                mean(population_deaths_hunger_age_600_plus_count)
            ) if population_deaths_hunger_age_600_plus_count else 0.0,
            "avg_hunger_deaths_before_first_food_acquisition": float(
                mean(hunger_deaths_before_first_food_acquisition)
            ) if hunger_deaths_before_first_food_acquisition else 0.0,
            "avg_agent_average_age": float(mean(agent_average_age)) if agent_average_age else 0.0,
            "avg_agent_median_age_at_death": float(mean(agent_median_age_at_death)) if agent_median_age_at_death else 0.0,
            "avg_agent_average_lifespan_at_death": float(mean(agent_average_lifespan_at_death)) if agent_average_lifespan_at_death else 0.0,
            "avg_time_spawn_to_first_food_acquisition": float(
                mean(avg_time_spawn_to_first_food_acquisition)
            ) if avg_time_spawn_to_first_food_acquisition else 0.0,
            "avg_time_high_hunger_to_eat": float(mean(avg_time_high_hunger_to_eat)) if avg_time_high_hunger_to_eat else 0.0,
            "avg_food_acquisition_interval_ticks": float(
                mean(avg_food_acquisition_interval_ticks)
            ) if avg_food_acquisition_interval_ticks else 0.0,
            "avg_food_acquisition_distance": float(
                mean(avg_food_acquisition_distance)
            ) if avg_food_acquisition_distance else 0.0,
            "avg_food_consumption_interval_ticks": float(
                mean(avg_food_consumption_interval_ticks)
            ) if avg_food_consumption_interval_ticks else 0.0,
            "avg_failed_food_seeking_attempts": float(mean(failed_food_seeking_attempts)) if failed_food_seeking_attempts else 0.0,
            "avg_fallback_food_search_activations": float(
                mean(fallback_food_search_activations)
            ) if fallback_food_search_activations else 0.0,
            "avg_early_life_food_inventory_acquisition_count": float(
                mean(early_life_food_inventory_acquisition_count)
            ) if early_life_food_inventory_acquisition_count else 0.0,
            "avg_high_hunger_to_eat_events_started": float(
                mean(high_hunger_to_eat_events_started)
            ) if high_hunger_to_eat_events_started else 0.0,
            "avg_agent_hunger_relapse_after_first_food_count": float(
                mean(agent_hunger_relapse_after_first_food_count)
            ) if agent_hunger_relapse_after_first_food_count else 0.0,
            "avg_early_food_priority_overrides": float(mean(early_food_priority_overrides)) if early_food_priority_overrides else 0.0,
            "avg_medium_term_food_priority_overrides": float(
                mean(medium_term_food_priority_overrides)
            ) if medium_term_food_priority_overrides else 0.0,
            "avg_local_food_inventory_per_agent": float(
                mean(avg_local_food_inventory_per_agent)
            ) if avg_local_food_inventory_per_agent else 0.0,
            "avg_food_seeking_time_ratio": float(mean(food_seeking_time_ratio)) if food_seeking_time_ratio else 0.0,
            "avg_food_source_contention_events": float(
                mean(food_source_contention_events)
            ) if food_source_contention_events else 0.0,
            "avg_food_source_depletion_events": float(
                mean(food_source_depletion_events)
            ) if food_source_depletion_events else 0.0,
            "avg_food_respawned_total_observed": float(
                mean(food_respawned_total_observed)
            ) if food_respawned_total_observed else 0.0,
            "avg_foraging_yield_per_trip": float(
                mean(avg_foraging_yield_per_trip)
            ) if avg_foraging_yield_per_trip else 0.0,
            "avg_farming_yield_per_cycle": float(
                mean(avg_farming_yield_per_cycle)
            ) if avg_farming_yield_per_cycle else 0.0,
            "avg_food_move_time_ratio": float(
                mean(food_move_time_ratio)
            ) if food_move_time_ratio else 0.0,
            "avg_food_harvest_time_ratio": float(
                mean(food_harvest_time_ratio)
            ) if food_harvest_time_ratio else 0.0,
            "avg_local_food_basin_accessible": float(
                mean(avg_local_food_basin_accessible)
            ) if avg_local_food_basin_accessible else 0.0,
            "avg_local_food_pressure_ratio": float(
                mean(avg_local_food_pressure_ratio)
            ) if avg_local_food_pressure_ratio else 0.0,
            "avg_local_food_basin_competing_agents": float(
                mean(avg_local_food_basin_competing_agents)
            ) if avg_local_food_basin_competing_agents else 0.0,
            "avg_distance_to_viable_food_from_proto": float(
                mean(avg_distance_to_viable_food_from_proto)
            ) if avg_distance_to_viable_food_from_proto else 0.0,
            "avg_local_food_basin_severe_pressure_ticks": float(
                mean(local_food_basin_severe_pressure_ticks)
            ) if local_food_basin_severe_pressure_ticks else 0.0,
            "avg_local_food_basin_collapse_events": float(
                mean(local_food_basin_collapse_events)
            ) if local_food_basin_collapse_events else 0.0,
            "avg_proto_settlement_abandoned_due_to_food_pressure_count": float(
                mean(proto_settlement_abandoned_due_to_food_pressure_count)
            ) if proto_settlement_abandoned_due_to_food_pressure_count else 0.0,
            "avg_food_scarcity_adaptive_retarget_events": float(
                mean(food_scarcity_adaptive_retarget_events)
            ) if food_scarcity_adaptive_retarget_events else 0.0,
            "avg_food_gathered_total_observed": float(mean(food_gathered_total_observed)) if food_gathered_total_observed else 0.0,
            "avg_food_consumed_total_observed": float(mean(food_consumed_total_observed)) if food_consumed_total_observed else 0.0,
            "avg_deaths_before_first_house_completed": float(mean(deaths_before_first_house_completed)) if deaths_before_first_house_completed else 0.0,
            "avg_deaths_before_settlement_stability_threshold": float(mean(deaths_before_settlement_stability_threshold)) if deaths_before_settlement_stability_threshold else 0.0,
            "avg_population_collapse_events": float(mean(population_collapse_events)) if population_collapse_events else 0.0,
            "avg_settlement_proto_count": float(mean(settlement_proto_count)) if settlement_proto_count else 0.0,
            "avg_settlement_stable_village_count": float(mean(settlement_stable_village_count)) if settlement_stable_village_count else 0.0,
            "avg_settlement_abandoned_count": float(mean(settlement_abandoned_count)) if settlement_abandoned_count else 0.0,
            "avg_first_house_completion_tick": float(mean(first_house_completion_tick)) if first_house_completion_tick else 0.0,
            "avg_first_storage_completion_tick": float(mean(first_storage_completion_tick)) if first_storage_completion_tick else 0.0,
            "avg_first_road_completion_tick": float(mean(first_road_completion_tick)) if first_road_completion_tick else 0.0,
            "avg_first_village_formalization_tick": float(mean(first_village_formalization_tick)) if first_village_formalization_tick else 0.0,
            "avg_storage_built_before_house_count": float(mean(storage_built_before_house_count)) if storage_built_before_house_count else 0.0,
            "avg_road_built_before_house_threshold_count": float(mean(road_built_before_house_threshold_count)) if road_built_before_house_threshold_count else 0.0,
            "avg_wood_available_world_total": float(mean(wood_available_world_total)) if wood_available_world_total else 0.0,
            "avg_wood_available_on_map": float(mean(wood_available_on_map)) if wood_available_on_map else 0.0,
            "avg_wood_in_agent_inventories": float(mean(wood_in_agent_inventories)) if wood_in_agent_inventories else 0.0,
            "avg_wood_in_storage_buildings": float(mean(wood_in_storage_buildings)) if wood_in_storage_buildings else 0.0,
            "avg_wood_in_construction_buffers": float(mean(wood_in_construction_buffers)) if wood_in_construction_buffers else 0.0,
            "avg_wood_gathered_total": float(mean(wood_gathered_total)) if wood_gathered_total else 0.0,
            "avg_wood_respawned_total": float(mean(wood_respawned_total)) if wood_respawned_total else 0.0,
            "avg_wood_consumed_for_construction_total": float(
                mean(wood_consumed_for_construction_total)
            ) if wood_consumed_for_construction_total else 0.0,
            "avg_wood_shortage_events": float(mean(wood_shortage_events)) if wood_shortage_events else 0.0,
            "avg_local_wood_pressure": float(mean(avg_local_wood_pressure)) if avg_local_wood_pressure else 0.0,
            "avg_construction_sites_created": float(mean(construction_sites_created)) if construction_sites_created else 0.0,
            "avg_construction_sites_created_house": float(
                mean(construction_sites_created_house)
            ) if construction_sites_created_house else 0.0,
            "avg_construction_sites_created_storage": float(
                mean(construction_sites_created_storage)
            ) if construction_sites_created_storage else 0.0,
            "avg_active_construction_sites": float(mean(active_construction_sites)) if active_construction_sites else 0.0,
            "avg_partially_built_sites_count": float(mean(partially_built_sites_count)) if partially_built_sites_count else 0.0,
            "avg_construction_stalled_ticks_material": float(
                mean(construction_stalled_ticks_material)
            ) if construction_stalled_ticks_material else 0.0,
            "avg_construction_stalled_sites_count": float(
                mean(construction_stalled_sites_count)
            ) if construction_stalled_sites_count else 0.0,
            "avg_construction_completed_count": float(
                mean(construction_completed_count_material)
            ) if construction_completed_count_material else 0.0,
            "avg_construction_abandoned_count_material": float(
                mean(construction_abandoned_count_material)
            ) if construction_abandoned_count_material else 0.0,
            "avg_construction_material_delivery_failures": float(
                mean(construction_material_delivery_failures)
            ) if construction_material_delivery_failures else 0.0,
            "avg_construction_material_shortage_blocks": float(
                mean(construction_material_shortage_blocks)
            ) if construction_material_shortage_blocks else 0.0,
            "avg_houses_completed_count": float(mean(houses_completed_count)) if houses_completed_count else 0.0,
            "avg_storage_attempts": float(mean(storage_attempts)) if storage_attempts else 0.0,
            "avg_storage_completed_count": float(mean(storage_completed_count)) if storage_completed_count else 0.0,
            "avg_storage_completion_rate": float(mean(storage_completion_rate)) if storage_completion_rate else 0.0,
            "avg_construction_delivery_attempts": float(mean(construction_delivery_attempts)) if construction_delivery_attempts else 0.0,
            "avg_construction_delivery_successes": float(mean(construction_delivery_successes)) if construction_delivery_successes else 0.0,
            "avg_construction_delivery_failures": float(mean(construction_delivery_failures)) if construction_delivery_failures else 0.0,
            "avg_construction_delivery_to_site_events": float(
                mean(construction_delivery_to_site_events)
            ) if construction_delivery_to_site_events else 0.0,
            "avg_construction_delivery_to_wrong_target_or_drift": float(
                mean(construction_delivery_to_wrong_target_or_drift)
            ) if construction_delivery_to_wrong_target_or_drift else 0.0,
            "avg_construction_delivery_avg_distance_to_site": float(
                mean(construction_delivery_avg_distance_to_site)
            ) if construction_delivery_avg_distance_to_site else 0.0,
            "avg_construction_delivery_avg_distance_to_source": float(
                mean(construction_delivery_avg_distance_to_source)
            ) if construction_delivery_avg_distance_to_source else 0.0,
            "avg_storage_delivery_failures": float(mean(storage_delivery_failures)) if storage_delivery_failures else 0.0,
            "avg_house_delivery_failures": float(mean(house_delivery_failures)) if house_delivery_failures else 0.0,
            "avg_storage_delivery_successes": float(mean(storage_delivery_successes)) if storage_delivery_successes else 0.0,
            "avg_house_delivery_successes": float(mean(house_delivery_successes)) if house_delivery_successes else 0.0,
            "avg_construction_site_waiting_for_material_ticks": float(
                mean(construction_site_waiting_for_material_ticks)
            ) if construction_site_waiting_for_material_ticks else 0.0,
            "avg_construction_site_waiting_for_builder_ticks": float(
                mean(construction_site_waiting_for_builder_ticks)
            ) if construction_site_waiting_for_builder_ticks else 0.0,
            "avg_construction_site_waiting_total_ticks": float(
                mean(construction_site_waiting_total_ticks)
            ) if construction_site_waiting_total_ticks else 0.0,
            "avg_construction_site_progress_active_ticks": float(
                mean(construction_site_progress_active_ticks)
            ) if construction_site_progress_active_ticks else 0.0,
            "avg_construction_site_starved_cycles": float(
                mean(construction_site_starved_cycles)
            ) if construction_site_starved_cycles else 0.0,
            "avg_storage_waiting_for_material_ticks": float(
                mean(storage_waiting_for_material_ticks)
            ) if storage_waiting_for_material_ticks else 0.0,
            "avg_house_waiting_for_material_ticks": float(
                mean(house_waiting_for_material_ticks)
            ) if house_waiting_for_material_ticks else 0.0,
            "avg_storage_waiting_for_builder_ticks": float(
                mean(storage_waiting_for_builder_ticks)
            ) if storage_waiting_for_builder_ticks else 0.0,
            "avg_house_waiting_for_builder_ticks": float(
                mean(house_waiting_for_builder_ticks)
            ) if house_waiting_for_builder_ticks else 0.0,
            "avg_construction_site_lifetime_ticks_avg": float(
                mean(construction_site_lifetime_ticks_avg)
            ) if construction_site_lifetime_ticks_avg else 0.0,
            "avg_construction_site_progress_before_abandon_avg": float(
                mean(construction_site_progress_before_abandon_avg)
            ) if construction_site_progress_before_abandon_avg else 0.0,
            "avg_construction_site_material_units_delivered_avg": float(
                mean(construction_site_material_units_delivered_avg)
            ) if construction_site_material_units_delivered_avg else 0.0,
            "avg_construction_site_material_units_missing_avg": float(
                mean(construction_site_material_units_missing_avg)
            ) if construction_site_material_units_missing_avg else 0.0,
            "avg_construction_site_material_units_required_total": float(
                mean(construction_site_material_units_required_total)
            ) if construction_site_material_units_required_total else 0.0,
            "avg_construction_site_material_units_delivered_total": float(
                mean(construction_site_material_units_delivered_total)
            ) if construction_site_material_units_delivered_total else 0.0,
            "avg_construction_site_material_units_remaining": float(
                mean(construction_site_material_units_remaining)
            ) if construction_site_material_units_remaining else 0.0,
            "avg_construction_site_required_work_ticks_total": float(
                mean(construction_site_required_work_ticks_total)
            ) if construction_site_required_work_ticks_total else 0.0,
            "avg_construction_site_completed_work_ticks_total": float(
                mean(construction_site_completed_work_ticks_total)
            ) if construction_site_completed_work_ticks_total else 0.0,
            "avg_construction_site_remaining_work_ticks": float(
                mean(construction_site_remaining_work_ticks)
            ) if construction_site_remaining_work_ticks else 0.0,
            "avg_construction_build_state_planned_count": float(
                mean(construction_build_state_planned_count)
            ) if construction_build_state_planned_count else 0.0,
            "avg_construction_build_state_supplying_count": float(
                mean(construction_build_state_supplying_count)
            ) if construction_build_state_supplying_count else 0.0,
            "avg_construction_build_state_buildable_count": float(
                mean(construction_build_state_buildable_count)
            ) if construction_build_state_buildable_count else 0.0,
            "avg_construction_build_state_in_progress_count": float(
                mean(construction_build_state_in_progress_count)
            ) if construction_build_state_in_progress_count else 0.0,
            "avg_construction_build_state_paused_count": float(
                mean(construction_build_state_paused_count)
            ) if construction_build_state_paused_count else 0.0,
            "avg_construction_build_state_completed_count": float(
                mean(construction_build_state_completed_count)
            ) if construction_build_state_completed_count else 0.0,
            "avg_construction_near_complete_sites_count": float(
                mean(construction_near_complete_sites_count)
            ) if construction_near_complete_sites_count else 0.0,
            "avg_builder_assigned_site_count": float(mean(builder_assigned_site_count)) if builder_assigned_site_count else 0.0,
            "avg_builder_site_arrival_count": float(mean(builder_site_arrival_count)) if builder_site_arrival_count else 0.0,
            "avg_builder_left_site_count": float(mean(builder_left_site_count)) if builder_left_site_count else 0.0,
            "avg_builder_left_site_before_completion_count": float(
                mean(builder_left_site_before_completion_count)
            ) if builder_left_site_before_completion_count else 0.0,
            "avg_builder_waiting_on_site_ticks_total": float(
                mean(builder_waiting_on_site_ticks_total)
            ) if builder_waiting_on_site_ticks_total else 0.0,
            "avg_builder_on_site_ticks_total": float(mean(builder_on_site_ticks_total)) if builder_on_site_ticks_total else 0.0,
            "avg_builder_work_tick_applied_count": float(
                mean(builder_work_tick_applied_count)
            ) if builder_work_tick_applied_count else 0.0,
            "avg_builder_survival_override_during_construction_count": float(
                mean(builder_survival_override_during_construction_count)
            ) if builder_survival_override_during_construction_count else 0.0,
            "avg_builder_redirected_to_storage_during_construction_count": float(
                mean(builder_redirected_to_storage_during_construction_count)
            ) if builder_redirected_to_storage_during_construction_count else 0.0,
            "avg_builder_commitment_created_count": float(
                mean(builder_commitment_created_count)
            ) if builder_commitment_created_count else 0.0,
            "avg_builder_commitment_pause_count": float(
                mean(builder_commitment_pause_count)
            ) if builder_commitment_pause_count else 0.0,
            "avg_builder_commitment_resume_count": float(
                mean(builder_commitment_resume_count)
            ) if builder_commitment_resume_count else 0.0,
            "avg_builder_commitment_completed_count": float(
                mean(builder_commitment_completed_count)
            ) if builder_commitment_completed_count else 0.0,
            "avg_builder_commitment_abandoned_count": float(
                mean(builder_commitment_abandoned_count)
            ) if builder_commitment_abandoned_count else 0.0,
            "avg_builder_returned_to_same_site_count": float(
                mean(builder_returned_to_same_site_count)
            ) if builder_returned_to_same_site_count else 0.0,
            "avg_builder_commitment_duration_avg": float(
                mean(builder_commitment_duration_avg)
            ) if builder_commitment_duration_avg else 0.0,
            "avg_builder_commitment_resume_delay_avg": float(
                mean(builder_commitment_resume_delay_avg)
            ) if builder_commitment_resume_delay_avg else 0.0,
            "avg_construction_site_buildable_ticks_total": float(
                mean(construction_site_buildable_ticks_total)
            ) if construction_site_buildable_ticks_total else 0.0,
            "avg_construction_site_idle_buildable_ticks_total": float(
                mean(construction_site_idle_buildable_ticks_total)
            ) if construction_site_idle_buildable_ticks_total else 0.0,
            "avg_construction_site_buildable_but_idle_ticks_total": float(
                mean(construction_site_buildable_but_idle_ticks_total)
            ) if construction_site_buildable_but_idle_ticks_total else 0.0,
            "avg_construction_site_waiting_materials_ticks_total": float(
                mean(construction_site_waiting_materials_ticks_total)
            ) if construction_site_waiting_materials_ticks_total else 0.0,
            "avg_construction_site_in_progress_ticks_total": float(
                mean(construction_site_in_progress_ticks_total)
            ) if construction_site_in_progress_ticks_total else 0.0,
            "avg_construction_site_distinct_builders_avg": float(
                mean(construction_site_distinct_builders_avg)
            ) if construction_site_distinct_builders_avg else 0.0,
            "avg_construction_site_work_ticks_per_builder_avg": float(
                mean(construction_site_work_ticks_per_builder_avg)
            ) if construction_site_work_ticks_per_builder_avg else 0.0,
            "avg_construction_site_delivery_to_work_gap_avg": float(
                mean(construction_site_delivery_to_work_gap_avg)
            ) if construction_site_delivery_to_work_gap_avg else 0.0,
            "avg_construction_site_active_age_ticks_avg": float(
                mean(construction_site_active_age_ticks_avg)
            ) if construction_site_active_age_ticks_avg else 0.0,
            "avg_construction_site_first_builder_arrival_delay_avg": float(
                mean(construction_site_first_builder_arrival_delay_avg)
            ) if construction_site_first_builder_arrival_delay_avg else 0.0,
            "avg_construction_site_material_ready_to_first_work_delay_avg": float(
                mean(construction_site_material_ready_to_first_work_delay_avg)
            ) if construction_site_material_ready_to_first_work_delay_avg else 0.0,
            "avg_construction_site_completion_time_avg": float(
                mean(construction_site_completion_time_avg)
            ) if construction_site_completion_time_avg else 0.0,
            "avg_construction_time_first_delivery_to_completion_avg": float(
                mean(construction_time_first_delivery_to_completion_avg)
            ) if construction_time_first_delivery_to_completion_avg else 0.0,
            "avg_construction_time_first_progress_to_completion_avg": float(
                mean(construction_time_first_progress_to_completion_avg)
            ) if construction_time_first_progress_to_completion_avg else 0.0,
            "avg_construction_time_first_work_to_completion_avg": float(
                mean(construction_time_first_work_to_completion_avg)
            ) if construction_time_first_work_to_completion_avg else 0.0,
            "avg_construction_completed_after_first_delivery_count": float(
                mean(construction_completed_after_first_delivery_count)
            ) if construction_completed_after_first_delivery_count else 0.0,
            "avg_construction_completed_after_started_progress_count": float(
                mean(construction_completed_after_started_progress_count)
            ) if construction_completed_after_started_progress_count else 0.0,
            "avg_construction_completed_after_first_work_count": float(
                mean(construction_completed_after_first_work_count)
            ) if construction_completed_after_first_work_count else 0.0,
            "avg_house_completion_time_avg": float(mean(house_completion_time_avg)) if house_completion_time_avg else 0.0,
            "avg_storage_completion_time_avg": float(mean(storage_completion_time_avg)) if storage_completion_time_avg else 0.0,
        },
    }
