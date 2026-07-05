using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon.Logging;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Unit tests for <see cref="LoggingPipeline"/> (FR-022, FR-024).
/// </summary>
/// <remarks>
/// Tests run serially within this collection because <see cref="LoggingPipeline.Apply"/>
/// sets the global <see cref="Serilog.Log.Logger"/>.
/// </remarks>
[Collection("SerialLoggingTests")]
public sealed class LoggingPipelineTests : IDisposable
{
    private readonly string _tempDir;

    public LoggingPipelineTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(),
            "openwsfz-lp-test-" + Path.GetRandomFileName());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        try { Directory.Delete(_tempDir, recursive: true); } catch { /* best-effort */ }
    }

    // ── FR-022: file-creation behaviour ──────────────────────────────────────

    [Fact(DisplayName = "FR-022: LoggingPipeline.Apply creates a log file when FileEnabled is true")]
    public void Apply_CreatesLogFile_WhenFileEnabled()
    {
        using var pipeline = new LoggingPipeline();
        var config = new LoggingConfig { FileEnabled = true, Directory = _tempDir };

        pipeline.Apply(config);

        Directory.GetFiles(_tempDir, "openswfz-*.log")
            .Should().HaveCount(1,
                "Apply with FileEnabled=true must create exactly one timestamped log file");
    }

    [Fact(DisplayName = "FR-022: LoggingPipeline.Apply does not create a log file when FileEnabled is false")]
    public void Apply_DoesNotCreateLogFile_WhenFileDisabled()
    {
        using var pipeline = new LoggingPipeline();
        var config = new LoggingConfig { FileEnabled = false, Directory = _tempDir };

        pipeline.Apply(config);

        Directory.GetFiles(_tempDir, "openswfz-*.log")
            .Should().BeEmpty(
                "Apply with FileEnabled=false must not create any log files");
    }

    [Fact(DisplayName = "FR-022: LoggingPipeline.Apply falls back to console-only when log directory cannot be created")]
    public void Apply_FallsBackToConsoleOnly_WhenDirectoryIsInvalid()
    {
        // Create a FILE at a path, then try to use it as a directory.
        // Directory.CreateDirectory("file/subdir") always fails on all platforms.
        var blockingFile = Path.Combine(_tempDir, "blocking.txt");
        File.WriteAllText(blockingFile, "I block directory creation");
        var invalidDir = Path.Combine(blockingFile, "subdir");

        using var pipeline = new LoggingPipeline();
        var config = new LoggingConfig { FileEnabled = true, Directory = invalidDir };

        // Must not throw — must degrade gracefully to console-only.
        var act = () => pipeline.Apply(config);
        act.Should().NotThrow(
            "Apply must fall back to console-only when the log directory cannot be created");

        // No log file should appear in the temp directory.
        Directory.GetFiles(_tempDir, "openswfz-*.log")
            .Should().BeEmpty(
                "no log file should be created when the directory cannot be set up");
    }

    [Fact(DisplayName = "FR-022: LoggingPipeline file sink uses an independent log level from the console sink")]
    public void Apply_FileSinkUsesIndependentLogLevel()
    {
        var pipeline = new LoggingPipeline();
        var config = new LoggingConfig
        {
            FileEnabled  = true,
            Directory    = _tempDir,
            FileLogLevel = "Warning",   // file: Warning+
        };

        // Console at Information, file at Warning — Debug must not appear in file.
        pipeline.Apply(config, consoleLevel: LogLevel.Information);
        Serilog.Log.Debug("debug-msg-must-not-appear-in-file");
        Serilog.Log.Warning("warning-msg-must-appear-in-file");
        pipeline.Dispose();   // flush buffered file events; second call from using is a no-op

        var files = Directory.GetFiles(_tempDir, "openswfz-*.log");
        files.Should().HaveCount(1);
        var content = File.ReadAllText(files[0]);

        content.Should().Contain("warning-msg-must-appear-in-file",
            "Warning-level messages must appear in the file when FileLogLevel=Warning");
        content.Should().NotContain("debug-msg-must-not-appear-in-file",
            "Debug-level messages must not appear when the file threshold is Warning");
    }

    [Fact(DisplayName = "log-viewer: a logged event reaches disk immediately, without requiring Dispose()")]
    public async Task Apply_LoggedEvent_ReachesDiskWithoutDispose()
    {
        // Regression test for a gap found during f-004 manual verification: the file sink was
        // buffered:true with no flush interval, so a log event could sit in memory indefinitely
        // (until the buffer filled or the process shut down) — which meant GET
        // /api/v1/logs/tail's polling could show stale/empty content for a long time under light
        // logging volume. LoggingPipeline now writes unbuffered (buffered: false — the Serilog
        // default) so this test can observe the write on disk WITHOUT ever calling
        // Dispose()/CloseAndFlush(). (An earlier attempt at this fix used buffered:true plus
        // flushToDiskInterval; that reliably flushed a logger built at process startup but did
        // NOT flush one rebuilt via a later Apply() call from within an HTTP request handler —
        // see the test below — hence the switch to unbuffered writes instead.)
        using var pipeline = new LoggingPipeline();
        var config = new LoggingConfig { FileEnabled = true, Directory = _tempDir };

        pipeline.Apply(config);
        Serilog.Log.Information("logged-event-must-reach-disk-without-dispose");

        // Poll briefly rather than asserting instantaneously, to stay robust against ordinary
        // OS-level write scheduling — but this should resolve near-instantly, not after a
        // meaningful delay, since writes are no longer buffered.
        var files = Directory.GetFiles(_tempDir, "openswfz-*.log");
        files.Should().HaveCount(1);
        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(1);
        string content;
        do
        {
            content = ReadWithSharing(files[0]);
            if (content.Contains("logged-event-must-reach-disk-without-dispose")) break;
            await Task.Delay(20);
        } while (DateTime.UtcNow < deadline);

        content.Should().Contain("logged-event-must-reach-disk-without-dispose",
            "unbuffered writes must reach disk immediately — an operator polling " +
            "GET /api/v1/logs/tail must not have to wait for the daemon to shut down " +
            "(or a buffer to fill) before new log content becomes visible");
    }

    [Fact(DisplayName = "log-viewer: a logged event still reaches disk after a SECOND Apply() (e.g. operator enables file logging at runtime)")]
    public async Task Apply_LoggedEvent_ReachesDiskAfterSecondApplyCall()
    {
        // The real daemon calls Apply() at least twice: once at startup (often with
        // FileEnabled=false, the default), and again whenever the operator changes logging
        // settings via the Settings page while the daemon is already running — the realistic
        // way file logging actually gets turned on. This isolates that exact sequence.
        //
        // This is the scenario that exposed the buffered:true + flushToDiskInterval approach as
        // unreliable: in the real daemon, a logger rebuilt via this second Apply() call (invoked
        // from inside the POST /api/v1/config request handler) never flushed its periodic timer,
        // even after 60+ real seconds — while the exact same two-Apply() sequence in this
        // in-process unit test (no ASP.NET Core hosting involved) flushed within 3 s. Root cause
        // undetermined; switching to unbuffered writes sidesteps it entirely by not depending on
        // a timer at all.
        using var pipeline = new LoggingPipeline();

        pipeline.Apply(new LoggingConfig { FileEnabled = false, Directory = _tempDir });
        pipeline.Apply(new LoggingConfig { FileEnabled = true,  Directory = _tempDir });

        Serilog.Log.Information("logged-event-must-reach-disk-after-second-apply");

        var files = Directory.GetFiles(_tempDir, "openswfz-*.log");
        files.Should().HaveCount(1);
        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(1);
        string content;
        do
        {
            content = ReadWithSharing(files[0]);
            if (content.Contains("logged-event-must-reach-disk-after-second-apply")) break;
            await Task.Delay(20);
        } while (DateTime.UtcNow < deadline);

        content.Should().Contain("logged-event-must-reach-disk-after-second-apply",
            "unbuffered writes must reach disk immediately whether the file sink was built on " +
            "the first Apply() call or a later one — an operator enabling file logging " +
            "mid-session must see the same live-tail behaviour as one who started with it " +
            "already enabled");
    }

    // ── f-004-operator-visibility-improvements (log-viewer): CurrentLogFilePath ──

    [Fact(DisplayName = "log-viewer: CurrentLogFilePath is set to the created file when FileEnabled is true")]
    public void CurrentLogFilePath_IsSet_WhenFileEnabled()
    {
        using var pipeline = new LoggingPipeline();
        var config = new LoggingConfig { FileEnabled = true, Directory = _tempDir };

        pipeline.Apply(config);

        var createdFiles = Directory.GetFiles(_tempDir, "openswfz-*.log");
        createdFiles.Should().HaveCount(1);
        pipeline.CurrentLogFilePath.Should().Be(createdFiles[0],
            "CurrentLogFilePath must be set to the exact path Apply() just created via TryCreateLogFile");
    }

    [Fact(DisplayName = "log-viewer: CurrentLogFilePath is null when FileEnabled is false")]
    public void CurrentLogFilePath_IsNull_WhenFileDisabled()
    {
        using var pipeline = new LoggingPipeline();
        var config = new LoggingConfig { FileEnabled = false, Directory = _tempDir };

        pipeline.Apply(config);

        pipeline.CurrentLogFilePath.Should().BeNull(
            "no log file is created when FileEnabled is false, so there is no active path to expose");
    }

    [Fact(DisplayName = "log-viewer: CurrentLogFilePath is null when the log directory cannot be created")]
    public void CurrentLogFilePath_IsNull_WhenDirectoryIsInvalid()
    {
        var blockingFile = Path.Combine(_tempDir, "blocking.txt");
        File.WriteAllText(blockingFile, "I block directory creation");
        var invalidDir = Path.Combine(blockingFile, "subdir");

        using var pipeline = new LoggingPipeline();
        var config = new LoggingConfig { FileEnabled = true, Directory = invalidDir };

        pipeline.Apply(config);

        pipeline.CurrentLogFilePath.Should().BeNull(
            "file creation failed, so CurrentLogFilePath must reflect that (null), " +
            "the same as the file-logging-disabled case");
    }

    [Fact(DisplayName = "log-viewer: CurrentLogFilePath is reset to null on a subsequent Apply() that disables file logging")]
    public void CurrentLogFilePath_ResetsToNull_OnSubsequentApplyWithFileDisabled()
    {
        using var pipeline = new LoggingPipeline();

        pipeline.Apply(new LoggingConfig { FileEnabled = true, Directory = _tempDir });
        pipeline.CurrentLogFilePath.Should().NotBeNull("first Apply() enabled file logging");

        pipeline.Apply(new LoggingConfig { FileEnabled = false, Directory = _tempDir });
        pipeline.CurrentLogFilePath.Should().BeNull(
            "a later Apply() that disables file logging must clear the stale path from the " +
            "previous call, not leave it pointing at a file that is no longer being written to");
    }

    // ── FR-024: retention enforcement ────────────────────────────────────────

    [Fact(DisplayName = "FR-024: LoggingPipeline.EnforceRetention leaves files untouched when within limit")]
    public void EnforceRetention_LeavesFiles_WhenWithinLimit()
    {
        CreateLogFiles("openswfz-20260101T000000Z.log",
                       "openswfz-20260102T000000Z.log",
                       "openswfz-20260103T000000Z.log");

        LoggingPipeline.EnforceRetention(_tempDir, maxFiles: 5);

        Directory.GetFiles(_tempDir, "openswfz-*.log")
            .Should().HaveCount(3,
                "3 files with a limit of 5 must remain untouched");
    }

    [Fact(DisplayName = "FR-024: LoggingPipeline.EnforceRetention deletes oldest files when over limit")]
    public void EnforceRetention_DeletesOldestFiles_WhenOverLimit()
    {
        var names = new[]
        {
            "openswfz-20260101T000000Z.log",
            "openswfz-20260102T000000Z.log",
            "openswfz-20260103T000000Z.log",
            "openswfz-20260104T000000Z.log",
            "openswfz-20260105T000000Z.log",
        };
        CreateLogFiles(names);

        LoggingPipeline.EnforceRetention(_tempDir, maxFiles: 3);

        var remaining = Directory.GetFiles(_tempDir, "openswfz-*.log")
                                  .Select(Path.GetFileName)
                                  .Order()
                                  .ToArray();

        remaining.Should().HaveCount(3,
            "5 files with limit 3 must leave only the 3 newest");
        remaining.Should().NotContain("openswfz-20260101T000000Z.log",
            "the oldest file must be deleted first");
        remaining.Should().NotContain("openswfz-20260102T000000Z.log",
            "the second-oldest file must also be deleted");
        remaining.Should().Contain("openswfz-20260105T000000Z.log",
            "the newest file must be kept");
    }

    [Fact(DisplayName = "FR-024: LoggingPipeline.EnforceRetention clamps maxFiles ≤ 0 to 1")]
    public void EnforceRetention_ClampsMaxFilesToOne_WhenZeroOrNegative()
    {
        CreateLogFiles("openswfz-20260101T000000Z.log",
                       "openswfz-20260102T000000Z.log",
                       "openswfz-20260103T000000Z.log");

        LoggingPipeline.EnforceRetention(_tempDir, maxFiles: 0);

        var remaining = Directory.GetFiles(_tempDir, "openswfz-*.log");
        remaining.Should().HaveCount(1,
            "maxFiles=0 must be clamped to 1, leaving only the newest file");
        Path.GetFileName(remaining[0]).Should().Be("openswfz-20260103T000000Z.log",
            "the newest (lexicographically last) file must be the one retained");
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    private void CreateLogFiles(params string[] names)
    {
        foreach (var name in names)
            File.WriteAllText(Path.Combine(_tempDir, name), "log content");
    }

    /// <summary>
    /// Reads a file while it may still be open for writing by the Serilog file sink.
    /// A plain <see cref="File.ReadAllText(string)"/> throws <see cref="IOException"/> on
    /// Windows in that case (default share mode is not compatible with the sink's open
    /// handle) — this mirrors the <c>FileShare.ReadWrite</c> approach the real
    /// <c>GET /api/v1/logs/tail</c>/<c>/logs/full</c> endpoints use for the same reason.
    /// </summary>
    private static string ReadWithSharing(string path)
    {
        using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
        using var sr = new StreamReader(fs);
        return sr.ReadToEnd();
    }
}

/// <summary>
/// Defines the "SerialLoggingTests" collection with parallelism disabled within
/// the collection, preventing concurrent mutations of <see cref="Serilog.Log.Logger"/>.
/// </summary>
[CollectionDefinition("SerialLoggingTests", DisableParallelization = true)]
public sealed class SerialLoggingTestsCollection { }
