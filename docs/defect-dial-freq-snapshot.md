# Defect: Dial Frequency Mislabeling at Band-Change Boundaries

**Raised by:** QA  
**Date:** 2026-06-02  
**Severity:** Medium — silent data corruption (wrong frequency in ALL.TXT and WebSocket decode events; no crash, no error log)  
**Branch:** `feat/p16-cat-control`

---

## Summary

When the operator changes bands during a 15-second FT8 decode window, the dial frequency
written to `ALL.TXT` (and broadcast via WebSocket) reflects the **new band** even though the
audio — and therefore the decoded signals — belongs to the **old band**.

If the frequency has changed during the window the cycle must be **discarded entirely**.
A decode whose audio was split across two bands cannot be labeled with either frequency
without lying; it is less harmful to drop it than to log it with wrong metadata.

---

## Evidence

Session log `openswfz-20260602T202704Z.log` + `ALL.TXT` from the same run.

Cycle `202730` is labeled **3.573 MHz (80 m)**. Two signals appear in it with
audio-frequency offsets (DF) that are physically identical to their readings from the
preceding **7.074 MHz (40 m)** cycle `202700`:

| Signal | Cycle | Labeled freq | DT | DF |
|---|---|---|---|---|
| `VJ2L Q9JBX JO90` | 202700 | 7.074 MHz | 0.9 | **2794** |
| `VJ2L Q9JBX JO90` | 202730 | 3.573 MHz | 0.9 | **2794** |
| `Q3WST Q5ROR JN78` | 202700 | 7.074 MHz | 0.8 | 653 |
| `Q3WST Q5ROR JN78` | 202730 | 3.573 MHz | 0.8 | **650** |

If cycle `202730` were genuine 80 m audio the DF values would be unrelated to those from
40 m. Identical DT and DF conclusively identifies these as 40 m signals decoded from 40 m
audio that was mislabeled as 80 m.

---

## Root Cause

`AllTxtWriter.AppendAsync` reads `_catState?.DialFrequencyMHz` at the moment it is called —
**after** 15 seconds of audio capture and a decode pass. If a band change occurred during
the window, `CatState` already holds the new frequency by the time the write happens.

```csharp
// AllTxtWriter.cs — line 84
// BUG: reads live CatState ~15 s after the window started accumulating.
double dialMhz = _catState?.DialFrequencyMHz ?? config.DialFrequencyMHz;
```

The frequency that should be associated with a window is the one that was current **when
`CycleFramer` began accumulating that window**, not when `AllTxtWriter` flushed it.

---

## Required Changes

### 1. Carry a frequency snapshot through the decode channel

**`src/OpenWSFZ.Ft8/CycleFramer.cs`**

Add an optional `Func<double?>` constructor parameter. Call it at the two points where a
new window begins accumulating: at startup and immediately after each emission.

```csharp
// Constructor — add optional provider
public CycleFramer(
    ChannelReader<float[]>  source,
    IClock                  clock,
    ILogger<CycleFramer>?   logger           = null,
    Func<double?>?          dialFreqProvider = null)
{
    _source           = source;
    _clock            = clock;
    _logger           = logger;
    _dialFreqProvider = dialFreqProvider;
}

private readonly Func<double?>? _dialFreqProvider;
```

Change the output channel signature to carry the snapshot:

```csharp
// RunAsync signature change
public async Task RunAsync(
    ChannelWriter<(float[] Pcm, DateTime CycleStart, double? DialFrequencyMHz)> output,
    CancellationToken ct)
```

Inside `RunAsync`, snapshot the frequency at every window start:

```csharp
// At startup — snapshot before entering the read loop
DateTime cycleStart     = AlignToCycleStart(startUtc);
double?  windowDialFreq = _dialFreqProvider?.Invoke();

// After each emission — snapshot for the next window
if (filled == SamplesPerCycle)
{
    output.TryWrite((window, cycleStart, windowDialFreq));

    window         = new float[SamplesPerCycle];
    filled         = 0;
    cycleStart     = cycleStart.AddSeconds(CycleDurationSecs);
    windowDialFreq = _dialFreqProvider?.Invoke();   // ← snapshot at window-open time
}
```

---

### 2. Update the channel type in `Program.cs`

**`src/OpenWSFZ.Daemon/Program.cs`**

Change the channel declaration:

```csharp
// Before
var framerOutput = Channel.CreateBounded<(float[] Pcm, DateTime CycleStart)>(...);

// After
var framerOutput = Channel.CreateBounded<(float[] Pcm, DateTime CycleStart, double? DialFrequencyMHz)>(...);
```

Wire the frequency provider when constructing `CycleFramer`:

```csharp
var cycleFramer = new CycleFramer(
    captureManager.Samples,
    clock,
    loggerFactory.CreateLogger<CycleFramer>(),
    dialFreqProvider: () => catState.DialFrequencyMHz);   // ← new
```

In the decode pump, **discard the cycle if the frequency changed** during the window:

```csharp
await foreach (var (pcmWindow, cycleStart, windowDialFreq) in
    framerOutput.Reader.ReadAllAsync(stoppingToken))
{
    try
    {
        // Snapshot the frequency again immediately before decoding.
        var currentDialFreq = catState.DialFrequencyMHz;

        // If the frequency changed during the window, the audio spans two bands.
        // Discard: a mislabeled decode is worse than no decode.
        if (windowDialFreq != currentDialFreq)
        {
            startupLogger.LogInformation(
                "Cycle {CycleStart:HH:mm:ss}: discarded — dial frequency changed " +
                "from {Before} to {After} MHz during capture window.",
                cycleStart,
                windowDialFreq?.ToString("F3") ?? "unknown",
                currentDialFreq?.ToString("F3") ?? "unknown");
            continue;
        }

        var dialFreq = windowDialFreq ?? configStore.Current.DecodeLog?.DialFrequencyMHz ?? 0.0;
        var results  = await ft8Decoder.DecodeAsync(pcmWindow, cycleStart);
        decodeEventBus.Publish(results);
        await allTxtWriter.AppendAsync(cycleStart, dialFreq, results);
    }
    catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
    {
        break;
    }
    catch (Exception ex)
    {
        startupLogger.LogError(ex, "Decode error: {Message}", ex.Message);
    }
}
```

> **Comparison note:** `double?` equality is exact-match. Because both snapshots come from
> `CatState.DialFrequencyMHz` — which is set by a single CAT poll writing one `double`
> value — they will be bitwise-equal if the frequency did not change, and visibly different
> if any poll fired a new value. No epsilon comparison is needed here.

---

### 3. Remove live `_catState` read from `AllTxtWriter`

**`src/OpenWSFZ.Daemon/AllTxtWriter.cs`**

The caller (the decode pump in `Program.cs`) now holds the correct snapshotted frequency
and passes it in. `AllTxtWriter` no longer needs to know about `ICatState` at all.

Change the `AppendAsync` signature:

```csharp
// Before
public async Task AppendAsync(DateTime cycleUtc, IReadOnlyList<DecodeResult> results)

// After
public async Task AppendAsync(DateTime cycleUtc, double dialMhz, IReadOnlyList<DecodeResult> results)
```

Remove the live read inside the method:

```csharp
// Remove entirely:
double dialMhz = _catState?.DialFrequencyMHz ?? config.DialFrequencyMHz;
```

The `_catState` field and the `ICatState? catState` constructor parameter can be removed.
The `configStore` fallback is now handled by the caller.

---

### 4. Update `AllTxtWriterTests`

**`tests/OpenWSFZ.Daemon.Tests/AllTxtWriterTests.cs`**

All calls to `AppendAsync` gain a `dialMhz` argument. Existing tests pass the value they
were previously configuring via mock `ICatState` — pass it directly instead.

Add a test that verifies `AppendAsync` uses the `dialMhz` parameter and does **not** read
from any injected state:

```csharp
[Fact(DisplayName = "P16-Cat: AppendAsync uses caller-supplied dialMhz, not live state")]
public async Task AppendAsync_UsesSuppliedDialMhz()
{
    // If AppendAsync still read from ICatState this test would need a mock;
    // the absence of any ICatState parameter proves it cannot.
    var results = new[] { new DecodeResult("20:27:30", snr: 5, dt: 0.9, freqHz: 1200, message: "CQ TEST") };
    var writer  = MakeWriter(enabled: true, path: _tempFile);

    await writer.AppendAsync(DateTime.UtcNow, dialMhz: 14.074, results);

    var lines = await File.ReadAllLinesAsync(_tempFile);
    lines[0].Should().Contain("14.074");
}
```

Add a test that verifies a changed-frequency cycle is discarded in the decode pump. This
is an integration concern; a unit test on `AllTxtWriter` alone cannot cover the discard
logic. Add it to `CatPollingServiceTests` or a new `DecodePumpTests` fixture if one is
created.

---

### 5. Update `CycleFramerTests`

**`tests/OpenWSFZ.Ft8.Tests/CycleFramerTests.cs`** (or equivalent)

Add tests covering the new `dialFreqProvider` parameter:

- Provider is `null` → `DialFrequencyMHz` in emitted tuple is `null`.
- Provider returns a value → emitted tuple carries that value.
- Provider is called at window-open time, not window-close time (verify with a provider
  whose return value changes between window-open and the end of accumulation).

---

## Acceptance Criteria

- [ ] `ALL.TXT` entries for a cycle always carry the frequency that was live at the
      **start** of that cycle's audio capture.
- [ ] When the operator changes bands mid-cycle, the affected cycle is **not written** to
      `ALL.TXT` and is **not broadcast** via WebSocket; an `INF` log line explains the
      discard.
- [ ] The cycle immediately before the band change and the cycle immediately after are
      unaffected — they decode and log normally.
- [ ] All existing tests pass; new tests for the provider parameter and the discard path
      are green.
- [ ] Manual verification: change bands at mid-cycle; confirm the transition cycle is
      absent from `ALL.TXT` and the surrounding cycles carry correct frequencies.
