# Developer Briefing — p5-ft8-decoder (Round 8)

**Date:** 2026-05-23
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Scope:** Logging only — no functional changes

---

## Objective

Audio capture stops after a few seconds. The root cause has not yet been
confirmed from logs. This briefing prescribes comprehensive logging across
the entire audio capture pipeline so that the next run produces a complete
trace of every significant function invocation, state change, and failure
point from device open to pipeline exit.

All additions are logging only. No pipeline logic is changed.

All new entries should use `// DIAG` comments and standard
`Microsoft.Extensions.Logging.ILogger` structured-logging calls.

---

## File: `src/OpenWSFZ.Audio/WasapiAudioSource.cs`

### L-1 — Log device FriendlyName and negotiated WaveFormat

**Location:** immediately after `capture = new WasapiCapture(device, useEventSync: true);`

The WaveFormat negotiated by WASAPI at this point determines the entire
downstream resampling chain. Mismatched formats and channel counts have
historically caused silent pipeline failures. Log both the device identity
and the format before any pipeline objects are constructed.

```csharp
_logger?.LogInformation(
    "WASAPI device opened: '{DeviceId}' ('{FriendlyName}') — " +
    "WaveFormat={SampleRate} Hz, {BitsPerSample}-bit, {Channels} ch",
    deviceId,
    device.FriendlyName,
    capture.WaveFormat.SampleRate,
    capture.WaveFormat.BitsPerSample,
    capture.WaveFormat.Channels);
```

---

### L-2 — Log BufferedWaveProvider and resampler chain construction

**Location:** after `var resampler = new WdlResamplingSampleProvider(samples, 12_000);`

Confirms which resampling path was taken (stereo-to-mono or direct) and
the target sample rate.

```csharp
_logger?.LogInformation(
    "Resampling pipeline ready on '{DeviceId}': " +
    "stereoToMono={StereoToMono}, inputRate={InputRate} Hz → 12000 Hz",
    deviceId,
    capture.WaveFormat.Channels == 2,
    capture.WaveFormat.SampleRate);
```

---

### L-3 — Log periodic DataAvailable progress

**Location:** inside `capture.DataAvailable`, after the existing D1 first-buffer
check. Requires a counter variable `var dataAvailableCount = 0;` declared
alongside `dataAvailableFired`.

Log every 100 calls. This creates a heartbeat that shows exactly when data
stops flowing and how many buffers arrived before the stop.

```csharp
dataAvailableCount++;
if (dataAvailableCount % 100 == 0)
{
    _logger?.LogDebug(
        "DIAG DataAvailable: {Count} buffers on '{DeviceId}' — " +
        "BytesRecorded={Bytes}, BufferedMs={BufferedMs:F0}",
        dataAvailableCount,
        deviceId,
        e.BytesRecorded,
        buffer.BufferedDuration.TotalMilliseconds);
}
```

---

### L-4 — Log BufferedWaveProvider overflow

**Location:** replace the silent `DiscardOnBufferOverflow = true` behaviour
with a logged wrapper. The `BufferedWaveProvider` drops data silently when
the 5-second buffer fills. If the resampler is too slow to drain, the buffer
fills and overflow begins — degraded audio without any error signal.

After the `buffer.AddSamples(e.Buffer, 0, e.BytesRecorded);` line, add:

```csharp
var bufferedMs = buffer.BufferedDuration.TotalMilliseconds;
if (bufferedMs > 4000) // >80% of the 5-second buffer
{
    _logger?.LogWarning(
        "DIAG BufferedWaveProvider near full on '{DeviceId}': " +
        "{BufferedMs:F0} ms buffered — resampler may not be draining fast enough.",
        deviceId,
        bufferedMs);
}
```

---

### L-5 — Log resampler producing zero output from a non-empty input

**Location:** after the `while ((read = resampler.Read(...)) > 0)` loop exits,
still inside the `try` block of `DataAvailable`. A non-empty buffer that
produces no resampler output indicates a resampler state problem.

```csharp
if (e.BytesRecorded > 0 && dataAvailableCount > 1)
{
    var samplesInBuffer = buffer.BufferedBytes /
        (capture.WaveFormat.BitsPerSample / 8 * capture.WaveFormat.Channels);
    if (samplesInBuffer > 0)
    {
        _logger?.LogWarning(
            "DIAG Resampler produced 0 output on '{DeviceId}' " +
            "despite {SamplesInBuffer} samples in buffer.",
            deviceId,
            samplesInBuffer);
    }
}
```

---

### L-6 — Log innerChannel write drops

**Location:** replace `innerChannel.Writer.TryWrite(chunk);` with a version
that logs when the channel is full and a chunk is dropped.

```csharp
if (!innerChannel.Writer.TryWrite(chunk))
{
    _logger?.LogWarning(
        "DIAG innerChannel full on '{DeviceId}' — chunk dropped " +
        "({Samples} samples). Consumer may be stalled.",
        deviceId,
        chunk.Length);
}
```

---

### L-7 — Log capture.StartRecording() entry and exit

**Location:** wrap the `capture.StartRecording();` call.

```csharp
_logger?.LogInformation(
    "Calling capture.StartRecording() on '{DeviceId}'.", deviceId);
capture.StartRecording();
_logger?.LogInformation(
    "capture.StartRecording() returned on '{DeviceId}'.", deviceId);
```

---

### L-8 — Log STA WaitOne unblock and reason

**Location:** immediately after `staCts.Token.WaitHandle.WaitOne();`

This is the single most informative location in the entire STA thread.
When WaitOne returns, one of three things happened:
- `ct` was cancelled (operator StopAsync)
- `staCts` was cancelled by `RecordingStopped` or a session event
- An unhandled exception in the capture thread caused staCts to be cancelled

```csharp
_logger?.LogInformation(
    "DIAG STA WaitOne unblocked on '{DeviceId}' — " +
    "ct.IsCancellationRequested={CtCancelled}, " +
    "staCts.IsCancellationRequested={StaCancelled}",
    deviceId,
    ct.IsCancellationRequested,
    staCts.IsCancellationRequested);
```

---

### L-9 — Log STA finally block entry and cleanup steps

**Location:** at the very start of the `finally` block, and around each
cleanup call.

```csharp
_logger?.LogInformation(
    "DIAG STA finally: beginning cleanup on '{DeviceId}'.", deviceId);

// existing sessionControl.Dispose() block — add before it:
if (sessionControl is not null)
    _logger?.LogDebug("DIAG STA finally: disposing sessionControl on '{DeviceId}'.", deviceId);

// existing capture.StopRecording() — add before it:
_logger?.LogDebug("DIAG STA finally: calling capture.StopRecording() on '{DeviceId}'.", deviceId);

// existing capture.Dispose() — add before it:
_logger?.LogDebug("DIAG STA finally: calling capture.Dispose() on '{DeviceId}'.", deviceId);

// add at the end of the finally block:
_logger?.LogInformation(
    "DIAG STA finally: cleanup complete on '{DeviceId}'.", deviceId);
```

---

### L-10 — Log all WASAPI session state changes, not just Expired

**Location:** `WasapiSessionEventClient.OnStateChanged`

The current implementation only acts on `Expired`. The `Inactive` and
`Active` states are silently ignored. Log all three so the full session
lifecycle is visible in the log.

Replace the current `OnStateChanged` body with:

```csharp
public void OnStateChanged(AudioSessionState state)
{
    _logger?.LogInformation(
        "DIAG OnStateChanged on '{DeviceId}': state = {State}",
        _deviceId, state);

    if (state == AudioSessionState.AudioSessionStateExpired)
    {
        var ex = new AudioCaptureException(
            _deviceId,
            "WASAPI audio session expired (OnStateChanged: Expired).");

        _channel.Writer.TryComplete(ex);
        try { _staCts.Cancel(); } catch (ObjectDisposedException) { }
    }
}
```

---

### L-11 — Log volume and mute changes

**Location:** `WasapiSessionEventClient.OnVolumeChanged`

A session mute or volume-to-zero event does not terminate the capture session
but produces silent audio that trips the watchdog. Log it so it is visible.

```csharp
public void OnVolumeChanged(float volume, bool isMuted)
{
    _logger?.LogInformation(
        "DIAG OnVolumeChanged on '{DeviceId}': volume={Volume:F2}, isMuted={IsMuted}",
        _deviceId, volume, isMuted);
}
```

---

## File: `src/OpenWSFZ.Audio/CaptureManager.cs`

### L-12 — Log before invoking CaptureFailed

**Location:** in `StartAsync`, immediately before each `CaptureFailed?.Invoke(...)` call.

There are two such calls — Case 2 (unexpected end) and Case 3 (exception).
Add a log entry before each so it is clear the event is being raised:

**Case 2:**
```csharp
_logger?.LogWarning(
    "Invoking CaptureFailed on '{DeviceId}' (Case 2 — unexpected end). " +
    "Chunks received before stop: {ChunksReceived}.",
    deviceId, chunksReceived);
CaptureFailed?.Invoke(unexpectedEndEx);
```

**Case 3:**
```csharp
_logger?.LogError(
    "Invoking CaptureFailed on '{DeviceId}' (Case 3 — exception). " +
    "Chunks received before stop: {ChunksReceived}.",
    deviceId, chunksReceived);
CaptureFailed?.Invoke(ex);
```

---

## File: `src/OpenWSFZ.Daemon/Program.cs`

### L-13 — Log restart attempt number in the CaptureFailed handler

**Location:** in the `captureManager.CaptureFailed` handler.

Add a restart counter so the log shows how many restart attempts have
been made. Declare `var captureRestartCount = 0;` in the top-level scope
(alongside `framerCts` and `framerTask`), then increment inside the
fire-and-forget task before the restart log.

```csharp
// Declaration (top-level scope, near framerCts):
var captureRestartCount = 0;

// Inside the Task.Run body in CaptureFailed, before StartPipeline:
captureRestartCount++;
startupLogger.LogInformation(
    "Auto-restarting audio capture on device '{Device}' after failure " +
    "(attempt #{RestartCount}).", device, captureRestartCount);
```

---

### L-14 — Log IsCapturing guard result in the restart handler

**Location:** inside the `Task.Run` body, at the `if (captureManager.IsCapturing) return;` guard.

```csharp
var isCapturing = captureManager.IsCapturing;
_logger?.LogDebug(
    "Restart guard check on '{Device}': IsCapturing={IsCapturing}.",
    device, isCapturing);
if (isCapturing) return;
```

---

## Commit Guidance

Single commit. All changes are logging only.

```
diag(audio): extensive pipeline logging for capture stop diagnosis

Add structured log entries at every significant function invocation and
state transition in the WASAPI capture pipeline:

- L-1:  device FriendlyName + negotiated WaveFormat on device open
- L-2:  resampling pipeline construction (stereoToMono, inputRate)
- L-3:  periodic DataAvailable heartbeat every 100 buffers
- L-4:  BufferedWaveProvider near-full warning (>80% of 5 s buffer)
- L-5:  resampler producing zero output from non-empty input
- L-6:  innerChannel write drops (TryWrite returning false)
- L-7:  capture.StartRecording() entry and exit
- L-8:  STA WaitOne unblock reason (ct vs staCts cancellation state)
- L-9:  STA finally block entry, cleanup steps, and exit
- L-10: all WASAPI session state changes (Active/Inactive/Expired)
- L-11: WASAPI volume and mute changes
- L-12: CaptureFailed invocation with chunk count (Cases 2 and 3)
- L-13: restart attempt counter in CaptureFailed handler
- L-14: IsCapturing guard result at restart gate

All entries tagged DIAG for removal after root cause is confirmed.
```

Files: `src/OpenWSFZ.Audio/WasapiAudioSource.cs`,
       `src/OpenWSFZ.Audio/CaptureManager.cs`,
       `src/OpenWSFZ.Daemon/Program.cs`

---

## What to read in the log after the next run

Run the daemon, wait for capture to stop, then read the full log from
startup. Work through this table from top to bottom:

| Entry present? | What it means |
|---|---|
| `WASAPI device opened` | Device found and format negotiated — note the WaveFormat |
| `capture.StartRecording() returned` | NAudio accepted the start call |
| `DIAG DataAvailable: first buffer` | WASAPI is delivering data — note timestamp |
| `DIAG DataAvailable: 100 buffers` | Data flowing at T+~2 s |
| NO `100 buffers` entry | Data stopped before 100 callbacks — very early failure |
| `DIAG BufferedWaveProvider near full` | Resampler is not draining — CPU or thread contention |
| `DIAG Resampler produced 0 output` | Resampler state problem — format mismatch |
| `DIAG innerChannel full — chunk dropped` | Consumer (CaptureManager) stalled |
| `DIAG OnStateChanged: Inactive` | WASAPI session paused — driver power-management candidate |
| `DIAG OnStateChanged: Expired` | WASAPI session destroyed |
| `DIAG OnSessionDisconnected: reason = …` | Windows terminated the session — reason IS the root cause |
| `DIAG OnVolumeChanged: isMuted=True` | Session muted — explains silent audio, not a stop |
| `DIAG RecordingStopped — WASAPI error` | NAudio received an exception — read ExType and ExMessage |
| `DIAG RecordingStopped — null exception` | NAudio's doStop was set — see STA WaitOne entry |
| `DIAG STA WaitOne unblocked: ct=False, staCts=True` | Something other than operator-stop cancelled staCts |
| `DIAG STA WaitOne unblocked: ct=True, staCts=True` | Normal operator StopAsync — capture was stopped externally |
| `Invoking CaptureFailed … Case 2` | Unexpected graceful stop — restart will fire in 5 s |
| `Invoking CaptureFailed … Case 3` | Exception-driven failure — restart will fire in 5 s |
| `Auto-restarting … attempt #N` | Restart loop is running — if N increments indefinitely, the failure is persistent |
