# Architect → QA — task 4 closes INCONCLUSIVE. Row 2 rejected, and not for the reason I
# suspended it. The calibration is accepted and clean; the density law simply cannot support
# the inference either row 1 or row 2 requires.
# The defect is in the reading rule I wrote, and it was defective before QA ran anything.

**Author:** Architect, 2026-07-31 (12:12 UTC, `date -u`, per HK-017). Repo at `3dca0a9`.
**For:** QA and the Captain.
**Answers:** `2026-07-31-1207-qa-task4-calibration-result-row2-confirmed.md`.
**Strikes:** `2026-07-31-1030` §3's reading rule (mine, defective as written), and the row 2
determination that rule produced.
**Closes:** task 4.

---

## 0. Summary

| item | ruling |
|---|---|
| QA's §1 catch — Measurement C's parity uses **WSJT-X-live** as denominator, so my offered arm (a) was the wrong instrument | **ACCEPTED.** My `1148` §3 was wrong and re-running both arms fresh with jt9-as-reference was the only correct response |
| The calibration itself, **penalty = +0.15 pt** | **ACCEPTED.** Clean, well-powered, and it delivers a free result worth more than the calibration (§1.2) |
| The same-source/cross-source confound I raised at `1148` §2 | **Measured and dead.** ~0.15 of 6.4 points. My concern was legitimate and empirically wrong |
| **Row 2 — "the two capture chains differ"** | **REJECTED.** Not because of a confound. Because a 3-point fit with 2 fitted parameters cannot discriminate a 6.4-point residual — its 95% prediction interval at 19.81 decodes/cycle is **[50.2%, 76.4%]**, and 56.6% sits comfortably inside it (§2) |
| **Task 4 overall** | **CLOSES INCONCLUSIVE.** The cross-instance claim stays withdrawn — unchanged, and for the same reason as before: **unevidenced**. Not "confirmed different" |

**This is my error, and it predates QA's run.** The reading rule at `1030` §3 asked whether a new
observation lands "materially outside" a curve, without ever establishing that the curve could
predict a new observation. It cannot. Both the confound at `1148` and the statistical defect here
should have been caught when I wrote that rule, not after 2.6 hours of decoding.

## 1. The calibration — accepted, plus one free result

### 1.1 QA's catch on my arm (a) is correct

I offered Measurement C's published 61.4% as an already-measured same-source arm. QA checked
before reusing it and found C computes every row's parity against **WSJT-X's live `ALL.TXT`** as
the denominator — a different reference convention from the one 489135a's recompute and the
density law both use. Substituting it would have compared two reference *decoders* under one
label while purporting to isolate audio *source*. Re-running both arms fresh, jt9-as-reference in
both, on C's exact 150 healthy cycles without re-cutting the stratum, is exactly right.

The related error in my §3 self-check — describing 4 831 as "jt9 decodes on our WAVs" when it is
WSJT-X's live count — is also mine. QA flagging it as a clarification rather than a failure is the
correct handling.

### 1.2 The free result, which outlasts the calibration

| arm | parity | 95% CI |
|---|---:|---|
| (a) jt9 on **our** WAV | 59.1% | [57.8%, 60.5%] |
| (b) jt9 on **WSJT-X's** WAV, same cycles | 59.0% | [57.6%, 60.3%] |

Penalty **+0.15 pt**, CIs overlapping almost entirely. Row 2 of the calibration's own rule
(≤ 2 pts) fires unambiguously.

Note what arm (b) actually contains: our decodes come from **our** audio, jt9's reference from
**WSJT-X's**, with up to 0.5 s of residual misalignment between them. Arm (a) has zero
misalignment by construction. The two agree to 0.15 points. So:

> **Sub-0.5-second capture misalignment costs essentially nothing in matched parity.**

That is a measured constant, it is consistent with the 2.34–2.48 s cliff being a genuine cliff
rather than the end of a ramp, and it independently justifies `|drift| < 0.5 s` as the healthy-
window bar this programme has been using on intuition. **It is the most durable thing task 4
produced.** Cite it in preference to anything else here.

## 2. Why row 2 is rejected — the fit cannot bear the weight

The position-consistency test compares 56.6% against a point prediction of 63.1% from
`parity ≈ 111.9 − 37.63·log₁₀(density)`, fitted on three corpora.

**Three points, two fitted parameters. One residual degree of freedom.** Refitting from the
anchors themselves:

```
refit                     parity = 111.78 − 37.37 · log10(density)
residuals at anchors      −0.42, +0.69, −0.27       s = 0.846 pts on 1 dof
at 19.81 decodes/cycle    point prediction 63.3%
                          SE of a NEW observation   1.032
                          t(0.975, 1 dof)           12.706
95% PREDICTION INTERVAL   [50.2%, 76.4%]
observed                  56.6%–56.7%               → INSIDE, comfortably
```

**A 26-point-wide prediction interval cannot adjudicate a 6.4-point residual.** The observation is
consistent with the density law. It is also consistent with a real cross-chain difference. The
measurement is precise — QA's parity CI is ~1.4 points wide — but **the benchmark is not**, and no
amount of precision on the observation fixes an imprecise predictor.

**Why the anchors' small residuals are not the reassurance they look like.** QA's §5 reasons that
the three anchors sit within 1 point of the line while 489135a sits 6.4 points off, "six to
sixteen times larger." With three points and two fitted parameters, the residuals are **constrained
to be small by construction** — they carry one degree of freedom between them. They describe how
well the line was fitted to the points that defined it, not how well it predicts a point that did
not. This is the standard trap of reading in-sample residuals as out-of-sample accuracy, and the
fit's own slope CI shows the scale of the real uncertainty: **−37.4 ± 14.6**, i.e. [−52.0, −22.8].

**No row of `1030` §3's rule correctly describes this outcome.** Row 3 covers "too few cycles to
bound", which is not the problem — the cycles are ample. The problem is a benchmark with no
discriminating power, which I did not anticipate when writing the rule. That is a defect in the
rule, so the rule does not get applied; it gets struck.

## 3. Where this was already on record — the part that stings

`2253` §3.1, written by me:

> *"Three points, two fitted parameters, one degree of freedom. I am not quoting R² for a
> three-point fit; it would be meaningless. **Monotone across a decade is the honest claim**, and
> it is enough to motivate Measurement A."*

I wrote that, and then five documents later wrote a reading rule that requires the fit to predict a
fourth point to within a few percentage points. HK-018 exists for exactly this: the answer was in
my own document, and I did not open it before writing the rule. Fourth Architect error in this
thread's density-law work, and the most expensive one — it is the one that consumed QA's 2.6 h
decode plus two rounds of escalation.

## 4. The verdict, and task 4 closes

- **The cross-instance claim stays withdrawn** — exactly as it has been since `2253` §R. Its
  status is **unevidenced**, not refuted. Nothing about "the two chains differ" enters the record.
- **The density law's fourth point is neither restored nor refuted.** 489135a's drift-corrected
  parity of 56.6% is compatible with the law and compatible with a real difference. It is not a
  discriminating observation and should not be cited as one in either direction.
- **The point estimate does sit 6.4 points below prediction**, and I am recording that as
  *directionally suggestive and statistically silent* rather than suppressing it. If further
  same-source anchors ever arrive, this observation would become informative retrospectively.
- **Task 4 closes INCONCLUSIVE on its primary question.** Its secondary outputs stand (§5).

**Can it be settled?** Only by adding same-source anchors — each new corpus buys a degree of
freedom and narrows the prediction interval. A same-source measurement of 489135a itself is
impossible: that session archived no OpenWSFZ WAVs, which is what forced the cross-source design
in the first place. **I recommend against pursuing it.** Three or four more corpora to resolve a
question that bears on the row 4 decomposition only indirectly is not a defensible purchase
against the closing handoff §0 stop rule, and Measurement D bears on the same decision far more
directly for a fraction of the cost.

## 5. What task 4 actually delivered — the 2.6 h was not wasted

Only the comparison against the density law is void. Everything else stands:

| output | status |
|---|---|
| **Sub-0.5 s misalignment costs ~0.15 pt** (§1.2) | **Measured constant.** The most valuable output |
| 489135a's drift-free parity, **56.6%–56.7%**, robust across both cutoffs | Stands as a measurement of that corpus. Do not compare it to the density law |
| The **parity-vs-drift curve** (`1137` §4) | Stands, with QA's propagation caveat intact |
| **489135a crossed the cliff in its final hours** (`1137` §3, ruled at `1148` §1) | Stands. My "never crossed it" remains struck |
| **Reference-method by-product** — jt9 vs live WSJT-X agree closely on identical audio (`1137` §6) | Stands. Partially answers `2253` §3.2's open question, on one corpus |
| `anova_report_40m.md`'s **62.4%** | **Un-suspended, and superseded.** The corpus's honest figure is 56.6% drift-free; 62.4% was session-averaged across a drift ramp and a late collapse. Cite neither against the density law |

## 6. Citation blacklist — additions

| do not cite | instead |
|---|---|
| `parity ≈ 111.9 − 37.63·log₁₀(density)` as a **predictive** instrument, or any residual computed against it | **Descriptive of three same-source corpora only.** 1 residual dof; 95% prediction interval at 19.81/cyc is **[50.2%, 76.4%]**; slope CI **[−52.0, −22.8]**. It cannot adjudicate a new point |
| *"489135a's residual is 6.4 pts, therefore the two capture chains differ"* | **Rejected** (§2). Inside the prediction interval. The claim stays **unevidenced**, neither restored nor refuted |
| the three anchors' **<1 pt residuals** as evidence the law is accurate | **In-sample residuals of a 2-parameter fit to 3 points.** Small by construction; they say nothing about predicting a fourth |
| `1030` §3's reading rule (rows 1/2) | **Struck.** Defective as written — it presumes a predictive power the fit does not have |
| *"489135a: degraded, not broken"* ⟨mine, struck at `1148`⟩ | Remains struck; drift(14) = −2.473 s |

## 7. Boundaries

- **No `src/`** (HK-011). **No new arm** — task 4 closes rather than extends; §0's stop rule holds.
- **Does not change the menu** (row 1/4/5) — the Captain's.
- **Does not affect Measurement D**, which is now the only open D-001 measurement and is
  unaffected by any of this: it is a within-corpus comparison and never relies on the density law.
- **NFR-021:** aggregates only. **No push, no merge** (HK-014/HK-010). **No `pre_merge_check.py`**
  (HK-006).

## 8. Cross-references

- `2026-07-31-1207-qa-task4-calibration-result-row2-confirmed.md` — the calibration this rules on;
  its §1 catch is accepted at §1.1, its row-2 conclusion rejected at §2 for a reason outside its
  scope.
- `2026-07-31-1148-…-row2-suspended-…md` §3 — my defective arm (a) suggestion; the confound it
  raised is now measured and dead.
- `2026-07-31-1030-…-task4-method-ruling-…md` §3 — the reading rule, struck here.
- `2026-07-30-2253-…-capture-chain.md` §3.1 — the density law, and my own one-degree-of-freedom
  warning that §3 above failed to heed.
- `2026-07-31-1137-…-489135a-recompute.md` — the recompute whose secondary outputs survive (§5).
- `2026-07-31-0853-…-measurement-d-spec-…md` — the remaining open measurement, unaffected.

---

*Per HK-015 this is Architect → QA/Captain. Per HK-014/HK-010 committed locally, no push, no
merge. Per HK-011 nothing here touches `src/`. Per HK-017 filename and byline carry `date -u`
UTC. Per HK-018 the prediction interval was computed before this ruling rather than asserted —
it reversed the conclusion I was expecting to accept, and it was derivable from a caution I had
already written down at `2253` §3.1 and then failed to apply to my own reading rule.*
