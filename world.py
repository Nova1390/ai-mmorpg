from __future__ import annotations

import random
from typing import List, Optional, Set, Tuple

from config import (
    WIDTH,
    HEIGHT,
    NUM_AGENTS,
    NUM_FOOD,
    FOOD_RESPAWN_PER_TICK,
    MAX_FOOD,
    FOOD_EAT_GAIN,
    MAX_AGENTS,
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

        # spawn NPC iniziali (se vuoi: li spawn anche dal server.py; qui li metto per sicurezza)
        if NUM_AGENTS > 0:
            brain = FoodBrain()
            for _ in range(NUM_AGENTS):
                pos = self.find_random_free()
                if pos:
                    x, y = pos
                    self.add_agent(Agent(x, y, brain=brain, is_player=False, player_id=None))

    def _generate_tiles(self) -> List[List[str]]:
        tiles = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                r = random.random()
                # acqua un po' rara
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
        dirs = [(1,0), (-1,0), (0,1), (0,-1)]
        random.shuffle(dirs)
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if self.is_walkable(nx, ny) and not self.is_occupied(nx, ny):
                return (nx, ny)
        return None

    def _spawn_initial_food(self, n: int) -> None:
        for _ in range(n):
            pos = self.find_random_free()
            if pos is None:
                break
            self.food.add(pos)

    def respawn_food(self) -> None:
        # Respawn cibo
        if len(self.food) < MAX_FOOD:
            for _ in range(FOOD_RESPAWN_PER_TICK):
                if len(self.food) >= MAX_FOOD:
                    break
                pos = self.find_random_free()
                if pos is not None:
                    self.food.add(pos)

    def autopickup(self, agent: Agent) -> None:
        """
        HARD GUARANTEE: se l'agente sta su una cella col food, lo prende sempre.
        In più, può mangiare subito (evita morti stupide).
        """
        pos = (agent.x, agent.y)
        if pos in self.food:
            self.food.remove(pos)
            agent.inventory["food"] = agent.inventory.get("food", 0) + 1

            # opzionale: mangia subito (super utile per survival)
            agent.hunger += FOOD_EAT_GAIN
            if agent.hunger > 100:
                agent.hunger = 100

    def update(self) -> None:
        self.tick += 1

        # respawn risorse
        self.respawn_food()

        # update agenti (copia lista per sicurezza)
        alive_now = 0
        for agent in list(self.agents):
            if not agent.alive:
                continue

            agent.update(self)

            if agent.alive:
                alive_now += 1

        # cleanup morti (mantiene lista più leggera)
        self.agents = [a for a in self.agents if a.alive]

        # cap popolazione
        if len(self.agents) > MAX_AGENTS:
            # elimina NPC extra (non player) per sicurezza
            extras = len(self.agents) - MAX_AGENTS
            if extras > 0:
                for a in list(self.agents):
                    if extras <= 0:
                        break
                    if not a.is_player:
                        a.alive = False
                        extras -= 1
                self.agents = [a for a in self.agents if a.alive]