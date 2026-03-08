from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

from config import HOUSE_WOOD_COST, HOUSE_STONE_COST

if TYPE_CHECKING:
    from world import World
    from agent import Agent


Coord = Tuple[int, int]

STORAGE_WOOD_COST = 4
STORAGE_STONE_COST = 2


def _find_nearest_storage_spot(world: "World", village: dict, origin: Coord) -> Optional[Coord]:
    cx = village.get("center", {}).get("x", origin[0])
    cy = village.get("center", {}).get("y", origin[1])

    best: Optional[Coord] = None
    best_score = 10**9

    for radius in range(0, 7):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                x = cx + dx
                y = cy + dy
                if abs(dx) + abs(dy) > radius:
                    continue

                if not can_build_at(world, x, y):
                    continue

                # Keep storage close to village center and reachable by current builder.
                score = abs(x - cx) + abs(y - cy) + abs(x - origin[0]) + abs(y - origin[1])
                if score < best_score:
                    best_score = score
                    best = (x, y)

        if best is not None:
            return best

    return None


def _get_build_wallet(world: "World", agent: "Agent"):
    village = world.get_village_by_id(getattr(agent, "village_id", None))
    if village is not None:
        return village.get("storage", {})
    return agent.inventory


def _can_pay(world: "World", agent: "Agent", wood_cost: int, stone_cost: int) -> bool:
    village = world.get_village_by_id(getattr(agent, "village_id", None))
    if village is None:
        wallet = _get_build_wallet(world, agent)
        return wallet.get("wood", 0) >= wood_cost and wallet.get("stone", 0) >= stone_cost

    inv = agent.inventory
    storage = village.get("storage", {})
    return (
        inv.get("wood", 0) + storage.get("wood", 0) >= wood_cost
        and inv.get("stone", 0) + storage.get("stone", 0) >= stone_cost
    )


def _pay(world: "World", agent: "Agent", wood_cost: int, stone_cost: int) -> None:
    village = world.get_village_by_id(getattr(agent, "village_id", None))
    if village is None:
        wallet = _get_build_wallet(world, agent)
        wallet["wood"] = wallet.get("wood", 0) - wood_cost
        wallet["stone"] = wallet.get("stone", 0) - stone_cost
        return

    inv = agent.inventory
    storage = village.get("storage", {})

    wood_from_inv = min(inv.get("wood", 0), wood_cost)
    stone_from_inv = min(inv.get("stone", 0), stone_cost)

    inv["wood"] = inv.get("wood", 0) - wood_from_inv
    inv["stone"] = inv.get("stone", 0) - stone_from_inv

    remaining_wood = wood_cost - wood_from_inv
    remaining_stone = stone_cost - stone_from_inv

    if remaining_wood > 0:
        storage["wood"] = storage.get("wood", 0) - remaining_wood
    if remaining_stone > 0:
        storage["stone"] = storage.get("stone", 0) - remaining_stone


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
    if not world.is_walkable(x, y):
        return False
    if (x, y) in world.structures:
        return False
    if (x, y) in getattr(world, "storage_buildings", set()):
        return False
    return True


def try_build_house(world: "World", agent: "Agent") -> bool:
    if len(world.structures) >= world.MAX_STRUCTURES:
        return False

    if not _can_pay(world, agent, HOUSE_WOOD_COST, HOUSE_STONE_COST):
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

            if score > best_score:
                best_score = score
                best_pos = (x, y)

    if best_pos is None:
        return False

    bx, by = best_pos
    world.structures.add((bx, by))
    _pay(world, agent, HOUSE_WOOD_COST, HOUSE_STONE_COST)
    world.emit_event(
        "house_built",
        {
            "agent_id": agent.agent_id,
            "x": bx,
            "y": by,
            "village_uid": world.resolve_village_uid(getattr(agent, "village_id", None)),
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

    if not can_build_at(world, sx, sy):
        replacement = _find_nearest_storage_spot(world, village, (agent.x, agent.y))
        if replacement is None:
            return False
        sx, sy = replacement
        village["storage_pos"] = {"x": sx, "y": sy}

    if not _can_pay(world, agent, STORAGE_WOOD_COST, STORAGE_STONE_COST):
        return False

    if abs(agent.x - sx) > 2 or abs(agent.y - sy) > 2:
        return False

    if not can_build_at(world, sx, sy):
        return False

    world.storage_buildings.add((sx, sy))
    _pay(world, agent, STORAGE_WOOD_COST, STORAGE_STONE_COST)
    return True
