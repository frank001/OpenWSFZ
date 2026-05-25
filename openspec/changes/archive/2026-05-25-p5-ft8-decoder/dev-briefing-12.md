# Developer Briefing — p5-ft8-decoder (Round 12)

**Date:** 2026-05-23
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Scope:** Diagnostic — zero-content audio chunks

---

## Situation

`captureActive=True`, `dataFlowing=True`, but all PCM chunks reaching the
application contain only zero samples. The existing zero-check at the resampler
output (added by the developer) confirms zeros are present there, but does not
tell us where in the pipeline they originate.

There are exactly two possible origins:

| Origin | Meaning | Fix |
|---|---|---|
| Raw bytes from WASAPI (`e.Buffer`) are zero | The device itself is returning silence | OS / device configuration — see below |
| Raw bytes are non-zero but resampler output is zero | Something in the format-conversion pipeline is zeroing the data | Code fix in the pipeline |

These require completely different responses. One log entry resolves the ambiguity.

---

## Prescription — add raw-byte check before `buffer.AddSamples`

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`

Add immediately **before** the `buffer.AddSamples(e.Buffer, 0, e.BytesRecorded);` line
inside the `DataAvailable` try block. This runs on every callback but the boolean scan
short-circuits on the first non-zero byte, so it is inexpensive:

```csharp
// DIAG: check whether WASAPI is delivering non-zero bytes.
// If rawHasData=False the device itself is returning silence — OS/hardware cause.
// If rawHasData=True but resampler output is zero, the pipeline is the cause.
var rawHasData = false;
for (var i = 0; i < e.BytesRecorded && !rawHasData; i++)
    rawHasData = e.Buffer[i] != 0;

if (dataAvailableCount <= 5 || dataAvailableCount % 100 == 0)
{
    _logger?.LogInformation(
        "DIAG raw bytes on '{DeviceId}': BytesRecorded={Bytes}, rawHasData={HasData}",
        deviceId, e.BytesRecorded, rawHasData);
}
```

The `dataAvailableCount <= 5` guard logs the first five callbacks unconditionally
(startup confirmation), then falls back to the existing 100-buffer cadence.

---

## Interpreting the result

### Case A — `rawHasData=False` on every entry

The device is delivering zero-filled buffers. This is an OS or hardware problem,
not a code problem. Common causes for the Jabra EVOLVE LINK:

1. **Hardware mute active** — the headset has a physical mute button. If the mute
   LED is lit, the headset reports silence to WASAPI. Press the mute button to toggle.

2. **Windows microphone volume at zero** — open Windows Sound settings →
   Recording tab → Jabra EVOLVE LINK → Properties → Levels. Confirm the microphone
   level is above 0 and not muted.

3. **Windows microphone privacy setting** — Settings → Privacy & Security →
   Microphone → confirm "Allow apps to access your microphone" is On, and that
   desktop apps are permitted.

4. **Another application in exclusive mode** — if a communications app (Teams,
   Discord, Zoom) has the Jabra open in exclusive mode, WASAPI shared-mode access
   returns silence. Close all other audio applications and retry.

5. **Driver state** — if the above are all clear, unplug and reconnect the headset
   to force a driver re-initialisation.

### Case B — `rawHasData=True` but resampler output is zero

The raw PCM from WASAPI is valid but something in the NAudio pipeline is
discarding or zeroing it. Most probable causes:

1. **`BufferedWaveProvider.ToSampleProvider()` format issue** — the provider
   is created from `capture.WaveFormat` (32-bit IEEE float, 48 kHz, 1 ch). This
   format is fully supported by NAudio. Unlikely to be the cause, but log
   `buffer.BufferedBytes` after `AddSamples` to confirm the provider accepted
   the data.

2. **`WdlResamplingSampleProvider` state** — the resampler is constructed once and
   reused. If `Read()` is called before the internal state is initialised, it may
   output zeros for the first N frames. Log `read` (the return value of
   `resampler.Read()`) on the first few callbacks to confirm it returns a positive
   number.

3. **`DiscardOnBufferOverflow = true` combined with a stalled consumer** — if the
   `BufferedWaveProvider` is full and discarding data, the resampler drains an
   empty provider and returns zeros. The existing L-4 overflow warning will fire
   in this case.

---

## Commit guidance

```
diag(audio): add raw-byte zero-check before BufferedWaveProvider

Log whether the raw WASAPI bytes contain any non-zero data on the first
5 callbacks and every 100 thereafter.  Separates device-level silence
(OS/hardware cause) from pipeline-level silence (code cause).
```

File: `src/OpenWSFZ.Audio/WasapiAudioSource.cs`
