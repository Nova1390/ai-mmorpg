from __future__ import annotations

import asyncio

from agent import (
    Agent,
    build_agent_cognitive_context,
    detect_agent_reflection_reason,
    ensure_agent_cognitive_profile,
)
from brain import FoodBrain, LLMBrain
from world import World


class _MalformedReflectionPlanner:
    async def propose_goal_async(self, prompt: str) -> str:
        return "not-json"


class _ValidReflectionPlanner:
    async def propose_goal_async(self, prompt: str) -> str:
        return (
            '{"suggested_intention_type":"gather_food",'
            '"suggested_target_kind":"resource",'
            '"suggested_resource_type":"food",'
            '"reasoning_tags":["survival"]}'
        )


class _FencedValidPlanner:
    async def propose_goal_async(self, prompt: str) -> str:
        return (
            "some prefix\n```json\n"
            '{"suggested_intention_type":"GATHER_FOOD","suggested_target_kind":"RESOURCE","suggested_resource_type":"FOOD","reasoning_tags":["SURVIVAL"]}'
            "\n```\nsuffix"
        )


class _UnsupportedEnumPlanner:
    async def propose_goal_async(self, prompt: str) -> str:
        return (
            '{"suggested_intention_type":"global_plan",'
            '"suggested_target_kind":"planet",'
            '"suggested_resource_type":"gold",'
            '"reasoning_tags":["omniscience"]}'
        )


class _UnavailablePlanner:
    async def propose_goal_async(self, prompt: str) -> str:
        raise OSError("provider unreachable")


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
    world.llm_reflection_mode = "provider_with_stub_fallback"
    world.llm_stub_enabled = True
    world.llm_calls_this_tick = 0
    world.max_llm_calls_per_tick = 1
    return world


def test_blocked_intention_produces_reflection_reason() -> None:
    world = _flat_world()
    agent = Agent(x=10, y=10, brain=None)
    agent.current_intention = {"type": "deliver_resource", "failed_ticks": 3}
    agent.subjective_state = {"attention": {}, "local_signals": {"needs": {}}}
    assert detect_agent_reflection_reason(world, agent) == "blocked_intention"


def test_conflicting_local_needs_can_produce_reason() -> None:
    world = _flat_world()
    agent = Agent(x=10, y=10, brain=None)
    agent.hunger = 30
    agent.subjective_state = {
        "attention": {
            "top_resource_targets": [{"salience": 1.2}, {"salience": 1.15}],
            "top_building_targets": [{"salience": 1.1}],
            "top_social_targets": [],
        },
        "local_signals": {"needs": {"need_materials": True}},
        "local_culture": {"cooperation_norm": 0.5},
    }
    assert detect_agent_reflection_reason(world, agent) == "conflicting_local_needs"


def test_malformed_reflection_output_rejected_safely() -> None:
    world = _flat_world()
    brain = LLMBrain(planner=_MalformedReflectionPlanner(), fallback=FoodBrain(), think_every_ticks=1)
    agent = Agent(x=10, y=10, brain=brain, is_player=False, player_id=None)
    ensure_agent_cognitive_profile(agent)
    agent.subjective_state = {
        "attention": {"top_resource_targets": [1, 2], "top_building_targets": [1], "top_social_targets": []},
        "local_signals": {"needs": {"food_urgent": True}},
        "local_culture": {},
    }
    agent.current_intention = {"type": "gather_resource", "failed_ticks": 3}
    agent.llm_pending = True
    asyncio.run(brain._request_reflection(agent, world, "x", reflection_reason="blocked_intention"))
    profile = ensure_agent_cognitive_profile(agent)
    assert profile["last_reflection_outcome"] == "deterministic_stub_used"
    hint = getattr(agent, "reflection_hint", None)
    assert isinstance(hint, dict)
    assert hint.get("source") == "stub"


def test_fenced_json_reflection_output_is_parsed_and_accepted() -> None:
    world = _flat_world()
    brain = LLMBrain(planner=_FencedValidPlanner(), fallback=FoodBrain(), think_every_ticks=1)
    agent = Agent(x=10, y=10, brain=brain, is_player=False, player_id=None)
    ensure_agent_cognitive_profile(agent)
    agent.subjective_state = {
        "attention": {"top_resource_targets": [1], "top_building_targets": [], "top_social_targets": []},
        "local_signals": {"needs": {"food_urgent": True}},
        "local_culture": {},
    }
    agent.current_intention = {"type": "gather_resource", "failed_ticks": 3}
    agent.llm_pending = True
    asyncio.run(brain._request_reflection(agent, world, "x", reflection_reason="blocked_intention"))
    hint = getattr(agent, "reflection_hint", None)
    assert isinstance(hint, dict)
    assert hint.get("source") == "provider"
    assert hint.get("suggested_intention_type") == "gather_food"


def test_unsupported_enums_rejected_with_reason_and_stub_used() -> None:
    world = _flat_world()
    brain = LLMBrain(planner=_UnsupportedEnumPlanner(), fallback=FoodBrain(), think_every_ticks=1)
    agent = Agent(x=10, y=10, brain=brain, is_player=False, player_id=None)
    ensure_agent_cognitive_profile(agent)
    agent.subjective_state = {
        "attention": {"top_resource_targets": [1], "top_building_targets": [1], "top_social_targets": []},
        "local_signals": {"needs": {"food_urgent": True}},
        "local_culture": {},
    }
    agent.current_intention = {"type": "gather_resource", "failed_ticks": 3}
    agent.llm_pending = True
    asyncio.run(brain._request_reflection(agent, world, "x", reflection_reason="blocked_intention"))
    stats = world.reflection_stats
    assert int(stats["reflection_rejection_reason_counts"].get("unsupported_values", 0)) >= 1
    assert int(stats["reflection_accepted_source_counts"].get("stub", 0)) >= 1


def test_accepted_reflection_applies_only_local_bounded_choice() -> None:
    world = _flat_world()
    world.food = {(11, 10)}
    brain = LLMBrain(planner=_ValidReflectionPlanner(), fallback=FoodBrain(), think_every_ticks=1)
    agent = Agent(x=10, y=10, brain=brain, is_player=False, player_id=None)
    ensure_agent_cognitive_profile(agent)
    agent.current_intention = {"type": "gather_resource", "failed_ticks": 3}
    agent.subjective_state = {
        "attention": {
            "top_resource_targets": [{"resource": "food", "x": 11, "y": 10, "salience": 1.5}],
            "top_building_targets": [],
            "top_social_targets": [],
        },
        "local_signals": {"needs": {"food_urgent": True}},
        "local_culture": {},
    }
    agent.llm_pending = True
    asyncio.run(brain._request_reflection(agent, world, "x", reflection_reason="blocked_intention"))
    assert isinstance(getattr(agent, "reflection_hint", None), dict)
    brain.decide(agent, world)
    current = getattr(agent, "current_intention", {}) or {}
    assert str(current.get("type", "")) in {
        "gather_food",
        "gather_resource",
        "deliver_resource",
        "build_structure",
        "work_mine",
        "work_lumberyard",
        "explore",
    }
    assert getattr(agent, "reflection_hint", None) is None


def test_non_leader_agents_can_reflect() -> None:
    world = _flat_world()
    world.tick = 200
    brain = LLMBrain(planner=_ValidReflectionPlanner(), fallback=FoodBrain(), think_every_ticks=1)
    agent = Agent(x=5, y=5, brain=brain, is_player=False, player_id=None)
    agent.role = "builder"
    profile = ensure_agent_cognitive_profile(agent)
    profile["last_reflection_tick"] = -1000
    profile["reflection_budget"] = 0.8
    agent.subjective_state = {
        "attention": {"top_resource_targets": [1, 2], "top_building_targets": [1], "top_social_targets": []},
        "local_signals": {"needs": {"food_urgent": True}},
        "local_culture": {},
    }
    agent.current_intention = {"type": "build_structure", "failed_ticks": 3}
    assert brain.maybe_reflect_with_llm(agent, world) is True


def test_provider_unavailable_uses_deterministic_stub_and_is_observable() -> None:
    world = _flat_world()
    world.tick = 120
    world.llm_sync_execution = True
    brain = LLMBrain(planner=_UnavailablePlanner(), fallback=FoodBrain(), think_every_ticks=1)
    agent = Agent(x=10, y=10, brain=brain, is_player=False, player_id=None)
    profile = ensure_agent_cognitive_profile(agent)
    profile["last_reflection_tick"] = -1000
    profile["reflection_budget"] = 1.0
    agent.last_llm_tick = -1000
    agent.subjective_state = {
        "attention": {"top_resource_targets": [1], "top_building_targets": [1], "top_social_targets": []},
        "local_signals": {"needs": {"food_urgent": True}},
        "local_culture": {},
    }
    agent.current_intention = {"type": "gather_resource", "failed_ticks": 3}
    assert brain.maybe_reflect_with_llm(agent, world) is True
    stats = world.reflection_stats
    assert int(stats["reflection_success_count"]) >= 1
    assert int(stats["reflection_accepted_source_counts"].get("stub", 0)) >= 1
    hint = getattr(agent, "reflection_hint", None)
    assert isinstance(hint, dict)
    assert hint.get("source") == "stub"


def test_provider_failure_without_stub_uses_deterministic_fallback() -> None:
    world = _flat_world()
    world.tick = 120
    world.llm_sync_execution = True
    world.llm_stub_enabled = False
    brain = LLMBrain(planner=_UnavailablePlanner(), fallback=FoodBrain(), think_every_ticks=1)
    agent = Agent(x=10, y=10, brain=brain, is_player=False, player_id=None)
    profile = ensure_agent_cognitive_profile(agent)
    profile["last_reflection_tick"] = -1000
    profile["reflection_budget"] = 1.0
    agent.last_llm_tick = -1000
    agent.subjective_state = {
        "attention": {"top_resource_targets": [1], "top_building_targets": [1], "top_social_targets": []},
        "local_signals": {"needs": {"food_urgent": True}},
        "local_culture": {},
    }
    agent.current_intention = {"type": "gather_resource", "failed_ticks": 3}
    assert brain.maybe_reflect_with_llm(agent, world) is True
    stats = world.reflection_stats
    assert int(stats["reflection_fallback_reason_counts"].get("provider_unavailable", 0)) >= 1
    assert getattr(agent, "reflection_hint", None) is None


def test_budget_cooldown_and_global_cap_still_gate_reflection() -> None:
    world = _flat_world()
    brain = LLMBrain(planner=_ValidReflectionPlanner(), fallback=FoodBrain(), think_every_ticks=1)
    agent = Agent(x=5, y=5, brain=brain, is_player=False, player_id=None)
    profile = ensure_agent_cognitive_profile(agent)
    agent.subjective_state = {
        "attention": {"top_resource_targets": [1, 2], "top_building_targets": [1], "top_social_targets": []},
        "local_signals": {"needs": {"food_urgent": True}},
        "local_culture": {},
    }
    agent.current_intention = {"type": "gather_food", "failed_ticks": 3}

    profile["last_reflection_tick"] = world.tick
    profile["reflection_cooldown_ticks"] = 20
    assert brain.maybe_reflect_with_llm(agent, world) is False

    profile["last_reflection_tick"] = -1000
    profile["reflection_budget"] = 0.05
    assert brain.maybe_reflect_with_llm(agent, world) is False

    profile["reflection_budget"] = 0.8
    world.llm_calls_this_tick = world.max_llm_calls_per_tick
    assert brain.maybe_reflect_with_llm(agent, world) is False


def test_reflection_context_contains_no_omniscient_dump() -> None:
    world = _flat_world()
    agent = Agent(x=10, y=10, brain=None)
    ensure_agent_cognitive_profile(agent)["max_context_items"] = 4
    agent.subjective_state = {
        "attention": {"top_resource_targets": [], "top_building_targets": [], "top_social_targets": []},
        "local_signals": {"needs": {}},
        "local_culture": {},
    }
    ctx = build_agent_cognitive_context(world, agent)
    assert "all_agents" not in ctx
    assert "full_world_tiles" not in ctx


def test_fallback_remains_when_reflection_skipped() -> None:
    world = _flat_world()
    world.llm_enabled = False
    brain = LLMBrain(planner=_ValidReflectionPlanner(), fallback=FoodBrain(), think_every_ticks=1)
    agent = Agent(x=10, y=10, brain=brain, is_player=False, player_id=None)
    agent.hunger = 90
    agent.inventory["food"] = 2
    agent.subjective_state = {"attention": {}, "local_signals": {"needs": {}}, "local_culture": {}}
    action = brain.decide(agent, world)
    assert isinstance(action, tuple)
    assert agent.llm_pending is False
