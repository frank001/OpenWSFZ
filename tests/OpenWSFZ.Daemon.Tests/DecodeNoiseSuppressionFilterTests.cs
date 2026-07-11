using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="DecodeNoiseSuppressionFilter"/> (<c>decode-noise-suppression</c>
/// capability, tasks 6.1–6.3). Uses a local, in-memory <see cref="ICallsignRegionStore"/> test
/// double (<see cref="StubRegionStore"/>) with a settable entry count, mirroring
/// <c>WorkedBeforeIndexTests.FixedRegionStore</c>'s pattern but mutable, so the region-data-
/// presence default-resolution tests (task 6.2) can flip "no data" → "data present" mid-test.
///
/// NFR-021: all callsigns in test data use the ITU-unallocated Q-prefix.
/// </summary>
[Trait("Category", "Unit")]
public sealed class DecodeNoiseSuppressionFilterTests
{
    // ── Helpers ───────────────────────────────────────────────────────────────

    private static readonly RegionInfo RealRegion = new("EU", "Monaco", Synthetic: false, CqZone: 14, ItuZone: 27);
    private static readonly RegionInfo SyntheticRegion = new(null, "Synthetic (R&R Study)", Synthetic: true);

    private static DecodeResult MakeDecode(string message, RegionInfo? region) =>
        new(Time: "12:00:00", Snr: 0, Dt: 0.0, FreqHz: 1000, Message: message, Region: region);

    private static DecodeNoiseSuppressionConfig Config(bool? suppressUnknownRegion, bool suppressSynthetic) =>
        new(suppressUnknownRegion, suppressSynthetic);

    /// <summary>Minimal <see cref="ICallsignRegionStore"/> test double with a settable entry count.</summary>
    private sealed class StubRegionStore : ICallsignRegionStore
    {
        public List<CallsignRegionEntry> EntryList { get; } = [];

        public IReadOnlyList<CallsignRegionEntry> Entries => EntryList;

        public RegionInfo? TryGetRegion(string callsignToken) => throw new NotSupportedException();

        public Task SaveAsync(IReadOnlyList<CallsignRegionEntry> entries, CancellationToken cancellationToken = default) =>
            throw new NotSupportedException();
    }

    private static CallsignRegionEntry MakeEntry() =>
        new("Q0AA", "Q0ZZ", "Testland", "TA", 14, 27);

    // ── Task 6.1: suppression predicate ──────────────────────────────────────

    [Fact(DisplayName = "decode-noise-suppression: null-region decode is suppressed when SuppressUnknownRegion is explicitly true")]
    public void Apply_SuppressesNullRegionDecode_WhenExplicitlyEnabled()
    {
        var decode = MakeDecode("CQ Q1TST JO22", region: null);
        var result = DecodeNoiseSuppressionFilter.Apply(
            [decode], Config(suppressUnknownRegion: true, suppressSynthetic: false), new StubRegionStore());

        result.Should().BeEmpty();
    }

    [Fact(DisplayName = "decode-noise-suppression: null-region decode passes through when SuppressUnknownRegion is explicitly false")]
    public void Apply_PassesNullRegionDecode_WhenExplicitlyDisabled()
    {
        var decode = MakeDecode("CQ Q1TST JO22", region: null);
        var result = DecodeNoiseSuppressionFilter.Apply(
            [decode], Config(suppressUnknownRegion: false, suppressSynthetic: false), new StubRegionStore());

        result.Should().ContainSingle().Which.Should().Be(decode);
    }

    [Fact(DisplayName = "decode-noise-suppression: Region.Synthetic decode is suppressed when SuppressSynthetic is true")]
    public void Apply_SuppressesSyntheticDecode_WhenEnabled()
    {
        var decode = MakeDecode("CQ QS1TST JO22", region: SyntheticRegion);
        var result = DecodeNoiseSuppressionFilter.Apply(
            [decode], Config(suppressUnknownRegion: false, suppressSynthetic: true), new StubRegionStore());

        result.Should().BeEmpty();
    }

    [Fact(DisplayName = "decode-noise-suppression: Region.Synthetic decode passes through when SuppressSynthetic is false")]
    public void Apply_PassesSyntheticDecode_WhenDisabled()
    {
        var decode = MakeDecode("CQ QS1TST JO22", region: SyntheticRegion);
        var result = DecodeNoiseSuppressionFilter.Apply(
            [decode], Config(suppressUnknownRegion: false, suppressSynthetic: false), new StubRegionStore());

        result.Should().ContainSingle().Which.Should().Be(decode);
    }

    [Fact(DisplayName = "decode-noise-suppression: a decode matching neither rule always passes through")]
    public void Apply_PassesRealResolvedDecode_RegardlessOfSettings()
    {
        var decode = MakeDecode("CQ Q1TST JO22", region: RealRegion);

        foreach (var suppressUnknown in new[] { true, false })
        foreach (var suppressSynthetic in new[] { true, false })
        {
            var result = DecodeNoiseSuppressionFilter.Apply(
                [decode], Config(suppressUnknown, suppressSynthetic), new StubRegionStore());
            result.Should().ContainSingle().Which.Should().Be(decode);
        }
    }

    [Fact(DisplayName = "decode-noise-suppression: both rules active simultaneously correctly filter a mixed batch")]
    public void Apply_BothRulesActive_FiltersMixedBatchCorrectly()
    {
        var unknownDecode   = MakeDecode("CQ Q1AAA JO22", region: null);
        var syntheticDecode = MakeDecode("CQ QS1AAA JO22", region: SyntheticRegion);
        var realDecode      = MakeDecode("CQ Q1BBB JO22", region: RealRegion);

        var result = DecodeNoiseSuppressionFilter.Apply(
            [unknownDecode, syntheticDecode, realDecode],
            Config(suppressUnknownRegion: true, suppressSynthetic: true),
            new StubRegionStore());

        result.Should().ContainSingle().Which.Should().Be(realDecode);
    }

    // ── Task 6.2: Unknown-setting default resolution ─────────────────────────

    [Fact(DisplayName = "decode-noise-suppression: unset + empty region table -> not suppressed")]
    public void ResolveEffectiveSuppressUnknownRegion_UnsetAndEmptyTable_NotSuppressed()
    {
        var store = new StubRegionStore();
        DecodeNoiseSuppressionFilter.ResolveEffectiveSuppressUnknownRegion(null, store).Should().BeFalse();
    }

    [Fact(DisplayName = "decode-noise-suppression: unset + populated region table -> suppressed")]
    public void ResolveEffectiveSuppressUnknownRegion_UnsetAndPopulatedTable_Suppressed()
    {
        var store = new StubRegionStore();
        store.EntryList.Add(MakeEntry());
        DecodeNoiseSuppressionFilter.ResolveEffectiveSuppressUnknownRegion(null, store).Should().BeTrue();
    }

    [Theory(DisplayName = "decode-noise-suppression: an explicit choice is honored regardless of region-table state")]
    [InlineData(true, 0)]
    [InlineData(true, 1)]
    [InlineData(false, 0)]
    [InlineData(false, 1)]
    public void ResolveEffectiveSuppressUnknownRegion_ExplicitChoice_HonoredRegardlessOfTableState(
        bool explicitChoice, int entryCount)
    {
        var store = new StubRegionStore();
        for (var i = 0; i < entryCount; i++) store.EntryList.Add(MakeEntry());

        DecodeNoiseSuppressionFilter.ResolveEffectiveSuppressUnknownRegion(explicitChoice, store)
            .Should().Be(explicitChoice);
    }

    [Fact(DisplayName = "decode-noise-suppression: an explicit choice made before data exists is still honored after data is later loaded")]
    public void ResolveEffectiveSuppressUnknownRegion_ExplicitChoiceBeforeData_StillHonoredAfterDataLoads()
    {
        var store = new StubRegionStore();

        // Operator explicitly disabled suppression while the table was still empty.
        DecodeNoiseSuppressionFilter.ResolveEffectiveSuppressUnknownRegion(false, store).Should().BeFalse();

        // A region-data refresh later populates the table — the explicit choice must not flip.
        store.EntryList.Add(MakeEntry());
        DecodeNoiseSuppressionFilter.ResolveEffectiveSuppressUnknownRegion(false, store).Should().BeFalse(
            "an explicit operator choice must never be silently recomputed from region-data presence");
    }

    // ── Task 6.3: ALL.TXT / decode-panel divergence (narrowest feasible seam) ───
    //
    // Program.cs's decode-pump loop passes the *unfiltered* `results` list to
    // `allTxtWriter.AppendAsync` and this filter's *output* to the decode-panel broadcast and
    // both QSO-controller channels (design.md Decision 1). Program.cs itself (top-level
    // statements) isn't unit-testable directly, so this test proves the underlying contract that
    // makes that wiring correct: `Apply` never mutates its input and its output can omit
    // decodes still present in the original list.

    [Fact(DisplayName = "decode-noise-suppression: ALL.TXT's unfiltered input retains a decode the panel/QSO-controller output omits")]
    public void Apply_UnfilteredInputRetainsSuppressedDecode_ThatFilteredOutputOmits()
    {
        var suppressedDecode = MakeDecode("CQ Q1AAA JO22", region: null);
        var visibleDecode    = MakeDecode("CQ Q1BBB JO22", region: RealRegion);
        IReadOnlyList<DecodeResult> results = [suppressedDecode, visibleDecode];

        var visibleResults = DecodeNoiseSuppressionFilter.Apply(
            results, Config(suppressUnknownRegion: true, suppressSynthetic: false), new StubRegionStore());

        // The exact same `results` reference/contents that ALL.TXT receives (Program.cs passes
        // `results`, not `visibleResults`, to allTxtWriter.AppendAsync) still contains the
        // suppressed decode — proving ALL.TXT is never filtered.
        results.Should().Contain(suppressedDecode);
        results.Should().HaveCount(2, "Apply must never mutate its input list");

        // The filtered output — what the panel broadcast and QSO-controller batches actually
        // receive — omits it.
        visibleResults.Should().NotContain(suppressedDecode);
        visibleResults.Should().ContainSingle().Which.Should().Be(visibleDecode);
    }

    [Fact(DisplayName = "decode-noise-suppression: Apply returns the same list instance when nothing is suppressed (fast path)")]
    public void Apply_ReturnsSameInstance_WhenNothingSuppressed()
    {
        IReadOnlyList<DecodeResult> results = [MakeDecode("CQ Q1AAA JO22", region: RealRegion)];

        var visibleResults = DecodeNoiseSuppressionFilter.Apply(
            results, Config(suppressUnknownRegion: false, suppressSynthetic: false), new StubRegionStore());

        visibleResults.Should().BeSameAs(results);
    }
}
