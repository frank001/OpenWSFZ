# Developer Briefing — p5-ft8-decoder (Round 15)

**Date:** 2026-05-24
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Scope:** Replace the waterfall placeholder with a live scrolling spectrum display

---

## Overview

The `#waterfall-panel` canvas has displayed a static "Waterfall — awaiting audio input"
placeholder since Phase 4. The backend audio pipeline already delivers 12 kHz mono
float samples via `CaptureManager.ChunkReceived`. This briefing wires those samples into
a Cooley-Tukey FFT, broadcasts the resulting spectrum over WebSocket, and replaces the
placeholder with a scrolling waterfall rendered in the browser.

The FT8 decoder work is **parked**. No changes to `CycleFramer`, `Ft8Decoder`, or
their wiring are required.

---

## Data Flow

```
CaptureManager
  └─ ChunkReceived (float[])
       └─ SpectrumAnalyser.Push()
            └─ every 2048 new samples →
                 SpectrumReady (float[] dBFS, 512 bins)
                      └─ Program.cs converts → int[] [0-255]
                           └─ SpectrumEventBus.Publish()
                                └─ WebSocketHub.BroadcastSpectrum()
                                     └─ WebSocket "spectrum" event
                                          └─ WaterfallRenderer.render()
                                               └─ <canvas id="waterfall">
```

---

## Architecture Decisions

| Decision | Choice | Rationale |
|---|---|---|
| FFT size | 2048 samples | 170.7 ms / transform at 12 kHz; 5.86 Hz/bin resolution; fits one resampler drain chunk |
| Frequency coverage | Bins 0–511 → 0–2994 Hz | Covers full FT8 audio passband (200–2800 Hz) with margin |
| Window function | Hann | Standard choice; suppresses spectral leakage without excessive bin broadening |
| Update rate | 1 FFT per 2048 new samples | ≈ 5.9 fps; smooth enough without flooding the WebSocket |
| Wire format | JSON `int[]`, values 0–255 | ~1.6 KB/message; consistent with existing text-frame architecture |
| dBFS mapping | −120 dBFS → 0, 0 dBFS → 255 | −120 dBFS is a practical silence floor for 32-bit IEEE float capture |
| FFT implementation | Pure C# Cooley-Tukey radix-2 | No new NuGet packages; consistent with design doc policy |
| Placement | `OpenWSFZ.Ft8/Dsp/SpectrumAnalyser.cs` | Pure DSP with no NAudio dependency; reuses existing test project; consistent with `GoertzelDetector` precedent |

---

## Server-Side Tasks

### S.1 — Implement `SpectrumAnalyser`

**File:** `src/OpenWSFZ.Ft8/Dsp/SpectrumAnalyser.cs`

```csharp
namespace OpenWSFZ.Ft8.Dsp;

/// <summary>
/// Computes a power spectrum from a stream of 12 kHz mono float samples.
///
/// Accumulates samples into a 2048-point ring buffer. After every 2048 new
/// samples, applies a Hann window, runs a radix-2 Cooley-Tukey FFT, converts
/// to dBFS, and invokes <see cref="SpectrumReady"/> with the first
/// <see cref="OutputBinCount"/> magnitude values (covering 0–2994 Hz at 12 kHz).
///
/// Not thread-safe — Push must be called from a single thread.
/// </summary>
public sealed class SpectrumAnalyser
{
    public const int FftSize        = 2048;
    public const int SampleRate     = 12_000;
    public const int OutputBinCount = 512;   // bins 0–511 → 0–2994 Hz

    private static readonly float[] HannWindow = BuildHannWindow();

    private readonly float[] _ringBuffer = new float[FftSize];
    private int _writePos;
    private int _accumulated;

    /// <summary>
    /// Invoked after every 2048 new samples with the computed dBFS magnitudes
    /// (length = <see cref="OutputBinCount"/>). Values are in the range
    /// [<c>−120f</c>, <c>0f</c>], where <c>−120f</c> represents silence.
    /// </summary>
    public Action<float[]>? SpectrumReady { get; set; }

    /// <summary>
    /// Push a chunk of 12 kHz mono samples into the analyser.
    /// May invoke <see cref="SpectrumReady"/> synchronously before returning.
    /// </summary>
    public void Push(ReadOnlySpan<float> chunk)
    {
        foreach (var sample in chunk)
        {
            _ringBuffer[_writePos] = sample;
            _writePos = (_writePos + 1) % FftSize;
            _accumulated++;

            if (_accumulated >= FftSize)
            {
                _accumulated = 0;
                Compute();
            }
        }
    }

    private void Compute()
    {
        // Copy ring buffer in chronological order and apply Hann window.
        // _writePos is the oldest slot (next write target in a full ring).
        var re = new float[FftSize];
        var im = new float[FftSize]; // stays zero — real input

        for (var i = 0; i < FftSize; i++)
        {
            var srcIdx = (_writePos + i) % FftSize;
            re[i] = _ringBuffer[srcIdx] * HannWindow[i];
        }

        Fft(re, im);

        // Convert to dBFS; extract first OutputBinCount bins.
        // Normalisation factor: 2 / FftSize (one-sided spectrum, Hann compensation omitted
        // — display is for visualisation only, not calibrated level measurement).
        var magnitudes = new float[OutputBinCount];
        const float scale = 2f / FftSize;
        for (var i = 0; i < OutputBinCount; i++)
        {
            var mag = MathF.Sqrt(re[i] * re[i] + im[i] * im[i]) * scale;
            magnitudes[i] = mag > 0f
                ? MathF.Max(20f * MathF.Log10(mag), -120f)
                : -120f;
        }

        SpectrumReady?.Invoke(magnitudes);
    }

    // ── Cooley-Tukey radix-2 DIT FFT ─────────────────────────────────────────

    private static void Fft(float[] re, float[] im)
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
                    curIm = curRe * wIm + curIm * wRe;
                    curRe = nextRe;
                }
            }
        }
    }

    private static float[] BuildHannWindow()
    {
        var w = new float[FftSize];
        for (var i = 0; i < FftSize; i++)
            w[i] = 0.5f * (1f - MathF.Cos(2f * MathF.PI * i / (FftSize - 1)));
        return w;
    }
}
```

**Note on `Push` signature:** Accept `ReadOnlySpan<float>` so callers can pass `float[]`
or a slice without allocation. `CaptureManager.ChunkReceived` supplies `float[]` — this
is implicitly convertible.

---

### S.2 — Update `ChunkReceived` callback

**File:** `src/OpenWSFZ.Daemon/Program.cs`

Add `SpectrumAnalyser` instantiation and wiring **after** the existing monitor setup and
**before** `WebApp.Create`:

```csharp
// ── Spectrum analyser ─────────────────────────────────────────────────────
var spectrumAnalyser = new SpectrumAnalyser();
var spectrumBus      = new SpectrumEventBus();

spectrumAnalyser.SpectrumReady += magnitudes =>
{
    // Gate: skip serialisation if no clients are connected.
    if (!WebSocketHub.HasClients) return;

    // Map dBFS [−120, 0] → int [0, 255].
    var bins = new int[SpectrumAnalyser.OutputBinCount];
    for (var i = 0; i < bins.Length; i++)
    {
        var db = magnitudes[i];
        if (db < -120f) db = -120f;
        if (db >    0f) db =    0f;
        bins[i] = (int)MathF.Round((db + 120f) / 120f * 255f);
    }

    spectrumBus.Publish(bins);
};
```

Extend the existing `ChunkReceived` assignment to include `spectrumAnalyser.Push`:

```csharp
// BEFORE:
captureManager.ChunkReceived = chunk =>
{
    audioMonitor.ObserveSamples(chunk);
    dataFlowMonitor.OnChunkReceived();
};

// AFTER:
captureManager.ChunkReceived = chunk =>
{
    audioMonitor.ObserveSamples(chunk);
    dataFlowMonitor.OnChunkReceived();
    spectrumAnalyser.Push(chunk);
};
```

Add the required `using` statement: `using OpenWSFZ.Ft8.Dsp;`

---

### S.3 — Add `SpectrumEventBus`

**File:** `src/OpenWSFZ.Web/SpectrumEventBus.cs`

Parallel to the existing `DecodeEventBus` — a public façade over the internal
`WebSocketHub`:

```csharp
namespace OpenWSFZ.Web;

/// <summary>
/// Public façade that allows <c>OpenWSFZ.Daemon</c> to broadcast spectrum data
/// to all connected WebSocket clients without depending on the internal
/// <see cref="WebSocketHub"/> class directly.
/// </summary>
public sealed class SpectrumEventBus
{
    public void Publish(int[] bins) => WebSocketHub.BroadcastSpectrum(bins);
}
```

---

### S.4 — Add `BroadcastSpectrum` and `HasClients` to `WebSocketHub`

**File:** `src/OpenWSFZ.Web/WebSocketHub.cs`

Add alongside `BroadcastDecodes`:

```csharp
/// <summary>
/// True when at least one WebSocket client is currently connected.
/// Used to gate FFT computation and serialisation when no clients exist.
/// </summary>
internal static bool HasClients => !ActiveSockets.IsEmpty;

/// <summary>
/// Broadcasts a <c>spectrum</c> event carrying the given magnitude bins to all
/// currently connected WebSocket clients. Stale connections are closed and removed.
/// </summary>
/// <param name="bins">
/// Array of <see cref="SpectrumAnalyser.OutputBinCount"/> integers in [0, 255].
/// </param>
internal static void BroadcastSpectrum(int[] bins)
{
    if (ActiveSockets.IsEmpty) return;

    var msg     = new WsSpectrumMessage(Type: "spectrum", Payload: bins);
    var json    = JsonSerializer.Serialize(msg, AppJsonContext.Default.WsSpectrumMessage);
    var bytes   = Encoding.UTF8.GetBytes(json);
    var segment = new ArraySegment<byte>(bytes);

    foreach (var (ws, _) in ActiveSockets)
        _ = SendWithTimeoutAsync(ws, segment);
}
```

---

### S.5 — Register `WsSpectrumMessage` in `AppJsonContext`

**File:** `src/OpenWSFZ.Web/AppJsonContext.cs`

Add the new record and register it:

```csharp
/// <summary>Envelope for <c>spectrum</c> WebSocket text frames.</summary>
internal sealed record WsSpectrumMessage(string Type, int[] Payload);
```

Add to the `[JsonSerializable]` attribute list:

```csharp
[JsonSerializable(typeof(WsSpectrumMessage))]
[JsonSerializable(typeof(int[]))]
```

---

### S.6 — Unit tests for `SpectrumAnalyser`

**File:** `tests/OpenWSFZ.Ft8.Tests/SpectrumAnalyserTests.cs`

Three tests are required:

#### T-1 — Known sine wave produces energy peak in the expected bin

Synthesise a 1000 Hz sine wave at 12 kHz, exactly 2048 samples long. Feed it to
`Push`. Assert that `SpectrumReady` fires once and that the bin with the highest
magnitude corresponds to 1000 Hz.

Bin index for 1000 Hz at 12 kHz with 2048-point FFT:
`binIdx = Round(1000 / (12000 / 2048)) = Round(1000 / 5.859375) = Round(170.67) = 171`

Assert: `magnitudes[171]` is greater than all other bins (or at minimum, is the argmax
of the first 512 values). A tolerance of ±2 bins is acceptable to account for the Hann
window broadening.

```csharp
[Fact]
public void SpectrumAnalyser_SineWave_PeaksAtExpectedBin()
{
    const int    SampleRate  = 12_000;
    const int    FftSize     = SpectrumAnalyser.FftSize;
    const double FrequencyHz = 1_000.0;
    const int    ExpectedBin = 171; // Round(1000 / 5.859375)
    const int    Tolerance   = 2;

    var analyser  = new SpectrumAnalyser();
    float[]? received = null;
    analyser.SpectrumReady += m => received = m;

    var samples = new float[FftSize];
    for (var i = 0; i < FftSize; i++)
        samples[i] = MathF.Sin(2f * MathF.PI * (float)FrequencyHz * i / SampleRate);

    analyser.Push(samples);

    received.Should().NotBeNull();
    var peak = Array.IndexOf(received!, received!.Max());
    peak.Should().BeInRange(ExpectedBin - Tolerance, ExpectedBin + Tolerance,
        "1000 Hz tone should peak at bin ~171");
}
```

#### T-2 — Pure silence produces all-minimum output

Push 2048 zero samples. Assert that every `SpectrumReady` value equals −120f.

```csharp
[Fact]
public void SpectrumAnalyser_Silence_ProducesMinimumMagnitudes()
{
    var analyser  = new SpectrumAnalyser();
    float[]? received = null;
    analyser.SpectrumReady += m => received = m;

    analyser.Push(new float[SpectrumAnalyser.FftSize]);

    received.Should().NotBeNull();
    received!.Should().AllSatisfy(v => v.Should().BeApproximately(-120f, 0.001f));
}
```

#### T-3 — SpectrumReady fires exactly once per FftSize samples

Push 3 × FftSize samples. Assert that `SpectrumReady` was invoked exactly 3 times.

```csharp
[Fact]
public void SpectrumAnalyser_FiresOncePerFftSize()
{
    var analyser = new SpectrumAnalyser();
    var count    = 0;
    analyser.SpectrumReady += _ => count++;

    analyser.Push(new float[SpectrumAnalyser.FftSize * 3]);

    count.Should().Be(3);
}
```

---

## Client-Side Tasks

### C.1 — Create `web/js/spectrum.js`

New module containing the `WaterfallRenderer` class and the private `colormap` function.

```javascript
/**
 * Live scrolling waterfall renderer for the spectrum display.
 *
 * Data flow: WebSocket "spectrum" event → WaterfallRenderer.render(bins)
 *
 * Canvas layout:
 *   - X axis: frequency, left (0 Hz) to right (~3000 Hz)
 *   - Y axis: time, top (most recent) to bottom (oldest)
 *   - Pixel intensity: signal strength (0 = noise floor, 255 = peak)
 *
 * @module spectrum
 */

const MAX_FREQ_HZ = 3000;
const TICK_FREQS  = [500, 1000, 1500, 2000, 2500, 3000];

/**
 * Maps an intensity value [0, 255] to an RGB triple using a 4-stop gradient:
 *   0   → black   [0,   0,   0  ]
 *   64  → blue    [0,   0,   255]
 *   128 → cyan    [0,   255, 255]
 *   192 → yellow  [255, 255, 0  ]
 *   255 → white   [255, 255, 255]
 *
 * @param {number} v  Integer in [0, 255]
 * @returns {[number, number, number]}  [R, G, B] each in [0, 255]
 */
function colormap(v) {
  if (v < 64) {
    const t = v / 64;
    return [0, 0, Math.round(t * 255)];
  }
  if (v < 128) {
    const t = (v - 64) / 64;
    return [0, Math.round(t * 255), 255];
  }
  if (v < 192) {
    const t = (v - 128) / 64;
    return [Math.round(t * 255), 255, Math.round((1 - t) * 255)];
  }
  const t = (v - 192) / 63;
  return [255, 255, Math.round(t * 255)];
}

/**
 * Scrolling waterfall renderer backed by a raw ImageData pixel buffer.
 *
 * Designed to be instantiated once and reused across resize events.
 * Call `resize()` whenever the canvas dimensions change.
 */
export class WaterfallRenderer {
  /** @param {HTMLCanvasElement} canvas */
  constructor(canvas) {
    this._canvas    = canvas;
    this._ctx       = canvas.getContext('2d');
    this._imageData = null;
    this._resize();
  }

  /**
   * Rebuild the internal pixel buffer to match the current canvas size.
   * Must be called after any change to canvas CSS dimensions.
   */
  resize() {
    this._resize();
  }

  /**
   * Render one spectrum line at the top of the waterfall.
   * Previous content scrolls down by one physical pixel.
   *
   * @param {number[]} bins  Array of OutputBinCount integers, each in [0, 255].
   */
  render(bins) {
    if (!this._imageData) return;

    const w    = this._canvas.width;
    const h    = this._canvas.height;
    const data = this._imageData.data;

    // Scroll existing content down by one pixel.
    // copyWithin(target, start) copies [start .. data.length) to [target .. ).
    // Source and destination overlap; the spec guarantees correct memmove semantics.
    const rowBytes = w * 4;
    data.copyWithin(rowBytes, 0);

    // Write the new spectrum line into row 0.
    const binCount = bins.length;
    for (let x = 0; x < w; x++) {
      const binIdx    = Math.min(Math.floor(x * binCount / w), binCount - 1);
      const intensity = bins[binIdx];
      const [r, g, b] = colormap(intensity);
      const px        = x * 4;
      data[px]     = r;
      data[px + 1] = g;
      data[px + 2] = b;
      // Alpha channel (data[px + 3]) is pre-set to 255 in _resize().
    }

    this._ctx.putImageData(this._imageData, 0, 0);
    this._drawFrequencyAxis();
  }

  // ── Private ──────────────────────────────────────────────────────────────

  _resize() {
    const { width, height } = this._canvas.getBoundingClientRect();
    const dpr = devicePixelRatio;
    const w   = Math.max(1, Math.round(width  * dpr));
    const h   = Math.max(1, Math.round(height * dpr));

    this._canvas.width  = w;
    this._canvas.height = h;

    this._imageData = this._ctx.createImageData(w, h);

    // Fill entirely black (RGB = 0) with full opacity (A = 255).
    const data = this._imageData.data;
    for (let i = 3; i < data.length; i += 4)
      data[i] = 255;
  }

  _drawFrequencyAxis() {
    const ctx = this._ctx;
    const w   = this._canvas.width;
    const h   = this._canvas.height;
    const dpr = devicePixelRatio;

    ctx.save();
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.35)';
    ctx.fillStyle   = 'rgba(255, 255, 255, 0.55)';
    ctx.font        = `${Math.round(9 * dpr)}px ui-monospace, monospace`;
    ctx.textAlign   = 'center';
    ctx.lineWidth   = 1;

    const labelY  = h - 4 * dpr;
    const tickTop = h - 14 * dpr;

    for (const freq of TICK_FREQS) {
      const x = Math.round(freq / MAX_FREQ_HZ * w);

      // Vertical tick.
      ctx.beginPath();
      ctx.moveTo(x + 0.5, tickTop);
      ctx.lineTo(x + 0.5, h);
      ctx.stroke();

      // Frequency label: "1k", "1.5k", "2k", etc.
      const label = freq % 1000 === 0
        ? `${freq / 1000}k`
        : `${freq / 1000}`;
      ctx.fillText(label, x, labelY);
    }

    ctx.restore();
  }
}
```

---

### C.2 — Update `web/js/main.js`

Three changes are required.

#### 1 — Import `WaterfallRenderer`

Add at the top alongside the existing imports:

```javascript
import { WaterfallRenderer } from './spectrum.js';
```

#### 2 — Replace the placeholder with a live renderer

Inside the `DOMContentLoaded` listener, replace the current placeholder block:

```javascript
// REMOVE these lines:
const canvas = /** @type {HTMLCanvasElement} */ (document.getElementById('waterfall'));
paintWaterfallPlaceholder(canvas);
const observer = new ResizeObserver(() => paintWaterfallPlaceholder(canvas));
observer.observe(canvas.parentElement ?? canvas);

// REPLACE WITH:
const canvas   = /** @type {HTMLCanvasElement} */ (document.getElementById('waterfall'));
const renderer = new WaterfallRenderer(canvas);
const observer = new ResizeObserver(() => renderer.resize());
observer.observe(canvas.parentElement ?? canvas);
```

The `paintWaterfallPlaceholder` function and its two constants (`BG_COLOUR`,
`PLACEHOLDER_COLOUR`, `PLACEHOLDER_TEXT`) may be removed entirely.

#### 3 — Handle the `spectrum` WebSocket event

Add a branch to the existing event dispatch inside `connect(...)`:

```javascript
if (event.type === 'spectrum' && Array.isArray(event.payload)) {
  renderer.render(event.payload);
  return;
}
```

Place this branch **before** the `decode` branch so it is evaluated first (spectrum
events are expected at ~6 Hz; order matters for performance).

---

### C.3 — Update `web/css/app.css`

No structural changes to the waterfall panel layout are required — the existing
`#waterfall-panel` and `#waterfall` rules already set `width: 100%; height: 100%`
and `flex: 0 0 40%`. However, add a `cursor` rule so the user's pointer changes over
the spectrum display to signal it is an interactive surface (for future click-to-tune
functionality):

```css
#waterfall {
  display: block;
  width: 100%;
  height: 100%;
  cursor: crosshair;  /* ← add this line */
}
```

---

## What Is Not In Scope

- **Click-to-tune** — clicking on the waterfall to set the FT8 dial frequency. Deferred.
- **Overlay spectrum bar chart** — a live power-vs-frequency line above the waterfall. Deferred.
- **Configurable dBFS floor / gain** — user-adjustable sensitivity. Deferred.
- **50 % overlap** — would increase to ~12 fps. Not required for initial delivery.
- **Binary WebSocket frames** — JSON is sufficient at 1.6 KB/message × 6 fps per client.

---

## Reset on Pipeline Restart

`SpectrumAnalyser` is stateful (ring buffer + write pointer). When `CaptureManager`
restarts on a device change (via `configStore.OnSaved`) or after a watchdog restart,
the ring buffer may contain stale samples from the old session.

Add a `Reset()` method to `SpectrumAnalyser`:

```csharp
/// <summary>
/// Clears the ring buffer and resets the accumulation counter.
/// Call after any pipeline restart to prevent stale samples from a prior
/// capture session contaminating the first post-restart FFT window.
/// </summary>
public void Reset()
{
    Array.Clear(_ringBuffer, 0, FftSize);
    _writePos    = 0;
    _accumulated = 0;
}
```

Call `spectrumAnalyser.Reset()` wherever `audioMonitor.Reset()` and
`dataFlowMonitor.Reset()` are currently called in `Program.cs` (three locations:
`CaptureFailed` handler, `configStore.OnSaved` handler, and `restartPipeline` lambda).

---

## Build & Test Checklist

```
dotnet build -c Release          ← 0 errors, 0 warnings across all projects
dotnet test  -c Release          ← T-1, T-2, T-3 green; all existing tests still pass
```

Manual verification (task 13.4, now unblocked for spectrum):

1. Start the daemon with a configured audio device.
2. Open `http://127.0.0.1:8080`.
3. Observe that the waterfall panel scrolls — each row is a new frequency snapshot.
4. Play a known audio tone (e.g. a 1 kHz test tone from the SDR software) and confirm
   a bright vertical stripe appears at approximately 1/3 of the width from the left.
5. Remove the audio source — confirm the waterfall turns dark (noise floor only), not
   frozen.
6. Confirm frequency axis tick marks (500, 1k, 1.5k, 2k, 2.5k, 3k) are visible at
   the bottom of the panel.

---

## Commit Guidance

Three atomic commits are recommended:

**1 — DSP component and tests:**
```
feat(spectrum): add SpectrumAnalyser with Cooley-Tukey FFT and Hann window

Accumulates 12 kHz mono samples into a 2048-point ring buffer. After
every 2048 new samples, applies a Hann window, runs a radix-2 in-place
FFT, converts to dBFS, and fires SpectrumReady with 512 bins covering
0–2994 Hz. Includes Reset() for pipeline-restart hygiene.
```

**2 — Server wiring and WebSocket broadcast:**
```
feat(spectrum): wire SpectrumAnalyser into pipeline; broadcast via WebSocket

Adds SpectrumEventBus (public façade) and WebSocketHub.BroadcastSpectrum
(internal). Serialises 512-bin int[] as a "spectrum" JSON event at
~6 fps. Gates serialisation on HasClients to avoid wasted allocation
when no browser is connected. Resets analyser on all three pipeline
restart paths.
```

**3 — Waterfall renderer:**
```
feat(spectrum): replace waterfall placeholder with live scrolling display

WaterfallRenderer (spectrum.js) maintains a pre-allocated ImageData pixel
buffer; each spectrum update scrolls existing content down by one physical
pixel and writes a new top row using a 4-stop black→blue→cyan→yellow→white
colormap. Frequency axis tick marks drawn at 500 Hz intervals up to 3 kHz.
Handles resize via ResizeObserver.
```
