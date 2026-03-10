from __future__ import annotations

from agent import Agent
import systems.role_system as role_system
from world import World


def _world_with_workers(num_workers: int = 8) -> tuple[World, dict]:
    world = World(width=40, height=40, num_agents=0, seed=21, llm_enabled=False)
    world.tiles = [["G" for _ in range(world.width)] for _ in range(world.height)]
    village = {
        "id": 1,
        "village_uid": "v-000001",
        "center": {"x": 10, "y": 10},
        "houses": 6,
        "population": num_workers,
        "storage": {"food": 10, "wood": 10, "stone": 10},
        "storage_pos": {"x": 10, "y": 10},
        "tier": 2,
        "needs": {},
        "metrics": {},
    }
    world.villages = [village]
    agents = []
    for i in range(num_workers):
        a = Agent(x=10 + (i % 3), y=10 + (i // 3), brain=None, is_player=False, player_id=None)
        a.village_id = 1
        a.role = "npc"
        agents.append(a)
    world.agents = agents
    return world, village


def test_food_shortage_increases_food_worker_target() -> None:
    world, village = _world_with_workers(10)
    base = role_system.compute_target_workforce_mix(world, village)
    village["needs"] = {"food_urgent": True}
    pressured = role_system.compute_target_workforce_mix(world, village)
    assert int(pressured["farmer"]) + int(pressured["forager"]) >= int(base["farmer"]) + int(base["forager"])


def test_material_shortage_increases_material_or_logistics_targets() -> None:
    world, village = _world_with_workers(10)
    base = role_system.compute_target_workforce_mix(world, village)
    village["needs"] = {"need_materials": True}
    pressured = role_system.compute_target_workforce_mix(world, village)
    assert int(pressured["hauler"]) >= int(base["hauler"])
    assert int(pressured["material_pressure"]) >= int(base["material_pressure"])


def test_construction_pressure_increases_builder_and_hauler_targets() -> None:
    world, village = _world_with_workers(10)
    base = role_system.compute_target_workforce_mix(world, village)
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
    }
    pressured = role_system.compute_target_workforce_mix(world, village)
    assert int(pressured["builder"]) >= int(base["builder"])
    assert int(pressured["hauler"]) >= int(base["hauler"])


def test_mature_village_can_target_specialists_when_assets_and_demand_exist() -> None:
    world, village = _world_with_workers(10)
    village["storage"] = {"food": 12, "wood": 8, "stone": 0}
    village["needs"] = {"need_materials": True}
    world.buildings["b-mine"] = {
        "building_id": "b-mine",
        "type": "mine",
        "x": 12,
        "y": 10,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "active",
        "connected_to_road": True,
    }
    targets = role_system.compute_specialist_targets_for_village(world, village)
    assert int(targets["miner"]) > 0


def test_role_allocation_prefers_residents_and_attached_agents() -> None:
    world, village = _world_with_workers(4)
    village["needs"] = {"food_urgent": True}
    resident = world.agents[0]
    resident.village_affiliation_status = "resident"
    resident.home_village_uid = "v-000001"
    resident.primary_village_uid = "v-000001"
    attached = world.agents[1]
    attached.village_affiliation_status = "attached"
    attached.primary_village_uid = "v-000001"
    outsider_a = world.agents[2]
    outsider_a.village_affiliation_status = "transient"
    outsider_a.primary_village_uid = "v-999999"
    outsider_b = world.agents[3]
    outsider_b.village_affiliation_status = "unaffiliated"
    outsider_b.primary_village_uid = None

    role_system.assign_village_roles(world)

    assert resident.role == "farmer"
    assert attached.role == "farmer"


def test_reallocation_is_deterministic_and_bounded_by_interval() -> None:
    world_a, village_a = _world_with_workers(8)
    world_b, village_b = _world_with_workers(8)
    village_a["needs"] = {"food_urgent": True}
    village_b["needs"] = {"food_urgent": True}

    role_system.assign_village_roles(world_a)
    role_system.assign_village_roles(world_b)
    initial_farmers = sum(1 for a in world_a.agents if a.role == "farmer")

    village_a["needs"] = {"food_surplus": True}
    village_b["needs"] = {"food_surplus": True}
    for step in range(1, role_system.WORKFORCE_REALLOCATION_INTERVAL_TICKS):
        world_a.tick = step
        world_b.tick = step
        role_system.assign_village_roles(world_a)
        role_system.assign_village_roles(world_b)
        assert sum(1 for a in world_a.agents if a.role == "farmer") == initial_farmers

    world_a.tick = role_system.WORKFORCE_REALLOCATION_INTERVAL_TICKS
    world_b.tick = role_system.WORKFORCE_REALLOCATION_INTERVAL_TICKS
    role_system.assign_village_roles(world_a)
    role_system.assign_village_roles(world_b)

    roles_a = [a.role for a in sorted(world_a.agents, key=lambda x: x.agent_id)]
    roles_b = [a.role for a in sorted(world_b.agents, key=lambda x: x.agent_id)]
    assert roles_a == roles_b


def test_role_allocation_prefers_recently_productive_same_role_continuity(monkeypatch) -> None:
    world, village = _world_with_workers(3)
    village["needs"] = {}
    world.tick = 100

    def _fixed_mix(_world, _village):
        return {
            "farmer": 0,
            "builder": 1,
            "hauler": 0,
            "forager": 0,
            "food_pressure": 0,
            "construction_pressure": 0,
            "logistics_pressure": 0,
            "material_pressure": 0,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)

    continuity_builder = world.agents[0]
    continuity_builder.role = "builder"
    continuity_builder.hunger = 30
    continuity_builder.workforce_last_productive_tick_by_role = {"builder": 99}

    hungry_npc = world.agents[1]
    hungry_npc.role = "npc"
    hungry_npc.hunger = 95

    world.agents[2].role = "npc"
    world.agents[2].hunger = 20

    role_system.assign_village_roles(world)
    builders = [a for a in world.agents if a.role == "builder"]
    assert len(builders) == 1
    assert builders[0] is continuity_builder


def test_live_under_construction_demand_applies_builder_hauler_role_floor_with_cached_targets() -> None:
    world, village = _world_with_workers(6)
    world.tick = 1
    village["workforce_rebalance_state"] = {
        "last_reallocation_tick": int(world.tick),
        "cached_targets": {"farmer": 4, "builder": 0, "hauler": 0, "forager": 2},
    }
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
    }

    role_system.assign_village_roles(world)

    assert sum(1 for a in world.agents if a.role == "builder") >= 1
    assert sum(1 for a in world.agents if a.role == "hauler") >= 1


def test_builder_wait_signal_boosts_hauler_engagement_target() -> None:
    world, village = _world_with_workers(8)
    world.tick = 1
    village["workforce_rebalance_state"] = {
        "last_reallocation_tick": int(world.tick),
        "cached_targets": {"farmer": 3, "builder": 0, "hauler": 0, "forager": 1},
    }
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "house",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
        "builder_waiting_tick": int(world.tick),
    }

    role_system.assign_village_roles(world)

    assert sum(1 for a in world.agents if a.role == "hauler") >= 2


def test_support_roles_release_when_live_site_invalidated() -> None:
    world, village = _world_with_workers(6)
    world.tick = 1
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
        "builder_waiting_tick": int(world.tick),
    }
    role_system.assign_village_roles(world)
    assert sum(1 for a in world.agents if a.role == "builder") >= 1

    # Invalidate site and advance beyond hold/reallocation windows.
    world.buildings.pop("b-site", None)
    village["needs"] = {"food_urgent": True}
    world.tick = int(role_system.ROLE_MIN_HOLD_TICKS + role_system.WORKFORCE_REALLOCATION_INTERVAL_TICKS + 5)
    role_system.assign_village_roles(world)

    assert sum(1 for a in world.agents if a.role == "builder") == 0


def test_assignment_persistence_tuning_does_not_fake_delivery_or_progress() -> None:
    world, village = _world_with_workers(6)
    world.tick = 1
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_buffer": {"wood": 0, "stone": 0, "food": 0},
        "construction_progress": 0,
        "construction_required_work": 6,
        "construction_last_demand_tick": int(world.tick),
        "builder_waiting_tick": int(world.tick),
    }
    before_progress = int(world.buildings["b-site"]["construction_progress"])
    logistics_before = int(village.get("logistics_metrics", {}).get("construction_deliveries_count", 0))

    role_system.assign_village_roles(world)

    assert int(world.buildings["b-site"]["construction_progress"]) == before_progress
    assert int(village.get("logistics_metrics", {}).get("construction_deliveries_count", 0)) == logistics_before


def test_live_demand_support_assignment_diagnostics_present_with_floor_request() -> None:
    world, village = _world_with_workers(6)
    world.tick = 10
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
        "builder_waiting_tick": int(world.tick),
    }

    role_system.assign_village_roles(world)
    diag = village.get("metrics", {}).get("support_role_assignment_diagnostics", {})
    assert isinstance(diag, dict)
    assert bool(diag.get("live_demand", False)) is True
    roles = diag.get("roles", {})
    assert isinstance(roles, dict)
    assert bool((roles.get("builder", {}) or {}).get("floor_requested", False)) is True
    assert bool((roles.get("hauler", {}) or {}).get("floor_requested", False)) is True


def test_support_assignment_diagnostics_capture_candidate_and_selection_counts() -> None:
    world, village = _world_with_workers(6)
    world.tick = 10
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "house",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
    }

    role_system.assign_village_roles(world)
    diag = village.get("metrics", {}).get("support_role_assignment_diagnostics", {})
    builder = (((diag.get("roles", {}) or {}).get("builder", {})) if isinstance(diag, dict) else {})
    assert int(builder.get("candidates_total", 0)) >= int(builder.get("candidates_eligible", 0))
    assert int(builder.get("selected_count", 0)) <= int(builder.get("candidates_eligible", 0))
    selected_ids = builder.get("selected_agent_ids", [])
    assert isinstance(selected_ids, list)
    assert len(selected_ids) <= 6


def test_support_assignment_diagnostics_record_filtered_reasons_deterministically(monkeypatch) -> None:
    world, village = _world_with_workers(6)
    world.tick = 5
    def _fixed_mix(_world, _village):
        return {
            "farmer": 0,
            "builder": 1,
            "hauler": 0,
            "forager": 0,
            "food_pressure": 0,
            "construction_pressure": 1,
            "logistics_pressure": 0,
            "material_pressure": 0,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
    }
    # Force a deterministic hold block for one worker.
    blocked = world.agents[0]
    blocked.role = "hauler"
    blocked.hunger = 99.0
    blocked.role_hold_until_tick = int(world.tick) + 100

    role_system.assign_village_roles(world)
    diag = village.get("metrics", {}).get("support_role_assignment_diagnostics", {})
    builder = (((diag.get("roles", {}) or {}).get("builder", {})) if isinstance(diag, dict) else {})
    reasons = builder.get("filter_reasons", {}) if isinstance(builder.get("filter_reasons", {}), dict) else {}
    # Depending on safe-floor override, the hold-blocked candidate may be either
    # recorded as filtered or admitted via one bounded override.
    assert int(reasons.get("role_hold_block", 0)) >= 1 or bool(builder.get("floor_satisfied", False)) is True


def test_live_demand_can_override_role_hold_for_one_builder_in_safe_conditions(monkeypatch) -> None:
    world, village = _world_with_workers(4)
    world.tick = 8

    def _fixed_mix(_world, _village):
        return {
            "farmer": 0,
            "builder": 1,
            "hauler": 0,
            "forager": 0,
            "food_pressure": 0,
            "construction_pressure": 1,
            "logistics_pressure": 0,
            "material_pressure": 0,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["storage"]["food"] = 20
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
    }
    for a in world.agents:
        a.role = "farmer"
        a.hunger = 80.0
        a.role_hold_until_tick = int(world.tick) + 50

    role_system.assign_village_roles(world)
    assert sum(1 for a in world.agents if a.role == "builder") >= 1
    diag = village.get("metrics", {}).get("support_role_assignment_diagnostics", {})
    builder = ((diag.get("roles", {}) or {}).get("builder", {}) if isinstance(diag, dict) else {})
    assert bool(builder.get("floor_requested", False)) is True
    assert bool(builder.get("floor_satisfied", False)) is True


def test_live_demand_requests_and_assigns_hauler_floor_in_small_safe_village(monkeypatch) -> None:
    world, village = _world_with_workers(2)
    world.tick = 8

    def _fixed_mix(_world, _village):
        return {
            "farmer": 0,
            "builder": 0,
            "hauler": 0,
            "forager": 0,
            "food_pressure": 0,
            "construction_pressure": 1,
            "logistics_pressure": 1,
            "material_pressure": 1,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["storage"]["food"] = 20
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "house",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
    }

    role_system.assign_village_roles(world)
    diag = village.get("metrics", {}).get("support_role_assignment_diagnostics", {})
    roles = (diag.get("roles", {}) if isinstance(diag, dict) else {})
    hauler = roles.get("hauler", {}) if isinstance(roles, dict) else {}
    assert bool(hauler.get("floor_requested", False)) is True
    assert int(hauler.get("floor_required", 0)) >= 1
    assert sum(1 for a in world.agents if a.role == "hauler") >= 1


def test_support_floor_override_does_not_apply_in_true_crisis(monkeypatch) -> None:
    world, village = _world_with_workers(4)
    world.tick = 8

    def _fixed_mix(_world, _village):
        return {
            "farmer": 0,
            "builder": 1,
            "hauler": 1,
            "forager": 0,
            "food_pressure": 2,
            "construction_pressure": 1,
            "logistics_pressure": 1,
            "material_pressure": 1,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["needs"] = {"food_urgent": True, "food_buffer_critical": True}
    village["storage"]["food"] = 0
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
    }
    for a in world.agents:
        a.role = "farmer"
        a.hunger = 20.0
        a.role_hold_until_tick = int(world.tick) + 50

    role_system.assign_village_roles(world)
    diag = village.get("metrics", {}).get("support_role_assignment_diagnostics", {})
    roles = (diag.get("roles", {}) if isinstance(diag, dict) else {})
    builder = roles.get("builder", {}) if isinstance(roles, dict) else {}
    reasons = builder.get("filter_reasons", {}) if isinstance(builder.get("filter_reasons", {}), dict) else {}
    assert bool(builder.get("floor_requested", False)) is True
    assert bool(builder.get("floor_satisfied", False)) is False
    assert int(reasons.get("food_base_reserved", 0)) >= 1


def test_moderate_hunger_live_demand_relaxes_food_base_for_builder_floor(monkeypatch) -> None:
    world, village = _world_with_workers(3)
    world.tick = 12

    def _fixed_mix(_world, _village):
        return {
            "farmer": 0,
            "builder": 1,
            "hauler": 0,
            "forager": 0,
            "food_pressure": 1,
            "construction_pressure": 1,
            "logistics_pressure": 0,
            "material_pressure": 0,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["needs"] = {"food_urgent": False, "food_buffer_critical": False}
    village["storage"]["food"] = 6
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
    }
    for idx, a in enumerate(world.agents):
        if idx == 0:
            a.role = "hauler"
            a.role_hold_until_tick = int(world.tick) + 50
        else:
            a.role = "farmer"
            a.role_hold_until_tick = -1
        a.hunger = 52.0

    role_system.assign_village_roles(world)
    diag = village.get("metrics", {}).get("support_role_assignment_diagnostics", {})
    builder = (((diag.get("roles", {}) or {}).get("builder", {})) if isinstance(diag, dict) else {})
    reasons = builder.get("filter_reasons", {}) if isinstance(builder.get("filter_reasons", {}), dict) else {}
    assert bool(builder.get("floor_requested", False)) is True
    assert bool(builder.get("floor_satisfied", False)) is True
    assert int(builder.get("candidates_eligible", 0)) >= 1
    assert int(reasons.get("food_base_relaxed_for_support_role", 0)) >= 1


def test_live_demand_builder_wait_signal_can_trigger_food_base_relaxation(monkeypatch) -> None:
    world, village = _world_with_workers(3)
    world.tick = 240

    def _fixed_mix(_world, _village):
        return {
            "farmer": 0,
            "builder": 1,
            "hauler": 0,
            "forager": 0,
            "food_pressure": 1,
            "construction_pressure": 1,
            "logistics_pressure": 0,
            "material_pressure": 0,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["needs"] = {"food_urgent": False, "food_buffer_critical": False}
    village["storage"]["food"] = 6
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        # stale heartbeat on purpose: trigger should come from builder_wait signal.
        "construction_last_demand_tick": int(world.tick) - (role_system.LIVE_CONSTRUCTION_SIGNAL_WINDOW_TICKS + 5),
        "builder_waiting_tick": int(world.tick),
    }
    for idx, a in enumerate(world.agents):
        if idx == 0:
            a.role = "hauler"
            a.role_hold_until_tick = int(world.tick) + 60
        else:
            a.role = "farmer"
            a.role_hold_until_tick = -1
        a.hunger = 50.0

    role_system.assign_village_roles(world)
    diag = village.get("metrics", {}).get("support_role_assignment_diagnostics", {})
    builder = (((diag.get("roles", {}) or {}).get("builder", {})) if isinstance(diag, dict) else {})
    reasons = builder.get("filter_reasons", {}) if isinstance(builder.get("filter_reasons", {}), dict) else {}
    assert bool(builder.get("floor_requested", False)) is True
    assert int(builder.get("candidates_eligible", 0)) >= 1
    assert int(reasons.get("food_base_relaxed_for_support_role", 0)) >= 1


def test_food_base_relaxation_does_not_happen_in_true_crisis(monkeypatch) -> None:
    world, village = _world_with_workers(3)
    world.tick = 12

    def _fixed_mix(_world, _village):
        return {
            "farmer": 2,
            "builder": 1,
            "hauler": 1,
            "forager": 0,
            "food_pressure": 2,
            "construction_pressure": 1,
            "logistics_pressure": 1,
            "material_pressure": 1,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["needs"] = {"food_urgent": True, "food_buffer_critical": True}
    village["storage"]["food"] = 0
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
    }
    for a in world.agents:
        a.role = "farmer"
        a.hunger = 18.0
        a.role_hold_until_tick = -1

    role_system.assign_village_roles(world)
    diag = village.get("metrics", {}).get("support_role_assignment_diagnostics", {})
    roles = (diag.get("roles", {}) if isinstance(diag, dict) else {})
    for role_name in ("builder", "hauler"):
        role_diag = roles.get(role_name, {}) if isinstance(roles, dict) else {}
        reasons = role_diag.get("filter_reasons", {}) if isinstance(role_diag.get("filter_reasons", {}), dict) else {}
        assert int(reasons.get("food_base_relaxed_for_support_role", 0)) == 0


def test_food_base_relaxation_allows_at_most_one_candidate_per_role(monkeypatch) -> None:
    world, village = _world_with_workers(6)
    world.tick = 12

    def _fixed_mix(_world, _village):
        return {
            "farmer": 3,
            "builder": 1,
            "hauler": 1,
            "forager": 0,
            "food_pressure": 1,
            "construction_pressure": 1,
            "logistics_pressure": 1,
            "material_pressure": 1,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["needs"] = {"food_urgent": False, "food_buffer_critical": False}
    village["storage"]["food"] = 12
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
    }
    for a in world.agents:
        a.role = "farmer"
        a.hunger = 55.0
        a.role_hold_until_tick = -1

    role_system.assign_village_roles(world)
    diag = village.get("metrics", {}).get("support_role_assignment_diagnostics", {})
    roles = (diag.get("roles", {}) if isinstance(diag, dict) else {})
    for role_name in ("builder", "hauler"):
        role_diag = roles.get(role_name, {}) if isinstance(roles, dict) else {}
        reasons = role_diag.get("filter_reasons", {}) if isinstance(role_diag.get("filter_reasons", {}), dict) else {}
        assert int(reasons.get("food_base_relaxed_for_support_role", 0)) <= 1


def test_food_base_minimum_roles_remain_preserved_after_relaxation(monkeypatch) -> None:
    world, village = _world_with_workers(6)
    world.tick = 12

    def _fixed_mix(_world, _village):
        return {
            "farmer": 3,
            "builder": 1,
            "hauler": 1,
            "forager": 0,
            "food_pressure": 1,
            "construction_pressure": 1,
            "logistics_pressure": 1,
            "material_pressure": 1,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["needs"] = {"food_urgent": False, "food_buffer_critical": False}
    village["storage"]["food"] = 12
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
    }
    for a in world.agents:
        a.role = "farmer"
        a.hunger = 55.0
        a.role_hold_until_tick = -1

    role_system.assign_village_roles(world)
    food_roles = sum(1 for a in world.agents if a.role in {"farmer", "forager"})
    assert food_roles >= max(1, len(world.agents) // 3)


def test_relaxation_branch_entry_counters_increment_for_live_recent_signal(monkeypatch) -> None:
    world, village = _world_with_workers(4)
    world.tick = 20

    def _fixed_mix(_world, _village):
        return {
            "farmer": 0,
            "builder": 1,
            "hauler": 1,
            "forager": 0,
            "food_pressure": 1,
            "construction_pressure": 1,
            "logistics_pressure": 1,
            "material_pressure": 1,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["needs"] = {"food_urgent": False, "food_buffer_critical": False}
    village["storage"]["food"] = 10
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
    }

    role_system.assign_village_roles(world)
    diag = village.get("metrics", {}).get("support_role_relaxation_diagnostics", {})
    roles = diag.get("roles", {}) if isinstance(diag, dict) else {}
    for role_name in ("builder", "hauler"):
        rd = roles.get(role_name, {}) if isinstance(roles, dict) else {}
        assert int(rd.get("live_demand_context_seen", 0)) >= 1
        assert int(rd.get("support_signal_recent_seen", 0)) >= 1


def test_relaxation_branch_records_true_crisis_short_circuit(monkeypatch) -> None:
    world, village = _world_with_workers(4)
    world.tick = 20

    def _fixed_mix(_world, _village):
        return {
            "farmer": 0,
            "builder": 1,
            "hauler": 1,
            "forager": 0,
            "food_pressure": 2,
            "construction_pressure": 1,
            "logistics_pressure": 1,
            "material_pressure": 1,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["needs"] = {"food_urgent": True, "food_buffer_critical": True}
    village["storage"]["food"] = 0
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
    }
    for a in world.agents:
        a.hunger = 15.0
        a.role = "farmer"

    role_system.assign_village_roles(world)
    diag = village.get("metrics", {}).get("support_role_relaxation_diagnostics", {})
    roles = diag.get("roles", {}) if isinstance(diag, dict) else {}
    builder = roles.get("builder", {}) if isinstance(roles, dict) else {}
    reasons = builder.get("short_circuit_reasons", {}) if isinstance(builder.get("short_circuit_reasons", {}), dict) else {}
    assert int(builder.get("true_survival_crisis_seen", 0)) >= 1
    assert int(reasons.get("true_survival_crisis", 0)) >= 1


def test_relaxation_budget_granted_and_consumed_counters_update(monkeypatch) -> None:
    world, village = _world_with_workers(3)
    world.tick = 12

    def _fixed_mix(_world, _village):
        return {
            "farmer": 0,
            "builder": 1,
            "hauler": 0,
            "forager": 0,
            "food_pressure": 1,
            "construction_pressure": 1,
            "logistics_pressure": 0,
            "material_pressure": 0,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["needs"] = {"food_urgent": False, "food_buffer_critical": False}
    village["storage"]["food"] = 6
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
    }
    for idx, a in enumerate(world.agents):
        if idx == 0:
            a.role = "hauler"
            a.role_hold_until_tick = int(world.tick) + 50
        else:
            a.role = "farmer"
            a.role_hold_until_tick = -1
        a.hunger = 52.0

    role_system.assign_village_roles(world)
    diag = village.get("metrics", {}).get("support_role_relaxation_diagnostics", {})
    roles = diag.get("roles", {}) if isinstance(diag, dict) else {}
    builder = roles.get("builder", {}) if isinstance(roles, dict) else {}
    assert int(builder.get("food_base_relaxation_budget_granted", 0)) >= 1
    assert int(builder.get("food_base_relaxation_budget_consumed", 0)) >= 1


def test_hold_override_branch_counters_update_deterministically(monkeypatch) -> None:
    world, village = _world_with_workers(4)
    world.tick = 8

    def _fixed_mix(_world, _village):
        return {
            "farmer": 0,
            "builder": 1,
            "hauler": 0,
            "forager": 0,
            "food_pressure": 0,
            "construction_pressure": 1,
            "logistics_pressure": 0,
            "material_pressure": 0,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["storage"]["food"] = 20
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
    }
    for a in world.agents:
        a.role = "farmer"
        a.hunger = 70.0
        a.role_hold_until_tick = int(world.tick) + 50

    role_system.assign_village_roles(world)
    diag = village.get("metrics", {}).get("support_role_relaxation_diagnostics", {})
    roles = diag.get("roles", {}) if isinstance(diag, dict) else {}
    builder = roles.get("builder", {}) if isinstance(roles, dict) else {}
    assert int(builder.get("hold_override_budget_granted", 0)) >= 1
    assert int(builder.get("hold_override_budget_consumed", 0)) >= 1


def test_relaxation_diag_records_candidate_became_eligible_when_relaxed_path_succeeds(monkeypatch) -> None:
    world, village = _world_with_workers(3)
    world.tick = 240

    def _fixed_mix(_world, _village):
        return {
            "farmer": 0,
            "builder": 1,
            "hauler": 0,
            "forager": 0,
            "food_pressure": 1,
            "construction_pressure": 1,
            "logistics_pressure": 0,
            "material_pressure": 0,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["needs"] = {"food_urgent": False, "food_buffer_critical": False}
    village["storage"]["food"] = 6
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick) - (role_system.LIVE_CONSTRUCTION_SIGNAL_WINDOW_TICKS + 3),
        "builder_waiting_tick": int(world.tick),
    }
    for idx, a in enumerate(world.agents):
        if idx == 0:
            a.role = "hauler"
            a.role_hold_until_tick = int(world.tick) + 50
        else:
            a.role = "farmer"
            a.role_hold_until_tick = -1
        a.hunger = 52.0

    role_system.assign_village_roles(world)
    diag = village.get("metrics", {}).get("support_role_relaxation_diagnostics", {})
    roles = diag.get("roles", {}) if isinstance(diag, dict) else {}
    builder = roles.get("builder", {}) if isinstance(roles, dict) else {}
    reasons = builder.get("short_circuit_reasons", {}) if isinstance(builder.get("short_circuit_reasons", {}), dict) else {}
    assert int(builder.get("eligible_count", 0)) >= 1
    assert int(reasons.get("candidate_became_eligible", 0)) >= 1


def test_reserved_civic_support_slot_activates_under_live_demand_safe_conditions(monkeypatch) -> None:
    world, village = _world_with_workers(4)
    world.tick = 20

    def _fixed_mix(_world, _village):
        return {
            "farmer": 2,
            "builder": 1,
            "hauler": 1,
            "forager": 0,
            "food_pressure": 1,
            "construction_pressure": 1,
            "logistics_pressure": 1,
            "material_pressure": 1,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["needs"] = {"food_urgent": False, "food_buffer_critical": False}
    village["storage"]["food"] = 10
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
        "builder_waiting_tick": int(world.tick),
    }
    for a in world.agents:
        a.role = "farmer"
        a.hunger = 52.0
        a.role_hold_until_tick = int(world.tick) + 80

    role_system.assign_village_roles(world)
    slot = village.get("reserved_civic_support", {})
    assert bool(slot.get("reserved_civic_support_active", False)) is True
    assert str(slot.get("reserved_civic_support_role", "")) in {"builder", "hauler"}
    metrics = village.get("metrics", {}).get("reserved_civic_support_metrics", {})
    assert int(metrics.get("reserved_civic_support_activations", 0)) >= 1
    gate = village.get("metrics", {}).get("reserved_civic_support_gate_diagnostics", {})
    roles = gate.get("roles", {}) if isinstance(gate, dict) else {}
    assert int((roles.get("builder", {}) or {}).get("gate_evaluations", 0)) >= 1
    assert int((roles.get("hauler", {}) or {}).get("gate_evaluations", 0)) >= 1
    granted_total = int((roles.get("builder", {}) or {}).get("slot_activation_granted", 0)) + int((roles.get("hauler", {}) or {}).get("slot_activation_granted", 0))
    assert granted_total >= 1


def test_reserved_civic_support_slot_blocked_in_true_survival_crisis(monkeypatch) -> None:
    world, village = _world_with_workers(4)
    world.tick = 20

    def _fixed_mix(_world, _village):
        return {
            "farmer": 2,
            "builder": 1,
            "hauler": 1,
            "forager": 0,
            "food_pressure": 2,
            "construction_pressure": 1,
            "logistics_pressure": 1,
            "material_pressure": 1,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["needs"] = {"food_urgent": True, "food_buffer_critical": True}
    village["storage"]["food"] = 0
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
        "builder_waiting_tick": int(world.tick),
    }
    for a in world.agents:
        a.role = "farmer"
        a.hunger = 12.0

    role_system.assign_village_roles(world)
    slot = village.get("reserved_civic_support", {})
    assert bool(slot.get("reserved_civic_support_active", False)) is False
    gate = village.get("metrics", {}).get("reserved_civic_support_gate_diagnostics", {})
    builder = ((gate.get("roles", {}) or {}).get("builder", {})) if isinstance(gate, dict) else {}
    reasons = builder.get("slot_activation_block_reasons", {}) if isinstance(builder.get("slot_activation_block_reasons", {}), dict) else {}
    assert int(reasons.get("true_survival_crisis", 0)) >= 1


def test_reserved_civic_support_slot_can_activate_in_fragile_non_terminal_state(monkeypatch) -> None:
    world, village = _world_with_workers(3)
    world.tick = 20

    def _fixed_mix(_world, _village):
        return {
            "farmer": 1,
            "builder": 1,
            "hauler": 0,
            "forager": 0,
            "food_pressure": 1,
            "construction_pressure": 1,
            "logistics_pressure": 0,
            "material_pressure": 0,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    # Fragile but non-terminal for slot logic: low stock and urgency, but not critical combination.
    village["needs"] = {"food_urgent": True, "food_buffer_critical": False}
    village["storage"]["food"] = 0
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 2, "wood_reserved": 0, "stone_needed": 1, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
    }
    for a in world.agents:
        a.role = "farmer"
        a.hunger = 35.0
        a.role_hold_until_tick = int(world.tick) + 60

    role_system.assign_village_roles(world)
    slot = village.get("reserved_civic_support", {})
    assert bool(slot.get("reserved_civic_support_active", False)) is True


def test_reserved_civic_support_slot_can_activate_in_one_worker_viable_village(monkeypatch) -> None:
    world, village = _world_with_workers(1)
    world.tick = 20

    def _fixed_mix(_world, _village):
        return {
            "farmer": 1,
            "builder": 1,
            "hauler": 0,
            "forager": 0,
            "food_pressure": 1,
            "construction_pressure": 1,
            "logistics_pressure": 0,
            "material_pressure": 0,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["needs"] = {"food_urgent": False, "food_buffer_critical": False}
    village["storage"]["food"] = 2
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 1, "wood_reserved": 0, "stone_needed": 0, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
    }
    worker = world.agents[0]
    worker.role = "farmer"
    worker.hunger = 48.0
    worker.role_hold_until_tick = int(world.tick) + 40

    role_system.assign_village_roles(world)
    slot = village.get("reserved_civic_support", {})
    assert bool(slot.get("reserved_civic_support_active", False)) is True
    assert str(slot.get("reserved_civic_support_role", "")) in {"builder", "hauler"}


def test_reserved_civic_support_slot_records_no_candidate_available(monkeypatch) -> None:
    world, village = _world_with_workers(0)
    world.tick = 20

    def _fixed_mix(_world, _village):
        return {
            "farmer": 2,
            "builder": 1,
            "hauler": 1,
            "forager": 0,
            "food_pressure": 1,
            "construction_pressure": 1,
            "logistics_pressure": 1,
            "material_pressure": 1,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["needs"] = {"food_urgent": False, "food_buffer_critical": False}
    village["storage"]["food"] = 10
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
        "builder_waiting_tick": int(world.tick),
    }
    role_system.assign_village_roles(world)
    gate = village.get("metrics", {}).get("reserved_civic_support_gate_diagnostics", {})
    roles = gate.get("roles", {}) if isinstance(gate, dict) else {}
    builder_reasons = ((roles.get("builder", {}) or {}).get("slot_activation_block_reasons", {})) if isinstance(roles, dict) else {}
    hauler_reasons = ((roles.get("hauler", {}) or {}).get("slot_activation_block_reasons", {})) if isinstance(roles, dict) else {}
    assert int(builder_reasons.get("no_candidate_available", 0)) >= 1 or int(hauler_reasons.get("no_candidate_available", 0)) >= 1


def test_reserved_civic_support_slot_remains_single_per_village(monkeypatch) -> None:
    world, village = _world_with_workers(5)
    world.tick = 20

    def _fixed_mix(_world, _village):
        return {
            "farmer": 2,
            "builder": 1,
            "hauler": 1,
            "forager": 0,
            "food_pressure": 1,
            "construction_pressure": 1,
            "logistics_pressure": 1,
            "material_pressure": 1,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["needs"] = {"food_urgent": False, "food_buffer_critical": False}
    village["storage"]["food"] = 12
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
        "builder_waiting_tick": int(world.tick),
    }
    for a in world.agents:
        a.role = "farmer"
        a.hunger = 55.0
        a.role_hold_until_tick = int(world.tick) + 60

    role_system.assign_village_roles(world)
    role_system.assign_village_roles(world)
    slot = village.get("reserved_civic_support", {})
    assert bool(slot.get("reserved_civic_support_active", False)) is True
    metrics = village.get("metrics", {}).get("reserved_civic_support_metrics", {})
    assert int(metrics.get("reserved_civic_support_active_count", 0)) <= 1


def test_reserved_civic_support_slot_expires_and_releases(monkeypatch) -> None:
    world, village = _world_with_workers(4)
    world.tick = 20

    def _fixed_mix(_world, _village):
        return {
            "farmer": 2,
            "builder": 1,
            "hauler": 1,
            "forager": 0,
            "food_pressure": 1,
            "construction_pressure": 1,
            "logistics_pressure": 1,
            "material_pressure": 1,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["needs"] = {"food_urgent": False, "food_buffer_critical": False}
    village["storage"]["food"] = 10
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world.tick),
        "builder_waiting_tick": int(world.tick),
    }
    for a in world.agents:
        a.role = "farmer"
        a.hunger = 55.0
        a.role_hold_until_tick = int(world.tick) + 60

    role_system.assign_village_roles(world)
    slot = village.get("reserved_civic_support", {})
    assert bool(slot.get("reserved_civic_support_active", False)) is True
    world.tick = int(slot.get("reserved_civic_support_until_tick", 0)) + 1
    world.buildings.pop("b-site", None)
    role_system.assign_village_roles(world)
    slot_after = village.get("reserved_civic_support", {})
    assert bool(slot_after.get("reserved_civic_support_active", False)) is False
    metrics = village.get("metrics", {}).get("reserved_civic_support_metrics", {})
    reasons = metrics.get("reserved_civic_support_released_reason_counts", {})
    assert int(metrics.get("reserved_civic_support_expired_count", 0)) >= 1
    assert int(reasons.get("slot_expired", 0)) >= 1 or int(reasons.get("demand_disappeared", 0)) >= 1


def test_reserved_civic_support_slot_does_not_fake_delivery_or_progress(monkeypatch) -> None:
    world, village = _world_with_workers(4)
    world.tick = 20

    def _fixed_mix(_world, _village):
        return {
            "farmer": 2,
            "builder": 1,
            "hauler": 1,
            "forager": 0,
            "food_pressure": 1,
            "construction_pressure": 1,
            "logistics_pressure": 1,
            "material_pressure": 1,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village["needs"] = {"food_urgent": False, "food_buffer_critical": False}
    village["storage"]["food"] = 10
    world.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_buffer": {"wood": 0, "stone": 0, "food": 0},
        "construction_progress": 0,
        "construction_required_work": 6,
        "construction_last_demand_tick": int(world.tick),
        "builder_waiting_tick": int(world.tick),
    }
    before_progress = int(world.buildings["b-site"]["construction_progress"])
    before_deliveries = int(village.get("logistics_metrics", {}).get("construction_deliveries_count", 0))
    for a in world.agents:
        a.role = "farmer"
        a.hunger = 55.0

    role_system.assign_village_roles(world)
    assert int(world.buildings["b-site"]["construction_progress"]) == before_progress
    assert int(village.get("logistics_metrics", {}).get("construction_deliveries_count", 0)) == before_deliveries


def test_reserved_civic_support_slot_can_bias_builder_or_hauler(monkeypatch) -> None:
    # Builder-leaning case: no outstanding materials, recent heartbeat.
    world_a, village_a = _world_with_workers(4)
    world_a.tick = 20

    def _fixed_mix(_world, _village):
        return {
            "farmer": 2,
            "builder": 1,
            "hauler": 1,
            "forager": 0,
            "food_pressure": 1,
            "construction_pressure": 1,
            "logistics_pressure": 1,
            "material_pressure": 1,
            "resident_population": 0,
            "attached_population": 0,
        }

    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village_a["needs"] = {"food_urgent": False, "food_buffer_critical": False}
    village_a["storage"]["food"] = 10
    world_a.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 0, "wood_reserved": 0, "stone_needed": 0, "stone_reserved": 0},
        "construction_last_demand_tick": int(world_a.tick),
    }
    village_a["specialist_rebalance_state"] = {
        "last_specialist_rebalance_tick": int(world_a.tick),
        "cached_miner_target": 0,
        "cached_woodcutter_target": 0,
    }
    for idx, a in enumerate(world_a.agents):
        a.role = "farmer" if idx == 0 else "miner"
        a.hunger = 52.0
        a.role_hold_until_tick = int(world_a.tick) + 60
    role_system.assign_village_roles(world_a)
    slot_role_a = str(village_a.get("reserved_civic_support", {}).get("reserved_civic_support_role", ""))
    assert slot_role_a == "builder"

    # Hauler-leaning case: outstanding materials + builder wait signal.
    world_b, village_b = _world_with_workers(4)
    world_b.tick = 20
    monkeypatch.setattr(role_system, "compute_target_workforce_mix", _fixed_mix)
    village_b["needs"] = {"food_urgent": False, "food_buffer_critical": False}
    village_b["storage"]["food"] = 10
    world_b.buildings["b-site"] = {
        "building_id": "b-site",
        "type": "storage",
        "x": 11,
        "y": 11,
        "village_id": 1,
        "village_uid": "v-000001",
        "operational_state": "under_construction",
        "construction_request": {"wood_needed": 4, "wood_reserved": 0, "stone_needed": 2, "stone_reserved": 0},
        "construction_last_demand_tick": int(world_b.tick),
        "builder_waiting_tick": int(world_b.tick),
    }
    village_b["specialist_rebalance_state"] = {
        "last_specialist_rebalance_tick": int(world_b.tick),
        "cached_miner_target": 0,
        "cached_woodcutter_target": 0,
    }
    for idx, a in enumerate(world_b.agents):
        a.role = "farmer" if idx == 0 else "miner"
        a.hunger = 52.0
        a.role_hold_until_tick = int(world_b.tick) + 60
    role_system.assign_village_roles(world_b)
    slot_role_b = str(village_b.get("reserved_civic_support", {}).get("reserved_civic_support_role", ""))
    assert slot_role_b == "hauler"
