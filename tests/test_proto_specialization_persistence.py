from __future__ import annotations

from agent import Agent
from config import HOUSE_STONE_COST, HOUSE_WOOD_COST
from world import World


def _world() -> World:
    world = World(width=24, height=24, num_agents=0, seed=1414, llm_enabled=False)
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    world.food.clear()
    world.wood.clear()
    world.stone.clear()
    world.camps = {}
    world.agents = []
    world.tick = 0
    return world


def _camp(food_cache: int = 0, *, active: bool = True) -> dict:
    return {
        "camp_id": "camp-001",
        "x": 8,
        "y": 8,
        "community_id": "pc-000001",
        "created_tick": 0,
        "last_active_tick": 0,
        "active": bool(active),
        "absence_ticks": 0,
        "village_uid": "",
        "return_events": 0,
        "rest_events": 0,
        "food_cache": int(food_cache),
    }


def test_gatherer_specialization_persists_briefly_under_valid_need() -> None:
    world = _world()
    world.camps["camp-001"] = _camp(food_cache=0)
    world.food.add((9, 8))
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.hunger = 80.0
    world.agents = [a]

    world.update_agent_proto_specialization(a)
    assert str(a.proto_specialization) == "food_gatherer"
    base_until = int(a.proto_specialization_until_tick)
    world.tick += 1
    world.update_agent_proto_specialization(a)
    assert str(a.proto_specialization) == "food_gatherer"
    assert int(a.proto_specialization_until_tick) >= base_until
    assert int(world.proto_specialization_retained_ticks) >= 1


def test_gatherer_assignment_receives_local_task_anchor() -> None:
    world = _world()
    world.camps["camp-001"] = _camp(food_cache=0)
    world.food.add((9, 8))
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.hunger = 80.0
    world.agents = [a]

    world.update_agent_proto_specialization(a)

    assert str(a.proto_specialization) == "food_gatherer"
    anchor = getattr(a, "proto_task_anchor", {})
    assert isinstance(anchor, dict) and anchor
    assert str(anchor.get("anchor_type", "")) == "food_gatherer"
    assert str(anchor.get("camp_id", "")) == "camp-001"
    assert isinstance(anchor.get("drop_pos", []), list) and len(anchor.get("drop_pos", [])) == 2
    assert isinstance(anchor.get("source_pos", []), list) and len(anchor.get("source_pos", [])) == 2
    assert int(world.proto_specialization_anchor_assignments) >= 1


def test_anchor_backed_retention_updates_anchor_metrics() -> None:
    world = _world()
    world.camps["camp-001"] = _camp(food_cache=0)
    world.food.add((9, 8))
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.hunger = 85.0
    world.agents = [a]

    world.update_agent_proto_specialization(a)
    world.tick += 1
    world.update_agent_proto_specialization(a)

    assert str(a.proto_specialization) == "food_gatherer"
    assert int(world.proto_specialization_anchor_retained_ticks) >= 1


def test_hauler_specialization_persists_briefly_under_valid_need() -> None:
    world = _world()
    world.camps["camp-001"] = _camp(food_cache=1)
    world.food.add((10, 8))
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.hunger = 85.0
    a.inventory["food"] = 1
    world.agents = [a]

    world.update_agent_proto_specialization(a)
    assert str(a.proto_specialization) == "food_hauler"
    world.tick += 1
    world.update_agent_proto_specialization(a)
    assert str(a.proto_specialization) == "food_hauler"
    assert int(world.proto_specialization_retained_ticks) >= 1


def test_builder_specialization_persists_only_while_build_need_valid() -> None:
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

    world.update_agent_proto_specialization(a)
    assert str(a.proto_specialization) == "builder"

    world.buildings["house-a"] = {
        "building_id": "house-a",
        "type": "house",
        "x": 8,
        "y": 8,
        "operational_state": "active",
    }
    world.tick += 1
    world.update_agent_proto_specialization(a)
    assert str(a.proto_specialization) == "none"
    assert int(world.proto_specialization_cleared_reasons.get("no_local_need", 0)) >= 1


def test_critical_hunger_clears_specialization() -> None:
    world = _world()
    world.camps["camp-001"] = _camp(food_cache=1)
    world.food.add((9, 8))
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.hunger = 80.0
    a.inventory["food"] = 1
    world.agents = [a]
    world.update_agent_proto_specialization(a)
    assert str(a.proto_specialization) != "none"

    a.hunger = 10.0
    world.tick += 1
    world.update_agent_proto_specialization(a)
    assert str(a.proto_specialization) == "none"
    assert int(world.proto_specialization_cleared_reasons.get("critical_hunger", 0)) >= 1


def test_camp_disappearance_clears_specialization() -> None:
    world = _world()
    world.camps["camp-001"] = _camp(food_cache=1)
    world.food.add((9, 8))
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.hunger = 80.0
    a.inventory["food"] = 1
    world.agents = [a]
    world.update_agent_proto_specialization(a)
    assert str(a.proto_specialization) != "none"

    world.camps.clear()
    world.tick += 1
    world.update_agent_proto_specialization(a)
    assert str(a.proto_specialization) == "none"
    assert getattr(a, "proto_task_anchor", {}) == {}
    assert int(world.proto_specialization_cleared_reasons.get("camp_missing", 0)) >= 1


def test_builder_anchor_invalidates_when_local_target_opportunity_disappears() -> None:
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

    world.update_agent_proto_specialization(a)
    assert str(a.proto_specialization) == "builder"

    for y in range(world.height):
        for x in range(world.width):
            if abs(x - 8) + abs(y - 8) <= 5:
                world.building_occupancy[(x, y)] = "blocker"
    world.tick += 1
    world.update_agent_proto_specialization(a)
    assert str(a.proto_specialization) == "none"
    assert int(world.proto_specialization_anchor_invalidations) >= 1
    reasons = dict(getattr(world, "proto_specialization_anchor_invalidation_reasons", {}) or {})
    assert int(reasons.get("target_missing", 0) + reasons.get("local_loop_broken", 0) + reasons.get("anchor_invalid", 0)) >= 1


def test_no_permanent_lock_in_when_local_need_changes() -> None:
    world = _world()
    world.camps["camp-001"] = _camp(food_cache=0)
    world.food.add((9, 8))
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.hunger = 85.0
    world.agents = [a]
    world.update_agent_proto_specialization(a)
    assert str(a.proto_specialization) == "food_gatherer"

    world.food.clear()
    world.tick = int(a.proto_specialization_until_tick) + 1
    world.update_agent_proto_specialization(a)
    assert str(a.proto_specialization) == "none"


def test_observability_exports_persistence_and_clear_metrics() -> None:
    world = _world()
    world.camps["camp-001"] = _camp(food_cache=0)
    world.food.add((9, 8))
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.hunger = 85.0
    world.agents = [a]
    world.update_agent_proto_specialization(a)
    world.tick += 1
    world.update_agent_proto_specialization(a)
    world.food.clear()
    world.tick = int(a.proto_specialization_until_tick) + 1
    world.update_agent_proto_specialization(a)

    world.metrics_collector.collect(world)
    ps = world.metrics_collector.latest()["cognition_society"]["proto_specialization_global"]
    assert "proto_specialization_assigned_tick_count" in ps
    assert "proto_specialization_retained_ticks" in ps
    assert "proto_specialization_cleared_count" in ps
    assert "proto_specialization_cleared_reasons" in ps
    assert "proto_specialization_anchor_assignments" in ps
    assert "proto_specialization_anchor_retained_ticks" in ps
    assert "proto_specialization_anchor_invalidations" in ps
    assert "proto_specialization_anchor_invalidation_reasons" in ps
    assert int(ps["proto_specialization_cleared_count"]) >= 1
