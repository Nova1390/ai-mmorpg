from __future__ import annotations

from typing import Optional, Tuple
import random


class FoodBrain:
    """
    Brain semplice:
    - aggiorna memoria visiva
    - se serve cibo e lo vede: va dritto al cibo (priorità alta)
    - altrimenti: wandering leggero
    """

    def __init__(self, vision_radius: int = 6):
        self.vision_radius = vision_radius

    def decide(self, agent, world) -> Tuple[str, ...]:
        # aggiorna memoria: quello che vede entra in memoria
        self.update_memory(agent, world)

        # priorità food: se fame bassa o non ho food in inventory
        need_food = agent.hunger < 60 or agent.inventory.get("food", 0) == 0

        if need_food:
            target = self.find_nearest_food(agent, world, radius=self.vision_radius)
            if target is not None:
                tx, ty = target

                # se sono già sul target, aspetto: world.autopickup farà il resto
                if (agent.x, agent.y) == (tx, ty):
                    return ("wait",)

                return self.step_towards(agent, world, tx, ty)

        # se non serve food: roaming
        return self.wander(agent, world)

    def update_memory(self, agent, world) -> None:
        ax, ay = agent.x, agent.y
        r = self.vision_radius

        # vede food nel raggio
        for (fx, fy) in world.food:
            if abs(fx - ax) + abs(fy - ay) <= r:
                agent.memory["food"].add((fx, fy))

        # pulizia memory: se quel punto non ha più cibo, rimuovi
        # (evita target "fantasma")
        to_remove = []
        for (fx, fy) in agent.memory["food"]:
            if (fx, fy) not in world.food:
                to_remove.append((fx, fy))
        for p in to_remove:
            agent.memory["food"].discard(p)

    def find_nearest_food(self, agent, world, radius: int = 6) -> Optional[Tuple[int, int]]:
        ax, ay = agent.x, agent.y
        best = None
        best_d = 10**9

        # usa direttamente world.food (reale), non solo memory
        for (fx, fy) in world.food:
            d = abs(fx - ax) + abs(fy - ay)
            if d <= radius and d < best_d:
                best_d = d
                best = (fx, fy)

        # fallback: prova memory (nel caso)
        if best is None:
            for (fx, fy) in agent.memory["food"]:
                d = abs(fx - ax) + abs(fy - ay)
                if d <= radius and d < best_d:
                    best_d = d
                    best = (fx, fy)

        return best

    def step_towards(self, agent, world, tx: int, ty: int):
        # muovi di 1 step verso target
        dx = 0 if tx == agent.x else (1 if tx > agent.x else -1)
        dy = 0 if ty == agent.y else (1 if ty > agent.y else -1)

        # prova prima asse più “utile”
        # (preferisce ridurre la distanza manhattan)
        candidates = []
        if dx != 0:
            candidates.append((dx, 0))
        if dy != 0:
            candidates.append((0, dy))

        # alternativa per aggirare ostacoli
        random.shuffle(candidates)
        for (mx, my) in candidates:
            nx, ny = agent.x + mx, agent.y + my
            if world.is_walkable(nx, ny) and not world.is_occupied(nx, ny):
                return ("move", mx, my)

        # se bloccato: tenta 4 direzioni
        dirs = [(1,0), (-1,0), (0,1), (0,-1)]
        random.shuffle(dirs)
        for (mx, my) in dirs:
            nx, ny = agent.x + mx, agent.y + my
            if world.is_walkable(nx, ny) and not world.is_occupied(nx, ny):
                return ("move", mx, my)

        return ("wait",)

    def wander(self, agent, world):
        dirs = [(1,0), (-1,0), (0,1), (0,-1), (0,0)]
        random.shuffle(dirs)
        for (dx, dy) in dirs:
            nx, ny = agent.x + dx, agent.y + dy
            if dx == 0 and dy == 0:
                return ("wait",)
            if world.is_walkable(nx, ny) and not world.is_occupied(nx, ny):
                return ("move", dx, dy)
        return ("wait",)