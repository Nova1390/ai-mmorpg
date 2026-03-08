from __future__ import annotations

import json
from pathlib import Path

from agent import Agent
from jsonschema import validate
import server
from world import World

ROOT = Path(__file__).resolve().parents[1]
EVENTS_SCHEMA_PATH = ROOT / "docs" / "state_events_schema.json"


def test_event_buffer_emits_birth_role_change_and_death() -> None:
    world = World()
    world.events = []

    agent = Agent(x=1, y=1, brain=None, is_player=False, player_id=None)
    world.add_agent(agent)
    world.set_agent_role(agent, "farmer", reason="test_assignment")
    world.set_agent_dead(agent, reason="test_death")

    event_types = [e["event_type"] for e in world.events]
    assert event_types == ["agent_born", "role_changed", "agent_died"]

    born = world.events[0]
    assert born["payload"]["agent_id"] == agent.agent_id


def test_resource_harvested_event_is_emitted() -> None:
    world = World()
    world.events = []

    agent = Agent(x=3, y=3, brain=None, is_player=False, player_id=None)
    world.add_agent(agent)
    world.wood.add((3, 3))

    assert world.gather_resource(agent) is True
    assert any(e["event_type"] == "resource_harvested" for e in world.events)


def test_village_created_event_is_emitted() -> None:
    world = World()
    world.events = []
    world.agents = []
    world.structures = {(10, 10), (10, 11), (11, 10)}

    world.detect_villages()

    created = [e for e in world.events if e["event_type"] == "village_created"]
    assert len(created) == 1
    assert created[0]["payload"]["village_uid"].startswith("v-")


def test_events_filter_and_endpoint_are_deterministic_and_json_safe() -> None:
    world = World()
    world.events = []
    world.tick = 1
    world.emit_event("x", {"n": 1})
    world.tick = 2
    world.emit_event("y", {"n": 2})
    world.tick = 3
    world.emit_event("z", {"n": 3})

    all_events = world.get_events_since(-1)
    assert [e["event_id"] for e in all_events] == ["e-000001", "e-000002", "e-000003"]
    assert [e["event_type"] for e in world.get_events_since(1)] == ["y", "z"]

    original_world = server.world
    try:
        server.world = world
        response = server.get_events(since_tick=1)
    finally:
        server.world = original_world

    assert response["schema_version"] == "1.1.0"
    assert [e["event_type"] for e in response["events"]] == ["y", "z"]
    assert response["oldest_retained_tick"] == 1
    assert response["newest_retained_tick"] == 3
    assert response["retained_event_count"] == 3
    json.dumps(response)


def test_event_retention_trims_oldest_events_and_keeps_order() -> None:
    world = World()
    world.events = []
    world.max_retained_events = 3

    for tick in range(1, 6):
        world.tick = tick
        world.emit_event("sample", {"tick": tick})

    assert len(world.events) == 3
    assert [e["tick"] for e in world.events] == [3, 4, 5]
    assert [e["event_id"] for e in world.events] == ["e-000003", "e-000004", "e-000005"]


def test_events_since_tick_before_retained_history_returns_retained_subset() -> None:
    world = World()
    world.events = []
    world.max_retained_events = 2

    for tick in range(1, 5):
        world.tick = tick
        world.emit_event("t", {"tick": tick})

    # Retained history only includes ticks 3 and 4.
    filtered = world.get_events_since(0)
    assert [e["tick"] for e in filtered] == [3, 4]

    original_world = server.world
    try:
        server.world = world
        response = server.get_events(since_tick=0)
    finally:
        server.world = original_world

    assert [e["tick"] for e in response["events"]] == [3, 4]
    assert response["oldest_retained_tick"] == 3
    assert response["newest_retained_tick"] == 4
    assert response["retained_event_count"] == 2


def test_events_endpoint_payload_validates_against_events_schema() -> None:
    world = World()
    world.events = []
    world.max_retained_events = 10
    world.tick = 2
    world.emit_event("agent_born", {"agent_id": "agent-1"})
    world.tick = 3
    world.emit_event("role_changed", {"agent_id": "agent-1", "to_role": "leader"})

    original_world = server.world
    try:
        server.world = world
        payload = server.get_events(since_tick=-1)
    finally:
        server.world = original_world

    schema = json.loads(EVENTS_SCHEMA_PATH.read_text(encoding="utf-8"))
    validate(instance=payload, schema=schema)
