# QA to Architect: final full ANOVA report of the LINUX R&R series on `sol`

- **To:** Architect, cc Captain. **From:** QA. **Date:** 2026-10-14 (`date -u` 17:0xZ at writing). **Go:** the Captain ("a new report with the full anova with all the complete datasets ... send it to the architect"). Descriptive; nothing filed or pushed; no `src/` or `native/` change.
- **Report:** `qa/rr-study/results/2026-10-14-LINUX-full-anova-final/` (`report.md`, `report.html`, `report-standalone.html`, `img/`, `stats.json`). Code: `qa/rr-study/linux/full_anova_core.py`, `build_full_anova_report.py` (`qa/refset` `36a296f8`, local). It is a NEW analysis, not an amendment to `2026-10-13-LINUX-series-consolidated` (which stays as the earlier version).
- **Data:** five PAIRED sweeps, balanced (10 parts x 2 appraisers x 3 trials per sweep; asserted in code): run 1 (default chain), run 2, repeats 1b, 2b (replacement), 3b (corrected chain). Not used: the three 11-12 Oct repeats (WSJT-X silent, one appraiser) and the INVALID stalled first attempt at repeat 2 (WSJT-X silent from 11:09:30Z; none of its data used, `INVALID.md` in its folder). Series rule as you ruled: N complete sweeps; a sweep with missing appraiser data is invalid and replaced.

## Method

Per sweep: the analyser's own `_two_way_anova` (imported); the 15 %GR&R and ndc values (3 scenarios x 5 sweeps) are asserted equal to each sweep's `report.md`. Pooled: two-way ignoring sweeps; three-way crossed random-effects ANOVA Part x Appraiser x Sweep (EMS variance components, exact F for the four interactions, Satterthwaite quasi-F for the three main effects), part-cluster bootstrap CIs (2000, seed 20261014; resamples parts, NOT sweeps). Bias and linearity; Cochran's Q and exact sign tests for S4 and S1b per-message decode counts; chain effect by adding run 1 as a fifth sweep.

## Results (four corrected sweeps unless stated)

| Item | Value |
|---|---|
| %GR&R S1 / S2 / S3 | 0.22 % [0.10, 0.79] ndc 29 / 0.000 % ndc 1518 / 1.11 % [0.82, 2.65] ndc 13 |
| Run 1 (default chain) S1 %GR&R | 11.2 % MARGINAL, OpenWSFZ bias -3.75 dB; sweep share of S1 variance 0.043 % -> 2.84 % with run 1 added |
| S3 appraiser share (largest non-part source) | 1.02 % [0.76, 2.43], appraiser main effect p < 0.0001 |
| S1 OpenWSFZ bias per sweep | +0.88, +0.95, +1.28, +1.45 dB; WSJT-X +0.82 to +0.85 dB; Appraiser x Sweep p < 0.0001 |
| S1 appraiser difference (OpenWSFZ - WSJT-X) | +0.31 dB, t CI -0.12 to +0.74 (includes 0); appraiser main effect p 0.104 |
| S4 | OpenWSFZ 96/96/96/96, WSJT-X 102/102/102/103 of 108; Cochran Q p 1.0 and 0.39; WSJT-X decodes 7 messages OpenWSFZ never decodes, the reverse 0 (exact sign p 0.0156) |
| S1b | OpenWSFZ 6 of 12, WSJT-X 9 of 12 in every corrected sweep; S5 0/480 false positives, both appraisers |

## Points for the Architect's reading

1. The S1 OpenWSFZ bias is **not monotone in time** (run order +0.88, +0.95, +1.45, +1.28 dB), so the report does not call it drift; its range (0.57 dB) is the yardstick, against 0.03 dB for WSJT-X. Four sweeps cannot separate drift from chance (stated).
2. The F-test p values are approximate: the reported values are rounded (1 dB, 1 Hz, 0.1 s) and 76 % / 98 % / 78 % (S1 / S2 / S3) of within-cell residuals are exactly zero.
3. The same 10 parts and 108 messages are in every sweep, so the sweeps are replicates of one design, not independent samples of the message population.
4. No bar is proposed (HK-038); S7 is shown per sweep and as a band, never as a mean; S8 is descriptive.
5. The report's recommendation 1 is the monitoring/liveness-gate plan (`2026-10-14-1830-qa-plan-wsjtx-stall-monitoring-and-gate.md`); both stalls are listed together in Section 1. The Captain's go for M1-M3 and a root `core_pattern` change on `sol` are still pending.
6. HK-031: Section 6 of the last LINUX report was read before the new Section 6 was written.

Not claimed: any decoder-improvement statement, any comparison with the Windows series, the cause of the two WSJT-X stalls.
