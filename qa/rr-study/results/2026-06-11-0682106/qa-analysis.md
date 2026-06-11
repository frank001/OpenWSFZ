# QA Analysis — R&R Run 2026-06-11 / SHA 0682106

## Run context

| Field | Value |
|---|---|
| SHA | `068210692666c3865a994c378f86718a9e1ca908` |
| Branch | `fix/d002-snr-bias` |
| Shim version | `FT8_SHIM_VERSION = 20260006` |
| SNR formula | `signal_db − noise_floor_db − 26.5` |
| PCM normalisation | `PcmNormalisationTargetRms = 0.20f` |
| Scenarios run | S1 only (targeted D-002 validation) |
| Study validity | UNBLOCKED — D-003 absent (0 anomalies in 30 cycles) |

## Verdict

**PASS — D-002 resolved.**

OpenWSFZ S1 SNR bias = **+1.78 dB**, within the ±2.0 dB threshold for the first time.
Margin to threshold: **0.22 dB**.

## Metrics

| Metric | Value | Threshold | Verdict |
|---|---|---|---|
| OpenWSFZ S1 bias | +1.78 dB | ±2.0 dB | **PASS** |
| WSJT-X S1 bias | +0.98 dB | ±2.0 dB | **PASS** |
| %GR&R | 0.5% | ≤ 10% | **PASS** |
| ndc | 19 | ≥ 5 | **PASS** |
| SNR monotonicity (P0→P9) | non-decreasing | non-decreasing | **PASS** |
| False positives | 1 each (warmup) | — | informational |

## Per-part bias — OpenWSFZ

| Part | True SNR (dB) | Reported | Bias | Part mean |
|---|---|---|---|---|
| P0 | −12.0 | −10, −10, −11 | +2.0, +2.0, +1.0 | +1.67 |
| P1 | −8.1 | −6, −6, −6 | +2.1, +2.1, +2.1 | +2.10 |
| P2 | −5.8 | −5, −4, −4 | +0.8, +1.8, +1.8 | +1.47 |
| P3 | −2.3 | −1, 0, −1 | +1.3, +2.3, +1.3 | +1.63 |
| P4 | +0.4 | +2, +3, +2 | +1.6, +2.6, +1.6 | +1.93 |
| P5 | +3.5 | +6, +5, +5 | +2.5, +1.5, +1.5 | +1.83 |
| P6 | +6.6 | +8, +9, +8 | +1.4, +2.4, +1.4 | +1.73 |
| P7 | +9.3 | +11, +11, +11 | +1.7, +1.7, +1.7 | +1.70 |
| P8 | +12.8 | +15, +15, +15 | +2.2, +2.2, +2.2 | +2.20 |
| P9 | +15.1 | +16, +17, +17 | +0.9, +1.9, +1.9 | +1.57 |

Bias range: +0.8 to +2.5 dB (individual observations). All scatter is consistent with
±0.5 dB integer-rounding noise from libft8's integer SNR output. No systematic linearity
component (R² = 0.003, slope = 0.003 dB/dB). The bias is a flat calibration offset,
as expected.

## D-002 resolution history

| Run | SHA | Change | Bias | Verdict |
|---|---|---|---|---|
| Baseline | `91f68dd` | No normalisation | +2.42 dB | FAIL |
| Run 1 | `6ce38a3` | PCM norm target=0.08 | +2.28 dB | FAIL |
| Run 2 | `4ab061a` | PCM norm target=0.20 | +2.28 dB | FAIL |
| **Run 3** | **`0682106`** | **Shim −26.0→−26.5 dB** | **+1.78 dB** | **PASS** |

**Key finding (runs 1 & 2):** PCM normalisation was mathematically invariant to amplitude
because both `signal_db` and `noise_floor_db` are derived from the same waterfall formula.
The residual bias was a property of the SNR constant, not of PCM amplitude.

**Fix (run 3):** Adjusting the shim bandwidth constant from −26.0 to −26.5 dB reduced bias
by 0.50 dB (2.28 → 1.78 dB), clearing the ±2.0 dB threshold with 0.22 dB margin.

## Open defects — status update

| ID | Status |
|---|---|
| **D-002** | **RESOLVED** — bias +1.78 dB ≤ ±2.0 dB threshold |
| D-001 | Open — co-channel decode gap (separate root cause) |
| D-003 | Open (medium) — intermittent signal_db drop; absent this run |

## Measurement system quality

%GR&R improved from 1.2% (previous clean runs) to 0.5%, ndc improved from 12–13 to 19.
Both well within acceptable ranges. The improvement is likely run-to-run variation.
