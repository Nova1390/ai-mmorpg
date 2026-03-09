from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

import systems.building_system as building_system

SCHEMA_VERSION = "1.1.0"
STATIC_STATE_VERSION = 1
Coord = Tuple[int, int]


# Deterministic coordinate ordering: row-major (y first, x second).
def _coord_key(coord: Coord) -> Tuple[int, int]:
    return (coord[1], coord[0])


def _coord_dict(x: int, y: int) -> Dict[str, int]:
    return {"x": int(x), "y": int(y)}


def _sorted_coords(coords: Iterable[Coord]) -> List[Dict[str, int]]:
    return [_coord_dict(x, y) for x, y in sorted(coords, key=_coord_key)]


def _serialize_farms(world) -> List[Dict[str, Any]]:
    farms: List[Dict[str, Any]] = []
    for _, plot in sorted(world.farm_plots.items(), key=lambda item: _coord_key(item[0])):
        farms.append(
            {
                "x": int(plot["x"]),
                "y": int(plot["y"]),
                "state": plot.get("state", "prepared"),
                "growth": int(plot.get("growth", 0)),
                "village_id": plot.get("village_id"),
            }
        )
    return farms


def _serialize_villages(world) -> List[Dict[str, Any]]:
    villages = []
    for v in world.villages:
        village_uid = str(v.get("village_uid") or f"legacy-{int(v.get('id', 0))}")
        raw_tiles = v.get("tiles", [])
        sorted_tiles = sorted(
            (
                {"x": int(t["x"]), "y": int(t["y"])}
                for t in raw_tiles
                if isinstance(t, dict) and "x" in t and "y" in t
            ),
            key=lambda t: (t["y"], t["x"]),
        )
        villages.append(
            {
                **v,
                "village_uid": village_uid,
                "tiles": sorted_tiles,
                "storage": v.get("storage", {"food": 0, "wood": 0, "stone": 0}),
                "storage_pos": v.get("storage_pos"),
                "farm_zone_center": v.get("farm_zone_center"),
                "tier": int(v.get("tier", 1)),
                "needs": v.get("needs", {}),
                "priority": v.get("priority", "stabilize"),
                "metrics": v.get("metrics", {}),
            }
        )

    villages.sort(key=lambda v: (v.get("village_uid") or "", int(v.get("id", 0))))
    return villages


def _serialize_agents(alive_agents) -> List[Dict[str, Any]]:
    agents = [
        {
            "agent_id": a.agent_id,
            "x": a.x,
            "y": a.y,
            "is_player": a.is_player,
            "player_id": a.player_id,
            "role": getattr(a, "role", "npc"),
            "village_id": getattr(a, "village_id", None),
            "task": getattr(a, "task", "idle"),
            "inventory": {
                "food": int(getattr(a, "inventory", {}).get("food", 0)),
                "wood": int(getattr(a, "inventory", {}).get("wood", 0)),
                "stone": int(getattr(a, "inventory", {}).get("stone", 0)),
            },
            "max_inventory": int(getattr(a, "max_inventory", 0)),
        }
        for a in alive_agents
    ]
    agents.sort(key=lambda a: a["agent_id"])
    return agents


def _serialize_buildings(world) -> List[Dict[str, Any]]:
    serialized: List[Dict[str, Any]] = []
    raw_buildings = getattr(world, "buildings", {})

    if isinstance(raw_buildings, dict) and raw_buildings:
        for building in raw_buildings.values():
            footprint = building.get("footprint", [])
            footprint_sorted = sorted(
                (
                    {"x": int(tile["x"]), "y": int(tile["y"])}
                    for tile in footprint
                    if isinstance(tile, dict) and "x" in tile and "y" in tile
                ),
                key=lambda t: (t["y"], t["x"]),
            )
            serialized.append(
                {
                    "building_id": str(building.get("building_id", "")),
                    "type": str(building.get("type", "house")),
                    "category": str(building.get("category", "residential")),
                    "tier": int(building.get("tier", 1)),
                    "x": int(building.get("x", 0)),
                    "y": int(building.get("y", 0)),
                    "footprint": footprint_sorted,
                    "village_id": building.get("village_id"),
                    "village_uid": building.get("village_uid"),
                    "connected_to_road": bool(building.get("connected_to_road", False)),
                    "operational_state": str(building.get("operational_state", "active")),
                    "linked_resource_type": building.get("linked_resource_type"),
                    "linked_resource_tiles_count": int(building.get("linked_resource_tiles_count", 0)),
                    "service": {
                        **building_system.evaluate_building_infrastructure_service(world, building),
                        "efficiency_multiplier": building_system.compute_building_efficiency_multiplier(world, building),
                    },
                    "storage": (
                        {
                            "food": int((building.get("storage") or {}).get("food", 0)),
                            "wood": int((building.get("storage") or {}).get("wood", 0)),
                            "stone": int((building.get("storage") or {}).get("stone", 0)),
                        }
                        if str(building.get("type", "")) == "storage"
                        else None
                    ),
                    "storage_capacity": (
                        int(building.get("storage_capacity", 0))
                        if str(building.get("type", "")) == "storage"
                        else None
                    ),
                    "construction_request": (
                        dict(building.get("construction_request", {}))
                        if isinstance(building.get("construction_request"), dict)
                        else None
                    ),
                    "construction_buffer": (
                        {
                            "food": int((building.get("construction_buffer") or {}).get("food", 0)),
                            "wood": int((building.get("construction_buffer") or {}).get("wood", 0)),
                            "stone": int((building.get("construction_buffer") or {}).get("stone", 0)),
                        }
                        if isinstance(building.get("construction_buffer"), dict)
                        else None
                    ),
                }
            )
    else:
        for x, y in sorted(getattr(world, "structures", set()), key=_coord_key):
            metadata = building_system.get_building_metadata("house") or {}
            serialized.append(
                {
                    "building_id": f"legacy-house-{x}-{y}",
                    "type": "house",
                    "category": str(metadata.get("category", "residential")),
                    "tier": int(metadata.get("tier", 1)),
                    "x": x,
                    "y": y,
                    "footprint": [_coord_dict(x, y)],
                    "village_id": None,
                    "village_uid": None,
                    "connected_to_road": False,
                    "operational_state": "active",
                    "linked_resource_type": None,
                    "linked_resource_tiles_count": 0,
                    "service": None,
                    "storage": None,
                    "storage_capacity": None,
                    "construction_request": None,
                    "construction_buffer": None,
                }
            )
        for x, y in sorted(getattr(world, "storage_buildings", set()), key=_coord_key):
            metadata = building_system.get_building_metadata("storage") or {}
            serialized.append(
                {
                    "building_id": f"legacy-storage-{x}-{y}",
                    "type": "storage",
                    "category": str(metadata.get("category", "food_storage")),
                    "tier": int(metadata.get("tier", 1)),
                    "x": x,
                    "y": y,
                    "footprint": [_coord_dict(x, y)],
                    "village_id": None,
                    "village_uid": None,
                    "connected_to_road": False,
                    "operational_state": "active",
                    "linked_resource_type": None,
                    "linked_resource_tiles_count": 0,
                    "service": None,
                    "storage": None,
                    "storage_capacity": None,
                    "construction_request": None,
                    "construction_buffer": None,
                }
            )

    serialized.sort(key=lambda b: b["building_id"])
    return serialized


def serialize_static_world_state(world) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "static_state_version": STATIC_STATE_VERSION,
        "width": world.width,
        "height": world.height,
        "tiles": world.tiles,
    }
    if hasattr(world, "world_seed"):
        payload["world_seed"] = getattr(world, "world_seed")
    return payload


def serialize_dynamic_world_state(world) -> Dict[str, Any]:
    alive_agents = [a for a in world.agents if a.alive]
    players = [a for a in alive_agents if a.is_player]
    npcs = [a for a in alive_agents if not a.is_player]
    avg_hunger = (
        (sum(a.hunger for a in alive_agents) / len(alive_agents))
        if alive_agents
        else 0.0
    )

    farms = _serialize_farms(world)
    villages = _serialize_villages(world)
    agents = _serialize_agents(alive_agents)
    buildings = _serialize_buildings(world)
    infrastructure_state = getattr(world, "infrastructure_state", {})
    systems_available: List[str] = []
    transport_network_counts: Dict[str, int] = {}
    if isinstance(infrastructure_state, dict):
        systems = infrastructure_state.get("systems", {})
        if isinstance(systems, dict):
            systems_available = sorted(str(k) for k in systems.keys())
        transport = infrastructure_state.get("transport", {})
        if isinstance(transport, dict):
            raw_counts = transport.get("tile_counts", {})
            if isinstance(raw_counts, dict):
                transport_network_counts = {
                    str(k): int(v)
                    for k, v in sorted(raw_counts.items(), key=lambda item: str(item[0]))
                }

    state_version = world.next_state_version()

    payload: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "state_version": state_version,
        "tick": world.tick,
        "food": _sorted_coords(world.food),
        "wood": _sorted_coords(world.wood),
        "stone": _sorted_coords(world.stone),
        "farms": farms,
        "farms_count": len(world.farm_plots),
        "structures": _sorted_coords(world.structures),
        "roads": _sorted_coords(world.roads),
        "storage_buildings": _sorted_coords(world.storage_buildings),
        "buildings": buildings,
        "villages": villages,
        "civ_stats": world.get_civilization_stats(),
        "agents": agents,
        "population": len(alive_agents),
        "players": len(players),
        "npcs": len(npcs),
        "avg_hunger": round(avg_hunger, 2),
        "food_count": len(world.food),
        "wood_count": len(world.wood),
        "stone_count": len(world.stone),
        "houses_count": len(world.structures),
        "villages_count": len(world.villages),
        "leaders_count": world.count_leaders(),
        "llm_interactions": world.llm_interactions,
        "infrastructure_systems_available": systems_available,
        "transport_network_counts": transport_network_counts,
    }

    return payload
