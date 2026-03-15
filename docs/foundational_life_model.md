# Foundational Life Model (FOUNDATIONAL-LIFE-001)

## Core Principle
Agents do not exist to execute tasks. Agents exist to live.
Civilization is a downstream effect of survival continuity.

## Agent Life Priorities
1. Stay alive now: hunger, acute fatigue/rest, immediate safety.
2. Stay alive soon: secure repeatable local food access.
3. Stabilize locally: maintain shelter, proximity to viable food, and social continuity.
4. Build reserves: accumulate buffers against scarcity shocks.
5. Reproduce under stability: only when sustained survival conditions hold.
6. Expand infrastructure: only when it improves continuity, not as early default behavior.

## Life Loop
1. Seek nourishment and consume food.
2. Recover (rest/shelter) to preserve long-horizon capability.
3. Repeat successful local loops (food, shelter, camp/house support).
4. Adapt under pressure (reposition, reduce non-essential work, preserve viable loops).

## Self-Feeding vs Group-Feeding
- `self_feeding`: actions that directly keep the agent alive (e.g. `gather_food_wild`, `eat_food`, survival fallback).
- `group_feeding`: actions that keep the local nucleus alive (e.g. `camp_supply_food`, food logistics into shared buffers).
- Both are valid survival behaviors; arbitration must remain survival-first and pressure-aware.

## Settlement Emergence
- Proto-settlements emerge from repeated local viability, not from fixed stage scripting.
- Formal villages require persistence and viability thresholds (population, shelter anchors, continuity over time).
- Ghost settlements must dissolve/downgrade when viability collapses.

## Food Security and Reserves
- Food continuity is the core bottleneck before higher structures.
- Reserve systems (camp/house/storage) are anti-scarcity mechanisms.
- Storage should emerge only when sustained throughput and pressure justify it.
- Implementation notes for explicit loop separation are in `docs/food_security_layers.md`.
- Raw materials follow physical stock-flow conservation (see `docs/resource_foundation_model.md`).

## Reproduction and Continuity
- Reproduction is downstream of stability.
- Births should be rare and conditional on real continuity (not forced, not guaranteed).
- No stability, no demographic continuity.

## Infrastructure as Downstream System
- Houses: early continuity anchors.
- Storage: reserve-pressure response in mature nuclei.
- Roads/logistics: repeated traffic optimization in already viable settlements.
- Infrastructure should follow life support, never replace it.

## Design Invariants
- No global omniscient planner.
- No global abundance hack as a default fix.
- Scarcity remains meaningful and scenario-differentiated.
- Survival pressure can still cause migration, fragmentation, and failure.
- Local adaptation should improve realism, not force success.
