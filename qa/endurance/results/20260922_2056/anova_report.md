## Grid-alignment gate (per HK-021, 2026-08-02 correction)

| appraiser | unique ts | on-grid | G | row | verdict |
|---|---:|---:|---:|---|---|
| OpenWSFZ | 2880 | 2880 | 1.0000 | ROW 1 | PASS |
| WSJT-X | 2880 | 2880 | 1.0000 | ROW 1 | PASS |

# Endurance-session ANOVA -- matched-decode metrics (OpenWSFZ vs WSJT-X)

**Run:** 2026-09-22/23 40m overnight endurance (first standardised run_endurance.py production run)  
**Generated:** 2026-09-23T09:16:55Z (`date -u`, HK-017)  
**Design:** two-way ANOVA without replication (randomized complete block design) -- Part (matched decode instance) x Appraiser (OpenWSFZ, WSJT-X), run separately for each paired numeric response below (SNR, DT, frequency offset) over the identical matched Parts. See anova_common.py's module docstring for why this design applies to single-pass live data, and not the replicated design in `qa/rr-study/harness/anova_compute.py`.

Both appraisers' decode logs come from the same live session already on disk -- OpenWSFZ's own ALL.TXT and the real WSJT-X application's own ALL.TXT, both listening to the same physical radio feed throughout. No re-decoding was performed (contrast endurance_anova_jt9.py, used when there is no live third-party log to read).

- OpenWSFZ decodes in window: **55429**
- WSJT-X decodes in window: **92048**
- Matched pairs (Parts, shared across every response below): **55010**

## Decode coverage

- OpenWSFZ decoded **55429** messages in this window; WSJT-X decoded **92048**.
- **55010** decodes matched between the two (same cycle + normalised message text) -- **99.2%** of OpenWSFZ's decodes, **59.8%** of WSJT-X's decodes.
- OpenWSFZ-only (WSJT-X did not report it): **419** (0.8% of OpenWSFZ's total).
- WSJT-X-only (OpenWSFZ did not report it): **37038** (40.2% of WSJT-X's total).

## SNR (dB)

![Matched-decode SNR scatter: OpenWSFZ vs WSJT-X](anova_report_snr_scatter.png)

![Per-Part residual vs WSJT-X SNR](anova_report_snr_residual.png)

| Source | SS | df | MS | F | P |
|---|---:|---:|---:|---:|---:|
| Part | 8812011.2657 | 55009 | 160.1922 | 14.107 | 0.0000 |
| Appraiser | 219288.9136 | 1 | 219288.9136 | 19310.714 | 0.0000 |
| Residual (confounded with interaction, n=1/cell) | 624672.0864 | 55009 | 11.3558 | | |
| Total | 9655972.2657 | 110019 | | | |

Appraiser means (SNR, dB): OpenWSFZ -5.957 dB, WSJT-X -3.133 dB, grand mean -4.545 dB.

## DT (time offset) (s)

![Matched-decode DT (time offset) scatter: OpenWSFZ vs WSJT-X](anova_report_dt_scatter.png)

![Per-Part residual vs WSJT-X DT (time offset)](anova_report_dt_residual.png)

| Source | SS | df | MS | F | P |
|---|---:|---:|---:|---:|---:|
| Part | 12215.9694 | 55009 | 0.2221 | 176.784 | 0.0000 |
| Appraiser | 11792.8341 | 1 | 11792.8341 | 9387890.691 | 0.0000 |
| Residual (confounded with interaction, n=1/cell) | 69.1009 | 55009 | 0.0013 | | |
| Total | 24077.9044 | 110019 | | | |

Appraiser means (DT (time offset), s): OpenWSFZ 0.9035 s, WSJT-X 0.2487 s, grand mean 0.5761 s.

## Frequency offset (Hz)

![Matched-decode Frequency offset scatter: OpenWSFZ vs WSJT-X](anova_report_freq_hz_scatter.png)

![Per-Part residual vs WSJT-X Frequency offset](anova_report_freq_hz_residual.png)

| Source | SS | df | MS | F | P |
|---|---:|---:|---:|---:|---:|
| Part | 58846911039.0956 | 55009 | 1069768.7840 | 154843.677 | 0.0000 |
| Appraiser | 650.2251 | 1 | 650.2251 | 94.117 | 0.0000 |
| Residual (confounded with interaction, n=1/cell) | 380040.7749 | 55009 | 6.9087 | | |
| Total | 58847291730.0956 | 110019 | | | |

Appraiser means (Frequency offset, Hz): OpenWSFZ 1507.2 Hz, WSJT-X 1507.1 Hz, grand mean 1507.2 Hz.

## Caveat (structural, not a defect)

With one observation per Part x Appraiser cell -- a live signal happens once -- the interaction term and the residual/error term are mathematically confounded (standard property of an unreplicated factorial design), for every response above. Each table can say whether the two appraisers' *mean* value differs after removing part-to-part variation (the Appraiser row); none of them can separately test whether that difference itself varies signal-to-signal.

Cross-run comparison and interpretation of these numbers is Architect/Captain territory, not this module's.

## Section 4 -- Historical trend: every standardised endurance run to date

13 run(s). `G` is the grid-alignment gate (the lower of the two appraisers' where both are known; ROW 1 PASS >= 0.99). `Ref.` is the second appraiser: live WSJT-X on the same feed, an offline `jt9 -d 3` re-decode, or n/a for a comparison that wasn't against a reference decoder at all (e.g. OpenWSFZ vs OpenWSFZ) -- **offline and n/a rows are marked non-comparable** (HK-031: `jt9 -d 3` offline is not a valid reference decoder) and must not be pooled or compared against live-WSJT-X rows. **Never pool `nhard` 60 and `nhard` 40 runs together.** `Matched %` and `OWS-only %` are each source report's own stated decode-coverage figures (matched as a share of the reference's own decodes; OpenWSFZ-only as a share of OpenWSFZ's own decodes), not recomputed here. `DT gap` has no `+/- SD` column: none of the pre-standardisation reports computed a standalone SD of the DT offset (only appraiser means), and deriving one now from raw logs would be new analysis, not backfill -- it is left out rather than invented. `Source` cites the file(s) every other field in that row was read from, repo-relative. Footnote numbering runs in table order, first-needed.

| Date | Band | Hours | DLL SHA (short) | Build branch | Build commit (short) | Shim | nhard | Ref. | Radio chain | G | Matched pairs | Matched % of ref | OWS-only % | SNR gap (dB) | DT gap (s) | Source |
|---|---|---:|---|---|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-07-28 | 10m | 9.6 | not recorded | not recorded | not recorded | not recorded | not recorded | offline `jt9 -d 3`<sup>1</sup> | not recorded | not recorded | 5781 | 68.9 | 10.8 | -14.780 | +0.6662 | `qa/endurance/2026-07-28-031fb37/anova_report_10m.md` |
| 2026-07-28 | 20m | 4.8 | not recorded | not recorded | not recorded | not recorded | not recorded | offline `jt9 -d 3`<sup>2</sup> | Voicemeeter-fed second receiver | not recorded | 24658 | 48.4 | 3.3 | -6.250 | +0.6543 | `qa/endurance/2026-07-28-031fb37/anova_report_20m.md` |
| 2026-07-28/29 | 20m(originally 80m) | not recorded | not recorded | not recorded | not recorded | not recorded | not recorded | n/a (no audio archived, zero decodes)<sup>3</sup> | not recorded | not recorded | 0 | not recorded | not recorded | not recorded | not recorded | `qa/endurance/2026-07-29-489135a/anova_report_20m_no_audio.md` |
| 2026-07-28/29 | 40m | not recorded | not recorded | not recorded | not recorded | not recorded | not recorded | offline `jt9 -d 3`<sup>4</sup> | not recorded | not recorded | 42668 | 60.2 | 3.5 | -10.419 | -0.2733 | `qa/endurance/2026-07-29-489135a/anova_report_40m.md` |
| 2026-07-29 | 20m | not recorded | not recorded | not recorded | not recorded | not recorded | not recorded | offline `jt9 -d 3`<sup>5</sup> | SDR Uno / Voicemeeter B1 | not recorded | 24201 | 48.9 | 8.2 | -5.602 | +0.6541 | `qa/endurance/2026-07-29-5016363/anova_report_20m.md`, `qa/endurance/2026-07-29-5016363/CONTAMINATION-NOTE.md` |
| 2026-07-29 | 80m | not recorded | not recorded | not recorded | not recorded | not recorded | not recorded | offline `jt9 -d 3`<sup>6,7</sup> | SDR Uno / Voicemeeter B1 | not recorded | 8290 | 84.2 | 8.1 | -8.037 | +0.6675 | `qa/endurance/2026-07-29-5016363/anova_report_80m.md`, `qa/endurance/2026-07-29-5016363/CONTAMINATION-NOTE.md` |
| 2026-07-29/30 | 10m | not recorded | not recorded | not recorded | not recorded | not recorded | not recorded | offline `jt9 -d 3`<sup>8</sup> | SDR Uno / Voicemeeter B1 | not recorded | 9177 | 72.3 | 7.0 | -3.195 | +0.6503 | `qa/endurance/2026-07-29-5016363/anova_report_10m.md` |
| 2026-07-29/30 | 40m | 24.0 | not recorded | not recorded | not recorded | not recorded | not recorded | live WSJT-X | not recorded | not recorded | 52736 | 47.8 | 4.2 | -12.498 | -0.6410 | `qa/endurance/2026-07-29-5016363/anova_report_40m.md`, `qa/endurance/2026-07-29-5016363/CONTAMINATION-NOTE.md` |
| 2026-07-31/08-02 | 20m | 43.8 | not recorded | not recorded | not recorded | not recorded | not recorded | n/a (OpenWSFZ-8080 vs OpenWSFZ-8081, same decoder both sides, hardware-chain comparison)<sup>9,10</sup> | 8080: FT-991A; 8081: SDR Uno -> Voicemeeter B1 (split antenna) | 0.3472 | 62775 | not recorded | not recorded | -3.467 | -0.4903 | `qa/endurance/2026-08-02-multiday-20m-anova/anova_report_8080_vs_8081.md`, `qa/endurance/2026-08-02-multiday-20m-anova/table_a_8080_vs_8081_grid_snapped.md` |
| 2026-07-31/08-02 | 20m | 43.8 | not recorded | not recorded | not recorded | not recorded | not recorded | live WSJT-X<sup>11</sup> | FT-991A | 0.3472 | 64275 | 18.1 | 65.2 | -5.431 | +0.1093 | `qa/endurance/2026-08-02-multiday-20m-anova/anova_report_8080_vs_wsjtx.md`, `qa/endurance/2026-08-02-multiday-20m-anova/table_a_8080_vs_wsjtx_grid_snapped.md` |
| 2026-07-31/08-02 | 20m | 43.8 | not recorded | not recorded | not recorded | not recorded | not recorded | live WSJT-X | OpenWSFZ-8081: SDR Uno -> Voicemeeter B1; WSJT-X: separate FT-991A instance (cross-hardware, split-antenna feed, NOT the same receiver) | 0.9984 | 201834 | 56.9 | 5.0 | -1.789 | +0.5635 | `qa/endurance/2026-08-02-multiday-20m-anova/anova_report_8081_vs_wsjtx.md`, `qa/endurance/2026-08-02-multiday-20m-anova/table_a_8080_vs_8081_grid_snapped.md` |
| 2026-09-21 | 20m | 24.0 | 38a21f84… | not recorded | not recorded | 20260054 | 40 | live WSJT-X | Yaesu FT-991A -> Voicemeeter Out B1 | 1.0000 | 76961 | 60.0 | 1.3 | -2.663 | +0.6533 | `2026-09-21-84cac119/anova_report_20m.md` |
| 2026-09-22 | 40m | 12.0 | 38a21f84… | decoding_improvement | 84cac119… | 20260054 | 40 | live WSJT-X | Yaesu FT-991A -> Voicemeeter Out B1 | 1.0000 | 55010 | 59.8 | 0.8 | -2.824 | +0.6548 | `artefacts/20260922_2056_endurance_run-gathered/anova_report.md` |

1. non-comparable reference (offline `jt9 -d 3`) -- 2026-07-28 10m
2. non-comparable reference (offline `jt9 -d 3`) -- 2026-07-28 20m
3. non-comparable reference (n/a (no audio archived, zero decodes)) -- 2026-07-28/29 20m(originally 80m)
4. non-comparable reference (offline `jt9 -d 3`) -- 2026-07-28/29 40m
5. non-comparable reference (offline `jt9 -d 3`) -- 2026-07-29 20m
6. non-comparable reference (offline `jt9 -d 3`) -- 2026-07-29 80m
7. drift/audio-contaminated: audio-leak contamination (other Windows-app audio bleeding into the Voicemeeter B1 bus), ~60% of sampled cycles elevated in the 21:18-23:07:30Z portion of this window -- see CONTAMINATION-NOTE.md's own timeline; report's own title flags it explicitly -- 2026-07-29 80m
8. non-comparable reference (offline `jt9 -d 3`) -- 2026-07-29/30 10m
9. non-comparable reference (n/a (OpenWSFZ-8080 vs OpenWSFZ-8081, same decoder both sides, hardware-chain comparison)) -- 2026-07-31/08-02 20m
10. drift/audio-contaminated: 8080's cycle-clock drifts off the FT8 15s grid at ~0.18s/h; the 62,775 matched pairs here are the +0s (on-grid) stratum only, 33.9% of the run's OpenWSFZ-8080 decodes -- see report banner and table_a_8080_vs_8081_grid_snapped.md -- 2026-07-31/08-02 20m
11. drift/audio-contaminated: 8080's cycle-clock drifts off the FT8 15s grid at ~0.18s/h; the 64,275 matched pairs here are the +0s (on-grid) stratum only, 34.8% of the run -- see report banner and table_a_8080_vs_wsjtx_grid_snapped.md -- 2026-07-31/08-02 20m

**Descriptive only.** No trend line and no "build effect" reading is drawn here -- interpretation across runs is Architect/Captain territory, same as every other cross-run comparison this module produces.

