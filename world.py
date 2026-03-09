from __future__ import annotations

import random
from typing import Dict, List, Optional, Set, Tuple

from config import (
    WIDTH,
    HEIGHT,
    NUM_AGENTS,
    NUM_FOOD,
    NUM_WOOD,
    NUM_STONE,
    FOOD_RESPAWN_PER_TICK,
    WOOD_RESPAWN_PER_TICK,
    STONE_RESPAWN_PER_TICK,
    MAX_FOOD,
    MAX_WOOD,
    MAX_STONE,
    FOOD_EAT_GAIN,
    MAX_AGENTS,
    HOUSE_WOOD_COST,
    HOUSE_STONE_COST,
    LLM_ENABLED,
    LLM_TIMEOUT_SECONDS,
)

from agent import Agent
from brain import FoodBrain
from worldgen.generator import generate_world
import systems.building_system as building_system
import systems.village_system as village_system
import systems.farming_system as farming_system
import systems.road_system as road_system
import systems.role_system as role_system
import systems.village_ai_system as village_ai_system

Coord = Tuple[int, int]

MAX_STRUCTURES = 60
MAX_HOUSES_PER_VILLAGE = 8
MAX_NEW_VILLAGE_SEEDS = 2
MIN_HOUSES_FOR_VILLAGE = 3
MIN_HOUSES_FOR_LEADER = 3
INITIAL_FOUNDER_QUOTA = 8


class World:
    def __init__(self):
        self.width = int(WIDTH)
        self.height = int(HEIGHT)

        self.tick = 0
        self._state_version = 0
        self.llm_interactions = 0
        self.llm_calls_this_tick = 0
        self.max_llm_calls_per_tick = 1
        self.build_policy_interval = 20
        self.llm_enabled = bool(LLM_ENABLED)
        self.llm_timeout_seconds = float(LLM_TIMEOUT_SECONDS)
        self._village_uid_counter = 0
        self._event_id_counter = 0
        self._building_id_counter = 0
        self.events: List[Dict] = []
        self.max_retained_events = 5000

        self.tiles: List[List[str]] = self._generate_tiles()

        self.food: Set[Coord] = set()
        self.wood: Set[Coord] = set()
        self.stone: Set[Coord] = set()

        self.farms: Set[Coord] = set()
        self.farm_plots: Dict[Coord, Dict] = {}

        self.structures: Set[Coord] = set()
        self.storage_buildings: Set[Coord] = set()
        self.buildings: Dict[str, Dict] = {}
        self.building_occupancy: Dict[Coord, str] = {}
        self.roads: Set[Coord] = set()
        self.transport_tiles: Dict[Coord, str] = {}
        self.road_usage: Dict[Coord, int] = {}
        self.infrastructure_state: Dict[str, Dict] = {
            "systems": {
                system: {"enabled": True}
                for system in sorted(building_system.INFRASTRUCTURE_SYSTEMS)
            },
            "transport": {
                "road_tiles": 0,
                "network_types": ["path", "road", "logistics_corridor", "bridge", "tunnel"],
            },
            "logistics": {
                "network_types": ["storage_link", "haul_route"],
            },
            "water": {"network_types": ["well_network"]},
            "energy": {"network_types": ["power_line"]},
            "communication": {"network_types": ["messenger_route"]},
            "environment": {"network_types": ["drainage"]},
        }

        self.villages: List[Dict] = []
        self.agents: List[Agent] = []

        self.MAX_STRUCTURES = MAX_STRUCTURES
        self.MAX_HOUSES_PER_VILLAGE = MAX_HOUSES_PER_VILLAGE
        self.MAX_NEW_VILLAGE_SEEDS = MAX_NEW_VILLAGE_SEEDS
        self.MIN_HOUSES_FOR_VILLAGE = MIN_HOUSES_FOR_VILLAGE
        self.MIN_HOUSES_FOR_LEADER = MIN_HOUSES_FOR_LEADER
        self.INITIAL_FOUNDER_QUOTA = INITIAL_FOUNDER_QUOTA
        self.founders_assigned = 0
        self.founding_hub: Optional[Coord] = None

        self.MAX_FOOD = MAX_FOOD
        self.MAX_WOOD = MAX_WOOD
        self.MAX_STONE = MAX_STONE

        self._spawn_initial_food(NUM_FOOD)
        self._spawn_initial_wood(NUM_WOOD)
        self._spawn_initial_stone(NUM_STONE)

        if NUM_AGENTS > 0:
            brain = FoodBrain()
            for _ in range(NUM_AGENTS):
                pos = self.find_random_free()
                if pos:
                    x, y = pos
                    self.add_agent(Agent(x, y, brain, False, None))

        self.detect_villages()
        self.update_village_ai()
        self.assign_village_roles()
        self.sync_infrastructure_state()

    def record_llm_interaction(self) -> None:
        self.llm_interactions += 1

    def next_state_version(self) -> int:
        self._state_version += 1
        return self._state_version

    def new_village_uid(self) -> str:
        self._village_uid_counter += 1
        return f"v-{self._village_uid_counter:06d}"

    def _next_event_id(self) -> str:
        self._event_id_counter += 1
        return f"e-{self._event_id_counter:06d}"

    def new_building_id(self) -> str:
        self._building_id_counter += 1
        return f"b-{self._building_id_counter:06d}"

    def resolve_village_uid(self, village_id: Optional[int]) -> Optional[str]:
        village = self.get_village_by_id(village_id)
        if village is None:
            return None
        uid = village.get("village_uid")
        if uid is None:
            return None
        return str(uid)

    def emit_event(self, event_type: str, payload: Dict) -> Dict:
        event = {
            "event_id": self._next_event_id(),
            "tick": int(self.tick),
            "event_type": str(event_type),
            "payload": payload if isinstance(payload, dict) else {},
        }
        self.events.append(event)
        # Bounded in-memory retention to prevent unbounded growth.
        if self.max_retained_events > 0 and len(self.events) > self.max_retained_events:
            overflow = len(self.events) - self.max_retained_events
            del self.events[:overflow]
        return event

    def get_events_since(self, since_tick: int = -1) -> List[Dict]:
        cutoff = int(since_tick)
        return [e for e in self.events if int(e.get("tick", -1)) > cutoff]

    def set_agent_role(self, agent: Agent, new_role: str, reason: str = "") -> None:
        old_role = getattr(agent, "role", "npc")
        if old_role == new_role:
            agent.role = new_role
            return
        agent.role = new_role
        self.emit_event(
            "role_changed",
            {
                "agent_id": agent.agent_id,
                "from_role": old_role,
                "to_role": new_role,
                "reason": reason,
                "village_uid": self.resolve_village_uid(getattr(agent, "village_id", None)),
            },
        )

    def set_agent_dead(self, agent: Agent, reason: str = "unknown") -> None:
        if not agent.alive:
            return
        agent.alive = False
        self.emit_event(
            "agent_died",
            {
                "agent_id": agent.agent_id,
                "is_player": bool(agent.is_player),
                "reason": reason,
                "village_uid": self.resolve_village_uid(getattr(agent, "village_id", None)),
            },
        )

    def get_village_by_id(self, village_id: Optional[int]) -> Optional[Dict]:
        return village_system.get_village_by_id(self, village_id)

    def count_leaders(self) -> int:
        return village_system.count_leaders(self)

    def get_civilization_stats(self) -> Dict:
        return village_system.get_civilization_stats(self)

    def record_road_step(self, x: int, y: int) -> None:
        road_system.record_agent_step(self, x, y)

    def update_road_infrastructure(self) -> None:
        road_system.update_road_infrastructure(self)
        self.sync_infrastructure_state()

    def sync_infrastructure_state(self) -> None:
        transport_state = self.infrastructure_state.setdefault("transport", {})
        transport_state["road_tiles"] = int(len(self.roads))
        tile_counts: Dict[str, int] = {}
        for t in self.transport_tiles.values():
            tile_counts[t] = int(tile_counts.get(t, 0)) + 1
        transport_state["tile_counts"] = {k: tile_counts[k] for k in sorted(tile_counts.keys())}
        road_meta = building_system.get_infrastructure_metadata("road")
        if isinstance(road_meta, dict):
            transport_state["road_infrastructure_type"] = str(road_meta.get("type", "road"))
            transport_state["network_type"] = str(road_meta.get("network_type", "tile_network"))

    def update_village_ai(self) -> None:
        village_ai_system.update_village_ai(self)

    def assign_village_roles(self) -> None:
        role_system.assign_village_roles(self)

    def _generate_tiles(self) -> List[List[str]]:
        return generate_world(self.width, self.height)

    def is_walkable(self, x: int, y: int) -> bool:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return False
        terrain = str(self.tiles[y][x])
        transport_type = self.get_transport_type(x, y)
        if terrain == "W":
            return transport_type == "bridge"
        if terrain == "X":
            return transport_type == "tunnel"
        return True

    def is_occupied(self, x: int, y: int) -> bool:
        for a in self.agents:
            if a.alive and a.x == x and a.y == y:
                return True
        return False

    def movement_cost(self, x: int, y: int) -> float:
        terrain = str(self.tiles[y][x]) if 0 <= x < self.width and 0 <= y < self.height else "G"
        base_costs = {
            "G": 1.0,
            "F": 1.0,
            "M": 1.2,
            "W": 1.4,
            "X": 1.6,
        }
        base_cost = float(base_costs.get(terrain, 1.0))
        transport_type = self.get_transport_type(x, y)
        if transport_type is None:
            return base_cost
        transport_meta = building_system.get_infrastructure_metadata(transport_type) or {}
        modifier = float(transport_meta.get("movement_modifier", 1.0) or 1.0)
        return max(0.05, base_cost * modifier)

    def get_transport_type(self, x: int, y: int) -> Optional[str]:
        pos = (x, y)
        transport_type = self.transport_tiles.get(pos)
        if transport_type is not None:
            return str(transport_type)
        if pos in self.roads:
            return "road"
        return None

    def set_transport_type(self, x: int, y: int, transport_type: Optional[str]) -> None:
        pos = (x, y)
        if transport_type is None:
            self.transport_tiles.pop(pos, None)
            self.roads.discard(pos)
            return
        t = str(transport_type)
        self.transport_tiles[pos] = t
        if t in {"road", "logistics_corridor", "bridge", "tunnel"}:
            self.roads.add(pos)
        else:
            self.roads.discard(pos)

    def get_transport_tiles(self) -> Dict[Coord, str]:
        tiles: Dict[Coord, str] = {}
        for pos in self.roads:
            tiles[pos] = "road"
        for pos, t in self.transport_tiles.items():
            tiles[pos] = str(t)
        return tiles

    def minimum_step_cost(self) -> float:
        # Lower bound for A* heuristic with current transport hierarchy.
        return 0.35

    def is_tile_blocked_by_building(self, x: int, y: int) -> bool:
        pos = (x, y)
        if pos in self.building_occupancy:
            return True
        if pos in self.structures:
            return True
        if pos in self.storage_buildings:
            return True
        return False

    def get_building_occupied_tiles(self) -> Set[Coord]:
        if self.building_occupancy:
            return set(self.building_occupancy.keys())
        return set(self.structures) | set(self.storage_buildings)

    def add_agent(self, agent: Agent):
        if (
            getattr(agent, "brain", None) is not None
            and
            not agent.is_player
            and getattr(agent, "village_id", None) is None
            and not getattr(agent, "founder", False)
            and self.founders_assigned < self.INITIAL_FOUNDER_QUOTA
            and self.tick < 300
            and len(self.structures) < self.MIN_HOUSES_FOR_VILLAGE
        ):
            agent.founder = True
            self.founders_assigned += 1
            if self.founding_hub is None:
                self.founding_hub = (agent.x, agent.y)
            agent.task_target = self.founding_hub
            # Minimal starter kit so founders can reliably place early houses.
            agent.max_inventory = max(int(getattr(agent, "max_inventory", 5)), HOUSE_WOOD_COST + HOUSE_STONE_COST)
            agent.inventory["wood"] = max(agent.inventory.get("wood", 0), HOUSE_WOOD_COST)
            agent.inventory["stone"] = max(agent.inventory.get("stone", 0), HOUSE_STONE_COST)

        self.agents.append(agent)
        self.emit_event(
            "agent_born",
            {
                "agent_id": agent.agent_id,
                "is_player": bool(agent.is_player),
                "player_id": agent.player_id,
                "village_uid": self.resolve_village_uid(getattr(agent, "village_id", None)),
            },
        )

    def find_random_free(self) -> Optional[Coord]:
        for _ in range(2000):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)

            if self.is_walkable(x, y) and not self.is_occupied(x, y):
                return (x, y)

        return None

    def find_free_adjacent(self, x: int, y: int) -> Optional[Coord]:
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        random.shuffle(dirs)

        for dx, dy in dirs:
            nx = x + dx
            ny = y + dy

            if self.is_walkable(nx, ny) and not self.is_occupied(nx, ny):
                return (nx, ny)

        return None

    def _spawn_initial_food(self, n: int):
        added = 0

        # preferisci pianure vicino all'acqua
        for _ in range(n * 4):
            if added >= n:
                break

            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)

            if self.tiles[y][x] != "G":
                continue

            near_water = False
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    nx = x + dx
                    ny = y + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        if self.tiles[ny][nx] == "W":
                            near_water = True
                            break
                if near_water:
                    break

            if near_water and (x, y) not in self.food:
                self.food.add((x, y))
                added += 1

        # fallback per riempire il resto
        while added < n:
            pos = self.find_random_free()
            if pos and pos not in self.food:
                self.food.add(pos)
                added += 1

    def _spawn_initial_wood(self, n: int):
        added = 0
        for _ in range(n):
            for _ in range(120):
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)
                if self.tiles[y][x] == "F" and (x, y) not in self.wood:
                    self.wood.add((x, y))
                    added += 1
                    break

        # fallback leggero se il worldgen ha poche foreste accessibili
        while added < n:
            pos = self.find_random_free()
            if pos and pos not in self.wood:
                x, y = pos
                if self.tiles[y][x] != "W":
                    self.wood.add(pos)
                    added += 1

    def _spawn_initial_stone(self, n: int):
        added = 0
        for _ in range(n):
            for _ in range(120):
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)
                if self.tiles[y][x] == "M" and (x, y) not in self.stone:
                    self.stone.add((x, y))
                    added += 1
                    break

        # fallback leggero se ci sono poche montagne accessibili
        while added < n:
            pos = self.find_random_free()
            if pos and pos not in self.stone:
                x, y = pos
                if self.tiles[y][x] != "W":
                    self.stone.add(pos)
                    added += 1

    def respawn_resources(self):
        if len(self.food) < MAX_FOOD:
            for _ in range(FOOD_RESPAWN_PER_TICK):
                # preferisci ancora pianure libere
                placed = False
                for _ in range(40):
                    x = random.randint(0, self.width - 1)
                    y = random.randint(0, self.height - 1)
                    if self.tiles[y][x] == "G" and (x, y) not in self.food and not self.is_occupied(x, y):
                        self.food.add((x, y))
                        placed = True
                        break

                if not placed:
                    pos = self.find_random_free()
                    if pos:
                        self.food.add(pos)

        if len(self.wood) < MAX_WOOD:
            for _ in range(WOOD_RESPAWN_PER_TICK):
                for _ in range(80):
                    x = random.randint(0, self.width - 1)
                    y = random.randint(0, self.height - 1)
                    if self.tiles[y][x] == "F":
                        self.wood.add((x, y))
                        break

        if len(self.stone) < MAX_STONE:
            for _ in range(STONE_RESPAWN_PER_TICK):
                for _ in range(80):
                    x = random.randint(0, self.width - 1)
                    y = random.randint(0, self.height - 1)
                    if self.tiles[y][x] == "M":
                        self.stone.add((x, y))
                        break

    def autopickup(self, agent: Agent):
        pos = (agent.x, agent.y)

        if pos in self.food:
            self.food.remove(pos)
            if agent.inventory_space() > 0:
                agent.inventory["food"] = agent.inventory.get("food", 0) + 1
            agent.hunger += FOOD_EAT_GAIN
            if agent.hunger > 100:
                agent.hunger = 100
            self.emit_event(
                "resource_harvested",
                {
                    "agent_id": agent.agent_id,
                    "resource": "food",
                    "amount": 1,
                    "source": "wild_food",
                    "x": agent.x,
                    "y": agent.y,
                    "village_uid": self.resolve_village_uid(getattr(agent, "village_id", None)),
                },
            )

    def gather_resource(self, agent: Agent):
        pos = (agent.x, agent.y)
        village = self.get_village_by_id(getattr(agent, "village_id", None))
        if agent.inventory_space() <= 0:
            return False

        if pos in self.wood:
            self.wood.remove(pos)
            bonus, source = building_system.production_bonus_details_for_resource(self, village, "wood", pos)
            amount = min(1 + bonus, max(0, agent.inventory_space()))
            if amount <= 0:
                return False
            agent.inventory["wood"] = agent.inventory.get("wood", 0) + amount
            building_system.record_village_resource_gather(
                village,
                "wood",
                amount=amount,
                bonus_amount=bonus,
                production_source=source,
            )
            self.emit_event(
                "resource_harvested",
                {
                    "agent_id": agent.agent_id,
                    "resource": "wood",
                    "amount": amount,
                    "source": "wild",
                    "x": agent.x,
                    "y": agent.y,
                    "village_uid": self.resolve_village_uid(getattr(agent, "village_id", None)),
                },
            )
            return True

        if pos in self.stone:
            self.stone.remove(pos)
            bonus, source = building_system.production_bonus_details_for_resource(self, village, "stone", pos)
            amount = min(1 + bonus, max(0, agent.inventory_space()))
            if amount <= 0:
                return False
            agent.inventory["stone"] = agent.inventory.get("stone", 0) + amount
            building_system.record_village_resource_gather(
                village,
                "stone",
                amount=amount,
                bonus_amount=bonus,
                production_source=source,
            )
            self.emit_event(
                "resource_harvested",
                {
                    "agent_id": agent.agent_id,
                    "resource": "stone",
                    "amount": amount,
                    "source": "wild",
                    "x": agent.x,
                    "y": agent.y,
                    "village_uid": self.resolve_village_uid(getattr(agent, "village_id", None)),
                },
            )
            return True

        return False

    def building_score(self, x: int, y: int) -> int:
        return building_system.building_score(self, x, y)

    def count_nearby_houses(self, x: int, y: int, radius: int = 5) -> int:
        return building_system.count_nearby_houses(self, x, y, radius)

    def count_nearby_population(self, x: int, y: int, radius: int = 6) -> int:
        return building_system.count_nearby_population(self, x, y, radius)

    def can_build_at(self, x: int, y: int) -> bool:
        return building_system.can_build_at(self, x, y)

    def can_place_building(self, building_type: str, x: int, y: int) -> bool:
        return building_system.can_place_building(self, building_type, (x, y))

    def place_building(
        self,
        building_type: str,
        x: int,
        y: int,
        *,
        village_id: Optional[int] = None,
        village_uid: Optional[str] = None,
        connected_to_road: bool = False,
    ) -> Optional[Dict]:
        return building_system.place_building(
            self,
            building_type,
            (x, y),
            village_id=village_id,
            village_uid=village_uid,
            connected_to_road=connected_to_road,
        )

    def try_build_house(self, agent: Agent):
        return building_system.try_build_house(self, agent)

    def try_build_storage(self, agent: Agent):
        return building_system.try_build_storage(self, agent)

    def try_build_type(
        self,
        agent: Agent,
        building_type: str,
        village_id: Optional[int] = None,
        village_uid: Optional[str] = None,
    ) -> Dict:
        return building_system.try_build_type(
            self,
            agent,
            building_type,
            village_id=village_id,
            village_uid=village_uid,
        )

    def try_build_farm(self, agent: Agent):
        return farming_system.try_build_farm(self, agent)

    def work_farm(self, agent: Agent):
        return farming_system.work_farm(self, agent)

    def haul_harvest(self, agent: Agent):
        return farming_system.haul_harvest(self, agent)

    def detect_villages(self):
        village_system.detect_villages(self)

    def assign_village_leaders(self):
        village_system.assign_village_leaders(self)

    def update_village_politics(self):
        village_system.update_village_politics(self)

    def update(self):
        self.tick += 1
        self.llm_calls_this_tick = 0

        self.respawn_resources()
        farming_system.update_farms(self)

        for agent in list(self.agents):
            if not agent.alive:
                continue
            agent.update(self)

        self.agents = [a for a in self.agents if a.alive]

        if len(self.agents) > MAX_AGENTS:
            extra = len(self.agents) - MAX_AGENTS

            for a in self.agents:
                if extra <= 0:
                    break
                if not a.is_player:
                    self.set_agent_dead(a, reason="population_cap")
                    extra -= 1

            self.agents = [a for a in self.agents if a.alive]

        self.detect_villages()
        self.update_village_ai()
        if self.build_policy_interval > 0 and self.tick % self.build_policy_interval == 0:
            building_system.run_village_build_policy(self)
        self.assign_village_roles()
        self.update_road_infrastructure()
