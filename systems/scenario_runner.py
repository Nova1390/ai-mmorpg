from __future__ import annotations

from typing import Any, Dict, Optional

from brain import FoodBrain, LLMBrain
from planner import Planner
from world import World


def run_simulation_scenario(
    *,
    seed: Optional[int] = 123,
    width: int = 72,
    height: int = 72,
    initial_population: int = 32,
    ticks: int = 400,
    snapshot_interval: int = 10,
    llm_enabled: bool = False,
    llm_reflection_mode: str = "provider_with_stub_fallback",
    llm_stub_enabled: bool = True,
    llm_force_local_stub: bool = False,
    history_limit: int = 120,
) -> Dict[str, Any]:
    world = World(
        width=width,
        height=height,
        num_agents=initial_population,
        seed=seed,
        llm_enabled=llm_enabled,
    )
    # Scenario runner executes in a sync loop; allow bounded sync LLM execution
    # when no asyncio loop is running.
    world.llm_sync_execution = bool(llm_enabled)
    world.llm_reflection_mode = str(llm_reflection_mode)
    world.llm_stub_enabled = bool(llm_stub_enabled)
    world.llm_force_local_stub = bool(llm_force_local_stub)
    if llm_enabled:
        fallback = FoodBrain(vision_radius=8)
        planner = Planner(model="phi3")
        llm_brain = LLMBrain(planner=planner, fallback=fallback, think_every_ticks=20)
        for agent in getattr(world, "agents", []):
            if getattr(agent, "alive", False):
                agent.brain = llm_brain
    if hasattr(world, "metrics_collector"):
        world.metrics_collector.snapshot_interval = max(1, int(snapshot_interval))

    for _ in range(max(0, int(ticks))):
        world.update()

    latest = world.metrics_collector.latest() if hasattr(world, "metrics_collector") else {}
    history = world.metrics_collector.history(limit=history_limit) if hasattr(world, "metrics_collector") else []
    return {
        "scenario": {
            "seed": seed,
            "width": int(width),
            "height": int(height),
            "initial_population": int(initial_population),
            "ticks": int(ticks),
            "snapshot_interval": int(snapshot_interval),
            "llm_enabled": bool(llm_enabled),
            "llm_reflection_mode": str(llm_reflection_mode),
            "llm_stub_enabled": bool(llm_stub_enabled),
            "llm_force_local_stub": bool(llm_force_local_stub),
        },
        "summary": latest,
        "history": history,
    }
