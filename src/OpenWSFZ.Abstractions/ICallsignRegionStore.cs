namespace OpenWSFZ.Abstractions;

/// <summary>
/// In-process store for the advisory callsign region lookup table
/// (<c>callsign-regions.json</c>). Loaded at startup; mirrors the
/// <see cref="IFrequencyStore"/> pattern. A lookup miss, a missing file, or a
/// malformed file all degrade to "no match" (rendered as <c>"Unknown"</c> by the
/// frontend) and never affect decode accept/reject decisions
/// (<c>region-lookup</c> capability).
/// <para>
/// Resolution here is unmodified by, and unaware of, the <c>decode-noise-suppression</c>
/// capability — <see cref="TryGetRegion"/> still resolves and returns exactly as documented below
/// for every decode. That capability's <c>DecodeNoiseSuppressionFilter</c> is a separate,
/// operator-opt-in stage layered on <em>after</em> resolution, in the daemon's decode-pump loop,
/// that may withhold an already-resolved (or already-unresolved) decode from the decode panel and
/// QSO automation. If a future reader lands here expecting every resolution to always reach the
/// UI, see that filter's doc comment for the deliberate, operator-controlled exception.
/// </para>
/// </summary>
public interface ICallsignRegionStore
{
    /// <summary>The current in-memory region table.</summary>
    IReadOnlyList<CallsignRegionEntry> Entries { get; }

    /// <summary>
    /// Resolves the region for <paramref name="callsignToken"/> (the base callsign,
    /// before any portable suffix) against <see cref="Entries"/>, preferring the
    /// longest (most specific) matching prefix range.
    /// </summary>
    /// <returns>
    /// The matching <see cref="RegionInfo"/>, or <c>null</c> on a lookup miss
    /// (rendered as <c>"Unknown"</c> by the frontend).
    /// </returns>
    RegionInfo? TryGetRegion(string callsignToken);

    /// <summary>
    /// Resolves the longest matching region-store prefix for <paramref name="callsignToken"/>,
    /// returning both the matched <see cref="RegionInfo"/> and the length of the matched prefix
    /// range. <see cref="TryGetRegion"/> is a thin wrapper over this method
    /// (<c>TryMatchPrefix(token)?.Region</c>) — there is exactly one longest-prefix-match
    /// implementation, so the two methods can never disagree on which entry matched.
    /// <c>engagement-target-validation</c> uses the matched-prefix length to determine where a
    /// match ends within the token, so the remainder can be validated against
    /// <see cref="ICallsignGrammarStore"/>'s digit-run/suffix rules.
    /// </summary>
    /// <returns>
    /// The matched <see cref="CallsignRegionMatch"/>, or <c>null</c> on a lookup miss — identical
    /// miss semantics to <see cref="TryGetRegion"/>.
    /// </returns>
    CallsignRegionMatch? TryMatchPrefix(string callsignToken);

    /// <summary>
    /// <c>true</c> when <see cref="Entries"/> still holds only the compiled-in seed table
    /// (<c>CallsignRegionDefaults.Entries</c>) — i.e. no on-disk <c>callsign-regions.json</c> has
    /// ever been successfully loaded at startup, and no operator-triggered region-data refresh
    /// (<see cref="SaveAsync"/>) has ever succeeded this session. <c>false</c> once either happens.
    /// Consulted by <c>engagement-target-validation</c> so its gate no-ops entirely while only
    /// seed data is loaded — the seed table is intentionally partial (39 entries) and must never
    /// itself become a source of engagement rejections.
    /// </summary>
    bool IsSeedData { get; }

    /// <summary>
    /// Replaces the in-memory region table and persists the new list to
    /// <c>callsign-regions.json</c> atomically (write-to-temp-then-rename), without requiring a
    /// daemon restart (region-lookup-data-refresh capability). Mirrors
    /// <see cref="IFrequencyStore.SaveAsync"/>'s contract exactly. <see cref="Entries"/> is updated
    /// only after a successful file write — a failed write leaves the previous in-memory table and
    /// on-disk file unchanged. An in-flight <see cref="TryGetRegion"/> call observes either the
    /// complete old table or the complete new table, never a partial one.
    /// </summary>
    Task SaveAsync(IReadOnlyList<CallsignRegionEntry> entries, CancellationToken cancellationToken = default);
}
