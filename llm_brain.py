from __future__ import annotations

from typing import Optional, Tuple, Set
import random
import asyncio

from planner import Planner


class FoodBrain:
    def __init__(self, vision_radius: int = 8):
        self.vision_radius = vision_radius

    def decide(self, agent, world) -> Tuple[str, ...]:
        if agent.hunger < 60 or agent.inventory.get("food", 0) == 0:
            target = self.find_nearest(agent, world.food, self.vision_radius)
            if target is not None:
                return self.move_towards(agent, world, target)

        if agent.inventory.get("wood", 0) < 5:
            target = self.find_nearest(agent, world.wood, self.vision_radius)
            if target is not None:
                return self.move_towards(agent, world, target)

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
    def __init__(self, planner: Planner, fallback: FoodBrain, think_every_ticks: int = 30):
        self.planner = planner
        self.fallback = fallback
        self.think_every_ticks = think_every_ticks

    def decide(self, agent, world) -> Tuple[str, ...]:
        # survival prima di tutto
        if agent.hunger < 60 or agent.inventory.get("food", 0) == 0:
            return self.fallback.decide(agent, world)

        # trigger non bloccante
        if (
            world.tick - agent.last_llm_tick >= self.think_every_ticks
            and not agent.llm_pending
        ):
            agent.last_llm_tick = world.tick
            agent.llm_pending = True
            prompt = self._make_prompt(agent, world)

            print(f"LLM thinking for player: {agent.player_id}")

            asyncio.create_task(self._request_goal(agent, prompt))

        # usa il goal corrente senza bloccare
        g = (agent.goal or "").lower()

        if "wood" in g or "legn" in g or "tree" in g:
            if agent.inventory.get("wood", 0) < 8:
                target = self.fallback.find_nearest(agent, world.wood, self.fallback.vision_radius)
                if target is not None:
                    return self.fallback.move_towards(agent, world, target)

        if "stone" in g or "pietr" in g or "rock" in g:
            if agent.inventory.get("stone", 0) < 6:
                target = self.fallback.find_nearest(agent, world.stone, self.fallback.vision_radius)
                if target is not None:
                    return self.fallback.move_towards(agent, world, target)

        if "food" in g or "cibo" in g or "eat" in g or "hunt" in g:
            target = self.fallback.find_nearest(agent, world.food, self.fallback.vision_radius)
            if target is not None:
                return self.fallback.move_towards(agent, world, target)

        return self.fallback.decide(agent, world)

    async def _request_goal(self, agent, prompt: str) -> None:
        try:
            goal = await self.planner.propose_goal_async(prompt)
            agent.goal = goal or "survive"
            print(f"LLM goal: {agent.goal}")
        except Exception as e:
            print(f"LLM error for player {agent.player_id}: {e}")
        finally:
            agent.llm_pending = False

    def _make_prompt(self, agent, world) -> str:
        return (
            "You are the brain of a player character in a small tile world.\n"
            "Return a VERY SHORT goal for the next seconds.\n"
            "Answer as JSON: {\"goal\":\"...\"}\n"
            f"Tick={world.tick}\n"
            f"Position=({agent.x},{agent.y})\n"
            f"Hunger={agent.hunger}\n"
            f"Inventory={agent.inventory}\n"
            "Possible goals: gather food, gather wood, gather stone, explore.\n"
        )