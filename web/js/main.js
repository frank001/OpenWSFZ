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
    }
  });
});
