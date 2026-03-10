from __future__ import annotations

from agent import Agent
import systems.building_system as building_system
from world import World


def _base_world() -> tuple[World, dict]:
    world = World(width=24, height=24, num_agents=0, seed=123, llm_enabled=False)
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    village = {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 10, "y": 10},
        "houses": 3,
        "population": 4,
        "storage": {"food": 0, "wood": 0, "stone": 0},
        "storage_pos": {"x": 10, "y": 10},
        "tier": 1,
        "needs": {},
        "metrics": {"workforce_target_mix": {"farmer": 1, "forager": 1, "hauler": 1, "builder": 1}},
    }
    world.villages = [village]
    return world, village


def test_assigned_farmer_farm_work_increments_productive_action_count() -> None:
    world, _ = _base_world()
    farmer = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    farmer.village_id = 1
    farmer.role = "farmer"
    world.agents = [farmer]
    world.farms.add((10, 10))
    world.farm_plots[(10, 10)] = {"x": 10, "y": 10, "state": "prepared", "growth": 0, "village_id": 1}

    assert world.work_farm(farmer) is True
    diag = world.compute_workforce_realization_snapshot()
    farmer_diag = diag["by_village"]["v-000001"]["farmer"]
    assert int(farmer_diag["productive_action_count"]) >= 1
    assert int(farmer_diag["assigned_count"]) == 1


def test_assigned_forager_gathering_increments_productive_action_count() -> None:
    world, _ = _base_world()
    forager = Agent(x=11, y=10, brain=None, is_player=False, player_id=None)
    forager.village_id = 1
    forager.role = "forager"
    world.agents = [forager]
    world.food.add((11, 10))

    world.autopickup(forager)
    diag = world.compute_workforce_realization_snapshot()
    forager_diag = diag["by_village"]["v-000001"]["forager"]
    assert int(forager_diag["productive_action_count"]) >= 1


def test_assigned_hauler_with_no_valid_delivery_path_increments_block_reason() -> None:
    world, _ = _base_world()
    hauler = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    hauler.village_id = 1
    hauler.role = "hauler"
    world.agents = [hauler]

    assert building_system.run_hauler_construction_delivery(world, hauler) is False
    diag = world.compute_workforce_realization_snapshot()
    reasons = diag["by_village"]["v-000001"]["hauler"]["block_reasons"]
    assert int(reasons.get("no_construction_site", 0)) >= 1


def test_assigned_builder_progressing_construction_increments_productive_action_count() -> None:
    world, _ = _base_world()
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
        "construction_required_work": 2,
    }

    assert world.try_build_storage(builder) is False
    diag = world.compute_workforce_realization_snapshot()
    builder_diag = diag["by_village"]["v-000001"]["builder"]
    assert int(builder_diag["productive_action_count"]) >= 1


def test_workforce_realization_includes_affiliation_contribution_counts() -> None:
    world, _ = _base_world()
    resident = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    resident.village_id = 1
    resident.role = "farmer"
    resident.village_affiliation_status = "resident"
    resident.home_village_uid = "v-000001"
    resident.primary_village_uid = "v-000001"
    attached = Agent(x=11, y=10, brain=None, is_player=False, player_id=None)
    attached.village_id = 1
    attached.role = "forager"
    attached.village_affiliation_status = "attached"
    attached.primary_village_uid = "v-000001"
    world.agents = [resident, attached]

    world.farms.add((10, 10))
    world.farm_plots[(10, 10)] = {"x": 10, "y": 10, "state": "prepared", "growth": 0, "village_id": 1}
    world.food.add((11, 10))

    assert world.work_farm(resident) is True
    world.autopickup(attached)

    diag = world.compute_workforce_realization_snapshot()
    by_aff_global = diag["affiliation_contribution"]["global"]
    assert int(by_aff_global["resident"]["productive_action_count"]) >= 1
    assert int(by_aff_global["attached"]["productive_action_count"]) >= 1
    assert "v-000001" in diag["by_village"]

