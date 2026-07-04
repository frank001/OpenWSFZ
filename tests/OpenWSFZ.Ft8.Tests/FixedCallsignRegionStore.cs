using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Test double for <see cref="ICallsignRegionStore"/> backed by an in-memory entry list —
/// no file I/O. Mirrors <see cref="CallsignRegionStore"/>'s longest-prefix-match lookup so
/// tests exercise the same matching semantics without touching disk.
/// </summary>
internal sealed class FixedCallsignRegionStore(IReadOnlyList<CallsignRegionEntry> entries) : ICallsignRegionStore
{
    public IReadOnlyList<CallsignRegionEntry> Entries { get; } = entries;

    public RegionInfo? TryGetRegion(string callsignToken)
    {
        if (string.IsNullOrEmpty(callsignToken)) return null;
        var token = callsignToken.ToUpperInvariant();

        CallsignRegionEntry? best = null;
        foreach (var entry in Entries)
        {
            var len = entry.PrefixStart.Length;
            if (len == 0 || entry.PrefixEnd.Length != len) continue;
            if (token.Length < len) continue;

            var candidate = token[..len];
            if (string.CompareOrdinal(candidate, entry.PrefixStart) < 0 ||
                string.CompareOrdinal(candidate, entry.PrefixEnd) > 0)
                continue;

            if (best is null || len > best.PrefixStart.Length)
                best = entry;
        }

        return best is null ? null : new RegionInfo(best.Continent, best.Entity, best.Synthetic);
    }
}

/// <summary>
/// Test double for <see cref="ICallsignRegionStore"/> that always throws — used to verify
/// that a region-resolution failure degrades to <c>Region = null</c> ("Unknown") and never
/// withholds the underlying decode (region-lookup capability's "advisory only" requirement).
/// </summary>
internal sealed class ThrowingCallsignRegionStore : ICallsignRegionStore
{
    public IReadOnlyList<CallsignRegionEntry> Entries => [];

    public RegionInfo? TryGetRegion(string callsignToken)
        => throw new InvalidOperationException("Simulated region-lookup failure.");
}
