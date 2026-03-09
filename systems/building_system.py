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
STORAGE_REBALANCE_RESERVE = 8
STORAGE_REBALANCE_MARGIN = 3
STORAGE_REBALANCE_TRANSFER_CAP = 2
POLICY_BUILD_COOLDOWN_TICKS = 60
POLICY_MAX_ATTEMPTS_PER_WINDOW = 2
CONSTRUCTION_WORK_RANGE = 1
CONSTRUCTION_WORK_PER_TICK = 1
CONSTRUCTION_REQUIRED_WORK_BY_TYPE = {
    "house": 4,
    "storage": 6,
}

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
            "population_min": 10,
            "houses_min": 4,
            "roads_required": True,
            "storage_required": True,
            "farms_min": 1,
        },
        "unlock_signals": ["stone_demand_high", "roads_present"],
        "unlock_conditions": {"population_min": 10, "food_surplus": True},
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
            "population_min": 8,
            "houses_min": 3,
            "roads_required": True,
            "storage_required": True,
            "farms_min": 1,
        },
        "unlock_signals": ["wood_demand_high", "roads_present"],
        "unlock_conditions": {"population_min": 10, "food_surplus": True},
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


def deposit_agent_inventory_to_storage(world: "World", agent: "Agent") -> bool:
    village = world.get_village_by_id(getattr(agent, "village_id", None))
    storage_building = _nearest_storage_for_agent(world, agent, village)
    if storage_building is None:
        return False

    sx = int(storage_building.get("x", 0))
    sy = int(storage_building.get("y", 0))
    if _distance((agent.x, agent.y), (sx, sy)) > 1:
        return False

    storage = _ensure_storage_state(storage_building)
    capacity = int(storage_building.get("storage_capacity", STORAGE_BUILDING_CAPACITY))
    moved = False
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

    if moved:
        _sync_village_storage_cache(world, village)
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
        return {
            "success": False,
            "reason": "invalid_resource_context",
            "building_id": None,
            "position": None,
        }

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

    placed = place_building(
        world,
        building_type,
        chosen,
        village_id=resolved_village_id,
        village_uid=resolved_village_uid,
    )
    if placed is None:
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
    placed["operational_state"] = (
        "active"
        if (not context.get("required", False) or context.get("valid", False))
        else "inactive"
    )

    return {
        "success": True,
        "reason": "placed",
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


def evaluate_village_unlock_signals(world: "World", village: Dict[str, Any]) -> Dict[str, bool]:
    population = int(village.get("population", 0))
    houses = int(village.get("houses", 0))
    storage = _village_storage(world, village)
    farms_count = _farms_count_for_village(world, village)
    storage_exists = _storage_exists_for_village(world, village)
    center_x, center_y = _village_center(village)

    roads_present = any(
        abs(rx - center_x) <= 4 and abs(ry - center_y) <= 4
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

    village_tier = int(village.get("tier", 1))
    min_tier = int(metadata.get("min_tier", metadata.get("tier", 0)))
    tier_ok = village_tier >= min_tier
    hard_requirements_ok = building_hard_requirements_met(world, village, building_type)
    if not tier_ok or not hard_requirements_ok:
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

    world.buildings[building_id] = building
    for tile in tiles:
        world.building_occupancy[tile] = building_id

    # Legacy compatibility sets kept for existing gameplay and observer paths.
    if building_type == "house" and building.get("operational_state") == "active":
        world.structures.add(origin)
    elif building_type == "storage" and building.get("operational_state") == "active":
        world.storage_buildings.add(origin)
        if village_for_readiness is not None:
            _sync_village_storage_cache(world, village_for_readiness)

    return building


def _find_nearest_storage_spot(world: "World", village: dict, origin: Coord) -> Optional[Coord]:
    cx = village.get("center", {}).get("x", origin[0])
    cy = village.get("center", {}).get("y", origin[1])

    candidates = _enumerate_candidate_positions(
        world,
        "storage",
        village=village,
        agent_pos=origin,
        preferred_anchors=[(cx, cy)],
        search_radius=6,
        max_distance_from_agent=10,
    )
    placeable = [pos for pos in candidates if can_place_building(world, "storage", pos)]
    if not placeable:
        return None
    return find_preferred_build_position(world, village, "storage", placeable)


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


def can_agent_work_on_construction(agent: "Agent", building: Dict[str, Any]) -> bool:
    if not isinstance(building, dict):
        return False
    bx = int(building.get("x", 0))
    by = int(building.get("y", 0))
    return _distance((int(agent.x), int(agent.y)), (bx, by)) <= int(CONSTRUCTION_WORK_RANGE)


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
    return place_building(
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


def _complete_construction_site(world: "World", building: Dict[str, Any]) -> None:
    building["operational_state"] = "active"
    building.pop("construction_request", None)
    building.pop("construction_buffer", None)
    required = max(1, int(building.get("construction_required_work", 1)))
    building["construction_progress"] = required
    building["construction_required_work"] = required
    pos = (int(building.get("x", 0)), int(building.get("y", 0)))
    if building.get("type") == "house":
        world.structures.add(pos)
    elif building.get("type") == "storage":
        world.storage_buildings.add(pos)
        village_id = building.get("village_id")
        village = world.get_village_by_id(village_id) if village_id is not None else None
        _sync_village_storage_cache(world, village)


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


def _clear_hauler_delivery(agent: "Agent") -> None:
    if hasattr(agent, "delivery_target_building_id"):
        agent.delivery_target_building_id = None
    if hasattr(agent, "delivery_resource_type"):
        agent.delivery_resource_type = None
    if hasattr(agent, "delivery_reserved_amount"):
        agent.delivery_reserved_amount = 0


def _withdraw_resource_from_storage(
    world: "World",
    agent: "Agent",
    *,
    resource_type: str,
    amount: int,
) -> int:
    village = world.get_village_by_id(getattr(agent, "village_id", None))
    storage_building = _nearest_storage_for_agent(world, agent, village)
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
    village = world.get_village_by_id(getattr(agent, "village_id", None))
    if village is None:
        _clear_hauler_delivery(agent)
        return False

    target_id = getattr(agent, "delivery_target_building_id", None)
    resource_type = getattr(agent, "delivery_resource_type", None)
    reserved_amount = int(getattr(agent, "delivery_reserved_amount", 0) or 0)

    if not target_id or resource_type not in ("wood", "stone", "food") or reserved_amount <= 0:
        sites = _construction_sites_for_village(world, village)
        candidates: List[Tuple[int, str, str, int]] = []
        storage_totals = get_village_storage_totals(world, village)
        for site in sites:
            needs = get_outstanding_construction_needs(site)
            for resource in ("wood", "stone", "food"):
                need = int(needs.get(resource, 0))
                if need <= 0:
                    continue
                available = int(storage_totals.get(resource, 0))
                if available <= 0:
                    continue
                sx = int(site.get("x", 0))
                sy = int(site.get("y", 0))
                dist = _distance((agent.x, agent.y), (sx, sy))
                candidates.append((dist, str(site.get("building_id", "")), resource, need))
        if not candidates:
            _clear_hauler_delivery(agent)
            return False
        candidates.sort(key=lambda x: (x[0], x[1], x[2]))
        _, bid, resource_type, need = candidates[0]
        reserve_cap = min(int(need), int(getattr(agent, "max_inventory", 0)))
        reserved = reserve_materials_for_construction(world, bid, resource_type, reserve_cap)
        if reserved <= 0:
            _clear_hauler_delivery(agent)
            return False
        agent.delivery_target_building_id = bid
        agent.delivery_resource_type = resource_type
        agent.delivery_reserved_amount = int(reserved)
        target_id = bid
        reserved_amount = int(reserved)

    site = getattr(world, "buildings", {}).get(str(target_id))
    if not isinstance(site, dict) or site.get("operational_state") != "under_construction":
        _clear_hauler_delivery(agent)
        return False
    resource_type = str(getattr(agent, "delivery_resource_type", ""))
    reserved_amount = int(getattr(agent, "delivery_reserved_amount", 0))
    if reserved_amount <= 0:
        _clear_hauler_delivery(agent)
        return False

    carrying = int(agent.inventory.get(resource_type, 0))
    if carrying <= 0:
        taken = _withdraw_resource_from_storage(
            world,
            agent,
            resource_type=resource_type,
            amount=reserved_amount,
        )
        return taken > 0

    sx = int(site.get("x", 0))
    sy = int(site.get("y", 0))
    if _distance((agent.x, agent.y), (sx, sy)) > 1:
        return False

    deliver_amount = min(carrying, reserved_amount)
    fulfilled = fulfill_reserved_delivery(world, str(target_id), resource_type, deliver_amount)
    if fulfilled <= 0:
        _clear_hauler_delivery(agent)
        return False
    agent.inventory[resource_type] = carrying - fulfilled
    agent.delivery_reserved_amount = max(0, reserved_amount - fulfilled)
    if int(agent.delivery_reserved_amount) <= 0:
        _clear_hauler_delivery(agent)
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
    village = world.get_village_by_id(getattr(agent, "village_id", None))
    if village is None:
        _clear_internal_transfer(agent)
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
        return False

    carrying = int(agent.inventory.get(resource_type, 0))
    if carrying <= 0:
        sx, sy = int(source.get("x", 0)), int(source.get("y", 0))
        if _distance((agent.x, agent.y), (sx, sy)) > 1:
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
            return False
        storage[resource_type] = available - qty
        agent.inventory[resource_type] = int(agent.inventory.get(resource_type, 0)) + qty
        _sync_village_storage_cache(world, village)
        return True

    tx, ty = int(target.get("x", 0)), int(target.get("y", 0))
    if _distance((agent.x, agent.y), (tx, ty)) > 1:
        return False
    target_storage = _ensure_storage_state(target)
    cap = int(target.get("storage_capacity", STORAGE_BUILDING_CAPACITY))
    free = max(0, cap - _storage_load(target))
    qty = min(carrying, max(0, transfer_amount), free)
    if qty <= 0:
        _clear_internal_transfer(agent)
        return False
    target_storage[resource_type] = int(target_storage.get(resource_type, 0)) + qty
    agent.inventory[resource_type] = carrying - qty
    _sync_village_storage_cache(world, village)
    _record_internal_transfer_metric(village, resource_type, qty)
    _clear_internal_transfer(agent)
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
    if len(world.structures) >= world.MAX_STRUCTURES:
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

    village = world.get_village_by_id(getattr(agent, "village_id", None))

    existing_site: Optional[Dict[str, Any]] = None
    if village is not None:
        existing_site = _find_existing_village_construction_site(
            world,
            "house",
            getattr(agent, "village_id", None),
            world.resolve_village_uid(getattr(agent, "village_id", None)),
        )
    if existing_site is not None:
        best_pos = (int(existing_site.get("x", 0)), int(existing_site.get("y", 0)))
    else:
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                x = agent.x + dx
                y = agent.y + dy

                if not can_build_at(world, x, y):
                    continue

                nearby_houses = count_nearby_houses(world, x, y, radius=5)
                connected_houses = count_nearby_houses(world, x, y, radius=4)
                nearby_population = count_nearby_population(world, x, y, radius=6)

                if nearby_houses >= world.MAX_HOUSES_PER_VILLAGE:
                    continue

                allowed_houses = nearby_population // 2 + 1
                if nearby_houses >= allowed_houses:
                    continue

                if nearby_houses == 0 and len(world.structures) >= world.MAX_NEW_VILLAGE_SEEDS:
                    continue

                # bootstrap hardening: after first seed, force compact growth so village detector can cluster.
                if bootstrap_mode and len(world.structures) > 0 and connected_houses == 0:
                    continue

                score = building_score(world, x, y)
                score += connected_houses * 8

                if nearby_houses == 0:
                    score -= 10

                if anchor is not None:
                    d_anchor = abs(anchor[0] - x) + abs(anchor[1] - y)
                    if d_anchor > 8:
                        continue
                    score += max(0, 36 - d_anchor * 4)

                if village is not None:
                    score += score_building_position(world, village, "house", (x, y))

                if score > best_score:
                    best_score = score
                    best_pos = (x, y)

    if best_pos is None:
        return False

    if bootstrap_mode:
        if not _can_pay(world, agent, HOUSE_WOOD_COST, HOUSE_STONE_COST):
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
            return False
        _pay(world, agent, HOUSE_WOOD_COST, HOUSE_STONE_COST)
        world.emit_event(
            "house_built",
            {
                "agent_id": agent.agent_id,
                "x": result["position"]["x"],
                "y": result["position"]["y"],
                "village_uid": world.resolve_village_uid(getattr(agent, "village_id", None)),
            },
        )
        return True

    village_id = getattr(agent, "village_id", None)
    village_uid = world.resolve_village_uid(village_id)
    costs = _construction_costs("house")
    site = _find_matching_construction_site(world, "house", best_pos, village_id, village_uid)
    if site is None:
        site = _create_construction_site(
            world,
            "house",
            best_pos,
            village_id=village_id,
            village_uid=village_uid,
            costs=costs,
        )
    if site is None:
        return False
    if not can_agent_work_on_construction(agent, site):
        return False
    _attach_carried_materials_to_site(agent, site, costs)
    if not _site_ready_for_completion(site, costs):
        return False
    _advance_construction_progress(site)
    if not _site_work_complete(site):
        return False
    if not _use_construction_buffer(site, costs):
        return False
    _complete_construction_site(world, site)
    world.emit_event(
        "house_built",
        {
            "agent_id": agent.agent_id,
            "x": int(site.get("x", 0)),
            "y": int(site.get("y", 0)),
            "village_uid": village_uid,
        },
    )
    return True


def try_build_storage(world: "World", agent: "Agent") -> bool:
    village_id = getattr(agent, "village_id", None)
    village = world.get_village_by_id(village_id)
    if village is None:
        return False

    storage_pos = village.get("storage_pos")
    if not storage_pos:
        return False

    sx = storage_pos["x"]
    sy = storage_pos["y"]

    if (sx, sy) in getattr(world, "storage_buildings", set()):
        return False

    existing_site = _find_matching_construction_site(
        world,
        "storage",
        (sx, sy),
        village_id,
        world.resolve_village_uid(village_id),
    )
    if existing_site is None and not can_place_building(world, "storage", (sx, sy)):
        replacement = _find_nearest_storage_spot(world, village, (agent.x, agent.y))
        if replacement is None:
            return False
        sx, sy = replacement
        village["storage_pos"] = {"x": sx, "y": sy}

    if _distance((int(agent.x), int(agent.y)), (int(sx), int(sy))) > int(CONSTRUCTION_WORK_RANGE):
        return False

    if existing_site is None and not can_place_building(world, "storage", (sx, sy)):
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
        return False
    if not can_agent_work_on_construction(agent, site):
        return False
    _attach_carried_materials_to_site(agent, site, costs)
    if not _site_ready_for_completion(site, costs):
        return False
    _advance_construction_progress(site)
    if not _site_work_complete(site):
        return False
    if not _use_construction_buffer(site, costs):
        return False
    _complete_construction_site(world, site)
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

    for building in getattr(world, "buildings", {}).values():
        if village_id is not None and building.get("village_id") != village_id:
            continue
        if village_id is None and village_uid is not None and building.get("village_uid") != village_uid:
            continue
        if building.get("linked_resource_type") != resource_type:
            continue
        if building.get("operational_state") != "active":
            continue
        if int(building.get("linked_resource_tiles_count", 0)) <= 0:
            continue
        eligible.append(building)

    if not eligible:
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
    if bool(selected.get("connected_to_road", False)):
        bonus += 1
    bonus = min(3, bonus)

    # Soft infrastructure service gradient: production remains functional even
    # with low service, but throughput scales with transport/logistics quality.
    base_yield = 1 + bonus
    efficiency = compute_building_efficiency_multiplier(world, selected)
    scaled_yield = int(round(base_yield * efficiency))
    # Keep output bounded to avoid runaway amplification from future modifiers.
    scaled_yield = max(1, min(5, scaled_yield))
    scaled_bonus = max(0, scaled_yield - 1)
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

    recommended = get_recommended_building_types_for_village(world, village)
    available = get_available_building_types_for_village(world, village)
    if not recommended and not available:
        return None

    candidates = recommended if recommended else available
    recommended_set = set(recommended)
    needs = village.get("needs", {}) if isinstance(village.get("needs"), dict) else {}
    signals = evaluate_village_unlock_signals(world, village)

    def rank(building_type: str) -> Tuple[int, int, str]:
        metadata = get_building_metadata(building_type) or {}
        category = str(metadata.get("category", ""))

        urgency = 9
        if building_type == "storage" and (needs.get("need_storage") or signals.get("storage_pressure_high")):
            urgency = 0
        elif building_type in {"mine", "lumberyard"} and (
            signals.get("stone_demand_high") or signals.get("wood_demand_high")
        ):
            urgency = 1
        elif building_type == "house" and signals.get("population_pressure_high"):
            urgency = 2
        elif category == "food_storage":
            urgency = 3
        elif category == "production":
            urgency = 4
        elif category == "residential":
            urgency = 5

        recommended_bias = 0 if building_type in recommended_set else 1
        return (recommended_bias, urgency, building_type)

    return sorted(candidates, key=rank)[0]


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

    village_id = _village_id(village)
    village_uid = _village_uid(village)
    candidates = [
        a
        for a in world.agents
        if a.alive and not a.is_player and getattr(a, "village_id", None) == village_id
    ]
    if not candidates:
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
    result = try_build_type(world, agent, building_type, village_id=village_id, village_uid=village_uid)
    record_policy_build_attempt(world, village, success=bool(result.get("success")))
    return {
        **result,
        "building_type": building_type,
    }


def run_village_build_policy(world: "World", max_attempts_per_tick: int = 2) -> None:
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
