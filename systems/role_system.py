from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from world import World


CORE_ROLES = ("farmer", "builder", "forager", "hauler")
SPECIALIST_ROLES = ("miner", "woodcutter")
SPECIALIST_REBALANCE_INTERVAL_TICKS = 12
WORKFORCE_REALLOCATION_INTERVAL_TICKS = 10
ROLE_MIN_HOLD_TICKS = 24
ROLE_CONTINUITY_PRODUCTIVE_WINDOW_TICKS = 48
LIVE_CONSTRUCTION_SIGNAL_WINDOW_TICKS = 120
RESERVED_CIVIC_SUPPORT_DURATION_TICKS = 36
RESERVED_CIVIC_SUPPORT_MIN_POPULATION = 1
SUPPORT_ASSIGNMENT_ROLES = ("builder", "hauler")
SUPPORT_ASSIGNMENT_FILTER_REASONS = (
    "role_hold_block",
    "food_base_reserved",
    "food_base_relaxed_for_support_role",
    "specialist_preserved",
    "already_selected_for_other_role",
    "reallocation_not_due",
    "insufficient_population_for_floor",
    "cached_target_override_missed",
)
SUPPORT_RELAXATION_SHORT_CIRCUIT_REASONS = (
    "no_live_demand_context",
    "support_signal_not_recent",
    "true_survival_crisis",
    "population_not_safe",
    "food_base_block_before_relax",
    "relax_budget_not_granted",
    "relax_budget_granted_but_not_used",
    "role_hold_block_before_override",
    "hold_override_not_granted",
    "hold_override_granted_but_not_used",
    "filtered_by_other_role_selection",
    "filtered_by_specialist_preservation",
    "filtered_after_relaxation_other_guard",
    "candidate_became_eligible",
)


def _empty_support_role_assignment_role_diag() -> dict[str, object]:
    return {
        "floor_requested": False,
        "floor_required": 0,
        "target_requested": 0,
        "candidates_total": 0,
        "candidates_eligible": 0,
        "candidates_filtered_out": 0,
        "selected_count": 0,
        "selected_agent_ids": [],
        "floor_satisfied": False,
        "previous_assigned_count": 0,
        "final_assigned_count_after_pass": 0,
        "filter_reasons": {},
    }


def _new_support_role_assignment_diag() -> dict[str, object]:
    return {
        "live_demand": False,
        "under_construction_sites": 0,
        "outstanding_materials": 0,
        "recent_heartbeat_sites": 0,
        "recent_builder_wait_sites": 0,
        "reallocation_due": False,
        "roles": {
            "builder": _empty_support_role_assignment_role_diag(),
            "hauler": _empty_support_role_assignment_role_diag(),
        },
    }


def _empty_support_role_relaxation_role_diag() -> dict[str, object]:
    return {
        "live_demand_context_seen": 0,
        "support_signal_recent_seen": 0,
        "true_survival_crisis_seen": 0,
        "population_safe_for_relaxation": 0,
        "food_base_relaxation_budget_granted": 0,
        "food_base_relaxation_budget_consumed": 0,
        "hold_override_budget_granted": 0,
        "hold_override_budget_consumed": 0,
        "eligible_count": 0,
        "short_circuit_reasons": {},
    }


def _new_support_role_relaxation_diag() -> dict[str, object]:
    return {
        "roles": {
            "builder": _empty_support_role_relaxation_role_diag(),
            "hauler": _empty_support_role_relaxation_role_diag(),
        }
    }


def _default_reserved_civic_support_state() -> dict[str, object]:
    return {
        "reserved_civic_support_active": False,
        "reserved_civic_support_agent_id": "",
        "reserved_civic_support_role": "",
        "reserved_civic_support_until_tick": -1,
        "reserved_civic_support_reason": "",
    }


def _default_reserved_civic_support_metrics() -> dict[str, object]:
    return {
        "reserved_civic_support_activations": 0,
        "reserved_civic_support_active_count": 0,
        "reserved_civic_support_role_counts": {"builder": 0, "hauler": 0},
        "reserved_civic_support_expired_count": 0,
        "reserved_civic_support_released_reason_counts": {},
        "reserved_civic_support_supported_outcome_counts": {
            "construction_delivery": 0,
            "construction_progress": 0,
        },
    }


def _default_reserved_civic_support_gate_role_diag() -> dict[str, object]:
    return {
        "gate_evaluations": 0,
        "live_construction_demand_seen": 0,
        "support_signal_recent_seen": 0,
        "true_survival_crisis_blocked": 0,
        "population_not_safe_blocked": 0,
        "support_floor_gap_seen": 0,
        "support_floor_gap_count": 0,
        "candidate_available_count": 0,
        "slot_activation_granted": 0,
        "slot_activation_block_reasons": {},
    }


def _default_reserved_civic_support_gate_diag() -> dict[str, object]:
    return {
        "roles": {
            "builder": _default_reserved_civic_support_gate_role_diag(),
            "hauler": _default_reserved_civic_support_gate_role_diag(),
        }
    }


def _is_true_survival_crisis(village: dict, workers_sorted: list) -> bool:
    needs = village.get("needs", {}) if isinstance(village.get("needs"), dict) else {}
    storage = village.get("storage", {}) if isinstance(village.get("storage"), dict) else {}
    population = max(0, int(len(workers_sorted)))
    food_stock = int(storage.get("food", 0))
    avg_hunger = (
        sum(float(getattr(a, "hunger", 0.0)) for a in workers_sorted) / max(1, population)
        if population > 0
        else 0.0
    )

    # Require combined severe signals to classify as terminal survival crisis.
    severe_flags = 0
    if bool(needs.get("food_urgent")):
        severe_flags += 1
    if bool(needs.get("food_buffer_critical")):
        severe_flags += 1
    if avg_hunger < 28.0:
        severe_flags += 1
    if food_stock <= 0:
        severe_flags += 1
    if food_stock < max(1, population // 10):
        severe_flags += 1

    if severe_flags >= 3:
        return True
    if bool(needs.get("food_urgent")) and avg_hunger < 34.0:
        return True
    if food_stock <= 0 and avg_hunger < 40.0:
        return True
    return False


def _is_reserved_civic_slot_terminal_crisis(village: dict, workers_sorted: list) -> bool:
    """
    Slot-specific terminal crisis guard:
    stricter than generic survival pressure so fragile-but-viable villages can
    still allocate one temporary civic support worker.
    """
    needs = village.get("needs", {}) if isinstance(village.get("needs"), dict) else {}
    storage = village.get("storage", {}) if isinstance(village.get("storage"), dict) else {}
    population = max(0, int(len(workers_sorted)))
    food_stock = int(storage.get("food", 0))
    avg_hunger = (
        sum(float(getattr(a, "hunger", 0.0)) for a in workers_sorted) / max(1, population)
        if population > 0
        else 0.0
    )

    severe = 0
    if bool(needs.get("food_urgent")) and bool(needs.get("food_buffer_critical")):
        severe += 1
    if food_stock <= 0:
        severe += 1
    if avg_hunger < 24.0:
        severe += 1
    if avg_hunger < 18.0:
        severe += 1

    if severe >= 3:
        return True
    if bool(needs.get("food_urgent")) and bool(needs.get("food_buffer_critical")) and food_stock <= 0 and avg_hunger < 28.0:
        return True
    return False


def _set_role(world: "World", agent, role: str, reason: str) -> None:
    previous = str(getattr(agent, "role", "npc"))
    world.set_agent_role(agent, role, reason=reason)
    if previous != str(role):
        agent.role_hold_until_tick = int(getattr(world, "tick", 0)) + ROLE_MIN_HOLD_TICKS


def _can_change_role(world: "World", agent, target_role: str) -> bool:
    current_role = str(getattr(agent, "role", "npc"))
    if current_role == str(target_role):
        return True
    # Keep a short local commitment while a hauler is in an active delivery chain.
    if current_role == "hauler" and str(target_role) != "hauler":
        delivery_target = str(getattr(agent, "delivery_target_building_id", "") or "")
        delivery_resource = str(getattr(agent, "delivery_resource_type", "") or "")
        reserved_amount = int(getattr(agent, "delivery_reserved_amount", 0) or 0)
        carrying = int(getattr(agent, "inventory", {}).get(delivery_resource, 0)) if delivery_resource in {"wood", "stone", "food"} else 0
        commit_until = int(getattr(agent, "delivery_commit_until_tick", -1))
        hunger = float(getattr(agent, "hunger", 100.0))
        if delivery_target and (reserved_amount > 0 or carrying > 0) and int(getattr(world, "tick", 0)) <= commit_until and hunger > 15.0:
            return False
    hold_until = int(getattr(agent, "role_hold_until_tick", -1))
    return int(getattr(world, "tick", 0)) >= hold_until


def _active_village_buildings(world: "World", village: dict, building_type: str) -> list[dict]:
    vid = village.get("id")
    vuid = village.get("village_uid")
    buildings = []
    for b in getattr(world, "buildings", {}).values():
        if b.get("type") != building_type:
            continue
        if b.get("operational_state") != "active":
            continue
        if vid is not None and b.get("village_id") == vid:
            buildings.append(b)
            continue
        if vuid is not None and b.get("village_uid") == vuid:
            buildings.append(b)
    buildings.sort(key=lambda b: str(b.get("building_id", "")))
    return buildings


def _default_specialist_rebalance_state() -> dict[str, int]:
    return {
        "last_specialist_rebalance_tick": -SPECIALIST_REBALANCE_INTERVAL_TICKS,
        "cached_miner_target": 0,
        "cached_woodcutter_target": 0,
    }


def _default_workforce_rebalance_state() -> dict[str, int | dict[str, int]]:
    return {
        "last_reallocation_tick": -WORKFORCE_REALLOCATION_INTERVAL_TICKS,
        "cached_targets": {"farmer": 0, "builder": 0, "hauler": 0, "forager": 0},
    }


def _get_workforce_rebalance_state(village: dict) -> dict[str, int | dict[str, int]]:
    state = village.get("workforce_rebalance_state")
    if not isinstance(state, dict):
        state = _default_workforce_rebalance_state()
        village["workforce_rebalance_state"] = state
        return state
    defaults = _default_workforce_rebalance_state()
    last_tick = int(state.get("last_reallocation_tick", defaults["last_reallocation_tick"]))
    cached = state.get("cached_targets")
    if not isinstance(cached, dict):
        cached = dict(defaults["cached_targets"])
    state["last_reallocation_tick"] = last_tick
    state["cached_targets"] = {
        "farmer": int(cached.get("farmer", 0)),
        "builder": int(cached.get("builder", 0)),
        "hauler": int(cached.get("hauler", 0)),
        "forager": int(cached.get("forager", 0)),
    }
    return state


def workforce_reallocation_due(world: "World", village: dict) -> bool:
    state = _get_workforce_rebalance_state(village)
    return int(world.tick) - int(state.get("last_reallocation_tick", -WORKFORCE_REALLOCATION_INTERVAL_TICKS)) >= WORKFORCE_REALLOCATION_INTERVAL_TICKS


def _agent_affiliation_rank_for_village(world: "World", village: dict, agent) -> int:
    uid = str(village.get("village_uid", ""))
    status = str(getattr(agent, "village_affiliation_status", "unaffiliated"))
    primary_uid = str(getattr(agent, "primary_village_uid", "") or "")
    home_uid = str(getattr(agent, "home_village_uid", "") or "")
    if status == "resident" and home_uid == uid:
        return 0
    if status == "attached" and primary_uid == uid:
        return 1
    if status == "transient" and primary_uid == uid:
        return 2
    if getattr(agent, "village_id", None) == village.get("id"):
        return 3
    return 4


def _construction_pressure_for_village(world: "World", village: dict) -> tuple[int, int]:
    vid = village.get("id")
    vuid = village.get("village_uid")
    under_construction = 0
    outstanding_materials = 0
    for b in getattr(world, "buildings", {}).values():
        if vid is not None and b.get("village_id") != vid:
            if vuid is None or b.get("village_uid") != vuid:
                continue
        if str(b.get("operational_state", "")) != "under_construction":
            continue
        under_construction += 1
        req = b.get("construction_request", {})
        if isinstance(req, dict):
            for resource in ("wood", "stone", "food"):
                needed = int(req.get(f"{resource}_needed", 0))
                reserved = int(req.get(f"{resource}_reserved", 0))
                outstanding_materials += max(0, needed - reserved)
    return int(under_construction), int(outstanding_materials)


def _live_construction_engagement_signals(world: "World", village: dict) -> dict[str, int | bool]:
    vid = village.get("id")
    vuid = village.get("village_uid")
    tick = int(getattr(world, "tick", 0))
    under_construction_sites = 0
    outstanding_materials = 0
    recent_heartbeat_sites = 0
    recent_builder_wait_sites = 0
    for b in getattr(world, "buildings", {}).values():
        if vid is not None and b.get("village_id") != vid:
            if vuid is None or b.get("village_uid") != vuid:
                continue
        if str(b.get("operational_state", "")) != "under_construction":
            continue
        under_construction_sites += 1
        req = b.get("construction_request", {})
        if isinstance(req, dict):
            for resource in ("wood", "stone", "food"):
                needed = int(req.get(f"{resource}_needed", 0))
                reserved = int(req.get(f"{resource}_reserved", 0))
                outstanding_materials += max(0, needed - reserved)
        hb = b.get("construction_last_demand_tick")
        if hb is not None:
            try:
                if tick - int(hb) <= LIVE_CONSTRUCTION_SIGNAL_WINDOW_TICKS:
                    recent_heartbeat_sites += 1
            except Exception:
                pass
        bw = b.get("builder_waiting_tick")
        if bw is not None:
            try:
                if tick - int(bw) <= LIVE_CONSTRUCTION_SIGNAL_WINDOW_TICKS:
                    recent_builder_wait_sites += 1
            except Exception:
                pass

    live_demand = bool(
        under_construction_sites > 0
        and (
            outstanding_materials > 0
            or recent_heartbeat_sites > 0
            or recent_builder_wait_sites > 0
        )
    )
    return {
        "under_construction_sites": int(under_construction_sites),
        "outstanding_materials": int(outstanding_materials),
        "recent_heartbeat_sites": int(recent_heartbeat_sites),
        "recent_builder_wait_sites": int(recent_builder_wait_sites),
        "live_demand": bool(live_demand),
    }


def compute_target_workforce_mix(world: "World", village: dict) -> dict[str, int | float]:
    village_id = village.get("id")
    all_workers = [
        a for a in world.agents
        if a.alive and not a.is_player and getattr(a, "role", "npc") != "leader" and getattr(a, "village_id", None) == village_id
    ]
    pop = len(all_workers)
    if pop <= 0:
        return {
            "farmer": 0,
            "builder": 0,
            "hauler": 0,
            "forager": 0,
            "food_pressure": 0,
            "construction_pressure": 0,
            "logistics_pressure": 0,
            "material_pressure": 0,
            "resident_population": 0,
            "attached_population": 0,
        }

    uid = str(village.get("village_uid", ""))
    residents = sum(1 for a in all_workers if str(getattr(a, "village_affiliation_status", "")) == "resident" and str(getattr(a, "home_village_uid", "") or "") == uid)
    attached = sum(1 for a in all_workers if str(getattr(a, "village_affiliation_status", "")) == "attached" and str(getattr(a, "primary_village_uid", "") or "") == uid)

    needs = village.get("needs", {}) if isinstance(village.get("needs"), dict) else {}
    storage = village.get("storage", {}) if isinstance(village.get("storage"), dict) else {}
    try:
        import systems.building_system as building_system
        signals = building_system.evaluate_village_unlock_signals(world, village)
    except Exception:
        signals = {}
    active_mines = _active_village_buildings(world, village, "mine")
    active_lumberyards = _active_village_buildings(world, village, "lumberyard")

    under_construction, outstanding_materials = _construction_pressure_for_village(world, village)
    engagement = _live_construction_engagement_signals(world, village)
    food_stock = int(storage.get("food", 0))
    wood_stock = int(storage.get("wood", 0))
    stone_stock = int(storage.get("stone", 0))

    food_pressure = 2 if bool(needs.get("food_urgent")) else (1 if bool(needs.get("food_low") or needs.get("food_buffer_low")) else 0)
    material_pressure = 1 if bool(needs.get("need_materials") or signals.get("wood_demand_high") or signals.get("stone_demand_high")) else 0
    construction_pressure = int(under_construction > 0) + int(outstanding_materials > 0) + int(bool(needs.get("need_housing") or needs.get("need_storage")))
    logistics_pressure = int(outstanding_materials > 0) + int(bool(needs.get("need_storage"))) + int(pop >= 8)
    if bool(engagement.get("live_demand", False)):
        construction_pressure = max(construction_pressure, 2)
        logistics_pressure = max(logistics_pressure, 2)

    farmer_target = max(1, pop // 4)
    forager_target = 0
    if food_pressure >= 2:
        farmer_target = max(farmer_target, pop // 2)
        forager_target = 1
    elif food_pressure == 1:
        farmer_target = max(farmer_target, pop // 3 + 1)
        forager_target = 1 if food_stock <= max(2, pop // 2) else 0
    elif bool(needs.get("food_surplus")):
        farmer_target = max(1, pop // 5)

    builder_target = 0
    if construction_pressure > 0:
        builder_target = 1
    if under_construction >= 2 or outstanding_materials >= 4:
        builder_target = max(builder_target, 2)
    if bool(engagement.get("live_demand", False)):
        builder_target = max(builder_target, 1)

    hauler_target = 1 if pop >= 4 else 0
    if logistics_pressure >= 2 or material_pressure > 0:
        hauler_target = max(hauler_target, 2)
    if construction_pressure >= 2:
        hauler_target = max(hauler_target, 2)
    if bool(engagement.get("live_demand", False)) and pop >= 3:
        hauler_target = max(hauler_target, 1)
    if int(engagement.get("recent_builder_wait_sites", 0)) > 0 and int(engagement.get("outstanding_materials", 0)) > 0 and pop >= 5:
        hauler_target = max(hauler_target, 2)

    # Bound targets to available workforce while maintaining food base first.
    farmer_target = min(pop, max(1, int(farmer_target)))
    forager_target = min(max(0, pop - farmer_target), int(forager_target))
    remaining = max(0, pop - farmer_target - forager_target)
    builder_target = min(remaining, int(builder_target))
    remaining = max(0, remaining - builder_target)
    hauler_target = min(remaining, int(hauler_target))

    # Keep bounded room for specialization when village has active specialist assets
    # and material pressure is non-zero.
    specialist_assets = int(len(active_mines) + len(active_lumberyards))
    if specialist_assets > 0 and material_pressure > 0 and food_pressure < 2:
        reserve_specialists = min(2, specialist_assets, max(0, pop - 2))
        max_core = max(0, pop - reserve_specialists)
        core_total = farmer_target + forager_target + builder_target + hauler_target
        overflow = max(0, core_total - max_core)
        if overflow > 0:
            cut = min(overflow, hauler_target)
            hauler_target -= cut
            overflow -= cut
        if overflow > 0:
            cut = min(overflow, builder_target)
            builder_target -= cut
            overflow -= cut
        if overflow > 0:
            cut = min(overflow, forager_target)
            forager_target -= cut
            overflow -= cut
        if overflow > 0:
            farmer_floor = 1
            cut = min(overflow, max(0, farmer_target - farmer_floor))
            farmer_target -= cut

    return {
        "farmer": int(farmer_target),
        "builder": int(builder_target),
        "hauler": int(hauler_target),
        "forager": int(forager_target),
        "food_pressure": int(food_pressure),
        "construction_pressure": int(construction_pressure),
        "logistics_pressure": int(logistics_pressure),
        "material_pressure": int(material_pressure),
        "resident_population": int(residents),
        "attached_population": int(attached),
        "wood_stock": int(wood_stock),
        "stone_stock": int(stone_stock),
        "live_construction_demand": int(bool(engagement.get("live_demand", False))),
        "live_construction_site_count": int(engagement.get("under_construction_sites", 0)),
        "live_construction_recent_wait_sites": int(engagement.get("recent_builder_wait_sites", 0)),
    }


def _get_specialist_rebalance_state(village: dict) -> dict[str, int]:
    state = village.get("specialist_rebalance_state")
    if not isinstance(state, dict):
        state = _default_specialist_rebalance_state()
        village["specialist_rebalance_state"] = state
        return state
    defaults = _default_specialist_rebalance_state()
    for key, value in defaults.items():
        state[key] = int(state.get(key, value))
    return state


def specialist_rebalance_due(world: "World", village: dict) -> bool:
    state = _get_specialist_rebalance_state(village)
    return int(world.tick) - int(state.get("last_specialist_rebalance_tick", -SPECIALIST_REBALANCE_INTERVAL_TICKS)) >= SPECIALIST_REBALANCE_INTERVAL_TICKS


def compute_specialist_targets_for_village(world: "World", village: dict) -> dict[str, int]:
    """
    Compute deterministic specialist targets from village demand and capacity.
    Returns:
      {
        "miner": int,
        "woodcutter": int,
        "core_workers_reserved": int,
        "max_specialists": int,
      }
    """
    village_id = village.get("id")
    workers = [
        a for a in world.agents
        if a.alive and not a.is_player and getattr(a, "village_id", None) == village_id
    ]
    pop = len(workers)
    if pop <= 0:
        return {
            "miner": 0,
            "woodcutter": 0,
            "core_workers_reserved": 0,
            "max_specialists": 0,
            "miner_demand_score": 0,
            "woodcutter_demand_score": 0,
        }

    needs = village.get("needs", {}) if isinstance(village.get("needs"), dict) else {}
    metrics = village.get("metrics", {}) if isinstance(village.get("metrics"), dict) else {}
    storage = village.get("storage", {}) if isinstance(village.get("storage"), dict) else {}

    active_mines = _active_village_buildings(world, village, "mine")
    active_lumberyards = _active_village_buildings(world, village, "lumberyard")

    wood_stock = int(storage.get("wood", metrics.get("wood_stock", 0)) or 0)
    stone_stock = int(storage.get("stone", metrics.get("stone_stock", 0)) or 0)
    houses = int(village.get("houses", 0))

    # Reuse deterministic unlock signals as first-pass demand layer.
    try:
        import systems.building_system as building_system
        signals = building_system.evaluate_village_unlock_signals(world, village)
    except Exception:
        signals = {}

    wood_demand = bool(signals.get("wood_demand_high")) or bool(needs.get("need_materials"))
    stone_demand = bool(signals.get("stone_demand_high")) or bool(needs.get("need_materials"))
    food_urgent = bool(needs.get("food_urgent"))

    # Preserve minimum core workforce for food/survival roles.
    core_workers_reserved = max(2, pop // 3)
    if food_urgent:
        core_workers_reserved = max(core_workers_reserved, pop // 2)
    max_specialists = max(0, min(pop - core_workers_reserved, pop // 2))

    miner_score = 0
    woodcutter_score = 0
    if stone_demand:
        miner_score += 2
    if wood_demand:
        woodcutter_score += 2
    if stone_stock < max(2, houses):
        miner_score += 1
    if wood_stock < max(4, houses * 2):
        woodcutter_score += 1

    miner_cap = min(len(active_mines), max_specialists)
    woodcutter_cap = min(len(active_lumberyards), max_specialists)
    if food_urgent:
        return {
            "miner": 0,
            "woodcutter": 0,
            "core_workers_reserved": core_workers_reserved,
            "max_specialists": max_specialists,
            "miner_demand_score": miner_score,
            "woodcutter_demand_score": woodcutter_score,
        }

    miner_target = 0
    woodcutter_target = 0
    if miner_cap > 0 and miner_score > 0:
        miner_target = 1
    if woodcutter_cap > 0 and woodcutter_score > 0:
        woodcutter_target = 1

    remaining = max(0, max_specialists - miner_target - woodcutter_target)
    role_rank = sorted(
        [
            ("miner", miner_score, miner_cap),
            ("woodcutter", woodcutter_score, woodcutter_cap),
        ],
        key=lambda r: (-int(r[1]), r[0]),
    )
    for role_name, score, cap in role_rank:
        if remaining <= 0 or score <= 0:
            continue
        current_target = miner_target if role_name == "miner" else woodcutter_target
        if current_target >= cap:
            continue
        extra = min(cap - current_target, remaining)
        if role_name == "miner":
            miner_target += extra
        else:
            woodcutter_target += extra
        remaining -= extra

    return {
        "miner": max(0, int(miner_target)),
        "woodcutter": max(0, int(woodcutter_target)),
        "core_workers_reserved": int(core_workers_reserved),
        "max_specialists": int(max_specialists),
        "miner_demand_score": int(miner_score),
        "woodcutter_demand_score": int(woodcutter_score),
    }


def apply_specialist_allocation_policy(
    world: "World",
    village: dict,
    workers_sorted: list,
    assigned_ids: set[int],
    protected_specialist_ids: set[int] | None = None,
) -> dict[str, int]:
    try:
        import systems.building_system as building_system
    except Exception:  # pragma: no cover - defensive only
        building_system = None
    protected_specialist_ids = protected_specialist_ids or set()
    targets = compute_specialist_targets_for_village(world, village)
    raw_target_miners = int(targets.get("miner", 0))
    raw_target_woodcutters = int(targets.get("woodcutter", 0))
    miner_demand_score = int(targets.get("miner_demand_score", 0))
    woodcutter_demand_score = int(targets.get("woodcutter_demand_score", 0))

    active_mines = sorted(
        _active_village_buildings(world, village, "mine"),
        key=lambda b: (0 if b.get("connected_to_road") else 1, str(b.get("building_id", ""))),
    )
    active_lumberyards = sorted(
        _active_village_buildings(world, village, "lumberyard"),
        key=lambda b: (0 if b.get("connected_to_road") else 1, str(b.get("building_id", ""))),
    )
    current_miners = sum(1 for a in workers_sorted if getattr(a, "role", "") == "miner")
    current_woodcutters = sum(1 for a in workers_sorted if getattr(a, "role", "") == "woodcutter")
    rebalance_due = specialist_rebalance_due(world, village)

    state = _get_specialist_rebalance_state(village)
    if rebalance_due:
        # Hysteresis: demote only on clearly weak demand (score == 0).
        target_miners = raw_target_miners
        target_woodcutters = raw_target_woodcutters
        if raw_target_miners < current_miners and miner_demand_score > 0:
            target_miners = current_miners
        if raw_target_woodcutters < current_woodcutters and woodcutter_demand_score > 0:
            target_woodcutters = current_woodcutters
        state["last_specialist_rebalance_tick"] = int(world.tick)
        state["cached_miner_target"] = int(target_miners)
        state["cached_woodcutter_target"] = int(target_woodcutters)
    else:
        # Between rebalance checkpoints, keep cached targets bounded by current feasibility.
        target_miners = min(int(state.get("cached_miner_target", current_miners)), len(active_mines))
        target_woodcutters = min(int(state.get("cached_woodcutter_target", current_woodcutters)), len(active_lumberyards))

    specialist_candidates = [a for a in workers_sorted if id(a) not in assigned_ids]

    def take_specialists(role: str, n: int, buildings: list[dict]) -> int:
        if n <= 0 or not buildings:
            return 0
        ordered = sorted(
            specialist_candidates,
            key=lambda a: (
                0 if getattr(a, "role", "") == role else 1,  # keep role when possible
                -a.hunger,
                -(a.inventory.get("food", 0) + a.inventory.get("wood", 0) + a.inventory.get("stone", 0)),
                getattr(a, "agent_id", ""),
            ),
        )
        count = 0
        for a in ordered:
            aid = id(a)
            if aid in assigned_ids:
                continue
            _set_role(world, a, role, reason="specialist_target_policy")
            assigned_ids.add(aid)
            linked = buildings[count % len(buildings)]
            a.assigned_building_id = linked.get("building_id")
            count += 1
            if count >= n:
                break
        return count

    assigned_miners = take_specialists("miner", target_miners, active_mines)
    assigned_woodcutters = take_specialists("woodcutter", target_woodcutters, active_lumberyards)
    if building_system is not None:
        if assigned_miners > 0:
            for _ in range(int(assigned_miners)):
                building_system.record_specialization_stage(world, "mine", "staffed_count", village=village)
        elif len(active_mines) > 0:
            building_system.record_specialization_blocker(world, "mine", "no_specialist_assigned", village=village)
        if assigned_woodcutters > 0:
            for _ in range(int(assigned_woodcutters)):
                building_system.record_specialization_stage(world, "lumberyard", "staffed_count", village=village)
        elif len(active_lumberyards) > 0:
            building_system.record_specialization_blocker(world, "lumberyard", "no_specialist_assigned", village=village)

    for a in workers_sorted:
        if id(a) in assigned_ids:
            continue
        if getattr(a, "role", "") in SPECIALIST_ROLES and hasattr(a, "assigned_building_id"):
            # Explicit demotion path: non-target specialists get reassigned by fallback.
            a.assigned_building_id = None
    # Keep protected specialists stable between rebalance ticks.
    if not rebalance_due:
        for a in workers_sorted:
            aid = id(a)
            if aid not in protected_specialist_ids:
                continue
            if aid in assigned_ids:
                continue
            if getattr(a, "role", "") not in SPECIALIST_ROLES:
                continue
            assigned_ids.add(aid)
            if getattr(a, "role", "") == "miner" and active_mines:
                a.assigned_building_id = active_mines[0].get("building_id")
            if getattr(a, "role", "") == "woodcutter" and active_lumberyards:
                a.assigned_building_id = active_lumberyards[0].get("building_id")

    metrics = village.setdefault("metrics", {})
    metrics["miner_target"] = int(target_miners)
    metrics["woodcutter_target"] = int(target_woodcutters)
    pressure = max(0, target_miners - assigned_miners) + max(0, target_woodcutters - assigned_woodcutters)
    metrics["specialist_allocation_pressure"] = int(pressure)
    metrics["last_specialist_rebalance_tick"] = int(state.get("last_specialist_rebalance_tick", -SPECIALIST_REBALANCE_INTERVAL_TICKS))
    metrics["specialist_rebalance_due"] = bool(specialist_rebalance_due(world, village))

    return {
        "miner_target": int(target_miners),
        "woodcutter_target": int(target_woodcutters),
        "assigned_miners": int(assigned_miners),
        "assigned_woodcutters": int(assigned_woodcutters),
        "rebalance_due": bool(rebalance_due),
    }


def assign_village_roles(world: "World") -> None:
    """
    Assegna ruoli stabili agli agenti vivi in base ai bisogni del villaggio.
    Mantiene leader e player.
    """
    for village in world.villages:
        members = [
            a for a in world.agents
            if a.alive and not a.is_player and getattr(a, "village_id", None) == village["id"]
        ]
        workers = [a for a in members if getattr(a, "role", "npc") != "leader"]
        if not workers:
            metrics = village.setdefault("metrics", {})
            gate_diag = metrics.get("reserved_civic_support_gate_diagnostics")
            if not isinstance(gate_diag, dict):
                gate_diag = _default_reserved_civic_support_gate_diag()
                metrics["reserved_civic_support_gate_diagnostics"] = gate_diag
            roles = gate_diag.get("roles")
            if not isinstance(roles, dict):
                roles = {}
                gate_diag["roles"] = roles
            engagement = _live_construction_engagement_signals(world, village)
            support_signal_recent = (
                int(engagement.get("recent_heartbeat_sites", 0)) > 0
                or int(engagement.get("recent_builder_wait_sites", 0)) > 0
            )
            for role_name in ("builder", "hauler"):
                rd = roles.get(role_name)
                if not isinstance(rd, dict):
                    rd = _default_reserved_civic_support_gate_role_diag()
                rd["gate_evaluations"] = int(rd.get("gate_evaluations", 0)) + 1
                if bool(engagement.get("live_demand", False)):
                    rd["live_construction_demand_seen"] = int(rd.get("live_construction_demand_seen", 0)) + 1
                if bool(support_signal_recent):
                    rd["support_signal_recent_seen"] = int(rd.get("support_signal_recent_seen", 0)) + 1
                reasons = rd.get("slot_activation_block_reasons")
                if not isinstance(reasons, dict):
                    reasons = {}
                reasons["no_candidate_available"] = int(reasons.get("no_candidate_available", 0)) + 1
                rd["slot_activation_block_reasons"] = reasons
                roles[role_name] = rd
            gate_diag["roles"] = roles
            metrics["reserved_civic_support_gate_diagnostics"] = gate_diag
            continue

        workers_sorted = sorted(
            workers,
            key=lambda a: (
                _agent_affiliation_rank_for_village(world, village, a),
                -float(getattr(a, "hunger", 0.0)),
                -int(a.inventory.get("food", 0) + a.inventory.get("wood", 0) + a.inventory.get("stone", 0)),
                str(getattr(a, "agent_id", "")),
            ),
        )

        workforce_state = _get_workforce_rebalance_state(village)
        reallocation_due = workforce_reallocation_due(world, village)
        if reallocation_due:
            target_mix = compute_target_workforce_mix(world, village)
            workforce_state["last_reallocation_tick"] = int(world.tick)
            workforce_state["cached_targets"] = {
                "farmer": int(target_mix.get("farmer", 0)),
                "builder": int(target_mix.get("builder", 0)),
                "hauler": int(target_mix.get("hauler", 0)),
                "forager": int(target_mix.get("forager", 0)),
            }
        else:
            cached = workforce_state.get("cached_targets", {})
            target_mix = compute_target_workforce_mix(world, village)
            target_mix["farmer"] = int(cached.get("farmer", target_mix.get("farmer", 0)))
            target_mix["builder"] = int(cached.get("builder", target_mix.get("builder", 0)))
            target_mix["hauler"] = int(cached.get("hauler", target_mix.get("hauler", 0)))
            target_mix["forager"] = int(cached.get("forager", target_mix.get("forager", 0)))

        engagement = _live_construction_engagement_signals(world, village)
        support_diag = _new_support_role_assignment_diag()
        support_relax_diag = _new_support_role_relaxation_diag()
        support_diag["live_demand"] = bool(engagement.get("live_demand", False))
        support_diag["under_construction_sites"] = int(engagement.get("under_construction_sites", 0))
        support_diag["outstanding_materials"] = int(engagement.get("outstanding_materials", 0))
        support_diag["recent_heartbeat_sites"] = int(engagement.get("recent_heartbeat_sites", 0))
        support_diag["recent_builder_wait_sites"] = int(engagement.get("recent_builder_wait_sites", 0))
        support_diag["reallocation_due"] = bool(reallocation_due)
        if not reallocation_due:
            for role_name in SUPPORT_ASSIGNMENT_ROLES:
                rr = support_diag["roles"][role_name]
                fr = rr.get("filter_reasons")
                if isinstance(fr, dict):
                    fr["reallocation_not_due"] = int(fr.get("reallocation_not_due", 0)) + 1

        pre_assignment_mix = {
            "builder": sum(1 for a in workers_sorted if str(getattr(a, "role", "")) == "builder"),
            "hauler": sum(1 for a in workers_sorted if str(getattr(a, "role", "")) == "hauler"),
        }
        for role_name in SUPPORT_ASSIGNMENT_ROLES:
            role_diag = support_diag["roles"][role_name]
            role_diag["previous_assigned_count"] = int(pre_assignment_mix.get(role_name, 0))

        builder_floor_required = 0
        hauler_floor_required = 0
        population = int(len(workers_sorted))
        true_survival_crisis = _is_true_survival_crisis(village, workers_sorted)
        slot_terminal_crisis = _is_reserved_civic_slot_terminal_crisis(village, workers_sorted)
        if bool(engagement.get("live_demand", False)):
            builder_floor_required = 1
            target_mix["builder"] = max(int(target_mix.get("builder", 0)), 1)
            if population < 1:
                fr = support_diag["roles"]["builder"]["filter_reasons"]
                if isinstance(fr, dict):
                    fr["insufficient_population_for_floor"] = int(fr.get("insufficient_population_for_floor", 0)) + 1
            # Allow a minimal hauler floor in small-but-viable villages when
            # materials are outstanding, instead of suppressing until pop>=3.
            if int(engagement.get("outstanding_materials", 0)) > 0 and population >= 2:
                hauler_floor_required = 1
                target_mix["hauler"] = max(int(target_mix.get("hauler", 0)), 1)
            else:
                fr = support_diag["roles"]["hauler"]["filter_reasons"]
                if isinstance(fr, dict):
                    fr["insufficient_population_for_floor"] = int(fr.get("insufficient_population_for_floor", 0)) + 1
            if int(engagement.get("recent_builder_wait_sites", 0)) > 0 and int(engagement.get("outstanding_materials", 0)) > 0 and population >= 4:
                hauler_floor_required = 2
                target_mix["hauler"] = max(int(target_mix.get("hauler", 0)), 2)
        for role_name, floor_required in (("builder", builder_floor_required), ("hauler", hauler_floor_required)):
            role_diag = support_diag["roles"][role_name]
            role_diag["floor_requested"] = bool(floor_required > 0)
            role_diag["floor_required"] = int(floor_required)
            if bool(floor_required > 0) and true_survival_crisis:
                fr = role_diag.get("filter_reasons")
                if isinstance(fr, dict):
                    fr["food_base_reserved"] = int(fr.get("food_base_reserved", 0)) + 1

        desired_farmers = int(target_mix.get("farmer", 0))
        desired_builders = int(target_mix.get("builder", 0))
        desired_haulers = int(target_mix.get("hauler", 0))
        desired_foragers = int(target_mix.get("forager", 0))
        support_diag["roles"]["builder"]["target_requested"] = int(desired_builders)
        support_diag["roles"]["hauler"]["target_requested"] = int(desired_haulers)

        assigned_ids = set()
        rebalance_due = specialist_rebalance_due(world, village)
        protected_specialist_ids = set()
        if not rebalance_due:
            for a in workers_sorted:
                if getattr(a, "role", "") in SPECIALIST_ROLES:
                    protected_specialist_ids.add(id(a))

        support_signal_recent = (
            int(engagement.get("recent_heartbeat_sites", 0)) > 0
            or int(engagement.get("recent_builder_wait_sites", 0)) > 0
        )
        for role_name in SUPPORT_ASSIGNMENT_ROLES:
            rd = support_relax_diag["roles"][role_name]
            if bool(engagement.get("live_demand", False)):
                rd["live_demand_context_seen"] = int(rd.get("live_demand_context_seen", 0)) + 1
            else:
                reasons = rd.get("short_circuit_reasons")
                if isinstance(reasons, dict):
                    reasons["no_live_demand_context"] = int(reasons.get("no_live_demand_context", 0)) + 1
            if bool(support_signal_recent):
                rd["support_signal_recent_seen"] = int(rd.get("support_signal_recent_seen", 0)) + 1
            else:
                reasons = rd.get("short_circuit_reasons")
                if isinstance(reasons, dict):
                    reasons["support_signal_not_recent"] = int(reasons.get("support_signal_not_recent", 0)) + 1
            if bool(true_survival_crisis):
                rd["true_survival_crisis_seen"] = int(rd.get("true_survival_crisis_seen", 0)) + 1
                reasons = rd.get("short_circuit_reasons")
                if isinstance(reasons, dict):
                    reasons["true_survival_crisis"] = int(reasons.get("true_survival_crisis", 0)) + 1
        floor_override_budget = {
            # One bounded hold-override per role, only in safe live-demand windows
            # with a recent local construction signal.
            "builder": 1 if bool(engagement.get("live_demand", False)) and not true_survival_crisis and population >= 2 and bool(support_signal_recent) else 0,
            "hauler": 1 if bool(engagement.get("live_demand", False)) and not true_survival_crisis and population >= 2 and int(engagement.get("outstanding_materials", 0)) > 0 and bool(support_signal_recent) else 0,
        }
        food_base_relaxation_budget = {
            # At most one relaxed admission per support role, only in safe non-terminal windows.
            "builder": 1 if bool(engagement.get("live_demand", False)) and not true_survival_crisis and population >= 2 and bool(support_signal_recent) else 0,
            "hauler": 1 if bool(engagement.get("live_demand", False)) and not true_survival_crisis and population >= 2 and int(engagement.get("outstanding_materials", 0)) > 0 and bool(support_signal_recent) else 0,
        }
        for role_name in SUPPORT_ASSIGNMENT_ROLES:
            rd = support_relax_diag["roles"][role_name]
            if not bool(true_survival_crisis) and population >= 2:
                rd["population_safe_for_relaxation"] = int(rd.get("population_safe_for_relaxation", 0)) + 1
            else:
                reasons = rd.get("short_circuit_reasons")
                if isinstance(reasons, dict):
                    reasons["population_not_safe"] = int(reasons.get("population_not_safe", 0)) + 1
            rd["food_base_relaxation_budget_granted"] = int(food_base_relaxation_budget.get(role_name, 0))
            rd["hold_override_budget_granted"] = int(floor_override_budget.get(role_name, 0))
        # Preserve a hard food-base floor while allowing a narrow support-role window.
        # This keeps roughly half the local workforce food-capable in fragile states.
        food_workers_min_reserved = max(1, int((population + 1) // 2))
        current_food_workers = sum(1 for a in workers_sorted if str(getattr(a, "role", "")) in {"farmer", "forager"})
        metrics = village.setdefault("metrics", {})
        reserved_slot_state = village.get("reserved_civic_support")
        if not isinstance(reserved_slot_state, dict):
            reserved_slot_state = _default_reserved_civic_support_state()
            village["reserved_civic_support"] = reserved_slot_state
        for k, v in _default_reserved_civic_support_state().items():
            reserved_slot_state[k] = reserved_slot_state.get(k, v)
        reserved_slot_metrics = metrics.get("reserved_civic_support_metrics")
        if not isinstance(reserved_slot_metrics, dict):
            reserved_slot_metrics = _default_reserved_civic_support_metrics()
            metrics["reserved_civic_support_metrics"] = reserved_slot_metrics
        defaults = _default_reserved_civic_support_metrics()
        for k, v in defaults.items():
            if k not in reserved_slot_metrics:
                reserved_slot_metrics[k] = v
        role_counts = reserved_slot_metrics.get("reserved_civic_support_role_counts")
        if not isinstance(role_counts, dict):
            role_counts = {"builder": 0, "hauler": 0}
            reserved_slot_metrics["reserved_civic_support_role_counts"] = role_counts
        released_reasons = reserved_slot_metrics.get("reserved_civic_support_released_reason_counts")
        if not isinstance(released_reasons, dict):
            released_reasons = {}
            reserved_slot_metrics["reserved_civic_support_released_reason_counts"] = released_reasons
        reserved_slot_gate_diag = metrics.get("reserved_civic_support_gate_diagnostics")
        if not isinstance(reserved_slot_gate_diag, dict):
            reserved_slot_gate_diag = _default_reserved_civic_support_gate_diag()
            metrics["reserved_civic_support_gate_diagnostics"] = reserved_slot_gate_diag
        gate_roles = reserved_slot_gate_diag.get("roles")
        if not isinstance(gate_roles, dict):
            gate_roles = {}
            reserved_slot_gate_diag["roles"] = gate_roles
        for role_name in ("builder", "hauler"):
            entry = gate_roles.get(role_name)
            if not isinstance(entry, dict):
                gate_roles[role_name] = _default_reserved_civic_support_gate_role_diag()
                continue
            defaults = _default_reserved_civic_support_gate_role_diag()
            for k, v in defaults.items():
                if k not in entry:
                    entry[k] = v
            if not isinstance(entry.get("slot_activation_block_reasons"), dict):
                entry["slot_activation_block_reasons"] = {}

        def _release_reserved_support_slot(reason: str) -> None:
            nonlocal reserved_slot_state, released_reasons
            if not bool(reserved_slot_state.get("reserved_civic_support_active", False)):
                return
            key = str(reason or "released").strip() or "released"
            released_reasons[key] = int(released_reasons.get(key, 0)) + 1
            if key == "slot_expired":
                reserved_slot_metrics["reserved_civic_support_expired_count"] = int(
                    reserved_slot_metrics.get("reserved_civic_support_expired_count", 0)
                ) + 1
            reserved_slot_state["reserved_civic_support_active"] = False
            reserved_slot_state["reserved_civic_support_agent_id"] = ""
            reserved_slot_state["reserved_civic_support_role"] = ""
            reserved_slot_state["reserved_civic_support_until_tick"] = -1
            reserved_slot_state["reserved_civic_support_reason"] = ""

        def take(n: int, role: str) -> None:
            nonlocal current_food_workers
            if n <= 0:
                if role in SUPPORT_ASSIGNMENT_ROLES and bool(engagement.get("live_demand", False)):
                    role_diag = support_diag["roles"][role]
                    if bool(role_diag.get("floor_requested", False)):
                        fr = role_diag.get("filter_reasons")
                        if isinstance(fr, dict):
                            fr["cached_target_override_missed"] = int(fr.get("cached_target_override_missed", 0)) + 1
                return
            candidate_pool = []
            override_candidates_added = 0
            for a in workers_sorted:
                if role in SUPPORT_ASSIGNMENT_ROLES:
                    support_diag["roles"][role]["candidates_total"] = int(support_diag["roles"][role]["candidates_total"]) + 1
                aid = id(a)
                if aid in assigned_ids:
                    if role in SUPPORT_ASSIGNMENT_ROLES:
                        rr = support_diag["roles"][role]
                        rr["candidates_filtered_out"] = int(rr.get("candidates_filtered_out", 0)) + 1
                        fr = rr.get("filter_reasons")
                        if isinstance(fr, dict):
                            fr["already_selected_for_other_role"] = int(fr.get("already_selected_for_other_role", 0)) + 1
                        rd = support_relax_diag["roles"][role]
                        sr = rd.get("short_circuit_reasons")
                        if isinstance(sr, dict):
                            sr["filtered_by_other_role_selection"] = int(sr.get("filtered_by_other_role_selection", 0)) + 1
                    continue
                if aid in protected_specialist_ids and role in CORE_ROLES:
                    if role in SUPPORT_ASSIGNMENT_ROLES:
                        rr = support_diag["roles"][role]
                        rr["candidates_filtered_out"] = int(rr.get("candidates_filtered_out", 0)) + 1
                        fr = rr.get("filter_reasons")
                        if isinstance(fr, dict):
                            fr["specialist_preserved"] = int(fr.get("specialist_preserved", 0)) + 1
                        rd = support_relax_diag["roles"][role]
                        sr = rd.get("short_circuit_reasons")
                        if isinstance(sr, dict):
                            sr["filtered_by_specialist_preservation"] = int(sr.get("filtered_by_specialist_preservation", 0)) + 1
                    continue
                relaxed_food_base_for_candidate = False
                if role in SUPPORT_ASSIGNMENT_ROLES and str(getattr(a, "role", "")) in {"farmer", "forager"}:
                    projected_food_workers = int(current_food_workers) - 1
                    requires_reserve = projected_food_workers < int(food_workers_min_reserved)
                    if requires_reserve:
                        can_relax_food_base = (
                            int(food_base_relaxation_budget.get(role, 0)) > 0
                            and not true_survival_crisis
                        )
                        if can_relax_food_base:
                            food_base_relaxation_budget[role] = max(0, int(food_base_relaxation_budget.get(role, 0)) - 1)
                            rr = support_diag["roles"][role]
                            fr = rr.get("filter_reasons")
                            if isinstance(fr, dict):
                                fr["food_base_relaxed_for_support_role"] = int(fr.get("food_base_relaxed_for_support_role", 0)) + 1
                            rd = support_relax_diag["roles"][role]
                            rd["food_base_relaxation_budget_consumed"] = int(rd.get("food_base_relaxation_budget_consumed", 0)) + 1
                            relaxed_food_base_for_candidate = True
                        else:
                            rr = support_diag["roles"][role]
                            rr["candidates_filtered_out"] = int(rr.get("candidates_filtered_out", 0)) + 1
                            fr = rr.get("filter_reasons")
                            if isinstance(fr, dict):
                                fr["food_base_reserved"] = int(fr.get("food_base_reserved", 0)) + 1
                            rd = support_relax_diag["roles"][role]
                            sr = rd.get("short_circuit_reasons")
                            if isinstance(sr, dict):
                                sr["food_base_block_before_relax"] = int(sr.get("food_base_block_before_relax", 0)) + 1
                                if int(rd.get("food_base_relaxation_budget_granted", 0)) <= 0:
                                    sr["relax_budget_not_granted"] = int(sr.get("relax_budget_not_granted", 0)) + 1
                            continue
                if not _can_change_role(world, a, role):
                    floor_needed = False
                    if role in SUPPORT_ASSIGNMENT_ROLES:
                        rr = support_diag["roles"][role]
                        floor_required = int(rr.get("floor_required", 0))
                        selected_count = int(rr.get("selected_count", 0))
                        floor_needed = floor_required > selected_count
                    can_override_hold = (
                        role in SUPPORT_ASSIGNMENT_ROLES
                        and floor_needed
                        and (
                            (
                                int(floor_override_budget.get(role, 0)) > 0
                                and override_candidates_added < int(floor_override_budget.get(role, 0))
                            )
                            or bool(relaxed_food_base_for_candidate)
                        )
                    )
                    if can_override_hold:
                        last_prod = getattr(a, "workforce_last_productive_tick_by_role", {})
                        role_last_prod = int(last_prod.get(role, -10_000)) if isinstance(last_prod, dict) else -10_000
                        # prioritize one bounded override candidate before normal continuity ranking.
                        candidate_pool.append((0, 0, role_last_prod, a, True))
                        if role in SUPPORT_ASSIGNMENT_ROLES:
                            rr = support_diag["roles"][role]
                            rr["candidates_eligible"] = int(rr.get("candidates_eligible", 0)) + 1
                            rd = support_relax_diag["roles"][role]
                            rd["eligible_count"] = int(rd.get("eligible_count", 0)) + 1
                            sr = rd.get("short_circuit_reasons")
                            if isinstance(sr, dict):
                                sr["candidate_became_eligible"] = int(sr.get("candidate_became_eligible", 0)) + 1
                        override_candidates_added += 1
                        continue
                    if hasattr(world, "record_workforce_block_reason"):
                        world.record_workforce_block_reason(a, str(getattr(a, "role", "")), "role_hold_block")
                    if role in SUPPORT_ASSIGNMENT_ROLES:
                        rr = support_diag["roles"][role]
                        rr["candidates_filtered_out"] = int(rr.get("candidates_filtered_out", 0)) + 1
                        fr = rr.get("filter_reasons")
                        if isinstance(fr, dict):
                            fr["role_hold_block"] = int(fr.get("role_hold_block", 0)) + 1
                        rd = support_relax_diag["roles"][role]
                        sr = rd.get("short_circuit_reasons")
                        if isinstance(sr, dict):
                            sr["role_hold_block_before_override"] = int(sr.get("role_hold_block_before_override", 0)) + 1
                            if int(rd.get("hold_override_budget_granted", 0)) <= 0:
                                sr["hold_override_not_granted"] = int(sr.get("hold_override_not_granted", 0)) + 1
                            if bool(relaxed_food_base_for_candidate):
                                sr["filtered_after_relaxation_other_guard"] = int(sr.get("filtered_after_relaxation_other_guard", 0)) + 1
                    continue
                last_prod = getattr(a, "workforce_last_productive_tick_by_role", {})
                role_last_prod = int(last_prod.get(role, -10_000)) if isinstance(last_prod, dict) else -10_000
                recently_productive = (int(world.tick) - role_last_prod) <= ROLE_CONTINUITY_PRODUCTIVE_WINDOW_TICKS
                currently_role = str(getattr(a, "role", "")) == role
                continuity_rank = 2
                if currently_role and recently_productive:
                    continuity_rank = 0
                elif currently_role:
                    continuity_rank = 1
                candidate_pool.append((1, continuity_rank, role_last_prod, a, False))
                if role in SUPPORT_ASSIGNMENT_ROLES:
                    rr = support_diag["roles"][role]
                    rr["candidates_eligible"] = int(rr.get("candidates_eligible", 0)) + 1
                    rd = support_relax_diag["roles"][role]
                    rd["eligible_count"] = int(rd.get("eligible_count", 0)) + 1
                    sr = rd.get("short_circuit_reasons")
                    if isinstance(sr, dict):
                        sr["candidate_became_eligible"] = int(sr.get("candidate_became_eligible", 0)) + 1

            candidate_pool.sort(
                key=lambda item: (
                    int(item[0]),
                    int(item[1]),
                    -int(item[2]),
                    _agent_affiliation_rank_for_village(world, village, item[3]),
                    -float(getattr(item[3], "hunger", 0.0)),
                    str(getattr(item[3], "agent_id", "")),
                )
            )

            count = 0
            for _, _, _, a, used_override in candidate_pool:
                previous_role_name = str(getattr(a, "role", ""))
                _set_role(world, a, role, reason="adaptive_workforce_allocation")
                if used_override and role in SUPPORT_ASSIGNMENT_ROLES:
                    floor_override_budget[role] = max(0, int(floor_override_budget.get(role, 0)) - 1)
                    rd = support_relax_diag["roles"][role]
                    rd["hold_override_budget_consumed"] = int(rd.get("hold_override_budget_consumed", 0)) + 1
                if role in {"builder", "hauler"} and bool(engagement.get("live_demand", False)):
                    sticky_hold = int(world.tick) + int(ROLE_MIN_HOLD_TICKS) + 6
                    a.role_hold_until_tick = max(int(getattr(a, "role_hold_until_tick", -1)), sticky_hold)
                aid = id(a)
                assigned_ids.add(aid)
                if role in SUPPORT_ASSIGNMENT_ROLES and previous_role_name in {"farmer", "forager"}:
                    current_food_workers = max(0, int(current_food_workers) - 1)
                count += 1
                if role in SUPPORT_ASSIGNMENT_ROLES:
                    rr = support_diag["roles"][role]
                    rr["selected_count"] = int(rr.get("selected_count", 0)) + 1
                    selected_ids = rr.get("selected_agent_ids")
                    if isinstance(selected_ids, list) and len(selected_ids) < 6:
                        selected_ids.append(str(getattr(a, "agent_id", "")))
                if count >= n:
                    break

        take(desired_farmers, "farmer")
        take(desired_builders, "builder")
        take(desired_haulers, "hauler")
        take(desired_foragers, "forager")
        specialist_out = apply_specialist_allocation_policy(
            world,
            village,
            workers_sorted,
            assigned_ids,
            protected_specialist_ids=protected_specialist_ids,
        )

        for a in workers_sorted:
            aid = id(a)
            if aid in assigned_ids:
                continue
            if aid in protected_specialist_ids and getattr(a, "role", "") in SPECIALIST_ROLES:
                assigned_ids.add(aid)
                continue
            if rebalance_due and getattr(a, "role", "") in SPECIALIST_ROLES:
                _set_role(world, a, "hauler", reason="specialist_rebalance_demote")
                if hasattr(a, "assigned_building_id"):
                    a.assigned_building_id = None
                assigned_ids.add(aid)
                continue
            if _can_change_role(world, a, "hauler"):
                _set_role(world, a, "hauler", reason="adaptive_workforce_fallback")
            elif hasattr(world, "record_workforce_block_reason"):
                world.record_workforce_block_reason(a, str(getattr(a, "role", "")), "role_hold_block")
            assigned_ids.add(aid)
            if getattr(a, "role", "") not in SPECIALIST_ROLES and hasattr(a, "assigned_building_id"):
                a.assigned_building_id = None

        # Reserved civic support slot lifecycle maintenance.
        active_slot = bool(reserved_slot_state.get("reserved_civic_support_active", False))
        if active_slot:
            slot_until = int(reserved_slot_state.get("reserved_civic_support_until_tick", -1))
            slot_agent_id = str(reserved_slot_state.get("reserved_civic_support_agent_id", ""))
            slot_agent = next(
                (
                    a
                    for a in workers_sorted
                    if str(getattr(a, "agent_id", "")) == slot_agent_id and getattr(a, "alive", False)
                ),
                None,
            )
            slot_still_valid = bool(engagement.get("live_demand", False)) and bool(support_signal_recent)
            if int(world.tick) > slot_until:
                _release_reserved_support_slot("slot_expired")
            elif bool(slot_terminal_crisis):
                _release_reserved_support_slot("true_survival_crisis")
            elif population < int(RESERVED_CIVIC_SUPPORT_MIN_POPULATION):
                _release_reserved_support_slot("population_not_safe")
            elif not slot_still_valid:
                _release_reserved_support_slot("demand_disappeared")
            elif slot_agent is None:
                _release_reserved_support_slot("agent_unavailable")
            else:
                slot_role = str(reserved_slot_state.get("reserved_civic_support_role", "") or "builder")
                if slot_role not in {"builder", "hauler"}:
                    slot_role = "builder"
                _set_role(world, slot_agent, slot_role, reason="reserved_civic_support_slot")
                slot_agent.role_hold_until_tick = max(
                    int(getattr(slot_agent, "role_hold_until_tick", -1)),
                    int(slot_until),
                )

        actual_mix = {
            "farmer": sum(1 for a in workers_sorted if getattr(a, "role", "") == "farmer"),
            "builder": sum(1 for a in workers_sorted if getattr(a, "role", "") == "builder"),
            "hauler": sum(1 for a in workers_sorted if getattr(a, "role", "") == "hauler"),
            "forager": sum(1 for a in workers_sorted if getattr(a, "role", "") == "forager"),
            "miner": sum(1 for a in workers_sorted if getattr(a, "role", "") == "miner"),
            "woodcutter": sum(1 for a in workers_sorted if getattr(a, "role", "") == "woodcutter"),
        }
        if not bool(reserved_slot_state.get("reserved_civic_support_active", False)):
            support_floor_gap = (
                int(actual_mix.get("builder", 0)) < int(builder_floor_required)
                or int(actual_mix.get("hauler", 0)) < int(hauler_floor_required)
            )
            safe_slot_window = (
                bool(engagement.get("live_demand", False))
                and bool(support_signal_recent)
                and not bool(slot_terminal_crisis)
                and population >= int(RESERVED_CIVIC_SUPPORT_MIN_POPULATION)
            )

            def _gate_reason_increment(role_name: str, reason: str) -> None:
                rd = gate_roles.get(role_name, {})
                if not isinstance(rd, dict):
                    return
                reasons = rd.get("slot_activation_block_reasons")
                if not isinstance(reasons, dict):
                    reasons = {}
                key = str(reason or "").strip() or "unknown"
                reasons[key] = int(reasons.get(key, 0)) + 1
                rd["slot_activation_block_reasons"] = reasons
                gate_roles[role_name] = rd

            candidate_map: dict[str, object] = {"builder": None, "hauler": None}
            for role_name in ("builder", "hauler"):
                rd = gate_roles.get(role_name, {})
                rd["gate_evaluations"] = int(rd.get("gate_evaluations", 0)) + 1
                if bool(engagement.get("live_demand", False)):
                    rd["live_construction_demand_seen"] = int(rd.get("live_construction_demand_seen", 0)) + 1
                else:
                    _gate_reason_increment(role_name, "no_live_construction_demand")
                if bool(support_signal_recent):
                    rd["support_signal_recent_seen"] = int(rd.get("support_signal_recent_seen", 0)) + 1
                else:
                    _gate_reason_increment(role_name, "support_signal_not_recent")
                if bool(slot_terminal_crisis):
                    rd["true_survival_crisis_blocked"] = int(rd.get("true_survival_crisis_blocked", 0)) + 1
                    _gate_reason_increment(role_name, "true_survival_crisis")
                if population < int(RESERVED_CIVIC_SUPPORT_MIN_POPULATION):
                    rd["population_not_safe_blocked"] = int(rd.get("population_not_safe_blocked", 0)) + 1
                    _gate_reason_increment(role_name, "population_not_safe")
                required_floor = int(builder_floor_required if role_name == "builder" else hauler_floor_required)
                role_gap = int(actual_mix.get(role_name, 0)) < required_floor
                if role_gap:
                    rd["support_floor_gap_seen"] = int(rd.get("support_floor_gap_seen", 0)) + 1
                    rd["support_floor_gap_count"] = int(rd.get("support_floor_gap_count", 0)) + 1
                else:
                    _gate_reason_increment(role_name, "no_support_floor_gap")
                gate_roles[role_name] = rd

                if not (
                    bool(engagement.get("live_demand", False))
                    and bool(support_signal_recent)
                    and not bool(slot_terminal_crisis)
                    and population >= int(RESERVED_CIVIC_SUPPORT_MIN_POPULATION)
                    and role_gap
                ):
                    continue
                food_floor = max(0, population // 4)
                current_food_roles = int(actual_mix.get("farmer", 0)) + int(actual_mix.get("forager", 0))
                candidates = sorted(
                    workers_sorted,
                    key=lambda a: (
                        _agent_affiliation_rank_for_village(world, village, a),
                        0 if _can_change_role(world, a, role_name) else 1,
                        0 if str(getattr(a, "role", "")) in {"farmer", "forager"} else 1,
                        -float(getattr(a, "hunger", 0.0)),
                        str(getattr(a, "agent_id", "")),
                    ),
                )
                chosen_candidate = None
                for cand in candidates:
                    crole = str(getattr(cand, "role", ""))
                    projected_food_roles = current_food_roles - 1 if crole in {"farmer", "forager"} else current_food_roles
                    if projected_food_roles < food_floor:
                        continue
                    chosen_candidate = cand
                    break
                if chosen_candidate is not None:
                    rd = gate_roles.get(role_name, {})
                    rd["candidate_available_count"] = int(rd.get("candidate_available_count", 0)) + 1
                    gate_roles[role_name] = rd
                    candidate_map[role_name] = chosen_candidate
                else:
                    _gate_reason_increment(role_name, "no_candidate_available")

            if safe_slot_window and support_floor_gap:
                preferred_role = "builder"
                if int(engagement.get("outstanding_materials", 0)) > 0 and int(engagement.get("recent_builder_wait_sites", 0)) > 0:
                    preferred_role = "hauler"
                chosen = candidate_map.get(preferred_role)
                if chosen is not None:
                    _set_role(world, chosen, preferred_role, reason="reserved_civic_support_slot")
                    until_tick = int(world.tick) + int(RESERVED_CIVIC_SUPPORT_DURATION_TICKS)
                    chosen.role_hold_until_tick = max(
                        int(getattr(chosen, "role_hold_until_tick", -1)),
                        int(until_tick),
                    )
                    reserved_slot_state["reserved_civic_support_active"] = True
                    reserved_slot_state["reserved_civic_support_agent_id"] = str(getattr(chosen, "agent_id", ""))
                    reserved_slot_state["reserved_civic_support_role"] = str(preferred_role)
                    reserved_slot_state["reserved_civic_support_until_tick"] = int(until_tick)
                    reserved_slot_state["reserved_civic_support_reason"] = "live_construction_support"
                    reserved_slot_metrics["reserved_civic_support_activations"] = int(
                        reserved_slot_metrics.get("reserved_civic_support_activations", 0)
                    ) + 1
                    role_counts[str(preferred_role)] = int(role_counts.get(str(preferred_role), 0)) + 1
                    rd = gate_roles.get(preferred_role, {})
                    rd["slot_activation_granted"] = int(rd.get("slot_activation_granted", 0)) + 1
                    gate_roles[preferred_role] = rd
                    _gate_reason_increment(preferred_role, "slot_activated")
                    # Refresh actual mix after slot assignment.
                    actual_mix = {
                        "farmer": sum(1 for a in workers_sorted if getattr(a, "role", "") == "farmer"),
                        "builder": sum(1 for a in workers_sorted if getattr(a, "role", "") == "builder"),
                        "hauler": sum(1 for a in workers_sorted if getattr(a, "role", "") == "hauler"),
                        "forager": sum(1 for a in workers_sorted if getattr(a, "role", "") == "forager"),
                        "miner": sum(1 for a in workers_sorted if getattr(a, "role", "") == "miner"),
                        "woodcutter": sum(1 for a in workers_sorted if getattr(a, "role", "") == "woodcutter"),
                    }
                else:
                    _gate_reason_increment(preferred_role, "no_candidate_available")
        target_metrics = {
            "farmer": int(desired_farmers),
            "builder": int(desired_builders),
            "hauler": int(desired_haulers),
            "forager": int(desired_foragers),
            "miner": int(specialist_out.get("miner_target", 0)),
            "woodcutter": int(specialist_out.get("woodcutter_target", 0)),
        }
        deficits = {
            role: max(0, int(target_metrics.get(role, 0)) - int(actual_mix.get(role, 0)))
            for role in ("farmer", "builder", "hauler", "forager", "miner", "woodcutter")
        }
        for role_name in SUPPORT_ASSIGNMENT_ROLES:
            rr = support_diag["roles"][role_name]
            rr["final_assigned_count_after_pass"] = int(actual_mix.get(role_name, 0))
            floor_required = int(rr.get("floor_required", 0))
            rr["floor_satisfied"] = bool(int(actual_mix.get(role_name, 0)) >= floor_required) if floor_required > 0 else True
            rd = support_relax_diag["roles"][role_name]
            sr = rd.get("short_circuit_reasons")
            if isinstance(sr, dict):
                if int(rd.get("food_base_relaxation_budget_granted", 0)) > int(rd.get("food_base_relaxation_budget_consumed", 0)):
                    sr["relax_budget_granted_but_not_used"] = int(sr.get("relax_budget_granted_but_not_used", 0)) + 1
                if int(rd.get("hold_override_budget_granted", 0)) > int(rd.get("hold_override_budget_consumed", 0)):
                    sr["hold_override_granted_but_not_used"] = int(sr.get("hold_override_granted_but_not_used", 0)) + 1
                for reason in SUPPORT_RELAXATION_SHORT_CIRCUIT_REASONS:
                    sr[str(reason)] = int(sr.get(str(reason), 0))
                rd["short_circuit_reasons"] = sr
            for key in (
                "live_demand_context_seen",
                "support_signal_recent_seen",
                "true_survival_crisis_seen",
                "population_safe_for_relaxation",
                "food_base_relaxation_budget_granted",
                "food_base_relaxation_budget_consumed",
                "hold_override_budget_granted",
                "hold_override_budget_consumed",
                "eligible_count",
            ):
                rd[key] = int(rd.get(key, 0))
        reserved_slot_metrics["reserved_civic_support_active_count"] = 1 if bool(
            reserved_slot_state.get("reserved_civic_support_active", False)
        ) else 0
        for role_name in ("builder", "hauler"):
            rd = gate_roles.get(role_name, {})
            for k in (
                "gate_evaluations",
                "live_construction_demand_seen",
                "support_signal_recent_seen",
                "true_survival_crisis_blocked",
                "population_not_safe_blocked",
                "support_floor_gap_seen",
                "support_floor_gap_count",
                "candidate_available_count",
                "slot_activation_granted",
            ):
                rd[k] = int(rd.get(k, 0))
            reasons = rd.get("slot_activation_block_reasons")
            if not isinstance(reasons, dict):
                reasons = {}
            rd["slot_activation_block_reasons"] = {str(k): int(v) for k, v in reasons.items()}
            gate_roles[role_name] = rd
        reserved_slot_gate_diag["roles"] = gate_roles
        metrics["reserved_civic_support_gate_diagnostics"] = reserved_slot_gate_diag
        metrics["support_role_relaxation_diagnostics"] = support_relax_diag
        metrics["support_role_assignment_diagnostics"] = support_diag
        metrics["workforce_target_mix"] = dict(target_metrics)
        metrics["workforce_actual_mix"] = dict(actual_mix)
        metrics["workforce_role_deficits"] = dict(deficits)
        metrics["workforce_reallocation_interval_ticks"] = int(WORKFORCE_REALLOCATION_INTERVAL_TICKS)
        metrics["workforce_role_hold_ticks"] = int(ROLE_MIN_HOLD_TICKS)
        metrics["workforce_last_reallocation_tick"] = int(workforce_state.get("last_reallocation_tick", -WORKFORCE_REALLOCATION_INTERVAL_TICKS))
        metrics["workforce_pressure_summary"] = {
            "food_pressure": int(target_mix.get("food_pressure", 0)),
            "construction_pressure": int(target_mix.get("construction_pressure", 0)),
            "logistics_pressure": int(target_mix.get("logistics_pressure", 0)),
            "material_pressure": int(target_mix.get("material_pressure", 0)),
            "resident_population": int(target_mix.get("resident_population", 0)),
            "attached_population": int(target_mix.get("attached_population", 0)),
        }

        for a in workers_sorted:
            if getattr(a, "role", "") not in SPECIALIST_ROLES and hasattr(a, "assigned_building_id"):
                a.assigned_building_id = None
