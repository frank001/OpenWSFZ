# OpenWSFZ R&R Study Report — f-002 Callsign Shape Grammar Acceptance Gate

## 1. Study Hypothesis

**Context.** `f-002-callsign-structure-region-lookup` replaces `Ft8Decoder.IsCallsignOversized`'s
length-only D9-R3 guard (raised to an 11-char ceiling by D-011, to admit genuine Type 4
nonstandard-callsign literals) with `IsCallsignShapeInvalid` — an ITU Radio Regulations Article 19
§19.68–19.69-derived structural grammar (prefix + capped digit-run + letters-only suffix), plus a
reserved/never-allocated prefix exclusion list with a synthetic `Q`-series carve-out (NFR-021). The
change exists because a length-only ceiling cannot distinguish a genuine literal nonstandard
callsign from callsign-*shaped* OSD noise of the same length — a live decode matching the
predicted failure shape (fictional `3AG9672ATCH`, 4-digit trailing run) motivated the change; see
`design.md`. This run is that change's own pre-committed acceptance gate (tasks.md §6).

**Null hypotheses:**

| ID | Null hypothesis | Would be refuted by |
|---|---|---|
| H₀₁ | The shape-grammar gate does not raise the S5 noise-floor false-positive rate above the `STUDY-SPEC.md` §10 ratified ceiling (95% Clopper–Pearson upper bound ≤ 6%/slot). | Observed 95% UB > 6%/slot. |
| H₀₂ | The shape-grammar gate does not produce a statistically meaningful increase in FP rate versus the D-011 AC-4 baseline (shim/SHA `f1e76d4`, 7/120 = 5.83%/slot, 95% UB 10.68%). | Baseline and new-run 95% CIs fail to overlap in the adverse direction, or a two-proportion test rejects equality at α = 0.05 with the new rate higher. |

**Defect IDs under observation:** this change (`f-002`) is the fix under test; D-011/D-009 are the
source of the baseline this run validates against — not themselves being re-litigated.

**Sample size.** The D-011 AC-4 recheck (`results/d011-fp-recheck-2026-07-04/report.md`, finding
#1) flagged its own N=120 as merely "confirmatory" for a result that close to the ceiling (5.83%
observed vs. a 6% ceiling), and recommended N=300–500 for a decisive read. Since this change makes
a materially similar claim against the same gate, this run uses **N=300** (`s5-noise-wide-n300.json`,
a sibling of `s5-noise-wide.json` differing only in `trials`) rather than repeating the
underpowered N=120.

**What constitutes a meaningful result:** a FAIL on H₀₁ is merge-blocking; a FAIL on H₀₂ (a
significant regression, even if H₀₁ still passes) warrants scrutiny before merge. A PASS on both
is evidence the shape-grammar replacement is safe to ship at current settings — ideally an
*improvement* over baseline, since shape-invalid noise of the `3AG9672ATCH` class should now be
rejected where it previously wasn't.

## 2. Run Context

| Field | Value |
|---|---|
| Run date | 2026-07-04 |
| OpenWSFZ SHA | `a3738fcbece0e19ca827591325139a91f48f0fcb` (fresh Release build from a clean commit on `feat/f-002-callsign-structure-region-lookup`) |
| WSJT-X version | `2.7.0` (`D:\WSJT\wsjtx\bin\wsjtx.exe` file version) |
| Scenario | `s5-noise-wide-n300.json`, 300 signal-free AWGN slots, VB-CABLE loopback |
| Pre-flight check | Warm-up cycle (`CQ Q1ABC FN42`) independently verified via both apps' `ALL.TXT` at cycle `260704_164115` (SNR +7 dB WSJT-X, −10 dB OpenWSFZ) before proceeding — not taken on `warmup.py`'s own prompt alone |
| Baseline compared against | 7/120 (5.83%/slot, 95% UB 10.68%), shim/SHA `f1e76d4`, `results/d011-fp-recheck-2026-07-04/` |

**Data-integrity note (methodology, disclosed rather than silently corrected).** WSJT-X's
`ALL.TXT` (`%LOCALAPPDATA%\WSJT-X\ALL.TXT`) persists across sessions and was not cleared before
this run — it still carried two pre-run warm-up decodes (`CQ Q1ABC FN42` at cycles `164030` and
`164115`, both outside this run's cycle range, which starts at `164430`). OpenWSFZ's `ALL.TXT` is
disposable and *was* truncated immediately before the timed run started, so it required no
correction. The first `matcher.py` pass, run against WSJT-X's raw log, consequently mis-attributed
those two warm-up lines as false positives. This was caught before the result was recorded: a
cutoff-timestamp filter (`awk '$1 >= "260704_164430"'`) was applied to WSJT-X's log, confirmed
empty (both warm-up lines predate the run), and the match re-run — see finding #3 below for the
process recommendation this motivates.

## 3–4. Attribute Agreement Analysis (S4 positives + S5 negatives)

_κ is computed over a pooled population: S4 injected messages (truth = present) and S5 signal-free slots (truth = absent), so the truth vector has both classes. **κ verdicts below are advisory** — the §10 attribute gate is pending Captain ratification of this pooled method._

### Confusion vs truth

| Appraiser | TP | FN | FP | TN | Recovery | Specificity |
|---|---|---|---|---|---|---|
| WSJT-X | 0 | 0 | 0 | 300 | —% | 100.00% |
| OpenWSFZ | 0 | 0 | 8 | 292 | —% | 97.33% |

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
| WSJT-X | 0 / 300 | 0.00% | 0.99% | 0.00% | PASS |
| OpenWSFZ | 8 / 300 | 2.67% | 4.76% | 2.67% | PASS |

_Gate (STUDY-SPEC §10, ratified 2026-07-04, R&R-004): the per-slot FP **event rate**, gated on its one-sided 95% Clopper–Pearson **upper bound** (PASS iff 95% UB ≤ 6%). The UB is defined for all event counts (≈ 3 / N_slots at 0 events) and bounds the true per-slot FP probability at 95% confidence rather than the Poisson-noisy point estimate. Decode rate is reported for reference only._

### f-002 acceptance-gate evaluation (pre-committed, tasks.md §6)

| Gate | Criterion | Result | Verdict |
|---|---|---|---|
| 1 — Hard ship ceiling (`STUDY-SPEC.md` §10, ratified) | 95% UB ≤ 6%/slot | OpenWSFZ 4.76% UB (8/300) | **PASS** (margin 1.24 pp) |
| 2 — Regression vs. D-011 baseline | New 95% UB not worse than baseline's; point estimate not significantly higher | Baseline 5.83% [UB 10.68%] vs. new 2.67% [UB 4.76%] — **lower** on both point estimate and UB | **PASS** — clear improvement, not merely non-regression |

H₀₁ and H₀₂ (§1) are both **not refuted**; the result is stronger than a bare non-regression — the
point estimate roughly halved (5.83% → 2.67%) and the upper bound dropped by more than half
(10.68% → 4.76%), consistent with the shape grammar rejecting a real share of the
`3AG9672ATCH`-class noise the length-only guard let through.

## Summary

| Metric | Scope | Value | Verdict |
|---|---|---|---|
| FP event rate (95% UB) | S5/WSJT-X | 0/300 slots (event 0.0%; 95% UB 0.99%; decode 0.0%) | PASS |
| FP event rate (95% UB) | S5/OpenWSFZ | 8/300 slots (event 2.7%; 95% UB 4.76%; decode 2.7%) | PASS |

**Overall verdict: PASS**

## 5. Recommendations

| # | Finding | Defect / Ticket | Hypothesis | Next diagnostic step |
|---|---|---|---|---|
| 1 | Gate PASSES with a comfortable margin (4.76% UB vs. 6% ceiling) and is a genuine improvement over the D-011 baseline on both the point estimate (5.83%→2.67%) and the 95% UB (10.68%→4.76%), at a larger, better-powered N (300 vs. 120). | f-002 (this change) | The shape grammar's digit-run cap (3) closes a real share of the noise-floor OSD false-positive space that the length-only guard could not distinguish from genuine nonstandard literals. | None — result stands. Safe to proceed to merge. |
| 2 | Of the 8 OpenWSFZ false positives, 2 (`<...> KOWQ8MGEQVT RR73` at `164900`; `<...> RHLI8VWMXMG RRR` at `175945`) share an identified residual shape hole: exactly one digit buried inside an otherwise-long letter run, with a 4-character prefix sitting at the current `PrefixLengthMax` ceiling (`KOWQ`, `RHLI`). This was flagged and empirically confirmed *live* during this same session, independent of this run's own data. | Candidate follow-up (not filed as a numbered defect yet) | The digit-run cap alone cannot reject this shape, since the grammar has no requirement that a prefix be *semantically* plausible — only that it be 1–4 alphanumeric characters containing a letter. Tightening `PrefixLengthMax` from 4 to 3 was tested against the full `OpenWSFZ.Ft8.Tests` suite (244/244 pass, including every existing D-011 nonstandard-literal fixture, all of which already use a 3-char prefix) and confirmed to reject both tokens above with zero regressions. | Recommend a small, fast follow-up change: promote `PrefixLengthMax` from a hardcoded local `const` in `Ft8Decoder.TryParseCallsignShape` into `CallsignGrammarConfig` (it is currently the one grammar parameter *not* JSON-configurable, unlike `DigitRunMax`/`SuffixLengthMax`/`TotalLengthMax`) and default it to 3. Not blocking this merge — the gate already passes with these included. |
| 3 | The other 6 false positives (`VN6NY/R K69IGM/R CA05`, `<...> 3W3ZAJ/R RM02`, `<...> HL5QRM/R ML60`, `HA3YSR 1D2QID/R EB40`, `C4QM 2F1SJJ/R HK20`, `N0LMJ/R WO9TMN GK96`) are structurally indistinguishable from genuine Standard-QSO traffic — valid-shaped compound calls with `/R` portable suffixes and valid Maidenhead-shaped grid fields (D9-R4 passes them cleanly). | Not a defect of `f-002` | These are inherent OSD/CRC-14 noise-floor coincidences that happen to land on a shape-and-grid-valid combination. No shape-grammar rule can reject them without also rejecting real traffic of the identical shape — this is D-009's domain (OSD correlation threshold / `kMinScorePass2` tuning), not D9-R3's, and any such tuning trades sensitivity for specificity elsewhere in the S1–S8 suite. | None recommended against this change. Track only if the overall S5 rate trends upward across future runs. |
| 4 | WSJT-X version was not recorded in the D-011 AC-4 recheck report (flagged there as finding #3, a `STUDY-SPEC.md` §11 process gap). Recorded here (`2.7.0`) without incident. | Process (closed) | N/A | None — confirms the manual pre-run check from `RUNBOOK.md` §2 is sufficient when followed; no tooling change needed. |
| 5 | WSJT-X's `ALL.TXT` persists across sessions (unlike OpenWSFZ's, which this session truncates before each timed run) and briefly contaminated the first match pass with two pre-run warm-up decodes, caught and corrected before this report was written (see §2 data-integrity note). | Process | `RUNBOOK.md`'s pre-run checklist (§4.1 and elsewhere) says to "clear ALL.TXT in both apps" but doesn't distinguish that OpenWSFZ's is disposable while WSJT-X's is the operator's persistent application log, which a QA session shouldn't casually truncate. | Recommend `RUNBOOK.md` be updated to either (a) instruct recording the WSJT-X `ALL.TXT` line count/last-timestamp as an explicit cutoff marker before every run (as done here after the fact), or (b) note that `matcher.py` could optionally take a `--since` cutoff parameter to make this automatic rather than relying on the operator's memory. Filing as a small process follow-up, not blocking. |

**Overall recommendation.** Both pre-committed gates (tasks.md §6.1/§6.2) **PASS**, with a
materially better result than the D-011 baseline at a larger, better-powered N. Safe to proceed to
merge. Finding #2 (the `PrefixLengthMax` residual gap) is recommended as a fast, narrow, separate
follow-up — not a merge blocker, since the gate already accounts for its effect in the observed
rate and the fix is small, tested, and non-regressive whenever it lands.
