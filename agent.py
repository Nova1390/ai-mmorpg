from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple
import random

from config import FOOD_EAT_GAIN, AGENT_START_HUNGER, REPRO_MIN_HUNGER, REPRO_PROB, REPRO_COST


@dataclass
class Agent:
    x: int
    y: int
    brain: Any
    is_player: bool = False
    player_id: Optional[str] = None

    alive: bool = True
    hunger: float = float(AGENT_START_HUNGER)

    # inventario semplice (estendibile)
    inventory: Dict[str, int] = field(default_factory=lambda: {"food": 0, "wood": 0, "stone": 0})

    # memoria percettiva
    memory: Dict[str, set] = field(default_factory=lambda: {"food": set(), "wood": set(), "stone": set()})

    # riproduzione (solo npc)
    repro_cooldown: int = 0

    def run_brain(self, world: "World") -> Tuple[str, ...]:
        """
        Ritorna un'azione come tuple:
          ("move", dx, dy) oppure ("wait",)
        """
        if self.brain is None:
            return ("wait",)

        action = self.brain.decide(self, world)

        if not action:
            return ("wait",)

        # normalizza
        if isinstance(action, tuple):
            return action

        return ("wait",)

    def eat_if_needed(self) -> None:
        """
        Se ho cibo e ho fame bassa, mangio automaticamente.
        """
        if self.inventory.get("food", 0) > 0 and self.hunger < 50:
            self.inventory["food"] -= 1
            self.hunger += FOOD_EAT_GAIN
            if self.hunger > 100:
                self.hunger = 100

    def try_reproduce(self, world: "World") -> None:
        """
        Riproduzione semplice (solo NPC): se ho abbastanza fame "alta" (energia) genero un nuovo NPC vicino.
        """
        if self.is_player:
            return

        if self.repro_cooldown > 0:
            self.repro_cooldown -= 1
            return

        if self.hunger < REPRO_MIN_HUNGER:
            return

        if random.random() > REPRO_PROB:
            return

        baby_pos = world.find_free_adjacent(self.x, self.y)
        if baby_pos is None:
            return

        bx, by = baby_pos

        baby = Agent(
            x=bx,
            y=by,
            brain=self.brain,
            is_player=False,
            player_id=None,
        )
        baby.hunger = float(AGENT_START_HUNGER)
        world.add_agent(baby)

        self.hunger -= REPRO_COST
        if self.hunger < 1:
            self.hunger = 1

        self.repro_cooldown = 8

    def update(self, world: "World") -> None:
        """
        1 tick di simulazione per l'agente.
        """
        if not self.alive:
            return

        # consumo base
        self.hunger -= 1
        if self.hunger <= 0:
            self.alive = False
            return

        # mangia se serve
        self.eat_if_needed()

        # decisione + movimento
        action = self.run_brain(world)

        if action[0] == "move":
            dx = int(action[1])
            dy = int(action[2])

            nx = self.x + dx
            ny = self.y + dy

            if world.is_walkable(nx, ny) and not world.is_occupied(nx, ny):
                self.x = nx
                self.y = ny

        # pickup garantito (anche se brain è scemo)
        world.autopickup(self)

        # mangia dopo pickup (utile quando raccoglie proprio adesso)
        self.eat_if_needed()

        # riproduzione
        self.try_reproduce(world)