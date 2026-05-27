## Context

The daemon uses `Microsoft.Extensions.Logging` (MELA) throughout with the default ASP.NET console provider. All `ILogger<T>` callsites are unaware of the underlying sink. This is the correct abstraction boundary: adding a file sink must not touch any callsite.

The two open questions at design time were (1) which logging framework to adopt and (2) how to implement scheduled rotation, since the built-in Serilog rolling options do not include a weekly interval. Both are resolved below.

## Goals / Non-Goals

**Goals:**
- File logging sink that can be independently enabled, configured, and disabled without restarting the daemon (settings UI applies on Save).
- Session rotation: every application start opens a fresh, timestamped file.
- Scheduled rotation: hourly, daily at a specified UTC time, or weekly on a specified day and time.
- Retention: automatic deletion of files beyond the configured limit after each rotation.
- Independent file log-level threshold configurable at runtime via the settings page.
- All configuration round-trips through the existing `GET/POST /api/v1/config` endpoints.

**Non-Goals:**
- Callsite changes: zero modifications to existing `ILogger<T>` usage.
- Log format customisation (a sensible default is provided; operators may edit the Serilog output template in a future phase).
- Per-component log levels for the file sink.
- Remote, syslog, or structured (JSON) file sinks in this phase.
- Log file compression.
- Weekly rotation at non-midnight granularity is supported (the operator sets `rotationTime`); sub-hourly granularity is not.

## Decisions

### D1 — Adopt Serilog as the logging backend

**Decision:** Replace the default ASP.NET console provider with Serilog via `Host.UseSerilog()`. Console output is reproduced via `WriteTo.Console`; the file sink is `WriteTo.File`.

**Rationale:** Serilog is the standard choice for rolling file sinks in .NET. Its `ILogger<T>` bridge means zero callsite changes. The alternative — `Microsoft.Extensions.Logging.AzureAppServices` or a custom `ILoggerProvider` with `StreamWriter` — requires writing and maintaining rolling-file logic from scratch. The incremental NuGet surface is three packages (`Serilog.AspNetCore`, `Serilog.Sinks.File`, `Serilog.Sinks.Console`), all Apache-2.0 licensed.

**Serilog bootstrap:** Because `AppConfig` is loaded before `WebApplication.Build()`, `Log.Logger` is assigned from `AppConfig.Logging` before `UseSerilog()` is called. This captures startup logs that would otherwise be lost.

---

### D2 — Session rotation via timestamped filename; scheduled rotation via hosted-service timer

**Decision:** File sink is opened with `RollingInterval.Infinite` (no automatic Serilog rolling). Session rotation is achieved by embedding a UTC ISO-8601 timestamp in the filename at startup. Scheduled rotation is implemented by `LogRotationService` — an `IHostedService` that maintains a `Timer` firing at the next rotation boundary.

**Rationale:** Serilog's built-in `RollingInterval` supports `Hour` and `Day` but not `Week`. Implementing weekly rotation via a custom sink or a per-day file with a "skip" flag is fragile. A timer-based hosted service is straightforward, fully testable (inject `IClock`), and handles all three schedules uniformly.

On rotation, `LogRotationService`:
1. Calls `LoggingPipeline.Rotate()`, which:
   a. Disposes the current Serilog `Logger`.
   b. Opens a new `Logger` with a new timestamped path.
   c. Reassigns `Log.Logger` and the `ILoggerFactory` used by the DI container.
2. Enforces retention (deletes oldest files beyond `maxFiles`).
3. Schedules the next timer tick.

**Timer drift:** Each tick recalculates the next boundary from `DateTime.UtcNow` rather than adding a fixed period, so drift does not accumulate.

---

### D3 — `LoggingPipeline` service owns all file-sink lifecycle

**Decision:** Introduce `LoggingPipeline` (singleton) in `OpenWSFZ.Daemon`. It holds the `LoggerConfiguration` builder, the active `Logger`, a `LoggingLevelSwitch` for the file sink, and exposes `Apply(LoggingConfig)`, `Rotate()`, and `Dispose()`.

**Rationale:** Centralising lifecycle in one class makes the startup/shutdown/save-handler interactions explicit. `Program.cs` calls `pipeline.Apply(config.Logging)` once at startup and again on every `IConfigStore.OnSaved` event that touches the logging block. This avoids scattered `if (fileEnabled)` checks throughout `Program.cs`.

---

### D4 — Settings live-reload: full logger rebuild on any logging-config change

**Decision:** When `IConfigStore.OnSaved` fires and `LoggingConfig` has changed, `LoggingPipeline.Apply()` disposes the current logger and builds a new one from scratch. A `LoggingLevelSwitch` allows the level to be changed without a full rebuild, but for simplicity the same rebuild path handles all changes.

**Rationale:** Full rebuild on save is simpler and safer than partial updates (e.g., only changing the level switch). The save event fires at most once per operator interaction, so the overhead of a full rebuild is negligible.

---

### D5 — `LoggingConfig` as a nested record in `AppConfig`

**Decision:** Add `LoggingConfig` as a nested record (not a top-level config key). `AppConfig` gains a `Logging` property of type `LoggingConfig` with all defaults.

```csharp
public record LoggingConfig
{
    public bool   FileEnabled        { get; init; } = false;
    public string Directory          { get; init; } = "logs";
    public string FileLogLevel       { get; init; } = "Information";
    public string RotationSchedule   { get; init; } = "daily";
    public string RotationTime       { get; init; } = "00:00";      // HH:MM UTC
    public string RotationDayOfWeek  { get; init; } = "Monday";     // weekly only
    public int    MaxFiles           { get; init; } = 7;
}
```

`AppJsonContext` is updated to include `LoggingConfig` and the updated `AppConfig` for AOT-safe serialisation.

---

### D6 — Log filename convention

```
openswfz-20260525T143000Z.log
```

Pattern: `openswfz-yyyyMMddTHHmmssZ.log`, UTC timestamp of the moment the file is opened. The `logs/` directory is created if absent. On invalid directory, a `LogWarning` is emitted and the file sink is skipped; the console sink is always active.

---

### D7 — Retention enforcement

After each rotation (startup or scheduled), the daemon:
1. Lists all files matching `openswfz-*.log` in the configured directory.
2. Sorts by file name (ISO-8601 filenames sort chronologically by name).
3. If count > `MaxFiles`, deletes from the beginning of the sorted list until count == `MaxFiles`.
4. Deletion failures are logged at Warning but do not abort the rotation.

`MaxFiles` is validated: values ≤ 0 are clamped to 1 with a startup warning.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| File I/O on logging thread adds latency | Serilog's file sink uses a background queue by default (`buffered: true`); I/O does not block the caller |
| Logger rebuild during high-throughput periods could drop log events | `LoggingPipeline.Rotate()` flushes the old logger (`Log.CloseAndFlush()`) before closing; the window between close and reopen is < 1 ms |
| Operator sets an invalid or read-only directory | Caught in `LoggingPipeline.Apply()`: `IOException` → `LogWarning`; fall back to console-only |
| Rotation fires while a log event is in-flight | Serilog's `Logger.Dispose()` is thread-safe; in-flight events are flushed before the file handle is closed |
| `maxFiles = 0` passed from UI | Clamped to 1 at `LoggingPipeline.Apply()` with a Warning log |
| Weekly rotation timer fires when daemon is stopped and restarted mid-week | Session rotation creates a new file; the next scheduled rotation time is recalculated from `UtcNow` at startup, so no event is missed or double-fired |
| Three new NuGet packages increase supply-chain surface | All three (`Serilog.*`) are Apache-2.0, widely audited, and already present in many .NET stacks; `LicenseInventoryCheck` gate will verify |

## Migration Plan

1. `Directory.Packages.props` — pin `Serilog.AspNetCore`, `Serilog.Sinks.File`, `Serilog.Sinks.Console`.
2. `OpenWSFZ.Abstractions` — add `LoggingConfig` record; update `AppConfig`.
3. `OpenWSFZ.Daemon` — implement `LoggingPipeline` and `LogRotationService`; wire into `Program.cs`.
4. `AppJsonContext` — register `LoggingConfig`.
5. `web/settings.html` + `web/js/settings.js` — add Logging section.
6. `dotnet test -c Release` — must remain green; no existing tests need changes.
7. Manual smoke test: start with `fileEnabled: false` → no file created; enable via UI → file appears; rotation schedule fires correctly.

**Rollback:** If a regression is found post-merge, set `fileEnabled: false` via the settings page — this rebuilds the logger without the file sink. No config schema rollback is needed (unknown fields are preserved by the config round-trip).

## Open Questions

None — all design decisions are resolved. The implementation may discover edge cases in `Logger` rebuild thread-safety under high event volume, but this is addressable within the implementation phase without spec changes.
