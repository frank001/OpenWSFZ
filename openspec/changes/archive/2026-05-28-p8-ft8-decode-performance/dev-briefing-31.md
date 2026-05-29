# Developer Briefing — p8-ft8-decode-performance (Round 31)

**Date:** 2026-05-28  
**Issued by:** QA  
**Branch:** `feat/p8-ft8-decode-performance`  
**Scope:** Post-implementation review + audio capture error diagnosis

---

## Verdict

**The p8 implementation is correct.** The audio capture error is not caused by the p8
changes and requires a separate, straightforward resolution.

---

## Implementation Review — commit `041cdad`

Each task from dev-briefing-30 has been reviewed against the committed diff.

| Task | Verdict | Notes |
|------|---------|-------|
| 2.1 Coefficient caching in `SymbolExtractor.Extract` | ✅ Correct | Array pre-computed before symbol loop |
| 2.2 `GoertzelDetector` overloads | ✅ Correct | `Coeff` + `ComputeEnergyWithCoeff` present |
| 3.1 `MaxCandidatesPerSweep = 2` constant | ✅ Correct | Placed with sync threshold constants |
| 3.2 Candidate cap applied after `FindCandidates` | ✅ Correct | `take = Math.Min(...)`, `for (int ci = 0; ci < take; ci++)` |
| 4.1 `_spectrogram` field removed | ✅ Correct | Field and its comment both removed |
| 4.2 `Parallel.For` with per-iteration spectrogram | ✅ Correct | `var spectrogram = new float[SymbolCount, SpecBins]` inside lambda |
| 4.3 `ConcurrentBag` + post-loop de-duplication | ✅ Correct | `seen.Add` only in post-loop merge; no concurrent access to `HashSet` |
| 4.4 Diagnostic counters via `Interlocked` | ✅ Correct | `Increment` and `Add` used throughout |
| 4.5 Cancellation semantics (advisory) | ✅ Acceptable | See advisory A1 below |
| 5.1 Stopwatch elapsed in `LogInformation` | ✅ Correct | `elapsed={Elapsed} ms` in format string |
| 6.1–6.2 FR-026 performance regression test | ✅ Correct | 8 signals, Box-Muller noise, `[Trait("Category", "Performance")]` |

No correctness defects were found in the p8 implementation.

---

## Audio Capture Error — Root Cause

### Error

```
[18:37:32 ERR] Audio capture failed on 'Microphone (2- USB Audio CODEC )':
Cannot capture from device '{0.0.1.00000000}.{8352a3c3-66ff-4078-b537-64a755c483a2}':
Element not found. (0x80070490)
```

### Cause

`0x80070490` = `HRESULT_FROM_WIN32(ERROR_NOT_FOUND)`.

This HRESULT is returned by `MMDeviceEnumerator.GetDevice(deviceId)` in
`WasapiAudioSource.CaptureAsync` (line 70–74) when the supplied device ID does not
exist in the Windows audio device registry.  The error propagates as an
`AudioCaptureException`, causes `CaptureManager` to fire the `CaptureFailed` event,
and is logged in `Program.cs` by the `CaptureFailed` handler:

```csharp
captureManager.CaptureFailed += ex =>
{
    startupLogger.LogError(ex,
        "Audio capture failed on '{Device}': {Message}",
        configStore.Current.AudioDeviceFriendlyName ?? configStore.Current.AudioDeviceId,
        ex.Message);
    ...
};
```

The friendly name `Microphone (2- USB Audio CODEC )` comes from
`configStore.Current.AudioDeviceFriendlyName`; the device ID in the exception message
is the WASAPI GUID stored in `configStore.Current.AudioDeviceId`.

### Why this is unrelated to p8

The p8 changes modify `GoertzelDetector`, `SymbolExtractor`, and `Ft8Decoder`.  None
of these touch `WasapiAudioSource`, `CaptureManager`, `Program.cs`, or the config
store.

Separately: the decode pump in `Program.cs` calls `DecodeAsync` **without** a
`CancellationToken`:

```csharp
var results = await ft8Decoder.DecodeAsync(pcmWindow);  // ct = default
```

The new `Parallel.For` runs with `CancellationToken.None`.  `ct.ThrowIfCancellationRequested()`
inside the parallel body is a no-op; the loop cannot be interrupted mid-decode and
cannot propagate any cancellation signal that would affect audio capture.  Any
exception from the parallel body is caught by the decode pump's `catch (Exception ex)`
handler (line 241) and logged — it does not propagate to `CaptureManager`.

### What actually happened

The most likely cause is that the USB audio device changed its Windows device ID.
This happens when:

- The device is unplugged and replugged into a different USB port
- Windows Device Manager reinstalls the driver
- Windows assigns a new GUID after an OS update or USB hub reset

The `2-` ordinal prefix in `Microphone (2- USB Audio CODEC )` indicates this device
was previously enumerated as the second instance of its type.  USB device instance
IDs with ordinal prefixes are particularly volatile.

Because the stored ID is now stale, the auto-restart loop (5-second delay, then
`RestartPipelineAsync`) will retry indefinitely with the same bad ID and fail every
time.

---

## Resolution

### Step 1 — Check the device is connected

Confirm the USB audio codec is physically connected and visible in Windows Sound
settings (Control Panel → Sound → Recording tab).  If it is not listed there, no
software fix will help; reconnect the device first.

### Step 2 — Re-select the device via the UI

Navigate to the audio device selector in the web UI and select
`Microphone (2- USB Audio CODEC )` (or its current name) from the dropdown.  This
triggers `configStore.OnSaved`, which calls `RestartPipelineAsync` with the fresh,
currently-valid device ID that was just returned by WASAPI enumeration.

The stored ID in config will be updated to the new GUID.  Capture will resume.

### Step 3 — Verify capture resumes

The log should show:

```
INF  WASAPI device opened: '...' ('Microphone (2- USB Audio CODEC )') — WaveFormat=...
INF  Resampling pipeline ready on '...': channelMode=..., inputRate=... Hz → 12000 Hz
```

If neither line appears, the device is still unavailable.  Reconnect the hardware
and repeat from Step 1.

---

## Advisory A1 — `AggregateException` on mid-decode cancellation (low priority)

`DecodeAsync` is currently called without a token in the decode pump.  If a future
change passes `stoppingToken` to `DecodeAsync`, `Parallel.For` may throw
`AggregateException` when the token is cancelled mid-sweep.  The decode pump's
`catch (Exception ex)` handler will catch it and log it, but the logged exception
will be `AggregateException` rather than `OperationCanceledException`.  This is
cosmetically ugly but not a runtime fault.

If clean shutdown logging is later required, wrap the `Parallel.For` in a
try/catch that unwraps a single-inner `AggregateException`:

```csharp
try
{
    Parallel.For(...);
}
catch (AggregateException ae) when (ae.InnerExceptions.Count == 1
                                     && ae.InnerException is OperationCanceledException)
{
    throw ae.InnerException;
}
```

This is not required to ship p8.

---

## Next Steps

1. Resolve the audio capture error per the three steps above
2. Run `dotnet test -c Release` — all tests including FR-026 should be green
3. Verify the live band log shows `elapsed=` values under 5,000 ms and
   `Costas candidates=` in the low hundreds
4. Once Task 7.3 is confirmed, p8 is ready for QA gate review and merge
