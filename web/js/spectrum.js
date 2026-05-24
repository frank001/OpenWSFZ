/**
 * Live scrolling waterfall renderer for the spectrum display.
 *
 * Data flow: WebSocket "spectrum" event → WaterfallRenderer.render(bins)
 *
 * Canvas layout:
 *   - X axis: frequency, left (0 Hz) to right (~3000 Hz)
 *   - Y axis: time, top (most recent) to bottom (oldest)
 *   - Pixel intensity: signal strength (0 = noise floor, 255 = peak)
 *
 * @module spectrum
 */

const MAX_FREQ_HZ = 3000;
const TICK_FREQS  = [500, 1000, 1500, 2000, 2500, 3000];

/**
 * Maps an intensity value [0, 255] to an RGB triple using a 4-stop gradient:
 *   0   → black   [0,   0,   0  ]
 *   64  → blue    [0,   0,   255]
 *   128 → cyan    [0,   255, 255]
 *   192 → yellow  [255, 255, 0  ]
 *   255 → white   [255, 255, 255]
 *
 * @param {number} v  Integer in [0, 255]
 * @returns {[number, number, number]}  [R, G, B] each in [0, 255]
 */
function colormap(v) {
  if (v < 64) {
    const t = v / 64;
    return [0, 0, Math.round(t * 255)];
  }
  if (v < 128) {
    const t = (v - 64) / 64;
    return [0, Math.round(t * 255), 255];
  }
  if (v < 192) {
    const t = (v - 128) / 64;
    return [Math.round(t * 255), 255, Math.round((1 - t) * 255)];
  }
  const t = (v - 192) / 63;
  return [255, 255, Math.round(t * 255)];
}

/**
 * Scrolling waterfall renderer backed by a raw ImageData pixel buffer.
 *
 * Designed to be instantiated once and reused across resize events.
 * Call `resize()` whenever the canvas dimensions change.
 */
export class WaterfallRenderer {
  /** @param {HTMLCanvasElement} canvas */
  constructor(canvas) {
    this._canvas    = canvas;
    this._ctx       = canvas.getContext('2d');
    this._imageData = null;
    this._resize();
  }

  /**
   * Rebuild the internal pixel buffer to match the current canvas size.
   * Must be called after any change to canvas CSS dimensions.
   */
  resize() {
    this._resize();
  }

  /**
   * Render one spectrum line at the top of the waterfall.
   * Previous content scrolls down by one physical pixel.
   *
   * @param {number[]} bins  Array of OutputBinCount integers, each in [0, 255].
   */
  render(bins) {
    if (!this._imageData) return;

    const w    = this._canvas.width;
    const h    = this._canvas.height;
    const data = this._imageData.data;

    // Scroll existing content down by one pixel.
    // copyWithin(target, start) copies [start .. data.length) to [target .. ).
    // Source and destination overlap; the spec guarantees correct memmove semantics.
    const rowBytes = w * 4;
    data.copyWithin(rowBytes, 0);

    // Write the new spectrum line into row 0.
    const binCount = bins.length;
    for (let x = 0; x < w; x++) {
      const binIdx    = Math.min(Math.floor(x * binCount / w), binCount - 1);
      const intensity = bins[binIdx];
      const [r, g, b] = colormap(intensity);
      const px        = x * 4;
      data[px]     = r;
      data[px + 1] = g;
      data[px + 2] = b;
      // Alpha channel (data[px + 3]) is pre-set to 255 in _resize().
    }

    this._ctx.putImageData(this._imageData, 0, 0);
    this._drawFrequencyAxis();
  }

  // ── Private ──────────────────────────────────────────────────────────────

  _resize() {
    const { width, height } = this._canvas.getBoundingClientRect();
    const dpr = devicePixelRatio;
    const w   = Math.max(1, Math.round(width  * dpr));
    const h   = Math.max(1, Math.round(height * dpr));

    this._canvas.width  = w;
    this._canvas.height = h;

    this._imageData = this._ctx.createImageData(w, h);

    // Fill entirely black (RGB = 0) with full opacity (A = 255).
    const data = this._imageData.data;
    for (let i = 3; i < data.length; i += 4)
      data[i] = 255;
  }

  _drawFrequencyAxis() {
    const ctx = this._ctx;
    const w   = this._canvas.width;
    const h   = this._canvas.height;
    const dpr = devicePixelRatio;

    ctx.save();
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.35)';
    ctx.fillStyle   = 'rgba(255, 255, 255, 0.55)';
    ctx.font        = `${Math.round(9 * dpr)}px ui-monospace, monospace`;
    ctx.textAlign   = 'center';
    ctx.lineWidth   = 1;

    const labelY  = h - 4 * dpr;
    const tickTop = h - 14 * dpr;

    for (const freq of TICK_FREQS) {
      const x = Math.round(freq / MAX_FREQ_HZ * w);

      // Vertical tick.
      ctx.beginPath();
      ctx.moveTo(x + 0.5, tickTop);
      ctx.lineTo(x + 0.5, h);
      ctx.stroke();

      // Frequency label: "1k", "1.5k", "2k", etc.
      const label = freq % 1000 === 0
        ? `${freq / 1000}k`
        : `${freq / 1000}`;
      ctx.fillText(label, x, labelY);
    }

    ctx.restore();
  }
}
