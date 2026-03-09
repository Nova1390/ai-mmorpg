from __future__ import annotations

from agent import Agent, ensure_agent_self_model, evaluate_local_survival_pressure
from brain import FoodBrain, LLMBrain
from world import World


class _NoopPlanner:
    async def propose_goal_async(self, prompt: str) -> str:
        return (
            '{"suggested_intention_type":"gather_food",'
            '"suggested_target_kind":"resource",'
            '"suggested_resource_type":"food",'
            '"reasoning_tags":["survival"]}'
        )


def _flat_world() -> World:
    world = World(width=40, height=40, num_agents=0, seed=42, llm_enabled=False)
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


def _agent(world: World, *, role: str = "npc", hunger: float = 70.0, llm: bool = True) -> Agent:
    brain = (
        LLMBrain(planner=_NoopPlanner(), fallback=FoodBrain(), think_every_ticks=1)
        if llm
        else FoodBrain()
    )
    a = Agent(x=10, y=10, brain=brain, is_player=False, player_id=None)
    a.role = role
    a.hunger = float(hunger)
    a.task = "idle"
    world.add_agent(a)
    return a


def _set_village(world: World, *, food: int, pop: int = 10, needs: dict | None = None) -> None:
    world.villages = [
        {
            "id": 1,
            "village_uid": "v-000001",
            "center": {"x": 10, "y": 10},
            "houses": 4,
            "population": int(pop),
            "storage": {"food": int(food), "wood": 20, "stone": 20},
            "needs": dict(needs or {}),
            "market_state": {
                "food": {"pressure": 0.8 if food <= 1 else 0.1, "local_price_index": 1.6 if food <= 1 else 0.9},
                "wood": {"pressure": 0.2, "local_price_index": 1.0},
                "stone": {"pressure": 0.2, "local_price_index": 1.0},
            },
        }
    ]


def test_high_hunger_and_food_scarcity_raise_survival_pressure() -> None:
    world = _flat_world()
    _set_village(world, food=0, pop=12, needs={"food_urgent": True, "food_buffer_critical": True})
    a = _agent(world, role="builder", hunger=25)
    a.village_id = 1
    a.subjective_state = {
        "local_signals": {
            "needs": {"food_urgent": True, "food_buffer_critical": True},
            "market_state": world.villages[0]["market_state"],
        },
        "nearby_resources": {"food": []},
    }

    pressure = evaluate_local_survival_pressure(world, a)
    assert pressure["survival_pressure"] >= 0.6
    assert pressure["food_crisis"] is True


def test_reflection_hint_build_structure_is_suppressed_during_food_crisis() -> None:
    world = _flat_world()
    _set_village(world, food=0, pop=10, needs={"food_urgent": True})
    a = _agent(world, role="builder", hunger=20)
    a.village_id = 1
    a.subjective_state = {
        "local_signals": {
            "needs": {"food_urgent": True, "food_buffer_critical": True},
            "market_state": world.villages[0]["market_state"],
            "survival": {"survival_pressure": 0.8, "food_crisis": True},
        },
        "attention": {
            "top_resource_targets": [{"resource": "food", "x": 11, "y": 10, "salience": 2.0}],
            "top_building_targets": [{"type": "storage", "x": 10, "y": 10, "salience": 1.5}],
            "top_social_targets": [],
        },
    }
    a.reflection_hint = {
        "suggested_intention_type": "build_structure",
        "suggested_target_kind": "building",
        "suggested_resource_type": "wood",
        "reasoning_tags": ["work"],
        "generated_tick": world.tick,
        "reason": "conflicting_local_needs",
    }

    a.brain._apply_reflection_guidance(a, world)
    current = getattr(a, "current_intention", {}) or {}
    assert str(current.get("type", "")) in {"gather_food", "deliver_resource"}
    assert int(world.reflection_stats.get("survival_reflection_suppressed_count", 0)) >= 1


def test_exploration_is_reduced_under_food_crisis() -> None:
    world = _flat_world()
    _set_village(world, food=0, pop=10, needs={"food_urgent": True})
    a = _agent(world, role="npc", hunger=40, llm=False)
    a.village_id = 1
    ensure_agent_self_model(a)["exploration_weight"] = 0.95
    a.subjective_state = {
        "local_culture": {"exploration_norm": 0.9, "work_norm": 0.4, "cooperation_norm": 0.4},
        "local_signals": {
            "needs": {"food_urgent": True},
            "market_state": world.villages[0]["market_state"],
            "survival": {"survival_pressure": 0.8, "food_crisis": True},
        },
        "attention": {
            "top_resource_targets": [{"resource": "food", "x": 9, "y": 10, "salience": 3.0}],
            "top_building_targets": [],
            "top_social_targets": [],
        },
    }

    intention = a.brain.select_agent_intention(world, a)
    assert isinstance(intention, dict)
    assert str(intention.get("type", "")) != "explore"


def test_survival_tuning_is_deterministic_for_same_setup() -> None:
    w1 = _flat_world()
    w2 = _flat_world()
    _set_village(w1, food=0, pop=10, needs={"food_urgent": True})
    _set_village(w2, food=0, pop=10, needs={"food_urgent": True})
    a1 = _agent(w1, role="builder", hunger=35, llm=False)
    a2 = _agent(w2, role="builder", hunger=35, llm=False)
    a1.village_id = 1
    a2.village_id = 1
    subjective = {
        "local_culture": {"exploration_norm": 0.4, "work_norm": 0.6, "cooperation_norm": 0.5},
        "local_signals": {
            "needs": {"food_urgent": True},
            "market_state": w1.villages[0]["market_state"],
            "survival": {"survival_pressure": 0.75, "food_crisis": True},
        },
        "attention": {
            "top_resource_targets": [{"resource": "food", "x": 9, "y": 10, "salience": 2.8}],
            "top_building_targets": [{"type": "storage", "x": 10, "y": 10, "salience": 1.3}],
            "top_social_targets": [],
        },
    }
    a1.subjective_state = dict(subjective)
    a2.subjective_state = dict(subjective)
    i1 = a1.brain.select_agent_intention(w1, a1)
    i2 = a2.brain.select_agent_intention(w2, a2)
    assert i1 == i2


def test_healthy_village_still_allows_growth_or_work_intentions() -> None:
    world = _flat_world()
    _set_village(world, food=120, pop=10, needs={"need_housing": True})
    a = _agent(world, role="builder", hunger=80, llm=False)
    a.village_id = 1
    a.subjective_state = {
        "local_culture": {"exploration_norm": 0.4, "work_norm": 0.7, "cooperation_norm": 0.5},
        "local_signals": {
            "needs": {"need_housing": True},
            "market_state": world.villages[0]["market_state"],
            "survival": {"survival_pressure": 0.1, "food_crisis": False},
        },
        "attention": {
            "top_resource_targets": [{"resource": "wood", "x": 11, "y": 10, "salience": 1.8}],
            "top_building_targets": [{"type": "house", "x": 10, "y": 10, "salience": 2.2}],
            "top_social_targets": [],
        },
    }

    intention = a.brain.select_agent_intention(world, a)
    assert isinstance(intention, dict)
    assert str(intention.get("type", "")) in {"build_structure", "gather_resource", "deliver_resource", "explore"}
