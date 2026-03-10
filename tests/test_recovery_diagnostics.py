from __future__ import annotations

from agent import Agent
from world import World


def _world() -> World:
    world = World(width=24, height=24, num_agents=0, seed=1201, llm_enabled=False)
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    world.villages = [
        {
            "id": 1,
            "village_uid": "v-000001",
            "center": {"x": 8, "y": 8},
            "houses": 2,
            "population": 5,
            "storage": {"food": 4, "wood": 0, "stone": 0},
            "storage_pos": {"x": 8, "y": 8},
            "tier": 1,
            "metrics": {},
        }
    ]
    return world


def test_high_pressure_increments_recovery_context_and_pressure_stages() -> None:
    world = _world()
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.role = "forager"
    a.village_id = 1
    a.sleep_need = 92.0
    a.fatigue = 83.0
    world.agents = [a]

    a.update(world)
    diag = world.compute_recovery_diagnostics_snapshot()["global"]
    assert int(diag["recovery_context_seen"]) >= 1
    assert int(diag["high_sleep_need_seen"]) >= 1
    assert int(diag["high_fatigue_seen"]) >= 1
    assert int(diag["rest_candidate_seen"]) >= 1


def test_rest_task_selection_increments_stage() -> None:
    world = _world()
    world.tick = 9
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.role = "forager"
    a.village_id = 1
    a.sleep_need = 95.0
    a.fatigue = 20.0
    a.hunger = 80.0
    a.update_role_task(world)

    diag = world.compute_recovery_diagnostics_snapshot()["global"]
    assert str(a.task) == "rest"
    assert int(diag["rest_task_selected"]) >= 1


def test_missing_home_records_no_home_or_not_resident() -> None:
    world = _world()
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.role = "forager"
    a.village_id = 1
    a.sleep_need = 95.0
    a.fatigue = 20.0
    a.hunger = 80.0
    world.tick = 10
    world.agents = [a]

    a.update(world)
    reasons = world.compute_recovery_diagnostics_snapshot()["global"]["failure_reasons"]
    assert int(reasons.get("no_home", 0)) >= 1
    assert int(reasons.get("not_resident", 0)) >= 1


def test_idle_recovery_stage_increments() -> None:
    world = _world()
    a = Agent(x=5, y=5, brain=None, is_player=False, player_id=None)
    a.role = "npc"
    a.sleep_need = 80.0
    a.fatigue = 80.0
    world.agents = [a]

    a._apply_base_physiology_tick()
    a._apply_recovery(world, active_work=False)
    diag = world.compute_recovery_diagnostics_snapshot()["global"]
    assert int(diag["idle_recovery_applied"]) >= 1
    assert int(diag["recovery_success_tick"]) >= 1


def test_home_recovery_stage_increments() -> None:
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
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.role = "npc"
    a.home_building_id = "b-home"
    a.sleep_need = 75.0
    a.fatigue = 75.0
    world.agents = [a]

    a._apply_base_physiology_tick()
    a._apply_recovery(world, active_work=False)
    diag = world.compute_recovery_diagnostics_snapshot()["global"]
    assert int(diag["home_recovery_applied"]) >= 1
    assert int(diag["recovery_success_tick"]) >= 1


def test_observability_includes_recovery_diagnostics_fields() -> None:
    world = _world()
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.role = "forager"
    a.village_id = 1
    a.sleep_need = 90.0
    a.fatigue = 85.0
    world.agents = [a]

    a.update(world)
    world.metrics_collector.collect(world)
    cog = world.metrics_collector.latest()["cognition_society"]
    assert "recovery_diagnostics_global" in cog
    assert "recovery_diagnostics_by_role" in cog
    assert "recovery_diagnostics_by_village" in cog
