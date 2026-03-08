# Godot Observer Plan

## Vision
Costruire un renderer Godot separato che osserva `/state/static` + `/state` senza introdurre logica simulativa duplicata.

## Phase 1: Basic Observer
- Setup progetto Godot 2D con tile grid.
- Bootstrap statico con `GET /state/static`.
- Client HTTP polling su `GET /state`.
- Parsing snapshot e mapping dati:
  - tiles
  - resources (`food`, `wood`, `stone`)
  - agents
  - villages
  - structures/roads/storage/farms
- Render base:
  - terrain layer
  - entity layer
  - village markers
- HUD minima:
  - tick
  - population
  - counts principali

Deliverable:
- observer funzionante in real-time con aggiornamento continuo.

## Phase 2: Debug Overlay
- Overlay attivabili:
  - roads
  - farms state
  - village influence / heat
  - roles/tasks agenti
- pannelli diagnostici:
  - top villages
  - civ_stats
  - metriche `needs/metrics` villaggio
- strumenti debug:
  - ispezione entità (hover/click)
  - filtro per `village_id` e `role`

Deliverable:
- observer utile per tuning simulazione e validazione comportamento.

## Phase 3: UI / Replay / Metrics
- UI operativa:
  - timeline tick
  - selezione villaggio/agente
  - grafici trend (population, food, roads, farms)
- Replay base:
  - snapshot cache locale
  - playback pausa/seek semplice
- Export metrics:
  - dump JSON/CSV sessione osservata

Deliverable:
- observer avanzato orientato a analisi e presentazione.

## Technical constraints
- Nessun comando di simulazione dal client Godot.
- Nessuna decision logic lato renderer.
- Fallback robusti per campi mancanti/opzionali.
- Aggiornamento sicuro se schema evolve (feature flags per campi).

## Dependencies for future hardening
- `schema_version` nel payload.
- ID stabili (`agent_id`, `village_uid`).
- split static/dynamic.
- endpoint delta per replay efficiente.
