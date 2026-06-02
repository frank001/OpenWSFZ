using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="AllTxtWriter"/> (FR-028).
/// Verifies WSJT-X compatible ALL.TXT line format, suppression behaviour,
/// and fault isolation (write failures must not throw).
/// </summary>
[Trait("Category", "Unit")]
public sealed class AllTxtWriterTests : IDisposable
{
    private readonly string _tempDir;

    public AllTxtWriterTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(),
            "openwsfz-alltxt-test-" + Path.GetRandomFileName());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        try { Directory.Delete(_tempDir, recursive: true); } catch { /* best-effort */ }
    }

    // ── FR-028: correct line format ───────────────────────────────────────────

    [Fact(DisplayName = "FR-027, FR-028: line format matches WSJT-X ALL.TXT exactly, including dial frequency column")]
    public async Task AppendAsync_WritesLineMatchingWsjtxFormat()
    {
        var tmpFile = Path.Combine(_tempDir, "ALL.TXT");
        var config  = new DecodeLogConfig { Enabled = true, Path = tmpFile, DialFrequencyMHz = 7.074 };
        var writer  = MakeWriter(config);

        var cycleUtc = new DateTime(2026, 5, 28, 17, 29, 30, DateTimeKind.Utc);
        var results  = new List<DecodeResult>
        {
            new("17:29:30", Snr: 3, Dt: 0.2, FreqHz: 2252, Message: "Q4DSA QD1BER JO22"),
        };

        await writer.AppendAsync(cycleUtc, 7.074, results);

        var lines = await File.ReadAllLinesAsync(tmpFile);
        lines.Should().HaveCount(1);
        // Format: "{timestamp}     {dialMhz:F3} Rx FT8 {snr,6} {dt,4:F1} {freq,4} {message}"
        // snr=3  → "     3" (6 chars); dt=0.2 → " 0.2" (4 chars); plus 1-space separator = 2 spaces before "0.2".
        lines[0].Should().Be("260528_172930     7.074 Rx FT8      3  0.2 2252 Q4DSA QD1BER JO22",
            "the line must exactly match the WSJT-X ALL.TXT column layout");
    }

    // ── FR-028: suppression when disabled ─────────────────────────────────────

    [Fact(DisplayName = "FR-028: nothing written when disabled")]
    public async Task AppendAsync_DoesNotCreateFile_WhenDisabled()
    {
        var tmpFile = Path.Combine(_tempDir, "ALL.TXT");
        var config  = new DecodeLogConfig { Enabled = false, Path = tmpFile, DialFrequencyMHz = 7.074 };
        var writer  = MakeWriter(config);

        var results = new List<DecodeResult>
        {
            new("17:29:30", Snr: 3, Dt: 0.2, FreqHz: 2252, Message: "Q4DSA QD1BER JO22"),
        };

        await writer.AppendAsync(DateTime.UtcNow, 7.074, results);

        File.Exists(tmpFile).Should().BeFalse("no file should be created when decodeLog.enabled is false");
    }

    // ── FR-028: suppression when results empty ────────────────────────────────

    [Fact(DisplayName = "FR-028: nothing written when results empty")]
    public async Task AppendAsync_DoesNotCreateFile_WhenResultsEmpty()
    {
        var tmpFile = Path.Combine(_tempDir, "ALL.TXT");
        var config  = new DecodeLogConfig { Enabled = true, Path = tmpFile, DialFrequencyMHz = 7.074 };
        var writer  = MakeWriter(config);

        await writer.AppendAsync(DateTime.UtcNow, 7.074, new List<DecodeResult>());

        File.Exists(tmpFile).Should().BeFalse("no file should be created when results list is empty");
    }

    // ── FR-028: write failure does not throw ──────────────────────────────────

    [Fact(DisplayName = "FR-028: file write failure does not throw")]
    public async Task AppendAsync_DoesNotThrow_OnWriteFailure()
    {
        // Create a DIRECTORY at the path where the writer expects a FILE.
        // On all OSes, opening a directory as a StreamWriter throws
        // UnauthorizedAccessException (Windows) or IOException (Linux/macOS).
        // Both exceptions are caught and swallowed by AllTxtWriter.
        var invalidPath = Path.Combine(_tempDir, "ALL.TXT");
        Directory.CreateDirectory(invalidPath); // ALL.TXT is now a directory, not a file

        var config = new DecodeLogConfig { Enabled = true, Path = invalidPath, DialFrequencyMHz = 7.074 };
        var logger = new CapturingLogger<AllTxtWriter>();
        var writer = MakeWriter(config, logger);

        var results = new List<DecodeResult>
        {
            new("17:29:30", Snr: 3, Dt: 0.2, FreqHz: 2252, Message: "Q4DSA QD1BER JO22"),
        };

        // Must not throw.
        var act = async () => await writer.AppendAsync(DateTime.UtcNow, 7.074, results);
        await act.Should().NotThrowAsync("write failures must be swallowed and logged, not propagated");

        // Must have logged a Warning.
        logger.HasWarning.Should().BeTrue("a Warning must be logged when the file cannot be written");
    }

    // ── FR-032: caller-supplied dial frequency (defect: dial-freq-snapshot) ───

    [Fact(DisplayName = "P16-Cat: AppendAsync uses caller-supplied dialMhz, not live state")]
    public async Task AppendAsync_UsesSuppliedDialMhz()
    {
        // If AppendAsync still read from ICatState this test would need a mock;
        // the absence of any ICatState parameter proves it cannot.
        var tmpFile = Path.Combine(_tempDir, "ALL.TXT");
        var config  = new DecodeLogConfig { Enabled = true, Path = tmpFile, DialFrequencyMHz = 7.074 };
        var writer  = MakeWriter(config);

        var results = new[] { new DecodeResult("20:27:30", Snr: 5, Dt: 0.9, FreqHz: 1200, Message: "CQ TEST") };

        await writer.AppendAsync(DateTime.UtcNow, dialMhz: 14.074, results);

        var lines = await File.ReadAllLinesAsync(tmpFile);
        lines.Should().HaveCount(1);
        lines[0].Should().Contain("14.074",
            "the caller-supplied dialMhz must appear in the log line");
        lines[0].Should().NotContain("7.074",
            "the config's DialFrequencyMHz must not override the caller-supplied value");
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static AllTxtWriter MakeWriter(
        DecodeLogConfig        config,
        ILogger<AllTxtWriter>? logger = null)
    {
        var configStore = new StubConfigStore(new AppConfig() with { DecodeLog = config });
        return new AllTxtWriter(configStore, logger ?? new CapturingLogger<AllTxtWriter>());
    }

    // ── Stub IConfigStore ─────────────────────────────────────────────────────

    private sealed class StubConfigStore : IConfigStore
    {
        public StubConfigStore(AppConfig config) => Current = config;
        public AppConfig Current { get; }
        public event Action<AppConfig>? OnSaved;
        public Task SaveAsync(AppConfig config, CancellationToken ct = default)
        {
            OnSaved?.Invoke(config);
            return Task.CompletedTask;
        }
    }

    // ── Capturing logger ──────────────────────────────────────────────────────

    private sealed class CapturingLogger<T> : ILogger<T>
    {
        private bool _hasWarning;
        public bool HasWarning => _hasWarning;

        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;

        public void Log<TState>(
            LogLevel logLevel, EventId eventId, TState state,
            Exception? exception, Func<TState, Exception?, string> formatter)
        {
            if (logLevel >= LogLevel.Warning)
                _hasWarning = true;
        }
    }
}
