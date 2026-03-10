from __future__ import annotations

from agent import Agent
from systems.global_balance_runner import (
    GlobalBalanceThresholds,
    compute_implausibility_flags,
    compute_village_support_map,
)
from world import World


def test_compute_village_support_map_counts_affiliated_agents_by_uid() -> None:
    world = World(width=20, height=20, num_agents=0, seed=42, llm_enabled=False)
    world.agents = []

    a1 = Agent(x=5, y=5, brain=None, is_player=False, player_id=None)
    a1.village_affiliation_status = "attached"
    a1.primary_village_uid = "v-000001"

    a2 = Agent(x=6, y=5, brain=None, is_player=False, player_id=None)
    a2.village_affiliation_status = "resident"
    a2.home_village_uid = "v-000001"

    a3 = Agent(x=7, y=5, brain=None, is_player=False, player_id=None)
    a3.village_affiliation_status = "transient"
    a3.primary_village_uid = "v-000002"

    world.agents = [a1, a2, a3]
    support = compute_village_support_map(world)

    assert int(support.get("v-000001", 0)) == 2
    assert int(support.get("v-000002", 0)) == 1


def test_implausibility_flags_detect_singleton_village_and_leader() -> None:
    thresholds = GlobalBalanceThresholds(
        min_legit_village_population=2,
        min_legit_leader_village_population=3,
        early_extinction_threshold_tick=200,
        early_mass_death_threshold_ratio=0.5,
    )
    metrics = {
        "survival": {
            "extinction": True,
            "extinction_tick": 150,
            "early_mass_death": True,
        },
        "settlement_legitimacy": {
            "singleton_village_count": 1,
            "villages_under_legit_threshold_count": 2,
        },
        "leadership_legitimacy": {
            "leaders_in_singleton_villages_count": 1,
            "leaders_under_legit_threshold_count": 1,
        },
    }

    flags = compute_implausibility_flags(metrics=metrics, thresholds=thresholds)
    assert bool(flags["singleton_village_created"]) is True
    assert bool(flags["singleton_leader_created"]) is True
    assert bool(flags["village_before_min_population_support"]) is True
    assert bool(flags["leadership_before_min_social_support"]) is True
    assert bool(flags["early_mass_death"]) is True
    assert bool(flags["extinction_before_tick_threshold"]) is True


def test_implausibility_flags_remain_false_for_legit_non_extinction_case() -> None:
    thresholds = GlobalBalanceThresholds(
        min_legit_village_population=3,
        min_legit_leader_village_population=3,
        early_extinction_threshold_tick=200,
        early_mass_death_threshold_ratio=0.5,
    )
    metrics = {
        "survival": {
            "extinction": False,
            "extinction_tick": None,
            "early_mass_death": False,
        },
        "settlement_legitimacy": {
            "singleton_village_count": 0,
            "villages_under_legit_threshold_count": 0,
        },
        "leadership_legitimacy": {
            "leaders_in_singleton_villages_count": 0,
            "leaders_under_legit_threshold_count": 0,
        },
    }

    flags = compute_implausibility_flags(metrics=metrics, thresholds=thresholds)
    assert all(bool(v) is False for v in flags.values())
