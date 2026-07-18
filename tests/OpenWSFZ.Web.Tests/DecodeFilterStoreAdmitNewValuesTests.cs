using System.Collections.Concurrent;
using FluentAssertions;
using OpenWSFZ.Abstractions;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Unit tests for <see cref="DecodeFilterStore.AdmitNewValues"/>
/// (<c>fix-decode-filter-new-value-admission</c>, tasks 3.1-3.6). Covers first-seen admission on
/// a narrowed-but-non-empty axis, the two no-op cases (untouched <c>null</c> axis and explicitly
/// empty <c>[]</c> axis), non-re-admission of an already-seen excluded value, multi-axis
/// combination, and concurrency safety under the lock/copy-on-write discipline (design.md
/// Decision 3).
///
/// NFR-021: all callsigns/entities use synthetic or already-established test fixture names.
/// </summary>
[Trait("Category", "Unit")]
public sealed class DecodeFilterStoreAdmitNewValuesTests
{
    private static DecodeResult MakeDecode(RegionInfo? region)
        => new(
            Time:    "12:00:00",
            Snr:     0,
            Dt:      0.0,
            FreqHz:  1000,
            Message: "CQ Q1TST JO22",
            Region:  region);

    private static readonly RegionInfo Monaco =
        new(Continent: "EU", Entity: "Monaco", Synthetic: false, CqZone: 14, ItuZone: 27);

    private static readonly RegionInfo WallisAndFutuna =
        new(Continent: "OC", Entity: "Wallis and Futuna", Synthetic: false, CqZone: 32, ItuZone: 62);

    // ── 3.1 — first-seen value on a narrowed-but-non-empty axis is admitted ──────

    [Fact(DisplayName = "FR-061: 3.1: first-seen entity on a narrowed-but-non-empty AllowedEntities axis is admitted")]
    public void FirstSeenEntity_NarrowedNonEmptyAxis_IsAdmitted()
    {
        var store = new DecodeFilterStore();
        store.Set(DecodeFilterState.Unfiltered with { AllowedEntities = new HashSet<string> { "Germany" } });

        var updated = store.AdmitNewValues(MakeDecode(WallisAndFutuna));

        updated.Should().NotBeNull();
        updated!.AllowedEntities.Should().BeEquivalentTo(new[] { "Germany", "Wallis and Futuna" });
        store.Current.AllowedEntities.Should().BeEquivalentTo(new[] { "Germany", "Wallis and Futuna" });
    }

    [Fact(DisplayName = "FR-061: 3.1: first-seen continent on a narrowed-but-non-empty AllowedContinents axis is admitted")]
    public void FirstSeenContinent_NarrowedNonEmptyAxis_IsAdmitted()
    {
        var store = new DecodeFilterStore();
        store.Set(DecodeFilterState.Unfiltered with { AllowedContinents = new HashSet<string> { "EU" } });

        var updated = store.AdmitNewValues(MakeDecode(WallisAndFutuna)); // OC — never seen

        updated.Should().NotBeNull();
        updated!.AllowedContinents.Should().BeEquivalentTo(new[] { "EU", "OC" });
    }

    [Fact(DisplayName = "FR-061: 3.1: first-seen CQ zone on a narrowed-but-non-empty AllowedCqZones axis is admitted")]
    public void FirstSeenCqZone_NarrowedNonEmptyAxis_IsAdmitted()
    {
        var store = new DecodeFilterStore();
        store.Set(DecodeFilterState.Unfiltered with { AllowedCqZones = new HashSet<int> { 14 } });

        var updated = store.AdmitNewValues(MakeDecode(WallisAndFutuna)); // zone 32 — never seen

        updated.Should().NotBeNull();
        updated!.AllowedCqZones.Should().BeEquivalentTo(new[] { 14, 32 });
    }

    [Fact(DisplayName = "FR-061: 3.1: first-seen ITU zone on a narrowed-but-non-empty AllowedItuZones axis is admitted")]
    public void FirstSeenItuZone_NarrowedNonEmptyAxis_IsAdmitted()
    {
        var store = new DecodeFilterStore();
        store.Set(DecodeFilterState.Unfiltered with { AllowedItuZones = new HashSet<int> { 27 } });

        var updated = store.AdmitNewValues(MakeDecode(WallisAndFutuna)); // zone 62 — never seen

        updated.Should().NotBeNull();
        updated!.AllowedItuZones.Should().BeEquivalentTo(new[] { 27, 62 });
    }

    // ── 3.2 — untouched (null) axis is a no-op ───────────────────────────────────

    [Fact(DisplayName = "FR-061: 3.2: first-seen value on an untouched (null) axis is a no-op")]
    public void FirstSeenValue_NullAxis_IsNoOp()
    {
        var store = new DecodeFilterStore(); // Unfiltered — every axis null

        var updated = store.AdmitNewValues(MakeDecode(WallisAndFutuna));

        updated.Should().BeNull();
        store.Current.Should().Be(DecodeFilterState.Unfiltered);
    }

    // ── 3.3 — explicitly empty ([]) axis is NOT admitted into ───────────────────

    [Fact(DisplayName = "FR-061: 3.3: first-seen value on an explicitly empty ([]) axis is NOT admitted")]
    public void FirstSeenValue_ExplicitlyEmptyAxis_IsNotAdmitted()
    {
        var store = new DecodeFilterStore();
        store.Set(DecodeFilterState.Unfiltered with { AllowedEntities = new HashSet<string>() });

        var updated = store.AdmitNewValues(MakeDecode(WallisAndFutuna));

        updated.Should().BeNull();
        store.Current.AllowedEntities.Should().NotBeNull().And.BeEmpty();
    }

    // ── 3.4 — an already-seen, already-excluded value is never re-admitted ──────

    [Fact(DisplayName = "FR-061: 3.4: an already-seen, already-excluded value is never re-admitted on a later decode")]
    public void AlreadySeenExcludedValue_IsNeverReAdmitted()
    {
        var store = new DecodeFilterStore();
        // Monaco has been seen this session (first decode, unfiltered)...
        store.AdmitNewValues(MakeDecode(Monaco));
        // ...then the operator explicitly excludes it, narrowing to Germany only.
        store.Set(DecodeFilterState.Unfiltered with { AllowedEntities = new HashSet<string> { "Germany" } });

        // A further decode resolving to the already-seen, already-excluded Monaco.
        var updated = store.AdmitNewValues(MakeDecode(Monaco));

        updated.Should().BeNull();
        store.Current.AllowedEntities.Should().BeEquivalentTo(new[] { "Germany" });
    }

    // ── 3.5 — multi-axis combination ────────────────────────────────────────────

    [Fact(DisplayName = "FR-061: 3.5: a decode touching multiple axes simultaneously admits both in a single call")]
    public void DecodeTouchingMultipleAxes_AdmitsBothInSingleCall()
    {
        var store = new DecodeFilterStore();
        store.Set(DecodeFilterState.Unfiltered with
        {
            AllowedEntities = new HashSet<string> { "Germany" },
            AllowedCqZones  = new HashSet<int> { 14 },
        });

        var updated = store.AdmitNewValues(MakeDecode(WallisAndFutuna)); // new entity AND new CQ zone

        updated.Should().NotBeNull();
        updated!.AllowedEntities.Should().BeEquivalentTo(new[] { "Germany", "Wallis and Futuna" });
        updated.AllowedCqZones.Should().BeEquivalentTo(new[] { 14, 32 });
    }

    // ── 3.6 — concurrency safety ─────────────────────────────────────────────────

    [Fact(DisplayName = "FR-061: 3.6: parallel AdmitNewValues/Set calls do not corrupt state or lose an admission")]
    public async Task ParallelAdmitNewValuesAndSetCalls_DoNotCorruptStateOrLoseAdmission()
    {
        var store = new DecodeFilterStore();
        // Narrow AllowedEntities up front so every distinct entity below is a genuine admission.
        store.Set(DecodeFilterState.Unfiltered with { AllowedEntities = new HashSet<string> { "Seed" } });

        var expectedEntities = Enumerable.Range(0, 200).Select(i => $"Entity{i}").ToList();
        var seenUpdates = new ConcurrentBag<DecodeFilterState>();

        var admitTasks = expectedEntities.Select(entity => Task.Run(() =>
        {
            var region  = new RegionInfo(Continent: "EU", Entity: entity, Synthetic: false, CqZone: 14, ItuZone: 27);
            var updated = store.AdmitNewValues(MakeDecode(region));
            if (updated is not null)
                seenUpdates.Add(updated);
        }));

        // Interleave a handful of concurrent Set() calls that don't touch AllowedEntities, to
        // exercise the same lock from the other writer without disturbing the assertion below.
        var setTasks = Enumerable.Range(0, 20).Select(i => Task.Run(() =>
        {
            var current = store.Current;
            store.Set(current with { AllowedItuZones = new HashSet<int> { i } });
        }));

        await Task.WhenAll(admitTasks.Concat(setTasks));

        store.Current.AllowedEntities.Should().NotBeNull();
        store.Current.AllowedEntities!.Should().Contain(expectedEntities);
        store.Current.AllowedEntities.Should().Contain("Seed");
        store.Current.AllowedEntities!.Count.Should().Be(expectedEntities.Count + 1,
            "no admission may be lost and no duplicate/corrupted entry may appear under concurrency");
    }
}
