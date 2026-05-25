# Developer Briefing — p5-ft8-decoder (Round 4)

**Date:** 2026-05-23
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Head commit reviewed:** `b227bb0` (FR-021 — classified capture-stop logging)

---

## Executive Summary

The B10 fix (commit `19b1e69`) was correctly implemented and closes the identified
`RecordingStopped`-hang scenario. However, the symptom — audio capture stops silently
with no log message — **persists because there are at least two separate root causes**,
only one of which B10 addressed.

This briefing documents all defects found during deep investigation. They are presented
in priority order. Items **B11** and **B12** are new blockers. Items **B13** and **B14**
are correctness defects that may contribute. **S6** is an architectural gap that must be
discussed before a fix is agreed.

---

## Status of B10

B10 is correctly fixed in `19b1e69`. The `staCts` / linked-CTS pattern is sound. The fix
eliminates the hang caused by `RecordingStopped` firing while the STA thread was blocked
on the **caller's** `ct`. All four scenarios in the B10 test matrix now behave correctly
at the code level.

The B10 regression test (`FiniteAudioSource`) is present and passes.

The silent-stop symptom that persists is therefore caused by one or more of the defects
described below.

---

## B11 — WASAPI audio session terminated silently by Windows (BLOCKER)

**Files:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`
**Severity:** Blocker — root cause of the persisting silent stop.

### Root cause

B10 fixed the case where NAudio fires `RecordingStopped`. B11 is the case where NAudio
**does not fire `RecordingStopped` at all**, because the WASAPI audio session is terminated
at the COM-session level before NAudio's capture loop is even aware.

Windows can invalidate a WASAPI shared-mode capture session in the following situations
without triggering NAudio's `RecordingStopped` event:

| Trigger | Windows behaviour | NAudio response |
|---|---|---|
| User changes default audio device (Sound → Output) | Session on the old endpoint is forcibly disconnected | No `RecordingStopped` if NAudio's thread hasn't been scheduled to notice |
| Exclusive-mode application claims the device | Shared-mode sessions are evicted | `IAudioSessionEvents::OnSessionDisconnected` fires on a COM thread — NAudio has no listener |
| Windows audio engine restart (e.g. after driver update) | All sessions are terminated | COM event — unheard |
| Power state change (suspend/resume) | Audio engine is torn down and rebuilt | Depends on timing; often silent |
| Format change (sample rate / channel count reconfigured) | `AUDCLNT_E_DEVICE_INVALIDATED` — session is dead | NAudio may not surface this as `RecordingStopped` |

NAudio's `WasapiCapture` captures raw audio from a COM `IAudioCaptureClient` on an
internal thread. It **does not** implement `IAudioSessionEvents` and therefore has no
mechanism to receive the `OnSessionDisconnected` notification that Windows sends when
a session is evicted.

When this happens:

```
Windows evicts the WASAPI session (audio engine reset / exclusive takeover)
  └── IAudioSessionEvents::OnSessionDisconnected fires on COM event thread
       └── NAudio has no listener → callback is silently ignored
            └── DataAvailable stops firing (no more audio from the device)
                 └── innerChannel receives no new items
                      └── ReadAllAsync(ct) in WasapiAudioSource.CaptureAsync
                           └── waits indefinitely (channel never completes)
                                └── CaptureManager._captureTask never exits
                                     └── IsCapturing = true (forever)
                                          └── ChunkReceived never called
                                               └── AudioActivityMonitor stays dark
                                                    └── NO LOG. NO EVENT. NO RECOVERY.
```

This is distinct from B10:

| | B10 (fixed) | B11 (this defect) |
|---|---|---|
| `RecordingStopped` fires? | Yes | No |
| STA thread unblocks? | Yes (after fix) | Never |
| `innerChannel` completed? | Yes (after fix) | Never |
| `CaptureAsync` exits? | Yes (after fix) | Never |
| Log message appears? | Yes (after FR-021) | Never |
| Recovery possible? | Yes (after fix) | No |

### How to reproduce

1. Start the daemon with a valid audio device configured.
2. Open Windows Sound Settings.
3. Change the default playback or recording device.
4. Observe: within 5–10 seconds, `audioActive` in the heartbeat drops to `false`.
   No `[warn]` or `[fail]` line appears in the log.

Alternatively: open any application that requests exclusive WASAPI access (Voicemeeter,
ASIO4ALL, some DAWs) on the same device.

### The fix

The fix requires registering for Windows audio session change events via
`IAudioSessionEvents` (or the higher-level `IAudioSessionManager2` / `IAudioEndpointVolumeCallback`
interfaces exposed by NAudio or the COM interop layer).

The simplest reliable approach is to subscribe to
`MMDevice.AudioSessionManager.OnSessionCreated` / the `SessionDisconnected` event that
NAudio surfaces via `AudioSessionControl`. This detects session eviction and completes
the `innerChannel` with an appropriate exception, which causes `CaptureAsync` to exit
and `CaptureManager` to raise `CaptureFailed`.

**Recommended implementation (inside `StaThread.Run<bool>` lambda, after `capture.StartRecording()`):**

```csharp
// Subscribe to WASAPI audio session events so Windows-initiated session
// termination is detected even if NAudio's RecordingStopped does not fire.
// This covers: device format changes, exclusive-mode takeover, audio engine
// restarts, and default-device switches.
AudioSessionControl? sessionControl = null;
try
{
    sessionControl = device.AudioSessionManager.GetAudioSessionControl(Guid.Empty, 0);
    sessionControl.RegisterEventClient(new WasapiSessionEventClient(innerChannel, staCts));
}
catch
{
    // Session monitoring is best-effort; failure here must not prevent capture.
}
```

Where `WasapiSessionEventClient` is a small class implementing `IAudioSessionEventsHandler`
(NAudio's managed wrapper):

```csharp
private sealed class WasapiSessionEventClient : IAudioSessionEventsHandler
{
    private readonly Channel<float[]>           _channel;
    private readonly CancellationTokenSource    _staCts;

    public WasapiSessionEventClient(Channel<float[]> channel, CancellationTokenSource staCts)
    {
        _channel = channel;
        _staCts  = staCts;
    }

    public void OnSessionDisconnected(AudioSessionDisconnectReason disconnectReason)
    {
        // Windows terminated the session (format change, exclusive takeover, etc.).
        // Complete the channel with a descriptive exception so CaptureManager
        // surfaces the event via CaptureFailed and FR-021 logs it at Error.
        var ex = new AudioCaptureException(
            "unknown",
            $"WASAPI audio session disconnected: {disconnectReason}");

        _channel.Writer.TryComplete(ex);

        try { _staCts.Cancel(); } catch (ObjectDisposedException) { }
    }

    // All other event methods are no-ops for capture purposes.
    public void OnVolumeChanged(float volume, bool isMuted) { }
    public void OnDisplayNameChanged(string displayName) { }
    public void OnIconPathChanged(string iconPath) { }
    public void OnChannelVolumeChanged(uint channelCount, IntPtr newVolumes, uint channelIndex) { }
    public void OnGroupingParamChanged(ref Guid groupingId) { }
    public void OnStateChanged(AudioSessionState state) { }
}
```

The `sessionControl` must be disposed in the STA `finally` block alongside `capture`.

**Note on NAudio API surface:** Verify that `MMDevice.AudioSessionManager.GetAudioSessionControl`
and `IAudioSessionEventsHandler` are available in the NAudio version in use. If not,
the COM interface `IAudioSessionEvents` can be implemented directly via P/Invoke.

---

## B12 — `staCts.Cancel()` called on disposed source in second `RecordingStopped` (race condition)

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`
**Severity:** Blocker — can throw `ObjectDisposedException` on NAudio's internal thread.

### Root cause

The `RecordingStopped` handler calls `staCts.Cancel()`. After the first (unexpected)
`RecordingStopped` fires:

1. `staCts.Cancel()` → STA thread unblocks from `WaitOne()`
2. STA thread `finally` → `capture.StopRecording()` is called
3. WASAPI fires `RecordingStopped` **a second time** (from `StopRecording()`) on a WASAPI
   callback thread — this is standard NAudio/WASAPI behaviour
4. Handler: `staCts.Cancel()` is called again

The second call in step 4 races with `staCts.Dispose()` (which happens at the end of
`CaptureAsync` via `using var staCts`). The disposal sequence is:

```
STA thread:    capture.StopRecording() → starts async WASAPI teardown
STA thread:    capture.Dispose()
STA thread:    return true  →  tcs.SetResult(true)  →  staTask completes
CaptureAsync:  finally { await staTask; }  →  unblocks
CaptureAsync:  exits  →  'using var staCts'  →  staCts.Dispose()   ← (D)
WASAPI thread: RecordingStopped fires  →  staCts.Cancel()           ← (X)
```

If (X) occurs after (D), `staCts.Cancel()` throws `ObjectDisposedException` on the WASAPI
callback thread. NAudio does not wrap its event callbacks in try-catch in all versions.
On .NET 6+ this can crash the process via the unhandled-exception ratchet.

In the benign case this is silently swallowed; in the worst case it kills the process.
Either way, the existing handler is incorrect.

### The fix

Wrap `staCts.Cancel()` in a try-catch for `ObjectDisposedException` in the
`RecordingStopped` handler:

```csharp
capture.RecordingStopped += (_, e) =>
{
    // Complete the channel (propagate any WASAPI error through the pipeline).
    if (e.Exception is not null)
        innerChannel.Writer.TryComplete(e.Exception);
    else
        innerChannel.Writer.TryComplete();

    // Wake the STA thread.  Guard against ObjectDisposedException if this
    // handler fires a second time (from StopRecording() in the finally block)
    // after staCts has been disposed (B12).
    try { staCts.Cancel(); }
    catch (ObjectDisposedException) { /* already disposed — STA thread is unblocking */ }
};
```

This is a one-line change relative to the current code.

---

## B13 — `DataAvailable` handler is unguarded; exceptions can crash NAudio's capture thread

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`
**Severity:** Blocker (potential; depends on NAudio version) — silent stop with no log.

### Root cause

```csharp
capture.DataAvailable += (_, e) =>
{
    buffer.AddSamples(e.Buffer, 0, e.BytesRecorded);

    var outBuf = new float[2048];
    int read;
    while ((read = resampler.Read(outBuf, 0, outBuf.Length)) > 0)
    {
        // ...
        innerChannel.Writer.TryWrite(chunk);
        outBuf = new float[2048];
    }
};
```

If any call in this handler throws — `buffer.AddSamples` with a corrupt buffer,
`resampler.Read` with an unexpected format, or any other path — the exception propagates
to NAudio's internal capture loop.

NAudio's behaviour depends on the version:
- **NAudio ≥ 2.0**: typically catches handler exceptions and stores them in
  `RecordingStopped`'s `StoppedEventArgs.Exception`. If so, the B10 fix surfaces the
  error correctly.
- **Older NAudio / edge cases**: the exception may propagate and crash NAudio's thread
  outright, without firing `RecordingStopped`. The STA thread then blocks forever (same
  symptom as B11).

Given that the specific NAudio version in use has not been verified against this behaviour,
and that the `WdlResamplingSampleProvider` has known edge cases with certain device formats,
the handler must be made defensive.

### The fix

Wrap the handler body in a try-catch that completes the channel on failure:

```csharp
capture.DataAvailable += (_, e) =>
{
    try
    {
        buffer.AddSamples(e.Buffer, 0, e.BytesRecorded);

        var outBuf = new float[2048];
        int read;
        while ((read = resampler.Read(outBuf, 0, outBuf.Length)) > 0)
        {
            var chunk = new float[read];
            outBuf.AsSpan(0, read).CopyTo(chunk);
            innerChannel.Writer.TryWrite(chunk);
            outBuf = new float[2048];
        }
    }
    catch (Exception ex)
    {
        // DataAvailable handler failure — complete the channel so CaptureAsync
        // exits and CaptureManager surfaces the error via CaptureFailed.
        innerChannel.Writer.TryComplete(ex);
        try { staCts.Cancel(); } catch (ObjectDisposedException) { }
    }
};
```

---

## B14 — Double `StartAsync` on device change via `configStore.OnSaved` (correctness bug)

**File:** `src/OpenWSFZ.Daemon/Program.cs`
**Severity:** Defect — causes a second capture start that immediately cancels the first.

### Root cause

In the `configStore.OnSaved` handler:

```csharp
_ = Task.Run(async () =>
{
    await StopFramerAsync();
    await captureManager.StopAsync();
    audioMonitor.Reset();

    if (newDevice is not null)
    {
        try
        {
            await captureManager.StartAsync(newDevice);  // ← call (A)
            StartPipeline(newDevice);                    // ← calls StartAsync again! (B)
        }
        // ...
    }
});
```

`StartPipeline` calls `_ = captureManager.StartAsync(deviceName)` (fire-and-forget). That
second `StartAsync` begins with `await StopAsync()`, which **cancels the session just
started by call (A)** before any audio is captured. The first session stops, the second
starts. This produces confusing log output and a brief dead period in audio capture.

The log output would show:
```
[info] Starting audio capture on device 'DEVICE' (call A)
[info] Capture stopped on device 'DEVICE' (operator-stopped, source drained). (A cancelled by B's StopAsync)
[info] Starting audio capture on device 'DEVICE' (call B)
```

This is not the primary cause of the silent stop (it still logs), but it is incorrect
and should be fixed before the double-restart compounds with B11.

### The fix

Remove the redundant `await captureManager.StartAsync(newDevice)` from `OnSaved`.
`StartPipeline` handles the start:

```csharp
if (newDevice is not null)
{
    try
    {
        StartPipeline(newDevice);  // StartPipeline calls captureManager.StartAsync internally
    }
    catch (Exception ex)
    {
        startupLogger.LogError(ex,
            "Audio capture failed to restart on device '{Device}'.", newDevice);
    }
}
```

---

## S6 — No watchdog; silent-death scenarios have no auto-recovery (architectural gap)

**Files:** `src/OpenWSFZ.Daemon/Program.cs`, `src/OpenWSFZ.Web/AudioActivityMonitor.cs`
**Severity:** Suggestion (must be discussed — recovery strategy not yet agreed)

### Observation

Even with B11 fixed (session event registration), there may be edge cases where audio
stops flowing without any event firing (driver bugs, hardware issues, VM audio
pass-through quirks). There is currently no recovery mechanism: once capture stops
silently, the daemon requires a manual restart or a config POST to trigger pipeline
restart.

The `AudioActivityMonitor` already tracks activity per heartbeat window. Its
`ConsumeAndReset()` method is called every 5 seconds. This data could drive a watchdog:
if N consecutive heartbeat windows report `audioActive = false` while `IsCapturing = true`,
the pipeline should restart.

### Suggested approach (requires Captain's approval before implementation)

```
AudioActivityMonitor.ConsumeAndReset() returns false (no audio this window)
   AND CaptureManager.IsCapturing == true
   AND consecutive silent windows >= threshold (e.g. 3 × 5 s = 15 s)
        → log Warning: "Audio inactivity detected — restarting capture pipeline"
        → trigger StopFramerAsync() / captureManager.StopAsync() / StartPipeline()
```

This is NOT a substitute for B11–B13 fixes — those must be fixed regardless. This is a
belt-and-suspenders measure for edge cases the event-based fixes cannot cover.

---

## Consolidated Merge Checklist (updated)

| # | Item | Effort | Status |
|---|---|---|---|
| B11 | Implement `IAudioSessionEvents` registration in `WasapiAudioSource`; detect session disconnect and complete `innerChannel` with exception | ~2–4 hrs | ❌ |
| B11 | Add test: `CaptureManager` raises `CaptureFailed` when source completes channel with exception (session disconnect scenario) | ~30 min | ❌ (partial — existing `FaultyAudioSource` tests cover this path) |
| B12 | Wrap `staCts.Cancel()` in `RecordingStopped` handler with `catch (ObjectDisposedException)` | ~5 min | ❌ |
| B13 | Wrap `DataAvailable` handler body in try-catch; complete channel on exception | ~15 min | ❌ |
| B14 | Remove redundant `await captureManager.StartAsync(newDevice)` from `configStore.OnSaved` | ~5 min | ❌ |
| S6 | Discuss watchdog strategy with Captain before implementing | — | ❌ |
| B10 | Fix verified in code ✅ | — | ✅ |
| S5 | Dead `configLogger` variable | — | (confirm from previous briefing) |
| B6 | WAV fixture — obtain, commit, un-skip e2e test | ~2–4 hrs | ❌ |
| FR-017 | Start/stop control — `AppConfig.DecodingEnabled`, UI toggle | ~1 day | ❌ |
| PR | Open draft PR to `main` (task 13.5) | ~5 min | ❌ |

Work B11 → B12 → B13 → B14 in order. All four are changes to `WasapiAudioSource.cs`
and/or `Program.cs` only. No changes to the FT8 decoder or web layer are required.

---

## Appendix — Thread Model Reference

For convenience, the full thread topology of `WasapiAudioSource.CaptureAsync` is
reproduced below, with the new session-event thread added:

```
Thread A  [STA, background]
          MMDeviceEnumerator → WasapiCapture → StartRecording()
          Blocks on staCts.Token.WaitHandle.WaitOne()
          Unblocked by: ct cancellation (StopAsync) OR staCts.Cancel() (from B or D)

Thread B  [WASAPI internal capture thread]
          Fires DataAvailable → handler: AddSamples → resampler.Read → TryWrite(chunk)
          Fires RecordingStopped (device error OR capture.StopRecording() call)
                → handler: TryComplete(innerChannel) + staCts.Cancel()

Thread C  [COM event thread — currently unlistened]
          Fires IAudioSessionEvents::OnSessionDisconnected
          WITHOUT B11 fix: ignored (BUG)
          WITH B11 fix: → TryComplete(innerChannel) + staCts.Cancel()

Thread D  [thread-pool, async]
          Runs CaptureAsync state machine
          Reads innerChannel via ReadAllAsync(ct)
          Yields chunks to CaptureManager

Thread E  [thread-pool, async]
          Runs CaptureManager._captureTask
          Reads from CaptureAsync via await foreach
          Writes to _channel.Writer (→ CycleFramer reads this)
```

Without the Thread C listener (B11 unfixed), Thread C fires and its notification is
lost. Thread B stops producing events. Thread D waits forever. Thread E waits forever.
Operator sees silence.
