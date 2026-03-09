from __future__ import annotations

from agent import (
    Agent,
    decay_agent_knowledge_state,
    diffuse_local_knowledge,
    ensure_agent_knowledge_state,
    get_known_resource_spot,
    update_agent_knowledge_from_experience,
    write_episodic_memory_event,
)
from brain import FoodBrain
from world import World


def _flat_world() -> World:
    world = World()
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    world.agents = []
    world.villages = []
    world.buildings = {}
    world.structures = set()
    world.storage_buildings = set()
    world.food = set()
    world.wood = set()
    world.stone = set()
    world.roads = set()
    world.transport_tiles = {}
    return world


def test_direct_success_creates_knowledge_entries() -> None:
    world = _flat_world()
    agent = Agent(x=10, y=10, brain=None)
    world.tick = 10
    write_episodic_memory_event(
        agent,
        tick=world.tick,
        event_type="found_resource",
        outcome="success",
        location=(12, 10),
        resource_type="food",
        salience=1.2,
    )
    update_agent_knowledge_from_experience(world, agent)
    state = ensure_agent_knowledge_state(agent)
    spots = state["known_resource_spots"]
    assert any(str(e.get("subject")) == "food" for e in spots if isinstance(e, dict))


def test_social_diffusion_occurs_only_locally() -> None:
    world = _flat_world()
    donor = Agent(x=10, y=10, brain=None)
    donor.village_id = 1
    receiver_near = Agent(x=11, y=10, brain=None)
    receiver_near.village_id = 1
    receiver_far = Agent(x=25, y=25, brain=None)
    receiver_far.village_id = 1
    world.agents = [donor, receiver_near, receiver_far]

    ensure_agent_knowledge_state(donor)["known_resource_spots"] = [
        {
            "type": "resource_spot",
            "subject": "food",
            "location": {"x": 12, "y": 10},
            "learned_tick": 1,
            "confidence": 0.9,
            "source": "direct",
            "salience": 0.9,
        }
    ]
    receiver_near.subjective_state = {
        "nearby_agents": [
            {
                "agent_id": donor.agent_id,
                "x": donor.x,
                "y": donor.y,
                "distance": 1,
                "same_village": True,
                "role": donor.role,
                "social_influence": 0.7,
            }
        ]
    }
    receiver_far.subjective_state = {"nearby_agents": []}
    receiver_near.social_memory = {
        "known_agents": {
            donor.agent_id: {
                "times_seen": 4,
                "same_village": True,
                "social_salience": 1.2,
                "last_seen_tick": 0,
                "recent_interaction": "seen",
            }
        }
    }
    diffuse_local_knowledge(world, receiver_near)
    diffuse_local_knowledge(world, receiver_far)
    near_spot = get_known_resource_spot(receiver_near, "food", min_confidence=0.2)
    far_spot = get_known_resource_spot(receiver_far, "food", min_confidence=0.2)
    assert near_spot == (12, 10)
    assert far_spot is None


def test_social_knowledge_confidence_lower_than_direct() -> None:
    world = _flat_world()
    donor = Agent(x=10, y=10, brain=None)
    receiver = Agent(x=11, y=10, brain=None)
    world.agents = [donor, receiver]
    donor_entry = {
        "type": "resource_spot",
        "subject": "stone",
        "location": {"x": 9, "y": 10},
        "learned_tick": 1,
        "confidence": 0.95,
        "source": "direct",
        "salience": 0.9,
    }
    ensure_agent_knowledge_state(donor)["known_resource_spots"] = [donor_entry]
    receiver.subjective_state = {
        "nearby_agents": [
            {
                "agent_id": donor.agent_id,
                "distance": 1,
                "same_village": True,
                "social_influence": 0.8,
                "role": donor.role,
                "x": donor.x,
                "y": donor.y,
            }
        ]
    }
    receiver.social_memory = {
        "known_agents": {
            donor.agent_id: {
                "times_seen": 6,
                "same_village": True,
                "social_salience": 1.5,
                "last_seen_tick": 0,
                "recent_interaction": "co_present_success",
            }
        }
    }
    diffuse_local_knowledge(world, receiver)
    received = ensure_agent_knowledge_state(receiver)["known_resource_spots"][0]
    assert float(received["confidence"]) < float(donor_entry["confidence"])
    assert str(received["source"]) == "social"


def test_repeated_confirmation_increases_confidence() -> None:
    world = _flat_world()
    agent = Agent(x=10, y=10, brain=None)
    world.tick = 5
    write_episodic_memory_event(
        agent,
        tick=world.tick,
        event_type="found_resource",
        outcome="success",
        location=(13, 10),
        resource_type="wood",
        salience=1.0,
    )
    update_agent_knowledge_from_experience(world, agent)
    first = float(ensure_agent_knowledge_state(agent)["known_resource_spots"][0]["confidence"])
    world.tick = 6
    write_episodic_memory_event(
        agent,
        tick=world.tick,
        event_type="found_resource",
        outcome="success",
        location=(13, 10),
        resource_type="wood",
        salience=1.0,
    )
    update_agent_knowledge_from_experience(world, agent)
    second = float(ensure_agent_knowledge_state(agent)["known_resource_spots"][0]["confidence"])
    assert second >= first


def test_stale_low_confidence_entries_decay_and_trim() -> None:
    world = _flat_world()
    agent = Agent(x=1, y=1, brain=None)
    state = ensure_agent_knowledge_state(agent)
    state["known_resource_spots"] = [
        {
            "type": "resource_spot",
            "subject": "food",
            "location": {"x": 2, "y": 2},
            "learned_tick": 0,
            "confidence": 0.2,
            "source": "social",
            "salience": 0.4,
        },
        {
            "type": "resource_spot",
            "subject": "wood",
            "location": {"x": 3, "y": 3},
            "learned_tick": 0,
            "confidence": 0.1,
            "source": "social",
            "salience": 0.3,
        },
    ]
    world.tick = 400
    decay_agent_knowledge_state(world, agent)
    kept = state["known_resource_spots"]
    assert all(float(e["confidence"]) >= 0.15 for e in kept)
    assert len(kept) <= 1


def test_find_nearest_uses_known_spot_bias() -> None:
    world = _flat_world()
    brain = FoodBrain()
    agent = Agent(x=10, y=10, brain=brain)
    state = ensure_agent_knowledge_state(agent)
    state["known_resource_spots"] = [
        {
            "type": "resource_spot",
            "subject": "food",
            "location": {"x": 12, "y": 10},
            "learned_tick": 1,
            "confidence": 0.8,
            "source": "direct",
            "salience": 0.8,
        }
    ]
    target = brain.find_nearest(agent, set(), "food", radius=5)
    assert target == (12, 10)


def test_no_omniscient_leakage_from_distant_unseen_agent() -> None:
    world = _flat_world()
    donor = Agent(x=30, y=30, brain=None)
    receiver = Agent(x=5, y=5, brain=None)
    world.agents = [donor, receiver]
    ensure_agent_knowledge_state(donor)["known_resource_spots"] = [
        {
            "type": "resource_spot",
            "subject": "food",
            "location": {"x": 31, "y": 30},
            "learned_tick": 1,
            "confidence": 0.9,
            "source": "direct",
            "salience": 0.9,
        }
    ]
    receiver.subjective_state = {"nearby_agents": []}
    diffuse_local_knowledge(world, receiver)
    assert get_known_resource_spot(receiver, "food", min_confidence=0.2) is None
