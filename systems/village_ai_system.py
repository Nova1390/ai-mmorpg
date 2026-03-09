from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from world import World

MARKET_UPDATE_INTERVAL_TICKS = 5
CULTURE_UPDATE_INTERVAL_TICKS = 120


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def ensure_village_proto_culture(village: Dict[str, Any]) -> Dict[str, Any]:
    culture = village.get("proto_culture")
    if isinstance(culture, dict):
        return culture

    storage = village.get("storage", {}) if isinstance(village.get("storage"), dict) else {}
    food_stock = max(0, int(storage.get("food", 0)))
    wood_stock = max(0, int(storage.get("wood", 0)))
    stone_stock = max(0, int(storage.get("stone", 0)))
    total = max(1, food_stock + wood_stock + stone_stock)

    food_focus = _clamp(food_stock / total, 0.0, 1.0)
    wood_focus = _clamp(wood_stock / total, 0.0, 1.0)
    stone_focus = _clamp(stone_stock / total, 0.0, 1.0)

    # Slight deterministic offsets from founding/local state.
    pop = max(1, int(village.get("population", 0)))
    houses = max(1, int(village.get("houses", 0)))
    coop_base = 0.48 + min(0.08, pop * 0.01)
    work_base = 0.50 + min(0.07, houses * 0.01)
    explore_base = 0.45 + (0.05 if wood_focus + stone_focus > food_focus else 0.0)
    risk_base = 0.45 + (0.04 if food_focus < 0.33 else 0.0)

    culture = {
        "cooperation_norm": round(_clamp(coop_base, 0.0, 1.0), 3),
        "work_norm": round(_clamp(work_base, 0.0, 1.0), 3),
        "exploration_norm": round(_clamp(explore_base, 0.0, 1.0), 3),
        "risk_norm": round(_clamp(risk_base, 0.0, 1.0), 3),
        "resource_focus": {
            "food": round(food_focus, 3),
            "wood": round(wood_focus, 3),
            "stone": round(stone_focus, 3),
        },
        "cultural_stability": 0.92,
        "last_culture_update_tick": -1,
    }
    village["proto_culture"] = culture
    return culture


def _dominant_resource_key(resource_focus: Dict[str, float]) -> str:
    ordered = ("food", "wood", "stone")
    return max(ordered, key=lambda r: (float(resource_focus.get(r, 0.0)), -ordered.index(r)))


def update_village_proto_culture(
    world: "World",
    village: Dict[str, Any],
    members: List[Any],
) -> Dict[str, Any]:
    culture = ensure_village_proto_culture(village)
    tick = int(getattr(world, "tick", 0))
    last_tick = int(culture.get("last_culture_update_tick", -1))
    if last_tick >= 0 and tick - last_tick < CULTURE_UPDATE_INTERVAL_TICKS:
        return culture

    market_state = village.get("market_state", {}) if isinstance(village.get("market_state"), dict) else {}
    production_metrics = village.get("production_metrics", {}) if isinstance(village.get("production_metrics"), dict) else {}

    coop_count = 0
    work_count = 0
    explore_count = 0
    failure_count = 0
    events_seen = 0

    for agent in members:
        recent = (getattr(agent, "episodic_memory", {}) or {}).get("recent_events", [])
        if not isinstance(recent, list):
            continue
        for ev in recent[-20:]:
            if not isinstance(ev, dict):
                continue
            ev_tick = int(ev.get("tick", tick))
            if tick - ev_tick > CULTURE_UPDATE_INTERVAL_TICKS:
                continue
            events_seen += 1
            etype = str(ev.get("type", ""))
            outcome = str(ev.get("outcome", ""))
            if etype == "co_present_success" and outcome == "success":
                coop_count += 1
            if etype in {"construction_progress", "delivered_material", "found_resource"} and outcome == "success":
                work_count += 1
            if etype in {"found_resource", "hunger_relief"} and outcome == "success":
                explore_count += 1
            if outcome == "failure":
                failure_count += 1

    coop_obs = _clamp(0.35 + coop_count / max(1, len(members) * 2), 0.0, 1.0)
    work_obs = _clamp(
        0.35
        + (work_count + int(production_metrics.get("wood_from_lumberyards", 0)) + int(production_metrics.get("stone_from_mines", 0)) * 0.5)
        / max(1.0, len(members) * 4.0),
        0.0,
        1.0,
    )
    explore_obs = _clamp(0.30 + explore_count / max(1, len(members) * 2), 0.0, 1.0)
    risk_obs = _clamp((failure_count / max(1, events_seen)) * 0.8 + (0.15 if failure_count > work_count else 0.0), 0.0, 1.0)

    prev_focus = culture.get("resource_focus", {}) if isinstance(culture.get("resource_focus"), dict) else {}
    scarcity_food = float((market_state.get("food") or {}).get("pressure", 0.0))
    scarcity_wood = float((market_state.get("wood") or {}).get("pressure", 0.0))
    scarcity_stone = float((market_state.get("stone") or {}).get("pressure", 0.0))
    total_scarcity = max(0.0001, scarcity_food + scarcity_wood + scarcity_stone)
    focus_obs = {
        "food": _clamp(scarcity_food / total_scarcity, 0.0, 1.0),
        "wood": _clamp(scarcity_wood / total_scarcity, 0.0, 1.0),
        "stone": _clamp(scarcity_stone / total_scarcity, 0.0, 1.0),
    }

    stability = _clamp(float(culture.get("cultural_stability", 0.92)), 0.78, 0.98)
    for key, obs in (
        ("cooperation_norm", coop_obs),
        ("work_norm", work_obs),
        ("exploration_norm", explore_obs),
        ("risk_norm", risk_obs),
    ):
        prev = _clamp(float(culture.get(key, 0.5)), 0.0, 1.0)
        blended = prev * stability + float(obs) * (1.0 - stability)
        culture[key] = round(_clamp(blended, 0.0, 1.0), 3)

    focus_out = {}
    for r in ("food", "wood", "stone"):
        prev = _clamp(float(prev_focus.get(r, 1.0 / 3.0)), 0.0, 1.0)
        blended = prev * stability + float(focus_obs[r]) * (1.0 - stability)
        focus_out[r] = round(_clamp(blended, 0.0, 1.0), 3)
    culture["resource_focus"] = focus_out

    # Reinforcement loop: coherence with observed behavior increases stability; divergence decreases it.
    coherence = (
        1.0
        - (
            abs(float(culture["cooperation_norm"]) - coop_obs)
            + abs(float(culture["work_norm"]) - work_obs)
            + abs(float(culture["exploration_norm"]) - explore_obs)
        )
        / 3.0
    )
    if coherence > 0.7:
        stability = min(0.98, stability + 0.01)
    elif coherence < 0.4:
        stability = max(0.78, stability - 0.015)
    culture["cultural_stability"] = round(_clamp(stability, 0.78, 0.98), 3)
    culture["last_culture_update_tick"] = tick

    village["proto_culture"] = culture
    village["culture_summary"] = {
        "dominant_resource_focus": _dominant_resource_key(focus_out),
        "cooperation_norm": float(culture["cooperation_norm"]),
        "work_norm": float(culture["work_norm"]),
        "exploration_norm": float(culture["exploration_norm"]),
        "risk_norm": float(culture["risk_norm"]),
    }
    return culture


def _resource_market_entry(
    supply: int,
    demand: int,
    previous: Dict[str, Any] | None = None,
) -> Dict[str, float]:
    s = max(0, int(supply))
    d = max(1, int(demand))
    scarcity_ratio = max(0.0, float(d - s) / float(d))
    surplus_ratio = max(0.0, float(s - d) / float(max(1, s)))
    pressure = _clamp(scarcity_ratio, 0.0, 1.0)
    local_price_index = _clamp(1.0 + scarcity_ratio * 1.2 - surplus_ratio * 0.6, 0.5, 2.0)

    if isinstance(previous, dict):
        prev_pressure = float(previous.get("pressure", pressure))
        prev_price = float(previous.get("local_price_index", local_price_index))
        # Deterministic smoothing to reduce oscillation near boundaries.
        pressure = _clamp(prev_pressure * 0.65 + pressure * 0.35, 0.0, 1.0)
        local_price_index = _clamp(prev_price * 0.65 + local_price_index * 0.35, 0.5, 2.0)

    return {
        "supply": int(s),
        "demand": int(d),
        "pressure": round(float(pressure), 3),
        "local_price_index": round(float(local_price_index), 3),
    }


def _construction_resource_demand(world: "World", village: Dict[str, Any], resource_type: str) -> int:
    village_id = village.get("id")
    village_uid = village.get("village_uid")
    total = 0
    for building in getattr(world, "buildings", {}).values():
        if village_id is not None and building.get("village_id") != village_id:
            if village_uid is None or building.get("village_uid") != village_uid:
                continue
        request = building.get("construction_request", {})
        if not isinstance(request, dict):
            continue
        needed = int(request.get(f"{resource_type}_needed", 0))
        reserved = int(request.get(f"{resource_type}_reserved", 0))
        total += max(0, needed - reserved)
    return int(total)


def _compute_village_market_state(
    world: "World",
    village: Dict[str, Any],
    members: List[Any],
    pop: int,
    houses: int,
    avg_hunger: float,
    food_urgent: bool,
    need_materials: bool,
) -> Dict[str, Dict[str, float]]:
    import systems.building_system as building_system

    storage = building_system.get_village_storage_totals(world, village)
    inv_food = sum(int(getattr(a, "inventory", {}).get("food", 0)) for a in members)
    inv_wood = sum(int(getattr(a, "inventory", {}).get("wood", 0)) for a in members)
    inv_stone = sum(int(getattr(a, "inventory", {}).get("stone", 0)) for a in members)

    food_supply = int(storage.get("food", 0)) + inv_food
    wood_supply = int(storage.get("wood", 0)) + inv_wood
    stone_supply = int(storage.get("stone", 0)) + inv_stone

    hunger_pressure = max(0, int(round((60.0 - float(avg_hunger)) / 10.0)))
    food_demand = max(1, pop * 2 + hunger_pressure + (4 if food_urgent else 0))
    housing_pressure = max(0, pop - houses * 4)
    wood_demand = max(
        1,
        pop // 2
        + _construction_resource_demand(world, village, "wood")
        + housing_pressure
        + (2 if need_materials else 0),
    )
    stone_demand = max(
        1,
        pop // 3
        + _construction_resource_demand(world, village, "stone")
        + max(0, housing_pressure // 2)
        + (2 if need_materials else 0),
    )

    previous_state = village.get("market_state", {})
    if not isinstance(previous_state, dict):
        previous_state = {}

    return {
        "food": _resource_market_entry(food_supply, food_demand, previous_state.get("food")),
        "wood": _resource_market_entry(wood_supply, wood_demand, previous_state.get("wood")),
        "stone": _resource_market_entry(stone_supply, stone_demand, previous_state.get("stone")),
    }


def _detect_village_phase(
    houses: int,
    active_farms: int,
    storage_exists: bool,
    food_stock: int,
    pop: int,
) -> str:
    p = max(1, pop)
    if houses < 5:
        return "bootstrap"
    if active_farms < 3 or food_stock < p:
        return "survival"
    if food_stock >= p * 3 and active_farms >= 10:
        return "expansion"
    if houses >= 10 and food_stock >= p * 2:
        return "growth"
    if active_farms >= 5 and storage_exists and food_stock >= p:
        return "stabilize"
    return "stabilize"


def update_village_ai(world: "World") -> None:
    """
    Calcola stato economico e bisogni di ogni villaggio.
    """
    for village in world.villages:
        vid = village["id"]

        members = [
            a for a in world.agents
            if a.alive and getattr(a, "village_id", None) == vid
        ]
        miners_count = sum(1 for a in members if getattr(a, "role", "") == "miner")
        woodcutters_count = sum(1 for a in members if getattr(a, "role", "") == "woodcutter")

        pop = len(members)
        avg_hunger = (
            sum(a.hunger for a in members) / len(members)
            if members else 0.0
        )
        houses = village.get("houses", 0)
        storage = village.get("storage", {"food": 0, "wood": 0, "stone": 0})

        farms = [
            plot for plot in world.farm_plots.values()
            if plot.get("village_id") == vid
        ]

        ripe_farms = sum(1 for f in farms if f.get("state") == "ripe")
        active_farms = sum(1 for f in farms if f.get("state") in ("prepared", "planted", "growing", "ripe"))

        storage_exists = False
        storage_pos = village.get("storage_pos")
        if storage_pos:
            storage_exists = (storage_pos["x"], storage_pos["y"]) in getattr(world, "storage_buildings", set())

        housing_capacity = houses * 4
        food_stock = storage.get("food", 0)
        wood_stock = storage.get("wood", 0)
        stone_stock = storage.get("stone", 0)

        # metriche semplici ma credibili
        food_buffer_target = max(4, pop * 4)
        food_surplus_target = max(3, pop * 3)
        food_surplus = food_stock >= food_surplus_target
        food_buffer_low = food_stock < food_buffer_target
        food_buffer_critical = food_stock < max(2, pop)
        food_low = food_stock < max(4, pop // 2)
        food_urgent = food_stock < max(2, pop // 4)
        overcrowded = pop > housing_capacity
        need_housing = pop >= max(1, housing_capacity - 1)
        need_storage = not storage_exists and houses >= 2
        # Hard trigger: once a minimal farming base exists, force first storage project earlier.
        if (not storage_exists) and active_farms >= 2:
            need_storage = True
        min_farms_target = max(3, pop // 3)
        need_farms = active_farms < min_farms_target
        need_roads = active_farms >= 3 and len(world.roads) < active_farms
        need_materials = wood_stock < 6 or stone_stock < 4
        hunger_critical = avg_hunger < 45
        secure_food_deescalate = (
            storage_exists
            and active_farms >= min_farms_target
            and avg_hunger >= 55
        )

        market_last_update_tick = int(village.get("market_last_update_tick", -MARKET_UPDATE_INTERVAL_TICKS))
        if int(world.tick) - market_last_update_tick >= MARKET_UPDATE_INTERVAL_TICKS:
            village["market_state"] = _compute_village_market_state(
                world=world,
                village=village,
                members=members,
                pop=pop,
                houses=houses,
                avg_hunger=avg_hunger,
                food_urgent=food_urgent,
                need_materials=need_materials,
            )
            village["market_last_update_tick"] = int(world.tick)
        market_state = village.get("market_state", {})
        if not isinstance(market_state, dict):
            market_state = {}
            village["market_state"] = market_state

        village_phase = _detect_village_phase(houses, active_farms, storage_exists, food_stock, pop)
        village["phase"] = village_phase
        production_metrics = village.get("production_metrics", {})
        total_food_gathered = int(production_metrics.get("total_food_gathered", 0))
        total_wood_gathered = int(production_metrics.get("total_wood_gathered", 0))
        total_stone_gathered = int(production_metrics.get("total_stone_gathered", 0))
        direct_food_gathered = int(production_metrics.get("direct_food_gathered", 0))
        direct_wood_gathered = int(production_metrics.get("direct_wood_gathered", 0))
        direct_stone_gathered = int(production_metrics.get("direct_stone_gathered", 0))
        wood_from_lumberyards = int(production_metrics.get("wood_from_lumberyards", 0))
        stone_from_mines = int(production_metrics.get("stone_from_mines", 0))
        logistics_metrics = village.get("logistics_metrics", {})
        internal_transfers_count = int(logistics_metrics.get("internal_transfers_count", 0))
        redistributed_wood = int(logistics_metrics.get("redistributed_wood", 0))
        redistributed_stone = int(logistics_metrics.get("redistributed_stone", 0))
        redistributed_food = int(logistics_metrics.get("redistributed_food", 0))
        policy_state = village.get("policy_build_state", {})
        last_policy_build_tick = int(policy_state.get("last_policy_build_tick", -1))
        next_policy_build_tick = int(policy_state.get("next_policy_build_tick", 0))
        policy_attempts_in_window = int(policy_state.get("attempts_in_window", 0))
        policy_build_cooldown_remaining = max(0, next_policy_build_tick - int(world.tick))
        existing_metrics = village.get("metrics", {}) if isinstance(village.get("metrics"), dict) else {}
        miner_target = int(existing_metrics.get("miner_target", 0))
        woodcutter_target = int(existing_metrics.get("woodcutter_target", 0))
        specialist_allocation_pressure = int(existing_metrics.get("specialist_allocation_pressure", 0))
        last_specialist_rebalance_tick = int(existing_metrics.get("last_specialist_rebalance_tick", -1))
        specialist_rebalance_due = bool(existing_metrics.get("specialist_rebalance_due", False))

        village["metrics"] = {
            "population": pop,
            "avg_hunger": round(avg_hunger, 2),
            "phase": village_phase,
            "housing_capacity": housing_capacity,
            "food_stock": food_stock,
            "food_buffer_target": food_buffer_target,
            "food_surplus_target": food_surplus_target,
            "wood_stock": wood_stock,
            "stone_stock": stone_stock,
            "active_farms": active_farms,
            "ripe_farms": ripe_farms,
            "storage_exists": storage_exists,
            "total_food_gathered": total_food_gathered,
            "total_wood_gathered": total_wood_gathered,
            "total_stone_gathered": total_stone_gathered,
            "direct_food_gathered": direct_food_gathered,
            "direct_wood_gathered": direct_wood_gathered,
            "direct_stone_gathered": direct_stone_gathered,
            "wood_from_lumberyards": wood_from_lumberyards,
            "stone_from_mines": stone_from_mines,
            "internal_transfers_count": internal_transfers_count,
            "redistributed_wood": redistributed_wood,
            "redistributed_stone": redistributed_stone,
            "redistributed_food": redistributed_food,
            "last_policy_build_tick": last_policy_build_tick,
            "next_policy_build_tick": next_policy_build_tick,
            "policy_attempts_in_window": policy_attempts_in_window,
            "policy_build_cooldown_remaining": policy_build_cooldown_remaining,
            "miners_count": miners_count,
            "woodcutters_count": woodcutters_count,
            "miner_target": miner_target,
            "woodcutter_target": woodcutter_target,
            "specialist_allocation_pressure": specialist_allocation_pressure,
            "last_specialist_rebalance_tick": last_specialist_rebalance_tick,
            "specialist_rebalance_due": specialist_rebalance_due,
            "food_price_index": float(((market_state.get("food") or {}).get("local_price_index", 1.0))),
            "wood_price_index": float(((market_state.get("wood") or {}).get("local_price_index", 1.0))),
            "stone_price_index": float(((market_state.get("stone") or {}).get("local_price_index", 1.0))),
        }

        village["needs"] = {
            "food_surplus": food_surplus,
            "food_buffer_low": food_buffer_low,
            "food_buffer_critical": food_buffer_critical,
            "food_low": food_low,
            "food_urgent": food_urgent,
            "hunger_critical": hunger_critical,
            "secure_food_deescalate": secure_food_deescalate,
            "overcrowded": overcrowded,
            "need_housing": need_housing,
            "need_storage": need_storage,
            "need_farms": need_farms,
            "need_roads": need_roads,
            "need_materials": need_materials,
        }

        baseline_priority = _choose_priority(village["needs"])

        # Phase guardrails: keep priorities sticky until the minimum phase target is met.
        if active_farms < min_farms_target:
            baseline_priority = "expand_farms"
        elif active_farms >= 2 and not storage_exists:
            baseline_priority = "build_storage"
        if food_buffer_low and not food_surplus:
            baseline_priority = "secure_food"
        if baseline_priority == "secure_food" and secure_food_deescalate and not food_buffer_critical:
            baseline_priority = "stabilize"

        # Strategic phase baseline guidance for non-leader governance fallback.
        if village_phase == "bootstrap":
            baseline_priority = "expand_farms" if not need_housing else "build_housing"
        elif village_phase == "survival":
            baseline_priority = "secure_food" if not need_farms else "expand_farms"
        elif village_phase == "stabilize" and baseline_priority == "secure_food":
            baseline_priority = "stabilize"
        elif village_phase == "growth" and baseline_priority in ("secure_food", "stabilize"):
            baseline_priority = "build_housing"
        elif village_phase == "expansion" and baseline_priority in ("secure_food", "stabilize"):
            baseline_priority = "improve_logistics"

        # If no active leader, keep village governance moving with deterministic baseline.
        if village.get("leader_id") is None:
            village["priority"] = baseline_priority
            village["strategy"] = _priority_to_strategy(baseline_priority)
        else:
            village["priority"] = village.get("priority") or baseline_priority
            village["strategy"] = village.get("strategy") or _priority_to_strategy(village["priority"])

        update_village_proto_culture(world, village, members)


def _choose_priority(needs: Dict) -> str:
    if needs.get("food_buffer_critical"):
        return "secure_food"
    if needs.get("food_buffer_low"):
        return "secure_food"
    if needs.get("food_urgent"):
        return "secure_food"
    if needs.get("need_storage"):
        return "build_storage"
    if needs.get("need_housing"):
        return "build_housing"
    if needs.get("need_farms"):
        return "expand_farms"
    if needs.get("need_materials"):
        return "improve_logistics"
    if needs.get("need_roads"):
        return "improve_logistics"
    return "stabilize"


def _priority_to_strategy(priority: str) -> str:
    p = (priority or "stabilize").strip().lower()
    if p == "secure_food":
        return "gather food"
    if p == "build_storage":
        return "build storage"
    if p == "build_housing":
        return "build house"
    if p == "expand_farms":
        return "gather food"
    if p == "improve_logistics":
        return "improve logistics"
    return "stabilize"
