from __future__ import annotations

from agent import Agent
from config import HOUSE_STONE_COST, HOUSE_WOOD_COST
from world import World


def _world() -> World:
    world = World(width=24, height=24, num_agents=0, seed=1313, llm_enabled=False)
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    world.food.clear()
    world.wood.clear()
    world.stone.clear()
    world.villages = []
    world.camps = {}
    return world


def _camp(food_cache: int = 0) -> dict:
    return {
        "camp_id": "camp-001",
        "x": 8,
        "y": 8,
        "community_id": "pc-000001",
        "created_tick": 0,
        "last_active_tick": 0,
        "active": True,
        "absence_ticks": 0,
        "village_uid": "",
        "return_events": 0,
        "rest_events": 0,
        "food_cache": int(food_cache),
    }


def test_low_camp_food_biases_nearby_agents_toward_gather_and_supply() -> None:
    world = _world()
    world.camps["camp-001"] = _camp(food_cache=0)
    world.food.add((9, 8))

    gatherer = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    gatherer.hunger = 80.0
    supplier = Agent(x=8, y=9, brain=None, is_player=False, player_id=None)
    supplier.hunger = 80.0
    supplier.inventory["food"] = 1

    gatherer.update_role_task(world)
    supplier.update_role_task(world)

    assert str(gatherer.proto_specialization) == "food_gatherer"
    assert str(gatherer.task) == "gather_food_wild"
    assert str(supplier.proto_specialization) == "food_hauler"
    assert str(supplier.task) == "camp_supply_food"


def test_camp_food_loop_attracts_hauler_like_bias_when_useful() -> None:
    world = _world()
    world.camps["camp-001"] = _camp(food_cache=1)
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.hunger = 75.0
    a.inventory["food"] = 2

    a.update_role_task(world)
    assert str(a.proto_specialization) == "food_hauler"
    assert str(a.task) == "camp_supply_food"


def test_builder_bias_activates_only_when_camp_stable_and_local_build_opportunity_exists() -> None:
    world = _world()
    world.camps["camp-001"] = _camp(food_cache=3)
    world.wood.update({(7, 8), (9, 8)})
    world.stone.update({(8, 7), (8, 9)})
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.hunger = 90.0
    a.inventory["wood"] = int(HOUSE_WOOD_COST)
    a.inventory["stone"] = int(HOUSE_STONE_COST)
    helper = Agent(x=9, y=8, brain=None, is_player=False, player_id=None)
    helper.hunger = 90.0
    world.agents = [a, helper]

    a.update_role_task(world)
    assert str(a.proto_specialization) == "builder"
    assert str(a.task) == "bootstrap_build_house"


def test_urgent_hunger_overrides_proto_specialization() -> None:
    world = _world()
    world.camps["camp-001"] = _camp(food_cache=0)
    world.food.add((9, 8))
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.hunger = 10.0
    a.inventory["food"] = 1

    a.update_role_task(world)
    assert str(a.proto_specialization) == "none"
    assert str(a.task) != "camp_supply_food"


def test_proto_specialization_not_locked_when_camp_disappears() -> None:
    world = _world()
    world.camps["camp-001"] = _camp(food_cache=0)
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.hunger = 80.0
    a.inventory["food"] = 1

    a.update_role_task(world)
    assert str(a.task) == "camp_supply_food"
    assert str(a.proto_specialization) == "food_hauler"

    world.camps.clear()
    a.update_role_task(world)
    assert str(a.proto_specialization) == "none"
    assert str(a.task) != "camp_supply_food"


def test_observability_exports_proto_specialization_metrics() -> None:
    world = _world()
    world.camps["camp-001"] = _camp(food_cache=0)
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.hunger = 80.0
    a.inventory["food"] = 1
    b = Agent(x=9, y=8, brain=None, is_player=False, player_id=None)
    b.hunger = 80.0
    world.food.add((10, 8))
    world.agents = [a, b]
    for agent in world.agents:
        agent.update_role_task(world)

    world.metrics_collector.collect(world)
    cog = world.metrics_collector.latest()["cognition_society"]
    assert "proto_specialization_global" in cog
    ps = cog["proto_specialization_global"]
    assert int(ps.get("proto_food_gatherer_count", 0)) >= 1
    assert int(ps.get("proto_food_hauler_count", 0)) >= 1
