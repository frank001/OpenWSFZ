/**
 * decode-panel-filtering: the daemon-owned filter shape and the visibility predicate.
 *
 * `isDecodeVisible` is a hand-ported twin of `DecodeFilterEvaluator.IsVisible`
 * (`src/OpenWSFZ.Abstractions/DecodeFilterEvaluator.cs`) — structurally identical, exercised
 * against the same payload shape a decode already carries over the WebSocket. Kept in sync with
 * the C# original by disciplined 1:1 porting rather than a shared runtime, mirroring the
 * `tokenMatchesCallsign`/`MatchesCallsign` precedent (qso-confirmation Decision 3).
 *
 * Deliberately DOM-free (no `document`/`window` references) so it can be exercised directly by
 * `node --test` without a browser — see `decodeFilter.test.js`.
 *
 * @module decodeFilter
 */

/**
 * @typedef {{
 *   allowedEntities: string[]|null, allowedContinents: string[]|null,
 *   allowedCqZones: number[]|null, allowedItuZones: number[]|null,
 *   contactStates: string[]|null, countryStates: string[]|null,
 *   continentStates: string[]|null, cqZoneStates: string[]|null, ituZoneStates: string[]|null
 * }} DecodeFilterState
 */

/**
 * The all-`null` default — no restriction on any axis, every decode passes.
 * @type {DecodeFilterState}
 */
export const UNFILTERED_DECODE_FILTER = {
  allowedEntities:   null,
  allowedContinents: null,
  allowedCqZones:    null,
  allowedItuZones:   null,
  contactStates:     null,
  countryStates:     null,
  continentStates:   null,
  cqZoneStates:      null,
  ituZoneStates:     null,
};

/** The all-`"never"` default used when a decode's `workedBefore` field is absent. */
const WORKED_BEFORE_NONE = {
  contact:   'never',
  country:   'never',
  continent: 'never',
  cqZone:    'never',
  ituZone:   'never',
};

/**
 * Returns `true` if `decode` passes every active (non-null) axis of `filter`.
 *
 * An unresolved attribute value on an attribute-allow-list axis (e.g. an absent `region`, or a
 * resolved region whose `continent`/`cqZone`/`ituZone` is itself `null`) always passes that
 * axis, regardless of the axis's contents — fails open, never silently hides a decode because
 * metadata failed to resolve.
 *
 * An absent `workedBefore` is treated as {@link WORKED_BEFORE_NONE} (all `"never"`) and
 * participates normally in an active worked-before-axis filter.
 *
 * @param {{region?: {continent?: string|null, entity: string, cqZone?: number|null, ituZone?: number|null}|null,
 *           workedBefore?: {contact:string, country:string, continent:string, cqZone:string, ituZone:string}|null}} decode
 * @param {DecodeFilterState} filter
 * @returns {boolean}
 */
export function isDecodeVisible(decode, filter) {
  const region = decode.region;

  // ── Attribute allow-list axes — fail open on an unresolved value ────────
  if (filter.allowedEntities && region && !filter.allowedEntities.includes(region.entity))
    return false;

  if (filter.allowedContinents && region && region.continent != null &&
      !filter.allowedContinents.includes(region.continent))
    return false;

  if (filter.allowedCqZones && region && region.cqZone != null &&
      !filter.allowedCqZones.includes(region.cqZone))
    return false;

  if (filter.allowedItuZones && region && region.ituZone != null &&
      !filter.allowedItuZones.includes(region.ituZone))
    return false;

  // ── Worked-before tri-state axes — absent workedBefore treated as Never ─
  const wb = decode.workedBefore ?? WORKED_BEFORE_NONE;

  if (filter.contactStates   && !filter.contactStates.includes(wb.contact))     return false;
  if (filter.countryStates   && !filter.countryStates.includes(wb.country))     return false;
  if (filter.continentStates && !filter.continentStates.includes(wb.continent)) return false;
  if (filter.cqZoneStates    && !filter.cqZoneStates.includes(wb.cqZone))       return false;
  if (filter.ituZoneStates   && !filter.ituZoneStates.includes(wb.ituZone))     return false;

  return true;
}
