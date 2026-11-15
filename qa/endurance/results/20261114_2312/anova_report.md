## Grid-alignment gate (per HK-021, 2026-08-02 correction)

| appraiser | unique ts | on-grid | G | row | verdict |
|---|---:|---:|---:|---|---|
| OpenWSFZ | 2830 | 2830 | 1.0000 | ROW 1 | PASS |
| WSJT-X | 2829 | 2829 | 1.0000 | ROW 1 | PASS |

# Endurance-session ANOVA -- matched-decode metrics (OpenWSFZ vs WSJT-X)

**Run:** artefacts/20261114_2312_endurance_run-gathered/owsfz/ALL.TXT vs artefacts/20261114_2312_endurance_run-gathered/wsjt-x/ALL.TXT  
**Generated:** 2026-11-15T11:33:31Z (`date -u`, HK-017)  
**Design:** two-way ANOVA without replication (randomized complete block design) -- Part (matched decode instance) x Appraiser (OpenWSFZ, WSJT-X), run separately for each paired numeric response below (SNR, DT, frequency offset) over the identical matched Parts. See anova_common.py's module docstring for why this design applies to single-pass live data, and not the replicated design in `qa/rr-study/harness/anova_compute.py`.

Both appraisers' decode logs come from the same live session already on disk -- OpenWSFZ's own ALL.TXT and the real WSJT-X application's own ALL.TXT, both listening to the same physical radio feed throughout. No re-decoding was performed (contrast endurance_anova_jt9.py, used when there is no live third-party log to read).

- OpenWSFZ decodes in window: **79317**
- WSJT-X decodes in window: **85783**
- Matched pairs (Parts, shared across every response below): **75673**

## Decode coverage

- OpenWSFZ decoded **79317** messages in this window; WSJT-X decoded **85783**.
- **75673** decodes matched between the two (same cycle + normalised message text) -- **95.4%** of OpenWSFZ's decodes, **88.2%** of WSJT-X's decodes.
- OpenWSFZ-only (WSJT-X did not report it): **3644** (4.6% of OpenWSFZ's total).
- WSJT-X-only (OpenWSFZ did not report it): **10110** (11.8% of WSJT-X's total).

## SNR (dB)

![Matched-decode SNR scatter: OpenWSFZ vs WSJT-X](anova_report_snr_scatter.png)

![Per-Part residual vs WSJT-X SNR](anova_report_snr_residual.png)

| Source | SS | df | MS | F | P |
|---|---:|---:|---:|---:|---:|
| Part | 10536869.3888 | 75672 | 139.2440 | 11.024 | 0.0000 |
| Appraiser | 381514.7136 | 1 | 381514.7136 | 30205.241 | 0.0000 |
| Residual (confounded with interaction, n=1/cell) | 955793.7864 | 75672 | 12.6307 | | |
| Total | 11874177.8888 | 151345 | | | |

Appraiser means (SNR, dB): OpenWSFZ -8.996 dB, WSJT-X -5.820 dB, grand mean -7.408 dB.

## DT (time offset) (s)

![Matched-decode DT (time offset) scatter: OpenWSFZ vs WSJT-X](anova_report_dt_scatter.png)

![Per-Part residual vs WSJT-X DT (time offset)](anova_report_dt_residual.png)

| Source | SS | df | MS | F | P |
|---|---:|---:|---:|---:|---:|
| Part | 14387.1810 | 75672 | 0.1901 | 134.602 | 0.0000 |
| Appraiser | 15927.0530 | 1 | 15927.0530 | 11275762.930 | 0.0000 |
| Residual (confounded with interaction, n=1/cell) | 106.8870 | 75672 | 0.0014 | | |
| Total | 30421.1210 | 151345 | | | |

Appraiser means (DT (time offset), s): OpenWSFZ 0.8573 s, WSJT-X 0.2085 s, grand mean 0.5329 s.

## Frequency offset (Hz)

![Matched-decode Frequency offset scatter: OpenWSFZ vs WSJT-X](anova_report_freq_hz_scatter.png)

![Per-Part residual vs WSJT-X Frequency offset](anova_report_freq_hz_residual.png)

| Source | SS | df | MS | F | P |
|---|---:|---:|---:|---:|---:|
| Part | 75958507819.5242 | 75672 | 1003786.1801 | 324400.747 | 0.0000 |
| Appraiser | 81.7750 | 1 | 81.7750 | 26.428 | 0.0000 |
| Residual (confounded with interaction, n=1/cell) | 234150.2250 | 75672 | 3.0943 | | |
| Total | 75958742051.5242 | 151345 | | | |

Appraiser means (Frequency offset, Hz): OpenWSFZ 1533.5 Hz, WSJT-X 1533.4 Hz, grand mean 1533.5 Hz.

## Caveat (structural, not a defect)

With one observation per Part x Appraiser cell -- a live signal happens once -- the interaction term and the residual/error term are mathematically confounded (standard property of an unreplicated factorial design), for every response above. Each table can say whether the two appraisers' *mean* value differs after removing part-to-part variation (the Appraiser row); none of them can separately test whether that difference itself varies signal-to-signal.

Cross-run comparison and interpretation of these numbers is Architect/Captain territory, not this module's.

## Section 4 -- Historical trend: every standardised endurance run to date

10 run(s). `G` is the grid-alignment gate (the lower of the two appraisers' where both are known; ROW 1 PASS >= 0.99). `Ref.` is the second appraiser: live WSJT-X on the same feed, an offline `jt9 -d 3` re-decode, or n/a for a comparison that wasn't against a reference decoder at all (e.g. OpenWSFZ vs OpenWSFZ) -- **offline and n/a rows are marked non-comparable** (HK-031: `jt9 -d 3` offline is not a valid reference decoder) and must not be pooled or compared against live-WSJT-X rows. **Never pool `nhard` 60 and `nhard` 40 runs together.** `Matched %` and `OWS-only %` are each source report's own stated decode-coverage figures (matched as a share of the reference's own decodes; OpenWSFZ-only as a share of OpenWSFZ's own decodes), not recomputed here. `DT gap` has no `+/- SD` column: none of the pre-standardisation reports computed a standalone SD of the DT offset (only appraiser means), and deriving one now from raw logs would be new analysis, not backfill -- it is left out rather than invented. `Source` cites the file(s) every other field in that row was read from, repo-relative. Footnote numbering runs in table order, first-needed.

**Table A -- measurements**

| Date | Band | Hours | Shim | nhard | Ref. | G | Matched pairs | Matched % of ref | OWS-only % | SNR gap (dB) | DT gap (s) |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 2026-09-22 | 40m | 12.0 | 20260054 | 40 | live WSJT-X | 1.0000 | 55010 | 59.8 | 0.8 | -2.824 | +0.6548 |
| 2026-09-23 | 40m | 24.0 | 20260054 | 40 | live WSJT-X | 1.0000 | 97279 | 61.1 | 0.7 | -3.225 | +0.6484 |
| 2026-09-25 | 40m | 12.0 | 20260054 | 40 | live WSJT-X | 1.0000 | 46917 | 60.9 | 0.6 | -2.638 | +0.6511 |
| 2026-09-30 | 40m | 17.9 | 20260056 | 40 | live WSJT-X | 1.0000 | 94307 | 72.8 | 1.1 | -1.546 | +0.6611 |
| 2026-10-04 | 40m | 12.9 | 20260058 | 40 | live WSJT-X | 1.0000 | 68387 | 70.3 | 1.1 | -2.280 | +0.6588 |
| 2026-10-09 | 40m | 15.1 | 20260061 | 24 | live WSJT-X | 1.0000 | 62340 | 66.6 | 0.4 | -3.229 | +0.6508 |
| 2026-10-19 | 40m | 19.4 | 20260064 | 24 | live WSJT-X | 1.0000 | 97480 | 71.9 | 0.8 | -2.347 | +0.6572 |
| 2026-10-22 | 40m | 12.2 | 20260070 | 24 | live WSJT-X | 1.0000 | 60074 | 76.7 | 1.4 | -2.074 | +0.6529 |
| 2026-10-28 | 40m | 16.9 | 20260071 | 24 | live WSJT-X | 1.0000 | 103489 | 84.1 | 1.7 | -2.906 | +0.6529 |
| 2026-11-14 | 40m | 11.8 | 20260072 | 24 | live WSJT-X | 1.0000 | 75673 | 88.2 | 4.6 | -3.175 | +0.6488 |

**Table B -- build, radio chain and source (same row order as Table A)**

| Date | Band | DLL SHA (short) | Build branch | Build commit (short) | Radio chain | Source |
|---|---|---|---|---|---|---|
| 2026-09-22 | 40m | 38a21f84… | decoding_improvement | 84cac119… | Yaesu FT-991A -> Voicemeeter Out B1 | `artefacts/20260922_2056_endurance_run-gathered/anova_report.md` |
| 2026-09-23 | 40m | 38a21f84… | decoding_improvement | 84cac119… | FT-991A -> Microphone (2- USB Audio CODEC), DIRECT (Voicemeeter/CABLE out of the loop for this arm) | `artefacts/20260923_1730_endurance_run-gathered/anova_report.md` |
| 2026-09-25 | 40m | 38a21f84… | decoding_improvement | 51e40b55… | FT-991A -> Microphone (2- USB Audio CODEC), DIRECT (Voicemeeter/CABLE out of the loop for this arm) | `artefacts/20260925_2010_endurance_run-gathered/anova_report.md` |
| 2026-09-30 | 40m | ee00d118… | feat/sub-feas-two-stage-publish | 247ac391… | Yaesu FT-991A -> Voicemeeter Out B1 [SUB-FEAS flag ON, 8 workers: NOT poolable with flag-OFF rows] | `artefacts/20260930_1930_endurance_run-gathered/anova_report.md` |
| 2026-10-04 | 40m | 2fa6d993… | HEAD | 040613d9… | FT-991A -> Stereo Input 1 (USB 2 Audio CODEC) -> Voicemeeter B1 -> OpenWSFZ + WSJT-X [SUB-FEAS flag ON, 8 workers, early decode ON; nhard 40 per config.json (arm_config recorded null): NOT poolable with flag-OFF rows] | `../../artefacts/20261004_1634_endurance_run-gathered/anova_report.md` |
| 2026-10-09 | 40m | a14fe354… | HEAD | 421e3ce2… | FT-991A direct USB CODEC (Microphone (2- USB Audio CODEC)), no Voicemeeter | `../../artefacts/20261009_1752_endurance_run-gathered/anova_report.md` |
| 2026-10-19 | 40m | 51a28ff6… | HEAD | 87beed94… | FT-991A -> Voicemeeter Strip[0] -> B1 -> both WSJT-X and OpenWSFZ | `artefacts/20261019_1905_endurance_run-gathered/anova_report.md` |
| 2026-10-22 | 40m | 0e180dfc… | HEAD | 56736264… | FT-991A -> Voicemeeter Strip[0] -> B1 -> both WSJT-X and OpenWSFZ | `../../artefacts/20261022_1949_endurance_run-gathered/anova_report.md` |
| 2026-10-28 | 40m | 1ba8dc3d… | qa/coh-gate-r-f4-pr | fa119fe0… | FT-991A USB CODEC -> Voicemeeter Stereo Input 1 -> B1; WSJT-X and daemon both read B1 (RF4ON era) | `../../artefacts/20261028_2233_endurance_run-gathered/anova_report.md` |
| 2026-11-14 | 40m | bbde6eb6… | HEAD | 66b3ddf1… | FT-991A -> USB Audio CODEC direct (no Voicemeeter), XC ON | `artefacts/20261114_2312_endurance_run-gathered/anova_report.md` |

**Descriptive only.** No trend line and no "build effect" reading is drawn here -- interpretation across runs is Architect/Captain territory, same as every other cross-run comparison this module produces.

