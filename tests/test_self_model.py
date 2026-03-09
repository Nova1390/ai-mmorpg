from __future__ import annotations

from agent import (
    Agent,
    ensure_agent_self_model,
    evaluate_agent_salience,
    interpret_local_signals_with_self_model,
    update_agent_self_model,
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


def _keys() -> set[str]:
    return {
        "survival_weight",
        "social_weight",
        "work_weight",
        "exploration_weight",
        "security_weight",
        "stress_level",
        "recent_success_bias",
        "recent_failure_bias",
        "last_self_update_tick",
    }


def test_self_model_initialization_is_deterministic() -> None:
    a1 = Agent(x=0, y=0, brain=None)
    a2 = Agent(x=1, y=1, brain=None)
    a1.role = "builder"
    a2.role = "builder"
    m1 = ensure_agent_self_model(a1)
    m2 = ensure_agent_self_model(a2)
    assert _keys().issubset(set(m1.keys()))
    assert _keys().issubset(set(m2.keys()))
    compare1 = {k: m1[k] for k in _keys() if k != "last_self_update_tick"}
    compare2 = {k: m2[k] for k in _keys() if k != "last_self_update_tick"}
    assert compare1 == compare2


def test_self_model_updates_are_bounded() -> None:
    world = _flat_world()
    agent = Agent(x=5, y=5, brain=None)
    ensure_agent_self_model(agent)
    for i in range(30):
        world.tick = i
        agent.hunger = 10 if i % 2 == 0 else 90
        write_episodic_memory_event(
            agent,
            tick=i,
            event_type="failed_resource_search" if i % 3 == 0 else "construction_progress",
            outcome="failure" if i % 3 == 0 else "success",
            location=(5, 5),
            resource_type="food",
            salience=1.5,
        )
        update_agent_self_model(world, agent)
    m = agent.self_model
    for key in (
        "survival_weight",
        "social_weight",
        "work_weight",
        "exploration_weight",
        "security_weight",
        "stress_level",
        "recent_success_bias",
        "recent_failure_bias",
    ):
        assert 0.0 <= float(m[key]) <= 1.0


def test_hunger_increases_survival_and_stress_bias() -> None:
    world = _flat_world()
    agent = Agent(x=3, y=3, brain=None)
    ensure_agent_self_model(agent)
    baseline_survival = float(agent.self_model["survival_weight"])
    baseline_stress = float(agent.self_model["stress_level"])
    world.tick = 1
    agent.hunger = 20
    update_agent_self_model(world, agent)
    assert float(agent.self_model["survival_weight"]) >= baseline_survival
    assert float(agent.self_model["stress_level"]) >= baseline_stress


def test_successful_work_reinforces_work_weight() -> None:
    world = _flat_world()
    agent = Agent(x=2, y=2, brain=None)
    ensure_agent_self_model(agent)
    base_work = float(agent.self_model["work_weight"])
    for i in range(3):
        write_episodic_memory_event(
            agent,
            tick=i,
            event_type="construction_progress",
            outcome="success",
            location=(2, 2),
            salience=1.2,
        )
    world.tick = 4
    update_agent_self_model(world, agent)
    assert float(agent.self_model["work_weight"]) > base_work


def test_useful_social_interaction_reinforces_social_weight() -> None:
    world = _flat_world()
    observer = Agent(x=10, y=10, brain=None)
    peer = Agent(x=11, y=10, brain=None)
    world.agents = [observer, peer]
    ensure_agent_self_model(observer)
    base_social = float(observer.self_model["social_weight"])
    write_episodic_memory_event(
        observer,
        tick=1,
        event_type="useful_building",
        outcome="success",
        location=(10, 10),
        salience=1.1,
    )
    observer.update_subjective_state(world)
    world.tick = 2
    update_agent_self_model(world, observer)
    assert float(observer.self_model["social_weight"]) >= base_social


def test_self_model_affects_salience_and_intention_choice() -> None:
    world = _flat_world()
    world.food = {(11, 10)}
    world.wood = {(10, 11)}

    survival_agent = Agent(x=10, y=10, brain=FoodBrain())
    work_agent = Agent(x=10, y=10, brain=FoodBrain())
    ensure_agent_self_model(survival_agent)
    ensure_agent_self_model(work_agent)
    survival_agent.self_model.update({"survival_weight": 0.95, "work_weight": 0.25, "stress_level": 0.2})
    work_agent.self_model.update({"survival_weight": 0.35, "work_weight": 0.95, "stress_level": 0.2})
    survival_agent.hunger = 55
    work_agent.hunger = 55
    survival_agent.update_subjective_state(world)
    work_agent.update_subjective_state(world)

    s_top = evaluate_agent_salience(world, survival_agent)["top_resource_targets"][0]["resource"]
    w_top = evaluate_agent_salience(world, work_agent)["top_resource_targets"][0]["resource"]
    assert s_top == "food"
    assert w_top in {"wood", "food"}

    s_int = survival_agent.brain.select_agent_intention(world, survival_agent)
    w_int = work_agent.brain.select_agent_intention(world, work_agent)
    assert isinstance(s_int, dict) and isinstance(w_int, dict)


def test_self_model_updates_without_global_world_knowledge() -> None:
    world = _flat_world()
    agent = Agent(x=1, y=1, brain=None)
    ensure_agent_self_model(agent)
    agent.subjective_state = {
        "local_signals": {
            "market_state": {
                "food": {"pressure": 0.8, "local_price_index": 1.4},
                "wood": {"pressure": 0.3, "local_price_index": 1.1},
                "stone": {"pressure": 0.2, "local_price_index": 1.0},
            },
            "needs": {"food_urgent": True},
        }
    }
    world.tick = 3
    updated = update_agent_self_model(world, agent)
    interpreted = interpret_local_signals_with_self_model(world, agent)
    assert updated["last_self_update_tick"] == 3
    assert interpreted["priority_interpretation"] in {
        "food_security",
        "work_materials",
        "social_coordination",
        "exploration",
    }
