# Developer Briefing — p5-ft8-decoder (Round 11)

**Date:** 2026-05-23
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Scope:** Behaviour change — audioActive driven by data flow, not amplitude

---

## Directive

`audioActive` must be `true` whenever WASAPI is delivering audio buffers to the
pipeline. A quiet input — wrong frequency, wrong mode, silent band — is not a failure
mode for the application. The amplitude threshold check must not affect the indicator.

---

## Root Cause

In `WebSocketHub.HandleAsync`, the heartbeat derives `active` from
`AudioActivityMonitor.ConsumeAndReset()`. That monitor's threshold is `|sample| > 1e-6`.
Any period of quiet audio (radio band empty, wrong device mode) produces
`audioActive=False` in the heartbeat even when `captureActive=True` and
`dataFlowing=True` — i.e. when WASAPI is operating perfectly.

The same heartbeat tick already calls `DataFlowMonitor.ConsumeAndReset()` for the
watchdog. `DataFlowMonitor` is set whenever any chunk reaches `CaptureManager`,
regardless of content. That is the correct signal for `audioActive`.

---

## Changes Required

### File: `src/OpenWSFZ.Web/WebSocketHub.cs`

**Change 1 — Heartbeat: derive `active` from `dataFlowing`, not amplitude**

```csharp
// BEFORE:
var active = audioMonitor?.ConsumeAndReset() ?? false;

var dataFlowing = dataFlowMonitor?.ConsumeAndReset() ?? false;

if (watchdog is not null)
    _ = watchdog.TickAsync(dataFlowing);

var heartbeatMsg = new WsHeartbeatMessage(
    Type:    "heartbeat",
    Payload: new HeartbeatPayload(
        AudioActive:   active,
        CaptureActive: captureManager?.IsCapturing ?? false));

// AFTER:
audioMonitor?.ConsumeAndReset(); // reset amplitude window — result no longer used for active

var dataFlowing = dataFlowMonitor?.ConsumeAndReset() ?? false;
var active      = dataFlowing; // audioActive = WASAPI is delivering data

if (watchdog is not null)
    _ = watchdog.TickAsync(dataFlowing);

var heartbeatMsg = new WsHeartbeatMessage(
    Type:    "heartbeat",
    Payload: new HeartbeatPayload(
        AudioActive:   active,
        CaptureActive: captureManager?.IsCapturing ?? false));
```

Note: `audioMonitor?.ConsumeAndReset()` is still called — without consuming the
result — to keep the amplitude window resetting on each tick. This prevents the
internal `_active` flag accumulating stale state if `AudioActivityMonitor` is
repurposed in a future feature.

**Change 2 — Initial status event: derive `AudioActive` from `IsCapturing`**

On WebSocket connect, the `status` event is sent with `AudioActive` from
`audioMonitor?.IsActive`. Replace with `IsCapturing` for consistency with the
heartbeat behaviour:

```csharp
// BEFORE:
var status = new DaemonStatus(
    State:         "Running",
    Version:       AssemblyVersion.Get(),
    AudioDevice:   configStore.Current.AudioDeviceName,
    CaptureActive: captureManager?.IsCapturing ?? false,
    AudioActive:   audioMonitor?.IsActive ?? false);

// AFTER:
var status = new DaemonStatus(
    State:         "Running",
    Version:       AssemblyVersion.Get(),
    AudioDevice:   configStore.Current.AudioDeviceName,
    CaptureActive: captureManager?.IsCapturing ?? false,
    AudioActive:   captureManager?.IsCapturing ?? false);
```

---

## Behaviour After This Change

| Scenario | captureActive | audioActive | dataFlowing |
|---|---|---|---|
| Capture running, radio transmitting | True | **True** | True |
| Capture running, radio silent (empty band) | True | **True** | True |
| Capture running, wrong mode/frequency | True | **True** | True |
| Capture stopped or not yet started | False | **False** | False |
| Capture started, first buffer not yet received | True | **False** | False |

`audioActive` is now equivalent to `dataFlowing` — it is `true` for the entire
5-second window in which WASAPI delivered at least one buffer. It goes `false` only
when the pipeline is genuinely stopped or stalled.

---

## Commit Guidance

```
fix(web): audioActive driven by data flow, not amplitude threshold

AudioActivityMonitor's 1e-6 amplitude gate caused audioActive to go False
whenever the radio band was quiet, making the indicator useless as a
capture-health signal. A quiet radio frequency is not an application failure.

Drive audioActive from DataFlowMonitor instead: True whenever WASAPI is
delivering buffers to CaptureManager, regardless of signal amplitude.
Consistent in both the heartbeat and the initial WebSocket status event.
```

Files: `src/OpenWSFZ.Web/WebSocketHub.cs`
