from __future__ import annotations

from agent import Agent
import systems.building_system as building_system
import systems.role_system as role_system
from world import World


def _world() -> tuple[World, dict]:
    world = World(width=24, height=24, num_agents=0, seed=404, llm_enabled=False)
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    village = {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 10, "y": 10},
        "houses": 4,
        "population": 6,
        "storage": {"food": 0, "wood": 20, "stone": 20},
        "storage_pos": {"x": 10, "y": 10},
        "tier": 2,
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
        "storage": {"food": 0, "wood": 20, "stone": 20},
        "storage_capacity": 250,
    }
    return world, village


def _add_site(world: World) -> None:
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
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
        "construction_required_work": 3,
    }


def test_delivery_target_created_and_reserved_counters_increment() -> None:
    world, _ = _world()
    _add_site(world)
    hauler = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    hauler.village_id = 1
    hauler.role = "hauler"
    world.agents = [hauler]

    assert building_system.run_hauler_construction_delivery(world, hauler) is True
    diag = world.compute_delivery_diagnostics_snapshot()
    g = diag["global"]
    assert int(g["delivery_target_created_count"]) >= 1
    assert int(g["delivery_target_reserved_count"]) >= 1
    assert int(g["delivery_target_visible_count"]) >= 1


def test_pickup_attempt_and_success_counters_increment() -> None:
    world, _ = _world()
    _add_site(world)
    hauler = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    hauler.village_id = 1
    hauler.role = "hauler"
    world.agents = [hauler]

    assert building_system.run_hauler_construction_delivery(world, hauler) is True
    diag = world.compute_delivery_diagnostics_snapshot()
    g = diag["global"]
    assert int(g["resource_pickup_attempt_count"]) >= 1
    assert int(g["resource_pickup_success_count"]) >= 1
    assert int(g["hauler_departed_with_resource_count"]) >= 1


def test_delivery_abandonment_reason_recorded_deterministically() -> None:
    world, _ = _world()
    hauler = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    hauler.village_id = 1
    hauler.role = "hauler"
    world.agents = [hauler]

    assert building_system.run_hauler_construction_delivery(world, hauler) is False
    diag = world.compute_delivery_diagnostics_snapshot()
    g = diag["global"]
    assert int(g["delivery_abandoned_count"]) >= 1
    assert int(g["delivery_failure_reasons"].get("no_delivery_target", 0)) >= 1


def test_observability_exports_delivery_diagnostics_fields() -> None:
    world, _ = _world()
    _add_site(world)
    hauler = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    hauler.village_id = 1
    hauler.role = "hauler"
    world.agents = [hauler]
    building_system.run_hauler_construction_delivery(world, hauler)

    world.metrics_collector.collect(world)
    snapshot = world.metrics_collector.latest()
    cs = snapshot["cognition_society"]
    assert "delivery_diagnostics_global" in cs
    assert "delivery_diagnostics_by_role" in cs
    assert "delivery_diagnostics_by_village" in cs
    assert int(cs["delivery_diagnostics_global"].get("delivery_target_created_count", 0)) >= 1


def test_delivery_target_not_created_when_no_plausible_source_exists() -> None:
    world, _ = _world()
    _add_site(world)
    world.buildings["b-storage"]["storage"]["wood"] = 0
    world.buildings["b-storage"]["storage"]["stone"] = 0
    world.villages[0]["storage"]["wood"] = 0
    world.villages[0]["storage"]["stone"] = 0
    hauler = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    hauler.village_id = 1
    hauler.role = "hauler"
    world.agents = [hauler]

    assert building_system.run_hauler_construction_delivery(world, hauler) is False
    diag = world.compute_delivery_diagnostics_snapshot()["global"]
    assert int(diag["delivery_target_created_count"]) == 0
    assert int(diag["delivery_failure_reasons"].get("no_resource_available", 0)) >= 1


def test_hauler_carrying_material_keeps_valid_delivery_path_without_source_lookup() -> None:
    world, _ = _world()
    _add_site(world)
    hauler = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    hauler.village_id = 1
    hauler.role = "hauler"
    hauler.inventory["wood"] = 2
    hauler.delivery_target_building_id = "b-site"
    hauler.delivery_resource_type = "wood"
    hauler.delivery_reserved_amount = 2
    world.buildings["b-site"]["construction_request"]["wood_reserved"] = 2
    world.agents = [hauler]

    assert building_system.run_hauler_construction_delivery(world, hauler) is True
    diag = world.compute_delivery_diagnostics_snapshot()["global"]
    assert int(diag["site_arrival_count"]) >= 1
    assert int(diag["delivery_success_count"]) >= 1


def test_active_delivery_commit_blocks_premature_hauler_reassignment_in_safe_condition() -> None:
    world, _ = _world()
    hauler = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    hauler.role = "hauler"
    hauler.village_id = 1
    hauler.delivery_target_building_id = "b-site"
    hauler.delivery_resource_type = "wood"
    hauler.delivery_reserved_amount = 1
    hauler.delivery_commit_until_tick = 20
    hauler.hunger = 80
    world.tick = 10

    assert role_system._can_change_role(world, hauler, "farmer") is False
    world.tick = 21
    assert role_system._can_change_role(world, hauler, "farmer") is True


def test_no_fake_delivery_when_resource_is_truly_unavailable() -> None:
    world, _ = _world()
    _add_site(world)
    world.buildings["b-storage"]["storage"]["wood"] = 0
    world.buildings["b-storage"]["storage"]["stone"] = 0
    world.buildings["b-storage"]["storage"]["food"] = 0
    world.villages[0]["storage"]["wood"] = 0
    world.villages[0]["storage"]["stone"] = 0
    world.villages[0]["storage"]["food"] = 0
    world.buildings["b-site"]["construction_request"]["stone_needed"] = 0
    world.buildings["b-site"]["construction_request"]["stone_reserved"] = 0
    world.buildings["b-site"]["construction_buffer"]["stone"] = 0
    hauler = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    hauler.village_id = 1
    hauler.role = "hauler"
    world.agents = [hauler]

    assert building_system.run_hauler_construction_delivery(world, hauler) is False
    diag = world.compute_delivery_diagnostics_snapshot()["global"]
    assert int(diag["delivery_success_count"]) == 0
