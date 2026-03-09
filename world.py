from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Set, Tuple

from config import (
    WIDTH,
    HEIGHT,
    NUM_AGENTS,
    NUM_FOOD,
    NUM_WOOD,
    NUM_STONE,
    FOOD_RESPAWN_PER_TICK,
    WOOD_RESPAWN_PER_TICK,
    STONE_RESPAWN_PER_TICK,
    MAX_FOOD,
    MAX_WOOD,
    MAX_STONE,
    FOOD_EAT_GAIN,
    MAX_AGENTS,
    HOUSE_WOOD_COST,
    HOUSE_STONE_COST,
    LLM_ENABLED,
    LLM_TIMEOUT_SECONDS,
)

from agent import Agent, detect_agent_innovation_opportunity, validate_proto_asset_proposal
from brain import FoodBrain
from worldgen.generator import generate_world
import systems.building_system as building_system
import systems.village_system as village_system
import systems.farming_system as farming_system
import systems.road_system as road_system
import systems.role_system as role_system
import systems.village_ai_system as village_ai_system
import systems.observability as observability_system

Coord = Tuple[int, int]

MAX_STRUCTURES = 60
MAX_HOUSES_PER_VILLAGE = 8
MAX_NEW_VILLAGE_SEEDS = 2
MIN_HOUSES_FOR_VILLAGE = 3
MIN_HOUSES_FOR_LEADER = 3
INITIAL_FOUNDER_QUOTA = 8


def _default_world_production_metrics() -> Dict[str, int]:
    return {
        "total_food_gathered": 0,
        "total_wood_gathered": 0,
        "total_stone_gathered": 0,
        "direct_food_gathered": 0,
        "direct_wood_gathered": 0,
        "direct_stone_gathered": 0,
        "wood_from_lumberyards": 0,
        "stone_from_mines": 0,
    }


PROTO_ASSET_REJECTION_REASONS = {
    "invalid_effect_context",
    "impossible_terrain_dependency",
    "excessive_material_cost",
    "unsupported_category_context",
    "duplicate_equivalent_proposal",
    "insufficient_local_basis",
}
PROTO_ASSET_PROTOTYPE_STATUSES = {
    "prototype_pending",
    "prototype_under_construction",
    "prototype_built",
    "prototype_failed",
}
PROTO_ASSET_PROTOTYPE_FAILURE_REASONS = {
    "missing_materials",
    "invalid_placement",
    "abandoned_work",
    "construction_conflict",
    "not_admissible",
    "unsupported_mapping",
}
PROTO_ASSET_PROTOTYPE_SUPPORTED_EFFECTS = {
    "cross_water",
    "reduce_movement_cost",
    "increase_storage_efficiency",
    "improve_delivery_efficiency",
}
PROTO_ASSET_USEFULNESS_STATUSES = {"unknown", "useful", "neutral", "ineffective"}
PROTO_ASSET_USEFULNESS_BASIS = {
    "improved_crossing",
    "reduced_route_cost",
    "improved_storage_access",
    "improved_delivery_support",
    "no_observed_benefit",
    "low_usage",
}
PROTO_ASSET_USEFULNESS_MIN_EVAL_TICKS = 40


def select_proto_asset_for_adoption_attempt(world: "World", agent: Agent) -> Optional[Dict[str, Any]]:
    return world.select_proto_asset_for_adoption_attempt(agent)


def find_proto_asset_placement(world: "World", agent: Agent, proposal: Dict[str, Any]) -> Optional[Coord]:
    return world.find_proto_asset_placement(agent, proposal)


def evaluate_prototype_usefulness(world: "World", prototype: Dict[str, Any]) -> Tuple[str, float, List[str]]:
    return world.evaluate_prototype_usefulness(prototype)


class World:
    def __init__(
        self,
        *,
        width: Optional[int] = None,
        height: Optional[int] = None,
        num_agents: Optional[int] = None,
        seed: Optional[int] = None,
        llm_enabled: Optional[bool] = None,
    ):
        if seed is not None:
            random.seed(int(seed))
        self.world_seed = int(seed) if seed is not None else None
        self.width = int(width if width is not None else WIDTH)
        self.height = int(height if height is not None else HEIGHT)

        self.tick = 0
        self._state_version = 0
        self.llm_interactions = 0
        self.llm_calls_this_tick = 0
        self.max_llm_calls_per_tick = 1
        self.build_policy_interval = 20
        self.llm_enabled = bool(LLM_ENABLED) if llm_enabled is None else bool(llm_enabled)
        self.llm_timeout_seconds = float(LLM_TIMEOUT_SECONDS)
        self.llm_reflection_mode = "provider_with_stub_fallback"
        self.llm_stub_enabled = True
        self.llm_force_local_stub = False
        self._village_uid_counter = 0
        self._event_id_counter = 0
        self._building_id_counter = 0
        self._agent_id_counter = 0
        self.events: List[Dict] = []
        self.max_retained_events = 5000
        self.reflection_stats: Dict[str, Dict] = {
            "reflection_trigger_detected_count": 0,
            "reflection_attempt_count": 0,
            "reflection_executed_count": 0,
            "reflection_success_count": 0,
            "reflection_rejection_count": 0,
            "reflection_fallback_count": 0,
            "reflection_reason_counts": {},
            "reflection_role_counts": {},
            "reflection_executed_reason_counts": {},
            "reflection_executed_role_counts": {},
            "reflection_skip_reason_counts": {},
            "reflection_outcome_reason_counts": {},
            "reflection_rejection_reason_counts": {},
            "reflection_fallback_reason_counts": {},
            "reflection_accepted_source_counts": {},
            "survival_reflection_suppressed_count": 0,
            "survival_biased_reflection_applied_count": 0,
            "llm_calls_per_tick": {},
            "llm_calls_per_agent": {},
            "construction_deliveries_count": 0,
            "blocked_construction_count": 0,
            "proto_asset_proposal_count": 0,
            "proto_asset_proposal_rejection_count": 0,
            "proto_asset_proposal_rejection_reasons": {},
            "proto_asset_proposal_counts_by_reason": {},
            "proto_asset_proposal_counts_by_kind": {},
            "proto_asset_proposal_counts_by_source": {},
            "admissible_proposal_count": 0,
            "rejected_proposal_count": 0,
            "proposal_counts_by_status": {},
            "proposal_counts_by_effect": {},
            "proposal_counts_by_category": {},
            "prototype_attempt_count": 0,
            "prototype_built_count": 0,
            "prototype_failed_count": 0,
            "prototype_counts_by_category": {},
            "prototype_counts_by_effect": {},
            "prototype_failure_reasons": {},
            "prototype_useful_count": 0,
            "prototype_neutral_count": 0,
            "prototype_ineffective_count": 0,
            "prototype_usefulness_by_effect": {},
            "prototype_usefulness_by_category": {},
        }

        self.tiles: List[List[str]] = self._generate_tiles()

        self.food: Set[Coord] = set()
        self.wood: Set[Coord] = set()
        self.stone: Set[Coord] = set()

        self.farms: Set[Coord] = set()
        self.farm_plots: Dict[Coord, Dict] = {}

        self.structures: Set[Coord] = set()
        self.storage_buildings: Set[Coord] = set()
        self.buildings: Dict[str, Dict] = {}
        self.building_occupancy: Dict[Coord, str] = {}
        self.roads: Set[Coord] = set()
        self.transport_tiles: Dict[Coord, str] = {}
        self.road_usage: Dict[Coord, int] = {}
        self.infrastructure_state: Dict[str, Dict] = {
            "systems": {
                system: {"enabled": True}
                for system in sorted(building_system.INFRASTRUCTURE_SYSTEMS)
            },
            "transport": {
                "road_tiles": 0,
                "network_types": ["path", "road", "logistics_corridor", "bridge", "tunnel"],
            },
            "logistics": {
                "network_types": ["storage_link", "haul_route"],
            },
            "water": {"network_types": ["well_network"]},
            "energy": {"network_types": ["power_line"]},
            "communication": {"network_types": ["messenger_route"]},
            "environment": {"network_types": ["drainage"]},
        }

        self.villages: List[Dict] = []
        self.agents: List[Agent] = []
        self.proto_asset_proposals: List[Dict] = []
        self.proto_asset_prototypes: List[Dict] = []
        self.production_metrics: Dict[str, int] = _default_world_production_metrics()

        self.MAX_STRUCTURES = MAX_STRUCTURES
        self.MAX_HOUSES_PER_VILLAGE = MAX_HOUSES_PER_VILLAGE
        self.MAX_NEW_VILLAGE_SEEDS = MAX_NEW_VILLAGE_SEEDS
        self.MIN_HOUSES_FOR_VILLAGE = MIN_HOUSES_FOR_VILLAGE
        self.MIN_HOUSES_FOR_LEADER = MIN_HOUSES_FOR_LEADER
        self.INITIAL_FOUNDER_QUOTA = INITIAL_FOUNDER_QUOTA
        self.founders_assigned = 0
        self.founding_hub: Optional[Coord] = None

        self.MAX_FOOD = MAX_FOOD
        self.MAX_WOOD = MAX_WOOD
        self.MAX_STONE = MAX_STONE

        self._spawn_initial_food(NUM_FOOD)
        self._spawn_initial_wood(NUM_WOOD)
        self._spawn_initial_stone(NUM_STONE)

        boot_agents = int(NUM_AGENTS if num_agents is None else num_agents)
        if boot_agents > 0:
            brain = FoodBrain()
            for _ in range(boot_agents):
                pos = self.find_random_free()
                if pos:
                    x, y = pos
                    self.add_agent(Agent(x, y, brain, False, None))

        self.detect_villages()
        self.update_village_ai()
        self.assign_village_roles()
        self.sync_infrastructure_state()
        self.metrics_collector = observability_system.SimulationMetricsCollector(snapshot_interval=5, history_size=240)
        self.metrics_collector.collect(self)

    def record_llm_interaction(self) -> None:
        self.llm_interactions += 1

    def record_reflection_trigger(self, reason: str) -> None:
        stats = self.reflection_stats
        stats["reflection_trigger_detected_count"] = int(
            stats.get("reflection_trigger_detected_count", 0)
        ) + 1
        reasons = stats.setdefault("reflection_reason_counts", {})
        reasons[str(reason)] = int(reasons.get(str(reason), 0)) + 1

    def record_reflection_attempt(self, agent: Agent, reason: str) -> None:
        stats = self.reflection_stats
        stats["reflection_attempt_count"] = int(stats.get("reflection_attempt_count", 0)) + 1
        roles = stats.setdefault("reflection_role_counts", {})
        role = str(getattr(agent, "role", "npc"))
        roles[role] = int(roles.get(role, 0)) + 1
        per_tick = stats.setdefault("llm_calls_per_tick", {})
        per_tick[int(self.tick)] = int(per_tick.get(int(self.tick), 0)) + 1
        per_agent = stats.setdefault("llm_calls_per_agent", {})
        aid = str(getattr(agent, "agent_id", ""))
        per_agent[aid] = int(per_agent.get(aid, 0)) + 1

    def record_reflection_executed(self, agent: Agent, reason: str) -> None:
        stats = self.reflection_stats
        stats["reflection_executed_count"] = int(stats.get("reflection_executed_count", 0)) + 1
        reasons = stats.setdefault("reflection_executed_reason_counts", {})
        reasons[str(reason)] = int(reasons.get(str(reason), 0)) + 1
        roles = stats.setdefault("reflection_executed_role_counts", {})
        role = str(getattr(agent, "role", "npc"))
        roles[role] = int(roles.get(role, 0)) + 1

    def record_reflection_skip(self, reason: str) -> None:
        stats = self.reflection_stats
        skips = stats.setdefault("reflection_skip_reason_counts", {})
        skips[str(reason)] = int(skips.get(str(reason), 0)) + 1

    def record_survival_reflection_suppressed(self) -> None:
        stats = self.reflection_stats
        stats["survival_reflection_suppressed_count"] = int(
            stats.get("survival_reflection_suppressed_count", 0)
        ) + 1

    def record_survival_biased_reflection_applied(self) -> None:
        stats = self.reflection_stats
        stats["survival_biased_reflection_applied_count"] = int(
            stats.get("survival_biased_reflection_applied_count", 0)
        ) + 1

    def record_reflection_outcome(
        self,
        outcome: str,
        *,
        reason: str = "",
        source: str = "",
    ) -> None:
        stats = self.reflection_stats
        key = str(outcome)
        reason_key = str(reason or "").strip()
        source_key = str(source or "").strip()
        if reason_key:
            reasons = stats.setdefault("reflection_outcome_reason_counts", {})
            reasons[reason_key] = int(reasons.get(reason_key, 0)) + 1
        if key == "accepted":
            stats["reflection_success_count"] = int(stats.get("reflection_success_count", 0)) + 1
            if source_key:
                accepted_sources = stats.setdefault("reflection_accepted_source_counts", {})
                accepted_sources[source_key] = int(accepted_sources.get(source_key, 0)) + 1
        elif key == "rejected":
            stats["reflection_rejection_count"] = int(stats.get("reflection_rejection_count", 0)) + 1
            if reason_key:
                rejected_reasons = stats.setdefault("reflection_rejection_reason_counts", {})
                rejected_reasons[reason_key] = int(rejected_reasons.get(reason_key, 0)) + 1
        elif key == "fallback":
            stats["reflection_fallback_count"] = int(stats.get("reflection_fallback_count", 0)) + 1
            if reason_key:
                fallback_reasons = stats.setdefault("reflection_fallback_reason_counts", {})
                fallback_reasons[reason_key] = int(fallback_reasons.get(reason_key, 0)) + 1

    def record_proto_asset_proposal_rejected(self, reason: str) -> None:
        stats = self.reflection_stats
        stats["proto_asset_proposal_rejection_count"] = int(stats.get("proto_asset_proposal_rejection_count", 0)) + 1
        reasons = stats.setdefault("proto_asset_proposal_rejection_reasons", {})
        key = str(reason or "invalid_schema").strip() or "invalid_schema"
        reasons[key] = int(reasons.get(key, 0)) + 1

    def _proposal_equivalence_key(self, proposal: Dict[str, Any]) -> str:
        effects = sorted(str(e).strip().lower() for e in list(proposal.get("intended_effects", []))[:4])
        materials = proposal.get("required_materials", {})
        if not isinstance(materials, dict):
            materials = {}
        material_sig = ",".join(f"{k}:{int(v)}" for k, v in sorted((str(k).strip().lower(), int(v)) for k, v in materials.items()))
        hint = proposal.get("footprint_hint", {})
        if not isinstance(hint, dict):
            hint = {}
        width = int(hint.get("width", 1))
        height = int(hint.get("height", 1))
        placement = str(hint.get("placement", "")).strip().lower()
        return "|".join(
            [
                str(proposal.get("reason", "")).strip().lower(),
                str(proposal.get("category", "")).strip().lower(),
                ",".join(effects),
                material_sig,
                f"{width}x{height}@{placement}",
            ]
        )

    def _nearby_terrain_counts(self, agent: Optional[Agent], radius: int = 6) -> Dict[str, int]:
        if agent is None:
            return {"water": 0, "mountain": 0, "forest": 0}
        ax, ay = int(getattr(agent, "x", 0)), int(getattr(agent, "y", 0))
        counts = {"water": 0, "mountain": 0, "forest": 0}
        for y in range(max(0, ay - radius), min(self.height, ay + radius + 1)):
            for x in range(max(0, ax - radius), min(self.width, ax + radius + 1)):
                if abs(ax - x) + abs(ay - y) > radius:
                    continue
                t = str(self.tiles[y][x]) if 0 <= y < self.height and 0 <= x < self.width else "G"
                if t == "W":
                    counts["water"] += 1
                elif t == "M":
                    counts["mountain"] += 1
                elif t == "F":
                    counts["forest"] += 1
        return counts

    def _prototype_supported_effect(self, proposal: Dict[str, Any]) -> str:
        category = str(proposal.get("category", "")).strip().lower()
        effects = [str(e).strip().lower() for e in list(proposal.get("intended_effects", []))]
        if category == "transport":
            if "cross_water" in effects:
                return "cross_water"
            if "reduce_movement_cost" in effects:
                return "reduce_movement_cost"
        if category in {"storage", "logistics"} and "increase_storage_efficiency" in effects:
            return "increase_storage_efficiency"
        if category == "logistics" and "improve_delivery_efficiency" in effects:
            return "improve_delivery_efficiency"
        return ""

    def _proposal_by_id(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        pid = str(proposal_id)
        for proposal in self.proto_asset_proposals:
            if isinstance(proposal, dict) and str(proposal.get("proposal_id", "")) == pid:
                return proposal
        return None

    def _active_prototype_for_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        pid = str(proposal_id)
        for rec in self.proto_asset_prototypes:
            if not isinstance(rec, dict):
                continue
            if str(rec.get("proposal_id", "")) != pid:
                continue
            status = str(rec.get("status", ""))
            if status in {"prototype_pending", "prototype_under_construction", "prototype_built"}:
                return rec
        return None

    def _active_prototype_for_agent(self, agent: Agent) -> Optional[Dict[str, Any]]:
        aid = str(getattr(agent, "agent_id", ""))
        if not aid:
            return None
        for rec in self.proto_asset_prototypes:
            if not isinstance(rec, dict):
                continue
            if str(rec.get("adopting_agent_id", "")) != aid:
                continue
            status = str(rec.get("status", ""))
            if status in {"prototype_pending", "prototype_under_construction"}:
                return rec
        return None

    def _is_prototype_site_valid(self, location: Any) -> bool:
        if not isinstance(location, dict):
            return False
        x = int(location.get("x", -1))
        y = int(location.get("y", -1))
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return False
        if not self.is_walkable(x, y):
            return False
        if self.is_tile_blocked_by_building(x, y):
            return False
        return True

    def _record_prototype_attempt(self, proposal: Dict[str, Any]) -> None:
        stats = self.reflection_stats
        stats["prototype_attempt_count"] = int(stats.get("prototype_attempt_count", 0)) + 1
        category = str(proposal.get("category", ""))
        by_category = stats.setdefault("prototype_counts_by_category", {})
        by_category[category] = int(by_category.get(category, 0)) + 1
        effect = self._prototype_supported_effect(proposal)
        by_effect = stats.setdefault("prototype_counts_by_effect", {})
        by_effect[effect or "unsupported"] = int(by_effect.get(effect or "unsupported", 0)) + 1

    def _record_proposal_status_transition(self, status: str) -> None:
        key = str(status).strip().lower()
        if not key:
            return
        by_status = self.reflection_stats.setdefault("proposal_counts_by_status", {})
        by_status[key] = int(by_status.get(key, 0)) + 1

    def _record_prototype_outcome(self, outcome: str, *, reason: str = "") -> None:
        stats = self.reflection_stats
        key = str(outcome).strip().lower()
        if key == "built":
            stats["prototype_built_count"] = int(stats.get("prototype_built_count", 0)) + 1
        elif key == "failed":
            stats["prototype_failed_count"] = int(stats.get("prototype_failed_count", 0)) + 1
            r = str(reason or "abandoned_work").strip().lower()
            reasons = stats.setdefault("prototype_failure_reasons", {})
            reasons[r] = int(reasons.get(r, 0)) + 1

    def _record_prototype_usefulness_outcome(self, instance: Dict[str, Any], status: str) -> None:
        key = str(status).strip().lower()
        if key not in {"useful", "neutral", "ineffective"}:
            return
        stats = self.reflection_stats
        if key == "useful":
            stats["prototype_useful_count"] = int(stats.get("prototype_useful_count", 0)) + 1
        elif key == "neutral":
            stats["prototype_neutral_count"] = int(stats.get("prototype_neutral_count", 0)) + 1
        else:
            stats["prototype_ineffective_count"] = int(stats.get("prototype_ineffective_count", 0)) + 1
        by_effect = stats.setdefault("prototype_usefulness_by_effect", {})
        effect = str(instance.get("effect", "")).strip().lower()
        effect_key = f"{effect}:{key}" if effect else f"unknown:{key}"
        by_effect[effect_key] = int(by_effect.get(effect_key, 0)) + 1
        by_category = stats.setdefault("prototype_usefulness_by_category", {})
        category = str(instance.get("category", "")).strip().lower()
        category_key = f"{category}:{key}" if category else f"unknown:{key}"
        by_category[category_key] = int(by_category.get(category_key, 0)) + 1

    def _prototype_local_snapshot(self, instance: Dict[str, Any]) -> Dict[str, int]:
        location = instance.get("location", {})
        if not isinstance(location, dict):
            return {"road_usage": 0, "nearby_agents": 0, "storage_total": 0, "construction_outstanding": 0}
        px = int(location.get("x", 0))
        py = int(location.get("y", 0))
        radius = 3
        road_usage = 0
        for y in range(max(0, py - radius), min(self.height, py + radius + 1)):
            for x in range(max(0, px - radius), min(self.width, px + radius + 1)):
                if abs(px - x) + abs(py - y) > radius:
                    continue
                road_usage += int(self.road_usage.get((x, y), 0))
        nearby_agents = sum(
            1
            for a in self.agents
            if getattr(a, "alive", False)
            and abs(int(getattr(a, "x", -9999)) - px) + abs(int(getattr(a, "y", -9999)) - py) <= 2
        )
        village_id = instance.get("village_id")
        storage_total = 0
        construction_outstanding = 0
        for b in self.buildings.values():
            if not isinstance(b, dict):
                continue
            if village_id is not None and b.get("village_id") != village_id:
                continue
            bx = int(b.get("x", 0))
            by = int(b.get("y", 0))
            if abs(px - bx) + abs(py - by) > 6:
                continue
            if str(b.get("type", "")) == "storage":
                storage = b.get("storage", {})
                if isinstance(storage, dict):
                    storage_total += int(storage.get("food", 0)) + int(storage.get("wood", 0)) + int(storage.get("stone", 0))
            if str(b.get("operational_state", "")) == "under_construction":
                needs = building_system.get_outstanding_construction_needs(b)
                if isinstance(needs, dict):
                    construction_outstanding += int(needs.get("wood", 0)) + int(needs.get("stone", 0)) + int(needs.get("food", 0))
        return {
            "road_usage": int(road_usage),
            "nearby_agents": int(nearby_agents),
            "storage_total": int(storage_total),
            "construction_outstanding": int(construction_outstanding),
        }

    def _update_built_prototype_observations(self, instance: Dict[str, Any]) -> None:
        if str(instance.get("status", "")) != "prototype_built":
            return
        if str(instance.get("usefulness_status", "unknown")) != "unknown":
            return
        snapshot = self._prototype_local_snapshot(instance)
        instance["observation_road_usage_peak"] = max(
            int(instance.get("observation_road_usage_peak", snapshot["road_usage"])),
            int(snapshot["road_usage"]),
        )
        instance["observation_nearby_agent_peak"] = max(
            int(instance.get("observation_nearby_agent_peak", snapshot["nearby_agents"])),
            int(snapshot["nearby_agents"]),
        )
        last_storage_total = int(instance.get("observation_last_storage_total", snapshot["storage_total"]))
        instance["observation_storage_activity"] = int(instance.get("observation_storage_activity", 0)) + abs(
            int(snapshot["storage_total"]) - last_storage_total
        )
        instance["observation_last_storage_total"] = int(snapshot["storage_total"])
        base_outstanding = int(instance.get("observation_baseline_construction_outstanding", snapshot["construction_outstanding"]))
        current_outstanding = int(snapshot["construction_outstanding"])
        improvement = max(0, base_outstanding - current_outstanding)
        instance["observation_construction_relief_peak"] = max(
            int(instance.get("observation_construction_relief_peak", 0)),
            int(improvement),
        )
        if int(snapshot["nearby_agents"]) > 0:
            instance["observation_usage_ticks"] = int(instance.get("observation_usage_ticks", 0)) + 1

    def _mark_prototype_usefulness(self, instance: Dict[str, Any], status: str, score: float, basis: List[str]) -> None:
        cleaned_status = str(status).strip().lower()
        if cleaned_status not in PROTO_ASSET_USEFULNESS_STATUSES:
            cleaned_status = "neutral"
        cleaned_basis = [str(b).strip().lower() for b in (basis or []) if str(b).strip().lower() in PROTO_ASSET_USEFULNESS_BASIS]
        if not cleaned_basis:
            cleaned_basis = ["no_observed_benefit"]
        instance["usefulness_status"] = cleaned_status
        instance["usefulness_score"] = max(0.0, min(1.0, float(score)))
        instance["evaluation_tick"] = int(self.tick)
        instance["evaluation_basis"] = cleaned_basis[:3]
        pid = str(instance.get("proposal_id", ""))
        proposal = self._proposal_by_id(pid)
        if isinstance(proposal, dict):
            proposal["prototype_usefulness_status"] = cleaned_status
            proposal["prototype_usefulness_score"] = float(instance["usefulness_score"])
            proposal["prototype_evaluation_tick"] = int(self.tick)
            proposal["prototype_evaluation_basis"] = list(instance["evaluation_basis"])
        self._record_prototype_usefulness_outcome(instance, cleaned_status)

    def evaluate_prototype_usefulness(self, prototype: Dict[str, Any]) -> Tuple[str, float, List[str]]:
        if not isinstance(prototype, dict):
            return ("ineffective", 0.0, ["no_observed_benefit"])
        if str(prototype.get("status", "")) != "prototype_built":
            return ("neutral", 0.0, ["low_usage"])
        built_tick = int(prototype.get("prototype_completed_tick", prototype.get("tick_created", self.tick)))
        if int(self.tick) - built_tick < PROTO_ASSET_USEFULNESS_MIN_EVAL_TICKS:
            return ("unknown", 0.0, [])
        effect = str(prototype.get("effect", "")).strip().lower()
        usage_ticks = int(prototype.get("observation_usage_ticks", 0))
        road_peak = int(prototype.get("observation_road_usage_peak", 0))
        road_base = int(prototype.get("observation_baseline_road_usage", 0))
        storage_activity = int(prototype.get("observation_storage_activity", 0))
        construction_relief = int(prototype.get("observation_construction_relief_peak", 0))

        score = 0.0
        basis: List[str] = []
        if effect == "cross_water":
            if usage_ticks >= 6:
                score += 0.45
                basis.append("improved_crossing")
            if (road_peak - road_base) >= 4:
                score += 0.30
                if "improved_crossing" not in basis:
                    basis.append("improved_crossing")
        elif effect == "reduce_movement_cost":
            if (road_peak - road_base) >= 5:
                score += 0.50
                basis.append("reduced_route_cost")
            if usage_ticks >= 8:
                score += 0.20
        elif effect == "increase_storage_efficiency":
            if storage_activity >= 8:
                score += 0.50
                basis.append("improved_storage_access")
            if usage_ticks >= 5:
                score += 0.15
        elif effect == "improve_delivery_efficiency":
            if construction_relief >= 2:
                score += 0.45
                basis.append("improved_delivery_support")
            if storage_activity >= 6:
                score += 0.20
        else:
            if usage_ticks >= 8:
                score += 0.25

        if usage_ticks <= 1:
            basis.append("low_usage")
        if score <= 0.05:
            basis.append("no_observed_benefit")

        score = max(0.0, min(1.0, score))
        if score >= 0.55:
            status = "useful"
        elif score >= 0.25:
            status = "neutral"
        else:
            status = "ineffective"
        seen: List[str] = []
        for b in basis:
            if b in PROTO_ASSET_USEFULNESS_BASIS and b not in seen:
                seen.append(b)
        if not seen:
            seen = ["no_observed_benefit"]
        return (status, score, seen[:3])

    def select_proto_asset_for_adoption_attempt(self, agent: Agent) -> Optional[Dict[str, Any]]:
        aid = str(getattr(agent, "agent_id", ""))
        village_id = getattr(agent, "village_id", None)
        inventor_by_id = {
            str(getattr(a, "agent_id", "")): a
            for a in self.agents
            if getattr(a, "alive", True)
        }
        candidates: List[Tuple[int, int, int, str, Dict[str, Any]]] = []
        for proposal in self.proto_asset_proposals:
            if not isinstance(proposal, dict):
                continue
            if str(proposal.get("status", "")) != "admissible":
                continue
            effect = self._prototype_supported_effect(proposal)
            if effect not in PROTO_ASSET_PROTOTYPE_SUPPORTED_EFFECTS:
                continue
            pid = str(proposal.get("proposal_id", ""))
            if self._active_prototype_for_proposal(pid) is not None:
                continue
            inventor_id = str(proposal.get("inventor_agent_id", ""))
            inventor = inventor_by_id.get(inventor_id)
            same_inventor = 0 if inventor_id == aid else 1
            same_village = False
            proximity = 9999
            if inventor is not None:
                proximity = abs(int(getattr(agent, "x", 0)) - int(getattr(inventor, "x", 0))) + abs(
                    int(getattr(agent, "y", 0)) - int(getattr(inventor, "y", 0))
                )
                same_village = village_id is not None and getattr(inventor, "village_id", None) == village_id
            if same_inventor != 0 and not same_village:
                continue
            recency = -int(proposal.get("tick_created", 0))
            candidates.append((same_inventor, proximity, recency, pid, proposal))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
        return dict(candidates[0][4])

    def find_proto_asset_placement(self, agent: Agent, proposal: Dict[str, Any]) -> Optional[Coord]:
        effect = self._prototype_supported_effect(proposal)
        if effect not in PROTO_ASSET_PROTOTYPE_SUPPORTED_EFFECTS:
            return None
        ax, ay = int(getattr(agent, "x", 0)), int(getattr(agent, "y", 0))

        def _open_near(px: int, py: int, radius: int = 2) -> Optional[Coord]:
            picks: List[Tuple[int, int, int]] = []
            for y in range(max(0, py - radius), min(self.height, py + radius + 1)):
                for x in range(max(0, px - radius), min(self.width, px + radius + 1)):
                    if abs(px - x) + abs(py - y) > radius:
                        continue
                    if not self.is_walkable(x, y) or self.is_tile_blocked_by_building(x, y):
                        continue
                    d = abs(ax - x) + abs(ay - y)
                    picks.append((d, y, x))
            if not picks:
                return None
            picks.sort(key=lambda t: (t[0], t[1], t[2]))
            return (picks[0][2], picks[0][1])

        if effect == "cross_water":
            water_edges: List[Tuple[int, int, int]] = []
            for y in range(max(1, ay - 8), min(self.height - 1, ay + 9)):
                for x in range(max(1, ax - 8), min(self.width - 1, ax + 9)):
                    if str(self.tiles[y][x]) != "W":
                        continue
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                        if not self.is_walkable(nx, ny) or self.is_tile_blocked_by_building(nx, ny):
                            continue
                        d = abs(ax - nx) + abs(ay - ny)
                        water_edges.append((d, ny, nx))
            if water_edges:
                water_edges.sort(key=lambda t: (t[0], t[1], t[2]))
                return (water_edges[0][2], water_edges[0][1])
            return None

        if effect == "reduce_movement_cost":
            road_tiles = list(self.get_transport_tiles().keys())
            road_tiles.sort(key=lambda p: (abs(ax - p[0]) + abs(ay - p[1]), p[1], p[0]))
            for rx, ry in road_tiles[:40]:
                candidate = _open_near(int(rx), int(ry), radius=2)
                if candidate is not None:
                    return candidate
            return _open_near(ax, ay, radius=4)

        if effect in {"increase_storage_efficiency", "improve_delivery_efficiency"}:
            village_id = getattr(agent, "village_id", None)
            storages = [
                b for b in self.buildings.values()
                if isinstance(b, dict)
                and str(b.get("type", "")) == "storage"
                and (
                    village_id is None
                    or b.get("village_id") == village_id
                )
            ]
            storages.sort(
                key=lambda b: (
                    abs(ax - int(b.get("x", 0))) + abs(ay - int(b.get("y", 0))),
                    str(b.get("building_id", "")),
                )
            )
            for storage in storages[:8]:
                candidate = _open_near(int(storage.get("x", 0)), int(storage.get("y", 0)), radius=2)
                if candidate is not None:
                    return candidate
            return _open_near(ax, ay, radius=4)

        return None

    def get_proto_material_needs_for_agent(self, agent: Agent) -> Dict[str, int]:
        instance = self._active_prototype_for_agent(agent)
        if not isinstance(instance, dict):
            return {"wood": 0, "stone": 0}
        required = instance.get("required_materials", {})
        delivered = instance.get("delivered_materials", {})
        if not isinstance(required, dict):
            required = {}
        if not isinstance(delivered, dict):
            delivered = {}
        needs: Dict[str, int] = {"wood": 0, "stone": 0}
        for resource in ("wood", "stone"):
            needs[resource] = max(0, int(required.get(resource, 0)) - int(delivered.get(resource, 0)))
        return needs

    def has_proto_asset_work_for_agent(self, agent: Agent) -> bool:
        if self._active_prototype_for_agent(agent) is not None:
            return True
        return self.select_proto_asset_for_adoption_attempt(agent) is not None

    def _mark_prototype_failed(self, instance: Dict[str, Any], reason: str) -> None:
        failure = str(reason).strip().lower()
        if failure not in PROTO_ASSET_PROTOTYPE_FAILURE_REASONS:
            failure = "abandoned_work"
        instance["status"] = "prototype_failed"
        instance["prototype_failure_reason"] = failure
        instance["prototype_completed_tick"] = int(self.tick)
        pid = str(instance.get("proposal_id", ""))
        proposal = self._proposal_by_id(pid)
        if isinstance(proposal, dict):
            proposal["status"] = "prototype_failed"
            proposal["prototype_failure_reason"] = failure
            proposal["prototype_completed_tick"] = int(self.tick)
            self._record_proposal_status_transition("prototype_failed")
        self._record_prototype_outcome("failed", reason=failure)

    def _mark_prototype_built(self, instance: Dict[str, Any]) -> None:
        instance["status"] = "prototype_built"
        instance["prototype_completed_tick"] = int(self.tick)
        instance["usefulness_status"] = "unknown"
        instance["usefulness_score"] = 0.0
        instance["evaluation_tick"] = -1
        instance["evaluation_basis"] = []
        baseline = self._prototype_local_snapshot(instance)
        instance["observation_baseline_road_usage"] = int(baseline.get("road_usage", 0))
        instance["observation_road_usage_peak"] = int(baseline.get("road_usage", 0))
        instance["observation_baseline_storage_total"] = int(baseline.get("storage_total", 0))
        instance["observation_last_storage_total"] = int(baseline.get("storage_total", 0))
        instance["observation_storage_activity"] = 0
        instance["observation_baseline_construction_outstanding"] = int(baseline.get("construction_outstanding", 0))
        instance["observation_construction_relief_peak"] = 0
        instance["observation_usage_ticks"] = 0
        instance["observation_nearby_agent_peak"] = int(baseline.get("nearby_agents", 0))
        pid = str(instance.get("proposal_id", ""))
        proposal = self._proposal_by_id(pid)
        if isinstance(proposal, dict):
            proposal["status"] = "prototype_built"
            proposal["prototype_completed_tick"] = int(self.tick)
            proposal["prototype_building_id"] = str(instance.get("instance_id", ""))
            proposal["prototype_usefulness_status"] = "unknown"
            proposal["prototype_usefulness_score"] = 0.0
            self._record_proposal_status_transition("prototype_built")
        self._record_prototype_outcome("built")

    def run_proto_asset_adoption_attempt(self, agent: Agent) -> bool:
        instance = self._active_prototype_for_agent(agent)
        if not isinstance(instance, dict):
            proposal = self.select_proto_asset_for_adoption_attempt(agent)
            if proposal is None:
                return False
            effect = self._prototype_supported_effect(proposal)
            if effect not in PROTO_ASSET_PROTOTYPE_SUPPORTED_EFFECTS:
                return False
            placement = self.find_proto_asset_placement(agent, proposal)
            if placement is None:
                return False
            x, y = placement
            pid = str(proposal.get("proposal_id", ""))
            instance = {
                "instance_id": f"proto-{pid}-{int(self.tick)}",
                "proposal_id": pid,
                "inventor_agent_id": str(proposal.get("inventor_agent_id", "")),
                "adopting_agent_id": str(getattr(agent, "agent_id", "")),
                "village_id": getattr(agent, "village_id", None),
                "category": str(proposal.get("category", "")),
                "effect": effect,
                "location": {"x": int(x), "y": int(y)},
                "required_materials": {
                    "wood": max(0, int((proposal.get("required_materials") or {}).get("wood", 0))),
                    "stone": max(0, int((proposal.get("required_materials") or {}).get("stone", 0))),
                },
                "delivered_materials": {"wood": 0, "stone": 0},
                "construction_progress": 0,
                "construction_required_work": 4 if str(proposal.get("asset_kind", "")) != "building" else 5,
                "status": "prototype_pending",
                "tick_created": int(self.tick),
                "last_progress_tick": int(self.tick),
            }
            self.proto_asset_prototypes.append(instance)
            proposal_ref = self._proposal_by_id(pid)
            if isinstance(proposal_ref, dict):
                proposal_ref["status"] = "prototype_pending"
                proposal_ref["adopting_agent_id"] = str(getattr(agent, "agent_id", ""))
                proposal_ref["prototype_started_tick"] = int(self.tick)
                proposal_ref["prototype_instance_id"] = str(instance.get("instance_id", ""))
                self._record_proposal_status_transition("prototype_pending")
            self._record_prototype_attempt(proposal)

        location = instance.get("location", {})
        if not self._is_prototype_site_valid(location):
            self._mark_prototype_failed(instance, "invalid_placement")
            return False
        px = int(location.get("x", 0))
        py = int(location.get("y", 0))
        distance = abs(int(getattr(agent, "x", 0)) - px) + abs(int(getattr(agent, "y", 0)) - py)
        if distance > 1:
            return False

        pid = str(instance.get("proposal_id", ""))
        proposal_ref = self._proposal_by_id(pid)
        if isinstance(proposal_ref, dict) and str(proposal_ref.get("status", "")) == "admissible":
            proposal_ref["status"] = "prototype_pending"
        if isinstance(proposal_ref, dict):
            proposal_ref["adopting_agent_id"] = str(getattr(agent, "agent_id", ""))
            proposal_ref["prototype_started_tick"] = int(proposal_ref.get("prototype_started_tick", int(self.tick)))
            proposal_ref["prototype_instance_id"] = str(instance.get("instance_id", ""))

        if str(instance.get("status", "")) == "prototype_pending":
            instance["status"] = "prototype_under_construction"
            if isinstance(proposal_ref, dict):
                proposal_ref["status"] = "prototype_under_construction"
                self._record_proposal_status_transition("prototype_under_construction")

        required = instance.get("required_materials", {})
        delivered = instance.get("delivered_materials", {})
        if not isinstance(required, dict):
            required = {"wood": 0, "stone": 0}
            instance["required_materials"] = required
        if not isinstance(delivered, dict):
            delivered = {"wood": 0, "stone": 0}
            instance["delivered_materials"] = delivered

        moved = 0
        for resource in ("wood", "stone"):
            need = max(0, int(required.get(resource, 0)) - int(delivered.get(resource, 0)))
            if need <= 0:
                continue
            have = int(getattr(agent, "inventory", {}).get(resource, 0))
            qty = min(need, have)
            if qty <= 0:
                continue
            agent.inventory[resource] = have - qty
            delivered[resource] = int(delivered.get(resource, 0)) + qty
            moved += qty

        materials_ready = all(
            int(delivered.get(resource, 0)) >= int(required.get(resource, 0))
            for resource in ("wood", "stone")
        )
        if materials_ready:
            required_work = max(1, int(instance.get("construction_required_work", 4)))
            progress = max(0, int(instance.get("construction_progress", 0)))
            instance["construction_progress"] = min(required_work, progress + 1)
            instance["last_progress_tick"] = int(self.tick)
            if int(instance.get("construction_progress", 0)) >= required_work:
                self._mark_prototype_built(instance)
                return True
        elif moved > 0:
            instance["last_progress_tick"] = int(self.tick)
        return moved > 0

    def update_proto_asset_prototypes(self) -> None:
        alive_agents = {str(getattr(a, "agent_id", "")) for a in self.agents if getattr(a, "alive", False)}
        for instance in self.proto_asset_prototypes:
            if not isinstance(instance, dict):
                continue
            status = str(instance.get("status", ""))
            if status == "prototype_built":
                self._update_built_prototype_observations(instance)
                outcome, score, basis = self.evaluate_prototype_usefulness(instance)
                if outcome in {"useful", "neutral", "ineffective"} and str(instance.get("usefulness_status", "unknown")) == "unknown":
                    self._mark_prototype_usefulness(instance, outcome, score, basis)
                    if outcome == "useful":
                        loc = instance.get("location", {})
                        if isinstance(loc, dict):
                            px = int(loc.get("x", 0))
                            py = int(loc.get("y", 0))
                            for a in self.agents:
                                if not getattr(a, "alive", False):
                                    continue
                                if abs(int(getattr(a, "x", -9999)) - px) + abs(int(getattr(a, "y", -9999)) - py) > 3:
                                    continue
                                memory = getattr(a, "episodic_memory", None)
                                if not isinstance(memory, dict):
                                    continue
                                events = memory.get("recent_events")
                                if not isinstance(events, list):
                                    continue
                                events.append(
                                    {
                                        "tick": int(self.tick),
                                        "type": "useful_prototype_seen",
                                        "target_id": str(instance.get("instance_id", "")),
                                        "resource_type": "",
                                        "outcome": "success",
                                        "location": {"x": px, "y": py},
                                        "salience": 0.5,
                                        "novelty": 0.3,
                                        "importance": 0.4,
                                    }
                                )
                                if len(events) > int(memory.get("max_events", 200)):
                                    overflow = len(events) - int(memory.get("max_events", 200))
                                    del events[:overflow]
                continue
            if status not in {"prototype_pending", "prototype_under_construction"}:
                continue
            if str(instance.get("adopting_agent_id", "")) not in alive_agents:
                self._mark_prototype_failed(instance, "abandoned_work")
                continue
            if not self._is_prototype_site_valid(instance.get("location", {})):
                self._mark_prototype_failed(instance, "construction_conflict")
                continue
            stalled_ticks = int(self.tick) - int(instance.get("last_progress_tick", instance.get("tick_created", self.tick)))
            if stalled_ticks > 180:
                required = instance.get("required_materials", {})
                delivered = instance.get("delivered_materials", {})
                if isinstance(required, dict) and isinstance(delivered, dict):
                    materials_ready = all(
                        int(delivered.get(resource, 0)) >= int(required.get(resource, 0))
                        for resource in ("wood", "stone")
                    )
                    self._mark_prototype_failed(instance, "abandoned_work" if materials_ready else "missing_materials")
                else:
                    self._mark_prototype_failed(instance, "abandoned_work")

    def evaluate_proto_asset_admissibility(
        self,
        proposal: Dict[str, Any],
        inventor_agent: Optional[Agent] = None,
    ) -> Tuple[str, str]:
        if not isinstance(proposal, dict):
            return ("rejected", "insufficient_local_basis")

        reason = str(proposal.get("reason", "")).strip().lower()
        effects = [str(e).strip().lower() for e in proposal.get("intended_effects", []) if str(e).strip()]
        category = str(proposal.get("category", "")).strip().lower()
        materials = proposal.get("required_materials", {})
        if not isinstance(materials, dict):
            materials = {}
        hint = proposal.get("footprint_hint", {})
        if not isinstance(hint, dict):
            hint = {}

        local_reason = detect_agent_innovation_opportunity(self, inventor_agent) if inventor_agent is not None else None
        local_signals = getattr(inventor_agent, "subjective_state", {}) if inventor_agent is not None else {}
        local_signals = local_signals.get("local_signals", {}) if isinstance(local_signals, dict) else {}
        needs = local_signals.get("needs", {}) if isinstance(local_signals.get("needs"), dict) else {}
        terrain_counts = self._nearby_terrain_counts(inventor_agent)
        has_local_basis = bool(local_reason) or bool(reason)
        if inventor_agent is None and not has_local_basis:
            return ("rejected", "insufficient_local_basis")

        if sum(max(0, int(v)) for v in materials.values()) > 12:
            return ("rejected", "excessive_material_cost")

        width = int(hint.get("width", 1))
        height = int(hint.get("height", 1))
        placement = str(hint.get("placement", "")).strip().lower()
        if width > 3 or height > 3 or width * height > 6:
            return ("rejected", "impossible_terrain_dependency")
        if placement == "near_water" and terrain_counts.get("water", 0) <= 0:
            return ("rejected", "impossible_terrain_dependency")

        if category == "transport" and not any(e in {"cross_water", "reduce_movement_cost"} for e in effects):
            return ("rejected", "unsupported_category_context")
        if category == "storage" and "increase_storage_efficiency" not in effects:
            return ("rejected", "unsupported_category_context")
        if category == "logistics" and not any(
            e in {"improve_delivery_efficiency", "improve_food_handling", "improve_construction_access"} for e in effects
        ):
            return ("rejected", "unsupported_category_context")

        reason_basis = local_reason or reason
        for effect in effects:
            if effect == "cross_water":
                if reason_basis != "transport_barrier":
                    return ("rejected", "invalid_effect_context")
                if terrain_counts.get("water", 0) <= 0:
                    return ("rejected", "impossible_terrain_dependency")
            elif effect == "reduce_movement_cost":
                if reason_basis not in {"route_inefficiency", "transport_barrier"}:
                    return ("rejected", "invalid_effect_context")
            elif effect == "increase_storage_efficiency":
                if reason_basis != "storage_friction" and not bool(needs.get("need_storage")):
                    return ("rejected", "invalid_effect_context")
            elif effect == "improve_delivery_efficiency":
                if reason_basis not in {"storage_friction", "construction_friction", "food_handling_friction"}:
                    return ("rejected", "invalid_effect_context")
            elif effect == "improve_resource_access":
                if reason_basis != "resource_access_friction":
                    return ("rejected", "invalid_effect_context")
            elif effect == "improve_food_handling":
                if reason_basis != "food_handling_friction":
                    return ("rejected", "invalid_effect_context")
            elif effect == "improve_construction_access":
                if reason_basis != "construction_friction":
                    return ("rejected", "invalid_effect_context")

        return ("admissible", "")

    def register_proto_asset_proposal(self, proposal: Dict[str, Any], *, source: str = "stub") -> bool:
        validated, reason = validate_proto_asset_proposal(proposal if isinstance(proposal, dict) else {})
        if validated is None:
            self.record_proto_asset_proposal_rejected(reason or "invalid_schema")
            return False
        pid = str(validated.get("proposal_id", ""))
        inventor = str(validated.get("inventor_agent_id", ""))
        proposal_reason = str(validated.get("reason", ""))
        tick_created = int(validated.get("tick_created", 0))
        equivalence_key = self._proposal_equivalence_key(validated)
        for existing in self.proto_asset_proposals:
            if not isinstance(existing, dict):
                continue
            if str(existing.get("proposal_id", "")) == pid:
                return False
            if (
                str(existing.get("inventor_agent_id", "")) == inventor
                and str(existing.get("reason", "")) == proposal_reason
                and tick_created - int(existing.get("tick_created", -99999)) < 120
            ):
                # Basic anti-spam guard: same agent/reason cannot flood near-identical proposals.
                return False
            if (
                str(existing.get("equivalence_key", "")) == equivalence_key
                and str(existing.get("status", "")) in {"admissible", "proposed"}
                and tick_created - int(existing.get("tick_created", -99999)) < 400
            ):
                archived = dict(validated)
                archived["status"] = "archived"
                archived["rejection_reason"] = "duplicate_equivalent_proposal"
                archived["equivalence_key"] = equivalence_key
                self.proto_asset_proposals.append(archived)
                self.record_proto_asset_proposal_rejected("duplicate_equivalent_proposal")
                stats = self.reflection_stats
                stats["proto_asset_proposal_count"] = int(stats.get("proto_asset_proposal_count", 0)) + 1
                by_status = stats.setdefault("proposal_counts_by_status", {})
                by_status["archived"] = int(by_status.get("archived", 0)) + 1
                by_reason = stats.setdefault("proto_asset_proposal_counts_by_reason", {})
                by_reason[proposal_reason] = int(by_reason.get(proposal_reason, 0)) + 1
                by_kind = stats.setdefault("proto_asset_proposal_counts_by_kind", {})
                kind = str(validated.get("asset_kind", ""))
                by_kind[kind] = int(by_kind.get(kind, 0)) + 1
                by_source = stats.setdefault("proto_asset_proposal_counts_by_source", {})
                src = str(source or "stub").strip().lower() or "stub"
                by_source[src] = int(by_source.get(src, 0)) + 1
                by_category = stats.setdefault("proposal_counts_by_category", {})
                by_category[str(validated.get("category", ""))] = int(by_category.get(str(validated.get("category", "")), 0)) + 1
                by_effect = stats.setdefault("proposal_counts_by_effect", {})
                for effect in validated.get("intended_effects", []):
                    ekey = str(effect)
                    by_effect[ekey] = int(by_effect.get(ekey, 0)) + 1
                return True

        stored = dict(validated)
        stored["status"] = "proposed"
        stored["equivalence_key"] = equivalence_key
        inventor_agent = next((a for a in self.agents if str(getattr(a, "agent_id", "")) == inventor), None)
        status, rejection_reason = self.evaluate_proto_asset_admissibility(stored, inventor_agent=inventor_agent)
        if status == "admissible":
            stored["status"] = "admissible"
            stored["admissibility_tick"] = int(self.tick)
        else:
            stored["status"] = "rejected"
            stored["rejection_reason"] = rejection_reason if rejection_reason in PROTO_ASSET_REJECTION_REASONS else "insufficient_local_basis"
            stored["admissibility_tick"] = int(self.tick)
            self.record_proto_asset_proposal_rejected(str(stored.get("rejection_reason", "")))

        self.proto_asset_proposals.append(stored)
        if len(self.proto_asset_proposals) > 800:
            overflow = len(self.proto_asset_proposals) - 800
            del self.proto_asset_proposals[:overflow]

        stats = self.reflection_stats
        stats["proto_asset_proposal_count"] = int(stats.get("proto_asset_proposal_count", 0)) + 1
        by_reason = stats.setdefault("proto_asset_proposal_counts_by_reason", {})
        by_reason[proposal_reason] = int(by_reason.get(proposal_reason, 0)) + 1
        kind = str(validated.get("asset_kind", ""))
        by_kind = stats.setdefault("proto_asset_proposal_counts_by_kind", {})
        by_kind[kind] = int(by_kind.get(kind, 0)) + 1
        src = str(source or "stub").strip().lower() or "stub"
        by_source = stats.setdefault("proto_asset_proposal_counts_by_source", {})
        by_source[src] = int(by_source.get(src, 0)) + 1
        by_status = stats.setdefault("proposal_counts_by_status", {})
        final_status = str(stored.get("status", "proposed"))
        by_status[final_status] = int(by_status.get(final_status, 0)) + 1
        if final_status == "admissible":
            stats["admissible_proposal_count"] = int(stats.get("admissible_proposal_count", 0)) + 1
        elif final_status == "rejected":
            stats["rejected_proposal_count"] = int(stats.get("rejected_proposal_count", 0)) + 1
        by_category = stats.setdefault("proposal_counts_by_category", {})
        category = str(validated.get("category", ""))
        by_category[category] = int(by_category.get(category, 0)) + 1
        by_effect = stats.setdefault("proposal_counts_by_effect", {})
        for effect in validated.get("intended_effects", []):
            ekey = str(effect)
            by_effect[ekey] = int(by_effect.get(ekey, 0)) + 1
        return True

    def next_state_version(self) -> int:
        self._state_version += 1
        return self._state_version

    def new_village_uid(self) -> str:
        self._village_uid_counter += 1
        return f"v-{self._village_uid_counter:06d}"

    def _next_event_id(self) -> str:
        self._event_id_counter += 1
        return f"e-{self._event_id_counter:06d}"

    def new_building_id(self) -> str:
        self._building_id_counter += 1
        return f"b-{self._building_id_counter:06d}"

    def resolve_village_uid(self, village_id: Optional[int]) -> Optional[str]:
        village = self.get_village_by_id(village_id)
        if village is None:
            return None
        uid = village.get("village_uid")
        if uid is None:
            return None
        return str(uid)

    def emit_event(self, event_type: str, payload: Dict) -> Dict:
        event = {
            "event_id": self._next_event_id(),
            "tick": int(self.tick),
            "event_type": str(event_type),
            "payload": payload if isinstance(payload, dict) else {},
        }
        self.events.append(event)
        # Bounded in-memory retention to prevent unbounded growth.
        if self.max_retained_events > 0 and len(self.events) > self.max_retained_events:
            overflow = len(self.events) - self.max_retained_events
            del self.events[:overflow]
        return event

    def record_resource_production(
        self,
        resource_type: str,
        amount: int,
        *,
        bonus_amount: int = 0,
        production_source: Optional[str] = None,
    ) -> None:
        qty = int(amount)
        if qty <= 0:
            return
        bonus = max(0, int(bonus_amount))
        metrics = self.production_metrics
        if not isinstance(metrics, dict):
            metrics = _default_world_production_metrics()
            self.production_metrics = metrics

        defaults = _default_world_production_metrics()
        for key, default_value in defaults.items():
            if key not in metrics:
                metrics[key] = default_value
            else:
                metrics[key] = int(metrics.get(key, default_value))

        if resource_type == "food":
            metrics["total_food_gathered"] += qty
            metrics["direct_food_gathered"] += qty
            return

        if resource_type == "wood":
            specialized = min(qty, bonus) if production_source == "lumberyard" else 0
            direct = max(0, qty - specialized)
            metrics["total_wood_gathered"] += qty
            metrics["direct_wood_gathered"] += direct
            if specialized > 0:
                metrics["wood_from_lumberyards"] += specialized
            return

        if resource_type == "stone":
            specialized = min(qty, bonus) if production_source == "mine" else 0
            direct = max(0, qty - specialized)
            metrics["total_stone_gathered"] += qty
            metrics["direct_stone_gathered"] += direct
            if specialized > 0:
                metrics["stone_from_mines"] += specialized

    def get_events_since(self, since_tick: int = -1) -> List[Dict]:
        cutoff = int(since_tick)
        return [e for e in self.events if int(e.get("tick", -1)) > cutoff]

    def set_agent_role(self, agent: Agent, new_role: str, reason: str = "") -> None:
        old_role = getattr(agent, "role", "npc")
        if old_role == new_role:
            agent.role = new_role
            return
        agent.role = new_role
        self.emit_event(
            "role_changed",
            {
                "agent_id": agent.agent_id,
                "from_role": old_role,
                "to_role": new_role,
                "reason": reason,
                "village_uid": self.resolve_village_uid(getattr(agent, "village_id", None)),
            },
        )

    def set_agent_dead(self, agent: Agent, reason: str = "unknown") -> None:
        if not agent.alive:
            return
        agent.alive = False
        self.emit_event(
            "agent_died",
            {
                "agent_id": agent.agent_id,
                "is_player": bool(agent.is_player),
                "reason": reason,
                "village_uid": self.resolve_village_uid(getattr(agent, "village_id", None)),
            },
        )

    def get_village_by_id(self, village_id: Optional[int]) -> Optional[Dict]:
        return village_system.get_village_by_id(self, village_id)

    def count_leaders(self) -> int:
        return village_system.count_leaders(self)

    def get_civilization_stats(self) -> Dict:
        return village_system.get_civilization_stats(self)

    def record_road_step(self, x: int, y: int) -> None:
        road_system.record_agent_step(self, x, y)

    def update_road_infrastructure(self) -> None:
        road_system.update_road_infrastructure(self)
        self.sync_infrastructure_state()

    def sync_infrastructure_state(self) -> None:
        transport_state = self.infrastructure_state.setdefault("transport", {})
        transport_state["road_tiles"] = int(len(self.roads))
        tile_counts: Dict[str, int] = {}
        for t in self.transport_tiles.values():
            tile_counts[t] = int(tile_counts.get(t, 0)) + 1
        transport_state["tile_counts"] = {k: tile_counts[k] for k in sorted(tile_counts.keys())}
        road_meta = building_system.get_infrastructure_metadata("road")
        if isinstance(road_meta, dict):
            transport_state["road_infrastructure_type"] = str(road_meta.get("type", "road"))
            transport_state["network_type"] = str(road_meta.get("network_type", "tile_network"))

    def update_village_ai(self) -> None:
        village_ai_system.update_village_ai(self)

    def assign_village_roles(self) -> None:
        role_system.assign_village_roles(self)

    def _generate_tiles(self) -> List[List[str]]:
        return generate_world(self.width, self.height)

    def is_walkable(self, x: int, y: int) -> bool:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return False
        terrain = str(self.tiles[y][x])
        transport_type = self.get_transport_type(x, y)
        if terrain == "W":
            return transport_type == "bridge"
        if terrain == "X":
            return transport_type == "tunnel"
        return True

    def is_occupied(self, x: int, y: int) -> bool:
        for a in self.agents:
            if a.alive and a.x == x and a.y == y:
                return True
        return False

    def movement_cost(self, x: int, y: int) -> float:
        terrain = str(self.tiles[y][x]) if 0 <= x < self.width and 0 <= y < self.height else "G"
        base_costs = {
            "G": 1.0,
            "F": 1.0,
            "M": 1.2,
            "W": 1.4,
            "X": 1.6,
        }
        base_cost = float(base_costs.get(terrain, 1.0))
        transport_type = self.get_transport_type(x, y)
        if transport_type is None:
            return base_cost
        transport_meta = building_system.get_infrastructure_metadata(transport_type) or {}
        modifier = float(transport_meta.get("movement_modifier", 1.0) or 1.0)
        return max(0.05, base_cost * modifier)

    def get_transport_type(self, x: int, y: int) -> Optional[str]:
        pos = (x, y)
        transport_type = self.transport_tiles.get(pos)
        if transport_type is not None:
            return str(transport_type)
        if pos in self.roads:
            return "road"
        return None

    def set_transport_type(self, x: int, y: int, transport_type: Optional[str]) -> None:
        pos = (x, y)
        if transport_type is None:
            self.transport_tiles.pop(pos, None)
            self.roads.discard(pos)
            return
        t = str(transport_type)
        self.transport_tiles[pos] = t
        if t in {"road", "logistics_corridor", "bridge", "tunnel"}:
            self.roads.add(pos)
        else:
            self.roads.discard(pos)

    def get_transport_tiles(self) -> Dict[Coord, str]:
        tiles: Dict[Coord, str] = {}
        for pos in self.roads:
            tiles[pos] = "road"
        for pos, t in self.transport_tiles.items():
            tiles[pos] = str(t)
        return tiles

    def minimum_step_cost(self) -> float:
        # Lower bound for A* heuristic with current transport hierarchy.
        return 0.35

    def is_tile_blocked_by_building(self, x: int, y: int) -> bool:
        pos = (x, y)
        if pos in self.building_occupancy:
            return True
        if pos in self.structures:
            return True
        if pos in self.storage_buildings:
            return True
        return False

    def get_building_occupied_tiles(self) -> Set[Coord]:
        if self.building_occupancy:
            return set(self.building_occupancy.keys())
        return set(self.structures) | set(self.storage_buildings)

    def add_agent(self, agent: Agent):
        if self.world_seed is not None:
            self._agent_id_counter += 1
            agent.agent_id = f"a-{self._agent_id_counter:06d}"

        if (
            getattr(agent, "brain", None) is not None
            and
            not agent.is_player
            and getattr(agent, "village_id", None) is None
            and not getattr(agent, "founder", False)
            and self.founders_assigned < self.INITIAL_FOUNDER_QUOTA
            and self.tick < 300
            and len(self.structures) < self.MIN_HOUSES_FOR_VILLAGE
        ):
            agent.founder = True
            self.founders_assigned += 1
            if self.founding_hub is None:
                self.founding_hub = (agent.x, agent.y)
            agent.task_target = self.founding_hub
            # Minimal starter kit so founders can reliably place early houses.
            agent.max_inventory = max(int(getattr(agent, "max_inventory", 5)), HOUSE_WOOD_COST + HOUSE_STONE_COST)
            agent.inventory["wood"] = max(agent.inventory.get("wood", 0), HOUSE_WOOD_COST)
            agent.inventory["stone"] = max(agent.inventory.get("stone", 0), HOUSE_STONE_COST)

        self.agents.append(agent)
        self.emit_event(
            "agent_born",
            {
                "agent_id": agent.agent_id,
                "is_player": bool(agent.is_player),
                "player_id": agent.player_id,
                "village_uid": self.resolve_village_uid(getattr(agent, "village_id", None)),
            },
        )

    def find_random_free(self) -> Optional[Coord]:
        for _ in range(2000):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)

            if self.is_walkable(x, y) and not self.is_occupied(x, y):
                return (x, y)

        return None

    def find_free_adjacent(self, x: int, y: int) -> Optional[Coord]:
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        random.shuffle(dirs)

        for dx, dy in dirs:
            nx = x + dx
            ny = y + dy

            if self.is_walkable(nx, ny) and not self.is_occupied(nx, ny):
                return (nx, ny)

        return None

    def _spawn_initial_food(self, n: int):
        added = 0

        # preferisci pianure vicino all'acqua
        for _ in range(n * 4):
            if added >= n:
                break

            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)

            if self.tiles[y][x] != "G":
                continue

            near_water = False
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    nx = x + dx
                    ny = y + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        if self.tiles[ny][nx] == "W":
                            near_water = True
                            break
                if near_water:
                    break

            if near_water and (x, y) not in self.food:
                self.food.add((x, y))
                added += 1

        # fallback per riempire il resto
        while added < n:
            pos = self.find_random_free()
            if pos and pos not in self.food:
                self.food.add(pos)
                added += 1

    def _spawn_initial_wood(self, n: int):
        added = 0
        for _ in range(n):
            for _ in range(120):
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)
                if self.tiles[y][x] == "F" and (x, y) not in self.wood:
                    self.wood.add((x, y))
                    added += 1
                    break

        # fallback leggero se il worldgen ha poche foreste accessibili
        while added < n:
            pos = self.find_random_free()
            if pos and pos not in self.wood:
                x, y = pos
                if self.tiles[y][x] != "W":
                    self.wood.add(pos)
                    added += 1

    def _spawn_initial_stone(self, n: int):
        added = 0
        for _ in range(n):
            for _ in range(120):
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)
                if self.tiles[y][x] == "M" and (x, y) not in self.stone:
                    self.stone.add((x, y))
                    added += 1
                    break

        # fallback leggero se ci sono poche montagne accessibili
        while added < n:
            pos = self.find_random_free()
            if pos and pos not in self.stone:
                x, y = pos
                if self.tiles[y][x] != "W":
                    self.stone.add(pos)
                    added += 1

    def respawn_resources(self):
        if len(self.food) < MAX_FOOD:
            for _ in range(FOOD_RESPAWN_PER_TICK):
                # preferisci ancora pianure libere
                placed = False
                for _ in range(40):
                    x = random.randint(0, self.width - 1)
                    y = random.randint(0, self.height - 1)
                    if self.tiles[y][x] == "G" and (x, y) not in self.food and not self.is_occupied(x, y):
                        self.food.add((x, y))
                        placed = True
                        break

                if not placed:
                    pos = self.find_random_free()
                    if pos:
                        self.food.add(pos)

        if len(self.wood) < MAX_WOOD:
            for _ in range(WOOD_RESPAWN_PER_TICK):
                for _ in range(80):
                    x = random.randint(0, self.width - 1)
                    y = random.randint(0, self.height - 1)
                    if self.tiles[y][x] == "F":
                        self.wood.add((x, y))
                        break

        if len(self.stone) < MAX_STONE:
            for _ in range(STONE_RESPAWN_PER_TICK):
                for _ in range(80):
                    x = random.randint(0, self.width - 1)
                    y = random.randint(0, self.height - 1)
                    if self.tiles[y][x] == "M":
                        self.stone.add((x, y))
                        break

    def autopickup(self, agent: Agent):
        pos = (agent.x, agent.y)
        village = self.get_village_by_id(getattr(agent, "village_id", None))

        if pos in self.food:
            self.food.remove(pos)
            if agent.inventory_space() > 0:
                agent.inventory["food"] = agent.inventory.get("food", 0) + 1
            agent.hunger += FOOD_EAT_GAIN
            if agent.hunger > 100:
                agent.hunger = 100
            building_system.record_village_resource_gather(village, "food", amount=1)
            self.record_resource_production("food", 1)
            self.emit_event(
                "resource_harvested",
                {
                    "agent_id": agent.agent_id,
                    "resource": "food",
                    "amount": 1,
                    "source": "wild_food",
                    "x": agent.x,
                    "y": agent.y,
                    "village_uid": self.resolve_village_uid(getattr(agent, "village_id", None)),
                },
            )

    def gather_resource(self, agent: Agent):
        pos = (agent.x, agent.y)
        village = self.get_village_by_id(getattr(agent, "village_id", None))
        if agent.inventory_space() <= 0:
            return False

        if pos in self.wood:
            self.wood.remove(pos)
            bonus, source = building_system.production_bonus_details_for_resource(self, village, "wood", pos)
            amount = min(1 + bonus, max(0, agent.inventory_space()))
            if amount <= 0:
                return False
            effective_bonus = max(0, min(int(bonus), int(amount) - 1))
            agent.inventory["wood"] = agent.inventory.get("wood", 0) + amount
            building_system.record_village_resource_gather(
                village,
                "wood",
                amount=amount,
                bonus_amount=effective_bonus,
                production_source=source,
            )
            self.record_resource_production("wood", amount, bonus_amount=effective_bonus, production_source=source)
            self.emit_event(
                "resource_harvested",
                {
                    "agent_id": agent.agent_id,
                    "resource": "wood",
                    "amount": amount,
                    "source": "wild",
                    "x": agent.x,
                    "y": agent.y,
                    "village_uid": self.resolve_village_uid(getattr(agent, "village_id", None)),
                },
            )
            return True

        if pos in self.stone:
            self.stone.remove(pos)
            bonus, source = building_system.production_bonus_details_for_resource(self, village, "stone", pos)
            amount = min(1 + bonus, max(0, agent.inventory_space()))
            if amount <= 0:
                return False
            effective_bonus = max(0, min(int(bonus), int(amount) - 1))
            agent.inventory["stone"] = agent.inventory.get("stone", 0) + amount
            building_system.record_village_resource_gather(
                village,
                "stone",
                amount=amount,
                bonus_amount=effective_bonus,
                production_source=source,
            )
            self.record_resource_production("stone", amount, bonus_amount=effective_bonus, production_source=source)
            self.emit_event(
                "resource_harvested",
                {
                    "agent_id": agent.agent_id,
                    "resource": "stone",
                    "amount": amount,
                    "source": "wild",
                    "x": agent.x,
                    "y": agent.y,
                    "village_uid": self.resolve_village_uid(getattr(agent, "village_id", None)),
                },
            )
            return True

        return False

    def building_score(self, x: int, y: int) -> int:
        return building_system.building_score(self, x, y)

    def count_nearby_houses(self, x: int, y: int, radius: int = 5) -> int:
        return building_system.count_nearby_houses(self, x, y, radius)

    def count_nearby_population(self, x: int, y: int, radius: int = 6) -> int:
        return building_system.count_nearby_population(self, x, y, radius)

    def can_build_at(self, x: int, y: int) -> bool:
        return building_system.can_build_at(self, x, y)

    def can_place_building(self, building_type: str, x: int, y: int) -> bool:
        return building_system.can_place_building(self, building_type, (x, y))

    def place_building(
        self,
        building_type: str,
        x: int,
        y: int,
        *,
        village_id: Optional[int] = None,
        village_uid: Optional[str] = None,
        connected_to_road: bool = False,
    ) -> Optional[Dict]:
        return building_system.place_building(
            self,
            building_type,
            (x, y),
            village_id=village_id,
            village_uid=village_uid,
            connected_to_road=connected_to_road,
        )

    def try_build_house(self, agent: Agent):
        return building_system.try_build_house(self, agent)

    def try_build_storage(self, agent: Agent):
        return building_system.try_build_storage(self, agent)

    def try_build_type(
        self,
        agent: Agent,
        building_type: str,
        village_id: Optional[int] = None,
        village_uid: Optional[str] = None,
    ) -> Dict:
        return building_system.try_build_type(
            self,
            agent,
            building_type,
            village_id=village_id,
            village_uid=village_uid,
        )

    def try_build_farm(self, agent: Agent):
        return farming_system.try_build_farm(self, agent)

    def work_farm(self, agent: Agent):
        return farming_system.work_farm(self, agent)

    def haul_harvest(self, agent: Agent):
        return farming_system.haul_harvest(self, agent)

    def detect_villages(self):
        village_system.detect_villages(self)

    def assign_village_leaders(self):
        village_system.assign_village_leaders(self)

    def update_village_politics(self):
        village_system.update_village_politics(self)

    def update(self):
        self.tick += 1
        self.llm_calls_this_tick = 0

        self.respawn_resources()
        farming_system.update_farms(self)

        for agent in list(self.agents):
            if not agent.alive:
                continue
            agent.update(self)

        self.agents = [a for a in self.agents if a.alive]

        if len(self.agents) > MAX_AGENTS:
            extra = len(self.agents) - MAX_AGENTS

            for a in self.agents:
                if extra <= 0:
                    break
                if not a.is_player:
                    self.set_agent_dead(a, reason="population_cap")
                    extra -= 1

            self.agents = [a for a in self.agents if a.alive]

        self.detect_villages()
        self.update_village_ai()
        if self.build_policy_interval > 0 and self.tick % self.build_policy_interval == 0:
            building_system.run_village_build_policy(self)
        self.assign_village_roles()
        self.update_road_infrastructure()
        self.update_proto_asset_prototypes()
        if hasattr(self, "metrics_collector"):
            self.metrics_collector.collect(self)
