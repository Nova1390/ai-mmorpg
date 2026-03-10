from __future__ import annotations

from agent import Agent
from config import HOUSE_STONE_COST, HOUSE_WOOD_COST
import systems.building_system as building_system
import systems.role_system as role_system
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
    return world


def _village(
    *,
    village_id: int = 1,
    tier: int = 1,
    population: int = 6,
    houses: int = 3,
    center_x: int = 10,
    center_y: int = 10,
    uid: str = "v-000001",
) -> dict:
    return {
        "id": village_id,
        "village_uid": uid,
        "center": {"x": center_x, "y": center_y},
        "houses": houses,
        "population": population,
        "storage": {"food": 0, "wood": 0, "stone": 0},
        "storage_pos": {"x": center_x, "y": center_y},
        "tier": tier,
    }


def _specialization_readiness_world(
    *,
    tier: int = 2,
    population: int = 12,
    houses: int = 5,
    add_farm: bool = True,
    add_storage: bool = True,
    add_road: bool = True,
) -> tuple[World, dict]:
    world = _flat_grass_world()
    village = _village(tier=tier, population=population, houses=houses)
    village["storage"] = {"food": 12, "wood": 1, "stone": 1}
    world.villages = [village]
    if add_farm:
        world.farm_plots[(9, 10)] = {"x": 9, "y": 10, "village_id": 1}
    if add_road:
        world.roads.add((10, 9))
    if add_storage:
        world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    return world, village


def test_place_house_and_storage_with_stable_building_ids_and_footprints() -> None:
    world = _flat_grass_world()

    house = world.place_building("house", 5, 5, village_id=1, village_uid="v-000001")
    storage = world.place_building("storage", 7, 7, village_id=1, village_uid="v-000001")

    assert house is not None
    assert storage is not None
    assert house["building_id"] != storage["building_id"]
    assert house["type"] == "house"
    assert house["category"] == "residential"
    assert house["tier"] == 1
    assert storage["type"] == "storage"
    assert storage["category"] == "food_storage"
    assert storage["tier"] == 1
    assert len(house["footprint"]) == 1
    assert len(storage["footprint"]) == 4
    assert world.is_tile_blocked_by_building(7, 7)
    assert world.is_tile_blocked_by_building(8, 8)


def test_multi_tile_overlap_is_prevented() -> None:
    world = _flat_grass_world()
    assert world.place_building("storage", 10, 10) is not None
    assert world.place_building("house", 10, 10) is None
    assert world.place_building("house", 11, 11) is None


def test_multi_tile_bounds_and_terrain_validation() -> None:
    world = _flat_grass_world()
    world.tiles[0][0] = "W"

    assert world.place_building("house", 0, 0) is None
    assert world.place_building("storage", world.width - 1, world.height - 1) is None


def test_dynamic_state_serializes_typed_buildings_and_legacy_structure_fields() -> None:
    world = _flat_grass_world()
    house = world.place_building("house", 3, 4, village_id=2, village_uid="v-000002")
    storage = world.place_building("storage", 6, 6, village_id=2, village_uid="v-000002")
    assert house is not None
    assert storage is not None

    payload = serialize_dynamic_world_state(world)

    assert "buildings" in payload
    assert [b["type"] for b in payload["buildings"]] == ["house", "storage"]
    assert [b["category"] for b in payload["buildings"]] == ["residential", "food_storage"]
    assert all("operational_state" in b for b in payload["buildings"])
    assert all("linked_resource_type" in b for b in payload["buildings"])
    assert all("linked_resource_tiles_count" in b for b in payload["buildings"])
    assert payload["structures"] == [{"x": 3, "y": 4}]
    assert payload["storage_buildings"] == [{"x": 6, "y": 6}]
    assert payload["buildings"][1]["footprint"] == [
        {"x": 6, "y": 6},
        {"x": 7, "y": 6},
        {"x": 6, "y": 7},
        {"x": 7, "y": 7},
    ]


def test_building_catalog_integrity_and_taxonomy() -> None:
    required_fields = {
        "type",
        "category",
        "tier",
        "footprint_size",
        "min_tier",
        "hard_requirements",
        "unlock_signals",
        "requires_road",
        "worker_capacity",
        "description",
        "requires_infrastructure",
        "benefits_from_infrastructure",
    }
    assert {"house", "storage", "farm_plot", "mine", "lumberyard"}.issubset(
        set(building_system.BUILDING_CATALOG.keys())
    )

    for building_type, metadata in building_system.BUILDING_CATALOG.items():
        assert required_fields.issubset(set(metadata.keys()))
        assert metadata["type"] == building_type
        assert metadata["category"] in building_system.BUILDING_CATEGORIES
        assert int(metadata["tier"]) >= 0
        w, h = metadata["footprint_size"]
        assert int(w) > 0 and int(h) > 0


def test_infrastructure_catalog_integrity() -> None:
    required_fields = {
        "type",
        "system",
        "tier",
        "network_type",
        "connects_buildings",
        "supports_logistics",
        "description",
    }
    expected_types = {
        "path",
        "road",
        "logistics_corridor",
        "bridge",
        "tunnel",
        "storage_link",
        "haul_route",
        "well_network",
        "power_line",
        "messenger_route",
        "drainage",
    }
    assert expected_types.issubset(set(building_system.INFRASTRUCTURE_CATALOG.keys()))
    for infra_type, metadata in building_system.INFRASTRUCTURE_CATALOG.items():
        assert required_fields.issubset(set(metadata.keys()))
        assert metadata["type"] == infra_type
        assert metadata["system"] in building_system.INFRASTRUCTURE_SYSTEMS


def test_infrastructure_lookup_is_deterministic() -> None:
    first = building_system.get_infrastructure_metadata("road")
    second = building_system.get_infrastructure_metadata("road")
    assert first == second
    assert first is not None
    assert first["system"] == "transport"


def test_building_metadata_declares_infrastructure_dependencies() -> None:
    mine = building_system.get_building_metadata("mine")
    storage = building_system.get_building_metadata("storage")
    assert mine is not None and storage is not None
    assert "road" in mine["requires_infrastructure"]
    assert "road" in mine["benefits_from_infrastructure"]
    assert "storage_link" in storage["benefits_from_infrastructure"]


def test_footprint_is_derived_from_catalog_metadata() -> None:
    house_meta = building_system.get_building_metadata("house")
    storage_meta = building_system.get_building_metadata("storage")
    assert house_meta is not None
    assert storage_meta is not None
    assert house_meta["footprint_size"] == (1, 1)
    assert storage_meta["footprint_size"] == (2, 2)

    house_tiles = building_system.footprint_tiles("house", (0, 0))
    storage_tiles = building_system.footprint_tiles("storage", (5, 5))
    assert len(house_tiles) == 1
    assert storage_tiles == [(5, 5), (6, 5), (5, 6), (6, 6)]


def test_tier1_village_available_and_unavailable_buildings() -> None:
    world = _flat_grass_world()
    village = _village(tier=1, population=8, houses=4)
    world.villages = [village]
    world.farm_plots[(9, 10)] = {"x": 9, "y": 10, "village_id": 1}
    world.roads.add((10, 9))

    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    available = building_system.get_available_building_types_for_village(world, village)

    assert {"house", "storage", "farm_plot"}.issubset(set(available))
    assert "mine" not in available
    assert "lumberyard" not in available


def test_tier2_village_unlocks_production_when_requirements_met() -> None:
    world = _flat_grass_world()
    village = _village(tier=2, population=12, houses=5)
    village["storage"] = {"food": 8, "wood": 1, "stone": 1}
    world.villages = [village]
    world.farm_plots[(9, 10)] = {"x": 9, "y": 10, "village_id": 1}
    world.roads.update({(10, 9), (9, 9)})
    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])

    available = building_system.get_available_building_types_for_village(world, village)
    assert "mine" in available
    assert "lumberyard" in available


def test_mature_tier1_village_can_unlock_specialization_readiness() -> None:
    world = _flat_grass_world()
    village = _village(tier=1, population=9, houses=4)
    village["storage"] = {"food": 8, "wood": 1, "stone": 1}
    world.villages = [village]
    world.farm_plots[(9, 10)] = {"x": 9, "y": 10, "village_id": 1}
    world.roads.add((10, 9))
    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])

    mine_readiness = building_system.evaluate_building_readiness_for_village(world, village, "mine")
    lumber_readiness = building_system.evaluate_building_readiness_for_village(world, village, "lumberyard")

    assert mine_readiness["tier_ok"] is True
    assert mine_readiness["hard_requirements_ok"] is True
    assert mine_readiness["status"] in {"available", "recommended"}
    assert lumber_readiness["tier_ok"] is True
    assert lumber_readiness["hard_requirements_ok"] is True
    assert lumber_readiness["status"] in {"available", "recommended"}


def test_immature_tier1_village_still_blocks_specialization_readiness() -> None:
    world = _flat_grass_world()
    village = _village(tier=1, population=8, houses=2)
    village["storage"] = {"food": 8, "wood": 1, "stone": 1}
    world.villages = [village]
    world.farm_plots[(9, 10)] = {"x": 9, "y": 10, "village_id": 1}
    world.roads.add((10, 9))
    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])

    mine_readiness = building_system.evaluate_building_readiness_for_village(world, village, "mine")
    lumber_readiness = building_system.evaluate_building_readiness_for_village(world, village, "lumberyard")

    assert mine_readiness["status"] == "unavailable"
    assert mine_readiness["tier_ok"] is False
    assert lumber_readiness["status"] == "unavailable"
    assert lumber_readiness["tier_ok"] is False
    mine_breakdown = world.specialization_diagnostics["mine"]["readiness_breakdown"]
    assert int(mine_breakdown.get("tier_inputs_population_low", 0)) >= 1
    assert int(mine_breakdown.get("tier_inputs_houses_low", 0)) >= 1


def test_specialization_not_unconditionally_available_without_local_requirements() -> None:
    world = _flat_grass_world()
    village = _village(tier=1, population=9, houses=4)
    village["storage"] = {"food": 8, "wood": 1, "stone": 1}
    world.villages = [village]
    # Missing farms and storage building should still fail hard requirements.
    world.roads.add((10, 9))

    mine_readiness = building_system.evaluate_building_readiness_for_village(world, village, "mine")
    lumber_readiness = building_system.evaluate_building_readiness_for_village(world, village, "lumberyard")

    assert mine_readiness["status"] == "unavailable"
    assert mine_readiness["tier_ok"] is False
    assert mine_readiness["hard_requirements_ok"] is False
    assert lumber_readiness["status"] == "unavailable"
    assert lumber_readiness["tier_ok"] is False
    assert lumber_readiness["hard_requirements_ok"] is False


def test_hard_requirements_are_enforced() -> None:
    world = _flat_grass_world()
    village = _village(tier=2, population=12, houses=5)
    world.villages = [village]
    # no roads, no farms, no storage => tier is OK but hard requirements fail
    readiness = building_system.evaluate_building_readiness_for_village(world, village, "mine")
    assert readiness["status"] == "unavailable"
    assert readiness["tier_ok"] is True
    assert readiness["hard_requirements_ok"] is False


def test_requirement_population_min_breakdown_increments() -> None:
    world, village = _specialization_readiness_world(population=8, houses=5)
    readiness = building_system.evaluate_building_readiness_for_village(world, village, "mine")
    assert readiness["status"] == "unavailable"
    breakdown = world.specialization_diagnostics["mine"]["requirement_breakdown"]
    assert int(breakdown.get("requirement_population_min_failed", 0)) >= 1


def test_requirement_houses_min_breakdown_increments() -> None:
    world, village = _specialization_readiness_world(population=12, houses=2)
    readiness = building_system.evaluate_building_readiness_for_village(world, village, "mine")
    assert readiness["status"] == "unavailable"
    breakdown = world.specialization_diagnostics["mine"]["requirement_breakdown"]
    assert int(breakdown.get("requirement_houses_min_failed", 0)) >= 1


def test_requirement_farms_min_breakdown_increments() -> None:
    world, village = _specialization_readiness_world(add_farm=False)
    readiness = building_system.evaluate_building_readiness_for_village(world, village, "mine")
    assert readiness["status"] == "unavailable"
    breakdown = world.specialization_diagnostics["mine"]["requirement_breakdown"]
    assert int(breakdown.get("requirement_farms_min_failed", 0)) >= 1


def test_requirement_storage_required_breakdown_increments() -> None:
    world, village = _specialization_readiness_world(add_storage=False)
    readiness = building_system.evaluate_building_readiness_for_village(world, village, "mine")
    assert readiness["status"] == "unavailable"
    breakdown = world.specialization_diagnostics["mine"]["requirement_breakdown"]
    assert int(breakdown.get("requirement_storage_required_failed", 0)) >= 1


def test_requirement_roads_required_breakdown_increments() -> None:
    world, village = _specialization_readiness_world(add_road=False)
    readiness = building_system.evaluate_building_readiness_for_village(world, village, "mine")
    assert readiness["status"] == "unavailable"
    breakdown = world.specialization_diagnostics["mine"]["requirement_breakdown"]
    assert int(breakdown.get("requirement_roads_required_failed", 0)) >= 1


def test_specialization_readiness_counter_increments_when_eligible() -> None:
    world = _flat_grass_world()
    village = _village(tier=2, population=12, houses=5)
    village["storage"] = {"food": 12, "wood": 1, "stone": 1}
    world.villages = [village]
    world.farm_plots[(9, 10)] = {"x": 9, "y": 10, "village_id": 1}
    world.roads.add((10, 9))
    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])

    building_system.evaluate_building_readiness_for_village(world, village, "mine")
    building_system.evaluate_building_readiness_for_village(world, village, "lumberyard")

    diag = world.specialization_diagnostics
    assert int(diag["mine"].get("readiness_possible_count", 0)) >= 1
    assert int(diag["lumberyard"].get("readiness_possible_count", 0)) >= 1


def test_readiness_status_moves_from_available_to_recommended() -> None:
    world = _flat_grass_world()
    village = _village(tier=1, population=8, houses=4)
    world.villages = [village]

    ready = building_system.evaluate_building_readiness_for_village(world, village, "house")
    assert ready["status"] == "recommended"
    assert "population_pressure_high" in ready["matching_signals"]

    village["population"] = 3
    ready2 = building_system.evaluate_building_readiness_for_village(world, village, "house")
    assert ready2["status"] == "available"
    assert ready2["matching_signals"] == []


def test_unlock_signals_are_deterministic() -> None:
    world = _flat_grass_world()
    village = _village(tier=2, population=10, houses=4)
    village["storage"] = {"food": 12, "wood": 1, "stone": 1}
    world.villages = [village]
    world.farm_plots[(9, 10)] = {"x": 9, "y": 10, "village_id": 1}
    world.roads.add((10, 9))
    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])

    first = building_system.evaluate_village_unlock_signals(world, village)
    second = building_system.evaluate_village_unlock_signals(world, village)
    assert first == second
    assert first["farms_present"] is True
    assert first["storage_exists"] is True
    assert first["roads_present"] is True


def test_malformed_or_unsupported_requirements_fail_safely() -> None:
    world = _flat_grass_world()
    village = _village(tier=3, population=20, houses=10)
    world.villages = [village]

    original_mine = building_system.BUILDING_CATALOG["mine"]
    try:
        malformed = dict(original_mine)
        malformed["hard_requirements"] = {"unknown_gate": 1}
        building_system.BUILDING_CATALOG["mine"] = malformed
        assert building_system.building_hard_requirements_met(world, village, "mine") is False

        malformed2 = dict(original_mine)
        malformed2["hard_requirements"] = {"population_min": "oops"}
        building_system.BUILDING_CATALOG["mine"] = malformed2
        assert building_system.building_hard_requirements_met(world, village, "mine") is False
    finally:
        building_system.BUILDING_CATALOG["mine"] = original_mine


def test_available_and_recommended_ordering_is_deterministic() -> None:
    world = _flat_grass_world()
    village = _village(tier=2, population=12, houses=5)
    village["storage"] = {"food": 12, "wood": 1, "stone": 1}
    world.villages = [village]
    world.farm_plots[(9, 10)] = {"x": 9, "y": 10, "village_id": 1}
    world.roads.add((10, 9))
    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])

    first_available = building_system.get_available_building_types_for_village(world, village)
    second_available = building_system.get_available_building_types_for_village(world, village)
    first_recommended = building_system.get_recommended_building_types_for_village(world, village)
    second_recommended = building_system.get_recommended_building_types_for_village(world, village)

    assert first_available == second_available
    assert first_recommended == second_recommended


def test_food_storage_prefers_center_proximal_positions() -> None:
    world = _flat_grass_world()
    village = _village(center_x=20, center_y=20)
    world.villages = [village]

    near_center = (20, 21)
    far_from_center = (30, 30)
    near_score = building_system.score_building_position(world, village, "storage", near_center)
    far_score = building_system.score_building_position(world, village, "storage", far_from_center)

    assert near_score > far_score


def test_residential_prefers_settlement_adjacent_locations() -> None:
    world = _flat_grass_world()
    village = _village(center_x=15, center_y=15)
    world.villages = [village]

    world.place_building("house", 16, 15, village_id=1, village_uid=village["village_uid"])
    near_settlement = (17, 15)
    remote = (30, 30)

    near_score = building_system.score_building_position(world, village, "house", near_settlement)
    remote_score = building_system.score_building_position(world, village, "house", remote)
    assert near_score > remote_score


def test_production_prefers_peripheral_road_connected_positions() -> None:
    world = _flat_grass_world()
    village = _village(tier=2, population=16, houses=6, center_x=20, center_y=20)
    village["storage"] = {"food": 12, "wood": 3, "stone": 3}
    world.villages = [village]
    world.place_building("storage", 20, 20, village_id=1, village_uid=village["village_uid"])
    world.roads.update({(25, 20), (25, 21)})
    world.farm_plots[(21, 20)] = {"x": 21, "y": 20, "village_id": 1}

    peripheral_road_near = (25, 22)
    dense_core = (20, 21)
    peripheral_score = building_system.score_building_position(world, village, "mine", peripheral_road_near)
    core_score = building_system.score_building_position(world, village, "mine", dense_core)
    assert peripheral_score > core_score


def test_farm_plot_scoring_prefers_farm_zone_over_dense_core() -> None:
    world = _flat_grass_world()
    village = _village(center_x=20, center_y=20)
    village["farm_zone_center"] = {"x": 26, "y": 20}
    world.villages = [village]
    world.place_building("house", 20, 20, village_id=1, village_uid=village["village_uid"])
    world.place_building("house", 21, 20, village_id=1, village_uid=village["village_uid"])

    near_farm_zone = (26, 21)
    dense_core = (20, 21)
    near_score = building_system.score_building_position(world, village, "farm_plot", near_farm_zone)
    core_score = building_system.score_building_position(world, village, "farm_plot", dense_core)
    assert near_score > core_score


def test_preferred_position_selection_is_deterministic() -> None:
    world = _flat_grass_world()
    village = _village(center_x=10, center_y=10)
    world.villages = [village]
    candidates = [(12, 10), (9, 9), (10, 9), (15, 15)]

    first = building_system.find_preferred_build_position(world, village, "house", candidates)
    second = building_system.find_preferred_build_position(world, village, "house", candidates)
    assert first == second


def test_scoring_respects_placement_safety_checks() -> None:
    world = _flat_grass_world()
    village = _village(center_x=5, center_y=5)
    world.villages = [village]
    world.tiles[5][5] = "W"

    blocked_score = building_system.score_building_position(world, village, "house", (5, 5))
    assert blocked_score <= -10**9


def test_generic_try_build_type_places_house() -> None:
    world = _flat_grass_world()
    village = _village(population=8, houses=4)
    world.villages = [village]
    agent = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    agent.village_id = 1

    result = building_system.try_build_type(world, agent, "house", village_id=1, village_uid=village["village_uid"])
    assert result["success"] is True
    assert result["reason"] == "placed"
    assert isinstance(result["building_id"], str)
    assert isinstance(result["position"], dict)


def test_generic_try_build_type_places_storage() -> None:
    world = _flat_grass_world()
    village = _village(population=8, houses=4)
    world.villages = [village]
    world.farm_plots[(9, 10)] = {"x": 9, "y": 10, "village_id": 1}
    agent = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    agent.village_id = 1

    result = building_system.try_build_type(world, agent, "storage", village_id=1, village_uid=village["village_uid"])
    assert result["success"] is True
    placed = world.buildings[result["building_id"]]
    assert placed["type"] == "storage"


def test_generic_try_build_type_blocked_by_readiness() -> None:
    world = _flat_grass_world()
    village = _village(tier=1, population=12, houses=5)
    world.villages = [village]
    agent = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    agent.village_id = 1

    result = building_system.try_build_type(world, agent, "mine", village_id=1, village_uid=village["village_uid"])
    assert result["success"] is False
    assert result["reason"] == "readiness_unavailable"


def test_generic_try_build_type_respects_spatial_scoring_for_storage() -> None:
    world = _flat_grass_world()
    village = _village(center_x=20, center_y=20, population=8, houses=4)
    world.villages = [village]
    world.farm_plots[(20, 21)] = {"x": 20, "y": 21, "village_id": 1}
    agent = Agent(x=20, y=20, brain=None, is_player=False, player_id=None)
    agent.village_id = 1

    result = building_system.try_build_type(
        world,
        agent,
        "storage",
        village_id=1,
        village_uid=village["village_uid"],
        search_radius=4,
    )
    assert result["success"] is True
    pos = (result["position"]["x"], result["position"]["y"])
    assert abs(pos[0] - 20) + abs(pos[1] - 20) <= 3


def test_generic_try_build_type_respects_safety_validation() -> None:
    world = _flat_grass_world()
    world.tiles = [["W" for _ in range(world.width)] for _ in range(world.height)]
    village = _village(population=8, houses=4)
    world.villages = [village]
    agent = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    agent.village_id = 1

    result = building_system.try_build_type(world, agent, "house", village_id=1, village_uid=village["village_uid"])
    assert result["success"] is False
    assert result["reason"] == "no_valid_position"


def test_generic_try_build_type_can_place_placeholder_when_readiness_permits() -> None:
    world = _flat_grass_world()
    village = _village(tier=2, population=14, houses=6)
    village["storage"] = {"food": 12, "wood": 1, "stone": 1}
    world.villages = [village]
    world.farm_plots[(9, 10)] = {"x": 9, "y": 10, "village_id": 1}
    world.roads.update({(10, 9), (11, 9)})
    world.stone.update({(12, 10), (13, 10), (12, 11), (13, 11)})
    world.wood.update({(9, 10), (9, 11), (8, 10), (8, 11)})
    world.tiles[10][12] = "M"
    world.tiles[10][9] = "F"
    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    agent = Agent(x=12, y=10, brain=None, is_player=False, player_id=None)
    agent.village_id = 1

    mine = building_system.try_build_type(world, agent, "mine", village_id=1, village_uid=village["village_uid"])
    lumberyard = building_system.try_build_type(
        world, agent, "lumberyard", village_id=1, village_uid=village["village_uid"]
    )
    assert mine["success"] is True
    assert lumberyard["success"] is True
    assert world.buildings[mine["building_id"]]["type"] == "mine"
    assert world.buildings[lumberyard["building_id"]]["type"] == "lumberyard"


def test_generic_try_build_type_is_deterministic_for_same_setup() -> None:
    world_a = _flat_grass_world()
    world_b = _flat_grass_world()
    village_a = _village(center_x=18, center_y=18, population=8, houses=4)
    village_b = _village(center_x=18, center_y=18, population=8, houses=4)
    world_a.villages = [village_a]
    world_b.villages = [village_b]
    world_a.farm_plots[(18, 19)] = {"x": 18, "y": 19, "village_id": 1}
    world_b.farm_plots[(18, 19)] = {"x": 18, "y": 19, "village_id": 1}
    agent_a = Agent(x=18, y=18, brain=None, is_player=False, player_id=None)
    agent_b = Agent(x=18, y=18, brain=None, is_player=False, player_id=None)
    agent_a.village_id = 1
    agent_b.village_id = 1

    result_a = building_system.try_build_type(
        world_a, agent_a, "storage", village_id=1, village_uid=village_a["village_uid"], search_radius=4
    )
    result_b = building_system.try_build_type(
        world_b, agent_b, "storage", village_id=1, village_uid=village_b["village_uid"], search_radius=4
    )
    assert result_a["success"] is True and result_b["success"] is True
    assert result_a["position"] == result_b["position"]


def test_mine_requires_valid_stone_context() -> None:
    world = _flat_grass_world()
    world.stone = set()
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    village = _village(tier=2, population=14, houses=6)
    village["storage"] = {"food": 12, "wood": 2, "stone": 2}
    world.villages = [village]
    world.farm_plots[(10, 11)] = {"x": 10, "y": 11, "village_id": 1}
    world.roads.add((10, 9))
    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    agent = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    agent.village_id = 1

    result = building_system.try_build_type(world, agent, "mine", village_id=1, village_uid=village["village_uid"])
    assert result["success"] is False
    assert result["reason"] == "invalid_resource_context"
    blockers = world.specialization_diagnostics["mine"]["blocker_reasons"]
    assert int(blockers.get("no_resource_context", 0)) >= 1
    req_breakdown = world.specialization_diagnostics["mine"]["requirement_breakdown"]
    assert int(req_breakdown.get("requirement_resource_context_failed", 0)) >= 1


def test_lumberyard_requires_valid_wood_context() -> None:
    world = _flat_grass_world()
    world.wood = set()
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    village = _village(tier=2, population=14, houses=6)
    village["storage"] = {"food": 12, "wood": 2, "stone": 2}
    world.villages = [village]
    world.farm_plots[(10, 11)] = {"x": 10, "y": 11, "village_id": 1}
    world.roads.add((10, 9))
    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    agent = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    agent.village_id = 1

    result = building_system.try_build_type(
        world, agent, "lumberyard", village_id=1, village_uid=village["village_uid"]
    )
    assert result["success"] is False
    assert result["reason"] == "invalid_resource_context"


def test_production_building_yields_efficiency_bonus() -> None:
    world_without = _flat_grass_world()
    world_with = _flat_grass_world()

    for world in (world_without, world_with):
        village = _village(tier=2, population=14, houses=6, center_x=10, center_y=10)
        village["storage"] = {"food": 12, "wood": 2, "stone": 0}
        world.villages = [village]
        world.farm_plots[(10, 11)] = {"x": 10, "y": 11, "village_id": 1}
        world.roads.update({(10, 9), (11, 9), (12, 9)})
        world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
        world.stone.update({(12, 10), (13, 10), (12, 11), (13, 11)})
        world.tiles[10][12] = "M"

    agent_without = Agent(x=12, y=10, brain=None, is_player=False, player_id=None)
    agent_with = Agent(x=12, y=10, brain=None, is_player=False, player_id=None)
    agent_without.village_id = 1
    agent_with.village_id = 1

    mine_result = building_system.try_build_type(
        world_with, agent_with, "mine", village_id=1, village_uid="v-000001"
    )
    assert mine_result["success"] is True
    mine = world_with.buildings[mine_result["building_id"]]
    mine["connected_to_road"] = True

    assert world_without.gather_resource(agent_without) is True
    assert world_with.gather_resource(agent_with) is True

    stone_without = agent_without.inventory["stone"]
    stone_with = agent_with.inventory["stone"]
    assert stone_without == 1
    assert stone_with > stone_without
    metrics = world_with.villages[0].get("production_metrics", {})
    assert metrics.get("total_stone_gathered", 0) >= stone_with
    assert metrics.get("stone_from_mines", 0) >= 1


def test_direct_gathering_still_works_without_production_buildings() -> None:
    world = _flat_grass_world()
    village = _village(tier=1, population=8, houses=4)
    world.villages = [village]
    world.wood.add((8, 8))
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.village_id = 1

    assert world.gather_resource(agent) is True
    assert agent.inventory["wood"] >= 1
    assert world.villages[0]["storage"]["wood"] == 0
    metrics = world.villages[0].get("production_metrics", {})
    assert metrics.get("total_wood_gathered", 0) >= 1
    assert metrics.get("wood_from_lumberyards", 0) == 0


def test_direct_wood_gathering_increments_total_and_direct_counters() -> None:
    world = _flat_grass_world()
    village = _village(tier=1, population=8, houses=4)
    world.villages = [village]
    world.wood.add((8, 8))
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.village_id = 1

    assert world.gather_resource(agent) is True

    vm = world.villages[0]["production_metrics"]
    assert int(vm.get("total_wood_gathered", 0)) == 1
    assert int(vm.get("direct_wood_gathered", 0)) == 1
    assert int(vm.get("wood_from_lumberyards", 0)) == 0
    wm = world.production_metrics
    assert int(wm.get("total_wood_gathered", 0)) == 1
    assert int(wm.get("direct_wood_gathered", 0)) == 1
    assert int(wm.get("wood_from_lumberyards", 0)) == 0


def test_direct_stone_gathering_increments_total_and_direct_counters() -> None:
    world = _flat_grass_world()
    village = _village(tier=1, population=8, houses=4)
    world.villages = [village]
    world.stone.add((8, 8))
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.village_id = 1

    assert world.gather_resource(agent) is True

    vm = world.villages[0]["production_metrics"]
    assert int(vm.get("total_stone_gathered", 0)) == 1
    assert int(vm.get("direct_stone_gathered", 0)) == 1
    assert int(vm.get("stone_from_mines", 0)) == 0
    wm = world.production_metrics
    assert int(wm.get("total_stone_gathered", 0)) == 1
    assert int(wm.get("direct_stone_gathered", 0)) == 1
    assert int(wm.get("stone_from_mines", 0)) == 0


def test_food_gathering_increments_food_counters() -> None:
    world = _flat_grass_world()
    village = _village(tier=1, population=8, houses=4)
    world.villages = [village]
    world.food.add((8, 8))
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.village_id = 1

    world.autopickup(agent)

    vm = world.villages[0]["production_metrics"]
    assert int(vm.get("total_food_gathered", 0)) == 1
    assert int(vm.get("direct_food_gathered", 0)) == 1
    wm = world.production_metrics
    assert int(wm.get("total_food_gathered", 0)) == 1
    assert int(wm.get("direct_food_gathered", 0)) == 1


def test_lumberyard_supported_gathering_splits_direct_and_specialized() -> None:
    world = _flat_grass_world()
    village = _village(tier=2, population=12, houses=5, center_x=10, center_y=10)
    world.villages = [village]
    world.roads.add((10, 9))
    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    world.wood.update({(9, 9), (9, 10), (9, 11), (8, 10)})
    world.tiles[9][9] = "F"
    world.tiles[10][9] = "F"
    world.tiles[11][9] = "F"
    world.tiles[10][8] = "F"
    world.buildings["b-lumber"] = {
        "building_id": "b-lumber",
        "type": "lumberyard",
        "x": 9,
        "y": 10,
        "village_id": 1,
        "village_uid": village["village_uid"],
        "operational_state": "active",
        "linked_resource_type": "wood",
        "linked_resource_tiles_count": 4,
        "connected_to_road": True,
    }
    world.wood.add((9, 12))
    world.tiles[12][9] = "F"
    bonus, source = building_system.production_bonus_details_for_resource(world, village, "wood", (9, 12))
    assert source == "lumberyard"
    expected_total = 1 + int(bonus)

    agent = Agent(x=9, y=12, brain=None, is_player=False, player_id=None)
    agent.village_id = 1
    assert world.gather_resource(agent) is True

    vm = world.villages[0]["production_metrics"]
    assert int(vm.get("total_wood_gathered", 0)) == expected_total
    assert int(vm.get("wood_from_lumberyards", 0)) == int(bonus)
    assert int(vm.get("direct_wood_gathered", 0)) == (expected_total - int(bonus))
    assert int(world.specialization_diagnostics["lumberyard"].get("used_for_production_count", 0)) >= 1


def test_mine_supported_gathering_splits_direct_and_specialized() -> None:
    world = _flat_grass_world()
    village = _village(tier=2, population=12, houses=5, center_x=10, center_y=10)
    world.villages = [village]
    world.roads.add((10, 9))
    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    world.stone.update({(11, 9), (11, 10), (11, 11), (12, 10)})
    world.tiles[9][11] = "M"
    world.tiles[10][11] = "M"
    world.tiles[11][11] = "M"
    world.tiles[10][12] = "M"
    world.buildings["b-mine"] = {
        "building_id": "b-mine",
        "type": "mine",
        "x": 11,
        "y": 10,
        "village_id": 1,
        "village_uid": village["village_uid"],
        "operational_state": "active",
        "linked_resource_type": "stone",
        "linked_resource_tiles_count": 4,
        "connected_to_road": True,
    }
    world.stone.add((11, 12))
    world.tiles[12][11] = "M"
    bonus, source = building_system.production_bonus_details_for_resource(world, village, "stone", (11, 12))
    assert source == "mine"
    expected_total = 1 + int(bonus)

    agent = Agent(x=11, y=12, brain=None, is_player=False, player_id=None)
    agent.village_id = 1
    assert world.gather_resource(agent) is True

    vm = world.villages[0]["production_metrics"]
    assert int(vm.get("total_stone_gathered", 0)) == expected_total
    assert int(vm.get("stone_from_mines", 0)) == int(bonus)
    assert int(vm.get("direct_stone_gathered", 0)) == (expected_total - int(bonus))
    assert int(world.specialization_diagnostics["mine"].get("used_for_production_count", 0)) >= 1


def test_choose_next_building_type_is_deterministic() -> None:
    world = _flat_grass_world()
    village = _village(tier=2, population=14, houses=6)
    village["storage"] = {"food": 12, "wood": 1, "stone": 1}
    village["needs"] = {"need_storage": False, "need_housing": True}
    world.villages = [village]
    world.farm_plots[(9, 10)] = {"x": 9, "y": 10, "village_id": 1}
    world.roads.update({(10, 9), (11, 9)})
    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    world.stone.update({(12, 10), (13, 10), (12, 11), (13, 11)})
    world.tiles[10][12] = "M"

    first = building_system.choose_next_building_type_for_village(world, village)
    second = building_system.choose_next_building_type_for_village(world, village)
    assert first == second


def test_choose_next_prefers_recommended_over_available() -> None:
    world = _flat_grass_world()
    village = _village(tier=2, population=14, houses=6)
    village["storage"] = {"food": 12, "wood": 1, "stone": 0}
    village["needs"] = {}
    world.villages = [village]
    world.farm_plots[(9, 10)] = {"x": 9, "y": 10, "village_id": 1}
    world.roads.update({(10, 9), (11, 9)})
    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    world.stone.update({(12, 10), (13, 10), (12, 11), (13, 11)})
    world.tiles[10][12] = "M"

    recommended = set(building_system.get_recommended_building_types_for_village(world, village))
    chosen = building_system.choose_next_building_type_for_village(world, village)
    assert chosen in recommended


def test_build_policy_attempts_try_build_type_successfully() -> None:
    world = _flat_grass_world()
    village = _village(tier=2, population=14, houses=6)
    village["storage"] = {"food": 12, "wood": 1, "stone": 1}
    world.villages = [village]
    world.farm_plots[(9, 10)] = {"x": 9, "y": 10, "village_id": 1}
    world.roads.update({(10, 9), (11, 9)})
    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    world.stone.update({(12, 10), (13, 10), (12, 11), (13, 11)})
    world.wood.update({(8, 10), (8, 11), (9, 10), (9, 11)})
    world.tiles[10][12] = "M"
    world.tiles[10][8] = "F"
    builder = Agent(x=12, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    world.agents = [builder]

    result = building_system.try_expand_village_buildings(world, village)
    assert "success" in result and "reason" in result and "building_type" in result
    if result["success"]:
        assert result["building_id"] in world.buildings


def test_policy_construction_build_creates_under_construction_site_not_instant_active() -> None:
    world = _flat_grass_world()
    village = _village(tier=1, population=10, houses=3)
    village["needs"] = {"need_storage": True}
    world.villages = [village]
    world.farm_plots[(9, 10)] = {"x": 9, "y": 10, "village_id": 1}
    builder = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    world.agents = [builder]

    result = building_system.try_expand_village_buildings(world, village)
    assert result["success"] is True
    site = world.buildings[str(result["building_id"])]
    assert str(site.get("type", "")) in {"storage", "house"}
    assert str(site.get("operational_state", "")) == "under_construction"
    assert int(site.get("construction_progress", 0)) == 0
    if str(site.get("type", "")) == "storage":
        assert (int(site.get("x", 0)), int(site.get("y", 0))) not in world.storage_buildings
    if str(site.get("type", "")) == "house":
        assert (int(site.get("x", 0)), int(site.get("y", 0))) not in world.structures


def test_under_construction_site_persists_while_still_recent_and_viable() -> None:
    world = _flat_grass_world()
    village = _village(tier=1, population=10, houses=3)
    world.villages = [village]
    agent = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    agent.village_id = 1

    created = building_system.try_build_type(
        world,
        agent,
        "storage",
        village_id=1,
        village_uid=village["village_uid"],
        as_construction_site=True,
    )
    assert created["success"] is True
    bid = str(created["building_id"])
    assert bid in world.buildings
    world.tick = int(world.tick) + 120
    removed = building_system.clear_stale_construction_sites(world)
    assert removed == 0
    assert bid in world.buildings
    site = world.buildings[bid]
    needs = building_system.get_outstanding_construction_needs(site)
    assert int(needs.get("wood", 0)) > 0 or int(needs.get("stone", 0)) > 0


def test_stale_or_invalid_construction_site_clears_safely() -> None:
    world = _flat_grass_world()
    village = _village(tier=1, population=10, houses=3)
    world.villages = [village]
    agent = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    agent.village_id = 1

    created = building_system.try_build_type(
        world,
        agent,
        "house",
        village_id=1,
        village_uid=village["village_uid"],
        as_construction_site=True,
    )
    assert created["success"] is True
    bid = str(created["building_id"])
    site = world.buildings[bid]
    site["construction_last_demand_tick"] = 0
    world.tick = 500
    removed = building_system.clear_stale_construction_sites(world, stale_ticks=120)
    assert removed >= 1
    assert bid not in world.buildings


def test_specialization_policy_selection_counter_increments_when_selected() -> None:
    world = _flat_grass_world()
    village = _village(tier=2, population=14, houses=6)
    village["storage"] = {"food": 12, "wood": 1, "stone": 1}
    world.villages = [village]
    world.farm_plots[(9, 10)] = {"x": 9, "y": 10, "village_id": 1}
    world.roads.update({(10, 9), (11, 9)})
    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])

    chosen = building_system.choose_next_building_type_for_village(world, village)
    assert chosen in {"mine", "lumberyard"}
    diag = world.specialization_diagnostics
    if chosen == "mine":
        assert int(diag["mine"].get("selected_by_policy_count", 0)) >= 1
    elif chosen == "lumberyard":
        assert int(diag["lumberyard"].get("selected_by_policy_count", 0)) >= 1


def test_build_policy_fails_safely_without_agents() -> None:
    world = _flat_grass_world()
    village = _village(tier=2, population=14, houses=6)
    world.villages = [village]
    result = building_system.try_expand_village_buildings(world, village)
    assert result["success"] is False
    assert result["reason"] in {"no_builder_agent", "no_candidate_building_type"}


def test_serialized_village_metrics_include_production_counters() -> None:
    world = _flat_grass_world()
    village = _village(tier=1, population=8, houses=4)
    world.villages = [village]
    world.wood.add((8, 8))
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.village_id = 1
    world.gather_resource(agent)
    world.update_village_ai()

    payload = serialize_dynamic_world_state(world)
    vm = payload["villages"][0]["metrics"]
    assert "total_wood_gathered" in vm
    assert "total_stone_gathered" in vm
    assert "wood_from_lumberyards" in vm
    assert "stone_from_mines" in vm


def test_market_food_pressure_lower_with_high_food_supply() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, population=8, houses=4, uid="v-000001")
    village["storage"] = {"food": 200, "wood": 10, "stone": 10}
    world.villages = [village]
    world.update_village_ai()
    market = world.villages[0].get("market_state", {})
    food = market.get("food", {})
    assert float(food.get("pressure", 1.0)) < 0.2
    assert float(food.get("local_price_index", 2.0)) <= 1.0


def test_market_food_pressure_higher_with_low_food_and_higher_population() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, population=18, houses=4, uid="v-000001")
    village["storage"] = {"food": 2, "wood": 10, "stone": 10}
    world.villages = [village]
    world.update_village_ai()
    market = world.villages[0].get("market_state", {})
    food = market.get("food", {})
    assert float(food.get("pressure", 0.0)) > 0.6
    assert float(food.get("local_price_index", 0.0)) > 1.0


def test_market_construction_demand_raises_wood_and_stone_pressure() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, population=10, houses=4, uid="v-000001")
    village["storage"] = {"food": 50, "wood": 3, "stone": 2}
    world.villages = [village]
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "house",
        "x": 10,
        "y": 10,
        "footprint": [{"x": 10, "y": 10}],
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {
            "wood_needed": 8,
            "stone_needed": 5,
            "wood_reserved": 1,
            "stone_reserved": 0,
        },
    }
    world.update_village_ai()
    market = world.villages[0].get("market_state", {})
    assert float((market.get("wood") or {}).get("pressure", 0.0)) > 0.2
    assert float((market.get("stone") or {}).get("pressure", 0.0)) > 0.2


def test_market_price_index_is_deterministic_and_bounded() -> None:
    w1 = _flat_grass_world()
    w2 = _flat_grass_world()
    v1 = _village(village_id=1, population=12, houses=4, uid="v-000001")
    v2 = _village(village_id=1, population=12, houses=4, uid="v-000001")
    v1["storage"] = {"food": 12, "wood": 4, "stone": 2}
    v2["storage"] = {"food": 12, "wood": 4, "stone": 2}
    w1.villages = [v1]
    w2.villages = [v2]
    w1.update_village_ai()
    w2.update_village_ai()
    m1 = w1.villages[0]["market_state"]
    m2 = w2.villages[0]["market_state"]
    assert m1 == m2
    for resource in ("food", "wood", "stone"):
        entry = m1[resource]
        assert 0.0 <= float(entry["pressure"]) <= 1.0
        assert 0.5 <= float(entry["local_price_index"]) <= 2.0


def _policy_ready_world_two_villages() -> World:
    world = _flat_grass_world()
    v1 = _village(village_id=1, uid="v-000001", tier=1, population=8, houses=4, center_x=10, center_y=10)
    v2 = _village(village_id=2, uid="v-000002", tier=1, population=8, houses=4, center_x=30, center_y=30)
    world.villages = [v1, v2]
    b1 = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    b1.village_id = 1
    b1.role = "builder"
    b2 = Agent(x=30, y=30, brain=None, is_player=False, player_id=None)
    b2.village_id = 2
    b2.role = "builder"
    world.agents = [b1, b2]
    return world


def test_policy_success_starts_cooldown() -> None:
    world = _policy_ready_world_two_villages()
    village = world.villages[0]

    result = building_system.try_expand_village_buildings(world, village)
    assert result["success"] is True
    state = building_system.get_or_init_policy_build_state(village)
    assert state["last_policy_build_tick"] == world.tick
    assert state["next_policy_build_tick"] == world.tick + building_system.POLICY_BUILD_COOLDOWN_TICKS
    assert building_system.policy_build_cooldown_remaining(world, village) > 0


def test_policy_cooldown_blocks_immediate_second_build() -> None:
    world = _policy_ready_world_two_villages()
    village = world.villages[0]

    first = building_system.try_expand_village_buildings(world, village)
    assert first["success"] is True
    second = building_system.try_expand_village_buildings(world, village)
    assert second["success"] is False
    assert second["reason"] == "cooldown_active"


def test_policy_can_build_again_after_cooldown_expires() -> None:
    world = _policy_ready_world_two_villages()
    village = world.villages[0]

    first = building_system.try_expand_village_buildings(world, village)
    assert first["success"] is True
    state = building_system.get_or_init_policy_build_state(village)
    world.tick = state["next_policy_build_tick"]
    second = building_system.try_expand_village_buildings(world, village)
    assert second["success"] is True


def test_policy_pacing_is_deterministic_for_same_setup() -> None:
    world_a = _policy_ready_world_two_villages()
    world_b = _policy_ready_world_two_villages()

    res_a = building_system.try_expand_village_buildings(world_a, world_a.villages[0])
    res_b = building_system.try_expand_village_buildings(world_b, world_b.villages[0])
    assert res_a["success"] == res_b["success"]
    assert res_a["building_type"] == res_b["building_type"]
    assert res_a["position"] == res_b["position"]


def test_run_policy_multi_village_respects_global_tick_bound() -> None:
    world = _policy_ready_world_two_villages()
    before = len(world.buildings)
    building_system.run_village_build_policy(world, max_attempts_per_tick=1)
    after = len(world.buildings)
    assert after - before <= 1
    assert after - before >= 1


def test_serialized_village_metrics_include_policy_pacing_debug_fields() -> None:
    world = _policy_ready_world_two_villages()
    village = world.villages[0]
    building_system.try_expand_village_buildings(world, village)
    world.update_village_ai()
    payload = serialize_dynamic_world_state(world)
    vm = [v for v in payload["villages"] if v["id"] == village["id"]][0]["metrics"]
    assert "last_policy_build_tick" in vm
    assert "next_policy_build_tick" in vm
    assert "policy_attempts_in_window" in vm
    assert "policy_build_cooldown_remaining" in vm


def _specialist_ready_world() -> World:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001", tier=2, population=14, houses=6, center_x=10, center_y=10)
    village["storage"] = {"food": 12, "wood": 2, "stone": 2}
    world.villages = [village]
    world.farm_plots[(9, 10)] = {"x": 9, "y": 10, "village_id": 1}
    world.roads.update({(10, 9), (11, 9), (12, 9), (8, 10)})
    world.stone.update({(12, 10), (13, 10), (12, 11), (13, 11)})
    world.wood.update({(8, 10), (8, 11), (9, 10), (9, 11)})
    world.tiles[10][12] = "M"
    world.tiles[10][8] = "F"
    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    builder = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    mine = building_system.try_build_type(world, builder, "mine", village_id=1, village_uid=village["village_uid"])
    lumberyard = building_system.try_build_type(
        world, builder, "lumberyard", village_id=1, village_uid=village["village_uid"]
    )
    assert mine["success"] is True
    assert lumberyard["success"] is True
    world.buildings[mine["building_id"]]["connected_to_road"] = True
    world.buildings[lumberyard["building_id"]]["connected_to_road"] = True
    world.agents = []
    for idx in range(8):
        a = Agent(x=10 + (idx % 2), y=10 + (idx // 2), brain=None, is_player=False, player_id=None)
        a.agent_id = f"a-{idx:02d}"
        a.village_id = 1
        world.agents.append(a)
    world.update_village_ai()
    return world


def test_village_with_mine_gets_miner_assigned() -> None:
    world = _specialist_ready_world()
    world.assign_village_roles()
    miners = [a for a in world.agents if getattr(a, "role", "") == "miner"]
    assert len(miners) >= 1
    assert any(getattr(a, "assigned_building_id", None) is not None for a in miners)
    assert int(world.specialization_diagnostics["mine"].get("staffed_count", 0)) >= 1


def test_village_with_lumberyard_gets_woodcutter_assigned() -> None:
    world = _specialist_ready_world()
    world.assign_village_roles()
    woodcutters = [a for a in world.agents if getattr(a, "role", "") == "woodcutter"]
    assert len(woodcutters) >= 1
    assert any(getattr(a, "assigned_building_id", None) is not None for a in woodcutters)
    assert int(world.specialization_diagnostics["lumberyard"].get("staffed_count", 0)) >= 1


def test_specialist_assignment_is_deterministic() -> None:
    world_a = _specialist_ready_world()
    world_b = _specialist_ready_world()
    world_a.assign_village_roles()
    world_b.assign_village_roles()
    map_a = [(a.agent_id, a.role, getattr(a, "assigned_building_id", None)) for a in sorted(world_a.agents, key=lambda x: x.agent_id)]
    map_b = [(a.agent_id, a.role, getattr(a, "assigned_building_id", None)) for a in sorted(world_b.agents, key=lambda x: x.agent_id)]
    assert map_a == map_b


def test_specialists_improve_production_bonus() -> None:
    world_without = _specialist_ready_world()
    world_with = _specialist_ready_world()

    for a in world_without.agents:
        a.role = "hauler"
        a.assigned_building_id = None

    world_with.assign_village_roles()
    gatherer_without = world_without.agents[0]
    gatherer_with = world_with.agents[0]
    gatherer_without.x = 12
    gatherer_without.y = 10
    gatherer_with.x = 12
    gatherer_with.y = 10

    assert world_without.gather_resource(gatherer_without) is True
    assert world_with.gather_resource(gatherer_with) is True

    stone_without = gatherer_without.inventory["stone"]
    stone_with = gatherer_with.inventory["stone"]
    assert stone_with > stone_without


def test_specialist_assignment_preserves_core_roles() -> None:
    world = _specialist_ready_world()
    world.assign_village_roles()
    specialist_count = sum(1 for a in world.agents if a.role in {"miner", "woodcutter"})
    assert specialist_count < len(world.agents)
    assert any(a.role in {"farmer", "builder", "hauler", "forager"} for a in world.agents)


def test_serialized_metrics_include_specialist_counts() -> None:
    world = _specialist_ready_world()
    world.assign_village_roles()
    world.update_village_ai()
    payload = serialize_dynamic_world_state(world)
    vm = payload["villages"][0]["metrics"]
    assert "miners_count" in vm
    assert "woodcutters_count" in vm


def test_serialized_village_includes_market_state() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, population=9, houses=4, uid="v-000001")
    village["storage"] = {"food": 8, "wood": 5, "stone": 3}
    world.villages = [village]
    world.update_village_ai()
    payload = serialize_dynamic_world_state(world)
    serialized_village = payload["villages"][0]
    assert "market_state" in serialized_village
    market = serialized_village["market_state"]
    assert set(market.keys()) == {"food", "wood", "stone"}


def test_specialist_targets_raise_for_stone_demand_with_active_mine() -> None:
    world = _specialist_ready_world()
    for b in world.buildings.values():
        if b.get("type") == "lumberyard":
            b["operational_state"] = "inactive"
    storage_building = [b for b in world.buildings.values() if b.get("type") == "storage"][0]
    storage_building["storage"]["stone"] = 0
    world.update_village_ai()
    world.assign_village_roles()
    vm = world.villages[0].get("metrics", {})
    assert int(vm.get("miner_target", 0)) > 0


def test_specialist_targets_raise_for_wood_demand_with_active_lumberyard() -> None:
    world = _specialist_ready_world()
    for b in world.buildings.values():
        if b.get("type") == "mine":
            b["operational_state"] = "inactive"
    storage_building = [b for b in world.buildings.values() if b.get("type") == "storage"][0]
    storage_building["storage"]["wood"] = 0
    world.update_village_ai()
    world.assign_village_roles()
    vm = world.villages[0].get("metrics", {})
    assert int(vm.get("woodcutter_target", 0)) > 0


def test_specialist_targets_are_bounded_and_preserve_core_workers() -> None:
    world = _specialist_ready_world()
    world.agents = world.agents[:5]
    world.villages[0]["population"] = 5
    world.update_village_ai()
    world.assign_village_roles()
    specialists = [a for a in world.agents if getattr(a, "role", "") in {"miner", "woodcutter"}]
    assert len(specialists) <= 2
    assert len(specialists) < len(world.agents)


def test_specialists_reduce_when_material_demand_drops() -> None:
    world = _specialist_ready_world()
    world.assign_village_roles()
    before = sum(1 for a in world.agents if getattr(a, "role", "") in {"miner", "woodcutter"})
    assert before >= 1

    storage_building = [b for b in world.buildings.values() if b.get("type") == "storage"][0]
    storage_building["storage"]["wood"] = 100
    storage_building["storage"]["stone"] = 100
    world.villages[0]["storage"]["wood"] = 100
    world.villages[0]["storage"]["stone"] = 100
    world.tick += role_system.SPECIALIST_REBALANCE_INTERVAL_TICKS
    world.update_village_ai()
    world.assign_village_roles()
    after = sum(1 for a in world.agents if getattr(a, "role", "") in {"miner", "woodcutter"})
    assert after <= before
    assert after == 0


def test_assigned_building_id_coherent_after_specialist_reallocation() -> None:
    world = _specialist_ready_world()
    world.assign_village_roles()

    storage_building = [b for b in world.buildings.values() if b.get("type") == "storage"][0]
    storage_building["storage"]["wood"] = 100
    storage_building["storage"]["stone"] = 100
    world.update_village_ai()
    world.assign_village_roles()

    for agent in world.agents:
        if getattr(agent, "role", "") in {"miner", "woodcutter"}:
            assert getattr(agent, "assigned_building_id", None) is not None
        else:
            assert getattr(agent, "assigned_building_id", None) is None


def test_serialized_metrics_include_specialist_targets() -> None:
    world = _specialist_ready_world()
    world.assign_village_roles()
    world.update_village_ai()
    payload = serialize_dynamic_world_state(world)
    vm = payload["villages"][0]["metrics"]
    assert "miner_target" in vm
    assert "woodcutter_target" in vm
    assert "specialist_allocation_pressure" in vm


def test_specialists_do_not_churn_before_rebalance_interval() -> None:
    world = _specialist_ready_world()
    world.assign_village_roles()
    initial = {
        a.agent_id: (a.role, getattr(a, "assigned_building_id", None))
        for a in sorted(world.agents, key=lambda x: x.agent_id)
    }

    # Boundary-like oscillation in stocks shouldn't immediately churn specialists
    # before the next deterministic rebalance checkpoint.
    for i in range(role_system.SPECIALIST_REBALANCE_INTERVAL_TICKS - 1):
        world.tick += 1
        storage_building = [b for b in world.buildings.values() if b.get("type") == "storage"][0]
        if i % 2 == 0:
            storage_building["storage"]["stone"] = 0
            storage_building["storage"]["wood"] = 100
        else:
            storage_building["storage"]["stone"] = 100
            storage_building["storage"]["wood"] = 0
        world.update_village_ai()
        world.assign_village_roles()

    final = {
        a.agent_id: (a.role, getattr(a, "assigned_building_id", None))
        for a in sorted(world.agents, key=lambda x: x.agent_id)
    }
    assert initial == final


def test_specialist_rebalance_runs_after_interval() -> None:
    world = _specialist_ready_world()
    world.assign_village_roles()
    before = sum(1 for a in world.agents if a.role in {"miner", "woodcutter"})
    assert before >= 1

    storage_building = [b for b in world.buildings.values() if b.get("type") == "storage"][0]
    storage_building["storage"]["stone"] = 100
    storage_building["storage"]["wood"] = 100
    world.villages[0]["storage"]["stone"] = 100
    world.villages[0]["storage"]["wood"] = 100
    world.tick += role_system.SPECIALIST_REBALANCE_INTERVAL_TICKS
    world.update_village_ai()
    world.assign_village_roles()
    after = sum(1 for a in world.agents if a.role in {"miner", "woodcutter"})
    assert after == 0


def test_specialist_promotion_occurs_when_demand_rises() -> None:
    world = _specialist_ready_world()
    storage_building = [b for b in world.buildings.values() if b.get("type") == "storage"][0]
    storage_building["storage"]["stone"] = 100
    storage_building["storage"]["wood"] = 100
    world.villages[0]["storage"]["stone"] = 100
    world.villages[0]["storage"]["wood"] = 100
    world.update_village_ai()
    world.assign_village_roles()
    assert sum(1 for a in world.agents if a.role in {"miner", "woodcutter"}) == 0

    world.tick += role_system.SPECIALIST_REBALANCE_INTERVAL_TICKS
    storage_building["storage"]["stone"] = 0
    storage_building["storage"]["wood"] = 0
    world.update_village_ai()
    world.assign_village_roles()
    assert sum(1 for a in world.agents if a.role in {"miner", "woodcutter"}) >= 1


def test_serialized_metrics_include_specialist_rebalance_debug_fields() -> None:
    world = _specialist_ready_world()
    world.assign_village_roles()
    world.update_village_ai()
    payload = serialize_dynamic_world_state(world)
    vm = payload["villages"][0]["metrics"]
    assert "last_specialist_rebalance_tick" in vm
    assert "specialist_rebalance_due" in vm


def test_gather_to_inventory_then_deposit_to_storage() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001", tier=1, population=8, houses=4, center_x=10, center_y=10)
    world.villages = [village]
    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    world.wood.add((9, 10))
    agent = Agent(x=9, y=10, brain=None, is_player=False, player_id=None)
    agent.village_id = 1

    assert world.gather_resource(agent) is True
    assert agent.inventory["wood"] >= 1
    assert world.villages[0]["storage"]["wood"] == 0

    agent.x = 10
    agent.y = 10
    assert agent._deposit_inventory_to_storage(world) is True
    assert agent.inventory["wood"] == 0
    assert world.villages[0]["storage"]["wood"] >= 1


def test_storage_building_state_is_updated_on_deposit() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001", tier=1, population=8, houses=4, center_x=10, center_y=10)
    world.villages = [village]
    storage = world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    assert storage is not None

    agent = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    agent.village_id = 1
    agent.inventory["stone"] = 2
    assert agent._deposit_inventory_to_storage(world) is True
    assert world.buildings[storage["building_id"]]["storage"]["stone"] == 2
    assert world.villages[0]["storage"]["stone"] == 2


def test_hauler_deposits_inventory_via_logistics_task() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001", tier=1, population=8, houses=4, center_x=10, center_y=10)
    world.villages = [village]
    storage = world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    assert storage is not None

    hauler = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    hauler.village_id = 1
    hauler.role = "hauler"
    hauler.task = "village_logistics"
    hauler.inventory["wood"] = 3
    world.agents = [hauler]

    hauler.update(world)
    assert hauler.inventory["wood"] == 0
    assert world.buildings[storage["building_id"]]["storage"]["wood"] >= 3


def test_build_house_consumes_builder_inventory_not_global_magic() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001", tier=1, population=8, houses=4, center_x=10, center_y=10)
    village["storage"] = {"food": 0, "wood": 20, "stone": 20}
    world.villages = [village]
    storage = world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    assert storage is not None
    builder = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1

    # First attempt withdraws from concrete storage, then build consumes carried materials.
    assert builder._withdraw_build_materials(world, wood_need=5, stone_need=3) is True
    pre_w = builder.inventory["wood"]
    pre_s = builder.inventory["stone"]
    assert world.try_build_house(builder) is False
    site = [b for b in world.buildings.values() if b.get("type") == "house" and b.get("operational_state") == "under_construction"][0]
    required_work = int(site.get("construction_required_work", 0))
    for _ in range(max(0, required_work - 1)):
        world.try_build_house(builder)
    assert world.buildings[site["building_id"]]["operational_state"] == "active"
    assert builder.inventory["wood"] < pre_w
    assert builder.inventory["stone"] < pre_s


def test_serialization_includes_agent_inventory_and_storage_state() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001", tier=1, population=8, houses=4, center_x=10, center_y=10)
    world.villages = [village]
    storage = world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    assert storage is not None
    a = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    a.agent_id = "agent-log"
    a.village_id = 1
    a.inventory["food"] = 2
    world.agents = [a]
    a._deposit_inventory_to_storage(world)

    payload = serialize_dynamic_world_state(world)
    agent_payload = [x for x in payload["agents"] if x["agent_id"] == "agent-log"][0]
    storage_payload = [b for b in payload["buildings"] if b["type"] == "storage"][0]
    assert "inventory" in agent_payload
    assert "max_inventory" in agent_payload
    assert storage_payload["storage"] is not None
    assert "wood" in storage_payload["storage"]


def _construction_ready_world() -> tuple[World, dict, Agent, Agent]:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001", tier=1, population=10, houses=4, center_x=10, center_y=10)
    village["storage"] = {"food": 20, "wood": 20, "stone": 20}
    world.villages = [village]
    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    builder = Agent(x=11, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    hauler = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    hauler.village_id = 1
    hauler.role = "hauler"
    hauler.task = "village_logistics"
    return world, village, builder, hauler


def test_early_housing_mode_finds_local_site_when_builder_area_is_blocked() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001", tier=1, population=8, houses=0, center_x=10, center_y=10)
    world.villages = [village]
    builder = Agent(x=20, y=20, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    world.agents = [builder]

    # Block immediate builder neighborhood so fallback search must use village anchors.
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            x = builder.x + dx
            y = builder.y + dy
            if 0 <= x < world.width and 0 <= y < world.height:
                world.tiles[y][x] = "W"

    # Keep a local viable area near village center but include road tiles that must be avoided.
    world.roads.add((10, 10))
    world.roads.add((10, 11))
    world.roads.add((11, 10))

    result = building_system.try_build_house(world, builder)
    assert result is False  # Site created, but no completion yet.
    sites = [b for b in world.buildings.values() if b.get("type") == "house" and b.get("operational_state") == "under_construction"]
    assert len(sites) >= 1
    site = sites[0]
    sx, sy = int(site["x"]), int(site["y"])
    assert abs(sx - 10) + abs(sy - 10) <= 6
    assert (sx, sy) not in world.roads
    assert str(site.get("operational_state", "")) == "under_construction"


def test_early_housing_mode_still_blocks_invalid_terrain() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001", tier=1, population=8, houses=0, center_x=10, center_y=10)
    world.villages = [village]
    builder = Agent(x=20, y=20, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    world.agents = [builder]

    # Everything non-buildable.
    world.tiles = [["W" for _ in range(world.width)] for _ in range(world.height)]

    assert building_system.try_build_house(world, builder) is False
    sites = [b for b in world.buildings.values() if b.get("type") == "house" and b.get("operational_state") == "under_construction"]
    assert sites == []


def test_early_housing_site_does_not_overlap_existing_structures() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001", tier=1, population=8, houses=0, center_x=10, center_y=10)
    world.villages = [village]
    existing = world.place_building("house", 10, 10, village_id=1, village_uid=village["village_uid"])
    assert existing is not None
    builder = Agent(x=20, y=20, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    world.agents = [builder]

    for dy in range(-3, 4):
        for dx in range(-3, 4):
            x = builder.x + dx
            y = builder.y + dy
            if 0 <= x < world.width and 0 <= y < world.height:
                world.tiles[y][x] = "W"

    assert building_system.try_build_house(world, builder) is False
    sites = [
        b
        for b in world.buildings.values()
        if b.get("type") == "house"
        and b.get("operational_state") == "under_construction"
        and str(b.get("building_id", "")) != str(existing.get("building_id", ""))
    ]
    assert len(sites) >= 1
    site = sites[0]
    assert (int(site["x"]), int(site["y"])) != (int(existing["x"]), int(existing["y"]))


def test_mature_village_keeps_stricter_local_siting_without_early_fallback() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001", tier=2, population=16, houses=5, center_x=10, center_y=10)
    world.villages = [village]
    # Existing houses indicate mature settlement.
    for i in range(3):
        built = world.place_building("house", 10 + i, 10, village_id=1, village_uid=village["village_uid"])
        assert built is not None
    builder = Agent(x=20, y=20, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    world.agents = [builder]

    # Block builder local search window; only far center area remains viable.
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            x = builder.x + dx
            y = builder.y + dy
            if 0 <= x < world.width and 0 <= y < world.height:
                world.tiles[y][x] = "W"

    assert building_system.try_build_house(world, builder) is False
    sites = [b for b in world.buildings.values() if b.get("type") == "house" and b.get("operational_state") == "under_construction"]
    assert sites == []


def _redistribution_ready_world() -> tuple[World, dict, Agent]:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001", tier=1, population=10, houses=4, center_x=10, center_y=10)
    world.villages = [village]
    s1 = world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    s2 = world.place_building("storage", 14, 10, village_id=1, village_uid=village["village_uid"])
    assert s1 is not None and s2 is not None
    world.buildings[s1["building_id"]]["storage"]["wood"] = 30
    world.buildings[s1["building_id"]]["storage"]["stone"] = 20
    world.buildings[s2["building_id"]]["storage"]["wood"] = 0
    world.buildings[s2["building_id"]]["storage"]["stone"] = 0
    village["storage"] = {"food": 0, "wood": 30, "stone": 20}
    hauler = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    hauler.village_id = 1
    hauler.role = "hauler"
    hauler.task = "village_logistics"
    return world, village, hauler


def test_construction_request_created_for_under_construction_house() -> None:
    world, village, builder, _ = _construction_ready_world()
    world.agents = [builder]
    assert building_system.try_build_house(world, builder) is False
    sites = [b for b in world.buildings.values() if b.get("type") == "house" and b.get("operational_state") == "under_construction"]
    assert len(sites) == 1
    req = sites[0].get("construction_request", {})
    assert req.get("wood_needed") == HOUSE_WOOD_COST
    assert req.get("stone_needed") == HOUSE_STONE_COST
    assert req.get("wood_reserved") == 0
    assert req.get("stone_reserved") == 0


def test_construction_reservation_does_not_exceed_unmet_need() -> None:
    world, village, builder, _ = _construction_ready_world()
    world.agents = [builder]
    building_system.try_build_house(world, builder)
    site = [b for b in world.buildings.values() if b.get("type") == "house" and b.get("operational_state") == "under_construction"][0]
    bid = site["building_id"]
    first = building_system.reserve_materials_for_construction(world, bid, "wood", 999)
    second = building_system.reserve_materials_for_construction(world, bid, "wood", 999)
    assert first == HOUSE_WOOD_COST
    assert second == 0


def test_hauler_can_reserve_and_deliver_to_construction_target() -> None:
    world, village, builder, hauler = _construction_ready_world()
    world.agents = [builder, hauler]
    building_system.try_build_house(world, builder)
    site = [b for b in world.buildings.values() if b.get("type") == "house" and b.get("operational_state") == "under_construction"][0]
    bid = site["building_id"]

    assert building_system.run_hauler_construction_delivery(world, hauler) is True
    assert hauler.delivery_target_building_id == bid
    assert hauler.delivery_resource_type in {"wood", "stone"}
    assert hauler.inventory.get(hauler.delivery_resource_type, 0) > 0

    hauler.x = site["x"]
    hauler.y = site["y"]
    assert building_system.run_hauler_construction_delivery(world, hauler) is True
    updated = world.buildings[bid]
    buffer = updated.get("construction_buffer", {})
    assert buffer.get("wood", 0) + buffer.get("stone", 0) > 0


def test_builder_consumes_delivered_buffer_and_completes_house() -> None:
    world, village, builder, hauler = _construction_ready_world()
    world.agents = [builder, hauler]
    building_system.try_build_house(world, builder)
    site = [b for b in world.buildings.values() if b.get("type") == "house" and b.get("operational_state") == "under_construction"][0]
    bid = site["building_id"]

    # Deliver all needed resources via deterministic reservation+fulfillment.
    reserved_w = building_system.reserve_materials_for_construction(world, bid, "wood", HOUSE_WOOD_COST)
    reserved_s = building_system.reserve_materials_for_construction(world, bid, "stone", HOUSE_STONE_COST)
    assert reserved_w == HOUSE_WOOD_COST
    assert reserved_s == HOUSE_STONE_COST
    assert building_system.fulfill_reserved_delivery(world, bid, "wood", HOUSE_WOOD_COST) == HOUSE_WOOD_COST
    assert building_system.fulfill_reserved_delivery(world, bid, "stone", HOUSE_STONE_COST) == HOUSE_STONE_COST

    builder.x = site["x"]
    builder.y = site["y"]
    required_work = int(site.get("construction_required_work", 0))
    assert required_work >= 2
    for _ in range(required_work - 1):
        assert building_system.try_build_house(world, builder) is False
        still_pending = world.buildings[bid]
        assert still_pending["operational_state"] == "under_construction"
    assert building_system.try_build_house(world, builder) is True
    built = world.buildings[bid]
    assert built["operational_state"] == "active"
    assert built.get("construction_request") is None
    assert built.get("construction_buffer") is None
    assert int(built.get("construction_progress", 0)) == int(built.get("construction_required_work", 0))


def test_builder_cannot_progress_construction_from_far_away() -> None:
    world, _, builder, _ = _construction_ready_world()
    world.agents = [builder]
    assert building_system.try_build_house(world, builder) is False
    site = [b for b in world.buildings.values() if b.get("type") == "house" and b.get("operational_state") == "under_construction"][0]
    bid = site["building_id"]
    assert building_system.reserve_materials_for_construction(world, bid, "wood", HOUSE_WOOD_COST) == HOUSE_WOOD_COST
    assert building_system.reserve_materials_for_construction(world, bid, "stone", HOUSE_STONE_COST) == HOUSE_STONE_COST
    assert building_system.fulfill_reserved_delivery(world, bid, "wood", HOUSE_WOOD_COST) == HOUSE_WOOD_COST
    assert building_system.fulfill_reserved_delivery(world, bid, "stone", HOUSE_STONE_COST) == HOUSE_STONE_COST

    builder.x = site["x"] + 4
    builder.y = site["y"] + 4
    assert building_system.try_build_house(world, builder) is False
    assert int(world.buildings[bid].get("construction_progress", 0)) == 0


def test_builder_prefers_nearest_existing_house_construction_site() -> None:
    world, _, builder, _ = _construction_ready_world()
    world.agents = [builder]
    # Two valid existing house sites in same village; builder should progress nearest one.
    near = building_system.place_building(
        world,
        "house",
        (builder.x + 1, builder.y),
        village_id=1,
        village_uid="v-000001",
        operational_state="under_construction",
        construction_request={"wood_needed": HOUSE_WOOD_COST, "stone_needed": HOUSE_STONE_COST, "food_needed": 0, "wood_reserved": 0, "stone_reserved": 0, "food_reserved": 0},
        construction_buffer={"wood": HOUSE_WOOD_COST, "stone": HOUSE_STONE_COST, "food": 0},
        construction_progress=0,
        construction_required_work=2,
    )
    far = building_system.place_building(
        world,
        "house",
        (builder.x + 6, builder.y + 6),
        village_id=1,
        village_uid="v-000001",
        operational_state="under_construction",
        construction_request={"wood_needed": HOUSE_WOOD_COST, "stone_needed": HOUSE_STONE_COST, "food_needed": 0, "wood_reserved": 0, "stone_reserved": 0, "food_reserved": 0},
        construction_buffer={"wood": HOUSE_WOOD_COST, "stone": HOUSE_STONE_COST, "food": 0},
        construction_progress=0,
        construction_required_work=2,
    )
    assert near is not None and far is not None

    assert building_system.try_build_house(world, builder) is False
    assert int(world.buildings[near["building_id"]].get("construction_progress", 0)) == 1
    assert int(world.buildings[far["building_id"]].get("construction_progress", 0)) == 0


def test_materials_alone_do_not_complete_construction_without_work_ticks() -> None:
    world, _, builder, _ = _construction_ready_world()
    world.agents = [builder]
    assert building_system.try_build_house(world, builder) is False
    site = [b for b in world.buildings.values() if b.get("type") == "house" and b.get("operational_state") == "under_construction"][0]
    bid = site["building_id"]
    assert building_system.reserve_materials_for_construction(world, bid, "wood", HOUSE_WOOD_COST) == HOUSE_WOOD_COST
    assert building_system.reserve_materials_for_construction(world, bid, "stone", HOUSE_STONE_COST) == HOUSE_STONE_COST
    assert building_system.fulfill_reserved_delivery(world, bid, "wood", HOUSE_WOOD_COST) == HOUSE_WOOD_COST
    assert building_system.fulfill_reserved_delivery(world, bid, "stone", HOUSE_STONE_COST) == HOUSE_STONE_COST
    assert world.buildings[bid]["operational_state"] == "under_construction"
    assert int(world.buildings[bid].get("construction_progress", 0)) == 0


def test_work_alone_does_not_complete_construction_without_materials() -> None:
    world, _, builder, _ = _construction_ready_world()
    world.agents = [builder]
    assert building_system.try_build_house(world, builder) is False
    site = [b for b in world.buildings.values() if b.get("type") == "house" and b.get("operational_state") == "under_construction"][0]
    bid = site["building_id"]
    builder.x = site["x"]
    builder.y = site["y"]
    for _ in range(3):
        assert building_system.try_build_house(world, builder) is False
    assert world.buildings[bid]["operational_state"] == "under_construction"
    assert int(world.buildings[bid].get("construction_progress", 0)) == 0


def test_construction_reservation_is_deterministic_for_same_setup() -> None:
    w1, _, b1, h1 = _construction_ready_world()
    w2, _, b2, h2 = _construction_ready_world()
    w1.agents = [b1, h1]
    w2.agents = [b2, h2]
    building_system.try_build_house(w1, b1)
    building_system.try_build_house(w2, b2)

    assert building_system.run_hauler_construction_delivery(w1, h1) is True
    assert building_system.run_hauler_construction_delivery(w2, h2) is True
    snap1 = (h1.delivery_target_building_id, h1.delivery_resource_type, h1.delivery_reserved_amount)
    snap2 = (h2.delivery_target_building_id, h2.delivery_resource_type, h2.delivery_reserved_amount)
    assert snap1 == snap2


def test_hauler_can_form_delivery_target_from_carried_materials_without_storage_supply() -> None:
    world, _, builder, hauler = _construction_ready_world()
    world.agents = [builder, hauler]
    building_system.try_build_house(world, builder)
    site = [b for b in world.buildings.values() if b.get("type") == "house" and b.get("operational_state") == "under_construction"][0]

    # Remove storage stock so delivery viability depends on carried goods.
    village = world.get_village_by_id(1)
    assert village is not None
    village["storage"]["wood"] = 0
    village["storage"]["stone"] = 0
    for b in world.buildings.values():
        if b.get("type") == "storage":
            b.setdefault("storage", {"food": 0, "wood": 0, "stone": 0})
            b["storage"]["wood"] = 0
            b["storage"]["stone"] = 0

    hauler.inventory["wood"] = 2
    assert building_system.run_hauler_construction_delivery(world, hauler) is True
    assert hauler.delivery_target_building_id == site["building_id"]
    assert hauler.delivery_resource_type == "wood"
    updated = world.buildings[site["building_id"]]
    assert int(updated.get("construction_buffer", {}).get("wood", 0)) >= 2


def test_builder_wait_signal_guides_hauler_target_selection() -> None:
    world, _, builder, hauler = _construction_ready_world()
    world.agents = [builder, hauler]
    # Create one under-construction house site, then force builder wait-on-delivery.
    assert building_system.try_build_house(world, builder) is False
    site = [b for b in world.buildings.values() if b.get("type") == "house" and b.get("operational_state") == "under_construction"][0]
    site["construction_buffer"] = {"wood": 0, "stone": 0, "food": 0}
    site["construction_request"] = {
        "wood_needed": HOUSE_WOOD_COST,
        "wood_reserved": 0,
        "stone_needed": HOUSE_STONE_COST,
        "stone_reserved": 0,
        "food_needed": 0,
        "food_reserved": 0,
    }
    builder.x = int(site["x"])
    builder.y = int(site["y"])
    builder.hunger = 10
    assert building_system.try_build_house(world, builder) is False
    assert int(site.get("builder_waiting_tick", -1)) >= 0

    # Remove storage material availability; target must still form from carried materials.
    village = world.get_village_by_id(1)
    assert village is not None
    village["storage"]["wood"] = 0
    village["storage"]["stone"] = 0
    for b in world.buildings.values():
        if b.get("type") == "storage":
            b.setdefault("storage", {"food": 0, "wood": 0, "stone": 0})
            b["storage"]["wood"] = 0
            b["storage"]["stone"] = 0

    hauler.inventory["wood"] = 1
    assert building_system.run_hauler_construction_delivery(world, hauler) is True
    assert hauler.delivery_target_building_id == site["building_id"]


def test_no_fake_delivery_or_progress_when_materials_unavailable() -> None:
    world, _, builder, hauler = _construction_ready_world()
    world.agents = [builder, hauler]
    assert building_system.try_build_house(world, builder) is False
    site = [b for b in world.buildings.values() if b.get("type") == "house" and b.get("operational_state") == "under_construction"][0]
    site["construction_buffer"] = {"wood": 0, "stone": 0, "food": 0}
    site["construction_request"] = {
        "wood_needed": HOUSE_WOOD_COST,
        "wood_reserved": 0,
        "stone_needed": HOUSE_STONE_COST,
        "stone_reserved": 0,
        "food_needed": 0,
        "food_reserved": 0,
    }
    # No storage resources and no carried resources -> no fake delivery/progress.
    village = world.get_village_by_id(1)
    assert village is not None
    village["storage"]["wood"] = 0
    village["storage"]["stone"] = 0
    for b in world.buildings.values():
        if b.get("type") == "storage":
            b.setdefault("storage", {"food": 0, "wood": 0, "stone": 0})
            b["storage"]["wood"] = 0
            b["storage"]["stone"] = 0
    hauler.inventory["wood"] = 0
    hauler.inventory["stone"] = 0
    progress_before = int(site.get("construction_progress", 0))
    events_before = len([e for e in world.events if str(e.get("type", "")) in {"delivered_material", "construction_progress"}])

    assert building_system.run_hauler_construction_delivery(world, hauler) is False
    assert int(site.get("construction_progress", 0)) == progress_before
    events_after = len([e for e in world.events if str(e.get("type", "")) in {"delivered_material", "construction_progress"}])
    assert events_after == events_before


def test_builder_local_self_supply_can_feed_nearby_construction_site() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001", tier=1, population=8, houses=3, center_x=10, center_y=10)
    village["storage"] = {"food": 10, "wood": 20, "stone": 20}
    world.villages = [village]
    storage = world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    assert storage is not None
    site = building_system.place_building(
        world,
        "house",
        (9, 10),
        village_id=1,
        village_uid=village["village_uid"],
        operational_state="under_construction",
        construction_request={
            "wood_needed": HOUSE_WOOD_COST,
            "wood_reserved": 0,
            "stone_needed": HOUSE_STONE_COST,
            "stone_reserved": 0,
            "food_needed": 0,
            "food_reserved": 0,
        },
        construction_buffer={"wood": 0, "stone": 0, "food": 0},
        construction_progress=0,
        construction_required_work=3,
    )
    assert site is not None
    builder = Agent(x=9, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    world.agents = [builder]

    assert building_system.try_build_house(world, builder) is False
    diag = world.compute_builder_self_supply_snapshot()
    assert int(diag["builder_self_supply_attempt_count"]) >= 1
    assert int(diag["builder_self_supply_success_count"]) >= 1
    updated = world.buildings[site["building_id"]]
    assert int(updated.get("construction_buffer", {}).get("wood", 0)) + int(updated.get("construction_buffer", {}).get("stone", 0)) >= 1

    bid = str(site["building_id"])
    assert building_system.reserve_materials_for_construction(world, bid, "wood", HOUSE_WOOD_COST) >= 0
    assert building_system.reserve_materials_for_construction(world, bid, "stone", HOUSE_STONE_COST) >= 0
    # After local self-supply moved some material, completion is still real and requires buffer/work.
    assert int(updated.get("construction_progress", 0)) == 0


def test_builder_local_self_supply_rejects_long_range_source() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001", tier=1, population=8, houses=3, center_x=10, center_y=10)
    village["storage"] = {"food": 10, "wood": 20, "stone": 20}
    world.villages = [village]
    storage = world.place_building("storage", 18, 18, village_id=1, village_uid=village["village_uid"])
    assert storage is not None
    site = building_system.place_building(
        world,
        "house",
        (12, 10),
        village_id=1,
        village_uid=village["village_uid"],
        operational_state="under_construction",
        construction_request={
            "wood_needed": HOUSE_WOOD_COST,
            "wood_reserved": 0,
            "stone_needed": HOUSE_STONE_COST,
            "stone_reserved": 0,
            "food_needed": 0,
            "food_reserved": 0,
        },
        construction_buffer={"wood": 0, "stone": 0, "food": 0},
        construction_progress=0,
        construction_required_work=3,
    )
    assert site is not None
    builder = Agent(x=12, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    world.agents = [builder]

    assert building_system.try_build_house(world, builder) is False
    diag = world.compute_builder_self_supply_snapshot()
    assert int(diag["builder_self_supply_attempt_count"]) >= 1
    assert int(diag["builder_self_supply_success_count"]) == 0
    reasons = diag.get("builder_self_supply_failure_reasons", {})
    assert int(reasons.get("source_too_far", 0)) >= 1 or int(reasons.get("no_local_viable_source", 0)) >= 1
    updated = world.buildings[site["building_id"]]
    assert int(updated.get("construction_buffer", {}).get("wood", 0)) == 0
    assert int(updated.get("construction_buffer", {}).get("stone", 0)) == 0


def test_builder_local_self_supply_does_not_bypass_site_range_or_fake_resources() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001", tier=1, population=8, houses=3, center_x=10, center_y=10)
    village["storage"] = {"food": 10, "wood": 0, "stone": 0}
    world.villages = [village]
    storage = world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    assert storage is not None
    site = building_system.place_building(
        world,
        "house",
        (12, 10),
        village_id=1,
        village_uid=village["village_uid"],
        operational_state="under_construction",
        construction_request={
            "wood_needed": HOUSE_WOOD_COST,
            "wood_reserved": 0,
            "stone_needed": HOUSE_STONE_COST,
            "stone_reserved": 0,
            "food_needed": 0,
            "food_reserved": 0,
        },
        construction_buffer={"wood": 0, "stone": 0, "food": 0},
        construction_progress=0,
        construction_required_work=3,
    )
    assert site is not None
    builder = Agent(x=16, y=16, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    world.agents = [builder]

    assert building_system.try_build_house(world, builder) is False
    diag = world.compute_builder_self_supply_snapshot()
    # Too far from site: no self-supply side effects and no fake material creation.
    assert int(diag["builder_self_supply_attempt_count"]) == 0
    updated = world.buildings[site["building_id"]]
    assert int(updated.get("construction_buffer", {}).get("wood", 0)) == 0
    assert int(updated.get("construction_buffer", {}).get("stone", 0)) == 0


def test_builder_local_self_supply_disabled_for_mature_village_with_hauler() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001", tier=2, population=16, houses=6, center_x=10, center_y=10)
    village["storage"] = {"food": 20, "wood": 20, "stone": 20}
    world.villages = [village]
    storage = world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    assert storage is not None
    site = building_system.place_building(
        world,
        "house",
        (12, 10),
        village_id=1,
        village_uid=village["village_uid"],
        operational_state="under_construction",
        construction_request={
            "wood_needed": HOUSE_WOOD_COST,
            "wood_reserved": 0,
            "stone_needed": HOUSE_STONE_COST,
            "stone_reserved": 0,
            "food_needed": 0,
            "food_reserved": 0,
        },
        construction_buffer={"wood": 0, "stone": 0, "food": 0},
        construction_progress=0,
        construction_required_work=3,
    )
    assert site is not None
    builder = Agent(x=12, y=10, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    hauler = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    hauler.village_id = 1
    hauler.role = "hauler"
    world.agents = [builder, hauler]

    assert building_system.try_build_house(world, builder) is False
    diag = world.compute_builder_self_supply_snapshot()
    assert int(diag["builder_self_supply_attempt_count"]) == 0


def test_try_build_storage_can_bootstrap_storage_pos_when_missing() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001", tier=1, population=8, houses=4, center_x=12, center_y=12)
    village.pop("storage_pos", None)
    world.villages = [village]
    builder = Agent(x=12, y=12, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"

    assert building_system.try_build_storage(world, builder) is False
    assert isinstance(village.get("storage_pos"), dict)
    assert "x" in village["storage_pos"] and "y" in village["storage_pos"]
    sites = [b for b in world.buildings.values() if b.get("type") == "storage" and b.get("operational_state") == "under_construction"]
    assert len(sites) == 1


def test_serialized_buildings_include_construction_logistics_fields() -> None:
    world, _, builder, _ = _construction_ready_world()
    world.agents = [builder]
    building_system.try_build_house(world, builder)
    payload = serialize_dynamic_world_state(world)
    pending = [b for b in payload["buildings"] if b["type"] == "house" and b["operational_state"] == "under_construction"][0]
    assert "construction_request" in pending
    assert "construction_buffer" in pending
    assert "construction_progress" in pending
    assert "construction_required_work" in pending
    assert "construction_complete_ratio" in pending


def test_storage_surplus_deficit_detection() -> None:
    world, _, _ = _redistribution_ready_world()
    storages = sorted(
        [b for b in world.buildings.values() if b.get("type") == "storage"],
        key=lambda b: b["building_id"],
    )
    source, target = storages[0], storages[1]
    assert building_system.get_storage_surplus(source, "wood") > 0
    assert building_system.get_storage_deficit(target, "wood") > 0


def test_storage_transfer_candidate_selection_is_deterministic() -> None:
    world, village, _ = _redistribution_ready_world()
    first = building_system.find_storage_transfer_candidates(world, village, "wood")
    second = building_system.find_storage_transfer_candidates(world, village, "wood")
    assert first == second
    assert len(first) >= 1


def test_hauler_moves_resource_between_storages() -> None:
    world, village, hauler = _redistribution_ready_world()
    world.agents = [hauler]
    storages = sorted(
        [b for b in world.buildings.values() if b.get("type") == "storage"],
        key=lambda b: b["building_id"],
    )
    source, target = storages[0], storages[1]

    # Step 1: assign transfer and withdraw at source.
    assert building_system.run_hauler_internal_redistribution(world, hauler) is True
    assert hauler.inventory["wood"] > 0
    carried = hauler.inventory["wood"]

    # Step 2: move to target and deposit.
    hauler.x, hauler.y = int(target["x"]), int(target["y"])
    assert building_system.run_hauler_internal_redistribution(world, hauler) is True
    assert hauler.inventory["wood"] == 0
    assert int(target["storage"]["wood"]) >= carried


def test_construction_delivery_priority_over_passive_redistribution() -> None:
    world, village, builder, hauler = _construction_ready_world()
    # add a second storage to enable passive redistribution opportunities
    s2 = world.place_building("storage", 14, 10, village_id=1, village_uid=village["village_uid"])
    assert s2 is not None
    world.buildings[s2["building_id"]]["storage"]["wood"] = 0
    world.buildings[s2["building_id"]]["storage"]["stone"] = 0
    world.agents = [builder, hauler]
    building_system.try_build_house(world, builder)

    # village logistics tick: construction delivery must be selected before passive balancing.
    hauler.update(world)
    assert hauler.delivery_target_building_id is not None


def test_redistribution_is_bounded_and_not_oscillating_in_simple_case() -> None:
    world, village, hauler = _redistribution_ready_world()
    world.agents = [hauler]
    storages = sorted(
        [b for b in world.buildings.values() if b.get("type") == "storage"],
        key=lambda b: b["building_id"],
    )
    source, target = storages[0], storages[1]
    initial_gap = int(source["storage"]["wood"]) - int(target["storage"]["wood"])

    # Run a few deterministic transfer cycles.
    for _ in range(8):
        if getattr(hauler, "transfer_source_storage_id", None):
            sb = world.buildings[hauler.transfer_source_storage_id]
            hauler.x, hauler.y = int(sb["x"]), int(sb["y"])
        assert building_system.run_hauler_internal_redistribution(world, hauler) in {True, False}
        if getattr(hauler, "transfer_target_storage_id", None):
            tb = world.buildings[hauler.transfer_target_storage_id]
            hauler.x, hauler.y = int(tb["x"]), int(tb["y"])
            assert building_system.run_hauler_internal_redistribution(world, hauler) in {True, False}

    final_gap = int(source["storage"]["wood"]) - int(target["storage"]["wood"])
    assert final_gap < initial_gap
    # bounded transfer should not invert into extreme opposite imbalance in this short run
    assert final_gap >= -building_system.STORAGE_REBALANCE_MARGIN


def test_serialized_metrics_include_redistribution_counters() -> None:
    world, village, hauler = _redistribution_ready_world()
    world.agents = [hauler]
    # one full transfer cycle
    assert building_system.run_hauler_internal_redistribution(world, hauler) is True
    target_id = hauler.transfer_target_storage_id
    assert target_id is not None
    target = world.buildings[target_id]
    hauler.x, hauler.y = int(target["x"]), int(target["y"])
    assert building_system.run_hauler_internal_redistribution(world, hauler) is True
    world.update_village_ai()
    payload = serialize_dynamic_world_state(world)
    vm = payload["villages"][0]["metrics"]
    assert "internal_transfers_count" in vm
    assert "redistributed_wood" in vm


def test_transport_service_scoring_matches_distance_gradient() -> None:
    world = _flat_grass_world()
    world.roads = {(10, 10)}
    building = {"x": 10, "y": 10, "footprint": [{"x": 10, "y": 10}]}
    assert building_system.evaluate_building_infrastructure_service(world, building)["transport"] == 1.0
    building["footprint"] = [{"x": 11, "y": 10}]
    assert building_system.evaluate_building_infrastructure_service(world, building)["transport"] == 0.8
    building["footprint"] = [{"x": 12, "y": 10}]
    assert building_system.evaluate_building_infrastructure_service(world, building)["transport"] == 0.6
    building["footprint"] = [{"x": 13, "y": 10}]
    assert building_system.evaluate_building_infrastructure_service(world, building)["transport"] == 0.4
    building["footprint"] = [{"x": 16, "y": 10}]
    assert building_system.evaluate_building_infrastructure_service(world, building)["transport"] == 0.2


def test_logistics_service_scoring_tracks_storage_distance() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001")
    world.villages = [village]
    storage = world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    assert storage is not None

    near = {
        "x": 11,
        "y": 10,
        "footprint": [{"x": 11, "y": 10}],
        "village_id": 1,
        "village_uid": village["village_uid"],
    }
    medium = {
        "x": 14,
        "y": 10,
        "footprint": [{"x": 14, "y": 10}],
        "village_id": 1,
        "village_uid": village["village_uid"],
    }
    far = {
        "x": 25,
        "y": 10,
        "footprint": [{"x": 25, "y": 10}],
        "village_id": 1,
        "village_uid": village["village_uid"],
    }
    near_score = building_system.evaluate_building_infrastructure_service(world, near)["logistics"]
    med_score = building_system.evaluate_building_infrastructure_service(world, medium)["logistics"]
    far_score = building_system.evaluate_building_infrastructure_service(world, far)["logistics"]
    assert near_score == 1.0
    assert med_score == 0.6
    assert far_score == 0.3


def test_efficiency_multiplier_is_bounded_and_deterministic() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001")
    world.villages = [village]
    world.place_building("storage", 10, 10, village_id=1, village_uid=village["village_uid"])
    world.roads = {(10, 9), (10, 10), (10, 11)}
    building = {
        "x": 10,
        "y": 10,
        "footprint": [{"x": 10, "y": 10}],
        "village_id": 1,
        "village_uid": village["village_uid"],
    }
    first = building_system.compute_building_efficiency_multiplier(world, building)
    second = building_system.compute_building_efficiency_multiplier(world, building)
    assert first == second
    assert 0.5 <= first <= 1.5


def test_production_bonus_scales_with_infrastructure_service() -> None:
    village = _village(village_id=1, uid="v-000001", tier=2, population=12, houses=6)

    world_poor = _flat_grass_world()
    world_poor.villages = [dict(village)]
    mine_poor = {
        "building_id": "b-mine-poor",
        "type": "mine",
        "x": 15,
        "y": 15,
        "footprint": [{"x": 15, "y": 15}, {"x": 16, "y": 15}, {"x": 15, "y": 16}, {"x": 16, "y": 16}],
        "village_id": 1,
        "village_uid": village["village_uid"],
        "connected_to_road": False,
        "operational_state": "active",
        "linked_resource_type": "stone",
        "linked_resource_tiles_count": 8,
    }
    world_poor.buildings = {"b-mine-poor": mine_poor}
    miner_poor = Agent(x=15, y=15, brain=None, is_player=False, player_id=None)
    miner_poor.village_id = 1
    miner_poor.role = "miner"
    miner_poor.assigned_building_id = "b-mine-poor"
    world_poor.agents = [miner_poor]

    world_good = _flat_grass_world()
    world_good.villages = [dict(village)]
    mine_good = dict(mine_poor)
    mine_good["building_id"] = "b-mine-good"
    mine_good["connected_to_road"] = True
    world_good.buildings = {"b-mine-good": mine_good}
    world_good.roads = {(15, 14), (15, 15), (16, 15)}
    world_good.place_building("storage", 14, 15, village_id=1, village_uid=village["village_uid"])
    miner_good = Agent(x=15, y=15, brain=None, is_player=False, player_id=None)
    miner_good.village_id = 1
    miner_good.role = "miner"
    miner_good.assigned_building_id = "b-mine-good"
    world_good.agents = [miner_good]

    poor_bonus, _ = building_system.production_bonus_details_for_resource(world_poor, world_poor.villages[0], "stone", (15, 15))
    good_bonus, _ = building_system.production_bonus_details_for_resource(world_good, world_good.villages[0], "stone", (15, 15))
    assert good_bonus > poor_bonus


def test_serialized_buildings_include_service_metrics() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001")
    world.villages = [village]
    world.roads = {(10, 10)}
    mine = world.place_building("mine", 10, 10, village_id=1, village_uid=village["village_uid"])
    if mine is None:
        mine = {
            "building_id": "b-mine-service",
            "type": "mine",
            "category": "production",
            "tier": 2,
            "x": 10,
            "y": 10,
            "footprint": [{"x": 10, "y": 10}],
            "village_id": 1,
            "village_uid": village["village_uid"],
            "connected_to_road": True,
            "operational_state": "active",
            "linked_resource_type": "stone",
            "linked_resource_tiles_count": 3,
        }
        world.buildings[mine["building_id"]] = mine
    payload = serialize_dynamic_world_state(world)
    building_payload = [b for b in payload["buildings"] if b["type"] == "mine"][0]
    service = building_payload["service"]
    assert isinstance(service, dict)
    assert set(service.keys()) == {"transport", "logistics", "efficiency_multiplier"}
    assert 0.0 <= service["transport"] <= 1.0
    assert 0.0 <= service["logistics"] <= 1.0
    assert 0.5 <= service["efficiency_multiplier"] <= 1.5


def test_transport_service_prefers_logistics_corridor_over_road() -> None:
    world = _flat_grass_world()
    village = _village(village_id=1, uid="v-000001")
    world.villages = [village]
    building = {
        "x": 10,
        "y": 10,
        "footprint": [{"x": 10, "y": 10}],
        "village_id": 1,
        "village_uid": village["village_uid"],
    }

    world.set_transport_type(11, 10, "road")
    road_score = building_system.evaluate_building_infrastructure_service(world, building)["transport"]

    world.set_transport_type(11, 10, "logistics_corridor")
    corridor_score = building_system.evaluate_building_infrastructure_service(world, building)["transport"]
    assert corridor_score >= road_score
