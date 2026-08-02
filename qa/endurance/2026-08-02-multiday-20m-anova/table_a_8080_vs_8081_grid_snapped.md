## Grid-alignment gate (per HK-021, 2026-08-02 correction)

| appraiser | unique ts | on-grid | G | row | verdict |
|---|---:|---:|---:|---|---|
| OpenWSFZ-8080 | 10475 | 3637 | 0.3472 | ROW 2 | VOID |
| OpenWSFZ-8081 | 10467 | 10450 | 0.9984 | ROW 1 | PASS |

# Endurance-session ANOVA -- matched-decode metrics (OpenWSFZ-8080 vs OpenWSFZ-8081)

**Run:** 2026-07-31 20:04Z -> 2026-08-02 15:52Z multi-day 20m live run: Table A, OpenWSFZ 8080 vs OpenWSFZ 8081 -- GRID-SNAPPED, ALL STRATA (see breakdown, do not cite a pooled number)  
**Generated:** 2026-08-02T17:35:52Z (`date -u`, HK-017)  
**Design:** two-way ANOVA without replication (randomized complete block design) -- Part (matched decode instance) x Appraiser (OpenWSFZ-8080, OpenWSFZ-8081), run separately for each paired numeric response below (SNR, DT, frequency offset) over the identical matched Parts. See anova_common.py's module docstring for why this design applies to single-pass live data, and not the replicated design in `qa/rr-study/harness/anova_compute.py`.

Grid-snapped whole-run recall/match-count comparison (Table A of the 2026-08-02-1721 spec), not a decoder-quality ANOVA -- see the per-stratum breakdown below for why a pooled SNR/DT number is not shown.

- OpenWSFZ-8080 decodes in window: **184918**
- OpenWSFZ-8081 decodes in window: **212422**
- Matched pairs (Parts, shared across every response below): **173728**

## Decode coverage

- OpenWSFZ-8080 decoded **184918** messages in this window; OpenWSFZ-8081 decoded **212422**.
- **173728** decodes matched between the two (same cycle + normalised message text) -- **93.9%** of OpenWSFZ-8080's decodes, **81.8%** of OpenWSFZ-8081's decodes.
- OpenWSFZ-8080-only (OpenWSFZ-8081 did not report it): **11190** (6.1% of OpenWSFZ-8080's total).
- OpenWSFZ-8081-only (OpenWSFZ-8080 did not report it): **38694** (18.2% of OpenWSFZ-8081's total).

> **Grid-snapped, no single stratum selected.** Per the 2026-08-02 spec: pooling SNR/DT/frequency across drift strata produces numbers that describe this run's restart schedule, not the decoder -- the POOLED row below is shown for transparency only and must never be cited on its own.

### SNR (dB) -- grid-snapped, by stratum

| stratum | n | OpenWSFZ-8080 mean | OpenWSFZ-8081 mean | gap (OpenWSFZ-8081 minus OpenWSFZ-8080) |
|---|---:|---:|---:|---:|
| **POOLED -- DO NOT REPORT** | 173728 | -14.937 | -3.153 | 11.784 |
| +0s stratum | 62775 | -7.754 | -4.287 | 3.468 |
| +1s stratum | 75262 | -18.566 | -2.382 | 16.184 |
| +2s stratum | 35691 | -19.919 | -2.786 | 17.133 |

### DT (time offset) (s) -- grid-snapped, by stratum

| stratum | n | OpenWSFZ-8080 mean | OpenWSFZ-8081 mean | gap (OpenWSFZ-8081 minus OpenWSFZ-8080) |
|---|---:|---:|---:|---:|
| **POOLED -- DO NOT REPORT** | 173728 | -0.3975 | 0.8067 | 1.2042 |
| +0s stratum | 62775 | 0.3229 | 0.8132 | 0.4902 |
| +1s stratum | 75262 | -0.5855 | 0.7924 | 1.3779 |
| +2s stratum | 35691 | -1.2682 | 0.8254 | 2.0937 |

### Frequency offset (Hz) -- grid-snapped, by stratum

| stratum | n | OpenWSFZ-8080 mean | OpenWSFZ-8081 mean | gap (OpenWSFZ-8081 minus OpenWSFZ-8080) |
|---|---:|---:|---:|---:|
| **POOLED -- DO NOT REPORT** | 173728 | 1503.4 | 1514.9 | 11.5 |
| +0s stratum | 62775 | 1504.2 | 1516.5 | 12.3 |
| +1s stratum | 75262 | 1513.0 | 1523.6 | 10.6 |
| +2s stratum | 35691 | 1481.6 | 1493.8 | 12.2 |

