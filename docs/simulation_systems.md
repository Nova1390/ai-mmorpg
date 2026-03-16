# Simulation Systems

This document describes the main simulation systems currently active in `world.update()` and adjacent runtime workflows.

## System Execution Context

Per tick (`World.update`), the world performs:
1. resource/patch decay and respawn
2. farm updates
3. per-agent updates
4. village detection + village AI update
5. periodic build policy
6. role assignment
7. road infrastructure update
8. prototype/settlement progression updates
9. metrics collection

## `farming_system`

Primary responsibilities:
- manage farm plot lifecycle (`prepared`, `planted`, `growing`, `ripe`, `dead`)
- track food-site discovery memory and productivity signals
- decide farm emergence eligibility from local observations and pressure
- support farmer task continuity and viability checks
- handle harvest and haul-to-storage behavior

Key implementation concepts:
- discovery map with decay (`farm_discovery_memory`)
- candidate scoring using repeat success, patch activity, local support
- early-loop persistence bonuses to reduce churn in productive loops
- abandonment logic for low-productivity/idle plots

## `road_system`

Primary responsibilities:
- record movement pressure per tile (`road_usage`)
- promote transport type by usage thresholds:
  - `path` -> `road` -> `logistics_corridor`
- connect village hubs to important targets (storage, production, construction, residential access)
- maintain building road-connectivity flags

Key implementation concepts:
- deterministic path choice with Manhattan candidates
- local-purpose guards to avoid unjustified infrastructure growth
- per-village road growth budget

## `building_system`

Primary responsibilities:
- define building and infrastructure catalogs/metadata
- choose building types and placements for villages
- create/advance construction sites with work and material requirements
- manage storage totals, deposits, withdrawals, and internal redistribution
- run hauler construction deliveries and source binding/reservations
- evaluate building service levels and efficiency multipliers
- track specialization readiness/blockers (`mine`, `lumberyard`)

Key implementation concepts:
- typed building records (`house`, `storage`, `farm_plot`, `mine`, `lumberyard`)
- construction buffers and request fields for staged completion
- policy build cooldown/attempt windows
- extensive diagnostics hooks for construction and specialization funnels

## `village_system`

Primary responsibilities:
- detect villages from structure clusters
- preserve village continuity via matching previous clusters
- maintain stable `village_uid`
- compute civilization summary stats (`civ_stats`)
- assign and maintain village leadership
- update village-level politics/relation state

Key implementation concepts:
- formalization gates (houses, population, stability, food/security context)
- ghost/abandonment and transitional settlement handling
- progression and bottleneck counters for settlement realism diagnostics

## `role_system`

Primary responsibilities:
- assign village workforce roles (`farmer`, `builder`, `forager`, `hauler`)
- rebalance specialist roles (`miner`, `woodcutter`)
- enforce role hold windows to reduce oscillation
- protect delivery-chain continuity for haulers
- gate/support civic roles during construction pressure

Key implementation concepts:
- target mix from village needs and construction signals
- reserved civic support slot logic in non-terminal crises
- allocation and relaxation diagnostics for support roles

## `village_ai_system`

Primary responsibilities:
- compute village needs and operational phase (`bootstrap`, `survival`, `stabilize`, `growth`, `expansion`)
- compute market pressure state (`food`, `wood`, `stone`)
- determine village priority/strategy updates
- maintain proto-culture and culture summary fields

Key implementation concepts:
- periodic market updates (`MARKET_UPDATE_INTERVAL_TICKS`)
- demand signals include hunger pressure + construction requirements
- proto-culture norms updated from observed member behavior and resource pressure

## Observability

Module: `systems/observability.py`

Primary responsibilities:
- collect periodic simulation snapshots via `SimulationMetricsCollector`
- retain rolling history (`history_size`, `snapshot_interval`)
- aggregate metrics across survival, logistics, construction, social, knowledge, and settlement progression dimensions
- expose latest/history through API debug endpoints:
  - `GET /debug/metrics`
  - `GET /debug/history`

Related runtime consumers:
- scenario tools (`systems/scenario_runner.py`, `systems/global_balance_runner.py`, `systems/parameter_sweep.py`)
- validation scripts in `scripts/`.

## Contract Surface Impact

These systems collectively shape `/state` fields, especially:
- `farms`, `buildings`, `roads`, `villages`, `agents`
- village `needs`/`metrics`/`priority`/`phase`
- infrastructure summaries (`infrastructure_systems_available`, `transport_network_counts`)
