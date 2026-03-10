from __future__ import annotations

from agent import Agent
from world import World


def _world() -> World:
    world = World(width=24, height=24, num_agents=0, seed=909, llm_enabled=False)
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    world.food.clear()
    world.wood.clear()
    world.stone.clear()
    world.camps = {}
    return world


def _active_camp(*, x: int = 8, y: int = 8, food_cache: int = 0) -> dict:
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


def test_agent_can_deposit_food_to_nearby_camp() -> None:
    world = _world()
    world.camps["camp-001"] = _active_camp(food_cache=0)
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.hunger = 80.0
    world.food.add((8, 8))

    world.autopickup(agent)
    assert int(agent.inventory.get("food", 0)) == 0
    assert int(world.camps["camp-001"].get("food_cache", 0)) == 1


def test_agent_does_not_deposit_if_starving() -> None:
    world = _world()
    world.camps["camp-001"] = _active_camp(food_cache=0)
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.hunger = 10.0
    world.food.add((8, 8))

    world.autopickup(agent)
    assert int(world.camps["camp-001"].get("food_cache", 0)) == 0


def test_agent_preserves_last_food_ration_when_not_safe_to_over_donate() -> None:
    world = _world()
    world.camps["camp-001"] = _active_camp(food_cache=0)
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.hunger = 42.0
    agent.inventory["food"] = 1

    moved = world.try_deposit_food_to_nearby_camp(agent, amount=1, hunger_before=42.0)
    assert moved == 0
    assert int(agent.inventory.get("food", 0)) == 1
    assert int(world.camps["camp-001"].get("food_cache", 0)) == 0


def test_agent_can_deposit_surplus_while_keeping_self_reserve() -> None:
    world = _world()
    world.camps["camp-001"] = _active_camp(food_cache=0)
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.hunger = 42.0
    agent.inventory["food"] = 2

    moved = world.try_deposit_food_to_nearby_camp(agent, amount=2, hunger_before=42.0)
    assert moved == 1
    assert int(agent.inventory.get("food", 0)) == 1
    assert int(world.camps["camp-001"].get("food_cache", 0)) == 1


def test_agent_can_consume_from_camp_cache() -> None:
    world = _world()
    world.camps["camp-001"] = _active_camp(food_cache=2)
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.hunger = 40.0

    ate = agent.eat_if_needed(world)
    assert ate is True
    assert int(world.camps["camp-001"].get("food_cache", 0)) == 1


def test_agent_can_consume_from_nearby_camp_before_critical_threshold() -> None:
    world = _world()
    world.camps["camp-001"] = _active_camp(food_cache=2)
    agent = Agent(x=9, y=8, brain=None, is_player=False, player_id=None)
    agent.hunger = 53.0

    ate = agent.eat_if_needed(world)
    assert ate is True
    assert int(world.camps["camp-001"].get("food_cache", 0)) == 1


def test_camp_food_cache_respects_capacity() -> None:
    world = _world()
    world.camps["camp-001"] = _active_camp(food_cache=8)
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.inventory["food"] = 3
    moved = world.try_deposit_food_to_nearby_camp(agent, amount=3, hunger_before=80.0)
    assert moved == 0
    assert int(world.camps["camp-001"].get("food_cache", 0)) == 8


def test_camp_food_decays_over_time() -> None:
    world = _world()
    world.camps["camp-001"] = _active_camp(food_cache=2)
    world.tick = 50
    world.update_camp_food_decay()
    assert int(world.camps["camp-001"].get("food_cache", 0)) == 1
    snap = world.compute_camp_food_snapshot()
    assert int(snap["camp_food_decay"]) == 1


def test_no_infinite_food_generation_in_camp_loop() -> None:
    world = _world()
    world.camps["camp-001"] = _active_camp(food_cache=0)
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.inventory["food"] = 1

    deposited = world.try_deposit_food_to_nearby_camp(agent, amount=1, hunger_before=80.0)
    consumed = world.consume_food_from_nearby_camp(agent, amount=1)
    snap = world.compute_camp_food_snapshot()

    assert deposited == 1
    assert consumed == 1
    assert int(snap["total_food_in_camps"]) == 0
    assert int(snap["camp_food_deposits"]) == 1
    assert int(snap["camp_food_consumptions"]) == 1


def test_camp_food_snapshot_exposes_throughput_counters() -> None:
    world = _world()
    world.camps["camp-001"] = _active_camp(food_cache=1)
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.hunger = 55.0
    agent.inventory["food"] = 2
    world.try_deposit_food_to_nearby_camp(agent, amount=2, hunger_before=55.0)
    agent.eat_if_needed(world)
    snap = world.compute_camp_food_snapshot()

    assert "camp_food_deposit_attempts" in snap
    assert "camp_food_deposit_blocked_self_reserve" in snap
    assert "camp_food_consume_attempts" in snap
    assert "camp_food_consume_misses" in snap
    assert "food_consumed_from_camp" in snap
    assert "camp_food_consumption_share" in snap
    assert "local_food_pressure_events" in snap
    assert "pressure_backed_food_deliveries" in snap
    assert "pressure_served_ratio" in snap


def test_pressure_active_food_gatherer_prefers_camp_supply_when_carrying_food() -> None:
    world = _world()
    world.camps["camp-001"] = _active_camp(food_cache=0)
    world.food.add((9, 8))
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.proto_specialization = "food_gatherer"
    agent.proto_task_anchor = {"drop_pos": [8, 8], "source_pos": [9, 8]}
    agent.inventory["food"] = 1
    world.agents = [agent]
    world.update_agent_proto_specialization = lambda _a: None  # type: ignore[assignment]

    agent.update_role_task(world)
    assert str(agent.task) == "camp_supply_food"


def test_low_pressure_food_gatherer_falls_back_to_gathering() -> None:
    world = _world()
    world.camps["camp-001"] = _active_camp(food_cache=5)
    world.food.add((9, 8))
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.proto_specialization = "food_gatherer"
    agent.proto_task_anchor = {"drop_pos": [8, 8], "source_pos": [9, 8]}
    agent.inventory["food"] = 1
    world.agents = [agent]
    world.update_agent_proto_specialization = lambda _a: None  # type: ignore[assignment]

    agent.update_role_task(world)
    assert str(agent.task) == "gather_food_wild"


def test_pressure_backed_delivery_increments_throughput_counters() -> None:
    world = _world()
    world.camps["camp-001"] = _active_camp(food_cache=0)
    world.food.add((8, 8))
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.hunger = 80.0
    world.agents = [agent]

    world.autopickup(agent)
    snap = world.compute_camp_food_snapshot()
    assert int(snap["pressure_backed_food_deliveries"]) >= 1
    assert int(snap["loop_completed_count"]) >= 1


def test_low_value_saturated_cache_deposit_is_avoided() -> None:
    world = _world()
    world.camps["camp-001"] = _active_camp(food_cache=4)
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.hunger = 60.0
    agent.inventory["food"] = 2
    world.agents = [agent]

    moved = world.try_deposit_food_to_nearby_camp(agent, amount=1, hunger_before=60.0)
    snap = world.compute_camp_food_snapshot()
    assert moved == 0
    assert int(snap["loop_abandoned_due_to_saturated_cache"]) >= 1


def test_near_complete_loop_counters_increment_on_completion() -> None:
    world = _world()
    world.camps["camp-001"] = _active_camp(food_cache=0)
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.hunger = 85.0
    agent.inventory["food"] = 1
    world.agents = [agent]

    moved = world.try_deposit_food_to_nearby_camp(agent, amount=1, hunger_before=85.0)
    snap = world.compute_camp_food_snapshot()
    assert moved == 1
    assert int(snap["near_complete_loop_opportunities"]) >= 1
    assert int(snap["near_complete_loop_completed"]) >= 1


def test_delivery_commitment_retains_camp_supply_under_minor_noise() -> None:
    world = _world()
    world.tick = 10
    world.camps["camp-001"] = _active_camp(food_cache=0)
    agent = Agent(x=9, y=8, brain=None, is_player=False, player_id=None)
    agent.hunger = 70.0
    agent.task = "camp_supply_food"
    agent.inventory["food"] = 1
    agent.camp_loop_commit_until_tick = 20
    world.agents = [agent]
    world.update_agent_proto_specialization = lambda _a: None  # type: ignore[assignment]

    agent.update_role_task(world)
    snap = world.compute_camp_food_snapshot()
    assert str(agent.task) == "camp_supply_food"
    assert int(snap["delivery_commitment_retained_ticks"]) >= 1
    assert int(snap["completion_bias_applied_count"]) >= 1


def test_critical_hunger_overrides_delivery_commitment() -> None:
    world = _world()
    world.tick = 10
    world.camps["camp-001"] = _active_camp(food_cache=0)
    world.food.add((9, 8))
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.hunger = 10.0
    agent.task = "camp_supply_food"
    agent.inventory["food"] = 1
    agent.camp_loop_commit_until_tick = 30
    world.agents = [agent]
    world.update_agent_proto_specialization = lambda _a: None  # type: ignore[assignment]

    agent.update_role_task(world)
    assert str(agent.task) != "camp_supply_food"


def test_loop_retarget_succeeds_for_equivalent_local_food_source() -> None:
    world = _world()
    world.camps["camp-001"] = _active_camp(food_cache=0)
    world.food = {(10, 8)}
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    anchor = {"camp_id": "camp-001", "source_pos": [99, 99]}
    context = {"camp": world.camps["camp-001"]}

    ok, reason = world._validate_proto_task_anchor(agent, "food_gatherer", anchor, context)
    snap = world.compute_camp_food_snapshot()
    assert ok is True
    assert reason == ""
    assert anchor.get("source_pos") == [10, 8]
    assert int(snap["loop_retarget_success_count"]) >= 1


def test_loop_retarget_failure_recorded_when_no_equivalent_source() -> None:
    world = _world()
    world.camps["camp-001"] = _active_camp(food_cache=0)
    world.food = set()
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    anchor = {"camp_id": "camp-001", "source_pos": [99, 99]}
    context = {"camp": world.camps["camp-001"]}

    ok, reason = world._validate_proto_task_anchor(agent, "food_gatherer", anchor, context)
    snap = world.compute_camp_food_snapshot()
    assert ok is False
    assert reason in {"target_missing", "local_loop_broken"}
    assert int(snap["loop_retarget_failure_count"]) >= 1
