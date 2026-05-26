## Why

The daemon currently logs exclusively to the console (stdout/stderr). An operator running the daemon headlessly — as a Windows service, a scheduled task, or overnight — has no way to review what happened during a session after the window is closed. File logging with automatic rotation is the standard remedy; without it, any fault that occurs outside the operator's direct observation is undiagnosable.

## What Changes

- **New `logging` section in `AppConfig` / `config.json`** — seven new fields covering the file sink on/off switch, directory, log level, rotation schedule, scheduled rotation time/day, and retention count.
- **File logging sink wired into the daemon at startup** — when `fileEnabled` is true, a rolling file sink is opened alongside the existing console sink. The two sinks are independent; the file log level is configured separately.
- **Session rotation** — each application start opens a new timestamped log file (`openswfz-<UTC-ISO8601>.log`). The previous session's file is never appended to.
- **Scheduled rotation** — the operator may choose hourly, daily (at a specified UTC time), or weekly (on a specified day and UTC time) rotation. Rotation closes the current file and opens a new one.
- **Retention enforcement** — after each rotation the daemon deletes the oldest files until the configured `maxFiles` limit is satisfied.
- **New "Logging" section on the Settings page** — the operator can enable/disable file logging, set the directory, choose the log level and rotation schedule, and set the retention count entirely through the browser UI without editing `config.json` by hand.

## Capabilities

### New Capabilities

- `file-logging`: Configurable file-based logging sink with session and scheduled rotation, independent log-level threshold, and automatic retention management.

### Modified Capabilities

- `configuration`: `AppConfig` schema gains a `logging` object. REST API `GET/POST /api/v1/config` round-trips the new fields automatically (no endpoint changes needed, but the schema must be documented).
- `web-frontend`: Settings page gains a "Logging" section with controls for all seven `logging` fields. The existing Save/Cancel flow covers the new fields without structural changes to the page.
- `daemon-host`: Startup sequence must configure and open the file sink before the web host starts (so early startup logs are captured). Shutdown sequence must flush and close the file sink after the web host stops.

## Impact

- **`src/OpenWSFZ.Daemon`**: `Program.cs` — logging pipeline configured before `WebApplication.Build()`; shutdown flush added to `ApplicationStopped` hook.
- **`src/OpenWSFZ.Abstractions`**: `AppConfig` record gains `LoggingConfig` nested record. `IConfigStore` is unchanged.
- **`web/settings.html`** and **`web/js/settings.js`**: New Logging section added; no structural changes to existing audio-device or port controls.
- **`web/css/app.css`**: Minor additions for the new settings section; no theme changes.
- **New NuGet dependency**: `Serilog.AspNetCore`, `Serilog.Sinks.File`, `Serilog.Sinks.Console` (Serilog replaces `Microsoft.Extensions.Logging` console provider; same `ILogger<T>` surface everywhere — no callsite changes).
- **`Directory.Packages.props`**: Three Serilog packages version-pinned.
- **Existing tests**: No changes required. All existing code uses `ILogger<T>`; the sink swap is transparent at callsites.
