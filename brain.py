from __future__ import annotations

from typing import Optional, Tuple, Set
import random
import asyncio
import logging

from planner import Planner
from pathfinder import astar
from config import HOUSE_WOOD_COST, HOUSE_STONE_COST
from systems.building_system import STORAGE_WOOD_COST, STORAGE_STONE_COST


Coord = Tuple[int, int]
logger = logging.getLogger(__name__)

VALID_GOALS = {
    "expand village",
    "gather food",
    "gather wood",
    "gather stone",
    "explore",
    "build storage",
    "build house",
    "improve logistics",
    "stabilize",
    "survive",
}

ALLOWED_PRIORITIES = {
    "secure_food",
    "build_storage",
    "build_housing",
    "expand_farms",
    "improve_logistics",
    "stabilize",
}


def phase_allowed_priorities(village: Optional[dict]) -> Set[str]:
    phase = (village or {}).get("phase", "survival")
    mapping = {
        "bootstrap": {"expand_farms", "build_housing"},
        "survival": {"secure_food", "expand_farms"},
        "stabilize": {"expand_farms", "build_housing", "improve_logistics", "stabilize"},
        "growth": {"build_housing", "improve_logistics", "expand_farms", "stabilize"},
        "expansion": {"improve_logistics", "build_housing", "stabilize", "expand_farms"},
    }
    return mapping.get(phase, ALLOWED_PRIORITIES)


def clamp_priority_to_phase(village: Optional[dict], priority: str) -> str:
    p = normalize_priority(priority or "") or "stabilize"
    if p == "build_storage" and village is not None:
        storage_exists = bool(village.get("metrics", {}).get("storage_exists", False))
        if not storage_exists:
            return "build_storage"
    allowed = phase_allowed_priorities(village)
    if p in allowed:
        return p

    phase = (village or {}).get("phase", "survival")
    fallback_by_phase = {
        "bootstrap": "expand_farms",
        "survival": "secure_food",
        "stabilize": "stabilize",
        "growth": "build_housing",
        "expansion": "improve_logistics",
    }
    fallback = fallback_by_phase.get(phase, "stabilize")
    if fallback in allowed:
        return fallback

    ordered = (
        "secure_food",
        "build_storage",
        "build_housing",
        "expand_farms",
        "improve_logistics",
        "stabilize",
    )
    for candidate in ordered:
        if candidate in allowed:
            return candidate
    return "stabilize"


def normalize_goal(text: str) -> Optional[str]:
    t = (text or "").strip().lower()

    if not t:
        return None

    if "wood" in t or "legn" in t or "tree" in t:
        return "gather wood"

    if "stone" in t or "rock" in t or "pietr" in t:
        return "gather stone"

    if "food" in t or "hunt" in t or "eat" in t or "cibo" in t or "farm" in t:
        return "gather food"

    if "storage" in t or "granary" in t:
        return "build storage"

    if "house" in t or "housing" in t:
        return "build house"

    if "road" in t or "logistic" in t:
        return "improve logistics"

    if "stabil" in t:
        return "stabilize"

    if "expand" in t or "build" in t or "village" in t:
        return "expand village"

    if "explore" in t or "esplora" in t:
        return "explore"

    if t in VALID_GOALS:
        return t

    return None


def normalize_priority(text: str) -> Optional[str]:
    t = (text or "").strip().lower()
    if not t:
        return None
    if "food" in t or "hunger" in t or "secure_food" in t:
        return "secure_food"
    if "storage" in t or "granary" in t:
        return "build_storage"
    if "housing" in t or "house" in t:
        return "build_housing"
    if "farm" in t:
        return "expand_farms"
    if "logistic" in t or "road" in t:
        return "improve_logistics"
    if "stabil" in t:
        return "stabilize"
    if t in ALLOWED_PRIORITIES:
        return t
    return None


def deterministic_priority_from_needs(
    needs: dict,
    traits: Optional[dict] = None,
    village: Optional[dict] = None,
) -> str:
    scores = {p: 0 for p in ALLOWED_PRIORITIES}

    if needs.get("food_urgent"):
        scores["secure_food"] += 7
    if needs.get("food_low"):
        scores["secure_food"] += 3
    if needs.get("need_storage"):
        scores["build_storage"] += 6
    if needs.get("need_housing"):
        scores["build_housing"] += 5
    if needs.get("need_farms"):
        scores["expand_farms"] += 4
    if needs.get("need_roads"):
        scores["improve_logistics"] += 3
    scores["stabilize"] += 1

    t = traits or {}
    temperament = t.get("temperament", "")
    focus = t.get("focus", "")
    style = t.get("style", "")

    if temperament == "cautious":
        scores["secure_food"] += 2
        scores["build_storage"] += 2
        scores["stabilize"] += 1
    elif temperament == "ambitious":
        scores["expand_farms"] += 2
        scores["build_housing"] += 2
        scores["improve_logistics"] += 1
    else:  # balanced
        scores["stabilize"] += 1

    if focus == "food":
        scores["secure_food"] += 2
    elif focus == "housing":
        scores["build_housing"] += 2
    elif focus == "logistics":
        scores["build_storage"] += 1
        scores["improve_logistics"] += 2
    elif focus == "expansion":
        scores["expand_farms"] += 2
        scores["build_housing"] += 1

    if style == "conservative":
        scores["secure_food"] += 1
        scores["build_storage"] += 1
    elif style == "opportunistic":
        scores["improve_logistics"] += 1
        scores["expand_farms"] += 1
    else:  # adaptive
        if needs.get("need_storage") and needs.get("food_low"):
            scores["build_storage"] += 1

    # Phase-aware bias to prevent sterile secure_food loops.
    if village is not None:
        metrics = village.get("metrics", {})
        farms = int(metrics.get("active_farms", 0))
        storage_exists = bool(metrics.get("storage_exists", False))
        if farms <= 0:
            scores["expand_farms"] += 6
            scores["secure_food"] += 1
        elif farms >= 2 and not storage_exists:
            scores["build_storage"] += 7

        allowed = phase_allowed_priorities(village)
        for p in list(scores.keys()):
            if p not in allowed:
                scores[p] -= 50

    ordered = (
        "secure_food",
        "build_storage",
        "build_housing",
        "expand_farms",
        "improve_logistics",
        "stabilize",
    )
    return max(ordered, key=lambda p: (scores[p], -ordered.index(p)))


def strategy_from_priority(priority: str) -> str:
    p = (priority or "stabilize").strip().lower()
    if p == "secure_food":
        return "gather food"
    if p == "build_storage":
        return "build storage"
    if p == "build_housing":
        return "build house"
    if p == "expand_farms":
        return "gather food"
    if p == "improve_logistics":
        return "improve logistics"
    return "stabilize"


def apply_phase_guardrails(village: dict, proposed: str) -> str:
    metrics = village.get("metrics", {})
    needs = village.get("needs", {})
    farms = int(metrics.get("active_farms", 0))
    storage_exists = bool(metrics.get("storage_exists", False))

    if needs.get("food_buffer_critical"):
        return clamp_priority_to_phase(village, "secure_food")
    if (
        needs.get("food_buffer_low")
        and not needs.get("food_surplus")
        and not needs.get("secure_food_deescalate")
    ):
        return clamp_priority_to_phase(village, "secure_food")

    # Phase 1: village exists but no farming base yet -> push to farms.
    min_farms_target = max(3, int(village.get("population", 0) // 3))

    if farms < min_farms_target:
        if proposed in ("secure_food", "expand_farms", "stabilize"):
            return "expand_farms"
        if needs.get("food_urgent"):
            return "expand_farms"

    # Phase 2: farming base established but no storage -> prioritize storage.
    if farms >= 2 and not storage_exists:
        return clamp_priority_to_phase(village, "build_storage")

    return clamp_priority_to_phase(village, proposed)


def apply_village_priority(village: dict, priority: str, tick: int, source: str) -> None:
    p = apply_phase_guardrails(village, priority)
    village["priority"] = p
    village["strategy"] = strategy_from_priority(p)
    history = village.get("priority_history", [])
    history.append({"tick": tick, "priority": p, "source": source})
    village["priority_history"] = history[-6:]


class FoodBrain:
    def __init__(self, vision_radius: int = 8):
        self.vision_radius = vision_radius

    def decide(self, agent, world) -> Tuple[str, ...]:
        task = str(getattr(agent, "task", "idle")).lower()

        # -----------------------------
        # 1) bootstrap founding
        # -----------------------------
        if task == "bootstrap_gather":
            is_founder = bool(getattr(agent, "founder", False))
            bootstrap_radius = max(world.width, world.height) if is_founder else (self.vision_radius + 10)

            # strict order: wood -> stone -> emergency food
            if agent.inventory.get("wood", 0) < HOUSE_WOOD_COST:
                target = self.find_nearest(agent, world.wood, "wood", bootstrap_radius)
                if target is not None:
                    return self.move_towards(agent, world, target)

            if agent.inventory.get("stone", 0) < HOUSE_STONE_COST:
                target = self.find_nearest(agent, world.stone, "stone", bootstrap_radius)
                if target is not None:
                    return self.move_towards(agent, world, target)

            if agent.hunger < 45:
                target = self.find_nearest(agent, world.food, "food", self.vision_radius + 2)
                if target is not None:
                    return self.move_towards(agent, world, target)

            target_hint = getattr(agent, "task_target", None)
            if target_hint is not None:
                return self.move_towards(agent, world, target_hint)

            return self.wander(agent, world)

        if task == "bootstrap_build_house":
            village_home = self._get_known_village_center(agent, world)
            if village_home is not None and random.random() < 0.45:
                return self.move_towards(agent, world, village_home)

            target_hint = getattr(agent, "task_target", None)
            if target_hint is not None:
                return self.move_towards(agent, world, target_hint)

            if world.structures:
                nearest_structure = min(
                    world.structures,
                    key=lambda p: abs(p[0] - agent.x) + abs(p[1] - agent.y),
                )
                return self.move_towards(agent, world, nearest_structure)

            return self.wander(agent, world)

        # -----------------------------
        # 2) task-guided logic
        # -----------------------------
        if task == "farm_cycle":
            village = world.get_village_by_id(getattr(agent, "village_id", None))
            wallet = village.get("storage", {}) if village else agent.inventory

            if wallet.get("wood", 0) < 1:
                target = self.find_nearest(agent, world.wood, "wood", max(world.width, world.height))
                if target is not None:
                    return self.move_towards(agent, world, target)

            farm_target = self.find_farm_target(agent, world, prefer_ripe=True)
            if farm_target is not None:
                return self.move_towards(agent, world, farm_target)

            build_pos = self.find_farm_build_target(agent, world)
            if build_pos is not None:
                return self.move_towards(agent, world, build_pos)

        if task == "mine_cycle":
            assigned_id = getattr(agent, "assigned_building_id", None)
            if assigned_id is not None:
                building = getattr(world, "buildings", {}).get(assigned_id)
                if isinstance(building, dict):
                    anchor = building.get("linked_resource_anchor")
                    if isinstance(anchor, dict) and "x" in anchor and "y" in anchor:
                        return self.move_towards(agent, world, (int(anchor["x"]), int(anchor["y"])))
            target = self.find_nearest(agent, world.stone, "stone", self.vision_radius + 5)
            if target is not None:
                return self.move_towards(agent, world, target)

        if task == "lumber_cycle":
            assigned_id = getattr(agent, "assigned_building_id", None)
            if assigned_id is not None:
                building = getattr(world, "buildings", {}).get(assigned_id)
                if isinstance(building, dict):
                    anchor = building.get("linked_resource_anchor")
                    if isinstance(anchor, dict) and "x" in anchor and "y" in anchor:
                        return self.move_towards(agent, world, (int(anchor["x"]), int(anchor["y"])))
            target = self.find_nearest(agent, world.wood, "wood", self.vision_radius + 5)
            if target is not None:
                return self.move_towards(agent, world, target)

        if task == "build_storage":
            village = world.get_village_by_id(getattr(agent, "village_id", None))
            if village:
                gather_radius = max(world.width, world.height)
                storage = village.get("storage", {})
                inv = agent.inventory
                wood_missing = max(0, STORAGE_WOOD_COST - int(inv.get("wood", 0)))
                stone_missing = max(0, STORAGE_STONE_COST - int(inv.get("stone", 0)))
                if wood_missing > 0 or stone_missing > 0:
                    sp = village.get("storage_pos")
                    if sp and (abs(agent.x - sp["x"]) + abs(agent.y - sp["y"]) > 1):
                        return self.move_towards(agent, world, (sp["x"], sp["y"]))
                if storage.get("wood", 0) < wood_missing:
                    target = self.find_nearest(agent, world.wood, "wood", gather_radius)
                    if target is not None:
                        return self.move_towards(agent, world, target)

                if storage.get("stone", 0) < stone_missing:
                    target = self.find_nearest(agent, world.stone, "stone", gather_radius)
                    if target is not None:
                        return self.move_towards(agent, world, target)

                storage_pos = village.get("storage_pos")
                if storage_pos:
                    return self.move_towards(agent, world, (storage_pos["x"], storage_pos["y"]))

        if task == "build_house":
            if (
                agent.inventory.get("wood", 0) < HOUSE_WOOD_COST
                or agent.inventory.get("stone", 0) < HOUSE_STONE_COST
            ):
                village = world.get_village_by_id(getattr(agent, "village_id", None))
                if village:
                    sp = village.get("storage_pos")
                    if sp:
                        return self.move_towards(agent, world, (sp["x"], sp["y"]))
            village_home = self._get_known_village_center(agent, world)
            if village_home is not None:
                return self.move_towards(agent, world, village_home)

        if task == "gather_materials":
            village = world.get_village_by_id(getattr(agent, "village_id", None))
            needs = village.get("needs", {}) if village else {}
            wallet = village.get("storage", {}) if village else {"wood": 0, "stone": 0}

            if needs.get("need_storage") or needs.get("need_housing") or needs.get("need_materials"):
                if wallet.get("wood", 0) < 4:
                    target = self.find_nearest(agent, world.wood, "wood", self.vision_radius + 4)
                    if target is not None:
                        return self.move_towards(agent, world, target)

                if wallet.get("stone", 0) < 2:
                    target = self.find_nearest(agent, world.stone, "stone", self.vision_radius + 4)
                    if target is not None:
                        return self.move_towards(agent, world, target)

        if task == "gather_food_wild":
            target = self.find_nearest(agent, world.food, "food", self.vision_radius + 3)
            if target is not None:
                return self.move_towards(agent, world, target)

        if task == "food_logistics":
            if agent.inventory.get("food", 0) > 0:
                village = world.get_village_by_id(getattr(agent, "village_id", None))
                if village:
                    sp = village.get("storage_pos")
                    if sp:
                        return self.move_towards(agent, world, (sp["x"], sp["y"]))

            farm_target = self.find_farm_target(agent, world, prefer_ripe=True)
            if farm_target is not None:
                return self.move_towards(agent, world, farm_target)

            village_home = self._get_known_village_center(agent, world)
            if village_home is not None:
                return self.move_towards(agent, world, village_home)

        if task == "village_logistics":
            transfer_source = getattr(agent, "transfer_source_storage_id", None)
            transfer_target = getattr(agent, "transfer_target_storage_id", None)
            transfer_resource = str(getattr(agent, "transfer_resource_type", ""))
            transfer_amount = int(getattr(agent, "transfer_amount", 0) or 0)
            if transfer_source and transfer_target and transfer_resource in {"food", "wood", "stone"} and transfer_amount > 0:
                source_building = getattr(world, "buildings", {}).get(str(transfer_source))
                target_building = getattr(world, "buildings", {}).get(str(transfer_target))
                if isinstance(source_building, dict) and isinstance(target_building, dict):
                    if int(agent.inventory.get(transfer_resource, 0)) > 0:
                        return self.move_towards(
                            agent,
                            world,
                            (int(target_building.get("x", 0)), int(target_building.get("y", 0))),
                        )
                    return self.move_towards(
                        agent,
                        world,
                        (int(source_building.get("x", 0)), int(source_building.get("y", 0))),
                    )

            delivery_target = getattr(agent, "delivery_target_building_id", None)
            delivery_resource = getattr(agent, "delivery_resource_type", None)
            delivery_reserved = int(getattr(agent, "delivery_reserved_amount", 0) or 0)
            if delivery_target and delivery_resource in {"wood", "stone", "food"} and delivery_reserved > 0:
                building = getattr(world, "buildings", {}).get(str(delivery_target))
                if isinstance(building, dict):
                    if agent.inventory.get(delivery_resource, 0) > 0:
                        return self.move_towards(agent, world, (int(building.get("x", 0)), int(building.get("y", 0))))
                    village = world.get_village_by_id(getattr(agent, "village_id", None))
                    if village:
                        sp = village.get("storage_pos")
                        if sp:
                            return self.move_towards(agent, world, (sp["x"], sp["y"]))

            if (
                agent.inventory.get("food", 0) > 0
                or agent.inventory.get("wood", 0) > 0
                or agent.inventory.get("stone", 0) > 0
            ):
                village = world.get_village_by_id(getattr(agent, "village_id", None))
                if village:
                    sp = village.get("storage_pos")
                    if sp:
                        return self.move_towards(agent, world, (sp["x"], sp["y"]))

            farm_target = self.find_farm_target(agent, world, prefer_ripe=True)
            if farm_target is not None:
                return self.move_towards(agent, world, farm_target)

            village = world.get_village_by_id(getattr(agent, "village_id", None))
            needs = village.get("needs", {}) if village else {}
            if needs.get("need_materials"):
                wood_target = self.find_nearest(agent, world.wood, "wood", self.vision_radius + 6)
                stone_target = self.find_nearest(agent, world.stone, "stone", self.vision_radius + 6)
                if wood_target is not None and stone_target is not None:
                    dw = abs(wood_target[0] - agent.x) + abs(wood_target[1] - agent.y)
                    ds = abs(stone_target[0] - agent.x) + abs(stone_target[1] - agent.y)
                    return self.move_towards(agent, world, wood_target if dw <= ds else stone_target)
                if wood_target is not None:
                    return self.move_towards(agent, world, wood_target)
                if stone_target is not None:
                    return self.move_towards(agent, world, stone_target)

            village_home = self._get_known_village_center(agent, world)
            if village_home is not None and random.random() < 0.5:
                return self.move_towards(agent, world, village_home)

        if task == "manage_village":
            village_home = self._get_known_village_center(agent, world)
            if village_home is not None and random.random() < 0.7:
                return self.move_towards(agent, world, village_home)

        # -----------------------------
        # 3) general village/world logic
        # -----------------------------
        village_strategy = self._get_village_strategy(agent, world)
        village = world.get_village_by_id(getattr(agent, "village_id", None))
        relation = (village.get("relation", "") if village else "").lower()

        # survival sempre prima
        if agent.hunger < 60 or agent.inventory.get("food", 0) == 0:
            farm_target = self.find_farm_target(agent, world, prefer_ripe=True)
            if farm_target is not None:
                return self.move_towards(agent, world, farm_target)

            target = self.find_nearest(agent, world.food, "food", self.vision_radius)
            if target is not None:
                return self.move_towards(agent, world, target)

        # migrazione
        if relation == "migrate" and village:
            migration_target_id = village.get("migration_target_id")
            migration_target = world.get_village_by_id(migration_target_id)
            if migration_target:
                center = migration_target.get("center")
                if center:
                    return self.move_towards(agent, world, (center["x"], center["y"]))

        # guerra
        if relation == "war" and village:
            target_village_id = village.get("target_village_id")
            enemy = world.get_village_by_id(target_village_id)
            if enemy:
                center = enemy.get("center")
                if center and random.random() < 0.45:
                    return self.move_towards(agent, world, (center["x"], center["y"]))

        # strategia del villaggio
        if village_strategy:
            action = self._decide_from_strategy(agent, world, village_strategy)
            if action is not None:
                return action

        # comportamento base
        if agent.inventory.get("wood", 0) < 5:
            target = self.find_nearest(agent, world.wood, "wood", self.vision_radius)
            if target is not None:
                return self.move_towards(agent, world, target)

        if agent.inventory.get("stone", 0) < 3:
            target = self.find_nearest(agent, world.stone, "stone", self.vision_radius)
            if target is not None:
                return self.move_towards(agent, world, target)

        village_home = self._get_known_village_center(agent, world)
        if village_home is not None and random.random() < 0.35:
            return self.move_towards(agent, world, village_home)

        return self.wander(agent, world)

    def _get_village_strategy(self, agent, world) -> str:
        village_id = getattr(agent, "village_id", None)
        if village_id is None:
            return ""

        village = world.get_village_by_id(village_id)
        if not village:
            return ""

        return str(village.get("strategy", "")).lower().strip()

    def _get_known_village_center(self, agent, world) -> Optional[Coord]:
        village_id = getattr(agent, "village_id", None)
        if village_id is not None:
            village = world.get_village_by_id(village_id)
            if village:
                c = village.get("center")
                if c:
                    return (c["x"], c["y"])

        mem = agent.memory.get("villages", set())
        if mem:
            ax, ay = agent.x, agent.y
            return min(mem, key=lambda p: abs(p[0] - ax) + abs(p[1] - ay))

        return None

    def _decide_from_strategy(self, agent, world, strategy: str) -> Optional[Tuple[str, ...]]:
        if "food" in strategy or "hunt" in strategy or "eat" in strategy or "farm" in strategy:
            farm_target = self.find_farm_target(agent, world, prefer_ripe=True)
            if farm_target is not None:
                return self.move_towards(agent, world, farm_target)

            target = self.find_nearest(agent, world.food, "food", self.vision_radius + 2)
            if target is not None:
                return self.move_towards(agent, world, target)

        if "wood" in strategy or "tree" in strategy or "legn" in strategy:
            target = self.find_nearest(agent, world.wood, "wood", self.vision_radius + 2)
            if target is not None:
                return self.move_towards(agent, world, target)

        if "stone" in strategy or "rock" in strategy or "pietr" in strategy:
            target = self.find_nearest(agent, world.stone, "stone", self.vision_radius + 2)
            if target is not None:
                return self.move_towards(agent, world, target)

        if "expand" in strategy or "build" in strategy or "village" in strategy or "house" in strategy:
            if len(getattr(world, "farm_plots", {})) < max(2, len(getattr(world, "villages", [])) * 2):
                farm_target = self.find_farm_target(agent, world, prefer_ripe=False)
                if farm_target is not None:
                    return self.move_towards(agent, world, farm_target)

            if agent.inventory.get("wood", 0) < 8:
                target = self.find_nearest(agent, world.wood, "wood", self.vision_radius + 2)
                if target is not None:
                    return self.move_towards(agent, world, target)

            if agent.inventory.get("stone", 0) < 5:
                target = self.find_nearest(agent, world.stone, "stone", self.vision_radius + 2)
                if target is not None:
                    return self.move_towards(agent, world, target)

            village_home = self._get_known_village_center(agent, world)
            if village_home is not None:
                return self.move_towards(agent, world, village_home)

        if "storage" in strategy:
            village = world.get_village_by_id(getattr(agent, "village_id", None))
            if village:
                storage_pos = village.get("storage_pos")
                if storage_pos:
                    return self.move_towards(agent, world, (storage_pos["x"], storage_pos["y"]))

        if "logistic" in strategy or "road" in strategy:
            village_home = self._get_known_village_center(agent, world)
            if village_home is not None:
                return self.move_towards(agent, world, village_home)

        if "explore" in strategy or "esplora" in strategy:
            if random.random() < 0.75:
                return self.wander(agent, world)

        return None

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
        best_d = 999999

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

    def find_farm_build_target(self, agent, world) -> Optional[Coord]:
        village = world.get_village_by_id(getattr(agent, "village_id", None))
        if village is None:
            return None

        village_id = village["id"]
        storage_pos = village.get("storage_pos")
        storage_coord = None
        if storage_pos:
            sx, sy = storage_pos.get("x"), storage_pos.get("y")
            if (sx, sy) in getattr(world, "storage_buildings", set()):
                storage_coord = (sx, sy)
        storage_bonus_radius = 5
        primary_zone_radius = 6

        farms = [
            p for p, plot in getattr(world, "farm_plots", {}).items()
            if plot.get("village_id") == village_id
        ]

        zone = village.get("farm_zone_center", village.get("center", {"x": agent.x, "y": agent.y}))
        zone_coord = (zone.get("x", agent.x), zone.get("y", agent.y))

        def road_proximity_score(pos: Coord) -> int:
            x, y = pos
            roads = getattr(world, "roads", set())
            score = 0
            if (x, y) in roads:
                score += 2
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (x + dx, y + dy) in roads:
                    score += 1
            return score

        def farm_build_score(pos: Coord) -> float:
            x, y = pos
            d_agent = abs(x - agent.x) + abs(y - agent.y)
            cluster_neighbors = sum(1 for fx, fy in farms if abs(fx - x) <= 1 and abs(fy - y) <= 1)
            road_score = road_proximity_score(pos)

            anchor = storage_coord if storage_coord is not None else zone_coord
            d_anchor = abs(anchor[0] - x) + abs(anchor[1] - y)

            score = d_anchor * 1.6 + d_agent * 0.35
            score -= cluster_neighbors * 2.2
            score -= road_score * 0.6

            # Prefer tight agricultural cluster near storage bonus radius before expanding outwards.
            if storage_coord is not None:
                if d_anchor <= storage_bonus_radius:
                    score -= 8.0
                else:
                    score += (d_anchor - storage_bonus_radius) * 1.7

            return score

        def in_primary_zone(pos: Coord) -> bool:
            cx, cy = (storage_coord if storage_coord is not None else zone_coord)
            return abs(pos[0] - cx) + abs(pos[1] - cy) <= primary_zone_radius

        def valid(pos: Coord, first: bool) -> bool:
            x, y = pos
            if not (0 <= x < world.width and 0 <= y < world.height):
                return False
            if world.tiles[y][x] != "G":
                return False
            if not world.can_build_at(x, y):
                return False
            if pos in world.farms or pos in world.farm_plots:
                return False
            for sx, sy in world.structures:
                if abs(sx - x) <= 1 and abs(sy - y) <= 1:
                    return False
            if first:
                return True
            return any(abs(fx - x) <= 1 and abs(fy - y) <= 1 for fx, fy in farms)

        if farms:
            candidates = []
            for fx, fy in farms:
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        p = (fx + dx, fy + dy)
                        if valid(p, first=False):
                            candidates.append(p)
            if candidates:
                primary_candidates = [p for p in candidates if in_primary_zone(p)]
                if primary_candidates:
                    candidates = primary_candidates
                elif storage_coord is not None:
                    in_bonus = [
                        p for p in candidates
                        if abs(p[0] - storage_coord[0]) + abs(p[1] - storage_coord[1]) <= storage_bonus_radius
                    ]
                    if in_bonus:
                        candidates = in_bonus
                return min(candidates, key=farm_build_score)
            return None

        # First farm: search around farm zone, then around village center as fallback.
        seeds = [
            storage_coord if storage_coord is not None else zone_coord,
            zone_coord,
            (village.get("center", {}).get("x", agent.x), village.get("center", {}).get("y", agent.y)),
        ]
        for sx, sy in seeds:
            for radius in range(0, 9):
                candidates = []
                for dx in range(-radius, radius + 1):
                    for dy in range(-radius, radius + 1):
                        if abs(dx) + abs(dy) > radius:
                            continue
                        p = (sx + dx, sy + dy)
                        if valid(p, first=True):
                            candidates.append(p)
                if candidates:
                    primary_candidates = [p for p in candidates if in_primary_zone(p)]
                    if primary_candidates:
                        candidates = primary_candidates
                    return min(candidates, key=farm_build_score)

        return None

    def find_farm_target(self, agent, world, prefer_ripe: bool = True) -> Optional[Coord]:
        ax = agent.x
        ay = agent.y

        best: Optional[Coord] = None
        best_score = 999999

        known_farms = set(agent.memory.get("farms", set()))
        known_farms.update(getattr(world, "farms", set()))

        for pos in known_farms:
            plot = getattr(world, "farm_plots", {}).get(pos)
            if not plot:
                continue

            # se ha villaggio, preferisci i campi del proprio villaggio
            agent_vid = getattr(agent, "village_id", None)
            plot_vid = plot.get("village_id")
            own_penalty = 0
            if agent_vid is not None and plot_vid is not None and plot_vid != agent_vid:
                own_penalty = 8

            state = plot.get("state", "prepared")
            d = abs(pos[0] - ax) + abs(pos[1] - ay)

            if prefer_ripe:
                if state == "ripe":
                    score = d
                elif state == "prepared":
                    score = d + 4
                elif state == "planted":
                    score = d + 20
                elif state == "growing":
                    score = d + 12
                else:
                    score = d + 50
            else:
                if state == "prepared":
                    score = d
                elif state == "ripe":
                    score = d + 2
                elif state == "growing":
                    score = d + 10
                elif state == "planted":
                    score = d + 14
                else:
                    score = d + 50

            score += own_penalty

            if score < best_score:
                best_score = score
                best = pos

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
            detour = self.local_detour_step(agent, world, target)
            if detour is not None:
                return detour

        return self.greedy_step(agent, world, target)

    def greedy_step(self, agent, world, target: Coord) -> Tuple[str, ...]:
        detour = self.local_detour_step(agent, world, target)
        if detour is not None:
            return detour
        return self.wander(agent, world)

    def local_detour_step(self, agent, world, target: Coord) -> Optional[Tuple[str, ...]]:
        tx, ty = target
        ax, ay = agent.x, agent.y
        current_d = abs(tx - ax) + abs(ty - ay)

        options = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        random.shuffle(options)
        ranked = []

        for dx, dy in options:
            nx, ny = ax + dx, ay + dy
            if not world.is_walkable(nx, ny) or world.is_occupied(nx, ny):
                continue
            nd = abs(tx - nx) + abs(ty - ny)
            ranked.append((nd, dx, dy))

        if not ranked:
            return None

        ranked.sort(key=lambda t: t[0])

        # Prefer strict progress first, then allow side-step to break jams.
        for nd, dx, dy in ranked:
            if nd < current_d:
                return ("move", dx, dy)

        nd, dx, dy = ranked[0]
        if nd <= current_d + 1:
            return ("move", dx, dy)

        return None

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
    def __init__(self, planner: Planner, fallback: FoodBrain, think_every_ticks: int = 240):
        self.planner = planner
        self.fallback = fallback
        self.think_every_ticks = think_every_ticks

    def decide(self, agent, world) -> Tuple[str, ...]:
        if agent.hunger < 60 or agent.inventory.get("food", 0) == 0:
            return self.fallback.decide(agent, world)

        if getattr(agent, "role", "") == "leader":
            return self._decide_leader_governance(agent, world)

        if self._should_think(agent, world):
            self._schedule_llm_request(agent, world)

        # se l'LLM è in pending, fallback immediato: niente freeze percepito
        if agent.llm_pending:
            return self.fallback.decide(agent, world)

        return self._act_from_goal(agent, world)

    def _decide_leader_governance(self, agent, world) -> Tuple[str, ...]:
        village = world.get_village_by_id(getattr(agent, "village_id", None))

        if village is not None:
            needs = village.get("needs", {})
            traits = getattr(agent, "leader_traits", None) or village.get("leader_profile", {})
            if not village.get("priority"):
                p = deterministic_priority_from_needs(needs, traits, village)
                apply_village_priority(village, p, world.tick, "deterministic_boot")

        if self._should_think(agent, world):
            self._schedule_llm_request(agent, world)

        # Leader stays mostly near village center; workers execute operations.
        if village is not None:
            c = village.get("center")
            if c and random.random() < 0.65:
                return self.fallback.move_towards(agent, world, (c["x"], c["y"]))

        return ("wait",)

    def _should_think(self, agent, world) -> bool:
        if not getattr(world, "llm_enabled", True):
            return False

        if agent.llm_pending:
            return False

        think_interval = self.think_every_ticks
        if getattr(agent, "role", "") == "leader":
            think_interval = min(self.think_every_ticks, 120)

        if world.tick - agent.last_llm_tick < think_interval:
            return False

        # rate limit per tick
        if getattr(world, "llm_calls_this_tick", 0) >= getattr(world, "max_llm_calls_per_tick", 1):
            return False

        return True

    def _schedule_llm_request(self, agent, world) -> None:
        if not getattr(world, "llm_enabled", True):
            logger.warning("LLM disabled: using deterministic fallback for agent_id=%s", getattr(agent, "agent_id", "unknown"))
            return

        agent.llm_pending = True
        agent.last_llm_tick = world.tick

        prompt = self._make_prompt(agent, world)
        logger.info("LLM request scheduled role=%s agent_id=%s", getattr(agent, "role", "npc"), getattr(agent, "agent_id", "unknown"))

        if hasattr(world, "record_llm_interaction"):
            world.record_llm_interaction()

        if hasattr(world, "llm_calls_this_tick"):
            world.llm_calls_this_tick += 1

        try:
            loop = asyncio.get_running_loop()
            if getattr(agent, "role", "") == "leader":
                loop.create_task(self._request_leader_priority(agent, world, prompt))
            else:
                loop.create_task(self._request_goal(agent, world, prompt))
        except RuntimeError:
            agent.llm_pending = False
            if getattr(agent, "role", "") == "leader":
                village = world.get_village_by_id(getattr(agent, "village_id", None))
                if village is not None:
                    traits = getattr(agent, "leader_traits", None) or village.get("leader_profile", {})
                    p = deterministic_priority_from_needs(village.get("needs", {}), traits, village)
                    apply_village_priority(village, p, world.tick, "deterministic_no_loop")
            logger.warning("LLM scheduling failed: no running event loop; deterministic fallback remains active")

    async def _request_leader_priority(self, agent, world, prompt: str) -> None:
        village = world.get_village_by_id(getattr(agent, "village_id", None))
        traits = getattr(agent, "leader_traits", None) or (village.get("leader_profile", {}) if village else {})
        timeout_s = float(getattr(world, "llm_timeout_seconds", 3.0))
        try:
            raw = await asyncio.wait_for(
                self.planner.propose_goal_async(prompt),
                timeout=timeout_s,
            )
            priority = self._extract_priority_from_llm(raw)

            if priority is None:
                needs = village.get("needs", {}) if village else {}
                priority = deterministic_priority_from_needs(needs, traits, village)

            if village is not None:
                apply_village_priority(village, priority, world.tick, "llm")
        except Exception:
            logger.warning(
                "LLM leader request failed or timed out; fallback priority applied agent_id=%s timeout_s=%.2f",
                getattr(agent, "agent_id", "unknown"),
                timeout_s,
            )
            needs = village.get("needs", {}) if village else {}
            priority = deterministic_priority_from_needs(needs, traits, village)
            if village is not None:
                apply_village_priority(village, priority, world.tick, "deterministic_fallback")
        finally:
            agent.llm_pending = False

    def _extract_priority_from_llm(self, raw: str) -> Optional[str]:
        txt = (raw or "").strip()
        if not txt:
            return None
        cleaned = txt
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").replace("json", "", 1).strip()
        try:
            import json

            obj = json.loads(cleaned)
            if isinstance(obj, dict):
                p = obj.get("priority")
                if isinstance(p, str):
                    return normalize_priority(p)
        except Exception:
            pass
        line = txt.splitlines()[0][:120]
        return normalize_priority(line)

    async def _request_goal(self, agent, world, prompt: str) -> None:
        timeout_s = float(getattr(world, "llm_timeout_seconds", 3.0))
        try:
            raw_goal = await asyncio.wait_for(
                self.planner.propose_goal_async(prompt),
                timeout=timeout_s,
            )
            normalized = normalize_goal(raw_goal)

            if normalized is None:
                logger.warning("LLM returned invalid goal; fallback used agent_id=%s raw=%r", getattr(agent, "agent_id", "unknown"), raw_goal)
                agent.goal = "survive"
                return

            agent.goal = normalized
            logger.info("LLM goal accepted role=%s agent_id=%s goal=%s", getattr(agent, "role", "npc"), getattr(agent, "agent_id", "unknown"), agent.goal)

            if getattr(agent, "role", "") == "leader" and getattr(agent, "village_id", None) is not None:
                village = world.get_village_by_id(agent.village_id)
                if village is not None:
                    village["strategy"] = normalized

        except Exception as e:
            agent.goal = "survive"
            logger.warning(
                "LLM request failed or timed out; fallback goal applied agent_id=%s timeout_s=%.2f error=%s",
                getattr(agent, "agent_id", "unknown"),
                timeout_s,
                e,
            )
        finally:
            agent.llm_pending = False

    def _act_from_goal(self, agent, world) -> Tuple[str, ...]:
        g = (agent.goal or "").lower()

        if "food" in g or "cibo" in g or "eat" in g or "hunt" in g or "farm" in g:
            farm_target = self.fallback.find_farm_target(agent, world, prefer_ripe=True)
            if farm_target is not None:
                return self.fallback.move_towards(agent, world, farm_target)

            target = self.fallback.find_nearest(
                agent, world.food, "food", self.fallback.vision_radius + 2
            )
            if target is not None:
                return self.fallback.move_towards(agent, world, target)

        if "wood" in g or "legn" in g or "tree" in g:
            target = self.fallback.find_nearest(
                agent, world.wood, "wood", self.fallback.vision_radius + 2
            )
            if target is not None:
                return self.fallback.move_towards(agent, world, target)

        if "stone" in g or "pietr" in g or "rock" in g:
            target = self.fallback.find_nearest(
                agent, world.stone, "stone", self.fallback.vision_radius + 2
            )
            if target is not None:
                return self.fallback.move_towards(agent, world, target)

        if "storage" in g:
            village = world.get_village_by_id(getattr(agent, "village_id", None))
            if village:
                storage_pos = village.get("storage_pos")
                if storage_pos:
                    return self.fallback.move_towards(agent, world, (storage_pos["x"], storage_pos["y"]))

        if "house" in g or "expand" in g or "build" in g or "village" in g:
            if agent.inventory.get("wood", 0) < 8:
                target = self.fallback.find_nearest(
                    agent, world.wood, "wood", self.fallback.vision_radius + 2
                )
                if target is not None:
                    return self.fallback.move_towards(agent, world, target)

            if agent.inventory.get("stone", 0) < 5:
                target = self.fallback.find_nearest(
                    agent, world.stone, "stone", self.fallback.vision_radius + 2
                )
                if target is not None:
                    return self.fallback.move_towards(agent, world, target)

            village_home = self.fallback._get_known_village_center(agent, world)
            if village_home is not None:
                return self.fallback.move_towards(agent, world, village_home)

        if "logistic" in g or "road" in g:
            village_home = self.fallback._get_known_village_center(agent, world)
            if village_home is not None:
                return self.fallback.move_towards(agent, world, village_home)

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
                    f"village_houses={village.get('houses', 0)}\n"
                    f"village_population={village.get('population', 0)}\n"
                    f"current_strategy={village.get('strategy', 'none')}\n"
                    f"relation={village.get('relation', 'peace')}\n"
                    f"target_village_id={village.get('target_village_id')}\n"
                    f"migration_target_id={village.get('migration_target_id')}\n"
                    f"power={village.get('power', 0)}\n"
                    f"priority={village.get('priority', 'stabilize')}\n"
                    f"needs={village.get('needs', {})}\n"
                    f"metrics={village.get('metrics', {})}\n"
                    f"farms={len(getattr(world, 'farm_plots', {}))}\n"
                )

        if role == "leader":
            village = world.get_village_by_id(getattr(agent, "village_id", None))
            storage_buildings = 0
            traits = getattr(agent, "leader_traits", None) or (village.get("leader_profile", {}) if village else {})
            priority_history = village.get("priority_history", [])[-4:] if village else []
            active_farms = 0
            phase_hint = "bootstrap"
            village_phase = (village.get("phase") if village else None) or "survival"
            phase_allowed = sorted(phase_allowed_priorities(village))
            if village is not None:
                vcenter = village.get("center", {})
                cx = vcenter.get("x", agent.x)
                cy = vcenter.get("y", agent.y)
                storage_buildings = sum(
                    1
                    for sx, sy in getattr(world, "storage_buildings", set())
                    if abs(sx - cx) <= 8 and abs(sy - cy) <= 8
                )
                active_farms = village.get("metrics", {}).get("active_farms", 0)
                if active_farms <= 0:
                    phase_hint = "found_farms"
                elif active_farms >= 2 and storage_buildings == 0:
                    phase_hint = "build_first_storage"
                else:
                    phase_hint = "stabilize_and_expand"
            return (
                "You are the governor consciousness of a village leader character.\n"
                "Use leader_traits consistently over time.\n"
                "Choose only one strategic priority for village development phase.\n"
                "Return strict JSON only: {\"priority\":\"...\"}\n"
                "Allowed priorities: secure_food, build_storage, build_housing, expand_farms, improve_logistics, stabilize.\n"
                "You must choose a priority coherent with the current village_phase.\n"
                "Hard guidance:\n"
                "- if phase_hint is found_farms, prioritize expand_farms.\n"
                "- if phase_hint is build_first_storage, prioritize build_storage.\n"
                f"tick={world.tick}\n"
                f"population={village.get('population', 0) if village else 0}\n"
                f"houses={village.get('houses', 0) if village else 0}\n"
                f"farms={active_farms}\n"
                f"storage_buildings={storage_buildings}\n"
                f"phase_hint={phase_hint}\n"
                f"village_phase={village_phase}\n"
                f"phase_allowed_priorities={phase_allowed}\n"
                f"food_stock={village.get('storage', {}).get('food', 0) if village else 0}\n"
                f"wood_stock={village.get('storage', {}).get('wood', 0) if village else 0}\n"
                f"stone_stock={village.get('storage', {}).get('stone', 0) if village else 0}\n"
                f"needs={village.get('needs', {}) if village else {}}\n"
                f"metrics={village.get('metrics', {}) if village else {}}\n"
                f"current_priority={village.get('priority', 'stabilize') if village else 'stabilize'}\n"
                f"current_strategy={village.get('strategy', 'stabilize') if village else 'stabilize'}\n"
                f"leader_traits={traits}\n"
                f"recent_priority_history={priority_history}\n"
                f"{village_summary}"
            )

        return (
            "You are the high-level brain of a player character in a tile world.\n"
            "Return only one short goal.\n"
            "Allowed goals: gather food, gather wood, gather stone, explore.\n"
            f"tick={world.tick}\n"
            f"position=({agent.x},{agent.y})\n"
            f"hunger={agent.hunger}\n"
            f"inventory={agent.inventory}\n"
        )
