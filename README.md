# AI Civilization Sandbox

AI Civilization Sandbox is an agent-based civilization simulation prototype where autonomous agents form villages, organize labor, build infrastructure, produce food, and evolve over simulation ticks.

## Vision

The project explores emergent civilization behavior from simple local rules and AI-guided governance, while keeping the simulation core inspectable, deterministic in execution order, and renderer-agnostic.

## Core Architecture

### 1) Python Simulation Core (Source of Truth)
- Runtime authority lives in Python (`world.py`, `agent.py`, `systems/`, `worldgen/`).
- The world advances through a tick loop and updates agents, villages, farming, roads, and economy-related state.
- AI governance can be enabled for leader/player planning (`brain.py`, `planner.py`) with deterministic simulation state serialization.

### 2) API / State Transport Layer
- FastAPI exposes the simulation state to observer clients.
- `GET /state` is the canonical runtime snapshot for external consumers.
- Additional state endpoints may be introduced as the simulation contract evolves.

### 3) Godot Observer (Read-Only)
- The Godot project in `observer/godot/` is an observer client.
- It polls `/state` to render runtime simulation state.
- It renders simulation state but does not drive simulation logic.

## Current Features

- Procedural world simulation running on a Python tick loop.
- Autonomous agents with stable `agent_id` identifiers.
- Village detection and tracking with stable `village_uid`.
- Farming plots with lifecycle state (`prepared`, `planted`, `growing`, `ripe`, `dead`).
- Emergent roads and built structures.
- Village storage and economy-relevant fields (`storage`, `needs`, `metrics`, priorities, power indicators).
- Village governance fields in `/state` (leadership, strategy/priority data, profiles/history when present).
- Versioned state contract with JSON schema documentation.

## Repository Structure

- `server.py` - FastAPI app and simulation startup/tick orchestration.
- `state_serializer.py` - simulation state serialization.
- `world.py` - world state container and simulation update loop.
- `systems/` - domain systems (village AI, roles, farming, roads, building).
- `worldgen/` - procedural terrain generation.
- `observer/godot/` - Godot observer project.
- `frontend/` - lightweight web observer client.
- `docs/` - architecture notes and state contract/schema docs.
- `tests/` - contract and serializer tests.

## Run the Python Simulation

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the backend:

```bash
uvicorn server:app --reload
```

By default the API runs on `http://127.0.0.1:8000`.

## Inspect `/state`

Quick check from terminal:

```bash
curl http://127.0.0.1:8000/state | python -m json.tool
```

Recommended observer flow:
1. Poll `GET /state` for runtime updates.
2. Treat `/state` as the authoritative snapshot.
3. Handle future endpoint additions as optional contract evolutions.

## Run the Godot Observer

1. Keep the Python backend running on `http://127.0.0.1:8000`.
2. Open `observer/godot/project.godot` in Godot 4.x.
3. Run scene `res://scenes/Main.tscn` (default main scene).

Notes:
- The Godot client is a read-only observer by design.
- Observer integration is functional and still under active stabilization.

## State Contract and Schema

- Contract reference: `docs/state_contract.md`
- Dynamic snapshot schema: `docs/state_schema.json`
- Additional schemas:
  - `docs/state_static_schema.json`
  - `docs/state_events_schema.json`

## Development Principles

- Python simulation is the source of truth.
- Clear separation of concerns: simulation core vs. renderer clients.
- Deterministic core update/serialization behavior, with optional AI governance layers.
- Renderer independence: Godot/web clients observe state but do not own it.
- Emergent systems over scripted outcomes.

## Current Project Status

This repository is an early but functional simulation prototype:
- The core loop, state API, and observer path are running.
- The state contract is versioned and documented.
- Systems and observer UX are still evolving and being stabilized.

## Roadmap (Near Term)

- Stabilize village economy balancing and resource flows.
- Improve logistics behavior (hauling, storage usage, distribution).
- Harden renderer integration and observer resilience to schema evolution.
- Improve multi-village emergence dynamics and inter-village behavior.

## Contributing / Development Workflow

- Keep simulation logic in Python core modules.
- Treat renderer clients as read-only observers.
- Update contract docs/schemas when changing state payloads.
- Add or update tests in `tests/` for serializer/contract changes.
- Prefer small, focused pull requests with clear behavioral impact.
