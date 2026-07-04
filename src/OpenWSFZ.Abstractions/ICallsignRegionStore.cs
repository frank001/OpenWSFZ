namespace OpenWSFZ.Abstractions;

/// <summary>
/// In-process store for the advisory callsign region lookup table
/// (<c>callsign-regions.json</c>). Loaded at startup; mirrors the
/// <see cref="IFrequencyStore"/> pattern. A lookup miss, a missing file, or a
/// malformed file all degrade to "no match" (rendered as <c>"Unknown"</c> by the
/// frontend) and never affect decode accept/reject decisions
/// (<c>region-lookup</c> capability).
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
}
