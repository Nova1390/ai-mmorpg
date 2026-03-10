(function main() {
  Renderer.init();

  const canvas = document.getElementById("world");
  const mapWrap = document.querySelector(".map-wrap");
  const apiBaseInput = document.getElementById("apiBaseInput");
  const applyApiBtn = document.getElementById("applyApiBtn");
  const refreshBtn = document.getElementById("refreshBtn");
  const reloadStaticBtn = document.getElementById("reloadStaticBtn");
  const pollMsSelect = document.getElementById("pollMsSelect");
  const zoomInBtn = document.getElementById("zoomInBtn");
  const zoomOutBtn = document.getElementById("zoomOutBtn");
  const followBtn = document.getElementById("followBtn");
  const minimap = document.getElementById("minimap");
  const agentFilterInput = document.getElementById("agentFilterInput");
  const agentCapSelect = document.getElementById("agentCapSelect");

  let isDragging = false;
  let dragStartClientX = 0;
  let dragStartClientY = 0;
  let dragStartCameraX = 0;
  let dragStartCameraY = 0;

  const keys = new Set();
  let followPlayer = false;

  function refreshFollowButton() {
    followBtn.textContent = `Follow Player: ${followPlayer ? "ON" : "OFF"}`;
  }

  function resizeCanvasToContainer() {
    const w = Math.max(320, Math.floor(mapWrap.clientWidth));
    const h = Math.max(320, Math.floor(mapWrap.clientHeight));
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    if (State.data) Camera.clamp(State.data, canvas);
  }

  function applyApiAndRestart() {
    State.setApiBase(apiBaseInput.value || "");
    State.staticData = null;
    State.dynamicData = null;
    State.indexes = null;
    State.status.staticOk = false;
    State.status.dynamicOk = false;
    State.status.staticError = "";
    State.status.dynamicError = "";
    State.stopPolling();

    bootstrap().catch((err) => {
      console.error(err);
    });
  }

  async function bootstrap() {
    resizeCanvasToContainer();

    try {
      await State.loadStatic(false);
    } catch (_) {
      // Keep UI up even if static fetch fails.
    }

    try {
      await State.fetchDynamic();
    } catch (_) {
      // Keep UI up even if first dynamic fetch fails.
    }

    State.startPolling(Number(pollMsSelect.value || 300));

    const data = State.data;
    if (data && Number.isFinite(Number(data.width)) && Number.isFinite(Number(data.height))) {
      Camera.centerOn(Math.floor(data.width / 2), Math.floor(data.height / 2), canvas, data);
    }
  }

  function animate() {
    const data = State.data;

    if (data) {
      if (followPlayer) {
        const player = (data.agents || []).find((a) => a && a.is_player);
        if (player && Number.isFinite(player.x) && Number.isFinite(player.y)) {
          Camera.centerOn(player.x, player.y, canvas, data);
        }
      } else {
        const speed = keys.has("Shift") ? 2 : 1;
        if (keys.has("ArrowLeft") || keys.has("a") || keys.has("A")) Camera.x -= speed;
        if (keys.has("ArrowRight") || keys.has("d") || keys.has("D")) Camera.x += speed;
        if (keys.has("ArrowUp") || keys.has("w") || keys.has("W")) Camera.y -= speed;
        if (keys.has("ArrowDown") || keys.has("s") || keys.has("S")) Camera.y += speed;
      }
      Camera.clamp(data, canvas);
    }

    Renderer.draw();
    requestAnimationFrame(animate);
  }

  Renderer.onSelectVillage = (uid) => {
    const data = State.data;
    if (!data) return;
    const village = (State.indexes && State.indexes.villagesByUid.get(uid)) || null;
    if (village && village.center) {
      Camera.centerOn(village.center.x, village.center.y, canvas, data);
    }
  };

  canvas.addEventListener("mousedown", (event) => {
    if (!State.data) return;
    followPlayer = false;
    refreshFollowButton();
    isDragging = true;
    dragStartClientX = event.clientX;
    dragStartClientY = event.clientY;
    dragStartCameraX = Camera.x;
    dragStartCameraY = Camera.y;
  });

  window.addEventListener("mouseup", () => {
    isDragging = false;
  });

  window.addEventListener("mousemove", (event) => {
    const data = State.data;
    if (data) {
      const tile = Renderer.worldToTile(event.clientX, event.clientY);
      if (Renderer.isTileInside(tile, data)) {
        Renderer.setHoverTile(tile);
      } else {
        Renderer.setHoverTile(null);
      }
    }

    if (!isDragging || !data) return;
    const dxPixels = event.clientX - dragStartClientX;
    const dyPixels = event.clientY - dragStartClientY;
    Camera.x = dragStartCameraX - Math.round(dxPixels / Camera.cellSize);
    Camera.y = dragStartCameraY - Math.round(dyPixels / Camera.cellSize);
    Camera.clamp(data, canvas);
  });

  canvas.addEventListener("mouseleave", () => {
    Renderer.setHoverTile(null);
  });

  canvas.addEventListener("click", (event) => {
    const data = State.data;
    if (!data) return;
    followPlayer = false;
    refreshFollowButton();
    const tile = Renderer.worldToTile(event.clientX, event.clientY);
    if (!Renderer.isTileInside(tile, data)) return;
    Renderer.setSelectedTile(tile);
    Renderer.selectVillageByTile(tile, data);
  });

  canvas.addEventListener("wheel", (event) => {
    const data = State.data;
    if (!data) return;
    event.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;
    Camera.zoomBy(event.deltaY < 0 ? 2 : -2, px, py, canvas, data);
  }, { passive: false });

  zoomInBtn.addEventListener("click", () => {
    const data = State.data;
    if (!data) return;
    Camera.zoomBy(2, canvas.width / 2, canvas.height / 2, canvas, data);
  });

  zoomOutBtn.addEventListener("click", () => {
    const data = State.data;
    if (!data) return;
    Camera.zoomBy(-2, canvas.width / 2, canvas.height / 2, canvas, data);
  });

  window.addEventListener("keydown", (event) => {
    keys.add(event.key);
    if (event.key === "f" || event.key === "F") {
      followPlayer = !followPlayer;
      refreshFollowButton();
    }
    if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", " "].includes(event.key)) {
      event.preventDefault();
    }
  });

  window.addEventListener("keyup", (event) => {
    keys.delete(event.key);
  });

  applyApiBtn.addEventListener("click", () => {
    applyApiAndRestart();
  });

  followBtn.addEventListener("click", () => {
    followPlayer = !followPlayer;
    refreshFollowButton();
  });

  refreshBtn.addEventListener("click", async () => {
    try {
      await State.fetchDynamic();
    } catch (_) {
      // Status panel shows error.
    }
  });

  reloadStaticBtn.addEventListener("click", async () => {
    try {
      await State.loadStatic(true);
      await State.fetchDynamic();
      if (State.data) Camera.clamp(State.data, canvas);
    } catch (_) {
      // Status panel shows error.
    }
  });

  pollMsSelect.addEventListener("change", () => {
    State.startPolling(Number(pollMsSelect.value || 300));
  });

  minimap.addEventListener("click", (event) => {
    const data = State.data;
    if (!data) return;
    const rect = minimap.getBoundingClientRect();
    const mx = (event.clientX - rect.left) * (minimap.width / Math.max(rect.width, 1));
    const my = (event.clientY - rect.top) * (minimap.height / Math.max(rect.height, 1));
    const scaleX = minimap.width / Math.max(1, Number(data.width) || 1);
    const scaleY = minimap.height / Math.max(1, Number(data.height) || 1);
    const wx = Math.floor(mx / Math.max(scaleX, 0.0001));
    const wy = Math.floor(my / Math.max(scaleY, 0.0001));
    Camera.centerOn(wx, wy, canvas, data);
    followPlayer = false;
    refreshFollowButton();
  });

  agentFilterInput.addEventListener("input", () => {
    Renderer._lastDataKey = "";
  });

  agentCapSelect.addEventListener("change", () => {
    Renderer._lastDataKey = "";
  });

  window.addEventListener("resize", resizeCanvasToContainer);

  apiBaseInput.value = State.initApiBase();
  refreshFollowButton();
  bootstrap().catch((err) => {
    console.error(err);
  });
  animate();
})();
