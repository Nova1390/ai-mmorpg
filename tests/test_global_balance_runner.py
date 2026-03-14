from __future__ import annotations

import pytest

from agent import Agent
from systems.global_balance_runner import (
    GlobalBalanceThresholds,
    aggregate_global_balance_results,
    compute_implausibility_flags,
    compute_village_support_map,
)
from world import World


def test_compute_village_support_map_counts_affiliated_agents_by_uid() -> None:
    world = World(width=20, height=20, num_agents=0, seed=42, llm_enabled=False)
    world.agents = []

    a1 = Agent(x=5, y=5, brain=None, is_player=False, player_id=None)
    a1.village_affiliation_status = "attached"
    a1.primary_village_uid = "v-000001"

    a2 = Agent(x=6, y=5, brain=None, is_player=False, player_id=None)
    a2.village_affiliation_status = "resident"
    a2.home_village_uid = "v-000001"

    a3 = Agent(x=7, y=5, brain=None, is_player=False, player_id=None)
    a3.village_affiliation_status = "transient"
    a3.primary_village_uid = "v-000002"

    world.agents = [a1, a2, a3]
    support = compute_village_support_map(world)

    assert int(support.get("v-000001", 0)) == 2
    assert int(support.get("v-000002", 0)) == 1


def test_implausibility_flags_detect_singleton_village_and_leader() -> None:
    thresholds = GlobalBalanceThresholds(
        min_legit_village_population=2,
        min_legit_leader_village_population=3,
        early_extinction_threshold_tick=200,
        early_mass_death_threshold_ratio=0.5,
    )
    metrics = {
        "survival": {
            "extinction": True,
            "extinction_tick": 150,
            "early_mass_death": True,
        },
        "settlement_legitimacy": {
            "singleton_village_count": 1,
            "villages_under_legit_threshold_count": 2,
        },
        "leadership_legitimacy": {
            "leaders_in_singleton_villages_count": 1,
            "leaders_under_legit_threshold_count": 1,
        },
    }

    flags = compute_implausibility_flags(metrics=metrics, thresholds=thresholds)
    assert bool(flags["singleton_village_created"]) is True
    assert bool(flags["singleton_leader_created"]) is True
    assert bool(flags["village_before_min_population_support"]) is True
    assert bool(flags["leadership_before_min_social_support"]) is True
    assert bool(flags["early_mass_death"]) is True
    assert bool(flags["extinction_before_tick_threshold"]) is True


def test_implausibility_flags_remain_false_for_legit_non_extinction_case() -> None:
    thresholds = GlobalBalanceThresholds(
        min_legit_village_population=3,
        min_legit_leader_village_population=3,
        early_extinction_threshold_tick=200,
        early_mass_death_threshold_ratio=0.5,
    )
    metrics = {
        "survival": {
            "extinction": False,
            "extinction_tick": None,
            "early_mass_death": False,
        },
        "settlement_legitimacy": {
            "singleton_village_count": 0,
            "villages_under_legit_threshold_count": 0,
        },
        "leadership_legitimacy": {
            "leaders_in_singleton_villages_count": 0,
            "leaders_under_legit_threshold_count": 0,
        },
    }

    flags = compute_implausibility_flags(metrics=metrics, thresholds=thresholds)
    assert all(bool(v) is False for v in flags.values())


def test_aggregate_global_balance_includes_comm002_metrics() -> None:
    thresholds = GlobalBalanceThresholds()
    runs = [
        {
            "metrics": {
                "survival": {"final_population": 12, "extinction": False, "early_mass_death": False},
                "settlement_legitimacy": {
                    "singleton_village_count": 0,
                    "settlement_bottleneck_diagnostics": {
                        "village_creation_attempts": 15,
                        "village_creation_blocked_count": 9,
                        "independent_cluster_count": 11,
                        "camp_to_village_transition_attempts": 6,
                        "camp_to_village_transition_failures": 4,
                        "local_viable_camp_retained_count": 18,
                        "distant_cluster_pull_suppressed_count": 7,
                        "camp_absorption_events": 3,
                        "mature_nucleus_detected_count": 6,
                        "mature_nucleus_failed_transition_count": 2,
                        "mature_nucleus_successful_transition_count": 3,
                        "cluster_ecological_productivity_score": {"avg": 4.2},
                        "cluster_inertia_events": 20,
                        "dominant_cluster_saturation_penalty_applied": 9,
                        "camp_absorption_delay_events": 5,
                        "secondary_cluster_persistence_ticks": 140,
                        "exploration_shift_due_to_low_density": 18,
                        "secondary_nucleus_structure_count": 55,
                        "secondary_nucleus_build_support_events": 21,
                        "secondary_nucleus_material_delivery_events": 17,
                        "secondary_nucleus_materialization_ticks": 66,
                        "secondary_nucleus_absorption_during_build": 4,
                        "secondary_nucleus_materialization_success": 2,
                        "cluster_population_distribution_summary": {"secondary_cluster_nonzero_count": 2},
                    },
                },
                "leadership_legitimacy": {"leaders_in_singleton_villages_count": 0},
                "camp_proto": {
                    "camps_formed_count": 4,
                    "active_camps_final": 2,
                    "camp_food_metrics": {
                        "camp_food_deposits": 20,
                        "camp_food_consumptions": 15,
                        "domestic_food_stored_total": 6,
                        "domestic_food_consumed_total": 5,
                        "house_food_capacity_utilization": 0.25,
                        "houses_with_food": 2,
                        "local_food_pressure_events": 500,
                        "pressure_backed_food_deliveries": 5,
                        "pressure_served_ratio": 0.01,
                    },
                    "communication_knowledge_metrics": {
                        "communication_events": 1000,
                        "shared_food_knowledge_used_count": 30,
                        "shared_camp_knowledge_used_count": 2,
                        "social_knowledge_accept_count": 100,
                        "social_knowledge_reject_count": 600,
                        "social_knowledge_reject_survival_priority": 50,
                        "direct_overrides_social_count": 200,
                        "repeated_duplicate_share_suppressed_count": 80,
                        "confirmed_memory_reinforcements": 40,
                        "direct_memory_invalidations": 18,
                    },
                    "lifespan_continuity_metrics": {
                        "avg_useful_memory_age": 72.0,
                        "repeated_successful_loop_count": 55,
                        "routine_persistence_ticks": 210,
                        "routine_abandonment_after_failure": 11,
                        "routine_abandonment_after_success": 8,
                        "average_agent_age_alive": 260.0,
                    },
                    "social_encounter_metrics": {
                        "total_encounter_events": 5000,
                        "familiarity_relationships_count": 12,
                        "avg_familiarity_score": 0.6,
                        "familiar_agent_proximity_events": 2500,
                        "social_density_bias_applied_count": 700,
                        "familiar_communication_bonus_applied": 120,
                        "familiar_zone_reinforcement_events": 90,
                        "familiar_camp_support_bias_events": 60,
                        "familiar_loop_continuity_bonus": 45,
                        "familiar_anchor_exploration_events": 30,
                        "familiar_zone_score_updates": 100,
                        "familiar_zone_score_decay": 80,
                        "familiar_zone_saturation_clamps": 25,
                        "dense_area_social_bias_reductions": 40,
                        "familiar_zone_decay_due_to_low_payoff": 35,
                        "overcrowded_familiar_bias_suppressed": 45,
                        "density_safe_loop_bonus_reduced_count": 20,
                    },
                    "construction_situated_metrics": {
                        "construction_on_site_work_ticks": 90,
                        "construction_offsite_blocked_ticks": 10,
                        "construction_interrupted_survival": 3,
                        "construction_interrupted_invalid_target": 2,
                    },
                    "road_purpose_metrics": {
                        "road_built_with_purpose_count": 25,
                        "road_build_suppressed_no_purpose": 12,
                    },
                    "settlement_progression_metrics": {
                        "house_cluster_count": 3,
                        "avg_houses_per_cluster": 2.0,
                        "house_cluster_growth_events": 8,
                        "farm_sites_created": 5,
                        "farm_work_events": 18,
                        "farm_abandoned": 1,
                        "farm_yield_events": 9,
                        "farm_productivity_score_avg": 1.4,
                        "agents_farming_count": 3,
                        "storage_built_after_cluster_count": 2,
                        "storage_built_without_cluster_count": 1,
                        "storage_emergence_attempts": 6,
                        "storage_emergence_successes": 2,
                        "storage_deferred_due_to_low_house_cluster": 2,
                        "storage_deferred_due_to_low_throughput": 3,
                        "storage_deferred_due_to_low_buffer_pressure": 1,
                        "storage_built_in_mature_cluster_count": 2,
                        "storage_supporting_active_house_cluster_count": 2,
                        "storage_relief_of_domestic_pressure_events": 5,
                        "storage_relief_of_camp_pressure_events": 3,
                        "active_storage_construction_sites": 2,
                        "storage_builder_commitment_retained_ticks": 11,
                        "storage_material_delivery_events": 7,
                        "storage_construction_progress_ticks": 19,
                        "storage_construction_interrupted_survival": 2,
                        "storage_construction_interrupted_invalid": 3,
                        "storage_construction_abandoned_count": 1,
                        "storage_construction_completed_count": 2,
                        "construction_material_delivery_events": 14,
                        "construction_material_delivery_to_active_site": 11,
                        "construction_material_delivery_drift_events": 4,
                        "construction_progress_ticks": 22,
                        "construction_progress_stalled_ticks": 9,
                        "construction_completion_events": 6,
                        "construction_abandonment_events": 2,
                        "local_food_surplus_rate": 0.06,
                        "local_resource_surplus_rate": 0.05,
                        "buffer_saturation_events": 4,
                        "surplus_triggered_storage_attempts": 3,
                        "surplus_storage_construction_completed": 2,
                        "surplus_storage_abandoned": 1,
                        "storage_deferred_due_to_low_surplus": 1,
                        "secondary_nucleus_with_house_count": 2,
                        "secondary_nucleus_house_growth_events": 3,
                        "repeated_successful_loop_count": 55,
                        "routine_persistence_ticks": 210,
                        "routine_abandonment_after_failure": 11,
                        "routine_abandonment_after_success": 8,
                        "cultural_practices_created": 14,
                        "cultural_practices_reinforced": 82,
                        "cultural_practices_decayed": 10,
                        "active_cultural_practices": 12,
                        "agents_using_cultural_memory_bias": 44,
                        "productive_food_patch_practices": 7,
                        "proto_farm_practices": 3,
                        "construction_cluster_practices": 2,
                    },
                    "material_feasibility_metrics": {
                        "wood_available_world_total": 120,
                        "wood_available_on_map": 40,
                        "wood_in_agent_inventories": 18,
                        "wood_in_storage_buildings": 45,
                        "wood_in_construction_buffers": 17,
                        "wood_gathered_total": 90,
                        "wood_respawned_total": 55,
                        "wood_consumed_for_construction_total": 48,
                        "wood_shortage_events": 7,
                        "avg_local_wood_pressure": 0.22,
                        "construction_sites_created": 14,
                        "construction_sites_created_house": 10,
                        "construction_sites_created_storage": 4,
                        "active_construction_sites": 5,
                        "partially_built_sites_count": 3,
                        "construction_stalled_ticks": 9,
                        "construction_stalled_sites_count": 2,
                        "construction_completed_count": 6,
                        "construction_abandoned_count": 2,
                        "construction_material_delivery_failures": 4,
                        "construction_material_shortage_blocks": 6,
                        "construction_delivery_attempts": 16,
                        "construction_delivery_successes": 9,
                        "construction_delivery_failures": 6,
                        "construction_delivery_to_site_events": 9,
                        "construction_delivery_to_wrong_target_or_drift": 3,
                        "construction_delivery_avg_distance_to_site": 0.8,
                        "construction_delivery_avg_distance_to_source": 3.2,
                        "storage_delivery_failures": 4,
                        "house_delivery_failures": 2,
                        "storage_delivery_successes": 3,
                        "house_delivery_successes": 6,
                        "construction_site_waiting_for_material_ticks": 40,
                        "construction_site_waiting_for_builder_ticks": 12,
                        "construction_site_waiting_total_ticks": 90,
                        "construction_site_progress_active_ticks": 28,
                        "construction_site_starved_cycles": 14,
                        "storage_waiting_for_material_ticks": 22,
                        "house_waiting_for_material_ticks": 18,
                        "storage_waiting_for_builder_ticks": 8,
                        "house_waiting_for_builder_ticks": 4,
                        "construction_site_lifetime_ticks_avg": 55.0,
                        "construction_site_progress_before_abandon_avg": 1.7,
                        "construction_site_material_units_delivered_avg": 5.2,
                        "construction_site_material_units_missing_avg": 2.1,
                        "construction_site_material_units_required_total": 20,
                        "construction_site_material_units_delivered_total": 13,
                        "construction_site_material_units_remaining": 7,
                        "construction_near_complete_sites_count": 1,
                        "builder_assigned_site_count": 6,
                        "builder_site_arrival_count": 4,
                        "builder_left_site_count": 3,
                        "builder_left_site_before_completion_count": 2,
                        "builder_waiting_on_site_ticks_total": 22,
                        "builder_on_site_ticks_total": 18,
                        "builder_work_tick_applied_count": 9,
                        "builder_survival_override_during_construction_count": 1,
                        "builder_redirected_to_storage_during_construction_count": 2,
                        "construction_site_buildable_ticks_total": 30,
                        "construction_site_idle_buildable_ticks_total": 12,
                        "construction_site_first_builder_arrival_delay_avg": 7.0,
                        "construction_site_material_ready_to_first_work_delay_avg": 5.0,
                        "construction_site_completion_time_avg": 47.0,
                        "construction_time_first_delivery_to_completion_avg": 22.0,
                        "construction_time_first_progress_to_completion_avg": 16.0,
                        "construction_completed_after_first_delivery_count": 2,
                        "construction_completed_after_started_progress_count": 2,
                        "house_completion_time_avg": 41.0,
                        "storage_completion_time_avg": 62.0,
                        "houses_completed_count": 5,
                        "storage_attempts": 6,
                        "storage_completed_count": 2,
                        "storage_completion_rate": 0.3333,
                    },
                },
                "behavior_map": {
                    "secondary_nucleus_lifecycle": {
                        "secondary_nucleus_birth_count": 9,
                        "secondary_nucleus_absorption_count": 3,
                        "secondary_nucleus_decay_count": 2,
                        "secondary_nucleus_persistence_ticks": 80,
                        "secondary_nucleus_village_attempts": 4,
                        "secondary_nucleus_village_successes": 1,
                    }
                },
            }
        },
        {
            "metrics": {
                "survival": {"final_population": 8, "extinction": True, "early_mass_death": True},
                "settlement_legitimacy": {
                    "singleton_village_count": 1,
                    "settlement_bottleneck_diagnostics": {
                        "village_creation_attempts": 18,
                        "village_creation_blocked_count": 12,
                        "independent_cluster_count": 13,
                        "camp_to_village_transition_attempts": 8,
                        "camp_to_village_transition_failures": 6,
                        "local_viable_camp_retained_count": 14,
                        "distant_cluster_pull_suppressed_count": 5,
                        "camp_absorption_events": 4,
                        "mature_nucleus_detected_count": 5,
                        "mature_nucleus_failed_transition_count": 3,
                        "mature_nucleus_successful_transition_count": 2,
                        "cluster_ecological_productivity_score": {"avg": 3.4},
                        "cluster_inertia_events": 16,
                        "dominant_cluster_saturation_penalty_applied": 11,
                        "camp_absorption_delay_events": 4,
                        "secondary_cluster_persistence_ticks": 110,
                        "exploration_shift_due_to_low_density": 12,
                        "secondary_nucleus_structure_count": 45,
                        "secondary_nucleus_build_support_events": 17,
                        "secondary_nucleus_material_delivery_events": 13,
                        "secondary_nucleus_materialization_ticks": 52,
                        "secondary_nucleus_absorption_during_build": 5,
                        "secondary_nucleus_materialization_success": 1,
                        "cluster_population_distribution_summary": {"secondary_cluster_nonzero_count": 1},
                    },
                },
                "leadership_legitimacy": {"leaders_in_singleton_villages_count": 1},
                "camp_proto": {
                    "camps_formed_count": 2,
                    "active_camps_final": 1,
                    "camp_food_metrics": {
                        "camp_food_deposits": 10,
                        "camp_food_consumptions": 8,
                        "domestic_food_stored_total": 2,
                        "domestic_food_consumed_total": 1,
                        "house_food_capacity_utilization": 0.1,
                        "houses_with_food": 1,
                        "local_food_pressure_events": 300,
                        "pressure_backed_food_deliveries": 3,
                        "pressure_served_ratio": 0.02,
                    },
                    "communication_knowledge_metrics": {
                        "communication_events": 800,
                        "shared_food_knowledge_used_count": 20,
                        "shared_camp_knowledge_used_count": 0,
                        "social_knowledge_accept_count": 80,
                        "social_knowledge_reject_count": 500,
                        "social_knowledge_reject_survival_priority": 40,
                        "direct_overrides_social_count": 150,
                        "repeated_duplicate_share_suppressed_count": 60,
                        "confirmed_memory_reinforcements": 20,
                        "direct_memory_invalidations": 30,
                    },
                    "lifespan_continuity_metrics": {
                        "avg_useful_memory_age": 60.0,
                        "repeated_successful_loop_count": 35,
                        "routine_persistence_ticks": 150,
                        "routine_abandonment_after_failure": 18,
                        "routine_abandonment_after_success": 9,
                        "average_agent_age_alive": 215.0,
                    },
                    "social_encounter_metrics": {
                        "total_encounter_events": 4000,
                        "familiarity_relationships_count": 10,
                        "avg_familiarity_score": 0.5,
                        "familiar_agent_proximity_events": 2000,
                        "social_density_bias_applied_count": 600,
                        "familiar_communication_bonus_applied": 100,
                        "familiar_zone_reinforcement_events": 70,
                        "familiar_camp_support_bias_events": 40,
                        "familiar_loop_continuity_bonus": 35,
                        "familiar_anchor_exploration_events": 20,
                        "familiar_zone_score_updates": 80,
                        "familiar_zone_score_decay": 60,
                        "familiar_zone_saturation_clamps": 15,
                        "dense_area_social_bias_reductions": 30,
                        "familiar_zone_decay_due_to_low_payoff": 25,
                        "overcrowded_familiar_bias_suppressed": 35,
                        "density_safe_loop_bonus_reduced_count": 10,
                    },
                    "construction_situated_metrics": {
                        "construction_on_site_work_ticks": 70,
                        "construction_offsite_blocked_ticks": 15,
                        "construction_interrupted_survival": 5,
                        "construction_interrupted_invalid_target": 4,
                    },
                    "road_purpose_metrics": {
                        "road_built_with_purpose_count": 18,
                        "road_build_suppressed_no_purpose": 20,
                    },
                    "settlement_progression_metrics": {
                        "house_cluster_count": 2,
                        "avg_houses_per_cluster": 1.5,
                        "house_cluster_growth_events": 5,
                        "farm_sites_created": 3,
                        "farm_work_events": 10,
                        "farm_abandoned": 2,
                        "farm_yield_events": 5,
                        "farm_productivity_score_avg": 0.9,
                        "agents_farming_count": 2,
                        "storage_built_after_cluster_count": 1,
                        "storage_built_without_cluster_count": 2,
                        "storage_emergence_attempts": 4,
                        "storage_emergence_successes": 1,
                        "storage_deferred_due_to_low_house_cluster": 1,
                        "storage_deferred_due_to_low_throughput": 2,
                        "storage_deferred_due_to_low_buffer_pressure": 1,
                        "storage_built_in_mature_cluster_count": 1,
                        "storage_supporting_active_house_cluster_count": 1,
                        "storage_relief_of_domestic_pressure_events": 2,
                        "storage_relief_of_camp_pressure_events": 1,
                        "active_storage_construction_sites": 1,
                        "storage_builder_commitment_retained_ticks": 7,
                        "storage_material_delivery_events": 4,
                        "storage_construction_progress_ticks": 12,
                        "storage_construction_interrupted_survival": 3,
                        "storage_construction_interrupted_invalid": 4,
                        "storage_construction_abandoned_count": 2,
                        "storage_construction_completed_count": 1,
                        "construction_material_delivery_events": 10,
                        "construction_material_delivery_to_active_site": 7,
                        "construction_material_delivery_drift_events": 5,
                        "construction_progress_ticks": 16,
                        "construction_progress_stalled_ticks": 11,
                        "construction_completion_events": 4,
                        "construction_abandonment_events": 3,
                        "local_food_surplus_rate": 0.02,
                        "local_resource_surplus_rate": 0.01,
                        "buffer_saturation_events": 2,
                        "surplus_triggered_storage_attempts": 1,
                        "surplus_storage_construction_completed": 0,
                        "surplus_storage_abandoned": 2,
                        "storage_deferred_due_to_low_surplus": 3,
                        "secondary_nucleus_with_house_count": 1,
                        "secondary_nucleus_house_growth_events": 2,
                        "repeated_successful_loop_count": 35,
                        "routine_persistence_ticks": 150,
                        "routine_abandonment_after_failure": 18,
                        "routine_abandonment_after_success": 9,
                        "cultural_practices_created": 10,
                        "cultural_practices_reinforced": 62,
                        "cultural_practices_decayed": 8,
                        "active_cultural_practices": 8,
                        "agents_using_cultural_memory_bias": 24,
                        "productive_food_patch_practices": 5,
                        "proto_farm_practices": 2,
                        "construction_cluster_practices": 1,
                    },
                    "material_feasibility_metrics": {
                        "wood_available_world_total": 80,
                        "wood_available_on_map": 28,
                        "wood_in_agent_inventories": 10,
                        "wood_in_storage_buildings": 30,
                        "wood_in_construction_buffers": 12,
                        "wood_gathered_total": 62,
                        "wood_respawned_total": 32,
                        "wood_consumed_for_construction_total": 30,
                        "wood_shortage_events": 14,
                        "avg_local_wood_pressure": 0.44,
                        "construction_sites_created": 10,
                        "construction_sites_created_house": 7,
                        "construction_sites_created_storage": 3,
                        "active_construction_sites": 4,
                        "partially_built_sites_count": 2,
                        "construction_stalled_ticks": 14,
                        "construction_stalled_sites_count": 3,
                        "construction_completed_count": 4,
                        "construction_abandoned_count": 3,
                        "construction_material_delivery_failures": 7,
                        "construction_material_shortage_blocks": 11,
                        "construction_delivery_attempts": 10,
                        "construction_delivery_successes": 6,
                        "construction_delivery_failures": 4,
                        "construction_delivery_to_site_events": 6,
                        "construction_delivery_to_wrong_target_or_drift": 2,
                        "construction_delivery_avg_distance_to_site": 1.0,
                        "construction_delivery_avg_distance_to_source": 2.8,
                        "storage_delivery_failures": 3,
                        "house_delivery_failures": 1,
                        "storage_delivery_successes": 2,
                        "house_delivery_successes": 4,
                        "construction_site_waiting_for_material_ticks": 30,
                        "construction_site_waiting_for_builder_ticks": 9,
                        "construction_site_waiting_total_ticks": 70,
                        "construction_site_progress_active_ticks": 21,
                        "construction_site_starved_cycles": 10,
                        "storage_waiting_for_material_ticks": 16,
                        "house_waiting_for_material_ticks": 14,
                        "storage_waiting_for_builder_ticks": 6,
                        "house_waiting_for_builder_ticks": 3,
                        "construction_site_lifetime_ticks_avg": 49.0,
                        "construction_site_progress_before_abandon_avg": 1.3,
                        "construction_site_material_units_delivered_avg": 4.6,
                        "construction_site_material_units_missing_avg": 1.7,
                        "construction_site_material_units_required_total": 17,
                        "construction_site_material_units_delivered_total": 11,
                        "construction_site_material_units_remaining": 6,
                        "construction_near_complete_sites_count": 1,
                        "builder_assigned_site_count": 4,
                        "builder_site_arrival_count": 3,
                        "builder_left_site_count": 2,
                        "builder_left_site_before_completion_count": 1,
                        "builder_waiting_on_site_ticks_total": 18,
                        "builder_on_site_ticks_total": 14,
                        "builder_work_tick_applied_count": 7,
                        "builder_survival_override_during_construction_count": 2,
                        "builder_redirected_to_storage_during_construction_count": 1,
                        "construction_site_buildable_ticks_total": 24,
                        "construction_site_idle_buildable_ticks_total": 10,
                        "construction_site_first_builder_arrival_delay_avg": 8.0,
                        "construction_site_material_ready_to_first_work_delay_avg": 6.0,
                        "construction_site_completion_time_avg": 42.0,
                        "construction_time_first_delivery_to_completion_avg": 19.0,
                        "construction_time_first_progress_to_completion_avg": 14.0,
                        "construction_completed_after_first_delivery_count": 1,
                        "construction_completed_after_started_progress_count": 1,
                        "house_completion_time_avg": 38.0,
                        "storage_completion_time_avg": 55.0,
                        "houses_completed_count": 3,
                        "storage_attempts": 4,
                        "storage_completed_count": 1,
                        "storage_completion_rate": 0.25,
                    },
                },
                "behavior_map": {
                    "secondary_nucleus_lifecycle": {
                        "secondary_nucleus_birth_count": 7,
                        "secondary_nucleus_absorption_count": 5,
                        "secondary_nucleus_decay_count": 4,
                        "secondary_nucleus_persistence_ticks": 60,
                        "secondary_nucleus_village_attempts": 3,
                        "secondary_nucleus_village_successes": 0,
                    }
                },
            }
        },
    ]
    payload = aggregate_global_balance_results(
        scenario_family="baseline",
        runs=runs,
        thresholds=thresholds,
    )
    agg = payload["aggregate"]
    assert float(agg["avg_final_population"]) == 10.0
    assert float(agg["extinction_run_ratio"]) == 0.5
    assert float(agg["avg_active_camps_final"]) == 1.5
    assert float(agg["avg_communication_events"]) == 900.0
    assert float(agg["avg_shared_food_knowledge_used"]) == 25.0
    assert float(agg["avg_domestic_food_stored_total"]) == 4.0
    assert float(agg["avg_domestic_food_consumed_total"]) == 3.0
    assert float(agg["avg_house_food_capacity_utilization"]) == 0.175
    assert float(agg["avg_houses_with_food"]) == 1.5
    assert float(agg["avg_direct_overrides_social_count"]) == 175.0
    assert float(agg["avg_social_knowledge_reject_count"]) == 550.0
    assert float(agg["avg_confirmed_memory_reinforcements"]) == 30.0
    assert float(agg["avg_direct_memory_invalidations"]) == 24.0
    assert float(agg["avg_useful_memory_age"]) == 66.0
    assert float(agg["avg_repeated_successful_loop_count"]) == 45.0
    assert float(agg["avg_routine_persistence_ticks"]) == 180.0
    assert float(agg["avg_routine_abandonment_after_failure"]) == 14.5
    assert float(agg["avg_routine_abandonment_after_success"]) == 8.5
    assert float(agg["avg_average_agent_age_alive"]) == 237.5
    assert float(agg["average_agent_age_alive"]) == 237.5
    assert float(agg["avg_confirmed_memory_reinforcements_per_agent"]) == 3.0
    assert float(agg["avg_direct_memory_invalidations_per_agent"]) == 2.4
    assert float(agg["avg_confirmed_memory_reinforcements_per_alive_agent_tick"]) == 3.0
    assert float(agg["avg_direct_memory_invalidations_per_alive_agent_tick"]) == 2.4
    assert float(agg["avg_confirmed_to_invalidated_memory_ratio"]) == 1.25
    assert float(agg["avg_routine_success_to_failure_abandonment_ratio"]) == pytest.approx(0.5862)
    assert float(agg["avg_total_encounter_events"]) == 4500.0
    assert float(agg["avg_familiarity_relationships_count"]) == 11.0
    assert float(agg["avg_familiarity_score"]) == 0.55
    assert float(agg["avg_familiar_agent_proximity_events"]) == 2250.0
    assert float(agg["avg_social_density_bias_applied_count"]) == 650.0
    assert float(agg["avg_familiar_communication_bonus_applied"]) == 110.0
    assert float(agg["avg_familiar_zone_reinforcement_events"]) == 80.0
    assert float(agg["avg_familiar_camp_support_bias_events"]) == 50.0
    assert float(agg["avg_familiar_loop_continuity_bonus"]) == 40.0
    assert float(agg["avg_familiar_anchor_exploration_events"]) == 25.0
    assert float(agg["avg_familiar_zone_score_updates"]) == 90.0
    assert float(agg["avg_familiar_zone_score_decay"]) == 70.0
    assert float(agg["avg_familiar_zone_saturation_clamps"]) == 20.0
    assert float(agg["avg_dense_area_social_bias_reductions"]) == 35.0
    assert float(agg["avg_familiar_zone_decay_due_to_low_payoff"]) == 30.0
    assert float(agg["avg_overcrowded_familiar_bias_suppressed"]) == 40.0
    assert float(agg["avg_density_safe_loop_bonus_reduced_count"]) == 15.0
    assert float(agg["avg_road_built_with_purpose_count"]) == 21.5
    assert float(agg["avg_road_build_suppressed_no_purpose"]) == 16.0
    assert float(agg["avg_construction_on_site_work_ticks"]) == 80.0
    assert float(agg["avg_construction_offsite_blocked_ticks"]) == 12.5
    assert float(agg["avg_construction_interrupted_survival"]) == 4.0
    assert float(agg["avg_construction_interrupted_invalid_target"]) == 3.0
    assert float(agg["avg_house_cluster_count"]) == 2.5
    assert float(agg["avg_houses_per_cluster"]) == 1.75
    assert float(agg["avg_house_cluster_growth_events"]) == 6.5
    assert float(agg["avg_farm_sites_created"]) == 4.0
    assert float(agg["avg_farm_work_events"]) == 14.0
    assert float(agg["avg_farm_abandoned"]) == 1.5
    assert float(agg["avg_farm_yield_events"]) == 7.0
    assert float(agg["avg_farm_productivity_score_avg"]) == pytest.approx(1.15)
    assert float(agg["avg_agents_farming_count"]) == 2.5
    assert float(agg["avg_cultural_practices_created"]) == 12.0
    assert float(agg["avg_cultural_practices_reinforced"]) == 72.0
    assert float(agg["avg_cultural_practices_decayed"]) == 9.0
    assert float(agg["avg_active_cultural_practices"]) == 10.0
    assert float(agg["avg_agents_using_cultural_memory_bias"]) == 34.0
    assert float(agg["avg_productive_food_patch_practices"]) == 6.0
    assert float(agg["avg_proto_farm_practices"]) == 2.5
    assert float(agg["avg_construction_cluster_practices"]) == 1.5
    assert float(agg["avg_storage_built_after_cluster_count"]) == 1.5
    assert float(agg["avg_storage_built_without_cluster_count"]) == 1.5
    assert float(agg["avg_storage_emergence_attempts"]) == 5.0
    assert float(agg["avg_storage_emergence_successes"]) == 1.5
    assert float(agg["avg_storage_deferred_due_to_low_house_cluster"]) == 1.5
    assert float(agg["avg_storage_deferred_due_to_low_throughput"]) == 2.5
    assert float(agg["avg_storage_deferred_due_to_low_buffer_pressure"]) == 1.0
    assert float(agg["avg_storage_deferred_due_to_low_surplus"]) == 2.0
    assert float(agg["avg_storage_built_in_mature_cluster_count"]) == 1.5
    assert float(agg["avg_storage_supporting_active_house_cluster_count"]) == 1.5
    assert float(agg["avg_storage_relief_of_domestic_pressure_events"]) == 3.5
    assert float(agg["avg_storage_relief_of_camp_pressure_events"]) == 2.0
    assert float(agg["avg_active_storage_construction_sites"]) == 1.5
    assert float(agg["avg_storage_builder_commitment_retained_ticks"]) == 9.0
    assert float(agg["avg_storage_material_delivery_events"]) == 5.5
    assert float(agg["avg_storage_construction_progress_ticks"]) == 15.5
    assert float(agg["avg_storage_construction_interrupted_survival"]) == 2.5
    assert float(agg["avg_storage_construction_interrupted_invalid"]) == 3.5
    assert float(agg["avg_storage_construction_abandoned_count"]) == 1.5
    assert float(agg["avg_storage_construction_completed_count"]) == 1.5
    assert float(agg["avg_construction_material_delivery_events"]) == 12.0
    assert float(agg["avg_construction_material_delivery_to_active_site"]) == 9.0
    assert float(agg["avg_construction_material_delivery_drift_events"]) == 4.5
    assert float(agg["avg_construction_progress_ticks"]) == 19.0
    assert float(agg["avg_construction_progress_stalled_ticks"]) == 10.0
    assert float(agg["avg_construction_completion_events"]) == 5.0
    assert float(agg["avg_construction_abandonment_events"]) == 2.5
    assert float(agg["avg_local_food_surplus_rate"]) == 0.04
    assert float(agg["avg_local_resource_surplus_rate"]) == pytest.approx(0.03)
    assert float(agg["avg_buffer_saturation_events"]) == 3.0
    assert float(agg["avg_surplus_triggered_storage_attempts"]) == 2.0
    assert float(agg["avg_surplus_storage_construction_completed"]) == 1.0
    assert float(agg["avg_surplus_storage_abandoned"]) == 1.5
    assert float(agg["avg_secondary_nucleus_with_house_count"]) == 1.5
    assert float(agg["avg_secondary_nucleus_house_growth_events"]) == 2.5
    assert float(agg["avg_village_creation_attempts"]) == 16.5
    assert float(agg["avg_village_creation_blocked_count"]) == 10.5
    assert float(agg["avg_independent_cluster_count"]) == 12.0
    assert float(agg["avg_camp_to_village_transition_attempts"]) == 7.0
    assert float(agg["avg_camp_to_village_transition_failures"]) == 5.0
    assert float(agg["avg_local_viable_camp_retained_count"]) == 16.0
    assert float(agg["avg_distant_cluster_pull_suppressed_count"]) == 6.0
    assert float(agg["avg_camp_absorption_events"]) == 3.5
    assert float(agg["avg_mature_nucleus_detected_count"]) == 5.5
    assert float(agg["avg_mature_nucleus_failed_transition_count"]) == 2.5
    assert float(agg["avg_mature_nucleus_successful_transition_count"]) == 2.5
    assert float(agg["avg_cluster_ecological_productivity_score"]) == 3.8
    assert float(agg["avg_cluster_inertia_events"]) == 18.0
    assert float(agg["avg_dominant_cluster_saturation_penalty_applied"]) == 10.0
    assert float(agg["avg_camp_absorption_delay_events"]) == 4.5
    assert float(agg["avg_secondary_cluster_persistence_ticks"]) == 125.0
    assert float(agg["avg_exploration_shift_due_to_low_density"]) == 15.0
    assert float(agg["avg_secondary_cluster_nonzero_count"]) == 1.5
    assert float(agg["avg_secondary_nucleus_structure_count"]) == 50.0
    assert float(agg["avg_wood_available_world_total"]) == 100.0
    assert float(agg["avg_wood_available_on_map"]) == 34.0
    assert float(agg["avg_wood_in_agent_inventories"]) == 14.0
    assert float(agg["avg_wood_in_storage_buildings"]) == 37.5
    assert float(agg["avg_wood_in_construction_buffers"]) == 14.5
    assert float(agg["avg_wood_gathered_total"]) == 76.0
    assert float(agg["avg_wood_respawned_total"]) == 43.5
    assert float(agg["avg_wood_consumed_for_construction_total"]) == 39.0
    assert float(agg["avg_wood_shortage_events"]) == 10.5
    assert float(agg["avg_local_wood_pressure"]) == pytest.approx(0.33)
    assert float(agg["avg_construction_sites_created"]) == 12.0
    assert float(agg["avg_construction_sites_created_house"]) == 8.5
    assert float(agg["avg_construction_sites_created_storage"]) == 3.5
    assert float(agg["avg_active_construction_sites"]) == 4.5
    assert float(agg["avg_partially_built_sites_count"]) == 2.5
    assert float(agg["avg_construction_stalled_ticks_material"]) == 11.5
    assert float(agg["avg_construction_stalled_sites_count"]) == 2.5
    assert float(agg["avg_construction_completed_count"]) == 5.0
    assert float(agg["avg_construction_abandoned_count_material"]) == 2.5
    assert float(agg["avg_construction_material_delivery_failures"]) == 5.5
    assert float(agg["avg_construction_material_shortage_blocks"]) == 8.5
    assert float(agg["avg_construction_delivery_attempts"]) == 13.0
    assert float(agg["avg_construction_delivery_successes"]) == 7.5
    assert float(agg["avg_construction_delivery_failures"]) == 5.0
    assert float(agg["avg_construction_delivery_to_site_events"]) == 7.5
    assert float(agg["avg_construction_delivery_to_wrong_target_or_drift"]) == 2.5
    assert float(agg["avg_construction_delivery_avg_distance_to_site"]) == 0.9
    assert float(agg["avg_construction_delivery_avg_distance_to_source"]) == 3.0
    assert float(agg["avg_storage_delivery_failures"]) == 3.5
    assert float(agg["avg_house_delivery_failures"]) == 1.5
    assert float(agg["avg_storage_delivery_successes"]) == 2.5
    assert float(agg["avg_house_delivery_successes"]) == 5.0
    assert float(agg["avg_construction_site_waiting_for_material_ticks"]) == 35.0
    assert float(agg["avg_construction_site_waiting_for_builder_ticks"]) == 10.5
    assert float(agg["avg_construction_site_waiting_total_ticks"]) == 80.0
    assert float(agg["avg_construction_site_progress_active_ticks"]) == 24.5
    assert float(agg["avg_construction_site_starved_cycles"]) == 12.0
    assert float(agg["avg_storage_waiting_for_material_ticks"]) == 19.0
    assert float(agg["avg_house_waiting_for_material_ticks"]) == 16.0
    assert float(agg["avg_storage_waiting_for_builder_ticks"]) == 7.0
    assert float(agg["avg_house_waiting_for_builder_ticks"]) == 3.5
    assert float(agg["avg_construction_site_lifetime_ticks_avg"]) == 52.0
    assert float(agg["avg_construction_site_progress_before_abandon_avg"]) == 1.5
    assert float(agg["avg_construction_site_material_units_delivered_avg"]) == 4.9
    assert float(agg["avg_construction_site_material_units_missing_avg"]) == 1.9
    assert float(agg["avg_construction_site_material_units_required_total"]) == 18.5
    assert float(agg["avg_construction_site_material_units_delivered_total"]) == 12.0
    assert float(agg["avg_construction_site_material_units_remaining"]) == 6.5
    assert float(agg["avg_construction_near_complete_sites_count"]) == 1.0
    assert float(agg["avg_builder_assigned_site_count"]) == 5.0
    assert float(agg["avg_builder_site_arrival_count"]) == 3.5
    assert float(agg["avg_builder_work_tick_applied_count"]) == 8.0
    assert float(agg["avg_construction_site_buildable_ticks_total"]) == 27.0
    assert float(agg["avg_construction_site_first_builder_arrival_delay_avg"]) == 7.5
    assert float(agg["avg_construction_site_completion_time_avg"]) == 44.5
    assert float(agg["avg_construction_time_first_delivery_to_completion_avg"]) == 20.5
    assert float(agg["avg_construction_time_first_progress_to_completion_avg"]) == 15.0
    assert float(agg["avg_construction_completed_after_first_delivery_count"]) == 1.5
    assert float(agg["avg_construction_completed_after_started_progress_count"]) == 1.5
    assert float(agg["avg_house_completion_time_avg"]) == 39.5
    assert float(agg["avg_storage_completion_time_avg"]) == 58.5
    assert float(agg["avg_houses_completed_count"]) == 4.0
    assert float(agg["avg_storage_attempts"]) == 5.0
    assert float(agg["avg_storage_completed_count"]) == 1.5
    assert float(agg["avg_storage_completion_rate"]) == pytest.approx(0.29165)
    assert float(agg["avg_secondary_nucleus_build_support_events"]) == 19.0
    assert float(agg["avg_secondary_nucleus_material_delivery_events"]) == 15.0
    assert float(agg["avg_secondary_nucleus_materialization_ticks"]) == 59.0
    assert float(agg["avg_secondary_nucleus_absorption_during_build"]) == 4.5
    assert float(agg["avg_secondary_nucleus_materialization_success"]) == 1.5
    assert float(agg["avg_secondary_nucleus_birth_count"]) == 8.0
    assert float(agg["avg_secondary_nucleus_absorption_count"]) == 4.0
    assert float(agg["avg_secondary_nucleus_decay_count"]) == 3.0
    assert float(agg["avg_secondary_nucleus_persistence_ticks"]) == 70.0
    assert float(agg["avg_secondary_nucleus_village_attempts"]) == 3.5
    assert float(agg["avg_secondary_nucleus_village_successes"]) == 0.5
    assert "avg_population_deaths_hunger_age_0_199_count" in agg
    assert "avg_hunger_deaths_before_first_food_acquisition" in agg
    assert "avg_time_spawn_to_first_food_acquisition" in agg
    assert "avg_time_high_hunger_to_eat" in agg
    assert "avg_failed_food_seeking_attempts" in agg
    assert "avg_fallback_food_search_activations" in agg
    assert "avg_early_life_food_inventory_acquisition_count" in agg
    assert "avg_early_food_priority_overrides" in agg
    assert "avg_food_acquisition_interval_ticks" in agg
    assert "avg_food_acquisition_distance" in agg
    assert "avg_food_consumption_interval_ticks" in agg
    assert "avg_agent_hunger_relapse_after_first_food_count" in agg
    assert "avg_medium_term_food_priority_overrides" in agg
    assert "avg_local_food_inventory_per_agent" in agg
    assert "avg_food_seeking_time_ratio" in agg
    assert "avg_food_source_contention_events" in agg
    assert "avg_food_source_depletion_events" in agg
    assert "avg_food_respawned_total_observed" in agg
    assert "avg_foraging_yield_per_trip" in agg
    assert "avg_farming_yield_per_cycle" in agg
    assert "avg_food_move_time_ratio" in agg
    assert "avg_food_harvest_time_ratio" in agg
    assert "avg_local_food_basin_accessible" in agg
    assert "avg_local_food_pressure_ratio" in agg
    assert "avg_local_food_basin_competing_agents" in agg
    assert "avg_distance_to_viable_food_from_proto" in agg
    assert "avg_local_food_basin_severe_pressure_ticks" in agg
    assert "avg_local_food_basin_collapse_events" in agg
    assert "avg_proto_settlement_abandoned_due_to_food_pressure_count" in agg
    assert "avg_food_scarcity_adaptive_retarget_events" in agg
    assert "avg_food_gathered_total_observed" in agg
    assert "avg_food_consumed_total_observed" in agg
