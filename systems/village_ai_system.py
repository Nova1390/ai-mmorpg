from __future__ import annotations

from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from world import World


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

        village["metrics"] = {
            "population": pop,
            "avg_hunger": round(avg_hunger, 2),
            "housing_capacity": housing_capacity,
            "food_stock": food_stock,
            "food_buffer_target": food_buffer_target,
            "food_surplus_target": food_surplus_target,
            "wood_stock": wood_stock,
            "stone_stock": stone_stock,
            "active_farms": active_farms,
            "ripe_farms": ripe_farms,
            "storage_exists": storage_exists,
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

        # If no active leader, keep village governance moving with deterministic baseline.
        if village.get("leader_id") is None:
            village["priority"] = baseline_priority
            village["strategy"] = _priority_to_strategy(baseline_priority)
        else:
            village["priority"] = village.get("priority") or baseline_priority
            village["strategy"] = village.get("strategy") or _priority_to_strategy(village["priority"])


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
