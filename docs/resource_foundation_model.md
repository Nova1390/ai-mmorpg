# Resource Foundation Model (RESOURCE-FOUNDATION-001)

## Core Conservation Rule
Raw materials must have physical provenance.

- Wood comes from world wood nodes/biomass sources.
- Stone comes from world stone/geological nodes.
- Food comes from wild gathering, farming, hunting, or existing reserves.

No system may fabricate raw mass from nothing.

## Stock-Flow Framing
Each core resource is diagnosed as a stock-flow pipeline:

1. `world_stock` (raw nodes/patches currently present on map)
2. `extracted` (units gathered from world sources)
3. `transported/deposited` (units moved into buffers, storage, or active sites)
4. `buffered` (units currently held in inventories/camps/storage/construction buffers)
5. `consumed` (units spent by eating/construction/use)
6. `regenerated` (units respawned by ecology, where applicable)

## Processing vs Raw Matter
Processing/refinement can improve quality or efficiency, but cannot create raw material mass.

- Valid: better construction yield from already-extracted material.
- Invalid: creating new raw wood/stone/food without extraction/respawn provenance.

## Diagnostics Intent
Material observability is used to identify whether scarcity is structural because of:

- low initial stock
- weak regeneration
- extraction bottlenecks
- transport/deposit bottlenecks
- demand outpacing supply
- spatial/access constraints

The objective is realism under scarcity, not global abundance hacks.
