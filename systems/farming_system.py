from __future__ import annotations

import random
from typing import Tuple

Coord = Tuple[int, int]

PREPARE_WOOD_COST = 1
PLANT_GROW_TICKS = 35
HARVEST_YIELD = 1
HARVEST_BONUS_CHANCE = 0.3
STORAGE_NEAR_FARM_RADIUS = 5
PRIMARY_FARM_ZONE_RADIUS = 6


def _get_build_wallet(world, agent):
    return agent.inventory


def update_farms(world) -> None:
    to_delete = []

    for pos, plot in world.farm_plots.items():
        state = plot.get("state", "prepared")

        if state == "planted":
            plot["state"] = "growing"
            plot["growth"] = 1
            continue

        if state == "growing":
            plot["growth"] = plot.get("growth", 0) + 1
            if plot["growth"] >= PLANT_GROW_TICKS:
                plot["state"] = "ripe"
            continue

        if state == "dead":
            to_delete.append(pos)

    for pos in to_delete:
        world.farm_plots.pop(pos, None)
        world.farms.discard(pos)


def try_build_farm(world, agent) -> bool:
    wallet = _get_build_wallet(world, agent)
    if wallet.get("wood", 0) < PREPARE_WOOD_COST:
        return False

    village_id = getattr(agent, "village_id", None)
    village = world.get_village_by_id(village_id)
    if village is None:
        return False

    x = agent.x
    y = agent.y
    pos = (x, y)

    primary_center = _primary_farm_center(world, village)
    if primary_center is not None:
        pcx, pcy = primary_center
        has_primary_slot = _has_primary_zone_slot(world, village, village_id, primary_center)
        if has_primary_slot and (abs(x - pcx) + abs(y - pcy) > PRIMARY_FARM_ZONE_RADIUS):
            return False

    if world.tiles[y][x] != "G":
        return False

    if world.is_tile_blocked_by_building(x, y):
        return False

    if pos in world.farms or pos in world.farm_plots:
        return False

    # non attaccato alle case
    for sx, sy in world.get_building_occupied_tiles():
        if abs(sx - x) <= 1 and abs(sy - y) <= 1:
            return False

    same_village_farms = [
        p for p, plot in world.farm_plots.items()
        if plot.get("village_id") == village_id
    ]

    # limite campi per villaggio
    max_farms_for_village = max(2, village["population"] // 2 + village["houses"])
    if len(same_village_farms) >= max_farms_for_village:
        return False

    farm_zone = village.get("farm_zone_center", village["center"])
    fzx = farm_zone["x"]
    fzy = farm_zone["y"]

    if not same_village_farms:
        # primo campo: vicino al centro agricolo del villaggio
        if abs(fzx - x) > 3 or abs(fzy - y) > 3:
            return False
    else:
        # campi successivi: cluster vicino ai campi esistenti
        adjacent_same_village = False
        for fx, fy in same_village_farms:
            if abs(fx - x) <= 1 and abs(fy - y) <= 1:
                adjacent_same_village = True
                break

        if not adjacent_same_village:
            return False

        # non allargare troppo il cluster
        if abs(fzx - x) > 6 or abs(fzy - y) > 6:
            return False

    world.farms.add(pos)
    world.farm_plots[pos] = {
        "x": x,
        "y": y,
        "state": "prepared",
        "growth": 0,
        "village_id": village_id,
        "owner_role": getattr(agent, "role", "npc"),
    }

    wallet["wood"] = wallet.get("wood", 0) - PREPARE_WOOD_COST
    world.emit_event(
        "farm_created",
        {
            "agent_id": agent.agent_id,
            "x": x,
            "y": y,
            "village_uid": world.resolve_village_uid(village_id),
        },
    )
    return True


def work_farm(world, agent) -> bool:
    pos = (agent.x, agent.y)
    plot = world.farm_plots.get(pos)

    if not plot:
        return False

    state = plot.get("state", "prepared")
    village_id = plot.get("village_id")
    village = world.get_village_by_id(village_id)

    if state == "prepared":
        plot["state"] = "planted"
        plot["growth"] = 0
        return True

    if state == "ripe":
        harvest_amount = HARVEST_YIELD
        bonus_chance = HARVEST_BONUS_CHANCE + _storage_farm_bonus_chance(world, village, pos)
        if random.random() < bonus_chance:
            harvest_amount += 1
        space = max(0, getattr(agent, "inventory_space", lambda: 0)())
        if space <= 0:
            return False
        gathered = min(harvest_amount, space)
        agent.inventory["food"] = agent.inventory.get("food", 0) + gathered

        plot["state"] = "prepared"
        plot["growth"] = 0
        world.emit_event(
            "resource_harvested",
            {
                "agent_id": agent.agent_id,
                "resource": "food",
                "amount": gathered,
                "source": "farm",
                "x": pos[0],
                "y": pos[1],
                "village_uid": world.resolve_village_uid(getattr(agent, "village_id", None)),
            },
        )
        return True

    return False


def haul_harvest(world, agent) -> bool:
    """
    Minimal logistics harvest:
    hauler raccoglie dal campo maturo nel proprio inventario
    invece di depositare direttamente nello storage villaggio.
    """
    pos = (agent.x, agent.y)
    plot = world.farm_plots.get(pos)
    if not plot:
        return False

    if plot.get("state") != "ripe":
        return False

    village = world.get_village_by_id(getattr(agent, "village_id", None))
    harvest_amount = HARVEST_YIELD
    bonus_chance = HARVEST_BONUS_CHANCE + _storage_farm_bonus_chance(world, village, pos)
    if random.random() < bonus_chance:
        harvest_amount += 1
    space = max(0, getattr(agent, "inventory_space", lambda: 0)())
    if space <= 0:
        return False
    gathered = min(harvest_amount, space)
    agent.inventory["food"] = agent.inventory.get("food", 0) + gathered
    plot["state"] = "prepared"
    plot["growth"] = 0
    world.emit_event(
        "resource_harvested",
        {
            "agent_id": agent.agent_id,
            "resource": "food",
            "amount": gathered,
            "source": "farm_haul",
            "x": pos[0],
            "y": pos[1],
            "village_uid": world.resolve_village_uid(getattr(agent, "village_id", None)),
        },
    )
    return True


def _storage_farm_bonus_chance(world, village, farm_pos: Coord) -> float:
    """
    Storage as logistic hub:
    farms near storage get a +10% baseline bonus, plus a small distance factor.
    """
    if village is None:
        return 0.0
    sp = village.get("storage_pos")
    if not sp:
        return 0.0
    sx, sy = sp["x"], sp["y"]
    if (sx, sy) not in getattr(world, "storage_buildings", set()):
        return 0.0
    fx, fy = farm_pos
    d = abs(fx - sx) + abs(fy - sy)
    if d > STORAGE_NEAR_FARM_RADIUS:
        return 0.0
    # +10% in radius, with up to +10% extra for very close farms.
    return 0.10 + max(0.0, (STORAGE_NEAR_FARM_RADIUS - d) * 0.02)


def _primary_farm_center(world, village) -> Coord | None:
    if village is None:
        return None
    sp = village.get("storage_pos")
    if sp:
        sx, sy = sp.get("x"), sp.get("y")
        if (sx, sy) in getattr(world, "storage_buildings", set()):
            return (sx, sy)
    zone = village.get("farm_zone_center", village.get("center"))
    if not zone:
        return None
    zx = zone.get("x")
    zy = zone.get("y")
    if zx is None or zy is None:
        return None
    return (zx, zy)


def _is_valid_primary_slot(world, village, village_id, x: int, y: int) -> bool:
    pos = (x, y)
    if not (0 <= x < world.width and 0 <= y < world.height):
        return False
    if world.tiles[y][x] != "G":
        return False
    if not world.can_build_at(x, y):
        return False
    if pos in world.farms or pos in world.farm_plots:
        return False
    for sx, sy in world.get_building_occupied_tiles():
        if abs(sx - x) <= 1 and abs(sy - y) <= 1:
            return False
    same_village_farms = [
        p for p, plot in world.farm_plots.items()
        if plot.get("village_id") == village_id
    ]
    if not same_village_farms:
        return True
    return any(abs(fx - x) <= 1 and abs(fy - y) <= 1 for fx, fy in same_village_farms)


def _has_primary_zone_slot(world, village, village_id, center: Coord) -> bool:
    cx, cy = center
    for x in range(max(0, cx - PRIMARY_FARM_ZONE_RADIUS), min(world.width, cx + PRIMARY_FARM_ZONE_RADIUS + 1)):
        for y in range(max(0, cy - PRIMARY_FARM_ZONE_RADIUS), min(world.height, cy + PRIMARY_FARM_ZONE_RADIUS + 1)):
            if abs(x - cx) + abs(y - cy) > PRIMARY_FARM_ZONE_RADIUS:
                continue
            if _is_valid_primary_slot(world, village, village_id, x, y):
                return True
    return False
