from __future__ import annotations

from agent import Agent
from brain import FoodBrain
from world import World


def _world_with_village() -> tuple[World, dict]:
    world = World(width=32, height=32, num_agents=0, seed=919, llm_enabled=False)
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


def _strong_attached_agent(village_uid: str, *, x: int = 10, y: int = 10) -> Agent:
    agent = Agent(x=x, y=y, brain=None, is_player=False, player_id=None)
    agent.village_affiliation_status = "attached"
    agent.primary_village_uid = village_uid
    agent.village_affiliation_scores[village_uid] = {
        "time_spent": 8.0,
        "work_contribution": 4.0,
        "structure_usage": 2.0,
        "social_interactions": 3.0,
        "gravity_exposure": 2.4,
    }
    return agent


def test_strong_affiliation_path_increments_early_stages() -> None:
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
    agent = _strong_attached_agent(village["village_uid"], x=10, y=11)
    world.agents = [agent]

    agent.update_village_affiliation(world)
    gate = world.compute_resident_conversion_gate_snapshot()["global"]
    assert int(gate["conversion_context_seen"]) >= 1
    assert int(gate["strong_affiliation_seen"]) >= 1
    assert int(gate["candidate_house_search_started"]) >= 1
    assert int(gate["resident_conversion_granted"]) >= 1


def test_no_candidate_house_records_reason() -> None:
    world, village = _world_with_village()
    agent = _strong_attached_agent(village["village_uid"], x=10, y=10)
    world.agents = [agent]

    agent.update_village_affiliation(world)
    reasons = world.compute_resident_conversion_gate_snapshot()["global"]["failure_reasons"]
    assert int(reasons.get("no_candidate_house", 0)) >= 1


def test_inactive_house_records_house_inactive_reason() -> None:
    world, village = _world_with_village()
    world.buildings["b-inactive"] = {
        "building_id": "b-inactive",
        "type": "house",
        "x": 10,
        "y": 10,
        "village_id": 1,
        "village_uid": village["village_uid"],
        "operational_state": "under_construction",
    }
    agent = _strong_attached_agent(village["village_uid"], x=10, y=10)
    world.agents = [agent]

    agent.update_village_affiliation(world)
    reasons = world.compute_resident_conversion_gate_snapshot()["global"]["failure_reasons"]
    assert int(reasons.get("house_inactive", 0)) >= 1


def test_occupied_house_records_house_not_empty_reason() -> None:
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
    resident = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    resident.home_building_id = "b-home"
    resident.home_village_uid = village["village_uid"]
    resident.primary_village_uid = village["village_uid"]
    resident.village_affiliation_status = "resident"
    agent = _strong_attached_agent(village["village_uid"], x=10, y=11)
    world.agents = [resident, agent]

    agent.update_village_affiliation(world)
    reasons = world.compute_resident_conversion_gate_snapshot()["global"]["failure_reasons"]
    assert int(reasons.get("house_not_empty", 0)) >= 1


def test_outside_claim_radius_records_reason() -> None:
    world, village = _world_with_village()
    world.buildings["b-far"] = {
        "building_id": "b-far",
        "type": "house",
        "x": 30,
        "y": 30,
        "village_id": 1,
        "village_uid": village["village_uid"],
        "operational_state": "active",
    }
    agent = _strong_attached_agent(village["village_uid"], x=10, y=10)
    world.agents = [agent]

    agent.update_village_affiliation(world)
    reasons = world.compute_resident_conversion_gate_snapshot()["global"]["failure_reasons"]
    assert int(reasons.get("outside_claim_radius", 0)) >= 1


def test_successful_conversion_increments_granted_counter() -> None:
    world, village = _world_with_village()
    world.buildings["b-home"] = {
        "building_id": "b-home",
        "type": "house",
        "x": 11,
        "y": 10,
        "village_id": 1,
        "village_uid": village["village_uid"],
        "operational_state": "active",
    }
    agent = _strong_attached_agent(village["village_uid"], x=10, y=10)
    world.agents = [agent]

    agent.update_village_affiliation(world)
    gate = world.compute_resident_conversion_gate_snapshot()["global"]
    assert int(gate["resident_conversion_granted"]) >= 1
    assert int(gate["conversion_success_count"]) >= 1


def test_house_with_village_id_only_is_aligned_and_claimable() -> None:
    world, village = _world_with_village()
    world.buildings["b-home"] = {
        "building_id": "b-home",
        "type": "house",
        "x": 11,
        "y": 10,
        "village_id": 1,
        "operational_state": "active",
    }
    agent = _strong_attached_agent(village["village_uid"], x=10, y=10)
    world.agents = [agent]

    agent.update_village_affiliation(world)

    assert agent.village_affiliation_status == "resident"
    assert agent.home_building_id == "b-home"
    reasons = world.compute_resident_conversion_gate_snapshot()["global"]["failure_reasons"]
    assert int(reasons.get("village_mismatch", 0)) == 0


def test_completed_under_construction_house_is_claimable_for_conversion() -> None:
    world, village = _world_with_village()
    world.buildings["b-home"] = {
        "building_id": "b-home",
        "type": "house",
        "x": 10,
        "y": 10,
        "village_id": 1,
        "village_uid": village["village_uid"],
        "operational_state": "under_construction",
        "construction_progress": 6,
        "construction_required_work": 6,
    }
    agent = _strong_attached_agent(village["village_uid"], x=10, y=11)
    world.agents = [agent]

    agent.update_village_affiliation(world)

    assert agent.village_affiliation_status == "resident"
    assert agent.home_building_id == "b-home"
    gate = world.compute_resident_conversion_gate_snapshot()["global"]
    assert int(gate["resident_conversion_granted"]) >= 1


def test_successful_conversion_enables_home_target_selection_for_rest() -> None:
    world, village = _world_with_village()
    world.buildings["b-home"] = {
        "building_id": "b-home",
        "type": "house",
        "x": 12,
        "y": 10,
        "village_id": 1,
        "village_uid": village["village_uid"],
        "operational_state": "active",
    }
    agent = _strong_attached_agent(village["village_uid"], x=8, y=10)
    agent.brain = FoodBrain()
    agent.task = "rest"
    agent.village_id = 1
    world.agents = [agent]

    agent.update_village_affiliation(world)
    agent.brain._evaluate_intention = lambda _world, _agent: None  # type: ignore[method-assign]
    agent.brain.decide(agent, world)

    diag = world.compute_recovery_diagnostics_snapshot()["global"]
    assert int(diag.get("home_target_available", 0)) >= 1
    assert int(diag.get("home_target_selected", 0)) >= 1


def test_observability_snapshot_exports_resident_conversion_gate_diagnostics() -> None:
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
    agent = _strong_attached_agent(village["village_uid"], x=10, y=11)
    world.agents = [agent]
    agent.update_village_affiliation(world)

    world.metrics_collector.collect(world)
    snap = world.metrics_collector.latest()["cognition_society"]
    assert "resident_conversion_gate_diagnostics_global" in snap
    assert "resident_conversion_gate_diagnostics_by_village" in snap
    by_v = snap["resident_conversion_gate_diagnostics_by_village"]
    assert village["village_uid"] in by_v
