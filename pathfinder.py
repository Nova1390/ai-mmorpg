from __future__ import annotations

import heapq
from typing import Dict, List, Optional, Tuple


Coord = Tuple[int, int]


def heuristic(a: Coord, b: Coord) -> float:
    # Lower-bound based on minimum movement cost (logistics corridors ~= 0.35).
    return 0.35 * (abs(a[0] - b[0]) + abs(a[1] - b[1]))


def reconstruct_path(came_from: Dict[Coord, Coord], current: Coord) -> List[Coord]:
    path = [current]

    while current in came_from:
        current = came_from[current]
        path.append(current)

    path.reverse()
    return path


def get_neighbors(world, node: Coord) -> List[Coord]:
    x, y = node
    candidates = [
        (x + 1, y),
        (x - 1, y),
        (x, y + 1),
        (x, y - 1),
    ]

    result: List[Coord] = []

    for nx, ny in candidates:
        if world.is_walkable(nx, ny):
            result.append((nx, ny))

    return result


def astar(world, start: Coord, goal: Coord, max_nodes: int = 2000) -> Optional[List[Coord]]:
    """
    Ritorna una lista di coordinate da start a goal inclusi.
    Se non trova un path, ritorna None.
    """

    if start == goal:
        return [start]

    open_heap: List[Tuple[float, float, Coord]] = []
    heapq.heappush(open_heap, (heuristic(start, goal), 0, start))

    came_from: Dict[Coord, Coord] = {}

    g_score: Dict[Coord, float] = {start: 0.0}
    visited = 0

    while open_heap:
        _, current_g, current = heapq.heappop(open_heap)
        visited += 1

        if visited > max_nodes:
            return None

        if current == goal:
            return reconstruct_path(came_from, current)

        for neighbor in get_neighbors(world, current):
            move_cost = float(getattr(world, "movement_cost", lambda x, y: 1.0)(neighbor[0], neighbor[1]))
            tentative_g = current_g + move_cost

            if tentative_g < g_score.get(neighbor, 10**9):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + heuristic(neighbor, goal)
                heapq.heappush(open_heap, (f_score, tentative_g, neighbor))

    return None
