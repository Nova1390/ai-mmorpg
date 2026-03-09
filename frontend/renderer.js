const Renderer = {
  canvas: null,
  ctx: null,
  minimap: null,
  mctx: null,
  statsEl: null,
  inspectEl: null,

  init() {
    this.canvas = document.getElementById("world");
    this.ctx = this.canvas.getContext("2d");

    this.minimap = document.getElementById("minimap");
    this.mctx = this.minimap.getContext("2d");

    this.statsEl = document.getElementById("stats");
    this.inspectEl = document.getElementById("inspect");
  },

  draw() {
    const data = State.data;
    if (!data) return;

    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    Layers.terrain(this.ctx, data, Camera, this.canvas);
    Layers.roads(this.ctx, data, Camera, this.canvas);
    Layers.resources(this.ctx, data, Camera, this.canvas);
    Layers.buildings(this.ctx, data, Camera, this.canvas);
    Layers.farms(this.ctx, data, Camera, this.canvas);
    Layers.villages(this.ctx, data, Camera, this.canvas);
    Layers.agents(this.ctx, data, Camera, this.canvas);

    Layers.minimap(this.mctx, this.minimap, data, Camera, this.canvas);

    this.renderStats(data, State.playerData);
  },

  renderStats(data, playerData) {
    const inv = playerData?.inventory || { food: 0, wood: 0, stone: 0 };
    const civ = data.civ_stats || {};

    let totalStoredFood = 0;
    let totalStoredWood = 0;
    let totalStoredStone = 0;

    (data.villages || []).forEach(v => {
      const s = v.storage || {};
      totalStoredFood += s.food || 0;
      totalStoredWood += s.wood || 0;
      totalStoredStone += s.stone || 0;
    });

    const topVillages = [...(data.villages || [])]
      .sort((a, b) => (b.houses || 0) - (a.houses || 0))
      .slice(0, 5)
      .map(v => {
        const s = v.storage || {};
        return `#${v.id} houses=${v.houses} pop=${v.population} leader=${v.leader_id ? "yes" : "no"} strategy=${v.strategy} food=${s.food || 0} wood=${s.wood || 0} stone=${s.stone || 0}`;
      })
      .join("\n");

    const dbg = State.metrics || {};
    const dbgWorld = dbg.world || {};
    const dbgLogistics = dbg.logistics || {};
    const dbgProd = dbg.production || {};
    const dbgCog = dbg.cognition_society || {};
    const dbgLLM = dbg.llm_reflection || {};
    const history = Array.isArray(State.history) ? State.history : [];
    const recentTicks = history.slice(-8).map(s => `${s.tick}:${(s.world || {}).population || 0}`).join(" | ");
    const topIntentions = Object.entries(dbgCog.active_intentions_by_type || {})
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([k, v]) => `${k}=${v}`)
      .join(", ");
    const specialists = Object.entries(dbgCog.specialists_by_role || {})
      .sort((a, b) => b[1] - a[1])
      .map(([k, v]) => `${k}=${v}`)
      .join(", ");
    const llmReasons = Object.entries(dbgLLM.reflection_reason_counts || {})
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
      .map(([k, v]) => `${k}=${v}`)
      .join(", ");
    const llmSkips = Object.entries(dbgLLM.reflection_skip_reason_counts || {})
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
      .map(([k, v]) => `${k}=${v}`)
      .join(", ");
    const topReflectionAgents = (dbgLLM.llm_calls_per_agent_top || [])
      .slice(0, 5)
      .map(a => `${(a.agent_id || "").slice(0, 8)}=${a.calls}`)
      .join(", ");

    this.statsEl.textContent =
`WORLD STATS
tick: ${data.tick}
population: ${data.population} (players: ${data.players}, npcs: ${data.npcs})
avg_hunger: ${data.avg_hunger}

food: ${data.food_count}
wood: ${data.wood_count}
stone: ${data.stone_count}
farms: ${data.farms_count}
houses: ${data.houses_count}
villages: ${data.villages_count}
leaders: ${data.leaders_count}
llm_interactions: ${data.llm_interactions}

roads: ${(data.roads || []).length}
storage_buildings: ${(data.storage_buildings || []).length}

camera: (${Camera.x}, ${Camera.y})
zoom_cell: ${Camera.cellSize}
follow_player: ${Camera.followPlayer ? "yes" : "no"}

PLAYER
id: ${State.playerId ? State.playerId.slice(0, 8) + "..." : "-"}
pos: ${playerData ? `(${playerData.x}, ${playerData.y})` : "-"}
hunger: ${playerData ? playerData.hunger : "-"}
goal: ${playerData ? playerData.goal : "-"}
role: ${playerData ? playerData.role : "-"}
village_id: ${playerData ? playerData.village_id : "-"}
inventory: food=${inv.food ?? 0}, wood=${inv.wood ?? 0}, stone=${inv.stone ?? 0}

CIVILIZATION
largest_village: ${civ.largest_village_id ?? "-"} (houses=${civ.largest_village_houses ?? 0})
strongest_village: ${civ.strongest_village_id ?? "-"} (power=${civ.strongest_village_power ?? 0})
expanding_village: ${civ.expanding_village_id ?? "-"}
warring_villages: ${civ.warring_villages ?? 0}
migrating_villages: ${civ.migrating_villages ?? 0}
stored_food: ${totalStoredFood}
stored_wood: ${totalStoredWood}
stored_stone: ${totalStoredStone}

VILLAGES
${topVillages || "-"}

OBSERVABILITY OVERVIEW
obs_tick: ${dbg.tick ?? "-"}
obs_population: ${dbgWorld.population ?? "-"}
obs_villages: ${dbgWorld.villages ?? "-"}
obs_stored: food=${dbgWorld.stored_food ?? "-"} wood=${dbgWorld.stored_wood ?? "-"} stone=${dbgWorld.stored_stone ?? "-"}
obs_under_construction: ${dbgWorld.under_construction_count ?? "-"}
obs_transport: ${JSON.stringify(dbgWorld.transport_network_counts || {})}

ECONOMY / LOGISTICS
prod_food_total=${dbgProd.total_food_gathered ?? "-"} (direct=${dbgProd.direct_food_gathered ?? "-"})
prod_wood_total=${dbgProd.total_wood_gathered ?? "-"} (direct=${dbgProd.direct_wood_gathered ?? "-"}, lumberyard=${dbgProd.wood_from_lumberyards ?? "-"})
prod_stone_total=${dbgProd.total_stone_gathered ?? "-"} (direct=${dbgProd.direct_stone_gathered ?? "-"}, mine=${dbgProd.stone_from_mines ?? "-"})
internal_transfers=${dbgLogistics.internal_transfers_count ?? "-"}
construction_deliveries=${dbgLogistics.construction_deliveries_count ?? "-"}
blocked_construction=${dbgLogistics.blocked_construction_count ?? "-"}
storage_utilization_avg=${dbgLogistics.storage_utilization_avg ?? "-"}

COGNITION / SOCIETY
blocked_intentions=${dbgCog.blocked_intentions_count ?? "-"}
top_intentions=${topIntentions || "-"}
specialists=${specialists || "-"}
leadership_changes=${dbgCog.leadership_changes ?? "-"}

LLM REFLECTION
attempts=${dbgLLM.reflection_attempt_count ?? "-"} accepted=${dbgLLM.reflection_success_count ?? "-"} rejected=${dbgLLM.reflection_rejection_count ?? "-"} fallback=${dbgLLM.reflection_fallback_count ?? "-"}
reason_counts=${llmReasons || "-"}
skip_reasons=${llmSkips || "-"}
top_agents=${topReflectionAgents || "-"}

RECENT POP HISTORY
${recentTicks || "-"}`;
  }
};
