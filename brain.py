from __future__ import annotations

from typing import Optional, Tuple, Set
import random
import asyncio

from planner import Planner


class FoodBrain:
    def __init__(self, vision_radius: int = 8):
        self.vision_radius = vision_radius

    def decide(self, agent, world) -> Tuple[str, ...]:
        # 1) FOOD priority
        if agent.hunger < 60 or agent.inventory.get("food", 0) == 0:
            target = self.find_nearest(agent, world.food, self.vision_radius)
            if target is not None:
                return self.move_towards(agent, world, target)

        # 2) WOOD
        if agent.inventory.get("wood", 0) < 5:
            target = self.find_nearest(agent, world.wood, self.vision_radius)
            if target is not None:
                return self.move_towards(agent, world, target)

        # 3) STONE
        if agent.inventory.get("stone", 0) < 3:
            target = self.find_nearest(agent, world.stone, self.vision_radius)
            if target is not None:
                return self.move_towards(agent, world, target)

        return self.wander(agent, world)

    def find_nearest(
        self,
        agent,
        resource_set: Set[Tuple[int, int]],
        radius: int,
    ) -> Optional[Tuple[int, int]]:
        ax, ay = agent.x, agent.y
        best: Optional[Tuple[int, int]] = None
        best_d = 10**9

        for (x, y) in resource_set:
            d = abs(x - ax) + abs(y - ay)
            if d <= radius and d < best_d:
                best_d = d
                best = (x, y)

        return best

    def move_towards(self, agent, world, target: Tuple[int, int]) -> Tuple[str, ...]:
        tx, ty = target

        if (agent.x, agent.y) == (tx, ty):
            return ("wait",)

        options = []

        if tx > agent.x:
            options.append((1, 0))
        elif tx < agent.x:
            options.append((-1, 0))

        if ty > agent.y:
            options.append((0, 1))
        elif ty < agent.y:
            options.append((0, -1))

        random.shuffle(options)

        for dx, dy in options:
            nx, ny = agent.x + dx, agent.y + dy
            if world.is_walkable(nx, ny) and not world.is_occupied(nx, ny):
                return ("move", dx, dy)

        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        random.shuffle(dirs)

        for dx, dy in dirs:
            nx, ny = agent.x + dx, agent.y + dy
            if world.is_walkable(nx, ny) and not world.is_occupied(nx, ny):
                return ("move", dx, dy)

        return ("wait",)

    def wander(self, agent, world) -> Tuple[str, ...]:
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (0, 0)]
        random.shuffle(dirs)

        for dx, dy in dirs:
            if dx == 0 and dy == 0:
                return ("wait",)

            nx, ny = agent.x + dx, agent.y + dy
            if world.is_walkable(nx, ny) and not world.is_occupied(nx, ny):
                return ("move", dx, dy)

        return ("wait",)


class LLMBrain:
    """
    Brain ibrido:
    - survival e movimento concreto demandati a FoodBrain
    - goal alto livello aggiornato via LLM in modo non bloccante
    """

    def __init__(self, planner: Planner, fallback: FoodBrain, think_every_ticks: int = 60):
        self.planner = planner
        self.fallback = fallback
        self.think_every_ticks = think_every_ticks

    def decide(self, agent, world) -> Tuple[str, ...]:
        # survival sempre prioritaria
        if agent.hunger < 60 or agent.inventory.get("food", 0) == 0:
            return self.fallback.decide(agent, world)

        # chiedi nuovo goal solo ogni tanto e solo se non c'è già una richiesta in corso
        if self._should_think(agent, world):
            self._schedule_llm_request(agent, world)

        # usa il goal corrente per indirizzare il comportamento
        return self._act_from_goal(agent, world)

    def _should_think(self, agent, world) -> bool:
        if agent.llm_pending:
            return False
        if world.tick - agent.last_llm_tick < self.think_every_ticks:
            return False
        return True

    def _schedule_llm_request(self, agent, world) -> None:
        agent.llm_pending = True
        agent.last_llm_tick = world.tick

        prompt = self._make_prompt(agent, world)
        print(f"LLM thinking for player: {agent.player_id}")

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._request_goal(agent, prompt))
        except RuntimeError:
            # fallback di sicurezza: se per qualche motivo non c'è event loop attivo
            agent.llm_pending = False
            print(f"LLM scheduling failed for player {agent.player_id}: no running event loop")

    async def _request_goal(self, agent, prompt: str) -> None:
        try:
            goal = await self.planner.propose_goal_async(prompt)
            agent.goal = goal or "survive"
            print(f"LLM goal: {agent.goal}")
        except Exception as e:
            print(f"LLM error for player {agent.player_id}: {e}")
        finally:
            agent.llm_pending = False

    def _act_from_goal(self, agent, world) -> Tuple[str, ...]:
        g = (agent.goal or "").lower()

        if "wood" in g or "legn" in g or "tree" in g:
            if agent.inventory.get("wood", 0) < 8:
                target = self.fallback.find_nearest(
                    agent, world.wood, self.fallback.vision_radius
                )
                if target is not None:
                    return self.fallback.move_towards(agent, world, target)

        if "stone" in g or "pietr" in g or "rock" in g:
            if agent.inventory.get("stone", 0) < 6:
                target = self.fallback.find_nearest(
                    agent, world.stone, self.fallback.vision_radius
                )
                if target is not None:
                    return self.fallback.move_towards(agent, world, target)

        if "food" in g or "cibo" in g or "eat" in g or "hunt" in g:
            target = self.fallback.find_nearest(
                agent, world.food, self.fallback.vision_radius
            )
            if target is not None:
                return self.fallback.move_towards(agent, world, target)

        if "explore" in g or "esplora" in g:
            return self.fallback.wander(agent, world)

        # fallback sensato
        return self.fallback.decide(agent, world)

    def _make_prompt(self, agent, world) -> str:
        return (
            "You are the high-level brain of a player character in a tile world.\n"
            "Return only a short JSON object.\n"
            'Format: {"goal":"gather food|gather wood|gather stone|explore"}\n'
            f"tick={world.tick}\n"
            f"position=({agent.x},{agent.y})\n"
            f"hunger={agent.hunger}\n"
            f"inventory={agent.inventory}\n"
        )