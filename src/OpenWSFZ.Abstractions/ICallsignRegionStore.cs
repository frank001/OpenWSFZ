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
