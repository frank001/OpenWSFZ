# Developer Briefing — p7 + p6 (combined)

**Date:** 2026-05-25
**Issued by:** QA
**Branch:** create `feat/p7-p6-logging-and-display` from `main` (after p5 is merged)
**Scope:** Audio device friendly-name display (p7) + configurable file logging (p6)

---

## Why one briefing

Both changes touch `AppConfig`, `settings.html`, `settings.js`, and `Program.cs`.
Implementing them separately would require two schema migrations and two sets of
conflicts. Doing them in one commit is cleaner.

---

## Change map

| # | File | Driven by |
|---|---|---|
| C1 | `REQUIREMENTS.md` | p7 + p6 |
| C2 | `Directory.Packages.props` | p6 |
| C3 | `OpenWSFZ.Daemon.csproj` | p6 |
| C4 | `src/OpenWSFZ.Abstractions/AppConfig.cs` | p7 + p6 |
| C5 | `src/OpenWSFZ.Abstractions/LoggingConfig.cs` *(new)* | p6 |
| C6 | `src/OpenWSFZ.Web/AppJsonContext.cs` | p6 |
| C7 | `src/OpenWSFZ.Config/JsonConfigStore.cs` | p7 + p6 |
| C8 | `src/OpenWSFZ.Daemon/Logging/LoggingPipeline.cs` *(new)* | p6 |
| C9 | `src/OpenWSFZ.Daemon/Logging/LogRotationService.cs` *(new)* | p6 |
| C10 | `src/OpenWSFZ.Web/WebApp.cs` | p7 + p6 |
| C11 | `src/OpenWSFZ.Web/WebSocketHub.cs` | p7 |
| C12 | `src/OpenWSFZ.Daemon/Program.cs` | p7 + p6 |
| C13 | `web/settings.html` | p6 |
| C14 | `web/js/settings.js` | p7 + p6 |
| C15 | `tests/OpenWSFZ.Config.Tests/JsonConfigStoreTests.cs` | p7 + p6 |
| C16 | `tests/OpenWSFZ.Config.Tests/ConfigPathResolverTests.cs` | p7 |
| C17 | `tests/OpenWSFZ.Web.Tests/AudioConfigIntegrationTests.cs` | p7 |
| C18 | `tests/OpenWSFZ.Ft8.Tests/LogRotationServiceTests.cs` *(new)* | p6 |

---

## C1 — `REQUIREMENTS.md`

In the functional-requirements table, after the FR-021 row, insert the following four rows:

```
| FR-022 | File logging sink | When logging.fileEnabled is true, the daemon SHALL write
log events to a timestamped file in logging.directory (default: logs/ beside the
executable) in addition to the console sink. The file sink SHALL use an independent
logging.fileLogLevel threshold. An invalid or unwritable directory SHALL produce a
console Warning and the daemon SHALL continue without a file sink. | Must Have |

| FR-023 | Log rotation | Each application start SHALL open a new file
(openswfz-<yyyyMMddTHHmmssZ>.log). The operator MAY configure scheduled rotation:
"session" (startup only), "hourly" (each UTC hour boundary), "daily" (at
logging.rotationTime UTC), or "weekly" (on logging.rotationDayOfWeek at
logging.rotationTime UTC). Rotation timers SHALL recalculate from DateTime.UtcNow
after each firing. | Must Have |

| FR-024 | Log file retention | After each rotation, the daemon SHALL delete the oldest
openswfz-*.log files in the configured directory until at most logging.maxFiles
(default: 7) files remain. maxFiles <= 0 SHALL be clamped to 1 with a Warning.
Deletion failures SHALL be logged at Warning and SHALL NOT abort rotation. | Must Have |

| FR-025 | Audio device friendly name display | The daemon SHALL persist the
human-readable audio device label (audioDeviceFriendlyName) alongside the OS
identifier (audioDeviceId). Wherever the active device is displayed — status bar,
WebSocket events, log messages — the friendly name SHALL be shown when available;
the OS identifier SHALL be the fallback. | Must Have |
```

---

## C2 — `Directory.Packages.props`

Add three Serilog entries inside the existing `<ItemGroup>`:

```xml
<!-- File logging (p6) -->
<PackageVersion Include="Serilog.AspNetCore" Version="9.0.0" />
<PackageVersion Include="Serilog.Sinks.File"    Version="6.0.0" />
<PackageVersion Include="Serilog.Sinks.Console" Version="5.0.0" />
```

Check https://www.nuget.org/packages/ for the latest stable versions of each if
the above are outdated. All three are Apache-2.0 licensed — confirm with `LicenseInventoryCheck`.

---

## C3 — `src/OpenWSFZ.Daemon/OpenWSFZ.Daemon.csproj`

Add inside the first `<ItemGroup>`:

```xml
<PackageReference Include="Serilog.AspNetCore" />
<PackageReference Include="Serilog.Sinks.File" />
<PackageReference Include="Serilog.Sinks.Console" />
```

---

## C4 — `src/OpenWSFZ.Abstractions/AppConfig.cs`

Replace the entire file:

```csharp
namespace OpenWSFZ.Abstractions;

/// <summary>
/// Operator configuration persisted to the config file.
/// </summary>
public sealed record AppConfig(
    /// <summary>OS-internal device identifier (WASAPI GUID, ALSA hw: string, etc.).</summary>
    string? AudioDeviceId           = null,
    /// <summary>Human-readable device label shown in the UI and logs.</summary>
    string? AudioDeviceFriendlyName = null,
    int     Port                    = 8080,
    bool    ShowCycleCountdown      = false,
    /// <summary>
    /// Minimum log level for the console sink.
    /// One of: Trace, Debug, Information, Warning, Error, Critical, None.
    /// Default: "Information".
    /// </summary>
    string  LogLevel                = "Information")
{
    /// <summary>File logging configuration. Always non-null; defaults to file logging disabled.</summary>
    public LoggingConfig Logging { get; init; } = new();
}
```

---

## C5 — `src/OpenWSFZ.Abstractions/LoggingConfig.cs` *(new file)*

```csharp
namespace OpenWSFZ.Abstractions;

/// <summary>
/// Configuration for the file logging sink (FR-022, FR-023, FR-024).
/// All fields have defaults so existing config.json files without a
/// "logging" key continue to deserialise without error.
/// </summary>
public sealed record LoggingConfig
{
    /// <summary>When false (default), no log file is created.</summary>
    public bool   FileEnabled       { get; init; } = false;

    /// <summary>Directory for log files. Relative paths are resolved from the executable.</summary>
    public string Directory         { get; init; } = "logs";

    /// <summary>Minimum severity written to the file sink. Independent of the console level.</summary>
    public string FileLogLevel      { get; init; } = "Information";

    /// <summary>"session" | "hourly" | "daily" | "weekly"</summary>
    public string RotationSchedule  { get; init; } = "daily";

    /// <summary>UTC time of day for daily/weekly rotation. Format: "HH:MM".</summary>
    public string RotationTime      { get; init; } = "00:00";

    /// <summary>Day of week for weekly rotation. E.g. "Monday".</summary>
    public string RotationDayOfWeek { get; init; } = "Monday";

    /// <summary>Maximum number of log files to retain. Values ≤ 0 are clamped to 1.</summary>
    public int    MaxFiles          { get; init; } = 7;
}
```

---

## C6 — `src/OpenWSFZ.Web/AppJsonContext.cs`

Add `LoggingConfig` to the source-generation attributes:

```csharp
// Before (last few lines of the attribute list):
[JsonSerializable(typeof(WsSpectrumMessage))]
[JsonSerializable(typeof(int[]))]
internal sealed partial class AppJsonContext : JsonSerializerContext { }

// After:
[JsonSerializable(typeof(WsSpectrumMessage))]
[JsonSerializable(typeof(int[]))]
[JsonSerializable(typeof(LoggingConfig))]
internal sealed partial class AppJsonContext : JsonSerializerContext { }
```

---

## C7 — `src/OpenWSFZ.Config/JsonConfigStore.cs`

Replace the `try` block inside `Load()` with a migration-aware version that handles both
the legacy `audioDeviceName` rename (p7) and the missing `logging` key (p6 — handled
automatically by the `LoggingConfig` defaults, no code needed):

```csharp
// Before:
try
{
    var json = File.ReadAllText(path);
    return JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)
        ?? new AppConfig();
}

// After:
try
{
    var json   = File.ReadAllText(path);
    var config = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)
        ?? new AppConfig();

    // Migrate legacy audioDeviceName → audioDeviceId (p7 field rename).
    if (config.AudioDeviceId is null)
    {
        using var doc = JsonDocument.Parse(json);
        if (doc.RootElement.TryGetProperty("audioDeviceName", out var legacy) &&
            legacy.ValueKind == JsonValueKind.String)
        {
            config = config with { AudioDeviceId = legacy.GetString() };
        }
    }

    return config;
}
```

No other changes to `JsonConfigStore.cs`. The `Logging` property defaults are handled
by `LoggingConfig`'s own defaults when the `"logging"` key is absent.

---

## C8 — `src/OpenWSFZ.Daemon/Logging/LoggingPipeline.cs` *(new file)*

```csharp
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
```

---

## C9 — `src/OpenWSFZ.Daemon/Logging/LogRotationService.cs` *(new file)*

```csharp
using Microsoft.Extensions.Hosting;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon.Logging;

/// <summary>
/// Fires scheduled log rotation (FR-023) based on <see cref="LoggingConfig.RotationSchedule"/>.
/// Exits immediately if file logging is disabled or schedule is "session".
/// </summary>
internal sealed class LogRotationService : BackgroundService
{
    private readonly LoggingPipeline _pipeline;
    private readonly IConfigStore    _configStore;

    public LogRotationService(LoggingPipeline pipeline, IConfigStore configStore)
    {
        _pipeline    = pipeline;
        _configStore = configStore;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var cfg = _configStore.Current.Logging;

        if (!cfg.FileEnabled || cfg.RotationSchedule == "session")
            return;

        while (!stoppingToken.IsCancellationRequested)
        {
            var delay = CalculateNextBoundary(DateTime.UtcNow, cfg) - DateTime.UtcNow;
            if (delay > TimeSpan.Zero)
            {
                try   { await Task.Delay(delay, stoppingToken); }
                catch (OperationCanceledException) { return; }
            }

            if (stoppingToken.IsCancellationRequested) return;

            _pipeline.Rotate();

            cfg = _configStore.Current.Logging;
            if (!cfg.FileEnabled || cfg.RotationSchedule == "session") return;
        }
    }

    /// <summary>
    /// Returns the next UTC moment at which rotation should fire,
    /// always strictly in the future.
    /// </summary>
    internal static DateTime CalculateNextBoundary(DateTime utcNow, LoggingConfig cfg) =>
        cfg.RotationSchedule switch
        {
            "hourly" => NextHourly(utcNow),
            "daily"  => NextDaily(utcNow, cfg.RotationTime),
            "weekly" => NextWeekly(utcNow, cfg.RotationDayOfWeek, cfg.RotationTime),
            _        => utcNow.AddDays(36500), // "session" or unknown — effectively never
        };

    private static DateTime NextHourly(DateTime utcNow)
    {
        var next = new DateTime(utcNow.Year, utcNow.Month, utcNow.Day,
                                utcNow.Hour, 0, 0, DateTimeKind.Utc).AddHours(1);
        return next > utcNow ? next : next.AddHours(1);
    }

    private static DateTime NextDaily(DateTime utcNow, string rotationTime)
    {
        var (h, m) = ParseHHMM(rotationTime);
        var today  = new DateTime(utcNow.Year, utcNow.Month, utcNow.Day,
                                  h, m, 0, DateTimeKind.Utc);
        return today > utcNow ? today : today.AddDays(1);
    }

    private static DateTime NextWeekly(DateTime utcNow, string dayOfWeek, string rotationTime)
    {
        var (h, m) = ParseHHMM(rotationTime);
        var target = Enum.TryParse<DayOfWeek>(dayOfWeek, ignoreCase: true, out var dow)
            ? dow : DayOfWeek.Monday;

        var candidate = new DateTime(utcNow.Year, utcNow.Month, utcNow.Day,
                                     h, m, 0, DateTimeKind.Utc);
        var daysUntil = ((int)target - (int)candidate.DayOfWeek + 7) % 7;
        candidate = candidate.AddDays(daysUntil);
        return candidate > utcNow ? candidate : candidate.AddDays(7);
    }

    private static (int h, int m) ParseHHMM(string hhmm)
    {
        var parts = hhmm.Split(':');
        return parts.Length == 2
               && int.TryParse(parts[0], out var h) && h is >= 0 and <= 23
               && int.TryParse(parts[1], out var m) && m is >= 0 and <= 59
            ? (h, m)
            : (0, 0);
    }
}
```

---

## C10 — `src/OpenWSFZ.Web/WebApp.cs`

### C10a — Add `configureServices` parameter

In the `Create` method signature, add one optional parameter at the end:

```csharp
// Before:
public static WebApplication Create(
    int port,
    ...
    Func<Task>?                                   restartPipeline      = null)

// After:
public static WebApplication Create(
    int port,
    ...
    Func<Task>?                                   restartPipeline      = null,
    Action<IServiceCollection>?                   configureServices    = null)
```

In the services section of `Create`, add the invocation immediately after the existing
`AddSingleton<IAudioDeviceProvider>` lines:

```csharp
// After the audioProvider / audioProviderFactory block:
configureServices?.Invoke(builder.Services);
```

### C10b — Friendly name in `GET /api/v1/status`

```csharp
// Before (line 131):
AudioDevice:   store.Current.AudioDeviceName,

// After:
AudioDevice:   store.Current.AudioDeviceFriendlyName ?? store.Current.AudioDeviceId,
```

---

## C11 — `src/OpenWSFZ.Web/WebSocketHub.cs`

Line 138 — initial status event sent on WebSocket connect:

```csharp
// Before:
AudioDevice:   configStore.Current.AudioDeviceName,

// After:
AudioDevice:   configStore.Current.AudioDeviceFriendlyName ?? configStore.Current.AudioDeviceId,
```

---

## C12 — `src/OpenWSFZ.Daemon/Program.cs`

Apply all changes below in order. They are logically independent and can be made in any sequence within the file.

### C12a — Logging setup section (lines 24–50): replace with Serilog

```csharp
// ── Before (lines 24–50) ──────────────────────────────────────────────────────
// ── Logging setup (FR-019) ────────────────────────────────────────────────────
var logLevel = Enum.TryParse<LogLevel>(configStore.Current.LogLevel, ignoreCase: true, out var parsedLevel)
    ? parsedLevel
    : LogLevel.Information;

var frameworkLevel = logLevel > LogLevel.Warning ? logLevel : LogLevel.Warning;

void ConfigureLogging(ILoggingBuilder lb)
{
    lb.ClearProviders();
    lb.AddProvider(new StderrLoggerProvider(logLevel));
    lb.SetMinimumLevel(logLevel);
    lb.AddFilter("Microsoft", frameworkLevel);
    lb.AddFilter("System",    frameworkLevel);
}

using var loggerFactory = LoggerFactory.Create(ConfigureLogging);
```

```csharp
// ── After ─────────────────────────────────────────────────────────────────────
// ── Logging setup (FR-019, FR-022, FR-023, FR-024) ────────────────────────────
var logLevel = Enum.TryParse<LogLevel>(configStore.Current.LogLevel, ignoreCase: true, out var parsedLevel)
    ? parsedLevel
    : LogLevel.Information;

var frameworkLevel = logLevel > LogLevel.Warning ? logLevel : LogLevel.Warning;

// Bootstrap the Serilog pipeline before any loggerFactory is created so that
// CaptureManager / CycleFramer / Ft8Decoder startup logs reach the file sink.
var loggingPipeline = new LoggingPipeline();
loggingPipeline.Apply(configStore.Current.Logging, consoleLevel: logLevel);

// Early loggerFactory delegates to Log.Logger (set above).
using var loggerFactory = new Serilog.Extensions.Logging.SerilogLoggerFactory(
    Log.Logger, dispose: false);

void ConfigureLogging(ILoggingBuilder lb)
{
    lb.ClearProviders();
    lb.AddSerilog(Log.Logger, dispose: false);
    lb.SetMinimumLevel(logLevel);
    lb.AddFilter("Microsoft", frameworkLevel);
    lb.AddFilter("System",    frameworkLevel);
}
```

### C12b — `CaptureFailed` handler (lines 124–132): device ID + friendly name

```csharp
// Before:
startupLogger.LogError(ex,
    "Audio capture failed on '{Device}': {Message}",
    configStore.Current.AudioDeviceName, ex.Message);

var device = configStore.Current.AudioDeviceName;

// After:
startupLogger.LogError(ex,
    "Audio capture failed on '{Device}': {Message}",
    configStore.Current.AudioDeviceFriendlyName ?? configStore.Current.AudioDeviceId,
    ex.Message);

var device = configStore.Current.AudioDeviceId;
```

### C12c — Watchdog `restartPipeline` lambda (lines 165–175): device ID + friendly name

```csharp
// Before:
var device = configStore.Current.AudioDeviceName;
startupLogger.LogWarning(
    "Watchdog: audio silent for 15 s while capturing on '{Device}' — restarting pipeline.",
    device);
await RestartPipelineAsync(device, stopCaptureManager: true);
// ...
startupLogger.LogError(ex,
    "Watchdog pipeline restart failed on device '{Device}': {Message}",
    configStore.Current.AudioDeviceName, ex.Message);

// After:
var device      = configStore.Current.AudioDeviceId;
var displayName = configStore.Current.AudioDeviceFriendlyName ?? device;
startupLogger.LogWarning(
    "Watchdog: audio silent for 15 s while capturing on '{Device}' — restarting pipeline.",
    displayName);
await RestartPipelineAsync(device, stopCaptureManager: true);
// ...
startupLogger.LogError(ex,
    "Watchdog pipeline restart failed on device '{Device}': {Message}",
    configStore.Current.AudioDeviceFriendlyName ?? configStore.Current.AudioDeviceId,
    ex.Message);
```

### C12d — `ApplicationStarted` hook (lines 198–200)

```csharp
// Before:
var deviceName = configStore.Current.AudioDeviceName;

// After:
var deviceName = configStore.Current.AudioDeviceId;
```

### C12e — `OnSaved` handler (lines 228–231): device ID + re-apply logging on save

```csharp
// Before:
string? runningDevice = configStore.Current.AudioDeviceName;
configStore.OnSaved += newConfig =>
{
    var newDevice = newConfig.AudioDeviceName;

// After:
string? runningDevice = configStore.Current.AudioDeviceId;
configStore.OnSaved += newConfig =>
{
    // Re-apply the logging pipeline on every save so file-logging changes
    // and console level changes take effect immediately (FR-022, FR-019).
    var newConsoleLevel = Enum.TryParse<LogLevel>(newConfig.LogLevel,
        ignoreCase: true, out var nl) ? nl : LogLevel.Information;
    loggingPipeline.Apply(newConfig.Logging, consoleLevel: newConsoleLevel);

    var newDevice = newConfig.AudioDeviceId;
```

### C12f — `WebApp.Create` call: register `LoggingPipeline` and `LogRotationService`

```csharp
// Before:
var app = WebApp.Create(
    port,
    configStore:          configStore,
    ...
    restartPipeline:      restartPipeline);

// After:
var app = WebApp.Create(
    port,
    configStore:          configStore,
    ...
    restartPipeline:      restartPipeline,
    configureServices:    services =>
    {
        services.AddSingleton(loggingPipeline);
        services.AddHostedService<LogRotationService>();
    });
```

### C12g — `ApplicationStopping` hook: flush the file sink on shutdown

Inside the `ApplicationStopping.Register` callback, add one line at the very end,
after `framerOutput.Writer.TryComplete()`:

```csharp
// After framerOutput.Writer.TryComplete():
loggingPipeline.Dispose();    // flush buffered file events before process exit
```

---

## C13 — `web/settings.html`

Insert the following block immediately **before** the `<div class="form-footer">` at line 74:

```html
      <fieldset id="logging-settings">
        <legend>File logging</legend>

        <div class="field-group">
          <label class="checkbox-label">
            <input type="checkbox" id="logging-file-enabled" />
            Write logs to a file
          </label>
        </div>

        <div class="field-group" id="logging-dependent">
          <label for="logging-directory">Log directory</label>
          <input type="text" id="logging-directory" placeholder="logs" />
          <p class="field-hint">Relative to the executable, or an absolute path.</p>
        </div>

        <div class="field-group" id="logging-level-group">
          <label for="logging-file-log-level">File log level</label>
          <select id="logging-file-log-level">
            <option value="Verbose">Verbose</option>
            <option value="Debug">Debug</option>
            <option value="Information">Information (default)</option>
            <option value="Warning">Warning</option>
            <option value="Error">Error</option>
            <option value="Fatal">Fatal</option>
          </select>
        </div>

        <div class="field-group">
          <label for="logging-rotation-schedule">Rotation schedule</label>
          <select id="logging-rotation-schedule">
            <option value="session">Session — new file on each start</option>
            <option value="hourly">Hourly — at each UTC hour boundary</option>
            <option value="daily" selected>Daily — at a configured UTC time</option>
            <option value="weekly">Weekly — on a configured day and time</option>
          </select>
        </div>

        <div class="field-group" id="logging-time-group">
          <label for="logging-rotation-time">Rotation time (UTC, HH:MM)</label>
          <input type="time" id="logging-rotation-time" value="00:00" />
        </div>

        <div class="field-group" id="logging-day-group" style="display:none">
          <label for="logging-rotation-day">Day of week</label>
          <select id="logging-rotation-day">
            <option value="Monday">Monday</option>
            <option value="Tuesday">Tuesday</option>
            <option value="Wednesday">Wednesday</option>
            <option value="Thursday">Thursday</option>
            <option value="Friday">Friday</option>
            <option value="Saturday">Saturday</option>
            <option value="Sunday">Sunday</option>
          </select>
        </div>

        <div class="field-group">
          <label for="logging-max-files">Maximum files to keep</label>
          <input type="number" id="logging-max-files" min="1" value="7" />
        </div>

      </fieldset>
```

---

## C14 — `web/js/settings.js`

Replace the entire file:

```js
/**
 * Settings page logic.
 * - Loads audio devices and current config from the API on page load.
 * - Populates the device selector, port field, and logging controls.
 * - Handles Save: POSTs updated config and shows success/error feedback.
 *
 * @module settings
 */

import { getConfig, getDevices, postConfig } from './api.js';

const deviceSelect          = /** @type {HTMLSelectElement} */ (document.getElementById('device-select'));
const portInput             = /** @type {HTMLInputElement}  */ (document.getElementById('port-input'));
const cycleCountdownToggle  = /** @type {HTMLInputElement}  */ (document.getElementById('cycle-countdown-toggle'));
const logLevelSelect        = /** @type {HTMLSelectElement} */ (document.getElementById('log-level-select'));
const saveBtn               = /** @type {HTMLButtonElement} */ (document.getElementById('save-btn'));
const feedback              = /** @type {HTMLElement}       */ (document.getElementById('feedback'));

// Logging controls
const loggingFileEnabled    = /** @type {HTMLInputElement}  */ (document.getElementById('logging-file-enabled'));
const loggingDirectory      = /** @type {HTMLInputElement}  */ (document.getElementById('logging-directory'));
const loggingFileLogLevel   = /** @type {HTMLSelectElement} */ (document.getElementById('logging-file-log-level'));
const loggingSchedule       = /** @type {HTMLSelectElement} */ (document.getElementById('logging-rotation-schedule'));
const loggingTime           = /** @type {HTMLInputElement}  */ (document.getElementById('logging-rotation-time'));
const loggingDay            = /** @type {HTMLSelectElement} */ (document.getElementById('logging-rotation-day'));
const loggingMaxFiles       = /** @type {HTMLInputElement}  */ (document.getElementById('logging-max-files'));
const loggingDependent      = /** @type {HTMLElement}       */ (document.getElementById('logging-dependent'));
const loggingTimeGroup      = /** @type {HTMLElement}       */ (document.getElementById('logging-time-group'));
const loggingDayGroup       = /** @type {HTMLElement}       */ (document.getElementById('logging-day-group'));

// ── Load config and devices ───────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const [config, devices] = await Promise.all([getConfig(), getDevices()]);

    // Populate device selector.
    deviceSelect.innerHTML = '';
    const noneOpt = document.createElement('option');
    noneOpt.value       = '';
    noneOpt.textContent = '(none)';
    deviceSelect.appendChild(noneOpt);

    if (devices.length === 0) {
      const noDevOpt = document.createElement('option');
      noDevOpt.disabled     = true;
      noDevOpt.textContent  = 'No devices found';
      deviceSelect.appendChild(noDevOpt);
    } else {
      for (const dev of devices) {
        const opt = document.createElement('option');
        opt.value       = dev.id;
        opt.textContent = dev.name;
        deviceSelect.appendChild(opt);
      }
    }

    // Pre-select the configured device (p7: use audioDeviceId, not audioDeviceName).
    deviceSelect.value = config.audioDeviceId ?? '';

    // Pre-fill port.
    portInput.value = String(config.port);

    // Pre-check cycle countdown.
    cycleCountdownToggle.checked = config.showCycleCountdown ?? false;

    // Pre-select console log level.
    logLevelSelect.value = config.logLevel ?? 'Information';

    // Pre-fill logging controls (p6).
    const lg = config.logging ?? {};
    loggingFileEnabled.checked  = lg.fileEnabled       ?? false;
    loggingDirectory.value      = lg.directory         ?? 'logs';
    loggingFileLogLevel.value   = lg.fileLogLevel      ?? 'Information';
    loggingSchedule.value       = lg.rotationSchedule  ?? 'daily';
    loggingTime.value           = lg.rotationTime      ?? '00:00';
    loggingDay.value            = lg.rotationDayOfWeek ?? 'Monday';
    loggingMaxFiles.value       = String(lg.maxFiles   ?? 7);

    updateLoggingVisibility();

  } catch (err) {
    showFeedback(`Failed to load settings: ${err.message}`, 'error');
  }
});

// ── Visibility helpers (p6) ───────────────────────────────────────────────

function updateLoggingVisibility() {
  const enabled  = loggingFileEnabled.checked;
  const schedule = loggingSchedule.value;

  // Grey out all dependent controls when file logging is disabled.
  loggingDependent.querySelectorAll('input, select').forEach(el => {
    /** @type {HTMLInputElement|HTMLSelectElement} */ (el).disabled = !enabled;
  });
  loggingFileLogLevel.disabled     = !enabled;
  loggingSchedule.disabled         = !enabled;
  loggingTime.disabled             = !enabled;
  loggingDay.disabled              = !enabled;
  loggingMaxFiles.disabled         = !enabled;

  // Show/hide time and day based on schedule.
  loggingTimeGroup.style.display = (enabled && (schedule === 'daily' || schedule === 'weekly'))
      ? '' : 'none';
  loggingDayGroup.style.display  = (enabled && schedule === 'weekly')
      ? '' : 'none';
}

loggingFileEnabled.addEventListener('change', updateLoggingVisibility);
loggingSchedule.addEventListener('change',    updateLoggingVisibility);

// ── Save ──────────────────────────────────────────────────────────────────

saveBtn.addEventListener('click', async () => {
  saveBtn.disabled = true;
  clearFeedback();

  // p7: capture both device ID (for WASAPI) and friendly name (for display).
  const audioDeviceId           = deviceSelect.value.trim() || null;
  const selectedOption          = deviceSelect.options[deviceSelect.selectedIndex];
  const audioDeviceFriendlyName = audioDeviceId
      ? (selectedOption?.textContent?.trim() || null)
      : null;

  const port               = parseInt(portInput.value, 10);
  const showCycleCountdown = cycleCountdownToggle.checked;
  const logLevel           = logLevelSelect.value;

  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    showFeedback('Port must be a number between 1 and 65535.', 'error');
    saveBtn.disabled = false;
    return;
  }

  // p6: collect logging config.
  const logging = {
    fileEnabled:       loggingFileEnabled.checked,
    directory:         loggingDirectory.value.trim() || 'logs',
    fileLogLevel:      loggingFileLogLevel.value,
    rotationSchedule:  loggingSchedule.value,
    rotationTime:      loggingTime.value || '00:00',
    rotationDayOfWeek: loggingDay.value,
    maxFiles:          parseInt(loggingMaxFiles.value, 10) || 7,
  };

  try {
    await postConfig({
      audioDeviceId,
      audioDeviceFriendlyName,
      port,
      showCycleCountdown,
      logLevel,
      logging,
    });
    showFeedback('Saved ✓', 'success');
    setTimeout(() => { saveBtn.disabled = false; }, 2000);
  } catch (err) {
    showFeedback(`Save failed — ${err.message}`, 'error');
    saveBtn.disabled = false;
  }
});

// ── Helpers ───────────────────────────────────────────────────────────────

function showFeedback(message, type) {
  feedback.textContent = message;
  feedback.className   = type;
}

function clearFeedback() {
  feedback.textContent = '';
  feedback.className   = '';
}
```

---

## C15 — `tests/OpenWSFZ.Config.Tests/JsonConfigStoreTests.cs`

### C15a — Rename `AudioDeviceName` → `AudioDeviceId` throughout

Apply these substitutions (all occurrences):

| Before | After |
|---|---|
| `new AppConfig(AudioDeviceName: "TestMic", Port: 9090)` | `new AppConfig(AudioDeviceId: "TestMic", Port: 9090)` |
| `store.Current.AudioDeviceName.Should().Be("TestMic")` | `store.Current.AudioDeviceId.Should().Be("TestMic")` |
| `store.Current.AudioDeviceName.Should().BeNull()` | `store.Current.AudioDeviceId.Should().BeNull()` |
| `new AppConfig(AudioDeviceName: "SavedMic", Port: 7070)` | `new AppConfig(AudioDeviceId: "SavedMic", Port: 7070)` |
| `onDisk!.AudioDeviceName.Should().Be("SavedMic")` | `onDisk!.AudioDeviceId.Should().Be("SavedMic")` |
| `store.Current.AudioDeviceName.Should().Be("SavedMic")` | `store.Current.AudioDeviceId.Should().Be("SavedMic")` |

Lines affected: 41, 50, 67, 87, 131, 144, 154, 158, 206.

### C15b — Update the secondary assertion in both backward-compat tests

Line 131 and line 206 both assert `AudioDeviceName` as a "other fields preserved" check
inside tests that write `{"audioDeviceName":"TestMic","port":9090}`. After the rename,
update the assertions and their messages:

```csharp
// Before:
store.Current.AudioDeviceName.Should().Be("TestMic",
    "other fields must be preserved when ShowCycleCountdown is absent");

// After:
store.Current.AudioDeviceId.Should().Be("TestMic",
    "legacy audioDeviceName must be migrated to AudioDeviceId");
```

### C15c — Add two new tests at the end of the class

```csharp
// ── p7: audioDeviceName migration ────────────────────────────────────────────

[Fact(DisplayName = "FR-025: Legacy audioDeviceName config is migrated to AudioDeviceId on load")]
public void Load_MigratesLegacyAudioDeviceName_ToAudioDeviceId()
{
    using var dir = new TempDirectory();
    var configPath = System.IO.Path.Combine(dir.Path, "config.json");

    File.WriteAllText(configPath, """{"audioDeviceName":"LegacyDevice","port":8080}""");

    var store = new JsonConfigStore(configPath);

    store.Current.AudioDeviceId.Should().Be("LegacyDevice",
        "the legacy audioDeviceName value must be promoted to AudioDeviceId");
    store.Current.AudioDeviceFriendlyName.Should().BeNull(
        "no friendly name was stored in the legacy config");
    store.Current.Port.Should().Be(8080);
}

[Fact(DisplayName = "FR-025: AudioDeviceFriendlyName round-trips via config file")]
public async Task AudioDeviceFriendlyName_RoundTrips()
{
    using var dir = new TempDirectory();
    var configPath = System.IO.Path.Combine(dir.Path, "config.json");
    var store = new JsonConfigStore(configPath);

    await store.SaveAsync(new AppConfig(
        AudioDeviceId:           "{0.0.1.00000000}.{test-guid}",
        AudioDeviceFriendlyName: "Test Microphone"));

    var reloaded = new JsonConfigStore(configPath);
    reloaded.Current.AudioDeviceId.Should().Be("{0.0.1.00000000}.{test-guid}");
    reloaded.Current.AudioDeviceFriendlyName.Should().Be("Test Microphone");
}

// ── p6: LoggingConfig defaults and round-trip ─────────────────────────────────

[Fact(DisplayName = "FR-022: AppConfig.Logging defaults to file logging disabled")]
public void AppConfig_Logging_DefaultsToFileDisabled()
{
    var config = new AppConfig();

    config.Logging.FileEnabled.Should().BeFalse(
        "file logging must be opt-in; operators are not surprised by unexpected files on first run");
    config.Logging.Directory.Should().Be("logs");
    config.Logging.FileLogLevel.Should().Be("Information");
    config.Logging.RotationSchedule.Should().Be("daily");
    config.Logging.MaxFiles.Should().Be(7);
}

[Fact(DisplayName = "FR-022: AppConfig.Logging round-trips via config file")]
public async Task AppConfig_Logging_RoundTrips()
{
    using var dir = new TempDirectory();
    var configPath = System.IO.Path.Combine(dir.Path, "config.json");
    var store = new JsonConfigStore(configPath);

    var logging = new LoggingConfig { FileEnabled = true, Directory = "C:\\logs", MaxFiles = 3 };
    await store.SaveAsync(new AppConfig() { Logging = logging });

    var reloaded = new JsonConfigStore(configPath);
    reloaded.Current.Logging.FileEnabled.Should().BeTrue();
    reloaded.Current.Logging.Directory.Should().Be("C:\\logs");
    reloaded.Current.Logging.MaxFiles.Should().Be(3);
}

[Fact(DisplayName = "FR-022: AppConfig.Logging defaults when logging key absent from config file")]
public void AppConfig_Logging_Defaults_WhenAbsentFromFile()
{
    using var dir = new TempDirectory();
    var configPath = System.IO.Path.Combine(dir.Path, "config.json");
    File.WriteAllText(configPath, """{"audioDeviceId":"mic","port":8080}""");

    var store = new JsonConfigStore(configPath);

    store.Current.Logging.FileEnabled.Should().BeFalse(
        "Logging must default to disabled when the key is absent");
}
```

---

## C16 — `tests/OpenWSFZ.Config.Tests/ConfigPathResolverTests.cs`

Line 78:

```csharp
// Before:
config.AudioDeviceName.Should().BeNull(
    "no audio device is selected by default");

// After:
config.AudioDeviceId.Should().BeNull(
    "no audio device is selected by default");
```

---

## C17 — `tests/OpenWSFZ.Web.Tests/AudioConfigIntegrationTests.cs`

### C17a — `GetConfig_Returns200WithConfigFields` (lines 137–138)

```csharp
// Before:
doc.RootElement.TryGetProperty("audioDeviceName", out _).Should().BeTrue(
    "audioDeviceName field must be present in the config response");

// After:
doc.RootElement.TryGetProperty("audioDeviceId", out _).Should().BeTrue(
    "audioDeviceId field must be present in the config response");
```

### C17b — `PostConfig_PersistsUpdatedConfig_AndSubsequentGetReflectsChange` (lines 153–169)

```csharp
// Before:
var payload = """{"audioDeviceName":"NewMic","port":9090}""";
// ...
postDoc.RootElement.GetProperty("audioDeviceName").GetString().Should().Be("NewMic");
// ...
getDoc.RootElement.GetProperty("audioDeviceName").GetString().Should().Be("NewMic");

// After:
var payload = """{"audioDeviceId":"NewMic","audioDeviceFriendlyName":"New Microphone","port":9090}""";
// ...
postDoc.RootElement.GetProperty("audioDeviceId").GetString().Should().Be("NewMic");
postDoc.RootElement.GetProperty("audioDeviceFriendlyName").GetString()
    .Should().Be("New Microphone");
// ...
getDoc.RootElement.GetProperty("audioDeviceId").GetString().Should().Be("NewMic");
getDoc.RootElement.GetProperty("audioDeviceFriendlyName").GetString()
    .Should().Be("New Microphone");
```

---

## C18 — `tests/OpenWSFZ.Ft8.Tests/LogRotationServiceTests.cs` *(new file)*

```csharp
using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon.Logging;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>Unit tests for <see cref="LogRotationService.CalculateNextBoundary"/>.</summary>
public sealed class LogRotationServiceTests
{
    private static LoggingConfig Cfg(string schedule, string time = "00:00", string day = "Monday") =>
        new() { FileEnabled = true, RotationSchedule = schedule, RotationTime = time, RotationDayOfWeek = day };

    [Fact(DisplayName = "FR-023: CalculateNextBoundary hourly returns next full UTC hour")]
    public void Hourly_ReturnsNextFullHour()
    {
        var now    = new DateTime(2026, 5, 25, 2, 47, 0, DateTimeKind.Utc);
        var result = LogRotationService.CalculateNextBoundary(now, Cfg("hourly"));

        result.Should().Be(new DateTime(2026, 5, 25, 3, 0, 0, DateTimeKind.Utc));
    }

    [Fact(DisplayName = "FR-023: CalculateNextBoundary daily before rotation time returns same day")]
    public void Daily_BeforeRotationTime_ReturnsSameDay()
    {
        var now    = new DateTime(2026, 5, 25, 2, 59, 0, DateTimeKind.Utc);
        var result = LogRotationService.CalculateNextBoundary(now, Cfg("daily", "03:00"));

        result.Should().Be(new DateTime(2026, 5, 25, 3, 0, 0, DateTimeKind.Utc));
    }

    [Fact(DisplayName = "FR-023: CalculateNextBoundary daily after rotation time returns next day")]
    public void Daily_AfterRotationTime_ReturnsNextDay()
    {
        var now    = new DateTime(2026, 5, 25, 3, 1, 0, DateTimeKind.Utc);
        var result = LogRotationService.CalculateNextBoundary(now, Cfg("daily", "03:00"));

        result.Should().Be(new DateTime(2026, 5, 26, 3, 0, 0, DateTimeKind.Utc));
    }

    [Fact(DisplayName = "FR-023: CalculateNextBoundary weekly returns correct next occurrence")]
    public void Weekly_ReturnsNextOccurrenceOfConfiguredDay()
    {
        // It is Monday 00:01 — next Monday 00:00 is 7 days away.
        var now    = new DateTime(2026, 5, 25, 0, 1, 0, DateTimeKind.Utc); // Monday
        var result = LogRotationService.CalculateNextBoundary(now, Cfg("weekly", "00:00", "Monday"));

        result.Should().Be(new DateTime(2026, 6, 1, 0, 0, 0, DateTimeKind.Utc));
    }

    [Fact(DisplayName = "FR-023: CalculateNextBoundary always returns a strictly future time")]
    public void AlwaysReturnsFutureTime()
    {
        // Clock is exactly at a daily rotation boundary.
        var exactBoundary = new DateTime(2026, 5, 25, 3, 0, 0, DateTimeKind.Utc);
        var result        = LogRotationService.CalculateNextBoundary(exactBoundary, Cfg("daily", "03:00"));

        result.Should().BeAfter(exactBoundary,
            "the next rotation must always be in the future, never at or before now");
    }
}
```

> **Note:** `LogRotationService` lives in `OpenWSFZ.Daemon`. The test project that references it
> must either be `OpenWSFZ.Daemon.Tests` (create if it doesn't exist) or the existing
> `OpenWSFZ.Ft8.Tests` must add a project reference to `OpenWSFZ.Daemon`. The simpler path is to
> move these tests into a new `tests/OpenWSFZ.Daemon.Tests/` project referencing `OpenWSFZ.Daemon`,
> or make `CalculateNextBoundary` accessible via `InternalsVisibleTo`. Choose whichever is consistent
> with the existing test project layout.

---

## Verification

```
dotnet build -c Release        # 0 errors, 0 warnings
dotnet test  -c Release        # all existing tests green + 7 new tests pass
```

Then manual smoke test:

1. Start the daemon. Status bar must show `(no device)` or the GUID fallback (legacy config).
2. Open Settings → select a device → Save. Status bar must show the human-readable label.
3. Restart the daemon — label persists.
4. In Settings → Logging: enable file logging, set directory to `logs`, Daily at `00:01`, Max files 3 → Save.
5. Confirm `logs/openswfz-<timestamp>.log` is created immediately.
6. Confirm the log file contains the same entries as the console.
7. Advance the system clock past `00:01` UTC (or temporarily set RotationTime to `<now + 2 min>`) and confirm a new file opens and the old one is closed.
