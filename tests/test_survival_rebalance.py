from __future__ import annotations

from agent import Agent, EARLY_FOOD_RELIABILITY_TICKS
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


def test_early_food_priority_override_applies_before_first_food_relief() -> None:
    world = _world()
    world.tick = 40
    world.food.add((11, 10))
    a = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    a.role = "builder"
    a.hunger = 40.0
    a.born_tick = 0
    a.first_food_relief_tick = -1

    a.update_role_task(world)

    assert str(a.task) == "gather_food_wild"
    assert isinstance(a.task_target, tuple) and len(a.task_target) == 2
    snap = world.compute_settlement_progression_snapshot()
    assert int(snap.get("early_food_priority_overrides", 0)) >= 1


def test_food_relief_latency_and_hunger_death_buckets_are_recorded() -> None:
    world = _world()
    a = Agent(x=5, y=5, brain=None, is_player=False, player_id=None)
    a.born_tick = 0
    a.high_hunger_enter_tick = 40
    world.add_agent(a)

    world.tick = 55
    world.record_agent_food_relief(a, source="inventory")
    snap = world.compute_settlement_progression_snapshot()
    assert float(snap.get("avg_time_spawn_to_first_food_acquisition", 0.0)) >= 55.0
    assert float(snap.get("avg_time_high_hunger_to_eat", 0.0)) >= 15.0

    b = Agent(x=6, y=6, brain=None, is_player=False, player_id=None)
    b.born_tick = 0
    b.first_food_relief_tick = -1
    world.add_agent(b)
    world.tick = min(199, int(EARLY_FOOD_RELIABILITY_TICKS // 2))
    world.set_agent_dead(b, reason="hunger")
    snap = world.compute_settlement_progression_snapshot()
    assert int(snap.get("hunger_deaths_before_first_food_acquisition", 0)) >= 1
    assert int(snap.get("population_deaths_hunger_age_0_199_count", 0)) >= 1


def test_medium_term_food_continuity_override_with_existing_village() -> None:
    world = _world()
    world.tick = 420
    world.food.add((12, 10))
    village = {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 10, "y": 10},
        "population": 4,
        "houses": 1,
        "storage": {"food": 0, "wood": 0, "stone": 0},
        "needs": {},
        "priority": "build_housing",
        "formalized": False,
    }
    world.villages = [village]
    a = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    a.village_id = 1
    a.role = "builder"
    a.first_food_relief_tick = 120
    a.hunger = 38.0
    a.inventory["food"] = 0
    a.high_hunger_episode_count = 2

    a.update_role_task(world)

    assert str(a.task) == "gather_food_wild"
    snap = world.compute_settlement_progression_snapshot()
    assert int(snap.get("medium_term_food_priority_overrides", 0)) >= 1


def test_food_continuity_intervals_and_relapse_are_recorded() -> None:
    world = _world()
    a = Agent(x=5, y=5, brain=None, is_player=False, player_id=None)
    a.born_tick = 0
    world.add_agent(a)

    world.tick = 50
    world.record_agent_food_inventory_acquired(a, amount=1, source="wild_direct")
    world.tick = 70
    world.record_agent_food_inventory_acquired(a, amount=1, source="wild_direct")
    world.tick = 90
    world.record_agent_food_relief(a, source="inventory")
    world.tick = 105
    a.high_hunger_enter_tick = 100
    a.first_food_relief_tick = 90
    world.record_settlement_progression_metric("agent_hunger_relapse_after_first_food_count")
    world.record_agent_food_relief(a, source="camp")

    snap = world.compute_settlement_progression_snapshot()
    assert float(snap.get("avg_food_acquisition_interval_ticks", 0.0)) >= 20.0
    assert float(snap.get("avg_food_consumption_interval_ticks", 0.0)) >= 15.0
    assert int(snap.get("agent_hunger_relapse_after_first_food_count", 0)) >= 1


def test_scarcity_adaptive_food_target_avoids_high_contention_when_possible() -> None:
    world = _world()
    world.food.update({(9, 8), (14, 8)})
    world.camps["camp-001"] = _camp(x=8, y=8, food_cache=0)

    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.task = "gather_food_wild"
    world.add_agent(agent)

    competitor = Agent(x=9, y=7, brain=None, is_player=False, player_id=None)
    competitor.task = "gather_food_wild"
    competitor.task_target = (9, 8)
    world.add_agent(competitor)

    target = world.find_scarcity_adaptive_food_target(agent, radius=10)

    assert target == (14, 8)


def test_local_food_basin_metrics_are_exposed_in_snapshot() -> None:
    world = _world()
    world.camps["camp-001"] = _camp(x=8, y=8, food_cache=0)
    world.food.add((8, 9))
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.task = "gather_food_wild"
    world.add_agent(a)

    world.update_settlement_progression_metrics()
    snap = world.compute_settlement_progression_snapshot()

    assert "avg_local_food_basin_accessible" in snap
    assert "avg_local_food_pressure_ratio" in snap
    assert "avg_distance_to_viable_food_from_proto" in snap
    assert "food_scarcity_adaptive_retarget_events" in snap
