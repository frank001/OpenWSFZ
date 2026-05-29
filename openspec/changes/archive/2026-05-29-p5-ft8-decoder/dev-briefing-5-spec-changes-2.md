# Specification Change Request — dev-briefing-5.md (Round 2)

**Date:** 2026-05-23
**Raised by:** Developer review
**Target document:** `openspec/changes/p5-ft8-decoder/dev-briefing-5.md`
**Supersedes:** `dev-briefing-5-spec-changes.md` (all four items from that document are now applied)
**Status:** Awaiting QA action

Two items remain. SCR-5 has operational impact and must be applied before the
developer starts on S6. SCR-6 is cosmetic.

---

## SCR-5 — Add Exception Handler to `restartPipeline` Lambda (REQUIRED)

### Problem

The `restartPipeline` lambda in Step 1 of the S6 wiring guide has no top-level
try-catch:

```csharp
Func<Task> restartPipeline = () => Task.Run(async () =>
{
    var device = configStore.Current.AudioDeviceName;
    startupLogger.LogWarning(
        "Watchdog: audio silent for 15 s while capturing on '{Device}' — restarting pipeline.",
        device);
    await StopFramerAsync();
    await captureManager.StopAsync();
    audioMonitor.Reset();
    if (device is not null)
        StartPipeline(device);
});
```

The call site in the heartbeat loop discards the `ValueTask`:

```csharp
_ = watchdog.TickAsync(active);
```

Execution path when `_onRestart()` throws:

1. Exception propagates out of `await _onRestart()` inside `AudioWatchdog.TickAsync`.
2. `TickAsync` returns a faulted `ValueTask`.
3. `_ =` discards the `ValueTask` — the exception is silently swallowed.
4. `_silentWindows` was already reset to `0` before the restart was attempted,
   so the watchdog starts counting again from zero with no log evidence that the
   restart was attempted, let alone that it failed.

The operator sees audio go silent, the watchdog triggers at the 15-second mark,
the restart fails (e.g. `StopFramerAsync` timeout, driver fault), and the log
shows nothing after the initial Warning. The daemon appears to be counting down
again normally while the pipeline remains dead.

### Required Change

Wrap the body of the lambda in a top-level `try/catch`:

```csharp
Func<Task> restartPipeline = () => Task.Run(async () =>
{
    try
    {
        var device = configStore.Current.AudioDeviceName;
        startupLogger.LogWarning(
            "Watchdog: audio silent for 15 s while capturing on '{Device}' — restarting pipeline.",
            device);
        await StopFramerAsync();
        await captureManager.StopAsync();
        audioMonitor.Reset();
        if (device is not null)
            StartPipeline(device);
    }
    catch (Exception ex)
    {
        startupLogger.LogError(ex,
            "Watchdog pipeline restart failed on device '{Device}': {Message}",
            configStore.Current.AudioDeviceName, ex.Message);
    }
});
```

No other changes to the lambda are required. `startupLogger` and `configStore`
are both in scope at the definition site in `Program.cs` (lines 47 and 21
respectively).

---

## SCR-6 — Update S6 `Files` Header to List All Four Affected Files (MINOR)

### Problem

The S6 section header currently reads:

```
**Files:** `src/OpenWSFZ.Daemon/Program.cs`
```

After the SCR-1 additions, S6 touches four files. A developer reading the header
to estimate scope will undercount the work by roughly half.

### Required Change

Replace the single-file entry with the full list:

```
**Files:**
- `src/OpenWSFZ.Web/AudioWatchdog.cs` — new class (create)
- `src/OpenWSFZ.Web/WebSocketHub.cs` — signature change + heartbeat integration
- `src/OpenWSFZ.Web/WebApp.cs` — new `restartPipeline` parameter + call-site update
- `src/OpenWSFZ.Daemon/Program.cs` — restart lambda definition + `WebApp.Create` call-site update
```

---

## Summary

| # | Change | Section | Blocking? |
|---|---|---|---|
| **SCR-5** | Add try-catch to `restartPipeline` lambda; log restart failures at Error | S6 — Wiring, Step 1 | **Yes — silent failure makes the watchdog undiagnosable** |
| SCR-6 | Update `Files` header to list all four files affected by S6 | S6 heading | No |
