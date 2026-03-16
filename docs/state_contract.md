# State Contract: Python Simulation -> Observer API

## Scope

This document describes the observer-facing state contract implemented by:
- `state_serializer.py`
- `server.py`

Authoritative rule:
- Python simulation state is the single source of truth.
- Observer clients consume snapshots in read-only mode.

## Endpoints

### `GET /state/static`
Static payload for map bootstrap.

### `GET /state`
Canonical dynamic runtime snapshot.

### `GET /state/events`
Semantic event stream sourced from `world.events`.

## Coordinate Format

Coordinates are JSON objects:

```json
{ "x": 12, "y": 7 }
```

Semantics:
- integer grid coordinates
- origin at top-left
- bounds: `0 <= x < width`, `0 <= y < height`

## `GET /state/static`

Current payload fields:
- `schema_version` (`string`)
- `static_state_version` (`integer`)
- `width` (`integer`)
- `height` (`integer`)
- `tiles` (`string[][]`)
- `world_seed` (`integer | null`, optional key if `world.world_seed` exists)

Runtime tile codes in `/state/static`:
- `G` grass
- `F` forest
- `M` mountain
- `W` water

Note:
- Hills (`H`) may appear during generation internals but are collapsed before runtime serialization.

## `GET /state`

Top-level keys emitted by `serialize_dynamic_world_state`:
- `schema_version` (`string`)
- `state_version` (`integer`)
- `tick` (`integer`)
- `food`, `wood`, `stone` (`Coord[]`)
- `farms` (`FarmPlot[]`)
- `farms_count` (`integer`)
- `structures` (`Coord[]`)
- `roads` (`Coord[]`)
- `storage_buildings` (`Coord[]`)
- `buildings` (`Building[]`)
- `villages` (`Village[]`)
- `civ_stats` (`object`)
- `agents` (`Agent[]`)
- `population`, `players`, `npcs` (`integer`)
- `avg_hunger` (`number`, rounded to 2 decimals)
- `food_count`, `wood_count`, `stone_count` (`integer`)
- `houses_count`, `villages_count`, `leaders_count` (`integer`)
- `llm_interactions` (`integer`)
- `infrastructure_systems_available` (`string[]`)
- `transport_network_counts` (`{ [networkType: string]: integer }`)

Notes:
- Dynamic payload does not include `width`, `height`, `tiles`.
- Coordinate arrays are sorted deterministically row-major (`y`, then `x`).
- `agents`, `villages`, and `buildings` are sorted deterministically (`agent_id`, `village_uid`, `building_id`).

## Resource Fields

- `food`, `wood`, `stone`: world resource-node coordinates.
- `food_count`, `wood_count`, `stone_count`: aggregate counts.

## Farms

`farms` item shape:
- `x`, `y` (`integer`)
- `state` (`string`) currently one of: `prepared`, `planted`, `growing`, `ripe`, `dead`
- `growth` (`integer`)
- `village_id` (`integer | null`)

## Buildings

`buildings` is the canonical built-environment list.

Each building object contains:
- `building_id` (`string`)
- `type` (`string`)
- `category` (`string`)
- `tier` (`integer`)
- `x`, `y` (`integer`)
- `footprint` (`Coord[]`)
- `village_id` (`integer | null`)
- `village_uid` (`string | null`)
- `connected_to_road` (`boolean`)
- `operational_state` (`string`)
- `linked_resource_type` (`string | null`)
- `linked_resource_tiles_count` (`integer`)
- `service` (`object | null`) with `transport`, `logistics`, `efficiency_multiplier` when present
- `storage` (`ResourceBucket | null`)
- `storage_capacity` (`integer | null`)
- `construction_request` (`object | null`)
- `construction_buffer` (`ResourceBucket | null`)
- `construction_progress` (`integer | null`)
- `construction_required_work` (`integer | null`)
- `construction_complete_ratio` (`number | null`)

Legacy compatibility:
- if `world.buildings` is empty, serializer emits synthetic `legacy-house-*` and `legacy-storage-*` records from `structures` and `storage_buildings`.

## Villages

`villages` entries are serializer-normalized dictionaries with passthrough of internal fields.

Common fields include:
- `id` (`integer`)
- `village_uid` (`string`, stable)
- `center` (`Coord`)
- `houses`, `population` (`integer`)
- `tiles` (`Coord[]`)
- `leader_id` (`integer | null`)
- `strategy`, `color`, `relation`, `priority`, `phase` (`string`)
- `target_village_id`, `migration_target_id` (`integer | null`)
- `power` (`number`)
- `tier` (`integer`)
- `storage` (`ResourceBucket`)
- `storage_pos`, `farm_zone_center` (`Coord | null`)
- `needs` (`object`)
- `metrics` (`object`)
- optional/history/profile fields (for example `priority_history`, `leader_profile`, `proto_culture`, `culture_summary`)

## Agents

`agents` includes alive agents only.

Each agent entry contains:
- `agent_id` (`string`, stable)
- `x`, `y` (`integer`)
- `is_player` (`boolean`)
- `player_id` (`string | null`)
- `role` (`string`)
- `village_id` (`integer | null`)
- `task` (`string`)
- `inventory` (`ResourceBucket`)
- `max_inventory` (`integer`)

## Civilization Stats (`civ_stats`)

- `largest_village_id` (`integer | null`)
- `largest_village_houses` (`integer`)
- `strongest_village_id` (`integer | null`)
- `strongest_village_power` (`number`)
- `expanding_village_id` (`integer | null`)
- `warring_villages` (`integer`)
- `migrating_villages` (`integer`)

## `GET /state/events`

Response fields:
- `schema_version` (`string`)
- `events` (`array`)
- `oldest_retained_tick` (`integer | null`)
- `newest_retained_tick` (`integer | null`)
- `retained_event_count` (`integer`)

Query param:
- `since_tick` (`integer`, default `-1`) returns events with `tick > since_tick`

Event shape:
- `event_id` (`string`)
- `tick` (`integer`)
- `event_type` (`string`)
- `payload` (`object`)

Event retention:
- events are bounded in memory (`world.max_retained_events`)
- old events are dropped FIFO when capacity is exceeded

## Versioning

- `schema_version`: contract/version string from serializer
- `static_state_version`: static payload version
- `state_version`: monotonically increasing dynamic snapshot version

## Observer Compatibility Rules

Observers should:
- treat unknown additional fields as forward-compatible
- use stable IDs (`agent_id`, `village_uid`, `building_id`) for tracking
- avoid deriving simulation authority from local renderer state
