from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from world import World


CORE_ROLES = ("farmer", "builder", "forager", "hauler")


def _set_role(world: "World", agent, role: str, reason: str) -> None:
    world.set_agent_role(agent, role, reason=reason)


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
            ),
            reverse=True,
        )

        # Agent dataclass is unhashable, track stable object ids instead.
        assigned_ids = set()

        def take(n: int, role: str) -> None:
            count = 0
            for a in workers_sorted:
                aid = id(a)
                if aid in assigned_ids:
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
        current_farmers = sum(1 for a in workers_sorted if getattr(a, "role", "") == "farmer")

        # resto guard / generic worker?
        # per ora li teniamo farmer se c'è bisogno, altrimenti hauler
        for a in workers_sorted:
            aid = id(a)
            if aid in assigned_ids:
                continue
            if needs.get("food_low") and current_farmers < farmer_cap:
                _set_role(world, a, "farmer", reason="food_priority")
                current_farmers += 1
            else:
                _set_role(world, a, "hauler", reason="fallback_logistics")
            assigned_ids.add(aid)
