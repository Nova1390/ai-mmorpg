Renderer.init();

const worldCanvas = document.getElementById("world");
const minimap = document.getElementById("minimap");

const followBtn = document.getElementById("followBtn");
const roadsBtn = document.getElementById("roadsBtn");
const farmsBtn = document.getElementById("farmsBtn");
const villagesBtn = document.getElementById("villagesBtn");
const heatBtn = document.getElementById("heatBtn");

function refreshButtons() {
  followBtn.textContent = `Follow: ${Camera.followPlayer ? "ON" : "OFF"}`;
  roadsBtn.classList.toggle("active", Layers.overlays.roads);
  farmsBtn.classList.toggle("active", Layers.overlays.farms);
  villagesBtn.classList.toggle("active", Layers.overlays.villages);
  heatBtn.classList.toggle("active", Layers.overlays.heat);
}

followBtn.addEventListener("click", () => {
  Camera.followPlayer = !Camera.followPlayer;
  refreshButtons();
});

roadsBtn.addEventListener("click", () => {
  Layers.overlays.roads = !Layers.overlays.roads;
  refreshButtons();
});

farmsBtn.addEventListener("click", () => {
  Layers.overlays.farms = !Layers.overlays.farms;
  refreshButtons();
});

villagesBtn.addEventListener("click", () => {
  Layers.overlays.villages = !Layers.overlays.villages;
  refreshButtons();
});

heatBtn.addEventListener("click", () => {
  Layers.overlays.heat = !Layers.overlays.heat;
  refreshButtons();
});

let isDragging = false;
let dragStartX = 0;
let dragStartY = 0;
let dragCameraStartX = 0;
let dragCameraStartY = 0;
const keys = new Set();

worldCanvas.addEventListener("mousedown", (e) => {
  if (!State.data) return;
  isDragging = true;
  Camera.followPlayer = false;
  refreshButtons();

  dragStartX = e.clientX;
  dragStartY = e.clientY;
  dragCameraStartX = Camera.x;
  dragCameraStartY = Camera.y;
});

window.addEventListener("mouseup", () => {
  isDragging = false;
});

window.addEventListener("mousemove", (e) => {
  if (!isDragging || !State.data) return;

  const dxPixels = e.clientX - dragStartX;
  const dyPixels = e.clientY - dragStartY;

  Camera.x = dragCameraStartX - Math.round(dxPixels / Camera.cellSize);
  Camera.y = dragCameraStartY - Math.round(dyPixels / Camera.cellSize);

  Camera.clamp(State.data, worldCanvas);
});

worldCanvas.addEventListener("wheel", (e) => {
  if (!State.data) return;
  e.preventDefault();

  const oldCellSize = Camera.cellSize;

  if (e.deltaY < 0) {
    Camera.cellSize = Math.min(Camera.maxCellSize, Camera.cellSize + 2);
  } else {
    Camera.cellSize = Math.max(Camera.minCellSize, Camera.cellSize - 2);
  }

  if (Camera.cellSize === oldCellSize) return;

  const rect = worldCanvas.getBoundingClientRect();
  const mouseX = e.clientX - rect.left;
  const mouseY = e.clientY - rect.top;

  const worldX = Camera.x + mouseX / oldCellSize;
  const worldY = Camera.y + mouseY / oldCellSize;

  Camera.x = Math.floor(worldX - mouseX / Camera.cellSize);
  Camera.y = Math.floor(worldY - mouseY / Camera.cellSize);

  Camera.followPlayer = false;
  refreshButtons();
  Camera.clamp(State.data, worldCanvas);
}, { passive: false });

minimap.addEventListener("click", (e) => {
  if (!State.data) return;

  const rect = minimap.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;

  const sx = minimap.width / State.data.width;
  const sy = minimap.height / State.data.height;

  const targetX = Math.floor(mx / sx);
  const targetY = Math.floor(my / sy);

  Camera.centerOn(targetX, targetY, worldCanvas, State.data);
  Camera.followPlayer = false;
  refreshButtons();
});

window.addEventListener("keydown", (e) => {
  keys.add(e.key);

  if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", " "].includes(e.key)) {
    e.preventDefault();
  }

  if (e.key === "p" || e.key === "P") {
    State.spawnPlayer();
  }

  if (e.key === "f" || e.key === "F") {
    Camera.followPlayer = !Camera.followPlayer;
    refreshButtons();
  }
});

window.addEventListener("keyup", (e) => {
  keys.delete(e.key);
});

function applyKeyboardCamera() {
  if (!State.data || Camera.followPlayer) return;

  let speed = 1;
  if (keys.has("Shift")) speed = 2;

  if (keys.has("ArrowLeft") || keys.has("a") || keys.has("A")) Camera.x -= speed;
  if (keys.has("ArrowRight") || keys.has("d") || keys.has("D")) Camera.x += speed;
  if (keys.has("ArrowUp") || keys.has("w") || keys.has("W")) Camera.y -= speed;
  if (keys.has("ArrowDown") || keys.has("s") || keys.has("S")) Camera.y += speed;

  Camera.clamp(State.data, worldCanvas);
}

async function loop() {
  await State.update();

  if (State.data) {
    if (Camera.followPlayer && State.playerData) {
      Camera.centerOn(State.playerData.x, State.playerData.y, worldCanvas, State.data);
    } else {
      applyKeyboardCamera();
    }
  }

  Renderer.draw();
  requestAnimationFrame(loop);
}
document.querySelectorAll(".toggle").forEach(el => {

  el.addEventListener("click", () => {

    const layer = el.dataset.layer;

    if(layer in Layers.overlays){

      Layers.overlays[layer] = !Layers.overlays[layer];

      if(Layers.overlays[layer]){
        el.style.opacity = "1";
      }else{
        el.style.opacity = "0.35";
      }

    }

  });

});
async function start() {
  await State.init();
  refreshButtons();
  loop();
}

start();
