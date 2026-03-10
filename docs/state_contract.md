# State Contract: Python Simulation -> Observer API

## Scope
This document defines the observer-facing, read-only state contract produced by the Python simulation backend.

Source of truth:
- Python simulation implementation (`state_serializer.py`, `world.py`, `systems/*`)

Observer rule:
- `/state` and `/state/static` are read-only snapshots.
- Clients must not treat local state as simulation authority.

## Endpoints
- `GET /state/static`: static map payload (terrain + map dimensions)
- `GET /state`: dynamic runtime payload (entities, resources, counters, stats)

## Coordinate Type
All map positions use:

```json
{ "x": 12, "y": 7 }
```

Semantics:
- Integer grid coordinates
- Origin at top-left
- Bounds: `0 <= x < width`, `0 <= y < height`

## `GET /state/static`
Current payload (exact serializer output):

- `schema_version` (`string`)
- `static_state_version` (`integer`)
- `width` (`integer`)
- `height` (`integer`)
- `tiles` (`string[][]`)
- `world_seed` (`integer | null`, optional key; included only when `world.world_seed` attribute exists)

Notes:
- `tiles` is the authoritative terrain grid for observers.

## Terrain Tile Codes
- `G` = grass
- `F` = forest
- `M` = mountain
- `W` = water
- `H` = hill

## `GET /state`
Top-level fields (current exact keys):

- `schema_version` (`string`)
- `state_version` (`integer`) increments on every `/state` serialization
- `tick` (`integer`)
- `civ_stats` (`object`)

Version semantics:
- `schema_version` = contract/schema shape version
- `state_version` = runtime snapshot version

### Resource Nodes (terrain resources)
- `food` (`Coord[]`)
- `wood` (`Coord[]`)
- `stone` (`Coord[]`)

### Farms
- `farms` (`FarmPlot[]`)
- `farms_count` (`integer`)

`FarmPlot` fields:
- `x` (`integer`)
- `y` (`integer`)
- `state` (`string`)
- `growth` (`integer`)
- `village_id` (`integer | null`)

### Built Environment
- `structures` (`Coord[]`) legacy house tiles
- `roads` (`Coord[]`)
- `storage_buildings` (`Coord[]`) legacy storage tiles
- `buildings` (`Building[]`) canonical typed building objects

`Building` fields (always present):
- `building_id` (`string`)
- `type` (`string`)
- `category` (`string`)
- `tier` (`integer`)
- `x` (`integer`)
- `y` (`integer`)
- `footprint` (`Coord[]`)
- `village_id` (`integer | null`)
- `village_uid` (`string | null`)
- `connected_to_road` (`boolean`)
- `operational_state` (`string`)
- `linked_resource_type` (`string | null`)
- `linked_resource_tiles_count` (`integer`)
- `service` (`object | null`)
- `storage` (`ResourceBucket | null`)
- `storage_capacity` (`integer | null`)
- `construction_request` (`object | null`)
- `construction_buffer` (`ResourceBucket | null`)
- `construction_progress` (`integer | null`)
- `construction_required_work` (`integer | null`)
- `construction_complete_ratio` (`number | null`)

Observer note:
- `type` and `category` are implementation-defined strings.
- Clients should not assume a closed enum unless that enum is separately versioned.

`Building.service` when non-null:
- `transport` (`number`)
- `logistics` (`number`)
- `efficiency_multiplier` (`number`)

Nullability behavior:
- `storage` and `storage_capacity` are non-null only for `type == "storage"` in canonical building records.
- `construction_*` fields are non-null only when the building record contains construction state.
- In legacy fallback serialization (`world.buildings` empty), `service`, `storage`, and construction fields are emitted as `null`.

### Villages
- `villages` (`Village[]`)

Stable normalized fields provided by serializer:
- `village_uid` (`string`) always populated by serializer (falls back to `legacy-{id}` if missing)
- `tiles` (`Coord[]`) normalized + sorted
- `storage` (`ResourceBucket`)
- `storage_pos` (`Coord | null`)
- `farm_zone_center` (`Coord | null`)
- `tier` (`integer`)
- `needs` (`object`)
- `priority` (`string`)
- `metrics` (`object`)

Implementation passthrough fields:
- Village objects are emitted as `{**v, ...normalized_fields}`.
- Additional village keys from simulation internals are passed through when present (for example: `id`, `center`, `houses`, `population`, `leader_id`, `strategy`, `color`, `relation`, `target_village_id`, `migration_target_id`, `power`, `priority_history`, `leader_profile`, `proto_culture`, `culture_summary`, `phase`).

Important implementation detail:
- Passthrough keys are implementation-driven and may vary by runtime state.

### Agents
- `agents` (`Agent[]`)

`Agent` fields (alive agents only):
- `agent_id` (`string`)
- `x` (`integer`)
- `y` (`integer`)
- `is_player` (`boolean`)
- `player_id` (`string | null`)
- `role` (`string`)
- `village_id` (`integer | null`)
- `task` (`string`)
- `inventory` (`ResourceBucket`)
- `max_inventory` (`integer`)

### Aggregate Counters
- `population` (`integer`)
- `players` (`integer`)
- `npcs` (`integer`)
- `avg_hunger` (`number`, rounded to 2 decimals)
- `food_count` (`integer`)
- `wood_count` (`integer`)
- `stone_count` (`integer`)
- `houses_count` (`integer`)
- `villages_count` (`integer`)
- `leaders_count` (`integer`)
- `llm_interactions` (`integer`)

### Infrastructure Snapshot Fields
- `infrastructure_systems_available` (`string[]`)
- `transport_network_counts` (`{ [network_type: string]: integer }`)

Transitional note:
- These two fields are infrastructure observability outputs derived from `world.infrastructure_state`.
- They are observer/debug-facing summaries, not a full infrastructure graph contract.

### Civilization Stats (`civ_stats`)
- `largest_village_id` (`integer | null`)
- `largest_village_houses` (`integer`)
- `strongest_village_id` (`integer | null`)
- `strongest_village_power` (`number`)
- `expanding_village_id` (`integer | null`)
- `warring_villages` (`integer`)
- `migrating_villages` (`integer`)

## Type Aliases
- `Coord = { x: integer, y: integer }`
- `ResourceBucket = { food: integer, wood: integer, stone: integer }`

## Realistic Example (`GET /state`)

```json
{
  "schema_version": "1.1.0",
  "state_version": 1,
  "tick": 42,
  "food": [{ "x": 3, "y": 4 }, { "x": 5, "y": 6 }],
  "wood": [{ "x": 8, "y": 2 }],
  "stone": [{ "x": 9, "y": 9 }],
  "farms": [
    { "x": 12, "y": 10, "state": "growing", "growth": 2, "village_id": 1 }
  ],
  "farms_count": 1,
  "structures": [{ "x": 10, "y": 10 }],
  "roads": [{ "x": 10, "y": 9 }, { "x": 10, "y": 10 }, { "x": 10, "y": 11 }],
  "storage_buildings": [{ "x": 11, "y": 10 }],
  "buildings": [
    {
      "building_id": "b-000001",
      "type": "house",
      "category": "residential",
      "tier": 1,
      "x": 10,
      "y": 10,
      "footprint": [{ "x": 10, "y": 10 }],
      "village_id": 1,
      "village_uid": "v-000001",
      "connected_to_road": true,
      "operational_state": "active",
      "linked_resource_type": null,
      "linked_resource_tiles_count": 0,
      "service": { "transport": 1.0, "logistics": 1.0, "efficiency_multiplier": 1.5 },
      "storage": null,
      "storage_capacity": null,
      "construction_request": null,
      "construction_buffer": null,
      "construction_progress": null,
      "construction_required_work": null,
      "construction_complete_ratio": null
    }
  ],
  "villages": [
    {
      "id": 1,
      "village_uid": "v-000001",
      "center": { "x": 10, "y": 10 },
      "houses": 1,
      "population": 1,
      "tiles": [{ "x": 10, "y": 10 }],
      "leader_id": null,
      "strategy": "gather food",
      "color": "#8b4513",
      "relation": "peace",
      "target_village_id": null,
      "migration_target_id": null,
      "power": 0,
      "storage": { "food": 6, "wood": 3, "stone": 1 },
      "storage_pos": { "x": 11, "y": 10 },
      "farm_zone_center": { "x": 12, "y": 10 },
      "priority_history": [],
      "leader_profile": null,
      "tier": 1,
      "proto_culture": null,
      "culture_summary": null,
      "needs": { "need_storage": false },
      "priority": "stabilize",
      "metrics": { "active_farms": 1, "storage_exists": true }
    }
  ],
  "civ_stats": {
    "largest_village_id": 1,
    "largest_village_houses": 1,
    "strongest_village_id": 1,
    "strongest_village_power": 0,
    "expanding_village_id": null,
    "warring_villages": 0,
    "migrating_villages": 0
  },
  "agents": [
    {
      "agent_id": "a-000001",
      "x": 10,
      "y": 10,
      "is_player": false,
      "player_id": null,
      "role": "builder",
      "village_id": 1,
      "task": "build_storage",
      "inventory": { "food": 1, "wood": 0, "stone": 0 },
      "max_inventory": 6
    }
  ],
  "population": 1,
  "players": 0,
  "npcs": 1,
  "avg_hunger": 80.0,
  "food_count": 2,
  "wood_count": 1,
  "stone_count": 1,
  "houses_count": 1,
  "villages_count": 1,
  "leaders_count": 0,
  "llm_interactions": 0,
  "infrastructure_systems_available": ["communication", "energy", "environment", "logistics", "transport", "water"],
  "transport_network_counts": { "logistics_corridor": 1, "road": 2 }
}
```

## Stability Rules for Observers
- Treat field names and nullability above as authoritative for current backend behavior.
- Ignore unknown future fields safely.
- Do not infer simulation authority from client-side state.
