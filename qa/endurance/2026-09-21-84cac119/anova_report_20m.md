## Grid-alignment gate (per HK-021, 2026-08-02 correction)

| appraiser | unique ts | on-grid | G | row | verdict |
|---|---:|---:|---:|---|---|
| OpenWSFZ | 4852 | 4852 | 1.0000 | ROW 1 | PASS |
| WSJT-X | 4896 | 4896 | 1.0000 | ROW 1 | PASS |

# Endurance-session ANOVA -- matched-decode metrics (OpenWSFZ vs WSJT-X)

**Run:** 2026-09-21/22 20m LIVE-GAP-MAP endurance run (OpenWSFZ decoding_improvement 84cac119 vs live WSJT-X, same audio feed, FT-991A)  
**Generated:** 2026-09-22T18:52:41Z (`date -u`, HK-017)  
**Design:** two-way ANOVA without replication (randomized complete block design) -- Part (matched decode instance) x Appraiser (OpenWSFZ, WSJT-X), run separately for each paired numeric response below (SNR, DT, frequency offset) over the identical matched Parts. See anova_common.py's module docstring for why this design applies to single-pass live data, and not the replicated design in `qa/rr-study/harness/anova_compute.py`.

Both appraisers' decode logs come from the same live session already on disk -- OpenWSFZ's own ALL.TXT and the real WSJT-X application's own ALL.TXT, both listening to the same physical radio feed throughout. No re-decoding was performed (contrast endurance_anova_jt9.py, used when there is no live third-party log to read).

- OpenWSFZ decodes in window: **77985**
- WSJT-X decodes in window: **128369**
- Matched pairs (Parts, shared across every response below): **76961**

## Decode coverage

- OpenWSFZ decoded **77985** messages in this window; WSJT-X decoded **128369**.
- **76961** decodes matched between the two (same cycle + normalised message text) -- **98.7%** of OpenWSFZ's decodes, **60.0%** of WSJT-X's decodes.
- OpenWSFZ-only (WSJT-X did not report it): **1024** (1.3% of OpenWSFZ's total).
- WSJT-X-only (OpenWSFZ did not report it): **51408** (40.0% of WSJT-X's total).

## SNR (dB)

![Matched-decode SNR scatter: OpenWSFZ vs WSJT-X](anova_report_20m_snr_scatter.png)

![Per-Part residual vs WSJT-X SNR](anova_report_20m_snr_residual.png)

| Source | SS | df | MS | F | P |
|---|---:|---:|---:|---:|---:|
| Part | 18335853.7768 | 76960 | 238.2517 | 18.308 | 0.0000 |
| Appraiser | 272857.4479 | 1 | 272857.4479 | 20967.227 | 0.0000 |
| Residual (confounded with interaction, n=1/cell) | 1001520.5521 | 76960 | 13.0135 | | |
| Total | 19610231.7768 | 153921 | | | |

Appraiser means (SNR, dB): OpenWSFZ -2.575 dB, WSJT-X 0.088 dB, grand mean -1.244 dB.

## DT (time offset) (s)

![Matched-decode DT (time offset) scatter: OpenWSFZ vs WSJT-X](anova_report_20m_dt_scatter.png)

![Per-Part residual vs WSJT-X DT (time offset)](anova_report_20m_dt_residual.png)

| Source | SS | df | MS | F | P |
|---|---:|---:|---:|---:|---:|
| Part | 20008.2171 | 76960 | 0.2600 | 206.466 | 0.0000 |
| Appraiser | 16422.3218 | 1 | 16422.3218 | 13041848.555 | 0.0000 |
| Residual (confounded with interaction, n=1/cell) | 96.9082 | 76960 | 0.0013 | | |
| Total | 36527.4471 | 153921 | | | |

Appraiser means (DT (time offset), s): OpenWSFZ 0.9377 s, WSJT-X 0.2844 s, grand mean 0.6111 s.

## Frequency offset (Hz)

![Matched-decode Frequency offset scatter: OpenWSFZ vs WSJT-X](anova_report_20m_freq_hz_scatter.png)

![Per-Part residual vs WSJT-X Frequency offset](anova_report_20m_freq_hz_residual.png)

| Source | SS | df | MS | F | P |
|---|---:|---:|---:|---:|---:|
| Part | 79877851976.7655 | 76960 | 1037913.8770 | 513816.414 | 0.0000 |
| Appraiser | 772.5928 | 1 | 772.5928 | 382.470 | 0.0000 |
| Residual (confounded with interaction, n=1/cell) | 155459.9072 | 76960 | 2.0200 | | |
| Total | 79878008209.2655 | 153921 | | | |

Appraiser means (Frequency offset, Hz): OpenWSFZ 1486.6 Hz, WSJT-X 1486.5 Hz, grand mean 1486.5 Hz.

## Caveat (structural, not a defect)

With one observation per Part x Appraiser cell -- a live signal happens once -- the interaction term and the residual/error term are mathematically confounded (standard property of an unreplicated factorial design), for every response above. Each table can say whether the two appraisers' *mean* value differs after removing part-to-part variation (the Appraiser row); none of them can separately test whether that difference itself varies signal-to-signal.

Cross-run comparison and interpretation of these numbers is Architect/Captain territory, not this module's.

## Section 4 -- Historical trend: every standardised endurance run to date

1 standardised run(s). `G` is the grid-alignment gate (the lower of the two appraisers', i.e. the binding one; ROW 1 PASS >= 0.99). `Ref.` is the second appraiser: live WSJT-X on the same feed, or an offline `jt9 -d 3` re-decode -- **offline rows are marked non-comparable** (HK-031: `jt9 -d 3` offline is not a valid reference decoder) and must not be pooled or compared against live-WSJT-X rows. **Never pool `nhard` 60 and `nhard` 40 runs together** -- read the `nhard` column before comparing any two rows. Footnote numbering runs in table order, first-needed.

| Date | Band | Hours | DLL SHA (short) | Shim | nhard | Ref. | Radio chain | G | Matched pairs | SNR gap (dB) | DT gap (s) |
|---|---|---:|---|---:|---:|---|---|---:|---:|---:|---:|
| 2026-09-21 | 20m | 24.0 | `38a21f84…` | 20260054 | 40 | live WSJT-X | Yaesu FT-991A -> Voicemeeter Out B1 | 1.0000 | 76961 | -2.663 | +0.6533 |

**Descriptive only.** No trend line and no "build effect" reading is drawn here -- interpretation across runs is Architect/Captain territory, same as every other cross-run comparison this module produces.

