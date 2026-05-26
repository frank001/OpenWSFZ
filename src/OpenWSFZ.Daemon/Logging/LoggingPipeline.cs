using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using Serilog;
using Serilog.Events;

namespace OpenWSFZ.Daemon.Logging;

/// <summary>
/// Owns the Serilog logging pipeline.
/// Call <see cref="Apply"/> once at bootstrap and again on every config save.
/// Call <see cref="Dispose"/> on shutdown to flush buffered file events.
/// </summary>
internal sealed class LoggingPipeline : IDisposable
{
    private LoggingConfig _config       = new();
    private LogLevel      _consoleLevel = LogLevel.Information;

    /// <summary>
    /// (Re-)builds the Serilog logger from config and assigns <see cref="Log.Logger"/>.
    /// Flushes the previous logger before replacing it.
    /// </summary>
    public void Apply(LoggingConfig config, LogLevel consoleLevel = LogLevel.Information)
    {
        _config       = config;
        _consoleLevel = consoleLevel;

        var consoleSerilog = ToSerilog(consoleLevel);
        var fileSerilog    = TryParseSerilogLevel(config.FileLogLevel)
                             ?? LogEventLevel.Information;

        // Global minimum must be the less-restrictive of the two sink thresholds.
        var globalMin = consoleSerilog <= fileSerilog ? consoleSerilog : fileSerilog;

        var loggerCfg = new LoggerConfiguration()
            .MinimumLevel.Is(globalMin)
            .WriteTo.Console(restrictedToMinimumLevel: consoleSerilog);

        if (config.FileEnabled)
        {
            var path = TryCreateLogFile(config.Directory);
            if (path is not null)
            {
                loggerCfg = loggerCfg.WriteTo.File(
                    path,
                    restrictedToMinimumLevel: fileSerilog,
                    rollingInterval: RollingInterval.Infinite,
                    buffered: true);
            }
        }

        Log.CloseAndFlush();
        Log.Logger = loggerCfg.CreateLogger();

        if (config.FileEnabled)
            EnforceRetention(config.Directory, config.MaxFiles);
    }

    /// <summary>
    /// Closes the current file and opens a new timestamped one (scheduled rotation).
    /// Re-reads the stored config so a settings change takes effect on next rotation.
    /// </summary>
    public void Rotate() => Apply(_config, _consoleLevel);

    /// <summary>
    /// Deletes the oldest <c>openswfz-*.log</c> files until at most
    /// <paramref name="maxFiles"/> remain. Failures are logged at Warning.
    /// </summary>
    public static void EnforceRetention(string directory, int maxFiles)
    {
        if (maxFiles <= 0) maxFiles = 1;
        try
        {
            var files = System.IO.Directory
                              .GetFiles(directory, "openswfz-*.log")
                              .OrderBy(f => f)          // ISO-8601 names sort chronologically
                              .ToArray();

            for (var i = 0; i < files.Length - maxFiles; i++)
            {
                try   { File.Delete(files[i]); }
                catch (Exception ex)
                {
                    Log.Warning(ex,
                        "Could not delete old log file '{File}' during retention enforcement.",
                        files[i]);
                }
            }
        }
        catch (Exception ex)
        {
            Log.Warning(ex,
                "Could not enforce log retention in '{Directory}'.", directory);
        }
    }

    public void Dispose() => Log.CloseAndFlush();

    // ── Private helpers ──────────────────────────────────────────────────────

    private static string? TryCreateLogFile(string directory)
    {
        try
        {
            System.IO.Directory.CreateDirectory(directory);
            return Path.Combine(directory,
                $"openswfz-{DateTime.UtcNow:yyyyMMddTHHmmssZ}.log");
        }
        catch (Exception ex)
        {
            Log.Warning(ex,
                "Cannot create log directory '{Directory}' — file sink disabled.",
                directory);
            return null;
        }
    }

    internal static LogEventLevel ToSerilog(LogLevel level) => level switch
    {
        LogLevel.Trace       => LogEventLevel.Verbose,
        LogLevel.Debug       => LogEventLevel.Debug,
        LogLevel.Information => LogEventLevel.Information,
        LogLevel.Warning     => LogEventLevel.Warning,
        LogLevel.Error       => LogEventLevel.Error,
        LogLevel.Critical    => LogEventLevel.Fatal,
        _                    => LogEventLevel.Information,
    };

    private static LogEventLevel? TryParseSerilogLevel(string? level) =>
        Enum.TryParse<LogEventLevel>(level, ignoreCase: true, out var parsed)
            ? parsed : null;
}
