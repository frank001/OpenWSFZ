# D-001 MEASUREMENT D — within-band density stratification
# Architect → QA specification. Authorised by the Captain, 2026-07-31.
# This is the arm that separates "competition" from "20m specifically" and ungates the row 4
# decomposition. It needs no new data, no decoding, and no `src/` change.

**Author:** Architect, 2026-07-31 (08:53 UTC, `date -u`, per HK-017). Repo at `881cdc9`.
**For:** QA to implement, run, read, and write up. The result document is QA's, not mine.
**Authorisation:** the Captain, 2026-07-31, on §1.4 of
`2026-07-31-0029-architect-ruling-measurements-abc-and-drift-root-cause.md`.
**Status of the reading rule:** pre-registered below and **fixed now, before QA's run**. Per the
closing handoff §4.3 template it must be quoted verbatim in QA's write-up and must not be edited
after results are seen.

---

## 0. Disclosure — read this first

I began implementing and running this measurement myself before the Captain redirected me to
specify it instead. That was my error: executing an authorised measurement arm is QA's role, not
the Architect's (HK-015), and the Architect writing, running, *and* reading a measurement removes
the independent check that this thread's process depends on. The script and its output have been
deleted and nothing was committed.

**I have seen an exploratory result, and I am deliberately not stating it here.** Publishing my
numbers would anchor QA's reading and reduce this run to a formality — a pre-registered rule read
by someone who already knows the answer is not pre-registered in any meaningful sense. I hold the
figures; the Captain has them; they will be compared against QA's once QA's run is complete and
written up. **If QA's result and mine disagree, that disagreement is itself a finding and must be
chased, not reconciled quietly.**

What I *have* carried across from that attempt is the part that is legitimately mine to give: the
design detail below, including three confounds and one artefact that only became visible in
implementation. §3's checks exist because of them. The spec is stronger for it; the reading is
still QA's to take blind.

## 1. Purpose

Measurement A established that 20m recalls 10–35 points below 10m and 80m at matched reference
SNR. It could not say **why**, because band identity and band density are fully confounded across
corpora: three bands means three densities, three antennas, three propagation environments, three
spectral characters, three dial frequencies. And A's curves are **not ordered by density**
(`80m ≥ 10m` fails in 10 of 26 bins), so a density law is not what A measured.

This measurement breaks the confound by stratifying **inside a single band**. 20m's own cycles
vary in density by p90/p10 = 2.23. Comparing dense 20m cycles against sparse 20m cycles at
matched reference SNR holds every band-specific factor constant, because it is the same band, the
same antenna, the same receiver, the same session.

| if… | then… |
|---|---|
| recall falls with per-cycle density **inside** the band | competition is real and general — it is not about 20m |
| recall is flat across 20m's own density range | the cross-band effect is **20m-specific**; the density law is withdrawn entirely |

Either outcome ungates the row 4 decomposition, because either one names the target.

## 2. Design

**Corpora** — all three jt9-referenced bands from `artefacts/20260729_live_run_1831-8081/owsfz/`:
`{20m,10m,80m}/ALL.TXT` (ours) against `{20m,10m,80m}/jt9_ALL.TXT` (reference).

- **20m carries the decisive reading.** It is the only band with both the absolute density and
  the internal density range to support it.
- **10m and 80m are replication**, run because they are free. They are reported, **not read** —
  their verdicts do not override or dilute 20m's.

**Steps:**

1. Compute each cycle's density = **the reference decoder's** decode count for that cycle.
2. Rank cycles by that density. **Sparse stratum** = bottom quartile of cycles; **dense stratum**
   = top quartile. Quartiles of *cycles*, not of decodes.
3. Within each stratum, bin the reference decodes by **the reference's own reported SNR**, 2 dB
   bins — never by OpenWSFZ's SNR (the §7 gain error, slope 0.6865, would re-enter as noise).
4. Per bin per stratum: recall = matched / total, with 95% Wilson intervals.
5. Compare the two strata bin-by-bin over their common support, `n ≥ 20` per bin per stratum.
   Report `diff(b) = recall_sparse(b) − recall_dense(b)` in percentage points.
6. Reuse **`anova_common.py`'s existing normalisation and matching logic — reused, not
   reimplemented**, exactly as Measurement A did.

**Four design constraints that are not optional.** Each of these is a way to get a large, clean,
entirely spurious answer:

- **Density must be defined from the reference decoder, never from ours.** Using our own decode
  count to rank cycles is circular — cycles we did badly on would be labelled sparse by
  construction, and the measurement would report its own definition back as a finding.
- **Matching must be resolved in a single pass over the full corpus**, with the stratum filter
  selecting only which reference rows enter the bins. If matching is re-resolved per stratum, the
  greedy multiplicity handling behaves differently in each and the strata stop being comparable.
- **Bin by reference SNR** (step 3). Stated twice deliberately.
- **The strata must not be re-cut after seeing the result.** Quartiles are fixed here, in advance.
  If QA judges a different cut is required, that is a change to this spec and comes back to me
  before the run, not after.

## 3. Mandatory self-checks — all four before any reading is taken

If any fails, the run is **void** and the reading is not taken.

| # | check | bar |
|---|---|---|
| 1 | **Matching gate** (inherited from S5.2) — full-corpus matched count per band reproduces the published ANOVA figure | **exactly** 20m = 24 201, 10m = 9 177, 80m = 8 290 |
| 2 | **Density contrast achieved** — report mean reference decodes/cycle for each stratum, per band | report it; a contrast below ~2× on 20m means the strata are too close to read |
| 3 | **Duplicate-key artefact** — dense cycles carry more repeated messages, and the matcher is greedy, so a denser stratum can show lower recall for purely clerical reasons. Measure the duplicate-key rate in each stratum | report both rates. If the dense-minus-sparse duplicate-rate gap is **within an order of magnitude of the observed recall difference**, the result is confounded and must not be read |
| 4 | **Common support** — number of usable bins (`n ≥ 20` both strata) per band | report it; fewer than ~10 usable bins on 20m means insufficient support |

Check 3 is the one I would not have thought to specify without implementing it. It is cheap and
it is the single most likely way this measurement produces a false positive.

## 4. Reading rule — **pre-registered, fixed before the run**

Let `diff(b) = recall_sparse(b) − recall_dense(b)` in percentage points, over usable bins.
**Evaluated in strict order; the first row that matches is the outcome.** No two rows can both
fire — the overlap in Measurement A's rule between "≥10 pts, monotone" and "or non-monotone" is
the drafting defect this ordering exists to prevent, and that one was mine.

| # | condition | reading | consequence |
|---|---|---|---|
| **1** | median `diff` **≥ 8 pts** AND **≥ 80%** of usable bins have `diff ≥ 8` | At the same signal strength we miss more when the band is busier, with band identity held constant. | **Competition confirmed as a named, measured mechanism.** Row 4's decomposition re-scopes toward it. **Escalate to the Captain before any engineering.** |
| **2** | else if **−3 < median `diff` < 3** | Density does not act within a band. | **The cross-band effect is 20m-specific and the density law is withdrawn entirely.** Row 4's target reverts to sensitivity/front-end. The 20m deficit becomes its own bounded question. |
| **3** | else if median `diff` **≤ −3** | Sparse recalls *worse* than dense. Not anticipated by any current model. | **Escalate. Do not rationalise it in the findings document.** |
| **4** | else | Partial. | **Report as ambiguous. Do not interpret.** Escalate. |

**The reading is taken on 20m.** 10m and 80m verdicts are reported alongside and are explicitly
**not** part of the decision. No other reading is authorised.

**One instruction about how the verdict is produced.** If QA's harness prints a mechanical verdict
line, that line is an input to QA's judgement, not a substitute for it. Measurement A's script
printed "monotone" from a two-band check and the write-up's human observation — which was correct
— was overridden by it. **Report any disagreement between the printed verdict and what the per-bin
table plainly shows**, rather than deferring to the script.

## 5. What to report

The write-up is QA's and its shape is QA's, but it should carry: the four self-check results; the
per-band strata definitions with achieved contrast; the full per-bin table for 20m (sparse recall,
dense recall, both `n`, both CIs, `diff`); the same for the two replication bands; the reading
rule quoted verbatim; and the mechanical outcome.

**Two things worth computing while the data is open**, because they cost nothing and bear directly
on the mechanism if row 1 fires:

- **Effect size against density contrast, across all three bands.** If the effect scales with the
  *ratio* between strata, it is a density law. If it scales with *absolute* density — appearing
  only where occupancy is high — it is a threshold, which is a different mechanism and a different
  engineering target. The three bands span both axes and the comparison is free.
- **Our decodes per cycle against the reference's, bucketed.** If our per-cycle output flattens
  while the reference's keeps rising, that is a capacity ceiling and it is visible in one table.

Both are **descriptive and not subject to §4's rule** — they inform the mechanism question, they
do not decide it, and neither may be read as a finding on its own.

## 6. Cost

| item | estimate | basis |
|---|---|---|
| compute | **seconds** | same parse as Measurement A (0.06 s per 50k rows), no decoding, no WAVs |
| script | ~150 lines reusing `anova_common.py` | Measurement A's script is the template |
| self-checks + report + write-up | the bulk of it | |
| **total** | **half a QA session** | dominated by writing, not running |

## 7. Boundaries

- **Does not touch `src/` or native code** (HK-011). Read-only analysis of committed artefacts.
- **Does not authorise any further arm.** In particular, if row 1 fires and §5's descriptive
  extras point at a capacity ceiling, the follow-up (re-running the c1 candidate-cap sweep in a
  dense regime, counting our decode passes against jt9's `-d 3`) touches native rebuilds and is a
  different cost class. **It comes back to the Captain, priced, and is not started off the back
  of this run.**
- **Does not re-open the diagnostic programme** (closing handoff §0). One arm, one stop rule.
- **NFR-021:** message text is read only to build match keys, as `anova_common.py` does, and is
  never printed or written out. Aggregate counts only.
- **No push, no merge** (HK-014/HK-010). **No `pre_merge_check.py`** (HK-006) — Captain's trigger.

## 8. Cross-references

- `2026-07-31-0029-architect-ruling-measurements-abc-and-drift-root-cause.md` §1.4 — the ruling
  that recommended this arm, with the power calculation (20m p90/p10 = 2.23, ~13 pt predicted
  effect from the between-band fit, ~8 000 matched decodes per stratum).
- `2026-07-30-2337-qa-measurement-a-result-co-channel-reverses.md` §4 — QA's own observation that
  20m may differ from the other two bands specifically, which is the question this settles.
- `measurement_a_snr_recall.py` — the template: matching reuse, Wilson intervals, binning,
  self-check gate, reading rule embedded in the docstring.
- `qa/endurance/anova_common.py` — `normalize_hash_tokens` / `match_pairs`; reuse, do not
  reimplement.
- `2026-07-26-c1-candidate-cap-sweep-findings.md` — relevant only if §5's ceiling table fires;
  note its corpus sat at ~19 reference decodes/cycle, which is **not** the dense regime.

---

*Per HK-015 this is Architect → QA material: I specify, QA implements, runs, reads and writes up.
Per HK-014/HK-010 committed locally, no push, no merge. Per HK-011 nothing here touches `src/`.
Per HK-017 filename and byline carry mechanically-derived `date -u` UTC — note the ~8 h gap from
the `0029` ruling is real elapsed time, not a typo. §0 discloses that I ran a version of this
myself before being redirected, and why the figures are withheld from this document.*
