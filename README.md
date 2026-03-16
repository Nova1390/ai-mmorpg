# AI Civilization Sandbox

AI Civilization Sandbox is an agent-based civilization simulation where autonomous agents form settlements, organize labor, build infrastructure, and adapt over time under a Python simulation core.

## Project Vision

The project aims to model emergent civilization behavior from local decision rules, resource constraints, and village-level governance.

Key principle:
- Python simulation is authoritative.
- Observer clients (web, Godot) are read-only.

## Core Architecture

### Simulation Core (Python)
- `world.py` owns mutable world state and tick progression.
- `agent.py` and `brain.py` drive per-agent behavior and decision loops.
- `systems/` modules implement domain logic (farming, roads, buildings, villages, roles, AI policy, observability).
- `worldgen/` produces deterministic terrain layouts from seed/config.

### State Serialization Layer
- `state_serializer.py` converts in-memory state into observer payloads.
- `GET /state` is the canonical dynamic snapshot.
- `GET /state/static` provides static map payload (dimensions + tiles + optional seed).
- Contract versioning is explicit via `schema_version`, `state_version`, and `static_state_version`.

### Transport/API Layer
- `server.py` hosts FastAPI routes, starts the tick loop, and exposes observer endpoints.
- The API is polling-oriented and returns JSON snapshots.

## Simulation Systems

The core simulation loop coordinates these systems each tick:
- `farming_system`: farm emergence, growth cycles, harvest flow, and farm viability logic.
- `building_system`: building catalogs, placement, construction sites, storage logistics, specialization, and build policy.
- `road_system`: movement usage tracking and transport network growth (`path` -> `road` -> `logistics_corridor`).
- `village_system`: village detection from structure clusters, continuity/stability tracking, and leadership/politics hooks.
- `village_ai_system`: village needs, market pressure, phase/priority selection, and proto-culture updates.
- `role_system`: workforce allocation, specialist balancing, and role continuity/reassignment constraints.
- `observability`: metrics snapshots/history for diagnostics and scenario evaluation.

## Observer Architecture

### Web Observer
- Located in `frontend/`.
- Fetches `/state/static` once, then polls `/state`.
- Builds local indexes for rendering (agents, villages, resources, buildings, roads).

### Godot Observer
- Located in `godot/`.
- `StateClient.gd` fetches `/state/static` and polls `/state`.
- Merges static map fields into runtime payload for rendering convenience.
- Operates as read-only visualization/debug client.

## API `/state`

`GET /state` returns the canonical runtime snapshot for observers. It includes:
- version fields (`schema_version`, `state_version`, `tick`)
- resource coordinates and counts (`food`, `wood`, `stone`, counters)
- farm data (`farms`, `farms_count`)
- built environment (`structures`, `roads`, `storage_buildings`, `buildings`)
- village objects (`villages`, `civ_stats`)
- agent objects (`agents`)
- aggregate population/leadership counters
- infrastructure observability summaries (`infrastructure_systems_available`, `transport_network_counts`)

Reference docs:
- `docs/state_contract.md`
- `docs/state_schema.json`

## Running the Simulation

1. Create and activate a Python virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the server:

```bash
uvicorn server:app --reload
```

4. Open observers:
- Web: `http://127.0.0.1:8000/`
- Godot: open `godot/project.godot` and run `res://scenes/Main.tscn`

Quick `/state` inspection:

```bash
curl http://127.0.0.1:8000/state | python -m json.tool
```

## Roadmap

Near-term focus areas:
- stabilize village economy and food/material throughput
- improve logistics and construction delivery coherence
- harden multi-village emergence and persistence behavior
- continue observability and scenario-driven balancing workflows
- improve observer robustness as contract fields evolve
