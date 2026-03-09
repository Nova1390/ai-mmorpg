from __future__ import annotations

from agent import Agent
import server
from systems.scenario_runner import run_simulation_scenario
from world import World


def _flat_world() -> World:
    world = World(width=32, height=32, num_agents=0, seed=42, llm_enabled=False)
    world.agents = []
    world.villages = []
    world.buildings = {}
    world.structures = set()
    world.storage_buildings = set()
    world.food = set()
    world.wood = set()
    world.stone = set()
    world.roads = set()
    world.transport_tiles = {}
    return world


def test_scenario_runner_is_deterministic_with_fixed_seed() -> None:
    r1 = run_simulation_scenario(
        seed=77,
        width=30,
        height=30,
        initial_population=12,
        ticks=35,
        snapshot_interval=5,
        llm_enabled=False,
        history_limit=40,
    )
    r2 = run_simulation_scenario(
        seed=77,
        width=30,
        height=30,
        initial_population=12,
        ticks=35,
        snapshot_interval=5,
        llm_enabled=False,
        history_limit=40,
    )
    s1 = r1["summary"]
    s2 = r2["summary"]
    assert s1["tick"] == s2["tick"]
    assert s1["world"]["population"] == s2["world"]["population"]
    assert s1["world"]["villages"] == s2["world"]["villages"]
    assert s1["world"]["buildings_by_type"] == s2["world"]["buildings_by_type"]
    assert "total_food_gathered" in s1["production"]
    assert "direct_food_gathered" in s1["production"]
    assert "total_wood_gathered" in s1["production"]
    assert "direct_wood_gathered" in s1["production"]
    assert "total_stone_gathered" in s1["production"]
    assert "direct_stone_gathered" in s1["production"]


def test_metrics_collector_contains_core_fields() -> None:
    world = _flat_world()
    world.metrics_collector.collect(world)
    snapshot = world.metrics_collector.latest()
    assert "tick" in snapshot
    assert "world" in snapshot
    assert "logistics" in snapshot
    assert "production" in snapshot
    assert "cognition_society" in snapshot
    assert "llm_reflection" in snapshot
    assert "innovation" in snapshot
    assert "proposal_counts_by_status" in snapshot["innovation"]
    assert "proposal_counts_by_effect" in snapshot["innovation"]
    assert "proposal_counts_by_category" in snapshot["innovation"]
    assert "prototype_attempt_count" in snapshot["innovation"]
    assert "prototype_built_count" in snapshot["innovation"]
    assert "prototype_failed_count" in snapshot["innovation"]
    assert "prototype_useful_count" in snapshot["innovation"]
    assert "prototype_neutral_count" in snapshot["innovation"]
    assert "prototype_ineffective_count" in snapshot["innovation"]
    assert "prototype_usefulness_by_effect" in snapshot["innovation"]
    assert "prototype_usefulness_by_category" in snapshot["innovation"]
    assert "known_invention_entry_count" in snapshot["innovation"]
    assert "agents_with_known_inventions" in snapshot["innovation"]
    assert "invention_knowledge_by_source" in snapshot["innovation"]
    assert "invention_knowledge_by_category" in snapshot["innovation"]
    assert "recent_diffused_inventions" in snapshot["innovation"]
    assert "recent_useful_prototypes" in snapshot["innovation"]
    assert "transport_network_counts" in snapshot["world"]


def test_metrics_collector_reports_non_zero_production_after_real_gather() -> None:
    world = _flat_world()
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    village = {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 8, "y": 8},
        "houses": 4,
        "population": 8,
        "storage": {"food": 0, "wood": 0, "stone": 0},
        "storage_pos": {"x": 8, "y": 8},
        "tier": 2,
    }
    world.villages = [village]
    world.place_building("storage", 8, 8, village_id=1, village_uid=village["village_uid"])
    world.wood.update({(9, 7), (9, 8), (9, 9), (10, 8)})
    world.stone.update({(7, 7), (7, 8), (7, 9), (6, 8)})
    world.tiles[7][9] = "F"
    world.tiles[8][9] = "F"
    world.tiles[9][9] = "F"
    world.tiles[8][10] = "F"
    world.tiles[7][7] = "M"
    world.tiles[8][7] = "M"
    world.tiles[9][7] = "M"
    world.tiles[8][6] = "M"
    world.buildings["b-lumber"] = {
        "building_id": "b-lumber",
        "type": "lumberyard",
        "x": 9,
        "y": 8,
        "village_id": 1,
        "village_uid": village["village_uid"],
        "operational_state": "active",
        "linked_resource_type": "wood",
        "linked_resource_tiles_count": 4,
        "connected_to_road": True,
    }
    world.buildings["b-mine"] = {
        "building_id": "b-mine",
        "type": "mine",
        "x": 7,
        "y": 8,
        "village_id": 1,
        "village_uid": village["village_uid"],
        "operational_state": "active",
        "linked_resource_type": "stone",
        "linked_resource_tiles_count": 4,
        "connected_to_road": True,
    }
    world.food.add((8, 8))
    world.wood.add((9, 9))
    world.stone.add((7, 9))
    world.tiles[9][9] = "F"
    world.tiles[9][7] = "M"

    food_agent = Agent(x=8, y=8, brain=None)
    food_agent.village_id = 1
    wood_agent = Agent(x=9, y=9, brain=None)
    wood_agent.village_id = 1
    stone_agent = Agent(x=7, y=9, brain=None)
    stone_agent.village_id = 1
    world.autopickup(food_agent)
    assert world.gather_resource(wood_agent) is True
    assert world.gather_resource(stone_agent) is True

    world.metrics_collector.collect(world)
    production = world.metrics_collector.latest()["production"]
    assert int(production.get("total_food_gathered", 0)) > 0
    assert int(production.get("total_wood_gathered", 0)) > 0
    assert int(production.get("total_stone_gathered", 0)) > 0
    assert int(production.get("direct_wood_gathered", 0)) > 0
    assert int(production.get("direct_stone_gathered", 0)) > 0
    assert int(production.get("wood_from_lumberyards", 0)) > 0
    assert int(production.get("stone_from_mines", 0)) > 0


def test_history_buffer_is_bounded() -> None:
    world = _flat_world()
    world.metrics_collector.snapshot_interval = 1
    world.metrics_collector.history_size = 20
    for _ in range(80):
        world.update()
    hist = world.metrics_collector.history(limit=1000)
    assert len(hist) <= 240  # collector maxlen default clamp in constructor


def test_reflection_stats_counting() -> None:
    world = _flat_world()
    a = Agent(x=1, y=1, brain=None)
    a.role = "builder"
    world.record_reflection_trigger("blocked_intention")
    world.record_reflection_attempt(a, "blocked_intention")
    world.record_reflection_executed(a, "blocked_intention")
    world.record_reflection_outcome("accepted")
    world.record_reflection_outcome("rejected")
    world.record_reflection_skip("cooldown")
    stats = world.reflection_stats
    assert int(stats["reflection_trigger_detected_count"]) == 1
    assert int(stats["reflection_attempt_count"]) == 1
    assert int(stats["reflection_executed_count"]) == 1
    assert int(stats["reflection_success_count"]) == 1
    assert int(stats["reflection_rejection_count"]) == 1
    assert int(stats["reflection_skip_reason_counts"]["cooldown"]) == 1
    assert int(stats["reflection_reason_counts"]["blocked_intention"]) == 1
    assert int(stats["reflection_role_counts"]["builder"]) == 1
    assert int(stats["reflection_executed_reason_counts"]["blocked_intention"]) == 1
    assert int(stats["reflection_executed_role_counts"]["builder"]) == 1
    world.record_reflection_outcome("accepted", reason="deterministic_stub_used", source="stub")
    assert int(stats["reflection_accepted_source_counts"]["stub"]) == 1
    assert int(stats["reflection_outcome_reason_counts"]["deterministic_stub_used"]) == 1


def test_debug_metrics_endpoints_return_structure() -> None:
    world = _flat_world()
    world.update()
    original_world = server.world
    try:
        server.world = world
        metrics = server.get_debug_metrics()
        history_payload = server.get_debug_history(limit=10)
        assert "tick" in metrics
        assert "world" in metrics
        assert "production" in metrics
        assert "total_food_gathered" in metrics["production"]
        assert "history" in history_payload
        assert isinstance(history_payload["history"], list)
    finally:
        server.world = original_world
