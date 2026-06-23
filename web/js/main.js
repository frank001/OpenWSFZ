/**
 * Main page logic.
 * - Initialises the live waterfall renderer (WaterfallRenderer).
 * - Connects the WebSocket client and updates the status bar.
 *
 * @module main
 */

import { connect }                                                          from './ws.js';
import { getConfig, getFrequencies, postTune, postAudioOffset,
         getTxStatus, postTxEnable, postTxDisable, postTxAbort,
         postTxAnswerCq, getApiKey }                                         from './api.js';
import { WaterfallRenderer }                                                 from './spectrum.js';

const MAX_DECODE_ROWS = 200;

// ── Active protocol (FR-044) ──────────────────────────────────────────────
/** Protocol used to filter the frequency list for the dropdown. */
const activeProtocol = 'FT8';

// ── Cached FT8 frequency list (task 8.1) ─────────────────────────────────
/**
 * @type {Array<{protocol: string, frequencyMHz: number, description: string}>}
 */
let cachedFt8Frequencies = [];

// ── Decode pipeline state ─────────────────────────────────────────────────
/** @type {boolean} Mirrors the server-side DecodingEnabled flag. */
let decodingEnabled = true;

// ── TX panel state (tasks 6.2–6.5) ───────────────────────────────────────

/** Operator callsign read from config.tx.callsign on page load. */
let txCallsign = 'Q1OFZ';

/** Operator grid read from config.tx.grid on page load. */
let txGrid = 'JO33';

/** Current QSO controller state string (e.g. 'Idle', 'TxAnswer'). */
let currentTxState = 'Idle';

/** Current active partner callsign, or null when Idle. */
let currentTxPartner = /** @type {string|null} */ (null);

/** Whether tx.autoAnswer is enabled (mirrors the config flag). */
let currentAutoAnswerEnabled = false;

// ── TX panel DOM elements ─────────────────────────────────────────────────

const txEnableBtnEl  = /** @type {HTMLButtonElement} */ (/** @type {unknown} */ (document.getElementById('tx-enable-btn')));
const txAbortBtnEl   = /** @type {HTMLButtonElement} */ (/** @type {unknown} */ (document.getElementById('tx-abort-btn')));
const txStateDisplayEl = /** @type {HTMLElement} */ (document.getElementById('tx-state-display'));
const txMsg1El       = /** @type {HTMLElement} */ (document.getElementById('tx-msg-1'));
const txMsg2El       = /** @type {HTMLElement} */ (document.getElementById('tx-msg-2'));
const txMsg3El       = /** @type {HTMLElement} */ (document.getElementById('tx-msg-3'));

// ── TX panel render functions (tasks 6.3, 6.4) ───────────────────────────

/**
 * Compute and render the three standard FT8 message rows.
 * Row text is computed from `partner`, `txCallsign`, and `txGrid`.
 * Active row highlighting is driven by `state`.
 * Rows are greyed out when `autoAnswerEnabled` is false.
 *
 * @param {string|null}  partner
 * @param {string}       state
 * @param {boolean}      autoAnswerEnabled
 */
function renderMessageRows(partner, state, autoAnswerEnabled) {
  const p = partner ?? '———';

  const texts = [
    `${p} ${txCallsign} ${txGrid}`,   // Tx 1 — Answer (TxAnswer)
    `${p} ${txCallsign} R+00`,         // Tx 2 — Report  (TxReport)
    `${p} ${txCallsign} 73`,           // Tx 3 — 73      (Tx73)
  ];

  const activeStates = ['TxAnswer', 'TxReport', 'Tx73'];
  const rows = [txMsg1El, txMsg2El, txMsg3El];

  rows.forEach((row, i) => {
    if (!row) return;

    // Update text content
    const textSpan = row.querySelector('.tx-msg-text');
    if (textSpan) textSpan.textContent = texts[i];

    // Active row highlight
    if (state === activeStates[i]) {
      row.classList.add('tx-msg-active');
    } else {
      row.classList.remove('tx-msg-active');
    }

    // Muted when disarmed
    if (autoAnswerEnabled) {
      row.classList.remove('tx-msg-muted');
    } else {
      row.classList.add('tx-msg-muted');
    }
  });
}

/**
 * Render the full TX panel: button label/style, state display, and message rows.
 *
 * @param {string}       state              - QsoState string (e.g. 'Idle', 'TxAnswer')
 * @param {string|null}  partner            - Active partner callsign or null
 * @param {boolean}      autoAnswerEnabled  - Whether tx.autoAnswer is true
 */
function renderTxPanel(state, partner, autoAnswerEnabled) {
  // Persist for subsequent partial updates (e.g. WS txState without config change).
  currentTxState           = state;
  currentTxPartner         = partner;
  currentAutoAnswerEnabled = autoAnswerEnabled;

  // ── Enable/Disable toggle button ─────────────────────────────────────
  // D-TX-UI-002: label is always "Enable TX"; red background alone signals the armed state.
  if (txEnableBtnEl) {
    txEnableBtnEl.textContent = 'Enable TX';
    if (autoAnswerEnabled) {
      txEnableBtnEl.classList.add('tx-btn-armed');
    } else {
      txEnableBtnEl.classList.remove('tx-btn-armed');
    }
  }

  // ── State display ─────────────────────────────────────────────────────
  if (txStateDisplayEl) {
    if (!state || state === 'Idle') {
      txStateDisplayEl.textContent = 'Idle';
      txStateDisplayEl.className   = 'tx-state-idle';
    } else {
      txStateDisplayEl.textContent = partner ? `Working ${partner}` : state;
      txStateDisplayEl.className   = 'tx-state-working';
    }
  }

  // ── Message rows ─────────────────────────────────────────────────────
  renderMessageRows(partner, state, autoAnswerEnabled);
}

// ── CQ / partner interaction helpers ─────────────────────────────────────

/**
 * Convert a DecodeResult `time` field ("HH:mm:ss" UTC) to an ISO 8601 UTC string
 * suitable for use as `cqCycleStartUtc` in the answer-cq request body.
 * Approximates the date as today UTC.  Corner case near midnight UTC is acceptable.
 * @param {string} ft8Time  "HH:mm:ss" UTC cycle start from a DecodeResult.
 * @returns {string}  e.g. "2026-06-22T17:29:15Z"
 */
function parseFt8CycleStartUtc(ft8Time) {
  const now = new Date();
  const [h, m, s] = ft8Time.split(':');
  const year  = now.getUTCFullYear();
  const month = String(now.getUTCMonth() + 1).padStart(2, '0');
  const day   = String(now.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}T${h}:${m}:${s}Z`;
}

/**
 * Extract the target callsign from a CQ message.
 * CQ callsign grid     → token[1]   (3 tokens)
 * CQ modifier callsign → token[2]   (4 tokens, e.g. "CQ DX Q1TST JO22")
 * @param {string} message  Full FT8 message text.
 * @returns {string|null}
 */
function extractCqCallsign(message) {
  const tokens = message.split(' ');
  if (tokens.length === 3) return tokens[1];  // CQ callsign grid
  if (tokens.length >= 4)  return tokens[2];  // CQ modifier callsign [grid]
  return null;
}

/**
 * Returns true if `token` matches `callsign` exactly or as a portable suffix
 * (e.g. "PD2FZ/P" matches callsign "PD2FZ").
 * @param {string} token
 * @param {string} callsign
 * @returns {boolean}
 */
function tokenMatchesCallsign(token, callsign) {
  return token === callsign || token.startsWith(callsign + '/');
}

/**
 * Returns true if `message` contains both the operator's callsign and the
 * active partner's callsign as space-delimited tokens.
 * Used to highlight partner QSO exchange rows in the decode table.
 * @param {string}      message     Full FT8 message text.
 * @param {string}      txCallsign  Operator callsign (from config.tx.callsign).
 * @param {string|null} partner     Active QSO partner callsign, or null.
 * @returns {boolean}
 */
function isPartnerInteractionRow(message, txCallsign, partner) {
  if (!partner || !txCallsign) return false;
  const tokens = message.split(' ');
  return tokens.some(t => tokenMatchesCallsign(t, txCallsign))
      && tokens.some(t => tokenMatchesCallsign(t, partner));
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

    // Store cycle-start UTC string as a data attribute for the click handler.
    tr.dataset.cqCycleStartUtc = parseFt8CycleStartUtc(r.time);

    // CQ row highlighting and click-to-answer (TX-D01).
    if (r.message.startsWith('CQ ')) {
      tr.classList.add('decode-cq');
      tr.style.cursor = 'pointer';

      let inFlight = false;
      tr.addEventListener('click', async () => {
        if (inFlight) return;                          // guard already-queued duplicate events
        inFlight = true;
        tr.style.pointerEvents = 'none';               // belt-and-suspenders for mouse
        const callsign = extractCqCallsign(r.message);
        if (!callsign) {
          inFlight = false;
          tr.style.pointerEvents = '';
          return;
        }
        const cqCycleStartUtc = tr.dataset.cqCycleStartUtc;
        try {
          const status = await postTxAnswerCq(callsign, r.freqHz, cqCycleStartUtc);
          renderTxPanel(status.state, status.partner, status.autoAnswerEnabled);
          // Delay guard reset to block human double-clicks (~130–185 ms interval).
          // On success the operator does not need to retry; 400 ms is harmless (D-TX-UI-005).
          setTimeout(() => {
            inFlight = false;
            tr.style.pointerEvents = '';
          }, 400);
        } catch (err) {
          // On error, reset immediately so the operator can retry.
          inFlight = false;
          tr.style.pointerEvents = '';
          if (/** @type {any} */ (err)?.status === 409) {
            console.warn('TX not Idle — CQ click ignored.');
          } else {
            console.error('postTxAnswerCq error:', err);
          }
        }
      });
    }

    // Partner interaction highlighting — rows that contain both operator's and
    // partner's callsign are shown in subdued red during an active QSO.
    if (isPartnerInteractionRow(r.message, txCallsign, currentTxPartner)) {
      tr.classList.add('decode-partner');
    }

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
 * Window in seconds after the cycle boundary during which audio playback
 * started will still produce a decodable FT8 cycle.
 *
 * An FT8 transmission occupies 12.64 s (79 symbols × 0.16 s/symbol).
 * Within a 15 s cycle the latest usable start is 15 − 12.64 = 2.36 s.
 * Empirically, decode quality degrades noticeably beyond ~2 s, so the GO
 * window is set conservatively at 2 s to keep the indicator honest.
 */
const GO_WINDOW_S = 2;

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
 * Fetch config. If ShowCycleCountdown is true, make the timer visible and
 * start the 100 ms tick. The hidden attribute is never used — see FR-036.
 */
async function startCycleTimerIfEnabled() {
  // Remove the HTML hidden attribute unconditionally — CSS provides the default
  // visibility: hidden state.  This prevents a FOUC if the attribute is left on
  // the element at parse time.
  cycleTimerEl.removeAttribute('hidden');

  try {
    const config = await getConfig();
    if (config.showCycleCountdown) {
      cycleTimerEl.style.visibility = 'visible';
      tickCycleTimer();
      setInterval(tickCycleTimer, 100);
    }
    // If false, CSS default (visibility: hidden) applies — no explicit set needed.

    // Task 6.8: extract callsign and grid from tx config; refresh message rows.
    if (config.tx?.callsign) txCallsign = config.tx.callsign;
    if (config.tx?.grid)     txGrid     = config.tx.grid;
    renderMessageRows(currentTxPartner, currentTxState, currentAutoAnswerEnabled);
  } catch {
    // Config fetch failed — timer stays hidden; message rows keep their defaults.
  }
}

// ── Status bar elements ───────────────────────────────────────────────────

const wsStateEl        = /** @type {HTMLElement} */ (document.getElementById('ws-state'));
const audioDeviceEl    = /** @type {HTMLElement} */ (document.getElementById('audio-device'));
const audioIndicatorEl = /** @type {HTMLElement} */ (document.getElementById('audio-indicator'));
const decodeBadgeEl    = /** @type {HTMLElement} */ (document.getElementById('decode-badge'));
const decodeToggleEl   = /** @type {HTMLButtonElement} */ (/** @type {unknown} */ (document.getElementById('decode-toggle')));
const catBadgeEl       = /** @type {HTMLElement} */ (document.getElementById('cat-badge'));

function setWsState(state, label) {
  wsStateEl.className = state;
  wsStateEl.textContent = label;
}

// ── Dial frequency rendering (FR-044) ────────────────────────────────────

/**
 * Replace #dial-freq with a plain <span> showing the formatted frequency.
 * Used when CAT is disabled, in error, or not yet connected.
 * @param {number|null|undefined} freqMHz
 */
function renderDialFreqSpan(freqMHz) {
  const hz  = typeof freqMHz === 'number' ? freqMHz : 0;
  const old = document.getElementById('dial-freq');
  if (!old) return;

  // If it's already a span, just update the text.
  if (old.tagName === 'SPAN') {
    old.textContent = hz.toFixed(3) + ' MHz';
    return;
  }

  const span = document.createElement('span');
  span.id          = 'dial-freq';
  span.title       = 'Effective dial frequency (CAT live value or configured value)';
  span.textContent = hz.toFixed(3) + ' MHz';
  old.replaceWith(span);
}

/**
 * Replace #dial-freq with a <select> populated from the cached FT8 frequency
 * list. Selects the option closest to freqMHz. Attaches a change handler
 * that calls POST /api/v1/tune and updates the display on success.
 * @param {number|null|undefined} freqMHz
 */
function renderDialFreqSelect(freqMHz) {
  const hz  = typeof freqMHz === 'number' ? freqMHz : 0;
  const old = document.getElementById('dial-freq');
  if (!old) return;

  // Re-use existing select only if options are already fully populated.
  // When the cache was empty at first render (start-up race — F-004) the
  // select will have fewer options than the cache; fall through to rebuild.
  if (old.tagName === 'SELECT' &&
      cachedFt8Frequencies.length > 0 &&
      old.options.length === cachedFt8Frequencies.length) {
    updateSelectValue(/** @type {HTMLSelectElement} */ (old), hz);
    return;
  }

  const select = document.createElement('select');
  select.id    = 'dial-freq';
  select.title = 'Select working frequency (CAT will tune the rig)';

  if (cachedFt8Frequencies.length === 0) {
    const opt = document.createElement('option');
    opt.textContent = hz.toFixed(3) + ' MHz';
    opt.value       = String(hz);
    select.appendChild(opt);
  } else {
    for (const entry of cachedFt8Frequencies) {
      const opt = document.createElement('option');
      opt.value       = String(entry.frequencyMHz);
      opt.textContent = entry.frequencyMHz.toFixed(3) + ' MHz'
                        + (entry.description ? ` — ${entry.description}` : '');
      select.appendChild(opt);
    }
  }

  updateSelectValue(select, hz);

  select.addEventListener('change', async () => {
    const chosen = parseFloat(select.value);
    if (!isFinite(chosen)) return;
    try {
      const result = await postTune(chosen);
      // Update the display to the confirmed effective frequency.
      renderDialFreqSelect(result.effectiveFrequencyMHz);
    } catch (err) {
      console.error('POST /api/v1/tune failed:', err);
    }
  });

  old.replaceWith(select);
}

/**
 * Select the option whose value is closest to freqMHz.
 * @param {HTMLSelectElement} select
 * @param {number}            freqMHz
 */
function updateSelectValue(select, freqMHz) {
  let best = null;
  let bestDiff = Infinity;
  for (const opt of select.options) {
    const diff = Math.abs(parseFloat(opt.value) - freqMHz);
    if (diff < bestDiff) {
      bestDiff = diff;
      best     = opt;
    }
  }
  if (best) select.value = best.value;
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

/**
 * Dispatch dial-freq rendering based on CAT connection status (FR-044).
 * @param {string|null|undefined} catStatus
 * @param {number|null|undefined} freqMHz
 */
function updateDialFreq(catStatus, freqMHz) {
  if (catStatus === 'Connected' || catStatus === 'Connecting') {
    renderDialFreqSelect(freqMHz);
  } else {
    renderDialFreqSpan(freqMHz);
  }
}

// ── Initialise ────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {

  // Start cycle countdown timer (shows only when enabled in config).
  // Also extracts config.tx.callsign / .grid for message row rendering (task 6.8).
  startCycleTimerIfEnabled();

  // Task 6.1 — Seed the TX panel with current server state on page load.
  getTxStatus().then(status => {
    renderTxPanel(
      status.state             ?? 'Idle',
      status.partner           ?? null,
      status.autoAnswerEnabled ?? false);
  }).catch(err => {
    // Non-fatal — panel stays in default disarmed / Idle state.
    console.warn('GET /api/v1/tx/status failed on load:', err);
  });

  // Task 6.6 — Enable TX / TX Armed toggle button.
  if (txEnableBtnEl) {
    txEnableBtnEl.addEventListener('click', async () => {
      txEnableBtnEl.disabled = true;
      try {
        const status = currentAutoAnswerEnabled
          ? await postTxDisable()
          : await postTxEnable();
        renderTxPanel(
          status.state             ?? currentTxState,
          status.partner           ?? currentTxPartner,
          status.autoAnswerEnabled ?? false);
      } catch (err) {
        console.error('TX enable/disable failed:', err);
      } finally {
        txEnableBtnEl.disabled = false;
      }
    });
  }

  // Task 6.7 — Abort TX button. D-TX-UI-001: read response body and re-render
  // so the button returns to disarmed state immediately after abort.
  if (txAbortBtnEl) {
    txAbortBtnEl.addEventListener('click', async () => {
      txAbortBtnEl.disabled = true;
      try {
        const status = await postTxAbort();
        renderTxPanel(
          status.state             ?? currentTxState,
          status.partner           ?? null,
          status.autoAnswerEnabled ?? false);
      } catch (err) {
        console.error('POST /api/v1/tx/abort failed:', err);
      } finally {
        txAbortBtnEl.disabled = false;
      }
    });
  }

  // Task 8.1: fetch frequency list once on page load and cache it.
  // F-004: if the dropdown was already rendered before the fetch resolved
  // (start-up race — WebSocket status arrives before the HTTP round-trip
  // completes), force a rebuild now so all frequency options appear.
  getFrequencies().then(entries => {
    if (!Array.isArray(entries)) return;
    cachedFt8Frequencies = entries.filter(e => e.protocol === activeProtocol);

    const existing = document.getElementById('dial-freq');
    if (existing?.tagName === 'SELECT') {
      const currentVal = parseFloat(/** @type {HTMLSelectElement} */ (existing).value);
      renderDialFreqSelect(isFinite(currentVal) ? currentVal : 0);
    }
  }).catch(() => {
    // Best-effort; dropdown will fall back to single-option display.
  });

  // Live waterfall renderer — replaces the static placeholder.
  const canvas   = /** @type {HTMLCanvasElement} */ (document.getElementById('waterfall'));
  const renderer = new WaterfallRenderer(canvas);
  const observer = new ResizeObserver(() => renderer.resize());
  observer.observe(canvas.parentElement ?? canvas);

  // ── Audio offset / cursor state ───────────────────────────────────────────

  const rxFreqDisplayEl = /** @type {HTMLElement} */ (document.getElementById('rx-freq-display'));
  const txFreqDisplayEl = /** @type {HTMLElement} */ (document.getElementById('tx-freq-display'));
  const holdTxFreqEl    = /** @type {HTMLInputElement} */ (/** @type {unknown} */ (document.getElementById('hold-tx-freq')));

  /** Current RX cursor position in Hz. Mirrored locally to avoid DOM reads on every click. */
  let currentRxHz = 1500;
  /** Current TX cursor position in Hz. */
  let currentTxHz = 1500;

  /**
   * Apply an audio offset update to all local UI elements.
   * Called on WS events and after local cursor interactions.
   * @param {number}  rxHz
   * @param {number}  txHz
   * @param {boolean} holdTxFreq
   */
  function applyAudioOffset(rxHz, txHz, holdTxFreq) {
    currentRxHz = rxHz;
    currentTxHz = txHz;
    renderer.setRxHz(rxHz);
    renderer.setTxHz(txHz);
    if (rxFreqDisplayEl) rxFreqDisplayEl.textContent = rxHz + ' Hz';
    if (txFreqDisplayEl) txFreqDisplayEl.textContent = txHz + ' Hz';
    if (holdTxFreqEl)    holdTxFreqEl.checked = holdTxFreq;
  }

  /**
   * Fire-and-forget POST /api/v1/audio-offset.
   * Logs errors to console; never throws so cursor updates always succeed locally.
   * @param {number}  rxHz
   * @param {number}  txHz
   * @param {boolean} holdTxFreq
   */
  async function postAudioOffsetSilently(rxHz, txHz, holdTxFreq) {
    try {
      await postAudioOffset(rxHz, txHz, holdTxFreq);
    } catch (err) {
      console.error('POST /api/v1/audio-offset failed:', err);
    }
  }

  /**
   * Task 6.1 / D5 — Map a canvas mouse event to an audio frequency in Hz.
   * Uses offsetX (CSS pixels, DPR-independent) divided by the CSS width of the
   * canvas element, then scaled to MAX_FREQ_HZ (3000 Hz).
   * @param {MouseEvent} e
   * @returns {number}  Hz, clamped to [0, 3000].
   */
  function freqFromEvent(e) {
    const rect = canvas.getBoundingClientRect();
    const hz   = Math.round((e.offsetX / rect.width) * 3000);
    return Math.max(0, Math.min(3000, hz));
  }

  // Task 6.1 — Left-click: set RX (or both when Shift held).
  canvas.addEventListener('click', (e) => {
    const hz = freqFromEvent(e);
    if (e.shiftKey) {
      // Shift+left-click: set both RX and TX to the same frequency.
      applyAudioOffset(hz, hz, holdTxFreqEl?.checked ?? false);
      postAudioOffsetSilently(hz, hz, holdTxFreqEl?.checked ?? false);
    } else {
      // Plain left-click: set RX only; TX stays unchanged.
      applyAudioOffset(hz, currentTxHz, holdTxFreqEl?.checked ?? false);
      postAudioOffsetSilently(hz, currentTxHz, holdTxFreqEl?.checked ?? false);
    }
  });

  // Task 6.2 — Right-click: set TX; suppress browser context menu.
  canvas.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    const hz = freqFromEvent(e);
    applyAudioOffset(currentRxHz, hz, holdTxFreqEl?.checked ?? false);
    postAudioOffsetSilently(currentRxHz, hz, holdTxFreqEl?.checked ?? false);
  });

  // Task 7.3 — Hold TX Freq checkbox change handler.
  if (holdTxFreqEl) {
    holdTxFreqEl.addEventListener('change', () => {
      postAudioOffsetSilently(currentRxHz, currentTxHz, holdTxFreqEl.checked);
    });
  }

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
      const key = getApiKey();
      const response = await fetch(endpoint, {
        method:  'POST',
        headers: key ? { 'X-Api-Key': key } : {},
      });
      if (response.status === 401) {
        sessionStorage.removeItem('owsfz-api-key');
        window.location.href = '/login.html';
        return;
      }
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
      // FR-032 / FR-044: status event carries effective dial frequency and CAT status.
      updateDialFreq(event.payload.catConnectionStatus, event.payload.dialFrequencyMHz);
      setCatStatus(event.payload.catConnectionStatus);
      // Task 7.4 — initialise cursor state from the status event so newly-connected
      // tabs immediately show the correct cursor positions without waiting for a change.
      applyAudioOffset(
        event.payload.rxAudioOffsetHz ?? 1500,
        event.payload.txAudioOffsetHz ?? 1500,
        event.payload.holdTxFreq      ?? false);
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

    // FR-033 / FR-044: cat_status event updates frequency display and CAT indicator.
    if (event.type === 'cat_status' && event.payload) {
      updateDialFreq(event.payload.status, event.payload.dialFrequencyMHz);
      setCatStatus(event.payload.status);
      return;
    }

    // Task 6.4 — audioOffset event: update cursors, readouts, and checkbox.
    // Pushed by the daemon when the operator changes settings from another tab
    // or when the QSO answerer auto-updates the TX cursor (Hold TX = OFF).
    if (event.type === 'audioOffset' && event.payload) {
      applyAudioOffset(
        event.payload.rxHz,
        event.payload.txHz,
        event.payload.holdTxFreq);
      return;
    }

    // Task 6.5 — txState event: update TX panel state and message rows.
    // D-TX-UI-003: read autoAnswerEnabled from the event (now carried in the WS frame)
    // so QSO completion / abort disarms the panel without a separate HTTP call.
    if (event.type === 'txState') {
      renderTxPanel(
        event.state             ?? 'Idle',
        event.partner           ?? null,
        event.autoAnswerEnabled ?? currentAutoAnswerEnabled);
      return;
    }

    if (event.type === 'decode') {
      handleDecodes(event.payload);
    }
  });
});
