const Layers = {
  toggles: {
    terrain: true,
    food: true,
    wood: true,
    stone: true,
    farms: true,
    structures: true,
    storage_buildings: true,
    buildings: true,
    roads: true,
    village_territory: true,
    village_centers: true,
    agents: true,
    village_labels: true,
    hover_coords: false,
  },

  terrainColor(code) {
    if (code === "G") return "#6fcf6a";
    if (code === "F") return "#2f8f45";
    if (code === "M") return "#8d9196";
    if (code === "W") return "#4da6ff";
    if (code === "H") return "#b3986a";
    return "#ffffff";
  },

  farmColor(state) {
    if (state === "prepared") return "#b38b5a";
    if (state === "planted") return "#4f7f35";
    if (state === "growing") return "#4caf50";
    if (state === "ripe") return "#e3be2b";
    if (state === "dead") return "#5d3c32";
    return "#9b815f";
  },

  buildingFill(building) {
    const t = String(building.type || "").toLowerCase();
    const c = String(building.category || "").toLowerCase();
    if (t === "storage") return "#6f5b4d";
    if (t === "house") return "#8d6b3f";
    if (t === "mine") return "#5d6f83";
    if (t === "lumberyard") return "#4f6846";
    if (c === "production") return "#4f6d86";
    if (c === "food_storage") return "#6f5b4d";
    return "#6f7f8a";
  },

  buildingStroke(building) {
    const op = String(building.operational_state || "active").toLowerCase();
    if (op.includes("construction") || op.includes("under")) return "#e0a14f";
    return "#1f2b34";
  },

  draw(ctx, data, indexes, camera, canvas, options) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (this.toggles.terrain) this.drawTerrain(ctx, data, camera, canvas);
    if (this.toggles.village_territory) this.drawVillageTerritories(ctx, data, camera, canvas, options);
    if (this.toggles.roads) this.drawRoads(ctx, data, camera, canvas);
    this.drawResources(ctx, data, camera, canvas);
    if (this.toggles.farms) this.drawFarms(ctx, data, camera, canvas);
    this.drawLegacy(ctx, data, indexes, camera, canvas);
    if (this.toggles.buildings) this.drawBuildings(ctx, data, camera, canvas, options);
    if (this.toggles.village_centers) this.drawVillageCenters(ctx, data, camera, canvas, options);
    if (this.toggles.agents) this.drawAgents(ctx, data, camera, canvas, options);
    if (this.toggles.village_labels) this.drawVillageLabels(ctx, data, camera, canvas);
    this.drawSelection(ctx, camera, options);
    if (this.toggles.hover_coords) this.drawHoverCoord(ctx, camera, options);
  },

  drawTerrain(ctx, data, camera, canvas) {
    const s = camera.cellSize;
    const vw = camera.getViewWidth(canvas);
    const vh = camera.getViewHeight(canvas);
    const width = Number(data.width) || 0;
    const height = Number(data.height) || 0;
    const tiles = Array.isArray(data.tiles) ? data.tiles : [];

    for (let sy = 0; sy < vh; sy += 1) {
      for (let sx = 0; sx < vw; sx += 1) {
        const wx = camera.x + sx;
        const wy = camera.y + sy;
        if (wx < 0 || wy < 0 || wx >= width || wy >= height) continue;
        const row = Array.isArray(tiles[wy]) ? tiles[wy] : [];
        const code = row[wx];
        ctx.fillStyle = this.terrainColor(code);
        ctx.fillRect(sx * s, sy * s, s, s);
      }
    }
  },

  drawRoads(ctx, data, camera, canvas) {
    const s = camera.cellSize;
    for (const r of data.roads) {
      const px = (r.x - camera.x) * s;
      const py = (r.y - camera.y) * s;
      if (px < -s || py < -s || px > canvas.width || py > canvas.height) continue;
      const pad = Math.max(1, Math.floor(s * 0.25));
      ctx.fillStyle = "#c2a27a";
      ctx.fillRect(px + pad, py + pad, s - pad * 2, s - pad * 2);
    }
  },

  drawResources(ctx, data, camera, canvas) {
    const s = camera.cellSize;
    const drawCells = (cells, enabled, color, shape) => {
      if (!enabled) return;
      for (const p of cells) {
        const px = (p.x - camera.x) * s;
        const py = (p.y - camera.y) * s;
        if (px < -s || py < -s || px > canvas.width || py > canvas.height) continue;
        ctx.fillStyle = color;
        if (shape === "circle") {
          ctx.beginPath();
          ctx.arc(px + s / 2, py + s / 2, Math.max(2, s * 0.25), 0, Math.PI * 2);
          ctx.fill();
        } else {
          const pad = Math.max(1, Math.floor(s * 0.2));
          ctx.fillRect(px + pad, py + pad, s - pad * 2, s - pad * 2);
        }
      }
    };

    drawCells(data.food, this.toggles.food, "#19b231", "circle");
    drawCells(data.wood, this.toggles.wood, "#1f4c2b", "square");
    drawCells(data.stone, this.toggles.stone, "#d0d4da", "square");
  },

  drawFarms(ctx, data, camera, canvas) {
    const s = camera.cellSize;
    for (const f of data.farms) {
      const px = (f.x - camera.x) * s;
      const py = (f.y - camera.y) * s;
      if (px < -s || py < -s || px > canvas.width || py > canvas.height) continue;
      const pad = Math.max(1, Math.floor(s * 0.1));
      ctx.fillStyle = this.farmColor(String(f.state || "prepared"));
      ctx.fillRect(px + pad, py + pad, s - pad * 2, s - pad * 2);
      ctx.strokeStyle = "#2d2419";
      ctx.lineWidth = 1;
      ctx.strokeRect(px + pad, py + pad, s - pad * 2, s - pad * 2);
    }
  },

  drawLegacy(ctx, data, indexes, camera, canvas) {
    const s = camera.cellSize;
    const canonicalByTile = indexes.buildingsByTile;

    if (this.toggles.structures) {
      for (const p of data.structures) {
        const key = `${p.x},${p.y}`;
        if (canonicalByTile.has(key)) continue;
        const px = (p.x - camera.x) * s;
        const py = (p.y - camera.y) * s;
        if (px < -s || py < -s || px > canvas.width || py > canvas.height) continue;
        ctx.strokeStyle = "#5f3f2f";
        ctx.lineWidth = 1;
        ctx.strokeRect(px + 1, py + 1, s - 2, s - 2);
      }
    }

    if (this.toggles.storage_buildings) {
      for (const p of data.storage_buildings) {
        const key = `${p.x},${p.y}`;
        if (canonicalByTile.has(key)) continue;
        const px = (p.x - camera.x) * s;
        const py = (p.y - camera.y) * s;
        if (px < -s || py < -s || px > canvas.width || py > canvas.height) continue;
        const pad = Math.max(1, Math.floor(s * 0.22));
        ctx.fillStyle = "rgba(111, 91, 77, 0.7)";
        ctx.fillRect(px + pad, py + pad, s - pad * 2, s - pad * 2);
        ctx.strokeStyle = "#f6ddb8";
        ctx.strokeRect(px + pad, py + pad, s - pad * 2, s - pad * 2);
      }
    }
  },

  drawBuildings(ctx, data, camera, canvas, options) {
    const s = camera.cellSize;
    for (const b of data.buildings) {
      const footprint = Array.isArray(b.footprint) && b.footprint.length > 0
        ? b.footprint
        : [{ x: b.x, y: b.y }];

      for (const tile of footprint) {
        const px = (tile.x - camera.x) * s;
        const py = (tile.y - camera.y) * s;
        if (px < -s || py < -s || px > canvas.width || py > canvas.height) continue;
        ctx.fillStyle = this.buildingFill(b);
        ctx.fillRect(px, py, s, s);

        ctx.strokeStyle = this.buildingStroke(b);
        ctx.lineWidth = 1;
        ctx.strokeRect(px + 0.5, py + 0.5, s - 1, s - 1);

        if (String(b.type || "") === "storage" && b.storage && typeof b.storage === "object") {
          ctx.fillStyle = "#f3e7c6";
          ctx.fillRect(px + Math.max(1, Math.floor(s * 0.34)), py + Math.max(1, Math.floor(s * 0.34)), Math.max(2, Math.floor(s * 0.3)), Math.max(2, Math.floor(s * 0.3)));
        }

        if (b.construction_complete_ratio != null) {
          const ratio = Math.max(0, Math.min(1, Number(b.construction_complete_ratio) || 0));
          const barH = Math.max(2, Math.floor(s * 0.12));
          ctx.fillStyle = "rgba(0,0,0,0.5)";
          ctx.fillRect(px, py + s - barH, s, barH);
          ctx.fillStyle = "#8be28b";
          ctx.fillRect(px, py + s - barH, Math.floor(s * ratio), barH);
        }
      }
    }

    if (options.selectedVillageUid) {
      for (const b of data.buildings) {
        if (String(b.village_uid || "") !== String(options.selectedVillageUid)) continue;
        const footprint = Array.isArray(b.footprint) && b.footprint.length > 0
          ? b.footprint
          : [{ x: b.x, y: b.y }];
        for (const tile of footprint) {
          const px = (tile.x - camera.x) * s;
          const py = (tile.y - camera.y) * s;
          if (px < -s || py < -s || px > canvas.width || py > canvas.height) continue;
          ctx.strokeStyle = "#ffdf7a";
          ctx.lineWidth = 2;
          ctx.strokeRect(px + 1, py + 1, s - 2, s - 2);
        }
      }
      ctx.lineWidth = 1;
    }
  },

  drawVillageTerritories(ctx, data, camera, canvas, options) {
    const s = camera.cellSize;
    for (const v of data.villages) {
      const color = String(v.color || "#ffd46a");
      const tiles = Array.isArray(v.tiles) ? v.tiles : [];
      const isSelected = String(v.village_uid || "") === String(options.selectedVillageUid || "");
      for (const t of tiles) {
        const px = (t.x - camera.x) * s;
        const py = (t.y - camera.y) * s;
        if (px < -s || py < -s || px > canvas.width || py > canvas.height) continue;
        ctx.fillStyle = isSelected ? this.alphaColor(color, 0.26) : this.alphaColor(color, 0.12);
        ctx.fillRect(px, py, s, s);
      }
    }
  },

  drawVillageCenters(ctx, data, camera, canvas, options) {
    const s = camera.cellSize;
    for (const v of data.villages) {
      if (v.farm_zone_center && Number.isFinite(v.farm_zone_center.x) && Number.isFinite(v.farm_zone_center.y)) {
        const fzx = (v.farm_zone_center.x - camera.x) * s + (s / 2);
        const fzy = (v.farm_zone_center.y - camera.y) * s + (s / 2);
        if (!(fzx < -s || fzy < -s || fzx > canvas.width + s || fzy > canvas.height + s)) {
          ctx.fillStyle = "#f0cf6e";
          ctx.beginPath();
          ctx.arc(fzx, fzy, Math.max(2, Math.floor(s * 0.18)), 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = "#2b2620";
          ctx.stroke();
        }
      }

      if (!v.center || !Number.isFinite(v.center.x) || !Number.isFinite(v.center.y)) continue;
      const cx = (v.center.x - camera.x) * s + (s / 2);
      const cy = (v.center.y - camera.y) * s + (s / 2);
      if (cx < -s || cy < -s || cx > canvas.width + s || cy > canvas.height + s) continue;

      const isSelected = String(v.village_uid || "") === String(options.selectedVillageUid || "");
      ctx.beginPath();
      ctx.arc(cx, cy, Math.max(3, Math.floor(s * 0.25)), 0, Math.PI * 2);
      ctx.fillStyle = isSelected ? "#fff2a6" : (v.color || "#ffd46a");
      ctx.fill();
      ctx.strokeStyle = "#1b252c";
      ctx.stroke();
    }
  },

  drawVillageLabels(ctx, data, camera, canvas) {
    const s = camera.cellSize;
    ctx.font = `${Math.max(10, Math.floor(s * 0.5))}px ui-monospace, monospace`;
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    for (const v of data.villages) {
      if (!v.center || !Number.isFinite(v.center.x) || !Number.isFinite(v.center.y)) continue;
      const cx = (v.center.x - camera.x) * s + (s / 2);
      const cy = (v.center.y - camera.y) * s;
      if (cx < -s || cy < -s || cx > canvas.width + s || cy > canvas.height + s) continue;
      const label = (v.id != null) ? `V${v.id}` : String(v.village_uid || "village");
      ctx.fillStyle = "#0d0f10";
      ctx.fillText(label, cx + 1, cy - 1);
      ctx.fillStyle = "#f0f5fa";
      ctx.fillText(label, cx, cy - 2);
    }
  },

  drawAgents(ctx, data, camera, canvas, options) {
    const s = camera.cellSize;
    for (const a of data.agents) {
      const px = (a.x - camera.x) * s;
      const py = (a.y - camera.y) * s;
      if (px < -s || py < -s || px > canvas.width || py > canvas.height) continue;
      const isPlayer = Boolean(a.is_player);
      ctx.fillStyle = isPlayer ? "#ff6464" : "#63b7ff";
      ctx.fillRect(px + 1, py + 1, s - 2, s - 2);

      if (String(a.role || "") === "leader") {
        ctx.fillStyle = "#ffd166";
        ctx.beginPath();
        ctx.arc(px + s * 0.5, py + s * 0.5, Math.max(2, s * 0.18), 0, Math.PI * 2);
        ctx.fill();
      }

      if (options.selectedVillage && a.village_id != null && options.selectedVillage.id != null && a.village_id === options.selectedVillage.id) {
        ctx.strokeStyle = "#f9ee9a";
        ctx.lineWidth = 2;
      } else {
        ctx.strokeStyle = "#15212a";
        ctx.lineWidth = 1;
      }
      ctx.strokeRect(px + 0.5, py + 0.5, s - 1, s - 1);
    }
    ctx.lineWidth = 1;
  },

  drawSelection(ctx, camera, options) {
    if (!options.selectedTile) return;
    const s = camera.cellSize;
    const px = (options.selectedTile.x - camera.x) * s;
    const py = (options.selectedTile.y - camera.y) * s;
    ctx.strokeStyle = "#ffe38d";
    ctx.lineWidth = 2;
    ctx.strokeRect(px + 1, py + 1, s - 2, s - 2);
    ctx.lineWidth = 1;
  },

  drawHoverCoord(ctx, camera, options) {
    if (!options.hoverTile) return;
    const s = camera.cellSize;
    const px = (options.hoverTile.x - camera.x) * s;
    const py = (options.hoverTile.y - camera.y) * s;
    ctx.strokeStyle = "rgba(255,255,255,0.65)";
    ctx.strokeRect(px + 0.5, py + 0.5, s - 1, s - 1);
  },

  alphaColor(hex, alpha) {
    const fallback = `rgba(255,212,106,${alpha})`;
    if (!/^#([0-9a-fA-F]{6})$/.test(hex)) return fallback;
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  },
};
