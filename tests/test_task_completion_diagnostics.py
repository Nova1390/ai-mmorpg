from __future__ import annotations

from agent import Agent
import systems.building_system as building_system
from world import World


def _world() -> tuple[World, dict]:
    world = World(width=28, height=28, num_agents=0, seed=202, llm_enabled=False)
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    village = {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 10, "y": 10},
        "houses": 4,
        "population": 6,
        "storage": {"food": 0, "wood": 10, "stone": 10},
        "storage_pos": {"x": 10, "y": 10},
        "tier": 2,
        "needs": {},
        "metrics": {},
    }
    world.villages = [village]
    return world, village


def _completion(world: World) -> dict:
    return world.compute_task_completion_snapshot()


def test_farmer_failure_reason_when_farm_unavailable() -> None:
    world, _ = _world()
    farmer = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    farmer.village_id = 1
    farmer.role = "farmer"
    world.agents = [farmer]

    assert world.work_farm(farmer) is False
    diag = _completion(world)
    farm_work = diag["global"]["farm_work"]
    assert int(farm_work["preconditions_failed_count"]) >= 1
    assert int(farm_work["failure_reasons"].get("no_farm_available", 0)) >= 1


def test_farmer_productive_completion_when_farm_work_succeeds() -> None:
    world, _ = _world()
    farmer = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    farmer.village_id = 1
    farmer.role = "farmer"
    world.agents = [farmer]
    world.farms.add((10, 10))
    world.farm_plots[(10, 10)] = {"x": 10, "y": 10, "state": "prepared", "growth": 0, "village_id": 1}

    assert world.work_farm(farmer) is True
    diag = _completion(world)
    farm_work = diag["global"]["farm_work"]
    assert int(farm_work["preconditions_met_count"]) >= 1
    assert int(farm_work["productive_completion_count"]) >= 1


def test_builder_failure_reason_when_site_out_of_range() -> None:
    world, _ = _world()
    builder = Agent(x=1, y=1, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    world.agents = [builder]

    assert world.try_build_storage(builder) is False
    diag = _completion(world)
    build_storage = diag["global"]["build_storage"]
    assert int(build_storage["preconditions_failed_count"]) >= 1
    assert int(build_storage["failure_reasons"].get("site_not_in_range", 0)) >= 1


def test_builder_far_from_storage_does_not_emit_inventory_failure_spam() -> None:
    world, _ = _world()
    builder = Agent(x=1, y=1, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    world.agents = [builder]

    assert world.try_build_storage(builder) is False
    diag = _completion(world)
    reasons = diag["global"]["build_storage"]["failure_reasons"]
    # Out-of-range should dominate; missing-inventory should not be emitted just because builder is far from storage.
    assert int(reasons.get("site_not_in_range", 0)) >= 1
    assert int(reasons.get("no_materials_in_inventory", 0)) == 0


def test_builder_productive_completion_when_progress_applied() -> None:
    world, _ = _world()
    builder = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    world.agents = [builder]
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 10,
        "y": 10,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {
            "wood_needed": 4,
            "wood_reserved": 0,
            "stone_needed": 2,
            "stone_reserved": 0,
            "food_needed": 0,
            "food_reserved": 0,
        },
        "construction_buffer": {"wood": 4, "stone": 2, "food": 0},
        "construction_progress": 0,
        "construction_required_work": 1,
    }

    assert world.try_build_storage(builder) is True
    diag = _completion(world)
    assert int(diag["global"]["construction_progress"]["productive_completion_count"]) >= 1
    assert int(diag["global"]["build_storage"]["productive_completion_count"]) >= 1


def test_builder_keeps_build_storage_task_when_active_site_exists() -> None:
    world, village = _world()
    village["storage"]["wood"] = 0
    village["storage"]["stone"] = 0
    village["needs"] = {"need_storage": True}
    builder = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    builder.task = "build_storage"
    world.agents = [builder]
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 10,
        "y": 10,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {
            "wood_needed": 4,
            "wood_reserved": 0,
            "stone_needed": 2,
            "stone_reserved": 0,
            "food_needed": 0,
            "food_reserved": 0,
        },
        "construction_buffer": {"wood": 0, "stone": 0, "food": 0},
        "construction_progress": 0,
        "construction_required_work": 2,
    }

    builder.update(world)
    assert builder.task == "build_storage"


def test_builder_started_site_stickiness_suppresses_immediate_inventory_bounce() -> None:
    world, village = _world()
    village["storage"]["wood"] = 0
    village["storage"]["stone"] = 0
    village["needs"] = {"need_storage": True}
    world.tick = 200
    builder = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    builder.task = "build_storage"
    builder.inventory["wood"] = 0
    builder.inventory["stone"] = 0
    world.agents = [builder]
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 10,
        "y": 10,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {
            "wood_needed": 4,
            "wood_reserved": 0,
            "stone_needed": 2,
            "stone_reserved": 0,
            "food_needed": 0,
            "food_reserved": 0,
        },
        "construction_buffer": {"wood": 0, "stone": 0, "food": 0},
        "construction_progress": 1,
        "construction_required_work": 6,
        "construction_last_progress_tick": 199,
        "construction_delivered_units": 2,
    }
    builder.assigned_building_id = "b-site"

    builder.update(world)

    assert builder.task == "build_storage"
    assert str(builder.primary_commitment_target_id or "") == "b-site"


def test_construction_commitment_created_when_builder_owns_site() -> None:
    world, village = _world()
    village["needs"] = {"need_storage": True}
    builder = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    builder.task = "build_storage"
    world.agents = [builder]
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 10,
        "y": 10,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0, "food_needed": 0, "food_reserved": 0},
        "construction_buffer": {"wood": 0, "stone": 0, "food": 0},
        "construction_progress": 1,
        "construction_required_work": 6,
        "construction_delivered_units": 2,
        "construction_last_progress_tick": 0,
    }
    builder.assigned_building_id = "b-site"

    builder.update_role_task(world)

    assert builder.primary_commitment_type == "finish_construction"
    assert builder.primary_commitment_target_id == "b-site"
    assert builder.primary_commitment_status == "active"
    snap = world.compute_settlement_progression_snapshot()
    assert int(snap["builder_commitment_created_count"]) >= 1


def test_construction_commitment_pauses_for_rest_and_resumes() -> None:
    world, village = _world()
    village["needs"] = {"need_storage": True}
    builder = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    builder.task = "build_storage"
    builder.assigned_building_id = "b-site"
    builder.primary_commitment_type = "finish_construction"
    builder.primary_commitment_target_id = "b-site"
    builder.primary_commitment_status = "active"
    builder.primary_commitment_created_tick = 0
    world.agents = [builder]
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 10,
        "y": 10,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0, "food_needed": 0, "food_reserved": 0},
        "construction_buffer": {"wood": 0, "stone": 0, "food": 0},
        "construction_progress": 1,
        "construction_required_work": 6,
        "construction_delivered_units": 2,
        "construction_last_progress_tick": 0,
    }

    world.tick = 3
    builder.sleep_need = 90.0
    builder.hunger = 80.0
    builder.update_role_task(world)
    assert builder.task == "rest"
    assert builder.primary_commitment_status == "paused"
    assert builder.primary_commitment_paused_reason == "needs_rest"

    world.tick = 3
    builder.sleep_need = 0.0
    builder.update_role_task(world)
    assert builder.task == "build_storage"
    assert builder.primary_commitment_status == "active"
    assert builder.primary_commitment_target_id == "b-site"
    snap = world.compute_settlement_progression_snapshot()
    assert int(snap["builder_commitment_pause_count"]) >= 1
    assert int(snap["builder_commitment_resume_count"]) >= 1


def test_construction_commitment_clears_on_completion_or_invalidation() -> None:
    world, village = _world()
    village["needs"] = {"need_storage": True}
    builder = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    builder.task = "build_storage"
    builder.primary_commitment_type = "finish_construction"
    builder.primary_commitment_target_id = "b-site"
    builder.primary_commitment_status = "active"
    builder.primary_commitment_created_tick = 0
    world.agents = [builder]
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 10,
        "y": 10,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "active",
    }

    builder.update_role_task(world)
    assert builder.primary_commitment_type == "none"
    snap = world.compute_settlement_progression_snapshot()
    assert int(snap["builder_commitment_completed_count"]) >= 1

    # Recreate and ensure invalidation clears as abandoned.
    builder.primary_commitment_type = "finish_construction"
    builder.primary_commitment_target_id = "b-missing"
    builder.primary_commitment_status = "active"
    builder.primary_commitment_created_tick = int(world.tick)
    builder.update_role_task(world)
    assert builder.primary_commitment_type == "none"
    snap2 = world.compute_settlement_progression_snapshot()
    assert int(snap2["builder_commitment_abandoned_count"]) >= 1


def test_builder_can_seed_commitment_from_existing_site_without_assignment() -> None:
    world, village = _world()
    village["needs"] = {"need_storage": True}
    builder = Agent(x=9, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    builder.task = "idle"
    world.agents = [builder]
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 12,
        "y": 10,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0, "food_needed": 0, "food_reserved": 0},
        "construction_buffer": {"wood": 1, "stone": 0, "food": 0},
        "construction_progress": 1,
        "construction_required_work": 6,
        "construction_delivered_units": 1,
        "construction_last_progress_tick": 0,
    }

    builder.update_role_task(world)
    assert builder.primary_commitment_type == "finish_construction"
    assert builder.primary_commitment_target_id == "b-site"
    assert builder.task == "build_storage"


def test_gather_materials_returns_to_committed_site_task() -> None:
    world, village = _world()
    village["needs"] = {"need_storage": True}
    builder = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    builder.task = "gather_materials"
    builder.primary_commitment_type = "finish_construction"
    builder.primary_commitment_target_id = "b-site"
    builder.primary_commitment_status = "active"
    builder.inventory["wood"] = 1
    world.agents = [builder]
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 10,
        "y": 10,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0, "food_needed": 0, "food_reserved": 0},
        "construction_buffer": {"wood": 0, "stone": 0, "food": 0},
        "construction_progress": 0,
        "construction_required_work": 6,
    }

    builder.update(world)
    assert builder.task == "build_storage"
    assert str(builder.assigned_building_id) == "b-site"


def test_no_immediate_bounce_after_first_useful_work_tick_when_built_false() -> None:
    world, village = _world()
    village["needs"] = {"need_storage": True}
    builder = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    builder.task = "build_storage"
    builder.assigned_building_id = "b-site"
    world.agents = [builder]
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 10,
        "y": 10,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0, "food_needed": 0, "food_reserved": 0},
        "construction_buffer": {"wood": 1, "stone": 0, "food": 0},
        "construction_progress": 0,
        "construction_required_work": 6,
        "construction_last_progress_tick": -100,
    }

    builder.update(world)

    assert builder.task == "build_storage"
    assert int(world.buildings["b-site"]["construction_progress"]) >= 1


def test_commitment_hold_succeeds_via_recent_builder_progress_grace() -> None:
    world, _ = _world()
    world.tick = 100
    builder = Agent(x=0, y=0, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    builder.primary_commitment_type = "finish_construction"
    builder.primary_commitment_target_id = "b-site"
    builder.primary_commitment_last_progress_tick = 99
    site = {
        "building_id": "b-site",
        "type": "storage",
        "x": 20,
        "y": 20,
        "operational_state": "under_construction",
        "construction_progress": 1,
        "construction_required_work": 6,
        "construction_delivered_units": 0,
        "construction_buffer": {"wood": 0, "stone": 0, "food": 0},
        "construction_last_progress_tick": 10,
        "construction_last_delivery_tick": 10,
    }

    assert builder._should_hold_construction_site_commitment(world, site) is True


def test_stickiness_window_preserves_build_context_after_recent_progress() -> None:
    world, village = _world()
    village["priority"] = "secure_food"
    village["needs"] = {"need_storage": False, "need_housing": False}
    world.tick = 150
    builder = Agent(x=0, y=0, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    builder.task = "build_storage"
    builder.assigned_building_id = "b-site"
    builder.construction_site_commit_site_id = "b-site"
    builder.construction_site_commit_until_tick = 160
    world.agents = [builder]
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 20,
        "y": 20,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0, "food_needed": 0, "food_reserved": 0},
        "construction_buffer": {"wood": 0, "stone": 0, "food": 0},
        "construction_progress": 1,
        "construction_required_work": 6,
        "construction_delivered_units": 1,
        "construction_last_progress_tick": 149,
    }

    builder.update_role_task(world)

    assert builder.task == "build_storage"


def test_hauler_failure_reason_when_no_delivery_target_exists() -> None:
    world, _ = _world()
    hauler = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    hauler.village_id = 1
    hauler.role = "hauler"
    world.agents = [hauler]

    assert building_system.run_hauler_construction_delivery(world, hauler) is False
    diag = _completion(world)
    delivery = diag["global"]["construction_delivery"]
    assert int(delivery["preconditions_failed_count"]) >= 1
    assert int(delivery["failure_reasons"].get("no_delivery_target", 0)) >= 1


def test_hauler_no_target_clears_delivery_state_and_avoids_stale_loop() -> None:
    world, _ = _world()
    hauler = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    hauler.village_id = 1
    hauler.role = "hauler"
    hauler.delivery_target_building_id = "ghost-site"
    hauler.delivery_resource_type = "wood"
    hauler.delivery_reserved_amount = 2
    world.agents = [hauler]

    assert building_system.run_hauler_construction_delivery(world, hauler) is False
    assert hauler.delivery_target_building_id is None
    assert hauler.delivery_resource_type is None
    assert int(hauler.delivery_reserved_amount) == 0


def test_hauler_productive_completion_when_deposit_succeeds() -> None:
    world, _ = _world()
    hauler = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    hauler.village_id = 1
    hauler.role = "hauler"
    hauler.inventory["wood"] = 3
    world.agents = [hauler]
    world.buildings["b-storage"] = {
        "building_id": "b-storage",
        "type": "storage",
        "x": 10,
        "y": 10,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "active",
        "storage": {"food": 0, "wood": 0, "stone": 0},
        "storage_capacity": 50,
    }

    assert building_system.deposit_agent_inventory_to_storage(world, hauler) is True
    diag = _completion(world)
    deposit = diag["global"]["deposit_to_storage"]
    assert int(deposit["preconditions_met_count"]) >= 1
    assert int(deposit["productive_completion_count"]) >= 1
