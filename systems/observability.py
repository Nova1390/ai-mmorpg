from __future__ import annotations

from collections import Counter, deque
from typing import Any, Deque, Dict, List, Set, Tuple


def _clamp_float(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(v)))


def _empty_production_metrics() -> Dict[str, int]:
    return {
        "total_food_gathered": 0,
        "total_wood_gathered": 0,
        "total_stone_gathered": 0,
        "direct_food_gathered": 0,
        "direct_wood_gathered": 0,
        "direct_stone_gathered": 0,
        "wood_from_lumberyards": 0,
        "stone_from_mines": 0,
    }


def _empty_specialization_diagnostics() -> Dict[str, Any]:
    base = {
        "readiness_possible_count": 0,
        "selected_by_policy_count": 0,
        "placement_candidate_found_count": 0,
        "build_attempt_count": 0,
        "built_active_count": 0,
        "staffed_count": 0,
        "used_for_production_count": 0,
        "blocker_reasons": {},
        "readiness_breakdown": {},
        "requirement_breakdown": {},
    }
    return {
        "mine": dict(base),
        "lumberyard": dict(base),
        "by_village": {},
    }


class SimulationMetricsCollector:
    def __init__(self, *, snapshot_interval: int = 5, history_size: int = 240) -> None:
        self.snapshot_interval = max(1, int(snapshot_interval))
        self.history_size = max(10, int(history_size))
        self._history: Deque[Dict[str, Any]] = deque(maxlen=self.history_size)
        self._latest: Dict[str, Any] = {}
        self._last_leader_by_village_uid: Dict[str, Any] = {}
        self._leadership_changes: int = 0

    def collect(self, world: Any) -> None:
        snapshot = self._build_snapshot(world)
        self._latest = snapshot
        if int(getattr(world, "tick", 0)) % self.snapshot_interval == 0:
            self._history.append(snapshot)

    def latest(self) -> Dict[str, Any]:
        return dict(self._latest)

    def history(self, limit: int = 120) -> List[Dict[str, Any]]:
        n = max(1, int(limit))
        return list(self._history)[-n:]

    def _build_snapshot(self, world: Any) -> Dict[str, Any]:
        alive_agents = [a for a in getattr(world, "agents", []) if getattr(a, "alive", False)]
        villages = list(getattr(world, "villages", []))
        buildings = list(getattr(world, "buildings", {}).values())
        avg_hunger = (
            sum(float(getattr(a, "hunger", 0.0)) for a in alive_agents) / float(len(alive_agents))
            if alive_agents
            else 0.0
        )

        storage_food = 0
        storage_wood = 0
        storage_stone = 0
        storage_utilization = []
        for b in buildings:
            if str(b.get("type", "")) != "storage":
                continue
            st = b.get("storage", {}) if isinstance(b.get("storage"), dict) else {}
            capacity = max(1, int(b.get("storage_capacity", 0) or 1))
            used = int(st.get("food", 0)) + int(st.get("wood", 0)) + int(st.get("stone", 0))
            storage_food += int(st.get("food", 0))
            storage_wood += int(st.get("wood", 0))
            storage_stone += int(st.get("stone", 0))
            storage_utilization.append(_clamp_float(used / capacity, 0.0, 1.0))

        buildings_by_type: Counter[str] = Counter(str(b.get("type", "unknown")) for b in buildings)
        under_construction = sum(1 for b in buildings if str(b.get("operational_state", "active")) == "under_construction")
        transport_counts: Counter[str] = Counter(str(t) for t in getattr(world, "get_transport_tiles", lambda: {})().values())

        logistics_internal_transfers = 0
        for v in villages:
            lm = v.get("logistics_metrics", {}) if isinstance(v.get("logistics_metrics"), dict) else {}
            logistics_internal_transfers += int(lm.get("internal_transfers_count", 0))
        construction_deliveries = 0
        blocked_construction = 0
        for a in alive_agents:
            recent = (getattr(a, "episodic_memory", {}) or {}).get("recent_events", [])
            if not isinstance(recent, list):
                continue
            for ev in recent[-20:]:
                if not isinstance(ev, dict):
                    continue
                etype = str(ev.get("type", ""))
                outcome = str(ev.get("outcome", ""))
                if etype == "delivered_material" and outcome == "success":
                    construction_deliveries += 1
                if etype == "construction_blocked" and outcome == "failure":
                    blocked_construction += 1

        production = _empty_production_metrics()
        world_production = getattr(world, "production_metrics", None)
        if isinstance(world_production, dict):
            for key, default in _empty_production_metrics().items():
                production[key] = int(world_production.get(key, default))
        else:
            for v in villages:
                pm = v.get("production_metrics", {}) if isinstance(v.get("production_metrics"), dict) else {}
                for key, default in _empty_production_metrics().items():
                    production[key] += int(pm.get(key, default))
            # Backward-compatible direct derivation for older village counters.
            production["direct_wood_gathered"] = max(
                production["direct_wood_gathered"],
                production["total_wood_gathered"] - production["wood_from_lumberyards"],
            )
            production["direct_stone_gathered"] = max(
                production["direct_stone_gathered"],
                production["total_stone_gathered"] - production["stone_from_mines"],
            )
            production["direct_food_gathered"] = max(
                production["direct_food_gathered"],
                production["total_food_gathered"],
            )
        wood_total = max(0, int(production.get("total_wood_gathered", 0)))
        stone_total = max(0, int(production.get("total_stone_gathered", 0)))
        food_total = max(0, int(production.get("total_food_gathered", 0)))
        production["wood_specialization_ratio"] = round(
            float(production.get("wood_from_lumberyards", 0)) / float(wood_total),
            3,
        ) if wood_total > 0 else 0.0
        production["stone_specialization_ratio"] = round(
            float(production.get("stone_from_mines", 0)) / float(stone_total),
            3,
        ) if stone_total > 0 else 0.0
        production["food_direct_ratio"] = round(
            float(production.get("direct_food_gathered", 0)) / float(food_total),
            3,
        ) if food_total > 0 else 0.0

        intention_counts: Counter[str] = Counter()
        blocked_intentions = 0
        specialists_by_role: Counter[str] = Counter()
        food_crisis_count = 0
        survival_pressure_samples: List[float] = []
        sleep_need_samples: List[float] = []
        fatigue_samples: List[float] = []
        health_samples: List[float] = []
        happiness_samples: List[float] = []
        familiarity_scores: List[float] = []
        familiarity_relationships_count = 0
        useful_memory_ages: List[int] = []
        agent_ages: List[int] = []
        high_sleep_need_agents = 0
        high_fatigue_agents = 0
        low_health_agents = 0
        low_happiness_agents = 0
        high_happiness_agents = 0
        known_invention_entry_count = 0
        agents_with_known_inventions = 0
        invention_knowledge_by_source: Counter[str] = Counter()
        invention_knowledge_by_category: Counter[str] = Counter()
        recent_diffused_inventions: List[Dict[str, Any]] = []
        affiliation_by_village: Dict[str, Dict[str, int]] = {
            str(v.get("village_uid", "")): {"resident": 0, "attached": 0, "transient": 0}
            for v in villages
            if str(v.get("village_uid", ""))
        }
        agents_unaffiliated = 0
        affiliation_distance_by_village: Dict[str, List[int]] = {}
        co_presence_by_village: Counter[str] = Counter()
        top_social = sorted(
            [
                {
                    "agent_id": str(getattr(a, "agent_id", "")),
                    "role": str(getattr(a, "role", "npc")),
                    "social_influence": float(getattr(a, "social_influence", 0.0)),
                }
                for a in alive_agents
            ],
            key=lambda item: (-float(item["social_influence"]), str(item["agent_id"])),
        )[:5]
        for a in alive_agents:
            born_tick = int(getattr(a, "born_tick", 0))
            agent_ages.append(max(0, int(getattr(world, "tick", 0)) - born_tick))
            role = str(getattr(a, "role", "npc"))
            if role in {"miner", "woodcutter", "builder", "hauler", "farmer"}:
                specialists_by_role[role] += 1
            intention = getattr(a, "current_intention", {})
            if isinstance(intention, dict):
                t = str(intention.get("type", "none"))
                intention_counts[t] += 1
                if int(intention.get("failed_ticks", 0)) >= 2:
                    blocked_intentions += 1
            subjective = getattr(a, "subjective_state", {})
            local_signals = subjective.get("local_signals", {}) if isinstance(subjective, dict) else {}
            survival = local_signals.get("survival", {}) if isinstance(local_signals, dict) else {}
            if isinstance(survival, dict):
                survival_pressure_samples.append(float(survival.get("survival_pressure", 0.0)))
                if bool(survival.get("food_crisis", False)):
                    food_crisis_count += 1
            sleep_need = float(getattr(a, "sleep_need", 0.0))
            fatigue = float(getattr(a, "fatigue", 0.0))
            health = float(getattr(a, "health", 100.0))
            happiness = float(getattr(a, "happiness", 50.0))
            sleep_need_samples.append(sleep_need)
            fatigue_samples.append(fatigue)
            health_samples.append(health)
            happiness_samples.append(happiness)
            if sleep_need >= 80.0:
                high_sleep_need_agents += 1
            if fatigue >= 80.0:
                high_fatigue_agents += 1
            if health <= 35.0:
                low_health_agents += 1
            if happiness <= 30.0:
                low_happiness_agents += 1
            if happiness >= 70.0:
                high_happiness_agents += 1
            encounter_memory = getattr(a, "recent_encounters", {})
            if isinstance(encounter_memory, dict):
                for enc in encounter_memory.values():
                    if not isinstance(enc, dict):
                        continue
                    fam = float(enc.get("familiarity_score", 0.0))
                    if fam <= 0.0:
                        continue
                    familiarity_relationships_count += 1
                    familiarity_scores.append(fam)
            kstate_all = getattr(a, "knowledge_state", {})
            if isinstance(kstate_all, dict):
                for key in ("known_resource_spots", "known_camp_spots", "known_useful_buildings", "known_practices", "known_inventions"):
                    entries = kstate_all.get(key, [])
                    if not isinstance(entries, list):
                        continue
                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        if float(entry.get("confidence", 0.0)) < 0.40:
                            continue
                        if float(entry.get("salience", 0.0)) < 0.45:
                            continue
                        learned_tick = int(entry.get("learned_tick", int(getattr(world, "tick", 0))))
                        useful_memory_ages.append(max(0, int(getattr(world, "tick", 0)) - learned_tick))
            kstate = getattr(a, "knowledge_state", {})
            known_inv = kstate.get("known_inventions", []) if isinstance(kstate, dict) else []
            if isinstance(known_inv, list) and known_inv:
                agents_with_known_inventions += 1
                for entry in known_inv:
                    if not isinstance(entry, dict):
                        continue
                    known_invention_entry_count += 1
                    source = str(entry.get("source", ""))
                    category = str(entry.get("category", ""))
                    invention_knowledge_by_source[source] += 1
                    invention_knowledge_by_category[category] += 1
                    if source == "social":
                        recent_diffused_inventions.append(
                            {
                                "agent_id": str(getattr(a, "agent_id", "")),
                                "proposal_id": str(entry.get("proposal_id", "")),
                                "category": category,
                                "learned_tick": int(entry.get("learned_tick", 0)),
                                "confidence": float(entry.get("confidence", 0.0)),
                            }
                        )
            status = str(getattr(a, "village_affiliation_status", "unaffiliated"))
            primary_uid = getattr(a, "primary_village_uid", None)
            home_uid = getattr(a, "home_village_uid", None)
            if status == "resident":
                aff_uid = str(home_uid or primary_uid or "")
            elif status in {"attached", "transient"}:
                aff_uid = str(primary_uid or "")
            else:
                aff_uid = ""
            if status in {"resident", "attached", "transient"} and aff_uid:
                village_counts = affiliation_by_village.setdefault(
                    aff_uid, {"resident": 0, "attached": 0, "transient": 0}
                )
                village_counts[status] = int(village_counts.get(status, 0)) + 1
                village_ref = next((v for v in villages if str(v.get("village_uid", "")) == aff_uid), None)
                if isinstance(village_ref, dict):
                    center = village_ref.get("center", {}) if isinstance(village_ref.get("center"), dict) else {}
                    cx = int(center.get("x", 0))
                    cy = int(center.get("y", 0))
                    dist = abs(int(getattr(a, "x", 0)) - cx) + abs(int(getattr(a, "y", 0)) - cy)
                    affiliation_distance_by_village.setdefault(aff_uid, []).append(dist)
                    if dist <= 6:
                        co_presence_by_village[aff_uid] += 1
            else:
                agents_unaffiliated += 1
        recent_diffused_inventions.sort(
            key=lambda rec: (-int(rec.get("learned_tick", 0)), str(rec.get("agent_id", "")), str(rec.get("proposal_id", "")))
        )

        house_count_by_village: Counter[str] = Counter()
        occupied_house_count_by_village: Counter[str] = Counter()
        occupied_house_ids: Set[str] = set()
        for a in alive_agents:
            hb = getattr(a, "home_building_id", None)
            if hb is not None:
                occupied_house_ids.add(str(hb))
        for b in getattr(world, "buildings", {}).values():
            if not isinstance(b, dict):
                continue
            if str(b.get("type", "")) != "house":
                continue
            if str(b.get("operational_state", "")) != "active":
                continue
            uid = str(b.get("village_uid", "") or "")
            if not uid:
                continue
            bid = str(b.get("building_id", ""))
            house_count_by_village[uid] += 1
            if bid in occupied_house_ids:
                occupied_house_count_by_village[uid] += 1

        social_gravity_events = {}
        if hasattr(world, "compute_social_gravity_event_snapshot"):
            try:
                sge = world.compute_social_gravity_event_snapshot()
                social_gravity_events = sge if isinstance(sge, dict) else {}
            except Exception:
                social_gravity_events = {}
        residence_stabilization = {}
        if hasattr(world, "compute_residence_stabilization_snapshot"):
            try:
                rss = world.compute_residence_stabilization_snapshot()
                residence_stabilization = rss if isinstance(rss, dict) else {}
            except Exception:
                residence_stabilization = {}
        resident_conversion_gate = {}
        if hasattr(world, "compute_resident_conversion_gate_snapshot"):
            try:
                rcg = world.compute_resident_conversion_gate_snapshot()
                resident_conversion_gate = rcg if isinstance(rcg, dict) else {}
            except Exception:
                resident_conversion_gate = {}
        recovery_diag = {}
        if hasattr(world, "compute_recovery_diagnostics_snapshot"):
            try:
                rd = world.compute_recovery_diagnostics_snapshot()
                recovery_diag = rd if isinstance(rd, dict) else {}
            except Exception:
                recovery_diag = {}

        social_cohesion_by_village: Dict[str, Dict[str, Any]] = {}
        for v in villages:
            uid = str(v.get("village_uid", ""))
            if not uid:
                continue
            counts = affiliation_by_village.get(uid, {"resident": 0, "attached": 0, "transient": 0})
            resident_count = int(counts.get("resident", 0))
            attached_count = int(counts.get("attached", 0))
            transient_count = int(counts.get("transient", 0))
            affiliated_total = resident_count + attached_count + transient_count
            houses = int(house_count_by_village.get(uid, 0))
            occupied_houses = int(occupied_house_count_by_village.get(uid, 0))
            avg_house_occupancy = round(float(resident_count) / float(max(1, houses)), 3) if houses > 0 else 0.0
            avg_dist = 0.0
            dlist = affiliation_distance_by_village.get(uid, [])
            if dlist:
                avg_dist = round(float(sum(dlist)) / float(len(dlist)), 3)
            co_presence_density = round(float(co_presence_by_village.get(uid, 0)) / float(max(1, affiliated_total)), 3) if affiliated_total > 0 else 0.0
            storage = v.get("storage", {}) if isinstance(v.get("storage"), dict) else {}
            storage_total = int(storage.get("food", 0)) + int(storage.get("wood", 0)) + int(storage.get("stone", 0))
            gravity_score = round(
                0.4
                + min(2.0, float(houses) * 0.25)
                + min(1.5, float(storage_total) / 25.0)
                + min(2.0, float(affiliated_total) * 0.2)
                + (0.5 if co_presence_density >= 0.5 else 0.0),
                3,
            )
            ev = (social_gravity_events.get("by_village", {}) or {}).get(uid, {}) if isinstance(social_gravity_events, dict) else {}
            social_cohesion_by_village[uid] = {
                "resident_count": resident_count,
                "attached_count": attached_count,
                "transient_count": transient_count,
                "unaffiliated_count": int(max(0, len(alive_agents) - affiliated_total)),
                "occupied_house_count": occupied_houses,
                "average_house_occupancy": avg_house_occupancy,
                "average_distance_from_village_center": avg_dist,
                "co_presence_density": co_presence_density,
                "village_social_gravity_score": gravity_score,
                "return_to_village_events": int(ev.get("return_to_village_events", 0)),
                "stay_near_village_bias_events": int(ev.get("stay_near_village_bias_events", 0)),
                "home_return_events": int(ev.get("home_return_events", 0)),
            }

        social_cohesion_global = {
            "resident_count": int(sum(v.get("resident_count", 0) for v in social_cohesion_by_village.values())),
            "attached_count": int(sum(v.get("attached_count", 0) for v in social_cohesion_by_village.values())),
            "transient_count": int(sum(v.get("transient_count", 0) for v in social_cohesion_by_village.values())),
            "unaffiliated_count": int(agents_unaffiliated),
            "occupied_house_count": int(sum(v.get("occupied_house_count", 0) for v in social_cohesion_by_village.values())),
            "average_house_occupancy": round(
                float(sum(v.get("average_house_occupancy", 0.0) for v in social_cohesion_by_village.values()))
                / float(max(1, len(social_cohesion_by_village))),
                3,
            ),
            "average_distance_from_village_center": round(
                float(sum(v.get("average_distance_from_village_center", 0.0) for v in social_cohesion_by_village.values()))
                / float(max(1, len(social_cohesion_by_village))),
                3,
            ),
            "co_presence_density": round(
                float(sum(v.get("co_presence_density", 0.0) for v in social_cohesion_by_village.values()))
                / float(max(1, len(social_cohesion_by_village))),
                3,
            ),
            "village_social_gravity_score": round(
                float(sum(v.get("village_social_gravity_score", 0.0) for v in social_cohesion_by_village.values()))
                / float(max(1, len(social_cohesion_by_village))),
                3,
            ),
            "return_to_village_events": int((social_gravity_events.get("global", {}) or {}).get("return_to_village_events", 0)) if isinstance(social_gravity_events, dict) else 0,
            "stay_near_village_bias_events": int((social_gravity_events.get("global", {}) or {}).get("stay_near_village_bias_events", 0)) if isinstance(social_gravity_events, dict) else 0,
            "home_return_events": int((social_gravity_events.get("global", {}) or {}).get("home_return_events", 0)) if isinstance(social_gravity_events, dict) else 0,
        }

        proto_culture_summary = []
        for v in villages:
            c = v.get("proto_culture", {}) if isinstance(v.get("proto_culture"), dict) else {}
            focus = c.get("resource_focus", {}) if isinstance(c.get("resource_focus"), dict) else {}
            dominant = max(("food", "wood", "stone"), key=lambda r: (float(focus.get(r, 0.0)), r))
            proto_culture_summary.append(
                {
                    "village_uid": str(v.get("village_uid", "")),
                    "cooperation_norm": float(c.get("cooperation_norm", 0.5)),
                    "work_norm": float(c.get("work_norm", 0.5)),
                    "exploration_norm": float(c.get("exploration_norm", 0.5)),
                    "risk_norm": float(c.get("risk_norm", 0.5)),
                    "dominant_resource_focus": dominant,
                }
            )
        proto_culture_summary.sort(key=lambda x: x["village_uid"])

        for v in villages:
            uid = str(v.get("village_uid", ""))
            current = v.get("leader_id")
            if uid not in self._last_leader_by_village_uid:
                self._last_leader_by_village_uid[uid] = current
                continue
            if self._last_leader_by_village_uid[uid] != current:
                self._leadership_changes += 1
                self._last_leader_by_village_uid[uid] = current

        reflection_stats = getattr(world, "reflection_stats", {})
        if not isinstance(reflection_stats, dict):
            reflection_stats = {}
        specialization = getattr(world, "specialization_diagnostics", None)
        if not isinstance(specialization, dict):
            specialization = _empty_specialization_diagnostics()
        else:
            fallback = _empty_specialization_diagnostics()
            for btype in ("mine", "lumberyard"):
                entry = specialization.get(btype, {})
                if not isinstance(entry, dict):
                    entry = {}
                merged = dict(fallback[btype])
                for key in (
                    "readiness_possible_count",
                    "selected_by_policy_count",
                    "placement_candidate_found_count",
                    "build_attempt_count",
                    "built_active_count",
                    "staffed_count",
                    "used_for_production_count",
                ):
                    merged[key] = int(entry.get(key, 0))
                blockers = entry.get("blocker_reasons", {})
                merged["blocker_reasons"] = dict(blockers) if isinstance(blockers, dict) else {}
                readiness_breakdown = entry.get("readiness_breakdown", {})
                merged["readiness_breakdown"] = (
                    dict(readiness_breakdown) if isinstance(readiness_breakdown, dict) else {}
                )
                requirement_breakdown = entry.get("requirement_breakdown", {})
                merged["requirement_breakdown"] = (
                    dict(requirement_breakdown) if isinstance(requirement_breakdown, dict) else {}
                )
                specialization[btype] = merged
            if not isinstance(specialization.get("by_village"), dict):
                specialization["by_village"] = {}

        workforce_target_mix_by_village: Dict[str, Dict[str, int]] = {}
        workforce_actual_mix_by_village: Dict[str, Dict[str, int]] = {}
        workforce_role_deficits_by_village: Dict[str, Dict[str, int]] = {}
        workforce_pressure_by_village: Dict[str, Dict[str, int]] = {}
        support_role_assignment_diagnostics_by_village: Dict[str, Dict[str, Any]] = {}
        support_role_assignment_diagnostics_global: Dict[str, Dict[str, Any]] = {
            "builder": {
                "floor_requested_count": 0,
                "floor_satisfied_count": 0,
                "target_requested": 0,
                "candidates_total": 0,
                "candidates_eligible": 0,
                "candidates_filtered_out": 0,
                "selected_count": 0,
                "previous_assigned_count": 0,
                "final_assigned_count_after_pass": 0,
                "filter_reasons": {},
            },
            "hauler": {
                "floor_requested_count": 0,
                "floor_satisfied_count": 0,
                "target_requested": 0,
                "candidates_total": 0,
                "candidates_eligible": 0,
                "candidates_filtered_out": 0,
                "selected_count": 0,
                "previous_assigned_count": 0,
                "final_assigned_count_after_pass": 0,
                "filter_reasons": {},
            },
        }
        support_role_relaxation_diagnostics_by_village: Dict[str, Dict[str, Any]] = {}
        support_role_relaxation_diagnostics_global: Dict[str, Dict[str, Any]] = {
            "builder": {
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
            },
            "hauler": {
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
            },
        }
        reserved_civic_support_by_village: Dict[str, Dict[str, Any]] = {}
        reserved_civic_support_global: Dict[str, Any] = {
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
        reserved_civic_support_gate_diagnostics_by_village: Dict[str, Dict[str, Any]] = {}
        reserved_civic_support_gate_diagnostics_global: Dict[str, Dict[str, Any]] = {
            "builder": {
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
            },
            "hauler": {
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
            },
        }
        for village in villages:
            uid = str(village.get("village_uid", ""))
            if not uid:
                continue
            metrics = village.get("metrics", {}) if isinstance(village.get("metrics"), dict) else {}
            target = metrics.get("workforce_target_mix", {})
            actual = metrics.get("workforce_actual_mix", {})
            deficits = metrics.get("workforce_role_deficits", {})
            pressure = metrics.get("workforce_pressure_summary", {})
            workforce_target_mix_by_village[uid] = {
                str(k): int(v) for k, v in (target.items() if isinstance(target, dict) else [])
            }
            workforce_actual_mix_by_village[uid] = {
                str(k): int(v) for k, v in (actual.items() if isinstance(actual, dict) else [])
            }
            workforce_role_deficits_by_village[uid] = {
                str(k): int(v) for k, v in (deficits.items() if isinstance(deficits, dict) else [])
            }
            workforce_pressure_by_village[uid] = {
                str(k): int(v) for k, v in (pressure.items() if isinstance(pressure, dict) else [])
            }
            support_diag = metrics.get("support_role_assignment_diagnostics", {})
            if isinstance(support_diag, dict):
                vdiag = {
                    "live_demand": bool(support_diag.get("live_demand", False)),
                    "under_construction_sites": int(support_diag.get("under_construction_sites", 0)),
                    "outstanding_materials": int(support_diag.get("outstanding_materials", 0)),
                    "recent_heartbeat_sites": int(support_diag.get("recent_heartbeat_sites", 0)),
                    "recent_builder_wait_sites": int(support_diag.get("recent_builder_wait_sites", 0)),
                    "reallocation_due": bool(support_diag.get("reallocation_due", False)),
                    "roles": {},
                }
                roles = support_diag.get("roles", {})
                if isinstance(roles, dict):
                    for role_name in ("builder", "hauler"):
                        role_entry = roles.get(role_name, {})
                        if not isinstance(role_entry, dict):
                            continue
                        filter_reasons = role_entry.get("filter_reasons", {})
                        clean_role = {
                            "floor_requested": bool(role_entry.get("floor_requested", False)),
                            "floor_required": int(role_entry.get("floor_required", 0)),
                            "target_requested": int(role_entry.get("target_requested", 0)),
                            "candidates_total": int(role_entry.get("candidates_total", 0)),
                            "candidates_eligible": int(role_entry.get("candidates_eligible", 0)),
                            "candidates_filtered_out": int(role_entry.get("candidates_filtered_out", 0)),
                            "selected_count": int(role_entry.get("selected_count", 0)),
                            "selected_agent_ids": list(role_entry.get("selected_agent_ids", []))[:6]
                            if isinstance(role_entry.get("selected_agent_ids", []), list)
                            else [],
                            "floor_satisfied": bool(role_entry.get("floor_satisfied", False)),
                            "previous_assigned_count": int(role_entry.get("previous_assigned_count", 0)),
                            "final_assigned_count_after_pass": int(role_entry.get("final_assigned_count_after_pass", 0)),
                            "filter_reasons": {
                                str(k): int(v) for k, v in (filter_reasons.items() if isinstance(filter_reasons, dict) else [])
                            },
                        }
                        vdiag["roles"][role_name] = clean_role
                        g = support_role_assignment_diagnostics_global[role_name]
                        if clean_role["floor_requested"]:
                            g["floor_requested_count"] = int(g.get("floor_requested_count", 0)) + 1
                        if clean_role["floor_satisfied"]:
                            g["floor_satisfied_count"] = int(g.get("floor_satisfied_count", 0)) + 1
                        g["target_requested"] = int(g.get("target_requested", 0)) + int(clean_role["target_requested"])
                        g["candidates_total"] = int(g.get("candidates_total", 0)) + int(clean_role["candidates_total"])
                        g["candidates_eligible"] = int(g.get("candidates_eligible", 0)) + int(clean_role["candidates_eligible"])
                        g["candidates_filtered_out"] = int(g.get("candidates_filtered_out", 0)) + int(clean_role["candidates_filtered_out"])
                        g["selected_count"] = int(g.get("selected_count", 0)) + int(clean_role["selected_count"])
                        g["previous_assigned_count"] = int(g.get("previous_assigned_count", 0)) + int(clean_role["previous_assigned_count"])
                        g["final_assigned_count_after_pass"] = int(g.get("final_assigned_count_after_pass", 0)) + int(clean_role["final_assigned_count_after_pass"])
                        for reason, count in clean_role["filter_reasons"].items():
                            gr = g.get("filter_reasons", {})
                            gr[str(reason)] = int(gr.get(str(reason), 0)) + int(count)
                            g["filter_reasons"] = gr
                support_role_assignment_diagnostics_by_village[uid] = vdiag
            support_relax_diag = metrics.get("support_role_relaxation_diagnostics", {})
            if isinstance(support_relax_diag, dict):
                vrelax = {"roles": {}}
                roles = support_relax_diag.get("roles", {})
                if isinstance(roles, dict):
                    for role_name in ("builder", "hauler"):
                        role_entry = roles.get(role_name, {})
                        if not isinstance(role_entry, dict):
                            continue
                        short = role_entry.get("short_circuit_reasons", {})
                        clean_role = {
                            "live_demand_context_seen": int(role_entry.get("live_demand_context_seen", 0)),
                            "support_signal_recent_seen": int(role_entry.get("support_signal_recent_seen", 0)),
                            "true_survival_crisis_seen": int(role_entry.get("true_survival_crisis_seen", 0)),
                            "population_safe_for_relaxation": int(role_entry.get("population_safe_for_relaxation", 0)),
                            "food_base_relaxation_budget_granted": int(role_entry.get("food_base_relaxation_budget_granted", 0)),
                            "food_base_relaxation_budget_consumed": int(role_entry.get("food_base_relaxation_budget_consumed", 0)),
                            "hold_override_budget_granted": int(role_entry.get("hold_override_budget_granted", 0)),
                            "hold_override_budget_consumed": int(role_entry.get("hold_override_budget_consumed", 0)),
                            "eligible_count": int(role_entry.get("eligible_count", 0)),
                            "short_circuit_reasons": {
                                str(k): int(v) for k, v in (short.items() if isinstance(short, dict) else [])
                            },
                        }
                        vrelax["roles"][role_name] = clean_role
                        g = support_role_relaxation_diagnostics_global[role_name]
                        for k in (
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
                            g[k] = int(g.get(k, 0)) + int(clean_role.get(k, 0))
                        for reason, count in clean_role["short_circuit_reasons"].items():
                            gs = g.get("short_circuit_reasons", {})
                            gs[str(reason)] = int(gs.get(str(reason), 0)) + int(count)
                            g["short_circuit_reasons"] = gs
                support_role_relaxation_diagnostics_by_village[uid] = vrelax
            reserved_state = village.get("reserved_civic_support", {})
            reserved_metrics = metrics.get("reserved_civic_support_metrics", {})
            if isinstance(reserved_state, dict) or isinstance(reserved_metrics, dict):
                role_counts = reserved_metrics.get("reserved_civic_support_role_counts", {}) if isinstance(reserved_metrics, dict) else {}
                release_reasons = reserved_metrics.get("reserved_civic_support_released_reason_counts", {}) if isinstance(reserved_metrics, dict) else {}
                outcome_counts = reserved_metrics.get("reserved_civic_support_supported_outcome_counts", {}) if isinstance(reserved_metrics, dict) else {}
                vslot = {
                    "reserved_civic_support_active": bool(reserved_state.get("reserved_civic_support_active", False)) if isinstance(reserved_state, dict) else False,
                    "reserved_civic_support_agent_id": str(reserved_state.get("reserved_civic_support_agent_id", "")) if isinstance(reserved_state, dict) else "",
                    "reserved_civic_support_role": str(reserved_state.get("reserved_civic_support_role", "")) if isinstance(reserved_state, dict) else "",
                    "reserved_civic_support_until_tick": int(reserved_state.get("reserved_civic_support_until_tick", -1)) if isinstance(reserved_state, dict) else -1,
                    "reserved_civic_support_reason": str(reserved_state.get("reserved_civic_support_reason", "")) if isinstance(reserved_state, dict) else "",
                    "reserved_civic_support_activations": int(reserved_metrics.get("reserved_civic_support_activations", 0)) if isinstance(reserved_metrics, dict) else 0,
                    "reserved_civic_support_active_count": int(reserved_metrics.get("reserved_civic_support_active_count", 0)) if isinstance(reserved_metrics, dict) else 0,
                    "reserved_civic_support_role_counts": {
                        "builder": int(role_counts.get("builder", 0)) if isinstance(role_counts, dict) else 0,
                        "hauler": int(role_counts.get("hauler", 0)) if isinstance(role_counts, dict) else 0,
                    },
                    "reserved_civic_support_expired_count": int(reserved_metrics.get("reserved_civic_support_expired_count", 0)) if isinstance(reserved_metrics, dict) else 0,
                    "reserved_civic_support_released_reason_counts": {
                        str(k): int(v) for k, v in (release_reasons.items() if isinstance(release_reasons, dict) else [])
                    },
                    "reserved_civic_support_supported_outcome_counts": {
                        "construction_delivery": int(outcome_counts.get("construction_delivery", 0)) if isinstance(outcome_counts, dict) else 0,
                        "construction_progress": int(outcome_counts.get("construction_progress", 0)) if isinstance(outcome_counts, dict) else 0,
                    },
                }
                reserved_civic_support_by_village[uid] = vslot
                reserved_civic_support_global["reserved_civic_support_activations"] = int(
                    reserved_civic_support_global.get("reserved_civic_support_activations", 0)
                ) + int(vslot["reserved_civic_support_activations"])
                reserved_civic_support_global["reserved_civic_support_active_count"] = int(
                    reserved_civic_support_global.get("reserved_civic_support_active_count", 0)
                ) + int(vslot["reserved_civic_support_active_count"])
                g_role_counts = reserved_civic_support_global.get("reserved_civic_support_role_counts", {})
                g_role_counts["builder"] = int(g_role_counts.get("builder", 0)) + int(vslot["reserved_civic_support_role_counts"]["builder"])
                g_role_counts["hauler"] = int(g_role_counts.get("hauler", 0)) + int(vslot["reserved_civic_support_role_counts"]["hauler"])
                reserved_civic_support_global["reserved_civic_support_role_counts"] = g_role_counts
                reserved_civic_support_global["reserved_civic_support_expired_count"] = int(
                    reserved_civic_support_global.get("reserved_civic_support_expired_count", 0)
                ) + int(vslot["reserved_civic_support_expired_count"])
                g_release = reserved_civic_support_global.get("reserved_civic_support_released_reason_counts", {})
                for reason, count in vslot["reserved_civic_support_released_reason_counts"].items():
                    g_release[str(reason)] = int(g_release.get(str(reason), 0)) + int(count)
                reserved_civic_support_global["reserved_civic_support_released_reason_counts"] = g_release
                g_outcome = reserved_civic_support_global.get("reserved_civic_support_supported_outcome_counts", {})
                g_outcome["construction_delivery"] = int(g_outcome.get("construction_delivery", 0)) + int(
                    vslot["reserved_civic_support_supported_outcome_counts"]["construction_delivery"]
                )
                g_outcome["construction_progress"] = int(g_outcome.get("construction_progress", 0)) + int(
                    vslot["reserved_civic_support_supported_outcome_counts"]["construction_progress"]
                )
                reserved_civic_support_global["reserved_civic_support_supported_outcome_counts"] = g_outcome
            gate_diag = metrics.get("reserved_civic_support_gate_diagnostics", {})
            if isinstance(gate_diag, dict):
                vgate = {"roles": {}}
                roles = gate_diag.get("roles", {})
                if isinstance(roles, dict):
                    for role_name in ("builder", "hauler"):
                        role_entry = roles.get(role_name, {})
                        if not isinstance(role_entry, dict):
                            continue
                        reasons = role_entry.get("slot_activation_block_reasons", {})
                        clean_role = {
                            "gate_evaluations": int(role_entry.get("gate_evaluations", 0)),
                            "live_construction_demand_seen": int(role_entry.get("live_construction_demand_seen", 0)),
                            "support_signal_recent_seen": int(role_entry.get("support_signal_recent_seen", 0)),
                            "true_survival_crisis_blocked": int(role_entry.get("true_survival_crisis_blocked", 0)),
                            "population_not_safe_blocked": int(role_entry.get("population_not_safe_blocked", 0)),
                            "support_floor_gap_seen": int(role_entry.get("support_floor_gap_seen", 0)),
                            "support_floor_gap_count": int(role_entry.get("support_floor_gap_count", 0)),
                            "candidate_available_count": int(role_entry.get("candidate_available_count", 0)),
                            "slot_activation_granted": int(role_entry.get("slot_activation_granted", 0)),
                            "slot_activation_block_reasons": {
                                str(k): int(v) for k, v in (reasons.items() if isinstance(reasons, dict) else [])
                            },
                        }
                        vgate["roles"][role_name] = clean_role
                        g = reserved_civic_support_gate_diagnostics_global[role_name]
                        for key in (
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
                            g[key] = int(g.get(key, 0)) + int(clean_role.get(key, 0))
                        for reason, count in clean_role["slot_activation_block_reasons"].items():
                            gr = g.get("slot_activation_block_reasons", {})
                            gr[str(reason)] = int(gr.get(str(reason), 0)) + int(count)
                            g["slot_activation_block_reasons"] = gr
                reserved_civic_support_gate_diagnostics_by_village[uid] = vgate
        workforce_realization = {}
        if hasattr(world, "compute_workforce_realization_snapshot"):
            try:
                wr = world.compute_workforce_realization_snapshot()
                workforce_realization = wr if isinstance(wr, dict) else {}
            except Exception:
                workforce_realization = {}
        assignment_gap = {}
        if hasattr(world, "compute_assignment_to_action_gap_snapshot"):
            try:
                ag = world.compute_assignment_to_action_gap_snapshot()
                assignment_gap = ag if isinstance(ag, dict) else {}
            except Exception:
                assignment_gap = {}
        task_completion = {}
        if hasattr(world, "compute_task_completion_snapshot"):
            try:
                tc = world.compute_task_completion_snapshot()
                task_completion = tc if isinstance(tc, dict) else {}
            except Exception:
                task_completion = {}
        delivery_diagnostics = {}
        if hasattr(world, "compute_delivery_diagnostics_snapshot"):
            try:
                dd = world.compute_delivery_diagnostics_snapshot()
                delivery_diagnostics = dd if isinstance(dd, dict) else {}
            except Exception:
                delivery_diagnostics = {}
        housing_diagnostics = {}
        if hasattr(world, "compute_housing_construction_diagnostics_snapshot"):
            try:
                hd = world.compute_housing_construction_diagnostics_snapshot()
                housing_diagnostics = hd if isinstance(hd, dict) else {}
            except Exception:
                housing_diagnostics = {}
        housing_siting_rejection = {}
        if hasattr(world, "compute_housing_siting_rejection_snapshot"):
            try:
                hs = world.compute_housing_siting_rejection_snapshot()
                housing_siting_rejection = hs if isinstance(hs, dict) else {}
            except Exception:
                housing_siting_rejection = {}
        housing_path_coherence = {}
        if hasattr(world, "compute_housing_path_coherence_snapshot"):
            try:
                hp = world.compute_housing_path_coherence_snapshot()
                housing_path_coherence = hp if isinstance(hp, dict) else {}
            except Exception:
                housing_path_coherence = {}
        builder_self_supply = {}
        if hasattr(world, "compute_builder_self_supply_snapshot"):
            try:
                bss = world.compute_builder_self_supply_snapshot()
                builder_self_supply = bss if isinstance(bss, dict) else {}
            except Exception:
                builder_self_supply = {}
        builder_self_supply_gate = {}
        if hasattr(world, "compute_builder_self_supply_gate_snapshot"):
            try:
                bssg = world.compute_builder_self_supply_gate_snapshot()
                builder_self_supply_gate = bssg if isinstance(bssg, dict) else {}
            except Exception:
                builder_self_supply_gate = {}
        movement_diagnostics = {}
        if hasattr(world, "compute_movement_diagnostics_snapshot"):
            try:
                md = world.compute_movement_diagnostics_snapshot()
                movement_diagnostics = md if isinstance(md, dict) else {}
            except Exception:
                movement_diagnostics = {}
        progression_diag = {}
        if hasattr(world, "compute_progression_snapshot"):
            try:
                pd = world.compute_progression_snapshot()
                progression_diag = pd if isinstance(pd, dict) else {}
            except Exception:
                progression_diag = {}
        proto_funnel_diag = {}
        if hasattr(world, "compute_proto_community_funnel_snapshot"):
            try:
                pfd = world.compute_proto_community_funnel_snapshot()
                proto_funnel_diag = pfd if isinstance(pfd, dict) else {}
            except Exception:
                proto_funnel_diag = {}
        camp_lifecycle_diag = {}
        if hasattr(world, "compute_camp_lifecycle_snapshot"):
            try:
                cld = world.compute_camp_lifecycle_snapshot()
                camp_lifecycle_diag = cld if isinstance(cld, dict) else {}
            except Exception:
                camp_lifecycle_diag = {}
        camp_targeting_diag = {}
        if hasattr(world, "compute_camp_targeting_snapshot"):
            try:
                ctd = world.compute_camp_targeting_snapshot()
                camp_targeting_diag = ctd if isinstance(ctd, dict) else {}
            except Exception:
                camp_targeting_diag = {}
        proto_specialization_diag = {}
        if hasattr(world, "compute_proto_specialization_snapshot"):
            try:
                psd = world.compute_proto_specialization_snapshot()
                proto_specialization_diag = psd if isinstance(psd, dict) else {}
            except Exception:
                proto_specialization_diag = {}
        camp_food_diag = {}
        if hasattr(world, "compute_camp_food_snapshot"):
            try:
                cfd = world.compute_camp_food_snapshot()
                camp_food_diag = cfd if isinstance(cfd, dict) else {}
            except Exception:
                camp_food_diag = {}
        communication_diag = {}
        if hasattr(world, "compute_communication_snapshot"):
            try:
                cds = world.compute_communication_snapshot()
                communication_diag = cds if isinstance(cds, dict) else {}
            except Exception:
                communication_diag = {}
        social_encounter_diag = {}
        if hasattr(world, "compute_social_encounter_snapshot"):
            try:
                sed = world.compute_social_encounter_snapshot()
                social_encounter_diag = sed if isinstance(sed, dict) else {}
            except Exception:
                social_encounter_diag = {}
        food_patch_diag = {}
        if hasattr(world, "compute_food_patch_snapshot"):
            try:
                fpd = world.compute_food_patch_snapshot()
                food_patch_diag = fpd if isinstance(fpd, dict) else {}
            except Exception:
                food_patch_diag = {}
        behavior_map_diag = {}
        if hasattr(world, "compute_behavior_map_snapshot"):
            try:
                bmd = world.compute_behavior_map_snapshot()
                behavior_map_diag = bmd if isinstance(bmd, dict) else {}
            except Exception:
                behavior_map_diag = {}
        settlement_progression_diag = {}
        if hasattr(world, "compute_settlement_progression_snapshot"):
            try:
                spd = world.compute_settlement_progression_snapshot()
                settlement_progression_diag = spd if isinstance(spd, dict) else {}
            except Exception:
                settlement_progression_diag = {}
        material_feasibility_diag = {}
        if hasattr(world, "compute_material_feasibility_snapshot"):
            try:
                mfd = world.compute_material_feasibility_snapshot()
                material_feasibility_diag = mfd if isinstance(mfd, dict) else {}
            except Exception:
                material_feasibility_diag = {}

        snapshot = {
            "tick": int(getattr(world, "tick", 0)),
            "world": {
                "population": len(alive_agents),
                "villages": len(villages),
                "avg_hunger": round(avg_hunger, 2),
                "stored_food": int(storage_food),
                "stored_wood": int(storage_wood),
                "stored_stone": int(storage_stone),
                "village_population_resident": int(sum(v["resident"] for v in affiliation_by_village.values())),
                "village_population_attached": int(sum(v["attached"] for v in affiliation_by_village.values())),
                "village_population_transient": int(sum(v["transient"] for v in affiliation_by_village.values())),
                "agents_unaffiliated": int(agents_unaffiliated),
                "village_affiliation_by_village": {
                    uid: {
                        "resident": int(counts.get("resident", 0)),
                        "attached": int(counts.get("attached", 0)),
                        "transient": int(counts.get("transient", 0)),
                    }
                    for uid, counts in sorted(affiliation_by_village.items(), key=lambda item: item[0])
                },
                "buildings_by_type": {k: int(v) for k, v in sorted(buildings_by_type.items(), key=lambda x: x[0])},
                "under_construction_count": int(under_construction),
                "transport_network_counts": {k: int(v) for k, v in sorted(transport_counts.items(), key=lambda x: x[0])},
                "food_patch_count": int(food_patch_diag.get("food_patch_count", 0)),
                "food_patch_total_area": int(food_patch_diag.get("food_patch_total_area", 0)),
                "food_patch_food_spawned": int(food_patch_diag.get("food_patch_food_spawned", 0)),
            },
            "logistics": {
                "internal_transfers_count": int(logistics_internal_transfers),
                "construction_deliveries_count": int(construction_deliveries),
                "blocked_construction_count": int(blocked_construction),
                "storage_utilization_avg": round(
                    sum(storage_utilization) / max(1, len(storage_utilization)),
                    3,
                ),
            },
            "production": production,
            "cognition_society": {
                "active_intentions_by_type": {k: int(v) for k, v in sorted(intention_counts.items(), key=lambda x: x[0])},
                "blocked_intentions_count": int(blocked_intentions),
                "food_crisis_count": int(food_crisis_count),
                "survival_pressure_avg": round(
                    sum(survival_pressure_samples) / max(1, len(survival_pressure_samples)),
                    3,
                ),
                "physiology_global": {
                    "avg_sleep_need": round(sum(sleep_need_samples) / max(1, len(sleep_need_samples)), 3),
                    "avg_fatigue": round(sum(fatigue_samples) / max(1, len(fatigue_samples)), 3),
                    "avg_health": round(sum(health_samples) / max(1, len(health_samples)), 3),
                    "high_sleep_need_agents": int(high_sleep_need_agents),
                    "high_fatigue_agents": int(high_fatigue_agents),
                    "low_health_agents": int(low_health_agents),
                },
                "happiness_global": {
                    "avg_happiness": round(sum(happiness_samples) / max(1, len(happiness_samples)), 3),
                    "low_happiness_agents": int(low_happiness_agents),
                    "high_happiness_agents": int(high_happiness_agents),
                },
                "specialists_by_role": {k: int(v) for k, v in sorted(specialists_by_role.items(), key=lambda x: x[0])},
                "top_social_influence_agents": top_social,
                "village_proto_culture": proto_culture_summary[:8],
                "leadership_changes": int(self._leadership_changes),
                "workforce_target_mix_by_village": dict(sorted(workforce_target_mix_by_village.items(), key=lambda item: item[0])),
                "workforce_actual_mix_by_village": dict(sorted(workforce_actual_mix_by_village.items(), key=lambda item: item[0])),
                "workforce_role_deficits_by_village": dict(sorted(workforce_role_deficits_by_village.items(), key=lambda item: item[0])),
                "workforce_pressure_by_village": dict(sorted(workforce_pressure_by_village.items(), key=lambda item: item[0])),
                "workforce_realization_global": dict(workforce_realization.get("global", {})) if isinstance(workforce_realization, dict) else {},
                "workforce_realization_by_village": dict(workforce_realization.get("by_village", {})) if isinstance(workforce_realization, dict) else {},
                "workforce_affiliation_contribution": dict(workforce_realization.get("affiliation_contribution", {})) if isinstance(workforce_realization, dict) else {},
                "workforce_realization_window_ticks": int(workforce_realization.get("window_ticks", 0)) if isinstance(workforce_realization, dict) else 0,
                "support_role_assignment_diagnostics_global": dict(support_role_assignment_diagnostics_global),
                "support_role_assignment_diagnostics_by_village": dict(sorted(support_role_assignment_diagnostics_by_village.items(), key=lambda item: item[0])),
                "support_role_relaxation_diagnostics_global": dict(support_role_relaxation_diagnostics_global),
                "support_role_relaxation_diagnostics_by_village": dict(sorted(support_role_relaxation_diagnostics_by_village.items(), key=lambda item: item[0])),
                "reserved_civic_support_global": dict(reserved_civic_support_global),
                "reserved_civic_support_by_village": dict(sorted(reserved_civic_support_by_village.items(), key=lambda item: item[0])),
                "reserved_civic_support_gate_diagnostics_global": dict(reserved_civic_support_gate_diagnostics_global),
                "reserved_civic_support_gate_diagnostics_by_village": dict(sorted(reserved_civic_support_gate_diagnostics_by_village.items(), key=lambda item: item[0])),
                "assignment_to_action_gap_global": dict(assignment_gap.get("global", {})) if isinstance(assignment_gap, dict) else {},
                "assignment_to_action_gap_by_village": dict(assignment_gap.get("by_village", {})) if isinstance(assignment_gap, dict) else {},
                "assignment_to_action_gap_by_affiliation": dict(assignment_gap.get("by_affiliation", {})) if isinstance(assignment_gap, dict) else {},
                "task_completion_diagnostics_global": dict(task_completion.get("global", {})) if isinstance(task_completion, dict) else {},
                "task_completion_diagnostics_by_village": dict(task_completion.get("by_village", {})) if isinstance(task_completion, dict) else {},
                "task_completion_diagnostics_by_affiliation": dict(task_completion.get("by_affiliation", {})) if isinstance(task_completion, dict) else {},
                "delivery_diagnostics_global": dict(delivery_diagnostics.get("global", {})) if isinstance(delivery_diagnostics, dict) else {},
                "delivery_diagnostics_by_role": dict(delivery_diagnostics.get("by_role", {})) if isinstance(delivery_diagnostics, dict) else {},
                "delivery_diagnostics_by_village": dict(delivery_diagnostics.get("by_village", {})) if isinstance(delivery_diagnostics, dict) else {},
                "housing_construction_diagnostics_global": dict(housing_diagnostics.get("global", {})) if isinstance(housing_diagnostics, dict) else {},
                "housing_construction_diagnostics_by_village": dict(housing_diagnostics.get("by_village", {})) if isinstance(housing_diagnostics, dict) else {},
                "housing_siting_rejection_global": dict(housing_siting_rejection.get("global", {})) if isinstance(housing_siting_rejection, dict) else {},
                "housing_siting_rejection_by_village": dict(housing_siting_rejection.get("by_village", {})) if isinstance(housing_siting_rejection, dict) else {},
                "housing_path_coherence_global": dict(housing_path_coherence.get("global", {})) if isinstance(housing_path_coherence, dict) else {},
                "housing_path_coherence_by_village": dict(housing_path_coherence.get("by_village", {})) if isinstance(housing_path_coherence, dict) else {},
                "builder_self_supply_diagnostics": dict(builder_self_supply) if isinstance(builder_self_supply, dict) else {},
                "builder_self_supply_gate_diagnostics_global": dict(builder_self_supply_gate.get("global", {})) if isinstance(builder_self_supply_gate, dict) else {},
                "builder_self_supply_gate_diagnostics_by_village": dict(builder_self_supply_gate.get("by_village", {})) if isinstance(builder_self_supply_gate, dict) else {},
                "movement_diagnostics_global": dict(movement_diagnostics.get("global", {})) if isinstance(movement_diagnostics, dict) else {},
                "movement_diagnostics_by_role": dict(movement_diagnostics.get("by_role", {})) if isinstance(movement_diagnostics, dict) else {},
                "movement_diagnostics_by_task": dict(movement_diagnostics.get("by_task", {})) if isinstance(movement_diagnostics, dict) else {},
                "movement_diagnostics_by_transport_context": dict(movement_diagnostics.get("by_transport_context", {})) if isinstance(movement_diagnostics, dict) else {},
                "movement_diagnostics_by_village": dict(movement_diagnostics.get("by_village", {})) if isinstance(movement_diagnostics, dict) else {},
                "movement_diagnostics_top_oscillating_agents": list(movement_diagnostics.get("top_oscillating_agents", [])) if isinstance(movement_diagnostics, dict) else [],
                "movement_congestion_global": dict(movement_diagnostics.get("movement_congestion_global", {})) if isinstance(movement_diagnostics, dict) else {},
                "movement_congestion_by_role": dict(movement_diagnostics.get("movement_congestion_by_role", {})) if isinstance(movement_diagnostics, dict) else {},
                "movement_congestion_by_task": dict(movement_diagnostics.get("movement_congestion_by_task", {})) if isinstance(movement_diagnostics, dict) else {},
                "movement_congestion_by_transport_context": dict(movement_diagnostics.get("movement_congestion_by_transport_context", {})) if isinstance(movement_diagnostics, dict) else {},
                "top_congested_tiles": list(movement_diagnostics.get("top_congested_tiles", [])) if isinstance(movement_diagnostics, dict) else [],
                "social_cohesion_global": dict(social_cohesion_global),
                "social_cohesion_by_village": dict(sorted(social_cohesion_by_village.items(), key=lambda item: item[0])),
                "residence_stabilization_global": dict(residence_stabilization.get("global", {})) if isinstance(residence_stabilization, dict) else {},
                "residence_stabilization_by_village": dict(residence_stabilization.get("by_village", {})) if isinstance(residence_stabilization, dict) else {},
                "resident_conversion_gate_diagnostics_global": dict(resident_conversion_gate.get("global", {})) if isinstance(resident_conversion_gate, dict) else {},
                "resident_conversion_gate_diagnostics_by_village": dict(resident_conversion_gate.get("by_village", {})) if isinstance(resident_conversion_gate, dict) else {},
                "recovery_diagnostics_global": dict(recovery_diag.get("global", {})) if isinstance(recovery_diag, dict) else {},
                "recovery_diagnostics_by_role": dict(recovery_diag.get("by_role", {})) if isinstance(recovery_diag, dict) else {},
                "recovery_diagnostics_by_village": dict(recovery_diag.get("by_village", {})) if isinstance(recovery_diag, dict) else {},
                "proto_community_count": int(progression_diag.get("proto_community_count", 0)) if isinstance(progression_diag, dict) else 0,
                "proto_community_agents": int(progression_diag.get("proto_community_agents", 0)) if isinstance(progression_diag, dict) else 0,
                "camps_count": int(progression_diag.get("camps_count", 0)) if isinstance(progression_diag, dict) else 0,
                "active_camps_count": int(progression_diag.get("active_camps_count", 0)) if isinstance(progression_diag, dict) else 0,
                "camp_return_events": int(progression_diag.get("camp_return_events", 0)) if isinstance(progression_diag, dict) else 0,
                "camp_rest_events": int(progression_diag.get("camp_rest_events", 0)) if isinstance(progression_diag, dict) else 0,
                "house_vs_camp_population": dict(progression_diag.get("house_vs_camp_population", {})) if isinstance(progression_diag, dict) else {},
                "early_road_suppressed_count": int(progression_diag.get("early_road_suppressed_count", 0)) if isinstance(progression_diag, dict) else 0,
                "road_priority_deferred_reasons": dict(progression_diag.get("road_priority_deferred_reasons", {})) if isinstance(progression_diag, dict) else {},
                "road_built_with_purpose_count": int(progression_diag.get("road_built_with_purpose_count", 0)) if isinstance(progression_diag, dict) else 0,
                "road_build_suppressed_no_purpose": int(progression_diag.get("road_build_suppressed_no_purpose", 0)) if isinstance(progression_diag, dict) else 0,
                "road_build_suppressed_reasons": dict(progression_diag.get("road_build_suppressed_reasons", {})) if isinstance(progression_diag, dict) else {},
                "settlement_stage_counts": dict(progression_diag.get("settlement_stage_counts", {})) if isinstance(progression_diag, dict) else {},
                "progression_by_village": dict(progression_diag.get("by_village", {})) if isinstance(progression_diag, dict) else {},
                "construction_situated_diagnostics": dict(world.compute_situated_construction_snapshot()) if hasattr(world, "compute_situated_construction_snapshot") else {},
                "settlement_bottleneck_diagnostics": dict(world.compute_settlement_bottleneck_snapshot()) if hasattr(world, "compute_settlement_bottleneck_snapshot") else {},
                "proto_community_funnel_global": dict(proto_funnel_diag.get("global", {})) if isinstance(proto_funnel_diag, dict) else {},
                "proto_community_funnel_by_region": dict(proto_funnel_diag.get("by_region", {})) if isinstance(proto_funnel_diag, dict) else {},
                "camp_lifecycle_global": dict(camp_lifecycle_diag.get("global", {})) if isinstance(camp_lifecycle_diag, dict) else {},
                "camp_lifecycle_by_region": dict(camp_lifecycle_diag.get("by_region", {})) if isinstance(camp_lifecycle_diag, dict) else {},
                "camp_targeting_diagnostics": dict(camp_targeting_diag) if isinstance(camp_targeting_diag, dict) else {},
                "camp_food_metrics": dict(camp_food_diag) if isinstance(camp_food_diag, dict) else {},
                "communication_knowledge_global": dict(communication_diag) if isinstance(communication_diag, dict) else {},
                "social_encounter_global": {
                    **(dict(social_encounter_diag) if isinstance(social_encounter_diag, dict) else {}),
                    "familiarity_relationships_count": int(familiarity_relationships_count),
                    "avg_familiarity_score": round(
                        float(sum(familiarity_scores) / max(1, len(familiarity_scores))),
                        3,
                    ),
                },
                "social_proto_coordination_metrics": {
                    "familiar_communication_bonus_applied": int((social_encounter_diag or {}).get("familiar_communication_bonus_applied", 0)),
                    "familiar_zone_reinforcement_events": int((social_encounter_diag or {}).get("familiar_zone_reinforcement_events", 0)),
                    "familiar_camp_support_bias_events": int((social_encounter_diag or {}).get("familiar_camp_support_bias_events", 0)),
                    "familiar_loop_continuity_bonus": int((social_encounter_diag or {}).get("familiar_loop_continuity_bonus", 0)),
                    "familiar_anchor_exploration_events": int((social_encounter_diag or {}).get("familiar_anchor_exploration_events", 0)),
                    "familiar_zone_score_updates": int((social_encounter_diag or {}).get("familiar_zone_score_updates", 0)),
                    "familiar_zone_score_decay": int((social_encounter_diag or {}).get("familiar_zone_score_decay", 0)),
                    "familiar_zone_saturation_clamps": int((social_encounter_diag or {}).get("familiar_zone_saturation_clamps", 0)),
                    "dense_area_social_bias_reductions": int((social_encounter_diag or {}).get("dense_area_social_bias_reductions", 0)),
                    "familiar_zone_decay_due_to_low_payoff": int((social_encounter_diag or {}).get("familiar_zone_decay_due_to_low_payoff", 0)),
                    "overcrowded_familiar_bias_suppressed": int((social_encounter_diag or {}).get("overcrowded_familiar_bias_suppressed", 0)),
                    "density_safe_loop_bonus_reduced_count": int((social_encounter_diag or {}).get("density_safe_loop_bonus_reduced_count", 0)),
                },
                "lifespan_continuity_global": {
                    "avg_useful_memory_age": round(float(sum(useful_memory_ages) / max(1, len(useful_memory_ages))), 3),
                    "repeated_successful_loop_count": int((settlement_progression_diag or {}).get("repeated_successful_loop_count", 0)),
                    "routine_persistence_ticks": int((settlement_progression_diag or {}).get("routine_persistence_ticks", 0)),
                    "routine_abandonment_after_failure": int((settlement_progression_diag or {}).get("routine_abandonment_after_failure", 0)),
                    "routine_abandonment_after_success": int((settlement_progression_diag or {}).get("routine_abandonment_after_success", 0)),
                    "confirmed_memory_reinforcements": int((communication_diag or {}).get("confirmed_memory_reinforcements", 0)),
                    "direct_memory_invalidations": int((communication_diag or {}).get("direct_memory_invalidations", 0)),
                    "average_agent_age_alive": round(float(sum(agent_ages) / max(1, len(agent_ages))), 3),
                },
                "proto_specialization_global": dict(proto_specialization_diag) if isinstance(proto_specialization_diag, dict) else {},
                "behavior_map_global": dict(behavior_map_diag) if isinstance(behavior_map_diag, dict) else {},
                "settlement_progression_metrics": dict(settlement_progression_diag) if isinstance(settlement_progression_diag, dict) else {},
                "material_feasibility_metrics": dict(material_feasibility_diag) if isinstance(material_feasibility_diag, dict) else {},
            },
            "llm_reflection": {
                "reflection_trigger_detected_count": int(reflection_stats.get("reflection_trigger_detected_count", 0)),
                "reflection_attempt_count": int(reflection_stats.get("reflection_attempt_count", 0)),
                "reflection_executed_count": int(reflection_stats.get("reflection_executed_count", 0)),
                "reflection_success_count": int(reflection_stats.get("reflection_success_count", 0)),
                "reflection_rejection_count": int(reflection_stats.get("reflection_rejection_count", 0)),
                "reflection_fallback_count": int(reflection_stats.get("reflection_fallback_count", 0)),
                "reflection_reason_counts": dict(reflection_stats.get("reflection_reason_counts", {})),
                "reflection_role_counts": dict(reflection_stats.get("reflection_role_counts", {})),
                "reflection_executed_reason_counts": dict(reflection_stats.get("reflection_executed_reason_counts", {})),
                "reflection_executed_role_counts": dict(reflection_stats.get("reflection_executed_role_counts", {})),
                "reflection_skip_reason_counts": dict(reflection_stats.get("reflection_skip_reason_counts", {})),
                "reflection_outcome_reason_counts": dict(reflection_stats.get("reflection_outcome_reason_counts", {})),
                "reflection_rejection_reason_counts": dict(reflection_stats.get("reflection_rejection_reason_counts", {})),
                "reflection_fallback_reason_counts": dict(reflection_stats.get("reflection_fallback_reason_counts", {})),
                "reflection_accepted_source_counts": dict(reflection_stats.get("reflection_accepted_source_counts", {})),
                "survival_reflection_suppressed_count": int(reflection_stats.get("survival_reflection_suppressed_count", 0)),
                "survival_biased_reflection_applied_count": int(reflection_stats.get("survival_biased_reflection_applied_count", 0)),
                "llm_calls_per_tick": dict(reflection_stats.get("llm_calls_per_tick", {})),
                "llm_calls_per_agent_top": [
                    {"agent_id": aid, "calls": int(c)}
                    for aid, c in sorted(
                        (reflection_stats.get("llm_calls_per_agent") or {}).items(),
                        key=lambda item: (-int(item[1]), str(item[0])),
                    )[:10]
                ],
            },
            "innovation": {
                "proto_asset_proposal_count": int(reflection_stats.get("proto_asset_proposal_count", 0)),
                "admissible_proposal_count": int(reflection_stats.get("admissible_proposal_count", 0)),
                "rejected_proposal_count": int(reflection_stats.get("rejected_proposal_count", 0)),
                "proto_asset_proposal_rejection_count": int(reflection_stats.get("proto_asset_proposal_rejection_count", 0)),
                "proposal_counts_by_status": dict(reflection_stats.get("proposal_counts_by_status", {})),
                "proposal_counts_by_reason": dict(reflection_stats.get("proto_asset_proposal_counts_by_reason", {})),
                "proposal_counts_by_kind": dict(reflection_stats.get("proto_asset_proposal_counts_by_kind", {})),
                "proposal_counts_by_source": dict(reflection_stats.get("proto_asset_proposal_counts_by_source", {})),
                "proposal_counts_by_effect": dict(reflection_stats.get("proposal_counts_by_effect", {})),
                "proposal_counts_by_category": dict(reflection_stats.get("proposal_counts_by_category", {})),
                "proposal_rejection_reasons": dict(reflection_stats.get("proto_asset_proposal_rejection_reasons", {})),
                "prototype_attempt_count": int(reflection_stats.get("prototype_attempt_count", 0)),
                "prototype_built_count": int(reflection_stats.get("prototype_built_count", 0)),
                "prototype_failed_count": int(reflection_stats.get("prototype_failed_count", 0)),
                "prototype_counts_by_category": dict(reflection_stats.get("prototype_counts_by_category", {})),
                "prototype_counts_by_effect": dict(reflection_stats.get("prototype_counts_by_effect", {})),
                "prototype_failure_reasons": dict(reflection_stats.get("prototype_failure_reasons", {})),
                "prototype_useful_count": int(reflection_stats.get("prototype_useful_count", 0)),
                "prototype_neutral_count": int(reflection_stats.get("prototype_neutral_count", 0)),
                "prototype_ineffective_count": int(reflection_stats.get("prototype_ineffective_count", 0)),
                "prototype_usefulness_by_effect": dict(reflection_stats.get("prototype_usefulness_by_effect", {})),
                "prototype_usefulness_by_category": dict(reflection_stats.get("prototype_usefulness_by_category", {})),
                "known_invention_entry_count": int(known_invention_entry_count),
                "agents_with_known_inventions": int(agents_with_known_inventions),
                "invention_knowledge_by_source": {k: int(v) for k, v in sorted(invention_knowledge_by_source.items(), key=lambda x: x[0])},
                "invention_knowledge_by_category": {k: int(v) for k, v in sorted(invention_knowledge_by_category.items(), key=lambda x: x[0])},
                "recent_diffused_inventions": recent_diffused_inventions[:8],
                "world_proto_asset_registry_size": int(len(getattr(world, "proto_asset_proposals", []) or [])),
                "world_proto_asset_instance_count": int(len(getattr(world, "proto_asset_prototypes", []) or [])),
                "recent_useful_prototypes": [
                    {
                        "instance_id": str(p.get("instance_id", "")),
                        "proposal_id": str(p.get("proposal_id", "")),
                        "effect": str(p.get("effect", "")),
                        "category": str(p.get("category", "")),
                        "evaluation_tick": int(p.get("evaluation_tick", -1)),
                        "usefulness_score": float(p.get("usefulness_score", 0.0)),
                    }
                    for p in sorted(
                        [
                            proto for proto in (getattr(world, "proto_asset_prototypes", []) or [])
                            if isinstance(proto, dict) and str(proto.get("usefulness_status", "")) == "useful"
                        ],
                        key=lambda rec: (-int(rec.get("evaluation_tick", -1)), str(rec.get("instance_id", ""))),
                    )[:5]
                ],
            },
            "specialization_diagnostics": specialization,
        }
        return snapshot
