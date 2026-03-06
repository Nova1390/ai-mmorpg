from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple
import random

from config import (
    FOOD_EAT_GAIN,
    AGENT_START_HUNGER,
    REPRO_MIN_HUNGER,
    REPRO_PROB,
    REPRO_COST,
    MAX_AGENTS,
)


@dataclass
class Agent:
    x: int
    y: int
    brain: Any
    is_player: bool = False
    player_id: Optional[str] = None

    alive: bool = True
    hunger: float = float(AGENT_START_HUNGER)

    inventory: Dict[str, int] = field(
        default_factory=lambda: {"food": 0, "wood": 0, "stone": 0}
    )

    memory: Dict[str, set] = field(
        default_factory=lambda: {
            "food": set(),
            "wood": set(),
            "stone": set(),
            "villages": set(),
        }
    )

    repro_cooldown: int = 0

    # stato LLM / goal alto livello
    goal: str = "survive"
    last_llm_tick: int = 0
    llm_pending: bool = False

    # civ / villaggio
    role: str = "npc"          # npc | leader | player
    village_id: Optional[int] = None

    # ---------------------------------------------------
    # MEMORY
    # ---------------------------------------------------

    def update_memory(self, world: "World") -> None:
        vision = 6

        for dx in range(-vision, vision + 1):
            for dy in range(-vision, vision + 1):
                x = self.x + dx
                y = self.y + dy

                if x < 0 or y < 0 or x >= world.width or y >= world.height:
                    continue

                pos = (x, y)

                if pos in world.food:
                    self.memory["food"].add(pos)

                if pos in world.wood:
                    self.memory["wood"].add(pos)

                if pos in world.stone:
                    self.memory["stone"].add(pos)

        for village in getattr(world, "villages", []):
            center = village.get("center")
            if not center:
                continue

            vx = center.get("x")
            vy = center.get("y")

            if vx is None or vy is None:
                continue

            if abs(vx - self.x) <= vision * 2 and abs(vy - self.y) <= vision * 2:
                self.memory["villages"].add((vx, vy))

    def cleanup_memory(self, world: "World") -> None:
        self.memory["food"] = {
            p for p in self.memory["food"] if p in world.food
        }

        self.memory["wood"] = {
            p for p in self.memory["wood"] if p in world.wood
        }

        self.memory["stone"] = {
            p for p in self.memory["stone"] if p in world.stone
        }

        valid_village_centers = set()

        for village in getattr(world, "villages", []):
            center = village.get("center")
            if center and "x" in center and "y" in center:
                valid_village_centers.add((center["x"], center["y"]))

        self.memory["villages"] = {
            p for p in self.memory["villages"] if p in valid_village_centers
        }

    # ---------------------------------------------------
    # BRAIN
    # ---------------------------------------------------

    def run_brain(self, world: "World") -> Tuple[str, ...]:
        if self.brain is None:
            return ("wait",)

        action = self.brain.decide(self, world)

        if not action:
            return ("wait",)

        if isinstance(action, tuple):
            return action

        return ("wait",)

    # ---------------------------------------------------
    # FOOD
    # ---------------------------------------------------

    def eat_if_needed(self) -> None:
        if self.inventory.get("food", 0) > 0 and self.hunger < 50:
            self.inventory["food"] -= 1
            self.hunger += FOOD_EAT_GAIN

            if self.hunger > 100:
                self.hunger = 100

    # ---------------------------------------------------
    # REPRODUCTION
    # ---------------------------------------------------

    def try_reproduce(self, world: "World") -> None:
        if self.is_player:
            return

        if len(world.agents) >= int(MAX_AGENTS * 0.60):
            return

        if self.repro_cooldown > 0:
            self.repro_cooldown -= 1
            return

        if self.hunger < REPRO_MIN_HUNGER:
            return

        if random.random() > REPRO_PROB:
            return

        pos = world.find_free_adjacent(self.x, self.y)
        if pos is None:
            return

        bx, by = pos

        baby = Agent(
            x=bx,
            y=by,
            brain=self.brain,
            is_player=False,
            player_id=None,
        )

        baby.hunger = float(AGENT_START_HUNGER)
        baby.role = "npc"
        baby.village_id = self.village_id

        world.add_agent(baby)

        self.hunger -= REPRO_COST
        if self.hunger < 1:
            self.hunger = 1

        self.repro_cooldown = 80

    # ---------------------------------------------------
    # UPDATE
    # ---------------------------------------------------

    def update(self, world: "World") -> None:
        if not self.alive:
            return

        self.update_memory(world)
        self.cleanup_memory(world)

        self.hunger -= 1

        if self.hunger <= 0:
            self.alive = False
            return

        self.eat_if_needed()

        action = self.run_brain(world)

        if action and action[0] == "move":
            dx = int(action[1])
            dy = int(action[2])

            nx = self.x + dx
            ny = self.y + dy

            if world.is_walkable(nx, ny) and not world.is_occupied(nx, ny):
                self.x = nx
                self.y = ny

        world.autopickup(self)
        world.gather_resource(self)
        world.try_build_house(self)

        self.eat_if_needed()
        self.try_reproduce(world)