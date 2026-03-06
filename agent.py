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

    # inventario
    inventory: Dict[str, int] = field(
        default_factory=lambda: {"food": 0, "wood": 0, "stone": 0}
    )

    # memoria percettiva
    memory: Dict[str, set] = field(
        default_factory=lambda: {"food": set(), "wood": set(), "stone": set()}
    )

    # riproduzione
    repro_cooldown: int = 0

    # stato LLM / goal alto livello
    goal: str = "survive"
    last_llm_tick: int = 0
    llm_pending: bool = False

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
        # solo NPC
        if self.is_player:
            return

        # frena crescita popolazione
        if len(world.agents) >= int(MAX_AGENTS * 0.60):
            return

        # cooldown
        if self.repro_cooldown > 0:
            self.repro_cooldown -= 1
            return

        # energia minima
        if self.hunger < REPRO_MIN_HUNGER:
            return

        # probabilità
        if random.random() > REPRO_PROB:
            return

        pos = world.find_free_adjacent(self.x, self.y)
        if pos is None:
            return

        bx, by = pos

        baby = Agent(
            x=bx,
            y=by,
            brain=self.brain,  # NPC condividono brain veloce
            is_player=False,
            player_id=None,
        )

        baby.hunger = float(AGENT_START_HUNGER)

        world.add_agent(baby)

        # costo riproduzione
        self.hunger -= REPRO_COST
        if self.hunger < 1:
            self.hunger = 1

        # cooldown alto per evitare crescita esponenziale
        self.repro_cooldown = 80

    # ---------------------------------------------------
    # UPDATE
    # ---------------------------------------------------

    def update(self, world: "World") -> None:
        if not self.alive:
            return

        # consumo fame
        self.hunger -= 1

        if self.hunger <= 0:
            self.alive = False
            return

        # mangia se necessario
        self.eat_if_needed()

        # decisione brain
        action = self.run_brain(world)

        # movimento
        if action and action[0] == "move":
            dx = int(action[1])
            dy = int(action[2])

            nx = self.x + dx
            ny = self.y + dy

            if world.is_walkable(nx, ny) and not world.is_occupied(nx, ny):
                self.x = nx
                self.y = ny

        # interazioni col mondo
        world.autopickup(self)
        world.gather_resource(self)
        world.try_build_house(self)

        # mangia dopo eventuale raccolta
        self.eat_if_needed()

        # riproduzione
        self.try_reproduce(world)