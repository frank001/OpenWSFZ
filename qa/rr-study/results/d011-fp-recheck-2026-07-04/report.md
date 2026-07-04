# OpenWSFZ R&R Study Report — D-011 AC-4 False-Positive Re-check

> **Revision 2 (2026-07-04, post-run):** the embedded harness block (§3–4, Summary)
> was regenerated after **R&R-004 (GitHub #32)** was resolved — the §10 false-positive
> gate is now ratified as the per-slot event rate's one-sided **95% CP upper bound ≤ 6%**
> (PR #34), superseding both the retired in-code zero-event rule and the point-estimate
> reading of "≤ 6%". Under the ratified gate this run's OpenWSFZ result (UB 10.68%) is a
> **FAIL**. This materially affects pre-committed AC-4 Gate 1 (§1/§3–4) — see the
> post-hoc note there and the updated §5 finding #2. Revision 1 (original run-time
> evaluation, point-estimate reading) is preserved in git history at the run SHA.

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
| WSJT-X | 0 / 120 | 0.00% | 2.47% | 0.00% | PASS |
| OpenWSFZ | 7 / 120 | 5.83% | 10.68% | 5.83% | FAIL |

_Gate (STUDY-SPEC §10, ratified 2026-07-04, R&R-004): the per-slot FP **event rate**, gated on its one-sided 95% Clopper–Pearson **upper bound** (PASS iff 95% UB ≤ 6%). The UB is defined for all event counts (≈ 3 / N_slots at 0 events) and bounds the true per-slot FP probability at 95% confidence rather than the Poisson-noisy point estimate. Decode rate is reported for reference only._

> ✅ **Gate conflict resolved (R&R-004, PR #34, ratified 2026-07-04).** At the original
> run (Revision 1) this row printed against `analyse.py`'s in-code zero-event rule, whose
> authority was disputed against §10's then-point-estimate "≤ 6%" ceiling. R&R-004 has
> since ratified a single §10 gate: the per-slot event rate's one-sided **95% CP upper
> bound ≤ 6%**. Under it, OpenWSFZ's 7/120 result (UB **10.68%**) is a genuine **FAIL** —
> not on the retired zero-event rule, but on the ratified ceiling. See the post-hoc note
> under the AC-4 gate table below and §5 finding #2.

### D-011 AC-4 gate evaluation (pre-committed, not the harness's AC5a rule above)

| Gate | Criterion (as pre-committed / run-time reading) | Result | Verdict (Rev 1) |
|---|---|---|---|
| 1 — Hard ship ceiling (`STUDY-SPEC.md` §10) | FP rate ≤ 6%/slot (point estimate, as §10 stood at run time) | OpenWSFZ 5.83%/slot (7/120) | **PASS** (margin 0.17 pp) |
| 2 — Regression vs. D-009 baseline | 95% CIs overlap; no significant difference | Baseline 4.17% [1.79%, 9.38%] vs. new 5.83% [2.85%, 11.55%] (Wilson); Fisher's exact p = 0.77; two-proportion z-test p = 0.55 | **PASS** — no statistically significant regression |

> **Post-hoc note (Revision 2, R&R-004).** Gate 1 *is* the §10 ceiling — not a separate
> gate — so R&R-004's ratification directly changes how it reads. Evaluated as it stood
> at run time (point estimate ≤ 6%), Gate 1 was a narrow **PASS** (5.83% ≤ 6.00%).
> Evaluated under the **now-ratified** §10 gate (95% CP upper bound ≤ 6%), Gate 1 is a
> **FAIL** (UB 10.68% > 6%). Gate 2 (regression) is unaffected and remains **PASS**.
> D-011 was merged (PRs #30–#32) under the Revision-1 reading; whether the tightened
> gate warrants revisiting D-011 (e.g. a larger-N re-run) is a Captain decision — see §5
> finding #2. This report does not unilaterally reverse the merge; it records the
> changed gate transparently.

Under the Revision-1 (run-time) reading, both pre-committed AC-4 gates **PASS** and
H₀₁/H₀₂ (§1) are both **not refuted**. Under the Revision-2 (ratified §10) reading, H₀₁
(FP rate within the §10 ceiling) is **refuted** on the upper-bound gate while H₀₂
(no regression vs. baseline) still stands.

## Summary

| Metric | Scope | Value | Verdict |
|---|---|---|---|
| FP event rate (95% UB) | S5/WSJT-X | 0/120 slots (event 0.0%; 95% UB 2.47%; decode 0.0%) | PASS |
| FP event rate (95% UB) | S5/OpenWSFZ | 7/120 slots (event 5.8%; 95% UB 10.68%; decode 5.8%) | FAIL |

**Overall verdict: FAIL**

> This "Overall verdict" and the Defect Notice below are `analyse.py`'s regenerated
> (Revision 2) output against the **ratified §10 gate** (95% CP upper bound ≤ 6%,
> R&R-004 / PR #34) — now the applicable gate, not a disputed in-code rule. The FAIL is
> genuine: OpenWSFZ's 95% upper bound (10.68%) exceeds the 6% ceiling. See §5 finding #2
> for the disposition (including the D-011 revisit question).

### Defect Notices

- ❌ FAIL — FP event rate (OpenWSFZ) = 7 events in 120 slots (event rate 5.8%, 95% UB 10.68%); gate requires 95% UB ≤ 6%

## 5. Recommendations

| # | Finding | Defect / Ticket | Hypothesis | Next diagnostic step |
|---|---|---|---|---|
| 1 | Both pre-committed AC-4 gates PASS, but the hard-ceiling margin is thin (5.83% vs. 6.00%, 0.17 pp) and the point estimate rose 40% relative over baseline (4.17% → 5.83%), even though the increase is not statistically significant at N=120. | D-011 | N=120 is a "confirmatory," not fully decisive, sample size (consistent with the original resume-note caveat: at N=120 there is meaningful probability of failing to detect a real but moderate rate increase). A larger N cannot be ruled out as clarifying a real (if small) upward shift. | If tighter certainty is wanted before merge, re-run at N=300–500 slots (rule-of-three / CI width scale roughly with √N). Otherwise: merge is defensible on the numbers as measured, decision is the Captain's. |
| 2 | **RESOLVED.** `harness/analyse.py`'s `_verdict_fp()` enforced an unratified zero-tolerance FP gate, contradicting §10's ≤6% ceiling with no dated amendment. | Process / governance — **[R&R-004 (GitHub #32)](https://github.com/frank001/OpenWSFZ/issues/32)**, resolved via **[PR #34](https://github.com/frank001/OpenWSFZ/pull/34)** (2026-07-04). | Neither option (a) nor (b) as originally posed: the Captain ratified a third, principled option — the §10 FP gate is the per-slot **event rate**, gated on its one-sided **95% CP upper bound ≤ 6%**, with a dated §10 note mirroring the Kappa precedent. The retired zero-event rule and the point-estimate reading are both superseded. | **Done:** §10 amended, `analyse.py`/`analyse_xplat.py` updated (15/15 tests pass), this report's embedded block regenerated (Revision 2). **Open (Captain):** under the ratified gate this run FAILs Gate 1 (§3–4 post-hoc note); decide whether D-011 (already merged) warrants a larger-N re-run or revisit. |
| 3 | WSJT-X version was not recorded this run (`report.md` field shows "unknown"). `STUDY-SPEC.md` §11 requires pinning it in every report header. | Process (minor) | Harness does not currently query WSJT-X's version programmatically (no remote API). | Record WSJT-X version manually pre-run per `RUNBOOK.md` §2, or file a small enhancement to prompt for it at harness start. |

**Overall recommendation (updated Revision 2).** The finding-#2 gate conflict is now
resolved: §10's FP gate is ratified as the 95% CP upper bound ≤ 6% (R&R-004 / PR #34).
Applying that ratified gate to this run changes the bottom line from Revision 1 — Gate 1
(which *is* the §10 ceiling) now **FAILs** (UB 10.68% > 6%), while the regression gate
(Gate 2) still passes. Because the pre-committed Gate 1 and §10 are the same threshold,
this is **not** orthogonal to D-011 as Revision 1 assumed — the earlier "both gates PASS"
conclusion held only under the point-estimate reading in force at run time. D-011 is
already merged (PRs #30–#32); this report does not reverse that. **Escalated to the
Captain:** decide whether the tightened, now-ratified gate warrants revisiting D-011 —
options are (i) accept the merge as-shipped (Gate 1 passed under the reading in force
when it merged) and record the tighter gate as forward-looking only, or (ii) commission a
larger-N (300–500 slot) re-run to measure whether the true FP rate genuinely clears the
6% upper-bound gate before considering the ceiling raise settled.
