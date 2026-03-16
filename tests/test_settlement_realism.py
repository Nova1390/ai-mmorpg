from __future__ import annotations

import random

from agent import (
    AGENT_START_HUNGER,
    BASE_HUNGER_DECAY_PER_TICK,
    EARLY_HUNGER_DECAY_MULTIPLIER,
    STARTUP_NO_SHELTER_HUNGER_DECAY_MULTIPLIER,
    Agent,
)
from brain import FoodBrain
from world import World
import systems.building_system as building_system
import systems.village_system as village_system


def _spawn_agent(world: World, x: int, y: int) -> Agent:
    a = Agent(x=x, y=y, brain=FoodBrain(), is_player=False, player_id=None)
    world.add_agent(a)
    return a


def test_village_formalization_requires_stability_window() -> None:
    world = World(width=30, height=30, seed=11)
    world.structures = {(10, 10), (11, 10), (10, 11)}
    world.camps = {"c1": {"active": True, "x": 10, "y": 10, "support_score": 6}}
    for _ in range(4):
        _spawn_agent(world, 10, 10)

    for _ in range(30):
        world.tick += 1
        village_system.detect_villages(world)
    assert world.villages
    assert world.villages[0].get("formalized") is False

    for _ in range(80):
        world.tick += 1
        village_system.detect_villages(world)
    assert world.villages[0].get("formalized") is True


def test_ghost_village_downgrades_after_low_viability() -> None:
    world = World(width=30, height=30, seed=22)
    world.structures = {(10, 10), (11, 10), (10, 11)}
    world.camps = {"c1": {"active": True, "x": 10, "y": 10, "support_score": 6}}
    for _ in range(4):
        _spawn_agent(world, 10, 10)

    for _ in range(120):
        world.tick += 1
        village_system.detect_villages(world)
    assert world.villages and world.villages[0].get("formalized") is True

    world.agents = []
    for _ in range(90):
        world.tick += 1
        village_system.detect_villages(world)
    assert world.villages[0].get("formalized") is False
    assert world.villages[0].get("settlement_stage") == "proto_settlement"


def test_storage_maturity_requires_formalized_stable_village() -> None:
    world = World(width=30, height=30, seed=33)
    village = {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 10, "y": 10},
        "population": 8,
        "houses": 4,
        "formalized": False,
        "stability_ticks": 120,
        "storage": {"food": 20, "wood": 10, "stone": 8},
        "needs": {"need_storage": True},
        "production_metrics": {},
    }
    world.villages = [village]
    for pos in ((10, 10), (11, 10), (10, 11), (11, 11)):
        world.place_building("house", pos[0], pos[1], village_id=1, village_uid="v-000001")

    snap = building_system._storage_maturity_snapshot(world, village)
    assert snap["formalized_ready"] is False
    assert snap["mature_ready"] is False


def test_road_growth_deferred_for_non_formalized_village() -> None:
    world = World(width=30, height=30, seed=44)
    village = {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 10, "y": 10},
        "population": 8,
        "houses": 4,
        "formalized": False,
        "stability_ticks": 200,
        "storage": {"food": 20, "wood": 0, "stone": 0},
        "needs": {},
        "metrics": {"population": 8, "food_stock": 20},
    }
    should_defer, reason = world.should_defer_road_growth_for_village(village)
    assert should_defer is True
    assert reason == "village_not_formalized"


def test_startup_survival_relief_reduces_hunger_decay_without_shelter() -> None:
    world = World(width=30, height=30, seed=55)
    world.villages = []
    world.structures.clear()
    world.tick = 10
    agent = Agent(5, 5, FoodBrain(), False, None)
    agent.hunger = float(AGENT_START_HUNGER)
    world.add_agent(agent)

    # keep update deterministic and non-moving for this assertion
    random.seed(1)
    before = float(agent.hunger)
    agent.update(world)
    after = float(agent.hunger)
    observed_decay = before - after
    expected_decay = float(BASE_HUNGER_DECAY_PER_TICK) * float(EARLY_HUNGER_DECAY_MULTIPLIER) * float(
        STARTUP_NO_SHELTER_HUNGER_DECAY_MULTIPLIER
    )
    assert observed_decay <= expected_decay + 1e-6
    snap = world.compute_settlement_progression_snapshot()
    assert int(snap.get("startup_survival_relief_ticks", 0)) >= 1


def test_reproduction_requires_formalized_local_stability() -> None:
    world = World(width=30, height=30, seed=66)
    world.tick = 500
    village = {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 10, "y": 10},
        "population": 5,
        "houses": 3,
        "formalized": False,
        "stability_ticks": 120,
        "storage": {"food": 20, "wood": 0, "stone": 0},
    }
    world.villages = [village]
    a1 = _spawn_agent(world, 10, 10)
    a2 = _spawn_agent(world, 11, 10)
    a1.village_id = 1
    a2.village_id = 1
    a1.born_tick = 0
    a2.born_tick = 0
    a1.hunger = 95.0
    a2.hunger = 95.0
    start_count = len(world.agents)
    a1.try_reproduce(world)
    assert len(world.agents) == start_count

    village["formalized"] = True
    random_state = random.random
    try:
        random.random = lambda: 0.0
        a1.repro_cooldown = 0
        a1.try_reproduce(world)
    finally:
        random.random = random_state
    assert len(world.agents) >= start_count + 1
    snap = world.compute_settlement_progression_snapshot()
    assert int(snap.get("population_births_count", 0)) >= 1


def test_reproduction_requires_opposite_biological_sex_partner() -> None:
    world = World(width=30, height=30, seed=67)
    world.tick = 500
    world.villages = [
        {
            "id": 1,
            "village_uid": "v-000001",
            "center": {"x": 10, "y": 10},
            "population": 5,
            "houses": 3,
            "formalized": True,
            "stability_ticks": 200,
            "storage": {"food": 20, "wood": 0, "stone": 0},
        }
    ]
    a1 = _spawn_agent(world, 10, 10)
    a2 = _spawn_agent(world, 11, 10)
    a1.village_id = 1
    a2.village_id = 1
    a1.born_tick = 0
    a2.born_tick = 0
    a1.hunger = 95.0
    a2.hunger = 95.0
    a1.biological_sex = "female"
    a2.biological_sex = "female"
    start_count = len(world.agents)

    a1.try_reproduce(world)

    assert len(world.agents) == start_count
    snap = world.compute_settlement_progression_snapshot()
    assert int(snap.get("reproduction_blocked_by_no_opposite_sex_partner_count", 0)) >= 1


def test_reproduction_proto_path_allows_stable_proto_settlement_birth() -> None:
    world = World(width=30, height=30, seed=68)
    world.tick = 500
    world.villages = [
        {
            "id": 1,
            "village_uid": "v-000001",
            "center": {"x": 10, "y": 10},
            "population": 6,
            "houses": 3,
            "formalized": False,
            "settlement_stage": "proto_settlement",
            "stability_ticks": 180,
            "storage": {"food": 24, "wood": 0, "stone": 0},
        }
    ]
    a1 = _spawn_agent(world, 10, 10)
    a2 = _spawn_agent(world, 11, 10)
    a1.village_id = 1
    a2.village_id = 1
    a1.born_tick = 0
    a2.born_tick = 0
    a1.hunger = 95.0
    a2.hunger = 95.0
    a1.biological_sex = "female"
    a2.biological_sex = "male"
    start_count = len(world.agents)

    random_state = random.random
    try:
        random.random = lambda: 0.0
        a1.repro_cooldown = 0
        a2.repro_cooldown = 0
        a1.try_reproduce(world)
    finally:
        random.random = random_state

    assert len(world.agents) >= start_count + 1
    snap = world.compute_settlement_progression_snapshot()
    assert int(snap.get("reproduction_proto_path_activated_count", 0)) >= 1
    assert int(snap.get("population_births_count", 0)) >= 1


def test_reproduction_proto_food_security_continuity_window_can_unlock_proto_path() -> None:
    world = World(width=30, height=30, seed=69)
    world.tick = 500
    world.villages = [
        {
            "id": 1,
            "village_uid": "v-000001",
            "center": {"x": 10, "y": 10},
            "population": 6,
            "houses": 3,
            "formalized": False,
            "settlement_stage": "proto_settlement",
            "stability_ticks": 180,
            "storage": {"food": 0, "wood": 0, "stone": 0},
        }
    ]
    a1 = _spawn_agent(world, 10, 10)
    a2 = _spawn_agent(world, 11, 10)
    a1.village_id = 1
    a2.village_id = 1
    a1.born_tick = 0
    a2.born_tick = 0
    a1.hunger = 95.0
    a2.hunger = 95.0
    a1.biological_sex = "female"
    a2.biological_sex = "male"

    world.compute_local_food_pressure_for_agent = lambda _a, max_distance=8: {  # type: ignore[assignment]
        "pressure_active": False,
        "unmet_pressure": False,
        "camp_food": 1,
        "house_food_nearby": 1,
        "near_food_sources": 2,
    }
    random_state = random.random
    try:
        random.random = lambda: 0.99
        for _ in range(15):
            world.tick += 1
            a1.repro_cooldown = 0
            a1.try_reproduce(world)
    finally:
        random.random = random_state

    snap = world.compute_settlement_progression_snapshot()
    assert int(snap.get("proto_food_security_window_pass_count", 0)) >= 1
    assert int(snap.get("reproduction_proto_path_activated_count", 0)) >= 1


def test_stable_proto_household_path_can_activate_without_village_id() -> None:
    world = World(width=30, height=30, seed=70)
    world.tick = 520
    world.villages = [
        {
            "id": 1,
            "village_uid": "v-000001",
            "center": {"x": 10, "y": 10},
            "population": 6,
            "houses": 3,
            "formalized": False,
            "settlement_stage": "proto_settlement",
            "stability_ticks": 220,
            "storage": {"food": 0, "wood": 0, "stone": 0},
        }
    ]
    a1 = _spawn_agent(world, 10, 10)
    a2 = _spawn_agent(world, 11, 10)
    a1.village_id = None
    a2.village_id = None
    a1.born_tick = 0
    a2.born_tick = 0
    a1.hunger = 95.0
    a2.hunger = 95.0
    a1.biological_sex = "female"
    a2.biological_sex = "male"

    world.compute_local_food_pressure_for_agent = lambda _a, max_distance=8: {  # type: ignore[assignment]
        "pressure_active": True,
        "unmet_pressure": False,
        "camp_food": 1,
        "house_food_nearby": 1,
        "near_food_sources": 2,
    }
    random_state = random.random
    try:
        random.random = lambda: 0.0
        for _ in range(20):
            world.tick += 1
            a1.repro_cooldown = 0
            a2.repro_cooldown = 0
            a1.try_reproduce(world)
    finally:
        random.random = random_state

    snap = world.compute_settlement_progression_snapshot()
    assert int(snap.get("reproduction_stable_proto_household_path_considered_count", 0)) >= 1
    assert int(snap.get("reproduction_stable_proto_household_path_activated_count", 0)) >= 1
