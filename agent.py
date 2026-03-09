from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple
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
