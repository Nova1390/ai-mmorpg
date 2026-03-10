from __future__ import annotations

from agent import Agent
from brain import FoodBrain
from world import World


def _world_with_village() -> tuple[World, dict]:
    world = World(width=32, height=32, num_agents=0, seed=11, llm_enabled=False)
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    village = {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 10, "y": 10},
        "houses": 4,
        "population": 8,
        "storage": {"food": 0, "wood": 0, "stone": 0},
        "storage_pos": {"x": 10, "y": 10},
        "tier": 2,
    }
    world.villages = [village]
    return world, village


def test_agents_with_home_house_are_residents() -> None:
    world, village = _world_with_village()
    world.buildings["b-home"] = {
        "building_id": "b-home",
        "type": "house",
        "x": 10,
        "y": 10,
        "village_id": 1,
        "village_uid": village["village_uid"],
        "operational_state": "active",
    }
    agent = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    agent.home_building_id = "b-home"

    agent.update_village_affiliation(world)

    assert agent.village_affiliation_status == "resident"
    assert agent.primary_village_uid == village["village_uid"]
    assert agent.home_village_uid == village["village_uid"]


def test_agents_without_house_can_become_attached_by_local_work() -> None:
    world, village = _world_with_village()
    agent = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    agent.task = "build_storage"

    for _ in range(8):
        agent.update_village_affiliation(world)

    assert agent.village_affiliation_status == "attached"
    assert agent.primary_village_uid == village["village_uid"]


def test_agents_with_little_local_contact_remain_unaffiliated() -> None:
    world, _ = _world_with_village()
    agent = Agent(x=30, y=30, brain=None, is_player=False, player_id=None)

    agent.update_village_affiliation(world)

    assert agent.village_affiliation_status == "unaffiliated"
    assert agent.primary_village_uid is None


def test_affiliation_updates_are_deterministic_and_bounded() -> None:
    w1, _ = _world_with_village()
    w2, _ = _world_with_village()
    a1 = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    a2 = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    a1.task = "village_logistics"
    a2.task = "village_logistics"

    for _ in range(20):
        a1.update_village_affiliation(w1)
        a2.update_village_affiliation(w2)

    assert a1.village_affiliation_status == a2.village_affiliation_status
    assert a1.primary_village_uid == a2.primary_village_uid
    assert a1.village_affiliation_scores == a2.village_affiliation_scores
    assert len(a1.village_affiliation_scores) <= 8


def test_nearby_unaffiliated_agents_can_attach_via_social_gravity() -> None:
    world, village = _world_with_village()
    agent = Agent(x=11, y=10, brain=None, is_player=False, player_id=None)
    agent.task = "idle"

    for _ in range(14):
        agent.update_village_affiliation(world)

    assert agent.primary_village_uid == village["village_uid"]
    assert agent.village_affiliation_status in {"attached", "resident", "transient"}


def test_attached_agent_gets_return_to_village_bias_stronger_than_unaffiliated() -> None:
    world, village = _world_with_village()
    world.food = set()
    world.wood = set()
    world.stone = set()
    brain = FoodBrain()

    attached = Agent(x=28, y=28, brain=brain, is_player=False, player_id=None)
    attached.task = "gather_food_wild"
    attached.village_affiliation_status = "attached"
    attached.primary_village_uid = village["village_uid"]

    unaffiliated = Agent(x=28, y=28, brain=brain, is_player=False, player_id=None)
    unaffiliated.task = "gather_food_wild"
    unaffiliated.village_affiliation_status = "unaffiliated"
    unaffiliated.primary_village_uid = None

    action_attached = brain.decide(attached, world)
    before = world.compute_social_gravity_event_snapshot()["global"]["return_to_village_events"]
    action_unaffiliated = brain.decide(unaffiliated, world)
    after = world.compute_social_gravity_event_snapshot()["global"]["return_to_village_events"]

    assert action_attached and action_attached[0] == "move"
    # Unaffiliated behavior should not increment village return bias event.
    assert int(after) == int(before)
    assert action_unaffiliated is not None


def test_houses_can_gain_residents_beyond_leader_when_candidates_exist() -> None:
    world, village = _world_with_village()
    world.buildings["b-home-1"] = {
        "building_id": "b-home-1",
        "type": "house",
        "x": 10,
        "y": 10,
        "village_id": 1,
        "village_uid": village["village_uid"],
        "operational_state": "active",
    }
    world.buildings["b-home-2"] = {
        "building_id": "b-home-2",
        "type": "house",
        "x": 11,
        "y": 10,
        "village_id": 1,
        "village_uid": village["village_uid"],
        "operational_state": "active",
    }
    a1 = Agent(x=10, y=11, brain=None, is_player=False, player_id=None)
    a2 = Agent(x=11, y=11, brain=None, is_player=False, player_id=None)
    a1.primary_village_uid = village["village_uid"]
    a2.primary_village_uid = village["village_uid"]
    a1.village_affiliation_status = "attached"
    a2.village_affiliation_status = "attached"
    a1.village_affiliation_scores[village["village_uid"]] = {
        "time_spent": 6.0,
        "work_contribution": 3.0,
        "structure_usage": 2.0,
        "social_interactions": 2.0,
        "gravity_exposure": 2.0,
    }
    a2.village_affiliation_scores[village["village_uid"]] = {
        "time_spent": 6.0,
        "work_contribution": 3.0,
        "structure_usage": 2.0,
        "social_interactions": 2.0,
        "gravity_exposure": 2.0,
    }
    world.agents = [a1, a2]

    a1.update_village_affiliation(world)
    a2.update_village_affiliation(world)

    residents = [a for a in (a1, a2) if a.village_affiliation_status == "resident" and a.home_building_id is not None]
    assert len(residents) >= 1


def test_lone_wolf_behavior_remains_possible_when_far_from_villages() -> None:
    world, _ = _world_with_village()
    agent = Agent(x=31, y=31, brain=None, is_player=False, player_id=None)
    for _ in range(20):
        agent.update_village_affiliation(world)
    assert agent.village_affiliation_status == "unaffiliated"
    assert agent.home_building_id is None


def test_social_gravity_respects_urgent_survival_food_override() -> None:
    world, village = _world_with_village()
    brain = FoodBrain()
    world.food = {(28, 27)}
    world.tiles[27][28] = "G"
    agent = Agent(x=28, y=28, brain=brain, is_player=False, player_id=None)
    agent.task = "gather_food_wild"
    agent.hunger = 10
    agent.village_affiliation_status = "attached"
    agent.primary_village_uid = village["village_uid"]

    before = world.compute_social_gravity_event_snapshot()["global"]["return_to_village_events"]
    action = brain.decide(agent, world)
    after = world.compute_social_gravity_event_snapshot()["global"]["return_to_village_events"]

    assert action and action[0] == "move"
    # No social-return event should fire while urgent food behavior dominates.
    assert int(after) == int(before)


def test_strong_attached_agent_near_house_converts_to_resident() -> None:
    world, village = _world_with_village()
    world.buildings["b-home"] = {
        "building_id": "b-home",
        "type": "house",
        "x": 10,
        "y": 10,
        "village_id": 1,
        "village_uid": village["village_uid"],
        "operational_state": "active",
    }
    agent = Agent(x=10, y=11, brain=None, is_player=False, player_id=None)
    agent.village_affiliation_status = "attached"
    agent.primary_village_uid = village["village_uid"]
    agent.village_affiliation_scores[village["village_uid"]] = {
        "time_spent": 8.0,
        "work_contribution": 4.0,
        "structure_usage": 2.0,
        "social_interactions": 3.0,
        "gravity_exposure": 2.5,
    }
    world.agents = [agent]

    agent.update_village_affiliation(world)

    assert agent.village_affiliation_status == "resident"
    assert agent.home_building_id == "b-home"
    assert agent.home_village_uid == village["village_uid"]


def test_distant_attached_agent_does_not_convert_to_resident_too_easily() -> None:
    world, village = _world_with_village()
    world.buildings["b-home"] = {
        "building_id": "b-home",
        "type": "house",
        "x": 10,
        "y": 10,
        "village_id": 1,
        "village_uid": village["village_uid"],
        "operational_state": "active",
    }
    agent = Agent(x=30, y=30, brain=None, is_player=False, player_id=None)
    agent.village_affiliation_status = "attached"
    agent.primary_village_uid = village["village_uid"]
    agent.village_affiliation_scores[village["village_uid"]] = {
        "time_spent": 8.0,
        "work_contribution": 4.0,
        "structure_usage": 2.0,
        "social_interactions": 3.0,
        "gravity_exposure": 2.5,
    }
    world.agents = [agent]

    agent.update_village_affiliation(world)

    assert agent.home_building_id is None
    assert agent.village_affiliation_status in {"attached", "transient", "unaffiliated"}


def test_residency_persists_then_releases_when_home_missing_after_window() -> None:
    world, village = _world_with_village()
    world.buildings["b-home"] = {
        "building_id": "b-home",
        "type": "house",
        "x": 10,
        "y": 10,
        "village_id": 1,
        "village_uid": village["village_uid"],
        "operational_state": "active",
    }
    agent = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    agent.home_building_id = "b-home"
    world.agents = [agent]
    world.tick = 1
    agent.update_village_affiliation(world)
    assert agent.village_affiliation_status == "resident"
    persistence_until = int(agent.residence_persistence_until_tick)
    assert persistence_until > 1

    del world.buildings["b-home"]
    world.tick = persistence_until - 1
    agent.update_village_affiliation(world)
    assert agent.village_affiliation_status == "resident"

    world.tick = persistence_until + 1
    agent.update_village_affiliation(world)
    assert agent.home_building_id is None
    assert agent.village_affiliation_status != "resident"
    snapshot = world.compute_residence_stabilization_snapshot()
    assert int(snapshot["global"]["resident_release_count"]) >= 1
    reasons = snapshot["global"]["resident_release_reasons"]
    assert (
        int(reasons.get("house_missing_or_inactive", 0)) >= 1
        or int(reasons.get("persistence_window_expired", 0)) >= 1
    )


def test_resident_home_return_event_is_stronger_than_attached_return() -> None:
    world, village = _world_with_village()
    world.food = set()
    world.wood = set()
    world.stone = set()
    world.buildings["b-home"] = {
        "building_id": "b-home",
        "type": "house",
        "x": 14,
        "y": 10,
        "village_id": 1,
        "village_uid": village["village_uid"],
        "operational_state": "active",
    }
    brain = FoodBrain()
    resident = Agent(x=30, y=10, brain=brain, is_player=False, player_id=None)
    resident.task = "gather_food_wild"
    resident.hunger = 80
    resident.village_affiliation_status = "resident"
    resident.primary_village_uid = village["village_uid"]
    resident.home_village_uid = village["village_uid"]
    resident.home_building_id = "b-home"

    attached = Agent(x=30, y=10, brain=brain, is_player=False, player_id=None)
    attached.task = "gather_food_wild"
    attached.hunger = 80
    attached.village_affiliation_status = "attached"
    attached.primary_village_uid = village["village_uid"]

    before = world.compute_social_gravity_event_snapshot()["global"]
    action_resident = brain.decide(resident, world)
    mid = world.compute_social_gravity_event_snapshot()["global"]
    action_attached = brain.decide(attached, world)
    after = world.compute_social_gravity_event_snapshot()["global"]

    assert action_resident and action_resident[0] == "move"
    assert action_attached and action_attached[0] == "move"
    assert int(mid["home_return_events"]) == int(before["home_return_events"]) + 1
    assert int(after["return_to_village_events"]) == int(mid["return_to_village_events"]) + 1
