from __future__ import annotations

import random
import json
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
PROTO_COMMUNITY_RADIUS = 4
PROTO_COMMUNITY_MIN_AGENTS = 2
PROTO_COMMUNITY_FORMATION_STREAK = 3
PROTO_COMMUNITY_STALE_TICKS = 120
CAMP_ACTIVE_STALE_TICKS = 240
CAMP_FORMATION_HUNGER_MIN = 18.0
CAMP_REST_RADIUS = 2
CAMP_ANCHOR_RADIUS = 10
CAMP_DEACTIVATION_ABSENCE_TICKS = 36
CAMP_LINKED_COMMUNITY_ABSENCE_BONUS_TICKS = 72
CAMP_SUPPORT_EVAL_RADIUS = 14
CAMP_SUPPORT_RECENT_USE_TICKS = 28
CAMP_SUPPORT_GRACE_ABSENCE_BONUS_TICKS = 18
CAMP_LOCAL_VIABLE_RADIUS = 8
CAMP_DOMINANT_PULL_DISTANCE_GAP = 4
CAMP_DOMINANT_CLUSTER_NEARBY_AGENT_THRESHOLD = 7
CLUSTER_PATCH_ACTIVITY_DECAY = 0.985
CLUSTER_PATCH_ACTIVITY_MAX = 120.0
CLUSTER_PRODUCTIVITY_RADIUS = 8
CLUSTER_ABSORPTION_DELAY_STREAK_MAX = PROTO_COMMUNITY_FORMATION_STREAK + 2
SECONDARY_NUCLEUS_STRUCTURE_RADIUS = 6
SECONDARY_NUCLEUS_BUILD_GRAVITY_RADIUS = 8
SECONDARY_NUCLEUS_BUILD_GRAVITY_BONUS = 18
SECONDARY_NUCLEUS_COHESION_BONUS_CAP = 14
SECONDARY_NUCLEUS_MATERIALIZATION_GRACE_TICKS = 28
SECONDARY_NUCLEUS_BUILDER_CONTINUITY_BONUS_TICKS = 6
CAMP_FOOD_CACHE_CAPACITY = 8
HOUSE_DOMESTIC_FOOD_CAPACITY = 4
HOUSE_DOMESTIC_DEPOSIT_RADIUS = 2
HOUSE_DOMESTIC_CONSUME_RADIUS = 3
CAMP_FOOD_ACCESS_RADIUS = 3
CULTURAL_MEMORY_CELL_SIZE = 5
CULTURAL_MEMORY_ACCESS_RADIUS = 8
CULTURAL_MEMORY_MAX_CONFIDENCE = 6.0
CULTURAL_MEMORY_MIN_CONFIDENCE = 0.18
CAMP_FOOD_DECAY_INTERVAL_TICKS = 50
LOCAL_FOOD_PRESSURE_RADIUS = 10
LOCAL_FOOD_PRESSURE_NEEDY_HUNGER = 50.0
LOCAL_HANDOFF_MAX_DISTANCE = 1
LOCAL_HANDOFF_RECEIVER_HUNGER_THRESHOLD = 20.0
LOCAL_HANDOFF_RECEIVER_CRITICAL_HUNGER_OVERRIDE = 14.0
LOCAL_HANDOFF_DONOR_MIN_FOOD = 2
LOCAL_HANDOFF_DONOR_MIN_HUNGER = 65.0
LOCAL_HANDOFF_COOLDOWN_TICKS = 36
LOCAL_HANDOFF_PAIR_COOLDOWN_TICKS = 60
LOCAL_HANDOFF_RECENT_RESCUE_TICKS = 80
EARLY_SURVIVAL_RELIEF_TICKS = 320
EARLY_SURVIVAL_RELIEF_HUNGER_DECAY_MULTIPLIER = 0.9
SETTLEMENT_STABILITY_TICK_THRESHOLD = 120
FOOD_PATCH_MIN_COUNT = 3
FOOD_PATCH_MAX_COUNT = 6
FOOD_PATCH_MIN_RADIUS = 5
FOOD_PATCH_MAX_RADIUS = 8
FOOD_PATCH_REGEN_MULTIPLIER = 1.35
FOOD_PATCH_DENSITY_MULTIPLIER = 1.25
FOOD_PATCH_EXTRA_INITIAL_FOOD_RATIO = 0.2
PROTO_SPECIALIZATION_KEYS = ("none", "food_gatherer", "food_hauler", "builder")
PROTO_SPECIALIZATION_PERSISTENCE_TICKS = {
    "food_gatherer": 18,
    "food_hauler": 18,
    "builder": 16,
}
PROTO_COMMUNITY_FUNNEL_STAGES = (
    "co_presence_detected",
    "co_presence_cluster_valid",
    "proto_streak_incremented",
    "proto_viability_check_passed",
    "proto_community_formed",
)
PROTO_COMMUNITY_FUNNEL_FAILURE_REASONS = {
    "cluster_too_small",
    "cluster_not_persistent",
    "agents_starving",
    "area_not_viable",
    "agents_moving_apart",
    "blocked_by_existing_structure",
    "other_guard",
}
CAMP_LIFECYCLE_STAGES = (
    "camp_created",
    "camp_became_active",
    "camp_used_for_rest",
    "camp_used_for_return",
    "camp_population_present",
    "camp_deactivated",
)
CAMP_LIFECYCLE_DEACTIVATION_REASONS = {
    "camp_stale_timeout",
    "no_agents_nearby",
    "agents_migrated",
    "no_viable_support",
    "area_no_longer_viable",
    "replaced_by_village_anchor",
    "replaced_by_house_anchor",
    "other_guard",
}
CAMP_LIFECYCLE_RETENTION_REASONS = {
    "recent_use",
    "nearby_agents",
    "food_cache",
    "anchored_loop_support",
}
CAMP_TARGETING_STAGES = (
    "rest_target_home",
    "rest_target_camp",
    "rest_target_idle",
)
CAMP_TARGETING_REASONS = {
    "no_camp_in_range",
    "camp_not_active",
    "hunger_override",
    "task_override",
    "other_guard",
}


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


def _default_resource_respawn_stats() -> Dict[str, int]:
    return {
        "food_respawned_total": 0,
        "wood_respawned_total": 0,
        "stone_respawned_total": 0,
    }


WORKFORCE_REALIZATION_ROLES = ("farmer", "forager", "hauler", "builder", "miner", "woodcutter")
WORKFORCE_AFFILIATION_CLASSES = ("resident", "attached", "transient", "unaffiliated")
WORKFORCE_BLOCK_REASONS = {
    "no_valid_task",
    "no_target_found",
    "no_materials_available",
    "no_storage_available",
    "no_construction_site",
    "waiting_on_delivery",
    "survival_override",
    "role_hold_block",
    "task_conflict",
    "no_affiliated_village_context",
}
WORKFORCE_REALIZATION_PRODUCTIVE_WINDOW_TICKS = 80
WORKFORCE_REALIZATION_IDLE_GRACE_TICKS = 20
MOVEMENT_DIAGNOSTIC_ROLES = ("farmer", "forager", "hauler", "builder", "miner", "woodcutter")
MOVEMENT_DIAGNOSTIC_CONTEXTS = ("off_network", "path", "road", "logistics_corridor", "bridge", "tunnel")
RECOVERY_DIAGNOSTIC_ROLES = ("farmer", "forager", "hauler", "builder", "miner", "woodcutter", "npc", "other")
RECOVERY_FUNNEL_STAGES = (
    "recovery_context_seen",
    "high_sleep_need_seen",
    "high_fatigue_seen",
    "rest_candidate_seen",
    "rest_task_selected",
    "home_target_available",
    "home_target_selected",
    "idle_recovery_applied",
    "home_recovery_applied",
    "recovery_success_tick",
)
RECOVERY_FAILURE_REASONS = {
    "rest_not_needed",
    "rest_not_selected",
    "survival_override",
    "work_task_retained",
    "no_home",
    "not_resident",
    "no_valid_home_target",
    "task_replaced",
    "recovery_only_idle",
    "recovery_home_success",
    "recovery_idle_success",
    "unknown_failure",
}
DELIVERY_DIAGNOSTIC_STAGES = (
    "delivery_target_created_count",
    "delivery_target_visible_count",
    "delivery_target_reserved_count",
    "resource_source_found_count",
    "resource_pickup_attempt_count",
    "resource_pickup_success_count",
    "hauler_departed_with_resource_count",
    "site_arrival_count",
    "delivery_attempt_count",
    "delivery_success_count",
    "delivery_abandoned_count",
)
DELIVERY_DIAGNOSTIC_FAILURE_REASONS = {
    "no_delivery_target",
    "no_source_storage",
    "no_resource_available",
    "source_depleted",
    "reservation_lost",
    "site_invalidated",
    "site_not_in_range",
    "no_path_to_source",
    "no_path_to_site",
    "arrival_failed",
    "retargeted_before_delivery",
    "interrupted_by_other_priority",
    "inventory_empty",
    "task_replaced",
    "path_failed",
    "hauler_reassigned",
    "construction_completed_before_delivery",
    "unknown_failure",
}
HOUSING_CONSTRUCTION_STAGES = (
    "house_plan_requested",
    "house_site_created",
    "house_site_visible_to_workers",
    "house_material_requirement_detected",
    "house_delivery_target_created",
    "house_delivery_reserved",
    "house_delivery_attempt",
    "house_delivery_success",
    "house_construction_progress_tick",
    "house_construction_completed",
    "house_building_activated",
)
HOUSING_CONSTRUCTION_FAILURE_REASONS = {
    "no_build_location",
    "terrain_invalid",
    "village_not_viable",
    "no_delivery_target",
    "no_resource_available",
    "no_source_storage",
    "hauler_reassigned",
    "path_failed",
    "no_builder_assigned",
    "builder_reassigned",
    "builder_starving",
    "materials_missing",
    "site_invalidated",
    "activation_state_mismatch",
    "construction_completed_not_activated",
}
HOUSING_WORKER_PARTICIPATION_KEYS = (
    "builder_assigned_to_house",
    "builder_arrived_at_house",
    "builder_progress_events",
    "hauler_assigned_house_delivery",
    "hauler_pickup_house_material",
    "hauler_arrived_house",
    "hauler_delivery_success",
)
HOUSING_SITING_REJECTION_REASONS = {
    "overlap_with_structure",
    "blocked_by_road",
    "non_walkable",
    "terrain_invalid",
    "too_dense",
    "too_far_from_anchor",
    "village_cap_block",
    "reserved_space_block",
    "invalid_house_footprint",
    "other_guard",
}
HOUSING_SITING_SEARCH_STAGES = (
    "house_candidate_scan_started",
    "house_candidate_evaluated",
    "house_candidate_passed_all_checks",
    "house_site_created",
)
HOUSING_PATH_COHERENCE_KEYS = (
    "house_created_via_bootstrap",
    "house_created_via_construction_site",
    "house_completed_via_construction_progress",
    "house_activated_via_completion_hook",
    "house_activated_via_direct_path",
    "house_path_unknown",
)
ASSIGNMENT_GAP_STAGES = (
    "assigned_role_count",
    "task_selected_count",
    "target_found_count",
    "movement_started_count",
    "action_attempted_count",
    "productive_action_count",
    "abandoned_or_overridden_count",
)
ASSIGNMENT_GAP_BLOCK_REASONS = {
    "no_task_candidate",
    "no_target_candidate",
    "target_too_far",
    "no_path",
    "no_materials",
    "no_storage",
    "no_construction_site",
    "no_farm_target",
    "no_resource_target",
    "waiting_on_delivery",
    "survival_override",
    "role_reassigned",
    "task_replaced",
    "affiliation_context_missing",
}
TASK_COMPLETION_KEYS = (
    "farm_work",
    "farm_harvest",
    "build_house",
    "build_storage",
    "construction_progress",
    "construction_delivery",
    "deposit_to_storage",
    "internal_transfer",
    "farm_haul_harvest",
)
TASK_COMPLETION_STAGES = (
    "task_attempt_count",
    "preconditions_met_count",
    "preconditions_failed_count",
    "productive_completion_count",
    "interrupted_or_replaced_count",
)
TASK_COMPLETION_FAILURE_REASONS = {
    "no_farm_available",
    "farm_not_ready",
    "farm_not_owned_or_not_village_relevant",
    "too_far_from_farm",
    "inventory_full",
    "no_path",
    "task_replaced",
    "survival_override",
    "no_construction_site",
    "site_not_in_range",
    "no_materials_in_inventory",
    "no_materials_in_buffer",
    "waiting_on_delivery",
    "invalid_site_state",
    "construction_already_complete",
    "no_delivery_target",
    "no_source_storage",
    "no_target_storage",
    "no_resource_available",
    "no_reserved_delivery",
    "target_not_in_range",
    "inventory_empty",
}


def _empty_workforce_affiliation_counts() -> Dict[str, int]:
    return {k: 0 for k in WORKFORCE_AFFILIATION_CLASSES}


def _empty_workforce_realization_role_metrics() -> Dict[str, Any]:
    return {
        "target_count": 0,
        "assigned_count": 0,
        "active_task_count": 0,
        "productive_action_count": 0,
        "blocked_or_idle_count": 0,
        "productive_actions": {},
        "block_reasons": {},
    }


def _empty_assignment_gap_role_metrics() -> Dict[str, Any]:
    payload = {k: 0 for k in ASSIGNMENT_GAP_STAGES}
    payload["block_reasons"] = {}
    return payload


def _empty_task_completion_task_metrics() -> Dict[str, Any]:
    payload = {k: 0 for k in TASK_COMPLETION_STAGES}
    payload["failure_reasons"] = {}
    return payload


def _empty_movement_metrics() -> Dict[str, Any]:
    return {
        "movement_ticks_total": 0,
        "no_progress_ticks": 0,
        "oscillation_events": 0,
        "backtrack_steps": 0,
        "same_area_retarget_count": 0,
        "target_changes_count": 0,
        "path_recompute_count": 0,
        "near_target_indecision_count": 0,
        "net_displacement": 0,
        "gross_displacement": 0,
        "tile_occupancy_samples": 0,
        "tile_occupancy_peak": 0,
        "multi_agent_tile_events": 0,
        "blocked_by_agent_count": 0,
        "attempted_move_into_occupied_tile": 0,
        "head_on_collision_events": 0,
        "corridor_congestion_events": 0,
        "near_target_blocked_by_agent": 0,
        "road_tile_agent_samples": 0,
        "road_tile_multi_agent_events": 0,
        "road_congestion_events": 0,
        "movement_efficiency_ratio": 0.0,
    }


def _default_movement_diagnostic_stats() -> Dict[str, Any]:
    return {
        "global": _empty_movement_metrics(),
        "by_role": {},
        "by_task": {},
        "by_transport_context": {},
        "by_village": {},
        "agent_track": {},
        "tile_hotspots": {},
    }


def _empty_delivery_diagnostic_metrics() -> Dict[str, Any]:
    payload = {k: 0 for k in DELIVERY_DIAGNOSTIC_STAGES}
    payload["delivery_failure_reasons"] = {}
    return payload


def _default_delivery_diagnostic_stats() -> Dict[str, Any]:
    return {
        "global": _empty_delivery_diagnostic_metrics(),
        "by_role": {},
        "by_village": {},
    }


def _empty_housing_construction_metrics() -> Dict[str, Any]:
    payload = {k: 0 for k in HOUSING_CONSTRUCTION_STAGES}
    payload["failure_reasons"] = {}
    payload["worker_participation"] = {k: 0 for k in HOUSING_WORKER_PARTICIPATION_KEYS}
    payload["houses_under_construction_count"] = 0
    payload["houses_completed_count"] = 0
    payload["houses_active_count"] = 0
    payload["average_house_construction_time"] = 0.0
    payload["max_house_construction_time"] = 0
    return payload


def _default_housing_construction_stats() -> Dict[str, Any]:
    return {
        "global": _empty_housing_construction_metrics(),
        "by_village": {},
        "_house_start_tick_by_id": {},
        "_house_completed_ids": set(),
        "_durations_global": [],
        "_durations_by_village": {},
    }


def _empty_housing_siting_metrics() -> Dict[str, Any]:
    payload = {k: 0 for k in HOUSING_SITING_SEARCH_STAGES}
    payload["rejection_reasons"] = {}
    return payload


def _default_housing_siting_stats() -> Dict[str, Any]:
    return {
        "global": _empty_housing_siting_metrics(),
        "by_village": {},
    }


def _empty_housing_path_coherence_metrics() -> Dict[str, Any]:
    return {k: 0 for k in HOUSING_PATH_COHERENCE_KEYS}


def _default_housing_path_coherence_stats() -> Dict[str, Any]:
    return {
        "global": _empty_housing_path_coherence_metrics(),
        "by_village": {},
    }


def _default_builder_self_supply_stats() -> Dict[str, Any]:
    return {
        "attempt_count": 0,
        "success_count": 0,
        "failure_reasons": {},
        "distance_total": 0,
        "distance_samples": 0,
    }


BUILDER_SELF_SUPPLY_GATE_STAGES = (
    "self_supply_attempt_seen",
    "valid_under_construction_site_seen",
    "site_material_need_seen",
    "candidate_storage_found",
    "candidate_storage_has_resource",
    "source_within_site_radius",
    "source_accessible_from_builder",
    "inventory_capacity_available",
    "self_supply_pickup_attempt",
    "self_supply_pickup_success",
)
BUILDER_SELF_SUPPLY_GATE_REASONS = {
    "no_valid_site",
    "site_not_material_needy",
    "no_candidate_storage",
    "candidate_storage_missing_resource",
    "source_out_of_site_radius",
    "source_not_accessible_from_builder",
    "inventory_full",
    "pickup_failed",
    "unknown_failure",
    "self_supply_succeeded",
}


def _empty_builder_self_supply_gate_metrics() -> Dict[str, Any]:
    payload = {k: 0 for k in BUILDER_SELF_SUPPLY_GATE_STAGES}
    payload["failure_reasons"] = {}
    payload["success_count"] = 0
    return payload


def _default_builder_self_supply_gate_stats() -> Dict[str, Any]:
    return {
        "global": _empty_builder_self_supply_gate_metrics(),
        "by_village": {},
    }


def _default_social_gravity_event_stats() -> Dict[str, Any]:
    return {
        "return_to_village_events": 0,
        "stay_near_village_bias_events": 0,
        "home_return_events": 0,
        "by_village": {},
    }


def _default_social_encounter_stats() -> Dict[str, int]:
    return {
        "total_encounter_events": 0,
        "familiar_agent_proximity_events": 0,
        "social_density_bias_applied_count": 0,
        "familiar_communication_bonus_applied": 0,
        "familiar_zone_reinforcement_events": 0,
        "familiar_camp_support_bias_events": 0,
        "familiar_loop_continuity_bonus": 0,
        "familiar_anchor_exploration_events": 0,
        "familiar_zone_score_updates": 0,
        "familiar_zone_score_decay": 0,
        "familiar_zone_saturation_clamps": 0,
        "dense_area_social_bias_reductions": 0,
        "familiar_zone_decay_due_to_low_payoff": 0,
        "overcrowded_familiar_bias_suppressed": 0,
        "density_safe_loop_bonus_reduced_count": 0,
    }


def _default_progression_stats() -> Dict[str, Any]:
    return {
        "proto_community_formed_count": 0,
        "camp_created_count": 0,
        "camp_return_events": 0,
        "camp_rest_events": 0,
        "early_road_suppressed_count": 0,
        "road_priority_deferred_reasons": {},
        "road_built_with_purpose_count": 0,
        "road_build_suppressed_no_purpose": 0,
        "road_build_suppressed_reasons": {},
        "by_village": {},
    }


def _default_situated_construction_stats() -> Dict[str, int]:
    return {
        "construction_on_site_work_ticks": 0,
        "construction_offsite_blocked_ticks": 0,
        "construction_interrupted_survival": 0,
        "construction_interrupted_invalid_target": 0,
    }


def _default_settlement_bottleneck_stats() -> Dict[str, Any]:
    return {
        "village_creation_attempts": 0,
        "village_creation_blocked_count": 0,
        "village_creation_blocked_reasons": {},
        "independent_cluster_count": 0,
        "independent_cluster_support_score_total": 0,
        "independent_cluster_support_score_samples": 0,
        "camp_to_village_transition_attempts": 0,
        "camp_to_village_transition_failures": 0,
        "camp_to_village_transition_failure_reasons": {},
        "local_viable_camp_retained_count": 0,
        "distant_cluster_pull_suppressed_count": 0,
        "distant_cluster_pull_suppressed_reasons": {},
        "camp_absorption_events": 0,
        "camp_absorption_reasons": {},
        "mature_nucleus_detected_count": 0,
        "mature_nucleus_failed_transition_count": 0,
        "mature_nucleus_successful_transition_count": 0,
        "cluster_ecological_productivity_score_total": 0.0,
        "cluster_ecological_productivity_score_samples": 0,
        "cluster_inertia_events": 0,
        "dominant_cluster_saturation_penalty_applied": 0,
        "camp_absorption_delay_events": 0,
        "secondary_cluster_persistence_ticks": 0,
        "exploration_shift_due_to_low_density": 0,
        "secondary_nucleus_structure_count": 0,
        "secondary_nucleus_build_support_events": 0,
        "secondary_nucleus_material_delivery_events": 0,
        "secondary_nucleus_materialization_ticks": 0,
        "secondary_nucleus_absorption_during_build": 0,
        "secondary_nucleus_materialization_success": 0,
    }


def _default_settlement_progression_stats() -> Dict[str, Any]:
    return {
        "population_alive": 0,
        "population_births_count": 0,
        "population_deaths_count": 0,
        "population_deaths_hunger_count": 0,
        "population_deaths_exhaustion_count": 0,
        "population_deaths_other_count": 0,
        "population_deaths_hunger_age_0_199_count": 0,
        "population_deaths_hunger_age_200_599_count": 0,
        "population_deaths_hunger_age_600_plus_count": 0,
        "hunger_deaths_before_first_food_acquisition": 0,
        "population_net_change": 0,
        "agent_average_age": 0.0,
        "agent_median_age_at_death": 0.0,
        "agent_average_lifespan_at_death": 0.0,
        "time_spawn_to_first_food_acquisition_total": 0,
        "time_spawn_to_first_food_acquisition_samples": 0,
        "time_high_hunger_to_eat_total": 0,
        "time_high_hunger_to_eat_samples": 0,
        "high_hunger_to_eat_events_started": 0,
        "agent_hunger_relapse_after_first_food_count": 0,
        "failed_food_seeking_attempts": 0,
        "fallback_food_search_activations": 0,
        "early_life_food_inventory_acquisition_count": 0,
        "early_food_priority_overrides": 0,
        "medium_term_food_priority_overrides": 0,
        "food_acquisition_interval_ticks_total": 0,
        "food_acquisition_interval_ticks_samples": 0,
        "food_acquisition_events_total": 0,
        "food_self_feeding_events": 0,
        "food_self_feeding_units": 0,
        "food_group_feeding_events": 0,
        "food_group_feeding_units": 0,
        "food_reserve_accumulation_events": 0,
        "food_reserve_accumulation_units": 0,
        "food_reserve_draw_events": 0,
        "food_reserve_draw_units": 0,
        "food_security_layer_self_feeding_ticks_total": 0,
        "food_security_layer_group_feeding_ticks_total": 0,
        "food_security_layer_reserve_accumulation_ticks_total": 0,
        "food_security_layer_none_ticks_total": 0,
        "food_security_layer_agents_self_feeding_total": 0,
        "food_security_layer_agents_group_feeding_total": 0,
        "food_security_layer_agents_reserve_accumulation_total": 0,
        "food_security_layer_agents_none_total": 0,
        "food_security_layer_samples": 0,
        "food_security_layer_transition_count": 0,
        "food_security_layer_transition_none_to_self_feeding": 0,
        "food_security_layer_transition_none_to_group_feeding": 0,
        "food_security_layer_transition_none_to_reserve_accumulation": 0,
        "food_security_layer_transition_none_to_none": 0,
        "food_security_layer_transition_self_feeding_to_self_feeding": 0,
        "food_security_layer_transition_self_feeding_to_group_feeding": 0,
        "food_security_layer_transition_self_feeding_to_reserve_accumulation": 0,
        "food_security_layer_transition_self_feeding_to_none": 0,
        "food_security_layer_transition_group_feeding_to_self_feeding": 0,
        "food_security_layer_transition_group_feeding_to_group_feeding": 0,
        "food_security_layer_transition_group_feeding_to_reserve_accumulation": 0,
        "food_security_layer_transition_group_feeding_to_none": 0,
        "food_security_layer_transition_reserve_accumulation_to_self_feeding": 0,
        "food_security_layer_transition_reserve_accumulation_to_group_feeding": 0,
        "food_security_layer_transition_reserve_accumulation_to_reserve_accumulation": 0,
        "food_security_layer_transition_reserve_accumulation_to_none": 0,
        "food_security_reserve_entry_checks": 0,
        "food_security_reserve_entry_condition_met_count": 0,
        "food_security_reserve_entry_activated_count": 0,
        "food_security_reserve_entry_blocked_no_surplus": 0,
        "food_security_reserve_entry_blocked_no_qualifying_task": 0,
        "food_security_reserve_entry_blocked_unstable_context": 0,
        "food_security_reserve_entry_blocked_group_feeding_dominance": 0,
        "food_security_reserve_prepolicy_candidate_count": 0,
        "food_security_reserve_postpolicy_candidate_count": 0,
        "food_security_reserve_final_activation_count": 0,
        "food_security_reserve_selection_considered_count": 0,
        "food_security_reserve_selection_chosen_count": 0,
        "food_security_reserve_selection_rejected_count": 0,
        "food_security_reserve_selection_rejected_by_group_feeding_count": 0,
        "food_security_reserve_selection_rejected_by_unstable_context_count": 0,
        "food_security_reserve_selection_rejected_by_no_surplus_count": 0,
        "food_security_reserve_selection_rejected_by_other_count": 0,
        "food_security_reserve_final_selection_lost_to_self_feeding_count": 0,
        "food_security_reserve_final_selection_lost_to_group_feeding_count": 0,
        "food_security_reserve_final_selection_lost_to_unstable_context_count": 0,
        "food_security_reserve_final_selection_lost_to_no_surplus_count": 0,
        "food_security_reserve_final_selection_lost_to_other_count": 0,
        "food_security_reserve_final_selection_winner_self_feeding_count": 0,
        "food_security_reserve_final_selection_winner_group_feeding_count": 0,
        "food_security_reserve_final_selection_winner_other_count": 0,
        "food_security_reserve_loss_stage_policy_ranking_count": 0,
        "food_security_reserve_loss_stage_final_gate_count": 0,
        "food_security_reserve_loss_stage_final_override_count": 0,
        "food_security_reserve_final_decision_observed_count": 0,
        "food_security_reserve_final_decision_candidate_count": 0,
        "food_security_reserve_final_decision_candidate_survived_prepolicy_count": 0,
        "food_security_reserve_final_decision_candidate_survived_postpolicy_count": 0,
        "food_security_reserve_final_decision_candidate_lost_count": 0,
        "food_security_reserve_final_decision_candidate_chosen_count": 0,
        "food_security_reserve_final_selected_task_food_logistics_count": 0,
        "food_security_reserve_final_selected_task_village_logistics_count": 0,
        "food_security_reserve_final_selected_task_camp_supply_food_count": 0,
        "food_security_reserve_final_selected_task_other_count": 0,
        "food_security_reserve_final_selected_layer_reserve_accumulation_count": 0,
        "food_security_reserve_final_selected_layer_group_feeding_count": 0,
        "food_security_reserve_final_selected_layer_self_feeding_count": 0,
        "food_security_reserve_final_selected_layer_none_count": 0,
        "food_security_reserve_final_winner_subsystem_policy_ranking_count": 0,
        "food_security_reserve_final_winner_subsystem_role_task_update_count": 0,
        "food_security_reserve_final_winner_subsystem_final_gate_count": 0,
        "food_security_reserve_final_winner_subsystem_final_override_count": 0,
        "food_security_reserve_final_winner_subsystem_task_layer_routing_count": 0,
        "food_security_reserve_final_winner_subsystem_contextual_override_count": 0,
        "food_security_reserve_final_winner_subsystem_unknown_count": 0,
        "food_security_reserve_final_override_reason_group_feeding_pressure_override_count": 0,
        "food_security_reserve_final_override_reason_village_logistics_group_routing_count": 0,
        "food_security_reserve_final_override_reason_camp_supply_group_routing_count": 0,
        "food_security_reserve_final_override_reason_unstable_context_count": 0,
        "food_security_reserve_final_override_reason_no_surplus_count": 0,
        "food_security_reserve_final_override_reason_other_count": 0,
        "reserve_final_tiebreak_invoked_count": 0,
        "reserve_final_tiebreak_won_count": 0,
        "reserve_final_tiebreak_lost_count": 0,
        "reserve_final_tiebreak_blocked_by_pressure_count": 0,
        "reserve_final_tiebreak_blocked_by_unstable_context_count": 0,
        "reserve_final_tiebreak_blocked_by_no_surplus_count": 0,
        "reserve_total_food_observed_sum": 0,
        "reserve_total_food_observed_samples": 0,
        "reserve_total_food_observed_max": 0,
        "reserve_fill_events": 0,
        "reserve_depletion_events": 0,
        "ticks_reserve_above_threshold": 0,
        "ticks_reserve_empty": 0,
        "reserve_recovery_cycles": 0,
        "reserve_partial_recovery_cycles": 0,
        "reserve_full_recovery_cycles": 0,
        "reserve_failed_recovery_attempts": 0,
        "reserve_recovery_tracking_active": 0,
        "reserve_recovery_refill_started": 0,
        "reserve_recovery_sustain_ticks": 0,
        "reserve_continuity_current_window": 0,
        "reserve_continuity_longest_window": 0,
        "reserve_shortage_active_prev": 0,
        "reserve_refill_attempts": 0,
        "reserve_refill_success": 0,
        "reserve_refill_food_added_total": 0,
        "reserve_refill_interval_ticks_total": 0,
        "reserve_refill_interval_ticks_samples": 0,
        "reserve_last_refill_tick": -1,
        "reserve_refill_blocked_by_pressure": 0,
        "reserve_refill_blocked_by_no_surplus": 0,
        "reserve_refill_blocked_by_unstable_context": 0,
        "reserve_refill_blocked_by_other": 0,
        "reserve_draw_interval_ticks_total": 0,
        "reserve_draw_interval_ticks_samples": 0,
        "reserve_last_draw_tick": -1,
        "settlement_food_shortage_events": 0,
        "local_food_handoff_events": 0,
        "local_food_handoff_units": 0,
        "handoff_allowed_by_context_count": 0,
        "handoff_blocked_by_group_priority_count": 0,
        "handoff_blocked_by_cooldown_count": 0,
        "handoff_blocked_by_same_unit_recently_count": 0,
        "handoff_blocked_by_receiver_viability": 0,
        "handoff_blocked_by_camp_fragility": 0,
        "handoff_blocked_by_recent_rescue": 0,
        "handoff_blocked_by_camp_fragility_when_receiver_critical_count": 0,
        "handoff_blocked_by_camp_fragility_when_donor_safe_count": 0,
        "handoff_blocked_by_camp_fragility_with_local_surplus_count": 0,
        "handoff_blocked_by_camp_fragility_context_pressure_count": 0,
        "handoff_blocked_by_camp_fragility_context_nonpressure_count": 0,
        "handoff_blocked_by_camp_fragility_donor_food_sum": 0,
        "handoff_blocked_by_camp_fragility_donor_food_samples": 0,
        "handoff_blocked_by_camp_fragility_receiver_hunger_sum": 0.0,
        "handoff_blocked_by_camp_fragility_receiver_hunger_samples": 0,
        "handoff_blocked_by_camp_fragility_camp_food_sum": 0,
        "handoff_blocked_by_camp_fragility_camp_food_samples": 0,
        "local_food_handoff_prevented_by_low_surplus": 0,
        "local_food_handoff_prevented_by_distance": 0,
        "local_food_handoff_prevented_by_donor_risk": 0,
        "hunger_relief_after_local_handoff_total": 0.0,
        "hunger_relief_after_local_handoff_samples": 0,
        "hunger_deaths_with_reserve_available": 0,
        "hunger_deaths_without_reserve": 0,
        "reserve_draw_hunger_sum": 0.0,
        "reserve_draw_hunger_samples": 0,
        "reserve_draw_events_during_food_stress": 0,
        "reserve_draw_events_during_normal_conditions": 0,
        "reserve_usage_after_failed_foraging_trip": 0,
        "food_acquisition_distance_total": 0,
        "food_acquisition_distance_samples": 0,
        "food_consumption_interval_ticks_total": 0,
        "food_consumption_interval_ticks_samples": 0,
        "food_source_contention_events": 0,
        "food_source_depletion_events": 0,
        "food_respawned_total_observed": 0,
        "foraging_trip_started_count": 0,
        "foraging_trip_completed_count": 0,
        "foraging_trip_zero_harvest_count": 0,
        "foraging_trip_terminated_by_hunger_count": 0,
        "foraging_trip_food_gained_total": 0,
        "foraging_trip_movement_ticks_total": 0,
        "foraging_trip_harvest_actions_total": 0,
        "foraging_trip_retarget_count_total": 0,
        "foraging_source_visit_count": 0,
        "foraging_target_lock_duration_total": 0,
        "foraging_target_lock_duration_samples": 0,
        "foraging_commit_before_retarget_ticks_total": 0,
        "foraging_commit_before_retarget_ticks_samples": 0,
        "foraging_trip_move_before_first_harvest_total": 0,
        "foraging_trip_move_before_first_harvest_samples": 0,
        "foraging_trip_wasted_arrival_count": 0,
        "foraging_arrival_depleted_source_count": 0,
        "foraging_arrival_overcontested_count": 0,
        "foraging_trip_efficiency_ratio_sum": 0.0,
        "foraging_trip_efficiency_ratio_samples": 0,
        "foraging_retarget_events": 0,
        "foraging_retarget_events_pressure_low": 0,
        "foraging_retarget_events_pressure_medium": 0,
        "foraging_retarget_events_pressure_high": 0,
        "foraging_trip_aborted_before_first_harvest_count": 0,
        "foraging_trip_aborted_after_first_harvest_count": 0,
        "foraging_trip_successful_count": 0,
        "foraging_trip_post_first_harvest_units_total": 0,
        "foraging_trip_post_first_harvest_units_samples": 0,
        "foraging_trip_single_harvest_action_count": 0,
        "foraging_trip_patch_dwell_after_first_harvest_ticks_total": 0,
        "foraging_trip_patch_dwell_after_first_harvest_ticks_samples": 0,
        "foraging_trip_ended_soon_after_first_harvest_count": 0,
        "foraging_trip_max_consecutive_harvest_actions_total": 0,
        "foraging_trip_max_consecutive_harvest_actions_samples": 0,
        "foraging_trip_end_reason_task_switched": 0,
        "foraging_trip_end_reason_hunger_death": 0,
        "foraging_trip_end_reason_other": 0,
        "foraging_trip_end_after_first_harvest_completed": 0,
        "foraging_trip_end_after_first_harvest_task_switched": 0,
        "foraging_trip_end_after_first_harvest_hunger_death": 0,
        "foraging_trip_end_after_first_harvest_other": 0,
        "post_first_harvest_task_switch_attempt_count": 0,
        "post_first_harvest_task_switch_committed_count": 0,
        "post_first_harvest_task_switch_blocked_count": 0,
        "post_first_harvest_task_switch_attempt_source_survival_override": 0,
        "post_first_harvest_task_switch_attempt_source_role_task_update": 0,
        "post_first_harvest_task_switch_attempt_source_brain_retarget": 0,
        "post_first_harvest_task_switch_attempt_source_commitment_clear": 0,
        "post_first_harvest_task_switch_attempt_source_target_invalidated": 0,
        "post_first_harvest_task_switch_attempt_source_inventory_logic": 0,
        "post_first_harvest_task_switch_attempt_source_wander_fallback": 0,
        "post_first_harvest_task_switch_attempt_source_unknown": 0,
        "post_first_harvest_task_switch_committed_source_survival_override": 0,
        "post_first_harvest_task_switch_committed_source_role_task_update": 0,
        "post_first_harvest_task_switch_committed_source_brain_retarget": 0,
        "post_first_harvest_task_switch_committed_source_commitment_clear": 0,
        "post_first_harvest_task_switch_committed_source_target_invalidated": 0,
        "post_first_harvest_task_switch_committed_source_inventory_logic": 0,
        "post_first_harvest_task_switch_committed_source_wander_fallback": 0,
        "post_first_harvest_task_switch_committed_source_unknown": 0,
        "post_first_harvest_task_switch_blocked_source_survival_override": 0,
        "post_first_harvest_task_switch_blocked_source_role_task_update": 0,
        "post_first_harvest_task_switch_blocked_source_brain_retarget": 0,
        "post_first_harvest_task_switch_blocked_source_commitment_clear": 0,
        "post_first_harvest_task_switch_blocked_source_target_invalidated": 0,
        "post_first_harvest_task_switch_blocked_source_inventory_logic": 0,
        "post_first_harvest_task_switch_blocked_source_wander_fallback": 0,
        "post_first_harvest_task_switch_blocked_source_unknown": 0,
        "foraging_trip_success_pressure_low_count": 0,
        "foraging_trip_success_pressure_medium_count": 0,
        "foraging_trip_success_pressure_high_count": 0,
        "foraging_trip_total_pressure_low_count": 0,
        "foraging_trip_total_pressure_medium_count": 0,
        "foraging_trip_total_pressure_high_count": 0,
        "foraging_trip_efficiency_pressure_low_sum": 0.0,
        "foraging_trip_efficiency_pressure_low_samples": 0,
        "foraging_trip_efficiency_pressure_medium_sum": 0.0,
        "foraging_trip_efficiency_pressure_medium_samples": 0,
        "foraging_trip_efficiency_pressure_high_sum": 0.0,
        "foraging_trip_efficiency_pressure_high_samples": 0,
        "foraging_trip_efficiency_contention_low_sum": 0.0,
        "foraging_trip_efficiency_contention_low_samples": 0,
        "foraging_trip_efficiency_contention_medium_sum": 0.0,
        "foraging_trip_efficiency_contention_medium_samples": 0,
        "foraging_trip_efficiency_contention_high_sum": 0.0,
        "foraging_trip_efficiency_contention_high_samples": 0,
        "foraging_micro_retarget_events": 0,
        "foraging_commitment_hold_overrides": 0,
        "foraging_bonus_yield_units_total": 0,
        "food_seeking_ticks_total": 0,
        "agent_ticks_total": 0,
        "agent_food_inventory_total": 0,
        "agent_food_inventory_samples": 0,
        "food_harvest_ticks_total": 0,
        "food_move_ticks_total": 0,
        "local_food_basin_accessible_total": 0,
        "local_food_basin_accessible_samples": 0,
        "local_food_basin_pressure_ratio_total": 0.0,
        "local_food_basin_pressure_ratio_samples": 0,
        "local_food_basin_competing_agents_total": 0,
        "local_food_basin_competing_agents_samples": 0,
        "local_food_basin_nearest_food_distance_total": 0,
        "local_food_basin_nearest_food_distance_samples": 0,
        "local_food_basin_severe_pressure_ticks": 0,
        "local_food_basin_collapse_events": 0,
        "proto_settlement_abandoned_due_to_food_pressure_count": 0,
        "food_scarcity_adaptive_retarget_events": 0,
        "deaths_before_first_house_completed": 0,
        "deaths_before_settlement_stability_threshold": 0,
        "population_collapse_events": 0,
        "first_house_completion_tick": -1,
        "first_storage_completion_tick": -1,
        "first_road_completion_tick": -1,
        "first_village_formalization_tick": -1,
        "settlement_proto_count": 0,
        "settlement_stable_village_count": 0,
        "settlement_abandoned_count": 0,
        "storage_built_before_house_count": 0,
        "road_built_before_house_threshold_count": 0,
        "startup_survival_relief_ticks": 0,
        "_dead_agent_ages_sum": 0,
        "_dead_agent_ages_count": 0,
        "_dead_agent_ages_sorted": [],
        "_population_peak_alive": 0,
        "_population_collapse_active": False,
        "farm_sites_created": 0,
        "farm_work_events": 0,
        "farm_abandoned": 0,
        "farm_yield_events": 0,
        "farm_yield_units_total": 0,
        "farm_productivity_score_avg": 0.0,
        "agents_farming_count": 0,
        "farm_candidate_detected_count": 0,
        "farm_candidate_bootstrap_trigger_count": 0,
        "farm_candidate_rejected_count": 0,
        "early_farm_loop_persistence_ticks": 0,
        "early_farm_loop_abandonment_count": 0,
        "first_harvest_after_farm_creation_count": 0,
        "house_cluster_count": 0,
        "avg_houses_per_cluster": 0.0,
        "house_cluster_growth_events": 0,
        "storage_built_after_cluster_count": 0,
        "storage_built_without_cluster_count": 0,
        "storage_emergence_attempts": 0,
        "storage_emergence_successes": 0,
        "storage_deferred_due_to_low_house_cluster": 0,
        "storage_deferred_due_to_low_throughput": 0,
        "storage_deferred_due_to_low_buffer_pressure": 0,
        "storage_deferred_due_to_low_surplus": 0,
        "storage_built_in_mature_cluster_count": 0,
        "storage_supporting_active_house_cluster_count": 0,
        "storage_relief_of_domestic_pressure_events": 0,
        "storage_relief_of_camp_pressure_events": 0,
        "active_storage_construction_sites": 0,
        "storage_builder_commitment_retained_ticks": 0,
        "storage_material_delivery_events": 0,
        "storage_construction_progress_ticks": 0,
        "storage_construction_interrupted_survival": 0,
        "storage_construction_interrupted_invalid": 0,
        "storage_construction_abandoned_count": 0,
        "storage_construction_completed_count": 0,
        "construction_sites_created": 0,
        "construction_sites_created_house": 0,
        "construction_sites_created_storage": 0,
        "active_construction_sites": 0,
        "partially_built_sites_count": 0,
        "construction_material_delivery_events": 0,
        "construction_material_delivery_to_active_site": 0,
        "construction_material_delivery_drift_events": 0,
        "construction_material_delivery_wood_units": 0,
        "construction_material_delivery_stone_units": 0,
        "construction_material_delivery_food_units": 0,
        "storage_deposit_food_units": 0,
        "storage_deposit_wood_units": 0,
        "storage_deposit_stone_units": 0,
        "construction_site_nearest_wood_distance_total": 0,
        "construction_site_nearest_wood_distance_samples": 0,
        "construction_site_nearest_stone_distance_total": 0,
        "construction_site_nearest_stone_distance_samples": 0,
        "construction_site_viable_wood_sources_within_radius_total": 0,
        "construction_site_viable_wood_sources_within_radius_samples": 0,
        "construction_site_viable_stone_sources_within_radius_total": 0,
        "construction_site_viable_stone_sources_within_radius_samples": 0,
        "construction_site_zero_wood_sources_within_radius_ticks": 0,
        "construction_site_zero_stone_sources_within_radius_ticks": 0,
        "construction_site_local_wood_source_contention_total": 0.0,
        "construction_site_local_wood_source_contention_samples": 0,
        "construction_site_local_stone_source_contention_total": 0.0,
        "construction_site_local_stone_source_contention_samples": 0,
        "construction_site_ticks_since_last_delivery_total": 0,
        "construction_site_ticks_since_last_delivery_samples": 0,
        "construction_site_waiting_with_positive_wood_stock_ticks": 0,
        "construction_site_waiting_with_positive_stone_stock_ticks": 0,
        "construction_site_first_demand_to_first_delivery_total": 0,
        "construction_site_first_demand_to_first_delivery_samples": 0,
        "construction_site_material_inflow_rate_total": 0.0,
        "construction_site_material_inflow_rate_samples": 0,
        "construction_site_delivered_wood_units_total_live": 0,
        "construction_site_delivered_stone_units_total_live": 0,
        "construction_site_delivered_food_units_total_live": 0,
        "active_builders_count": 0,
        "active_haulers_count": 0,
        "active_builders_nearest_wood_distance_total": 0,
        "active_builders_nearest_wood_distance_samples": 0,
        "active_builders_nearest_stone_distance_total": 0,
        "active_builders_nearest_stone_distance_samples": 0,
        "active_haulers_nearest_wood_distance_total": 0,
        "active_haulers_nearest_wood_distance_samples": 0,
        "active_haulers_nearest_stone_distance_total": 0,
        "active_haulers_nearest_stone_distance_samples": 0,
        "construction_delivery_attempts": 0,
        "construction_delivery_successes": 0,
        "construction_delivery_failures": 0,
        "construction_delivery_to_site_events": 0,
        "construction_delivery_to_wrong_target_or_drift": 0,
        "construction_delivery_source_binding_selected_count": 0,
        "construction_delivery_source_binding_persisted_count": 0,
        "construction_delivery_source_binding_refreshed_count": 0,
        "construction_delivery_source_binding_missing_count": 0,
        "construction_delivery_source_binding_unavailable_count": 0,
        "construction_delivery_source_binding_lost_missing_source_count": 0,
        "construction_delivery_source_binding_lost_ineligible_source_count": 0,
        "construction_delivery_source_binding_lost_not_refreshed_count": 0,
        "construction_delivery_prepickup_checks_count": 0,
        "construction_delivery_prepickup_site_exists_count": 0,
        "construction_delivery_prepickup_site_missing_count": 0,
        "construction_delivery_prepickup_site_under_construction_count": 0,
        "construction_delivery_prepickup_site_not_under_construction_count": 0,
        "construction_delivery_prepickup_site_reachable_count": 0,
        "construction_delivery_prepickup_site_unreachable_count": 0,
        "construction_delivery_prepickup_site_demand_matches_material_count": 0,
        "construction_delivery_prepickup_site_demand_mismatch_material_count": 0,
        "construction_delivery_source_persistence_window_invoked_count": 0,
        "construction_delivery_source_persistence_window_completed_count": 0,
        "construction_delivery_source_persistence_window_broken_by_source_invalidity_count": 0,
        "construction_delivery_source_persistence_window_broken_by_demand_mismatch_count": 0,
        "construction_delivery_reservation_alignment_pass_count": 0,
        "construction_delivery_reservation_alignment_fail_count": 0,
        "construction_delivery_reservation_alignment_fail_material_wood_count": 0,
        "construction_delivery_reservation_alignment_fail_material_stone_count": 0,
        "construction_delivery_reservation_alignment_fail_material_food_count": 0,
        "construction_delivery_reservation_alignment_fail_reason_site_missing_count": 0,
        "construction_delivery_reservation_alignment_fail_reason_site_not_under_construction_count": 0,
        "construction_delivery_reservation_alignment_fail_reason_reservation_invalid_count": 0,
        "construction_delivery_reservation_alignment_fail_reason_demand_mismatch_count": 0,
        "construction_delivery_reservation_alignment_fail_reason_source_ineligible_count": 0,
        "construction_delivery_reservation_alignment_fail_reason_source_empty_count": 0,
        "delivery_commitment_hold_invoked_count": 0,
        "delivery_commitment_hold_completed_count": 0,
        "delivery_commitment_hold_broken_by_survival_count": 0,
        "delivery_commitment_hold_broken_by_invalid_site_count": 0,
        "delivery_commitment_hold_broken_by_invalid_source_count": 0,
        "construction_delivery_invalid_site_missing_site_count": 0,
        "construction_delivery_invalid_site_not_under_construction_count": 0,
        "construction_delivery_invalid_site_village_mismatch_count": 0,
        "construction_delivery_invalid_site_construction_completed_count": 0,
        "construction_delivery_invalid_site_no_path_to_site_count": 0,
        "construction_delivery_invalid_site_demand_mismatch_count": 0,
        "construction_delivery_invalid_site_other_count": 0,
        "construction_delivery_invalid_source_no_source_available_count": 0,
        "construction_delivery_invalid_source_source_depleted_count": 0,
        "construction_delivery_invalid_source_reservation_invalidated_count": 0,
        "construction_delivery_invalid_source_source_reassigned_count": 0,
        "construction_delivery_invalid_source_linkage_mismatch_count": 0,
        "construction_delivery_invalid_source_no_path_to_source_count": 0,
        "construction_delivery_invalid_source_other_count": 0,
        "construction_delivery_invalid_site_before_pickup_count": 0,
        "construction_delivery_invalid_site_after_pickup_count": 0,
        "construction_delivery_invalid_source_before_pickup_count": 0,
        "construction_delivery_invalid_source_after_pickup_count": 0,
        "construction_delivery_ticks_reservation_to_invalid_site_total": 0,
        "construction_delivery_ticks_reservation_to_invalid_site_samples": 0,
        "construction_delivery_ticks_reservation_to_invalid_source_total": 0,
        "construction_delivery_ticks_reservation_to_invalid_source_samples": 0,
        "construction_delivery_ticks_pickup_to_invalid_site_total": 0,
        "construction_delivery_ticks_pickup_to_invalid_site_samples": 0,
        "construction_delivery_ticks_pickup_to_invalid_source_total": 0,
        "construction_delivery_ticks_pickup_to_invalid_source_samples": 0,
        "construction_delivery_invalid_site_material_wood_count": 0,
        "construction_delivery_invalid_site_material_stone_count": 0,
        "construction_delivery_invalid_site_material_food_count": 0,
        "construction_delivery_invalid_source_material_wood_count": 0,
        "construction_delivery_invalid_source_material_stone_count": 0,
        "construction_delivery_invalid_source_material_food_count": 0,
        "construction_delivery_invalid_site_committed_site_mismatch_count": 0,
        "construction_delivery_invalid_source_committed_source_missing_count": 0,
        "construction_delivery_distance_to_site_sum": 0,
        "construction_delivery_distance_to_site_samples": 0,
        "construction_delivery_distance_to_source_sum": 0,
        "construction_delivery_distance_to_source_samples": 0,
        "storage_delivery_failures": 0,
        "house_delivery_failures": 0,
        "storage_delivery_successes": 0,
        "house_delivery_successes": 0,
        "construction_progress_ticks": 0,
        "construction_progress_stalled_ticks": 0,
        "construction_completion_events": 0,
        "construction_abandonment_events": 0,
        "construction_site_waiting_for_material_ticks": 0,
        "construction_site_waiting_for_builder_ticks": 0,
        "construction_site_waiting_total_ticks": 0,
        "construction_site_progress_active_ticks": 0,
        "construction_site_starved_cycles": 0,
        "storage_waiting_for_material_ticks": 0,
        "house_waiting_for_material_ticks": 0,
        "storage_waiting_for_builder_ticks": 0,
        "house_waiting_for_builder_ticks": 0,
        "construction_site_lifetime_ticks_total": 0,
        "construction_site_lifetime_samples": 0,
        "construction_site_progress_before_abandon_total": 0,
        "construction_site_progress_before_abandon_samples": 0,
        "construction_site_material_units_delivered_total": 0,
        "construction_site_material_units_missing_total": 0,
        "construction_site_material_units_missing_samples": 0,
        "construction_site_material_units_required_total": 0,
        "construction_site_material_units_delivered_total_live": 0,
        "construction_site_material_units_remaining": 0,
        "construction_site_required_work_ticks_total": 0,
        "construction_site_completed_work_ticks_total_live": 0,
        "construction_site_remaining_work_ticks": 0,
        "construction_build_state_planned_count": 0,
        "construction_build_state_supplying_count": 0,
        "construction_build_state_buildable_count": 0,
        "construction_build_state_in_progress_count": 0,
        "construction_build_state_paused_count": 0,
        "construction_build_state_completed_count": 0,
        "construction_near_complete_sites_count": 0,
        "builder_assigned_site_count": 0,
        "builder_site_arrival_count": 0,
        "builder_left_site_count": 0,
        "builder_left_site_before_completion_count": 0,
        "builder_waiting_on_site_ticks_total": 0,
        "builder_on_site_ticks_total": 0,
        "builder_work_tick_applied_count": 0,
        "builder_survival_override_during_construction_count": 0,
        "builder_redirected_to_storage_during_construction_count": 0,
        "builder_commitment_created_count": 0,
        "builder_commitment_pause_count": 0,
        "builder_commitment_resume_count": 0,
        "builder_commitment_completed_count": 0,
        "builder_commitment_abandoned_count": 0,
        "builder_returned_to_same_site_count": 0,
        "builder_commitment_duration_total": 0,
        "builder_commitment_duration_samples": 0,
        "builder_commitment_resume_delay_total": 0,
        "builder_commitment_resume_delay_samples": 0,
        "construction_site_buildable_ticks_total": 0,
        "construction_site_idle_buildable_ticks_total": 0,
        "construction_site_buildable_but_idle_ticks_total": 0,
        "construction_site_waiting_materials_ticks_total": 0,
        "construction_site_in_progress_ticks_total": 0,
        "construction_site_distinct_builders_total": 0,
        "construction_site_distinct_builders_samples": 0,
        "construction_site_work_ticks_per_builder_total": 0.0,
        "construction_site_work_ticks_per_builder_samples": 0,
        "construction_site_delivery_to_work_gap_total": 0,
        "construction_site_delivery_to_work_gap_samples": 0,
        "construction_site_active_age_ticks_total": 0,
        "construction_site_active_age_ticks_samples": 0,
        "construction_site_first_builder_arrival_delay_total": 0,
        "construction_site_first_builder_arrival_delay_samples": 0,
        "construction_site_material_ready_to_first_work_delay_total": 0,
        "construction_site_material_ready_to_first_work_delay_samples": 0,
        "construction_site_completion_time_total": 0,
        "construction_site_completion_time_samples": 0,
        "construction_time_first_delivery_to_completion_total": 0,
        "construction_time_first_delivery_to_completion_samples": 0,
        "construction_time_first_progress_to_completion_total": 0,
        "construction_time_first_progress_to_completion_samples": 0,
        "construction_completed_after_first_delivery_count": 0,
        "construction_completed_after_started_progress_count": 0,
        "house_completion_time_total": 0,
        "house_completion_time_samples": 0,
        "storage_completion_time_total": 0,
        "storage_completion_time_samples": 0,
        "buffer_saturation_events": 0,
        "surplus_triggered_storage_attempts": 0,
        "surplus_storage_construction_completed": 0,
        "surplus_storage_abandoned": 0,
        "_surplus_food_rate_sum_scaled": 0,
        "_surplus_resource_rate_sum_scaled": 0,
        "_surplus_rate_samples": 0,
        "secondary_nucleus_with_house_count": 0,
        "secondary_nucleus_house_growth_events": 0,
        "repeated_successful_loop_count": 0,
        "routine_persistence_ticks": 0,
        "routine_abandonment_after_failure": 0,
        "routine_abandonment_after_success": 0,
        "cultural_practices_created": 0,
        "cultural_practices_reinforced": 0,
        "cultural_practices_decayed": 0,
        "active_cultural_practices": 0,
        "agents_using_cultural_memory_bias": 0,
        "productive_food_patch_practices": 0,
        "proto_farm_practices": 0,
        "construction_cluster_practices": 0,
        "_prev_cluster_sizes": [],
        "_seen_storage_ids": set(),
        "_prev_secondary_nucleus_with_house_count": 0,
    }


def _default_camp_food_stats() -> Dict[str, int]:
    return {
        "camp_food_deposits": 0,
        "camp_food_consumptions": 0,
        "camp_food_decay": 0,
        "camp_food_deposit_attempts": 0,
        "camp_food_deposit_blocked_low_hunger": 0,
        "camp_food_deposit_blocked_self_reserve": 0,
        "camp_food_consume_attempts": 0,
        "camp_food_consume_misses": 0,
        "food_consumed_from_inventory": 0,
        "food_consumed_from_camp": 0,
        "food_consumed_from_domestic": 0,
        "food_consumed_from_storage": 0,
        "food_consumed_from_wild_direct": 0,
        "domestic_food_stored_total": 0,
        "domestic_food_consumed_total": 0,
        "domestic_storage_full_events": 0,
        "house_food_distribution_events": 0,
        "camp_food_pressure_ticks": 0,
        "local_food_pressure_events": 0,
        "pressure_backed_loop_selected_count": 0,
        "pressure_backed_food_deliveries": 0,
        "unmet_food_pressure_count": 0,
        "loop_completed_count": 0,
        "loop_abandoned_count": 0,
        "loop_abandoned_due_to_no_source": 0,
        "loop_abandoned_due_to_saturated_cache": 0,
        "loop_abandoned_due_to_no_drop_target": 0,
        "near_complete_loop_opportunities": 0,
        "near_complete_loop_completed": 0,
        "near_complete_loop_abandoned": 0,
        "completion_bias_applied_count": 0,
        "delivery_commitment_retained_ticks": 0,
        "loop_retarget_success_count": 0,
        "loop_retarget_failure_count": 0,
    }


def _default_communication_stats() -> Dict[str, int]:
    return {
        "communication_events": 0,
        "food_knowledge_shared_count": 0,
        "camp_knowledge_shared_count": 0,
        "shared_food_knowledge_used_count": 0,
        "shared_camp_knowledge_used_count": 0,
        "stale_knowledge_expired_count": 0,
        "invalidated_shared_knowledge_count": 0,
        "social_knowledge_accept_count": 0,
        "social_knowledge_reject_count": 0,
        "social_knowledge_reject_stale": 0,
        "social_knowledge_reject_too_far": 0,
        "social_knowledge_reject_lower_than_direct": 0,
        "social_knowledge_reject_survival_priority": 0,
        "direct_overrides_social_count": 0,
        "social_food_knowledge_adopted_count": 0,
        "social_camp_knowledge_adopted_count": 0,
        "repeated_duplicate_share_suppressed_count": 0,
        "camp_knowledge_share_suppressed_count": 0,
        "confirmed_memory_reinforcements": 0,
        "direct_memory_invalidations": 0,
    }


def _default_behavior_map_stats() -> Dict[str, Any]:
    return {
        "activity_counts": {},
        "activity_by_region": {},
        "activity_by_type_region": {},
        "activity_context_counts": {},
        "task_transition_counts": {},
        "task_transition_by_region": {},
        "secondary_nucleus_birth_count": 0,
        "secondary_nucleus_persistence_ticks": 0,
        "secondary_nucleus_absorption_count": 0,
        "secondary_nucleus_decay_count": 0,
        "secondary_nucleus_village_attempts": 0,
        "secondary_nucleus_village_successes": 0,
    }


def _empty_proto_funnel_metrics() -> Dict[str, Any]:
    payload = {k: 0 for k in PROTO_COMMUNITY_FUNNEL_STAGES}
    payload["failure_reasons"] = {}
    return payload


def _default_proto_funnel_stats() -> Dict[str, Any]:
    return {
        "global": _empty_proto_funnel_metrics(),
        "by_region": {},
    }


def _empty_camp_lifecycle_metrics() -> Dict[str, Any]:
    payload = {k: 0 for k in CAMP_LIFECYCLE_STAGES}
    payload["deactivation_reasons"] = {}
    payload["retention_reasons"] = {}
    payload["deactivation_with_food_cache_count"] = 0
    payload["deactivation_with_recent_use_count"] = 0
    payload["deactivation_with_anchor_support_count"] = 0
    payload["deactivation_with_nearby_agents_count"] = 0
    return payload


def _default_camp_lifecycle_stats() -> Dict[str, Any]:
    return {
        "global": _empty_camp_lifecycle_metrics(),
        "by_region": {},
    }


def _empty_camp_targeting_metrics() -> Dict[str, Any]:
    payload = {k: 0 for k in CAMP_TARGETING_STAGES}
    payload["camp_not_chosen_reasons"] = {}
    return payload


def _default_camp_targeting_stats() -> Dict[str, Any]:
    return {
        "global": _empty_camp_targeting_metrics(),
        "by_region": {},
    }


def _default_residence_stabilization_stats() -> Dict[str, Any]:
    return {
        "resident_conversion_attempt_count": 0,
        "resident_conversion_count": 0,
        "resident_persistence_count": 0,
        "resident_release_count": 0,
        "resident_release_reasons": {},
        "by_village": {},
    }


RESIDENT_CONVERSION_GATE_STAGES = (
    "conversion_context_seen",
    "strong_affiliation_seen",
    "candidate_house_search_started",
    "candidate_house_found",
    "candidate_house_active",
    "candidate_house_empty",
    "within_claim_radius",
    "conversion_eligibility_passed",
    "resident_conversion_granted",
)
RESIDENT_CONVERSION_GATE_FAILURE_REASONS = {
    "affiliation_not_strong_enough",
    "no_candidate_house",
    "house_inactive",
    "house_not_empty",
    "outside_claim_radius",
    "village_mismatch",
    "survival_override",
    "house_already_reserved",
    "eligibility_failed_other_guard",
    "conversion_succeeded",
}


def _empty_resident_conversion_gate_metrics() -> Dict[str, Any]:
    payload = {k: 0 for k in RESIDENT_CONVERSION_GATE_STAGES}
    payload["failure_reasons"] = {}
    payload["conversion_success_count"] = 0
    return payload


def _default_resident_conversion_gate_stats() -> Dict[str, Any]:
    return {
        "global": _empty_resident_conversion_gate_metrics(),
        "by_village": {},
    }


def _empty_recovery_diagnostic_metrics() -> Dict[str, Any]:
    payload = {k: 0 for k in RECOVERY_FUNNEL_STAGES}
    payload["failure_reasons"] = {}
    payload["agents_with_valid_home"] = 0
    payload["high_pressure_with_valid_home"] = 0
    payload["home_recovery_possible_not_chosen"] = 0
    return payload


def _default_recovery_diagnostic_stats() -> Dict[str, Any]:
    return {
        "global": _empty_recovery_diagnostic_metrics(),
        "by_role": {},
        "by_village": {},
    }


def _default_workforce_realization_stats() -> Dict[str, Any]:
    return {
        "productive_actions_by_role": {role: 0 for role in WORKFORCE_REALIZATION_ROLES},
        "productive_actions_by_role_actions": {role: {} for role in WORKFORCE_REALIZATION_ROLES},
        "productive_actions_by_role_by_village": {},
        "productive_actions_by_role_actions_by_village": {},
        "block_reasons_by_role": {role: {} for role in WORKFORCE_REALIZATION_ROLES},
        "block_reasons_by_role_by_village": {},
        "productive_actions_by_affiliation": {
            role: _empty_workforce_affiliation_counts()
            for role in WORKFORCE_REALIZATION_ROLES
        },
        "productive_actions_by_affiliation_by_village": {},
        "assignment_gap_stage_counts_by_role": {
            role: {stage: 0 for stage in ASSIGNMENT_GAP_STAGES}
            for role in WORKFORCE_REALIZATION_ROLES
        },
        "assignment_gap_stage_counts_by_role_by_village": {},
        "assignment_gap_stage_counts_by_affiliation": {
            status: {stage: 0 for stage in ASSIGNMENT_GAP_STAGES}
            for status in WORKFORCE_AFFILIATION_CLASSES
        },
        "assignment_gap_stage_counts_by_affiliation_by_village": {},
        "assignment_gap_block_reasons_by_role": {role: {} for role in WORKFORCE_REALIZATION_ROLES},
        "assignment_gap_block_reasons_by_role_by_village": {},
        "task_completion_stage_counts_by_task": {
            task: {stage: 0 for stage in TASK_COMPLETION_STAGES}
            for task in TASK_COMPLETION_KEYS
        },
        "task_completion_stage_counts_by_task_by_village": {},
        "task_completion_failure_reasons_by_task": {task: {} for task in TASK_COMPLETION_KEYS},
        "task_completion_failure_reasons_by_task_by_village": {},
        "task_completion_stage_counts_by_affiliation": {
            status: {
                "preconditions_failed_count": 0,
                "productive_completion_count": 0,
            }
            for status in WORKFORCE_AFFILIATION_CLASSES
        },
        "task_completion_stage_counts_by_affiliation_by_village": {},
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
        eco_seed = int(seed) + 104729 if seed is not None else 104729
        self._eco_rng = random.Random(eco_seed)
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
        self.resource_respawn_stats: Dict[str, int] = _default_resource_respawn_stats()
        self.specialization_diagnostics: Dict[str, Any] = {}
        if hasattr(building_system, "get_or_init_specialization_diagnostics"):
            self.specialization_diagnostics = building_system.get_or_init_specialization_diagnostics(self)
        self.workforce_realization_stats: Dict[str, Any] = _default_workforce_realization_stats()
        self.movement_diagnostic_stats: Dict[str, Any] = _default_movement_diagnostic_stats()
        self.delivery_diagnostic_stats: Dict[str, Any] = _default_delivery_diagnostic_stats()
        self.housing_construction_stats: Dict[str, Any] = _default_housing_construction_stats()
        self.housing_siting_stats: Dict[str, Any] = _default_housing_siting_stats()
        self.housing_path_coherence_stats: Dict[str, Any] = _default_housing_path_coherence_stats()
        self.builder_self_supply_stats: Dict[str, Any] = _default_builder_self_supply_stats()
        self.builder_self_supply_gate_stats: Dict[str, Any] = _default_builder_self_supply_gate_stats()
        self.social_gravity_event_stats: Dict[str, Any] = _default_social_gravity_event_stats()
        self.social_encounter_stats: Dict[str, int] = _default_social_encounter_stats()
        self.residence_stabilization_stats: Dict[str, Any] = _default_residence_stabilization_stats()
        self.resident_conversion_gate_stats: Dict[str, Any] = _default_resident_conversion_gate_stats()
        self.recovery_diagnostic_stats: Dict[str, Any] = _default_recovery_diagnostic_stats()
        self.proto_communities: Dict[str, Dict[str, Any]] = {}
        self._proto_community_counter: int = 0
        self.camps: Dict[str, Dict[str, Any]] = {}
        self._camp_counter: int = 0
        self.progression_stats: Dict[str, Any] = _default_progression_stats()
        self.camp_food_stats: Dict[str, int] = _default_camp_food_stats()
        self.communication_stats: Dict[str, int] = _default_communication_stats()
        self.proto_specialization_switches: int = 0
        self.proto_specialization_assigned_tick_count: int = 0
        self.proto_specialization_retained_ticks: int = 0
        self.proto_specialization_cleared_count: int = 0
        self.proto_specialization_cleared_reasons: Dict[str, int] = {}
        self.proto_specialization_anchor_assignments: int = 0
        self.proto_specialization_anchor_retained_ticks: int = 0
        self.proto_specialization_anchor_invalidations: int = 0
        self.proto_specialization_anchor_invalidation_reasons: Dict[str, int] = {}
        self.proto_community_funnel_stats: Dict[str, Any] = _default_proto_funnel_stats()
        self.camp_lifecycle_stats: Dict[str, Any] = _default_camp_lifecycle_stats()
        self.camp_targeting_stats: Dict[str, Any] = _default_camp_targeting_stats()
        self.situated_construction_stats: Dict[str, int] = _default_situated_construction_stats()
        self.settlement_bottleneck_stats: Dict[str, Any] = _default_settlement_bottleneck_stats()
        self.settlement_progression_stats: Dict[str, Any] = _default_settlement_progression_stats()
        self.behavior_map_stats: Dict[str, Any] = _default_behavior_map_stats()
        self.food_rich_patches: List[Dict[str, Any]] = []
        self.food_patch_food_spawned: int = 0
        self.food_patch_activity: Dict[str, float] = {}
        self.farm_discovery_memory: Dict[str, Dict[str, Any]] = {}
        self.local_practice_memory: Dict[str, Dict[str, Any]] = {}

        self.MAX_STRUCTURES = MAX_STRUCTURES
        self.MAX_HOUSES_PER_VILLAGE = MAX_HOUSES_PER_VILLAGE
        self.MAX_NEW_VILLAGE_SEEDS = MAX_NEW_VILLAGE_SEEDS
        self.MIN_HOUSES_FOR_VILLAGE = MIN_HOUSES_FOR_VILLAGE
        self.MIN_HOUSES_FOR_LEADER = MIN_HOUSES_FOR_LEADER
        self.EARLY_SURVIVAL_RELIEF_TICKS = EARLY_SURVIVAL_RELIEF_TICKS
        self.INITIAL_FOUNDER_QUOTA = INITIAL_FOUNDER_QUOTA
        self.founders_assigned = 0
        self.founding_hub: Optional[Coord] = None

        self.MAX_FOOD = MAX_FOOD
        self.MAX_WOOD = MAX_WOOD
        self.MAX_STONE = MAX_STONE

        self._generate_food_rich_patches()
        self._spawn_initial_food(NUM_FOOD)
        self._spawn_initial_wood(NUM_WOOD)
        self._spawn_initial_stone(NUM_STONE)
        self.initial_resource_stock: Dict[str, int] = {
            "food": int(len(self.food)),
            "wood": int(len(self.wood)),
            "stone": int(len(self.stone)),
        }

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
        self.debug_construction_trace_enabled: bool = False
        self.debug_construction_trace_path: Optional[str] = None
        self.debug_construction_trace_max_agents: int = 3
        self.debug_construction_trace_max_sites: int = 2
        self._debug_construction_traced_agents: Set[str] = set()
        self._debug_construction_traced_sites: Set[str] = set()
        self.debug_foraging_switch_trace_enabled: bool = False
        self.debug_foraging_switch_trace_path: Optional[str] = None
        self.debug_foraging_switch_trace_max_agents: int = 4
        self._debug_foraging_switch_traced_agents: Set[str] = set()

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

    def _resolve_agent_work_village_uid(self, agent: Agent) -> str:
        village_uid = self.resolve_village_uid(getattr(agent, "village_id", None))
        if village_uid:
            return str(village_uid)
        home_uid = str(getattr(agent, "home_village_uid", "") or "")
        if home_uid:
            return home_uid
        primary_uid = str(getattr(agent, "primary_village_uid", "") or "")
        return primary_uid

    def _workforce_affiliation_for_village(self, agent: Agent, village_uid: str) -> str:
        uid = str(village_uid or "")
        status = str(getattr(agent, "village_affiliation_status", "unaffiliated"))
        home_uid = str(getattr(agent, "home_village_uid", "") or "")
        primary_uid = str(getattr(agent, "primary_village_uid", "") or "")
        if status == "resident" and home_uid == uid:
            return "resident"
        if status == "attached" and primary_uid == uid:
            return "attached"
        if status == "transient" and primary_uid == uid:
            return "transient"
        return "unaffiliated"

    def record_workforce_productive_action(
        self,
        agent: Agent,
        role: str,
        action: str,
        *,
        village_uid: Optional[str] = None,
    ) -> None:
        role_key = str(role)
        if role_key not in WORKFORCE_REALIZATION_ROLES:
            return
        stats = self.workforce_realization_stats
        if not isinstance(stats, dict):
            stats = _default_workforce_realization_stats()
            self.workforce_realization_stats = stats

        uid = str(village_uid or self._resolve_agent_work_village_uid(agent) or "")
        action_key = str(action or "unknown")

        by_role = stats.setdefault("productive_actions_by_role", {})
        by_role[role_key] = int(by_role.get(role_key, 0)) + 1

        by_role_actions = stats.setdefault("productive_actions_by_role_actions", {})
        role_actions = by_role_actions.setdefault(role_key, {})
        role_actions[action_key] = int(role_actions.get(action_key, 0)) + 1

        if uid:
            by_village = stats.setdefault("productive_actions_by_role_by_village", {})
            ventry = by_village.setdefault(uid, {r: 0 for r in WORKFORCE_REALIZATION_ROLES})
            ventry[role_key] = int(ventry.get(role_key, 0)) + 1

            by_village_actions = stats.setdefault("productive_actions_by_role_actions_by_village", {})
            vactions = by_village_actions.setdefault(uid, {})
            vrole_actions = vactions.setdefault(role_key, {})
            vrole_actions[action_key] = int(vrole_actions.get(action_key, 0)) + 1

        affiliation = self._workforce_affiliation_for_village(agent, uid) if uid else "unaffiliated"
        by_aff = stats.setdefault("productive_actions_by_affiliation", {})
        role_aff = by_aff.setdefault(role_key, _empty_workforce_affiliation_counts())
        role_aff[affiliation] = int(role_aff.get(affiliation, 0)) + 1

        if uid:
            by_aff_village = stats.setdefault("productive_actions_by_affiliation_by_village", {})
            vaff = by_aff_village.setdefault(
                uid,
                {r: _empty_workforce_affiliation_counts() for r in WORKFORCE_REALIZATION_ROLES},
            )
            role_vaff = vaff.setdefault(role_key, _empty_workforce_affiliation_counts())
            role_vaff[affiliation] = int(role_vaff.get(affiliation, 0)) + 1

        last_prod = getattr(agent, "workforce_last_productive_tick_by_role", None)
        if not isinstance(last_prod, dict):
            last_prod = {}
            agent.workforce_last_productive_tick_by_role = last_prod
        last_prod[role_key] = int(self.tick)
        self.record_assignment_pipeline_stage(agent, role_key, "productive_action_count", village_uid=uid)

    def record_workforce_block_reason(
        self,
        agent: Agent,
        role: str,
        reason: str,
        *,
        village_uid: Optional[str] = None,
    ) -> None:
        role_key = str(role)
        if role_key not in WORKFORCE_REALIZATION_ROLES:
            return
        reason_key = str(reason)
        if reason_key not in WORKFORCE_BLOCK_REASONS:
            reason_key = "no_valid_task"

        stats = self.workforce_realization_stats
        if not isinstance(stats, dict):
            stats = _default_workforce_realization_stats()
            self.workforce_realization_stats = stats

        by_role = stats.setdefault("block_reasons_by_role", {})
        role_reasons = by_role.setdefault(role_key, {})
        role_reasons[reason_key] = int(role_reasons.get(reason_key, 0)) + 1

        uid = str(village_uid or self._resolve_agent_work_village_uid(agent) or "")
        if uid:
            by_village = stats.setdefault("block_reasons_by_role_by_village", {})
            ventry = by_village.setdefault(uid, {})
            vrole_reasons = ventry.setdefault(role_key, {})
            vrole_reasons[reason_key] = int(vrole_reasons.get(reason_key, 0)) + 1

        last_block = getattr(agent, "workforce_last_block_tick_by_role", None)
        if not isinstance(last_block, dict):
            last_block = {}
            agent.workforce_last_block_tick_by_role = last_block
        last_block[role_key] = int(self.tick)
        assignment_reason_map = {
            "no_valid_task": "no_task_candidate",
            "no_target_found": "no_target_candidate",
            "no_materials_available": "no_materials",
            "no_storage_available": "no_storage",
            "no_construction_site": "no_construction_site",
            "waiting_on_delivery": "waiting_on_delivery",
            "survival_override": "survival_override",
            "role_hold_block": "task_replaced",
            "task_conflict": "task_replaced",
            "no_affiliated_village_context": "affiliation_context_missing",
        }
        mapped = assignment_reason_map.get(reason_key, "no_task_candidate")
        self.record_assignment_pipeline_block_reason(agent, role_key, mapped, village_uid=uid)

    def record_assignment_pipeline_stage(
        self,
        agent: Agent,
        role: str,
        stage: str,
        *,
        village_uid: Optional[str] = None,
    ) -> None:
        role_key = str(role)
        stage_key = str(stage)
        if role_key not in WORKFORCE_REALIZATION_ROLES or stage_key not in ASSIGNMENT_GAP_STAGES:
            return
        stats = self.workforce_realization_stats
        if not isinstance(stats, dict):
            stats = _default_workforce_realization_stats()
            self.workforce_realization_stats = stats
        uid = str(village_uid or self._resolve_agent_work_village_uid(agent) or "")
        by_role = stats.setdefault("assignment_gap_stage_counts_by_role", {})
        role_counts = by_role.setdefault(role_key, {s: 0 for s in ASSIGNMENT_GAP_STAGES})
        role_counts[stage_key] = int(role_counts.get(stage_key, 0)) + 1

        affiliation = self._workforce_affiliation_for_village(agent, uid) if uid else "unaffiliated"
        by_aff = stats.setdefault("assignment_gap_stage_counts_by_affiliation", {})
        aff_counts = by_aff.setdefault(affiliation, {s: 0 for s in ASSIGNMENT_GAP_STAGES})
        aff_counts[stage_key] = int(aff_counts.get(stage_key, 0)) + 1

        if uid:
            by_village = stats.setdefault("assignment_gap_stage_counts_by_role_by_village", {})
            ventry = by_village.setdefault(uid, {})
            vrole = ventry.setdefault(role_key, {s: 0 for s in ASSIGNMENT_GAP_STAGES})
            vrole[stage_key] = int(vrole.get(stage_key, 0)) + 1

            by_aff_village = stats.setdefault("assignment_gap_stage_counts_by_affiliation_by_village", {})
            vaff = by_aff_village.setdefault(
                uid,
                {status: {s: 0 for s in ASSIGNMENT_GAP_STAGES} for status in WORKFORCE_AFFILIATION_CLASSES},
            )
            status_counts = vaff.setdefault(affiliation, {s: 0 for s in ASSIGNMENT_GAP_STAGES})
            status_counts[stage_key] = int(status_counts.get(stage_key, 0)) + 1

    def record_assignment_pipeline_block_reason(
        self,
        agent: Agent,
        role: str,
        reason: str,
        *,
        village_uid: Optional[str] = None,
    ) -> None:
        role_key = str(role)
        reason_key = str(reason)
        if role_key not in WORKFORCE_REALIZATION_ROLES:
            return
        if reason_key not in ASSIGNMENT_GAP_BLOCK_REASONS:
            reason_key = "no_task_candidate"
        stats = self.workforce_realization_stats
        if not isinstance(stats, dict):
            stats = _default_workforce_realization_stats()
            self.workforce_realization_stats = stats
        by_role = stats.setdefault("assignment_gap_block_reasons_by_role", {})
        role_reasons = by_role.setdefault(role_key, {})
        role_reasons[reason_key] = int(role_reasons.get(reason_key, 0)) + 1

        uid = str(village_uid or self._resolve_agent_work_village_uid(agent) or "")
        if uid:
            by_village = stats.setdefault("assignment_gap_block_reasons_by_role_by_village", {})
            ventry = by_village.setdefault(uid, {})
            vrole = ventry.setdefault(role_key, {})
            vrole[reason_key] = int(vrole.get(reason_key, 0)) + 1

        self.record_assignment_pipeline_stage(agent, role_key, "abandoned_or_overridden_count", village_uid=uid)

    def record_task_completion_stage(
        self,
        agent: Agent,
        task_key: str,
        stage: str,
        *,
        village_uid: Optional[str] = None,
    ) -> None:
        task = str(task_key)
        stage_key = str(stage)
        if task not in TASK_COMPLETION_KEYS or stage_key not in TASK_COMPLETION_STAGES:
            return
        stats = self.workforce_realization_stats
        if not isinstance(stats, dict):
            stats = _default_workforce_realization_stats()
            self.workforce_realization_stats = stats
        uid = str(village_uid or self._resolve_agent_work_village_uid(agent) or "")

        by_task = stats.setdefault("task_completion_stage_counts_by_task", {})
        task_counts = by_task.setdefault(task, {s: 0 for s in TASK_COMPLETION_STAGES})
        task_counts[stage_key] = int(task_counts.get(stage_key, 0)) + 1

        affiliation = self._workforce_affiliation_for_village(agent, uid) if uid else "unaffiliated"
        if stage_key in {"preconditions_failed_count", "productive_completion_count"}:
            by_aff = stats.setdefault("task_completion_stage_counts_by_affiliation", {})
            aff_counts = by_aff.setdefault(
                affiliation,
                {"preconditions_failed_count": 0, "productive_completion_count": 0},
            )
            aff_counts[stage_key] = int(aff_counts.get(stage_key, 0)) + 1

        if uid:
            by_village = stats.setdefault("task_completion_stage_counts_by_task_by_village", {})
            ventry = by_village.setdefault(uid, {})
            vtask = ventry.setdefault(task, {s: 0 for s in TASK_COMPLETION_STAGES})
            vtask[stage_key] = int(vtask.get(stage_key, 0)) + 1
            if stage_key in {"preconditions_failed_count", "productive_completion_count"}:
                by_aff_village = stats.setdefault("task_completion_stage_counts_by_affiliation_by_village", {})
                vaff = by_aff_village.setdefault(
                    uid,
                    {
                        status: {
                            "preconditions_failed_count": 0,
                            "productive_completion_count": 0,
                        }
                        for status in WORKFORCE_AFFILIATION_CLASSES
                    },
                )
                va = vaff.setdefault(
                    affiliation,
                    {"preconditions_failed_count": 0, "productive_completion_count": 0},
                )
                va[stage_key] = int(va.get(stage_key, 0)) + 1

    def record_task_completion_failure_reason(
        self,
        agent: Agent,
        task_key: str,
        reason: str,
        *,
        village_uid: Optional[str] = None,
    ) -> None:
        task = str(task_key)
        reason_key = str(reason)
        if task not in TASK_COMPLETION_KEYS:
            return
        if reason_key not in TASK_COMPLETION_FAILURE_REASONS:
            reason_key = "invalid_site_state"
        stats = self.workforce_realization_stats
        if not isinstance(stats, dict):
            stats = _default_workforce_realization_stats()
            self.workforce_realization_stats = stats
        by_task = stats.setdefault("task_completion_failure_reasons_by_task", {})
        task_reasons = by_task.setdefault(task, {})
        task_reasons[reason_key] = int(task_reasons.get(reason_key, 0)) + 1
        uid = str(village_uid or self._resolve_agent_work_village_uid(agent) or "")
        if uid:
            by_village = stats.setdefault("task_completion_failure_reasons_by_task_by_village", {})
            ventry = by_village.setdefault(uid, {})
            vtask = ventry.setdefault(task, {})
            vtask[reason_key] = int(vtask.get(reason_key, 0)) + 1

    def record_task_completion_attempt(self, agent: Agent, task_key: str) -> None:
        self.record_task_completion_stage(agent, task_key, "task_attempt_count")

    def record_task_completion_preconditions_met(self, agent: Agent, task_key: str) -> None:
        self.record_task_completion_stage(agent, task_key, "preconditions_met_count")

    def record_task_completion_preconditions_failed(self, agent: Agent, task_key: str, reason: str) -> None:
        self.record_task_completion_stage(agent, task_key, "preconditions_failed_count")
        self.record_task_completion_failure_reason(agent, task_key, reason)

    def record_task_completion_productive(self, agent: Agent, task_key: str) -> None:
        self.record_task_completion_stage(agent, task_key, "productive_completion_count")

    def record_task_completion_interrupted(self, agent: Agent, task_key: str, reason: str) -> None:
        self.record_task_completion_stage(agent, task_key, "interrupted_or_replaced_count")
        self.record_task_completion_failure_reason(agent, task_key, reason)

    def _nearest_active_construction_site_id_for_agent(self, agent: Agent) -> str:
        aid = str(getattr(agent, "village_id", ""))
        best_id = ""
        best_dist = 10_000
        for b in (self.buildings or {}).values():
            if not isinstance(b, dict):
                continue
            if str(b.get("type", "")) not in {"house", "storage"}:
                continue
            if str(b.get("operational_state", "")) != "under_construction":
                continue
            if aid and str(b.get("village_id", "")) != aid:
                continue
            bx, by = int(b.get("x", 0)), int(b.get("y", 0))
            dist = abs(int(getattr(agent, "x", 0)) - bx) + abs(int(getattr(agent, "y", 0)) - by)
            bid = str(b.get("building_id", ""))
            if dist < best_dist or (dist == best_dist and bid < best_id):
                best_dist = dist
                best_id = bid
        return best_id

    def _construction_site_payload(self, site_id: str) -> Dict[str, Any]:
        building = (self.buildings or {}).get(str(site_id))
        if not isinstance(building, dict):
            return {}
        rm = building.get("remaining_materials", {})
        dm = building.get("delivered_materials", {})
        return {
            "site_id": str(site_id),
            "site_type": str(building.get("type", "")),
            "site_x": int(building.get("x", 0)),
            "site_y": int(building.get("y", 0)),
            "site_build_state": str(building.get("build_state", "")),
            "site_remaining_materials": {
                "wood": int((rm or {}).get("wood", 0)) if isinstance(rm, dict) else 0,
                "stone": int((rm or {}).get("stone", 0)) if isinstance(rm, dict) else 0,
                "food": int((rm or {}).get("food", 0)) if isinstance(rm, dict) else 0,
            },
            "site_delivered_materials": {
                "wood": int((dm or {}).get("wood", 0)) if isinstance(dm, dict) else 0,
                "stone": int((dm or {}).get("stone", 0)) if isinstance(dm, dict) else 0,
                "food": int((dm or {}).get("food", 0)) if isinstance(dm, dict) else 0,
            },
            "site_remaining_work_ticks": int(building.get("remaining_work_ticks", 0)),
            "site_completed_work_ticks": int(building.get("completed_work_ticks", 0)),
        }

    def record_construction_debug_event(
        self,
        agent: Optional[Agent],
        event_name: str,
        *,
        reason: str = "",
        previous_task: Optional[str] = None,
        target: Optional[Tuple[int, int]] = None,
        site_id: Optional[str] = None,
    ) -> None:
        if not bool(getattr(self, "debug_construction_trace_enabled", False)):
            return
        if agent is None:
            return
        role = str(getattr(agent, "role", ""))
        task = str(getattr(agent, "task", ""))
        assigned_site = str(getattr(agent, "assigned_building_id", "") or "")
        is_construction_agent = role == "builder" or task in {"build_house", "build_storage", "gather_materials"}
        if not is_construction_agent and not assigned_site:
            return

        agent_id = str(getattr(agent, "agent_id", ""))
        if agent_id and agent_id not in self._debug_construction_traced_agents:
            if len(self._debug_construction_traced_agents) >= int(max(1, self.debug_construction_trace_max_agents)):
                return
            self._debug_construction_traced_agents.add(agent_id)

        sid = str(site_id or assigned_site or "")
        if sid and sid not in self._debug_construction_traced_sites:
            if len(self._debug_construction_traced_sites) >= int(max(1, self.debug_construction_trace_max_sites)):
                sid = ""
            else:
                self._debug_construction_traced_sites.add(sid)
        if not sid:
            sid = str(self._nearest_active_construction_site_id_for_agent(agent) or "")

        sx = int(target[0]) if isinstance(target, tuple) and len(target) == 2 else None
        sy = int(target[1]) if isinstance(target, tuple) and len(target) == 2 else None
        if sx is None or sy is None:
            task_target = getattr(agent, "task_target", None)
            if isinstance(task_target, tuple) and len(task_target) == 2:
                sx, sy = int(task_target[0]), int(task_target[1])

        payload: Dict[str, Any] = {
            "tick": int(getattr(self, "tick", 0)),
            "event_name": str(event_name),
            "reason": str(reason or ""),
            "agent_id": agent_id,
            "role": role,
            "current_task": task,
            "previous_task": str(previous_task or ""),
            "x": int(getattr(agent, "x", 0)),
            "y": int(getattr(agent, "y", 0)),
            "target_x": sx,
            "target_y": sy,
            "hunger": round(float(getattr(agent, "hunger", 0.0)), 3),
            "sleep_need": round(float(getattr(agent, "sleep_need", 0.0)), 3),
            "fatigue": round(float(getattr(agent, "fatigue", 0.0)), 3),
            "inventory": {
                "food": int(getattr(agent, "inventory", {}).get("food", 0)),
                "wood": int(getattr(agent, "inventory", {}).get("wood", 0)),
                "stone": int(getattr(agent, "inventory", {}).get("stone", 0)),
            },
            "assigned_site_id": assigned_site,
            "nearest_active_site_id": str(self._nearest_active_construction_site_id_for_agent(agent) or ""),
            "on_site": False,
        }
        site_payload = self._construction_site_payload(sid)
        if site_payload:
            payload.update(site_payload)
            payload["on_site"] = bool(
                abs(int(getattr(agent, "x", 0)) - int(site_payload.get("site_x", 0)))
                + abs(int(getattr(agent, "y", 0)) - int(site_payload.get("site_y", 0)))
                <= 1
            )
        if hasattr(self, "record_settlement_progression_metric"):
            if str(event_name) == "assigned_site":
                self.record_settlement_progression_metric("builder_assigned_site_count")
            elif str(event_name) == "arrived_on_site":
                self.record_settlement_progression_metric("builder_site_arrival_count")
                if sid:
                    building = (self.buildings or {}).get(str(sid))
                    if isinstance(building, dict):
                        first_arrival = int(building.get("construction_first_builder_arrival_tick", -1))
                        if first_arrival < 0:
                            building["construction_first_builder_arrival_tick"] = int(getattr(self, "tick", 0))
                            created = int(building.get("construction_created_tick", int(getattr(self, "tick", 0))))
                            self.record_settlement_progression_metric(
                                "construction_site_first_builder_arrival_delay_total",
                                max(0, int(getattr(self, "tick", 0)) - created),
                            )
                            self.record_settlement_progression_metric("construction_site_first_builder_arrival_delay_samples", 1)
            elif str(event_name) == "left_site":
                self.record_settlement_progression_metric("builder_left_site_count")
                if site_payload and int(site_payload.get("site_remaining_work_ticks", 0)) > 0:
                    self.record_settlement_progression_metric("builder_left_site_before_completion_count")
            elif str(event_name) == "waiting_on_delivery":
                self.record_settlement_progression_metric("builder_waiting_on_site_ticks_total")
            elif str(event_name) == "on_site_tick":
                self.record_settlement_progression_metric("builder_on_site_ticks_total")
            elif str(event_name) == "work_tick_applied":
                self.record_settlement_progression_metric("builder_work_tick_applied_count")
                if sid:
                    building = (self.buildings or {}).get(str(sid))
                    if isinstance(building, dict):
                        first_work = int(building.get("construction_first_progress_tick", -1))
                        mat_ready_tick = int(building.get("construction_material_ready_tick", -1))
                        if first_work >= 0 and mat_ready_tick >= 0 and int(building.get("construction_material_ready_to_first_work_recorded", 0)) == 0:
                            self.record_settlement_progression_metric(
                                "construction_site_material_ready_to_first_work_delay_total",
                                max(0, first_work - mat_ready_tick),
                            )
                            self.record_settlement_progression_metric("construction_site_material_ready_to_first_work_delay_samples", 1)
                            building["construction_material_ready_to_first_work_recorded"] = 1
            elif str(event_name) == "survival_override":
                self.record_settlement_progression_metric("builder_survival_override_during_construction_count")
            elif str(event_name) == "redirected_to_storage":
                self.record_settlement_progression_metric("builder_redirected_to_storage_during_construction_count")
        try:
            path = str(getattr(self, "debug_construction_trace_path", "") or "")
            if not path:
                return
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, sort_keys=True) + "\n")
        except Exception:
            pass

    def record_foraging_switch_debug_event(
        self,
        agent: Optional[Agent],
        event_name: str,
        *,
        prev_task: str = "",
        new_task: str = "",
        reason: str = "",
        source_subsystem: str = "unknown",
        ticks_since_first_harvest: int = -1,
        within_exploitation_window: bool = False,
        commitment_active: bool = False,
        target_valid: bool = False,
        local_food_available: int = 0,
        nearest_food_distance: int = -1,
    ) -> None:
        if not bool(getattr(self, "debug_foraging_switch_trace_enabled", False)):
            return
        if agent is None:
            return
        agent_id = str(getattr(agent, "agent_id", ""))
        if agent_id and agent_id not in self._debug_foraging_switch_traced_agents:
            if len(self._debug_foraging_switch_traced_agents) >= int(max(1, self.debug_foraging_switch_trace_max_agents)):
                return
            self._debug_foraging_switch_traced_agents.add(agent_id)
        payload: Dict[str, Any] = {
            "tick": int(getattr(self, "tick", 0)),
            "event_name": str(event_name),
            "prev_task": str(prev_task or ""),
            "new_task": str(new_task or ""),
            "reason": str(reason or ""),
            "source_subsystem": str(source_subsystem or "unknown"),
            "agent_id": agent_id,
            "x": int(getattr(agent, "x", 0)),
            "y": int(getattr(agent, "y", 0)),
            "pressure_regime": str(getattr(agent, "foraging_pressure_regime", "medium") or "medium"),
            "pressure_ratio": round(float(getattr(agent, "foraging_pressure_ratio", 0.0) or 0.0), 4),
            "hunger": round(float(getattr(agent, "hunger", 0.0)), 3),
            "food_inventory": int(getattr(agent, "inventory", {}).get("food", 0)),
            "harvest_count_on_trip": int(getattr(agent, "foraging_trip_harvest_actions", 0)),
            "ticks_since_first_harvest": int(ticks_since_first_harvest),
            "within_exploitation_window": bool(within_exploitation_window),
            "commitment_active": bool(commitment_active),
            "target_valid": bool(target_valid),
            "local_food_available": int(local_food_available),
            "nearest_food_distance": int(nearest_food_distance),
            "task_target": list(getattr(agent, "task_target", ())) if isinstance(getattr(agent, "task_target", None), tuple) else [],
        }
        if hasattr(self, "record_settlement_progression_metric"):
            event_key = str(event_name or "")
            source = str(source_subsystem or "unknown")
            if source not in {
                "survival_override",
                "role_task_update",
                "brain_retarget",
                "commitment_clear",
                "target_invalidated",
                "inventory_logic",
                "wander_fallback",
                "unknown",
            }:
                source = "unknown"
            if event_key == "post_first_harvest_task_switch_attempt":
                self.record_settlement_progression_metric("post_first_harvest_task_switch_attempt_count")
                self.record_settlement_progression_metric(f"post_first_harvest_task_switch_attempt_source_{source}")
            elif event_key == "post_first_harvest_task_switch_committed":
                self.record_settlement_progression_metric("post_first_harvest_task_switch_committed_count")
                self.record_settlement_progression_metric(f"post_first_harvest_task_switch_committed_source_{source}")
            elif event_key == "post_first_harvest_task_switch_blocked":
                self.record_settlement_progression_metric("post_first_harvest_task_switch_blocked_count")
                self.record_settlement_progression_metric(f"post_first_harvest_task_switch_blocked_source_{source}")
        try:
            path = str(getattr(self, "debug_foraging_switch_trace_path", "") or "")
            if not path:
                return
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, sort_keys=True) + "\n")
        except Exception:
            pass

    def _movement_bucket(self, stats: Dict[str, Any], key: str, label: str) -> Dict[str, Any]:
        bucket_map = stats.setdefault(key, {})
        bucket = bucket_map.get(label)
        if not isinstance(bucket, dict):
            bucket = _empty_movement_metrics()
            bucket_map[label] = bucket
        return bucket

    def _resolve_movement_transport_context(self, pos: Tuple[int, int]) -> str:
        transport = self.get_transport_type(int(pos[0]), int(pos[1]))
        if transport is None:
            return "off_network"
        t = str(transport)
        return t if t in MOVEMENT_DIAGNOSTIC_CONTEXTS else "off_network"

    def _movement_track_for_agent(self, stats: Dict[str, Any], agent_id: str, current_pos: Tuple[int, int]) -> Dict[str, Any]:
        tracks = stats.setdefault("agent_track", {})
        track = tracks.get(agent_id)
        if not isinstance(track, dict):
            track = {
                "origin": (int(current_pos[0]), int(current_pos[1])),
                "last_pos": (int(current_pos[0]), int(current_pos[1])),
                "prev_pos": None,
                "last_target": None,
                "last_target_tick": -10**9,
                "oscillation_events": 0,
            }
            tracks[agent_id] = track
        return track

    def _movement_increment(self, bucket: Dict[str, Any], key: str, amount: int = 1) -> None:
        bucket[key] = int(bucket.get(key, 0)) + int(amount)

    def _record_movement_tile_hotspot(
        self,
        stats: Dict[str, Any],
        pos: Tuple[int, int],
        *,
        peak_occupancy: int = 0,
        congestion_events: int = 0,
    ) -> None:
        hotspots = stats.setdefault("tile_hotspots", {})
        key = f"{int(pos[0])},{int(pos[1])}"
        entry = hotspots.get(key)
        if not isinstance(entry, dict):
            entry = {"tile_position": {"x": int(pos[0]), "y": int(pos[1])}, "congestion_events": 0, "peak_occupancy": 0}
            hotspots[key] = entry
        if int(congestion_events) > 0:
            entry["congestion_events"] = int(entry.get("congestion_events", 0)) + int(congestion_events)
        if int(peak_occupancy) > int(entry.get("peak_occupancy", 0)):
            entry["peak_occupancy"] = int(peak_occupancy)

    def _agent_at_tile(self, x: int, y: int, *, exclude_agent_id: Optional[str] = None) -> Optional[Agent]:
        ex = str(exclude_agent_id or "")
        for a in self.agents:
            if not getattr(a, "alive", False):
                continue
            if ex and str(getattr(a, "agent_id", "")) == ex:
                continue
            if int(getattr(a, "x", -10**9)) == int(x) and int(getattr(a, "y", -10**9)) == int(y):
                return a
        return None

    def _count_agents_on_tile(self, x: int, y: int) -> int:
        n = 0
        for a in self.agents:
            if not getattr(a, "alive", False):
                continue
            if int(getattr(a, "x", -10**9)) == int(x) and int(getattr(a, "y", -10**9)) == int(y):
                n += 1
        return int(n)

    def _movement_iter_buckets(
        self,
        stats: Dict[str, Any],
        *,
        role: str,
        task: str,
        context: str,
        village_uid: str,
    ) -> List[Dict[str, Any]]:
        buckets = [stats.setdefault("global", _empty_movement_metrics())]
        buckets.append(self._movement_bucket(stats, "by_role", role))
        buckets.append(self._movement_bucket(stats, "by_task", task))
        buckets.append(self._movement_bucket(stats, "by_transport_context", context))
        if village_uid:
            village_map = stats.setdefault("by_village", {})
            village_entry = village_map.get(village_uid)
            if not isinstance(village_entry, dict):
                village_entry = {
                    "global": _empty_movement_metrics(),
                    "by_role": {},
                    "by_task": {},
                    "by_transport_context": {},
                }
                village_map[village_uid] = village_entry
            vb = village_entry.setdefault("global", _empty_movement_metrics())
            buckets.append(vb)
            buckets.append(self._movement_bucket(village_entry, "by_role", role))
            buckets.append(self._movement_bucket(village_entry, "by_task", task))
            buckets.append(self._movement_bucket(village_entry, "by_transport_context", context))
        return buckets

    def record_movement_congestion_snapshot(self) -> None:
        stats = self.movement_diagnostic_stats
        if not isinstance(stats, dict):
            stats = _default_movement_diagnostic_stats()
            self.movement_diagnostic_stats = stats

        # Per-tick occupancy pass to capture crowding pressure independently from movement success/failure.
        occupancy: Dict[Tuple[int, int], int] = {}
        alive = [a for a in self.agents if getattr(a, "alive", False)]
        for a in alive:
            pos = (int(getattr(a, "x", 0)), int(getattr(a, "y", 0)))
            occupancy[pos] = int(occupancy.get(pos, 0)) + 1
            context = self._resolve_movement_transport_context(pos)
            if context == "road":
                gb = stats.setdefault("global", _empty_movement_metrics())
                self._movement_increment(gb, "road_tile_agent_samples", 1)
                self._movement_increment(self._movement_bucket(stats, "by_transport_context", context), "road_tile_agent_samples", 1)

        for pos, count in occupancy.items():
            peak = max(0, int(count))
            context = self._resolve_movement_transport_context(pos)
            gb = stats.setdefault("global", _empty_movement_metrics())
            if peak > int(gb.get("tile_occupancy_peak", 0)):
                gb["tile_occupancy_peak"] = peak
            cb = self._movement_bucket(stats, "by_transport_context", context)
            if peak > int(cb.get("tile_occupancy_peak", 0)):
                cb["tile_occupancy_peak"] = peak
            if peak >= 2:
                self._movement_increment(gb, "tile_occupancy_samples", 1)
                self._movement_increment(gb, "multi_agent_tile_events", 1)
                self._movement_increment(cb, "tile_occupancy_samples", 1)
                self._movement_increment(cb, "multi_agent_tile_events", 1)
                if context == "road":
                    self._movement_increment(gb, "road_tile_multi_agent_events", 1)
                    self._movement_increment(cb, "road_tile_multi_agent_events", 1)
                self._record_movement_tile_hotspot(stats, pos, peak_occupancy=peak, congestion_events=1)

    def record_movement_blocked_by_agent(
        self,
        agent: Agent,
        *,
        from_pos: Tuple[int, int],
        to_pos: Tuple[int, int],
        target: Optional[Coord],
        blocking_agent: Optional[Agent] = None,
    ) -> None:
        stats = self.movement_diagnostic_stats
        if not isinstance(stats, dict):
            stats = _default_movement_diagnostic_stats()
            self.movement_diagnostic_stats = stats
        role = str(getattr(agent, "role", "npc"))
        role_key = role if role in MOVEMENT_DIAGNOSTIC_ROLES else "other"
        task = str(getattr(agent, "task", "idle") or "idle")
        uid = str(self._resolve_agent_work_village_uid(agent) or "")
        context = self._resolve_movement_transport_context((int(to_pos[0]), int(to_pos[1])))
        buckets = self._movement_iter_buckets(stats, role=role_key, task=task, context=context, village_uid=uid)
        for bucket in buckets:
            self._movement_increment(bucket, "blocked_by_agent_count", 1)
            self._movement_increment(bucket, "attempted_move_into_occupied_tile", 1)

        if isinstance(target, tuple) and len(target) == 2:
            dist_to_target = abs(int(target[0]) - int(from_pos[0])) + abs(int(target[1]) - int(from_pos[1]))
            if dist_to_target <= 2:
                for bucket in buckets:
                    self._movement_increment(bucket, "near_target_blocked_by_agent", 1)

        # Detect likely head-on conflicts when both agents target each other local tiles.
        head_on = False
        blocker = blocking_agent
        if blocker is None:
            blocker = self._agent_at_tile(int(to_pos[0]), int(to_pos[1]), exclude_agent_id=str(getattr(agent, "agent_id", "")))
        if blocker is not None:
            other_targets: List[Tuple[int, int]] = []
            for cand in (
                getattr(blocker, "task_target", None),
                getattr(blocker, "movement_commit_target", None),
            ):
                if isinstance(cand, tuple) and len(cand) == 2:
                    other_targets.append((int(cand[0]), int(cand[1])))
            cint = getattr(blocker, "current_intention", None)
            if isinstance(cint, dict):
                tdata = cint.get("target")
                if isinstance(tdata, dict):
                    other_targets.append((int(tdata.get("x", getattr(blocker, "x", 0))), int(tdata.get("y", getattr(blocker, "y", 0)))))
            if (int(from_pos[0]), int(from_pos[1])) in other_targets:
                head_on = True
        if head_on:
            for bucket in buckets:
                self._movement_increment(bucket, "head_on_collision_events", 1)

        # Corridor congestion: no available adjacent walkable tile not occupied by another agent.
        walkable_neighbors = 0
        occupied_neighbors = 0
        fx, fy = int(from_pos[0]), int(from_pos[1])
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = fx + dx, fy + dy
            if not self.is_walkable(nx, ny):
                continue
            walkable_neighbors += 1
            occ = self._agent_at_tile(nx, ny, exclude_agent_id=str(getattr(agent, "agent_id", "")))
            if occ is not None:
                occupied_neighbors += 1
        if walkable_neighbors > 0 and occupied_neighbors >= walkable_neighbors:
            for bucket in buckets:
                self._movement_increment(bucket, "corridor_congestion_events", 1)

        from_context = self._resolve_movement_transport_context((int(from_pos[0]), int(from_pos[1])))
        if context == "road" or from_context == "road":
            for bucket in buckets:
                self._movement_increment(bucket, "road_congestion_events", 1)

        occupancy_count = self._count_agents_on_tile(int(to_pos[0]), int(to_pos[1]))
        self._record_movement_tile_hotspot(
            stats,
            (int(to_pos[0]), int(to_pos[1])),
            peak_occupancy=max(2, int(occupancy_count)),
            congestion_events=1,
        )

    def record_movement_path_recompute(self, agent: Agent, target: Optional[Coord]) -> None:
        stats = self.movement_diagnostic_stats
        if not isinstance(stats, dict):
            stats = _default_movement_diagnostic_stats()
            self.movement_diagnostic_stats = stats
        role = str(getattr(agent, "role", "npc"))
        task = str(getattr(agent, "task", "idle") or "idle")
        uid = str(self._resolve_agent_work_village_uid(agent) or "")
        aid = str(getattr(agent, "agent_id", ""))
        track = self._movement_track_for_agent(stats, aid, (int(getattr(agent, "x", 0)), int(getattr(agent, "y", 0))))
        context = self._resolve_movement_transport_context((int(getattr(agent, "x", 0)), int(getattr(agent, "y", 0))))
        buckets = self._movement_iter_buckets(
            stats,
            role=role if role in MOVEMENT_DIAGNOSTIC_ROLES else "other",
            task=task,
            context=context,
            village_uid=uid,
        )
        for bucket in buckets:
            self._movement_increment(bucket, "path_recompute_count", 1)
        if target is None:
            return
        new_target = (int(target[0]), int(target[1]))
        old_target = track.get("last_target")
        if isinstance(old_target, tuple) and len(old_target) == 2 and old_target != new_target:
            dist = abs(int(old_target[0]) - new_target[0]) + abs(int(old_target[1]) - new_target[1])
            for bucket in buckets:
                self._movement_increment(bucket, "target_changes_count", 1)
                if dist <= 2:
                    self._movement_increment(bucket, "same_area_retarget_count", 1)
        elif old_target is None:
            for bucket in buckets:
                self._movement_increment(bucket, "target_changes_count", 1)
        track["last_target"] = new_target
        track["last_target_tick"] = int(self.tick)

    def record_movement_tick(
        self,
        agent: Agent,
        *,
        from_pos: Tuple[int, int],
        to_pos: Tuple[int, int],
        target: Optional[Coord],
        action_was_move: bool,
    ) -> None:
        if not bool(action_was_move):
            return
        stats = self.movement_diagnostic_stats
        if not isinstance(stats, dict):
            stats = _default_movement_diagnostic_stats()
            self.movement_diagnostic_stats = stats
        role = str(getattr(agent, "role", "npc"))
        role_key = role if role in MOVEMENT_DIAGNOSTIC_ROLES else "other"
        task = str(getattr(agent, "task", "idle") or "idle")
        uid = str(self._resolve_agent_work_village_uid(agent) or "")
        context = self._resolve_movement_transport_context((int(to_pos[0]), int(to_pos[1])))
        buckets = self._movement_iter_buckets(stats, role=role_key, task=task, context=context, village_uid=uid)
        moved = (int(from_pos[0]), int(from_pos[1])) != (int(to_pos[0]), int(to_pos[1]))
        gross = abs(int(to_pos[0]) - int(from_pos[0])) + abs(int(to_pos[1]) - int(from_pos[1]))
        target_before = None
        target_after = None
        if isinstance(target, tuple) and len(target) == 2:
            tx, ty = int(target[0]), int(target[1])
            target_before = abs(tx - int(from_pos[0])) + abs(ty - int(from_pos[1]))
            target_after = abs(tx - int(to_pos[0])) + abs(ty - int(to_pos[1]))
        progress = 0
        no_progress = False
        near_target_indecision = False
        if target_before is not None and target_after is not None:
            progress = max(0, int(target_before) - int(target_after))
            no_progress = int(target_after) >= int(target_before)
            near_target_indecision = int(target_before) <= 2 and no_progress
        else:
            no_progress = not moved
        for bucket in buckets:
            self._movement_increment(bucket, "movement_ticks_total", 1)
            self._movement_increment(bucket, "gross_displacement", gross)
            self._movement_increment(bucket, "net_displacement", int(progress))
            if no_progress:
                self._movement_increment(bucket, "no_progress_ticks", 1)
            if near_target_indecision:
                self._movement_increment(bucket, "near_target_indecision_count", 1)

        aid = str(getattr(agent, "agent_id", ""))
        track = self._movement_track_for_agent(stats, aid, from_pos)
        prev_pos = track.get("prev_pos")
        if moved and isinstance(prev_pos, tuple) and len(prev_pos) == 2 and (
            int(to_pos[0]) == int(prev_pos[0]) and int(to_pos[1]) == int(prev_pos[1])
        ):
            for bucket in buckets:
                self._movement_increment(bucket, "backtrack_steps", 1)
                self._movement_increment(bucket, "oscillation_events", 1)
            track["oscillation_events"] = int(track.get("oscillation_events", 0)) + 1
        track["prev_pos"] = track.get("last_pos")
        track["last_pos"] = (int(to_pos[0]), int(to_pos[1]))

    def compute_movement_diagnostics_snapshot(self) -> Dict[str, Any]:
        stats = self.movement_diagnostic_stats if isinstance(self.movement_diagnostic_stats, dict) else _default_movement_diagnostic_stats()

        def _copy_bucket(src: Dict[str, Any]) -> Dict[str, Any]:
            out = _empty_movement_metrics()
            for key in (
                "movement_ticks_total",
                "no_progress_ticks",
                "oscillation_events",
                "backtrack_steps",
                "same_area_retarget_count",
                "target_changes_count",
                "path_recompute_count",
                "near_target_indecision_count",
                "net_displacement",
                "gross_displacement",
                "tile_occupancy_samples",
                "tile_occupancy_peak",
                "multi_agent_tile_events",
                "blocked_by_agent_count",
                "attempted_move_into_occupied_tile",
                "head_on_collision_events",
                "corridor_congestion_events",
                "near_target_blocked_by_agent",
                "road_tile_agent_samples",
                "road_tile_multi_agent_events",
                "road_congestion_events",
            ):
                out[key] = int(src.get(key, 0))
            gross = int(out.get("gross_displacement", 0))
            net = int(out.get("net_displacement", 0))
            out["movement_efficiency_ratio"] = round(float(net) / float(gross), 3) if gross > 0 else 0.0
            return out

        def _copy_congestion_bucket(src: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "tile_occupancy_samples": int(src.get("tile_occupancy_samples", 0)),
                "tile_occupancy_peak": int(src.get("tile_occupancy_peak", 0)),
                "multi_agent_tile_events": int(src.get("multi_agent_tile_events", 0)),
                "blocked_by_agent_count": int(src.get("blocked_by_agent_count", 0)),
                "attempted_move_into_occupied_tile": int(src.get("attempted_move_into_occupied_tile", 0)),
                "head_on_collision_events": int(src.get("head_on_collision_events", 0)),
                "corridor_congestion_events": int(src.get("corridor_congestion_events", 0)),
                "near_target_blocked_by_agent": int(src.get("near_target_blocked_by_agent", 0)),
                "road_tile_agent_samples": int(src.get("road_tile_agent_samples", 0)),
                "road_tile_multi_agent_events": int(src.get("road_tile_multi_agent_events", 0)),
                "road_congestion_events": int(src.get("road_congestion_events", 0)),
            }

        global_bucket = _copy_bucket(stats.get("global", {}))
        by_role = {str(k): _copy_bucket(v if isinstance(v, dict) else {}) for k, v in (stats.get("by_role", {}) or {}).items()}
        by_task = {str(k): _copy_bucket(v if isinstance(v, dict) else {}) for k, v in (stats.get("by_task", {}) or {}).items()}
        by_context = {
            str(k): _copy_bucket(v if isinstance(v, dict) else {})
            for k, v in (stats.get("by_transport_context", {}) or {}).items()
        }
        by_village: Dict[str, Any] = {}
        for uid, entry in (stats.get("by_village", {}) or {}).items():
            if not isinstance(entry, dict):
                continue
            by_village[str(uid)] = {
                "global": _copy_bucket(entry.get("global", {})),
                "by_role": {str(k): _copy_bucket(v if isinstance(v, dict) else {}) for k, v in (entry.get("by_role", {}) or {}).items()},
                "by_task": {str(k): _copy_bucket(v if isinstance(v, dict) else {}) for k, v in (entry.get("by_task", {}) or {}).items()},
                "by_transport_context": {
                    str(k): _copy_bucket(v if isinstance(v, dict) else {})
                    for k, v in (entry.get("by_transport_context", {}) or {}).items()
                },
            }

        top_oscillating_agents: List[Dict[str, Any]] = []
        for aid, track in (stats.get("agent_track", {}) or {}).items():
            if not isinstance(track, dict):
                continue
            count = int(track.get("oscillation_events", 0))
            if count <= 0:
                continue
            top_oscillating_agents.append({"agent_id": str(aid), "oscillation_events": count})
        top_oscillating_agents.sort(key=lambda item: (-int(item["oscillation_events"]), str(item["agent_id"])))

        top_congested_tiles: List[Dict[str, Any]] = []
        for _, entry in (stats.get("tile_hotspots", {}) or {}).items():
            if not isinstance(entry, dict):
                continue
            c = int(entry.get("congestion_events", 0))
            p = int(entry.get("peak_occupancy", 0))
            if c <= 0 and p <= 1:
                continue
            pos = entry.get("tile_position", {}) if isinstance(entry.get("tile_position"), dict) else {}
            top_congested_tiles.append(
                {
                    "tile_position": {"x": int(pos.get("x", 0)), "y": int(pos.get("y", 0))},
                    "congestion_events": c,
                    "peak_occupancy": p,
                }
            )
        top_congested_tiles.sort(
            key=lambda item: (
                -int(item.get("congestion_events", 0)),
                -int(item.get("peak_occupancy", 0)),
                int((item.get("tile_position", {}) or {}).get("x", 0)),
                int((item.get("tile_position", {}) or {}).get("y", 0)),
            )
        )

        return {
            "global": global_bucket,
            "by_role": dict(sorted(by_role.items(), key=lambda item: item[0])),
            "by_task": dict(sorted(by_task.items(), key=lambda item: item[0])),
            "by_transport_context": dict(sorted(by_context.items(), key=lambda item: item[0])),
            "by_village": dict(sorted(by_village.items(), key=lambda item: item[0])),
            "movement_congestion_global": _copy_congestion_bucket(global_bucket),
            "movement_congestion_by_role": {
                str(k): _copy_congestion_bucket(v if isinstance(v, dict) else {})
                for k, v in sorted(by_role.items(), key=lambda item: item[0])
            },
            "movement_congestion_by_task": {
                str(k): _copy_congestion_bucket(v if isinstance(v, dict) else {})
                for k, v in sorted(by_task.items(), key=lambda item: item[0])
            },
            "movement_congestion_by_transport_context": {
                str(k): _copy_congestion_bucket(v if isinstance(v, dict) else {})
                for k, v in sorted(by_context.items(), key=lambda item: item[0])
            },
            "top_congested_tiles": top_congested_tiles[:10],
            "top_oscillating_agents": top_oscillating_agents[:5],
        }

    def record_delivery_pipeline_stage(
        self,
        agent: Agent,
        stage: str,
        *,
        village_uid: Optional[str] = None,
        role: Optional[str] = None,
    ) -> None:
        stage_key = str(stage)
        if stage_key not in DELIVERY_DIAGNOSTIC_STAGES:
            return
        stats = self.delivery_diagnostic_stats
        if not isinstance(stats, dict):
            stats = _default_delivery_diagnostic_stats()
            self.delivery_diagnostic_stats = stats

        role_key = str(role or getattr(agent, "role", "npc") or "npc")
        uid = str(village_uid or self._resolve_agent_work_village_uid(agent) or "")

        global_entry = stats.setdefault("global", _empty_delivery_diagnostic_metrics())
        global_entry[stage_key] = int(global_entry.get(stage_key, 0)) + 1

        by_role = stats.setdefault("by_role", {})
        role_entry = by_role.get(role_key)
        if not isinstance(role_entry, dict):
            role_entry = _empty_delivery_diagnostic_metrics()
            by_role[role_key] = role_entry
        role_entry[stage_key] = int(role_entry.get(stage_key, 0)) + 1

        if uid:
            by_village = stats.setdefault("by_village", {})
            village_entry = by_village.get(uid)
            if not isinstance(village_entry, dict):
                village_entry = {
                    "global": _empty_delivery_diagnostic_metrics(),
                    "by_role": {},
                }
                by_village[uid] = village_entry
            vglobal = village_entry.setdefault("global", _empty_delivery_diagnostic_metrics())
            vglobal[stage_key] = int(vglobal.get(stage_key, 0)) + 1
            vby_role = village_entry.setdefault("by_role", {})
            vrole = vby_role.get(role_key)
            if not isinstance(vrole, dict):
                vrole = _empty_delivery_diagnostic_metrics()
                vby_role[role_key] = vrole
            vrole[stage_key] = int(vrole.get(stage_key, 0)) + 1

    def record_delivery_pipeline_failure(
        self,
        agent: Agent,
        reason: str,
        *,
        village_uid: Optional[str] = None,
        role: Optional[str] = None,
    ) -> None:
        reason_key = str(reason)
        if reason_key not in DELIVERY_DIAGNOSTIC_FAILURE_REASONS:
            reason_key = "unknown_failure"
        self.record_delivery_pipeline_stage(
            agent,
            "delivery_abandoned_count",
            village_uid=village_uid,
            role=role,
        )
        stats = self.delivery_diagnostic_stats
        if not isinstance(stats, dict):
            stats = _default_delivery_diagnostic_stats()
            self.delivery_diagnostic_stats = stats
        role_key = str(role or getattr(agent, "role", "npc") or "npc")
        uid = str(village_uid or self._resolve_agent_work_village_uid(agent) or "")

        global_entry = stats.setdefault("global", _empty_delivery_diagnostic_metrics())
        greasons = global_entry.setdefault("delivery_failure_reasons", {})
        greasons[reason_key] = int(greasons.get(reason_key, 0)) + 1

        by_role = stats.setdefault("by_role", {})
        role_entry = by_role.get(role_key)
        if not isinstance(role_entry, dict):
            role_entry = _empty_delivery_diagnostic_metrics()
            by_role[role_key] = role_entry
        rreasons = role_entry.setdefault("delivery_failure_reasons", {})
        rreasons[reason_key] = int(rreasons.get(reason_key, 0)) + 1

        if uid:
            by_village = stats.setdefault("by_village", {})
            village_entry = by_village.get(uid)
            if not isinstance(village_entry, dict):
                village_entry = {"global": _empty_delivery_diagnostic_metrics(), "by_role": {}}
                by_village[uid] = village_entry
            vglobal = village_entry.setdefault("global", _empty_delivery_diagnostic_metrics())
            vgreasons = vglobal.setdefault("delivery_failure_reasons", {})
            vgreasons[reason_key] = int(vgreasons.get(reason_key, 0)) + 1
            vby_role = village_entry.setdefault("by_role", {})
            vrole = vby_role.get(role_key)
            if not isinstance(vrole, dict):
                vrole = _empty_delivery_diagnostic_metrics()
                vby_role[role_key] = vrole
            vreasons = vrole.setdefault("delivery_failure_reasons", {})
            vreasons[reason_key] = int(vreasons.get(reason_key, 0)) + 1

    def compute_delivery_diagnostics_snapshot(self) -> Dict[str, Any]:
        stats = self.delivery_diagnostic_stats if isinstance(self.delivery_diagnostic_stats, dict) else _default_delivery_diagnostic_stats()

        def _copy(src: Dict[str, Any]) -> Dict[str, Any]:
            out = _empty_delivery_diagnostic_metrics()
            for stage in DELIVERY_DIAGNOSTIC_STAGES:
                out[stage] = int(src.get(stage, 0))
            out["delivery_failure_reasons"] = {
                str(k): int(v) for k, v in ((src.get("delivery_failure_reasons", {}) or {}).items())
            }
            return out

        global_out = _copy(stats.get("global", {}) if isinstance(stats.get("global", {}), dict) else {})
        by_role = {
            str(role): _copy(entry if isinstance(entry, dict) else {})
            for role, entry in (stats.get("by_role", {}) or {}).items()
        }
        by_village: Dict[str, Any] = {}
        for uid, entry in (stats.get("by_village", {}) or {}).items():
            if not isinstance(entry, dict):
                continue
            by_village[str(uid)] = {
                "global": _copy(entry.get("global", {}) if isinstance(entry.get("global", {}), dict) else {}),
                "by_role": {
                    str(role): _copy(rentry if isinstance(rentry, dict) else {})
                    for role, rentry in (entry.get("by_role", {}) or {}).items()
                },
            }
        return {
            "global": global_out,
            "by_role": dict(sorted(by_role.items(), key=lambda item: item[0])),
            "by_village": dict(sorted(by_village.items(), key=lambda item: item[0])),
        }

    def _resolve_building_village_uid(self, building: Dict[str, Any]) -> str:
        if not isinstance(building, dict):
            return ""
        uid = str(building.get("village_uid", "") or "")
        if uid:
            return uid
        vid = building.get("village_id")
        if vid is not None:
            resolved = self.resolve_village_uid(vid)
            if resolved is not None:
                return str(resolved)
        return ""

    def _housing_construction_entry(self, village_uid: Optional[str] = None) -> Dict[str, Any]:
        stats = self.housing_construction_stats
        if not isinstance(stats, dict):
            stats = _default_housing_construction_stats()
            self.housing_construction_stats = stats
        uid = str(village_uid or "")
        if uid:
            by_village = stats.setdefault("by_village", {})
            entry = by_village.get(uid)
            if not isinstance(entry, dict):
                entry = _empty_housing_construction_metrics()
                by_village[uid] = entry
            return entry
        entry = stats.get("global")
        if not isinstance(entry, dict):
            entry = _empty_housing_construction_metrics()
            stats["global"] = entry
        return entry

    def _record_house_construction_duration(
        self,
        building_id: Optional[str],
        *,
        village_uid: Optional[str] = None,
    ) -> None:
        bid = str(building_id or "")
        if not bid:
            return
        stats = self.housing_construction_stats
        if not isinstance(stats, dict):
            stats = _default_housing_construction_stats()
            self.housing_construction_stats = stats
        completed_ids = stats.setdefault("_house_completed_ids", set())
        if not isinstance(completed_ids, set):
            completed_ids = set()
            stats["_house_completed_ids"] = completed_ids
        if bid in completed_ids:
            return
        start_map = stats.setdefault("_house_start_tick_by_id", {})
        if not isinstance(start_map, dict):
            start_map = {}
            stats["_house_start_tick_by_id"] = start_map
        started = start_map.get(bid)
        if started is None:
            return
        try:
            duration = max(0, int(self.tick) - int(started))
        except Exception:
            return
        completed_ids.add(bid)
        durations_global = stats.setdefault("_durations_global", [])
        if not isinstance(durations_global, list):
            durations_global = []
            stats["_durations_global"] = durations_global
        durations_global.append(duration)
        uid = str(village_uid or "")
        if uid:
            by_v = stats.setdefault("_durations_by_village", {})
            if not isinstance(by_v, dict):
                by_v = {}
                stats["_durations_by_village"] = by_v
            lst = by_v.get(uid)
            if not isinstance(lst, list):
                lst = []
                by_v[uid] = lst
            lst.append(duration)

    def record_housing_construction_stage(
        self,
        stage: str,
        *,
        village_uid: Optional[str] = None,
        building_id: Optional[str] = None,
    ) -> None:
        key = str(stage).strip()
        if key not in HOUSING_CONSTRUCTION_STAGES:
            return
        g = self._housing_construction_entry(None)
        g[key] = int(g.get(key, 0)) + 1
        uid = str(village_uid or "")
        if uid:
            v = self._housing_construction_entry(uid)
            v[key] = int(v.get(key, 0)) + 1

        stats = self.housing_construction_stats
        if not isinstance(stats, dict):
            stats = _default_housing_construction_stats()
            self.housing_construction_stats = stats
        bid = str(building_id or "")
        if key == "house_site_created" and bid:
            start_map = stats.setdefault("_house_start_tick_by_id", {})
            if not isinstance(start_map, dict):
                start_map = {}
                stats["_house_start_tick_by_id"] = start_map
            start_map.setdefault(bid, int(self.tick))
        if key == "house_construction_completed":
            self._record_house_construction_duration(bid, village_uid=uid or None)

    def record_housing_construction_failure(
        self,
        reason: str,
        *,
        village_uid: Optional[str] = None,
    ) -> None:
        key = str(reason).strip().lower() or "site_invalidated"
        if key not in HOUSING_CONSTRUCTION_FAILURE_REASONS:
            key = "site_invalidated"
        g = self._housing_construction_entry(None)
        greasons = g.setdefault("failure_reasons", {})
        greasons[key] = int(greasons.get(key, 0)) + 1
        uid = str(village_uid or "")
        if uid:
            v = self._housing_construction_entry(uid)
            vreasons = v.setdefault("failure_reasons", {})
            vreasons[key] = int(vreasons.get(key, 0)) + 1

    def record_housing_worker_participation(
        self,
        event: str,
        *,
        village_uid: Optional[str] = None,
    ) -> None:
        key = str(event).strip()
        if key not in HOUSING_WORKER_PARTICIPATION_KEYS:
            return
        g = self._housing_construction_entry(None)
        gw = g.setdefault("worker_participation", {})
        gw[key] = int(gw.get(key, 0)) + 1
        uid = str(village_uid or "")
        if uid:
            v = self._housing_construction_entry(uid)
            vw = v.setdefault("worker_participation", {})
            vw[key] = int(vw.get(key, 0)) + 1

    def compute_housing_construction_diagnostics_snapshot(self) -> Dict[str, Any]:
        stats = self.housing_construction_stats if isinstance(self.housing_construction_stats, dict) else _default_housing_construction_stats()

        counts_under: Dict[str, int] = {}
        counts_active: Dict[str, int] = {}
        for building in getattr(self, "buildings", {}).values():
            if not isinstance(building, dict):
                continue
            if str(building.get("type", "")) != "house":
                continue
            uid = self._resolve_building_village_uid(building)
            state = str(building.get("operational_state", ""))
            if state == "under_construction":
                counts_under[uid] = int(counts_under.get(uid, 0)) + 1
            elif state == "active":
                counts_active[uid] = int(counts_active.get(uid, 0)) + 1

        durations_global = stats.get("_durations_global", [])
        if not isinstance(durations_global, list):
            durations_global = []
        completed_ids = stats.get("_house_completed_ids", set())
        if not isinstance(completed_ids, set):
            completed_ids = set()

        def _copy_entry(src: Dict[str, Any], uid: str = "") -> Dict[str, Any]:
            out = _empty_housing_construction_metrics()
            for stage in HOUSING_CONSTRUCTION_STAGES:
                out[stage] = int(src.get(stage, 0))
            out["failure_reasons"] = {
                str(k): int(v) for k, v in ((src.get("failure_reasons", {}) or {}).items())
            }
            src_worker = src.get("worker_participation", {}) if isinstance(src.get("worker_participation", {}), dict) else {}
            out["worker_participation"] = {
                key: int(src_worker.get(key, 0)) for key in HOUSING_WORKER_PARTICIPATION_KEYS
            }
            out["houses_under_construction_count"] = int(counts_under.get(uid, 0)) if uid else int(sum(counts_under.values()))
            out["houses_active_count"] = int(counts_active.get(uid, 0)) if uid else int(sum(counts_active.values()))
            completed_from_stage = int(src.get("house_construction_completed", 0))
            if uid:
                by_v_durations = stats.get("_durations_by_village", {})
                durations = by_v_durations.get(uid, []) if isinstance(by_v_durations, dict) else []
                if not isinstance(durations, list):
                    durations = []
                out["houses_completed_count"] = max(len(durations), completed_from_stage)
                out["average_house_construction_time"] = round(float(sum(durations)) / float(len(durations)), 3) if durations else 0.0
                out["max_house_construction_time"] = max([int(d) for d in durations], default=0)
            else:
                out["houses_completed_count"] = max(len(completed_ids), completed_from_stage)
                out["average_house_construction_time"] = round(float(sum(durations_global)) / float(len(durations_global)), 3) if durations_global else 0.0
                out["max_house_construction_time"] = max([int(d) for d in durations_global], default=0)
            return out

        global_out = _copy_entry(stats.get("global", {}) if isinstance(stats.get("global", {}), dict) else {})
        by_village: Dict[str, Dict[str, Any]] = {}
        for uid, entry in (stats.get("by_village", {}) or {}).items():
            if not isinstance(entry, dict):
                continue
            suid = str(uid)
            by_village[suid] = _copy_entry(entry, uid=suid)
        return {
            "global": global_out,
            "by_village": dict(sorted(by_village.items(), key=lambda item: item[0])),
        }

    def _housing_siting_entry(self, village_uid: Optional[str] = None) -> Dict[str, Any]:
        stats = self.housing_siting_stats
        if not isinstance(stats, dict):
            stats = _default_housing_siting_stats()
            self.housing_siting_stats = stats
        uid = str(village_uid or "")
        if uid:
            by_village = stats.setdefault("by_village", {})
            entry = by_village.get(uid)
            if not isinstance(entry, dict):
                entry = _empty_housing_siting_metrics()
                by_village[uid] = entry
            return entry
        entry = stats.get("global")
        if not isinstance(entry, dict):
            entry = _empty_housing_siting_metrics()
            stats["global"] = entry
        return entry

    def record_housing_siting_stage(self, stage: str, *, village_uid: Optional[str] = None) -> None:
        key = str(stage).strip()
        if key not in HOUSING_SITING_SEARCH_STAGES:
            return
        g = self._housing_siting_entry(None)
        g[key] = int(g.get(key, 0)) + 1
        uid = str(village_uid or "")
        if uid:
            v = self._housing_siting_entry(uid)
            v[key] = int(v.get(key, 0)) + 1

    def record_housing_siting_rejection_reason(self, reason: str, *, village_uid: Optional[str] = None) -> None:
        key = str(reason).strip().lower() or "other_guard"
        if key not in HOUSING_SITING_REJECTION_REASONS:
            key = "other_guard"
        g = self._housing_siting_entry(None)
        greasons = g.setdefault("rejection_reasons", {})
        greasons[key] = int(greasons.get(key, 0)) + 1
        uid = str(village_uid or "")
        if uid:
            v = self._housing_siting_entry(uid)
            vreasons = v.setdefault("rejection_reasons", {})
            vreasons[key] = int(vreasons.get(key, 0)) + 1

    def compute_housing_siting_rejection_snapshot(self) -> Dict[str, Any]:
        stats = self.housing_siting_stats if isinstance(self.housing_siting_stats, dict) else _default_housing_siting_stats()

        def _copy(src: Dict[str, Any]) -> Dict[str, Any]:
            out = _empty_housing_siting_metrics()
            for stage in HOUSING_SITING_SEARCH_STAGES:
                out[stage] = int(src.get(stage, 0))
            out["rejection_reasons"] = {
                str(k): int(v) for k, v in ((src.get("rejection_reasons", {}) or {}).items())
            }
            return out

        global_out = _copy(stats.get("global", {}) if isinstance(stats.get("global", {}), dict) else {})
        by_village: Dict[str, Dict[str, Any]] = {}
        for uid, entry in (stats.get("by_village", {}) or {}).items():
            if not isinstance(entry, dict):
                continue
            by_village[str(uid)] = _copy(entry)
        return {
            "global": global_out,
            "by_village": dict(sorted(by_village.items(), key=lambda item: item[0])),
        }

    def _housing_path_entry(self, village_uid: Optional[str] = None) -> Dict[str, Any]:
        stats = self.housing_path_coherence_stats
        if not isinstance(stats, dict):
            stats = _default_housing_path_coherence_stats()
            self.housing_path_coherence_stats = stats
        uid = str(village_uid or "")
        if uid:
            by_village = stats.setdefault("by_village", {})
            entry = by_village.get(uid)
            if not isinstance(entry, dict):
                entry = _empty_housing_path_coherence_metrics()
                by_village[uid] = entry
            return entry
        entry = stats.get("global")
        if not isinstance(entry, dict):
            entry = _empty_housing_path_coherence_metrics()
            stats["global"] = entry
        return entry

    def record_housing_path_coherence(self, key: str, *, village_uid: Optional[str] = None) -> None:
        metric = str(key).strip()
        if metric not in HOUSING_PATH_COHERENCE_KEYS:
            return
        g = self._housing_path_entry(None)
        g[metric] = int(g.get(metric, 0)) + 1
        uid = str(village_uid or "")
        if uid:
            v = self._housing_path_entry(uid)
            v[metric] = int(v.get(metric, 0)) + 1

    def compute_housing_path_coherence_snapshot(self) -> Dict[str, Any]:
        stats = self.housing_path_coherence_stats if isinstance(self.housing_path_coherence_stats, dict) else _default_housing_path_coherence_stats()

        def _copy(src: Dict[str, Any]) -> Dict[str, Any]:
            out = _empty_housing_path_coherence_metrics()
            for key in HOUSING_PATH_COHERENCE_KEYS:
                out[key] = int(src.get(key, 0))
            return out

        global_out = _copy(stats.get("global", {}) if isinstance(stats.get("global", {}), dict) else {})
        by_village: Dict[str, Dict[str, Any]] = {}
        for uid, entry in (stats.get("by_village", {}) or {}).items():
            if not isinstance(entry, dict):
                continue
            by_village[str(uid)] = _copy(entry)

        # Infer unknown activation path as active houses not explicitly accounted.
        if int(global_out.get("house_path_unknown", 0)) == 0:
            active_houses = 0
            for building in getattr(self, "buildings", {}).values():
                if (
                    isinstance(building, dict)
                    and str(building.get("type", "")) == "house"
                    and str(building.get("operational_state", "")) == "active"
                ):
                    active_houses += 1
            known = int(global_out.get("house_activated_via_completion_hook", 0)) + int(global_out.get("house_activated_via_direct_path", 0))
            global_out["house_path_unknown"] = max(0, int(active_houses) - int(known))
        return {
            "global": global_out,
            "by_village": dict(sorted(by_village.items(), key=lambda item: item[0])),
        }

    def record_builder_self_supply_attempt(self) -> None:
        stats = self.builder_self_supply_stats
        if not isinstance(stats, dict):
            stats = _default_builder_self_supply_stats()
            self.builder_self_supply_stats = stats
        stats["attempt_count"] = int(stats.get("attempt_count", 0)) + 1

    def record_builder_self_supply_success(self, distance: int) -> None:
        stats = self.builder_self_supply_stats
        if not isinstance(stats, dict):
            stats = _default_builder_self_supply_stats()
            self.builder_self_supply_stats = stats
        stats["success_count"] = int(stats.get("success_count", 0)) + 1
        stats["distance_total"] = int(stats.get("distance_total", 0)) + max(0, int(distance))
        stats["distance_samples"] = int(stats.get("distance_samples", 0)) + 1

    def record_builder_self_supply_failure(self, reason: str) -> None:
        stats = self.builder_self_supply_stats
        if not isinstance(stats, dict):
            stats = _default_builder_self_supply_stats()
            self.builder_self_supply_stats = stats
        key = str(reason).strip().lower() or "unknown_failure"
        reasons = stats.setdefault("failure_reasons", {})
        reasons[key] = int(reasons.get(key, 0)) + 1

    def compute_builder_self_supply_snapshot(self) -> Dict[str, Any]:
        stats = self.builder_self_supply_stats if isinstance(self.builder_self_supply_stats, dict) else _default_builder_self_supply_stats()
        samples = int(stats.get("distance_samples", 0))
        total = int(stats.get("distance_total", 0))
        avg = round(float(total) / float(samples), 3) if samples > 0 else 0.0
        return {
            "builder_self_supply_attempt_count": int(stats.get("attempt_count", 0)),
            "builder_self_supply_success_count": int(stats.get("success_count", 0)),
            "builder_self_supply_failure_reasons": {
                str(k): int(v) for k, v in ((stats.get("failure_reasons", {}) or {}).items())
            },
            "builder_self_supply_distance_avg": avg,
        }

    def _builder_self_supply_gate_entry(self, village_uid: Optional[str] = None) -> Dict[str, Any]:
        stats = self.builder_self_supply_gate_stats
        if not isinstance(stats, dict):
            stats = _default_builder_self_supply_gate_stats()
            self.builder_self_supply_gate_stats = stats
        uid = str(village_uid or "")
        if uid:
            by_village = stats.setdefault("by_village", {})
            entry = by_village.get(uid)
            if not isinstance(entry, dict):
                entry = _empty_builder_self_supply_gate_metrics()
                by_village[uid] = entry
            return entry
        entry = stats.get("global")
        if not isinstance(entry, dict):
            entry = _empty_builder_self_supply_gate_metrics()
            stats["global"] = entry
        return entry

    def record_builder_self_supply_gate_stage(self, stage: str, *, village_uid: Optional[str] = None) -> None:
        key = str(stage).strip()
        if key not in BUILDER_SELF_SUPPLY_GATE_STAGES:
            return
        g = self._builder_self_supply_gate_entry(None)
        g[key] = int(g.get(key, 0)) + 1
        uid = str(village_uid or "")
        if uid:
            v = self._builder_self_supply_gate_entry(uid)
            v[key] = int(v.get(key, 0)) + 1

    def record_builder_self_supply_gate_failure(self, reason: str, *, village_uid: Optional[str] = None) -> None:
        key = str(reason).strip().lower() or "unknown_failure"
        if key not in BUILDER_SELF_SUPPLY_GATE_REASONS:
            key = "unknown_failure"
        g = self._builder_self_supply_gate_entry(None)
        greasons = g.setdefault("failure_reasons", {})
        greasons[key] = int(greasons.get(key, 0)) + 1
        if key == "self_supply_succeeded":
            g["success_count"] = int(g.get("success_count", 0)) + 1
        uid = str(village_uid or "")
        if uid:
            v = self._builder_self_supply_gate_entry(uid)
            vreasons = v.setdefault("failure_reasons", {})
            vreasons[key] = int(vreasons.get(key, 0)) + 1
            if key == "self_supply_succeeded":
                v["success_count"] = int(v.get("success_count", 0)) + 1

    def compute_builder_self_supply_gate_snapshot(self) -> Dict[str, Any]:
        stats = self.builder_self_supply_gate_stats if isinstance(self.builder_self_supply_gate_stats, dict) else _default_builder_self_supply_gate_stats()

        def _copy(src: Dict[str, Any]) -> Dict[str, Any]:
            out = _empty_builder_self_supply_gate_metrics()
            for stage in BUILDER_SELF_SUPPLY_GATE_STAGES:
                out[stage] = int(src.get(stage, 0))
            out["success_count"] = int(src.get("success_count", 0))
            out["failure_reasons"] = {
                str(k): int(v) for k, v in ((src.get("failure_reasons", {}) or {}).items())
            }
            return out

        global_out = _copy(stats.get("global", {}) if isinstance(stats.get("global", {}), dict) else {})
        by_village: Dict[str, Dict[str, Any]] = {}
        for uid, entry in (stats.get("by_village", {}) or {}).items():
            if not isinstance(entry, dict):
                continue
            by_village[str(uid)] = _copy(entry)
        return {
            "global": global_out,
            "by_village": dict(sorted(by_village.items(), key=lambda item: item[0])),
        }

    def _next_proto_community_id(self) -> str:
        self._proto_community_counter = int(getattr(self, "_proto_community_counter", 0)) + 1
        return f"pc-{self._proto_community_counter:06d}"

    def _region_key_for_pos(self, x: int, y: int) -> str:
        best_uid = ""
        best_dist = 10**9
        for village in getattr(self, "villages", []):
            if not isinstance(village, dict):
                continue
            center = village.get("center", {}) if isinstance(village.get("center"), dict) else {}
            vx = int(center.get("x", x))
            vy = int(center.get("y", y))
            dist = abs(int(x) - vx) + abs(int(y) - vy)
            if dist < best_dist and dist <= 18:
                best_dist = dist
                best_uid = str(village.get("village_uid", "") or "")
        return best_uid or "unaffiliated_region"

    def _proto_funnel_entry(self, region: Optional[str] = None) -> Dict[str, Any]:
        stats = self.proto_community_funnel_stats
        if not isinstance(stats, dict):
            stats = _default_proto_funnel_stats()
            self.proto_community_funnel_stats = stats
        key = str(region or "")
        if key:
            by_region = stats.setdefault("by_region", {})
            entry = by_region.get(key)
            if not isinstance(entry, dict):
                entry = _empty_proto_funnel_metrics()
                by_region[key] = entry
            return entry
        global_entry = stats.get("global")
        if not isinstance(global_entry, dict):
            global_entry = _empty_proto_funnel_metrics()
            stats["global"] = global_entry
        return global_entry

    def record_proto_funnel_stage(self, stage: str, *, region: Optional[str] = None) -> None:
        key = str(stage).strip()
        if key not in PROTO_COMMUNITY_FUNNEL_STAGES:
            return
        g = self._proto_funnel_entry(None)
        g[key] = int(g.get(key, 0)) + 1
        if region:
            r = self._proto_funnel_entry(region)
            r[key] = int(r.get(key, 0)) + 1

    def record_proto_funnel_failure(self, reason: str, *, region: Optional[str] = None) -> None:
        key = str(reason).strip().lower() or "other_guard"
        if key not in PROTO_COMMUNITY_FUNNEL_FAILURE_REASONS:
            key = "other_guard"
        g = self._proto_funnel_entry(None)
        greasons = g.setdefault("failure_reasons", {})
        greasons[key] = int(greasons.get(key, 0)) + 1
        if region:
            r = self._proto_funnel_entry(region)
            rreasons = r.setdefault("failure_reasons", {})
            rreasons[key] = int(rreasons.get(key, 0)) + 1

    def compute_proto_community_funnel_snapshot(self) -> Dict[str, Any]:
        stats = self.proto_community_funnel_stats if isinstance(self.proto_community_funnel_stats, dict) else _default_proto_funnel_stats()

        def _copy(src: Dict[str, Any]) -> Dict[str, Any]:
            out = _empty_proto_funnel_metrics()
            for s in PROTO_COMMUNITY_FUNNEL_STAGES:
                out[s] = int(src.get(s, 0))
            out["failure_reasons"] = {str(k): int(v) for k, v in ((src.get("failure_reasons", {}) or {}).items())}
            return out

        global_out = _copy(stats.get("global", {}) if isinstance(stats.get("global", {}), dict) else {})
        by_region: Dict[str, Dict[str, Any]] = {}
        for region, entry in (stats.get("by_region", {}) or {}).items():
            if isinstance(entry, dict):
                by_region[str(region)] = _copy(entry)
        return {
            "global": global_out,
            "by_region": dict(sorted(by_region.items(), key=lambda item: item[0])),
        }

    def _camp_lifecycle_entry(self, region: Optional[str] = None) -> Dict[str, Any]:
        stats = self.camp_lifecycle_stats
        if not isinstance(stats, dict):
            stats = _default_camp_lifecycle_stats()
            self.camp_lifecycle_stats = stats
        key = str(region or "")
        if key:
            by_region = stats.setdefault("by_region", {})
            entry = by_region.get(key)
            if not isinstance(entry, dict):
                entry = _empty_camp_lifecycle_metrics()
                by_region[key] = entry
            return entry
        global_entry = stats.get("global")
        if not isinstance(global_entry, dict):
            global_entry = _empty_camp_lifecycle_metrics()
            stats["global"] = global_entry
        return global_entry

    def record_camp_lifecycle_stage(self, stage: str, *, region: Optional[str] = None) -> None:
        key = str(stage).strip()
        if key not in CAMP_LIFECYCLE_STAGES:
            return
        g = self._camp_lifecycle_entry(None)
        g[key] = int(g.get(key, 0)) + 1
        if region:
            r = self._camp_lifecycle_entry(region)
            r[key] = int(r.get(key, 0)) + 1

    def record_camp_deactivation_reason(self, reason: str, *, region: Optional[str] = None) -> None:
        key = str(reason).strip().lower() or "other_guard"
        if key not in CAMP_LIFECYCLE_DEACTIVATION_REASONS:
            key = "other_guard"
        g = self._camp_lifecycle_entry(None)
        greasons = g.setdefault("deactivation_reasons", {})
        greasons[key] = int(greasons.get(key, 0)) + 1
        if region:
            r = self._camp_lifecycle_entry(region)
            rreasons = r.setdefault("deactivation_reasons", {})
            rreasons[key] = int(rreasons.get(key, 0)) + 1

    def record_camp_retention_reason(self, reason: str, *, region: Optional[str] = None) -> None:
        key = str(reason).strip().lower() or "recent_use"
        if key not in CAMP_LIFECYCLE_RETENTION_REASONS:
            key = "recent_use"
        g = self._camp_lifecycle_entry(None)
        greasons = g.setdefault("retention_reasons", {})
        greasons[key] = int(greasons.get(key, 0)) + 1
        if region:
            r = self._camp_lifecycle_entry(region)
            rreasons = r.setdefault("retention_reasons", {})
            rreasons[key] = int(rreasons.get(key, 0)) + 1

    def record_camp_deactivation_support_snapshot(self, *, region: Optional[str] = None, support: Optional[Dict[str, Any]] = None) -> None:
        snap = support if isinstance(support, dict) else {}

        def _apply(entry: Dict[str, Any]) -> None:
            if bool(snap.get("has_food_buffer", False)):
                entry["deactivation_with_food_cache_count"] = int(entry.get("deactivation_with_food_cache_count", 0)) + 1
            if bool(snap.get("recent_use", False)):
                entry["deactivation_with_recent_use_count"] = int(entry.get("deactivation_with_recent_use_count", 0)) + 1
            if int(snap.get("anchor_agents", 0)) > 0:
                entry["deactivation_with_anchor_support_count"] = int(entry.get("deactivation_with_anchor_support_count", 0)) + 1
            if int(snap.get("nearby_agents", 0)) > 0:
                entry["deactivation_with_nearby_agents_count"] = int(entry.get("deactivation_with_nearby_agents_count", 0)) + 1

        g = self._camp_lifecycle_entry(None)
        _apply(g)
        if region:
            r = self._camp_lifecycle_entry(region)
            _apply(r)

    def compute_camp_lifecycle_snapshot(self) -> Dict[str, Any]:
        stats = self.camp_lifecycle_stats if isinstance(self.camp_lifecycle_stats, dict) else _default_camp_lifecycle_stats()

        def _copy(src: Dict[str, Any]) -> Dict[str, Any]:
            out = _empty_camp_lifecycle_metrics()
            for s in CAMP_LIFECYCLE_STAGES:
                out[s] = int(src.get(s, 0))
            out["deactivation_reasons"] = {str(k): int(v) for k, v in ((src.get("deactivation_reasons", {}) or {}).items())}
            out["retention_reasons"] = {str(k): int(v) for k, v in ((src.get("retention_reasons", {}) or {}).items())}
            out["deactivation_with_food_cache_count"] = int(src.get("deactivation_with_food_cache_count", 0))
            out["deactivation_with_recent_use_count"] = int(src.get("deactivation_with_recent_use_count", 0))
            out["deactivation_with_anchor_support_count"] = int(src.get("deactivation_with_anchor_support_count", 0))
            out["deactivation_with_nearby_agents_count"] = int(src.get("deactivation_with_nearby_agents_count", 0))
            return out

        global_out = _copy(stats.get("global", {}) if isinstance(stats.get("global", {}), dict) else {})
        by_region: Dict[str, Dict[str, Any]] = {}
        for region, entry in (stats.get("by_region", {}) or {}).items():
            if isinstance(entry, dict):
                by_region[str(region)] = _copy(entry)
        return {
            "global": global_out,
            "by_region": dict(sorted(by_region.items(), key=lambda item: item[0])),
        }

    def _camp_targeting_entry(self, region: Optional[str] = None) -> Dict[str, Any]:
        stats = self.camp_targeting_stats
        if not isinstance(stats, dict):
            stats = _default_camp_targeting_stats()
            self.camp_targeting_stats = stats
        key = str(region or "")
        if key:
            by_region = stats.setdefault("by_region", {})
            entry = by_region.get(key)
            if not isinstance(entry, dict):
                entry = _empty_camp_targeting_metrics()
                by_region[key] = entry
            return entry
        global_entry = stats.get("global")
        if not isinstance(global_entry, dict):
            global_entry = _empty_camp_targeting_metrics()
            stats["global"] = global_entry
        return global_entry

    def record_camp_targeting(self, stage: str, *, region: Optional[str] = None) -> None:
        key = str(stage).strip()
        if key not in CAMP_TARGETING_STAGES:
            return
        g = self._camp_targeting_entry(None)
        g[key] = int(g.get(key, 0)) + 1
        if region:
            r = self._camp_targeting_entry(region)
            r[key] = int(r.get(key, 0)) + 1

    def record_camp_not_chosen_reason(self, reason: str, *, region: Optional[str] = None) -> None:
        key = str(reason).strip().lower() or "other_guard"
        if key not in CAMP_TARGETING_REASONS:
            key = "other_guard"
        g = self._camp_targeting_entry(None)
        reasons = g.setdefault("camp_not_chosen_reasons", {})
        reasons[key] = int(reasons.get(key, 0)) + 1
        if region:
            r = self._camp_targeting_entry(region)
            rreasons = r.setdefault("camp_not_chosen_reasons", {})
            rreasons[key] = int(rreasons.get(key, 0)) + 1

    def compute_camp_targeting_snapshot(self) -> Dict[str, Any]:
        stats = self.camp_targeting_stats if isinstance(self.camp_targeting_stats, dict) else _default_camp_targeting_stats()

        def _copy(src: Dict[str, Any]) -> Dict[str, Any]:
            out = _empty_camp_targeting_metrics()
            for s in CAMP_TARGETING_STAGES:
                out[s] = int(src.get(s, 0))
            out["camp_not_chosen_reasons"] = {
                str(k): int(v) for k, v in ((src.get("camp_not_chosen_reasons", {}) or {}).items())
            }
            return out

        global_out = _copy(stats.get("global", {}) if isinstance(stats.get("global", {}), dict) else {})
        by_region: Dict[str, Dict[str, Any]] = {}
        for region, entry in (stats.get("by_region", {}) or {}).items():
            if isinstance(entry, dict):
                by_region[str(region)] = _copy(entry)
        return {
            "global": global_out,
            "by_region": dict(sorted(by_region.items(), key=lambda item: item[0])),
        }

    def _next_camp_id(self) -> str:
        self._camp_counter = int(getattr(self, "_camp_counter", 0)) + 1
        return f"camp-{self._camp_counter:06d}"

    def _camp_viable_walkable_pos(self, x: int, y: int) -> Optional[Coord]:
        origin = (int(x), int(y))
        for radius in range(0, 3):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if abs(dx) + abs(dy) != radius:
                        continue
                    nx, ny = origin[0] + dx, origin[1] + dy
                    if not (0 <= nx < self.width and 0 <= ny < self.height):
                        continue
                    if not self.is_walkable(nx, ny):
                        continue
                    if self.is_tile_blocked_by_building(nx, ny):
                        continue
                    return (nx, ny)
        return None

    def _agents_components_for_proto(self) -> List[List[Agent]]:
        alive = sorted(
            [a for a in self.agents if getattr(a, "alive", False)],
            key=lambda a: str(getattr(a, "agent_id", "")),
        )
        components: List[List[Agent]] = []
        visited: Set[str] = set()
        for agent in alive:
            aid = str(getattr(agent, "agent_id", ""))
            if aid in visited:
                continue
            stack = [agent]
            cluster: List[Agent] = []
            while stack:
                cur = stack.pop()
                cid = str(getattr(cur, "agent_id", ""))
                if cid in visited:
                    continue
                visited.add(cid)
                cluster.append(cur)
                for other in alive:
                    oid = str(getattr(other, "agent_id", ""))
                    if oid in visited:
                        continue
                    if abs(int(cur.x) - int(other.x)) + abs(int(cur.y) - int(other.y)) <= PROTO_COMMUNITY_RADIUS:
                        stack.append(other)
            components.append(sorted(cluster, key=lambda a: str(getattr(a, "agent_id", ""))))
        components.sort(
            key=lambda c: (
                -len(c),
                round(sum(int(a.x) for a in c) / float(max(1, len(c)))),
                round(sum(int(a.y) for a in c) / float(max(1, len(c)))),
            )
        )
        return components

    def _agents_clustered_for_proto(self) -> List[List[Agent]]:
        components = self._agents_components_for_proto()
        clusters: List[List[Agent]] = [c for c in components if len(c) >= PROTO_COMMUNITY_MIN_AGENTS]
        return clusters

    def _cluster_center(self, cluster: List[Agent]) -> Coord:
        cx = int(round(sum(int(a.x) for a in cluster) / float(max(1, len(cluster)))))
        cy = int(round(sum(int(a.y) for a in cluster) / float(max(1, len(cluster)))))
        return (cx, cy)

    def _cluster_true_survival_crisis(self, cluster: List[Agent]) -> bool:
        if not cluster:
            return True
        avg_hunger = sum(float(getattr(a, "hunger", 0.0)) for a in cluster) / float(max(1, len(cluster)))
        min_hunger = min(float(getattr(a, "hunger", 0.0)) for a in cluster)
        return bool(avg_hunger < 12.0 or min_hunger < 8.0)

    def _resolve_camp_village_uid(self, x: int, y: int) -> str:
        best_uid = ""
        best_dist = 10**9
        for village in getattr(self, "villages", []):
            if not isinstance(village, dict):
                continue
            center = village.get("center", {}) if isinstance(village.get("center"), dict) else {}
            vx = int(center.get("x", x))
            vy = int(center.get("y", y))
            d = abs(int(x) - vx) + abs(int(y) - vy)
            if d < best_dist and d <= CAMP_ANCHOR_RADIUS:
                best_dist = d
                best_uid = str(village.get("village_uid", "") or "")
        return best_uid

    def _camp_support_snapshot(self, camp: Dict[str, Any], *, current_tick: int) -> Dict[str, Any]:
        if not isinstance(camp, dict):
            return {
                "nearby_agents": 0,
                "nearby_needy_agents": 0,
                "anchor_agents": 0,
                "nearby_food_sources": 0,
                "has_food_buffer": False,
                "recent_use": False,
                "recent_food_activity": False,
                "patch_activity_score": 0.0,
                "ecological_productivity_score": 0.0,
                "support_score": 0,
                "viable": False,
            }
        cx, cy = int(camp.get("x", 0)), int(camp.get("y", 0))
        camp_id = str(camp.get("camp_id", "") or "")
        nearby_agents = 0
        nearby_needy_agents = 0
        anchor_agents = 0
        for agent in self.agents:
            if not getattr(agent, "alive", False):
                continue
            dist = abs(int(getattr(agent, "x", 0)) - cx) + abs(int(getattr(agent, "y", 0)) - cy)
            if dist > int(CAMP_SUPPORT_EVAL_RADIUS):
                continue
            nearby_agents += 1
            if float(getattr(agent, "hunger", 100.0)) < 55.0:
                nearby_needy_agents += 1
            if str(getattr(agent, "proto_specialization", "none") or "none") != "none":
                anchor = getattr(agent, "proto_task_anchor", {})
                if isinstance(anchor, dict) and str(anchor.get("camp_id", "") or "") == camp_id:
                    anchor_agents += 1
        has_food_buffer = int(camp.get("food_cache", 0)) > 0
        nearby_food_sources = self._count_food_near(cx, cy, radius=CLUSTER_PRODUCTIVITY_RADIUS)
        patch_activity_score = self._patch_activity_score_at(cx, cy)
        ecological_productivity_score = float(nearby_food_sources) + min(4.0, float(patch_activity_score) * 0.08)
        last_use_tick = int(camp.get("last_use_tick", camp.get("last_active_tick", current_tick)))
        last_food_activity_tick = int(camp.get("last_food_activity_tick", camp.get("last_active_tick", current_tick)))
        recent_use = (int(current_tick) - int(last_use_tick)) <= int(CAMP_SUPPORT_RECENT_USE_TICKS)
        recent_food_activity = (int(current_tick) - int(last_food_activity_tick)) <= int(CAMP_SUPPORT_RECENT_USE_TICKS)
        support_score = 0
        if nearby_agents > 0:
            support_score += 2
        if nearby_needy_agents > 0 and has_food_buffer:
            support_score += 2
        elif has_food_buffer:
            support_score += 1
        if recent_use:
            support_score += 1
        if recent_food_activity:
            support_score += 1
        if anchor_agents > 0:
            support_score += 1
        if nearby_food_sources >= 2:
            support_score += 1
        if patch_activity_score >= 8.0:
            support_score += 1
        viable = bool(
            nearby_agents > 0
            or (has_food_buffer and nearby_needy_agents > 0)
            or recent_use
            or recent_food_activity
            or anchor_agents > 0
            or nearby_food_sources > 0
        )
        return {
            "nearby_agents": int(nearby_agents),
            "nearby_needy_agents": int(nearby_needy_agents),
            "anchor_agents": int(anchor_agents),
            "nearby_food_sources": int(nearby_food_sources),
            "has_food_buffer": bool(has_food_buffer),
            "recent_use": bool(recent_use),
            "recent_food_activity": bool(recent_food_activity),
            "patch_activity_score": float(round(float(patch_activity_score), 3)),
            "ecological_productivity_score": float(round(float(ecological_productivity_score), 3)),
            "support_score": int(support_score),
            "viable": bool(viable),
        }

    def _record_camp_retention_from_support(self, support: Dict[str, Any], *, region: str) -> None:
        if not isinstance(support, dict):
            return
        if bool(support.get("recent_use", False)) or bool(support.get("recent_food_activity", False)):
            self.record_camp_retention_reason("recent_use", region=region)
        if int(support.get("nearby_agents", 0)) > 0:
            self.record_camp_retention_reason("nearby_agents", region=region)
        if bool(support.get("has_food_buffer", False)):
            self.record_camp_retention_reason("food_cache", region=region)
        if int(support.get("anchor_agents", 0)) > 0:
            self.record_camp_retention_reason("anchored_loop_support", region=region)

    def update_proto_communities_and_camps(self) -> None:
        components = self._agents_components_for_proto()
        clusters = [c for c in components if len(c) >= PROTO_COMMUNITY_MIN_AGENTS]
        current_tick = int(getattr(self, "tick", 0))
        previous = self.proto_communities if isinstance(self.proto_communities, dict) else {}
        next_state: Dict[str, Dict[str, Any]] = {}
        used_prev: Set[str] = set()
        for component in components:
            center = self._cluster_center(component)
            region = self._region_key_for_pos(center[0], center[1])
            self.record_proto_funnel_stage("co_presence_detected", region=region)
            if len(component) >= PROTO_COMMUNITY_MIN_AGENTS:
                self.record_proto_funnel_stage("co_presence_cluster_valid", region=region)
            else:
                self.record_proto_funnel_failure("cluster_too_small", region=region)

        for cluster in clusters:
            center = self._cluster_center(cluster)
            region = self._region_key_for_pos(center[0], center[1])
            member_ids = tuple(str(getattr(a, "agent_id", "")) for a in cluster)
            best_prev_id = ""
            best_key = (10**9, 10**9)
            for pid, entry in previous.items():
                if not isinstance(entry, dict) or pid in used_prev:
                    continue
                px, py = int(entry.get("x", center[0])), int(entry.get("y", center[1]))
                dist = abs(px - center[0]) + abs(py - center[1])
                prev_members = set(entry.get("agent_ids", [])) if isinstance(entry.get("agent_ids", []), list) else set()
                overlap = len(prev_members.intersection(member_ids))
                key = (0 if overlap > 0 else 1, dist)
                if key < best_key and dist <= PROTO_COMMUNITY_RADIUS + 2:
                    best_key = key
                    best_prev_id = str(pid)

            if best_prev_id:
                used_prev.add(best_prev_id)
                prev_entry = previous.get(best_prev_id, {})
                prev_streak = int(prev_entry.get("streak", 1))
                streak = prev_streak + 1 if best_key[0] == 0 else 1
                community_id = best_prev_id
                if best_key[0] != 0:
                    self.record_proto_funnel_failure("cluster_not_persistent", region=region)
            else:
                community_id = self._next_proto_community_id()
                streak = 1
                stats = self.progression_stats if isinstance(self.progression_stats, dict) else _default_progression_stats()
                stats["proto_community_formed_count"] = int(stats.get("proto_community_formed_count", 0)) + 1
                self.progression_stats = stats
                self.record_proto_funnel_stage("proto_community_formed", region=region)
            self.record_proto_funnel_stage("proto_streak_incremented", region=region)
            if self._cluster_true_survival_crisis(cluster):
                self.record_proto_funnel_failure("agents_starving", region=region)
            else:
                self.record_proto_funnel_stage("proto_viability_check_passed", region=region)
            if self.is_tile_blocked_by_building(center[0], center[1]):
                self.record_proto_funnel_failure("blocked_by_existing_structure", region=region)

            next_state[community_id] = {
                "community_id": community_id,
                "x": int(center[0]),
                "y": int(center[1]),
                "agent_ids": list(member_ids),
                "agent_count": int(len(member_ids)),
                "streak": int(streak),
                "last_seen_tick": int(current_tick),
                "active": True,
            }

        self.proto_communities = next_state
        for pid, entry in previous.items():
            if not isinstance(entry, dict):
                continue
            if str(pid) in used_prev:
                continue
            px, py = int(entry.get("x", 0)), int(entry.get("y", 0))
            region = self._region_key_for_pos(px, py)
            self.record_proto_funnel_failure("agents_moving_apart", region=region)

        camps = self.camps if isinstance(self.camps, dict) else {}
        for community in next_state.values():
            cx, cy = int(community.get("x", 0)), int(community.get("y", 0))
            region = self._region_key_for_pos(cx, cy)
            if int(community.get("streak", 0)) < int(PROTO_COMMUNITY_FORMATION_STREAK):
                continue
            if self._cluster_true_survival_crisis(
                [a for a in self.agents if str(getattr(a, "agent_id", "")) in set(community.get("agent_ids", []))]
            ):
                self.record_proto_funnel_failure("agents_starving", region=region)
                continue
            avg_hunger = 0.0
            members = [a for a in self.agents if str(getattr(a, "agent_id", "")) in set(community.get("agent_ids", []))]
            if members:
                avg_hunger = sum(float(getattr(a, "hunger", 0.0)) for a in members) / float(len(members))
            if avg_hunger < CAMP_FORMATION_HUNGER_MIN:
                self.record_proto_funnel_failure("area_not_viable", region=region)
                continue
            nearby_existing = None
            nearby_existing_dist = 10**9
            for camp in camps.values():
                if not isinstance(camp, dict):
                    continue
                if not bool(camp.get("active", True)):
                    continue
                dist = abs(int(camp.get("x", 0)) - cx) + abs(int(camp.get("y", 0)) - cy)
                if dist <= PROTO_COMMUNITY_RADIUS and dist < nearby_existing_dist:
                    nearby_existing = camp
                    nearby_existing_dist = dist
            if nearby_existing is not None:
                same_community = (
                    str(nearby_existing.get("community_id", "") or "")
                    == str(community.get("community_id", "") or "")
                )
                member_count = int(community.get("agent_count", len(community.get("agent_ids", []))))
                mature_local_nucleus = bool(
                    int(community.get("streak", 0)) >= int(PROTO_COMMUNITY_FORMATION_STREAK + 2)
                    and member_count >= 3
                    and float(avg_hunger) >= float(CAMP_FORMATION_HUNGER_MIN + 6.0)
                )
                local_material = self.secondary_nucleus_materialization_signals(cx, cy)
                materializing_now = bool(
                    bool(local_material.get("materializing", False))
                    and int(local_material.get("nearby_agents", 0)) >= 2
                )
                local_food_sources = self._count_food_near(cx, cy, radius=CLUSTER_PRODUCTIVITY_RADIUS)
                local_patch_activity = self._patch_activity_score_at(cx, cy)
                existing_grace_until = int(nearby_existing.get("materialization_grace_until_tick", -1))
                absorption_delay_allowed = bool(
                    not same_community
                    and int(nearby_existing_dist) >= 3
                    and int(community.get("streak", 0)) <= int(CLUSTER_ABSORPTION_DELAY_STREAK_MAX)
                    and member_count >= 2
                    and float(avg_hunger) >= float(CAMP_FORMATION_HUNGER_MIN + 3.0)
                    and (int(local_food_sources) >= 2 or float(local_patch_activity) >= 8.0)
                )
                if (not absorption_delay_allowed) and materializing_now and float(avg_hunger) >= float(CAMP_FORMATION_HUNGER_MIN + 2.0):
                    absorption_delay_allowed = bool(int(nearby_existing_dist) >= 3)
                if (not absorption_delay_allowed) and int(existing_grace_until) >= int(current_tick):
                    absorption_delay_allowed = True
                if same_community or int(nearby_existing_dist) <= 2 or (not mature_local_nucleus and not absorption_delay_allowed):
                    nearby_existing["last_active_tick"] = int(current_tick)
                    if not same_community:
                        support_nearby = int(nearby_existing.get("support_nearby_agents", 0))
                        reason = (
                            "absorbed_by_dominant_neighbor"
                            if support_nearby >= int(CAMP_DOMINANT_CLUSTER_NEARBY_AGENT_THRESHOLD)
                            else "absorbed_by_nearby_existing_camp"
                        )
                        self.record_settlement_bottleneck("camp_absorption_events")
                        self.record_settlement_bottleneck("camp_absorption_reasons", reason=reason)
                        if materializing_now:
                            self.record_settlement_bottleneck("secondary_nucleus_absorption_during_build")
                        self.record_secondary_nucleus_event("secondary_nucleus_absorption_count")
                    continue
                if absorption_delay_allowed:
                    self.record_settlement_bottleneck("camp_absorption_delay_events")
            pos = self._camp_viable_walkable_pos(cx, cy)
            if pos is None:
                self.record_proto_funnel_failure("area_not_viable", region=region)
                continue
            camp_id = self._next_camp_id()
            camps[camp_id] = {
                "camp_id": camp_id,
                "x": int(pos[0]),
                "y": int(pos[1]),
                "community_id": str(community.get("community_id", "")),
                "created_tick": int(current_tick),
                "last_active_tick": int(current_tick),
                "active": True,
                "absence_ticks": 0,
                "village_uid": self._resolve_camp_village_uid(int(pos[0]), int(pos[1])),
                "return_events": 0,
                "rest_events": 0,
                "food_cache": 0,
                "last_use_tick": int(current_tick),
                "last_food_activity_tick": int(current_tick),
            }
            stats = self.progression_stats if isinstance(self.progression_stats, dict) else _default_progression_stats()
            stats["camp_created_count"] = int(stats.get("camp_created_count", 0)) + 1
            self.progression_stats = stats
            self.record_camp_lifecycle_stage("camp_created", region=region)
            self.record_camp_lifecycle_stage("camp_became_active", region=region)
            active_other_camps = [
                c for cid, c in camps.items()
                if str(cid) != str(camp_id) and isinstance(c, dict) and bool(c.get("active", False))
            ]
            if active_other_camps:
                self.record_secondary_nucleus_event("secondary_nucleus_birth_count")

        for camp in camps.values():
            if not isinstance(camp, dict):
                continue
            x, y = int(camp.get("x", 0)), int(camp.get("y", 0))
            region = self._region_key_for_pos(x, y)
            support = self._camp_support_snapshot(camp, current_tick=current_tick)
            camp["support_score"] = int(support.get("support_score", 0))
            camp["support_nearby_agents"] = int(support.get("nearby_agents", 0))
            camp["support_anchor_agents"] = int(support.get("anchor_agents", 0))
            camp["support_viable"] = bool(support.get("viable", False))
            camp["ecological_productivity_score"] = float(support.get("ecological_productivity_score", 0.0))
            structure_count = self._count_structures_near(x, y, radius=SECONDARY_NUCLEUS_STRUCTURE_RADIUS)
            active_construction_sites = self._count_active_construction_sites_near(x, y, radius=SECONDARY_NUCLEUS_STRUCTURE_RADIUS)
            camp["structure_count"] = int(structure_count)
            camp["active_construction_sites"] = int(active_construction_sites)
            self.record_settlement_bottleneck("secondary_nucleus_structure_count", count=int(structure_count))
            if int(active_construction_sites) > 0 and int(camp.get("support_nearby_agents", 0)) >= 2:
                self.record_settlement_bottleneck("secondary_nucleus_materialization_ticks")
                camp["materialization_grace_until_tick"] = int(current_tick) + int(SECONDARY_NUCLEUS_MATERIALIZATION_GRACE_TICKS)
            self.record_settlement_bottleneck(
                "cluster_ecological_productivity_score_total",
                count=int(round(float(max(0.0, support.get("ecological_productivity_score", 0.0))) * 100.0)),
            )
            self.record_settlement_bottleneck("cluster_ecological_productivity_score_samples")
            near = 0
            for agent in self.agents:
                if not getattr(agent, "alive", False):
                    continue
                if abs(int(agent.x) - x) + abs(int(agent.y) - y) <= CAMP_ANCHOR_RADIUS:
                    near += 1
            if near > 0:
                was_active = bool(camp.get("active", False))
                camp["active"] = True
                camp["last_active_tick"] = int(current_tick)
                camp["absence_ticks"] = 0
                self.record_camp_lifecycle_stage("camp_population_present", region=region)
                if bool(support.get("viable", False)) and int(support.get("support_score", 0)) >= 3:
                    self.record_settlement_bottleneck("local_viable_camp_retained_count")
                    if int(camp.get("support_nearby_agents", 0)) >= 2:
                        self.record_settlement_bottleneck("secondary_cluster_persistence_ticks")
                        self.record_secondary_nucleus_event("secondary_nucleus_persistence_ticks")
                if not was_active:
                    self.record_camp_lifecycle_stage("camp_became_active", region=region)
            else:
                camp["absence_ticks"] = int(camp.get("absence_ticks", 0)) + 1
                stale = int(current_tick) - int(camp.get("last_active_tick", current_tick))
                linked_community = str(camp.get("community_id", "")) in next_state
                required_absence = int(CAMP_DEACTIVATION_ABSENCE_TICKS) + (
                    int(CAMP_LINKED_COMMUNITY_ABSENCE_BONUS_TICKS) if linked_community else 0
                )
                sustained_absence = int(camp.get("absence_ticks", 0)) > int(required_absence)
                support_viable = bool(support.get("viable", False))
                support_grace = int(CAMP_SUPPORT_GRACE_ABSENCE_BONUS_TICKS) if support_viable else 0
                if stale > CAMP_ACTIVE_STALE_TICKS:
                    if support_viable and stale <= int(CAMP_ACTIVE_STALE_TICKS + CAMP_SUPPORT_RECENT_USE_TICKS):
                        camp["active"] = True
                        self.record_settlement_bottleneck("local_viable_camp_retained_count")
                        if int(camp.get("support_nearby_agents", 0)) >= 2:
                            self.record_settlement_bottleneck("secondary_cluster_persistence_ticks")
                            self.record_secondary_nucleus_event("secondary_nucleus_persistence_ticks")
                        self._record_camp_retention_from_support(support, region=region)
                    else:
                        if bool(camp.get("active", False)):
                            self.record_camp_lifecycle_stage("camp_deactivated", region=region)
                            self.record_camp_deactivation_reason("camp_stale_timeout", region=region)
                            self.record_camp_deactivation_support_snapshot(region=region, support=support)
                        camp["active"] = False
                        camp["food_cache"] = 0
                elif sustained_absence:
                    if int(camp.get("absence_ticks", 0)) <= int(required_absence + support_grace):
                        camp["active"] = True
                        self.record_settlement_bottleneck("local_viable_camp_retained_count")
                        if int(camp.get("support_nearby_agents", 0)) >= 2:
                            self.record_settlement_bottleneck("secondary_cluster_persistence_ticks")
                            self.record_secondary_nucleus_event("secondary_nucleus_persistence_ticks")
                        self._record_camp_retention_from_support(support, region=region)
                    else:
                        if bool(camp.get("active", False)):
                            self.record_camp_lifecycle_stage("camp_deactivated", region=region)
                            reason = "agents_migrated" if not linked_community else "no_agents_nearby"
                            if not support_viable:
                                reason = "no_viable_support"
                            self.record_camp_deactivation_reason(reason, region=region)
                            self.record_camp_deactivation_support_snapshot(region=region, support=support)
                            self.record_secondary_nucleus_event("secondary_nucleus_decay_count")
                        camp["active"] = False
                        camp["food_cache"] = 0
            camp["village_uid"] = self._resolve_camp_village_uid(x, y)
            community_id = str(camp.get("community_id", ""))
            if community_id and community_id not in next_state and int(current_tick) - int(camp.get("created_tick", current_tick)) > PROTO_COMMUNITY_STALE_TICKS:
                was_active = bool(camp.get("active", False))
                if was_active:
                    self.record_camp_lifecycle_stage("camp_deactivated", region=region)
                    self.record_camp_deactivation_support_snapshot(
                        region=region, support=self._camp_support_snapshot(camp, current_tick=current_tick)
                    )
                reason = "agents_migrated"
                if str(camp.get("village_uid", "") or ""):
                    reason = "replaced_by_village_anchor"
                if any(
                    isinstance(b, dict)
                    and str(b.get("type", "")) == "house"
                    and str(b.get("operational_state", "")) == "active"
                    and abs(int(b.get("x", 0)) - x) + abs(int(b.get("y", 0)) - y) <= 6
                    for b in self.buildings.values()
                ):
                    reason = "replaced_by_house_anchor"
                if was_active:
                    self.record_camp_deactivation_reason(reason, region=region)
                camp["active"] = False
                camp["food_cache"] = 0
            if not self.is_walkable(x, y):
                was_active = bool(camp.get("active", False))
                if was_active:
                    self.record_camp_lifecycle_stage("camp_deactivated", region=region)
                    self.record_camp_deactivation_reason("area_no_longer_viable", region=region)
                    self.record_camp_deactivation_support_snapshot(
                        region=region, support=self._camp_support_snapshot(camp, current_tick=current_tick)
                    )
                camp["active"] = False
                camp["food_cache"] = 0
        self.update_camp_food_decay()
        self.camps = camps

    def nearest_active_camp_for_agent(self, agent: Agent, *, max_distance: int = CAMP_ANCHOR_RADIUS) -> Optional[Dict[str, Any]]:
        camps = self.camps if isinstance(self.camps, dict) else {}
        status = str(getattr(agent, "village_affiliation_status", "unaffiliated") or "unaffiliated")
        preferred_uid = str(getattr(agent, "home_village_uid", "") or getattr(agent, "primary_village_uid", "") or "")
        candidates: List[Tuple[int, int, int, int, int, float, str, Dict[str, Any]]] = []
        nearest_viable_dist: Optional[int] = None
        nearest_viable_productivity = 0.0
        anchor = getattr(agent, "proto_task_anchor", {})
        anchored_camp_id = str(anchor.get("camp_id", "")) if isinstance(anchor, dict) else ""
        critical_hunger = float(getattr(agent, "hunger", 100.0)) < 28.0
        for camp_id, camp in camps.items():
            if not isinstance(camp, dict) or not bool(camp.get("active", False)):
                continue
            cx, cy = int(camp.get("x", 0)), int(camp.get("y", 0))
            dist = abs(int(getattr(agent, "x", 0)) - cx) + abs(int(getattr(agent, "y", 0)) - cy)
            if dist > int(max_distance):
                continue
            camp_uid = str(camp.get("village_uid", "") or "")
            uid_bias = 0 if (preferred_uid and camp_uid == preferred_uid) else 1
            status_bias = 0 if status in {"attached", "transient", "unaffiliated"} else 1
            support_score = int(camp.get("support_score", 0))
            nearby_agents = int(camp.get("support_nearby_agents", 0))
            ecological_productivity = float(camp.get("ecological_productivity_score", 0.0))
            candidates.append((uid_bias, status_bias, dist, support_score, nearby_agents, ecological_productivity, str(camp_id), camp))
            if support_score >= 2 and dist <= int(CAMP_LOCAL_VIABLE_RADIUS):
                if nearest_viable_dist is None or dist < nearest_viable_dist:
                    nearest_viable_dist = int(dist)
                    nearest_viable_productivity = float(ecological_productivity)
                elif nearest_viable_dist == int(dist):
                    nearest_viable_productivity = max(float(nearest_viable_productivity), float(ecological_productivity))
        if not candidates:
            return None

        def _base_sort_key(item: Tuple[int, int, int, int, int, float, str, Dict[str, Any]]) -> Tuple[int, int, str]:
            uid_bias, status_bias, dist, _, _, _, camp_id, _ = item
            return (uid_bias, status_bias * 2 + dist, camp_id)

        def _tuned_sort_key(item: Tuple[int, int, int, int, int, float, str, Dict[str, Any]]) -> Tuple[int, int, str]:
            uid_bias, status_bias, dist, support_score, nearby_agents, ecological_productivity, camp_id, _ = item
            penalty = 0
            effective_uid_bias = uid_bias
            if nearest_viable_dist is not None and dist > int(nearest_viable_dist + CAMP_DOMINANT_PULL_DISTANCE_GAP):
                penalty += 4
                effective_uid_bias = 1
                if nearest_viable_productivity >= max(1.2, ecological_productivity * 0.75):
                    penalty += 1
            if nearest_viable_dist is not None and nearby_agents >= int(CAMP_DOMINANT_CLUSTER_NEARBY_AGENT_THRESHOLD):
                penalty += 2
                if dist > int(max(2, nearest_viable_dist or 0)):
                    self.record_settlement_bottleneck("dominant_cluster_saturation_penalty_applied")
            local_bonus = -1 if support_score >= 3 and dist <= int(CAMP_LOCAL_VIABLE_RADIUS) else 0
            if ecological_productivity >= 3.0 and dist <= int(CAMP_LOCAL_VIABLE_RADIUS):
                local_bonus -= 1
            if (not critical_hunger) and anchored_camp_id and str(camp_id) == anchored_camp_id and support_score >= 2:
                local_bonus -= 2
            return (effective_uid_bias, status_bias * 2 + dist + penalty + local_bonus, camp_id)

        base_sorted = sorted(candidates, key=_base_sort_key)
        tuned_sorted = sorted(candidates, key=_tuned_sort_key)
        base_winner = base_sorted[0]
        tuned_winner = tuned_sorted[0]
        if nearest_viable_dist is not None and str(base_winner[6]) != str(tuned_winner[6]):
            self.record_settlement_bottleneck("distant_cluster_pull_suppressed_count")
            reason = "prefer_nearby_viable_cluster"
            if int(base_winner[4]) >= int(CAMP_DOMINANT_CLUSTER_NEARBY_AGENT_THRESHOLD):
                reason = "avoid_overcrowded_dominant_cluster"
            self.record_settlement_bottleneck("distant_cluster_pull_suppressed_reasons", reason=reason)
        if (not critical_hunger) and anchored_camp_id and str(tuned_winner[6]) == anchored_camp_id:
            self.record_settlement_bottleneck("cluster_inertia_events")
        return tuned_winner[7]

    def is_agent_near_camp(self, agent: Agent, *, radius: int = CAMP_REST_RADIUS) -> bool:
        camp = self.nearest_active_camp_for_agent(agent, max_distance=max(1, int(radius)))
        if not isinstance(camp, dict):
            return False
        cx, cy = int(camp.get("x", 0)), int(camp.get("y", 0))
        return (
            abs(int(getattr(agent, "x", 0)) - cx) + abs(int(getattr(agent, "y", 0)) - cy)
        ) <= int(radius)

    def camp_has_food_for_agent(self, agent: Agent, *, max_distance: int = 4) -> bool:
        camp = self.nearest_active_camp_for_agent(agent, max_distance=max(1, int(max_distance)))
        if not isinstance(camp, dict):
            return False
        return int(camp.get("food_cache", 0)) > 0

    def _nearby_active_houses_for_agent(self, agent: Agent, *, max_distance: int) -> List[Dict[str, Any]]:
        candidates: List[Tuple[int, int, Dict[str, Any]]] = []
        preferred_uid = str(self.resolve_village_uid(getattr(agent, "village_id", None)) or "")
        for building in getattr(self, "buildings", {}).values():
            if not isinstance(building, dict):
                continue
            if str(building.get("type", "")) != "house":
                continue
            if str(building.get("operational_state", "")) != "active":
                continue
            bx = int(building.get("x", 0))
            by = int(building.get("y", 0))
            dist = abs(int(agent.x) - bx) + abs(int(agent.y) - by)
            if dist > int(max_distance):
                continue
            building_uid = str(building.get("village_uid", "") or "")
            uid_sort = 0 if (preferred_uid and building_uid == preferred_uid) else 1
            candidates.append((dist, uid_sort, building))
        candidates.sort(key=lambda item: (int(item[0]), int(item[1]), str(item[2].get("building_id", ""))))
        return [item[2] for item in candidates]

    def _ensure_house_food_state(self, house: Dict[str, Any]) -> Tuple[int, int]:
        if not isinstance(house, dict):
            return (0, 0)
        capacity = max(1, int(house.get("domestic_food_capacity", HOUSE_DOMESTIC_FOOD_CAPACITY)))
        food = max(0, int(house.get("domestic_food", 0)))
        house["domestic_food_capacity"] = int(capacity)
        house["domestic_food"] = int(food)
        return (food, capacity)

    def house_has_food_for_agent(self, agent: Agent, *, max_distance: int = HOUSE_DOMESTIC_CONSUME_RADIUS) -> bool:
        houses = self._nearby_active_houses_for_agent(agent, max_distance=max(1, int(max_distance)))
        for house in houses:
            food, _capacity = self._ensure_house_food_state(house)
            if int(food) > 0:
                return True
        return False

    def current_total_food_in_reserves(self) -> int:
        total = 0
        for camp in (self.camps or {}).values():
            if not isinstance(camp, dict):
                continue
            if not bool(camp.get("active", False)):
                continue
            total += max(0, int(camp.get("food_cache", 0)))
        for building in (self.buildings or {}).values():
            if not isinstance(building, dict):
                continue
            btype = str(building.get("type", ""))
            if btype == "house":
                total += max(0, int(building.get("domestic_food", 0)))
                continue
            if btype != "storage":
                continue
            if str(building.get("operational_state", "")) != "active":
                continue
            storage = building.get("storage", {})
            if isinstance(storage, dict):
                total += max(0, int(storage.get("food", 0)))
        return int(max(0, total))

    def compute_local_food_pressure_for_agent(self, agent: Agent, *, max_distance: int = LOCAL_FOOD_PRESSURE_RADIUS) -> Dict[str, Any]:
        camp = self.nearest_active_camp_for_agent(agent, max_distance=max(1, int(max_distance)))
        if not isinstance(camp, dict):
            return {
                "has_camp": False,
                "pressure_score": 0,
                "pressure_active": False,
                "unmet_pressure": False,
                "camp_id": "",
                "camp_food": 0,
                "nearby_needy_agents": 0,
                "near_food_sources": 0,
                "drop_distance": 9999,
            }
        cx, cy = int(camp.get("x", 0)), int(camp.get("y", 0))
        camp_food = max(0, int(camp.get("food_cache", 0)))
        house_food_nearby = 0
        for house in self._nearby_active_houses_for_agent(agent, max_distance=HOUSE_DOMESTIC_CONSUME_RADIUS):
            food, _capacity = self._ensure_house_food_state(house)
            house_food_nearby += int(food)
        nearby_needy_agents = 0
        for other in self.agents:
            if not getattr(other, "alive", False):
                continue
            dist = abs(int(getattr(other, "x", 0)) - cx) + abs(int(getattr(other, "y", 0)) - cy)
            if dist > int(max_distance):
                continue
            if float(getattr(other, "hunger", 100.0)) < float(LOCAL_FOOD_PRESSURE_NEEDY_HUNGER):
                nearby_needy_agents += 1
        near_food_sources = 0
        for fx, fy in self.food:
            if abs(int(fx) - cx) + abs(int(fy) - cy) <= int(max_distance):
                near_food_sources += 1
                if near_food_sources >= 4:
                    break
        drop_distance = abs(int(getattr(agent, "x", 0)) - cx) + abs(int(getattr(agent, "y", 0)) - cy)
        score = 0
        buffered_food = int(camp_food + house_food_nearby)
        if buffered_food <= 1:
            score += 2
        elif buffered_food <= 3:
            score += 1
        if nearby_needy_agents > 0:
            score += 2
        if near_food_sources > 0:
            score += 1
        if drop_distance <= 4:
            score += 1
        has_carried_food = int(getattr(agent, "inventory", {}).get("food", 0)) > 0
        unmet = bool(buffered_food <= 1 and nearby_needy_agents > 0 and near_food_sources <= 0 and not has_carried_food)
        pressure_active = bool(score >= 3)
        stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
        if score > 0:
            stats["camp_food_pressure_ticks"] = int(stats.get("camp_food_pressure_ticks", 0)) + 1
        if pressure_active:
            stats["local_food_pressure_events"] = int(stats.get("local_food_pressure_events", 0)) + 1
        if unmet:
            stats["unmet_food_pressure_count"] = int(stats.get("unmet_food_pressure_count", 0)) + 1
            stats["loop_abandoned_due_to_no_source"] = int(stats.get("loop_abandoned_due_to_no_source", 0)) + 1
        self.camp_food_stats = stats
        return {
            "has_camp": True,
            "pressure_score": int(score),
            "pressure_active": bool(pressure_active),
            "unmet_pressure": bool(unmet),
            "camp_id": str(camp.get("camp_id", "")),
            "camp_food": int(camp_food),
            "house_food_nearby": int(house_food_nearby),
            "nearby_needy_agents": int(nearby_needy_agents),
            "near_food_sources": int(near_food_sources),
            "drop_distance": int(drop_distance),
        }

    def record_pressure_backed_loop_selected(self) -> None:
        stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
        stats["pressure_backed_loop_selected_count"] = int(stats.get("pressure_backed_loop_selected_count", 0)) + 1
        self.camp_food_stats = stats

    def record_communication_event(self, kind: str) -> None:
        stats = self.communication_stats if isinstance(self.communication_stats, dict) else _default_communication_stats()
        stats["communication_events"] = int(stats.get("communication_events", 0)) + 1
        if str(kind) == "food":
            stats["food_knowledge_shared_count"] = int(stats.get("food_knowledge_shared_count", 0)) + 1
        elif str(kind) == "camp":
            stats["camp_knowledge_shared_count"] = int(stats.get("camp_knowledge_shared_count", 0)) + 1
        self.communication_stats = stats

    def record_shared_knowledge_used(self, kind: str) -> None:
        stats = self.communication_stats if isinstance(self.communication_stats, dict) else _default_communication_stats()
        if str(kind) == "food":
            stats["shared_food_knowledge_used_count"] = int(stats.get("shared_food_knowledge_used_count", 0)) + 1
        elif str(kind) == "camp":
            stats["shared_camp_knowledge_used_count"] = int(stats.get("shared_camp_knowledge_used_count", 0)) + 1
        self.communication_stats = stats

    def record_stale_knowledge_expired(self, count: int = 1) -> None:
        stats = self.communication_stats if isinstance(self.communication_stats, dict) else _default_communication_stats()
        stats["stale_knowledge_expired_count"] = int(stats.get("stale_knowledge_expired_count", 0)) + max(0, int(count))
        self.communication_stats = stats

    def record_invalidated_shared_knowledge(self, count: int = 1) -> None:
        stats = self.communication_stats if isinstance(self.communication_stats, dict) else _default_communication_stats()
        stats["invalidated_shared_knowledge_count"] = int(stats.get("invalidated_shared_knowledge_count", 0)) + max(0, int(count))
        self.communication_stats = stats

    def record_confirmed_memory_reinforcement(self, count: int = 1) -> None:
        stats = self.communication_stats if isinstance(self.communication_stats, dict) else _default_communication_stats()
        stats["confirmed_memory_reinforcements"] = int(stats.get("confirmed_memory_reinforcements", 0)) + max(0, int(count))
        self.communication_stats = stats

    def record_direct_memory_invalidation(self, count: int = 1) -> None:
        stats = self.communication_stats if isinstance(self.communication_stats, dict) else _default_communication_stats()
        stats["direct_memory_invalidations"] = int(stats.get("direct_memory_invalidations", 0)) + max(0, int(count))
        self.communication_stats = stats

    def record_social_knowledge_decision(self, *, accepted: bool, reason: str = "", subject: str = "") -> None:
        stats = self.communication_stats if isinstance(self.communication_stats, dict) else _default_communication_stats()
        if bool(accepted):
            stats["social_knowledge_accept_count"] = int(stats.get("social_knowledge_accept_count", 0)) + 1
            sub = str(subject or "")
            if sub == "food":
                stats["social_food_knowledge_adopted_count"] = int(stats.get("social_food_knowledge_adopted_count", 0)) + 1
            elif sub == "camp":
                stats["social_camp_knowledge_adopted_count"] = int(stats.get("social_camp_knowledge_adopted_count", 0)) + 1
        else:
            stats["social_knowledge_reject_count"] = int(stats.get("social_knowledge_reject_count", 0)) + 1
            key = f"social_knowledge_reject_{str(reason or '').strip()}"
            if key in stats:
                stats[key] = int(stats.get(key, 0)) + 1
        self.communication_stats = stats

    def record_direct_overrides_social(self, count: int = 1) -> None:
        stats = self.communication_stats if isinstance(self.communication_stats, dict) else _default_communication_stats()
        stats["direct_overrides_social_count"] = int(stats.get("direct_overrides_social_count", 0)) + max(0, int(count))
        self.communication_stats = stats

    def record_duplicate_share_suppressed(self, count: int = 1) -> None:
        stats = self.communication_stats if isinstance(self.communication_stats, dict) else _default_communication_stats()
        stats["repeated_duplicate_share_suppressed_count"] = int(stats.get("repeated_duplicate_share_suppressed_count", 0)) + max(0, int(count))
        self.communication_stats = stats

    def record_camp_knowledge_share_suppressed(self, count: int = 1) -> None:
        stats = self.communication_stats if isinstance(self.communication_stats, dict) else _default_communication_stats()
        stats["camp_knowledge_share_suppressed_count"] = int(stats.get("camp_knowledge_share_suppressed_count", 0)) + max(0, int(count))
        self.communication_stats = stats

    def record_completion_bias_applied(self) -> None:
        stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
        stats["completion_bias_applied_count"] = int(stats.get("completion_bias_applied_count", 0)) + 1
        self.camp_food_stats = stats

    def record_delivery_commitment_retained(self) -> None:
        stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
        stats["delivery_commitment_retained_ticks"] = int(stats.get("delivery_commitment_retained_ticks", 0)) + 1
        self.camp_food_stats = stats

    def record_loop_retarget_outcome(self, *, success: bool) -> None:
        stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
        key = "loop_retarget_success_count" if bool(success) else "loop_retarget_failure_count"
        stats[key] = int(stats.get(key, 0)) + 1
        self.camp_food_stats = stats

    def try_deposit_food_to_nearby_camp(self, agent: Agent, *, amount: int = 1, hunger_before: Optional[float] = None) -> int:
        stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
        stats["camp_food_deposit_attempts"] = int(stats.get("camp_food_deposit_attempts", 0)) + 1
        self.camp_food_stats = stats
        pressure = self.compute_local_food_pressure_for_agent(agent, max_distance=LOCAL_FOOD_PRESSURE_RADIUS)
        near_complete = bool(
            isinstance(pressure, dict)
            and int(pressure.get("drop_distance", 9999)) <= 2
            and int(getattr(agent, "inventory", {}).get("food", 0)) > 0
        )
        if near_complete:
            stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
            stats["near_complete_loop_opportunities"] = int(stats.get("near_complete_loop_opportunities", 0)) + 1
            self.camp_food_stats = stats
        inventory_food = int(getattr(agent, "inventory", {}).get("food", 0))
        if inventory_food <= 0:
            return 0
        hunger_gate = float(hunger_before if hunger_before is not None else getattr(agent, "hunger", 100.0))
        if hunger_gate < 30.0:
            stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
            stats["camp_food_deposit_blocked_low_hunger"] = int(stats.get("camp_food_deposit_blocked_low_hunger", 0)) + 1
            self.camp_food_stats = stats
            return 0
        camp = self.nearest_active_camp_for_agent(agent, max_distance=2)
        if not isinstance(camp, dict):
            stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
            stats["loop_abandoned_count"] = int(stats.get("loop_abandoned_count", 0)) + 1
            stats["loop_abandoned_due_to_no_drop_target"] = int(stats.get("loop_abandoned_due_to_no_drop_target", 0)) + 1
            if near_complete:
                stats["near_complete_loop_abandoned"] = int(stats.get("near_complete_loop_abandoned", 0)) + 1
            self.camp_food_stats = stats
            return 0
        cache_now = max(0, int(camp.get("food_cache", 0)))
        space = max(0, int(CAMP_FOOD_CACHE_CAPACITY) - cache_now)
        if space <= 0:
            stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
            stats["loop_abandoned_count"] = int(stats.get("loop_abandoned_count", 0)) + 1
            stats["loop_abandoned_due_to_saturated_cache"] = int(stats.get("loop_abandoned_due_to_saturated_cache", 0)) + 1
            if near_complete:
                stats["near_complete_loop_abandoned"] = int(stats.get("near_complete_loop_abandoned", 0)) + 1
            self.camp_food_stats = stats
            return 0
        # Avoid low-value churn: if local camp pressure is low and cache is already buffered, keep food local.
        if int(pressure.get("pressure_score", 0)) <= 2 and cache_now >= 3 and hunger_gate < 80.0:
            stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
            stats["loop_abandoned_count"] = int(stats.get("loop_abandoned_count", 0)) + 1
            stats["loop_abandoned_due_to_saturated_cache"] = int(stats.get("loop_abandoned_due_to_saturated_cache", 0)) + 1
            if near_complete:
                stats["near_complete_loop_abandoned"] = int(stats.get("near_complete_loop_abandoned", 0)) + 1
            self.camp_food_stats = stats
            return 0
        # Preserve a bounded self-ration so cooperation does not become suicidal over-donation.
        reserve_food = 0
        if hunger_gate < 45.0:
            reserve_food = 1
        if hunger_gate < 35.0:
            reserve_food = min(2, max(1, int(inventory_food)))
        if cache_now > 0 and hunger_gate >= 40.0:
            reserve_food = max(0, int(reserve_food) - 1)
        depositable = max(0, int(inventory_food) - int(reserve_food))
        if depositable <= 0:
            stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
            stats["camp_food_deposit_blocked_self_reserve"] = int(stats.get("camp_food_deposit_blocked_self_reserve", 0)) + 1
            self.camp_food_stats = stats
            return 0
        move_amount = min(max(0, int(amount)), int(depositable), space)
        if move_amount <= 0:
            return 0
        agent.inventory["food"] = int(agent.inventory.get("food", 0)) - move_amount
        camp["food_cache"] = cache_now + move_amount
        stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
        stats["camp_food_deposits"] = int(stats.get("camp_food_deposits", 0)) + int(move_amount)
        self.camp_food_stats = stats
        camp["last_active_tick"] = int(getattr(self, "tick", 0))
        camp["last_use_tick"] = int(getattr(self, "tick", 0))
        camp["last_food_activity_tick"] = int(getattr(self, "tick", 0))
        camp["active"] = True
        self.record_food_patch_activity(int(camp.get("x", agent.x)), int(camp.get("y", agent.y)), amount=0.9 * float(move_amount))
        stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
        stats["loop_completed_count"] = int(stats.get("loop_completed_count", 0)) + 1
        if bool(pressure.get("pressure_active", False)):
            stats["pressure_backed_food_deliveries"] = int(stats.get("pressure_backed_food_deliveries", 0)) + int(move_amount)
        if near_complete:
            stats["near_complete_loop_completed"] = int(stats.get("near_complete_loop_completed", 0)) + 1
        self.camp_food_stats = stats
        self.record_food_security_flow("group_feeding", amount=int(move_amount))
        self.record_food_security_flow("reserve_accumulation", amount=int(move_amount))
        return int(move_amount)

    def try_deposit_food_to_nearby_house(self, agent: Agent, *, amount: int = 1, hunger_before: Optional[float] = None) -> int:
        inventory_food = int(getattr(agent, "inventory", {}).get("food", 0))
        if inventory_food <= 0:
            return 0
        hunger_gate = float(hunger_before if hunger_before is not None else getattr(agent, "hunger", 100.0))
        if hunger_gate < 30.0:
            return 0
        houses = self._nearby_active_houses_for_agent(agent, max_distance=HOUSE_DOMESTIC_DEPOSIT_RADIUS)
        if not houses:
            return 0
        reserve_food = 0
        if hunger_gate < 45.0:
            reserve_food = 1
        if hunger_gate < 35.0:
            reserve_food = min(2, max(1, int(inventory_food)))
        depositable = max(0, int(inventory_food) - int(reserve_food))
        if depositable <= 0:
            return 0

        stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
        for house in houses:
            house_food, house_capacity = self._ensure_house_food_state(house)
            space = max(0, int(house_capacity) - int(house_food))
            if space <= 0:
                stats["domestic_storage_full_events"] = int(stats.get("domestic_storage_full_events", 0)) + 1
                continue
            move_amount = min(max(0, int(amount)), int(depositable), int(space))
            if move_amount <= 0:
                continue
            house["domestic_food"] = int(house_food) + int(move_amount)
            house["last_active_tick"] = int(getattr(self, "tick", 0))
            agent.inventory["food"] = int(agent.inventory.get("food", 0)) - int(move_amount)
            stats["domestic_food_stored_total"] = int(stats.get("domestic_food_stored_total", 0)) + int(move_amount)
            stats["house_food_distribution_events"] = int(stats.get("house_food_distribution_events", 0)) + 1
            self.camp_food_stats = stats
            self.record_food_security_flow("group_feeding", amount=int(move_amount))
            self.record_food_security_flow("reserve_accumulation", amount=int(move_amount))
            self.record_food_patch_activity(int(house.get("x", agent.x)), int(house.get("y", agent.y)), amount=0.5 * float(move_amount))
            return int(move_amount)
        self.camp_food_stats = stats
        return 0

    def consume_food_from_nearby_camp(self, agent: Agent, *, amount: int = 1) -> int:
        camp = self.nearest_active_camp_for_agent(agent, max_distance=int(CAMP_FOOD_ACCESS_RADIUS))
        if not isinstance(camp, dict):
            return 0
        stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
        stats["camp_food_consume_attempts"] = int(stats.get("camp_food_consume_attempts", 0)) + 1
        self.camp_food_stats = stats
        cache_now = max(0, int(camp.get("food_cache", 0)))
        if cache_now <= 0:
            stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
            stats["camp_food_consume_misses"] = int(stats.get("camp_food_consume_misses", 0)) + 1
            self.camp_food_stats = stats
            return 0
        consume_amount = min(max(0, int(amount)), cache_now)
        if consume_amount <= 0:
            stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
            stats["camp_food_consume_misses"] = int(stats.get("camp_food_consume_misses", 0)) + 1
            self.camp_food_stats = stats
            return 0
        camp["food_cache"] = cache_now - consume_amount
        stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
        stats["camp_food_consumptions"] = int(stats.get("camp_food_consumptions", 0)) + int(consume_amount)
        self.camp_food_stats = stats
        camp["last_active_tick"] = int(getattr(self, "tick", 0))
        camp["last_use_tick"] = int(getattr(self, "tick", 0))
        camp["last_food_activity_tick"] = int(getattr(self, "tick", 0))
        camp["active"] = True
        self.record_food_patch_activity(int(camp.get("x", agent.x)), int(camp.get("y", agent.y)), amount=0.6 * float(consume_amount))
        stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
        stats["loop_completed_count"] = int(stats.get("loop_completed_count", 0)) + 1
        self.camp_food_stats = stats
        return int(consume_amount)

    def consume_food_from_nearby_house(self, agent: Agent, *, amount: int = 1) -> int:
        houses = self._nearby_active_houses_for_agent(agent, max_distance=HOUSE_DOMESTIC_CONSUME_RADIUS)
        if not houses:
            return 0
        stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
        for house in houses:
            house_food, _house_capacity = self._ensure_house_food_state(house)
            if house_food <= 0:
                continue
            consume_amount = min(max(0, int(amount)), int(house_food))
            if consume_amount <= 0:
                continue
            house["domestic_food"] = int(house_food) - int(consume_amount)
            house["last_active_tick"] = int(getattr(self, "tick", 0))
            stats["domestic_food_consumed_total"] = int(stats.get("domestic_food_consumed_total", 0)) + int(consume_amount)
            stats["house_food_distribution_events"] = int(stats.get("house_food_distribution_events", 0)) + 1
            self.camp_food_stats = stats
            self.record_food_patch_activity(int(house.get("x", agent.x)), int(house.get("y", agent.y)), amount=0.4 * float(consume_amount))
            return int(consume_amount)
        return 0

    def _try_deposit_food_to_nearby_storage(self, agent: Agent, *, amount: int = 1, hunger_before: Optional[float] = None) -> int:
        hunger_gate = float(hunger_before if hunger_before is not None else getattr(agent, "hunger", 100.0))
        if hunger_gate < 30.0:
            return 0
        inventory_food = int(getattr(agent, "inventory", {}).get("food", 0))
        if inventory_food <= 0:
            return 0
        preferred_uid = str(self.resolve_village_uid(getattr(agent, "village_id", None)) or "")
        candidates: List[Tuple[int, int, Dict[str, Any]]] = []
        for building in getattr(self, "buildings", {}).values():
            if not isinstance(building, dict):
                continue
            if str(building.get("type", "")) != "storage":
                continue
            if str(building.get("operational_state", "")) != "active":
                continue
            storage = building.get("storage", {})
            if not isinstance(storage, dict):
                continue
            capacity = max(1, int(building.get("storage_capacity", 0) or 1))
            used = int(storage.get("food", 0)) + int(storage.get("wood", 0)) + int(storage.get("stone", 0))
            if used >= capacity:
                continue
            bx = int(building.get("x", 0))
            by = int(building.get("y", 0))
            dist = abs(int(agent.x) - bx) + abs(int(agent.y) - by)
            if dist > 1:
                continue
            building_uid = str(building.get("village_uid", "") or "")
            uid_sort = 0 if (preferred_uid and building_uid == preferred_uid) else 1
            candidates.append((dist, uid_sort, building))
        if not candidates:
            return 0
        candidates.sort(key=lambda item: (int(item[0]), int(item[1]), str(item[2].get("building_id", ""))))
        target = candidates[0][2]
        storage = target.get("storage", {})
        if not isinstance(storage, dict):
            return 0
        capacity = max(1, int(target.get("storage_capacity", 0) or 1))
        used = int(storage.get("food", 0)) + int(storage.get("wood", 0)) + int(storage.get("stone", 0))
        space = max(0, int(capacity) - int(used))
        move_amount = min(max(0, int(amount)), int(inventory_food), int(space))
        if move_amount <= 0:
            return 0
        storage["food"] = int(storage.get("food", 0)) + int(move_amount)
        target["storage"] = storage
        agent.inventory["food"] = int(agent.inventory.get("food", 0)) - int(move_amount)
        progression = self.settlement_progression_stats if isinstance(self.settlement_progression_stats, dict) else _default_settlement_progression_stats()
        camp_food = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
        if int(camp_food.get("domestic_storage_full_events", 0)) > 0:
            progression["storage_relief_of_domestic_pressure_events"] = int(
                progression.get("storage_relief_of_domestic_pressure_events", 0)
            ) + int(move_amount)
        camp_near = self.nearest_active_camp_for_agent(agent, max_distance=int(CAMP_FOOD_ACCESS_RADIUS))
        if isinstance(camp_near, dict) and int(camp_near.get("food_cache", 0)) >= int(CAMP_FOOD_CACHE_CAPACITY) - 1:
            progression["storage_relief_of_camp_pressure_events"] = int(
                progression.get("storage_relief_of_camp_pressure_events", 0)
            ) + int(move_amount)
        self.settlement_progression_stats = progression
        self.record_food_security_flow("reserve_accumulation", amount=int(move_amount))
        village = self.get_village_by_id(getattr(agent, "village_id", None))
        if village is not None and hasattr(building_system, "_sync_village_storage_cache"):
            try:
                building_system._sync_village_storage_cache(self, village)
            except Exception:
                pass
        return int(move_amount)

    def try_deposit_food_to_local_buffers(self, agent: Agent, *, amount: int = 1, hunger_before: Optional[float] = None) -> int:
        progression = (
            self.settlement_progression_stats
            if isinstance(self.settlement_progression_stats, dict)
            else _default_settlement_progression_stats()
        )
        had_food_before = int(getattr(agent, "inventory", {}).get("food", 0))
        if int(amount) > 0 and had_food_before > 0:
            progression["reserve_refill_attempts"] = int(progression.get("reserve_refill_attempts", 0)) + 1
        moved = int(self.try_deposit_food_to_nearby_house(agent, amount=amount, hunger_before=hunger_before))
        if moved > 0:
            progression["reserve_refill_success"] = int(progression.get("reserve_refill_success", 0)) + 1
            progression["reserve_refill_food_added_total"] = int(progression.get("reserve_refill_food_added_total", 0)) + int(moved)
            tick_now = int(getattr(self, "tick", 0))
            last_tick = int(progression.get("reserve_last_refill_tick", -1))
            if last_tick >= 0:
                progression["reserve_refill_interval_ticks_total"] = int(
                    progression.get("reserve_refill_interval_ticks_total", 0)
                ) + max(0, tick_now - last_tick)
                progression["reserve_refill_interval_ticks_samples"] = int(
                    progression.get("reserve_refill_interval_ticks_samples", 0)
                ) + 1
            progression["reserve_last_refill_tick"] = int(tick_now)
            self.settlement_progression_stats = progression
            return moved
        if isinstance(self.nearest_active_camp_for_agent(agent, max_distance=2), dict):
            moved = int(self.try_deposit_food_to_nearby_camp(agent, amount=amount, hunger_before=hunger_before))
            if moved > 0:
                progression["reserve_refill_success"] = int(progression.get("reserve_refill_success", 0)) + 1
                progression["reserve_refill_food_added_total"] = int(progression.get("reserve_refill_food_added_total", 0)) + int(moved)
                tick_now = int(getattr(self, "tick", 0))
                last_tick = int(progression.get("reserve_last_refill_tick", -1))
                if last_tick >= 0:
                    progression["reserve_refill_interval_ticks_total"] = int(
                        progression.get("reserve_refill_interval_ticks_total", 0)
                    ) + max(0, tick_now - last_tick)
                    progression["reserve_refill_interval_ticks_samples"] = int(
                        progression.get("reserve_refill_interval_ticks_samples", 0)
                    ) + 1
                progression["reserve_last_refill_tick"] = int(tick_now)
                self.settlement_progression_stats = progression
                return moved
        moved = int(self._try_deposit_food_to_nearby_storage(agent, amount=amount, hunger_before=hunger_before))
        if moved > 0:
            progression["reserve_refill_success"] = int(progression.get("reserve_refill_success", 0)) + 1
            progression["reserve_refill_food_added_total"] = int(progression.get("reserve_refill_food_added_total", 0)) + int(moved)
            tick_now = int(getattr(self, "tick", 0))
            last_tick = int(progression.get("reserve_last_refill_tick", -1))
            if last_tick >= 0:
                progression["reserve_refill_interval_ticks_total"] = int(
                    progression.get("reserve_refill_interval_ticks_total", 0)
                ) + max(0, tick_now - last_tick)
                progression["reserve_refill_interval_ticks_samples"] = int(
                    progression.get("reserve_refill_interval_ticks_samples", 0)
                ) + 1
            progression["reserve_last_refill_tick"] = int(tick_now)
            self.settlement_progression_stats = progression
            return int(moved)
        if int(amount) > 0 and had_food_before > 0:
            pressure = self.compute_local_food_pressure_for_agent(agent, max_distance=10)
            if not isinstance(pressure, dict):
                pressure = {}
            supply = int(pressure.get("near_food_sources", 0)) + int(pressure.get("camp_food", 0)) + int(
                pressure.get("house_food_nearby", 0)
            )
            demand = int(pressure.get("nearby_needy_agents", 0))
            has_surplus = bool(supply >= max(2, demand + 1))
            stable_context = bool(
                str(getattr(agent, "village_affiliation_status", "")) in {"attached", "resident"}
                or isinstance(self.nearest_active_camp_for_agent(agent, max_distance=2), dict)
            )
            if bool(pressure.get("pressure_active", False)):
                progression["reserve_refill_blocked_by_pressure"] = int(
                    progression.get("reserve_refill_blocked_by_pressure", 0)
                ) + 1
            elif not has_surplus:
                progression["reserve_refill_blocked_by_no_surplus"] = int(
                    progression.get("reserve_refill_blocked_by_no_surplus", 0)
                ) + 1
            elif not stable_context:
                progression["reserve_refill_blocked_by_unstable_context"] = int(
                    progression.get("reserve_refill_blocked_by_unstable_context", 0)
                ) + 1
            else:
                progression["reserve_refill_blocked_by_other"] = int(
                    progression.get("reserve_refill_blocked_by_other", 0)
                ) + 1
        self.settlement_progression_stats = progression
        return int(moved)

    def record_food_consumption(self, source: str, *, amount: int = 1, agent: Optional[Agent] = None) -> None:
        qty = max(0, int(amount))
        if qty <= 0:
            return
        stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
        src = str(source or "")
        if src == "inventory":
            stats["food_consumed_from_inventory"] = int(stats.get("food_consumed_from_inventory", 0)) + qty
        elif src == "camp":
            stats["food_consumed_from_camp"] = int(stats.get("food_consumed_from_camp", 0)) + qty
        elif src == "domestic":
            stats["food_consumed_from_domestic"] = int(stats.get("food_consumed_from_domestic", 0)) + qty
        elif src == "storage":
            stats["food_consumed_from_storage"] = int(stats.get("food_consumed_from_storage", 0)) + qty
        elif src == "wild_direct":
            stats["food_consumed_from_wild_direct"] = int(stats.get("food_consumed_from_wild_direct", 0)) + qty
        self.camp_food_stats = stats
        progression = self.settlement_progression_stats if isinstance(self.settlement_progression_stats, dict) else _default_settlement_progression_stats()
        if src == "inventory" and isinstance(agent, Agent):
            last_handoff_tick = int(getattr(agent, "last_local_handoff_received_tick", -10_000))
            if int(getattr(self, "tick", 0)) - last_handoff_tick <= 60:
                hunger_pre = float(
                    getattr(agent, "last_local_handoff_hunger_pre", float(getattr(agent, "hunger", 0.0)))
                )
                hunger_now = float(getattr(agent, "hunger", 0.0))
                hunger_relief = max(0.0, hunger_now - hunger_pre)
                if hunger_relief > 0.0:
                    progression["hunger_relief_after_local_handoff_total"] = float(
                        progression.get("hunger_relief_after_local_handoff_total", 0.0)
                    ) + float(hunger_relief)
                    progression["hunger_relief_after_local_handoff_samples"] = int(
                        progression.get("hunger_relief_after_local_handoff_samples", 0)
                    ) + 1
                    setattr(agent, "last_local_handoff_hunger_pre", hunger_now)
        self.settlement_progression_stats = progression
        if src in {"inventory", "wild_direct"}:
            self.record_food_security_flow("self_feeding", amount=qty)
        elif src in {"camp", "domestic", "storage"}:
            self.record_food_security_flow("reserve_draw", amount=qty)
            progression = self.settlement_progression_stats if isinstance(self.settlement_progression_stats, dict) else _default_settlement_progression_stats()
            if isinstance(agent, Agent):
                progression["reserve_draw_hunger_sum"] = float(progression.get("reserve_draw_hunger_sum", 0.0)) + float(
                    getattr(agent, "hunger", 0.0)
                )
                progression["reserve_draw_hunger_samples"] = int(progression.get("reserve_draw_hunger_samples", 0)) + 1
                tick_now = int(getattr(self, "tick", 0))
                last_draw_tick = int(progression.get("reserve_last_draw_tick", -1))
                if last_draw_tick >= 0:
                    progression["reserve_draw_interval_ticks_total"] = int(
                        progression.get("reserve_draw_interval_ticks_total", 0)
                    ) + max(0, tick_now - last_draw_tick)
                    progression["reserve_draw_interval_ticks_samples"] = int(
                        progression.get("reserve_draw_interval_ticks_samples", 0)
                    ) + 1
                progression["reserve_last_draw_tick"] = int(tick_now)
                if hasattr(self, "compute_local_food_pressure_for_agent"):
                    try:
                        pressure = self.compute_local_food_pressure_for_agent(agent, max_distance=10)
                    except Exception:
                        pressure = {}
                else:
                    pressure = {}
                if isinstance(pressure, dict) and bool(pressure.get("pressure_active", False)):
                    progression["reserve_draw_events_during_food_stress"] = int(
                        progression.get("reserve_draw_events_during_food_stress", 0)
                    ) + 1
                else:
                    progression["reserve_draw_events_during_normal_conditions"] = int(
                        progression.get("reserve_draw_events_during_normal_conditions", 0)
                    ) + 1
                last_failed = int(getattr(agent, "last_failed_foraging_trip_tick", -10_000))
                if int(getattr(self, "tick", 0)) - last_failed <= 40:
                    progression["reserve_usage_after_failed_foraging_trip"] = int(
                        progression.get("reserve_usage_after_failed_foraging_trip", 0)
                    ) + 1
            self.settlement_progression_stats = progression
        if isinstance(agent, Agent):
            self.record_agent_food_relief(agent, source=src)
            self.record_behavior_activity("consume_food", x=int(agent.x), y=int(agent.y), agent=agent, count=qty)

    def record_food_security_flow(self, flow_type: str, *, amount: int = 1) -> None:
        qty = max(0, int(amount))
        if qty <= 0:
            return
        progression = (
            self.settlement_progression_stats
            if isinstance(self.settlement_progression_stats, dict)
            else _default_settlement_progression_stats()
        )
        flow = str(flow_type or "")
        if flow == "self_feeding":
            progression["food_self_feeding_events"] = int(progression.get("food_self_feeding_events", 0)) + 1
            progression["food_self_feeding_units"] = int(progression.get("food_self_feeding_units", 0)) + qty
        elif flow == "group_feeding":
            progression["food_group_feeding_events"] = int(progression.get("food_group_feeding_events", 0)) + 1
            progression["food_group_feeding_units"] = int(progression.get("food_group_feeding_units", 0)) + qty
        elif flow == "reserve_accumulation":
            progression["food_reserve_accumulation_events"] = int(
                progression.get("food_reserve_accumulation_events", 0)
            ) + 1
            progression["food_reserve_accumulation_units"] = int(
                progression.get("food_reserve_accumulation_units", 0)
            ) + qty
        elif flow == "reserve_draw":
            progression["food_reserve_draw_events"] = int(progression.get("food_reserve_draw_events", 0)) + 1
            progression["food_reserve_draw_units"] = int(progression.get("food_reserve_draw_units", 0)) + qty
        self.settlement_progression_stats = progression

    def run_local_food_handoff_pass(self) -> None:
        progression = (
            self.settlement_progression_stats
            if isinstance(self.settlement_progression_stats, dict)
            else _default_settlement_progression_stats()
        )
        alive_agents = [a for a in (self.agents or []) if getattr(a, "alive", False)]
        if not alive_agents:
            self.settlement_progression_stats = progression
            return
        tick_now = int(getattr(self, "tick", 0))
        for donor in alive_agents:
            donor_food = int(getattr(donor, "inventory", {}).get("food", 0))
            donor_hunger = float(getattr(donor, "hunger", 100.0))
            donor_camp = self.nearest_active_camp_for_agent(donor, max_distance=6)
            last_donor_handoff_tick = int(getattr(donor, "last_local_handoff_donor_tick", -10_000))
            if tick_now - last_donor_handoff_tick < int(LOCAL_HANDOFF_COOLDOWN_TICKS):
                progression["handoff_blocked_by_cooldown_count"] = int(
                    progression.get("handoff_blocked_by_cooldown_count", 0)
                ) + 1
                continue
            needy_any = False
            receiver_candidate: Optional[Agent] = None
            best_need_score = -1.0
            for receiver in alive_agents:
                if receiver is donor:
                    continue
                rx = int(getattr(receiver, "x", 0))
                ry = int(getattr(receiver, "y", 0))
                dist = abs(int(getattr(donor, "x", 0)) - rx) + abs(int(getattr(donor, "y", 0)) - ry)
                receiver_hunger = float(getattr(receiver, "hunger", 100.0))
                receiver_food = int(getattr(receiver, "inventory", {}).get("food", 0))
                is_needy = bool(
                    receiver_hunger < float(LOCAL_HANDOFF_RECEIVER_HUNGER_THRESHOLD)
                    and receiver_food <= 0
                )
                if not is_needy:
                    continue
                last_rescue_tick = int(getattr(receiver, "last_local_handoff_received_tick", -10_000))
                if tick_now - last_rescue_tick < int(LOCAL_HANDOFF_RECENT_RESCUE_TICKS):
                    progression["handoff_blocked_by_recent_rescue"] = int(
                        progression.get("handoff_blocked_by_recent_rescue", 0)
                    ) + 1
                    continue
                has_adjacent_food = False
                rx_i, ry_i = int(rx), int(ry)
                for fx, fy in self.food:
                    if abs(int(fx) - rx_i) + abs(int(fy) - ry_i) <= 1:
                        has_adjacent_food = True
                        break
                receiver_task = str(getattr(receiver, "task", "") or "")
                receiver_target = getattr(receiver, "task_target", None)
                receiver_has_viable_food_task = False
                if (
                    receiver_task == "gather_food_wild"
                    and isinstance(receiver_target, tuple)
                    and len(receiver_target) == 2
                ):
                    tx, ty = int(receiver_target[0]), int(receiver_target[1])
                    target_distance = abs(int(tx) - rx_i) + abs(int(ty) - ry_i)
                    receiver_has_viable_food_task = bool((tx, ty) in self.food and target_distance <= 1)
                if (
                    (has_adjacent_food or receiver_has_viable_food_task)
                    and receiver_hunger > float(LOCAL_HANDOFF_RECEIVER_CRITICAL_HUNGER_OVERRIDE)
                ):
                    progression["handoff_blocked_by_receiver_viability"] = int(
                        progression.get("handoff_blocked_by_receiver_viability", 0)
                    ) + 1
                    continue
                needy_any = True
                if dist > int(LOCAL_HANDOFF_MAX_DISTANCE):
                    continue
                receiver_camp = self.nearest_active_camp_for_agent(receiver, max_distance=6)
                if isinstance(donor_camp, dict):
                    donor_camp_id = str(donor_camp.get("camp_id", ""))
                    receiver_camp_id = str(receiver_camp.get("camp_id", "")) if isinstance(receiver_camp, dict) else ""
                    if donor_camp_id != receiver_camp_id:
                        progression["handoff_blocked_by_group_priority_count"] = int(
                            progression.get("handoff_blocked_by_group_priority_count", 0)
                        ) + 1
                        continue
                need_score = (
                    (float(LOCAL_HANDOFF_RECEIVER_HUNGER_THRESHOLD) - receiver_hunger)
                    + (2.0 if receiver_food <= 0 else 0.0)
                )
                if need_score > best_need_score:
                    best_need_score = float(need_score)
                    receiver_candidate = receiver

            if not needy_any:
                continue
            if donor_food < int(LOCAL_HANDOFF_DONOR_MIN_FOOD):
                progression["local_food_handoff_prevented_by_low_surplus"] = int(
                    progression.get("local_food_handoff_prevented_by_low_surplus", 0)
                ) + 1
                continue
            if donor_hunger < float(LOCAL_HANDOFF_DONOR_MIN_HUNGER):
                progression["local_food_handoff_prevented_by_donor_risk"] = int(
                    progression.get("local_food_handoff_prevented_by_donor_risk", 0)
                ) + 1
                continue
            if isinstance(donor_camp, dict) and int(donor_camp.get("food_cache", 0)) < 2:
                camp_food_now = int(donor_camp.get("food_cache", 0))
                progression["handoff_blocked_by_camp_fragility"] = int(
                    progression.get("handoff_blocked_by_camp_fragility", 0)
                ) + 1
                if receiver_hunger <= float(LOCAL_HANDOFF_RECEIVER_CRITICAL_HUNGER_OVERRIDE):
                    progression["handoff_blocked_by_camp_fragility_when_receiver_critical_count"] = int(
                        progression.get("handoff_blocked_by_camp_fragility_when_receiver_critical_count", 0)
                    ) + 1
                if donor_hunger >= float(LOCAL_HANDOFF_DONOR_MIN_HUNGER):
                    progression["handoff_blocked_by_camp_fragility_when_donor_safe_count"] = int(
                        progression.get("handoff_blocked_by_camp_fragility_when_donor_safe_count", 0)
                    ) + 1
                donor_pressure_ctx = self.compute_local_food_pressure_for_agent(donor, max_distance=8)
                pressure_active = bool(
                    isinstance(donor_pressure_ctx, dict) and donor_pressure_ctx.get("pressure_active", False)
                )
                if pressure_active:
                    progression["handoff_blocked_by_camp_fragility_context_pressure_count"] = int(
                        progression.get("handoff_blocked_by_camp_fragility_context_pressure_count", 0)
                    ) + 1
                else:
                    progression["handoff_blocked_by_camp_fragility_context_nonpressure_count"] = int(
                        progression.get("handoff_blocked_by_camp_fragility_context_nonpressure_count", 0)
                    ) + 1
                near_food = int(donor_pressure_ctx.get("near_food_sources", 0)) if isinstance(donor_pressure_ctx, dict) else 0
                nearby_needy = int(donor_pressure_ctx.get("nearby_needy_agents", 0)) if isinstance(donor_pressure_ctx, dict) else 0
                has_local_surplus = bool(donor_food >= 4 or (near_food >= 2 and nearby_needy <= 1))
                if has_local_surplus:
                    progression["handoff_blocked_by_camp_fragility_with_local_surplus_count"] = int(
                        progression.get("handoff_blocked_by_camp_fragility_with_local_surplus_count", 0)
                    ) + 1
                progression["handoff_blocked_by_camp_fragility_donor_food_sum"] = int(
                    progression.get("handoff_blocked_by_camp_fragility_donor_food_sum", 0)
                ) + int(donor_food)
                progression["handoff_blocked_by_camp_fragility_donor_food_samples"] = int(
                    progression.get("handoff_blocked_by_camp_fragility_donor_food_samples", 0)
                ) + 1
                progression["handoff_blocked_by_camp_fragility_receiver_hunger_sum"] = float(
                    progression.get("handoff_blocked_by_camp_fragility_receiver_hunger_sum", 0.0)
                ) + float(receiver_hunger)
                progression["handoff_blocked_by_camp_fragility_receiver_hunger_samples"] = int(
                    progression.get("handoff_blocked_by_camp_fragility_receiver_hunger_samples", 0)
                ) + 1
                progression["handoff_blocked_by_camp_fragility_camp_food_sum"] = int(
                    progression.get("handoff_blocked_by_camp_fragility_camp_food_sum", 0)
                ) + int(camp_food_now)
                progression["handoff_blocked_by_camp_fragility_camp_food_samples"] = int(
                    progression.get("handoff_blocked_by_camp_fragility_camp_food_samples", 0)
                ) + 1
                continue
            donor_pressure = self.compute_local_food_pressure_for_agent(donor, max_distance=8)
            if (
                isinstance(donor_pressure, dict)
                and bool(donor_pressure.get("pressure_active", False))
                and (
                    bool(donor_pressure.get("unmet_pressure", False))
                    or (
                        int(donor_pressure.get("camp_food", 0)) <= 0
                        and int(donor_pressure.get("nearby_needy_agents", 0)) >= 3
                    )
                )
            ):
                progression["handoff_blocked_by_group_priority_count"] = int(
                    progression.get("handoff_blocked_by_group_priority_count", 0)
                ) + 1
                continue
            if receiver_candidate is None:
                progression["local_food_handoff_prevented_by_distance"] = int(
                    progression.get("local_food_handoff_prevented_by_distance", 0)
                ) + 1
                continue
            donor_id = str(getattr(donor, "id", id(donor)))
            last_from = str(getattr(receiver_candidate, "last_local_handoff_from_agent_id", ""))
            last_recv_tick = int(getattr(receiver_candidate, "last_local_handoff_received_tick", -10_000))
            if last_from == donor_id and (tick_now - last_recv_tick) < int(LOCAL_HANDOFF_PAIR_COOLDOWN_TICKS):
                progression["handoff_blocked_by_same_unit_recently_count"] = int(
                    progression.get("handoff_blocked_by_same_unit_recently_count", 0)
                ) + 1
                continue

            donor.inventory["food"] = max(0, int(donor.inventory.get("food", 0)) - 1)
            receiver_candidate.inventory["food"] = int(receiver_candidate.inventory.get("food", 0)) + 1
            setattr(donor, "last_local_handoff_donor_tick", tick_now)
            setattr(receiver_candidate, "last_local_handoff_received_tick", tick_now)
            setattr(receiver_candidate, "last_local_handoff_from_agent_id", donor_id)
            setattr(receiver_candidate, "last_local_handoff_hunger_pre", float(getattr(receiver_candidate, "hunger", 100.0)))
            progression["handoff_allowed_by_context_count"] = int(
                progression.get("handoff_allowed_by_context_count", 0)
            ) + 1
            progression["local_food_handoff_events"] = int(progression.get("local_food_handoff_events", 0)) + 1
            progression["local_food_handoff_units"] = int(progression.get("local_food_handoff_units", 0)) + 1
            self.record_behavior_activity("local_food_handoff", x=int(getattr(donor, "x", 0)), y=int(getattr(donor, "y", 0)), agent=donor)
        self.settlement_progression_stats = progression

    def record_food_search_failure(self, agent: Optional[Agent], *, resource_type: str = "food") -> None:
        if str(resource_type or "") != "food":
            return
        self.record_settlement_progression_metric("failed_food_seeking_attempts")
        if isinstance(agent, Agent):
            setattr(agent, "last_failed_food_search_tick", int(getattr(self, "tick", 0)))

    def record_food_search_fallback_activation(self, agent: Optional[Agent]) -> None:
        self.record_settlement_progression_metric("fallback_food_search_activations")
        if isinstance(agent, Agent):
            setattr(agent, "last_food_search_fallback_tick", int(getattr(self, "tick", 0)))

    def record_agent_food_inventory_acquired(self, agent: Optional[Agent], *, amount: int = 1, source: str = "") -> None:
        qty = max(0, int(amount))
        if qty <= 0 or not isinstance(agent, Agent):
            return
        tick_now = int(getattr(self, "tick", 0))
        progression = self.settlement_progression_stats if isinstance(self.settlement_progression_stats, dict) else _default_settlement_progression_stats()
        last_acq_tick = int(getattr(agent, "last_food_acquisition_tick", -1))
        if last_acq_tick >= 0:
            progression["food_acquisition_interval_ticks_total"] = int(
                progression.get("food_acquisition_interval_ticks_total", 0)
            ) + max(0, tick_now - last_acq_tick)
            progression["food_acquisition_interval_ticks_samples"] = int(
                progression.get("food_acquisition_interval_ticks_samples", 0)
            ) + 1
        progression["food_acquisition_events_total"] = int(
            progression.get("food_acquisition_events_total", 0)
        ) + 1
        last_pos = getattr(agent, "last_food_acquisition_pos", None)
        if isinstance(last_pos, tuple) and len(last_pos) == 2:
            dist = abs(int(last_pos[0]) - int(getattr(agent, "x", 0))) + abs(
                int(last_pos[1]) - int(getattr(agent, "y", 0))
            )
            progression["food_acquisition_distance_total"] = int(
                progression.get("food_acquisition_distance_total", 0)
            ) + int(max(0, dist))
            progression["food_acquisition_distance_samples"] = int(
                progression.get("food_acquisition_distance_samples", 0)
            ) + 1
        born_tick = int(getattr(agent, "born_tick", tick_now))
        age = max(0, tick_now - born_tick)
        if age <= 320:
            self.record_settlement_progression_metric("early_life_food_inventory_acquisition_count", qty)
        setattr(agent, "last_food_acquisition_tick", tick_now)
        setattr(agent, "last_food_acquisition_pos", (int(getattr(agent, "x", 0)), int(getattr(agent, "y", 0))))
        if str(source or "") == "wild_direct":
            setattr(agent, "last_wild_food_acquired_tick", tick_now)
        self.settlement_progression_stats = progression

    def record_agent_food_relief(self, agent: Optional[Agent], *, source: str = "") -> None:
        if not isinstance(agent, Agent):
            return
        tick_now = int(getattr(self, "tick", 0))
        progression = self.settlement_progression_stats if isinstance(self.settlement_progression_stats, dict) else _default_settlement_progression_stats()
        first_tick = int(getattr(agent, "first_food_relief_tick", -1))
        if first_tick < 0:
            setattr(agent, "first_food_relief_tick", tick_now)
            born_tick = int(getattr(agent, "born_tick", tick_now))
            latency = max(0, tick_now - born_tick)
            progression["time_spawn_to_first_food_acquisition_total"] = int(
                progression.get("time_spawn_to_first_food_acquisition_total", 0)
            ) + int(latency)
            progression["time_spawn_to_first_food_acquisition_samples"] = int(
                progression.get("time_spawn_to_first_food_acquisition_samples", 0)
            ) + 1
        last_consume_tick = int(getattr(agent, "last_food_consumption_tick", -1))
        if last_consume_tick >= 0:
            progression["food_consumption_interval_ticks_total"] = int(
                progression.get("food_consumption_interval_ticks_total", 0)
            ) + max(0, tick_now - last_consume_tick)
            progression["food_consumption_interval_ticks_samples"] = int(
                progression.get("food_consumption_interval_ticks_samples", 0)
            ) + 1
        setattr(agent, "last_food_consumption_tick", tick_now)
        high_hunger_enter_tick = int(getattr(agent, "high_hunger_enter_tick", -1))
        if high_hunger_enter_tick >= 0:
            latency = max(0, tick_now - high_hunger_enter_tick)
            progression["time_high_hunger_to_eat_total"] = int(progression.get("time_high_hunger_to_eat_total", 0)) + int(latency)
            progression["time_high_hunger_to_eat_samples"] = int(progression.get("time_high_hunger_to_eat_samples", 0)) + 1
            setattr(agent, "high_hunger_enter_tick", -1)
        self.settlement_progression_stats = progression

    def update_camp_food_decay(self) -> None:
        if int(getattr(self, "tick", 0)) % int(CAMP_FOOD_DECAY_INTERVAL_TICKS) != 0:
            return
        stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
        decayed = 0
        for camp in (self.camps or {}).values():
            if not isinstance(camp, dict):
                continue
            if not bool(camp.get("active", False)):
                camp["food_cache"] = 0
                continue
            food_now = max(0, int(camp.get("food_cache", 0)))
            if food_now > 0:
                camp["food_cache"] = food_now - 1
                decayed += 1
        if decayed > 0:
            stats["camp_food_decay"] = int(stats.get("camp_food_decay", 0)) + int(decayed)
            self.camp_food_stats = stats

    def compute_camp_food_snapshot(self) -> Dict[str, int]:
        camps = self.camps if isinstance(self.camps, dict) else {}
        total_food = 0
        camps_with_food = 0
        for camp in camps.values():
            if not isinstance(camp, dict):
                continue
            food = max(0, int(camp.get("food_cache", 0)))
            total_food += food
            if food > 0:
                camps_with_food += 1
        total_house_food = 0
        houses_with_food = 0
        house_capacity_total = 0
        for building in getattr(self, "buildings", {}).values():
            if not isinstance(building, dict):
                continue
            if str(building.get("type", "")) != "house":
                continue
            if str(building.get("operational_state", "")) != "active":
                continue
            house_food, house_capacity = self._ensure_house_food_state(building)
            total_house_food += int(house_food)
            house_capacity_total += int(house_capacity)
            if int(house_food) > 0:
                houses_with_food += 1
        stats = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
        total_consumed = int(stats.get("food_consumed_from_inventory", 0)) + int(stats.get("food_consumed_from_camp", 0)) + int(
            stats.get("food_consumed_from_storage", 0)
        ) + int(stats.get("food_consumed_from_domestic", 0)) + int(stats.get("food_consumed_from_wild_direct", 0))
        camp_consumed = int(stats.get("food_consumed_from_camp", 0))
        pressure_events = int(stats.get("local_food_pressure_events", 0))
        pressure_delivered = int(stats.get("pressure_backed_food_deliveries", 0))
        unmet_pressure = int(stats.get("unmet_food_pressure_count", 0))
        return {
            "total_food_in_camps": int(total_food),
            "camp_food_deposits": int(stats.get("camp_food_deposits", 0)),
            "camp_food_consumptions": int(stats.get("camp_food_consumptions", 0)),
            "camp_food_decay": int(stats.get("camp_food_decay", 0)),
            "camps_with_food": int(camps_with_food),
            "camp_food_deposit_attempts": int(stats.get("camp_food_deposit_attempts", 0)),
            "camp_food_deposit_blocked_low_hunger": int(stats.get("camp_food_deposit_blocked_low_hunger", 0)),
            "camp_food_deposit_blocked_self_reserve": int(stats.get("camp_food_deposit_blocked_self_reserve", 0)),
            "camp_food_consume_attempts": int(stats.get("camp_food_consume_attempts", 0)),
            "camp_food_consume_misses": int(stats.get("camp_food_consume_misses", 0)),
            "food_consumed_from_inventory": int(stats.get("food_consumed_from_inventory", 0)),
            "food_consumed_from_camp": int(stats.get("food_consumed_from_camp", 0)),
            "food_consumed_from_domestic": int(stats.get("food_consumed_from_domestic", 0)),
            "food_consumed_from_storage": int(stats.get("food_consumed_from_storage", 0)),
            "food_consumed_from_wild_direct": int(stats.get("food_consumed_from_wild_direct", 0)),
            "total_food_in_houses": int(total_house_food),
            "houses_with_food": int(houses_with_food),
            "domestic_food_stored_total": int(stats.get("domestic_food_stored_total", 0)),
            "domestic_food_consumed_total": int(stats.get("domestic_food_consumed_total", 0)),
            "domestic_storage_full_events": int(stats.get("domestic_storage_full_events", 0)),
            "house_food_distribution_events": int(stats.get("house_food_distribution_events", 0)),
            "house_food_capacity_utilization": round(float(total_house_food) / float(max(1, house_capacity_total)), 4),
            "camp_food_pressure_ticks": int(stats.get("camp_food_pressure_ticks", 0)),
            "local_food_pressure_events": int(pressure_events),
            "pressure_backed_loop_selected_count": int(stats.get("pressure_backed_loop_selected_count", 0)),
            "pressure_backed_food_deliveries": int(pressure_delivered),
            "unmet_food_pressure_count": int(unmet_pressure),
            "loop_completed_count": int(stats.get("loop_completed_count", 0)),
            "loop_abandoned_count": int(stats.get("loop_abandoned_count", 0)),
            "loop_abandoned_due_to_no_source": int(stats.get("loop_abandoned_due_to_no_source", 0)),
            "loop_abandoned_due_to_saturated_cache": int(stats.get("loop_abandoned_due_to_saturated_cache", 0)),
            "loop_abandoned_due_to_no_drop_target": int(stats.get("loop_abandoned_due_to_no_drop_target", 0)),
            "near_complete_loop_opportunities": int(stats.get("near_complete_loop_opportunities", 0)),
            "near_complete_loop_completed": int(stats.get("near_complete_loop_completed", 0)),
            "near_complete_loop_abandoned": int(stats.get("near_complete_loop_abandoned", 0)),
            "completion_bias_applied_count": int(stats.get("completion_bias_applied_count", 0)),
            "delivery_commitment_retained_ticks": int(stats.get("delivery_commitment_retained_ticks", 0)),
            "loop_retarget_success_count": int(stats.get("loop_retarget_success_count", 0)),
            "loop_retarget_failure_count": int(stats.get("loop_retarget_failure_count", 0)),
            "pressure_served_ratio": round(float(pressure_delivered) / float(max(1, pressure_events + unmet_pressure)), 4),
            "camp_food_consumption_share": round(float(camp_consumed) / float(max(1, total_consumed)), 4),
        }

    def compute_food_patch_snapshot(self) -> Dict[str, int]:
        patches = self.food_rich_patches if isinstance(self.food_rich_patches, list) else []
        total_area = 0
        for patch in patches:
            if not isinstance(patch, dict):
                continue
            r = max(0, int(patch.get("radius", 0)))
            total_area += int(3.14159 * float(r * r))
        return {
            "food_patch_count": int(len([p for p in patches if isinstance(p, dict)])),
            "food_patch_total_area": int(total_area),
            "food_patch_food_spawned": int(getattr(self, "food_patch_food_spawned", 0)),
        }

    def compute_communication_snapshot(self) -> Dict[str, int]:
        stats = self.communication_stats if isinstance(self.communication_stats, dict) else _default_communication_stats()
        out = _default_communication_stats()
        for k in out.keys():
            out[k] = int(stats.get(k, 0))
        return out

    def _proto_specialization_context(self, agent: Agent) -> Dict[str, Any]:
        active_camp = self.nearest_active_camp_for_agent(agent, max_distance=8)
        has_any_camp = False
        has_inactive_camp = False
        if isinstance(self.camps, dict):
            for camp in self.camps.values():
                if not isinstance(camp, dict):
                    continue
                cx, cy = int(camp.get("x", 0)), int(camp.get("y", 0))
                dist = abs(int(getattr(agent, "x", 0)) - cx) + abs(int(getattr(agent, "y", 0)) - cy)
                if dist > 8:
                    continue
                has_any_camp = True
                if not bool(camp.get("active", False)):
                    has_inactive_camp = True
                    break
        camp = active_camp if isinstance(active_camp, dict) else None
        if not isinstance(camp, dict):
            return {
                "has_active_camp": False,
                "has_any_camp": bool(has_any_camp),
                "has_inactive_camp": bool(has_inactive_camp),
                "camp": None,
                "camp_food": 0,
                "near_food": 0,
                "near_material": 0,
                "nearby_agents": 0,
                "houses_near": False,
            }
        cx, cy = int(camp.get("x", 0)), int(camp.get("y", 0))
        camp_food = max(0, int(camp.get("food_cache", 0)))
        near_food = 0
        near_material = 0
        for fx, fy in self.food:
            if abs(int(fx) - cx) + abs(int(fy) - cy) <= 8:
                near_food += 1
                if near_food >= 3:
                    break
        for wx, wy in self.wood:
            if abs(int(wx) - cx) + abs(int(wy) - cy) <= 8:
                near_material += 1
                if near_material >= 2:
                    break
        for sx, sy in self.stone:
            if abs(int(sx) - cx) + abs(int(sy) - cy) <= 8:
                near_material += 1
                if near_material >= 2:
                    break
        nearby_agents = 0
        for other in self.agents:
            if not getattr(other, "alive", False):
                continue
            if abs(int(getattr(other, "x", 0)) - cx) + abs(int(getattr(other, "y", 0)) - cy) <= 6:
                nearby_agents += 1
        houses_near = any(
            isinstance(b, dict)
            and str(b.get("type", "")) == "house"
            and str(b.get("operational_state", "")) == "active"
            and abs(int(b.get("x", 0)) - cx) + abs(int(b.get("y", 0)) - cy) <= 8
            for b in self.buildings.values()
        )
        return {
            "has_active_camp": True,
            "has_any_camp": True,
            "has_inactive_camp": bool(has_inactive_camp),
            "camp": camp,
            "camp_id": str(camp.get("camp_id", "")),
            "camp_pos": (int(cx), int(cy)),
            "camp_food": int(camp_food),
            "near_food": int(near_food),
            "near_material": int(near_material),
            "nearby_agents": int(nearby_agents),
            "houses_near": bool(houses_near),
        }

    def _find_nearest_food_to(self, x: int, y: int, *, radius: int = 10) -> Optional[Coord]:
        candidates: List[Tuple[int, int, int]] = []
        for fx, fy in self.food:
            dist = abs(int(fx) - int(x)) + abs(int(fy) - int(y))
            if dist <= int(radius):
                candidates.append((dist, int(fx), int(fy)))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        return (int(candidates[0][1]), int(candidates[0][2]))

    def find_scarcity_adaptive_food_target(
        self,
        agent: Agent,
        *,
        radius: int = 12,
    ) -> Optional[Coord]:
        origin_x = int(getattr(agent, "x", 0))
        origin_y = int(getattr(agent, "y", 0))
        pressure = self.compute_local_food_pressure_for_agent(agent, max_distance=LOCAL_FOOD_PRESSURE_RADIUS)
        severe_pressure = bool(
            isinstance(pressure, dict)
            and bool(pressure.get("pressure_active", False))
            and int(pressure.get("near_food_sources", 0)) <= 0
            and int(pressure.get("camp_food", 0)) <= 1
            and int(pressure.get("house_food_nearby", 0)) <= 1
        )
        if severe_pressure and bool(pressure.get("has_camp", False)):
            camp = self.nearest_active_camp_for_agent(agent, max_distance=LOCAL_FOOD_PRESSURE_RADIUS)
            if isinstance(camp, dict):
                origin_x = int(camp.get("x", origin_x))
                origin_y = int(camp.get("y", origin_y))

        search_radius = max(8, int(radius) + (8 if severe_pressure else 0))
        candidate_rows: List[Tuple[float, int, int, int, int]] = []
        for fx, fy in self.food:
            dist_origin = abs(int(fx) - origin_x) + abs(int(fy) - origin_y)
            if dist_origin > search_radius:
                continue
            dist_agent = abs(int(fx) - int(getattr(agent, "x", 0))) + abs(int(fy) - int(getattr(agent, "y", 0)))
            local_food_cluster = 0
            for ox, oy in self.food:
                if abs(int(ox) - int(fx)) + abs(int(oy) - int(fy)) <= 2:
                    local_food_cluster += 1
                    if local_food_cluster >= 6:
                        break
            contention = 0
            for other in self.agents:
                if not getattr(other, "alive", False):
                    continue
                if str(getattr(other, "agent_id", "")) == str(getattr(agent, "agent_id", "")):
                    continue
                if str(getattr(other, "task", "")) not in {"gather_food_wild", "farm_cycle"}:
                    continue
                target = getattr(other, "task_target", None)
                if isinstance(target, tuple) and len(target) == 2:
                    if abs(int(target[0]) - int(fx)) + abs(int(target[1]) - int(fy)) <= 1:
                        contention += 1
                elif abs(int(getattr(other, "x", 0)) - int(fx)) + abs(int(getattr(other, "y", 0)) - int(fy)) <= 1:
                    contention += 1
            patch_activity = float(self._patch_activity_score_at(int(fx), int(fy)))
            score = (
                float(local_food_cluster) * 1.8
                + float(patch_activity) * 0.18
                - float(dist_agent) * 0.22
                - float(contention) * 1.35
            )
            if severe_pressure:
                score += float(local_food_cluster) * 0.85
                score -= float(dist_origin) * 0.08
            candidate_rows.append((float(score), int(dist_agent), int(contention), int(fx), int(fy)))

        if not candidate_rows:
            return self._find_nearest_food_to(int(getattr(agent, "x", 0)), int(getattr(agent, "y", 0)), radius=search_radius)

        candidate_rows.sort(key=lambda row: (-float(row[0]), int(row[1]), int(row[2]), int(row[3]), int(row[4])))
        best = candidate_rows[0]
        if severe_pressure and hasattr(self, "record_settlement_progression_metric"):
            self.record_settlement_progression_metric("food_scarcity_adaptive_retarget_events")
        return (int(best[3]), int(best[4]))

    def _find_proto_builder_target(self, camp_pos: Coord) -> Optional[Coord]:
        cx, cy = int(camp_pos[0]), int(camp_pos[1])
        for radius in (2, 3, 4, 5):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if abs(dx) + abs(dy) > radius:
                        continue
                    tx = cx + dx
                    ty = cy + dy
                    if tx < 1 or ty < 1 or tx >= self.width - 1 or ty >= self.height - 1:
                        continue
                    if self.can_place_building("house", tx, ty):
                        return (int(tx), int(ty))
        return None

    def _acquire_proto_task_anchor(self, agent: Agent, specialization: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        camp = context.get("camp")
        if not isinstance(camp, dict):
            return None
        camp_id = str(context.get("camp_id", "") or camp.get("camp_id", ""))
        camp_pos = tuple(context.get("camp_pos", (int(camp.get("x", 0)), int(camp.get("y", 0)))))
        if len(camp_pos) != 2:
            return None
        tick_now = int(getattr(self, "tick", 0))
        anchor: Dict[str, Any] = {
            "anchor_type": str(specialization),
            "role_loop_type": str(specialization),
            "camp_id": camp_id,
            "village_uid": str(camp.get("village_uid", "") or ""),
            "target_pos": [int(camp_pos[0]), int(camp_pos[1])],
            "drop_pos": [int(camp_pos[0]), int(camp_pos[1])],
            "source_pos": [],
            "assigned_tick": tick_now,
            "last_validated_tick": tick_now,
            "expiry_tick": tick_now + int(PROTO_SPECIALIZATION_PERSISTENCE_TICKS.get(specialization, 14)),
        }
        if specialization in {"food_gatherer", "food_hauler"}:
            source = self._find_nearest_food_to(int(camp_pos[0]), int(camp_pos[1]), radius=10)
            if source is None and int(getattr(agent, "inventory", {}).get("food", 0)) <= 0:
                return None
            if isinstance(source, tuple):
                anchor["source_pos"] = [int(source[0]), int(source[1])]
        elif specialization == "builder":
            target = self._find_proto_builder_target((int(camp_pos[0]), int(camp_pos[1])))
            if target is None:
                return None
            anchor["target_pos"] = [int(target[0]), int(target[1])]
        return anchor

    def _validate_proto_task_anchor(self, agent: Agent, specialization: str, anchor: Dict[str, Any], context: Dict[str, Any]) -> Tuple[bool, str]:
        if not isinstance(anchor, dict):
            return (False, "anchor_missing")
        if float(getattr(agent, "hunger", 100.0)) < 20.0:
            return (False, "critical_hunger")
        camp_id = str(anchor.get("camp_id", "") or "")
        camp = (self.camps or {}).get(camp_id) if camp_id else None
        if not isinstance(camp, dict):
            return (False, "anchor_missing")
        if not bool(camp.get("active", False)):
            return (False, "camp_not_active")
        camp_food = max(0, int(camp.get("food_cache", 0)))
        source = anchor.get("source_pos", [])
        if specialization == "food_gatherer":
            if camp_food > 3:
                return (False, "no_local_need")
            if isinstance(source, list) and len(source) == 2:
                if (int(source[0]), int(source[1])) not in self.food:
                    replacement = self._find_nearest_food_to(int(camp.get("x", 0)), int(camp.get("y", 0)), radius=10)
                    if isinstance(replacement, tuple):
                        anchor["source_pos"] = [int(replacement[0]), int(replacement[1])]
                        self.record_loop_retarget_outcome(success=True)
                    else:
                        self.record_loop_retarget_outcome(success=False)
                        return (False, "target_missing")
            elif self._find_nearest_food_to(int(camp.get("x", 0)), int(camp.get("y", 0)), radius=10) is None:
                self.record_loop_retarget_outcome(success=False)
                return (False, "local_loop_broken")
        elif specialization == "food_hauler":
            if camp_food > 4:
                return (False, "no_local_need")
            if int(getattr(agent, "inventory", {}).get("food", 0)) <= 0:
                if isinstance(source, list) and len(source) == 2:
                    if (int(source[0]), int(source[1])) not in self.food:
                        replacement = self._find_nearest_food_to(int(camp.get("x", 0)), int(camp.get("y", 0)), radius=10)
                        if isinstance(replacement, tuple):
                            anchor["source_pos"] = [int(replacement[0]), int(replacement[1])]
                            self.record_loop_retarget_outcome(success=True)
                        else:
                            self.record_loop_retarget_outcome(success=False)
                            return (False, "target_missing")
                elif self._find_nearest_food_to(int(camp.get("x", 0)), int(camp.get("y", 0)), radius=10) is None:
                    self.record_loop_retarget_outcome(success=False)
                    return (False, "local_loop_broken")
        elif specialization == "builder":
            t = anchor.get("target_pos", [])
            if not (isinstance(t, list) and len(t) == 2):
                return (False, "anchor_invalid")
            tx, ty = int(t[0]), int(t[1])
            if not self.can_place_building("house", tx, ty):
                return (False, "target_missing")
        return (True, "")

    def _proto_specialization_valid_for_context(self, agent: Agent, specialization: str, context: Dict[str, Any]) -> bool:
        if specialization not in {"food_gatherer", "food_hauler", "builder"}:
            return False
        if float(getattr(agent, "hunger", 100.0)) < 20.0:
            return False
        if not bool(context.get("has_active_camp", False)):
            return False
        camp_food = int(context.get("camp_food", 0))
        near_food = int(context.get("near_food", 0))
        near_material = int(context.get("near_material", 0))
        nearby_agents = int(context.get("nearby_agents", 0))
        houses_near = bool(context.get("houses_near", False))
        has_carried_food = int(getattr(agent, "inventory", {}).get("food", 0)) > 0
        if specialization == "food_hauler":
            return bool(camp_food <= 2 and (has_carried_food or near_food > 0))
        if specialization == "food_gatherer":
            return bool(camp_food <= 2 and near_food > 0)
        return bool(
            camp_food >= 2
            and not houses_near
            and nearby_agents >= 2
            and near_material > 0
            and float(getattr(agent, "hunger", 100.0)) >= 35.0
        )

    def compute_agent_proto_specialization(self, agent: Agent) -> str:
        if not getattr(agent, "alive", False) or getattr(agent, "is_player", False):
            return "none"
        if float(getattr(agent, "hunger", 100.0)) < 20.0:
            return "none"
        context = self._proto_specialization_context(agent)
        if not bool(context.get("has_active_camp", False)):
            return "none"
        camp_food = int(context.get("camp_food", 0))
        near_food = int(context.get("near_food", 0))
        near_material = int(context.get("near_material", 0))
        nearby_agents = int(context.get("nearby_agents", 0))
        houses_near = bool(context.get("houses_near", False))
        has_carried_food = int(getattr(agent, "inventory", {}).get("food", 0)) > 0
        if camp_food <= 1 and has_carried_food:
            return "food_hauler"
        if camp_food <= 2 and near_food > 0:
            return "food_gatherer"
        if (
            camp_food >= 2
            and not houses_near
            and nearby_agents >= 2
            and near_material > 0
            and float(getattr(agent, "hunger", 100.0)) >= 35.0
        ):
            return "builder"
        return "none"

    def _record_proto_specialization_cleared(self, reason: str) -> None:
        self.proto_specialization_cleared_count = int(getattr(self, "proto_specialization_cleared_count", 0)) + 1
        reasons = self.proto_specialization_cleared_reasons if isinstance(self.proto_specialization_cleared_reasons, dict) else {}
        key = str(reason or "opportunity_gone")
        reasons[key] = int(reasons.get(key, 0)) + 1
        self.proto_specialization_cleared_reasons = reasons

    def _record_proto_anchor_invalidation(self, reason: str) -> None:
        self.proto_specialization_anchor_invalidations = int(
            getattr(self, "proto_specialization_anchor_invalidations", 0)
        ) + 1
        reasons = getattr(self, "proto_specialization_anchor_invalidation_reasons", {})
        if not isinstance(reasons, dict):
            reasons = {}
        key = str(reason or "anchor_invalid")
        reasons[key] = int(reasons.get(key, 0)) + 1
        self.proto_specialization_anchor_invalidation_reasons = reasons

    def update_agent_proto_specialization(self, agent: Agent) -> None:
        if not getattr(agent, "alive", False) or getattr(agent, "is_player", False):
            setattr(agent, "proto_specialization", "none")
            setattr(agent, "proto_specialization_until_tick", -1)
            setattr(agent, "proto_task_anchor", {})
            return
        tick_now = int(getattr(self, "tick", 0))
        previous = str(getattr(agent, "proto_specialization", "none") or "none")
        until_tick = int(getattr(agent, "proto_specialization_until_tick", -1))
        current_anchor = getattr(agent, "proto_task_anchor", {})
        if not isinstance(current_anchor, dict):
            current_anchor = {}
        context = self._proto_specialization_context(agent)
        computed_spec = str(self.compute_agent_proto_specialization(agent) or "none")
        if computed_spec not in PROTO_SPECIALIZATION_KEYS:
            computed_spec = "none"
        next_spec = computed_spec
        cleared_recorded = False

        def _clear(reason: str) -> None:
            nonlocal next_spec, cleared_recorded
            if next_spec != "none":
                next_spec = "none"
            if previous != "none":
                self._record_proto_specialization_cleared(reason)
                cleared_recorded = True

        if previous != "none":
            if float(getattr(agent, "hunger", 100.0)) < 20.0:
                _clear("critical_hunger")
            elif not bool(context.get("has_active_camp", False)):
                _clear("camp_not_active" if bool(context.get("has_inactive_camp", False)) else "camp_missing")
            elif not self._proto_specialization_valid_for_context(agent, previous, context):
                _clear("no_local_need")
            else:
                anchor_ok, anchor_reason = self._validate_proto_task_anchor(agent, previous, current_anchor, context)
                if not anchor_ok:
                    reacquired = self._acquire_proto_task_anchor(agent, previous, context)
                    if isinstance(reacquired, dict):
                        current_anchor = reacquired
                        self.proto_specialization_anchor_assignments = int(
                            getattr(self, "proto_specialization_anchor_assignments", 0)
                        ) + 1
                        anchor_ok = True
                    else:
                        reason = str(anchor_reason or "anchor_invalid")
                        _clear(reason)
                        self._record_proto_anchor_invalidation(reason)
                if anchor_ok and tick_now <= until_tick:
                    # Keep valid local specialization/loop through its bounded persistence window.
                    next_spec = previous
                    self.proto_specialization_retained_ticks = int(
                        getattr(self, "proto_specialization_retained_ticks", 0)
                    ) + 1
                    self.proto_specialization_anchor_retained_ticks = int(
                        getattr(self, "proto_specialization_anchor_retained_ticks", 0)
                    ) + 1
                    current_anchor["last_validated_tick"] = tick_now
                elif anchor_ok and computed_spec == "none":
                    _clear("opportunity_gone")

        if previous != "none" and next_spec not in {"none", previous}:
            self._record_proto_specialization_cleared("replaced_by_higher_need")
            cleared_recorded = True

        agent.proto_specialization = next_spec
        if next_spec != "none":
            if previous != next_spec or not current_anchor:
                acquired = self._acquire_proto_task_anchor(agent, next_spec, context)
                if not isinstance(acquired, dict):
                    agent.proto_task_anchor = {}
                    agent.proto_specialization = "none"
                    agent.proto_specialization_until_tick = -1
                    if previous != "none" or not cleared_recorded:
                        self._record_proto_specialization_cleared("anchor_missing")
                    self._record_proto_anchor_invalidation("anchor_missing")
                    if previous != "none":
                        self.proto_specialization_switches = int(
                            getattr(self, "proto_specialization_switches", 0)
                        ) + 1
                    return
                current_anchor = acquired
                self.proto_specialization_anchor_assignments = int(
                    getattr(self, "proto_specialization_anchor_assignments", 0)
                ) + 1
            duration = int(PROTO_SPECIALIZATION_PERSISTENCE_TICKS.get(next_spec, 14))
            agent.proto_specialization_until_tick = tick_now + max(1, duration)
            if previous != next_spec:
                agent.proto_specialization_last_assigned_tick = tick_now
                self.proto_specialization_assigned_tick_count = int(
                    getattr(self, "proto_specialization_assigned_tick_count", 0)
                ) + 1
            current_anchor["last_validated_tick"] = tick_now
            current_anchor["expiry_tick"] = int(agent.proto_specialization_until_tick)
            agent.proto_task_anchor = current_anchor
        else:
            agent.proto_specialization_until_tick = -1
            agent.proto_task_anchor = {}
        if previous != str(getattr(agent, "proto_specialization", "none") or "none"):
            self.proto_specialization_switches = int(getattr(self, "proto_specialization_switches", 0)) + 1

    def compute_proto_specialization_snapshot(self) -> Dict[str, Any]:
        counts = {k: 0 for k in PROTO_SPECIALIZATION_KEYS}
        by_region: Dict[str, Dict[str, int]] = {}
        for agent in self.agents:
            if not getattr(agent, "alive", False):
                continue
            spec = str(getattr(agent, "proto_specialization", "none") or "none")
            if spec not in counts:
                spec = "none"
            counts[spec] += 1
            camp = self.nearest_active_camp_for_agent(agent, max_distance=8)
            if isinstance(camp, dict):
                region = self._region_key_for_pos(int(camp.get("x", 0)), int(camp.get("y", 0)))
                entry = by_region.get(region)
                if not isinstance(entry, dict):
                    entry = {
                        "proto_food_gatherer_count": 0,
                        "proto_food_hauler_count": 0,
                        "proto_builder_count": 0,
                    }
                    by_region[region] = entry
                if spec == "food_gatherer":
                    entry["proto_food_gatherer_count"] += 1
                elif spec == "food_hauler":
                    entry["proto_food_hauler_count"] += 1
                elif spec == "builder":
                    entry["proto_builder_count"] += 1
        return {
            "proto_food_gatherer_count": int(counts.get("food_gatherer", 0)),
            "proto_food_hauler_count": int(counts.get("food_hauler", 0)),
            "proto_builder_count": int(counts.get("builder", 0)),
            "proto_specialization_switches": int(getattr(self, "proto_specialization_switches", 0)),
            "proto_specialization_assigned_tick_count": int(getattr(self, "proto_specialization_assigned_tick_count", 0)),
            "proto_specialization_retained_ticks": int(getattr(self, "proto_specialization_retained_ticks", 0)),
            "proto_specialization_anchor_assignments": int(getattr(self, "proto_specialization_anchor_assignments", 0)),
            "proto_specialization_anchor_retained_ticks": int(getattr(self, "proto_specialization_anchor_retained_ticks", 0)),
            "proto_specialization_anchor_invalidations": int(getattr(self, "proto_specialization_anchor_invalidations", 0)),
            "proto_specialization_anchor_invalidation_reasons": dict(
                sorted((getattr(self, "proto_specialization_anchor_invalidation_reasons", {}) or {}).items(), key=lambda item: item[0])
            ),
            "proto_specialization_cleared_count": int(getattr(self, "proto_specialization_cleared_count", 0)),
            "proto_specialization_cleared_reasons": dict(sorted((getattr(self, "proto_specialization_cleared_reasons", {}) or {}).items(), key=lambda item: item[0])),
            "proto_specialization_by_region": dict(sorted(by_region.items(), key=lambda item: item[0])),
        }

    def record_camp_event(self, event_key: str, *, camp_id: Optional[str] = None, village_uid: Optional[str] = None) -> None:
        key = str(event_key).strip().lower()
        if key not in {"camp_return_events", "camp_rest_events"}:
            return
        stats = self.progression_stats if isinstance(self.progression_stats, dict) else _default_progression_stats()
        stats[key] = int(stats.get(key, 0)) + 1
        uid = str(village_uid or "")
        if not uid and camp_id is not None:
            camp = (self.camps or {}).get(str(camp_id), {})
            if isinstance(camp, dict):
                uid = str(camp.get("village_uid", "") or "")
        if uid:
            by_village = stats.setdefault("by_village", {})
            entry = by_village.get(uid)
            if not isinstance(entry, dict):
                entry = {
                    "camp_return_events": 0,
                    "camp_rest_events": 0,
                    "early_road_suppressed_count": 0,
                    "road_priority_deferred_reasons": {},
                    "road_built_with_purpose_count": 0,
                    "road_build_suppressed_no_purpose": 0,
                    "road_build_suppressed_reasons": {},
                }
                by_village[uid] = entry
            entry[key] = int(entry.get(key, 0)) + 1
        if camp_id is not None:
            camp = (self.camps or {}).get(str(camp_id))
            if isinstance(camp, dict):
                region = self._region_key_for_pos(int(camp.get("x", 0)), int(camp.get("y", 0)))
                if key == "camp_return_events":
                    camp["return_events"] = int(camp.get("return_events", 0)) + 1
                    self.record_camp_lifecycle_stage("camp_used_for_return", region=region)
                    self.record_behavior_activity("camp_return", x=int(camp.get("x", 0)), y=int(camp.get("y", 0)))
                elif key == "camp_rest_events":
                    camp["rest_events"] = int(camp.get("rest_events", 0)) + 1
                    self.record_camp_lifecycle_stage("camp_used_for_rest", region=region)
                    self.record_behavior_activity("camp_use", x=int(camp.get("x", 0)), y=int(camp.get("y", 0)))
                camp["last_active_tick"] = int(getattr(self, "tick", 0))
                camp["last_use_tick"] = int(getattr(self, "tick", 0))
                camp["active"] = True
        self.progression_stats = stats

    def record_situated_construction_event(self, event_key: str, count: int = 1) -> None:
        key = str(event_key).strip()
        stats = self.situated_construction_stats if isinstance(self.situated_construction_stats, dict) else _default_situated_construction_stats()
        if key not in stats:
            return
        stats[key] = int(stats.get(key, 0)) + max(0, int(count))
        self.situated_construction_stats = stats

    def compute_situated_construction_snapshot(self) -> Dict[str, int]:
        stats = self.situated_construction_stats if isinstance(self.situated_construction_stats, dict) else _default_situated_construction_stats()
        out = _default_situated_construction_stats()
        for k in out.keys():
            out[k] = int(stats.get(k, 0))
        return out

    def record_settlement_bottleneck(self, key: str, *, reason: Optional[str] = None, count: int = 1) -> None:
        metric = str(key).strip()
        stats = self.settlement_bottleneck_stats if isinstance(self.settlement_bottleneck_stats, dict) else _default_settlement_bottleneck_stats()
        if metric not in stats:
            return
        if metric in {
            "village_creation_blocked_reasons",
            "camp_to_village_transition_failure_reasons",
            "distant_cluster_pull_suppressed_reasons",
            "camp_absorption_reasons",
        }:
            r = str(reason or "unknown")
            reasons = stats.setdefault(metric, {})
            reasons[r] = int(reasons.get(r, 0)) + max(0, int(count))
        elif metric == "cluster_ecological_productivity_score_total":
            stats[metric] = float(stats.get(metric, 0.0)) + float(max(0, int(count)))
        else:
            stats[metric] = int(stats.get(metric, 0)) + max(0, int(count))
        self.settlement_bottleneck_stats = stats

    def compute_settlement_bottleneck_snapshot(self) -> Dict[str, Any]:
        stats = self.settlement_bottleneck_stats if isinstance(self.settlement_bottleneck_stats, dict) else _default_settlement_bottleneck_stats()
        support_total = int(stats.get("independent_cluster_support_score_total", 0))
        support_samples = int(stats.get("independent_cluster_support_score_samples", 0))
        eco_total_scaled = float(stats.get("cluster_ecological_productivity_score_total", 0.0))
        eco_samples = int(stats.get("cluster_ecological_productivity_score_samples", 0))
        active_camps = [
            c for c in (self.camps or {}).values()
            if isinstance(c, dict) and bool(c.get("active", False))
        ]
        cluster_pop = sorted([int(c.get("support_nearby_agents", 0)) for c in active_camps], reverse=True)
        top3 = cluster_pop[:3]
        secondary = cluster_pop[1:] if len(cluster_pop) > 1 else []
        return {
            "village_creation_attempts": int(stats.get("village_creation_attempts", 0)),
            "village_creation_blocked_count": int(stats.get("village_creation_blocked_count", 0)),
            "village_creation_blocked_reasons": {
                str(k): int(v) for k, v in ((stats.get("village_creation_blocked_reasons", {}) or {}).items())
            },
            "independent_cluster_count": int(stats.get("independent_cluster_count", 0)),
            "independent_cluster_support_score_summary": {
                "total": int(support_total),
                "samples": int(support_samples),
                "avg": round(float(support_total / max(1, support_samples)), 3),
            },
            "camp_to_village_transition_attempts": int(stats.get("camp_to_village_transition_attempts", 0)),
            "camp_to_village_transition_failures": int(stats.get("camp_to_village_transition_failures", 0)),
            "camp_to_village_transition_failure_reasons": {
                str(k): int(v) for k, v in ((stats.get("camp_to_village_transition_failure_reasons", {}) or {}).items())
            },
            "local_viable_camp_retained_count": int(stats.get("local_viable_camp_retained_count", 0)),
            "distant_cluster_pull_suppressed_count": int(stats.get("distant_cluster_pull_suppressed_count", 0)),
            "distant_cluster_pull_suppressed_reasons": {
                str(k): int(v) for k, v in ((stats.get("distant_cluster_pull_suppressed_reasons", {}) or {}).items())
            },
            "camp_absorption_events": int(stats.get("camp_absorption_events", 0)),
            "camp_absorption_reasons": {
                str(k): int(v) for k, v in ((stats.get("camp_absorption_reasons", {}) or {}).items())
            },
            "mature_nucleus_detected_count": int(stats.get("mature_nucleus_detected_count", 0)),
            "mature_nucleus_failed_transition_count": int(stats.get("mature_nucleus_failed_transition_count", 0)),
            "mature_nucleus_successful_transition_count": int(stats.get("mature_nucleus_successful_transition_count", 0)),
            "cluster_ecological_productivity_score": {
                "total": round(float(eco_total_scaled / 100.0), 3),
                "samples": int(eco_samples),
                "avg": round(float((eco_total_scaled / 100.0) / max(1, eco_samples)), 3),
            },
            "cluster_inertia_events": int(stats.get("cluster_inertia_events", 0)),
            "dominant_cluster_saturation_penalty_applied": int(stats.get("dominant_cluster_saturation_penalty_applied", 0)),
            "camp_absorption_delay_events": int(stats.get("camp_absorption_delay_events", 0)),
            "secondary_cluster_persistence_ticks": int(stats.get("secondary_cluster_persistence_ticks", 0)),
            "exploration_shift_due_to_low_density": int(stats.get("exploration_shift_due_to_low_density", 0)),
            "secondary_nucleus_structure_count": int(stats.get("secondary_nucleus_structure_count", 0)),
            "secondary_nucleus_build_support_events": int(stats.get("secondary_nucleus_build_support_events", 0)),
            "secondary_nucleus_material_delivery_events": int(stats.get("secondary_nucleus_material_delivery_events", 0)),
            "secondary_nucleus_materialization_ticks": int(stats.get("secondary_nucleus_materialization_ticks", 0)),
            "secondary_nucleus_absorption_during_build": int(stats.get("secondary_nucleus_absorption_during_build", 0)),
            "secondary_nucleus_materialization_success": int(stats.get("secondary_nucleus_materialization_success", 0)),
            "cluster_population_distribution_summary": {
                "active_cluster_count": int(len(cluster_pop)),
                "top_cluster_population": int(cluster_pop[0]) if cluster_pop else 0,
                "top3_cluster_population": [int(v) for v in top3],
                "secondary_cluster_avg_population": round(float(sum(secondary) / max(1, len(secondary))), 3) if secondary else 0.0,
                "secondary_cluster_nonzero_count": int(sum(1 for v in secondary if int(v) > 0)),
            },
        }

    def _active_house_buildings(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for b in (self.buildings or {}).values():
            if not isinstance(b, dict):
                continue
            if str(b.get("type", "")) != "house":
                continue
            if str(b.get("operational_state", "")) != "active":
                continue
            out.append(b)
        return out

    def _compute_house_cluster_sizes(self, *, link_distance: int = 4) -> List[int]:
        houses = self._active_house_buildings()
        if not houses:
            return []
        coords = [(int(h.get("x", 0)), int(h.get("y", 0))) for h in houses]
        n = len(coords)
        seen = [False] * n
        sizes: List[int] = []
        for i in range(n):
            if seen[i]:
                continue
            queue = [i]
            seen[i] = True
            size = 0
            while queue:
                idx = queue.pop()
                size += 1
                x, y = coords[idx]
                for j in range(n):
                    if seen[j]:
                        continue
                    ox, oy = coords[j]
                    if abs(x - ox) + abs(y - oy) <= int(link_distance):
                        seen[j] = True
                        queue.append(j)
            sizes.append(int(size))
        sizes.sort(reverse=True)
        return sizes

    def record_settlement_progression_build_event(self, building_type: str, building: Optional[Dict[str, Any]]) -> None:
        stats = self.settlement_progression_stats if isinstance(self.settlement_progression_stats, dict) else _default_settlement_progression_stats()
        btype = str(building_type or "").strip().lower()
        if btype == "house":
            if int(stats.get("first_house_completion_tick", -1)) < 0:
                stats["first_house_completion_tick"] = int(getattr(self, "tick", 0))
            self.settlement_progression_stats = stats
            return
        if btype != "storage":
            self.settlement_progression_stats = stats
            return
        if not isinstance(building, dict):
            self.settlement_progression_stats = stats
            return
        bid = str(building.get("building_id", ""))
        seen = stats.get("_seen_storage_ids", set())
        if not isinstance(seen, set):
            seen = set(str(v) for v in list(seen))
        if bid in seen:
            self.settlement_progression_stats = stats
            return
        seen.add(bid)
        stats["_seen_storage_ids"] = seen
        if int(stats.get("first_storage_completion_tick", -1)) < 0:
            stats["first_storage_completion_tick"] = int(getattr(self, "tick", 0))
        stats["storage_emergence_successes"] = int(stats.get("storage_emergence_successes", 0)) + 1
        stats["storage_construction_completed_count"] = int(stats.get("storage_construction_completed_count", 0)) + 1
        if int(stats.get("first_house_completion_tick", -1)) < 0:
            stats["storage_built_before_house_count"] = int(stats.get("storage_built_before_house_count", 0)) + 1
        village = self.get_village_by_id(building.get("village_id"))
        if village is not None and self.is_village_surplus_sustained(village):
            stats["surplus_storage_construction_completed"] = int(stats.get("surplus_storage_construction_completed", 0)) + 1
        bx, by = int(building.get("x", 0)), int(building.get("y", 0))
        nearby_houses = self.count_nearby_houses(bx, by, radius=8)
        if int(nearby_houses) >= 2:
            stats["storage_built_after_cluster_count"] = int(stats.get("storage_built_after_cluster_count", 0)) + 1
        else:
            stats["storage_built_without_cluster_count"] = int(stats.get("storage_built_without_cluster_count", 0)) + 1
        if int(nearby_houses) >= 3:
            stats["storage_supporting_active_house_cluster_count"] = int(stats.get("storage_supporting_active_house_cluster_count", 0)) + 1
        camp_food = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else _default_camp_food_stats()
        pressure = int(camp_food.get("domestic_storage_full_events", 0)) + int(camp_food.get("camp_food_pressure_ticks", 0)) // 12
        if int(nearby_houses) >= 3 and pressure >= 3:
            stats["storage_built_in_mature_cluster_count"] = int(stats.get("storage_built_in_mature_cluster_count", 0)) + 1
        self.settlement_progression_stats = stats

    def record_settlement_progression_metric(self, key: str, count: int = 1) -> None:
        metric = str(key or "").strip()
        stats = self.settlement_progression_stats if isinstance(self.settlement_progression_stats, dict) else _default_settlement_progression_stats()
        if metric not in stats:
            return
        stats[metric] = int(stats.get(metric, 0)) + max(0, int(count))
        self.settlement_progression_stats = stats

    def _practice_memory_key(self, x: int, y: int, practice_type: str) -> str:
        cell = max(1, int(CULTURAL_MEMORY_CELL_SIZE))
        return f"{str(practice_type)}:{int(x)//cell}:{int(y)//cell}"

    def record_local_practice(
        self,
        practice_type: str,
        *,
        x: int,
        y: int,
        weight: float = 1.0,
        decay_rate: float = 0.006,
    ) -> None:
        ptype = str(practice_type or "").strip()
        if not ptype:
            return
        key = self._practice_memory_key(int(x), int(y), ptype)
        memory = self.local_practice_memory if isinstance(self.local_practice_memory, dict) else {}
        now = int(getattr(self, "tick", 0))
        entry = memory.get(key)
        if not isinstance(entry, dict):
            entry = {
                "practice_type": ptype,
                "x": int(x),
                "y": int(y),
                "confidence": 0.0,
                "confirmations": 0,
                "last_observed_tick": now,
                "decay_rate": float(max(0.001, min(0.05, float(decay_rate)))),
            }
            memory[key] = entry
            self.record_settlement_progression_metric("cultural_practices_created")
        entry["confirmations"] = int(entry.get("confirmations", 0)) + 1
        confidence = float(entry.get("confidence", 0.0)) + max(0.05, float(weight)) * 0.45
        entry["confidence"] = float(min(float(CULTURAL_MEMORY_MAX_CONFIDENCE), confidence))
        entry["last_observed_tick"] = now
        self.record_settlement_progression_metric("cultural_practices_reinforced")
        self.local_practice_memory = memory

    def _decay_local_practice_memory(self) -> None:
        memory = self.local_practice_memory if isinstance(self.local_practice_memory, dict) else {}
        if not memory:
            self.local_practice_memory = {}
            return
        now = int(getattr(self, "tick", 0))
        next_memory: Dict[str, Dict[str, Any]] = {}
        for key, entry in memory.items():
            if not isinstance(entry, dict):
                continue
            idle_ticks = max(0, now - int(entry.get("last_observed_tick", now)))
            decay_rate = float(max(0.001, min(0.05, float(entry.get("decay_rate", 0.006)))))
            confidence = float(entry.get("confidence", 0.0))
            if idle_ticks > 0:
                confidence -= decay_rate * float(min(8, idle_ticks))
            if confidence < float(CULTURAL_MEMORY_MIN_CONFIDENCE):
                self.record_settlement_progression_metric("cultural_practices_decayed")
                continue
            kept = dict(entry)
            kept["confidence"] = float(round(confidence, 4))
            next_memory[str(key)] = kept
        self.local_practice_memory = next_memory

    def get_local_practice_bias(
        self,
        x: int,
        y: int,
        *,
        max_distance: int = CULTURAL_MEMORY_ACCESS_RADIUS,
    ) -> Dict[str, float]:
        out = {
            "productive_food_patch": 0.0,
            "good_gathering_zone": 0.0,
            "proto_farm_area": 0.0,
            "construction_cluster": 0.0,
            "stable_storage_area": 0.0,
            "any": 0.0,
        }
        memory = self.local_practice_memory if isinstance(self.local_practice_memory, dict) else {}
        if not memory:
            return out
        ax, ay = int(x), int(y)
        for entry in memory.values():
            if not isinstance(entry, dict):
                continue
            px = int(entry.get("x", 0))
            py = int(entry.get("y", 0))
            dist = abs(ax - px) + abs(ay - py)
            if dist > int(max_distance):
                continue
            ptype = str(entry.get("practice_type", ""))
            if ptype not in out:
                continue
            confidence = float(entry.get("confidence", 0.0))
            influence = max(0.0, confidence / float(1 + dist))
            out[ptype] = float(out.get(ptype, 0.0)) + influence
            out["any"] = float(out.get("any", 0.0)) + influence
        return {k: float(round(v, 4)) for k, v in out.items()}

    def _village_surplus_state(self, village: Dict[str, Any]) -> Dict[str, Any]:
        state = village.get("surplus_state")
        if not isinstance(state, dict):
            state = {
                "last_tick": int(getattr(self, "tick", 0)),
                "last_food_stock": 0.0,
                "last_resource_stock": 0.0,
                "food_surplus_rate": 0.0,
                "resource_surplus_rate": 0.0,
                "saturation_streak": 0,
                "last_saturated": False,
                "sustained": False,
            }
            village["surplus_state"] = state
        return state

    def update_village_surplus_state(self, village: Dict[str, Any]) -> Dict[str, Any]:
        state = self._village_surplus_state(village)
        center = village.get("center", {}) if isinstance(village.get("center"), dict) else {}
        cx = int(center.get("x", 0))
        cy = int(center.get("y", 0))
        vid = village.get("id")
        vuid = str(village.get("village_uid", "") or "")

        camp_food = 0
        camp_cap = 0
        for camp in (self.camps or {}).values():
            if not isinstance(camp, dict):
                continue
            if not bool(camp.get("active", False)):
                continue
            cvid = camp.get("village_id")
            cvuid = str(camp.get("village_uid", "") or "")
            if (vid is not None and cvid != vid) and (vuid and cvuid != vuid):
                continue
            if abs(int(camp.get("x", 0)) - cx) + abs(int(camp.get("y", 0)) - cy) > 10:
                continue
            camp_food += int(camp.get("food_cache", 0))
            camp_cap += int(CAMP_FOOD_CACHE_CAPACITY)

        house_food = 0
        house_cap = 0
        for b in (self.buildings or {}).values():
            if not isinstance(b, dict):
                continue
            if str(b.get("type", "")) != "house" or str(b.get("operational_state", "")) != "active":
                continue
            if (vid is not None and b.get("village_id") != vid) and (vuid and str(b.get("village_uid", "") or "") != vuid):
                continue
            if abs(int(b.get("x", 0)) - cx) + abs(int(b.get("y", 0)) - cy) > 10:
                continue
            house_food += int(b.get("domestic_food", 0))
            house_cap += int(b.get("domestic_food_capacity", HOUSE_DOMESTIC_FOOD_CAPACITY))

        storage = village.get("storage", {}) if isinstance(village.get("storage"), dict) else {}
        food_stock = float(camp_food + house_food + int(storage.get("food", 0)))
        resource_stock = float(int(storage.get("wood", 0)) + int(storage.get("stone", 0)))
        now = int(getattr(self, "tick", 0))
        dt = max(1, now - int(state.get("last_tick", now)))
        prev_food = float(state.get("last_food_stock", food_stock))
        prev_resource = float(state.get("last_resource_stock", resource_stock))
        food_delta_rate = (food_stock - prev_food) / float(dt)
        resource_delta_rate = (resource_stock - prev_resource) / float(dt)
        food_rate = float(state.get("food_surplus_rate", 0.0)) * 0.7 + float(food_delta_rate) * 0.3
        resource_rate = float(state.get("resource_surplus_rate", 0.0)) * 0.7 + float(resource_delta_rate) * 0.3
        saturation_now = bool(
            (camp_cap > 0 and float(camp_food) / float(max(1, camp_cap)) >= 0.6)
            or (house_cap > 0 and float(house_food) / float(max(1, house_cap)) >= 0.7)
        )
        if saturation_now and not bool(state.get("last_saturated", False)):
            self.record_settlement_progression_metric("buffer_saturation_events")
        streak = int(state.get("saturation_streak", 0))
        if food_rate > 0.03 and resource_rate >= -0.01 and saturation_now:
            streak += 1
        else:
            streak = max(0, streak - 1)
        sustained = bool(streak >= 4 or (food_rate > 0.08 and resource_rate > 0.02))

        state.update(
            {
                "last_tick": int(now),
                "last_food_stock": float(food_stock),
                "last_resource_stock": float(resource_stock),
                "food_surplus_rate": float(round(food_rate, 4)),
                "resource_surplus_rate": float(round(resource_rate, 4)),
                "saturation_streak": int(streak),
                "last_saturated": bool(saturation_now),
                "sustained": bool(sustained),
            }
        )
        village["surplus_state"] = state
        return state

    def is_village_surplus_sustained(self, village: Optional[Dict[str, Any]]) -> bool:
        if not isinstance(village, dict):
            return False
        state = self.update_village_surplus_state(village)
        return bool(state.get("sustained", False))

    def has_active_storage_construction_for_agent(self, agent: Agent) -> bool:
        village_id = getattr(agent, "village_id", None)
        for building in (self.buildings or {}).values():
            if not isinstance(building, dict):
                continue
            if str(building.get("type", "")) != "storage":
                continue
            if str(building.get("operational_state", "")) != "under_construction":
                continue
            if village_id is not None and building.get("village_id") != village_id:
                continue
            return True
        return False

    def has_active_construction_for_agent(self, agent: Agent) -> bool:
        village_id = getattr(agent, "village_id", None)
        for building in (self.buildings or {}).values():
            if not isinstance(building, dict):
                continue
            if str(building.get("type", "")) not in {"house", "storage"}:
                continue
            if str(building.get("operational_state", "")) != "under_construction":
                continue
            if village_id is not None and building.get("village_id") != village_id:
                continue
            return True
        return False

    def storage_builder_continuity_bonus(self, agent: Agent, task_name: str) -> int:
        if str(task_name) != "build_storage":
            return 0
        if float(getattr(agent, "hunger", 100.0)) < 24.0:
            return 0
        if not self.has_active_storage_construction_for_agent(agent):
            return 0
        return 8

    def storage_delivery_priority_bonus(self, agent: Agent, site: Dict[str, Any], *, record_event: bool = False) -> int:
        if not isinstance(site, dict):
            return 0
        if str(site.get("type", "")) != "storage":
            return 0
        if str(site.get("operational_state", "")) != "under_construction":
            return 0
        if float(getattr(agent, "hunger", 100.0)) < 24.0:
            return 0
        sx = int(site.get("x", 0))
        sy = int(site.get("y", 0))
        houses = int(self.count_nearby_houses(sx, sy, radius=8))
        if houses < 3:
            return 0
        progress = int(site.get("construction_progress", 0))
        required = max(1, int(site.get("construction_required_work", 1)))
        progress_bonus = min(6, int((float(progress) / float(required)) * 6.0))
        bonus = 8 + int(progress_bonus)
        return int(bonus)

    def try_direct_material_drop_to_nearby_construction(self, agent: Agent, *, max_distance: int = 2) -> int:
        if float(getattr(agent, "hunger", 100.0)) < 20.0:
            return 0
        inv = getattr(agent, "inventory", {}) if isinstance(getattr(agent, "inventory", {}), dict) else {}
        if int(inv.get("wood", 0)) <= 0 and int(inv.get("stone", 0)) <= 0 and int(inv.get("food", 0)) <= 0:
            return 0
        village_id = getattr(agent, "village_id", None)
        candidates = []
        for b in (self.buildings or {}).values():
            if not isinstance(b, dict):
                continue
            if str(b.get("type", "")) not in {"house", "storage"}:
                continue
            if str(b.get("operational_state", "")) != "under_construction":
                continue
            if village_id is not None and b.get("village_id") != village_id:
                continue
            bx, by = int(b.get("x", 0)), int(b.get("y", 0))
            dist = abs(int(agent.x) - bx) + abs(int(agent.y) - by)
            if dist > int(max_distance):
                continue
            try:
                needs = building_system.get_outstanding_construction_needs(b)
            except Exception:
                needs = {}
            outstanding = int(needs.get("wood", 0)) + int(needs.get("stone", 0)) + int(needs.get("food", 0))
            if outstanding <= 0:
                continue
            progress = int(b.get("construction_progress", 0))
            required = max(1, int(b.get("construction_required_work", 1)))
            progress_ratio = float(progress) / float(required)
            local_bonus = 0
            if hasattr(self, "secondary_nucleus_delivery_priority"):
                try:
                    local_bonus += int(self.secondary_nucleus_delivery_priority(agent, b))
                except Exception:
                    pass
            if hasattr(self, "storage_delivery_priority_bonus"):
                try:
                    local_bonus += int(self.storage_delivery_priority_bonus(agent, b))
                except Exception:
                    pass
            candidates.append((-int(local_bonus), -float(progress_ratio), dist, str(b.get("building_id", "")), b, needs))
        if not candidates:
            return 0
        candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
        _neg_bonus, _neg_prog, _dist, _bid, site, needs = candidates[0]
        buf = site.get("construction_buffer")
        if not isinstance(buf, dict):
            buf = {"wood": 0, "stone": 0, "food": 0}
            site["construction_buffer"] = buf
        moved = 0
        for resource in ("wood", "stone", "food"):
            need = max(0, int(needs.get(resource, 0)))
            have = max(0, int(inv.get(resource, 0)))
            qty = min(need, have)
            if qty <= 0:
                continue
            inv[resource] = have - qty
            buf[resource] = int(buf.get(resource, 0)) + qty
            moved += qty
            self.record_settlement_progression_metric(f"construction_material_delivery_{resource}_units", int(qty))
            site[f"construction_delivered_{resource}_units"] = int(site.get(f"construction_delivered_{resource}_units", 0)) + int(qty)
        if moved <= 0:
            return 0
        site["construction_buffer"] = buf
        site["construction_last_demand_tick"] = int(getattr(self, "tick", 0))
        site_dist = abs(int(agent.x) - int(site.get("x", 0))) + abs(int(agent.y) - int(site.get("y", 0)))
        self.record_settlement_progression_metric("construction_delivery_attempts", 1)
        self.record_settlement_progression_metric("construction_delivery_successes", 1)
        self.record_settlement_progression_metric("construction_delivery_to_site_events", 1)
        self.record_settlement_progression_metric("construction_delivery_distance_to_site_sum", int(site_dist))
        self.record_settlement_progression_metric("construction_delivery_distance_to_site_samples", 1)
        self.record_settlement_progression_metric("construction_delivery_distance_to_source_sum", 0)
        self.record_settlement_progression_metric("construction_delivery_distance_to_source_samples", 1)
        self.record_settlement_progression_metric("construction_material_delivery_events", int(moved))
        progress = int(site.get("construction_progress", 0))
        if progress > 0 or int(site.get("builder_waiting_tick", -10_000)) >= int(getattr(self, "tick", 0)) - 24:
            self.record_settlement_progression_metric("construction_material_delivery_to_active_site", int(moved))
        if str(site.get("type", "")) == "storage":
            self.record_settlement_progression_metric("storage_delivery_successes")
        elif str(site.get("type", "")) == "house":
            self.record_settlement_progression_metric("house_delivery_successes")
        site["construction_delivered_units"] = int(site.get("construction_delivered_units", 0)) + int(moved)
        site["construction_last_delivery_tick"] = int(getattr(self, "tick", 0))
        if int(site.get("construction_first_delivery_tick", -1)) < 0:
            site["construction_first_delivery_tick"] = int(getattr(self, "tick", 0))
        agent.construction_focus_site_id = str(site.get("building_id", ""))
        agent.construction_focus_tick = int(getattr(self, "tick", 0))
        if str(site.get("type", "")) == "storage":
            self.record_settlement_progression_metric("storage_material_delivery_events", int(moved))

        if hasattr(building_system, "_sync_construction_site_state"):
            try:
                building_system._sync_construction_site_state(site, now_tick=int(getattr(self, "tick", 0)))  # type: ignore[attr-defined]
            except Exception:
                pass
        return int(moved)

    def update_settlement_progression_metrics(self) -> None:
        stats = self.settlement_progression_stats if isinstance(self.settlement_progression_stats, dict) else _default_settlement_progression_stats()
        respawn = self.resource_respawn_stats if isinstance(self.resource_respawn_stats, dict) else _default_resource_respawn_stats()
        stats["food_respawned_total_observed"] = int(respawn.get("food_respawned_total", 0))
        farm_scores: List[float] = []
        for plot in (self.farm_plots or {}).values():
            if not isinstance(plot, dict):
                continue
            state = str(plot.get("state", ""))
            if state not in {"prepared", "planted", "growing", "ripe"}:
                continue
            farm_scores.append(max(0.0, float(plot.get("productivity_score", 0.0))))
        stats["farm_productivity_score_avg"] = round(float(sum(farm_scores)) / float(max(1, len(farm_scores))), 4) if farm_scores else 0.0
        stats["agents_farming_count"] = int(
            len(
                [
                    a
                    for a in (self.agents or [])
                    if getattr(a, "alive", False)
                    and (str(getattr(a, "task", "")) == "farm_cycle" or str(getattr(a, "role", "")) == "farmer")
                ]
            )
        )
        alive_agents = [a for a in (self.agents or []) if getattr(a, "alive", False)]
        alive_count = int(len(alive_agents))
        stats["population_alive"] = int(alive_count)
        reserve_total_now = int(self.current_total_food_in_reserves())
        stats["reserve_total_food_observed_sum"] = int(stats.get("reserve_total_food_observed_sum", 0)) + int(reserve_total_now)
        stats["reserve_total_food_observed_samples"] = int(stats.get("reserve_total_food_observed_samples", 0)) + 1
        stats["reserve_total_food_observed_max"] = int(
            max(int(stats.get("reserve_total_food_observed_max", 0)), int(reserve_total_now))
        )
        reserve_prev = int(stats.get("_reserve_total_food_prev_tick", -1))
        if reserve_prev >= 0:
            if reserve_total_now > reserve_prev:
                stats["reserve_fill_events"] = int(stats.get("reserve_fill_events", 0)) + 1
            elif reserve_total_now < reserve_prev:
                stats["reserve_depletion_events"] = int(stats.get("reserve_depletion_events", 0)) + 1
        stats["_reserve_total_food_prev_tick"] = int(reserve_total_now)
        reserve_threshold = max(3, int(round(float(max(1, alive_count)) * 0.15)))
        if reserve_total_now >= reserve_threshold:
            stats["ticks_reserve_above_threshold"] = int(stats.get("ticks_reserve_above_threshold", 0)) + 1
            current_window = int(stats.get("reserve_continuity_current_window", 0)) + 1
            stats["reserve_continuity_current_window"] = int(current_window)
            stats["reserve_continuity_longest_window"] = int(
                max(int(stats.get("reserve_continuity_longest_window", 0)), int(current_window))
            )
            if reserve_prev <= 0:
                stats["reserve_recovery_cycles"] = int(stats.get("reserve_recovery_cycles", 0)) + 1
        else:
            stats["reserve_continuity_current_window"] = 0
        sustain_threshold_ticks = 20
        tracking_active = bool(int(stats.get("reserve_recovery_tracking_active", 0)))
        refill_started = bool(int(stats.get("reserve_recovery_refill_started", 0)))
        sustain_ticks = int(stats.get("reserve_recovery_sustain_ticks", 0))
        if reserve_total_now <= 0:
            if reserve_prev > 0:
                tracking_active = True
                refill_started = False
                sustain_ticks = 0
        elif tracking_active and not refill_started:
            refill_started = True
            stats["reserve_partial_recovery_cycles"] = int(stats.get("reserve_partial_recovery_cycles", 0)) + 1
        if tracking_active and refill_started:
            if reserve_total_now >= reserve_threshold:
                sustain_ticks += 1
                if sustain_ticks >= sustain_threshold_ticks:
                    stats["reserve_full_recovery_cycles"] = int(stats.get("reserve_full_recovery_cycles", 0)) + 1
                    tracking_active = False
                    refill_started = False
                    sustain_ticks = 0
            elif reserve_total_now <= 0:
                stats["reserve_failed_recovery_attempts"] = int(stats.get("reserve_failed_recovery_attempts", 0)) + 1
                tracking_active = False
                refill_started = False
                sustain_ticks = 0
            else:
                sustain_ticks = 0
        stats["reserve_recovery_tracking_active"] = 1 if tracking_active else 0
        stats["reserve_recovery_refill_started"] = 1 if refill_started else 0
        stats["reserve_recovery_sustain_ticks"] = int(max(0, sustain_ticks))
        if reserve_total_now <= 0:
            stats["ticks_reserve_empty"] = int(stats.get("ticks_reserve_empty", 0)) + 1
        hungry_agents = int(sum(1 for a in alive_agents if float(getattr(a, "hunger", 100.0)) < 35.0))
        shortage_active = bool(reserve_total_now <= 0 and hungry_agents > 0)
        shortage_prev = bool(int(stats.get("reserve_shortage_active_prev", 0)))
        if shortage_active and not shortage_prev:
            stats["settlement_food_shortage_events"] = int(stats.get("settlement_food_shortage_events", 0)) + 1
        stats["reserve_shortage_active_prev"] = 1 if shortage_active else 0
        layer_counts = {
            "self_feeding": 0,
            "group_feeding": 0,
            "reserve_accumulation": 0,
            "none": 0,
        }
        reserve_candidate_tasks = {"food_logistics", "camp_supply_food", "village_logistics"}
        reserve_candidate_count = 0
        reserve_eligible_count = 0
        for a in alive_agents:
            layer = str(getattr(a, "food_security_layer", "none") or "none")
            if layer not in layer_counts:
                layer = "none"
            layer_counts[layer] = int(layer_counts[layer]) + 1
            prev_layer = str(getattr(a, "_food_security_layer_prev", "none") or "none")
            if prev_layer not in layer_counts:
                prev_layer = "none"
            if prev_layer != layer:
                stats["food_security_layer_transition_count"] = int(
                    stats.get("food_security_layer_transition_count", 0)
                ) + 1
            transition_key = f"food_security_layer_transition_{prev_layer}_to_{layer}"
            stats[transition_key] = int(stats.get(transition_key, 0)) + 1
            setattr(a, "_food_security_layer_prev", layer)
            task_name = str(getattr(a, "task", "") or "")
            if task_name in reserve_candidate_tasks:
                reserve_candidate_count += 1
                stats["food_security_reserve_prepolicy_candidate_count"] = int(
                    stats.get("food_security_reserve_prepolicy_candidate_count", 0)
                ) + 1
                stats["food_security_reserve_entry_checks"] = int(
                    stats.get("food_security_reserve_entry_checks", 0)
                ) + 1
                stats["food_security_reserve_selection_considered_count"] = int(
                    stats.get("food_security_reserve_selection_considered_count", 0)
                ) + 1
                pressure = {}
                if hasattr(self, "compute_local_food_pressure_for_agent"):
                    try:
                        pressure = self.compute_local_food_pressure_for_agent(a, max_distance=10)
                    except Exception:
                        pressure = {}
                supply = 0
                demand = 0
                pressure_active = False
                if isinstance(pressure, dict):
                    supply = int(pressure.get("near_food_sources", 0)) + int(pressure.get("camp_food", 0)) + int(pressure.get("house_food_nearby", 0))
                    demand = int(pressure.get("nearby_needy_agents", 0))
                    pressure_active = bool(pressure.get("pressure_active", False))
                has_local_surplus = bool(supply >= max(2, demand + 1))
                stable_context = bool(
                    str(getattr(a, "village_affiliation_status", "")) in {"attached", "resident"}
                    or isinstance(self.nearest_active_camp_for_agent(a, max_distance=2), dict)
                )
                stats["food_security_reserve_final_decision_observed_count"] = int(
                    stats.get("food_security_reserve_final_decision_observed_count", 0)
                ) + 1
                stats["food_security_reserve_final_decision_candidate_count"] = int(
                    stats.get("food_security_reserve_final_decision_candidate_count", 0)
                ) + 1
                if has_local_surplus:
                    stats["food_security_reserve_final_decision_candidate_survived_prepolicy_count"] = int(
                        stats.get("food_security_reserve_final_decision_candidate_survived_prepolicy_count", 0)
                    ) + 1
                if has_local_surplus and stable_context:
                    stats["food_security_reserve_final_decision_candidate_survived_postpolicy_count"] = int(
                        stats.get("food_security_reserve_final_decision_candidate_survived_postpolicy_count", 0)
                    ) + 1
                selected_task_key = str(task_name if task_name in reserve_candidate_tasks else "other")
                if selected_task_key not in {"food_logistics", "village_logistics", "camp_supply_food"}:
                    selected_task_key = "other"
                stats[f"food_security_reserve_final_selected_task_{selected_task_key}_count"] = int(
                    stats.get(f"food_security_reserve_final_selected_task_{selected_task_key}_count", 0)
                ) + 1
                selected_layer_key = str(layer if layer in {"reserve_accumulation", "group_feeding", "self_feeding"} else "none")
                stats[f"food_security_reserve_final_selected_layer_{selected_layer_key}_count"] = int(
                    stats.get(f"food_security_reserve_final_selected_layer_{selected_layer_key}_count", 0)
                ) + 1

                winner_subsystem = "unknown"
                override_reason = "other"
                if not has_local_surplus:
                    winner_subsystem = "policy_ranking"
                    override_reason = "no_surplus"
                elif not stable_context:
                    winner_subsystem = "final_gate"
                    override_reason = "unstable_context"
                elif layer == "reserve_accumulation":
                    winner_subsystem = "policy_ranking"
                    override_reason = "reserve_selected"
                elif layer == "group_feeding":
                    if pressure_active:
                        winner_subsystem = "contextual_override"
                        override_reason = "group_feeding_pressure_override"
                    elif task_name == "village_logistics":
                        winner_subsystem = "task_layer_routing"
                        override_reason = "village_logistics_group_routing"
                    elif task_name == "camp_supply_food":
                        winner_subsystem = "task_layer_routing"
                        override_reason = "camp_supply_group_routing"
                    else:
                        winner_subsystem = "role_task_update"
                        override_reason = "group_feeding_role_update"
                elif layer == "self_feeding":
                    winner_subsystem = "role_task_update"
                    override_reason = "self_feeding_override"
                else:
                    winner_subsystem = "unknown"
                    override_reason = "other"

                stats[f"food_security_reserve_final_winner_subsystem_{winner_subsystem}_count"] = int(
                    stats.get(f"food_security_reserve_final_winner_subsystem_{winner_subsystem}_count", 0)
                ) + 1
                override_reason_key = (
                    override_reason
                    if override_reason in {
                        "group_feeding_pressure_override",
                        "village_logistics_group_routing",
                        "camp_supply_group_routing",
                        "unstable_context",
                        "no_surplus",
                    }
                    else "other"
                )
                stats[f"food_security_reserve_final_override_reason_{override_reason_key}_count"] = int(
                    stats.get(f"food_security_reserve_final_override_reason_{override_reason_key}_count", 0)
                ) + 1

                if has_local_surplus and stable_context:
                    reserve_eligible_count += 1
                    stats["food_security_reserve_postpolicy_candidate_count"] = int(
                        stats.get("food_security_reserve_postpolicy_candidate_count", 0)
                    ) + 1
                    stats["food_security_reserve_entry_condition_met_count"] = int(
                        stats.get("food_security_reserve_entry_condition_met_count", 0)
                    ) + 1
                if layer == "reserve_accumulation":
                    stats["food_security_reserve_final_decision_candidate_chosen_count"] = int(
                        stats.get("food_security_reserve_final_decision_candidate_chosen_count", 0)
                    ) + 1
                    stats["food_security_reserve_selection_chosen_count"] = int(
                        stats.get("food_security_reserve_selection_chosen_count", 0)
                    ) + 1
                    stats["food_security_reserve_final_activation_count"] = int(
                        stats.get("food_security_reserve_final_activation_count", 0)
                    ) + 1
                    stats["food_security_reserve_entry_activated_count"] = int(
                        stats.get("food_security_reserve_entry_activated_count", 0)
                    ) + 1
                else:
                    stats["food_security_reserve_final_decision_candidate_lost_count"] = int(
                        stats.get("food_security_reserve_final_decision_candidate_lost_count", 0)
                    ) + 1
                    stats["food_security_reserve_selection_rejected_count"] = int(
                        stats.get("food_security_reserve_selection_rejected_count", 0)
                    ) + 1
                    if not has_local_surplus:
                        stats["food_security_reserve_entry_blocked_no_surplus"] = int(
                            stats.get("food_security_reserve_entry_blocked_no_surplus", 0)
                        ) + 1
                        stats["food_security_reserve_selection_rejected_by_no_surplus_count"] = int(
                            stats.get("food_security_reserve_selection_rejected_by_no_surplus_count", 0)
                        ) + 1
                        stats["food_security_reserve_final_selection_lost_to_no_surplus_count"] = int(
                            stats.get("food_security_reserve_final_selection_lost_to_no_surplus_count", 0)
                        ) + 1
                        stats["food_security_reserve_loss_stage_policy_ranking_count"] = int(
                            stats.get("food_security_reserve_loss_stage_policy_ranking_count", 0)
                        ) + 1
                    elif not stable_context:
                        stats["food_security_reserve_entry_blocked_unstable_context"] = int(
                            stats.get("food_security_reserve_entry_blocked_unstable_context", 0)
                        ) + 1
                        stats["food_security_reserve_selection_rejected_by_unstable_context_count"] = int(
                            stats.get("food_security_reserve_selection_rejected_by_unstable_context_count", 0)
                        ) + 1
                        stats["food_security_reserve_final_selection_lost_to_unstable_context_count"] = int(
                            stats.get("food_security_reserve_final_selection_lost_to_unstable_context_count", 0)
                        ) + 1
                        stats["food_security_reserve_loss_stage_final_gate_count"] = int(
                            stats.get("food_security_reserve_loss_stage_final_gate_count", 0)
                        ) + 1
                    elif pressure_active and layer == "group_feeding":
                        stats["food_security_reserve_entry_blocked_group_feeding_dominance"] = int(
                            stats.get("food_security_reserve_entry_blocked_group_feeding_dominance", 0)
                        ) + 1
                        stats["food_security_reserve_selection_rejected_by_group_feeding_count"] = int(
                            stats.get("food_security_reserve_selection_rejected_by_group_feeding_count", 0)
                        ) + 1
                        stats["food_security_reserve_final_selection_lost_to_group_feeding_count"] = int(
                            stats.get("food_security_reserve_final_selection_lost_to_group_feeding_count", 0)
                        ) + 1
                        stats["food_security_reserve_final_selection_winner_group_feeding_count"] = int(
                            stats.get("food_security_reserve_final_selection_winner_group_feeding_count", 0)
                        ) + 1
                        stats["food_security_reserve_loss_stage_final_override_count"] = int(
                            stats.get("food_security_reserve_loss_stage_final_override_count", 0)
                        ) + 1
                    elif layer == "self_feeding":
                        stats["food_security_reserve_final_selection_lost_to_self_feeding_count"] = int(
                            stats.get("food_security_reserve_final_selection_lost_to_self_feeding_count", 0)
                        ) + 1
                        stats["food_security_reserve_final_selection_winner_self_feeding_count"] = int(
                            stats.get("food_security_reserve_final_selection_winner_self_feeding_count", 0)
                        ) + 1
                        stats["food_security_reserve_loss_stage_final_override_count"] = int(
                            stats.get("food_security_reserve_loss_stage_final_override_count", 0)
                        ) + 1
                    else:
                        stats["food_security_reserve_selection_rejected_by_other_count"] = int(
                            stats.get("food_security_reserve_selection_rejected_by_other_count", 0)
                        ) + 1
                        stats["food_security_reserve_final_selection_lost_to_other_count"] = int(
                            stats.get("food_security_reserve_final_selection_lost_to_other_count", 0)
                        ) + 1
                        stats["food_security_reserve_final_selection_winner_other_count"] = int(
                            stats.get("food_security_reserve_final_selection_winner_other_count", 0)
                        ) + 1
                        stats["food_security_reserve_loss_stage_final_override_count"] = int(
                            stats.get("food_security_reserve_loss_stage_final_override_count", 0)
                        ) + 1
        stats["food_security_layer_self_feeding_ticks_total"] = int(
            stats.get("food_security_layer_self_feeding_ticks_total", 0)
        ) + int(layer_counts["self_feeding"])
        stats["food_security_layer_group_feeding_ticks_total"] = int(
            stats.get("food_security_layer_group_feeding_ticks_total", 0)
        ) + int(layer_counts["group_feeding"])
        stats["food_security_layer_reserve_accumulation_ticks_total"] = int(
            stats.get("food_security_layer_reserve_accumulation_ticks_total", 0)
        ) + int(layer_counts["reserve_accumulation"])
        stats["food_security_layer_none_ticks_total"] = int(
            stats.get("food_security_layer_none_ticks_total", 0)
        ) + int(layer_counts["none"])
        stats["food_security_layer_agents_self_feeding_total"] = int(
            stats.get("food_security_layer_agents_self_feeding_total", 0)
        ) + int(layer_counts["self_feeding"])
        stats["food_security_layer_agents_group_feeding_total"] = int(
            stats.get("food_security_layer_agents_group_feeding_total", 0)
        ) + int(layer_counts["group_feeding"])
        stats["food_security_layer_agents_reserve_accumulation_total"] = int(
            stats.get("food_security_layer_agents_reserve_accumulation_total", 0)
        ) + int(layer_counts["reserve_accumulation"])
        stats["food_security_layer_agents_none_total"] = int(
            stats.get("food_security_layer_agents_none_total", 0)
        ) + int(layer_counts["none"])
        stats["food_security_layer_samples"] = int(stats.get("food_security_layer_samples", 0)) + 1
        if reserve_candidate_count <= 0:
            stats["food_security_reserve_entry_blocked_no_qualifying_task"] = int(
                stats.get("food_security_reserve_entry_blocked_no_qualifying_task", 0)
            ) + 1
        elif reserve_eligible_count > 0 and int(layer_counts["reserve_accumulation"]) <= 0:
            stats["food_security_reserve_entry_blocked_group_feeding_dominance"] = int(
                stats.get("food_security_reserve_entry_blocked_group_feeding_dominance", 0)
            ) + 1
        food_inventory_total_tick = int(
            sum(
                int(getattr(a, "inventory", {}).get("food", 0))
                for a in alive_agents
                if isinstance(getattr(a, "inventory", {}), dict)
            )
        )
        stats["agent_food_inventory_total"] = int(stats.get("agent_food_inventory_total", 0)) + int(food_inventory_total_tick)
        stats["agent_food_inventory_samples"] = int(stats.get("agent_food_inventory_samples", 0)) + int(max(1, alive_count))
        food_tasks = {"gather_food_wild", "farm_cycle", "camp_supply_food", "food_logistics"}
        food_seekers_tick = int(sum(1 for a in alive_agents if str(getattr(a, "task", "")) in food_tasks))
        stats["food_seeking_ticks_total"] = int(stats.get("food_seeking_ticks_total", 0)) + int(food_seekers_tick)
        stats["agent_ticks_total"] = int(stats.get("agent_ticks_total", 0)) + int(max(1, alive_count))
        moving_for_food = 0
        for a in alive_agents:
            if str(getattr(a, "task", "")) not in {"gather_food_wild", "farm_cycle"}:
                continue
            apos = (int(getattr(a, "x", 0)), int(getattr(a, "y", 0)))
            if apos in self.food:
                continue
            moving_for_food += 1
        stats["food_move_ticks_total"] = int(stats.get("food_move_ticks_total", 0)) + int(moving_for_food)
        target_counts: Dict[Tuple[int, int], int] = {}
        for a in alive_agents:
            if str(getattr(a, "task", "")) not in {"gather_food_wild", "farm_cycle"}:
                continue
            target = getattr(a, "task_target", None)
            if not (isinstance(target, tuple) and len(target) == 2):
                continue
            key = (int(target[0]), int(target[1]))
            target_counts[key] = int(target_counts.get(key, 0)) + 1
        contention_events = int(sum(max(0, c - 1) for c in target_counts.values() if int(c) > 1))
        if contention_events > 0:
            stats["food_source_contention_events"] = int(stats.get("food_source_contention_events", 0)) + int(contention_events)
        active_camps = [c for c in (self.camps or {}).values() if isinstance(c, dict) and bool(c.get("active", False))]
        prev_accessible = stats.get("_food_basin_prev_accessible_by_camp", {})
        if not isinstance(prev_accessible, dict):
            prev_accessible = {}
        next_accessible: Dict[str, int] = {}
        severe_pressure_ticks = 0
        for camp in active_camps:
            camp_id = str(camp.get("camp_id", ""))
            cx = int(camp.get("x", 0))
            cy = int(camp.get("y", 0))
            basin_radius = 8
            accessible = int(self._count_food_near(cx, cy, radius=basin_radius))
            competing = int(
                sum(
                    1
                    for a in alive_agents
                    if abs(int(getattr(a, "x", 0)) - cx) + abs(int(getattr(a, "y", 0)) - cy) <= basin_radius
                    and str(getattr(a, "task", "")) in {"gather_food_wild", "farm_cycle", "camp_supply_food", "food_logistics"}
                )
            )
            demand = max(1, int(competing))
            ratio = float(demand) / float(max(1, accessible))
            nearest = self._find_nearest_food_to(cx, cy, radius=16)
            nearest_dist = int(abs(int(nearest[0]) - cx) + abs(int(nearest[1]) - cy)) if isinstance(nearest, tuple) else 17
            stats["local_food_basin_accessible_total"] = int(stats.get("local_food_basin_accessible_total", 0)) + int(accessible)
            stats["local_food_basin_accessible_samples"] = int(stats.get("local_food_basin_accessible_samples", 0)) + 1
            stats["local_food_basin_pressure_ratio_total"] = float(stats.get("local_food_basin_pressure_ratio_total", 0.0)) + float(ratio)
            stats["local_food_basin_pressure_ratio_samples"] = int(stats.get("local_food_basin_pressure_ratio_samples", 0)) + 1
            stats["local_food_basin_competing_agents_total"] = int(stats.get("local_food_basin_competing_agents_total", 0)) + int(competing)
            stats["local_food_basin_competing_agents_samples"] = int(stats.get("local_food_basin_competing_agents_samples", 0)) + 1
            stats["local_food_basin_nearest_food_distance_total"] = int(
                stats.get("local_food_basin_nearest_food_distance_total", 0)
            ) + int(nearest_dist)
            stats["local_food_basin_nearest_food_distance_samples"] = int(
                stats.get("local_food_basin_nearest_food_distance_samples", 0)
            ) + 1
            severe = bool((accessible <= 0 and competing >= 2) or ratio >= 1.8)
            if severe:
                severe_pressure_ticks += 1
            prev_val = int(prev_accessible.get(camp_id, accessible))
            if prev_val > 0 and accessible <= 0:
                stats["local_food_basin_collapse_events"] = int(stats.get("local_food_basin_collapse_events", 0)) + 1
            next_accessible[camp_id] = int(accessible)
        if severe_pressure_ticks > 0:
            stats["local_food_basin_severe_pressure_ticks"] = int(
                stats.get("local_food_basin_severe_pressure_ticks", 0)
            ) + int(severe_pressure_ticks)
        stats["_food_basin_prev_accessible_by_camp"] = next_accessible
        dead_count = int(stats.get("population_deaths_count", 0))
        birth_count = int(stats.get("population_births_count", 0))
        stats["population_net_change"] = int(birth_count - dead_count)
        alive_ages: List[int] = []
        for agent in alive_agents:
            born_tick = int(getattr(agent, "born_tick", int(getattr(self, "tick", 0))))
            alive_ages.append(max(0, int(getattr(self, "tick", 0)) - born_tick))
        stats["agent_average_age"] = round(float(sum(alive_ages)) / float(max(1, len(alive_ages))), 4) if alive_ages else 0.0
        peak_alive = max(int(stats.get("_population_peak_alive", 0)), alive_count)
        stats["_population_peak_alive"] = int(peak_alive)
        collapse_trigger = int(round(float(peak_alive) * 0.6))
        collapse_active = bool(stats.get("_population_collapse_active", False))
        if peak_alive >= 8 and alive_count <= max(3, collapse_trigger):
            if not collapse_active:
                stats["population_collapse_events"] = int(stats.get("population_collapse_events", 0)) + 1
                stats["_population_collapse_active"] = True
        elif collapse_active and alive_count >= max(4, int(round(float(peak_alive) * 0.75))):
            stats["_population_collapse_active"] = False
        formalized_villages = [
            v for v in (self.villages or [])
            if isinstance(v, dict) and bool(v.get("formalized", False))
        ]
        proto_villages = [
            v for v in (self.villages or [])
            if isinstance(v, dict) and not bool(v.get("formalized", False))
        ]
        stats["settlement_proto_count"] = int(len(proto_villages))
        stats["settlement_stable_village_count"] = int(
            len([v for v in formalized_villages if int(v.get("stability_ticks", 0)) >= int(SETTLEMENT_STABILITY_TICK_THRESHOLD)])
        )
        abandoned_due_food = 0
        for v in (self.villages or []):
            if not isinstance(v, dict):
                continue
            if not bool(v.get("abandoned", False)):
                continue
            needs = v.get("needs", {})
            if isinstance(needs, dict) and bool(needs.get("food_urgent", False) or needs.get("food_low", False)):
                abandoned_due_food += 1
        stats["proto_settlement_abandoned_due_to_food_pressure_count"] = int(abandoned_due_food)
        food_rate_sum_scaled = 0
        resource_rate_sum_scaled = 0
        rate_samples = 0
        for village in (self.villages or []):
            if not isinstance(village, dict):
                continue
            ss = self.update_village_surplus_state(village)
            food_rate_sum_scaled += int(round(float(ss.get("food_surplus_rate", 0.0)) * 1000.0))
            resource_rate_sum_scaled += int(round(float(ss.get("resource_surplus_rate", 0.0)) * 1000.0))
            rate_samples += 1
        stats["_surplus_food_rate_sum_scaled"] = int(food_rate_sum_scaled)
        stats["_surplus_resource_rate_sum_scaled"] = int(resource_rate_sum_scaled)
        stats["_surplus_rate_samples"] = int(rate_samples)

        sizes = self._compute_house_cluster_sizes(link_distance=4)
        stats["house_cluster_count"] = int(len([s for s in sizes if int(s) > 0]))
        stats["avg_houses_per_cluster"] = round(float(sum(sizes)) / float(max(1, len(sizes))), 3) if sizes else 0.0

        prev_sizes = stats.get("_prev_cluster_sizes", [])
        if not isinstance(prev_sizes, list):
            prev_sizes = []
        growth_events = 0
        max_len = max(len(prev_sizes), len(sizes))
        for i in range(max_len):
            prev = int(prev_sizes[i]) if i < len(prev_sizes) else 0
            cur = int(sizes[i]) if i < len(sizes) else 0
            if cur > prev:
                growth_events += 1
        if growth_events > 0:
            stats["house_cluster_growth_events"] = int(stats.get("house_cluster_growth_events", 0)) + int(growth_events)
        stats["_prev_cluster_sizes"] = [int(v) for v in sizes]

        secondary_with_house = 0
        for camp in (self.camps or {}).values():
            if not isinstance(camp, dict) or not bool(camp.get("active", False)):
                continue
            cx, cy = int(camp.get("x", 0)), int(camp.get("y", 0))
            if self.count_nearby_houses(cx, cy, radius=6) > 0:
                secondary_with_house += 1
        stats["secondary_nucleus_with_house_count"] = int(secondary_with_house)
        prev_secondary = int(stats.get("_prev_secondary_nucleus_with_house_count", 0))
        if secondary_with_house > prev_secondary:
            stats["secondary_nucleus_house_growth_events"] = int(stats.get("secondary_nucleus_house_growth_events", 0)) + int(
                secondary_with_house - prev_secondary
            )
        stats["_prev_secondary_nucleus_with_house_count"] = int(secondary_with_house)
        stats["active_storage_construction_sites"] = int(
            len(
                [
                    b
                    for b in (self.buildings or {}).values()
                    if isinstance(b, dict)
                    and str(b.get("type", "")) == "storage"
                    and str(b.get("operational_state", "")) == "under_construction"
                ]
            )
        )
        housing_diag = self.compute_housing_construction_diagnostics_snapshot()
        hglobal = housing_diag.get("global", {}) if isinstance(housing_diag, dict) else {}
        stats["houses_completed_count"] = int(hglobal.get("houses_completed_count", 0))
        wood_on_map_now = int(len(self.wood))
        stone_on_map_now = int(len(self.stone))
        wood_in_agents_now = int(
            sum(
                int(getattr(a, "inventory", {}).get("wood", 0))
                for a in (self.agents or [])
                if getattr(a, "alive", False) and isinstance(getattr(a, "inventory", {}), dict)
            )
        )
        stone_in_agents_now = int(
            sum(
                int(getattr(a, "inventory", {}).get("stone", 0))
                for a in (self.agents or [])
                if getattr(a, "alive", False) and isinstance(getattr(a, "inventory", {}), dict)
            )
        )
        wood_in_storage_now = 0
        stone_in_storage_now = 0
        wood_in_construction_buffers_now = 0
        stone_in_construction_buffers_now = 0

        def _nearest_distance_to_sources(x: int, y: int, sources: Set[Coord]) -> int:
            if not sources:
                return -1
            best = None
            for sx, sy in sources:
                d = abs(int(x) - int(sx)) + abs(int(y) - int(sy))
                if best is None or d < best:
                    best = d
            return int(best) if best is not None else -1

        def _count_sources_within_radius(x: int, y: int, sources: Set[Coord], radius: int) -> int:
            if not sources:
                return 0
            r = max(0, int(radius))
            return int(sum(1 for sx, sy in sources if abs(int(x) - int(sx)) + abs(int(y) - int(sy)) <= r))

        active_sites = 0
        partial_sites = 0
        near_complete_sites = 0
        live_required_total = 0
        live_delivered_total = 0
        live_remaining_total = 0
        live_required_work_total = 0
        live_completed_work_total = 0
        live_remaining_work_total = 0
        in_progress_ticks_total = 0
        waiting_material_ticks_total = 0
        buildable_but_idle_ticks_total = 0
        delivery_to_work_gap_total = 0
        delivery_to_work_gap_samples = 0
        distinct_builders_total = 0
        distinct_builders_samples = 0
        work_ticks_per_builder_total = 0.0
        work_ticks_per_builder_samples = 0
        active_age_ticks_total = 0
        active_age_ticks_samples = 0
        site_nearest_wood_dist_total = 0
        site_nearest_wood_dist_samples = 0
        site_nearest_stone_dist_total = 0
        site_nearest_stone_dist_samples = 0
        site_viable_wood_total = 0
        site_viable_wood_samples = 0
        site_viable_stone_total = 0
        site_viable_stone_samples = 0
        site_zero_wood_ticks = 0
        site_zero_stone_ticks = 0
        site_local_wood_contention_total = 0.0
        site_local_wood_contention_samples = 0
        site_local_stone_contention_total = 0.0
        site_local_stone_contention_samples = 0
        site_ticks_since_last_delivery_total = 0
        site_ticks_since_last_delivery_samples = 0
        site_waiting_positive_wood_stock_ticks = 0
        site_waiting_positive_stone_stock_ticks = 0
        site_first_demand_to_first_delivery_total = 0
        site_first_demand_to_first_delivery_samples = 0
        site_material_inflow_rate_total = 0.0
        site_material_inflow_rate_samples = 0
        site_delivered_wood_units_live = 0
        site_delivered_stone_units_live = 0
        site_delivered_food_units_live = 0
        state_counts = {
            "planned": 0,
            "supplying": 0,
            "buildable": 0,
            "in_progress": 0,
            "paused": 0,
            "completed": 0,
        }
        for _b in (self.buildings or {}).values():
            if not isinstance(_b, dict):
                continue
            if str(_b.get("type", "")) == "storage":
                _st = _b.get("storage", {}) if isinstance(_b.get("storage"), dict) else {}
                wood_in_storage_now += int(_st.get("wood", 0))
                stone_in_storage_now += int(_st.get("stone", 0))
        for b in (self.buildings or {}).values():
            if not isinstance(b, dict):
                continue
            if str(b.get("type", "")) not in {"house", "storage"}:
                continue
            if str(b.get("operational_state", "")) != "under_construction":
                continue
            if hasattr(building_system, "_sync_construction_site_state"):
                try:
                    building_system._sync_construction_site_state(b, now_tick=int(getattr(self, "tick", 0)))  # type: ignore[attr-defined]
                except Exception:
                    pass
            active_sites += 1
            stats["construction_site_waiting_total_ticks"] = int(stats.get("construction_site_waiting_total_ticks", 0)) + 1
            progress = int(b.get("construction_progress", 0))
            required = max(1, int(b.get("construction_required_work", 1)))
            remaining_work = max(0, required - progress)
            if progress > 0:
                in_progress_ticks_total += 1
            live_required_work_total += int(required)
            live_completed_work_total += int(max(0, min(progress, required)))
            live_remaining_work_total += int(remaining_work)
            build_state = str(b.get("build_state", "planned"))
            if build_state in state_counts:
                state_counts[build_state] = int(state_counts.get(build_state, 0)) + 1
            if progress > 0 and progress < required:
                partial_sites += 1
                stats["construction_site_progress_active_ticks"] = int(stats.get("construction_site_progress_active_ticks", 0)) + 1
            needs = {}
            if hasattr(building_system, "get_outstanding_construction_needs"):
                try:
                    needs = building_system.get_outstanding_construction_needs(b)
                except Exception:
                    needs = {}
            outstanding = 0
            if isinstance(needs, dict):
                outstanding = int(needs.get("wood", 0)) + int(needs.get("stone", 0)) + int(needs.get("food", 0))
            buf = b.get("construction_buffer", {}) if isinstance(b.get("construction_buffer", {}), dict) else {}
            wood_in_construction_buffers_now += int(buf.get("wood", 0))
            stone_in_construction_buffers_now += int(buf.get("stone", 0))
            req = b.get("construction_request", {}) if isinstance(b.get("construction_request", {}), dict) else {}
            required_total = int(req.get("wood_needed", 0)) + int(req.get("stone_needed", 0)) + int(req.get("food_needed", 0))
            delivered_total = int(b.get("construction_delivered_units", 0))
            delivered_wood_total = int(b.get("construction_delivered_wood_units", 0))
            delivered_stone_total = int(b.get("construction_delivered_stone_units", 0))
            delivered_food_total = int(b.get("construction_delivered_food_units", 0))
            live_required_total += max(0, required_total)
            live_delivered_total += max(0, delivered_total)
            live_remaining_total += max(0, outstanding)
            site_delivered_wood_units_live += max(0, delivered_wood_total)
            site_delivered_stone_units_live += max(0, delivered_stone_total)
            site_delivered_food_units_live += max(0, delivered_food_total)
            if outstanding > 0 and outstanding <= 2:
                near_complete_sites += 1
            bx = int(b.get("x", 0))
            by = int(b.get("y", 0))
            nearest_wood = _nearest_distance_to_sources(bx, by, self.wood)
            nearest_stone = _nearest_distance_to_sources(bx, by, self.stone)
            if nearest_wood >= 0:
                site_nearest_wood_dist_total += int(nearest_wood)
                site_nearest_wood_dist_samples += 1
            if nearest_stone >= 0:
                site_nearest_stone_dist_total += int(nearest_stone)
                site_nearest_stone_dist_samples += 1
            nearby_wood_sources = _count_sources_within_radius(bx, by, self.wood, radius=8)
            nearby_stone_sources = _count_sources_within_radius(bx, by, self.stone, radius=8)
            site_viable_wood_total += int(nearby_wood_sources)
            site_viable_wood_samples += 1
            site_viable_stone_total += int(nearby_stone_sources)
            site_viable_stone_samples += 1
            if nearby_wood_sources <= 0:
                site_zero_wood_ticks += 1
            if nearby_stone_sources <= 0:
                site_zero_stone_ticks += 1
            nearby_harvesters = 0
            nearby_miners = 0
            for _a in (self.agents or []):
                if not getattr(_a, "alive", False):
                    continue
                ad = abs(int(getattr(_a, "x", 0)) - bx) + abs(int(getattr(_a, "y", 0)) - by)
                if ad > 8:
                    continue
                atask = str(getattr(_a, "task", ""))
                if atask in {"lumber_cycle", "gather_materials"}:
                    nearby_harvesters += 1
                if atask in {"mine_cycle", "gather_materials"}:
                    nearby_miners += 1
            if nearby_wood_sources > 0:
                site_local_wood_contention_total += float(nearby_harvesters) / float(max(1, nearby_wood_sources))
                site_local_wood_contention_samples += 1
            if nearby_stone_sources > 0:
                site_local_stone_contention_total += float(nearby_miners) / float(max(1, nearby_stone_sources))
                site_local_stone_contention_samples += 1
            now_tick = int(getattr(self, "tick", 0))
            last_delivery_tick = int(b.get("construction_last_delivery_tick", -1))
            if last_delivery_tick >= 0:
                site_ticks_since_last_delivery_total += max(0, now_tick - last_delivery_tick)
                site_ticks_since_last_delivery_samples += 1
            first_demand_tick = int(b.get("construction_last_demand_tick", b.get("construction_created_tick", -1)))
            first_delivery_tick = int(b.get("construction_first_delivery_tick", -1))
            if (
                first_demand_tick >= 0
                and first_delivery_tick >= first_demand_tick
                and not bool(b.get("construction_first_demand_to_first_delivery_recorded", False))
            ):
                site_first_demand_to_first_delivery_total += int(first_delivery_tick - first_demand_tick)
                site_first_demand_to_first_delivery_samples += 1
                b["construction_first_demand_to_first_delivery_recorded"] = True
            created_tick = int(b.get("construction_created_tick", now_tick))
            age_ticks = max(1, now_tick - created_tick + 1)
            site_material_inflow_rate_total += float(max(0, delivered_total)) / float(age_ticks)
            site_material_inflow_rate_samples += 1
            if outstanding <= 0:
                stats["construction_site_buildable_ticks_total"] = int(stats.get("construction_site_buildable_ticks_total", 0)) + 1
                if progress <= 0:
                    stats["construction_site_idle_buildable_ticks_total"] = int(
                        stats.get("construction_site_idle_buildable_ticks_total", 0)
                    ) + 1
                    buildable_but_idle_ticks_total += 1
                if int(b.get("construction_material_ready_tick", -1)) < 0:
                    b["construction_material_ready_tick"] = int(getattr(self, "tick", 0))
            btype = str(b.get("type", ""))
            if outstanding > 0:
                stats["construction_site_waiting_for_material_ticks"] = int(stats.get("construction_site_waiting_for_material_ticks", 0)) + 1
                waiting_material_ticks_total += 1
                wood_available_now = int(wood_on_map_now + wood_in_agents_now + wood_in_storage_now + wood_in_construction_buffers_now)
                stone_available_now = int(stone_on_map_now + stone_in_agents_now + stone_in_storage_now + stone_in_construction_buffers_now)
                if wood_available_now > 0:
                    site_waiting_positive_wood_stock_ticks += 1
                if stone_available_now > 0:
                    site_waiting_positive_stone_stock_ticks += 1
                if btype == "storage":
                    stats["storage_waiting_for_material_ticks"] = int(stats.get("storage_waiting_for_material_ticks", 0)) + 1
                elif btype == "house":
                    stats["house_waiting_for_material_ticks"] = int(stats.get("house_waiting_for_material_ticks", 0)) + 1
            else:
                stats["construction_site_waiting_for_builder_ticks"] = int(stats.get("construction_site_waiting_for_builder_ticks", 0)) + 1
                if btype == "storage":
                    stats["storage_waiting_for_builder_ticks"] = int(stats.get("storage_waiting_for_builder_ticks", 0)) + 1
                elif btype == "house":
                    stats["house_waiting_for_builder_ticks"] = int(stats.get("house_waiting_for_builder_ticks", 0)) + 1
                first_delivery = int(b.get("construction_first_delivery_tick", -1))
                first_progress = int(b.get("construction_first_progress_tick", -1))
                if first_delivery >= 0 and first_progress >= first_delivery:
                    delivery_to_work_gap_total += int(first_progress - first_delivery)
                    delivery_to_work_gap_samples += 1

            builders = b.get("construction_builder_ids", [])
            if isinstance(builders, (list, tuple, set)):
                distinct = len({str(x) for x in builders if str(x)})
                distinct_builders_total += int(distinct)
                distinct_builders_samples += 1
                if distinct > 0:
                    work_ticks_per_builder_total += float(max(0, progress)) / float(distinct)
                    work_ticks_per_builder_samples += 1

            created_tick = int(b.get("construction_created_tick", int(getattr(self, "tick", 0))))
            active_age_ticks_total += max(0, int(getattr(self, "tick", 0)) - created_tick)
            active_age_ticks_samples += 1
        stats["active_construction_sites"] = int(active_sites)
        stats["partially_built_sites_count"] = int(partial_sites)
        stats["construction_site_material_units_required_total"] = int(live_required_total)
        stats["construction_site_material_units_delivered_total_live"] = int(live_delivered_total)
        stats["construction_site_material_units_remaining"] = int(live_remaining_total)
        stats["construction_site_required_work_ticks_total"] = int(live_required_work_total)
        stats["construction_site_completed_work_ticks_total_live"] = int(live_completed_work_total)
        stats["construction_site_remaining_work_ticks"] = int(live_remaining_work_total)
        stats["construction_site_in_progress_ticks_total"] = int(stats.get("construction_site_in_progress_ticks_total", 0)) + int(in_progress_ticks_total)
        stats["construction_site_waiting_materials_ticks_total"] = int(stats.get("construction_site_waiting_materials_ticks_total", 0)) + int(waiting_material_ticks_total)
        stats["construction_site_buildable_but_idle_ticks_total"] = int(stats.get("construction_site_buildable_but_idle_ticks_total", 0)) + int(buildable_but_idle_ticks_total)
        stats["construction_site_distinct_builders_total"] = int(stats.get("construction_site_distinct_builders_total", 0)) + int(distinct_builders_total)
        stats["construction_site_distinct_builders_samples"] = int(stats.get("construction_site_distinct_builders_samples", 0)) + int(distinct_builders_samples)
        stats["construction_site_work_ticks_per_builder_total"] = float(stats.get("construction_site_work_ticks_per_builder_total", 0.0)) + float(work_ticks_per_builder_total)
        stats["construction_site_work_ticks_per_builder_samples"] = int(stats.get("construction_site_work_ticks_per_builder_samples", 0)) + int(work_ticks_per_builder_samples)
        stats["construction_site_delivery_to_work_gap_total"] = int(stats.get("construction_site_delivery_to_work_gap_total", 0)) + int(delivery_to_work_gap_total)
        stats["construction_site_delivery_to_work_gap_samples"] = int(stats.get("construction_site_delivery_to_work_gap_samples", 0)) + int(delivery_to_work_gap_samples)
        stats["construction_site_active_age_ticks_total"] = int(stats.get("construction_site_active_age_ticks_total", 0)) + int(active_age_ticks_total)
        stats["construction_site_active_age_ticks_samples"] = int(stats.get("construction_site_active_age_ticks_samples", 0)) + int(active_age_ticks_samples)
        stats["construction_site_nearest_wood_distance_total"] = int(
            stats.get("construction_site_nearest_wood_distance_total", 0)
        ) + int(site_nearest_wood_dist_total)
        stats["construction_site_nearest_wood_distance_samples"] = int(
            stats.get("construction_site_nearest_wood_distance_samples", 0)
        ) + int(site_nearest_wood_dist_samples)
        stats["construction_site_nearest_stone_distance_total"] = int(
            stats.get("construction_site_nearest_stone_distance_total", 0)
        ) + int(site_nearest_stone_dist_total)
        stats["construction_site_nearest_stone_distance_samples"] = int(
            stats.get("construction_site_nearest_stone_distance_samples", 0)
        ) + int(site_nearest_stone_dist_samples)
        stats["construction_site_viable_wood_sources_within_radius_total"] = int(
            stats.get("construction_site_viable_wood_sources_within_radius_total", 0)
        ) + int(site_viable_wood_total)
        stats["construction_site_viable_wood_sources_within_radius_samples"] = int(
            stats.get("construction_site_viable_wood_sources_within_radius_samples", 0)
        ) + int(site_viable_wood_samples)
        stats["construction_site_viable_stone_sources_within_radius_total"] = int(
            stats.get("construction_site_viable_stone_sources_within_radius_total", 0)
        ) + int(site_viable_stone_total)
        stats["construction_site_viable_stone_sources_within_radius_samples"] = int(
            stats.get("construction_site_viable_stone_sources_within_radius_samples", 0)
        ) + int(site_viable_stone_samples)
        stats["construction_site_zero_wood_sources_within_radius_ticks"] = int(
            stats.get("construction_site_zero_wood_sources_within_radius_ticks", 0)
        ) + int(site_zero_wood_ticks)
        stats["construction_site_zero_stone_sources_within_radius_ticks"] = int(
            stats.get("construction_site_zero_stone_sources_within_radius_ticks", 0)
        ) + int(site_zero_stone_ticks)
        stats["construction_site_local_wood_source_contention_total"] = float(
            stats.get("construction_site_local_wood_source_contention_total", 0.0)
        ) + float(site_local_wood_contention_total)
        stats["construction_site_local_wood_source_contention_samples"] = int(
            stats.get("construction_site_local_wood_source_contention_samples", 0)
        ) + int(site_local_wood_contention_samples)
        stats["construction_site_local_stone_source_contention_total"] = float(
            stats.get("construction_site_local_stone_source_contention_total", 0.0)
        ) + float(site_local_stone_contention_total)
        stats["construction_site_local_stone_source_contention_samples"] = int(
            stats.get("construction_site_local_stone_source_contention_samples", 0)
        ) + int(site_local_stone_contention_samples)
        stats["construction_site_ticks_since_last_delivery_total"] = int(
            stats.get("construction_site_ticks_since_last_delivery_total", 0)
        ) + int(site_ticks_since_last_delivery_total)
        stats["construction_site_ticks_since_last_delivery_samples"] = int(
            stats.get("construction_site_ticks_since_last_delivery_samples", 0)
        ) + int(site_ticks_since_last_delivery_samples)
        stats["construction_site_waiting_with_positive_wood_stock_ticks"] = int(
            stats.get("construction_site_waiting_with_positive_wood_stock_ticks", 0)
        ) + int(site_waiting_positive_wood_stock_ticks)
        stats["construction_site_waiting_with_positive_stone_stock_ticks"] = int(
            stats.get("construction_site_waiting_with_positive_stone_stock_ticks", 0)
        ) + int(site_waiting_positive_stone_stock_ticks)
        stats["construction_site_first_demand_to_first_delivery_total"] = int(
            stats.get("construction_site_first_demand_to_first_delivery_total", 0)
        ) + int(site_first_demand_to_first_delivery_total)
        stats["construction_site_first_demand_to_first_delivery_samples"] = int(
            stats.get("construction_site_first_demand_to_first_delivery_samples", 0)
        ) + int(site_first_demand_to_first_delivery_samples)
        stats["construction_site_material_inflow_rate_total"] = float(
            stats.get("construction_site_material_inflow_rate_total", 0.0)
        ) + float(site_material_inflow_rate_total)
        stats["construction_site_material_inflow_rate_samples"] = int(
            stats.get("construction_site_material_inflow_rate_samples", 0)
        ) + int(site_material_inflow_rate_samples)
        stats["construction_site_delivered_wood_units_total_live"] = int(site_delivered_wood_units_live)
        stats["construction_site_delivered_stone_units_total_live"] = int(site_delivered_stone_units_live)
        stats["construction_site_delivered_food_units_total_live"] = int(site_delivered_food_units_live)

        active_builders = [
            a
            for a in (self.agents or [])
            if getattr(a, "alive", False)
            and str(getattr(a, "role", "")) == "builder"
            and str(getattr(a, "task", "")) in {"build_house", "build_storage", "gather_materials"}
        ]
        active_haulers = [
            a
            for a in (self.agents or [])
            if getattr(a, "alive", False)
            and str(getattr(a, "role", "")) == "hauler"
            and str(getattr(a, "task", "")) in {"food_logistics", "village_logistics", "gather_materials"}
        ]
        stats["active_builders_count"] = int(len(active_builders))
        stats["active_haulers_count"] = int(len(active_haulers))
        for _a in active_builders:
            bdist_wood = _nearest_distance_to_sources(int(getattr(_a, "x", 0)), int(getattr(_a, "y", 0)), self.wood)
            bdist_stone = _nearest_distance_to_sources(int(getattr(_a, "x", 0)), int(getattr(_a, "y", 0)), self.stone)
            if bdist_wood >= 0:
                stats["active_builders_nearest_wood_distance_total"] = int(
                    stats.get("active_builders_nearest_wood_distance_total", 0)
                ) + int(bdist_wood)
                stats["active_builders_nearest_wood_distance_samples"] = int(
                    stats.get("active_builders_nearest_wood_distance_samples", 0)
                ) + 1
            if bdist_stone >= 0:
                stats["active_builders_nearest_stone_distance_total"] = int(
                    stats.get("active_builders_nearest_stone_distance_total", 0)
                ) + int(bdist_stone)
                stats["active_builders_nearest_stone_distance_samples"] = int(
                    stats.get("active_builders_nearest_stone_distance_samples", 0)
                ) + 1
        for _a in active_haulers:
            hdist_wood = _nearest_distance_to_sources(int(getattr(_a, "x", 0)), int(getattr(_a, "y", 0)), self.wood)
            hdist_stone = _nearest_distance_to_sources(int(getattr(_a, "x", 0)), int(getattr(_a, "y", 0)), self.stone)
            if hdist_wood >= 0:
                stats["active_haulers_nearest_wood_distance_total"] = int(
                    stats.get("active_haulers_nearest_wood_distance_total", 0)
                ) + int(hdist_wood)
                stats["active_haulers_nearest_wood_distance_samples"] = int(
                    stats.get("active_haulers_nearest_wood_distance_samples", 0)
                ) + 1
            if hdist_stone >= 0:
                stats["active_haulers_nearest_stone_distance_total"] = int(
                    stats.get("active_haulers_nearest_stone_distance_total", 0)
                ) + int(hdist_stone)
                stats["active_haulers_nearest_stone_distance_samples"] = int(
                    stats.get("active_haulers_nearest_stone_distance_samples", 0)
                ) + 1
        stats["construction_build_state_planned_count"] = int(state_counts.get("planned", 0))
        stats["construction_build_state_supplying_count"] = int(state_counts.get("supplying", 0))
        stats["construction_build_state_buildable_count"] = int(state_counts.get("buildable", 0))
        stats["construction_build_state_in_progress_count"] = int(state_counts.get("in_progress", 0))
        stats["construction_build_state_paused_count"] = int(state_counts.get("paused", 0))
        stats["construction_build_state_completed_count"] = int(state_counts.get("completed", 0))
        stats["construction_near_complete_sites_count"] = int(near_complete_sites)
        local_memory = self.local_practice_memory if isinstance(self.local_practice_memory, dict) else {}
        stats["active_cultural_practices"] = int(len(local_memory))
        counts_by_type: Dict[str, int] = {
            "productive_food_patch": 0,
            "good_gathering_zone": 0,
            "proto_farm_area": 0,
            "construction_cluster": 0,
            "stable_storage_area": 0,
        }
        for entry in local_memory.values():
            if not isinstance(entry, dict):
                continue
            ptype = str(entry.get("practice_type", ""))
            if ptype in counts_by_type:
                counts_by_type[ptype] = int(counts_by_type.get(ptype, 0)) + 1
        stats["productive_food_patch_practices"] = int(
            counts_by_type.get("productive_food_patch", 0) + counts_by_type.get("good_gathering_zone", 0)
        )
        stats["proto_farm_practices"] = int(counts_by_type.get("proto_farm_area", 0))
        stats["construction_cluster_practices"] = int(
            counts_by_type.get("construction_cluster", 0) + counts_by_type.get("stable_storage_area", 0)
        )

        self.settlement_progression_stats = stats

    def compute_settlement_progression_snapshot(self) -> Dict[str, Any]:
        stats = self.settlement_progression_stats if isinstance(self.settlement_progression_stats, dict) else _default_settlement_progression_stats()
        rate_samples = int(stats.get("_surplus_rate_samples", 0))
        food_rate = float(stats.get("_surplus_food_rate_sum_scaled", 0)) / 1000.0
        resource_rate = float(stats.get("_surplus_resource_rate_sum_scaled", 0)) / 1000.0
        storage_attempts = int(stats.get("storage_emergence_attempts", 0))
        storage_completions = int(stats.get("storage_construction_completed_count", 0))
        storage_completion_rate = float(storage_completions) / float(max(1, storage_attempts))
        site_lifetime_samples = int(stats.get("construction_site_lifetime_samples", 0))
        site_completion_samples = int(stats.get("construction_site_completion_time_samples", 0))
        site_abandon_samples = int(stats.get("construction_site_progress_before_abandon_samples", 0))
        site_missing_samples = int(stats.get("construction_site_material_units_missing_samples", 0))
        site_first_arrival_samples = int(stats.get("construction_site_first_builder_arrival_delay_samples", 0))
        site_material_ready_to_work_samples = int(stats.get("construction_site_material_ready_to_first_work_delay_samples", 0))
        house_completion_samples = int(stats.get("house_completion_time_samples", 0))
        storage_completion_samples = int(stats.get("storage_completion_time_samples", 0))
        commitment_duration_samples = int(stats.get("builder_commitment_duration_samples", 0))
        commitment_resume_delay_samples = int(stats.get("builder_commitment_resume_delay_samples", 0))
        distinct_builders_samples = int(stats.get("construction_site_distinct_builders_samples", 0))
        work_ticks_per_builder_samples = int(stats.get("construction_site_work_ticks_per_builder_samples", 0))
        delivery_to_work_gap_samples = int(stats.get("construction_site_delivery_to_work_gap_samples", 0))
        active_age_ticks_samples = int(stats.get("construction_site_active_age_ticks_samples", 0))
        site_nearest_wood_samples = int(stats.get("construction_site_nearest_wood_distance_samples", 0))
        site_nearest_stone_samples = int(stats.get("construction_site_nearest_stone_distance_samples", 0))
        site_viable_wood_samples = int(stats.get("construction_site_viable_wood_sources_within_radius_samples", 0))
        site_viable_stone_samples = int(stats.get("construction_site_viable_stone_sources_within_radius_samples", 0))
        site_local_wood_contention_samples = int(stats.get("construction_site_local_wood_source_contention_samples", 0))
        site_local_stone_contention_samples = int(stats.get("construction_site_local_stone_source_contention_samples", 0))
        site_last_delivery_samples = int(stats.get("construction_site_ticks_since_last_delivery_samples", 0))
        site_first_demand_to_first_delivery_samples = int(
            stats.get("construction_site_first_demand_to_first_delivery_samples", 0)
        )
        site_material_inflow_samples = int(stats.get("construction_site_material_inflow_rate_samples", 0))
        active_builder_wood_samples = int(stats.get("active_builders_nearest_wood_distance_samples", 0))
        active_builder_stone_samples = int(stats.get("active_builders_nearest_stone_distance_samples", 0))
        active_hauler_wood_samples = int(stats.get("active_haulers_nearest_wood_distance_samples", 0))
        active_hauler_stone_samples = int(stats.get("active_haulers_nearest_stone_distance_samples", 0))
        first_food_latency_samples = int(stats.get("time_spawn_to_first_food_acquisition_samples", 0))
        high_hunger_latency_samples = int(stats.get("time_high_hunger_to_eat_samples", 0))
        acquisition_interval_samples = int(stats.get("food_acquisition_interval_ticks_samples", 0))
        acquisition_distance_samples = int(stats.get("food_acquisition_distance_samples", 0))
        consumption_interval_samples = int(stats.get("food_consumption_interval_ticks_samples", 0))
        food_inventory_samples = int(stats.get("agent_food_inventory_samples", 0))
        agent_tick_samples = int(stats.get("agent_ticks_total", 0))
        basin_access_samples = int(stats.get("local_food_basin_accessible_samples", 0))
        basin_ratio_samples = int(stats.get("local_food_basin_pressure_ratio_samples", 0))
        basin_compete_samples = int(stats.get("local_food_basin_competing_agents_samples", 0))
        basin_distance_samples = int(stats.get("local_food_basin_nearest_food_distance_samples", 0))
        layer_samples = int(stats.get("food_security_layer_samples", 0))
        reserve_samples = int(stats.get("reserve_total_food_observed_samples", 0))
        reserve_draw_hunger_samples = int(stats.get("reserve_draw_hunger_samples", 0))
        layer_total_ticks = max(
            1,
            int(stats.get("food_security_layer_self_feeding_ticks_total", 0))
            + int(stats.get("food_security_layer_group_feeding_ticks_total", 0))
            + int(stats.get("food_security_layer_reserve_accumulation_ticks_total", 0))
            + int(stats.get("food_security_layer_none_ticks_total", 0)),
        )
        dead_age_list = stats.get("_dead_agent_ages_sorted", [])
        if not isinstance(dead_age_list, list):
            dead_age_list = []
        dead_age_sorted = sorted(int(max(0, a)) for a in dead_age_list)
        dead_age_count = int(len(dead_age_sorted))
        dead_age_median = 0.0
        if dead_age_count > 0:
            mid = dead_age_count // 2
            if dead_age_count % 2 == 1:
                dead_age_median = float(dead_age_sorted[mid])
            else:
                dead_age_median = (float(dead_age_sorted[mid - 1]) + float(dead_age_sorted[mid])) / 2.0
        dead_age_avg = float(stats.get("_dead_agent_ages_sum", 0)) / float(max(1, int(stats.get("_dead_agent_ages_count", 0))))
        return {
            "population_alive": int(stats.get("population_alive", 0)),
            "population_births_count": int(stats.get("population_births_count", 0)),
            "population_deaths_count": int(stats.get("population_deaths_count", 0)),
            "population_deaths_hunger_count": int(stats.get("population_deaths_hunger_count", 0)),
            "population_deaths_exhaustion_count": int(stats.get("population_deaths_exhaustion_count", 0)),
            "population_deaths_other_count": int(stats.get("population_deaths_other_count", 0)),
            "population_deaths_hunger_age_0_199_count": int(stats.get("population_deaths_hunger_age_0_199_count", 0)),
            "population_deaths_hunger_age_200_599_count": int(stats.get("population_deaths_hunger_age_200_599_count", 0)),
            "population_deaths_hunger_age_600_plus_count": int(stats.get("population_deaths_hunger_age_600_plus_count", 0)),
            "hunger_deaths_before_first_food_acquisition": int(
                stats.get("hunger_deaths_before_first_food_acquisition", 0)
            ),
            "population_net_change": int(stats.get("population_net_change", 0)),
            "agent_average_age": float(stats.get("agent_average_age", 0.0)),
            "agent_median_age_at_death": round(float(dead_age_median), 4),
            "agent_average_lifespan_at_death": round(float(dead_age_avg), 4),
            "avg_time_spawn_to_first_food_acquisition": round(
                float(stats.get("time_spawn_to_first_food_acquisition_total", 0))
                / float(max(1, first_food_latency_samples)),
                4,
            ),
            "avg_time_high_hunger_to_eat": round(
                float(stats.get("time_high_hunger_to_eat_total", 0))
                / float(max(1, high_hunger_latency_samples)),
                4,
            ),
            "avg_food_acquisition_interval_ticks": round(
                float(stats.get("food_acquisition_interval_ticks_total", 0))
                / float(max(1, acquisition_interval_samples)),
                4,
            ),
            "avg_food_acquisition_distance": round(
                float(stats.get("food_acquisition_distance_total", 0))
                / float(max(1, acquisition_distance_samples)),
                4,
            ),
            "avg_food_consumption_interval_ticks": round(
                float(stats.get("food_consumption_interval_ticks_total", 0))
                / float(max(1, consumption_interval_samples)),
                4,
            ),
            "failed_food_seeking_attempts": int(stats.get("failed_food_seeking_attempts", 0)),
            "fallback_food_search_activations": int(stats.get("fallback_food_search_activations", 0)),
            "early_life_food_inventory_acquisition_count": int(
                stats.get("early_life_food_inventory_acquisition_count", 0)
            ),
            "high_hunger_to_eat_events_started": int(stats.get("high_hunger_to_eat_events_started", 0)),
            "agent_hunger_relapse_after_first_food_count": int(
                stats.get("agent_hunger_relapse_after_first_food_count", 0)
            ),
            "early_food_priority_overrides": int(stats.get("early_food_priority_overrides", 0)),
            "medium_term_food_priority_overrides": int(stats.get("medium_term_food_priority_overrides", 0)),
            "avg_local_food_inventory_per_agent": round(
                float(stats.get("agent_food_inventory_total", 0)) / float(max(1, food_inventory_samples)),
                4,
            ),
            "food_seeking_time_ratio": round(
                float(stats.get("food_seeking_ticks_total", 0)) / float(max(1, agent_tick_samples)),
                4,
            ),
            "food_source_contention_events": int(stats.get("food_source_contention_events", 0)),
            "food_source_depletion_events": int(stats.get("food_source_depletion_events", 0)),
            "food_respawned_total_observed": int(stats.get("food_respawned_total_observed", 0)),
            "food_acquisition_events_total": int(stats.get("food_acquisition_events_total", 0)),
            "food_self_feeding_events": int(stats.get("food_self_feeding_events", 0)),
            "food_self_feeding_units": int(stats.get("food_self_feeding_units", 0)),
            "food_group_feeding_events": int(stats.get("food_group_feeding_events", 0)),
            "food_group_feeding_units": int(stats.get("food_group_feeding_units", 0)),
            "food_reserve_accumulation_events": int(stats.get("food_reserve_accumulation_events", 0)),
            "food_reserve_accumulation_units": int(stats.get("food_reserve_accumulation_units", 0)),
            "food_reserve_draw_events": int(stats.get("food_reserve_draw_events", 0)),
            "food_reserve_draw_units": int(stats.get("food_reserve_draw_units", 0)),
            "food_reserve_balance_units": int(stats.get("food_reserve_accumulation_units", 0))
            - int(stats.get("food_reserve_draw_units", 0)),
            "total_food_in_reserves": int(stats.get("_reserve_total_food_prev_tick", 0)),
            "avg_food_in_reserves": round(
                float(stats.get("reserve_total_food_observed_sum", 0))
                / float(max(1, reserve_samples)),
                4,
            ),
            "max_food_in_reserves": int(stats.get("reserve_total_food_observed_max", 0)),
            "reserve_fill_events": int(stats.get("reserve_fill_events", 0)),
            "reserve_depletion_events": int(stats.get("reserve_depletion_events", 0)),
            "ticks_reserve_above_threshold": int(stats.get("ticks_reserve_above_threshold", 0)),
            "ticks_reserve_empty": int(stats.get("ticks_reserve_empty", 0)),
            "reserve_recovery_cycles": int(stats.get("reserve_recovery_cycles", 0)),
            "reserve_partial_recovery_cycles": int(stats.get("reserve_partial_recovery_cycles", 0)),
            "reserve_full_recovery_cycles": int(stats.get("reserve_full_recovery_cycles", 0)),
            "reserve_failed_recovery_attempts": int(stats.get("reserve_failed_recovery_attempts", 0)),
            "reserve_refill_attempts": int(stats.get("reserve_refill_attempts", 0)),
            "reserve_refill_success": int(stats.get("reserve_refill_success", 0)),
            "avg_food_added_per_refill": round(
                float(stats.get("reserve_refill_food_added_total", 0))
                / float(max(1, int(stats.get("reserve_refill_success", 0)))),
                4,
            ),
            "ticks_between_reserve_refills": round(
                float(stats.get("reserve_refill_interval_ticks_total", 0))
                / float(max(1, int(stats.get("reserve_refill_interval_ticks_samples", 0)))),
                4,
            ),
            "avg_food_draw_per_event": round(
                float(stats.get("food_reserve_draw_units", 0))
                / float(max(1, int(stats.get("food_reserve_draw_events", 0)))),
                4,
            ),
            "ticks_between_reserve_draws": round(
                float(stats.get("reserve_draw_interval_ticks_total", 0))
                / float(max(1, int(stats.get("reserve_draw_interval_ticks_samples", 0)))),
                4,
            ),
            "reserve_draw_after_failed_foraging_trip": int(
                stats.get("reserve_usage_after_failed_foraging_trip", 0)
            ),
            "reserve_draw_under_pressure": int(
                stats.get("reserve_draw_events_during_food_stress", 0)
            ),
            "reserve_draw_under_normal_conditions": int(
                stats.get("reserve_draw_events_during_normal_conditions", 0)
            ),
            "reserve_refill_blocked_by_pressure": int(
                stats.get("reserve_refill_blocked_by_pressure", 0)
            ),
            "reserve_refill_blocked_by_no_surplus": int(
                stats.get("reserve_refill_blocked_by_no_surplus", 0)
            ),
            "reserve_refill_blocked_by_unstable_context": int(
                stats.get("reserve_refill_blocked_by_unstable_context", 0)
            ),
            "local_food_handoff_events": int(stats.get("local_food_handoff_events", 0)),
            "local_food_handoff_units": int(stats.get("local_food_handoff_units", 0)),
            "handoff_allowed_by_context_count": int(
                stats.get("handoff_allowed_by_context_count", 0)
            ),
            "handoff_blocked_by_group_priority_count": int(
                stats.get("handoff_blocked_by_group_priority_count", 0)
            ),
            "handoff_blocked_by_cooldown_count": int(
                stats.get("handoff_blocked_by_cooldown_count", 0)
            ),
            "handoff_blocked_by_same_unit_recently_count": int(
                stats.get("handoff_blocked_by_same_unit_recently_count", 0)
            ),
            "handoff_blocked_by_receiver_viability": int(
                stats.get("handoff_blocked_by_receiver_viability", 0)
            ),
            "handoff_blocked_by_camp_fragility": int(
                stats.get("handoff_blocked_by_camp_fragility", 0)
            ),
            "handoff_blocked_by_recent_rescue": int(
                stats.get("handoff_blocked_by_recent_rescue", 0)
            ),
            "handoff_blocked_by_camp_fragility_when_receiver_critical_count": int(
                stats.get("handoff_blocked_by_camp_fragility_when_receiver_critical_count", 0)
            ),
            "handoff_blocked_by_camp_fragility_when_donor_safe_count": int(
                stats.get("handoff_blocked_by_camp_fragility_when_donor_safe_count", 0)
            ),
            "handoff_blocked_by_camp_fragility_with_local_surplus_count": int(
                stats.get("handoff_blocked_by_camp_fragility_with_local_surplus_count", 0)
            ),
            "handoff_blocked_by_camp_fragility_context_pressure_count": int(
                stats.get("handoff_blocked_by_camp_fragility_context_pressure_count", 0)
            ),
            "handoff_blocked_by_camp_fragility_context_nonpressure_count": int(
                stats.get("handoff_blocked_by_camp_fragility_context_nonpressure_count", 0)
            ),
            "avg_handoff_blocked_by_camp_fragility_donor_food": round(
                float(stats.get("handoff_blocked_by_camp_fragility_donor_food_sum", 0))
                / float(max(1, int(stats.get("handoff_blocked_by_camp_fragility_donor_food_samples", 0)))),
                4,
            ),
            "avg_handoff_blocked_by_camp_fragility_receiver_hunger": round(
                float(stats.get("handoff_blocked_by_camp_fragility_receiver_hunger_sum", 0.0))
                / float(max(1, int(stats.get("handoff_blocked_by_camp_fragility_receiver_hunger_samples", 0)))),
                4,
            ),
            "avg_handoff_blocked_by_camp_fragility_camp_food": round(
                float(stats.get("handoff_blocked_by_camp_fragility_camp_food_sum", 0))
                / float(max(1, int(stats.get("handoff_blocked_by_camp_fragility_camp_food_samples", 0)))),
                4,
            ),
            "local_food_handoff_prevented_by_low_surplus": int(
                stats.get("local_food_handoff_prevented_by_low_surplus", 0)
            ),
            "local_food_handoff_prevented_by_distance": int(
                stats.get("local_food_handoff_prevented_by_distance", 0)
            ),
            "local_food_handoff_prevented_by_donor_risk": int(
                stats.get("local_food_handoff_prevented_by_donor_risk", 0)
            ),
            "hunger_relief_after_local_handoff": round(
                float(stats.get("hunger_relief_after_local_handoff_total", 0.0))
                / float(max(1, int(stats.get("hunger_relief_after_local_handoff_samples", 0)))),
                4,
            ),
            "average_settlement_food_buffer": round(
                float(stats.get("reserve_total_food_observed_sum", 0))
                / float(max(1, reserve_samples)),
                4,
            ),
            "longest_reserve_continuity_window": int(stats.get("reserve_continuity_longest_window", 0)),
            "settlement_food_shortage_events": int(stats.get("settlement_food_shortage_events", 0)),
            "hunger_deaths_with_reserve_available": int(stats.get("hunger_deaths_with_reserve_available", 0)),
            "hunger_deaths_without_reserve": int(stats.get("hunger_deaths_without_reserve", 0)),
            "avg_agent_hunger_when_reserve_used": round(
                float(stats.get("reserve_draw_hunger_sum", 0.0))
                / float(max(1, reserve_draw_hunger_samples)),
                4,
            ),
            "reserve_draw_events_during_food_stress": int(stats.get("reserve_draw_events_during_food_stress", 0)),
            "reserve_draw_events_during_normal_conditions": int(
                stats.get("reserve_draw_events_during_normal_conditions", 0)
            ),
            "reserve_usage_after_failed_foraging_trip": int(
                stats.get("reserve_usage_after_failed_foraging_trip", 0)
            ),
            "food_security_layer_transition_count": int(stats.get("food_security_layer_transition_count", 0)),
            "food_security_layer_transition_none_to_self_feeding": int(
                stats.get("food_security_layer_transition_none_to_self_feeding", 0)
            ),
            "food_security_layer_transition_none_to_group_feeding": int(
                stats.get("food_security_layer_transition_none_to_group_feeding", 0)
            ),
            "food_security_layer_transition_none_to_reserve_accumulation": int(
                stats.get("food_security_layer_transition_none_to_reserve_accumulation", 0)
            ),
            "food_security_layer_transition_none_to_none": int(
                stats.get("food_security_layer_transition_none_to_none", 0)
            ),
            "food_security_layer_transition_self_feeding_to_self_feeding": int(
                stats.get("food_security_layer_transition_self_feeding_to_self_feeding", 0)
            ),
            "food_security_layer_transition_self_feeding_to_group_feeding": int(
                stats.get("food_security_layer_transition_self_feeding_to_group_feeding", 0)
            ),
            "food_security_layer_transition_self_feeding_to_reserve_accumulation": int(
                stats.get("food_security_layer_transition_self_feeding_to_reserve_accumulation", 0)
            ),
            "food_security_layer_transition_self_feeding_to_none": int(
                stats.get("food_security_layer_transition_self_feeding_to_none", 0)
            ),
            "food_security_layer_transition_group_feeding_to_self_feeding": int(
                stats.get("food_security_layer_transition_group_feeding_to_self_feeding", 0)
            ),
            "food_security_layer_transition_group_feeding_to_group_feeding": int(
                stats.get("food_security_layer_transition_group_feeding_to_group_feeding", 0)
            ),
            "food_security_layer_transition_group_feeding_to_reserve_accumulation": int(
                stats.get("food_security_layer_transition_group_feeding_to_reserve_accumulation", 0)
            ),
            "food_security_layer_transition_group_feeding_to_none": int(
                stats.get("food_security_layer_transition_group_feeding_to_none", 0)
            ),
            "food_security_layer_transition_reserve_accumulation_to_self_feeding": int(
                stats.get("food_security_layer_transition_reserve_accumulation_to_self_feeding", 0)
            ),
            "food_security_layer_transition_reserve_accumulation_to_group_feeding": int(
                stats.get("food_security_layer_transition_reserve_accumulation_to_group_feeding", 0)
            ),
            "food_security_layer_transition_reserve_accumulation_to_reserve_accumulation": int(
                stats.get("food_security_layer_transition_reserve_accumulation_to_reserve_accumulation", 0)
            ),
            "food_security_layer_transition_reserve_accumulation_to_none": int(
                stats.get("food_security_layer_transition_reserve_accumulation_to_none", 0)
            ),
            "food_security_reserve_entry_checks": int(stats.get("food_security_reserve_entry_checks", 0)),
            "food_security_reserve_entry_condition_met_count": int(
                stats.get("food_security_reserve_entry_condition_met_count", 0)
            ),
            "food_security_reserve_entry_activated_count": int(
                stats.get("food_security_reserve_entry_activated_count", 0)
            ),
            "food_security_reserve_entry_blocked_no_surplus": int(
                stats.get("food_security_reserve_entry_blocked_no_surplus", 0)
            ),
            "food_security_reserve_entry_blocked_no_qualifying_task": int(
                stats.get("food_security_reserve_entry_blocked_no_qualifying_task", 0)
            ),
            "food_security_reserve_entry_blocked_unstable_context": int(
                stats.get("food_security_reserve_entry_blocked_unstable_context", 0)
            ),
            "food_security_reserve_entry_blocked_group_feeding_dominance": int(
                stats.get("food_security_reserve_entry_blocked_group_feeding_dominance", 0)
            ),
            "food_security_reserve_prepolicy_candidate_count": int(
                stats.get("food_security_reserve_prepolicy_candidate_count", 0)
            ),
            "food_security_reserve_postpolicy_candidate_count": int(
                stats.get("food_security_reserve_postpolicy_candidate_count", 0)
            ),
            "food_security_reserve_final_activation_count": int(
                stats.get("food_security_reserve_final_activation_count", 0)
            ),
            "food_security_reserve_selection_considered_count": int(
                stats.get("food_security_reserve_selection_considered_count", 0)
            ),
            "food_security_reserve_selection_chosen_count": int(
                stats.get("food_security_reserve_selection_chosen_count", 0)
            ),
            "food_security_reserve_selection_rejected_count": int(
                stats.get("food_security_reserve_selection_rejected_count", 0)
            ),
            "food_security_reserve_selection_rejected_by_group_feeding_count": int(
                stats.get("food_security_reserve_selection_rejected_by_group_feeding_count", 0)
            ),
            "food_security_reserve_selection_rejected_by_unstable_context_count": int(
                stats.get("food_security_reserve_selection_rejected_by_unstable_context_count", 0)
            ),
            "food_security_reserve_selection_rejected_by_no_surplus_count": int(
                stats.get("food_security_reserve_selection_rejected_by_no_surplus_count", 0)
            ),
            "food_security_reserve_selection_rejected_by_other_count": int(
                stats.get("food_security_reserve_selection_rejected_by_other_count", 0)
            ),
            "food_security_reserve_final_selection_lost_to_self_feeding_count": int(
                stats.get("food_security_reserve_final_selection_lost_to_self_feeding_count", 0)
            ),
            "food_security_reserve_final_selection_lost_to_group_feeding_count": int(
                stats.get("food_security_reserve_final_selection_lost_to_group_feeding_count", 0)
            ),
            "food_security_reserve_final_selection_lost_to_unstable_context_count": int(
                stats.get("food_security_reserve_final_selection_lost_to_unstable_context_count", 0)
            ),
            "food_security_reserve_final_selection_lost_to_no_surplus_count": int(
                stats.get("food_security_reserve_final_selection_lost_to_no_surplus_count", 0)
            ),
            "food_security_reserve_final_selection_lost_to_other_count": int(
                stats.get("food_security_reserve_final_selection_lost_to_other_count", 0)
            ),
            "food_security_reserve_final_selection_winner_self_feeding_count": int(
                stats.get("food_security_reserve_final_selection_winner_self_feeding_count", 0)
            ),
            "food_security_reserve_final_selection_winner_group_feeding_count": int(
                stats.get("food_security_reserve_final_selection_winner_group_feeding_count", 0)
            ),
            "food_security_reserve_final_selection_winner_other_count": int(
                stats.get("food_security_reserve_final_selection_winner_other_count", 0)
            ),
            "food_security_reserve_loss_stage_policy_ranking_count": int(
                stats.get("food_security_reserve_loss_stage_policy_ranking_count", 0)
            ),
            "food_security_reserve_loss_stage_final_gate_count": int(
                stats.get("food_security_reserve_loss_stage_final_gate_count", 0)
            ),
            "food_security_reserve_loss_stage_final_override_count": int(
                stats.get("food_security_reserve_loss_stage_final_override_count", 0)
            ),
            "food_security_reserve_final_decision_observed_count": int(
                stats.get("food_security_reserve_final_decision_observed_count", 0)
            ),
            "food_security_reserve_final_decision_candidate_count": int(
                stats.get("food_security_reserve_final_decision_candidate_count", 0)
            ),
            "food_security_reserve_final_decision_candidate_survived_prepolicy_count": int(
                stats.get("food_security_reserve_final_decision_candidate_survived_prepolicy_count", 0)
            ),
            "food_security_reserve_final_decision_candidate_survived_postpolicy_count": int(
                stats.get("food_security_reserve_final_decision_candidate_survived_postpolicy_count", 0)
            ),
            "food_security_reserve_final_decision_candidate_lost_count": int(
                stats.get("food_security_reserve_final_decision_candidate_lost_count", 0)
            ),
            "food_security_reserve_final_decision_candidate_chosen_count": int(
                stats.get("food_security_reserve_final_decision_candidate_chosen_count", 0)
            ),
            "food_security_reserve_final_selected_task_food_logistics_count": int(
                stats.get("food_security_reserve_final_selected_task_food_logistics_count", 0)
            ),
            "food_security_reserve_final_selected_task_village_logistics_count": int(
                stats.get("food_security_reserve_final_selected_task_village_logistics_count", 0)
            ),
            "food_security_reserve_final_selected_task_camp_supply_food_count": int(
                stats.get("food_security_reserve_final_selected_task_camp_supply_food_count", 0)
            ),
            "food_security_reserve_final_selected_task_other_count": int(
                stats.get("food_security_reserve_final_selected_task_other_count", 0)
            ),
            "food_security_reserve_final_selected_layer_reserve_accumulation_count": int(
                stats.get("food_security_reserve_final_selected_layer_reserve_accumulation_count", 0)
            ),
            "food_security_reserve_final_selected_layer_group_feeding_count": int(
                stats.get("food_security_reserve_final_selected_layer_group_feeding_count", 0)
            ),
            "food_security_reserve_final_selected_layer_self_feeding_count": int(
                stats.get("food_security_reserve_final_selected_layer_self_feeding_count", 0)
            ),
            "food_security_reserve_final_selected_layer_none_count": int(
                stats.get("food_security_reserve_final_selected_layer_none_count", 0)
            ),
            "food_security_reserve_final_winner_subsystem_policy_ranking_count": int(
                stats.get("food_security_reserve_final_winner_subsystem_policy_ranking_count", 0)
            ),
            "food_security_reserve_final_winner_subsystem_role_task_update_count": int(
                stats.get("food_security_reserve_final_winner_subsystem_role_task_update_count", 0)
            ),
            "food_security_reserve_final_winner_subsystem_final_gate_count": int(
                stats.get("food_security_reserve_final_winner_subsystem_final_gate_count", 0)
            ),
            "food_security_reserve_final_winner_subsystem_final_override_count": int(
                stats.get("food_security_reserve_final_winner_subsystem_final_override_count", 0)
            ),
            "food_security_reserve_final_winner_subsystem_task_layer_routing_count": int(
                stats.get("food_security_reserve_final_winner_subsystem_task_layer_routing_count", 0)
            ),
            "food_security_reserve_final_winner_subsystem_contextual_override_count": int(
                stats.get("food_security_reserve_final_winner_subsystem_contextual_override_count", 0)
            ),
            "food_security_reserve_final_winner_subsystem_unknown_count": int(
                stats.get("food_security_reserve_final_winner_subsystem_unknown_count", 0)
            ),
            "food_security_reserve_final_override_reason_group_feeding_pressure_override_count": int(
                stats.get("food_security_reserve_final_override_reason_group_feeding_pressure_override_count", 0)
            ),
            "food_security_reserve_final_override_reason_village_logistics_group_routing_count": int(
                stats.get("food_security_reserve_final_override_reason_village_logistics_group_routing_count", 0)
            ),
            "food_security_reserve_final_override_reason_camp_supply_group_routing_count": int(
                stats.get("food_security_reserve_final_override_reason_camp_supply_group_routing_count", 0)
            ),
            "food_security_reserve_final_override_reason_unstable_context_count": int(
                stats.get("food_security_reserve_final_override_reason_unstable_context_count", 0)
            ),
            "food_security_reserve_final_override_reason_no_surplus_count": int(
                stats.get("food_security_reserve_final_override_reason_no_surplus_count", 0)
            ),
            "food_security_reserve_final_override_reason_other_count": int(
                stats.get("food_security_reserve_final_override_reason_other_count", 0)
            ),
            "reserve_final_tiebreak_invoked_count": int(
                stats.get("reserve_final_tiebreak_invoked_count", 0)
            ),
            "reserve_final_tiebreak_won_count": int(
                stats.get("reserve_final_tiebreak_won_count", 0)
            ),
            "reserve_final_tiebreak_lost_count": int(
                stats.get("reserve_final_tiebreak_lost_count", 0)
            ),
            "reserve_final_tiebreak_blocked_by_pressure_count": int(
                stats.get("reserve_final_tiebreak_blocked_by_pressure_count", 0)
            ),
            "reserve_final_tiebreak_blocked_by_unstable_context_count": int(
                stats.get("reserve_final_tiebreak_blocked_by_unstable_context_count", 0)
            ),
            "reserve_final_tiebreak_blocked_by_no_surplus_count": int(
                stats.get("reserve_final_tiebreak_blocked_by_no_surplus_count", 0)
            ),
            "ratio_food_security_layer_self_feeding": round(
                float(stats.get("food_security_layer_self_feeding_ticks_total", 0))
                / float(layer_total_ticks),
                4,
            ),
            "ratio_food_security_layer_group_feeding": round(
                float(stats.get("food_security_layer_group_feeding_ticks_total", 0))
                / float(layer_total_ticks),
                4,
            ),
            "ratio_food_security_layer_reserve_accumulation": round(
                float(stats.get("food_security_layer_reserve_accumulation_ticks_total", 0))
                / float(layer_total_ticks),
                4,
            ),
            "ratio_food_security_layer_none": round(
                float(stats.get("food_security_layer_none_ticks_total", 0))
                / float(layer_total_ticks),
                4,
            ),
            "avg_agents_in_food_security_layer_self_feeding": round(
                float(stats.get("food_security_layer_agents_self_feeding_total", 0))
                / float(max(1, layer_samples)),
                4,
            ),
            "avg_agents_in_food_security_layer_group_feeding": round(
                float(stats.get("food_security_layer_agents_group_feeding_total", 0))
                / float(max(1, layer_samples)),
                4,
            ),
            "avg_agents_in_food_security_layer_reserve_accumulation": round(
                float(stats.get("food_security_layer_agents_reserve_accumulation_total", 0))
                / float(max(1, layer_samples)),
                4,
            ),
            "avg_agents_in_food_security_layer_none": round(
                float(stats.get("food_security_layer_agents_none_total", 0))
                / float(max(1, layer_samples)),
                4,
            ),
            "foraging_trip_started_count": int(stats.get("foraging_trip_started_count", 0)),
            "foraging_trip_completed_count": int(stats.get("foraging_trip_completed_count", 0)),
            "foraging_trip_zero_harvest_count": int(stats.get("foraging_trip_zero_harvest_count", 0)),
            "foraging_trip_terminated_by_hunger_count": int(stats.get("foraging_trip_terminated_by_hunger_count", 0)),
            "foraging_trip_wasted_arrival_count": int(stats.get("foraging_trip_wasted_arrival_count", 0)),
            "foraging_arrival_depleted_source_count": int(stats.get("foraging_arrival_depleted_source_count", 0)),
            "foraging_arrival_overcontested_count": int(stats.get("foraging_arrival_overcontested_count", 0)),
            "foraging_source_visit_count": int(stats.get("foraging_source_visit_count", 0)),
            "avg_foraging_trip_food_gained": round(
                float(stats.get("foraging_trip_food_gained_total", 0))
                / float(max(1, int(stats.get("foraging_trip_completed_count", 0)))),
                4,
            ),
            "avg_foraging_trip_move_before_first_harvest": round(
                float(stats.get("foraging_trip_move_before_first_harvest_total", 0))
                / float(max(1, int(stats.get("foraging_trip_move_before_first_harvest_samples", 0)))),
                4,
            ),
            "avg_foraging_trip_harvest_actions": round(
                float(stats.get("foraging_trip_harvest_actions_total", 0))
                / float(max(1, int(stats.get("foraging_trip_completed_count", 0)))),
                4,
            ),
            "avg_harvest_actions_per_visited_source": round(
                float(stats.get("foraging_trip_harvest_actions_total", 0))
                / float(max(1, int(stats.get("foraging_source_visit_count", 0)))),
                4,
            ),
            "avg_visits_per_source_before_depletion": round(
                float(stats.get("foraging_source_visit_count", 0))
                / float(max(1, int(stats.get("food_source_depletion_events", 0)))),
                4,
            ),
            "foraging_zero_harvest_trip_ratio": round(
                float(stats.get("foraging_trip_zero_harvest_count", 0))
                / float(max(1, int(stats.get("foraging_trip_completed_count", 0)))),
                4,
            ),
            "avg_foraging_trip_retarget_count": round(
                float(stats.get("foraging_trip_retarget_count_total", 0))
                / float(max(1, int(stats.get("foraging_trip_completed_count", 0)))),
                4,
            ),
            "avg_foraging_target_lock_duration": round(
                float(stats.get("foraging_target_lock_duration_total", 0))
                / float(max(1, int(stats.get("foraging_target_lock_duration_samples", 0)))),
                4,
            ),
            "avg_foraging_commit_before_retarget_ticks": round(
                float(stats.get("foraging_commit_before_retarget_ticks_total", 0))
                / float(max(1, int(stats.get("foraging_commit_before_retarget_ticks_samples", 0)))),
                4,
            ),
            "avg_foraging_trip_efficiency_ratio": round(
                float(stats.get("foraging_trip_efficiency_ratio_sum", 0.0))
                / float(max(1, int(stats.get("foraging_trip_efficiency_ratio_samples", 0)))),
                4,
            ),
            "foraging_retarget_events": int(stats.get("foraging_retarget_events", 0)),
            "foraging_retarget_events_pressure_low": int(stats.get("foraging_retarget_events_pressure_low", 0)),
            "foraging_retarget_events_pressure_medium": int(stats.get("foraging_retarget_events_pressure_medium", 0)),
            "foraging_retarget_events_pressure_high": int(stats.get("foraging_retarget_events_pressure_high", 0)),
            "foraging_trip_aborted_before_first_harvest_count": int(
                stats.get("foraging_trip_aborted_before_first_harvest_count", 0)
            ),
            "foraging_trip_aborted_after_first_harvest_count": int(
                stats.get("foraging_trip_aborted_after_first_harvest_count", 0)
            ),
            "foraging_trip_successful_count": int(stats.get("foraging_trip_successful_count", 0)),
            "avg_foraging_trip_food_gained_after_first_harvest": round(
                float(stats.get("foraging_trip_post_first_harvest_units_total", 0))
                / float(max(1, int(stats.get("foraging_trip_post_first_harvest_units_samples", 0)))),
                4,
            ),
            "foraging_trip_single_harvest_action_count": int(stats.get("foraging_trip_single_harvest_action_count", 0)),
            "foraging_trip_single_harvest_action_ratio": round(
                float(stats.get("foraging_trip_single_harvest_action_count", 0))
                / float(max(1, int(stats.get("foraging_trip_successful_count", 0)))),
                4,
            ),
            "avg_foraging_trip_consecutive_harvest_actions_on_patch": round(
                float(stats.get("foraging_trip_max_consecutive_harvest_actions_total", 0))
                / float(max(1, int(stats.get("foraging_trip_max_consecutive_harvest_actions_samples", 0)))),
                4,
            ),
            "avg_foraging_trip_patch_dwell_after_first_harvest_ticks": round(
                float(stats.get("foraging_trip_patch_dwell_after_first_harvest_ticks_total", 0))
                / float(max(1, int(stats.get("foraging_trip_patch_dwell_after_first_harvest_ticks_samples", 0)))),
                4,
            ),
            "foraging_trip_ended_soon_after_first_harvest_count": int(
                stats.get("foraging_trip_ended_soon_after_first_harvest_count", 0)
            ),
            "foraging_trip_ended_soon_after_first_harvest_ratio": round(
                float(stats.get("foraging_trip_ended_soon_after_first_harvest_count", 0))
                / float(max(1, int(stats.get("foraging_trip_successful_count", 0)))),
                4,
            ),
            "foraging_trip_end_after_first_harvest_completed": int(
                stats.get("foraging_trip_end_after_first_harvest_completed", 0)
            ),
            "foraging_trip_end_after_first_harvest_task_switched": int(
                stats.get("foraging_trip_end_after_first_harvest_task_switched", 0)
            ),
            "foraging_trip_end_after_first_harvest_hunger_death": int(
                stats.get("foraging_trip_end_after_first_harvest_hunger_death", 0)
            ),
            "foraging_trip_end_after_first_harvest_other": int(
                stats.get("foraging_trip_end_after_first_harvest_other", 0)
            ),
            "post_first_harvest_task_switch_attempt_count": int(
                stats.get("post_first_harvest_task_switch_attempt_count", 0)
            ),
            "post_first_harvest_task_switch_committed_count": int(
                stats.get("post_first_harvest_task_switch_committed_count", 0)
            ),
            "post_first_harvest_task_switch_blocked_count": int(
                stats.get("post_first_harvest_task_switch_blocked_count", 0)
            ),
            "post_first_harvest_task_switch_attempt_source_survival_override": int(
                stats.get("post_first_harvest_task_switch_attempt_source_survival_override", 0)
            ),
            "post_first_harvest_task_switch_attempt_source_role_task_update": int(
                stats.get("post_first_harvest_task_switch_attempt_source_role_task_update", 0)
            ),
            "post_first_harvest_task_switch_attempt_source_inventory_logic": int(
                stats.get("post_first_harvest_task_switch_attempt_source_inventory_logic", 0)
            ),
            "post_first_harvest_task_switch_attempt_source_wander_fallback": int(
                stats.get("post_first_harvest_task_switch_attempt_source_wander_fallback", 0)
            ),
            "post_first_harvest_task_switch_attempt_source_target_invalidated": int(
                stats.get("post_first_harvest_task_switch_attempt_source_target_invalidated", 0)
            ),
            "post_first_harvest_task_switch_attempt_source_unknown": int(
                stats.get("post_first_harvest_task_switch_attempt_source_unknown", 0)
            ),
            "post_first_harvest_task_switch_committed_source_role_task_update": int(
                stats.get("post_first_harvest_task_switch_committed_source_role_task_update", 0)
            ),
            "post_first_harvest_task_switch_committed_source_inventory_logic": int(
                stats.get("post_first_harvest_task_switch_committed_source_inventory_logic", 0)
            ),
            "post_first_harvest_task_switch_committed_source_target_invalidated": int(
                stats.get("post_first_harvest_task_switch_committed_source_target_invalidated", 0)
            ),
            "post_first_harvest_task_switch_committed_source_unknown": int(
                stats.get("post_first_harvest_task_switch_committed_source_unknown", 0)
            ),
            "foraging_trip_end_reason_task_switched": int(stats.get("foraging_trip_end_reason_task_switched", 0)),
            "foraging_trip_end_reason_hunger_death": int(stats.get("foraging_trip_end_reason_hunger_death", 0)),
            "foraging_trip_end_reason_other": int(stats.get("foraging_trip_end_reason_other", 0)),
            "foraging_trip_success_rate_pressure_low": round(
                float(stats.get("foraging_trip_success_pressure_low_count", 0))
                / float(max(1, int(stats.get("foraging_trip_total_pressure_low_count", 0)))),
                4,
            ),
            "foraging_trip_success_rate_pressure_medium": round(
                float(stats.get("foraging_trip_success_pressure_medium_count", 0))
                / float(max(1, int(stats.get("foraging_trip_total_pressure_medium_count", 0)))),
                4,
            ),
            "foraging_trip_success_rate_pressure_high": round(
                float(stats.get("foraging_trip_success_pressure_high_count", 0))
                / float(max(1, int(stats.get("foraging_trip_total_pressure_high_count", 0)))),
                4,
            ),
            "avg_foraging_trip_efficiency_pressure_low": round(
                float(stats.get("foraging_trip_efficiency_pressure_low_sum", 0.0))
                / float(max(1, int(stats.get("foraging_trip_efficiency_pressure_low_samples", 0)))),
                4,
            ),
            "avg_foraging_trip_efficiency_pressure_medium": round(
                float(stats.get("foraging_trip_efficiency_pressure_medium_sum", 0.0))
                / float(max(1, int(stats.get("foraging_trip_efficiency_pressure_medium_samples", 0)))),
                4,
            ),
            "avg_foraging_trip_efficiency_pressure_high": round(
                float(stats.get("foraging_trip_efficiency_pressure_high_sum", 0.0))
                / float(max(1, int(stats.get("foraging_trip_efficiency_pressure_high_samples", 0)))),
                4,
            ),
            "avg_foraging_trip_efficiency_contention_low": round(
                float(stats.get("foraging_trip_efficiency_contention_low_sum", 0.0))
                / float(max(1, int(stats.get("foraging_trip_efficiency_contention_low_samples", 0)))),
                4,
            ),
            "avg_foraging_trip_efficiency_contention_medium": round(
                float(stats.get("foraging_trip_efficiency_contention_medium_sum", 0.0))
                / float(max(1, int(stats.get("foraging_trip_efficiency_contention_medium_samples", 0)))),
                4,
            ),
            "avg_foraging_trip_efficiency_contention_high": round(
                float(stats.get("foraging_trip_efficiency_contention_high_sum", 0.0))
                / float(max(1, int(stats.get("foraging_trip_efficiency_contention_high_samples", 0)))),
                4,
            ),
            "foraging_micro_retarget_events": int(stats.get("foraging_micro_retarget_events", 0)),
            "foraging_commitment_hold_overrides": int(stats.get("foraging_commitment_hold_overrides", 0)),
            "foraging_bonus_yield_units_total": int(stats.get("foraging_bonus_yield_units_total", 0)),
            "avg_foraging_yield_per_trip": round(
                float((self.production_metrics if isinstance(self.production_metrics, dict) else {}).get("total_food_gathered", 0))
                / float(max(1, int(stats.get("food_acquisition_events_total", 0)))),
                4,
            ),
            "food_move_time_ratio": round(
                float(stats.get("food_move_ticks_total", 0)) / float(max(1, agent_tick_samples)),
                4,
            ),
            "food_harvest_time_ratio": round(
                float(stats.get("food_harvest_ticks_total", 0)) / float(max(1, agent_tick_samples)),
                4,
            ),
            "avg_local_food_basin_accessible": round(
                float(stats.get("local_food_basin_accessible_total", 0)) / float(max(1, basin_access_samples)),
                4,
            ),
            "avg_local_food_pressure_ratio": round(
                float(stats.get("local_food_basin_pressure_ratio_total", 0.0)) / float(max(1, basin_ratio_samples)),
                4,
            ),
            "avg_local_food_basin_competing_agents": round(
                float(stats.get("local_food_basin_competing_agents_total", 0)) / float(max(1, basin_compete_samples)),
                4,
            ),
            "avg_distance_to_viable_food_from_proto": round(
                float(stats.get("local_food_basin_nearest_food_distance_total", 0)) / float(max(1, basin_distance_samples)),
                4,
            ),
            "local_food_basin_severe_pressure_ticks": int(stats.get("local_food_basin_severe_pressure_ticks", 0)),
            "local_food_basin_collapse_events": int(stats.get("local_food_basin_collapse_events", 0)),
            "proto_settlement_abandoned_due_to_food_pressure_count": int(
                stats.get("proto_settlement_abandoned_due_to_food_pressure_count", 0)
            ),
            "food_scarcity_adaptive_retarget_events": int(stats.get("food_scarcity_adaptive_retarget_events", 0)),
            "deaths_before_first_house_completed": int(stats.get("deaths_before_first_house_completed", 0)),
            "deaths_before_settlement_stability_threshold": int(stats.get("deaths_before_settlement_stability_threshold", 0)),
            "population_collapse_events": int(stats.get("population_collapse_events", 0)),
            "first_house_completion_tick": int(stats.get("first_house_completion_tick", -1)),
            "first_storage_completion_tick": int(stats.get("first_storage_completion_tick", -1)),
            "first_road_completion_tick": int(stats.get("first_road_completion_tick", -1)),
            "first_village_formalization_tick": int(stats.get("first_village_formalization_tick", -1)),
            "settlement_proto_count": int(stats.get("settlement_proto_count", 0)),
            "settlement_stable_village_count": int(stats.get("settlement_stable_village_count", 0)),
            "settlement_abandoned_count": int(stats.get("settlement_abandoned_count", 0)),
            "storage_built_before_house_count": int(stats.get("storage_built_before_house_count", 0)),
            "road_built_before_house_threshold_count": int(stats.get("road_built_before_house_threshold_count", 0)),
            "startup_survival_relief_ticks": int(stats.get("startup_survival_relief_ticks", 0)),
            "farm_sites_created": int(stats.get("farm_sites_created", 0)),
            "farm_work_events": int(stats.get("farm_work_events", 0)),
            "farm_abandoned": int(stats.get("farm_abandoned", 0)),
            "farm_yield_events": int(stats.get("farm_yield_events", 0)),
            "farm_yield_units_total": int(stats.get("farm_yield_units_total", 0)),
            "avg_farming_yield_per_cycle": round(
                float(stats.get("farm_yield_units_total", 0)) / float(max(1, int(stats.get("farm_yield_events", 0)))),
                4,
            ),
            "farm_productivity_score_avg": float(stats.get("farm_productivity_score_avg", 0.0)),
            "agents_farming_count": int(stats.get("agents_farming_count", 0)),
            "farm_candidate_detected_count": int(stats.get("farm_candidate_detected_count", 0)),
            "farm_candidate_bootstrap_trigger_count": int(stats.get("farm_candidate_bootstrap_trigger_count", 0)),
            "farm_candidate_rejected_count": int(stats.get("farm_candidate_rejected_count", 0)),
            "early_farm_loop_persistence_ticks": int(stats.get("early_farm_loop_persistence_ticks", 0)),
            "early_farm_loop_abandonment_count": int(stats.get("early_farm_loop_abandonment_count", 0)),
            "first_harvest_after_farm_creation_count": int(stats.get("first_harvest_after_farm_creation_count", 0)),
            "house_cluster_count": int(stats.get("house_cluster_count", 0)),
            "avg_houses_per_cluster": float(stats.get("avg_houses_per_cluster", 0.0)),
            "house_cluster_growth_events": int(stats.get("house_cluster_growth_events", 0)),
            "storage_built_after_cluster_count": int(stats.get("storage_built_after_cluster_count", 0)),
            "storage_built_without_cluster_count": int(stats.get("storage_built_without_cluster_count", 0)),
            "storage_emergence_attempts": int(stats.get("storage_emergence_attempts", 0)),
            "storage_emergence_successes": int(stats.get("storage_emergence_successes", 0)),
            "storage_deferred_due_to_low_house_cluster": int(stats.get("storage_deferred_due_to_low_house_cluster", 0)),
            "storage_deferred_due_to_low_throughput": int(stats.get("storage_deferred_due_to_low_throughput", 0)),
            "storage_deferred_due_to_low_buffer_pressure": int(stats.get("storage_deferred_due_to_low_buffer_pressure", 0)),
            "storage_deferred_due_to_low_surplus": int(stats.get("storage_deferred_due_to_low_surplus", 0)),
            "storage_built_in_mature_cluster_count": int(stats.get("storage_built_in_mature_cluster_count", 0)),
            "storage_supporting_active_house_cluster_count": int(stats.get("storage_supporting_active_house_cluster_count", 0)),
            "storage_relief_of_domestic_pressure_events": int(stats.get("storage_relief_of_domestic_pressure_events", 0)),
            "storage_relief_of_camp_pressure_events": int(stats.get("storage_relief_of_camp_pressure_events", 0)),
            "active_storage_construction_sites": int(stats.get("active_storage_construction_sites", 0)),
            "storage_builder_commitment_retained_ticks": int(stats.get("storage_builder_commitment_retained_ticks", 0)),
            "storage_material_delivery_events": int(stats.get("storage_material_delivery_events", 0)),
            "storage_construction_progress_ticks": int(stats.get("storage_construction_progress_ticks", 0)),
            "storage_construction_interrupted_survival": int(stats.get("storage_construction_interrupted_survival", 0)),
            "storage_construction_interrupted_invalid": int(stats.get("storage_construction_interrupted_invalid", 0)),
            "storage_construction_abandoned_count": int(stats.get("storage_construction_abandoned_count", 0)),
            "storage_construction_completed_count": int(stats.get("storage_construction_completed_count", 0)),
            "construction_sites_created": int(stats.get("construction_sites_created", 0)),
            "construction_sites_created_house": int(stats.get("construction_sites_created_house", 0)),
            "construction_sites_created_storage": int(stats.get("construction_sites_created_storage", 0)),
            "active_construction_sites": int(stats.get("active_construction_sites", 0)),
            "partially_built_sites_count": int(stats.get("partially_built_sites_count", 0)),
            "construction_material_delivery_events": int(stats.get("construction_material_delivery_events", 0)),
            "construction_material_delivery_to_active_site": int(stats.get("construction_material_delivery_to_active_site", 0)),
            "construction_material_delivery_drift_events": int(stats.get("construction_material_delivery_drift_events", 0)),
            "construction_material_delivery_wood_units": int(stats.get("construction_material_delivery_wood_units", 0)),
            "construction_material_delivery_stone_units": int(stats.get("construction_material_delivery_stone_units", 0)),
            "construction_material_delivery_food_units": int(stats.get("construction_material_delivery_food_units", 0)),
            "storage_deposit_food_units": int(stats.get("storage_deposit_food_units", 0)),
            "storage_deposit_wood_units": int(stats.get("storage_deposit_wood_units", 0)),
            "storage_deposit_stone_units": int(stats.get("storage_deposit_stone_units", 0)),
            "construction_delivery_attempts": int(stats.get("construction_delivery_attempts", 0)),
            "construction_delivery_successes": int(stats.get("construction_delivery_successes", 0)),
            "construction_delivery_failures": int(stats.get("construction_delivery_failures", 0)),
            "construction_delivery_to_site_events": int(stats.get("construction_delivery_to_site_events", 0)),
            "construction_delivery_to_wrong_target_or_drift": int(stats.get("construction_delivery_to_wrong_target_or_drift", 0)),
            "construction_delivery_source_binding_selected_count": int(
                stats.get("construction_delivery_source_binding_selected_count", 0)
            ),
            "construction_delivery_source_binding_persisted_count": int(
                stats.get("construction_delivery_source_binding_persisted_count", 0)
            ),
            "construction_delivery_source_binding_refreshed_count": int(
                stats.get("construction_delivery_source_binding_refreshed_count", 0)
            ),
            "construction_delivery_source_binding_missing_count": int(
                stats.get("construction_delivery_source_binding_missing_count", 0)
            ),
            "construction_delivery_source_binding_unavailable_count": int(
                stats.get("construction_delivery_source_binding_unavailable_count", 0)
            ),
            "construction_delivery_source_binding_lost_missing_source_count": int(
                stats.get("construction_delivery_source_binding_lost_missing_source_count", 0)
            ),
            "construction_delivery_source_binding_lost_ineligible_source_count": int(
                stats.get("construction_delivery_source_binding_lost_ineligible_source_count", 0)
            ),
            "construction_delivery_source_binding_lost_not_refreshed_count": int(
                stats.get("construction_delivery_source_binding_lost_not_refreshed_count", 0)
            ),
            "construction_delivery_prepickup_checks_count": int(
                stats.get("construction_delivery_prepickup_checks_count", 0)
            ),
            "construction_delivery_prepickup_site_exists_count": int(
                stats.get("construction_delivery_prepickup_site_exists_count", 0)
            ),
            "construction_delivery_prepickup_site_missing_count": int(
                stats.get("construction_delivery_prepickup_site_missing_count", 0)
            ),
            "construction_delivery_prepickup_site_under_construction_count": int(
                stats.get("construction_delivery_prepickup_site_under_construction_count", 0)
            ),
            "construction_delivery_prepickup_site_not_under_construction_count": int(
                stats.get("construction_delivery_prepickup_site_not_under_construction_count", 0)
            ),
            "construction_delivery_prepickup_site_reachable_count": int(
                stats.get("construction_delivery_prepickup_site_reachable_count", 0)
            ),
            "construction_delivery_prepickup_site_unreachable_count": int(
                stats.get("construction_delivery_prepickup_site_unreachable_count", 0)
            ),
            "construction_delivery_prepickup_site_demand_matches_material_count": int(
                stats.get("construction_delivery_prepickup_site_demand_matches_material_count", 0)
            ),
            "construction_delivery_prepickup_site_demand_mismatch_material_count": int(
                stats.get("construction_delivery_prepickup_site_demand_mismatch_material_count", 0)
            ),
            "construction_delivery_source_persistence_window_invoked_count": int(
                stats.get("construction_delivery_source_persistence_window_invoked_count", 0)
            ),
            "construction_delivery_source_persistence_window_completed_count": int(
                stats.get("construction_delivery_source_persistence_window_completed_count", 0)
            ),
            "construction_delivery_source_persistence_window_broken_by_source_invalidity_count": int(
                stats.get("construction_delivery_source_persistence_window_broken_by_source_invalidity_count", 0)
            ),
            "construction_delivery_source_persistence_window_broken_by_demand_mismatch_count": int(
                stats.get("construction_delivery_source_persistence_window_broken_by_demand_mismatch_count", 0)
            ),
            "construction_delivery_reservation_alignment_pass_count": int(
                stats.get("construction_delivery_reservation_alignment_pass_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_count": int(
                stats.get("construction_delivery_reservation_alignment_fail_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_material_wood_count": int(
                stats.get("construction_delivery_reservation_alignment_fail_material_wood_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_material_stone_count": int(
                stats.get("construction_delivery_reservation_alignment_fail_material_stone_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_material_food_count": int(
                stats.get("construction_delivery_reservation_alignment_fail_material_food_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_reason_site_missing_count": int(
                stats.get("construction_delivery_reservation_alignment_fail_reason_site_missing_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_reason_site_not_under_construction_count": int(
                stats.get("construction_delivery_reservation_alignment_fail_reason_site_not_under_construction_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_reason_reservation_invalid_count": int(
                stats.get("construction_delivery_reservation_alignment_fail_reason_reservation_invalid_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_reason_demand_mismatch_count": int(
                stats.get("construction_delivery_reservation_alignment_fail_reason_demand_mismatch_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_reason_source_ineligible_count": int(
                stats.get("construction_delivery_reservation_alignment_fail_reason_source_ineligible_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_reason_source_empty_count": int(
                stats.get("construction_delivery_reservation_alignment_fail_reason_source_empty_count", 0)
            ),
            "delivery_commitment_hold_invoked_count": int(stats.get("delivery_commitment_hold_invoked_count", 0)),
            "delivery_commitment_hold_completed_count": int(stats.get("delivery_commitment_hold_completed_count", 0)),
            "delivery_commitment_hold_broken_by_survival_count": int(
                stats.get("delivery_commitment_hold_broken_by_survival_count", 0)
            ),
            "delivery_commitment_hold_broken_by_invalid_site_count": int(
                stats.get("delivery_commitment_hold_broken_by_invalid_site_count", 0)
            ),
            "delivery_commitment_hold_broken_by_invalid_source_count": int(
                stats.get("delivery_commitment_hold_broken_by_invalid_source_count", 0)
            ),
            "construction_delivery_invalid_site_missing_site_count": int(
                stats.get("construction_delivery_invalid_site_missing_site_count", 0)
            ),
            "construction_delivery_invalid_site_not_under_construction_count": int(
                stats.get("construction_delivery_invalid_site_not_under_construction_count", 0)
            ),
            "construction_delivery_invalid_site_village_mismatch_count": int(
                stats.get("construction_delivery_invalid_site_village_mismatch_count", 0)
            ),
            "construction_delivery_invalid_site_construction_completed_count": int(
                stats.get("construction_delivery_invalid_site_construction_completed_count", 0)
            ),
            "construction_delivery_invalid_site_no_path_to_site_count": int(
                stats.get("construction_delivery_invalid_site_no_path_to_site_count", 0)
            ),
            "construction_delivery_invalid_site_demand_mismatch_count": int(
                stats.get("construction_delivery_invalid_site_demand_mismatch_count", 0)
            ),
            "construction_delivery_invalid_site_other_count": int(
                stats.get("construction_delivery_invalid_site_other_count", 0)
            ),
            "construction_delivery_invalid_source_no_source_available_count": int(
                stats.get("construction_delivery_invalid_source_no_source_available_count", 0)
            ),
            "construction_delivery_invalid_source_source_depleted_count": int(
                stats.get("construction_delivery_invalid_source_source_depleted_count", 0)
            ),
            "construction_delivery_invalid_source_reservation_invalidated_count": int(
                stats.get("construction_delivery_invalid_source_reservation_invalidated_count", 0)
            ),
            "construction_delivery_invalid_source_source_reassigned_count": int(
                stats.get("construction_delivery_invalid_source_source_reassigned_count", 0)
            ),
            "construction_delivery_invalid_source_linkage_mismatch_count": int(
                stats.get("construction_delivery_invalid_source_linkage_mismatch_count", 0)
            ),
            "construction_delivery_invalid_source_no_path_to_source_count": int(
                stats.get("construction_delivery_invalid_source_no_path_to_source_count", 0)
            ),
            "construction_delivery_invalid_source_other_count": int(
                stats.get("construction_delivery_invalid_source_other_count", 0)
            ),
            "construction_delivery_invalid_site_before_pickup_count": int(
                stats.get("construction_delivery_invalid_site_before_pickup_count", 0)
            ),
            "construction_delivery_invalid_site_after_pickup_count": int(
                stats.get("construction_delivery_invalid_site_after_pickup_count", 0)
            ),
            "construction_delivery_invalid_source_before_pickup_count": int(
                stats.get("construction_delivery_invalid_source_before_pickup_count", 0)
            ),
            "construction_delivery_invalid_source_after_pickup_count": int(
                stats.get("construction_delivery_invalid_source_after_pickup_count", 0)
            ),
            "construction_delivery_ticks_reservation_to_invalid_site_avg": round(
                float(stats.get("construction_delivery_ticks_reservation_to_invalid_site_total", 0))
                / float(max(1, int(stats.get("construction_delivery_ticks_reservation_to_invalid_site_samples", 0)))),
                4,
            ),
            "construction_delivery_ticks_reservation_to_invalid_source_avg": round(
                float(stats.get("construction_delivery_ticks_reservation_to_invalid_source_total", 0))
                / float(max(1, int(stats.get("construction_delivery_ticks_reservation_to_invalid_source_samples", 0)))),
                4,
            ),
            "construction_delivery_ticks_pickup_to_invalid_site_avg": round(
                float(stats.get("construction_delivery_ticks_pickup_to_invalid_site_total", 0))
                / float(max(1, int(stats.get("construction_delivery_ticks_pickup_to_invalid_site_samples", 0)))),
                4,
            ),
            "construction_delivery_ticks_pickup_to_invalid_source_avg": round(
                float(stats.get("construction_delivery_ticks_pickup_to_invalid_source_total", 0))
                / float(max(1, int(stats.get("construction_delivery_ticks_pickup_to_invalid_source_samples", 0)))),
                4,
            ),
            "construction_delivery_invalid_site_material_wood_count": int(
                stats.get("construction_delivery_invalid_site_material_wood_count", 0)
            ),
            "construction_delivery_invalid_site_material_stone_count": int(
                stats.get("construction_delivery_invalid_site_material_stone_count", 0)
            ),
            "construction_delivery_invalid_site_material_food_count": int(
                stats.get("construction_delivery_invalid_site_material_food_count", 0)
            ),
            "construction_delivery_invalid_source_material_wood_count": int(
                stats.get("construction_delivery_invalid_source_material_wood_count", 0)
            ),
            "construction_delivery_invalid_source_material_stone_count": int(
                stats.get("construction_delivery_invalid_source_material_stone_count", 0)
            ),
            "construction_delivery_invalid_source_material_food_count": int(
                stats.get("construction_delivery_invalid_source_material_food_count", 0)
            ),
            "construction_delivery_invalid_site_committed_site_mismatch_count": int(
                stats.get("construction_delivery_invalid_site_committed_site_mismatch_count", 0)
            ),
            "construction_delivery_invalid_source_committed_source_missing_count": int(
                stats.get("construction_delivery_invalid_source_committed_source_missing_count", 0)
            ),
            "construction_delivery_avg_distance_to_site": round(
                float(stats.get("construction_delivery_distance_to_site_sum", 0))
                / float(max(1, int(stats.get("construction_delivery_distance_to_site_samples", 0)))),
                4,
            ),
            "construction_delivery_avg_distance_to_source": round(
                float(stats.get("construction_delivery_distance_to_source_sum", 0))
                / float(max(1, int(stats.get("construction_delivery_distance_to_source_samples", 0)))),
                4,
            ),
            "storage_delivery_failures": int(stats.get("storage_delivery_failures", 0)),
            "house_delivery_failures": int(stats.get("house_delivery_failures", 0)),
            "storage_delivery_successes": int(stats.get("storage_delivery_successes", 0)),
            "house_delivery_successes": int(stats.get("house_delivery_successes", 0)),
            "construction_progress_ticks": int(stats.get("construction_progress_ticks", 0)),
            "construction_progress_stalled_ticks": int(stats.get("construction_progress_stalled_ticks", 0)),
            "construction_completion_events": int(stats.get("construction_completion_events", 0)),
            "construction_abandonment_events": int(stats.get("construction_abandonment_events", 0)),
            "construction_site_waiting_for_material_ticks": int(stats.get("construction_site_waiting_for_material_ticks", 0)),
            "construction_site_waiting_for_builder_ticks": int(stats.get("construction_site_waiting_for_builder_ticks", 0)),
            "construction_site_waiting_total_ticks": int(stats.get("construction_site_waiting_total_ticks", 0)),
            "construction_site_progress_active_ticks": int(stats.get("construction_site_progress_active_ticks", 0)),
            "construction_site_starved_cycles": int(stats.get("construction_site_starved_cycles", 0)),
            "storage_waiting_for_material_ticks": int(stats.get("storage_waiting_for_material_ticks", 0)),
            "house_waiting_for_material_ticks": int(stats.get("house_waiting_for_material_ticks", 0)),
            "storage_waiting_for_builder_ticks": int(stats.get("storage_waiting_for_builder_ticks", 0)),
            "house_waiting_for_builder_ticks": int(stats.get("house_waiting_for_builder_ticks", 0)),
            "construction_site_lifetime_ticks_avg": round(
                float(stats.get("construction_site_lifetime_ticks_total", 0)) / float(max(1, site_lifetime_samples)),
                4,
            ),
            "construction_site_progress_before_abandon_avg": round(
                float(stats.get("construction_site_progress_before_abandon_total", 0)) / float(max(1, site_abandon_samples)),
                4,
            ),
            "construction_site_material_units_delivered_avg": round(
                float(stats.get("construction_site_material_units_delivered_total", 0)) / float(max(1, site_lifetime_samples)),
                4,
            ),
            "construction_site_material_units_missing_avg": round(
                float(stats.get("construction_site_material_units_missing_total", 0)) / float(max(1, site_missing_samples)),
                4,
            ),
            "construction_site_material_units_required_total": int(
                stats.get("construction_site_material_units_required_total", 0)
            ),
            "construction_site_material_units_delivered_total": int(
                stats.get("construction_site_material_units_delivered_total_live", 0)
            ),
            "construction_site_material_units_remaining": int(
                stats.get("construction_site_material_units_remaining", 0)
            ),
            "construction_site_required_work_ticks_total": int(
                stats.get("construction_site_required_work_ticks_total", 0)
            ),
            "construction_site_completed_work_ticks_total": int(
                stats.get("construction_site_completed_work_ticks_total_live", 0)
            ),
            "construction_site_remaining_work_ticks": int(
                stats.get("construction_site_remaining_work_ticks", 0)
            ),
            "construction_build_state_planned_count": int(
                stats.get("construction_build_state_planned_count", 0)
            ),
            "construction_build_state_supplying_count": int(
                stats.get("construction_build_state_supplying_count", 0)
            ),
            "construction_build_state_buildable_count": int(
                stats.get("construction_build_state_buildable_count", 0)
            ),
            "construction_build_state_in_progress_count": int(
                stats.get("construction_build_state_in_progress_count", 0)
            ),
            "construction_build_state_paused_count": int(
                stats.get("construction_build_state_paused_count", 0)
            ),
            "construction_build_state_completed_count": int(
                stats.get("construction_build_state_completed_count", 0)
            ),
            "construction_near_complete_sites_count": int(
                stats.get("construction_near_complete_sites_count", 0)
            ),
            "builder_assigned_site_count": int(stats.get("builder_assigned_site_count", 0)),
            "builder_site_arrival_count": int(stats.get("builder_site_arrival_count", 0)),
            "builder_left_site_count": int(stats.get("builder_left_site_count", 0)),
            "builder_left_site_before_completion_count": int(
                stats.get("builder_left_site_before_completion_count", 0)
            ),
            "builder_waiting_on_site_ticks_total": int(stats.get("builder_waiting_on_site_ticks_total", 0)),
            "builder_on_site_ticks_total": int(stats.get("builder_on_site_ticks_total", 0)),
            "builder_work_tick_applied_count": int(stats.get("builder_work_tick_applied_count", 0)),
            "builder_survival_override_during_construction_count": int(
                stats.get("builder_survival_override_during_construction_count", 0)
            ),
            "builder_redirected_to_storage_during_construction_count": int(
                stats.get("builder_redirected_to_storage_during_construction_count", 0)
            ),
            "builder_commitment_created_count": int(stats.get("builder_commitment_created_count", 0)),
            "builder_commitment_pause_count": int(stats.get("builder_commitment_pause_count", 0)),
            "builder_commitment_resume_count": int(stats.get("builder_commitment_resume_count", 0)),
            "builder_commitment_completed_count": int(stats.get("builder_commitment_completed_count", 0)),
            "builder_commitment_abandoned_count": int(stats.get("builder_commitment_abandoned_count", 0)),
            "builder_returned_to_same_site_count": int(stats.get("builder_returned_to_same_site_count", 0)),
            "builder_commitment_duration_avg": round(
                float(stats.get("builder_commitment_duration_total", 0))
                / float(max(1, commitment_duration_samples)),
                4,
            ),
            "builder_commitment_resume_delay_avg": round(
                float(stats.get("builder_commitment_resume_delay_total", 0))
                / float(max(1, commitment_resume_delay_samples)),
                4,
            ),
            "construction_site_buildable_ticks_total": int(stats.get("construction_site_buildable_ticks_total", 0)),
            "construction_site_idle_buildable_ticks_total": int(
                stats.get("construction_site_idle_buildable_ticks_total", 0)
            ),
            "construction_site_buildable_but_idle_ticks_total": int(
                stats.get("construction_site_buildable_but_idle_ticks_total", 0)
            ),
            "construction_site_waiting_materials_ticks_total": int(
                stats.get("construction_site_waiting_materials_ticks_total", 0)
            ),
            "construction_site_in_progress_ticks_total": int(
                stats.get("construction_site_in_progress_ticks_total", 0)
            ),
            "construction_site_distinct_builders_avg": round(
                float(stats.get("construction_site_distinct_builders_total", 0))
                / float(max(1, distinct_builders_samples)),
                4,
            ),
            "construction_site_work_ticks_per_builder_avg": round(
                float(stats.get("construction_site_work_ticks_per_builder_total", 0.0))
                / float(max(1, work_ticks_per_builder_samples)),
                4,
            ),
            "construction_site_delivery_to_work_gap_avg": round(
                float(stats.get("construction_site_delivery_to_work_gap_total", 0))
                / float(max(1, delivery_to_work_gap_samples)),
                4,
            ),
            "construction_site_active_age_ticks_avg": round(
                float(stats.get("construction_site_active_age_ticks_total", 0))
                / float(max(1, active_age_ticks_samples)),
                4,
            ),
            "construction_site_nearest_wood_distance_avg": round(
                float(stats.get("construction_site_nearest_wood_distance_total", 0))
                / float(max(1, site_nearest_wood_samples)),
                4,
            ),
            "construction_site_nearest_stone_distance_avg": round(
                float(stats.get("construction_site_nearest_stone_distance_total", 0))
                / float(max(1, site_nearest_stone_samples)),
                4,
            ),
            "construction_site_viable_wood_sources_within_radius_avg": round(
                float(stats.get("construction_site_viable_wood_sources_within_radius_total", 0))
                / float(max(1, site_viable_wood_samples)),
                4,
            ),
            "construction_site_viable_stone_sources_within_radius_avg": round(
                float(stats.get("construction_site_viable_stone_sources_within_radius_total", 0))
                / float(max(1, site_viable_stone_samples)),
                4,
            ),
            "construction_site_zero_wood_sources_within_radius_ticks": int(
                stats.get("construction_site_zero_wood_sources_within_radius_ticks", 0)
            ),
            "construction_site_zero_stone_sources_within_radius_ticks": int(
                stats.get("construction_site_zero_stone_sources_within_radius_ticks", 0)
            ),
            "construction_site_local_wood_source_contention_avg": round(
                float(stats.get("construction_site_local_wood_source_contention_total", 0.0))
                / float(max(1, site_local_wood_contention_samples)),
                4,
            ),
            "construction_site_local_stone_source_contention_avg": round(
                float(stats.get("construction_site_local_stone_source_contention_total", 0.0))
                / float(max(1, site_local_stone_contention_samples)),
                4,
            ),
            "construction_site_ticks_since_last_delivery_avg": round(
                float(stats.get("construction_site_ticks_since_last_delivery_total", 0))
                / float(max(1, site_last_delivery_samples)),
                4,
            ),
            "construction_site_waiting_with_positive_wood_stock_ticks": int(
                stats.get("construction_site_waiting_with_positive_wood_stock_ticks", 0)
            ),
            "construction_site_waiting_with_positive_stone_stock_ticks": int(
                stats.get("construction_site_waiting_with_positive_stone_stock_ticks", 0)
            ),
            "construction_site_first_demand_to_first_delivery_avg": round(
                float(stats.get("construction_site_first_demand_to_first_delivery_total", 0))
                / float(max(1, site_first_demand_to_first_delivery_samples)),
                4,
            ),
            "construction_site_material_inflow_rate_avg": round(
                float(stats.get("construction_site_material_inflow_rate_total", 0.0))
                / float(max(1, site_material_inflow_samples)),
                4,
            ),
            "construction_site_delivered_wood_units_total_live": int(
                stats.get("construction_site_delivered_wood_units_total_live", 0)
            ),
            "construction_site_delivered_stone_units_total_live": int(
                stats.get("construction_site_delivered_stone_units_total_live", 0)
            ),
            "construction_site_delivered_food_units_total_live": int(
                stats.get("construction_site_delivered_food_units_total_live", 0)
            ),
            "active_builders_count": int(stats.get("active_builders_count", 0)),
            "active_haulers_count": int(stats.get("active_haulers_count", 0)),
            "active_builders_nearest_wood_distance_avg": round(
                float(stats.get("active_builders_nearest_wood_distance_total", 0))
                / float(max(1, active_builder_wood_samples)),
                4,
            ),
            "active_builders_nearest_stone_distance_avg": round(
                float(stats.get("active_builders_nearest_stone_distance_total", 0))
                / float(max(1, active_builder_stone_samples)),
                4,
            ),
            "active_haulers_nearest_wood_distance_avg": round(
                float(stats.get("active_haulers_nearest_wood_distance_total", 0))
                / float(max(1, active_hauler_wood_samples)),
                4,
            ),
            "active_haulers_nearest_stone_distance_avg": round(
                float(stats.get("active_haulers_nearest_stone_distance_total", 0))
                / float(max(1, active_hauler_stone_samples)),
                4,
            ),
            "construction_site_first_builder_arrival_delay_avg": round(
                float(stats.get("construction_site_first_builder_arrival_delay_total", 0))
                / float(max(1, site_first_arrival_samples)),
                4,
            ),
            "construction_site_material_ready_to_first_work_delay_avg": round(
                float(stats.get("construction_site_material_ready_to_first_work_delay_total", 0))
                / float(max(1, site_material_ready_to_work_samples)),
                4,
            ),
            "construction_site_completion_time_avg": round(
                float(stats.get("construction_site_completion_time_total", 0)) / float(max(1, site_completion_samples)),
                4,
            ),
            "construction_time_first_delivery_to_completion_avg": round(
                float(stats.get("construction_time_first_delivery_to_completion_total", 0))
                / float(max(1, int(stats.get("construction_time_first_delivery_to_completion_samples", 0)))),
                4,
            ),
            "construction_time_first_progress_to_completion_avg": round(
                float(stats.get("construction_time_first_progress_to_completion_total", 0))
                / float(max(1, int(stats.get("construction_time_first_progress_to_completion_samples", 0)))),
                4,
            ),
            "construction_time_first_work_to_completion_avg": round(
                float(stats.get("construction_time_first_progress_to_completion_total", 0))
                / float(max(1, int(stats.get("construction_time_first_progress_to_completion_samples", 0)))),
                4,
            ),
            "construction_completed_after_first_delivery_count": int(
                stats.get("construction_completed_after_first_delivery_count", 0)
            ),
            "construction_completed_after_started_progress_count": int(
                stats.get("construction_completed_after_started_progress_count", 0)
            ),
            "construction_completed_after_first_work_count": int(
                stats.get("construction_completed_after_started_progress_count", 0)
            ),
            "house_completion_time_avg": round(
                float(stats.get("house_completion_time_total", 0)) / float(max(1, house_completion_samples)),
                4,
            ),
            "storage_completion_time_avg": round(
                float(stats.get("storage_completion_time_total", 0)) / float(max(1, storage_completion_samples)),
                4,
            ),
            "houses_completed_count": int(stats.get("houses_completed_count", 0)),
            "storage_attempts": int(storage_attempts),
            "storage_completed_count": int(storage_completions),
            "storage_completion_rate": round(float(storage_completion_rate), 4),
            "food_gathered_total_observed": int(
                (self.production_metrics if isinstance(self.production_metrics, dict) else {}).get("total_food_gathered", 0)
            ),
            "food_consumed_total_observed": int(
                int((self.camp_food_stats if isinstance(self.camp_food_stats, dict) else {}).get("food_consumed_from_inventory", 0))
                + int((self.camp_food_stats if isinstance(self.camp_food_stats, dict) else {}).get("food_consumed_from_camp", 0))
                + int((self.camp_food_stats if isinstance(self.camp_food_stats, dict) else {}).get("food_consumed_from_domestic", 0))
                + int((self.camp_food_stats if isinstance(self.camp_food_stats, dict) else {}).get("food_consumed_from_storage", 0))
                + int((self.camp_food_stats if isinstance(self.camp_food_stats, dict) else {}).get("food_consumed_from_wild_direct", 0))
            ),
            "local_food_surplus_rate": round(float(food_rate / float(max(1, rate_samples))), 4),
            "local_resource_surplus_rate": round(float(resource_rate / float(max(1, rate_samples))), 4),
            "buffer_saturation_events": int(stats.get("buffer_saturation_events", 0)),
            "surplus_triggered_storage_attempts": int(stats.get("surplus_triggered_storage_attempts", 0)),
            "surplus_storage_construction_completed": int(stats.get("surplus_storage_construction_completed", 0)),
            "surplus_storage_abandoned": int(stats.get("surplus_storage_abandoned", 0)),
            "secondary_nucleus_with_house_count": int(stats.get("secondary_nucleus_with_house_count", 0)),
            "secondary_nucleus_house_growth_events": int(stats.get("secondary_nucleus_house_growth_events", 0)),
            "repeated_successful_loop_count": int(stats.get("repeated_successful_loop_count", 0)),
            "routine_persistence_ticks": int(stats.get("routine_persistence_ticks", 0)),
            "routine_abandonment_after_failure": int(stats.get("routine_abandonment_after_failure", 0)),
            "routine_abandonment_after_success": int(stats.get("routine_abandonment_after_success", 0)),
            "cultural_practices_created": int(stats.get("cultural_practices_created", 0)),
            "cultural_practices_reinforced": int(stats.get("cultural_practices_reinforced", 0)),
            "cultural_practices_decayed": int(stats.get("cultural_practices_decayed", 0)),
            "active_cultural_practices": int(stats.get("active_cultural_practices", 0)),
            "agents_using_cultural_memory_bias": int(stats.get("agents_using_cultural_memory_bias", 0)),
            "productive_food_patch_practices": int(stats.get("productive_food_patch_practices", 0)),
            "proto_farm_practices": int(stats.get("proto_farm_practices", 0)),
            "construction_cluster_practices": int(stats.get("construction_cluster_practices", 0)),
        }

    def compute_material_feasibility_snapshot(self) -> Dict[str, Any]:
        production = self.production_metrics if isinstance(self.production_metrics, dict) else _default_world_production_metrics()
        respawn = self.resource_respawn_stats if isinstance(self.resource_respawn_stats, dict) else _default_resource_respawn_stats()
        progression = self.compute_settlement_progression_snapshot()
        stats = self.settlement_progression_stats if isinstance(self.settlement_progression_stats, dict) else {}
        camp_food = self.camp_food_stats if isinstance(self.camp_food_stats, dict) else {}
        initial_stock = self.initial_resource_stock if isinstance(getattr(self, "initial_resource_stock", {}), dict) else {}

        def _resource_stock(resource: str) -> Dict[str, int]:
            on_map = int(len(getattr(self, resource, set())))
            in_agents = int(
                sum(
                    int(getattr(a, "inventory", {}).get(resource, 0))
                    for a in (self.agents or [])
                    if getattr(a, "alive", False) and isinstance(getattr(a, "inventory", {}), dict)
                )
            )
            in_storage = 0
            in_construction = 0
            in_camps = 0
            for b in (self.buildings or {}).values():
                if not isinstance(b, dict):
                    continue
                btype = str(b.get("type", ""))
                st = b.get("storage", {}) if isinstance(b.get("storage"), dict) else {}
                if btype == "storage":
                    in_storage += int(st.get(resource, 0))
                if btype in {"house", "storage"} and str(b.get("operational_state", "")) == "under_construction":
                    buf = b.get("construction_buffer", {}) if isinstance(b.get("construction_buffer", {}), dict) else {}
                    in_construction += int(buf.get(resource, 0))
            if resource == "food":
                for camp in (self.camps or {}).values():
                    if not isinstance(camp, dict):
                        continue
                    in_camps += int(camp.get("food_cache", 0))
            available_world_total = int(on_map + in_agents + in_storage + in_construction + in_camps)
            return {
                "on_map": int(on_map),
                "in_agents": int(in_agents),
                "in_storage": int(in_storage),
                "in_construction_buffers": int(in_construction),
                "in_camps": int(in_camps),
                "available_world_total": int(available_world_total),
            }

        wood_stock = _resource_stock("wood")
        stone_stock = _resource_stock("stone")
        food_stock = _resource_stock("food")

        active_sites = 0
        partial_sites = 0
        stalled_sites = 0
        outstanding_wood_total = 0
        outstanding_stone_total = 0
        for b in (self.buildings or {}).values():
            if not isinstance(b, dict):
                continue
            if str(b.get("type", "")) not in {"house", "storage"}:
                continue
            if str(b.get("operational_state", "")) != "under_construction":
                continue
            active_sites += 1
            progress = int(b.get("construction_progress", 0))
            required = max(1, int(b.get("construction_required_work", 1)))
            if progress > 0 and progress < required:
                partial_sites += 1
            if int(b.get("builder_waiting_tick", -10_000)) >= int(self.tick) - 24:
                stalled_sites += 1
            if hasattr(building_system, "get_outstanding_construction_needs"):
                try:
                    needs = building_system.get_outstanding_construction_needs(b)
                except Exception:
                    needs = {}
                if isinstance(needs, dict):
                    outstanding_wood_total += int(needs.get("wood", 0))
                    outstanding_stone_total += int(needs.get("stone", 0))

        workforce = self.workforce_realization_stats if isinstance(self.workforce_realization_stats, dict) else {}
        by_role_blocks = workforce.get("block_reasons_by_role", {}) if isinstance(workforce.get("block_reasons_by_role", {}), dict) else {}
        shortage_blocks = 0
        for role in ("builder", "hauler"):
            role_blocks = by_role_blocks.get(role, {}) if isinstance(by_role_blocks.get(role, {}), dict) else {}
            shortage_blocks += int(role_blocks.get("no_materials_available", 0))

        delivery_diag = self.delivery_diagnostic_stats if isinstance(self.delivery_diagnostic_stats, dict) else _default_delivery_diagnostic_stats()
        delivery_global = delivery_diag.get("global", {}) if isinstance(delivery_diag.get("global", {}), dict) else {}
        delivery_fail_reasons = delivery_global.get("delivery_failure_reasons", {}) if isinstance(delivery_global.get("delivery_failure_reasons", {}), dict) else {}
        construction_delivery_failures = int(delivery_global.get("delivery_abandoned_count", 0))
        material_delivery_failures = int(delivery_fail_reasons.get("no_resource_available", 0)) + int(
            delivery_fail_reasons.get("no_source_storage", 0)
        )
        construction_delivery_failure_no_source_available = int(delivery_fail_reasons.get("no_source_storage", 0))
        construction_delivery_failure_source_depleted = int(delivery_fail_reasons.get("source_depleted", 0)) + int(
            delivery_fail_reasons.get("no_resource_available", 0)
        )
        construction_delivery_failure_reservation_invalidated = int(delivery_fail_reasons.get("reservation_lost", 0))
        construction_delivery_failure_no_path_to_source = int(delivery_fail_reasons.get("no_path_to_source", 0)) + int(
            delivery_fail_reasons.get("path_failed", 0)
        )
        construction_delivery_failure_no_path_to_site = int(delivery_fail_reasons.get("no_path_to_site", 0)) + int(
            delivery_fail_reasons.get("site_not_in_range", 0)
        )
        construction_delivery_failure_arrival_failed = int(delivery_fail_reasons.get("arrival_failed", 0))
        construction_delivery_failure_retargeted_before_delivery = int(
            delivery_fail_reasons.get("retargeted_before_delivery", 0)
        ) + int(delivery_fail_reasons.get("no_delivery_target", 0))
        construction_delivery_failure_interrupted_by_other_priority = int(
            delivery_fail_reasons.get("interrupted_by_other_priority", 0)
        ) + int(delivery_fail_reasons.get("task_replaced", 0))
        construction_delivery_failure_unknown = int(delivery_fail_reasons.get("unknown_failure", 0))

        houses_completed = int(progression.get("houses_completed_count", 0))
        storage_completed = int(progression.get("storage_completed_count", 0))
        wood_consumed_for_construction_total = int(houses_completed * int(HOUSE_WOOD_COST)) + int(
            storage_completed * int(getattr(building_system, "STORAGE_WOOD_COST", 0))
        )
        stone_consumed_for_construction_total = int(houses_completed * int(HOUSE_STONE_COST)) + int(
            storage_completed * int(getattr(building_system, "STORAGE_STONE_COST", 0))
        )
        wood_available_world_total = int(wood_stock.get("available_world_total", 0))
        stone_available_world_total = int(stone_stock.get("available_world_total", 0))
        food_available_world_total = int(food_stock.get("available_world_total", 0))
        avg_local_wood_pressure = float(outstanding_wood_total) / float(max(1, wood_available_world_total))
        avg_local_stone_pressure = float(outstanding_stone_total) / float(max(1, stone_available_world_total))
        wood_shortage_events = int(shortage_blocks + material_delivery_failures)
        construction_delivery_wood_units = int(stats.get("construction_material_delivery_wood_units", 0))
        construction_delivery_stone_units = int(stats.get("construction_material_delivery_stone_units", 0))
        construction_delivery_food_units = int(stats.get("construction_material_delivery_food_units", 0))
        storage_deposit_food_units = int(stats.get("storage_deposit_food_units", 0))
        storage_deposit_wood_units = int(stats.get("storage_deposit_wood_units", 0))
        storage_deposit_stone_units = int(stats.get("storage_deposit_stone_units", 0))
        food_consumed_total_observed = int(
            int(camp_food.get("food_consumed_from_inventory", 0))
            + int(camp_food.get("food_consumed_from_camp", 0))
            + int(camp_food.get("food_consumed_from_domestic", 0))
            + int(camp_food.get("food_consumed_from_storage", 0))
            + int(camp_food.get("food_consumed_from_wild_direct", 0))
        )

        return {
            "resource_conservation_raw_material_fabrication_detected": 0,
            "food_initial_world_stock_estimate": int(initial_stock.get("food", 0)),
            "wood_initial_world_stock_estimate": int(initial_stock.get("wood", 0)),
            "stone_initial_world_stock_estimate": int(initial_stock.get("stone", 0)),
            "food_available_world_total": int(food_available_world_total),
            "food_available_on_map": int(food_stock.get("on_map", 0)),
            "food_in_agent_inventories": int(food_stock.get("in_agents", 0)),
            "food_in_storage_buildings": int(food_stock.get("in_storage", 0)),
            "food_in_camp_buffers": int(food_stock.get("in_camps", 0)),
            "food_in_construction_buffers": int(food_stock.get("in_construction_buffers", 0)),
            "food_gathered_total": int(production.get("total_food_gathered", 0)),
            "food_respawned_total": int(respawn.get("food_respawned_total", 0)),
            "food_consumed_total_observed": int(food_consumed_total_observed),
            "food_transported_to_camp_total": int(camp_food.get("camp_food_deposits", 0)),
            "food_transported_to_storage_total": int(storage_deposit_food_units),
            "food_transported_to_construction_total": int(construction_delivery_food_units),
            "food_deposited_total": int(
                int(camp_food.get("camp_food_deposits", 0))
                + int(storage_deposit_food_units)
                + int(construction_delivery_food_units)
            ),
            "food_reserve_buffered_total": int(
                int(food_stock.get("in_storage", 0)) + int(food_stock.get("in_camps", 0))
            ),
            "wood_available_world_total": int(wood_available_world_total),
            "wood_available_on_map": int(wood_stock.get("on_map", 0)),
            "wood_in_agent_inventories": int(wood_stock.get("in_agents", 0)),
            "wood_in_storage_buildings": int(wood_stock.get("in_storage", 0)),
            "wood_in_construction_buffers": int(wood_stock.get("in_construction_buffers", 0)),
            "wood_gathered_total": int(production.get("total_wood_gathered", 0)),
            "wood_respawned_total": int(respawn.get("wood_respawned_total", 0)),
            "wood_consumed_for_construction_total": int(wood_consumed_for_construction_total),
            "wood_transported_to_storage_total": int(storage_deposit_wood_units),
            "wood_transported_to_construction_total": int(construction_delivery_wood_units),
            "wood_deposited_total": int(storage_deposit_wood_units + construction_delivery_wood_units),
            "wood_reserve_buffered_total": int(wood_stock.get("in_storage", 0)),
            "wood_shortage_events": int(wood_shortage_events),
            "avg_local_wood_pressure": round(float(avg_local_wood_pressure), 4),
            "wood_outstanding_construction_demand_units": int(outstanding_wood_total),
            "wood_supply_demand_gap_units": int(wood_available_world_total - outstanding_wood_total),
            "wood_respawn_to_extraction_ratio": round(
                float(respawn.get("wood_respawned_total", 0)) / float(max(1, int(production.get("total_wood_gathered", 0)))),
                4,
            ),
            "wood_extraction_to_initial_stock_ratio": round(
                float(int(production.get("total_wood_gathered", 0))) / float(max(1, int(initial_stock.get("wood", 0)))),
                4,
            ),
            "stone_available_world_total": int(stone_available_world_total),
            "stone_available_on_map": int(stone_stock.get("on_map", 0)),
            "stone_in_agent_inventories": int(stone_stock.get("in_agents", 0)),
            "stone_in_storage_buildings": int(stone_stock.get("in_storage", 0)),
            "stone_in_construction_buffers": int(stone_stock.get("in_construction_buffers", 0)),
            "stone_gathered_total": int(production.get("total_stone_gathered", 0)),
            "stone_respawned_total": int(respawn.get("stone_respawned_total", 0)),
            "stone_consumed_for_construction_total": int(stone_consumed_for_construction_total),
            "stone_transported_to_storage_total": int(storage_deposit_stone_units),
            "stone_transported_to_construction_total": int(construction_delivery_stone_units),
            "stone_deposited_total": int(storage_deposit_stone_units + construction_delivery_stone_units),
            "stone_reserve_buffered_total": int(stone_stock.get("in_storage", 0)),
            "avg_local_stone_pressure": round(float(avg_local_stone_pressure), 4),
            "stone_outstanding_construction_demand_units": int(outstanding_stone_total),
            "stone_supply_demand_gap_units": int(stone_available_world_total - outstanding_stone_total),
            "stone_respawn_to_extraction_ratio": round(
                float(respawn.get("stone_respawned_total", 0)) / float(max(1, int(production.get("total_stone_gathered", 0)))),
                4,
            ),
            "stone_extraction_to_initial_stock_ratio": round(
                float(int(production.get("total_stone_gathered", 0))) / float(max(1, int(initial_stock.get("stone", 0)))),
                4,
            ),
            "material_transport_observed_total": int(
                int(camp_food.get("camp_food_deposits", 0))
                + int(storage_deposit_food_units)
                + int(storage_deposit_wood_units)
                + int(storage_deposit_stone_units)
                + int(construction_delivery_wood_units)
                + int(construction_delivery_stone_units)
                + int(construction_delivery_food_units)
            ),
            "construction_material_delivery_wood_units": int(construction_delivery_wood_units),
            "construction_material_delivery_stone_units": int(construction_delivery_stone_units),
            "construction_material_delivery_food_units": int(construction_delivery_food_units),
            "storage_deposit_food_units": int(storage_deposit_food_units),
            "storage_deposit_wood_units": int(storage_deposit_wood_units),
            "storage_deposit_stone_units": int(storage_deposit_stone_units),
            "construction_sites_created": int(progression.get("construction_sites_created", 0)),
            "construction_sites_created_house": int(progression.get("construction_sites_created_house", 0)),
            "construction_sites_created_storage": int(progression.get("construction_sites_created_storage", 0)),
            "active_construction_sites": int(active_sites),
            "partially_built_sites_count": int(partial_sites),
            "construction_stalled_ticks": int(progression.get("construction_progress_stalled_ticks", 0)),
            "construction_stalled_sites_count": int(stalled_sites),
            "construction_completed_count": int(progression.get("construction_completion_events", 0)),
            "construction_abandoned_count": int(progression.get("construction_abandonment_events", 0)),
            "construction_progress_ticks": int(progression.get("construction_progress_ticks", 0)),
            "construction_material_delivery_events": int(progression.get("construction_material_delivery_events", 0)),
            "construction_material_delivery_to_active_site": int(progression.get("construction_material_delivery_to_active_site", 0)),
            "construction_material_delivery_drift_events": int(progression.get("construction_material_delivery_drift_events", 0)),
            "construction_delivery_attempts": int(progression.get("construction_delivery_attempts", 0)),
            "construction_delivery_successes": int(progression.get("construction_delivery_successes", 0)),
            "construction_delivery_failures": int(progression.get("construction_delivery_failures", 0)),
            "construction_delivery_to_site_events": int(progression.get("construction_delivery_to_site_events", 0)),
            "construction_delivery_to_wrong_target_or_drift": int(
                progression.get("construction_delivery_to_wrong_target_or_drift", 0)
            ),
            "construction_delivery_source_binding_selected_count": int(
                progression.get("construction_delivery_source_binding_selected_count", 0)
            ),
            "construction_delivery_source_binding_persisted_count": int(
                progression.get("construction_delivery_source_binding_persisted_count", 0)
            ),
            "construction_delivery_source_binding_refreshed_count": int(
                progression.get("construction_delivery_source_binding_refreshed_count", 0)
            ),
            "construction_delivery_source_binding_missing_count": int(
                progression.get("construction_delivery_source_binding_missing_count", 0)
            ),
            "construction_delivery_source_binding_unavailable_count": int(
                progression.get("construction_delivery_source_binding_unavailable_count", 0)
            ),
            "construction_delivery_source_binding_lost_missing_source_count": int(
                progression.get("construction_delivery_source_binding_lost_missing_source_count", 0)
            ),
            "construction_delivery_source_binding_lost_ineligible_source_count": int(
                progression.get("construction_delivery_source_binding_lost_ineligible_source_count", 0)
            ),
            "construction_delivery_source_binding_lost_not_refreshed_count": int(
                progression.get("construction_delivery_source_binding_lost_not_refreshed_count", 0)
            ),
            "construction_delivery_prepickup_checks_count": int(
                progression.get("construction_delivery_prepickup_checks_count", 0)
            ),
            "construction_delivery_prepickup_site_exists_count": int(
                progression.get("construction_delivery_prepickup_site_exists_count", 0)
            ),
            "construction_delivery_prepickup_site_missing_count": int(
                progression.get("construction_delivery_prepickup_site_missing_count", 0)
            ),
            "construction_delivery_prepickup_site_under_construction_count": int(
                progression.get("construction_delivery_prepickup_site_under_construction_count", 0)
            ),
            "construction_delivery_prepickup_site_not_under_construction_count": int(
                progression.get("construction_delivery_prepickup_site_not_under_construction_count", 0)
            ),
            "construction_delivery_prepickup_site_reachable_count": int(
                progression.get("construction_delivery_prepickup_site_reachable_count", 0)
            ),
            "construction_delivery_prepickup_site_unreachable_count": int(
                progression.get("construction_delivery_prepickup_site_unreachable_count", 0)
            ),
            "construction_delivery_prepickup_site_demand_matches_material_count": int(
                progression.get("construction_delivery_prepickup_site_demand_matches_material_count", 0)
            ),
            "construction_delivery_prepickup_site_demand_mismatch_material_count": int(
                progression.get("construction_delivery_prepickup_site_demand_mismatch_material_count", 0)
            ),
            "construction_delivery_source_persistence_window_invoked_count": int(
                progression.get("construction_delivery_source_persistence_window_invoked_count", 0)
            ),
            "construction_delivery_source_persistence_window_completed_count": int(
                progression.get("construction_delivery_source_persistence_window_completed_count", 0)
            ),
            "construction_delivery_source_persistence_window_broken_by_source_invalidity_count": int(
                progression.get("construction_delivery_source_persistence_window_broken_by_source_invalidity_count", 0)
            ),
            "construction_delivery_source_persistence_window_broken_by_demand_mismatch_count": int(
                progression.get("construction_delivery_source_persistence_window_broken_by_demand_mismatch_count", 0)
            ),
            "construction_delivery_reservation_alignment_pass_count": int(
                progression.get("construction_delivery_reservation_alignment_pass_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_count": int(
                progression.get("construction_delivery_reservation_alignment_fail_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_material_wood_count": int(
                progression.get("construction_delivery_reservation_alignment_fail_material_wood_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_material_stone_count": int(
                progression.get("construction_delivery_reservation_alignment_fail_material_stone_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_material_food_count": int(
                progression.get("construction_delivery_reservation_alignment_fail_material_food_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_reason_site_missing_count": int(
                progression.get("construction_delivery_reservation_alignment_fail_reason_site_missing_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_reason_site_not_under_construction_count": int(
                progression.get("construction_delivery_reservation_alignment_fail_reason_site_not_under_construction_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_reason_reservation_invalid_count": int(
                progression.get("construction_delivery_reservation_alignment_fail_reason_reservation_invalid_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_reason_demand_mismatch_count": int(
                progression.get("construction_delivery_reservation_alignment_fail_reason_demand_mismatch_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_reason_source_ineligible_count": int(
                progression.get("construction_delivery_reservation_alignment_fail_reason_source_ineligible_count", 0)
            ),
            "construction_delivery_reservation_alignment_fail_reason_source_empty_count": int(
                progression.get("construction_delivery_reservation_alignment_fail_reason_source_empty_count", 0)
            ),
            "delivery_commitment_hold_invoked_count": int(
                progression.get("delivery_commitment_hold_invoked_count", 0)
            ),
            "delivery_commitment_hold_completed_count": int(
                progression.get("delivery_commitment_hold_completed_count", 0)
            ),
            "delivery_commitment_hold_broken_by_survival_count": int(
                progression.get("delivery_commitment_hold_broken_by_survival_count", 0)
            ),
            "delivery_commitment_hold_broken_by_invalid_site_count": int(
                progression.get("delivery_commitment_hold_broken_by_invalid_site_count", 0)
            ),
            "delivery_commitment_hold_broken_by_invalid_source_count": int(
                progression.get("delivery_commitment_hold_broken_by_invalid_source_count", 0)
            ),
            "construction_delivery_invalid_site_missing_site_count": int(
                progression.get("construction_delivery_invalid_site_missing_site_count", 0)
            ),
            "construction_delivery_invalid_site_not_under_construction_count": int(
                progression.get("construction_delivery_invalid_site_not_under_construction_count", 0)
            ),
            "construction_delivery_invalid_site_village_mismatch_count": int(
                progression.get("construction_delivery_invalid_site_village_mismatch_count", 0)
            ),
            "construction_delivery_invalid_site_construction_completed_count": int(
                progression.get("construction_delivery_invalid_site_construction_completed_count", 0)
            ),
            "construction_delivery_invalid_site_no_path_to_site_count": int(
                progression.get("construction_delivery_invalid_site_no_path_to_site_count", 0)
            ),
            "construction_delivery_invalid_site_demand_mismatch_count": int(
                progression.get("construction_delivery_invalid_site_demand_mismatch_count", 0)
            ),
            "construction_delivery_invalid_site_other_count": int(
                progression.get("construction_delivery_invalid_site_other_count", 0)
            ),
            "construction_delivery_invalid_source_no_source_available_count": int(
                progression.get("construction_delivery_invalid_source_no_source_available_count", 0)
            ),
            "construction_delivery_invalid_source_source_depleted_count": int(
                progression.get("construction_delivery_invalid_source_source_depleted_count", 0)
            ),
            "construction_delivery_invalid_source_reservation_invalidated_count": int(
                progression.get("construction_delivery_invalid_source_reservation_invalidated_count", 0)
            ),
            "construction_delivery_invalid_source_source_reassigned_count": int(
                progression.get("construction_delivery_invalid_source_source_reassigned_count", 0)
            ),
            "construction_delivery_invalid_source_linkage_mismatch_count": int(
                progression.get("construction_delivery_invalid_source_linkage_mismatch_count", 0)
            ),
            "construction_delivery_invalid_source_no_path_to_source_count": int(
                progression.get("construction_delivery_invalid_source_no_path_to_source_count", 0)
            ),
            "construction_delivery_invalid_source_other_count": int(
                progression.get("construction_delivery_invalid_source_other_count", 0)
            ),
            "construction_delivery_invalid_site_before_pickup_count": int(
                progression.get("construction_delivery_invalid_site_before_pickup_count", 0)
            ),
            "construction_delivery_invalid_site_after_pickup_count": int(
                progression.get("construction_delivery_invalid_site_after_pickup_count", 0)
            ),
            "construction_delivery_invalid_source_before_pickup_count": int(
                progression.get("construction_delivery_invalid_source_before_pickup_count", 0)
            ),
            "construction_delivery_invalid_source_after_pickup_count": int(
                progression.get("construction_delivery_invalid_source_after_pickup_count", 0)
            ),
            "construction_delivery_ticks_reservation_to_invalid_site_avg": float(
                progression.get("construction_delivery_ticks_reservation_to_invalid_site_avg", 0.0)
            ),
            "construction_delivery_ticks_reservation_to_invalid_source_avg": float(
                progression.get("construction_delivery_ticks_reservation_to_invalid_source_avg", 0.0)
            ),
            "construction_delivery_ticks_pickup_to_invalid_site_avg": float(
                progression.get("construction_delivery_ticks_pickup_to_invalid_site_avg", 0.0)
            ),
            "construction_delivery_ticks_pickup_to_invalid_source_avg": float(
                progression.get("construction_delivery_ticks_pickup_to_invalid_source_avg", 0.0)
            ),
            "construction_delivery_invalid_site_material_wood_count": int(
                progression.get("construction_delivery_invalid_site_material_wood_count", 0)
            ),
            "construction_delivery_invalid_site_material_stone_count": int(
                progression.get("construction_delivery_invalid_site_material_stone_count", 0)
            ),
            "construction_delivery_invalid_site_material_food_count": int(
                progression.get("construction_delivery_invalid_site_material_food_count", 0)
            ),
            "construction_delivery_invalid_source_material_wood_count": int(
                progression.get("construction_delivery_invalid_source_material_wood_count", 0)
            ),
            "construction_delivery_invalid_source_material_stone_count": int(
                progression.get("construction_delivery_invalid_source_material_stone_count", 0)
            ),
            "construction_delivery_invalid_source_material_food_count": int(
                progression.get("construction_delivery_invalid_source_material_food_count", 0)
            ),
            "construction_delivery_invalid_site_committed_site_mismatch_count": int(
                progression.get("construction_delivery_invalid_site_committed_site_mismatch_count", 0)
            ),
            "construction_delivery_invalid_source_committed_source_missing_count": int(
                progression.get("construction_delivery_invalid_source_committed_source_missing_count", 0)
            ),
            "construction_delivery_failure_no_source_available": int(construction_delivery_failure_no_source_available),
            "construction_delivery_failure_source_depleted": int(construction_delivery_failure_source_depleted),
            "construction_delivery_failure_reservation_invalidated": int(
                construction_delivery_failure_reservation_invalidated
            ),
            "construction_delivery_failure_no_path_to_source": int(construction_delivery_failure_no_path_to_source),
            "construction_delivery_failure_no_path_to_site": int(construction_delivery_failure_no_path_to_site),
            "construction_delivery_failure_arrival_failed": int(construction_delivery_failure_arrival_failed),
            "construction_delivery_failure_retargeted_before_delivery": int(
                construction_delivery_failure_retargeted_before_delivery
            ),
            "construction_delivery_failure_interrupted_by_other_priority": int(
                construction_delivery_failure_interrupted_by_other_priority
            ),
            "construction_delivery_failure_unknown": int(construction_delivery_failure_unknown),
            "construction_delivery_avg_distance_to_site": float(
                progression.get("construction_delivery_avg_distance_to_site", 0.0)
            ),
            "construction_delivery_avg_distance_to_source": float(
                progression.get("construction_delivery_avg_distance_to_source", 0.0)
            ),
            "storage_delivery_failures": int(progression.get("storage_delivery_failures", 0)),
            "house_delivery_failures": int(progression.get("house_delivery_failures", 0)),
            "storage_delivery_successes": int(progression.get("storage_delivery_successes", 0)),
            "house_delivery_successes": int(progression.get("house_delivery_successes", 0)),
            "construction_material_delivery_failures": int(construction_delivery_failures),
            "construction_material_shortage_blocks": int(shortage_blocks),
            "construction_material_source_failures": int(material_delivery_failures),
            "construction_site_waiting_for_material_ticks": int(
                progression.get("construction_site_waiting_for_material_ticks", 0)
            ),
            "construction_site_waiting_for_builder_ticks": int(
                progression.get("construction_site_waiting_for_builder_ticks", 0)
            ),
            "construction_site_waiting_total_ticks": int(progression.get("construction_site_waiting_total_ticks", 0)),
            "construction_site_progress_active_ticks": int(progression.get("construction_site_progress_active_ticks", 0)),
            "construction_site_starved_cycles": int(progression.get("construction_site_starved_cycles", 0)),
            "storage_waiting_for_material_ticks": int(progression.get("storage_waiting_for_material_ticks", 0)),
            "house_waiting_for_material_ticks": int(progression.get("house_waiting_for_material_ticks", 0)),
            "storage_waiting_for_builder_ticks": int(progression.get("storage_waiting_for_builder_ticks", 0)),
            "house_waiting_for_builder_ticks": int(progression.get("house_waiting_for_builder_ticks", 0)),
            "construction_site_lifetime_ticks_avg": float(progression.get("construction_site_lifetime_ticks_avg", 0.0)),
            "construction_site_progress_before_abandon_avg": float(
                progression.get("construction_site_progress_before_abandon_avg", 0.0)
            ),
            "construction_site_material_units_delivered_avg": float(
                progression.get("construction_site_material_units_delivered_avg", 0.0)
            ),
            "construction_site_material_units_missing_avg": float(
                progression.get("construction_site_material_units_missing_avg", 0.0)
            ),
            "construction_site_material_units_required_total": int(
                progression.get("construction_site_material_units_required_total", 0)
            ),
            "construction_site_material_units_delivered_total": int(
                progression.get("construction_site_material_units_delivered_total", 0)
            ),
            "construction_site_material_units_remaining": int(
                progression.get("construction_site_material_units_remaining", 0)
            ),
            "construction_site_required_work_ticks_total": int(
                progression.get("construction_site_required_work_ticks_total", 0)
            ),
            "construction_site_completed_work_ticks_total": int(
                progression.get("construction_site_completed_work_ticks_total", 0)
            ),
            "construction_site_remaining_work_ticks": int(
                progression.get("construction_site_remaining_work_ticks", 0)
            ),
            "construction_build_state_planned_count": int(
                progression.get("construction_build_state_planned_count", 0)
            ),
            "construction_build_state_supplying_count": int(
                progression.get("construction_build_state_supplying_count", 0)
            ),
            "construction_build_state_buildable_count": int(
                progression.get("construction_build_state_buildable_count", 0)
            ),
            "construction_build_state_in_progress_count": int(
                progression.get("construction_build_state_in_progress_count", 0)
            ),
            "construction_build_state_paused_count": int(
                progression.get("construction_build_state_paused_count", 0)
            ),
            "construction_build_state_completed_count": int(
                progression.get("construction_build_state_completed_count", 0)
            ),
            "construction_near_complete_sites_count": int(
                progression.get("construction_near_complete_sites_count", 0)
            ),
            "builder_assigned_site_count": int(progression.get("builder_assigned_site_count", 0)),
            "builder_site_arrival_count": int(progression.get("builder_site_arrival_count", 0)),
            "builder_left_site_count": int(progression.get("builder_left_site_count", 0)),
            "builder_left_site_before_completion_count": int(
                progression.get("builder_left_site_before_completion_count", 0)
            ),
            "builder_waiting_on_site_ticks_total": int(
                progression.get("builder_waiting_on_site_ticks_total", 0)
            ),
            "builder_on_site_ticks_total": int(progression.get("builder_on_site_ticks_total", 0)),
            "builder_work_tick_applied_count": int(
                progression.get("builder_work_tick_applied_count", 0)
            ),
            "builder_survival_override_during_construction_count": int(
                progression.get("builder_survival_override_during_construction_count", 0)
            ),
            "builder_redirected_to_storage_during_construction_count": int(
                progression.get("builder_redirected_to_storage_during_construction_count", 0)
            ),
            "builder_commitment_created_count": int(
                progression.get("builder_commitment_created_count", 0)
            ),
            "builder_commitment_pause_count": int(
                progression.get("builder_commitment_pause_count", 0)
            ),
            "builder_commitment_resume_count": int(
                progression.get("builder_commitment_resume_count", 0)
            ),
            "builder_commitment_completed_count": int(
                progression.get("builder_commitment_completed_count", 0)
            ),
            "builder_commitment_abandoned_count": int(
                progression.get("builder_commitment_abandoned_count", 0)
            ),
            "builder_returned_to_same_site_count": int(
                progression.get("builder_returned_to_same_site_count", 0)
            ),
            "builder_commitment_duration_avg": float(
                progression.get("builder_commitment_duration_avg", 0.0)
            ),
            "builder_commitment_resume_delay_avg": float(
                progression.get("builder_commitment_resume_delay_avg", 0.0)
            ),
            "construction_site_buildable_ticks_total": int(
                progression.get("construction_site_buildable_ticks_total", 0)
            ),
            "construction_site_idle_buildable_ticks_total": int(
                progression.get("construction_site_idle_buildable_ticks_total", 0)
            ),
            "construction_site_buildable_but_idle_ticks_total": int(
                progression.get("construction_site_buildable_but_idle_ticks_total", 0)
            ),
            "construction_site_waiting_materials_ticks_total": int(
                progression.get("construction_site_waiting_materials_ticks_total", 0)
            ),
            "construction_site_in_progress_ticks_total": int(
                progression.get("construction_site_in_progress_ticks_total", 0)
            ),
            "construction_site_distinct_builders_avg": float(
                progression.get("construction_site_distinct_builders_avg", 0.0)
            ),
            "construction_site_work_ticks_per_builder_avg": float(
                progression.get("construction_site_work_ticks_per_builder_avg", 0.0)
            ),
            "construction_site_delivery_to_work_gap_avg": float(
                progression.get("construction_site_delivery_to_work_gap_avg", 0.0)
            ),
            "construction_site_active_age_ticks_avg": float(
                progression.get("construction_site_active_age_ticks_avg", 0.0)
            ),
            "construction_site_nearest_wood_distance_avg": float(
                progression.get("construction_site_nearest_wood_distance_avg", 0.0)
            ),
            "construction_site_nearest_stone_distance_avg": float(
                progression.get("construction_site_nearest_stone_distance_avg", 0.0)
            ),
            "construction_site_viable_wood_sources_within_radius_avg": float(
                progression.get("construction_site_viable_wood_sources_within_radius_avg", 0.0)
            ),
            "construction_site_viable_stone_sources_within_radius_avg": float(
                progression.get("construction_site_viable_stone_sources_within_radius_avg", 0.0)
            ),
            "construction_site_zero_wood_sources_within_radius_ticks": int(
                progression.get("construction_site_zero_wood_sources_within_radius_ticks", 0)
            ),
            "construction_site_zero_stone_sources_within_radius_ticks": int(
                progression.get("construction_site_zero_stone_sources_within_radius_ticks", 0)
            ),
            "construction_site_local_wood_source_contention_avg": float(
                progression.get("construction_site_local_wood_source_contention_avg", 0.0)
            ),
            "construction_site_local_stone_source_contention_avg": float(
                progression.get("construction_site_local_stone_source_contention_avg", 0.0)
            ),
            "construction_site_ticks_since_last_delivery_avg": float(
                progression.get("construction_site_ticks_since_last_delivery_avg", 0.0)
            ),
            "construction_site_waiting_with_positive_wood_stock_ticks": int(
                progression.get("construction_site_waiting_with_positive_wood_stock_ticks", 0)
            ),
            "construction_site_waiting_with_positive_stone_stock_ticks": int(
                progression.get("construction_site_waiting_with_positive_stone_stock_ticks", 0)
            ),
            "construction_site_first_demand_to_first_delivery_avg": float(
                progression.get("construction_site_first_demand_to_first_delivery_avg", 0.0)
            ),
            "construction_site_material_inflow_rate_avg": float(
                progression.get("construction_site_material_inflow_rate_avg", 0.0)
            ),
            "construction_site_delivered_wood_units_total_live": int(
                progression.get("construction_site_delivered_wood_units_total_live", 0)
            ),
            "construction_site_delivered_stone_units_total_live": int(
                progression.get("construction_site_delivered_stone_units_total_live", 0)
            ),
            "construction_site_delivered_food_units_total_live": int(
                progression.get("construction_site_delivered_food_units_total_live", 0)
            ),
            "active_builders_count": int(progression.get("active_builders_count", 0)),
            "active_haulers_count": int(progression.get("active_haulers_count", 0)),
            "active_builders_nearest_wood_distance_avg": float(
                progression.get("active_builders_nearest_wood_distance_avg", 0.0)
            ),
            "active_builders_nearest_stone_distance_avg": float(
                progression.get("active_builders_nearest_stone_distance_avg", 0.0)
            ),
            "active_haulers_nearest_wood_distance_avg": float(
                progression.get("active_haulers_nearest_wood_distance_avg", 0.0)
            ),
            "active_haulers_nearest_stone_distance_avg": float(
                progression.get("active_haulers_nearest_stone_distance_avg", 0.0)
            ),
            "construction_site_first_builder_arrival_delay_avg": float(
                progression.get("construction_site_first_builder_arrival_delay_avg", 0.0)
            ),
            "construction_site_material_ready_to_first_work_delay_avg": float(
                progression.get("construction_site_material_ready_to_first_work_delay_avg", 0.0)
            ),
            "construction_site_completion_time_avg": float(progression.get("construction_site_completion_time_avg", 0.0)),
            "construction_time_first_delivery_to_completion_avg": float(
                progression.get("construction_time_first_delivery_to_completion_avg", 0.0)
            ),
            "construction_time_first_progress_to_completion_avg": float(
                progression.get("construction_time_first_progress_to_completion_avg", 0.0)
            ),
            "construction_time_first_work_to_completion_avg": float(
                progression.get("construction_time_first_work_to_completion_avg", 0.0)
            ),
            "construction_completed_after_first_delivery_count": int(
                progression.get("construction_completed_after_first_delivery_count", 0)
            ),
            "construction_completed_after_started_progress_count": int(
                progression.get("construction_completed_after_started_progress_count", 0)
            ),
            "construction_completed_after_first_work_count": int(
                progression.get("construction_completed_after_first_work_count", 0)
            ),
            "house_completion_time_avg": float(progression.get("house_completion_time_avg", 0.0)),
            "storage_completion_time_avg": float(progression.get("storage_completion_time_avg", 0.0)),
            "houses_completed_count": int(houses_completed),
            "storage_attempts": int(progression.get("storage_attempts", 0)),
            "storage_completed_count": int(storage_completed),
            "storage_completion_rate": float(progression.get("storage_completion_rate", 0.0)),
            "storage_emergence_attempts": int(progression.get("storage_emergence_attempts", 0)),
        }

    def _behavior_region_key(self, x: int, y: int, *, cell: int = 6) -> str:
        rx = max(0, int(x) // max(1, int(cell)))
        ry = max(0, int(y) // max(1, int(cell)))
        return f"{rx}:{ry}"

    def record_behavior_activity(
        self,
        activity_type: str,
        *,
        x: int,
        y: int,
        agent: Optional[Agent] = None,
        count: int = 1,
    ) -> None:
        key = str(activity_type or "unknown").strip().lower() or "unknown"
        qty = max(0, int(count))
        if qty <= 0:
            return
        stats = self.behavior_map_stats if isinstance(self.behavior_map_stats, dict) else _default_behavior_map_stats()
        region = self._behavior_region_key(int(x), int(y))
        activity_counts = stats.setdefault("activity_counts", {})
        activity_counts[key] = int(activity_counts.get(key, 0)) + qty
        by_region = stats.setdefault("activity_by_region", {})
        by_region[region] = int(by_region.get(region, 0)) + qty
        by_type_region = stats.setdefault("activity_by_type_region", {})
        regions = by_type_region.setdefault(key, {})
        regions[region] = int(regions.get(region, 0)) + qty

        context_counts = stats.setdefault("activity_context_counts", {})
        if self._is_in_food_patch(int(x), int(y)):
            tag = f"{key}:near_food_patch"
            context_counts[tag] = int(context_counts.get(tag, 0)) + qty
        if self.nearest_active_camp_for_agent(agent, max_distance=4) if isinstance(agent, Agent) else False:
            tag = f"{key}:near_camp"
            context_counts[tag] = int(context_counts.get(tag, 0)) + qty
        local_density = self._count_alive_agents_near(int(x), int(y), radius=4)
        density_tag = "low_density" if local_density <= 2 else ("high_density" if local_density >= 7 else "mid_density")
        tag = f"{key}:{density_tag}"
        context_counts[tag] = int(context_counts.get(tag, 0)) + qty
        self.behavior_map_stats = stats

    def record_behavior_transition(
        self,
        from_task: str,
        to_task: str,
        *,
        x: int,
        y: int,
        count: int = 1,
    ) -> None:
        src = str(from_task or "unknown").strip().lower() or "unknown"
        dst = str(to_task or "unknown").strip().lower() or "unknown"
        qty = max(0, int(count))
        if qty <= 0 or src == dst:
            return
        stats = self.behavior_map_stats if isinstance(self.behavior_map_stats, dict) else _default_behavior_map_stats()
        key = f"{src}->{dst}"
        transitions = stats.setdefault("task_transition_counts", {})
        transitions[key] = int(transitions.get(key, 0)) + qty
        by_region = stats.setdefault("task_transition_by_region", {})
        region = self._behavior_region_key(int(x), int(y))
        region_map = by_region.setdefault(region, {})
        region_map[key] = int(region_map.get(key, 0)) + qty
        self.behavior_map_stats = stats

    def record_secondary_nucleus_event(self, event_key: str, *, count: int = 1) -> None:
        key = str(event_key or "").strip()
        stats = self.behavior_map_stats if isinstance(self.behavior_map_stats, dict) else _default_behavior_map_stats()
        if key not in {
            "secondary_nucleus_birth_count",
            "secondary_nucleus_persistence_ticks",
            "secondary_nucleus_absorption_count",
            "secondary_nucleus_decay_count",
            "secondary_nucleus_village_attempts",
            "secondary_nucleus_village_successes",
        }:
            return
        stats[key] = int(stats.get(key, 0)) + max(0, int(count))
        self.behavior_map_stats = stats

    def compute_behavior_map_snapshot(self) -> Dict[str, Any]:
        stats = self.behavior_map_stats if isinstance(self.behavior_map_stats, dict) else _default_behavior_map_stats()
        by_type_region = stats.get("activity_by_type_region", {}) if isinstance(stats.get("activity_by_type_region", {}), dict) else {}
        top_regions: Dict[str, List[Dict[str, Any]]] = {}
        for activity, regions in by_type_region.items():
            if not isinstance(regions, dict):
                continue
            ranked = sorted(regions.items(), key=lambda item: (-int(item[1]), str(item[0])))[:8]
            top_regions[str(activity)] = [
                {"region": str(region), "count": int(count)}
                for region, count in ranked
            ]
        transitions = stats.get("task_transition_counts", {}) if isinstance(stats.get("task_transition_counts", {}), dict) else {}
        top_transitions = sorted(transitions.items(), key=lambda item: (-int(item[1]), str(item[0])))[:24]
        return {
            "activity_counts": {str(k): int(v) for k, v in ((stats.get("activity_counts", {}) or {}).items())},
            "activity_heatmap_by_type": {
                str(k): {str(r): int(c) for r, c in (v.items() if isinstance(v, dict) else [])}
                for k, v in by_type_region.items()
            },
            "top_active_regions_by_type": top_regions,
            "task_transition_counts": {str(k): int(v) for k, v in transitions.items()},
            "top_task_transitions": [
                {"transition": str(k), "count": int(v)}
                for k, v in top_transitions
            ],
            "task_transition_by_region": {
                str(region): {str(k): int(v) for k, v in (mapping.items() if isinstance(mapping, dict) else [])}
                for region, mapping in ((stats.get("task_transition_by_region", {}) or {}).items())
            },
            "activity_context_counts": {str(k): int(v) for k, v in ((stats.get("activity_context_counts", {}) or {}).items())},
            "secondary_nucleus_lifecycle": {
                "secondary_nucleus_birth_count": int(stats.get("secondary_nucleus_birth_count", 0)),
                "secondary_nucleus_persistence_ticks": int(stats.get("secondary_nucleus_persistence_ticks", 0)),
                "secondary_nucleus_absorption_count": int(stats.get("secondary_nucleus_absorption_count", 0)),
                "secondary_nucleus_decay_count": int(stats.get("secondary_nucleus_decay_count", 0)),
                "secondary_nucleus_village_attempts": int(stats.get("secondary_nucleus_village_attempts", 0)),
                "secondary_nucleus_village_successes": int(stats.get("secondary_nucleus_village_successes", 0)),
            },
            "cluster_population_distribution_summary": dict(self.compute_settlement_bottleneck_snapshot().get("cluster_population_distribution_summary", {})),
        }

    def record_road_purpose_decision(self, *, village_uid: Optional[str], built: bool, reason: str) -> None:
        stats = self.progression_stats if isinstance(self.progression_stats, dict) else _default_progression_stats()
        progression = self.settlement_progression_stats if isinstance(self.settlement_progression_stats, dict) else _default_settlement_progression_stats()
        uid = str(village_uid or "")
        reason_key = str(reason or "unknown")
        if built:
            stats["road_built_with_purpose_count"] = int(stats.get("road_built_with_purpose_count", 0)) + 1
            if int(progression.get("first_road_completion_tick", -1)) < 0:
                progression["first_road_completion_tick"] = int(getattr(self, "tick", 0))
            if int(progression.get("first_house_completion_tick", -1)) < 0:
                progression["road_built_before_house_threshold_count"] = int(
                    progression.get("road_built_before_house_threshold_count", 0)
                ) + 1
        else:
            stats["road_build_suppressed_no_purpose"] = int(stats.get("road_build_suppressed_no_purpose", 0)) + 1
            global_reasons = stats.setdefault("road_build_suppressed_reasons", {})
            global_reasons[reason_key] = int(global_reasons.get(reason_key, 0)) + 1
        if uid:
            by_village = stats.setdefault("by_village", {})
            entry = by_village.get(uid)
            if not isinstance(entry, dict):
                entry = {
                    "camp_return_events": 0,
                    "camp_rest_events": 0,
                    "early_road_suppressed_count": 0,
                    "road_priority_deferred_reasons": {},
                    "road_built_with_purpose_count": 0,
                    "road_build_suppressed_no_purpose": 0,
                    "road_build_suppressed_reasons": {},
                }
                by_village[uid] = entry
            if built:
                entry["road_built_with_purpose_count"] = int(entry.get("road_built_with_purpose_count", 0)) + 1
            else:
                entry["road_build_suppressed_no_purpose"] = int(entry.get("road_build_suppressed_no_purpose", 0)) + 1
                vreasons = entry.setdefault("road_build_suppressed_reasons", {})
                vreasons[reason_key] = int(vreasons.get(reason_key, 0)) + 1
        self.progression_stats = stats
        self.settlement_progression_stats = progression

    def should_defer_road_growth_for_village(self, village: Dict[str, Any]) -> Tuple[bool, str]:
        if not isinstance(village, dict):
            return (False, "")
        uid = str(village.get("village_uid", "") or "")
        needs = village.get("needs", {}) if isinstance(village.get("needs"), dict) else {}
        metrics = village.get("metrics", {}) if isinstance(village.get("metrics"), dict) else {}
        pop = int(metrics.get("population", village.get("population", 0)))
        houses = int(village.get("houses", 0))
        formalized = bool(village.get("formalized", True))
        stability_ticks = int(village.get("stability_ticks", int(SETTLEMENT_STABILITY_TICK_THRESHOLD)))
        food_stock = int(metrics.get("food_stock", (village.get("storage", {}) or {}).get("food", 0)))
        food_buffer_critical = bool(needs.get("food_buffer_critical", False))
        camps = self.compute_progression_snapshot().get("active_camps_by_village", {})
        camp_count = int(camps.get(uid, 0)) if isinstance(camps, dict) else 0
        reason = ""
        if not formalized:
            reason = "village_not_formalized"
        elif stability_ticks < int(SETTLEMENT_STABILITY_TICK_THRESHOLD):
            reason = "village_not_stable_yet"
        elif pop < 5:
            reason = "population_too_low"
        elif houses < 3 and camp_count <= 0:
            reason = "no_settlement_anchor"
        elif food_buffer_critical or food_stock < max(3, pop // 2):
            reason = "food_crisis_active"
        if not reason:
            return (False, "")
        stats = self.progression_stats if isinstance(self.progression_stats, dict) else _default_progression_stats()
        stats["early_road_suppressed_count"] = int(stats.get("early_road_suppressed_count", 0)) + 1
        reasons = stats.setdefault("road_priority_deferred_reasons", {})
        reasons[reason] = int(reasons.get(reason, 0)) + 1
        if uid:
            by_village = stats.setdefault("by_village", {})
            entry = by_village.get(uid)
            if not isinstance(entry, dict):
                entry = {
                    "camp_return_events": 0,
                    "camp_rest_events": 0,
                    "early_road_suppressed_count": 0,
                    "road_priority_deferred_reasons": {},
                    "road_built_with_purpose_count": 0,
                    "road_build_suppressed_no_purpose": 0,
                    "road_build_suppressed_reasons": {},
                }
                by_village[uid] = entry
            entry["early_road_suppressed_count"] = int(entry.get("early_road_suppressed_count", 0)) + 1
            vreasons = entry.setdefault("road_priority_deferred_reasons", {})
            vreasons[reason] = int(vreasons.get(reason, 0)) + 1
        self.progression_stats = stats
        return (True, reason)

    def compute_progression_snapshot(self) -> Dict[str, Any]:
        communities = self.proto_communities if isinstance(self.proto_communities, dict) else {}
        camps = self.camps if isinstance(self.camps, dict) else {}
        active_communities = [
            c for c in communities.values()
            if isinstance(c, dict) and int(getattr(self, "tick", 0)) - int(c.get("last_seen_tick", -10**9)) <= PROTO_COMMUNITY_STALE_TICKS
        ]
        active_camps = [c for c in camps.values() if isinstance(c, dict) and bool(c.get("active", False))]
        active_camps_by_village: Dict[str, int] = {}
        for camp in active_camps:
            uid = str(camp.get("village_uid", "") or "")
            if not uid:
                continue
            active_camps_by_village[uid] = int(active_camps_by_village.get(uid, 0)) + 1

        camp_population = 0
        for agent in self.agents:
            if not getattr(agent, "alive", False):
                continue
            camp = self.nearest_active_camp_for_agent(agent, max_distance=4)
            if camp is not None:
                camp_population += 1
        house_population = sum(
            1 for a in self.agents if getattr(a, "alive", False) and getattr(a, "home_building_id", None) is not None
        )
        stats = self.progression_stats if isinstance(self.progression_stats, dict) else _default_progression_stats()
        return {
            "proto_community_count": int(len(active_communities)),
            "proto_community_agents": int(sum(int(c.get("agent_count", 0)) for c in active_communities)),
            "camps_count": int(len(camps)),
            "active_camps_count": int(len(active_camps)),
            "active_camps_by_village": dict(sorted(active_camps_by_village.items(), key=lambda item: item[0])),
            "camp_return_events": int(stats.get("camp_return_events", 0)),
            "camp_rest_events": int(stats.get("camp_rest_events", 0)),
            "house_vs_camp_population": {
                "house_population": int(house_population),
                "camp_population": int(camp_population),
            },
            "early_road_suppressed_count": int(stats.get("early_road_suppressed_count", 0)),
            "road_priority_deferred_reasons": {
                str(k): int(v) for k, v in ((stats.get("road_priority_deferred_reasons", {}) or {}).items())
            },
            "road_built_with_purpose_count": int(stats.get("road_built_with_purpose_count", 0)),
            "road_build_suppressed_no_purpose": int(stats.get("road_build_suppressed_no_purpose", 0)),
            "road_build_suppressed_reasons": {
                str(k): int(v) for k, v in ((stats.get("road_build_suppressed_reasons", {}) or {}).items())
            },
            "settlement_stage_counts": {
                "survival": int(sum(1 for v in self.villages if str(v.get("phase", "")) in {"bootstrap", "survival"})),
                "camp": int(len(active_camps)),
                "village": int(len(self.villages)),
                "mature_village": int(sum(1 for v in self.villages if int(v.get("houses", 0)) >= 6)),
            },
            "by_village": dict(sorted((stats.get("by_village", {}) or {}).items(), key=lambda item: item[0])),
        }

    def record_social_gravity_event(self, event_key: str, *, village_uid: Optional[str] = None) -> None:
        key = str(event_key).strip()
        if key not in {"return_to_village_events", "stay_near_village_bias_events", "home_return_events"}:
            return
        stats = self.social_gravity_event_stats
        if not isinstance(stats, dict):
            stats = _default_social_gravity_event_stats()
            self.social_gravity_event_stats = stats
        stats[key] = int(stats.get(key, 0)) + 1
        uid = str(village_uid or "")
        if uid:
            by_village = stats.setdefault("by_village", {})
            entry = by_village.get(uid)
            if not isinstance(entry, dict):
                entry = {
                    "return_to_village_events": 0,
                    "stay_near_village_bias_events": 0,
                    "home_return_events": 0,
                }
                by_village[uid] = entry
            entry[key] = int(entry.get(key, 0)) + 1

    def compute_social_gravity_event_snapshot(self) -> Dict[str, Any]:
        stats = self.social_gravity_event_stats if isinstance(self.social_gravity_event_stats, dict) else _default_social_gravity_event_stats()
        by_village: Dict[str, Dict[str, int]] = {}
        for uid, entry in (stats.get("by_village", {}) or {}).items():
            if not isinstance(entry, dict):
                continue
            by_village[str(uid)] = {
                "return_to_village_events": int(entry.get("return_to_village_events", 0)),
                "stay_near_village_bias_events": int(entry.get("stay_near_village_bias_events", 0)),
                "home_return_events": int(entry.get("home_return_events", 0)),
            }
        return {
            "global": {
                "return_to_village_events": int(stats.get("return_to_village_events", 0)),
                "stay_near_village_bias_events": int(stats.get("stay_near_village_bias_events", 0)),
                "home_return_events": int(stats.get("home_return_events", 0)),
            },
            "by_village": dict(sorted(by_village.items(), key=lambda item: item[0])),
        }

    def record_social_encounter_event(self, key: str, count: int = 1) -> None:
        metric = str(key).strip()
        stats = self.social_encounter_stats if isinstance(self.social_encounter_stats, dict) else _default_social_encounter_stats()
        if metric not in stats:
            return
        stats[metric] = int(stats.get(metric, 0)) + max(0, int(count))
        self.social_encounter_stats = stats

    def compute_social_encounter_snapshot(self) -> Dict[str, int]:
        stats = self.social_encounter_stats if isinstance(self.social_encounter_stats, dict) else _default_social_encounter_stats()
        out = _default_social_encounter_stats()
        for k in out.keys():
            out[k] = int(stats.get(k, 0))
        return out

    def record_resident_conversion_attempt(self, *, village_uid: Optional[str] = None) -> None:
        stats = self.residence_stabilization_stats
        if not isinstance(stats, dict):
            stats = _default_residence_stabilization_stats()
            self.residence_stabilization_stats = stats
        stats["resident_conversion_attempt_count"] = int(stats.get("resident_conversion_attempt_count", 0)) + 1
        uid = str(village_uid or "")
        if uid:
            by_village = stats.setdefault("by_village", {})
            entry = by_village.get(uid)
            if not isinstance(entry, dict):
                entry = {
                    "resident_conversion_attempt_count": 0,
                    "resident_conversion_count": 0,
                    "resident_persistence_count": 0,
                    "resident_release_count": 0,
                    "resident_release_reasons": {},
                }
                by_village[uid] = entry
            entry["resident_conversion_attempt_count"] = int(entry.get("resident_conversion_attempt_count", 0)) + 1

    def record_resident_conversion(self, *, village_uid: Optional[str] = None) -> None:
        stats = self.residence_stabilization_stats
        if not isinstance(stats, dict):
            stats = _default_residence_stabilization_stats()
            self.residence_stabilization_stats = stats
        stats["resident_conversion_count"] = int(stats.get("resident_conversion_count", 0)) + 1
        uid = str(village_uid or "")
        if uid:
            by_village = stats.setdefault("by_village", {})
            entry = by_village.get(uid)
            if not isinstance(entry, dict):
                entry = {
                    "resident_conversion_attempt_count": 0,
                    "resident_conversion_count": 0,
                    "resident_persistence_count": 0,
                    "resident_release_count": 0,
                    "resident_release_reasons": {},
                }
                by_village[uid] = entry
            entry["resident_conversion_count"] = int(entry.get("resident_conversion_count", 0)) + 1

    def record_resident_persistence(self, *, village_uid: Optional[str] = None) -> None:
        stats = self.residence_stabilization_stats
        if not isinstance(stats, dict):
            stats = _default_residence_stabilization_stats()
            self.residence_stabilization_stats = stats
        stats["resident_persistence_count"] = int(stats.get("resident_persistence_count", 0)) + 1
        uid = str(village_uid or "")
        if uid:
            by_village = stats.setdefault("by_village", {})
            entry = by_village.get(uid)
            if not isinstance(entry, dict):
                entry = {
                    "resident_conversion_attempt_count": 0,
                    "resident_conversion_count": 0,
                    "resident_persistence_count": 0,
                    "resident_release_count": 0,
                    "resident_release_reasons": {},
                }
                by_village[uid] = entry
            entry["resident_persistence_count"] = int(entry.get("resident_persistence_count", 0)) + 1

    def record_resident_release(self, reason: str, *, village_uid: Optional[str] = None) -> None:
        stats = self.residence_stabilization_stats
        if not isinstance(stats, dict):
            stats = _default_residence_stabilization_stats()
            self.residence_stabilization_stats = stats
        key = str(reason).strip().lower() or "unknown_release"
        stats["resident_release_count"] = int(stats.get("resident_release_count", 0)) + 1
        reasons = stats.setdefault("resident_release_reasons", {})
        reasons[key] = int(reasons.get(key, 0)) + 1
        uid = str(village_uid or "")
        if uid:
            by_village = stats.setdefault("by_village", {})
            entry = by_village.get(uid)
            if not isinstance(entry, dict):
                entry = {
                    "resident_conversion_attempt_count": 0,
                    "resident_conversion_count": 0,
                    "resident_persistence_count": 0,
                    "resident_release_count": 0,
                    "resident_release_reasons": {},
                }
                by_village[uid] = entry
            entry["resident_release_count"] = int(entry.get("resident_release_count", 0)) + 1
            vreasons = entry.setdefault("resident_release_reasons", {})
            vreasons[key] = int(vreasons.get(key, 0)) + 1

    def compute_residence_stabilization_snapshot(self) -> Dict[str, Any]:
        stats = self.residence_stabilization_stats if isinstance(self.residence_stabilization_stats, dict) else _default_residence_stabilization_stats()
        attempts = int(stats.get("resident_conversion_attempt_count", 0))
        success = int(stats.get("resident_conversion_count", 0))
        by_village: Dict[str, Dict[str, Any]] = {}
        for uid, entry in (stats.get("by_village", {}) or {}).items():
            if not isinstance(entry, dict):
                continue
            v_attempts = int(entry.get("resident_conversion_attempt_count", 0))
            v_success = int(entry.get("resident_conversion_count", 0))
            by_village[str(uid)] = {
                "resident_conversion_attempt_count": v_attempts,
                "resident_conversion_count": v_success,
                "resident_persistence_count": int(entry.get("resident_persistence_count", 0)),
                "resident_release_count": int(entry.get("resident_release_count", 0)),
                "resident_release_reasons": {
                    str(k): int(v) for k, v in ((entry.get("resident_release_reasons", {}) or {}).items())
                },
                "attached_to_resident_success_rate": round(float(v_success) / float(v_attempts), 3) if v_attempts > 0 else 0.0,
            }
        return {
            "global": {
                "resident_conversion_attempt_count": attempts,
                "resident_conversion_count": success,
                "resident_persistence_count": int(stats.get("resident_persistence_count", 0)),
                "resident_release_count": int(stats.get("resident_release_count", 0)),
                "resident_release_reasons": {
                    str(k): int(v) for k, v in ((stats.get("resident_release_reasons", {}) or {}).items())
                },
                "attached_to_resident_success_rate": round(float(success) / float(attempts), 3) if attempts > 0 else 0.0,
            },
            "by_village": dict(sorted(by_village.items(), key=lambda item: item[0])),
        }

    def _resident_conversion_gate_entry(self, village_uid: Optional[str] = None) -> Dict[str, Any]:
        stats = self.resident_conversion_gate_stats
        if not isinstance(stats, dict):
            stats = _default_resident_conversion_gate_stats()
            self.resident_conversion_gate_stats = stats
        uid = str(village_uid or "")
        if uid:
            by_village = stats.setdefault("by_village", {})
            entry = by_village.get(uid)
            if not isinstance(entry, dict):
                entry = _empty_resident_conversion_gate_metrics()
                by_village[uid] = entry
            return entry
        entry = stats.get("global")
        if not isinstance(entry, dict):
            entry = _empty_resident_conversion_gate_metrics()
            stats["global"] = entry
        return entry

    def record_resident_conversion_gate_stage(self, stage: str, *, village_uid: Optional[str] = None) -> None:
        key = str(stage).strip()
        if key not in RESIDENT_CONVERSION_GATE_STAGES:
            return
        entry_global = self._resident_conversion_gate_entry(None)
        entry_global[key] = int(entry_global.get(key, 0)) + 1
        if key == "resident_conversion_granted":
            entry_global["conversion_success_count"] = int(entry_global.get("conversion_success_count", 0)) + 1
        uid = str(village_uid or "")
        if uid:
            entry_village = self._resident_conversion_gate_entry(uid)
            entry_village[key] = int(entry_village.get(key, 0)) + 1
            if key == "resident_conversion_granted":
                entry_village["conversion_success_count"] = int(entry_village.get("conversion_success_count", 0)) + 1

    def record_resident_conversion_gate_failure(self, reason: str, *, village_uid: Optional[str] = None) -> None:
        key = str(reason).strip()
        if key not in RESIDENT_CONVERSION_GATE_FAILURE_REASONS:
            key = "eligibility_failed_other_guard"
        entry_global = self._resident_conversion_gate_entry(None)
        g_reasons = entry_global.setdefault("failure_reasons", {})
        g_reasons[key] = int(g_reasons.get(key, 0)) + 1
        uid = str(village_uid or "")
        if uid:
            entry_village = self._resident_conversion_gate_entry(uid)
            v_reasons = entry_village.setdefault("failure_reasons", {})
            v_reasons[key] = int(v_reasons.get(key, 0)) + 1

    def compute_resident_conversion_gate_snapshot(self) -> Dict[str, Any]:
        stats = self.resident_conversion_gate_stats if isinstance(self.resident_conversion_gate_stats, dict) else _default_resident_conversion_gate_stats()

        def _copy(src: Dict[str, Any]) -> Dict[str, Any]:
            out = _empty_resident_conversion_gate_metrics()
            for stage in RESIDENT_CONVERSION_GATE_STAGES:
                out[stage] = int(src.get(stage, 0))
            out["failure_reasons"] = {
                str(k): int(v) for k, v in ((src.get("failure_reasons", {}) or {}).items())
            }
            out["conversion_success_count"] = int(src.get("conversion_success_count", 0))
            return out

        global_out = _copy(stats.get("global", {}) if isinstance(stats.get("global", {}), dict) else {})
        by_village: Dict[str, Dict[str, Any]] = {}
        for uid, entry in (stats.get("by_village", {}) or {}).items():
            if not isinstance(entry, dict):
                continue
            by_village[str(uid)] = _copy(entry)
        return {
            "global": global_out,
            "by_village": dict(sorted(by_village.items(), key=lambda item: item[0])),
        }

    def _recovery_bucket(self, stats: Dict[str, Any], key: str, label: str) -> Dict[str, Any]:
        bucket_map = stats.setdefault(key, {})
        bucket = bucket_map.get(label)
        if not isinstance(bucket, dict):
            bucket = _empty_recovery_diagnostic_metrics()
            bucket_map[label] = bucket
        return bucket

    def _iter_recovery_buckets(self, role: str, village_uid: Optional[str]) -> List[Dict[str, Any]]:
        stats = self.recovery_diagnostic_stats
        if not isinstance(stats, dict):
            stats = _default_recovery_diagnostic_stats()
            self.recovery_diagnostic_stats = stats
        role_key = role if role in RECOVERY_DIAGNOSTIC_ROLES else "other"
        buckets = [stats.setdefault("global", _empty_recovery_diagnostic_metrics())]
        buckets.append(self._recovery_bucket(stats, "by_role", role_key))
        uid = str(village_uid or "")
        if uid:
            buckets.append(self._recovery_bucket(stats, "by_village", uid))
        return buckets

    def record_recovery_stage(self, agent: Agent, stage: str, *, village_uid: Optional[str] = None, role: Optional[str] = None) -> None:
        key = str(stage).strip()
        if key not in RECOVERY_FUNNEL_STAGES:
            return
        uid = str(village_uid or self._resolve_agent_work_village_uid(agent) or "")
        role_key = str(role or getattr(agent, "role", "other") or "other")
        for bucket in self._iter_recovery_buckets(role_key, uid):
            bucket[key] = int(bucket.get(key, 0)) + 1

    def record_recovery_failure_reason(self, agent: Agent, reason: str, *, village_uid: Optional[str] = None, role: Optional[str] = None) -> None:
        key = str(reason).strip()
        if key not in RECOVERY_FAILURE_REASONS:
            key = "unknown_failure"
        uid = str(village_uid or self._resolve_agent_work_village_uid(agent) or "")
        role_key = str(role or getattr(agent, "role", "other") or "other")
        for bucket in self._iter_recovery_buckets(role_key, uid):
            reasons = bucket.setdefault("failure_reasons", {})
            reasons[key] = int(reasons.get(key, 0)) + 1

    def record_recovery_home_context(
        self,
        agent: Agent,
        *,
        valid_home: bool = False,
        high_pressure_with_valid_home: bool = False,
        home_possible_not_chosen: bool = False,
        village_uid: Optional[str] = None,
        role: Optional[str] = None,
    ) -> None:
        uid = str(village_uid or self._resolve_agent_work_village_uid(agent) or "")
        role_key = str(role or getattr(agent, "role", "other") or "other")
        for bucket in self._iter_recovery_buckets(role_key, uid):
            if bool(valid_home):
                bucket["agents_with_valid_home"] = int(bucket.get("agents_with_valid_home", 0)) + 1
            if bool(high_pressure_with_valid_home):
                bucket["high_pressure_with_valid_home"] = int(bucket.get("high_pressure_with_valid_home", 0)) + 1
            if bool(home_possible_not_chosen):
                bucket["home_recovery_possible_not_chosen"] = int(bucket.get("home_recovery_possible_not_chosen", 0)) + 1

    def compute_recovery_diagnostics_snapshot(self) -> Dict[str, Any]:
        stats = self.recovery_diagnostic_stats if isinstance(self.recovery_diagnostic_stats, dict) else _default_recovery_diagnostic_stats()

        def _copy(src: Dict[str, Any]) -> Dict[str, Any]:
            out = _empty_recovery_diagnostic_metrics()
            for stage in RECOVERY_FUNNEL_STAGES:
                out[stage] = int(src.get(stage, 0))
            out["failure_reasons"] = {
                str(k): int(v) for k, v in ((src.get("failure_reasons", {}) or {}).items())
            }
            out["agents_with_valid_home"] = int(src.get("agents_with_valid_home", 0))
            out["high_pressure_with_valid_home"] = int(src.get("high_pressure_with_valid_home", 0))
            out["home_recovery_possible_not_chosen"] = int(src.get("home_recovery_possible_not_chosen", 0))
            return out

        global_out = _copy(stats.get("global", {}) if isinstance(stats.get("global", {}), dict) else {})
        by_role = {
            str(k): _copy(v if isinstance(v, dict) else {})
            for k, v in (stats.get("by_role", {}) or {}).items()
        }
        by_village = {
            str(k): _copy(v if isinstance(v, dict) else {})
            for k, v in (stats.get("by_village", {}) or {}).items()
        }
        return {
            "global": global_out,
            "by_role": dict(sorted(by_role.items(), key=lambda item: item[0])),
            "by_village": dict(sorted(by_village.items(), key=lambda item: item[0])),
        }

    def compute_task_completion_snapshot(self) -> Dict[str, Any]:
        stats = self.workforce_realization_stats if isinstance(self.workforce_realization_stats, dict) else _default_workforce_realization_stats()
        by_task = stats.get("task_completion_stage_counts_by_task", {})
        by_task_village = stats.get("task_completion_stage_counts_by_task_by_village", {})
        reasons = stats.get("task_completion_failure_reasons_by_task", {})
        reasons_village = stats.get("task_completion_failure_reasons_by_task_by_village", {})
        by_aff = stats.get("task_completion_stage_counts_by_affiliation", {})
        by_aff_village = stats.get("task_completion_stage_counts_by_affiliation_by_village", {})

        global_out = {task: _empty_task_completion_task_metrics() for task in TASK_COMPLETION_KEYS}
        for task in TASK_COMPLETION_KEYS:
            task_counts = (by_task or {}).get(task, {})
            for stage in TASK_COMPLETION_STAGES:
                global_out[task][stage] = int((task_counts or {}).get(stage, 0))
            global_out[task]["failure_reasons"] = {
                str(k): int(v) for k, v in (((reasons or {}).get(task, {}) or {}).items())
            }

        by_village_out: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for village in self.villages:
            uid = str(village.get("village_uid", ""))
            if not uid:
                continue
            by_village_out[uid] = {task: _empty_task_completion_task_metrics() for task in TASK_COMPLETION_KEYS}
            vcounts = (by_task_village or {}).get(uid, {})
            vreasons = (reasons_village or {}).get(uid, {})
            for task in TASK_COMPLETION_KEYS:
                for stage in TASK_COMPLETION_STAGES:
                    by_village_out[uid][task][stage] = int(((vcounts or {}).get(task, {}) or {}).get(stage, 0))
                by_village_out[uid][task]["failure_reasons"] = {
                    str(k): int(v) for k, v in ((((vreasons or {}).get(task, {}) or {}).items()))
                }

        by_aff_out = {
            status: {
                "preconditions_failed_count": int(((by_aff or {}).get(status, {}) or {}).get("preconditions_failed_count", 0)),
                "productive_completion_count": int(((by_aff or {}).get(status, {}) or {}).get("productive_completion_count", 0)),
            }
            for status in WORKFORCE_AFFILIATION_CLASSES
        }
        by_aff_village_out: Dict[str, Dict[str, Dict[str, int]]] = {}
        for uid, entry in (by_aff_village or {}).items():
            by_aff_village_out[str(uid)] = {
                status: {
                    "preconditions_failed_count": int(((entry or {}).get(status, {}) or {}).get("preconditions_failed_count", 0)),
                    "productive_completion_count": int(((entry or {}).get(status, {}) or {}).get("productive_completion_count", 0)),
                }
                for status in WORKFORCE_AFFILIATION_CLASSES
            }

        return {
            "global": global_out,
            "by_village": by_village_out,
            "by_affiliation": {
                "global": by_aff_out,
                "by_village": by_aff_village_out,
            },
        }

    def compute_assignment_to_action_gap_snapshot(self) -> Dict[str, Any]:
        roles = WORKFORCE_REALIZATION_ROLES
        global_counts = {role: _empty_assignment_gap_role_metrics() for role in roles}
        by_village: Dict[str, Dict[str, Dict[str, Any]]] = {}
        by_affiliation = {
            status: {
                "assigned_role_count": 0,
                "task_selected_count": 0,
                "productive_action_count": 0,
                "abandoned_or_overridden_count": 0,
            }
            for status in WORKFORCE_AFFILIATION_CLASSES
        }

        stats = self.workforce_realization_stats if isinstance(self.workforce_realization_stats, dict) else _default_workforce_realization_stats()
        by_role = stats.get("assignment_gap_stage_counts_by_role", {})
        by_role_village = stats.get("assignment_gap_stage_counts_by_role_by_village", {})
        by_aff = stats.get("assignment_gap_stage_counts_by_affiliation", {})
        by_role_reasons = stats.get("assignment_gap_block_reasons_by_role", {})
        by_role_reasons_village = stats.get("assignment_gap_block_reasons_by_role_by_village", {})

        for role in roles:
            role_counts = (by_role or {}).get(role, {})
            for stage in ASSIGNMENT_GAP_STAGES:
                if stage == "assigned_role_count":
                    continue
                global_counts[role][stage] = int((role_counts or {}).get(stage, 0))
            global_counts[role]["block_reasons"] = {
                str(k): int(v) for k, v in (((by_role_reasons or {}).get(role, {}) or {}).items())
            }

        for village in self.villages:
            uid = str(village.get("village_uid", ""))
            if not uid:
                continue
            by_village[uid] = {role: _empty_assignment_gap_role_metrics() for role in roles}
            vcounts = (by_role_village or {}).get(uid, {})
            vreasons = (by_role_reasons_village or {}).get(uid, {})
            for role in roles:
                for stage in ASSIGNMENT_GAP_STAGES:
                    if stage == "assigned_role_count":
                        continue
                    by_village[uid][role][stage] = int(((vcounts or {}).get(role, {}) or {}).get(stage, 0))
                by_village[uid][role]["block_reasons"] = {
                    str(k): int(v) for k, v in ((((vreasons or {}).get(role, {}) or {}).items()))
                }

        for agent in self.agents:
            if not getattr(agent, "alive", False) or bool(getattr(agent, "is_player", False)):
                continue
            role = str(getattr(agent, "role", "npc"))
            if role not in roles:
                continue
            uid = self._resolve_agent_work_village_uid(agent)
            if uid and uid not in by_village:
                by_village[uid] = {r: _empty_assignment_gap_role_metrics() for r in roles}
            aff = self._workforce_affiliation_for_village(agent, uid) if uid else "unaffiliated"
            global_counts[role]["assigned_role_count"] += 1
            if uid:
                by_village[uid][role]["assigned_role_count"] += 1
            by_affiliation[aff]["assigned_role_count"] += 1

        for status in WORKFORCE_AFFILIATION_CLASSES:
            sc = (by_aff or {}).get(status, {})
            by_affiliation[status]["task_selected_count"] = int((sc or {}).get("task_selected_count", 0))
            by_affiliation[status]["productive_action_count"] = int((sc or {}).get("productive_action_count", 0))
            by_affiliation[status]["abandoned_or_overridden_count"] = int((sc or {}).get("abandoned_or_overridden_count", 0))

        return {
            "global": global_counts,
            "by_village": by_village,
            "by_affiliation": by_affiliation,
        }

    def compute_workforce_realization_snapshot(self) -> Dict[str, Any]:
        role_task_map = {
            "farmer": {"farm_cycle"},
            "forager": {"gather_food_wild"},
            "hauler": {"food_logistics", "village_logistics"},
            "builder": {"build_storage", "build_house", "gather_materials"},
            "miner": {"mine_cycle"},
            "woodcutter": {"lumber_cycle"},
        }
        roles = WORKFORCE_REALIZATION_ROLES
        target_by_village: Dict[str, Dict[str, int]] = {}
        by_village: Dict[str, Dict[str, Dict[str, Any]]] = {}
        global_role: Dict[str, Dict[str, Any]] = {
            role: _empty_workforce_realization_role_metrics()
            for role in roles
        }
        affiliation_global = {
            status: {
                "assigned_count": 0,
                "active_task_count": 0,
                "productive_action_count": 0,
                "blocked_or_idle_count": 0,
            }
            for status in WORKFORCE_AFFILIATION_CLASSES
        }
        affiliation_by_village: Dict[str, Dict[str, Dict[str, int]]] = {}

        for village in self.villages:
            uid = str(village.get("village_uid", ""))
            if not uid:
                continue
            metrics = village.get("metrics", {}) if isinstance(village.get("metrics"), dict) else {}
            target = metrics.get("workforce_target_mix", {})
            if not isinstance(target, dict):
                target = {}
            target_by_village[uid] = {
                role: int(target.get(role, 0))
                for role in roles
            }
            by_village[uid] = {role: _empty_workforce_realization_role_metrics() for role in roles}
            affiliation_by_village[uid] = {
                status: {
                    "assigned_count": 0,
                    "active_task_count": 0,
                    "productive_action_count": 0,
                    "blocked_or_idle_count": 0,
                }
                for status in WORKFORCE_AFFILIATION_CLASSES
            }

        for uid, role_targets in target_by_village.items():
            for role in roles:
                t = int(role_targets.get(role, 0))
                by_village[uid][role]["target_count"] = t
                global_role[role]["target_count"] += t

        window = int(WORKFORCE_REALIZATION_PRODUCTIVE_WINDOW_TICKS)
        idle_grace = int(WORKFORCE_REALIZATION_IDLE_GRACE_TICKS)
        for agent in self.agents:
            if not getattr(agent, "alive", False) or bool(getattr(agent, "is_player", False)):
                continue
            role = str(getattr(agent, "role", "npc"))
            if role not in roles:
                continue
            uid = self._resolve_agent_work_village_uid(agent)
            if not uid:
                continue
            if uid not in by_village:
                by_village[uid] = {r: _empty_workforce_realization_role_metrics() for r in roles}
                affiliation_by_village[uid] = {
                    status: {
                        "assigned_count": 0,
                        "active_task_count": 0,
                        "productive_action_count": 0,
                        "blocked_or_idle_count": 0,
                    }
                    for status in WORKFORCE_AFFILIATION_CLASSES
                }
            affiliation = self._workforce_affiliation_for_village(agent, uid)

            by_village[uid][role]["assigned_count"] += 1
            global_role[role]["assigned_count"] += 1
            affiliation_by_village[uid][affiliation]["assigned_count"] += 1
            affiliation_global[affiliation]["assigned_count"] += 1

            task = str(getattr(agent, "task", ""))
            if task in role_task_map.get(role, set()):
                by_village[uid][role]["active_task_count"] += 1
                global_role[role]["active_task_count"] += 1
                affiliation_by_village[uid][affiliation]["active_task_count"] += 1
                affiliation_global[affiliation]["active_task_count"] += 1

            assigned_tick = int(getattr(agent, "workforce_role_assigned_tick", self.tick))
            last_prod_map = getattr(agent, "workforce_last_productive_tick_by_role", {})
            last_prod_tick = int(last_prod_map.get(role, -10**9)) if isinstance(last_prod_map, dict) else -10**9
            recent_productive = last_prod_tick >= int(self.tick) - window
            if not recent_productive and int(self.tick) - assigned_tick >= idle_grace:
                by_village[uid][role]["blocked_or_idle_count"] += 1
                global_role[role]["blocked_or_idle_count"] += 1
                affiliation_by_village[uid][affiliation]["blocked_or_idle_count"] += 1
                affiliation_global[affiliation]["blocked_or_idle_count"] += 1

        stats = self.workforce_realization_stats if isinstance(self.workforce_realization_stats, dict) else _default_workforce_realization_stats()
        productive_by_role = stats.get("productive_actions_by_role", {})
        productive_actions_by_role = stats.get("productive_actions_by_role_actions", {})
        blocks_by_role = stats.get("block_reasons_by_role", {})
        productive_by_village = stats.get("productive_actions_by_role_by_village", {})
        productive_actions_by_village = stats.get("productive_actions_by_role_actions_by_village", {})
        blocks_by_village = stats.get("block_reasons_by_role_by_village", {})

        for role in roles:
            global_role[role]["productive_action_count"] = int((productive_by_role or {}).get(role, 0))
            global_role[role]["productive_actions"] = {
                str(k): int(v) for k, v in (((productive_actions_by_role or {}).get(role, {}) or {}).items())
            }
            global_role[role]["block_reasons"] = {
                str(k): int(v) for k, v in (((blocks_by_role or {}).get(role, {}) or {}).items())
            }

        for uid, role_metrics in by_village.items():
            vprod = (productive_by_village or {}).get(uid, {})
            vprod_actions = (productive_actions_by_village or {}).get(uid, {})
            vblocks = (blocks_by_village or {}).get(uid, {})
            for role in roles:
                role_metrics[role]["productive_action_count"] = int((vprod or {}).get(role, 0))
                role_metrics[role]["productive_actions"] = {
                    str(k): int(v) for k, v in (((vprod_actions or {}).get(role, {}) or {}).items())
                }
                role_metrics[role]["block_reasons"] = {
                    str(k): int(v) for k, v in (((vblocks or {}).get(role, {}) or {}).items())
                }

        by_aff_role = stats.get("productive_actions_by_affiliation", {})
        by_aff_role_village = stats.get("productive_actions_by_affiliation_by_village", {})
        for role in roles:
            aff_map = (by_aff_role or {}).get(role, {})
            for status in WORKFORCE_AFFILIATION_CLASSES:
                affiliation_global[status]["productive_action_count"] += int((aff_map or {}).get(status, 0))
        for uid, by_status in affiliation_by_village.items():
            rv = (by_aff_role_village or {}).get(uid, {})
            for role in roles:
                aff_map = (rv or {}).get(role, {})
                for status in WORKFORCE_AFFILIATION_CLASSES:
                    by_status[status]["productive_action_count"] += int((aff_map or {}).get(status, 0))

        return {
            "window_ticks": int(window),
            "idle_grace_ticks": int(idle_grace),
            "global": global_role,
            "by_village": by_village,
            "affiliation_contribution": {
                "global": affiliation_global,
                "by_village": affiliation_by_village,
            },
        }

    def get_events_since(self, since_tick: int = -1) -> List[Dict]:
        cutoff = int(since_tick)
        return [e for e in self.events if int(e.get("tick", -1)) > cutoff]

    def set_agent_role(self, agent: Agent, new_role: str, reason: str = "") -> None:
        old_role = getattr(agent, "role", "npc")
        if old_role == new_role:
            agent.role = new_role
            if str(new_role) in WORKFORCE_REALIZATION_ROLES and getattr(agent, "workforce_role_assigned_tick", None) is None:
                agent.workforce_role_assigned_tick = int(self.tick)
            return
        agent.role = new_role
        if str(new_role) in WORKFORCE_REALIZATION_ROLES:
            agent.workforce_role_assigned_tick = int(self.tick)
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
        progression = self.settlement_progression_stats if isinstance(self.settlement_progression_stats, dict) else _default_settlement_progression_stats()
        progression["population_deaths_count"] = int(progression.get("population_deaths_count", 0)) + 1
        reason_key = str(reason or "unknown").strip().lower()
        if reason_key == "hunger":
            progression["population_deaths_hunger_count"] = int(progression.get("population_deaths_hunger_count", 0)) + 1
            reserve_available = int(self.current_total_food_in_reserves()) > 0
            if reserve_available:
                progression["hunger_deaths_with_reserve_available"] = int(
                    progression.get("hunger_deaths_with_reserve_available", 0)
                ) + 1
            else:
                progression["hunger_deaths_without_reserve"] = int(
                    progression.get("hunger_deaths_without_reserve", 0)
                ) + 1
            first_food_relief_tick = int(getattr(agent, "first_food_relief_tick", -1))
            if first_food_relief_tick < 0:
                progression["hunger_deaths_before_first_food_acquisition"] = int(
                    progression.get("hunger_deaths_before_first_food_acquisition", 0)
                ) + 1
        elif reason_key in {"exhaustion", "fatigue", "sleep_failure"}:
            progression["population_deaths_exhaustion_count"] = int(progression.get("population_deaths_exhaustion_count", 0)) + 1
        else:
            progression["population_deaths_other_count"] = int(progression.get("population_deaths_other_count", 0)) + 1
        if int(progression.get("first_house_completion_tick", -1)) < 0:
            progression["deaths_before_first_house_completed"] = int(
                progression.get("deaths_before_first_house_completed", 0)
            ) + 1
        if int(progression.get("first_village_formalization_tick", -1)) < 0:
            progression["deaths_before_settlement_stability_threshold"] = int(
                progression.get("deaths_before_settlement_stability_threshold", 0)
            ) + 1
        born_tick = int(getattr(agent, "born_tick", int(getattr(self, "tick", 0))))
        age = max(0, int(getattr(self, "tick", 0)) - born_tick)
        if reason_key == "hunger":
            if age <= 199:
                progression["population_deaths_hunger_age_0_199_count"] = int(
                    progression.get("population_deaths_hunger_age_0_199_count", 0)
                ) + 1
            elif age <= 599:
                progression["population_deaths_hunger_age_200_599_count"] = int(
                    progression.get("population_deaths_hunger_age_200_599_count", 0)
                ) + 1
            else:
                progression["population_deaths_hunger_age_600_plus_count"] = int(
                    progression.get("population_deaths_hunger_age_600_plus_count", 0)
                ) + 1
        progression["_dead_agent_ages_sum"] = int(progression.get("_dead_agent_ages_sum", 0)) + int(age)
        progression["_dead_agent_ages_count"] = int(progression.get("_dead_agent_ages_count", 0)) + 1
        dead_ages = progression.get("_dead_agent_ages_sorted", [])
        if not isinstance(dead_ages, list):
            dead_ages = []
        dead_ages.append(int(age))
        progression["_dead_agent_ages_sorted"] = dead_ages
        self.settlement_progression_stats = progression
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
        setattr(agent, "born_tick", int(getattr(self, "tick", 0)))
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
        progression = self.settlement_progression_stats if isinstance(self.settlement_progression_stats, dict) else _default_settlement_progression_stats()
        if str(getattr(agent, "spawn_origin", "")).strip().lower() == "reproduction":
            progression["population_births_count"] = int(progression.get("population_births_count", 0)) + 1
        self.settlement_progression_stats = progression
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

    def _generate_food_rich_patches(self) -> None:
        self.food_rich_patches = []
        map_area = max(1, int(self.width) * int(self.height))
        scale = (float(map_area) / float(72 * 72)) ** 0.5
        target_count = int(round(4 * scale))
        target_count = max(int(FOOD_PATCH_MIN_COUNT), min(int(FOOD_PATCH_MAX_COUNT), target_count))
        min_radius = max(3, int(round(float(FOOD_PATCH_MIN_RADIUS) * scale)))
        max_radius = max(min_radius + 1, int(round(float(FOOD_PATCH_MAX_RADIUS) * scale)))
        attempts = max(200, target_count * 160)
        while len(self.food_rich_patches) < target_count and attempts > 0:
            attempts -= 1
            x = self._eco_rng.randint(0, self.width - 1)
            y = self._eco_rng.randint(0, self.height - 1)
            if str(self.tiles[y][x]) == "W":
                continue
            radius = self._eco_rng.randint(min_radius, max_radius)
            overlap = False
            for patch in self.food_rich_patches:
                px = int(patch.get("center_x", 0))
                py = int(patch.get("center_y", 0))
                pr = int(patch.get("radius", min_radius))
                if abs(px - x) + abs(py - y) < int((pr + radius) * 0.8):
                    overlap = True
                    break
            if overlap:
                continue
            self.food_rich_patches.append(
                {
                    "center_x": int(x),
                    "center_y": int(y),
                    "radius": int(radius),
                    "regen_multiplier": float(FOOD_PATCH_REGEN_MULTIPLIER),
                    "density_multiplier": float(FOOD_PATCH_DENSITY_MULTIPLIER),
                }
            )

    def _is_in_food_patch(self, x: int, y: int) -> bool:
        for patch in self.food_rich_patches:
            if not isinstance(patch, dict):
                continue
            px = int(patch.get("center_x", 0))
            py = int(patch.get("center_y", 0))
            pr = int(patch.get("radius", 0))
            if abs(int(x) - px) + abs(int(y) - py) <= pr:
                return True
        return False

    def _food_patch_index_for_pos(self, x: int, y: int) -> Optional[int]:
        best_idx: Optional[int] = None
        best_dist = 10**9
        for idx, patch in enumerate(self.food_rich_patches):
            if not isinstance(patch, dict):
                continue
            px = int(patch.get("center_x", 0))
            py = int(patch.get("center_y", 0))
            pr = int(patch.get("radius", 0))
            dist = abs(int(x) - px) + abs(int(y) - py)
            if dist <= pr and dist < best_dist:
                best_dist = dist
                best_idx = int(idx)
        return best_idx

    def _patch_activity_score_at(self, x: int, y: int) -> float:
        idx = self._food_patch_index_for_pos(x, y)
        if idx is None:
            return 0.0
        key = str(int(idx))
        return max(0.0, float((self.food_patch_activity or {}).get(key, 0.0)))

    def record_food_patch_activity(self, x: int, y: int, amount: float = 1.0) -> None:
        idx = self._food_patch_index_for_pos(int(x), int(y))
        if idx is None:
            return
        key = str(int(idx))
        activity = self.food_patch_activity if isinstance(self.food_patch_activity, dict) else {}
        current = max(0.0, float(activity.get(key, 0.0)))
        next_value = min(float(CLUSTER_PATCH_ACTIVITY_MAX), current + max(0.0, float(amount)))
        activity[key] = float(next_value)
        self.food_patch_activity = activity

    def _decay_food_patch_activity(self) -> None:
        activity = self.food_patch_activity if isinstance(self.food_patch_activity, dict) else {}
        if not activity:
            return
        next_activity: Dict[str, float] = {}
        for key, value in activity.items():
            v = float(value) * float(CLUSTER_PATCH_ACTIVITY_DECAY)
            if v >= 0.05:
                next_activity[str(key)] = float(v)
        self.food_patch_activity = next_activity

    def _count_food_near(self, x: int, y: int, *, radius: int = CLUSTER_PRODUCTIVITY_RADIUS) -> int:
        count = 0
        for fx, fy in self.food:
            if abs(int(fx) - int(x)) + abs(int(fy) - int(y)) <= int(radius):
                count += 1
        return int(count)

    def _count_alive_agents_near(self, x: int, y: int, *, radius: int) -> int:
        count = 0
        for agent in self.agents:
            if not getattr(agent, "alive", False):
                continue
            if abs(int(getattr(agent, "x", 0)) - int(x)) + abs(int(getattr(agent, "y", 0)) - int(y)) <= int(radius):
                count += 1
        return int(count)

    def _count_structures_near(self, x: int, y: int, *, radius: int = SECONDARY_NUCLEUS_STRUCTURE_RADIUS) -> int:
        count = 0
        for building in (self.buildings or {}).values():
            if not isinstance(building, dict):
                continue
            btype = str(building.get("type", ""))
            if btype not in {"house", "storage"}:
                continue
            state = str(building.get("operational_state", "active"))
            if state not in {"active", "under_construction"}:
                continue
            bx = int(building.get("x", 0))
            by = int(building.get("y", 0))
            if abs(bx - int(x)) + abs(by - int(y)) <= int(radius):
                count += 1
        return int(count)

    def _count_active_construction_sites_near(self, x: int, y: int, *, radius: int = SECONDARY_NUCLEUS_STRUCTURE_RADIUS) -> int:
        count = 0
        for building in (self.buildings or {}).values():
            if not isinstance(building, dict):
                continue
            if str(building.get("operational_state", "")) != "under_construction":
                continue
            if str(building.get("type", "")) not in {"house", "storage"}:
                continue
            bx = int(building.get("x", 0))
            by = int(building.get("y", 0))
            if abs(bx - int(x)) + abs(by - int(y)) <= int(radius):
                count += 1
        return int(count)

    def _nearest_active_camp_raw(self, x: int, y: int, *, max_distance: int = CAMP_ANCHOR_RADIUS) -> Optional[Dict[str, Any]]:
        best: Optional[Tuple[int, str, Dict[str, Any]]] = None
        for camp_id, camp in (self.camps or {}).items():
            if not isinstance(camp, dict) or not bool(camp.get("active", False)):
                continue
            cx = int(camp.get("x", 0))
            cy = int(camp.get("y", 0))
            dist = abs(int(x) - cx) + abs(int(y) - cy)
            if dist > int(max_distance):
                continue
            key = (int(dist), str(camp_id))
            if best is None or key < (best[0], best[1]):
                best = (int(dist), str(camp_id), camp)
        return best[2] if best is not None else None

    def secondary_nucleus_materialization_signals(self, x: int, y: int) -> Dict[str, Any]:
        camp = self._nearest_active_camp_raw(int(x), int(y), max_distance=SECONDARY_NUCLEUS_BUILD_GRAVITY_RADIUS)
        if not isinstance(camp, dict):
            return {
                "has_camp": False,
                "camp_id": "",
                "camp_pos": (int(x), int(y)),
                "nearby_agents": 0,
                "nearby_food_sources": 0,
                "ecological_productivity": 0.0,
                "structure_count": 0,
                "active_construction_sites": 0,
                "viable": False,
                "materializing": False,
            }
        cx, cy = int(camp.get("x", 0)), int(camp.get("y", 0))
        nearby_agents = int(camp.get("support_nearby_agents", 0))
        if nearby_agents <= 0:
            nearby_agents = self._count_alive_agents_near(cx, cy, radius=CAMP_ANCHOR_RADIUS)
        nearby_food_sources = self._count_food_near(cx, cy, radius=CLUSTER_PRODUCTIVITY_RADIUS)
        ecological_productivity = max(
            float(camp.get("ecological_productivity_score", 0.0)),
            float(nearby_food_sources),
            float(min(4.0, self._patch_activity_score_at(cx, cy) * 0.08)),
        )
        structure_count = self._count_structures_near(cx, cy, radius=SECONDARY_NUCLEUS_STRUCTURE_RADIUS)
        active_construction_sites = self._count_active_construction_sites_near(cx, cy, radius=SECONDARY_NUCLEUS_STRUCTURE_RADIUS)
        viable = bool(
            nearby_agents >= 2
            and (
                nearby_food_sources >= 1
                or ecological_productivity >= 2.0
                or int(camp.get("food_cache", 0)) > 0
            )
        )
        # House-first settlement materialization: one durable structure near a viable camp
        # should already count as a materializing nucleus.
        materializing = bool(viable and (active_construction_sites > 0 or structure_count >= 1))
        return {
            "has_camp": True,
            "camp_id": str(camp.get("camp_id", "")),
            "camp_pos": (int(cx), int(cy)),
            "nearby_agents": int(nearby_agents),
            "nearby_food_sources": int(nearby_food_sources),
            "ecological_productivity": float(round(ecological_productivity, 3)),
            "structure_count": int(structure_count),
            "active_construction_sites": int(active_construction_sites),
            "viable": bool(viable),
            "materializing": bool(materializing),
        }

    def secondary_nucleus_context_for_agent(self, agent: Agent, *, max_distance: int = CAMP_ANCHOR_RADIUS) -> Dict[str, Any]:
        signals = self.secondary_nucleus_materialization_signals(int(getattr(agent, "x", 0)), int(getattr(agent, "y", 0)))
        if not bool(signals.get("has_camp", False)):
            return dict(signals)
        camp_pos = signals.get("camp_pos", (int(getattr(agent, "x", 0)), int(getattr(agent, "y", 0))))
        dist_to_camp = abs(int(getattr(agent, "x", 0)) - int(camp_pos[0])) + abs(int(getattr(agent, "y", 0)) - int(camp_pos[1]))
        if dist_to_camp > int(max_distance):
            out = dict(signals)
            out["viable"] = False
            out["materializing"] = False
            return out
        out = dict(signals)
        out["distance_to_camp"] = int(dist_to_camp)
        return out

    def secondary_nucleus_build_position_bonus(self, agent: Agent, pos: Coord, building_type: str) -> int:
        if float(getattr(agent, "hunger", 100.0)) < 25.0:
            return 0
        if str(building_type) not in {"house", "storage"}:
            return 0
        context = self.secondary_nucleus_context_for_agent(agent, max_distance=SECONDARY_NUCLEUS_BUILD_GRAVITY_RADIUS + 2)
        if not bool(context.get("viable", False)):
            return 0
        camp_pos = context.get("camp_pos", (int(agent.x), int(agent.y)))
        dist = abs(int(pos[0]) - int(camp_pos[0])) + abs(int(pos[1]) - int(camp_pos[1]))
        base = max(0, int(SECONDARY_NUCLEUS_BUILD_GRAVITY_BONUS) - int(dist) * 2)
        nearby_structures = self._count_structures_near(int(pos[0]), int(pos[1]), radius=3)
        cohesion_bonus = min(int(SECONDARY_NUCLEUS_COHESION_BONUS_CAP), max(0, nearby_structures - 1) * 3)
        if abs(int(pos[0]) - int(camp_pos[0])) + abs(int(pos[1]) - int(camp_pos[1])) <= 4:
            cohesion_bonus += 2
        return int(max(-6, min(24, base + cohesion_bonus)))

    def secondary_nucleus_builder_continuity_bonus(self, agent: Agent, task_name: str, *, record_event: bool = False) -> int:
        if str(task_name) not in {"build_house", "build_storage", "gather_materials"}:
            return 0
        if float(getattr(agent, "hunger", 100.0)) < 25.0:
            return 0
        context = self.secondary_nucleus_context_for_agent(agent, max_distance=SECONDARY_NUCLEUS_BUILD_GRAVITY_RADIUS + 2)
        if not bool(context.get("materializing", False)):
            return 0
        bonus = int(SECONDARY_NUCLEUS_BUILDER_CONTINUITY_BONUS_TICKS)
        if int(context.get("active_construction_sites", 0)) > 1:
            bonus += 2
        if record_event and bonus > 0:
            self.record_settlement_bottleneck("secondary_nucleus_build_support_events")
        return int(bonus)

    def secondary_nucleus_delivery_priority(self, agent: Agent, site: Dict[str, Any], *, record_event: bool = False) -> int:
        if float(getattr(agent, "hunger", 100.0)) < 25.0:
            return 0
        if not isinstance(site, dict):
            return 0
        context = self.secondary_nucleus_context_for_agent(agent, max_distance=SECONDARY_NUCLEUS_BUILD_GRAVITY_RADIUS + 3)
        if (not bool(context.get("materializing", False))) or int(context.get("active_construction_sites", 0)) <= 0:
            return 0
        camp_pos = context.get("camp_pos", (int(agent.x), int(agent.y)))
        dist = abs(int(site.get("x", 0)) - int(camp_pos[0])) + abs(int(site.get("y", 0)) - int(camp_pos[1]))
        if dist > int(SECONDARY_NUCLEUS_BUILD_GRAVITY_RADIUS):
            return 0
        bonus = max(0, 12 - int(dist) * 2)
        if record_event and bonus > 0:
            self.record_settlement_bottleneck("secondary_nucleus_material_delivery_events")
        return int(bonus)

    def suggest_low_density_exploration_step(self, agent: Agent) -> Optional[Tuple[int, int]]:
        if float(getattr(agent, "hunger", 100.0)) < 30.0:
            return None
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        best: Optional[Tuple[float, int, int]] = None
        best_dxdy: Tuple[int, int] = (0, 0)
        for dx, dy in dirs:
            nx, ny = int(getattr(agent, "x", 0)) + dx, int(getattr(agent, "y", 0)) + dy
            if not self.is_walkable(nx, ny) or self.is_occupied(nx, ny):
                continue
            local_density = self._count_alive_agents_near(nx, ny, radius=4)
            if local_density > 3:
                continue
            nearby_food = self._count_food_near(nx, ny, radius=6)
            if nearby_food <= 0:
                continue
            zone_key = f"{int(nx)//6}:{int(ny)//6}"
            familiar_zones = getattr(agent, "familiar_activity_zones", {})
            zone_score = float(familiar_zones.get(zone_key, 0.0)) if isinstance(familiar_zones, dict) else 0.0
            if zone_score >= 1.2:
                continue
            patch_activity = self._patch_activity_score_at(nx, ny)
            score = float(nearby_food) * 0.9 + (2.0 - float(local_density)) * 0.7 + min(2.5, patch_activity * 0.06)
            key = (score, -local_density, nearby_food)
            if best is None or key > (best[0], best[1], best[2]):
                best = (float(score), int(-local_density), int(nearby_food))
                best_dxdy = (int(dx), int(dy))
        if best is None:
            return None
        self.record_settlement_bottleneck("exploration_shift_due_to_low_density")
        return best_dxdy

    def _spawn_food_in_patch_once(self) -> bool:
        if not self.food_rich_patches:
            return False
        patch = self._eco_rng.choice(self.food_rich_patches)
        if not isinstance(patch, dict):
            return False
        cx = int(patch.get("center_x", 0))
        cy = int(patch.get("center_y", 0))
        radius = max(1, int(patch.get("radius", 1)))
        for _ in range(24):
            dx = self._eco_rng.randint(-radius, radius)
            dy = self._eco_rng.randint(-radius, radius)
            if abs(dx) + abs(dy) > radius:
                continue
            x = cx + dx
            y = cy + dy
            if not (0 <= x < self.width and 0 <= y < self.height):
                continue
            if str(self.tiles[y][x]) != "G":
                continue
            if (x, y) in self.food:
                continue
            if self.is_occupied(x, y):
                continue
            self.food.add((x, y))
            self.food_patch_food_spawned = int(self.food_patch_food_spawned) + 1
            return True
        return False

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
        # Additive ecological boost: food-rich patches start denser than the baseline world.
        extra_food = int(round(float(n) * float(FOOD_PATCH_EXTRA_INITIAL_FOOD_RATIO)))
        spawned = 0
        while spawned < extra_food and len(self.food) < int(self.MAX_FOOD):
            if not self._spawn_food_in_patch_once():
                break
            spawned += 1

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
            food_added = 0
            for _ in range(FOOD_RESPAWN_PER_TICK):
                # preferisci ancora pianure libere
                placed = False
                for _ in range(40):
                    x = random.randint(0, self.width - 1)
                    y = random.randint(0, self.height - 1)
                    if self.tiles[y][x] == "G" and (x, y) not in self.food and not self.is_occupied(x, y):
                        self.food.add((x, y))
                        food_added += 1
                        placed = True
                        break

                if not placed:
                    pos = self.find_random_free()
                    if pos:
                        if pos not in self.food:
                            self.food.add(pos)
                            food_added += 1
            # Ecological variation: patches regenerate food faster than the global baseline.
            extra_factor = float(FOOD_RESPAWN_PER_TICK) * max(0.0, float(FOOD_PATCH_REGEN_MULTIPLIER) - 1.0)
            patch_extra = int(extra_factor)
            fractional = max(0.0, extra_factor - float(patch_extra))
            if self._eco_rng.random() < fractional:
                patch_extra += 1
            for _ in range(max(0, patch_extra)):
                if len(self.food) >= MAX_FOOD:
                    break
                before = len(self.food)
                self._spawn_food_in_patch_once()
                if len(self.food) > before:
                    food_added += 1
            if food_added > 0:
                stats = self.resource_respawn_stats if isinstance(self.resource_respawn_stats, dict) else _default_resource_respawn_stats()
                stats["food_respawned_total"] = int(stats.get("food_respawned_total", 0)) + int(food_added)
                self.resource_respawn_stats = stats

        if len(self.wood) < MAX_WOOD:
            wood_added = 0
            for _ in range(WOOD_RESPAWN_PER_TICK):
                for _ in range(80):
                    x = random.randint(0, self.width - 1)
                    y = random.randint(0, self.height - 1)
                    if self.tiles[y][x] == "F":
                        before = len(self.wood)
                        self.wood.add((x, y))
                        if len(self.wood) > before:
                            wood_added += 1
                        break
            if wood_added > 0:
                stats = self.resource_respawn_stats if isinstance(self.resource_respawn_stats, dict) else _default_resource_respawn_stats()
                stats["wood_respawned_total"] = int(stats.get("wood_respawned_total", 0)) + int(wood_added)
                self.resource_respawn_stats = stats

        if len(self.stone) < MAX_STONE:
            stone_added = 0
            for _ in range(STONE_RESPAWN_PER_TICK):
                for _ in range(80):
                    x = random.randint(0, self.width - 1)
                    y = random.randint(0, self.height - 1)
                    if self.tiles[y][x] == "M":
                        before = len(self.stone)
                        self.stone.add((x, y))
                        if len(self.stone) > before:
                            stone_added += 1
                        break
            if stone_added > 0:
                stats = self.resource_respawn_stats if isinstance(self.resource_respawn_stats, dict) else _default_resource_respawn_stats()
                stats["stone_respawned_total"] = int(stats.get("stone_respawned_total", 0)) + int(stone_added)
                self.resource_respawn_stats = stats

    def autopickup(self, agent: Agent):
        pos = (agent.x, agent.y)
        village = self.get_village_by_id(getattr(agent, "village_id", None))

        if pos in self.food:
            hunger_before = float(getattr(agent, "hunger", 100.0))
            self.food.remove(pos)
            if hasattr(self, "record_settlement_progression_metric"):
                self.record_settlement_progression_metric("food_source_depletion_events")
                self.record_settlement_progression_metric("food_harvest_ticks_total")
            if bool(getattr(agent, "foraging_trip_active", False)):
                first_harvest_tick = int(getattr(agent, "foraging_trip_first_harvest_tick", -1))
                if first_harvest_tick < 0:
                    move_ticks_before = int(getattr(agent, "foraging_trip_move_ticks", 0))
                    if hasattr(self, "record_settlement_progression_metric"):
                        self.record_settlement_progression_metric("foraging_trip_move_before_first_harvest_total", move_ticks_before)
                        self.record_settlement_progression_metric("foraging_trip_move_before_first_harvest_samples")
                    setattr(agent, "foraging_trip_first_harvest_tick", int(getattr(self, "tick", 0)))
                    regime = str(getattr(agent, "foraging_pressure_regime", "medium"))
                    exploit_ticks = 0
                    exploit_harvest_actions = 0
                    if regime == "high":
                        exploit_ticks = 18
                        exploit_harvest_actions = 5
                    elif regime == "medium":
                        exploit_ticks = 12
                        exploit_harvest_actions = 4
                    elif regime == "low":
                        exploit_ticks = 6
                        exploit_harvest_actions = 2
                    if exploit_ticks > 0 and exploit_harvest_actions > 0:
                        setattr(agent, "foraging_patch_exploit_until_tick", int(getattr(self, "tick", 0)) + int(exploit_ticks))
                        setattr(agent, "foraging_patch_exploit_target_harvest_actions", int(exploit_harvest_actions))
                        setattr(agent, "foraging_patch_exploit_anchor", (int(agent.x), int(agent.y)))
            if agent.inventory_space() > 0:
                agent.inventory["food"] = agent.inventory.get("food", 0) + 1
                self.record_agent_food_inventory_acquired(agent, amount=1, source="wild_direct")
            if bool(getattr(agent, "foraging_trip_active", False)):
                setattr(agent, "foraging_trip_harvest_units", int(getattr(agent, "foraging_trip_harvest_units", 0)) + 1)
                setattr(agent, "foraging_trip_harvest_actions", int(getattr(agent, "foraging_trip_harvest_actions", 0)) + 1)
                last_pos = getattr(agent, "foraging_trip_last_harvest_pos", None)
                current_pos = (int(agent.x), int(agent.y))
                if isinstance(last_pos, tuple) and len(last_pos) == 2 and (int(last_pos[0]), int(last_pos[1])) == current_pos:
                    streak = int(getattr(agent, "foraging_trip_current_consecutive_harvest_actions", 0)) + 1
                else:
                    streak = 1
                setattr(agent, "foraging_trip_last_harvest_pos", current_pos)
                setattr(agent, "foraging_trip_current_consecutive_harvest_actions", int(streak))
                setattr(
                    agent,
                    "foraging_trip_max_consecutive_harvest_actions",
                    max(int(getattr(agent, "foraging_trip_max_consecutive_harvest_actions", 0)), int(streak)),
                )
                if int(getattr(agent, "foraging_patch_exploit_target_harvest_actions", 0)) > 0:
                    current_tick = int(getattr(self, "tick", 0))
                    current_until = int(getattr(agent, "foraging_patch_exploit_until_tick", -1))
                    setattr(agent, "foraging_patch_exploit_until_tick", max(current_until, current_tick + 4))
            bonus_food = 0
            if str(getattr(agent, "task", "")) == "gather_food_wild" and self._is_in_food_patch(int(agent.x), int(agent.y)):
                nearby_foragers = 0
                for other in self.agents:
                    if not getattr(other, "alive", False):
                        continue
                    if str(getattr(other, "agent_id", "")) == str(getattr(agent, "agent_id", "")):
                        continue
                    if str(getattr(other, "task", "")) not in {"gather_food_wild", "farm_cycle"}:
                        continue
                    if abs(int(getattr(other, "x", 0)) - int(agent.x)) + abs(int(getattr(other, "y", 0)) - int(agent.y)) <= 2:
                        nearby_foragers += 1
                if nearby_foragers <= 1 and random.random() < 0.10:
                    bonus_food = 1
            if bonus_food > 0 and int(getattr(agent, "inventory_space", lambda: 0)()) > 0:
                agent.inventory["food"] = int(agent.inventory.get("food", 0)) + int(bonus_food)
                self.record_agent_food_inventory_acquired(agent, amount=int(bonus_food), source="wild_bonus")
                if bool(getattr(agent, "foraging_trip_active", False)):
                    setattr(
                        agent,
                        "foraging_trip_harvest_units",
                        int(getattr(agent, "foraging_trip_harvest_units", 0)) + int(bonus_food),
                    )
                    setattr(
                        agent,
                        "foraging_trip_harvest_actions",
                        int(getattr(agent, "foraging_trip_harvest_actions", 0)) + 1,
                    )
                    last_pos = getattr(agent, "foraging_trip_last_harvest_pos", None)
                    current_pos = (int(agent.x), int(agent.y))
                    if isinstance(last_pos, tuple) and len(last_pos) == 2 and (int(last_pos[0]), int(last_pos[1])) == current_pos:
                        streak = int(getattr(agent, "foraging_trip_current_consecutive_harvest_actions", 0)) + 1
                    else:
                        streak = 1
                    setattr(agent, "foraging_trip_last_harvest_pos", current_pos)
                    setattr(agent, "foraging_trip_current_consecutive_harvest_actions", int(streak))
                    setattr(
                        agent,
                        "foraging_trip_max_consecutive_harvest_actions",
                        max(int(getattr(agent, "foraging_trip_max_consecutive_harvest_actions", 0)), int(streak)),
                    )
                    if int(getattr(agent, "foraging_patch_exploit_target_harvest_actions", 0)) > 0:
                        current_tick = int(getattr(self, "tick", 0))
                        current_until = int(getattr(agent, "foraging_patch_exploit_until_tick", -1))
                        setattr(agent, "foraging_patch_exploit_until_tick", max(current_until, current_tick + 4))
                if hasattr(self, "record_settlement_progression_metric"):
                    self.record_settlement_progression_metric("foraging_bonus_yield_units_total", int(bonus_food))
            agent.hunger += FOOD_EAT_GAIN
            if agent.hunger > 100:
                agent.hunger = 100
            self.record_food_consumption("wild_direct", amount=1, agent=agent)
            self.record_food_patch_activity(agent.x, agent.y, amount=1.6)
            if hasattr(self, "record_farm_discovery_observation"):
                self.record_farm_discovery_observation(int(agent.x), int(agent.y), success=True, amount=1)
            if hasattr(self, "farm_discovery_snapshot"):
                snap = self.farm_discovery_snapshot(int(agent.x), int(agent.y))
                repeat_count = int(snap.get("repeat_count", 0)) if isinstance(snap, dict) else 0
                if repeat_count >= 2 and hasattr(self, "record_local_practice"):
                    self.record_local_practice("productive_food_patch", x=int(agent.x), y=int(agent.y), weight=0.9, decay_rate=0.006)
                    self.record_local_practice("good_gathering_zone", x=int(agent.x), y=int(agent.y), weight=0.6, decay_rate=0.007)
            self.try_deposit_food_to_local_buffers(agent, amount=1, hunger_before=hunger_before)
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
            if str(getattr(agent, "role", "")) == "forager":
                self.record_workforce_productive_action(agent, "forager", "direct_food_gather")

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
            if str(getattr(agent, "role", "")) == "woodcutter":
                self.record_workforce_productive_action(agent, "woodcutter", "wood_gather")
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
            if str(getattr(agent, "role", "")) == "miner":
                self.record_workforce_productive_action(agent, "miner", "stone_gather")
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

    def record_farm_discovery_observation(self, x: int, y: int, *, success: bool, amount: int = 1) -> None:
        farming_system.record_food_site_observation(self, int(x), int(y), success=bool(success), amount=int(amount))

    def farm_site_productivity_score(self, x: int, y: int) -> float:
        return float(farming_system.farm_site_productivity_score(self, int(x), int(y)))

    def farm_discovery_snapshot(self, x: int, y: int) -> Dict[str, Any]:
        return dict(farming_system.farm_discovery_snapshot(self, int(x), int(y)))

    def work_farm(self, agent: Agent):
        return farming_system.work_farm(self, agent)

    def haul_harvest(self, agent: Agent):
        return farming_system.haul_harvest(self, agent)

    def is_farmer_task_viable(self, agent: Agent) -> bool:
        return bool(farming_system.is_farmer_task_viable(self, agent))

    def farm_task_continuity_bonus(self, agent: Agent, task_name: str) -> int:
        return int(farming_system.farm_task_continuity_bonus(self, agent, str(task_name)))

    def detect_villages(self):
        village_system.detect_villages(self)

    def assign_village_leaders(self):
        village_system.assign_village_leaders(self)

    def update_village_politics(self):
        village_system.update_village_politics(self)

    def update(self):
        self.tick += 1
        self.llm_calls_this_tick = 0
        self._decay_food_patch_activity()
        self._decay_local_practice_memory()

        self.respawn_resources()
        farming_system.update_farms(self)

        for agent in list(self.agents):
            if not agent.alive:
                continue
            agent.update(self)

        self.agents = [a for a in self.agents if a.alive]
        self.record_movement_congestion_snapshot()
        self.update_proto_communities_and_camps()
        self.run_local_food_handoff_pass()

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
        self.update_settlement_progression_metrics()
        if hasattr(self, "metrics_collector"):
            self.metrics_collector.collect(self)
