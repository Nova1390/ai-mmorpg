from __future__ import annotations

from agent import Agent
import systems.building_system as building_system
from world import World


def _world() -> tuple[World, dict]:
    world = World(width=24, height=24, num_agents=0, seed=606, llm_enabled=False)
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    world.agents = []
    world.villages = []
    world.structures = set()
    world.storage_buildings = set()
    world.buildings = {}
    world.building_occupancy = {}
    village = {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 10, "y": 10},
        "houses": 3,
        "population": 8,
        "storage": {"food": 0, "wood": 0, "stone": 0},
        "storage_pos": {"x": 10, "y": 10},
        "tier": 1,
    }
    world.villages = [village]
    return world, village


def _add_storage(world: World, village: dict, *, x: int, y: int, wood: int, stone: int) -> str:
    storage = world.place_building("storage", x, y, village_id=1, village_uid=village["village_uid"])
    assert storage is not None
    bid = str(storage["building_id"])
    world.buildings[bid]["storage"]["wood"] = int(wood)
    world.buildings[bid]["storage"]["stone"] = int(stone)
    village["storage"]["wood"] = int(wood)
    village["storage"]["stone"] = int(stone)
    return bid


def _add_house_site(world: World, village: dict, *, x: int, y: int) -> str:
    site = building_system.place_building(
        world,
        "house",
        (x, y),
        village_id=1,
        village_uid=village["village_uid"],
        operational_state="under_construction",
        construction_request={
            "wood_needed": 5,
            "wood_reserved": 0,
            "stone_needed": 3,
            "stone_reserved": 0,
            "food_needed": 0,
            "food_reserved": 0,
        },
        construction_buffer={"wood": 0, "stone": 0, "food": 0},
        construction_progress=0,
        construction_required_work=3,
    )
    assert site is not None
    return str(site["building_id"])


def _builder(*, x: int, y: int) -> Agent:
    builder = Agent(x=x, y=y, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    return builder


def test_gate_diagnostics_storage_found_but_missing_resource() -> None:
    world, village = _world()
    _add_storage(world, village, x=10, y=10, wood=0, stone=0)
    _add_house_site(world, village, x=9, y=10)
    builder = _builder(x=9, y=10)
    world.agents = [builder]

    assert building_system.try_build_house(world, builder) is False
    gate = world.compute_builder_self_supply_gate_snapshot()["global"]
    reasons = gate["failure_reasons"]
    assert int(gate["candidate_storage_found"]) >= 1
    assert int(reasons.get("candidate_storage_missing_resource", 0)) >= 1


def test_gate_diagnostics_out_of_site_radius_reason() -> None:
    world, village = _world()
    _add_storage(world, village, x=18, y=18, wood=8, stone=8)
    _add_house_site(world, village, x=9, y=10)
    builder = _builder(x=9, y=10)
    world.agents = [builder]

    assert building_system.try_build_house(world, builder) is False
    gate = world.compute_builder_self_supply_gate_snapshot()["global"]
    reasons = gate["failure_reasons"]
    assert int(gate["candidate_storage_has_resource"]) >= 1
    assert int(reasons.get("source_out_of_site_radius", 0)) >= 1


def test_gate_diagnostics_source_in_radius_but_not_accessible() -> None:
    world, village = _world()
    _add_storage(world, village, x=9, y=13, wood=8, stone=8)
    _add_house_site(world, village, x=9, y=10)
    builder = _builder(x=10, y=10)
    world.agents = [builder]

    assert building_system.try_build_house(world, builder) is False
    gate = world.compute_builder_self_supply_gate_snapshot()["global"]
    reasons = gate["failure_reasons"]
    assert int(gate["source_within_site_radius"]) >= 1
    assert int(reasons.get("source_not_accessible_from_builder", 0)) >= 1


def test_gate_diagnostics_inventory_full_reason() -> None:
    world, village = _world()
    _add_storage(world, village, x=10, y=10, wood=8, stone=8)
    _add_house_site(world, village, x=9, y=10)
    builder = _builder(x=9, y=10)
    builder.inventory["food"] = int(builder.max_inventory)
    world.agents = [builder]

    assert building_system.try_build_house(world, builder) is False
    gate = world.compute_builder_self_supply_gate_snapshot()["global"]
    reasons = gate["failure_reasons"]
    assert int(reasons.get("inventory_full", 0)) >= 1


def test_gate_diagnostics_success_stage_and_reason() -> None:
    world, village = _world()
    _add_storage(world, village, x=10, y=10, wood=8, stone=8)
    _add_house_site(world, village, x=9, y=10)
    builder = _builder(x=9, y=10)
    world.agents = [builder]

    assert building_system.try_build_house(world, builder) is False
    gate = world.compute_builder_self_supply_gate_snapshot()["global"]
    reasons = gate["failure_reasons"]
    assert int(gate["self_supply_pickup_success"]) >= 1
    assert int(gate["success_count"]) >= 1
    assert int(reasons.get("self_supply_succeeded", 0)) >= 1


def test_observability_exposes_builder_self_supply_gate_diagnostics() -> None:
    world, village = _world()
    _add_storage(world, village, x=10, y=10, wood=8, stone=8)
    _add_house_site(world, village, x=9, y=10)
    builder = _builder(x=9, y=10)
    world.agents = [builder]
    building_system.try_build_house(world, builder)

    world.metrics_collector.collect(world)
    snapshot = world.metrics_collector.latest()
    cog = snapshot["cognition_society"]
    assert "builder_self_supply_gate_diagnostics_global" in cog
    assert "builder_self_supply_gate_diagnostics_by_village" in cog
    by_village = cog["builder_self_supply_gate_diagnostics_by_village"]
    assert "v-000001" in by_village
