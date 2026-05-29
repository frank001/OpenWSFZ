# Developer Briefing — p5-ft8-decoder (Round 20)

**Date:** 2026-05-24
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Scope:** Fix 100% CPU / UI freeze (FT8 decoder); fix capture.Dispose() hang; implement
WebSocketHub.AbortAll() (S1a/S1b were not implemented in dev-briefing-19)

---

## Situation

Three independent problems are present.

### Problem A — FT8 decoder is running ~29 billion arithmetic operations per 15-second window

This is the root cause of the 100% CPU, the unresponsive UI, the defective countdown timer,
and the absence of FT8 decode results.

`Ft8Decoder.DecodeAsync` performs a two-dimensional sweep:

```
for startSample in [0 … 97 440] step 1920       // 52 time positions
  for baseHz in [50 … 3000] step 6.25            // 473 frequency positions
    SymbolExtractor.Extract(pcm, startSample, baseHz)   // ← the bottleneck
    CostasSynchroniser.FindCandidates(grid, threshold)
```

`SymbolExtractor.Extract` calls `GoertzelDetector.ComputeEnergy` for each of
79 symbols × 8 tones = 632 times per call, each Goertzel evaluation iterating
1 920 samples. Total work:

```
52 × 473 × 79 × 8 × 1 920 ≈ 29.8 billion multiply-accumulate operations per decode cycle
```

At realistic throughput this takes ~30 seconds on a single core. Since `DecodeAsync` is
synchronous (`return Task.FromResult(...)`) it blocks the thread-pool thread for the entire
duration. The first window is ready ~4.5 seconds after startup; the decoder immediately
saturates one CPU core and holds it continuously.

**The fix:** compute a 2048-point zero-padded FFT **once per time position** (79 FFTs),
then extract each (baseHz, tone) energy value from the pre-computed spectrogram by a
single array lookup. This reduces work to:

```
52 × 79 FFTs of 2048 samples ≈ 93 million ops     (FFT phase)
52 × 473 × 79 × 8 array lookups ≈ 16 million ops  (extraction phase)
Total ≈ 109 million ops per decode cycle
```

**Speedup ≈ 275×.** The decode per 15-second window drops from ~30 s to ~0.1 s.

---

### Problem B — `capture.Dispose()` hangs for 10 seconds

`capture.StopRecording()` now completes quickly (dev-briefing-19 S2 working as intended),
but the hang has moved to the subsequent `capture.Dispose()` call. The log shows:

```
15:28:53 DIAG STA finally: calling capture.Dispose() on '...'
           [10-second silence]
15:29:03 StopAsync: capture task did not complete within 10 s
```

The same Task.Run + timeout treatment used for `StopRecording` must be applied to `Dispose`.

---

### Problem C — `WebSocketHub.AbortAll()` was not implemented

The ApplicationStopping log still reads "Application stopping — shutting down capture
pipeline." (old text). S1a and S1b from dev-briefing-19 were not implemented. Heartbeats
continue for ~20 seconds after ApplicationStopping because `ctx.RequestAborted` (the token
passed to `HandleAsync`) is not cancelled by `ApplicationStopping`. These tasks must be
completed.

---

## Tasks

### P1a — Extract `Fft` to a shared utility class

**New file:** `src/OpenWSFZ.Ft8/Dsp/FftCompute.cs`

Create a shared, internal Cooley-Tukey radix-2 FFT implementation so the algorithm is not
duplicated between `SpectrumAnalyser` and `SymbolExtractor`.

```csharp
namespace OpenWSFZ.Ft8.Dsp;

/// <summary>
/// Shared radix-2 Cooley-Tukey in-place FFT for power-of-2 sizes.
/// </summary>
internal static class FftCompute
{
    /// <summary>
    /// In-place radix-2 DIT FFT.  <paramref name="re"/> and <paramref name="im"/> must be
    /// the same length, which must be a power of two.
    /// </summary>
    internal static void Fft(float[] re, float[] im)
    {
        var n = re.Length;

        // Bit-reversal permutation.
        for (int i = 1, j = 0; i < n; i++)
        {
            var bit = n >> 1;
            for (; (j & bit) != 0; bit >>= 1) j ^= bit;
            j ^= bit;
            if (i < j)
            {
                (re[i], re[j]) = (re[j], re[i]);
                (im[i], im[j]) = (im[j], im[i]);
            }
        }

        // Butterfly passes.
        for (var len = 2; len <= n; len <<= 1)
        {
            var ang = -2f * MathF.PI / len;
            var wRe = MathF.Cos(ang);
            var wIm = MathF.Sin(ang);

            for (var i = 0; i < n; i += len)
            {
                var curRe = 1f;
                var curIm = 0f;
                for (var j = 0; j < len / 2; j++)
                {
                    var uRe = re[i + j];
                    var uIm = im[i + j];
                    var vRe = re[i + j + len / 2] * curRe - im[i + j + len / 2] * curIm;
                    var vIm = re[i + j + len / 2] * curIm + im[i + j + len / 2] * curRe;

                    re[i + j]           = uRe + vRe;
                    im[i + j]           = uIm + vIm;
                    re[i + j + len / 2] = uRe - vRe;
                    im[i + j + len / 2] = uIm - vIm;

                    var nextRe = curRe * wRe - curIm * wIm;
                    curIm      = curRe * wIm + curIm * wRe;
                    curRe      = nextRe;
                }
            }
        }
    }
}
```

**Modified:** `src/OpenWSFZ.Ft8/Dsp/SpectrumAnalyser.cs`

Replace the private `Fft(float[] re, float[] im)` method body with a delegation to
`FftCompute.Fft`. The existing implementation is identical to the one above — just remove
the body and forward the call:

```csharp
// Before (private static):
private static void Fft(float[] re, float[] im) { /* existing Cooley-Tukey body */ }

// After:
private static void Fft(float[] re, float[] im) => FftCompute.Fft(re, im);
```

---

### P1b — Add `ComputeSpectrogram` and `ExtractFromSpectrogram` to `SymbolExtractor`

**File:** `src/OpenWSFZ.Ft8/Dsp/SymbolExtractor.cs`

Add the following constants and two new internal methods. **Do not modify the existing
`Extract` method** — it is used by unit tests and must remain unchanged.

Add constants after the existing public constants:

```csharp
/// <summary>
/// FFT size used by the spectrogram path.  1 920 samples are zero-padded to this
/// value (the next power of 2) before the FFT.  Bin spacing = 12 000 / 2 048 ≈ 5.859 Hz.
/// The frequency error versus the exact 6.25 Hz spacing is ≤ 3 Hz per tone — negligible
/// for FT8 tone discrimination.
/// </summary>
internal const int FftSizePadded = 2048;

/// <summary>Number of unique positive-frequency bins in the zero-padded FFT.</summary>
internal const int SpecBins = FftSizePadded / 2; // 1 024
```

Add two new methods inside the class:

```csharp
/// <summary>
/// Pre-computes a power spectrogram for all 79 symbol windows starting at
/// <paramref name="startSample"/>.
///
/// <para>
/// Each 1 920-sample symbol window is zero-padded to 2 048 samples and passed
/// through a radix-2 FFT.  The squared magnitudes of the 1 024 positive-frequency
/// bins are stored in the returned array.
/// </para>
///
/// <para>
/// Bin <c>k</c> corresponds to frequency <c>k × 12 000 / 2 048 ≈ k × 5.859 Hz</c>.
/// To find the bin for a target frequency <c>f</c>:
/// <c>bin = (int)Math.Round(f * FftSizePadded / SampleRate)</c>.
/// </para>
///
/// <para>
/// Call this <strong>once per time-domain start position</strong>; then call
/// <see cref="ExtractFromSpectrogram"/> for each candidate base frequency.
/// This reduces per-decode work from O(F·S·T·N) to O(S·T·N log N), where
/// F = frequency sweep width (~473 steps), S = symbol count (79),
/// T = time sweep positions (52), N = FFT size (2 048).
/// </para>
/// </summary>
/// <returns>
/// A <c>float[SymbolCount, SpecBins]</c> array of squared FFT magnitudes.
/// </returns>
internal static float[,] ComputeSpectrogram(ReadOnlySpan<float> pcm, int startSample)
{
    var result = new float[SymbolCount, SpecBins];
    var re     = new float[FftSizePadded];
    var im     = new float[FftSizePadded];

    for (int sym = 0; sym < SymbolCount; sym++)
    {
        int offset = startSample + sym * SamplesPerSymbol;
        if (offset + SamplesPerSymbol > pcm.Length) break;

        // Copy 1 920 samples into the FFT buffer; the remaining 128 stay zero (padding).
        pcm.Slice(offset, SamplesPerSymbol).CopyTo(re);
        Array.Clear(re, SamplesPerSymbol, FftSizePadded - SamplesPerSymbol); // zero pad
        Array.Clear(im, 0, FftSizePadded);

        FftCompute.Fft(re, im);

        for (int bin = 0; bin < SpecBins; bin++)
            result[sym, bin] = re[bin] * re[bin] + im[bin] * im[bin];
    }

    return result;
}

/// <summary>
/// Extracts a 79 × 8 log-energy grid from a pre-computed spectrogram by mapping
/// each FT8 tone to its nearest FFT bin.
///
/// For each of the 79 symbols, the energy for tone <c>t</c> is taken from
/// FFT bin <c>baseBin + t</c> where
/// <c>baseBin = (int)Math.Round(baseFrequencyHz * FftSizePadded / SampleRate)</c>.
/// </summary>
/// <param name="spectrogram">
/// Output of <see cref="ComputeSpectrogram"/>: <c>float[SymbolCount, SpecBins]</c>.
/// </param>
/// <param name="baseBin">
/// Bin index of the lowest tone.  Compute as
/// <c>(int)Math.Round(baseFrequencyHz * FftSizePadded / SampleRate)</c>.
/// </param>
internal static float[,] ExtractFromSpectrogram(float[,] spectrogram, int baseBin)
{
    int symCount = spectrogram.GetLength(0); // 79
    int specBins = spectrogram.GetLength(1); // 1 024
    var grid     = new float[symCount, ToneCount];

    for (int sym = 0; sym < symCount; sym++)
    for (int tone = 0; tone < ToneCount; tone++)
    {
        int   bin    = baseBin + tone;
        float energy = (uint)bin < (uint)specBins ? spectrogram[sym, bin] : 0f;
        grid[sym, tone] = MathF.Log(energy + 1e-10f);
    }

    return grid;
}
```

---

### P1c — Switch `Ft8Decoder.DecodeAsync` to the two-phase spectrogram approach

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`

Replace the inner frequency loop to use a pre-computed spectrogram per time position.

```csharp
// Before: single nested loop calling SymbolExtractor.Extract on every (startSample, baseHz) pair
for (int startSample = 0; startSample <= maxStartSample; startSample += SamplesPerSymbol)
{
    for (double baseHz = MinFreqHz; baseHz <= MaxFreqHz; baseHz += ToneSpacing)
    {
        ct.ThrowIfCancellationRequested();

        var grid       = SymbolExtractor.Extract(pcm, startSample, baseFrequencyHz: baseHz);
        var candidates = CostasSynchroniser.FindCandidates(grid, SyncThreshold);
        ...
    }
}

// After: compute spectrogram once per time position; extract by bin lookup for each frequency
for (int startSample = 0; startSample <= maxStartSample; startSample += SamplesPerSymbol)
{
    // P1: pre-compute 79 FFTs once for this time offset, replacing ~24 000 Goertzel calls.
    var spectrogram = SymbolExtractor.ComputeSpectrogram(pcm, startSample);

    for (double baseHz = MinFreqHz; baseHz <= MaxFreqHz; baseHz += ToneSpacing)
    {
        ct.ThrowIfCancellationRequested();

        int baseBin    = (int)Math.Round(baseHz * SymbolExtractor.FftSizePadded
                                                 / (double)SymbolExtractor.SampleRate);
        var grid       = SymbolExtractor.ExtractFromSpectrogram(spectrogram, baseBin);
        var candidates = CostasSynchroniser.FindCandidates(grid, SyncThreshold);
        ...
    }
}
```

No other changes to `Ft8Decoder`.

---

### P1d — Add regression test for the spectrogram extraction path

**File:** `tests/OpenWSFZ.Ft8.Tests/GoertzelDetectorTests.cs`

Add two new facts to the existing test class (do not touch the existing tests):

```csharp
[Fact(DisplayName = "SymbolExtractor.ComputeSpectrogram + ExtractFromSpectrogram: peak tone matches known-good signal")]
public void Spectrogram_PureToneSingleSymbol_PeaksAtCorrectTone()
{
    // Same setup as Extract_PureToneSingleSymbol_PeaksAtCorrectTone.
    double baseHz    = 1000.0;
    int    targetTone = 3;
    double toneHz    = baseHz + targetTone * SymbolExtractor.ToneSpacingHz; // 1018.75 Hz

    var pcm = new float[15 * SampleRate];
    var sym = GenerateSine(toneHz, SymbolExtractor.SamplesPerSymbol, SampleRate);
    sym.CopyTo(new Span<float>(pcm, 0, SymbolExtractor.SamplesPerSymbol));

    var spectrogram = SymbolExtractor.ComputeSpectrogram(pcm, startSample: 0);
    int baseBin     = (int)Math.Round(baseHz * SymbolExtractor.FftSizePadded
                                              / (double)SymbolExtractor.SampleRate);
    var grid        = SymbolExtractor.ExtractFromSpectrogram(spectrogram, baseBin);

    int peakTone = 0;
    float peakVal = grid[0, 0];
    for (int t = 1; t < SymbolExtractor.ToneCount; t++)
    {
        if (grid[0, t] > peakVal) { peakVal = grid[0, t]; peakTone = t; }
    }

    peakTone.Should().Be(targetTone,
        "the FFT-based spectrogram should identify the same dominant tone as the Goertzel path");
}

[Fact(DisplayName = "SymbolExtractor.ComputeSpectrogram: produces SymbolCount × SpecBins array")]
public void Spectrogram_Dimensions_AreCorrect()
{
    var pcm         = new float[15 * SampleRate];
    var spectrogram = SymbolExtractor.ComputeSpectrogram(pcm, startSample: 0);

    spectrogram.GetLength(0).Should().Be(SymbolExtractor.SymbolCount);
    spectrogram.GetLength(1).Should().Be(SymbolExtractor.SpecBins);
}
```

---

### P2 — Apply Task.Run + 3-second timeout to `capture.Dispose()`

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`

The `if (stopped)` branch in the STA finally block currently calls `capture.Dispose()` with
no timeout.  Apply the same treatment used for `capture.StopRecording()`:

```csharp
// Before (inside "if (stopped)" block):
_logger?.LogInformation(
    "DIAG STA finally: calling capture.Dispose() on '{DeviceId}'.", deviceId);
try { capture.Dispose(); } catch { }

// After:
_logger?.LogInformation(
    "DIAG STA finally: calling capture.Dispose() on '{DeviceId}' (3 s timeout).", deviceId);
var disposeTask = Task.Run(() => { try { capture.Dispose(); } catch { } });
if (disposeTask.Wait(TimeSpan.FromSeconds(3)))
    _logger?.LogInformation(
        "DIAG STA finally: capture.Dispose() completed on '{DeviceId}'.", deviceId);
else
    _logger?.LogWarning(
        "DIAG STA finally: capture.Dispose() timed out after 3 s on '{DeviceId}' " +
        "— abandoning device handle; OS will reclaim on process exit.", deviceId);
```

---

### P3a — Add `WebSocketHub.AbortAll()` (S1a from dev-briefing-19, not yet implemented)

**File:** `src/OpenWSFZ.Web/WebSocketHub.cs`

Add the following method immediately after `SetBroadcastLogger` (after the line
`internal static void SetBroadcastLogger(...) => ...`):

```csharp
/// <summary>
/// Aborts all currently-open WebSocket connections immediately.
/// Called at the start of application shutdown so the browser UI goes dark at once,
/// rather than continuing to receive heartbeats for the duration of the capture
/// pipeline teardown sequence.
/// Each connection's <see cref="HandleAsync"/> loop will detect the aborted socket state
/// via <see cref="ReceiveUntilCloseAsync"/> and exit without a graceful close handshake.
/// </summary>
internal static void AbortAll()
{
    foreach (var (ws, _) in ActiveSockets)
    {
        try { ws.Abort(); } catch { /* best-effort */ }
    }
}
```

---

### P3b — Call `AbortAll()` at the start of `ApplicationStopping.Register` (S1b from dev-briefing-19, not yet implemented)

**File:** `src/OpenWSFZ.Daemon/Program.cs`

Replace the `ApplicationStopping.Register` callback:

```csharp
// Before:
app.Lifetime.ApplicationStopping.Register(() =>
{
    startupLogger.LogInformation("Application stopping — shutting down capture pipeline.");

    // B2: wait for any in-progress restart...
    restartSemaphore.Wait();

// After:
app.Lifetime.ApplicationStopping.Register(() =>
{
    startupLogger.LogInformation(
        "Application stopping — aborting WebSocket connections and shutting down capture pipeline.");

    // P3: abort all active WebSocket connections immediately so the browser UI goes dark
    // the moment Ctrl+C is pressed, rather than continuing to receive heartbeats while
    // the capture pipeline drains.  Must be called BEFORE restartSemaphore.Wait() so the
    // abort is visible to clients regardless of any ongoing restart delay.
    WebSocketHub.AbortAll();

    // B2: wait for any in-progress restart...
    restartSemaphore.Wait();
```

---

## Expected outcomes after this briefing

| Symptom | Before | After |
|---|---|---|
| CPU usage | 100% continuously (Goertzel ×29B ops) | Near-zero between decodes; ~0.1 s spike per 15 s cycle |
| UI responsiveness | Frozen — timer defective, browser unresponsive | Fully responsive |
| FT8 decodes | None (decoder never completes) | One decode attempt per 15 s window |
| Browser on Ctrl+C | Stays connected for ~20 s | Goes dark within ~1 s |
| Process exit after Ctrl+C | ~20 s | ~3–6 s (semaphore wait + 3 s Dispose timeout) |

---

## Summary

| Task | Files | Description |
|---|---|---|
| P1a | `FftCompute.cs` (new), `SpectrumAnalyser.cs` | Extract shared FFT into `FftCompute` |
| P1b | `SymbolExtractor.cs` | Add `ComputeSpectrogram` + `ExtractFromSpectrogram` |
| P1c | `Ft8Decoder.cs` | Use two-phase spectrogram approach in `DecodeAsync` |
| P1d | `GoertzelDetectorTests.cs` | Two new regression tests for spectrogram path |
| P2  | `WasapiAudioSource.cs` | 3-second timeout on `capture.Dispose()` |
| P3a | `WebSocketHub.cs` | Add `AbortAll()` |
| P3b | `Program.cs` | Call `WebSocketHub.AbortAll()` before `restartSemaphore.Wait()` |

---

## Appendix — Waterfall independence review

### Question

The Captain observed that the waterfall display appeared to depend on FT8 signal decoding.
The expectation is that the waterfall should update continuously from live audio regardless
of whether any decodes are in progress.

### Finding: the architecture is correct — no code dependency exists

The spectrum and decode pipelines are entirely separate paths through the codebase:

**Spectrum / waterfall path:**
1. WASAPI DataAvailable → `WasapiAudioSource` (STA thread) → `innerChannel`
2. `CaptureManager` capture task reads `innerChannel`, calls `ChunkReceived` callback
3. `ChunkReceived` → `SpectrumAnalyser.Push(chunk)` (accumulates samples, fires every 2 048 samples)
4. `SpectrumReady` handler in `Program.cs` → dBFS mapping → `SpectrumEventBus.Publish(bins)`
5. `SpectrumEventBus.Publish` → `WebSocketHub.BroadcastSpectrum(bins)`
6. `BroadcastSpectrum` serialises JSON and fires `SendWithTimeoutAsync` tasks
7. Browser receives `{ "type": "spectrum", "payload": [...] }` → `WaterfallRenderer.render(bins)`

**FT8 decode path:**
1. `CaptureManager` writes chunks to `_channel`
2. `CycleFramer` reads `_channel.Reader` and accumulates 180 000-sample windows
3. Completed window written to `framerOutput`
4. Decode pump task reads `framerOutput` → `Ft8Decoder.DecodeAsync(pcm)`
5. Results → `DecodeEventBus.Publish(results)` → `WebSocketHub.BroadcastDecodes(results)`
6. Browser receives `{ "type": "decode", "payload": [...] }` → `handleDecodes(results)`

There is no shared gate, flag, lock, or ordering dependency between these two paths. The
waterfall handler in `main.js` (`event.type === 'spectrum'`) is completely independent of
the decode handler (`event.type === 'decode'`).

### Root cause of the observed effect

The waterfall appeared frozen because **Problem A (FT8 decoder CPU)** causes a secondary
failure in the spectrum broadcast path. The mechanism is:

1. `Ft8Decoder.DecodeAsync` is synchronous — it runs ~29 billion ops on a thread-pool
   thread for ~30 seconds without yielding.

2. `BroadcastSpectrum` fires every ~170 ms. It serialises JSON synchronously on the
   capture thread, then calls `SendWithTimeoutAsync` as a fire-and-forget task that needs
   the thread pool to do the actual `ws.SendAsync`.

3. `SendWithTimeoutAsync` has a hard 1-second `CancellationTokenSource` budget covering
   both the semaphore wait AND the send. When the thread pool is saturated, either the
   send is delayed past 1 second, or — if another spectrum send is already in-flight on
   the same socket — the lock wait times out.

4. On timeout, `SendWithTimeoutAsync` calls `ws.Abort()` and removes the socket from
   `ActiveSockets`. The browser's WebSocket `onclose` fires, `ws.js` schedules a 1-second
   reconnect. The next spectrum frame arrives before the reconnect completes, so
   `ActiveSockets.IsEmpty` is true and the frame is silently dropped. This repeats for
   the entire ~30-second decode, making the waterfall appear frozen or disconnected.

### Fix

**No additional code changes are required.** Once P1 is implemented and the decoder
completes in ~0.1 seconds every 15 seconds, CPU saturation ceases, thread-pool threads are
available promptly, `SendWithTimeoutAsync` completes well within its 1-second budget, and
the waterfall updates at its natural cadence of approximately 6 frames per second,
continuously and independently of decode activity.

### Observation for the record

There is one minor architecture note that does not require immediate action but is worth
recording: the JSON serialisation of the 512-bin spectrum array (`JsonSerializer.Serialize`
+ `Encoding.UTF8.GetBytes`) runs synchronously on the `CaptureManager` capture thread
inside `BroadcastSpectrum`. At 6 calls per second the overhead is negligible (~10 µs). If
a future change increases the spectrum rate substantially, this serialisation should be
moved off the capture thread (e.g., into the fire-and-forget task) to avoid blocking the
channel write.
