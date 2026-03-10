from __future__ import annotations

from agent import (
    Agent,
    decay_agent_knowledge_state,
    diffuse_local_knowledge,
    ensure_agent_knowledge_state,
    get_known_camp_spot,
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


def test_local_camp_knowledge_diffusion_and_usage_metrics() -> None:
    world = _flat_world()
    world.tick = 25
    donor = Agent(x=10, y=10, brain=None)
    receiver = Agent(x=11, y=10, brain=None)
    world.agents = [donor, receiver]
    ensure_agent_knowledge_state(donor)["known_camp_spots"] = [
        {
            "type": "camp_spot",
            "subject": "camp",
            "location": {"x": 13, "y": 10},
            "learned_tick": 20,
            "confidence": 0.9,
            "source": "direct",
            "salience": 0.8,
        }
    ]
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
                "social_salience": 1.2,
                "last_seen_tick": 24,
                "recent_interaction": "co_present_success",
            }
        }
    }
    diffuse_local_knowledge(world, receiver)
    camp_spot = get_known_camp_spot(receiver, min_confidence=0.2, world=world)
    snapshot = world.compute_communication_snapshot()
    assert camp_spot == (13, 10)
    assert int(snapshot.get("communication_events", 0)) >= 1
    assert int(snapshot.get("camp_knowledge_shared_count", 0)) >= 1
    assert int(snapshot.get("shared_camp_knowledge_used_count", 0)) >= 1


def test_knowledge_decay_records_stale_expired_counter() -> None:
    world = _flat_world()
    world.tick = 500
    agent = Agent(x=2, y=2, brain=None)
    state = ensure_agent_knowledge_state(agent)
    state["known_resource_spots"] = [
        {
            "type": "resource_spot",
            "subject": "food",
            "location": {"x": 3, "y": 2},
            "learned_tick": 0,
            "confidence": 0.1,
            "source": "social",
            "salience": 0.3,
        }
    ]
    state["known_camp_spots"] = [
        {
            "type": "camp_spot",
            "subject": "camp",
            "location": {"x": 4, "y": 2},
            "learned_tick": 0,
            "confidence": 0.1,
            "source": "social",
            "salience": 0.3,
        }
    ]
    decay_agent_knowledge_state(world, agent)
    snapshot = world.compute_communication_snapshot()
    assert int(snapshot.get("stale_knowledge_expired_count", 0)) >= 2


def test_invalid_social_camp_knowledge_is_removed_and_counted() -> None:
    world = _flat_world()
    world.tick = 20
    world.camps = {}
    agent = Agent(x=10, y=10, brain=None)
    state = ensure_agent_knowledge_state(agent)
    state["known_camp_spots"] = [
        {
            "type": "camp_spot",
            "subject": "camp",
            "location": {"x": 10, "y": 10},
            "learned_tick": 19,
            "confidence": 0.16,
            "source": "social",
            "salience": 0.6,
        }
    ]
    update_agent_knowledge_from_experience(world, agent)
    snapshot = world.compute_communication_snapshot()
    assert len(state["known_camp_spots"]) == 0
    assert int(snapshot.get("invalidated_shared_knowledge_count", 0)) >= 1


def test_stale_social_knowledge_is_rejected_during_diffusion() -> None:
    world = _flat_world()
    world.tick = 400
    donor = Agent(x=10, y=10, brain=None)
    receiver = Agent(x=11, y=10, brain=None)
    world.agents = [donor, receiver]
    ensure_agent_knowledge_state(donor)["known_resource_spots"] = [
        {
            "type": "resource_spot",
            "subject": "food",
            "location": {"x": 12, "y": 10},
            "learned_tick": 10,
            "confidence": 0.9,
            "source": "direct",
            "salience": 0.9,
        }
    ]
    receiver.subjective_state = {
        "nearby_agents": [{"agent_id": donor.agent_id, "distance": 1, "same_village": True, "x": donor.x, "y": donor.y}]
    }
    receiver.social_memory = {"known_agents": {donor.agent_id: {"times_seen": 6, "same_village": True}}}
    diffuse_local_knowledge(world, receiver)
    snapshot = world.compute_communication_snapshot()
    assert get_known_resource_spot(receiver, "food", min_confidence=0.2) is None
    assert int(snapshot.get("social_knowledge_reject_stale", 0)) >= 1


def test_direct_local_food_overrides_weaker_social_hint() -> None:
    world = _flat_world()
    world.tick = 40
    agent = Agent(x=10, y=10, brain=None)
    state = ensure_agent_knowledge_state(agent)
    state["known_resource_spots"] = [
        {
            "type": "resource_spot",
            "subject": "food",
            "location": {"x": 19, "y": 10},
            "learned_tick": 39,
            "confidence": 0.82,
            "source": "social",
            "salience": 0.7,
        }
    ]
    agent.subjective_state = {
        "nearby_resources": {
            "food": [{"x": 11, "y": 10, "distance": 1, "salience": 1.0}],
        }
    }
    target = get_known_resource_spot(agent, "food", world=world)
    snapshot = world.compute_communication_snapshot()
    assert target == (11, 10)
    assert int(snapshot.get("direct_overrides_social_count", 0)) >= 1


def test_near_critical_hunger_rejects_far_social_food_hint() -> None:
    world = _flat_world()
    world.tick = 50
    agent = Agent(x=10, y=10, brain=None)
    agent.hunger = 25.0
    ensure_agent_knowledge_state(agent)["known_resource_spots"] = [
        {
            "type": "resource_spot",
            "subject": "food",
            "location": {"x": 22, "y": 10},
            "learned_tick": 48,
            "confidence": 0.75,
            "source": "social",
            "salience": 0.8,
        }
    ]
    target = get_known_resource_spot(agent, "food", world=world)
    snapshot = world.compute_communication_snapshot()
    assert target is None
    assert int(snapshot.get("social_knowledge_reject_survival_priority", 0)) >= 1


def test_duplicate_resharing_is_suppressed() -> None:
    world = _flat_world()
    world.tick = 60
    donor = Agent(x=10, y=10, brain=None)
    receiver = Agent(x=11, y=10, brain=None)
    world.agents = [donor, receiver]
    ensure_agent_knowledge_state(donor)["known_resource_spots"] = [
        {
            "type": "resource_spot",
            "subject": "food",
            "location": {"x": 12, "y": 10},
            "learned_tick": 59,
            "confidence": 0.95,
            "source": "direct",
            "salience": 0.95,
        }
    ]
    receiver.subjective_state = {
        "nearby_agents": [{"agent_id": donor.agent_id, "distance": 1, "same_village": True, "x": donor.x, "y": donor.y}]
    }
    receiver.social_memory = {"known_agents": {donor.agent_id: {"times_seen": 8, "same_village": True}}}
    diffuse_local_knowledge(world, receiver)
    world.tick += 7
    diffuse_local_knowledge(world, receiver)
    snapshot = world.compute_communication_snapshot()
    assert int(snapshot.get("repeated_duplicate_share_suppressed_count", 0)) >= 1
