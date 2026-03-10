const State = {
  staticData: null,
  dynamicData: null,
  indexes: null,
  apiBase: "",
  pollMs: 300,
  pollTimer: null,
  inFlight: false,
  status: {
    staticOk: false,
    dynamicOk: false,
    staticError: "",
    dynamicError: "",
    lastStaticAt: null,
    lastDynamicAt: null,
  },

  initApiBase() {
    const fromQuery = new URLSearchParams(window.location.search).get("api");
    const fromStorage = localStorage.getItem("observer_api_base");
    const chosen = typeof fromQuery === "string" ? fromQuery : (fromStorage || "");
    this.setApiBase(chosen || "");
    return this.apiBase;
  },

  setApiBase(base) {
    const cleaned = String(base || "").trim().replace(/\/$/, "");
    this.apiBase = cleaned;
    localStorage.setItem("observer_api_base", cleaned);
  },

  buildUrl(path) {
    return `${this.apiBase}${path}`;
  },

  async jsonFetch(path) {
    const response = await fetch(this.buildUrl(path), { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`${path} failed (${response.status})`);
    }
    return response.json();
  },

  get data() {
    if (!this.staticData) return null;
    const d = this.dynamicData || {};
    return {
      ...d,
      width: this.staticData.width,
      height: this.staticData.height,
      tiles: this.staticData.tiles,
      schema_version: d.schema_version ?? this.staticData.schema_version,
      food: Array.isArray(d.food) ? d.food : [],
      wood: Array.isArray(d.wood) ? d.wood : [],
      stone: Array.isArray(d.stone) ? d.stone : [],
      farms: Array.isArray(d.farms) ? d.farms : [],
      structures: Array.isArray(d.structures) ? d.structures : [],
      roads: Array.isArray(d.roads) ? d.roads : [],
      storage_buildings: Array.isArray(d.storage_buildings) ? d.storage_buildings : [],
      buildings: Array.isArray(d.buildings) ? d.buildings : [],
      villages: Array.isArray(d.villages) ? d.villages : [],
      agents: Array.isArray(d.agents) ? d.agents : [],
      civ_stats: d.civ_stats && typeof d.civ_stats === "object" ? d.civ_stats : {},
      infrastructure_systems_available: Array.isArray(d.infrastructure_systems_available) ? d.infrastructure_systems_available : [],
      transport_network_counts: d.transport_network_counts && typeof d.transport_network_counts === "object" ? d.transport_network_counts : {},
    };
  },

  async loadStatic(force = false) {
    if (!force && this.staticData) return this.staticData;
    try {
      const payload = await this.jsonFetch("/state/static");
      this.staticData = payload;
      this.status.staticOk = true;
      this.status.staticError = "";
      this.status.lastStaticAt = Date.now();
      return payload;
    } catch (err) {
      this.status.staticOk = false;
      this.status.staticError = String(err && err.message ? err.message : err);
      throw err;
    }
  },

  async fetchDynamic() {
    if (!this.staticData) {
      await this.loadStatic(false);
    }
    try {
      const payload = await this.jsonFetch("/state");
      this.dynamicData = payload;
      this.indexes = this.buildIndexes(this.data);
      this.status.dynamicOk = true;
      this.status.dynamicError = "";
      this.status.lastDynamicAt = Date.now();
      return payload;
    } catch (err) {
      this.status.dynamicOk = false;
      this.status.dynamicError = String(err && err.message ? err.message : err);
      throw err;
    }
  },

  startPolling(pollMs = 300) {
    this.stopPolling();
    this.pollMs = Math.max(200, Math.min(500, Number(pollMs) || 300));

    const tick = async () => {
      if (this.inFlight) {
        this.pollTimer = setTimeout(tick, this.pollMs);
        return;
      }
      this.inFlight = true;
      try {
        await this.fetchDynamic();
      } catch (_) {
        // Status is already set in fetchDynamic.
      } finally {
        this.inFlight = false;
        this.pollTimer = setTimeout(tick, this.pollMs);
      }
    };

    this.pollTimer = setTimeout(tick, 0);
  },

  stopPolling() {
    if (this.pollTimer) {
      clearTimeout(this.pollTimer);
      this.pollTimer = null;
    }
  },

  key(x, y) {
    return `${x},${y}`;
  },

  buildIndexes(data) {
    const index = {
      foodSet: new Set(),
      woodSet: new Set(),
      stoneSet: new Set(),
      farmsByTile: new Map(),
      roadsSet: new Set(),
      structuresSet: new Set(),
      storageLegacySet: new Set(),
      buildingsById: new Map(),
      buildingsByTile: new Map(),
      villagesByUid: new Map(),
      villagesByTile: new Map(),
      villagesByCenter: new Map(),
      agentsByTile: new Map(),
    };

    const putMapArray = (map, key, value) => {
      const arr = map.get(key);
      if (arr) arr.push(value);
      else map.set(key, [value]);
    };

    for (const p of data.food) {
      index.foodSet.add(this.key(p.x, p.y));
    }
    for (const p of data.wood) {
      index.woodSet.add(this.key(p.x, p.y));
    }
    for (const p of data.stone) {
      index.stoneSet.add(this.key(p.x, p.y));
    }

    for (const f of data.farms) {
      index.farmsByTile.set(this.key(f.x, f.y), f);
    }

    for (const r of data.roads) {
      index.roadsSet.add(this.key(r.x, r.y));
    }

    for (const s of data.structures) {
      index.structuresSet.add(this.key(s.x, s.y));
    }

    for (const s of data.storage_buildings) {
      index.storageLegacySet.add(this.key(s.x, s.y));
    }

    for (const b of data.buildings) {
      const id = String(b.building_id || "");
      if (id) index.buildingsById.set(id, b);
      const footprint = Array.isArray(b.footprint) && b.footprint.length > 0
        ? b.footprint
        : [{ x: b.x, y: b.y }];
      for (const t of footprint) {
        const k = this.key(t.x, t.y);
        putMapArray(index.buildingsByTile, k, b);
      }
    }

    for (const v of data.villages) {
      const uid = String(v.village_uid || "");
      if (uid) index.villagesByUid.set(uid, v);
      if (v.center && Number.isFinite(v.center.x) && Number.isFinite(v.center.y)) {
        index.villagesByCenter.set(this.key(v.center.x, v.center.y), v);
      }
      const tiles = Array.isArray(v.tiles) ? v.tiles : [];
      for (const t of tiles) {
        putMapArray(index.villagesByTile, this.key(t.x, t.y), v);
      }
    }

    for (const a of data.agents) {
      putMapArray(index.agentsByTile, this.key(a.x, a.y), a);
    }

    return index;
  },
};
