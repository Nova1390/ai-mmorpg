from __future__ import annotations

from agent import Agent, detect_agent_innovation_opportunity, maybe_generate_innovation_proposal
from world import World


def _blank_world() -> World:
    world = World(width=24, height=24, num_agents=0, seed=7, llm_enabled=False)
    world.agents = []
    world.villages = []
    world.buildings = {}
    world.structures = set()
    world.storage_buildings = set()
    world.roads = set()
    world.transport_tiles = {}
    world.food = set()
    world.wood = set()
    world.stone = set()
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    return world


def _agent_with_local_context() -> Agent:
    agent = Agent(x=8, y=8, brain=None)
    agent.subjective_state = {
        "local_signals": {
            "needs": {
                "food_buffer_critical": False,
                "need_storage": True,
            }
        }
    }
    return agent


def test_repeated_local_friction_can_trigger_innovation_opportunity() -> None:
    world = _blank_world()
    agent = _agent_with_local_context()
    agent.role = "builder"
    agent.current_intention = {"type": "build_structure", "failed_ticks": 3}
    assert detect_agent_innovation_opportunity(world, agent) == "construction_friction"


def test_opportunity_detection_does_not_require_global_omniscience() -> None:
    world = _blank_world()
    agent = _agent_with_local_context()
    agent.subjective_state["local_signals"]["needs"]["need_storage"] = False
    agent.current_intention = {"type": "gather_resource", "failed_ticks": 0}
    agent.episodic_memory = {
        "recent_events": [
            {"type": "failed_resource_search", "outcome": "failure", "resource_type": "wood"},
            {"type": "failed_resource_search", "outcome": "failure", "resource_type": "wood"},
            {"type": "failed_resource_search", "outcome": "failure", "resource_type": "stone"},
        ]
    }
    assert detect_agent_innovation_opportunity(world, agent) == "resource_access_friction"


def test_transport_barrier_cross_water_proposal_can_be_admissible() -> None:
    world = _blank_world()
    for y in range(7, 10):
        world.tiles[y][9] = "W"
    agent = _agent_with_local_context()
    agent.agent_id = "a-transport"
    agent.subjective_state["local_signals"]["needs"]["need_storage"] = False
    agent.episodic_memory = {
        "recent_events": [
            {"type": "unreachable_target", "outcome": "failure", "location": {"x": 9, "y": 8, "terrain_hint": "water"}},
            {"type": "unreachable_target", "outcome": "failure", "location": {"x": 9, "y": 9, "terrain_hint": "water"}},
        ]
    }
    world.agents = [agent]

    proposal = maybe_generate_innovation_proposal(world, agent, source="stub")
    assert isinstance(proposal, dict)
    assert proposal["status"] == "admissible"
    assert proposal.get("admissibility_tick", -1) >= 0
    assert proposal["reason"] == "transport_barrier"
    assert "cross_water" in proposal["intended_effects"]


def test_storage_friction_storage_proposal_can_be_admissible() -> None:
    world = _blank_world()
    agent = _agent_with_local_context()
    agent.agent_id = "a-storage"
    agent.current_intention = {"type": "deliver_resource", "failed_ticks": 0}
    world.agents = [agent]

    proposal = maybe_generate_innovation_proposal(world, agent, source="stub", reason="storage_friction")
    assert isinstance(proposal, dict)
    assert proposal["status"] == "admissible"
    assert proposal["category"] in {"storage", "logistics"}


def test_implausible_effect_context_is_rejected() -> None:
    world = _blank_world()
    agent = _agent_with_local_context()
    agent.agent_id = "a-bad-context"
    agent.subjective_state["local_signals"]["needs"]["need_storage"] = False
    world.agents = [agent]
    malformed_context = {
        "name": "odd transport ritual",
        "asset_kind": "process",
        "category": "transport",
        "intended_effects": ["improve_food_handling"],
        "required_materials": {"wood": 2},
        "footprint_hint": {"width": 1, "height": 1, "placement": "near_route"},
    }
    proposal = maybe_generate_innovation_proposal(
        world,
        agent,
        source="provider",
        reason="route_inefficiency",
        proposal_payload=malformed_context,
    )
    assert isinstance(proposal, dict)
    assert proposal["status"] == "rejected"
    assert proposal["rejection_reason"] in {"invalid_effect_context", "unsupported_category_context"}


def test_excessive_material_cost_is_rejected() -> None:
    world = _blank_world()
    agent = _agent_with_local_context()
    agent.agent_id = "a-expensive"
    world.agents = [agent]
    expensive = {
        "name": "heavy route slab",
        "asset_kind": "infrastructure",
        "category": "transport",
        "intended_effects": ["reduce_movement_cost"],
        "required_materials": {"wood": 8, "stone": 8},
        "footprint_hint": {"width": 2, "height": 2, "placement": "near_route"},
    }
    proposal = maybe_generate_innovation_proposal(
        world,
        agent,
        source="provider",
        reason="route_inefficiency",
        proposal_payload=expensive,
    )
    assert isinstance(proposal, dict)
    assert proposal["status"] == "rejected"
    assert proposal["rejection_reason"] == "excessive_material_cost"


def test_duplicate_equivalent_proposal_is_archived_deterministically() -> None:
    world = _blank_world()
    agent = _agent_with_local_context()
    agent.agent_id = "a-dup"
    world.agents = [agent]
    p1 = maybe_generate_innovation_proposal(world, agent, source="stub", reason="storage_friction")
    assert isinstance(p1, dict)
    world.tick = 300
    p2 = maybe_generate_innovation_proposal(world, agent, source="stub", reason="storage_friction")
    assert isinstance(p2, dict)
    assert p2["status"] == "archived"
    assert p2["rejection_reason"] == "duplicate_equivalent_proposal"


def test_status_lifecycle_and_observability_counters_update() -> None:
    world = _blank_world()

    a1 = _agent_with_local_context()
    a1.agent_id = "a-good"
    world.agents = [a1]
    good = maybe_generate_innovation_proposal(world, a1, source="stub", reason="storage_friction")
    assert isinstance(good, dict) and good["status"] == "admissible"

    world.tick = 150
    a2 = _agent_with_local_context()
    a2.agent_id = "a-bad"
    a2.subjective_state["local_signals"]["needs"]["need_storage"] = False
    world.agents.append(a2)
    bad_payload = {
        "name": "crosswater plan",
        "asset_kind": "infrastructure",
        "category": "transport",
        "intended_effects": ["cross_water"],
        "required_materials": {"wood": 2},
        "footprint_hint": {"width": 1, "height": 1, "placement": "near_water"},
    }
    bad = maybe_generate_innovation_proposal(
        world,
        a2,
        source="provider",
        reason="route_inefficiency",
        proposal_payload=bad_payload,
    )
    assert isinstance(bad, dict) and bad["status"] == "rejected"

    stats = world.reflection_stats
    assert int(stats.get("admissible_proposal_count", 0)) >= 1
    assert int(stats.get("rejected_proposal_count", 0)) >= 1
    assert int((stats.get("proposal_counts_by_status") or {}).get("admissible", 0)) >= 1
    assert int((stats.get("proposal_counts_by_status") or {}).get("rejected", 0)) >= 1
    assert int((stats.get("proposal_counts_by_category") or {}).get("storage", 0)) >= 1
    assert isinstance((stats.get("proposal_counts_by_effect") or {}), dict)
