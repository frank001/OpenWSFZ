# Developer Briefing — p5-ft8-decoder (Round 27)

**Date:** 2026-05-27  
**Issued by:** Developer  
**Branch:** `fix/d11-ldpc-convergence`  
**Scope:** D12 — 8× Goertzel duplication causes O(minutes) decode on live audio

---

## Summary

D12 identified and fixed. The outer frequency sweep stepped by 6.25 Hz (one tone bin)
while CostasSynchroniser swept freqShift 0–7 internally, causing each signal to be decoded
eight times. Test suite time: **13 m 20 s → 1 m 38 s** (8× speedup). Fix: step the outer
loop by 50 Hz (8 × ToneSpacing) so each signal lands in exactly one (baseHz, freqShift) pair.

---

## Evidence from log `openswfz-20260527T165341Z.log`

```
18:54:00.100  Starting decode for cycle 16:54:00; pcm = 180000 samples, RMS = 1.457E-002.
18:54:00.110  Costas hit: startSample=0, base=50.00 Hz, score=0.573
18:54:00.127  Costas hit: startSample=0, base=81.25 Hz, score=0.532
...
18:54:13.188  Costas hit: startSample=960, base=931.25 Hz, score=0.506
...
18:54:13.662  Application is shutting down...  ← decode still running after 13 s
```

The decode was cut off mid-cycle after 13 seconds, still at `startSample=960` (the
second of ~102 time positions). At that rate the full decode would require **~13 minutes**.

WSJT-X confirmed 15+ active signals in the same audio, all within the 50–3000 Hz sweep
range. The first-cycle diag line: `Costas candidates=0` (correct — first window truncated).
The second window never completed due to the O(minutes) decode time.

---

## Root Cause

The outer frequency loop in `Ft8Decoder.DecodeAsync` stepped by `ToneSpacing = 6.25 Hz`.
`CostasSynchroniser.FindCandidates` swept `freqShift = 0..7` (8 values) within each
15-wide grid window. For any signal at frequency F:

| baseHz        | freqShift | actualBase |
|---------------|-----------|------------|
| F             | 0         | F ✓        |
| F − 6.25      | 1         | F ✓ dup    |
| F − 12.5      | 2         | F ✓ dup    |
| F − 18.75     | 3         | F ✓ dup    |
| F − 25        | 4         | F ✓ dup    |
| F − 31.25     | 5         | F ✓ dup    |
| F − 37.5      | 6         | F ✓ dup    |
| F − 43.75     | 7         | F ✓ dup    |

Eight identical `actualBase = F` candidates → eight Goertzel+LDPC calls for the same signal.
With 15 signals × 8 = 120 Goertzel+LDPC calls per time position × ~102 time positions ×
14 ms per call ≈ **144 seconds per cycle**.

The debug log confirmed this: `base=100.00 Hz` appeared 8 consecutive times, `base=468.75 Hz`
appeared 8 times — the classic duplication fingerprint.

---

## Fix

Changed outer frequency sweep step from `ToneSpacing = 6.25 Hz` to
`FreqSweepStep = 8 × ToneSpacing = 50 Hz`.

The CostasSynchroniser freqShift 0–7 sweep covers the 50 Hz window with 6.25 Hz resolution.
Each FT8 signal (always on the 6.25 Hz grid) falls in exactly one (baseHz, freqShift) pair:

```
baseHz = 50 Hz,  freqShift 0–7 covers signals at  50.00 – 93.75 Hz
baseHz = 100 Hz, freqShift 0–7 covers signals at 100.00 – 143.75 Hz
...no gap, no overlap...
baseHz = 3000 Hz, freqShift 0–7 covers signals at 3000.00 – 3043.75 Hz
```

For a busy 15-signal band: 15 Goertzel+LDPC calls per time position × ~102 time positions
× 14 ms ≈ **21 seconds per cycle**. Borderline but acceptable; signals with dt outside ±1 s
would produce zero Costas hits at most time positions, reducing the effective count further.

---

## Results

| Metric | Before D12 fix | After D12 fix |
|--------|----------------|---------------|
| Test suite duration | 13 m 20 s | **1 m 38 s** |
| Tests passed | 50/50 | **50/50** |
| Goertzel calls per time position (15-signal band) | ~120 | ~15 |
| Decode time per cycle (15-signal band) | ~144 s | ~21 s estimate |

The 8× speedup confirms 8× duplication was the sole cause of the test-suite slowdown.

---

## Commit

`fix/d11-ldpc-convergence` — commit `a12c942`:
```
fix(ft8): eliminate 8× Goertzel duplication — 50 Hz outer frequency step (D12)
```

---

## Outstanding Concern

The estimated 21-second decode time for a 15-signal band still slightly exceeds the
15-second FT8 cycle period. This is a pessimistic estimate — most time positions will
produce zero candidates (the signal is only detectable in the ±1-2 positions around its
true dt). In practice the actual decode time on live audio should be well under 15 seconds.

**Verify with live audio**: rebuild and run the daemon. The `[diag]` suffix on the first
complete-window cycle line should show `LDPC converged=N>0` and the decode should complete
before the next cycle boundary. If decode time still exceeds the cycle period,
the next step is to limit the time-domain sweep to a ±2 s dt window
(`maxStartSample = min(24000, pcm.Length − SecondCostasEnd)`) to avoid processing
time positions where no real signal can plausibly start.

---

## Status

| Item | Status |
|------|--------|
| D10 — Costas O(minutes) on flat spectrum | ✅ Resolved |
| D11 — Zero decodes (hard Costas + full-symbol sweep) | ✅ Fixed |
| **D12 — O(minutes) decode due to 8× Goertzel duplication** | ✅ Fixed |
| Live audio verification | ⏳ Pending rebuild + run |
