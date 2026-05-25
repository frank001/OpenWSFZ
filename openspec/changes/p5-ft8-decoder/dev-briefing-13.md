# Developer Briefing — p5-ft8-decoder (Round 13)

**Date:** 2026-05-23
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Scope:** Zero audio chunks — root cause and fix

---

## Diagnosis

Situation C is confirmed: the selected device is correct and functioning, audio is
actively present at the device, WASAPI delivers buffers with `BytesRecorded=1920`,
yet every float chunk reaching `CaptureManager` contains only zero samples.

The most probable root cause is `useEventSync: true`.

### Why useEventSync causes zeros on software audio devices

`WasapiCapture` operates in one of two modes:

| Mode | Mechanism | Device requirement |
|---|---|---|
| `useEventSync: false` (timer) | Internal thread sleeps 50ms, wakes, reads whatever data is in the WASAPI buffer | Any device — no hardware clock required |
| `useEventSync: true` (event) | Internal thread waits on a Windows kernel event that WASAPI signals when a buffer period of data is ready | Requires a hardware-backed clock source to trigger the event |

**Virtual audio cables** (VB-Audio Virtual Cable, VoiceMeeter, ASIO4ALL wrappers)
and **SDR audio outputs** are software-defined devices. They do not have a hardware
clock. In event-sync mode they must synthesise the kernel event signal in software.
Depending on driver implementation, this can produce one of two failure modes:

1. **The event fires but the buffer has not been filled** — WASAPI delivers a
   buffer with `BytesRecorded > 0` but all bytes are `0x00`. This is exactly the
   symptom observed: non-zero `BytesRecorded`, `rawHasData=False`.

2. **The event fires late** — data is present but arrives out-of-phase with the
   capture thread, causing underruns and eventual capture stops (the original
   presenting symptom before the logging was added).

`useEventSync: true` was introduced in commit `0d8b367` as a speculative fix for
what was subsequently confirmed to be a misdiagnosed issue — the stopping was the
`audioActive` amplitude indicator going false, not a genuine WASAPI capture stop.
The event-sync change was never validated against the actual radio audio device.

---

## Fix

### Step 1 — Revert to timer-based mode

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`

```csharp
// BEFORE (commit 0d8b367):
capture = new WasapiCapture(device, useEventSync: true);

// AFTER:
capture = new WasapiCapture(device, useEventSync: false);
```

This is a one-line change. Timer-based mode reads whatever data is in the WASAPI
buffer on a fixed schedule regardless of device clock source. It is the correct
mode for virtual and software-defined audio devices.

If the original Jabra stopping issue recurs after this revert, that is a separate
finding to investigate — it was not definitively caused by timer mode in the first
place, given the stopping was never confirmed in logs.

### Step 2 — Verify with a raw value log during an active transmission

If Step 1 alone resolves the zero-chunk issue, no further changes are needed.

If zeros persist after the revert, add the following inside `DataAvailable` to
confirm whether the raw WASAPI bytes carry actual audio values. This checks the
first four bytes as a single IEEE 754 float — the simplest possible validation of
the raw signal:

```csharp
// DIAG: interpret first sample as float to confirm signal is present.
// Place this after the existing rawHasData check and before buffer.AddSamples.
if (e.BytesRecorded >= 4 && (dataAvailableCount <= 5 || dataAvailableCount % 100 == 0))
{
    var firstSample = BitConverter.ToSingle(e.Buffer, 0);
    _logger?.LogInformation(
        "DIAG first sample on '{DeviceId}': {FirstSample:G6} (rawHasData={HasData})",
        deviceId, firstSample, rawHasData);
}
```

A non-zero `firstSample` with `rawHasData=True` when audio is actively present
confirms the raw signal is reaching the pipeline and the zeros are introduced in
the NAudio chain (see Part 2 of dev-briefing-12 for the pipeline suspects).

A zero `firstSample` with `rawHasData=False` even during active audio confirms the
device is not delivering signal in event-sync mode — resolved by Step 1.

---

## Commit guidance

```
fix(audio): revert to timer-based WASAPI capture mode

useEventSync: true was introduced speculatively in 0d8b367 to address a
stopping issue that was subsequently confirmed as a misdiagnosed audioActive
indicator problem, not a genuine capture stop.

Event-sync mode requires hardware-backed clock support. Virtual audio cables
and SDR audio outputs are software-defined devices that do not provide this.
On these devices, useEventSync: true delivers zero-filled buffers even when
audio is present. Timer-based mode reads the WASAPI buffer on a fixed schedule
and is correct for all device types.
```

File: `src/OpenWSFZ.Audio/WasapiAudioSource.cs`
