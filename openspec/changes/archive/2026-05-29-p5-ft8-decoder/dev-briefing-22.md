# Developer Briefing — p5-ft8-decoder (Round 22)

**Date:** 2026-05-24
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Scope:** Remove diagnostic logging from the audio capture hot path

---

## Situation

All performance fixes from dev-briefings 20 and 21 have been applied and the problem
persists. The root cause is the diagnostic logging that was added incrementally across
earlier briefings to diagnose audio pipeline issues. Those issues are now resolved; the
logging remains and is now the dominant source of overhead.

The core of the problem is the `DataAvailable` event handler in `WasapiAudioSource`.
This handler fires **approximately 50 times per second** on the WASAPI capture thread.
It currently contains diagnostic code that runs on every single callback:

1. **`rawHasData` byte-scan loop** — iterates over all raw bytes from the WASAPI buffer
   on every callback. Introduced to diagnose zero-audio; audio is now confirmed flowing.

2. **Three `LogInformation` calls per callback** (on callbacks #1–5 and every #100):
   raw bytes check, first-sample float interpretation, and direct-cast maxAbs scan. Each
   `LogInformation` call boxes its integer/bool arguments, formats a string, and writes
   to the console sink. At a 50 Hz callback rate, this is measurable I/O on an audio thread.

3. **`chunk.All(sample => sample == 0)` LINQ check** — evaluates on every successfully
   written chunk. This creates a heap-allocated LINQ `IEnumerator` and invokes a lambda
   per sample (~240 times) at 50 Hz. Introduced to detect the NAudio pipeline zeroing
   audio; that bug is resolved.

4. **`L-5` resampler-zero check** — accesses `buffer.BufferedBytes` (an Interlocked
   read) every 100th callback, then logs a conditional warning. Unnecessary now that
   resampler output is confirmed non-zero.

These together mean the `DataAvailable` handler is doing significant unnecessary work
on a real-time audio thread, 50 times per second, on top of the actual audio processing.

---

## Tasks

### L1 — Replace the entire `DataAvailable` handler body

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`

Replace the full `capture.DataAvailable` handler (everything between `capture.DataAvailable += (_, e) =>` and the closing `};`) with the following. All diagnostic variables (`dataAvailableFired`, `dataAvailableCount`, `zeroOutputCount`, `rawHasData`, `dataAvailable*`) are removed with it — do not declare them.

```csharp
capture.DataAvailable += (_, e) =>
{
    try
    {
        buffer.AddSamples(e.Buffer, 0, e.BytesRecorded);

        // Warn if the buffer is near-full (> 4 s). This indicates the consumer
        // is stalling and new audio will be silently discarded.
        if (buffer.BufferedDuration.TotalMilliseconds > 4000)
        {
            _logger?.LogWarning(
                "BufferedWaveProvider near full on '{DeviceId}': " +
                "{BufferedMs:F0} ms — consumer may be stalled.",
                deviceId,
                buffer.BufferedDuration.TotalMilliseconds);
        }

        // Drain the resampler in 2 048-sample chunks.
        var outBuf = new float[2048];
        int read;
        while ((read = resampler.Read(outBuf, 0, outBuf.Length)) > 0)
        {
            var chunk = new float[read];
            outBuf.AsSpan(0, read).CopyTo(chunk);

            if (!innerChannel.Writer.TryWrite(chunk))
            {
                _logger?.LogWarning(
                    "Audio chunk dropped on '{DeviceId}' ({Samples} samples) — " +
                    "consumer is not keeping up.",
                    deviceId,
                    chunk.Length);
            }
        }
    }
    catch (Exception ex)
    {
        innerChannel.Writer.TryComplete(ex);
        try { staCts.Cancel(); } catch (ObjectDisposedException) { }
    }
};
```

**What was removed and why:**

| Removed | Reason |
|---|---|
| `dataAvailableFired` + first-buffer log | One-time diagnostic — audio is confirmed |
| `dataAvailableCount` + per-100 counter log | Heartbeat was for diagnosis; no longer needed |
| `rawHasData` byte-scan loop | Confirmed audio flows; scan is pure overhead at 50 Hz |
| raw-bytes log, first-sample log, direct-cast log | All three ran on callbacks #1–5 and every #100; resolved |
| `zeroOutputCount` + zero-output LINQ check (`chunk.All(...)`) | Resampler output confirmed non-zero; LINQ at 50 Hz is costly |
| D5 phase-cancellation stereo check | Differential signal issue resolved by `LeftChannelSampleProvider` |
| L-5 resampler-zero warning block | `BufferedBytes` access on every 100th callback; condition never fires |

**What was kept:**

| Kept | Reason |
|---|---|
| L-4 BufferedWaveProvider near-full warning | Fires only under abnormal backpressure — real operational signal |
| L-6 innerChannel drop warning | Fires only when the consumer is genuinely stalling — real operational signal |

---

### L2 — Clean up `WasapiSessionEventClient`

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`

#### L2a — `OnStateChanged`: log only the `Expired` transition

The current implementation logs every session state transition at `LogInformation`. The
`Active ↔ Inactive` transitions are normal and fire regularly (e.g. during device
re-negotiation); logging them produces noise and allocates strings on a COM event thread.
Only the `Expired` transition requires an action and a log entry.

Replace the current `OnStateChanged` method:

```csharp
// Before:
public void OnStateChanged(AudioSessionState state)
{
    // L-10 (DIAG): log all state transitions ...
    _logger?.LogInformation(
        "DIAG OnStateChanged on '{DeviceId}': state = {State}",
        _deviceId, state);

    if (state == AudioSessionState.AudioSessionStateExpired)
    {
        ...
    }
}
```

```csharp
// After:
public void OnStateChanged(AudioSessionState state)
{
    if (state != AudioSessionState.AudioSessionStateExpired) return;

    _logger?.LogWarning(
        "WASAPI audio session expired on '{DeviceId}'.", _deviceId);

    var ex = new AudioCaptureException(
        _deviceId,
        "WASAPI audio session expired (OnStateChanged: Expired).");

    _channel.Writer.TryComplete(ex);
    try { _staCts.Cancel(); } catch (ObjectDisposedException) { }
}
```

#### L2b — `OnVolumeChanged`: remove the log

Volume changes are irrelevant to capture correctness; logging them allocates on a COM
event thread at an unpredictable rate.

Replace:
```csharp
// Before:
public void OnVolumeChanged(float volume, bool isMuted)
{
    _logger?.LogInformation(
        "DIAG OnVolumeChanged on '{DeviceId}': volume={Volume:F2}, isMuted={IsMuted}",
        _deviceId, volume, isMuted);
}
```

```csharp
// After:
public void OnVolumeChanged(float volume, bool isMuted) { }
```

#### L2c — `OnSessionDisconnected`: remove the "DIAG" prefix

```csharp
// Before:
_logger?.LogError(
    "DIAG OnSessionDisconnected on '{DeviceId}': reason = {Reason}",
    _deviceId, disconnectReason);

// After:
_logger?.LogError(
    "WASAPI session disconnected on '{DeviceId}': {Reason}",
    _deviceId, disconnectReason);
```

---

### L3 — Clean up setup and shutdown logs in the STA thread

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`

#### L3a — Demote `StartRecording` progress logs to `LogDebug`

These fire once per session and carry no actionable information; at `LogInformation`
they appear in the console on every capture start.

```csharp
// Before:
_logger?.LogInformation(
    "Calling capture.StartRecording() on '{DeviceId}'.", deviceId);
capture.StartRecording();
_logger?.LogInformation(
    "capture.StartRecording() returned on '{DeviceId}'.", deviceId);

// After:
_logger?.LogDebug("Starting capture on '{DeviceId}'.", deviceId);
capture.StartRecording();
_logger?.LogDebug("Capture started on '{DeviceId}'.", deviceId);
```

#### L3b — Remove "DIAG" prefix from the `RecordingStopped` handler logs

```csharp
// Before:
_logger?.LogError(e.Exception,
    "DIAG RecordingStopped — WASAPI error on '{DeviceId}': {ExType} — {ExMessage}",
    deviceId, e.Exception.GetType().Name, e.Exception.Message);

_logger?.LogWarning(
    "DIAG RecordingStopped — null exception on '{DeviceId}' " +
    "(graceful/unexpected stop; doStop was set internally by NAudio).",
    deviceId);

// After:
_logger?.LogError(e.Exception,
    "RecordingStopped with error on '{DeviceId}': {ExType} — {ExMessage}",
    deviceId, e.Exception.GetType().Name, e.Exception.Message);

_logger?.LogInformation(
    "RecordingStopped (graceful) on '{DeviceId}'.", deviceId);
```

#### L3c — Remove "DIAG" prefix from STA finally logs

Replace the six "DIAG STA finally:" prefix strings with clean equivalents.

```csharp
// "DIAG STA finally: beginning cleanup on '{DeviceId}'."
// → "Audio capture cleanup starting on '{DeviceId}'."

// "DIAG STA finally: disposing sessionControl on '{DeviceId}'."
// → Remove this line entirely (sessionControl disposal is an implementation detail).

// "DIAG STA finally: calling capture.StopRecording() on '{DeviceId}' (3 s timeout)."
// → "Stopping capture on '{DeviceId}'."

// "DIAG STA finally: capture.StopRecording() completed on '{DeviceId}'."
// → Remove this line (success is the expected case; no log needed).

// "DIAG STA finally: calling capture.Dispose() on '{DeviceId}' (3 s timeout)."
// → Remove this line (implementation detail).

// "DIAG STA finally: capture.Dispose() completed on '{DeviceId}'."
// → Remove this line (success is the expected case; no log needed).

// "DIAG STA finally: cleanup complete on '{DeviceId}'."
// → "Audio capture cleanup complete on '{DeviceId}'."
```

The two **warning** messages (StopRecording timed out, Dispose timed out) are genuine
operational events and must be kept. Update their prefix:

```csharp
// "DIAG STA finally: capture.StopRecording() timed out after 3 s on '{DeviceId}' — ..."
// → "capture.StopRecording() timed out after 3 s on '{DeviceId}' — abandoning device handle."

// "DIAG STA finally: capture.Dispose() timed out after 3 s on '{DeviceId}' — ..."
// → "capture.Dispose() timed out after 3 s on '{DeviceId}' — abandoning device handle."
```

#### L3d — Remove "DIAG" prefix from the STA WaitOne log

```csharp
// Before:
_logger?.LogInformation(
    "DIAG STA WaitOne unblocked on '{DeviceId}' — " +
    "ct.IsCancellationRequested={CtCancelled}, " +
    "staCts.IsCancellationRequested={StaCancelled}",
    deviceId,
    ct.IsCancellationRequested,
    staCts.IsCancellationRequested);

// After:
_logger?.LogInformation(
    "Capture session unblocked on '{DeviceId}' " +
    "(ct={CtCancelled}, staCts={StaCancelled}).",
    deviceId,
    ct.IsCancellationRequested,
    staCts.IsCancellationRequested);
```

---

### L4 — Remove redundant double-log entries from `CaptureManager`

**File:** `src/OpenWSFZ.Audio/CaptureManager.cs`

The `L-12` entries log "Invoking CaptureFailed" immediately after an identical message
has already been logged at Error or Warning. Remove the second log in each case.

#### Case 2 — unexpected end

```csharp
// Before:
_logger?.LogWarning(unexpectedEndEx,
    "Capture ended unexpectedly on device '{DeviceId}'. Chunks received: {ChunksReceived}.",
    deviceId, chunksReceived);
// L-12 (DIAG): confirm the event is actually being raised (Case 2).
_logger?.LogWarning(
    "Invoking CaptureFailed on '{DeviceId}' (Case 2 — unexpected end). " +
    "Chunks received before stop: {ChunksReceived}.",
    deviceId, chunksReceived);
CaptureFailed?.Invoke(unexpectedEndEx);

// After:
_logger?.LogWarning(unexpectedEndEx,
    "Capture ended unexpectedly on device '{DeviceId}'. Chunks received: {ChunksReceived}.",
    deviceId, chunksReceived);
CaptureFailed?.Invoke(unexpectedEndEx);
```

#### Case 3 — exception

```csharp
// Before:
_logger?.LogError(ex,
    "Capture failed on device '{DeviceId}': {ExType} — {ExMessage}. Chunks received: {ChunksReceived}.",
    deviceId, ex.GetType().Name, ex.Message, chunksReceived);
// L-12 (DIAG): confirm the event is actually being raised (Case 3).
_logger?.LogError(
    "Invoking CaptureFailed on '{DeviceId}' (Case 3 — exception). " +
    "Chunks received before stop: {ChunksReceived}.",
    deviceId, chunksReceived);
CaptureFailed?.Invoke(ex);

// After:
_logger?.LogError(ex,
    "Capture failed on device '{DeviceId}': {ExType} — {ExMessage}. Chunks received: {ChunksReceived}.",
    deviceId, ex.GetType().Name, ex.Message, chunksReceived);
CaptureFailed?.Invoke(ex);
```

---

## What the logs should look like after this briefing

On a normal start, the console should show approximately:

```
[info] WASAPI device opened: 'device-id' ('Jabra EVOLVE LINK') — WaveFormat=48000 Hz, 32-bit, 1 ch, Encoding=IeeeFloat
[info] WASAPI sub-format on 'device-id': 00000003-0000-0010-8000-00aa00389b71
[info] Resampling pipeline ready on 'device-id': channelMode=mono, inputRate=48000 Hz → 12000 Hz
[dbug] Starting capture on 'device-id'.
[dbug] Capture started on 'device-id'.
```

And on Ctrl+C:

```
[info] Application stopping — aborting WebSocket connections and shutting down capture pipeline.
[info] Capture session unblocked on 'device-id' (ct=True, staCts=True).
[info] Audio capture cleanup starting on 'device-id'.
[info] Stopping capture on 'device-id'.
[warn] capture.StopRecording() timed out after 3 s on 'device-id' — abandoning device handle.
[info] Audio capture cleanup complete on 'device-id'.
[info] Application stopped.
```

Nothing else — no repeated heartbeats, no per-callback diagnostics, no redundant entries.

---

## Summary

| Task | File | Change |
|---|---|---|
| L1 | `WasapiAudioSource.cs` | Replace DataAvailable handler — remove all hot-path diagnostic code |
| L2a | `WasapiAudioSource.cs` | `OnStateChanged` — log only Expired transition |
| L2b | `WasapiAudioSource.cs` | `OnVolumeChanged` — remove log entirely |
| L2c | `WasapiAudioSource.cs` | `OnSessionDisconnected` — remove "DIAG" prefix |
| L3a | `WasapiAudioSource.cs` | StartRecording logs — demote to `LogDebug` |
| L3b | `WasapiAudioSource.cs` | `RecordingStopped` — remove "DIAG" prefix; clean messages |
| L3c | `WasapiAudioSource.cs` | STA finally — remove intermediate step logs; remove "DIAG" prefix |
| L3d | `WasapiAudioSource.cs` | STA WaitOne unblocked — remove "DIAG" prefix |
| L4  | `CaptureManager.cs` | Remove L-12 double-log entries (Cases 2 and 3) |
