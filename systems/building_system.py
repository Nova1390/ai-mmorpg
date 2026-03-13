from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple
import math

from config import HOUSE_WOOD_COST, HOUSE_STONE_COST

if TYPE_CHECKING:
    from world import World
    from agent import Agent


Coord = Tuple[int, int]

STORAGE_WOOD_COST = 4
STORAGE_STONE_COST = 2
STORAGE_BUILDING_CAPACITY = 250
HOUSE_DOMESTIC_FOOD_CAPACITY = 4
STORAGE_REBALANCE_RESERVE = 8
STORAGE_REBALANCE_MARGIN = 3
STORAGE_REBALANCE_TRANSFER_CAP = 2
STORAGE_MATURE_CLUSTER_HOUSES_MIN = 3
STORAGE_MATURE_CLUSTER_POP_MIN = 6
STORAGE_MATURE_FLOW_EVENTS_MIN = 6
STORAGE_MATURE_BUFFER_PRESSURE_MIN = 3
STORAGE_SURPLUS_FOOD_RATE_MIN = 0.04
STORAGE_SURPLUS_RESOURCE_RATE_MIN = 0.03
POLICY_BUILD_COOLDOWN_TICKS = 60
POLICY_MAX_ATTEMPTS_PER_WINDOW = 2
CONSTRUCTION_WORK_RANGE = 1
CONSTRUCTION_WORK_PER_TICK = 1
CONSTRUCTION_WAIT_SIGNAL_TICKS = 24
DELIVERY_COMMIT_TICKS = 8
BUILDER_SELF_SUPPLY_MAX_PER_RESOURCE = 1
BUILDER_SELF_SUPPLY_MAX_SOURCE_DISTANCE = 3
BUILDER_SELF_SUPPLY_HUNGER_MIN = 16
BUILDER_SELF_SUPPLY_FRAGILE_POP_MAX = 12
CONSTRUCTION_SITE_STALE_TIMEOUT_TICKS = 360
SPECIALIZATION_ROAD_SIGNAL_RADIUS = 6
SPECIALIZATION_TIER2_POPULATION_MIN = 9
SPECIALIZATION_TIER2_HOUSES_MIN = 3
CONSTRUCTION_REQUIRED_WORK_BY_TYPE = {
    "house": 4,
    "storage": 6,
}
SPECIALIZATION_BUILDING_TYPES = {"mine", "lumberyard"}
SPECIALIZATION_PIPELINE_STAGES = (
    "readiness_possible_count",
    "selected_by_policy_count",
    "placement_candidate_found_count",
    "build_attempt_count",
    "built_active_count",
    "staffed_count",
    "used_for_production_count",
)
SPECIALIZATION_READINESS_BREAKDOWN_REASONS = (
    "tier_inputs_population_low",
    "tier_inputs_houses_low",
    "tier_inputs_farms_low",
    "tier_inputs_storage_missing",
    "tier_inputs_roads_missing",
)
SPECIALIZATION_REQUIREMENT_BREAKDOWN_REASONS = (
    "requirement_population_min_failed",
    "requirement_houses_min_failed",
    "requirement_farms_min_failed",
    "requirement_storage_required_failed",
    "requirement_roads_required_failed",
    "requirement_resource_context_failed",
)


def _default_specialization_stage_counts() -> Dict[str, int]:
    return {key: 0 for key in SPECIALIZATION_PIPELINE_STAGES}


def _default_specialization_diag_entry() -> Dict[str, Any]:
    return {
        **_default_specialization_stage_counts(),
        "blocker_reasons": {},
        "readiness_breakdown": {},
        "requirement_breakdown": {},
    }


def _default_specialization_diagnostics() -> Dict[str, Any]:
    return {
        "mine": _default_specialization_diag_entry(),
        "lumberyard": _default_specialization_diag_entry(),
        "by_village": {},
    }


def get_or_init_specialization_diagnostics(world: "World") -> Dict[str, Any]:
    payload = getattr(world, "specialization_diagnostics", None)
    if not isinstance(payload, dict):
        payload = _default_specialization_diagnostics()
        world.specialization_diagnostics = payload
        return payload
    for btype in ("mine", "lumberyard"):
        entry = payload.get(btype)
        if not isinstance(entry, dict):
            entry = _default_specialization_diag_entry()
            payload[btype] = entry
        for key in SPECIALIZATION_PIPELINE_STAGES:
            entry[key] = int(entry.get(key, 0))
        blockers = entry.get("blocker_reasons")
        if not isinstance(blockers, dict):
            entry["blocker_reasons"] = {}
        readiness_breakdown = entry.get("readiness_breakdown")
        if not isinstance(readiness_breakdown, dict):
            entry["readiness_breakdown"] = {}
        requirement_breakdown = entry.get("requirement_breakdown")
        if not isinstance(requirement_breakdown, dict):
            entry["requirement_breakdown"] = {}
    by_village = payload.get("by_village")
    if not isinstance(by_village, dict):
        payload["by_village"] = {}
    return payload


def _resolve_village_uid(world: "World", village: Optional[Dict[str, Any]]) -> str:
    if not isinstance(village, dict):
        return ""
    vuid = village.get("village_uid")
    if vuid is not None:
        return str(vuid)
    vid = village.get("id")
    if isinstance(vid, int) and hasattr(world, "resolve_village_uid"):
        resolved = world.resolve_village_uid(vid)
        if resolved is not None:
            return str(resolved)
    return ""


def _record_housing_stage(
    world: "World",
    stage: str,
    *,
    village_uid: Optional[str] = None,
    building_id: Optional[str] = None,
) -> None:
    if hasattr(world, "record_housing_construction_stage"):
        world.record_housing_construction_stage(
            stage,
            village_uid=village_uid,
            building_id=building_id,
        )


def _record_housing_failure(
    world: "World",
    reason: str,
    *,
    village_uid: Optional[str] = None,
) -> None:
    if hasattr(world, "record_housing_construction_failure"):
        world.record_housing_construction_failure(reason, village_uid=village_uid)


def _record_housing_worker(
    world: "World",
    event: str,
    *,
    village_uid: Optional[str] = None,
) -> None:
    if hasattr(world, "record_housing_worker_participation"):
        world.record_housing_worker_participation(event, village_uid=village_uid)


def _record_housing_siting_stage(
    world: "World",
    stage: str,
    *,
    village_uid: Optional[str] = None,
) -> None:
    if hasattr(world, "record_housing_siting_stage"):
        world.record_housing_siting_stage(stage, village_uid=village_uid)


def _record_housing_siting_rejection(
    world: "World",
    reason: str,
    *,
    village_uid: Optional[str] = None,
) -> None:
    if hasattr(world, "record_housing_siting_rejection_reason"):
        world.record_housing_siting_rejection_reason(reason, village_uid=village_uid)


def _record_housing_path(
    world: "World",
    key: str,
    *,
    village_uid: Optional[str] = None,
) -> None:
    if hasattr(world, "record_housing_path_coherence"):
        world.record_housing_path_coherence(key, village_uid=village_uid)


def _get_or_init_village_specialization_entry(world: "World", village_uid: str, building_type: str) -> Dict[str, Any]:
    payload = get_or_init_specialization_diagnostics(world)
    by_village = payload.setdefault("by_village", {})
    village_entry = by_village.get(village_uid)
    if not isinstance(village_entry, dict):
        village_entry = {}
        by_village[village_uid] = village_entry
    b_entry = village_entry.get(building_type)
    if not isinstance(b_entry, dict):
        b_entry = _default_specialization_diag_entry()
        village_entry[building_type] = b_entry
    for key in SPECIALIZATION_PIPELINE_STAGES:
        b_entry[key] = int(b_entry.get(key, 0))
    if not isinstance(b_entry.get("blocker_reasons"), dict):
        b_entry["blocker_reasons"] = {}
    if not isinstance(b_entry.get("readiness_breakdown"), dict):
        b_entry["readiness_breakdown"] = {}
    if not isinstance(b_entry.get("requirement_breakdown"), dict):
        b_entry["requirement_breakdown"] = {}
    return b_entry


def record_specialization_stage(
    world: "World",
    building_type: str,
    stage_key: str,
    *,
    village: Optional[Dict[str, Any]] = None,
) -> None:
    btype = str(building_type)
    if btype not in SPECIALIZATION_BUILDING_TYPES:
        return
    if stage_key not in SPECIALIZATION_PIPELINE_STAGES:
        return
    payload = get_or_init_specialization_diagnostics(world)
    entry = payload.get(btype)
    if not isinstance(entry, dict):
        entry = _default_specialization_diag_entry()
        payload[btype] = entry
    entry[stage_key] = int(entry.get(stage_key, 0)) + 1
    village_uid = _resolve_village_uid(world, village)
    if village_uid:
        v_entry = _get_or_init_village_specialization_entry(world, village_uid, btype)
        v_entry[stage_key] = int(v_entry.get(stage_key, 0)) + 1


def record_specialization_blocker(
    world: "World",
    building_type: str,
    reason: str,
    *,
    village: Optional[Dict[str, Any]] = None,
) -> None:
    btype = str(building_type)
    if btype not in SPECIALIZATION_BUILDING_TYPES:
        return
    key = str(reason).strip().lower() or "unknown"
    payload = get_or_init_specialization_diagnostics(world)
    entry = payload.get(btype)
    if not isinstance(entry, dict):
        entry = _default_specialization_diag_entry()
        payload[btype] = entry
    blockers = entry.setdefault("blocker_reasons", {})
    blockers[key] = int(blockers.get(key, 0)) + 1
    village_uid = _resolve_village_uid(world, village)
    if village_uid:
        v_entry = _get_or_init_village_specialization_entry(world, village_uid, btype)
        v_blockers = v_entry.setdefault("blocker_reasons", {})
        v_blockers[key] = int(v_blockers.get(key, 0)) + 1


def record_specialization_readiness_breakdown(
    world: "World",
    building_type: str,
    reason: str,
    *,
    village: Optional[Dict[str, Any]] = None,
) -> None:
    btype = str(building_type)
    key = str(reason).strip().lower()
    if btype not in SPECIALIZATION_BUILDING_TYPES or key not in SPECIALIZATION_READINESS_BREAKDOWN_REASONS:
        return
    payload = get_or_init_specialization_diagnostics(world)
    entry = payload.get(btype)
    if not isinstance(entry, dict):
        entry = _default_specialization_diag_entry()
        payload[btype] = entry
    breakdown = entry.setdefault("readiness_breakdown", {})
    breakdown[key] = int(breakdown.get(key, 0)) + 1
    village_uid = _resolve_village_uid(world, village)
    if village_uid:
        v_entry = _get_or_init_village_specialization_entry(world, village_uid, btype)
        v_breakdown = v_entry.setdefault("readiness_breakdown", {})
        v_breakdown[key] = int(v_breakdown.get(key, 0)) + 1


def record_specialization_requirement_breakdown(
    world: "World",
    building_type: str,
    reason: str,
    *,
    village: Optional[Dict[str, Any]] = None,
) -> None:
    btype = str(building_type)
    key = str(reason).strip().lower()
    if btype not in SPECIALIZATION_BUILDING_TYPES or key not in SPECIALIZATION_REQUIREMENT_BREAKDOWN_REASONS:
        return
    payload = get_or_init_specialization_diagnostics(world)
    entry = payload.get(btype)
    if not isinstance(entry, dict):
        entry = _default_specialization_diag_entry()
        payload[btype] = entry
    breakdown = entry.setdefault("requirement_breakdown", {})
    breakdown[key] = int(breakdown.get(key, 0)) + 1
    village_uid = _resolve_village_uid(world, village)
    if village_uid:
        v_entry = _get_or_init_village_specialization_entry(world, village_uid, btype)
        v_breakdown = v_entry.setdefault("requirement_breakdown", {})
        v_breakdown[key] = int(v_breakdown.get(key, 0)) + 1

BUILDING_CATEGORIES = {
    "residential",
    "food_storage",
    "production",
    "governance",
    "infrastructure",
    "security",
    "knowledge",
    "health",
    "culture",
    "commerce",
}

INFRASTRUCTURE_SYSTEMS = {
    "transport",
    "water",
    "energy",
    "logistics",
    "communication",
    "environment",
}

INFRASTRUCTURE_CATALOG: Dict[str, Dict[str, Any]] = {
    "path": {
        "type": "path",
        "system": "transport",
        "tier": 0,
        "network_type": "tile_network",
        "connects_buildings": True,
        "supports_logistics": True,
        "description": "Low-grade transport connector made by repeated local movement.",
        "movement_modifier": 0.8,
        "service_radius": 0,
        "capacity": None,
        "requires_terrain": [],
        "crosses_blocking_terrain": False,
        "enables_building_categories": ["residential", "food_storage"],
        "benefits_building_categories": ["residential", "production", "food_storage"],
    },
    "road": {
        "type": "road",
        "system": "transport",
        "tier": 1,
        "network_type": "tile_network",
        "connects_buildings": True,
        "supports_logistics": True,
        "description": "Primary transport network used for village movement and logistics.",
        "movement_modifier": 0.5,
        "service_radius": 0,
        "capacity": None,
        "requires_terrain": [],
        "crosses_blocking_terrain": False,
        "enables_building_categories": ["food_storage", "production", "infrastructure"],
        "benefits_building_categories": ["residential", "food_storage", "production", "infrastructure"],
    },
    "logistics_corridor": {
        "type": "logistics_corridor",
        "system": "transport",
        "tier": 2,
        "network_type": "tile_network",
        "connects_buildings": True,
        "supports_logistics": True,
        "description": "High-throughput transport spine for dense logistics movement.",
        "movement_modifier": 0.35,
        "service_radius": 0,
        "capacity": None,
        "requires_terrain": [],
        "crosses_blocking_terrain": False,
        "enables_building_categories": ["food_storage", "production", "infrastructure"],
        "benefits_building_categories": ["food_storage", "production", "infrastructure", "commerce"],
    },
    "bridge": {
        "type": "bridge",
        "system": "transport",
        "tier": 2,
        "network_type": "crossing_link",
        "connects_buildings": True,
        "supports_logistics": True,
        "description": "Placeholder transport crossing for blocked terrain segments.",
        "movement_modifier": 0.6,
        "service_radius": 0,
        "capacity": None,
        "requires_terrain": ["water"],
        "crosses_blocking_terrain": True,
        "enables_building_categories": ["production", "infrastructure"],
        "benefits_building_categories": ["production", "food_storage"],
    },
    "tunnel": {
        "type": "tunnel",
        "system": "transport",
        "tier": 2,
        "network_type": "crossing_link",
        "connects_buildings": True,
        "supports_logistics": True,
        "description": "Placeholder underground crossing for impassable terrain segments.",
        "movement_modifier": 0.45,
        "service_radius": 0,
        "capacity": None,
        "requires_terrain": ["X"],
        "crosses_blocking_terrain": True,
        "enables_building_categories": ["production", "infrastructure"],
        "benefits_building_categories": ["production", "infrastructure", "food_storage"],
    },
    "storage_link": {
        "type": "storage_link",
        "system": "logistics",
        "tier": 1,
        "network_type": "service_link",
        "connects_buildings": True,
        "supports_logistics": True,
        "description": "Conceptual logistics connector between storage hubs and work sites.",
        "movement_modifier": None,
        "service_radius": 8,
        "capacity": None,
        "requires_terrain": [],
        "crosses_blocking_terrain": False,
        "enables_building_categories": ["food_storage", "production"],
        "benefits_building_categories": ["food_storage", "production", "residential"],
    },
    "haul_route": {
        "type": "haul_route",
        "system": "logistics",
        "tier": 1,
        "network_type": "route",
        "connects_buildings": True,
        "supports_logistics": True,
        "description": "Conceptual hauler route used for deterministic delivery targeting.",
        "movement_modifier": None,
        "service_radius": 12,
        "capacity": None,
        "requires_terrain": [],
        "crosses_blocking_terrain": False,
        "enables_building_categories": ["food_storage", "production", "infrastructure"],
        "benefits_building_categories": ["production", "food_storage"],
    },
    "well_network": {
        "type": "well_network",
        "system": "water",
        "tier": 1,
        "network_type": "service_grid",
        "connects_buildings": True,
        "supports_logistics": False,
        "description": "Placeholder water service network for future farming/health systems.",
        "movement_modifier": None,
        "service_radius": 6,
        "capacity": None,
        "requires_terrain": [],
        "crosses_blocking_terrain": False,
        "enables_building_categories": ["health", "production"],
        "benefits_building_categories": ["production", "health"],
    },
    "power_line": {
        "type": "power_line",
        "system": "energy",
        "tier": 2,
        "network_type": "service_grid",
        "connects_buildings": True,
        "supports_logistics": False,
        "description": "Placeholder energy distribution network for future industrial tiers.",
        "movement_modifier": None,
        "service_radius": 10,
        "capacity": None,
        "requires_terrain": [],
        "crosses_blocking_terrain": False,
        "enables_building_categories": ["production", "knowledge", "commerce"],
        "benefits_building_categories": ["production", "knowledge", "commerce"],
    },
    "messenger_route": {
        "type": "messenger_route",
        "system": "communication",
        "tier": 1,
        "network_type": "route",
        "connects_buildings": True,
        "supports_logistics": False,
        "description": "Placeholder communication route for governance/coordination systems.",
        "movement_modifier": None,
        "service_radius": 12,
        "capacity": None,
        "requires_terrain": [],
        "crosses_blocking_terrain": False,
        "enables_building_categories": ["governance", "knowledge", "security"],
        "benefits_building_categories": ["governance", "knowledge", "security"],
    },
    "drainage": {
        "type": "drainage",
        "system": "environment",
        "tier": 1,
        "network_type": "service_grid",
        "connects_buildings": False,
        "supports_logistics": False,
        "description": "Placeholder environmental control network for terrain resilience.",
        "movement_modifier": None,
        "service_radius": 5,
        "capacity": None,
        "requires_terrain": [],
        "crosses_blocking_terrain": False,
        "enables_building_categories": ["health", "residential", "production"],
        "benefits_building_categories": ["health", "residential", "production"],
    },
}


BUILDING_CATALOG: Dict[str, Dict[str, Any]] = {
    "house": {
        "type": "house",
        "category": "residential",
        "tier": 1,
        "min_tier": 1,
        "footprint_size": (1, 1),
        "requires_road": False,
        "worker_capacity": 0,
        "description": "Basic dwelling for population growth.",
        "economic_role": "housing",
        "requires_infrastructure": [],
        "benefits_from_infrastructure": ["path", "road", "messenger_route"],
        "hard_requirements": {"population_min": 0},
        "unlock_signals": ["population_pressure_high"],
        "unlock_conditions": {"population_min": 0},
        "service_effects": {},
    },
    "storage": {
        "type": "storage",
        "category": "food_storage",
        "tier": 1,
        "min_tier": 1,
        "footprint_size": (2, 2),
        "requires_road": False,
        "worker_capacity": 0,
        "description": "Village storage hub for food, wood, and stone.",
        "economic_role": "logistics",
        "requires_infrastructure": [],
        "benefits_from_infrastructure": ["road", "storage_link", "haul_route"],
        "hard_requirements": {"population_min": 4, "houses_min": 1},
        "unlock_signals": ["storage_pressure_high", "food_surplus_high"],
        "unlock_conditions": {"population_min": 4},
        "service_effects": {"storage_bonus": True},
    },
    # Farm tiles are still serialized via farm_plots/farms, but the building model
    # reserves a typed slot for future settlement-level farm support structures.
    "farm_plot": {
        "type": "farm_plot",
        "category": "production",
        "tier": 1,
        "min_tier": 1,
        "footprint_size": (1, 1),
        "requires_road": False,
        "worker_capacity": 1,
        "description": "Cultivated plot for local food production.",
        "economic_role": "food_production",
        "requires_infrastructure": [],
        "benefits_from_infrastructure": ["path", "well_network", "drainage"],
        "hard_requirements": {"population_min": 2, "houses_min": 1},
        "unlock_signals": ["food_surplus_high", "farms_present"],
        "unlock_conditions": {"population_min": 2},
        "service_effects": {},
    },
    "mine": {
        "type": "mine",
        "category": "production",
        "tier": 2,
        "min_tier": 2,
        "footprint_size": (2, 2),
        "requires_road": True,
        "resource_type": "stone",
        "resource_context_required": True,
        "resource_context_radius": 6,
        "resource_context_min_tiles": 3,
        "worker_capacity": 4,
        "description": "Placeholder extraction site for future ore/stone systems.",
        "economic_role": "resource_extraction",
        "requires_infrastructure": ["road"],
        "benefits_from_infrastructure": ["road", "storage_link", "haul_route", "power_line"],
        "hard_requirements": {
            "population_min": 9,
            "houses_min": 3,
            "roads_required": True,
            "storage_required": True,
            "farms_min": 1,
        },
        "unlock_signals": ["stone_demand_high", "roads_present"],
        "unlock_conditions": {"population_min": 9, "food_surplus": True},
        "service_effects": {},
    },
    "lumberyard": {
        "type": "lumberyard",
        "category": "production",
        "tier": 2,
        "min_tier": 2,
        "footprint_size": (2, 2),
        "requires_road": True,
        "resource_type": "wood",
        "resource_context_required": True,
        "resource_context_radius": 6,
        "resource_context_min_tiles": 4,
        "worker_capacity": 3,
        "description": "Placeholder wood processing site for future production chains.",
        "economic_role": "resource_processing",
        "requires_infrastructure": ["road"],
        "benefits_from_infrastructure": ["road", "storage_link", "haul_route", "power_line"],
        "hard_requirements": {
            "population_min": 7,
            "houses_min": 2,
            "roads_required": True,
            "storage_required": True,
            "farms_min": 1,
        },
        "unlock_signals": ["wood_demand_high", "roads_present"],
        "unlock_conditions": {"population_min": 7, "food_surplus": True},
        "service_effects": {},
    },
}


def _coord_key(coord: Coord) -> Tuple[int, int]:
    return (coord[1], coord[0])


def get_building_metadata(building_type: str) -> Optional[Dict[str, Any]]:
    metadata = BUILDING_CATALOG.get(building_type)
    if metadata is None:
        return None
    return dict(metadata)


def get_infrastructure_metadata(infrastructure_type: str) -> Optional[Dict[str, Any]]:
    metadata = INFRASTRUCTURE_CATALOG.get(infrastructure_type)
    if metadata is None:
        return None
    return dict(metadata)


def _village_storage(world: "World", village: Dict[str, Any]) -> Dict[str, Any]:
    return get_village_storage_totals(world, village)


def _distance(a: Coord, b: Coord) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _distance_to_nearest(pos: Coord, points: List[Coord]) -> int:
    if not points:
        return 9999
    return min(_distance(pos, point) for point in points)


def _distance_to_nearest_coords(origins: List[Coord], points: List[Coord]) -> int:
    if not origins or not points:
        return 9999
    return min(_distance(origin, p) for origin in origins for p in points)


def _building_footprint_coords(building: Dict[str, Any]) -> List[Coord]:
    footprint = building.get("footprint", [])
    coords: List[Coord] = []
    if isinstance(footprint, list):
        for tile in footprint:
            if isinstance(tile, dict) and "x" in tile and "y" in tile:
                coords.append((int(tile["x"]), int(tile["y"])))
    if not coords:
        coords = [(int(building.get("x", 0)), int(building.get("y", 0)))]
    return sorted(coords, key=_coord_key)


def _village_farm_zone(village: Dict[str, Any]) -> Coord:
    farm_zone = village.get("farm_zone_center")
    if isinstance(farm_zone, dict):
        return (int(farm_zone.get("x", 0)), int(farm_zone.get("y", 0)))
    return _village_center(village)


def _nearest_storage_anchor(world: "World", village: Dict[str, Any]) -> Coord:
    village_id = _village_id(village)
    village_uid = _village_uid(village)
    storage_anchors: List[Coord] = []
    for building in getattr(world, "buildings", {}).values():
        if building.get("type") != "storage":
            continue
        if village_id is not None and building.get("village_id") == village_id:
            storage_anchors.append((int(building.get("x", 0)), int(building.get("y", 0))))
            continue
        if village_uid is not None and building.get("village_uid") == village_uid:
            storage_anchors.append((int(building.get("x", 0)), int(building.get("y", 0))))
    if storage_anchors:
        storage_anchors.sort(key=_coord_key)
        return storage_anchors[0]

    storage_pos = village.get("storage_pos")
    if isinstance(storage_pos, dict):
        return (int(storage_pos.get("x", 0)), int(storage_pos.get("y", 0)))
    return _village_center(village)


def _road_points(world: "World") -> List[Coord]:
    return sorted(getattr(world, "roads", set()), key=_coord_key)


def _transport_tiles(world: "World") -> List[Tuple[Coord, str]]:
    if hasattr(world, "get_transport_tiles"):
        tiles = world.get_transport_tiles()
        if isinstance(tiles, dict):
            return sorted(
                [((int(x), int(y)), str(t)) for (x, y), t in tiles.items()],
                key=lambda item: _coord_key(item[0]),
            )
    return sorted([((x, y), "road") for x, y in getattr(world, "roads", set())], key=lambda item: _coord_key(item[0]))


def evaluate_building_infrastructure_service(world: "World", building: Dict[str, Any]) -> Dict[str, float]:
    footprint = _building_footprint_coords(building)
    transport_tiles = _transport_tiles(world)
    road_points = [coord for coord, t in transport_tiles if t in {"road", "logistics_corridor", "bridge", "tunnel"}]

    def _distance_score(distance: int) -> float:
        if distance <= 0:
            return 1.0
        if distance == 1:
            return 0.8
        if distance == 2:
            return 0.6
        if distance == 3:
            return 0.4
        return 0.2

    type_weight = {
        "path": 0.9,
        "road": 1.0,
        "logistics_corridor": 1.15,
        "bridge": 1.0,
        "tunnel": 1.0,
    }
    if transport_tiles:
        weighted_scores: List[float] = []
        for t in sorted(type_weight.keys()):
            points = [coord for coord, tt in transport_tiles if tt == t]
            if not points:
                continue
            d = _distance_to_nearest_coords(footprint, points)
            weighted_scores.append(min(1.0, _distance_score(d) * type_weight[t]))
        transport_score = max(weighted_scores) if weighted_scores else 0.2
    else:
        transport_score = 0.2

    village: Optional[Dict[str, Any]] = None
    village_id = building.get("village_id")
    villages = getattr(world, "villages", [])
    if isinstance(village_id, int):
        if hasattr(world, "get_village_by_id"):
            village = world.get_village_by_id(village_id)
        if village is None:
            village = next((v for v in villages if v.get("id") == village_id), None)
    elif building.get("village_uid") is not None:
        village = next((v for v in villages if v.get("village_uid") == building.get("village_uid")), None)
    storage_points: List[Coord] = []
    for storage in _iter_village_storage_buildings(world, village):
        storage_points.append((int(storage.get("x", 0)), int(storage.get("y", 0))))
    storage_points = sorted(storage_points, key=_coord_key)
    logistics_distance = _distance_to_nearest_coords(footprint, storage_points)
    if logistics_distance <= 1:
        logistics_score = 1.0
    elif logistics_distance <= 4:
        logistics_score = 0.6
    else:
        logistics_score = 0.3

    # Optional lightweight heuristic: if both building and nearest storage are road-adjacent,
    # logistics service gets a small deterministic boost.
    if storage_points:
        nearest_storage = min(
            storage_points,
            key=lambda p: (_distance_to_nearest_coords(footprint, [p]), _coord_key(p)),
        )
        building_road_adj = _distance_to_nearest_coords(footprint, road_points) <= 1
        storage_road_adj = _distance_to_nearest_coords([nearest_storage], road_points) <= 1
        if building_road_adj and storage_road_adj:
            logistics_score = min(1.0, logistics_score + 0.1)

    return {
        "transport": float(round(transport_score, 3)),
        "logistics": float(round(logistics_score, 3)),
    }


def compute_building_efficiency_multiplier(world: "World", building: Dict[str, Any]) -> float:
    service = evaluate_building_infrastructure_service(world, building)
    transport = float(service.get("transport", 0.0))
    logistics = float(service.get("logistics", 0.0))
    # Center around neutral service=0.5 per dimension:
    # low service degrades below 1.0, high service improves above 1.0.
    efficiency = 1.0 + (transport - 0.5) * 0.5 + (logistics - 0.5) * 0.5
    efficiency = max(0.5, min(1.5, efficiency))
    return float(round(efficiency, 3))


def _village_center(village: Dict[str, Any]) -> Coord:
    center = village.get("center")
    if isinstance(center, dict):
        return (int(center.get("x", 0)), int(center.get("y", 0)))
    return (0, 0)


def _village_id(village: Dict[str, Any]) -> Optional[int]:
    value = village.get("id")
    return int(value) if isinstance(value, int) else None


def _village_uid(village: Dict[str, Any]) -> Optional[str]:
    value = village.get("village_uid")
    if value is None:
        return None
    return str(value)


def _empty_resource_bucket() -> Dict[str, int]:
    return {"food": 0, "wood": 0, "stone": 0}


def _ensure_storage_state(building: Dict[str, Any]) -> Dict[str, int]:
    storage = building.get("storage")
    if not isinstance(storage, dict):
        storage = _empty_resource_bucket()
        building["storage"] = storage
    for key in ("food", "wood", "stone"):
        storage[key] = int(storage.get(key, 0))
    return storage


def _iter_village_storage_buildings(world: "World", village: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if village is None:
        return []
    village_id = _village_id(village)
    village_uid = _village_uid(village)
    result: List[Dict[str, Any]] = []
    for b in getattr(world, "buildings", {}).values():
        if b.get("type") != "storage":
            continue
        if village_id is not None and b.get("village_id") == village_id:
            result.append(b)
            continue
        if village_uid is not None and b.get("village_uid") == village_uid:
            result.append(b)
    result.sort(key=lambda b: str(b.get("building_id", "")))
    return result


def _sync_village_storage_cache(world: "World", village: Optional[Dict[str, Any]]) -> Dict[str, int]:
    if village is None:
        return _empty_resource_bucket()
    storage_buildings = _iter_village_storage_buildings(world, village)
    if not storage_buildings:
        legacy = village.get("storage", {})
        if isinstance(legacy, dict):
            normalized = {
                "food": int(legacy.get("food", 0)),
                "wood": int(legacy.get("wood", 0)),
                "stone": int(legacy.get("stone", 0)),
            }
            village["storage"] = normalized
            return normalized
        village["storage"] = _empty_resource_bucket()
        return village["storage"]
    totals = _empty_resource_bucket()
    for b in storage_buildings:
        s = _ensure_storage_state(b)
        totals["food"] += int(s.get("food", 0))
        totals["wood"] += int(s.get("wood", 0))
        totals["stone"] += int(s.get("stone", 0))
    village["storage"] = totals
    return totals


def get_village_storage_totals(world: "World", village: Optional[Dict[str, Any]]) -> Dict[str, int]:
    return _sync_village_storage_cache(world, village)


def _storage_load(building: Dict[str, Any]) -> int:
    s = _ensure_storage_state(building)
    return int(s.get("food", 0)) + int(s.get("wood", 0)) + int(s.get("stone", 0))


def get_storage_surplus(building: Dict[str, Any], resource_type: str) -> int:
    if str(building.get("type", "")) != "storage":
        return 0
    r = str(resource_type)
    if r not in {"food", "wood", "stone"}:
        return 0
    s = _ensure_storage_state(building)
    reserve = min(int(building.get("storage_capacity", STORAGE_BUILDING_CAPACITY)), STORAGE_REBALANCE_RESERVE)
    return max(0, int(s.get(r, 0)) - reserve)


def get_storage_deficit(building: Dict[str, Any], resource_type: str) -> int:
    if str(building.get("type", "")) != "storage":
        return 0
    r = str(resource_type)
    if r not in {"food", "wood", "stone"}:
        return 0
    s = _ensure_storage_state(building)
    reserve = min(int(building.get("storage_capacity", STORAGE_BUILDING_CAPACITY)), STORAGE_REBALANCE_RESERVE)
    return max(0, reserve - int(s.get(r, 0)))


def _storage_by_id(world: "World", building_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if building_id is None:
        return None
    b = getattr(world, "buildings", {}).get(str(building_id))
    if not isinstance(b, dict):
        return None
    if str(b.get("type", "")) != "storage":
        return None
    return b


def find_storage_transfer_candidates(
    world: "World",
    village: Optional[Dict[str, Any]],
    resource_type: str,
) -> List[Tuple[str, str, int]]:
    if village is None:
        return []
    r = str(resource_type)
    if r not in {"food", "wood", "stone"}:
        return []
    storages = _iter_village_storage_buildings(world, village)
    if len(storages) < 2:
        return []
    storages = sorted(storages, key=lambda b: str(b.get("building_id", "")))
    total = sum(int(_ensure_storage_state(b).get(r, 0)) for b in storages)
    avg = total // len(storages)
    high = avg + STORAGE_REBALANCE_MARGIN
    low = max(0, avg - STORAGE_REBALANCE_MARGIN)
    sources = []
    targets = []
    for b in storages:
        bid = str(b.get("building_id", ""))
        amt = int(_ensure_storage_state(b).get(r, 0))
        src_surplus = max(0, amt - high)
        tgt_deficit = max(0, low - amt)
        if src_surplus > 0:
            sources.append((bid, src_surplus, int(b.get("x", 0)), int(b.get("y", 0))))
        if tgt_deficit > 0:
            targets.append((bid, tgt_deficit, int(b.get("x", 0)), int(b.get("y", 0))))
    if not sources or not targets:
        return []
    candidates: List[Tuple[str, str, int]] = []
    for sbid, ssur, sx, sy in sources:
        for tbid, tdef, tx, ty in targets:
            if sbid == tbid:
                continue
            qty = min(ssur, tdef, STORAGE_REBALANCE_TRANSFER_CAP)
            if qty <= 0:
                continue
            candidates.append((sbid, tbid, int(qty)))
    candidates.sort(key=lambda c: (c[0], c[1], c[2]))
    return candidates


def _clear_internal_transfer(agent: "Agent") -> None:
    if hasattr(agent, "transfer_source_storage_id"):
        agent.transfer_source_storage_id = None
    if hasattr(agent, "transfer_target_storage_id"):
        agent.transfer_target_storage_id = None
    if hasattr(agent, "transfer_resource_type"):
        agent.transfer_resource_type = None
    if hasattr(agent, "transfer_amount"):
        agent.transfer_amount = 0


def has_active_internal_transfer(agent: "Agent") -> bool:
    return (
        bool(getattr(agent, "transfer_source_storage_id", None))
        and bool(getattr(agent, "transfer_target_storage_id", None))
        and str(getattr(agent, "transfer_resource_type", "")) in {"food", "wood", "stone"}
        and int(getattr(agent, "transfer_amount", 0) or 0) > 0
    )


def _nearest_storage_for_agent(world: "World", agent: "Agent", village: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    storages = _iter_village_storage_buildings(world, village)
    if not storages:
        return None
    storages.sort(
        key=lambda b: (
            _distance((agent.x, agent.y), (int(b.get("x", 0)), int(b.get("y", 0)))),
            str(b.get("building_id", "")),
        )
    )
    return storages[0]


def _nearest_storage_with_resource_for_agent(
    world: "World",
    agent: "Agent",
    village: Optional[Dict[str, Any]],
    resource_type: str,
) -> Optional[Dict[str, Any]]:
    r = str(resource_type)
    storages = _iter_village_storage_buildings(world, village)
    if not storages:
        return None
    candidates = [b for b in storages if int(_ensure_storage_state(b).get(r, 0)) > 0]
    if not candidates:
        return None
    candidates.sort(
        key=lambda b: (
            _distance((agent.x, agent.y), (int(b.get("x", 0)), int(b.get("y", 0)))),
            -int(_ensure_storage_state(b).get(r, 0)),
            str(b.get("building_id", "")),
        )
    )
    return candidates[0]


def deposit_agent_inventory_to_storage(world: "World", agent: "Agent") -> bool:
    if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_attempt"):
        world.record_task_completion_attempt(agent, "deposit_to_storage")
    village = world.get_village_by_id(getattr(agent, "village_id", None))
    storage_building = _nearest_storage_for_agent(world, agent, village)
    if storage_building is None:
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "deposit_to_storage", "no_target_storage")
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "hauler", "no_storage_available")
        return False

    sx = int(storage_building.get("x", 0))
    sy = int(storage_building.get("y", 0))
    if _distance((agent.x, agent.y), (sx, sy)) > 1:
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "deposit_to_storage", "target_not_in_range")
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "hauler", "no_target_found")
        return False

    storage = _ensure_storage_state(storage_building)
    capacity = int(storage_building.get("storage_capacity", STORAGE_BUILDING_CAPACITY))
    moved = False
    moved_materials = 0
    moved_wood_or_stone = 0
    for key in ("food", "wood", "stone"):
        have = int(agent.inventory.get(key, 0))
        if have <= 0:
            continue
        free = max(0, capacity - _storage_load(storage_building))
        if free <= 0:
            break
        qty = min(have, free)
        if qty <= 0:
            continue
        storage[key] = int(storage.get(key, 0)) + qty
        agent.inventory[key] = have - qty
        moved = True
        moved_materials += int(qty)
        if key in {"wood", "stone"}:
            moved_wood_or_stone += int(qty)

    if moved:
        _sync_village_storage_cache(world, village)
        if (
            moved_wood_or_stone > 0
            and hasattr(world, "has_active_construction_for_agent")
            and bool(world.has_active_construction_for_agent(agent))
            and hasattr(world, "record_settlement_progression_metric")
        ):
            world.record_settlement_progression_metric("construction_material_delivery_drift_events", int(moved_wood_or_stone))
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_met"):
            world.record_task_completion_preconditions_met(agent, "deposit_to_storage")
            world.record_task_completion_productive(agent, "deposit_to_storage")
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_productive_action"):
            world.record_workforce_productive_action(agent, "hauler", "deposit_to_storage")
    elif str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
        world.record_workforce_block_reason(agent, "hauler", "no_materials_available")
        if hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "deposit_to_storage", "inventory_empty")
    return moved


def withdraw_build_materials_from_storage(
    world: "World",
    agent: "Agent",
    *,
    wood_need: int,
    stone_need: int,
) -> bool:
    village = world.get_village_by_id(getattr(agent, "village_id", None))
    storage_building = _nearest_storage_for_agent(world, agent, village)
    if storage_building is None:
        return False
    sx = int(storage_building.get("x", 0))
    sy = int(storage_building.get("y", 0))
    if _distance((agent.x, agent.y), (sx, sy)) > 1:
        return False

    storage = _ensure_storage_state(storage_building)
    missing_wood = max(0, int(wood_need) - int(agent.inventory.get("wood", 0)))
    missing_stone = max(0, int(stone_need) - int(agent.inventory.get("stone", 0)))
    take_wood = min(int(storage.get("wood", 0)), missing_wood)
    take_stone = min(int(storage.get("stone", 0)), missing_stone)
    if take_wood <= 0 and take_stone <= 0:
        return False
    storage["wood"] = int(storage.get("wood", 0)) - take_wood
    storage["stone"] = int(storage.get("stone", 0)) - take_stone
    agent.inventory["wood"] = int(agent.inventory.get("wood", 0)) + take_wood
    agent.inventory["stone"] = int(agent.inventory.get("stone", 0)) + take_stone
    _sync_village_storage_cache(world, village)
    return True


def _iter_diamond(center: Coord, radius: int) -> List[Coord]:
    cx, cy = center
    points: List[Coord] = []
    for dx in range(-radius, radius + 1):
        max_dy = radius - abs(dx)
        for dy in range(-max_dy, max_dy + 1):
            points.append((cx + dx, cy + dy))
    return sorted(points, key=_coord_key)


def _default_search_anchors(world: "World", village: Dict[str, Any], building_type: str) -> List[Coord]:
    metadata = get_building_metadata(building_type) or {}
    category = str(metadata.get("category", ""))
    anchors: List[Coord] = [_village_center(village), _nearest_storage_anchor(world, village)]

    if building_type == "farm_plot":
        anchors.append(_village_farm_zone(village))
    elif category in {"production", "infrastructure"}:
        anchors.append(_village_farm_zone(village))

    unique: List[Coord] = []
    seen: Set[Coord] = set()
    for anchor in anchors:
        if anchor in seen:
            continue
        seen.add(anchor)
        unique.append(anchor)
    return unique


def _enumerate_candidate_positions(
    world: "World",
    building_type: str,
    *,
    village: Optional[Dict[str, Any]],
    agent_pos: Coord,
    preferred_anchors: Optional[List[Coord]] = None,
    search_radius: int = 8,
    max_distance_from_agent: Optional[int] = None,
) -> List[Coord]:
    anchors: List[Coord] = []
    if preferred_anchors:
        anchors.extend(preferred_anchors)
    elif village is not None:
        anchors.extend(_default_search_anchors(world, village, building_type))
    else:
        anchors.append(agent_pos)

    candidates: Set[Coord] = set()
    for anchor in anchors:
        for pos in _iter_diamond(anchor, search_radius):
            x, y = pos
            if not (0 <= x < world.width and 0 <= y < world.height):
                continue
            if max_distance_from_agent is not None and _distance(pos, agent_pos) > max_distance_from_agent:
                continue
            candidates.add(pos)

    return sorted(candidates, key=_coord_key)


def _resource_context_points(world: "World", resource_type: str) -> List[Coord]:
    if resource_type == "stone":
        points = set(getattr(world, "stone", set()))
        for y, row in enumerate(world.tiles):
            for x, tile in enumerate(row):
                if tile == "M":
                    points.add((x, y))
        return sorted(points, key=_coord_key)
    if resource_type == "wood":
        points = set(getattr(world, "wood", set()))
        for y, row in enumerate(world.tiles):
            for x, tile in enumerate(row):
                if tile == "F":
                    points.add((x, y))
        return sorted(points, key=_coord_key)
    return []


def evaluate_production_resource_context(world: "World", building_type: str, pos: Coord) -> Dict[str, Any]:
    metadata = get_building_metadata(building_type) or {}
    resource_type = metadata.get("resource_type")
    required = bool(metadata.get("resource_context_required", False))
    radius = int(metadata.get("resource_context_radius", 0))
    min_tiles = int(metadata.get("resource_context_min_tiles", 0))

    if not resource_type:
        return {
            "required": required,
            "valid": True,
            "linked_resource_type": None,
            "linked_resource_tiles_count": 0,
            "linked_resource_anchor": None,
        }

    points = _resource_context_points(world, str(resource_type))
    nearby = [p for p in points if _distance(p, pos) <= radius]
    nearby_sorted = sorted(nearby, key=lambda p: (_distance(p, pos), _coord_key(p)))
    anchor = nearby_sorted[0] if nearby_sorted else None
    valid = len(nearby) >= max(0, min_tiles)
    return {
        "required": required,
        "valid": valid,
        "linked_resource_type": str(resource_type),
        "linked_resource_tiles_count": len(nearby),
        "linked_resource_anchor": {"x": anchor[0], "y": anchor[1]} if anchor is not None else None,
    }


def score_building_position(world: "World", village: Dict[str, Any], building_type: str, pos: Coord) -> int:
    metadata = get_building_metadata(building_type)
    if metadata is None:
        return -10**9
    if not can_place_building(world, building_type, pos):
        return -10**9

    category = str(metadata.get("category", ""))
    requires_road = bool(metadata.get("requires_road", False))
    center = _village_center(village)
    farm_zone = _village_farm_zone(village)
    storage_anchor = _nearest_storage_anchor(world, village)
    road_points = _road_points(world)

    d_center = _distance(pos, center)
    d_farm_zone = _distance(pos, farm_zone)
    d_storage = _distance(pos, storage_anchor)
    d_road = _distance_to_nearest(pos, road_points)
    nearby_houses = count_nearby_houses(world, pos[0], pos[1], radius=3)

    score = 0

    if category in {"governance", "food_storage"}:
        score += max(0, 64 - d_center * 8)
        score += max(0, 18 - d_road * 3)
    elif category == "residential":
        score += max(0, 52 - d_center * 5)
        score += max(0, 18 - d_road * 3)
        score += nearby_houses * 5
    elif category in {"production"}:
        score += min(d_center, 8) * 4
        score += max(0, 24 - d_storage * 3)
        score += max(0, 20 - d_road * 4)
        score -= nearby_houses * 4
    elif category == "infrastructure":
        score += max(0, 30 - d_road * 5)
        score += max(0, 20 - d_center * 3)
    else:
        score += max(0, 28 - d_center * 3)

    if building_type == "farm_plot":
        score += max(0, 70 - d_farm_zone * 8)
        score -= nearby_houses * 6
        if d_center <= 3:
            score -= 20

    if category == "production" and d_center <= 3:
        score -= 20

    if requires_road:
        if d_road <= 1:
            score += 20
        elif d_road <= 3:
            score += 8
        else:
            score -= 18

    return score


def find_preferred_build_position(
    world: "World",
    village: Dict[str, Any],
    building_type: str,
    candidates: List[Coord],
) -> Optional[Coord]:
    best_pos: Optional[Coord] = None
    best_score = -10**9
    for pos in sorted(candidates, key=_coord_key):
        score = score_building_position(world, village, building_type, pos)
        if score > best_score:
            best_score = score
            best_pos = pos
    return best_pos


def try_build_type(
    world: "World",
    agent: "Agent",
    building_type: str,
    village_id: Optional[int] = None,
    village_uid: Optional[str] = None,
    *,
    preferred_anchors: Optional[List[Coord]] = None,
    search_radius: int = 8,
    max_distance_from_agent: Optional[int] = None,
    as_construction_site: bool = False,
) -> Dict[str, Any]:
    if building_type not in BUILDING_CATALOG:
        return {
            "success": False,
            "reason": "unknown_building_type",
            "building_id": None,
            "position": None,
        }

    resolved_village_id = village_id if village_id is not None else getattr(agent, "village_id", None)
    resolved_village_uid = village_uid if village_uid is not None else world.resolve_village_uid(resolved_village_id)

    village: Optional[Dict[str, Any]] = None
    if resolved_village_id is not None:
        village = world.get_village_by_id(resolved_village_id)
    elif resolved_village_uid is not None:
        village = next((v for v in world.villages if v.get("village_uid") == resolved_village_uid), None)

    if village is not None:
        readiness = evaluate_building_readiness_for_village(world, village, building_type)
        if readiness["status"] == "unavailable":
            if building_type in SPECIALIZATION_BUILDING_TYPES:
                if not bool(readiness.get("tier_ok", False)):
                    record_specialization_blocker(world, building_type, "readiness_tier_too_low", village=village)
                if not bool(readiness.get("hard_requirements_ok", False)):
                    record_specialization_blocker(
                        world,
                        building_type,
                        _specialization_hard_requirement_blocker_reason(world, village, building_type),
                        village=village,
                    )
            return {
                "success": False,
                "reason": "readiness_unavailable",
                "building_id": None,
                "position": None,
            }

    candidates = _enumerate_candidate_positions(
        world,
        building_type,
        village=village,
        agent_pos=(agent.x, agent.y),
        preferred_anchors=preferred_anchors,
        search_radius=search_radius,
        max_distance_from_agent=max_distance_from_agent,
    )

    placeable = [pos for pos in candidates if can_place_building(world, building_type, pos)]
    if not placeable:
        if building_type in SPECIALIZATION_BUILDING_TYPES:
            record_specialization_blocker(world, building_type, "no_valid_placement", village=village)
        return {
            "success": False,
            "reason": "no_valid_position",
            "building_id": None,
            "position": None,
        }

    context_by_pos: Dict[Coord, Dict[str, Any]] = {}
    filtered: List[Coord] = []
    for pos in placeable:
        context = evaluate_production_resource_context(world, building_type, pos)
        context_by_pos[pos] = context
        if context["required"] and not context["valid"]:
            continue
        filtered.append(pos)

    if not filtered:
        if building_type in SPECIALIZATION_BUILDING_TYPES:
            record_specialization_blocker(world, building_type, "no_resource_context", village=village)
            record_specialization_requirement_breakdown(
                world,
                building_type,
                "requirement_resource_context_failed",
                village=village,
            )
        return {
            "success": False,
            "reason": "invalid_resource_context",
            "building_id": None,
            "position": None,
        }
    if building_type in SPECIALIZATION_BUILDING_TYPES:
        record_specialization_stage(world, building_type, "placement_candidate_found_count", village=village)

    chosen: Optional[Coord]
    if village is not None:
        chosen = find_preferred_build_position(world, village, building_type, filtered)
    else:
        chosen = min(filtered, key=lambda pos: (_distance(pos, (agent.x, agent.y)), _coord_key(pos)))

    if chosen is None:
        return {
            "success": False,
            "reason": "no_valid_position",
            "building_id": None,
            "position": None,
        }

    create_as_site = bool(as_construction_site and building_type in {"house", "storage"})
    if create_as_site:
        placed = _create_construction_site(
            world,
            building_type,
            chosen,
            village_id=resolved_village_id,
            village_uid=resolved_village_uid,
            costs=_construction_costs(building_type),
        )
    else:
        placed = place_building(
            world,
            building_type,
            chosen,
            village_id=resolved_village_id,
            village_uid=resolved_village_uid,
        )
    if placed is None:
        if building_type in SPECIALIZATION_BUILDING_TYPES:
            record_specialization_blocker(world, building_type, "no_valid_placement", village=village)
        return {
            "success": False,
            "reason": "placement_rejected",
            "building_id": None,
            "position": None,
        }

    context = context_by_pos.get(chosen, {})
    placed["linked_resource_type"] = context.get("linked_resource_type")
    placed["linked_resource_tiles_count"] = int(context.get("linked_resource_tiles_count", 0))
    placed["linked_resource_anchor"] = context.get("linked_resource_anchor")
    if not create_as_site:
        placed["operational_state"] = (
            "active"
            if (not context.get("required", False) or context.get("valid", False))
            else "inactive"
        )
    if building_type in SPECIALIZATION_BUILDING_TYPES:
        if str(placed.get("operational_state", "")) == "active":
            record_specialization_stage(world, building_type, "built_active_count", village=village)
        else:
            record_specialization_blocker(world, building_type, "building_inactive", village=village)

    return {
        "success": True,
        "reason": "construction_site_created" if create_as_site else "placed",
        "building_id": placed["building_id"],
        "position": {"x": int(chosen[0]), "y": int(chosen[1])},
    }


def _storage_exists_for_village(world: "World", village: Dict[str, Any]) -> bool:
    village_id = _village_id(village)
    village_uid = _village_uid(village)
    for building in getattr(world, "buildings", {}).values():
        if building.get("type") != "storage":
            continue
        if village_id is not None and building.get("village_id") == village_id:
            return True
        if village_uid is not None and building.get("village_uid") == village_uid:
            return True

    storage_pos = village.get("storage_pos")
    if isinstance(storage_pos, dict):
        sx = int(storage_pos.get("x", -1))
        sy = int(storage_pos.get("y", -1))
        if (sx, sy) in getattr(world, "storage_buildings", set()):
            return True
    return False


def _farms_count_for_village(world: "World", village: Dict[str, Any]) -> int:
    village_id = _village_id(village)
    if village_id is None:
        return 0
    return sum(
        1
        for plot in getattr(world, "farm_plots", {}).values()
        if isinstance(plot, dict) and plot.get("village_id") == village_id
    )


def _effective_village_tier(world: "World", village: Dict[str, Any]) -> int:
    declared = int(village.get("tier", 1))
    if declared >= 2:
        return declared

    population = int(village.get("population", 0))
    houses = int(village.get("houses", 0))
    farms_count = _farms_count_for_village(world, village)
    signals = evaluate_village_unlock_signals(world, village)
    mature_tier2 = (
        population >= SPECIALIZATION_TIER2_POPULATION_MIN
        and houses >= SPECIALIZATION_TIER2_HOUSES_MIN
        and farms_count >= 1
        and bool(signals.get("storage_exists", False))
        and bool(signals.get("roads_present", False))
    )
    if mature_tier2:
        return 2
    return declared


def evaluate_village_unlock_signals(world: "World", village: Dict[str, Any]) -> Dict[str, bool]:
    population = int(village.get("population", 0))
    houses = int(village.get("houses", 0))
    storage = _village_storage(world, village)
    farms_count = _farms_count_for_village(world, village)
    storage_exists = _storage_exists_for_village(world, village)
    center_x, center_y = _village_center(village)

    roads_present = any(
        abs(rx - center_x) <= SPECIALIZATION_ROAD_SIGNAL_RADIUS
        and abs(ry - center_y) <= SPECIALIZATION_ROAD_SIGNAL_RADIUS
        for rx, ry in getattr(world, "roads", set())
    )

    food = int(storage.get("food", 0))
    wood = int(storage.get("wood", 0))
    stone = int(storage.get("stone", 0))
    total_storage = food + wood + stone

    return {
        "farms_present": farms_count > 0,
        "storage_exists": storage_exists,
        "roads_present": roads_present,
        "food_surplus_high": food >= max(4, population * 2),
        "population_pressure_high": houses > 0 and population >= houses * 2,
        "storage_pressure_high": total_storage >= max(6, houses * 4),
        "wood_demand_high": wood < max(2, houses * 2),
        "stone_demand_high": stone < max(1, houses),
    }


def building_hard_requirements_met(world: "World", village: Dict[str, Any], building_type: str) -> bool:
    metadata = get_building_metadata(building_type)
    if metadata is None:
        return False

    requirements = metadata.get("hard_requirements", {})
    if requirements in (None, {}):
        return True
    if not isinstance(requirements, dict):
        return False

    population = int(village.get("population", 0))
    houses = int(village.get("houses", 0))
    farms_count = _farms_count_for_village(world, village)
    storage_exists = _storage_exists_for_village(world, village)
    roads_present = evaluate_village_unlock_signals(world, village)["roads_present"]

    for key, value in requirements.items():
        try:
            if key == "population_min":
                if population < int(value):
                    return False
            elif key == "houses_min":
                if houses < int(value):
                    return False
            elif key == "farms_min":
                if farms_count < int(value):
                    return False
            elif key == "storage_required":
                if bool(value) and not storage_exists:
                    return False
            elif key == "roads_required":
                if bool(value) and not roads_present:
                    return False
            else:
                # Unsupported requirements fail safely.
                return False
        except (TypeError, ValueError):
            return False

    return True


def _specialization_requirement_fail_reasons(
    world: "World",
    village: Dict[str, Any],
    building_type: str,
) -> List[str]:
    metadata = get_building_metadata(building_type)
    if metadata is None:
        return []
    requirements = metadata.get("hard_requirements", {})
    if requirements in (None, {}):
        return []
    if not isinstance(requirements, dict):
        return []

    population = int(village.get("population", 0))
    houses = int(village.get("houses", 0))
    farms_count = _farms_count_for_village(world, village)
    storage_exists = _storage_exists_for_village(world, village)
    signals = evaluate_village_unlock_signals(world, village)
    roads_present = bool(signals.get("roads_present", False))

    reasons: List[str] = []
    for key, value in requirements.items():
        try:
            if key == "population_min" and population < int(value):
                reasons.append("requirement_population_min_failed")
            elif key == "houses_min" and houses < int(value):
                reasons.append("requirement_houses_min_failed")
            elif key == "farms_min" and farms_count < int(value):
                reasons.append("requirement_farms_min_failed")
            elif key == "storage_required" and bool(value) and not storage_exists:
                reasons.append("requirement_storage_required_failed")
            elif key == "roads_required" and bool(value) and not roads_present:
                reasons.append("requirement_roads_required_failed")
        except (TypeError, ValueError):
            return []
    return sorted(set(reasons))


def _specialization_tier_input_fail_reasons(
    world: "World",
    village: Dict[str, Any],
    *,
    min_tier: int,
    effective_tier: int,
) -> List[str]:
    if effective_tier >= min_tier:
        return []
    if min_tier < 2:
        return []
    population = int(village.get("population", 0))
    houses = int(village.get("houses", 0))
    farms_count = _farms_count_for_village(world, village)
    signals = evaluate_village_unlock_signals(world, village)
    reasons: List[str] = []
    if population < SPECIALIZATION_TIER2_POPULATION_MIN:
        reasons.append("tier_inputs_population_low")
    if houses < SPECIALIZATION_TIER2_HOUSES_MIN:
        reasons.append("tier_inputs_houses_low")
    if farms_count < 1:
        reasons.append("tier_inputs_farms_low")
    if not bool(signals.get("storage_exists", False)):
        reasons.append("tier_inputs_storage_missing")
    if not bool(signals.get("roads_present", False)):
        reasons.append("tier_inputs_roads_missing")
    return reasons


def _specialization_hard_requirement_blocker_reason(
    world: "World",
    village: Dict[str, Any],
    building_type: str,
) -> str:
    reasons = _specialization_requirement_fail_reasons(world, village, building_type)
    if "requirement_roads_required_failed" in reasons:
        return "no_road_service"
    return "hard_requirements_failed"


def evaluate_building_readiness_for_village(
    world: "World",
    village: Dict[str, Any],
    building_type: str,
) -> Dict[str, Any]:
    metadata = get_building_metadata(building_type)
    if metadata is None:
        return {
            "status": "unavailable",
            "tier_ok": False,
            "hard_requirements_ok": False,
            "matching_signals": [],
        }

    village_tier = _effective_village_tier(world, village)
    min_tier = int(metadata.get("min_tier", metadata.get("tier", 0)))
    tier_ok = village_tier >= min_tier
    hard_requirements_ok = building_hard_requirements_met(world, village, building_type)
    if not tier_ok or not hard_requirements_ok:
        if building_type in SPECIALIZATION_BUILDING_TYPES:
            if not tier_ok:
                record_specialization_blocker(world, building_type, "readiness_tier_too_low", village=village)
                for reason in _specialization_tier_input_fail_reasons(
                    world,
                    village,
                    min_tier=min_tier,
                    effective_tier=village_tier,
                ):
                    record_specialization_readiness_breakdown(world, building_type, reason, village=village)
            if not hard_requirements_ok:
                for reason in _specialization_requirement_fail_reasons(world, village, building_type):
                    record_specialization_requirement_breakdown(world, building_type, reason, village=village)
                record_specialization_blocker(
                    world,
                    building_type,
                    _specialization_hard_requirement_blocker_reason(world, village, building_type),
                    village=village,
                )
        return {
            "status": "unavailable",
            "tier_ok": tier_ok,
            "hard_requirements_ok": hard_requirements_ok,
            "matching_signals": [],
        }

    signals = evaluate_village_unlock_signals(world, village)
    unlock_signals = metadata.get("unlock_signals", [])
    matching_signals = sorted(
        [
            signal
            for signal in unlock_signals
            if isinstance(signal, str) and signals.get(signal, False)
        ]
    )
    if building_type in SPECIALIZATION_BUILDING_TYPES:
        record_specialization_stage(world, building_type, "readiness_possible_count", village=village)
        if not matching_signals:
            record_specialization_blocker(world, building_type, "village_never_reached_trigger_pressure", village=village)
    status = "recommended" if matching_signals else "available"
    return {
        "status": status,
        "tier_ok": True,
        "hard_requirements_ok": True,
        "matching_signals": matching_signals,
    }


def get_available_building_types_for_village(world: "World", village: Dict[str, Any]) -> List[str]:
    result: List[str] = []
    for building_type in sorted(BUILDING_CATALOG.keys()):
        readiness = evaluate_building_readiness_for_village(world, village, building_type)
        if readiness["status"] in {"available", "recommended"}:
            result.append(building_type)
    return result


def get_recommended_building_types_for_village(world: "World", village: Dict[str, Any]) -> List[str]:
    result: List[str] = []
    for building_type in sorted(BUILDING_CATALOG.keys()):
        readiness = evaluate_building_readiness_for_village(world, village, building_type)
        if readiness["status"] == "recommended":
            result.append(building_type)
    return result


def _footprint_offsets(building_type: str) -> List[Coord]:
    metadata = get_building_metadata(building_type)
    if metadata is None:
        return []
    width, height = metadata.get("footprint_size", (0, 0))
    width_i = int(width)
    height_i = int(height)
    if width_i <= 0 or height_i <= 0:
        return []
    return [(dx, dy) for dy in range(height_i) for dx in range(width_i)]


def footprint_tiles(building_type: str, origin: Coord) -> List[Coord]:
    ox, oy = origin
    tiles = [(ox + dx, oy + dy) for dx, dy in _footprint_offsets(building_type)]
    return sorted(tiles, key=_coord_key)


def can_place_building(world: "World", building_type: str, origin: Coord) -> bool:
    tiles = footprint_tiles(building_type, origin)
    if not tiles:
        return False

    for x, y in tiles:
        if not (0 <= x < world.width and 0 <= y < world.height):
            return False
        if not world.is_walkable(x, y):
            return False
        if world.is_tile_blocked_by_building(x, y):
            return False
    return True


def place_building(
    world: "World",
    building_type: str,
    origin: Coord,
    *,
    village_id: Optional[int] = None,
    village_uid: Optional[str] = None,
    connected_to_road: bool = False,
    operational_state: Optional[str] = None,
    construction_request: Optional[Dict[str, int]] = None,
    construction_buffer: Optional[Dict[str, int]] = None,
    construction_progress: Optional[int] = None,
    construction_required_work: Optional[int] = None,
) -> Optional[Dict]:
    if building_type not in BUILDING_CATALOG:
        return None

    village_for_readiness: Optional[Dict[str, Any]] = None
    if village_id is not None:
        village_for_readiness = world.get_village_by_id(village_id)
    elif village_uid is not None:
        village_for_readiness = next(
            (v for v in world.villages if v.get("village_uid") == village_uid),
            None,
        )

    if village_for_readiness is not None:
        readiness = evaluate_building_readiness_for_village(world, village_for_readiness, building_type)
        if readiness["status"] == "unavailable":
            return None

    if not can_place_building(world, building_type, origin):
        return None

    context = evaluate_production_resource_context(world, building_type, origin)
    if context.get("required", False) and not context.get("valid", False):
        return None

    x, y = origin
    tiles = footprint_tiles(building_type, origin)
    building_id = world.new_building_id()
    tile_dicts = [{"x": tx, "y": ty} for tx, ty in tiles]
    metadata = get_building_metadata(building_type)
    if metadata is None:
        return None
    computed_state = (
        "active"
        if (not context.get("required", False) or context.get("valid", False))
        else "inactive"
    )
    building = {
        "building_id": building_id,
        "type": building_type,
        "category": str(metadata.get("category", "")),
        "tier": int(metadata.get("tier", 0)),
        "x": x,
        "y": y,
        "footprint": tile_dicts,
        "village_id": village_id,
        "village_uid": village_uid,
        "connected_to_road": bool(connected_to_road),
        "requires_road": bool(metadata.get("requires_road", False)),
        "worker_capacity": int(metadata.get("worker_capacity", 0)),
        "description": str(metadata.get("description", "")),
        "unlock_conditions": dict(metadata.get("unlock_conditions", {})),
        "linked_resource_type": context.get("linked_resource_type"),
        "linked_resource_tiles_count": int(context.get("linked_resource_tiles_count", 0)),
        "linked_resource_anchor": context.get("linked_resource_anchor"),
        "operational_state": str(operational_state or computed_state),
    }
    if construction_request is not None:
        building["construction_request"] = dict(construction_request)
    if construction_buffer is not None:
        building["construction_buffer"] = dict(construction_buffer)
    if construction_progress is not None:
        building["construction_progress"] = max(0, int(construction_progress))
    if construction_required_work is not None:
        building["construction_required_work"] = max(1, int(construction_required_work))
    if building_type == "storage":
        building["storage"] = _empty_resource_bucket()
        building["storage_capacity"] = STORAGE_BUILDING_CAPACITY
        # Backward-compat migration: if village had aggregate stock before explicit
        # storage-state existed, move it into the first concrete storage building.
        if village_for_readiness is not None:
            existing_storage = _iter_village_storage_buildings(world, village_for_readiness)
            if not existing_storage:
                legacy = village_for_readiness.get("storage", {})
                if isinstance(legacy, dict):
                    building["storage"]["food"] = int(legacy.get("food", 0))
                    building["storage"]["wood"] = int(legacy.get("wood", 0))
                    building["storage"]["stone"] = int(legacy.get("stone", 0))
    elif building_type == "house":
        building["domestic_food"] = int(building.get("domestic_food", 0))
        building["domestic_food_capacity"] = int(building.get("domestic_food_capacity", HOUSE_DOMESTIC_FOOD_CAPACITY))

    world.buildings[building_id] = building
    for tile in tiles:
        world.building_occupancy[tile] = building_id

    # Legacy compatibility sets kept for existing gameplay and observer paths.
    if building_type == "house" and building.get("operational_state") == "active":
        world.structures.add(origin)
        _record_housing_path(
            world,
            "house_activated_via_direct_path",
            village_uid=str(village_uid or _resolve_village_uid(world, village_for_readiness) or ""),
        )
        if hasattr(world, "record_settlement_progression_build_event"):
            world.record_settlement_progression_build_event("house", building)
    elif building_type == "storage" and building.get("operational_state") == "active":
        world.storage_buildings.add(origin)
        if village_for_readiness is not None:
            _sync_village_storage_cache(world, village_for_readiness)
        if hasattr(world, "record_settlement_progression_build_event"):
            world.record_settlement_progression_build_event("storage", building)

    return building


def _find_nearest_storage_spot(world: "World", village: dict, origin: Coord) -> Optional[Coord]:
    cx = village.get("center", {}).get("x", origin[0])
    cy = village.get("center", {}).get("y", origin[1])
    preferred_anchors: List[Coord] = [(int(cx), int(cy))]
    houses = [
        b
        for b in getattr(world, "buildings", {}).values()
        if isinstance(b, dict)
        and str(b.get("type", "")) == "house"
        and str(b.get("operational_state", "")) == "active"
        and (b.get("village_id") == village.get("id") or str(b.get("village_uid", "")) == str(village.get("village_uid", "")))
    ]
    if len(houses) >= 2:
        hx = int(round(sum(int(h.get("x", 0)) for h in houses) / float(len(houses))))
        hy = int(round(sum(int(h.get("y", 0)) for h in houses) / float(len(houses))))
        preferred_anchors.insert(0, (hx, hy))
    if hasattr(world, "_nearest_active_camp_raw"):
        try:
            camp = world._nearest_active_camp_raw(int(cx), int(cy), max_distance=10)  # type: ignore[attr-defined]
        except Exception:
            camp = None
        if isinstance(camp, dict):
            preferred_anchors.insert(0, (int(camp.get("x", cx)), int(camp.get("y", cy))))

    candidates = _enumerate_candidate_positions(
        world,
        "storage",
        village=village,
        agent_pos=origin,
        preferred_anchors=preferred_anchors,
        search_radius=6,
        max_distance_from_agent=10,
    )
    placeable = [pos for pos in candidates if can_place_building(world, "storage", pos)]
    if not placeable:
        return None
    if not getattr(world, "agents", None):
        return find_preferred_build_position(world, village, "storage", placeable)
    # Prefer cohesive local materialization near viable secondary nuclei when available.
    nearby_agent = min(
        [a for a in world.agents if getattr(a, "alive", False)],
        key=lambda a: abs(int(getattr(a, "x", 0)) - int(origin[0])) + abs(int(getattr(a, "y", 0)) - int(origin[1])),
        default=None,
    )
    if nearby_agent is None or not hasattr(world, "secondary_nucleus_build_position_bonus"):
        return find_preferred_build_position(world, village, "storage", placeable)
    best_pos: Optional[Coord] = None
    best_score = -10**9
    primary_anchor = preferred_anchors[0] if preferred_anchors else (int(cx), int(cy))
    for pos in sorted(placeable, key=_coord_key):
        score = score_building_position(world, village, "storage", pos)
        nearby_houses = count_nearby_houses(world, int(pos[0]), int(pos[1]), radius=6)
        nearby_people = count_nearby_population(world, int(pos[0]), int(pos[1]), radius=6)
        score += min(20, int(nearby_houses) * 4)
        score += min(12, int(nearby_people) * 2)
        score += max(0, 28 - (_distance(pos, primary_anchor) * 5))
        try:
            score += int(world.secondary_nucleus_build_position_bonus(nearby_agent, pos, "storage"))
        except Exception:
            pass
        if score > best_score:
            best_score = int(score)
            best_pos = pos
    return best_pos


def _storage_maturity_snapshot(world: "World", village: Dict[str, Any]) -> Dict[str, Any]:
    center = village.get("center", {}) if isinstance(village.get("center"), dict) else {}
    cx = int(center.get("x", 0))
    cy = int(center.get("y", 0))
    houses = int(village.get("houses", 0))
    nearby_houses = count_nearby_houses(world, cx, cy, radius=8) if ("x" in center and "y" in center) else houses
    nearby_population = count_nearby_population(world, cx, cy, radius=7) if ("x" in center and "y" in center) else int(village.get("population", 0))
    if nearby_population <= 0:
        nearby_population = int(village.get("population", 0))
    production = village.get("production_metrics", {}) if isinstance(village.get("production_metrics"), dict) else {}
    camp_food = getattr(world, "camp_food_stats", {}) if isinstance(getattr(world, "camp_food_stats", {}), dict) else {}
    flow_events = int(camp_food.get("camp_food_deposits", 0)) + int(camp_food.get("domestic_food_stored_total", 0))
    flow_events += int(camp_food.get("pressure_backed_food_deliveries", 0))
    flow_events += int(production.get("total_food_gathered", 0)) // 12
    buffer_pressure = int(camp_food.get("domestic_storage_full_events", 0)) + int(camp_food.get("camp_food_pressure_ticks", 0)) // 12
    signals = evaluate_village_unlock_signals(world, village)
    food_stock = int((village.get("storage", {}) or {}).get("food", 0)) if isinstance(village.get("storage", {}), dict) else 0
    house_cluster_ready = bool(nearby_houses >= int(STORAGE_MATURE_CLUSTER_HOUSES_MIN))
    throughput_ready = bool(flow_events >= int(STORAGE_MATURE_FLOW_EVENTS_MIN) or food_stock >= 16)
    pressure_ready = bool(buffer_pressure >= int(STORAGE_MATURE_BUFFER_PRESSURE_MIN) or bool(signals.get("storage_pressure_high")))
    support_ready = bool(nearby_population >= int(STORAGE_MATURE_CLUSTER_POP_MIN))
    surplus_ready = False
    if hasattr(world, "is_village_surplus_sustained"):
        try:
            surplus_ready = bool(world.is_village_surplus_sustained(village))
        except Exception:
            surplus_ready = False
    if not surplus_ready and hasattr(world, "update_village_surplus_state"):
        try:
            state = world.update_village_surplus_state(village)
            food_rate = float(state.get("food_surplus_rate", 0.0))
            resource_rate = float(state.get("resource_surplus_rate", 0.0))
            saturation = int(state.get("buffer_saturation_events", 0))
            surplus_ready = bool(
                food_rate >= float(STORAGE_SURPLUS_FOOD_RATE_MIN)
                and resource_rate >= float(STORAGE_SURPLUS_RESOURCE_RATE_MIN)
                and saturation >= 2
            )
        except Exception:
            surplus_ready = False
    mature_ready = bool(house_cluster_ready and throughput_ready and pressure_ready and support_ready and surplus_ready)
    return {
        "nearby_houses": int(nearby_houses),
        "nearby_population": int(nearby_population),
        "flow_events": int(flow_events),
        "buffer_pressure": int(buffer_pressure),
        "house_cluster_ready": bool(house_cluster_ready),
        "throughput_ready": bool(throughput_ready),
        "pressure_ready": bool(pressure_ready),
        "support_ready": bool(support_ready),
        "surplus_ready": bool(surplus_ready),
        "mature_ready": bool(mature_ready),
    }


def _storage_defer_reason_for_snapshot(snapshot: Dict[str, Any]) -> Optional[str]:
    if bool(snapshot.get("house_cluster_ready", False)) is False:
        return "storage_deferred_due_to_low_house_cluster"
    if bool(snapshot.get("throughput_ready", False)) is False:
        return "storage_deferred_due_to_low_throughput"
    if bool(snapshot.get("pressure_ready", False)) is False:
        return "storage_deferred_due_to_low_buffer_pressure"
    if bool(snapshot.get("support_ready", False)) is False:
        return "storage_deferred_due_to_low_throughput"
    if bool(snapshot.get("surplus_ready", False)) is False:
        return "storage_deferred_due_to_low_surplus"
    return None


def _get_build_wallet(world: "World", agent: "Agent"):
    return agent.inventory


def _can_pay(world: "World", agent: "Agent", wood_cost: int, stone_cost: int) -> bool:
    wallet = _get_build_wallet(world, agent)
    return wallet.get("wood", 0) >= wood_cost and wallet.get("stone", 0) >= stone_cost


def _pay(world: "World", agent: "Agent", wood_cost: int, stone_cost: int) -> None:
    wallet = _get_build_wallet(world, agent)
    wallet["wood"] = wallet.get("wood", 0) - wood_cost
    wallet["stone"] = wallet.get("stone", 0) - stone_cost


def _construction_costs(building_type: str) -> Dict[str, int]:
    if building_type == "house":
        return {"wood": HOUSE_WOOD_COST, "stone": HOUSE_STONE_COST, "food": 0}
    if building_type == "storage":
        return {"wood": STORAGE_WOOD_COST, "stone": STORAGE_STONE_COST, "food": 0}
    return {"wood": 0, "stone": 0, "food": 0}


def _construction_required_work(building_type: str) -> int:
    return max(1, int(CONSTRUCTION_REQUIRED_WORK_BY_TYPE.get(str(building_type), 3)))


def _empty_construction_buffer() -> Dict[str, int]:
    return {"wood": 0, "stone": 0, "food": 0}


def _construction_request_from_costs(costs: Dict[str, int]) -> Dict[str, int]:
    return {
        "wood_needed": int(costs.get("wood", 0)),
        "stone_needed": int(costs.get("stone", 0)),
        "food_needed": int(costs.get("food", 0)),
        "wood_reserved": 0,
        "stone_reserved": 0,
        "food_reserved": 0,
    }


def get_outstanding_construction_needs(building: Dict[str, Any]) -> Dict[str, int]:
    req = building.get("construction_request")
    if not isinstance(req, dict):
        return {"wood": 0, "stone": 0, "food": 0}
    buf = building.get("construction_buffer")
    if not isinstance(buf, dict):
        buf = _empty_construction_buffer()
        building["construction_buffer"] = buf

    outstanding: Dict[str, int] = {}
    for resource in ("wood", "stone", "food"):
        needed = max(0, int(req.get(f"{resource}_needed", 0)))
        reserved = max(0, int(req.get(f"{resource}_reserved", 0)))
        buffered = max(0, int(buf.get(resource, 0)))
        outstanding[resource] = max(0, needed - reserved - buffered)
    return outstanding


def reserve_materials_for_construction(
    world: "World",
    building_id: str,
    resource_type: str,
    amount: int,
) -> int:
    building = getattr(world, "buildings", {}).get(building_id)
    if not isinstance(building, dict):
        return 0
    if building.get("operational_state") != "under_construction":
        return 0
    req = building.get("construction_request")
    if not isinstance(req, dict):
        return 0
    r = str(resource_type)
    if r not in ("wood", "stone", "food"):
        return 0
    want = max(0, int(amount))
    if want <= 0:
        return 0
    outstanding = get_outstanding_construction_needs(building).get(r, 0)
    reserve = min(want, int(outstanding))
    if reserve <= 0:
        return 0
    key = f"{r}_reserved"
    req[key] = int(req.get(key, 0)) + reserve
    return reserve


def fulfill_reserved_delivery(
    world: "World",
    building_id: str,
    resource_type: str,
    amount: int,
) -> int:
    building = getattr(world, "buildings", {}).get(building_id)
    if not isinstance(building, dict):
        return 0
    req = building.get("construction_request")
    if not isinstance(req, dict):
        return 0
    buf = building.get("construction_buffer")
    if not isinstance(buf, dict):
        buf = _empty_construction_buffer()
        building["construction_buffer"] = buf

    r = str(resource_type)
    if r not in ("wood", "stone", "food"):
        return 0
    deliver = max(0, int(amount))
    if deliver <= 0:
        return 0
    reserved_key = f"{r}_reserved"
    reserved = max(0, int(req.get(reserved_key, 0)))
    qty = min(deliver, reserved)
    if qty <= 0:
        return 0
    req[reserved_key] = reserved - qty
    buf[r] = int(buf.get(r, 0)) + qty
    return qty


def _use_construction_buffer(building: Dict[str, Any], costs: Dict[str, int]) -> bool:
    buf = building.get("construction_buffer")
    if not isinstance(buf, dict):
        return False
    for resource in ("wood", "stone", "food"):
        if int(buf.get(resource, 0)) < int(costs.get(resource, 0)):
            return False
    for resource in ("wood", "stone", "food"):
        buf[resource] = int(buf.get(resource, 0)) - int(costs.get(resource, 0))
    return True


def _site_ready_for_completion(building: Dict[str, Any], costs: Dict[str, int]) -> bool:
    buf = building.get("construction_buffer")
    if not isinstance(buf, dict):
        return False
    for resource in ("wood", "stone", "food"):
        if int(buf.get(resource, 0)) < int(costs.get(resource, 0)):
            return False
    return True


def _mark_builder_waiting_on_site(world: "World", building: Dict[str, Any], agent: "Agent") -> None:
    if not isinstance(building, dict):
        return
    building["builder_waiting_tick"] = int(getattr(world, "tick", 0))
    building["builder_waiting_agent_id"] = str(getattr(agent, "agent_id", ""))
    _mark_construction_site_demand_tick(world, building)
    if hasattr(world, "record_delivery_pipeline_stage"):
        world.record_delivery_pipeline_stage(agent, "delivery_target_created_count", role="builder")
    if hasattr(world, "record_settlement_progression_metric"):
        world.record_settlement_progression_metric("construction_progress_stalled_ticks")


def _mark_construction_site_demand_tick(world: "World", building: Dict[str, Any]) -> None:
    if not isinstance(building, dict):
        return
    building["construction_last_demand_tick"] = int(getattr(world, "tick", 0))


def _site_has_recent_builder_wait_signal(world: "World", building: Dict[str, Any]) -> bool:
    if not isinstance(building, dict):
        return False
    waiting_tick = building.get("builder_waiting_tick")
    if waiting_tick is None:
        return False
    try:
        wt = int(waiting_tick)
    except Exception:
        return False
    return int(getattr(world, "tick", 0)) - wt <= int(CONSTRUCTION_WAIT_SIGNAL_TICKS)


def can_agent_work_on_construction(agent: "Agent", building: Dict[str, Any]) -> bool:
    if not isinstance(building, dict):
        return False
    bx = int(building.get("x", 0))
    by = int(building.get("y", 0))
    return _distance((int(agent.x), int(agent.y)), (bx, by)) <= int(CONSTRUCTION_WORK_RANGE)


def _agent_is_situated_on_site(agent: "Agent", building: Dict[str, Any]) -> bool:
    if not isinstance(building, dict):
        return False
    footprint: List[Coord] = []
    raw_footprint = building.get("footprint", [])
    if isinstance(raw_footprint, list):
        for tile in raw_footprint:
            if isinstance(tile, dict) and "x" in tile and "y" in tile:
                footprint.append((int(tile["x"]), int(tile["y"])))
    if not footprint:
        footprint.append((int(building.get("x", 0)), int(building.get("y", 0))))
    ax, ay = int(agent.x), int(agent.y)
    return any(_distance((ax, ay), (tx, ty)) <= int(CONSTRUCTION_WORK_RANGE) for tx, ty in footprint)


def _advance_construction_progress(building: Dict[str, Any], work_amount: int = CONSTRUCTION_WORK_PER_TICK) -> int:
    progress = max(0, int(building.get("construction_progress", 0)))
    required = max(1, int(building.get("construction_required_work", 1)))
    gained = max(0, int(work_amount))
    new_progress = min(required, progress + gained)
    building["construction_progress"] = new_progress
    building["construction_required_work"] = required
    return new_progress


def _site_work_complete(building: Dict[str, Any]) -> bool:
    required = max(1, int(building.get("construction_required_work", 1)))
    progress = max(0, int(building.get("construction_progress", 0)))
    return progress >= required


def _attach_carried_materials_to_site(agent: "Agent", building: Dict[str, Any], costs: Dict[str, int]) -> int:
    buf = building.get("construction_buffer")
    if not isinstance(buf, dict):
        buf = _empty_construction_buffer()
        building["construction_buffer"] = buf
    moved = 0
    for resource in ("wood", "stone", "food"):
        need = max(0, int(costs.get(resource, 0)) - int(buf.get(resource, 0)))
        if need <= 0:
            continue
        have = int(agent.inventory.get(resource, 0))
        qty = min(have, need)
        if qty <= 0:
            continue
        agent.inventory[resource] = have - qty
        buf[resource] = int(buf.get(resource, 0)) + qty
        moved += qty
    return moved


def _builder_self_supply_allowed(world: "World", agent: "Agent", village: Optional[Dict[str, Any]]) -> bool:
    if str(getattr(agent, "role", "")) != "builder":
        return False
    if int(getattr(agent, "hunger", 100)) < int(BUILDER_SELF_SUPPLY_HUNGER_MIN):
        return False
    if not isinstance(village, dict):
        return False
    pop = int(village.get("population", 0))
    if pop <= int(BUILDER_SELF_SUPPLY_FRAGILE_POP_MAX):
        return True
    village_id = village.get("id")
    haulers = 0
    for worker in getattr(world, "agents", []):
        if not getattr(worker, "alive", False):
            continue
        if getattr(worker, "village_id", None) != village_id:
            continue
        if str(getattr(worker, "role", "")) == "hauler":
            haulers += 1
    return haulers <= 0


def _record_builder_self_supply_failure(world: "World", reason: str) -> None:
    if hasattr(world, "record_builder_self_supply_failure"):
        world.record_builder_self_supply_failure(reason)


def _builder_self_supply_village_uid(world: "World", village: Optional[Dict[str, Any]]) -> str:
    if not isinstance(village, dict):
        return ""
    uid = village.get("village_uid")
    if uid is not None:
        return str(uid)
    vid = village.get("id")
    if isinstance(vid, int) and hasattr(world, "resolve_village_uid"):
        resolved = world.resolve_village_uid(vid)
        if resolved is not None:
            return str(resolved)
    return ""


def _record_builder_self_supply_gate_stage(world: "World", stage: str, *, village_uid: str = "") -> None:
    if hasattr(world, "record_builder_self_supply_gate_stage"):
        world.record_builder_self_supply_gate_stage(stage, village_uid=village_uid or None)


def _record_builder_self_supply_gate_failure(world: "World", reason: str, *, village_uid: str = "") -> None:
    if hasattr(world, "record_builder_self_supply_gate_failure"):
        world.record_builder_self_supply_gate_failure(reason, village_uid=village_uid or None)


def _try_builder_local_self_supply(
    world: "World",
    agent: "Agent",
    site: Dict[str, Any],
    costs: Dict[str, int],
    *,
    village: Optional[Dict[str, Any]],
) -> bool:
    village_uid = _builder_self_supply_village_uid(world, village)
    gate_failure_recorded = False

    def _gate_fail(reason: str) -> None:
        nonlocal gate_failure_recorded
        gate_failure_recorded = True
        _record_builder_self_supply_gate_failure(world, reason, village_uid=village_uid)

    if not _builder_self_supply_allowed(world, agent, village):
        return False
    _record_builder_self_supply_gate_stage(world, "self_supply_attempt_seen", village_uid=village_uid)
    if str(site.get("operational_state", "")) != "under_construction":
        _record_builder_self_supply_failure(world, "invalid_site_state")
        _gate_fail("no_valid_site")
        return False
    _record_builder_self_supply_gate_stage(world, "valid_under_construction_site_seen", village_uid=village_uid)
    if not can_agent_work_on_construction(agent, site):
        _record_builder_self_supply_failure(world, "site_not_in_range")
        _gate_fail("no_valid_site")
        return False
    if hasattr(world, "record_builder_self_supply_attempt"):
        world.record_builder_self_supply_attempt()

    sx = int(site.get("x", 0))
    sy = int(site.get("y", 0))
    outstanding = get_outstanding_construction_needs(site)
    if int(outstanding.get("wood", 0)) <= 0 and int(outstanding.get("stone", 0)) <= 0:
        _gate_fail("site_not_material_needy")
        return False
    _record_builder_self_supply_gate_stage(world, "site_material_need_seen", village_uid=village_uid)
    capacity = max(0, int(getattr(agent, "inventory_space", lambda: 0)()))
    if capacity <= 0:
        _record_builder_self_supply_failure(world, "inventory_full")
        _gate_fail("inventory_full")
        return False
    _record_builder_self_supply_gate_stage(world, "inventory_capacity_available", village_uid=village_uid)

    for resource in ("wood", "stone"):
        need = min(
            int(outstanding.get(resource, 0)),
            max(0, int(costs.get(resource, 0))),
            int(BUILDER_SELF_SUPPLY_MAX_PER_RESOURCE),
        )
        if need <= 0:
            continue
        candidate_storage = _nearest_storage_for_agent(world, agent, village)
        if candidate_storage is None:
            _gate_fail("no_candidate_storage")
            _record_builder_self_supply_failure(world, "no_source_storage")
            continue
        _record_builder_self_supply_gate_stage(world, "candidate_storage_found", village_uid=village_uid)
        candidate_state = _ensure_storage_state(candidate_storage)
        if int(candidate_state.get(resource, 0)) <= 0:
            _gate_fail("candidate_storage_missing_resource")
            _record_builder_self_supply_failure(world, "no_source_storage")
            continue
        _record_builder_self_supply_gate_stage(world, "candidate_storage_has_resource", village_uid=village_uid)
        source = _nearest_storage_with_resource_for_agent(world, agent, village, resource)
        if source is None:
            _record_builder_self_supply_failure(world, "no_source_storage")
            _gate_fail("unknown_failure")
            continue
        storage_pos = (int(source.get("x", 0)), int(source.get("y", 0)))
        site_dist = _distance(storage_pos, (sx, sy))
        if site_dist > int(BUILDER_SELF_SUPPLY_MAX_SOURCE_DISTANCE):
            _record_builder_self_supply_failure(world, "source_too_far")
            _gate_fail("source_out_of_site_radius")
            continue
        _record_builder_self_supply_gate_stage(world, "source_within_site_radius", village_uid=village_uid)
        if _distance((int(agent.x), int(agent.y)), storage_pos) > 1:
            _record_builder_self_supply_failure(world, "source_not_in_range")
            _gate_fail("source_not_accessible_from_builder")
            continue
        _record_builder_self_supply_gate_stage(world, "source_accessible_from_builder", village_uid=village_uid)
        _record_builder_self_supply_gate_stage(world, "self_supply_pickup_attempt", village_uid=village_uid)
        storage_state = _ensure_storage_state(source)
        available = max(0, int(storage_state.get(resource, 0)))
        qty = min(need, available, capacity)
        if qty <= 0:
            _record_builder_self_supply_failure(world, "no_resource_available")
            _gate_fail("pickup_failed")
            continue
        storage_state[resource] = available - qty
        agent.inventory[resource] = int(agent.inventory.get(resource, 0)) + qty
        moved = _attach_carried_materials_to_site(agent, site, costs)
        if moved <= 0:
            _record_builder_self_supply_failure(world, "attach_failed")
            _gate_fail("pickup_failed")
            return False
        _sync_village_storage_cache(world, village)
        _mark_construction_site_demand_tick(world, site)
        if hasattr(world, "record_builder_self_supply_success"):
            world.record_builder_self_supply_success(site_dist)
        _record_builder_self_supply_gate_stage(world, "self_supply_pickup_success", village_uid=village_uid)
        _gate_fail("self_supply_succeeded")
        return True

    _record_builder_self_supply_failure(world, "no_local_viable_source")
    if not gate_failure_recorded:
        _gate_fail("unknown_failure")
    return False


def _find_matching_construction_site(
    world: "World",
    building_type: str,
    origin: Coord,
    village_id: Optional[int],
    village_uid: Optional[str],
) -> Optional[Dict[str, Any]]:
    ox, oy = origin
    for b in getattr(world, "buildings", {}).values():
        if b.get("type") != building_type:
            continue
        if b.get("operational_state") != "under_construction":
            continue
        if int(b.get("x", -1)) != int(ox) or int(b.get("y", -1)) != int(oy):
            continue
        if village_id is not None and b.get("village_id") != village_id:
            continue
        if village_id is None and village_uid is not None and b.get("village_uid") != village_uid:
            continue
        return b
    return None


def _find_existing_village_construction_site(
    world: "World",
    building_type: str,
    village_id: Optional[int],
    village_uid: Optional[str],
    *,
    agent_pos: Optional[Coord] = None,
) -> Optional[Dict[str, Any]]:
    sites = []
    for b in getattr(world, "buildings", {}).values():
        if b.get("type") != building_type:
            continue
        if b.get("operational_state") != "under_construction":
            continue
        if village_id is not None and b.get("village_id") != village_id:
            continue
        if village_id is None and village_uid is not None and b.get("village_uid") != village_uid:
            continue
        sites.append(b)
    if not sites:
        return None
    if agent_pos is not None:
        ax, ay = int(agent_pos[0]), int(agent_pos[1])
        sites.sort(
            key=lambda b: (
                _distance((ax, ay), (int(b.get("x", 0)), int(b.get("y", 0)))),
                str(b.get("building_id", "")),
            )
        )
    else:
        sites.sort(key=lambda b: str(b.get("building_id", "")))
    return sites[0]


def _create_construction_site(
    world: "World",
    building_type: str,
    origin: Coord,
    *,
    village_id: Optional[int],
    village_uid: Optional[str],
    costs: Dict[str, int],
) -> Optional[Dict[str, Any]]:
    site = place_building(
        world,
        building_type,
        origin,
        village_id=village_id,
        village_uid=village_uid,
        connected_to_road=False,
        operational_state="under_construction",
        construction_request=_construction_request_from_costs(costs),
        construction_buffer=_empty_construction_buffer(),
        construction_progress=0,
        construction_required_work=_construction_required_work(building_type),
    )
    if isinstance(site, dict):
        _mark_construction_site_demand_tick(world, site)
        if hasattr(world, "record_settlement_progression_metric"):
            world.record_settlement_progression_metric("construction_sites_created")
            if str(building_type) == "house":
                world.record_settlement_progression_metric("construction_sites_created_house")
            elif str(building_type) == "storage":
                world.record_settlement_progression_metric("construction_sites_created_storage")
        if str(building_type) == "house":
            _record_housing_stage(
                world,
                "house_site_created",
                village_uid=str(village_uid or ""),
                building_id=str(site.get("building_id", "")),
            )
            _record_housing_path(
                world,
                "house_created_via_construction_site",
                village_uid=str(village_uid or ""),
            )
    return site


def _complete_construction_site(world: "World", building: Dict[str, Any]) -> None:
    btype = str(building.get("type", ""))
    village_uid = str(building.get("village_uid", "") or "")
    bid = str(building.get("building_id", "") or "")
    if btype == "house":
        _record_housing_stage(
            world,
            "house_construction_completed",
            village_uid=village_uid,
            building_id=bid,
        )
    if hasattr(world, "record_settlement_progression_metric"):
        world.record_settlement_progression_metric("construction_completion_events")
    building["operational_state"] = "active"
    building.pop("construction_request", None)
    building.pop("construction_buffer", None)
    building.pop("construction_last_demand_tick", None)
    required = max(1, int(building.get("construction_required_work", 1)))
    building["construction_progress"] = required
    building["construction_required_work"] = required
    pos = (int(building.get("x", 0)), int(building.get("y", 0)))
    if building.get("type") == "house":
        world.structures.add(pos)
        _record_housing_stage(
            world,
            "house_building_activated",
            village_uid=village_uid,
            building_id=bid,
        )
        _record_housing_path(
            world,
            "house_activated_via_completion_hook",
            village_uid=village_uid,
        )
    elif building.get("type") == "storage":
        world.storage_buildings.add(pos)
        village_id = building.get("village_id")
        village = world.get_village_by_id(village_id) if village_id is not None else None
        _sync_village_storage_cache(world, village)
        if hasattr(world, "record_settlement_progression_build_event"):
            world.record_settlement_progression_build_event("storage", building)


def _construction_sites_for_village(world: "World", village: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if village is None:
        return []
    village_id = _village_id(village)
    village_uid = _village_uid(village)
    sites = []
    for b in getattr(world, "buildings", {}).values():
        if b.get("operational_state") != "under_construction":
            continue
        if village_id is not None and b.get("village_id") == village_id:
            sites.append(b)
            continue
        if village_uid is not None and b.get("village_uid") == village_uid:
            sites.append(b)
    sites.sort(key=lambda b: str(b.get("building_id", "")))
    return sites


def _pending_construction_type_for_village(world: "World", village: Optional[Dict[str, Any]]) -> Optional[str]:
    sites = _construction_sites_for_village(world, village)
    if not sites:
        return None
    ranked: List[Tuple[int, int, str, str]] = []
    for site in sites:
        btype = str(site.get("type", ""))
        if btype not in {"house", "storage"}:
            continue
        needs = get_outstanding_construction_needs(site)
        demand = int(needs.get("wood", 0)) + int(needs.get("stone", 0)) + int(needs.get("food", 0))
        waiting_tick = int(site.get("builder_waiting_tick", -1))
        ranked.append(
            (
                0 if demand > 0 else 1,
                -waiting_tick,
                str(site.get("building_id", "")),
                btype,
            )
        )
    if not ranked:
        return None
    ranked.sort(key=lambda row: (row[0], row[1], row[2], row[3]))
    return str(ranked[0][3])


def _remove_building_and_occupancy(world: "World", building_id: str) -> None:
    building = getattr(world, "buildings", {}).get(str(building_id))
    if not isinstance(building, dict):
        return
    footprint = building.get("footprint", [])
    if isinstance(footprint, list):
        for tile in footprint:
            if not isinstance(tile, dict):
                continue
            tx = int(tile.get("x", -1))
            ty = int(tile.get("y", -1))
            getattr(world, "building_occupancy", {}).pop((tx, ty), None)
    origin = (int(building.get("x", 0)), int(building.get("y", 0)))
    if str(building.get("type", "")) == "house":
        getattr(world, "structures", set()).discard(origin)
    elif str(building.get("type", "")) == "storage":
        getattr(world, "storage_buildings", set()).discard(origin)
        village = None
        vid = building.get("village_id")
        if vid is not None:
            village = world.get_village_by_id(vid)
        if village is not None:
            _sync_village_storage_cache(world, village)
    getattr(world, "buildings", {}).pop(str(building_id), None)


def clear_stale_construction_sites(world: "World", *, stale_ticks: int = CONSTRUCTION_SITE_STALE_TIMEOUT_TICKS) -> int:
    now = int(getattr(world, "tick", 0))
    timeout = max(1, int(stale_ticks))
    removed = 0

    def _record_abandonment_metrics(b: Dict[str, Any]) -> None:
        b_type = str(b.get("type", ""))
        if b_type == "storage" and hasattr(world, "record_settlement_progression_metric"):
            world.record_settlement_progression_metric("storage_construction_abandoned_count")
            village = None
            vid = b.get("village_id")
            if vid is not None and hasattr(world, "get_village_by_id"):
                village = world.get_village_by_id(vid)
            if village is None:
                vu = str(b.get("village_uid", ""))
                if vu:
                    village = next(
                        (v for v in getattr(world, "villages", []) if str(v.get("village_uid", "")) == vu),
                        None,
                    )
            if hasattr(world, "is_village_surplus_sustained"):
                try:
                    if world.is_village_surplus_sustained(village):
                        world.record_settlement_progression_metric("surplus_storage_abandoned")
                except Exception:
                    pass
        if hasattr(world, "record_settlement_progression_metric"):
            world.record_settlement_progression_metric("construction_abandonment_events")

    for building_id, building in list(getattr(world, "buildings", {}).items()):
        if not isinstance(building, dict):
            continue
        if str(building.get("operational_state", "")) != "under_construction":
            continue
        if str(building.get("type", "")) not in {"house", "storage"}:
            continue

        village_missing = building.get("village_id") is None and not str(building.get("village_uid", ""))
        if village_missing:
            _record_abandonment_metrics(building)
            _remove_building_and_occupancy(world, str(building_id))
            removed += 1
            continue

        last_tick_raw = building.get("construction_last_demand_tick")
        if last_tick_raw is None:
            building["construction_last_demand_tick"] = now
            continue
        try:
            idle_ticks = now - int(last_tick_raw)
        except Exception:
            building["construction_last_demand_tick"] = now
            continue
        if idle_ticks < timeout:
            continue

        progress = int(building.get("construction_progress", 0))
        req = building.get("construction_request", {})
        buf = building.get("construction_buffer", {})
        if not isinstance(req, dict) or not isinstance(buf, dict):
            _record_abandonment_metrics(building)
            _remove_building_and_occupancy(world, str(building_id))
            removed += 1
            continue
        reserved_total = int(req.get("wood_reserved", 0)) + int(req.get("stone_reserved", 0)) + int(req.get("food_reserved", 0))
        buffered_total = int(buf.get("wood", 0)) + int(buf.get("stone", 0)) + int(buf.get("food", 0))
        if progress > 0 or reserved_total > 0 or buffered_total > 0:
            continue

        _record_abandonment_metrics(building)
        _remove_building_and_occupancy(world, str(building_id))
        removed += 1
    return int(removed)


def _clear_hauler_delivery(agent: "Agent") -> None:
    if hasattr(agent, "delivery_target_building_id"):
        agent.delivery_target_building_id = None
    if hasattr(agent, "delivery_resource_type"):
        agent.delivery_resource_type = None
    if hasattr(agent, "delivery_reserved_amount"):
        agent.delivery_reserved_amount = 0
    if hasattr(agent, "delivery_commit_until_tick"):
        agent.delivery_commit_until_tick = -1


def _withdraw_resource_from_storage(
    world: "World",
    agent: "Agent",
    *,
    resource_type: str,
    amount: int,
) -> int:
    village = world.get_village_by_id(getattr(agent, "village_id", None))
    storage_building = _nearest_storage_with_resource_for_agent(
        world,
        agent,
        village,
        str(resource_type),
    )
    if storage_building is None:
        return 0
    sx = int(storage_building.get("x", 0))
    sy = int(storage_building.get("y", 0))
    if _distance((agent.x, agent.y), (sx, sy)) > 1:
        return 0
    storage = _ensure_storage_state(storage_building)
    want = max(0, int(amount))
    available = max(0, int(storage.get(resource_type, 0)))
    qty = min(want, available, max(0, int(getattr(agent, "inventory_space", lambda: 0)())))
    if qty <= 0:
        return 0
    storage[resource_type] = available - qty
    agent.inventory[resource_type] = int(agent.inventory.get(resource_type, 0)) + qty
    _sync_village_storage_cache(world, village)
    return qty


def run_hauler_construction_delivery(world: "World", agent: "Agent") -> bool:
    def _delivery_stage(stage: str, *, role: Optional[str] = None, village_uid: Optional[str] = None) -> None:
        if hasattr(world, "record_delivery_pipeline_stage"):
            world.record_delivery_pipeline_stage(agent, stage, role=role, village_uid=village_uid)

    def _delivery_fail(reason: str, *, role: Optional[str] = None, village_uid: Optional[str] = None) -> None:
        if hasattr(world, "record_delivery_pipeline_failure"):
            world.record_delivery_pipeline_failure(agent, reason, role=role, village_uid=village_uid)

    if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_attempt"):
        world.record_task_completion_attempt(agent, "construction_delivery")
    village = world.get_village_by_id(getattr(agent, "village_id", None))
    village_uid = str(village.get("village_uid", "")) if isinstance(village, dict) else ""
    if village is None:
        _clear_hauler_delivery(agent)
        _delivery_fail("no_delivery_target")
        _record_housing_failure(world, "no_delivery_target", village_uid=village_uid or None)
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "construction_delivery", "no_delivery_target")
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "hauler", "no_affiliated_village_context")
        return False

    target_id = getattr(agent, "delivery_target_building_id", None)
    resource_type = getattr(agent, "delivery_resource_type", None)
    reserved_amount = int(getattr(agent, "delivery_reserved_amount", 0) or 0)

    if not target_id or resource_type not in ("wood", "stone", "food") or reserved_amount <= 0:
        sites = _construction_sites_for_village(world, village)
        candidates: List[Tuple[int, int, int, int, int, str, str, int]] = []
        storage_totals = get_village_storage_totals(world, village)
        carrying_by_resource = {
            "wood": int(getattr(agent, "inventory", {}).get("wood", 0)),
            "stone": int(getattr(agent, "inventory", {}).get("stone", 0)),
            "food": int(getattr(agent, "inventory", {}).get("food", 0)),
        }
        for site in sites:
            needs = get_outstanding_construction_needs(site)
            for resource in ("wood", "stone", "food"):
                need = int(needs.get(resource, 0))
                if need <= 0:
                    continue
                available = int(storage_totals.get(resource, 0))
                carrying = int(carrying_by_resource.get(resource, 0))
                source = None
                source_dist = 9999
                if carrying <= 0:
                    source = _nearest_storage_with_resource_for_agent(world, agent, village, resource)
                    if source is not None:
                        source_dist = _distance((agent.x, agent.y), (int(source.get("x", 0)), int(source.get("y", 0))))
                if available <= 0 and carrying <= 0 and source is None:
                    continue
                sx = int(site.get("x", 0))
                sy = int(site.get("y", 0))
                dist = _distance((agent.x, agent.y), (sx, sy))
                carrying_priority = 0 if carrying > 0 else 1
                builder_wait_priority = 0 if _site_has_recent_builder_wait_signal(world, site) else 1
                local_delivery_bonus = 0
                if hasattr(world, "secondary_nucleus_delivery_priority"):
                    try:
                        local_delivery_bonus = int(world.secondary_nucleus_delivery_priority(agent, site))
                    except Exception:
                        local_delivery_bonus = 0
                if hasattr(world, "storage_delivery_priority_bonus"):
                    try:
                        local_delivery_bonus += int(world.storage_delivery_priority_bonus(agent, site))
                    except Exception:
                        pass
                candidates.append(
                    (
                        builder_wait_priority,
                        -int(local_delivery_bonus),
                        carrying_priority,
                        source_dist,
                        dist,
                        str(site.get("building_id", "")),
                        resource,
                        need,
                    )
                )
        if candidates:
            _delivery_stage("delivery_target_visible_count", village_uid=village_uid)
        if not candidates:
            carrying_any = int(getattr(agent, "inventory", {}).get("wood", 0)) + int(getattr(agent, "inventory", {}).get("stone", 0)) + int(
                getattr(agent, "inventory", {}).get("food", 0)
            )
            if carrying_any > 0 and hasattr(world, "record_settlement_progression_metric"):
                world.record_settlement_progression_metric("construction_material_delivery_drift_events")
            _clear_hauler_delivery(agent)
            fail_reason = "no_delivery_target" if not sites else "no_resource_available"
            _delivery_fail(fail_reason, village_uid=village_uid)
            _record_housing_failure(world, fail_reason, village_uid=village_uid or None)
            if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_failed"):
                world.record_task_completion_preconditions_failed(agent, "construction_delivery", "no_delivery_target")
            if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
                if not sites:
                    world.record_workforce_block_reason(agent, "hauler", "no_construction_site")
                else:
                    world.record_workforce_block_reason(agent, "hauler", "no_materials_available")
            return False
        candidates.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4], x[5], x[6]))
        _, local_bonus_key, _, _, _, bid, resource_type, need = candidates[0]
        if int(local_bonus_key) < 0 and hasattr(world, "secondary_nucleus_delivery_priority"):
            try:
                selected_site = getattr(world, "buildings", {}).get(str(bid))
                if isinstance(selected_site, dict):
                    world.secondary_nucleus_delivery_priority(agent, selected_site, record_event=True)
            except Exception:
                pass
        if int(local_bonus_key) < 0 and hasattr(world, "storage_delivery_priority_bonus"):
            try:
                selected_site = getattr(world, "buildings", {}).get(str(bid))
                if isinstance(selected_site, dict):
                    world.storage_delivery_priority_bonus(agent, selected_site, record_event=True)
            except Exception:
                pass
        _delivery_stage("delivery_target_created_count", village_uid=village_uid)
        selected_site = getattr(world, "buildings", {}).get(str(bid))
        is_house_target = isinstance(selected_site, dict) and str(selected_site.get("type", "")) == "house"
        if is_house_target:
            _record_housing_stage(
                world,
                "house_delivery_target_created",
                village_uid=village_uid or None,
                building_id=str(bid),
            )
            _record_housing_worker(world, "hauler_assigned_house_delivery", village_uid=village_uid or None)
        reserve_cap = min(int(need), int(getattr(agent, "max_inventory", 0)))
        reserved = reserve_materials_for_construction(world, bid, resource_type, reserve_cap)
        if reserved <= 0:
            _clear_hauler_delivery(agent)
            _delivery_fail("reservation_lost", village_uid=village_uid)
            if is_house_target:
                _record_housing_failure(world, "hauler_reassigned", village_uid=village_uid or None)
            if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_failed"):
                world.record_task_completion_preconditions_failed(agent, "construction_delivery", "no_reserved_delivery")
            if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
                world.record_workforce_block_reason(agent, "hauler", "waiting_on_delivery")
            return False
        _delivery_stage("delivery_target_reserved_count", village_uid=village_uid)
        if is_house_target:
            _record_housing_stage(
                world,
                "house_delivery_reserved",
                village_uid=village_uid or None,
                building_id=str(bid),
            )
        agent.delivery_target_building_id = bid
        agent.delivery_resource_type = resource_type
        agent.delivery_reserved_amount = int(reserved)
        agent.delivery_chain_started_tick = int(getattr(world, "tick", 0))
        agent.delivery_commit_until_tick = int(getattr(world, "tick", 0)) + int(DELIVERY_COMMIT_TICKS)
        if isinstance(selected_site, dict):
            _mark_construction_site_demand_tick(world, selected_site)
        target_id = bid
        reserved_amount = int(reserved)

    site = getattr(world, "buildings", {}).get(str(target_id))
    site_is_house = isinstance(site, dict) and str(site.get("type", "")) == "house"
    if not isinstance(site, dict) or site.get("operational_state") != "under_construction":
        _clear_hauler_delivery(agent)
        fail_reason = "site_invalidated"
        if isinstance(site, dict) and str(site.get("operational_state", "")) == "active":
            fail_reason = "construction_completed_before_delivery"
        _delivery_fail(fail_reason, village_uid=village_uid)
        if site_is_house:
            _record_housing_failure(world, "site_invalidated", village_uid=village_uid or None)
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "construction_delivery", "invalid_site_state")
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "hauler", "no_construction_site")
        return False
    _delivery_stage("delivery_target_visible_count", village_uid=village_uid)
    resource_type = str(getattr(agent, "delivery_resource_type", ""))
    reserved_amount = int(getattr(agent, "delivery_reserved_amount", 0))
    if reserved_amount <= 0:
        _clear_hauler_delivery(agent)
        _delivery_fail("reservation_lost", village_uid=village_uid)
        if site_is_house:
            _record_housing_failure(world, "hauler_reassigned", village_uid=village_uid or None)
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "construction_delivery", "no_reserved_delivery")
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "hauler", "waiting_on_delivery")
        return False
    agent.delivery_commit_until_tick = int(getattr(world, "tick", 0)) + int(DELIVERY_COMMIT_TICKS)

    carrying = int(agent.inventory.get(resource_type, 0))
    if carrying <= 0:
        _delivery_stage("resource_pickup_attempt_count", village_uid=village_uid)
        source_storage = _nearest_storage_with_resource_for_agent(world, agent, village, resource_type)
        if source_storage is None:
            _delivery_fail("no_source_storage", village_uid=village_uid)
            if site_is_house:
                _record_housing_failure(world, "no_source_storage", village_uid=village_uid or None)
            if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
                world.record_workforce_block_reason(agent, "hauler", "no_materials_available")
                if hasattr(world, "record_task_completion_preconditions_failed"):
                    world.record_task_completion_preconditions_failed(agent, "construction_delivery", "no_resource_available")
            return False
        _delivery_stage("resource_source_found_count", village_uid=village_uid)
        taken = _withdraw_resource_from_storage(
            world,
            agent,
            resource_type=resource_type,
            amount=reserved_amount,
        )
        if taken > 0 and str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_met"):
            world.record_task_completion_preconditions_met(agent, "construction_delivery")
            _delivery_stage("resource_pickup_success_count", village_uid=village_uid)
            _delivery_stage("hauler_departed_with_resource_count", village_uid=village_uid)
            if site_is_house:
                _record_housing_worker(world, "hauler_pickup_house_material", village_uid=village_uid or None)
            agent.delivery_commit_until_tick = int(getattr(world, "tick", 0)) + int(DELIVERY_COMMIT_TICKS)
        if taken <= 0 and str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "hauler", "no_materials_available")
            if hasattr(world, "record_task_completion_preconditions_failed"):
                world.record_task_completion_preconditions_failed(agent, "construction_delivery", "no_resource_available")
            source_state = _ensure_storage_state(source_storage)
            if int(source_state.get(resource_type, 0)) <= 0:
                _delivery_fail("no_resource_available", village_uid=village_uid)
                if site_is_house:
                    _record_housing_failure(world, "no_resource_available", village_uid=village_uid or None)
            elif _distance((agent.x, agent.y), (int(source_storage.get("x", 0)), int(source_storage.get("y", 0)))) > 1:
                _delivery_fail("path_failed", village_uid=village_uid)
                if site_is_house:
                    _record_housing_failure(world, "path_failed", village_uid=village_uid or None)
            else:
                _delivery_fail("unknown_failure", village_uid=village_uid)
                if site_is_house:
                    _record_housing_failure(world, "site_invalidated", village_uid=village_uid or None)
        return taken > 0
    _delivery_stage("hauler_departed_with_resource_count", village_uid=village_uid)

    sx = int(site.get("x", 0))
    sy = int(site.get("y", 0))
    if _distance((agent.x, agent.y), (sx, sy)) > 1:
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "construction_delivery", "target_not_in_range")
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "hauler", "no_target_found")
        _delivery_fail("site_not_in_range", village_uid=village_uid)
        if site_is_house:
            _record_housing_failure(world, "site_invalidated", village_uid=village_uid or None)
        return False
    _delivery_stage("site_arrival_count", village_uid=village_uid)
    if site_is_house:
        _record_housing_worker(world, "hauler_arrived_house", village_uid=village_uid or None)

    deliver_amount = min(carrying, reserved_amount)
    _delivery_stage("delivery_attempt_count", village_uid=village_uid)
    if site_is_house:
        _record_housing_stage(
            world,
            "house_delivery_attempt",
            village_uid=village_uid or None,
            building_id=str(target_id),
        )
    fulfilled = fulfill_reserved_delivery(world, str(target_id), resource_type, deliver_amount)
    if fulfilled <= 0:
        _clear_hauler_delivery(agent)
        _delivery_fail("reservation_lost", village_uid=village_uid)
        if site_is_house:
            _record_housing_failure(world, "hauler_reassigned", village_uid=village_uid or None)
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "construction_delivery", "no_reserved_delivery")
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "hauler", "waiting_on_delivery")
        return False
    agent.inventory[resource_type] = carrying - fulfilled
    agent.delivery_reserved_amount = max(0, reserved_amount - fulfilled)
    if int(agent.delivery_reserved_amount) <= 0:
        _clear_hauler_delivery(agent)
    if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_met"):
        world.record_task_completion_preconditions_met(agent, "construction_delivery")
        world.record_task_completion_productive(agent, "construction_delivery")
    _delivery_stage("delivery_success_count", village_uid=village_uid)
    if site_is_house:
        _record_housing_stage(
            world,
            "house_delivery_success",
            village_uid=village_uid or None,
            building_id=str(target_id),
        )
        _record_housing_worker(world, "hauler_delivery_success", village_uid=village_uid or None)
    agent.delivery_commit_until_tick = int(getattr(world, "tick", 0)) + int(DELIVERY_COMMIT_TICKS)
    if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_productive_action"):
        world.record_workforce_productive_action(agent, "hauler", "construction_delivery")
    if hasattr(world, "emit_event"):
        world.emit_event(
            "delivered_material",
            {
                "agent_id": str(getattr(agent, "agent_id", "")),
                "building_id": str(target_id),
                "resource_type": str(resource_type),
                "amount": int(fulfilled),
                "outcome": "success",
            },
        )
    _mark_construction_site_demand_tick(world, site)
    if hasattr(world, "record_settlement_progression_metric"):
        world.record_settlement_progression_metric("construction_material_delivery_events", int(fulfilled))
        if int(site.get("construction_progress", 0)) > 0 or _site_has_recent_builder_wait_signal(world, site):
            world.record_settlement_progression_metric("construction_material_delivery_to_active_site", int(fulfilled))
    if str(site.get("type", "")) == "storage" and hasattr(world, "record_settlement_progression_metric"):
        world.record_settlement_progression_metric("storage_material_delivery_events", int(fulfilled))
    return True


def _record_internal_transfer_metric(village: Optional[Dict[str, Any]], resource_type: str, amount: int) -> None:
    if village is None or amount <= 0:
        return
    metrics = village.get("logistics_metrics")
    if not isinstance(metrics, dict):
        metrics = {
            "internal_transfers_count": 0,
            "redistributed_wood": 0,
            "redistributed_stone": 0,
            "redistributed_food": 0,
        }
        village["logistics_metrics"] = metrics
    metrics["internal_transfers_count"] = int(metrics.get("internal_transfers_count", 0)) + 1
    if resource_type == "wood":
        metrics["redistributed_wood"] = int(metrics.get("redistributed_wood", 0)) + int(amount)
    elif resource_type == "stone":
        metrics["redistributed_stone"] = int(metrics.get("redistributed_stone", 0)) + int(amount)
    elif resource_type == "food":
        metrics["redistributed_food"] = int(metrics.get("redistributed_food", 0)) + int(amount)


def run_hauler_internal_redistribution(world: "World", agent: "Agent") -> bool:
    if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_attempt"):
        world.record_task_completion_attempt(agent, "internal_transfer")
    village = world.get_village_by_id(getattr(agent, "village_id", None))
    if village is None:
        _clear_internal_transfer(agent)
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "internal_transfer", "no_delivery_target")
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "hauler", "no_affiliated_village_context")
        return False

    source_id = getattr(agent, "transfer_source_storage_id", None)
    target_id = getattr(agent, "transfer_target_storage_id", None)
    resource_type = str(getattr(agent, "transfer_resource_type", ""))
    transfer_amount = int(getattr(agent, "transfer_amount", 0) or 0)

    if not source_id or not target_id or resource_type not in {"food", "wood", "stone"} or transfer_amount <= 0:
        selected = None
        for resource in ("wood", "stone", "food"):
            candidates = find_storage_transfer_candidates(world, village, resource)
            if not candidates:
                continue
            ranked = []
            for sbid, tbid, qty in candidates:
                sb = _storage_by_id(world, sbid)
                tb = _storage_by_id(world, tbid)
                if sb is None or tb is None:
                    continue
                sdist = _distance((agent.x, agent.y), (int(sb.get("x", 0)), int(sb.get("y", 0))))
                tdist = _distance((agent.x, agent.y), (int(tb.get("x", 0)), int(tb.get("y", 0))))
                ranked.append((sdist + tdist, sbid, tbid, qty))
            if ranked:
                ranked.sort(key=lambda x: (x[0], x[1], x[2]))
                _, sbid, tbid, qty = ranked[0]
                selected = (resource, sbid, tbid, qty)
                break
        if selected is None:
            _clear_internal_transfer(agent)
            if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_failed"):
                world.record_task_completion_preconditions_failed(agent, "internal_transfer", "no_delivery_target")
            if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
                world.record_workforce_block_reason(agent, "hauler", "no_valid_task")
            return False
        resource_type, source_id, target_id, transfer_amount = selected
        agent.transfer_resource_type = str(resource_type)
        agent.transfer_source_storage_id = str(source_id)
        agent.transfer_target_storage_id = str(target_id)
        agent.transfer_amount = int(transfer_amount)

    source = _storage_by_id(world, str(source_id))
    target = _storage_by_id(world, str(target_id))
    if source is None or target is None or source.get("village_id") != target.get("village_id"):
        _clear_internal_transfer(agent)
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "internal_transfer", "no_target_storage")
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "hauler", "task_conflict")
        return False

    carrying = int(agent.inventory.get(resource_type, 0))
    if carrying <= 0:
        sx, sy = int(source.get("x", 0)), int(source.get("y", 0))
        if _distance((agent.x, agent.y), (sx, sy)) > 1:
            if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_failed"):
                world.record_task_completion_preconditions_failed(agent, "internal_transfer", "target_not_in_range")
            if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
                world.record_workforce_block_reason(agent, "hauler", "no_target_found")
            return False
        storage = _ensure_storage_state(source)
        available = int(storage.get(resource_type, 0))
        qty = min(
            max(0, transfer_amount),
            max(0, available),
            max(0, int(getattr(agent, "inventory_space", lambda: 0)())),
        )
        if qty <= 0:
            _clear_internal_transfer(agent)
            if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_failed"):
                world.record_task_completion_preconditions_failed(agent, "internal_transfer", "no_resource_available")
            if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
                world.record_workforce_block_reason(agent, "hauler", "no_materials_available")
            return False
        storage[resource_type] = available - qty
        agent.inventory[resource_type] = int(agent.inventory.get(resource_type, 0)) + qty
        _sync_village_storage_cache(world, village)
        return True

    tx, ty = int(target.get("x", 0)), int(target.get("y", 0))
    if _distance((agent.x, agent.y), (tx, ty)) > 1:
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "internal_transfer", "target_not_in_range")
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "hauler", "no_target_found")
        return False
    target_storage = _ensure_storage_state(target)
    cap = int(target.get("storage_capacity", STORAGE_BUILDING_CAPACITY))
    free = max(0, cap - _storage_load(target))
    qty = min(carrying, max(0, transfer_amount), free)
    if qty <= 0:
        _clear_internal_transfer(agent)
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "internal_transfer", "no_target_storage")
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "hauler", "no_storage_available")
        return False
    target_storage[resource_type] = int(target_storage.get(resource_type, 0)) + qty
    agent.inventory[resource_type] = carrying - qty
    _sync_village_storage_cache(world, village)
    _record_internal_transfer_metric(village, resource_type, qty)
    _clear_internal_transfer(agent)
    if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_met"):
        world.record_task_completion_preconditions_met(agent, "internal_transfer")
        world.record_task_completion_productive(agent, "internal_transfer")
    if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_productive_action"):
        world.record_workforce_productive_action(agent, "hauler", "internal_transfer")
    return True


def building_score(world: "World", x: int, y: int) -> int:
    score = 0

    for dx in range(-2, 3):
        for dy in range(-2, 3):
            nx = x + dx
            ny = y + dy
            if (nx, ny) in world.structures:
                score += 5

    for dx in range(-3, 4):
        for dy in range(-3, 4):
            nx = x + dx
            ny = y + dy
            if 0 <= nx < world.width and 0 <= ny < world.height:
                if world.tiles[ny][nx] == "F":
                    score += 1

    return score


def count_nearby_houses(world: "World", x: int, y: int, radius: int = 5) -> int:
    count = 0
    for hx, hy in world.structures:
        if abs(hx - x) <= radius and abs(hy - y) <= radius:
            count += 1
    return count


def count_nearby_population(world: "World", x: int, y: int, radius: int = 6) -> int:
    count = 0
    for a in world.agents:
        if not a.alive:
            continue
        if abs(a.x - x) <= radius and abs(a.y - y) <= radius:
            count += 1
    return count


def can_build_at(world: "World", x: int, y: int) -> bool:
    return can_place_building(world, "house", (x, y))


def try_build_house(world: "World", agent: "Agent") -> bool:
    village_id = getattr(agent, "village_id", None)
    resolved_village_uid = world.resolve_village_uid(village_id) if hasattr(world, "resolve_village_uid") else None
    village_uid = str(resolved_village_uid or "")
    _record_housing_stage(world, "house_plan_requested", village_uid=village_uid or None)
    if str(getattr(agent, "role", "")) == "builder":
        _record_housing_worker(world, "builder_assigned_to_house", village_uid=village_uid or None)
    if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_attempt"):
        world.record_task_completion_attempt(agent, "build_house")
    if len(world.structures) >= world.MAX_STRUCTURES:
        _record_housing_failure(world, "village_not_viable", village_uid=village_uid or None)
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "build_house", "construction_already_complete")
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "builder", "no_valid_task")
        return False

    best_pos: Optional[Coord] = None
    best_score = -10**9
    bootstrap_mode = getattr(agent, "village_id", None) is None

    anchor: Optional[Coord] = None
    if bootstrap_mode and getattr(agent, "founder", False):
        target = getattr(agent, "task_target", None)
        if isinstance(target, tuple) and len(target) == 2:
            anchor = target
        elif getattr(world, "founding_hub", None) is not None:
            anchor = world.founding_hub

    village = world.get_village_by_id(village_id)
    if not bootstrap_mode and village is None:
        _record_housing_failure(world, "village_not_viable", village_uid=village_uid or None)

    def _house_count_for_village() -> int:
        if village is None:
            return 0
        vid = village.get("id")
        vuid = str(village.get("village_uid", "") or "")
        count = 0
        for b in getattr(world, "buildings", {}).values():
            if not isinstance(b, dict):
                continue
            if str(b.get("type", "")) != "house":
                continue
            if vid is not None and b.get("village_id") == vid:
                count += 1
                continue
            buid = str(b.get("village_uid", "") or "")
            if vuid and buid == vuid:
                count += 1
        return count

    village_house_count = _house_count_for_village()
    early_housing_mode = bool(
        village is not None
        and not bootstrap_mode
        and village_house_count < 3
        and int(village.get("houses", 0)) < 3
    )

    existing_site: Optional[Dict[str, Any]] = None
    if village is not None:
        existing_site = _find_existing_village_construction_site(
            world,
            "house",
            getattr(agent, "village_id", None),
            world.resolve_village_uid(getattr(agent, "village_id", None)),
            agent_pos=(int(agent.x), int(agent.y)),
        )
    if existing_site is not None:
        best_pos = (int(existing_site.get("x", 0)), int(existing_site.get("y", 0)))
    else:
        _record_housing_siting_stage(world, "house_candidate_scan_started", village_uid=village_uid or None)

        def _candidate_rejection_reason(x: int, y: int, *, relaxed: bool) -> Optional[str]:
            tiles = footprint_tiles("house", (x, y))
            if not tiles:
                return "invalid_house_footprint"
            for tx, ty in tiles:
                if not (0 <= tx < world.width and 0 <= ty < world.height):
                    return "invalid_house_footprint"
                tile = str(world.tiles[ty][tx]) if 0 <= ty < len(world.tiles) and 0 <= tx < len(world.tiles[ty]) else ""
                if tile in {"W", "M"}:
                    return "terrain_invalid"
                if not world.is_walkable(tx, ty):
                    return "non_walkable"
                if world.is_tile_blocked_by_building(tx, ty):
                    return "overlap_with_structure"
            if (int(x), int(y)) in getattr(world, "roads", set()):
                return "blocked_by_road"

            nearby_houses = count_nearby_houses(world, x, y, radius=5)
            connected_houses = count_nearby_houses(world, x, y, radius=4)
            nearby_population = count_nearby_population(world, x, y, radius=6)

            if nearby_houses >= world.MAX_HOUSES_PER_VILLAGE:
                return "village_cap_block"
            allowed_houses = nearby_population // 2 + 1
            if not relaxed and nearby_houses >= allowed_houses:
                return "too_dense"
            if relaxed and nearby_houses >= max(2, allowed_houses + 1):
                return "too_dense"

            if nearby_houses == 0 and len(world.structures) >= world.MAX_NEW_VILLAGE_SEEDS and not relaxed:
                return "village_cap_block"
            if bootstrap_mode and len(world.structures) > 0 and connected_houses == 0:
                return "reserved_space_block"
            if anchor is not None:
                d_anchor = abs(anchor[0] - x) + abs(anchor[1] - y)
                if d_anchor > 8:
                    return "too_far_from_anchor"
            return None

        def _candidate_score(x: int, y: int, *, relaxed: bool) -> Optional[int]:
            rejection = _candidate_rejection_reason(x, y, relaxed=relaxed)
            if rejection is not None:
                _record_housing_siting_rejection(world, rejection, village_uid=village_uid or None)
                return None
            nearby_houses = count_nearby_houses(world, x, y, radius=5)
            connected_houses = count_nearby_houses(world, x, y, radius=4)
            nearby_population = count_nearby_population(world, x, y, radius=6)

            score = building_score(world, x, y)
            score += connected_houses * 8
            score += min(18, nearby_houses * 4)
            if nearby_houses == 0:
                score -= 10

            if anchor is not None:
                d_anchor = abs(anchor[0] - x) + abs(anchor[1] - y)
                if d_anchor > 8:
                    return None
                score += max(0, 36 - d_anchor * 4)

            if village is not None:
                score += score_building_position(world, village, "house", (x, y))
                center = village.get("center", {}) if isinstance(village.get("center"), dict) else {}
                cx = int(center.get("x", x))
                cy = int(center.get("y", y))
                # Early mode prefers "good enough" near-center sites.
                if relaxed:
                    score += max(0, 24 - (_distance((x, y), (cx, cy)) * 3))
            if hasattr(world, "secondary_nucleus_materialization_signals"):
                try:
                    nucleus = world.secondary_nucleus_materialization_signals(x, y)
                except Exception:
                    nucleus = {}
                if isinstance(nucleus, dict) and bool(nucleus.get("has_camp", False)):
                    camp_pos = nucleus.get("camp_pos", (x, y))
                    d_camp = abs(int(camp_pos[0]) - int(x)) + abs(int(camp_pos[1]) - int(y))
                    score += max(0, 24 - d_camp * 3)
                    if bool(nucleus.get("viable", False)):
                        score += 6
            if hasattr(world, "secondary_nucleus_build_position_bonus"):
                try:
                    score += int(world.secondary_nucleus_build_position_bonus(agent, (x, y), "house"))
                except Exception:
                    pass

            _record_housing_siting_stage(world, "house_candidate_passed_all_checks", village_uid=village_uid or None)
            return int(score)

        for dx in range(-3, 4):
            for dy in range(-3, 4):
                x = agent.x + dx
                y = agent.y + dy
                _record_housing_siting_stage(world, "house_candidate_evaluated", village_uid=village_uid or None)
                score = _candidate_score(x, y, relaxed=False)
                if score is None:
                    continue
                if score > best_score:
                    best_score = score
                    best_pos = (x, y)

        # Early-housing mode: expand deterministic local search around village anchors.
        if best_pos is None and early_housing_mode and village is not None:
            anchors: List[Coord] = []
            center = village.get("center", {}) if isinstance(village.get("center"), dict) else {}
            if "x" in center and "y" in center:
                anchors.append((int(center["x"]), int(center["y"])))
            storage_pos = village.get("storage_pos", {}) if isinstance(village.get("storage_pos"), dict) else {}
            if "x" in storage_pos and "y" in storage_pos:
                anchors.append((int(storage_pos["x"]), int(storage_pos["y"])))
            anchors.append((int(agent.x), int(agent.y)))
            seen: Set[Coord] = set()
            ordered_anchors = [a for a in anchors if not (a in seen or seen.add(a))]
            for anchor_pos in ordered_anchors:
                for pos in _iter_diamond(anchor_pos, 6):
                    x, y = int(pos[0]), int(pos[1])
                    if not (0 <= x < world.width and 0 <= y < world.height):
                        _record_housing_siting_stage(world, "house_candidate_evaluated", village_uid=village_uid or None)
                        _record_housing_siting_rejection(world, "invalid_house_footprint", village_uid=village_uid or None)
                        continue
                    _record_housing_siting_stage(world, "house_candidate_evaluated", village_uid=village_uid or None)
                    score = _candidate_score(x, y, relaxed=True)
                    if score is None:
                        continue
                    if score > best_score:
                        best_score = score
                        best_pos = (x, y)

    if best_pos is None:
        _record_housing_failure(world, "no_build_location", village_uid=village_uid or None)
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "build_house", "no_construction_site")
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "builder", "no_target_found")
        return False

    if bootstrap_mode:
        if not _can_pay(world, agent, HOUSE_WOOD_COST, HOUSE_STONE_COST):
            _record_housing_failure(world, "materials_missing", village_uid=village_uid or None)
            return False
        result = try_build_type(
            world,
            agent,
            "house",
            village_id=getattr(agent, "village_id", None),
            village_uid=world.resolve_village_uid(getattr(agent, "village_id", None)),
            preferred_anchors=[best_pos],
            search_radius=0,
        )
        if not result["success"]:
            _record_housing_failure(world, "terrain_invalid", village_uid=village_uid or None)
            return False
        _pay(world, agent, HOUSE_WOOD_COST, HOUSE_STONE_COST)
        agent.home_building_id = str(result.get("building_id"))
        agent.home_village_uid = world.resolve_village_uid(getattr(agent, "village_id", None))
        world.emit_event(
            "house_built",
            {
                "agent_id": agent.agent_id,
                "x": result["position"]["x"],
                "y": result["position"]["y"],
                "village_uid": world.resolve_village_uid(getattr(agent, "village_id", None)),
            },
        )
        bid = str(result.get("building_id", ""))
        _record_housing_path(world, "house_created_via_bootstrap", village_uid=village_uid or None)
        _record_housing_stage(world, "house_construction_completed", village_uid=village_uid or None, building_id=bid)
        _record_housing_stage(world, "house_building_activated", village_uid=village_uid or None, building_id=bid)
        return True

    village_uid = world.resolve_village_uid(village_id)
    costs = _construction_costs("house")
    site = _find_matching_construction_site(world, "house", best_pos, village_id, village_uid)
    site_was_new = False
    if site is None:
        site = _create_construction_site(
            world,
            "house",
            best_pos,
            village_id=village_id,
            village_uid=village_uid,
            costs=costs,
        )
        site_was_new = isinstance(site, dict)
    if site is None:
        _record_housing_failure(world, "terrain_invalid", village_uid=village_uid)
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "build_house", "no_construction_site")
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "builder", "no_construction_site")
        return False
    if site_was_new:
        _record_housing_siting_stage(world, "house_site_created", village_uid=village_uid)
    _record_housing_stage(
        world,
        "house_site_visible_to_workers",
        village_uid=village_uid,
        building_id=str(site.get("building_id", "")),
    )
    needs_now = get_outstanding_construction_needs(site)
    if int(needs_now.get("wood", 0)) + int(needs_now.get("stone", 0)) + int(needs_now.get("food", 0)) > 0:
        _record_housing_stage(
            world,
            "house_material_requirement_detected",
            village_uid=village_uid,
            building_id=str(site.get("building_id", "")),
        )
    if not _agent_is_situated_on_site(agent, site):
        if hasattr(world, "record_situated_construction_event"):
            world.record_situated_construction_event("construction_offsite_blocked_ticks")
            world.record_situated_construction_event("construction_interrupted_invalid_target")
        _record_housing_failure(world, "site_invalidated", village_uid=village_uid)
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "build_house", "site_not_in_range")
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "builder", "no_target_found")
        return False
    _record_housing_worker(world, "builder_arrived_at_house", village_uid=village_uid)
    _mark_construction_site_demand_tick(world, site)
    _attach_carried_materials_to_site(agent, site, costs)
    if not _site_ready_for_completion(site, costs):
        if _try_builder_local_self_supply(world, agent, site, costs, village=village):
            return False
        _mark_builder_waiting_on_site(world, site, agent)
        if int(getattr(agent, "hunger", 100)) < 20:
            _record_housing_failure(world, "builder_starving", village_uid=village_uid)
        else:
            _record_housing_failure(world, "materials_missing", village_uid=village_uid)
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "build_house", "waiting_on_delivery")
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "builder", "waiting_on_delivery")
        return False
    if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_preconditions_met"):
        world.record_task_completion_preconditions_met(agent, "build_house")
        world.record_task_completion_preconditions_met(agent, "construction_progress")
    if hasattr(world, "record_situated_construction_event"):
        world.record_situated_construction_event("construction_on_site_work_ticks")
    _advance_construction_progress(site)
    if hasattr(world, "record_settlement_progression_metric"):
        world.record_settlement_progression_metric("construction_progress_ticks")
    _record_housing_stage(
        world,
        "house_construction_progress_tick",
        village_uid=village_uid,
        building_id=str(site.get("building_id", "")),
    )
    _record_housing_worker(world, "builder_progress_events", village_uid=village_uid)
    _mark_construction_site_demand_tick(world, site)
    if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_productive"):
        world.record_task_completion_productive(agent, "construction_progress")
    if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_workforce_productive_action"):
        world.record_workforce_productive_action(agent, "builder", "construction_progress")
    if hasattr(world, "emit_event"):
        world.emit_event(
            "construction_progress",
            {
                "agent_id": str(getattr(agent, "agent_id", "")),
                "building_id": str(site.get("building_id", "")),
                "building_type": "house",
                "outcome": "success",
            },
        )
    if not _site_work_complete(site):
        return False
    _record_housing_path(world, "house_completed_via_construction_progress", village_uid=village_uid)
    if not _use_construction_buffer(site, costs):
        _record_housing_failure(world, "materials_missing", village_uid=village_uid)
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "build_house", "no_materials_in_buffer")
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "builder", "waiting_on_delivery")
        return False
    _complete_construction_site(world, site)
    if str(site.get("operational_state", "")) != "active":
        _record_housing_failure(world, "construction_completed_not_activated", village_uid=village_uid)
        _record_housing_failure(world, "activation_state_mismatch", village_uid=village_uid)
    agent.home_building_id = str(site.get("building_id", ""))
    agent.home_village_uid = village_uid
    world.emit_event(
        "house_built",
        {
            "agent_id": agent.agent_id,
            "x": int(site.get("x", 0)),
            "y": int(site.get("y", 0)),
            "village_uid": village_uid,
        },
    )
    if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_productive"):
        world.record_task_completion_productive(agent, "build_house")
    return True


def try_build_storage(world: "World", agent: "Agent") -> bool:
    if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_attempt"):
        world.record_task_completion_attempt(agent, "build_storage")
    village_id = getattr(agent, "village_id", None)
    village = world.get_village_by_id(village_id)
    if village is None:
        if hasattr(world, "record_settlement_progression_metric"):
            world.record_settlement_progression_metric("storage_construction_interrupted_invalid")
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "build_storage", "invalid_site_state")
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "builder", "no_affiliated_village_context")
        return False

    storage_pos = village.get("storage_pos")
    if not storage_pos:
        replacement = _find_nearest_storage_spot(world, village, (int(agent.x), int(agent.y)))
        if replacement is None:
            if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_preconditions_failed"):
                world.record_task_completion_preconditions_failed(agent, "build_storage", "no_construction_site")
            if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_workforce_block_reason"):
                world.record_workforce_block_reason(agent, "builder", "no_target_found")
            return False
        sx, sy = replacement
        village["storage_pos"] = {"x": int(sx), "y": int(sy)}
    else:
        sx = int(storage_pos["x"])
        sy = int(storage_pos["y"])

    if (sx, sy) in getattr(world, "storage_buildings", set()):
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "build_storage", "construction_already_complete")
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "builder", "no_valid_task")
        return False

    existing_site = _find_existing_village_construction_site(
        world,
        "storage",
        village_id,
        world.resolve_village_uid(village_id),
        agent_pos=(int(agent.x), int(agent.y)),
    )
    if existing_site is not None:
        sx = int(existing_site.get("x", sx))
        sy = int(existing_site.get("y", sy))
        village["storage_pos"] = {"x": int(sx), "y": int(sy)}
    if existing_site is None and not can_place_building(world, "storage", (sx, sy)):
        replacement = _find_nearest_storage_spot(world, village, (agent.x, agent.y))
        if replacement is None:
            if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_preconditions_failed"):
                world.record_task_completion_preconditions_failed(agent, "build_storage", "no_construction_site")
            if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_workforce_block_reason"):
                world.record_workforce_block_reason(agent, "builder", "no_target_found")
            return False
        sx, sy = replacement
        village["storage_pos"] = {"x": sx, "y": sy}

    if _distance((int(agent.x), int(agent.y)), (int(sx), int(sy))) > int(CONSTRUCTION_WORK_RANGE):
        if hasattr(world, "record_settlement_progression_metric"):
            world.record_settlement_progression_metric("storage_construction_interrupted_invalid")
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "build_storage", "site_not_in_range")
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "builder", "no_target_found")
        return False

    if existing_site is None and not can_place_building(world, "storage", (sx, sy)):
        if hasattr(world, "record_settlement_progression_metric"):
            world.record_settlement_progression_metric("storage_construction_interrupted_invalid")
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "build_storage", "invalid_site_state")
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "builder", "no_construction_site")
        return False

    costs = _construction_costs("storage")
    site = existing_site
    if site is None:
        site = _create_construction_site(
            world,
            "storage",
            (sx, sy),
            village_id=village_id,
            village_uid=world.resolve_village_uid(village_id),
            costs=costs,
        )
    if site is None:
        if hasattr(world, "record_settlement_progression_metric"):
            world.record_settlement_progression_metric("storage_construction_interrupted_invalid")
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "build_storage", "no_construction_site")
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "builder", "no_construction_site")
        return False
    if not _agent_is_situated_on_site(agent, site):
        if hasattr(world, "record_settlement_progression_metric"):
            world.record_settlement_progression_metric("storage_construction_interrupted_invalid")
        if hasattr(world, "record_situated_construction_event"):
            world.record_situated_construction_event("construction_offsite_blocked_ticks")
            world.record_situated_construction_event("construction_interrupted_invalid_target")
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "build_storage", "site_not_in_range")
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "builder", "no_target_found")
        return False
    _mark_construction_site_demand_tick(world, site)
    _attach_carried_materials_to_site(agent, site, costs)
    if not _site_ready_for_completion(site, costs):
        if _try_builder_local_self_supply(world, agent, site, costs, village=village):
            return False
        _mark_builder_waiting_on_site(world, site, agent)
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "build_storage", "waiting_on_delivery")
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "builder", "waiting_on_delivery")
        return False
    if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_preconditions_met"):
        world.record_task_completion_preconditions_met(agent, "build_storage")
        world.record_task_completion_preconditions_met(agent, "construction_progress")
    if hasattr(world, "record_situated_construction_event"):
        world.record_situated_construction_event("construction_on_site_work_ticks")
    _advance_construction_progress(site)
    if hasattr(world, "record_settlement_progression_metric"):
        world.record_settlement_progression_metric("construction_progress_ticks")
    if hasattr(world, "record_settlement_progression_metric"):
        world.record_settlement_progression_metric("storage_construction_progress_ticks")
    _mark_construction_site_demand_tick(world, site)
    if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_productive"):
        world.record_task_completion_productive(agent, "construction_progress")
    if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_workforce_productive_action"):
        world.record_workforce_productive_action(agent, "builder", "construction_progress")
    if hasattr(world, "emit_event"):
        world.emit_event(
            "construction_progress",
            {
                "agent_id": str(getattr(agent, "agent_id", "")),
                "building_id": str(site.get("building_id", "")),
                "building_type": "storage",
                "outcome": "success",
            },
        )
    if not _site_work_complete(site):
        return False
    if not _use_construction_buffer(site, costs):
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "build_storage", "no_materials_in_buffer")
        if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "builder", "waiting_on_delivery")
        return False
    _complete_construction_site(world, site)
    if str(getattr(agent, "role", "")) == "builder" and hasattr(world, "record_task_completion_productive"):
        world.record_task_completion_productive(agent, "build_storage")
    return True


def production_yield_bonus_for_resource(
    world: "World",
    village: Optional[Dict[str, Any]],
    resource_type: str,
    gather_pos: Coord,
) -> int:
    bonus, _ = production_bonus_details_for_resource(world, village, resource_type, gather_pos)
    return bonus


def production_bonus_details_for_resource(
    world: "World",
    village: Optional[Dict[str, Any]],
    resource_type: str,
    gather_pos: Coord,
) -> Tuple[int, Optional[str]]:
    if village is None:
        return (0, None)

    village_id = _village_id(village)
    village_uid = _village_uid(village)
    eligible: List[Dict[str, Any]] = []
    specialization_type = "mine" if resource_type == "stone" else ("lumberyard" if resource_type == "wood" else "")
    active_specialized_count = 0

    for building in getattr(world, "buildings", {}).values():
        if village_id is not None and building.get("village_id") != village_id:
            continue
        if village_id is None and village_uid is not None and building.get("village_uid") != village_uid:
            continue
        if specialization_type and str(building.get("type", "")) == specialization_type and building.get("operational_state") == "active":
            active_specialized_count += 1
        if building.get("linked_resource_type") != resource_type:
            continue
        if building.get("operational_state") != "active":
            continue
        if int(building.get("linked_resource_tiles_count", 0)) <= 0:
            continue
        eligible.append(building)

    if not eligible:
        if specialization_type and active_specialized_count > 0:
            village = world.get_village_by_id(village_id) if village_id is not None else next(
                (v for v in getattr(world, "villages", []) if str(v.get("village_uid", "")) == str(village_uid or "")),
                None,
            )
            record_specialization_blocker(world, specialization_type, "no_matching_gather_events", village=village)
        return (0, None)

    eligible.sort(
        key=lambda b: (
            _distance((int(b.get("x", 0)), int(b.get("y", 0))), gather_pos),
            str(b.get("building_id", "")),
        )
    )
    selected = eligible[0]
    radius = int((get_building_metadata(str(selected.get("type", ""))) or {}).get("resource_context_radius", 6))
    distance = _distance((int(selected.get("x", 0)), int(selected.get("y", 0))), gather_pos)
    if distance > radius:
        if specialization_type:
            village = world.get_village_by_id(village_id) if village_id is not None else next(
                (v for v in getattr(world, "villages", []) if str(v.get("village_uid", "")) == str(village_uid or "")),
                None,
            )
            record_specialization_blocker(world, specialization_type, "no_matching_gather_events", village=village)
        return (0, None)

    specialist_role = "miner" if resource_type == "stone" else "woodcutter"
    has_specialist = False
    for a in getattr(world, "agents", []):
        if not getattr(a, "alive", False):
            continue
        if village_id is not None and getattr(a, "village_id", None) != village_id:
            continue
        if village_id is None and village_uid is not None:
            avuid = world.resolve_village_uid(getattr(a, "village_id", None))
            if avuid != village_uid:
                continue
        if getattr(a, "role", "") != specialist_role:
            continue
        assigned = getattr(a, "assigned_building_id", None)
        if assigned is None or assigned == selected.get("building_id"):
            has_specialist = True
            break

    # Legacy deterministic bonus stack kept as the base layer:
    # active production site (+1), specialist (+1), road connectivity (+1).
    bonus = 1
    if has_specialist:
        bonus += 1
    elif specialization_type:
        village = world.get_village_by_id(village_id) if village_id is not None else next(
            (v for v in getattr(world, "villages", []) if str(v.get("village_uid", "")) == str(village_uid or "")),
            None,
        )
        record_specialization_blocker(world, specialization_type, "no_specialist_assigned", village=village)
    if bool(selected.get("connected_to_road", False)):
        bonus += 1
    elif specialization_type:
        village = world.get_village_by_id(village_id) if village_id is not None else next(
            (v for v in getattr(world, "villages", []) if str(v.get("village_uid", "")) == str(village_uid or "")),
            None,
        )
        record_specialization_blocker(world, specialization_type, "no_road_service", village=village)
    bonus = min(3, bonus)

    # Soft infrastructure service gradient: production remains functional even
    # with low service, but throughput scales with transport/logistics quality.
    base_yield = 1 + bonus
    efficiency = compute_building_efficiency_multiplier(world, selected)
    scaled_yield = int(round(base_yield * efficiency))
    # Keep output bounded to avoid runaway amplification from future modifiers.
    scaled_yield = max(1, min(5, scaled_yield))
    scaled_bonus = max(0, scaled_yield - 1)
    if specialization_type:
        village = world.get_village_by_id(village_id) if village_id is not None else next(
            (v for v in getattr(world, "villages", []) if str(v.get("village_uid", "")) == str(village_uid or "")),
            None,
        )
        record_specialization_stage(world, specialization_type, "used_for_production_count", village=village)
    return (scaled_bonus, str(selected.get("type", "")))


def _default_production_metrics() -> Dict[str, int]:
    return {
        "total_food_gathered": 0,
        "total_wood_gathered": 0,
        "total_stone_gathered": 0,
        "direct_food_gathered": 0,
        "direct_wood_gathered": 0,
        "direct_stone_gathered": 0,
        "wood_from_lumberyards": 0,
        "stone_from_mines": 0,
    }


def _default_policy_build_state() -> Dict[str, int]:
    return {
        "last_policy_build_tick": -1,
        "next_policy_build_tick": 0,
        "window_start_tick": 0,
        "attempts_in_window": 0,
        "last_attempt_tick": -1,
    }


def get_or_init_policy_build_state(village: Dict[str, Any]) -> Dict[str, int]:
    state = village.get("policy_build_state")
    if not isinstance(state, dict):
        state = _default_policy_build_state()
        village["policy_build_state"] = state
        return state

    defaults = _default_policy_build_state()
    for key, default_value in defaults.items():
        if key not in state:
            state[key] = default_value
        else:
            state[key] = int(state.get(key, default_value))
    return state


def policy_build_cooldown_remaining(world: "World", village: Dict[str, Any]) -> int:
    state = get_or_init_policy_build_state(village)
    return max(0, int(state.get("next_policy_build_tick", 0)) - int(world.tick))


def _refresh_policy_attempt_window(world: "World", village: Dict[str, Any]) -> Dict[str, int]:
    state = get_or_init_policy_build_state(village)
    window_start = int(state.get("window_start_tick", 0))
    if int(world.tick) - window_start >= POLICY_BUILD_COOLDOWN_TICKS:
        state["window_start_tick"] = int(world.tick)
        state["attempts_in_window"] = 0
    return state


def can_attempt_policy_build(world: "World", village: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    state = _refresh_policy_attempt_window(world, village)
    if int(world.tick) < int(state.get("next_policy_build_tick", 0)):
        return (False, "cooldown_active")
    if int(state.get("attempts_in_window", 0)) >= POLICY_MAX_ATTEMPTS_PER_WINDOW:
        return (False, "attempt_budget_exhausted")
    return (True, None)


def record_policy_build_attempt(world: "World", village: Dict[str, Any], success: bool) -> None:
    state = _refresh_policy_attempt_window(world, village)
    state["last_attempt_tick"] = int(world.tick)
    state["attempts_in_window"] = int(state.get("attempts_in_window", 0)) + 1
    if success:
        state["last_policy_build_tick"] = int(world.tick)
        state["next_policy_build_tick"] = int(world.tick) + POLICY_BUILD_COOLDOWN_TICKS
        # Successful build opens a new pacing window after cooldown.
        state["window_start_tick"] = int(world.tick)
        state["attempts_in_window"] = 0


def get_or_init_village_production_metrics(village: Dict[str, Any]) -> Dict[str, int]:
    metrics = village.get("production_metrics")
    if not isinstance(metrics, dict):
        metrics = _default_production_metrics()
        village["production_metrics"] = metrics
        return metrics

    defaults = _default_production_metrics()
    for key, default_value in defaults.items():
        if key not in metrics:
            metrics[key] = default_value
        else:
            metrics[key] = int(metrics.get(key, default_value))
    return metrics


def record_village_resource_gather(
    village: Optional[Dict[str, Any]],
    resource_type: str,
    amount: int,
    bonus_amount: int = 0,
    production_source: Optional[str] = None,
) -> None:
    if village is None:
        return
    qty = int(amount)
    if qty <= 0:
        return
    bonus = max(0, int(bonus_amount))
    metrics = get_or_init_village_production_metrics(village)

    if resource_type == "food":
        metrics["total_food_gathered"] = int(metrics.get("total_food_gathered", 0)) + qty
        metrics["direct_food_gathered"] = int(metrics.get("direct_food_gathered", 0)) + qty
        return

    if resource_type == "wood":
        specialized = min(qty, bonus) if production_source == "lumberyard" else 0
        direct = max(0, qty - specialized)
        metrics["total_wood_gathered"] = int(metrics.get("total_wood_gathered", 0)) + qty
        metrics["direct_wood_gathered"] = int(metrics.get("direct_wood_gathered", 0)) + direct
        if specialized > 0:
            metrics["wood_from_lumberyards"] = int(metrics.get("wood_from_lumberyards", 0)) + specialized
    elif resource_type == "stone":
        specialized = min(qty, bonus) if production_source == "mine" else 0
        direct = max(0, qty - specialized)
        metrics["total_stone_gathered"] = int(metrics.get("total_stone_gathered", 0)) + qty
        metrics["direct_stone_gathered"] = int(metrics.get("direct_stone_gathered", 0)) + direct
        if specialized > 0:
            metrics["stone_from_mines"] = int(metrics.get("stone_from_mines", 0)) + specialized


def choose_next_building_type_for_village(world: "World", village: Dict[str, Any]) -> Optional[str]:
    can_attempt, _ = can_attempt_policy_build(world, village)
    if not can_attempt:
        return None

    pending_type = _pending_construction_type_for_village(world, village)
    if pending_type is not None:
        return pending_type

    recommended = get_recommended_building_types_for_village(world, village)
    available = get_available_building_types_for_village(world, village)
    if not recommended and not available:
        return None

    candidates = sorted(set(list(recommended) + list(available)))
    recommended_set = set(recommended)
    needs = village.get("needs", {}) if isinstance(village.get("needs"), dict) else {}
    signals = evaluate_village_unlock_signals(world, village)
    houses = int(village.get("houses", 0))
    population = int(village.get("population", 0))
    center = village.get("center", {}) if isinstance(village.get("center"), dict) else {}
    cx = int(center.get("x", 0))
    cy = int(center.get("y", 0))
    storage_maturity = _storage_maturity_snapshot(world, village)
    nearby_houses = int(storage_maturity.get("nearby_houses", 0))
    camp_signal = None
    if "x" in center and "y" in center and hasattr(world, "_nearest_active_camp_raw"):
        try:
            camp_signal = world._nearest_active_camp_raw(cx, cy, max_distance=8)  # type: ignore[attr-defined]
        except Exception:
            camp_signal = None
    active_camp_near = bool(isinstance(camp_signal, dict))

    def rank(building_type: str) -> Tuple[int, int, str]:
        metadata = get_building_metadata(building_type) or {}
        category = str(metadata.get("category", ""))

        urgency = 9
        if building_type == "storage":
            if bool(storage_maturity.get("mature_ready", False)) and (
                needs.get("need_storage")
                or signals.get("storage_pressure_high")
                or bool(signals.get("food_surplus_high"))
            ):
                urgency = 1
            else:
                # House-first progression: storage is collective infrastructure, not early materialization.
                urgency = 8
        elif building_type in {"mine", "lumberyard"}:
            if building_type in recommended_set:
                urgency = 1
            elif signals.get("stone_demand_high") or signals.get("wood_demand_high"):
                urgency = 3
            else:
                urgency = 6
        elif building_type == "house":
            if active_camp_near and nearby_houses < max(3, population // 2):
                urgency = 0
            elif signals.get("population_pressure_high"):
                urgency = 2
            else:
                urgency = 4
        elif category == "food_storage":
            urgency = 5
        elif category == "production":
            urgency = 6
        elif category == "residential":
            urgency = 4

        recommended_bias = 0 if building_type in recommended_set else 1
        return (urgency, recommended_bias, building_type)

    ordered = sorted(candidates, key=rank)
    selected = ordered[0]
    if selected in SPECIALIZATION_BUILDING_TYPES:
        record_specialization_stage(world, selected, "selected_by_policy_count", village=village)
    for candidate in ordered:
        if candidate in SPECIALIZATION_BUILDING_TYPES and candidate != selected:
            record_specialization_blocker(world, candidate, "build_policy_not_selected", village=village)
    return selected


def try_expand_village_buildings(world: "World", village: Dict[str, Any]) -> Dict[str, Any]:
    can_attempt, pacing_reason = can_attempt_policy_build(world, village)
    if not can_attempt:
        return {
            "success": False,
            "reason": str(pacing_reason),
            "building_type": None,
            "building_id": None,
            "position": None,
        }

    building_type = choose_next_building_type_for_village(world, village)
    if building_type is None:
        return {
            "success": False,
            "reason": "no_candidate_building_type",
            "building_type": None,
            "building_id": None,
            "position": None,
        }

    if building_type == "storage":
        if hasattr(world, "record_settlement_progression_metric"):
            world.record_settlement_progression_metric("storage_emergence_attempts")
        storage_maturity = _storage_maturity_snapshot(world, village)
        if bool(storage_maturity.get("surplus_ready", False)) and hasattr(world, "record_settlement_progression_metric"):
            world.record_settlement_progression_metric("surplus_triggered_storage_attempts")
        defer_reason = _storage_defer_reason_for_snapshot(storage_maturity)
        if defer_reason is not None:
            if hasattr(world, "record_settlement_progression_metric"):
                world.record_settlement_progression_metric(defer_reason)
            record_policy_build_attempt(world, village, success=False)
            return {
                "success": False,
                "reason": str(defer_reason),
                "building_type": building_type,
                "building_id": None,
                "position": None,
            }

    village_id = _village_id(village)
    village_uid = _village_uid(village)
    candidates = [
        a
        for a in world.agents
        if a.alive and not a.is_player and getattr(a, "village_id", None) == village_id
    ]
    if not candidates:
        if building_type in SPECIALIZATION_BUILDING_TYPES:
            record_specialization_blocker(world, building_type, "construction_not_completed", village=village)
        record_policy_build_attempt(world, village, success=False)
        return {
            "success": False,
            "reason": "no_builder_agent",
            "building_type": building_type,
            "building_id": None,
            "position": None,
        }

    candidates.sort(key=lambda a: (0 if getattr(a, "role", "") == "builder" else 1, a.agent_id))
    agent = candidates[0]
    if building_type in SPECIALIZATION_BUILDING_TYPES:
        record_specialization_stage(world, building_type, "build_attempt_count", village=village)
    if building_type in {"house", "storage"}:
        existing_site = _find_existing_village_construction_site(
            world,
            building_type,
            village_id,
            village_uid,
            agent_pos=(int(getattr(agent, "x", 0)), int(getattr(agent, "y", 0))),
        )
        if existing_site is not None:
            _mark_construction_site_demand_tick(world, existing_site)
            result = {
                "success": True,
                "reason": "existing_construction_site",
                "building_id": str(existing_site.get("building_id", "")),
                "position": {
                    "x": int(existing_site.get("x", 0)),
                    "y": int(existing_site.get("y", 0)),
                },
            }
        else:
            result = try_build_type(
                world,
                agent,
                building_type,
                village_id=village_id,
                village_uid=village_uid,
                as_construction_site=True,
            )
    else:
        result = try_build_type(world, agent, building_type, village_id=village_id, village_uid=village_uid)
    record_policy_build_attempt(world, village, success=bool(result.get("success")))
    return {
        **result,
        "building_type": building_type,
    }


def run_village_build_policy(world: "World", max_attempts_per_tick: int = 2) -> None:
    clear_stale_construction_sites(world)
    villages = sorted(
        getattr(world, "villages", []),
        key=lambda v: (str(v.get("village_uid", "")), int(v.get("id", 0))),
    )
    attempts = 0
    for village in villages:
        if attempts >= max_attempts_per_tick:
            break
        result = try_expand_village_buildings(world, village)
        if result.get("success"):
            attempts += 1
