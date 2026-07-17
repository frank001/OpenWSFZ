using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using NSubstitute;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="WorkedBeforeIndex"/> (<c>qso-confirmation</c> capability, tasks
/// 1.3–1.5/1.7; band-awareness added by <c>qso-confirmation-band-awareness</c>, task 3.6). Uses
/// a local, in-memory <see cref="ICallsignRegionStore"/> test double (mirroring
/// <c>OpenWSFZ.Ft8.Tests.FixedCallsignRegionStore</c>) so region resolution is fully controlled
/// without touching disk.
///
/// NFR-021: all callsigns use the ITU-unallocated Q-prefix.
/// </summary>
[Trait("Category", "Unit")]
public sealed class WorkedBeforeIndexTests : IDisposable
{
    private readonly string _tempDir;

    public WorkedBeforeIndexTests()
    {
        _tempDir = Path.Combine(
            Path.GetTempPath(),
            "openwsfz-workedbefore-test-" + Path.GetRandomFileName());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        try { Directory.Delete(_tempDir, recursive: true); } catch { /* best-effort */ }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private string AdifPath => Path.Combine(_tempDir, "ADIF.log");

    /// <summary>Writes one ADIF record per (callsign, band) pair. A null band omits the &lt;band:N&gt; tag.</summary>
    private void WriteAdifFixture(params (string Call, string? Band)[] records)
    {
        var lines = records.Select(r =>
            r.Band is null
                ? $"<call:{r.Call.Length}>{r.Call}<eor>"
                : $"<call:{r.Call.Length}>{r.Call}<band:{r.Band.Length}>{r.Band}<eor>");
        File.WriteAllLines(AdifPath, lines);
    }

    private IConfigStore MakeConfigStore()
    {
        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with
        {
            DecodeLog = new DecodeLogConfig
            {
                Enabled = true,
                Path    = Path.Combine(_tempDir, "ALL.TXT"),
            }
        });
        return store;
    }

    /// <summary>Fixed test region table: Q1x → "Testland Alpha"/"TA"/CQ14/ITU27;
    /// Q2x → "Testland Beta"/"TA"/CQ14/ITU27; Q3x → "Testland Gamma"/"TG"/CQ20/ITU30;
    /// QSx → the synthetic entry.</summary>
    private static ICallsignRegionStore MakeRegionStore() => new FixedRegionStore();

    private static WorkedBeforeIndex MakeSut(IConfigStore configStore, ICallsignRegionStore? regionStore = null)
        => new(configStore, regionStore ?? MakeRegionStore(), NullLogger<WorkedBeforeIndex>.Instance);

    // ── Exact-callsign / portable-suffix match, band-aware (task 3.6) ──────────

    [Fact(DisplayName = "3.6: never worked resolves Contact = Never")]
    public async Task Resolve_UnrelatedCallsign_ContactNever()
    {
        WriteAdifFixture(("Q1TST", "40m"));
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        sut.Resolve("Q2ABC", "40m").Contact.Should().Be(WorkedBeforeState.Never);
    }

    [Fact(DisplayName = "3.6: worked on a different band resolves Contact = DifferentBand")]
    public async Task Resolve_ExactCallsignDifferentBand_ContactDifferentBand()
    {
        WriteAdifFixture(("Q1TST", "40m"));
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        sut.Resolve("Q1TST", "20m").Contact.Should().Be(WorkedBeforeState.DifferentBand);
    }

    [Fact(DisplayName = "3.6: worked on the current band resolves Contact = ThisBand")]
    public async Task Resolve_ExactCallsignSameBand_ContactThisBand()
    {
        WriteAdifFixture(("Q1TST", "20m"));
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        sut.Resolve("Q1TST", "20m").Contact.Should().Be(WorkedBeforeState.ThisBand);
    }

    [Fact(DisplayName = "3.6: worked on both the current band and another band — ThisBand wins")]
    public async Task Resolve_WorkedBothBands_ThisBandWins()
    {
        WriteAdifFixture(("Q1TST", "40m"), ("Q1TST", "20m"));
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        sut.Resolve("Q1TST", "20m").Contact.Should().Be(WorkedBeforeState.ThisBand);
    }

    [Fact(DisplayName = "3.6: currentBand null degrades ThisBand to DifferentBand, never ThisBand")]
    public async Task Resolve_CurrentBandNull_NeverThisBand()
    {
        WriteAdifFixture(("Q1TST", "20m"));
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        sut.Resolve("Q1TST", null).Contact.Should().Be(WorkedBeforeState.DifferentBand);
    }

    [Fact(DisplayName = "3.6: an unknown-band historical record contributes to 'ever' but never to ThisBand")]
    public async Task Resolve_UnknownBandHistoricalRecord_DifferentBandAtBest()
    {
        WriteAdifFixture(("Q1TST", null)); // pre-D-013-style record, no BAND
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        var result = sut.Resolve("Q1TST", "20m");

        result.Contact.Should().Be(WorkedBeforeState.DifferentBand,
            "a record with no known band can never itself justify ThisBand");
    }

    [Fact(DisplayName = "3.6: portable-suffixed decode token matches a plain historical log entry, band-aware")]
    public async Task Resolve_PortableSuffixedToken_MatchesPlainHistoricalEntry()
    {
        WriteAdifFixture(("Q1TST", "20m"));
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        sut.Resolve("Q1TST/P", "20m").Contact.Should().Be(WorkedBeforeState.ThisBand);
    }

    [Fact(DisplayName = "3.6: plain decode token matches a portable-suffixed historical log entry, band-aware")]
    public async Task Resolve_PlainToken_MatchesPortableSuffixedHistoricalEntry()
    {
        WriteAdifFixture(("Q1TST/P", "40m"));
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        sut.Resolve("Q1TST", "20m").Contact.Should().Be(WorkedBeforeState.DifferentBand);
    }

    // ── Country / Continent / CQ Zone / ITU Zone matching, band-aware ──────────

    [Fact(DisplayName = "3.6: country match with a different callsign, same DXCC entity, band-aware")]
    public async Task Resolve_DifferentCallsignSameEntity_CountryBandAware()
    {
        WriteAdifFixture(("Q1AAA", "20m")); // resolves to "Testland Alpha"
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        var result = sut.Resolve("Q1ZZZ", "20m"); // different call, same "Q1" entity prefix

        result.Contact.Should().Be(WorkedBeforeState.Never, "different callsign, never logged");
        result.Country.Should().Be(WorkedBeforeState.ThisBand, "same DXCC entity, worked on the current band");
    }

    [Fact(DisplayName = "3.6: continent match with a different country, different band")]
    public async Task Resolve_DifferentCountrySameContinent_ContinentDifferentBandCountryNever()
    {
        WriteAdifFixture(("Q2AAA", "40m")); // "Testland Beta", continent "TA"
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        var result = sut.Resolve("Q1AAA", "20m"); // "Testland Alpha", continent "TA" — different entity, same continent

        result.Country.Should().Be(WorkedBeforeState.Never, "different DXCC entity");
        result.Continent.Should().Be(WorkedBeforeState.DifferentBand, "same continent, worked only on a different band");
    }

    [Fact(DisplayName = "3.6: CQ Zone match, band-aware (new axis)")]
    public async Task Resolve_SameCqZone_ThisBand()
    {
        WriteAdifFixture(("Q1AAA", "20m")); // CQ zone 14
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        sut.Resolve("Q2ZZZ", "20m").CqZone.Should().Be(WorkedBeforeState.ThisBand, "Q2x also resolves CQ zone 14");
    }

    [Fact(DisplayName = "3.6: ITU Zone match, different band (new axis)")]
    public async Task Resolve_SameItuZone_DifferentBand()
    {
        WriteAdifFixture(("Q1AAA", "40m")); // ITU zone 27
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        sut.Resolve("Q2ZZZ", "20m").ItuZone.Should().Be(WorkedBeforeState.DifferentBand, "Q2x also resolves ITU zone 27");
    }

    [Fact(DisplayName = "3.6: two distinct unresolved (\"Unknown\") callsigns never co-match")]
    public async Task Resolve_TwoUnresolvedCallsigns_NeverCoMatch()
    {
        WriteAdifFixture(("ZZ1AAA", "20m")); // no region-store entry covers "ZZ" prefix
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        var result = sut.Resolve("ZZ2BBB", "20m"); // also unresolved

        result.Country.Should().Be(WorkedBeforeState.Never, "two unresolved callsigns are not known to share anything");
        result.Continent.Should().Be(WorkedBeforeState.Never);
        result.CqZone.Should().Be(WorkedBeforeState.Never);
        result.ItuZone.Should().Be(WorkedBeforeState.Never);
    }

    [Fact(DisplayName = "3.6: a synthetic-resolved historical entry never causes a real decode to match")]
    public async Task Resolve_SyntheticHistoricalEntry_NeverMatchesRealDecode()
    {
        WriteAdifFixture(("QSABC", "20m")); // resolves to the synthetic entry
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        var result = sut.Resolve("Q1AAA", "20m"); // real, resolvable entity

        result.Country.Should().Be(WorkedBeforeState.Never);
        result.Continent.Should().Be(WorkedBeforeState.Never);
    }

    [Fact(DisplayName = "3.6: a synthetic-resolved decode itself always resolves Never on country/continent regardless of index content")]
    public async Task Resolve_SyntheticDecode_AlwaysNeverCountryContinent()
    {
        WriteAdifFixture(("Q1AAA", "20m"), ("Q1BBB", "20m")); // plenty of real "Testland Alpha" history
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        var result = sut.Resolve("QSXYZ", "20m"); // synthetic decode

        result.Country.Should().Be(WorkedBeforeState.Never);
        result.Continent.Should().Be(WorkedBeforeState.Never);
    }

    [Fact(DisplayName = "3.6: empty index (no ADIF.log) resolves all five axes Never")]
    public async Task Resolve_EmptyIndex_AllFiveNever()
    {
        // No ADIF.log written at all.
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        var result = sut.Resolve("Q1AAA", "20m");

        result.Contact.Should().Be(WorkedBeforeState.Never);
        result.Country.Should().Be(WorkedBeforeState.Never);
        result.Continent.Should().Be(WorkedBeforeState.Never);
        result.CqZone.Should().Be(WorkedBeforeState.Never);
        result.ItuZone.Should().Be(WorkedBeforeState.Never);
    }

    // ── Register (live update, design.md Decision 5) ───────────────────────────

    [Fact(DisplayName = "3.6: Register makes a mid-session QSO immediately resolvable without a reload, band-correct")]
    public async Task Register_NewCallsign_ImmediatelyResolvableBandCorrect()
    {
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync(); // empty index

        sut.Resolve("Q1TST", "20m").Contact.Should().Be(WorkedBeforeState.Never);

        sut.Register("Q1TST", "20m");

        sut.Resolve("Q1TST", "20m").Contact.Should().Be(WorkedBeforeState.ThisBand);
        sut.Resolve("Q1TST", "40m").Contact.Should().Be(WorkedBeforeState.DifferentBand);
    }

    [Fact(DisplayName = "3.6: Register with a null band still marks the callsign worked, but never ThisBand")]
    public async Task Register_NullBand_WorkedButNeverThisBand()
    {
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        sut.Register("Q1TST", null);

        sut.Resolve("Q1TST", "20m").Contact.Should().Be(WorkedBeforeState.DifferentBand);
    }

    // ── Test double ──────────────────────────────────────────────────────────

    /// <summary>
    /// Minimal fixed <see cref="ICallsignRegionStore"/> for these tests: Q1x → "Testland Alpha"
    /// (continent "TA", CQ zone 14, ITU zone 27); Q2x → "Testland Beta" (continent "TA", CQ zone
    /// 14, ITU zone 27); Q3x → "Testland Gamma" (continent "TG", CQ zone 20, ITU zone 30);
    /// QSx → the synthetic entry. Everything else is unresolved.
    /// </summary>
    private sealed class FixedRegionStore : ICallsignRegionStore
    {
        public IReadOnlyList<CallsignRegionEntry> Entries { get; } = [];
        public bool IsSeedData => false;

        public RegionInfo? TryGetRegion(string callsignToken)
        {
            if (callsignToken.StartsWith("Q1", StringComparison.Ordinal))
                return new RegionInfo("TA", "Testland Alpha", Synthetic: false, CqZone: 14, ItuZone: 27);
            if (callsignToken.StartsWith("Q2", StringComparison.Ordinal))
                return new RegionInfo("TA", "Testland Beta", Synthetic: false, CqZone: 14, ItuZone: 27);
            if (callsignToken.StartsWith("Q3", StringComparison.Ordinal))
                return new RegionInfo("TG", "Testland Gamma", Synthetic: false, CqZone: 20, ItuZone: 30);
            if (callsignToken.StartsWith("QS", StringComparison.Ordinal))
                return new RegionInfo(null, "Synthetic (R&R Study)", Synthetic: true);
            return null;
        }

        public CallsignRegionMatch? TryMatchPrefix(string callsignToken)
            => TryGetRegion(callsignToken) is { } region ? new CallsignRegionMatch(region, 2) : null;

        public Task SaveAsync(IReadOnlyList<CallsignRegionEntry> entries, CancellationToken cancellationToken = default)
            => throw new NotSupportedException();
    }
}
