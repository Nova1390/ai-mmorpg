from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import systems.building_system as building_system

PATH_BUILD_THRESHOLD = 4
ROAD_BUILD_THRESHOLD = 12
CORRIDOR_BUILD_THRESHOLD = 30
ROAD_GROWTH_TILES_PER_TICK = 12

Coord = Tuple[int, int]


def get_transport_infrastructure_metadata(infrastructure_type: str = "road") -> Optional[Dict]:
    metadata = building_system.get_infrastructure_metadata(infrastructure_type)
    if metadata is None:
        return None
    if str(metadata.get("system", "")) != "transport":
        return None
    return metadata


def record_agent_step(world, x: int, y: int) -> None:
    pos = (x, y)
    world.road_usage[pos] = world.road_usage.get(pos, 0) + 1

    if world.is_tile_blocked_by_building(x, y):
        return

    usage = int(world.road_usage[pos])
    current_type = getattr(world, "get_transport_type", lambda px, py: "road" if (px, py) in world.roads else None)(x, y)
    if usage >= CORRIDOR_BUILD_THRESHOLD:
        if current_type != "logistics_corridor":
            world.set_transport_type(x, y, "logistics_corridor")
        return
    if usage >= ROAD_BUILD_THRESHOLD:
        if current_type != "road":
            world.set_transport_type(x, y, "road")
        return
    if usage >= PATH_BUILD_THRESHOLD and current_type is None:
        world.set_transport_type(x, y, "path")


def _coord_key(coord: Coord) -> Tuple[int, int]:
    return (coord[1], coord[0])


def _neighbors4(x: int, y: int) -> List[Coord]:
    return [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]


def _is_road_adjacent(world, x: int, y: int) -> bool:
    for nx, ny in _neighbors4(x, y):
        t = world.get_transport_type(nx, ny)
        if t in {"road", "logistics_corridor", "bridge", "tunnel"}:
            return True
    return False


def _building_footprint_tiles(building: Dict) -> List[Coord]:
    footprint = building.get("footprint", [])
    if isinstance(footprint, list) and footprint:
        tiles = []
        for tile in footprint:
            if isinstance(tile, dict) and "x" in tile and "y" in tile:
                tiles.append((int(tile["x"]), int(tile["y"])))
        if tiles:
            return sorted(tiles, key=_coord_key)
    return [(int(building.get("x", 0)), int(building.get("y", 0)))]


def update_building_road_connectivity(world) -> None:
    for building_id in sorted(getattr(world, "buildings", {}).keys()):
        building = world.buildings[building_id]
        connected = False
        for bx, by in _building_footprint_tiles(building):
            if _is_road_adjacent(world, bx, by):
                connected = True
                break
        building["connected_to_road"] = connected


def _is_road_placeable(world, x: int, y: int) -> bool:
    if not (0 <= x < world.width and 0 <= y < world.height):
        return False
    if not world.is_walkable(x, y):
        return False
    if world.is_tile_blocked_by_building(x, y):
        return False
    return True


def _anchor_road_candidates_for_building(world, building: Dict) -> List[Coord]:
    candidates = set()
    for x, y in _building_footprint_tiles(building):
        for nx, ny in _neighbors4(x, y):
            if _is_road_placeable(world, nx, ny):
                candidates.add((nx, ny))
    return sorted(candidates, key=_coord_key)


def _anchor_road_candidates_for_point(world, x: int, y: int) -> List[Coord]:
    candidates = set()
    if _is_road_placeable(world, x, y):
        candidates.add((x, y))
    for nx, ny in _neighbors4(x, y):
        if _is_road_placeable(world, nx, ny):
            candidates.add((nx, ny))
    return sorted(candidates, key=_coord_key)


def _prefer_existing_road_node(world, candidates: Iterable[Coord]) -> Optional[Coord]:
    sorted_candidates = sorted(candidates, key=_coord_key)
    for coord in sorted_candidates:
        if world.get_transport_type(coord[0], coord[1]) in {"road", "logistics_corridor", "bridge", "tunnel"}:
            return coord
    return sorted_candidates[0] if sorted_candidates else None


def _manhattan_path_xy_first(start: Coord, goal: Coord) -> List[Coord]:
    x, y = start
    gx, gy = goal
    path: List[Coord] = [(x, y)]
    step_x = 1 if gx > x else -1
    while x != gx:
        x += step_x
        path.append((x, y))
    step_y = 1 if gy > y else -1
    while y != gy:
        y += step_y
        path.append((x, y))
    return path


def _manhattan_path_yx_first(start: Coord, goal: Coord) -> List[Coord]:
    x, y = start
    gx, gy = goal
    path: List[Coord] = [(x, y)]
    step_y = 1 if gy > y else -1
    while y != gy:
        y += step_y
        path.append((x, y))
    step_x = 1 if gx > x else -1
    while x != gx:
        x += step_x
        path.append((x, y))
    return path


def _valid_road_path(world, path: List[Coord]) -> bool:
    return all(
        _is_road_placeable(world, x, y) or world.get_transport_type(x, y) in {"road", "logistics_corridor", "bridge", "tunnel"}
        for x, y in path
    )


def _choose_road_path(world, start: Coord, goal: Coord) -> Optional[List[Coord]]:
    paths = [_manhattan_path_xy_first(start, goal), _manhattan_path_yx_first(start, goal)]
    valid_paths = [p for p in paths if _valid_road_path(world, p)]
    if not valid_paths:
        return None
    valid_paths.sort(key=lambda p: (len(p), p))
    return valid_paths[0]


def _building_priority(building: Dict) -> Tuple[int, str]:
    metadata = building_system.get_building_metadata(str(building.get("type", ""))) or {}
    requires_road = bool(metadata.get("requires_road", False))
    category = str(building.get("category") or metadata.get("category", ""))
    btype = str(building.get("type", ""))

    if requires_road:
        prio = 0
    elif category == "food_storage":
        prio = 1
    elif btype == "house" or category == "residential":
        prio = 2
    elif category in {"production", "infrastructure"}:
        prio = 3
    else:
        prio = 4
    return (prio, str(building.get("building_id", "")))


def _village_buildings(world, village: Dict) -> List[Dict]:
    village_id = village.get("id")
    village_uid = village.get("village_uid")
    result = []
    for building in world.buildings.values():
        if village_id is not None and building.get("village_id") == village_id:
            result.append(building)
            continue
        if village_uid is not None and building.get("village_uid") == village_uid:
            result.append(building)
    result.sort(key=_building_priority)
    return result


def _village_hub_node(world, village: Dict, village_buildings: List[Dict]) -> Optional[Coord]:
    storage_buildings = [b for b in village_buildings if b.get("category") == "food_storage"]
    if storage_buildings:
        storage_buildings.sort(key=lambda b: str(b.get("building_id", "")))
        for building in storage_buildings:
            candidates = _anchor_road_candidates_for_building(world, building)
            node = _prefer_existing_road_node(world, candidates)
            if node is not None:
                return node

    center = village.get("center", {})
    cx = int(center.get("x", 0))
    cy = int(center.get("y", 0))
    candidates = _anchor_road_candidates_for_point(world, cx, cy)
    return _prefer_existing_road_node(world, candidates)


def _important_target_nodes(world, village: Dict, village_buildings: List[Dict]) -> List[Tuple[int, Coord]]:
    targets: List[Tuple[int, Coord]] = []

    for building in village_buildings:
        metadata = building_system.get_building_metadata(str(building.get("type", ""))) or {}
        category = str(building.get("category") or metadata.get("category", ""))
        requires_road = bool(metadata.get("requires_road", False))
        is_important = requires_road or category in {"food_storage", "production", "infrastructure", "residential"}
        if not is_important:
            continue

        candidates = _anchor_road_candidates_for_building(world, building)
        if not candidates:
            continue

        if bool(building.get("connected_to_road", False)):
            continue

        node = _prefer_existing_road_node(world, candidates)
        if node is not None:
            prio, _ = _building_priority(building)
            targets.append((prio, node))

    farm_zone = village.get("farm_zone_center")
    if isinstance(farm_zone, dict):
        fx = int(farm_zone.get("x", 0))
        fy = int(farm_zone.get("y", 0))
        if not _is_road_adjacent(world, fx, fy):
            candidates = _anchor_road_candidates_for_point(world, fx, fy)
            node = _prefer_existing_road_node(world, candidates)
            if node is not None:
                targets.append((2, node))

    targets = sorted(targets, key=lambda item: (item[0], _coord_key(item[1])))
    dedup: List[Tuple[int, Coord]] = []
    seen = set()
    for item in targets:
        if item[1] in seen:
            continue
        seen.add(item[1])
        dedup.append(item)
    return dedup


def _grow_roads_for_village(world, village: Dict, budget: int) -> int:
    if budget <= 0:
        return 0

    village_buildings = _village_buildings(world, village)
    if not village_buildings:
        return 0

    hub = _village_hub_node(world, village, village_buildings)
    if hub is None:
        return 0

    targets = _important_target_nodes(world, village, village_buildings)
    if not targets:
        return 0

    # Connect closest important target to hub first.
    ranked_targets = sorted(
        targets,
        key=lambda item: (item[0], abs(item[1][0] - hub[0]) + abs(item[1][1] - hub[1]), _coord_key(item[1])),
    )

    added = 0
    for _, target in ranked_targets:
        if added >= budget:
            break
        path = _choose_road_path(world, hub, target)
        if path is None:
            continue

        for x, y in path:
            if added >= budget:
                break
            existing = world.get_transport_type(x, y)
            if existing in {"road", "logistics_corridor", "bridge", "tunnel"}:
                continue
            if _is_road_placeable(world, x, y):
                world.set_transport_type(x, y, "road")
                added += 1

    return added


def update_road_infrastructure(world) -> None:
    villages = sorted(
        getattr(world, "villages", []),
        key=lambda v: (str(v.get("village_uid", "")), int(v.get("id", 0))),
    )

    remaining_budget = ROAD_GROWTH_TILES_PER_TICK
    for village in villages:
        if remaining_budget <= 0:
            break
        added = _grow_roads_for_village(world, village, remaining_budget)
        remaining_budget -= added

    update_building_road_connectivity(world)

    # Explicitly mirror road runtime as transport infrastructure metadata.
    meta = get_transport_infrastructure_metadata("road")
    if isinstance(getattr(world, "infrastructure_state", None), dict):
        transport = world.infrastructure_state.setdefault("transport", {})
        if meta is not None:
            transport["road_infrastructure_type"] = str(meta.get("type", "road"))
            transport["network_type"] = str(meta.get("network_type", "tile_network"))
