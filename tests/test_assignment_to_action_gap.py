from __future__ import annotations

from agent import Agent
from brain import FoodBrain
import systems.building_system as building_system
from world import World


def _world() -> tuple[World, dict]:
    world = World(width=28, height=28, num_agents=0, seed=99, llm_enabled=False)
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    village = {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 10, "y": 10},
        "houses": 4,
        "population": 6,
        "storage": {"food": 4, "wood": 8, "stone": 8},
        "storage_pos": {"x": 10, "y": 10},
        "tier": 2,
        "needs": {},
        "metrics": {
            "workforce_target_mix": {"farmer": 1, "forager": 1, "hauler": 1, "builder": 1}
        },
    }
    world.villages = [village]
    return world, village


def _gap(world: World) -> dict:
    return world.compute_assignment_to_action_gap_snapshot()


def test_assigned_farmer_selecting_task_increments_task_selected_count() -> None:
    world, _ = _world()
    farmer = Agent(x=10, y=10, brain=FoodBrain(), is_player=False, player_id=None)
    farmer.village_id = 1
    farmer.role = "farmer"
    world.agents = [farmer]

    farmer.update(world)
    diag = _gap(world)
    assert int(diag["global"]["farmer"]["task_selected_count"]) >= 1


def test_farmer_with_no_farm_target_increments_block_reason() -> None:
    world, _ = _world()
    farmer = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    farmer.village_id = 1
    farmer.role = "farmer"
    world.agents = [farmer]

    farmer.update(world)
    diag = _gap(world)
    reasons = diag["global"]["farmer"]["block_reasons"]
    assert int(reasons.get("no_target_candidate", 0)) >= 1


def test_forager_visible_food_reaches_target_attempt_and_productive_action() -> None:
    world, _ = _world()
    forager = Agent(x=10, y=10, brain=FoodBrain(), is_player=False, player_id=None)
    forager.village_id = 1
    forager.role = "forager"
    world.food.add((11, 10))
    world.agents = [forager]

    forager.update(world)
    diag = _gap(world)
    role = diag["global"]["forager"]
    assert int(role["target_found_count"]) >= 1
    assert int(role["action_attempted_count"]) >= 1
    assert int(role["productive_action_count"]) >= 1


def test_hauler_without_delivery_target_records_no_construction_site_reason() -> None:
    world, _ = _world()
    hauler = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    hauler.village_id = 1
    hauler.role = "hauler"
    world.agents = [hauler]

    assert building_system.run_hauler_construction_delivery(world, hauler) is False
    diag = _gap(world)
    reasons = diag["global"]["hauler"]["block_reasons"]
    assert int(reasons.get("no_construction_site", 0)) >= 1


def test_builder_with_site_path_increments_movement_attempt_and_productive_stages() -> None:
    world, _ = _world()
    world.villages[0]["needs"] = {"need_storage": True}
    builder = Agent(x=9, y=10, brain=FoodBrain(), is_player=False, player_id=None)
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

    builder.update(world)
    diag = _gap(world)
    role = diag["global"]["builder"]
    assert int(role["movement_started_count"]) >= 1
    assert int(role["action_attempted_count"]) >= 1
    assert int(role["productive_action_count"]) >= 1


def test_assignment_gap_affiliation_summary_updates() -> None:
    world, _ = _world()
    resident = Agent(x=10, y=10, brain=FoodBrain(), is_player=False, player_id=None)
    resident.village_id = 1
    resident.role = "farmer"
    resident.village_affiliation_status = "resident"
    resident.home_village_uid = "v-000001"
    resident.primary_village_uid = "v-000001"
    attached = Agent(x=10, y=11, brain=FoodBrain(), is_player=False, player_id=None)
    attached.village_id = 1
    attached.role = "forager"
    attached.village_affiliation_status = "attached"
    attached.primary_village_uid = "v-000001"
    world.agents = [resident, attached]
    world.farms.add((10, 10))
    world.farm_plots[(10, 10)] = {"x": 10, "y": 10, "state": "prepared", "growth": 0, "village_id": 1}
    world.food.add((10, 11))

    resident.update(world)
    attached.update(world)

    diag = _gap(world)
    by_aff = diag["by_affiliation"]
    total_assigned = sum(int(v.get("assigned_role_count", 0)) for v in by_aff.values())
    total_task_selected = sum(int(v.get("task_selected_count", 0)) for v in by_aff.values())
    total_productive = sum(int(v.get("productive_action_count", 0)) for v in by_aff.values())
    assert total_assigned >= 2
    assert total_task_selected >= 2
    assert total_productive >= 1
