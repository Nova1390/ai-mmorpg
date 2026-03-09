from __future__ import annotations

from agent import Agent, evaluate_agent_salience, write_episodic_memory_event
from brain import FoodBrain
from systems.village_ai_system import (
    CULTURE_UPDATE_INTERVAL_TICKS,
    ensure_village_proto_culture,
    update_village_proto_culture,
)
from world import World


def _flat_world() -> World:
    world = World()
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
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


def _base_village() -> dict:
    return {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 10, "y": 10},
        "houses": 4,
        "population": 3,
        "tiles": [{"x": 10, "y": 10}],
        "leader_id": None,
        "strategy": "stabilize",
        "relation": "peace",
        "target_village_id": None,
        "migration_target_id": None,
        "power": 0,
        "storage": {"food": 8, "wood": 5, "stone": 3},
        "storage_pos": {"x": 10, "y": 10},
        "farm_zone_center": {"x": 12, "y": 12},
        "priority_history": [],
        "leader_profile": None,
        "tier": 1,
        "market_state": {
            "food": {"supply": 8, "demand": 6, "pressure": 0.1, "local_price_index": 0.9},
            "wood": {"supply": 5, "demand": 5, "pressure": 0.2, "local_price_index": 1.0},
            "stone": {"supply": 3, "demand": 4, "pressure": 0.4, "local_price_index": 1.2},
        },
        "production_metrics": {
            "wood_from_lumberyards": 0,
            "stone_from_mines": 0,
        },
    }


def test_proto_culture_initialization_is_deterministic() -> None:
    v1 = _base_village()
    v2 = _base_village()
    c1 = ensure_village_proto_culture(v1)
    c2 = ensure_village_proto_culture(v2)
    assert c1 == c2
    for k in ("cooperation_norm", "work_norm", "exploration_norm", "risk_norm", "cultural_stability"):
        assert 0.0 <= float(c1[k]) <= 1.0
    for r in ("food", "wood", "stone"):
        assert 0.0 <= float(c1["resource_focus"][r]) <= 1.0


def test_proto_culture_values_remain_bounded() -> None:
    world = _flat_world()
    village = _base_village()
    world.villages = [village]
    members = [Agent(x=10, y=10, brain=None) for _ in range(3)]
    for m in members:
        m.village_id = 1
    world.agents = members

    ensure_village_proto_culture(village)
    for i in range(6):
        world.tick = i * CULTURE_UPDATE_INTERVAL_TICKS
        for m in members:
            write_episodic_memory_event(
                m,
                tick=world.tick,
                event_type="failed_resource_search" if i % 2 else "construction_progress",
                outcome="failure" if i % 2 else "success",
                location=(10, 10),
                salience=1.2,
            )
        update_village_proto_culture(world, village, members)
    culture = village["proto_culture"]
    for k in ("cooperation_norm", "work_norm", "exploration_norm", "risk_norm", "cultural_stability"):
        assert 0.0 <= float(culture[k]) <= 1.0


def test_culture_drifts_from_cooperative_events() -> None:
    world = _flat_world()
    village = _base_village()
    world.villages = [village]
    members = [Agent(x=10, y=10, brain=None) for _ in range(2)]
    for m in members:
        m.village_id = 1
        m.subjective_state = {"nearby_agents": [{"agent_id": "peer", "role": "npc", "same_village": True}]}
    world.agents = members

    base = ensure_village_proto_culture(village)["cooperation_norm"]
    world.tick = CULTURE_UPDATE_INTERVAL_TICKS
    for m in members:
        write_episodic_memory_event(
            m,
            tick=world.tick,
            event_type="delivered_material",
            outcome="success",
            location=(10, 10),
            salience=1.2,
        )
    update_village_proto_culture(world, village, members)
    assert float(village["proto_culture"]["cooperation_norm"]) >= float(base)


def test_culture_drifts_from_exploration_success_and_construction() -> None:
    world = _flat_world()
    village = _base_village()
    world.villages = [village]
    members = [Agent(x=10, y=10, brain=None) for _ in range(2)]
    for m in members:
        m.village_id = 1
    world.agents = members

    culture = ensure_village_proto_culture(village)
    base_explore = float(culture["exploration_norm"])
    base_work = float(culture["work_norm"])

    world.tick = CULTURE_UPDATE_INTERVAL_TICKS
    write_episodic_memory_event(
        members[0],
        tick=world.tick,
        event_type="found_resource",
        outcome="success",
        location=(13, 10),
        resource_type="food",
        salience=1.1,
    )
    write_episodic_memory_event(
        members[1],
        tick=world.tick,
        event_type="construction_progress",
        outcome="success",
        location=(10, 11),
        salience=1.2,
    )
    village["production_metrics"]["wood_from_lumberyards"] = 3
    update_village_proto_culture(world, village, members)
    assert float(village["proto_culture"]["exploration_norm"]) >= base_explore
    assert float(village["proto_culture"]["work_norm"]) >= base_work


def test_agent_perceives_local_culture_only_for_own_village() -> None:
    world = _flat_world()
    village = _base_village()
    world.villages = [village]
    ensure_village_proto_culture(village)

    insider = Agent(x=10, y=10, brain=None)
    insider.village_id = 1
    outsider = Agent(x=20, y=20, brain=None)
    world.agents = [insider, outsider]

    insider.update_subjective_state(world)
    outsider.update_subjective_state(world)
    assert isinstance(insider.subjective_state.get("local_culture"), dict)
    assert outsider.subjective_state.get("local_culture", {}) == {}


def test_culture_bias_affects_behavior_deterministically() -> None:
    world = _flat_world()
    village = _base_village()
    world.villages = [village]
    culture = ensure_village_proto_culture(village)
    culture["exploration_norm"] = 0.9
    culture["work_norm"] = 0.3
    culture["risk_norm"] = 0.8
    culture["resource_focus"] = {"food": 0.1, "wood": 0.8, "stone": 0.1}
    village["proto_culture"] = culture

    world.food = {(11, 10)}
    world.wood = {(10, 11)}
    world.stone = {(9, 10)}

    a1 = Agent(x=10, y=10, brain=FoodBrain())
    a2 = Agent(x=10, y=10, brain=FoodBrain())
    a1.village_id = 1
    a2.village_id = 1
    a1.hunger = 55
    a2.hunger = 55
    world.agents = [a1, a2]
    a1.update_subjective_state(world)
    a2.update_subjective_state(world)

    s1 = evaluate_agent_salience(world, a1)
    s2 = evaluate_agent_salience(world, a2)
    assert s1["top_resource_targets"] == s2["top_resource_targets"]
    assert s1["top_resource_targets"][0]["resource"] in {"wood", "food", "stone"}

    i1 = a1.brain.select_agent_intention(world, a1)
    i2 = a2.brain.select_agent_intention(world, a2)
    assert i1 == i2


def test_proto_culture_update_is_deterministic() -> None:
    w1 = _flat_world()
    w2 = _flat_world()
    v1 = _base_village()
    v2 = _base_village()
    w1.villages = [v1]
    w2.villages = [v2]
    m1 = [Agent(x=10, y=10, brain=None)]
    m2 = [Agent(x=10, y=10, brain=None)]
    m1[0].village_id = 1
    m2[0].village_id = 1
    w1.agents = m1
    w2.agents = m2
    ensure_village_proto_culture(v1)
    ensure_village_proto_culture(v2)
    w1.tick = CULTURE_UPDATE_INTERVAL_TICKS
    w2.tick = CULTURE_UPDATE_INTERVAL_TICKS
    write_episodic_memory_event(
        m1[0],
        tick=w1.tick,
        event_type="construction_progress",
        outcome="success",
        location=(10, 10),
        salience=1.1,
    )
    write_episodic_memory_event(
        m2[0],
        tick=w2.tick,
        event_type="construction_progress",
        outcome="success",
        location=(10, 10),
        salience=1.1,
    )
    c1 = update_village_proto_culture(w1, v1, m1)
    c2 = update_village_proto_culture(w2, v2, m2)
    assert c1 == c2
