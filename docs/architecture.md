# AI Civilization Sandbox Architecture

This document summarizes the current implementation architecture.

## Simulation Core

```mermaid
flowchart TD
    A["World (world.py)"] --> B["Tick Loop (World.update)"]
    B --> C["Agent Updates (agent.py)"]
    B --> D["Systems Pipeline"]
    D --> D1["farming_system"]
    D --> D2["village_system"]
    D --> D3["village_ai_system"]
    D --> D4["building_system"]
    D --> D5["role_system"]
    D --> D6["road_system"]
    B --> E["Metrics Collector (observability)"]
```

## Systems Architecture

```mermaid
flowchart LR
    V["village_system\n(cluster detection + IDs)"] --> VA["village_ai_system\n(needs/market/priority)"]
    VA --> R["role_system\n(workforce allocation)"]
    VA --> B["building_system\n(policy + construction)"]
    C["agent actions"] --> F["farming_system\n(plot lifecycle + harvest)"]
    C --> RO["road_system\ntransport usage growth"]
    B --> RO
    F --> B
    ALL["all systems"] --> O["observability metrics"]
```

## API Layer

```mermaid
flowchart TD
    W["World instance"] --> S["state_serializer.py"]
    S --> ST["serialize_static_world_state"]
    S --> DY["serialize_dynamic_world_state"]
    W --> EV["world.events"]

    API["FastAPI (server.py)"] --> R0["GET /state/static"]
    API --> R1["GET /state"]
    API --> R2["GET /state/events"]
    API --> R3["GET /debug/metrics"]
    API --> R4["GET /debug/history"]

    ST --> R0
    DY --> R1
    EV --> R2
```

## Observer Clients

```mermaid
flowchart LR
    API["FastAPI"] --> WEB["Web Observer (frontend/)"]
    API --> GODOT["Godot Observer (godot/)"]

    WEB --> WEB1["GET /state/static once"]
    WEB --> WEB2["poll GET /state"]

    GODOT --> G1["StateClient.gd\nGET /state/static once"]
    GODOT --> G2["StateClient.gd\npoll GET /state"]

    NOTE["Observers are read-only\nNo simulation authority client-side"]
```

## Runtime Notes

- Tick cadence in `server.py` is `~0.2s` (`asyncio.sleep(0.2)`).
- Dynamic snapshots are versioned (`state_version`) and contract-versioned (`schema_version`).
- Static map payload is split into `/state/static` for bootstrap and caching.
- Diagnostics are collected in-process by `SimulationMetricsCollector` and exposed via debug endpoints.
