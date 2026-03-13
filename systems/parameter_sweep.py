from __future__ import annotations

import hashlib
import itertools
import json
import random
from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, Iterable, List, Sequence, Tuple


@dataclass(frozen=True)
class SweepConfig:
    config_id: str
    parameters: Dict[str, float]


DEFAULT_SWEEP_RANGES: Dict[str, Sequence[float]] = {
    "food_regeneration_rate": (0.8, 1.0, 1.2, 1.4),
    "wild_food_density": (0.8, 1.0, 1.2),
    "food_patch_cluster_strength": (0.9, 1.0, 1.15),
    "food_patch_distribution_variance": (0.9, 1.0, 1.2),
    "hunger_decay_rate": (0.9, 1.0, 1.1),
    "food_value_per_unit": (0.9, 1.0, 1.1),
    "critical_hunger_threshold": (30.0, 34.0, 38.0),
    "eat_trigger_threshold": (46.0, 50.0, 54.0),
    "routine_success_extension_ticks": (2.0, 3.0, 4.0),
    "routine_persistence_bias": (0.9, 1.0, 1.1),
    "camp_food_buffer_capacity": (0.75, 1.0, 1.25),
    "camp_food_access_radius": (2.0, 3.0, 4.0),
    "house_domestic_food_capacity": (0.75, 1.0, 1.25),
}


def _config_id_for_parameters(parameters: Dict[str, float]) -> str:
    canonical = json.dumps({k: float(parameters[k]) for k in sorted(parameters.keys())}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:12]


def generate_sweep_configs(
    *,
    ranges: Dict[str, Sequence[float]],
    max_configs: int = 32,
    deterministic_seed: int = 1337,
) -> List[SweepConfig]:
    keys = sorted(str(k) for k in ranges.keys())
    value_lists: List[Sequence[float]] = [tuple(float(v) for v in ranges[k]) for k in keys]
    counts = [len(v) for v in value_lists]
    total = 1
    for c in counts:
        total *= int(max(1, c))

    def _decode_index(index: int) -> Dict[str, float]:
        remainder = int(index)
        out: Dict[str, float] = {}
        for i in range(len(keys) - 1, -1, -1):
            vals = value_lists[i]
            base = max(1, len(vals))
            pick = int(remainder % base)
            remainder //= base
            out[keys[i]] = float(vals[pick])
        return out

    chosen: List[Dict[str, float]] = []
    limit = int(max_configs)
    if total <= limit:
        for idx in range(total):
            chosen.append(_decode_index(idx))
    else:
        rng = random.Random(int(deterministic_seed))
        sampled = sorted(rng.sample(range(total), limit))
        for idx in sampled:
            chosen.append(_decode_index(int(idx)))
    out: List[SweepConfig] = []
    for params in chosen:
        out.append(SweepConfig(config_id=_config_id_for_parameters(params), parameters=params))
    return out


def summarize_family_aggregate(aggregate: Dict[str, Any]) -> Dict[str, float]:
    return {
        "avg_final_population": float(aggregate.get("avg_final_population", 0.0)),
        "avg_active_camps_final": float(aggregate.get("avg_active_camps_final", 0.0)),
        "extinction_run_ratio": float(aggregate.get("extinction_run_ratio", 0.0)),
        "avg_useful_memory_age": float(aggregate.get("avg_useful_memory_age", 0.0)),
        "avg_repeated_successful_loop_count": float(aggregate.get("avg_repeated_successful_loop_count", 0.0)),
        "avg_routine_persistence_ticks": float(aggregate.get("avg_routine_persistence_ticks", 0.0)),
        "avg_active_cultural_practices": float(aggregate.get("avg_active_cultural_practices", 0.0)),
        "avg_cultural_practices_reinforced": float(aggregate.get("avg_cultural_practices_reinforced", 0.0)),
        "avg_farm_sites_created": float(aggregate.get("avg_farm_sites_created", 0.0)),
        "avg_farm_work_events": float(aggregate.get("avg_farm_work_events", 0.0)),
        "avg_local_food_surplus_rate": float(aggregate.get("avg_local_food_surplus_rate", 0.0)),
        "avg_storage_emergence_attempts": float(aggregate.get("avg_storage_emergence_attempts", 0.0)),
        "avg_wood_available_world_total": float(aggregate.get("avg_wood_available_world_total", 0.0)),
        "avg_wood_gathered_total": float(aggregate.get("avg_wood_gathered_total", 0.0)),
        "avg_wood_respawned_total": float(aggregate.get("avg_wood_respawned_total", 0.0)),
        "avg_wood_shortage_events": float(aggregate.get("avg_wood_shortage_events", 0.0)),
        "avg_local_wood_pressure": float(aggregate.get("avg_local_wood_pressure", 0.0)),
        "avg_construction_sites_created": float(aggregate.get("avg_construction_sites_created", 0.0)),
        "avg_active_construction_sites": float(aggregate.get("avg_active_construction_sites", 0.0)),
        "avg_partially_built_sites_count": float(aggregate.get("avg_partially_built_sites_count", 0.0)),
        "avg_construction_completed_count": float(aggregate.get("avg_construction_completed_count", 0.0)),
        "avg_construction_material_delivery_failures": float(
            aggregate.get("avg_construction_material_delivery_failures", 0.0)
        ),
        "avg_construction_material_shortage_blocks": float(
            aggregate.get("avg_construction_material_shortage_blocks", 0.0)
        ),
        "avg_houses_completed_count": float(aggregate.get("avg_houses_completed_count", 0.0)),
        "avg_storage_completed_count": float(aggregate.get("avg_storage_completed_count", 0.0)),
        "avg_storage_completion_rate": float(aggregate.get("avg_storage_completion_rate", 0.0)),
        "avg_construction_delivery_attempts": float(aggregate.get("avg_construction_delivery_attempts", 0.0)),
        "avg_construction_delivery_successes": float(aggregate.get("avg_construction_delivery_successes", 0.0)),
        "avg_construction_delivery_failures": float(aggregate.get("avg_construction_delivery_failures", 0.0)),
        "avg_construction_delivery_to_site_events": float(
            aggregate.get("avg_construction_delivery_to_site_events", 0.0)
        ),
        "avg_construction_delivery_to_wrong_target_or_drift": float(
            aggregate.get("avg_construction_delivery_to_wrong_target_or_drift", 0.0)
        ),
        "avg_construction_delivery_avg_distance_to_site": float(
            aggregate.get("avg_construction_delivery_avg_distance_to_site", 0.0)
        ),
        "avg_construction_delivery_avg_distance_to_source": float(
            aggregate.get("avg_construction_delivery_avg_distance_to_source", 0.0)
        ),
        "avg_storage_delivery_failures": float(aggregate.get("avg_storage_delivery_failures", 0.0)),
        "avg_house_delivery_failures": float(aggregate.get("avg_house_delivery_failures", 0.0)),
        "avg_storage_delivery_successes": float(aggregate.get("avg_storage_delivery_successes", 0.0)),
        "avg_house_delivery_successes": float(aggregate.get("avg_house_delivery_successes", 0.0)),
        "avg_construction_site_waiting_for_material_ticks": float(
            aggregate.get("avg_construction_site_waiting_for_material_ticks", 0.0)
        ),
        "avg_construction_site_waiting_for_builder_ticks": float(
            aggregate.get("avg_construction_site_waiting_for_builder_ticks", 0.0)
        ),
        "avg_construction_site_waiting_total_ticks": float(aggregate.get("avg_construction_site_waiting_total_ticks", 0.0)),
        "avg_construction_site_progress_active_ticks": float(
            aggregate.get("avg_construction_site_progress_active_ticks", 0.0)
        ),
        "avg_construction_site_starved_cycles": float(aggregate.get("avg_construction_site_starved_cycles", 0.0)),
        "avg_storage_waiting_for_material_ticks": float(aggregate.get("avg_storage_waiting_for_material_ticks", 0.0)),
        "avg_house_waiting_for_material_ticks": float(aggregate.get("avg_house_waiting_for_material_ticks", 0.0)),
        "avg_storage_waiting_for_builder_ticks": float(aggregate.get("avg_storage_waiting_for_builder_ticks", 0.0)),
        "avg_house_waiting_for_builder_ticks": float(aggregate.get("avg_house_waiting_for_builder_ticks", 0.0)),
        "avg_construction_site_lifetime_ticks_avg": float(aggregate.get("avg_construction_site_lifetime_ticks_avg", 0.0)),
        "avg_construction_site_progress_before_abandon_avg": float(
            aggregate.get("avg_construction_site_progress_before_abandon_avg", 0.0)
        ),
        "avg_construction_site_material_units_delivered_avg": float(
            aggregate.get("avg_construction_site_material_units_delivered_avg", 0.0)
        ),
        "avg_construction_site_material_units_missing_avg": float(
            aggregate.get("avg_construction_site_material_units_missing_avg", 0.0)
        ),
        "avg_construction_site_material_units_required_total": float(
            aggregate.get("avg_construction_site_material_units_required_total", 0.0)
        ),
        "avg_construction_site_material_units_delivered_total": float(
            aggregate.get("avg_construction_site_material_units_delivered_total", 0.0)
        ),
        "avg_construction_site_material_units_remaining": float(
            aggregate.get("avg_construction_site_material_units_remaining", 0.0)
        ),
        "avg_construction_near_complete_sites_count": float(
            aggregate.get("avg_construction_near_complete_sites_count", 0.0)
        ),
        "avg_builder_assigned_site_count": float(aggregate.get("avg_builder_assigned_site_count", 0.0)),
        "avg_builder_site_arrival_count": float(aggregate.get("avg_builder_site_arrival_count", 0.0)),
        "avg_builder_left_site_count": float(aggregate.get("avg_builder_left_site_count", 0.0)),
        "avg_builder_left_site_before_completion_count": float(
            aggregate.get("avg_builder_left_site_before_completion_count", 0.0)
        ),
        "avg_builder_waiting_on_site_ticks_total": float(
            aggregate.get("avg_builder_waiting_on_site_ticks_total", 0.0)
        ),
        "avg_builder_on_site_ticks_total": float(aggregate.get("avg_builder_on_site_ticks_total", 0.0)),
        "avg_builder_work_tick_applied_count": float(
            aggregate.get("avg_builder_work_tick_applied_count", 0.0)
        ),
        "avg_builder_survival_override_during_construction_count": float(
            aggregate.get("avg_builder_survival_override_during_construction_count", 0.0)
        ),
        "avg_builder_redirected_to_storage_during_construction_count": float(
            aggregate.get("avg_builder_redirected_to_storage_during_construction_count", 0.0)
        ),
        "avg_builder_commitment_created_count": float(
            aggregate.get("avg_builder_commitment_created_count", 0.0)
        ),
        "avg_builder_commitment_pause_count": float(
            aggregate.get("avg_builder_commitment_pause_count", 0.0)
        ),
        "avg_builder_commitment_resume_count": float(
            aggregate.get("avg_builder_commitment_resume_count", 0.0)
        ),
        "avg_builder_commitment_completed_count": float(
            aggregate.get("avg_builder_commitment_completed_count", 0.0)
        ),
        "avg_builder_commitment_abandoned_count": float(
            aggregate.get("avg_builder_commitment_abandoned_count", 0.0)
        ),
        "avg_builder_returned_to_same_site_count": float(
            aggregate.get("avg_builder_returned_to_same_site_count", 0.0)
        ),
        "avg_builder_commitment_duration_avg": float(
            aggregate.get("avg_builder_commitment_duration_avg", 0.0)
        ),
        "avg_builder_commitment_resume_delay_avg": float(
            aggregate.get("avg_builder_commitment_resume_delay_avg", 0.0)
        ),
        "avg_construction_site_buildable_ticks_total": float(
            aggregate.get("avg_construction_site_buildable_ticks_total", 0.0)
        ),
        "avg_construction_site_idle_buildable_ticks_total": float(
            aggregate.get("avg_construction_site_idle_buildable_ticks_total", 0.0)
        ),
        "avg_construction_site_buildable_but_idle_ticks_total": float(
            aggregate.get("avg_construction_site_buildable_but_idle_ticks_total", 0.0)
        ),
        "avg_construction_site_waiting_materials_ticks_total": float(
            aggregate.get("avg_construction_site_waiting_materials_ticks_total", 0.0)
        ),
        "avg_construction_site_in_progress_ticks_total": float(
            aggregate.get("avg_construction_site_in_progress_ticks_total", 0.0)
        ),
        "avg_construction_site_distinct_builders_avg": float(
            aggregate.get("avg_construction_site_distinct_builders_avg", 0.0)
        ),
        "avg_construction_site_work_ticks_per_builder_avg": float(
            aggregate.get("avg_construction_site_work_ticks_per_builder_avg", 0.0)
        ),
        "avg_construction_site_delivery_to_work_gap_avg": float(
            aggregate.get("avg_construction_site_delivery_to_work_gap_avg", 0.0)
        ),
        "avg_construction_site_active_age_ticks_avg": float(
            aggregate.get("avg_construction_site_active_age_ticks_avg", 0.0)
        ),
        "avg_construction_site_first_builder_arrival_delay_avg": float(
            aggregate.get("avg_construction_site_first_builder_arrival_delay_avg", 0.0)
        ),
        "avg_construction_site_material_ready_to_first_work_delay_avg": float(
            aggregate.get("avg_construction_site_material_ready_to_first_work_delay_avg", 0.0)
        ),
        "avg_construction_site_completion_time_avg": float(aggregate.get("avg_construction_site_completion_time_avg", 0.0)),
        "avg_construction_time_first_delivery_to_completion_avg": float(
            aggregate.get("avg_construction_time_first_delivery_to_completion_avg", 0.0)
        ),
        "avg_construction_time_first_progress_to_completion_avg": float(
            aggregate.get("avg_construction_time_first_progress_to_completion_avg", 0.0)
        ),
        "avg_construction_completed_after_first_delivery_count": float(
            aggregate.get("avg_construction_completed_after_first_delivery_count", 0.0)
        ),
        "avg_construction_completed_after_started_progress_count": float(
            aggregate.get("avg_construction_completed_after_started_progress_count", 0.0)
        ),
        "avg_house_completion_time_avg": float(aggregate.get("avg_house_completion_time_avg", 0.0)),
        "avg_storage_completion_time_avg": float(aggregate.get("avg_storage_completion_time_avg", 0.0)),
    }


def aggregate_across_families(family_aggregates: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    if not family_aggregates:
        return {}
    keys = sorted(next(iter(family_aggregates.values())).keys())
    out: Dict[str, float] = {}
    for k in keys:
        vals = [float(v.get(k, 0.0)) for v in family_aggregates.values()]
        out[k] = float(mean(vals)) if vals else 0.0
    return out


def is_breakeven_candidate(
    *,
    aggregate_all: Dict[str, float],
    baseline_reference: Dict[str, float],
) -> bool:
    return bool(
        float(aggregate_all.get("extinction_run_ratio", 1.0)) <= 0.0
        and float(aggregate_all.get("avg_repeated_successful_loop_count", 0.0))
        > float(baseline_reference.get("avg_repeated_successful_loop_count", 0.0))
        and float(aggregate_all.get("avg_active_cultural_practices", 0.0)) > 0.0
        and float(aggregate_all.get("avg_final_population", 0.0))
        >= float(baseline_reference.get("avg_final_population", 0.0))
    )


def score_configuration(aggregate_all: Dict[str, float]) -> float:
    return float(
        float(aggregate_all.get("avg_final_population", 0.0)) * 0.35
        + float(aggregate_all.get("avg_active_camps_final", 0.0)) * 0.20
        + float(aggregate_all.get("avg_repeated_successful_loop_count", 0.0)) * 0.20
        + float(aggregate_all.get("avg_active_cultural_practices", 0.0)) * 0.15
        + float(aggregate_all.get("avg_farm_work_events", 0.0)) * 0.05
        + float(aggregate_all.get("avg_local_food_surplus_rate", 0.0)) * 100.0 * 0.05
        - float(aggregate_all.get("extinction_run_ratio", 0.0)) * 100.0
    )


def build_influence_ranking(entries: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = [e for e in entries if isinstance(e, dict)]
    if not rows:
        return []
    baseline = next((e for e in rows if bool(e.get("is_baseline", False))), None)
    base_score = float((baseline or {}).get("score", 0.0))
    impacts: Dict[str, List[float]] = {}
    for row in rows:
        params = row.get("parameters", {})
        if not isinstance(params, dict):
            continue
        delta = float(row.get("score", 0.0)) - base_score
        for k in params.keys():
            impacts.setdefault(str(k), []).append(delta)
    ranking: List[Dict[str, Any]] = []
    for k, values in impacts.items():
        ranking.append(
            {
                "parameter": str(k),
                "avg_score_delta_from_baseline": float(mean(values)) if values else 0.0,
                "samples": int(len(values)),
            }
        )
    ranking.sort(key=lambda x: abs(float(x.get("avg_score_delta_from_baseline", 0.0))), reverse=True)
    return ranking
