from __future__ import annotations

import random
from typing import List, Optional, Set, Tuple

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


class World:
    def __init__(self):
        self.width = int(WIDTH)
        self.height = int(HEIGHT)

        self.tick = 0

        # tiles: matrice [y][x] con "G F M W"
        self.tiles: List[List[str]] = self._generate_tiles()

        # risorse (set di coordinate)
        self.food: Set[Tuple[int, int]] = set()
        self.wood: Set[Tuple[int, int]] = set()
        self.stone: Set[Tuple[int, int]] = set()

        # strutture: set di coordinate (x,y)
        self.structures: Set[Tuple[int, int]] = set()

        # agenti
        self.agents: List[Agent] = []

        # spawn iniziale risorse
        self._spawn_initial_food(NUM_FOOD)
        self._spawn_initial_wood(NUM_WOOD)
        self._spawn_initial_stone(NUM_STONE)

        # spawn NPC iniziali
        # se li spawni già da server.py, lascia NUM_AGENTS = 0 in config.py
        if NUM_AGENTS > 0:
            brain = FoodBrain()
            for _ in range(NUM_AGENTS):
                pos = self.find_random_free()
                if pos:
                    x, y = pos
                    self.add_agent(
                        Agent(x, y, brain=brain, is_player=False, player_id=None)
                    )

    # ---------------------------------------------------
    # MAP / TILES
    # ---------------------------------------------------

    def _generate_tiles(self) -> List[List[str]]:
        tiles: List[List[str]] = []
        for _y in range(self.height):
            row: List[str] = []
            for _x in range(self.width):
                r = random.random()

                # distribuzione semplice biomi
                if r < 0.08:
                    row.append("W")  # water
                elif r < 0.18:
                    row.append("M")  # mountain
                elif r < 0.40:
                    row.append("F")  # forest
                else:
                    row.append("G")  # grass

            tiles.append(row)

        return tiles

    def is_walkable(self, x: int, y: int) -> bool:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return False

        return self.tiles[y][x] != "W"

    # ---------------------------------------------------
    # AGENTS / POSITIONS
    # ---------------------------------------------------

    def is_occupied(self, x: int, y: int) -> bool:
        for a in self.agents:
            if a.alive and a.x == x and a.y == y:
                return True
        return False

    def add_agent(self, agent: Agent) -> None:
        self.agents.append(agent)

    def find_random_free(self) -> Optional[Tuple[int, int]]:
        for _ in range(2000):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            if self.is_walkable(x, y) and not self.is_occupied(x, y):
                return (x, y)
        return None

    def find_free_adjacent(self, x: int, y: int) -> Optional[Tuple[int, int]]:
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        random.shuffle(dirs)

        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if self.is_walkable(nx, ny) and not self.is_occupied(nx, ny):
                return (nx, ny)

        return None

    # ---------------------------------------------------
    # FOOD
    # ---------------------------------------------------

    def _spawn_initial_food(self, n: int) -> None:
        for _ in range(n):
            for _ in range(50):
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)

                if self.tiles[y][x] == "G":
                    self.food.add((x, y))
                    break

    def respawn_food(self) -> None:
        if len(self.food) >= MAX_FOOD:
            return

        for _ in range(FOOD_RESPAWN_PER_TICK):
            for _ in range(50):
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)

                if self.tiles[y][x] == "G":
                    self.food.add((x, y))
                    break

    def autopickup(self, agent: Agent) -> None:
        """
        Se l'agente è sopra una cella con food, lo raccoglie sempre.
        In più può mangiare subito per stabilizzare la survival.
        """
        pos = (agent.x, agent.y)

        if pos in self.food:
            self.food.remove(pos)
            agent.inventory["food"] = agent.inventory.get("food", 0) + 1

            agent.hunger += FOOD_EAT_GAIN
            if agent.hunger > 100:
                agent.hunger = 100

    # ---------------------------------------------------
    # WOOD / STONE
    # ---------------------------------------------------

    def _spawn_initial_wood(self, n: int) -> None:
        for _ in range(n):
            for _ in range(50):
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)

                if self.tiles[y][x] == "F" and (x, y) not in self.wood:
                    self.wood.add((x, y))
                    break

    def _spawn_initial_stone(self, n: int) -> None:
        for _ in range(n):
            for _ in range(50):
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)

                if self.tiles[y][x] == "M" and (x, y) not in self.stone:
                    self.stone.add((x, y))
                    break

    def respawn_wood(self) -> None:
        if len(self.wood) >= MAX_WOOD:
            return

        for _ in range(WOOD_RESPAWN_PER_TICK):
            for _ in range(50):
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)

                if self.tiles[y][x] == "F":
                    self.wood.add((x, y))
                    break

    def respawn_stone(self) -> None:
        if len(self.stone) >= MAX_STONE:
            return

        for _ in range(STONE_RESPAWN_PER_TICK):
            for _ in range(50):
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)

                if self.tiles[y][x] == "M":
                    self.stone.add((x, y))
                    break

    # ---------------------------------------------------
    # RESOURCES + BUILDING
    # ---------------------------------------------------

    def gather_resource(self, agent: Agent) -> bool:
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

    def try_build_house(self, agent: Agent) -> bool:
        if (
            agent.inventory.get("wood", 0) >= HOUSE_WOOD_COST
            and agent.inventory.get("stone", 0) >= HOUSE_STONE_COST
        ):
            pos = (agent.x, agent.y)

            if pos not in self.structures:
                self.structures.add(pos)
                agent.inventory["wood"] -= HOUSE_WOOD_COST
                agent.inventory["stone"] -= HOUSE_STONE_COST
                return True

        return False

    # ---------------------------------------------------
    # TICK
    # ---------------------------------------------------

    def update(self) -> None:
        self.tick += 1

        # respawn risorse
        self.respawn_food()
        self.respawn_wood()
        self.respawn_stone()

        # update agenti
        for agent in list(self.agents):
            if not agent.alive:
                continue

            agent.update(self)

        # cleanup morti
        self.agents = [a for a in self.agents if a.alive]

        # cap popolazione
        if len(self.agents) > MAX_AGENTS:
            extras = len(self.agents) - MAX_AGENTS

            if extras > 0:
                for a in list(self.agents):
                    if extras <= 0:
                        break

                    if not a.is_player:
                        a.alive = False
                        extras -= 1

                self.agents = [a for a in self.agents if a.alive]