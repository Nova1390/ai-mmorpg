from __future__ import annotations

from agent import Agent
from world import World


def _world() -> World:
    world = World(width=24, height=24, num_agents=0, seed=777, llm_enabled=False)
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    world.villages = [
        {
            "id": 1,
            "village_uid": "v-000001",
            "center": {"x": 8, "y": 8},
            "houses": 2,
            "population": 4,
            "storage": {"food": 0, "wood": 0, "stone": 0},
            "storage_pos": {"x": 8, "y": 8},
            "tier": 1,
            "metrics": {},
        }
    ]
    return world


def test_sleep_need_increases_over_tick() -> None:
    world = _world()
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.role = "forager"
    a.village_id = 1
    a.sleep_need = 10.0
    a.fatigue = 10.0
    world.wood.add((8, 8))
    world.agents = [a]

    before = float(a.sleep_need)
    a.update(world)
    assert float(a.sleep_need) > before


def test_fatigue_increases_during_work() -> None:
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.fatigue = 10.0
    before = float(a.fatigue)
    a._add_work_fatigue(0.2)
    assert float(a.fatigue) > before


def test_rest_reduces_sleep_need_and_fatigue() -> None:
    world = _world()
    world.food.clear()
    world.wood.clear()
    world.stone.clear()
    a = Agent(x=12, y=12, brain=None, is_player=False, player_id=None)
    a.role = "npc"
    a.sleep_need = 80.0
    a.fatigue = 80.0
    world.agents = [a]

    before_sleep = float(a.sleep_need)
    before_fatigue = float(a.fatigue)
    a._apply_base_physiology_tick()
    a._apply_recovery(world, active_work=False)
    assert float(a.sleep_need) < before_sleep
    assert float(a.fatigue) < before_fatigue


def test_idle_recovery_is_weaker_than_base_sleep_accumulation() -> None:
    world = _world()
    a = Agent(x=12, y=12, brain=None, is_player=False, player_id=None)
    a.sleep_need = 50.0
    a.fatigue = 50.0

    before_sleep = float(a.sleep_need)
    before_fatigue = float(a.fatigue)
    a._apply_base_physiology_tick()
    a._apply_recovery(world, active_work=False)
    # Idle recovery remains available but very weak.
    assert float(a.sleep_need) < before_sleep
    assert (before_sleep - float(a.sleep_need)) < 0.03
    # Fatigue can still recover slowly via idle.
    assert float(a.fatigue) < before_fatigue


def test_home_rest_is_more_effective_than_idle_rest() -> None:
    world = _world()
    world.buildings["b-home"] = {
        "building_id": "b-home",
        "type": "house",
        "x": 8,
        "y": 8,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "active",
    }
    home_agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    home_agent.sleep_need = 70.0
    home_agent.fatigue = 70.0
    home_agent.home_building_id = "b-home"
    idle_agent = Agent(x=16, y=16, brain=None, is_player=False, player_id=None)
    idle_agent.sleep_need = 70.0
    idle_agent.fatigue = 70.0

    home_agent._apply_base_physiology_tick()
    idle_agent._apply_base_physiology_tick()
    home_agent._apply_recovery(world, active_work=False)
    idle_agent._apply_recovery(world, active_work=False)

    assert float(home_agent.sleep_need) < float(idle_agent.sleep_need)
    assert float(home_agent.fatigue) < float(idle_agent.fatigue)


def test_health_decreases_when_stressors_high() -> None:
    a = Agent(x=0, y=0, brain=None, is_player=False, player_id=None)
    a.hunger = 20.0
    a.sleep_need = 80.0
    a.fatigue = 90.0
    a.health = 90.0

    before = float(a.health)
    a._update_health_from_stressors()
    assert float(a.health) < before


def test_health_recovers_when_conditions_good() -> None:
    a = Agent(x=0, y=0, brain=None, is_player=False, player_id=None)
    a.hunger = 90.0
    a.sleep_need = 10.0
    a.fatigue = 10.0
    a.health = 70.0

    before = float(a.health)
    a._update_health_from_stressors()
    assert float(a.health) > before


def test_observability_exports_physiology_metrics() -> None:
    world = _world()
    a1 = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a2 = Agent(x=9, y=8, brain=None, is_player=False, player_id=None)
    a1.sleep_need = 90.0
    a1.fatigue = 85.0
    a1.health = 30.0
    a2.sleep_need = 10.0
    a2.fatigue = 20.0
    a2.health = 90.0
    world.agents = [a1, a2]

    world.metrics_collector.collect(world)
    phys = world.metrics_collector.latest()["cognition_society"]["physiology_global"]
    assert float(phys["avg_sleep_need"]) == 50.0
    assert float(phys["avg_fatigue"]) == 52.5
    assert float(phys["avg_health"]) == 60.0
    assert int(phys["high_sleep_need_agents"]) == 1
    assert int(phys["high_fatigue_agents"]) == 1
    assert int(phys["low_health_agents"]) == 1
    happiness = world.metrics_collector.latest()["cognition_society"]["happiness_global"]
    assert "avg_happiness" in happiness
    assert "low_happiness_agents" in happiness
    assert "high_happiness_agents" in happiness


def test_nearby_social_copresence_increases_happiness() -> None:
    world = _world()
    primary = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    primary.primary_village_uid = "v-000001"
    primary.village_affiliation_status = "attached"
    primary.happiness = 50.0
    ally = Agent(x=9, y=8, brain=None, is_player=False, player_id=None)
    ally.primary_village_uid = "v-000001"
    ally.village_affiliation_status = "attached"
    world.agents = [primary, ally]

    before = float(primary.happiness)
    primary._update_happiness(world, active_work=False)
    assert float(primary.happiness) > before


def test_isolation_and_stress_reduce_happiness() -> None:
    world = _world()
    a = Agent(x=12, y=12, brain=None, is_player=False, player_id=None)
    a.happiness = 60.0
    a.hunger = 20.0
    a.sleep_need = 90.0
    a.fatigue = 90.0
    a.health = 25.0
    world.agents = [a]

    before = float(a.happiness)
    a._update_happiness(world, active_work=True)
    assert float(a.happiness) < before


def test_home_rest_gives_stronger_happiness_than_camp_rest() -> None:
    world = _world()
    world.buildings["b-home"] = {
        "building_id": "b-home",
        "type": "house",
        "x": 8,
        "y": 8,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "active",
    }
    world.camps["camp-001"] = {
        "camp_id": "camp-001",
        "x": 12,
        "y": 12,
        "active": True,
        "community_id": "pc-000001",
        "created_tick": 0,
        "last_active_tick": 0,
        "absence_ticks": 0,
        "village_uid": "v-000001",
    }
    home_agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    home_agent.home_building_id = "b-home"
    home_agent.happiness = 50.0
    camp_agent = Agent(x=12, y=12, brain=None, is_player=False, player_id=None)
    camp_agent.happiness = 50.0
    world.agents = [home_agent, camp_agent]

    home_agent._update_happiness(world, active_work=False)
    camp_agent._update_happiness(world, active_work=False)
    assert float(home_agent.happiness) > float(camp_agent.happiness)


def test_happiness_modestly_improves_work_fatigue_penalty() -> None:
    low = Agent(x=0, y=0, brain=None, is_player=False, player_id=None)
    high = Agent(x=0, y=0, brain=None, is_player=False, player_id=None)
    low.happiness = 10.0
    high.happiness = 90.0
    low.fatigue = 20.0
    high.fatigue = 20.0

    low._add_work_fatigue(0.2)
    high._add_work_fatigue(0.2)
    assert float(high.fatigue) < float(low.fatigue)


def test_rest_selected_under_moderate_pressure() -> None:
    world = _world()
    world.tick = 6
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.role = "forager"
    a.village_id = 1
    a.sleep_need = 70.0
    a.fatigue = 40.0
    a.hunger = 80.0

    a.update_role_task(world)
    assert str(a.task) == "rest"


def test_urgent_survival_overrides_rest() -> None:
    world = _world()
    world.tick = 6
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.role = "forager"
    a.village_id = 1
    a.sleep_need = 90.0
    a.fatigue = 90.0
    a.happiness = 95.0
    a.hunger = 15.0

    a.update_role_task(world)
    assert str(a.task) != "rest"


def test_no_trivial_infinite_rest_when_pressure_low() -> None:
    world = _world()
    world.tick = 6
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.role = "forager"
    a.village_id = 1
    a.sleep_need = 20.0
    a.fatigue = 20.0
    a.hunger = 80.0

    a.update_role_task(world)
    assert str(a.task) == "gather_food_wild"
