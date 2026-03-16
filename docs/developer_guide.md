# Developer Guide

## Prerequisites

- Python 3.10+
- `pip`
- Optional: Godot 4.x for observer client

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the Server

```bash
uvicorn server:app --reload
```

Default base URL:
- `http://127.0.0.1:8000`

Useful routes:
- `GET /state`
- `GET /state/static`
- `GET /state/events`
- `GET /debug/metrics`
- `GET /debug/history`

## Run Tests

Run all tests:

```bash
pytest
```

Run contract/schema tests only:

```bash
pytest tests/test_state_contract.py tests/test_state_serializer.py tests/test_events.py
```

## Run Simulation Scenarios

### Single scenario run

```bash
python scripts/run_simulation_scenario.py --ticks 400 --seed 123
```

Write scenario output to file:

```bash
python scripts/run_simulation_scenario.py --ticks 600 --out analysis_outputs/scenario.json
```

### Global balance validation

```bash
python scripts/run_global_balance_validation.py --ticks 1200 --seeds 4242 5151 6262
```

### Parameter sweep

```bash
python scripts/run_parameter_sweep.py --max-configs 24 --ticks 1600
```

### Behavior map validation

```bash
python scripts/run_behavior_map_validation.py --ticks 1200 --seeds 4242 5151 6262
```

## Observer Clients

### Web observer
- Served by FastAPI root route (`/`) from `frontend/index.html`.
- Uses `/state/static` for bootstrap and polls `/state`.

### Godot observer
- Open `godot/project.godot`.
- Run `res://scenes/Main.tscn`.
- `StateClient.gd` fetches static state once and polls runtime state.

## Repository Structure

- `server.py`: FastAPI transport + startup tick task
- `world.py`: simulation state and tick update orchestration
- `agent.py`: agent behavior/state updates
- `brain.py`: decision logic (rule-based + optional LLM integration)
- `state_serializer.py`: `/state` and `/state/static` payload serialization
- `systems/`: domain systems and analysis runners
- `worldgen/`: terrain generation
- `frontend/`: web observer client
- `godot/`: Godot observer project
- `scripts/`: scenario/analysis entry scripts
- `tests/`: unit and integration tests
- `docs/`: architecture, contracts, and technical references

## Development Notes

- Keep simulation authority in Python runtime modules.
- Treat observers as read-only clients.
- When changing `/state`, update both:
  - `docs/state_contract.md`
  - `docs/state_schema.json`
- Prefer adding targeted tests with serializer/contract changes.
