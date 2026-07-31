# Endurance-session ANOVA -- matched-decode metrics (OpenWSFZ vs jt9)

**Run:** 2026-07-28 20m live run (16:12-20:57 UTC, fix-cycle-audio-archive-null-config-crash build, Voicemeeter-fed second receiver)  
**Generated:** 2026-07-28T21:24:51Z (`date -u`, HK-017)  
**Design:** two-way ANOVA without replication (randomized complete block design) -- Part (matched decode instance) x Appraiser (OpenWSFZ, jt9), run separately for each paired numeric response below (SNR, DT, frequency offset) over the identical matched Parts. See this script's docstring for why this design applies to single-pass live data, and not the replicated design in `qa/rr-study/harness/anova_compute.py`.

- WAV cycles fed to jt9: **1141**
- Our decodes in window: **25512**
- jt9 decodes in window: **50953**
- Matched pairs (Parts, shared across every response below): **24658**

## Decode coverage

- OpenWSFZ decoded **25512** messages in this window; jt9 decoded **50953**.
- **24658** decodes matched between the two (same cycle + normalised message text) -- **96.7%** of OpenWSFZ's decodes, **48.4%** of jt9's decodes.
- OpenWSFZ-only (jt9 did not report it): **854** (3.3% of OpenWSFZ's total).
- jt9-only (OpenWSFZ did not report it): **26295** (51.6% of jt9's total).

## SNR (dB)

![Matched-decode SNR scatter: OpenWSFZ vs jt9](anova_report_20m_snr_scatter.png)

![Per-Part residual vs jt9 SNR](anova_report_20m_snr_residual.png)

| Source | SS | df | MS | F | P |
|---|---:|---:|---:|---:|---:|
| Part | 4995335.0929 | 24657 | 202.5930 | 15.856 | 0.0000 |
| Appraiser | 481679.6907 | 1 | 481679.6907 | 37699.406 | 0.0000 |
| Residual (confounded with interaction, n=1/cell) | 315038.8093 | 24657 | 12.7769 | | |
| Total | 5792053.5929 | 49315 | | | |

Appraiser means (SNR, dB): OpenWSFZ -3.426 dB, jt9 2.824 dB, grand mean -0.301 dB.

## DT (time offset) (s)

![Matched-decode DT (time offset) scatter: OpenWSFZ vs jt9](anova_report_20m_dt_scatter.png)

![Per-Part residual vs jt9 DT (time offset)](anova_report_20m_dt_residual.png)

| Source | SS | df | MS | F | P |
|---|---:|---:|---:|---:|---:|
| Part | 6380.7853 | 24657 | 0.2588 | 207.535 | 0.0000 |
| Appraiser | 5277.9995 | 1 | 5277.9995 | 4232799.577 | 0.0000 |
| Residual (confounded with interaction, n=1/cell) | 30.7455 | 24657 | 0.0012 | | |
| Total | 11689.5303 | 49315 | | | |

Appraiser means (DT (time offset), s): OpenWSFZ 1.2230 s, jt9 0.5687 s, grand mean 0.8958 s.

## Frequency offset (Hz)

![Matched-decode Frequency offset scatter: OpenWSFZ vs jt9](anova_report_20m_freq_hz_scatter.png)

![Per-Part residual vs jt9 Frequency offset](anova_report_20m_freq_hz_residual.png)

| Source | SS | df | MS | F | P |
|---|---:|---:|---:|---:|---:|
| Part | 27563486166.2562 | 24657 | 1117876.7152 | 252418.743 | 0.0000 |
| Appraiser | 26.5378 | 1 | 26.5378 | 5.992 | 0.0144 |
| Residual (confounded with interaction, n=1/cell) | 109197.4622 | 24657 | 4.4287 | | |
| Total | 27563595390.2562 | 49315 | | | |

Appraiser means (Frequency offset, Hz): OpenWSFZ 1583.7 Hz, jt9 1583.7 Hz, grand mean 1583.7 Hz.

## Caveat (structural, not a defect)

With one observation per Part x Appraiser cell -- a live signal happens once -- the interaction term and the residual/error term are mathematically confounded (standard property of an unreplicated factorial design), for every response above. Each table can say whether the two appraisers' *mean* value differs after removing part-to-part variation (the Appraiser row); none of them can separately test whether that difference itself varies signal-to-signal.

Cross-run comparison and interpretation of these numbers is Architect/Captain territory, not this script's.

