from __future__ import annotations

import random
from typing import Tuple
import systems.building_system as building_system

Coord = Tuple[int, int]

PREPARE_WOOD_COST = 1
PLANT_GROW_TICKS = 35
HARVEST_YIELD = 1
HARVEST_BONUS_CHANCE = 0.3
STORAGE_NEAR_FARM_RADIUS = 5
PRIMARY_FARM_ZONE_RADIUS = 6
FARM_DISCOVERY_CELL = 4
FARM_DISCOVERY_DECAY = 0.985
FARM_DISCOVERY_RETENTION_TICKS = 260
FARM_MIN_REPEAT_GATHER = 1
FARM_MIN_SUCCESS_RATE = 0.40
FARM_MIN_CANDIDATE_SCORE = 1.9
FARM_CONTINUITY_CANDIDATE_SCORE = 1.6
FARM_BOOTSTRAP_MIN_SCORE = 1.1
FARM_BOOTSTRAP_MAX_HUNGER = 100.0
FARM_ABANDON_IDLE_TICKS = 220
FARM_ABANDON_LOW_PRODUCTIVITY = 0.35
FARM_PRODUCTIVE_IDLE_BONUS_TICKS = 80
EARLY_FARM_WINDOW_TICKS = 220
EARLY_FARM_PRODUCTIVE_SCORE = 0.85
EARLY_FARM_PERSISTENCE_BONUS_TICKS = 4


def _get_build_wallet(world, agent):
    return agent.inventory


def _farm_discovery_map(world) -> dict:
    memory = getattr(world, "farm_discovery_memory", None)
    if not isinstance(memory, dict):
        memory = {}
        setattr(world, "farm_discovery_memory", memory)
    return memory


def _farm_discovery_key(x: int, y: int) -> str:
    cell = max(1, int(FARM_DISCOVERY_CELL))
    return f"{int(x)//cell}:{int(y)//cell}"


def _farm_discovery_entry(world, x: int, y: int) -> dict:
    key = _farm_discovery_key(int(x), int(y))
    memory = _farm_discovery_map(world)
    entry = memory.get(key)
    if not isinstance(entry, dict):
        entry = {
            "attempt_count": 0,
            "success_count": 0,
            "repeat_gather_count": 0,
            "patch_productivity_score": 0.0,
            "productivity_score": 0.0,
            "last_tick": int(getattr(world, "tick", 0)),
        }
        memory[key] = entry
    return entry


def record_food_site_observation(world, x: int, y: int, *, success: bool, amount: int = 1) -> None:
    entry = _farm_discovery_entry(world, int(x), int(y))
    entry["attempt_count"] = int(entry.get("attempt_count", 0)) + 1
    if bool(success):
        qty = max(1, int(amount))
        entry["success_count"] = int(entry.get("success_count", 0)) + qty
        entry["repeat_gather_count"] = int(entry.get("repeat_gather_count", 0)) + 1
    else:
        entry["repeat_gather_count"] = max(0, int(entry.get("repeat_gather_count", 0)) - 1)
    patch_score = 0.0
    if hasattr(world, "_patch_activity_score_at"):
        try:
            patch_score = float(world._patch_activity_score_at(int(x), int(y)))
        except Exception:
            patch_score = 0.0
    entry["patch_productivity_score"] = float(max(0.0, patch_score))
    attempts = max(1, int(entry.get("attempt_count", 0)))
    successes = int(entry.get("success_count", 0))
    success_rate = float(successes) / float(attempts)
    score = float(entry.get("productivity_score", 0.0)) * 0.75 + success_rate * 0.25
    entry["productivity_score"] = float(round(score, 4))
    entry["last_tick"] = int(getattr(world, "tick", 0))


def _decay_food_site_observations(world) -> None:
    memory = _farm_discovery_map(world)
    if not memory:
        return
    now = int(getattr(world, "tick", 0))
    next_memory = {}
    for key, entry in memory.items():
        if not isinstance(entry, dict):
            continue
        age = max(0, now - int(entry.get("last_tick", now)))
        if age > int(FARM_DISCOVERY_RETENTION_TICKS):
            continue
        score = float(entry.get("productivity_score", 0.0)) * float(FARM_DISCOVERY_DECAY)
        patch_score = float(entry.get("patch_productivity_score", 0.0)) * float(FARM_DISCOVERY_DECAY)
        attempts = int(entry.get("attempt_count", 0))
        successes = int(entry.get("success_count", 0))
        repeat = int(entry.get("repeat_gather_count", 0))
        if score < 0.02 and patch_score < 0.2 and repeat <= 0 and attempts <= 0 and successes <= 0:
            continue
        next_memory[str(key)] = {
            "attempt_count": max(0, attempts - (1 if now % 11 == 0 else 0)),
            "success_count": max(0, successes - (1 if now % 17 == 0 else 0)),
            "repeat_gather_count": max(0, repeat - (1 if now % 13 == 0 else 0)),
            "patch_productivity_score": float(round(max(0.0, patch_score), 4)),
            "productivity_score": float(round(max(0.0, score), 4)),
            "last_tick": int(entry.get("last_tick", now)),
        }
    world.farm_discovery_memory = next_memory


def _farm_candidate_snapshot(world, village, x: int, y: int, *, agent=None) -> dict:
    entry = _farm_discovery_entry(world, int(x), int(y))
    attempts = max(1, int(entry.get("attempt_count", 0)))
    successes = int(entry.get("success_count", 0))
    success_rate = float(successes) / float(attempts)
    repeat_count = int(entry.get("repeat_gather_count", 0))
    patch_score = float(entry.get("patch_productivity_score", 0.0))
    productivity_score = float(entry.get("productivity_score", 0.0))
    nearby_food = int(world._count_food_near(int(x), int(y), radius=4)) if hasattr(world, "_count_food_near") else 0
    near_houses = int(world.count_nearby_houses(int(x), int(y), radius=6)) if hasattr(world, "count_nearby_houses") else 0
    if near_houses <= 0 and isinstance(village, dict):
        center = village.get("center", {}) if isinstance(village.get("center"), dict) else {}
        cx = int(center.get("x", x))
        cy = int(center.get("y", y))
        if abs(int(x) - cx) + abs(int(y) - cy) <= 8:
            near_houses = max(0, int(village.get("houses", 0)))
    near_camp = False
    if hasattr(world, "_nearest_active_camp_raw"):
        try:
            near_camp = isinstance(world._nearest_active_camp_raw(int(x), int(y), max_distance=6), dict)  # type: ignore[attr-defined]
        except Exception:
            near_camp = False
    score = 0.0
    score += min(4.0, float(repeat_count) * 0.5)
    score += float(success_rate) * 3.0
    score += min(3.0, float(patch_score) * 0.1)
    score += min(1.8, float(productivity_score) * 2.0)
    score += min(1.6, float(nearby_food) * 0.2)
    if near_camp:
        score += 1.0
    if near_houses > 0:
        score += min(1.5, float(near_houses) * 0.25)
    local_continuity = 0.0
    if agent is not None and hasattr(agent, "episodic_memory"):
        memory = getattr(agent, "episodic_memory", {})
        events = memory.get("recent_events", []) if isinstance(memory, dict) else []
        now = int(getattr(world, "tick", 0))
        if isinstance(events, list):
            recent_successes = 0
            for ev in events[-24:]:
                if not isinstance(ev, dict):
                    continue
                if str(ev.get("outcome", "")) != "success":
                    continue
                etype = str(ev.get("type", ""))
                if etype not in {"found_resource", "hunger_relief", "farm_work", "farm_harvest"}:
                    continue
                loc = ev.get("location", {})
                if not isinstance(loc, dict):
                    continue
                ex, ey = int(loc.get("x", x)), int(loc.get("y", y))
                if abs(ex - int(x)) + abs(ey - int(y)) > 4:
                    continue
                if now - int(ev.get("tick", now)) > 120:
                    continue
                recent_successes += 1
            local_continuity = float(min(2.0, recent_successes * 0.25))
            score += local_continuity
    needs = village.get("needs", {}) if isinstance(village.get("needs"), dict) else {}
    food_pressure = bool(needs.get("food_urgent") or needs.get("food_low") or needs.get("food_buffer_low"))
    return {
        "repeat_count": int(repeat_count),
        "success_rate": float(round(success_rate, 4)),
        "patch_score": float(round(patch_score, 4)),
        "productivity_score": float(round(productivity_score, 4)),
        "nearby_food": int(nearby_food),
        "near_houses": int(near_houses),
        "near_camp": bool(near_camp),
        "local_continuity": float(round(local_continuity, 4)),
        "score": float(round(score, 4)),
        "food_pressure": bool(food_pressure),
    }


def farm_site_productivity_score(world, x: int, y: int) -> float:
    snap = _farm_candidate_snapshot(world, {"needs": {}}, int(x), int(y))
    return float(snap.get("score", 0.0))


def farm_discovery_snapshot(world, x: int, y: int) -> dict:
    return dict(_farm_candidate_snapshot(world, {"needs": {}}, int(x), int(y)))


def _evaluate_farm_emergence(world, agent, village, pos: Coord, *, snapshot: dict | None = None) -> dict:
    x, y = int(pos[0]), int(pos[1])
    snap = snapshot if isinstance(snapshot, dict) else _farm_candidate_snapshot(world, village, x, y, agent=agent)
    support_ok = bool(snap.get("near_camp", False)) or int(snap.get("near_houses", 0)) >= 1
    core_signal = (
        int(snap.get("repeat_count", 0)) >= int(FARM_MIN_REPEAT_GATHER)
        and float(snap.get("success_rate", 0.0)) >= float(FARM_MIN_SUCCESS_RATE)
        and float(snap.get("score", 0.0)) >= float(FARM_MIN_CANDIDATE_SCORE)
        and support_ok
    )
    if core_signal:
        return {"eligible": True, "reason": "core_signal", "bootstrap": False}
    continuity_signal = (
        support_ok
        and int(snap.get("repeat_count", 0)) >= 1
        and float(snap.get("local_continuity", 0.0)) >= 0.5
        and float(snap.get("score", 0.0)) >= float(FARM_CONTINUITY_CANDIDATE_SCORE)
    )
    if continuity_signal:
        return {"eligible": True, "reason": "continuity_signal", "bootstrap": False}
    if (
        not bool(snap.get("food_pressure", False))
        or not support_ok
    ):
        return {"eligible": False, "reason": "no_support_or_pressure", "bootstrap": False}
    village_id = village.get("id")
    same_village_farms = [
        p for p, plot in world.farm_plots.items()
        if isinstance(plot, dict) and plot.get("village_id") == village_id
    ]
    if same_village_farms:
        return {"eligible": False, "reason": "needs_core_signal", "bootstrap": False}
    if float(getattr(agent, "hunger", 100.0)) <= 24.0:
        return {"eligible": False, "reason": "critical_hunger", "bootstrap": False}
    bootstrap_ok = bool(
        float(getattr(agent, "hunger", 100.0)) <= float(FARM_BOOTSTRAP_MAX_HUNGER)
        and (
            float(snap.get("score", 0.0)) >= float(FARM_BOOTSTRAP_MIN_SCORE)
            or float(snap.get("patch_score", 0.0)) >= 3.0
            or int(snap.get("repeat_count", 0)) >= 1
        )
    )
    if bootstrap_ok:
        return {"eligible": True, "reason": "bootstrap_pressure", "bootstrap": True}
    return {"eligible": False, "reason": "low_signal", "bootstrap": False}


def is_farm_emergence_candidate(world, agent, village, pos: Coord) -> bool:
    x, y = int(pos[0]), int(pos[1])
    snap = _farm_candidate_snapshot(world, village, x, y, agent=agent)
    ev = _evaluate_farm_emergence(world, agent, village, pos, snapshot=snap)
    return bool(ev.get("eligible", False))


def _candidate_exists_near(world, agent, village, center: Coord, *, radius: int = 4) -> bool:
    cx, cy = int(center[0]), int(center[1])
    for x in range(max(0, cx - int(radius)), min(world.width, cx + int(radius) + 1)):
        for y in range(max(0, cy - int(radius)), min(world.height, cy + int(radius) + 1)):
            if abs(x - cx) + abs(y - cy) > int(radius):
                continue
            pos = (int(x), int(y))
            if pos in world.farms or pos in world.farm_plots:
                continue
            if world.tiles[y][x] != "G":
                continue
            if world.is_tile_blocked_by_building(x, y):
                continue
            snap = _farm_candidate_snapshot(world, village, x, y, agent=agent)
            if bool(_evaluate_farm_emergence(world, agent, village, pos, snapshot=snap).get("eligible", False)):
                return True
    return False


def _is_early_productive_farm(plot: dict, now_tick: int) -> bool:
    if not isinstance(plot, dict):
        return False
    created = int(plot.get("created_tick", now_tick))
    age = max(0, int(now_tick) - created)
    productivity = float(plot.get("productivity_score", 0.0))
    return bool(age <= int(EARLY_FARM_WINDOW_TICKS) and productivity >= float(EARLY_FARM_PRODUCTIVE_SCORE))


def farm_task_continuity_bonus(world, agent, task_name: str) -> int:
    if str(task_name) != "farm_cycle":
        return 0
    if float(getattr(agent, "hunger", 100.0)) <= 24.0:
        return 0
    now_tick = int(getattr(world, "tick", 0))
    ax, ay = int(getattr(agent, "x", 0)), int(getattr(agent, "y", 0))
    for (fx, fy), plot in (getattr(world, "farm_plots", {}) or {}).items():
        if not isinstance(plot, dict):
            continue
        if plot.get("village_id") != getattr(agent, "village_id", None):
            continue
        if abs(int(fx) - ax) + abs(int(fy) - ay) > 4:
            continue
        if _is_early_productive_farm(plot, now_tick):
            return int(EARLY_FARM_PERSISTENCE_BONUS_TICKS)
    if hasattr(world, "get_local_practice_bias"):
        try:
            bias = world.get_local_practice_bias(ax, ay)
        except Exception:
            bias = {}
        if float(bias.get("proto_farm_area", 0.0)) >= 0.35:
            return 2
    return 0

def update_farms(world) -> None:
    _decay_food_site_observations(world)
    to_delete = []

    for pos, plot in world.farm_plots.items():
        state = plot.get("state", "prepared")
        created_tick = int(plot.get("created_tick", int(getattr(world, "tick", 0))))
        last_work_tick = int(plot.get("last_work_tick", int(getattr(world, "tick", 0))))
        idle_ticks = int(getattr(world, "tick", 0)) - int(last_work_tick)
        productivity = float(plot.get("productivity_score", 0.0))
        nearby_agents = int(world._count_alive_agents_near(int(pos[0]), int(pos[1]), radius=3)) if hasattr(world, "_count_alive_agents_near") else 0
        if productivity >= float(EARLY_FARM_PRODUCTIVE_SCORE):
            idle_limit = int(FARM_ABANDON_IDLE_TICKS) + int(FARM_PRODUCTIVE_IDLE_BONUS_TICKS)
        else:
            idle_limit = int(FARM_ABANDON_IDLE_TICKS)
        if (
            idle_ticks >= int(idle_limit)
            and productivity <= float(FARM_ABANDON_LOW_PRODUCTIVITY)
            and nearby_agents <= 0
            and state in {"prepared", "planted", "growing"}
        ):
            plot["state"] = "dead"
            state = "dead"

        if state == "planted":
            plot["state"] = "growing"
            plot["growth"] = 1
            continue

        if state == "growing":
            plot["growth"] = plot.get("growth", 0) + 1
            if plot["growth"] >= PLANT_GROW_TICKS:
                plot["state"] = "ripe"
            continue

        if state == "dead":
            to_delete.append(pos)

    for pos in to_delete:
        plot = world.farm_plots.get(pos, {})
        world.farm_plots.pop(pos, None)
        world.farms.discard(pos)
        if hasattr(world, "record_settlement_progression_metric"):
            world.record_settlement_progression_metric("farm_abandoned")
            created_tick = int(plot.get("created_tick", int(getattr(world, "tick", 0)))) if isinstance(plot, dict) else int(getattr(world, "tick", 0))
            if int(getattr(world, "tick", 0)) - created_tick <= int(EARLY_FARM_WINDOW_TICKS):
                world.record_settlement_progression_metric("early_farm_loop_abandonment_count")


def try_build_farm(world, agent) -> bool:
    wallet = _get_build_wallet(world, agent)

    village_id = getattr(agent, "village_id", None)
    village = world.get_village_by_id(village_id)
    if village is None:
        return False
    village_storage = village.get("storage", {}) if isinstance(village.get("storage"), dict) else {}
    have_wood = int(wallet.get("wood", 0))
    need_wood = int(PREPARE_WOOD_COST)
    center = village.get("center", {}) if isinstance(village.get("center"), dict) else {}
    near_center = (
        abs(int(getattr(agent, "x", 0)) - int(center.get("x", 0)))
        + abs(int(getattr(agent, "y", 0)) - int(center.get("y", 0)))
    ) <= 8
    use_village_wood = False
    if have_wood < need_wood:
        if near_center and int(village_storage.get("wood", 0)) >= int(need_wood - have_wood):
            use_village_wood = True
        else:
            return False

    x = agent.x
    y = agent.y
    pos = (x, y)
    snap = _farm_candidate_snapshot(world, village, int(x), int(y), agent=agent)
    support_ok = bool(snap.get("near_camp", False)) or int(snap.get("near_houses", 0)) >= 1
    if support_ok and (int(snap.get("repeat_count", 0)) >= 1 or float(snap.get("score", 0.0)) >= 1.0):
        if hasattr(world, "record_settlement_progression_metric"):
            world.record_settlement_progression_metric("farm_candidate_detected_count")

    primary_center = _primary_farm_center(world, village)
    if primary_center is not None:
        pcx, pcy = primary_center
        has_primary_slot = _has_primary_zone_slot(world, village, village_id, primary_center)
        if has_primary_slot and (abs(x - pcx) + abs(y - pcy) > PRIMARY_FARM_ZONE_RADIUS):
            return False

    if world.tiles[y][x] != "G":
        return False

    if world.is_tile_blocked_by_building(x, y):
        return False

    if pos in world.farms or pos in world.farm_plots:
        return False
    eval_result = _evaluate_farm_emergence(world, agent, village, pos, snapshot=snap)
    if not bool(eval_result.get("eligible", False)):
        if hasattr(world, "record_settlement_progression_metric"):
            world.record_settlement_progression_metric("farm_candidate_rejected_count")
        return False
    if bool(eval_result.get("bootstrap", False)) and hasattr(world, "record_settlement_progression_metric"):
        world.record_settlement_progression_metric("farm_candidate_bootstrap_trigger_count")

    # non attaccato alle case
    for sx, sy in world.get_building_occupied_tiles():
        if abs(sx - x) <= 1 and abs(sy - y) <= 1:
            return False

    same_village_farms = [
        p for p, plot in world.farm_plots.items()
        if plot.get("village_id") == village_id
    ]

    # limite campi per villaggio
    max_farms_for_village = max(2, village["population"] // 2 + village["houses"])
    if len(same_village_farms) >= max_farms_for_village:
        return False

    farm_zone = village.get("farm_zone_center", village["center"])
    fzx = farm_zone["x"]
    fzy = farm_zone["y"]

    if not same_village_farms:
        # primo campo: vicino al centro agricolo del villaggio
        if abs(fzx - x) > 3 or abs(fzy - y) > 3:
            return False
    else:
        # campi successivi: cluster vicino ai campi esistenti
        adjacent_same_village = False
        for fx, fy in same_village_farms:
            if abs(fx - x) <= 1 and abs(fy - y) <= 1:
                adjacent_same_village = True
                break

        if not adjacent_same_village:
            return False

        # non allargare troppo il cluster
        if abs(fzx - x) > 6 or abs(fzy - y) > 6:
            return False

    world.farms.add(pos)
    world.farm_plots[pos] = {
        "x": x,
        "y": y,
        "state": "prepared",
        "growth": 0,
        "village_id": village_id,
        "owner_role": getattr(agent, "role", "npc"),
        "created_tick": int(getattr(world, "tick", 0)),
        "last_work_tick": int(getattr(world, "tick", 0)),
        "work_events": 0,
        "yield_events": 0,
        "yield_total": 0,
        "productivity_score": float(round(farm_site_productivity_score(world, x, y), 4)),
    }

    if use_village_wood:
        take_local = max(0, min(int(wallet.get("wood", 0)), int(need_wood)))
        if take_local > 0:
            wallet["wood"] = int(wallet.get("wood", 0)) - int(take_local)
        rem = int(need_wood - take_local)
        if rem > 0:
            village_storage["wood"] = int(village_storage.get("wood", 0)) - int(rem)
            village["storage"] = village_storage
    else:
        wallet["wood"] = int(wallet.get("wood", 0)) - int(need_wood)
    world.emit_event(
        "farm_created",
        {
            "agent_id": agent.agent_id,
            "x": x,
            "y": y,
            "village_uid": world.resolve_village_uid(village_id),
        },
    )
    if hasattr(world, "record_settlement_progression_metric"):
        world.record_settlement_progression_metric("farm_sites_created")
    return True


def work_farm(world, agent) -> bool:
    if str(getattr(agent, "role", "")) == "farmer" and hasattr(world, "record_task_completion_attempt"):
        world.record_task_completion_attempt(agent, "farm_work")
    pos = (agent.x, agent.y)
    plot = world.farm_plots.get(pos)

    if not plot:
        if str(getattr(agent, "role", "")) == "farmer" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "farm_work", "no_farm_available")
        if str(getattr(agent, "role", "")) == "farmer" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "farmer", "no_target_found")
        return False

    state = plot.get("state", "prepared")
    village_id = plot.get("village_id")
    village = world.get_village_by_id(village_id)

    if state == "prepared":
        plot["state"] = "planted"
        plot["growth"] = 0
        plot["last_work_tick"] = int(getattr(world, "tick", 0))
        plot["work_events"] = int(plot.get("work_events", 0)) + 1
        if hasattr(world, "record_settlement_progression_metric"):
            world.record_settlement_progression_metric("farm_work_events")
            if _is_early_productive_farm(plot, int(getattr(world, "tick", 0))):
                world.record_settlement_progression_metric("early_farm_loop_persistence_ticks")
        if int(plot.get("work_events", 0)) >= 2 and hasattr(world, "record_local_practice"):
            world.record_local_practice(
                "proto_farm_area",
                x=int(plot.get("x", pos[0])),
                y=int(plot.get("y", pos[1])),
                weight=0.8,
                decay_rate=0.0045,
            )
        if str(getattr(agent, "role", "")) == "farmer" and hasattr(world, "record_task_completion_preconditions_met"):
            world.record_task_completion_preconditions_met(agent, "farm_work")
            world.record_task_completion_productive(agent, "farm_work")
        if str(getattr(agent, "role", "")) == "farmer" and hasattr(world, "record_workforce_productive_action"):
            world.record_workforce_productive_action(agent, "farmer", "farm_work")
        return True

    if state == "ripe":
        if str(getattr(agent, "role", "")) == "farmer" and hasattr(world, "record_task_completion_attempt"):
            world.record_task_completion_attempt(agent, "farm_harvest")
        harvest_amount = HARVEST_YIELD
        bonus_chance = HARVEST_BONUS_CHANCE + _storage_farm_bonus_chance(world, village, pos)
        if random.random() < bonus_chance:
            harvest_amount += 1
        space = max(0, getattr(agent, "inventory_space", lambda: 0)())
        if space <= 0:
            if str(getattr(agent, "role", "")) == "farmer" and hasattr(world, "record_task_completion_preconditions_failed"):
                world.record_task_completion_preconditions_failed(agent, "farm_harvest", "inventory_full")
            if str(getattr(agent, "role", "")) == "farmer" and hasattr(world, "record_workforce_block_reason"):
                world.record_workforce_block_reason(agent, "farmer", "no_storage_available")
            return False
        gathered = min(harvest_amount, space)
        agent.inventory["food"] = agent.inventory.get("food", 0) + gathered
        if hasattr(world, "record_agent_food_inventory_acquired"):
            world.record_agent_food_inventory_acquired(agent, amount=int(gathered), source="farm_harvest")
        building_system.record_village_resource_gather(village, "food", amount=gathered)
        if hasattr(world, "record_resource_production"):
            world.record_resource_production("food", gathered)

        plot["state"] = "prepared"
        plot["growth"] = 0
        plot["last_work_tick"] = int(getattr(world, "tick", 0))
        plot["work_events"] = int(plot.get("work_events", 0)) + 1
        first_harvest = int(plot.get("yield_events", 0)) <= 0
        plot["yield_events"] = int(plot.get("yield_events", 0)) + 1
        plot["yield_total"] = int(plot.get("yield_total", 0)) + int(gathered)
        productivity = float(plot.get("productivity_score", 0.0)) * 0.8 + (float(gathered) * 0.2)
        plot["productivity_score"] = float(round(productivity, 4))
        record_food_site_observation(world, int(pos[0]), int(pos[1]), success=True, amount=int(gathered))
        if hasattr(world, "record_settlement_progression_metric"):
            world.record_settlement_progression_metric("farm_work_events")
            world.record_settlement_progression_metric("farm_yield_events")
            world.record_settlement_progression_metric("farm_yield_units_total", int(gathered))
            if first_harvest:
                world.record_settlement_progression_metric("first_harvest_after_farm_creation_count")
            if _is_early_productive_farm(plot, int(getattr(world, "tick", 0))):
                world.record_settlement_progression_metric("early_farm_loop_persistence_ticks")
        if hasattr(world, "record_local_practice"):
            world.record_local_practice(
                "proto_farm_area",
                x=int(plot.get("x", pos[0])),
                y=int(plot.get("y", pos[1])),
                weight=1.2,
                decay_rate=0.0045,
            )
        world.emit_event(
            "resource_harvested",
            {
                "agent_id": agent.agent_id,
                "resource": "food",
                "amount": gathered,
                "source": "farm",
                "x": pos[0],
                "y": pos[1],
                "village_uid": world.resolve_village_uid(getattr(agent, "village_id", None)),
            },
        )
        if str(getattr(agent, "role", "")) == "farmer" and hasattr(world, "record_task_completion_preconditions_met"):
            world.record_task_completion_preconditions_met(agent, "farm_harvest")
            world.record_task_completion_productive(agent, "farm_harvest")
        if str(getattr(agent, "role", "")) == "farmer" and hasattr(world, "record_workforce_productive_action"):
            world.record_workforce_productive_action(agent, "farmer", "farm_harvest")
        return True

    if str(getattr(agent, "role", "")) == "farmer" and hasattr(world, "record_task_completion_preconditions_failed"):
        world.record_task_completion_preconditions_failed(agent, "farm_work", "farm_not_ready")
    if str(getattr(agent, "role", "")) == "farmer" and hasattr(world, "record_workforce_block_reason"):
        world.record_workforce_block_reason(agent, "farmer", "waiting_on_delivery")
    return False


def haul_harvest(world, agent) -> bool:
    """
    Minimal logistics harvest:
    hauler raccoglie dal campo maturo nel proprio inventario
    invece di depositare direttamente nello storage villaggio.
    """
    if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_attempt"):
        world.record_task_completion_attempt(agent, "farm_haul_harvest")
    pos = (agent.x, agent.y)
    plot = world.farm_plots.get(pos)
    if not plot:
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "farm_haul_harvest", "no_farm_available")
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "hauler", "no_target_found")
        return False

    if plot.get("state") != "ripe":
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "farm_haul_harvest", "farm_not_ready")
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "hauler", "waiting_on_delivery")
        return False

    village = world.get_village_by_id(getattr(agent, "village_id", None))
    harvest_amount = HARVEST_YIELD
    bonus_chance = HARVEST_BONUS_CHANCE + _storage_farm_bonus_chance(world, village, pos)
    if random.random() < bonus_chance:
        harvest_amount += 1
    space = max(0, getattr(agent, "inventory_space", lambda: 0)())
    if space <= 0:
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_failed"):
            world.record_task_completion_preconditions_failed(agent, "farm_haul_harvest", "inventory_empty")
        if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_block_reason"):
            world.record_workforce_block_reason(agent, "hauler", "no_storage_available")
        return False
    gathered = min(harvest_amount, space)
    agent.inventory["food"] = agent.inventory.get("food", 0) + gathered
    if hasattr(world, "record_agent_food_inventory_acquired"):
        world.record_agent_food_inventory_acquired(agent, amount=int(gathered), source="farm_haul_harvest")
    building_system.record_village_resource_gather(village, "food", amount=gathered)
    if hasattr(world, "record_resource_production"):
        world.record_resource_production("food", gathered)
    plot["state"] = "prepared"
    plot["growth"] = 0
    world.emit_event(
        "resource_harvested",
        {
            "agent_id": agent.agent_id,
            "resource": "food",
            "amount": gathered,
            "source": "farm_haul",
            "x": pos[0],
            "y": pos[1],
            "village_uid": world.resolve_village_uid(getattr(agent, "village_id", None)),
        },
    )
    if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_task_completion_preconditions_met"):
        world.record_task_completion_preconditions_met(agent, "farm_haul_harvest")
        world.record_task_completion_productive(agent, "farm_haul_harvest")
    if str(getattr(agent, "role", "")) == "hauler" and hasattr(world, "record_workforce_productive_action"):
        world.record_workforce_productive_action(agent, "hauler", "farm_haul_harvest")
    return True


def _storage_farm_bonus_chance(world, village, farm_pos: Coord) -> float:
    """
    Storage as logistic hub:
    farms near storage get a +10% baseline bonus, plus a small distance factor.
    """
    if village is None:
        return 0.0
    sp = village.get("storage_pos")
    if not sp:
        return 0.0
    sx, sy = sp["x"], sp["y"]
    if (sx, sy) not in getattr(world, "storage_buildings", set()):
        return 0.0
    fx, fy = farm_pos
    d = abs(fx - sx) + abs(fy - sy)
    if d > STORAGE_NEAR_FARM_RADIUS:
        return 0.0
    # +10% in radius, with up to +10% extra for very close farms.
    return 0.10 + max(0.0, (STORAGE_NEAR_FARM_RADIUS - d) * 0.02)


def _primary_farm_center(world, village) -> Coord | None:
    if village is None:
        return None
    sp = village.get("storage_pos")
    if sp:
        sx, sy = sp.get("x"), sp.get("y")
        if (sx, sy) in getattr(world, "storage_buildings", set()):
            return (sx, sy)
    zone = village.get("farm_zone_center", village.get("center"))
    if not zone:
        return None
    zx = zone.get("x")
    zy = zone.get("y")
    if zx is None or zy is None:
        return None
    return (zx, zy)


def _is_valid_primary_slot(world, village, village_id, x: int, y: int) -> bool:
    pos = (x, y)
    if not (0 <= x < world.width and 0 <= y < world.height):
        return False
    if world.tiles[y][x] != "G":
        return False
    if not world.can_build_at(x, y):
        return False
    if pos in world.farms or pos in world.farm_plots:
        return False
    for sx, sy in world.get_building_occupied_tiles():
        if abs(sx - x) <= 1 and abs(sy - y) <= 1:
            return False
    same_village_farms = [
        p for p, plot in world.farm_plots.items()
        if plot.get("village_id") == village_id
    ]
    if not same_village_farms:
        return True
    return any(abs(fx - x) <= 1 and abs(fy - y) <= 1 for fx, fy in same_village_farms)


def _has_primary_zone_slot(world, village, village_id, center: Coord) -> bool:
    cx, cy = center
    for x in range(max(0, cx - PRIMARY_FARM_ZONE_RADIUS), min(world.width, cx + PRIMARY_FARM_ZONE_RADIUS + 1)):
        for y in range(max(0, cy - PRIMARY_FARM_ZONE_RADIUS), min(world.height, cy + PRIMARY_FARM_ZONE_RADIUS + 1)):
            if abs(x - cx) + abs(y - cy) > PRIMARY_FARM_ZONE_RADIUS:
                continue
            if _is_valid_primary_slot(world, village, village_id, x, y):
                return True
    return False


def is_farmer_task_viable(world, agent) -> bool:
    village_id = getattr(agent, "village_id", None)
    village = world.get_village_by_id(village_id)
    if village is None:
        return False

    # Village-relevant existing farms are the strongest validity signal.
    for _, plot in getattr(world, "farm_plots", {}).items():
        if not isinstance(plot, dict):
            continue
        if plot.get("village_id") != village_id:
            continue
        state = str(plot.get("state", "prepared"))
        if state in {"prepared", "ripe", "planted", "growing"}:
            return True

    # If no farm exists yet, allow farmer task only when a first-slot build is plausible.
    center = _primary_farm_center(world, village)
    if center is None:
        return False
    if not bool(_has_primary_zone_slot(world, village, village_id, center)):
        return False

    if is_farm_emergence_candidate(world, agent, village, (int(getattr(agent, "x", 0)), int(getattr(agent, "y", 0)))):
        return True
    center = _primary_farm_center(world, village)
    if center is not None and _candidate_exists_near(world, agent, village, center, radius=4):
        return True

    village_storage = village.get("storage", {}) if isinstance(village.get("storage"), dict) else {}
    available_wood = int(agent.inventory.get("wood", 0)) + int(village_storage.get("wood", 0))
    if available_wood >= PREPARE_WOOD_COST:
        return True

    needs = village.get("needs", {}) if isinstance(village.get("needs"), dict) else {}
    food_pressure = bool(needs.get("food_urgent") or needs.get("food_low") or needs.get("food_buffer_low"))
    if not food_pressure:
        return False

    # Under sustained food pressure, first-farm bootstrap is viable if there is
    # reachable local wood supply to collect for plot preparation.
    ax = int(getattr(agent, "x", 0))
    ay = int(getattr(agent, "y", 0))
    search_radius = 12
    for wx, wy in getattr(world, "wood", set()):
        if abs(int(wx) - ax) + abs(int(wy) - ay) > search_radius:
            continue
        if not world.is_walkable(int(wx), int(wy)):
            continue
        return True
    return False
