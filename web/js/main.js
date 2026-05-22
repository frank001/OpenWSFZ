/**
 * Main page logic.
 * - Paints the waterfall canvas placeholder.
 * - Connects the WebSocket client and updates the status bar.
 *
 * @module main
 */

import { connect } from './ws.js';

const BG_COLOUR          = '#0d1117';
const PLACEHOLDER_COLOUR = '#8b949e';
const PLACEHOLDER_TEXT   = 'Waterfall — awaiting audio input';
const MAX_DECODE_ROWS    = 200;

/**
 * Paint a static dark-background placeholder on the waterfall canvas.
 * Phase 5 (FT8 decoder) will replace this with real spectrogram rendering.
 * @param {HTMLCanvasElement} canvas
 */
function paintWaterfallPlaceholder(canvas) {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  // Match the canvas bitmap size to its CSS-rendered size.
  const { width, height } = canvas.getBoundingClientRect();
  canvas.width  = Math.round(width  * devicePixelRatio);
  canvas.height = Math.round(height * devicePixelRatio);
  ctx.scale(devicePixelRatio, devicePixelRatio);

  // Fill background.
  ctx.fillStyle = BG_COLOUR;
  ctx.fillRect(0, 0, width, height);

  // Centred placeholder text.
  ctx.fillStyle    = PLACEHOLDER_COLOUR;
  ctx.font         = '14px system-ui, sans-serif';
  ctx.textAlign    = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(PLACEHOLDER_TEXT, width / 2, height / 2);
}

// ── Decoded-messages table ────────────────────────────────────────────────

const decodesBody = /** @type {HTMLTableSectionElement} */ (document.getElementById('decodes-body'));

/**
 * Create a table cell with safely-escaped text content.
 * Using textContent prevents XSS from FT8 Type 5 (free-text) messages that
 * may contain HTML-significant characters such as <, >, &, and ".
 *
 * @param {string} text
 * @returns {HTMLTableCellElement}
 */
function makeCell(text) {
  const td = document.createElement('td');
  td.textContent = text;
  return td;
}

/**
 * Handle a `decode` WebSocket event.
 * Prepends one row per result, removes the placeholder row on first decode,
 * and caps the table at MAX_DECODE_ROWS.
 *
 * @param {Array<{time:string, snr:number, dt:number, freqHz:number, message:string}>} results
 */
function handleDecodes(results) {
  if (!results || results.length === 0) return;

  // Remove placeholder row on first real decode.
  const placeholder = decodesBody.querySelector('tr .td-no-data, tr td.td-no-data');
  if (placeholder) placeholder.closest('tr')?.remove();

  // Prepend newest rows (results are newest first if multiple in one cycle).
  for (const r of results) {
    const dtStr  = (r.dt >= 0 ? '+' : '') + r.dt.toFixed(1);
    const snrStr = r.snr >= 0 ? `+${r.snr}` : `${r.snr}`;

    // Use textContent for each cell — FT8 Type 5 (free-text) messages may contain
    // characters that are valid HTML (<, >, &, ") and must not be parsed as markup.
    const tr = document.createElement('tr');
    tr.appendChild(makeCell(r.time));
    tr.appendChild(makeCell(snrStr));
    tr.appendChild(makeCell(dtStr));
    tr.appendChild(makeCell(String(r.freqHz)));
    tr.appendChild(makeCell(r.message));
    decodesBody.prepend(tr);
  }

  // Cap at MAX_DECODE_ROWS — remove excess from the bottom.
  const rows = decodesBody.querySelectorAll('tr');
  for (let i = MAX_DECODE_ROWS; i < rows.length; i++) {
    rows[i].remove();
  }
}

// ── Status bar elements ───────────────────────────────────────────────────

const wsStateEl      = /** @type {HTMLElement} */ (document.getElementById('ws-state'));
const audioDeviceEl  = /** @type {HTMLElement} */ (document.getElementById('audio-device'));

function setWsState(state, label) {
  wsStateEl.className = state;
  wsStateEl.textContent = label;
}

// ── Initialise ────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {

  // Paint waterfall placeholder.
  const canvas = /** @type {HTMLCanvasElement} */ (document.getElementById('waterfall'));
  paintWaterfallPlaceholder(canvas);

  // Re-paint on window resize so it always fills the panel.
  const observer = new ResizeObserver(() => paintWaterfallPlaceholder(canvas));
  observer.observe(canvas.parentElement ?? canvas);

  // Connect WebSocket and update status bar.
  connect((event) => {
    if (event.type === '__state') {
      if (event.payload === 'connected') {
        setWsState('connected', 'Connected');
      } else {
        setWsState('disconnected', 'Disconnected');
        audioDeviceEl.textContent = '(no device)';
      }
      return;
    }

    if (event.type === 'status' && event.payload) {
      const { audioDevice } = event.payload;
      audioDeviceEl.textContent = audioDevice ?? '(no device)';
      return;
    }

    if (event.type === 'decode') {
      handleDecodes(event.payload);
    }
  });
});
