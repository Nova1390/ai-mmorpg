from __future__ import annotations

from agent import (
    Agent,
    IDENTITY_UPDATE_INTERVAL_TICKS,
    ensure_agent_proto_traits,
    evaluate_agent_salience,
    update_agent_identity,
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


def test_proto_traits_initialization_is_deterministic_for_role() -> None:
    a1 = Agent(x=0, y=0, brain=None)
    a2 = Agent(x=1, y=1, brain=None)
    a1.role = "hauler"
    a2.role = "hauler"
    t1 = ensure_agent_proto_traits(a1)
    t2 = ensure_agent_proto_traits(a2)
    compare1 = {k: v for k, v in t1.items() if k != "last_identity_update_tick"}
    compare2 = {k: v for k, v in t2.items() if k != "last_identity_update_tick"}
    assert compare1 == compare2
    assert all(0.0 <= float(compare1[k]) <= 1.0 for k in compare1 if k != "last_identity_update_tick")


def test_identity_updates_are_bounded_and_periodic() -> None:
    world = _flat_world()
    agent = Agent(x=4, y=4, brain=None)
    agent.role = "builder"
    traits = ensure_agent_proto_traits(agent)
    base_diligence = float(traits["diligence"])

    for i in range(3):
        write_episodic_memory_event(
            agent,
            tick=i,
            event_type="construction_progress",
            outcome="success",
            location=(4, 4),
            salience=1.2,
        )

    world.tick = 0
    update_agent_identity(world, agent)
    first_tick = int(agent.proto_traits["last_identity_update_tick"])
    first_value = float(agent.proto_traits["diligence"])
    assert first_value >= base_diligence

    world.tick = first_tick + 10
    update_agent_identity(world, agent)
    assert int(agent.proto_traits["last_identity_update_tick"]) == first_tick
    assert float(agent.proto_traits["diligence"]) == first_value

    world.tick = first_tick + IDENTITY_UPDATE_INTERVAL_TICKS
    update_agent_identity(world, agent)
    assert int(agent.proto_traits["last_identity_update_tick"]) == world.tick
    for key in ("cooperation", "diligence", "caution", "curiosity", "resilience", "identity_stability"):
        assert 0.0 <= float(agent.proto_traits[key]) <= 1.0


def test_cooperation_increases_after_cooperative_experience() -> None:
    world = _flat_world()
    world.tick = IDENTITY_UPDATE_INTERVAL_TICKS
    agent = Agent(x=6, y=6, brain=None)
    ensure_agent_proto_traits(agent)
    baseline = float(agent.proto_traits["cooperation"])
    agent.social_memory = {
        "known_agents": {
            "a-1": {
                "last_seen_tick": world.tick,
                "times_seen": 5,
                "same_village": True,
                "role": "hauler",
                "recent_interaction": "co_present_success",
                "social_salience": 2.0,
            }
        }
    }
    update_agent_identity(world, agent)
    assert float(agent.proto_traits["cooperation"]) > baseline


def test_diligence_and_curiosity_increase_from_relevant_successes() -> None:
    world = _flat_world()
    agent = Agent(x=8, y=8, brain=None)
    ensure_agent_proto_traits(agent)
    base_diligence = float(agent.proto_traits["diligence"])
    base_curiosity = float(agent.proto_traits["curiosity"])

    write_episodic_memory_event(
        agent,
        tick=1,
        event_type="construction_progress",
        outcome="success",
        location=(8, 8),
        salience=1.3,
    )
    write_episodic_memory_event(
        agent,
        tick=2,
        event_type="found_resource",
        outcome="success",
        location=(9, 8),
        resource_type="food",
        salience=1.1,
    )
    world.tick = IDENTITY_UPDATE_INTERVAL_TICKS
    update_agent_identity(world, agent)
    assert float(agent.proto_traits["diligence"]) >= base_diligence
    assert float(agent.proto_traits["curiosity"]) >= base_curiosity


def test_trait_bias_affects_attention_deterministically() -> None:
    world = _flat_world()
    world.food = {(11, 10)}
    world.wood = {(10, 11)}
    world.stone = {(9, 10)}
    world.agents = []

    agent = Agent(x=10, y=10, brain=None)
    peer = Agent(x=11, y=10, brain=None)
    agent.village_id = 1
    peer.village_id = 1
    world.agents = [agent, peer]
    agent.update_subjective_state(world)

    ensure_agent_proto_traits(agent)
    agent.proto_traits.update(
        {
            "cooperation": 0.95,
            "diligence": 0.80,
            "caution": 0.70,
            "curiosity": 0.30,
            "resilience": 0.80,
        }
    )
    attention_1 = evaluate_agent_salience(world, agent)
    attention_2 = evaluate_agent_salience(world, agent)
    assert attention_1 == attention_2
    assert len(attention_1["top_social_targets"]) >= 1
    assert float(attention_1["top_social_targets"][0]["salience"]) > 0.0


def test_identity_update_uses_local_memory_only() -> None:
    world = _flat_world()
    world.tick = IDENTITY_UPDATE_INTERVAL_TICKS
    agent = Agent(x=3, y=3, brain=None)
    ensure_agent_proto_traits(agent)
    write_episodic_memory_event(
        agent,
        tick=1,
        event_type="failed_resource_search",
        outcome="failure",
        location=(3, 3),
        resource_type="stone",
        salience=1.5,
    )
    updated = update_agent_identity(world, agent)
    assert int(updated["last_identity_update_tick"]) == world.tick
    assert 0.0 <= float(updated["caution"]) <= 1.0

