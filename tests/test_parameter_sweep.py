from __future__ import annotations

from systems.global_balance_runner import GlobalBalanceScenarioConfig, GlobalBalanceThresholds, run_global_balance_scenario
from systems.parameter_sweep import (
    aggregate_across_families,
    generate_sweep_configs,
    is_breakeven_candidate,
    summarize_family_aggregate,
)
import agent as agent_module
import world as world_module


def test_generate_sweep_configs_is_deterministic_and_capped() -> None:
    ranges = {
        "food_regeneration_rate": (0.8, 1.0, 1.2),
        "hunger_decay_rate": (0.9, 1.0, 1.1),
        "camp_food_buffer_capacity": (0.75, 1.0, 1.25),
    }
    a = generate_sweep_configs(ranges=ranges, max_configs=4, deterministic_seed=42)
    b = generate_sweep_configs(ranges=ranges, max_configs=4, deterministic_seed=42)
    c = generate_sweep_configs(ranges=ranges, max_configs=4, deterministic_seed=43)
    assert len(a) == 4
    assert [x.config_id for x in a] == [x.config_id for x in b]
    assert [x.config_id for x in a] != [x.config_id for x in c]


def test_parameter_overrides_apply_and_restore() -> None:
    base_hunger_decay = float(agent_module.BASE_HUNGER_DECAY_PER_TICK)
    base_camp_cap = int(world_module.CAMP_FOOD_CACHE_CAPACITY)
    cfg = GlobalBalanceScenarioConfig(
        name="override_probe",
        seed=777,
        width=24,
        height=24,
        initial_population=12,
        ticks=8,
        snapshot_interval=2,
        history_limit=20,
        llm_enabled=False,
        parameter_overrides={
            "hunger_decay_rate": 1.1,
            "camp_food_buffer_capacity": 1.5,
            "eat_trigger_threshold": 54.0,
        },
    )
    payload = run_global_balance_scenario(cfg, thresholds=GlobalBalanceThresholds())
    assert isinstance(payload, dict)
    assert float(agent_module.BASE_HUNGER_DECAY_PER_TICK) == base_hunger_decay
    assert int(world_module.CAMP_FOOD_CACHE_CAPACITY) == base_camp_cap


def test_aggregate_across_families_is_deterministic() -> None:
    fam = {
        "baseline": {"avg_final_population": 10.0, "extinction_run_ratio": 0.0},
        "food_stress": {"avg_final_population": 6.0, "extinction_run_ratio": 0.2},
    }
    agg = aggregate_across_families(fam)
    assert float(agg["avg_final_population"]) == 8.0
    assert float(agg["extinction_run_ratio"]) == 0.1


def test_breakeven_detection_logic() -> None:
    baseline = {
        "avg_final_population": 10.0,
        "avg_repeated_successful_loop_count": 20.0,
    }
    improved = {
        "extinction_run_ratio": 0.0,
        "avg_repeated_successful_loop_count": 24.0,
        "avg_active_cultural_practices": 1.0,
        "avg_final_population": 11.0,
    }
    non_candidate = {
        "extinction_run_ratio": 0.2,
        "avg_repeated_successful_loop_count": 30.0,
        "avg_active_cultural_practices": 2.0,
        "avg_final_population": 12.0,
    }
    assert is_breakeven_candidate(aggregate_all=improved, baseline_reference=baseline) is True
    assert is_breakeven_candidate(aggregate_all=non_candidate, baseline_reference=baseline) is False


def test_summarize_family_aggregate_includes_material_feasibility_metrics() -> None:
    agg = summarize_family_aggregate(
        {
            "avg_wood_available_world_total": 88.0,
            "avg_wood_gathered_total": 44.0,
            "avg_wood_respawned_total": 21.0,
            "avg_wood_shortage_events": 7.0,
            "avg_local_wood_pressure": 0.28,
            "avg_construction_sites_created": 9.0,
            "avg_active_construction_sites": 3.0,
            "avg_partially_built_sites_count": 2.0,
            "avg_construction_completed_count": 4.0,
            "avg_construction_material_delivery_failures": 5.0,
            "avg_construction_material_shortage_blocks": 6.0,
            "avg_houses_completed_count": 3.0,
            "avg_storage_completed_count": 1.0,
            "avg_storage_completion_rate": 0.25,
            "avg_construction_delivery_attempts": 12.0,
            "avg_construction_delivery_successes": 7.0,
            "avg_construction_delivery_failures": 5.0,
            "avg_construction_delivery_to_site_events": 6.0,
            "avg_construction_delivery_to_wrong_target_or_drift": 2.0,
            "avg_construction_delivery_avg_distance_to_site": 1.1,
            "avg_construction_delivery_avg_distance_to_source": 3.4,
            "avg_storage_delivery_failures": 3.0,
            "avg_house_delivery_failures": 2.0,
            "avg_storage_delivery_successes": 2.0,
            "avg_house_delivery_successes": 5.0,
            "avg_construction_site_waiting_for_material_ticks": 40.0,
            "avg_construction_site_waiting_for_builder_ticks": 10.0,
            "avg_construction_site_waiting_total_ticks": 70.0,
            "avg_construction_site_progress_active_ticks": 22.0,
            "avg_construction_site_starved_cycles": 9.0,
            "avg_storage_waiting_for_material_ticks": 21.0,
            "avg_house_waiting_for_material_ticks": 19.0,
            "avg_storage_waiting_for_builder_ticks": 6.0,
            "avg_house_waiting_for_builder_ticks": 4.0,
            "avg_construction_site_lifetime_ticks_avg": 53.0,
            "avg_construction_site_progress_before_abandon_avg": 1.5,
            "avg_construction_site_material_units_delivered_avg": 4.8,
            "avg_construction_site_material_units_missing_avg": 2.2,
            "avg_construction_site_material_units_required_total": 18.0,
            "avg_construction_site_material_units_delivered_total": 11.0,
            "avg_construction_site_material_units_remaining": 7.0,
            "avg_construction_near_complete_sites_count": 1.0,
            "avg_builder_assigned_site_count": 5.0,
            "avg_builder_site_arrival_count": 3.0,
            "avg_builder_left_site_count": 2.0,
            "avg_builder_left_site_before_completion_count": 1.0,
            "avg_builder_waiting_on_site_ticks_total": 18.0,
            "avg_builder_on_site_ticks_total": 12.0,
            "avg_builder_work_tick_applied_count": 7.0,
            "avg_builder_survival_override_during_construction_count": 1.0,
            "avg_builder_redirected_to_storage_during_construction_count": 2.0,
            "avg_construction_site_buildable_ticks_total": 25.0,
            "avg_construction_site_idle_buildable_ticks_total": 9.0,
            "avg_construction_site_first_builder_arrival_delay_avg": 7.5,
            "avg_construction_site_material_ready_to_first_work_delay_avg": 5.5,
            "avg_construction_site_completion_time_avg": 45.0,
            "avg_construction_time_first_delivery_to_completion_avg": 20.0,
            "avg_construction_time_first_progress_to_completion_avg": 15.0,
            "avg_construction_completed_after_first_delivery_count": 2.0,
            "avg_construction_completed_after_started_progress_count": 2.0,
            "avg_house_completion_time_avg": 40.0,
            "avg_storage_completion_time_avg": 60.0,
        }
    )
    assert float(agg["avg_wood_available_world_total"]) == 88.0
    assert float(agg["avg_wood_gathered_total"]) == 44.0
    assert float(agg["avg_wood_respawned_total"]) == 21.0
    assert float(agg["avg_wood_shortage_events"]) == 7.0
    assert float(agg["avg_local_wood_pressure"]) == 0.28
    assert float(agg["avg_construction_sites_created"]) == 9.0
    assert float(agg["avg_active_construction_sites"]) == 3.0
    assert float(agg["avg_partially_built_sites_count"]) == 2.0
    assert float(agg["avg_construction_completed_count"]) == 4.0
    assert float(agg["avg_construction_material_delivery_failures"]) == 5.0
    assert float(agg["avg_construction_material_shortage_blocks"]) == 6.0
    assert float(agg["avg_houses_completed_count"]) == 3.0
    assert float(agg["avg_storage_completed_count"]) == 1.0
    assert float(agg["avg_storage_completion_rate"]) == 0.25
    assert float(agg["avg_construction_delivery_attempts"]) == 12.0
    assert float(agg["avg_construction_delivery_successes"]) == 7.0
    assert float(agg["avg_construction_delivery_failures"]) == 5.0
    assert float(agg["avg_construction_delivery_to_site_events"]) == 6.0
    assert float(agg["avg_construction_delivery_to_wrong_target_or_drift"]) == 2.0
    assert float(agg["avg_construction_delivery_avg_distance_to_site"]) == 1.1
    assert float(agg["avg_construction_delivery_avg_distance_to_source"]) == 3.4
    assert float(agg["avg_storage_delivery_failures"]) == 3.0
    assert float(agg["avg_house_delivery_failures"]) == 2.0
    assert float(agg["avg_storage_delivery_successes"]) == 2.0
    assert float(agg["avg_house_delivery_successes"]) == 5.0
    assert float(agg["avg_construction_site_waiting_for_material_ticks"]) == 40.0
    assert float(agg["avg_construction_site_waiting_for_builder_ticks"]) == 10.0
    assert float(agg["avg_construction_site_waiting_total_ticks"]) == 70.0
    assert float(agg["avg_construction_site_progress_active_ticks"]) == 22.0
    assert float(agg["avg_construction_site_starved_cycles"]) == 9.0
    assert float(agg["avg_storage_waiting_for_material_ticks"]) == 21.0
    assert float(agg["avg_house_waiting_for_material_ticks"]) == 19.0
    assert float(agg["avg_storage_waiting_for_builder_ticks"]) == 6.0
    assert float(agg["avg_house_waiting_for_builder_ticks"]) == 4.0
    assert float(agg["avg_construction_site_lifetime_ticks_avg"]) == 53.0
    assert float(agg["avg_construction_site_progress_before_abandon_avg"]) == 1.5
    assert float(agg["avg_construction_site_material_units_delivered_avg"]) == 4.8
    assert float(agg["avg_construction_site_material_units_missing_avg"]) == 2.2
    assert float(agg["avg_construction_site_material_units_required_total"]) == 18.0
    assert float(agg["avg_construction_site_material_units_delivered_total"]) == 11.0
    assert float(agg["avg_construction_site_material_units_remaining"]) == 7.0
    assert float(agg["avg_construction_near_complete_sites_count"]) == 1.0
    assert float(agg["avg_builder_assigned_site_count"]) == 5.0
    assert float(agg["avg_builder_work_tick_applied_count"]) == 7.0
    assert float(agg["avg_construction_site_buildable_ticks_total"]) == 25.0
    assert float(agg["avg_construction_site_material_ready_to_first_work_delay_avg"]) == 5.5
    assert float(agg["avg_construction_site_completion_time_avg"]) == 45.0
    assert float(agg["avg_construction_time_first_delivery_to_completion_avg"]) == 20.0
    assert float(agg["avg_construction_time_first_progress_to_completion_avg"]) == 15.0
    assert float(agg["avg_construction_completed_after_first_delivery_count"]) == 2.0
    assert float(agg["avg_construction_completed_after_started_progress_count"]) == 2.0
    assert float(agg["avg_house_completion_time_avg"]) == 40.0
    assert float(agg["avg_storage_completion_time_avg"]) == 60.0
