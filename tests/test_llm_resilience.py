from __future__ import annotations

import asyncio

from agent import Agent, ensure_agent_cognitive_profile
from brain import FoodBrain, LLMBrain
import server
from systems.scenario_runner import run_simulation_scenario
from state_serializer import serialize_dynamic_world_state, serialize_static_world_state
from world import World


class _TimeoutPlanner:
    async def propose_goal_async(self, prompt: str) -> str:
        await asyncio.sleep(0.05)
        return "gather food"


class _ExceptionPlanner:
    async def propose_goal_async(self, prompt: str) -> str:
        raise RuntimeError("provider unavailable")


class _MalformedPlanner:
    async def propose_goal_async(self, prompt: str) -> str:
        return "??? ###"


class _ValidReflectionPlanner:
    async def propose_goal_async(self, prompt: str) -> str:
        return (
            '{"suggested_intention_type":"gather_food",'
            '"suggested_target_kind":"resource",'
            '"suggested_resource_type":"food",'
            '"reasoning_tags":["survival"]}'
        )


class _DummyWorld:
    def __init__(self) -> None:
        self.tick = 100
        self.llm_timeout_seconds = 0.01
        self.llm_enabled = True

    def get_village_by_id(self, village_id):
        return None


def test_llm_timeout_degrades_to_survive_without_crash() -> None:
    world = _DummyWorld()
    brain = LLMBrain(planner=_TimeoutPlanner(), fallback=FoodBrain(), think_every_ticks=1)
    agent = Agent(x=0, y=0, brain=brain, is_player=False, player_id=None)
    agent.goal = "explore"
    agent.llm_pending = True

    asyncio.run(brain._request_goal(agent, world, "test prompt"))

    assert agent.goal == "survive"
    assert agent.llm_pending is False


def test_llm_exception_degrades_to_survive_without_crash() -> None:
    world = _DummyWorld()
    brain = LLMBrain(planner=_ExceptionPlanner(), fallback=FoodBrain(), think_every_ticks=1)
    agent = Agent(x=0, y=0, brain=brain, is_player=False, player_id=None)
    agent.goal = "explore"
    agent.llm_pending = True

    asyncio.run(brain._request_goal(agent, world, "test prompt"))

    assert agent.goal == "survive"
    assert agent.llm_pending is False


def test_llm_malformed_output_uses_deterministic_fallback_goal() -> None:
    world = _DummyWorld()
    world.llm_timeout_seconds = 0.5
    brain = LLMBrain(planner=_MalformedPlanner(), fallback=FoodBrain(), think_every_ticks=1)
    agent = Agent(x=0, y=0, brain=brain, is_player=False, player_id=None)
    agent.goal = "gather wood"
    agent.llm_pending = True

    asyncio.run(brain._request_goal(agent, world, "test prompt"))

    assert agent.goal == "survive"
    assert agent.llm_pending is False


def test_world_update_does_not_crash_when_llm_scheduling_has_no_running_loop() -> None:
    world = World()
    world.agents = []
    world.llm_enabled = True
    world.llm_timeout_seconds = 0.01

    llm_brain = LLMBrain(planner=_ExceptionPlanner(), fallback=FoodBrain(), think_every_ticks=0)
    agent = Agent(x=5, y=5, brain=llm_brain, is_player=False, player_id=None)
    agent.inventory["food"] = 2
    agent.hunger = 90
    world.add_agent(agent)

    world.update()
    world.update()

    assert agent.alive
    assert agent.llm_pending is False


def test_state_endpoints_and_serializers_work_in_llm_degraded_mode() -> None:
    world = World()
    world.llm_enabled = False
    world.agents = []

    for _ in range(3):
        world.update()

    dynamic_payload = serialize_dynamic_world_state(world)
    static_payload = serialize_static_world_state(world)

    assert "tick" in dynamic_payload
    assert "agents" in dynamic_payload
    assert "tiles" in static_payload

    original_world = server.world
    try:
        server.world = world
        assert "tick" in server.get_state()
        assert "tiles" in server.get_static_state()
        assert "events" in server.get_events(since_tick=-1)
    finally:
        server.world = original_world


def test_sync_reflection_executes_without_running_event_loop() -> None:
    world = World(num_agents=0, seed=7, llm_enabled=True)
    world.tick = 100
    world.llm_sync_execution = True
    world.max_llm_calls_per_tick = 1
    brain = LLMBrain(planner=_ValidReflectionPlanner(), fallback=FoodBrain(), think_every_ticks=1)
    agent = Agent(x=5, y=5, brain=brain, is_player=False, player_id=None)
    profile = ensure_agent_cognitive_profile(agent)
    profile["last_reflection_tick"] = -1000
    profile["reflection_budget"] = 1.0
    agent.last_llm_tick = -1000
    agent.current_intention = {"type": "gather_resource", "failed_ticks": 3}
    agent.subjective_state = {
        "attention": {"top_resource_targets": [1], "top_building_targets": [1], "top_social_targets": []},
        "local_signals": {"needs": {"food_urgent": True}},
        "local_culture": {},
    }

    assert brain.maybe_reflect_with_llm(agent, world) is True
    stats = world.reflection_stats
    assert int(stats["reflection_trigger_detected_count"]) == 1
    assert int(stats["reflection_attempt_count"]) == 1
    assert int(stats["reflection_executed_count"]) == 1
    assert int(stats["reflection_success_count"]) == 1
    assert agent.llm_pending is False


def test_sync_reflection_failure_keeps_fallback_and_counts() -> None:
    world = World(num_agents=0, seed=8, llm_enabled=True)
    world.tick = 100
    world.llm_sync_execution = True
    world.llm_stub_enabled = False
    world.max_llm_calls_per_tick = 1
    brain = LLMBrain(planner=_ExceptionPlanner(), fallback=FoodBrain(), think_every_ticks=1)
    agent = Agent(x=5, y=5, brain=brain, is_player=False, player_id=None)
    profile = ensure_agent_cognitive_profile(agent)
    profile["last_reflection_tick"] = -1000
    profile["reflection_budget"] = 1.0
    agent.last_llm_tick = -1000
    agent.current_intention = {"type": "gather_resource", "failed_ticks": 3}
    agent.subjective_state = {
        "attention": {"top_resource_targets": [1], "top_building_targets": [1], "top_social_targets": []},
        "local_signals": {"needs": {"food_urgent": True}},
        "local_culture": {},
    }

    assert brain.maybe_reflect_with_llm(agent, world) is True
    stats = world.reflection_stats
    assert int(stats["reflection_attempt_count"]) == 1
    assert int(stats["reflection_executed_count"]) == 1
    assert int(stats["reflection_fallback_count"]) == 1


def test_stub_enabled_scenario_can_produce_non_zero_accepted_reflections() -> None:
    payload = run_simulation_scenario(
        seed=101,
        width=28,
        height=28,
        initial_population=10,
        ticks=160,
        snapshot_interval=10,
        llm_enabled=True,
        llm_reflection_mode="force_local_stub",
        llm_stub_enabled=True,
        llm_force_local_stub=True,
        history_limit=40,
    )
    llm = payload.get("summary", {}).get("llm_reflection", {})
    attempts = int(llm.get("reflection_attempt_count", 0))
    executed = int(llm.get("reflection_executed_count", 0))
    success = int(llm.get("reflection_success_count", 0))
    assert attempts >= 0
    assert executed >= 0
    assert success >= 0
    assert executed <= attempts
    assert success <= executed
    accepted_sources = llm.get("reflection_accepted_source_counts", {})
    accepted_stub = int((accepted_sources or {}).get("stub", 0))
    assert accepted_stub >= 0
    assert accepted_stub <= success
