from __future__ import annotations

from agent import Agent
from brain import FoodBrain
from world import World


def _world() -> tuple[World, dict]:
    world = World(width=28, height=28, num_agents=0, seed=303, llm_enabled=False)
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    village = {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 10, "y": 10},
        "houses": 4,
        "population": 8,
        "storage": {"food": 3, "wood": 0, "stone": 0},
        "storage_pos": {"x": 10, "y": 10},
        "tier": 2,
        "needs": {},
        "metrics": {},
    }
    world.villages = [village]
    return world, village


def test_farmer_task_not_selected_when_no_valid_farm_exists() -> None:
    world, _ = _world()
    farmer = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    farmer.village_id = 1
    farmer.role = "farmer"
    world.agents = [farmer]

    farmer.update_role_task(world)
    assert farmer.task != "farm_cycle"
    assert farmer.task == "gather_food_wild"


def test_farmer_task_selected_when_real_farm_is_workable() -> None:
    world, _ = _world()
    farmer = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    farmer.village_id = 1
    farmer.role = "farmer"
    world.agents = [farmer]
    world.farms.add((10, 10))
    world.farm_plots[(10, 10)] = {"x": 10, "y": 10, "state": "prepared", "growth": 0, "village_id": 1}

    farmer.update_role_task(world)
    assert farmer.task == "farm_cycle"


def test_farm_work_productive_completion_occurs_under_valid_conditions() -> None:
    world, _ = _world()
    farmer = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    farmer.village_id = 1
    farmer.role = "farmer"
    world.agents = [farmer]
    world.farms.add((10, 10))
    world.farm_plots[(10, 10)] = {"x": 10, "y": 10, "state": "prepared", "growth": 0, "village_id": 1}

    farmer.task = "farm_cycle"
    farmer.update(world)

    completion = world.compute_task_completion_snapshot()
    farm_work = completion["global"]["farm_work"]
    assert int(farm_work["productive_completion_count"]) >= 1
    assert int(farm_work["preconditions_met_count"]) >= 1


def test_tuning_does_not_create_unconditional_farm_availability() -> None:
    world, village = _world()
    farmer = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    farmer.village_id = 1
    farmer.role = "farmer"
    world.agents = [farmer]

    assert world.is_farmer_task_viable(farmer) is False
    village["storage"]["wood"] = 2
    assert world.is_farmer_task_viable(farmer) is True


def test_food_pressured_village_can_bootstrap_first_farm_with_plausible_local_material_path() -> None:
    world, village = _world()
    village["needs"] = {"food_low": True}
    farmer = Agent(x=10, y=10, brain=FoodBrain(), is_player=False, player_id=None)
    farmer.village_id = 1
    farmer.role = "farmer"
    world.agents = [farmer]
    # Plausible first-farm bootstrap path: nearby wood + valid grass tile.
    world.wood.add((10, 10))

    for _ in range(4):
        world.tick += 1
        farmer.update(world)
        if world.farm_plots:
            break
    assert len(world.farm_plots) >= 1


def test_no_plausible_site_or_material_still_prevents_first_farm() -> None:
    world, village = _world()
    village["needs"] = {"food_low": True}
    # Block all local terrain for farm placement.
    for y in range(world.height):
        for x in range(world.width):
            world.tiles[y][x] = "W"
    farmer = Agent(x=10, y=10, brain=FoodBrain(), is_player=False, player_id=None)
    farmer.village_id = 1
    farmer.role = "farmer"
    world.agents = [farmer]

    for _ in range(3):
        world.tick += 1
        farmer.update(world)
    assert len(world.farm_plots) == 0


def test_no_viable_farm_does_not_reintroduce_invalid_farm_work_attempts() -> None:
    world, _ = _world()
    farmer = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    farmer.village_id = 1
    farmer.role = "farmer"
    world.agents = [farmer]

    world.tick += 1
    farmer.update(world)
    completion = world.compute_task_completion_snapshot()
    assert int(completion["global"]["farm_work"]["task_attempt_count"]) == 0


def test_farmer_prefers_existing_viable_farm_over_wood_fallback() -> None:
    world, _ = _world()
    farmer = Agent(x=10, y=10, brain=FoodBrain(), is_player=False, player_id=None)
    farmer.village_id = 1
    farmer.role = "farmer"
    farmer.task = "farm_cycle"
    world.agents = [farmer]
    # Existing workable farm and nearby wood: farm should be prioritized.
    world.farms.add((11, 10))
    world.farm_plots[(11, 10)] = {"x": 11, "y": 10, "state": "prepared", "growth": 0, "village_id": 1}
    world.wood.add((10, 11))

    action = farmer.brain.decide(farmer, world)
    assert isinstance(action, tuple) and action[0] == "move"
    assert (farmer.x + int(action[1]), farmer.y + int(action[2])) == (11, 10)


def test_farmer_keeps_farm_cycle_when_viable_farm_opportunity_remains() -> None:
    world, _ = _world()
    farmer = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    farmer.village_id = 1
    farmer.role = "farmer"
    farmer.task = "farm_cycle"
    world.agents = [farmer]
    world.farms.add((10, 10))
    world.farm_plots[(10, 10)] = {"x": 10, "y": 10, "state": "prepared", "growth": 0, "village_id": 1}

    farmer.update_role_task(world)
    assert farmer.task == "farm_cycle"


def test_farmer_survival_override_still_applies_under_true_crisis() -> None:
    world, _ = _world()
    farmer = Agent(x=10, y=10, brain=FoodBrain(), is_player=False, player_id=None)
    farmer.village_id = 1
    farmer.role = "farmer"
    farmer.task = "farm_cycle"
    farmer.hunger = 10
    world.agents = [farmer]
    world.farms.add((11, 10))
    world.farm_plots[(11, 10)] = {"x": 11, "y": 10, "state": "prepared", "growth": 0, "village_id": 1}
    world.food.add((10, 11))

    action = farmer.brain.decide(farmer, world)
    assert isinstance(action, tuple) and action[0] == "move"
    assert (farmer.x + int(action[1]), farmer.y + int(action[2])) == (10, 11)


def test_builder_keeps_valid_productive_task_for_short_persistence_window() -> None:
    world, village = _world()
    builder = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    builder.task = "build_house"
    builder.role_task_persisted_task = "build_house"
    builder.role_task_persistence_until_tick = world.tick + 4
    world.agents = [builder]
    # New policy pressure appears, but ongoing construction pressure still exists.
    village["priority"] = "build_storage"
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "house",
        "x": 11,
        "y": 10,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
    }

    builder.update_role_task(world)
    assert builder.task == "build_house"


def test_hauler_keeps_logistics_task_when_local_needs_remain_valid() -> None:
    world, village = _world()
    hauler = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    hauler.village_id = 1
    hauler.role = "hauler"
    hauler.task = "food_logistics"
    hauler.role_task_persisted_task = "food_logistics"
    hauler.role_task_persistence_until_tick = world.tick + 4
    world.agents = [hauler]
    village["priority"] = "stabilize"
    village["storage"]["food"] = 1

    hauler.update_role_task(world)
    assert hauler.task == "food_logistics"


def test_role_task_persistence_expires_and_allows_retargeting() -> None:
    world, village = _world()
    builder = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    builder.task = "build_house"
    builder.role_task_persisted_task = "build_house"
    builder.role_task_persistence_until_tick = world.tick
    world.agents = [builder]
    village["priority"] = "build_storage"
    world.tick += 10

    builder.update_role_task(world)
    assert builder.task == "build_storage"


def test_true_crisis_preempts_task_persistence_bias() -> None:
    world, village = _world()
    builder = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    builder.task = "build_house"
    builder.hunger = 10
    builder.role_task_persisted_task = "build_house"
    builder.role_task_persistence_until_tick = world.tick + 5
    world.agents = [builder]
    village["priority"] = "build_storage"
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "house",
        "x": 11,
        "y": 10,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
    }

    builder.update_role_task(world)
    assert builder.task == "build_storage"
