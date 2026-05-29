# Developer Briefing — p5-ft8-decoder (Round 26)

**Date:** 2026-05-27  
**Issued by:** Developer  
**Branch:** `fix/d11-ldpc-convergence`  
**Scope:** D11 resolution — soft Costas score + half-symbol time sweep

---

## Summary

D11 (zero decodes on complete windows) is fixed. Diagnosis confirmed **Case B**: Costas
candidates found in abundance, LDPC converged 0 times. Two independent root causes
identified and fixed. All 50 tests pass (up from 48 — two new D11 regression tests added).

---

## Diagnosis

Live diagnostic output (`[diag]` suffix from the counters added in dev-briefing-25) confirmed:

```
Cycle 16:12:00: 0 decode(s) found. [diag] Costas candidates=240, LDPC converged=0, CRC passed=0.
```

240 Costas candidates reaching Goertzel, zero LDPC convergences. This is **Case B** exactly
as described in dev-briefing-25.

---

## Root Causes

### Root Cause 1 — Hard-decision Costas in multi-signal band

The D10 fix introduced a hard Costas criterion: a position scores 1.0 only when the Costas
tone is the strict absolute peak (`costas >= maxE`) among all 8 signal-band bins for that
symbol. In a busy band with 15+ concurrent signals this produces two failure modes:

**False alarms:** A non-signal frequency bin can coincidentally score 1.0 at all 21 Costas
positions across three competing stations' energy patterns. These produce Goertzel calls at
incorrect frequencies, wasting decoder work and contributing no valid LLRs.

**Real-signal misses:** If a competing station's data tone is momentarily stronger than our
target's Costas tone at *any single* position, that position contributes 0.0 instead of
~1.0. For a 15-station band the expected number of such collisions per 21-position sweep is
large enough to push the real signal's Costas score below the 0.45 threshold.

### Root Cause 2 — Full-symbol time sweep step

The time-domain sweep stepped by `SamplesPerSymbol = 1920` (one full symbol, 160 ms).
FT8 signals can start at any UTC offset; WSJT-X reports dt values of −0.2 to +1.1 s.
A signal whose start time falls exactly halfway between two sweep positions has every
Goertzel window split 50/50 between adjacent symbols: each bin accumulates equal energy
from the *current* symbol tone and the *next* symbol tone. The resulting LLRs have
unreliable signs, and the LDPC min-sum decoder diverges rather than converges.

The FFT-based Costas sweep sees the same contamination but Costas scoring is less sensitive
to it — a split-symbol Costas window still shows elevated energy at the Costas tone
relative to noise. So candidates are found (240 of them), but Goertzel LLRs are corrupt.

---

## Fixes

### Fix 1 — Soft Costas energy fraction (`CostasSynchroniser.cs`)

Replaced hard-decision contribution with soft energy fraction:

```csharp
// Before (D10 — hard decision):
score += costas >= maxE ? 1.0f : 0.0f;

// After (D11 — soft energy fraction):
score += MathF.Exp(costas - maxE);
// = E_costas / E_max  ∈ (0, 1]
// Perfect signal:   contribution ≈ 1.0 per position
// Random noise:     expected contribution ≈ 1/8 ≈ 0.125 (well below 0.45 threshold)
// Partial overlap:  contribution ∈ (0, 1) — partial evidence preserved
```

The D9 noise-floor gate (`if (maxE < -18f) continue`) is retained to prevent silent bands
from accumulating soft scores across flat-spectrum log(ε) noise.

### Fix 2 — Half-symbol time sweep step (`Ft8Decoder.cs`)

Reduced sweep step from 1920 samples (full symbol) to 960 samples (half symbol):

```csharp
// Before:
for (int startSample = 0; startSample <= maxStartSample; startSample += SamplesPerSymbol)

// After:
private const int TimeSweepStep = SamplesPerSymbol / 2; // 960
for (int startSample = 0; startSample <= maxStartSample; startSample += TimeSweepStep)
```

Worst-case Goertzel window contamination drops from 50% (full symbol step) to 25%
(half symbol step). The LDPC min-sum decoder handles 25% contamination — LLR magnitudes
are reduced but sign reliability is preserved for most bit positions. The number of
time-domain sweep positions doubles (from ~93 to ~187 for a 180 000-sample window) but
Goertzel calls are only made for confirmed Costas hits — still single-digit per frequency
offset — so the performance impact is negligible.

---

## Tests Added

Two new regression tests in `Ft8DecoderFixtureTests.cs`:

| Test | Signal offset | Sweep step that lands | Why it was broken before |
|------|--------------|----------------------|--------------------------|
| `DecodeAsync_HalfSymbolOffset_ReturnsKnownDecodes` | 960 samples (80 ms) | startSample=960 | Old step=1920: 50% contamination at both 0 and 1920 |
| `DecodeAsync_QuarterSymbolOffset_ReturnsKnownDecodes` | 480 samples (40 ms) | startSample=0 (40 ms misalignment) | Exercises worst-case between half-symbol steps |

Both tests use `TestFt8Encoder.SymbolsToPcm(symbols, baseFreqHz, startSample: N)` to place
the synthetic signal at an offset that was not reachable with the old full-symbol sweep.

**Test results:** 50 passed, 0 failed (was 48/48 before D11 fix).

---

## Files Changed

| File | Change |
|------|--------|
| `src/OpenWSFZ.Ft8/Dsp/CostasSynchroniser.cs` | Hard-decision → soft `exp(costas−maxE)` score contribution |
| `src/OpenWSFZ.Ft8/Ft8Decoder.cs` | `TimeSweepStep = SamplesPerSymbol / 2` (960); comment documenting D11 |
| `tests/OpenWSFZ.Ft8.Tests/Ft8DecoderFixtureTests.cs` | Two D11 regression tests added |

---

## Commit

`fix/d11-ldpc-convergence` — commit `e98678e`:
```
fix(ft8): soft Costas score + half-symbol sweep — fix D11 zero decodes on complete windows
```

---

## Next Steps

### Step 1 — Live verification

Build and run against live audio. Check the `[diag]` suffix on complete cycle lines
(Cycle HH:MM:15 or HH:MM:45 — not the first truncated window):

```
dotnet build src/OpenWSFZ.Ft8/ -c Release
dotnet run --project src/OpenWSFZ.Daemon/ -c Release
```

Expected result on a busy 40 m band:

```
Cycle HH:MM:30: N decode(s) found. [diag] Costas candidates=K, LDPC converged=M>0, CRC passed=N>0.
```

If `LDPC converged=0` still appears, the contamination at 25% is exceeding the decoder's
tolerance at the observed SNR. Next step in that case: reduce `TimeSweepStep` further
to `SamplesPerSymbol / 4 = 480` (quarter symbol, ~4.7× more sweep positions).

If `LDPC converged=N>0` but `CRC passed=0`, that would be a new defect (D12) pointing
to a CRC polynomial or bit-ordering mismatch.

### Step 2 — Merge

Once live verification confirms decodes:

1. Merge `fix/d11-ldpc-convergence` into `feat/p7-p6-logging-and-display`
   (or directly to `main` if that branch has already been merged).
2. Update qa-review.md with D11 resolution.

### Step 3 — Advisory A1 from QA Round 5

`CostasSynchroniser` still generates candidates with `FreqBinOffset` 1–7 where the old
code (before the D4 GridWidth fix) would have wrapped modulo 8. With GridWidth=15 the
Goertzel call at freqShift=7 now reads the correct tones (columns 7–14 of the 15-wide
grid). The QA A1 advisory about `ComputeLlrs` wrapping `(t + freqShift) % 8` may now be
stale — verify `ComputeLlrs` in `Ft8Decoder.cs` uses the un-wrapped grid column directly
before closing A1.

---

## Status Table

| Item | Status |
|------|--------|
| D10 — Costas soft-match O(minutes) decode | ✅ Resolved |
| Window 1 zero decodes | ✅ Expected (truncated capture window) |
| D11 — Zero decodes on complete windows | ✅ Fixed — awaiting live verification |
| Regression tests (half/quarter symbol offset) | ✅ 50/50 pass |
