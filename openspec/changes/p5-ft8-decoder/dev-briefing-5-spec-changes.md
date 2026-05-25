# Specification Change Request — dev-briefing-5.md

**Date:** 2026-05-23
**Raised by:** Developer review
**Target document:** `openspec/changes/p5-ft8-decoder/dev-briefing-5.md`
**Status:** Awaiting QA action

Two changes are required before the developer starts implementation (SCR-1, SCR-2).
Two further changes are recommended but non-blocking (SCR-3, SCR-4).

---

## SCR-1 — Add `HandleAsync` Wiring Guidance to S6 Section (REQUIRED)

### Problem

The S6 section directs the developer to implement the watchdog inside
`WebSocketHub.HandleAsync`, but the current signature of that method does not
include `CaptureManager` or a restart delegate:

```csharp
// Current — src/OpenWSFZ.Web/WebSocketHub.cs
public static async Task HandleAsync(
    WebSocket ws,
    IConfigStore configStore,
    AudioActivityMonitor? audioMonitor,
    ILogger logger,
    CancellationToken ct)
```

The watchdog requires:
- `captureManager.IsCapturing` — to avoid triggering on a stopped pipeline
- A restart action — to call `StopFramerAsync()` / `captureManager.StopAsync()` / `StartPipeline()`

Neither is currently available inside `HandleAsync`. `captureManager` is available
as a closure in `WebApp.Create` (it is already used there for the
`/api/v1/status` endpoint), but it is not forwarded to `HandleAsync`.

Without this wiring the developer must independently discover and solve the
plumbing before writing a line of watchdog logic.

### Required Addition

Add a **"Wiring — How to thread `CaptureManager` into `HandleAsync`"**
sub-section to the S6 section. The sub-section must cover:

**Step 1 — Update `WebSocketHub.HandleAsync` signature**

Add `CaptureManager?` and a restart delegate (or a single `AudioWatchdog?`
parameter if the developer extracts the class):

```csharp
public static async Task HandleAsync(
    WebSocket ws,
    IConfigStore configStore,
    AudioActivityMonitor? audioMonitor,
    CaptureManager? captureManager,   // ← ADD: needed by watchdog for IsCapturing
    Func<Task>? restartPipeline,      // ← ADD: watchdog restart action
    ILogger logger,
    CancellationToken ct)
```

**Step 2 — Update the call site in `WebApp.cs`**

The call on line 185 of `src/OpenWSFZ.Web/WebApp.cs` currently reads:

```csharp
await WebSocketHub.HandleAsync(ws, store, audioMonitor, wsLogger, ctx.RequestAborted);
```

Update to pass the two new arguments. `captureManager` is already in scope as a
closure; `restartPipeline` is the fire-and-forget restart lambda:

```csharp
await WebSocketHub.HandleAsync(
    ws, store, audioMonitor,
    captureManager,
    restartPipeline,   // defined elsewhere in Program.cs or WebApp.Create
    wsLogger,
    ctx.RequestAborted);
```

**Step 3 — Construct `AudioWatchdog` inside `HandleAsync`**

```csharp
var watchdog = captureManager is not null && restartPipeline is not null
    ? new AudioWatchdog(
          audioMonitor!,
          isCapturing:     () => captureManager.IsCapturing,
          onRestart:       restartPipeline,
          threshold:       3)
    : null;
```

Then in the heartbeat loop, replace the bare `ConsumeAndReset` call:

```csharp
// Before (heartbeat loop):
var active = audioMonitor?.ConsumeAndReset() ?? false;

// After:
var active = audioMonitor?.ConsumeAndReset() ?? false;
if (watchdog is not null)
    _ = watchdog.TickAsync();   // fire-and-forget; watchdog owns the restart
```

**Note:** `AudioWatchdog.TickAsync` must call `audioMonitor.ConsumeAndReset()`
internally so the watchdog's `active` reading is the same window the heartbeat
already consumed. Alternatively, pass `active` in to `watchdog.TickAsync(bool active)`
to avoid a double-consume. QA to decide the preferred interface.

---

## SCR-2 — Add `PlatformAudioSource` Constructor Change to B15 Section (REQUIRED)

### Problem

The B15 fix note says:

> *"add an `ILogger<WasapiAudioSource>?` field (constructor-injected) and pass it
> through from `PlatformAudioSource`."*

But `PlatformAudioSource`'s constructor is currently parameterless:

```csharp
// Current — src/OpenWSFZ.Audio/PlatformAudioSource.cs
public PlatformAudioSource()
{
    _inner = ResolveForCurrentPlatform();
}

private static IAudioSource ResolveForCurrentPlatform()
{
    ...
    return new WasapiAudioSource();   // ← no logger
}
```

The developer cannot "pass the logger through" without knowing what exact
constructor change is required in `PlatformAudioSource`. The phrase is correct
but incomplete.

### Required Addition

Append the following code block to the B15 **Note** section, immediately after
the existing paragraph that mentions `PlatformAudioSource`:

```csharp
// src/OpenWSFZ.Audio/PlatformAudioSource.cs — add logger parameter
public PlatformAudioSource(ILogger<WasapiAudioSource>? logger = null)
{
    _inner = ResolveForCurrentPlatform(logger);
}

private static IAudioSource ResolveForCurrentPlatform(
    ILogger<WasapiAudioSource>? logger = null)
{
#if WASAPI_SUPPORTED
    if (OperatingSystem.IsWindows())
        return new WasapiAudioSource(logger);
#endif
    if (OperatingSystem.IsLinux())  return new ArecordAudioSource();
    if (OperatingSystem.IsMacOS())  return new SoxAudioSource();
    return new NullAudioSource();
}
```

Also note: wherever `PlatformAudioSource` is constructed in `Program.cs` or
`WebApp.Create`, the logger must be resolved from DI and forwarded. Check
`src/OpenWSFZ.Daemon/Program.cs` for the construction site.

---

## SCR-3 — Add Multi-Connection Watchdog Scope Note to S6 Section (RECOMMENDED)

### Problem

The S6 design places the `AudioWatchdog` as a local variable inside
`HandleAsync`. If two WebSocket clients connect simultaneously, each connection
gets its own watchdog instance with its own counter. Both could reach the
threshold in the same 5-second window and fire `_ = watchdog.TickAsync()`
concurrently — triggering two pipeline restarts.

### Required Addition

Add a single sentence to the S6 **Thread safety** paragraph:

> **Multi-connection scope:** The watchdog counter is per-connection. If two
> clients are connected simultaneously, both may trigger a restart in the same
> heartbeat window. This is acceptable: `CaptureManager.StartAsync` calls
> `StopAsync` first, so double-restarts are safe but redundant. This scenario
> is not expected in normal daemon operation (single-user, single browser tab),
> and no additional synchronisation is required.

---

## SCR-4 — Clean Up `await Task.CompletedTask` No-Op in Test Stubs (RECOMMENDED)

### Problem

All three S6 test stubs use:

```csharp
onRestart: async () => { restarts++; await Task.CompletedTask; },
```

`await Task.CompletedTask` is a no-op. The lambda allocates a state machine for
no reason and introduces noise when the developer reads the test stubs as
implementation guidance.

### Required Change

Replace with the synchronous `Task`-returning form in all three test stubs:

```csharp
onRestart: () => { restarts++; return Task.CompletedTask; },
```

This is functionally identical. `AudioWatchdog`'s `onRestart` parameter type
should be `Func<Task>` (not `Func<ValueTask>`), matching the `Task`-based
pattern used throughout this codebase.

---

## Summary

| # | Change | Section | Blocking? |
|---|---|---|---|
| **SCR-1** | Add `HandleAsync` wiring guidance (signature, call site, `AudioWatchdog` construction) | S6 | **Yes — dev cannot implement S6 without it** |
| **SCR-2** | Add `PlatformAudioSource` constructor change to B15 note | B15 | **Yes — dev cannot wire the logger without it** |
| SCR-3 | Add multi-connection scope note to S6 thread-safety paragraph | S6 | No |
| SCR-4 | Replace `await Task.CompletedTask` no-ops in test stubs | Tests | No |

SCR-1 and SCR-2 must be applied before the developer is handed the briefing.
SCR-3 and SCR-4 may be applied at any point before implementation begins.
