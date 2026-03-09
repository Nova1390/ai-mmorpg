from __future__ import annotations

from agent import (
    Agent,
    KNOWLEDGE_MAX_INVENTIONS,
    decay_agent_knowledge_state,
    diffuse_invention_knowledge,
    ensure_agent_knowledge_state,
    update_agent_invention_knowledge_from_observation,
)
from world import World


def _flat_world() -> World:
    world = World(width=24, height=24, num_agents=0, seed=19, llm_enabled=False)
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


def _useful_prototype(*, pid: str = "p-1", iid: str = "proto-1", x: int = 10, y: int = 10) -> dict:
    return {
        "proposal_id": pid,
        "instance_id": iid,
        "inventor_agent_id": "a-inventor",
        "category": "storage",
        "effect": "increase_storage_efficiency",
        "location": {"x": x, "y": y},
        "status": "prototype_built",
        "usefulness_status": "useful",
    }


def test_useful_prototype_observation_creates_known_invention_entry() -> None:
    world = _flat_world()
    agent = Agent(x=10, y=11, brain=None)
    world.agents = [agent]
    world.proto_asset_prototypes = [_useful_prototype()]
    world.tick = 20
    update_agent_invention_knowledge_from_observation(world, agent)
    known = ensure_agent_knowledge_state(agent)["known_inventions"]
    assert len(known) == 1
    assert known[0]["proposal_id"] == "p-1"
    assert known[0]["source"] == "direct"
    assert known[0]["usefulness_status"] == "useful"


def test_useful_prototype_seen_event_can_seed_direct_knowledge() -> None:
    world = _flat_world()
    agent = Agent(x=1, y=1, brain=None)
    world.agents = [agent]
    world.proto_asset_prototypes = [_useful_prototype(iid="proto-ev", x=15, y=15)]
    agent.episodic_memory = {
        "recent_events": [
            {
                "type": "useful_prototype_seen",
                "tick": 30,
                "outcome": "success",
                "target_id": "proto-ev",
                "location": {"x": 15, "y": 15},
                "salience": 0.7,
            }
        ]
    }
    world.tick = 31
    update_agent_invention_knowledge_from_observation(world, agent)
    known = ensure_agent_knowledge_state(agent)["known_inventions"]
    assert any(e.get("prototype_id") == "proto-ev" for e in known)


def test_social_diffusion_of_invention_knowledge_is_local_only() -> None:
    world = _flat_world()
    donor = Agent(x=10, y=10, brain=None)
    donor.village_id = 1
    receiver_near = Agent(x=11, y=10, brain=None)
    receiver_near.village_id = 1
    receiver_far = Agent(x=20, y=20, brain=None)
    receiver_far.village_id = 1
    world.agents = [donor, receiver_near, receiver_far]

    ensure_agent_knowledge_state(donor)["known_inventions"] = [
        {
            "proposal_id": "p-1",
            "prototype_id": "proto-1",
            "inventor_agent_id": donor.agent_id,
            "category": "storage",
            "intended_effects": ["increase_storage_efficiency"],
            "location": {"x": 10, "y": 10},
            "learned_tick": 1,
            "confidence": 0.9,
            "source": "direct",
            "usefulness_status": "useful",
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
    receiver_near.social_memory = {
        "known_agents": {
            donor.agent_id: {
                "times_seen": 6,
                "same_village": True,
                "social_salience": 1.3,
                "last_seen_tick": 0,
                "recent_interaction": "co_present_success",
            }
        }
    }
    receiver_far.subjective_state = {"nearby_agents": []}
    diffuse_invention_knowledge(world, receiver_near)
    diffuse_invention_knowledge(world, receiver_far)
    assert len(ensure_agent_knowledge_state(receiver_near)["known_inventions"]) >= 1
    assert len(ensure_agent_knowledge_state(receiver_far)["known_inventions"]) == 0


def test_socially_learned_invention_has_lower_confidence_than_direct() -> None:
    world = _flat_world()
    donor = Agent(x=8, y=8, brain=None)
    receiver = Agent(x=9, y=8, brain=None)
    donor.village_id = 1
    receiver.village_id = 1
    world.agents = [donor, receiver]
    direct = {
        "proposal_id": "p-2",
        "prototype_id": "proto-2",
        "inventor_agent_id": donor.agent_id,
        "category": "transport",
        "intended_effects": ["reduce_movement_cost"],
        "location": {"x": 8, "y": 8},
        "learned_tick": 2,
        "confidence": 0.95,
        "source": "direct",
        "usefulness_status": "useful",
        "salience": 0.8,
    }
    ensure_agent_knowledge_state(donor)["known_inventions"] = [direct]
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
                "times_seen": 7,
                "same_village": True,
                "social_salience": 1.6,
                "last_seen_tick": 0,
                "recent_interaction": "co_present_success",
            }
        }
    }
    world.tick = 12
    diffuse_invention_knowledge(world, receiver)
    learned = ensure_agent_knowledge_state(receiver)["known_inventions"][0]
    assert learned["source"] == "social"
    assert float(learned["confidence"]) < float(direct["confidence"])


def test_repeated_direct_observation_increases_invention_confidence() -> None:
    world = _flat_world()
    agent = Agent(x=10, y=10, brain=None)
    world.agents = [agent]
    world.proto_asset_prototypes = [_useful_prototype()]
    world.tick = 5
    update_agent_invention_knowledge_from_observation(world, agent)
    first = float(ensure_agent_knowledge_state(agent)["known_inventions"][0]["confidence"])
    world.tick = 6
    update_agent_invention_knowledge_from_observation(world, agent)
    second = float(ensure_agent_knowledge_state(agent)["known_inventions"][0]["confidence"])
    assert second >= first


def test_invention_knowledge_decay_and_bounded_trimming() -> None:
    world = _flat_world()
    agent = Agent(x=2, y=2, brain=None)
    state = ensure_agent_knowledge_state(agent)
    entries = []
    for idx in range(KNOWLEDGE_MAX_INVENTIONS + 6):
        entries.append(
            {
                "proposal_id": f"p-{idx}",
                "prototype_id": f"proto-{idx}",
                "inventor_agent_id": "a-x",
                "category": "storage",
                "intended_effects": ["increase_storage_efficiency"],
                "location": {"x": idx % 5, "y": idx % 5},
                "learned_tick": 0,
                "confidence": 0.20 if idx % 2 == 0 else 0.32,
                "source": "social",
                "usefulness_status": "ineffective" if idx % 3 == 0 else "useful",
                "salience": 0.3,
            }
        )
    state["known_inventions"] = entries
    world.tick = 420
    decay_agent_knowledge_state(world, agent)
    kept = state["known_inventions"]
    assert len(kept) <= KNOWLEDGE_MAX_INVENTIONS
    assert all(float(e["confidence"]) >= 0.15 for e in kept)


def test_observability_reflects_invention_knowledge_spread() -> None:
    world = _flat_world()
    a1 = Agent(x=10, y=10, brain=None)
    a2 = Agent(x=11, y=10, brain=None)
    world.agents = [a1, a2]
    ensure_agent_knowledge_state(a1)["known_inventions"] = [
        {
            "proposal_id": "p-7",
            "prototype_id": "proto-7",
            "inventor_agent_id": "a-z",
            "category": "logistics",
            "intended_effects": ["improve_delivery_efficiency"],
            "location": {"x": 10, "y": 10},
            "learned_tick": 9,
            "confidence": 0.8,
            "source": "direct",
            "usefulness_status": "useful",
            "salience": 0.7,
        }
    ]
    ensure_agent_knowledge_state(a2)["known_inventions"] = [
        {
            "proposal_id": "p-7",
            "prototype_id": "proto-7",
            "inventor_agent_id": "a-z",
            "category": "logistics",
            "intended_effects": ["improve_delivery_efficiency"],
            "location": {"x": 10, "y": 10},
            "learned_tick": 10,
            "confidence": 0.55,
            "source": "social",
            "usefulness_status": "useful",
            "salience": 0.6,
        }
    ]
    world.tick = 12
    world.metrics_collector.collect(world)
    innovation = world.metrics_collector.latest()["innovation"]
    assert int(innovation.get("known_invention_entry_count", 0)) >= 2
    assert int(innovation.get("agents_with_known_inventions", 0)) >= 2
    assert int((innovation.get("invention_knowledge_by_source") or {}).get("social", 0)) >= 1
    assert int((innovation.get("invention_knowledge_by_category") or {}).get("logistics", 0)) >= 1


def test_no_omniscient_invention_leakage() -> None:
    world = _flat_world()
    far_agent = Agent(x=1, y=1, brain=None)
    world.agents = [far_agent]
    world.proto_asset_prototypes = [_useful_prototype(x=20, y=20)]
    far_agent.subjective_state = {"nearby_agents": []}
    world.tick = 50
    update_agent_invention_knowledge_from_observation(world, far_agent)
    assert len(ensure_agent_knowledge_state(far_agent)["known_inventions"]) == 0
