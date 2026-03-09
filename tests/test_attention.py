from __future__ import annotations

from agent import Agent, build_agent_perception, evaluate_agent_salience
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


def _with_state(world: World, agent: Agent) -> None:
    agent.subjective_state = build_agent_perception(world, agent)


def test_hunger_increases_food_salience() -> None:
    world = _flat_world()
    agent = Agent(x=10, y=10, brain=None)
    agent.visual_radius_tiles = 6
    agent.hunger = 25
    world.food = {(11, 10)}
    world.wood = {(10, 11)}
    world.stone = {(9, 10)}
    _with_state(world, agent)

    attention = evaluate_agent_salience(world, agent)
    top = attention["top_resource_targets"][0]
    assert top["resource"] == "food"
    assert attention["current_focus"] in {"urgent_food", "food_security"}


def test_miner_and_woodcutter_prioritize_relevant_targets() -> None:
    world = _flat_world()
    world.buildings = {
        "mine-1": {"building_id": "mine-1", "type": "mine", "x": 10, "y": 11, "operational_state": "active"},
        "yard-1": {"building_id": "yard-1", "type": "lumberyard", "x": 11, "y": 10, "operational_state": "active"},
    }
    world.stone = {(10, 12)}
    world.wood = {(12, 10)}

    miner = Agent(x=10, y=10, brain=None)
    miner.role = "miner"
    _with_state(world, miner)
    miner_attention = evaluate_agent_salience(world, miner)
    assert miner_attention["top_resource_targets"][0]["resource"] == "stone"
    assert miner_attention["top_building_targets"][0]["type"] == "mine"

    woodcutter = Agent(x=10, y=10, brain=None)
    woodcutter.role = "woodcutter"
    _with_state(world, woodcutter)
    wood_attention = evaluate_agent_salience(world, woodcutter)
    assert wood_attention["top_resource_targets"][0]["resource"] == "wood"
    assert wood_attention["top_building_targets"][0]["type"] == "lumberyard"


def test_attention_is_bounded_top_k() -> None:
    world = _flat_world()
    agent = Agent(x=10, y=10, brain=None)
    agent.visual_radius_tiles = 8
    world.food = {(10 + i, 10) for i in range(1, 7)}
    world.wood = {(10, 10 + i) for i in range(1, 7)}
    world.stone = {(10 - i, 10) for i in range(1, 7)}
    world.buildings = {
        f"b-{i}": {"building_id": f"b-{i}", "type": "house", "x": 10 + i, "y": 9, "operational_state": "active"}
        for i in range(1, 8)
    }
    world.agents = [agent] + [Agent(x=9 + i, y=10, brain=None) for i in range(1, 8)]
    _with_state(world, agent)
    attention = evaluate_agent_salience(world, agent)
    assert len(attention["top_resource_targets"]) <= 3
    assert len(attention["top_building_targets"]) <= 3
    assert len(attention["top_social_targets"]) <= 3


def test_salience_is_deterministic_for_same_setup() -> None:
    w1 = _flat_world()
    w2 = _flat_world()
    a1 = Agent(x=10, y=10, brain=None)
    a2 = Agent(x=10, y=10, brain=None)
    a1.role = "builder"
    a2.role = "builder"
    w1.food = {(11, 10)}
    w1.wood = {(12, 10)}
    w1.stone = {(10, 12)}
    w2.food = {(11, 10)}
    w2.wood = {(12, 10)}
    w2.stone = {(10, 12)}
    _with_state(w1, a1)
    _with_state(w2, a2)
    assert evaluate_agent_salience(w1, a1) == evaluate_agent_salience(w2, a2)


def test_dominant_signal_and_focus_follow_local_context() -> None:
    world = _flat_world()
    village = {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 10, "y": 10},
        "priority": "secure_food",
        "needs": {"food_urgent": True, "food_buffer_critical": True},
        "market_state": {
            "food": {"pressure": 0.9, "local_price_index": 1.8},
            "wood": {"pressure": 0.1, "local_price_index": 0.8},
            "stone": {"pressure": 0.2, "local_price_index": 0.9},
        },
    }
    world.villages = [village]
    agent = Agent(x=10, y=10, brain=None)
    agent.village_id = 1
    agent.hunger = 45
    _with_state(world, agent)
    attention = evaluate_agent_salience(world, agent)
    assert attention["dominant_local_signal"] in {"food_urgent", "food_scarcity", "priority:secure_food"}
    assert attention["current_focus"] in {"food_security", "urgent_food"}


def test_attention_has_no_obvious_omniscient_leakage() -> None:
    world = _flat_world()
    agent = Agent(x=5, y=5, brain=None)
    agent.visual_radius_tiles = 2
    world.food = {(6, 5), (20, 20)}
    _with_state(world, agent)
    attention = evaluate_agent_salience(world, agent)
    for entry in attention["top_resource_targets"]:
        dist = abs(int(entry["x"]) - agent.x) + abs(int(entry["y"]) - agent.y)
        assert dist <= agent.visual_radius_tiles


def test_salient_items_are_written_into_short_term_memory() -> None:
    world = _flat_world()
    agent = Agent(x=10, y=10, brain=None)
    agent.hunger = 20
    world.food = {(11, 10)}
    agent.update_subjective_state(world)
    recent = agent.short_term_memory.get("recently_seen_resources", [])
    assert isinstance(recent, list)
    assert any(bool(item.get("salient", False)) for item in recent if isinstance(item, dict))
