/**
 * Main page logic.
 * - Initialises the live waterfall renderer (WaterfallRenderer).
 * - Connects the WebSocket client and updates the status bar.
 *
 * @module main
 */

import { connect }           from './ws.js';
import { getConfig }         from './api.js';
import { WaterfallRenderer } from './spectrum.js';

const MAX_DECODE_ROWS = 200;

// ── Decode pipeline state ─────────────────────────────────────────────────
/** @type {boolean} Mirrors the server-side DecodingEnabled flag. */
let decodingEnabled = true;

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
const decodeBadgeEl    = /** @type {HTMLElement} */ (document.getElementById('decode-badge'));
const decodeToggleEl   = /** @type {HTMLButtonElement} */ (/** @type {unknown} */ (document.getElementById('decode-toggle')));
const dialFreqEl       = /** @type {HTMLElement} */ (document.getElementById('dial-freq'));
const catBadgeEl       = /** @type {HTMLElement} */ (document.getElementById('cat-badge'));

function setWsState(state, label) {
  wsStateEl.className = state;
  wsStateEl.textContent = label;
}

/**
 * Update the dial frequency display (FR-032).
 * @param {number|null|undefined} freqMHz
 */
function setDialFrequency(freqMHz) {
  const hz = typeof freqMHz === 'number' ? freqMHz : 0;
  dialFreqEl.textContent = hz.toFixed(3) + ' MHz';
}

/**
 * Update the CAT connection badge (FR-033).
 * Status is 'Connected', 'Connecting', 'Error', 'Disabled', or absent.
 * @param {string|null|undefined} status
 */
function setCatStatus(status) {
  if (!status || status === 'Disabled') {
    catBadgeEl.hidden     = true;
    catBadgeEl.textContent = '';
    catBadgeEl.className   = '';
    return;
  }
  catBadgeEl.hidden     = false;
  catBadgeEl.textContent = status;
  catBadgeEl.className   = 'cat-badge cat-' + status.toLowerCase();
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

/**
 * Update the decode badge and toggle button to reflect the current pipeline state (FR-017).
 * @param {boolean} enabled  - Whether decoding is active.
 * @param {boolean} hasDevice - Whether an audio device is configured.
 */
function setDecodingState(enabled, hasDevice) {
  decodingEnabled = enabled;

  if (!hasDevice) {
    decodeBadgeEl.textContent = 'Stopped';
    decodeBadgeEl.className   = 'decoding-stopped';
    decodeToggleEl.textContent = 'No device';
    decodeToggleEl.disabled    = true;
    return;
  }

  if (enabled) {
    decodeBadgeEl.textContent  = 'Decoding';
    decodeBadgeEl.className    = 'decoding-active';
    decodeToggleEl.textContent = 'Stop Decoding';
    decodeToggleEl.disabled    = false;
  } else {
    decodeBadgeEl.textContent  = 'Stopped';
    decodeBadgeEl.className    = 'decoding-stopped';
    decodeToggleEl.textContent = 'Start Decoding';
    decodeToggleEl.disabled    = false;
  }
}

// ── Initialise ────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {

  // Start cycle countdown timer (shows only when enabled in config).
  startCycleTimerIfEnabled();

  // Live waterfall renderer — replaces the static placeholder.
  const canvas   = /** @type {HTMLCanvasElement} */ (document.getElementById('waterfall'));
  const renderer = new WaterfallRenderer(canvas);
  const observer = new ResizeObserver(() => renderer.resize());
  observer.observe(canvas.parentElement ?? canvas);

  // W2: requestAnimationFrame throttle state for spectrum rendering.
  // Coalesces rapid onmessage deliveries into at most one putImageData call per
  // browser frame, preventing the JS main thread from being starved by putImageData.
  let pendingSpectrumBins = null;
  let spectrumRafPending  = false;

  // Decode toggle button — calls /api/v1/decode/start or /decode/stop (FR-017).
  decodeToggleEl.addEventListener('click', async () => {
    const endpoint = decodingEnabled ? '/api/v1/decode/stop' : '/api/v1/decode/start';
    decodeToggleEl.disabled = true;
    try {
      const response = await fetch(endpoint, { method: 'POST' });
      if (response.ok) {
        const data = await response.json();
        setDecodingState(data.decodingEnabled ?? decodingEnabled, !!data.audioDevice);
      } else {
        // Re-enable button on error so the operator can retry.
        decodeToggleEl.disabled = false;
        console.error(`${endpoint} returned HTTP ${response.status}`);
      }
    } catch (err) {
      decodeToggleEl.disabled = false;
      console.error(`${endpoint} network error:`, err);
    }
  });

  // Connect WebSocket and update status bar.
  connect((event) => {
    if (event.type === '__state') {
      if (event.payload === 'connected') {
        setWsState('connected', 'Connected');
      } else {
        setWsState('disconnected', 'Disconnected');
        audioDeviceEl.textContent = '(no device)';
        setAudioActive(false);
        setCatStatus(null);
      }
      return;
    }

    if (event.type === 'status' && event.payload) {
      const { audioDevice, audioActive } = event.payload;
      audioDeviceEl.textContent = audioDevice ?? '(no device)';
      setAudioActive(audioActive ?? false);
      setDecodingState(event.payload.decodingEnabled ?? true, !!audioDevice);
      // FR-032: status event carries effective dial frequency.
      setDialFrequency(event.payload.dialFrequencyMHz);
      return;
    }

    if (event.type === 'heartbeat' && event.payload) {
      // Update audio activity indicator from the heartbeat window (FR-020).
      setAudioActive(event.payload.audioActive ?? false);
      return;
    }

    if (event.type === 'spectrum' && Array.isArray(event.payload)) {
      // W2: store latest bins; schedule a single render on the next animation frame.
      // If another frame is already pending, just update the pending data — the already-
      // scheduled rAF callback will pick up the latest value when it fires.
      pendingSpectrumBins = event.payload;
      if (!spectrumRafPending) {
        spectrumRafPending = true;
        requestAnimationFrame(() => {
          spectrumRafPending = false;
          if (pendingSpectrumBins !== null) {
            renderer.render(pendingSpectrumBins);
            pendingSpectrumBins = null;
          }
        });
      }
      return;
    }

    // FR-033: cat_status event updates frequency and CAT indicator (task 13.3).
    if (event.type === 'cat_status' && event.payload) {
      setDialFrequency(event.payload.dialFrequencyMHz);
      setCatStatus(event.payload.status);
      return;
    }

    if (event.type === 'decode') {
      handleDecodes(event.payload);
    }
  });
});
