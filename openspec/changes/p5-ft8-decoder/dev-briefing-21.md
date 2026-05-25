# Developer Briefing — p5-ft8-decoder (Round 21)

**Date:** 2026-05-24
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Scope:** Eliminate LOH GC pressure in decode path; throttle waterfall rendering in browser

---

## Situation

Dev-briefing-20 has been implemented. CPU is "down about a bit" rather than the expected
near-zero. The UI is "totally unresponsive now, totally useless."

Two independent causes remain.

---

### Cause A — LOH GC pressure: `ComputeSpectrogram` allocates a 316 KB array 52 times per decode cycle

The FFT speedup (P1) is correctly implemented — the algorithm is sound and the
theoretical 275× improvement is real. The continued CPU elevation has a different root
cause: each call to `SymbolExtractor.ComputeSpectrogram` allocates a fresh
`float[SymbolCount, SpecBins]` array:

```
float[79, 1024] = 79 × 1024 × 4 bytes = 323 584 bytes ≈ 316 KB
```

The .NET Large Object Heap (LOH) threshold is **85 000 bytes**. Any single allocation
≥ 85 KB bypasses the Gen 0/Gen 1 nursery heaps and goes directly to the LOH, which is
collected only as part of a **Gen 2 (full) garbage collection** — a Stop-the-World pause.

With 52 time-domain sweep positions per decode cycle, `Ft8Decoder.DecodeAsync` allocates:

```
52 × 316 KB ≈ 16.4 MB of LOH per 15-second cycle
```

The Gen 2 GC triggered by this pressure causes STW pauses that inflate CPU measurements
and periodically freeze all managed threads for the duration of the collection. This is
why the CPU reads as "down a bit" rather than near-zero: the FFT work is genuinely fast,
but GC overhead fills in the gaps.

**The fix is simple:** allocate the spectrogram buffer **once** at `Ft8Decoder`
construction time as an instance field (`private readonly float[,] _spectrogram`).
Reuse that single buffer on every call, eliminating all 52 LOH allocations per cycle.
This requires a new `FillSpectrogram` overload in `SymbolExtractor` that writes into a
caller-provided buffer rather than returning a new one.

---

### Cause B — JS main thread saturated by waterfall rendering (regression from dev-briefing-20)

The "totally unresponsive" UI is a paradoxical regression caused by the successful fixes
in dev-briefing-20. Before dev-briefing-20, the 100% CPU caused `SendWithTimeoutAsync`
to hit its 1-second budget repeatedly, call `ws.Abort()`, and force the browser to
reconnect every few seconds. The browser was spending most of its time reconnecting —
very few spectrum messages actually reached `WaterfallRenderer.render()`.

After dev-briefing-20 (P1 reduced CPU + P3 implemented `AbortAll()`), the WebSocket
connection is stable. The browser now reliably receives spectrum messages at their
natural cadence of **~6 per second**. In `main.js`, the `onmessage` handler calls
`renderer.render(event.payload)` **synchronously** on every message:

```javascript
if (event.type === 'spectrum' && Array.isArray(event.payload)) {
  renderer.render(event.payload);   // ← called 6 × per second, inside onmessage
  return;
}
```

`WaterfallRenderer.render()` performs three expensive operations on every call:

1. `data.copyWithin(rowBytes, 0)` — shifts the entire `ImageData` pixel buffer
   (canvas_width × canvas_height × 4 bytes) by one row
2. Pixel row write — trivial assignment loop
3. `ctx.putImageData(this._imageData, 0, 0)` — uploads the entire buffer to the canvas
   GPU backing store

At HiDPI (`devicePixelRatio = 2`), a 900 × 300 CSS-pixel canvas element becomes
**1800 × 600 physical pixels** — an `ImageData` buffer of 1800 × 600 × 4 ≈ **4.3 MB**.
`putImageData` for a 4.3 MB buffer involves synchronising the GPU command pipeline and
can take **5–30 ms** on typical hardware. At 6 calls per second, that is up to
**180 ms/second** of JS main thread time spent inside `render()`.

The critical detail is that `render()` runs inside a `WebSocket.onmessage` handler — a
**macrotask** on the browser's event loop. While a macrotask runs, the browser cannot
process timer callbacks (`setInterval`), user input events, or `requestAnimationFrame`
callbacks. If spectrum messages arrive in a burst (e.g., after a brief network lag), the
browser queues multiple `onmessage` tasks and executes them without interruption — 6 ×
`putImageData` back-to-back with no opportunity for the countdown timer (`setInterval`
100 ms), keyboard input, or click handlers to run. This is why the UI appears completely
frozen.

**The fix:** replace the direct `renderer.render()` call with a
`requestAnimationFrame`-throttled dispatch. The latest bins are stored in a closure
variable; a `requestAnimationFrame` callback is scheduled only once per batch. The
`rAF` callback fires **between macrotasks**, at most once per browser frame (~16 ms at
60 fps). Multiple `onmessage` events arriving in a burst are coalesced into a single
`render()` call. This caps the GPU upload rate at the screen refresh rate regardless of
WebSocket message cadence, and ensures the countdown timer and user input are never
starved.

---

## Tasks

### W1 — Eliminate LOH allocations in the decode path

#### W1a — Add `SymbolExtractor.FillSpectrogram` (in-place overload)

**File:** `src/OpenWSFZ.Ft8/Dsp/SymbolExtractor.cs`

Add the following method immediately after `ComputeSpectrogram`. **Do not modify or
remove the existing `ComputeSpectrogram` method** — it returns a new array and is used
by existing tests.

```csharp
/// <summary>
/// Fills <paramref name="result"/> with the power spectrogram for the 79 symbol windows
/// starting at <paramref name="startSample"/>.
///
/// <para>
/// Functionally identical to <see cref="ComputeSpectrogram"/> but writes into a
/// caller-provided buffer instead of allocating a new array.  Use this overload
/// from long-running paths (e.g. <c>Ft8Decoder.DecodeAsync</c>) to avoid 316 KB
/// LOH allocations on every call.
/// </para>
/// </summary>
/// <param name="pcm">Full PCM buffer.</param>
/// <param name="startSample">First sample of the first symbol.</param>
/// <param name="result">
/// Pre-allocated <c>float[SymbolCount, SpecBins]</c> buffer to fill.
/// All elements are fully overwritten for symbols within the buffer bounds;
/// symbols that would fall outside <paramref name="pcm"/> leave the corresponding
/// rows unchanged (same guard as <see cref="ComputeSpectrogram"/>).
/// </param>
internal static void FillSpectrogram(ReadOnlySpan<float> pcm, int startSample, float[,] result)
{
    var re = new float[FftSizePadded];
    var im = new float[FftSizePadded];

    for (int sym = 0; sym < SymbolCount; sym++)
    {
        int offset = startSample + sym * SamplesPerSymbol;
        if (offset + SamplesPerSymbol > pcm.Length) break;

        pcm.Slice(offset, SamplesPerSymbol).CopyTo(re);
        Array.Clear(re, SamplesPerSymbol, FftSizePadded - SamplesPerSymbol);
        Array.Clear(im, 0, FftSizePadded);

        FftCompute.Fft(re, im);

        for (int bin = 0; bin < SpecBins; bin++)
            result[sym, bin] = re[bin] * re[bin] + im[bin] * im[bin];
    }
}
```

#### W1b — Pre-allocate `_spectrogram` in `Ft8Decoder` and switch to `FillSpectrogram`

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`

**Step 1 — Add `SpecBins` constant.**

Add the following line to the constants block, immediately after the `CodeLength` line:

```csharp
// Before (the last constant in the block):
private const int    CodeLength   = LdpcDecoder.CodeLength;          // 174

// After:
private const int    CodeLength   = LdpcDecoder.CodeLength;          // 174
private const int    SpecBins     = SymbolExtractor.SpecBins;        // 1 024
```

**Step 2 — Add pre-allocated spectrogram field.**

Add the following field immediately after `_logger`, before the constructor:

```csharp
// Before:
private readonly IClock              _clock;
private readonly ILogger<Ft8Decoder>? _logger;

public Ft8Decoder(IClock clock, ILogger<Ft8Decoder>? logger = null)

// After:
private readonly IClock              _clock;
private readonly ILogger<Ft8Decoder>? _logger;

// Pre-allocated spectrogram buffer — 79 × 1 024 floats ≈ 316 KB.
// Allocated once at construction to avoid LOH allocations on every decode cycle.
// Safe to share across DecodeAsync invocations: CycleFramer emits windows serially
// (one at a time) so DecodeAsync is never called concurrently on the same instance.
private readonly float[,] _spectrogram = new float[SymbolCount, SpecBins];

public Ft8Decoder(IClock clock, ILogger<Ft8Decoder>? logger = null)
```

**Step 3 — Switch the decode loop to use `FillSpectrogram`.**

Inside `DecodeAsync`, in the time-domain sweep loop, replace:

```csharp
// Before:
var spectrogram = SymbolExtractor.ComputeSpectrogram(pcm, startSample);
```

```csharp
// After:
SymbolExtractor.FillSpectrogram(pcm, startSample, _spectrogram);
```

Immediately following that line, update the `ExtractFromSpectrogram` call to pass the
instance field instead of the now-removed local variable:

```csharp
// Before:
var grid = SymbolExtractor.ExtractFromSpectrogram(spectrogram, baseBin);

// After:
var grid = SymbolExtractor.ExtractFromSpectrogram(_spectrogram, baseBin);
```

No other changes to `Ft8Decoder`.

---

### W2 — Throttle waterfall rendering with `requestAnimationFrame`

**File:** `web/js/main.js`

**Step 1 — Add throttle state variables.**

In the `DOMContentLoaded` callback, add two `let` declarations immediately after the
`observer.observe(...)` line and before the `connect(...)` call:

```javascript
// Before:
  const observer = new ResizeObserver(() => renderer.resize());
  observer.observe(canvas.parentElement ?? canvas);

  // Connect WebSocket and update status bar.
  connect((event) => {

// After:
  const observer = new ResizeObserver(() => renderer.resize());
  observer.observe(canvas.parentElement ?? canvas);

  // W2: requestAnimationFrame throttle state for spectrum rendering.
  // Coalesces rapid onmessage deliveries into at most one putImageData call per
  // browser frame, preventing the JS main thread from being starved by putImageData.
  let pendingSpectrumBins = null;
  let spectrumRafPending  = false;

  // Connect WebSocket and update status bar.
  connect((event) => {
```

**Step 2 — Replace the `spectrum` handler.**

Replace the existing `spectrum` event block:

```javascript
    // Before:
    if (event.type === 'spectrum' && Array.isArray(event.payload)) {
      renderer.render(event.payload);
      return;
    }
```

```javascript
    // After:
    if (event.type === 'spectrum' && Array.isArray(event.payload)) {
      // W2: store latest bins; schedule a single render on the next animation frame.
      // If another frame is already pending, just update the pending data — the already-
      // scheduled rAF callback will pick up the latest value when it fires.
      pendingSpectrumBins = event.payload;
      if (!spectrumRafPending) {
        spectrumRafPending = true;
        requestAnimationFrame(() => {
          spectrumRafPending = false;
          if (pendingSpectrumBins !== null) {
            renderer.render(pendingSpectrumBins);
            pendingSpectrumBins = null;
          }
        });
      }
      return;
    }
```

**Why this works:**

- `requestAnimationFrame` callbacks fire **between macrotasks**, just before the browser
  paints. They never interrupt a running macrotask.
- If 6 `onmessage` macrotasks queue up in rapid succession, all 6 update
  `pendingSpectrumBins` but only the first schedules a `rAF` callback (the
  `spectrumRafPending` guard prevents duplicate scheduling). When the `rAF` fires, it
  renders only the **most recent** bins — one `putImageData` call for the whole burst.
- The `setInterval(tickCycleTimer, 100)` and all user input events run normally between
  `rAF` callbacks, so the countdown timer and interactive controls are never starved.
- At steady state (6 messages/second, no bursting), one `rAF` is scheduled per message
  and the render rate matches the message rate (6 fps), well within the 60 fps budget.

---

## Expected outcomes after this briefing

| Symptom | Before | After |
|---|---|---|
| CPU between decodes | Elevated (LOH Gen 2 GC pauses) | Near-zero |
| CPU during decode | Brief spike per 15 s cycle | Brief spike per 15 s cycle (unchanged) |
| UI responsiveness | Totally unresponsive | Fully responsive |
| Countdown timer | Frozen | Updates every 100 ms as designed |
| Waterfall frame rate | Unreliable / bursting | Smooth, capped at screen refresh rate |
| Waterfall latency | Same | Same (one frame ≈ 16 ms added; imperceptible) |

---

## Summary

| Task | File | Effect |
|---|---|---|
| W1a | `SymbolExtractor.cs` | Add `FillSpectrogram` in-place overload — no allocation |
| W1b | `Ft8Decoder.cs` | Add `SpecBins` const; pre-allocate `_spectrogram` field; switch to `FillSpectrogram` |
| W2  | `main.js` | `requestAnimationFrame` throttle — at most one `putImageData` per browser frame |
