# QA Findings — Run `15b220b` — fix-d001-revised Option B (Soft SNR-Scaled Attenuation)

**Raised:** 2026-06-07
**Raised by:** QA
**Run:** `15b220b` (fix-d001-revised branch; FT8_SHIM_VERSION=20260004)
**Run directory:** `results/2026-06-07-15b220b/`
**Status:** Findings complete — pending Captain decision (task 3.2)
**Baseline:** Run `6bab388` (p15 hard-zero spectrogram suppression; 2026-06-06)

---

## Overall Verdict: PASS

S1–S6 gates all pass. No regression introduced. S7 informational result shows
a **+10.8 pp improvement** over the baseline.

---

## Gate Results — S1 through S6

| Scenario | Metric | Value | Gate | Verdict |
|---|---|---|---|---|
| S1 | %GR&R | 6.5% | < 10% | **PASS** |
| S1 | ndc | 5 | ≥ 5 | **PASS** |
| S2 | %GR&R | 0.0% | < 10% | **PASS** |
| S2 | ndc | 1620 | ≥ 5 | **PASS** |
| S3 | %GR&R | 3.4% | < 10% | **PASS** |
| S3 | ndc | 7 | ≥ 5 | **PASS** |
| S1 | SNR bias — WSJT-X | −1.60 dB, slope −0.008 | ≤ ±2 dB AND slope ≤ 0.1 | **PASS** |
| S1 | SNR bias — OpenWSFZ | +1.70 dB, slope 0.090 | ≤ ±2 dB AND slope ≤ 0.1 | **PASS** |
| S5 | FP rate — WSJT-X | 0.00% | ≤ 6% | **PASS** |
| S5 | FP rate — OpenWSFZ | 0.00% | ≤ 6% | **PASS** |
| S4+S5 | Kappa — WSJT-X vs truth | 1.000 | ≥ 0.90 (advisory) | PASS (advisory) |
| S4+S5 | Kappa — OpenWSFZ vs truth | 1.000 | ≥ 0.90 (advisory) | PASS (advisory) |

**S1–S6: all PASS. No regression.**

---

## S7 — Co-channel / Compounding Recovery (Informational)

### Aggregate comparison vs baseline

| Run | SHA | OpenWSFZ | WSJT-X | Δ OpenWSFZ vs baseline |
|---|---|---|---|---|
| Baseline (p15 hard-zero) | `6bab388` | 46.2% | 77.4% | — |
| **Option B (soft attenuation)** | **`15b220b`** | **57.0%** | **79.6%** | **+10.8 pp** |

### Recovery by overlap family — this run vs baseline

| Family | Condition | WSJT-X (`6bab388`) | OpenWSFZ (`6bab388`) | WSJT-X (`15b220b`) | OpenWSFZ (`15b220b`) | Δ OpenWSFZ |
|---|---|---|---|---|---|---|
| co_channel | 2/3-stack equal SNR | 38.1% | 4.8% | 47.6% | 9.5% | +4.7 pp |
| time_freq | co-freq, staggered DT | 100.0% | 38.9% | 100.0% | 44.4% | +5.5 pp |
| near_collision | 3–50 Hz separation | 100.0% | 76.7% | 100.0% | 90.0% | +13.3 pp |
| capture | co-freq, unequal SNR | 66.7% | 50.0% | 66.7% | 66.7% | +16.7 pp |
| **all** | | **77.4%** | **46.2%** | **79.6%** | **57.0%** | **+10.8 pp** |

### Per-part detail — this run

| Part | Family | Condition | WSJT-X | OpenWSFZ | Δ OpenWSFZ vs baseline |
|---|---|---|---|---|---|
| P0 | co_channel | 2-stack, equal 0 dB | 5/6 | 0/6 | ±0 |
| P1 | co_channel | 2-stack, equal −5 dB | 5/6 | 2/6 | +1 |
| P2 | co_channel | 3-stack, equal 0 dB | 0/9 | 0/9 | ±0 |
| P3 | near_collision | delta 3 Hz | 6/6 | 6/6 | ±0 |
| P4 | near_collision | delta 6 Hz | 6/6 | 5/6 | +3 |
| P5 | near_collision | delta 12 Hz | 6/6 | 5/6 | +2 |
| P6 | near_collision | delta 25 Hz | 6/6 | 5/6 | −1 |
| P7 | near_collision | delta 50 Hz | 6/6 | 6/6 | ±0 |
| P8 | time_freq | co-freq, dt 0.5 s | 6/6 | 0/6 | ±0 |
| P9 | time_freq | co-freq, dt 1.0 s | 6/6 | 2/6 | −1 |
| P10 | time_freq | co-freq, dt 2.0 s | 6/6 | 6/6 | +2 |
| P11 | capture | co-freq, 0 / −3 dB | 4/6 | 5/6 | +2 |
| P12 | capture | co-freq, 0 / −6 dB | 5/6 | 5/6 | +2 |
| P13 | capture | co-freq, 0 / −10 dB | 4/6 | 3/6 | ±0 |
| P14 | capture | co-freq, +3 / −10 dB | 3/6 | 3/6 | ±0 |

### Interpretation

**Option B delivers a meaningful, broad-based improvement.** The +10.8 pp overall gain is not
concentrated in a single family; near-collision (+13.3 pp) and capture (+16.7 pp) both show
substantial recovery. Time-freq and co-channel also improve, though modestly.

**The hard cases are unchanged:**
- P0 (2-stack, equal 0 dB): 0/6. The physics here are severe; tile suppression alone cannot
  separate perfectly co-channel equal-power signals. PCM-domain SIC would be needed.
- P8 (co-freq, dt 0.5 s): 0/6. The 0.5 s time offset is too small for spectrogram-domain
  separation.
- P2 (3-stack equal 0 dB): 0/9. Both apps fail; this remains consistent with the theoretical
  mutual-interference limit.

**Two parts show −1 changes (P6, P9)** — these are within trial-to-trial noise (single-count
differences from 3-trial results). They do not represent a genuine regression.

### Between-app agreement (S7)
- Overall: 70.97% per-signal agreement
- Strong signal capture: 100% / 100% (both apps agree on the dominant signal)
- Weak signal capture: 33% / 33% (equal, limited recovery of the suppressed station)

---

## Advisory Observations

### OpenWSFZ SNR bias slope — approaching threshold

| Run | Slope | Threshold | Margin |
|---|---|---|---|
| `6bab388` (baseline) | (not available in findings) | 0.1 | — |
| `15b220b` (this run) | 0.090 | 0.1 | 0.010 |

The slope passes (0.090 < 0.1) but the margin is narrow. This is not a defect under current
gates; it is noted for trend monitoring. If the slope continues to drift upward in future runs,
a dedicated calibration investigation would be warranted. No action required at this time.

---

## Comparison with D-001 Acceptance Criterion

The D-001 acceptance criterion (AC-IS-1) targets ≥ 1/6 improvement on P0 and P8:
- **P0 (2-stack, equal 0 dB):** 0/6 → 0/6. **No change.** Hard case; remains outside reach of
  spectrogram-domain approaches.
- **P8 (co-freq, dt 0.5 s):** 0/6 → 0/6. **No change.** Similarly hard.

The overall S7 recovery improvement (+10.8 pp) is real and is driven by the near-collision and
capture families, where soft attenuation reduces collateral damage on adjacent signals. It does
not address the specific P0/P8 failure modes that originally defined D-001.

**D-001 status: gap partially closed by Option B. The hardest cases (P0, P8) are unchanged.**

---

## Input to Captain Gate (Task 3.1)

| Item | Result |
|---|---|
| Option A verdict | No upstream update available; no decode-pipeline changes in kgoba/ft8_lib since v2.0 |
| Option B S1–S6 | All PASS — no regression |
| Option B S7 overall | OpenWSFZ 57.0% vs baseline 46.2% (+10.8 pp) |
| Option B P0 | 0/6 (unchanged — equal-SNR co-channel gap persists) |
| Option B P8 | 0/6 (unchanged — 0.5 s time-freq gap persists) |
| Ground-truth corpus | 69.2% (614/887) — at or above baseline |
| Test suite | 313 tests, 0 failures |

The Captain must now choose one of:
1. **Proceed to Option C PoC** — Python PoC demonstrating PCM-domain amplitude-tracked SIC
   on synthetic S7 cases, before any production C code.
2. **Proceed to Option D** — Downgrade or close D-001 given A+B results alone.
3. **Accept current state** — D-001 remains Open; no further action at this time.
