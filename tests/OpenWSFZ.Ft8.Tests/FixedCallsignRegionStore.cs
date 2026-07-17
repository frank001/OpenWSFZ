using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Test double for <see cref="ICallsignRegionStore"/> backed by an in-memory entry list —
/// no file I/O. Mirrors <see cref="CallsignRegionStore"/>'s longest-prefix-match lookup so
/// tests exercise the same matching semantics without touching disk.
/// </summary>
internal sealed class FixedCallsignRegionStore : ICallsignRegionStore
{
    private IReadOnlyList<CallsignRegionEntry> _entries;

    /// <summary>
    /// engagement-target-validation: defaults to <c>false</c> (real data) since every existing
    /// caller of this constructor is explicitly supplying a fixed entry list, not the compiled-in
    /// seed table — matches this double's overall "caller controls exactly what's loaded" contract.
    /// Settable via <see cref="IsSeedData"/>'s init-only-by-convention backing field through the
    /// second constructor overload for tests that specifically need to exercise the seed-data no-op.
    /// </summary>
    private bool _isSeedData;

    public FixedCallsignRegionStore(IReadOnlyList<CallsignRegionEntry> entries) => _entries = entries;

    public FixedCallsignRegionStore(IReadOnlyList<CallsignRegionEntry> entries, bool isSeedData)
    {
        _entries    = entries;
        _isSeedData = isSeedData;
    }

    public IReadOnlyList<CallsignRegionEntry> Entries => _entries;

    public bool IsSeedData => _isSeedData;

    public RegionInfo? TryGetRegion(string callsignToken) => TryMatchPrefix(callsignToken)?.Region;

    public CallsignRegionMatch? TryMatchPrefix(string callsignToken)
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

        if (best is null) return null;
        var region = new RegionInfo(best.Continent, best.Entity, best.Synthetic, best.CqZone, best.ItuZone);
        return new CallsignRegionMatch(region, best.PrefixStart.Length);
    }

    /// <summary>
    /// region-lookup-data-refresh (f-006): a trivial, fully-functional in-memory implementation —
    /// no file I/O, matching this test double's overall no-disk contract. Replaces
    /// <see cref="Entries"/> immediately (no atomicity concerns without a backing file).
    /// </summary>
    public Task SaveAsync(IReadOnlyList<CallsignRegionEntry> entries, CancellationToken cancellationToken = default)
    {
        _entries    = entries;
        _isSeedData = false; // engagement-target-validation: a successful save is real data.
        return Task.CompletedTask;
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

    public bool IsSeedData => false;

    public RegionInfo? TryGetRegion(string callsignToken)
        => throw new InvalidOperationException("Simulated region-lookup failure.");

    public CallsignRegionMatch? TryMatchPrefix(string callsignToken)
        => throw new InvalidOperationException("Simulated region-lookup failure.");

    public Task SaveAsync(IReadOnlyList<CallsignRegionEntry> entries, CancellationToken cancellationToken = default)
        => throw new InvalidOperationException("Simulated region-lookup failure.");
}
