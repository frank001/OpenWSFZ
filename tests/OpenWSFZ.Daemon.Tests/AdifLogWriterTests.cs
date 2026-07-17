using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using NSubstitute;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="AdifLogWriter"/> (FR-048, tasks 7.1–7.8).
///
/// Tests verify:
///   - Correct ADIF tagged-field format: <c>&lt;FIELD:len&gt;value</c>
///   - EOR terminator on every record
///   - BAND derivation from dial frequency
///   - FREQ and BAND fields omitted when dial frequency is 0.0
///   - Path resolution relative to DecodeLog.Path
///   - Write failures are swallowed (no throw)
///
/// NFR-021: all callsigns use ITU-unallocated Q-prefix.
/// </summary>
[Trait("Category", "Unit")]
public sealed class AdifLogWriterTests : IDisposable
{
    private readonly string _tempDir;

    public AdifLogWriterTests()
    {
        _tempDir = Path.Combine(
            Path.GetTempPath(),
            "openwsfz-adif-test-" + Path.GetRandomFileName());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        try { Directory.Delete(_tempDir, recursive: true); } catch { /* best-effort */ }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static QsoRecord MakeRecord(double dialMhz = 7.074) => new()
    {
        PartnerCallsign  = "Q1TST",
        PartnerGrid      = "JO22",
        RstSent          = "R+00",
        RstRcvd          = "+05",
        QsoStartUtc      = new DateTime(2026, 6, 14, 12, 0, 0, DateTimeKind.Utc),
        QsoEndUtc        = new DateTime(2026, 6, 14, 12, 1, 30, DateTimeKind.Utc),
        OperatorCallsign = "Q1OFZ",
        OperatorGrid     = "JO33",
        DialFrequencyMHz = dialMhz,
    };

    private IConfigStore StoreWith(string decodeLogPath, double dialMhz = 7.074)
    {
        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with
        {
            DecodeLog = new DecodeLogConfig
            {
                Enabled          = true,
                Path             = decodeLogPath,
                DialFrequencyMHz = dialMhz,
            }
        });
        return store;
    }

    // ── Task 7.2: Path resolution ─────────────────────────────────────────────

    [Fact(DisplayName = "7.2: Path is sibling of ALL.TXT when DecodeLog.Path has a directory")]
    public void ResolveAdifPath_WithDirectory_PlacesAdifNextToAllTxt()
    {
        var store = StoreWith(Path.Combine(_tempDir, "ALL.TXT"));
        var sut   = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);

        var path = sut.ResolveAdifPath();

        path.Should().Be(Path.Combine(_tempDir, "ADIF.log"));
    }

    [Fact(DisplayName = "7.2: Path is 'ADIF.log' when DecodeLog.Path has no directory component")]
    public void ResolveAdifPath_NoDirectory_ReturnsAdifLogInCwd()
    {
        var store = StoreWith("ALL.TXT");
        var sut   = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);

        var path = sut.ResolveAdifPath();

        path.Should().Be("ADIF.log");
    }

    // ── Task 7.3: ADIF field format ───────────────────────────────────────────

    [Fact(DisplayName = "FR-051: BuildAdifRecord uses <FIELD:len>value format for all fields")]
    public void BuildAdifRecord_FieldFormat_IsCorrect()
    {
        var record = MakeRecord();

        var adif = AdifLogWriter.BuildAdifRecord(record);

        // Spot-check a few fields.
        adif.Should().Contain("<CALL:5>Q1TST",        "CALL field must be length-prefixed");
        adif.Should().Contain("<GRIDSQUARE:4>JO22",   "GRIDSQUARE must be length-prefixed");
        adif.Should().Contain("<RST_SENT:4>R+00",     "RST_SENT must be length-prefixed");
        adif.Should().Contain("<RST_RCVD:3>+05",      "RST_RCVD must be length-prefixed");
        adif.Should().Contain("<OPERATOR:5>Q1OFZ",    "OPERATOR must be length-prefixed");
        adif.Should().Contain("<MY_GRIDSQUARE:4>JO33","MY_GRIDSQUARE must be length-prefixed");
        adif.Should().Contain("<MODE:3>FT8",           "MODE must always be FT8");
        adif.Should().Contain("<QSO_DATE:8>20260614",    "QSO_DATE in yyyyMMdd format");
        adif.Should().Contain("<TIME_ON:6>120000",     "TIME_ON in HHmmss format per ADIF 3.x");
        adif.Should().Contain("<QSO_DATE_OFF:8>20260614");
        adif.Should().Contain("<TIME_OFF:6>120130",    "TIME_OFF in HHmmss format per ADIF 3.x");
    }

    [Fact(DisplayName = "7.3: BuildAdifRecord ends with <EOR>")]
    public void BuildAdifRecord_EndsWithEor()
    {
        var adif = AdifLogWriter.BuildAdifRecord(MakeRecord());
        adif.Should().EndWith("<EOR>");
    }

    [Fact(DisplayName = "7.3: GRIDSQUARE field is omitted when PartnerGrid is null")]
    public void BuildAdifRecord_NullPartnerGrid_OmitsGridsquare()
    {
        var record = MakeRecord() with { PartnerGrid = null };
        var adif   = AdifLogWriter.BuildAdifRecord(record);
        // Use "<GRIDSQUARE:" to avoid matching "MY_GRIDSQUARE" which is always present.
        adif.Should().NotContain("<GRIDSQUARE:", "partner GRIDSQUARE field must be omitted when grid is unknown");
    }

    // ── Task 7.5: BAND derivation ─────────────────────────────────────────────

    [Theory(DisplayName = "7.5: DeriveBand returns correct ITU band name")]
    [InlineData(1.840,  "160m")]
    [InlineData(3.573,  "80m")]
    [InlineData(5.357,  "60m")]
    [InlineData(7.074,  "40m")]
    [InlineData(10.136, "30m")]
    [InlineData(14.074, "20m")]
    [InlineData(18.100, "17m")]
    [InlineData(21.074, "15m")]
    [InlineData(24.915, "12m")]
    [InlineData(28.074, "10m")]
    [InlineData(50.313, "6m")]
    [InlineData(144.174,"2m")]
    [InlineData(432.1,  "70cm")]
    public void DeriveBand_KnownFrequency_ReturnsCorrectBand(double freqMHz, string expected)
    {
        AdifLogWriter.DeriveBand(freqMHz).Should().Be(expected);
    }

    [Theory(DisplayName = "7.5: DeriveBand returns null for out-of-band or zero frequencies")]
    [InlineData(0.0)]
    [InlineData(99.5)]
    [InlineData(600.0)]
    public void DeriveBand_OutOfBandOrZero_ReturnsNull(double freqMHz)
    {
        AdifLogWriter.DeriveBand(freqMHz).Should().BeNull();
    }

    [Fact(DisplayName = "7.5: FREQ and BAND fields are present when dial frequency is non-zero")]
    public void BuildAdifRecord_NonZeroFreq_IncludesFreqAndBand()
    {
        var adif = AdifLogWriter.BuildAdifRecord(MakeRecord(dialMhz: 7.074));

        adif.Should().Contain("FREQ");
        adif.Should().Contain("<BAND:3>40m");
    }

    [Fact(DisplayName = "7.5: FREQ and BAND fields are omitted when dial frequency is 0.0")]
    public void BuildAdifRecord_ZeroFreq_OmitsFreqAndBand()
    {
        var adif = AdifLogWriter.BuildAdifRecord(MakeRecord(dialMhz: 0.0));

        adif.Should().NotContain("FREQ");
        adif.Should().NotContain("BAND");
    }

    // ── Task 7.3: File I/O ────────────────────────────────────────────────────

    [Fact(DisplayName = "7.3: AppendQsoAsync writes a valid ADIF record to disk")]
    public async Task AppendQsoAsync_WritesRecordToFile()
    {
        var adifPath = Path.Combine(_tempDir, "ADIF.log");
        var allTxt   = Path.Combine(_tempDir, "ALL.TXT");
        var store    = StoreWith(allTxt, dialMhz: 7.074);
        var sut      = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);

        await sut.AppendQsoAsync(MakeRecord(dialMhz: 7.074));

        File.Exists(adifPath).Should().BeTrue("ADIF file should be created");
        var content = await File.ReadAllTextAsync(adifPath);
        content.Should().Contain("<CALL:5>Q1TST");
        content.Should().Contain("<EOR>");
    }

    [Fact(DisplayName = "7.3: AppendQsoAsync appends (does not overwrite) on second call")]
    public async Task AppendQsoAsync_SecondCall_Appends()
    {
        var allTxt = Path.Combine(_tempDir, "ALL.TXT");
        var store  = StoreWith(allTxt);
        var sut    = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);

        await sut.AppendQsoAsync(MakeRecord());
        await sut.AppendQsoAsync(MakeRecord() with { PartnerCallsign = "Q2ABC" });

        var lines = await File.ReadAllLinesAsync(Path.Combine(_tempDir, "ADIF.log"));
        lines.Should().HaveCount(2, "two QSOs → two records, one per line");
        lines[0].Should().Contain("Q1TST");
        lines[1].Should().Contain("Q2ABC");
    }

    // ── Task 7.7: Write failure handling ─────────────────────────────────────

    [Fact(DisplayName = "7.7: AppendQsoAsync does not throw on I/O failure")]
    public async Task AppendQsoAsync_IoFailure_DoesNotThrow()
    {
        // Point at a path we can never write: a directory used as a file name.
        var store = StoreWith(Path.Combine(_tempDir, "subdir", "ALL.TXT"));
        // Create a *directory* at the ADIF path so the write must fail.
        Directory.CreateDirectory(Path.Combine(_tempDir, "subdir", "ADIF.log"));
        var sut = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);

        // Must not throw — task 7.7.
        var act = async () => await sut.AppendQsoAsync(MakeRecord());
        await act.Should().NotThrowAsync();
    }

    // ── Task 2.5/2.6/5.1/5.2: worked-before index registration (qso-confirmation,
    //    qso-confirmation-band-awareness) ───────────────────────────────────────

    [Fact(DisplayName = "2.6: AppendQsoAsync registers the partner callsign into the worked-before index on a successful write")]
    public async Task AppendQsoAsync_SuccessfulWrite_RegistersCallsignIntoIndex()
    {
        var store = StoreWith(Path.Combine(_tempDir, "ALL.TXT"));
        var index = new SpyWorkedBeforeIndex();
        var sut   = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance, index);

        await sut.AppendQsoAsync(MakeRecord()); // PartnerCallsign = "Q1TST"

        index.Registered.Should().ContainSingle().Which.Callsign.Should().Be("Q1TST");
    }

    [Fact(DisplayName = "5.1: AppendQsoAsync passes the already-computed band into Register")]
    public async Task AppendQsoAsync_SuccessfulWrite_RegistersBandIntoIndex()
    {
        var store = StoreWith(Path.Combine(_tempDir, "ALL.TXT"), dialMhz: 14.074);
        var index = new SpyWorkedBeforeIndex();
        var sut   = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance, index);

        await sut.AppendQsoAsync(MakeRecord(dialMhz: 14.074));

        index.Registered.Should().ContainSingle().Which.Band.Should().Be("20m");
    }

    [Fact(DisplayName = "5.2: a QSO logged with a known band resolves ThisBand on the very next decode of the same station/band")]
    public async Task AppendQsoAsync_KnownBand_NextResolveIsThisBand()
    {
        var store = StoreWith(Path.Combine(_tempDir, "ALL.TXT"), dialMhz: 14.074);
        var index = new WorkedBeforeIndex(store, new NullRegionStore(), NullLogger<WorkedBeforeIndex>.Instance);
        await index.LoadAsync(); // empty index — no ADIF.log yet
        var sut = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance, index);

        await sut.AppendQsoAsync(MakeRecord(dialMhz: 14.074)); // PartnerCallsign = "Q1TST", band "20m"

        index.Resolve("Q1TST", "20m").Contact.Should().Be(WorkedBeforeState.ThisBand,
            "the very next decode of the same station on the same band must resolve ThisBand without a reload");
        index.Resolve("Q1TST", "40m").Contact.Should().Be(WorkedBeforeState.DifferentBand,
            "the same station on a different band must not resolve ThisBand");
    }

    [Fact(DisplayName = "2.6: AppendQsoAsync does not register the callsign into the worked-before index when the write fails")]
    public async Task AppendQsoAsync_FailedWrite_DoesNotRegisterCallsign()
    {
        var store = StoreWith(Path.Combine(_tempDir, "subdir", "ALL.TXT"));
        Directory.CreateDirectory(Path.Combine(_tempDir, "subdir", "ADIF.log")); // forces the write to fail
        var index = new SpyWorkedBeforeIndex();
        var sut   = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance, index);

        await sut.AppendQsoAsync(MakeRecord());

        index.Registered.Should().BeEmpty("a failed write must not register the callsign");
    }

    /// <summary>Records every (callsign, band) pair passed to <see cref="Register"/> — no ADIF/region I/O.</summary>
    private sealed class SpyWorkedBeforeIndex : IWorkedBeforeIndex
    {
        public List<(string Callsign, string? Band)> Registered { get; } = [];

        public Task LoadAsync(CancellationToken cancellationToken = default) => Task.CompletedTask;
        public void Register(string callsign, string? band) => Registered.Add((callsign, band));
        public WorkedBeforeInfo Resolve(string callsignToken, string? currentBand) => WorkedBeforeInfo.None;
    }

    /// <summary>Region store with no entries — every callsign is unresolved ("Unknown").</summary>
    private sealed class NullRegionStore : ICallsignRegionStore
    {
        public IReadOnlyList<CallsignRegionEntry> Entries { get; } = [];
        public bool IsSeedData => false;
        public RegionInfo? TryGetRegion(string callsignToken) => null;
        public CallsignRegionMatch? TryMatchPrefix(string callsignToken) => null;
        public Task SaveAsync(IReadOnlyList<CallsignRegionEntry> entries, CancellationToken cancellationToken = default)
            => throw new NotSupportedException();
    }

    // ── Task 1.3: Optional enrichment fields (qso-log-dialog) ────────────────

    [Theory(DisplayName = "1.3: Optional field included in ADIF when non-null/non-empty")]
    [InlineData("NAME",       nameof(QsoRecord.PartnerName), "John")]
    [InlineData("TX_PWR",     nameof(QsoRecord.TxPower),     "100")]
    [InlineData("COMMENT",    nameof(QsoRecord.Comment),     "Nice contact")]
    [InlineData("PROP_MODE",  nameof(QsoRecord.PropMode),    "TR")]
    [InlineData("STX_STRING", nameof(QsoRecord.ExchSent),    "599001")]
    [InlineData("SRX_STRING", nameof(QsoRecord.ExchRcvd),    "599042")]
    public void BuildAdifRecord_OptionalField_IncludedWhenNonEmpty(
        string adifField, string propertyName, string value)
    {
        var record = MakeRecord() with
        {
            PartnerName = propertyName == nameof(QsoRecord.PartnerName) ? value : null,
            TxPower     = propertyName == nameof(QsoRecord.TxPower)     ? value : null,
            Comment     = propertyName == nameof(QsoRecord.Comment)      ? value : null,
            PropMode    = propertyName == nameof(QsoRecord.PropMode)     ? value : null,
            ExchSent    = propertyName == nameof(QsoRecord.ExchSent)     ? value : null,
            ExchRcvd    = propertyName == nameof(QsoRecord.ExchRcvd)     ? value : null,
        };

        var adif = AdifLogWriter.BuildAdifRecord(record);

        adif.Should().Contain($"<{adifField}:{value.Length}>{value}",
            $"ADIF field {adifField} must be written as <{adifField}:len>value");
    }

    [Theory(DisplayName = "1.3: Optional field omitted from ADIF when null or empty")]
    [InlineData(nameof(QsoRecord.PartnerName), "NAME",       null)]
    [InlineData(nameof(QsoRecord.PartnerName), "NAME",       "")]
    [InlineData(nameof(QsoRecord.TxPower),     "TX_PWR",     null)]
    [InlineData(nameof(QsoRecord.TxPower),     "TX_PWR",     "")]
    [InlineData(nameof(QsoRecord.Comment),     "COMMENT",    null)]
    [InlineData(nameof(QsoRecord.Comment),     "COMMENT",    "")]
    [InlineData(nameof(QsoRecord.PropMode),    "PROP_MODE",  null)]
    [InlineData(nameof(QsoRecord.PropMode),    "PROP_MODE",  "")]
    [InlineData(nameof(QsoRecord.ExchSent),    "STX_STRING", null)]
    [InlineData(nameof(QsoRecord.ExchSent),    "STX_STRING", "")]
    [InlineData(nameof(QsoRecord.ExchRcvd),    "SRX_STRING", null)]
    [InlineData(nameof(QsoRecord.ExchRcvd),    "SRX_STRING", "")]
    public void BuildAdifRecord_OptionalField_OmittedWhenNullOrEmpty(
        string propertyName, string adifField, string? value)
    {
        var record = MakeRecord() with
        {
            PartnerName = propertyName == nameof(QsoRecord.PartnerName) ? value : null,
            TxPower     = propertyName == nameof(QsoRecord.TxPower)     ? value : null,
            Comment     = propertyName == nameof(QsoRecord.Comment)      ? value : null,
            PropMode    = propertyName == nameof(QsoRecord.PropMode)     ? value : null,
            ExchSent    = propertyName == nameof(QsoRecord.ExchSent)     ? value : null,
            ExchRcvd    = propertyName == nameof(QsoRecord.ExchRcvd)     ? value : null,
        };

        var adif = AdifLogWriter.BuildAdifRecord(record);

        adif.Should().NotContain($"<{adifField}:",
            $"ADIF field {adifField} must be omitted when the source value is null or empty");
    }
}
