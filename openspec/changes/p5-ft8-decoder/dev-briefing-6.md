# Developer Briefing — p5-ft8-decoder (Round 6)

**Date:** 2026-05-23
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Severity:** BLOCKING — audio capture must always be running per Captain's directive

---

## Executive Summary

Every previous fix (B10–B18, S6) addressed either a specific WASAPI event failure
mode or a scenario where the capture infrastructure silently stalls while
`IsCapturing` remains `true`. The persistent symptom is none of those.

The root cause is a **two-part structural defect** in the restart architecture:

1. **B19** — `CaptureManager` does not invoke `CaptureFailed` when WASAPI stops
   gracefully without an exception (Case 2). The pipeline goes idle silently.
2. **B20** — The `CaptureFailed` handler in `Program.cs` only logs; it never
   restarts the pipeline. Even Case 3 failures (exceptions) leave the daemon
   permanently idle.

S6 (AudioWatchdog) **cannot compensate**. Its trigger condition requires
`captureManager.IsCapturing == true`. By the time the watchdog ticks, `IsCapturing`
is already `false`. The watchdog sees `!_isCapturing()`, resets its silent counter
to 0, and never fires.

**No existing mechanism restarts the pipeline on any unexpected capture stop.**

---

## Failure Sequence

```
1. App starts → StartPipeline(device) → captureManager.StartAsync(device)
2. WasapiAudioSource: capture.StartRecording() ← recording begins
3. [A few seconds later] RecordingStopped fires with e.Exception == null
4. innerChannel.Writer.TryComplete() ← channel completed without error
5. staCts.Cancel() ← STA thread unblocks → finally runs → capture disposed
6. CaptureManager await foreach exits normally
7. linkedCt.IsCancellationRequested == false → Case 2 branch:
      LogWarning("Capture ended unexpectedly…")
      // CaptureFailed is NOT invoked        ← B19
8. finally: _isCapturing = false
9. Watchdog ticks at T+5s: !_isCapturing() == true → resets counter, no restart
10. Pipeline is permanently idle.  User sees: audio capture stopped.
```

---

## B19 — `CaptureManager` does not invoke `CaptureFailed` on Case 2 (BLOCKER)

**File:** `src/OpenWSFZ.Audio/CaptureManager.cs`
**Lines:** 111–120

### Root Cause

The Case 2 branch logs a warning but does not raise `CaptureFailed`:

```csharp
else
{
    // Case 2: unexpected end
    _logger?.LogWarning(
        "Capture ended unexpectedly on device '{DeviceId}'. " +
        "The audio source stopped without a cancellation signal — " +
        "this may indicate a driver-level or audio-engine stop not requested by the application.",
        deviceId);
    // CaptureFailed is NOT invoked
}
```

`CaptureFailed` is the only signal available to `Program.cs` for restart decisions.
Case 2 never fires it. `IsCapturing` goes false. S6 watchdog evaluates
`!_isCapturing()` → true → resets counter → never triggers. Pipeline stays idle.

**What triggers Case 2?**

WASAPI's `RecordingStopped` with `e.Exception == null`. Common causes:
- Driver-level power management silently stopping the capture session
- Audio engine format re-negotiation (a brief stop without an error)
- Session expiry that B17's `OnStateChanged(Expired)` doesn't see (some drivers
  skip the session event entirely and go straight to `RecordingStopped`)
- `MMDevice` being invalidated by a hardware event that isn't surfaced as
  an `IAudioSessionEvents` notification

All produce the same symptom: `RecordingStopped` fires, no exception, pipeline idles.

### Required Fix

Replace the Case 2 block in `StartAsync`. Three changes:
- Construct an `AudioCaptureException` wrapping the event
- Pass the exception as the first argument to `LogWarning` so it appears in logs
- Invoke `CaptureFailed` to trigger the restart path

```csharp
// BEFORE (lines 112–120):
else
{
    _logger?.LogWarning(
        "Capture ended unexpectedly on device '{DeviceId}'. ...",
        deviceId);
}

// AFTER:
else
{
    // Case 2: unexpected end — source ended without any cancellation signal.
    // Treat this as a fault so the CaptureFailed restart path is triggered.
    // Without this, IsCapturing goes false and the watchdog cannot restart.
    var unexpectedEndEx = new AudioCaptureException(deviceId,
        "The audio source stopped unexpectedly without a cancellation signal. " +
        "This may indicate a driver-level power-management stop, a format " +
        "re-negotiation, or a session expiry not surfaced as a session event.");
    _logger?.LogWarning(unexpectedEndEx,
        "Capture ended unexpectedly on device '{DeviceId}'.", deviceId);
    CaptureFailed?.Invoke(unexpectedEndEx);
}
```

---

## B20 — `CaptureFailed` handler does not restart the pipeline (BLOCKER)

**File:** `src/OpenWSFZ.Daemon/Program.cs`
**Lines:** 59–61

### Root Cause

```csharp
// Current — logs only, never restarts:
captureManager.CaptureFailed += ex =>
    startupLogger.LogError(ex, "Audio capture error: {Message}", ex.Message);
```

This handler fires for Case 3 (exception-driven failures). With B19 fixed, it will
also fire for Case 2. In both cases, it does nothing but log. The pipeline remains
idle after every unforced capture termination.

### Required Fix

Replace the handler with one that logs and schedules a restart with a 5-second backoff.

```csharp
captureManager.CaptureFailed += ex =>
{
    startupLogger.LogError(ex,
        "Audio capture failed on '{Device}': {Message}",
        configStore.Current.AudioDeviceName, ex.Message);

    // Auto-restart: audio capture should always be running.
    // Read device at failure time; if the user changes device between failure
    // and restart, configStore.OnSaved handles that separately.
    var device = configStore.Current.AudioDeviceName;
    if (device is null) return;

    _ = Task.Run(async () =>
    {
        // 5-second backoff: prevents rapid restart loops on persistent failures
        // (e.g. device genuinely unavailable) while keeping recovery prompt
        // for transient stops (power management, format re-negotiation).
        await Task.Delay(TimeSpan.FromSeconds(5));

        // Guard: if a device change or another restart path has already
        // restarted capture, do not start a second session.
        if (captureManager.IsCapturing) return;

        startupLogger.LogInformation(
            "Auto-restarting audio capture on device '{Device}' after failure.", device);

        await StopFramerAsync();
        audioMonitor.Reset();
        dataFlowMonitor.Reset();
        StartPipeline(device);
    });
};
```

**Important constraint:** `StopFramerAsync`, `audioMonitor`, `dataFlowMonitor`, and
`StartPipeline` are all in scope as closures from the top-level program. Do NOT
restructure these into separate methods; the existing capture ensures correct
variable capture semantics.

---

## Why S6 Cannot Cover This

The `AudioWatchdog.TickAsync` trigger condition is:

```csharp
if (dataWasFlowing || !_isCapturing())
{
    _silentWindows = 0;
    return;   // ← always taken after Case 2 or Case 3
}
```

After `CaptureManager.finally` sets `_isCapturing = false`, the watchdog's
`!_isCapturing()` branch is permanently true. The counter is reset on every tick.
The watchdog was designed for the **hung-while-capturing** scenario (WASAPI stalls
silently but `RecordingStopped` never fires). It is not a substitute for a
`CaptureFailed` restart handler.

Both S6 and B19+B20 must be present: S6 handles the hung case; B20 handles
the terminated case.

---

## Tests Required

### T-B19 — `CaptureManager` raises `CaptureFailed` on unexpected graceful stop

Add to `tests/OpenWSFZ.Audio.Tests/CaptureManagerTests.cs`, adjacent to the
existing `StartAsync_WhenSourceEndsNaturally_LogsWarning` test.

```csharp
[Fact(DisplayName = "B19: CaptureManager raises CaptureFailed when source ends without cancellation")]
public async Task StartAsync_WhenSourceEndsNaturally_RaisesCaptureFailed()
{
    // Arrange — FiniteAudioSource (3 chunks) simulates WASAPI RecordingStopped
    // with e.Exception == null (graceful unexpected stop).
    await using var cm = new CaptureManager(new FiniteAudioSource(chunkCount: 3));

    var failureTcs = new TaskCompletionSource<Exception>(
        TaskCreationOptions.RunContinuationsAsynchronously);
    cm.CaptureFailed += ex => failureTcs.TrySetResult(ex);

    // Act
    await cm.StartAsync("mic-b19");

    // Assert — CaptureFailed must fire and carry an AudioCaptureException.
    var caughtEx = await failureTcs.Task.WaitAsync(TimeSpan.FromSeconds(5));

    caughtEx.Should().BeOfType<AudioCaptureException>(
        "Case 2 (unexpected source end) must raise CaptureFailed with " +
        "AudioCaptureException so the B20 restart path is triggered — without " +
        "this, the pipeline stays permanently idle after any graceful WASAPI stop");

    cm.IsCapturing.Should().BeFalse(
        "IsCapturing must be false once the unexpected stop completes");
}
```

**Existing test compatibility:** `StartAsync_WhenSourceEndsNaturally_LogsWarning` asserts
that a Warning log entry is produced. The B19 fix still logs at Warning (now with the
exception as the first argument). That test continues to pass unchanged.

### T-B19b — `CaptureFailed` fires even when `FiniteAudioSource` drains cleanly

Verify that the `FiniteAudioSource` test double correctly simulates Case 2 — i.e. it
does not throw and does not check the cancellation token mid-drain. The existing
`FiniteAudioSource` implementation is correct; this is a note, not a new test.

---

## Commit Guidance

Two commits. Keep them separate so each is independently revertible.

**Commit 1 — B19:**
```
fix(audio): B19 — CaptureManager invokes CaptureFailed on unexpected graceful stop

Case 2 (RecordingStopped with null exception) previously logged a warning but did
not invoke CaptureFailed.  Without this signal, IsCapturing goes false and the
S6 watchdog cannot restart — the pipeline stays permanently idle.

Fix: construct AudioCaptureException in Case 2 branch; log it at Warning with
the exception object; invoke CaptureFailed so the restart path fires.
Add T-B19 regression test.
```

Files:
- `src/OpenWSFZ.Audio/CaptureManager.cs`
- `tests/OpenWSFZ.Audio.Tests/CaptureManagerTests.cs`

**Commit 2 — B20:**
```
fix(daemon): B20 — CaptureFailed handler restarts pipeline after capture failure

The handler previously only logged the error. Any unforced capture termination
(Case 2 or Case 3) left the pipeline permanently idle.

Fix: schedule a restart with 5-second backoff on every CaptureFailed event.
Guard with IsCapturing check to prevent double-start if another path has already
restarted.
```

Files:
- `src/OpenWSFZ.Daemon/Program.cs`

---

## Verification Steps

After both fixes are applied and the suite is green:

1. `dotnet build -c Release` — 0 errors, 0 warnings
2. `dotnet test -c Release` — all tests pass; T-B19 is new and must pass
3. **Manual smoke test:** start the daemon with a configured audio device.
   Observe the log for the Case 2 warning.
   After the B20 fix, a log line:
   ```
   [INF] Auto-restarting audio capture on device '...' after failure.
   ```
   must appear within 6 seconds of the warning. Capture must resume.
4. Confirm `/api/v1/status` shows `captureActive: true` after the restart.

---

## Note on D1/D2 Diagnostic Commits

Commits `29e182c` (`diag(audio): D1 + D2`) introduced `DataFlowMonitor` and wired
`captureManager.ChunkReceived → dataFlowMonitor.OnChunkReceived()`. This is
**production code** required by S6/B18. It is not temporary diagnostic logging and
must not be removed.

---

## Updated Merge Checklist

| # | Item | Status |
|---|---|---|
| B10–B14 | WASAPI threading + event-client fixes | ✅ Done |
| B15–B17 | GC-safe sessionControl, B11 logging, Expired state | ✅ Done |
| S6 | AudioWatchdog (hung-while-capturing scenario) | ✅ Done |
| B18 | Watchdog uses data-flow gate, not amplitude | ✅ Done |
| **B19** | CaptureManager raises CaptureFailed on Case 2 | ❌ Required |
| **B20** | CaptureFailed handler restarts pipeline with backoff | ❌ Required |
| B6 | WAV fixture — obtain, commit, un-skip integration test | ❌ Required (next phase) |
| 13.4 | Manual smoke test with real device | ❌ Required (after B19+B20) |
| PR | Open draft PR to `main` (task 13.5) | ❌ After all above |
