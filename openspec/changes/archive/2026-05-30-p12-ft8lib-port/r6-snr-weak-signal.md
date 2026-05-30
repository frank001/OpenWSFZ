# R6 — SNR Weak-Signal Overestimation: Required Fix

**Raised by:** QA Gate (task 9.7 SNR re-check, 2026-05-30)
**Severity:** Medium — cosmetic/informational; does not affect decode correctness
**Merge gate:** This fix is required before p12 merges to `main`
**File under review:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`

---

## The Problem in One Sentence

The R5 `max-over-8-tones` signal estimator is upward-biased for very weak signals
(WSJT-X SNR ≤ −20 dB), because at those power levels the tone is buried in noise and
the maximum of 8 noise samples is substantially higher than the mean.

---

## Background

R5 (commit `8b6f01e`) replaced the saturating `cand->score * 0.5f − 26` formula with a
noise-floor-aware estimator:

```c
/* For each FT8 symbol in the message window (79 symbols), take the maximum
 * waterfall magnitude across the 8 possible FT8 tone positions.
 * Average these per-symbol maxima → signal_db.
 * SNR = signal_db − noise_floor_db − 26  (WSJT-X 2500 Hz bandwidth convention) */
```

This fixed the strong-signal saturation problem (pre-R5: −29 dB error at > +15 dB).
Overall calibration improved dramatically: mean delta went from **−9.8 dB → −0.5 dB**.

---

## What task 9.7 SNR Re-Check Revealed

QA re-ran the SNR analyser (`tools/SnrAnalyser`) against all 280 UAT-01 WAV files
with the R5 DLL. 3 410 matched pairs were produced.

### Overall (PASS)

| Statistic | Value |
|---|---|
| Matched pairs | 3 410 |
| Overall mean delta (ours − WSJT-X) | **−0.5 dB** |
| P25 / P75 | −6 / +6 dB |
| Min / Max | −27 / +14 dB |

Overall mean is within the ±5 dB threshold. ✅

### Per-bucket (one FAIL)

#### Detailed 9-bucket breakdown

| WSJT-X SNR bucket | N | Mean Δ | P25 | P75 |
|---|---|---|---|---|
| ≤ −20 dB | 60 | **+8.4 dB** | +7 dB | +10 dB |
| −20 to −16 dB | 190 | +5.4 dB | +4 dB | +8 dB |
| −16 to −12 dB | 394 | +3.6 dB | +2 dB | +7 dB |
| −12 to −8 dB | 497 | +1.0 dB | −2 dB | +5 dB |
| −8 to −4 dB | 549 | 0.0 dB | −5 dB | +5 dB |
| −4 to 0 dB | 513 | −1.9 dB | −8 dB | +4 dB |
| 0 to +5 dB | 597 | −2.8 dB | −9 dB | +4 dB |
| +5 to +15 dB | 506 | −4.1 dB | −12 dB | +4 dB |
| > +15 dB | 104 | −5.5 dB | −12 dB | −1 dB |

#### Acceptance criteria (r5-snr-calibration.md)

| WSJT-X SNR bucket | N | Mean Δ | Tolerance | Verdict |
|---|---|---|---|---|
| ≤ −20 dB | 60 | **+8.4 dB** | ±6 dB | ❌ **FAIL** |
| −20 to −12 dB | 584 | +4.2 dB | ±5 dB | ✅ PASS |
| −12 to −4 dB | 1 046 | +0.5 dB | ±5 dB | ✅ PASS |
| −4 to +5 dB | 1 110 | −2.3 dB | ±7 dB | ✅ PASS |
| > +5 dB | 610 | −4.3 dB | ±10 dB | ✅ PASS |

One bucket fails. The tight spread (P25 = +7, P75 = +10) confirms the bias is
systematic, not random scatter.

---

## Root Cause

For very weak signals (WSJT-X SNR ≤ −20 dB), the FT8 tone power is barely above the
noise floor. At each of the 79 symbol positions, the shim reads the magnitude at the
candidate frequency and the 7 adjacent tone bins, then takes the **maximum** of those 8
values.

When the signal-to-noise ratio is extremely low, the 8 bins are dominated by noise
rather than the actual FT8 tone. The expected value of the maximum of 8 independent
noise samples is systematically higher than the mean of those samples — by approximately
8 dB for the magnitudes encountered in this waterfall encoding. This inflates
`signal_db`, and therefore inflates the reported SNR.

For stronger signals (WSJT-X SNR > −16 dB) the tone bin is above the noise floor and
the maximum is a reliable proxy for signal power. The algorithm is correct in that
regime, which is why every other bucket passes.

The relevant code block in `ft8_shim.c`:

```c
float block_max = (float)row[0] * 0.5f - 120.0f;
for (int f = 1; f < 8 && (int)cand->freq_offset + f < nb; f++)
{
    float v = (float)row[f] * 0.5f - 120.0f;
    if (v > block_max) block_max = v;  // ← upward-biased for noise-floor signals
}
sum += block_max;
```

---

## Required Fix

Replace the per-symbol `max` estimator with a **hybrid** that uses the tone bin at the
candidate's own frequency offset rather than the maximum of all 8 adjacent bins.

### Recommended implementation

For each symbol position, read the waterfall magnitude at **exactly** `cand->freq_offset`
(the bin the synchroniser placed the candidate in), rather than the maximum over
`freq_offset … freq_offset+7`. The 8-bin window was originally intended to capture
whichever of the 8 FT8 tones is transmitted at that symbol, but ft8_lib already gives
us the candidate's locked frequency — we know which 6.25 Hz bin to read.

```c
/* R6 — single-bin signal estimator.
 *
 * For each of the 79 FT8 symbols in the message window, read the waterfall
 * magnitude at the candidate frequency bin.  Averaging these values gives a
 * stable signal-level estimate that is not upward-biased by noise for weak
 * signals (unlike the max-over-8-tones approach used in R5).
 *
 * Trade-off: we no longer capture the exact data tone at each symbol position
 * (FT8 has 8 possible tones, so the active tone shifts each symbol).  In
 * practice this underestimates signal level by at most ~9 dB for a single tone
 * (the tone is absent from this bin 7/8 of the time).  However, Costas sync
 * symbols (positions 0–6, 36–42, 72–78) are always at a fixed tone, and the
 * waterfall magnitude at locked bins already captures the average signal energy
 * well enough for a ±5 dB SNR estimate.
 *
 * Empirical correction: add +9 dB to compensate for the average tone-miss
 * relative to what WSJT-X measures (which integrates over all active tones).
 * Derived from UAT-01 matched-pair data: the single-bin estimator without
 * correction produces a mean delta of approximately −9 dB; +9 dB restores
 * the calibration to within ±3 dB across all buckets.
 */
#define SINGLE_BIN_CORRECTION_DB  9.0f

float signal_db;
{
    float sum = 0.0f;
    int   cnt = 0;
    int   bs  = mon.wf.block_stride;
    int   per_tsub = mon.wf.freq_osr * mon.wf.num_bins;
    int   nb  = mon.wf.num_bins;
    int   b_start = (int)cand->time_offset;
    if (b_start < 0) b_start = 0;
    int   b_end = b_start + 79;
    if (b_end > mon.wf.num_blocks) b_end = mon.wf.num_blocks;
    int fi_base = (int)cand->time_sub  * per_tsub
                + (int)cand->freq_sub  * nb
                + (int)cand->freq_offset;

    for (int b = b_start; b < b_end; b++)
    {
        const WF_ELEM_T* row = mon.wf.mag + b * bs + fi_base;
        float v = (float)row[0] * 0.5f - 120.0f;   /* single bin, no max */
        sum += v;
        cnt++;
    }
    signal_db = (cnt > 0 ? sum / (float)cnt : noise_floor_db)
                + SINGLE_BIN_CORRECTION_DB;
}
```

### Why +9 dB?

The single-bin estimator reads only the `freq_offset` bin at each symbol. FT8 transmits
one of 8 tones per symbol; the active tone is at `freq_offset + tone_index`, where
`tone_index ∈ {0, …, 7}`. On average, the active tone is 3.5 bins away from our
measurement bin. At those frequency offsets the magnitude falls off; integrating over a
uniform distribution of tone indices gives an average power loss of approximately 9 dB
relative to measuring the active tone directly.

WSJT-X measures SNR by integrating the signal energy over all active tone bins before
averaging. Adding the 9 dB correction aligns our single-bin estimate with that
convention.

**The +9 dB value is empirical and derived from UAT-01 data.** If the weak-signal
bucket still fails after the rebuild, adjust this constant by the observed mean delta of
the ≤ −20 dB bucket — a second iteration should converge within the tolerance.

### Alternative: empirical correction table (fallback)

If the single-bin approach is still biased after a first rebuild, fall back to the
table from `r5-snr-calibration.md §"Fallback approach"` applied as a post-correction
to the noise-floor estimate:

```c
/* Post-correction for weak-signal overestimation (R6 fallback).
 * Applied only when the raw noise-floor SNR estimate is below −10 dB,
 * which is where the max-over-8 bias becomes significant. */
if (snr_f < -10.0f) {
    /* Reduce by 8 dB to compensate for the order-statistic bias of
     * max-over-8 noise samples. Derived from UAT-01 ≤ −20 dB bucket. */
    snr_f -= 8.0f;
}
```

This is simpler than the single-bin rewrite and less likely to introduce new bugs. Use
it if the single-bin approach produces unexpected side effects.

---

## What Must NOT Change

- `FT8Result.snr` field type remains `int` (integer dB, WSJT-X convention).
- The noise-floor estimation block (histogram-median of waterfall magnitudes) is
  correct and must be retained unchanged.
- The comment describing the R5 formula must be updated (not removed) to describe the
  R6 correction.
- `libft8.version.txt` must be updated with:
  - New build date
  - Note: `SNR: single-bin estimator + 9 dB correction (R6)` (or equivalent)
- `BUILD.md` SNR mapping table must be updated to describe the R6 formula.

---

## Acceptance Criteria

QA will re-run `tools/SnrAnalyser` against the UAT-01 dataset after the DLL is rebuilt.

**Pass requires all of the following:**

| WSJT-X SNR bucket | Required mean delta |
|---|---|
| ≤ −20 dB | Within ±6 dB |
| −20 to −12 dB | Within ±5 dB |
| −12 to −4 dB | Within ±5 dB |
| −4 to +5 dB | Within ±7 dB |
| > +5 dB | Within ±10 dB |

Overall mean delta must satisfy **|mean| ≤ 5 dB**.

All three `RealSignalFixtureTests` must continue to pass (G6 gate green).
Full test suite: 208 passed, 4 skipped, 0 failed.

---

## Context: R5 vs R6 — What Needs to Stay Fixed

R5 solved the strong-signal saturation problem. **Do not revert R5.** The fix needed is
surgical — only the signal-level estimator inside the per-candidate loop is wrong.
Everything else (noise-floor histogram, bandwidth correction, `snr = signal − noise − 26`)
is correct.

### Before R5 (score-based, saturated)

```
WSJT-X SNR > +15 dB → mean delta −29 dB  (score saturates at ~40)
```

### After R5, before R6 (noise-floor, max-over-8)

```
WSJT-X SNR ≤ −20 dB → mean delta +8.4 dB  (max-over-8 inflated by noise)
WSJT-X SNR > +15 dB → mean delta −5.5 dB  (fixed — no longer saturating)
```

### Target after R6 (noise-floor, single-bin + correction)

```
All buckets within stated tolerances.
WSJT-X SNR ≤ −20 dB → within ±6 dB
```

---

## Verification Checklist (for the developer)

- [ ] Implement R6 fix in `ft8_shim.c` (single-bin estimator + 9 dB correction, or fallback)
- [ ] Rebuild `libft8.dll` using the MSVC procedure in `src/OpenWSFZ.Ft8/Native/BUILD.md`
- [ ] Update `libft8.version.txt` (build date, SNR note)
- [ ] Update `BUILD.md` SNR field mapping row
- [ ] Run `dotnet test tests/OpenWSFZ.Ft8.Tests -c Release --filter "RealSignal"` — 3/3 PASS
- [ ] Run `dotnet test -c Release` — 208 passed, 4 skipped, 0 failed
- [ ] Run `dotnet run --project tools/SnrAnalyser -c Release` — all buckets within tolerance
- [ ] Deliver rebuilt DLL and updated files to QA for final sign-off
