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