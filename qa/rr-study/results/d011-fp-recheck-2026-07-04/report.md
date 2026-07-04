# OpenWSFZ R&R Study Report — D-011 AC-4 False-Positive Re-check

## 1. Study Hypothesis

**Context.** D-011 raised `Ft8Decoder.IsCallsignOversized`'s base-callsign ceiling from
6 to 11 characters, so that genuine literal (non-hash) Type 4 nonstandard callsigns
7–11 characters long stop being silently dropped. That guard is the same one D-009
tuned in the opposite direction (for *specificity*, i.e. suppressing OSD noise-floor
false positives) — nearly doubling the ceiling is a materially bigger move than any
single D-009 tuning step, so this run exists to answer one question directly:

> **Does the D-011 ceiling raise reopen the false-positive hole that D-009 closed?**

**Null hypotheses:**

| ID | Null hypothesis | Would be refuted by |
|---|---|---|
| H₀₁ | The D-011 fix does not raise the S5 noise-floor false-positive rate above the `STUDY-SPEC.md` §10 hard ceiling (≤ 6%/slot). | Observed FP rate > 6%/slot. |
| H₀₂ | The D-011 fix does not produce a statistically meaningful increase in FP rate versus the D-009 baseline (shim 20260029, 5/120 = 4.17%/slot). | Baseline and new-run 95% CIs fail to overlap, or a two-proportion significance test rejects equality at α = 0.05. |

**Defect IDs under observation:** D-011 (fix under test), D-009 (source of the baseline
this run validates against — not itself being re-litigated).

**What constitutes a meaningful result:** a FAIL on either null hypothesis is
merge-blocking pending Captain/Architect review; a PASS on both, even by a narrow
margin, is evidence (not proof — see §5) that the ceiling raise is safe to ship at
current shim settings.

**Scenario used and a correction:** the dev-task (`dev-tasks/2026-07-03-d-011-nonstandard-callsign-fp-guard.md`,
Action 3.3) named `qa/rr-study/scenarios/s5-noise.json`, but that file is a 4-part ×
3-trial (12-slot) carrier/birdie *coverage* scenario, not the statistically-powered
rate estimator the 0.042/slot baseline was actually measured with. This run instead
uses **`s5-noise-wide.json`** (1 part × 120 independent AWGN trials), confirmed against
`results/d009-investigation-2026-06-21/report.md` §2.2, which cites that exact file for
the baseline measurement. Using the coverage scenario here would have produced a
non-comparable, underpowered (N=12) result.

## 2. Run Context

| Field | Value |
|---|---|
| Run date | d011-fp-recheck (2026-07-04) |
| OpenWSFZ SHA | `f1e76d48e8747ae3169a6cf1454ac0fef2b22878` (fresh build verified against clean working tree) |
| WSJT-X version | unknown (not queried this run — see §5 process note) |
| Scenario | `s5-noise-wide.json`, 120 signal-free AWGN slots, VB-CABLE loopback |
| Pre-flight check | Warm-up cycle (`CQ Q1ABC FN42`) decoded by both apps, cycle `260704_095700`, before the timed run began at `09:59:00Z` |
| Baseline compared against | 5/120 (4.17%/slot), shim 20260029, `results/d009-investigation-2026-06-21/` |

## 3–4. Attribute Agreement Analysis (S4 positives + S5 negatives)

_κ is computed over a pooled population: S4 injected messages (truth = present) and S5 signal-free slots (truth = absent), so the truth vector has both classes. **κ verdicts below are advisory** — the §10 attribute gate is pending Captain ratification of this pooled method._

### Confusion vs truth

| Appraiser | TP | FN | FP | TN | Recovery | Specificity |
|---|---|---|---|---|---|---|
| WSJT-X | 0 | 0 | 0 | 120 | —% | 100.00% |
| OpenWSFZ | 0 | 0 | 7 | 113 | —% | 94.17% |

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

### False-positive rate (S5)

| Appraiser | FP events / slots | Event rate | 95% UB | Decode rate | Verdict |
|---|---|---|---|---|---|
| WSJT-X | 0 / 120 | 0.00% | ≤ 2.50% | 0.00% | PASS |
| OpenWSFZ | 7 / 120 | 5.83% | — | 5.83% | FAIL |

_Gate (AC5a): FP event count must be 0. 95% UB is the rule-of-three one-sided bound on per-slot FP probability (valid only when 0 events observed; = 3 / N_slots)._

> ⚠️ **Gate discrepancy, flagged not resolved here.** The AC5a zero-tolerance gate above
> is `harness/analyse.py`'s own code-level rule, and it disagrees with the
> architect-ratified threshold in `STUDY-SPEC.md` §10 ("False-positive rate ≤ 6%:
> Acceptable"). The code comment states the 6% threshold was "retired," but §10 was
> never amended to record that decision (contrast the properly-dated 2026-06-06
> advisory-downgrade note for the Kappa gate in the same section). This run is
> evaluated against the **two gates pre-committed for D-011 AC-4** — the ratified §10
> ceiling and a regression-vs-baseline check — not against the in-code AC5a rule, whose
> authority is disputed. See §5.

### D-011 AC-4 gate evaluation (pre-committed, not the harness's AC5a rule above)

| Gate | Criterion | Result | Verdict |
|---|---|---|---|
| 1 — Hard ship ceiling (`STUDY-SPEC.md` §10) | FP rate ≤ 6%/slot | OpenWSFZ 5.83%/slot (7/120) | **PASS** (margin 0.17 pp) |
| 2 — Regression vs. D-009 baseline | 95% CIs overlap; no significant difference | Baseline 4.17% [1.79%, 9.38%] vs. new 5.83% [2.85%, 11.55%] (Wilson); Fisher's exact p = 0.77; two-proportion z-test p = 0.55 | **PASS** — no statistically significant regression |

Both pre-committed AC-4 gates **PASS**. H₀₁ and H₀₂ (§1) are both **not refuted**.

## Summary

| Metric | Scope | Value | Verdict |
|---|---|---|---|
| FP event rate | S5/WSJT-X | 0/120 slots (event 0.0%; 95% UB ≤ 2.50%; decode 0.0%) | PASS |
| FP event rate | S5/OpenWSFZ | 7/120 slots (event 5.8%; decode 5.8%) | FAIL |

**Overall verdict: FAIL**

> This "Overall verdict" and the Defect Notice below are `analyse.py`'s raw, unedited
> output against its own in-code AC5a zero-tolerance rule — retained here verbatim for
> traceability, not because it is the applicable gate. The actual D-011 AC-4
> determination uses the two pre-committed gates evaluated above (both **PASS**); see
> §5 for the recommended disposition of the AC5a/§10 conflict itself.

### Defect Notices

- ❌ FAIL — FP event rate (OpenWSFZ) = 7 events in 120 slots (5.8% event rate; 5.8% decode rate); gate requires 0 events

## 5. Recommendations

| # | Finding | Defect / Ticket | Hypothesis | Next diagnostic step |
|---|---|---|---|---|
| 1 | Both pre-committed AC-4 gates PASS, but the hard-ceiling margin is thin (5.83% vs. 6.00%, 0.17 pp) and the point estimate rose 40% relative over baseline (4.17% → 5.83%), even though the increase is not statistically significant at N=120. | D-011 | N=120 is a "confirmatory," not fully decisive, sample size (consistent with the original resume-note caveat: at N=120 there is meaningful probability of failing to detect a real but moderate rate increase). A larger N cannot be ruled out as clarifying a real (if small) upward shift. | If tighter certainty is wanted before merge, re-run at N=300–500 slots (rule-of-three / CI width scale roughly with √N). Otherwise: merge is defensible on the numbers as measured, decision is the Captain's. |
| 2 | `harness/analyse.py`'s `_verdict_fp()` enforces a zero-tolerance FP gate ("event count must be 0"), contradicting the architect-ratified ≤6% threshold in `STUDY-SPEC.md` §10. The code comment asserts the 6% threshold was "retired" but §10 was never amended, unlike the properly-dated 2026-06-06 Kappa-gate downgrade note in the same section. | Process / governance — filed as **[R&R-004 (GitHub #32)](https://github.com/frank001/OpenWSFZ/issues/32)** | An unratified gate tightening was committed to the harness without a corresponding `STUDY-SPEC.md` §10 amendment, meaning every run since that change has been evaluated (and reported "FAIL") against a gate the Architect never signed off on. | Architect to either (a) ratify the zero-tolerance gate and amend §10 with a dated note (as was done for Kappa), or (b) revert `_verdict_fp()` to the ratified ≤6% threshold. Until resolved, treat `analyse.py`'s printed "Overall verdict" as informational only, not authoritative — as done in this report. |
| 3 | WSJT-X version was not recorded this run (`report.md` field shows "unknown"). `STUDY-SPEC.md` §11 requires pinning it in every report header. | Process (minor) | Harness does not currently query WSJT-X's version programmatically (no remote API). | Record WSJT-X version manually pre-run per `RUNBOOK.md` §2, or file a small enhancement to prompt for it at harness start. |

**Overall recommendation:** No defect is being raised against the D-011 fix itself —
both pre-committed AC-4 gates pass. Recommend merge subject to the Captain's judgement
on finding #1's thin margin, and independently opening a process ticket for finding #2
(the AC5a/§10 gate conflict), since that conflict predates and is orthogonal to D-011.
