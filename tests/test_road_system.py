from __future__ import annotations

import systems.road_system as road_system
from state_serializer import serialize_dynamic_world_state
from world import World


def _flat_grass_world() -> World:
    world = World()
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    world.agents = []
    world.villages = []
    world.structures = set()
    world.storage_buildings = set()
    world.buildings = {}
    world.building_occupancy = {}
    world.roads = set()
    world.transport_tiles = {}
    return world


def _village() -> dict:
    return {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 10, "y": 10},
        "houses": 4,
        "population": 8,
        "storage": {"food": 8, "wood": 6, "stone": 4},
        "storage_pos": {"x": 10, "y": 10},
        "farm_zone_center": {"x": 12, "y": 10},
        "tier": 1,
    }


def test_building_connectivity_true_when_road_is_adjacent() -> None:
    world = _flat_grass_world()
    building = world.place_building("house", 5, 5)
    assert building is not None
    world.roads.add((5, 4))

    road_system.update_building_road_connectivity(world)
    assert world.buildings[building["building_id"]]["connected_to_road"] is True


def test_building_connectivity_false_without_adjacent_roads() -> None:
    world = _flat_grass_world()
    building = world.place_building("house", 5, 5)
    assert building is not None

    road_system.update_building_road_connectivity(world)
    assert world.buildings[building["building_id"]]["connected_to_road"] is False


def test_connectivity_update_is_deterministic() -> None:
    world = _flat_grass_world()
    b1 = world.place_building("house", 3, 3)
    b2 = world.place_building("storage", 6, 6)
    assert b1 is not None and b2 is not None
    world.roads.update({(3, 2), (8, 6)})

    road_system.update_building_road_connectivity(world)
    first = {
        bid: bool(b.get("connected_to_road", False))
        for bid, b in sorted(world.buildings.items())
    }
    road_system.update_building_road_connectivity(world)
    second = {
        bid: bool(b.get("connected_to_road", False))
        for bid, b in sorted(world.buildings.items())
    }
    assert first == second


def test_road_growth_connects_important_village_buildings() -> None:
    world = _flat_grass_world()
    village = _village()
    world.villages = [village]
    world.farm_plots[(11, 10)] = {"x": 11, "y": 10, "village_id": 1}

    storage = world.place_building("storage", 10, 10, village_id=1, village_uid="v-000001")
    house = world.place_building("house", 14, 10, village_id=1, village_uid="v-000001")
    assert storage is not None and house is not None
    assert len(world.roads) == 0

    road_system.update_road_infrastructure(world)

    assert len(world.roads) > 0
    assert world.buildings[storage["building_id"]]["connected_to_road"] is True
    assert world.buildings[house["building_id"]]["connected_to_road"] is True


def test_road_growth_is_deterministic_for_same_setup() -> None:
    first_world = _flat_grass_world()
    second_world = _flat_grass_world()

    for world in (first_world, second_world):
        village = _village()
        world.villages = [village]
        world.farm_plots[(11, 10)] = {"x": 11, "y": 10, "village_id": 1}
        world.place_building("storage", 10, 10, village_id=1, village_uid="v-000001")
        world.place_building("house", 14, 10, village_id=1, village_uid="v-000001")
        road_system.update_road_infrastructure(world)

    assert sorted(first_world.roads) == sorted(second_world.roads)


def test_roads_and_connected_flags_are_serialized() -> None:
    world = _flat_grass_world()
    village = _village()
    world.villages = [village]
    world.farm_plots[(11, 10)] = {"x": 11, "y": 10, "village_id": 1}
    world.place_building("storage", 10, 10, village_id=1, village_uid="v-000001")
    world.place_building("house", 14, 10, village_id=1, village_uid="v-000001")

    road_system.update_road_infrastructure(world)
    payload = serialize_dynamic_world_state(world)

    assert len(payload["roads"]) > 0
    assert all("connected_to_road" in b for b in payload["buildings"])
    assert any(bool(b["connected_to_road"]) for b in payload["buildings"])


def test_road_movement_cost_integration() -> None:
    world = _flat_grass_world()
    world.set_transport_type(2, 2, "road")
    assert world.movement_cost(2, 2) == 0.5
    assert world.movement_cost(2, 3) == 1.0


def test_transport_movement_hierarchy_modifiers_apply() -> None:
    world = _flat_grass_world()
    world.set_transport_type(5, 5, "path")
    world.set_transport_type(6, 5, "road")
    world.set_transport_type(7, 5, "logistics_corridor")
    assert world.movement_cost(5, 5) == 0.8
    assert world.movement_cost(6, 5) == 0.5
    assert world.movement_cost(7, 5) == 0.35


def test_bridge_and_tunnel_allow_crossing_blocked_terrain() -> None:
    world = _flat_grass_world()
    world.tiles[4][4] = "W"
    world.tiles[4][5] = "X"
    assert world.is_walkable(4, 4) is False
    assert world.is_walkable(5, 4) is False

    world.set_transport_type(4, 4, "bridge")
    world.set_transport_type(5, 4, "tunnel")
    assert world.is_walkable(4, 4) is True
    assert world.is_walkable(5, 4) is True


def test_path_emergence_upgrades_deterministically_to_corridor() -> None:
    world = _flat_grass_world()
    x, y = 9, 9
    for _ in range(road_system.PATH_BUILD_THRESHOLD):
        road_system.record_agent_step(world, x, y)
    assert world.get_transport_type(x, y) == "path"

    for _ in range(road_system.ROAD_BUILD_THRESHOLD - road_system.PATH_BUILD_THRESHOLD):
        road_system.record_agent_step(world, x, y)
    assert world.get_transport_type(x, y) == "road"

    for _ in range(road_system.CORRIDOR_BUILD_THRESHOLD - road_system.ROAD_BUILD_THRESHOLD):
        road_system.record_agent_step(world, x, y)
    assert world.get_transport_type(x, y) == "logistics_corridor"


def test_road_metadata_aligns_with_transport_infrastructure_runtime() -> None:
    world = _flat_grass_world()
    world.villages = [_village()]
    world.place_building("storage", 10, 10, village_id=1, village_uid="v-000001")
    road_system.update_road_infrastructure(world)

    road_meta = road_system.get_transport_infrastructure_metadata("road")
    assert road_meta is not None
    assert road_meta["system"] == "transport"
    assert road_meta["type"] == "road"
    assert world.infrastructure_state["transport"]["road_infrastructure_type"] == "road"


def test_transport_catalog_contains_hierarchy_types() -> None:
    path_meta = road_system.get_transport_infrastructure_metadata("path")
    road_meta = road_system.get_transport_infrastructure_metadata("road")
    corridor_meta = road_system.get_transport_infrastructure_metadata("logistics_corridor")
    bridge_meta = road_system.get_transport_infrastructure_metadata("bridge")
    tunnel_meta = road_system.get_transport_infrastructure_metadata("tunnel")

    assert path_meta is not None and path_meta["movement_modifier"] == 0.8
    assert road_meta is not None and road_meta["movement_modifier"] == 0.5
    assert corridor_meta is not None and corridor_meta["movement_modifier"] == 0.35
    assert bridge_meta is not None and bool(bridge_meta["crosses_blocking_terrain"]) is True
    assert tunnel_meta is not None and bool(tunnel_meta["crosses_blocking_terrain"]) is True
