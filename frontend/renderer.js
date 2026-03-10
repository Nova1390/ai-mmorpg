const Renderer = {
  canvas: null,
  ctx: null,
  minimapCanvas: null,
  minimapCtx: null,
  connectionPanel: null,
  summaryPanel: null,
  infraPanel: null,
  civStatsPanel: null,
  villagesMeta: null,
  villageList: null,
  agentsMeta: null,
  agentList: null,
  hoverPanel: null,
  selectionPanel: null,
  layerToggles: null,
  statusBar: null,

  selectedTile: null,
  hoverTile: null,
  selectedVillageUid: "",
  _lastDataKey: "",
  _lastHoverKey: "",
  _lastSelectionKey: "",

  onSelectVillage: null,

  init() {
    this.canvas = document.getElementById("world");
    this.ctx = this.canvas.getContext("2d");
    this.minimapCanvas = document.getElementById("minimap");
    this.minimapCtx = this.minimapCanvas ? this.minimapCanvas.getContext("2d") : null;

    this.connectionPanel = document.getElementById("connectionPanel");
    this.summaryPanel = document.getElementById("summaryPanel");
    this.infraPanel = document.getElementById("infraPanel");
    this.civStatsPanel = document.getElementById("civStatsPanel");
    this.villagesMeta = document.getElementById("villagesMeta");
    this.villageList = document.getElementById("villageList");
    this.agentsMeta = document.getElementById("agentsMeta");
    this.agentList = document.getElementById("agentList");
    this.hoverPanel = document.getElementById("hoverPanel");
    this.selectionPanel = document.getElementById("selectionPanel");
    this.layerToggles = document.getElementById("layerToggles");
    this.statusBar = document.getElementById("statusBar");

    this.bindLayerToggles();
    this.bindVillageList();
  },

  bindLayerToggles() {
    this.layerToggles.innerHTML = "";
    const keys = Object.keys(Layers.toggles);
    for (const key of keys) {
      const id = `layer_${key}`;
      const label = document.createElement("label");
      label.className = "toggle-item";
      label.setAttribute("for", id);

      const input = document.createElement("input");
      input.type = "checkbox";
      input.id = id;
      input.checked = !!Layers.toggles[key];
      input.addEventListener("change", () => {
        Layers.toggles[key] = input.checked;
      });

      const text = document.createElement("span");
      text.textContent = key;

      label.appendChild(input);
      label.appendChild(text);
      this.layerToggles.appendChild(label);
    }
  },

  bindVillageList() {
    this.villageList.addEventListener("click", (event) => {
      const row = event.target.closest(".list-item[data-vuid]");
      if (!row) return;
      const uid = String(row.dataset.vuid || "");
      this.selectedVillageUid = uid;
      if (typeof this.onSelectVillage === "function") {
        this.onSelectVillage(uid);
      }
    });
  },

  setHoverTile(tile) {
    this.hoverTile = tile;
  },

  setSelectedTile(tile) {
    this.selectedTile = tile;
  },

  setSelectedVillage(uid) {
    this.selectedVillageUid = String(uid || "");
  },

  draw() {
    const data = State.data;
    if (!data) {
      this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
      this.renderStatusBar(null);
      this.renderConnection();
      return;
    }

    const selectedVillage = this.getSelectedVillage(data);

    Layers.draw(this.ctx, data, State.indexes || State.buildIndexes(data), Camera, this.canvas, {
      selectedTile: this.selectedTile,
      hoverTile: this.hoverTile,
      selectedVillageUid: this.selectedVillageUid,
      selectedVillage,
    });
    this.drawMinimap(data);

    this.renderStatusBar(data);
    this.renderConnection();

    const dataKey = `${this.v(data.state_version)}|${this.v(data.tick)}|${this.v(data.villages?.length)}|${this.v(data.agents?.length)}|${this.v(State.status.lastDynamicAt)}`;
    if (dataKey !== this._lastDataKey) {
      this._lastDataKey = dataKey;
      this.renderSummary(data);
      this.renderInfrastructure(data);
      this.renderCivStats(data);
      this.renderVillageList(data);
      this.renderAgentList(data);
    }

    const hoverKey = this.hoverTile ? `${this.hoverTile.x},${this.hoverTile.y}|${dataKey}` : `none|${dataKey}`;
    if (hoverKey !== this._lastHoverKey) {
      this._lastHoverKey = hoverKey;
      this.renderHoverPanel(data);
    }

    const selectionKey = `${this.selectedVillageUid}|${this.selectedTile ? `${this.selectedTile.x},${this.selectedTile.y}` : "none"}|${dataKey}`;
    if (selectionKey !== this._lastSelectionKey) {
      this._lastSelectionKey = selectionKey;
      this.renderSelectionPanel(data, selectedVillage);
    }
  },

  kvGrid(el, rows) {
    el.innerHTML = rows.map(([k, v]) => `<div class="kv-k">${this.escapeHtml(k)}</div><div>${this.escapeHtml(v)}</div>`).join("");
  },

  renderConnection() {
    const s = State.status;
    this.kvGrid(this.connectionPanel, [
      ["API base", State.apiBase || "(same origin)"],
      ["/state/static", s.staticOk ? "ok" : "error"],
      ["/state", s.dynamicOk ? "ok" : "error"],
      ["last static", this.formatTime(s.lastStaticAt)],
      ["last dynamic", this.formatTime(s.lastDynamicAt)],
      ["static error", s.staticError || "-"],
      ["dynamic error", s.dynamicError || "-"],
    ]);

    const values = this.connectionPanel.querySelectorAll("div:nth-child(even)");
    if (values[1]) values[1].className = State.status.staticOk ? "ok" : "bad";
    if (values[2]) values[2].className = State.status.dynamicOk ? "ok" : "bad";
  },

  renderStatusBar(data) {
    if (!this.statusBar) return;
    const s = State.status || {};
    const staticPart = s.staticOk ? "static:ok" : "static:error";
    const dynamicPart = s.dynamicOk ? "dynamic:ok" : "dynamic:error";
    const tick = data ? this.v(data.tick) : "-";
    const stateVersion = data ? this.v(data.state_version) : "-";
    const updated = this.formatTime(s.lastDynamicAt || s.lastStaticAt);
    const err = s.dynamicError || s.staticError || "";

    this.statusBar.innerHTML = [
      `<span>${this.escapeHtml(staticPart)}</span>`,
      `<span>${this.escapeHtml(dynamicPart)}</span>`,
      `<span>tick: ${this.escapeHtml(tick)}</span>`,
      `<span>state_version: ${this.escapeHtml(stateVersion)}</span>`,
      `<span>updated: ${this.escapeHtml(updated)}</span>`,
      `<span>${err ? `error: ${this.escapeHtml(err)}` : "error: -"}</span>`,
    ].join("");
  },

  renderSummary(data) {
    this.kvGrid(this.summaryPanel, [
      ["schema_version", this.v(data.schema_version)],
      ["state_version", this.v(data.state_version)],
      ["tick", this.v(data.tick)],
      ["population", this.v(data.population)],
      ["players", this.v(data.players)],
      ["npcs", this.v(data.npcs)],
      ["avg_hunger", this.v(data.avg_hunger)],
      ["food_count", this.v(data.food_count)],
      ["wood_count", this.v(data.wood_count)],
      ["stone_count", this.v(data.stone_count)],
      ["houses_count", this.v(data.houses_count)],
      ["villages_count", this.v(data.villages_count)],
      ["farms_count", this.v(data.farms_count)],
      ["leaders_count", this.v(data.leaders_count)],
      ["llm_interactions", this.v(data.llm_interactions)],
    ]);
  },

  renderInfrastructure(data) {
    const systems = Array.isArray(data.infrastructure_systems_available)
      ? data.infrastructure_systems_available.join(", ")
      : "-";

    const counts = data.transport_network_counts && typeof data.transport_network_counts === "object"
      ? Object.entries(data.transport_network_counts).map(([k, v]) => `${k}:${v}`).join(", ")
      : "-";

    this.kvGrid(this.infraPanel, [
      ["systems", systems || "-"],
      ["transport_network_counts", counts || "-"],
    ]);
  },

  renderCivStats(data) {
    const c = data.civ_stats || {};
    this.kvGrid(this.civStatsPanel, [
      ["largest_village_id", this.v(c.largest_village_id)],
      ["largest_village_houses", this.v(c.largest_village_houses)],
      ["strongest_village_id", this.v(c.strongest_village_id)],
      ["strongest_village_power", this.v(c.strongest_village_power)],
      ["expanding_village_id", this.v(c.expanding_village_id)],
      ["warring_villages", this.v(c.warring_villages)],
      ["migrating_villages", this.v(c.migrating_villages)],
    ]);
  },

  renderVillageList(data) {
    const villages = Array.isArray(data.villages) ? data.villages : [];
    this.villagesMeta.textContent = `${villages.length} villages`;

    const rows = villages.map((v) => {
      const idOrUid = v.id != null ? `V${v.id}` : String(v.village_uid || "-");
      const title = `${idOrUid} pop=${this.v(v.population)} houses=${this.v(v.houses)} pri=${this.v(v.priority)} strat=${this.v(v.strategy)} rel=${this.v(v.relation)} power=${this.v(v.power)}`;
      const selected = String(v.village_uid || "") === String(this.selectedVillageUid || "") ? " selected" : "";
      return `<div class="list-item${selected}" data-vuid="${this.escapeAttr(String(v.village_uid || ""))}">${this.escapeHtml(title)}</div>`;
    });

    this.villageList.innerHTML = rows.join("") || '<div class="list-item">-</div>';
  },

  renderAgentList(data) {
    const all = Array.isArray(data.agents) ? data.agents : [];
    const filter = String(document.getElementById("agentFilterInput")?.value || "").trim().toLowerCase();
    const cap = Number(document.getElementById("agentCapSelect")?.value || 100);

    const filtered = filter
      ? all.filter((a) => {
          const hay = `${a.agent_id || ""} ${a.role || ""} ${a.task || ""} ${a.village_id ?? ""}`.toLowerCase();
          return hay.includes(filter);
        })
      : all;

    const capped = filtered.slice(0, cap);
    this.agentsMeta.textContent = `showing ${capped.length}/${filtered.length} (total ${all.length})`;

    const rows = capped.map((a) => {
      const who = a.is_player ? "player" : "npc";
      const label = `${a.agent_id || "-"} @ (${a.x},${a.y}) ${who} role=${a.role || "-"} task=${a.task || "-"} v=${a.village_id ?? "-"}`;
      return `<div class="list-item">${this.escapeHtml(label)}</div>`;
    });

    this.agentList.innerHTML = rows.join("") || '<div class="list-item">-</div>';
  },

  renderHoverPanel(data) {
    const tile = this.hoverTile;
    if (!tile) {
      this.hoverPanel.textContent = "-";
      return;
    }

    const idx = State.indexes || State.buildIndexes(data);
    const key = `${tile.x},${tile.y}`;

    const row = Array.isArray(data.tiles) ? data.tiles[tile.y] : null;
    const terrain = (Array.isArray(row) ? row[tile.x] : null);
    const farm = idx.farmsByTile.get(key) || null;
    const buildings = idx.buildingsByTile.get(key) || [];
    const villages = idx.villagesByTile.get(key) || [];
    const agents = idx.agentsByTile.get(key) || [];

    const lines = [];
    lines.push(`coords: (${tile.x}, ${tile.y})`);
    lines.push(`terrain: ${terrain ?? "-"}`);
    lines.push(`resource: ${[
      idx.foodSet.has(key) ? "food" : null,
      idx.woodSet.has(key) ? "wood" : null,
      idx.stoneSet.has(key) ? "stone" : null,
    ].filter(Boolean).join(", ") || "none"}`);
    lines.push(`farm: ${farm ? `${farm.state || "unknown"} growth=${this.v(farm.growth)} village_id=${this.v(farm.village_id)}` : "none"}`);
    lines.push(`road: ${idx.roadsSet.has(key) ? "yes" : "no"}`);
    lines.push(`legacy structure: ${idx.structuresSet.has(key) ? "yes" : "no"}`);
    lines.push(`legacy storage: ${idx.storageLegacySet.has(key) ? "yes" : "no"}`);

    if (buildings.length > 0) {
      const parts = buildings.slice(0, 4).map((b) => {
        const svc = b.service && typeof b.service === "object"
          ? ` service(t=${this.v(b.service.transport)},l=${this.v(b.service.logistics)},e=${this.v(b.service.efficiency_multiplier)})`
          : "";
        const storage = b.storage ? ` storage=${JSON.stringify(b.storage)}` : "";
        const ratio = b.construction_complete_ratio != null
          ? ` progress=${this.v(b.construction_complete_ratio)}(${this.v(b.construction_progress)}/${this.v(b.construction_required_work)})`
          : "";
        return `${b.building_id || "?"} type=${b.type || "?"} cat=${b.category || "?"} tier=${this.v(b.tier)} v_id=${this.v(b.village_id)} road=${this.v(b.connected_to_road)} op=${this.v(b.operational_state)} linked=${this.v(b.linked_resource_type)} cap=${this.v(b.storage_capacity)}${ratio}${svc}${storage}`;
      });
      lines.push(`buildings:\n- ${parts.join("\n- ")}`);
    } else {
      lines.push("buildings: none");
    }

    if (villages.length > 0) {
      const owned = villages.map((v) => `${v.id != null ? `id=${v.id}` : ""} uid=${v.village_uid || "-"}`).join(" | ");
      lines.push(`village ownership: ${owned}`);
    } else {
      lines.push("village ownership: none");
    }

    if (agents.length > 0) {
      const who = agents.map((a) => `${a.agent_id} role=${a.role || "-"} task=${a.task || "-"}`).join(" | ");
      lines.push(`agents: ${who}`);
    } else {
      lines.push("agents: none");
    }

    this.hoverPanel.textContent = lines.join("\n");
  },

  renderSelectionPanel(data, selectedVillage) {
    const lines = [];
    const tile = this.selectedTile;
    if (!tile || !this.isTileInside(tile, data)) {
      lines.push("Selected Tile");
      lines.push("- none");
      this.selectionPanel.textContent = lines.join("\n");
      return;
    }

    const idx = State.indexes || State.buildIndexes(data);
    const key = `${tile.x},${tile.y}`;
    const row = Array.isArray(data.tiles) ? data.tiles[tile.y] : null;
    const terrainCode = (Array.isArray(row) ? row[tile.x] : null);
    const terrainLabel = this.terrainLabel(terrainCode);
    const farm = idx.farmsByTile.get(key) || null;
    const hasRoad = idx.roadsSet.has(key);
    const hasStructure = idx.structuresSet.has(key);
    const hasStorageLegacy = idx.storageLegacySet.has(key);
    const buildings = idx.buildingsByTile.get(key) || [];
    const villages = idx.villagesByTile.get(key) || [];
    const agents = idx.agentsByTile.get(key) || [];

    lines.push("Selected Tile");
    lines.push(`- coordinates: (${tile.x}, ${tile.y})`);
    lines.push(`- terrain: ${this.v(terrainCode)} (${terrainLabel})`);

    lines.push("");
    lines.push("Resources");
    lines.push(`- food: ${idx.foodSet.has(key) ? "yes" : "no"}`);
    lines.push(`- wood: ${idx.woodSet.has(key) ? "yes" : "no"}`);
    lines.push(`- stone: ${idx.stoneSet.has(key) ? "yes" : "no"}`);

    lines.push("");
    lines.push("Farm");
    if (farm) {
      lines.push(`- exists: yes`);
      lines.push(`- state: ${this.v(farm.state)}`);
      lines.push(`- growth: ${this.v(farm.growth)}`);
      lines.push(`- village_id: ${this.v(farm.village_id)}`);
    } else {
      lines.push("- exists: no");
    }

    lines.push("");
    lines.push("Infrastructure / Legacy");
    lines.push(`- road: ${hasRoad ? "yes" : "no"}`);
    lines.push(`- structure: ${hasStructure ? "yes" : "no"}`);
    lines.push(`- storage_building: ${hasStorageLegacy ? "yes" : "no"}`);

    lines.push("");
    lines.push("Buildings (canonical)");
    if (buildings.length === 0) {
      lines.push("- none");
    } else {
      for (const b of buildings) {
        lines.push(`- building_id: ${this.v(b.building_id)}`);
        lines.push(`  type: ${this.v(b.type)}`);
        lines.push(`  category: ${this.v(b.category)}`);
        lines.push(`  tier: ${this.v(b.tier)}`);
        lines.push(`  village_id: ${this.v(b.village_id)}`);
        lines.push(`  village_uid: ${this.v(b.village_uid)}`);
        lines.push(`  connected_to_road: ${this.v(b.connected_to_road)}`);
        lines.push(`  operational_state: ${this.v(b.operational_state)}`);
        lines.push(`  linked_resource_type: ${this.v(b.linked_resource_type)}`);
        lines.push(`  linked_resource_tiles_count: ${this.v(b.linked_resource_tiles_count)}`);
        lines.push(`  storage: ${this.stringify(b.storage)}`);
        lines.push(`  storage_capacity: ${this.v(b.storage_capacity)}`);
        lines.push(`  construction_progress: ${this.v(b.construction_progress)}`);
        lines.push(`  construction_required_work: ${this.v(b.construction_required_work)}`);
        lines.push(`  construction_complete_ratio: ${this.v(b.construction_complete_ratio)}`);
      }
    }

    lines.push("");
    lines.push("Villages");
    if (villages.length === 0) {
      lines.push("- none");
    } else {
      for (const v of villages) {
        lines.push(`- id: ${this.v(v.id)}`);
        lines.push(`  village_uid: ${this.v(v.village_uid)}`);
        lines.push(`  center: ${this.stringify(v.center)}`);
        lines.push(`  houses: ${this.v(v.houses)}`);
        lines.push(`  population: ${this.v(v.population)}`);
        lines.push(`  strategy: ${this.v(v.strategy)}`);
        lines.push(`  priority: ${this.v(v.priority)}`);
        lines.push(`  relation: ${this.v(v.relation)}`);
        lines.push(`  power: ${this.v(v.power)}`);
        lines.push(`  leader_id: ${this.v(v.leader_id)}`);
        lines.push(`  target_village_id: ${this.v(v.target_village_id)}`);
        lines.push(`  migration_target_id: ${this.v(v.migration_target_id)}`);
        lines.push(`  storage: ${this.stringify(v.storage)}`);
        lines.push(`  farm_zone_center: ${this.stringify(v.farm_zone_center)}`);
        lines.push(`  metrics: ${this.stringify(v.metrics)}`);
        lines.push(`  needs: ${this.stringify(v.needs)}`);
        lines.push(`  phase: ${this.v(v.phase)}`);
      }
    }

    lines.push("");
    lines.push("Agents");
    if (agents.length === 0) {
      lines.push("- none");
    } else {
      for (const a of agents) {
        lines.push(`- agent_id: ${this.v(a.agent_id)}`);
        lines.push(`  is_player: ${this.v(a.is_player)}`);
        lines.push(`  player_id: ${this.v(a.player_id)}`);
        lines.push(`  role: ${this.v(a.role)}`);
        lines.push(`  village_id: ${this.v(a.village_id)}`);
        lines.push(`  task: ${this.v(a.task)}`);
        lines.push(`  inventory: ${this.stringify(a.inventory)}`);
        lines.push(`  max_inventory: ${this.v(a.max_inventory)}`);
      }
    }

    this.selectionPanel.textContent = lines.join("\n");
  },

  getSelectedVillage(data) {
    if (!this.selectedVillageUid) return null;
    const idx = State.indexes || State.buildIndexes(data);
    return idx.villagesByUid.get(String(this.selectedVillageUid)) || null;
  },

  worldToTile(clientX, clientY) {
    const rect = this.canvas.getBoundingClientRect();
    const px = clientX - rect.left;
    const py = clientY - rect.top;
    const wx = Math.floor(Camera.x + (px / Camera.cellSize));
    const wy = Math.floor(Camera.y + (py / Camera.cellSize));
    return { x: wx, y: wy };
  },

  isTileInside(tile, data) {
    if (!tile || !data) return false;
    const w = Number(data.width);
    const h = Number(data.height);
    if (!Number.isFinite(w) || !Number.isFinite(h)) return false;
    return tile.x >= 0 && tile.y >= 0 && tile.x < w && tile.y < h;
  },

  selectVillageByTile(tile, data) {
    const idx = State.indexes || State.buildIndexes(data);
    const villages = idx.villagesByTile.get(`${tile.x},${tile.y}`) || [];
    if (villages.length > 0) {
      this.selectedVillageUid = String(villages[0].village_uid || "");
      return;
    }

    const centered = idx.villagesByCenter.get(`${tile.x},${tile.y}`);
    if (centered) {
      this.selectedVillageUid = String(centered.village_uid || "");
      return;
    }

    this.selectedVillageUid = "";
  },

  formatTime(ts) {
    if (!ts) return "-";
    const d = new Date(ts);
    return `${d.toLocaleTimeString()} (${d.toLocaleDateString()})`;
  },

  v(value) {
    return value == null ? "-" : String(value);
  },

  stringify(value) {
    if (value == null) return "null";
    if (typeof value === "string") return value;
    try {
      return JSON.stringify(value);
    } catch (_) {
      return String(value);
    }
  },

  escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  },

  escapeAttr(value) {
    return this.escapeHtml(value).replaceAll("`", "");
  },

  terrainLabel(code) {
    if (code === "G") return "grass";
    if (code === "F") return "forest";
    if (code === "M") return "mountain";
    if (code === "W") return "water";
    if (code === "H") return "hill";
    return "unknown";
  },

  drawMinimap(data) {
    if (!this.minimapCanvas || !this.minimapCtx) return;
    const ctx = this.minimapCtx;
    const canvas = this.minimapCanvas;
    const w = canvas.width;
    const h = canvas.height;
    const worldW = Math.max(1, Number(data.width) || 1);
    const worldH = Math.max(1, Number(data.height) || 1);
    const sx = w / worldW;
    const sy = h / worldH;

    ctx.clearRect(0, 0, w, h);

    const step = Math.max(1, Math.floor(worldW / 180));
    for (let y = 0; y < worldH; y += step) {
      const row = Array.isArray(data.tiles) ? data.tiles[y] : null;
      for (let x = 0; x < worldW; x += step) {
        const code = Array.isArray(row) ? row[x] : null;
        ctx.fillStyle = Layers.terrainColor(code);
        ctx.fillRect(x * sx, y * sy, step * sx, step * sy);
      }
    }

    for (const r of data.roads || []) {
      ctx.fillStyle = "#c2a27a";
      ctx.fillRect(r.x * sx, r.y * sy, Math.max(1, sx), Math.max(1, sy));
    }

    for (const f of data.farms || []) {
      ctx.fillStyle = Layers.farmColor(String(f.state || ""));
      ctx.fillRect(f.x * sx, f.y * sy, Math.max(1, sx), Math.max(1, sy));
    }

    for (const b of data.buildings || []) {
      const footprint = Array.isArray(b.footprint) && b.footprint.length > 0 ? b.footprint : [{ x: b.x, y: b.y }];
      for (const t of footprint) {
        ctx.fillStyle = Layers.buildingFill(b);
        ctx.fillRect(t.x * sx, t.y * sy, Math.max(1, sx), Math.max(1, sy));
      }
    }

    for (const a of data.agents || []) {
      ctx.fillStyle = a.is_player ? "#ff6464" : "#63b7ff";
      ctx.fillRect(a.x * sx, a.y * sy, Math.max(1, sx), Math.max(1, sy));
    }

    if (this.selectedTile && this.isTileInside(this.selectedTile, data)) {
      ctx.strokeStyle = "#ffe38d";
      ctx.lineWidth = 1;
      ctx.strokeRect(this.selectedTile.x * sx, this.selectedTile.y * sy, Math.max(1, sx), Math.max(1, sy));
    }

    const viewW = Camera.getViewWidth(this.canvas);
    const viewH = Camera.getViewHeight(this.canvas);
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1;
    ctx.strokeRect(Camera.x * sx, Camera.y * sy, Math.max(2, viewW * sx), Math.max(2, viewH * sy));
  },
};
