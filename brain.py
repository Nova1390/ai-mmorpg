from __future__ import annotations

from typing import Optional, Tuple, Set
import random
import asyncio

from planner import Planner
from pathfinder import astar


Coord = Tuple[int, int]


class FoodBrain:
    def __init__(self, vision_radius: int = 8):
        self.vision_radius = vision_radius

    def decide(self, agent, world) -> Tuple[str, ...]:
        # strategia villaggio: piccolo bias per leader e membri
        village_strategy = ""
        if getattr(agent, "village_id", None) is not None:
            village = world.get_village_by_id(agent.village_id)
            if village:
                village_strategy = (village.get("strategy") or "").lower()

        # priorità fame sempre prima
        if agent.hunger < 60 or agent.inventory.get("food", 0) == 0:
            target = self.find_nearest(agent, world.food, "food", self.vision_radius)
            if target is not None:
                return self.move_towards(agent, world, target)

        # bias strategico
        if "food" in village_strategy:
            target = self.find_nearest(agent, world.food, "food", self.vision_radius)
            if target is not None:
                return self.move_towards(agent, world, target)

        if "wood" in village_strategy or "expand" in village_strategy or "build" in village_strategy:
            if agent.inventory.get("wood", 0) < 5:
                target = self.find_nearest(agent, world.wood, "wood", self.vision_radius)
                if target is not None:
                    return self.move_towards(agent, world, target)

        if "stone" in village_strategy or "expand" in village_strategy or "build" in village_strategy:
            if agent.inventory.get("stone", 0) < 3:
                target = self.find_nearest(agent, world.stone, "stone", self.vision_radius)
                if target is not None:
                    return self.move_towards(agent, world, target)

        # comportamento base
        if agent.inventory.get("wood", 0) < 5:
            target = self.find_nearest(agent, world.wood, "wood", self.vision_radius)
            if target is not None:
                return self.move_towards(agent, world, target)

        if agent.inventory.get("stone", 0) < 3:
            target = self.find_nearest(agent, world.stone, "stone", self.vision_radius)
            if target is not None:
                return self.move_towards(agent, world, target)

        return self.wander(agent, world)

    def find_nearest(
        self,
        agent,
        resource_set: Set[Coord],
        memory_key: str,
        radius: int,
    ) -> Optional[Coord]:
        ax = agent.x
        ay = agent.y

        best: Optional[Coord] = None
        best_d = 9999

        for (x, y) in resource_set:
            d = abs(x - ax) + abs(y - ay)

            if d <= radius and d < best_d:
                best_d = d
                best = (x, y)

        if best is not None:
            return best

        for (x, y) in agent.memory.get(memory_key, set()):
            d = abs(x - ax) + abs(y - ay)

            if d < best_d:
                best_d = d
                best = (x, y)

        return best

    def move_towards(self, agent, world, target: Coord) -> Tuple[str, ...]:
        start = (agent.x, agent.y)

        if start == target:
            return ("wait",)

        path = astar(world, start, target)

        if path is not None and len(path) >= 2:
            next_x, next_y = path[1]
            dx = next_x - agent.x
            dy = next_y - agent.y

            if world.is_walkable(next_x, next_y) and not world.is_occupied(next_x, next_y):
                return ("move", dx, dy)

        return self.greedy_step(agent, world, target)

    def greedy_step(self, agent, world, target: Coord) -> Tuple[str, ...]:
        tx, ty = target

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

        return self.wander(agent, world)

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
    def __init__(self, planner: Planner, fallback: FoodBrain, think_every_ticks: int = 120):
        self.planner = planner
        self.fallback = fallback
        self.think_every_ticks = think_every_ticks

    def decide(self, agent, world) -> Tuple[str, ...]:
        if agent.hunger < 60 or agent.inventory.get("food", 0) == 0:
            return self.fallback.decide(agent, world)

        if self._should_think(agent, world):
            self._schedule_llm_request(agent, world)

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
        print(f"LLM thinking for {agent.role}: {agent.player_id or 'npc'}")

        if hasattr(world, "record_llm_interaction"):
            world.record_llm_interaction()

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._request_goal(agent, world, prompt))
        except RuntimeError:
            agent.llm_pending = False
            print("LLM scheduling failed: no running event loop")

    async def _request_goal(self, agent, world, prompt: str) -> None:
        try:
            goal = await self.planner.propose_goal_async(prompt)
            agent.goal = goal or "survive"
            print(f"LLM goal ({agent.role}): {agent.goal}")

            # se è leader, aggiorna strategia villaggio
            if getattr(agent, "role", "") == "leader" and getattr(agent, "village_id", None) is not None:
                village = world.get_village_by_id(agent.village_id)
                if village is not None:
                    village["strategy"] = agent.goal
        except Exception as e:
            print(f"LLM error: {e}")
        finally:
            agent.llm_pending = False

    def _act_from_goal(self, agent, world) -> Tuple[str, ...]:
        g = (agent.goal or "").lower()

        if "wood" in g or "legn" in g or "tree" in g:
            if agent.inventory.get("wood", 0) < 8:
                target = self.fallback.find_nearest(
                    agent, world.wood, "wood", self.fallback.vision_radius
                )
                if target is not None:
                    return self.fallback.move_towards(agent, world, target)

        if "stone" in g or "pietr" in g or "rock" in g:
            if agent.inventory.get("stone", 0) < 6:
                target = self.fallback.find_nearest(
                    agent, world.stone, "stone", self.fallback.vision_radius
                )
                if target is not None:
                    return self.fallback.move_towards(agent, world, target)

        if "food" in g or "cibo" in g or "eat" in g or "hunt" in g:
            target = self.fallback.find_nearest(
                agent, world.food, "food", self.fallback.vision_radius
            )
            if target is not None:
                return self.fallback.move_towards(agent, world, target)

        if "expand" in g or "build" in g or "village" in g:
            # bias su wood/stone per costruire
            if agent.inventory.get("wood", 0) < 8:
                target = self.fallback.find_nearest(
                    agent, world.wood, "wood", self.fallback.vision_radius
                )
                if target is not None:
                    return self.fallback.move_towards(agent, world, target)

            if agent.inventory.get("stone", 0) < 5:
                target = self.fallback.find_nearest(
                    agent, world.stone, "stone", self.fallback.vision_radius
                )
                if target is not None:
                    return self.fallback.move_towards(agent, world, target)

        if "explore" in g or "esplora" in g:
            return self.fallback.wander(agent, world)

        return self.fallback.decide(agent, world)

    def _make_prompt(self, agent, world) -> str:
        role = getattr(agent, "role", "npc")
        village_summary = ""

        if getattr(agent, "village_id", None) is not None:
            village = world.get_village_by_id(agent.village_id)
            if village is not None:
                village_summary = (
                    f"village_id={village['id']}\n"
                    f"village_houses={village['houses']}\n"
                    f"village_population={village['population']}\n"
                    f"current_strategy={village.get('strategy', 'none')}\n"
                )

        if role == "leader":
            return (
                "You are the leader of a village in a tile world.\n"
                "Return only a short JSON object.\n"
                'Format: {"goal":"expand village|gather food|gather wood|gather stone|explore"}\n'
                f"{village_summary}"
                f"tick={world.tick}\n"
                f"position=({agent.x},{agent.y})\n"
                f"hunger={agent.hunger}\n"
                f"inventory={agent.inventory}\n"
            )

        return (
            "You are the high-level brain of a player character in a tile world.\n"
            "Return only a short JSON object.\n"
            'Format: {"goal":"gather food|gather wood|gather stone|explore"}\n'
            f"tick={world.tick}\n"
            f"position=({agent.x},{agent.y})\n"
            f"hunger={agent.hunger}\n"
            f"inventory={agent.inventory}\n"
        )