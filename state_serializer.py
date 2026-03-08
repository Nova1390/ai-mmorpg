from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple


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
        }
        for a in alive_agents
    ]
    agents.sort(key=lambda a: a["agent_id"])
    return agents


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
    }

    return payload
