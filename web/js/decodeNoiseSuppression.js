/**
 * decode-noise-suppression: pure resolution helpers for the Region data settings tab's
 * "Suppress Unknown region/DXCC decodes" control (design.md Decision 3/4).
 *
 * The actual effective-value *computation* (persisted-tri-state vs. region-data-presence) is
 * server-side (`DecodeNoiseSuppressionDefaults.ResolveEffectiveSuppressUnknownRegion` in
 * `OpenWSFZ.Abstractions`, surfaced via `GET /api/v1/region-data/status`'s
 * `effectiveSuppressUnknownRegion` field) — the frontend never re-derives it from entry counts.
 * What lives here is the small, genuinely client-side decision of *what the checkbox should
 * display* given the tri-state value already loaded/tracked in `settings.js`, extracted as a
 * standalone, DOM-free function so it can be exercised directly by `node --test`, mirroring the
 * `decodeFilter.js`/`isDecodeVisible` precedent.
 *
 * @module decodeNoiseSuppression
 */

/**
 * Resolves what the "Suppress Unknown region/DXCC decodes" checkbox should display.
 *
 * @param {boolean|null} raw
 *   The tri-state value currently tracked by the settings page: `null` while the operator has
 *   never explicitly chosen this session (and the persisted config had no explicit choice
 *   either), or the explicit `true`/`false` the operator (or a prior session) set.
 * @param {boolean} effectiveValue
 *   The server's live-resolved effective value (`GET /api/v1/region-data/status`'s
 *   `effectiveSuppressUnknownRegion`), used only while `raw` is still `null`.
 * @returns {boolean}
 */
export function resolveUnknownCheckboxDisplay(raw, effectiveValue) {
  return raw === null ? !!effectiveValue : raw;
}
