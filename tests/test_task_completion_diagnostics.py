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
