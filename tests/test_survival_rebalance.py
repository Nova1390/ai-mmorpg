from __future__ import annotations

from agent import Agent
from world import World


def _world() -> World:
    world = World(width=24, height=24, num_agents=0, seed=222, llm_enabled=False)
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    world.food.clear()
    world.wood.clear()
    world.stone.clear()
    world.villages = []
    world.buildings = {}
    world.structures = set()
    world.storage_buildings = set()
    world.camps = {}
    world.agents = []
    return world


def _camp(*, x: int = 8, y: int = 8, food_cache: int = 1) -> dict:
    return {
        "camp_id": "camp-001",
        "x": int(x),
        "y": int(y),
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


def test_early_grace_reduces_hunger_decay_per_tick() -> None:
    world = _world()
    a = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    a.hunger = 90.0
    world.agents = [a]
    world.tick = 0

    before = float(a.hunger)
    a.update(world)
    delta = before - float(a.hunger)

    assert delta > 0.0
    assert delta < 1.0


def test_nearby_camp_food_buffer_reduces_hunger_decay_after_grace() -> None:
    world_a = _world()
    world_b = _world()
    world_b.camps["camp-001"] = _camp(food_cache=2)

    a1 = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a2 = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a1.hunger = 90.0
    a2.hunger = 90.0
    world_a.agents = [a1]
    world_b.agents = [a2]
    world_a.tick = 500
    world_b.tick = 500

    before_a = float(a1.hunger)
    before_b = float(a2.hunger)
    a1.update(world_a)
    a2.update(world_b)
    decay_no_camp = before_a - float(a1.hunger)
    decay_with_camp = before_b - float(a2.hunger)

    assert decay_no_camp > 0.0
    assert decay_with_camp > 0.0
    assert decay_with_camp < decay_no_camp


def test_deposit_food_guard_is_more_conservative_under_low_hunger() -> None:
    world = _world()
    world.camps["camp-001"] = _camp(food_cache=0)
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.inventory["food"] = 1

    moved = world.try_deposit_food_to_nearby_camp(a, amount=1, hunger_before=35.0)

    assert moved == 0
    assert int(a.inventory.get("food", 0)) == 1
    assert int(world.camps["camp-001"].get("food_cache", 0)) == 0


def test_critical_hunger_still_clears_proto_specialization() -> None:
    world = _world()
    world.camps["camp-001"] = _camp(food_cache=0)
    world.food.add((9, 8))
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.hunger = 80.0
    world.agents = [a]

    world.update_agent_proto_specialization(a)
    assert str(a.proto_specialization) != "none"

    a.hunger = 10.0
    world.tick += 1
    world.update_agent_proto_specialization(a)
    assert str(a.proto_specialization) == "none"
