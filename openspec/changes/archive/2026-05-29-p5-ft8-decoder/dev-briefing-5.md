# Developer Briefing — p5-ft8-decoder (Round 5)

**Date:** 2026-05-23
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Head commit reviewed:** `eb0eaaf` (merge of `140b3be` — B11–B14 fixes)

---

## User Feedback

> "The audio capture still stops without any error message. I have not found any
> relation to timing or heartbeat, so there must be something else interrupting
> the audio stream. This needs deep investigation to find the root cause of the
> issue. This is a BLOCKER."

B10–B14 are verified correct at the code level. They are not the cause of the
persistent symptom. This briefing documents the new root cause candidates
identified by deep code review of the B11 implementation.

---

## Executive Summary

B11 introduced `WasapiSessionEventClient` to receive Windows audio session
disconnect events. However, the implementation contains **three defects** that,
individually or together, can render B11 completely ineffective at runtime:

| # | Defect | Effect |
|---|---|---|
| **B15** | `sessionControl` is declared inside the `try` block and never disposed or kept alive | GC may collect it in Release builds, silently deregistering the event callback |
| **B16** | B11 registration failure is silently swallowed with no log | Developer cannot tell whether B11 is working or has been failing since day one |
| **B17** | `OnStateChanged` is a no-op | WASAPI session expiry (state → `Expired`) is ignored; no `innerChannel` completion |

Any one of these is sufficient to explain the persistent silent stop.
Additionally, **S6** (watchdog) was deferred pending discussion — it must now be
treated as a blocker, because the event-based approach cannot cover all driver-
level failure modes.

---

## First Diagnostic Step — Run Before Writing Any Code

Before making any changes, check the status endpoint immediately after the next
observed failure:

```
GET http://localhost:<port>/api/v1/status
```

Compare `captureActive` against `audioActive`:

| `captureActive` | `audioActive` | Log entry present? | What it means |
|---|---|---|---|
| `true` | `false` | No | **Capture task is HUNG.** `innerChannel` never completed. B11 not working. Fix B15/B16/B17 first. |
| `false` | `false` | Yes | **Capture task completed.** Check log for Case 2 (warning: unexpected end) or Case 3 (error: exception). |
| `false` | `false` | No | **Capture task completed; log filtered.** Confirm log-level configuration — Case 2 logs at Warning. |

This single observation narrows the fix space dramatically. Do it before anything else.

---

## B15 — `sessionControl` eligible for premature GC collection in Release builds (BLOCKER)

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`
**Severity:** Blocker — B11 silently stops working when GC runs.

### Root Cause

```csharp
// Inside StaThread.Run<bool>() lambda, inside try block:
capture.StartRecording();

AudioSessionControl? sessionControl = null;
try
{
    sessionControl = device.AudioSessionManager.AudioSessionControl;
    sessionControl.RegisterEventClient(
        new WasapiSessionEventClient(innerChannel, staCts));
}
catch
{
    sessionControl = null;  // ← failure silently swallowed (B16 below)
}

setupTcs.SetResult();

// ← staCts.Token.WaitHandle.WaitOne() blocks here for the entire session
staCts.Token.WaitHandle.WaitOne();
```

After `RegisterEventClient()` returns, `sessionControl` is **never read or written
again** in the code that follows. The .NET JIT in Release mode generates precise
GC liveness maps: a local is considered live only up to its last use. Because
`sessionControl` is not used after `RegisterEventClient()`, the JIT may mark it
as dead at the very next GC-safe point (the `WaitOne()` call is a GC-safe point).

NAudio's `AudioSessionControl` wraps a COM `IAudioSessionControl2` pointer and
implements `IDisposable`. Its finalizer calls `Marshal.ReleaseComObject` and —
critically — **`IAudioSessionControl2::UnregisterEventClient`**. When the GC
collects `sessionControl` and the finalizer runs, our `WasapiSessionEventClient`
is unregistered from the Windows audio engine. `OnSessionDisconnected` will never
fire again for this session. B11 becomes a no-op.

This explains why the issue is not timing-related: it occurs whenever the GC
happens to run a finalization cycle after capture starts, which is non-deterministic.

### The Fix

Move `sessionControl` to the **outer scope** of the STA lambda (alongside
`capture`) so it is reachable in the `finally` block, and dispose it there.
A local on the stack in the `finally` block is guaranteed live until that block
exits.

```csharp
var staTask = StaThread.Run<bool>(() =>
{
    WasapiCapture?      capture        = null;
    AudioSessionControl? sessionControl = null;   // ← MOVED HERE

    try
    {
        // ... device, capture, pipeline setup ...

        capture.DataAvailable  += ...;
        capture.RecordingStopped += ...;

        capture.StartRecording();

        // B11: Subscribe to WASAPI audio session events.
        try
        {
            sessionControl = device.AudioSessionManager.AudioSessionControl;
            sessionControl.RegisterEventClient(
                new WasapiSessionEventClient(innerChannel, staCts));
            // sessionControl is now in outer scope → not GC-eligible until finally runs.
        }
        catch (Exception ex)
        {
            // B16: Log the failure so it is visible in the operator log.
            // Do NOT prevent capture — registration is best-effort.
            _logger?.LogWarning(ex,
                "WASAPI session event registration failed on device '{DeviceId}'; " +
                "session-disconnect events will not be detected. " +
                "Capture continues without event-driven termination detection.",
                deviceId);
            sessionControl = null;
        }

        setupTcs.SetResult();
        staCts.Token.WaitHandle.WaitOne();
    }
    catch (Exception ex)
    {
        setupException = ex;
        setupTcs.TrySetResult();
        innerChannel.Writer.TryComplete(ex);
    }
    finally
    {
        // Dispose sessionControl before capture to unregister the event client
        // cleanly before tearing down the WASAPI session.
        if (sessionControl is not null)
        {
            try { sessionControl.Dispose(); } catch { }
            sessionControl = null;
        }

        if (capture is not null)
        {
            try { capture.StopRecording(); } catch { }
            try { capture.Dispose();       } catch { }
        }
    }

    return true;
});
```

**Note — logger injection through `PlatformAudioSource` (SCR-2):**

`WasapiAudioSource` is `internal sealed` with no logger. Add an optional
`ILogger<WasapiAudioSource>?` constructor parameter and thread it through
`PlatformAudioSource`. The changes required are:

```csharp
// src/OpenWSFZ.Audio/WasapiAudioSource.cs — add logger field and constructor parameter
internal sealed class WasapiAudioSource : IAudioSource
{
    private readonly ILogger<WasapiAudioSource>? _logger;

    public WasapiAudioSource(ILogger<WasapiAudioSource>? logger = null)
    {
        _logger = logger;
    }
    // ... rest unchanged
}

// src/OpenWSFZ.Audio/PlatformAudioSource.cs — thread logger through platform resolver
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

// src/OpenWSFZ.Daemon/Program.cs — resolve logger when constructing PlatformAudioSource
// Current (line 56):
//   var audioSource = new PlatformAudioSource();
// Replace with:
var audioSource = new PlatformAudioSource(
    loggerFactory.CreateLogger<WasapiAudioSource>());
```

---

## B16 — B11 registration failure is completely silent (BLOCKER)

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`
**Severity:** Blocker — diagnostic blindness; operator cannot distinguish a
working B11 from a silently broken one.

### Root Cause

```csharp
catch
{
    sessionControl = null; // registration failed; proceed without it
}
```

This bare `catch {}` swallows every exception — `COMException`, `InvalidOperationException`,
`NullReferenceException` — with no log entry. If B11 has been failing on the
developer's machine since `140b3be` was committed, the log contains no evidence
of it. This must be fixed as part of B15 above (see the `catch (Exception ex)`
block with `LogWarning` in the B15 fix).

---

## B17 — `OnStateChanged` ignores `AudioSessionStateExpired` (BLOCKER)

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`
**Severity:** Blocker — a class of WASAPI session termination is silently ignored.

### Root Cause

```csharp
public void OnStateChanged(AudioSessionState state) { }
```

The WASAPI audio session state machine has three states:

| State | Meaning |
|---|---|
| `AudioSessionStateActive` | Audio is flowing |
| `AudioSessionStateInactive` | Session exists but no active streams |
| `AudioSessionStateExpired` | Session is being destroyed; all streams are closed |

`OnSessionDisconnected` fires when Windows **evicts** a session (device switch,
exclusive-mode takeover). `OnStateChanged` with `Expired` fires when the session
**expires normally** — for example, when the underlying device has gone away
quietly or when a format negotiation completes with the session being recreated.
These are not the same event. On some hardware configurations and driver versions,
`AudioSessionStateExpired` fires without a corresponding `OnSessionDisconnected`.

The current handler ignores all state changes. When the session expires, the
`innerChannel` is never completed, `ReadAllAsync(ct)` waits forever, and the
capture task hangs silently.

### The Fix

Handle `AudioSessionStateExpired` (and optionally `AudioSessionStateInactive`)
by completing the channel:

```csharp
public void OnStateChanged(AudioSessionState state)
{
    if (state == AudioSessionState.AudioSessionStateExpired)
    {
        // Session has expired — treat as a disconnect. Complete the channel so
        // CaptureAsync exits and CaptureManager raises CaptureFailed.
        var ex = new AudioCaptureException(
            "unknown",
            "WASAPI audio session expired (OnStateChanged: Expired).");

        _channel.Writer.TryComplete(ex);
        try { _staCts.Cancel(); } catch (ObjectDisposedException) { }
    }
    // AudioSessionStateInactive: session paused but not destroyed — do not
    // complete the channel; audio may resume (e.g. brief device re-negotiation).
}
```

---

## S6 — Watchdog: elevated from Suggestion to BLOCKER

**Files:**
- `src/OpenWSFZ.Web/AudioWatchdog.cs` — new class (create)
- `src/OpenWSFZ.Web/WebSocketHub.cs` — signature change + heartbeat integration
- `src/OpenWSFZ.Web/WebApp.cs` — new `restartPipeline` parameter + call-site update
- `src/OpenWSFZ.Daemon/Program.cs` — restart lambda definition + `WebApp.Create` call-site update

**Previous status:** Suggestion (pending discussion)
**New status:** Blocker

### Rationale for Elevation

B15/B16/B17 address specific Windows audio-session event scenarios. However:

1. Driver bugs exist where `DataAvailable` stops firing with **no session event
   of any kind** — `RecordingStopped` does not fire, `OnSessionDisconnected`
   does not fire, `OnStateChanged` does not fire. The device is alive, the
   session is alive, the STA thread is blocked on `WaitOne()`, the `innerChannel`
   is open. The capture task waits forever.

2. VM audio pass-through (e.g. VirtualBox, VMware) has known behaviour where
   audio stops silently without any host notification.

3. The user has confirmed no relation to timing or the existing heartbeat — this
   rules out a periodic event as the cause, but it also confirms that the
   `AudioActivityMonitor` already has the data needed for a watchdog.

**The watchdog is the only mechanism that can recover from all silent-stop
scenarios, including those no event handler can detect.**

### Agreed Design

```
In the WebSocket heartbeat loop (every 5 seconds):

    audioActive = audioMonitor.ConsumeAndReset()      ← already done by heartbeat emitter

    watchdog.TickAsync(audioActive)                   ← pass the consumed value in

If audioActive == false
    AND captureManager.IsCapturing == true
    AND consecutive_silent_windows >= 3   (15 seconds total)
        → log Warning: "Audio silence detected for 15 s while capture is active — restarting pipeline."
        → await restartPipeline()
        → reset consecutive_silent_windows = 0
Else
    → reset consecutive_silent_windows = 0
```

**Parameters:** 3 windows × 5 seconds = **15 seconds** of silence before restart.
This must survive the 12.64-second FT8 transmission gap (between the end of one
15-second cycle and the first received signal in the next). 15 seconds allows
one complete silent FT8 cycle before triggering. Confirm this value with QA if
real-world testing shows false positives.

**Critical constraint:** The watchdog must NOT trigger if `captureManager.IsCapturing == false`.
A stopped pipeline is not a malfunction. Only trigger when `IsCapturing == true`
AND audio has been silent for the threshold duration.

**Thread safety:** The watchdog counter is local to each `HandleAsync` call (one
instance per connection). The restart delegate is fire-and-forgotten at the call
site (`_ = watchdog.TickAsync(active)`), so it does not block heartbeat emission.

**Multi-connection scope:** The counter is per-connection. If two WebSocket clients
are connected simultaneously both may reach the threshold in the same heartbeat
window and fire `TickAsync` concurrently. This is safe: `CaptureManager.StartAsync`
calls `StopAsync` first, so a double-restart is redundant but not harmful. Normal
daemon operation is single-user, single browser tab; no additional synchronisation
is required.

---

### `AudioWatchdog` Class Design

Create `src/OpenWSFZ.Web/AudioWatchdog.cs`. The class takes the consumed `active`
flag from the heartbeat emitter — it does **not** call `ConsumeAndReset()` itself,
which would cause a double-consume and always see `false`.

```csharp
namespace OpenWSFZ.Web;

/// <summary>
/// Belt-and-suspenders watchdog for audio capture silence (S6).
/// Called once per heartbeat window with the already-consumed activity flag.
/// Triggers a pipeline restart if <see cref="Threshold"/> consecutive silent
/// windows occur while <see cref="_isCapturing"/> returns true.
/// </summary>
internal sealed class AudioWatchdog
{
    private readonly Func<bool> _isCapturing;
    private readonly Func<Task> _onRestart;
    private readonly int        _threshold;
    private int                 _silentWindows;

    public AudioWatchdog(
        Func<bool> isCapturing,
        Func<Task> onRestart,
        int        threshold)
    {
        _isCapturing   = isCapturing;
        _onRestart     = onRestart;
        _threshold     = threshold;
        _silentWindows = 0;
    }

    /// <summary>
    /// Advances the watchdog state for one heartbeat window.
    /// <paramref name="audioWasActive"/> is the value returned by
    /// <c>AudioActivityMonitor.ConsumeAndReset()</c> in the heartbeat loop —
    /// do NOT call ConsumeAndReset again; the window has already been consumed.
    /// </summary>
    public async ValueTask TickAsync(bool audioWasActive)
    {
        if (audioWasActive || !_isCapturing())
        {
            _silentWindows = 0;
            return;
        }

        if (++_silentWindows >= _threshold)
        {
            _silentWindows = 0;
            await _onRestart();
        }
    }
}
```

---

### Wiring — How to thread `CaptureManager` and the restart action into `HandleAsync`

**Step 1 — Define `restartPipeline` in `Program.cs`**

Add the following immediately after the `audioMonitor` declaration (before `WebApp.Create`):

```csharp
// S6: Watchdog restart action — wraps StopFramerAsync / StopAsync / StartPipeline
// in a fire-and-forget Task so the heartbeat loop is not blocked.
// The top-level try-catch ensures any restart failure is logged at Error rather
// than being swallowed silently by the discarded ValueTask at the call site.
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

**Step 2 — Add `restartPipeline` parameter to `WebApp.Create`**

In `src/OpenWSFZ.Web/WebApp.cs`, add one optional parameter to `WebApp.Create`:

```csharp
public static WebApplication Create(
    int port,
    IBindPolicy?                                  bindPolicy           = null,
    IConfigStore?                                 configStore          = null,
    IAudioDeviceProvider?                         audioProvider        = null,
    Func<IServiceProvider, IAudioDeviceProvider>? audioProviderFactory = null,
    CaptureManager?                               captureManager       = null,
    AudioActivityMonitor?                         audioMonitor         = null,
    Action<ILoggingBuilder>?                      configureLogging     = null,
    Func<Task>?                                   restartPipeline      = null)   // ← ADD
```

**Step 3 — Update the `WebApp.Create` call in `Program.cs`**

```csharp
var app = WebApp.Create(
    port,
    configStore:          configStore,
    audioProviderFactory: sp => new PlatformAudioDeviceProvider(
                                    sp.GetRequiredService<ILoggerFactory>()),
    captureManager:       captureManager,
    audioMonitor:         audioMonitor,
    configureLogging:     ConfigureLogging,
    restartPipeline:      restartPipeline);   // ← ADD
```

**Step 4 — Update `WebSocketHub.HandleAsync` signature**

```csharp
public static async Task HandleAsync(
    WebSocket              ws,
    IConfigStore           configStore,
    AudioActivityMonitor?  audioMonitor,
    CaptureManager?        captureManager,   // ← ADD
    Func<Task>?            restartPipeline,  // ← ADD
    ILogger                logger,
    CancellationToken      ct)
```

**Step 5 — Update the call site in `WebApp.cs`** (line 185):

```csharp
await WebSocketHub.HandleAsync(
    ws, store, audioMonitor,
    captureManager,
    restartPipeline,
    wsLogger,
    ctx.RequestAborted);
```

**Step 6 — Construct `AudioWatchdog` and tick in the heartbeat loop**

Inside `HandleAsync`, after registering the socket:

```csharp
// S6: construct watchdog only when both dependencies are available.
var watchdog = captureManager is not null && restartPipeline is not null
    ? new AudioWatchdog(
          isCapturing: () => captureManager.IsCapturing,
          onRestart:   restartPipeline,
          threshold:   3)
    : null;
```

In the heartbeat loop, after the existing `ConsumeAndReset` call:

```csharp
// Build heartbeat: consume-and-reset the activity window (FR-020).
var active       = audioMonitor?.ConsumeAndReset() ?? false;

// S6: tick the watchdog with the already-consumed active flag.
// Fire-and-forget: does not block the heartbeat emission.
if (watchdog is not null)
    _ = watchdog.TickAsync(active);

var heartbeatMsg = new WsHeartbeatMessage(
    Type:    "heartbeat",
    Payload: new HeartbeatPayload(AudioActive: active));

await SendHeartbeatAsync(ws, heartbeatMsg, ct);
```

---

## Additional Observations

### AO1 — `sessionControl` device reference lifetime (resolved)

Confirmed by decompilation of NAudio 2.2.1: both `MMDevice.AudioSessionManager`
and `AudioSessionManager.AudioSessionControl` are lazily initialised and cached
in private fields. Every property access returns the same instance. No additional
lifetime management of `AudioSessionManager` is required; the B15 fix (outer-scope
`sessionControl`) is sufficient. See the C2 addendum below for the full analysis.

### AO2 — No auto-restart after Case 2 (unexpected end)

When `CaptureAsync` exits normally without an exception and without `ct` being
cancelled, `CaptureManager` logs `LogWarning("Capture ended unexpectedly…")` and
sets `_isCapturing = false`. It does **not** call `CaptureFailed`. Nothing
restarts the pipeline.

**S6 does not cover this case.** The watchdog is gated on
`captureManager.IsCapturing == true`, but a Case 2 exit sets `_isCapturing =
false` (line 141 of `CaptureManager.cs`) before the next heartbeat tick fires.
The watchdog sees `!_isCapturing()`, resets its counter, and never triggers.
A Case 2 exit leaves the daemon permanently idle regardless of whether S6 is
in place.

A complete fix requires one of:
- **(a)** Invoke `CaptureFailed` from the Case 2 branch in `CaptureManager` so
  the existing restart path handles it identically to Case 3; or
- **(b)** A separate `IsCapturing`-off watchdog that detects the transition and
  restarts the pipeline.

Both options are out of scope for this round. Tracking as a follow-on item.

---

## Work Order — Priority

Fix in this order. Each item is a separate commit.

| # | Item | File(s) | Effort |
|---|---|---|---|
| **DIAG** | Check `/api/v1/status` after next failure; record `captureActive` value | — | 5 min |
| **B15** | Move `sessionControl` to outer scope; dispose in `finally`; add logger to `WasapiAudioSource` | `WasapiAudioSource.cs`, `PlatformAudioSource.cs` | 30 min |
| **B16** | Replace bare `catch {}` with `catch (Exception ex)` + `LogWarning` | `WasapiAudioSource.cs` | 5 min (part of B15 commit) |
| **B17** | Handle `AudioSessionStateExpired` in `OnStateChanged` | `WasapiAudioSource.cs` | 10 min (part of B15 commit) |
| **S6** | Implement watchdog in heartbeat loop (3 × 5 s threshold) | `AudioWatchdog.cs` (new), `WebSocketHub.cs`, `WebApp.cs`, `Program.cs` | 2–3 hrs |
| **Tests** | Add tests for B15/B17/S6 (see below) | Test projects | 1 hr |

B15, B16, and B17 are all changes to `WasapiAudioSource.cs` and should ship in a
single commit. S6 is a separate commit.

---

## Tests to Add

### B15 regression test (verify `sessionControl` kept alive)

No unit test can directly assert GC liveness. Add a smoke test that creates a
`WasapiAudioSource` (using the real Windows API on a CI machine with audio, or
via a test-double that records whether the event handler was ever called), verifies
that `OnSessionDisconnected` fires when the session is terminated, and that `CaptureAsync`
exits with an `AudioCaptureException`. The existing `FaultyAudioSource` test doubles
can be extended for this.

### B17 regression test

Extend the `WasapiSessionEventClient` test (or create one) that calls `OnStateChanged`
with `AudioSessionState.AudioSessionStateExpired` and asserts that:
- `innerChannel` is completed with an `AudioCaptureException`
- `staCts` is cancelled

Since `WasapiSessionEventClient` is `private sealed`, expose it via `InternalsVisibleTo`
or test it indirectly through a `FaultyAudioSource` that simulates state expiry.

### S6 watchdog test

**Interface note (C1 + SCR-1):** `TickAsync` takes `bool audioWasActive` — the value
already consumed by the heartbeat's `ConsumeAndReset()` call. The watchdog does not
hold an `AudioActivityMonitor` reference. Tests pass `true`/`false` directly;
`onRestart` is `Func<Task>` (not `Func<ValueTask>`) matching the codebase pattern.

Create `AudioWatchdogTests.cs`:

```csharp
[Fact(DisplayName = "S6: Watchdog triggers restart after 3 consecutive silent windows while capturing")]
public async Task Watchdog_TriggersRestart_AfterThresholdSilentWindows()
{
    // Arrange
    var restarts = 0;

    var watchdog = new AudioWatchdog(
        isCapturing: () => true,
        onRestart:   () => { restarts++; return Task.CompletedTask; },
        threshold:   3);

    // Act — await each tick so onRestart completes before assertion
    await watchdog.TickAsync(audioWasActive: false);
    await watchdog.TickAsync(audioWasActive: false);
    await watchdog.TickAsync(audioWasActive: false);

    // Assert — deterministic: onRestart is awaited inside TickAsync
    restarts.Should().Be(1, "watchdog must trigger exactly once after threshold is reached");
}

[Fact(DisplayName = "S6: Watchdog does not trigger when not capturing")]
public async Task Watchdog_DoesNotTrigger_WhenNotCapturing()
{
    var restarts = 0;

    var watchdog = new AudioWatchdog(
        isCapturing: () => false,   // pipeline not running
        onRestart:   () => { restarts++; return Task.CompletedTask; },
        threshold:   3);

    await watchdog.TickAsync(audioWasActive: false);
    await watchdog.TickAsync(audioWasActive: false);
    await watchdog.TickAsync(audioWasActive: false);

    restarts.Should().Be(0, "watchdog must not restart a pipeline that is not running");
}

[Fact(DisplayName = "S6: Watchdog resets counter when audio is active")]
public async Task Watchdog_ResetsCounter_WhenAudioActive()
{
    var restarts = 0;

    var watchdog = new AudioWatchdog(
        isCapturing: () => true,
        onRestart:   () => { restarts++; return Task.CompletedTask; },
        threshold:   3);

    await watchdog.TickAsync(audioWasActive: false);  // silent window 1
    await watchdog.TickAsync(audioWasActive: false);  // silent window 2
    await watchdog.TickAsync(audioWasActive: true);   // active → counter resets to 0
    await watchdog.TickAsync(audioWasActive: false);  // silent window 1 again
    await watchdog.TickAsync(audioWasActive: false);  // silent window 2

    restarts.Should().Be(0, "counter must reset on any active window before threshold is reached");
}
```

**Production usage** — in `HandleAsync` heartbeat loop:
```csharp
var active = audioMonitor?.ConsumeAndReset() ?? false;
if (watchdog is not null)
    _ = watchdog.TickAsync(active);   // fire-and-forget; does not block heartbeat
```

---

---

## Addendum — QA Responses to Developer Review (`dev-briefing-5-review.md`)

**Date:** 2026-05-23

### C1 — Tick() synchronicity: **Option A chosen, interface refined** ✅

`AudioWatchdog.TickAsync(bool audioWasActive)` returns `ValueTask`. The restart
is `await`ed inside the method; the caller fires-and-forgets with
`_ = watchdog.TickAsync(active)`.

The `bool` parameter (added during SCR-1 resolution) eliminates the need for
`AudioActivityMonitor` in the watchdog constructor: the heartbeat loop already
holds the consumed value and passes it in. This makes the watchdog simpler and
removes the double-consume hazard entirely.

Rationale for Option A over Option B:
- Tests `await watchdog.TickAsync(false/true)` directly — deterministic, no race.
- No hidden `Task.Run` inside the watchdog — honest async surface, no threadpool cost on non-triggering ticks.
- `onRestart` type is `Func<Task>` (not `Func<ValueTask>`) to match the codebase pattern.

Test stubs updated throughout. See the **S6 watchdog test** section.

---

### C2 — `AudioSessionManager` lifetime: verified from NAudio 2.2.1 source ✅

NAudio 2.2.1 was decompiled (`NAudio.Wasapi.dll`, `netstandard2.0`). Findings:

**Both properties are lazily initialised and cached:**

```csharp
// MMDevice (line 12765–12773 in decompiled output)
private AudioSessionManager audioSessionManager;  // cached field

public AudioSessionManager AudioSessionManager
{
    get
    {
        if (audioSessionManager == null) GetAudioSessionManager();
        return audioSessionManager;
    }
}

// AudioSessionManager (confirmed cached field)
private AudioSessionControl audioSessionControl;

public AudioSessionControl AudioSessionControl
{
    get
    {
        if (audioSessionControl == null)
        {
            audioSessionInterface.GetAudioSessionControl(Guid.Empty, 0u, out var sessionControl);
            audioSessionControl = new AudioSessionControl(sessionControl);
        }
        return audioSessionControl;
    }
}
```

**`AudioSessionControl.Dispose()` / finalizer calls `UnregisterAudioSessionNotification`
(confirmed):**

```csharp
public void Dispose()
{
    if (audioSessionEventCallback != null)
    {
        Marshal.ThrowExceptionForHR(
            audioSessionControlInterface.UnregisterAudioSessionNotification(audioSessionEventCallback));
        audioSessionEventCallback = null;
    }
    GC.SuppressFinalize(this);
}
~AudioSessionControl() { Dispose(); }
```

**Conclusion — B15 is confirmed and the fix is correct:**

The GC premature-collection chain is real:
1. `sessionControl` local → dead after `RegisterEventClient()` in optimised build
2. `device` local → dead after `device.AudioSessionManager.AudioSessionControl` access
3. Both collected → `audioSessionControl` unreachable → finalizer →
   `UnregisterAudioSessionNotification` → B11 deregistered silently

The B15 fix (move `sessionControl` to outer scope + dispose in `finally`) breaks
this chain: `sessionControl` is referenced in `finally`, so it cannot be collected
before `finally` runs, so `audioSessionControl` stays alive for the full session.

**C2's specific concern — `AudioSessionManager` GC risk:**

Because `AudioSessionManager` IS cached by `MMDevice`, `device.AudioSessionManager`
always returns the same instance. That instance is alive as long as `device` is
alive. When `device` is collected, `audioSessionManager.Dispose()` is called, but
this does NOT dispose `audioSessionControl`. The `audioSessionControl` object remains
alive because `sessionControl` (outer scope) holds the reference.

**Adding an explicit `sessionManager` local is therefore OPTIONAL, not required.**
The B15 fix alone is correct and complete. That said, the developer's suggestion to
store `sessionManager` explicitly is accepted as good defensive practice — it
documents the COM lifetime intent, costs one variable, and eliminates any doubt
about future NAudio behaviour changes. Include it if you prefer; omit it if you
prefer the shorter form. Either is correct.

If you include `sessionManager`, dispose in reverse order (session control first,
then manager) to ensure the event registration is cleanly removed before the
session manager is torn down:

```csharp
finally
{
    try { sessionControl?.Dispose(); } catch { }   // UnregisterAudioSessionNotification
    try { sessionManager?.Dispose(); } catch { }   // UnregisterSessionNotification
    if (capture is not null)
    {
        try { capture.StopRecording(); } catch { }
        try { capture.Dispose();       } catch { }
    }
}
```

---

### C3 — `async Task` without `await` in test stubs ✅

Resolved by C1. Option A → tests `await watchdog.TickAsync(...)` → `async Task`
is correct; no `CS1998` warning. No separate action needed.

---

### C4 — DIAG table duplicate rows ✅

Fixed above. The **First Diagnostic Step** table now has a `Log entry present?`
column that distinguishes the two `captureActive=false` / `audioActive=false`
scenarios. See the updated table in that section.

---

### SCR-1 — `HandleAsync` wiring guidance ✅ Applied

Six-step wiring guide added to the S6 section: `restartPipeline` definition in
`Program.cs` → `WebApp.Create` parameter → call-site update → `HandleAsync`
signature update → `WebApp.cs` call-site update → watchdog construction and
heartbeat integration. The `AudioWatchdog` class design is fully specified (no
`AudioActivityMonitor` in constructor; `TickAsync(bool audioWasActive)` interface).

---

### SCR-2 — `PlatformAudioSource` constructor change ✅ Applied

Concrete code block added to the B15 **Note** section. Covers: `WasapiAudioSource`
constructor with `ILogger` parameter, `PlatformAudioSource` constructor and
`ResolveForCurrentPlatform` signature, and the `Program.cs` construction site.

---

### SCR-3 — Multi-connection watchdog scope ✅ Applied

Note added to the S6 **Thread safety** paragraph: per-connection counter; double-
restart is safe (`StartAsync` calls `StopAsync` first) but redundant; normal
daemon operation is single-user; no additional synchronisation required.

---

### SCR-4 — `await Task.CompletedTask` no-ops in test stubs ✅ Applied

All three test stubs updated to `() => { restarts++; return Task.CompletedTask; }`.
`onRestart` parameter type throughout is `Func<Task>` (not `Func<ValueTask>`).

---

### SCR-5 — Exception handler in `restartPipeline` lambda ✅ Applied

**Accepted.** The developer's fault-propagation analysis is correct. When `_onRestart()`
throws inside `TickAsync`, the exception faults the returned `ValueTask`. The call
site discards it with `_ = watchdog.TickAsync(active)` — the exception is silently
lost, `_silentWindows` has already been reset to 0, and the operator sees nothing.

The fix is applied in the `restartPipeline` lambda (Step 1 of the wiring guide): a
top-level `try/catch(Exception ex)` wraps the entire body and logs at `Error` on
failure. With this guard in place `TickAsync` will never see a throw from
`_onRestart()`, so the discarded `ValueTask` concern is neutralised at source.

Note: `device` is a local variable scoped to the `try` block and is not accessible
in the `catch`. The catch re-reads `configStore.Current.AudioDeviceName`, which is
correct — this is consistent with the developer's proposed fix as written.

---

### SCR-6 — S6 `Files` header expanded ✅ Applied

The header now lists all four files touched by S6:
`AudioWatchdog.cs` (new), `WebSocketHub.cs`, `WebApp.cs`, `Program.cs`.

---

### SCR-7 — AO2 corrected: S6 cannot restart a Case 2 exit ✅ Applied

**Accepted. The original claim was incorrect and is retracted.**

A Case 2 exit (`RecordingStopped` fires with `e.Exception == null`, source ends
normally) sets `_isCapturing = false` in the `CaptureManager.finally` block within
microseconds — long before the next watchdog tick. The watchdog evaluates
`captureManager.IsCapturing == true` as part of its trigger condition; that condition
is already `false`. The watchdog resets its counter and never fires.

AO2 now states this accurately, explains the two fix options (invoke `CaptureFailed`
from Case 2, or add a separate IsCapturing-off watchdog), and marks both as
follow-on items out of scope for this round. The erroneous "less critical" language
has been removed.

---

### SCR-8 — Work Order S6 file list updated ✅ Applied

The S6 row in the Work Order table now matches the S6 header: `AudioWatchdog.cs`
(new), `WebSocketHub.cs`, `WebApp.cs`, `Program.cs`.

---

## Updated Merge Checklist

| # | Item | Status |
|---|---|---|
| B10 | staCts / linked-CTS fix | ✅ Done |
| B11 | WasapiSessionEventClient registered | ✅ Done (but undermined by B15/B17) |
| B12 | ODE guard on staCts.Cancel() | ✅ Done |
| B13 | DataAvailable handler wrapped in try-catch | ✅ Done |
| B14 | Redundant StartAsync removed from OnSaved | ✅ Done |
| S5 | Dead configLogger variable | ✅ Done |
| **B15** | sessionControl moved to outer scope, disposed in finally | ❌ Required |
| **B16** | B11 registration failure logged at Warning | ❌ Required (part of B15 commit) |
| **B17** | OnStateChanged handles Expired state | ❌ Required (part of B15 commit) |
| **S6** | Watchdog: 3 × 5 s silence → restart | ❌ Required |
| B6 | WAV fixture — obtain, commit, un-skip e2e test | ❌ Required |
| FR-017 | Start/stop control — AppConfig.DecodingEnabled, UI toggle | ❌ Required |
| PR | Open draft PR to main (task 13.5) | ❌ Do last |
