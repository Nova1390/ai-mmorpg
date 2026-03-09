from __future__ import annotations

from collections import Counter, deque
from typing import Any, Deque, Dict, List, Tuple


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
        known_invention_entry_count = 0
        agents_with_known_inventions = 0
        invention_knowledge_by_source: Counter[str] = Counter()
        invention_knowledge_by_category: Counter[str] = Counter()
        recent_diffused_inventions: List[Dict[str, Any]] = []
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
        recent_diffused_inventions.sort(
            key=lambda rec: (-int(rec.get("learned_tick", 0)), str(rec.get("agent_id", "")), str(rec.get("proposal_id", "")))
        )

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

        snapshot = {
            "tick": int(getattr(world, "tick", 0)),
            "world": {
                "population": len(alive_agents),
                "villages": len(villages),
                "avg_hunger": round(avg_hunger, 2),
                "stored_food": int(storage_food),
                "stored_wood": int(storage_wood),
                "stored_stone": int(storage_stone),
                "buildings_by_type": {k: int(v) for k, v in sorted(buildings_by_type.items(), key=lambda x: x[0])},
                "under_construction_count": int(under_construction),
                "transport_network_counts": {k: int(v) for k, v in sorted(transport_counts.items(), key=lambda x: x[0])},
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
                "specialists_by_role": {k: int(v) for k, v in sorted(specialists_by_role.items(), key=lambda x: x[0])},
                "top_social_influence_agents": top_social,
                "village_proto_culture": proto_culture_summary[:8],
                "leadership_changes": int(self._leadership_changes),
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
        }
        return snapshot
