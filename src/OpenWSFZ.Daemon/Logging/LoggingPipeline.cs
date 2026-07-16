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
internal sealed class LoggingPipeline : IDisposable, ILogFileSource
{
    private LoggingConfig _config       = new();
    private LogLevel      _consoleLevel = LogLevel.Information;

    /// <summary>
    /// Stable-identity wrapper assigned to <see cref="Log.Logger"/> exactly once, on the first
    /// <see cref="Apply"/> call (f-004-operator-visibility-improvements, log-viewer).
    ///
    /// <para>
    /// Previously, <see cref="Apply"/> reassigned <c>Log.Logger</c> itself to a brand-new
    /// <see cref="Serilog.Core.Logger"/> on every call. That silently broke every already-
    /// resolved <c>Microsoft.Extensions.Logging.ILogger&lt;T&gt;</c> in the application (not
    /// just this class's own diagnostics): Serilog.Extensions.Logging's <c>SerilogLogger</c>
    /// resolves <c>Serilog.Log.Logger</c> exactly once, in its own constructor, and caches the
    /// result forever — so an operator enabling file logging via the Settings page while the
    /// daemon was already running would see the new file created, but it would never receive a
    /// single application log line, because every category's cached <c>ILogger&lt;T&gt;</c> kept
    /// writing to whatever logger existed at the moment that category first logged (almost
    /// always well before the reconfigure). Confirmed against a live daemon: ASP.NET Core's own
    /// request-logging middleware kept appending to the OLD file after a runtime reconfigure; the
    /// new file received nothing.
    /// </para>
    ///
    /// <para>
    /// See <see cref="ReconfigurableLogger"/>'s remarks for the fix: <c>Log.Logger</c> is now
    /// assigned to a single stable wrapper instance once; every subsequent <see cref="Apply"/>
    /// call swaps only the wrapper's inner target via <see cref="ReconfigurableLogger.Reconfigure"/>,
    /// which every already-cached <c>ILogger&lt;T&gt;</c> transparently observes.
    /// </para>
    /// </summary>
    private ReconfigurableLogger? _reconfigurableLogger;

    /// <summary>
    /// The inner logger currently wrapped by <see cref="_reconfigurableLogger"/>. Tracked
    /// separately so <see cref="Apply"/> can flush/dispose the previous one (releasing its file
    /// handle) after swapping the wrapper to the new one, and so <see cref="Dispose"/> can flush
    /// the final one on shutdown — <see cref="Log.CloseAndFlush"/> is no longer used for this,
    /// since it would reassign the static <c>Log.Logger</c> itself, which must never change once
    /// <see cref="_reconfigurableLogger"/> is installed.
    /// </summary>
    private Serilog.Core.Logger? _currentInnerLogger;

    /// <summary>
    /// The daemon's currently active log file path, or <see langword="null"/> when file
    /// logging is disabled or the file could not be created
    /// (f-004-operator-visibility-improvements, log-viewer). Set at the same point
    /// <see cref="Apply"/> computes the path via <see cref="TryCreateLogFile"/>; read by the
    /// <c>GET /api/v1/logs/tail</c> and <c>GET /api/v1/logs/full</c> endpoints.
    /// </summary>
    public string? CurrentLogFilePath { get; private set; }

    /// <summary>
    /// Whether the most recent <see cref="Apply"/> call configured a console output sink
    /// (daemon-background-mode, task 7.3) — <see langword="false"/> whenever that call passed
    /// <c>suppressConsoleSink: true</c>. Exposed as a testable public seam so tests can assert
    /// "no console sink was configured" without capturing real console output.
    /// </summary>
    public bool ConsoleSinkConfigured { get; private set; }

    /// <summary>
    /// (Re-)builds the Serilog logger from config. On the first call, installs
    /// <see cref="_reconfigurableLogger"/> as <see cref="Log.Logger"/>; on every subsequent call,
    /// swaps only its inner target (see <see cref="_reconfigurableLogger"/>'s remarks) and
    /// flushes/disposes the previous inner logger.
    /// </summary>
    /// <param name="config">The logging configuration to apply.</param>
    /// <param name="consoleLevel">The minimum level for the console sink (ignored when
    /// <paramref name="suppressConsoleSink"/> is <see langword="true"/>).</param>
    /// <param name="suppressConsoleSink">
    /// When <see langword="true"/> (daemon-background-mode, design.md Decision 4), the console
    /// sink is skipped entirely rather than configured — a background worker has already
    /// detached from its inherited console by this point, and <c>Console.Out</c>/<c>Error</c>
    /// may point at invalid handles (Windows). Not configuring the sink at all is strictly
    /// safer than configuring it and relying on Serilog's sink-dispatch layer to swallow a
    /// misbehaving sink's exceptions. Defaults to <see langword="false"/> so existing
    /// callers/tests are unaffected.
    /// </param>
    public void Apply(
        LoggingConfig config, LogLevel consoleLevel = LogLevel.Information,
        bool suppressConsoleSink = false)
    {
        _config       = config;
        _consoleLevel = consoleLevel;

        var consoleSerilog = ToSerilog(consoleLevel);
        var fileSerilog    = TryParseSerilogLevel(config.FileLogLevel)
                             ?? LogEventLevel.Information;

        // Global minimum must be the less-restrictive of the two sink thresholds.
        // When the console sink is suppressed, the file sink alone determines the global floor.
        var globalMin = suppressConsoleSink
            ? fileSerilog
            : (consoleSerilog <= fileSerilog ? consoleSerilog : fileSerilog);

        var loggerCfg = new LoggerConfiguration().MinimumLevel.Is(globalMin);
        if (!suppressConsoleSink)
            loggerCfg = loggerCfg.WriteTo.Console(restrictedToMinimumLevel: consoleSerilog);

        ConsoleSinkConfigured = !suppressConsoleSink;

        // Reset before recomputing — if file logging is disabled or file creation fails
        // below, CurrentLogFilePath must reflect that (null), not a stale path from a
        // previous Apply()/Rotate() call.
        CurrentLogFilePath = null;

        if (config.FileEnabled)
        {
            var path = TryCreateLogFile(config.Directory);
            if (path is not null)
            {
                // buffered: false (the default) — each event is written and flushed to disk
                // immediately. This project's logging volume is low (occasional Information-
                // level status/QSO events, not a hot path), so the per-write flush cost is
                // negligible, and it sidesteps a genuine reliability gap found in this
                // ASP.NET Core hosting context: buffered:true + flushToDiskInterval's periodic
                // timer reliably flushed a logger built at process startup (verified in an
                // isolated unit test and against a real daemon instance), but did NOT flush a
                // logger rebuilt via a later Apply() call triggered from within an HTTP request
                // handler (i.e. an operator enabling file logging via the Settings page while
                // the daemon is already running — the realistic way this actually happens) —
                // confirmed stuck at 0 bytes after 60+ s of real daemon runtime. Root cause
                // undetermined (suspected interaction between Serilog.Sinks.File's periodic
                // flush timer and the Kestrel/ASP.NET Core hosting environment); unbuffered
                // writes avoid relying on that timer at all (log-viewer,
                // f-004-operator-visibility-improvements).
                loggerCfg = loggerCfg.WriteTo.File(
                    path,
                    restrictedToMinimumLevel: fileSerilog,
                    rollingInterval: RollingInterval.Infinite,
                    buffered: false);
                CurrentLogFilePath = path;
            }
        }

        var newInnerLogger = loggerCfg.CreateLogger();
        var previousInnerLogger = _currentInnerLogger;
        _currentInnerLogger = newInnerLogger;

        if (_reconfigurableLogger is null)
        {
            // First call: install the stable wrapper. Never reassigned again — see
            // ReconfigurableLogger's remarks for why.
            _reconfigurableLogger = new ReconfigurableLogger(newInnerLogger);
            Log.Logger = _reconfigurableLogger;
        }
        else
        {
            // Subsequent calls: swap the wrapper's target first, so every already-cached
            // ILogger<T> starts observing the new logger immediately, THEN flush/dispose the
            // previous inner logger (releasing its file handle) — never the other way around,
            // to avoid disposing the active target out from under an in-flight write.
            _reconfigurableLogger.Reconfigure(newInnerLogger);
            previousInnerLogger?.Dispose();
        }

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

    /// <summary>
    /// Flushes and disposes the current inner logger on shutdown. Deliberately does not call
    /// <see cref="Log.CloseAndFlush"/> or otherwise reassign <see cref="Log.Logger"/> — that
    /// would replace the stable <see cref="_reconfigurableLogger"/> wrapper with Serilog's
    /// no-op <c>SilentLogger</c>, which is unnecessary at process shutdown and would defeat the
    /// entire point of keeping the wrapper's identity stable.
    /// </summary>
    public void Dispose() => _currentInnerLogger?.Dispose();

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

    /// <summary>
    /// Parses a log-level string into a Serilog <see cref="LogEventLevel"/>.
    /// Accepts both MEL names (Trace, Debug, Information, Warning, Error, Critical)
    /// and native Serilog names (Verbose, Fatal) so that config files written by
    /// either the old UI (Serilog names) or the current UI (MEL names) round-trip
    /// correctly. <c>None</c> is excluded because it has no Serilog equivalent and
    /// the file sink is disabled via <see cref="LoggingConfig.FileEnabled"/> instead.
    /// </summary>
    private static LogEventLevel? TryParseSerilogLevel(string? level)
    {
        if (level is null) return null;

        // Prefer MEL names so the file and console log-level selects are consistent.
        // LogLevel.None is excluded — "disable all" is expressed by FileEnabled=false.
        if (Enum.TryParse<LogLevel>(level, ignoreCase: true, out var mel) &&
            mel != LogLevel.None)
            return ToSerilog(mel);

        // Fall back to native Serilog names for backward-compatibility with config
        // files that were written when the UI used Verbose/Fatal.
        if (Enum.TryParse<LogEventLevel>(level, ignoreCase: true, out var serilog))
            return serilog;

        return null;
    }
}
