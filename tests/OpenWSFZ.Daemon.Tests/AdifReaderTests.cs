using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="AdifReader"/> (<c>qso-confirmation</c> capability, tasks 1.2/1.6).
///
/// NFR-021: all callsigns use the ITU-unallocated Q-prefix; never real callsigns from the
/// repo's live <c>ADIF.log</c>.
/// </summary>
[Trait("Category", "Unit")]
public sealed class AdifReaderTests : IDisposable
{
    private readonly string _tempDir;

    public AdifReaderTests()
    {
        _tempDir = Path.Combine(
            Path.GetTempPath(),
            "openwsfz-adifreader-test-" + Path.GetRandomFileName());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        try { Directory.Delete(_tempDir, recursive: true); } catch { /* best-effort */ }
    }

    private string WriteFixture(string content)
    {
        var path = Path.Combine(_tempDir, "ADIF.log");
        File.WriteAllText(path, content);
        return path;
    }

    // ── TryExtractCall ───────────────────────────────────────────────────────

    [Theory(DisplayName = "1.2: TryExtractCall parses a well-formed <call:N> tag case-insensitively")]
    [InlineData("<call:5>Q1TST<eor>", "Q1TST")]
    [InlineData("<CALL:5>Q1TST<EOR>", "Q1TST")]
    [InlineData("<Call:5>Q1TST<eor>", "Q1TST")]
    public void TryExtractCall_WellFormedTag_ReturnsValue(string line, string expected)
        => AdifReader.TryExtractCall(line).Should().Be(expected);

    [Fact(DisplayName = "1.2: TryExtractCall extracts CALL from a line with multiple other fields")]
    public void TryExtractCall_LineWithOtherFields_ExtractsCallOnly()
    {
        var line = "<call:5>Q1TST<gridsquare:4>JO22<mode:3>FT8<eor>";
        AdifReader.TryExtractCall(line).Should().Be("Q1TST");
    }

    [Fact(DisplayName = "1.2: TryExtractCall returns null when no <call: tag is present")]
    public void TryExtractCall_NoCallTag_ReturnsNull()
        => AdifReader.TryExtractCall("<gridsquare:4>JO22<eor>").Should().BeNull();

    [Fact(DisplayName = "1.2: TryExtractCall returns null for a truncated/malformed <call: tag")]
    public void TryExtractCall_TruncatedTag_ReturnsNull()
        => AdifReader.TryExtractCall("<call:99>Q1TST<eor>").Should().BeNull(
            "the declared length (99) runs past the end of the line");

    [Fact(DisplayName = "1.2: TryExtractCall returns null for a non-numeric length")]
    public void TryExtractCall_NonNumericLength_ReturnsNull()
        => AdifReader.TryExtractCall("<call:abc>Q1TST<eor>").Should().BeNull();

    // ── TryExtractBand (2.1/2.2) ─────────────────────────────────────────────

    [Theory(DisplayName = "2.2: TryExtractBand parses a well-formed <band:N> tag case-insensitively")]
    [InlineData("<band:3>40m<eor>", "40m")]
    [InlineData("<BAND:3>40m<EOR>", "40m")]
    [InlineData("<Band:3>40m<eor>", "40m")]
    public void TryExtractBand_WellFormedTag_ReturnsValue(string line, string expected)
        => AdifReader.TryExtractBand(line).Should().Be(expected);

    [Fact(DisplayName = "2.2: TryExtractBand returns null when no <band: tag is present")]
    public void TryExtractBand_NoBandTag_ReturnsNull()
        => AdifReader.TryExtractBand("<call:5>Q1TST<eor>").Should().BeNull();

    [Fact(DisplayName = "2.2: TryExtractBand returns null for a truncated/malformed <band: tag")]
    public void TryExtractBand_TruncatedTag_ReturnsNull()
        => AdifReader.TryExtractBand("<band:99>40m<eor>").Should().BeNull(
            "the declared length (99) runs past the end of the line");

    // ── ReadEntries (2.2/2.4) ─────────────────────────────────────────────────

    [Fact(DisplayName = "2.4: ReadEntries parses a well-formed multi-record file with CALL and BAND")]
    public void ReadEntries_WellFormedMultiRecordFile_ReturnsAllEntries()
    {
        var path = WriteFixture(
            "ADIF Export\r\n" +
            "<adif_ver:5>3.1.4<eoh>\r\n" +
            "<call:5>Q1TST<band:3>40m<gridsquare:4>JO22<mode:3>FT8<eor>\r\n" +
            "<call:5>Q2ABC<band:3>20m<gridsquare:4>JO33<mode:3>FT8<eor>\r\n");

        var entries = AdifReader.ReadEntries(path);

        entries.Should().BeEquivalentTo(
        [
            new AdifLogEntry("Q1TST", "40m"),
            new AdifLogEntry("Q2ABC", "20m"),
        ]);
    }

    [Fact(DisplayName = "2.4: ReadEntries returns an empty list for a header-only file (no records)")]
    public void ReadEntries_HeaderOnlyFile_ReturnsEmpty()
    {
        var path = WriteFixture("ADIF Export\r\n<adif_ver:5>3.1.4<eoh>\r\n");

        AdifReader.ReadEntries(path).Should().BeEmpty();
    }

    [Fact(DisplayName = "2.4: ReadEntries skips a truncated/malformed <call: line without failing the rest of the parse")]
    public void ReadEntries_TruncatedCallLine_SkippedNotFatal()
    {
        var path = WriteFixture(
            "ADIF Export\r\n" +
            "<adif_ver:5>3.1.4<eoh>\r\n" +
            "<call:5>Q1TST<band:3>40m<eor>\r\n" +
            "<call:99>TRUNCATED<eor>\r\n" +
            "<call:5>Q2ABC<band:3>20m<eor>\r\n");

        var entries = AdifReader.ReadEntries(path);

        entries.Should().BeEquivalentTo(
        [
            new AdifLogEntry("Q1TST", "40m"),
            new AdifLogEntry("Q2ABC", "20m"),
        ], "the malformed middle line must be skipped without aborting the rest of the parse");
    }

    [Fact(DisplayName = "2.4: ReadEntries returns an empty list for a missing file, not an error")]
    public void ReadEntries_MissingFile_ReturnsEmpty()
    {
        var path = Path.Combine(_tempDir, "does-not-exist.log");

        var act = () => AdifReader.ReadEntries(path);

        act.Should().NotThrow();
        act().Should().BeEmpty();
    }

    [Fact(DisplayName = "2.4: ReadEntries includes duplicate CALL values verbatim (dedup is the caller's responsibility)")]
    public void ReadEntries_DuplicateCallsigns_ReturnsAllOccurrences()
    {
        var path = WriteFixture(
            "<call:5>Q1TST<band:3>40m<eor>\r\n" +
            "<call:5>Q1TST<band:3>20m<eor>\r\n");

        AdifReader.ReadEntries(path).Should().HaveCount(2);
    }

    [Fact(DisplayName = "2.4: ReadEntries does not warn for benign non-record lines (no <call: substring at all)")]
    public void ReadEntries_BenignNonRecordLines_NoWarningLogged()
    {
        var path = WriteFixture(
            "ADIF Export\r\n" +
            "<adif_ver:5>3.1.4<eoh>\r\n" +
            "\r\n" +
            "<call:5>Q1TST<band:3>40m<eor>\r\n");

        var logger = new RecordingLogger<object>();

        AdifReader.ReadEntries(path, logger).Should().BeEquivalentTo([new AdifLogEntry("Q1TST", "40m")]);
        logger.Warnings.Should().BeEmpty("header/blank lines are expected, not malformed");
    }

    [Fact(DisplayName = "2.4: ReadEntries logs a Warning for a truncated/malformed <call: tag")]
    public void ReadEntries_TruncatedCallLine_LogsWarning()
    {
        var path = WriteFixture("<call:99>TRUNCATED<eor>\r\n");
        var logger = new RecordingLogger<object>();

        AdifReader.ReadEntries(path, logger);

        logger.Warnings.Should().HaveCount(1, "a line carrying a malformed <call: tag must be flagged");
    }

    [Fact(DisplayName = "2.4: ReadEntries yields Band: null (not a skip) when CALL is present but BAND is missing")]
    public void ReadEntries_CallWithoutBand_YieldsNullBand()
    {
        var path = WriteFixture("<call:5>Q1TST<eor>\r\n");

        var entries = AdifReader.ReadEntries(path);

        entries.Should().ContainSingle().Which.Should().Be(new AdifLogEntry("Q1TST", null));
    }

    [Fact(DisplayName = "2.4: ReadEntries yields Band: null (not a skip) when the BAND tag is malformed/truncated")]
    public void ReadEntries_CallWithMalformedBand_YieldsNullBand()
    {
        var path = WriteFixture("<call:5>Q1TST<band:99>TRUNCATED<eor>\r\n");

        var entries = AdifReader.ReadEntries(path);

        entries.Should().ContainSingle().Which.Should().Be(new AdifLogEntry("Q1TST", null));
    }

    // ── Test double ──────────────────────────────────────────────────────────

    private sealed class RecordingLogger<T> : ILogger<T>
    {
        public List<string> Warnings { get; } = [];

        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;

        public void Log<TState>(
            LogLevel logLevel, EventId eventId, TState state,
            Exception? exception, Func<TState, Exception?, string> formatter)
        {
            if (logLevel >= LogLevel.Warning)
                Warnings.Add(formatter(state, exception));
        }
    }
}
