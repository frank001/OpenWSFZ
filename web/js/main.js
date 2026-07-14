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
         postTxSelectResponder, postTxCallCq, postTxStopCq,
         postTxCallerPartnerSelect, getApiKey,
         getPropModes, postLogQso,
         postTxEngageDecode,
         getDecodeFilter, postDecodeFilter }                                 from './api.js';
import { WaterfallRenderer }                                                 from './spectrum.js';
import { isDecodeVisible, UNFILTERED_DECODE_FILTER }                         from './decodeFilter.js';

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

// ── TX panel state (tasks 6.2–6.5, 7.1, 7.6) ────────────────────────────

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

/**
 * Whether the active QSO controller is currently inside its TransmitAsync/KeyDownAsync
 * bracket (dev-task 2026-07-10-tx-btn-live-verify-and-settings-tab-wrap.md item A).
 * Mirrors the daemon's IQsoController.Keying signal. Together with
 * currentAutoAnswerEnabled this drives #tx-enable-btn's bright-red/dark-red colour —
 * see renderTxPanel. Defaults false ("armed but idle") until the first txState/tx-status
 * response carries a real value.
 */
let currentKeying = false;

/**
 * Current QSO controller role ('answerer' or 'caller').
 * Updated from txState WS events and the initial getTxStatus() response.
 * Controls TX panel message templates and decode-row highlighting.
 * @type {'answerer'|'caller'}
 */
let currentTxRole = 'answerer';

/**
 * Caller partner-select mode ('First' or 'None').
 * Populated from config.tx.callerPartnerSelect on page load.
 * When 'None', responder rows in the decode table get the decode-responder class
 * and a click handler that calls POST /api/v1/tx/select-responder.
 * @type {'First'|'None'}
 */
let currentCallerPartnerSelect = 'First';

// ── TX panel DOM elements ─────────────────────────────────────────────────

const txEnableBtnEl  = /** @type {HTMLButtonElement} */ (/** @type {unknown} */ (document.getElementById('tx-enable-btn')));
const txCallCqBtnEl  = /** @type {HTMLButtonElement} */ (/** @type {unknown} */ (document.getElementById('tx-call-cq-btn')));
const txAbortBtnEl   = /** @type {HTMLButtonElement} */ (/** @type {unknown} */ (document.getElementById('tx-abort-btn')));
const txStateDisplayEl = /** @type {HTMLElement} */ (document.getElementById('tx-state-display'));
const txMsg1El       = /** @type {HTMLElement} */ (document.getElementById('tx-msg-1'));
const txMsg2El       = /** @type {HTMLElement} */ (document.getElementById('tx-msg-2'));
const txMsg3El       = /** @type {HTMLElement} */ (document.getElementById('tx-msg-3'));

// TX abort reason history (FR-UX-002)
const txAbortLogSection = /** @type {HTMLElement} */ (document.getElementById('tx-abort-log-section'));
const txAbortLogEl      = /** @type {HTMLOListElement} */ (document.getElementById('tx-abort-log'));

// Pileup-mode toggle (FR-PILEUP-001)
const pileupModeRowEl    = /** @type {HTMLElement} */ (document.getElementById('pileup-mode-row'));
const pileupAutoSelectEl = /** @type {HTMLInputElement} */ (/** @type {unknown} */ (document.getElementById('pileup-auto-select')));

/** @type {Array<{isoTs: string, reason: string, partner: string|null}>} */
const txAbortLog = [];
const TX_ABORT_LOG_MAX = 10;

/**
 * Appends an entry to the TX abort log (newest on top) and refreshes the DOM list.
 * Capped at TX_ABORT_LOG_MAX entries; oldest entries are dropped.
 * @param {string}      reason   - Human-readable abort reason.
 * @param {string|null} partner  - Partner callsign at time of abort, or null.
 */
function appendTxAbortLog(reason, partner) {
  const isoTs = new Date().toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
  txAbortLog.unshift({ isoTs, reason, partner });
  if (txAbortLog.length > TX_ABORT_LOG_MAX)
    txAbortLog.length = TX_ABORT_LOG_MAX;

  if (txAbortLogEl) {
    txAbortLogEl.innerHTML = txAbortLog
      .map(e => `<li><span class="tx-abort-ts">${e.isoTs}</span> — ${e.reason}</li>`)
      .join('');
  }
  if (txAbortLogSection) txAbortLogSection.hidden = false;
}

// ── TX panel render functions (tasks 6.3, 6.4) ───────────────────────────

/**
 * Compute and render the three standard FT8 message rows.
 * Row text is computed from `partner`, `txCallsign`, and `txGrid`.
 * Active row highlighting is driven by `state` and `role`.
 * Rows are greyed out when `autoAnswerEnabled` is false.
 *
 * Answerer templates (role === 'answerer'):
 *   Row 1 — TxAnswer:  {partner} {callsign} {grid}
 *   Row 2 — TxReport:  {partner} {callsign} R+00
 *   Row 3 — Tx73:      {partner} {callsign} 73
 *
 * Caller templates (role === 'caller'):
 *   Row 1 — TxCq (mapped to TxAnswer proxy): CQ {callsign} {grid}
 *   Row 2 — TxReport:                        {partner} {callsign} +00
 *   Row 3 — TxRr73 (mapped to Tx73 proxy):   {partner} {callsign} RR73
 *
 * @param {string|null}      partner
 * @param {string}           state
 * @param {boolean}          autoAnswerEnabled
 * @param {'answerer'|'caller'} [role]
 */
function renderMessageRows(partner, state, autoAnswerEnabled, role) {
  const effectiveRole = role ?? currentTxRole;
  const p = partner ?? '———';

  /** @type {string[]} */
  let texts;
  /** @type {string[]} */
  let activeStates;

  if (effectiveRole === 'caller') {
    texts = [
      `CQ ${txCallsign} ${txGrid}`,    // Tx 1 — CQ      (TxCq)
      `${p} ${txCallsign} +00`,         // Tx 2 — Report  (TxReport)
      `${p} ${txCallsign} RR73`,        // Tx 3 — RR73    (TxRr73)
    ];
    activeStates = ['TxCq', 'TxReport', 'TxRr73'];
  } else {
    texts = [
      `${p} ${txCallsign} ${txGrid}`,   // Tx 1 — Answer  (TxAnswer)
      `${p} ${txCallsign} R+00`,         // Tx 2 — Report  (TxReport)
      `${p} ${txCallsign} 73`,           // Tx 3 — 73      (Tx73)
    ];
    activeStates = ['TxAnswer', 'TxReport', 'Tx73'];
  }

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
 * @param {string}                  state              - QsoState string (e.g. 'Idle', 'TxAnswer')
 * @param {string|null}             partner            - Active partner callsign or null
 * @param {boolean}                 autoAnswerEnabled  - Whether tx.autoAnswer is true
 * @param {'answerer'|'caller'|undefined} [role]       - Controller role; falls back to currentTxRole
 * @param {boolean|undefined}       [keying]            - IQsoController.Keying; falls back to currentKeying
 */
function renderTxPanel(state, partner, autoAnswerEnabled, role, keying) {
  // Capture previous state before overwriting — used below for D-CALLER-008 sweep.
  const prevState = currentTxState;

  // Persist for subsequent partial updates (e.g. WS txState without config change).
  currentTxState           = state;
  currentAutoAnswerEnabled = autoAnswerEnabled;
  if (role) currentTxRole  = role;
  const effectiveKeying = keying ?? currentKeying;
  currentKeying = effectiveKeying;

  // Track partner for TX panel state display and message row templates.
  currentTxPartner = partner;

  // ── Enable/Disable toggle button ─────────────────────────────────────
  // D-TX-UI-002: label is always "Enable TX"; red background alone signals the armed state.
  // FR-TX-UI-004 (tx-state-indicators): dark red when armed-idle, bright red when armed AND
  // actively keying (dev-task 2026-07-10-tx-btn-live-verify-and-settings-tab-wrap.md item A
  // supersedes the prior state-string-prefix derivation, tx-state-indicators spec.md
  // Decision 2 — Keying is ground truth: true only while the daemon is actually inside its
  // TransmitAsync/KeyDownAsync bracket, so it can't under-report a retransmit the way the
  // old state-prefix check could).
  if (txEnableBtnEl) {
    txEnableBtnEl.textContent = 'Enable TX';
    if (autoAnswerEnabled) {
      txEnableBtnEl.classList.add('tx-btn-armed');
    } else {
      txEnableBtnEl.classList.remove('tx-btn-armed');
    }

    if (autoAnswerEnabled && effectiveKeying) {
      txEnableBtnEl.classList.add('tx-btn-transmitting');
    } else {
      txEnableBtnEl.classList.remove('tx-btn-transmitting');
    }
  }

  // ── Call CQ button — enable/disable + label + engaged colour ─────────
  // web-frontend "TX panel — Call CQ button" (f-004-operator-visibility-improvements):
  // supersedes the old `disabled = (state !== 'Idle')` gating. While role === 'caller'
  // the button stays enabled throughout the session ("Stop CQ" → graceful stop, task 3.9);
  // it is disabled only when the answerer role is mid-QSO (role !== 'caller' && state !== 'Idle').
  // currentTxRole has already been updated above (if role was supplied this call).
  // tx-state-indicators: bright green (`tx-call-cq-armed`) whenever engaged
  // (role === 'caller' && autoAnswerEnabled), independent of the disabled/label state above —
  // this can be true even at state === 'Idle' (a caller-role daemon armed but not yet
  // transmitting), so it is computed separately from isCallerEngaged.
  if (txCallCqBtnEl) {
    const isCallerEngaged = currentTxRole === 'caller' && state !== 'Idle';

    txCallCqBtnEl.disabled    = (currentTxRole !== 'caller') && (state !== 'Idle');
    txCallCqBtnEl.textContent = isCallerEngaged ? 'Stop CQ' : 'Call CQ';

    if (currentTxRole === 'caller' && autoAnswerEnabled) {
      txCallCqBtnEl.classList.add('tx-call-cq-armed');
    } else {
      txCallCqBtnEl.classList.remove('tx-call-cq-armed');
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

  // ── Pileup-mode toggle (FR-PILEUP-001) ───────────────────────────────
  // currentTxRole has already been updated above (if role was supplied).
  if (pileupModeRowEl) {
    pileupModeRowEl.hidden = (currentTxRole !== 'caller');
  }
  if (pileupAutoSelectEl) {
    pileupAutoSelectEl.checked = (currentCallerPartnerSelect === 'First');
  }

  // ── Message rows ─────────────────────────────────────────────────────
  renderMessageRows(partner, state, autoAnswerEnabled, role ?? currentTxRole);

  // D-CALLER-008: Sweep stale decode-responder rows when WaitAnswer begins.
  // Rows from prior WaitAnswer sessions carry the decode-responder class but
  // have stale responseCycleStartUtc values.  Clearing them here ensures only
  // rows created in the new WaitAnswer window are teal and single-click-selectable.
  // Note: rows are NOT cleared on WaitAnswer exit so the operator can still
  // double-click them (D-CALLER-012) to abort and re-engage.
  if (prevState !== 'WaitAnswer' && state === 'WaitAnswer') {
    decodesBody.querySelectorAll('tr.decode-responder').forEach(row => {
      row.classList.remove('decode-responder');
      row.style.cursor        = '';
      row.style.pointerEvents = 'none';
    });
  }
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

// ── decode-panel-filtering: filter state and popup UI ───────────────────────
//
// `isDecodeVisible` and `UNFILTERED_DECODE_FILTER` live in ./decodeFilter.js (a DOM-free
// module) so the visibility predicate can be exercised directly by `node --test` without a
// browser — see decodeFilter.test.js and design.md Decision 2's drift-risk mitigation.

/** @type {import('./decodeFilter.js').DecodeFilterState} */
let currentDecodeFilter = { ...UNFILTERED_DECODE_FILTER };

// Distinct attribute values seen this session (design.md Decision 4: "session-seen", not just
// the currently-rendered/MAX_DECODE_ROWS-capped row list — a value that has scrolled off the
// table is still offered as a filter checkbox).
const seenEntities   = /** @type {Set<string>} */ (new Set());
const seenContinents = /** @type {Set<string>} */ (new Set());
const seenCqZones    = /** @type {Set<number>} */ (new Set());
const seenItuZones   = /** @type {Set<number>} */ (new Set());

/**
 * Re-evaluates every currently-rendered decode row against `currentDecodeFilter`, showing or
 * hiding each one accordingly. Called after any filter change — this tab's own edit or a
 * `decodeFilterChanged` event from another tab — so already-rendered rows never go stale.
 */
function reapplyDecodeFilterToRenderedRows() {
  for (const row of decodesBody.querySelectorAll('tr')) {
    const decode = /** @type {any} */ (row).__decode;
    if (!decode) continue; // the placeholder "no data yet" row never carries __decode
    row.hidden = !isDecodeVisible(decode, currentDecodeFilter);
  }
  updateFilterHeaderStyles();
}

/**
 * Bolds each filterable column header whose axis is currently restricting anything (an
 * attribute allow-list and/or a worked-before tri-state narrower than "everything"), so the
 * operator can see at a glance which columns have an active filter without opening every popup.
 * Called from inside `reapplyDecodeFilterToRenderedRows()` so every `currentDecodeFilter`
 * mutation (local edit or a `decodeFilterChanged` broadcast from another tab) keeps this in sync.
 */
function updateFilterHeaderStyles() {
  for (const axis of Object.values(FILTER_AXES)) {
    const headerEl = document.getElementById(axis.headerId);
    if (!headerEl) continue;
    const active = currentDecodeFilter[axis.statesField] != null ||
      (axis.attributeField && currentDecodeFilter[axis.attributeField] != null);
    headerEl.classList.toggle('filter-axis-active', !!active);
  }
}

// ── Column-header filter popup ──────────────────────────────────────────────

/**
 * @typedef {{headerId: string, attributeField: string|null, statesField: string,
 *            seen: () => Set<string|number>, label: string}} FilterAxisConfig
 */
/** @type {Record<string, FilterAxisConfig>} */
const FILTER_AXES = {
  ctc:  { headerId: 'col-ctc',  attributeField: null,               statesField: 'contactStates',   seen: () => new Set(),      label: 'Ctc (Contact)' },
  dxcc: { headerId: 'col-dxcc', attributeField: 'allowedEntities',   statesField: 'countryStates',   seen: () => seenEntities,   label: 'DXCC (Country)' },
  cnt:  { headerId: 'col-cnt',  attributeField: 'allowedContinents', statesField: 'continentStates', seen: () => seenContinents, label: 'Cnt (Continent)' },
  cqz:  { headerId: 'col-cqz',  attributeField: 'allowedCqZones',    statesField: 'cqZoneStates',    seen: () => seenCqZones,    label: 'CQz (CQ Zone)' },
  itz:  { headerId: 'col-itz',  attributeField: 'allowedItuZones',   statesField: 'ituZoneStates',   seen: () => seenItuZones,   label: 'ITz (ITU Zone)' },
};

const WORKED_BEFORE_OPTIONS = [
  { value: 'never',         label: 'Never worked' },
  { value: 'differentBand', label: 'Worked — different band' },
  { value: 'thisBand',      label: 'Worked — this band' },
];

const decodeFilterPopupEl = /** @type {HTMLElement} */ (document.getElementById('decode-filter-popup'));

/** Pushes `currentDecodeFilter` to the daemon. Errors are logged, not surfaced to the operator —
 *  the checkbox state (already applied locally) reflects intent even if the POST fails; the
 *  next successful GET/broadcast reconciles it. */
async function commitDecodeFilterChange() {
  try {
    await postDecodeFilter(currentDecodeFilter);
  } catch (err) {
    console.error('POST /api/v1/decode-filter failed:', err);
  }
}

/**
 * Builds/refreshes the popup body for `axisKey` and shows it anchored under the clicked header.
 * @param {string} axisKey
 * @param {HTMLElement} anchorEl
 */
function openFilterPopup(axisKey, anchorEl) {
  const axis = FILTER_AXES[axisKey];
  decodeFilterPopupEl.innerHTML = '';
  decodeFilterPopupEl.dataset.axis = axisKey;

  const title = document.createElement('div');
  title.className = 'decode-filter-popup-title';
  title.textContent = axis.label;
  decodeFilterPopupEl.appendChild(title);

  // ── Attribute allow-list section (absent for Ctc — no small enumerable value-set) ──
  if (axis.attributeField) {
    const attributeField = axis.attributeField;
    const section = document.createElement('div');
    section.className = 'decode-filter-popup-section';

    const values = [...axis.seen()].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
    if (values.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'decode-filter-popup-empty';
      empty.textContent = 'No values decoded yet this session.';
      section.appendChild(empty);
    } else {
      const selectRow = document.createElement('div');
      selectRow.className = 'decode-filter-popup-select-row';

      const selectAllBtn = document.createElement('button');
      selectAllBtn.type = 'button';
      selectAllBtn.textContent = 'Select All';
      selectAllBtn.addEventListener('click', () => {
        for (const cb of section.querySelectorAll('input[type=checkbox]')) {
          /** @type {HTMLInputElement} */ (cb).checked = true;
        }
        currentDecodeFilter = { ...currentDecodeFilter, [attributeField]: null };
        reapplyDecodeFilterToRenderedRows();
        commitDecodeFilterChange();
      });

      const selectNoneBtn = document.createElement('button');
      selectNoneBtn.type = 'button';
      selectNoneBtn.textContent = 'Select None';
      selectNoneBtn.addEventListener('click', () => {
        for (const cb of section.querySelectorAll('input[type=checkbox]')) {
          /** @type {HTMLInputElement} */ (cb).checked = false;
        }
        currentDecodeFilter = { ...currentDecodeFilter, [attributeField]: [] };
        reapplyDecodeFilterToRenderedRows();
        commitDecodeFilterChange();
      });

      selectRow.appendChild(selectAllBtn);
      selectRow.appendChild(selectNoneBtn);
      section.appendChild(selectRow);

      const currentSet = /** @type {Array<string|number>|null} */ (currentDecodeFilter[attributeField]);
      for (const value of values) {
        const row = document.createElement('label');
        row.className = 'decode-filter-popup-row';
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = currentSet === null || currentSet.includes(value);
        cb.addEventListener('change', () => {
          const checkboxes = [...section.querySelectorAll('input[type=checkbox]')];
          const allChecked = checkboxes.every(c => /** @type {HTMLInputElement} */ (c).checked);
          currentDecodeFilter = {
            ...currentDecodeFilter,
            [attributeField]: allChecked
              ? null
              : values.filter((_, i) => /** @type {HTMLInputElement} */ (checkboxes[i]).checked),
          };
          reapplyDecodeFilterToRenderedRows();
          commitDecodeFilterChange();
        });
        row.appendChild(cb);
        row.appendChild(document.createTextNode(' ' + value));
        section.appendChild(row);
      }
    }
    decodeFilterPopupEl.appendChild(section);
  }

  // ── Worked-before tri-state section (every axis, including Ctc) ────────────────────
  {
    const statesField = axis.statesField;
    const wbSection = document.createElement('div');
    wbSection.className = 'decode-filter-popup-section';
    const wbCurrentSet = /** @type {string[]|null} */ (currentDecodeFilter[statesField]);
    for (const opt of WORKED_BEFORE_OPTIONS) {
      const row = document.createElement('label');
      row.className = 'decode-filter-popup-row';
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = wbCurrentSet === null || wbCurrentSet.includes(opt.value);
      cb.addEventListener('change', () => {
        const checkboxes = [...wbSection.querySelectorAll('input[type=checkbox]')];
        const allChecked = checkboxes.every(c => /** @type {HTMLInputElement} */ (c).checked);
        currentDecodeFilter = {
          ...currentDecodeFilter,
          [statesField]: allChecked
            ? null
            : WORKED_BEFORE_OPTIONS
                .filter((_, i) => /** @type {HTMLInputElement} */ (checkboxes[i]).checked)
                .map(o => o.value),
        };
        reapplyDecodeFilterToRenderedRows();
        commitDecodeFilterChange();
      });
      row.appendChild(cb);
      row.appendChild(document.createTextNode(' ' + opt.label));
      wbSection.appendChild(row);
    }
    decodeFilterPopupEl.appendChild(wbSection);
  }

  const closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.className = 'decode-filter-popup-close';
  closeBtn.textContent = 'Close';
  closeBtn.addEventListener('click', closeFilterPopup);
  decodeFilterPopupEl.appendChild(closeBtn);

  // Position under the clicked header.
  const rect = anchorEl.getBoundingClientRect();
  decodeFilterPopupEl.style.top  = `${rect.bottom + window.scrollY}px`;
  decodeFilterPopupEl.style.left = `${rect.left + window.scrollX}px`;
  decodeFilterPopupEl.hidden = false;
}

function closeFilterPopup() {
  decodeFilterPopupEl.hidden = true;
  delete decodeFilterPopupEl.dataset.axis;
}

/** Re-renders the currently-open popup (if any) so it reflects a filter change from another tab. */
function refreshOpenFilterPopupIfAny() {
  const axisKey = decodeFilterPopupEl.dataset.axis;
  if (!axisKey || decodeFilterPopupEl.hidden) return;
  const headerEl = document.getElementById(FILTER_AXES[axisKey].headerId);
  if (headerEl) openFilterPopup(axisKey, headerEl);
}

/** Wires column-header click handlers and fetches the daemon's current filter state. */
function initDecodeFilter() {
  for (const [axisKey, axis] of Object.entries(FILTER_AXES)) {
    const headerEl = document.getElementById(axis.headerId);
    if (!headerEl) continue;
    headerEl.style.cursor = 'pointer';
    headerEl.addEventListener('click', () => {
      if (!decodeFilterPopupEl.hidden && decodeFilterPopupEl.dataset.axis === axisKey) {
        closeFilterPopup();
      } else {
        openFilterPopup(axisKey, headerEl);
      }
    });
  }

  // Close on outside click (but not on a header click, which toggles independently above,
  // or a click inside the popup itself, which drives its own checkbox/close handlers).
  document.addEventListener('click', (ev) => {
    if (decodeFilterPopupEl.hidden) return;
    const target = /** @type {Node} */ (ev.target);
    if (decodeFilterPopupEl.contains(target)) return;
    if (target instanceof HTMLElement && target.classList.contains('filterable-col')) return;
    closeFilterPopup();
  });

  getDecodeFilter().then(state => {
    currentDecodeFilter = { ...UNFILTERED_DECODE_FILTER, ...state };
    reapplyDecodeFilterToRenderedRows();
  }).catch(err => {
    console.warn('GET /api/v1/decode-filter failed on load — filtering stays unfiltered:', err);
  });
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
 * Creates a readonly indicator cell for the worked-before Ctc/DXCC/Cnt/CQz/ITz columns
 * (qso-confirmation / qso-confirmation-band-awareness capabilities). Renders a tri-state glyph
 * from the wire value `"never"` / `"differentBand"` / `"thisBand"`:
 * - `"never"` (or absent/unrecognised) → empty cell.
 * - `"differentBand"` → a distinct "worked, different band" glyph.
 * - `"thisBand"` → the green checkmark glyph (unchanged from the prior binary implementation's
 *   "worked" rendering).
 * A plain `<span>` — nothing to disable, no click/change handler — carried forward from
 * design.md Decision 7 (a disabled checkbox's browser-suppressed `accent-color` made the
 * checked state illegible against the dark theme).
 *
 * @param {'never'|'differentBand'|'thisBand'|undefined|null} state
 * @returns {HTMLTableCellElement}
 */
function makeWorkedBeforeCell(state) {
  const td = document.createElement('td');
  const span = document.createElement('span');
  if (state === 'thisBand') {
    span.className = 'worked-before-mark worked-before-mark-this-band';
    span.textContent = '✓';
  } else if (state === 'differentBand') {
    span.className = 'worked-before-mark worked-before-mark-different-band';
    span.textContent = '●';
  } else {
    span.className = 'worked-before-mark';
    span.textContent = '';
  }
  td.appendChild(span);
  return td;
}

/**
 * Formats a decode row's advisory `region` field for display (region-lookup capability).
 * - Synthetic region (NFR-021, R&R Study test traffic): the entity label verbatim, no continent.
 * - Recognised region: "{continent} — {entity}".
 * - Unresolved / absent: "Unknown".
 *
 * @param {{continent?: string|null, entity: string, synthetic: boolean}|null|undefined} region
 * @returns {string}
 */
function formatRegion(region) {
  if (!region) return 'Unknown';
  if (region.synthetic) return region.entity;
  return region.continent ? `${region.continent} — ${region.entity}` : region.entity;
}

/**
 * Handle a `decode` WebSocket event.
 * Prepends one row per result, removes the placeholder row on first decode,
 * and caps the table at MAX_DECODE_ROWS.
 *
 * @param {Array<{time:string, snr:number, dt:number, freqHz:number, message:string, band?:string|null, region?:{continent?:string|null, entity:string, synthetic:boolean}|null, workedBefore?:{contact:string, country:string, continent:string, cqZone:string, ituZone:string}|null}>} results
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
    tr.appendChild(makeCell(r.band ?? ''));
    tr.appendChild(makeCell(snrStr));
    tr.appendChild(makeCell(dtStr));
    tr.appendChild(makeCell(String(r.freqHz)));
    tr.appendChild(makeCell(r.message));
    tr.appendChild(makeCell(formatRegion(r.region)));

    // Worked-before Ctc/DXCC/Cnt/CQz/ITz columns (qso-confirmation /
    // qso-confirmation-band-awareness capabilities). Default to empty (never worked before, or
    // unresolved) when the field or a given sub-field is absent.
    const wb = r.workedBefore;
    tr.appendChild(makeWorkedBeforeCell(wb?.contact));
    tr.appendChild(makeWorkedBeforeCell(wb?.country));
    tr.appendChild(makeWorkedBeforeCell(wb?.continent));
    tr.appendChild(makeWorkedBeforeCell(wb?.cqZone));
    tr.appendChild(makeWorkedBeforeCell(wb?.ituZone));

    // decode-panel-filtering: track distinct attribute values seen this session (for the
    // column-header popup's checkbox candidates), retain the raw decode on the row (so
    // reapplyDecodeFilterToRenderedRows can re-evaluate it later without a server round-trip),
    // and hide the row now if it fails the currently active filter.
    if (r.region) {
      if (r.region.entity)          seenEntities.add(r.region.entity);
      if (r.region.continent)       seenContinents.add(r.region.continent);
      if (r.region.cqZone != null)  seenCqZones.add(r.region.cqZone);
      if (r.region.ituZone != null) seenItuZones.add(r.region.ituZone);
    }
    /** @type {any} */ (tr).__decode = r;
    tr.hidden = !isDecodeVisible(r, currentDecodeFilter);

    // Store cycle-start UTC string as a data attribute for the dblclick handler.
    tr.dataset.cqCycleStartUtc = parseFt8CycleStartUtc(r.time);

    // CQ row highlighting (TX-D01). The double-click-to-answer gesture itself is handled
    // exclusively by the D-CALLER-012 engage-decode listener below (D-CALLER-019 removed the
    // redundant legacy postTxAnswerCq dblclick handler that used to live here — it always lost
    // the race against engage-decode's own abort-then-dispatch and produced a guaranteed
    // spurious 409 on every double-click; see
    // dev-tasks/2026-07-12-answerer-abort-hard-stop-and-reengage-timing.md).
    if (r.message.startsWith('CQ ')) {
      tr.classList.add('decode-cq');
      tr.style.cursor = 'pointer';
    }

    // Highlight any row addressed to the operator's callsign in red.
    // Simple rule: any space-delimited token in the message matches our callsign.
    const msgTokens = r.message.split(' ');
    if (txCallsign && msgTokens.some(t => tokenMatchesCallsign(t, txCallsign))) {
      tr.classList.add('decode-partner');
    }

    // Task 7.5 / 7.7 — Caller responder highlighting and click-to-select.
    // When role is 'caller', state is WaitAnswer, and CallerPartnerSelect is
    // 'None', highlight rows where someone is calling us back (first token ===
    // txCallsign or its base callsign, to handle /P suffix stripping by the
    // FT8 decoder) and attach a click handler that fires
    // POST /api/v1/tx/select-responder with the responder's callsign.
    // Note: decode-responder (teal) wins over decode-partner (red) in the CSS
    // cascade when both apply, correctly signalling that the row is clickable.
    const txCallsignBase = txCallsign ? txCallsign.split('/')[0] : '';
    const isResponderRow =
      currentTxRole === 'caller'
      && currentTxState === 'WaitAnswer'
      && currentCallerPartnerSelect === 'None'
      && msgTokens.length >= 3
      && txCallsign
      && (msgTokens[0] === txCallsign
          || msgTokens[0] === txCallsignBase);

    if (isResponderRow) {
      tr.classList.add('decode-responder');
      tr.style.cursor = 'pointer';

      let selectInFlight = false;
      tr.addEventListener('click', async () => {
        if (selectInFlight) return;
        selectInFlight = true;
        tr.style.pointerEvents = 'none';

        const responderCallsign    = msgTokens[1];
        const responseCycleStartUtc = tr.dataset.cqCycleStartUtc;
        try {
          const status = await postTxSelectResponder(
            responderCallsign, r.freqHz, responseCycleStartUtc);
          renderTxPanel(
            status.state             ?? currentTxState,
            status.partner           ?? currentTxPartner,
            status.autoAnswerEnabled ?? currentAutoAnswerEnabled,
            status.role              ?? currentTxRole,
            status.keying            ?? currentKeying);
          setTimeout(() => {
            selectInFlight = false;
            tr.style.pointerEvents = '';
          }, 400);
        } catch (err) {
          selectInFlight = false;
          tr.style.pointerEvents = '';
          const errStatus = /** @type {any} */ (err)?.status;
          if (errStatus === 409 || errStatus === 405) {
            console.warn('postTxSelectResponder ignored — role/state mismatch:', errStatus);
          } else {
            console.error('postTxSelectResponder error:', err);
          }
        }
      });
    }

    // ── D-CALLER-012: Double-click any decode row to abort + engage ───────────
    // The first click of a double-click fires the existing single-click handlers
    // (CQ answer or responder select) which fail gracefully with 409 if not idle.
    // The dblclick then calls engage-decode which performs the abort + re-engage
    // atomically on the server.
    let engageInFlight = false;
    tr.addEventListener('dblclick', async (event) => {
      event.preventDefault();                          // best-effort: browsers don't reliably
                                                          // treat text selection as dblclick's
                                                          // preventable default action
      // D-CALLER-019: this listener is now the only dblclick handler on CQ rows (the redundant
      // legacy postTxAnswerCq handler was removed above). Carry forward its stray-selection
      // cleanup so double-clicking still doesn't leave a "CQ " text selection behind — see the
      // history this cleanup used to live under, above the removed block.
      window.getSelection()?.removeAllRanges();
      if (engageInFlight) return;
      engageInFlight = true;

      try {
        const status = await postTxEngageDecode(
          r.message,
          r.freqHz,
          tr.dataset.cqCycleStartUtc);

        renderTxPanel(
          status.state             ?? 'Idle',
          status.partner           ?? null,
          status.autoAnswerEnabled ?? false,
          status.role              ?? currentTxRole,
          status.keying            ?? false);

      } catch (err) {
        const code = /** @type {any} */ (err)?.status;

        if (code === 422) {
          // Message not actionable (73, or not addressed to us) — abort already
          // happened.  Refresh state from the server so the UI reflects Idle.
          console.info('D-CALLER-012: engage-decode not actionable for:', r.message);
          try {
            const s = await getTxStatus();
            renderTxPanel(s.state, s.partner, s.autoAnswerEnabled, s.role, s.keying);
          } catch { /* ignore secondary error */ }

        } else if (code === 503) {
          console.warn('D-CALLER-012: engage-decode — abort timed out (503).');

        } else {
          console.error('D-CALLER-012: engage-decode error:', err);
        }

      } finally {
        engageInFlight = false;
      }
    });
    // ── End D-CALLER-012 ─────────────────────────────────────────────────────

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
    // Task 7.6: read callerPartnerSelect for decode-responder row click handling.
    // Guard against null/undefined (not falsy) so 'First' (which is truthy anyway)
    // and 'None' are both accepted, and any future integer serialisation artefacts
    // are still captured correctly.
    if (config.tx?.callerPartnerSelect != null) {
      currentCallerPartnerSelect = config.tx.callerPartnerSelect;
    }
    // Sync initial checkbox state (no event fired).
    if (pileupAutoSelectEl) {
      pileupAutoSelectEl.checked = (currentCallerPartnerSelect === 'First');
    }
    renderMessageRows(currentTxPartner, currentTxState, currentAutoAnswerEnabled, currentTxRole);
  } catch {
    // Config fetch failed — timer stays hidden; message rows keep their defaults.
  }
}

// ── Status bar elements ───────────────────────────────────────────────────

const wsStateEl        = /** @type {HTMLElement} */ (document.getElementById('ws-state'));
const audioDeviceEl    = /** @type {HTMLElement} */ (document.getElementById('audio-device'));
const audioIndicatorEl = /** @type {HTMLElement} */ (document.getElementById('audio-indicator'));
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
  catBadgeEl.textContent = 'CAT';
  catBadgeEl.title       = 'CAT rig connection state: ' + status;
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
 * Update the merged decode status/toggle control to reflect the current pipeline state (FR-017).
 * @param {boolean} enabled  - Whether decoding is active.
 * @param {boolean} hasDevice - Whether an audio device is configured.
 */
function setDecodingState(enabled, hasDevice) {
  decodingEnabled = enabled;

  if (!hasDevice) {
    decodeToggleEl.textContent = 'No device';
    decodeToggleEl.className   = '';
    decodeToggleEl.disabled    = true;
    return;
  }

  if (enabled) {
    decodeToggleEl.textContent = 'DECODING';
    decodeToggleEl.className   = 'decoding-active';
    decodeToggleEl.disabled    = false;
  } else {
    decodeToggleEl.textContent = 'Start decoding';
    decodeToggleEl.className   = 'decoding-stopped';
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

// ── QSO Log Confirmation Dialog (qso-log-dialog) ─────────────────────────

/**
 * Format an ISO 8601 UTC date-time string for display.
 * @param {string} isoStr
 * @returns {string}
 */
function fmtUtc(isoStr) {
  try {
    return new Date(isoStr).toISOString().replace('T', ' ').replace(/\.\d+Z$/, 'Z');
  } catch {
    return isoStr;
  }
}

/**
 * Open the QSO confirmation dialog with data from the daemon's `qsoReview` WS event.
 * Guards against double-open; suppresses Escape close (cancel button only).
 * @param {object} ev  The parsed `qsoReview` WebSocket event object.
 */
async function openQsoLogDialog(ev) {
  const dialog = /** @type {HTMLDialogElement|null} */ (
    document.getElementById('qso-log-dialog'));
  if (!dialog) return;

  // Guard: if already open, warn and ignore.
  if (dialog.open) {
    console.warn('[qso-log-dialog] Dialog already open — ignoring duplicate qsoReview event.');
    return;
  }

  // Suppress Escape key close (cancel button is the only way to dismiss).
  const cancelHandler = (/** @type {Event} */ e) => e.preventDefault();
  dialog.addEventListener('cancel', cancelHandler, { once: false });

  // Populate read-only summary fields.
  const set = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val ?? '';
  };
  set('dlg-callsign', ev.callsign);
  set('dlg-grid',     ev.grid ?? '—');
  set('dlg-mode',     'FT8');
  set('dlg-freq',     ev.freqMHz != null ? ev.freqMHz.toFixed(6) : '');
  set('dlg-rst-sent', ev.rstSent);
  set('dlg-rst-rcvd', ev.rstRcvd);
  set('dlg-start',    fmtUtc(ev.startUtc));
  set('dlg-end',      fmtUtc(ev.endUtc));
  set('dlg-operator', ev.operatorCallsign ?? '');

  // Pre-fill editable fields from retained values.
  const txPowerEl      = /** @type {HTMLInputElement|null}  */ (document.getElementById('dlg-tx-power'));
  const commentEl      = /** @type {HTMLInputElement|null}  */ (document.getElementById('dlg-comment'));
  const propModeEl     = /** @type {HTMLSelectElement|null} */ (document.getElementById('dlg-prop-mode'));
  const nameEl         = /** @type {HTMLInputElement|null}  */ (document.getElementById('dlg-name'));
  const exchSentEl     = /** @type {HTMLInputElement|null}  */ (document.getElementById('dlg-exch-sent'));
  const exchRcvdEl     = /** @type {HTMLInputElement|null}  */ (document.getElementById('dlg-exch-rcvd'));
  const retainTxPEl    = /** @type {HTMLInputElement|null}  */ (document.getElementById('dlg-retain-tx-power'));
  const retainCommentEl = /** @type {HTMLInputElement|null} */ (document.getElementById('dlg-retain-comment'));
  const retainPropMEl  = /** @type {HTMLInputElement|null}  */ (document.getElementById('dlg-retain-prop-mode'));

  if (txPowerEl)     txPowerEl.value = ev.retainedTxPower ?? '';
  if (commentEl)     commentEl.value = ev.retainedComment ?? '';
  if (nameEl)        nameEl.value    = '';
  if (exchSentEl)    exchSentEl.value = '';
  if (exchRcvdEl)    exchRcvdEl.value = '';

  // Populate Prop Mode dropdown from /api/v1/prop-modes.
  if (propModeEl) {
    propModeEl.innerHTML = '';
    try {
      const modes = await getPropModes();
      // Filter to the active protocol only (OBS-003: removed dead `|| m.protocol === ''` branch).
      const ft8Modes = Array.isArray(modes)
        ? modes.filter(m => m.protocol === activeProtocol)
        : [];
      for (const m of ft8Modes) {
        const opt = document.createElement('option');
        opt.value       = m.value;
        opt.textContent = m.description ? `${m.value ? m.value + ' — ' : ''}${m.description}` : m.value;
        propModeEl.appendChild(opt);
      }
    } catch (err) {
      console.warn('[qso-log-dialog] Failed to load prop modes:', err);
      // OBS-001: API unavailable — restore the hardcoded blank fallback so the select
      // is never empty and the operator can still submit the dialog.
      const fallback = document.createElement('option');
      fallback.value = '';
      fallback.textContent = 'Not specified';
      propModeEl.appendChild(fallback);
    }
    // Pre-select retained prop mode.
    const retainedPm = ev.retainedPropMode ?? '';
    if ([...propModeEl.options].some(o => o.value === retainedPm)) {
      propModeEl.value = retainedPm;
    } else if (propModeEl.options.length > 0) {
      propModeEl.selectedIndex = 0;
    }
  }

  // Wire Cancel button (once; remove previous listener to avoid stacking).
  const cancelBtn = document.getElementById('dlg-cancel-btn');
  const logBtn    = document.getElementById('dlg-log-qso-btn');

  const handleCancel = () => {
    dialog.removeEventListener('cancel', cancelHandler);
    dialog.close();
  };

  const handleLog = async () => {
    logBtn && (logBtn.disabled = true);
    try {
      const body = {
        callsign:         ev.callsign,
        grid:             ev.grid     ?? null,
        rstSent:          ev.rstSent,
        rstRcvd:          ev.rstRcvd,
        startUtc:         ev.startUtc,
        endUtc:           ev.endUtc,
        freqMHz:          ev.freqMHz,
        operatorCallsign: ev.operatorCallsign,
        name:             nameEl?.value.trim()    || null,
        txPower:          txPowerEl?.value.trim() || null,
        comment:          commentEl?.value.trim() || null,
        propMode:         propModeEl?.value        || null,
        exchSent:         exchSentEl?.value.trim() || null,
        exchRcvd:         exchRcvdEl?.value.trim() || null,
        retainTxPower:    retainTxPEl?.checked  ?? false,
        retainComment:    retainCommentEl?.checked ?? false,
        retainPropMode:   retainPropMEl?.checked ?? false,
      };
      await postLogQso(body);
      dialog.removeEventListener('cancel', cancelHandler);
      dialog.close();
    } catch (err) {
      console.error('[qso-log-dialog] POST /api/v1/tx/log-qso failed:', err);
      logBtn && (logBtn.disabled = false);
      // Leave dialog open so the operator can retry.
    }
  };

  // Attach one-time handlers; cloneNode trick avoids listener accumulation.
  if (cancelBtn) {
    const freshCancel = cancelBtn.cloneNode(true);
    cancelBtn.parentNode?.replaceChild(freshCancel, cancelBtn);
    freshCancel.addEventListener('click', handleCancel, { once: true });
  }
  if (logBtn) {
    const freshLog = logBtn.cloneNode(true);
    logBtn.parentNode?.replaceChild(freshLog, logBtn);
    freshLog.disabled = false;
    freshLog.addEventListener('click', handleLog, { once: true });
  }

  dialog.showModal();
}

// ── Initialise ────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {

  // Start cycle countdown timer (shows only when enabled in config).
  // Also extracts config.tx.callsign / .grid for message row rendering (task 6.8).
  startCycleTimerIfEnabled();

  // decode-panel-filtering: wire column-header popups and seed the current filter state.
  initDecodeFilter();

  // Task 6.1 / 7.4 — Seed the TX panel with current server state on page load.
  getTxStatus().then(status => {
    // FR-PILEUP-001: initialise pileup mode from the status response if present.
    if (status.callerPartnerSelect != null) {
      currentCallerPartnerSelect = status.callerPartnerSelect;
    }
    renderTxPanel(
      status.state             ?? 'Idle',
      status.partner           ?? null,
      status.autoAnswerEnabled ?? false,
      status.role              ?? 'answerer',
      status.keying            ?? false);
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
          status.autoAnswerEnabled ?? false,
          undefined,
          status.keying            ?? false);
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
          status.autoAnswerEnabled ?? false,
          undefined,
          status.keying            ?? false);
      } catch (err) {
        console.error('POST /api/v1/tx/abort failed:', err);
      } finally {
        txAbortBtnEl.disabled = false;
      }
    });
  }

  // Task 11.8 / 3.9 — Call CQ / Stop CQ toggle button.
  // When role === 'caller' && state !== 'Idle': engaged session — POST /api/v1/tx/stop-cq
  //   requests a graceful stop (any in-progress TX plays out; no immediate audio kill).
  //   Does NOT re-render the panel from this response directly (web-frontend spec) — the
  //   panel updates once the subsequent txState WS event with state: 'Idle' arrives,
  //   consistent with how Abort TX is already handled.
  // Otherwise (Idle, any role): POST /api/v1/tx/call-cq starts a new CQ session (existing).
  // Uses a 400 ms inFlight guard on the call-cq path to block double-clicks, same pattern
  // as CQ-row clicks. The stop-cq path has no such guard — the spec requires it to be
  // idempotent on the backend, so a second click while the first is in flight is harmless.
  if (txCallCqBtnEl) {
    let callCqInFlight = false;
    txCallCqBtnEl.addEventListener('click', async () => {

      // ── Graceful stop path ────────────────────────────────────────────
      if (currentTxRole === 'caller' && currentTxState !== 'Idle') {
        try {
          await postTxStopCq();
          // Intentionally no renderTxPanel call here — see comment above.
        } catch (err) {
          console.error('POST /api/v1/tx/stop-cq failed:', err);
        }
        return;
      }

      // ── Normal Call CQ path ───────────────────────────────────────────
      if (callCqInFlight) return;
      callCqInFlight = true;
      txCallCqBtnEl.disabled = true;
      try {
        const status = await postTxCallCq();
        renderTxPanel(
          status.state             ?? currentTxState,
          status.partner           ?? currentTxPartner,
          status.autoAnswerEnabled ?? true,
          status.role              ?? 'caller',
          status.keying            ?? false);
        setTimeout(() => {
          callCqInFlight = false;
          // Button re-enable / label driven by renderTxPanel (via WS events).
        }, 400);
      } catch (err) {
        callCqInFlight = false;
        txCallCqBtnEl.disabled = (currentTxRole !== 'caller') && (currentTxState !== 'Idle');
        if (/** @type {any} */ (err)?.status === 409) {
          console.warn('Call CQ rejected — TX busy.');
        } else {
          console.error('POST /api/v1/tx/call-cq failed:', err);
        }
      }
    });
  }

  // FR-PILEUP-001 — Pileup-mode toggle change handler (register once at DOMContentLoaded).
  if (pileupAutoSelectEl) {
    pileupAutoSelectEl.addEventListener('change', async () => {
      const newMode = pileupAutoSelectEl.checked ? 'First' : 'None';
      // Optimistic local update.
      currentCallerPartnerSelect = newMode;

      try {
        await postTxCallerPartnerSelect(newMode);
      } catch (err) {
        // Revert on error.
        currentCallerPartnerSelect = newMode === 'First' ? 'None' : 'First';
        pileupAutoSelectEl.checked = (currentCallerPartnerSelect === 'First');
        console.error('Failed to save pileup mode:', err);
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

  // Task 4.1 (f-004-operator-visibility-improvements, waterfall-cursors) —
  // Ctrl+left-click: RX. Shift+left-click: both RX and TX. Any left-click with no
  // modifier held is a no-op — this is the whole point of the change (design.md
  // Decision 3): existing plain-click muscle memory stops working, on purpose, so an
  // accidental click during a live session can no longer silently retune anything.
  canvas.addEventListener('click', (e) => {
    if (e.shiftKey) {
      // Shift+left-click: set both RX and TX to the same frequency.
      const hz = freqFromEvent(e);
      applyAudioOffset(hz, hz, holdTxFreqEl?.checked ?? false);
      postAudioOffsetSilently(hz, hz, holdTxFreqEl?.checked ?? false);
    } else if (e.ctrlKey) {
      // Ctrl+left-click: set RX only; TX stays unchanged.
      const hz = freqFromEvent(e);
      applyAudioOffset(hz, currentTxHz, holdTxFreqEl?.checked ?? false);
      postAudioOffsetSilently(hz, currentTxHz, holdTxFreqEl?.checked ?? false);
    }
    // No modifier held: no-op — deliberately does not touch RX/TX or call the API.
  });

  // Task 4.2 — Ctrl+right-click: set TX. Shift+right-click and an unmodified
  // right-click are no-ops. The browser's context menu is suppressed unconditionally
  // for every right-click regardless of modifier (design.md Decision 3) — the waterfall
  // canvas has no useful native context-menu items, and showing it only for the
  // no-op cases would be an inconsistent experience tied to a modifier key the
  // operator may not even be thinking about.
  canvas.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    if (!e.ctrlKey) return; // Shift+right-click or unmodified right-click: no-op.
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

    // Task 6.5 / 7.4 — txState event: update TX panel state and message rows.
    // D-TX-UI-003: read autoAnswerEnabled from the event (now carried in the WS frame)
    // so QSO completion / abort disarms the panel without a separate HTTP call.
    // Task 7.1: role field updates currentTxRole for decode-table highlighting.
    if (event.type === 'txState') {
      renderTxPanel(
        event.state             ?? 'Idle',
        event.partner           ?? null,
        event.autoAnswerEnabled ?? currentAutoAnswerEnabled,
        event.role              ?? undefined,
        event.keying            ?? currentKeying);

      // FR-UX-002: append to abort log when the daemon reports an abort reason.
      if (event.abortReason) {
        appendTxAbortLog(event.abortReason, event.partner ?? null);
      }
      return;
    }

    if (event.type === 'decode') {
      handleDecodes(event.payload);
      return;
    }

    // decode-panel-filtering: another client (or this one's own POST) changed the daemon's
    // filter state — re-evaluate every already-rendered row and refresh an open popup so the
    // change is reflected immediately, without a page reload.
    if (event.type === 'decodeFilterChanged' && event.payload) {
      currentDecodeFilter = { ...UNFILTERED_DECODE_FILTER, ...event.payload };
      reapplyDecodeFilterToRenderedRows();
      refreshOpenFilterPopupIfAny();
      return;
    }

    // qso-log-dialog (tasks 11.1–11.2): open the QSO confirmation dialog.
    if (event.type === 'qsoReview') {
      openQsoLogDialog(event);
      return;
    }
  });

  // D-LAN-005: update the Settings nav link to carry the API key so the browser
  // navigation does not trigger an unnecessary auth challenge.
  // getApiKey() is already imported from './api.js'; bootstrapApiKeyFromUrl() has
  // already run at module load time (before DOMContentLoaded), so the key is present.
  const settingsNavLink = document.querySelector('nav a[href="/settings.html"]');
  if (settingsNavLink) {
    const key = getApiKey();
    if (key) {
      settingsNavLink.href = '/settings.html?key=' + encodeURIComponent(key);
    }
  }
});
