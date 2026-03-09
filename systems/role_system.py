from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from world import World


CORE_ROLES = ("farmer", "builder", "forager", "hauler")
SPECIALIST_ROLES = ("miner", "woodcutter")
SPECIALIST_REBALANCE_INTERVAL_TICKS = 12


def _set_role(world: "World", agent, role: str, reason: str) -> None:
    world.set_agent_role(agent, role, reason=reason)


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
            if a.alive
            and not a.is_player
            and getattr(a, "village_id", None) == village["id"]
        ]

        if not members:
            continue

        # leader resta leader
        workers = [a for a in members if getattr(a, "role", "npc") != "leader"]

        if not workers:
            continue

        needs = village.get("needs", {})
        priority = village.get("priority", "stabilize")
        metrics = village.get("metrics", {})
        pop = len(workers)
        active_farms = int(metrics.get("active_farms", 0))
        storage_exists = bool(metrics.get("storage_exists", False))
        min_farms_target = max(3, int(village.get("population", 0) // 3))

        # quote minime / desiderate
        desired_farmers = max(1, pop // 3 + (1 if pop >= 5 else 0))
        desired_builders = 1 if needs.get("need_housing") or needs.get("need_storage") else 0
        desired_haulers = 1 if pop >= 4 else 0
        desired_foragers = 1 if needs.get("food_urgent") else 0
        farmer_cap_by_pop = max(2, int(pop * 0.45))
        farmer_cap_by_farms = max(2, active_farms // 2 + 2)
        farmer_cap = min(farmer_cap_by_pop, farmer_cap_by_farms)

        # Agricultural bootstrap hardening:
        # first village phase must aggressively create farms before other specializations.
        if active_farms == 0:
            desired_farmers = max(2, desired_farmers)
            desired_builders = max(1, desired_builders)
            desired_haulers = 0
            desired_foragers = 0

        if priority in ("build_storage", "build_housing"):
            desired_builders = max(1, desired_builders)
        if priority == "expand_farms":
            desired_farmers = max(2, desired_farmers)
            if active_farms > 0:
                desired_haulers = max(1, desired_haulers)
        if active_farms >= 5:
            desired_haulers = max(2, desired_haulers)

        # se manca cibo, spingi forte su farmer/forager
        if needs.get("food_urgent"):
            desired_farmers = max(desired_farmers, pop // 2)
        elif needs.get("food_buffer_low"):
            desired_farmers = max(desired_farmers, pop // 3 + 1)

        # Surplus state: once food buffer is healthy, release part of workforce
        # from farming so logistics/building can progress.
        if needs.get("food_surplus"):
            desired_farmers = min(desired_farmers, max(2, pop // 4))
        desired_farmers = min(desired_farmers, farmer_cap)

        # Mature village balance: keep non-farmer workforce active during stable phases.
        if storage_exists and active_farms >= min_farms_target and needs.get("secure_food_deescalate"):
            desired_builders = max(1, desired_builders)
            desired_haulers = max(2, desired_haulers)

        # ordina per "affidabilità"
        workers_sorted = sorted(
            workers,
            key=lambda a: (
                a.hunger,
                a.inventory.get("food", 0) + a.inventory.get("wood", 0) + a.inventory.get("stone", 0),
                getattr(a, "agent_id", ""),
            ),
            reverse=True,
        )

        # Agent dataclass is unhashable, track stable object ids instead.
        assigned_ids = set()
        rebalance_due = specialist_rebalance_due(world, village)
        protected_specialist_ids = set()
        if not rebalance_due:
            for a in workers_sorted:
                if getattr(a, "role", "") in SPECIALIST_ROLES:
                    protected_specialist_ids.add(id(a))

        def take(n: int, role: str) -> None:
            count = 0
            for a in workers_sorted:
                aid = id(a)
                if aid in assigned_ids:
                    continue
                if aid in protected_specialist_ids and role in CORE_ROLES:
                    continue
                _set_role(world, a, role, reason="role_allocation")
                assigned_ids.add(aid)
                count += 1
                if count >= n:
                    break

        take(desired_farmers, "farmer")
        take(desired_builders, "builder")
        take(desired_haulers, "hauler")
        take(desired_foragers, "forager")
        apply_specialist_allocation_policy(
            world,
            village,
            workers_sorted,
            assigned_ids,
            protected_specialist_ids=protected_specialist_ids,
        )
        current_farmers = sum(1 for a in workers_sorted if getattr(a, "role", "") == "farmer")

        # resto guard / generic worker?
        # per ora li teniamo farmer se c'è bisogno, altrimenti hauler
        for a in workers_sorted:
            aid = id(a)
            if aid in assigned_ids:
                continue
            if aid in protected_specialist_ids and getattr(a, "role", "") in SPECIALIST_ROLES:
                assigned_ids.add(aid)
                continue
            if needs.get("food_low") and current_farmers < farmer_cap:
                _set_role(world, a, "farmer", reason="food_priority")
                current_farmers += 1
            else:
                _set_role(world, a, "hauler", reason="fallback_logistics")
            if hasattr(a, "assigned_building_id"):
                a.assigned_building_id = None
            assigned_ids.add(aid)

        for a in workers_sorted:
            if getattr(a, "role", "") not in SPECIALIST_ROLES and hasattr(a, "assigned_building_id"):
                a.assigned_building_id = None
