from __future__ import annotations

import asyncio

from agent import Agent
from brain import FoodBrain, LLMBrain
import server
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

