from __future__ import annotations

import random
from typing import Dict, List, Optional, Set, Tuple

from config import (
    WIDTH,
    HEIGHT,
    NUM_AGENTS,
    NUM_FOOD,
    NUM_WOOD,
    NUM_STONE,
    FOOD_RESPAWN_PER_TICK,
    WOOD_RESPAWN_PER_TICK,
    STONE_RESPAWN_PER_TICK,
    MAX_FOOD,
    MAX_WOOD,
    MAX_STONE,
    FOOD_EAT_GAIN,
    MAX_AGENTS,
    HOUSE_WOOD_COST,
    HOUSE_STONE_COST,
)

from agent import Agent
from brain import FoodBrain


Coord = Tuple[int, int]

MAX_STRUCTURES = 60
MAX_HOUSES_PER_VILLAGE = 8
MAX_NEW_VILLAGE_SEEDS = 2
MIN_HOUSES_FOR_VILLAGE = 3
MIN_HOUSES_FOR_LEADER = 4


class World:
    def __init__(self):
        self.width = int(WIDTH)
        self.height = int(HEIGHT)

        self.tick = 0
        self.llm_interactions = 0

        self.tiles: List[List[str]] = self._generate_tiles()

        self.food: Set[Coord] = set()
        self.wood: Set[Coord] = set()
        self.stone: Set[Coord] = set()

        self.structures: Set[Coord] = set()
        self.villages: List[Dict] = []

        self.agents: List[Agent] = []

        self._spawn_initial_food(NUM_FOOD)
        self._spawn_initial_wood(NUM_WOOD)
        self._spawn_initial_stone(NUM_STONE)

        if NUM_AGENTS > 0:
            brain = FoodBrain()
            for _ in range(NUM_AGENTS):
                pos = self.find_random_free()
                if pos:
                    x, y = pos
                    self.add_agent(Agent(x, y, brain, False, None))

        self.detect_villages()

    # ---------------------------------------------------
    # HELPERS / METRICS
    # ---------------------------------------------------

    def record_llm_interaction(self) -> None:
        self.llm_interactions += 1

    def get_village_by_id(self, village_id: Optional[int]) -> Optional[Dict]:
        if village_id is None:
            return None

        for v in self.villages:
            if v["id"] == village_id:
                return v

        return None

    def count_leaders(self) -> int:
        return sum(
            1 for a in self.agents
            if a.alive and getattr(a, "role", "npc") == "leader"
        )

    # ---------------------------------------------------
    # MAP
    # ---------------------------------------------------

    def _generate_tiles(self) -> List[List[str]]:
        tiles: List[List[str]] = []

        for _y in range(self.height):
            row: List[str] = []

            for _x in range(self.width):
                r = random.random()

                if r < 0.08:
                    row.append("W")
                elif r < 0.18:
                    row.append("M")
                elif r < 0.40:
                    row.append("F")
                else:
                    row.append("G")

            tiles.append(row)

        return tiles

    def is_walkable(self, x: int, y: int) -> bool:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return False
        return self.tiles[y][x] != "W"

    # ---------------------------------------------------
    # AGENTS
    # ---------------------------------------------------

    def is_occupied(self, x: int, y: int) -> bool:
        for a in self.agents:
            if a.alive and a.x == x and a.y == y:
                return True
        return False

    def add_agent(self, agent: Agent):
        self.agents.append(agent)

    def find_random_free(self) -> Optional[Coord]:
        for _ in range(2000):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)

            if self.is_walkable(x, y) and not self.is_occupied(x, y):
                return (x, y)

        return None

    def find_free_adjacent(self, x: int, y: int) -> Optional[Coord]:
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        random.shuffle(dirs)

        for dx, dy in dirs:
            nx = x + dx
            ny = y + dy

            if self.is_walkable(nx, ny) and not self.is_occupied(nx, ny):
                return (nx, ny)

        return None

    # ---------------------------------------------------
    # RESOURCE SPAWN
    # ---------------------------------------------------

    def _spawn_initial_food(self, n: int):
        for _ in range(n):
            pos = self.find_random_free()
            if pos:
                self.food.add(pos)

    def _spawn_initial_wood(self, n: int):
        for _ in range(n):
            for _ in range(50):
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)
                if self.tiles[y][x] == "F" and (x, y) not in self.wood:
                    self.wood.add((x, y))
                    break

    def _spawn_initial_stone(self, n: int):
        for _ in range(n):
            for _ in range(50):
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)
                if self.tiles[y][x] == "M" and (x, y) not in self.stone:
                    self.stone.add((x, y))
                    break

    def respawn_resources(self):
        if len(self.food) < MAX_FOOD:
            for _ in range(FOOD_RESPAWN_PER_TICK):
                pos = self.find_random_free()
                if pos:
                    self.food.add(pos)

        if len(self.wood) < MAX_WOOD:
            for _ in range(WOOD_RESPAWN_PER_TICK):
                for _ in range(50):
                    x = random.randint(0, self.width - 1)
                    y = random.randint(0, self.height - 1)
                    if self.tiles[y][x] == "F":
                        self.wood.add((x, y))
                        break

        if len(self.stone) < MAX_STONE:
            for _ in range(STONE_RESPAWN_PER_TICK):
                for _ in range(50):
                    x = random.randint(0, self.width - 1)
                    y = random.randint(0, self.height - 1)
                    if self.tiles[y][x] == "M":
                        self.stone.add((x, y))
                        break

    # ---------------------------------------------------
    # RESOURCE INTERACTION
    # ---------------------------------------------------

    def autopickup(self, agent: Agent):
        pos = (agent.x, agent.y)

        if pos in self.food:
            self.food.remove(pos)
            agent.inventory["food"] = agent.inventory.get("food", 0) + 1
            agent.hunger += FOOD_EAT_GAIN
            if agent.hunger > 100:
                agent.hunger = 100

    def gather_resource(self, agent: Agent):
        pos = (agent.x, agent.y)

        if pos in self.wood:
            self.wood.remove(pos)
            agent.inventory["wood"] = agent.inventory.get("wood", 0) + 1
            return True

        if pos in self.stone:
            self.stone.remove(pos)
            agent.inventory["stone"] = agent.inventory.get("stone", 0) + 1
            return True

        return False

    # ---------------------------------------------------
    # BUILDING
    # ---------------------------------------------------

    def building_score(self, x: int, y: int) -> int:
        score = 0

        for dx in range(-2, 3):
            for dy in range(-2, 3):
                nx = x + dx
                ny = y + dy
                if (nx, ny) in self.structures:
                    score += 5

        for dx in range(-3, 4):
            for dy in range(-3, 4):
                nx = x + dx
                ny = y + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self.tiles[ny][nx] == "F":
                        score += 1

        return score

    def count_nearby_houses(self, x: int, y: int, radius: int = 5) -> int:
        count = 0
        for hx, hy in self.structures:
            if abs(hx - x) <= radius and abs(hy - y) <= radius:
                count += 1
        return count

    def count_nearby_population(self, x: int, y: int, radius: int = 6) -> int:
        count = 0
        for a in self.agents:
            if not a.alive:
                continue
            if abs(a.x - x) <= radius and abs(a.y - y) <= radius:
                count += 1
        return count

    def can_build_at(self, x: int, y: int) -> bool:
        if not self.is_walkable(x, y):
            return False
        if (x, y) in self.structures:
            return False
        return True

    def try_build_house(self, agent: Agent):
        if len(self.structures) >= MAX_STRUCTURES:
            return False

        if (
            agent.inventory.get("wood", 0) < HOUSE_WOOD_COST
            or agent.inventory.get("stone", 0) < HOUSE_STONE_COST
        ):
            return False

        best_pos = None
        best_score = -10**9

        for dx in range(-3, 4):
            for dy in range(-3, 4):
                x = agent.x + dx
                y = agent.y + dy

                if not self.can_build_at(x, y):
                    continue

                nearby_houses = self.count_nearby_houses(x, y, radius=5)
                nearby_population = self.count_nearby_population(x, y, radius=6)

                if nearby_houses >= MAX_HOUSES_PER_VILLAGE:
                    continue

                allowed_houses = nearby_population // 2 + 1
                if nearby_houses >= allowed_houses:
                    continue

                if nearby_houses == 0 and len(self.structures) >= MAX_NEW_VILLAGE_SEEDS:
                    continue

                score = self.building_score(x, y)

                if nearby_houses == 0:
                    score -= 10

                if score > best_score:
                    best_score = score
                    best_pos = (x, y)

        if best_pos is None:
            return False

        bx, by = best_pos
        self.structures.add((bx, by))
        agent.inventory["wood"] -= HOUSE_WOOD_COST
        agent.inventory["stone"] -= HOUSE_STONE_COST
        return True

    # ---------------------------------------------------
    # VILLAGES
    # ---------------------------------------------------

    def _structure_neighbors(self, pos: Coord, radius: int = 4) -> List[Coord]:
        x, y = pos
        result: List[Coord] = []

        for ox in range(-radius, radius + 1):
            for oy in range(-radius, radius + 1):
                if ox == 0 and oy == 0:
                    continue

                nx = x + ox
                ny = y + oy

                if (nx, ny) in self.structures:
                    result.append((nx, ny))

        return result

    def detect_villages(self):
        visited: Set[Coord] = set()
        villages: List[Dict] = []
        village_id = 1

        for start in self.structures:
            if start in visited:
                continue

            stack = [start]
            cluster: List[Coord] = []

            while stack:
                cur = stack.pop()
                if cur in visited:
                    continue

                visited.add(cur)
                cluster.append(cur)

                for nei in self._structure_neighbors(cur, radius=4):
                    if nei not in visited:
                        stack.append(nei)

            if len(cluster) < MIN_HOUSES_FOR_VILLAGE:
                continue

            cx = round(sum(x for x, _ in cluster) / len(cluster))
            cy = round(sum(y for _, y in cluster) / len(cluster))

            pop = 0
            for a in self.agents:
                if not a.alive:
                    continue
                if abs(a.x - cx) <= 6 and abs(a.y - cy) <= 6:
                    pop += 1

            villages.append(
                {
                    "id": village_id,
                    "center": {"x": cx, "y": cy},
                    "houses": len(cluster),
                    "population": pop,
                    "tiles": [{"x": x, "y": y} for x, y in cluster],
                    "leader_id": None,
                    "strategy": "survive",
                }
            )
            village_id += 1

        self.villages = villages
        self.assign_village_leaders()

    def assign_village_leaders(self):
        for a in self.agents:
            if not a.alive:
                continue

            if a.is_player:
                a.role = "player"
                continue

            a.role = "npc"
            a.village_id = None

        for village in self.villages:
            village_tiles = {
                (tile["x"], tile["y"])
                for tile in village.get("tiles", [])
            }

            nearby_agents = []

            for a in self.agents:
                if not a.alive or a.is_player:
                    continue

                # agente membro del villaggio se è vicino a QUALSIASI casa del cluster
                is_member = False

                for hx, hy in village_tiles:
                    if abs(a.x - hx) <= 4 and abs(a.y - hy) <= 4:
                        is_member = True
                        break

                if is_member:
                    a.village_id = village["id"]
                    nearby_agents.append(a)

            if village["houses"] < MIN_HOUSES_FOR_LEADER or not nearby_agents:
                village["leader_id"] = None
                print(
                    f"[LEADER] village={village['id']} houses={village['houses']} members={len(nearby_agents)} leader=NONE"
                )
                continue

            leader = max(
                nearby_agents,
                key=lambda a: (
                    a.hunger,
                    a.inventory.get("food", 0)
                    + a.inventory.get("wood", 0)
                    + a.inventory.get("stone", 0),
                ),
            )

            leader.role = "leader"
            leader.village_id = village["id"]
            village["leader_id"] = id(leader)

            print(
                f"[LEADER] village={village['id']} houses={village['houses']} "
                f"members={len(nearby_agents)} leader=({leader.x},{leader.y}) hunger={leader.hunger}"
            )

    # ---------------------------------------------------
    # TICK
    # ---------------------------------------------------

    def update(self):
        self.tick += 1

        self.respawn_resources()

        for agent in list(self.agents):
            if not agent.alive:
                continue
            agent.update(self)

        self.agents = [a for a in self.agents if a.alive]

        if len(self.agents) > MAX_AGENTS:
            extra = len(self.agents) - MAX_AGENTS

            for a in self.agents:
                if extra <= 0:
                    break
                if not a.is_player:
                    a.alive = False
                    extra -= 1

            self.agents = [a for a in self.agents if a.alive]

        self.detect_villages()