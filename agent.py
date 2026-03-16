from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
import random
import uuid

import systems.building_system as building_system

from config import (
    FOOD_EAT_GAIN,
    AGENT_START_HUNGER,
    REPRO_MIN_HUNGER,
    REPRO_PROB,
    REPRO_COST,
    MAX_AGENTS,
    HOUSE_WOOD_COST,
    HOUSE_STONE_COST,
)

ROLE_TASK_PERSISTENCE_TICKS = {
    "farmer": 8,
    "builder": 6,
    "hauler": 6,
}
RESIDENCE_PERSISTENCE_TICKS = 240
RESIDENCE_RELEASE_MAX_DRIFT = 24
SLEEP_ACCUMULATION_RATE = 0.07
FATIGUE_BASE_RATE = 0.03
REST_SLEEP_RECOVERY = 0.08
REST_FATIGUE_RECOVERY = 0.05
HOME_SLEEP_RECOVERY = 0.26
HOME_FATIGUE_RECOVERY = 0.16
CAMP_SLEEP_RECOVERY = 0.16
CAMP_FATIGUE_RECOVERY = 0.09
HIGH_SLEEP_NEED_THRESHOLD = 65.0
HIGH_FATIGUE_THRESHOLD = 60.0
LOW_HEALTH_THRESHOLD = 35.0
LOW_HAPPINESS_THRESHOLD = 30.0
HIGH_HAPPINESS_THRESHOLD = 70.0
BASE_HUNGER_DECAY_PER_TICK = 0.75
EARLY_SURVIVAL_GRACE_TICKS = 220
EARLY_HUNGER_DECAY_MULTIPLIER = 0.85
CAMP_BUFFER_HUNGER_DECAY_MULTIPLIER = 0.9
STARTUP_NO_SHELTER_HUNGER_DECAY_MULTIPLIER = 0.9
EARLY_FOOD_RELIABILITY_TICKS = 320
EARLY_FOOD_PRIORITY_HUNGER_THRESHOLD = 48.0
PRE_FIRST_FOOD_HUNGER_DECAY_MULTIPLIER = 0.9
HIGH_HUNGER_LATENCY_THRESHOLD = 35.0
MEDIUM_TERM_FOOD_CONTINUITY_HUNGER_THRESHOLD = 42.0
REPRO_MIN_AGE_TICKS = 260
REPRO_NEARBY_PARTNER_RADIUS = 3
BIOLOGICAL_SEX_VALUES = ("male", "female")
PROTO_REPRO_FOOD_SECURITY_WINDOW_TICKS = 12
STABLE_PROTO_HOUSEHOLD_RADIUS = 6
STABLE_PROTO_HOUSEHOLD_MIN_STABILITY_TICKS = 140
STABLE_PROTO_HOUSEHOLD_ANCHOR_MAX_AGE_TICKS = 80
STABLE_PROTO_HOUSEHOLD_ANCHOR_SEARCH_RADIUS = 18
STABLE_PROTO_HOUSEHOLD_ANCHOR_CAMP_LINK_RADIUS = 10
STABLE_PROTO_PARTNER_COLOCALITY_COMMIT_TICKS = 6
STABLE_PROTO_PARTNER_CONVERGENCE_TTL_TICKS = 10
STABLE_PROTO_COPRESENCE_RADIUS = 4
STABLE_PROTO_COPRESENCE_WINDOW_TICKS = 8
STABLE_PROTO_MICRO_CLOSURE_MAX_DISTANCE = 6
STABLE_PROTO_MICRO_CLOSURE_TTL_TICKS = 5
STABLE_PROTO_PARTNER_DRIFT_DAMPING_TTL_TICKS = 6
STABLE_PROTO_MICRO_CONTEXT_HOLD_GRACE_TICKS = 1
STABLE_PROTO_PATH_INACTIVITY_HOLD_TTL_TICKS = 2
LOCAL_LOOP_COMMITMENT_TICKS = 8
EAT_TRIGGER_BASE_THRESHOLD = 50
CONSTRUCTION_SITE_STICKINESS_TICKS = 18
CONSTRUCTION_SITE_RECENT_ACTIVITY_TICKS = 40
CONSTRUCTION_SITE_JUST_WORKED_GRACE_TICKS = 8
FORAGING_TARGET_LOCK_TICKS = 6
FORAGING_PRESSURE_HYSTERESIS = {
    "high": {"stay_high_min_ratio": 1.15, "drop_to_low_ratio": 0.72},
    "low": {"stay_low_max_ratio": 0.90, "rise_to_high_min_ratio": 1.45},
    "medium": {"rise_to_high_min_ratio": 1.45, "drop_to_low_ratio": 0.72},
}
FORAGING_POST_HARVEST_CONTINUE_TASKS = {
    "food_logistics",
    "village_logistics",
    "build_house",
    "build_storage",
    "gather_materials",
    "farm_cycle",
}
# These tasks can be useful for social continuity, so guards against them must stay narrow.
FORAGING_POST_HARVEST_REDIRECT_TASKS = {
    "camp_supply_food",
    "bootstrap_gather",
    "bootstrap_build_house",
}
POST_FIRST_HARVEST_RECENT_TICKS = 5
POST_FIRST_HARVEST_NEARBY_FOOD_DISTANCE = 2
POST_FIRST_HARVEST_LOW_HARVEST_ACTIONS = 2
POST_FIRST_HARVEST_NON_CRITICAL_HUNGER = 24.0


@dataclass
class Agent:
    x: int
    y: int
    brain: Any
    is_player: bool = False
    player_id: Optional[str] = None
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    alive: bool = True
    hunger: float = float(AGENT_START_HUNGER)
    sleep_need: float = field(default_factory=lambda: random.uniform(0.0, 20.0))
    fatigue: float = field(default_factory=lambda: random.uniform(0.0, 20.0))
    health: float = 100.0
    happiness: float = field(default_factory=lambda: random.uniform(40.0, 60.0))

    inventory: Dict[str, int] = field(
        default_factory=lambda: {"food": 0, "wood": 0, "stone": 0}
    )
    max_inventory: int = 5
    visual_radius_tiles: int = 8
    social_radius_tiles: int = 8

    memory: Dict[str, set] = field(
        default_factory=lambda: {
            "food": set(),
            "wood": set(),
            "stone": set(),
            "villages": set(),
            "farms": set(),
        }
    )

    repro_cooldown: int = 0
    biological_sex: str = field(default_factory=lambda: random.choice(BIOLOGICAL_SEX_VALUES))
    repro_proto_food_security_stable_ticks: int = 0
    stable_proto_anchor_village_id: Optional[int] = None
    stable_proto_anchor_tick: int = -1
    stable_proto_partner_convergence_agent_id: Optional[str] = None
    stable_proto_partner_convergence_until_tick: int = -1
    stable_proto_partner_convergence_anchor_village_id: Optional[int] = None
    stable_proto_copresence_ticks: int = 0
    stable_proto_micro_partner_agent_id: Optional[str] = None
    stable_proto_micro_until_tick: int = -1
    stable_proto_micro_anchor_village_id: Optional[int] = None
    stable_proto_micro_invoke_tick: int = -1
    stable_proto_micro_invoke_distance: int = 0
    stable_proto_path_inactivity_hold_until_tick: int = -1
    stable_proto_path_inactivity_hold_anchor_village_id: Optional[int] = None
    stable_proto_drift_damping_partner_agent_id: Optional[str] = None
    stable_proto_drift_damping_until_tick: int = -1
    stable_proto_drift_damping_anchor_village_id: Optional[int] = None

    goal: str = "survive"
    last_llm_tick: int = 0
    llm_pending: bool = False

    role: str = "npc"
    village_id: Optional[int] = None
    founder: bool = False
    home_building_id: Optional[str] = None
    home_village_uid: Optional[str] = None
    primary_village_uid: Optional[str] = None
    village_affiliation_status: str = "unaffiliated"
    village_affiliation_scores: Dict[str, Dict[str, float]] = field(default_factory=dict)
    residence_persistence_until_tick: int = -1
    proto_specialization: str = "none"
    proto_specialization_until_tick: int = -1
    proto_specialization_last_assigned_tick: int = -1
    proto_task_anchor: Dict[str, Any] = field(default_factory=dict)

    task: str = "idle"
    task_target: Optional[Tuple[int, int]] = None
    home_pos: Optional[Tuple[int, int]] = None
    work_pos: Optional[Tuple[int, int]] = None
    delivery_target_building_id: Optional[str] = None
    delivery_resource_type: Optional[str] = None
    delivery_reserved_amount: int = 0
    delivery_commit_until_tick: int = -1
    delivery_chain_started_tick: int = -1
    camp_loop_commit_until_tick: int = -1
    transfer_source_storage_id: Optional[str] = None
    transfer_target_storage_id: Optional[str] = None
    transfer_resource_type: Optional[str] = None
    transfer_amount: int = 0
    role_task_persisted_task: Optional[str] = None
    role_task_persistence_until_tick: int = -1
    movement_prev_tile: Optional[Tuple[int, int]] = None
    movement_commit_target: Optional[Tuple[int, int]] = None
    movement_commit_until_tick: int = -1
    movement_cached_target: Optional[Tuple[int, int]] = None
    movement_cached_path: List[Tuple[int, int]] = field(default_factory=list)
    movement_cached_path_tick: int = -1
    construction_site_commit_until_tick: int = -1
    construction_site_commit_site_id: Optional[str] = None
    primary_commitment_type: str = "none"
    primary_commitment_target_id: Optional[str] = None
    primary_commitment_status: str = "none"
    primary_commitment_created_tick: int = -1
    primary_commitment_last_progress_tick: int = -1
    primary_commitment_paused_reason: str = ""
    primary_commitment_paused_tick: int = -1
    last_pos: Optional[Tuple[int, int]] = None
    stuck_ticks: int = 0
    leader_traits: Optional[Dict[str, str]] = None
    current_intention: Optional[Dict[str, Any]] = None
    current_innovation_proposal: Optional[Dict[str, Any]] = None
    first_food_relief_tick: int = -1
    high_hunger_enter_tick: int = -1
    high_hunger_episode_count: int = 0
    foraging_trip_active: bool = False
    foraging_trip_start_tick: int = -1
    foraging_trip_move_ticks: int = 0
    foraging_trip_harvest_units: int = 0
    foraging_trip_harvest_actions: int = 0
    foraging_trip_retarget_count: int = 0
    foraging_trip_first_harvest_tick: int = -1
    foraging_trip_target: Optional[Tuple[int, int]] = None
    foraging_target_lock_until_tick: int = -1
    foraging_target_set_tick: int = -1
    foraging_trip_last_harvest_pos: Optional[Tuple[int, int]] = None
    foraging_trip_current_consecutive_harvest_actions: int = 0
    foraging_trip_max_consecutive_harvest_actions: int = 0
    foraging_pressure_regime: str = "medium"
    foraging_pressure_ratio: float = 0.0
    foraging_patch_exploit_until_tick: int = -1
    foraging_patch_exploit_target_harvest_actions: int = 0
    foraging_patch_exploit_anchor: Optional[Tuple[int, int]] = None
    self_model: Dict[str, Any] = field(default_factory=dict)
    proto_traits: Dict[str, Any] = field(default_factory=dict)
    cognitive_profile: Dict[str, Any] = field(default_factory=dict)
    social_influence: float = 0.0
    last_social_influence_tick: int = -1
    social_memory: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {"known_agents": {}}
    )
    recent_encounters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    recent_familiar_activity_zones: List[Dict[str, Any]] = field(default_factory=list)
    knowledge_state: Dict[str, List[Dict[str, Any]]] = field(
        default_factory=lambda: {
            "known_resource_spots": [],
            "known_useful_buildings": [],
            "known_routes": [],
            "known_practices": [],
            "known_inventions": [],
        }
    )
    episodic_memory: Dict[str, List[Dict[str, Any]]] = field(
        default_factory=lambda: {"recent_events": []}
    )
    subjective_state: Dict[str, Any] = field(default_factory=dict)
    short_term_memory: Dict[str, List[Dict[str, Any]]] = field(
        default_factory=lambda: {
            "recently_seen_resources": [],
            "recently_seen_agents": [],
            "recently_seen_buildings": [],
        }
    )

    def inventory_load(self) -> int:
        return int(self.inventory.get("food", 0)) + int(self.inventory.get("wood", 0)) + int(self.inventory.get("stone", 0))

    def inventory_space(self) -> int:
        return max(0, int(self.max_inventory) - self.inventory_load())

    def _near_storage(self, village: Optional[Dict]) -> bool:
        if not village:
            return False
        sp = village.get("storage_pos")
        if not sp:
            return False
        return abs(self.x - sp["x"]) <= 1 and abs(self.y - sp["y"]) <= 1

    @staticmethod
    def _clamp_stat(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    def _is_on_home_tile(self, world: "World") -> bool:
        if self.home_building_id is None:
            return False
        home = getattr(world, "buildings", {}).get(str(self.home_building_id))
        if not isinstance(home, dict):
            return False
        if str(home.get("type", "")) != "house":
            return False
        if str(home.get("operational_state", "")) != "active":
            return False
        hx = int(home.get("x", self.x))
        hy = int(home.get("y", self.y))
        return abs(int(self.x) - hx) + abs(int(self.y) - hy) <= 1

    def _has_valid_home(self, world: "World") -> bool:
        if self.home_building_id is None:
            return False
        home = getattr(world, "buildings", {}).get(str(self.home_building_id))
        if not isinstance(home, dict):
            return False
        return str(home.get("type", "")) == "house" and str(home.get("operational_state", "")) == "active"

    def _resolve_building_village_uid(self, world: "World", building: Dict[str, Any]) -> str:
        uid = str(building.get("village_uid", "") or "")
        if uid:
            return uid
        vid = building.get("village_id")
        if vid is not None and hasattr(world, "resolve_village_uid"):
            resolved = world.resolve_village_uid(vid)
            if resolved is not None:
                return str(resolved)
        return ""

    def _assigned_construction_site(self, world: "World", *, expected_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        sid = str(getattr(self, "assigned_building_id", "") or "")
        if not sid:
            return None
        site = getattr(world, "buildings", {}).get(sid)
        if not isinstance(site, dict):
            return None
        if str(site.get("operational_state", "")) != "under_construction":
            return None
        if expected_type and str(site.get("type", "")) != str(expected_type):
            return None
        return site

    def _construction_commitment_site(self, world: "World") -> Optional[Dict[str, Any]]:
        if str(getattr(self, "primary_commitment_type", "")) != "finish_construction":
            return None
        sid = str(getattr(self, "primary_commitment_target_id", "") or "")
        if not sid:
            return None
        site = getattr(world, "buildings", {}).get(sid)
        return site if isinstance(site, dict) else None

    def _nearest_village_construction_site(self, world: "World", *, preferred_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        vid = getattr(self, "village_id", None)
        candidates: List[Tuple[int, int, int, str, Dict[str, Any]]] = []
        for building in getattr(world, "buildings", {}).values():
            if not isinstance(building, dict):
                continue
            btype = str(building.get("type", ""))
            if btype not in {"house", "storage"}:
                continue
            if preferred_type and btype != str(preferred_type):
                continue
            if str(building.get("operational_state", "")) != "under_construction":
                continue
            if vid is not None and building.get("village_id") != vid:
                continue
            progress = int(building.get("construction_progress", 0))
            delivered = int(building.get("construction_delivered_units", 0))
            dist = abs(int(self.x) - int(building.get("x", 0))) + abs(int(self.y) - int(building.get("y", 0)))
            candidates.append(
                (
                    0 if progress > 0 else 1,
                    0 if delivered > 0 else 1,
                    dist,
                    str(building.get("building_id", "")),
                    building,
                )
            )
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
        return candidates[0][4]

    def _record_commitment_event(self, world: "World", event_name: str, *, reason: str, site_id: Optional[str] = None) -> None:
        if hasattr(world, "record_construction_debug_event"):
            world.record_construction_debug_event(
                self,
                event_name,
                reason=str(reason or "unknown"),
                site_id=str(site_id or getattr(self, "primary_commitment_target_id", "") or ""),
            )

    def _set_primary_construction_commitment(self, world: "World", site: Dict[str, Any], *, reason: str) -> None:
        sid = str(site.get("building_id", "") or "")
        if not sid:
            return
        now_tick = int(getattr(world, "tick", 0))
        previous_target = str(getattr(self, "primary_commitment_target_id", "") or "")
        previous_status = str(getattr(self, "primary_commitment_status", "none") or "none")
        is_new = not (str(getattr(self, "primary_commitment_type", "")) == "finish_construction" and previous_target == sid)

        self.primary_commitment_type = "finish_construction"
        self.primary_commitment_target_id = sid
        self.primary_commitment_paused_reason = ""
        self.primary_commitment_paused_tick = -1
        if is_new:
            self.primary_commitment_created_tick = now_tick
            self.primary_commitment_last_progress_tick = max(
                int(getattr(self, "primary_commitment_last_progress_tick", -1)),
                int(site.get("construction_first_progress_tick", -1)),
            )
            self.primary_commitment_status = "active"
            if hasattr(world, "record_settlement_progression_metric"):
                world.record_settlement_progression_metric("builder_commitment_created_count")
            self._record_commitment_event(world, "commitment_created", reason=reason, site_id=sid)
            return

        if previous_status in {"paused", "interrupted"}:
            self.primary_commitment_status = "active"
            if hasattr(world, "record_settlement_progression_metric"):
                world.record_settlement_progression_metric("builder_commitment_resume_count")
                world.record_settlement_progression_metric("builder_returned_to_same_site_count")
                paused_tick = int(getattr(self, "primary_commitment_paused_tick", -1))
                if paused_tick >= 0:
                    delay = max(0, now_tick - paused_tick)
                    world.record_settlement_progression_metric("builder_commitment_resume_delay_total", int(delay))
                    world.record_settlement_progression_metric("builder_commitment_resume_delay_samples", 1)
            self._record_commitment_event(world, "commitment_resumed", reason=reason, site_id=sid)
        else:
            self.primary_commitment_status = "active"
        self.primary_commitment_paused_tick = -1

    def _pause_primary_construction_commitment(self, world: "World", reason: str) -> None:
        if str(getattr(self, "primary_commitment_type", "")) != "finish_construction":
            return
        if str(getattr(self, "primary_commitment_status", "")) == "completed":
            return
        sid = str(getattr(self, "primary_commitment_target_id", "") or "")
        if not sid:
            return
        self.primary_commitment_status = "paused"
        self.primary_commitment_paused_reason = str(reason or "unknown")
        self.primary_commitment_paused_tick = int(getattr(world, "tick", 0))
        if hasattr(world, "record_settlement_progression_metric"):
            world.record_settlement_progression_metric("builder_commitment_pause_count")
        self._record_commitment_event(world, "commitment_paused", reason=str(reason or "unknown"), site_id=sid)

    def _clear_primary_construction_commitment(self) -> None:
        self.primary_commitment_type = "none"
        self.primary_commitment_target_id = None
        self.primary_commitment_status = "none"
        self.primary_commitment_created_tick = -1
        self.primary_commitment_last_progress_tick = -1
        self.primary_commitment_paused_reason = ""
        self.primary_commitment_paused_tick = -1

    def _finalize_primary_construction_commitment(self, world: "World", *, status: str, reason: str) -> None:
        if str(getattr(self, "primary_commitment_type", "")) != "finish_construction":
            return
        sid = str(getattr(self, "primary_commitment_target_id", "") or "")
        if not sid:
            self._clear_primary_construction_commitment()
            return
        now_tick = int(getattr(world, "tick", 0))
        created_tick = int(getattr(self, "primary_commitment_created_tick", -1))
        duration = max(0, now_tick - created_tick) if created_tick >= 0 else 0
        if hasattr(world, "record_settlement_progression_metric"):
            world.record_settlement_progression_metric("builder_commitment_duration_total", int(duration))
            world.record_settlement_progression_metric("builder_commitment_duration_samples", 1)
            if status == "completed":
                world.record_settlement_progression_metric("builder_commitment_completed_count")
            else:
                world.record_settlement_progression_metric("builder_commitment_abandoned_count")
        self._record_commitment_event(world, f"commitment_{status}", reason=str(reason or "unknown"), site_id=sid)
        self._clear_primary_construction_commitment()

    def _refresh_primary_construction_commitment_state(self, world: "World") -> None:
        if str(getattr(self, "primary_commitment_type", "")) != "finish_construction":
            return
        sid = str(getattr(self, "primary_commitment_target_id", "") or "")
        if not sid:
            self._clear_primary_construction_commitment()
            return
        site = getattr(world, "buildings", {}).get(sid)
        if not isinstance(site, dict):
            self._finalize_primary_construction_commitment(world, status="abandoned", reason="site_invalid")
            return
        state = str(site.get("operational_state", ""))
        if state == "under_construction":
            return
        if state in {"active", "complete", "completed"}:
            self._finalize_primary_construction_commitment(world, status="completed", reason="site_completed")
            return
        self._finalize_primary_construction_commitment(world, status="abandoned", reason="site_invalid")

    def _should_hold_construction_site_commitment(self, world: "World", site: Optional[Dict[str, Any]]) -> bool:
        if not isinstance(site, dict):
            return False
        if float(getattr(self, "hunger", 100.0)) <= 12.0:
            return False
        sid = str(site.get("building_id", "") or "")
        now_tick = int(getattr(world, "tick", 0))
        if (
            sid
            and sid == str(getattr(self, "construction_site_commit_site_id", "") or "")
            and now_tick <= int(getattr(self, "construction_site_commit_until_tick", -1))
        ):
            return True

        required_work = max(1, int(site.get("construction_required_work", 1)))
        completed_work = max(0, int(site.get("construction_progress", 0)))
        remaining_work = max(0, required_work - completed_work)
        delivered_units = max(0, int(site.get("construction_delivered_units", 0)))
        buffered = site.get("construction_buffer", {}) if isinstance(site.get("construction_buffer", {}), dict) else {}
        buffered_total = max(0, int(buffered.get("wood", 0))) + max(0, int(buffered.get("stone", 0))) + max(0, int(buffered.get("food", 0)))

        started = bool(delivered_units > 0 or completed_work > 0 or remaining_work > 0)
        if not started:
            return False

        sx = int(site.get("x", self.x))
        sy = int(site.get("y", self.y))
        on_site = abs(int(self.x) - sx) + abs(int(self.y) - sy) <= int(max(1, getattr(building_system, "CONSTRUCTION_WORK_RANGE", 1)))
        last_progress = int(site.get("construction_last_progress_tick", -10_000))
        last_delivery = int(site.get("construction_last_delivery_tick", -10_000))
        recently_active = (now_tick - max(last_progress, last_delivery)) <= int(CONSTRUCTION_SITE_RECENT_ACTIVITY_TICKS)
        self_recent_progress = int(getattr(self, "primary_commitment_last_progress_tick", -10_000))
        builder_just_worked = (
            sid
            and sid == str(getattr(self, "primary_commitment_target_id", "") or "")
            and (now_tick - max(self_recent_progress, last_progress)) <= int(CONSTRUCTION_SITE_JUST_WORKED_GRACE_TICKS)
        )
        if not (on_site or recently_active or buffered_total > 0 or builder_just_worked):
            return False

        self.construction_site_commit_site_id = sid or None
        self.construction_site_commit_until_tick = max(
            int(getattr(self, "construction_site_commit_until_tick", -1)),
            now_tick + int(CONSTRUCTION_SITE_STICKINESS_TICKS),
        )
        return True

    def _resolve_foraging_pressure_regime(
        self, pressure_payload: Dict[str, Any], previous_regime: str
    ) -> Tuple[str, float]:
        ratio = 0.0
        if isinstance(pressure_payload, dict):
            supply = max(
                1,
                int(pressure_payload.get("near_food_sources", 0))
                + int(pressure_payload.get("camp_food", 0))
                + int(pressure_payload.get("house_food_nearby", 0)),
            )
            ratio = float(max(0, int(pressure_payload.get("nearby_needy_agents", 0)))) / float(supply)
            pressure_active = bool(pressure_payload.get("pressure_active", False))
        else:
            pressure_active = False
        prev = str(previous_regime or "medium")
        if prev == "high":
            if pressure_active and ratio >= float(FORAGING_PRESSURE_HYSTERESIS["high"]["stay_high_min_ratio"]):
                return "high", ratio
            if ratio < float(FORAGING_PRESSURE_HYSTERESIS["high"]["drop_to_low_ratio"]):
                return "low", ratio
            return "medium", ratio
        if prev == "low":
            if ratio <= float(FORAGING_PRESSURE_HYSTERESIS["low"]["stay_low_max_ratio"]):
                return "low", ratio
            if pressure_active and ratio >= float(FORAGING_PRESSURE_HYSTERESIS["low"]["rise_to_high_min_ratio"]):
                return "high", ratio
            return "medium", ratio
        if pressure_active and ratio >= float(FORAGING_PRESSURE_HYSTERESIS["medium"]["rise_to_high_min_ratio"]):
            return "high", ratio
        if ratio < float(FORAGING_PRESSURE_HYSTERESIS["medium"]["drop_to_low_ratio"]):
            return "low", ratio
        return "medium", ratio

    def _post_first_harvest_switch_context(
        self,
        world: "World",
        *,
        new_task: str,
        tick_now: int,
    ) -> Dict[str, Any]:
        first_harvest_tick_local = int(getattr(self, "foraging_trip_first_harvest_tick", -1))
        ticks_since_first = max(0, tick_now - first_harvest_tick_local) if first_harvest_tick_local >= 0 else -1
        exploit_until_local = int(getattr(self, "foraging_patch_exploit_until_tick", -1))
        exploit_target_local = int(getattr(self, "foraging_patch_exploit_target_harvest_actions", 0))
        within_exploit = bool(
            exploit_until_local >= tick_now
            and exploit_target_local > 0
            and int(getattr(self, "foraging_trip_harvest_actions", 0)) < exploit_target_local
        )
        commitment_active_local = bool(
            within_exploit
            or str(getattr(self, "primary_commitment_type", "none")) != "none"
        )
        target_valid_local = False
        task_target = getattr(self, "task_target", None)
        if isinstance(task_target, tuple) and len(task_target) == 2:
            target_valid_local = tuple((int(task_target[0]), int(task_target[1]))) in getattr(world, "food", set())
        local_food_available_local = 0
        nearest_food_distance_local = -1
        if hasattr(world, "compute_local_food_pressure_for_agent"):
            try:
                p = world.compute_local_food_pressure_for_agent(self, max_distance=10)
            except Exception:
                p = {}
            if isinstance(p, dict):
                local_food_available_local = int(p.get("near_food_sources", 0))
        if hasattr(world, "_find_nearest_food_to"):
            try:
                nf = world._find_nearest_food_to(int(self.x), int(self.y), radius=10)
            except Exception:
                nf = None
            if isinstance(nf, tuple) and len(nf) == 2:
                nearest_food_distance_local = abs(int(self.x) - int(nf[0])) + abs(int(self.y) - int(nf[1]))
        source_subsystem_local = "unknown"
        nt = str(new_task or "")
        if nt in {"eat_food", "rest", "survive"} or float(getattr(self, "hunger", 100.0)) < 18.0:
            source_subsystem_local = "survival_override"
        elif nt in {"idle", "wander"}:
            source_subsystem_local = "wander_fallback"
        elif nt == "gather_materials" and int(getattr(self, "inventory", {}).get("food", 0)) <= 2:
            source_subsystem_local = "inventory_logic"
        elif (not target_valid_local) and local_food_available_local <= 0:
            source_subsystem_local = "target_invalidated"
        elif nt and nt != "gather_food_wild":
            source_subsystem_local = "role_task_update"
        return {
            "source_subsystem": source_subsystem_local,
            "ticks_since_first_harvest": ticks_since_first,
            "within_exploitation_window": within_exploit,
            "commitment_active": commitment_active_local,
            "target_valid": bool(target_valid_local),
            "local_food_available": int(local_food_available_local),
            "nearest_food_distance": int(nearest_food_distance_local),
        }

    def _reserve_vs_group_tiebreak_decision(
        self,
        world: "World",
        pressure_payload: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Narrow final tie-break: allow reserve accumulation only when non-emergency
        post-policy conditions are already satisfied.
        Returns (reserve_wins, reason_code).
        """
        pressure = pressure_payload if isinstance(pressure_payload, dict) else {}
        camp_food = int(pressure.get("camp_food", 0))
        house_food = int(pressure.get("house_food_nearby", 0))
        near_food = int(pressure.get("near_food_sources", 0))
        needy = int(pressure.get("nearby_needy_agents", 0))
        pressure_score = int(pressure.get("pressure_score", 0))
        pressure_active = bool(pressure.get("pressure_active", False))
        unmet_pressure = bool(pressure.get("unmet_pressure", False))

        supply = max(0, camp_food + house_food + near_food)
        has_local_surplus = bool(supply >= max(2, needy + 1))
        if not has_local_surplus:
            return False, "blocked_no_surplus"

        stable_context = bool(
            str(getattr(self, "village_affiliation_status", "")) in {"attached", "resident"}
            or isinstance(world.nearest_active_camp_for_agent(self, max_distance=2), dict)
        )
        if not stable_context:
            return False, "blocked_unstable_context"

        regime, _ratio = self._resolve_foraging_pressure_regime(
            pressure,
            str(getattr(self, "foraging_pressure_regime", "medium") or "medium"),
        )
        reserve_total_now = 0
        if hasattr(world, "current_total_food_in_reserves"):
            try:
                reserve_total_now = int(world.current_total_food_in_reserves())
            except Exception:
                reserve_total_now = 0
        if regime in {"low", "medium"} and reserve_total_now <= 0:
            refill_recovery_possible = bool(
                supply >= max(3, needy + 1)
                and near_food >= 2
                and (camp_food + house_food) <= 1
                and needy <= 1
                and pressure_score <= 3
                and not unmet_pressure
            )
            if refill_recovery_possible:
                return True, "won"
        # FOOD-SECURITY-009:
        # In non-high pressure, require stronger local coverage before reserve wins.
        # This protects group-feeding continuity in low/reduced-pressure contexts.
        if regime in {"low", "medium"} and pressure_score <= 3:
            buffered_food = max(0, camp_food + house_food)
            strong_surplus = bool(supply >= max(4, needy + 2))
            if buffered_food < 3 or (not strong_surplus) or needy > 0:
                return False, "blocked_no_surplus"

        critical_group_need = bool(needy > 0 and (camp_food + house_food) <= 1)
        pressure_emergency = bool(
            regime == "high"
            or unmet_pressure
            or pressure_score >= 5
            or critical_group_need
        )
        if pressure_emergency:
            return False, "blocked_pressure"

        return True, "won"

    def _should_block_narrow_post_harvest_redirect(self, switch_context: Dict[str, Any]) -> bool:
        ticks_since_first = int(switch_context.get("ticks_since_first_harvest", -1))
        nearest_food_distance = int(switch_context.get("nearest_food_distance", -1))
        local_food_available = int(switch_context.get("local_food_available", 0))
        target_valid = bool(switch_context.get("target_valid", False))
        recent_first_harvest = 0 <= ticks_since_first <= int(POST_FIRST_HARVEST_RECENT_TICKS)
        nearby_continuation = 0 <= nearest_food_distance <= int(POST_FIRST_HARVEST_NEARBY_FOOD_DISTANCE)
        patch_viable = bool(target_valid or local_food_available > 0)
        low_trip_harvest = int(getattr(self, "foraging_trip_harvest_actions", 0)) <= int(POST_FIRST_HARVEST_LOW_HARVEST_ACTIONS)
        non_critical_survival = float(getattr(self, "hunger", 100.0)) >= float(POST_FIRST_HARVEST_NON_CRITICAL_HUNGER)
        role_update_source = str(switch_context.get("source_subsystem", "unknown")) == "role_task_update"
        return bool(
            role_update_source
            and recent_first_harvest
            and nearby_continuation
            and patch_viable
            and low_trip_harvest
            and non_critical_survival
        )

    def _is_house_claimably_active(self, building: Dict[str, Any]) -> bool:
        state = str(building.get("operational_state", "") or "")
        if state == "active":
            return True
        # Coherence window: a house that has reached required construction work
        # can be considered claimable even if activation flips later in the tick.
        if state == "under_construction":
            required = max(1, int(building.get("construction_required_work", 1)))
            progress = max(0, int(building.get("construction_progress", 0)))
            return progress >= required
        return False

    def _apply_base_physiology_tick(self) -> None:
        self.sleep_need = self._clamp_stat(float(self.sleep_need) + float(SLEEP_ACCUMULATION_RATE))
        self.fatigue = self._clamp_stat(float(self.fatigue) + float(FATIGUE_BASE_RATE))

    def _add_work_fatigue(self, amount: float) -> None:
        effort = max(0.0, float(amount))
        happiness = self._clamp_stat(float(getattr(self, "happiness", 50.0)))
        # Keep the effect mild: happiness nudges fatigue gain, it never dominates it.
        fatigue_scale = 1.0 - ((happiness - 50.0) / 50.0) * 0.12
        self.fatigue = self._clamp_stat(float(self.fatigue) + effort * max(0.82, min(1.18, fatigue_scale)))

    def _update_health_from_stressors(self) -> None:
        delta = 0.0
        if float(self.hunger) <= 35.0 and float(self.sleep_need) >= 70.0:
            delta -= 0.03
        if float(self.fatigue) >= 85.0:
            delta -= 0.02
        if float(self.hunger) >= 65.0 and float(self.sleep_need) <= 30.0 and float(self.fatigue) <= 30.0:
            delta += 0.012
        happiness = self._clamp_stat(float(getattr(self, "happiness", 50.0)))
        if happiness >= 70.0 and float(self.hunger) >= 55.0 and float(self.sleep_need) <= 45.0 and float(self.fatigue) <= 45.0:
            delta += 0.004
        if happiness <= 25.0 and (
            float(self.hunger) <= 35.0
            or float(self.sleep_need) >= 70.0
            or float(self.fatigue) >= 70.0
        ):
            delta -= 0.006
        self.health = self._clamp_stat(float(self.health) + delta)

    def _count_nearby_social_allies(self, world: "World", radius: int = 6) -> int:
        my_uid = str(getattr(self, "primary_village_uid", "") or getattr(self, "home_village_uid", "") or "")
        total = 0
        for other in getattr(world, "agents", []):
            if other is self or not getattr(other, "alive", False):
                continue
            dist = abs(int(getattr(other, "x", 0)) - int(self.x)) + abs(int(getattr(other, "y", 0)) - int(self.y))
            if dist > int(radius):
                continue
            other_uid = str(getattr(other, "primary_village_uid", "") or getattr(other, "home_village_uid", "") or "")
            same_group = bool(my_uid and other_uid and my_uid == other_uid)
            if same_group or str(getattr(other, "village_affiliation_status", "unaffiliated")) in {"attached", "resident"}:
                total += 1
        return int(total)

    def _update_happiness(self, world: "World", *, active_work: bool) -> None:
        delta = 0.0
        nearby_allies = self._count_nearby_social_allies(world, radius=6)
        at_home = self._is_on_home_tile(world)
        at_camp = bool(hasattr(world, "is_agent_near_camp") and world.is_agent_near_camp(self))
        resting = not bool(active_work)

        # Social proximity and settlement anchors.
        if nearby_allies > 0:
            delta += min(0.16, 0.03 + 0.04 * float(nearby_allies))
        else:
            delta -= 0.05
        if at_home:
            delta += 0.06
        elif at_camp:
            delta += 0.04
            if hasattr(world, "camp_has_food_for_agent") and bool(world.camp_has_food_for_agent(self, max_distance=3)):
                delta += 0.02

        # Rest/recovery context gives extra wellbeing support; home remains strongest.
        if resting and at_home:
            delta += 0.05
        elif resting and at_camp:
            delta += 0.03
        elif resting:
            delta += 0.01

        # Physiological coupling.
        if float(self.hunger) <= 25.0:
            delta -= 0.06
        elif float(self.hunger) >= 60.0:
            delta += 0.02
        if float(self.sleep_need) >= 75.0:
            delta -= 0.05
        elif float(self.sleep_need) <= 45.0:
            delta += 0.02
        if float(self.fatigue) >= 75.0:
            delta -= 0.05
        elif float(self.fatigue) <= 45.0:
            delta += 0.02
        if float(self.health) <= 40.0:
            delta -= 0.04
        elif float(self.health) >= 70.0:
            delta += 0.01

        if active_work and (float(self.sleep_need) >= 70.0 or float(self.fatigue) >= 70.0):
            delta -= 0.02

        self.happiness = self._clamp_stat(float(getattr(self, "happiness", 50.0)) + delta)

    def _apply_recovery(self, world: "World", *, active_work: bool) -> None:
        applied_idle = False
        applied_home = False
        applied_camp = False
        resting = not bool(active_work)
        at_home = self._is_on_home_tile(world)
        at_camp = bool(hasattr(world, "is_agent_near_camp") and world.is_agent_near_camp(self))
        happiness = self._clamp_stat(float(getattr(self, "happiness", 50.0)))
        recovery_scale = 1.0 + ((happiness - 50.0) / 50.0) * 0.10
        recovery_scale = max(0.88, min(1.12, recovery_scale))
        if resting:
            self.sleep_need = self._clamp_stat(float(self.sleep_need) - float(REST_SLEEP_RECOVERY) * recovery_scale)
            self.fatigue = self._clamp_stat(float(self.fatigue) - float(REST_FATIGUE_RECOVERY) * recovery_scale)
            applied_idle = True
            if at_camp and not at_home:
                self.sleep_need = self._clamp_stat(float(self.sleep_need) - float(CAMP_SLEEP_RECOVERY) * recovery_scale)
                self.fatigue = self._clamp_stat(float(self.fatigue) - float(CAMP_FATIGUE_RECOVERY) * recovery_scale)
                applied_camp = True
        if at_home:
            self.sleep_need = self._clamp_stat(float(self.sleep_need) - float(HOME_SLEEP_RECOVERY) * recovery_scale)
            self.fatigue = self._clamp_stat(float(self.fatigue) - float(HOME_FATIGUE_RECOVERY) * recovery_scale)
            applied_home = True
        role_key = str(getattr(self, "role", "other") or "other")
        uid = str(world._resolve_agent_work_village_uid(self) or "") if hasattr(world, "_resolve_agent_work_village_uid") else ""
        if applied_idle and hasattr(world, "record_recovery_stage"):
            world.record_recovery_stage(self, "idle_recovery_applied", village_uid=uid, role=role_key)
        if applied_home and hasattr(world, "record_recovery_stage"):
            world.record_recovery_stage(self, "home_recovery_applied", village_uid=uid, role=role_key)
        if applied_camp and hasattr(world, "record_camp_event"):
            camp = world.nearest_active_camp_for_agent(self, max_distance=2) if hasattr(world, "nearest_active_camp_for_agent") else None
            world.record_camp_event(
                "camp_rest_events",
                camp_id=str(camp.get("camp_id", "")) if isinstance(camp, dict) else None,
                village_uid=str(camp.get("village_uid", "")) if isinstance(camp, dict) else None,
            )
        if (applied_idle or applied_home) and hasattr(world, "record_recovery_stage"):
            world.record_recovery_stage(self, "recovery_success_tick", village_uid=uid, role=role_key)
        if applied_home and hasattr(world, "record_recovery_failure_reason"):
            world.record_recovery_failure_reason(self, "recovery_home_success", village_uid=uid, role=role_key)
        elif applied_idle and hasattr(world, "record_recovery_failure_reason"):
            world.record_recovery_failure_reason(self, "recovery_idle_success", village_uid=uid, role=role_key)
        elif resting and not at_home and hasattr(world, "record_recovery_failure_reason"):
            world.record_recovery_failure_reason(self, "recovery_only_idle", village_uid=uid, role=role_key)

    def _deposit_inventory_to_storage(self, world: "World") -> bool:
        try:
            import systems.building_system as building_system
            return building_system.deposit_agent_inventory_to_storage(world, self)
        except Exception:
            return False

    def _withdraw_build_materials(self, world: "World", wood_need: int, stone_need: int) -> bool:
        try:
            import systems.building_system as building_system
            return building_system.withdraw_build_materials_from_storage(
                world,
                self,
                wood_need=wood_need,
                stone_need=stone_need,
            )
        except Exception:
            return False

    def update_memory(self, world: "World") -> None:
        vision = 6

        for dx in range(-vision, vision + 1):
            for dy in range(-vision, vision + 1):
                x = self.x + dx
                y = self.y + dy

                if x < 0 or y < 0 or x >= world.width or y >= world.height:
                    continue

                pos = (x, y)

                if pos in world.food:
                    self.memory["food"].add(pos)

                if pos in world.wood:
                    self.memory["wood"].add(pos)

                if pos in world.stone:
                    self.memory["stone"].add(pos)

                if pos in getattr(world, "farms", set()):
                    self.memory["farms"].add(pos)

        for village in getattr(world, "villages", []):
            center = village.get("center")
            if not center:
                continue

            vx = center.get("x")
            vy = center.get("y")

            if vx is None or vy is None:
                continue

            if abs(vx - self.x) <= vision * 2 and abs(vy - self.y) <= vision * 2:
                self.memory["villages"].add((vx, vy))

    def cleanup_memory(self, world: "World") -> None:
        self.memory["food"] = {p for p in self.memory["food"] if p in world.food}
        self.memory["wood"] = {p for p in self.memory["wood"] if p in world.wood}
        self.memory["stone"] = {p for p in self.memory["stone"] if p in world.stone}
        self.memory["farms"] = {
            p for p in self.memory["farms"] if p in getattr(world, "farms", set())
        }

        valid_village_centers = set()

        for village in getattr(world, "villages", []):
            center = village.get("center")
            if center and "x" in center and "y" in center:
                valid_village_centers.add((center["x"], center["y"]))

        self.memory["villages"] = {
            p for p in self.memory["villages"] if p in valid_village_centers
        }

    def update_role_task(self, world: "World") -> None:
        village = world.get_village_by_id(self.village_id)
        prev_task = str(getattr(self, "task", "idle"))
        tick_now = int(getattr(world, "tick", 0))
        born_tick = int(getattr(self, "born_tick", tick_now))
        age = max(0, tick_now - born_tick)
        first_food_relief_tick = int(getattr(self, "first_food_relief_tick", -1))
        if (
            village is None
            and
            first_food_relief_tick < 0
            and age <= int(EARLY_FOOD_RELIABILITY_TICKS)
            and float(getattr(self, "hunger", 100.0)) <= float(EARLY_FOOD_PRIORITY_HUNGER_THRESHOLD)
            and int(getattr(self, "inventory", {}).get("food", 0)) <= 0
        ):
            self.task = "gather_food_wild"
            nearest_food = None
            if hasattr(world, "find_scarcity_adaptive_food_target"):
                try:
                    nearest_food = world.find_scarcity_adaptive_food_target(
                        self,
                        radius=max(12, int(self.visual_radius_tiles) + 6),
                    )
                except Exception:
                    nearest_food = None
            elif hasattr(world, "_find_nearest_food_to"):
                try:
                    nearest_food = world._find_nearest_food_to(int(self.x), int(self.y), radius=max(12, int(self.visual_radius_tiles) + 6))
                except Exception:
                    nearest_food = None
            if isinstance(nearest_food, tuple) and len(nearest_food) == 2:
                self.task_target = (int(nearest_food[0]), int(nearest_food[1]))
                self.foraging_target_set_tick = int(tick_now)
            if hasattr(world, "record_settlement_progression_metric"):
                world.record_settlement_progression_metric("early_food_priority_overrides")
            return

        self._refresh_primary_construction_commitment_state(world)
        if hasattr(world, "update_agent_proto_specialization"):
            world.update_agent_proto_specialization(self)
        proto_spec = str(getattr(self, "proto_specialization", "none") or "none")

        if self.is_player:
            self.task = "player_controlled"
            return

        role = getattr(self, "role", "npc")

        if role == "leader":
            self.task = "manage_village"
            return

        # bootstrap: prima che esista un villaggio, gli NPC fondano i primi nuclei
        if village is None:
            if (
                str(prev_task) == "camp_supply_food"
                and tick_now <= int(getattr(self, "camp_loop_commit_until_tick", -1))
                and float(getattr(self, "hunger", 100.0)) >= 20.0
                and int(self.inventory.get("food", 0)) > 0
                and hasattr(world, "nearest_active_camp_for_agent")
            ):
                camp = world.nearest_active_camp_for_agent(self, max_distance=6)
                if isinstance(camp, dict):
                    self.task = "camp_supply_food"
                    self.task_target = (int(camp.get("x", self.x)), int(camp.get("y", self.y)))
                    if hasattr(world, "record_completion_bias_applied"):
                        world.record_completion_bias_applied()
                    if hasattr(world, "record_delivery_commitment_retained"):
                        world.record_delivery_commitment_retained()
                    return
            anchor = getattr(self, "proto_task_anchor", {})
            source_pos = tuple(anchor.get("source_pos", ())) if isinstance(anchor, dict) else ()
            drop_pos = tuple(anchor.get("drop_pos", ())) if isinstance(anchor, dict) else ()
            target_pos = tuple(anchor.get("target_pos", ())) if isinstance(anchor, dict) else ()
            local_food_pressure = {}
            if hasattr(world, "compute_local_food_pressure_for_agent"):
                try:
                    local_food_pressure = world.compute_local_food_pressure_for_agent(self)
                except Exception:
                    local_food_pressure = {}
            pressure_active = bool(isinstance(local_food_pressure, dict) and local_food_pressure.get("pressure_active", False))
            if proto_spec == "food_gatherer":
                if int(self.inventory.get("food", 0)) > 0 and (
                    pressure_active or int(local_food_pressure.get("camp_food", 0) if isinstance(local_food_pressure, dict) else 0) <= 2
                ):
                    tiebreak_invoked = bool(isinstance(local_food_pressure, dict) and pressure_active)
                    if tiebreak_invoked and hasattr(world, "record_settlement_progression_metric"):
                        world.record_settlement_progression_metric("reserve_final_tiebreak_invoked_count")
                    reserve_win = False
                    reserve_reason = "blocked_pressure"
                    if tiebreak_invoked:
                        reserve_win, reserve_reason = self._reserve_vs_group_tiebreak_decision(world, local_food_pressure)
                        if hasattr(world, "record_settlement_progression_metric"):
                            if reserve_win:
                                world.record_settlement_progression_metric("reserve_final_tiebreak_won_count")
                            else:
                                world.record_settlement_progression_metric("reserve_final_tiebreak_lost_count")
                                if reserve_reason == "blocked_pressure":
                                    world.record_settlement_progression_metric("reserve_final_tiebreak_blocked_by_pressure_count")
                                elif reserve_reason == "blocked_unstable_context":
                                    world.record_settlement_progression_metric("reserve_final_tiebreak_blocked_by_unstable_context_count")
                                elif reserve_reason == "blocked_no_surplus":
                                    world.record_settlement_progression_metric("reserve_final_tiebreak_blocked_by_no_surplus_count")
                    self.task = "food_logistics" if reserve_win else "camp_supply_food"
                    loop_bonus = 0
                    density_state = self.subjective_state.get("social_density", {}) if isinstance(self.subjective_state, dict) else {}
                    nearby_familiar = int(density_state.get("familiar_nearby_agents_count", 0))
                    nearby_agents_count = int(density_state.get("nearby_agents_count", 0))
                    if nearby_familiar > 0 and float(getattr(self, "hunger", 100.0)) >= 28.0:
                        loop_bonus = 2
                        if nearby_agents_count >= 8:
                            loop_bonus = 1
                            if hasattr(world, "record_social_encounter_event"):
                                world.record_social_encounter_event("density_safe_loop_bonus_reduced_count")
                        if hasattr(world, "record_social_encounter_event"):
                            world.record_social_encounter_event("familiar_loop_continuity_bonus")
                    self.camp_loop_commit_until_tick = tick_now + int(LOCAL_LOOP_COMMITMENT_TICKS) + int(loop_bonus)
                    if len(drop_pos) == 2:
                        self.task_target = (int(drop_pos[0]), int(drop_pos[1]))
                    if pressure_active and not reserve_win and hasattr(world, "record_pressure_backed_loop_selected"):
                        world.record_pressure_backed_loop_selected()
                else:
                    self.task = "gather_food_wild"
                    if len(source_pos) == 2:
                        self.task_target = (int(source_pos[0]), int(source_pos[1]))
                return
            if proto_spec == "food_hauler":
                if pressure_active or int(self.inventory.get("food", 0)) > 0:
                    tiebreak_invoked = bool(isinstance(local_food_pressure, dict) and pressure_active and int(self.inventory.get("food", 0)) > 0)
                    if tiebreak_invoked and hasattr(world, "record_settlement_progression_metric"):
                        world.record_settlement_progression_metric("reserve_final_tiebreak_invoked_count")
                    reserve_win = False
                    reserve_reason = "blocked_pressure"
                    if tiebreak_invoked:
                        reserve_win, reserve_reason = self._reserve_vs_group_tiebreak_decision(world, local_food_pressure)
                        if hasattr(world, "record_settlement_progression_metric"):
                            if reserve_win:
                                world.record_settlement_progression_metric("reserve_final_tiebreak_won_count")
                            else:
                                world.record_settlement_progression_metric("reserve_final_tiebreak_lost_count")
                                if reserve_reason == "blocked_pressure":
                                    world.record_settlement_progression_metric("reserve_final_tiebreak_blocked_by_pressure_count")
                                elif reserve_reason == "blocked_unstable_context":
                                    world.record_settlement_progression_metric("reserve_final_tiebreak_blocked_by_unstable_context_count")
                                elif reserve_reason == "blocked_no_surplus":
                                    world.record_settlement_progression_metric("reserve_final_tiebreak_blocked_by_no_surplus_count")
                    self.task = "food_logistics" if reserve_win else "camp_supply_food"
                    loop_bonus = 0
                    density_state = self.subjective_state.get("social_density", {}) if isinstance(self.subjective_state, dict) else {}
                    nearby_familiar = int(density_state.get("familiar_nearby_agents_count", 0))
                    nearby_agents_count = int(density_state.get("nearby_agents_count", 0))
                    if nearby_familiar > 0 and float(getattr(self, "hunger", 100.0)) >= 28.0:
                        loop_bonus = 2
                        if nearby_agents_count >= 8:
                            loop_bonus = 1
                            if hasattr(world, "record_social_encounter_event"):
                                world.record_social_encounter_event("density_safe_loop_bonus_reduced_count")
                        if hasattr(world, "record_social_encounter_event"):
                            world.record_social_encounter_event("familiar_loop_continuity_bonus")
                    self.camp_loop_commit_until_tick = tick_now + int(LOCAL_LOOP_COMMITMENT_TICKS) + int(loop_bonus)
                    if int(self.inventory.get("food", 0)) > 0 and len(drop_pos) == 2:
                        self.task_target = (int(drop_pos[0]), int(drop_pos[1]))
                    elif len(source_pos) == 2:
                        self.task_target = (int(source_pos[0]), int(source_pos[1]))
                    if pressure_active and not reserve_win and hasattr(world, "record_pressure_backed_loop_selected"):
                        world.record_pressure_backed_loop_selected()
                else:
                    self.task = "gather_food_wild"
                return
            if (
                self.inventory.get("wood", 0) >= HOUSE_WOOD_COST
                and self.inventory.get("stone", 0) >= HOUSE_STONE_COST
            ):
                self.task = "bootstrap_build_house"
            else:
                self.task = "bootstrap_gather"
            if proto_spec == "builder" and (
                self.inventory.get("wood", 0) >= HOUSE_WOOD_COST
                and self.inventory.get("stone", 0) >= HOUSE_STONE_COST
            ):
                self.task = "bootstrap_build_house"
                if len(target_pos) == 2:
                    self.task_target = (int(target_pos[0]), int(target_pos[1]))
            if getattr(self, "founder", False):
                self.task_target = self.task_target or (self.x, self.y)
            return

        priority = village.get("priority", "stabilize")
        needs = village.get("needs", {})
        scarcity_pressure = {}
        if hasattr(world, "compute_local_food_pressure_for_agent"):
            try:
                scarcity_pressure = world.compute_local_food_pressure_for_agent(self, max_distance=10)
            except Exception:
                scarcity_pressure = {}
        severe_local_scarcity = bool(
            isinstance(scarcity_pressure, dict)
            and bool(scarcity_pressure.get("pressure_active", False))
            and int(scarcity_pressure.get("near_food_sources", 0)) <= 0
            and int(scarcity_pressure.get("camp_food", 0)) <= 1
            and int(scarcity_pressure.get("house_food_nearby", 0)) <= 1
            and float(getattr(self, "hunger", 100.0)) <= 58.0
            and int(getattr(self, "inventory", {}).get("food", 0)) <= 0
        )
        if str(role) != "leader" and severe_local_scarcity:
            self.task = "gather_food_wild"
            scarcity_target = None
            if hasattr(world, "find_scarcity_adaptive_food_target"):
                try:
                    scarcity_target = world.find_scarcity_adaptive_food_target(
                        self,
                        radius=max(14, int(self.visual_radius_tiles) + 8),
                    )
                except Exception:
                    scarcity_target = None
            elif hasattr(world, "_find_nearest_food_to"):
                try:
                    scarcity_target = world._find_nearest_food_to(int(self.x), int(self.y), radius=max(14, int(self.visual_radius_tiles) + 8))
                except Exception:
                    scarcity_target = None
            if isinstance(scarcity_target, tuple) and len(scarcity_target) == 2:
                self.task_target = (int(scarcity_target[0]), int(scarcity_target[1]))
                self.foraging_target_set_tick = int(tick_now)
            if hasattr(world, "record_settlement_progression_metric"):
                world.record_settlement_progression_metric("medium_term_food_priority_overrides")
                world.record_settlement_progression_metric("food_scarcity_adaptive_retarget_events")
            return
        if (
            str(role) != "leader"
            and int(getattr(self, "first_food_relief_tick", -1)) >= 0
            and int(getattr(self, "inventory", {}).get("food", 0)) <= 0
            and float(getattr(self, "hunger", 100.0)) <= float(max(30.0, MEDIUM_TERM_FOOD_CONTINUITY_HUNGER_THRESHOLD - 4.0))
            and (
                int(getattr(self, "high_hunger_enter_tick", -1)) >= 0
                or int(getattr(self, "high_hunger_episode_count", 0)) >= 2
            )
        ):
            self.task = "gather_food_wild"
            nearest_food = None
            if hasattr(world, "find_scarcity_adaptive_food_target"):
                try:
                    nearest_food = world.find_scarcity_adaptive_food_target(
                        self,
                        radius=max(14, int(self.visual_radius_tiles) + 8),
                    )
                except Exception:
                    nearest_food = None
            elif hasattr(world, "_find_nearest_food_to"):
                try:
                    nearest_food = world._find_nearest_food_to(int(self.x), int(self.y), radius=max(14, int(self.visual_radius_tiles) + 8))
                except Exception:
                    nearest_food = None
            if isinstance(nearest_food, tuple) and len(nearest_food) == 2:
                self.task_target = (int(nearest_food[0]), int(nearest_food[1]))
                self.foraging_target_set_tick = int(tick_now)
            if hasattr(world, "record_settlement_progression_metric"):
                world.record_settlement_progression_metric("medium_term_food_priority_overrides")
            return

        def _survival_crisis() -> bool:
            return float(getattr(self, "hunger", 0.0)) <= 18.0

        def _maybe_apply_rest_bias() -> bool:
            under_pressure = bool(
                float(getattr(self, "sleep_need", 0.0)) >= float(HIGH_SLEEP_NEED_THRESHOLD)
                or float(getattr(self, "fatigue", 0.0)) >= float(HIGH_FATIGUE_THRESHOLD)
                or float(getattr(self, "happiness", 50.0)) <= 32.0
            )
            if not under_pressure:
                return False
            has_home = bool(self._has_valid_home(world))
            has_camp = bool((not has_home) and hasattr(world, "nearest_active_camp_for_agent") and world.nearest_active_camp_for_agent(self, max_distance=12) is not None)
            hunger_gate = 25.0 if has_home else (22.0 if has_camp else 25.0)
            if float(getattr(self, "hunger", 100.0)) < hunger_gate:
                return False
            cadence = 2 if (has_home or has_camp) else 3
            if float(getattr(self, "happiness", 50.0)) <= 32.0:
                cadence = max(1, cadence - 1)
            if int(getattr(world, "tick", 0)) % max(1, cadence) != 0:
                return False
            self.task = "rest"
            if hasattr(world, "record_recovery_stage"):
                world.record_recovery_stage(self, "rest_task_selected")
            return True

        def _has_village_construction_pressure() -> bool:
            vid = village.get("id")
            vuid = village.get("village_uid")
            for b in getattr(world, "buildings", {}).values():
                if not isinstance(b, dict):
                    continue
                b_vid = b.get("village_id")
                b_vuid = b.get("village_uid")
                if vid is not None and b_vid != vid and (vuid is None or b_vuid != vuid):
                    continue
                if str(b.get("operational_state", "")) != "under_construction":
                    continue
                return True
            return False

        def _is_task_still_viable_for_role(role_name: str, task_name: str) -> bool:
            if role_name == "farmer":
                if task_name != "farm_cycle":
                    return False
                return bool(hasattr(world, "is_farmer_task_viable") and world.is_farmer_task_viable(self))
            if role_name == "builder":
                if task_name == "build_storage":
                    keep_for_active_storage = False
                    if hasattr(world, "has_active_storage_construction_for_agent"):
                        try:
                            keep_for_active_storage = bool(world.has_active_storage_construction_for_agent(self))
                        except Exception:
                            keep_for_active_storage = False
                    return bool(
                        priority == "build_storage"
                        or needs.get("need_storage")
                        or _has_village_construction_pressure()
                        or keep_for_active_storage
                    )
                if task_name == "build_house":
                    return bool(priority == "build_housing" or needs.get("need_housing") or _has_village_construction_pressure())
                if task_name == "gather_materials":
                    return bool(
                        needs.get("need_materials")
                        or _has_village_construction_pressure()
                        or priority in {"build_storage", "build_housing", "improve_logistics"}
                    )
                return False
            if role_name == "hauler":
                if task_name not in {"food_logistics", "village_logistics"}:
                    return False
                storage = village.get("storage", {}) if isinstance(village.get("storage"), dict) else {}
                pop = max(1, int(village.get("population", 1)))
                low_food = int(storage.get("food", 0)) <= max(2, pop // 2)
                return bool(
                    _has_village_construction_pressure()
                    or needs.get("need_storage")
                    or needs.get("need_materials")
                    or low_food
                    or self.inventory_load() > 0
                    or priority == "secure_food"
                )
            return False

        def _try_keep_role_task(role_name: str) -> bool:
            if role_name not in ROLE_TASK_PERSISTENCE_TICKS:
                return False
            if _survival_crisis():
                return False
            if not prev_task:
                return False
            if str(getattr(self, "role_task_persisted_task", "")) != prev_task:
                return False
            recent_events = get_recent_memory_events(self, limit=8)
            recent_success = any(
                isinstance(ev, dict)
                and str(ev.get("outcome", "")) == "success"
                and str(ev.get("type", "")) in {"farm_work", "farm_harvest", "hunger_relief", "construction_progress", "delivered_material", "found_resource"}
                for ev in recent_events
            )
            recent_failure = any(
                isinstance(ev, dict)
                and str(ev.get("outcome", "")) == "failure"
                and str(ev.get("type", "")) in {"failed_resource_search", "construction_blocked"}
                for ev in recent_events
            )
            if int(getattr(world, "tick", 0)) > int(getattr(self, "role_task_persistence_until_tick", -1)):
                if hasattr(world, "record_settlement_progression_metric"):
                    if recent_success:
                        world.record_settlement_progression_metric("routine_abandonment_after_success")
                    elif recent_failure:
                        world.record_settlement_progression_metric("routine_abandonment_after_failure")
                return False
            if not _is_task_still_viable_for_role(role_name, prev_task):
                if hasattr(world, "record_settlement_progression_metric"):
                    if recent_success:
                        world.record_settlement_progression_metric("routine_abandonment_after_success")
                    elif recent_failure:
                        world.record_settlement_progression_metric("routine_abandonment_after_failure")
                return False
            self.task = prev_task
            if hasattr(world, "record_settlement_progression_metric"):
                world.record_settlement_progression_metric("routine_persistence_ticks")
                if recent_success:
                    world.record_settlement_progression_metric("repeated_successful_loop_count")
                    self.role_task_persistence_until_tick = max(
                        int(self.role_task_persistence_until_tick),
                        int(getattr(world, "tick", 0)) + int(ROUTINE_SUCCESS_EXTENSION_TICKS),
                    )
            if role_name == "builder" and str(prev_task) == "build_storage" and hasattr(world, "record_settlement_progression_metric"):
                world.record_settlement_progression_metric("storage_builder_commitment_retained_ticks")
            return True

        def _stamp_task_persistence(role_name: str, task_name: str) -> None:
            duration = int(ROLE_TASK_PERSISTENCE_TICKS.get(role_name, 0))
            if role_name == "farmer" and hasattr(world, "farm_task_continuity_bonus"):
                try:
                    duration += int(world.farm_task_continuity_bonus(self, task_name))
                except Exception:
                    pass
            if role_name == "builder" and hasattr(world, "secondary_nucleus_builder_continuity_bonus"):
                try:
                    duration += int(world.secondary_nucleus_builder_continuity_bonus(self, task_name, record_event=True))
                except Exception:
                    pass
            if role_name == "builder" and hasattr(world, "storage_builder_continuity_bonus"):
                try:
                    duration += int(world.storage_builder_continuity_bonus(self, task_name))
                except Exception:
                    pass
            if duration <= 0:
                self.role_task_persisted_task = None
                self.role_task_persistence_until_tick = -1
                return
            self.role_task_persisted_task = str(task_name)
            self.role_task_persistence_until_tick = int(getattr(world, "tick", 0)) + duration

        if role == "farmer":
            if _maybe_apply_rest_bias():
                return
            if _try_keep_role_task("farmer"):
                return
            if hasattr(world, "is_farmer_task_viable") and not bool(world.is_farmer_task_viable(self)):
                self.task = "gather_food_wild"
            else:
                self.task = "farm_cycle"
                _stamp_task_persistence("farmer", self.task)
            return

        if role == "miner":
            if _maybe_apply_rest_bias():
                return
            self.task = "mine_cycle"
            return

        if role == "woodcutter":
            if _maybe_apply_rest_bias():
                return
            self.task = "lumber_cycle"
            return

        if role in {"builder", "hauler"} and hasattr(world, "has_proto_asset_work_for_agent"):
            try:
                known_inventions = (ensure_agent_knowledge_state(self).get("known_inventions", []) if hasattr(self, "knowledge_state") else [])
                has_invention_signal = any(
                    isinstance(e, dict)
                    and str(e.get("usefulness_status", "")) == "useful"
                    and float(e.get("confidence", 0.0)) >= 0.45
                    for e in (known_inventions if isinstance(known_inventions, list) else [])
                )
                current_proposal = getattr(self, "current_innovation_proposal", {})
                owns_current = (
                    isinstance(current_proposal, dict)
                    and str(current_proposal.get("inventor_agent_id", "")) == str(getattr(self, "agent_id", ""))
                )
                if bool(world.has_proto_asset_work_for_agent(self)) and (has_invention_signal or owns_current):
                    self.task = "prototype_attempt"
                    return
            except Exception:
                pass

        if role == "builder":
            if _maybe_apply_rest_bias():
                self._pause_primary_construction_commitment(world, "needs_rest")
                return
            committed_site = self._construction_commitment_site(world)
            if isinstance(committed_site, dict):
                if str(committed_site.get("operational_state", "")) == "under_construction" and not _survival_crisis():
                    self._set_primary_construction_commitment(world, committed_site, reason="commitment_resume")
                    stype = str(committed_site.get("type", ""))
                    if stype == "storage":
                        self.task = "build_storage"
                        _stamp_task_persistence("builder", self.task)
                        return
                    if stype == "house":
                        self.task = "build_house"
                        _stamp_task_persistence("builder", self.task)
                        return
            if not isinstance(committed_site, dict):
                preferred_type = "storage" if (priority == "build_storage" or needs.get("need_storage")) else None
                candidate_site = self._nearest_village_construction_site(world, preferred_type=preferred_type)
                if isinstance(candidate_site, dict):
                    self._set_primary_construction_commitment(world, candidate_site, reason="site_scoped_assignment")
                    try:
                        self.assigned_building_id = str(candidate_site.get("building_id", "") or "")
                    except Exception:
                        pass
                    ctype = str(candidate_site.get("type", ""))
                    if ctype == "storage":
                        if str(prev_task) == "build_storage" and hasattr(world, "record_settlement_progression_metric"):
                            world.record_settlement_progression_metric("storage_builder_commitment_retained_ticks")
                        self.task = "build_storage"
                        _stamp_task_persistence("builder", self.task)
                        return
                    if ctype == "house":
                        self.task = "build_house"
                        _stamp_task_persistence("builder", self.task)
                        return
            sticky_site = self._assigned_construction_site(world)
            if self._should_hold_construction_site_commitment(world, sticky_site):
                if isinstance(sticky_site, dict):
                    self._set_primary_construction_commitment(world, sticky_site, reason="site_sticky")
                site_type = str((sticky_site or {}).get("type", ""))
                if site_type == "storage":
                    self.task = "build_storage"
                elif site_type == "house":
                    self.task = "build_house"
                if str(getattr(self, "task", "")) in {"build_storage", "build_house"}:
                    _stamp_task_persistence("builder", self.task)
                    return
            if _try_keep_role_task("builder"):
                return
            if priority == "build_storage" or needs.get("need_storage"):
                self.task = "build_storage"
            elif priority == "build_housing" or needs.get("need_housing"):
                self.task = "build_house"
            elif priority == "improve_logistics" or needs.get("need_roads"):
                self.task = "build_road"
            else:
                self.task = "gather_materials"
            _stamp_task_persistence("builder", self.task)
            return

        if role == "hauler":
            if _maybe_apply_rest_bias():
                return
            if _try_keep_role_task("hauler"):
                return
            if priority == "secure_food":
                self.task = "food_logistics"
            else:
                self.task = "village_logistics"
            _stamp_task_persistence("hauler", self.task)
            return

        if role == "forager":
            if _maybe_apply_rest_bias():
                return
            if int(self.inventory.get("food", 0)) > 0 and hasattr(world, "compute_local_food_pressure_for_agent"):
                pressure = world.compute_local_food_pressure_for_agent(self)
                if isinstance(pressure, dict) and bool(pressure.get("pressure_active", False)):
                    if hasattr(world, "record_settlement_progression_metric"):
                        world.record_settlement_progression_metric("reserve_final_tiebreak_invoked_count")
                    reserve_win, reserve_reason = self._reserve_vs_group_tiebreak_decision(world, pressure)
                    if hasattr(world, "record_settlement_progression_metric"):
                        if reserve_win:
                            world.record_settlement_progression_metric("reserve_final_tiebreak_won_count")
                        else:
                            world.record_settlement_progression_metric("reserve_final_tiebreak_lost_count")
                            if reserve_reason == "blocked_pressure":
                                world.record_settlement_progression_metric("reserve_final_tiebreak_blocked_by_pressure_count")
                            elif reserve_reason == "blocked_unstable_context":
                                world.record_settlement_progression_metric("reserve_final_tiebreak_blocked_by_unstable_context_count")
                            elif reserve_reason == "blocked_no_surplus":
                                world.record_settlement_progression_metric("reserve_final_tiebreak_blocked_by_no_surplus_count")
                    self.task = "food_logistics" if reserve_win else "camp_supply_food"
                    if (not reserve_win) and hasattr(world, "record_pressure_backed_loop_selected"):
                        world.record_pressure_backed_loop_selected()
                    return
            self.task = "gather_food_wild"
            return

        self.task = "survive"
        if role in {"farmer", "forager", "hauler", "builder", "miner", "woodcutter"} and hasattr(world, "record_assignment_pipeline_block_reason"):
            world.record_assignment_pipeline_block_reason(self, role, "survival_override")

    def update_village_affiliation(self, world: "World") -> None:
        max_entries = 8
        nearby_radius = 12
        attached_threshold = 6.0
        transient_threshold = 1.5
        tick_now = int(getattr(world, "tick", 0))

        # Apply bounded decay so affiliations remain adaptive and memory-limited.
        cleaned: Dict[str, Dict[str, float]] = {}
        for uid, score in self.village_affiliation_scores.items():
            if not isinstance(uid, str) or not isinstance(score, dict):
                continue
            next_score = {
                "time_spent": max(0.0, float(score.get("time_spent", 0.0)) * 0.98),
                "work_contribution": max(0.0, float(score.get("work_contribution", 0.0)) * 0.98),
                "structure_usage": max(0.0, float(score.get("structure_usage", 0.0)) * 0.98),
                "social_interactions": max(0.0, float(score.get("social_interactions", 0.0)) * 0.98),
                "gravity_exposure": max(0.0, float(score.get("gravity_exposure", 0.0)) * 0.985),
            }
            total = (
                next_score["time_spent"]
                + next_score["work_contribution"]
                + next_score["structure_usage"]
                + next_score["social_interactions"]
                + next_score["gravity_exposure"]
            )
            if total >= 0.25:
                cleaned[uid] = next_score
        self.village_affiliation_scores = cleaned

        # Residency is strongest and overrides score-based affiliation.
        if self.home_building_id is not None:
            home = getattr(world, "buildings", {}).get(str(self.home_building_id))
            if isinstance(home, dict) and str(home.get("type", "")) == "house":
                home_uid = home.get("village_uid")
                if home_uid is None:
                    vid = home.get("village_id")
                    home_uid = world.resolve_village_uid(vid) if vid is not None else None
                if home_uid is not None:
                    uid = str(home_uid)
                    center_village = next(
                        (
                            v for v in getattr(world, "villages", [])
                            if isinstance(v, dict) and str(v.get("village_uid", "")) == uid
                        ),
                        None,
                    )
                    if isinstance(center_village, dict):
                        c = center_village.get("center", {}) if isinstance(center_village.get("center"), dict) else {}
                        drift = abs(int(self.x) - int(c.get("x", self.x))) + abs(int(self.y) - int(c.get("y", self.y)))
                        if (
                            drift > int(RESIDENCE_RELEASE_MAX_DRIFT)
                            and tick_now > int(self.residence_persistence_until_tick)
                            and int(getattr(self, "hunger", 100)) >= 25
                        ):
                            if hasattr(world, "record_resident_release"):
                                world.record_resident_release("extreme_drift", village_uid=uid)
                            self.home_building_id = None
                            self.home_village_uid = None
                            self.residence_persistence_until_tick = -1
                            # Continue with normal affiliation fallback below.
                        else:
                            self.home_village_uid = uid
                            self.primary_village_uid = uid
                            self.village_affiliation_status = "resident"
                            self.residence_persistence_until_tick = max(
                                int(self.residence_persistence_until_tick),
                                tick_now + int(RESIDENCE_PERSISTENCE_TICKS),
                            )
                            if hasattr(world, "record_resident_persistence"):
                                world.record_resident_persistence(village_uid=uid)
                            return
                    else:
                        # Home still valid but village currently absent: keep resident for persistence window.
                        self.home_village_uid = uid
                        self.primary_village_uid = uid
                        self.village_affiliation_status = "resident"
                        self.residence_persistence_until_tick = max(
                            int(self.residence_persistence_until_tick),
                            tick_now + int(RESIDENCE_PERSISTENCE_TICKS),
                        )
                        if hasattr(world, "record_resident_persistence"):
                            world.record_resident_persistence(village_uid=uid)
                        return
            prior_uid = str(self.home_village_uid or self.primary_village_uid or "")
            if prior_uid and tick_now <= int(self.residence_persistence_until_tick):
                self.home_building_id = None
                self.home_village_uid = prior_uid
                self.primary_village_uid = prior_uid
                self.village_affiliation_status = "resident"
                if hasattr(world, "record_resident_persistence"):
                    world.record_resident_persistence(village_uid=prior_uid)
                return
            else:
                if prior_uid and hasattr(world, "record_resident_release"):
                    world.record_resident_release("house_missing_or_inactive", village_uid=prior_uid)
                self.home_building_id = None
                self.home_village_uid = None
                if self.village_affiliation_status == "resident":
                    self.village_affiliation_status = "transient"
                self.residence_persistence_until_tick = -1

        if (
            self.home_building_id is None
            and str(getattr(self, "village_affiliation_status", "")) == "resident"
            and isinstance(self.home_village_uid, str)
            and self.home_village_uid
            and tick_now > int(self.residence_persistence_until_tick)
        ):
            if hasattr(world, "record_resident_release"):
                world.record_resident_release("persistence_window_expired", village_uid=str(self.home_village_uid))
            self.home_village_uid = None
            if self.primary_village_uid is None:
                self.village_affiliation_status = "unaffiliated"
            else:
                self.village_affiliation_status = "transient"

        local_candidates: List[Dict[str, Any]] = []
        for village in getattr(world, "villages", []):
            if not isinstance(village, dict):
                continue
            center = village.get("center", {})
            if not isinstance(center, dict):
                continue
            vx = int(center.get("x", 0))
            vy = int(center.get("y", 0))
            if abs(vx - int(self.x)) + abs(vy - int(self.y)) <= nearby_radius:
                local_candidates.append(village)

        relevant_uids = set(self.village_affiliation_scores.keys())
        if isinstance(self.primary_village_uid, str):
            relevant_uids.add(self.primary_village_uid)
        for village in local_candidates:
            vuid = village.get("village_uid")
            if vuid is not None:
                relevant_uids.add(str(vuid))

        work_tasks = {
            "farm_cycle",
            "mine_cycle",
            "lumber_cycle",
            "build_storage",
            "build_house",
            "build_road",
            "gather_materials",
            "food_logistics",
            "village_logistics",
            "prototype_attempt",
        }

        for village in local_candidates:
            uid_raw = village.get("village_uid")
            if uid_raw is None:
                continue
            uid = str(uid_raw)
            v_storage = village.get("storage", {}) if isinstance(village.get("storage"), dict) else {}
            food_stock = max(0, int(v_storage.get("food", 0)))
            wood_stock = max(0, int(v_storage.get("wood", 0)))
            stone_stock = max(0, int(v_storage.get("stone", 0)))
            houses = max(0, int(village.get("houses", 0)))
            population = max(0, int(village.get("population", 0)))
            storage_signal = min(2.0, float(food_stock + wood_stock + stone_stock) / 30.0)
            social_density = 0.0
            center = village.get("center", {}) if isinstance(village.get("center"), dict) else {}
            cx = int(center.get("x", 0))
            cy = int(center.get("y", 0))
            local_social_count = 0
            for other in getattr(world, "agents", []):
                if not getattr(other, "alive", False):
                    continue
                ovuid = getattr(other, "primary_village_uid", None)
                if ovuid is None:
                    ovid = getattr(other, "village_id", None)
                    ovuid = world.resolve_village_uid(ovid)
                if str(ovuid or "") != uid:
                    continue
                if abs(int(getattr(other, "x", 0)) - cx) + abs(int(getattr(other, "y", 0)) - cy) <= nearby_radius:
                    local_social_count += 1
            social_density = min(2.5, float(local_social_count) * 0.2)
            gravity = (
                0.4
                + min(2.0, float(houses) * 0.25)
                + min(1.5, float(population) * 0.08)
                + storage_signal
                + social_density
            )
            if str(getattr(self, "primary_village_uid", "") or "") == uid:
                gravity += 0.6
            score = self.village_affiliation_scores.setdefault(
                uid,
                {
                    "time_spent": 0.0,
                    "work_contribution": 0.0,
                    "structure_usage": 0.0,
                    "social_interactions": 0.0,
                    "gravity_exposure": 0.0,
                },
            )
            score["time_spent"] = float(score.get("time_spent", 0.0)) + (1.0 + min(0.75, gravity * 0.08))
            score["gravity_exposure"] = float(score.get("gravity_exposure", 0.0)) + min(1.0, gravity * 0.12)

            if str(getattr(self, "task", "")) in work_tasks:
                score["work_contribution"] = float(score.get("work_contribution", 0.0)) + (1.0 + min(0.4, gravity * 0.05))

            # Structure usage remains local: count only nearby structures from this village.
            nearby_structure = False
            for building in getattr(world, "buildings", {}).values():
                if not isinstance(building, dict):
                    continue
                buid = building.get("village_uid")
                if buid is None and building.get("village_id") is not None:
                    buid = world.resolve_village_uid(building.get("village_id"))
                if str(buid or "") != uid:
                    continue
                if abs(int(building.get("x", 0)) - int(self.x)) + abs(int(building.get("y", 0)) - int(self.y)) <= 2:
                    nearby_structure = True
                    break
            if nearby_structure:
                score["structure_usage"] = float(score.get("structure_usage", 0.0)) + 1.0

            social_hits = 0
            for other in getattr(world, "agents", []):
                if other is self or not getattr(other, "alive", False):
                    continue
                if abs(int(getattr(other, "x", 0)) - int(self.x)) + abs(int(getattr(other, "y", 0)) - int(self.y)) > int(self.social_radius_tiles):
                    continue
                ovuid = getattr(other, "primary_village_uid", None)
                if ovuid is None:
                    ovid = getattr(other, "village_id", None)
                    ovuid = world.resolve_village_uid(ovid)
                if str(ovuid or "") == uid:
                    social_hits += 1
            if social_hits > 0:
                score["social_interactions"] = float(score.get("social_interactions", 0.0)) + float(social_hits) * (1.0 + min(0.25, gravity * 0.03))

        ranked: List[Tuple[float, str]] = []
        for uid in sorted(relevant_uids):
            score = self.village_affiliation_scores.get(uid)
            if not isinstance(score, dict):
                continue
            total = (
                float(score.get("time_spent", 0.0))
                + 1.5 * float(score.get("work_contribution", 0.0))
                + float(score.get("structure_usage", 0.0))
                + 0.5 * float(score.get("social_interactions", 0.0))
                + 0.8 * float(score.get("gravity_exposure", 0.0))
            )
            ranked.append((total, uid))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        if len(ranked) > max_entries:
            keep = {uid for _, uid in ranked[:max_entries]}
            self.village_affiliation_scores = {
                uid: self.village_affiliation_scores[uid]
                for uid in sorted(keep)
                if uid in self.village_affiliation_scores
            }
            ranked = ranked[:max_entries]

        if not ranked:
            if (
                str(getattr(self, "village_affiliation_status", "")) == "resident"
                and isinstance(self.home_village_uid, str)
                and self.home_village_uid
                and tick_now <= int(self.residence_persistence_until_tick)
            ):
                self.primary_village_uid = str(self.home_village_uid)
                if hasattr(world, "record_resident_persistence"):
                    world.record_resident_persistence(village_uid=str(self.home_village_uid))
                return
            self.primary_village_uid = None
            self.village_affiliation_status = "unaffiliated"
            return

        best_score, best_uid = ranked[0]
        best_score_map = self.village_affiliation_scores.get(best_uid, {})
        gravity_exposure = float(best_score_map.get("gravity_exposure", 0.0)) if isinstance(best_score_map, dict) else 0.0
        dynamic_attached_threshold = max(4.5, float(attached_threshold) - min(1.25, gravity_exposure * 0.35))
        dynamic_transient_threshold = max(1.2, float(transient_threshold) - min(0.25, gravity_exposure * 0.08))
        if best_score >= dynamic_attached_threshold:
            self.primary_village_uid = best_uid
            self.village_affiliation_status = "attached"
        elif best_score >= dynamic_transient_threshold:
            self.primary_village_uid = best_uid
            self.village_affiliation_status = "transient"
        else:
            self.primary_village_uid = None
            self.village_affiliation_status = "unaffiliated"

        # Bounded residence stabilization: allow strongly affiliated agents to fill empty houses.
        if self.home_building_id is None and self.village_affiliation_status in {"attached", "transient"} and isinstance(self.primary_village_uid, str):
            target_uid = str(self.primary_village_uid)
            if hasattr(world, "record_resident_conversion_gate_stage"):
                world.record_resident_conversion_gate_stage("conversion_context_seen", village_uid=target_uid)
            if hasattr(world, "record_resident_conversion_gate_stage"):
                world.record_resident_conversion_gate_stage("candidate_house_search_started", village_uid=target_uid)

            structure_usage = float(best_score_map.get("structure_usage", 0.0)) if isinstance(best_score_map, dict) else 0.0
            time_spent = float(best_score_map.get("time_spent", 0.0)) if isinstance(best_score_map, dict) else 0.0
            social_interactions = float(best_score_map.get("social_interactions", 0.0)) if isinstance(best_score_map, dict) else 0.0
            strong_local_affiliation = bool(
                best_score >= (dynamic_attached_threshold + 0.15)
                and gravity_exposure >= 1.1
                and (time_spent >= 4.0 or structure_usage >= 1.5 or social_interactions >= 2.0)
            )
            if strong_local_affiliation:
                if hasattr(world, "record_resident_conversion_gate_stage"):
                    world.record_resident_conversion_gate_stage("strong_affiliation_seen", village_uid=target_uid)
            elif hasattr(world, "record_resident_conversion_gate_failure"):
                world.record_resident_conversion_gate_failure("affiliation_not_strong_enough", village_uid=target_uid)

            candidate_houses = []
            occupied = set()
            houses_anywhere = False
            any_target_house = False
            any_target_active_house = False
            any_target_empty_house = False
            any_target_within_radius = False
            for other in getattr(world, "agents", []):
                if not getattr(other, "alive", False):
                    continue
                hb = getattr(other, "home_building_id", None)
                if hb is not None:
                    occupied.add(str(hb))
            for building in getattr(world, "buildings", {}).values():
                if not isinstance(building, dict):
                    continue
                if str(building.get("type", "")) != "house":
                    continue
                houses_anywhere = True
                buid = self._resolve_building_village_uid(world, building)
                if buid != target_uid:
                    continue
                any_target_house = True
                if not self._is_house_claimably_active(building):
                    if hasattr(world, "record_resident_conversion_gate_failure"):
                        world.record_resident_conversion_gate_failure("house_inactive", village_uid=target_uid)
                    continue
                any_target_active_house = True
                if hasattr(world, "record_resident_conversion_gate_stage"):
                    world.record_resident_conversion_gate_stage("candidate_house_found", village_uid=target_uid)
                    world.record_resident_conversion_gate_stage("candidate_house_active", village_uid=target_uid)
                bid = str(building.get("building_id", ""))
                if bid in occupied:
                    if hasattr(world, "record_resident_conversion_gate_failure"):
                        world.record_resident_conversion_gate_failure("house_not_empty", village_uid=target_uid)
                        world.record_resident_conversion_gate_failure("house_already_reserved", village_uid=target_uid)
                    continue
                any_target_empty_house = True
                if hasattr(world, "record_resident_conversion_gate_stage"):
                    world.record_resident_conversion_gate_stage("candidate_house_empty", village_uid=target_uid)
                dist = abs(int(building.get("x", 0)) - int(self.x)) + abs(int(building.get("y", 0)) - int(self.y))
                if dist > nearby_radius:
                    if hasattr(world, "record_resident_conversion_gate_failure"):
                        world.record_resident_conversion_gate_failure("outside_claim_radius", village_uid=target_uid)
                    continue
                any_target_within_radius = True
                if hasattr(world, "record_resident_conversion_gate_stage"):
                    world.record_resident_conversion_gate_stage("within_claim_radius", village_uid=target_uid)
                candidate_houses.append((dist, bid))

            if not any_target_house:
                if houses_anywhere and hasattr(world, "record_resident_conversion_gate_failure"):
                    world.record_resident_conversion_gate_failure("village_mismatch", village_uid=target_uid)
                elif hasattr(world, "record_resident_conversion_gate_failure"):
                    world.record_resident_conversion_gate_failure("no_candidate_house", village_uid=target_uid)
            elif any_target_active_house and not any_target_empty_house and hasattr(world, "record_resident_conversion_gate_failure"):
                world.record_resident_conversion_gate_failure("house_not_empty", village_uid=target_uid)
            elif any_target_empty_house and not any_target_within_radius and hasattr(world, "record_resident_conversion_gate_failure"):
                world.record_resident_conversion_gate_failure("outside_claim_radius", village_uid=target_uid)
            if candidate_houses:
                if hasattr(world, "record_resident_conversion_attempt"):
                    world.record_resident_conversion_attempt(village_uid=target_uid)
                eligible = bool(strong_local_affiliation and int(getattr(self, "hunger", 100)) >= 20)
                if eligible and hasattr(world, "record_resident_conversion_gate_stage"):
                    world.record_resident_conversion_gate_stage("conversion_eligibility_passed", village_uid=target_uid)
                elif not eligible and hasattr(world, "record_resident_conversion_gate_failure"):
                    if int(getattr(self, "hunger", 100)) < 20:
                        world.record_resident_conversion_gate_failure("survival_override", village_uid=target_uid)
                    elif not strong_local_affiliation:
                        world.record_resident_conversion_gate_failure("affiliation_not_strong_enough", village_uid=target_uid)
                    else:
                        world.record_resident_conversion_gate_failure("eligibility_failed_other_guard", village_uid=target_uid)
                if eligible:
                    candidate_houses.sort(key=lambda item: (item[0], item[1]))
                    selected_house_id = str(candidate_houses[0][1])
                    self.home_building_id = selected_house_id
                    self.home_village_uid = target_uid
                    self.primary_village_uid = target_uid
                    self.village_affiliation_status = "resident"
                    self.residence_persistence_until_tick = max(
                        int(self.residence_persistence_until_tick),
                        tick_now + int(RESIDENCE_PERSISTENCE_TICKS),
                    )
                    if hasattr(world, "record_resident_conversion_gate_stage"):
                        world.record_resident_conversion_gate_stage("resident_conversion_granted", village_uid=target_uid)
                    if hasattr(world, "record_resident_conversion_gate_failure"):
                        world.record_resident_conversion_gate_failure("conversion_succeeded", village_uid=target_uid)
                    if hasattr(world, "record_resident_conversion"):
                        world.record_resident_conversion(village_uid=target_uid)

    def update_subjective_state(self, world: "World") -> None:
        self.subjective_state = build_agent_perception(world, self)
        if isinstance(self.subjective_state.get("local_signals"), dict):
            self.subjective_state["local_signals"]["survival"] = evaluate_local_survival_pressure(world, self)
        update_agent_social_memory(world, self, self.subjective_state)
        update_agent_knowledge_from_experience(world, self)
        update_agent_invention_knowledge_from_observation(world, self)
        diffuse_local_knowledge(world, self)
        diffuse_invention_knowledge(world, self)
        decay_agent_knowledge_state(world, self)
        update_agent_self_model(world, self)
        update_agent_identity(world, self)
        update_agent_cognitive_profile(world, self)
        self.social_influence = evaluate_agent_social_influence(world, self)
        self.last_social_influence_tick = int(getattr(world, "tick", 0))
        self.subjective_state["self_interpretation"] = interpret_local_signals_with_self_model(world, self)
        self.subjective_state["attention"] = evaluate_agent_salience(world, self)
        _update_short_term_memory(self)

    def run_brain(self, world: "World") -> Tuple[str, ...]:
        if self.brain is None:
            return ("wait",)

        action = self.brain.decide(self, world)

        if not action:
            return ("wait",)

        if isinstance(action, tuple):
            return action

        return ("wait",)

    def eat_if_needed(self, world: "World") -> bool:
        village = world.get_village_by_id(self.village_id)
        trigger = int(EAT_TRIGGER_BASE_THRESHOLD)
        ate = False
        preserve_inventory_food = False
        has_camp_food_nearby = bool(hasattr(world, "camp_has_food_for_agent") and world.camp_has_food_for_agent(self, max_distance=3))
        has_house_food_nearby = bool(hasattr(world, "house_has_food_for_agent") and world.house_has_food_for_agent(self, max_distance=3))
        if has_camp_food_nearby:
            trigger = max(trigger, 54)
        if has_house_food_nearby:
            trigger = max(trigger, 58)

        if village is not None:
            storage = village.get("storage", {})
            pop = max(1, village.get("population", 1))
            food_stock = storage.get("food", 0)
            buffer_target = max(4, pop * 4)
            food_reserve = max(2, pop * 2)
            if food_stock > 0:
                # Village food should protect members earlier, reducing avoidable starvation.
                if food_stock >= pop:
                    trigger = 70
                else:
                    trigger = 62
            if (
                food_stock < buffer_target
                and self.inventory.get("food", 0) > 0
                and getattr(self, "role", "npc") in ("hauler", "farmer")
                and not self._near_storage(village)
            ):
                # Keep carried harvest for deposit when village stock buffer is low.
                preserve_inventory_food = True

        if self.hunger >= trigger:
            return ate

        # Survival-first: if hunger is already critical, consume carried food immediately.
        if self.hunger <= 15 and self.inventory.get("food", 0) > 0:
            self.inventory["food"] -= 1
            self.hunger += FOOD_EAT_GAIN
            if self.hunger > 100:
                self.hunger = 100
            if hasattr(world, "record_food_consumption"):
                world.record_food_consumption("inventory", amount=1, agent=self)
            return True

        if hasattr(world, "consume_food_from_nearby_house"):
            consumed = int(world.consume_food_from_nearby_house(self, amount=1))
            if consumed > 0:
                self.hunger += float(consumed) * float(FOOD_EAT_GAIN)
                if self.hunger > 100:
                    self.hunger = 100
                if hasattr(world, "record_food_consumption"):
                    world.record_food_consumption("domestic", amount=int(consumed), agent=self)
                return True

        if hasattr(world, "consume_food_from_nearby_camp"):
            consumed = int(world.consume_food_from_nearby_camp(self, amount=1))
            if consumed > 0:
                self.hunger += float(consumed) * float(FOOD_EAT_GAIN)
                if self.hunger > 100:
                    self.hunger = 100
                if hasattr(world, "record_food_consumption"):
                    world.record_food_consumption("camp", amount=int(consumed), agent=self)
                return True

        if village is not None:
            storage = village.get("storage", {})
            pop = max(1, village.get("population", 1))
            food_reserve = max(2, pop * 2)
            storage_food = storage.get("food", 0)
            can_use_storage_food = storage_food > food_reserve or self.hunger <= 15
            if storage_food > 0 and can_use_storage_food:
                storage["food"] -= 1
                self.hunger += FOOD_EAT_GAIN
                if self.hunger > 100:
                    self.hunger = 100
                if hasattr(world, "record_food_consumption"):
                    world.record_food_consumption("storage", amount=1, agent=self)
                return True

        if self.inventory.get("food", 0) > 0 and (not preserve_inventory_food or self.hunger <= 15):
            self.inventory["food"] -= 1
            self.hunger += FOOD_EAT_GAIN
            if self.hunger > 100:
                self.hunger = 100
            if hasattr(world, "record_food_consumption"):
                world.record_food_consumption("inventory", amount=1, agent=self)
            ate = True

        return ate

    def try_reproduce(self, world: "World") -> None:
        def _metric(key: str, value: int = 1) -> None:
            if hasattr(world, "record_settlement_progression_metric"):
                world.record_settlement_progression_metric(str(key), int(value))

        def _blocked(reason: str) -> None:
            _metric("reproduction_blocked_count", 1)
            _metric(f"reproduction_{str(reason)}_count", 1)

        def _clear_proto_micro_closure(broken_reason: str = "", context_subreason: str = "") -> None:
            if broken_reason == "survival":
                _metric("stable_proto_micro_proximity_closure_broken_by_survival_count", 1)
            elif broken_reason == "context_loss":
                _metric("stable_proto_micro_proximity_closure_broken_by_context_loss_count", 1)
                if context_subreason:
                    _metric(f"stable_proto_micro_context_loss_{str(context_subreason)}_count", 1)
            self.stable_proto_micro_partner_agent_id = None
            self.stable_proto_micro_until_tick = -1
            self.stable_proto_micro_anchor_village_id = None
            self.stable_proto_micro_invoke_tick = -1
            self.stable_proto_micro_invoke_distance = 0
            self.stable_proto_path_inactivity_hold_until_tick = -1
            self.stable_proto_path_inactivity_hold_anchor_village_id = None
            self.stable_proto_drift_damping_partner_agent_id = None
            self.stable_proto_drift_damping_until_tick = -1
            self.stable_proto_drift_damping_anchor_village_id = None

        def _clear_proto_partner_convergence(broken_reason: str = "") -> None:
            if broken_reason == "survival":
                _metric("stable_proto_partner_convergence_broken_by_survival_count", 1)
            elif broken_reason == "context_loss":
                _metric("stable_proto_partner_convergence_broken_by_context_loss_count", 1)
            self.stable_proto_partner_convergence_agent_id = None
            self.stable_proto_partner_convergence_until_tick = -1
            self.stable_proto_partner_convergence_anchor_village_id = None

        if self.is_player:
            return

        if not getattr(world, "villages", []):
            _blocked("blocked_by_no_formal_village")
            return

        effective_village_id: Optional[int] = self.village_id
        stable_proto_household_path_active = False
        stable_proto_household_center: Optional[Tuple[int, int]] = None
        tick_now = int(getattr(world, "tick", 0))
        convergence_active = bool(
            isinstance(getattr(self, "stable_proto_partner_convergence_agent_id", None), str)
            and int(getattr(self, "stable_proto_partner_convergence_until_tick", -1)) >= int(tick_now)
        )
        if convergence_active:
            survival_unstable = bool(
                float(getattr(self, "hunger", 0.0)) < max(30.0, float(REPRO_MIN_HUNGER) - 20.0)
                or float(getattr(self, "health", 100.0)) < float(LOW_HEALTH_THRESHOLD)
                or float(getattr(self, "sleep_need", 0.0)) >= 85.0
                or float(getattr(self, "fatigue", 0.0)) >= 85.0
            )
            if survival_unstable:
                _clear_proto_partner_convergence("survival")
                convergence_active = False
        micro_closure_active = bool(
            isinstance(getattr(self, "stable_proto_micro_partner_agent_id", None), str)
            and bool(str(getattr(self, "stable_proto_micro_partner_agent_id", "") or ""))
        )
        proto_path_inactivity_hold_active = bool(
            int(getattr(self, "stable_proto_path_inactivity_hold_until_tick", -1)) >= int(tick_now)
        )

        sex_self = str(getattr(self, "biological_sex", "") or "").strip().lower()
        if sex_self not in BIOLOGICAL_SEX_VALUES:
            sex_self = random.choice(BIOLOGICAL_SEX_VALUES)
            self.biological_sex = sex_self

        age_ticks = int(getattr(world, "tick", 0)) - int(getattr(self, "born_tick", 0))
        age_ok = age_ticks >= int(REPRO_MIN_AGE_TICKS)
        if age_ok:
            _metric("agents_above_repro_min_age_count", 1)
        health_ok = float(getattr(self, "health", 100.0)) >= float(LOW_HEALTH_THRESHOLD)
        if health_ok:
            _metric("agents_meeting_health_requirement_for_repro_count", 1)

        if len(world.agents) >= int(MAX_AGENTS * 0.60):
            _blocked("blocked_by_other")
            return

        cooldown_ok = int(self.repro_cooldown) <= 0
        if cooldown_ok:
            _metric("agents_meeting_repro_cooldown_requirement_count", 1)
        if self.repro_cooldown > 0:
            self.repro_cooldown -= 1
            _blocked("blocked_by_cooldown")
            return

        if effective_village_id is None:
            _metric("reproduction_stable_proto_household_path_considered_count", 1)
            _metric("stable_proto_household_path_considered_count", 1)
            candidate: Optional[Dict[str, Any]] = None
            best_dist = 10**9
            proto_all_count = 0
            proto_stage_eligible_count = 0
            proto_within_radius_count = 0
            anchor_reused = False
            tick_now = int(getattr(world, "tick", 0))

            # Step 1: try a short-lived local proto anchor memory to avoid repeatedly
            # failing on recomputation jitter when the local context is still valid.
            anchor_id = getattr(self, "stable_proto_anchor_village_id", None)
            anchor_age_ok = int(tick_now - int(getattr(self, "stable_proto_anchor_tick", -1))) <= int(
                STABLE_PROTO_HOUSEHOLD_ANCHOR_MAX_AGE_TICKS
            )
            if isinstance(anchor_id, int) and anchor_age_ok:
                anchor_v = world.get_village_by_id(anchor_id)
                if isinstance(anchor_v, dict) and not bool(anchor_v.get("formalized", False)):
                    stage = str(anchor_v.get("settlement_stage", "") or "").strip().lower()
                    if stage not in {"abandoned", "ghost", "ghost_village"}:
                        center = anchor_v.get("center", {})
                        vx = int(center.get("x", 0))
                        vy = int(center.get("y", 0))
                        dist = abs(int(self.x) - vx) + abs(int(self.y) - vy)
                        if dist <= int(STABLE_PROTO_HOUSEHOLD_ANCHOR_SEARCH_RADIUS):
                            candidate = anchor_v
                            best_dist = int(dist)
                            anchor_reused = True
                            _metric("stable_proto_household_local_anchor_reused_count", 1)
                if not anchor_reused:
                    self.stable_proto_anchor_village_id = None

            # Step 2: if no reusable anchor, create one from nearest active camp + nearby proto village.
            if candidate is None:
                camp = None
                if hasattr(world, "nearest_active_camp_for_agent"):
                    camp = world.nearest_active_camp_for_agent(self, max_distance=int(STABLE_PROTO_HOUSEHOLD_ANCHOR_SEARCH_RADIUS))
                if isinstance(camp, dict):
                    cx = int(camp.get("x", 0))
                    cy = int(camp.get("y", 0))
                    for v in getattr(world, "villages", []):
                        if not isinstance(v, dict):
                            continue
                        if bool(v.get("formalized", False)):
                            continue
                        stage = str(v.get("settlement_stage", "") or "").strip().lower()
                        if stage in {"abandoned", "ghost", "ghost_village"}:
                            continue
                        center = v.get("center", {})
                        vx = int(center.get("x", 0))
                        vy = int(center.get("y", 0))
                        camp_dist = abs(vx - cx) + abs(vy - cy)
                        if camp_dist > int(STABLE_PROTO_HOUSEHOLD_ANCHOR_CAMP_LINK_RADIUS):
                            continue
                        dist = abs(int(self.x) - vx) + abs(int(self.y) - vy)
                        if dist < best_dist:
                            candidate = v
                            best_dist = int(dist)
                    if isinstance(candidate, dict):
                        self.stable_proto_anchor_village_id = int(candidate.get("id")) if isinstance(candidate.get("id"), int) else None
                        self.stable_proto_anchor_tick = int(tick_now)
                        _metric("stable_proto_household_local_anchor_created_count", 1)

            # Step 3: fallback direct scan (legacy behavior) if anchor path didn't find anything.
            for v in getattr(world, "villages", []):
                if not isinstance(v, dict):
                    continue
                if bool(v.get("formalized", False)):
                    continue
                proto_all_count += 1
                stage = str(v.get("settlement_stage", "") or "").strip().lower()
                if stage in {"abandoned", "ghost", "ghost_village"}:
                    continue
                proto_stage_eligible_count += 1
                center = v.get("center", {})
                vx = int(center.get("x", 0))
                vy = int(center.get("y", 0))
                dist = abs(int(self.x) - vx) + abs(int(self.y) - vy)
                if dist > int(STABLE_PROTO_HOUSEHOLD_RADIUS):
                    continue
                proto_within_radius_count += 1
                if candidate is None and dist < best_dist:
                    candidate = v
                    best_dist = dist
            candidate_local_context_nearby = proto_within_radius_count > 0
            if (not candidate_local_context_nearby) and isinstance(candidate, dict):
                center = candidate.get("center", {})
                cx = int(center.get("x", int(self.x)))
                cy = int(center.get("y", int(self.y)))
                cdist = abs(int(self.x) - cx) + abs(int(self.y) - cy)
                if cdist <= int(STABLE_PROTO_HOUSEHOLD_ANCHOR_SEARCH_RADIUS):
                    candidate_local_context_nearby = True
            if candidate_local_context_nearby:
                _metric("reproduction_stable_proto_household_path_candidate_nearby_count", 1)
                _metric("stable_proto_household_candidate_nearby_count", 1)
            if candidate is None:
                reason_mapped = False
                if proto_all_count <= 0 or proto_stage_eligible_count <= 0:
                    _metric("reproduction_stable_proto_household_path_blocked_by_proto_context_mismatch_count", 1)
                    reason_mapped = True
                elif proto_within_radius_count <= 0:
                    _metric("reproduction_stable_proto_household_path_blocked_by_proto_candidate_too_far_count", 1)
                    _metric("stable_proto_household_candidate_too_far_count", 1)
                    reason_mapped = True
                else:
                    _metric("reproduction_stable_proto_household_path_blocked_by_no_proto_candidate_nearby_count", 1)
                    reason_mapped = True
                _metric("reproduction_stable_proto_household_path_blocked_by_other_count", 1)
                if not reason_mapped:
                    _metric("reproduction_stable_proto_household_path_blocked_by_other_residual_count", 1)
                _metric("stable_proto_household_local_anchor_fail_count", 1)
                _blocked("blocked_by_other")
                return
            if (not anchor_reused) and isinstance(candidate, dict):
                cand_id = candidate.get("id")
                if isinstance(cand_id, int):
                    self.stable_proto_anchor_village_id = cand_id
                    self.stable_proto_anchor_tick = int(tick_now)
                    _metric("stable_proto_household_local_anchor_created_count", 1)

            c_stability = int(candidate.get("stability_ticks", 0))
            c_pop = int(candidate.get("population", 0))
            c_houses = max(0, int(candidate.get("houses", 0)))
            c_storage_food = int(candidate.get("storage", {}).get("food", 0))
            c_center = candidate.get("center", {})
            stable_proto_household_center = (int(c_center.get("x", int(self.x))), int(c_center.get("y", int(self.y))))
            if c_stability < int(STABLE_PROTO_HOUSEHOLD_MIN_STABILITY_TICKS) or c_pop < 4:
                _metric("reproduction_stable_proto_household_path_blocked_by_insufficient_proto_continuity_ticks_count", 1)
                _metric("reproduction_stable_proto_household_path_blocked_by_stability_count", 1)
                _blocked("blocked_by_stability_requirement")
                return
            if c_houses < 2:
                _metric("reproduction_stable_proto_household_path_blocked_by_no_valid_household_or_shelter_match_count", 1)
                _metric("reproduction_stable_proto_household_path_blocked_by_no_household_or_shelter_count", 1)
                _blocked("blocked_by_no_shelter_or_household")
                return

            proto_crisis_block = False
            proto_food_ok = bool(c_storage_food >= max(4, c_pop // 3))
            if hasattr(world, "compute_local_food_pressure_for_agent"):
                pressure = world.compute_local_food_pressure_for_agent(self, max_distance=8)
                if isinstance(pressure, dict):
                    pressure_active = bool(pressure.get("pressure_active", False))
                    unmet_pressure = bool(pressure.get("unmet_pressure", False))
                    near_food_sources = int(pressure.get("near_food_sources", 0))
                    buffered_local_food = int(pressure.get("camp_food", 0)) + int(pressure.get("house_food_nearby", 0))
                    if (not unmet_pressure) and bool(buffered_local_food >= 1 or near_food_sources >= 2):
                        self.repro_proto_food_security_stable_ticks = int(
                            min(120, int(getattr(self, "repro_proto_food_security_stable_ticks", 0)) + 1)
                        )
                    else:
                        self.repro_proto_food_security_stable_ticks = 0
                    proto_food_ok = bool(
                        proto_food_ok
                        or int(getattr(self, "repro_proto_food_security_stable_ticks", 0))
                        >= int(PROTO_REPRO_FOOD_SECURITY_WINDOW_TICKS)
                    )
                    proto_crisis_block = bool(
                        unmet_pressure or (pressure_active and buffered_local_food <= 0 and near_food_sources <= 0)
                    )
            else:
                self.repro_proto_food_security_stable_ticks = 0

            if proto_crisis_block:
                _metric("reproduction_stable_proto_household_path_blocked_by_crisis_count", 1)
                _blocked("blocked_by_other")
                return
            if not proto_food_ok:
                _metric("reproduction_stable_proto_household_path_blocked_by_food_security_count", 1)
                _blocked("blocked_by_low_local_food_security")
                return

            effective_village_id = candidate.get("id")
            stable_proto_household_path_active = True
            _metric("reproduction_stable_proto_household_path_activated_count", 1)

        village = world.get_village_by_id(effective_village_id)
        storage_food = 0
        village_pop = 0
        formalized = False
        shelter_ok = False
        stability_ok = False
        proto_path_active = False
        if not age_ok:
            _blocked("blocked_by_age")
            return
        _metric("reproduction_attempt_count", 1)
        if village is not None:
            storage_food = village.get("storage", {}).get("food", 0)
            village_pop = village.get("population", 0)
            formalized = bool(village.get("formalized", False))
            if formalized:
                _metric("agents_in_formal_village_count", 1)
            stability_ticks = int(village.get("stability_ticks", 0))
            stability_ok = stability_ticks >= 120
            if stability_ok:
                _metric("agents_meeting_stability_requirement_for_repro_count", 1)
            houses = max(0, int(village.get("houses", 0)))
            population_cap = houses * 5
            shelter_ok = bool(houses >= 2 and village_pop >= 3 and village_pop < population_cap)
            if shelter_ok:
                _metric("agents_meeting_household_or_shelter_requirement_count", 1)
            local_food_security_ok_formal = bool(storage_food >= max(4, village_pop // 3))
            local_food_security_ok = local_food_security_ok_formal
            proto_pressure: Dict[str, Any] = {}
            if not formalized:
                _metric("reproduction_proto_path_considered_count", 1)
                proto_stage = str(village.get("settlement_stage", "") or "").strip().lower()
                proto_stability_ok = bool(
                    stability_ticks >= 120
                    and village_pop >= 4
                    and proto_stage not in {"abandoned", "ghost", "ghost_village"}
                )
                if not proto_stability_ok:
                    _metric("reproduction_proto_path_blocked_by_stability_count", 1)
                    _blocked("blocked_by_stability_requirement")
                    return
                _metric("reproduction_proto_path_gate_pass_stability_count", 1)
                crisis_block = False
                if hasattr(world, "compute_local_food_pressure_for_agent"):
                    pressure = world.compute_local_food_pressure_for_agent(self, max_distance=8)
                    if isinstance(pressure, dict):
                        proto_pressure = pressure
                        pressure_active = bool(pressure.get("pressure_active", False))
                        near_food_sources = int(pressure.get("near_food_sources", 0))
                        camp_food = int(pressure.get("camp_food", 0))
                        house_food_nearby = int(pressure.get("house_food_nearby", 0))
                        buffered_local_food = max(0, camp_food + house_food_nearby)
                        unmet_pressure = bool(pressure.get("unmet_pressure", False))
                        proto_food_signal_ok = bool(
                            local_food_security_ok_formal
                            or (buffered_local_food >= 2 and not unmet_pressure)
                            or (buffered_local_food >= 1 and near_food_sources >= 2 and not unmet_pressure)
                        )
                        if bool(buffered_local_food >= 1 or near_food_sources >= 2):
                            _metric("proto_food_security_window_recent_buffer_ok_count", 1)
                        if not unmet_pressure:
                            _metric("proto_food_security_window_recent_pressure_clear_count", 1)
                        if (not unmet_pressure) and bool(buffered_local_food >= 1 or near_food_sources >= 2):
                            self.repro_proto_food_security_stable_ticks = int(
                                min(120, int(getattr(self, "repro_proto_food_security_stable_ticks", 0)) + 1)
                            )
                        else:
                            self.repro_proto_food_security_stable_ticks = 0
                        local_food_security_ok = bool(
                            local_food_security_ok_formal
                            or int(getattr(self, "repro_proto_food_security_stable_ticks", 0)) >= int(PROTO_REPRO_FOOD_SECURITY_WINDOW_TICKS)
                        )
                        crisis_block = bool(
                            unmet_pressure
                            or (pressure_active and buffered_local_food <= 0 and near_food_sources <= 0)
                        )
                else:
                    self.repro_proto_food_security_stable_ticks = 0
                if crisis_block:
                    _metric("reproduction_proto_path_blocked_by_other_count", 1)
                    _blocked("blocked_by_other")
                    return
                _metric("reproduction_proto_path_gate_pass_crisis_count", 1)
                if not shelter_ok:
                    _metric("reproduction_proto_path_blocked_by_no_shelter_count", 1)
                    _blocked("blocked_by_no_shelter_or_household")
                    return
                if not local_food_security_ok:
                    _metric("proto_food_security_window_fail_count", 1)
                    _metric("reproduction_proto_path_blocked_by_food_security_count", 1)
                    _blocked("blocked_by_low_local_food_security")
                    return
                _metric("proto_food_security_window_pass_count", 1)
                _metric("reproduction_proto_path_gate_pass_food_security_count", 1)
                proto_path_active = True
                _metric("reproduction_proto_path_activated_count", 1)
            else:
                self.repro_proto_food_security_stable_ticks = 0
                if village_pop >= population_cap:
                    _blocked("blocked_by_no_shelter_or_household")
                    return
                if houses < 2 or village_pop < 3:
                    _blocked("blocked_by_no_shelter_or_household")
                    return
                local_food_security_ok = bool(local_food_security_ok_formal)
            if local_food_security_ok:
                _metric("agents_meeting_local_food_security_requirement_count", 1)
        else:
            _blocked("blocked_by_no_formal_village")
            return

        if convergence_active and not stable_proto_household_path_active:
            _clear_proto_partner_convergence("context_loss")
            convergence_active = False
        nearby_partners = 0
        opposite_sex_partners = 0
        opposite_sex_age_ok = 0
        opposite_sex_ready_partner: Optional["Agent"] = None
        anchor_partner_candidate_count = 0
        anchor_partner_nearby_count = 0
        anchor_partner_too_far_count = 0
        anchor_partner_context_mismatch_count = 0
        anchor_partner_blocked_health_or_hunger_count = 0
        anchor_partner_blocked_cooldown_count = 0
        anchor_nearest_partner_far_dist = 10**9
        anchor_nearest_partner_far_pos: Optional[Tuple[int, int]] = None
        anchor_nearest_age_ok_far_dist = 10**9
        anchor_nearest_age_ok_far_pos: Optional[Tuple[int, int]] = None
        anchor_nearest_age_ok_far_id: Optional[str] = None
        anchor_nearest_micro_age_ok_dist = 10**9
        anchor_nearest_micro_age_ok_id: Optional[str] = None
        anchor_nearest_micro_age_ok_agent: Optional["Agent"] = None
        anchor_nearest_valid_partner_far_dist = 10**9
        anchor_nearest_valid_partner_far_pos: Optional[Tuple[int, int]] = None
        anchor_nearest_valid_partner_far_id: Optional[str] = None
        anchor_opposite_sex_copresent_count = 0
        for other in getattr(world, "agents", []):
            if other is self or not getattr(other, "alive", False) or bool(getattr(other, "is_player", False)):
                continue
            other_sex = str(getattr(other, "biological_sex", "") or "").strip().lower()
            if other_sex not in BIOLOGICAL_SEX_VALUES:
                other_sex = random.choice(BIOLOGICAL_SEX_VALUES)
                other.biological_sex = other_sex
            same_effective_context = bool(getattr(other, "village_id", None) == effective_village_id)
            anchor_center_dist: Optional[int] = None
            if (not same_effective_context) and stable_proto_household_path_active and stable_proto_household_center is not None:
                ox = int(getattr(other, "x", 0))
                oy = int(getattr(other, "y", 0))
                cdist = abs(ox - int(stable_proto_household_center[0])) + abs(oy - int(stable_proto_household_center[1]))
                anchor_center_dist = int(cdist)
                same_effective_context = bool(cdist <= int(STABLE_PROTO_HOUSEHOLD_RADIUS))
            if (
                stable_proto_household_path_active
                and stable_proto_household_center is not None
                and other_sex != sex_self
            ):
                if anchor_center_dist is None:
                    ox = int(getattr(other, "x", 0))
                    oy = int(getattr(other, "y", 0))
                    anchor_center_dist = abs(ox - int(stable_proto_household_center[0])) + abs(oy - int(stable_proto_household_center[1]))
                if (not same_effective_context) and int(anchor_center_dist) <= int(STABLE_PROTO_HOUSEHOLD_ANCHOR_SEARCH_RADIUS):
                    anchor_partner_context_mismatch_count += 1
            if not same_effective_context:
                continue
            dist_to_other = abs(int(getattr(other, "x", 0)) - int(self.x)) + abs(int(getattr(other, "y", 0)) - int(self.y))
            if int(dist_to_other) <= int(REPRO_NEARBY_PARTNER_RADIUS):
                nearby_partners += 1
            if other_sex != sex_self:
                anchor_partner_candidate_count += 1
                if int(dist_to_other) <= int(REPRO_NEARBY_PARTNER_RADIUS):
                    anchor_partner_nearby_count += 1
                else:
                    anchor_partner_too_far_count += 1
                    if int(dist_to_other) < int(anchor_nearest_partner_far_dist):
                        anchor_nearest_partner_far_dist = int(dist_to_other)
                        anchor_nearest_partner_far_pos = (
                            int(getattr(other, "x", int(self.x))),
                            int(getattr(other, "y", int(self.y))),
                        )
                other_age = int(getattr(world, "tick", 0)) - int(getattr(other, "born_tick", 0))
                if other_age < int(REPRO_MIN_AGE_TICKS):
                    continue
                if int(dist_to_other) <= int(STABLE_PROTO_COPRESENCE_RADIUS):
                    anchor_opposite_sex_copresent_count += 1
                if int(dist_to_other) > int(REPRO_NEARBY_PARTNER_RADIUS) and int(dist_to_other) < int(anchor_nearest_age_ok_far_dist):
                    anchor_nearest_age_ok_far_dist = int(dist_to_other)
                    anchor_nearest_age_ok_far_pos = (
                        int(getattr(other, "x", int(self.x))),
                        int(getattr(other, "y", int(self.y))),
                    )
                    anchor_nearest_age_ok_far_id = str(getattr(other, "agent_id", ""))
                other_health_ok = float(getattr(other, "health", 100.0)) >= float(LOW_HEALTH_THRESHOLD)
                other_hunger_ok = float(getattr(other, "hunger", 0.0)) >= float(REPRO_MIN_HUNGER)
                other_cooldown_ok = int(getattr(other, "repro_cooldown", 0)) <= 0
                if not other_cooldown_ok:
                    anchor_partner_blocked_cooldown_count += 1
                if not (other_health_ok and other_hunger_ok):
                    anchor_partner_blocked_health_or_hunger_count += 1
                if (
                    int(dist_to_other) > int(REPRO_NEARBY_PARTNER_RADIUS)
                    and int(dist_to_other) <= int(STABLE_PROTO_MICRO_CLOSURE_MAX_DISTANCE)
                    and int(dist_to_other) < int(anchor_nearest_micro_age_ok_dist)
                ):
                    anchor_nearest_micro_age_ok_dist = int(dist_to_other)
                    anchor_nearest_micro_age_ok_id = str(getattr(other, "agent_id", ""))
                    anchor_nearest_micro_age_ok_agent = other
                if int(dist_to_other) > int(REPRO_NEARBY_PARTNER_RADIUS):
                    continue
                opposite_sex_partners += 1
                opposite_sex_age_ok += 1
                if other_health_ok and other_hunger_ok and other_cooldown_ok:
                    if int(dist_to_other) <= int(REPRO_NEARBY_PARTNER_RADIUS):
                        opposite_sex_ready_partner = other
                        break
                    if int(dist_to_other) < int(anchor_nearest_valid_partner_far_dist):
                        anchor_nearest_valid_partner_far_dist = int(dist_to_other)
                        anchor_nearest_valid_partner_far_pos = (
                            int(getattr(other, "x", int(self.x))),
                            int(getattr(other, "y", int(self.y))),
                        )
                        anchor_nearest_valid_partner_far_id = str(getattr(other, "agent_id", ""))
        if stable_proto_household_path_active:
            if anchor_partner_candidate_count > 0:
                _metric("stable_proto_anchor_partner_candidate_count", 1)
            if anchor_partner_nearby_count > 0:
                _metric("stable_proto_anchor_partner_nearby_count", 1)
            elif anchor_partner_too_far_count > 0:
                _metric("stable_proto_anchor_partner_too_far_count", 1)
            if anchor_partner_blocked_health_or_hunger_count > 0:
                _metric("stable_proto_anchor_partner_blocked_by_health_or_hunger_count", 1)
            if anchor_partner_blocked_cooldown_count > 0:
                _metric("stable_proto_anchor_partner_blocked_by_cooldown_count", 1)
            if anchor_partner_context_mismatch_count > 0:
                _metric("stable_proto_anchor_partner_blocked_by_context_mismatch_count", 1)
            copresence_survival_ok = bool(
                float(getattr(self, "hunger", 0.0)) >= max(30.0, float(REPRO_MIN_HUNGER) - 20.0)
                and float(getattr(self, "health", 100.0)) >= float(LOW_HEALTH_THRESHOLD)
                and float(getattr(self, "sleep_need", 0.0)) < 85.0
                and float(getattr(self, "fatigue", 0.0)) < 85.0
            )
            if anchor_opposite_sex_copresent_count > 0:
                _metric("stable_proto_copresence_ticks_with_opposite_sex_partner_count", 1)
                if copresence_survival_ok:
                    self.stable_proto_copresence_ticks = int(getattr(self, "stable_proto_copresence_ticks", 0)) + 1
                    if int(self.stable_proto_copresence_ticks) == int(STABLE_PROTO_COPRESENCE_WINDOW_TICKS):
                        _metric("stable_proto_copresence_window_pass_count", 1)
                else:
                    if int(getattr(self, "stable_proto_copresence_ticks", 0)) > 0:
                        _metric("stable_proto_copresence_broken_by_survival_count", 1)
                    self.stable_proto_copresence_ticks = 0
            else:
                if int(getattr(self, "stable_proto_copresence_ticks", 0)) > 0:
                    _metric("stable_proto_copresence_broken_by_context_loss_count", 1)
                self.stable_proto_copresence_ticks = 0
        else:
            if int(getattr(self, "stable_proto_copresence_ticks", 0)) > 0:
                _metric("stable_proto_copresence_broken_by_context_loss_count", 1)
            self.stable_proto_copresence_ticks = 0

        hold_survival_unstable = bool(
            float(getattr(self, "hunger", 0.0)) < max(30.0, float(REPRO_MIN_HUNGER) - 20.0)
            or float(getattr(self, "health", 100.0)) < float(LOW_HEALTH_THRESHOLD)
            or float(getattr(self, "sleep_need", 0.0)) >= 85.0
            or float(getattr(self, "fatigue", 0.0)) >= 85.0
        )
        if proto_path_inactivity_hold_active:
            hold_anchor_id = getattr(self, "stable_proto_path_inactivity_hold_anchor_village_id", None)
            hold_anchor_village = (
                world.get_village_by_id(int(hold_anchor_id))
                if isinstance(hold_anchor_id, int) and hasattr(world, "get_village_by_id")
                else None
            )
            if hold_survival_unstable:
                _metric("stable_proto_path_inactivity_jitter_hold_broken_by_survival_count", 1)
                self.stable_proto_path_inactivity_hold_until_tick = -1
                self.stable_proto_path_inactivity_hold_anchor_village_id = None
                proto_path_inactivity_hold_active = False
            elif not isinstance(hold_anchor_village, dict):
                _metric("stable_proto_path_inactivity_jitter_hold_broken_by_context_loss_count", 1)
                self.stable_proto_path_inactivity_hold_until_tick = -1
                self.stable_proto_path_inactivity_hold_anchor_village_id = None
                proto_path_inactivity_hold_active = False
            elif stable_proto_household_path_active and isinstance(anchor_nearest_micro_age_ok_id, str) and bool(anchor_nearest_micro_age_ok_id):
                _metric("stable_proto_path_inactivity_jitter_hold_completed_count", 1)
                self.stable_proto_path_inactivity_hold_until_tick = -1
                self.stable_proto_path_inactivity_hold_anchor_village_id = None
                proto_path_inactivity_hold_active = False
        if opposite_sex_partners > 0:
            _metric("agents_with_opposite_sex_partner_candidate_count", 1)
        partner_ok = opposite_sex_ready_partner is not None
        if convergence_active and (partner_ok or anchor_partner_nearby_count > 0):
            _metric("stable_proto_partner_convergence_completed_count", 1)
            _clear_proto_partner_convergence("")
            convergence_active = False
        if micro_closure_active and anchor_partner_nearby_count > 0:
            _metric("stable_proto_micro_proximity_closure_completed_count", 1)
            _clear_proto_micro_closure("")
            micro_closure_active = False
        if partner_ok:
            _metric("agents_with_local_partner_candidate_count", 1)
        if (
            (not partner_ok)
            and stable_proto_household_path_active
            and isinstance(anchor_nearest_micro_age_ok_id, str)
            and bool(anchor_nearest_micro_age_ok_id)
            and float(getattr(self, "hunger", 0.0)) >= max(34.0, float(REPRO_MIN_HUNGER) - 20.0)
            and float(getattr(self, "health", 100.0)) >= float(LOW_HEALTH_THRESHOLD)
            and float(getattr(self, "sleep_need", 0.0)) < 80.0
            and float(getattr(self, "fatigue", 0.0)) < 80.0
        ):
            tick_now = int(getattr(world, "tick", 0))
            if (not micro_closure_active) or str(getattr(self, "stable_proto_micro_partner_agent_id", "")) != str(anchor_nearest_micro_age_ok_id):
                _metric("stable_proto_micro_proximity_closure_invoked_count", 1)
            self.stable_proto_micro_partner_agent_id = str(anchor_nearest_micro_age_ok_id)
            self.stable_proto_micro_until_tick = int(tick_now) + int(STABLE_PROTO_MICRO_CLOSURE_TTL_TICKS)
            self.stable_proto_micro_anchor_village_id = (
                int(effective_village_id) if isinstance(effective_village_id, int) else None
            )
            self.stable_proto_micro_invoke_tick = int(tick_now)
            self.stable_proto_micro_invoke_distance = int(anchor_nearest_micro_age_ok_dist)
            self.stable_proto_drift_damping_partner_agent_id = str(anchor_nearest_micro_age_ok_id)
            self.stable_proto_drift_damping_until_tick = int(tick_now) + int(STABLE_PROTO_PARTNER_DRIFT_DAMPING_TTL_TICKS)
            self.stable_proto_drift_damping_anchor_village_id = (
                int(effective_village_id) if isinstance(effective_village_id, int) else None
            )
            if anchor_nearest_micro_age_ok_agent is not None and bool(getattr(anchor_nearest_micro_age_ok_agent, "alive", False)):
                anchor_nearest_micro_age_ok_agent.stable_proto_drift_damping_partner_agent_id = str(getattr(self, "agent_id", ""))
                anchor_nearest_micro_age_ok_agent.stable_proto_drift_damping_until_tick = (
                    int(tick_now) + int(STABLE_PROTO_PARTNER_DRIFT_DAMPING_TTL_TICKS)
                )
                partner_anchor_id = (
                    int(effective_village_id)
                    if isinstance(effective_village_id, int)
                    else (
                        int(getattr(anchor_nearest_micro_age_ok_agent, "village_id", -1))
                        if isinstance(getattr(anchor_nearest_micro_age_ok_agent, "village_id", None), int)
                        else None
                    )
                )
                anchor_nearest_micro_age_ok_agent.stable_proto_drift_damping_anchor_village_id = partner_anchor_id
            micro_closure_active = True
        elif micro_closure_active and (not partner_ok) and (
            not stable_proto_household_path_active
            or not isinstance(anchor_nearest_micro_age_ok_id, str)
            or not bool(anchor_nearest_micro_age_ok_id)
        ):
            tick_now = int(getattr(world, "tick", 0))
            invoke_tick = int(getattr(self, "stable_proto_micro_invoke_tick", -1))
            hold_allowed = bool(
                invoke_tick >= 0
                and int(tick_now - invoke_tick) <= int(STABLE_PROTO_MICRO_CONTEXT_HOLD_GRACE_TICKS)
            )
            hold_anchor_id = (
                int(effective_village_id) if isinstance(effective_village_id, int)
                else (
                    int(getattr(self, "stable_proto_micro_anchor_village_id", -1))
                    if isinstance(getattr(self, "stable_proto_micro_anchor_village_id", None), int)
                    else None
                )
            )
            hold_anchor_valid = bool(
                isinstance(hold_anchor_id, int)
                and hasattr(world, "get_village_by_id")
                and isinstance(world.get_village_by_id(int(hold_anchor_id)), dict)
            )
            if hold_allowed:
                _metric("stable_proto_micro_context_hold_invoked_count", 1)
                self.stable_proto_micro_until_tick = max(int(getattr(self, "stable_proto_micro_until_tick", -1)), int(tick_now) + 1)
            can_hold_jitter = bool((not hold_survival_unstable) and hold_anchor_valid)
            if can_hold_jitter:
                if not proto_path_inactivity_hold_active:
                    _metric("stable_proto_path_inactivity_jitter_hold_invoked_count", 1)
                self.stable_proto_path_inactivity_hold_until_tick = int(tick_now) + int(
                    STABLE_PROTO_PATH_INACTIVITY_HOLD_TTL_TICKS
                )
                self.stable_proto_path_inactivity_hold_anchor_village_id = int(hold_anchor_id) if isinstance(hold_anchor_id, int) else None
                proto_path_inactivity_hold_active = True
            elif (not hold_allowed) or hold_survival_unstable or (not hold_anchor_valid):
                subreason = (
                    "proto_path_inactive"
                    if (not stable_proto_household_path_active)
                    else "candidate_missing"
                )
                if hold_survival_unstable:
                    _metric("stable_proto_path_inactivity_jitter_hold_broken_by_survival_count", 1)
                elif not hold_anchor_valid:
                    _metric("stable_proto_path_inactivity_jitter_hold_broken_by_context_loss_count", 1)
                _clear_proto_micro_closure("context_loss", subreason)
                micro_closure_active = False
        if (
            (not partner_ok)
            and stable_proto_household_path_active
            and isinstance(anchor_nearest_age_ok_far_pos, tuple)
            and len(anchor_nearest_age_ok_far_pos) == 2
        ):
            tick_now = int(getattr(world, "tick", 0))
            self.task_target = (int(anchor_nearest_age_ok_far_pos[0]), int(anchor_nearest_age_ok_far_pos[1]))
            self.movement_commit_target = (int(anchor_nearest_age_ok_far_pos[0]), int(anchor_nearest_age_ok_far_pos[1]))
            self.movement_commit_until_tick = int(tick_now) + int(STABLE_PROTO_PARTNER_COLOCALITY_COMMIT_TICKS)
            new_convergence_target = str(anchor_nearest_age_ok_far_id or "")
            if (not convergence_active) or str(getattr(self, "stable_proto_partner_convergence_agent_id", "")) != new_convergence_target:
                _metric("stable_proto_partner_convergence_invoked_count", 1)
            self.stable_proto_partner_convergence_agent_id = new_convergence_target or None
            self.stable_proto_partner_convergence_until_tick = int(tick_now) + int(STABLE_PROTO_PARTNER_CONVERGENCE_TTL_TICKS)
            self.stable_proto_partner_convergence_anchor_village_id = (
                int(effective_village_id) if isinstance(effective_village_id, int) else None
            )
            convergence_active = True
        elif convergence_active and (not partner_ok) and (
            not stable_proto_household_path_active
            or not isinstance(anchor_nearest_age_ok_far_pos, tuple)
        ):
            _clear_proto_partner_convergence("context_loss")
            convergence_active = False
        if nearby_partners <= 0:
            if stable_proto_household_path_active:
                _metric("reproduction_stable_proto_household_path_blocked_by_partner_not_in_same_effective_proto_context_count", 1)
            core_near_miss = [
                age_ok,
                (formalized or proto_path_active or stable_proto_household_path_active),
                shelter_ok,
                health_ok,
                cooldown_ok,
                False,
            ]
            if sum(1 for ok in core_near_miss if not bool(ok)) == 1:
                _metric("agents_meeting_all_repro_conditions_except_one_count", 1)
            _blocked("blocked_by_no_local_partner")
            return
        if opposite_sex_partners <= 0:
            if proto_path_active:
                _metric("reproduction_proto_path_blocked_by_no_opposite_sex_partner_count", 1)
            if stable_proto_household_path_active:
                _metric("reproduction_stable_proto_household_path_blocked_by_no_opposite_sex_partner_count", 1)
            _blocked("blocked_by_no_opposite_sex_partner")
            return
        if opposite_sex_age_ok <= 0:
            _blocked("blocked_by_partner_age")
            return
        if not partner_ok:
            # At least one opposite-sex candidate exists and age is valid, but no healthy/hunger/cooldown-ready partner.
            partner_unavailable = False
            for other in getattr(world, "agents", []):
                if other is self or not getattr(other, "alive", False) or bool(getattr(other, "is_player", False)):
                    continue
                same_effective_context = bool(getattr(other, "village_id", None) == effective_village_id)
                if (not same_effective_context) and stable_proto_household_path_active and stable_proto_household_center is not None:
                    ox = int(getattr(other, "x", 0))
                    oy = int(getattr(other, "y", 0))
                    cdist = abs(ox - int(stable_proto_household_center[0])) + abs(oy - int(stable_proto_household_center[1]))
                    same_effective_context = bool(cdist <= int(STABLE_PROTO_HOUSEHOLD_RADIUS))
                if not same_effective_context:
                    continue
                if abs(int(getattr(other, "x", 0)) - int(self.x)) + abs(int(getattr(other, "y", 0)) - int(self.y)) > int(REPRO_NEARBY_PARTNER_RADIUS):
                    continue
                other_sex = str(getattr(other, "biological_sex", "") or "").strip().lower()
                if other_sex == sex_self:
                    continue
                other_age = int(getattr(world, "tick", 0)) - int(getattr(other, "born_tick", 0))
                if other_age < int(REPRO_MIN_AGE_TICKS):
                    continue
                if int(getattr(other, "repro_cooldown", 0)) > 0:
                    partner_unavailable = True
                    break
            if partner_unavailable:
                _blocked("blocked_by_partner_unavailable")
            else:
                _blocked("blocked_by_partner_health_or_hunger")
            return

        repro_min_hunger = REPRO_MIN_HUNGER
        repro_prob = REPRO_PROB
        if village is not None and local_food_security_ok:
            repro_min_hunger = max(75, REPRO_MIN_HUNGER - 10)
            repro_prob = min(0.03, REPRO_PROB * 1.8)
        if proto_path_active:
            # Proto path stays narrow and gated, but once all gates pass we allow slightly
            # better activation-to-birth conversion to avoid a fully inert continuity path.
            repro_min_hunger = max(72, repro_min_hunger - 3)
            repro_prob = min(0.12, repro_prob * 2.8)

        hunger_ok = float(self.hunger) >= float(repro_min_hunger)
        if hunger_ok:
            _metric("agents_meeting_hunger_requirement_for_repro_count", 1)
        core_near_miss = [
            age_ok,
            (formalized or proto_path_active or stable_proto_household_path_active),
            shelter_ok,
            health_ok,
            cooldown_ok,
            partner_ok,
            hunger_ok,
        ]
        if sum(1 for ok in core_near_miss if not bool(ok)) == 1:
            _metric("agents_meeting_all_repro_conditions_except_one_count", 1)
        if partner_ok and hunger_ok and age_ok and (formalized or proto_path_active or stable_proto_household_path_active) and shelter_ok and health_ok and cooldown_ok:
            _metric("agents_meeting_all_repro_conditions_count", 1)

        if self.hunger < repro_min_hunger:
            if not local_food_security_ok:
                _blocked("blocked_by_low_local_food_security")
            else:
                _blocked("blocked_by_hunger")
            return

        if random.random() > repro_prob:
            _blocked("blocked_by_other")
            return

        pos = world.find_free_adjacent(self.x, self.y)
        if pos is None:
            _blocked("blocked_by_other")
            return

        bx, by = pos

        baby = Agent(
            x=bx,
            y=by,
            brain=self.brain,
            is_player=False,
            player_id=None,
        )
        baby.spawn_origin = "reproduction"

        baby.hunger = float(AGENT_START_HUNGER)
        baby.role = "npc"
        baby.village_id = effective_village_id if isinstance(effective_village_id, int) else self.village_id
        baby.task = "idle"

        world.add_agent(baby)

        self.hunger -= REPRO_COST
        if self.hunger < 1:
            self.hunger = 1

        self.repro_cooldown = 80
        if opposite_sex_ready_partner is not None:
            opposite_sex_ready_partner.repro_cooldown = max(int(getattr(opposite_sex_ready_partner, "repro_cooldown", 0)), 80)

    def update(self, world: "World") -> None:
        if not self.alive:
            return
        # Lightweight per-tick reference for optional knowledge usage instrumentation.
        setattr(self, "_world_ref", world)

        self.update_memory(world)
        self.cleanup_memory(world)
        self.update_subjective_state(world)
        role_key = str(getattr(self, "role", "other") or "other")
        uid = str(world._resolve_agent_work_village_uid(self) or "") if hasattr(world, "_resolve_agent_work_village_uid") else ""
        high_sleep = bool(float(getattr(self, "sleep_need", 0.0)) >= float(HIGH_SLEEP_NEED_THRESHOLD))
        high_fatigue = bool(float(getattr(self, "fatigue", 0.0)) >= float(HIGH_FATIGUE_THRESHOLD))
        high_pressure = bool(high_sleep or high_fatigue)
        has_valid_home = self._has_valid_home(world)
        if hasattr(world, "record_recovery_stage"):
            world.record_recovery_stage(self, "recovery_context_seen", village_uid=uid, role=role_key)
        if high_sleep and hasattr(world, "record_recovery_stage"):
            world.record_recovery_stage(self, "high_sleep_need_seen", village_uid=uid, role=role_key)
        if high_fatigue and hasattr(world, "record_recovery_stage"):
            world.record_recovery_stage(self, "high_fatigue_seen", village_uid=uid, role=role_key)
        if high_pressure and hasattr(world, "record_recovery_stage"):
            world.record_recovery_stage(self, "rest_candidate_seen", village_uid=uid, role=role_key)
        elif hasattr(world, "record_recovery_failure_reason"):
            world.record_recovery_failure_reason(self, "rest_not_needed", village_uid=uid, role=role_key)
        if hasattr(world, "record_recovery_home_context"):
            world.record_recovery_home_context(
                self,
                valid_home=has_valid_home,
                high_pressure_with_valid_home=bool(high_pressure and has_valid_home),
                home_possible_not_chosen=bool(high_pressure and has_valid_home and str(getattr(self, "task", "")) != "rest"),
                village_uid=uid,
                role=role_key,
            )
        if high_pressure and not has_valid_home and hasattr(world, "record_recovery_failure_reason"):
            if self.home_building_id is None:
                world.record_recovery_failure_reason(self, "no_home", village_uid=uid, role=role_key)
            else:
                world.record_recovery_failure_reason(self, "no_valid_home_target", village_uid=uid, role=role_key)
        if high_pressure and str(getattr(self, "village_affiliation_status", "")) != "resident" and hasattr(world, "record_recovery_failure_reason"):
            world.record_recovery_failure_reason(self, "not_resident", village_uid=uid, role=role_key)
        prev_task = str(getattr(self, "task", "idle"))
        self.update_role_task(world)
        task_after_role = str(getattr(self, "task", "idle"))
        tick_now = int(getattr(world, "tick", 0))
        pressure_regime = "medium"
        pressure_ratio = 0.0
        if hasattr(world, "compute_local_food_pressure_for_agent"):
            try:
                pressure = world.compute_local_food_pressure_for_agent(self, max_distance=10)
            except Exception:
                pressure = {}
            if isinstance(pressure, dict):
                pressure_regime, pressure_ratio = self._resolve_foraging_pressure_regime(
                    pressure, str(getattr(self, "foraging_pressure_regime", "medium"))
                )
        self.foraging_pressure_regime = str(pressure_regime)
        self.foraging_pressure_ratio = float(pressure_ratio)
        high_pressure_hold = bool(
            pressure_regime == "high"
            and int(getattr(self, "foraging_trip_harvest_units", 0)) > 0
            and float(getattr(self, "hunger", 100.0)) >= 24.0
            and int(getattr(self, "inventory", {}).get("food", 0)) <= 4
            and task_after_role in FORAGING_POST_HARVEST_CONTINUE_TASKS
        )
        medium_pressure_hold = bool(
            pressure_regime == "medium"
            and int(getattr(self, "foraging_trip_harvest_units", 0)) >= 2
            and float(getattr(self, "hunger", 100.0)) >= 34.0
            and int(getattr(self, "inventory", {}).get("food", 0)) <= 2
            and task_after_role in FORAGING_POST_HARVEST_CONTINUE_TASKS
        )
        post_first_harvest_hold = False
        post_first_harvest_narrow_redirect_hold = False
        first_harvest_tick = int(getattr(self, "foraging_trip_first_harvest_tick", -1))
        exploit_until_tick = int(getattr(self, "foraging_patch_exploit_until_tick", -1))
        exploit_target_actions = int(getattr(self, "foraging_patch_exploit_target_harvest_actions", 0))
        exploit_anchor = getattr(self, "foraging_patch_exploit_anchor", None)
        switch_context: Dict[str, Any] = {}
        if (
            prev_task == "gather_food_wild"
            and task_after_role != "gather_food_wild"
            and bool(getattr(self, "foraging_trip_active", False))
            and int(getattr(self, "foraging_trip_harvest_units", 0)) > 0
            and (
                first_harvest_tick >= 0
                or exploit_until_tick >= tick_now
            )
            and task_after_role in (FORAGING_POST_HARVEST_CONTINUE_TASKS | FORAGING_POST_HARVEST_REDIRECT_TASKS)
            and float(getattr(self, "hunger", 100.0)) >= 24.0
        ):
            switch_context = self._post_first_harvest_switch_context(
                world,
                new_task=task_after_role,
                tick_now=tick_now,
            )
            if hasattr(world, "record_foraging_switch_debug_event"):
                world.record_foraging_switch_debug_event(
                    self,
                    "post_first_harvest_task_switch_attempt",
                    prev_task=prev_task,
                    new_task=task_after_role,
                    reason="role_recompute_after_first_harvest",
                    **switch_context,
                )
            low_value_redirect = str(task_after_role) in FORAGING_POST_HARVEST_REDIRECT_TASKS
            if low_value_redirect:
                if self._should_block_narrow_post_harvest_redirect(switch_context):
                    post_first_harvest_narrow_redirect_hold = True
            in_exploit_window = bool(exploit_until_tick >= tick_now and exploit_target_actions > 0)
            if in_exploit_window and int(getattr(self, "foraging_trip_harvest_actions", 0)) >= exploit_target_actions:
                in_exploit_window = False
            if (not in_exploit_window) and first_harvest_tick >= 0:
                hold_window = 0
                if pressure_regime == "medium":
                    hold_window = 10
                elif pressure_regime == "high":
                    hold_window = 18
                in_exploit_window = bool(hold_window > 0 and (tick_now - first_harvest_tick) <= hold_window)
            if in_exploit_window:
                target = None
                if isinstance(getattr(self, "task_target", None), tuple) and len(getattr(self, "task_target", ())) == 2:
                    target = (int(self.task_target[0]), int(self.task_target[1]))
                elif isinstance(getattr(self, "foraging_trip_target", None), tuple) and len(getattr(self, "foraging_trip_target", ())) == 2:
                    target = (int(self.foraging_trip_target[0]), int(self.foraging_trip_target[1]))
                elif isinstance(exploit_anchor, tuple) and len(exploit_anchor) == 2:
                    target = (int(exploit_anchor[0]), int(exploit_anchor[1]))
                if isinstance(target, tuple):
                    distance = abs(int(self.x) - int(target[0])) + abs(int(self.y) - int(target[1]))
                    target_has_food = target in getattr(world, "food", set())
                    if not target_has_food and hasattr(world, "_find_nearest_food_to") and distance <= 3:
                        nearby = world._find_nearest_food_to(int(target[0]), int(target[1]), radius=3)
                        if isinstance(nearby, tuple) and len(nearby) == 2:
                            self.task_target = (int(nearby[0]), int(nearby[1]))
                            target_has_food = True
                    if target_has_food or distance <= 1:
                        post_first_harvest_hold = True
        if (
            prev_task == "gather_food_wild"
            and task_after_role != "gather_food_wild"
            and bool(getattr(self, "foraging_trip_active", False))
            and (high_pressure_hold or medium_pressure_hold or post_first_harvest_hold or post_first_harvest_narrow_redirect_hold)
        ):
            self.task = "gather_food_wild"
            task_after_role = "gather_food_wild"
            if hasattr(world, "record_settlement_progression_metric"):
                world.record_settlement_progression_metric("foraging_commitment_hold_overrides")
            if switch_context and hasattr(world, "record_foraging_switch_debug_event"):
                world.record_foraging_switch_debug_event(
                    self,
                    "post_first_harvest_task_switch_blocked",
                    prev_task=prev_task,
                    new_task=str(getattr(self, "task", "")),
                    reason="exploitation_or_commitment_hold",
                    **switch_context,
                )

        def _finalize_foraging_trip(reason: str) -> None:
            if not bool(getattr(self, "foraging_trip_active", False)):
                return
            move_ticks = int(getattr(self, "foraging_trip_move_ticks", 0))
            harvest_units = int(getattr(self, "foraging_trip_harvest_units", 0))
            harvest_actions = int(getattr(self, "foraging_trip_harvest_actions", 0))
            retargets = int(getattr(self, "foraging_trip_retarget_count", 0))
            first_harvest_tick_local = int(getattr(self, "foraging_trip_first_harvest_tick", -1))
            max_consecutive_harvest_actions = int(getattr(self, "foraging_trip_max_consecutive_harvest_actions", 0))
            pressure_bucket = "medium"
            contention_bucket = "medium"
            pressure = {}
            if hasattr(world, "compute_local_food_pressure_for_agent"):
                try:
                    pressure = world.compute_local_food_pressure_for_agent(self, max_distance=10)
                except Exception:
                    pressure = {}
            if isinstance(pressure, dict):
                pressure_bucket, _ = self._resolve_foraging_pressure_regime(
                    pressure, str(getattr(self, "foraging_pressure_regime", "medium"))
                )
            nearby_foragers = 0
            for other in getattr(world, "agents", []):
                if not getattr(other, "alive", False):
                    continue
                if str(getattr(other, "agent_id", "")) == str(getattr(self, "agent_id", "")):
                    continue
                if str(getattr(other, "task", "")) not in {"gather_food_wild", "farm_cycle"}:
                    continue
                if abs(int(getattr(other, "x", 0)) - int(self.x)) + abs(int(getattr(other, "y", 0)) - int(self.y)) <= 4:
                    nearby_foragers += 1
            if nearby_foragers <= 1:
                contention_bucket = "low"
            elif nearby_foragers >= 4:
                contention_bucket = "high"
            if hasattr(world, "record_settlement_progression_metric"):
                world.record_settlement_progression_metric("foraging_trip_completed_count")
                world.record_settlement_progression_metric("foraging_trip_movement_ticks_total", move_ticks)
                world.record_settlement_progression_metric("foraging_trip_food_gained_total", harvest_units)
                world.record_settlement_progression_metric("foraging_trip_harvest_actions_total", harvest_actions)
                world.record_settlement_progression_metric("foraging_trip_retarget_count_total", retargets)
                world.record_settlement_progression_metric(f"foraging_trip_total_pressure_{pressure_bucket}_count")
                world.record_settlement_progression_metric("foraging_trip_max_consecutive_harvest_actions_total", max_consecutive_harvest_actions)
                world.record_settlement_progression_metric("foraging_trip_max_consecutive_harvest_actions_samples")
                if harvest_units <= 0:
                    world.record_settlement_progression_metric("foraging_trip_zero_harvest_count")
                    world.record_settlement_progression_metric("foraging_trip_aborted_before_first_harvest_count")
                    setattr(self, "last_failed_foraging_trip_tick", int(getattr(world, "tick", 0)))
                else:
                    setattr(self, "last_failed_foraging_trip_tick", -10_000)
                    world.record_settlement_progression_metric(f"foraging_trip_success_pressure_{pressure_bucket}_count")
                    world.record_settlement_progression_metric("foraging_trip_successful_count")
                    world.record_settlement_progression_metric(
                        "foraging_trip_post_first_harvest_units_total",
                        max(0, harvest_units - 1),
                    )
                    world.record_settlement_progression_metric("foraging_trip_post_first_harvest_units_samples")
                    if harvest_actions == 1:
                        world.record_settlement_progression_metric("foraging_trip_single_harvest_action_count")
                    if first_harvest_tick_local >= 0:
                        dwell_ticks = max(0, int(getattr(world, "tick", 0)) - first_harvest_tick_local)
                        world.record_settlement_progression_metric("foraging_trip_patch_dwell_after_first_harvest_ticks_total", dwell_ticks)
                        world.record_settlement_progression_metric("foraging_trip_patch_dwell_after_first_harvest_ticks_samples")
                        if str(reason) != "completed" and dwell_ticks <= 12:
                            world.record_settlement_progression_metric("foraging_trip_ended_soon_after_first_harvest_count")
                    if str(reason) != "completed":
                        world.record_settlement_progression_metric("foraging_trip_aborted_after_first_harvest_count")
                reason_metric = "foraging_trip_end_reason_other"
                if str(reason) == "task_switched":
                    reason_metric = "foraging_trip_end_reason_task_switched"
                elif str(reason) == "hunger_death":
                    reason_metric = "foraging_trip_end_reason_hunger_death"
                world.record_settlement_progression_metric(reason_metric)
                if harvest_units > 0:
                    if str(reason) == "task_switched":
                        world.record_settlement_progression_metric("foraging_trip_end_after_first_harvest_task_switched")
                    elif str(reason) == "hunger_death":
                        world.record_settlement_progression_metric("foraging_trip_end_after_first_harvest_hunger_death")
                    elif str(reason) == "completed":
                        world.record_settlement_progression_metric("foraging_trip_end_after_first_harvest_completed")
                    else:
                        world.record_settlement_progression_metric("foraging_trip_end_after_first_harvest_other")
            stats = getattr(world, "settlement_progression_stats", {})
            if isinstance(stats, dict):
                efficiency = float(harvest_units) / float(max(1, move_ticks))
                stats["foraging_trip_efficiency_ratio_sum"] = float(
                    stats.get("foraging_trip_efficiency_ratio_sum", 0.0)
                ) + float(efficiency)
                stats["foraging_trip_efficiency_ratio_samples"] = int(
                    stats.get("foraging_trip_efficiency_ratio_samples", 0)
                ) + 1
                pressure_sum_key = f"foraging_trip_efficiency_pressure_{pressure_bucket}_sum"
                pressure_samples_key = f"foraging_trip_efficiency_pressure_{pressure_bucket}_samples"
                stats[pressure_sum_key] = float(stats.get(pressure_sum_key, 0.0)) + float(efficiency)
                stats[pressure_samples_key] = int(stats.get(pressure_samples_key, 0)) + 1
                contention_sum_key = f"foraging_trip_efficiency_contention_{contention_bucket}_sum"
                contention_samples_key = f"foraging_trip_efficiency_contention_{contention_bucket}_samples"
                stats[contention_sum_key] = float(stats.get(contention_sum_key, 0.0)) + float(efficiency)
                stats[contention_samples_key] = int(stats.get(contention_samples_key, 0)) + 1
                world.settlement_progression_stats = stats
            self.foraging_trip_active = False
            self.foraging_trip_start_tick = -1
            self.foraging_trip_move_ticks = 0
            self.foraging_trip_harvest_units = 0
            self.foraging_trip_harvest_actions = 0
            self.foraging_trip_retarget_count = 0
            self.foraging_trip_first_harvest_tick = -1
            self.foraging_trip_target = None
            self.foraging_target_set_tick = -1
            self.foraging_trip_last_harvest_pos = None
            self.foraging_trip_current_consecutive_harvest_actions = 0
            self.foraging_trip_max_consecutive_harvest_actions = 0
            self.foraging_patch_exploit_until_tick = -1
            self.foraging_patch_exploit_target_harvest_actions = 0
            self.foraging_patch_exploit_anchor = None
            if hasattr(world, "record_behavior_activity"):
                world.record_behavior_activity(f"foraging_trip_end:{reason}", x=int(self.x), y=int(self.y), agent=self)

        if task_after_role == "gather_food_wild":
            if not bool(getattr(self, "foraging_trip_active", False)):
                self.foraging_trip_active = True
                self.foraging_trip_start_tick = int(tick_now)
                self.foraging_trip_move_ticks = 0
                self.foraging_trip_harvest_units = 0
                self.foraging_trip_harvest_actions = 0
                self.foraging_trip_retarget_count = 0
                self.foraging_trip_first_harvest_tick = -1
                self.foraging_trip_target = tuple(getattr(self, "task_target", ())) if isinstance(getattr(self, "task_target", None), tuple) else None
                self.foraging_trip_last_harvest_pos = None
                self.foraging_trip_current_consecutive_harvest_actions = 0
                self.foraging_trip_max_consecutive_harvest_actions = 0
                self.foraging_patch_exploit_until_tick = -1
                self.foraging_patch_exploit_target_harvest_actions = 0
                self.foraging_patch_exploit_anchor = None
                if hasattr(world, "record_settlement_progression_metric"):
                    world.record_settlement_progression_metric("foraging_trip_started_count")
            current_target = tuple(getattr(self, "task_target", ())) if isinstance(getattr(self, "task_target", None), tuple) else None
            prev_target = tuple(getattr(self, "foraging_trip_target", ())) if isinstance(getattr(self, "foraging_trip_target", None), tuple) else None
            if current_target is not None and prev_target is not None and current_target != prev_target:
                self.foraging_trip_retarget_count = int(getattr(self, "foraging_trip_retarget_count", 0)) + 1
                self.foraging_trip_target = current_target
                if hasattr(world, "record_settlement_progression_metric"):
                    world.record_settlement_progression_metric("foraging_retarget_events")
                    pressure = {}
                    if hasattr(world, "compute_local_food_pressure_for_agent"):
                        try:
                            pressure = world.compute_local_food_pressure_for_agent(self, max_distance=10)
                        except Exception:
                            pressure = {}
                    bucket = "medium"
                    if isinstance(pressure, dict):
                        bucket, _ = self._resolve_foraging_pressure_regime(
                            pressure, str(getattr(self, "foraging_pressure_regime", "medium"))
                        )
                    world.record_settlement_progression_metric(f"foraging_retarget_events_pressure_{bucket}")
                set_tick = int(getattr(self, "foraging_target_set_tick", -1))
                if set_tick >= 0:
                    stats = getattr(world, "settlement_progression_stats", {})
                    if isinstance(stats, dict):
                        stats["foraging_commit_before_retarget_ticks_total"] = int(
                            stats.get("foraging_commit_before_retarget_ticks_total", 0)
                        ) + max(0, tick_now - set_tick)
                        stats["foraging_commit_before_retarget_ticks_samples"] = int(
                            stats.get("foraging_commit_before_retarget_ticks_samples", 0)
                        ) + 1
                        world.settlement_progression_stats = stats
                self.foraging_target_set_tick = int(tick_now)
            elif current_target is not None and prev_target is None:
                self.foraging_trip_target = current_target
                self.foraging_target_set_tick = int(tick_now)
        elif prev_task == "gather_food_wild":
            if (
                bool(getattr(self, "foraging_trip_active", False))
                and int(getattr(self, "foraging_trip_harvest_units", 0)) > 0
                and str(task_after_role) != "gather_food_wild"
            ):
                committed_context = switch_context or self._post_first_harvest_switch_context(
                    world,
                    new_task=task_after_role,
                    tick_now=tick_now,
                )
                if hasattr(world, "record_foraging_switch_debug_event"):
                    world.record_foraging_switch_debug_event(
                        self,
                        "post_first_harvest_task_switch_committed",
                        prev_task=prev_task,
                        new_task=task_after_role,
                        reason="task_switched_after_role_update",
                        **committed_context,
                    )
            _finalize_foraging_trip("task_switched")
        if hasattr(world, "record_construction_debug_event"):
            in_construction_context = str(getattr(self, "role", "")) == "builder" or prev_task in {
                "build_house",
                "build_storage",
                "gather_materials",
            } or task_after_role in {"build_house", "build_storage", "gather_materials"}
            if in_construction_context and task_after_role != prev_task:
                reason = "target_recomputed"
                if task_after_role == "survive" or float(getattr(self, "hunger", 100.0)) <= 12.0:
                    reason = "survival_override"
                elif task_after_role == "gather_food_wild":
                    reason = "needs_food"
                elif task_after_role == "rest":
                    reason = "needs_rest"
                elif task_after_role == "gather_materials":
                    reason = "inventory_material_logic"
                elif task_after_role in {"village_logistics", "food_logistics"}:
                    reason = "village_priority_override"
                world.record_construction_debug_event(
                    self,
                    "task_changed",
                    reason=reason,
                    previous_task=prev_task,
                )
                assigned_bid = str(getattr(self, "assigned_building_id", "") or "")
                if assigned_bid and task_after_role not in {"build_house", "build_storage", "gather_materials"}:
                    world.record_construction_debug_event(
                        self,
                        "cleared_site_assignment",
                        reason=reason,
                        previous_task=prev_task,
                        site_id=assigned_bid,
                    )
                if reason == "needs_food":
                    world.record_construction_debug_event(
                        self,
                        "redirected_to_food",
                        reason=reason,
                        previous_task=prev_task,
                    )
                if reason in {"survival_override", "needs_food", "needs_rest"}:
                    self._pause_primary_construction_commitment(world, reason)
        if hasattr(world, "record_behavior_transition"):
            world.record_behavior_transition(prev_task, str(getattr(self, "task", "idle")), x=int(self.x), y=int(self.y))
        if hasattr(world, "record_behavior_activity"):
            world.record_behavior_activity(
                f"task:{str(getattr(self, 'task', 'idle') or 'idle')}",
                x=int(self.x),
                y=int(self.y),
                agent=self,
            )
        if high_pressure and str(getattr(self, "task", "")) != "rest" and hasattr(world, "record_recovery_failure_reason"):
            if float(getattr(self, "hunger", 100.0)) < 25.0:
                world.record_recovery_failure_reason(self, "survival_override", village_uid=uid, role=role_key)
            elif str(getattr(self, "task", "")) == prev_task and prev_task in {"farm_cycle", "build_storage", "build_house", "food_logistics", "village_logistics", "mine_cycle", "lumber_cycle", "gather_food_wild"}:
                world.record_recovery_failure_reason(self, "work_task_retained", village_uid=uid, role=role_key)
            else:
                world.record_recovery_failure_reason(self, "rest_not_selected", village_uid=uid, role=role_key)
        current_role = str(getattr(self, "role", "npc"))
        if current_role in {"farmer", "forager", "hauler", "builder", "miner", "woodcutter"} and hasattr(world, "record_assignment_pipeline_stage"):
            world.record_assignment_pipeline_stage(self, current_role, "task_selected_count")
        if (
            current_role in {"farmer", "forager", "hauler", "builder", "miner", "woodcutter"}
            and str(getattr(self, "task", "")) != prev_task
            and str(prev_task) not in {"idle", "survive", "bootstrap_gather", "bootstrap_build_house", ""}
            and hasattr(world, "record_assignment_pipeline_block_reason")
        ):
            world.record_assignment_pipeline_block_reason(self, current_role, "task_replaced")
        critical_task_map = {
            "build_house": "build_house",
            "build_storage": "build_storage",
            "food_logistics": "construction_delivery",
            "village_logistics": "construction_delivery",
        }
        prev_critical = critical_task_map.get(prev_task)
        if prev_critical and str(getattr(self, "task", "")) != prev_task and hasattr(world, "record_task_completion_interrupted"):
            reason = "survival_override" if (
                str(getattr(self, "task", "")) == "survive"
                or float(getattr(self, "hunger", 100.0)) <= 12.0
            ) else "task_replaced"
            if hasattr(world, "record_construction_debug_event"):
                world.record_construction_debug_event(
                    self,
                    "task_changed",
                    reason=reason,
                    previous_task=prev_task,
                )
                if reason == "survival_override":
                    world.record_construction_debug_event(
                        self,
                        "survival_override",
                        reason=reason,
                        previous_task=prev_task,
                    )
            world.record_task_completion_interrupted(self, prev_critical, reason)
            if prev_critical in {"build_house", "build_storage"} and hasattr(world, "record_situated_construction_event"):
                if reason == "survival_override":
                    world.record_situated_construction_event("construction_interrupted_survival")
                else:
                    world.record_situated_construction_event("construction_interrupted_invalid_target")
            if prev_critical in {"build_house", "build_storage"} and hasattr(world, "record_settlement_progression_metric"):
                if reason == "survival_override":
                    world.record_settlement_progression_metric("construction_progress_stalled_ticks")
                else:
                    world.record_settlement_progression_metric("construction_material_delivery_drift_events")
            if prev_critical == "build_storage" and hasattr(world, "record_settlement_progression_metric"):
                if reason == "survival_override":
                    world.record_settlement_progression_metric("storage_construction_interrupted_survival")
                else:
                    world.record_settlement_progression_metric("storage_construction_interrupted_invalid")
            if prev_critical == "construction_delivery" and hasattr(world, "record_delivery_pipeline_failure"):
                delivery_reason = "task_replaced"
                if str(getattr(self, "role", "")) != "hauler":
                    delivery_reason = "hauler_reassigned"
                world.record_delivery_pipeline_failure(self, delivery_reason)
        if prev_task == "rest" and str(getattr(self, "task", "")) != "rest" and hasattr(world, "record_recovery_failure_reason"):
            world.record_recovery_failure_reason(self, "task_replaced", village_uid=uid, role=role_key)
        self.update_village_affiliation(world)
        self._apply_base_physiology_tick()

        # Eat before decay so stocked villages actually prevent avoidable deaths.
        ate_before_action = self.eat_if_needed(world)

        hunger_decay = float(BASE_HUNGER_DECAY_PER_TICK)
        tick_now = int(getattr(world, "tick", 0))
        if tick_now <= int(EARLY_SURVIVAL_GRACE_TICKS):
            hunger_decay *= float(EARLY_HUNGER_DECAY_MULTIPLIER)
        if (
            tick_now <= int(getattr(world, "EARLY_SURVIVAL_RELIEF_TICKS", 0) or 0)
            and len(getattr(world, "structures", [])) <= 0
            and not any(bool(v.get("formalized", False)) for v in getattr(world, "villages", []))
        ):
            hunger_decay *= float(STARTUP_NO_SHELTER_HUNGER_DECAY_MULTIPLIER)
            if hasattr(world, "record_settlement_progression_metric"):
                world.record_settlement_progression_metric("startup_survival_relief_ticks")
        if hasattr(world, "camp_has_food_for_agent") and world.camp_has_food_for_agent(self, max_distance=3):
            hunger_decay *= float(CAMP_BUFFER_HUNGER_DECAY_MULTIPLIER)
        born_tick = int(getattr(self, "born_tick", tick_now))
        age = max(0, tick_now - born_tick)
        if (
            int(getattr(self, "first_food_relief_tick", -1)) < 0
            and age <= int(EARLY_FOOD_RELIABILITY_TICKS)
        ):
            hunger_decay *= float(PRE_FIRST_FOOD_HUNGER_DECAY_MULTIPLIER)
        self.hunger -= float(hunger_decay)
        if self.hunger <= 0:
            if bool(getattr(self, "foraging_trip_active", False)) and hasattr(world, "record_settlement_progression_metric"):
                world.record_settlement_progression_metric("foraging_trip_terminated_by_hunger_count")
            if bool(getattr(self, "foraging_trip_active", False)):
                _finalize_foraging_trip("hunger_death")
            world.set_agent_dead(self, reason="hunger")
            return
        if float(self.hunger) <= float(HIGH_HUNGER_LATENCY_THRESHOLD):
            if int(getattr(self, "high_hunger_enter_tick", -1)) < 0:
                self.high_hunger_enter_tick = int(tick_now)
                self.high_hunger_episode_count = int(getattr(self, "high_hunger_episode_count", 0)) + 1
                if hasattr(world, "record_settlement_progression_metric"):
                    world.record_settlement_progression_metric("high_hunger_to_eat_events_started")
                if int(getattr(self, "first_food_relief_tick", -1)) >= 0 and hasattr(world, "record_settlement_progression_metric"):
                    world.record_settlement_progression_metric("agent_hunger_relapse_after_first_food_count")
        else:
            self.high_hunger_enter_tick = -1

        action = self.run_brain(world)
        moved = False
        active_work_performed = False
        action_was_move = bool(action and action[0] == "move")
        if hasattr(world, "record_behavior_activity"):
            if action_was_move:
                world.record_behavior_activity("move_decision", x=int(self.x), y=int(self.y), agent=self)
            elif action and action[0] == "wait":
                world.record_behavior_activity("idle_wait", x=int(self.x), y=int(self.y), agent=self)
        move_start_pos = (int(self.x), int(self.y))
        move_target = getattr(self, "task_target", None)
        if move_target is None and isinstance(getattr(self, "current_intention", None), dict):
            tdata = self.current_intention.get("target")
            if isinstance(tdata, dict):
                move_target = (int(tdata.get("x", self.x)), int(tdata.get("y", self.y)))

        if action and action[0] == "move":
            dx = int(action[1])
            dy = int(action[2])

            nx = self.x + dx
            ny = self.y + dy

            walkable = world.is_walkable(nx, ny)
            blocking_agent = None
            occupied = False
            if walkable:
                if hasattr(world, "_agent_at_tile"):
                    blocking_agent = world._agent_at_tile(nx, ny, exclude_agent_id=str(getattr(self, "agent_id", "")))
                    occupied = bool(blocking_agent is not None)
                else:
                    occupied = world.is_occupied(nx, ny)
            if walkable and not occupied:
                self.x = nx
                self.y = ny
                moved = True

                # Roads reduce movement cost: crossing roads can grant a second short step.
                if (self.x, self.y) in getattr(world, "roads", set()):
                    nx2 = self.x + dx
                    ny2 = self.y + dy
                    if world.is_walkable(nx2, ny2) and not world.is_occupied(nx2, ny2):
                        self.x = nx2
                        self.y = ny2

                # le strade emergono solo da insediamenti veri, non dal caos iniziale
                if getattr(self, "village_id", None) is not None:
                    world.record_road_step(self.x, self.y)
            elif walkable and occupied and hasattr(world, "record_movement_blocked_by_agent"):
                world.record_movement_blocked_by_agent(
                    self,
                    from_pos=move_start_pos,
                    to_pos=(int(nx), int(ny)),
                    target=move_target if isinstance(move_target, tuple) and len(move_target) == 2 else None,
                    blocking_agent=blocking_agent,
                )
        if moved:
            self._add_work_fatigue(0.08)
            active_work_performed = True

        if hasattr(world, "record_movement_tick"):
            world.record_movement_tick(
                self,
                from_pos=move_start_pos,
                to_pos=(int(self.x), int(self.y)),
                target=move_target if isinstance(move_target, tuple) and len(move_target) == 2 else None,
                action_was_move=action_was_move,
            )
        if str(getattr(self, "task", "")) == "gather_food_wild" and bool(getattr(self, "foraging_trip_active", False)):
            if bool(action_was_move):
                self.foraging_trip_move_ticks = int(getattr(self, "foraging_trip_move_ticks", 0)) + 1
            active_target = getattr(self, "task_target", None)
            if moved and isinstance(active_target, tuple) and len(active_target) == 2:
                at_target = abs(int(self.x) - int(active_target[0])) + abs(int(self.y) - int(active_target[1])) <= 0
                if at_target:
                    if hasattr(world, "record_settlement_progression_metric"):
                        world.record_settlement_progression_metric("foraging_source_visit_count")
                    if (int(active_target[0]), int(active_target[1])) not in getattr(world, "food", set()):
                        if hasattr(world, "record_settlement_progression_metric"):
                            world.record_settlement_progression_metric("foraging_trip_wasted_arrival_count")
                        nearby_foragers = 0
                        for other in getattr(world, "agents", []):
                            if not getattr(other, "alive", False):
                                continue
                            if str(getattr(other, "agent_id", "")) == str(getattr(self, "agent_id", "")):
                                continue
                            if abs(int(getattr(other, "x", 0)) - int(self.x)) + abs(int(getattr(other, "y", 0)) - int(self.y)) <= 1:
                                if str(getattr(other, "task", "")) in {"gather_food_wild", "farm_cycle"}:
                                    nearby_foragers += 1
                        if nearby_foragers > 0 and hasattr(world, "record_settlement_progression_metric"):
                            world.record_settlement_progression_metric("foraging_arrival_overcontested_count")
                        elif hasattr(world, "record_settlement_progression_metric"):
                            world.record_settlement_progression_metric("foraging_arrival_depleted_source_count")

        if self.last_pos is None:
            self.last_pos = (self.x, self.y)

        if moved:
            self.movement_prev_tile = (int(move_start_pos[0]), int(move_start_pos[1]))
            self.last_pos = (self.x, self.y)
            self.stuck_ticks = 0
        else:
            if self.last_pos == (self.x, self.y):
                self.stuck_ticks += 1
            else:
                self.last_pos = (self.x, self.y)
                self.stuck_ticks = 0

            if self.stuck_ticks >= 3:
                if self._break_stall(world):
                    self.stuck_ticks = 0
                    self.last_pos = (self.x, self.y)

        world.autopickup(self)
        gathered = bool(world.gather_resource(self))
        if gathered:
            if hasattr(world, "record_behavior_activity"):
                world.record_behavior_activity("gather_resource", x=int(self.x), y=int(self.y), agent=self)
            self._add_work_fatigue(0.1)
            active_work_performed = True
        if (
            hasattr(world, "try_direct_material_drop_to_nearby_construction")
            and float(getattr(self, "hunger", 100.0)) >= 20.0
        ):
            moved_local = int(world.try_direct_material_drop_to_nearby_construction(self, max_distance=2))
            if moved_local > 0:
                active_work_performed = True
                if hasattr(world, "record_behavior_activity"):
                    world.record_behavior_activity("construction_material_drop", x=int(self.x), y=int(self.y), agent=self, count=moved_local)

        fatigue_work_penalty = bool(
            float(self.fatigue) >= 85.0
            and str(self.task) in {"farm_cycle", "build_storage", "build_house", "food_logistics", "village_logistics", "gather_materials"}
            and int(getattr(world, "tick", 0)) % 3 == 0
        )

        # azioni guidate da ruolo/task
        if self.task == "farm_cycle" and not fatigue_work_penalty:
            built_farm = world.try_build_farm(self)
            farm_worked = False
            pos = (int(self.x), int(self.y))
            plot = getattr(world, "farm_plots", {}).get(pos)
            on_relevant_farm = bool(isinstance(plot, dict) and plot.get("village_id") == getattr(self, "village_id", None))
            if built_farm or on_relevant_farm:
                if hasattr(world, "record_assignment_pipeline_stage"):
                    world.record_assignment_pipeline_stage(self, "farmer", "action_attempted_count")
                farm_worked = world.work_farm(self)
            if built_farm or farm_worked:
                if hasattr(world, "record_behavior_activity"):
                    world.record_behavior_activity("farm_work", x=int(self.x), y=int(self.y), agent=self)
                self._add_work_fatigue(0.12)
                active_work_performed = True
                if not farm_worked and hasattr(world, "record_workforce_block_reason"):
                    world.record_workforce_block_reason(self, "farmer", "no_valid_task")
            elif hasattr(world, "record_workforce_block_reason"):
                world.record_workforce_block_reason(self, "farmer", "no_target_found")

        elif self.task == "mine_cycle":
            # movement/targeting is handled by brain; gather occurs via world.gather_resource.
            pass

        elif self.task == "lumber_cycle":
            # movement/targeting is handled by brain; gather occurs via world.gather_resource.
            pass

        elif self.task == "build_storage" and not fatigue_work_penalty:
            if hasattr(world, "record_assignment_pipeline_stage"):
                world.record_assignment_pipeline_stage(self, "builder", "action_attempted_count")
            active_storage_site = self._assigned_construction_site(world, expected_type="storage")
            if isinstance(active_storage_site, dict):
                self._set_primary_construction_commitment(world, active_storage_site, reason="builder_assigned_site")
            pre_progress = int(active_storage_site.get("construction_progress", 0)) if isinstance(active_storage_site, dict) else -1
            village = world.get_village_by_id(self.village_id)
            wood_missing = max(0, 4 - int(self.inventory.get("wood", 0)))
            stone_missing = max(0, 2 - int(self.inventory.get("stone", 0)))
            withdrew = False
            if village is not None and (wood_missing > 0 or stone_missing > 0):
                sp = village.get("storage_pos")
                near_storage = bool(
                    isinstance(sp, dict)
                    and abs(int(self.x) - int(sp.get("x", 0))) + abs(int(self.y) - int(sp.get("y", 0))) <= 1
                )
                if near_storage:
                    withdrew = self._withdraw_build_materials(world, wood_need=4, stone_need=2)
                    if not withdrew and hasattr(world, "record_task_completion_preconditions_failed"):
                        world.record_task_completion_preconditions_failed(self, "build_storage", "no_materials_in_inventory")
            built = world.try_build_storage(self)
            if built or withdrew:
                if hasattr(world, "record_behavior_activity"):
                    world.record_behavior_activity("build_storage", x=int(self.x), y=int(self.y), agent=self)
                self._add_work_fatigue(0.12)
                active_work_performed = True
            post_site = self._assigned_construction_site(world, expected_type="storage")
            if isinstance(post_site, dict):
                post_progress = int(post_site.get("construction_progress", 0))
                if post_progress > pre_progress:
                    self.primary_commitment_last_progress_tick = int(getattr(world, "tick", 0))
                self._set_primary_construction_commitment(world, post_site, reason="build_storage_active")
            if built and hasattr(world, "record_local_practice"):
                world.record_local_practice("construction_cluster", x=int(self.x), y=int(self.y), weight=0.9, decay_rate=0.0055)
                world.record_local_practice("stable_storage_area", x=int(self.x), y=int(self.y), weight=0.8, decay_rate=0.005)
            if not built:
                inv_wood = int(self.inventory.get("wood", 0))
                inv_stone = int(self.inventory.get("stone", 0))
                switched_to_gather = False
                builder_just_worked = bool(isinstance(post_site, dict) and pre_progress >= 0 and int(post_site.get("construction_progress", 0)) > int(pre_progress))
                if builder_just_worked:
                    self.task = "build_storage"
                if not withdrew and (inv_wood < int(getattr(building_system, "STORAGE_WOOD_COST", 4)) or inv_stone < int(getattr(building_system, "STORAGE_STONE_COST", 2))):
                    active_site = post_site if isinstance(post_site, dict) else self._assigned_construction_site(world, expected_type="storage")
                    if builder_just_worked or self._should_hold_construction_site_commitment(world, active_site):
                        self.task = "build_storage"
                    else:
                        self.task = "gather_materials"
                        if isinstance(active_site, dict):
                            self.construction_focus_site_id = str(active_site.get("building_id", "") or "")
                            self.construction_focus_tick = int(getattr(world, "tick", 0))
                            self._set_primary_construction_commitment(world, active_site, reason="site_scoped_material_support")
                        switched_to_gather = True
                        if hasattr(world, "record_construction_debug_event"):
                            world.record_construction_debug_event(
                                self,
                                "task_changed",
                                reason="inventory_material_logic",
                                previous_task="build_storage",
                            )
                        if hasattr(world, "record_assignment_pipeline_block_reason"):
                            world.record_assignment_pipeline_block_reason(self, "builder", "materials_not_ready")
                if village is not None:
                    storage = village.get("storage", {})
                    has_active_site = False
                    for b in getattr(world, "buildings", {}).values():
                        if not isinstance(b, dict):
                            continue
                        if str(b.get("type", "")) != "storage":
                            continue
                        if str(b.get("operational_state", "")) != "under_construction":
                            continue
                        if b.get("village_id") == getattr(self, "village_id", None):
                            has_active_site = True
                            break
                    if (
                        not switched_to_gather
                        and not has_active_site
                        and (storage.get("wood", 0) < 4 or storage.get("stone", 0) < 2)
                    ):
                        self.task = "gather_materials"
                        if hasattr(world, "record_construction_debug_event"):
                            world.record_construction_debug_event(
                                self,
                                "task_changed",
                                reason="inventory_material_logic",
                                previous_task="build_storage",
                            )
                    else:
                        self.task = "build_storage"

        elif self.task == "build_house" and not fatigue_work_penalty:
            if hasattr(world, "record_assignment_pipeline_stage"):
                world.record_assignment_pipeline_stage(self, "builder", "action_attempted_count")
            active_house_site = self._assigned_construction_site(world, expected_type="house")
            if isinstance(active_house_site, dict):
                self._set_primary_construction_commitment(world, active_house_site, reason="builder_assigned_site")
            pre_progress = int(active_house_site.get("construction_progress", 0)) if isinstance(active_house_site, dict) else -1
            village = world.get_village_by_id(self.village_id)
            wood_missing = max(0, int(HOUSE_WOOD_COST) - int(self.inventory.get("wood", 0)))
            stone_missing = max(0, int(HOUSE_STONE_COST) - int(self.inventory.get("stone", 0)))
            withdrew = False
            if village is not None and (wood_missing > 0 or stone_missing > 0):
                sp = village.get("storage_pos")
                near_storage = bool(
                    isinstance(sp, dict)
                    and abs(int(self.x) - int(sp.get("x", 0))) + abs(int(self.y) - int(sp.get("y", 0))) <= 1
                )
                if near_storage:
                    withdrew = self._withdraw_build_materials(world, wood_need=HOUSE_WOOD_COST, stone_need=HOUSE_STONE_COST)
                    if not withdrew and hasattr(world, "record_task_completion_preconditions_failed"):
                        world.record_task_completion_preconditions_failed(self, "build_house", "no_materials_in_inventory")
            built_house = bool(world.try_build_house(self))
            if withdrew:
                if hasattr(world, "record_behavior_activity"):
                    world.record_behavior_activity("build_house", x=int(self.x), y=int(self.y), agent=self)
                self._add_work_fatigue(0.12)
                active_work_performed = True
            post_site = self._assigned_construction_site(world, expected_type="house")
            if isinstance(post_site, dict):
                post_progress = int(post_site.get("construction_progress", 0))
                if post_progress > pre_progress:
                    self.primary_commitment_last_progress_tick = int(getattr(world, "tick", 0))
                self._set_primary_construction_commitment(world, post_site, reason="build_house_active")
            if built_house and hasattr(world, "record_local_practice"):
                world.record_local_practice("construction_cluster", x=int(self.x), y=int(self.y), weight=0.75, decay_rate=0.0055)
            if not built_house:
                inv_wood = int(self.inventory.get("wood", 0))
                inv_stone = int(self.inventory.get("stone", 0))
                switched_to_gather = False
                builder_just_worked = bool(isinstance(post_site, dict) and pre_progress >= 0 and int(post_site.get("construction_progress", 0)) > int(pre_progress))
                if builder_just_worked:
                    self.task = "build_house"
                if not withdrew and (inv_wood < int(HOUSE_WOOD_COST) or inv_stone < int(HOUSE_STONE_COST)):
                    active_site = post_site if isinstance(post_site, dict) else self._assigned_construction_site(world, expected_type="house")
                    if builder_just_worked or self._should_hold_construction_site_commitment(world, active_site):
                        self.task = "build_house"
                    else:
                        self.task = "gather_materials"
                        if isinstance(active_site, dict):
                            self.construction_focus_site_id = str(active_site.get("building_id", "") or "")
                            self.construction_focus_tick = int(getattr(world, "tick", 0))
                            self._set_primary_construction_commitment(world, active_site, reason="site_scoped_material_support")
                        switched_to_gather = True
                        if hasattr(world, "record_construction_debug_event"):
                            world.record_construction_debug_event(
                                self,
                                "task_changed",
                                reason="inventory_material_logic",
                                previous_task="build_house",
                            )
                        if hasattr(world, "record_assignment_pipeline_block_reason"):
                            world.record_assignment_pipeline_block_reason(self, "builder", "materials_not_ready")

        elif self.task == "build_road":
            # per ora la strada emerge dal movimento
            pass

        elif self.task == "gather_materials" and not fatigue_work_penalty:
            # builder in attesa di materiali
            if hasattr(world, "record_assignment_pipeline_stage"):
                world.record_assignment_pipeline_stage(self, "builder", "action_attempted_count")
            committed_site = self._construction_commitment_site(world)
            committed_site_id = ""
            committed_site_type = ""
            if isinstance(committed_site, dict) and str(committed_site.get("operational_state", "")) == "under_construction":
                committed_site_id = str(committed_site.get("building_id", "") or "")
                committed_site_type = str(committed_site.get("type", "") or "")
                if committed_site_id:
                    self.construction_focus_site_id = committed_site_id
                    self.construction_focus_tick = int(getattr(world, "tick", 0))
                    try:
                        self.assigned_building_id = committed_site_id
                    except Exception:
                        pass
            delivered = False
            if int(self.inventory.get("wood", 0)) + int(self.inventory.get("stone", 0)) + int(self.inventory.get("food", 0)) > 0:
                try:
                    delivered = bool(building_system.run_hauler_construction_delivery(world, self))
                except Exception:
                    delivered = False
            if delivered:
                self._add_work_fatigue(0.08)
                active_work_performed = True
                if hasattr(world, "record_behavior_activity"):
                    world.record_behavior_activity("construction_delivery", x=int(self.x), y=int(self.y), agent=self)
            if delivered or (int(self.inventory.get("wood", 0)) + int(self.inventory.get("stone", 0)) + int(self.inventory.get("food", 0)) > 0):
                if committed_site_id and committed_site_type == "storage":
                    self.task = "build_storage"
                elif committed_site_id and committed_site_type == "house":
                    self.task = "build_house"
                elif hasattr(world, "has_active_storage_construction_for_agent") and bool(world.has_active_storage_construction_for_agent(self)):
                    self.task = "build_storage"
                    if hasattr(world, "record_construction_debug_event"):
                        world.record_construction_debug_event(
                            self,
                            "redirected_to_storage",
                            reason="inventory_material_logic",
                            previous_task="gather_materials",
                        )
                elif hasattr(world, "has_active_construction_for_agent") and bool(world.has_active_construction_for_agent(self)):
                    self.task = "build_house"
            if hasattr(world, "record_assignment_pipeline_block_reason"):
                world.record_assignment_pipeline_block_reason(self, "builder", "no_task_candidate")

        elif self.task == "food_logistics" and not fatigue_work_penalty:
            if hasattr(world, "record_assignment_pipeline_stage"):
                world.record_assignment_pipeline_stage(self, "hauler", "action_attempted_count")
            try:
                delivered = building_system.run_hauler_construction_delivery(world, self)
                redistributed = False if delivered else building_system.run_hauler_internal_redistribution(world, self)
                transfer_active = bool(getattr(building_system, "has_active_internal_transfer", lambda *_: False)(self))
            except Exception:
                delivered = False
                redistributed = False
                transfer_active = False
            deposited = self._deposit_inventory_to_storage(world)
            if delivered or redistributed or transfer_active or deposited:
                if hasattr(world, "record_behavior_activity"):
                    world.record_behavior_activity("camp_supply_food", x=int(self.x), y=int(self.y), agent=self)
                self._add_work_fatigue(0.1)
                active_work_performed = True
            if not delivered and not redistributed and not transfer_active and not deposited:
                harvested = world.haul_harvest(self)
                farm_worked = world.work_farm(self)
                if harvested or farm_worked:
                    self._add_work_fatigue(0.1)
                    active_work_performed = True
                if not harvested and not farm_worked and hasattr(world, "record_workforce_block_reason"):
                    world.record_workforce_block_reason(self, "hauler", "no_valid_task")

        elif self.task == "village_logistics" and not fatigue_work_penalty:
            if hasattr(world, "record_assignment_pipeline_stage"):
                world.record_assignment_pipeline_stage(self, "hauler", "action_attempted_count")
            try:
                delivered = building_system.run_hauler_construction_delivery(world, self)
                redistributed = False if delivered else building_system.run_hauler_internal_redistribution(world, self)
                transfer_active = bool(getattr(building_system, "has_active_internal_transfer", lambda *_: False)(self))
            except Exception:
                delivered = False
                redistributed = False
                transfer_active = False
            deposited = self._deposit_inventory_to_storage(world)
            if delivered or redistributed or transfer_active or deposited:
                if hasattr(world, "record_behavior_activity"):
                    world.record_behavior_activity("village_logistics", x=int(self.x), y=int(self.y), agent=self)
                self._add_work_fatigue(0.1)
                active_work_performed = True
            if not delivered and not redistributed and not transfer_active and not deposited:
                harvested = world.haul_harvest(self)
                if harvested:
                    self._add_work_fatigue(0.1)
                    active_work_performed = True
                if not harvested and hasattr(world, "record_workforce_block_reason"):
                    world.record_workforce_block_reason(self, "hauler", "no_valid_task")

        elif self.task == "gather_food_wild":
            # niente build casuali
            if hasattr(world, "record_farm_discovery_observation"):
                world.record_farm_discovery_observation(int(self.x), int(self.y), success=False, amount=0)
            if (
                str(getattr(self, "role", "")) in {"forager", "farmer"}
                and float(getattr(self, "hunger", 100.0)) >= 25.0
                and hasattr(world, "is_farmer_task_viable")
                and bool(world.is_farmer_task_viable(self))
            ):
                if bool(world.try_build_farm(self)):
                    if hasattr(world, "record_behavior_activity"):
                        world.record_behavior_activity("farm_work", x=int(self.x), y=int(self.y), agent=self)
                    self._add_work_fatigue(0.08)
                    active_work_performed = True
            if hasattr(world, "record_assignment_pipeline_stage"):
                world.record_assignment_pipeline_stage(self, "forager", "action_attempted_count")
            if hasattr(world, "record_workforce_block_reason"):
                world.record_workforce_block_reason(self, "forager", "no_valid_task")

        elif self.task == "bootstrap_build_house":
            built = world.try_build_house(self)
            if not built:
                # Keep founding behavior coherent: if still funded, keep trying near settlements.
                if (
                    self.inventory.get("wood", 0) >= HOUSE_WOOD_COST
                    and self.inventory.get("stone", 0) >= HOUSE_STONE_COST
                ):
                    if world.structures:
                        self.task_target = min(
                            world.structures,
                            key=lambda p: abs(p[0] - self.x) + abs(p[1] - self.y),
                        )
                    self.task = "bootstrap_build_house"
                else:
                    self.task = "bootstrap_gather"

        elif self.task == "bootstrap_gather":
            # niente build casuali, raccoglie e si muove col brain
            pass

        elif self.task == "camp_supply_food":
            deposited = False
            if hasattr(world, "try_deposit_food_to_local_buffers"):
                deposited = int(world.try_deposit_food_to_local_buffers(self, amount=1, hunger_before=float(self.hunger))) > 0
            elif hasattr(world, "try_deposit_food_to_nearby_camp"):
                deposited = int(world.try_deposit_food_to_nearby_camp(self, amount=1, hunger_before=float(self.hunger))) > 0
            if deposited:
                if hasattr(world, "record_behavior_activity"):
                    world.record_behavior_activity("deposit_food", x=int(self.x), y=int(self.y), agent=self)
                self._add_work_fatigue(0.06)
                active_work_performed = True

        elif self.task == "prototype_attempt":
            if hasattr(world, "get_proto_material_needs_for_agent"):
                needs = world.get_proto_material_needs_for_agent(self)
                if isinstance(needs, dict):
                    self._withdraw_build_materials(
                        world,
                        wood_need=max(0, int(needs.get("wood", 0))),
                        stone_need=max(0, int(needs.get("stone", 0))),
                    )
            if hasattr(world, "run_proto_asset_adoption_attempt"):
                world.run_proto_asset_adoption_attempt(self)

        elif self.task == "survive":
            pass

        if fatigue_work_penalty:
            self._add_work_fatigue(0.03)

        self._apply_recovery(world, active_work=active_work_performed)
        self._update_health_from_stressors()
        self._update_happiness(world, active_work=active_work_performed)

        if not ate_before_action:
            self.eat_if_needed(world)
        self.try_reproduce(world)
        if hasattr(world, "record_behavior_transition"):
            world.record_behavior_transition(task_after_role, str(getattr(self, "task", "idle")), x=int(self.x), y=int(self.y))

    def _break_stall(self, world: "World") -> bool:
        target = self.task_target
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        random.shuffle(dirs)
        options = []

        for dx, dy in dirs:
            nx = self.x + dx
            ny = self.y + dy
            if not world.is_walkable(nx, ny) or world.is_occupied(nx, ny):
                continue

            if target is not None:
                d = abs(target[0] - nx) + abs(target[1] - ny)
                options.append((d, dx, dy))
            else:
                options.append((0, dx, dy))

        if not options:
            return False

        options.sort(key=lambda t: t[0])
        _, dx, dy = options[0]
        self.x += dx
        self.y += dy

        if getattr(self, "village_id", None) is not None:
            world.record_road_step(self.x, self.y)

        return True


def _coord_key(coord: Tuple[int, int]) -> Tuple[int, int]:
    return (coord[1], coord[0])


def _manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _clampf(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


KNOWLEDGE_MAX_ENTRIES_PER_CATEGORY = 12
KNOWLEDGE_DECAY_PER_TICK = 0.0009
KNOWLEDGE_MIN_CONFIDENCE = 0.15
KNOWLEDGE_CONFIRMATION_DECAY_REDUCTION = 0.08
KNOWLEDGE_CONFIRMATION_MAX_REDUCTION = 0.55
KNOWLEDGE_DIRECT_DECAY_REDUCTION = 0.12
KNOWLEDGE_SALIENCE_DECAY_REDUCTION = 0.10
KNOWLEDGE_RECENT_CONFIRMATION_WINDOW = 26
ROUTINE_SUCCESS_EXTENSION_TICKS = 3
KNOWLEDGE_MAX_INVENTIONS = 10
INVENTION_SOCIAL_MIN_CONFIDENCE = 0.35
COMMUNICATION_COOLDOWN_TICKS = 6
COMMUNICATION_MAX_SHARES_PER_DONOR = 2
SHARED_KNOWLEDGE_MAX_AGE_TICKS = 260
SURVIVAL_CRITICAL_HUNGER_FOR_SOCIAL_KNOWLEDGE = 34.0
COGNITIVE_TIER_MIN = 1
COGNITIVE_TIER_MAX = 4
MAX_RECENT_ENCOUNTERS = 32
ENCOUNTER_FAMILIARITY_GAIN = 0.08
ENCOUNTER_FAMILIARITY_DECAY_PER_TICK = 0.005
ENCOUNTER_STALE_TICKS = 220
MAX_FAMILIAR_ACTIVITY_ZONES = 10
FAMILIAR_ZONE_SCORE_GAIN = 0.12
FAMILIAR_ZONE_SCORE_DECAY_PER_TICK = 0.01
FAMILIAR_ZONE_SCORE_MAX = 0.78
FAMILIAR_ZONE_DENSITY_SOFT_CAP = 6
FAMILIAR_ZONE_DENSITY_HARD_CAP = 10
FAMILIAR_ZONE_LOW_PAYOFF_DECAY_BOOST = 0.016
FAMILIAR_ZONE_USEFUL_REFRESH_WINDOW = 4


def _default_self_model() -> Dict[str, float]:
    return {
        "survival_weight": 0.65,
        "social_weight": 0.35,
        "work_weight": 0.50,
        "exploration_weight": 0.30,
        "security_weight": 0.40,
        "stress_level": 0.20,
        "recent_success_bias": 0.50,
        "recent_failure_bias": 0.20,
    }


def _default_cognitive_profile() -> Dict[str, Any]:
    return {
        "llm_enabled": True,
        "cognitive_tier": 1,
        "reflection_budget": 0.55,
        "reflection_cooldown_ticks": 80,
        "last_reflection_tick": -1000,
        "reflection_priority": 0.45,
        "max_context_items": 8,
        "reflection_count": 0,
        "last_reflection_reason": "",
        "last_reflection_outcome": "",
        "reflection_success_count": 0,
        "reflection_fallback_count": 0,
        "reflection_block_reason": "",
        "effective_context_size": 0,
    }


def ensure_agent_cognitive_profile(agent: Agent) -> Dict[str, Any]:
    profile = getattr(agent, "cognitive_profile", None)
    if not isinstance(profile, dict) or not profile:
        profile = _default_cognitive_profile()
        role = str(getattr(agent, "role", "npc"))
        # Universal baseline: no default leader privilege.
        if role in {"builder", "hauler", "miner", "woodcutter"}:
            profile["reflection_priority"] = round(_clampf(float(profile["reflection_priority"]) + 0.02), 3)
        profile["reflection_budget"] = round(_clampf(float(profile["reflection_budget"])), 3)
        profile["reflection_priority"] = round(_clampf(float(profile["reflection_priority"])), 3)
        profile["max_context_items"] = int(max(4, min(18, int(profile["max_context_items"]))))
        agent.cognitive_profile = profile
    return profile


def _default_knowledge_state() -> Dict[str, List[Dict[str, Any]]]:
    return {
        "known_resource_spots": [],
        "known_camp_spots": [],
        "known_useful_buildings": [],
        "known_routes": [],
        "known_practices": [],
        "known_inventions": [],
    }


def ensure_agent_knowledge_state(agent: Agent) -> Dict[str, List[Dict[str, Any]]]:
    state = getattr(agent, "knowledge_state", None)
    if not isinstance(state, dict):
        state = _default_knowledge_state()
        agent.knowledge_state = state
    for key in ("known_resource_spots", "known_camp_spots", "known_useful_buildings", "known_routes", "known_practices", "known_inventions"):
        if not isinstance(state.get(key), list):
            state[key] = []
    return state


def _knowledge_match_key(entry: Dict[str, Any]) -> Tuple[str, str, int, int]:
    loc = entry.get("location", {}) if isinstance(entry.get("location"), dict) else {}
    return (
        str(entry.get("type", "")),
        str(entry.get("subject", "")),
        int(loc.get("x", 0)),
        int(loc.get("y", 0)),
    )


def _upsert_knowledge_entry(
    entries: List[Dict[str, Any]],
    new_entry: Dict[str, Any],
    *,
    confidence_boost: float,
    tick: int,
    max_entries: int = KNOWLEDGE_MAX_ENTRIES_PER_CATEGORY,
) -> None:
    new_key = _knowledge_match_key(new_entry)
    for existing in entries:
        if not isinstance(existing, dict):
            continue
        if _knowledge_match_key(existing) != new_key:
            continue
        existing_conf = float(existing.get("confidence", 0.0))
        existing["confidence"] = round(_clampf(existing_conf + confidence_boost), 3)
        existing["learned_tick"] = int(tick)
        existing["last_confirmed_tick"] = int(tick)
        existing["confirmations"] = int(existing.get("confirmations", 1)) + 1
        existing["salience"] = round(
            _clampf(max(float(existing.get("salience", 0.0)), float(new_entry.get("salience", 0.0)))),
            3,
        )
        source = str(existing.get("source", "social"))
        # Direct confirmation dominates social origin.
        if str(new_entry.get("source", "social")) == "direct":
            existing["source"] = "direct"
        else:
            existing["source"] = source
        return

    payload = {
        "type": str(new_entry.get("type", "")),
        "subject": str(new_entry.get("subject", "")),
        "location": {
            "x": int((new_entry.get("location", {}) if isinstance(new_entry.get("location"), dict) else {}).get("x", 0)),
            "y": int((new_entry.get("location", {}) if isinstance(new_entry.get("location"), dict) else {}).get("y", 0)),
        },
        "learned_tick": int(tick),
        "last_confirmed_tick": int(tick),
        "confirmations": 1,
        "confidence": round(_clampf(float(new_entry.get("confidence", 0.5))), 3),
        "source": str(new_entry.get("source", "direct")),
        "salience": round(_clampf(float(new_entry.get("salience", 0.5))), 3),
    }
    entries.append(payload)
    if len(entries) > int(max_entries):
        entries.sort(
            key=lambda e: (
                float(e.get("confidence", 0.0)),
                int(e.get("learned_tick", 0)),
                float(e.get("salience", 0.0)),
                str(e.get("subject", "")),
            )
        )
        del entries[: len(entries) - int(max_entries)]


def _known_invention_key(entry: Dict[str, Any]) -> Tuple[str, str]:
    return (
        str(entry.get("proposal_id", "")),
        str(entry.get("prototype_id", "")),
    )


def _upsert_known_invention_entry(
    entries: List[Dict[str, Any]],
    new_entry: Dict[str, Any],
    *,
    confidence_boost: float,
    tick: int,
    max_entries: int = KNOWLEDGE_MAX_INVENTIONS,
) -> None:
    entry_key = _known_invention_key(new_entry)
    for existing in entries:
        if not isinstance(existing, dict):
            continue
        if _known_invention_key(existing) != entry_key:
            continue
        existing["learned_tick"] = int(tick)
        existing["last_confirmed_tick"] = int(tick)
        existing["confirmations"] = int(existing.get("confirmations", 1)) + 1
        current_conf = float(existing.get("confidence", 0.0))
        incoming_conf = float(new_entry.get("confidence", 0.5))
        existing["confidence"] = round(_clampf(max(current_conf, incoming_conf) + confidence_boost), 3)
        existing["salience"] = round(
            _clampf(max(float(existing.get("salience", 0.0)), float(new_entry.get("salience", 0.0)))),
            3,
        )
        if str(new_entry.get("source", "social")) == "direct":
            existing["source"] = "direct"
        if str(new_entry.get("usefulness_status", "unknown")) in {"useful", "neutral", "ineffective"}:
            existing["usefulness_status"] = str(new_entry.get("usefulness_status", "unknown"))
        return

    loc = new_entry.get("location", {}) if isinstance(new_entry.get("location"), dict) else {}
    payload = {
        "proposal_id": str(new_entry.get("proposal_id", "")),
        "prototype_id": str(new_entry.get("prototype_id", "")),
        "inventor_agent_id": str(new_entry.get("inventor_agent_id", "")),
        "category": str(new_entry.get("category", "")),
        "intended_effects": [str(e) for e in list(new_entry.get("intended_effects", []))[:3] if str(e)],
        "location": {"x": int(loc.get("x", 0)), "y": int(loc.get("y", 0))},
        "learned_tick": int(tick),
        "last_confirmed_tick": int(tick),
        "confirmations": 1,
        "confidence": round(_clampf(float(new_entry.get("confidence", 0.5))), 3),
        "source": str(new_entry.get("source", "direct")),
        "usefulness_status": str(new_entry.get("usefulness_status", "unknown")),
        "salience": round(_clampf(float(new_entry.get("salience", 0.5))), 3),
    }
    entries.append(payload)
    if len(entries) > int(max_entries):
        entries.sort(
            key=lambda e: (
                float(e.get("confidence", 0.0)),
                int(e.get("learned_tick", 0)),
                float(e.get("salience", 0.0)),
                str(e.get("proposal_id", "")),
            )
        )
        del entries[: len(entries) - int(max_entries)]


def update_agent_knowledge_from_experience(world: "World", agent: Agent) -> None:
    state = ensure_agent_knowledge_state(agent)
    tick = int(getattr(world, "tick", 0))
    recent_events = get_recent_memory_events(agent, limit=18)
    resource_entries = state["known_resource_spots"]
    camp_entries = state["known_camp_spots"]
    building_entries = state["known_useful_buildings"]
    practice_entries = state["known_practices"]

    for ev in recent_events:
        if not isinstance(ev, dict):
            continue
        etype = str(ev.get("type", ""))
        outcome = str(ev.get("outcome", ""))
        loc = ev.get("location", {})
        if not isinstance(loc, dict):
            continue
        x = int(loc.get("x", agent.x))
        y = int(loc.get("y", agent.y))
        sal = _clampf(float(ev.get("salience", 0.5)))
        if outcome == "success" and etype in {"found_resource", "hunger_relief"}:
            res = str(ev.get("resource_type", "food" if etype == "hunger_relief" else ""))
            if res in {"food", "wood", "stone"}:
                _upsert_knowledge_entry(
                    resource_entries,
                    {
                        "type": "resource_spot",
                        "subject": res,
                        "location": {"x": x, "y": y},
                        "confidence": 0.72,
                        "source": "direct",
                        "salience": sal,
                    },
                    confidence_boost=0.10,
                    tick=tick,
                )

        if outcome == "success" and etype in {"useful_building", "construction_progress", "delivered_material"}:
            btype = str(ev.get("building_type", "storage" if etype == "delivered_material" else ""))
            subject = btype if btype else "site"
            _upsert_knowledge_entry(
                building_entries,
                {
                    "type": "useful_building",
                    "subject": subject,
                    "location": {"x": x, "y": y},
                    "confidence": 0.68,
                    "source": "direct",
                    "salience": sal,
                },
                confidence_boost=0.08,
                tick=tick,
            )
            practice_subject = "deliver_to_storage" if etype == "delivered_material" else "construction_cycle"
            _upsert_knowledge_entry(
                practice_entries,
                {
                    "type": "practice",
                    "subject": practice_subject,
                    "location": {"x": x, "y": y},
                    "confidence": 0.66,
                    "source": "direct",
                    "salience": sal,
                },
                confidence_boost=0.05,
                tick=tick,
            )

        if outcome == "failure" and etype == "failed_resource_search":
            res = str(ev.get("resource_type", ""))
            for entry in resource_entries:
                if not isinstance(entry, dict):
                    continue
                if str(entry.get("subject", "")) != res:
                    continue
                lloc = entry.get("location", {})
                if not isinstance(lloc, dict):
                    continue
                if _manhattan((x, y), (int(lloc.get("x", 0)), int(lloc.get("y", 0)))) <= 2:
                    prior = float(entry.get("confidence", 0.0))
                    updated = _clampf(prior - 0.12)
                    entry["confidence"] = round(updated, 3)
                    if (
                        prior >= KNOWLEDGE_MIN_CONFIDENCE
                        and updated < KNOWLEDGE_MIN_CONFIDENCE
                        and str(entry.get("source", "")) == "direct"
                        and hasattr(world, "record_direct_memory_invalidation")
                    ):
                        world.record_direct_memory_invalidation(1)

    # Direct local camp observation becomes lightweight reusable knowledge.
    if hasattr(world, "nearest_active_camp_for_agent"):
        camp = world.nearest_active_camp_for_agent(agent, max_distance=8)
        if isinstance(camp, dict):
            _upsert_knowledge_entry(
                camp_entries,
                {
                    "type": "camp_spot",
                    "subject": "camp",
                    "location": {"x": int(camp.get("x", agent.x)), "y": int(camp.get("y", agent.y))},
                    "confidence": 0.72,
                    "source": "direct",
                    "salience": 0.62,
                },
                confidence_boost=0.08,
                tick=tick,
            )

    # Invalidate known camp spots when directly contradicted by local reality.
    keep_camps: List[Dict[str, Any]] = []
    for entry in camp_entries:
        if not isinstance(entry, dict):
            continue
        loc = entry.get("location", {})
        if not isinstance(loc, dict):
            continue
        ex, ey = int(loc.get("x", 0)), int(loc.get("y", 0))
        dist = _manhattan((int(agent.x), int(agent.y)), (ex, ey))
        if dist > 3:
            keep_camps.append(entry)
            continue
        active_present = False
        for camp in (getattr(world, "camps", {}) or {}).values():
            if not isinstance(camp, dict):
                continue
            if not bool(camp.get("active", False)):
                continue
            cx, cy = int(camp.get("x", 0)), int(camp.get("y", 0))
            if _manhattan((cx, cy), (ex, ey)) <= 2:
                active_present = True
                break
        if active_present:
            keep_camps.append(entry)
            continue
        decayed = _clampf(float(entry.get("confidence", 0.0)) - 0.18)
        entry["confidence"] = round(decayed, 3)
        if decayed >= KNOWLEDGE_MIN_CONFIDENCE:
            keep_camps.append(entry)
        elif str(entry.get("source", "")) == "direct" and hasattr(world, "record_direct_memory_invalidation"):
            world.record_direct_memory_invalidation(1)
        elif str(entry.get("source", "")) == "social" and hasattr(world, "record_invalidated_shared_knowledge"):
            world.record_invalidated_shared_knowledge(1)
    state["known_camp_spots"] = keep_camps[:KNOWLEDGE_MAX_ENTRIES_PER_CATEGORY]


def update_agent_invention_knowledge_from_observation(world: "World", agent: Agent) -> None:
    state = ensure_agent_knowledge_state(agent)
    inventions = state.get("known_inventions", [])
    if not isinstance(inventions, list):
        inventions = []
        state["known_inventions"] = inventions
    tick = int(getattr(world, "tick", 0))
    ax, ay = int(getattr(agent, "x", 0)), int(getattr(agent, "y", 0))

    prototypes = getattr(world, "proto_asset_prototypes", []) or []
    for proto in prototypes:
        if not isinstance(proto, dict):
            continue
        if str(proto.get("status", "")) != "prototype_built":
            continue
        loc = proto.get("location", {})
        if not isinstance(loc, dict):
            continue
        px = int(loc.get("x", 0))
        py = int(loc.get("y", 0))
        if _manhattan((ax, ay), (px, py)) > 4:
            continue
        if str(proto.get("usefulness_status", "")) == "ineffective":
            for entry in inventions:
                if not isinstance(entry, dict):
                    continue
                if str(entry.get("proposal_id", "")) != str(proto.get("proposal_id", "")):
                    continue
                entry["usefulness_status"] = "ineffective"
                entry["confidence"] = round(
                    _clampf(float(entry.get("confidence", 0.0)) - 0.10),
                    3,
                )
                entry["learned_tick"] = int(tick)
            continue
        if str(proto.get("usefulness_status", "")) != "useful":
            continue
        _upsert_known_invention_entry(
            inventions,
            {
                "proposal_id": str(proto.get("proposal_id", "")),
                "prototype_id": str(proto.get("instance_id", "")),
                "inventor_agent_id": str(proto.get("inventor_agent_id", "")),
                "category": str(proto.get("category", "")),
                "intended_effects": [str(proto.get("effect", ""))] if str(proto.get("effect", "")) else [],
                "location": {"x": px, "y": py},
                "confidence": 0.78,
                "source": "direct",
                "usefulness_status": "useful",
                "salience": 0.72,
            },
            confidence_boost=0.08,
            tick=tick,
            max_entries=KNOWLEDGE_MAX_INVENTIONS,
        )

    recent_useful_seen = get_recent_memory_events(agent, event_type="useful_prototype_seen", limit=8)
    by_instance = {
        str(proto.get("instance_id", "")): proto
        for proto in prototypes
        if isinstance(proto, dict) and str(proto.get("status", "")) == "prototype_built"
    }
    for ev in recent_useful_seen:
        if not isinstance(ev, dict):
            continue
        target_id = str(ev.get("target_id", ""))
        proto = by_instance.get(target_id)
        if not isinstance(proto, dict) or str(proto.get("usefulness_status", "")) != "useful":
            continue
        loc = ev.get("location", {})
        if not isinstance(loc, dict):
            loc = proto.get("location", {})
        if not isinstance(loc, dict):
            continue
        _upsert_known_invention_entry(
            inventions,
            {
                "proposal_id": str(proto.get("proposal_id", "")),
                "prototype_id": str(proto.get("instance_id", "")),
                "inventor_agent_id": str(proto.get("inventor_agent_id", "")),
                "category": str(proto.get("category", "")),
                "intended_effects": [str(proto.get("effect", ""))] if str(proto.get("effect", "")) else [],
                "location": {"x": int(loc.get("x", ax)), "y": int(loc.get("y", ay))},
                "confidence": 0.70,
                "source": "direct",
                "usefulness_status": "useful",
                "salience": 0.65,
            },
            confidence_boost=0.06,
            tick=tick,
            max_entries=KNOWLEDGE_MAX_INVENTIONS,
        )


def diffuse_invention_knowledge(world: "World", agent: Agent) -> None:
    state = ensure_agent_knowledge_state(agent)
    local_entries = state.get("known_inventions", [])
    if not isinstance(local_entries, list):
        local_entries = []
        state["known_inventions"] = local_entries
    subjective = getattr(agent, "subjective_state", {})
    nearby_agents = subjective.get("nearby_agents", []) if isinstance(subjective, dict) else []
    if not isinstance(nearby_agents, list) or not nearby_agents:
        return
    by_id = {str(getattr(a, "agent_id", "")): a for a in getattr(world, "agents", []) if getattr(a, "alive", False)}
    known_agents = (getattr(agent, "social_memory", {}) or {}).get("known_agents", {})
    tick = int(getattr(world, "tick", 0))

    for near in sorted(
        [n for n in nearby_agents if isinstance(n, dict)],
        key=lambda n: (int(n.get("distance", 999)), str(n.get("agent_id", ""))),
    ):
        aid = str(near.get("agent_id", ""))
        donor = by_id.get(aid)
        if donor is None:
            continue
        donor_state = ensure_agent_knowledge_state(donor)
        donor_entries = donor_state.get("known_inventions", [])
        if not isinstance(donor_entries, list) or not donor_entries:
            continue

        familiarity = 0.0
        if isinstance(known_agents, dict):
            rec = known_agents.get(aid, {})
            if isinstance(rec, dict):
                familiarity = min(1.0, float(rec.get("times_seen", 0)) / 8.0)
        encounter_familiarity = 0.0
        encounter_memory = getattr(agent, "recent_encounters", {})
        if isinstance(encounter_memory, dict):
            enc = encounter_memory.get(aid, {})
            if isinstance(enc, dict):
                encounter_familiarity = _clampf(float(enc.get("familiarity_score", 0.0)))
        same_village = bool(near.get("same_village", False))
        donor_infl = _clampf(float(getattr(donor, "social_influence", 0.0)))
        trust = 0.24 + (0.24 if same_village else 0.0) + familiarity * 0.24 + encounter_familiarity * 0.12 + donor_infl * 0.22
        if encounter_familiarity >= 0.35 and hasattr(world, "record_social_encounter_event"):
            world.record_social_encounter_event("familiar_communication_bonus_applied")
        if trust < 0.54:
            continue
        candidates = [
            e for e in donor_entries
            if isinstance(e, dict)
            and str(e.get("usefulness_status", "")) == "useful"
            and float(e.get("confidence", 0.0)) >= 0.55
        ]
        if not candidates:
            continue
        candidates.sort(
            key=lambda e: (
                -float(e.get("confidence", 0.0)),
                -float(e.get("salience", 0.0)),
                -int(e.get("learned_tick", 0)),
                str(e.get("proposal_id", "")),
            )
        )
        chosen = candidates[0]
        base_conf = _clampf(float(chosen.get("confidence", 0.6)) * 0.72)
        _upsert_known_invention_entry(
            local_entries,
            {
                "proposal_id": str(chosen.get("proposal_id", "")),
                "prototype_id": str(chosen.get("prototype_id", "")),
                "inventor_agent_id": str(chosen.get("inventor_agent_id", "")),
                "category": str(chosen.get("category", "")),
                "intended_effects": list(chosen.get("intended_effects", [])),
                "location": dict(chosen.get("location", {})) if isinstance(chosen.get("location"), dict) else {"x": int(agent.x), "y": int(agent.y)},
                "confidence": min(base_conf, float(chosen.get("confidence", 0.6)) - 0.05),
                "source": "social",
                "usefulness_status": "useful",
                "salience": _clampf(float(chosen.get("salience", 0.5)) * 0.88),
            },
            confidence_boost=0.03,
            tick=tick,
            max_entries=KNOWLEDGE_MAX_INVENTIONS,
        )


def diffuse_local_knowledge(world: "World", agent: Agent) -> None:
    state = ensure_agent_knowledge_state(agent)
    subjective = getattr(agent, "subjective_state", {})
    nearby_agents = subjective.get("nearby_agents", []) if isinstance(subjective, dict) else []
    if not isinstance(nearby_agents, list) or not nearby_agents:
        return

    by_id = {str(getattr(a, "agent_id", "")): a for a in getattr(world, "agents", []) if getattr(a, "alive", False)}
    known_agents = (getattr(agent, "social_memory", {}) or {}).get("known_agents", {})
    tick = int(getattr(world, "tick", 0))

    for near in sorted(
        [n for n in nearby_agents if isinstance(n, dict)],
        key=lambda n: (int(n.get("distance", 999)), str(n.get("agent_id", ""))),
    ):
        aid = str(near.get("agent_id", ""))
        donor = by_id.get(aid)
        if donor is None:
            continue
        donor_state = ensure_agent_knowledge_state(donor)

        familiarity = 0.0
        donor_record: Dict[str, Any] = {}
        if isinstance(known_agents, dict):
            rec = known_agents.get(aid, {})
            if isinstance(rec, dict):
                donor_record = rec
                familiarity = min(1.0, float(rec.get("times_seen", 0)) / 8.0)
        encounter_familiarity = 0.0
        encounter_memory = getattr(agent, "recent_encounters", {})
        if isinstance(encounter_memory, dict):
            enc = encounter_memory.get(aid, {})
            if isinstance(enc, dict):
                encounter_familiarity = _clampf(float(enc.get("familiarity_score", 0.0)))
        if int(tick - int(donor_record.get("last_knowledge_share_tick", -10_000))) < int(COMMUNICATION_COOLDOWN_TICKS):
            continue
        same_village = bool(near.get("same_village", False))
        donor_infl = _clampf(float(getattr(donor, "social_influence", 0.0)))
        trust = 0.25 + (0.25 if same_village else 0.0) + familiarity * 0.24 + encounter_familiarity * 0.12 + donor_infl * 0.2
        if encounter_familiarity >= 0.35 and hasattr(world, "record_social_encounter_event"):
            world.record_social_encounter_event("familiar_communication_bonus_applied")
        if trust < 0.52:
            continue

        shared_count = 0
        shared_any = False
        survival_hunger = float(getattr(agent, "hunger", 100.0))
        nearby_resources = (subjective.get("nearby_resources", {}) if isinstance(subjective, dict) else {})
        known_recent_keys = set()
        if isinstance(donor_record, dict):
            recent_keys_raw = donor_record.get("recent_shared_knowledge_keys", [])
            if isinstance(recent_keys_raw, list):
                for item in recent_keys_raw:
                    if not isinstance(item, dict):
                        continue
                    key = str(item.get("key", ""))
                    seen_tick = int(item.get("tick", -10_000))
                    if key and (tick - seen_tick) <= 24:
                        known_recent_keys.add(key)
        for category in ("known_resource_spots", "known_camp_spots", "known_useful_buildings", "known_practices"):
            if shared_count >= int(COMMUNICATION_MAX_SHARES_PER_DONOR):
                break
            donor_entries = donor_state.get(category, [])
            if not isinstance(donor_entries, list) or not donor_entries:
                continue
            candidates: List[Dict[str, Any]] = []
            for e in donor_entries:
                if not isinstance(e, dict):
                    continue
                conf = float(e.get("confidence", 0.0))
                if conf < 0.55:
                    continue
                age = tick - int(e.get("learned_tick", tick))
                if age > int(SHARED_KNOWLEDGE_MAX_AGE_TICKS):
                    if hasattr(world, "record_social_knowledge_decision"):
                        world.record_social_knowledge_decision(accepted=False, reason="stale", subject=str(e.get("subject", "")))
                    continue
                loc = e.get("location", {})
                if not isinstance(loc, dict):
                    continue
                ex = int(loc.get("x", agent.x))
                ey = int(loc.get("y", agent.y))
                dist = _manhattan((int(agent.x), int(agent.y)), (ex, ey))
                max_dist = 12
                if category == "known_resource_spots":
                    max_dist = 9 if survival_hunger <= SURVIVAL_CRITICAL_HUNGER_FOR_SOCIAL_KNOWLEDGE else 14
                elif category == "known_camp_spots":
                    # Keep camp payload conservative unless very plausible and fresh.
                    max_dist = 10
                    if age > 120 or conf < 0.72:
                        if hasattr(world, "record_camp_knowledge_share_suppressed"):
                            world.record_camp_knowledge_share_suppressed(1)
                        continue
                if dist > max_dist:
                    if hasattr(world, "record_social_knowledge_decision"):
                        world.record_social_knowledge_decision(accepted=False, reason="too_far", subject=str(e.get("subject", "")))
                    continue
                if category == "known_resource_spots":
                    subj = str(e.get("subject", ""))
                    perceived = nearby_resources.get(subj, []) if isinstance(nearby_resources, dict) else []
                    has_direct_alt = bool(
                        isinstance(perceived, list)
                        and any(
                            isinstance(p, dict)
                            and _manhattan((int(agent.x), int(agent.y)), (int(p.get("x", agent.x)), int(p.get("y", agent.y)))) <= 5
                            for p in perceived
                        )
                    )
                    if has_direct_alt:
                        if hasattr(world, "record_social_knowledge_decision"):
                            world.record_social_knowledge_decision(accepted=False, reason="lower_than_direct", subject=subj)
                        if hasattr(world, "record_direct_overrides_social"):
                            world.record_direct_overrides_social(1)
                        continue
                    if survival_hunger <= SURVIVAL_CRITICAL_HUNGER_FOR_SOCIAL_KNOWLEDGE and (dist > 7 or conf < 0.72):
                        if hasattr(world, "record_social_knowledge_decision"):
                            world.record_social_knowledge_decision(accepted=False, reason="survival_priority", subject=subj)
                        continue
                candidates.append(e)
            if not candidates:
                continue
            candidates.sort(
                key=lambda e: (
                    -float(e.get("confidence", 0.0)),
                    -float(e.get("salience", 0.0)),
                    -int(e.get("learned_tick", 0)),
                    str(e.get("subject", "")),
                )
            )
            chosen = candidates[0]
            chosen_loc = chosen.get("location", {}) if isinstance(chosen.get("location"), dict) else {}
            chosen_key = f"{category}:{str(chosen.get('subject', ''))}:{int(chosen_loc.get('x', 0))}:{int(chosen_loc.get('y', 0))}"
            if chosen_key in known_recent_keys:
                if hasattr(world, "record_duplicate_share_suppressed"):
                    world.record_duplicate_share_suppressed(1)
                continue
            receiver_entries = state.get(category, [])
            if isinstance(receiver_entries, list):
                duplicate_receiver = next(
                    (
                        rec
                        for rec in receiver_entries
                        if isinstance(rec, dict)
                        and _knowledge_match_key(rec) == _knowledge_match_key(chosen)
                    ),
                    None,
                )
                if isinstance(duplicate_receiver, dict):
                    rec_conf = float(duplicate_receiver.get("confidence", 0.0))
                    rec_source = str(duplicate_receiver.get("source", ""))
                    if rec_source == "direct" and rec_conf >= (float(chosen.get("confidence", 0.0)) - 0.03):
                        if hasattr(world, "record_social_knowledge_decision"):
                            world.record_social_knowledge_decision(
                                accepted=False,
                                reason="lower_than_direct",
                                subject=str(chosen.get("subject", "")),
                            )
                        continue
            _upsert_knowledge_entry(
                state[category],
                {
                    "type": str(chosen.get("type", "")),
                    "subject": str(chosen.get("subject", "")),
                    "location": dict(chosen.get("location", {})) if isinstance(chosen.get("location"), dict) else {"x": int(agent.x), "y": int(agent.y)},
                    "confidence": _clampf(float(chosen.get("confidence", 0.6)) * 0.82),
                    "source": "social",
                    "salience": _clampf(float(chosen.get("salience", 0.5)) * 0.9),
                },
                confidence_boost=0.03,
                tick=tick,
            )
            shared_count += 1
            shared_any = True
            if hasattr(world, "record_social_knowledge_decision"):
                world.record_social_knowledge_decision(accepted=True, subject=str(chosen.get("subject", "")))
            if hasattr(world, "record_communication_event"):
                if category == "known_resource_spots":
                    world.record_communication_event("food" if str(chosen.get("subject", "")) == "food" else "resource")
                elif category == "known_camp_spots":
                    world.record_communication_event("camp")
                else:
                    world.record_communication_event("other")
            if hasattr(world, "record_behavior_activity"):
                world.record_behavior_activity("communication_event", x=int(agent.x), y=int(agent.y), agent=agent)
            known_recent_keys.add(chosen_key)
        if shared_any and isinstance(donor_record, dict):
            donor_record["last_knowledge_share_tick"] = int(tick)
            donor_record["recent_shared_knowledge_keys"] = [
                {"key": key, "tick": int(tick)} for key in sorted(known_recent_keys)
            ][:12]


def decay_agent_knowledge_state(world: "World", agent: Agent) -> None:
    state = ensure_agent_knowledge_state(agent)
    tick = int(getattr(world, "tick", 0))
    for category in ("known_resource_spots", "known_camp_spots", "known_useful_buildings", "known_routes", "known_practices", "known_inventions"):
        entries = state.get(category, [])
        if not isinstance(entries, list):
            continue
        kept: List[Dict[str, Any]] = []
        expired = 0
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            learned_tick = int(entry.get("learned_tick", tick))
            age = max(0, tick - learned_tick)
            confirmations = max(1, int(entry.get("confirmations", 1)))
            recent_confirmation = max(0, tick - int(entry.get("last_confirmed_tick", learned_tick))) <= int(
                KNOWLEDGE_RECENT_CONFIRMATION_WINDOW
            )
            decay_rate = KNOWLEDGE_DECAY_PER_TICK
            if category == "known_inventions":
                decay_rate = KNOWLEDGE_DECAY_PER_TICK * (1.25 if str(entry.get("source", "social")) == "social" else 0.9)
                if str(entry.get("usefulness_status", "")) == "ineffective":
                    decay_rate *= 1.7
            retention_bonus = min(
                float(KNOWLEDGE_CONFIRMATION_MAX_REDUCTION),
                float(max(0, confirmations - 1)) * float(KNOWLEDGE_CONFIRMATION_DECAY_REDUCTION),
            )
            if str(entry.get("source", "social")) == "direct":
                retention_bonus += float(KNOWLEDGE_DIRECT_DECAY_REDUCTION)
            if float(entry.get("salience", 0.0)) >= 0.7:
                retention_bonus += float(KNOWLEDGE_SALIENCE_DECAY_REDUCTION)
            if recent_confirmation:
                retention_bonus += 0.06
            effective_decay = decay_rate * max(0.18, 1.0 - retention_bonus)
            decayed = _clampf(float(entry.get("confidence", 0.0)) - age * effective_decay)
            entry["confidence"] = round(decayed, 3)
            if (
                confirmations >= 2
                and int(entry.get("last_confirmed_tick", -1)) == int(tick)
                and hasattr(world, "record_confirmed_memory_reinforcement")
            ):
                world.record_confirmed_memory_reinforcement(1)
            min_conf = KNOWLEDGE_MIN_CONFIDENCE if category != "known_inventions" else min(KNOWLEDGE_MIN_CONFIDENCE, INVENTION_SOCIAL_MIN_CONFIDENCE)
            if decayed >= min_conf:
                kept.append(entry)
            else:
                expired += 1
                if str(entry.get("source", "")) == "direct" and hasattr(world, "record_direct_memory_invalidation"):
                    world.record_direct_memory_invalidation(1)
        kept.sort(
            key=lambda e: (
                -float(e.get("confidence", 0.0)),
                -float(e.get("salience", 0.0)),
                -int(e.get("learned_tick", 0)),
                str(e.get("subject", e.get("proposal_id", ""))),
            )
        )
        limit = KNOWLEDGE_MAX_ENTRIES_PER_CATEGORY if category != "known_inventions" else KNOWLEDGE_MAX_INVENTIONS
        state[category] = kept[:limit]
        if expired > 0 and hasattr(world, "record_stale_knowledge_expired"):
            world.record_stale_knowledge_expired(expired)


def get_known_resource_spot(
    agent: Agent,
    resource_type: str,
    *,
    min_confidence: float = 0.35,
    world: Optional["World"] = None,
) -> Optional[Tuple[int, int]]:
    world_ref = world if world is not None else getattr(agent, "_world_ref", None)
    state = ensure_agent_knowledge_state(agent)
    entries = state.get("known_resource_spots", [])
    if not isinstance(entries, list):
        return None
    candidates = [
        e for e in entries
        if isinstance(e, dict)
        and str(e.get("subject", "")) == str(resource_type)
        and float(e.get("confidence", 0.0)) >= float(min_confidence)
        and isinstance(e.get("location"), dict)
    ]
    if not candidates:
        return None
    hunger = float(getattr(agent, "hunger", 100.0))
    social_candidates: List[Dict[str, Any]] = []
    direct_candidates: List[Dict[str, Any]] = []
    for e in candidates:
        source = str(e.get("source", ""))
        loc = e.get("location", {}) if isinstance(e.get("location"), dict) else {}
        dist = _manhattan((int(agent.x), int(agent.y)), (int(loc.get("x", agent.x)), int(loc.get("y", agent.y))))
        if source == "social":
            if hunger <= SURVIVAL_CRITICAL_HUNGER_FOR_SOCIAL_KNOWLEDGE and (dist > 7 or float(e.get("confidence", 0.0)) < 0.72):
                if hasattr(world_ref, "record_social_knowledge_decision"):
                    world_ref.record_social_knowledge_decision(accepted=False, reason="survival_priority", subject=str(resource_type))
                continue
            social_candidates.append(e)
        else:
            direct_candidates.append(e)
    nearby_resources = (
        getattr(agent, "subjective_state", {}).get("nearby_resources", {})
        if isinstance(getattr(agent, "subjective_state", {}), dict)
        else {}
    )
    perceived = nearby_resources.get(str(resource_type), []) if isinstance(nearby_resources, dict) else []
    if isinstance(perceived, list):
        direct_perceived = [
            (int(p.get("x", agent.x)), int(p.get("y", agent.y)))
            for p in perceived
            if isinstance(p, dict)
        ]
        if direct_perceived:
            best_direct = min(direct_perceived, key=lambda t: _manhattan((int(agent.x), int(agent.y)), t))
            if social_candidates and hasattr(world_ref, "record_direct_overrides_social"):
                world_ref.record_direct_overrides_social(1)
            return best_direct
    prioritized = direct_candidates if direct_candidates else social_candidates
    if not prioritized:
        return None
    prioritized.sort(
        key=lambda e: (
            -float(e.get("confidence", 0.0)),
            -float(e.get("salience", 0.0)),
            -int(e.get("learned_tick", 0)),
            _manhattan(
                (int(agent.x), int(agent.y)),
                (
                    int((e.get("location") or {}).get("x", agent.x)),
                    int((e.get("location") or {}).get("y", agent.y)),
                ),
            ),
        )
    )
    chosen = prioritized[0]
    loc = chosen.get("location", {})
    if (
        str(chosen.get("source", "")) == "social"
        and world_ref is not None
        and hasattr(world_ref, "record_shared_knowledge_used")
    ):
        world_ref.record_shared_knowledge_used("food")
    return (int(loc.get("x", 0)), int(loc.get("y", 0)))


def get_known_useful_building_target(
    agent: Agent,
    allowed_types: Set[str],
    *,
    min_confidence: float = 0.35,
) -> Optional[Tuple[int, int]]:
    state = ensure_agent_knowledge_state(agent)
    entries = state.get("known_useful_buildings", [])
    if not isinstance(entries, list):
        return None
    allowed = {str(t) for t in allowed_types}
    candidates = [
        e for e in entries
        if isinstance(e, dict)
        and str(e.get("subject", "")) in allowed
        and float(e.get("confidence", 0.0)) >= float(min_confidence)
        and isinstance(e.get("location"), dict)
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda e: (
            -float(e.get("confidence", 0.0)),
            -float(e.get("salience", 0.0)),
            -int(e.get("learned_tick", 0)),
            str(e.get("subject", "")),
        )
    )
    loc = candidates[0].get("location", {})
    return (int(loc.get("x", 0)), int(loc.get("y", 0)))


def get_known_camp_spot(
    agent: Agent,
    *,
    min_confidence: float = 0.35,
    max_age_ticks: int = SHARED_KNOWLEDGE_MAX_AGE_TICKS,
    world: Optional["World"] = None,
) -> Optional[Tuple[int, int]]:
    world_ref = world if world is not None else getattr(agent, "_world_ref", None)
    state = ensure_agent_knowledge_state(agent)
    entries = state.get("known_camp_spots", [])
    if not isinstance(entries, list):
        return None
    tick = int(getattr(world_ref, "tick", 0)) if world_ref is not None else None
    candidates: List[Dict[str, Any]] = []
    hunger = float(getattr(agent, "hunger", 100.0))
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("subject", "")) != "camp":
            continue
        if float(entry.get("confidence", 0.0)) < float(min_confidence):
            continue
        if not isinstance(entry.get("location"), dict):
            continue
        if isinstance(tick, int):
            age = max(0, int(tick) - int(entry.get("learned_tick", tick)))
            if age > int(max_age_ticks):
                continue
        loc = entry.get("location", {}) if isinstance(entry.get("location"), dict) else {}
        dist = _manhattan((int(agent.x), int(agent.y)), (int(loc.get("x", agent.x)), int(loc.get("y", agent.y))))
        source = str(entry.get("source", ""))
        if source == "social":
            if float(entry.get("confidence", 0.0)) < 0.72:
                continue
            if dist > 10:
                continue
            if hunger <= SURVIVAL_CRITICAL_HUNGER_FOR_SOCIAL_KNOWLEDGE and dist > 6:
                if hasattr(world_ref, "record_social_knowledge_decision"):
                    world_ref.record_social_knowledge_decision(accepted=False, reason="survival_priority", subject="camp")
                continue
        candidates.append(entry)
    if not candidates:
        return None
    candidates.sort(
        key=lambda e: (
            -float(e.get("confidence", 0.0)),
            -float(e.get("salience", 0.0)),
            -int(e.get("learned_tick", 0)),
            int((e.get("location") or {}).get("y", 0)),
            int((e.get("location") or {}).get("x", 0)),
        )
    )
    chosen = candidates[0]
    loc = chosen.get("location", {})
    if (
        str(chosen.get("source", "")) == "social"
        and world_ref is not None
        and hasattr(world_ref, "record_shared_knowledge_used")
    ):
        world_ref.record_shared_knowledge_used("camp")
    return (int(loc.get("x", 0)), int(loc.get("y", 0)))


IDENTITY_UPDATE_INTERVAL_TICKS = 60


def _default_proto_traits() -> Dict[str, float]:
    return {
        "cooperation": 0.50,
        "diligence": 0.50,
        "caution": 0.50,
        "curiosity": 0.50,
        "resilience": 0.50,
        "identity_stability": 0.92,
    }


def ensure_agent_proto_traits(agent: Agent) -> Dict[str, Any]:
    traits = getattr(agent, "proto_traits", None)
    if not isinstance(traits, dict) or not traits:
        traits = _default_proto_traits()
        role = str(getattr(agent, "role", "npc"))
        if role == "builder":
            traits["diligence"] += 0.08
        elif role == "hauler":
            traits["cooperation"] += 0.08
        elif role == "miner":
            traits["resilience"] += 0.06
            traits["diligence"] += 0.04
        elif role == "woodcutter":
            traits["resilience"] += 0.04
            traits["curiosity"] += 0.03
        elif role == "leader":
            traits["cooperation"] += 0.10
            traits["caution"] += 0.04

        for key in ("cooperation", "diligence", "caution", "curiosity", "resilience", "identity_stability"):
            traits[key] = round(_clampf(float(traits.get(key, 0.5))), 3)
        traits["last_identity_update_tick"] = -1
        agent.proto_traits = traits
    return traits


def update_agent_identity(world: "World", agent: Agent) -> Dict[str, Any]:
    traits = ensure_agent_proto_traits(agent)
    tick = int(getattr(world, "tick", 0))
    last_tick = int(traits.get("last_identity_update_tick", -1))
    if last_tick >= 0 and tick - last_tick < int(IDENTITY_UPDATE_INTERVAL_TICKS):
        return traits

    recent_events = get_recent_memory_events(agent, limit=20)
    success_count = sum(1 for e in recent_events if str(e.get("outcome", "")) == "success")
    failure_count = sum(1 for e in recent_events if str(e.get("outcome", "")) == "failure")
    work_success = sum(
        1
        for e in recent_events
        if str(e.get("type", "")) in {"construction_progress", "delivered_material", "found_resource"}
        and str(e.get("outcome", "")) == "success"
    )
    explore_success = sum(
        1
        for e in recent_events
        if str(e.get("type", "")) in {"found_resource", "hunger_relief"}
        and str(e.get("outcome", "")) == "success"
    )

    social_memory = getattr(agent, "social_memory", {})
    known_agents = social_memory.get("known_agents", {}) if isinstance(social_memory, dict) else {}
    cooperative_contacts = sum(
        1
        for record in (known_agents.values() if isinstance(known_agents, dict) else [])
        if isinstance(record, dict) and str(record.get("recent_interaction", "")) == "co_present_success"
    )

    self_model = ensure_agent_self_model(agent)
    stress_level = float(self_model.get("stress_level", 0.2))

    identity_stability = _clampf(float(traits.get("identity_stability", 0.92)), 0.75, 0.99)
    adaptation_rate = 1.0 - identity_stability

    influence = {
        "cooperation": _clampf(
            float(traits.get("cooperation", 0.5))
            + 0.04 * min(cooperative_contacts, 3)
            + 0.01 * max(0, success_count - failure_count)
        ),
        "diligence": _clampf(
            float(traits.get("diligence", 0.5))
            + 0.03 * min(work_success, 4)
            - 0.01 * max(0, failure_count - success_count)
        ),
        "caution": _clampf(
            float(traits.get("caution", 0.5))
            + 0.03 * min(failure_count, 4)
            - 0.01 * min(success_count, 3)
        ),
        "curiosity": _clampf(
            float(traits.get("curiosity", 0.5))
            + 0.03 * min(explore_success, 4)
            - 0.01 * min(failure_count, 3)
        ),
        "resilience": _clampf(
            float(traits.get("resilience", 0.5))
            + 0.02 * min(failure_count, 4)
            + (0.02 if stress_level > 0.55 else 0.0)
            - (0.01 if stress_level < 0.25 else 0.0)
        ),
    }

    for key in ("cooperation", "diligence", "caution", "curiosity", "resilience"):
        current = _clampf(float(traits.get(key, 0.5)))
        target = _clampf(float(influence.get(key, current)))
        traits[key] = round(_clampf(current + (target - current) * adaptation_rate), 3)

    traits["identity_stability"] = round(identity_stability, 3)
    traits["last_identity_update_tick"] = tick
    return traits


def update_agent_cognitive_profile(world: "World", agent: Agent) -> Dict[str, Any]:
    profile = ensure_agent_cognitive_profile(agent)
    tick = int(getattr(world, "tick", 0))
    proto = ensure_agent_proto_traits(agent)
    recent_events = get_recent_memory_events(agent, limit=16)
    success_count = sum(1 for e in recent_events if str(e.get("outcome", "")) == "success")
    failure_count = sum(1 for e in recent_events if str(e.get("outcome", "")) == "failure")
    useful_work = sum(
        1
        for e in recent_events
        if str(e.get("type", "")) in {"construction_progress", "delivered_material", "found_resource"}
        and str(e.get("outcome", "")) == "success"
    )
    knowledge_state = ensure_agent_knowledge_state(agent)
    knowledge_richness = sum(
        len(knowledge_state.get(k, []))
        for k in ("known_resource_spots", "known_useful_buildings", "known_practices", "known_inventions")
        if isinstance(knowledge_state.get(k), list)
    )
    social_infl = _clampf(float(getattr(agent, "social_influence", 0.0)))

    maturity_signal = (
        min(1.0, useful_work / 6.0) * 0.35
        + min(1.0, success_count / 8.0) * 0.20
        + min(1.0, knowledge_richness / 12.0) * 0.25
        + social_infl * 0.15
        + float(proto.get("diligence", 0.5)) * 0.05
    )
    if failure_count > success_count:
        maturity_signal = _clampf(maturity_signal - 0.08)

    new_tier = COGNITIVE_TIER_MIN
    if maturity_signal >= 0.45:
        new_tier = 2
    if maturity_signal >= 0.65:
        new_tier = 3
    if maturity_signal >= 0.82:
        new_tier = 4
    profile["cognitive_tier"] = int(max(COGNITIVE_TIER_MIN, min(COGNITIVE_TIER_MAX, new_tier)))

    priority = 0.35 + maturity_signal * 0.45 + social_infl * 0.15
    profile["reflection_priority"] = round(_clampf(priority), 3)
    budget = 0.45 + maturity_signal * 0.35 - min(0.15, max(0.0, failure_count - success_count) * 0.03)
    profile["reflection_budget"] = round(_clampf(budget), 3)
    profile["reflection_cooldown_ticks"] = int(max(20, 90 - profile["cognitive_tier"] * 15))
    profile["max_context_items"] = int(max(6, min(18, 6 + profile["cognitive_tier"] * 3)))
    profile["llm_enabled"] = bool(profile.get("llm_enabled", True))
    profile.setdefault("last_reflection_tick", -1000)
    profile.setdefault("reflection_count", 0)
    profile.setdefault("last_reflection_reason", "")
    profile.setdefault("last_reflection_outcome", "")
    profile.setdefault("reflection_success_count", 0)
    profile.setdefault("reflection_fallback_count", 0)
    profile.setdefault("reflection_block_reason", "")
    profile.setdefault("effective_context_size", 0)
    profile["last_profile_update_tick"] = tick
    return profile


def _attention_complexity_score(attention: Dict[str, Any]) -> float:
    if not isinstance(attention, dict):
        return 0.0
    score = 0.0
    score += min(1.0, len(attention.get("top_resource_targets", [])) / 3.0) * 0.35
    score += min(1.0, len(attention.get("top_building_targets", [])) / 3.0) * 0.35
    score += min(1.0, len(attention.get("top_social_targets", [])) / 3.0) * 0.30
    return _clampf(score)


def should_agent_reflect(world: "World", agent: Agent) -> bool:
    profile = ensure_agent_cognitive_profile(agent)
    if not bool(getattr(world, "llm_enabled", True)):
        profile["reflection_block_reason"] = "world_llm_disabled"
        return False
    if not bool(profile.get("llm_enabled", True)):
        profile["reflection_block_reason"] = "agent_llm_disabled"
        return False
    if bool(getattr(agent, "llm_pending", False)):
        profile["reflection_block_reason"] = "already_pending"
        return False

    tick = int(getattr(world, "tick", 0))
    last = int(profile.get("last_reflection_tick", -1000))
    cooldown = int(profile.get("reflection_cooldown_ticks", 80))
    if tick - last < cooldown:
        profile["reflection_block_reason"] = "cooldown"
        return False

    if float(profile.get("reflection_budget", 0.0)) < 0.15:
        profile["reflection_block_reason"] = "budget_low"
        return False

    if int(getattr(world, "llm_calls_this_tick", 0)) >= int(getattr(world, "max_llm_calls_per_tick", 1)):
        profile["reflection_block_reason"] = "global_budget_exhausted"
        return False

    state = getattr(agent, "subjective_state", {})
    attention = state.get("attention", {}) if isinstance(state, dict) else {}
    local_signals = state.get("local_signals", {}) if isinstance(state, dict) else {}
    needs = local_signals.get("needs", {}) if isinstance(local_signals.get("needs"), dict) else {}
    current_intention = getattr(agent, "current_intention", {})
    failed_ticks = int(current_intention.get("failed_ticks", 0)) if isinstance(current_intention, dict) else 0

    complexity = _attention_complexity_score(attention)
    blocked = failed_ticks >= 2
    high_stakes = bool(needs.get("food_urgent")) or bool(needs.get("hunger_critical"))
    social_importance = bool(attention.get("salient_local_leader")) or len(attention.get("top_social_targets", [])) >= 2
    uncertainty = complexity >= 0.55

    eligibility = 0.0
    if blocked:
        eligibility += 0.35
    if high_stakes:
        eligibility += 0.25
    if social_importance:
        eligibility += 0.15
    if uncertainty:
        eligibility += 0.20
    eligibility += float(profile.get("reflection_priority", 0.0)) * 0.20

    if eligibility < 0.42:
        profile["reflection_block_reason"] = "low_relevance"
        return False

    profile["reflection_block_reason"] = ""
    return True


def detect_agent_reflection_reason(world: "World", agent: Agent) -> Optional[str]:
    state = getattr(agent, "subjective_state", {})
    if not isinstance(state, dict):
        return None
    attention = state.get("attention", {}) if isinstance(state.get("attention"), dict) else {}
    local_signals = state.get("local_signals", {}) if isinstance(state.get("local_signals"), dict) else {}
    needs = local_signals.get("needs", {}) if isinstance(local_signals.get("needs"), dict) else {}
    local_culture = state.get("local_culture", {}) if isinstance(state.get("local_culture"), dict) else {}
    current_intention = getattr(agent, "current_intention", {})
    failed_ticks = int(current_intention.get("failed_ticks", 0)) if isinstance(current_intention, dict) else 0
    survival = evaluate_local_survival_pressure(world, agent)
    survival_pressure = float(survival.get("survival_pressure", 0.0))
    food_crisis = bool(survival.get("food_crisis", False))
    if failed_ticks >= 2:
        return "blocked_intention"

    recent = get_recent_memory_events(agent, limit=8)
    recent_failures = sum(1 for ev in recent if str(ev.get("outcome", "")) == "failure")
    if recent_failures >= 3:
        return "repeated_local_failure"
    if food_crisis and hunger > 35:
        return "conflicting_local_needs"

    hunger = float(getattr(agent, "hunger", 100.0))
    top_resources = attention.get("top_resource_targets", []) if isinstance(attention.get("top_resource_targets"), list) else []
    top_buildings = attention.get("top_building_targets", []) if isinstance(attention.get("top_building_targets"), list) else []
    if (
        hunger < 45
        and (bool(needs.get("need_materials")) or bool(needs.get("need_storage")) or bool(needs.get("need_housing")))
        and len(top_resources) > 0
        and len(top_buildings) > 0
    ):
        # Self urgency vs local collective pressure.
        return "conflicting_local_needs"

    if len(top_resources) >= 2:
        s0 = float(top_resources[0].get("salience", 0.0))
        s1 = float(top_resources[1].get("salience", 0.0))
        if abs(s0 - s1) <= 0.15 and bool(needs.get("food_urgent")) is False and survival_pressure < 0.7:
            return "conflicting_local_needs"

    role = str(getattr(agent, "role", "npc"))
    top_social = attention.get("top_social_targets", []) if isinstance(attention.get("top_social_targets"), list) else []
    leader = attention.get("salient_local_leader")
    coop_norm = float(local_culture.get("cooperation_norm", 0.5))
    if role in {"builder", "hauler"} and len(top_buildings) >= 2 and isinstance(leader, dict) and len(top_social) > 0 and coop_norm >= 0.45:
        return "uncertain_cooperative_choice"

    return None


INNOVATION_OPPORTUNITY_REASONS = {
    "transport_barrier",
    "storage_friction",
    "construction_friction",
    "resource_access_friction",
    "food_handling_friction",
    "route_inefficiency",
}

PROTO_ASSET_KINDS = {"infrastructure", "building", "tool", "process"}
PROTO_ASSET_CATEGORIES = {"transport", "logistics", "production", "storage", "water", "sanitation"}
PROTO_ASSET_EFFECTS = {
    "cross_water",
    "reduce_movement_cost",
    "increase_storage_efficiency",
    "improve_delivery_efficiency",
    "improve_resource_access",
    "improve_food_handling",
    "improve_construction_access",
}
PROTO_ASSET_MATERIALS = {"food", "wood", "stone"}
PROTO_ASSET_FOOTPRINT_PLACEMENTS = {"near_storage", "near_route", "near_water", "resource_edge", "village_core"}
PROTO_ASSET_STATUSES = {
    "proposed",
    "admissible",
    "rejected",
    "archived",
    "prototype_pending",
    "prototype_under_construction",
    "prototype_built",
    "prototype_failed",
}
PROTO_ASSET_REJECTION_REASONS = {
    "invalid_effect_context",
    "impossible_terrain_dependency",
    "excessive_material_cost",
    "unsupported_category_context",
    "duplicate_equivalent_proposal",
    "insufficient_local_basis",
    "invalid_schema",
    "unsupported_values",
}


def detect_agent_innovation_opportunity(world: "World", agent: Agent) -> Optional[str]:
    state = getattr(agent, "subjective_state", {})
    if not isinstance(state, dict):
        return None
    local_signals = state.get("local_signals", {}) if isinstance(state.get("local_signals"), dict) else {}
    needs = local_signals.get("needs", {}) if isinstance(local_signals.get("needs"), dict) else {}
    recent = get_recent_memory_events(agent, limit=18)
    current_intention = getattr(agent, "current_intention", {})
    failed_ticks = int(current_intention.get("failed_ticks", 0)) if isinstance(current_intention, dict) else 0

    failure_events = [ev for ev in recent if str(ev.get("outcome", "")) == "failure"]
    failed_resource_search = [ev for ev in failure_events if str(ev.get("type", "")) == "failed_resource_search"]
    unreachable_target = [ev for ev in failure_events if str(ev.get("type", "")) == "unreachable_target"]
    construction_blocked = [ev for ev in failure_events if str(ev.get("type", "")) == "construction_blocked"]

    if len(unreachable_target) >= 2:
        crossing_candidates = sum(
            1
            for ev in unreachable_target
            if str((ev.get("location") or {}).get("terrain_hint", "")).lower() in {"water", "chokepoint"}
        )
        if crossing_candidates >= 1:
            return "transport_barrier"
        return "route_inefficiency"

    if len(construction_blocked) >= 2 or (failed_ticks >= 3 and str(getattr(agent, "role", "")) in {"builder", "hauler"}):
        return "construction_friction"

    food_failures = sum(1 for ev in failed_resource_search if str(ev.get("resource_type", "")) == "food")
    if food_failures >= 3 or (bool(needs.get("food_buffer_critical")) and len(failure_events) >= 3):
        return "food_handling_friction"

    if bool(needs.get("need_storage")) and len(failure_events) >= 3:
        return "storage_friction"

    material_failures = sum(
        1
        for ev in failed_resource_search
        if str(ev.get("resource_type", "")) in {"wood", "stone"}
    )
    if material_failures >= 3:
        return "resource_access_friction"

    if failed_ticks >= 3:
        return "route_inefficiency"
    return None


def _deterministic_proto_asset_payload(
    world: "World",
    agent: Agent,
    reason: str,
) -> Dict[str, Any]:
    role = str(getattr(agent, "role", "npc"))
    base_materials = {"wood": 2, "stone": 1}
    if reason == "transport_barrier":
        return {
            "name": "ford path marker",
            "asset_kind": "infrastructure",
            "category": "transport",
            "intended_effects": ["cross_water", "reduce_movement_cost"],
            "required_materials": {"wood": 3, "stone": 2},
            "footprint_hint": {"width": 1, "height": 2, "placement": "near_water"},
        }
    if reason == "route_inefficiency":
        return {
            "name": "waypoint lane",
            "asset_kind": "infrastructure",
            "category": "transport",
            "intended_effects": ["reduce_movement_cost"],
            "required_materials": dict(base_materials),
            "footprint_hint": {"width": 1, "height": 1, "placement": "near_route"},
        }
    if reason == "storage_friction":
        return {
            "name": "cache shelf",
            "asset_kind": "building",
            "category": "storage",
            "intended_effects": ["increase_storage_efficiency", "improve_delivery_efficiency"],
            "required_materials": {"wood": 4, "stone": 1},
            "footprint_hint": {"width": 2, "height": 2, "placement": "near_storage"},
        }
    if reason == "food_handling_friction":
        return {
            "name": "food handoff routine",
            "asset_kind": "process",
            "category": "logistics",
            "intended_effects": ["improve_food_handling", "improve_delivery_efficiency"],
            "required_materials": {"wood": 1},
            "footprint_hint": {"width": 1, "height": 1, "placement": "village_core"},
        }
    if reason == "construction_friction":
        return {
            "name": "build staging spot",
            "asset_kind": "process" if role == "hauler" else "tool",
            "category": "logistics",
            "intended_effects": ["improve_construction_access", "improve_delivery_efficiency"],
            "required_materials": {"wood": 2, "stone": 2},
            "footprint_hint": {"width": 1, "height": 1, "placement": "near_storage"},
        }
    return {
        "name": "resource access marker",
        "asset_kind": "tool",
        "category": "production",
        "intended_effects": ["improve_resource_access"],
        "required_materials": {"wood": 2},
        "footprint_hint": {"width": 1, "height": 1, "placement": "resource_edge"},
    }


def validate_proto_asset_proposal(payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], str]:
    if not isinstance(payload, dict):
        return None, "invalid_schema"
    required = (
        "proposal_id",
        "inventor_agent_id",
        "tick_created",
        "reason",
        "name",
        "asset_kind",
        "category",
        "intended_effects",
        "required_materials",
        "footprint_hint",
        "status",
    )
    for key in required:
        if key not in payload:
            return None, "invalid_schema"

    reason = str(payload.get("reason", "")).strip().lower()
    if reason not in INNOVATION_OPPORTUNITY_REASONS:
        return None, "unsupported_values"
    name = str(payload.get("name", "")).strip().lower()
    if len(name) < 3 or len(name) > 48:
        return None, "unsupported_values"
    asset_kind = str(payload.get("asset_kind", "")).strip().lower()
    if asset_kind not in PROTO_ASSET_KINDS:
        return None, "unsupported_values"
    category = str(payload.get("category", "")).strip().lower()
    if category not in PROTO_ASSET_CATEGORIES:
        return None, "unsupported_values"

    effects = payload.get("intended_effects", [])
    if not isinstance(effects, list) or not effects:
        return None, "invalid_schema"
    cleaned_effects = []
    for effect in effects[:3]:
        e = str(effect).strip().lower()
        if e not in PROTO_ASSET_EFFECTS:
            return None, "unsupported_values"
        if e not in cleaned_effects:
            cleaned_effects.append(e)
    if not cleaned_effects:
        return None, "unsupported_values"

    materials = payload.get("required_materials", {})
    if not isinstance(materials, dict):
        return None, "invalid_schema"
    cleaned_materials: Dict[str, int] = {}
    for k, v in materials.items():
        resource = str(k).strip().lower()
        if resource not in PROTO_ASSET_MATERIALS:
            return None, "unsupported_values"
        qty = int(v)
        if qty < 0 or qty > 8:
            return None, "unsupported_values"
        if qty > 0:
            cleaned_materials[resource] = qty
    if not cleaned_materials:
        return None, "unsupported_values"

    hint = payload.get("footprint_hint", {})
    if not isinstance(hint, dict):
        return None, "invalid_schema"
    width = int(hint.get("width", 1))
    height = int(hint.get("height", 1))
    placement = str(hint.get("placement", "")).strip().lower()
    if width < 1 or width > 3 or height < 1 or height > 3:
        return None, "unsupported_values"
    if placement not in PROTO_ASSET_FOOTPRINT_PLACEMENTS:
        return None, "unsupported_values"

    status = str(payload.get("status", "proposed")).strip().lower() or "proposed"
    if status not in PROTO_ASSET_STATUSES:
        return None, "unsupported_values"
    rejection_reason_raw = str(payload.get("rejection_reason", "")).strip().lower()
    if rejection_reason_raw and rejection_reason_raw not in PROTO_ASSET_REJECTION_REASONS:
        return None, "unsupported_values"
    if status == "rejected" and not rejection_reason_raw:
        return None, "invalid_schema"
    if status != "rejected":
        rejection_reason_raw = ""

    cleaned = {
        "proposal_id": str(payload.get("proposal_id", "")).strip(),
        "inventor_agent_id": str(payload.get("inventor_agent_id", "")).strip(),
        "tick_created": int(payload.get("tick_created", 0)),
        "reason": reason,
        "name": name,
        "asset_kind": asset_kind,
        "category": category,
        "intended_effects": cleaned_effects,
        "required_materials": cleaned_materials,
        "footprint_hint": {"width": width, "height": height, "placement": placement},
        "status": status,
    }
    if rejection_reason_raw:
        cleaned["rejection_reason"] = rejection_reason_raw
    if "admissibility_tick" in payload:
        admissibility_tick = int(payload.get("admissibility_tick", -1))
        if admissibility_tick >= 0:
            cleaned["admissibility_tick"] = admissibility_tick
    if not cleaned["proposal_id"] or not cleaned["inventor_agent_id"] or cleaned["tick_created"] < 0:
        return None, "invalid_schema"
    return cleaned, ""


def maybe_generate_innovation_proposal(
    world: "World",
    agent: Agent,
    *,
    source: str = "stub",
    reason: Optional[str] = None,
    proposal_payload: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    local_reason = str(reason or detect_agent_innovation_opportunity(world, agent) or "").strip().lower()
    if local_reason not in INNOVATION_OPPORTUNITY_REASONS:
        return None

    existing = getattr(agent, "current_innovation_proposal", None)
    if isinstance(existing, dict):
        if str(existing.get("status", "")) in {"proposed", "admissible"} and int(getattr(world, "tick", 0)) - int(existing.get("tick_created", 0)) < 120:
            return None

    tick = int(getattr(world, "tick", 0))
    inventor_id = str(getattr(agent, "agent_id", "unknown"))
    if isinstance(proposal_payload, dict):
        base = dict(proposal_payload)
    else:
        base = _deterministic_proto_asset_payload(world, agent, local_reason)
    proposal = {
        "proposal_id": str(base.get("proposal_id") or f"pa-{inventor_id}-{tick}-{local_reason}"),
        "inventor_agent_id": inventor_id,
        "tick_created": tick,
        "reason": local_reason,
        "name": str(base.get("name", "")),
        "asset_kind": str(base.get("asset_kind", "")),
        "category": str(base.get("category", "")),
        "intended_effects": list(base.get("intended_effects", [])),
        "required_materials": dict(base.get("required_materials", {})),
        "footprint_hint": dict(base.get("footprint_hint", {})),
        "status": "proposed",
    }
    validated, validation_reason = validate_proto_asset_proposal(proposal)
    if validated is None:
        if hasattr(world, "record_proto_asset_proposal_rejected"):
            world.record_proto_asset_proposal_rejected(validation_reason or "invalid_schema")
        return None
    if hasattr(world, "register_proto_asset_proposal"):
        if not bool(world.register_proto_asset_proposal(validated, source=source)):
            return None
        stored = None
        for entry in reversed(list(getattr(world, "proto_asset_proposals", []) or [])):
            if not isinstance(entry, dict):
                continue
            if str(entry.get("proposal_id", "")) == str(validated.get("proposal_id", "")):
                stored = dict(entry)
                break
        if isinstance(stored, dict):
            agent.current_innovation_proposal = dict(stored)
            return dict(stored)
    agent.current_innovation_proposal = dict(validated)
    return dict(validated)


def build_agent_cognitive_context(world: "World", agent: Agent) -> Dict[str, Any]:
    profile = ensure_agent_cognitive_profile(agent)
    max_items = int(max(1, min(20, int(profile.get("max_context_items", 8)))))
    state = getattr(agent, "subjective_state", {})
    attention = state.get("attention", {}) if isinstance(state.get("attention"), dict) else {}
    local_signals = state.get("local_signals", {}) if isinstance(state.get("local_signals"), dict) else {}
    local_culture = state.get("local_culture", {}) if isinstance(state.get("local_culture"), dict) else {}

    recent_events = get_recent_memory_events(agent, limit=max_items)
    social_memory = (getattr(agent, "social_memory", {}) or {}).get("known_agents", {})
    social_subset = []
    if isinstance(social_memory, dict):
        entries = [
            (aid, rec) for aid, rec in social_memory.items()
            if isinstance(rec, dict)
        ]
        entries.sort(
            key=lambda item: (
                -float(item[1].get("social_salience", 0.0)),
                -int(item[1].get("times_seen", 0)),
                str(item[0]),
            )
        )
        for aid, rec in entries[:max_items]:
            social_subset.append(
                {
                    "agent_id": str(aid),
                    "times_seen": int(rec.get("times_seen", 0)),
                    "same_village": bool(rec.get("same_village", False)),
                    "role": str(rec.get("role", "npc")),
                    "social_salience": float(rec.get("social_salience", 0.0)),
                }
            )

    knowledge_state = ensure_agent_knowledge_state(agent)
    knowledge_subset = {}
    for key in ("known_resource_spots", "known_useful_buildings", "known_practices", "known_inventions"):
        entries = knowledge_state.get(key, [])
        if not isinstance(entries, list):
            knowledge_subset[key] = []
            continue
        sorted_entries = sorted(
            entries,
            key=lambda e: (
                -float(e.get("confidence", 0.0)),
                -float(e.get("salience", 0.0)),
                -int(e.get("learned_tick", 0)),
                str(e.get("subject", "")),
            ),
        )
        knowledge_subset[key] = sorted_entries[:max_items]

    context = {
        "tick": int(getattr(world, "tick", 0)),
        "agent_state": {
            "agent_id": str(getattr(agent, "agent_id", "")),
            "role": str(getattr(agent, "role", "npc")),
            "task": str(getattr(agent, "task", "idle")),
            "hunger": float(getattr(agent, "hunger", 100.0)),
            "inventory": dict(getattr(agent, "inventory", {})),
            "current_intention": dict(getattr(agent, "current_intention", {}) or {}),
            "current_innovation_proposal": dict(getattr(agent, "current_innovation_proposal", {}) or {}),
        },
        "attention": {
            "top_resource_targets": list(attention.get("top_resource_targets", []))[:max_items],
            "top_building_targets": list(attention.get("top_building_targets", []))[:max_items],
            "top_social_targets": list(attention.get("top_social_targets", []))[:max_items],
            "dominant_local_signal": attention.get("dominant_local_signal"),
            "current_focus": attention.get("current_focus"),
        },
        "local_signals": {
            "priority": local_signals.get("priority"),
            "needs": dict(local_signals.get("needs", {})) if isinstance(local_signals.get("needs"), dict) else {},
            "market_state": dict(local_signals.get("market_state", {})) if isinstance(local_signals.get("market_state"), dict) else {},
            "survival": dict(local_signals.get("survival", {})) if isinstance(local_signals.get("survival"), dict) else {},
        },
        "local_culture": dict(local_culture),
        "recent_events": recent_events[-max_items:],
        "social_memory": social_subset[:max_items],
        "self_model": dict(getattr(agent, "self_model", {})),
        "proto_traits": dict(getattr(agent, "proto_traits", {})),
        "knowledge_state": knowledge_subset,
    }
    profile["effective_context_size"] = int(
        len(context["recent_events"])
        + len(context["social_memory"])
        + len(context["attention"]["top_resource_targets"])
        + len(context["knowledge_state"].get("known_resource_spots", []))
    )
    return context


def evaluate_agent_social_influence(world: "World", agent: Agent) -> float:
    proto_traits = ensure_agent_proto_traits(agent)
    social_memory = getattr(agent, "social_memory", {})
    known_agents = social_memory.get("known_agents", {}) if isinstance(social_memory, dict) else {}
    tick = int(getattr(world, "tick", 0))

    familiarity_score = 0.0
    if isinstance(known_agents, dict) and known_agents:
        familiarity_samples = []
        for record in known_agents.values():
            if not isinstance(record, dict):
                continue
            times_seen = int(record.get("times_seen", 0))
            familiarity_samples.append(min(1.0, times_seen / 8.0))
        if familiarity_samples:
            familiarity_score = sum(familiarity_samples) / float(len(familiarity_samples))
    encounter_memory = getattr(agent, "recent_encounters", {})
    encounter_familiarity = 0.0
    if isinstance(encounter_memory, dict) and encounter_memory:
        fam_values = [
            float(entry.get("familiarity_score", 0.0))
            for entry in encounter_memory.values()
            if isinstance(entry, dict)
        ]
        if fam_values:
            encounter_familiarity = sum(fam_values) / float(len(fam_values))

    recent_events = get_recent_memory_events(agent, limit=24)
    cooperative_successes = 0
    recent_successes = 0
    recent_success_horizon = 30
    for ev in recent_events:
        if not isinstance(ev, dict):
            continue
        ev_tick = int(ev.get("tick", tick))
        if tick - ev_tick > recent_success_horizon:
            continue
        if str(ev.get("outcome", "")) == "success":
            recent_successes += 1
        if str(ev.get("type", "")) == "co_present_success" and str(ev.get("outcome", "")) == "success":
            cooperative_successes += 1

    cooperative_score = min(1.0, cooperative_successes / 4.0)
    success_score = min(1.0, recent_successes / 8.0)
    trait_score = (
        float(proto_traits.get("cooperation", 0.5)) * 0.45
        + float(proto_traits.get("diligence", 0.5)) * 0.30
        + float(proto_traits.get("resilience", 0.5)) * 0.25
    )
    role_bonus = 0.08 if str(getattr(agent, "role", "npc")) == "leader" else 0.0

    subjective = getattr(agent, "subjective_state", {})
    nearby_agents = subjective.get("nearby_agents", []) if isinstance(subjective, dict) else []
    nearby_count = len(nearby_agents) if isinstance(nearby_agents, list) else 0
    local_presence_score = min(1.0, nearby_count / 4.0)

    raw_score = (
        familiarity_score * 0.24
        + encounter_familiarity * 0.08
        + cooperative_score * 0.24
        + trait_score * 0.24
        + success_score * 0.14
        + local_presence_score * 0.10
        + role_bonus
    )

    prev = _clampf(float(getattr(agent, "social_influence", 0.0)))
    blended = prev * 0.70 + _clampf(raw_score) * 0.30

    # Slow decay when locally isolated and without recent collaborative success.
    if nearby_count == 0 and cooperative_successes == 0:
        blended = min(blended, prev * 0.985)

    return round(_clampf(blended), 3)


def detect_local_leader(agent: Agent, leadership_threshold: float = 0.55) -> Optional[Dict[str, Any]]:
    state = getattr(agent, "subjective_state", {})
    if not isinstance(state, dict):
        return None
    nearby_agents = state.get("nearby_agents", [])
    radius = state.get("radius", {}) if isinstance(state.get("radius"), dict) else {}
    social_radius = int(radius.get("social", max(1, int(getattr(agent, "social_radius_tiles", 8)))))
    if not isinstance(nearby_agents, list):
        return None

    candidates = []
    for entry in nearby_agents:
        if not isinstance(entry, dict):
            continue
        influence = _clampf(float(entry.get("social_influence", 0.0)))
        distance = int(entry.get("distance", social_radius + 1))
        if distance > social_radius:
            continue
        if influence < float(leadership_threshold):
            continue
        candidates.append(
            {
                "agent_id": str(entry.get("agent_id", "")),
                "x": int(entry.get("x", 0)),
                "y": int(entry.get("y", 0)),
                "distance": distance,
                "role": str(entry.get("role", "npc")),
                "same_village": bool(entry.get("same_village", False)),
                "social_influence": round(influence, 3),
            }
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda c: (
            -float(c["social_influence"]),
            int(c["distance"]),
            str(c["agent_id"]),
        )
    )
    return candidates[0]


def ensure_agent_self_model(agent: Agent) -> Dict[str, Any]:
    model = getattr(agent, "self_model", None)
    if not isinstance(model, dict) or not model:
        model = _default_self_model()
        role = str(getattr(agent, "role", "npc"))
        if role == "builder":
            model["work_weight"] += 0.10
            model["security_weight"] += 0.05
        elif role == "hauler":
            model["social_weight"] += 0.10
            model["work_weight"] += 0.05
        elif role in {"miner", "woodcutter"}:
            model["work_weight"] += 0.08
        elif role == "leader":
            model["social_weight"] += 0.12
            model["security_weight"] += 0.05
        for key in ("survival_weight", "social_weight", "work_weight", "exploration_weight", "security_weight"):
            model[key] = round(_clampf(float(model.get(key, 0.5))), 3)
        model["stress_level"] = round(_clampf(float(model.get("stress_level", 0.2))), 3)
        model["recent_success_bias"] = round(_clampf(float(model.get("recent_success_bias", 0.5))), 3)
        model["recent_failure_bias"] = round(_clampf(float(model.get("recent_failure_bias", 0.2))), 3)
        model["last_self_update_tick"] = -1
        agent.self_model = model
    return model


def write_episodic_memory_event(
    agent: Agent,
    *,
    tick: int,
    event_type: str,
    outcome: str,
    location: Optional[Tuple[int, int]] = None,
    target_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    building_type: Optional[str] = None,
    salience: float = 1.0,
    max_events: int = 40,
) -> Dict[str, Any]:
    memory = getattr(agent, "episodic_memory", None)
    if not isinstance(memory, dict):
        memory = {"recent_events": []}
        agent.episodic_memory = memory
    events = memory.get("recent_events")
    if not isinstance(events, list):
        events = []
        memory["recent_events"] = events

    payload: Dict[str, Any] = {
        "type": str(event_type),
        "tick": int(tick),
        "outcome": str(outcome),
        "salience": float(round(max(0.0, salience), 3)),
    }
    if location is not None:
        payload["location"] = {"x": int(location[0]), "y": int(location[1])}
    if target_id is not None:
        payload["target_id"] = str(target_id)
    if resource_type is not None:
        payload["resource_type"] = str(resource_type)
    if building_type is not None:
        payload["building_type"] = str(building_type)

    events.append(payload)

    # Leadership reinforcement hook: successful events with co-present peers
    # create compact cooperative traces and strengthen local familiarity.
    if str(outcome) == "success":
        subjective = getattr(agent, "subjective_state", {})
        nearby_agents = subjective.get("nearby_agents", []) if isinstance(subjective, dict) else []
        if isinstance(nearby_agents, list) and nearby_agents:
            coop_event = {
                "type": "co_present_success",
                "tick": int(tick),
                "outcome": "success",
                "salience": float(round(max(0.0, salience + 0.2), 3)),
            }
            if location is not None:
                coop_event["location"] = {"x": int(location[0]), "y": int(location[1])}
            if target_id is not None:
                coop_event["target_id"] = str(target_id)
            events.append(coop_event)

            social_memory = getattr(agent, "social_memory", {})
            known_agents = social_memory.get("known_agents", {}) if isinstance(social_memory, dict) else {}
            if isinstance(known_agents, dict):
                for near in nearby_agents:
                    if not isinstance(near, dict):
                        continue
                    aid = str(near.get("agent_id", ""))
                    if not aid:
                        continue
                    record = known_agents.get(aid)
                    if not isinstance(record, dict):
                        record = {
                            "last_seen_tick": int(tick),
                            "times_seen": 0,
                            "same_village": bool(near.get("same_village", False)),
                            "role": str(near.get("role", "npc")),
                            "recent_interaction": "seen",
                            "social_salience": 0.0,
                        }
                        known_agents[aid] = record
                    record["last_seen_tick"] = int(tick)
                    record["times_seen"] = int(record.get("times_seen", 0)) + 1
                    record["same_village"] = bool(near.get("same_village", False))
                    record["role"] = str(near.get("role", "npc"))
                    record["recent_interaction"] = "co_present_success"
                    record["social_salience"] = round(
                        min(4.0, float(record.get("social_salience", 0.0)) + 0.2), 3
                    )

    # Bounded episodic window: keep only most recent events.
    if len(events) > int(max_events):
        overflow = len(events) - int(max_events)
        del events[:overflow]
    return payload


def get_recent_memory_events(
    agent: Agent,
    event_type: Optional[str] = None,
    *,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    memory = getattr(agent, "episodic_memory", {})
    events = memory.get("recent_events", []) if isinstance(memory, dict) else []
    if not isinstance(events, list):
        return []
    filtered = [
        e for e in events
        if isinstance(e, dict) and (event_type is None or str(e.get("type", "")) == str(event_type))
    ]
    if limit is None:
        return list(filtered)
    return filtered[-max(0, int(limit)):]


def find_recent_resource_memory(agent: Agent, resource_type: str) -> List[Dict[str, Any]]:
    target = str(resource_type)
    events = get_recent_memory_events(agent)
    out = [
        e for e in events
        if str(e.get("resource_type", "")) == target
    ]
    out.sort(key=lambda e: (int(e.get("tick", 0)), float(e.get("salience", 0.0))))
    return out


def find_recent_building_memory(
    agent: Agent,
    *,
    building_type: Optional[str] = None,
    target_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    bt = None if building_type is None else str(building_type)
    tid = None if target_id is None else str(target_id)
    events = get_recent_memory_events(agent)
    out = []
    for e in events:
        if bt is not None and str(e.get("building_type", "")) != bt:
            continue
        if tid is not None and str(e.get("target_id", "")) != tid:
            continue
        out.append(e)
    out.sort(key=lambda e: (int(e.get("tick", 0)), float(e.get("salience", 0.0))))
    return out


def _iter_resource_coords(world: "World", name: str) -> Set[Tuple[int, int]]:
    if name == "food":
        return set(getattr(world, "food", set()))
    if name == "wood":
        return set(getattr(world, "wood", set()))
    if name == "stone":
        return set(getattr(world, "stone", set()))
    return set()


def _village_local_signals(world: "World", agent: Agent) -> Dict[str, Any]:
    village_id = getattr(agent, "village_id", None)
    if village_id is None:
        return {}
    village = world.get_village_by_id(village_id)
    if not isinstance(village, dict):
        return {}

    market_state = village.get("market_state", {})
    if not isinstance(market_state, dict):
        market_state = {}

    compact_market = {}
    for resource in ("food", "wood", "stone"):
        entry = market_state.get(resource, {})
        if isinstance(entry, dict):
            compact_market[resource] = {
                "pressure": float(entry.get("pressure", 0.0)),
                "local_price_index": float(entry.get("local_price_index", 1.0)),
            }

    construction_needs = {"wood": 0, "stone": 0, "food": 0}
    for building in getattr(world, "buildings", {}).values():
        if building.get("village_id") != village_id:
            continue
        request = building.get("construction_request", {})
        if not isinstance(request, dict):
            continue
        for resource in ("wood", "stone", "food"):
            needed = int(request.get(f"{resource}_needed", 0))
            reserved = int(request.get(f"{resource}_reserved", 0))
            construction_needs[resource] += max(0, needed - reserved)

    return {
        "village_id": village_id,
        "priority": str(village.get("priority", "stabilize")),
        "needs": dict(village.get("needs", {})) if isinstance(village.get("needs"), dict) else {},
        "market_state": compact_market,
        "construction_needs": construction_needs,
    }


def evaluate_local_survival_pressure(world: "World", agent: Agent) -> Dict[str, Any]:
    state = getattr(agent, "subjective_state", {})
    local_signals = state.get("local_signals", {}) if isinstance(state, dict) else {}
    needs = local_signals.get("needs", {}) if isinstance(local_signals.get("needs"), dict) else {}
    market_state = local_signals.get("market_state", {}) if isinstance(local_signals.get("market_state"), dict) else {}
    nearby_resources = state.get("nearby_resources", {}) if isinstance(state, dict) else {}

    hunger = float(getattr(agent, "hunger", 100.0))
    hunger_pressure = _clampf((60.0 - hunger) / 60.0)
    critical_hunger = _clampf((35.0 - hunger) / 35.0)

    village_food_pressure = float((market_state.get("food") or {}).get("pressure", 0.0)) if isinstance(market_state, dict) else 0.0
    village_food_price = float((market_state.get("food") or {}).get("local_price_index", 1.0)) if isinstance(market_state, dict) else 1.0
    market_pressure = _clampf(village_food_pressure)
    market_price_pressure = _clampf((village_food_price - 1.0) / 1.5)

    village_storage_pressure = 0.0
    village_id = getattr(agent, "village_id", None)
    village = world.get_village_by_id(village_id) if village_id is not None else None
    if isinstance(village, dict):
        storage = village.get("storage", {}) if isinstance(village.get("storage"), dict) else {}
        food_stock = int(storage.get("food", 0))
        pop = max(1, int(village.get("population", 1)))
        target = max(4, pop * 2)
        village_storage_pressure = _clampf((target - food_stock) / float(target))

    needs_pressure = 0.0
    if bool(needs.get("food_urgent")):
        needs_pressure += 0.45
    if bool(needs.get("food_buffer_critical")):
        needs_pressure += 0.35
    if bool(needs.get("hunger_critical")):
        needs_pressure += 0.30
    needs_pressure = _clampf(needs_pressure)

    visible_food_entries = nearby_resources.get("food", []) if isinstance(nearby_resources, dict) else []
    visible_food_count = len(visible_food_entries) if isinstance(visible_food_entries, list) else 0
    visible_food_scarcity = 0.5 if visible_food_count == 0 else (0.2 if visible_food_count <= 2 else 0.0)

    recent_events = get_recent_memory_events(agent, limit=12)
    hunger_failure_events = sum(
        1
        for ev in recent_events
        if isinstance(ev, dict)
        and str(ev.get("type", "")) in {"failed_resource_search"}
        and str(ev.get("resource_type", "")) == "food"
        and str(ev.get("outcome", "")) == "failure"
    )
    hunger_relief_events = sum(
        1
        for ev in recent_events
        if isinstance(ev, dict)
        and str(ev.get("type", "")) == "hunger_relief"
        and str(ev.get("outcome", "")) == "success"
    )
    memory_pressure = _clampf(min(1.0, hunger_failure_events * 0.25) - min(0.5, hunger_relief_events * 0.12))

    pressure = (
        hunger_pressure * 0.32
        + critical_hunger * 0.16
        + market_pressure * 0.16
        + market_price_pressure * 0.10
        + village_storage_pressure * 0.14
        + needs_pressure * 0.08
        + visible_food_scarcity * 0.02
        + memory_pressure * 0.02
    )
    pressure = round(_clampf(pressure), 3)
    if pressure >= 0.75:
        level = "critical"
    elif pressure >= 0.50:
        level = "high"
    elif pressure >= 0.30:
        level = "moderate"
    else:
        level = "low"
    return {
        "survival_pressure": pressure,
        "food_crisis": bool(pressure >= 0.60),
        "food_insecurity_level": level,
    }


def _village_local_culture(world: "World", agent: Agent) -> Dict[str, Any]:
    village_id = getattr(agent, "village_id", None)
    if village_id is None:
        return {}
    village = world.get_village_by_id(village_id)
    if not isinstance(village, dict):
        return {}
    culture = village.get("proto_culture", {})
    if not isinstance(culture, dict):
        return {}
    resource_focus = culture.get("resource_focus", {}) if isinstance(culture.get("resource_focus"), dict) else {}
    ordered = ("food", "wood", "stone")
    dominant = max(ordered, key=lambda r: (float(resource_focus.get(r, 0.0)), -ordered.index(r)))
    return {
        "cooperation_norm": float(culture.get("cooperation_norm", 0.5)),
        "work_norm": float(culture.get("work_norm", 0.5)),
        "exploration_norm": float(culture.get("exploration_norm", 0.5)),
        "risk_norm": float(culture.get("risk_norm", 0.5)),
        "dominant_resource_focus": dominant,
    }


def update_agent_social_memory(world: "World", agent: Agent, subjective_state: Dict[str, Any]) -> None:
    social_memory = getattr(agent, "social_memory", None)
    if not isinstance(social_memory, dict):
        social_memory = {"known_agents": {}}
        agent.social_memory = social_memory
    known_agents = social_memory.get("known_agents")
    if not isinstance(known_agents, dict):
        known_agents = {}
        social_memory["known_agents"] = known_agents

    tick = int(getattr(world, "tick", 0))
    encounter_memory = getattr(agent, "recent_encounters", None)
    if not isinstance(encounter_memory, dict):
        encounter_memory = {}
        agent.recent_encounters = encounter_memory
    familiar_zones = getattr(agent, "recent_familiar_activity_zones", None)
    if not isinstance(familiar_zones, list):
        familiar_zones = []
        agent.recent_familiar_activity_zones = familiar_zones
    nearby_agents = subjective_state.get("nearby_agents", []) if isinstance(subjective_state, dict) else []
    if not isinstance(nearby_agents, list):
        nearby_agents = []

    recent_success = False
    for ev in get_recent_memory_events(agent, limit=6):
        if str(ev.get("outcome", "")) == "success" and tick - int(ev.get("tick", tick)) <= 2:
            recent_success = True
            break

    seen_ids = set()
    familiar_nearby = 0
    for entry in nearby_agents:
        if not isinstance(entry, dict):
            continue
        agent_id = str(entry.get("agent_id", ""))
        if not agent_id:
            continue
        seen_ids.add(agent_id)
        same_village = bool(entry.get("same_village", False))
        role = str(entry.get("role", "npc"))

        record = known_agents.get(agent_id)
        if not isinstance(record, dict):
            record = {
                "last_seen_tick": tick,
                "times_seen": 0,
                "same_village": False,
                "role": role,
                "recent_interaction": "seen",
                "social_salience": 0.0,
            }
            known_agents[agent_id] = record

        record["last_seen_tick"] = tick
        record["times_seen"] = int(record.get("times_seen", 0)) + 1
        record["same_village"] = bool(same_village)
        record["role"] = role
        if recent_success:
            record["recent_interaction"] = "co_present_success"
        elif str(record.get("recent_interaction", "")) == "":
            record["recent_interaction"] = "seen"

        times_seen = int(record.get("times_seen", 0))
        social_salience = min(3.0, times_seen * 0.12)
        if bool(record.get("same_village", False)):
            social_salience += 0.8
        if role == "leader":
            social_salience += 0.8
        if str(record.get("recent_interaction", "")) == "co_present_success":
            social_salience += 0.6
        record["social_salience"] = round(float(min(4.0, social_salience)), 3)

        # Bounded encounter memory for repeated local familiarity.
        encounter = encounter_memory.get(agent_id)
        if not isinstance(encounter, dict):
            encounter = {
                "encounter_count": 0,
                "last_encounter_tick": tick,
                "familiarity_score": 0.0,
            }
            encounter_memory[agent_id] = encounter
        encounter["encounter_count"] = int(encounter.get("encounter_count", 0)) + 1
        encounter["last_encounter_tick"] = int(tick)
        current_familiarity = float(encounter.get("familiarity_score", 0.0))
        familiarity_gain = float(ENCOUNTER_FAMILIARITY_GAIN)
        if bool(same_village):
            familiarity_gain += 0.02
        if str(record.get("recent_interaction", "")) == "co_present_success":
            familiarity_gain += 0.02
        encounter["familiarity_score"] = round(_clampf(current_familiarity + familiarity_gain), 3)
        if hasattr(world, "record_social_encounter_event"):
            world.record_social_encounter_event("total_encounter_events")
            if hasattr(world, "record_behavior_activity"):
                world.record_behavior_activity("encounter_event", x=int(agent.x), y=int(agent.y), agent=agent)
            if float(encounter.get("familiarity_score", 0.0)) >= 0.25:
                familiar_nearby += 1
                world.record_social_encounter_event("familiar_agent_proximity_events")
                if hasattr(world, "record_behavior_activity"):
                    world.record_behavior_activity("familiar_proximity", x=int(agent.x), y=int(agent.y), agent=agent)

    # Deterministic decay for unseen entries.
    for agent_id in sorted(list(known_agents.keys())):
        if agent_id in seen_ids:
            continue
        record = known_agents.get(agent_id)
        if not isinstance(record, dict):
            continue
        last_seen = int(record.get("last_seen_tick", tick))
        age = max(0, tick - last_seen)
        base_salience = float(record.get("social_salience", 0.0))
        decay = 0.02 * min(age, 10)
        record["social_salience"] = round(max(0.0, base_salience - decay), 3)
        if age > 20 and str(record.get("recent_interaction", "")) == "co_present_success":
            record["recent_interaction"] = "seen"

    # Deterministic encounter-memory decay and stale pruning.
    for agent_id in sorted(list(encounter_memory.keys())):
        encounter = encounter_memory.get(agent_id)
        if not isinstance(encounter, dict):
            encounter_memory.pop(agent_id, None)
            continue
        last_seen = int(encounter.get("last_encounter_tick", tick))
        age = max(0, tick - last_seen)
        if age > int(ENCOUNTER_STALE_TICKS):
            encounter_memory.pop(agent_id, None)
            continue
        if agent_id in seen_ids:
            continue
        familiarity = float(encounter.get("familiarity_score", 0.0))
        next_familiarity = max(
            0.0,
            familiarity - float(ENCOUNTER_FAMILIARITY_DECAY_PER_TICK) * float(min(age, 25)),
        )
        encounter["familiarity_score"] = round(next_familiarity, 3)

    # Familiar activity zone reinforcement from repeated encounters + useful local success.
    recent = get_recent_memory_events(agent, limit=8)
    useful_local_success = any(
        isinstance(ev, dict)
        and str(ev.get("outcome", "")) == "success"
        and str(ev.get("type", "")) in {"found_resource", "hunger_relief", "delivered_material", "construction_progress"}
        and tick - int(ev.get("tick", tick)) <= int(FAMILIAR_ZONE_USEFUL_REFRESH_WINDOW)
        for ev in recent
    )
    nearby_agents_count = int(len(nearby_agents))
    if nearby_agents_count <= int(FAMILIAR_ZONE_DENSITY_SOFT_CAP):
        density_factor = 1.0
    elif nearby_agents_count >= int(FAMILIAR_ZONE_DENSITY_HARD_CAP):
        density_factor = 0.4
    else:
        span = float(max(1, int(FAMILIAR_ZONE_DENSITY_HARD_CAP) - int(FAMILIAR_ZONE_DENSITY_SOFT_CAP)))
        over = float(nearby_agents_count - int(FAMILIAR_ZONE_DENSITY_SOFT_CAP))
        density_factor = 1.0 - 0.6 * (over / span)
    density_factor = max(0.4, min(1.0, density_factor))
    if familiar_nearby > 0 and useful_local_success:
        zx, zy = int(getattr(agent, "x", 0)), int(getattr(agent, "y", 0))
        matched = None
        for zone in familiar_zones:
            if not isinstance(zone, dict):
                continue
            if _manhattan((zx, zy), (int(zone.get("x", -9999)), int(zone.get("y", -9999)))) <= 3:
                matched = zone
                break
        gain = float(FAMILIAR_ZONE_SCORE_GAIN) + min(0.08, float(familiar_nearby) * 0.02)
        if isinstance(matched, dict):
            use_count = int(matched.get("use_count", 0))
            gain /= (1.0 + 0.18 * float(max(0, use_count - 1)))
        gain *= density_factor
        if density_factor < 0.98 and hasattr(world, "record_social_encounter_event"):
            world.record_social_encounter_event("dense_area_social_bias_reductions")
        if isinstance(matched, dict):
            prev_score = float(matched.get("score", 0.0))
            next_score = min(float(FAMILIAR_ZONE_SCORE_MAX), prev_score + gain)
            matched["score"] = round(next_score, 3)
            matched["last_tick"] = int(tick)
            matched["use_count"] = int(matched.get("use_count", 0)) + 1
            if next_score >= float(FAMILIAR_ZONE_SCORE_MAX) and prev_score < float(FAMILIAR_ZONE_SCORE_MAX) and hasattr(world, "record_social_encounter_event"):
                world.record_social_encounter_event("familiar_zone_saturation_clamps")
        else:
            initial_score = min(float(FAMILIAR_ZONE_SCORE_MAX), gain)
            familiar_zones.append(
                {
                    "x": zx,
                    "y": zy,
                    "score": round(initial_score, 3),
                    "last_tick": int(tick),
                    "use_count": 1,
                }
            )
            if initial_score >= float(FAMILIAR_ZONE_SCORE_MAX) and hasattr(world, "record_social_encounter_event"):
                world.record_social_encounter_event("familiar_zone_saturation_clamps")
        if hasattr(world, "record_social_encounter_event"):
            world.record_social_encounter_event("familiar_zone_reinforcement_events")
            world.record_social_encounter_event("familiar_zone_score_updates")

    # Zone score decay and bounded retention.
    keep_zones: List[Dict[str, Any]] = []
    for zone in familiar_zones:
        if not isinstance(zone, dict):
            continue
        age = max(0, tick - int(zone.get("last_tick", tick)))
        decay_rate = float(FAMILIAR_ZONE_SCORE_DECAY_PER_TICK)
        if not useful_local_success and age >= int(FAMILIAR_ZONE_USEFUL_REFRESH_WINDOW):
            decay_rate += float(FAMILIAR_ZONE_LOW_PAYOFF_DECAY_BOOST)
            if hasattr(world, "record_social_encounter_event"):
                world.record_social_encounter_event("familiar_zone_decay_due_to_low_payoff")
        score = max(0.0, float(zone.get("score", 0.0)) - decay_rate * float(min(age, 20)))
        if score <= 0.02 or age > 180:
            if hasattr(world, "record_social_encounter_event"):
                world.record_social_encounter_event("familiar_zone_score_decay")
            continue
        zone["score"] = round(score, 3)
        keep_zones.append(zone)
    keep_zones.sort(
        key=lambda z: (
            -float(z.get("score", 0.0)),
            -int(z.get("last_tick", 0)),
            int(z.get("y", 0)),
            int(z.get("x", 0)),
        )
    )
    agent.recent_familiar_activity_zones = keep_zones[: int(MAX_FAMILIAR_ACTIVITY_ZONES)]

    # Bounded social memory: drop least recent/least salient deterministically.
    max_known_agents = 40
    if len(known_agents) > max_known_agents:
        keys = sorted(
            known_agents.keys(),
            key=lambda k: (
                int(known_agents[k].get("last_seen_tick", 0)),
                float(known_agents[k].get("social_salience", 0.0)),
                int(known_agents[k].get("times_seen", 0)),
                str(k),
            ),
        )
        overflow = len(known_agents) - max_known_agents
        for k in keys[:overflow]:
            known_agents.pop(k, None)

    # Bounded encounter memory size.
    if len(encounter_memory) > int(MAX_RECENT_ENCOUNTERS):
        keys = sorted(
            encounter_memory.keys(),
            key=lambda k: (
                int((encounter_memory.get(k, {}) if isinstance(encounter_memory.get(k, {}), dict) else {}).get("last_encounter_tick", 0)),
                float((encounter_memory.get(k, {}) if isinstance(encounter_memory.get(k, {}), dict) else {}).get("familiarity_score", 0.0)),
                int((encounter_memory.get(k, {}) if isinstance(encounter_memory.get(k, {}), dict) else {}).get("encounter_count", 0)),
                str(k),
            ),
        )
        overflow = len(encounter_memory) - int(MAX_RECENT_ENCOUNTERS)
        for k in keys[:overflow]:
            encounter_memory.pop(k, None)


def update_agent_self_model(world: "World", agent: Agent) -> Dict[str, Any]:
    model = ensure_agent_self_model(agent)
    tick = int(getattr(world, "tick", 0))
    last_tick = int(model.get("last_self_update_tick", -1))
    if last_tick == tick:
        return model

    hunger = float(getattr(agent, "hunger", 100.0))
    if hunger < 45:
        model["survival_weight"] = _clampf(float(model["survival_weight"]) + 0.03)
        model["stress_level"] = _clampf(float(model["stress_level"]) + 0.04)
    elif hunger > 75:
        model["stress_level"] = _clampf(float(model["stress_level"]) - 0.02)

    recent_events = get_recent_memory_events(agent, limit=12)
    success_count = sum(1 for e in recent_events if str(e.get("outcome", "")) == "success")
    failure_count = sum(1 for e in recent_events if str(e.get("outcome", "")) == "failure")
    work_success = sum(
        1
        for e in recent_events
        if str(e.get("type", "")) in {"construction_progress", "delivered_material", "found_resource"}
        and str(e.get("outcome", "")) == "success"
    )
    social_success = sum(
        1
        for e in recent_events
        if str(e.get("type", "")) == "useful_building"
        and str(e.get("outcome", "")) == "success"
    )
    explore_success = sum(
        1
        for e in recent_events
        if str(e.get("type", "")) in {"found_resource", "hunger_relief"}
        and str(e.get("outcome", "")) == "success"
    )

    if work_success > 0:
        model["work_weight"] = _clampf(float(model["work_weight"]) + 0.01 * work_success)
    if social_success > 0:
        model["social_weight"] = _clampf(float(model["social_weight"]) + 0.01 * social_success)
    if explore_success > 0:
        model["exploration_weight"] = _clampf(float(model["exploration_weight"]) + 0.006 * explore_success)

    if failure_count > success_count:
        model["stress_level"] = _clampf(float(model["stress_level"]) + 0.02)
        model["recent_failure_bias"] = _clampf(float(model["recent_failure_bias"]) + 0.02)
        model["recent_success_bias"] = _clampf(float(model["recent_success_bias"]) - 0.01)
    elif success_count > failure_count:
        model["stress_level"] = _clampf(float(model["stress_level"]) - 0.01)
        model["recent_success_bias"] = _clampf(float(model["recent_success_bias"]) + 0.02)
        model["recent_failure_bias"] = _clampf(float(model["recent_failure_bias"]) - 0.01)

    # Local social familiarity affects social orientation gradually.
    known_agents = (getattr(agent, "social_memory", {}) or {}).get("known_agents", {})
    if isinstance(known_agents, dict):
        familiar = sum(1 for record in known_agents.values() if isinstance(record, dict) and int(record.get("times_seen", 0)) >= 3)
        if familiar > 0:
            model["social_weight"] = _clampf(float(model["social_weight"]) + 0.004 * min(familiar, 4))

    for key in ("survival_weight", "social_weight", "work_weight", "exploration_weight", "security_weight"):
        model[key] = round(_clampf(float(model.get(key, 0.5))), 3)
    model["stress_level"] = round(_clampf(float(model.get("stress_level", 0.2))), 3)
    model["recent_success_bias"] = round(_clampf(float(model.get("recent_success_bias", 0.5))), 3)
    model["recent_failure_bias"] = round(_clampf(float(model.get("recent_failure_bias", 0.2))), 3)
    model["last_self_update_tick"] = tick
    return model


def interpret_local_signals_with_self_model(world: "World", agent: Agent) -> Dict[str, Any]:
    model = ensure_agent_self_model(agent)
    proto_traits = ensure_agent_proto_traits(agent)
    state = getattr(agent, "subjective_state", {})
    local_signals = state.get("local_signals", {}) if isinstance(state, dict) else {}
    market_state = local_signals.get("market_state", {}) if isinstance(local_signals.get("market_state"), dict) else {}
    needs = local_signals.get("needs", {}) if isinstance(local_signals.get("needs"), dict) else {}
    survival = evaluate_local_survival_pressure(world, agent)
    survival_pressure = float(survival.get("survival_pressure", 0.0))
    food_crisis = bool(survival.get("food_crisis", False))

    food_pressure = float((market_state.get("food") or {}).get("pressure", 0.0))
    wood_pressure = float((market_state.get("wood") or {}).get("pressure", 0.0))
    stone_pressure = float((market_state.get("stone") or {}).get("pressure", 0.0))

    food_score = food_pressure * (0.9 + float(model.get("survival_weight", 0.5)) + float(proto_traits.get("caution", 0.5)) * 0.08)
    work_score = max(wood_pressure, stone_pressure) * (
        0.7 + float(model.get("work_weight", 0.5)) + float(proto_traits.get("diligence", 0.5)) * 0.08
    )
    social_score = (0.3 if bool(needs.get("need_materials")) else 0.0) * (0.8 + float(model.get("social_weight", 0.5)))
    explore_score = (1.0 - max(food_pressure, wood_pressure, stone_pressure)) * (
        float(model.get("exploration_weight", 0.3)) + float(proto_traits.get("curiosity", 0.5)) * 0.10
    )
    food_score += survival_pressure * 2.2
    work_score -= survival_pressure * 0.55
    social_score += survival_pressure * 0.20
    explore_score -= survival_pressure * 1.15
    if food_crisis:
        food_score += 1.8
        work_score -= 0.6
        explore_score -= 0.9

    preference = "food_security"
    if work_score > food_score and work_score >= social_score:
        preference = "work_materials"
    elif social_score > food_score and social_score >= work_score:
        preference = "social_coordination"
    elif explore_score > food_score and explore_score > work_score:
        preference = "exploration"

    preferred_resource = "food"
    if preference == "work_materials":
        preferred_resource = "wood" if wood_pressure >= stone_pressure else "stone"
    elif preference == "exploration":
        preferred_resource = "food" if food_pressure > 0.2 else ("wood" if wood_pressure >= stone_pressure else "stone")

    return {
        "priority_interpretation": preference,
        "preferred_resource": preferred_resource,
        "stress_narrowing": float(model.get("stress_level", 0.2)),
        "survival_pressure": survival_pressure,
    }


def build_agent_perception(world: "World", agent: Agent) -> Dict[str, Any]:
    ax, ay = int(agent.x), int(agent.y)
    visual_radius = max(1, int(getattr(agent, "visual_radius_tiles", 8)))
    social_radius = max(1, int(getattr(agent, "social_radius_tiles", visual_radius)))

    nearby_resources: Dict[str, List[Dict[str, int]]] = {"food": [], "wood": [], "stone": []}
    for resource_name in ("food", "wood", "stone"):
        coords = _iter_resource_coords(world, resource_name)
        visible = []
        for x, y in coords:
            dist = _manhattan((ax, ay), (int(x), int(y)))
            if dist <= visual_radius:
                visible.append((int(x), int(y), int(dist)))
        visible.sort(key=lambda item: (item[2], item[1], item[0]))
        nearby_resources[resource_name] = [
            {"x": x, "y": y, "distance": dist}
            for x, y, dist in visible
        ]

    nearby_buildings: List[Dict[str, Any]] = []
    for building_id in sorted(getattr(world, "buildings", {}).keys()):
        building = world.buildings[building_id]
        bx = int(building.get("x", 0))
        by = int(building.get("y", 0))
        dist = _manhattan((ax, ay), (bx, by))
        if dist > visual_radius:
            continue
        nearby_buildings.append(
            {
                "building_id": str(building.get("building_id", "")),
                "type": str(building.get("type", "")),
                "x": bx,
                "y": by,
                "distance": int(dist),
                "operational_state": str(building.get("operational_state", "active")),
            }
        )
    nearby_buildings.sort(key=lambda b: (b["distance"], b["y"], b["x"], b["building_id"]))

    nearby_agents: List[Dict[str, Any]] = []
    own_village_id = getattr(agent, "village_id", None)
    for other in getattr(world, "agents", []):
        if not getattr(other, "alive", False):
            continue
        if other is agent:
            continue
        ox = int(getattr(other, "x", 0))
        oy = int(getattr(other, "y", 0))
        dist = _manhattan((ax, ay), (ox, oy))
        if dist > social_radius:
            continue
        nearby_agents.append(
            {
                "agent_id": str(getattr(other, "agent_id", "")),
                "x": ox,
                "y": oy,
                "distance": int(dist),
                "role": str(getattr(other, "role", "npc")),
                "social_influence": round(_clampf(float(getattr(other, "social_influence", 0.0))), 3),
                "same_village": bool(
                    own_village_id is not None and getattr(other, "village_id", None) == own_village_id
                ),
            }
        )
    nearby_agents.sort(key=lambda a: (a["distance"], a["y"], a["x"], a["agent_id"]))
    encounter_memory = getattr(agent, "recent_encounters", {})
    familiar_nearby_count = 0
    if isinstance(encounter_memory, dict):
        for entry in nearby_agents:
            aid = str(entry.get("agent_id", ""))
            enc = encounter_memory.get(aid, {})
            if isinstance(enc, dict) and float(enc.get("familiarity_score", 0.0)) >= 0.22:
                familiar_nearby_count += 1

    terrain_summary: Dict[str, int] = {}
    nearby_transport: List[Dict[str, Any]] = []
    for dx in range(-visual_radius, visual_radius + 1):
        for dy in range(-visual_radius, visual_radius + 1):
            x = ax + dx
            y = ay + dy
            if x < 0 or y < 0 or x >= int(world.width) or y >= int(world.height):
                continue
            if _manhattan((ax, ay), (x, y)) > visual_radius:
                continue
            terrain = str(world.tiles[y][x])
            terrain_summary[terrain] = int(terrain_summary.get(terrain, 0)) + 1
            ttype = getattr(world, "get_transport_type", lambda _x, _y: None)(x, y)
            if ttype is not None:
                nearby_transport.append({"x": int(x), "y": int(y), "type": str(ttype)})
    nearby_transport.sort(key=lambda t: (t["y"], t["x"], t["type"]))

    return {
        "last_perception_tick": int(getattr(world, "tick", 0)),
        "radius": {"visual": visual_radius, "social": social_radius},
        "own_state": {
            "hunger": float(getattr(agent, "hunger", 0.0)),
            "role": str(getattr(agent, "role", "npc")),
            "task": str(getattr(agent, "task", "idle")),
            "inventory": {
                "food": int(getattr(agent, "inventory", {}).get("food", 0)),
                "wood": int(getattr(agent, "inventory", {}).get("wood", 0)),
                "stone": int(getattr(agent, "inventory", {}).get("stone", 0)),
            },
            "assigned_building_id": getattr(agent, "assigned_building_id", None),
        },
        "nearby_resources": nearby_resources,
        "nearby_buildings": nearby_buildings,
        "nearby_agents": nearby_agents,
        "social_density": {
            "nearby_agents_count": int(len(nearby_agents)),
            "familiar_nearby_agents_count": int(familiar_nearby_count),
        },
        "nearby_infrastructure": {"transport_tiles": nearby_transport},
        "terrain_summary": {k: int(v) for k, v in sorted(terrain_summary.items(), key=lambda item: item[0])},
        "local_signals": _village_local_signals(world, agent),
        "local_culture": _village_local_culture(world, agent),
    }


def evaluate_agent_salience(world: "World", agent: Agent) -> Dict[str, Any]:
    model = ensure_agent_self_model(agent)
    proto_traits = ensure_agent_proto_traits(agent)
    survival_w = float(model.get("survival_weight", 0.5))
    social_w = float(model.get("social_weight", 0.5))
    work_w = float(model.get("work_weight", 0.5))
    explore_w = float(model.get("exploration_weight", 0.3))
    stress = float(model.get("stress_level", 0.2))
    cooperation = float(proto_traits.get("cooperation", 0.5))
    diligence = float(proto_traits.get("diligence", 0.5))
    caution = float(proto_traits.get("caution", 0.5))
    curiosity = float(proto_traits.get("curiosity", 0.5))
    resilience = float(proto_traits.get("resilience", 0.5))
    effective_stress = stress * (1.0 - 0.35 * resilience)
    state = agent.subjective_state if isinstance(agent.subjective_state, dict) else {}
    own = state.get("own_state", {}) if isinstance(state.get("own_state"), dict) else {}
    role = str(own.get("role", getattr(agent, "role", "npc")))
    task = str(own.get("task", getattr(agent, "task", "idle")))
    hunger = float(own.get("hunger", getattr(agent, "hunger", 100.0)))
    assigned_building_id = own.get("assigned_building_id", getattr(agent, "assigned_building_id", None))

    local_signals = state.get("local_signals", {}) if isinstance(state.get("local_signals"), dict) else {}
    local_culture = state.get("local_culture", {}) if isinstance(state.get("local_culture"), dict) else {}
    market_state = local_signals.get("market_state", {}) if isinstance(local_signals.get("market_state"), dict) else {}
    needs = local_signals.get("needs", {}) if isinstance(local_signals.get("needs"), dict) else {}
    construction_needs = local_signals.get("construction_needs", {}) if isinstance(local_signals.get("construction_needs"), dict) else {}
    culture_coop = float(local_culture.get("cooperation_norm", 0.5))
    culture_work = float(local_culture.get("work_norm", 0.5))
    culture_explore = float(local_culture.get("exploration_norm", 0.5))
    culture_risk = float(local_culture.get("risk_norm", 0.5))
    culture_focus = str(local_culture.get("dominant_resource_focus", ""))
    survival = evaluate_local_survival_pressure(world, agent)
    survival_pressure = float(survival.get("survival_pressure", 0.0))
    food_crisis = bool(survival.get("food_crisis", False))

    nearby_resources = state.get("nearby_resources", {}) if isinstance(state.get("nearby_resources"), dict) else {}
    nearby_buildings = state.get("nearby_buildings", []) if isinstance(state.get("nearby_buildings"), list) else []
    nearby_agents = state.get("nearby_agents", []) if isinstance(state.get("nearby_agents"), list) else []
    familiar_zones = getattr(agent, "recent_familiar_activity_zones", [])
    if not isinstance(familiar_zones, list):
        familiar_zones = []
    nearby_count = int(len(nearby_agents))
    if nearby_count <= int(FAMILIAR_ZONE_DENSITY_SOFT_CAP):
        density_zone_factor = 1.0
    elif nearby_count >= int(FAMILIAR_ZONE_DENSITY_HARD_CAP):
        density_zone_factor = 0.4
    else:
        span = float(max(1, int(FAMILIAR_ZONE_DENSITY_HARD_CAP) - int(FAMILIAR_ZONE_DENSITY_SOFT_CAP)))
        over = float(nearby_count - int(FAMILIAR_ZONE_DENSITY_SOFT_CAP))
        density_zone_factor = 1.0 - 0.6 * (over / span)
    density_zone_factor = max(0.4, min(1.0, density_zone_factor))

    scored_resources: List[Dict[str, Any]] = []
    recent_resource_events = find_recent_resource_memory(agent, "food") + find_recent_resource_memory(agent, "wood") + find_recent_resource_memory(agent, "stone")
    recent_resource_boost: Dict[Tuple[str, int, int], float] = {}
    for ev in recent_resource_events[-12:]:
        loc = ev.get("location", {})
        if not isinstance(loc, dict):
            continue
        rx = int(loc.get("x", 0))
        ry = int(loc.get("y", 0))
        rr = str(ev.get("resource_type", ""))
        if rr not in {"food", "wood", "stone"}:
            continue
        if str(ev.get("outcome", "")) == "success":
            recent_resource_boost[(rr, rx, ry)] = max(recent_resource_boost.get((rr, rx, ry), 0.0), 0.7)
        elif str(ev.get("outcome", "")) == "failure":
            recent_resource_boost[(rr, rx, ry)] = min(recent_resource_boost.get((rr, rx, ry), 0.0), -0.5)
    for resource in ("food", "wood", "stone"):
        entries = nearby_resources.get(resource, [])
        if not isinstance(entries, list):
            continue
        market_pressure = float((market_state.get(resource) or {}).get("pressure", 0.0)) if isinstance(market_state, dict) else 0.0
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            x = int(entry.get("x", 0))
            y = int(entry.get("y", 0))
            distance = int(entry.get("distance", abs(x - int(agent.x)) + abs(y - int(agent.y))))
            score = 1.0 / (1.0 + float(distance))
            score += market_pressure * 1.5
            score -= min(0.6, effective_stress * 0.07 * float(distance))
            score -= caution * 0.015 * float(distance)
            score -= max(0.0, (1.0 - culture_risk)) * 0.01 * float(distance)

            if resource == "food":
                if hunger < 60:
                    score += 2.0 * (0.6 + survival_w)
                if hunger < 35:
                    score += 3.0 * (0.6 + survival_w)
                if bool(needs.get("food_urgent")) or bool(needs.get("food_buffer_critical")):
                    score += 2.5 * (0.6 + survival_w)
                score += survival_pressure * 2.0
                if food_crisis:
                    score += 1.2
            if role == "miner" and resource == "stone":
                score += 2.5 * (0.5 + work_w)
            if role == "woodcutter" and resource == "wood":
                score += 2.5 * (0.5 + work_w)
            if role == "builder" and resource in {"wood", "stone"}:
                score += 1.8 * (0.5 + work_w + diligence * 0.12)
            if role == "hauler" and int(construction_needs.get(resource, 0)) > 0:
                score += 1.5 * (0.4 + social_w)

            if task in {"mine_cycle"} and resource == "stone":
                score += 2.0
            if task in {"lumber_cycle"} and resource == "wood":
                score += 2.0
            if task in {"gather_food_wild"} and resource == "food":
                score += 2.0
            if task in {"build_storage", "build_house", "gather_materials"} and resource in {"wood", "stone"}:
                score += 1.8 * (0.5 + work_w + diligence * 0.10)
            if task in {"survive", "idle"} and resource != "food":
                score += explore_w * 0.2 + curiosity * 0.12
            if food_crisis and resource in {"wood", "stone"}:
                score -= 0.9
            if culture_focus == resource:
                score += 0.22
            for zone in familiar_zones[:4]:
                if not isinstance(zone, dict):
                    continue
                zd = _manhattan((x, y), (int(zone.get("x", x)), int(zone.get("y", y))))
                if zd <= 6:
                    zone_bonus = float(zone.get("score", 0.0)) * (0.18 / float(max(1, zd))) * density_zone_factor
                    score += zone_bonus
                    if density_zone_factor < 0.98 and zone_bonus > 0.0 and hasattr(world, "record_social_encounter_event"):
                        world.record_social_encounter_event("overcrowded_familiar_bias_suppressed")
            score += recent_resource_boost.get((resource, x, y), 0.0)

            scored_resources.append(
                {
                    "resource": resource,
                    "x": x,
                    "y": y,
                    "distance": distance,
                    "salience": round(float(score), 3),
                }
            )

    scored_resources.sort(
        key=lambda r: (
            -float(r["salience"]),
            int(r["distance"]),
            int(r["y"]),
            int(r["x"]),
            str(r["resource"]),
        )
    )
    top_resource_targets = scored_resources[:3]

    scored_buildings: List[Dict[str, Any]] = []
    recent_useful_building_events = get_recent_memory_events(agent, "useful_building", limit=16)
    useful_building_boost: Dict[str, float] = {}
    for ev in recent_useful_building_events:
        bid = str(ev.get("target_id", ""))
        if not bid:
            continue
        useful_building_boost[bid] = max(useful_building_boost.get(bid, 0.0), 0.9)
    for entry in nearby_buildings:
        if not isinstance(entry, dict):
            continue
        btype = str(entry.get("type", ""))
        building_id = str(entry.get("building_id", ""))
        distance = int(entry.get("distance", 0))
        operational_state = str(entry.get("operational_state", "active"))
        score = 1.0 / (1.0 + float(distance))
        score -= min(0.5, effective_stress * 0.05 * float(distance))
        score -= caution * 0.01 * float(distance)
        score -= max(0.0, (1.0 - culture_risk)) * 0.008 * float(distance)

        if assigned_building_id is not None and str(assigned_building_id) == building_id:
            score += 5.0
        if role == "miner" and btype == "mine":
            score += 3.0
        if role == "woodcutter" and btype == "lumberyard":
            score += 3.0
        if role in {"builder", "hauler"} and operational_state == "under_construction":
            score += 3.0 * (0.5 + work_w + diligence * 0.10)
            score += culture_work * 0.25
            if food_crisis:
                score -= 1.1
        if btype == "storage" and (role in {"hauler", "builder"} or hunger < 55):
            score += 2.0 * (0.5 + max(work_w, survival_w))
            score += survival_pressure * 0.8
        if task in {"build_storage"} and btype == "storage":
            score += 2.5
        if task in {"build_house"} and btype == "house":
            score += 2.0
        if int(construction_needs.get("wood", 0)) + int(construction_needs.get("stone", 0)) > 0 and operational_state == "under_construction":
            score += 1.0 + diligence * 0.15
            score += culture_work * 0.18
            if food_crisis:
                score -= 0.8
        score += useful_building_boost.get(building_id, 0.0)
        for zone in familiar_zones[:4]:
            if not isinstance(zone, dict):
                continue
            zd = _manhattan((int(entry.get("x", 0)), int(entry.get("y", 0))), (int(zone.get("x", 0)), int(zone.get("y", 0))))
            if zd <= 6:
                zone_bonus = float(zone.get("score", 0.0)) * (0.14 / float(max(1, zd))) * density_zone_factor
                score += zone_bonus
                if density_zone_factor < 0.98 and zone_bonus > 0.0 and hasattr(world, "record_social_encounter_event"):
                    world.record_social_encounter_event("overcrowded_familiar_bias_suppressed")

        scored_buildings.append(
            {
                "building_id": building_id,
                "type": btype,
                "x": int(entry.get("x", 0)),
                "y": int(entry.get("y", 0)),
                "distance": distance,
                "salience": round(float(score), 3),
            }
        )

    scored_buildings.sort(
        key=lambda b: (
            -float(b["salience"]),
            int(b["distance"]),
            int(b["y"]),
            int(b["x"]),
            str(b["building_id"]),
        )
    )
    top_building_targets = scored_buildings[:3]

    scored_social: List[Dict[str, Any]] = []
    social_memory = getattr(agent, "social_memory", {})
    known_agents = social_memory.get("known_agents", {}) if isinstance(social_memory, dict) else {}
    encounter_memory = getattr(agent, "recent_encounters", {})
    familiar_count = 0
    familiar_strength = 0.0
    for entry in nearby_agents:
        if not isinstance(entry, dict):
            continue
        distance = int(entry.get("distance", 0))
        other_role = str(entry.get("role", "npc"))
        other_id = str(entry.get("agent_id", ""))
        same_village = bool(entry.get("same_village", False))
        other_influence = _clampf(float(entry.get("social_influence", 0.0)))
        score = 1.0 / (1.0 + float(distance))
        score += other_influence * 0.8
        if other_role == "leader":
            score += 1.0 * (0.4 + social_w)
        if other_role == role:
            score += 0.5 * (0.4 + social_w)
        if same_village:
            score += 0.6 * (0.5 + social_w + cooperation * 0.18)
            score += culture_coop * 0.15
        record = known_agents.get(other_id, {}) if isinstance(known_agents, dict) else {}
        if isinstance(record, dict):
            score += min(1.5, float(record.get("social_salience", 0.0)) * 0.35)
            if int(record.get("times_seen", 0)) >= 3:
                score += 0.4
            if str(record.get("recent_interaction", "")) == "co_present_success":
                score += 0.7 * (0.4 + social_w + cooperation * 0.12)
        encounter = encounter_memory.get(other_id, {}) if isinstance(encounter_memory, dict) else {}
        if isinstance(encounter, dict):
            familiarity = float(encounter.get("familiarity_score", 0.0))
            score += min(0.9, familiarity * 0.55)
            if familiarity >= 0.22:
                familiar_count += 1
                familiar_strength += familiarity
        scored_social.append(
            {
                "agent_id": other_id,
                "role": other_role,
                "x": int(entry.get("x", 0)),
                "y": int(entry.get("y", 0)),
                "distance": distance,
                "same_village": same_village,
                "salience": round(float(score), 3),
            }
        )
    scored_social.sort(
        key=lambda a: (
            -float(a["salience"]),
            int(a["distance"]),
            int(a["y"]),
            int(a["x"]),
            str(a["agent_id"]),
        )
    )
    top_social_targets = scored_social[:3]
    local_social_density = float(len(nearby_agents))
    familiar_density = float(familiar_count)
    density_signal = min(1.0, (local_social_density / 5.0) * 0.6 + (familiar_density / 3.0) * 0.4)
    familiar_agents_nearby = [
        {
            "agent_id": str(s.get("agent_id", "")),
            "role": str(s.get("role", "npc")),
            "same_village": bool(s.get("same_village", False)),
        }
        for s in top_social_targets
        if int((known_agents.get(str(s.get("agent_id", "")), {}) if isinstance(known_agents, dict) else {}).get("times_seen", 0)) >= 2
    ][:3]
    salient_local_leader = detect_local_leader(agent)

    leader_nearby = bool(salient_local_leader)
    if leader_nearby:
        # Small social-follow bias: cooperation gets a nudge while exploration de-escalates.
        for entry in top_building_targets:
            if str(entry.get("type", "")) in {"storage", "house", "farm_plot", "mine", "lumberyard"}:
                entry["salience"] = round(float(entry.get("salience", 0.0)) + 0.25, 3)
        for entry in top_resource_targets:
            if str(entry.get("resource", "")) in {"wood", "stone", "food"}:
                entry["salience"] = round(float(entry.get("salience", 0.0)) + 0.12, 3)
        top_building_targets.sort(
            key=lambda b: (
                -float(b["salience"]),
                int(b["distance"]),
                int(b["y"]),
                int(b["x"]),
                str(b["building_id"]),
            )
        )
        top_resource_targets.sort(
            key=lambda r: (
                -float(r["salience"]),
                int(r["distance"]),
                int(r["y"]),
                int(r["x"]),
                str(r["resource"]),
            )
        )

    # Weak local social-density utility bias in viable conditions.
    if survival_pressure < 0.70 and hunger >= 35.0 and density_signal > 0.20:
        social_bonus = 0.10 + density_signal * 0.22 + min(0.18, familiar_strength * 0.08)
        social_bonus *= density_zone_factor
        if density_zone_factor < 0.98 and hasattr(world, "record_social_encounter_event"):
            world.record_social_encounter_event("dense_area_social_bias_reductions")
        if top_resource_targets:
            top_resource_targets[0]["salience"] = round(float(top_resource_targets[0]["salience"]) + social_bonus * 0.6, 3)
        if top_building_targets:
            top_building_targets[0]["salience"] = round(float(top_building_targets[0]["salience"]) + social_bonus * 0.4, 3)
        if hasattr(world, "record_social_encounter_event"):
            world.record_social_encounter_event("social_density_bias_applied_count")

    cultural_bias = {}
    if hasattr(world, "get_local_practice_bias"):
        try:
            cultural_bias = world.get_local_practice_bias(int(agent.x), int(agent.y))
        except Exception:
            cultural_bias = {}
    food_cultural = float(cultural_bias.get("productive_food_patch", 0.0)) + float(cultural_bias.get("good_gathering_zone", 0.0))
    farm_cultural = float(cultural_bias.get("proto_farm_area", 0.0))
    construction_cultural = float(cultural_bias.get("construction_cluster", 0.0)) + float(cultural_bias.get("stable_storage_area", 0.0))
    applied_cultural_bonus = False
    if survival_pressure < 0.82:
        food_bonus = min(0.85, food_cultural * 0.22 + farm_cultural * 0.14)
        if food_bonus > 0.0:
            for entry in top_resource_targets:
                if str(entry.get("resource", "")) == "food":
                    dist = max(1, int(entry.get("distance", 1)))
                    entry["salience"] = round(float(entry.get("salience", 0.0)) + (food_bonus / float(dist)), 3)
                    applied_cultural_bonus = True
        build_bonus = min(0.75, construction_cultural * 0.20)
        if build_bonus > 0.0:
            for entry in top_building_targets:
                btype = str(entry.get("type", ""))
                state = str(entry.get("operational_state", "active"))
                if btype in {"house", "storage", "farm_plot"} or state == "under_construction":
                    dist = max(1, int(entry.get("distance", 1)))
                    entry["salience"] = round(float(entry.get("salience", 0.0)) + (build_bonus / float(dist)), 3)
                    applied_cultural_bonus = True
        if applied_cultural_bonus and hasattr(world, "record_settlement_progression_metric"):
            world.record_settlement_progression_metric("agents_using_cultural_memory_bias")
        if applied_cultural_bonus:
            top_resource_targets.sort(
                key=lambda r: (
                    -float(r["salience"]),
                    int(r["distance"]),
                    int(r["y"]),
                    int(r["x"]),
                    str(r["resource"]),
                )
            )
            top_building_targets.sort(
                key=lambda b: (
                    -float(b["salience"]),
                    int(b["distance"]),
                    int(b["y"]),
                    int(b["x"]),
                    str(b["building_id"]),
                )
            )

    dominant_local_signal = "none"
    food_pressure = float((market_state.get("food") or {}).get("pressure", 0.0)) if isinstance(market_state, dict) else 0.0
    wood_pressure = float((market_state.get("wood") or {}).get("pressure", 0.0)) if isinstance(market_state, dict) else 0.0
    stone_pressure = float((market_state.get("stone") or {}).get("pressure", 0.0)) if isinstance(market_state, dict) else 0.0

    if bool(needs.get("food_urgent")) or bool(needs.get("food_buffer_critical")):
        dominant_local_signal = "food_urgent"
    elif food_crisis:
        dominant_local_signal = "food_crisis"
    elif food_pressure >= max(wood_pressure, stone_pressure) and food_pressure >= 0.45:
        dominant_local_signal = "food_scarcity"
    elif int(construction_needs.get("wood", 0)) + int(construction_needs.get("stone", 0)) > 0:
        dominant_local_signal = "construction_pressure"
    elif str(local_signals.get("priority", "")):
        dominant_local_signal = f"priority:{str(local_signals.get('priority', ''))}"

    current_focus = "stabilize"
    if hunger < 35:
        current_focus = "urgent_food"
    elif role == "miner":
        current_focus = "stone_extraction"
    elif role == "woodcutter":
        current_focus = "wood_extraction"
    elif role == "builder":
        current_focus = "construction"
    elif role == "hauler":
        current_focus = "logistics"
    elif dominant_local_signal in {"food_urgent", "food_scarcity"}:
        current_focus = "food_security"
    elif dominant_local_signal == "food_crisis":
        current_focus = "urgent_food"
    elif dominant_local_signal == "construction_pressure":
        current_focus = "construction_support"
    elif farm_cultural >= 0.45 and role == "farmer" and survival_pressure < 0.55 and hunger >= 35.0:
        current_focus = "farming_continuity"
    elif (
        explore_w + curiosity * 0.12 + culture_explore * 0.10 > 0.55
        and effective_stress < 0.35
        and not leader_nearby
        and survival_pressure < 0.45
    ):
        current_focus = "exploration"

    return {
        "top_resource_targets": top_resource_targets,
        "top_building_targets": top_building_targets,
        "top_social_targets": top_social_targets,
        "familiar_agents_nearby": familiar_agents_nearby,
        "social_density_signal": round(density_signal, 3),
        "cultural_memory_signal": {
            "food_practice": round(float(food_cultural), 3),
            "farm_practice": round(float(farm_cultural), 3),
            "construction_practice": round(float(construction_cultural), 3),
        },
        "salient_local_leader": salient_local_leader,
        "dominant_local_signal": dominant_local_signal,
        "current_focus": current_focus,
    }


def _update_short_term_memory(agent: Agent, max_items: int = 12) -> None:
    state = agent.subjective_state if isinstance(agent.subjective_state, dict) else {}
    tick = int(state.get("last_perception_tick", 0))
    attention = state.get("attention", {}) if isinstance(state.get("attention"), dict) else {}
    nearby_resources = state.get("nearby_resources", {})
    recent_resources = []
    salient_resources = []
    for entry in (attention.get("top_resource_targets", []) if isinstance(attention.get("top_resource_targets", []), list) else []):
        if isinstance(entry, dict):
            salient_resources.append(
                {
                    "tick": tick,
                    "resource": str(entry.get("resource", "")),
                    "x": int(entry.get("x", 0)),
                    "y": int(entry.get("y", 0)),
                    "salient": True,
                }
            )
    if isinstance(nearby_resources, dict):
        for resource in ("food", "wood", "stone"):
            entries = nearby_resources.get(resource, [])
            if not isinstance(entries, list):
                continue
            for entry in entries[:2]:
                if isinstance(entry, dict):
                    recent_resources.append(
                        {"tick": tick, "resource": resource, "x": int(entry.get("x", 0)), "y": int(entry.get("y", 0))}
                    )

    recent_agents = []
    for entry in (state.get("nearby_agents", []) if isinstance(state.get("nearby_agents", []), list) else [])[:4]:
        if isinstance(entry, dict):
            recent_agents.append({"tick": tick, "agent_id": str(entry.get("agent_id", "")), "x": int(entry.get("x", 0)), "y": int(entry.get("y", 0))})

    recent_buildings = []
    for entry in (state.get("nearby_buildings", []) if isinstance(state.get("nearby_buildings", []), list) else [])[:4]:
        if isinstance(entry, dict):
            recent_buildings.append(
                {
                    "tick": tick,
                    "building_id": str(entry.get("building_id", "")),
                    "type": str(entry.get("type", "")),
                    "x": int(entry.get("x", 0)),
                    "y": int(entry.get("y", 0)),
                }
            )

    for key, incoming in (
        ("recently_seen_resources", salient_resources + recent_resources),
        ("recently_seen_agents", recent_agents),
        ("recently_seen_buildings", recent_buildings),
    ):
        existing = agent.short_term_memory.get(key, [])
        if not isinstance(existing, list):
            existing = []
        merged = existing + incoming
        agent.short_term_memory[key] = merged[-max_items:]
