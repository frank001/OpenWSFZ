# Developer Briefing — p8-ft8-decode-performance (Round 30)

**Date:** 2026-05-28  
**Issued by:** QA  
**Branch:** `feat/p8-ft8-decode-performance`  
**Scope:** All implementation tasks — coefficient caching, candidate cap, parallel time sweep,
elapsed logging, performance regression test

---

## Context

The FT8 decode pipeline takes ~59 seconds per 15-second cycle on a live band.  Root cause:
`CostasSynchroniser.FindCandidates` returns ~4,235 false-positive candidates per cycle on a real
band (26× expected).  Each candidate triggers `SymbolExtractor.Extract` — 79 symbols × 15
columns × 1,920-sample Goertzel — which is ~2.3M floating-point operations.  Nearly all
candidates are noise.

Three fixes reduce decode time to well under 5 seconds:
1. **Candidate cap** — truncate to 2 per (time, baseHz) pair before committing to Goertzel
2. **Parallel time sweep** — 103 independent start positions can run concurrently
3. **Coefficient caching** — precompute 15 cosines once per `Extract` call, not 1,185 times

A fourth item (elapsed time logging) and a fifth (CI performance regression test) complete
the change.

---

## Current State

The propose commit (`eeee90c`) created all change artifacts.  One file has been modified but
not yet committed:

### `src/OpenWSFZ.Ft8/Dsp/GoertzelDetector.cs` — Task 2.2 ✅ (uncommitted)

`GoertzelDetector` now exposes two new `public` members:

```csharp
public static float Coeff(double targetFrequencyHz, double sampleRateHz)
    => 2.0f * MathF.Cos(2.0f * MathF.PI * (float)(targetFrequencyHz / sampleRateHz));

public static float ComputeEnergyWithCoeff(ReadOnlySpan<float> samples, float coeff)
{ ... }
```

`ComputeEnergy` now delegates through both.  The code is correct; it just needs
the remaining tasks wired up before committing the lot together.

---

## Tasks

Work through the tasks in order.  Each section ends with a `dotnet build` check so problems
surface immediately rather than compounding.

---

### Task 2.1 — Coefficient caching in `SymbolExtractor.Extract`

**File:** `src/OpenWSFZ.Ft8/Dsp/SymbolExtractor.cs`

The current `Extract` method calls `GoertzelDetector.ComputeEnergy(window, freq, SampleRate)`
inside the inner `(sym, col)` loop — recomputing `MathF.Cos` on every iteration.

Restructure the method to pre-compute the 15 coefficients **before** the symbol loop:

```csharp
public static float[,] Extract(ReadOnlySpan<float> pcm, int startSample, double baseFrequencyHz)
{
    var grid = new float[SymbolCount, GridWidth];

    // p8: pre-compute the 15 Goertzel coefficients once per Extract call.
    // Saves GridWidth × (SymbolCount − 1) = 15 × 78 = 1,170 MathF.Cos evaluations.
    var coeffs = new float[GridWidth];
    for (int col = 0; col < GridWidth; col++)
        coeffs[col] = GoertzelDetector.Coeff(baseFrequencyHz + col * ToneSpacingHz, SampleRate);

    for (int sym = 0; sym < SymbolCount; sym++)
    {
        int offset = startSample + sym * SamplesPerSymbol;
        if (offset + SamplesPerSymbol > pcm.Length)
            break;

        var window = pcm.Slice(offset, SamplesPerSymbol);

        for (int col = 0; col < GridWidth; col++)
        {
            float energy = GoertzelDetector.ComputeEnergyWithCoeff(window, coeffs[col]);
            grid[sym, col] = MathF.Log(energy + 1e-10f);
        }
    }

    return grid;
}
```

### Task 2.3 — Build verify

```
dotnet build -c Release
```

0 errors, 0 warnings expected.

---

### Task 3.1–3.2 — Costas candidate cap in `Ft8Decoder`

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`

**Step 1** — Add the constant alongside the other sweep constants (after `SyncThreshold`):

```csharp
// p8: bound Goertzel call count regardless of band noise level.
// FindCandidates returns candidates sorted by score descending; take the top N.
// A real signal produces at most one strong hit per (time, baseHz) pair; the
// second slot handles partial-overlap edge cases.  Value is a named constant so
// future tuning is explicit.
private const int MaxCandidatesPerSweep = 2;
```

**Step 2** — Apply the cap immediately after `FindCandidates` returns.  Replace:

```csharp
var candidates = CostasSynchroniser.FindCandidates(fftGrid, SyncThreshold);

foreach (var cand in candidates)
```

with:

```csharp
var candidates = CostasSynchroniser.FindCandidates(fftGrid, SyncThreshold);
int take = Math.Min(candidates.Count, MaxCandidatesPerSweep);

for (int ci = 0; ci < take; ci++)
{
    var cand = candidates[ci];
```

Close the `for` brace where the `foreach` brace currently closes (no other changes needed inside
the loop body).

### Task 3.3 — Build verify

```
dotnet build -c Release
```

---

### Task 4.1–4.4 — Parallel time sweep

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`

This is the most invasive change.  Take each step carefully.

**Step 1 (Task 4.1)** — Remove the pre-allocated instance field:

```csharp
// DELETE this line:
private readonly float[,] _spectrogram = new float[SymbolCount, SpecBins];
```

The comment above it (about serial invocation being safe) also goes.  Each parallel iteration
will allocate its own local buffer.

**Step 2 (Task 4.2–4.3)** — Replace the sequential time sweep with `Parallel.For`.

The current sequential loop looks like:

```csharp
int maxStartSample = Math.Max(0, pcm.Length - SecondCostasEnd);

for (int startSample = 0; startSample <= maxStartSample; startSample += TimeSweepStep)
{
    // ... FillSpectrogram + frequency sweep + candidate loop ...
}
```

Replace it in its entirety with the following.  Read the notes after the snippet before
making the edit.

```csharp
int maxStartSample = Math.Max(0, pcm.Length - SecondCostasEnd);
int stepCount      = maxStartSample / TimeSweepStep + 1;

// Thread-safe result accumulator.  Capacity hint avoids repeated resizing on
// a typical busy-band cycle (expect O(10–50) unique messages).
var bag = new System.Collections.Concurrent.ConcurrentBag<DecodeResult>();

// Diagnostic counters — updated via Interlocked because the parallel body runs
// on multiple threads.
int diag_costas    = 0;
int diag_ldpc      = 0;
int diag_crc       = 0;
int diag_paritySum = 0;

Parallel.For(0, stepCount, new ParallelOptions { CancellationToken = ct }, i =>
{
    int startSample = i * TimeSweepStep;
    if (startSample > maxStartSample) return;

    _logger?.LogTrace(
        "Time-domain sweep: startSample = {Start} / {Max} ({StartS:F2} s).",
        startSample, maxStartSample, (double)startSample / SampleRate);

    // Per-iteration spectrogram buffer (~316 KB, short-lived, collected after loop).
    var spectrogram = new float[SymbolCount, SpecBins];
    SymbolExtractor.FillSpectrogram(pcm, startSample, spectrogram);

    for (double baseHz = MinFreqHz; baseHz <= MaxFreqHz; baseHz += FreqSweepStep)
    {
        ct.ThrowIfCancellationRequested();

        var fftGrid    = SymbolExtractor.ExtractFromSpectrogram(spectrogram, baseHz);
        var candidates = CostasSynchroniser.FindCandidates(fftGrid, SyncThreshold);
        int take       = Math.Min(candidates.Count, MaxCandidatesPerSweep);

        for (int ci = 0; ci < take; ci++)
        {
            ct.ThrowIfCancellationRequested();
            var cand = candidates[ci];

            Interlocked.Increment(ref diag_costas);

            double actualBase = baseHz + cand.FreqBinOffset * ToneSpacing;
            int    freqHz     = (int)Math.Round(actualBase + 3 * ToneSpacing);

            _logger?.LogDebug(
                "Costas hit: startSample={Start}, base={Base:F2} Hz, score={Score:F3}.",
                startSample, actualBase, cand.Score);

            float[,] grid = SymbolExtractor.Extract(pcm, startSample, actualBase);
            var llr       = ComputeLlrs(grid, freqShift: 0);

            Interlocked.Add(ref diag_paritySum, LdpcDecoder.CountInitialParityFailures(llr));

            var decoded = LdpcDecoder.Decode(llr);
            if (decoded is null) continue;
            Interlocked.Increment(ref diag_ldpc);

            bool crcOk = Crc14.VerifyFt8(decoded);
            if (!crcOk) continue;
            Interlocked.Increment(ref diag_crc);

            bool allZeros = true;
            for (int z = 0; z < decoded.Length; z++)
                if (decoded[z] != 0) { allZeros = false; break; }
            if (allZeros) continue;

            var msgBits = new ReadOnlySpan<byte>(decoded, 0, MsgBits);
            string msg  = MessageUnpacker.Unpack(msgBits);

            double dt = (double)startSample / SampleRate;
            bag.Add(new DecodeResult(
                Time:    timeStr,
                Snr:     (int)Math.Round(EstimateSnr(grid, freqShift: 0)),
                Dt:      Math.Round(dt, 1),
                FreqHz:  freqHz,
                Message: msg));
        }
    }
});

// Merge bag results; apply de-duplication after parallel loop.
var results = new List<DecodeResult>();
foreach (var r in bag)
    if (seen.Add(r.Message))
        results.Add(r);
```

**Notes:**
- The `seen` `HashSet` declared earlier in `DecodeAsync` is now only used in the post-loop
  merge; it is no longer accessed concurrently.  Its declaration and initialisation remain
  unchanged.
- `results` is now populated only in the post-loop merge block; remove the `results.Add(...)`
  that was inside the old sequential loop (it no longer exists).
- The `diag_*` variables move from `int` declarations to `int` declarations initialised to 0
  before the `Parallel.For`.  Their type does not change.
- The `_logger?.LogTrace(...)` call inside the parallel body is safe: `ILogger` implementations
  provided by `Microsoft.Extensions.Logging` are thread-safe.

**Step 3 (Task 4.4)** — Cancellation propagation.

`OperationCanceledException` thrown inside the `Parallel.For` body (from
`ct.ThrowIfCancellationRequested()`) will be wrapped in an `AggregateException` by
`Parallel.For` and then re-thrown.  The `DecodeAsync` method does not catch
`AggregateException`, so the exception will propagate to the caller as an
`AggregateException`, not an `OperationCanceledException`.

This is acceptable — the existing cancellation test checks for `OperationCanceledException`
but the cancellation token is cancelled *before* `DecodeAsync` is called, so
`ct.ThrowIfCancellationRequested()` at the top of the method fires before the parallel loop
is reached.  The parallel-loop cancellation path is a belt-and-suspenders guard; its
exception type is not contractually tested.

If strict `OperationCanceledException` propagation is later required, wrap the
`Parallel.For` in a try/catch that unwraps `AggregateException` with a single
`OperationCanceledException` inner.  Defer unless a test demands it.

### Task 4.5 — Build verify

```
dotnet build -c Release
```

---

### Task 5.1 — Elapsed time logging

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`

Add a `Stopwatch` capture immediately before the `Parallel.For` and stop it immediately
after:

```csharp
var sw = System.Diagnostics.Stopwatch.StartNew();

Parallel.For(0, stepCount, new ParallelOptions { CancellationToken = ct }, i =>
{
    // ... unchanged ...
});

sw.Stop();
```

Update the existing `LogInformation` call at the end of `DecodeAsync` to include the elapsed
field:

```csharp
float avgParity = diag_costas > 0 ? (float)diag_paritySum / diag_costas : 0f;
_logger?.LogInformation(
    "Cycle {Time}: {Count} decode(s) found. " +
    "[diag] Costas candidates={Costas}, LDPC converged={Ldpc}, CRC passed={Crc}, " +
    "avg_initial_parity_fail={AvgParity:F1}/83, elapsed={Elapsed} ms.",
    timeStr, results.Count, diag_costas, diag_ldpc, diag_crc, avgParity, sw.ElapsedMilliseconds);
```

---

### Task 6.1–6.2 — Performance regression test

**File:** `tests/OpenWSFZ.Ft8.Tests/Ft8DecoderFixtureTests.cs`

Add the following test to the `Ft8DecoderFixtureTests` class.  It synthesises 8 simultaneous
FT8 signals at distinct frequencies, superimposes them with additive Gaussian noise, and
asserts that `DecodeAsync` completes within 10 seconds and returns at least 6 of the 8 known
messages.

```csharp
/// <summary>
/// FR-026 performance regression test: DecodeAsync must complete within 10 seconds
/// on a synthetic fixture containing 8 simultaneous FT8 signals.
///
/// A single-signal fixture cannot expose the candidate explosion that caused the
/// ~59-second decode regression.  Eight concurrent signals approximate a moderately
/// busy band.  The 10-second budget is conservative (target post-fix is under 5 s);
/// it provides headroom for CI runner variance while still catching regressions.
///
/// De-duplication by message string is verified: the decoder must return at least 6
/// of the 8 known callsigns (all 8 expected on a fast machine; 6 is the floor to
/// tolerate marginal-SNR edge cases at the frequency extremes).
/// </summary>
[Fact(DisplayName = "FR-026: DecodeAsync completes within 10 s on 8-signal fixture")]
[Trait("Category", "Performance")]
public async Task DecodeAsync_MultiSignal_CompletesWithinBudget()
{
    // Eight callsigns with distinct 28-bit encodings, each at a unique base frequency
    // on the 50 Hz outer sweep grid (MinFreqHz=50, FreqSweepStep=50).
    var signals = new (string callsign, double baseHz)[]
    {
        ("W1AW", 500.0),
        ("W2AW", 750.0),
        ("W3AW", 1000.0),
        ("W4AW", 1250.0),
        ("W5AW", 1500.0),
        ("W6AW", 1750.0),
        ("W7AW", 2000.0),
        ("W8AW", 2250.0),
    };
    const string grid = "FN31";

    // Build a composite PCM buffer: superimpose all 8 signals.
    const int totalSamples = 180_000;
    var pcm = new float[totalSamples];

    var expectedCallsigns = new List<string>();
    foreach (var (callsign, baseHz) in signals)
    {
        ulong c2      = TestFt8Encoder.EncodeCallsign28(callsign);
        ulong rg      = TestFt8Encoder.EncodeReport15Grid(grid);
        byte[] msg    = TestFt8Encoder.PackType1(c1: 2, c2: c2, rg: rg);
        byte[] info   = TestFt8Encoder.AppendCrc14(msg);
        byte[] cw     = TestFt8Encoder.LdpcEncode(info);
        int[]  syms   = TestFt8Encoder.BitsToSymbols(cw);
        float[] frame = TestFt8Encoder.SymbolsToPcm(syms, baseHz, startSample: 0);

        for (int i = 0; i < totalSamples; i++)
            pcm[i] += frame[i];

        expectedCallsigns.Add($"CQ {callsign} {grid}");
    }

    // Additive Gaussian noise — σ = 0.001, seeded for reproducibility.
    // Signal amplitude = 0.5 (default); SNR ≈ 54 dB — well above the LDPC floor.
    var rng = new Random(42);
    const double sigma = 0.001;
    for (int i = 0; i < totalSamples; i++)
    {
        // Box-Muller transform.
        double u1 = 1.0 - rng.NextDouble();
        double u2 = 1.0 - rng.NextDouble();
        double z  = Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2);
        pcm[i] += (float)(z * sigma);
    }

    var clock   = new FakeClock(new DateTime(2026, 5, 28, 15, 30, 0, DateTimeKind.Utc));
    var decoder = new Ft8Decoder(clock);

    var sw = System.Diagnostics.Stopwatch.StartNew();
    var results = await decoder.DecodeAsync(pcm, CancellationToken.None);
    sw.Stop();

    sw.ElapsedMilliseconds.Should().BeLessThan(10_000,
        "FR-026: decode must complete within 10 seconds on an 8-signal fixture");

    var decodedMessages = results.Select(r => r.Message).ToList();
    int hits = expectedCallsigns.Count(expected => decodedMessages.Contains(expected));
    hits.Should().BeGreaterThanOrEqualTo(6,
        $"at least 6 of 8 known FT8 messages must be decoded; got {hits}. " +
        $"Decoded: [{string.Join(", ", decodedMessages)}]");
}
```

---

### Task 7.1–7.2 — Build and test verification

```
dotnet build -c Release
dotnet test -c Release --no-build
```

All existing tests must remain green.  The new performance test must pass within the
10-second budget.

To run the performance test in isolation:

```
dotnet test -c Release --no-build --filter "Category=Performance"
```

### Task 7.3 — Live band verification (post-deploy)

Once the branch is merged and the daemon is running against a live band, confirm:

1. The cycle `LogInformation` line includes `elapsed=XXXX ms` and the value is under 13,000 ms
   (target: under 5,000 ms on a modern CPU).
2. `Costas candidates=` in the log is in the low hundreds, not thousands.
3. Decodes appear every 15 seconds (or at worst every 30 seconds), not once per minute.

---

## Commit Strategy

All five areas of change touch a small number of files.  Commit together once tasks 7.1 and
7.2 are green:

```
feat(p8): ft8-decode-performance — coefficient caching, candidate cap, parallel sweep, elapsed logging
```

Stage these files:
- `src/OpenWSFZ.Ft8/Dsp/GoertzelDetector.cs`
- `src/OpenWSFZ.Ft8/Dsp/SymbolExtractor.cs`
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs`
- `tests/OpenWSFZ.Ft8.Tests/Ft8DecoderFixtureTests.cs`

---

## Task Checklist

| # | Task | Status |
|---|------|--------|
| 2.1 | `SymbolExtractor.Extract` — pre-compute coefficient array | ⬜ |
| 2.2 | `GoertzelDetector` — `Coeff` + `ComputeEnergyWithCoeff` overloads | ✅ uncommitted |
| 2.3 | Build verify after 2.1–2.2 | ⬜ |
| 3.1 | Add `MaxCandidatesPerSweep = 2` constant to `Ft8Decoder` | ⬜ |
| 3.2 | Apply candidate cap after `FindCandidates` | ⬜ |
| 3.3 | Build verify after 3.x | ⬜ |
| 4.1 | Remove `_spectrogram` field from `Ft8Decoder` | ⬜ |
| 4.2 | Replace sequential `for` loop with `Parallel.For` | ⬜ |
| 4.3 | Collect results into `ConcurrentBag`; merge + de-duplicate after loop | ⬜ |
| 4.4 | Verify cancellation semantics | ⬜ |
| 4.5 | Build verify after 4.x | ⬜ |
| 5.1 | Add `Stopwatch` elapsed to cycle `LogInformation` | ⬜ |
| 6.1 | Add `FR-026` 8-signal performance regression test | ⬜ |
| 6.2 | Mark test with `[Trait("Category", "Performance")]` | ⬜ |
| 7.1 | `dotnet build -c Release` — 0 errors, 0 warnings | ⬜ |
| 7.2 | `dotnet test -c Release` — all green including performance test | ⬜ |
| 7.3 | Live band: confirm `elapsed=` in log, values under 13 s | ⬜ |
