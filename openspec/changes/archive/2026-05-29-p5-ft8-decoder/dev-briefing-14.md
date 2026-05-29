# Developer Briefing — p5-ft8-decoder (Round 14)

**Date:** 2026-05-23
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Scope:** Zero-chunk root cause — session overlap + raw-byte confirmation

---

## Situation

After reverting `useEventSync: true` (dev-briefing-13), zero chunks persist. The operator's
log shows two device GUIDs emitting "DIAG Resampler output all zeros" concurrently:

- `{3dc54b78-...}` — the selected SDR / virtual cable device
- `{857495f9-...}` — the Jabra EVOLVE LINK

Both devices producing all-zero resampler output at the same timestamp confirms that a
**session overlap** is in progress: the old session is still alive and writing to the shared
output channel when the new session starts.

Two separate problems are in play and must be addressed together:

| Problem | Root cause | File |
|---|---|---|
| Session overlap | `StopAsync` 2-second timeout is insufficient for STA COM cleanup | `CaptureManager.cs` |
| Zeros in selected device | Unknown — `rawHasData` result not yet surfaced | `WasapiAudioSource.cs` |

---

## Fix 1 — Session overlap: increase `StopAsync` timeout

**File:** `src/OpenWSFZ.Audio/CaptureManager.cs`

`StopAsync` currently waits at most 2 seconds for the capture task to finish before
proceeding to start the new session. The STA thread cleanup path is:

```
staCts.Cancel()
  → WaitHandle.WaitOne() unblocks
    → sessionControl.Dispose()       (COM call — can block up to ~1 s)
    → capture.StopRecording()        (NAudio waits for WASAPI to flush final buffer)
    → capture.Dispose()
  → RecordingStopped fires
    → innerChannel.Writer.TryComplete()
  → ReadAllAsync() on innerChannel exits
  → captureTask completes
```

On virtual audio drivers this chain can take 3–5 seconds. When it exceeds 2 seconds,
`StopAsync` returns while the old `_captureTask` is still alive. Both the old and new
tasks then write to the shared `_channel.Writer` — producing interleaved chunks from
two devices.

### Change

```csharp
// BEFORE (line ~180):
try
{
    await task.WaitAsync(TimeSpan.FromSeconds(2));
}
catch (TimeoutException) { }
catch (OperationCanceledException) { }
catch (Exception) { }

// AFTER:
try
{
    await task.WaitAsync(TimeSpan.FromSeconds(10));
}
catch (TimeoutException)
{
    _logger?.LogWarning(
        "StopAsync: capture task did not complete within 10 s — " +
        "old session may still be writing to the channel. " +
        "Device overlap in the output stream is possible.");
}
catch (OperationCanceledException) { }
catch (Exception) { }
```

A 10-second budget is sufficient for any realistic COM cleanup sequence. If the warning
fires, it tells us the driver cleanup is genuinely pathological and warrants further
investigation.

---

## Fix 2 — Surface the `rawHasData` readings

The `rawHasData` byte-scan check from dev-briefing-12 is already in the code. It fires on
the first 5 `DataAvailable` callbacks and every 100th thereafter — approximately one entry
every 5 seconds at 48 kHz / 10 ms WASAPI buffers. Look for lines matching this pattern in
the log **while audio is actively playing**:

```
DIAG raw bytes on '{DeviceId}': BytesRecorded={Bytes}, rawHasData={HasData}
```

Specifically: what is `rawHasData` for `{3dc54b78-...}` during active transmission? This
single value is the decisive diagnostic branch point.

---

## Fix 3 — First-sample float interpretation (dev-briefing-13 Step 2 — not yet implemented)

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`

This step was conditional in dev-briefing-13 ("if Step 1 alone resolves the issue"). Zeros
have persisted, so it must now be implemented. Add immediately after the rawHasData log
block (after the `if (dataAvailableCount <= 5 || dataAvailableCount % 100 == 0)` block)
and before `buffer.AddSamples`:

```csharp
// DIAG: interpret first sample as IEEE 754 float to confirm signal is present.
// A non-zero firstSample with rawHasData=True confirms valid audio in the raw bytes.
if (e.BytesRecorded >= 4 && (dataAvailableCount <= 5 || dataAvailableCount % 100 == 0))
{
    var firstSample = BitConverter.ToSingle(e.Buffer, 0);
    _logger?.LogInformation(
        "DIAG first sample on '{DeviceId}': {FirstSample:G6} (rawHasData={HasData})",
        deviceId, firstSample, rawHasData);
}
```

---

## Fix 4 — Direct pipeline bypass (implement only if rawHasData=True and firstSample ≠ 0)

If the raw WASAPI bytes are confirmed to contain valid audio (rawHasData=True, firstSample
non-zero), something in the NAudio chain is zeroing the data. Add a direct
`MemoryMarshal.Cast` to measure the maximum absolute value of the raw bytes interpreted
as floats, bypassing `BufferedWaveProvider`, `WaveToSampleProvider`, and
`WdlResamplingSampleProvider` entirely.

Add after the first-sample log and before `buffer.AddSamples`:

```csharp
// DIAG: direct float cast bypassing NAudio pipeline.
// maxAbs > 0 confirms valid signal in raw bytes; zeros introduced downstream.
// Only run when rawHasData is True to avoid noise from zero-filled buffers.
if (rawHasData && (dataAvailableCount <= 5 || dataAvailableCount % 100 == 0))
{
    var span   = e.Buffer.AsSpan(0, e.BytesRecorded);
    var floats = System.Runtime.InteropServices.MemoryMarshal.Cast<byte, float>(span);
    var maxAbs = 0f;
    foreach (var s in floats)
        if (MathF.Abs(s) > maxAbs) maxAbs = MathF.Abs(s);
    _logger?.LogInformation(
        "DIAG direct cast on '{DeviceId}': {FloatCount} floats, maxAbs={MaxAbs:G6}",
        deviceId, floats.Length, maxAbs);
}
```

---

## Interpretation

Once Fixes 1–3 are running and a log is captured during active audio:

### If `rawHasData = False`

WASAPI is delivering zero-filled buffers. The device is not routing audio to the
capture endpoint. This is a device configuration problem, not a code problem.

Most probable cause: the audio is being played to the virtual cable's **playback/input
side** but the application is capturing from a different endpoint — either a different
device entirely, or the monitoring/loopback side of the same virtual cable.

Checklist:
1. Open the Windows Sound settings → Recording tab. Confirm `{3dc54b78-...}` is listed
   as a **Recording** (capture) device.
2. Confirm the SDR software (or audio source) is configured to output audio to the device
   whose Recording counterpart is `{3dc54b78-...}`. For VB-Audio Virtual Cable: the SDR
   outputs to "CABLE Input (VB-Audio)", OpenWSFZ captures from "CABLE Output (VB-Audio)".
3. Set that Recording device as the default and confirm it shows activity in the level
   meter in Windows Sound settings while audio is playing.

### If `rawHasData = True`, `firstSample ≈ 0.0f`

Non-zero bytes but the first 4 bytes form an IEEE 754 representation of zero — unlikely
unless the audio format is not 32-bit IEEE float. Check the L-1 log entry
("WASAPI device opened") for BitsPerSample and confirm it is 32. If BitsPerSample is
16, `BitConverter.ToSingle` on the first 4 bytes (two PCM-16 samples) would not
produce the correct result. Proceed to Fix 4 regardless.

### If `rawHasData = True`, `firstSample ≠ 0.0f`

Valid audio signal is reaching the NAudio pipeline. The zeros are introduced somewhere
between `buffer.AddSamples` and `resampler.Read`. Implement Fix 4.

If Fix 4 confirms `maxAbs > 0` (valid data in raw bytes), the fault is in the NAudio
chain. The most probable suspects in order:

1. **`BufferedWaveProvider.DiscardOnBufferOverflow = true` + stalled consumer** — if the
   5-second buffer fills and discards data faster than the resampler drains it, the
   resampler reads an empty provider and outputs zeros. The existing L-4 overflow warning
   would fire in this case. Check whether L-4 appears before the zero-chunk warnings.

2. **`WdlResamplingSampleProvider` initialisation** — the resampler is constructed once
   and may return zeros for the first few frames while its internal state initialises.
   Add `_logger?.LogInformation("Resampler Read: read={Read}", read);` for the first
   5 reads (gate on `dataAvailableCount <= 5`) to confirm whether zero output is limited
   to startup or persists.

3. **Format encoding mismatch** — if `capture.WaveFormat.Encoding` is not
   `WaveFormatEncoding.IeeeFloat`, `BufferedWaveProvider.ToSampleProvider()` will use a
   PCM converter rather than `WaveToSampleProvider`. Log `capture.WaveFormat.Encoding`
   in the L-1 log entry if this is suspected.

---

## Commit guidance

Fix 1 (session overlap — CaptureManager.cs):
```
fix(audio): increase StopAsync timeout to 10 s, log overlap warning

StopAsync waited 2 s for capture task completion; STA COM cleanup
(sessionControl → StopRecording → Dispose) can exceed this on virtual
audio drivers. Increasing to 10 s eliminates the session overlap seen
in the log where two device GUIDs produced interleaved zero chunks.
```

Fix 3 (first-sample log — WasapiAudioSource.cs):
```
diag(audio): add first-sample float interpretation to DataAvailable

Log the first IEEE 754 float from the raw WASAPI buffer alongside the
rawHasData boolean. Confirms whether the raw bytes carry a valid audio
signal before entering the NAudio pipeline. Implements dev-briefing-13
Step 2 which was conditional on Step 1 not resolving the zeros.
```

Fix 4 (pipeline bypass — WasapiAudioSource.cs, conditional):
```
diag(audio): add direct MemoryMarshal float cast to DataAvailable

Bypasses the NAudio pipeline entirely and measures the peak absolute
value of the raw WASAPI bytes as IEEE 754 floats. Determines whether
zero resampler output originates at WASAPI (device silent) or in the
NAudio chain (BufferedWaveProvider / WdlResamplingSampleProvider).
```
