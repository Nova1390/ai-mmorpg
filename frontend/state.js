const State = {
  staticData: null,
  dynamicData: null,
  debugMetrics: null,
  debugHistory: [],
  playerData: null,
  playerId: null,
  _staticPromise: null,

  get data() {
    if (!this.dynamicData || !this.staticData) return null;
    // /state/static is the single source for immutable map fields.
    return {
      ...this.dynamicData,
      width: this.staticData.width,
      height: this.staticData.height,
      tiles: this.staticData.tiles
    };
  },

  get dynamic() {
    return this.dynamicData;
  },

  get metrics() {
    return this.debugMetrics;
  },

  get history() {
    return this.debugHistory;
  },

  get static() {
    return this.staticData;
  },

  async init() {
    await this.loadStatic();
  },

  async loadStatic() {
    if (this.staticData) return this.staticData;
    if (this._staticPromise) return this._staticPromise;

    this._staticPromise = (async () => {
      try {
        const r = await fetch("/state/static", { cache: "no-store" });
        if (!r.ok) return null;
        const payload = await r.json();
        this.staticData = payload;
        return payload;
      } finally {
        this._staticPromise = null;
      }
    })();

    return this._staticPromise;
  },

  async update() {
    if (!this.staticData) {
      await this.loadStatic();
    }

    const r = await fetch("/state", { cache: "no-store" });
    this.dynamicData = await r.json();

    try {
      const mr = await fetch("/debug/metrics", { cache: "no-store" });
      if (mr.ok) {
        this.debugMetrics = await mr.json();
      }
      const hr = await fetch("/debug/history?limit=80", { cache: "no-store" });
      if (hr.ok) {
        const payload = await hr.json();
        this.debugHistory = Array.isArray(payload.history) ? payload.history : [];
      }
    } catch (_) {
      // Debug metrics are optional and must not break rendering.
    }

    if (this.playerId) {
      const pr = await fetch(`/player/${this.playerId}`, { cache: "no-store" });
      if (pr.status === 200) {
        this.playerData = await pr.json();
      } else {
        this.playerData = null;
      }
    } else {
      this.playerData = null;
    }
  },

  async spawnPlayer() {
    const r = await fetch("/spawn_player", { method: "POST" });
    const data = await r.json();
    this.playerId = data.player_id || null;
  }
};
