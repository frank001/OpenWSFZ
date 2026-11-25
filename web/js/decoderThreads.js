/**
 * Pure helpers for the Settings page's lean-decoder controls (decoder.engine, decoder.effort, decoder.threads), kept out of settings.js (which
 * touches the DOM at import) so node --test can exercise them. The page shows a stored value as stored; an absent or unknown stored word shows the
 * code default and is NOT rewritten until the operator changes the select (the daemon already reads an unknown engine as classic and an unknown
 * effort as normal).
 */

/** The code defaults (DecoderConfig): the daemon's values when a key is absent. */
export const DEFAULT_ENGINE = 'classic';
export const DEFAULT_EFFORT = 'normal';
export const DEFAULT_THREADS = 2;
export const MIN_THREADS = 1;
export const MAX_THREADS = 16;

/** The word the engine select shows for a stored value: `lean` (any case, white space ignored) shows lean, everything else the default. */
export function decoderEngineShown(stored) {
  return typeof stored === 'string' && stored.trim().toLowerCase() === 'lean' ? 'lean' : DEFAULT_ENGINE;
}

/** The word the effort select shows for a stored value: `fast` (any case, white space ignored) shows fast, everything else the default. */
export function decoderEffortShown(stored) {
  return typeof stored === 'string' && stored.trim().toLowerCase() === 'fast' ? 'fast' : DEFAULT_EFFORT;
}

/**
 * The thread count to post for the number input's text: an integer clamped to [1, 16]; an empty or non-numeric entry posts the default (2).
 * (The daemon clamps too; clamping here keeps the posted value what the operator sees on the next load.)
 */
export function decoderThreadsPayload(text) {
  const n = parseInt(text, 10);
  if (!Number.isFinite(n)) return DEFAULT_THREADS;
  return Math.min(MAX_THREADS, Math.max(MIN_THREADS, n));
}
