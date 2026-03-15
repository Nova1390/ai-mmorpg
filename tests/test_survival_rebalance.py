from __future__ import annotations

import types

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


def test_local_food_handoff_transfers_food_between_nearby_agents() -> None:
    world = _world()
    donor = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    donor.hunger = 70.0
    donor.inventory["food"] = 3
    receiver = Agent(x=11, y=10, brain=None, is_player=False, player_id=None)
    receiver.hunger = 19.0
    receiver.inventory["food"] = 0
    world.agents = [donor, receiver]
    world.tick = 120

    world.run_local_food_handoff_pass()

    assert int(donor.inventory.get("food", 0)) == 2
    assert int(receiver.inventory.get("food", 0)) == 1
    snap = world.compute_settlement_progression_snapshot()
    assert int(snap.get("local_food_handoff_events", 0)) >= 1
    assert int(snap.get("local_food_handoff_units", 0)) >= 1


def test_hunger_relief_after_local_handoff_records_on_inventory_consumption() -> None:
    world = _world()
    donor = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    donor.hunger = 70.0
    donor.inventory["food"] = 3
    receiver = Agent(x=11, y=10, brain=None, is_player=False, player_id=None)
    receiver.hunger = 19.0
    receiver.inventory["food"] = 0
    world.agents = [donor, receiver]
    world.tick = 140

    world.run_local_food_handoff_pass()
    receiver.eat_if_needed(world)

    snap = world.compute_settlement_progression_snapshot()
    assert float(snap.get("hunger_relief_after_local_handoff", 0.0)) > 0.0


def test_local_food_handoff_cooldown_blocks_immediate_repeat() -> None:
    world = _world()
    donor = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    donor.hunger = 80.0
    donor.inventory["food"] = 3
    receiver = Agent(x=11, y=10, brain=None, is_player=False, player_id=None)
    receiver.hunger = 19.0
    receiver.inventory["food"] = 0
    world.agents = [donor, receiver]
    world.tick = 200

    world.run_local_food_handoff_pass()
    first_donor_food = int(donor.inventory.get("food", 0))
    receiver.inventory["food"] = 0
    world.tick = 201
    world.run_local_food_handoff_pass()

    assert int(donor.inventory.get("food", 0)) == first_donor_food
    snap = world.compute_settlement_progression_snapshot()
    assert int(snap.get("handoff_blocked_by_cooldown_count", 0)) >= 1


def test_local_food_handoff_blocked_by_group_priority_under_crisis_pressure() -> None:
    world = _world()
    donor = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    donor.hunger = 80.0
    donor.inventory["food"] = 3
    receiver = Agent(x=11, y=10, brain=None, is_player=False, player_id=None)
    receiver.hunger = 19.0
    receiver.inventory["food"] = 0
    world.agents = [donor, receiver]
    world.tick = 250

    def _mock_pressure(self, agent, max_distance=8):
        return {
            "pressure_active": True,
            "unmet_pressure": True,
            "camp_food": 0,
            "nearby_needy_agents": 3,
        }

    world.compute_local_food_pressure_for_agent = types.MethodType(_mock_pressure, world)
    world.run_local_food_handoff_pass()

    assert int(donor.inventory.get("food", 0)) == 3
    assert int(receiver.inventory.get("food", 0)) == 0
    snap = world.compute_settlement_progression_snapshot()
    assert int(snap.get("handoff_blocked_by_group_priority_count", 0)) >= 1


def test_local_food_handoff_blocked_by_receiver_viability_when_adjacent_food_exists() -> None:
    world = _world()
    donor = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    donor.hunger = 80.0
    donor.inventory["food"] = 3
    receiver = Agent(x=11, y=10, brain=None, is_player=False, player_id=None)
    receiver.hunger = 19.0
    receiver.inventory["food"] = 0
    world.food.add((11, 11))
    world.agents = [donor, receiver]
    world.tick = 300

    world.run_local_food_handoff_pass()

    assert int(donor.inventory.get("food", 0)) == 3
    assert int(receiver.inventory.get("food", 0)) == 0
    snap = world.compute_settlement_progression_snapshot()
    assert int(snap.get("handoff_blocked_by_receiver_viability", 0)) >= 1


def test_local_food_handoff_allows_critical_receiver_despite_adjacent_food() -> None:
    world = _world()
    donor = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    donor.hunger = 80.0
    donor.inventory["food"] = 3
    receiver = Agent(x=11, y=10, brain=None, is_player=False, player_id=None)
    receiver.hunger = 10.0
    receiver.inventory["food"] = 0
    world.food.add((11, 11))
    world.agents = [donor, receiver]
    world.tick = 305

    world.run_local_food_handoff_pass()

    assert int(donor.inventory.get("food", 0)) == 2
    assert int(receiver.inventory.get("food", 0)) == 1
    snap = world.compute_settlement_progression_snapshot()
    assert int(snap.get("local_food_handoff_events", 0)) >= 1


def test_local_food_handoff_blocked_by_camp_fragility() -> None:
    world = _world()
    world.camps["camp-001"] = _camp(x=10, y=10, food_cache=1)
    donor = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    donor.hunger = 80.0
    donor.inventory["food"] = 3
    receiver = Agent(x=11, y=10, brain=None, is_player=False, player_id=None)
    receiver.hunger = 19.0
    receiver.inventory["food"] = 0
    world.agents = [donor, receiver]
    world.tick = 320

    world.run_local_food_handoff_pass()

    assert int(donor.inventory.get("food", 0)) == 3
    assert int(receiver.inventory.get("food", 0)) == 0
    snap = world.compute_settlement_progression_snapshot()
    assert int(snap.get("handoff_blocked_by_camp_fragility", 0)) >= 1


def test_camp_fragility_diagnostics_capture_block_context() -> None:
    world = _world()
    world.camps["camp-001"] = _camp(x=10, y=10, food_cache=1)
    donor = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    donor.hunger = 85.0
    donor.inventory["food"] = 4
    receiver = Agent(x=11, y=10, brain=None, is_player=False, player_id=None)
    receiver.hunger = 10.0
    receiver.inventory["food"] = 0
    world.agents = [donor, receiver]
    world.tick = 340

    world.run_local_food_handoff_pass()

    snap = world.compute_settlement_progression_snapshot()
    assert int(snap.get("handoff_blocked_by_camp_fragility_when_receiver_critical_count", 0)) >= 1
    assert int(snap.get("handoff_blocked_by_camp_fragility_when_donor_safe_count", 0)) >= 1
    assert float(snap.get("avg_handoff_blocked_by_camp_fragility_donor_food", 0.0)) >= 4.0
    assert float(snap.get("avg_handoff_blocked_by_camp_fragility_receiver_hunger", 0.0)) <= 10.0


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


def test_foraging_trip_harvest_updates_trip_efficiency_metrics() -> None:
    world = _world()
    world.food.add((8, 8))
    a = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a.task = "gather_food_wild"
    a.foraging_trip_active = True
    a.foraging_trip_move_ticks = 5
    world.add_agent(a)

    world.autopickup(a)
    world.record_settlement_progression_metric("foraging_trip_completed_count")
    world.record_settlement_progression_metric("foraging_trip_movement_ticks_total", int(a.foraging_trip_move_ticks))
    world.record_settlement_progression_metric("foraging_trip_food_gained_total", int(a.foraging_trip_harvest_units))
    world.record_settlement_progression_metric("foraging_trip_harvest_actions_total", int(a.foraging_trip_harvest_actions))
    world.settlement_progression_stats["foraging_trip_efficiency_ratio_sum"] = (
        float(a.foraging_trip_harvest_units) / float(max(1, a.foraging_trip_move_ticks))
    )
    world.settlement_progression_stats["foraging_trip_efficiency_ratio_samples"] = 1

    snap = world.compute_settlement_progression_snapshot()
    assert int(snap.get("foraging_trip_completed_count", 0)) >= 1
    assert int(snap.get("foraging_source_visit_count", 0)) >= 0
    assert float(snap.get("avg_foraging_trip_move_before_first_harvest", 0.0)) >= 5.0
    assert float(snap.get("avg_foraging_trip_efficiency_ratio", 0.0)) > 0.0


def test_foraging_commitment_hold_applies_in_high_pressure() -> None:
    world = _world()
    world.tick = 300
    world.food.add((9, 8))
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.task = "gather_food_wild"
    agent.hunger = 46.0
    agent.inventory["food"] = 1
    agent.foraging_trip_active = True
    agent.foraging_trip_harvest_units = 1
    world.add_agent(agent)

    def _pressure(*_args, **_kwargs):
        return {
            "near_food_sources": 1,
            "camp_food": 0,
            "house_food_nearby": 0,
            "nearby_needy_agents": 2,
            "pressure_active": True,
        }

    def _role_update(self, _world):
        self.task = "gather_materials"

    world.compute_local_food_pressure_for_agent = _pressure  # type: ignore[attr-defined]
    agent.update_role_task = types.MethodType(_role_update, agent)
    agent.update(world)

    assert str(agent.task) == "gather_food_wild"
    snap = world.compute_settlement_progression_snapshot()
    assert int(snap.get("foraging_commitment_hold_overrides", 0)) >= 1


def test_foraging_commitment_hold_stays_fluid_in_low_pressure() -> None:
    world = _world()
    world.tick = 300
    world.food.add((9, 8))
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.task = "gather_food_wild"
    agent.hunger = 46.0
    agent.inventory["food"] = 6
    agent.foraging_trip_active = True
    agent.foraging_trip_harvest_units = 2
    world.add_agent(agent)

    def _pressure(*_args, **_kwargs):
        return {
            "near_food_sources": 4,
            "camp_food": 1,
            "house_food_nearby": 1,
            "nearby_needy_agents": 1,
            "pressure_active": False,
        }

    def _role_update(self, _world):
        self.task = "gather_materials"

    world.compute_local_food_pressure_for_agent = _pressure  # type: ignore[attr-defined]
    agent.update_role_task = types.MethodType(_role_update, agent)
    agent.update(world)

    assert str(agent.task) == "gather_materials"


def test_foraging_high_pressure_hysteresis_keeps_regime_stable() -> None:
    world = _world()
    world.tick = 320
    world.food.add((9, 8))
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.task = "gather_food_wild"
    agent.hunger = 44.0
    agent.inventory["food"] = 1
    agent.foraging_trip_active = True
    agent.foraging_trip_harvest_units = 1
    agent.foraging_pressure_regime = "high"
    world.add_agent(agent)

    def _pressure(*_args, **_kwargs):
        return {
            "near_food_sources": 2,
            "camp_food": 1,
            "house_food_nearby": 0,
            "nearby_needy_agents": 4,  # ratio=1.33 (below high-enter, above high-exit)
            "pressure_active": True,
        }

    def _role_update(self, _world):
        self.task = "gather_materials"

    world.compute_local_food_pressure_for_agent = _pressure  # type: ignore[attr-defined]
    agent.update_role_task = types.MethodType(_role_update, agent)
    agent.update(world)

    assert str(agent.foraging_pressure_regime) == "high"
    assert str(agent.task) == "gather_food_wild"


def test_foraging_high_pressure_hysteresis_can_exit_to_medium() -> None:
    world = _world()
    world.tick = 320
    world.food.add((9, 8))
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.task = "gather_food_wild"
    agent.hunger = 44.0
    agent.inventory["food"] = 1
    agent.foraging_trip_active = True
    agent.foraging_trip_harvest_units = 1
    agent.foraging_pressure_regime = "high"
    world.add_agent(agent)

    def _pressure(*_args, **_kwargs):
        return {
            "near_food_sources": 2,
            "camp_food": 1,
            "house_food_nearby": 1,
            "nearby_needy_agents": 2,  # ratio=0.5
            "pressure_active": False,
        }

    def _role_update(self, _world):
        self.task = "gather_materials"

    world.compute_local_food_pressure_for_agent = _pressure  # type: ignore[attr-defined]
    agent.update_role_task = types.MethodType(_role_update, agent)
    agent.update(world)

    assert str(agent.foraging_pressure_regime) in {"low", "medium"}
    assert str(agent.task) == "gather_materials"


def test_post_first_harvest_patch_persistence_holds_trip_in_medium_pressure() -> None:
    world = _world()
    world.tick = 480
    world.food.add((8, 8))
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.task = "gather_food_wild"
    agent.hunger = 46.0
    agent.inventory["food"] = 1
    agent.foraging_trip_active = True
    agent.foraging_trip_harvest_units = 1
    agent.foraging_trip_first_harvest_tick = 478
    agent.task_target = (8, 8)
    world.add_agent(agent)

    def _pressure(*_args, **_kwargs):
        return {
            "near_food_sources": 2,
            "camp_food": 1,
            "house_food_nearby": 0,
            "nearby_needy_agents": 3,  # ratio = 1.0 -> medium
            "pressure_active": False,
        }

    def _role_update(self, _world):
        self.task = "gather_materials"

    agent.foraging_pressure_regime = "medium"
    world.compute_local_food_pressure_for_agent = _pressure  # type: ignore[attr-defined]
    agent.update_role_task = types.MethodType(_role_update, agent)
    agent.update(world)

    assert str(agent.task) == "gather_food_wild"


def test_post_first_harvest_hold_can_handoff_to_nearby_patch() -> None:
    world = _world()
    world.tick = 500
    world.food.add((9, 8))
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.task = "gather_food_wild"
    agent.hunger = 48.0
    agent.inventory["food"] = 6
    agent.foraging_trip_active = True
    agent.foraging_trip_harvest_units = 1
    agent.foraging_trip_first_harvest_tick = 498
    agent.task_target = (8, 8)  # depleted target
    agent.foraging_trip_target = (8, 8)
    agent.foraging_pressure_regime = "high"
    world.add_agent(agent)

    def _pressure(*_args, **_kwargs):
        return {
            "near_food_sources": 1,
            "camp_food": 0,
            "house_food_nearby": 0,
            "nearby_needy_agents": 2,
            "pressure_active": True,
        }

    def _role_update(self, _world):
        self.task = "gather_materials"

    world.compute_local_food_pressure_for_agent = _pressure  # type: ignore[attr-defined]
    agent.update_role_task = types.MethodType(_role_update, agent)
    agent.update(world)

    assert str(agent.task) == "gather_food_wild"
    assert tuple(agent.task_target or ()) == (9, 8)


def test_post_first_harvest_hold_blocks_camp_supply_food_switch() -> None:
    world = _world()
    world.tick = 540
    world.food.add((8, 8))
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.task = "gather_food_wild"
    agent.hunger = 42.0
    agent.inventory["food"] = 1
    agent.foraging_trip_active = True
    agent.foraging_trip_harvest_units = 1
    agent.foraging_trip_first_harvest_tick = 538
    agent.foraging_patch_exploit_until_tick = 552
    agent.foraging_patch_exploit_target_harvest_actions = 4
    agent.task_target = (8, 8)
    world.add_agent(agent)

    def _pressure(*_args, **_kwargs):
        return {
            "near_food_sources": 1,
            "camp_food": 0,
            "house_food_nearby": 0,
            "nearby_needy_agents": 1,
            "pressure_active": False,
        }

    def _role_update(self, _world):
        self.task = "camp_supply_food"

    world.compute_local_food_pressure_for_agent = _pressure  # type: ignore[attr-defined]
    agent.update_role_task = types.MethodType(_role_update, agent)
    agent.update(world)
    assert str(agent.task) == "gather_food_wild"


def test_post_first_harvest_narrow_guard_does_not_block_when_food_not_nearby() -> None:
    world = _world()
    world.tick = 560
    world.food.add((20, 20))
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.task = "gather_food_wild"
    agent.hunger = 42.0
    agent.inventory["food"] = 1
    agent.foraging_trip_active = True
    agent.foraging_trip_harvest_units = 1
    agent.foraging_trip_harvest_actions = 1
    agent.foraging_trip_first_harvest_tick = 520
    agent.foraging_patch_exploit_until_tick = 530
    agent.foraging_patch_exploit_target_harvest_actions = 4
    agent.task_target = (8, 8)
    world.add_agent(agent)

    def _pressure(*_args, **_kwargs):
        return {
            "near_food_sources": 0,
            "camp_food": 0,
            "house_food_nearby": 0,
            "nearby_needy_agents": 2,
            "pressure_active": True,
        }

    def _role_update(self, _world):
        self.task = "camp_supply_food"

    world.compute_local_food_pressure_for_agent = _pressure  # type: ignore[attr-defined]
    agent.update_role_task = types.MethodType(_role_update, agent)
    agent.update(world)
    assert str(agent.task) == "camp_supply_food"


def test_patch_exploitation_window_is_bounded_by_target_harvest_actions() -> None:
    world = _world()
    world.tick = 520
    world.food.add((9, 8))
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.task = "gather_food_wild"
    agent.hunger = 48.0
    agent.inventory["food"] = 6
    agent.foraging_trip_active = True
    agent.foraging_trip_harvest_units = 2
    agent.foraging_trip_harvest_actions = 4
    agent.foraging_trip_first_harvest_tick = 480
    agent.foraging_patch_exploit_until_tick = 540
    agent.foraging_patch_exploit_target_harvest_actions = 4
    agent.task_target = (8, 8)
    world.add_agent(agent)

    def _pressure(*_args, **_kwargs):
        return {
            "near_food_sources": 1,
            "camp_food": 0,
            "house_food_nearby": 0,
            "nearby_needy_agents": 2,
            "pressure_active": True,
        }

    def _role_update(self, _world):
        self.task = "gather_materials"

    world.compute_local_food_pressure_for_agent = _pressure  # type: ignore[attr-defined]
    agent.update_role_task = types.MethodType(_role_update, agent)
    agent.update(world)

    assert str(agent.task) == "gather_materials"

def test_material_feasibility_snapshot_exposes_resource_stock_flow_basics() -> None:
    world = _world()
    world.food.update({(1, 1), (2, 2)})
    world.wood.update({(3, 3)})
    world.stone.update({(4, 4)})
    world.initial_resource_stock = {"food": 10, "wood": 8, "stone": 6}
    a = Agent(x=5, y=5, brain=None, is_player=False, player_id=None)
    a.inventory["wood"] = 2
    a.inventory["stone"] = 1
    a.inventory["food"] = 1
    world.agents = [a]

    snap = world.compute_material_feasibility_snapshot()

    assert int(snap.get("resource_conservation_raw_material_fabrication_detected", 1)) == 0
    assert int(snap.get("wood_initial_world_stock_estimate", 0)) == 8
    assert int(snap.get("stone_initial_world_stock_estimate", 0)) == 6
    assert int(snap.get("food_initial_world_stock_estimate", 0)) == 10
    assert int(snap.get("wood_available_world_total", 0)) >= 3
    assert int(snap.get("stone_available_world_total", 0)) >= 2
    assert int(snap.get("food_available_world_total", 0)) >= 3
    assert "construction_site_nearest_wood_distance_avg" in snap
    assert "construction_delivery_failure_no_source_available" in snap
