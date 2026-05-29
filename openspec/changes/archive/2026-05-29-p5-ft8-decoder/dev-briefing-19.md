# Developer Briefing — p5-ft8-decoder (Round 19)

**Date:** 2026-05-24
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Scope:** Eliminate 30-second shutdown delay

---

## Situation

The zero-audio problem is resolved. The Jabra EVOLVE LINK delivers 48 kHz, 32-bit, 1ch
IeeeFloat; audio flows correctly; `zeroOutputCount` fires once on startup (WDL resampler
initialisation — expected) and never again.

The outstanding issue is shutdown responsiveness. Pressing Ctrl+C takes approximately
30 seconds before the process exits. The log reveals two independent causes:

### Cause A — WebSocket heartbeats continue for ~20 seconds after Ctrl+C

`ApplicationStopping` fires, the capture pipeline begins tearing down, yet the browser
keeps receiving heartbeats at 12:00:12, 12:00:17, 12:00:22, 12:00:27. The heartbeat loop
in `WebSocketHub.HandleAsync` runs until the browser disconnects:

```csharp
while (!ct.IsCancellationRequested)
```

`ct` here is `ctx.RequestAborted` — the HTTP request token, not the application
stopping token. ASP.NET Core does not cancel it until the Kestrel listener shuts down,
which is _after_ `ApplicationStopping` completes. Consequently, connected WebSocket clients
receive heartbeats for the full duration of the shutdown sequence.

There is no `AbortAll()` method. `ActiveSockets` is a private `ConcurrentDictionary`
with no external escape hatch.

### Cause B — STA `capture.StopRecording()` hangs ~10 seconds (Jabra driver slow-stop)

The STA finally block calls `capture.StopRecording()` and then `capture.Dispose()`.
On the Jabra EVOLVE LINK (USB), `capture.StopRecording()` blocks the STA thread for
approximately 10 seconds before returning. During this time, `CaptureManager.StopAsync()`
is blocked awaiting `_captureTask`, which in turn awaits `staTask`. At T+10 s,
`CaptureManager.StopAsync()` logs its timeout message and continues, but the STA thread
is still hanging.

The intermediate steps are logged at `LogDebug` (invisible at the default `Information`
level), so there is no log evidence of which step is slow:

```
[info] DIAG STA finally: beginning cleanup on '...'    ← visible
[10-second gap — no intermediate steps visible]
[warn] StopAsync: capture task did not complete within 10 s  ← CaptureManager timeout
```

---

## Tasks

### S1 — Add `WebSocketHub.AbortAll()` and call it at the start of shutdown

#### S1a — New method in `WebSocketHub.cs`

**File:** `src/OpenWSFZ.Web/WebSocketHub.cs`

Add the following method immediately after `SetBroadcastLogger` (after line 49):

```csharp
/// <summary>
/// Aborts all currently-open WebSocket connections immediately.
/// Called at the start of application shutdown so the browser UI goes dark at once,
/// rather than continuing to receive heartbeats for the duration of the shutdown sequence.
/// Each connection's <see cref="HandleAsync"/> loop detects the aborted socket state via
/// <see cref="ReceiveUntilCloseAsync"/> and exits without attempting a graceful close handshake.
/// </summary>
internal static void AbortAll()
{
    foreach (var (ws, _) in ActiveSockets)
    {
        try { ws.Abort(); } catch { /* best-effort */ }
    }
}
```

**Why `Abort()` rather than `CloseAsync()`:**
`CloseAsync()` requires a cooperative close handshake with the browser. During shutdown the
Kestrel listener is still live and the handshake may succeed, but it takes additional round
trips and blocks. `Abort()` is synchronous and immediate: it transitions the socket to
`WebSocketState.Aborted`, which causes the pending `ReceiveAsync` in
`ReceiveUntilCloseAsync` to throw `WebSocketException` immediately. The `HandleAsync`
`WhenAny` loop then sees `completed == receiveTask` and breaks cleanly. The `finally` block
checks `ws.State is Open or CloseReceived` — after `Abort()` this is false, so the existing
`CloseAsync` call is skipped. No additional clean-up is needed.

#### S1b — Call `AbortAll()` at the start of `ApplicationStopping.Register`

**File:** `src/OpenWSFZ.Daemon/Program.cs`

Replace the existing `ApplicationStopping.Register` callback (around line 251):

```csharp
// Before:
app.Lifetime.ApplicationStopping.Register(() =>
{
    startupLogger.LogInformation("Application stopping — shutting down capture pipeline.");

    restartSemaphore.Wait();
    try
    {
        ...
```

```csharp
// After:
app.Lifetime.ApplicationStopping.Register(() =>
{
    startupLogger.LogInformation(
        "Application stopping — aborting WebSocket connections and shutting down capture pipeline.");

    // S1: abort all active WebSocket connections immediately so the browser UI goes dark
    // at the moment Ctrl+C is pressed, rather than continuing to receive heartbeats while
    // the capture pipeline drains below.
    WebSocketHub.AbortAll();

    // B2: wait for any in-progress restart to complete before tearing down.
    restartSemaphore.Wait();
    try
    {
        ...
```

`AbortAll()` must be called **before** `restartSemaphore.Wait()`, not after.  The semaphore
may take up to ~5 seconds to become available (restart backoff delay). Aborting sockets
before waiting for the semaphore means the browser sees the disconnect immediately,
regardless of how long the restart serialisation takes.

---

### S2 — Apply a 3-second timeout to `capture.StopRecording()` in the STA finally block

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`

Replace the `capture is not null` block in the STA `finally` (lines 412–420):

```csharp
// Before:
if (capture is not null)
{
    _logger?.LogDebug(
        "DIAG STA finally: calling capture.StopRecording() on '{DeviceId}'.", deviceId);
    try { capture.StopRecording(); } catch { }
    _logger?.LogDebug(
        "DIAG STA finally: calling capture.Dispose() on '{DeviceId}'.", deviceId);
    try { capture.Dispose();       } catch { }
}
```

```csharp
// After:
if (capture is not null)
{
    // S2: some drivers (e.g. Jabra EVOLVE LINK USB) take 10+ seconds to acknowledge
    // StopRecording().  Running it on a background thread with a 3-second timeout lets
    // the STA finally block complete promptly.  If the thread-pool thread violates the
    // STA COM apartment rule the resulting COMException is swallowed — acceptable during
    // shutdown since the process is exiting and the device is being abandoned regardless.
    _logger?.LogInformation(
        "DIAG STA finally: calling capture.StopRecording() on '{DeviceId}' (3 s timeout).",
        deviceId);
    var stopTask = Task.Run(() => { try { capture.StopRecording(); } catch { } });
    if (stopTask.Wait(TimeSpan.FromSeconds(3)))
    {
        _logger?.LogInformation(
            "DIAG STA finally: capture.StopRecording() completed on '{DeviceId}'.", deviceId);
        _logger?.LogInformation(
            "DIAG STA finally: calling capture.Dispose() on '{DeviceId}'.", deviceId);
        try { capture.Dispose(); } catch { }
    }
    else
    {
        // StopRecording timed out — skip Dispose (it would also hang).
        // The device handle is abandoned; the OS reclaims it on process exit.
        _logger?.LogWarning(
            "DIAG STA finally: capture.StopRecording() timed out after 3 s on '{DeviceId}' " +
            "— abandoning device handle; OS will reclaim on process exit.", deviceId);
    }
}
```

**Why `Dispose()` is skipped on timeout:**
`WasapiCapture.Dispose()` calls `StopRecording()` internally. If `StopRecording()` already
timed out, `Dispose()` would also hang indefinitely. Skipping it is correct: the OS
reclaims audio device handles on process exit, so no audio resource leak occurs.

---

### S3 — Promote `sessionControl.Dispose()` log to `LogInformation`

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`

The `sessionControl.Dispose()` log is still at `LogDebug` (line 405). If this step ever
becomes slow it will be invisible. Promote it:

```csharp
// Before (line 405):
_logger?.LogDebug(
    "DIAG STA finally: disposing sessionControl on '{DeviceId}'.", deviceId);

// After:
_logger?.LogInformation(
    "DIAG STA finally: disposing sessionControl on '{DeviceId}'.", deviceId);
```

The two `capture.StopRecording()` / `capture.Dispose()` logs are rewritten by S2 above
and will already be at `Information`. This change ensures `sessionControl.Dispose()` is
also visible.

---

## Expected outcome after this briefing

With S1 applied, Ctrl+C should cause the browser UI to go dark within approximately
one second — the browser's WebSocket `onclose` handler fires immediately when the server
aborts the connection, before any other shutdown work begins.

With S2 applied, the STA finally block completes in at most 3 seconds rather than 10.
Combined with S1, the total shutdown time should fall from ~30 seconds to ~5 seconds
or less (semaphore release delay + 3 s STA timeout, if the Jabra driver is still slow).

The log should then read approximately:

```
[info] Application stopping — aborting WebSocket connections and shutting down capture pipeline.
[info] DIAG STA finally: beginning cleanup on '...'
[info] DIAG STA finally: disposing sessionControl on '...'
[info] DIAG STA finally: calling capture.StopRecording() on '...' (3 s timeout)
[warn] DIAG STA finally: capture.StopRecording() timed out after 3 s on '...' — abandoning device handle; OS will reclaim on process exit.
[info] DIAG STA finally: cleanup complete on '...'
[info] Application stopped.
```

or, if the Jabra driver improves:

```
[info] DIAG STA finally: calling capture.StopRecording() on '...' (3 s timeout)
[info] DIAG STA finally: capture.StopRecording() completed on '...'
[info] DIAG STA finally: calling capture.Dispose() on '...'
[info] DIAG STA finally: cleanup complete on '...'
```

---

## Summary

| Task | File | Effect |
|---|---|---|
| S1a | `WebSocketHub.cs` | Add `AbortAll()` — calls `ws.Abort()` on every active socket |
| S1b | `Program.cs` | Call `WebSocketHub.AbortAll()` at the start of `ApplicationStopping.Register` |
| S2 | `WasapiAudioSource.cs` | 3-second timeout on `capture.StopRecording()` via background thread |
| S3 | `WasapiAudioSource.cs` | Promote `sessionControl.Dispose()` log from `LogDebug` to `LogInformation` |
