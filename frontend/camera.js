const Camera = {
  x: 0,
  y: 0,
  cellSize: 18,
  minCellSize: 6,
  maxCellSize: 40,

  getViewWidth(canvas) {
    return Math.max(1, Math.floor(canvas.width / this.cellSize));
  },

  getViewHeight(canvas) {
    return Math.max(1, Math.floor(canvas.height / this.cellSize));
  },

  clamp(data, canvas) {
    if (!data) return;
    const vw = this.getViewWidth(canvas);
    const vh = this.getViewHeight(canvas);
    this.x = Math.max(0, Math.min(this.x, Math.max(0, (data.width || 0) - vw)));
    this.y = Math.max(0, Math.min(this.y, Math.max(0, (data.height || 0) - vh)));
  },

  centerOn(wx, wy, canvas, data) {
    const vw = this.getViewWidth(canvas);
    const vh = this.getViewHeight(canvas);
    this.x = Math.floor(wx - vw / 2);
    this.y = Math.floor(wy - vh / 2);
    this.clamp(data, canvas);
  },

  zoomBy(delta, focusPxX, focusPxY, canvas, data) {
    const oldSize = this.cellSize;
    const next = Math.max(this.minCellSize, Math.min(this.maxCellSize, this.cellSize + delta));
    if (next === oldSize) return;

    const worldX = this.x + (focusPxX / oldSize);
    const worldY = this.y + (focusPxY / oldSize);

    this.cellSize = next;
    this.x = Math.floor(worldX - (focusPxX / next));
    this.y = Math.floor(worldY - (focusPxY / next));
    this.clamp(data, canvas);
  },
};
