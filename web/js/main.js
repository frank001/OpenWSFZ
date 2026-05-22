/**
 * Main page logic.
 * - Paints the waterfall canvas placeholder.
 * - Connects the WebSocket client and updates the status bar.
 *
 * @module main
 */

import { connect }    from './ws.js';
import { getConfig }  from './api.js';

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

// ── Cycle countdown timer (FR-018) ────────────────────────────────────────

/** Duration of one FT8 cycle in seconds. */
const CYCLE_DURATION_S = 15;

/**
 * Window in seconds after the cycle boundary during which a test recording
 * started will still capture enough of the FT8 transmission to be useful.
 * Derived from the decoder's time-domain sweep range.
 */
const GO_WINDOW_S = 8;

const cycleTimerEl   = /** @type {HTMLElement} */ (document.getElementById('cycle-timer'));
const cycleDisplayEl = /** @type {HTMLElement} */ (document.getElementById('cycle-display'));

/**
 * Update the cycle display element with the current phase.
 *
 * Phases:
 *   posInCycle < GO_WINDOW_S  → "GO" (green) — good time to start a test recording
 *   posInCycle >= GO_WINDOW_S → "X.Xs" countdown to the next cycle boundary
 */
function tickCycleTimer() {
  const posInCycle = (Date.now() / 1000) % CYCLE_DURATION_S;
  if (posInCycle < GO_WINDOW_S) {
    cycleDisplayEl.textContent = 'GO';
    cycleDisplayEl.className   = 'cycle-go';
  } else {
    const remaining = CYCLE_DURATION_S - posInCycle;
    cycleDisplayEl.textContent = remaining.toFixed(1) + 's';
    cycleDisplayEl.className   = 'cycle-counting';
  }
}

/**
 * Fetch the current config.  If ShowCycleCountdown is true, unhide the timer
 * element and start a 100 ms interval tick.
 * Failures are silently swallowed — the timer stays hidden on any error.
 */
async function startCycleTimerIfEnabled() {
  try {
    const config = await getConfig();
    if (config.showCycleCountdown) {
      cycleTimerEl.removeAttribute('hidden');
      tickCycleTimer();
      setInterval(tickCycleTimer, 100);
    }
  } catch {
    // Config fetch failed — timer stays hidden (fail-safe).
  }
}

// ── Status bar elements ───────────────────────────────────────────────────

const wsStateEl        = /** @type {HTMLElement} */ (document.getElementById('ws-state'));
const audioDeviceEl    = /** @type {HTMLElement} */ (document.getElementById('audio-device'));
const audioIndicatorEl = /** @type {HTMLElement} */ (document.getElementById('audio-indicator'));

function setWsState(state, label) {
  wsStateEl.className = state;
  wsStateEl.textContent = label;
}

/**
 * Update the audio activity indicator (FR-020).
 * @param {boolean} active
 */
function setAudioActive(active) {
  audioIndicatorEl.className = active ? 'audio-active' : 'audio-inactive';
  audioIndicatorEl.title = active
    ? 'Audio active — signal above noise floor detected in the last 5 seconds'
    : 'Audio inactive — no signal above noise floor in the last 5 seconds';
}

// ── Initialise ────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {

  // Start cycle countdown timer (shows only when enabled in config).
  startCycleTimerIfEnabled();

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
        setAudioActive(false);
      }
      return;
    }

    if (event.type === 'status' && event.payload) {
      const { audioDevice, audioActive } = event.payload;
      audioDeviceEl.textContent = audioDevice ?? '(no device)';
      setAudioActive(audioActive ?? false);
      return;
    }

    if (event.type === 'heartbeat' && event.payload) {
      // Update audio activity indicator from the heartbeat window (FR-020).
      setAudioActive(event.payload.audioActive ?? false);
      return;
    }

    if (event.type === 'decode') {
      handleDecodes(event.payload);
    }
  });
});
