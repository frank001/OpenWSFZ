# OpenWSFZ R&R Study Report

| Field | Value |
|---|---|
| Run date | 2026-09-05 |
| OpenWSFZ SHA | `df13da09fcbd537814e95cc7fc1053d53111e3a4` |
| WSJT-X version | 2.7.0 |

## Section 1 — Study hypothesis

**`S5-STANDALONE`** (Architect spec `2026-09-05-1311-…`, Captain-initiated per the PO's
"go with 1" ruling on the `S5-BASELINE` adjudication). `S5-BASELINE` (QA, 2026-09-04) found the
historical S5 series confounded era with context: pre-window and post-window each had **zero**
standalone-context runs, so the disputed `3.25×`/`4.88×` regression figures could not be checked
against a clean standalone-vs-standalone contrast. This run exists to fill that one empty cell.

**Null hypothesis:** the standalone, cold-decoder AWGN false-positive rate on current `main`
equals July's shipped-config rate (`8/300`, `a3738fc`), i.e. no elevation at the magnitude in
dispute. **Alternative:** an elevation at or above 2.25× (`k≥18/300`), the pre-registered,
mechanically fixed firing threshold (exact Fisher critical value — see ROW 1 below).

**What would be meaningful:** `k≥18` would confirm a large regression survives in the one
context previously untested; `k<18` rules out a *large* regression here but — by design, at
N=300 — carries almost no power (2.5%) against the smaller (~1.35×) effect the
July-vs-post-window comparison implies. Full pre-registration, all five precondition rows
(0a–0e), and the two secondary rows (2, 3) are in the companion report:
`qa/rr-study/2026-09-05-1505-qa-to-architect-s5-standalone-result.md` — that document is the
authoritative record of every row's mechanical outcome; this section exists so `report.md`
stands on its own per HK-001.

## Attribute Agreement Analysis (S4 positives + S5 negatives)

_κ is computed over a pooled population: S4 injected messages (truth = present) and S5 signal-free slots (truth = absent), so the truth vector has both classes. **κ verdicts below are advisory** — the §10 attribute gate is pending Captain ratification of this pooled method._

### Confusion vs truth

| Appraiser | TP | FN | FP | TN | Recovery | Specificity |
|---|---|---|---|---|---|---|
| WSJT-X | 0 | 0 | 0 | 300 | —% | 100.00% |
| OpenWSFZ | 0 | 0 | 6 | 294 | —% | 98.00% |

### Kappa (advisory)

| Pair | κ | 95% CI | Verdict (advisory) |
|---|---|---|---|
| OpenWSFZ_vs_truth | — | — | — |
| WSJT-X_vs_truth | — | — | — |
| between_appraisers | — | — | — |

### Within-app repeatability (decision consistency across trials)

| Appraiser | Consistent groups |
|---|---|
| WSJT-X | 100.00% |
| OpenWSFZ | 0.00% |

### Kappa — decodable-SNR-restricted positives (informational, floor -12 dB)

_S4 positives below the decodable-SNR floor are excluded (S5 negatives unchanged); shown alongside the full-population figures above per STUDY-SPEC.md §9.3's second ratification condition. **Informational only — does not affect the §10 gate or the overall verdict.**

| Appraiser | TP | FN | FP | TN | Recovery | Specificity |
|---|---|---|---|---|---|---|
| WSJT-X | 0 | 0 | 0 | 300 | —% | 100.00% |
| OpenWSFZ | 0 | 0 | 6 | 294 | —% | 98.00% |

| Pair | κ | 95% CI | Verdict (informational) |
|---|---|---|---|
| OpenWSFZ_vs_truth | — | — | — |
| WSJT-X_vs_truth | — | — | — |
| between_appraisers | — | — | — |

### False-positive rate (S5)

| Appraiser | FP events / slots | Event rate | 95% UB | Decode rate | Verdict |
|---|---|---|---|---|---|
| WSJT-X | 0 / 300 | 0.00% | 0.99% | 0.00% | PASS |
| OpenWSFZ | 6 / 300 | 2.00% | 3.91% | 2.00% | PASS |

_Gate (STUDY-SPEC §10, ratified 2026-07-04, R&R-004): the per-slot FP **event rate**, gated on its one-sided 95% Clopper–Pearson **upper bound** (PASS iff 95% UB ≤ 6%). The UB is defined for all event counts (≈ 3 / N_slots at 0 events) and bounds the true per-slot FP probability at 95% confidence rather than the Poisson-noisy point estimate. Decode rate is reported for reference only. **INFO** means the gate is not evaluated at this N: below 49 slots, even zero observed events cannot clear the 6% ceiling, so no outcome at this sample size can produce a PASS or a meaningful FAIL — see a properly powered run (N ≥ 49) for the ratified §10 verdict._

## Summary

| Metric | Scope | Value | Verdict |
|---|---|---|---|
| FP event rate (95% UB) | S5/WSJT-X | 0/300 slots (event 0.0%; 95% UB 0.99%; decode 0.0%) | PASS |
| FP event rate (95% UB) | S5/OpenWSFZ | 6/300 slots (event 2.0%; 95% UB 3.91%; decode 2.0%) | PASS |

**Overall verdict: PASS**

## Section 5 — Recommendations

All metrics PASS at this N. No further investigation is required as a *consequence of this
run's own gate*. However, per §5 of the Architect's spec, this run is powered to confirm a large
regression (96.5% power at the HELD `3.25×`) and nearly blind to a small one (2.5% power at the
`1.35×` the July-vs-post-window comparison implies) — **a PASS here does not clear a small
regression**, and should not be cited as doing so. The recommended follow-on (not authorised by
this spec, PO's call) is the offline `AWGN-FP` seam paired contrast (`a3738fc` built vs current
`main`, n=4,000, no device/cadence/era confound) — see spec §8.

Two process defects were found and corrected in-flight while producing this result (neither
changes the reported counts' *validity*, both are disclosed for the backlog): `matcher.py`'s
false-positive pass has no run-window time filter and mis-attributed the pre-run warm-up decode
as an in-scenario FP until manually corrected (mirrors a defect the July run's own report
documented and fixed the same way); and `run_scenario.py --run-dir <bare name>` resolves against
the CWD rather than `results/` as its own `--help` text claims, which nearly left this run's
gitignored raw logs outside the `.gitignore` coverage that protects them. Full detail in the
companion report §6.

## Section 6 — Extended historical trend

**HK-031 discharged** before this run was executed (spec §1 quotes it). S5 AWGN OpenWSFZ series
(one-sided 95% Clopper–Pearson upper bound; 🛑 do not back-compute counts from this column —
mixes rates and UBs, HK-031):

> `06-06 0.0% · 06-06 0.0% · 06-07 0.0% · 06-14 0.0% · 06-20 91.7% FAIL¹ · 06-22 0.0% · 07-04 0.0% ·
> 08-05 0.0% · 08-15 0.8% · 08-21 0.8% · 08-22 3.3% FAIL² · 08-27 0.0% · 08-29 7.66% FAIL ·
> 08-30/31 5.15%⁴ · 09-02 14.61% FAIL · 09-03 10.12% FAIL · **09-05 3.91% PASS (this run, standalone/cold)**`

This run is the **first standalone-context entry since July's own `0.0%`/`4.76%` figures** (the
July row above is the `s5-noise.json` battery-context figure per the trend table's own
convention; July's *standalone* `a3738fc` result — `8/300`, 95% UB 4.76% — is the ROW 1
comparator used directly in §3 of the companion report, not this trend column, per HK-031's
extension: routine-battery trend columns and targeted standalone runs are not the same series
and must not be silently merged). Read alongside its own note: this sweep's `3.91%` sits
*between* July's `4.76%` and the run immediately preceding it (`35378b9`, `10.12%` battery
context) — but §0.2 of the spec bars any per-commit attribution from this contrast, and ROW 3
(companion report §5) bars any ratio/adjudication on the same-build context pair. The number is
recorded here for the series; its meaning is adjudicated in the companion report, not here.
