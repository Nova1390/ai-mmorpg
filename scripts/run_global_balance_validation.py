from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from systems.global_balance_runner import (
    GlobalBalanceScenarioConfig,
    GlobalBalanceThresholds,
    aggregate_global_balance_results,
    run_global_balance_scenario,
)


def _family_configs(
    *,
    family_name: str,
    seeds: List[int],
    ticks: int,
    snapshot_interval: int,
    history_limit: int,
) -> List[GlobalBalanceScenarioConfig]:
    family_name = str(family_name)
    cfgs: List[GlobalBalanceScenarioConfig] = []
    for seed in seeds:
        if family_name == "baseline":
            cfgs.append(
                GlobalBalanceScenarioConfig(
                    name=f"baseline_seed_{seed}",
                    seed=int(seed),
                    width=72,
                    height=72,
                    initial_population=40,
                    ticks=int(ticks),
                    snapshot_interval=int(snapshot_interval),
                    history_limit=int(history_limit),
                    llm_enabled=False,
                    food_multiplier=1.0,
                )
            )
        elif family_name == "food_stress":
            cfgs.append(
                GlobalBalanceScenarioConfig(
                    name=f"food_stress_seed_{seed}",
                    seed=int(seed),
                    width=72,
                    height=72,
                    initial_population=45,
                    ticks=int(ticks),
                    snapshot_interval=int(snapshot_interval),
                    history_limit=int(history_limit),
                    llm_enabled=False,
                    food_multiplier=0.65,
                )
            )
        elif family_name == "population_variant":
            cfgs.append(
                GlobalBalanceScenarioConfig(
                    name=f"population_variant_seed_{seed}",
                    seed=int(seed),
                    width=72,
                    height=72,
                    initial_population=55,
                    ticks=int(ticks),
                    snapshot_interval=int(snapshot_interval),
                    history_limit=int(history_limit),
                    llm_enabled=False,
                    food_multiplier=1.0,
                )
            )
        elif family_name == "reduced_pressure":
            cfgs.append(
                GlobalBalanceScenarioConfig(
                    name=f"reduced_pressure_seed_{seed}",
                    seed=int(seed),
                    width=72,
                    height=72,
                    initial_population=40,
                    ticks=int(ticks),
                    snapshot_interval=int(snapshot_interval),
                    history_limit=int(history_limit),
                    llm_enabled=False,
                    food_multiplier=1.2,
                )
            )
        else:
            raise ValueError(f"Unknown scenario family: {family_name}")
    return cfgs


def _write_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run multi-scenario global stability/emergence validation.")
    parser.add_argument("--out-dir", type=str, default="analysis_outputs")
    parser.add_argument("--ticks", type=int, default=1200)
    parser.add_argument("--snapshot-interval", type=int, default=10)
    parser.add_argument("--history-limit", type=int, default=300)
    parser.add_argument("--seeds", type=int, nargs="+", default=[4242, 5151, 6262])
    parser.add_argument("--include-reduced-pressure", action="store_true")
    parser.add_argument("--min-legit-village-population", type=int, default=2)
    parser.add_argument("--min-legit-leader-village-population", type=int, default=3)
    parser.add_argument("--early-extinction-threshold-tick", type=int, default=200)
    parser.add_argument("--early-mass-death-threshold-ratio", type=float, default=0.5)
    args = parser.parse_args()

    thresholds = GlobalBalanceThresholds(
        min_legit_village_population=max(1, int(args.min_legit_village_population)),
        min_legit_leader_village_population=max(1, int(args.min_legit_leader_village_population)),
        early_extinction_threshold_tick=max(1, int(args.early_extinction_threshold_tick)),
        early_mass_death_threshold_ratio=max(0.0, min(1.0, float(args.early_mass_death_threshold_ratio))),
    )

    families = ["baseline", "food_stress", "population_variant"]
    if bool(args.include_reduced_pressure):
        families.append("reduced_pressure")

    out_dir = Path(args.out_dir)
    family_artifacts: Dict[str, Dict] = {}

    for family in families:
        runs: List[Dict] = []
        for cfg in _family_configs(
            family_name=family,
            seeds=[int(s) for s in args.seeds],
            ticks=int(args.ticks),
            snapshot_interval=int(args.snapshot_interval),
            history_limit=int(args.history_limit),
        ):
            run_payload = run_global_balance_scenario(cfg, thresholds=thresholds)
            runs.append(run_payload)

        family_payload = aggregate_global_balance_results(
            scenario_family=family,
            runs=runs,
            thresholds=thresholds,
        )
        family_artifacts[family] = family_payload

    mapping = {
        "baseline": "sim_global_balance_baseline.json",
        "food_stress": "sim_global_balance_food_stress.json",
        "population_variant": "sim_global_balance_population_variant.json",
        "reduced_pressure": "sim_global_balance_reduced_pressure.json",
    }

    written = []
    for family, payload in family_artifacts.items():
        fname = mapping.get(family, f"sim_global_balance_{family}.json")
        fpath = out_dir / fname
        _write_json(fpath, payload)
        written.append(str(fpath))

    summary_payload = {
        "analysis_thresholds": {
            "min_legit_village_population": int(thresholds.min_legit_village_population),
            "min_legit_leader_village_population": int(thresholds.min_legit_leader_village_population),
            "early_extinction_threshold_tick": int(thresholds.early_extinction_threshold_tick),
            "early_mass_death_threshold_ratio": float(thresholds.early_mass_death_threshold_ratio),
        },
        "scenario_families": family_artifacts,
        "written_files": written,
    }
    summary_path = out_dir / "sim_global_balance_summary.json"
    _write_json(summary_path, summary_payload)

    print("Global balance validation completed.")
    for p in written:
        print(p)
    print(str(summary_path))


if __name__ == "__main__":
    main()
