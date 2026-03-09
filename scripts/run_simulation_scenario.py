from __future__ import annotations

import argparse
import json
from pathlib import Path

from systems.scenario_runner import run_simulation_scenario


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a deterministic AI-Civ simulation scenario and export observability summary.")
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--width", type=int, default=72)
    parser.add_argument("--height", type=int, default=72)
    parser.add_argument("--population", type=int, default=32)
    parser.add_argument("--ticks", type=int, default=400)
    parser.add_argument("--snapshot-interval", type=int, default=10)
    parser.add_argument("--llm-enabled", action="store_true")
    parser.add_argument(
        "--llm-reflection-mode",
        type=str,
        default="provider_with_stub_fallback",
        choices=["provider_only", "provider_with_stub_fallback", "force_local_stub"],
    )
    parser.add_argument("--disable-llm-stub", action="store_true")
    parser.add_argument("--force-local-stub", action="store_true")
    parser.add_argument("--history-limit", type=int, default=120)
    parser.add_argument("--out", type=str, default="")
    args = parser.parse_args()

    payload = run_simulation_scenario(
        seed=args.seed,
        width=args.width,
        height=args.height,
        initial_population=args.population,
        ticks=args.ticks,
        snapshot_interval=args.snapshot_interval,
        llm_enabled=bool(args.llm_enabled),
        llm_reflection_mode=str(args.llm_reflection_mode),
        llm_stub_enabled=not bool(args.disable_llm_stub),
        llm_force_local_stub=bool(args.force_local_stub),
        history_limit=args.history_limit,
    )

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Scenario report written to: {out_path}")
    else:
        print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
