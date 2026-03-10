from __future__ import annotations

from agent import Agent
import systems.building_system as building_system
from world import World


def _world() -> World:
    world = World(width=28, height=28, num_agents=0, seed=1707, llm_enabled=False)
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    world.villages = [
        {
            "id": 1,
            "village_uid": "v-000001",
            "center": {"x": 10, "y": 10},
            "houses": 2,
            "population": 6,
            "storage": {"food": 0, "wood": 20, "stone": 20},
            "storage_pos": {"x": 10, "y": 10},
            "tier": 2,
            "needs": {},
            "metrics": {},
        }
    ]
    world.buildings["b-storage"] = {
        "building_id": "b-storage",
        "type": "storage",
        "x": 10,
        "y": 10,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "active",
        "storage": {"food": 0, "wood": 20, "stone": 20},
        "storage_capacity": 250,
    }
    return world


def _builder(x: int = 10, y: int = 10) -> Agent:
    a = Agent(x=x, y=y, brain=None, is_player=False, player_id=None)
    a.role = "builder"
    a.village_id = 1
    return a


def _hauler(x: int = 10, y: int = 10) -> Agent:
    a = Agent(x=x, y=y, brain=None, is_player=False, player_id=None)
    a.role = "hauler"
    a.village_id = 1
    return a


def test_house_site_creation_increments_housing_funnel_stage() -> None:
    world = _world()
    builder = _builder()
    world.agents = [builder]

    building_system.try_build_house(world, builder)
    diag = world.compute_housing_construction_diagnostics_snapshot()["global"]
    assert int(diag.get("house_plan_requested", 0)) >= 1
    assert int(diag.get("house_site_created", 0)) >= 1


def test_house_delivery_attempt_updates_housing_counters() -> None:
    world = _world()
    builder = _builder()
    hauler = _hauler()
    world.agents = [builder, hauler]
    building_system.try_build_house(world, builder)
    site = next(
        b
        for b in world.buildings.values()
        if str(b.get("type", "")) == "house" and str(b.get("operational_state", "")) == "under_construction"
    )
    # First call reserves target and picks up; second call reaches delivery attempt/success.
    assert building_system.run_hauler_construction_delivery(world, hauler) is True
    hauler.x = int(site.get("x", hauler.x))
    hauler.y = int(site.get("y", hauler.y))
    assert building_system.run_hauler_construction_delivery(world, hauler) is True

    diag = world.compute_housing_construction_diagnostics_snapshot()["global"]
    assert int(diag.get("house_delivery_target_created", 0)) >= 1
    assert int(diag.get("house_delivery_reserved", 0)) >= 1
    assert int(diag.get("house_delivery_attempt", 0)) >= 1


def test_house_construction_progress_and_activation_stages_increment() -> None:
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
    builder = _builder(x=10, y=11)
    world.agents = [builder]

    assert building_system.try_build_house(world, builder) is True
    diag = world.compute_housing_construction_diagnostics_snapshot()["global"]
    assert int(diag.get("house_construction_progress_tick", 0)) >= 1
    assert int(diag.get("house_construction_completed", 0)) >= 1
    assert int(diag.get("house_building_activated", 0)) >= 1


def test_housing_failure_reason_records_deterministically() -> None:
    world = _world()
    hauler = _hauler()
    world.agents = [hauler]
    # No under-construction house site available: should fail delivery targeting.
    assert building_system.run_hauler_construction_delivery(world, hauler) is False
    diag = world.compute_housing_construction_diagnostics_snapshot()["global"]
    reasons = diag.get("failure_reasons", {})
    assert int(reasons.get("no_delivery_target", 0)) >= 1


def test_observability_exports_housing_construction_diagnostics() -> None:
    world = _world()
    builder = _builder()
    world.agents = [builder]
    building_system.try_build_house(world, builder)
    world.metrics_collector.collect(world)
    snap = world.metrics_collector.latest()["cognition_society"]
    assert "housing_construction_diagnostics_global" in snap
    assert "housing_construction_diagnostics_by_village" in snap
