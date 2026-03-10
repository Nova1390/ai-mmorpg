from __future__ import annotations

from agent import Agent
from brain import FoodBrain
from world import World


class _MoveRightBrain:
    def decide(self, agent, world):
        return ("move", 1, 0)


def _world() -> World:
    world = World(width=20, height=20, num_agents=0, seed=303, llm_enabled=False)
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    world.villages = [
        {
            "id": 1,
            "village_uid": "v-000001",
            "center": {"x": 10, "y": 10},
            "houses": 3,
            "population": 4,
            "storage": {"food": 0, "wood": 0, "stone": 0},
            "storage_pos": {"x": 10, "y": 10},
            "tier": 1,
            "metrics": {},
        }
    ]
    return world


def test_immediate_backtrack_is_counted() -> None:
    world = _world()
    agent = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    agent.village_id = 1
    agent.role = "hauler"
    agent.task = "village_logistics"
    world.agents = [agent]

    world.record_movement_tick(
        agent,
        from_pos=(10, 10),
        to_pos=(11, 10),
        target=(12, 10),
        action_was_move=True,
    )
    world.record_movement_tick(
        agent,
        from_pos=(11, 10),
        to_pos=(10, 10),
        target=(12, 10),
        action_was_move=True,
    )

    diag = world.compute_movement_diagnostics_snapshot()
    assert int(diag["global"]["backtrack_steps"]) >= 1


def test_repeated_short_reversal_increments_oscillation() -> None:
    world = _world()
    agent = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    agent.village_id = 1
    agent.role = "builder"
    agent.task = "build_house"
    world.agents = [agent]

    world.record_movement_tick(agent, from_pos=(8, 8), to_pos=(9, 8), target=(12, 8), action_was_move=True)
    world.record_movement_tick(agent, from_pos=(9, 8), to_pos=(8, 8), target=(12, 8), action_was_move=True)
    world.record_movement_tick(agent, from_pos=(8, 8), to_pos=(9, 8), target=(12, 8), action_was_move=True)
    world.record_movement_tick(agent, from_pos=(9, 8), to_pos=(8, 8), target=(12, 8), action_was_move=True)

    diag = world.compute_movement_diagnostics_snapshot()
    assert int(diag["global"]["oscillation_events"]) >= 2


def test_no_progress_movement_increments_no_progress_ticks() -> None:
    world = _world()
    agent = Agent(x=5, y=5, brain=None, is_player=False, player_id=None)
    agent.village_id = 1
    agent.role = "forager"
    agent.task = "gather_food_wild"
    world.agents = [agent]

    world.record_movement_tick(
        agent,
        from_pos=(5, 5),
        to_pos=(5, 5),
        target=(7, 5),
        action_was_move=True,
    )

    diag = world.compute_movement_diagnostics_snapshot()
    assert int(diag["global"]["movement_ticks_total"]) >= 1
    assert int(diag["global"]["no_progress_ticks"]) >= 1


def test_metrics_aggregate_deterministically_by_role_and_task() -> None:
    world = _world()
    farmer = Agent(x=10, y=10, brain=None, is_player=False, player_id=None)
    farmer.village_id = 1
    farmer.role = "farmer"
    farmer.task = "farm_cycle"
    builder = Agent(x=9, y=9, brain=None, is_player=False, player_id=None)
    builder.village_id = 1
    builder.role = "builder"
    builder.task = "build_storage"
    world.agents = [farmer, builder]

    world.record_movement_path_recompute(farmer, (12, 10))
    world.record_movement_tick(
        farmer,
        from_pos=(10, 10),
        to_pos=(11, 10),
        target=(12, 10),
        action_was_move=True,
    )
    world.record_movement_path_recompute(builder, (9, 11))
    world.record_movement_tick(
        builder,
        from_pos=(9, 9),
        to_pos=(9, 10),
        target=(9, 11),
        action_was_move=True,
    )

    diag = world.compute_movement_diagnostics_snapshot()
    assert int(diag["by_role"]["farmer"]["movement_ticks_total"]) == 1
    assert int(diag["by_role"]["builder"]["movement_ticks_total"]) == 1
    assert int(diag["by_task"]["farm_cycle"]["movement_ticks_total"]) == 1
    assert int(diag["by_task"]["build_storage"]["movement_ticks_total"]) == 1
    assert int(diag["by_role"]["farmer"]["path_recompute_count"]) == 1
    assert int(diag["by_role"]["builder"]["path_recompute_count"]) == 1


def test_immediate_backtrack_is_reduced_when_target_remains_valid() -> None:
    world = _world()
    brain = FoodBrain()
    agent = Agent(x=5, y=5, brain=brain, is_player=False, player_id=None)
    agent.movement_prev_tile = (6, 5)
    agent.role = "builder"
    agent.task = "build_storage"
    world.agents = [agent]

    action = brain.move_towards(agent, world, (8, 5))
    assert action != ("move", 1, 0)


def test_target_does_not_change_for_marginally_better_alternative() -> None:
    world = _world()
    brain = FoodBrain()
    agent = Agent(x=5, y=5, brain=brain, is_player=False, player_id=None)
    agent.movement_commit_target = (8, 5)
    agent.movement_commit_until_tick = 20
    world.tick = 10
    world.agents = [agent]

    action = brain.move_towards(agent, world, (5, 7))
    assert action == ("move", 1, 0)


def test_near_target_oscillation_is_reduced() -> None:
    world = _world()
    brain = FoodBrain()
    agent = Agent(x=5, y=5, brain=brain, is_player=False, player_id=None)
    agent.movement_prev_tile = (6, 5)
    world.agents = [agent]

    action = brain.move_towards(agent, world, (6, 5))
    assert action == ("wait",)


def test_true_urgent_changes_override_movement_commitment() -> None:
    world = _world()
    brain = FoodBrain()
    agent = Agent(x=5, y=5, brain=brain, is_player=False, player_id=None)
    agent.hunger = 10
    agent.movement_commit_target = (8, 5)
    agent.movement_commit_until_tick = 20
    world.tick = 10
    world.agents = [agent]

    action = brain.move_towards(agent, world, (5, 7))
    assert action == ("move", 0, 1)


def test_no_pathfinding_deadlock_when_only_backtrack_step_exists() -> None:
    world = _world()
    brain = FoodBrain()
    agent = Agent(x=5, y=5, brain=brain, is_player=False, player_id=None)
    agent.movement_prev_tile = (6, 5)
    blocker_w = Agent(x=4, y=5, brain=None, is_player=False, player_id=None)
    blocker_n = Agent(x=5, y=4, brain=None, is_player=False, player_id=None)
    blocker_s = Agent(x=5, y=6, brain=None, is_player=False, player_id=None)
    world.agents = [agent, blocker_w, blocker_n, blocker_s]

    action = brain.move_towards(agent, world, (8, 5))
    assert action == ("move", 1, 0)


def test_blocked_by_agent_increments_when_destination_occupied() -> None:
    world = _world()
    mover = Agent(x=5, y=5, brain=_MoveRightBrain(), is_player=False, player_id=None)
    blocker = Agent(x=6, y=5, brain=None, is_player=False, player_id=None)
    mover.village_id = 1
    mover.role = "builder"
    mover.task = "build_storage"
    blocker.village_id = 1
    world.agents = [mover, blocker]

    mover.update(world)
    diag = world.compute_movement_diagnostics_snapshot()
    cg = diag["movement_congestion_global"]
    assert int(cg["blocked_by_agent_count"]) >= 1
    assert int(cg["attempted_move_into_occupied_tile"]) >= 1


def test_head_on_collision_increments_when_agents_target_each_other_tiles() -> None:
    world = _world()
    mover = Agent(x=5, y=5, brain=None, is_player=False, player_id=None)
    blocker = Agent(x=6, y=5, brain=None, is_player=False, player_id=None)
    mover.village_id = 1
    mover.role = "hauler"
    mover.task = "village_logistics"
    blocker.task_target = (5, 5)
    world.agents = [mover, blocker]

    world.record_movement_blocked_by_agent(
        mover,
        from_pos=(5, 5),
        to_pos=(6, 5),
        target=(8, 5),
        blocking_agent=blocker,
    )
    diag = world.compute_movement_diagnostics_snapshot()
    assert int(diag["movement_congestion_global"]["head_on_collision_events"]) >= 1


def test_road_congestion_recorded_when_block_occurs_on_road_tile() -> None:
    world = _world()
    world.roads.add((6, 5))
    mover = Agent(x=5, y=5, brain=None, is_player=False, player_id=None)
    blocker = Agent(x=6, y=5, brain=None, is_player=False, player_id=None)
    mover.village_id = 1
    mover.role = "builder"
    mover.task = "build_storage"
    world.agents = [mover, blocker]

    world.record_movement_blocked_by_agent(
        mover,
        from_pos=(5, 5),
        to_pos=(6, 5),
        target=(8, 5),
        blocking_agent=blocker,
    )
    world.record_movement_congestion_snapshot()
    diag = world.compute_movement_diagnostics_snapshot()
    cg = diag["movement_congestion_global"]
    assert int(cg["road_congestion_events"]) >= 1
    assert int(cg["road_tile_agent_samples"]) >= 1


def test_corridor_congestion_increments_when_agent_surrounded() -> None:
    world = _world()
    mover = Agent(x=5, y=5, brain=None, is_player=False, player_id=None)
    east = Agent(x=6, y=5, brain=None, is_player=False, player_id=None)
    west = Agent(x=4, y=5, brain=None, is_player=False, player_id=None)
    north = Agent(x=5, y=4, brain=None, is_player=False, player_id=None)
    south = Agent(x=5, y=6, brain=None, is_player=False, player_id=None)
    mover.village_id = 1
    mover.role = "forager"
    mover.task = "gather_food_wild"
    world.agents = [mover, east, west, north, south]

    world.record_movement_blocked_by_agent(
        mover,
        from_pos=(5, 5),
        to_pos=(6, 5),
        target=(8, 5),
        blocking_agent=east,
    )
    diag = world.compute_movement_diagnostics_snapshot()
    assert int(diag["movement_congestion_global"]["corridor_congestion_events"]) >= 1


def test_tile_occupancy_and_hotspot_metrics_are_exposed() -> None:
    world = _world()
    a1 = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    a2 = Agent(x=8, y=8, brain=None, is_player=False, player_id=None)
    world.agents = [a1, a2]

    world.record_movement_congestion_snapshot()
    diag = world.compute_movement_diagnostics_snapshot()
    cg = diag["movement_congestion_global"]
    assert int(cg["tile_occupancy_samples"]) >= 1
    assert int(cg["tile_occupancy_peak"]) >= 2
    assert int(cg["multi_agent_tile_events"]) >= 1
    assert isinstance(diag.get("top_congested_tiles", []), list)
    assert len(diag.get("top_congested_tiles", [])) >= 1
