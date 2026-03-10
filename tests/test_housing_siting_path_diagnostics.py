from __future__ import annotations

from agent import Agent
import systems.building_system as building_system
from world import World


def _world() -> World:
    world = World(width=28, height=28, num_agents=0, seed=1901, llm_enabled=False)
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    village = {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 10, "y": 10},
        "houses": 1,
        "population": 8,
        "storage": {"food": 8, "wood": 30, "stone": 30},
        "storage_pos": {"x": 10, "y": 10},
        "tier": 1,
        "needs": {},
        "metrics": {},
    }
    world.villages = [village]
    world.buildings["b-storage"] = {
        "building_id": "b-storage",
        "type": "storage",
        "x": 10,
        "y": 10,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "active",
        "storage": {"food": 8, "wood": 30, "stone": 30},
        "storage_capacity": 250,
    }
    return world


def _builder(x: int = 10, y: int = 10) -> Agent:
    a = Agent(x=x, y=y, brain=None, is_player=False, player_id=None)
    a.role = "builder"
    a.village_id = 1
    return a


def test_overlap_rejection_reason_increments() -> None:
    world = _world()
    existing = world.place_building("house", 10, 11, village_id=1, village_uid="v-000001")
    assert existing is not None
    builder = _builder(10, 11)
    world.agents = [builder]
    # Force local scan to mostly invalid terrain so overlap point is deterministically exercised.
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            x = builder.x + dx
            y = builder.y + dy
            if 0 <= x < world.width and 0 <= y < world.height:
                world.tiles[y][x] = "W"
    world.tiles[11][10] = "G"
    assert building_system.try_build_house(world, builder) is False
    reasons = world.compute_housing_siting_rejection_snapshot()["global"]["rejection_reasons"]
    assert int(reasons.get("overlap_with_structure", 0)) >= 1


def test_blocked_by_road_rejection_reason_increments() -> None:
    world = _world()
    builder = _builder(10, 10)
    world.agents = [builder]
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            x = builder.x + dx
            y = builder.y + dy
            if 0 <= x < world.width and 0 <= y < world.height:
                world.roads.add((x, y))
    assert building_system.try_build_house(world, builder) is False
    reasons = world.compute_housing_siting_rejection_snapshot()["global"]["rejection_reasons"]
    assert int(reasons.get("blocked_by_road", 0)) >= 1


def test_terrain_invalid_rejection_reason_increments() -> None:
    world = _world()
    builder = _builder(10, 10)
    world.agents = [builder]
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            x = builder.x + dx
            y = builder.y + dy
            if 0 <= x < world.width and 0 <= y < world.height:
                world.tiles[y][x] = "W"
    assert building_system.try_build_house(world, builder) is False
    reasons = world.compute_housing_siting_rejection_snapshot()["global"]["rejection_reasons"]
    assert int(reasons.get("terrain_invalid", 0)) >= 1


def test_successful_candidate_increments_passed_and_site_created() -> None:
    world = _world()
    builder = _builder(11, 10)
    world.agents = [builder]
    assert building_system.try_build_house(world, builder) is False
    siting = world.compute_housing_siting_rejection_snapshot()["global"]
    assert int(siting.get("house_candidate_scan_started", 0)) >= 1
    assert int(siting.get("house_candidate_evaluated", 0)) >= 1
    assert int(siting.get("house_candidate_passed_all_checks", 0)) >= 1
    assert int(siting.get("house_site_created", 0)) >= 1


def test_bootstrap_house_increments_bootstrap_path_counter() -> None:
    world = _world()
    world.villages = []
    builder = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    builder.role = "builder"
    builder.village_id = None
    builder.inventory["wood"] = 6
    builder.inventory["stone"] = 4
    world.agents = [builder]
    assert building_system.try_build_house(world, builder) is True
    path = world.compute_housing_path_coherence_snapshot()["global"]
    assert int(path.get("house_created_via_bootstrap", 0)) >= 1


def test_normal_construction_completion_increments_progress_path_counter() -> None:
    world = _world()
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "house",
        "x": 10,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {
            "wood_needed": 0,
            "wood_reserved": 0,
            "stone_needed": 0,
            "stone_reserved": 0,
            "food_needed": 0,
            "food_reserved": 0,
        },
        "construction_buffer": {"wood": 5, "stone": 3, "food": 0},
        "construction_progress": 0,
        "construction_required_work": 1,
    }
    builder = _builder(10, 11)
    world.agents = [builder]
    assert building_system.try_build_house(world, builder) is True
    path = world.compute_housing_path_coherence_snapshot()["global"]
    assert int(path.get("house_completed_via_construction_progress", 0)) >= 1
    assert int(path.get("house_activated_via_completion_hook", 0)) >= 1


def test_observability_exports_housing_siting_and_path_fields() -> None:
    world = _world()
    builder = _builder(11, 10)
    world.agents = [builder]
    building_system.try_build_house(world, builder)
    world.metrics_collector.collect(world)
    snap = world.metrics_collector.latest()["cognition_society"]
    assert "housing_siting_rejection_global" in snap
    assert "housing_siting_rejection_by_village" in snap
    assert "housing_path_coherence_global" in snap
    assert "housing_path_coherence_by_village" in snap

