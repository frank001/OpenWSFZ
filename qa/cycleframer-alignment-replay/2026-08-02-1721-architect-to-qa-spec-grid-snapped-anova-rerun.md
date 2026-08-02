# Architect → QA — execution spec: grid-snapped ANOVA re-run (Captain-authorised)
# The naive version of this re-run produces a WORSE lie than the one it fixes. Read §2 first.

**Author:** Architect, 2026-08-02 (17:21 UTC, `date -u`, per HK-017). Repo at `a2fa608`.
**For:** QA, to execute. **Authorised by the Captain** this session: re-run approved; the
density question (QA §6.3) deferred until this completes; the jt9 re-decode (QA §6.2) dropped.
**Reads with:** `2026-08-02-1714-architect-to-qa-correction-cycle-grid-artefact-voids-8080-anova.md`,
which this spec assumes in full.

---

## 0. One correction to my own correction, before anything else

My §3 ruled QA's §3.1/§3.3 tables **VOID**. That was too strong, and the data says so.

Recomputing the 8080-vs-WSJT-X comparison restricted to the on-grid stratum reproduces QA's
table almost exactly — gap **+5.44 dB** vs QA's **+5.43 dB**, 8080 mean SNR **−7.890** vs
**−7.923**, n = 61,867 vs 64,275.

**The arithmetic was never wrong. The label was.** Those tables are valid results for the
low-drift stratum and invalid only as whole-run claims. Corrected verdict:

| QA § | old verdict | corrected verdict |
|---|---|---|
| §3.1 | VOID | **VALID for the +0s stratum only** — must be relabelled, not recomputed |
| §3.3 | VOID | **VALID for the +0s stratum only** — same |
| §4 | VOID as reasoning | unchanged — still cannot corroborate across two co-biased legs |
| §3.2 | STANDS | unchanged |

QA loses no work. What was missing was the stratum label and the two tables either side of it.

## 1. What the re-run must produce

Three tables, not one. Each answers a different question and only one of them is about the decoder.

| # | table | population | question it answers |
|---|---|---|---|
| **A** | recall / match counts, grid-snapped | whole run | did 8080 *find* the decodes? |
| **B** | SNR / DT / freq ANOVA | **+0s stratum only** | how do the appraisers' reported values compare, uncorrupted? |
| **C** | SNR / DT / decode-ratio vs drift offset | stratified +0 / +1 / +2 | what does the drift defect cost? |

## 2. ⚠️ The trap — do not pool the strata

A grid-snapped ANOVA that pools all three drift strata is *more* misleading than the table it
replaces, because the drifted decodes carry genuinely degraded SNR and DT (correction §2.3):

| grid-snapped 8080 vs WSJT-X | n | 8080 SNR | WSJT-X SNR | gap |
|---|---:|---:|---:|---:|
| **POOLED — do not report** | 171,574 | −15.012 | −1.689 | **+13.32 dB** |
| +0s stratum | 61,867 | −7.890 | −2.452 | **+5.44 dB** |
| +1s stratum | 74,781 | −18.620 | −1.092 | +17.53 dB |
| +2s stratum | 34,926 | −19.899 | −1.615 | +18.28 dB |

The pooled row would read as "OpenWSFZ's decoder is 13 dB worse than WSJT-X." It is not. That
number is a weighted average over drift regimes, and its weights are **this run's restart
schedule** — an operational accident, not a property of anything. Restart 8080 hourly and the
same corpus reports ~+5.4 dB; never restart it and it reports ~+18 dB.

**Rule: no pooled cross-stratum mean of SNR or DT is to be reported for 8080, in any table,
without the stratum breakdown printed immediately beside it.**

## 3. Table C is already half-measured — and the finding is a threshold, not a gradient

Using 8081 as a same-instant, same-antenna, zero-drift control so propagation is common-mode
(per the Captain's splitter fact — the only hardware variance is FT-991A vs SDR Uno):

| 8080 drift | matched cycles | 8080/8081 decode ratio | vs +0s |
|---|---:|---:|---:|
| +0s | 3,617 | 0.963 | — |
| +1s | 4,107 | 0.977 | +1.5% |
| +2s | 2,690 | **0.677** | **−29.7%** |

**The damage is a cliff, not a slope.** Up to ~2 s of drift the decode count is unaffected
(+1.5% is noise, and the sign is wrong for a gradient). At +2 s it collapses by ~30%.

Note this **must** be computed against the 8081 control, not on raw per-cycle counts. Raw counts
give +5.3% at the +1s stratum and −24.3% at +2s, because drift strata correlate with
hours-since-restart, which correlates with time of day, which is propagation. The 8081 control
removes that; raw counts do not. Do not shortcut this.

Two open questions for Table C, neither of which QA should resolve by reasoning:
1. **Is the ~10 dB SNR drop real signal loss or a reporting error?** `DEFECT-snr-reported-gain-error.md`
   exists and may be implicated. At the +1s stratum SNR falls ~10 dB while the decode count does
   not move at all — those two facts are hard to reconcile with pure signal loss. Measure, don't argue.
2. **Is the true drift continuous with a floored label?** Reconstructing DT by adding the integer
   offset back gives +0.33 / +0.42 / +0.76 across strata — not the flat line a clean integer
   model predicts. Worth one plot before anyone builds on it.

## 4. Method — mechanical, per HK-021

**Grid-snap:** floor each timestamp to the enclosing 15-second boundary.
`tot = h*3600 + m*60 + s;  tot -= tot % 15`. Floor, not round — the drift is one-directional
(late), so rounding would move the +2s bucket into the wrong cycle entirely.

**Stratum assignment:** `offset = original_seconds mod 15`, taken from the *unsnapped* timestamp,
carried alongside each row as a factor.

**Gate, run first and reported at the top of every output** (correction §6):
```
G(L) = count(unique ts where seconds mod 15 == 0) / count(unique ts)
ROW 1:  G >= 0.99  ⇒ PASS — pool freely, no stratification needed.
ROW 2:  0.99 > G   ⇒ STRATIFY — every SNR/DT figure carries its stratum, no pooled mean.
```
Expected: WSJT-X 1.000 → ROW 1. 8081 0.998 → ROW 1. 8080 0.347 → ROW 2.

**Tooling:** `endurance_anova_two_alltxt.py` already takes a required `--method-note`, which is
the right place for the stratum label. Adding `--snap-grid` and `--stratum` flags to
`anova_common.py` is qa-tooling scope, so it needs no Developer session (HK-011) — but the
existing `match_pairs()` is **correct as written** and should keep its exact-key behaviour as the
default. Snapping is an opt-in for corpora that fail the gate, not a new default; silently
snapping everywhere would destroy the very signal that caught this.

**Every output file and every table header must carry the stratum and the word "grid-snapped."**
An unlabelled grid-snapped number is how this recurs.

## 5. Stop-line — what this authorisation does NOT cover

I deliberately did not compute the 8080-vs-WSJT-X **recall ratio** while preparing this spec,
though it was one line away and I had the data open.

That ratio is the D-001 **Angle 1 baseline-deficit decomposition** — "is OpenWSFZ missing
decodes, or was the signal not there?" — and the TODO file requires it to be pre-registered
*before* the data is read (the S.1 precedent). Table A above will make it trivially computable.
**It is still not authorised, and QA should not compute it as a by-product of Table A.**

I enforced this discipline on QA in my correction. It applies to me identically, and the fact
that the answer is now cheap is exactly the circumstance the rule exists for.

If the Captain wants Angle 1, I will write the pre-registration first, against Table A's shape
but not its values.

## 6. Expected outcome, stated in advance

So the result cannot be reverse-fitted after the fact:

- Table A recall recovers to **~93%** on both 8080 pairings (measured: 92.8% vs WSJT-X, 93.5% vs
  8081). If it comes back materially below ~90%, something in the snap is wrong — escalate rather
  than report.
- Table B reproduces QA's existing §3.1/§3.3 numbers within rounding. If it does not, the stratum
  filter is wrong.
- Table C shows a threshold at +2s, not a gradient.

If all three land as predicted, the corpus is sound and the run's value is recovered — and the
density question (QA §6.3) becomes answerable, with its own pre-registration.

## 7. Cross-references

- `2026-08-02-1714-…-correction-cycle-grid-artefact-voids-8080-anova.md` — the mechanism; §0 above amends its §3.
- `2026-08-02-1702-qa-to-architect-…-anova-and-segment-check.md` — the tables being relabelled.
- `qa/endurance/anova_common.py:170` — `match_pairs()`; keep the exact-key default.
- `DEFECT-snr-reported-gain-error.md` — candidate for §3's open question 1.
- `three-decoder-antenna-split-run-2026-07-31-todo.md` — Angle 1, still pre-registration-gated (§5).

---

*Per HK-015 this is Architect → QA: material for QA to scope and execute; the `dev-tasks/` entry
for the drift defect remains QA's to author. Per HK-014/HK-010 committed locally, no push, no
merge, and I do not ask for one. Per HK-011 §4's tooling changes are qa-scope, not `src/`. Per
HK-017 filename and byline carry real `date -u` UTC. Per HK-018 §0, §2 and §3 are measured from
the corpus, not reasoned — §0 in particular overturns my own ruling of three hours earlier. Per
HK-021 §4's gate is mechanical with a hard threshold and ordered exclusive rows. Per HK-022 §2
exists because the pooled number would have been green, large, and pointed at the wrong question.
NFR-021: aggregates and counts only.*
