# AI Civilization Sandbox

An agent-based simulation where autonomous NPCs build villages,
develop agriculture, and organize society under AI-driven leaders.
The world evolves without scripted events through emergent behavior.

## Preview

![simulation](docs/simulation.png)

## Features

- procedural world generation
- autonomous agents
- village formation
- agriculture and logistics
- LLM-driven leadership
- emergent economy

## Architecture

- `world.py` – simulation state and tick update
- `agent.py` – NPC lifecycle and actions
- `brain.py` – agent decision making
- `planner.py` – LLM strategy interface
- `systems/` – modular subsystems (villages, farming, roles, logistics)
- `worldgen/` – procedural terrain generation
- `frontend/` – visualization client

## Run

```bash
python server.py
```

## Observer API Quickstart

Python Simulation Core is the source of truth. Frontend/Godot observers are read-only clients.

- Static map bootstrap: `GET /state/static`
- Dynamic runtime updates: `GET /state`
- Optional semantic/debug stream: `GET /state/events?since_tick=...`

Recommended consumption flow:
1. Fetch `/state/static` once at startup.
2. Cache `width`, `height`, and `tiles` in the observer.
3. Poll `/state` for runtime updates.
4. Render entities/UI from dynamic payload data.
5. Never treat renderer state as simulation authority.
6. Optionally consume `/state/events` for semantic transitions (debug/analytics) without diffing full snapshots.

Stable tracking identifiers:
- Agents expose `agent_id`
- Villages expose `village_uid`

Use these IDs for entity tracking/interpolation instead of list position.

### Example: fetching static and dynamic state

```js
// 1) Static bootstrap (once at startup)
const staticRes = await fetch("/state/static");
const staticState = await staticRes.json();
const { width, height, tiles } = staticState;

// 2) Dynamic polling (on interval or game loop tick)
async function fetchDynamicState() {
  const res = await fetch("/state", { cache: "no-store" });
  const dynamicState = await res.json();

  // Runtime data examples
  const agents = dynamicState.agents || [];
  const villages = dynamicState.villages || [];
  const food = dynamicState.food || [];

  return { agents, villages, food, tick: dynamicState.tick };
}
```

Godot-oriented note:
- Request `/state/static` at startup and cache map data (`width`, `height`, `tiles`).
- Poll `/state` for runtime changes (agents, villages, resources, counters).
- Optionally poll `/state/events?since_tick=...` for semantic events and timeline overlays.
- Track moving/runtime entities by `agent_id` and settlements by `village_uid`.

Full contract and field definitions:
- [docs/state_contract.md](docs/state_contract.md)
- [docs/state_schema.json](docs/state_schema.json) (dynamic payload)
- [docs/state_static_schema.json](docs/state_static_schema.json) (static payload)
- [docs/state_events_schema.json](docs/state_events_schema.json) (events payload)
