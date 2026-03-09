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


def _prepare_subjective(agent: Agent, world: World) -> None:
    agent.update_subjective_state(world)


def test_intention_persists_across_ticks() -> None:
    world = _flat_world()
    brain = FoodBrain()
    agent = Agent(x=10, y=10, brain=brain)
    agent.hunger = 50
    world.food = {(12, 10)}
    _prepare_subjective(agent, world)

    first_action = brain.decide(agent, world)
    first_intention = dict(agent.current_intention or {})
    second_action = brain.decide(agent, world)
    second_intention = dict(agent.current_intention or {})

    assert first_action[0] == "move"
    assert second_action[0] == "move"
    assert first_intention.get("type") == second_intention.get("type")
    assert first_intention.get("started_tick") == second_intention.get("started_tick")


def test_intention_completes_when_goal_reached() -> None:
    world = _flat_world()
    brain = FoodBrain()
    agent = Agent(x=10, y=10, brain=brain)
    agent.current_intention = {
        "type": "gather_food",
        "target": {"x": 11, "y": 10},
        "target_id": None,
        "resource_type": "food",
        "started_tick": 0,
        "status": "active",
        "failed_ticks": 0,
    }
    agent.inventory["food"] = 1
    _prepare_subjective(agent, world)

    brain.decide(agent, world)
    assert agent.current_intention is None


def test_intention_invalidates_when_target_disappears() -> None:
    world = _flat_world()
    brain = FoodBrain()
    agent = Agent(x=10, y=10, brain=brain)
    agent.current_intention = {
        "type": "gather_resource",
        "target": {"x": 20, "y": 20},
        "target_id": None,
        "resource_type": "wood",
        "started_tick": 0,
        "status": "active",
        "failed_ticks": 0,
    }
    _prepare_subjective(agent, world)

    brain.decide(agent, world)
    brain.decide(agent, world)
    brain.decide(agent, world)
    assert agent.current_intention is None or agent.current_intention.get("type") != "gather_resource"


def test_hunger_overrides_existing_intention() -> None:
    world = _flat_world()
    brain = FoodBrain()
    agent = Agent(x=10, y=10, brain=brain)
    agent.current_intention = {
        "type": "work_mine",
        "target": {"x": 14, "y": 10},
        "target_id": "mine-1",
        "resource_type": "stone",
        "started_tick": 0,
        "status": "active",
        "failed_ticks": 0,
    }
    agent.hunger = 20
    world.food = {(11, 10)}
    _prepare_subjective(agent, world)

    brain.decide(agent, world)
    assert isinstance(agent.current_intention, dict)
    assert agent.current_intention.get("type") == "gather_food"


def test_intention_selection_is_deterministic_for_same_setup() -> None:
    w1 = _flat_world()
    w2 = _flat_world()
    b1 = FoodBrain()
    b2 = FoodBrain()
    a1 = Agent(x=10, y=10, brain=b1)
    a2 = Agent(x=10, y=10, brain=b2)
    a1.role = "woodcutter"
    a2.role = "woodcutter"
    w1.wood = {(11, 10)}
    w2.wood = {(11, 10)}
    _prepare_subjective(a1, w1)
    _prepare_subjective(a2, w2)

    b1.decide(a1, w1)
    b2.decide(a2, w2)

    i1 = a1.current_intention or {}
    i2 = a2.current_intention or {}
    assert i1.get("type") == i2.get("type")
    assert i1.get("resource_type") == i2.get("resource_type")
    assert i1.get("target") == i2.get("target")
