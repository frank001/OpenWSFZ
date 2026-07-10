namespace OpenWSFZ.Abstractions;

/// <summary>
/// Evaluates whether a <see cref="DecodeResult"/> is visible/engageable under a
/// <see cref="DecodeFilterState"/> (<c>decode-panel-filtering</c> capability, design.md
/// Decision 2). Consulted directly (same assembly graph) by <c>QsoAnswererService</c> and
/// <c>QsoCallerService</c> at their single engagement-decision point each, and hand-ported
/// (not shared at runtime) to <c>web/js/main.js</c>'s <c>isDecodeVisible</c> for the frontend
/// row-hiding logic — mirroring the existing <c>tokenMatchesCallsign</c>/<c>MatchesCallsign</c>
/// precedent (<c>qso-confirmation</c> Decision 3) for keeping the same predicate logic
/// consistent across languages via disciplined 1:1 porting rather than a shared runtime.
/// </summary>
public static class DecodeFilterEvaluator
{
    /// <summary>
    /// Returns <see langword="true"/> if <paramref name="decode"/> passes every active
    /// (non-null) axis of <paramref name="filter"/>.
    /// <para>
    /// An unresolved attribute value on an attribute-allow-list axis (e.g. <c>Region: null</c>,
    /// or a resolved <see cref="RegionInfo"/> whose <see cref="RegionInfo.Continent"/>/
    /// <see cref="RegionInfo.CqZone"/>/<see cref="RegionInfo.ItuZone"/> is itself <c>null</c>)
    /// always passes that axis, regardless of the axis's contents — fails open, never
    /// silently hides a decode because metadata failed to resolve.
    /// </para>
    /// <para>
    /// A <c>null</c> <see cref="DecodeResult.WorkedBefore"/> is treated as
    /// <see cref="WorkedBeforeInfo.None"/> (all <see cref="WorkedBeforeState.Never"/>) and
    /// participates normally in an active worked-before-axis filter.
    /// </para>
    /// </summary>
    public static bool IsVisible(DecodeResult decode, DecodeFilterState filter)
    {
        var region = decode.Region;

        // ── Attribute allow-list axes — fail open on an unresolved value ────────
        if (filter.AllowedEntities is not null &&
            region is not null &&
            !filter.AllowedEntities.Contains(region.Entity))
            return false;

        if (filter.AllowedContinents is not null &&
            region?.Continent is not null &&
            !filter.AllowedContinents.Contains(region.Continent))
            return false;

        if (filter.AllowedCqZones is not null &&
            region?.CqZone is not null &&
            !filter.AllowedCqZones.Contains(region.CqZone.Value))
            return false;

        if (filter.AllowedItuZones is not null &&
            region?.ItuZone is not null &&
            !filter.AllowedItuZones.Contains(region.ItuZone.Value))
            return false;

        // ── Worked-before tri-state axes — absent WorkedBefore treated as Never ─
        var workedBefore = decode.WorkedBefore ?? WorkedBeforeInfo.None;

        if (filter.ContactStates   is not null && !filter.ContactStates.Contains(workedBefore.Contact))
            return false;

        if (filter.CountryStates   is not null && !filter.CountryStates.Contains(workedBefore.Country))
            return false;

        if (filter.ContinentStates is not null && !filter.ContinentStates.Contains(workedBefore.Continent))
            return false;

        if (filter.CqZoneStates    is not null && !filter.CqZoneStates.Contains(workedBefore.CqZone))
            return false;

        if (filter.ItuZoneStates   is not null && !filter.ItuZoneStates.Contains(workedBefore.ItuZone))
            return false;

        return true;
    }
}
