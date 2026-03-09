from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
import random
import uuid

from config import (
    FOOD_EAT_GAIN,
    AGENT_START_HUNGER,
    REPRO_MIN_HUNGER,
    REPRO_PROB,
    REPRO_COST,
    MAX_AGENTS,
    HOUSE_WOOD_COST,
    HOUSE_STONE_COST,
)


@dataclass
class Agent:
    x: int
    y: int
    brain: Any
    is_player: bool = False
    player_id: Optional[str] = None
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    alive: bool = True
    hunger: float = float(AGENT_START_HUNGER)

    inventory: Dict[str, int] = field(
        default_factory=lambda: {"food": 0, "wood": 0, "stone": 0}
    )
    max_inventory: int = 5
    visual_radius_tiles: int = 8
    social_radius_tiles: int = 8

    memory: Dict[str, set] = field(
        default_factory=lambda: {
            "food": set(),
            "wood": set(),
            "stone": set(),
            "villages": set(),
            "farms": set(),
        }
    )

    repro_cooldown: int = 0

    goal: str = "survive"
    last_llm_tick: int = 0
    llm_pending: bool = False

    role: str = "npc"
    village_id: Optional[int] = None
    founder: bool = False

    task: str = "idle"
    task_target: Optional[Tuple[int, int]] = None
    home_pos: Optional[Tuple[int, int]] = None
    work_pos: Optional[Tuple[int, int]] = None
    delivery_target_building_id: Optional[str] = None
    delivery_resource_type: Optional[str] = None
    delivery_reserved_amount: int = 0
    transfer_source_storage_id: Optional[str] = None
    transfer_target_storage_id: Optional[str] = None
    transfer_resource_type: Optional[str] = None
    transfer_amount: int = 0
    last_pos: Optional[Tuple[int, int]] = None
    stuck_ticks: int = 0
    leader_traits: Optional[Dict[str, str]] = None
    current_intention: Optional[Dict[str, Any]] = None
    current_innovation_proposal: Optional[Dict[str, Any]] = None
    self_model: Dict[str, Any] = field(default_factory=dict)
    proto_traits: Dict[str, Any] = field(default_factory=dict)
    cognitive_profile: Dict[str, Any] = field(default_factory=dict)
    social_influence: float = 0.0
    last_social_influence_tick: int = -1
    social_memory: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {"known_agents": {}}
    )
    knowledge_state: Dict[str, List[Dict[str, Any]]] = field(
        default_factory=lambda: {
            "known_resource_spots": [],
            "known_useful_buildings": [],
            "known_routes": [],
            "known_practices": [],
            "known_inventions": [],
        }
    )
    episodic_memory: Dict[str, List[Dict[str, Any]]] = field(
        default_factory=lambda: {"recent_events": []}
    )
    subjective_state: Dict[str, Any] = field(default_factory=dict)
    short_term_memory: Dict[str, List[Dict[str, Any]]] = field(
        default_factory=lambda: {
            "recently_seen_resources": [],
            "recently_seen_agents": [],
            "recently_seen_buildings": [],
        }
    )

    def inventory_load(self) -> int:
        return int(self.inventory.get("food", 0)) + int(self.inventory.get("wood", 0)) + int(self.inventory.get("stone", 0))

    def inventory_space(self) -> int:
        return max(0, int(self.max_inventory) - self.inventory_load())

    def _near_storage(self, village: Optional[Dict]) -> bool:
        if not village:
            return False
        sp = village.get("storage_pos")
        if not sp:
            return False
        return abs(self.x - sp["x"]) <= 1 and abs(self.y - sp["y"]) <= 1

    def _deposit_inventory_to_storage(self, world: "World") -> bool:
        try:
            import systems.building_system as building_system
            return building_system.deposit_agent_inventory_to_storage(world, self)
        except Exception:
            return False

    def _withdraw_build_materials(self, world: "World", wood_need: int, stone_need: int) -> bool:
        try:
            import systems.building_system as building_system
            return building_system.withdraw_build_materials_from_storage(
                world,
                self,
                wood_need=wood_need,
                stone_need=stone_need,
            )
        except Exception:
            return False

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

                if pos in getattr(world, "farms", set()):
                    self.memory["farms"].add(pos)

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
        self.memory["food"] = {p for p in self.memory["food"] if p in world.food}
        self.memory["wood"] = {p for p in self.memory["wood"] if p in world.wood}
        self.memory["stone"] = {p for p in self.memory["stone"] if p in world.stone}
        self.memory["farms"] = {
            p for p in self.memory["farms"] if p in getattr(world, "farms", set())
        }

        valid_village_centers = set()

        for village in getattr(world, "villages", []):
            center = village.get("center")
            if center and "x" in center and "y" in center:
                valid_village_centers.add((center["x"], center["y"]))

        self.memory["villages"] = {
            p for p in self.memory["villages"] if p in valid_village_centers
        }

    def update_role_task(self, world: "World") -> None:
        village = world.get_village_by_id(self.village_id)

        if self.is_player:
            self.task = "player_controlled"
            return

        role = getattr(self, "role", "npc")

        if role == "leader":
            self.task = "manage_village"
            return

        # bootstrap: prima che esista un villaggio, gli NPC fondano i primi nuclei
        if village is None:
            if (
                self.inventory.get("wood", 0) >= HOUSE_WOOD_COST
                and self.inventory.get("stone", 0) >= HOUSE_STONE_COST
            ):
                self.task = "bootstrap_build_house"
            else:
                self.task = "bootstrap_gather"
            if getattr(self, "founder", False):
                self.task_target = self.task_target or (self.x, self.y)
            return

        priority = village.get("priority", "stabilize")
        needs = village.get("needs", {})

        if role == "farmer":
            self.task = "farm_cycle"
            return

        if role == "miner":
            self.task = "mine_cycle"
            return

        if role == "woodcutter":
            self.task = "lumber_cycle"
            return

        if role in {"builder", "hauler"} and hasattr(world, "has_proto_asset_work_for_agent"):
            try:
                known_inventions = (ensure_agent_knowledge_state(self).get("known_inventions", []) if hasattr(self, "knowledge_state") else [])
                has_invention_signal = any(
                    isinstance(e, dict)
                    and str(e.get("usefulness_status", "")) == "useful"
                    and float(e.get("confidence", 0.0)) >= 0.45
                    for e in (known_inventions if isinstance(known_inventions, list) else [])
                )
                current_proposal = getattr(self, "current_innovation_proposal", {})
                owns_current = (
                    isinstance(current_proposal, dict)
                    and str(current_proposal.get("inventor_agent_id", "")) == str(getattr(self, "agent_id", ""))
                )
                if bool(world.has_proto_asset_work_for_agent(self)) and (has_invention_signal or owns_current):
                    self.task = "prototype_attempt"
                    return
            except Exception:
                pass

        if role == "builder":
            if priority == "build_storage" or needs.get("need_storage"):
                self.task = "build_storage"
            elif priority == "build_housing" or needs.get("need_housing"):
                self.task = "build_house"
            elif priority == "improve_logistics" or needs.get("need_roads"):
                self.task = "build_road"
            else:
                self.task = "gather_materials"
            return

        if role == "hauler":
            if priority == "secure_food":
                self.task = "food_logistics"
            else:
                self.task = "village_logistics"
            return

        if role == "forager":
            self.task = "gather_food_wild"
            return

        self.task = "survive"

    def update_subjective_state(self, world: "World") -> None:
        self.subjective_state = build_agent_perception(world, self)
        if isinstance(self.subjective_state.get("local_signals"), dict):
            self.subjective_state["local_signals"]["survival"] = evaluate_local_survival_pressure(world, self)
        update_agent_social_memory(world, self, self.subjective_state)
        update_agent_knowledge_from_experience(world, self)
        update_agent_invention_knowledge_from_observation(world, self)
        diffuse_local_knowledge(world, self)
        diffuse_invention_knowledge(world, self)
        decay_agent_knowledge_state(world, self)
        update_agent_self_model(world, self)
        update_agent_identity(world, self)
        update_agent_cognitive_profile(world, self)
        self.social_influence = evaluate_agent_social_influence(world, self)
        self.last_social_influence_tick = int(getattr(world, "tick", 0))
        self.subjective_state["self_interpretation"] = interpret_local_signals_with_self_model(world, self)
        self.subjective_state["attention"] = evaluate_agent_salience(world, self)
        _update_short_term_memory(self)

    def run_brain(self, world: "World") -> Tuple[str, ...]:
        if self.brain is None:
            return ("wait",)

        action = self.brain.decide(self, world)

        if not action:
            return ("wait",)

        if isinstance(action, tuple):
            return action

        return ("wait",)

    def eat_if_needed(self, world: "World") -> bool:
        village = world.get_village_by_id(self.village_id)
        trigger = 50
        ate = False
        preserve_inventory_food = False

        if village is not None:
            storage = village.get("storage", {})
            pop = max(1, village.get("population", 1))
            food_stock = storage.get("food", 0)
            buffer_target = max(4, pop * 4)
            food_reserve = max(2, pop * 2)
            if food_stock > 0:
                # Village food should protect members earlier, reducing avoidable starvation.
                if food_stock >= pop:
                    trigger = 70
                else:
                    trigger = 62
            if (
                food_stock < buffer_target
                and self.inventory.get("food", 0) > 0
                and getattr(self, "role", "npc") in ("hauler", "farmer")
                and not self._near_storage(village)
            ):
                # Keep carried harvest for deposit when village stock buffer is low.
                preserve_inventory_food = True

        if self.hunger >= trigger:
            return ate

        if village is not None:
            storage = village.get("storage", {})
            pop = max(1, village.get("population", 1))
            food_reserve = max(2, pop * 2)
            storage_food = storage.get("food", 0)
            can_use_storage_food = storage_food > food_reserve or self.hunger <= 15
            if storage_food > 0 and can_use_storage_food:
                storage["food"] -= 1
                self.hunger += FOOD_EAT_GAIN
                if self.hunger > 100:
                    self.hunger = 100
                return True

        if self.inventory.get("food", 0) > 0 and (not preserve_inventory_food or self.hunger <= 15):
            self.inventory["food"] -= 1
            self.hunger += FOOD_EAT_GAIN
            if self.hunger > 100:
                self.hunger = 100
            ate = True

        return ate

    def try_reproduce(self, world: "World") -> None:
        if self.is_player:
            return

        # Hard gate: no uncontrolled growth before first real settlements.
        if getattr(self, "village_id", None) is None or not getattr(world, "villages", []):
            return

        if len(world.agents) >= int(MAX_AGENTS * 0.60):
            return

        if self.repro_cooldown > 0:
            self.repro_cooldown -= 1
            return

        village = world.get_village_by_id(self.village_id)
        storage_food = 0
        village_pop = 0
        if village is not None:
            storage_food = village.get("storage", {}).get("food", 0)
            village_pop = village.get("population", 0)
            houses = max(0, int(village.get("houses", 0)))
            population_cap = houses * 5
            if village_pop >= population_cap:
                return

        repro_min_hunger = REPRO_MIN_HUNGER
        repro_prob = REPRO_PROB
        if village is not None and storage_food >= max(4, village_pop // 3):
            repro_min_hunger = max(75, REPRO_MIN_HUNGER - 10)
            repro_prob = min(0.03, REPRO_PROB * 1.8)

        if self.hunger < repro_min_hunger:
            return

        if random.random() > repro_prob:
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
        baby.task = "idle"

        world.add_agent(baby)

        self.hunger -= REPRO_COST
        if self.hunger < 1:
            self.hunger = 1

        self.repro_cooldown = 80

    def update(self, world: "World") -> None:
        if not self.alive:
            return

        self.update_memory(world)
        self.cleanup_memory(world)
        self.update_subjective_state(world)
        self.update_role_task(world)

        # Eat before decay so stocked villages actually prevent avoidable deaths.
        ate_before_action = self.eat_if_needed(world)

        self.hunger -= 1
        if self.hunger <= 0:
            world.set_agent_dead(self, reason="hunger")
            return

        action = self.run_brain(world)
        moved = False

        if action and action[0] == "move":
            dx = int(action[1])
            dy = int(action[2])

            nx = self.x + dx
            ny = self.y + dy

            if world.is_walkable(nx, ny) and not world.is_occupied(nx, ny):
                self.x = nx
                self.y = ny
                moved = True

                # Roads reduce movement cost: crossing roads can grant a second short step.
                if (self.x, self.y) in getattr(world, "roads", set()):
                    nx2 = self.x + dx
                    ny2 = self.y + dy
                    if world.is_walkable(nx2, ny2) and not world.is_occupied(nx2, ny2):
                        self.x = nx2
                        self.y = ny2

                # le strade emergono solo da insediamenti veri, non dal caos iniziale
                if getattr(self, "village_id", None) is not None:
                    world.record_road_step(self.x, self.y)

        if self.last_pos is None:
            self.last_pos = (self.x, self.y)

        if moved:
            self.last_pos = (self.x, self.y)
            self.stuck_ticks = 0
        else:
            if self.last_pos == (self.x, self.y):
                self.stuck_ticks += 1
            else:
                self.last_pos = (self.x, self.y)
                self.stuck_ticks = 0

            if self.stuck_ticks >= 3:
                if self._break_stall(world):
                    self.stuck_ticks = 0
                    self.last_pos = (self.x, self.y)

        world.autopickup(self)
        world.gather_resource(self)

        # azioni guidate da ruolo/task
        if self.task == "farm_cycle":
            world.try_build_farm(self)
            world.work_farm(self)

        elif self.task == "mine_cycle":
            # movement/targeting is handled by brain; gather occurs via world.gather_resource.
            pass

        elif self.task == "lumber_cycle":
            # movement/targeting is handled by brain; gather occurs via world.gather_resource.
            pass

        elif self.task == "build_storage":
            self._withdraw_build_materials(world, wood_need=4, stone_need=2)
            built = world.try_build_storage(self)
            if not built:
                village = world.get_village_by_id(self.village_id)
                if village is not None:
                    storage = village.get("storage", {})
                    if storage.get("wood", 0) < 4 or storage.get("stone", 0) < 2:
                        self.task = "gather_materials"
                    else:
                        self.task = "build_storage"

        elif self.task == "build_house":
            self._withdraw_build_materials(world, wood_need=HOUSE_WOOD_COST, stone_need=HOUSE_STONE_COST)
            world.try_build_house(self)

        elif self.task == "build_road":
            # per ora la strada emerge dal movimento
            pass

        elif self.task == "gather_materials":
            # builder in attesa di materiali
            pass

        elif self.task == "food_logistics":
            try:
                import systems.building_system as building_system
                delivered = building_system.run_hauler_construction_delivery(world, self)
                redistributed = False if delivered else building_system.run_hauler_internal_redistribution(world, self)
                transfer_active = bool(getattr(building_system, "has_active_internal_transfer", lambda *_: False)(self))
            except Exception:
                delivered = False
                redistributed = False
                transfer_active = False
            if not delivered and not redistributed and not transfer_active and not self._deposit_inventory_to_storage(world):
                world.haul_harvest(self)
                world.work_farm(self)

        elif self.task == "village_logistics":
            try:
                import systems.building_system as building_system
                delivered = building_system.run_hauler_construction_delivery(world, self)
                redistributed = False if delivered else building_system.run_hauler_internal_redistribution(world, self)
                transfer_active = bool(getattr(building_system, "has_active_internal_transfer", lambda *_: False)(self))
            except Exception:
                delivered = False
                redistributed = False
                transfer_active = False
            if not delivered and not redistributed and not transfer_active and not self._deposit_inventory_to_storage(world):
                world.haul_harvest(self)

        elif self.task == "gather_food_wild":
            # niente build casuali
            pass

        elif self.task == "bootstrap_build_house":
            built = world.try_build_house(self)
            if not built:
                # Keep founding behavior coherent: if still funded, keep trying near settlements.
                if (
                    self.inventory.get("wood", 0) >= HOUSE_WOOD_COST
                    and self.inventory.get("stone", 0) >= HOUSE_STONE_COST
                ):
                    if world.structures:
                        self.task_target = min(
                            world.structures,
                            key=lambda p: abs(p[0] - self.x) + abs(p[1] - self.y),
                        )
                    self.task = "bootstrap_build_house"
                else:
                    self.task = "bootstrap_gather"

        elif self.task == "bootstrap_gather":
            # niente build casuali, raccoglie e si muove col brain
            pass

        elif self.task == "prototype_attempt":
            if hasattr(world, "get_proto_material_needs_for_agent"):
                needs = world.get_proto_material_needs_for_agent(self)
                if isinstance(needs, dict):
                    self._withdraw_build_materials(
                        world,
                        wood_need=max(0, int(needs.get("wood", 0))),
                        stone_need=max(0, int(needs.get("stone", 0))),
                    )
            if hasattr(world, "run_proto_asset_adoption_attempt"):
                world.run_proto_asset_adoption_attempt(self)

        elif self.task == "survive":
            pass

        if not ate_before_action:
            self.eat_if_needed(world)
        self.try_reproduce(world)

    def _break_stall(self, world: "World") -> bool:
        target = self.task_target
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        random.shuffle(dirs)
        options = []

        for dx, dy in dirs:
            nx = self.x + dx
            ny = self.y + dy
            if not world.is_walkable(nx, ny) or world.is_occupied(nx, ny):
                continue

            if target is not None:
                d = abs(target[0] - nx) + abs(target[1] - ny)
                options.append((d, dx, dy))
            else:
                options.append((0, dx, dy))

        if not options:
            return False

        options.sort(key=lambda t: t[0])
        _, dx, dy = options[0]
        self.x += dx
        self.y += dy

        if getattr(self, "village_id", None) is not None:
            world.record_road_step(self.x, self.y)

        return True


def _coord_key(coord: Tuple[int, int]) -> Tuple[int, int]:
    return (coord[1], coord[0])


def _manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _clampf(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


KNOWLEDGE_MAX_ENTRIES_PER_CATEGORY = 12
KNOWLEDGE_DECAY_PER_TICK = 0.0009
KNOWLEDGE_MIN_CONFIDENCE = 0.15
KNOWLEDGE_MAX_INVENTIONS = 10
INVENTION_SOCIAL_MIN_CONFIDENCE = 0.35
COGNITIVE_TIER_MIN = 1
COGNITIVE_TIER_MAX = 4


def _default_self_model() -> Dict[str, float]:
    return {
        "survival_weight": 0.65,
        "social_weight": 0.35,
        "work_weight": 0.50,
        "exploration_weight": 0.30,
        "security_weight": 0.40,
        "stress_level": 0.20,
        "recent_success_bias": 0.50,
        "recent_failure_bias": 0.20,
    }


def _default_cognitive_profile() -> Dict[str, Any]:
    return {
        "llm_enabled": True,
        "cognitive_tier": 1,
        "reflection_budget": 0.55,
        "reflection_cooldown_ticks": 80,
        "last_reflection_tick": -1000,
        "reflection_priority": 0.45,
        "max_context_items": 8,
        "reflection_count": 0,
        "last_reflection_reason": "",
        "last_reflection_outcome": "",
        "reflection_success_count": 0,
        "reflection_fallback_count": 0,
        "reflection_block_reason": "",
        "effective_context_size": 0,
    }


def ensure_agent_cognitive_profile(agent: Agent) -> Dict[str, Any]:
    profile = getattr(agent, "cognitive_profile", None)
    if not isinstance(profile, dict) or not profile:
        profile = _default_cognitive_profile()
        role = str(getattr(agent, "role", "npc"))
        # Universal baseline: no default leader privilege.
        if role in {"builder", "hauler", "miner", "woodcutter"}:
            profile["reflection_priority"] = round(_clampf(float(profile["reflection_priority"]) + 0.02), 3)
        profile["reflection_budget"] = round(_clampf(float(profile["reflection_budget"])), 3)
        profile["reflection_priority"] = round(_clampf(float(profile["reflection_priority"])), 3)
        profile["max_context_items"] = int(max(4, min(18, int(profile["max_context_items"]))))
        agent.cognitive_profile = profile
    return profile


def _default_knowledge_state() -> Dict[str, List[Dict[str, Any]]]:
    return {
        "known_resource_spots": [],
        "known_useful_buildings": [],
        "known_routes": [],
        "known_practices": [],
        "known_inventions": [],
    }


def ensure_agent_knowledge_state(agent: Agent) -> Dict[str, List[Dict[str, Any]]]:
    state = getattr(agent, "knowledge_state", None)
    if not isinstance(state, dict):
        state = _default_knowledge_state()
        agent.knowledge_state = state
    for key in ("known_resource_spots", "known_useful_buildings", "known_routes", "known_practices", "known_inventions"):
        if not isinstance(state.get(key), list):
            state[key] = []
    return state


def _knowledge_match_key(entry: Dict[str, Any]) -> Tuple[str, str, int, int]:
    loc = entry.get("location", {}) if isinstance(entry.get("location"), dict) else {}
    return (
        str(entry.get("type", "")),
        str(entry.get("subject", "")),
        int(loc.get("x", 0)),
        int(loc.get("y", 0)),
    )


def _upsert_knowledge_entry(
    entries: List[Dict[str, Any]],
    new_entry: Dict[str, Any],
    *,
    confidence_boost: float,
    tick: int,
    max_entries: int = KNOWLEDGE_MAX_ENTRIES_PER_CATEGORY,
) -> None:
    new_key = _knowledge_match_key(new_entry)
    for existing in entries:
        if not isinstance(existing, dict):
            continue
        if _knowledge_match_key(existing) != new_key:
            continue
        existing_conf = float(existing.get("confidence", 0.0))
        existing["confidence"] = round(_clampf(existing_conf + confidence_boost), 3)
        existing["learned_tick"] = int(tick)
        existing["salience"] = round(
            _clampf(max(float(existing.get("salience", 0.0)), float(new_entry.get("salience", 0.0)))),
            3,
        )
        source = str(existing.get("source", "social"))
        # Direct confirmation dominates social origin.
        if str(new_entry.get("source", "social")) == "direct":
            existing["source"] = "direct"
        else:
            existing["source"] = source
        return

    payload = {
        "type": str(new_entry.get("type", "")),
        "subject": str(new_entry.get("subject", "")),
        "location": {
            "x": int((new_entry.get("location", {}) if isinstance(new_entry.get("location"), dict) else {}).get("x", 0)),
            "y": int((new_entry.get("location", {}) if isinstance(new_entry.get("location"), dict) else {}).get("y", 0)),
        },
        "learned_tick": int(tick),
        "confidence": round(_clampf(float(new_entry.get("confidence", 0.5))), 3),
        "source": str(new_entry.get("source", "direct")),
        "salience": round(_clampf(float(new_entry.get("salience", 0.5))), 3),
    }
    entries.append(payload)
    if len(entries) > int(max_entries):
        entries.sort(
            key=lambda e: (
                float(e.get("confidence", 0.0)),
                int(e.get("learned_tick", 0)),
                float(e.get("salience", 0.0)),
                str(e.get("subject", "")),
            )
        )
        del entries[: len(entries) - int(max_entries)]


def _known_invention_key(entry: Dict[str, Any]) -> Tuple[str, str]:
    return (
        str(entry.get("proposal_id", "")),
        str(entry.get("prototype_id", "")),
    )


def _upsert_known_invention_entry(
    entries: List[Dict[str, Any]],
    new_entry: Dict[str, Any],
    *,
    confidence_boost: float,
    tick: int,
    max_entries: int = KNOWLEDGE_MAX_INVENTIONS,
) -> None:
    entry_key = _known_invention_key(new_entry)
    for existing in entries:
        if not isinstance(existing, dict):
            continue
        if _known_invention_key(existing) != entry_key:
            continue
        existing["learned_tick"] = int(tick)
        current_conf = float(existing.get("confidence", 0.0))
        incoming_conf = float(new_entry.get("confidence", 0.5))
        existing["confidence"] = round(_clampf(max(current_conf, incoming_conf) + confidence_boost), 3)
        existing["salience"] = round(
            _clampf(max(float(existing.get("salience", 0.0)), float(new_entry.get("salience", 0.0)))),
            3,
        )
        if str(new_entry.get("source", "social")) == "direct":
            existing["source"] = "direct"
        if str(new_entry.get("usefulness_status", "unknown")) in {"useful", "neutral", "ineffective"}:
            existing["usefulness_status"] = str(new_entry.get("usefulness_status", "unknown"))
        return

    loc = new_entry.get("location", {}) if isinstance(new_entry.get("location"), dict) else {}
    payload = {
        "proposal_id": str(new_entry.get("proposal_id", "")),
        "prototype_id": str(new_entry.get("prototype_id", "")),
        "inventor_agent_id": str(new_entry.get("inventor_agent_id", "")),
        "category": str(new_entry.get("category", "")),
        "intended_effects": [str(e) for e in list(new_entry.get("intended_effects", []))[:3] if str(e)],
        "location": {"x": int(loc.get("x", 0)), "y": int(loc.get("y", 0))},
        "learned_tick": int(tick),
        "confidence": round(_clampf(float(new_entry.get("confidence", 0.5))), 3),
        "source": str(new_entry.get("source", "direct")),
        "usefulness_status": str(new_entry.get("usefulness_status", "unknown")),
        "salience": round(_clampf(float(new_entry.get("salience", 0.5))), 3),
    }
    entries.append(payload)
    if len(entries) > int(max_entries):
        entries.sort(
            key=lambda e: (
                float(e.get("confidence", 0.0)),
                int(e.get("learned_tick", 0)),
                float(e.get("salience", 0.0)),
                str(e.get("proposal_id", "")),
            )
        )
        del entries[: len(entries) - int(max_entries)]


def update_agent_knowledge_from_experience(world: "World", agent: Agent) -> None:
    state = ensure_agent_knowledge_state(agent)
    tick = int(getattr(world, "tick", 0))
    recent_events = get_recent_memory_events(agent, limit=18)
    resource_entries = state["known_resource_spots"]
    building_entries = state["known_useful_buildings"]
    practice_entries = state["known_practices"]

    for ev in recent_events:
        if not isinstance(ev, dict):
            continue
        etype = str(ev.get("type", ""))
        outcome = str(ev.get("outcome", ""))
        loc = ev.get("location", {})
        if not isinstance(loc, dict):
            continue
        x = int(loc.get("x", agent.x))
        y = int(loc.get("y", agent.y))
        sal = _clampf(float(ev.get("salience", 0.5)))
        if outcome == "success" and etype in {"found_resource", "hunger_relief"}:
            res = str(ev.get("resource_type", "food" if etype == "hunger_relief" else ""))
            if res in {"food", "wood", "stone"}:
                _upsert_knowledge_entry(
                    resource_entries,
                    {
                        "type": "resource_spot",
                        "subject": res,
                        "location": {"x": x, "y": y},
                        "confidence": 0.72,
                        "source": "direct",
                        "salience": sal,
                    },
                    confidence_boost=0.10,
                    tick=tick,
                )

        if outcome == "success" and etype in {"useful_building", "construction_progress", "delivered_material"}:
            btype = str(ev.get("building_type", "storage" if etype == "delivered_material" else ""))
            subject = btype if btype else "site"
            _upsert_knowledge_entry(
                building_entries,
                {
                    "type": "useful_building",
                    "subject": subject,
                    "location": {"x": x, "y": y},
                    "confidence": 0.68,
                    "source": "direct",
                    "salience": sal,
                },
                confidence_boost=0.08,
                tick=tick,
            )
            practice_subject = "deliver_to_storage" if etype == "delivered_material" else "construction_cycle"
            _upsert_knowledge_entry(
                practice_entries,
                {
                    "type": "practice",
                    "subject": practice_subject,
                    "location": {"x": x, "y": y},
                    "confidence": 0.66,
                    "source": "direct",
                    "salience": sal,
                },
                confidence_boost=0.05,
                tick=tick,
            )

        if outcome == "failure" and etype == "failed_resource_search":
            res = str(ev.get("resource_type", ""))
            for entry in resource_entries:
                if not isinstance(entry, dict):
                    continue
                if str(entry.get("subject", "")) != res:
                    continue
                lloc = entry.get("location", {})
                if not isinstance(lloc, dict):
                    continue
                if _manhattan((x, y), (int(lloc.get("x", 0)), int(lloc.get("y", 0)))) <= 2:
                    entry["confidence"] = round(_clampf(float(entry.get("confidence", 0.0)) - 0.12), 3)


def update_agent_invention_knowledge_from_observation(world: "World", agent: Agent) -> None:
    state = ensure_agent_knowledge_state(agent)
    inventions = state.get("known_inventions", [])
    if not isinstance(inventions, list):
        inventions = []
        state["known_inventions"] = inventions
    tick = int(getattr(world, "tick", 0))
    ax, ay = int(getattr(agent, "x", 0)), int(getattr(agent, "y", 0))

    prototypes = getattr(world, "proto_asset_prototypes", []) or []
    for proto in prototypes:
        if not isinstance(proto, dict):
            continue
        if str(proto.get("status", "")) != "prototype_built":
            continue
        loc = proto.get("location", {})
        if not isinstance(loc, dict):
            continue
        px = int(loc.get("x", 0))
        py = int(loc.get("y", 0))
        if _manhattan((ax, ay), (px, py)) > 4:
            continue
        if str(proto.get("usefulness_status", "")) == "ineffective":
            for entry in inventions:
                if not isinstance(entry, dict):
                    continue
                if str(entry.get("proposal_id", "")) != str(proto.get("proposal_id", "")):
                    continue
                entry["usefulness_status"] = "ineffective"
                entry["confidence"] = round(
                    _clampf(float(entry.get("confidence", 0.0)) - 0.10),
                    3,
                )
                entry["learned_tick"] = int(tick)
            continue
        if str(proto.get("usefulness_status", "")) != "useful":
            continue
        _upsert_known_invention_entry(
            inventions,
            {
                "proposal_id": str(proto.get("proposal_id", "")),
                "prototype_id": str(proto.get("instance_id", "")),
                "inventor_agent_id": str(proto.get("inventor_agent_id", "")),
                "category": str(proto.get("category", "")),
                "intended_effects": [str(proto.get("effect", ""))] if str(proto.get("effect", "")) else [],
                "location": {"x": px, "y": py},
                "confidence": 0.78,
                "source": "direct",
                "usefulness_status": "useful",
                "salience": 0.72,
            },
            confidence_boost=0.08,
            tick=tick,
            max_entries=KNOWLEDGE_MAX_INVENTIONS,
        )

    recent_useful_seen = get_recent_memory_events(agent, event_type="useful_prototype_seen", limit=8)
    by_instance = {
        str(proto.get("instance_id", "")): proto
        for proto in prototypes
        if isinstance(proto, dict) and str(proto.get("status", "")) == "prototype_built"
    }
    for ev in recent_useful_seen:
        if not isinstance(ev, dict):
            continue
        target_id = str(ev.get("target_id", ""))
        proto = by_instance.get(target_id)
        if not isinstance(proto, dict) or str(proto.get("usefulness_status", "")) != "useful":
            continue
        loc = ev.get("location", {})
        if not isinstance(loc, dict):
            loc = proto.get("location", {})
        if not isinstance(loc, dict):
            continue
        _upsert_known_invention_entry(
            inventions,
            {
                "proposal_id": str(proto.get("proposal_id", "")),
                "prototype_id": str(proto.get("instance_id", "")),
                "inventor_agent_id": str(proto.get("inventor_agent_id", "")),
                "category": str(proto.get("category", "")),
                "intended_effects": [str(proto.get("effect", ""))] if str(proto.get("effect", "")) else [],
                "location": {"x": int(loc.get("x", ax)), "y": int(loc.get("y", ay))},
                "confidence": 0.70,
                "source": "direct",
                "usefulness_status": "useful",
                "salience": 0.65,
            },
            confidence_boost=0.06,
            tick=tick,
            max_entries=KNOWLEDGE_MAX_INVENTIONS,
        )


def diffuse_invention_knowledge(world: "World", agent: Agent) -> None:
    state = ensure_agent_knowledge_state(agent)
    local_entries = state.get("known_inventions", [])
    if not isinstance(local_entries, list):
        local_entries = []
        state["known_inventions"] = local_entries
    subjective = getattr(agent, "subjective_state", {})
    nearby_agents = subjective.get("nearby_agents", []) if isinstance(subjective, dict) else []
    if not isinstance(nearby_agents, list) or not nearby_agents:
        return
    by_id = {str(getattr(a, "agent_id", "")): a for a in getattr(world, "agents", []) if getattr(a, "alive", False)}
    known_agents = (getattr(agent, "social_memory", {}) or {}).get("known_agents", {})
    tick = int(getattr(world, "tick", 0))

    for near in sorted(
        [n for n in nearby_agents if isinstance(n, dict)],
        key=lambda n: (int(n.get("distance", 999)), str(n.get("agent_id", ""))),
    ):
        aid = str(near.get("agent_id", ""))
        donor = by_id.get(aid)
        if donor is None:
            continue
        donor_state = ensure_agent_knowledge_state(donor)
        donor_entries = donor_state.get("known_inventions", [])
        if not isinstance(donor_entries, list) or not donor_entries:
            continue

        familiarity = 0.0
        if isinstance(known_agents, dict):
            rec = known_agents.get(aid, {})
            if isinstance(rec, dict):
                familiarity = min(1.0, float(rec.get("times_seen", 0)) / 8.0)
        same_village = bool(near.get("same_village", False))
        donor_infl = _clampf(float(getattr(donor, "social_influence", 0.0)))
        trust = 0.24 + (0.24 if same_village else 0.0) + familiarity * 0.30 + donor_infl * 0.22
        if trust < 0.54:
            continue
        candidates = [
            e for e in donor_entries
            if isinstance(e, dict)
            and str(e.get("usefulness_status", "")) == "useful"
            and float(e.get("confidence", 0.0)) >= 0.55
        ]
        if not candidates:
            continue
        candidates.sort(
            key=lambda e: (
                -float(e.get("confidence", 0.0)),
                -float(e.get("salience", 0.0)),
                -int(e.get("learned_tick", 0)),
                str(e.get("proposal_id", "")),
            )
        )
        chosen = candidates[0]
        base_conf = _clampf(float(chosen.get("confidence", 0.6)) * 0.72)
        _upsert_known_invention_entry(
            local_entries,
            {
                "proposal_id": str(chosen.get("proposal_id", "")),
                "prototype_id": str(chosen.get("prototype_id", "")),
                "inventor_agent_id": str(chosen.get("inventor_agent_id", "")),
                "category": str(chosen.get("category", "")),
                "intended_effects": list(chosen.get("intended_effects", [])),
                "location": dict(chosen.get("location", {})) if isinstance(chosen.get("location"), dict) else {"x": int(agent.x), "y": int(agent.y)},
                "confidence": min(base_conf, float(chosen.get("confidence", 0.6)) - 0.05),
                "source": "social",
                "usefulness_status": "useful",
                "salience": _clampf(float(chosen.get("salience", 0.5)) * 0.88),
            },
            confidence_boost=0.03,
            tick=tick,
            max_entries=KNOWLEDGE_MAX_INVENTIONS,
        )


def diffuse_local_knowledge(world: "World", agent: Agent) -> None:
    state = ensure_agent_knowledge_state(agent)
    subjective = getattr(agent, "subjective_state", {})
    nearby_agents = subjective.get("nearby_agents", []) if isinstance(subjective, dict) else []
    if not isinstance(nearby_agents, list) or not nearby_agents:
        return

    by_id = {str(getattr(a, "agent_id", "")): a for a in getattr(world, "agents", []) if getattr(a, "alive", False)}
    known_agents = (getattr(agent, "social_memory", {}) or {}).get("known_agents", {})
    tick = int(getattr(world, "tick", 0))

    for near in sorted(
        [n for n in nearby_agents if isinstance(n, dict)],
        key=lambda n: (int(n.get("distance", 999)), str(n.get("agent_id", ""))),
    ):
        aid = str(near.get("agent_id", ""))
        donor = by_id.get(aid)
        if donor is None:
            continue
        donor_state = ensure_agent_knowledge_state(donor)

        familiarity = 0.0
        if isinstance(known_agents, dict):
            rec = known_agents.get(aid, {})
            if isinstance(rec, dict):
                familiarity = min(1.0, float(rec.get("times_seen", 0)) / 8.0)
        same_village = bool(near.get("same_village", False))
        donor_infl = _clampf(float(getattr(donor, "social_influence", 0.0)))
        trust = 0.25 + (0.25 if same_village else 0.0) + familiarity * 0.3 + donor_infl * 0.2
        if trust < 0.52:
            continue

        for category in ("known_resource_spots", "known_useful_buildings", "known_practices"):
            donor_entries = donor_state.get(category, [])
            if not isinstance(donor_entries, list) or not donor_entries:
                continue
            candidates = [
                e for e in donor_entries
                if isinstance(e, dict) and float(e.get("confidence", 0.0)) >= 0.55
            ]
            if not candidates:
                continue
            candidates.sort(
                key=lambda e: (
                    -float(e.get("confidence", 0.0)),
                    -float(e.get("salience", 0.0)),
                    int(e.get("learned_tick", 0)),
                    str(e.get("subject", "")),
                )
            )
            chosen = candidates[0]
            _upsert_knowledge_entry(
                state[category],
                {
                    "type": str(chosen.get("type", "")),
                    "subject": str(chosen.get("subject", "")),
                    "location": dict(chosen.get("location", {})) if isinstance(chosen.get("location"), dict) else {"x": int(agent.x), "y": int(agent.y)},
                    "confidence": _clampf(float(chosen.get("confidence", 0.6)) * 0.82),
                    "source": "social",
                    "salience": _clampf(float(chosen.get("salience", 0.5)) * 0.9),
                },
                confidence_boost=0.03,
                tick=tick,
            )


def decay_agent_knowledge_state(world: "World", agent: Agent) -> None:
    state = ensure_agent_knowledge_state(agent)
    tick = int(getattr(world, "tick", 0))
    for category in ("known_resource_spots", "known_useful_buildings", "known_routes", "known_practices", "known_inventions"):
        entries = state.get(category, [])
        if not isinstance(entries, list):
            continue
        kept: List[Dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            learned_tick = int(entry.get("learned_tick", tick))
            age = max(0, tick - learned_tick)
            decay_rate = KNOWLEDGE_DECAY_PER_TICK
            if category == "known_inventions":
                decay_rate = KNOWLEDGE_DECAY_PER_TICK * (1.25 if str(entry.get("source", "social")) == "social" else 0.9)
                if str(entry.get("usefulness_status", "")) == "ineffective":
                    decay_rate *= 1.7
            decayed = _clampf(float(entry.get("confidence", 0.0)) - age * decay_rate)
            entry["confidence"] = round(decayed, 3)
            min_conf = KNOWLEDGE_MIN_CONFIDENCE if category != "known_inventions" else min(KNOWLEDGE_MIN_CONFIDENCE, INVENTION_SOCIAL_MIN_CONFIDENCE)
            if decayed >= min_conf:
                kept.append(entry)
        kept.sort(
            key=lambda e: (
                -float(e.get("confidence", 0.0)),
                -float(e.get("salience", 0.0)),
                -int(e.get("learned_tick", 0)),
                str(e.get("subject", e.get("proposal_id", ""))),
            )
        )
        limit = KNOWLEDGE_MAX_ENTRIES_PER_CATEGORY if category != "known_inventions" else KNOWLEDGE_MAX_INVENTIONS
        state[category] = kept[:limit]


def get_known_resource_spot(
    agent: Agent,
    resource_type: str,
    *,
    min_confidence: float = 0.35,
) -> Optional[Tuple[int, int]]:
    state = ensure_agent_knowledge_state(agent)
    entries = state.get("known_resource_spots", [])
    if not isinstance(entries, list):
        return None
    candidates = [
        e for e in entries
        if isinstance(e, dict)
        and str(e.get("subject", "")) == str(resource_type)
        and float(e.get("confidence", 0.0)) >= float(min_confidence)
        and isinstance(e.get("location"), dict)
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda e: (
            -float(e.get("confidence", 0.0)),
            -float(e.get("salience", 0.0)),
            -int(e.get("learned_tick", 0)),
            int((e.get("location") or {}).get("y", 0)),
            int((e.get("location") or {}).get("x", 0)),
        )
    )
    loc = candidates[0].get("location", {})
    return (int(loc.get("x", 0)), int(loc.get("y", 0)))


def get_known_useful_building_target(
    agent: Agent,
    allowed_types: Set[str],
    *,
    min_confidence: float = 0.35,
) -> Optional[Tuple[int, int]]:
    state = ensure_agent_knowledge_state(agent)
    entries = state.get("known_useful_buildings", [])
    if not isinstance(entries, list):
        return None
    allowed = {str(t) for t in allowed_types}
    candidates = [
        e for e in entries
        if isinstance(e, dict)
        and str(e.get("subject", "")) in allowed
        and float(e.get("confidence", 0.0)) >= float(min_confidence)
        and isinstance(e.get("location"), dict)
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda e: (
            -float(e.get("confidence", 0.0)),
            -float(e.get("salience", 0.0)),
            -int(e.get("learned_tick", 0)),
            str(e.get("subject", "")),
        )
    )
    loc = candidates[0].get("location", {})
    return (int(loc.get("x", 0)), int(loc.get("y", 0)))


IDENTITY_UPDATE_INTERVAL_TICKS = 60


def _default_proto_traits() -> Dict[str, float]:
    return {
        "cooperation": 0.50,
        "diligence": 0.50,
        "caution": 0.50,
        "curiosity": 0.50,
        "resilience": 0.50,
        "identity_stability": 0.92,
    }


def ensure_agent_proto_traits(agent: Agent) -> Dict[str, Any]:
    traits = getattr(agent, "proto_traits", None)
    if not isinstance(traits, dict) or not traits:
        traits = _default_proto_traits()
        role = str(getattr(agent, "role", "npc"))
        if role == "builder":
            traits["diligence"] += 0.08
        elif role == "hauler":
            traits["cooperation"] += 0.08
        elif role == "miner":
            traits["resilience"] += 0.06
            traits["diligence"] += 0.04
        elif role == "woodcutter":
            traits["resilience"] += 0.04
            traits["curiosity"] += 0.03
        elif role == "leader":
            traits["cooperation"] += 0.10
            traits["caution"] += 0.04

        for key in ("cooperation", "diligence", "caution", "curiosity", "resilience", "identity_stability"):
            traits[key] = round(_clampf(float(traits.get(key, 0.5))), 3)
        traits["last_identity_update_tick"] = -1
        agent.proto_traits = traits
    return traits


def update_agent_identity(world: "World", agent: Agent) -> Dict[str, Any]:
    traits = ensure_agent_proto_traits(agent)
    tick = int(getattr(world, "tick", 0))
    last_tick = int(traits.get("last_identity_update_tick", -1))
    if last_tick >= 0 and tick - last_tick < int(IDENTITY_UPDATE_INTERVAL_TICKS):
        return traits

    recent_events = get_recent_memory_events(agent, limit=20)
    success_count = sum(1 for e in recent_events if str(e.get("outcome", "")) == "success")
    failure_count = sum(1 for e in recent_events if str(e.get("outcome", "")) == "failure")
    work_success = sum(
        1
        for e in recent_events
        if str(e.get("type", "")) in {"construction_progress", "delivered_material", "found_resource"}
        and str(e.get("outcome", "")) == "success"
    )
    explore_success = sum(
        1
        for e in recent_events
        if str(e.get("type", "")) in {"found_resource", "hunger_relief"}
        and str(e.get("outcome", "")) == "success"
    )

    social_memory = getattr(agent, "social_memory", {})
    known_agents = social_memory.get("known_agents", {}) if isinstance(social_memory, dict) else {}
    cooperative_contacts = sum(
        1
        for record in (known_agents.values() if isinstance(known_agents, dict) else [])
        if isinstance(record, dict) and str(record.get("recent_interaction", "")) == "co_present_success"
    )

    self_model = ensure_agent_self_model(agent)
    stress_level = float(self_model.get("stress_level", 0.2))

    identity_stability = _clampf(float(traits.get("identity_stability", 0.92)), 0.75, 0.99)
    adaptation_rate = 1.0 - identity_stability

    influence = {
        "cooperation": _clampf(
            float(traits.get("cooperation", 0.5))
            + 0.04 * min(cooperative_contacts, 3)
            + 0.01 * max(0, success_count - failure_count)
        ),
        "diligence": _clampf(
            float(traits.get("diligence", 0.5))
            + 0.03 * min(work_success, 4)
            - 0.01 * max(0, failure_count - success_count)
        ),
        "caution": _clampf(
            float(traits.get("caution", 0.5))
            + 0.03 * min(failure_count, 4)
            - 0.01 * min(success_count, 3)
        ),
        "curiosity": _clampf(
            float(traits.get("curiosity", 0.5))
            + 0.03 * min(explore_success, 4)
            - 0.01 * min(failure_count, 3)
        ),
        "resilience": _clampf(
            float(traits.get("resilience", 0.5))
            + 0.02 * min(failure_count, 4)
            + (0.02 if stress_level > 0.55 else 0.0)
            - (0.01 if stress_level < 0.25 else 0.0)
        ),
    }

    for key in ("cooperation", "diligence", "caution", "curiosity", "resilience"):
        current = _clampf(float(traits.get(key, 0.5)))
        target = _clampf(float(influence.get(key, current)))
        traits[key] = round(_clampf(current + (target - current) * adaptation_rate), 3)

    traits["identity_stability"] = round(identity_stability, 3)
    traits["last_identity_update_tick"] = tick
    return traits


def update_agent_cognitive_profile(world: "World", agent: Agent) -> Dict[str, Any]:
    profile = ensure_agent_cognitive_profile(agent)
    tick = int(getattr(world, "tick", 0))
    proto = ensure_agent_proto_traits(agent)
    recent_events = get_recent_memory_events(agent, limit=16)
    success_count = sum(1 for e in recent_events if str(e.get("outcome", "")) == "success")
    failure_count = sum(1 for e in recent_events if str(e.get("outcome", "")) == "failure")
    useful_work = sum(
        1
        for e in recent_events
        if str(e.get("type", "")) in {"construction_progress", "delivered_material", "found_resource"}
        and str(e.get("outcome", "")) == "success"
    )
    knowledge_state = ensure_agent_knowledge_state(agent)
    knowledge_richness = sum(
        len(knowledge_state.get(k, []))
        for k in ("known_resource_spots", "known_useful_buildings", "known_practices", "known_inventions")
        if isinstance(knowledge_state.get(k), list)
    )
    social_infl = _clampf(float(getattr(agent, "social_influence", 0.0)))

    maturity_signal = (
        min(1.0, useful_work / 6.0) * 0.35
        + min(1.0, success_count / 8.0) * 0.20
        + min(1.0, knowledge_richness / 12.0) * 0.25
        + social_infl * 0.15
        + float(proto.get("diligence", 0.5)) * 0.05
    )
    if failure_count > success_count:
        maturity_signal = _clampf(maturity_signal - 0.08)

    new_tier = COGNITIVE_TIER_MIN
    if maturity_signal >= 0.45:
        new_tier = 2
    if maturity_signal >= 0.65:
        new_tier = 3
    if maturity_signal >= 0.82:
        new_tier = 4
    profile["cognitive_tier"] = int(max(COGNITIVE_TIER_MIN, min(COGNITIVE_TIER_MAX, new_tier)))

    priority = 0.35 + maturity_signal * 0.45 + social_infl * 0.15
    profile["reflection_priority"] = round(_clampf(priority), 3)
    budget = 0.45 + maturity_signal * 0.35 - min(0.15, max(0.0, failure_count - success_count) * 0.03)
    profile["reflection_budget"] = round(_clampf(budget), 3)
    profile["reflection_cooldown_ticks"] = int(max(20, 90 - profile["cognitive_tier"] * 15))
    profile["max_context_items"] = int(max(6, min(18, 6 + profile["cognitive_tier"] * 3)))
    profile["llm_enabled"] = bool(profile.get("llm_enabled", True))
    profile.setdefault("last_reflection_tick", -1000)
    profile.setdefault("reflection_count", 0)
    profile.setdefault("last_reflection_reason", "")
    profile.setdefault("last_reflection_outcome", "")
    profile.setdefault("reflection_success_count", 0)
    profile.setdefault("reflection_fallback_count", 0)
    profile.setdefault("reflection_block_reason", "")
    profile.setdefault("effective_context_size", 0)
    profile["last_profile_update_tick"] = tick
    return profile


def _attention_complexity_score(attention: Dict[str, Any]) -> float:
    if not isinstance(attention, dict):
        return 0.0
    score = 0.0
    score += min(1.0, len(attention.get("top_resource_targets", [])) / 3.0) * 0.35
    score += min(1.0, len(attention.get("top_building_targets", [])) / 3.0) * 0.35
    score += min(1.0, len(attention.get("top_social_targets", [])) / 3.0) * 0.30
    return _clampf(score)


def should_agent_reflect(world: "World", agent: Agent) -> bool:
    profile = ensure_agent_cognitive_profile(agent)
    if not bool(getattr(world, "llm_enabled", True)):
        profile["reflection_block_reason"] = "world_llm_disabled"
        return False
    if not bool(profile.get("llm_enabled", True)):
        profile["reflection_block_reason"] = "agent_llm_disabled"
        return False
    if bool(getattr(agent, "llm_pending", False)):
        profile["reflection_block_reason"] = "already_pending"
        return False

    tick = int(getattr(world, "tick", 0))
    last = int(profile.get("last_reflection_tick", -1000))
    cooldown = int(profile.get("reflection_cooldown_ticks", 80))
    if tick - last < cooldown:
        profile["reflection_block_reason"] = "cooldown"
        return False

    if float(profile.get("reflection_budget", 0.0)) < 0.15:
        profile["reflection_block_reason"] = "budget_low"
        return False

    if int(getattr(world, "llm_calls_this_tick", 0)) >= int(getattr(world, "max_llm_calls_per_tick", 1)):
        profile["reflection_block_reason"] = "global_budget_exhausted"
        return False

    state = getattr(agent, "subjective_state", {})
    attention = state.get("attention", {}) if isinstance(state, dict) else {}
    local_signals = state.get("local_signals", {}) if isinstance(state, dict) else {}
    needs = local_signals.get("needs", {}) if isinstance(local_signals.get("needs"), dict) else {}
    current_intention = getattr(agent, "current_intention", {})
    failed_ticks = int(current_intention.get("failed_ticks", 0)) if isinstance(current_intention, dict) else 0

    complexity = _attention_complexity_score(attention)
    blocked = failed_ticks >= 2
    high_stakes = bool(needs.get("food_urgent")) or bool(needs.get("hunger_critical"))
    social_importance = bool(attention.get("salient_local_leader")) or len(attention.get("top_social_targets", [])) >= 2
    uncertainty = complexity >= 0.55

    eligibility = 0.0
    if blocked:
        eligibility += 0.35
    if high_stakes:
        eligibility += 0.25
    if social_importance:
        eligibility += 0.15
    if uncertainty:
        eligibility += 0.20
    eligibility += float(profile.get("reflection_priority", 0.0)) * 0.20

    if eligibility < 0.42:
        profile["reflection_block_reason"] = "low_relevance"
        return False

    profile["reflection_block_reason"] = ""
    return True


def detect_agent_reflection_reason(world: "World", agent: Agent) -> Optional[str]:
    state = getattr(agent, "subjective_state", {})
    if not isinstance(state, dict):
        return None
    attention = state.get("attention", {}) if isinstance(state.get("attention"), dict) else {}
    local_signals = state.get("local_signals", {}) if isinstance(state.get("local_signals"), dict) else {}
    needs = local_signals.get("needs", {}) if isinstance(local_signals.get("needs"), dict) else {}
    local_culture = state.get("local_culture", {}) if isinstance(state.get("local_culture"), dict) else {}
    current_intention = getattr(agent, "current_intention", {})
    failed_ticks = int(current_intention.get("failed_ticks", 0)) if isinstance(current_intention, dict) else 0
    survival = evaluate_local_survival_pressure(world, agent)
    survival_pressure = float(survival.get("survival_pressure", 0.0))
    food_crisis = bool(survival.get("food_crisis", False))
    if failed_ticks >= 2:
        return "blocked_intention"

    recent = get_recent_memory_events(agent, limit=8)
    recent_failures = sum(1 for ev in recent if str(ev.get("outcome", "")) == "failure")
    if recent_failures >= 3:
        return "repeated_local_failure"
    if food_crisis and hunger > 35:
        return "conflicting_local_needs"

    hunger = float(getattr(agent, "hunger", 100.0))
    top_resources = attention.get("top_resource_targets", []) if isinstance(attention.get("top_resource_targets"), list) else []
    top_buildings = attention.get("top_building_targets", []) if isinstance(attention.get("top_building_targets"), list) else []
    if (
        hunger < 45
        and (bool(needs.get("need_materials")) or bool(needs.get("need_storage")) or bool(needs.get("need_housing")))
        and len(top_resources) > 0
        and len(top_buildings) > 0
    ):
        # Self urgency vs local collective pressure.
        return "conflicting_local_needs"

    if len(top_resources) >= 2:
        s0 = float(top_resources[0].get("salience", 0.0))
        s1 = float(top_resources[1].get("salience", 0.0))
        if abs(s0 - s1) <= 0.15 and bool(needs.get("food_urgent")) is False and survival_pressure < 0.7:
            return "conflicting_local_needs"

    role = str(getattr(agent, "role", "npc"))
    top_social = attention.get("top_social_targets", []) if isinstance(attention.get("top_social_targets"), list) else []
    leader = attention.get("salient_local_leader")
    coop_norm = float(local_culture.get("cooperation_norm", 0.5))
    if role in {"builder", "hauler"} and len(top_buildings) >= 2 and isinstance(leader, dict) and len(top_social) > 0 and coop_norm >= 0.45:
        return "uncertain_cooperative_choice"

    return None


INNOVATION_OPPORTUNITY_REASONS = {
    "transport_barrier",
    "storage_friction",
    "construction_friction",
    "resource_access_friction",
    "food_handling_friction",
    "route_inefficiency",
}

PROTO_ASSET_KINDS = {"infrastructure", "building", "tool", "process"}
PROTO_ASSET_CATEGORIES = {"transport", "logistics", "production", "storage", "water", "sanitation"}
PROTO_ASSET_EFFECTS = {
    "cross_water",
    "reduce_movement_cost",
    "increase_storage_efficiency",
    "improve_delivery_efficiency",
    "improve_resource_access",
    "improve_food_handling",
    "improve_construction_access",
}
PROTO_ASSET_MATERIALS = {"food", "wood", "stone"}
PROTO_ASSET_FOOTPRINT_PLACEMENTS = {"near_storage", "near_route", "near_water", "resource_edge", "village_core"}
PROTO_ASSET_STATUSES = {
    "proposed",
    "admissible",
    "rejected",
    "archived",
    "prototype_pending",
    "prototype_under_construction",
    "prototype_built",
    "prototype_failed",
}
PROTO_ASSET_REJECTION_REASONS = {
    "invalid_effect_context",
    "impossible_terrain_dependency",
    "excessive_material_cost",
    "unsupported_category_context",
    "duplicate_equivalent_proposal",
    "insufficient_local_basis",
    "invalid_schema",
    "unsupported_values",
}


def detect_agent_innovation_opportunity(world: "World", agent: Agent) -> Optional[str]:
    state = getattr(agent, "subjective_state", {})
    if not isinstance(state, dict):
        return None
    local_signals = state.get("local_signals", {}) if isinstance(state.get("local_signals"), dict) else {}
    needs = local_signals.get("needs", {}) if isinstance(local_signals.get("needs"), dict) else {}
    recent = get_recent_memory_events(agent, limit=18)
    current_intention = getattr(agent, "current_intention", {})
    failed_ticks = int(current_intention.get("failed_ticks", 0)) if isinstance(current_intention, dict) else 0

    failure_events = [ev for ev in recent if str(ev.get("outcome", "")) == "failure"]
    failed_resource_search = [ev for ev in failure_events if str(ev.get("type", "")) == "failed_resource_search"]
    unreachable_target = [ev for ev in failure_events if str(ev.get("type", "")) == "unreachable_target"]
    construction_blocked = [ev for ev in failure_events if str(ev.get("type", "")) == "construction_blocked"]

    if len(unreachable_target) >= 2:
        crossing_candidates = sum(
            1
            for ev in unreachable_target
            if str((ev.get("location") or {}).get("terrain_hint", "")).lower() in {"water", "chokepoint"}
        )
        if crossing_candidates >= 1:
            return "transport_barrier"
        return "route_inefficiency"

    if len(construction_blocked) >= 2 or (failed_ticks >= 3 and str(getattr(agent, "role", "")) in {"builder", "hauler"}):
        return "construction_friction"

    food_failures = sum(1 for ev in failed_resource_search if str(ev.get("resource_type", "")) == "food")
    if food_failures >= 3 or (bool(needs.get("food_buffer_critical")) and len(failure_events) >= 3):
        return "food_handling_friction"

    if bool(needs.get("need_storage")) and len(failure_events) >= 3:
        return "storage_friction"

    material_failures = sum(
        1
        for ev in failed_resource_search
        if str(ev.get("resource_type", "")) in {"wood", "stone"}
    )
    if material_failures >= 3:
        return "resource_access_friction"

    if failed_ticks >= 3:
        return "route_inefficiency"
    return None


def _deterministic_proto_asset_payload(
    world: "World",
    agent: Agent,
    reason: str,
) -> Dict[str, Any]:
    role = str(getattr(agent, "role", "npc"))
    base_materials = {"wood": 2, "stone": 1}
    if reason == "transport_barrier":
        return {
            "name": "ford path marker",
            "asset_kind": "infrastructure",
            "category": "transport",
            "intended_effects": ["cross_water", "reduce_movement_cost"],
            "required_materials": {"wood": 3, "stone": 2},
            "footprint_hint": {"width": 1, "height": 2, "placement": "near_water"},
        }
    if reason == "route_inefficiency":
        return {
            "name": "waypoint lane",
            "asset_kind": "infrastructure",
            "category": "transport",
            "intended_effects": ["reduce_movement_cost"],
            "required_materials": dict(base_materials),
            "footprint_hint": {"width": 1, "height": 1, "placement": "near_route"},
        }
    if reason == "storage_friction":
        return {
            "name": "cache shelf",
            "asset_kind": "building",
            "category": "storage",
            "intended_effects": ["increase_storage_efficiency", "improve_delivery_efficiency"],
            "required_materials": {"wood": 4, "stone": 1},
            "footprint_hint": {"width": 2, "height": 2, "placement": "near_storage"},
        }
    if reason == "food_handling_friction":
        return {
            "name": "food handoff routine",
            "asset_kind": "process",
            "category": "logistics",
            "intended_effects": ["improve_food_handling", "improve_delivery_efficiency"],
            "required_materials": {"wood": 1},
            "footprint_hint": {"width": 1, "height": 1, "placement": "village_core"},
        }
    if reason == "construction_friction":
        return {
            "name": "build staging spot",
            "asset_kind": "process" if role == "hauler" else "tool",
            "category": "logistics",
            "intended_effects": ["improve_construction_access", "improve_delivery_efficiency"],
            "required_materials": {"wood": 2, "stone": 2},
            "footprint_hint": {"width": 1, "height": 1, "placement": "near_storage"},
        }
    return {
        "name": "resource access marker",
        "asset_kind": "tool",
        "category": "production",
        "intended_effects": ["improve_resource_access"],
        "required_materials": {"wood": 2},
        "footprint_hint": {"width": 1, "height": 1, "placement": "resource_edge"},
    }


def validate_proto_asset_proposal(payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], str]:
    if not isinstance(payload, dict):
        return None, "invalid_schema"
    required = (
        "proposal_id",
        "inventor_agent_id",
        "tick_created",
        "reason",
        "name",
        "asset_kind",
        "category",
        "intended_effects",
        "required_materials",
        "footprint_hint",
        "status",
    )
    for key in required:
        if key not in payload:
            return None, "invalid_schema"

    reason = str(payload.get("reason", "")).strip().lower()
    if reason not in INNOVATION_OPPORTUNITY_REASONS:
        return None, "unsupported_values"
    name = str(payload.get("name", "")).strip().lower()
    if len(name) < 3 or len(name) > 48:
        return None, "unsupported_values"
    asset_kind = str(payload.get("asset_kind", "")).strip().lower()
    if asset_kind not in PROTO_ASSET_KINDS:
        return None, "unsupported_values"
    category = str(payload.get("category", "")).strip().lower()
    if category not in PROTO_ASSET_CATEGORIES:
        return None, "unsupported_values"

    effects = payload.get("intended_effects", [])
    if not isinstance(effects, list) or not effects:
        return None, "invalid_schema"
    cleaned_effects = []
    for effect in effects[:3]:
        e = str(effect).strip().lower()
        if e not in PROTO_ASSET_EFFECTS:
            return None, "unsupported_values"
        if e not in cleaned_effects:
            cleaned_effects.append(e)
    if not cleaned_effects:
        return None, "unsupported_values"

    materials = payload.get("required_materials", {})
    if not isinstance(materials, dict):
        return None, "invalid_schema"
    cleaned_materials: Dict[str, int] = {}
    for k, v in materials.items():
        resource = str(k).strip().lower()
        if resource not in PROTO_ASSET_MATERIALS:
            return None, "unsupported_values"
        qty = int(v)
        if qty < 0 or qty > 8:
            return None, "unsupported_values"
        if qty > 0:
            cleaned_materials[resource] = qty
    if not cleaned_materials:
        return None, "unsupported_values"

    hint = payload.get("footprint_hint", {})
    if not isinstance(hint, dict):
        return None, "invalid_schema"
    width = int(hint.get("width", 1))
    height = int(hint.get("height", 1))
    placement = str(hint.get("placement", "")).strip().lower()
    if width < 1 or width > 3 or height < 1 or height > 3:
        return None, "unsupported_values"
    if placement not in PROTO_ASSET_FOOTPRINT_PLACEMENTS:
        return None, "unsupported_values"

    status = str(payload.get("status", "proposed")).strip().lower() or "proposed"
    if status not in PROTO_ASSET_STATUSES:
        return None, "unsupported_values"
    rejection_reason_raw = str(payload.get("rejection_reason", "")).strip().lower()
    if rejection_reason_raw and rejection_reason_raw not in PROTO_ASSET_REJECTION_REASONS:
        return None, "unsupported_values"
    if status == "rejected" and not rejection_reason_raw:
        return None, "invalid_schema"
    if status != "rejected":
        rejection_reason_raw = ""

    cleaned = {
        "proposal_id": str(payload.get("proposal_id", "")).strip(),
        "inventor_agent_id": str(payload.get("inventor_agent_id", "")).strip(),
        "tick_created": int(payload.get("tick_created", 0)),
        "reason": reason,
        "name": name,
        "asset_kind": asset_kind,
        "category": category,
        "intended_effects": cleaned_effects,
        "required_materials": cleaned_materials,
        "footprint_hint": {"width": width, "height": height, "placement": placement},
        "status": status,
    }
    if rejection_reason_raw:
        cleaned["rejection_reason"] = rejection_reason_raw
    if "admissibility_tick" in payload:
        admissibility_tick = int(payload.get("admissibility_tick", -1))
        if admissibility_tick >= 0:
            cleaned["admissibility_tick"] = admissibility_tick
    if not cleaned["proposal_id"] or not cleaned["inventor_agent_id"] or cleaned["tick_created"] < 0:
        return None, "invalid_schema"
    return cleaned, ""


def maybe_generate_innovation_proposal(
    world: "World",
    agent: Agent,
    *,
    source: str = "stub",
    reason: Optional[str] = None,
    proposal_payload: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    local_reason = str(reason or detect_agent_innovation_opportunity(world, agent) or "").strip().lower()
    if local_reason not in INNOVATION_OPPORTUNITY_REASONS:
        return None

    existing = getattr(agent, "current_innovation_proposal", None)
    if isinstance(existing, dict):
        if str(existing.get("status", "")) in {"proposed", "admissible"} and int(getattr(world, "tick", 0)) - int(existing.get("tick_created", 0)) < 120:
            return None

    tick = int(getattr(world, "tick", 0))
    inventor_id = str(getattr(agent, "agent_id", "unknown"))
    if isinstance(proposal_payload, dict):
        base = dict(proposal_payload)
    else:
        base = _deterministic_proto_asset_payload(world, agent, local_reason)
    proposal = {
        "proposal_id": str(base.get("proposal_id") or f"pa-{inventor_id}-{tick}-{local_reason}"),
        "inventor_agent_id": inventor_id,
        "tick_created": tick,
        "reason": local_reason,
        "name": str(base.get("name", "")),
        "asset_kind": str(base.get("asset_kind", "")),
        "category": str(base.get("category", "")),
        "intended_effects": list(base.get("intended_effects", [])),
        "required_materials": dict(base.get("required_materials", {})),
        "footprint_hint": dict(base.get("footprint_hint", {})),
        "status": "proposed",
    }
    validated, validation_reason = validate_proto_asset_proposal(proposal)
    if validated is None:
        if hasattr(world, "record_proto_asset_proposal_rejected"):
            world.record_proto_asset_proposal_rejected(validation_reason or "invalid_schema")
        return None
    if hasattr(world, "register_proto_asset_proposal"):
        if not bool(world.register_proto_asset_proposal(validated, source=source)):
            return None
        stored = None
        for entry in reversed(list(getattr(world, "proto_asset_proposals", []) or [])):
            if not isinstance(entry, dict):
                continue
            if str(entry.get("proposal_id", "")) == str(validated.get("proposal_id", "")):
                stored = dict(entry)
                break
        if isinstance(stored, dict):
            agent.current_innovation_proposal = dict(stored)
            return dict(stored)
    agent.current_innovation_proposal = dict(validated)
    return dict(validated)


def build_agent_cognitive_context(world: "World", agent: Agent) -> Dict[str, Any]:
    profile = ensure_agent_cognitive_profile(agent)
    max_items = int(max(1, min(20, int(profile.get("max_context_items", 8)))))
    state = getattr(agent, "subjective_state", {})
    attention = state.get("attention", {}) if isinstance(state.get("attention"), dict) else {}
    local_signals = state.get("local_signals", {}) if isinstance(state.get("local_signals"), dict) else {}
    local_culture = state.get("local_culture", {}) if isinstance(state.get("local_culture"), dict) else {}

    recent_events = get_recent_memory_events(agent, limit=max_items)
    social_memory = (getattr(agent, "social_memory", {}) or {}).get("known_agents", {})
    social_subset = []
    if isinstance(social_memory, dict):
        entries = [
            (aid, rec) for aid, rec in social_memory.items()
            if isinstance(rec, dict)
        ]
        entries.sort(
            key=lambda item: (
                -float(item[1].get("social_salience", 0.0)),
                -int(item[1].get("times_seen", 0)),
                str(item[0]),
            )
        )
        for aid, rec in entries[:max_items]:
            social_subset.append(
                {
                    "agent_id": str(aid),
                    "times_seen": int(rec.get("times_seen", 0)),
                    "same_village": bool(rec.get("same_village", False)),
                    "role": str(rec.get("role", "npc")),
                    "social_salience": float(rec.get("social_salience", 0.0)),
                }
            )

    knowledge_state = ensure_agent_knowledge_state(agent)
    knowledge_subset = {}
    for key in ("known_resource_spots", "known_useful_buildings", "known_practices", "known_inventions"):
        entries = knowledge_state.get(key, [])
        if not isinstance(entries, list):
            knowledge_subset[key] = []
            continue
        sorted_entries = sorted(
            entries,
            key=lambda e: (
                -float(e.get("confidence", 0.0)),
                -float(e.get("salience", 0.0)),
                -int(e.get("learned_tick", 0)),
                str(e.get("subject", "")),
            ),
        )
        knowledge_subset[key] = sorted_entries[:max_items]

    context = {
        "tick": int(getattr(world, "tick", 0)),
        "agent_state": {
            "agent_id": str(getattr(agent, "agent_id", "")),
            "role": str(getattr(agent, "role", "npc")),
            "task": str(getattr(agent, "task", "idle")),
            "hunger": float(getattr(agent, "hunger", 100.0)),
            "inventory": dict(getattr(agent, "inventory", {})),
            "current_intention": dict(getattr(agent, "current_intention", {}) or {}),
            "current_innovation_proposal": dict(getattr(agent, "current_innovation_proposal", {}) or {}),
        },
        "attention": {
            "top_resource_targets": list(attention.get("top_resource_targets", []))[:max_items],
            "top_building_targets": list(attention.get("top_building_targets", []))[:max_items],
            "top_social_targets": list(attention.get("top_social_targets", []))[:max_items],
            "dominant_local_signal": attention.get("dominant_local_signal"),
            "current_focus": attention.get("current_focus"),
        },
        "local_signals": {
            "priority": local_signals.get("priority"),
            "needs": dict(local_signals.get("needs", {})) if isinstance(local_signals.get("needs"), dict) else {},
            "market_state": dict(local_signals.get("market_state", {})) if isinstance(local_signals.get("market_state"), dict) else {},
            "survival": dict(local_signals.get("survival", {})) if isinstance(local_signals.get("survival"), dict) else {},
        },
        "local_culture": dict(local_culture),
        "recent_events": recent_events[-max_items:],
        "social_memory": social_subset[:max_items],
        "self_model": dict(getattr(agent, "self_model", {})),
        "proto_traits": dict(getattr(agent, "proto_traits", {})),
        "knowledge_state": knowledge_subset,
    }
    profile["effective_context_size"] = int(
        len(context["recent_events"])
        + len(context["social_memory"])
        + len(context["attention"]["top_resource_targets"])
        + len(context["knowledge_state"].get("known_resource_spots", []))
    )
    return context


def evaluate_agent_social_influence(world: "World", agent: Agent) -> float:
    proto_traits = ensure_agent_proto_traits(agent)
    social_memory = getattr(agent, "social_memory", {})
    known_agents = social_memory.get("known_agents", {}) if isinstance(social_memory, dict) else {}
    tick = int(getattr(world, "tick", 0))

    familiarity_score = 0.0
    if isinstance(known_agents, dict) and known_agents:
        familiarity_samples = []
        for record in known_agents.values():
            if not isinstance(record, dict):
                continue
            times_seen = int(record.get("times_seen", 0))
            familiarity_samples.append(min(1.0, times_seen / 8.0))
        if familiarity_samples:
            familiarity_score = sum(familiarity_samples) / float(len(familiarity_samples))

    recent_events = get_recent_memory_events(agent, limit=24)
    cooperative_successes = 0
    recent_successes = 0
    recent_success_horizon = 30
    for ev in recent_events:
        if not isinstance(ev, dict):
            continue
        ev_tick = int(ev.get("tick", tick))
        if tick - ev_tick > recent_success_horizon:
            continue
        if str(ev.get("outcome", "")) == "success":
            recent_successes += 1
        if str(ev.get("type", "")) == "co_present_success" and str(ev.get("outcome", "")) == "success":
            cooperative_successes += 1

    cooperative_score = min(1.0, cooperative_successes / 4.0)
    success_score = min(1.0, recent_successes / 8.0)
    trait_score = (
        float(proto_traits.get("cooperation", 0.5)) * 0.45
        + float(proto_traits.get("diligence", 0.5)) * 0.30
        + float(proto_traits.get("resilience", 0.5)) * 0.25
    )
    role_bonus = 0.08 if str(getattr(agent, "role", "npc")) == "leader" else 0.0

    subjective = getattr(agent, "subjective_state", {})
    nearby_agents = subjective.get("nearby_agents", []) if isinstance(subjective, dict) else []
    nearby_count = len(nearby_agents) if isinstance(nearby_agents, list) else 0
    local_presence_score = min(1.0, nearby_count / 4.0)

    raw_score = (
        familiarity_score * 0.28
        + cooperative_score * 0.24
        + trait_score * 0.24
        + success_score * 0.14
        + local_presence_score * 0.10
        + role_bonus
    )

    prev = _clampf(float(getattr(agent, "social_influence", 0.0)))
    blended = prev * 0.70 + _clampf(raw_score) * 0.30

    # Slow decay when locally isolated and without recent collaborative success.
    if nearby_count == 0 and cooperative_successes == 0:
        blended = min(blended, prev * 0.985)

    return round(_clampf(blended), 3)


def detect_local_leader(agent: Agent, leadership_threshold: float = 0.55) -> Optional[Dict[str, Any]]:
    state = getattr(agent, "subjective_state", {})
    if not isinstance(state, dict):
        return None
    nearby_agents = state.get("nearby_agents", [])
    radius = state.get("radius", {}) if isinstance(state.get("radius"), dict) else {}
    social_radius = int(radius.get("social", max(1, int(getattr(agent, "social_radius_tiles", 8)))))
    if not isinstance(nearby_agents, list):
        return None

    candidates = []
    for entry in nearby_agents:
        if not isinstance(entry, dict):
            continue
        influence = _clampf(float(entry.get("social_influence", 0.0)))
        distance = int(entry.get("distance", social_radius + 1))
        if distance > social_radius:
            continue
        if influence < float(leadership_threshold):
            continue
        candidates.append(
            {
                "agent_id": str(entry.get("agent_id", "")),
                "x": int(entry.get("x", 0)),
                "y": int(entry.get("y", 0)),
                "distance": distance,
                "role": str(entry.get("role", "npc")),
                "same_village": bool(entry.get("same_village", False)),
                "social_influence": round(influence, 3),
            }
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda c: (
            -float(c["social_influence"]),
            int(c["distance"]),
            str(c["agent_id"]),
        )
    )
    return candidates[0]


def ensure_agent_self_model(agent: Agent) -> Dict[str, Any]:
    model = getattr(agent, "self_model", None)
    if not isinstance(model, dict) or not model:
        model = _default_self_model()
        role = str(getattr(agent, "role", "npc"))
        if role == "builder":
            model["work_weight"] += 0.10
            model["security_weight"] += 0.05
        elif role == "hauler":
            model["social_weight"] += 0.10
            model["work_weight"] += 0.05
        elif role in {"miner", "woodcutter"}:
            model["work_weight"] += 0.08
        elif role == "leader":
            model["social_weight"] += 0.12
            model["security_weight"] += 0.05
        for key in ("survival_weight", "social_weight", "work_weight", "exploration_weight", "security_weight"):
            model[key] = round(_clampf(float(model.get(key, 0.5))), 3)
        model["stress_level"] = round(_clampf(float(model.get("stress_level", 0.2))), 3)
        model["recent_success_bias"] = round(_clampf(float(model.get("recent_success_bias", 0.5))), 3)
        model["recent_failure_bias"] = round(_clampf(float(model.get("recent_failure_bias", 0.2))), 3)
        model["last_self_update_tick"] = -1
        agent.self_model = model
    return model


def write_episodic_memory_event(
    agent: Agent,
    *,
    tick: int,
    event_type: str,
    outcome: str,
    location: Optional[Tuple[int, int]] = None,
    target_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    building_type: Optional[str] = None,
    salience: float = 1.0,
    max_events: int = 40,
) -> Dict[str, Any]:
    memory = getattr(agent, "episodic_memory", None)
    if not isinstance(memory, dict):
        memory = {"recent_events": []}
        agent.episodic_memory = memory
    events = memory.get("recent_events")
    if not isinstance(events, list):
        events = []
        memory["recent_events"] = events

    payload: Dict[str, Any] = {
        "type": str(event_type),
        "tick": int(tick),
        "outcome": str(outcome),
        "salience": float(round(max(0.0, salience), 3)),
    }
    if location is not None:
        payload["location"] = {"x": int(location[0]), "y": int(location[1])}
    if target_id is not None:
        payload["target_id"] = str(target_id)
    if resource_type is not None:
        payload["resource_type"] = str(resource_type)
    if building_type is not None:
        payload["building_type"] = str(building_type)

    events.append(payload)

    # Leadership reinforcement hook: successful events with co-present peers
    # create compact cooperative traces and strengthen local familiarity.
    if str(outcome) == "success":
        subjective = getattr(agent, "subjective_state", {})
        nearby_agents = subjective.get("nearby_agents", []) if isinstance(subjective, dict) else []
        if isinstance(nearby_agents, list) and nearby_agents:
            coop_event = {
                "type": "co_present_success",
                "tick": int(tick),
                "outcome": "success",
                "salience": float(round(max(0.0, salience + 0.2), 3)),
            }
            if location is not None:
                coop_event["location"] = {"x": int(location[0]), "y": int(location[1])}
            if target_id is not None:
                coop_event["target_id"] = str(target_id)
            events.append(coop_event)

            social_memory = getattr(agent, "social_memory", {})
            known_agents = social_memory.get("known_agents", {}) if isinstance(social_memory, dict) else {}
            if isinstance(known_agents, dict):
                for near in nearby_agents:
                    if not isinstance(near, dict):
                        continue
                    aid = str(near.get("agent_id", ""))
                    if not aid:
                        continue
                    record = known_agents.get(aid)
                    if not isinstance(record, dict):
                        record = {
                            "last_seen_tick": int(tick),
                            "times_seen": 0,
                            "same_village": bool(near.get("same_village", False)),
                            "role": str(near.get("role", "npc")),
                            "recent_interaction": "seen",
                            "social_salience": 0.0,
                        }
                        known_agents[aid] = record
                    record["last_seen_tick"] = int(tick)
                    record["times_seen"] = int(record.get("times_seen", 0)) + 1
                    record["same_village"] = bool(near.get("same_village", False))
                    record["role"] = str(near.get("role", "npc"))
                    record["recent_interaction"] = "co_present_success"
                    record["social_salience"] = round(
                        min(4.0, float(record.get("social_salience", 0.0)) + 0.2), 3
                    )

    # Bounded episodic window: keep only most recent events.
    if len(events) > int(max_events):
        overflow = len(events) - int(max_events)
        del events[:overflow]
    return payload


def get_recent_memory_events(
    agent: Agent,
    event_type: Optional[str] = None,
    *,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    memory = getattr(agent, "episodic_memory", {})
    events = memory.get("recent_events", []) if isinstance(memory, dict) else []
    if not isinstance(events, list):
        return []
    filtered = [
        e for e in events
        if isinstance(e, dict) and (event_type is None or str(e.get("type", "")) == str(event_type))
    ]
    if limit is None:
        return list(filtered)
    return filtered[-max(0, int(limit)):]


def find_recent_resource_memory(agent: Agent, resource_type: str) -> List[Dict[str, Any]]:
    target = str(resource_type)
    events = get_recent_memory_events(agent)
    out = [
        e for e in events
        if str(e.get("resource_type", "")) == target
    ]
    out.sort(key=lambda e: (int(e.get("tick", 0)), float(e.get("salience", 0.0))))
    return out


def find_recent_building_memory(
    agent: Agent,
    *,
    building_type: Optional[str] = None,
    target_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    bt = None if building_type is None else str(building_type)
    tid = None if target_id is None else str(target_id)
    events = get_recent_memory_events(agent)
    out = []
    for e in events:
        if bt is not None and str(e.get("building_type", "")) != bt:
            continue
        if tid is not None and str(e.get("target_id", "")) != tid:
            continue
        out.append(e)
    out.sort(key=lambda e: (int(e.get("tick", 0)), float(e.get("salience", 0.0))))
    return out


def _iter_resource_coords(world: "World", name: str) -> Set[Tuple[int, int]]:
    if name == "food":
        return set(getattr(world, "food", set()))
    if name == "wood":
        return set(getattr(world, "wood", set()))
    if name == "stone":
        return set(getattr(world, "stone", set()))
    return set()


def _village_local_signals(world: "World", agent: Agent) -> Dict[str, Any]:
    village_id = getattr(agent, "village_id", None)
    if village_id is None:
        return {}
    village = world.get_village_by_id(village_id)
    if not isinstance(village, dict):
        return {}

    market_state = village.get("market_state", {})
    if not isinstance(market_state, dict):
        market_state = {}

    compact_market = {}
    for resource in ("food", "wood", "stone"):
        entry = market_state.get(resource, {})
        if isinstance(entry, dict):
            compact_market[resource] = {
                "pressure": float(entry.get("pressure", 0.0)),
                "local_price_index": float(entry.get("local_price_index", 1.0)),
            }

    construction_needs = {"wood": 0, "stone": 0, "food": 0}
    for building in getattr(world, "buildings", {}).values():
        if building.get("village_id") != village_id:
            continue
        request = building.get("construction_request", {})
        if not isinstance(request, dict):
            continue
        for resource in ("wood", "stone", "food"):
            needed = int(request.get(f"{resource}_needed", 0))
            reserved = int(request.get(f"{resource}_reserved", 0))
            construction_needs[resource] += max(0, needed - reserved)

    return {
        "village_id": village_id,
        "priority": str(village.get("priority", "stabilize")),
        "needs": dict(village.get("needs", {})) if isinstance(village.get("needs"), dict) else {},
        "market_state": compact_market,
        "construction_needs": construction_needs,
    }


def evaluate_local_survival_pressure(world: "World", agent: Agent) -> Dict[str, Any]:
    state = getattr(agent, "subjective_state", {})
    local_signals = state.get("local_signals", {}) if isinstance(state, dict) else {}
    needs = local_signals.get("needs", {}) if isinstance(local_signals.get("needs"), dict) else {}
    market_state = local_signals.get("market_state", {}) if isinstance(local_signals.get("market_state"), dict) else {}
    nearby_resources = state.get("nearby_resources", {}) if isinstance(state, dict) else {}

    hunger = float(getattr(agent, "hunger", 100.0))
    hunger_pressure = _clampf((60.0 - hunger) / 60.0)
    critical_hunger = _clampf((35.0 - hunger) / 35.0)

    village_food_pressure = float((market_state.get("food") or {}).get("pressure", 0.0)) if isinstance(market_state, dict) else 0.0
    village_food_price = float((market_state.get("food") or {}).get("local_price_index", 1.0)) if isinstance(market_state, dict) else 1.0
    market_pressure = _clampf(village_food_pressure)
    market_price_pressure = _clampf((village_food_price - 1.0) / 1.5)

    village_storage_pressure = 0.0
    village_id = getattr(agent, "village_id", None)
    village = world.get_village_by_id(village_id) if village_id is not None else None
    if isinstance(village, dict):
        storage = village.get("storage", {}) if isinstance(village.get("storage"), dict) else {}
        food_stock = int(storage.get("food", 0))
        pop = max(1, int(village.get("population", 1)))
        target = max(4, pop * 2)
        village_storage_pressure = _clampf((target - food_stock) / float(target))

    needs_pressure = 0.0
    if bool(needs.get("food_urgent")):
        needs_pressure += 0.45
    if bool(needs.get("food_buffer_critical")):
        needs_pressure += 0.35
    if bool(needs.get("hunger_critical")):
        needs_pressure += 0.30
    needs_pressure = _clampf(needs_pressure)

    visible_food_entries = nearby_resources.get("food", []) if isinstance(nearby_resources, dict) else []
    visible_food_count = len(visible_food_entries) if isinstance(visible_food_entries, list) else 0
    visible_food_scarcity = 0.5 if visible_food_count == 0 else (0.2 if visible_food_count <= 2 else 0.0)

    recent_events = get_recent_memory_events(agent, limit=12)
    hunger_failure_events = sum(
        1
        for ev in recent_events
        if isinstance(ev, dict)
        and str(ev.get("type", "")) in {"failed_resource_search"}
        and str(ev.get("resource_type", "")) == "food"
        and str(ev.get("outcome", "")) == "failure"
    )
    hunger_relief_events = sum(
        1
        for ev in recent_events
        if isinstance(ev, dict)
        and str(ev.get("type", "")) == "hunger_relief"
        and str(ev.get("outcome", "")) == "success"
    )
    memory_pressure = _clampf(min(1.0, hunger_failure_events * 0.25) - min(0.5, hunger_relief_events * 0.12))

    pressure = (
        hunger_pressure * 0.32
        + critical_hunger * 0.16
        + market_pressure * 0.16
        + market_price_pressure * 0.10
        + village_storage_pressure * 0.14
        + needs_pressure * 0.08
        + visible_food_scarcity * 0.02
        + memory_pressure * 0.02
    )
    pressure = round(_clampf(pressure), 3)
    if pressure >= 0.75:
        level = "critical"
    elif pressure >= 0.50:
        level = "high"
    elif pressure >= 0.30:
        level = "moderate"
    else:
        level = "low"
    return {
        "survival_pressure": pressure,
        "food_crisis": bool(pressure >= 0.60),
        "food_insecurity_level": level,
    }


def _village_local_culture(world: "World", agent: Agent) -> Dict[str, Any]:
    village_id = getattr(agent, "village_id", None)
    if village_id is None:
        return {}
    village = world.get_village_by_id(village_id)
    if not isinstance(village, dict):
        return {}
    culture = village.get("proto_culture", {})
    if not isinstance(culture, dict):
        return {}
    resource_focus = culture.get("resource_focus", {}) if isinstance(culture.get("resource_focus"), dict) else {}
    ordered = ("food", "wood", "stone")
    dominant = max(ordered, key=lambda r: (float(resource_focus.get(r, 0.0)), -ordered.index(r)))
    return {
        "cooperation_norm": float(culture.get("cooperation_norm", 0.5)),
        "work_norm": float(culture.get("work_norm", 0.5)),
        "exploration_norm": float(culture.get("exploration_norm", 0.5)),
        "risk_norm": float(culture.get("risk_norm", 0.5)),
        "dominant_resource_focus": dominant,
    }


def update_agent_social_memory(world: "World", agent: Agent, subjective_state: Dict[str, Any]) -> None:
    social_memory = getattr(agent, "social_memory", None)
    if not isinstance(social_memory, dict):
        social_memory = {"known_agents": {}}
        agent.social_memory = social_memory
    known_agents = social_memory.get("known_agents")
    if not isinstance(known_agents, dict):
        known_agents = {}
        social_memory["known_agents"] = known_agents

    tick = int(getattr(world, "tick", 0))
    nearby_agents = subjective_state.get("nearby_agents", []) if isinstance(subjective_state, dict) else []
    if not isinstance(nearby_agents, list):
        nearby_agents = []

    recent_success = False
    for ev in get_recent_memory_events(agent, limit=6):
        if str(ev.get("outcome", "")) == "success" and tick - int(ev.get("tick", tick)) <= 2:
            recent_success = True
            break

    seen_ids = set()
    for entry in nearby_agents:
        if not isinstance(entry, dict):
            continue
        agent_id = str(entry.get("agent_id", ""))
        if not agent_id:
            continue
        seen_ids.add(agent_id)
        same_village = bool(entry.get("same_village", False))
        role = str(entry.get("role", "npc"))

        record = known_agents.get(agent_id)
        if not isinstance(record, dict):
            record = {
                "last_seen_tick": tick,
                "times_seen": 0,
                "same_village": False,
                "role": role,
                "recent_interaction": "seen",
                "social_salience": 0.0,
            }
            known_agents[agent_id] = record

        record["last_seen_tick"] = tick
        record["times_seen"] = int(record.get("times_seen", 0)) + 1
        record["same_village"] = bool(same_village)
        record["role"] = role
        if recent_success:
            record["recent_interaction"] = "co_present_success"
        elif str(record.get("recent_interaction", "")) == "":
            record["recent_interaction"] = "seen"

        times_seen = int(record.get("times_seen", 0))
        social_salience = min(3.0, times_seen * 0.12)
        if bool(record.get("same_village", False)):
            social_salience += 0.8
        if role == "leader":
            social_salience += 0.8
        if str(record.get("recent_interaction", "")) == "co_present_success":
            social_salience += 0.6
        record["social_salience"] = round(float(min(4.0, social_salience)), 3)

    # Deterministic decay for unseen entries.
    for agent_id in sorted(list(known_agents.keys())):
        if agent_id in seen_ids:
            continue
        record = known_agents.get(agent_id)
        if not isinstance(record, dict):
            continue
        last_seen = int(record.get("last_seen_tick", tick))
        age = max(0, tick - last_seen)
        base_salience = float(record.get("social_salience", 0.0))
        decay = 0.02 * min(age, 10)
        record["social_salience"] = round(max(0.0, base_salience - decay), 3)
        if age > 20 and str(record.get("recent_interaction", "")) == "co_present_success":
            record["recent_interaction"] = "seen"

    # Bounded social memory: drop least recent/least salient deterministically.
    max_known_agents = 40
    if len(known_agents) > max_known_agents:
        keys = sorted(
            known_agents.keys(),
            key=lambda k: (
                int(known_agents[k].get("last_seen_tick", 0)),
                float(known_agents[k].get("social_salience", 0.0)),
                int(known_agents[k].get("times_seen", 0)),
                str(k),
            ),
        )
        overflow = len(known_agents) - max_known_agents
        for k in keys[:overflow]:
            known_agents.pop(k, None)


def update_agent_self_model(world: "World", agent: Agent) -> Dict[str, Any]:
    model = ensure_agent_self_model(agent)
    tick = int(getattr(world, "tick", 0))
    last_tick = int(model.get("last_self_update_tick", -1))
    if last_tick == tick:
        return model

    hunger = float(getattr(agent, "hunger", 100.0))
    if hunger < 45:
        model["survival_weight"] = _clampf(float(model["survival_weight"]) + 0.03)
        model["stress_level"] = _clampf(float(model["stress_level"]) + 0.04)
    elif hunger > 75:
        model["stress_level"] = _clampf(float(model["stress_level"]) - 0.02)

    recent_events = get_recent_memory_events(agent, limit=12)
    success_count = sum(1 for e in recent_events if str(e.get("outcome", "")) == "success")
    failure_count = sum(1 for e in recent_events if str(e.get("outcome", "")) == "failure")
    work_success = sum(
        1
        for e in recent_events
        if str(e.get("type", "")) in {"construction_progress", "delivered_material", "found_resource"}
        and str(e.get("outcome", "")) == "success"
    )
    social_success = sum(
        1
        for e in recent_events
        if str(e.get("type", "")) == "useful_building"
        and str(e.get("outcome", "")) == "success"
    )
    explore_success = sum(
        1
        for e in recent_events
        if str(e.get("type", "")) in {"found_resource", "hunger_relief"}
        and str(e.get("outcome", "")) == "success"
    )

    if work_success > 0:
        model["work_weight"] = _clampf(float(model["work_weight"]) + 0.01 * work_success)
    if social_success > 0:
        model["social_weight"] = _clampf(float(model["social_weight"]) + 0.01 * social_success)
    if explore_success > 0:
        model["exploration_weight"] = _clampf(float(model["exploration_weight"]) + 0.006 * explore_success)

    if failure_count > success_count:
        model["stress_level"] = _clampf(float(model["stress_level"]) + 0.02)
        model["recent_failure_bias"] = _clampf(float(model["recent_failure_bias"]) + 0.02)
        model["recent_success_bias"] = _clampf(float(model["recent_success_bias"]) - 0.01)
    elif success_count > failure_count:
        model["stress_level"] = _clampf(float(model["stress_level"]) - 0.01)
        model["recent_success_bias"] = _clampf(float(model["recent_success_bias"]) + 0.02)
        model["recent_failure_bias"] = _clampf(float(model["recent_failure_bias"]) - 0.01)

    # Local social familiarity affects social orientation gradually.
    known_agents = (getattr(agent, "social_memory", {}) or {}).get("known_agents", {})
    if isinstance(known_agents, dict):
        familiar = sum(1 for record in known_agents.values() if isinstance(record, dict) and int(record.get("times_seen", 0)) >= 3)
        if familiar > 0:
            model["social_weight"] = _clampf(float(model["social_weight"]) + 0.004 * min(familiar, 4))

    for key in ("survival_weight", "social_weight", "work_weight", "exploration_weight", "security_weight"):
        model[key] = round(_clampf(float(model.get(key, 0.5))), 3)
    model["stress_level"] = round(_clampf(float(model.get("stress_level", 0.2))), 3)
    model["recent_success_bias"] = round(_clampf(float(model.get("recent_success_bias", 0.5))), 3)
    model["recent_failure_bias"] = round(_clampf(float(model.get("recent_failure_bias", 0.2))), 3)
    model["last_self_update_tick"] = tick
    return model


def interpret_local_signals_with_self_model(world: "World", agent: Agent) -> Dict[str, Any]:
    model = ensure_agent_self_model(agent)
    proto_traits = ensure_agent_proto_traits(agent)
    state = getattr(agent, "subjective_state", {})
    local_signals = state.get("local_signals", {}) if isinstance(state, dict) else {}
    market_state = local_signals.get("market_state", {}) if isinstance(local_signals.get("market_state"), dict) else {}
    needs = local_signals.get("needs", {}) if isinstance(local_signals.get("needs"), dict) else {}
    survival = evaluate_local_survival_pressure(world, agent)
    survival_pressure = float(survival.get("survival_pressure", 0.0))
    food_crisis = bool(survival.get("food_crisis", False))

    food_pressure = float((market_state.get("food") or {}).get("pressure", 0.0))
    wood_pressure = float((market_state.get("wood") or {}).get("pressure", 0.0))
    stone_pressure = float((market_state.get("stone") or {}).get("pressure", 0.0))

    food_score = food_pressure * (0.9 + float(model.get("survival_weight", 0.5)) + float(proto_traits.get("caution", 0.5)) * 0.08)
    work_score = max(wood_pressure, stone_pressure) * (
        0.7 + float(model.get("work_weight", 0.5)) + float(proto_traits.get("diligence", 0.5)) * 0.08
    )
    social_score = (0.3 if bool(needs.get("need_materials")) else 0.0) * (0.8 + float(model.get("social_weight", 0.5)))
    explore_score = (1.0 - max(food_pressure, wood_pressure, stone_pressure)) * (
        float(model.get("exploration_weight", 0.3)) + float(proto_traits.get("curiosity", 0.5)) * 0.10
    )
    food_score += survival_pressure * 2.2
    work_score -= survival_pressure * 0.55
    social_score += survival_pressure * 0.20
    explore_score -= survival_pressure * 1.15
    if food_crisis:
        food_score += 1.8
        work_score -= 0.6
        explore_score -= 0.9

    preference = "food_security"
    if work_score > food_score and work_score >= social_score:
        preference = "work_materials"
    elif social_score > food_score and social_score >= work_score:
        preference = "social_coordination"
    elif explore_score > food_score and explore_score > work_score:
        preference = "exploration"

    preferred_resource = "food"
    if preference == "work_materials":
        preferred_resource = "wood" if wood_pressure >= stone_pressure else "stone"
    elif preference == "exploration":
        preferred_resource = "food" if food_pressure > 0.2 else ("wood" if wood_pressure >= stone_pressure else "stone")

    return {
        "priority_interpretation": preference,
        "preferred_resource": preferred_resource,
        "stress_narrowing": float(model.get("stress_level", 0.2)),
        "survival_pressure": survival_pressure,
    }


def build_agent_perception(world: "World", agent: Agent) -> Dict[str, Any]:
    ax, ay = int(agent.x), int(agent.y)
    visual_radius = max(1, int(getattr(agent, "visual_radius_tiles", 8)))
    social_radius = max(1, int(getattr(agent, "social_radius_tiles", visual_radius)))

    nearby_resources: Dict[str, List[Dict[str, int]]] = {"food": [], "wood": [], "stone": []}
    for resource_name in ("food", "wood", "stone"):
        coords = _iter_resource_coords(world, resource_name)
        visible = []
        for x, y in coords:
            dist = _manhattan((ax, ay), (int(x), int(y)))
            if dist <= visual_radius:
                visible.append((int(x), int(y), int(dist)))
        visible.sort(key=lambda item: (item[2], item[1], item[0]))
        nearby_resources[resource_name] = [
            {"x": x, "y": y, "distance": dist}
            for x, y, dist in visible
        ]

    nearby_buildings: List[Dict[str, Any]] = []
    for building_id in sorted(getattr(world, "buildings", {}).keys()):
        building = world.buildings[building_id]
        bx = int(building.get("x", 0))
        by = int(building.get("y", 0))
        dist = _manhattan((ax, ay), (bx, by))
        if dist > visual_radius:
            continue
        nearby_buildings.append(
            {
                "building_id": str(building.get("building_id", "")),
                "type": str(building.get("type", "")),
                "x": bx,
                "y": by,
                "distance": int(dist),
                "operational_state": str(building.get("operational_state", "active")),
            }
        )
    nearby_buildings.sort(key=lambda b: (b["distance"], b["y"], b["x"], b["building_id"]))

    nearby_agents: List[Dict[str, Any]] = []
    own_village_id = getattr(agent, "village_id", None)
    for other in getattr(world, "agents", []):
        if not getattr(other, "alive", False):
            continue
        if other is agent:
            continue
        ox = int(getattr(other, "x", 0))
        oy = int(getattr(other, "y", 0))
        dist = _manhattan((ax, ay), (ox, oy))
        if dist > social_radius:
            continue
        nearby_agents.append(
            {
                "agent_id": str(getattr(other, "agent_id", "")),
                "x": ox,
                "y": oy,
                "distance": int(dist),
                "role": str(getattr(other, "role", "npc")),
                "social_influence": round(_clampf(float(getattr(other, "social_influence", 0.0))), 3),
                "same_village": bool(
                    own_village_id is not None and getattr(other, "village_id", None) == own_village_id
                ),
            }
        )
    nearby_agents.sort(key=lambda a: (a["distance"], a["y"], a["x"], a["agent_id"]))

    terrain_summary: Dict[str, int] = {}
    nearby_transport: List[Dict[str, Any]] = []
    for dx in range(-visual_radius, visual_radius + 1):
        for dy in range(-visual_radius, visual_radius + 1):
            x = ax + dx
            y = ay + dy
            if x < 0 or y < 0 or x >= int(world.width) or y >= int(world.height):
                continue
            if _manhattan((ax, ay), (x, y)) > visual_radius:
                continue
            terrain = str(world.tiles[y][x])
            terrain_summary[terrain] = int(terrain_summary.get(terrain, 0)) + 1
            ttype = getattr(world, "get_transport_type", lambda _x, _y: None)(x, y)
            if ttype is not None:
                nearby_transport.append({"x": int(x), "y": int(y), "type": str(ttype)})
    nearby_transport.sort(key=lambda t: (t["y"], t["x"], t["type"]))

    return {
        "last_perception_tick": int(getattr(world, "tick", 0)),
        "radius": {"visual": visual_radius, "social": social_radius},
        "own_state": {
            "hunger": float(getattr(agent, "hunger", 0.0)),
            "role": str(getattr(agent, "role", "npc")),
            "task": str(getattr(agent, "task", "idle")),
            "inventory": {
                "food": int(getattr(agent, "inventory", {}).get("food", 0)),
                "wood": int(getattr(agent, "inventory", {}).get("wood", 0)),
                "stone": int(getattr(agent, "inventory", {}).get("stone", 0)),
            },
            "assigned_building_id": getattr(agent, "assigned_building_id", None),
        },
        "nearby_resources": nearby_resources,
        "nearby_buildings": nearby_buildings,
        "nearby_agents": nearby_agents,
        "nearby_infrastructure": {"transport_tiles": nearby_transport},
        "terrain_summary": {k: int(v) for k, v in sorted(terrain_summary.items(), key=lambda item: item[0])},
        "local_signals": _village_local_signals(world, agent),
        "local_culture": _village_local_culture(world, agent),
    }


def evaluate_agent_salience(world: "World", agent: Agent) -> Dict[str, Any]:
    model = ensure_agent_self_model(agent)
    proto_traits = ensure_agent_proto_traits(agent)
    survival_w = float(model.get("survival_weight", 0.5))
    social_w = float(model.get("social_weight", 0.5))
    work_w = float(model.get("work_weight", 0.5))
    explore_w = float(model.get("exploration_weight", 0.3))
    stress = float(model.get("stress_level", 0.2))
    cooperation = float(proto_traits.get("cooperation", 0.5))
    diligence = float(proto_traits.get("diligence", 0.5))
    caution = float(proto_traits.get("caution", 0.5))
    curiosity = float(proto_traits.get("curiosity", 0.5))
    resilience = float(proto_traits.get("resilience", 0.5))
    effective_stress = stress * (1.0 - 0.35 * resilience)
    state = agent.subjective_state if isinstance(agent.subjective_state, dict) else {}
    own = state.get("own_state", {}) if isinstance(state.get("own_state"), dict) else {}
    role = str(own.get("role", getattr(agent, "role", "npc")))
    task = str(own.get("task", getattr(agent, "task", "idle")))
    hunger = float(own.get("hunger", getattr(agent, "hunger", 100.0)))
    assigned_building_id = own.get("assigned_building_id", getattr(agent, "assigned_building_id", None))

    local_signals = state.get("local_signals", {}) if isinstance(state.get("local_signals"), dict) else {}
    local_culture = state.get("local_culture", {}) if isinstance(state.get("local_culture"), dict) else {}
    market_state = local_signals.get("market_state", {}) if isinstance(local_signals.get("market_state"), dict) else {}
    needs = local_signals.get("needs", {}) if isinstance(local_signals.get("needs"), dict) else {}
    construction_needs = local_signals.get("construction_needs", {}) if isinstance(local_signals.get("construction_needs"), dict) else {}
    culture_coop = float(local_culture.get("cooperation_norm", 0.5))
    culture_work = float(local_culture.get("work_norm", 0.5))
    culture_explore = float(local_culture.get("exploration_norm", 0.5))
    culture_risk = float(local_culture.get("risk_norm", 0.5))
    culture_focus = str(local_culture.get("dominant_resource_focus", ""))
    survival = evaluate_local_survival_pressure(world, agent)
    survival_pressure = float(survival.get("survival_pressure", 0.0))
    food_crisis = bool(survival.get("food_crisis", False))

    nearby_resources = state.get("nearby_resources", {}) if isinstance(state.get("nearby_resources"), dict) else {}
    nearby_buildings = state.get("nearby_buildings", []) if isinstance(state.get("nearby_buildings"), list) else []
    nearby_agents = state.get("nearby_agents", []) if isinstance(state.get("nearby_agents"), list) else []

    scored_resources: List[Dict[str, Any]] = []
    recent_resource_events = find_recent_resource_memory(agent, "food") + find_recent_resource_memory(agent, "wood") + find_recent_resource_memory(agent, "stone")
    recent_resource_boost: Dict[Tuple[str, int, int], float] = {}
    for ev in recent_resource_events[-12:]:
        loc = ev.get("location", {})
        if not isinstance(loc, dict):
            continue
        rx = int(loc.get("x", 0))
        ry = int(loc.get("y", 0))
        rr = str(ev.get("resource_type", ""))
        if rr not in {"food", "wood", "stone"}:
            continue
        if str(ev.get("outcome", "")) == "success":
            recent_resource_boost[(rr, rx, ry)] = max(recent_resource_boost.get((rr, rx, ry), 0.0), 0.7)
        elif str(ev.get("outcome", "")) == "failure":
            recent_resource_boost[(rr, rx, ry)] = min(recent_resource_boost.get((rr, rx, ry), 0.0), -0.5)
    for resource in ("food", "wood", "stone"):
        entries = nearby_resources.get(resource, [])
        if not isinstance(entries, list):
            continue
        market_pressure = float((market_state.get(resource) or {}).get("pressure", 0.0)) if isinstance(market_state, dict) else 0.0
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            x = int(entry.get("x", 0))
            y = int(entry.get("y", 0))
            distance = int(entry.get("distance", abs(x - int(agent.x)) + abs(y - int(agent.y))))
            score = 1.0 / (1.0 + float(distance))
            score += market_pressure * 1.5
            score -= min(0.6, effective_stress * 0.07 * float(distance))
            score -= caution * 0.015 * float(distance)
            score -= max(0.0, (1.0 - culture_risk)) * 0.01 * float(distance)

            if resource == "food":
                if hunger < 60:
                    score += 2.0 * (0.6 + survival_w)
                if hunger < 35:
                    score += 3.0 * (0.6 + survival_w)
                if bool(needs.get("food_urgent")) or bool(needs.get("food_buffer_critical")):
                    score += 2.5 * (0.6 + survival_w)
                score += survival_pressure * 2.0
                if food_crisis:
                    score += 1.2
            if role == "miner" and resource == "stone":
                score += 2.5 * (0.5 + work_w)
            if role == "woodcutter" and resource == "wood":
                score += 2.5 * (0.5 + work_w)
            if role == "builder" and resource in {"wood", "stone"}:
                score += 1.8 * (0.5 + work_w + diligence * 0.12)
            if role == "hauler" and int(construction_needs.get(resource, 0)) > 0:
                score += 1.5 * (0.4 + social_w)

            if task in {"mine_cycle"} and resource == "stone":
                score += 2.0
            if task in {"lumber_cycle"} and resource == "wood":
                score += 2.0
            if task in {"gather_food_wild"} and resource == "food":
                score += 2.0
            if task in {"build_storage", "build_house", "gather_materials"} and resource in {"wood", "stone"}:
                score += 1.8 * (0.5 + work_w + diligence * 0.10)
            if task in {"survive", "idle"} and resource != "food":
                score += explore_w * 0.2 + curiosity * 0.12
            if food_crisis and resource in {"wood", "stone"}:
                score -= 0.9
            if culture_focus == resource:
                score += 0.22
            score += recent_resource_boost.get((resource, x, y), 0.0)

            scored_resources.append(
                {
                    "resource": resource,
                    "x": x,
                    "y": y,
                    "distance": distance,
                    "salience": round(float(score), 3),
                }
            )

    scored_resources.sort(
        key=lambda r: (
            -float(r["salience"]),
            int(r["distance"]),
            int(r["y"]),
            int(r["x"]),
            str(r["resource"]),
        )
    )
    top_resource_targets = scored_resources[:3]

    scored_buildings: List[Dict[str, Any]] = []
    recent_useful_building_events = get_recent_memory_events(agent, "useful_building", limit=16)
    useful_building_boost: Dict[str, float] = {}
    for ev in recent_useful_building_events:
        bid = str(ev.get("target_id", ""))
        if not bid:
            continue
        useful_building_boost[bid] = max(useful_building_boost.get(bid, 0.0), 0.9)
    for entry in nearby_buildings:
        if not isinstance(entry, dict):
            continue
        btype = str(entry.get("type", ""))
        building_id = str(entry.get("building_id", ""))
        distance = int(entry.get("distance", 0))
        operational_state = str(entry.get("operational_state", "active"))
        score = 1.0 / (1.0 + float(distance))
        score -= min(0.5, effective_stress * 0.05 * float(distance))
        score -= caution * 0.01 * float(distance)
        score -= max(0.0, (1.0 - culture_risk)) * 0.008 * float(distance)

        if assigned_building_id is not None and str(assigned_building_id) == building_id:
            score += 5.0
        if role == "miner" and btype == "mine":
            score += 3.0
        if role == "woodcutter" and btype == "lumberyard":
            score += 3.0
        if role in {"builder", "hauler"} and operational_state == "under_construction":
            score += 3.0 * (0.5 + work_w + diligence * 0.10)
            score += culture_work * 0.25
            if food_crisis:
                score -= 1.1
        if btype == "storage" and (role in {"hauler", "builder"} or hunger < 55):
            score += 2.0 * (0.5 + max(work_w, survival_w))
            score += survival_pressure * 0.8
        if task in {"build_storage"} and btype == "storage":
            score += 2.5
        if task in {"build_house"} and btype == "house":
            score += 2.0
        if int(construction_needs.get("wood", 0)) + int(construction_needs.get("stone", 0)) > 0 and operational_state == "under_construction":
            score += 1.0 + diligence * 0.15
            score += culture_work * 0.18
            if food_crisis:
                score -= 0.8
        score += useful_building_boost.get(building_id, 0.0)

        scored_buildings.append(
            {
                "building_id": building_id,
                "type": btype,
                "x": int(entry.get("x", 0)),
                "y": int(entry.get("y", 0)),
                "distance": distance,
                "salience": round(float(score), 3),
            }
        )

    scored_buildings.sort(
        key=lambda b: (
            -float(b["salience"]),
            int(b["distance"]),
            int(b["y"]),
            int(b["x"]),
            str(b["building_id"]),
        )
    )
    top_building_targets = scored_buildings[:3]

    scored_social: List[Dict[str, Any]] = []
    social_memory = getattr(agent, "social_memory", {})
    known_agents = social_memory.get("known_agents", {}) if isinstance(social_memory, dict) else {}
    for entry in nearby_agents:
        if not isinstance(entry, dict):
            continue
        distance = int(entry.get("distance", 0))
        other_role = str(entry.get("role", "npc"))
        other_id = str(entry.get("agent_id", ""))
        same_village = bool(entry.get("same_village", False))
        other_influence = _clampf(float(entry.get("social_influence", 0.0)))
        score = 1.0 / (1.0 + float(distance))
        score += other_influence * 0.8
        if other_role == "leader":
            score += 1.0 * (0.4 + social_w)
        if other_role == role:
            score += 0.5 * (0.4 + social_w)
        if same_village:
            score += 0.6 * (0.5 + social_w + cooperation * 0.18)
            score += culture_coop * 0.15
        record = known_agents.get(other_id, {}) if isinstance(known_agents, dict) else {}
        if isinstance(record, dict):
            score += min(1.5, float(record.get("social_salience", 0.0)) * 0.35)
            if int(record.get("times_seen", 0)) >= 3:
                score += 0.4
            if str(record.get("recent_interaction", "")) == "co_present_success":
                score += 0.7 * (0.4 + social_w + cooperation * 0.12)
        scored_social.append(
            {
                "agent_id": other_id,
                "role": other_role,
                "x": int(entry.get("x", 0)),
                "y": int(entry.get("y", 0)),
                "distance": distance,
                "same_village": same_village,
                "salience": round(float(score), 3),
            }
        )
    scored_social.sort(
        key=lambda a: (
            -float(a["salience"]),
            int(a["distance"]),
            int(a["y"]),
            int(a["x"]),
            str(a["agent_id"]),
        )
    )
    top_social_targets = scored_social[:3]
    familiar_agents_nearby = [
        {
            "agent_id": str(s.get("agent_id", "")),
            "role": str(s.get("role", "npc")),
            "same_village": bool(s.get("same_village", False)),
        }
        for s in top_social_targets
        if int((known_agents.get(str(s.get("agent_id", "")), {}) if isinstance(known_agents, dict) else {}).get("times_seen", 0)) >= 2
    ][:3]
    salient_local_leader = detect_local_leader(agent)

    leader_nearby = bool(salient_local_leader)
    if leader_nearby:
        # Small social-follow bias: cooperation gets a nudge while exploration de-escalates.
        for entry in top_building_targets:
            if str(entry.get("type", "")) in {"storage", "house", "farm_plot", "mine", "lumberyard"}:
                entry["salience"] = round(float(entry.get("salience", 0.0)) + 0.25, 3)
        for entry in top_resource_targets:
            if str(entry.get("resource", "")) in {"wood", "stone", "food"}:
                entry["salience"] = round(float(entry.get("salience", 0.0)) + 0.12, 3)
        top_building_targets.sort(
            key=lambda b: (
                -float(b["salience"]),
                int(b["distance"]),
                int(b["y"]),
                int(b["x"]),
                str(b["building_id"]),
            )
        )
        top_resource_targets.sort(
            key=lambda r: (
                -float(r["salience"]),
                int(r["distance"]),
                int(r["y"]),
                int(r["x"]),
                str(r["resource"]),
            )
        )

    dominant_local_signal = "none"
    food_pressure = float((market_state.get("food") or {}).get("pressure", 0.0)) if isinstance(market_state, dict) else 0.0
    wood_pressure = float((market_state.get("wood") or {}).get("pressure", 0.0)) if isinstance(market_state, dict) else 0.0
    stone_pressure = float((market_state.get("stone") or {}).get("pressure", 0.0)) if isinstance(market_state, dict) else 0.0

    if bool(needs.get("food_urgent")) or bool(needs.get("food_buffer_critical")):
        dominant_local_signal = "food_urgent"
    elif food_crisis:
        dominant_local_signal = "food_crisis"
    elif food_pressure >= max(wood_pressure, stone_pressure) and food_pressure >= 0.45:
        dominant_local_signal = "food_scarcity"
    elif int(construction_needs.get("wood", 0)) + int(construction_needs.get("stone", 0)) > 0:
        dominant_local_signal = "construction_pressure"
    elif str(local_signals.get("priority", "")):
        dominant_local_signal = f"priority:{str(local_signals.get('priority', ''))}"

    current_focus = "stabilize"
    if hunger < 35:
        current_focus = "urgent_food"
    elif role == "miner":
        current_focus = "stone_extraction"
    elif role == "woodcutter":
        current_focus = "wood_extraction"
    elif role == "builder":
        current_focus = "construction"
    elif role == "hauler":
        current_focus = "logistics"
    elif dominant_local_signal in {"food_urgent", "food_scarcity"}:
        current_focus = "food_security"
    elif dominant_local_signal == "food_crisis":
        current_focus = "urgent_food"
    elif dominant_local_signal == "construction_pressure":
        current_focus = "construction_support"
    elif (
        explore_w + curiosity * 0.12 + culture_explore * 0.10 > 0.55
        and effective_stress < 0.35
        and not leader_nearby
        and survival_pressure < 0.45
    ):
        current_focus = "exploration"

    return {
        "top_resource_targets": top_resource_targets,
        "top_building_targets": top_building_targets,
        "top_social_targets": top_social_targets,
        "familiar_agents_nearby": familiar_agents_nearby,
        "salient_local_leader": salient_local_leader,
        "dominant_local_signal": dominant_local_signal,
        "current_focus": current_focus,
    }


def _update_short_term_memory(agent: Agent, max_items: int = 12) -> None:
    state = agent.subjective_state if isinstance(agent.subjective_state, dict) else {}
    tick = int(state.get("last_perception_tick", 0))
    attention = state.get("attention", {}) if isinstance(state.get("attention"), dict) else {}
    nearby_resources = state.get("nearby_resources", {})
    recent_resources = []
    salient_resources = []
    for entry in (attention.get("top_resource_targets", []) if isinstance(attention.get("top_resource_targets", []), list) else []):
        if isinstance(entry, dict):
            salient_resources.append(
                {
                    "tick": tick,
                    "resource": str(entry.get("resource", "")),
                    "x": int(entry.get("x", 0)),
                    "y": int(entry.get("y", 0)),
                    "salient": True,
                }
            )
    if isinstance(nearby_resources, dict):
        for resource in ("food", "wood", "stone"):
            entries = nearby_resources.get(resource, [])
            if not isinstance(entries, list):
                continue
            for entry in entries[:2]:
                if isinstance(entry, dict):
                    recent_resources.append(
                        {"tick": tick, "resource": resource, "x": int(entry.get("x", 0)), "y": int(entry.get("y", 0))}
                    )

    recent_agents = []
    for entry in (state.get("nearby_agents", []) if isinstance(state.get("nearby_agents", []), list) else [])[:4]:
        if isinstance(entry, dict):
            recent_agents.append({"tick": tick, "agent_id": str(entry.get("agent_id", "")), "x": int(entry.get("x", 0)), "y": int(entry.get("y", 0))})

    recent_buildings = []
    for entry in (state.get("nearby_buildings", []) if isinstance(state.get("nearby_buildings", []), list) else [])[:4]:
        if isinstance(entry, dict):
            recent_buildings.append(
                {
                    "tick": tick,
                    "building_id": str(entry.get("building_id", "")),
                    "type": str(entry.get("type", "")),
                    "x": int(entry.get("x", 0)),
                    "y": int(entry.get("y", 0)),
                }
            )

    for key, incoming in (
        ("recently_seen_resources", salient_resources + recent_resources),
        ("recently_seen_agents", recent_agents),
        ("recently_seen_buildings", recent_buildings),
    ):
        existing = agent.short_term_memory.get(key, [])
        if not isinstance(existing, list):
            existing = []
        merged = existing + incoming
        agent.short_term_memory[key] = merged[-max_items:]
