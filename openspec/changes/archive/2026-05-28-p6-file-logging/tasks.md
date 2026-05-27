## 1. Requirements Registration

- [x] 1.1 Add `FR-022` to `REQUIREMENTS.md`: *File logging sink — when `logging.fileEnabled` is true, the daemon SHALL write log events to a timestamped file in `logging.directory` (default: `logs/` beside the executable) in addition to the console sink; the file sink SHALL use an independent `logging.fileLogLevel` threshold; an invalid or unwritable directory SHALL be reported as a Warning and the daemon SHALL fall back to console-only without crashing*
- [x] 1.2 Add `FR-023` to `REQUIREMENTS.md`: *Log rotation — each application start SHALL open a new file (`openswfz-<yyyyMMddTHHmmssZ>.log`); the operator MAY additionally configure scheduled rotation (`logging.rotationSchedule`): `"session"` (startup only), `"hourly"` (each UTC hour boundary), `"daily"` (at `logging.rotationTime` UTC), or `"weekly"` (on `logging.rotationDayOfWeek` at `logging.rotationTime` UTC); rotation timers SHALL recalculate from `DateTime.UtcNow` after each firing to prevent drift*
- [x] 1.3 Add `FR-024` to `REQUIREMENTS.md`: *Log file retention — after each rotation the daemon SHALL delete the oldest `openswfz-*.log` files in the configured directory until at most `logging.maxFiles` (default: 7) files remain; `maxFiles` ≤ 0 SHALL be clamped to 1 with a startup Warning; deletion failures SHALL be logged at Warning and SHALL NOT abort rotation*
- [x] 1.4 Amend `FR-019` in `REQUIREMENTS.md`: remove the "exclusively to stderr" constraint; change "takes effect on next application start" to "the console log level takes effect immediately when the operator saves settings"; note that `FR-022` adds the file sink alongside the console

## 2. NuGet Dependencies

- [x] 2.1 Pin `Serilog.AspNetCore`, `Serilog.Sinks.File`, and `Serilog.Sinks.Console` in `Directory.Packages.props`; verify that all three have Apache-2.0 licence entries in `licence-inventory.md`
- [x] 2.2 Add `<PackageReference>` for all three packages to `OpenWSFZ.Daemon.csproj`
- [x] 2.3 Verify `dotnet build -c Release` exits 0 with no new warnings

## 3. Configuration Schema

- [x] 3.1 Add `LoggingConfig` record to `OpenWSFZ.Abstractions`:
  ```csharp
  public record LoggingConfig
  {
      public bool   FileEnabled       { get; init; } = false;
      public string Directory         { get; init; } = "logs";
      public string FileLogLevel      { get; init; } = "Information";
      public string RotationSchedule  { get; init; } = "daily";
      public string RotationTime      { get; init; } = "00:00";
      public string RotationDayOfWeek { get; init; } = "Monday";
      public int    MaxFiles          { get; init; } = 7;
  }
  ```
- [x] 3.2 Add `public LoggingConfig Logging { get; init; } = new();` property to `AppConfig`
- [x] 3.3 Register `LoggingConfig` in `AppJsonContext` with `[JsonSerializable(typeof(LoggingConfig))]`
- [x] 3.4 Update the default-config creation path in `JsonConfigStore` (or equivalent) to include the `logging` block so first-run files contain the correct defaults
- [x] 3.5 Verify `dotnet build -c Release` exits 0; verify `dotnet test -c Release` exits 0 (existing config tests must pass with the new field)

## 4. LoggingPipeline Service

- [x] 4.1 Create `src/OpenWSFZ.Daemon/Logging/LoggingPipeline.cs` — singleton service that owns the Serilog logger lifecycle
- [x] 4.2 Implement `Apply(LoggingConfig config)`: build `LoggerConfiguration` with `WriteTo.Console` always present; if `config.FileEnabled`, call `GenerateLogFilePath` and add `WriteTo.File` with `RollingInterval.Infinite`; assign `Log.Logger`; on `IOException` during file open, log Warning to console and omit the file sink
- [x] 4.3 Implement `Rotate()`: call `Log.CloseAndFlush()`, then call `Apply` with the current config (which generates a new timestamped path)
- [x] 4.4 Implement `EnforceRetention(string directory, int maxFiles)`: list files matching `openswfz-*.log`; sort by filename (chronological); delete from the front of the list until `count ≤ maxFiles`; catch and log any `IOException` per file without aborting
- [x] 4.5 Implement `GenerateLogFilePath(string directory)`: call `Directory.CreateDirectory(directory)` (no-op if exists); return `Path.Combine(directory, $"openswfz-{DateTime.UtcNow:yyyyMMddTHHmmssZ}.log")`
- [x] 4.6 Implement `Dispose()`: call `Log.CloseAndFlush()`

## 5. LogRotationService

- [x] 5.1 Create `src/OpenWSFZ.Daemon/Logging/LogRotationService.cs` as a `BackgroundService`
- [x] 5.2 Constructor accepts `LoggingPipeline pipeline`, `IConfigStore configStore`, `IClock clock`
- [x] 5.3 Implement `ExecuteAsync`: read current `AppConfig.Logging`; if `!FileEnabled` or `RotationSchedule == "session"`, await `ct` and return without setting a timer
- [x] 5.4 Implement `CalculateNextBoundary(DateTime utcNow, LoggingConfig config) → DateTime`: for `"hourly"` return next full hour; for `"daily"` parse `config.RotationTime` as HH:MM and return the next occurrence of that time; for `"weekly"` parse day-of-week and time and return the next occurrence; always return a future time (minimum 1 second ahead)
- [x] 5.5 In the `ExecuteAsync` loop: await `Task.Delay(nextBoundary - clock.UtcNow, ct)`; on wake (not cancelled): call `pipeline.Rotate()`, call `pipeline.EnforceRetention(config.Directory, config.MaxFiles)`, recalculate next boundary
- [x] 5.6 Unit test (`LogRotationServiceTests` — `FR-023: CalculateNextBoundary hourly schedule returns next full hour`): `FakeClock` at `02:47:00Z` → returns `03:00:00Z` same day
- [x] 5.7 Unit test (`FR-023: CalculateNextBoundary daily schedule at 03:00 returns correct next occurrence`): `FakeClock` at `02:59:00Z` → `03:00:00Z`; `FakeClock` at `03:01:00Z` → `03:00:00Z` next day
- [x] 5.8 Unit test (`FR-023: CalculateNextBoundary weekly schedule returns correct next day`): `FakeClock` at Monday `00:01:00Z`, schedule=weekly/Monday/`"00:00"` → returns next Monday `00:00:00Z`
- [x] 5.9 Unit test (`FR-023: CalculateNextBoundary always returns a future time`): clock at exact boundary moment → returns the *next* occurrence, not the current one

## 6. Daemon Wiring

- [x] 6.1 In `Program.cs`, confirm `AppConfig` is loaded before `WebApplicationBuilder` is constructed; if not, move the config-load call earlier so the logging pipeline can use it at bootstrap
- [x] 6.2 Instantiate `LoggingPipeline`, call `pipeline.Apply(config.Logging)` immediately after config load and before `WebApplication.Build()`
- [x] 6.3 Add `builder.Host.UseSerilog()` so that the MELA `ILoggerFactory` delegates to `Log.Logger`
- [x] 6.4 Register `LoggingPipeline` as DI singleton (`services.AddSingleton(pipeline)`)
- [x] 6.5 Register `LogRotationService` as a hosted service (`services.AddHostedService<LogRotationService>()`)
- [x] 6.6 In the `IConfigStore.OnSaved` handler, add a call to `pipeline.Apply(newConfig.Logging)` so logging is live-reconfigured on every settings save (the rotation service will pick up the new config on its next loop iteration)
- [x] 6.7 In the `ApplicationStopped` hook (or `IHostApplicationLifetime.ApplicationStopped`), call `pipeline.Dispose()` (which calls `Log.CloseAndFlush()`) as the last action before process exit
- [x] 6.8 Verify `dotnet build -c Release` exits 0

## 7. Settings UI — Logging Section

- [x] 7.1 In `settings.html`, add a `<section id="logging-settings">` block below the port control containing:
  - Enable toggle: `<input type="checkbox" id="logging-file-enabled">`
  - Directory: `<input type="text" id="logging-directory">`
  - Log level: `<select id="logging-file-log-level">` with options Verbose / Debug / Information / Warning / Error / Fatal
  - Rotation schedule: `<select id="logging-rotation-schedule">` with options Session / Hourly / Daily / Weekly
  - Rotation time: `<input type="time" id="logging-rotation-time">` (UTC)
  - Day of week: `<select id="logging-rotation-day">` with options Monday–Sunday
  - Max files: `<input type="number" id="logging-max-files" min="1">`
- [x] 7.2 In `settings.js`, in the `GET /api/v1/config` response handler, populate all seven logging controls from `config.logging` (apply defaults if `logging` is absent)
- [x] 7.3 In `settings.js`, in the Save button handler, read all seven logging controls and include a `logging` object in the `POST /api/v1/config` body
- [x] 7.4 In `settings.js`, implement `updateLoggingVisibility()`: when `fileEnabled` is unchecked, add `disabled` attribute to all six dependent controls; when checked, remove it
- [x] 7.5 In `settings.js`, implement schedule-driven conditional visibility: when `rotationSchedule` is `"session"` or `"hourly"`, hide `rotationTime` row; when `"weekly"`, show both `rotationTime` and `rotationDayOfWeek` rows; when `"daily"`, show `rotationTime` only
- [x] 7.6 Call `updateLoggingVisibility()` on page load and on `change` event for the `fileEnabled` toggle and `rotationSchedule` selector
- [x] 7.7 In `app.css`, add CSS for `[disabled]` inputs and selects within `#logging-settings` (greyed text, reduced opacity) so the disabled state is visually clear

## 8. Traceability and Build Verification

- [x] 8.1 Add `[Fact(DisplayName = "FR-022: ...")]` tags to `LoggingPipelineTests` (at minimum: file-created-when-enabled, no-file-when-disabled, invalid-directory-falls-back, level-filters-independently)
- [x] 8.2 Add `[Fact(DisplayName = "FR-023: ...")]` tags to `LogRotationServiceTests` (the four `CalculateNextBoundary` unit tests from tasks 5.6–5.9)
- [x] 8.3 Add `[Fact(DisplayName = "FR-024: ...")]` tags to `LoggingPipelineTests` (at minimum: files-within-limit-not-deleted, oldest-files-deleted-when-exceeded, maxFiles-clamped-to-one)
- [x] 8.4 Add `[Fact(DisplayName = "FR-019: ...")]` tag to a test verifying the console log-level dropdown round-trips correctly via `GET/POST /api/v1/config` (if no such test exists, create one in `ConfigStoreTests` or equivalent)
- [x] 8.5 Remove `FR-019` from `traceability-debt.md` once tasks 8.4 and 6.3 confirm the console log level is configurable and tested
- [x] 8.6 Verify `dotnet build -c Release` exits 0 with 0 warnings across all projects
- [x] 8.7 Verify `dotnet test -c Release` exits 0 with all tests green
- [ ] 8.8 Manual smoke test: start daemon with `fileEnabled: false` → confirm no `logs/` directory created; enable via Settings page → confirm file appears immediately; let scheduled rotation fire or trigger manually → confirm new file opens and old file count is within `maxFiles`
