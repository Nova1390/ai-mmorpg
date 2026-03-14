from __future__ import annotations

import random
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from world import World


Coord = Tuple[int, int]


VILLAGE_COLORS = [
    "#8b4513",
    "#a0522d",
    "#b5651d",
    "#6b3e26",
    "#7a4b2f",
    "#915c3a",
]

TEMPERAMENTS = ("cautious", "balanced", "ambitious")
FOCUSES = ("food", "housing", "logistics", "expansion")
STYLES = ("conservative", "adaptive", "opportunistic")
FORMAL_VILLAGE_MIN_POPULATION = 4
FORMAL_VILLAGE_MIN_HOUSES = 3
FORMAL_VILLAGE_MIN_STABILITY_TICKS = 90
GHOST_VILLAGE_DOWNGRADE_GRACE_TICKS = 80
GHOST_VILLAGE_ABANDONED_TICKS = 180


def get_village_by_id(world: "World", village_id: Optional[int]) -> Optional[Dict]:
    if village_id is None:
        return None

    for v in world.villages:
        if v["id"] == village_id:
            return v

    return None


def count_leaders(world: "World") -> int:
    return sum(
        1 for a in world.agents
        if a.alive and getattr(a, "role", "npc") == "leader"
    )


def get_civilization_stats(world: "World") -> Dict:
    if not world.villages:
        return {
            "largest_village_id": None,
            "largest_village_houses": 0,
            "strongest_village_id": None,
            "strongest_village_power": 0,
            "expanding_village_id": None,
            "warring_villages": 0,
            "migrating_villages": 0,
        }

    largest = max(world.villages, key=lambda v: v.get("houses", 0))
    strongest = max(world.villages, key=lambda v: v.get("power", 0))
    expanding = next(
        (v for v in world.villages if "expand" in (v.get("strategy", "").lower())),
        None,
    )

    return {
        "largest_village_id": largest["id"],
        "largest_village_houses": largest.get("houses", 0),
        "strongest_village_id": strongest["id"],
        "strongest_village_power": strongest.get("power", 0),
        "expanding_village_id": expanding["id"] if expanding else None,
        "warring_villages": sum(1 for v in world.villages if v.get("relation") == "war"),
        "migrating_villages": sum(1 for v in world.villages if v.get("relation") == "migrate"),
    }


def _dist(a: Coord, b: Coord) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _match_previous_village(center: Coord, old_villages: List[Dict]) -> Optional[Dict]:
    best = None
    best_d = 999999

    for old in old_villages:
        oc = old.get("center")
        if not oc:
            continue

        old_center = (oc["x"], oc["y"])
        d = _dist(center, old_center)

        if d < best_d:
            best_d = d
            best = old

    if best is not None and best_d <= 12:
        return best

    return None


def _village_uid(world: "World", previous: Optional[Dict]) -> str:
    if previous and previous.get("village_uid"):
        return str(previous["village_uid"])
    return world.new_village_uid()


def _default_strategy_for_new_village(houses: int, population: int) -> str:
    if houses >= 5:
        return "expand village"
    if population <= 2:
        return "gather food"
    return "gather wood"


def _pick_color_for_village(previous: Optional[Dict], village_id: int) -> str:
    if previous and previous.get("color"):
        return previous["color"]
    return VILLAGE_COLORS[(village_id - 1) % len(VILLAGE_COLORS)]


def _structure_neighbors(world: "World", pos: Coord, radius: int = 4) -> List[Coord]:
    x, y = pos
    result: List[Coord] = []

    for ox in range(-radius, radius + 1):
        for oy in range(-radius, radius + 1):
            if ox == 0 and oy == 0:
                continue

            nx = x + ox
            ny = y + oy

            if (nx, ny) in world.structures:
                result.append((nx, ny))

    return result


def detect_villages(world: "World") -> None:
    old_villages = list(world.villages)
    unmatched_old = list(old_villages)

    visited: Set[Coord] = set()
    villages: List[Dict] = []
    village_id = 1
    settlement_stats = getattr(world, "settlement_bottleneck_stats", None)
    if not isinstance(settlement_stats, dict):
        settlement_stats = {
            "village_creation_attempts": 0,
            "village_creation_blocked_count": 0,
            "village_creation_blocked_reasons": {},
            "independent_cluster_count": 0,
            "independent_cluster_support_score_total": 0,
            "independent_cluster_support_score_samples": 0,
            "camp_to_village_transition_attempts": 0,
            "camp_to_village_transition_failures": 0,
            "camp_to_village_transition_failure_reasons": {},
            "local_viable_camp_retained_count": 0,
            "distant_cluster_pull_suppressed_count": 0,
            "distant_cluster_pull_suppressed_reasons": {},
            "camp_absorption_events": 0,
            "camp_absorption_reasons": {},
            "mature_nucleus_detected_count": 0,
            "mature_nucleus_failed_transition_count": 0,
            "mature_nucleus_successful_transition_count": 0,
            "cluster_ecological_productivity_score_total": 0.0,
            "cluster_ecological_productivity_score_samples": 0,
            "cluster_inertia_events": 0,
            "dominant_cluster_saturation_penalty_applied": 0,
            "camp_absorption_delay_events": 0,
            "secondary_cluster_persistence_ticks": 0,
            "exploration_shift_due_to_low_density": 0,
        }
        world.settlement_bottleneck_stats = settlement_stats
    settlement_stats["independent_cluster_count"] = 0

    for start in world.structures:
        if start in visited:
            continue

        stack = [start]
        cluster: List[Coord] = []

        while stack:
            cur = stack.pop()
            if cur in visited:
                continue

            visited.add(cur)
            cluster.append(cur)

            for nei in _structure_neighbors(world, cur, radius=4):
                if nei not in visited:
                    stack.append(nei)

        settlement_stats["independent_cluster_count"] = int(settlement_stats.get("independent_cluster_count", 0)) + 1
        settlement_stats["village_creation_attempts"] = int(settlement_stats.get("village_creation_attempts", 0)) + 1
        cx = round(sum(x for x, _ in cluster) / len(cluster))
        cy = round(sum(y for _, y in cluster) / len(cluster))
        pop = 0
        for a in world.agents:
            if not a.alive:
                continue
            if abs(a.x - cx) <= 6 and abs(a.y - cy) <= 6:
                pop += 1
        camps = getattr(world, "camps", {})
        nearby_camp = None
        nearby_camp_dist = 10**9
        if isinstance(camps, dict):
            for camp in camps.values():
                if not isinstance(camp, dict) or not bool(camp.get("active", False)):
                    continue
                dist = abs(int(camp.get("x", 0)) - int(cx)) + abs(int(camp.get("y", 0)) - int(cy))
                if dist <= 8 and dist < nearby_camp_dist:
                    nearby_camp = camp
                    nearby_camp_dist = dist
        active_camp_near = nearby_camp is not None
        camp_support_score = int(nearby_camp.get("support_score", 0)) if isinstance(nearby_camp, dict) else 0
        settlement_stats["independent_cluster_support_score_total"] = int(
            settlement_stats.get("independent_cluster_support_score_total", 0)
        ) + max(0, camp_support_score)
        settlement_stats["independent_cluster_support_score_samples"] = int(
            settlement_stats.get("independent_cluster_support_score_samples", 0)
        ) + 1
        mature_nucleus = bool(
            active_camp_near
            and int(pop) >= 3
            and int(camp_support_score) >= 4
            and len(cluster) >= max(1, int(world.MIN_HOUSES_FOR_VILLAGE) - 1)
        )
        if mature_nucleus:
            settlement_stats["mature_nucleus_detected_count"] = int(
                settlement_stats.get("mature_nucleus_detected_count", 0)
            ) + 1
        required_houses = int(world.MIN_HOUSES_FOR_VILLAGE)
        if mature_nucleus:
            # A mature independent nucleus can transition with one fewer house.
            required_houses = max(2, int(world.MIN_HOUSES_FOR_VILLAGE) - 1)

        if len(cluster) < required_houses:
            settlement_stats["village_creation_blocked_count"] = int(settlement_stats.get("village_creation_blocked_count", 0)) + 1
            blocked = settlement_stats.setdefault("village_creation_blocked_reasons", {})
            blocked["insufficient_houses"] = int(blocked.get("insufficient_houses", 0)) + 1
            if active_camp_near:
                settlement_stats["camp_to_village_transition_attempts"] = int(settlement_stats.get("camp_to_village_transition_attempts", 0)) + 1
                if hasattr(world, "record_secondary_nucleus_event"):
                    world.record_secondary_nucleus_event("secondary_nucleus_village_attempts")
                settlement_stats["camp_to_village_transition_failures"] = int(settlement_stats.get("camp_to_village_transition_failures", 0)) + 1
                fail_reasons = settlement_stats.setdefault("camp_to_village_transition_failure_reasons", {})
                fail_reason = "insufficient_houses_mature_nucleus" if mature_nucleus else "insufficient_houses"
                fail_reasons[fail_reason] = int(fail_reasons.get(fail_reason, 0)) + 1
                if mature_nucleus:
                    settlement_stats["mature_nucleus_failed_transition_count"] = int(
                        settlement_stats.get("mature_nucleus_failed_transition_count", 0)
                    ) + 1
            continue

        if active_camp_near:
            settlement_stats["camp_to_village_transition_attempts"] = int(settlement_stats.get("camp_to_village_transition_attempts", 0)) + 1
            if hasattr(world, "record_secondary_nucleus_event"):
                world.record_secondary_nucleus_event("secondary_nucleus_village_attempts")
            if mature_nucleus and len(cluster) < int(world.MIN_HOUSES_FOR_VILLAGE):
                settlement_stats["mature_nucleus_successful_transition_count"] = int(
                    settlement_stats.get("mature_nucleus_successful_transition_count", 0)
                ) + 1
                if hasattr(world, "record_settlement_bottleneck"):
                    world.record_settlement_bottleneck("secondary_nucleus_materialization_success")
                if hasattr(world, "record_secondary_nucleus_event"):
                    world.record_secondary_nucleus_event("secondary_nucleus_village_successes")

        center = (cx, cy)
        previous = _match_previous_village(center, unmatched_old)
        if previous is not None:
            unmatched_old.remove(previous)
        default_strategy = _default_strategy_for_new_village(len(cluster), pop)
        prev_stability = int(previous.get("stability_ticks", 0)) if isinstance(previous, dict) else 0
        stability_ticks = max(1, prev_stability + 1)
        prev_formalized = bool(previous.get("formalized", False)) if isinstance(previous, dict) else False
        prev_viability_debt = int(previous.get("viability_debt_ticks", 0)) if isinstance(previous, dict) else 0
        formalization_ready = bool(
            len(cluster) >= int(max(FORMAL_VILLAGE_MIN_HOUSES, world.MIN_HOUSES_FOR_VILLAGE))
            and int(pop) >= int(FORMAL_VILLAGE_MIN_POPULATION)
            and int(stability_ticks) >= int(FORMAL_VILLAGE_MIN_STABILITY_TICKS)
            and (active_camp_near or mature_nucleus)
        )
        viability_debt_ticks = 0
        if not formalization_ready and (prev_formalized or prev_viability_debt > 0):
            viability_debt_ticks = int(prev_viability_debt) + 1
        formalized = bool(formalization_ready)
        if prev_formalized and not formalized and int(viability_debt_ticks) < int(GHOST_VILLAGE_DOWNGRADE_GRACE_TICKS):
            # Grace period prevents noisy flicker while still allowing eventual downgrade.
            formalized = True
        if formalization_ready:
            viability_debt_ticks = 0
        settlement_stage = "formal_village" if formalized else "proto_settlement"
        prev_abandoned = bool(previous.get("abandoned", False)) if isinstance(previous, dict) else False
        abandoned = bool(
            not formalized
            and int(viability_debt_ticks) >= int(GHOST_VILLAGE_ABANDONED_TICKS)
            and int(pop) <= 1
        )
        if abandoned and not prev_abandoned and hasattr(world, "record_settlement_progression_metric"):
            world.record_settlement_progression_metric("settlement_abandoned_count")
            prev_needs = previous.get("needs", {}) if isinstance(previous, dict) else {}
            if isinstance(prev_needs, dict) and bool(prev_needs.get("food_urgent", False) or prev_needs.get("food_low", False)):
                world.record_settlement_progression_metric("proto_settlement_abandoned_due_to_food_pressure_count")
        if prev_formalized and not formalized and int(viability_debt_ticks) == int(GHOST_VILLAGE_DOWNGRADE_GRACE_TICKS):
            blocked = settlement_stats.setdefault("village_creation_blocked_reasons", {})
            blocked["ghost_village_downgraded"] = int(blocked.get("ghost_village_downgraded", 0)) + 1

        villages.append(
            {
                "id": village_id,
                "village_uid": _village_uid(world, previous),
                "center": {"x": cx, "y": cy},
                "houses": len(cluster),
                "population": pop,
                "tiles": [{"x": x, "y": y} for x, y in cluster],
                "leader_id": previous["leader_id"] if previous else None,
                "strategy": previous["strategy"] if previous else default_strategy,
                "color": _pick_color_for_village(previous, village_id),
                "relation": previous["relation"] if previous else "peace",
                "target_village_id": previous["target_village_id"] if previous else None,
                "migration_target_id": previous["migration_target_id"] if previous else None,
                "power": 0,
                "storage": previous["storage"] if previous and "storage" in previous else {
                    "food": 0,
                    "wood": 0,
                    "stone": 0,
                },
                "storage_pos": previous["storage_pos"] if previous and "storage_pos" in previous else {
                    "x": cx,
                    "y": cy,
                },
                "farm_zone_center": previous["farm_zone_center"] if previous and "farm_zone_center" in previous else {
                    "x": cx + 2,
                    "y": cy + 2,
                },
                "priority_history": previous["priority_history"] if previous and "priority_history" in previous else [],
                "leader_profile": previous["leader_profile"] if previous and "leader_profile" in previous else None,
                "tier": int(previous["tier"]) if previous and "tier" in previous else 1,
                "proto_culture": previous["proto_culture"] if previous and "proto_culture" in previous else None,
                "culture_summary": previous["culture_summary"] if previous and "culture_summary" in previous else None,
                "formalized": bool(formalized),
                "settlement_stage": str(settlement_stage),
                "stability_ticks": int(stability_ticks),
                "viability_debt_ticks": int(viability_debt_ticks),
                "abandoned": bool(abandoned),
            }
        )
        if bool(formalized) and not bool(prev_formalized):
            if hasattr(world, "settlement_progression_stats") and isinstance(world.settlement_progression_stats, dict):
                if int(world.settlement_progression_stats.get("first_village_formalization_tick", -1)) < 0:
                    world.settlement_progression_stats["first_village_formalization_tick"] = int(getattr(world, "tick", 0))
        if previous is None:
            world.emit_event(
                "village_created",
                {
                    "village_uid": villages[-1]["village_uid"],
                    "village_id": village_id,
                    "center": {"x": cx, "y": cy},
                    "houses": len(cluster),
                },
            )
        village_id += 1

    if hasattr(world, "record_settlement_progression_metric"):
        for old in unmatched_old:
            if not isinstance(old, dict):
                continue
            if bool(old.get("formalized", False)):
                world.record_settlement_progression_metric("settlement_abandoned_count")

    world.villages = villages
    assign_village_leaders(world)
    update_village_politics(world)


def assign_village_leaders(world: "World") -> None:
    prev_membership = {id(a): getattr(a, "village_id", None) for a in world.agents if a.alive}
    previous_leaders = {
        id(a): a for a in world.agents
        if a.alive and not a.is_player and getattr(a, "role", "npc") == "leader"
    }

    for a in world.agents:
        if not a.alive:
            continue

        if a.is_player:
            world.set_agent_role(a, "player", reason="player_guard")
            continue

        world.set_agent_role(a, "npc", reason="village_recompute")
        a.village_id = None

    for village in world.villages:
        village_tiles = {
            (tile["x"], tile["y"])
            for tile in village.get("tiles", [])
        }
        center = village.get("center", {})
        cx = center.get("x", 0)
        cy = center.get("y", 0)

        nearby_agents = []

        for a in world.agents:
            if not a.alive or a.is_player:
                continue

            is_member = False

            for hx, hy in village_tiles:
                if abs(a.x - hx) <= 4 and abs(a.y - hy) <= 4:
                    is_member = True
                    break

            # include agents working around farm/logistics zones near village center
            if not is_member and abs(a.x - cx) <= 10 and abs(a.y - cy) <= 10:
                is_member = True

            if is_member:
                a.village_id = village["id"]
                nearby_agents.append(a)

        village["population"] = max(village.get("population", 0), len(nearby_agents))

        # stable fallback: populous villages should always keep/get one leader
        if not nearby_agents and village["population"] >= 3:
            cx = village["center"]["x"]
            cy = village["center"]["y"]
            fallback_candidates = [
                a for a in world.agents
                if a.alive
                and not a.is_player
                and abs(a.x - cx) <= 10
                and abs(a.y - cy) <= 10
            ]
            if fallback_candidates:
                chosen = max(
                    fallback_candidates,
                    key=lambda a: (
                        a.hunger,
                        a.inventory.get("food", 0)
                        + a.inventory.get("wood", 0)
                        + a.inventory.get("stone", 0),
                    ),
                )
                chosen.village_id = village["id"]
                nearby_agents.append(chosen)

        previous_leader_id = village.get("leader_id")
        existing_leader = None

        if previous_leader_id is not None:
            candidate = previous_leaders.get(previous_leader_id)
            if candidate is not None and candidate.alive:
                # Keep leader persistent if alive and still close to village sphere.
                if (
                    prev_membership.get(id(candidate)) == village["id"]
                    or (abs(candidate.x - cx) <= 18 and abs(candidate.y - cy) <= 18)
                ):
                    candidate.village_id = village["id"]
                    existing_leader = candidate
                    if candidate not in nearby_agents:
                        nearby_agents.append(candidate)

        active_village = village.get("population", 0) >= 3 and bool(village.get("formalized", False))

        if existing_leader is None and (not active_village or not nearby_agents):
            village["leader_id"] = None
            continue

        if existing_leader is not None:
            leader = existing_leader
        else:
            leader = max(
                nearby_agents,
                key=lambda a: (
                    a.hunger,
                    a.inventory.get("food", 0)
                    + a.inventory.get("wood", 0)
                    + a.inventory.get("stone", 0),
                ),
            )

        world.set_agent_role(leader, "leader", reason="village_leadership")
        leader.village_id = village["id"]
        village["leader_id"] = id(leader)
        _ensure_leader_traits(leader, village)

    # final safety net: each active village gets one leader if possible
    for village in world.villages:
        if village.get("leader_id") is not None:
            continue
        if village.get("population", 0) < 3 or not bool(village.get("formalized", False)):
            continue
        cx = village["center"]["x"]
        cy = village["center"]["y"]
        candidates = [
            a for a in world.agents
            if a.alive
            and not a.is_player
            and getattr(a, "role", "npc") != "leader"
            and (
                prev_membership.get(id(a)) == village["id"]
                or (abs(a.x - cx) <= 18 and abs(a.y - cy) <= 18)
            )
        ]
        if not candidates:
            # last-resort continuity: pull the best alive non-player into leadership
            candidates = [
                a for a in world.agents
                if a.alive and not a.is_player and getattr(a, "role", "npc") != "leader"
            ]
        if not candidates:
            continue
        leader = max(
            candidates,
            key=lambda a: (
                a.hunger,
                a.inventory.get("food", 0)
                + a.inventory.get("wood", 0)
                + a.inventory.get("stone", 0),
            ),
        )
        world.set_agent_role(leader, "leader", reason="village_leadership_fallback")
        leader.village_id = village["id"]
        village["leader_id"] = id(leader)
        _ensure_leader_traits(leader, village)


def _ensure_leader_traits(agent, village: Dict) -> None:
    traits = getattr(agent, "leader_traits", None)
    if not traits:
        traits = {
            "temperament": random.choice(TEMPERAMENTS),
            "focus": random.choice(FOCUSES),
            "style": random.choice(STYLES),
        }
        agent.leader_traits = traits

    village["leader_profile"] = traits


def update_village_politics(world: "World") -> None:
    if not world.villages:
        return

    avg_power = 0.0

    for village in world.villages:
        leader_bonus = 3 if village.get("leader_id") else 0
        storage_bonus = village.get("storage", {}).get("food", 0) * 0.1
        power = village["houses"] * 2 + village["population"] * 1.5 + leader_bonus + storage_bonus
        village["power"] = round(power, 2)
        avg_power += power

    avg_power /= len(world.villages)

    for village in world.villages:
        village["relation"] = "peace"
        village["target_village_id"] = None
        village["migration_target_id"] = None

    for village in world.villages:
        others = [v for v in world.villages if v["id"] != village["id"]]
        if not others:
            continue

        my_center = (village["center"]["x"], village["center"]["y"])
        nearest = min(
            others,
            key=lambda v: _dist(my_center, (v["center"]["x"], v["center"]["y"]))
        )
        strongest = max(others, key=lambda v: v.get("power", 0))

        strategy = (village.get("strategy") or "").lower()

        if village["population"] <= 2 and village["houses"] <= 3:
            village["relation"] = "migrate"
            village["migration_target_id"] = strongest["id"]
            continue

        if (
            ("expand" in strategy or "build" in strategy)
            and village.get("leader_id")
            and village["power"] >= avg_power
            and village["houses"] >= 4
        ):
            village["relation"] = "war"
            weaker_targets = [v for v in others if v.get("power", 0) <= village["power"]]
            target = min(
                weaker_targets if weaker_targets else others,
                key=lambda v: _dist(my_center, (v["center"]["x"], v["center"]["y"]))
            )
            village["target_village_id"] = target["id"]
            continue

        if "food" in strategy:
            village["relation"] = "peace"
            continue

        if "wood" in strategy or "stone" in strategy:
            village["relation"] = "trade"
            village["target_village_id"] = nearest["id"]
            continue
