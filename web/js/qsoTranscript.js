/**
 * qso-transcript-panel (FR-062): the DOM-free matching/aggregation logic behind the TX panel's
 * QSO Transcript section — a single unified, newest-on-top log of every message the operator's
 * own station transmits, every decode belonging to the operator's tracked conversation, plus
 * abort-reason and partner-change events folded in as distinct entry kinds.
 *
 * Deliberately DOM-free (no `document`/`window` references) so it can be exercised directly by
 * `node --test` without a browser — mirrors `decodeFilter.js` + `decodeFilter.test.js`'s
 * precedent exactly. `web/js/main.js` imports these exports and handles only DOM rendering.
 *
 * See design.md Decisions 2 (sent-message capture), 3 (received-message matching), 4 (unified
 * entry kinds), 5 (rolling log / cap / partner-change separator) for the rationale behind each
 * function's behaviour.
 *
 * @module qsoTranscript
 */

/**
 * @typedef {'sent'|'received'|'abort'|'partner-change'} TranscriptEntryKind
 */

/**
 * @typedef {{isoTs: string, kind: TranscriptEntryKind, text: string, partner: string|null}} TranscriptEntry
 */

/** Rolling-log cap (design.md Decision 5) — raised from the prior TX_ABORT_LOG_MAX = 10. */
export const TRANSCRIPT_LOG_MAX = 100;

/**
 * Returns `true` if `token` matches `callsign` exactly or as a portable suffix
 * (e.g. "PD2FZ/P" matches callsign "PD2FZ"). A private twin of `main.js`'s
 * `tokenMatchesCallsign` — kept local so this module stays free of any import from the
 * DOM-touching `main.js`, matching the `decodeFilter.js` precedent of small, disciplined
 * duplication over a cross-module dependency.
 * @param {string} token
 * @param {string} callsign
 * @returns {boolean}
 */
function tokenMatchesCallsign(token, callsign) {
  return token === callsign || token.startsWith(callsign + '/');
}

/**
 * Returns `true` if `message` belongs to the operator's own tracked conversation: its
 * space-delimited tokens include either `txCallsign` (the operator's own callsign) or
 * `currentPartner` (the active partner), using the same matching idiom as the existing
 * `decode-partner` row highlight (`tokenMatchesCallsign` in `main.js`).
 *
 * When `currentPartner` is `null` (idle, not mid-QSO), a message matching only `txCallsign`
 * still qualifies — intentionally permissive rather than silently dropping traffic that
 * references the operator (design.md Decision 3, "Idle-state decodes").
 *
 * @param {string}      message        Full FT8 message text.
 * @param {string|null} txCallsign     The operator's own callsign, or null/empty if unknown.
 * @param {string|null} currentPartner The active tracked partner callsign, or null when idle.
 * @returns {boolean}
 */
export function shouldCaptureDecode(message, txCallsign, currentPartner) {
  if (!message) return false;
  const tokens = message.split(' ');

  if (txCallsign && tokens.some(t => tokenMatchesCallsign(t, txCallsign))) return true;
  if (currentPartner && tokens.some(t => tokenMatchesCallsign(t, currentPartner))) return true;

  return false;
}

/**
 * Constructs a transcript entry object. `isoTs` uses the same "YYYY-MM-DD HH:mm:ss UTC" format
 * as the prior `appendTxAbortLog`'s entries, for continuity with existing rendered output.
 *
 * @param {TranscriptEntryKind} kind
 * @param {string}              text     Message text, abort reason, or partner-change note.
 * @param {string|null}         [partner] Partner callsign at the time of the entry, or null.
 * @returns {TranscriptEntry}
 */
export function buildTranscriptEntry(kind, text, partner = null) {
  const isoTs = new Date().toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
  return { isoTs, kind, text, partner: partner ?? null };
}

/**
 * Unshifts `entry` onto `log` (newest-on-top) and truncates to `maxLen`, dropping the oldest
 * entries once the cap is exceeded (design.md Decision 5). Mutates and returns `log`.
 *
 * @param {TranscriptEntry[]} log
 * @param {TranscriptEntry}   entry
 * @param {number}            maxLen
 * @returns {TranscriptEntry[]}
 */
export function pushTranscriptEntry(log, entry, maxLen) {
  log.unshift(entry);
  if (log.length > maxLen) log.length = maxLen;
  return log;
}

/**
 * Returns `true` only when `newState` differs from `prevState` AND `newState` is a member of
 * `activeStates` — the state-transition detector behind "log a sent message once per actual
 * transmission step, not on every repeated render of the same state" (design.md Decision 2).
 *
 * A retried transmission (e.g. `TxReport` re-entered after leaving for `WaitRr73` and timing
 * out back to `TxReport`) correctly returns `true` again: `newState` differs from the
 * immediately preceding state even though it matches an earlier one further back.
 *
 * @param {string}   prevState
 * @param {string}   newState
 * @param {string[]} activeStates
 * @returns {boolean}
 */
export function hasEnteredNewActiveTxState(prevState, newState, activeStates) {
  return newState !== prevState && activeStates.includes(newState);
}
