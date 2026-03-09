from __future__ import annotations

from agent import (
    Agent,
    detect_local_leader,
    evaluate_agent_social_influence,
    write_episodic_memory_event,
)
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


def test_social_influence_is_deterministic_and_bounded() -> None:
    world = _flat_world()
    world.tick = 20
    a1 = Agent(x=10, y=10, brain=None)
    a2 = Agent(x=10, y=10, brain=None)
    a1.role = "hauler"
    a2.role = "hauler"
    a1.social_memory = {
        "known_agents": {
            "peer": {
                "last_seen_tick": 18,
                "times_seen": 4,
                "same_village": True,
                "role": "builder",
                "recent_interaction": "co_present_success",
                "social_salience": 1.8,
            }
        }
    }
    a2.social_memory = {
        "known_agents": {
            "peer": {
                "last_seen_tick": 18,
                "times_seen": 4,
                "same_village": True,
                "role": "builder",
                "recent_interaction": "co_present_success",
                "social_salience": 1.8,
            }
        }
    }
    a1.subjective_state = {"nearby_agents": [{"agent_id": "peer", "distance": 1}]}
    a2.subjective_state = {"nearby_agents": [{"agent_id": "peer", "distance": 1}]}
    s1 = evaluate_agent_social_influence(world, a1)
    s2 = evaluate_agent_social_influence(world, a2)
    assert s1 == s2
    assert 0.0 <= s1 <= 1.0


def test_detect_local_leader_selects_highest_influence() -> None:
    agent = Agent(x=5, y=5, brain=None)
    agent.subjective_state = {
        "radius": {"social": 8},
        "nearby_agents": [
            {"agent_id": "a-2", "x": 6, "y": 5, "distance": 1, "social_influence": 0.70, "role": "npc", "same_village": True},
            {"agent_id": "a-1", "x": 5, "y": 6, "distance": 1, "social_influence": 0.80, "role": "leader", "same_village": True},
        ],
    }
    leader = detect_local_leader(agent)
    assert isinstance(leader, dict)
    assert leader["agent_id"] == "a-1"


def test_detect_local_leader_tie_breaks_by_agent_id() -> None:
    agent = Agent(x=5, y=5, brain=None)
    agent.subjective_state = {
        "radius": {"social": 8},
        "nearby_agents": [
            {"agent_id": "b-2", "x": 6, "y": 5, "distance": 1, "social_influence": 0.76, "role": "npc", "same_village": True},
            {"agent_id": "a-1", "x": 5, "y": 6, "distance": 1, "social_influence": 0.76, "role": "npc", "same_village": True},
        ],
    }
    leader = detect_local_leader(agent)
    assert isinstance(leader, dict)
    assert leader["agent_id"] == "a-1"


def test_co_present_success_increases_social_influence() -> None:
    world = _flat_world()
    world.tick = 10
    actor = Agent(x=10, y=10, brain=None)
    peer = Agent(x=11, y=10, brain=None)
    actor.subjective_state = {
        "nearby_agents": [
            {"agent_id": peer.agent_id, "role": "builder", "same_village": True, "x": 11, "y": 10, "distance": 1}
        ]
    }

    before = evaluate_agent_social_influence(world, actor)
    write_episodic_memory_event(
        actor,
        tick=world.tick,
        event_type="delivered_material",
        outcome="success",
        location=(10, 10),
        salience=1.2,
    )
    world.tick = 12
    after = evaluate_agent_social_influence(world, actor)
    assert after > before
    recent = [e for e in actor.episodic_memory.get("recent_events", []) if e.get("type") == "co_present_success"]
    assert len(recent) >= 1


def test_social_influence_decays_when_unseen_and_idle() -> None:
    world = _flat_world()
    world.tick = 40
    agent = Agent(x=8, y=8, brain=None)
    agent.social_influence = 0.9
    agent.subjective_state = {"nearby_agents": []}
    decayed = evaluate_agent_social_influence(world, agent)
    assert decayed < 0.9


def test_no_omniscient_world_queries_required_for_influence() -> None:
    world = _flat_world()
    world.tick = 5
    agent = Agent(x=1, y=1, brain=None)
    # No world.agents/world.villages setup required; helper should rely on local memory/state only.
    agent.subjective_state = {"nearby_agents": []}
    value = evaluate_agent_social_influence(world, agent)
    assert 0.0 <= value <= 1.0


def test_attention_uses_detected_local_leader() -> None:
    world = _flat_world()
    observer = Agent(x=10, y=10, brain=None)
    leader_like = Agent(x=11, y=10, brain=None)
    leader_like.social_influence = 0.85
    leader_like.role = "npc"
    world.agents = [observer, leader_like]
    observer.update_subjective_state(world)
    attention = observer.subjective_state.get("attention", {})
    leader = attention.get("salient_local_leader")
    assert isinstance(leader, dict)
    assert leader.get("agent_id") == leader_like.agent_id
