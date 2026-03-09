from __future__ import annotations

from agent import (
    Agent,
    find_recent_building_memory,
    find_recent_resource_memory,
    get_recent_memory_events,
    write_episodic_memory_event,
)
from brain import FoodBrain


def test_meaningful_events_are_written() -> None:
    agent = Agent(x=5, y=5, brain=None)
    write_episodic_memory_event(
        agent,
        tick=10,
        event_type="found_resource",
        outcome="success",
        location=(6, 5),
        resource_type="food",
        salience=1.4,
    )
    events = get_recent_memory_events(agent)
    assert len(events) == 1
    assert events[0]["type"] == "found_resource"
    assert events[0]["resource_type"] == "food"


def test_episodic_memory_is_bounded() -> None:
    agent = Agent(x=1, y=1, brain=None)
    for i in range(60):
        write_episodic_memory_event(
            agent,
            tick=i,
            event_type="failed_resource_search",
            outcome="failure",
            location=(i, i),
            resource_type="wood",
            max_events=20,
        )
    events = get_recent_memory_events(agent)
    assert len(events) == 20
    assert int(events[0]["tick"]) == 40
    assert int(events[-1]["tick"]) == 59


def test_memory_queries_are_deterministic() -> None:
    agent = Agent(x=2, y=2, brain=None)
    write_episodic_memory_event(agent, tick=1, event_type="useful_building", outcome="success", target_id="b-1", building_type="storage")
    write_episodic_memory_event(agent, tick=2, event_type="found_resource", outcome="success", resource_type="stone", location=(3, 2))
    write_episodic_memory_event(agent, tick=3, event_type="found_resource", outcome="failure", resource_type="wood", location=(4, 2))
    first = find_recent_resource_memory(agent, "stone")
    second = find_recent_resource_memory(agent, "stone")
    assert first == second
    bfirst = find_recent_building_memory(agent, target_id="b-1")
    bsecond = find_recent_building_memory(agent, target_id="b-1")
    assert bfirst == bsecond


def test_recent_success_can_bias_choice() -> None:
    brain = FoodBrain()
    agent = Agent(x=10, y=10, brain=brain)
    write_episodic_memory_event(
        agent,
        tick=5,
        event_type="found_resource",
        outcome="success",
        location=(12, 10),
        resource_type="food",
        salience=1.8,
    )
    target = brain.find_nearest(agent, set(), "food", radius=5)
    assert target == (12, 10)


def test_recent_failure_can_reduce_immediate_retry() -> None:
    brain = FoodBrain()
    agent = Agent(x=10, y=10, brain=brain)
    agent.subjective_state = {"last_perception_tick": 20}
    write_episodic_memory_event(
        agent,
        tick=19,
        event_type="failed_resource_search",
        outcome="failure",
        location=(10, 10),
        resource_type="wood",
        salience=1.6,
    )
    # Even if a nearby target exists in the set, immediate retry is deprioritized.
    target = brain.find_nearest(agent, {(11, 10)}, "wood", radius=5)
    assert target is None


def test_no_omniscient_leakage_in_memory_events() -> None:
    agent = Agent(x=0, y=0, brain=None)
    event = write_episodic_memory_event(
        agent,
        tick=1,
        event_type="construction_progress",
        outcome="success",
        location=(1, 0),
        target_id="b-123",
        salience=1.1,
    )
    forbidden = {"world_food", "all_buildings", "global_state"}
    assert forbidden.isdisjoint(set(event.keys()))
