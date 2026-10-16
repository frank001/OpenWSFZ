/**
 * Waterfall history (#212, FR-086): the spectrum lines the renderer has
 * received, kept as raw bins so a resize can repaint them exactly instead of
 * losing them with the pixel buffer.
 *
 * DOM-free by design (same precedent as qsoTranscript.js): inputs are lines, a
 * width and a height; output is RGBA bytes. This is what lets Node's test
 * runner exercise it without a browser.
 *
 * @module waterfallHistory
 */

/**
 * Number of spectrum lines kept. One stored line is one physical pixel row, so
 * this covers a canvas up to 2,048 physical pixels tall. It is a design
 * constant that comes from the layout, not a pass bar.
 */
export const HISTORY_LINES = 2048;

const LUT_SIZE       = 256;
const RGB_STRIDE     = 3;
const RGBA_STRIDE    = 4;
const OPAQUE         = 255;
// Colour-map stop boundaries (see colormap()).
const STOP_BLUE      = 64;
const STOP_CYAN      = 128;
const STOP_YELLOW    = 192;
const MAX_INTENSITY  = 255;

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
export function colormap(v) {
  if (v < STOP_BLUE) {
    const t = v / STOP_BLUE;
    return [0, 0, Math.round(t * MAX_INTENSITY)];
  }
  if (v < STOP_CYAN) {
    const t = (v - STOP_BLUE) / STOP_BLUE;
    return [0, Math.round(t * MAX_INTENSITY), MAX_INTENSITY];
  }
  if (v < STOP_YELLOW) {
    const t = (v - STOP_CYAN) / STOP_BLUE;
    return [Math.round(t * MAX_INTENSITY), MAX_INTENSITY, Math.round((1 - t) * MAX_INTENSITY)];
  }
  const t = (v - STOP_YELLOW) / (MAX_INTENSITY - STOP_YELLOW);
  return [MAX_INTENSITY, MAX_INTENSITY, Math.round(t * MAX_INTENSITY)];
}

/**
 * Builds the 256-entry colour look-up table: entry v is bytes [3v, 3v+3) = R, G, B.
 * @returns {Uint8Array}
 */
export function createColormapLut() {
  const lut = new Uint8Array(LUT_SIZE * RGB_STRIDE);
  for (let v = 0; v < LUT_SIZE; v++) {
    const [r, g, b] = colormap(v);
    lut[v * RGB_STRIDE]     = r;
    lut[v * RGB_STRIDE + 1] = g;
    lut[v * RGB_STRIDE + 2] = b;
  }
  return lut;
}

const DEFAULT_LUT = createColormapLut();

/**
 * Paints one spectrum line into an RGBA buffer. Both the incremental
 * `render()` and the repaint go through this one function, so the two cannot
 * drift. Each line maps to x by ITS OWN length.
 *
 * @param {ArrayLike<number>} bins     Intensities in [0, 255].
 * @param {number}            width    Pixels in the row.
 * @param {Uint8ClampedArray|Uint8Array} out  RGBA destination.
 * @param {number}            rowOffset  Byte offset of the row's first pixel in `out`.
 * @param {Uint8Array}        [lut]    Colour table (defaults to the shared one).
 */
export function paintRow(bins, width, out, rowOffset, lut = DEFAULT_LUT) {
  const binCount = bins.length;
  if (binCount === 0) return;
  for (let x = 0; x < width; x++) {
    const binIdx    = Math.min(Math.floor(x * binCount / width), binCount - 1);
    const lutIdx    = bins[binIdx] * RGB_STRIDE;
    const px        = rowOffset + x * RGBA_STRIDE;
    out[px]     = lut[lutIdx];
    out[px + 1] = lut[lutIdx + 1];
    out[px + 2] = lut[lutIdx + 2];
    out[px + 3] = OPAQUE;
  }
}

/** Ring buffer of the newest `capacity` spectrum lines, each a private copy. */
export class WaterfallHistory {
  /** @param {number} [capacity=HISTORY_LINES] */
  constructor(capacity = HISTORY_LINES) {
    this._capacity = capacity;
    /** @type {(Uint8Array|undefined)[]} */
    this._lines    = new Array(capacity);
    this._next     = 0;   // slot the next push writes
    this._count    = 0;   // stored lines, <= capacity
    this._lut      = DEFAULT_LUT;
  }

  /** Number of lines currently stored. */
  get length() { return this._count; }

  /**
   * Stores a copy of `bins` as the newest line.
   * @param {ArrayLike<number>} bins
   */
  push(bins) {
    this._lines[this._next] = Uint8Array.from(bins);
    this._next = (this._next + 1) % this._capacity;
    if (this._count < this._capacity) this._count++;
  }

  /**
   * Repaints the stored lines, newest at row 0, into a fresh RGBA buffer.
   * Rows below the stored history are black and opaque (as at start-up).
   * A zero width or height returns an empty buffer and touches nothing.
   *
   * @param {number} width
   * @param {number} height
   * @returns {Uint8ClampedArray}
   */
  paint(width, height) {
    if (width <= 0 || height <= 0) return new Uint8ClampedArray(0);
    const out = new Uint8ClampedArray(width * height * RGBA_STRIDE);
    // Black, fully opaque everywhere; stored rows overwrite below.
    for (let i = RGBA_STRIDE - 1; i < out.length; i += RGBA_STRIDE) out[i] = OPAQUE;

    const rows = Math.min(height, this._count);
    for (let row = 0; row < rows; row++) {
      // Newest line is the slot before _next; older ones go backwards round the ring.
      const slot = (this._next - 1 - row + this._capacity * 2) % this._capacity;
      paintRow(this._lines[slot], width, out, row * width * RGBA_STRIDE, this._lut);
    }
    return out;
  }
}
