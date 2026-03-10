from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, Set
import random
import asyncio
import logging
import json
import re
from agent import (
    build_agent_cognitive_context,
    detect_agent_innovation_opportunity,
    detect_agent_reflection_reason,
    evaluate_local_survival_pressure,
    ensure_agent_cognitive_profile,
    ensure_agent_proto_traits,
    find_recent_resource_memory,
    maybe_generate_innovation_proposal,
    get_known_camp_spot,
    get_known_resource_spot,
    get_known_useful_building_target,
    get_recent_memory_events,
    should_agent_reflect,
    update_agent_cognitive_profile,
    validate_proto_asset_proposal,
    write_episodic_memory_event,
)
from agent import interpret_local_signals_with_self_model

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


def _manhattan(a: Coord, b: Coord) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


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
        self.target_stickiness_ticks = 4
        self.target_switch_improvement_margin = 2

    def _gap_role_for_task(self, agent) -> Optional[str]:
        role = str(getattr(agent, "role", "npc")).lower()
        task = str(getattr(agent, "task", "idle")).lower()
        if role in {"farmer", "forager", "hauler", "builder", "miner", "woodcutter"}:
            return role
        task_map = {
            "farm_cycle": "farmer",
            "gather_food_wild": "forager",
            "food_logistics": "hauler",
            "village_logistics": "hauler",
            "build_storage": "builder",
            "build_house": "builder",
            "gather_materials": "builder",
            "mine_cycle": "miner",
            "lumber_cycle": "woodcutter",
        }
        return task_map.get(task)

    def _record_gap_stage(self, world, agent, stage: str) -> None:
        role = self._gap_role_for_task(agent)
        if role and hasattr(world, "record_assignment_pipeline_stage"):
            world.record_assignment_pipeline_stage(agent, role, stage)

    def _record_gap_block(self, world, agent, reason: str) -> None:
        role = self._gap_role_for_task(agent)
        if role and hasattr(world, "record_assignment_pipeline_block_reason"):
            world.record_assignment_pipeline_block_reason(agent, role, reason)

    def _new_intention(
        self,
        world,
        intention_type: str,
        *,
        target: Optional[Coord] = None,
        target_id: Optional[str] = None,
        resource_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "type": str(intention_type),
            "target_id": str(target_id) if target_id is not None else None,
            "resource_type": str(resource_type) if resource_type is not None else None,
            "started_tick": int(getattr(world, "tick", 0)),
            "status": "active",
            "failed_ticks": 0,
        }
        if target is not None:
            payload["target"] = {"x": int(target[0]), "y": int(target[1])}
        else:
            payload["target"] = None
        return payload

    def _attention_resource_target(self, agent, resource_type: str) -> Optional[Coord]:
        subjective = getattr(agent, "subjective_state", {})
        if not isinstance(subjective, dict):
            return None
        attention = subjective.get("attention", {})
        if not isinstance(attention, dict):
            return None
        targets = attention.get("top_resource_targets", [])
        if not isinstance(targets, list):
            return None
        for entry in targets:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("resource", "")) != str(resource_type):
                continue
            return (int(entry.get("x", 0)), int(entry.get("y", 0)))
        return None

    def _increment_intention_fail(self, agent) -> None:
        intention = getattr(agent, "current_intention", None)
        if not isinstance(intention, dict):
            return
        intention["failed_ticks"] = int(intention.get("failed_ticks", 0)) + 1

    def _clear_intention(self, agent) -> None:
        setattr(agent, "current_intention", None)

    def select_agent_intention(self, world, agent) -> Optional[Dict[str, Any]]:
        task = str(getattr(agent, "task", "idle")).lower()
        role = str(getattr(agent, "role", "npc")).lower()
        hunger = float(getattr(agent, "hunger", 100.0))
        self_model = getattr(agent, "self_model", {}) if isinstance(getattr(agent, "self_model", {}), dict) else {}
        proto_traits = ensure_agent_proto_traits(agent)
        survival_w = float(self_model.get("survival_weight", 0.6))
        work_w = float(self_model.get("work_weight", 0.5))
        explore_w = float(self_model.get("exploration_weight", 0.3))
        stress = float(self_model.get("stress_level", 0.2))
        caution = float(proto_traits.get("caution", 0.5))
        curiosity = float(proto_traits.get("curiosity", 0.5))
        local_culture = (
            getattr(agent, "subjective_state", {}).get("local_culture", {})
            if isinstance(getattr(agent, "subjective_state", {}), dict)
            else {}
        )
        culture_coop = float(local_culture.get("cooperation_norm", 0.5)) if isinstance(local_culture, dict) else 0.5
        culture_work = float(local_culture.get("work_norm", 0.5)) if isinstance(local_culture, dict) else 0.5
        culture_explore = float(local_culture.get("exploration_norm", 0.5)) if isinstance(local_culture, dict) else 0.5
        dominant_focus = str(local_culture.get("dominant_resource_focus", "")) if isinstance(local_culture, dict) else ""
        leader_nearby = self._salient_local_leader(agent) is not None
        interpreted = interpret_local_signals_with_self_model(world, agent)
        survival = evaluate_local_survival_pressure(world, agent)
        survival_pressure = float(survival.get("survival_pressure", 0.0))
        food_crisis = bool(survival.get("food_crisis", False))
        preferred_resource = str(interpreted.get("preferred_resource", "food"))
        if dominant_focus in {"food", "wood", "stone"} and preferred_resource != dominant_focus:
            # Culture focus is a weak village-level deterministic bias, not an override.
            if max(culture_work, culture_coop, culture_explore) >= 0.55:
                preferred_resource = dominant_focus

        if food_crisis or hunger < 35 or (survival_w + caution * 0.08 + survival_pressure * 0.25 > 0.72 and hunger < 55):
            target = self._attention_resource_target(agent, "food")
            return self._new_intention(world, "gather_food", target=target, resource_type="food")

        if role == "miner" or task == "mine_cycle":
            assigned_id = getattr(agent, "assigned_building_id", None)
            building = getattr(world, "buildings", {}).get(str(assigned_id)) if assigned_id is not None else None
            target = None
            if isinstance(building, dict):
                target = (int(building.get("x", 0)), int(building.get("y", 0)))
            return self._new_intention(
                world,
                "work_mine",
                target=target,
                target_id=(str(assigned_id) if assigned_id is not None else None),
                resource_type="stone",
            )

        if role == "woodcutter" or task == "lumber_cycle":
            assigned_id = getattr(agent, "assigned_building_id", None)
            building = getattr(world, "buildings", {}).get(str(assigned_id)) if assigned_id is not None else None
            target = None
            if isinstance(building, dict):
                target = (int(building.get("x", 0)), int(building.get("y", 0)))
            return self._new_intention(
                world,
                "work_lumberyard",
                target=target,
                target_id=(str(assigned_id) if assigned_id is not None else None),
                resource_type="wood",
            )

        if role == "hauler" or task in {"village_logistics", "food_logistics"}:
            village = world.get_village_by_id(getattr(agent, "village_id", None))
            storage_pos = village.get("storage_pos") if isinstance(village, dict) else None
            target = None
            if isinstance(storage_pos, dict):
                target = (int(storage_pos.get("x", 0)), int(storage_pos.get("y", 0)))
            if food_crisis:
                return self._new_intention(world, "deliver_resource", target=target, resource_type="food")
            return self._new_intention(world, "deliver_resource", target=target)

        if role == "builder" or task in {"build_storage", "build_house", "gather_materials"}:
            if food_crisis:
                target = self._attention_resource_target(agent, "food")
                return self._new_intention(world, "gather_food", target=target, resource_type="food")
            village = world.get_village_by_id(getattr(agent, "village_id", None))
            center = village.get("center") if isinstance(village, dict) else None
            target = None
            if isinstance(center, dict):
                target = (int(center.get("x", 0)), int(center.get("y", 0)))
            return self._new_intention(world, "build_structure", target=target)

        if leader_nearby and role in {"builder", "hauler"} and culture_coop >= 0.45:
            village = world.get_village_by_id(getattr(agent, "village_id", None))
            storage_pos = village.get("storage_pos") if isinstance(village, dict) else None
            if isinstance(storage_pos, dict):
                return self._new_intention(
                    world,
                    "deliver_resource",
                    target=(int(storage_pos.get("x", 0)), int(storage_pos.get("y", 0))),
                )
            if isinstance(village, dict) and isinstance(village.get("center"), dict):
                center = village["center"]
                return self._new_intention(
                    world,
                    "build_structure",
                    target=(int(center.get("x", 0)), int(center.get("y", 0))),
                )

        if task == "gather_food_wild":
            target = self._attention_resource_target(agent, "food")
            return self._new_intention(world, "gather_food", target=target, resource_type="food")

        if role == "farmer" or task == "farm_cycle":
            farm_target = self.find_farm_target(agent, world, prefer_ripe=True)
            if farm_target is not None:
                return self._new_intention(world, "gather_food", target=farm_target, resource_type="food")
            farm_build = self.find_farm_build_target(agent, world)
            if farm_build is not None:
                return self._new_intention(world, "build_structure", target=farm_build)

        resources = ("food", "wood", "stone")
        if preferred_resource in {"food", "wood", "stone"}:
            resources = (preferred_resource,) + tuple(r for r in resources if r != preferred_resource)
        for resource in resources:
            target = self._attention_resource_target(agent, resource)
            if target is not None:
                itype = "gather_food" if resource == "food" else "gather_resource"
                return self._new_intention(world, itype, target=target, resource_type=resource)

        if (
            explore_w + curiosity * 0.10 + culture_explore * 0.08 > 0.55
            and stress - float(proto_traits.get("resilience", 0.5)) * 0.08 < 0.5
            and work_w + culture_work * 0.08 < 0.72
            and not leader_nearby
            and survival_pressure < 0.45
        ):
            return self._new_intention(world, "explore")

        if leader_nearby and role in {"builder", "hauler"}:
            return self._new_intention(world, "deliver_resource")
        return self._new_intention(world, "explore")

    def progress_agent_intention(self, world, agent, intention: Dict[str, Any]) -> Optional[Tuple[str, ...]]:
        itype = str(intention.get("type", ""))
        resource_type = str(intention.get("resource_type", ""))
        max_failed_ticks = max(1, int(intention.get("max_failed_ticks", 2)))
        target_data = intention.get("target")
        target: Optional[Coord] = None
        if isinstance(target_data, dict):
            target = (int(target_data.get("x", 0)), int(target_data.get("y", 0)))

        if itype == "gather_food":
            if int(getattr(agent, "inventory", {}).get("food", 0)) > 0:
                write_episodic_memory_event(
                    agent,
                    tick=int(getattr(world, "tick", 0)),
                    event_type="hunger_relief",
                    outcome="success",
                    location=(int(agent.x), int(agent.y)),
                    resource_type="food",
                    salience=2.5,
                )
                self._clear_intention(agent)
                return None
            target = target or self._attention_resource_target(agent, "food") or self.find_nearest(
                agent, getattr(world, "food", set()), "food", self.vision_radius + 4
            )
            if target is None:
                write_episodic_memory_event(
                    agent,
                    tick=int(getattr(world, "tick", 0)),
                    event_type="failed_resource_search",
                    outcome="failure",
                    location=(int(agent.x), int(agent.y)),
                    resource_type="food",
                    salience=1.6,
                )
                self._increment_intention_fail(agent)
                if int(intention.get("failed_ticks", 0)) >= max_failed_ticks:
                    self._clear_intention(agent)
                return None
            write_episodic_memory_event(
                agent,
                tick=int(getattr(world, "tick", 0)),
                event_type="found_resource",
                outcome="success",
                location=target,
                resource_type="food",
                salience=1.4,
            )
            intention["target"] = {"x": int(target[0]), "y": int(target[1])}
            if target not in getattr(world, "food", set()) and _manhattan((agent.x, agent.y), target) > 1:
                self._increment_intention_fail(agent)
                if int(intention.get("failed_ticks", 0)) >= max_failed_ticks:
                    self._clear_intention(agent)
                    return None
            return self.move_towards(agent, world, target)

        if itype == "gather_resource":
            if resource_type not in {"wood", "stone"}:
                self._clear_intention(agent)
                return None
            if int(getattr(agent, "inventory", {}).get(resource_type, 0)) > 0:
                self._clear_intention(agent)
                return None
            source = getattr(world, resource_type, set())
            target = target or self._attention_resource_target(agent, resource_type) or self.find_nearest(
                agent, source, resource_type, self.vision_radius + 5
            )
            if target is None:
                write_episodic_memory_event(
                    agent,
                    tick=int(getattr(world, "tick", 0)),
                    event_type="failed_resource_search",
                    outcome="failure",
                    location=(int(agent.x), int(agent.y)),
                    resource_type=resource_type,
                    salience=1.4,
                )
                self._increment_intention_fail(agent)
                if int(intention.get("failed_ticks", 0)) >= max_failed_ticks:
                    self._clear_intention(agent)
                return None
            write_episodic_memory_event(
                agent,
                tick=int(getattr(world, "tick", 0)),
                event_type="found_resource",
                outcome="success",
                location=target,
                resource_type=resource_type,
                salience=1.2,
            )
            intention["target"] = {"x": int(target[0]), "y": int(target[1])}
            if target not in source and _manhattan((agent.x, agent.y), target) > 1:
                self._increment_intention_fail(agent)
                if int(intention.get("failed_ticks", 0)) >= max_failed_ticks:
                    self._clear_intention(agent)
                    return None
            return self.move_towards(agent, world, target)

        if itype == "deliver_resource":
            inv = getattr(agent, "inventory", {})
            if int(inv.get("food", 0)) + int(inv.get("wood", 0)) + int(inv.get("stone", 0)) <= 0:
                write_episodic_memory_event(
                    agent,
                    tick=int(getattr(world, "tick", 0)),
                    event_type="delivered_material",
                    outcome="success",
                    location=(int(agent.x), int(agent.y)),
                    salience=1.5,
                )
                self._clear_intention(agent)
                return None
            village = world.get_village_by_id(getattr(agent, "village_id", None))
            storage_pos = village.get("storage_pos") if isinstance(village, dict) else None
            if isinstance(storage_pos, dict):
                target = (int(storage_pos.get("x", 0)), int(storage_pos.get("y", 0)))
                intention["target"] = {"x": int(target[0]), "y": int(target[1])}
                write_episodic_memory_event(
                    agent,
                    tick=int(getattr(world, "tick", 0)),
                    event_type="useful_building",
                    outcome="success",
                    location=target,
                    building_type="storage",
                    salience=1.1,
                )
                return self.move_towards(agent, world, target)
            self._clear_intention(agent)
            return None

        if itype in {"work_mine", "work_lumberyard"}:
            target_resource = "stone" if itype == "work_mine" else "wood"
            if int(getattr(agent, "inventory", {}).get(target_resource, 0)) > 0:
                write_episodic_memory_event(
                    agent,
                    tick=int(getattr(world, "tick", 0)),
                    event_type="construction_progress",
                    outcome="success",
                    location=(int(agent.x), int(agent.y)),
                    resource_type=target_resource,
                    salience=1.3,
                )
                self._clear_intention(agent)
                return None
            target_id = intention.get("target_id")
            if target_id is not None:
                building = getattr(world, "buildings", {}).get(str(target_id))
                if not isinstance(building, dict):
                    write_episodic_memory_event(
                        agent,
                        tick=int(getattr(world, "tick", 0)),
                        event_type="unreachable_target",
                        outcome="failure",
                        location=(int(agent.x), int(agent.y)),
                        target_id=str(target_id),
                        salience=1.8,
                    )
                    self._clear_intention(agent)
                    return None
                linked_anchor = building.get("linked_resource_anchor")
                if isinstance(linked_anchor, dict):
                    target = (int(linked_anchor.get("x", 0)), int(linked_anchor.get("y", 0)))
                    intention["target"] = {"x": int(target[0]), "y": int(target[1])}
                    return self.move_towards(agent, world, target)
                target = (int(building.get("x", 0)), int(building.get("y", 0)))
                intention["target"] = {"x": int(target[0]), "y": int(target[1])}
                return self.move_towards(agent, world, target)
            source = getattr(world, target_resource, set())
            target = self.find_nearest(agent, source, target_resource, self.vision_radius + 6)
            if target is None:
                write_episodic_memory_event(
                    agent,
                    tick=int(getattr(world, "tick", 0)),
                    event_type="failed_resource_search",
                    outcome="failure",
                    location=(int(agent.x), int(agent.y)),
                    resource_type=target_resource,
                    salience=1.2,
                )
                self._increment_intention_fail(agent)
                if int(intention.get("failed_ticks", 0)) >= max_failed_ticks:
                    self._clear_intention(agent)
                return None
            intention["target"] = {"x": int(target[0]), "y": int(target[1])}
            return self.move_towards(agent, world, target)

        if itype == "build_structure":
            task = str(getattr(agent, "task", "idle")).lower()
            if task not in {"build_storage", "build_house", "gather_materials"}:
                self._clear_intention(agent)
                return None
            salient = self._attention_building_target(agent, world, {"storage", "house"})
            if salient is not None:
                intention["target"] = {"x": int(salient[0]), "y": int(salient[1])}
                write_episodic_memory_event(
                    agent,
                    tick=int(getattr(world, "tick", 0)),
                    event_type="useful_building",
                    outcome="success",
                    location=salient,
                    salience=1.0,
                )
                return self.move_towards(agent, world, salient)
            village = world.get_village_by_id(getattr(agent, "village_id", None))
            if isinstance(village, dict) and isinstance(village.get("center"), dict):
                center = village["center"]
                target = (int(center.get("x", agent.x)), int(center.get("y", agent.y)))
                intention["target"] = {"x": int(target[0]), "y": int(target[1])}
                return self.move_towards(agent, world, target)
            write_episodic_memory_event(
                agent,
                tick=int(getattr(world, "tick", 0)),
                event_type="construction_blocked",
                outcome="failure",
                location=(int(agent.x), int(agent.y)),
                salience=1.4,
            )
            self._clear_intention(agent)
            return None

        if itype == "explore":
            started_tick = int(intention.get("started_tick", int(getattr(world, "tick", 0))))
            if int(getattr(world, "tick", 0)) - started_tick >= 8:
                self._clear_intention(agent)
                return None
            return self.wander(agent, world)

        self._clear_intention(agent)
        return None

    def _evaluate_intention(self, world, agent) -> Optional[Tuple[str, ...]]:
        task = str(getattr(agent, "task", "idle")).lower()
        if task in {"bootstrap_gather", "bootstrap_build_house", "camp_supply_food", "manage_village", "player_controlled", "rest"}:
            return None

        hunger = float(getattr(agent, "hunger", 100.0))
        proto_traits = ensure_agent_proto_traits(agent)
        diligence = float(proto_traits.get("diligence", 0.5))
        current = getattr(agent, "current_intention", None)
        if hunger < 35 and (not isinstance(current, dict) or str(current.get("type", "")) != "gather_food"):
            target = self._attention_resource_target(agent, "food")
            current = self._new_intention(world, "gather_food", target=target, resource_type="food")
            setattr(agent, "current_intention", current)

        if not isinstance(current, dict):
            selected = self.select_agent_intention(world, agent)
            setattr(agent, "current_intention", selected)
            current = selected

        if not isinstance(current, dict):
            return None

        # High diligence slightly increases persistence before intention churn.
        if isinstance(current, dict) and diligence > 0.65:
            current["max_failed_ticks"] = 3
        action = self.progress_agent_intention(world, agent, current)
        return action

    def decide(self, agent, world) -> Tuple[str, ...]:
        task = str(getattr(agent, "task", "idle")).lower()

        intention_action = self._evaluate_intention(world, agent)
        if intention_action is not None:
            return intention_action

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

        if task == "camp_supply_food":
            anchor = getattr(agent, "proto_task_anchor", {})
            source_pos = tuple(anchor.get("source_pos", ())) if isinstance(anchor, dict) else ()
            drop_pos = tuple(anchor.get("drop_pos", ())) if isinstance(anchor, dict) else ()
            if int(agent.inventory.get("food", 0)) > 0 and hasattr(world, "nearest_active_camp_for_agent"):
                if len(drop_pos) == 2:
                    target = (int(drop_pos[0]), int(drop_pos[1]))
                else:
                    camp = world.nearest_active_camp_for_agent(agent, max_distance=18)
                    if isinstance(camp, dict):
                        target = (int(camp.get("x", agent.x)), int(camp.get("y", agent.y)))
                    else:
                        target = None
                if target is not None:
                    if abs(int(agent.x) - target[0]) + abs(int(agent.y) - target[1]) > 1:
                        return self.move_towards(agent, world, target)
                    return ("wait",)
            if len(source_pos) == 2:
                target = (int(source_pos[0]), int(source_pos[1]))
                return self.move_towards(agent, world, target)
            target = self.find_nearest(agent, world.food, "food", self.vision_radius + 6)
            if target is not None:
                return self.move_towards(agent, world, target)
            return self.wander(agent, world)

        # -----------------------------
        # 2) task-guided logic
        # -----------------------------
        def _nearest_construction_site_target(building_type: str) -> Optional[Tuple[int, int]]:
            village_id = getattr(agent, "village_id", None)
            candidates = []
            for building in getattr(world, "buildings", {}).values():
                if not isinstance(building, dict):
                    continue
                if str(building.get("type", "")) != str(building_type):
                    continue
                if str(building.get("operational_state", "")) != "under_construction":
                    continue
                if village_id is not None and building.get("village_id") != village_id:
                    continue
                bx = int(building.get("x", 0))
                by = int(building.get("y", 0))
                dist = abs(agent.x - bx) + abs(agent.y - by)
                candidates.append((dist, str(building.get("building_id", "")), bx, by))
            if not candidates:
                return None
            candidates.sort(key=lambda item: (item[0], item[1]))
            _, _, tx, ty = candidates[0]
            return (tx, ty)

        def _nearest_under_construction_site_with_needs() -> Optional[Tuple[int, int]]:
            village_id = getattr(agent, "village_id", None)
            candidates = []
            for building in getattr(world, "buildings", {}).values():
                if not isinstance(building, dict):
                    continue
                if str(building.get("operational_state", "")) != "under_construction":
                    continue
                if village_id is not None and building.get("village_id") != village_id:
                    continue
                req = building.get("construction_request", {})
                if not isinstance(req, dict):
                    continue
                outstanding = 0
                for resource in ("wood", "stone", "food"):
                    needed = max(0, int(req.get(f"{resource}_needed", 0)))
                    reserved = max(0, int(req.get(f"{resource}_reserved", 0)))
                    buf = max(0, int((building.get("construction_buffer", {}) or {}).get(resource, 0)))
                    outstanding += max(0, needed - reserved - buf)
                if outstanding <= 0:
                    continue
                bx = int(building.get("x", 0))
                by = int(building.get("y", 0))
                dist = abs(agent.x - bx) + abs(agent.y - by)
                waiting_tick = int(building.get("builder_waiting_tick", -10_000))
                recent_wait = 0 if int(getattr(world, "tick", 0)) - waiting_tick <= 24 else 1
                candidates.append((recent_wait, dist, str(building.get("building_id", "")), bx, by))
            if not candidates:
                return None
            candidates.sort(key=lambda item: (item[0], item[1], item[2]))
            _, _, _, tx, ty = candidates[0]
            return (tx, ty)

        def _village_by_uid(vuid: str) -> Optional[Dict[str, Any]]:
            uid = str(vuid or "")
            if not uid:
                return None
            for village in getattr(world, "villages", []):
                if not isinstance(village, dict):
                    continue
                if str(village.get("village_uid", "")) == uid:
                    return village
            return None

        def _social_gravity_return_target() -> Optional[Tuple[Coord, str, str]]:
            if int(getattr(agent, "hunger", 100)) < 22:
                return None
            happiness = max(0.0, min(100.0, float(getattr(agent, "happiness", 50.0))))
            status = str(getattr(agent, "village_affiliation_status", "unaffiliated"))
            if status not in {"resident", "attached", "transient"}:
                return None
            target_village = None
            home_uid = str(getattr(agent, "home_village_uid", "") or "")
            primary_uid = str(getattr(agent, "primary_village_uid", "") or "")
            home_target: Optional[Coord] = None
            home_building_id = getattr(agent, "home_building_id", None)
            if status == "resident" and home_building_id is not None:
                home = getattr(world, "buildings", {}).get(str(home_building_id))
                if isinstance(home, dict) and str(home.get("type", "")) == "house":
                    home_target = (int(home.get("x", agent.x)), int(home.get("y", agent.y)))
            if status == "resident" and home_uid:
                target_village = _village_by_uid(home_uid)
            if target_village is None and primary_uid:
                target_village = _village_by_uid(primary_uid)
            if target_village is None:
                target_village = world.get_village_by_id(getattr(agent, "village_id", None))
            if not isinstance(target_village, dict):
                return None
            center = target_village.get("center", {})
            if not isinstance(center, dict):
                return None
            target = home_target or (int(center.get("x", agent.x)), int(center.get("y", agent.y)))
            dist = abs(int(agent.x) - target[0]) + abs(int(agent.y) - target[1])
            keep_radius = 12
            if status == "resident":
                keep_radius = 6 if home_target is not None else 7
            elif status == "attached":
                keep_radius = 9
            elif status == "transient":
                keep_radius = 12
            uid = str(target_village.get("village_uid", "") or "")
            if dist > keep_radius:
                event_key = "home_return_events" if status == "resident" and home_target is not None else "return_to_village_events"
                return (target, event_key, uid)
            linger_bias = 0.2 + ((happiness - 50.0) / 250.0)
            if status in {"resident", "attached"} and dist > 3 and random.random() < max(0.1, min(0.45, linger_bias)):
                event_key = "home_return_events" if status == "resident" and home_target is not None else "stay_near_village_bias_events"
                return (target, event_key, uid)
            return None

        def _camp_return_target(*, for_rest: bool = False) -> Optional[Tuple[Coord, str, str]]:
            if int(getattr(agent, "hunger", 100)) < (20 if for_rest else 22):
                return None
            happiness = max(0.0, min(100.0, float(getattr(agent, "happiness", 50.0))))
            camp: Optional[Dict[str, Any]] = None
            target: Optional[Coord] = None
            camp_id = ""
            camp_uid = ""
            if hasattr(world, "nearest_active_camp_for_agent"):
                local_camp = world.nearest_active_camp_for_agent(agent, max_distance=18 if for_rest else 16)
                if isinstance(local_camp, dict):
                    camp = local_camp
                    target = (int(camp.get("x", agent.x)), int(camp.get("y", agent.y)))
                    camp_id = str(camp.get("camp_id", ""))
                    camp_uid = str(camp.get("village_uid", "") or "")
            if target is None:
                known = get_known_camp_spot(agent, min_confidence=0.4, max_age_ticks=220, world=world)
                if known is None:
                    return None
                target = (int(known[0]), int(known[1]))
            dist = abs(int(agent.x) - target[0]) + abs(int(agent.y) - target[1])
            if dist <= (1 if for_rest else 3):
                return None
            food_bias = 0.0
            if hasattr(world, "camp_has_food_for_agent") and bool(world.camp_has_food_for_agent(agent, max_distance=4)):
                food_bias = 0.06
            keep_camp_orbit = 0.28 + ((happiness - 50.0) / 225.0) + food_bias
            if not for_rest and dist <= 7 and random.random() >= max(0.12, min(0.5, keep_camp_orbit)):
                return None
            return (target, camp_id, camp_uid)

        if task == "rest":
            region_uid = str(world._resolve_agent_work_village_uid(agent) or "") if hasattr(world, "_resolve_agent_work_village_uid") else ""
            if int(getattr(agent, "hunger", 100)) < 20:
                if hasattr(world, "record_camp_not_chosen_reason"):
                    world.record_camp_not_chosen_reason("hunger_override", region=region_uid or None)
                target = self.find_nearest(agent, world.food, "food", self.vision_radius + 3)
                if target is not None:
                    return self.move_towards(agent, world, target)
            role_key = str(getattr(agent, "role", "other") or "other")
            uid = str(world._resolve_agent_work_village_uid(agent) or "") if hasattr(world, "_resolve_agent_work_village_uid") else ""
            home_id = getattr(agent, "home_building_id", None)
            if home_id is not None:
                home = getattr(world, "buildings", {}).get(str(home_id))
                if isinstance(home, dict) and str(home.get("type", "")) == "house":
                    if hasattr(world, "record_recovery_stage"):
                        world.record_recovery_stage(agent, "home_target_available", village_uid=uid, role=role_key)
                    hx = int(home.get("x", agent.x))
                    hy = int(home.get("y", agent.y))
                    if abs(int(agent.x) - hx) + abs(int(agent.y) - hy) > 1:
                        if hasattr(world, "record_camp_targeting"):
                            world.record_camp_targeting("rest_target_home", region=uid or None)
                        if hasattr(world, "record_recovery_stage"):
                            world.record_recovery_stage(agent, "home_target_selected", village_uid=uid, role=role_key)
                        return self.move_towards(agent, world, (hx, hy))
                    if hasattr(world, "record_camp_targeting"):
                        world.record_camp_targeting("rest_target_home", region=uid or None)
                elif hasattr(world, "record_recovery_failure_reason"):
                    world.record_recovery_failure_reason(agent, "no_valid_home_target", village_uid=uid, role=role_key)
            elif hasattr(world, "record_recovery_failure_reason"):
                world.record_recovery_failure_reason(agent, "no_home", village_uid=uid, role=role_key)
            camp_target = _camp_return_target(for_rest=True)
            if camp_target is not None:
                target, camp_id, camp_uid = camp_target
                if hasattr(world, "record_camp_targeting"):
                    world.record_camp_targeting("rest_target_camp", region=camp_uid or uid or None)
                if hasattr(world, "record_camp_event"):
                    world.record_camp_event(
                        "camp_return_events",
                        camp_id=camp_id or None,
                        village_uid=camp_uid or None,
                    )
                return self.move_towards(agent, world, target)
            elif hasattr(world, "record_camp_not_chosen_reason"):
                has_inactive_in_range = False
                for camp in (getattr(world, "camps", {}) or {}).values():
                    if not isinstance(camp, dict):
                        continue
                    cx = int(camp.get("x", agent.x))
                    cy = int(camp.get("y", agent.y))
                    dist = abs(int(agent.x) - cx) + abs(int(agent.y) - cy)
                    if dist <= 16 and not bool(camp.get("active", False)):
                        has_inactive_in_range = True
                        break
                world.record_camp_not_chosen_reason(
                    "camp_not_active" if has_inactive_in_range else "no_camp_in_range",
                    region=uid or None,
                )
            social_target = _social_gravity_return_target()
            if social_target is not None:
                target, event_key, uid = social_target
                if hasattr(world, "record_camp_not_chosen_reason"):
                    world.record_camp_not_chosen_reason("task_override", region=uid or None)
                if hasattr(world, "record_social_gravity_event"):
                    world.record_social_gravity_event(event_key, village_uid=uid or None)
                return self.move_towards(agent, world, target)
            if hasattr(world, "record_camp_targeting"):
                world.record_camp_targeting("rest_target_idle", region=uid or None)
            return ("wait",)

        if task == "farm_cycle":
            village = world.get_village_by_id(getattr(agent, "village_id", None))
            farm_target = self.find_farm_target(agent, world, prefer_ripe=True)
            if farm_target is not None:
                return self.move_towards(agent, world, farm_target)

            # Bootstrap-only material pass: gather prep wood when no usable farm target exists.
            if int(agent.inventory.get("wood", 0)) < 1:
                target = self.find_nearest(agent, world.wood, "wood", max(world.width, world.height))
                if target is not None:
                    return self.move_towards(agent, world, target)

            build_pos = self.find_farm_build_target(agent, world)
            if build_pos is not None:
                return self.move_towards(agent, world, build_pos)
            self._record_gap_block(world, agent, "no_farm_target")

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
            self._record_gap_block(world, agent, "no_resource_target")

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
            self._record_gap_block(world, agent, "no_resource_target")

        if task == "build_storage":
            salient_storage = self._attention_building_target(agent, world, {"storage"})
            if salient_storage is not None:
                return self.move_towards(agent, world, salient_storage)
            site_target = _nearest_construction_site_target("storage")
            if site_target is not None:
                return self.move_towards(agent, world, site_target)
            collaborator = self._attention_social_target(agent, same_village_only=True)
            if collaborator is not None and random.random() < 0.2:
                return self.move_towards(agent, world, collaborator)
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
            salient_house = self._attention_building_target(agent, world, {"house", "storage"})
            if salient_house is not None:
                return self.move_towards(agent, world, salient_house)
            site_target = _nearest_construction_site_target("house")
            if site_target is not None:
                return self.move_towards(agent, world, site_target)
            collaborator = self._attention_social_target(agent, same_village_only=True)
            if collaborator is not None and random.random() < 0.2:
                return self.move_towards(agent, world, collaborator)
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
            self._record_gap_block(world, agent, "no_target_candidate")

        if task == "prototype_attempt":
            target = None
            if hasattr(world, "_active_prototype_for_agent"):
                try:
                    instance = world._active_prototype_for_agent(agent)
                except Exception:
                    instance = None
                if isinstance(instance, dict):
                    loc = instance.get("location", {})
                    if isinstance(loc, dict):
                        target = (int(loc.get("x", agent.x)), int(loc.get("y", agent.y)))
            if target is not None:
                needs = {"wood": 0, "stone": 0}
                if hasattr(world, "get_proto_material_needs_for_agent"):
                    try:
                        candidate_needs = world.get_proto_material_needs_for_agent(agent)
                    except Exception:
                        candidate_needs = {}
                    if isinstance(candidate_needs, dict):
                        needs = {
                            "wood": max(0, int(candidate_needs.get("wood", 0))),
                            "stone": max(0, int(candidate_needs.get("stone", 0))),
                        }
                if (
                    int(agent.inventory.get("wood", 0)) < int(needs.get("wood", 0))
                    or int(agent.inventory.get("stone", 0)) < int(needs.get("stone", 0))
                ):
                    village = world.get_village_by_id(getattr(agent, "village_id", None))
                    if village:
                        sp = village.get("storage_pos")
                        if sp:
                            return self.move_towards(agent, world, (int(sp["x"]), int(sp["y"])))
                return self.move_towards(agent, world, target)
            village_home = self._get_known_village_center(agent, world)
            if village_home is not None:
                return self.move_towards(agent, world, village_home)

        if task == "gather_food_wild":
            anchor = getattr(agent, "proto_task_anchor", {})
            source_pos = tuple(anchor.get("source_pos", ())) if isinstance(anchor, dict) else ()
            if len(source_pos) == 2 and tuple(source_pos) in getattr(world, "food", set()):
                return self.move_towards(agent, world, (int(source_pos[0]), int(source_pos[1])))
            target = self.find_nearest(agent, world.food, "food", self.vision_radius + 3)
            if target is not None:
                return self.move_towards(agent, world, target)
            social_target = _social_gravity_return_target()
            if social_target is not None:
                target, event_key, uid = social_target
                if hasattr(world, "record_social_gravity_event"):
                    world.record_social_gravity_event(event_key, village_uid=uid or None)
                return self.move_towards(agent, world, target)
            self._record_gap_block(world, agent, "no_resource_target")

        if task == "food_logistics":
            site_target = _nearest_under_construction_site_with_needs()
            if site_target is not None and (
                int(agent.inventory.get("wood", 0)) > 0
                or int(agent.inventory.get("stone", 0)) > 0
                or int(agent.inventory.get("food", 0)) > 0
            ):
                return self.move_towards(agent, world, site_target)
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
            self._record_gap_block(world, agent, "no_target_candidate")

        if task == "village_logistics":
            site_target = _nearest_under_construction_site_with_needs()
            if site_target is not None:
                if (
                    int(agent.inventory.get("wood", 0)) > 0
                    or int(agent.inventory.get("stone", 0)) > 0
                    or int(agent.inventory.get("food", 0)) > 0
                ):
                    return self.move_towards(agent, world, site_target)
                village = world.get_village_by_id(getattr(agent, "village_id", None))
                if village:
                    sp = village.get("storage_pos")
                    if sp:
                        return self.move_towards(agent, world, (sp["x"], sp["y"]))
            salient_logistics = self._attention_building_target(agent, world, {"storage", "house"})
            if salient_logistics is not None and random.random() < 0.25:
                return self.move_towards(agent, world, salient_logistics)
            collaborator = self._attention_social_target(agent, same_village_only=True)
            if collaborator is not None and random.random() < 0.25:
                return self.move_towards(agent, world, collaborator)
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
            self._record_gap_block(world, agent, "no_target_candidate")

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

        social_target = _social_gravity_return_target()
        if social_target is not None:
            target, event_key, uid = social_target
            if hasattr(world, "record_social_gravity_event"):
                world.record_social_gravity_event(event_key, village_uid=uid or None)
            return self.move_towards(agent, world, target)

        camp_target = _camp_return_target(for_rest=False)
        if camp_target is not None:
            target, camp_id, camp_uid = camp_target
            if hasattr(world, "record_camp_event"):
                world.record_camp_event(
                    "camp_return_events",
                    camp_id=camp_id or None,
                    village_uid=camp_uid or None,
                )
            return self.move_towards(agent, world, target)

        village_home = self._get_known_village_center(agent, world)
        happiness = max(0.0, min(100.0, float(getattr(agent, "happiness", 50.0))))
        village_return_bias = 0.35 + ((happiness - 50.0) / 250.0)
        if village_home is not None and random.random() < max(0.18, min(0.5, village_return_bias)):
            return self.move_towards(agent, world, village_home)

        return self.wander(agent, world)

    def _get_village_strategy(self, agent, world) -> str:
        subjective = getattr(agent, "subjective_state", {})
        if isinstance(subjective, dict):
            local_signals = subjective.get("local_signals", {})
            if isinstance(local_signals, dict):
                priority = str(local_signals.get("priority", "")).strip().lower()
                if priority:
                    return strategy_from_priority(priority)
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

        preferred_uid = str(getattr(agent, "home_village_uid", "") or getattr(agent, "primary_village_uid", "") or "")
        if preferred_uid:
            for village in getattr(world, "villages", []):
                if not isinstance(village, dict):
                    continue
                if str(village.get("village_uid", "")) != preferred_uid:
                    continue
                c = village.get("center")
                if isinstance(c, dict):
                    return (int(c.get("x", agent.x)), int(c.get("y", agent.y)))

        mem = agent.memory.get("villages", set())
        if mem:
            ax, ay = agent.x, agent.y
            return min(mem, key=lambda p: abs(p[0] - ax) + abs(p[1] - ay))

        if hasattr(world, "nearest_active_camp_for_agent"):
            camp = world.nearest_active_camp_for_agent(agent, max_distance=12)
            if isinstance(camp, dict):
                return (int(camp.get("x", agent.x)), int(camp.get("y", agent.y)))

        return None

    def _attention_building_target(self, agent, world, allowed_types: Set[str]) -> Optional[Coord]:
        subjective = getattr(agent, "subjective_state", {})
        if not isinstance(subjective, dict):
            return get_known_useful_building_target(agent, allowed_types)
        attention = subjective.get("attention", {})
        if not isinstance(attention, dict):
            return get_known_useful_building_target(agent, allowed_types)
        targets = attention.get("top_building_targets", [])
        if not isinstance(targets, list):
            return get_known_useful_building_target(agent, allowed_types)
        allowed = {str(t) for t in allowed_types}
        for entry in targets:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("type", "")) not in allowed:
                continue
            return (int(entry.get("x", 0)), int(entry.get("y", 0)))
        known = get_known_useful_building_target(agent, allowed)
        if known is None:
            return None
        kx, ky = known
        if 0 <= int(kx) < int(getattr(world, "width", 0)) and 0 <= int(ky) < int(getattr(world, "height", 0)):
            return known
        return None

    def _attention_social_target(self, agent, *, same_village_only: bool = True) -> Optional[Coord]:
        subjective = getattr(agent, "subjective_state", {})
        if not isinstance(subjective, dict):
            return None
        attention = subjective.get("attention", {})
        if not isinstance(attention, dict):
            return None
        targets = attention.get("top_social_targets", [])
        if not isinstance(targets, list):
            return None
        for entry in targets:
            if not isinstance(entry, dict):
                continue
            if same_village_only and not bool(entry.get("same_village", False)):
                continue
            return (int(entry.get("x", 0)), int(entry.get("y", 0)))
        return None

    def _salient_local_leader(self, agent) -> Optional[Dict[str, Any]]:
        subjective = getattr(agent, "subjective_state", {})
        if not isinstance(subjective, dict):
            return None
        attention = subjective.get("attention", {})
        if not isinstance(attention, dict):
            return None
        leader = attention.get("salient_local_leader")
        if not isinstance(leader, dict):
            return None
        if not str(leader.get("agent_id", "")):
            return None
        return leader

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
        world: Optional[Any] = None,
    ) -> Optional[Coord]:
        ax = agent.x
        ay = agent.y

        best: Optional[Coord] = None
        best_d = 999999

        # Practical knowledge bias: use compact learned spots before pure search.
        known_spot = get_known_resource_spot(agent, memory_key, min_confidence=0.35, world=world)
        if known_spot is not None:
            kx, ky = known_spot
            d = abs(kx - ax) + abs(ky - ay)
            if d <= radius:
                return known_spot

        # Episodic bias: reuse recent successful finds when still plausible.
        recent_resource = find_recent_resource_memory(agent, memory_key)
        for ev in reversed(recent_resource):
            if str(ev.get("type", "")) not in {"found_resource", "construction_progress", "hunger_relief"}:
                continue
            loc = ev.get("location", {})
            if not isinstance(loc, dict):
                continue
            x = int(loc.get("x", 0))
            y = int(loc.get("y", 0))
            d = abs(x - ax) + abs(y - ay)
            if d <= radius:
                return (x, y)

        # Episodic bias: avoid immediate retry loops after recent local failures.
        failed_recent = get_recent_memory_events(agent, "failed_resource_search", limit=6)
        proto_traits = ensure_agent_proto_traits(agent)
        caution = float(proto_traits.get("caution", 0.5))
        resilience = float(proto_traits.get("resilience", 0.5))
        local_culture = (
            getattr(agent, "subjective_state", {}).get("local_culture", {})
            if isinstance(getattr(agent, "subjective_state", {}), dict)
            else {}
        )
        culture_risk = float(local_culture.get("risk_norm", 0.5)) if isinstance(local_culture, dict) else 0.5
        avoid_window_ticks = 4 + int(caution * 6) - int(culture_risk * 2)
        avoid_radius = 2 + int(caution * 2) - int(culture_risk)
        avoid_window_ticks = max(2, avoid_window_ticks)
        avoid_radius = max(1, avoid_radius)
        if resilience > 0.7:
            avoid_window_ticks = max(3, avoid_window_ticks - 1)
        for ev in reversed(failed_recent):
            if str(ev.get("resource_type", "")) != str(memory_key):
                continue
            if int(getattr(agent, "subjective_state", {}).get("last_perception_tick", 0)) - int(ev.get("tick", 0)) > avoid_window_ticks:
                continue
            loc = ev.get("location", {})
            if not isinstance(loc, dict):
                continue
            fx = int(loc.get("x", 0))
            fy = int(loc.get("y", 0))
            if abs(fx - ax) + abs(fy - ay) <= avoid_radius:
                return None

        subjective = getattr(agent, "subjective_state", {})
        if isinstance(subjective, dict):
            attention = subjective.get("attention", {})
            if isinstance(attention, dict):
                top_targets = attention.get("top_resource_targets", [])
                if isinstance(top_targets, list):
                    for entry in top_targets:
                        if not isinstance(entry, dict):
                            continue
                        if str(entry.get("resource", "")) != str(memory_key):
                            continue
                        x = int(entry.get("x", 0))
                        y = int(entry.get("y", 0))
                        d = abs(x - ax) + abs(y - ay)
                        if d <= radius:
                            return (x, y)

        # Prefer situated perception if available; do not pull distant unseen targets.
        if isinstance(subjective, dict):
            nearby_resources = subjective.get("nearby_resources", {})
            if isinstance(nearby_resources, dict):
                perceived = nearby_resources.get(memory_key, [])
                if isinstance(perceived, list):
                    for entry in perceived:
                        if not isinstance(entry, dict):
                            continue
                        x = int(entry.get("x", 0))
                        y = int(entry.get("y", 0))
                        d = abs(x - ax) + abs(y - ay)
                        if d <= radius and d < best_d:
                            best_d = d
                            best = (x, y)
                    if best is not None:
                        return best

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
        target = self._apply_target_stickiness(agent, world, target)
        self._record_gap_stage(world, agent, "target_found_count")

        if start == target:
            return ("wait",)

        path = self._get_cached_path(agent, start, target)
        if path is None:
            if hasattr(world, "record_movement_path_recompute"):
                world.record_movement_path_recompute(agent, target)
            path = astar(world, start, target)
            self._store_cached_path(agent, target, path)

        if path is not None and len(path) >= 2:
            next_x, next_y = path[1]
            dx = next_x - agent.x
            dy = next_y - agent.y

            immediate_backtrack = self._is_immediate_backtrack(agent, (next_x, next_y))
            if world.is_walkable(next_x, next_y) and not world.is_occupied(next_x, next_y) and not immediate_backtrack:
                self._advance_cached_path(agent, start, target, path)
                self._record_gap_stage(world, agent, "movement_started_count")
                return ("move", dx, dy)
            detour = self.local_detour_step(
                agent,
                world,
                target,
                avoid_pos=getattr(agent, "movement_prev_tile", None),
                allow_backtrack=self._allow_backtrack_override(agent, world, target),
            )
            if detour is not None:
                self._clear_cached_path(agent)
                self._record_gap_stage(world, agent, "movement_started_count")
                return detour

        fallback = self.greedy_step(agent, world, target)
        if isinstance(fallback, tuple) and len(fallback) >= 1 and str(fallback[0]) == "move":
            self._clear_cached_path(agent)
            self._record_gap_stage(world, agent, "movement_started_count")
            return fallback
        self._clear_cached_path(agent)
        self._record_gap_block(world, agent, "no_path")
        return fallback

    def greedy_step(self, agent, world, target: Coord) -> Tuple[str, ...]:
        detour = self.local_detour_step(
            agent,
            world,
            target,
            avoid_pos=getattr(agent, "movement_prev_tile", None),
            allow_backtrack=self._allow_backtrack_override(agent, world, target),
        )
        if detour is not None:
            return detour
        return self.wander(agent, world)

    def local_detour_step(
        self,
        agent,
        world,
        target: Coord,
        *,
        avoid_pos: Optional[Coord] = None,
        allow_backtrack: bool = False,
    ) -> Optional[Tuple[str, ...]]:
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
            if (
                avoid_pos is not None
                and not allow_backtrack
                and (int(nx), int(ny)) == (int(avoid_pos[0]), int(avoid_pos[1]))
            ):
                continue
            nd = abs(tx - nx) + abs(ty - ny)
            ranked.append((nd, dx, dy))

        if not ranked:
            if avoid_pos is not None and not allow_backtrack:
                return self.local_detour_step(agent, world, target, avoid_pos=None, allow_backtrack=True)
            return None

        ranked.sort(key=lambda t: t[0])

        # Prefer strict progress first, then allow side-step to break jams.
        for nd, dx, dy in ranked:
            if nd < current_d:
                return ("move", dx, dy)

        if current_d <= 2 and not allow_backtrack:
            return ("wait",)

        nd, dx, dy = ranked[0]
        if nd <= current_d + 1:
            return ("move", dx, dy)

        return None

    def wander(self, agent, world) -> Tuple[str, ...]:
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (0, 0)]
        random.shuffle(dirs)
        avoid_pos = getattr(agent, "movement_prev_tile", None)

        for dx, dy in dirs:
            if dx == 0 and dy == 0:
                return ("wait",)

            nx, ny = agent.x + dx, agent.y + dy
            if (
                avoid_pos is not None
                and (int(nx), int(ny)) == (int(avoid_pos[0]), int(avoid_pos[1]))
                and not self._is_urgent_movement_context(agent, world)
            ):
                continue
            if world.is_walkable(nx, ny) and not world.is_occupied(nx, ny):
                return ("move", dx, dy)

        return ("wait",)

    def _is_urgent_movement_context(self, agent, world) -> bool:
        hunger = float(getattr(agent, "hunger", 100.0))
        if hunger <= 15.0:
            return True
        if str(getattr(agent, "task", "")) == "survive":
            return True
        intention = getattr(agent, "current_intention", {})
        if isinstance(intention, dict):
            itype = str(intention.get("type", ""))
            if itype in {"survive", "gather_food"} and hunger <= 25.0:
                return True
        return False

    def _apply_target_stickiness(self, agent, world, incoming_target: Coord) -> Coord:
        target = (int(incoming_target[0]), int(incoming_target[1]))
        start = (int(getattr(agent, "x", 0)), int(getattr(agent, "y", 0)))
        current_tick = int(getattr(world, "tick", 0))
        committed = getattr(agent, "movement_commit_target", None)
        commit_until = int(getattr(agent, "movement_commit_until_tick", -1))
        if (
            isinstance(committed, tuple)
            and len(committed) == 2
            and commit_until >= current_tick
            and not self._is_urgent_movement_context(agent, world)
        ):
            committed_target = (int(committed[0]), int(committed[1]))
            if committed_target != target and bool(world.is_walkable(committed_target[0], committed_target[1])):
                d_current = abs(start[0] - committed_target[0]) + abs(start[1] - committed_target[1])
                d_incoming = abs(start[0] - target[0]) + abs(start[1] - target[1])
                marginal_switch = d_incoming >= (d_current - int(self.target_switch_improvement_margin))
                near_committed = d_current <= 3
                if marginal_switch or near_committed:
                    target = committed_target
        agent.movement_commit_target = target
        agent.movement_commit_until_tick = current_tick + int(self.target_stickiness_ticks)
        return target

    def _get_cached_path(self, agent, start: Coord, target: Coord) -> Optional[list[Coord]]:
        cached_target = getattr(agent, "movement_cached_target", None)
        cached_path = getattr(agent, "movement_cached_path", None)
        if (
            isinstance(cached_target, tuple)
            and len(cached_target) == 2
            and (int(cached_target[0]), int(cached_target[1])) == (int(target[0]), int(target[1]))
            and isinstance(cached_path, list)
            and len(cached_path) >= 2
            and tuple(cached_path[0]) == (int(start[0]), int(start[1]))
        ):
            return [(int(p[0]), int(p[1])) for p in cached_path]
        return None

    def _store_cached_path(self, agent, target: Coord, path: Optional[list[Coord]]) -> None:
        if not isinstance(path, list) or len(path) < 2:
            self._clear_cached_path(agent)
            return
        agent.movement_cached_target = (int(target[0]), int(target[1]))
        agent.movement_cached_path = [(int(p[0]), int(p[1])) for p in path]
        agent.movement_cached_path_tick = int(getattr(agent, "movement_cached_path_tick", -1)) + 1

    def _advance_cached_path(self, agent, start: Coord, target: Coord, path: list[Coord]) -> None:
        if not isinstance(path, list) or len(path) < 2 or tuple(path[0]) != (int(start[0]), int(start[1])):
            self._clear_cached_path(agent)
            return
        trimmed = [(int(p[0]), int(p[1])) for p in path[1:]]
        if len(trimmed) < 2:
            self._clear_cached_path(agent)
            return
        agent.movement_cached_target = (int(target[0]), int(target[1]))
        agent.movement_cached_path = trimmed

    def _clear_cached_path(self, agent) -> None:
        agent.movement_cached_target = None
        agent.movement_cached_path = []

    def _is_immediate_backtrack(self, agent, next_pos: Coord) -> bool:
        prev = getattr(agent, "movement_prev_tile", None)
        if not isinstance(prev, tuple) or len(prev) != 2:
            return False
        return (int(prev[0]), int(prev[1])) == (int(next_pos[0]), int(next_pos[1]))

    def _allow_backtrack_override(self, agent, world, target: Coord) -> bool:
        if self._is_urgent_movement_context(agent, world):
            return True
        start = (int(getattr(agent, "x", 0)), int(getattr(agent, "y", 0)))
        d = abs(int(target[0]) - start[0]) + abs(int(target[1]) - start[1])
        return d > 4


class LLMBrain:
    def __init__(self, planner: Planner, fallback: FoodBrain, think_every_ticks: int = 240):
        self.planner = planner
        self.fallback = fallback
        self.think_every_ticks = think_every_ticks

    def decide(self, agent, world) -> Tuple[str, ...]:
        update_agent_cognitive_profile(world, agent)
        self._apply_reflection_guidance(agent, world)
        if agent.hunger < 60 or agent.inventory.get("food", 0) == 0:
            return self.fallback.decide(agent, world)

        if getattr(agent, "role", "") == "leader":
            return self._decide_leader_governance(agent, world)

        self.maybe_reflect_with_llm(agent, world)

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

        self.maybe_reflect_with_llm(agent, world)

        # Leader stays mostly near village center; workers execute operations.
        if village is not None:
            c = village.get("center")
            if c and random.random() < 0.65:
                return self.fallback.move_towards(agent, world, (c["x"], c["y"]))

        return ("wait",)

    def _should_think(self, agent, world) -> bool:
        profile = ensure_agent_cognitive_profile(agent)
        if not should_agent_reflect(world, agent):
            return False
        min_interval = min(int(self.think_every_ticks), int(profile.get("reflection_cooldown_ticks", self.think_every_ticks)))
        if int(world.tick) - int(agent.last_llm_tick) < int(min_interval):
            profile["reflection_block_reason"] = "brain_interval"
            return False
        return True

    def maybe_reflect_with_llm(self, agent, world) -> bool:
        if not self._should_think(agent, world):
            block_reason = str(ensure_agent_cognitive_profile(agent).get("reflection_block_reason", "blocked"))
            if hasattr(world, "record_reflection_skip"):
                world.record_reflection_skip(block_reason)
            return False
        profile = ensure_agent_cognitive_profile(agent)
        reason = detect_agent_reflection_reason(world, agent)
        if reason is None:
            profile["reflection_block_reason"] = "no_trigger_reason"
            if hasattr(world, "record_reflection_skip"):
                world.record_reflection_skip("no_trigger_reason")
            return False
        state = getattr(agent, "subjective_state", {})
        attention = state.get("attention", {}) if isinstance(state, dict) else {}
        if bool(attention.get("salient_local_leader")):
            reason = reason or "social_importance"
        current_intention = getattr(agent, "current_intention", {})
        if isinstance(current_intention, dict) and int(current_intention.get("failed_ticks", 0)) >= 2:
            reason = "blocked_intention"
        profile["last_reflection_reason"] = reason
        if hasattr(world, "record_reflection_trigger"):
            world.record_reflection_trigger(str(reason))
        self._schedule_llm_request(agent, world, reflection_reason=reason)
        return True

    def _schedule_llm_request(self, agent, world, reflection_reason: str = "general") -> None:
        if not getattr(world, "llm_enabled", True):
            logger.warning("LLM disabled: using deterministic fallback for agent_id=%s", getattr(agent, "agent_id", "unknown"))
            return

        agent.llm_pending = True
        agent.last_llm_tick = world.tick
        profile = ensure_agent_cognitive_profile(agent)
        profile["last_reflection_tick"] = int(world.tick)
        profile["reflection_count"] = int(profile.get("reflection_count", 0)) + 1

        context = build_agent_cognitive_context(world, agent)
        context["reflection_reason"] = str(reflection_reason)
        prompt = self._make_prompt(agent, world, context=context, reflection_reason=reflection_reason)
        logger.info("LLM request scheduled role=%s agent_id=%s", getattr(agent, "role", "npc"), getattr(agent, "agent_id", "unknown"))
        if hasattr(world, "record_reflection_attempt"):
            world.record_reflection_attempt(agent, str(reflection_reason))

        if hasattr(world, "llm_calls_this_tick"):
            world.llm_calls_this_tick += 1
        mode = self._reflection_mode(world)
        force_stub = mode == "force_local_stub"

        if force_stub:
            if hasattr(world, "record_reflection_executed"):
                world.record_reflection_executed(agent, str(reflection_reason))
            self._apply_deterministic_stub_reflection(agent, world, context, str(reflection_reason))
            agent.llm_pending = False
            return

        if hasattr(world, "record_llm_interaction"):
            world.record_llm_interaction()

        try:
            loop = asyncio.get_running_loop()
            if getattr(agent, "role", "") == "leader":
                loop.create_task(
                    self._request_leader_priority(
                        agent,
                        world,
                        prompt,
                        reflection_reason=str(reflection_reason),
                    )
                )
            else:
                loop.create_task(self._request_reflection(agent, world, prompt, reflection_reason=reflection_reason))
        except RuntimeError:
            # Scenario/test mode fallback: execute bounded request synchronously if
            # no loop is running, otherwise deterministic fallback remains active.
            allow_sync = bool(getattr(world, "llm_sync_execution", True))
            if not allow_sync:
                agent.llm_pending = False
                if getattr(agent, "role", "") == "leader":
                    village = world.get_village_by_id(getattr(agent, "village_id", None))
                    if village is not None:
                        traits = getattr(agent, "leader_traits", None) or village.get("leader_profile", {})
                        p = deterministic_priority_from_needs(village.get("needs", {}), traits, village)
                        apply_village_priority(village, p, world.tick, "deterministic_no_loop")
                logger.warning("LLM scheduling failed: no running event loop; deterministic fallback remains active")
                return
            try:
                if getattr(agent, "role", "") == "leader":
                    asyncio.run(
                        self._request_leader_priority(
                            agent,
                            world,
                            prompt,
                            reflection_reason=str(reflection_reason),
                        )
                    )
                else:
                    asyncio.run(
                        self._request_reflection(
                            agent,
                            world,
                            prompt,
                            reflection_reason=str(reflection_reason),
                        )
                    )
            except Exception:
                agent.llm_pending = False
                profile["last_reflection_outcome"] = "error_fallback"
                profile["reflection_fallback_count"] = int(profile.get("reflection_fallback_count", 0)) + 1
                if hasattr(world, "record_reflection_outcome"):
                    world.record_reflection_outcome("fallback", reason="fallback_used")
                logger.warning("LLM sync execution failed; deterministic fallback remains active")

    async def _request_leader_priority(self, agent, world, prompt: str, reflection_reason: str = "general") -> None:
        village = world.get_village_by_id(getattr(agent, "village_id", None))
        traits = getattr(agent, "leader_traits", None) or (village.get("leader_profile", {}) if village else {})
        timeout_s = float(getattr(world, "llm_timeout_seconds", 3.0))
        if hasattr(world, "record_reflection_executed"):
            world.record_reflection_executed(agent, str(reflection_reason))
        try:
            raw = await asyncio.wait_for(
                self.planner.propose_goal_async(prompt),
                timeout=timeout_s,
            )
            priority = self._extract_priority_from_llm(raw)

            if priority is None:
                needs = village.get("needs", {}) if village else {}
                priority = deterministic_priority_from_needs(needs, traits, village)
                if hasattr(world, "record_reflection_outcome"):
                    world.record_reflection_outcome("rejected", reason="invalid_schema")
            else:
                if hasattr(world, "record_reflection_outcome"):
                    world.record_reflection_outcome("accepted", reason="accepted", source="provider")

            if village is not None:
                apply_village_priority(village, priority, world.tick, "llm")
        except asyncio.TimeoutError:
            logger.warning(
                "LLM leader request failed or timed out; fallback priority applied agent_id=%s timeout_s=%.2f",
                getattr(agent, "agent_id", "unknown"),
                timeout_s,
            )
            needs = village.get("needs", {}) if village else {}
            priority = deterministic_priority_from_needs(needs, traits, village)
            if village is not None:
                apply_village_priority(village, priority, world.tick, "deterministic_fallback")
            if hasattr(world, "record_reflection_outcome"):
                world.record_reflection_outcome("fallback", reason="timeout")
        except Exception as exc:
            needs = village.get("needs", {}) if village else {}
            priority = deterministic_priority_from_needs(needs, traits, village)
            if village is not None:
                apply_village_priority(village, priority, world.tick, "deterministic_fallback")
            reason = "provider_unavailable" if self._is_provider_unavailable_error(exc) else "fallback_used"
            if hasattr(world, "record_reflection_outcome"):
                world.record_reflection_outcome("fallback", reason=reason)
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

    def _extract_first_json_object_text(self, raw: str) -> Optional[str]:
        text = (raw or "").strip()
        if not text:
            return None
        if text.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
            cleaned = re.sub(r"\s*```$", "", cleaned).strip()
            text = cleaned
        start = text.find("{")
        if start < 0:
            return None
        depth = 0
        in_string = False
        escaped = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : idx + 1]
        return None

    def _parse_reflection_payload(self, raw: str) -> Tuple[Optional[Dict[str, Any]], str]:
        text = (raw or "").strip()
        if not text:
            return None, "malformed_output"
        candidates = [text]
        extracted = self._extract_first_json_object_text(text)
        if extracted and extracted != text:
            candidates.append(extracted)
        for candidate in candidates:
            try:
                obj = json.loads(candidate)
            except Exception:
                continue
            if isinstance(obj, dict):
                return obj, ""
            return None, "invalid_schema"
        return None, "malformed_output"

    def _validate_reflection_output(
        self,
        payload: Dict[str, Any],
        *,
        world: Any = None,
        agent: Any = None,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        if not isinstance(payload, dict):
            return None, "invalid_schema"
        allowed_intentions = {
            "gather_food",
            "gather_resource",
            "deliver_resource",
            "build_structure",
            "work_mine",
            "work_lumberyard",
            "explore",
        }
        allowed_target_kind = {"resource", "building", "social", "none"}
        allowed_resource = {"food", "wood", "stone", ""}
        allowed_tags = {
            "survival",
            "cooperation",
            "work",
            "exploration",
            "logistics",
            "risk_management",
        }
        for required_key in (
            "suggested_intention_type",
            "suggested_target_kind",
            "suggested_resource_type",
            "reasoning_tags",
        ):
            if required_key not in payload:
                return None, "invalid_schema"
        intention = str(payload.get("suggested_intention_type", "")).strip().lower()
        target_kind = str(payload.get("suggested_target_kind", "")).strip().lower()
        resource_type = str(payload.get("suggested_resource_type", "")).strip().lower()
        tags = payload.get("reasoning_tags", [])
        if intention not in allowed_intentions:
            return None, "unsupported_values"
        if target_kind not in allowed_target_kind:
            return None, "unsupported_values"
        if resource_type not in allowed_resource:
            return None, "unsupported_values"
        if not isinstance(tags, list):
            return None, "invalid_schema"
        cleaned_tags = [str(t).strip().lower() for t in tags if str(t).strip().lower() in allowed_tags][:3]
        cleaned: Dict[str, Any] = {
            "suggested_intention_type": intention,
            "suggested_target_kind": target_kind,
            "suggested_resource_type": resource_type if resource_type else None,
            "reasoning_tags": cleaned_tags,
        }

        innovation = payload.get("innovation_proposal")
        if innovation is not None:
            if world is None or agent is None or not isinstance(innovation, dict):
                return None, "invalid_schema"
            local_reason = detect_agent_innovation_opportunity(world, agent)
            if local_reason is None:
                if hasattr(world, "record_proto_asset_proposal_rejected"):
                    world.record_proto_asset_proposal_rejected("no_local_opportunity")
                return None, "unsupported_values"
            proposal_seed = {
                "proposal_id": str(innovation.get("proposal_id", f"tmp-{getattr(agent, 'agent_id', 'unknown')}-{int(getattr(world, 'tick', 0))}")),
                "inventor_agent_id": str(getattr(agent, "agent_id", "")),
                "tick_created": int(getattr(world, "tick", 0)),
                "reason": str(innovation.get("reason", local_reason) or local_reason),
                "name": str(innovation.get("name", "")),
                "asset_kind": str(innovation.get("asset_kind", "")),
                "category": str(innovation.get("category", "")),
                "intended_effects": list(innovation.get("intended_effects", [])),
                "required_materials": dict(innovation.get("required_materials", {})),
                "footprint_hint": dict(innovation.get("footprint_hint", {})),
                "status": "proposed",
            }
            validated_proposal, proposal_reason = validate_proto_asset_proposal(proposal_seed)
            if validated_proposal is None:
                if hasattr(world, "record_proto_asset_proposal_rejected"):
                    world.record_proto_asset_proposal_rejected(proposal_reason or "invalid_schema")
                return None, proposal_reason or "invalid_schema"
            cleaned["innovation_proposal"] = {
                "reason": str(validated_proposal.get("reason", local_reason)),
                "name": str(validated_proposal.get("name", "")),
                "asset_kind": str(validated_proposal.get("asset_kind", "")),
                "category": str(validated_proposal.get("category", "")),
                "intended_effects": list(validated_proposal.get("intended_effects", [])),
                "required_materials": dict(validated_proposal.get("required_materials", {})),
                "footprint_hint": dict(validated_proposal.get("footprint_hint", {})),
            }
        return cleaned, ""

    def _is_provider_unavailable_error(self, exc: Exception) -> bool:
        text = str(exc).lower()
        markers = ("connection", "refused", "unreachable", "name resolution", "failed to establish", "timed out")
        return any(marker in text for marker in markers) or isinstance(exc, OSError)

    def _reflection_mode(self, world) -> str:
        if bool(getattr(world, "llm_force_local_stub", False)):
            return "force_local_stub"
        mode = str(getattr(world, "llm_reflection_mode", "provider_with_stub_fallback"))
        if mode not in {"provider_only", "provider_with_stub_fallback", "force_local_stub"}:
            return "provider_with_stub_fallback"
        return mode

    def _stub_allowed(self, world) -> bool:
        mode = self._reflection_mode(world)
        return bool(getattr(world, "llm_stub_enabled", True)) and mode in {
            "provider_with_stub_fallback",
            "force_local_stub",
        }

    def _deterministic_stub_hint(
        self,
        agent,
        world,
        context: Dict[str, Any],
        reflection_reason: str,
    ) -> Dict[str, Any]:
        role = str(getattr(agent, "role", "npc"))
        state = getattr(agent, "subjective_state", {})
        attention = state.get("attention", {}) if isinstance(state, dict) else {}
        local_signals = state.get("local_signals", {}) if isinstance(state, dict) else {}
        needs = local_signals.get("needs", {}) if isinstance(local_signals, dict) else {}
        hunger = float(getattr(agent, "hunger", 100.0))
        survival = evaluate_local_survival_pressure(world, agent)
        survival_pressure = float(survival.get("survival_pressure", 0.0))
        food_crisis = bool(survival.get("food_crisis", False))
        top_resources = attention.get("top_resource_targets", []) if isinstance(attention.get("top_resource_targets"), list) else []

        def top_resource_type(default: str = "food") -> str:
            if top_resources and isinstance(top_resources[0], dict):
                found = str(top_resources[0].get("resource", "")).strip().lower()
                if found in {"food", "wood", "stone"}:
                    return found
            return default

        if food_crisis or survival_pressure >= 0.60:
            return {
                "suggested_intention_type": "deliver_resource" if role in {"hauler", "builder"} else "gather_food",
                "suggested_target_kind": "building" if role in {"hauler", "builder"} else "resource",
                "suggested_resource_type": "food",
                "reasoning_tags": ["survival", "logistics"],
            }

        if reflection_reason == "blocked_intention":
            if role == "miner":
                return {
                    "suggested_intention_type": "work_mine",
                    "suggested_target_kind": "building",
                    "suggested_resource_type": "stone",
                    "reasoning_tags": ["work", "logistics"],
                }
            if role == "woodcutter":
                return {
                    "suggested_intention_type": "work_lumberyard",
                    "suggested_target_kind": "building",
                    "suggested_resource_type": "wood",
                    "reasoning_tags": ["work", "logistics"],
                }
            if role in {"builder", "hauler"}:
                return {
                    "suggested_intention_type": "deliver_resource",
                    "suggested_target_kind": "building",
                    "suggested_resource_type": "wood" if bool(needs.get("need_materials")) else "stone",
                    "reasoning_tags": ["work", "cooperation"],
                }
        if reflection_reason == "uncertain_cooperative_choice":
            return {
                "suggested_intention_type": "deliver_resource" if role in {"builder", "hauler"} else "gather_resource",
                "suggested_target_kind": "social" if bool(attention.get("salient_local_leader")) else "building",
                "suggested_resource_type": top_resource_type("food"),
                "reasoning_tags": ["cooperation", "logistics"],
            }
        if reflection_reason == "conflicting_local_needs":
            if hunger < 45:
                return {
                    "suggested_intention_type": "gather_food",
                    "suggested_target_kind": "resource",
                    "suggested_resource_type": "food",
                    "reasoning_tags": ["survival"],
                }
            return {
                "suggested_intention_type": "deliver_resource" if role in {"builder", "hauler"} else "gather_resource",
                "suggested_target_kind": "building" if role in {"builder", "hauler"} else "resource",
                "suggested_resource_type": top_resource_type("wood"),
                "reasoning_tags": ["work", "survival"],
            }
        return {
            "suggested_intention_type": "gather_food" if hunger < 45 else "gather_resource",
            "suggested_target_kind": "resource",
            "suggested_resource_type": "food" if hunger < 45 else top_resource_type("food"),
            "reasoning_tags": ["survival"],
        }

    def _apply_deterministic_stub_reflection(
        self,
        agent,
        world,
        context: Dict[str, Any],
        reflection_reason: str,
    ) -> bool:
        if not self._stub_allowed(world):
            return False
        hint = self._deterministic_stub_hint(agent, world, context, reflection_reason)
        validated, reason = self._validate_reflection_output(hint, world=world, agent=agent)
        if validated is None:
            if hasattr(world, "record_reflection_outcome"):
                world.record_reflection_outcome("fallback", reason=reason or "fallback_used")
            return False
        profile = ensure_agent_cognitive_profile(agent)
        final_hint = dict(validated)
        final_hint["reason"] = str(reflection_reason)
        final_hint["generated_tick"] = int(getattr(world, "tick", 0))
        final_hint["source"] = "stub"
        setattr(agent, "reflection_hint", final_hint)
        profile["last_reflection_outcome"] = "deterministic_stub_used"
        profile["last_reflection_source"] = "stub"
        if hasattr(world, "record_reflection_outcome"):
            world.record_reflection_outcome("accepted", reason="deterministic_stub_used", source="stub")
        maybe_generate_innovation_proposal(world, agent, source="stub")
        return True

    async def _request_reflection(self, agent, world, prompt: str, reflection_reason: str) -> None:
        timeout_s = float(getattr(world, "llm_timeout_seconds", 3.0))
        profile = ensure_agent_cognitive_profile(agent)
        context = build_agent_cognitive_context(world, agent)
        if hasattr(world, "record_reflection_executed"):
            world.record_reflection_executed(agent, str(reflection_reason))
        try:
            raw = await asyncio.wait_for(
                self.planner.propose_goal_async(prompt),
                timeout=timeout_s,
            )
            parsed, parse_reason = self._parse_reflection_payload(str(raw or ""))
            if parsed is None:
                profile["last_reflection_outcome"] = parse_reason
                if hasattr(world, "record_reflection_outcome"):
                    world.record_reflection_outcome("rejected", reason=parse_reason)
                if self._apply_deterministic_stub_reflection(agent, world, context, str(reflection_reason)):
                    return
                if hasattr(world, "record_reflection_outcome"):
                    world.record_reflection_outcome("fallback", reason="fallback_used")
                return

            validated, validation_reason = self._validate_reflection_output(parsed, world=world, agent=agent)
            if validated is None:
                profile["last_reflection_outcome"] = validation_reason
                profile["reflection_fallback_count"] = int(profile.get("reflection_fallback_count", 0)) + 1
                if hasattr(world, "record_reflection_outcome"):
                    world.record_reflection_outcome("rejected", reason=validation_reason)
                if self._apply_deterministic_stub_reflection(agent, world, context, str(reflection_reason)):
                    return
                if hasattr(world, "record_reflection_outcome"):
                    world.record_reflection_outcome("fallback", reason="fallback_used")
                logger.warning(
                    "LLM reflection rejected (malformed/unusable), deterministic fallback remains active agent_id=%s raw=%r",
                    getattr(agent, "agent_id", "unknown"),
                    raw,
                )
                return
            hint = dict(validated)
            hint["reason"] = str(reflection_reason)
            hint["generated_tick"] = int(getattr(world, "tick", 0))
            hint["source"] = "provider"
            setattr(agent, "reflection_hint", hint)
            if isinstance(hint.get("innovation_proposal"), dict):
                maybe_generate_innovation_proposal(
                    world,
                    agent,
                    source="provider",
                    proposal_payload=dict(hint.get("innovation_proposal", {})),
                )
            else:
                maybe_generate_innovation_proposal(world, agent, source="provider")
            profile["last_reflection_outcome"] = "accepted"
            profile["last_reflection_source"] = "provider"
            profile["reflection_success_count"] = int(profile.get("reflection_success_count", 0)) + 1
            if hasattr(world, "record_reflection_outcome"):
                world.record_reflection_outcome("accepted", reason="accepted", source="provider")
            logger.info(
                "LLM reflection accepted role=%s agent_id=%s intention=%s reason=%s",
                getattr(agent, "role", "npc"),
                getattr(agent, "agent_id", "unknown"),
                hint.get("suggested_intention_type"),
                reflection_reason,
            )

        except asyncio.TimeoutError:
            profile["last_reflection_outcome"] = "timeout"
            if hasattr(world, "record_reflection_outcome"):
                world.record_reflection_outcome("fallback", reason="timeout")
            if self._apply_deterministic_stub_reflection(agent, world, context, str(reflection_reason)):
                return
            if hasattr(world, "record_reflection_outcome"):
                world.record_reflection_outcome("fallback", reason="fallback_used")
        except Exception as e:
            outcome_reason = "provider_unavailable" if self._is_provider_unavailable_error(e) else "fallback_used"
            profile["last_reflection_outcome"] = outcome_reason
            profile["reflection_fallback_count"] = int(profile.get("reflection_fallback_count", 0)) + 1
            if hasattr(world, "record_reflection_outcome"):
                world.record_reflection_outcome("fallback", reason=outcome_reason)
            if self._apply_deterministic_stub_reflection(agent, world, context, str(reflection_reason)):
                return
            logger.warning(
                "LLM reflection failed or timed out; deterministic fallback remains active agent_id=%s timeout_s=%.2f error=%s",
                getattr(agent, "agent_id", "unknown"),
                timeout_s,
                e,
            )
        finally:
            agent.llm_pending = False

    async def _request_goal(self, agent, world, prompt: str) -> None:
        # Legacy compatibility path kept for existing tests/callers.
        timeout_s = float(getattr(world, "llm_timeout_seconds", 3.0))
        try:
            raw_goal = await asyncio.wait_for(
                self.planner.propose_goal_async(prompt),
                timeout=timeout_s,
            )
            normalized = normalize_goal(raw_goal)
            if normalized is None:
                agent.goal = "survive"
                return
            agent.goal = normalized
        except Exception:
            agent.goal = "survive"
        finally:
            agent.llm_pending = False

    def _apply_reflection_guidance(self, agent, world) -> None:
        hint = getattr(agent, "reflection_hint", None)
        if not isinstance(hint, dict):
            return
        profile = ensure_agent_cognitive_profile(agent)
        tick = int(getattr(world, "tick", 0))
        hint_tick = int(hint.get("generated_tick", tick))
        if tick - hint_tick > 12:
            setattr(agent, "reflection_hint", None)
            return
        intention_type = str(hint.get("suggested_intention_type", ""))
        resource_type = hint.get("suggested_resource_type")
        target_kind = str(hint.get("suggested_target_kind", "none"))
        survival = evaluate_local_survival_pressure(world, agent)
        survival_pressure = float(survival.get("survival_pressure", 0.0))
        food_crisis = bool(survival.get("food_crisis", False))
        if food_crisis and intention_type in {"build_structure", "explore"}:
            if hasattr(world, "record_survival_reflection_suppressed"):
                world.record_survival_reflection_suppressed()
            intention_type = "deliver_resource" if str(getattr(agent, "role", "npc")) in {"builder", "hauler"} else "gather_food"
            target_kind = "building" if intention_type == "deliver_resource" else "resource"
            resource_type = "food"
        elif survival_pressure >= 0.60 and intention_type == "gather_resource" and str(resource_type or "") != "food":
            if hasattr(world, "record_survival_reflection_suppressed"):
                world.record_survival_reflection_suppressed()
            intention_type = "gather_food"
            target_kind = "resource"
            resource_type = "food"
        if (food_crisis or survival_pressure >= 0.60) and hasattr(world, "record_survival_biased_reflection_applied"):
            world.record_survival_biased_reflection_applied()
        target = None
        if target_kind == "resource":
            target = self.fallback._attention_resource_target(agent, resource_type or "food")
        elif target_kind == "building":
            target = self.fallback._attention_building_target(agent, world, {"storage", "house", "mine", "lumberyard"})
        elif target_kind == "social":
            target = self.fallback._attention_social_target(agent, same_village_only=True)

        current = getattr(agent, "current_intention", None)
        blocked = isinstance(current, dict) and int(current.get("failed_ticks", 0)) >= 2
        if current is None or blocked:
            agent.current_intention = self.fallback._new_intention(
                world,
                intention_type,
                target=target,
                resource_type=(str(resource_type) if isinstance(resource_type, str) and resource_type else None),
            )
            profile["last_reflection_outcome"] = "applied_guidance"
        else:
            profile["last_reflection_outcome"] = "guidance_skipped_active_intention"
        setattr(agent, "reflection_hint", None)

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

    def _make_prompt(self, agent, world, context: Optional[Dict[str, Any]] = None, reflection_reason: str = "") -> str:
        role = getattr(agent, "role", "npc")
        context = context if isinstance(context, dict) else build_agent_cognitive_context(world, agent)
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
                f"local_cognitive_context={context}\n"
                f"{village_summary}"
            )

        return (
            "You are local bounded cognition for one agent in a tile world.\n"
            "Use ONLY the provided local_cognitive_context. Do not assume hidden/global knowledge.\n"
            "Output JSON only (no prose, no markdown) with exactly these keys:\n"
            "suggested_intention_type, suggested_target_kind, suggested_resource_type, reasoning_tags.\n"
            "Allowed suggested_intention_type: gather_food, gather_resource, deliver_resource, build_structure, work_mine, work_lumberyard, explore.\n"
            "Allowed suggested_target_kind: resource, building, social, none.\n"
            "Allowed suggested_resource_type: food, wood, stone or empty string.\n"
            "reasoning_tags should be a short list from: survival, cooperation, work, exploration, logistics, risk_management.\n"
            "Survival-first rule: when survival pressure or food crisis is high, prioritize gather_food or food logistics over expansion/exploration.\n"
            "Example valid output: {\"suggested_intention_type\":\"gather_food\",\"suggested_target_kind\":\"resource\",\"suggested_resource_type\":\"food\",\"reasoning_tags\":[\"survival\"]}\n"
            f"reflection_reason={reflection_reason}\n"
            f"tick={world.tick}\n"
            f"agent_role={getattr(agent, 'role', 'npc')}\n"
            f"local_cognitive_context={context}\n"
        )
