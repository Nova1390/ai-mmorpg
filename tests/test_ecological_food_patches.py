from __future__ import annotations

from world import (
    FOOD_PATCH_MAX_COUNT,
    FOOD_PATCH_MIN_COUNT,
    World,
)


def _inside_patch(world: World, x: int, y: int) -> bool:
    return bool(world._is_in_food_patch(x, y))


def test_food_patches_generated_in_bounds_and_respect_count() -> None:
    world = World(width=72, height=72, num_agents=0, seed=4242, llm_enabled=False)
    patches = list(getattr(world, "food_rich_patches", []))

    assert FOOD_PATCH_MIN_COUNT <= len(patches) <= FOOD_PATCH_MAX_COUNT
    for patch in patches:
        x = int(patch.get("center_x", -1))
        y = int(patch.get("center_y", -1))
        r = int(patch.get("radius", 0))
        assert 0 <= x < world.width
        assert 0 <= y < world.height
        assert r > 0


def test_initial_food_density_is_higher_inside_patches() -> None:
    world = World(width=72, height=72, num_agents=0, seed=5151, llm_enabled=False)

    inside_food = 0
    outside_food = 0
    inside_tiles = 0
    outside_tiles = 0

    for y in range(world.height):
        for x in range(world.width):
            if str(world.tiles[y][x]) == "W":
                continue
            if _inside_patch(world, x, y):
                inside_tiles += 1
                if (x, y) in world.food:
                    inside_food += 1
            else:
                outside_tiles += 1
                if (x, y) in world.food:
                    outside_food += 1

    inside_density = float(inside_food) / float(max(1, inside_tiles))
    outside_density = float(outside_food) / float(max(1, outside_tiles))
    assert inside_density > outside_density


def test_patch_regen_multiplier_spawns_food_in_patches() -> None:
    world = World(width=24, height=24, num_agents=0, seed=999, llm_enabled=False)
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    world.food = set()
    world.food_patch_food_spawned = 0
    world.food_rich_patches = [
        {
            "center_x": 12,
            "center_y": 12,
            "radius": 6,
            "regen_multiplier": 1.8,
            "density_multiplier": 1.5,
        }
    ]

    world.respawn_resources()
    assert int(world.food_patch_food_spawned) > 0


def test_patch_generation_is_deterministic_for_same_seed() -> None:
    a = World(width=72, height=72, num_agents=0, seed=6262, llm_enabled=False)
    b = World(width=72, height=72, num_agents=0, seed=6262, llm_enabled=False)

    assert a.food_rich_patches == b.food_rich_patches
    assert a.food == b.food
