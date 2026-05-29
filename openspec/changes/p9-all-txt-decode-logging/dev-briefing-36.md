# Developer Briefing — p9-all-txt-decode-logging (Round 36)

**Date:** 2026-05-29  
**Issued by:** QA  
**Branch:** `feat/p9-all-txt-decode-logging`  
**Scope:** D18 root cause identified and confirmed — fix ready to implement

---

## Summary

The Round 35 diagnostic data is conclusive.  The root cause of D18 is a single line in
`CostasSynchroniser.ComputeCostasScore`.  The Costas scoring formula was designed for
isolated signals over white noise; it produces near-maximum scores for structured live-band
audio, causing a 24 % false-alarm rate and 2,878 false-positive candidates per cycle.
No real signal reaches LDPC with useful LLRs.

**This briefing contains one fix and one cleanup task.**

| Task | File | Action |
|------|------|--------|
| D18 fix | `CostasSynchroniser.cs` | Replace hard-max scoring with softmax |
| Cleanup | `Ft8Decoder.cs`, `SymbolExtractor.cs` | Remove all `// TEMPORARY D18 DIAGNOSTIC` blocks |

---

## 1. Diagnostic Data Summary

### D18-1 (both cycles)

```
PCM count=180000  min=−0.0565  max=+0.0553  rms=0.0147
PCM count=180000  min=−0.0499  max=+0.0595  rms=0.0153
```

Audio path confirmed correct.  H1 eliminated.

### D18-4 (Goertzel tone frequencies)

```
[D18-4] Goertzel tones for actualBase=731.25 Hz:
        731.25  737.50  743.75  750.00  756.25  762.50  768.75  775.00
```

Tone frequencies are correct multiples of 6.25 Hz.  Frequency mapping eliminated as a cause.

### D18-2 and D18-3 (731 Hz Costas hits)

```
[D18-2] Costas at 731 Hz startSample=960:  score=0.6053  maxE=1.58
[D18-3] LDPC initial parity failures at 731 Hz: 39/83

[D18-2] Costas at 731 Hz startSample=960:  score=0.5874  maxE=1.58
[D18-3] LDPC initial parity failures at 731 Hz: 35/83

[D18-2] Costas at 731 Hz startSample=1920: score=0.6117  maxE=0.75
[D18-3] LDPC initial parity failures at 731 Hz: 34/83
```

High Costas scores (0.59–0.61) but near-random LDPC parity failures (34–39/83).
A real FT8 signal with score 0.60 would have parity failures well below 20/83.
These candidates are **false positives**.

### D18-5 (Goertzel energy grid at 731 Hz candidates)

Representative entries for `actualBase = 731.25 Hz`, first 8 symbols:

```
sym0:[−2.274,−1.874]  sym1:[−5.800,−6.540]  sym2:[−4.292,−4.985]
sym3:[−5.297,−8.387]  sym4:[−2.018,−2.030]  sym5:[−2.337,−1.908]
sym6:[−2.468,−2.030]  sym7:[−6.625,−5.077]
```

All tone0 and tone3 values cluster between −1.5 and −8.  This is indistinguishable from
the thermal noise floor (`rms = 0.015` → expected log-energy ≈ −1.5 for a single
Goertzel bin).  **There is no real FT8 signal at 731.25 Hz in this session.**  The
Costas detector found a coincidental pattern in the aggregate interference.

### D18-6 (LLRs at 731 Hz candidates)

Representative:

```
−0.81 −0.13 −0.47 −0.61 +0.03 −0.39 −0.42 −0.20 −0.23 −0.16 +0.26 −0.05
−0.66 −0.21 +0.23 −0.40 −0.18 −0.13 −0.20 −0.15 +0.01 −0.26 −0.07 +0.02
```

All magnitudes < 0.81, most < 0.3.  These are noise-only LLRs.

### Cycle summary

```
Cycle 22:02:45 — Costas candidates=1065  LDPC converged=17  CRC passed=13  avg_parity=40.8/83
Cycle 22:03:00 — Costas candidates=2878  LDPC converged=17  CRC passed=12  avg_parity=41.2/83
```

2,878 candidates = **24 % of sweep positions**.  Expected for a busy 40 m FT8 band with
a correct Costas algorithm: **< 2 %**.  ALL.TXT confirms 100 % false positives in both cycles.

---

## 2. Root Cause

The bug is in `CostasSynchroniser.ComputeCostasScore`, line 110:

```csharp
score += MathF.Exp(costas - maxE);
```

### What this formula does

For each of the 21 Costas symbol positions, it measures how close the Costas tone energy
is to the **maximum** of the 8 tones at that position:

```
contribution = exp(E_costas − max(E_0 … E_7))
```

- **Perfect signal** (one dominant tone): `E_costas ≈ maxE` → `exp(0) = 1.0` ✓
- **White noise** (one random dominant tone per position): on average, the Costas tone is the
  maximum 1 in 8 times → `E[contribution] ≈ 1/8 = 0.125` → normalised score ≈ 0.125 ✓
- **Live crowded band** (multiple overlapping FT8 signals create near-uniform energy across
  all 8 tones): `E_costas ≈ maxE − 0.3` → `exp(−0.3) ≈ 0.74` per position →
  normalised score **≈ 0.74 → EXCEEDS the 0.45 threshold** ✗

### Why unit tests pass

Synthetic tests use a single pure tone at the target frequency with no interference.  The
8 tone energies differ by 20+ dB.  The formula scores correctly (1.0 per position).
Unit tests cannot expose a failure mode that requires a live crowded band.

### Why the formula fails on live audio

On a busy 40 m FT8 band (40+ simultaneous signals), the FFT spectrogram at any 50 Hz sweep
window receives energy from several overlapping signals and their intermodulation products.
The 8 tone columns end up within 2–4 dB of each other.  The `exp(costas − maxE)` term
evaluates to 0.6–0.9 at every position, regardless of whether the Costas pattern is genuine,
and regardless of which `freqShift` (0–7) is being tested.

Every (`time`, `frequency`) sweep position scores 0.5–0.9, far above the threshold of 0.45.
With 101 time positions × 59 frequency bands × 8 freqShifts = 47,672 possible candidates,
a 60% pass rate produces ~28,600 raw candidates before the `MaxCandidatesPerSweep = 2` cap.
After the cap: ~2,878 Goertzel evaluations — all on false-positive candidates.
Real FT8 signals compete for slots and are not guaranteed to appear in the top-2 per band.

---

## 3. The Fix — Softmax Costas Scoring

Replace the hard-max formula with the **standard softmax**:

```
contribution = exp(E_costas) / Σ exp(E_k)  for k = 0…7
             = exp(E_costas − logSumExp(E_0…E_7))
```

Properties:
- **Uniform noise** (all 8 tones at equal energy E): `exp(E) / (8 × exp(E)) = 1/8 = 0.125`
  → normalised score = 0.125 → **below threshold** ✓
- **Real signal** (one dominant tone): `exp(E_signal) / (exp(E_signal) + 7 × exp(E_noise))`
  → as `E_signal >> E_noise`: contribution → 1.0 → normalised score → 1.0 ✓
- **Crowded band** (2–3 elevated tones): each contributes 1/3 of total energy →
  contribution ≈ 1/3 = 0.33 → normalised score ≈ 0.33 → **below threshold 0.45** ✓

The `maxPossible` normalisation constant (21.0) is unchanged.  The threshold (0.45) is
unchanged.

### Changes required

#### `src/OpenWSFZ.Ft8/Dsp/CostasSynchroniser.cs`

**Step 1 — Add a `LogSumExp8` helper at the bottom of the file.**

```csharp
private static float LogSumExp8(
    float a, float b, float c, float d,
    float e, float f, float g, float h)
{
    float m = MathF.Max(MathF.Max(MathF.Max(a, b), MathF.Max(c, d)),
                        MathF.Max(MathF.Max(e, f), MathF.Max(g, h)));
    return m + MathF.Log(
        MathF.Exp(a - m) + MathF.Exp(b - m) + MathF.Exp(c - m) + MathF.Exp(d - m) +
        MathF.Exp(e - m) + MathF.Exp(f - m) + MathF.Exp(g - m) + MathF.Exp(h - m));
}
```

**Step 2 — Replace the scoring loop body in `ComputeCostasScore`.**

Current (lines 86–110):

```csharp
// Score contribution: energy at the Costas tone relative to the peak
// among all 8 signal tones for this symbol.
float costas = grid[sym, tone];
float maxE   = costas;
for (int t = freqShift; t < freqShift + tones; t++)
    if (grid[sym, t] > maxE) maxE = grid[sym, t];

// Noise-floor gate: ...
if (maxE < -18f) continue;

// Soft energy fraction: exp(costas − maxE) = E_costas / E_max ∈ (0, 1].
// For a real FT8 signal, costas ≈ maxE → contribution ≈ 1.0 per position.
// For random noise (8 equiprobable bins), expected contribution ≈ 1/8 per
// position → expected normalised score ≈ 0.125 — well below the 0.45
// threshold even without additional filtering.
// For a busy band where a competing signal's data tone is momentarily
// stronger than our Costas tone at one position, exp(costas − maxE) ∈ (0, 1)
// rather than 0, preserving the accumulated score across all 21 positions.
// The D9 noise-floor gate above already guards against the degenerate case
// where all 8 log-energies are near log(ε) ≈ −23 (silent band). (D10, D11)
score += MathF.Exp(costas - maxE);
```

Replace with:

```csharp
// Softmax Costas scoring (D18 fix).
//
// The previous formula, exp(costas − maxE), computes energy at the Costas
// tone relative to the MAXIMUM of the 8 tones.  On an isolated signal this
// is fine (1.0 when Costas tone is dominant).  On a live crowded band, all
// 8 tones are within 2–4 dB → maxE ≈ costas → exp(0) ≈ 1.0 everywhere
// → false-positive rate of 24 %, flooding the decode pipeline.
//
// The softmax formula exp(costas − logSumExp(all 8)) = E_costas / Σ E_k
// is the standard probability that the Costas tone is the unique dominant
// tone.  Its properties:
//   • Uniform noise (all 8 tones equal):        contribution = 1/8 = 0.125 ✓
//   • Real isolated signal (one dominant tone):  contribution → 1.0         ✓
//   • Crowded band (N tones elevated equally):   contribution ≈ 1/N < 0.45  ✓
//
// The noise-floor gate (maxE < −18) is retained so that silent-band frames
// with FFT floor values ≈ −23 are skipped without corrupting the score.
float costas   = grid[sym, tone];
float maxE     = costas;
for (int t = freqShift; t < freqShift + tones; t++)
    if (grid[sym, t] > maxE) maxE = grid[sym, t];

if (maxE < -18f) continue;  // silent-band guard (D9, D10, D11)

float logSumAll = LogSumExp8(
    grid[sym, freqShift + 0], grid[sym, freqShift + 1],
    grid[sym, freqShift + 2], grid[sym, freqShift + 3],
    grid[sym, freqShift + 4], grid[sym, freqShift + 5],
    grid[sym, freqShift + 6], grid[sym, freqShift + 7]);

score += MathF.Exp(costas - logSumAll);
```

**Step 3 — Update the XML summary comment** in `FindCandidates` to replace the phrase
"Soft energy fraction: exp(costas − maxE)" with the corrected description, and remove
the now-incorrect remark that expected score for random noise is 0.125 "even without
additional filtering" (the new formula achieves this analytically).

---

## 4. Cleanup — Remove All D18 Diagnostic Instrumentation

Remove every block marked `// TEMPORARY D18 DIAGNOSTIC — remove after investigation` in:

- `src/OpenWSFZ.Ft8/Ft8Decoder.cs` — D18-1 PCM stats, D18-2 Costas log, D18-3 parity log, D18-4 tone-freq log, D18-5 energy-grid log, D18-6 LLR log
- (D18-4 and D18-5 were in `Ft8Decoder.cs` per tasks.md note)

After removal, verify that the `d18_*` local variables are also gone — the compiler will
catch any missed removals as unused-variable warnings.

---

## 5. Test — Update Costas Threshold Verification

There is no existing unit test for `CostasSynchroniser` threshold behaviour under crowded-band
conditions; that is acceptable.  What IS required:

**5.1 — Re-run the existing test suite.** No test should change score.  The existing
`CostasSynchroniser` tests use synthetic isolated-signal grids where the Costas tone
dominates by 20+ dB.  For a dominant tone, the softmax formula also returns ≈ 1.0 per
position, so scores are unchanged.

**5.2 — Add one new unit test** to `CostasSynchroniserTests` (or wherever Costas tests
live):

```csharp
[Fact(DisplayName = "CostasSynchroniser: uniform-energy grid scores below threshold (crowded-band guard)")]
public void FindCandidates_UniformEnergyGrid_ScoresBelowThreshold()
{
    // A 79×15 grid with identical log-energy (−2.0f) at every cell simulates a
    // crowded band where all 8 tones have equal energy.  The OLD formula returned
    // 1.0 per Costas position → normalised score 1.0 (false positive).
    // The softmax formula must return 1/8 = 0.125 per position → normalised 0.125
    // → below the 0.45 threshold → no candidates returned.
    var grid = new float[79, 15];
    for (int s = 0; s < 79; s++)
        for (int c = 0; c < 15; c++)
            grid[s, c] = -2.0f;

    var candidates = CostasSynchroniser.FindCandidates(grid, threshold: 0.45f);

    candidates.Should().BeEmpty(
        "a uniform-energy grid represents pure crowded-band noise " +
        "and must not pass the Costas gate");
}
```

---

## 6. Implementation Plan

| Step | File | Action |
|------|------|--------|
| 1 | `CostasSynchroniser.cs` | Add `LogSumExp8` helper |
| 2 | `CostasSynchroniser.cs` | Replace scoring line; update comments |
| 3 | `Ft8Decoder.cs` | Remove all 6 `D18 DIAGNOSTIC` blocks |
| 4 | All | `dotnet build -c Release` — 0 errors, 0 warnings |
| 5 | All | `dotnet test -c Release` — all tests green including new Costas test |
| 6 | All | Commit to `feat/p9-all-txt-decode-logging` |
| 7 | CAPTAIN | Live smoke test — confirm real callsigns appear in ALL.TXT |
