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

    // ── ReadCallsigns ─────────────────────────────────────────────────────────

    [Fact(DisplayName = "1.6: ReadCallsigns parses a well-formed multi-record file")]
    public void ReadCallsigns_WellFormedMultiRecordFile_ReturnsAllCallsigns()
    {
        var path = WriteFixture(
            "ADIF Export\r\n" +
            "<adif_ver:5>3.1.4<eoh>\r\n" +
            "<call:5>Q1TST<gridsquare:4>JO22<mode:3>FT8<eor>\r\n" +
            "<call:5>Q2ABC<gridsquare:4>JO33<mode:3>FT8<eor>\r\n");

        var callsigns = AdifReader.ReadCallsigns(path);

        callsigns.Should().BeEquivalentTo(["Q1TST", "Q2ABC"]);
    }

    [Fact(DisplayName = "1.6: ReadCallsigns returns an empty list for a header-only file (no records)")]
    public void ReadCallsigns_HeaderOnlyFile_ReturnsEmpty()
    {
        var path = WriteFixture("ADIF Export\r\n<adif_ver:5>3.1.4<eoh>\r\n");

        AdifReader.ReadCallsigns(path).Should().BeEmpty();
    }

    [Fact(DisplayName = "1.6: ReadCallsigns skips a truncated/malformed <call: line without failing the rest of the parse")]
    public void ReadCallsigns_TruncatedCallLine_SkippedNotFatal()
    {
        var path = WriteFixture(
            "ADIF Export\r\n" +
            "<adif_ver:5>3.1.4<eoh>\r\n" +
            "<call:5>Q1TST<eor>\r\n" +
            "<call:99>TRUNCATED<eor>\r\n" +
            "<call:5>Q2ABC<eor>\r\n");

        var callsigns = AdifReader.ReadCallsigns(path);

        callsigns.Should().BeEquivalentTo(["Q1TST", "Q2ABC"],
            "the malformed middle line must be skipped without aborting the rest of the parse");
    }

    [Fact(DisplayName = "1.6: ReadCallsigns returns an empty list for a missing file, not an error")]
    public void ReadCallsigns_MissingFile_ReturnsEmpty()
    {
        var path = Path.Combine(_tempDir, "does-not-exist.log");

        var act = () => AdifReader.ReadCallsigns(path);

        act.Should().NotThrow();
        act().Should().BeEmpty();
    }

    [Fact(DisplayName = "1.6: ReadCallsigns includes duplicate CALL values verbatim (dedup is the caller's responsibility)")]
    public void ReadCallsigns_DuplicateCallsigns_ReturnsAllOccurrences()
    {
        var path = WriteFixture(
            "<call:5>Q1TST<eor>\r\n" +
            "<call:5>Q1TST<eor>\r\n");

        AdifReader.ReadCallsigns(path).Should().HaveCount(2);
    }

    [Fact(DisplayName = "1.6: ReadCallsigns does not warn for benign non-record lines (no <call: substring at all)")]
    public void ReadCallsigns_BenignNonRecordLines_NoWarningLogged()
    {
        var path = WriteFixture(
            "ADIF Export\r\n" +
            "<adif_ver:5>3.1.4<eoh>\r\n" +
            "\r\n" +
            "<call:5>Q1TST<eor>\r\n");

        var logger = new RecordingLogger<object>();

        AdifReader.ReadCallsigns(path, logger).Should().BeEquivalentTo(["Q1TST"]);
        logger.Warnings.Should().BeEmpty("header/blank lines are expected, not malformed");
    }

    [Fact(DisplayName = "1.6: ReadCallsigns logs a Warning for a truncated/malformed <call: tag")]
    public void ReadCallsigns_TruncatedCallLine_LogsWarning()
    {
        var path = WriteFixture("<call:99>TRUNCATED<eor>\r\n");
        var logger = new RecordingLogger<object>();

        AdifReader.ReadCallsigns(path, logger);

        logger.Warnings.Should().HaveCount(1, "a line carrying a malformed <call: tag must be flagged");
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
