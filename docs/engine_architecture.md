# Engine Architecture: Python Core + Godot Observer

## Goal
Definire un'architettura chiara dove la simulazione resta nel backend Python e Godot agisce come client osservatore esterno.

## Current runtime layers

### 1) Simulation Core (Python)
- Componenti: `world.py`, `agent.py`, `brain.py`, `pathfinder.py`, `systems/*`, `worldgen/*`.
- Responsabilità:
  - stato mondo e tick loop
  - AI agenti e villaggi
  - regole di economia, farming, building, logistics
  - world generation

Output interno: stato runtime mutabile in memoria (`World`).

### 2) State serialization
- La serializzazione è centralizzata in `state_serializer.py`.
- Sono esposti due DTO distinti:
  - static DTO per `/state/static`
  - dynamic DTO per `/state`

### 3) FastAPI transport
- FastAPI espone `GET /state/static`, `GET /state` e endpoint ausiliari player.
- Trasporto attuale: HTTP polling da frontend web.

### 4) Observer (frontend oggi, Godot domani)
- Ruolo: visualizzare e analizzare.
- Non deve mutare o orchestrare la simulazione.
- Carica `/state/static` all'avvio e consuma snapshot periodici da `/state`.

## Data flow
1. `World.update()` avanza di un tick.
2. Observer carica `GET /state/static` per mappa immutabile.
3. FastAPI riceve `GET /state`.
4. Il backend serializza snapshot JSON dinamico.
5. Observer aggiorna rendering/UI/debug overlay in sola lettura.

## Architectural contract
- Python backend è il **single source of truth**.
- Godot è **read-only observer**.
- Nessuna logica di gameplay/simulazione deve divergere lato renderer.

## Evolution path (without changing simulation rules)

### A) Split static/dynamic payload (implemented)
- `GET /state/static`: `schema_version`, `static_state_version`, `width`, `height`, `tiles`, `world_seed` (se presente).
- `GET /state`: solo stato dinamico tick-based.
- Beneficio: payload minore, minor coupling prestazionale.

### B) Stable IDs
- introdurre `agent_id` stabile per NPC e player.
- introdurre `village_uid` stabile (indipendente da reorder/ridetection).
- Beneficio: tracking, interpolazione, replay affidabili.

### C) Explicit versioning
- `schema_version` = versione contratto.
- `static_state_version` = versione static snapshot.
- `state_version` = versione dynamic snapshot.

### D) Delta stream (future)
- `GET /state/delta?since_tick=N` o stream dedicato.
- Beneficio: observer più efficiente e pronto a replay/time-scrub.

## Non-goals in questa fase
- Nessun refactor del core simulation.
- Nessun cambio semantico ai sistemi AI/economia.
- Nessun cambio di protocollo runtime oltre documentazione.
