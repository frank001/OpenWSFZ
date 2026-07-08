using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using NSubstitute;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="WorkedBeforeIndex"/> (<c>qso-confirmation</c> capability, tasks
/// 1.3–1.5/1.7). Uses a local, in-memory <see cref="ICallsignRegionStore"/> test double
/// (mirroring <c>OpenWSFZ.Ft8.Tests.FixedCallsignRegionStore</c>) so region resolution is fully
/// controlled without touching disk.
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

    private void WriteAdifFixture(params string[] callsigns)
    {
        var lines = callsigns.Select(c => $"<call:{c.Length}>{c}<eor>");
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

    /// <summary>Fixed test region table: Q1x → "Testland Alpha"/"TA"; Q2x → "Testland Beta"/"TA";
    /// Q3x → "Testland Gamma"/"TG"; QSx → the synthetic entry.</summary>
    private static ICallsignRegionStore MakeRegionStore() => new FixedRegionStore();

    private static WorkedBeforeIndex MakeSut(IConfigStore configStore, ICallsignRegionStore? regionStore = null)
        => new(configStore, regionStore ?? MakeRegionStore(), NullLogger<WorkedBeforeIndex>.Instance);

    // ── Exact-callsign / portable-suffix match (task 1.5) ──────────────────────

    [Fact(DisplayName = "1.7: exact-callsign match resolves Call true")]
    public async Task Resolve_ExactCallsignLoggedBefore_CallTrue()
    {
        WriteAdifFixture("Q1TST");
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        sut.Resolve("Q1TST").Call.Should().BeTrue();
    }

    [Fact(DisplayName = "1.7: portable-suffixed decode token matches a plain historical log entry")]
    public async Task Resolve_PortableSuffixedToken_MatchesPlainHistoricalEntry()
    {
        WriteAdifFixture("Q1TST");
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        sut.Resolve("Q1TST/P").Call.Should().BeTrue();
    }

    [Fact(DisplayName = "1.7: plain decode token matches a portable-suffixed historical log entry")]
    public async Task Resolve_PlainToken_MatchesPortableSuffixedHistoricalEntry()
    {
        WriteAdifFixture("Q1TST/P");
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        sut.Resolve("Q1TST").Call.Should().BeTrue();
    }

    [Fact(DisplayName = "1.7: unrelated callsign never logged before resolves Call false")]
    public async Task Resolve_UnrelatedCallsign_CallFalse()
    {
        WriteAdifFixture("Q1TST");
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        sut.Resolve("Q2ABC").Call.Should().BeFalse();
    }

    // ── Country / Region matching (design.md Decision 4) ───────────────────────

    [Fact(DisplayName = "1.7: country match with a different callsign, same DXCC entity")]
    public async Task Resolve_DifferentCallsignSameEntity_CountryTrue()
    {
        WriteAdifFixture("Q1AAA"); // resolves to "Testland Alpha"
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        var result = sut.Resolve("Q1ZZZ"); // different call, same "Q1" entity prefix

        result.Call.Should().BeFalse("different callsign, never logged");
        result.Country.Should().BeTrue("same DXCC entity has been logged before");
    }

    [Fact(DisplayName = "1.7: region match with a different country, same continent")]
    public async Task Resolve_DifferentCountrySameContinent_RegionTrueCountryFalse()
    {
        WriteAdifFixture("Q2AAA"); // "Testland Beta", continent "TA"
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        var result = sut.Resolve("Q1AAA"); // "Testland Alpha", continent "TA" — different entity, same continent

        result.Country.Should().BeFalse("different DXCC entity");
        result.Region.Should().BeTrue("same continent has been logged before");
    }

    [Fact(DisplayName = "1.7: two distinct unresolved (\"Unknown\") callsigns never co-match")]
    public async Task Resolve_TwoUnresolvedCallsigns_NeverCoMatch()
    {
        WriteAdifFixture("ZZ1AAA"); // no region-store entry covers "ZZ" prefix
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        var result = sut.Resolve("ZZ2BBB"); // also unresolved

        result.Country.Should().BeFalse("two unresolved callsigns are not known to share anything");
        result.Region.Should().BeFalse();
    }

    [Fact(DisplayName = "1.7: a synthetic-resolved historical entry never causes a real decode to match")]
    public async Task Resolve_SyntheticHistoricalEntry_NeverMatchesRealDecode()
    {
        WriteAdifFixture("QSABC"); // resolves to the synthetic entry
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        var result = sut.Resolve("Q1AAA"); // real, resolvable entity

        result.Country.Should().BeFalse();
        result.Region.Should().BeFalse();
    }

    [Fact(DisplayName = "1.7: a synthetic-resolved decode itself always resolves false on country/region regardless of index content")]
    public async Task Resolve_SyntheticDecode_AlwaysFalseCountryRegion()
    {
        WriteAdifFixture("Q1AAA", "Q1BBB"); // plenty of real "Testland Alpha" history
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        var result = sut.Resolve("QSXYZ"); // synthetic decode

        result.Country.Should().BeFalse();
        result.Region.Should().BeFalse();
    }

    [Fact(DisplayName = "1.7: empty index (no ADIF.log) resolves all three false")]
    public async Task Resolve_EmptyIndex_AllThreeFalse()
    {
        // No ADIF.log written at all.
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync();

        var result = sut.Resolve("Q1AAA");

        result.Call.Should().BeFalse();
        result.Country.Should().BeFalse();
        result.Region.Should().BeFalse();
    }

    // ── Register (live update, design.md Decision 5) ───────────────────────────

    [Fact(DisplayName = "1.7: Register makes a mid-session QSO immediately resolvable without a reload")]
    public async Task Register_NewCallsign_ImmediatelyResolvable()
    {
        var sut = MakeSut(MakeConfigStore());
        await sut.LoadAsync(); // empty index

        sut.Resolve("Q1TST").Call.Should().BeFalse();

        sut.Register("Q1TST");

        sut.Resolve("Q1TST").Call.Should().BeTrue();
    }

    // ── Test double ──────────────────────────────────────────────────────────

    /// <summary>
    /// Minimal fixed <see cref="ICallsignRegionStore"/> for these tests: Q1x → "Testland Alpha"
    /// (continent "TA"); Q2x → "Testland Beta" (continent "TA"); Q3x → "Testland Gamma"
    /// (continent "TG"); QSx → the synthetic entry. Everything else is unresolved.
    /// </summary>
    private sealed class FixedRegionStore : ICallsignRegionStore
    {
        public IReadOnlyList<CallsignRegionEntry> Entries { get; } = [];

        public RegionInfo? TryGetRegion(string callsignToken)
        {
            if (callsignToken.StartsWith("Q1", StringComparison.Ordinal))
                return new RegionInfo("TA", "Testland Alpha", Synthetic: false);
            if (callsignToken.StartsWith("Q2", StringComparison.Ordinal))
                return new RegionInfo("TA", "Testland Beta", Synthetic: false);
            if (callsignToken.StartsWith("Q3", StringComparison.Ordinal))
                return new RegionInfo("TG", "Testland Gamma", Synthetic: false);
            if (callsignToken.StartsWith("QS", StringComparison.Ordinal))
                return new RegionInfo(null, "Synthetic (R&R Study)", Synthetic: true);
            return null;
        }

        public Task SaveAsync(IReadOnlyList<CallsignRegionEntry> entries, CancellationToken cancellationToken = default)
            => throw new NotSupportedException();
    }
}
