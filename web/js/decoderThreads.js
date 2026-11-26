/**
 * Pure helpers for the Settings page's lean-decoder controls (decoder.engine, decoder.effort, decoder.threads), kept out of settings.js (which
 * touches the DOM at import) so node --test can exercise them. The page shows a stored value as stored; an absent or unknown stored word shows the
 * code default and is NOT rewritten until the operator changes the select (the daemon already reads an unknown engine as lean, the default, and an unknown
 * effort as normal).
 */

/** The code defaults (DecoderConfig): the daemon's values when a key is absent. */
export const DEFAULT_ENGINE = 'lean';
export const DEFAULT_EFFORT = 'normal';
/** decoder.threads: 0 (or an absent key) is automatic = min(logical processors of the daemon PC, 16); 1 to 16 is an explicit choice. */
export const AUTO_THREADS = 0;
/** What the field shows for automatic when the daemon did not report its processor count (the old default); nothing else is said then. */
export const FALLBACK_SHOWN_THREADS = 2;
export const MIN_THREADS = 1;
export const MAX_THREADS = 16;

/** The word the engine select shows for a stored value: `classic` (any case, white space ignored) shows classic, everything else the default (lean). */
export function decoderEngineShown(stored) {
  return typeof stored === 'string' && stored.trim().toLowerCase() === 'classic' ? 'classic' : DEFAULT_ENGINE;
}

/** The word the effort select shows for a stored value: `fast` (any case, white space ignored) shows fast, everything else the default. */
export function decoderEffortShown(stored) {
  return typeof stored === 'string' && stored.trim().toLowerCase() === 'fast' ? 'fast' : DEFAULT_EFFORT;
}

/** The automatic thread count for a host with this many logical processors (min(count, 16)), or null when the count is missing or not a positive integer. */
export function autoThreadsValue(processorCount) {
  return Number.isInteger(processorCount) && processorCount > 0 ? Math.min(MAX_THREADS, processorCount) : null;
}

/**
 * What the number input shows after a load, and whether the value is automatic. A stored integer other than 0 is an explicit choice, shown clamped to
 * 1 to 16 (as the daemon clamps it); an absent, 0 or non-numeric stored value is automatic and shows the auto value (or 2 when the processor count is unknown).
 * @returns {{auto: boolean, value: number}}
 */
export function decoderThreadsLoaded(stored, processorCount) {
  if (Number.isInteger(stored) && stored !== AUTO_THREADS) {
    return { auto: false, value: Math.min(MAX_THREADS, Math.max(MIN_THREADS, stored)) };
  }
  return { auto: true, value: autoThreadsValue(processorCount) ?? FALLBACK_SHOWN_THREADS };
}

/** The "Automatic" hint under the field: empty when the processor count is unknown (nothing but the fallback value is said then). */
export function decoderThreadsAutoHint(processorCount) {
  const n = autoThreadsValue(processorCount);
  if (n === null) return '';
  return `Automatic: this PC has ${processorCount} logical processors, so ${n} threads (maximum ${MAX_THREADS}).`;
}

/**
 * The thread count to post. While the field is automatic (never touched since load, or reset) it posts 0 and so stores nothing the operator did not choose;
 * once touched it posts the typed integer clamped to [1, 16] (an empty or non-numeric entry means automatic, 0). A loaded explicit value, untouched, posts as stored.
 * (The daemon clamps too; clamping here keeps the posted value what the operator sees on the next load.)
 */
export function decoderThreadsPayload(text, auto = false) {
  if (auto) return AUTO_THREADS;
  const n = parseInt(text, 10);
  if (!Number.isFinite(n)) return AUTO_THREADS;
  return Math.min(MAX_THREADS, Math.max(MIN_THREADS, n));
}

/**
 * The engine / effort value to post: a changed select posts the new choice; an unchanged one posts the stored word back as it was (an unknown word is kept),
 * and when the key was never stored it posts nothing (undefined, dropped by JSON), so a page save never writes a default the operator did not choose.
 */
export function decoderChoicePayload(current, shown, loadedRaw) {
  return current !== shown ? current : (loadedRaw ?? undefined);
}
