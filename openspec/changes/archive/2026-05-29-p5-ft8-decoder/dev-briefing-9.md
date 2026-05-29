# Developer Briefing — p5-ft8-decoder (Round 9)

**Date:** 2026-05-23
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Scope:** Log analysis + two targeted prescriptions

---

## Log Analysis

The following is the authoritative interpretation of the log provided.

```
18:54:49  WASAPI device opened: Jabra EVOLVE LINK — 48000 Hz, 32-bit, 1 ch
18:54:49  Resampling pipeline ready: stereoToMono=False, 48000 → 12000 Hz
18:54:49  Calling capture.StartRecording()
18:54:49  capture.StartRecording() returned
18:54:49  DIAG DataAvailable: first buffer — BytesRecorded=1920, WaveFormat=32 bit IEEFloat: 48000Hz 1 channels
          [6-second gap]
18:54:55  WebSocket connection accepted
          [42-second gap]
18:55:37  WebSocket connection closed
18:55:37  WebSocket connection accepted  ← page refresh
```

### What the log confirms

| Observation | Conclusion |
|---|---|
| Device opened, format logged | WASAPI found the device and negotiated 48 kHz / 32-bit / mono |
| StartRecording returned | NAudio accepted the start call without error |
| First DataAvailable fired, BytesRecorded=1920 | WASAPI delivered the first 10 ms buffer (1920 bytes = 48000 × 4 × 0.01 s — correct for event-sync mode) |
| **No RecordingStopped entry** | NAudio did not stop recording during the observed period |
| **No STA WaitOne unblock entry** | The STA thread is still blocked on WaitOne — the capture session is still running |
| **No CaptureManager exit entry** | `await foreach` has not exited — IsCapturing is still true |
| **Watchdog did not fire** | See below |

### Critical finding — the watchdog did not fire

`AudioWatchdog.TickAsync` fires after 3 consecutive silent 5-second windows while
`IsCapturing == true`. The WebSocket was open for 42 seconds (approximately 8 heartbeat
ticks). The watchdog logs at Warning level and would appear in an Information-level log.
It did not appear.

The watchdog resets its counter when `dataWasFlowing || !_isCapturing()`.  
Since `IsCapturing` is still true (no exit log), the counter can only reset via
`dataWasFlowing = true`.  
`dataWasFlowing` comes from `dataFlowMonitor.ConsumeAndReset()`.  
`DataFlowMonitor._flowing` is set by `CaptureManager.ChunkReceived → dataFlowMonitor.OnChunkReceived()`.  

**Conclusion: audio chunks ARE reaching CaptureManager on every heartbeat tick.
The capture pipeline is running. WASAPI is delivering data.**

---

## The diagnostic gap

The L-3 periodic heartbeat (every 100 DataAvailable callbacks) was prescribed in
dev-briefing-8 at `_logger?.LogDebug(...)`. The daemon runs at `LogLevel: Information`.
**Debug entries are filtered out entirely.** The developer implemented the log call at
the prescribed level, but the prescribed level was wrong.

The entire purpose of L-3 was to show ongoing data flow between the first buffer and
any eventual stop. That purpose is defeated when the entry is invisible at the
runtime log level.

---

## The AudioActive indicator is not a capture indicator

The UI status bar shows an "Audio" dot (element `id="audio-indicator"`).
`main.js` drives this from `event.payload.audioActive` on every `heartbeat` event.
`heartbeat.audioActive` comes from `AudioActivityMonitor.ConsumeAndReset()`.
`AudioActivityMonitor` only triggers when a sample has `|value| > 1e-6`.

This indicator does **not** reflect whether WASAPI is delivering buffers.
It reflects whether the audio signal is above the noise floor. On a quiet
radio frequency — or if the selected device is a headset microphone in a quiet room
with no radio signal connected — the indicator goes dark even when capture is running
perfectly.

There is currently no visible indicator in the UI or heartbeat payload for
`captureManager.IsCapturing`. `DaemonStatus.CaptureActive` is populated correctly
in `GET /api/v1/status` but is:
1. Not included in the WebSocket initial `status` event (WebSocketHub constructs
   `DaemonStatus` without the `CaptureActive` parameter — it defaults to `false`)
2. Not included in the `heartbeat` payload at all

A user observing the "Audio" indicator going dark may be seeing a quiet input signal
(expected behaviour), not a capture failure.

---

## Prescriptions

### P-1 — Change L-3 from LogDebug to LogInformation

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`

The L-3 periodic log (every 100 DataAvailable callbacks) must be at `LogInformation`
to be visible at the daemon's default log level. Replace the `LogDebug` call added
for L-3 with `LogInformation`:

```csharp
// BEFORE (L-3 as implemented from dev-briefing-8):
_logger?.LogDebug(
    "DIAG DataAvailable: {Count} buffers on '{DeviceId}' — ...",
    ...);

// AFTER:
_logger?.LogInformation(
    "DIAG DataAvailable: {Count} buffers on '{DeviceId}' — ...",
    ...);
```

At 48 kHz with a 10 ms buffer period, 100 callbacks = 1 second of audio.
The log will show an entry approximately every second while data is flowing,
providing a heartbeat that confirms the exact moment WASAPI stops delivering buffers.

### P-2 — Add CaptureActive to the WebSocket heartbeat payload

**File:** `src/OpenWSFZ.Web/AppJsonContext.cs` and `src/OpenWSFZ.Web/WebSocketHub.cs`

The heartbeat currently carries only `AudioActive` (amplitude). Add `CaptureActive`
(is WASAPI delivering buffers) so both indicators are visible in the live stream
and distinguish a silent-but-running capture from a genuinely stopped one.

**Step 1 — Extend HeartbeatPayload:**

```csharp
// BEFORE:
internal sealed record HeartbeatPayload(bool AudioActive);

// AFTER:
internal sealed record HeartbeatPayload(bool AudioActive, bool CaptureActive);
```

**Step 2 — Populate in WebSocketHub.HandleAsync:**

```csharp
// BEFORE:
var heartbeatMsg = new WsHeartbeatMessage(
    Type:    "heartbeat",
    Payload: new HeartbeatPayload(AudioActive: active));

// AFTER:
var heartbeatMsg = new WsHeartbeatMessage(
    Type:    "heartbeat",
    Payload: new HeartbeatPayload(
        AudioActive:   active,
        CaptureActive: captureManager?.IsCapturing ?? false));
```

**Step 3 — Populate CaptureActive in the WebSocket initial status event:**

```csharp
// BEFORE (WebSocketHub.HandleAsync, initial status construction):
var status = new DaemonStatus(
    State:        "Running",
    Version:      AssemblyVersion.Get(),
    AudioDevice:  configStore.Current.AudioDeviceName,
    AudioActive:  audioMonitor?.IsActive ?? false);

// AFTER:
var status = new DaemonStatus(
    State:         "Running",
    Version:       AssemblyVersion.Get(),
    AudioDevice:   configStore.Current.AudioDeviceName,
    CaptureActive: captureManager?.IsCapturing ?? false,
    AudioActive:   audioMonitor?.IsActive ?? false);
```

**Step 4 — Log CaptureActive in the heartbeat log:**

Add a single `LogInformation` entry to WebSocketHub so each heartbeat's state
is visible in the server log, not only in the browser WebSocket stream:

```csharp
logger.LogInformation(
    "Heartbeat: captureActive={CaptureActive}, audioActive={AudioActive}, dataFlowing={DataFlowing}",
    captureManager?.IsCapturing ?? false, active, dataFlowing);
```

Place this immediately after the `dataFlowing` line and before the watchdog tick.

---

## What to check after P-1 and P-2 are implemented

Run the daemon. The log should now show:

```
[info] DIAG DataAvailable: 100 buffers on '...' — BytesRecorded=1920, BufferedMs=...
[info] Heartbeat: captureActive=True, audioActive=True/False, dataFlowing=True
[info] DIAG DataAvailable: 200 buffers on '...' — ...
[info] Heartbeat: captureActive=True, audioActive=True/False, dataFlowing=True
```

repeating every second (L-3) and every 5 seconds (heartbeat log).

If capture is running but the audio signal is quiet (radio frequency empty,
headset mic in a silent room), the expected pattern is:

```
captureActive=True    ← WASAPI is running
audioActive=False     ← amplitude below threshold — this is NOT a failure
dataFlowing=True      ← buffers ARE being delivered
```

If capture genuinely stops, the pattern changes to:

```
captureActive=False
dataFlowing=False
```

followed by the existing RecordingStopped / STA finally / CaptureFailed log entries.

---

## Commit guidance

```
diag(audio): P-1 L-3 at Information; P-2 CaptureActive in heartbeat

P-1: change L-3 DataAvailable heartbeat from LogDebug to LogInformation
so it is visible at the daemon's default log level.

P-2: add CaptureActive to HeartbeatPayload, WebSocket status event,
and heartbeat server log so the distinction between a stopped capture
and a silent-but-running capture is visible in both the browser and
the server log.
```

Files:
- `src/OpenWSFZ.Audio/WasapiAudioSource.cs` (P-1)
- `src/OpenWSFZ.Web/AppJsonContext.cs` (P-2 HeartbeatPayload)
- `src/OpenWSFZ.Web/WebSocketHub.cs` (P-2 construction + heartbeat log)
