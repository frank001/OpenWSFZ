using System.Text.Json.Serialization;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// Operator-controlled, persisted suppression of decode-panel/QSO-automation noise
/// (<c>decode-noise-suppression</c> capability). Evaluated by <c>DecodeNoiseSuppressionFilter</c>
/// upstream of the decode-panel WebSocket broadcast and the
/// <c>QsoAnswererService</c>/<c>QsoCallerService</c> batch input; <c>ALL.TXT</c> is never affected
/// by either setting (design.md Decision 1).
/// </summary>
public sealed record DecodeNoiseSuppressionConfig
{
    // ── Deserialization note (Lesson 6 / D-WFC-001 pattern, mirrors DecoderConfig) ──────────
    //
    // SuppressSynthetic defaults to true, which is not the CLR zero-default for bool. A JSON
    // object that omits the "suppressSynthetic" key needs an explicit parameter default here —
    // otherwise STJ source-gen would deserialise the absent field to false. SuppressUnknownRegion's
    // default (null) happens to coincide with bool?'s CLR default, so no equivalent trick is
    // strictly required for it, but the [JsonConstructor] is applied to both for symmetry.
    // ─────────────────────────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Deserialization constructor used by the STJ source-generated context.
    /// Parameter defaults ensure a field absent from an older/partial config object loads with
    /// the documented default rather than a CLR zero-value (Lesson 6 / D-WFC-001 pattern).
    /// </summary>
    [JsonConstructor]
    public DecodeNoiseSuppressionConfig(bool? suppressUnknownRegion = null, bool suppressSynthetic = true)
    {
        SuppressUnknownRegion = suppressUnknownRegion;
        SuppressSynthetic     = suppressSynthetic;
    }

    /// <summary>
    /// Whether decodes with an unresolved (<c>null</c>) region are suppressed from the decode
    /// panel and QSO-controller eligibility. <c>null</c> means the operator has never explicitly
    /// chosen a value — the effective value is then computed from region-data presence
    /// (design.md Decision 3): <c>false</c> (not suppressed) while
    /// <see cref="ICallsignRegionStore.Entries"/> is empty, <c>true</c> (suppressed) once it has
    /// at least one entry. Once explicitly set to <c>true</c>/<c>false</c> by the operator via the
    /// settings page, it stays exactly as set regardless of any subsequent region-data-refresh
    /// activity — an explicit operator choice is never silently recomputed.
    /// </summary>
    public bool? SuppressUnknownRegion { get; init; } = null;

    /// <summary>
    /// Whether decodes flagged <see cref="RegionInfo.Synthetic"/> (R&amp;R-study Q-prefix test
    /// traffic) are suppressed from the decode panel and QSO-controller eligibility. Defaults to
    /// <c>true</c> (suppressed) on a fresh configuration — an operator observing an R&amp;R study
    /// run against a live instance must explicitly uncheck the settings-page control to see
    /// synthetic decodes come through normally.
    /// </summary>
    public bool SuppressSynthetic { get; init; } = true;
}

/// <summary>
/// Shared default-resolution logic for <see cref="DecodeNoiseSuppressionConfig.SuppressUnknownRegion"/>
/// (design.md Decision 3). Lives in <c>OpenWSFZ.Abstractions</c> — rather than alongside the
/// suppression gate itself in <c>OpenWSFZ.Daemon</c> — specifically so that both
/// <c>OpenWSFZ.Daemon</c>'s <c>DecodeNoiseSuppressionFilter</c> (the actual suppression gate) and
/// <c>OpenWSFZ.Web</c>'s <c>GET /api/v1/region-data/status</c> endpoint (the settings page's
/// live-effective-value display, task 3.4) compute the identical value from a single source of
/// truth. <c>OpenWSFZ.Web</c> does not reference <c>OpenWSFZ.Daemon</c> (the dependency runs the
/// other way), so this could not live in <c>OpenWSFZ.Daemon</c> without either a second,
/// potentially-diverging copy in <c>OpenWSFZ.Web</c> or a layering violation.
/// </summary>
public static class DecodeNoiseSuppressionDefaults
{
    /// <summary>
    /// Resolves the effective (applied) value of the Unknown-region suppression setting. An
    /// explicit operator choice (<paramref name="persisted"/> is non-null) is always authoritative
    /// and is returned unchanged, regardless of region-data state. While unset (<c>null</c>), the
    /// effective value is computed from whether the active region table currently has any loaded
    /// entries — <c>false</c> (do not suppress) while empty, <c>true</c> (suppress) once at least
    /// one entry is present.
    /// </summary>
    public static bool ResolveEffectiveSuppressUnknownRegion(bool? persisted, ICallsignRegionStore regionStore) =>
        persisted ?? regionStore.Entries.Count > 0;
}
