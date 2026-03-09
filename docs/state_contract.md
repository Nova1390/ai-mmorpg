# State Contract: Python Simulation Core <-> Godot Observer

## Scope
Questo documento definisce il contratto dati observer tra Python Simulation Core e renderer esterni.

Regola fondamentale:
- Python Simulation Core = **source of truth**
- Godot Observer = **read-only observer**

Il renderer non deve prendere decisioni di simulazione, ma solo visualizzare e analizzare lo stato ricevuto.

Distinzione architetturale:
- **Buildings**: entità locali/siti fisici (house, storage, mine, lumberyard, farm_plot).
- **Infrastructure**: reti/sistemi abilitanti (transport, logistics, water, energy, communication, environment).

## Endpoint separation
- `GET /state/static`: payload mappa/statica (authoritative source dei campi immutabili)
- `GET /state`: payload runtime dinamico (authoritative source dello stato simulazione evolutivo)
- Response type: `application/json`
- Frequenza attuale simulazione: tick ogni ~`0.2s` (circa 5 TPS)

## Coordinate format
- Sistema a griglia con coordinate intere.
- Ogni punto usa `{ "x": int, "y": int }`.
- Origine: in alto a sinistra.
- Limiti validi:
  - `0 <= x < width`
  - `0 <= y < height`

## GET /state/static
- Method: `GET`
- Path: `/state/static`
- Campi:
  - `schema_version` (string): versione contratto
  - `static_state_version` (int): versione snapshot statico
  - `width` (int): larghezza mappa
  - `height` (int): altezza mappa
  - `tiles` (`string[][]`): matrice tile statica (`G`, `F`, `M`, `W`)
  - `world_seed` (optional): incluso solo se disponibile nel core

## GET /state
- Method: `GET`
- Path: `/state`
- Campi top-level dinamici:
  - `schema_version`
  - `state_version`
  - `tick`
  - `food`, `wood`, `stone`
  - `farms`, `farms_count`
  - `structures`, `roads`, `storage_buildings`, `buildings`
  - `villages`
  - `civ_stats`
  - `agents`
  - `population`, `players`, `npcs`, `avg_hunger`
  - `food_count`, `wood_count`, `stone_count`
  - `houses_count`, `villages_count`, `leaders_count`
  - `llm_interactions`
  - `infrastructure_systems_available` (array string, debug compatto)
- Nota: `/state` **non** contiene più `width`, `height`, `tiles`.

## GET /state/events
- Method: `GET`
- Path: `/state/events`
- Query params:
  - `since_tick` (int, default `-1`): restituisce eventi con `tick > since_tick`.
- Campi top-level:
  - `schema_version` (string)
  - `events` (array)
  - `oldest_retained_tick` (int|null)
  - `newest_retained_tick` (int|null)
  - `retained_event_count` (int)

Struttura evento:
- `event_id` (string): id univoco e monotonicamente crescente.
- `tick` (int): tick simulativo in cui l'evento viene emesso.
- `event_type` (string): tipo semantico evento.
- `payload` (object): dati evento JSON-safe, variabili per tipo.

Semantica ordering e retention:
- Gli eventi sono emessi e restituiti in ordine cronologico deterministico (append order).
- Il buffer eventi e` bounded in-memory e mantiene solo una finestra recente.
- Se `since_tick` e` piu` vecchio della finestra trattenuta, la risposta contiene solo gli eventi ancora disponibili (nessun errore, nessun backfill artificiale).

## Resource fields
- `food`: array di coordinate risorsa cibo selvatico.
- `wood`: array di coordinate risorsa legno.
- `stone`: array di coordinate risorsa pietra.
- `food_count`, `wood_count`, `stone_count`: conteggi globali.

## Farms
- `farms`: array plot agricoli.
- Campi per farm plot:
  - `x`, `y` (int)
  - `state` (string): `prepared | planted | growing | ripe` (oggi usati)
  - `growth` (int): progresso crescita
  - `village_id` (int|null): villaggio associato
- `farms_count`: numero totale plot.

## Built environment
- `structures`: coordinate case.
- `roads`: coordinate strade emerse da utilizzo.
- `storage_buildings`: coordinate edifici storage.
- `buildings`: array ricco di entita` edificio tipizzate con footprint.
  - campi principali: `building_id`, `type`, `category`, `tier`, `x`, `y`, `footprint`, `village_id`, `village_uid`, `connected_to_road`
  - campi operativi produzione (debug): `operational_state`, `linked_resource_type`, `linked_resource_tiles_count`
  - categorie attive: `residential`, `food_storage`, `production`, `governance`, `infrastructure`, `security`, `knowledge`, `health`, `culture`, `commerce`
  - tier civiltà supportati: `0..5` (struttura dati pronta; enforcement gameplay non ancora attivo)
- `houses_count`: totale strutture.

## Infrastructure systems
- Catalogo infrastrutture separato da `BUILDING_CATALOG` nel core Python (`INFRASTRUCTURE_CATALOG`).
- Sistemi supportati:
  - `transport`
  - `logistics`
  - `water`
  - `energy`
  - `communication`
  - `environment`
- Tipi `transport` attualmente vicini al runtime:
  - `path`, `road` (attivi semanticamente)
  - `bridge` (placeholder)
- `logistics` attuale: base strutturale con `storage_link` e `haul_route` come semantica di rete.
- Altri sistemi (`water`, `energy`, `communication`, `environment`) sono placeholder strutturali per evoluzioni future.

## Agents
- `agents`: array entità vive.
- Campi per agente:
  - `agent_id` (string, stabile)
  - `x`, `y` (int)
  - `is_player` (bool)
  - `player_id` (string|null)
  - `role` (string) es. `npc`, `player`, `leader`, `farmer`, `builder`, `hauler`, `forager`
  - `village_id` (int|null)
  - `task` (string) task runtime attuale

Metriche aggregate:
- `population`, `players`, `npcs`, `avg_hunger`, `leaders_count`, `llm_interactions`

## Villages
- `villages`: array villaggi rilevati dal core.
- Campi principali:
  - `village_uid` (string, stabile)
  - `id` (int)
  - `center` (`{x,y}`)
  - `tiles` (array coordinate tile del cluster)
  - `houses`, `population` (int)
  - `leader_id` (int|null)
  - `strategy`, `priority`, `phase` (string, se presente)
  - `tier` (int, placeholder sviluppo insediamento; default corrente `1`)
  - `relation`, `target_village_id`, `migration_target_id`
  - `power` (number)
  - `color` (string)
  - `storage` (`food`, `wood`, `stone`)
  - `storage_pos`, `farm_zone_center` (`{x,y}`)
  - `needs` (object)
  - `metrics` (object)
  - `priority_history` (array)
  - `leader_profile` (object|null)

## Civilization stats
`civ_stats` aggrega stato macro-civiltà:
- `largest_village_id`, `largest_village_houses`
- `strongest_village_id`, `strongest_village_power`
- `expanding_village_id`
- `warring_villages`, `migrating_villages`

## Contract stability notes
- `schema_version` = versione del contratto.
- `static_state_version` = versione del payload statico.
- `state_version` = versione snapshot dinamico (orientata a emissione snapshot).
- `/state` resta lo snapshot autoritativo dello stato corrente; `/state/events` e` uno stream complementare utile per debug/analytics/timeline tooling.
- Gli observer devono:
  - caricare `/state/static` una volta all'avvio
  - fare polling di `/state` per aggiornamenti runtime
  - usare `/state/events` in parallelo per eventi semantici, tollerando una history limitata dalla retention
  - non inferire autorità simulativa dallo stato locale renderer
  - usare `agent_id` e `village_uid` come identità stabili

## Event types correnti
- `agent_born`: emesso quando un agente viene aggiunto al mondo; payload con identita` agente e contesto base (`is_player`, `player_id`, `village_uid`).
- `agent_died`: emesso quando un agente passa a `alive=False`; payload con identita` agente e motivo.
- `village_created`: emesso quando il clustering rileva un nuovo villaggio non riconciliato con uno precedente; payload con `village_uid`, id numerico, centro e numero case iniziali.
- `house_built`: emesso quando viene costruita una casa; payload con agente costruttore, coordinate e `village_uid`.
- `farm_created`: emesso quando viene creato un plot agricolo; payload con agente, coordinate e `village_uid`.
- `resource_harvested`: emesso su raccolta risorse (wild/farm/farm_haul/autopickup); payload con agente, tipo risorsa, quantita`, sorgente e coordinate.
- `role_changed`: emesso quando cambia il ruolo agente tramite `world.set_agent_role`; payload con agente, ruolo precedente/successivo, reason e `village_uid`.
