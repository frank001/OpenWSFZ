# Developer Briefing — p5-ft8-decoder (Round 10)

**Date:** 2026-05-23
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`

---

## Verdict: Audio capture is not stopping. It has never been stopping.

The latest log is definitive. Every single heartbeat entry shows:

| Time     | captureActive | audioActive | dataFlowing |
|----------|---------------|-------------|-------------|
| 19:06:53 | **True**      | True        | **True**    |
| 19:06:58 | **True**      | False       | **True**    |
| 19:07:03 | **True**      | False       | **True**    |
| 19:07:08 | **True**      | False       | **True**    |
| 19:07:13 | **True**      | False       | **True**    |
| 19:07:18 | **True**      | False       | **True**    |
| 19:07:23 | **True**      | False       | **True**    |
| 19:07:28 | **True**      | False       | **True**    |

- `captureActive=True` on every tick — `CaptureManager.IsCapturing` is true for the entire 45-second window. WASAPI never stopped.
- `dataFlowing=True` on every tick — `DataFlowMonitor.ConsumeAndReset()` returned true on every heartbeat. WASAPI delivered audio buffers in every 5-second window without exception.

**The capture pipeline is healthy and has been healthy.** All the fixes applied across B10–B20 and S6 are working. There is no capture stop bug.

---

## What is actually happening

`audioActive` transitions from `True` (window 1) to `False` (windows 2–8). This is the `AudioActivityMonitor`, which flags any sample with `|value| > 1e-6`. It went true briefly (a startup transient or ambient sound in the first five seconds), then false (the audio signal dropped below the threshold).

The operator was observing the "Audio" indicator dot in the browser UI going dark and interpreting that as "audio capture stopped." It is not. The dot reflects signal amplitude, not capture state:

| Indicator | Source | Meaning when False |
|---|---|---|
| `audioActive` (the dot) | `AudioActivityMonitor` — amplitude > 1e-6 | Input is quiet — no signal above noise floor |
| `captureActive` | `CaptureManager.IsCapturing` | Capture session is not running |

The input device is the **Jabra EVOLVE LINK**, a professional USB headset microphone. It is recording ambient room sound. When the room is quiet — which it will be most of the time — `audioActive` is `False`. This is correct and expected behaviour.

---

## The actual problem for FT8 decoding

A headset microphone is the wrong audio source for FT8. An FT8 station receives signals
from a radio receiver (SDR or conventional). The audio path is:

```
Radio receiver / SDR software
        ↓
Virtual audio cable (e.g. VB-Audio, VAC) or direct line-in
        ↓
OpenWSFZ audio device selection
```

As long as the Jabra EVOLVE LINK is the configured device, OpenWSFZ is listening to
ambient room noise. It will never decode FT8 signals regardless of how reliably the
capture pipeline runs, because there are no FT8 signals in the room.

The operator should:

1. Open the settings page (`/settings.html`)
2. Change the audio device to the SDR audio output or virtual cable that carries
   the radio receiver's demodulated audio
3. Confirm `audioActive=True` in the heartbeat after switching — this will indicate
   that the radio audio signal is reaching OpenWSFZ above the noise floor

---

## Status of all outstanding capture bugs

With the evidence from this log, the following can be declared resolved:

| ID | Description | Status |
|---|---|---|
| B10–B14 | WASAPI threading + event-client fixes | ✅ Resolved |
| B15–B17 | GC-safe sessionControl, B11 logging, Expired state | ✅ Resolved |
| S6 | AudioWatchdog (hung-while-capturing) | ✅ Resolved |
| B18 | Watchdog uses data-flow gate | ✅ Resolved |
| B19 | CaptureManager raises CaptureFailed on Case 2 | ✅ Resolved |
| B20 | CaptureFailed handler restarts pipeline | ✅ Resolved |
| **Capture stops after a few seconds** | **Root cause confirmed: not a capture stop. audioActive indicator goes False = quiet input. captureActive and dataFlowing remain True throughout.** | ✅ Resolved |

---

## Remaining open items

| ID | Description |
|---|---|
| B6 | WAV fixture — obtain 15-second 12 kHz mono WAV, commit, un-skip the FR-001 integration test |
| FR-017 | `AppConfig.DecodingEnabled` — start/stop toggle |
| Task 13.4 | Manual smoke test with the **correct** audio device (radio / SDR output) |
| Task 13.5 | Open draft PR to `main` |

The branch is ready for task 13.4 once the operator switches to the radio audio source.
DIAG log entries should be removed in a cleanup commit before the PR is opened.
