from __future__ import annotations

from agent import Agent
import server
from systems.scenario_runner import run_simulation_scenario
from world import World


def _flat_world() -> World:
    world = World(width=32, height=32, num_agents=0, seed=42, llm_enabled=False)
    world.agents = []
    world.villages = []
    world.buildings = {}
    world.structures = set()
    world.storage_buildings = set()
    world.food = set()
    world.wood = set()
    world.stone = set()
    world.roads = set()
    world.transport_tiles = {}
    return world


def test_scenario_runner_is_deterministic_with_fixed_seed() -> None:
    r1 = run_simulation_scenario(
        seed=77,
        width=30,
        height=30,
        initial_population=12,
        ticks=35,
        snapshot_interval=5,
        llm_enabled=False,
        history_limit=40,
    )
    r2 = run_simulation_scenario(
        seed=77,
        width=30,
        height=30,
        initial_population=12,
        ticks=35,
        snapshot_interval=5,
        llm_enabled=False,
        history_limit=40,
    )
    s1 = r1["summary"]
    s2 = r2["summary"]
    assert s1["tick"] == s2["tick"]
    assert s1["world"]["population"] == s2["world"]["population"]
    assert s1["world"]["villages"] == s2["world"]["villages"]
    assert s1["world"]["buildings_by_type"] == s2["world"]["buildings_by_type"]
    assert "total_food_gathered" in s1["production"]
    assert "direct_food_gathered" in s1["production"]
    assert "total_wood_gathered" in s1["production"]
    assert "direct_wood_gathered" in s1["production"]
    assert "total_stone_gathered" in s1["production"]
    assert "direct_stone_gathered" in s1["production"]


def test_metrics_collector_contains_core_fields() -> None:
    world = _flat_world()
    world.metrics_collector.collect(world)
    snapshot = world.metrics_collector.latest()
    assert "tick" in snapshot
    assert "world" in snapshot
    assert "logistics" in snapshot
    assert "production" in snapshot
    assert "cognition_society" in snapshot
    assert "llm_reflection" in snapshot
    assert "innovation" in snapshot
    assert "specialization_diagnostics" in snapshot
    assert "mine" in snapshot["specialization_diagnostics"]
    assert "lumberyard" in snapshot["specialization_diagnostics"]
    assert "readiness_breakdown" in snapshot["specialization_diagnostics"]["mine"]
    assert "requirement_breakdown" in snapshot["specialization_diagnostics"]["mine"]
    assert "proposal_counts_by_status" in snapshot["innovation"]
    assert "proposal_counts_by_effect" in snapshot["innovation"]
    assert "proposal_counts_by_category" in snapshot["innovation"]
    assert "prototype_attempt_count" in snapshot["innovation"]
    assert "prototype_built_count" in snapshot["innovation"]
    assert "prototype_failed_count" in snapshot["innovation"]
    assert "prototype_useful_count" in snapshot["innovation"]
    assert "prototype_neutral_count" in snapshot["innovation"]
    assert "prototype_ineffective_count" in snapshot["innovation"]
    assert "prototype_usefulness_by_effect" in snapshot["innovation"]
    assert "prototype_usefulness_by_category" in snapshot["innovation"]
    assert "known_invention_entry_count" in snapshot["innovation"]
    assert "agents_with_known_inventions" in snapshot["innovation"]
    assert "invention_knowledge_by_source" in snapshot["innovation"]
    assert "invention_knowledge_by_category" in snapshot["innovation"]
    assert "recent_diffused_inventions" in snapshot["innovation"]
    assert "recent_useful_prototypes" in snapshot["innovation"]
    assert "transport_network_counts" in snapshot["world"]
    assert "food_patch_count" in snapshot["world"]
    assert "food_patch_total_area" in snapshot["world"]
    assert "food_patch_food_spawned" in snapshot["world"]
    assert "village_population_resident" in snapshot["world"]
    assert "village_population_attached" in snapshot["world"]
    assert "village_population_transient" in snapshot["world"]
    assert "agents_unaffiliated" in snapshot["world"]
    assert "village_affiliation_by_village" in snapshot["world"]
    assert "workforce_target_mix_by_village" in snapshot["cognition_society"]
    assert "workforce_actual_mix_by_village" in snapshot["cognition_society"]
    assert "workforce_role_deficits_by_village" in snapshot["cognition_society"]
    assert "workforce_pressure_by_village" in snapshot["cognition_society"]
    assert "physiology_global" in snapshot["cognition_society"]
    assert "happiness_global" in snapshot["cognition_society"]
    assert "workforce_realization_global" in snapshot["cognition_society"]
    assert "workforce_realization_by_village" in snapshot["cognition_society"]
    assert "workforce_affiliation_contribution" in snapshot["cognition_society"]
    assert "workforce_realization_window_ticks" in snapshot["cognition_society"]
    assert "support_role_assignment_diagnostics_global" in snapshot["cognition_society"]
    assert "support_role_assignment_diagnostics_by_village" in snapshot["cognition_society"]
    assert "support_role_relaxation_diagnostics_global" in snapshot["cognition_society"]
    assert "support_role_relaxation_diagnostics_by_village" in snapshot["cognition_society"]
    assert "reserved_civic_support_global" in snapshot["cognition_society"]
    assert "reserved_civic_support_by_village" in snapshot["cognition_society"]
    assert "reserved_civic_support_gate_diagnostics_global" in snapshot["cognition_society"]
    assert "reserved_civic_support_gate_diagnostics_by_village" in snapshot["cognition_society"]
    assert "assignment_to_action_gap_global" in snapshot["cognition_society"]
    assert "assignment_to_action_gap_by_village" in snapshot["cognition_society"]
    assert "assignment_to_action_gap_by_affiliation" in snapshot["cognition_society"]
    assert "task_completion_diagnostics_global" in snapshot["cognition_society"]
    assert "task_completion_diagnostics_by_village" in snapshot["cognition_society"]
    assert "task_completion_diagnostics_by_affiliation" in snapshot["cognition_society"]
    assert "delivery_diagnostics_global" in snapshot["cognition_society"]
    assert "delivery_diagnostics_by_role" in snapshot["cognition_society"]
    assert "delivery_diagnostics_by_village" in snapshot["cognition_society"]
    assert "builder_self_supply_diagnostics" in snapshot["cognition_society"]
    assert "builder_self_supply_gate_diagnostics_global" in snapshot["cognition_society"]
    assert "builder_self_supply_gate_diagnostics_by_village" in snapshot["cognition_society"]
    assert "social_cohesion_global" in snapshot["cognition_society"]
    assert "social_cohesion_by_village" in snapshot["cognition_society"]
    assert "residence_stabilization_global" in snapshot["cognition_society"]
    assert "residence_stabilization_by_village" in snapshot["cognition_society"]
    assert "resident_conversion_gate_diagnostics_global" in snapshot["cognition_society"]
    assert "resident_conversion_gate_diagnostics_by_village" in snapshot["cognition_society"]
    assert "recovery_diagnostics_global" in snapshot["cognition_society"]
    assert "recovery_diagnostics_by_role" in snapshot["cognition_society"]
    assert "recovery_diagnostics_by_village" in snapshot["cognition_society"]
    assert "movement_diagnostics_global" in snapshot["cognition_society"]
    assert "movement_diagnostics_by_role" in snapshot["cognition_society"]
    assert "movement_diagnostics_by_task" in snapshot["cognition_society"]
    assert "movement_diagnostics_by_transport_context" in snapshot["cognition_society"]
    assert "movement_diagnostics_by_village" in snapshot["cognition_society"]
    assert "movement_diagnostics_top_oscillating_agents" in snapshot["cognition_society"]
    assert "movement_congestion_global" in snapshot["cognition_society"]
    assert "movement_congestion_by_role" in snapshot["cognition_society"]
    assert "movement_congestion_by_task" in snapshot["cognition_society"]
    assert "movement_congestion_by_transport_context" in snapshot["cognition_society"]
    assert "top_congested_tiles" in snapshot["cognition_society"]
    assert "camp_food_metrics" in snapshot["cognition_society"]
    assert "proto_specialization_global" in snapshot["cognition_society"]
    assert "home_return_events" in snapshot["cognition_society"]["social_cohesion_global"]


def test_observability_reports_village_affiliation_population_counts() -> None:
    world = _flat_world()
    world.villages = [
        {
            "id": 1,
            "village_uid": "v-000001",
            "center": {"x": 8, "y": 8},
            "houses": 4,
            "population": 8,
            "storage": {"food": 0, "wood": 0, "stone": 0},
            "storage_pos": {"x": 8, "y": 8},
            "tier": 2,
        }
    ]
    resident = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    resident.village_affiliation_status = "resident"
    resident.home_village_uid = "v-000001"
    resident.primary_village_uid = "v-000001"
    attached = Agent(x=8, y=9, brain=None, is_player=False, player_id=None)
    attached.village_affiliation_status = "attached"
    attached.primary_village_uid = "v-000001"
    transient = Agent(x=9, y=8, brain=None, is_player=False, player_id=None)
    transient.village_affiliation_status = "transient"
    transient.primary_village_uid = "v-000001"
    unaff = Agent(x=20, y=20, brain=None, is_player=False, player_id=None)
    unaff.village_affiliation_status = "unaffiliated"
    unaff.primary_village_uid = None
    world.agents = [resident, attached, transient, unaff]

    world.metrics_collector.collect(world)
    snapshot = world.metrics_collector.latest()
    assert snapshot["world"]["village_population_resident"] == 1
    assert snapshot["world"]["village_population_attached"] == 1
    assert snapshot["world"]["village_population_transient"] == 1
    assert snapshot["world"]["agents_unaffiliated"] == 1
    assert snapshot["world"]["village_affiliation_by_village"]["v-000001"] == {
        "resident": 1,
        "attached": 1,
        "transient": 1,
    }


def test_observability_includes_support_role_assignment_diagnostics() -> None:
    world = _flat_world()
    world.villages = [
        {
            "id": 1,
            "village_uid": "v-000001",
            "center": {"x": 8, "y": 8},
            "houses": 4,
            "population": 6,
            "storage": {"food": 0, "wood": 0, "stone": 0},
            "storage_pos": {"x": 8, "y": 8},
            "tier": 2,
            "metrics": {
                "support_role_assignment_diagnostics": {
                    "live_demand": True,
                    "under_construction_sites": 1,
                    "outstanding_materials": 6,
                    "recent_heartbeat_sites": 1,
                    "recent_builder_wait_sites": 1,
                    "reallocation_due": False,
                    "roles": {
                        "builder": {
                            "floor_requested": True,
                            "floor_required": 1,
                            "target_requested": 1,
                            "candidates_total": 4,
                            "candidates_eligible": 2,
                            "candidates_filtered_out": 2,
                            "selected_count": 1,
                            "selected_agent_ids": ["a-1"],
                            "floor_satisfied": True,
                            "previous_assigned_count": 0,
                            "final_assigned_count_after_pass": 1,
                            "filter_reasons": {"role_hold_block": 1},
                        },
                        "hauler": {
                            "floor_requested": True,
                            "floor_required": 1,
                            "target_requested": 1,
                            "candidates_total": 4,
                            "candidates_eligible": 1,
                            "candidates_filtered_out": 3,
                            "selected_count": 1,
                            "selected_agent_ids": ["a-2"],
                            "floor_satisfied": True,
                            "previous_assigned_count": 0,
                            "final_assigned_count_after_pass": 1,
                            "filter_reasons": {"already_selected_for_other_role": 1},
                        },
                    },
                },
                "support_role_relaxation_diagnostics": {
                    "roles": {
                        "builder": {
                            "live_demand_context_seen": 1,
                            "support_signal_recent_seen": 1,
                            "true_survival_crisis_seen": 0,
                            "population_safe_for_relaxation": 1,
                            "food_base_relaxation_budget_granted": 1,
                            "food_base_relaxation_budget_consumed": 1,
                            "hold_override_budget_granted": 1,
                            "hold_override_budget_consumed": 1,
                            "eligible_count": 1,
                            "short_circuit_reasons": {"candidate_became_eligible": 1},
                        },
                        "hauler": {
                            "live_demand_context_seen": 1,
                            "support_signal_recent_seen": 1,
                            "true_survival_crisis_seen": 0,
                            "population_safe_for_relaxation": 1,
                            "food_base_relaxation_budget_granted": 1,
                            "food_base_relaxation_budget_consumed": 0,
                            "hold_override_budget_granted": 1,
                            "hold_override_budget_consumed": 0,
                            "eligible_count": 1,
                            "short_circuit_reasons": {"hold_override_granted_but_not_used": 1},
                        },
                    }
                },
                "reserved_civic_support_metrics": {
                    "reserved_civic_support_activations": 2,
                    "reserved_civic_support_active_count": 1,
                    "reserved_civic_support_role_counts": {"builder": 1, "hauler": 1},
                    "reserved_civic_support_expired_count": 1,
                    "reserved_civic_support_released_reason_counts": {"slot_expired": 1},
                    "reserved_civic_support_supported_outcome_counts": {
                        "construction_delivery": 0,
                        "construction_progress": 0,
                    },
                },
                "reserved_civic_support_gate_diagnostics": {
                    "roles": {
                        "builder": {
                            "gate_evaluations": 1,
                            "live_construction_demand_seen": 1,
                            "support_signal_recent_seen": 1,
                            "true_survival_crisis_blocked": 0,
                            "population_not_safe_blocked": 0,
                            "support_floor_gap_seen": 1,
                            "support_floor_gap_count": 1,
                            "candidate_available_count": 1,
                            "slot_activation_granted": 1,
                            "slot_activation_block_reasons": {"slot_activated": 1},
                        },
                        "hauler": {
                            "gate_evaluations": 1,
                            "live_construction_demand_seen": 1,
                            "support_signal_recent_seen": 1,
                            "true_survival_crisis_blocked": 0,
                            "population_not_safe_blocked": 0,
                            "support_floor_gap_seen": 1,
                            "support_floor_gap_count": 1,
                            "candidate_available_count": 0,
                            "slot_activation_granted": 0,
                            "slot_activation_block_reasons": {"no_candidate_available": 1},
                        },
                    }
                },
            },
            "reserved_civic_support": {
                "reserved_civic_support_active": True,
                "reserved_civic_support_agent_id": "a-1",
                "reserved_civic_support_role": "builder",
                "reserved_civic_support_until_tick": 42,
                "reserved_civic_support_reason": "live_construction_support",
            },
        }
    ]

    world.metrics_collector.collect(world)
    snapshot = world.metrics_collector.latest()
    cog = snapshot["cognition_society"]
    assert "support_role_assignment_diagnostics_global" in cog
    assert "support_role_assignment_diagnostics_by_village" in cog
    assert "support_role_relaxation_diagnostics_global" in cog
    assert "support_role_relaxation_diagnostics_by_village" in cog
    assert "reserved_civic_support_global" in cog
    assert "reserved_civic_support_by_village" in cog
    assert "reserved_civic_support_gate_diagnostics_global" in cog
    assert "reserved_civic_support_gate_diagnostics_by_village" in cog
    by_village = cog["support_role_assignment_diagnostics_by_village"]
    assert "v-000001" in by_village
    assert "roles" in by_village["v-000001"]


def test_observability_includes_residence_stabilization_metrics() -> None:
    world = _flat_world()
    world.villages = [
        {
            "id": 1,
            "village_uid": "v-000001",
            "center": {"x": 8, "y": 8},
            "houses": 2,
            "population": 4,
            "storage": {"food": 0, "wood": 0, "stone": 0},
            "storage_pos": {"x": 8, "y": 8},
            "tier": 1,
        }
    ]
    world.record_resident_conversion_attempt(village_uid="v-000001")
    world.record_resident_conversion(village_uid="v-000001")
    world.record_resident_persistence(village_uid="v-000001")
    world.record_resident_release("house_missing_or_inactive", village_uid="v-000001")

    world.metrics_collector.collect(world)
    snapshot = world.metrics_collector.latest()
    cog = snapshot["cognition_society"]
    assert "residence_stabilization_global" in cog
    assert "residence_stabilization_by_village" in cog
    global_metrics = cog["residence_stabilization_global"]
    by_village = cog["residence_stabilization_by_village"]["v-000001"]
    assert int(global_metrics["resident_conversion_attempt_count"]) == 1
    assert int(global_metrics["resident_conversion_count"]) == 1
    assert int(global_metrics["resident_persistence_count"]) == 1
    assert int(global_metrics["resident_release_count"]) == 1
    assert int(global_metrics["resident_release_reasons"]["house_missing_or_inactive"]) == 1
    assert float(global_metrics["attached_to_resident_success_rate"]) == 1.0
    assert int(by_village["resident_conversion_count"]) == 1


def test_metrics_collector_reports_non_zero_production_after_real_gather() -> None:
    world = _flat_world()
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    village = {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 8, "y": 8},
        "houses": 4,
        "population": 8,
        "storage": {"food": 0, "wood": 0, "stone": 0},
        "storage_pos": {"x": 8, "y": 8},
        "tier": 2,
    }
    world.villages = [village]
    world.place_building("storage", 8, 8, village_id=1, village_uid=village["village_uid"])
    world.wood.update({(9, 7), (9, 8), (9, 9), (10, 8)})
    world.stone.update({(7, 7), (7, 8), (7, 9), (6, 8)})
    world.tiles[7][9] = "F"
    world.tiles[8][9] = "F"
    world.tiles[9][9] = "F"
    world.tiles[8][10] = "F"
    world.tiles[7][7] = "M"
    world.tiles[8][7] = "M"
    world.tiles[9][7] = "M"
    world.tiles[8][6] = "M"
    world.buildings["b-lumber"] = {
        "building_id": "b-lumber",
        "type": "lumberyard",
        "x": 9,
        "y": 8,
        "village_id": 1,
        "village_uid": village["village_uid"],
        "operational_state": "active",
        "linked_resource_type": "wood",
        "linked_resource_tiles_count": 4,
        "connected_to_road": True,
    }
    world.buildings["b-mine"] = {
        "building_id": "b-mine",
        "type": "mine",
        "x": 7,
        "y": 8,
        "village_id": 1,
        "village_uid": village["village_uid"],
        "operational_state": "active",
        "linked_resource_type": "stone",
        "linked_resource_tiles_count": 4,
        "connected_to_road": True,
    }
    world.food.add((8, 8))
    world.wood.add((9, 9))
    world.stone.add((7, 9))
    world.tiles[9][9] = "F"
    world.tiles[9][7] = "M"

    food_agent = Agent(x=8, y=8, brain=None)
    food_agent.village_id = 1
    wood_agent = Agent(x=9, y=9, brain=None)
    wood_agent.village_id = 1
    stone_agent = Agent(x=7, y=9, brain=None)
    stone_agent.village_id = 1
    world.autopickup(food_agent)
    assert world.gather_resource(wood_agent) is True
    assert world.gather_resource(stone_agent) is True

    world.metrics_collector.collect(world)
    production = world.metrics_collector.latest()["production"]
    assert int(production.get("total_food_gathered", 0)) > 0
    assert int(production.get("total_wood_gathered", 0)) > 0
    assert int(production.get("total_stone_gathered", 0)) > 0
    assert int(production.get("direct_wood_gathered", 0)) > 0
    assert int(production.get("direct_stone_gathered", 0)) > 0
    assert int(production.get("wood_from_lumberyards", 0)) > 0
    assert int(production.get("stone_from_mines", 0)) > 0


def test_history_buffer_is_bounded() -> None:
    world = _flat_world()
    world.metrics_collector.snapshot_interval = 1
    world.metrics_collector.history_size = 20
    for _ in range(80):
        world.update()
    hist = world.metrics_collector.history(limit=1000)
    assert len(hist) <= 240  # collector maxlen default clamp in constructor


def test_reflection_stats_counting() -> None:
    world = _flat_world()
    a = Agent(x=1, y=1, brain=None)
    a.role = "builder"
    world.record_reflection_trigger("blocked_intention")
    world.record_reflection_attempt(a, "blocked_intention")
    world.record_reflection_executed(a, "blocked_intention")
    world.record_reflection_outcome("accepted")
    world.record_reflection_outcome("rejected")
    world.record_reflection_skip("cooldown")
    stats = world.reflection_stats
    assert int(stats["reflection_trigger_detected_count"]) == 1
    assert int(stats["reflection_attempt_count"]) == 1
    assert int(stats["reflection_executed_count"]) == 1
    assert int(stats["reflection_success_count"]) == 1
    assert int(stats["reflection_rejection_count"]) == 1
    assert int(stats["reflection_skip_reason_counts"]["cooldown"]) == 1
    assert int(stats["reflection_reason_counts"]["blocked_intention"]) == 1
    assert int(stats["reflection_role_counts"]["builder"]) == 1
    assert int(stats["reflection_executed_reason_counts"]["blocked_intention"]) == 1
    assert int(stats["reflection_executed_role_counts"]["builder"]) == 1
    world.record_reflection_outcome("accepted", reason="deterministic_stub_used", source="stub")
    assert int(stats["reflection_accepted_source_counts"]["stub"]) == 1
    assert int(stats["reflection_outcome_reason_counts"]["deterministic_stub_used"]) == 1


def test_debug_metrics_endpoints_return_structure() -> None:
    world = _flat_world()
    world.update()
    original_world = server.world
    try:
        server.world = world
        metrics = server.get_debug_metrics()
        history_payload = server.get_debug_history(limit=10)
        assert "tick" in metrics
        assert "world" in metrics
        assert "production" in metrics
        assert "total_food_gathered" in metrics["production"]
        assert "history" in history_payload
        assert isinstance(history_payload["history"], list)
    finally:
        server.world = original_world


def test_social_cohesion_metrics_are_exported_with_village_breakdown() -> None:
    world = _flat_world()
    village = {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 8, "y": 8},
        "houses": 2,
        "population": 4,
        "storage": {"food": 6, "wood": 2, "stone": 1},
        "storage_pos": {"x": 8, "y": 8},
        "tier": 1,
    }
    world.villages = [village]
    world.buildings["b-home-1"] = {"building_id": "b-home-1", "type": "house", "x": 8, "y": 8, "village_id": 1, "village_uid": "v-000001", "operational_state": "active"}
    world.buildings["b-home-2"] = {"building_id": "b-home-2", "type": "house", "x": 9, "y": 8, "village_id": 1, "village_uid": "v-000001", "operational_state": "active"}
    resident = Agent(x=8, y=8, brain=None)
    resident.village_affiliation_status = "resident"
    resident.primary_village_uid = "v-000001"
    resident.home_village_uid = "v-000001"
    resident.home_building_id = "b-home-1"
    attached = Agent(x=9, y=8, brain=None)
    attached.village_affiliation_status = "attached"
    attached.primary_village_uid = "v-000001"
    world.agents = [resident, attached]
    world.record_social_gravity_event("return_to_village_events", village_uid="v-000001")

    world.metrics_collector.collect(world)
    snap = world.metrics_collector.latest()["cognition_society"]
    global_cohesion = snap["social_cohesion_global"]
    by_village = snap["social_cohesion_by_village"]
    assert int(global_cohesion.get("resident_count", 0)) >= 1
    assert int(global_cohesion.get("attached_count", 0)) >= 1
    assert "v-000001" in by_village
    assert int(by_village["v-000001"].get("occupied_house_count", 0)) >= 1
    assert int(by_village["v-000001"].get("return_to_village_events", 0)) >= 1
