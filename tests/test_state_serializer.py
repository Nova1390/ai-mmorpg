from __future__ import annotations

import hashlib
import json

from agent import Agent
from state_serializer import (
    serialize_dynamic_world_state,
    serialize_static_world_state,
)
from world import World


class DummyWorld:
    def __init__(self) -> None:
        self.tick = 12
        self.width = 4
        self.height = 3
        self.tiles = [
            ["G", "W", "G", "F"],
            ["G", "M", "G", "G"],
            ["F", "G", "W", "G"],
        ]
        self.food = {(3, 0), (1, 2), (0, 0)}
        self.wood = {(1, 0), (0, 2)}
        self.stone = {(2, 1), (0, 1)}
        self.farm_plots = {
            (2, 2): {"x": 2, "y": 2, "state": "growing", "growth": 5, "village_id": 2},
            (0, 1): {"x": 0, "y": 1, "state": "prepared", "growth": 0, "village_id": 1},
        }
        self.structures = {(2, 0), (0, 2)}
        self.roads = {(1, 1), (0, 0)}
        self.storage_buildings = {(1, 2)}
        self.buildings = {
            "b-000002": {
                "building_id": "b-000002",
                "type": "storage",
                "category": "food_storage",
                "tier": 1,
                "x": 1,
                "y": 2,
                "footprint": [
                    {"x": 2, "y": 3},
                    {"x": 1, "y": 2},
                    {"x": 2, "y": 2},
                    {"x": 1, "y": 3},
                ],
                "village_id": 1,
                "village_uid": "v-000002",
                "connected_to_road": False,
                "operational_state": "active",
                "linked_resource_type": None,
                "linked_resource_tiles_count": 0,
            },
            "b-000001": {
                "building_id": "b-000001",
                "type": "house",
                "category": "residential",
                "tier": 1,
                "x": 2,
                "y": 0,
                "footprint": [{"x": 2, "y": 0}],
                "village_id": 2,
                "village_uid": "v-000010",
                "connected_to_road": True,
                "operational_state": "active",
                "linked_resource_type": None,
                "linked_resource_tiles_count": 0,
            },
        }
        self.villages = [
            {
                "id": 2,
                "village_uid": "v-000010",
                "center": {"x": 2, "y": 2},
                "houses": 2,
                "population": 3,
                "tiles": [{"x": 3, "y": 2}, {"x": 2, "y": 2}],
                "leader_id": None,
                "strategy": "gather food",
                "color": "#a0522d",
                "relation": "peace",
                "target_village_id": None,
                "migration_target_id": None,
                "power": 4.0,
                "storage": {"food": 2, "wood": 1, "stone": 0},
                "storage_pos": {"x": 2, "y": 2},
                "farm_zone_center": {"x": 3, "y": 2},
                "priority_history": [],
                "leader_profile": None,
                "phase": "bootstrap",
                "needs": {},
                "priority": "stabilize",
                "metrics": {},
            },
            {
                "id": 1,
                "village_uid": "v-000002",
                "center": {"x": 0, "y": 1},
                "houses": 3,
                "population": 4,
                "tiles": [{"x": 1, "y": 1}, {"x": 0, "y": 1}],
                "leader_id": None,
                "strategy": "build house",
                "color": "#8b4513",
                "relation": "peace",
                "target_village_id": None,
                "migration_target_id": None,
                "power": 5.0,
                "storage": {"food": 1, "wood": 2, "stone": 3},
                "storage_pos": {"x": 0, "y": 1},
                "farm_zone_center": {"x": 1, "y": 1},
                "priority_history": [],
                "leader_profile": None,
                "phase": "survival",
                "needs": {},
                "priority": "expand_farms",
                "metrics": {},
            },
        ]
        a1 = Agent(x=2, y=1, brain=None, is_player=False, player_id=None)
        a1.agent_id = "agent-b"
        a1.role = "npc"
        a1.task = "idle"
        a1.village_id = 1

        a2 = Agent(x=0, y=0, brain=None, is_player=True, player_id="p-1")
        a2.agent_id = "agent-a"
        a2.role = "player"
        a2.task = "player_controlled"
        a2.village_id = None

        self.agents = [a1, a2]
        self.llm_interactions = 3
        self._state_version = 0

    def get_civilization_stats(self):
        return {
            "largest_village_id": 1,
            "largest_village_houses": 3,
            "strongest_village_id": 1,
            "strongest_village_power": 5.0,
            "expanding_village_id": 1,
            "warring_villages": 0,
            "migrating_villages": 0,
        }

    def count_leaders(self):
        return 0

    def next_state_version(self):
        self._state_version += 1
        return self._state_version


def test_ordering_is_deterministic() -> None:
    world = DummyWorld()
    world.infrastructure_state = {
        "systems": {
            "logistics": {"enabled": True},
            "transport": {"enabled": True},
            "water": {"enabled": True},
        }
    }
    payload = serialize_dynamic_world_state(world)

    assert [a["agent_id"] for a in payload["agents"]] == ["agent-a", "agent-b"]
    assert [v["village_uid"] for v in payload["villages"]] == ["v-000002", "v-000010"]

    assert [(c["x"], c["y"]) for c in payload["food"]] == [(0, 0), (3, 0), (1, 2)]
    assert [(c["x"], c["y"]) for c in payload["wood"]] == [(1, 0), (0, 2)]
    assert [(c["x"], c["y"]) for c in payload["stone"]] == [(0, 1), (2, 1)]
    assert [(c["x"], c["y"]) for c in payload["structures"]] == [(2, 0), (0, 2)]
    assert [(c["x"], c["y"]) for c in payload["roads"]] == [(0, 0), (1, 1)]
    assert [(c["x"], c["y"]) for c in payload["storage_buildings"]] == [(1, 2)]
    assert [(f["x"], f["y"]) for f in payload["farms"]] == [(0, 1), (2, 2)]
    assert [b["building_id"] for b in payload["buildings"]] == ["b-000001", "b-000002"]
    assert payload["infrastructure_systems_available"] == ["logistics", "transport", "water"]
    assert payload["buildings"][1]["type"] == "storage"
    assert payload["buildings"][1]["category"] == "food_storage"
    assert payload["buildings"][1]["tier"] == 1
    assert payload["buildings"][1]["operational_state"] == "active"
    assert payload["buildings"][1]["linked_resource_type"] is None
    assert payload["buildings"][1]["linked_resource_tiles_count"] == 0
    assert payload["buildings"][1]["footprint"] == [
        {"x": 1, "y": 2},
        {"x": 2, "y": 2},
        {"x": 1, "y": 3},
        {"x": 2, "y": 3},
    ]


def test_village_uid_is_stable_across_detect_cycles() -> None:
    world = World()
    world.agents = []
    world.structures = {
        (10, 10), (10, 11), (11, 10),
        (50, 50), (50, 51), (51, 50),
    }

    world.detect_villages()
    first = {v["id"]: v["village_uid"] for v in world.villages}
    world.detect_villages()
    second = {v["id"]: v["village_uid"] for v in world.villages}

    assert len(first) == len(second)
    assert set(first.values()) == set(second.values())


def test_state_snapshot_regression_on_canonical_world() -> None:
    payload = serialize_dynamic_world_state(DummyWorld())
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    assert digest == "13111925d6fd15d0f73cd2be91085408bdf3893dca3fcc24f273a90d22adfb8e"


def test_static_payload_is_deterministic() -> None:
    world = DummyWorld()
    first = serialize_static_world_state(world)
    second = serialize_static_world_state(world)
    assert first == second
    assert first["static_state_version"] == 1


def test_buildings_legacy_fallback_serialization() -> None:
    class LegacyWorld:
        def __init__(self) -> None:
            self.tick = 0
            self.width = 2
            self.height = 2
            self.tiles = [["G", "G"], ["G", "G"]]
            self.food = set()
            self.wood = set()
            self.stone = set()
            self.farm_plots = {}
            self.structures = {(1, 0)}
            self.storage_buildings = {(0, 1)}
            self.roads = set()
            self.villages = []
            self.agents = []
            self.llm_interactions = 0
            self._state_version = 0

        def get_civilization_stats(self):
            return {
                "largest_village_id": None,
                "largest_village_houses": 0,
                "strongest_village_id": None,
                "strongest_village_power": 0,
                "expanding_village_id": None,
                "warring_villages": 0,
                "migrating_villages": 0,
            }

        def count_leaders(self):
            return 0

        def next_state_version(self):
            self._state_version += 1
            return self._state_version

    payload = serialize_dynamic_world_state(LegacyWorld())
    assert [b["building_id"] for b in payload["buildings"]] == [
        "legacy-house-1-0",
        "legacy-storage-0-1",
    ]
    assert [b["category"] for b in payload["buildings"]] == [
        "residential",
        "food_storage",
    ]
