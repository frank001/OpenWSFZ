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
}

/// <summary>
/// Defines the "SerialLoggingTests" collection with parallelism disabled within
/// the collection, preventing concurrent mutations of <see cref="Serilog.Log.Logger"/>.
/// </summary>
[CollectionDefinition("SerialLoggingTests", DisableParallelization = true)]
public sealed class SerialLoggingTestsCollection { }
