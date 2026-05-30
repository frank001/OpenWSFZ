# R5 — SNR Calibration: Required Fix

**Raised by:** QA Gate (UAT-01, 2026-05-30)  
**Severity:** Medium — cosmetic/informational; does not affect decode correctness  
**Merge gate:** This fix is required before p12 merges to `main`  
**File under review:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`

---

## The Problem in One Sentence

The ft8_lib `cand->score` value saturates at strong signal levels and is therefore not proportional to SNR above roughly −12 dB; the linear formula introduced in R1 is only accurate for weak signals.

---

## Background

The R1 fix (commit `f234f8e`) changed the SNR calculation in the shim from:

```c
result->snr = (int)(cand->score * 0.5f);
```

to:

```c
/* score * 0.5 approximates dB margin per Costas bin over neighbours.
 * WSJT-X convention: SNR relative to noise over 2500 Hz bandwidth.
 * Bandwidth correction: 10*log10(2500/6.25) ≈ 26 dB.
 * TODO: compute proper per-call noise floor estimate. */
float snr_f = (float)cand->score * 0.5f - 26.0f;
result->snr = (int)roundf(snr_f);
```

The correction improved over the original (which was ~26 dB too high), but the TODO comment was prescient — the result is still wrong, and more importantly the error is **signal-strength-dependent**, not a fixed offset.

---

## What UAT-01 Revealed

UAT-01 produced 3 063 exactly-matched (message, cycle) pairs across a 1 h 08 min live session on 7.074 MHz. For each pair we have the WSJT-X-reported SNR (the reference) and our reported SNR. The delta `ours − WSJT-X` bucketed by reference SNR is:

| WSJT-X SNR | Count | Mean delta | P25 | P75 |
|---|---|---|---|---|
| ≤ −20 dB | 53 | **+4.8 dB** | +3 dB | +6 dB |
| −20 to −16 dB | 173 | **+1.5 dB** | 0 dB | +3 dB |
| −16 to −12 dB | 361 | **−1.0 dB** | −3 dB | +1 dB |
| −12 to −8 dB | 464 | **−4.6 dB** | −6 dB | −3 dB |
| −8 to −4 dB | 512 | **−7.6 dB** | −9 dB | −6 dB |
| −4 to 0 dB | 470 | **−11.2 dB** | −13 dB | −10 dB |
| 0 to +5 dB | 523 | **−14.8 dB** | −16 dB | −13 dB |
| +5 to +15 dB | 418 | **−20.5 dB** | −23 dB | −18 dB |
| > +15 dB | 89 | **−29.2 dB** | −32 dB | −26 dB |

**The key observation:** for the weakest signals (WSJT-X ≤ −16 dB) our SNR is within ±5 dB — the R1 correction works there. But accuracy degrades monotonically as signal strength increases, reaching −29 dB mean error for the strongest signals.

The approximate score-to-WSJT-X SNR mapping derived from the data:

| Score (approx) | WSJT-X mean | Our mean (post-R1) |
|---|---|---|
| 10 – 16 | −12.3 dB | −19.6 dB |
| 16 – 22 | −9.2 dB | −16.8 dB |
| 22 – 28 | −4.3 dB | −14.0 dB |
| 28 – 34 | +0.7 dB | −11.2 dB |
| 34 – 40 | +5.3 dB | −8.7 dB |

Our SNR output range across all 3 063 matched decodes: **−21 dB to −7 dB**.  
WSJT-X SNR range for those same signals: **−24 dB to +29 dB**.

The score **saturates** at approximately score = 40, which maps to our output ceiling of ≈ −7 dB, regardless of whether the actual signal is +5 dB or +29 dB. The information needed to distinguish strong signals is simply not present in the score.

---

## Root Cause

`cand->score` is the **average dB margin of each Costas sync bin over its immediate frequency-domain neighbours** in the waterfall. It is a sync quality indicator, not a power measurement. As signal strength increases past the point where sync lock is achieved, the score reaches a ceiling — additional signal power does not increase the score further because the sync pattern is already clearly detected.

The linear formula `score * 0.5f − 26.0f` is therefore only meaningful in the narrow range where score is proportional to signal level, which corresponds approximately to WSJT-X SNR −20 dB to −12 dB in this dataset.

---

## Required Fix

The score is the wrong input for SNR computation. A noise-floor-aware measurement is required.

### Approach — Noise floor estimation from the monitor spectrum

The `monitor_t` structure computed by `monitor_process` already holds a magnitude waterfall internally. After all PCM data has been processed, estimate the noise floor from that spectrum and use it as the denominator for SNR.

**Suggested implementation in `ft8_shim.c`:**

```c
/*
 * Compute noise floor: take the median magnitude across all waterfall bins
 * in the passband (0–2700 Hz). The noise floor in WSJT-X convention is the
 * RMS noise power integrated over 2500 Hz. Use the per-bin median as a robust
 * estimator that rejects signal peaks.
 *
 * Then compute SNR for each candidate:
 *   SNR_dB = 10*log10(signal_power / noise_power_per_bin)
 *            + 10*log10(2500 / tone_spacing)   [bandwidth normalisation]
 *
 * where signal_power is derived from the waterfall magnitude at the candidate
 * frequency, and noise_power_per_bin is the squared median magnitude.
 */
```

Concretely:

1. After `monitor_process` returns, extract the waterfall magnitudes for the last complete 15-second window from `mon.mag` (or equivalent field — check `ft8_lib/common/monitor.h` for the field name and layout).
2. Sort the per-bin magnitudes; take the median. Square it to get noise power per bin.
3. For each candidate at frequency offset `freq_offset`, look up the magnitude at that bin; square it to get signal power.
4. Compute: `snr_dB = 10*log10(signal_power / noise_power) + 10*log10(2500.0f / FT8_SYMBOL_PERIOD)` where `FT8_SYMBOL_PERIOD = 6.25f` Hz.

If `mon.mag` is not directly accessible after `monitor_process`, you may need to expose it or compute the noise floor during `monitor_process` itself and store it on the `monitor_t` struct.

### Fallback approach — empirical correction table

If the noise floor approach proves impractical (e.g., the spectrum data is not accessible post-process), an empirical piecewise-linear correction derived from the UAT-01 data is an acceptable interim fix. The following table maps `score * 0.5f` (i.e., `snr_uncorrected + 26.0f`) to corrected WSJT-X-equivalent SNR:

| score * 0.5f (dB) | Corrected SNR |
|---|---|
| 5 | −16 |
| 8 | −12 |
| 11 | −9 |
| 14 | −4 |
| 17 | +1 |
| 20 | +5 |

Use linear interpolation between points; clamp to the table range (do not extrapolate above score*0.5=20). Report any decode with score below the minimum as −21 dB. Add a `// NOTE: empirical calibration from UAT-01 — replace with noise-floor method` comment.

This approach cannot recover the information lost by score saturation for very strong signals; it can only improve accuracy in the −16 to +5 dB WSJT-X range. It is acceptable only as a temporary measure pending the noise-floor implementation.

---

## What Must NOT Change

- The `FT8Result.snr` field type remains `int` (integer dB, matching WSJT-X convention).
- The existing R1 comment explaining the SNR formula must be updated (not removed) to describe the new calculation.
- `libft8.version.txt` must be updated with the new build date and a note: `SNR: noise-floor estimation (R5)` (or `SNR: empirical table (R5)` if the fallback is used).
- `BUILD.md` must be updated with the new SNR calculation description.

---

## Acceptance Criteria

QA will re-run the SNR delta bucketing against the existing UAT-01 matched-pair data (`uat-01-findings.md` paired dataset) after the DLL is rebuilt.

**Pass requires all of the following:**

| WSJT-X SNR bucket | Required mean delta |
|---|---|
| ≤ −20 dB | Within ±6 dB |
| −20 to −12 dB | Within ±5 dB |
| −12 to −4 dB | Within ±5 dB |
| −4 to +5 dB | Within ±7 dB |
| > +5 dB | Within ±10 dB (saturation tolerance) |

The looser tolerance for strong signals (> +5 dB) reflects the fundamental limitation of any score-based approach for highly saturated signals. The −20 to −4 dB range (where the vast majority of FT8 operational traffic lives) is held to the original ±5 dB criterion.

Overall mean delta must satisfy **|mean| ≤ 5 dB**.

All three `RealSignalFixtureTests` must continue to pass (G6 gate must remain green).

---

## Verification checklist (for the developer)

- [ ] Rebuild `libft8.dll` after changes to `ft8_shim.c`
- [ ] Update `libft8.version.txt` (build date, SNR note)
- [ ] Update `src/OpenWSFZ.Ft8/Native/BUILD.md` (SNR section)
- [ ] Run `dotnet test tests/OpenWSFZ.Ft8.Tests -c Release --filter "RealSignal"` — 3/3 pass
- [ ] Run `dotnet test -c Release` — 208 passed, 4 skipped, 0 failed
- [ ] Deliver rebuilt DLL and updated files to QA for SNR re-check
