from __future__ import annotations

from agent import Agent
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


def test_nearby_agents_populate_social_memory() -> None:
    world = _flat_world()
    observer = Agent(x=10, y=10, brain=None)
    observer.village_id = 1
    nearby = Agent(x=11, y=10, brain=None)
    nearby.village_id = 1
    world.agents = [observer, nearby]

    observer.update_subjective_state(world)
    known = observer.social_memory.get("known_agents", {})
    assert nearby.agent_id in known
    entry = known[nearby.agent_id]
    assert int(entry["times_seen"]) >= 1
    assert bool(entry["same_village"]) is True


def test_repeated_encounters_increase_social_salience() -> None:
    world = _flat_world()
    observer = Agent(x=10, y=10, brain=None)
    friend = Agent(x=11, y=10, brain=None)
    world.agents = [observer, friend]

    observer.update_subjective_state(world)
    first = dict(observer.social_memory["known_agents"][friend.agent_id])
    world.tick += 1
    observer.update_subjective_state(world)
    second = dict(observer.social_memory["known_agents"][friend.agent_id])
    assert int(second["times_seen"]) > int(first["times_seen"])
    assert float(second["social_salience"]) >= float(first["social_salience"])


def test_distant_agents_are_not_included() -> None:
    world = _flat_world()
    observer = Agent(x=5, y=5, brain=None)
    observer.social_radius_tiles = 2
    far = Agent(x=20, y=20, brain=None)
    world.agents = [observer, far]

    observer.update_subjective_state(world)
    known = observer.social_memory.get("known_agents", {})
    assert far.agent_id not in known


def test_same_village_and_leader_raise_social_salience_deterministically() -> None:
    world = _flat_world()
    observer = Agent(x=10, y=10, brain=None)
    observer.village_id = 1
    villager = Agent(x=11, y=10, brain=None)
    villager.village_id = 1
    leader = Agent(x=12, y=10, brain=None)
    leader.village_id = 1
    leader.role = "leader"
    world.agents = [observer, villager, leader]

    observer.update_subjective_state(world)
    attention = observer.subjective_state.get("attention", {})
    top_social = attention.get("top_social_targets", [])
    assert len(top_social) >= 1
    assert top_social[0]["agent_id"] in {villager.agent_id, leader.agent_id}
    first_order = [entry["agent_id"] for entry in top_social]

    # Deterministic: repeated evaluation with same setup yields same ordering.
    observer.update_subjective_state(world)
    top_social2 = observer.subjective_state.get("attention", {}).get("top_social_targets", [])
    second_order = [entry["agent_id"] for entry in top_social2]
    assert first_order == second_order
    first_salience = {entry["agent_id"]: float(entry["salience"]) for entry in top_social}
    second_salience = {entry["agent_id"]: float(entry["salience"]) for entry in top_social2}
    for agent_id in first_salience:
        assert second_salience[agent_id] >= first_salience[agent_id]


def test_no_omniscient_leakage_in_social_memory_entries() -> None:
    world = _flat_world()
    observer = Agent(x=10, y=10, brain=None)
    nearby = Agent(x=11, y=10, brain=None)
    world.agents = [observer, nearby]
    observer.update_subjective_state(world)

    entry = observer.social_memory["known_agents"][nearby.agent_id]
    forbidden = {"all_agents", "global_population", "world_state"}
    assert forbidden.isdisjoint(set(entry.keys()))


def test_light_social_decision_bias_is_deterministic() -> None:
    world = _flat_world()
    brain = FoodBrain()
    observer = Agent(x=10, y=10, brain=brain)
    observer.role = "hauler"
    observer.task = "village_logistics"
    observer.village_id = 1
    peer = Agent(x=11, y=10, brain=None)
    peer.village_id = 1
    world.agents = [observer, peer]
    observer.update_subjective_state(world)

    first = brain._attention_social_target(observer, same_village_only=True)
    second = brain._attention_social_target(observer, same_village_only=True)
    assert first == second
