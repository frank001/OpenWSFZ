## Grid-alignment gate (per HK-021, 2026-08-02 correction)

| appraiser | unique ts | on-grid | G | row | verdict |
|---|---:|---:|---:|---|---|
| OpenWSFZ | 10475 | 3637 | 0.3472 | ROW 2 | VOID |
| WSJT-X | 10470 | 10470 | 1.0000 | ROW 1 | PASS |

# Endurance-session ANOVA -- matched-decode metrics (OpenWSFZ vs WSJT-X)

**Run:** 2026-07-31 20:04Z -> 2026-08-02 15:52Z multi-day 20m live run: Table A, 8080/FT-991A vs WSJT-X -- GRID-SNAPPED, ALL STRATA (see breakdown, do not cite a pooled number)  
**Generated:** 2026-08-02T17:35:05Z (`date -u`, HK-017)  
**Design:** two-way ANOVA without replication (randomized complete block design) -- Part (matched decode instance) x Appraiser (OpenWSFZ, WSJT-X), run separately for each paired numeric response below (SNR, DT, frequency offset) over the identical matched Parts. See anova_common.py's module docstring for why this design applies to single-pass live data, and not the replicated design in `qa/rr-study/harness/anova_compute.py`.

Both appraisers' decode logs come from the same live session already on disk -- OpenWSFZ's own ALL.TXT and the real WSJT-X application's own ALL.TXT, both listening to the same physical radio feed throughout. No re-decoding was performed (contrast endurance_anova_jt9.py, used when there is no live third-party log to read).

- OpenWSFZ decodes in window: **184918**
- WSJT-X decodes in window: **354831**
- Matched pairs (Parts, shared across every response below): **178377**

## Decode coverage

- OpenWSFZ decoded **184918** messages in this window; WSJT-X decoded **354831**.
- **178377** decodes matched between the two (same cycle + normalised message text) -- **96.5%** of OpenWSFZ's decodes, **50.3%** of WSJT-X's decodes.
- OpenWSFZ-only (WSJT-X did not report it): **6541** (3.5% of OpenWSFZ's total).
- WSJT-X-only (OpenWSFZ did not report it): **176454** (49.7% of WSJT-X's total).

> **Grid-snapped, no single stratum selected.** Per the 2026-08-02 spec: pooling SNR/DT/frequency across drift strata produces numbers that describe this run's restart schedule, not the decoder -- the POOLED row below is shown for transparency only and must never be cited on its own.

### SNR (dB) -- grid-snapped, by stratum

| stratum | n | OpenWSFZ mean | WSJT-X mean | gap (WSJT-X minus OpenWSFZ) |
|---|---:|---:|---:|---:|
| **POOLED -- DO NOT REPORT** | 178377 | -15.073 | -1.752 | 13.320 |
| +0s stratum | 64275 | -7.923 | -2.492 | 5.430 |
| +1s stratum | 77867 | -18.690 | -1.157 | 17.533 |
| +2s stratum | 36235 | -19.982 | -1.718 | 18.263 |

### DT (time offset) (s) -- grid-snapped, by stratum

| stratum | n | OpenWSFZ mean | WSJT-X mean | gap (WSJT-X minus OpenWSFZ) |
|---|---:|---:|---:|---:|
| **POOLED -- DO NOT REPORT** | 178377 | -0.3989 | 0.2408 | 0.6397 |
| +0s stratum | 64275 | 0.3220 | 0.2127 | -0.1093 |
| +1s stratum | 77867 | -0.5891 | 0.2314 | 0.8205 |
| +2s stratum | 36235 | -1.2689 | 0.3109 | 1.5799 |

### Frequency offset (Hz) -- grid-snapped, by stratum

| stratum | n | OpenWSFZ mean | WSJT-X mean | gap (WSJT-X minus OpenWSFZ) |
|---|---:|---:|---:|---:|
| **POOLED -- DO NOT REPORT** | 178377 | 1502.2 | 1502.1 | -0.1 |
| +0s stratum | 64275 | 1503.1 | 1503.0 | -0.1 |
| +1s stratum | 77867 | 1511.2 | 1511.0 | -0.1 |
| +2s stratum | 36235 | 1481.5 | 1481.4 | -0.1 |

