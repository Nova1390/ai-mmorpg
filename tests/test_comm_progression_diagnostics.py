from __future__ import annotations

from agent import Agent
from brain import FoodBrain
from world import World


def _flat_world() -> World:
    world = World(width=32, height=32, num_agents=0, seed=99, llm_enabled=False)
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
    world.villages = []
    world.agents = []
    return world


def test_copresence_increments_proto_funnel_stages() -> None:
    world = _flat_world()
    world.agents = [
        Agent(x=10, y=10, brain=None, is_player=False, player_id=None),
        Agent(x=11, y=10, brain=None, is_player=False, player_id=None),
    ]
    world.tick = 1
    world.update_proto_communities_and_camps()
    snap = world.compute_proto_community_funnel_snapshot()
    assert int(snap["global"]["co_presence_detected"]) >= 1
    assert int(snap["global"]["co_presence_cluster_valid"]) >= 1
    assert int(snap["global"]["proto_streak_incremented"]) >= 1


def test_small_cluster_records_cluster_too_small_reason() -> None:
    world = _flat_world()
    world.agents = [Agent(x=10, y=10, brain=None, is_player=False, player_id=None)]
    world.tick = 1
    world.update_proto_communities_and_camps()
    snap = world.compute_proto_community_funnel_snapshot()
    reasons = snap["global"]["failure_reasons"]
    assert int(reasons.get("cluster_too_small", 0)) >= 1


def test_proto_community_formed_stage_records_success() -> None:
    world = _flat_world()
    a1 = Agent(x=12, y=12, brain=None, is_player=False, player_id=None)
    a2 = Agent(x=13, y=12, brain=None, is_player=False, player_id=None)
    a1.hunger = 80
    a2.hunger = 80
    world.agents = [a1, a2]
    world.tick = 1
    world.update_proto_communities_and_camps()
    snap = world.compute_proto_community_funnel_snapshot()
    assert int(snap["global"]["proto_community_formed"]) >= 1


def test_camp_creation_increments_lifecycle_stage() -> None:
    world = _flat_world()
    a1 = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    a2 = Agent(x=11, y=10, brain=None, is_player=False, player_id=None)
    a1.hunger = 90
    a2.hunger = 90
    world.agents = [a1, a2]
    for tick in range(1, 8):
        world.tick = tick
        world.update_proto_communities_and_camps()
    snap = world.compute_camp_lifecycle_snapshot()
    assert int(snap["global"]["camp_created"]) >= 1


def test_camp_deactivation_records_reason() -> None:
    world = _flat_world()
    world.tick = 500
    world.camps = {
        "camp-000001": {
            "camp_id": "camp-000001",
            "x": 20,
            "y": 20,
            "community_id": "pc-000001",
            "created_tick": 1,
            "last_active_tick": 1,
            "active": True,
            "village_uid": "",
        }
    }
    world.update_proto_communities_and_camps()
    snap = world.compute_camp_lifecycle_snapshot()
    assert int(snap["global"]["camp_deactivated"]) >= 1
    assert int(snap["global"]["deactivation_reasons"].get("camp_stale_timeout", 0)) >= 1


def test_camp_retained_briefly_when_cache_support_exists() -> None:
    world = _flat_world()
    world.tick = 50
    world.camps = {
        "camp-000001": {
            "camp_id": "camp-000001",
            "x": 10,
            "y": 10,
            "community_id": "",
            "created_tick": 1,
            "last_active_tick": 1,
            "last_use_tick": 48,
            "last_food_activity_tick": 48,
            "active": True,
            "absence_ticks": 36,
            "village_uid": "",
            "food_cache": 3,
        }
    }
    world.agents = []
    world.update_proto_communities_and_camps()
    camp = world.camps["camp-000001"]
    assert bool(camp.get("active", False)) is True
    snap = world.compute_camp_lifecycle_snapshot()
    reasons = snap["global"]["retention_reasons"]
    assert int(reasons.get("food_cache", 0)) >= 1
    assert int(reasons.get("recent_use", 0)) >= 1


def test_abandoned_camp_deactivates_with_no_viable_support_reason() -> None:
    world = _flat_world()
    world.tick = 95
    world.camps = {
        "camp-000001": {
            "camp_id": "camp-000001",
            "x": 12,
            "y": 12,
            "community_id": "",
            "created_tick": 1,
            "last_active_tick": 10,
            "last_use_tick": 10,
            "last_food_activity_tick": 10,
            "active": True,
            "absence_ticks": 70,
            "village_uid": "",
            "food_cache": 0,
        }
    }
    world.agents = []
    world.update_proto_communities_and_camps()
    camp = world.camps["camp-000001"]
    assert bool(camp.get("active", True)) is False
    snap = world.compute_camp_lifecycle_snapshot()
    reasons = snap["global"]["deactivation_reasons"]
    assert int(reasons.get("no_viable_support", 0)) >= 1


def test_deactivation_support_snapshot_counts_nearby_and_anchor_support() -> None:
    world = _flat_world()
    anchor_agent = Agent(x=22, y=10, brain=None, is_player=False, player_id=None)
    anchor_agent.proto_specialization = "food_gatherer"
    anchor_agent.proto_task_anchor = {"camp_id": "camp-000001"}
    world.agents = [anchor_agent]
    world.tick = 200
    world.camps = {
        "camp-000001": {
            "camp_id": "camp-000001",
            "x": 10,
            "y": 10,
            "community_id": "",
            "created_tick": 1,
            "last_active_tick": 1,
            "last_use_tick": 1,
            "last_food_activity_tick": 1,
            "active": True,
            "absence_ticks": 120,
            "village_uid": "",
            "food_cache": 2,
        }
    }
    world.update_proto_communities_and_camps()
    snap = world.compute_camp_lifecycle_snapshot()
    assert int(snap["global"]["deactivation_with_food_cache_count"]) >= 1
    assert int(snap["global"]["deactivation_with_anchor_support_count"]) >= 1
    assert int(snap["global"]["deactivation_with_nearby_agents_count"]) >= 1


def test_rest_target_camp_is_recorded_when_camp_selected() -> None:
    world = _flat_world()
    brain = FoodBrain()
    agent = Agent(x=3, y=3, brain=brain, is_player=False, player_id=None)
    agent.task = "rest"
    agent.hunger = 70
    world.agents = [agent]
    world.camps = {
        "camp-000001": {
            "camp_id": "camp-000001",
            "x": 10,
            "y": 10,
            "community_id": "pc-000001",
            "created_tick": 1,
            "last_active_tick": 1,
            "active": True,
            "village_uid": "",
        }
    }
    action = brain.decide(agent, world)
    assert action and action[0] == "move"
    targeting = world.compute_camp_targeting_snapshot()
    assert int(targeting["global"]["rest_target_camp"]) >= 1


def test_observability_includes_comm_diagnostics_fields() -> None:
    world = _flat_world()
    world.agents = [
        Agent(x=10, y=10, brain=None, is_player=False, player_id=None),
        Agent(x=11, y=10, brain=None, is_player=False, player_id=None),
    ]
    world.tick = 1
    world.update_proto_communities_and_camps()
    world.metrics_collector.collect(world)
    snap = world.metrics_collector.latest()
    cog = snap["cognition_society"]
    assert "proto_community_funnel_global" in cog
    assert "proto_community_funnel_by_region" in cog
    assert "camp_lifecycle_global" in cog
    assert "camp_lifecycle_by_region" in cog
    assert "camp_targeting_diagnostics" in cog
