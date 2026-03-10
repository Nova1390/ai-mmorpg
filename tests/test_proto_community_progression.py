from __future__ import annotations

from agent import Agent
from brain import FoodBrain
import systems.road_system as road_system
from world import World


def _flat_world() -> World:
    world = World(width=32, height=32, num_agents=0, seed=17, llm_enabled=False)
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    world.food = set()
    world.wood = set()
    world.stone = set()
    world.structures = set()
    world.storage_buildings = set()
    world.buildings = {}
    world.building_occupancy = {}
    world.roads = set()
    world.transport_tiles = {}
    return world


def test_repeated_local_copresence_forms_proto_community_and_camp() -> None:
    world = _flat_world()
    a1 = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    a2 = Agent(x=12, y=10, brain=None, is_player=False, player_id=None)
    a1.hunger = 80
    a2.hunger = 80
    world.agents = [a1, a2]

    for tick in range(1, 8):
        world.tick = tick
        world.update_proto_communities_and_camps()

    snap = world.compute_progression_snapshot()
    assert int(snap["proto_community_count"]) >= 1
    assert int(snap["camps_count"]) >= 1
    assert len(world.buildings) == 0


def test_camp_can_anchor_rest_behavior_before_houses() -> None:
    world = _flat_world()
    brain = FoodBrain()
    agent = Agent(x=3, y=3, brain=brain, is_player=False, player_id=None)
    agent.task = "rest"
    agent.hunger = 60
    world.agents = [agent]
    world.camps = {
        "camp-000001": {
            "camp_id": "camp-000001",
            "x": 10,
            "y": 10,
            "active": True,
            "village_uid": "",
            "community_id": "pc-000001",
            "last_active_tick": 1,
        }
    }

    action = brain.decide(agent, world)
    assert action and action[0] == "move"
    assert int(world.compute_progression_snapshot()["camp_return_events"]) >= 1


def test_early_roads_are_suppressed_for_fragile_village() -> None:
    world = _flat_world()
    world.villages = [
        {
            "id": 1,
            "village_uid": "v-000001",
            "center": {"x": 8, "y": 8},
            "houses": 1,
            "population": 3,
            "storage": {"food": 1, "wood": 0, "stone": 0},
            "storage_pos": {"x": 8, "y": 8},
            "needs": {"food_buffer_critical": True},
            "metrics": {"population": 3, "food_stock": 1},
        }
    ]

    road_system.update_road_infrastructure(world)
    snap = world.compute_progression_snapshot()
    assert int(snap["early_road_suppressed_count"]) >= 1
    reasons = snap["road_priority_deferred_reasons"]
    assert any(k in reasons for k in ("population_too_low", "food_crisis_active", "no_settlement_anchor"))


def test_mature_villages_can_still_progress_to_roads() -> None:
    world = _flat_world()
    world.villages = [
        {
            "id": 1,
            "village_uid": "v-000001",
            "center": {"x": 10, "y": 10},
            "houses": 7,
            "population": 10,
            "storage": {"food": 20, "wood": 10, "stone": 8},
            "storage_pos": {"x": 10, "y": 10},
            "farm_zone_center": {"x": 12, "y": 10},
            "needs": {"food_buffer_critical": False},
            "metrics": {"population": 10, "food_stock": 20},
        }
    ]
    world.place_building("storage", 10, 10, village_id=1, village_uid="v-000001")
    world.place_building("house", 16, 10, village_id=1, village_uid="v-000001")

    road_system.update_road_infrastructure(world)
    assert len(world.roads) > 0


def test_observability_includes_progression_metrics() -> None:
    world = _flat_world()
    a1 = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    a2 = Agent(x=11, y=10, brain=None, is_player=False, player_id=None)
    a1.hunger = 80
    a2.hunger = 80
    world.agents = [a1, a2]
    for tick in range(1, 6):
        world.tick = tick
        world.update_proto_communities_and_camps()

    world.metrics_collector.collect(world)
    snapshot = world.metrics_collector.latest()
    cog = snapshot["cognition_society"]
    assert "proto_community_count" in cog
    assert "proto_community_agents" in cog
    assert "camps_count" in cog
    assert "active_camps_count" in cog
    assert "camp_return_events" in cog
    assert "camp_rest_events" in cog
    assert "house_vs_camp_population" in cog
    assert "early_road_suppressed_count" in cog
    assert "road_priority_deferred_reasons" in cog
    assert "settlement_stage_counts" in cog


def test_camp_brief_drift_does_not_immediately_deactivate() -> None:
    world = _flat_world()
    world.tick = 10
    world.camps = {
        "camp-000001": {
            "camp_id": "camp-000001",
            "x": 10,
            "y": 10,
            "active": True,
            "village_uid": "",
            "community_id": "",
            "created_tick": 1,
            "last_active_tick": 1,
            "absence_ticks": 0,
        }
    }
    world.agents = []
    for t in range(11, 20):
        world.tick = t
        world.update_proto_communities_and_camps()
    assert bool(world.camps["camp-000001"]["active"]) is True


def test_camp_deactivates_after_sustained_absence() -> None:
    world = _flat_world()
    world.camps = {
        "camp-000001": {
            "camp_id": "camp-000001",
            "x": 10,
            "y": 10,
            "active": True,
            "village_uid": "",
            "community_id": "",
            "created_tick": 1,
            "last_active_tick": 1,
            "absence_ticks": 0,
        }
    }
    world.agents = []
    for t in range(1, 80):
        world.tick = t
        world.update_proto_communities_and_camps()
    assert bool(world.camps["camp-000001"]["active"]) is False


def test_rest_prefers_home_over_camp_when_both_available() -> None:
    world = _flat_world()
    brain = FoodBrain()
    agent = Agent(x=4, y=4, brain=brain, is_player=False, player_id=None)
    agent.task = "rest"
    agent.hunger = 70
    world.agents = [agent]
    world.buildings["h-1"] = {
        "building_id": "h-1",
        "type": "house",
        "x": 8,
        "y": 8,
        "operational_state": "active",
    }
    agent.home_building_id = "h-1"
    world.camps = {
        "camp-000001": {
            "camp_id": "camp-000001",
            "x": 12,
            "y": 12,
            "active": True,
            "village_uid": "",
            "community_id": "pc-000001",
            "last_active_tick": 1,
            "created_tick": 1,
            "absence_ticks": 0,
        }
    }

    action = brain.decide(agent, world)
    assert action and action[0] == "move"
    targeting = world.compute_camp_targeting_snapshot()["global"]
    assert int(targeting["rest_target_home"]) >= 1
    assert int(targeting["rest_target_camp"]) == 0


def test_survival_override_still_suppresses_camp_rest_routing() -> None:
    world = _flat_world()
    brain = FoodBrain()
    world.food = {(5, 4)}
    agent = Agent(x=4, y=4, brain=brain, is_player=False, player_id=None)
    agent.task = "rest"
    agent.hunger = 10
    world.agents = [agent]
    world.camps = {
        "camp-000001": {
            "camp_id": "camp-000001",
            "x": 10,
            "y": 10,
            "active": True,
            "village_uid": "",
            "community_id": "pc-000001",
            "last_active_tick": 1,
            "created_tick": 1,
            "absence_ticks": 0,
        }
    }

    action = brain.decide(agent, world)
    assert action and action[0] == "move"
    targeting = world.compute_camp_targeting_snapshot()["global"]
    reasons = targeting.get("camp_not_chosen_reasons", {})
    assert int(targeting["rest_target_camp"]) == 0
    assert int(reasons.get("hunger_override", 0)) >= 1


def test_no_infinite_camp_lock_in_for_non_rest_tasks() -> None:
    world = _flat_world()
    brain = FoodBrain()
    world.food = {(6, 4)}
    agent = Agent(x=4, y=4, brain=brain, is_player=False, player_id=None)
    agent.task = "gather_food_wild"
    agent.hunger = 60
    world.agents = [agent]
    world.camps = {
        "camp-000001": {
            "camp_id": "camp-000001",
            "x": 10,
            "y": 10,
            "active": True,
            "village_uid": "",
            "community_id": "pc-000001",
            "last_active_tick": 1,
            "created_tick": 1,
            "absence_ticks": 0,
        }
    }

    action = brain.decide(agent, world)
    assert action and action[0] == "move"
    # Task-oriented food behavior should remain available despite nearby camp.
    assert int(world.compute_progression_snapshot()["camp_return_events"]) == 0
