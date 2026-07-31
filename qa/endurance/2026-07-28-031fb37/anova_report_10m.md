# Endurance-session ANOVA -- matched-decode metrics (OpenWSFZ vs jt9)

**Run:** 2026-07-28 10m live run (11:19-20:57 UTC, fix-cycle-audio-archive-null-config-crash build)  
**Generated:** 2026-07-28T21:14:41Z (`date -u`, HK-017)  
**Design:** two-way ANOVA without replication (randomized complete block design) -- Part (matched decode instance) x Appraiser (OpenWSFZ, jt9), run separately for each paired numeric response below (SNR, DT, frequency offset) over the identical matched Parts. See this script's docstring for why this design applies to single-pass live data, and not the replicated design in `qa/rr-study/harness/anova_compute.py`.

- WAV cycles fed to jt9: **2315**
- Our decodes in window: **6480**
- jt9 decodes in window: **8390**
- Matched pairs (Parts, shared across every response below): **5781**

## Decode coverage

- OpenWSFZ decoded **6480** messages in this window; jt9 decoded **8390**.
- **5781** decodes matched between the two (same cycle + normalised message text) -- **89.2%** of OpenWSFZ's decodes, **68.9%** of jt9's decodes.
- OpenWSFZ-only (jt9 did not report it): **699** (10.8% of OpenWSFZ's total).
- jt9-only (OpenWSFZ did not report it): **2609** (31.1% of jt9's total).

## SNR (dB)

![Matched-decode SNR scatter: OpenWSFZ vs jt9](anova_report_10m_snr_scatter.png)

![Per-Part residual vs jt9 SNR](anova_report_10m_snr_residual.png)

| Source | SS | df | MS | F | P |
|---|---:|---:|---:|---:|---:|
| Part | 1926788.0623 | 5780 | 333.3543 | 5.782 | 0.0000 |
| Appraiser | 631437.2199 | 1 | 631437.2199 | 10952.688 | 0.0000 |
| Residual (confounded with interaction, n=1/cell) | 333224.7801 | 5780 | 57.6513 | | |
| Total | 2891450.0623 | 11561 | | | |

Appraiser means (SNR, dB): OpenWSFZ -7.311 dB, jt9 7.469 dB, grand mean 0.079 dB.

## DT (time offset) (s)

![Matched-decode DT (time offset) scatter: OpenWSFZ vs jt9](anova_report_10m_dt_scatter.png)

![Per-Part residual vs jt9 DT (time offset)](anova_report_10m_dt_residual.png)

| Source | SS | df | MS | F | P |
|---|---:|---:|---:|---:|---:|
| Part | 4162.5228 | 5780 | 0.7202 | 638.305 | 0.0000 |
| Appraiser | 1283.1338 | 1 | 1283.1338 | 1137291.131 | 0.0000 |
| Residual (confounded with interaction, n=1/cell) | 6.5212 | 5780 | 0.0011 | | |
| Total | 5452.1778 | 11561 | | | |

Appraiser means (DT (time offset), s): OpenWSFZ -0.3472 s, jt9 -1.0134 s, grand mean -0.6803 s.

## Frequency offset (Hz)

![Matched-decode Frequency offset scatter: OpenWSFZ vs jt9](anova_report_10m_freq_hz_scatter.png)

![Per-Part residual vs jt9 Frequency offset](anova_report_10m_freq_hz_residual.png)

| Source | SS | df | MS | F | P |
|---|---:|---:|---:|---:|---:|
| Part | 4052317787.0182 | 5780 | 701093.0427 | 1299068.429 | 0.0000 |
| Appraiser | 46.5971 | 1 | 46.5971 | 86.341 | 0.0000 |
| Residual (confounded with interaction, n=1/cell) | 3119.4029 | 5780 | 0.5397 | | |
| Total | 4052320953.0182 | 11561 | | | |

Appraiser means (Frequency offset, Hz): OpenWSFZ 1499.0 Hz, jt9 1498.9 Hz, grand mean 1499.0 Hz.

## Caveat (structural, not a defect)

With one observation per Part x Appraiser cell -- a live signal happens once -- the interaction term and the residual/error term are mathematically confounded (standard property of an unreplicated factorial design), for every response above. Each table can say whether the two appraisers' *mean* value differs after removing part-to-part variation (the Appraiser row); none of them can separately test whether that difference itself varies signal-to-signal.

Cross-run comparison and interpretation of these numbers is Architect/Captain territory, not this script's.

