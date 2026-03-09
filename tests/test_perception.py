from __future__ import annotations

from agent import Agent, build_agent_perception
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


def test_agent_perception_is_bounded_by_radius() -> None:
    world = _flat_world()
    agent = Agent(x=10, y=10, brain=None)
    agent.visual_radius_tiles = 3
    world.food = {(11, 10), (20, 20)}

    perception = build_agent_perception(world, agent)
    seen = {(x["x"], x["y"]) for x in perception["nearby_resources"]["food"]}
    assert (11, 10) in seen
    assert (20, 20) not in seen


def test_agent_perception_includes_nearby_buildings_and_agents_only() -> None:
    world = _flat_world()
    observer = Agent(x=10, y=10, brain=None)
    observer.visual_radius_tiles = 4
    observer.social_radius_tiles = 4
    near_agent = Agent(x=12, y=10, brain=None)
    far_agent = Agent(x=25, y=25, brain=None)
    world.agents = [observer, near_agent, far_agent]
    world.buildings = {
        "b-near": {
            "building_id": "b-near",
            "type": "house",
            "x": 9,
            "y": 10,
            "footprint": [{"x": 9, "y": 10}],
            "operational_state": "active",
        },
        "b-far": {
            "building_id": "b-far",
            "type": "house",
            "x": 30,
            "y": 30,
            "footprint": [{"x": 30, "y": 30}],
            "operational_state": "active",
        },
    }

    perception = build_agent_perception(world, observer)
    building_ids = [b["building_id"] for b in perception["nearby_buildings"]]
    agent_ids = [a["agent_id"] for a in perception["nearby_agents"]]
    assert "b-near" in building_ids
    assert "b-far" not in building_ids
    assert near_agent.agent_id in agent_ids
    assert far_agent.agent_id not in agent_ids


def test_subjective_state_updates_deterministically() -> None:
    world = _flat_world()
    world.tick = 42
    agent = Agent(x=8, y=8, brain=None)
    agent.visual_radius_tiles = 5
    world.food = {(7, 8)}
    world.wood = {(8, 9)}
    world.agents = [agent]

    first = build_agent_perception(world, agent)
    second = build_agent_perception(world, agent)
    assert first == second

    agent.update_subjective_state(world)
    assert agent.subjective_state["last_perception_tick"] == 42
    assert isinstance(agent.short_term_memory["recently_seen_resources"], list)


def test_local_village_signals_present_only_when_agent_has_village() -> None:
    world = _flat_world()
    village = {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 10, "y": 10},
        "priority": "secure_food",
        "needs": {"food_low": True},
        "market_state": {
            "food": {"pressure": 0.8, "local_price_index": 1.5},
            "wood": {"pressure": 0.2, "local_price_index": 0.9},
            "stone": {"pressure": 0.3, "local_price_index": 1.0},
        },
    }
    world.villages = [village]

    outsider = Agent(x=10, y=10, brain=None)
    insider = Agent(x=10, y=10, brain=None)
    insider.village_id = 1

    outsider_state = build_agent_perception(world, outsider)
    insider_state = build_agent_perception(world, insider)
    assert outsider_state["local_signals"] == {}
    assert insider_state["local_signals"]["priority"] == "secure_food"
    assert "market_state" in insider_state["local_signals"]


def test_no_omniscient_resource_leakage_in_subjective_state() -> None:
    world = _flat_world()
    agent = Agent(x=5, y=5, brain=None)
    agent.visual_radius_tiles = 2
    world.food = {(6, 5), (20, 20)}
    world.wood = {(7, 5), (40, 40)}
    world.stone = {(5, 7), (50, 50)}

    perception = build_agent_perception(world, agent)
    for resource in ("food", "wood", "stone"):
        for entry in perception["nearby_resources"][resource]:
            dist = abs(entry["x"] - agent.x) + abs(entry["y"] - agent.y)
            assert dist <= agent.visual_radius_tiles
