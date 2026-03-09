from __future__ import annotations

from agent import (
    Agent,
    build_agent_cognitive_context,
    ensure_agent_cognitive_profile,
    should_agent_reflect,
    update_agent_cognitive_profile,
    write_episodic_memory_event,
)
from brain import FoodBrain, LLMBrain
from world import World


class _NoopPlanner:
    async def propose_goal_async(self, prompt: str) -> str:
        return "survive"


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
    world.llm_enabled = True
    world.max_llm_calls_per_tick = 1
    world.llm_calls_this_tick = 0
    return world


def test_all_agents_get_initialized_cognitive_profile() -> None:
    a1 = Agent(x=0, y=0, brain=None)
    a2 = Agent(x=1, y=1, brain=None)
    p1 = ensure_agent_cognitive_profile(a1)
    p2 = ensure_agent_cognitive_profile(a2)
    for p in (p1, p2):
        assert "llm_enabled" in p
        assert "cognitive_tier" in p
        assert "reflection_budget" in p
        assert "reflection_priority" in p
        assert "max_context_items" in p


def test_leaders_not_privileged_by_default() -> None:
    leader = Agent(x=0, y=0, brain=None)
    leader.role = "leader"
    npc = Agent(x=1, y=1, brain=None)
    npc.role = "npc"
    p_leader = ensure_agent_cognitive_profile(leader)
    p_npc = ensure_agent_cognitive_profile(npc)
    assert float(p_leader["reflection_priority"]) == float(p_npc["reflection_priority"])
    assert int(p_leader["cognitive_tier"]) == int(p_npc["cognitive_tier"])


def test_should_reflect_is_deterministic() -> None:
    world = _flat_world()
    world.tick = 200
    agent = Agent(x=10, y=10, brain=None)
    ensure_agent_cognitive_profile(agent)
    agent.subjective_state = {
        "attention": {"top_resource_targets": [1, 2], "top_building_targets": [1], "top_social_targets": []},
        "local_signals": {"needs": {"food_urgent": True}},
    }
    first = should_agent_reflect(world, agent)
    second = should_agent_reflect(world, agent)
    assert first == second


def test_cooldown_and_budget_limits_enforced() -> None:
    world = _flat_world()
    world.tick = 100
    agent = Agent(x=0, y=0, brain=None)
    profile = ensure_agent_cognitive_profile(agent)
    profile["last_reflection_tick"] = 90
    profile["reflection_cooldown_ticks"] = 20
    profile["reflection_budget"] = 0.8
    assert should_agent_reflect(world, agent) is False
    profile["last_reflection_tick"] = 0
    profile["reflection_budget"] = 0.05
    assert should_agent_reflect(world, agent) is False


def test_blocked_agents_are_more_eligible_than_trivial_cases() -> None:
    world = _flat_world()
    world.tick = 250
    blocked = Agent(x=5, y=5, brain=None)
    trivial = Agent(x=6, y=5, brain=None)
    for a in (blocked, trivial):
        p = ensure_agent_cognitive_profile(a)
        p["last_reflection_tick"] = -1000
        p["reflection_budget"] = 0.8
    blocked.current_intention = {"type": "gather_food", "failed_ticks": 3}
    blocked.subjective_state = {
        "attention": {"top_resource_targets": [1, 2, 3], "top_building_targets": [1], "top_social_targets": [1]},
        "local_signals": {"needs": {"food_urgent": True}},
    }
    trivial.current_intention = {"type": "gather_food", "failed_ticks": 0}
    trivial.subjective_state = {
        "attention": {"top_resource_targets": [], "top_building_targets": [], "top_social_targets": []},
        "local_signals": {"needs": {}},
    }
    assert should_agent_reflect(world, blocked) is True
    assert should_agent_reflect(world, trivial) is False


def test_cognitive_maturity_increases_gradually_from_local_success() -> None:
    world = _flat_world()
    agent = Agent(x=10, y=10, brain=None)
    base = ensure_agent_cognitive_profile(agent)
    base_tier = int(base["cognitive_tier"])
    base_priority = float(base["reflection_priority"])
    world.tick = 120
    for i in range(8):
        write_episodic_memory_event(
            agent,
            tick=world.tick + i,
            event_type="construction_progress",
            outcome="success",
            location=(10, 10),
            salience=1.2,
        )
    agent.social_influence = 0.7
    updated = update_agent_cognitive_profile(world, agent)
    assert int(updated["cognitive_tier"]) >= base_tier
    assert float(updated["reflection_priority"]) >= base_priority


def test_social_influence_can_raise_priority_later() -> None:
    world = _flat_world()
    agent = Agent(x=2, y=2, brain=None)
    p = ensure_agent_cognitive_profile(agent)
    world.tick = 50
    agent.social_influence = 0.1
    low = float(update_agent_cognitive_profile(world, agent)["reflection_priority"])
    world.tick = 200
    agent.social_influence = 0.85
    high = float(update_agent_cognitive_profile(world, agent)["reflection_priority"])
    assert high >= low


def test_cognitive_context_is_bounded_and_non_omniscient() -> None:
    world = _flat_world()
    agent = Agent(x=10, y=10, brain=None)
    profile = ensure_agent_cognitive_profile(agent)
    profile["max_context_items"] = 3
    agent.subjective_state = {
        "attention": {
            "top_resource_targets": [{"x": 11, "y": 10}] * 6,
            "top_building_targets": [{"x": 10, "y": 11}] * 6,
            "top_social_targets": [{"agent_id": "a"}] * 6,
        },
        "local_signals": {"needs": {"food_urgent": True}, "market_state": {"food": {"pressure": 0.7}}},
        "local_culture": {"cooperation_norm": 0.6},
    }
    for i in range(6):
        write_episodic_memory_event(
            agent,
            tick=i,
            event_type="found_resource",
            outcome="success",
            location=(10 + i, 10),
            resource_type="food",
            salience=1.0,
        )
    context = build_agent_cognitive_context(world, agent)
    assert len(context["recent_events"]) <= 3
    assert len(context["attention"]["top_resource_targets"]) <= 3
    assert "all_agents" not in context
    assert "global_map" not in context


def test_fallback_works_when_reflection_is_skipped() -> None:
    world = _flat_world()
    world.llm_enabled = False
    brain = LLMBrain(planner=_NoopPlanner(), fallback=FoodBrain(), think_every_ticks=1)
    agent = Agent(x=10, y=10, brain=brain, is_player=False, player_id=None)
    agent.hunger = 90
    agent.inventory["food"] = 2
    ensure_agent_cognitive_profile(agent)["llm_enabled"] = True
    world.food = {(11, 10)}
    world.agents = [agent]
    agent.update_subjective_state(world)
    action = brain.decide(agent, world)
    assert isinstance(action, tuple)
    assert agent.llm_pending is False
