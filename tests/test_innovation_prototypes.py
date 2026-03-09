from __future__ import annotations

from agent import Agent, maybe_generate_innovation_proposal
from world import World, evaluate_prototype_usefulness, find_proto_asset_placement, select_proto_asset_for_adoption_attempt


def _blank_world() -> World:
    world = World(width=28, height=28, num_agents=0, seed=11, llm_enabled=False)
    world.agents = []
    world.villages = []
    world.buildings = {}
    world.building_occupancy = {}
    world.structures = set()
    world.storage_buildings = set()
    world.roads = set()
    world.transport_tiles = {}
    world.food = set()
    world.wood = set()
    world.stone = set()
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    return world


def _seed_village(world: World, *, village_id: int = 1, x: int = 10, y: int = 10) -> None:
    village = {
        "id": village_id,
        "village_uid": f"v-{village_id:06d}",
        "center": {"x": x, "y": y},
        "houses": 4,
        "population": 8,
        "storage": {"food": 0, "wood": 50, "stone": 50},
        "storage_pos": {"x": x, "y": y},
        "tier": 2,
        "needs": {"need_storage": True},
    }
    world.villages = [village]
    world.place_building("storage", x, y, village_id=village_id, village_uid=village["village_uid"])


def _agent(agent_id: str, x: int = 10, y: int = 10, village_id: int = 1, role: str = "builder") -> Agent:
    agent = Agent(x=x, y=y, brain=None)
    agent.agent_id = agent_id
    agent.village_id = village_id
    agent.role = role
    agent.subjective_state = {"local_signals": {"needs": {"need_storage": True}}}
    return agent


def _admissible_storage_proposal(world: World, inventor: Agent) -> dict:
    world.agents = [inventor]
    proposal = maybe_generate_innovation_proposal(world, inventor, source="stub", reason="storage_friction")
    assert isinstance(proposal, dict)
    assert proposal["status"] == "admissible"
    return proposal


def _build_storage_prototype(world: World, agent: Agent) -> dict:
    _admissible_storage_proposal(world, agent)
    world.run_proto_asset_adoption_attempt(agent)
    instance = world.proto_asset_prototypes[-1]
    loc = instance["location"]
    agent.x = int(loc["x"])
    agent.y = int(loc["y"])
    agent.inventory["wood"] = int(instance["required_materials"]["wood"])
    agent.inventory["stone"] = int(instance["required_materials"]["stone"])
    while str(instance.get("status", "")) != "prototype_built":
        world.run_proto_asset_adoption_attempt(agent)
        world.tick += 1
        assert world.tick < 90
    return instance


def test_admissible_proposals_can_become_prototype_candidates() -> None:
    world = _blank_world()
    _seed_village(world)
    inventor = _agent("a-inventor")
    proposal = _admissible_storage_proposal(world, inventor)
    selected = select_proto_asset_for_adoption_attempt(world, inventor)
    assert isinstance(selected, dict)
    assert selected["proposal_id"] == proposal["proposal_id"]


def test_non_admissible_proposals_cannot_be_selected_for_prototypes() -> None:
    world = _blank_world()
    _seed_village(world)
    inventor = _agent("a-reject")
    world.agents = [inventor]
    rejected = maybe_generate_innovation_proposal(
        world,
        inventor,
        source="provider",
        reason="route_inefficiency",
        proposal_payload={
            "name": "crosswater mismatch",
            "asset_kind": "infrastructure",
            "category": "transport",
            "intended_effects": ["cross_water"],
            "required_materials": {"wood": 2},
            "footprint_hint": {"width": 1, "height": 1, "placement": "near_water"},
        },
    )
    assert isinstance(rejected, dict)
    assert rejected["status"] == "rejected"
    assert select_proto_asset_for_adoption_attempt(world, inventor) is None


def test_prototype_attempt_requires_real_materials_and_work() -> None:
    world = _blank_world()
    _seed_village(world)
    inventor = _agent("a-build")
    _admissible_storage_proposal(world, inventor)
    assert world.run_proto_asset_adoption_attempt(inventor) is False
    assert len(world.proto_asset_prototypes) == 1
    instance = world.proto_asset_prototypes[0]
    assert instance["status"] in {"prototype_pending", "prototype_under_construction"}
    assert int(instance.get("construction_progress", 0)) == 0

    loc = instance["location"]
    inventor.x = int(loc["x"])
    inventor.y = int(loc["y"])
    required = dict(instance.get("required_materials", {}))
    inventor.inventory["wood"] = int(required.get("wood", 0))
    inventor.inventory["stone"] = int(required.get("stone", 0))
    assert world.run_proto_asset_adoption_attempt(inventor) in {True, False}
    assert str(world.proto_asset_proposals[0]["status"]) != "prototype_built"


def test_prototype_cannot_complete_remotely() -> None:
    world = _blank_world()
    _seed_village(world)
    inventor = _agent("a-remote", x=0, y=0)
    _admissible_storage_proposal(world, inventor)
    assert world.run_proto_asset_adoption_attempt(inventor) is False
    instance = world.proto_asset_prototypes[0]
    required = dict(instance.get("required_materials", {}))
    inventor.inventory["wood"] = int(required.get("wood", 0))
    inventor.inventory["stone"] = int(required.get("stone", 0))
    for _ in range(8):
        world.run_proto_asset_adoption_attempt(inventor)
        world.tick += 1
    assert str(world.proto_asset_proposals[0]["status"]) != "prototype_built"


def test_local_placement_is_bounded_for_cross_water() -> None:
    world = _blank_world()
    _seed_village(world)
    for y in range(8, 14):
        world.tiles[y][13] = "W"
    inventor = _agent("a-water", x=11, y=11)
    inventor.subjective_state = {"local_signals": {"needs": {"need_storage": False}}}
    inventor.episodic_memory = {
        "recent_events": [
            {"type": "unreachable_target", "outcome": "failure", "location": {"x": 13, "y": 10, "terrain_hint": "water"}},
            {"type": "unreachable_target", "outcome": "failure", "location": {"x": 13, "y": 11, "terrain_hint": "water"}},
        ]
    }
    world.agents = [inventor]
    proposal = maybe_generate_innovation_proposal(world, inventor, source="stub")
    assert isinstance(proposal, dict)
    placement = find_proto_asset_placement(world, inventor, proposal)
    assert placement is not None
    px, py = placement
    assert abs(px - inventor.x) + abs(py - inventor.y) <= 8
    adjacent_water = any(
        0 <= nx < world.width and 0 <= ny < world.height and world.tiles[ny][nx] == "W"
        for nx, ny in ((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1))
    )
    assert adjacent_water is True


def test_successful_and_failed_prototype_status_transitions_and_counters() -> None:
    world = _blank_world()
    _seed_village(world)
    success_agent = _agent("a-success")
    fail_agent = _agent("a-fail", x=11, y=10)
    world.agents = [success_agent, fail_agent]

    # Successful build.
    _admissible_storage_proposal(world, success_agent)
    world.run_proto_asset_adoption_attempt(success_agent)
    success_instance = world.proto_asset_prototypes[0]
    sloc = success_instance["location"]
    success_agent.x = int(sloc["x"])
    success_agent.y = int(sloc["y"])
    success_agent.inventory["wood"] = int(success_instance["required_materials"]["wood"])
    success_agent.inventory["stone"] = int(success_instance["required_materials"]["stone"])
    while str(success_instance.get("status", "")) != "prototype_built":
        world.run_proto_asset_adoption_attempt(success_agent)
        world.tick += 1
        assert world.tick < 80

    # Failing build by stall/missing materials.
    world.tick += 20
    _admissible_storage_proposal(world, fail_agent)
    world.run_proto_asset_adoption_attempt(fail_agent)
    fail_instance = world.proto_asset_prototypes[-1]
    world.tick = int(fail_instance.get("tick_created", 0)) + 220
    world.update_proto_asset_prototypes()

    stats = world.reflection_stats
    assert int(stats.get("prototype_attempt_count", 0)) >= 2
    assert int(stats.get("prototype_built_count", 0)) >= 1
    assert int(stats.get("prototype_failed_count", 0)) >= 1
    assert isinstance(stats.get("prototype_failure_reasons", {}), dict)
    statuses = {str(p.get("status", "")) for p in world.proto_asset_proposals}
    assert "prototype_built" in statuses
    assert "prototype_failed" in statuses


def test_built_prototype_not_evaluated_immediately() -> None:
    world = _blank_world()
    _seed_village(world)
    agent = _agent("a-eval-delay")
    world.agents = [agent]
    instance = _build_storage_prototype(world, agent)
    assert str(instance.get("usefulness_status", "")) == "unknown"
    status, _, _ = evaluate_prototype_usefulness(world, instance)
    assert status == "unknown"


def test_storage_prototype_can_become_useful_with_local_usage_evidence() -> None:
    world = _blank_world()
    _seed_village(world)
    agent = _agent("a-eval-useful")
    observer = _agent("a-observer", x=9, y=10, role="hauler")
    observer.episodic_memory = {"recent_events": [], "max_events": 40}
    world.agents = [agent, observer]
    instance = _build_storage_prototype(world, agent)
    loc = instance["location"]
    px = int(loc["x"])
    py = int(loc["y"])

    # Create local storage/logistics activity in evaluation window.
    for t in range(45):
        for b in world.buildings.values():
            if str(b.get("type", "")) != "storage":
                continue
            storage = b.get("storage", {})
            if isinstance(storage, dict):
                storage["wood"] = int(storage.get("wood", 0)) + (1 if t % 2 == 0 else -1)
                if int(storage.get("wood", 0)) < 0:
                    storage["wood"] = 0
        observer.x = px
        observer.y = py
        world.tick += 1
        world.update_proto_asset_prototypes()

    assert str(instance.get("usefulness_status", "")) == "useful"
    assert float(instance.get("usefulness_score", 0.0)) >= 0.55
    assert "improved_storage_access" in set(instance.get("evaluation_basis", []))
    assert int(world.reflection_stats.get("prototype_useful_count", 0)) >= 1


def test_prototype_can_become_ineffective_with_no_observed_benefit() -> None:
    world = _blank_world()
    _seed_village(world)
    agent = _agent("a-eval-ineff")
    world.agents = [agent]
    instance = _build_storage_prototype(world, agent)
    for _ in range(45):
        world.tick += 1
        world.update_proto_asset_prototypes()
    assert str(instance.get("usefulness_status", "")) == "ineffective"
    assert "no_observed_benefit" in set(instance.get("evaluation_basis", []))
    assert int(world.reflection_stats.get("prototype_ineffective_count", 0)) >= 1


def test_usefulness_is_deterministic_and_does_not_promote_to_permanent_asset() -> None:
    w1 = _blank_world()
    _seed_village(w1)
    a1 = _agent("a-det-1")
    w1.agents = [a1]
    i1 = _build_storage_prototype(w1, a1)
    for _ in range(45):
        w1.tick += 1
        w1.update_proto_asset_prototypes()

    w2 = _blank_world()
    _seed_village(w2)
    a2 = _agent("a-det-2")
    w2.agents = [a2]
    i2 = _build_storage_prototype(w2, a2)
    for _ in range(45):
        w2.tick += 1
        w2.update_proto_asset_prototypes()

    assert str(i1.get("usefulness_status", "")) == str(i2.get("usefulness_status", ""))
    assert float(i1.get("usefulness_score", 0.0)) == float(i2.get("usefulness_score", 0.0))
    assert str(i1.get("status", "")) == "prototype_built"
    assert str(i2.get("status", "")) == "prototype_built"
