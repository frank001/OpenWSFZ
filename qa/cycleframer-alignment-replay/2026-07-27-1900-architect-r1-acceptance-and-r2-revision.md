# D-001: R.1 accepted — §5 withdrawn, and the withdrawal is wider than QA credited. R.2 revised, R.4 promoted

**Author:** Architect, 2026-07-27 (19:00). **For:** QA (to run), and the Captain (§4, §7).
**Answers:** `2026-07-27-1830-qa-to-architect-r1-notification.md` §5 — "proceed to R.2 as designed,
or revise R.2/R.3's design first?"
**Ruling: revise, in three specific ways, then proceed.** The revisions are §5, §6 and §7.

---

## 1. Short answer

R.1 is accepted without reservation. Row 1 of my own reading table fires, and I apply it as written:
**the published `recov648` series measures candidate density, not detection. My 17:00 §5 inference
is withdrawn. Sync accuracy is un-eliminated and is now a live explanation for the whole 437.**

QA held at the checkpoint correctly and routed the result back rather than reconciling it. That was
right, and it is the second time in this thread that pre-committing a reading rule before the
numbers existed has paid for itself.

Three things follow, and only the first is in QA's notification:

1. **The withdrawal is wider than §3.3 of my design credited** (§3 below). I over-protected two
   results that share the same defect. Correcting my own protection list is the first item because
   everything downstream inherits it.
2. **R.1 left one cheap, high-value cell unfilled** — the empirical null at the *tight* tolerances.
   Condition 2 was true-population-only. Filling it costs ~30 minutes on a script that already
   exists and measures our sync error directly, which is exactly what R.2 needs to size its grid.
   That is **R.1b** (§5).
3. **R.2's offset grid was designed under the assumption R.1 has just falsified** and is too narrow;
   and my §6.2 stop rule ("if R.2 hits row 1, skip R.3") is no longer safe. Both revised (§6, §7).

## 2. On the execution itself

I audited the arm rather than only reading its conclusion, since it overturns a ruling of mine and
that is the direction in which I am least reliable.

- The self-check is genuine: `compute_648_population` reproduces C.3's published four-way split
  exactly before any other number is computed, and the script stops loudly if it does not.
- The matcher is `c4_min_score_sweep_analysis.py`'s own, imported rather than reimplemented, so the
  null and the published series are computed by identical code. This is the right construction — it
  makes the comparison immune to matcher-reimplementation error.
- **One property worth naming, because it strengthens the result:** the displaced null wraps inside
  200–3000 Hz, a band densely occupied by *other* real FT8 signals. A displaced target can therefore
  land near a genuine signal that legitimately has a candidate. This **inflates** the null. An
  inflated null makes row 1 *harder* to fire, not easier. The finding is conservative in the
  direction that matters, and I would rather it be conservative that way than the other.
- Condition 2 is independent of Condition 1 in construction and agrees with it at both settings.
  Two independent conditions pointing the same way at two settings is not a marginal call, and I
  will not treat it as one merely because it costs me a ruling.

**Accepted. No re-run requested.**

## 3. The full accounting of what falls — I over-protected two results

My design's §3.3 listed what was "at risk" and what was "not at risk." Having applied row 1, that
list was too generous to my own prior conclusions in two places. Stating this plainly, because a
correction that only goes as far as the notification credits would leave load-bearing claims
standing on a foundation I have just removed.

### 3.1 Withdrawn outright

| claim | where | why it falls |
|---|---|---|
| "At K=4 we can place a candidate at the **exact** frequency and time where WSJT-X decodes, and still fail" | 17:00 ruling §5 | Pre-committed row 1. "Exact" was carried by a ±10 Hz window three lattice bins wide. |
| "**Symbol demodulation → LLR sign correctness** is where the residue lives" | my 17:30 design §2, row 4 | This rested on Phase 2c Part B's BER measured over a tolerance-matched population. See §3.2. |

That second row matters more than the first. My §2 table was the argument that row 4 is "a much
narrower target than the menu implies." **That argument is withdrawn.** Row 4's front end is back to
being less decomposed than I claimed at 17:30 — not as undecomposed as the B.3 menu had it, but the
"one stage, well localised" framing does not survive.

### 3.2 Numbers that stand; inferences drawn from them that do not

This distinction is the whole of the correction and I want it stated exactly:

- **Phase 2c Part B — THE 135 (44.0%) and THE 567 (49.4%) median BER.** The measurements are correct.
  Their *interpretation* as "our demodulator produces wrong bits on located signals" is withdrawn.
  A candidate matched by coincidence points at spectrum that does not contain the signal, and
  demodulating noise yields ~50% BER by construction. **A 44–49% BER no longer discriminates between
  "our demodulator is broken" and "this candidate was never on the signal."** THE 567 is almost
  certainly the latter. THE 135 I had called "much less exposed"; at K=10@600 the true match rate
  (16.2%) is *indistinguishable from its own null* (16.6%), so THE 135 is exposed on exactly the
  same terms. I was wrong to grade it differently.
- **Phase 2c Part A — shrinkage, 0/135.** I listed this as "no tolerance dependence." The *count* has
  none. The *population* has all of it: the 135 were selected by the ±10 Hz matcher. So "LLR
  magnitude/normalisation is closed on evidence" is weakened to "LLR shrinkage does not recover a
  population we can no longer show was ever located." That is a much smaller claim. I am not
  reopening the shrinkage question — it remains unlikely on other grounds — but it is no longer
  *closed on evidence*, and the §2 table should not have said so.

### 3.3 Standing, tolerance-independently

Unchanged, and I want the correction not to be read as broader than it is:

- **C.4's +2 matched decodes** — a decode count. No matching enters it. Candidate *detection* being
  non-binding at the score floor still stands, and the score floor stays closed.
- **B.2's E = 5.69** — synthetic, ground-truth, no corpus matcher. Its `nearest_candidate` caveat
  (design §3.3) is now more clearly live; R.2 measures it directly.
- **C.3's SNR population split** (p = 1.1×10⁻⁷⁴) — the population was defined by decode
  presence/absence, never by a match. The miss population is genuinely weaker-signal.
- **B.1/B.1b's 437-message gap and the parity figures** — decode counts on both corpora.

**Net effect on the B.3 menu:** row 4's *prize* (437) is untouched. Row 4's *target* is less
localised than my 17:30 note claimed, and its *mechanism* is now genuinely open between detection,
estimation and demodulation. This does not move the row 4-vs-5 decision on its own — it moves the
confidence with which I claimed row 4 was narrow, and the Captain should discount that claim
accordingly.

## 4. What I owe the Captain, said plainly

At 17:00 I ruled that sync was fine and the residue was downstream. That ruling promoted the
structural avenue and shaped how row 4 was described in the menu the Captain is deciding on. **It
was wrong, and it was wrong because I accepted a match tolerance six times coarser than the
decoder's own lattice as though it meant "exact."** I caught it myself at 17:30 and designed the
test that would break it; QA ran it and it broke. That is the process working, but the Captain
should register that the row-4 narrative has now been revised twice in three hours, and weight my
next characterisation of row 4 accordingly.

**Nothing in this changes the 4-vs-5 decision the Captain has already leaned.** R.4 remains the arm
that decision actually needs, and §7 promotes it.

## 5. R.1b — the unfilled cell (new, cheap, run before or with R.2)

**Question.** Condition 1 measured the null at ±10 Hz / ±0.5 s only. Condition 2 tightened the
tolerance on the *true* population only. The cell that distinguishes my reading table's row 1 from
its row 3 — the null *at the tight tolerances* — was never computed.

**Why it is worth 30 minutes.** The decision is unaffected (rows 1 and 3 both lead to R.2), so this
is not re-litigation. It is worth running because of what the number would be *used for*:

An order-of-magnitude prompt, on the same uniform-placement assumption as my §3.2 and with the same
caveat — at ±3.125 Hz / ±0.08 s the window spans ~9 of the grid's 53,880 cells, so 2000 candidates
give E ≈ 0.33, P(≥1) ≈ 28%. The observed true rate in that cell is **8.0%**. At K=10@600 the same
arithmetic gives ≈3.6% against an observed **0.3%**.

If the empirical null confirms that shape, then at lattice resolution **our candidates are not
merely absent from the 648's locations — they are anti-correlated with them**, appearing there
*less* often than at arbitrary points in the same band. That is a materially different finding from
"detection is imprecise," and it points at the sync *scoring metric* (what the detector rewards)
rather than at estimator precision. It is also cheaper to act on than either.

**Method.** The existing `r1_coincidence_null_analysis.py`, one change: compute the displaced null
across the same 4×3 tolerance ladder as Condition 2, not only at ±10 Hz / ±0.5 s. Report true and
null side by side in every cell, both settings. Nothing else changes; no new instrument.

**Reading rule, fixed now:**

| result | reading |
|---|---|
| True ≈ null at every tolerance, at both settings | Our candidate set carries **no location information at all** about the 648. Detection failure is total, not imprecise. Row 4's target is the sync detector/metric; R.2's offset surface becomes a costing input rather than the mechanism test. |
| True materially **below** null at tight tolerance (the shape the arithmetic above suggests) | **Anti-correlation.** The detector systematically does not fire where these signals are. Strongest available pointer at the sync metric; R.3's D-miss class is expected to dominate and R.3 becomes the confirmatory arm, not the exploratory one. |
| True separates above null at some tolerance τ | Detection is real but imprecise, and **τ is a direct empirical measurement of our sync error**. R.2's offset grid must span τ, and §6's widened grid is sized from τ rather than from my guess. |

**Cost:** ~30 QA-minutes, offline, frozen artefacts, no capture, no rebuild. Same guardrails as R.1.

## 6. R.2 revised — the grid was sized by the assumption R.1 just falsified

R.2 as designed plants signals at Δf ∈ {0, ±0.39, ±0.78, ±1.17, ±1.56} Hz — **half a lattice step at
most**. That grid was chosen because I believed detection was accurate to the lattice and only
quantisation error remained. R.1 removed that belief. If the sync estimator's error is multiple bins,
R.2 as written would measure a corner of the surface and miss the region the real candidates occupy.

**Three revisions:**

1. **Widen the grid past the lattice.**
   Δf ∈ {0, ±0.39, ±0.78, ±1.56, ±3.125, ±6.25} Hz (to two full steps)
   Δt ∈ {0, ±0.02, ±0.04, ±0.08, ±0.16} s (to two full steps)
   crossed, ≥8 repeats/cell, at the fixed comfortable SNR the original design specifies (from B.2's
   own curve, where Arm A shows P(decode) ≥ 95%). If R.1b returns a separation tolerance τ, extend
   the grid to span τ regardless of the values above.
2. **Add the inverse map as a named deliverable.** Report not only BER as a function of offset, but
   the **offset implied by an observed BER** — i.e. invert the surface. This is what lets THE 135's
   measured 44.0% median BER be read as "consistent with an offset of about X Hz / Y s" instead of
   being uninterpretable. It is the only bridge left from ground-truth work back to the corpus
   numbers, now that the matcher no longer provides one. It costs nothing extra — it is a different
   reading of the same surface.
3. **Record the two discarded fields** — unchanged from the original design (`cand["freq_hz"] −
   base_freq`, `cand["dt"] − pdt`, `run_arm_a` lines 265-274). These also settle B.2's
   `nearest_candidate` caveat directly.

**Reading rule, revised and fixed now** (row 1's consequence changes; rows 2 and 3 are as designed,
with a new row 4 for the widened grid):

| result | reading |
|---|---|
| BER ≥ 35% at (±1.56 Hz, ±0.04 s) while BER ≤ 10% at (0,0) | Lattice quantisation alone is **sufficient** to produce the miss population's BER. **Revised consequence:** this no longer licenses skipping R.3 — see §7. It establishes sufficiency, not occurrence. Row 4's target is plausibly a fine-refinement stage; R.3 says whether our real candidates actually carry such offsets. |
| BER rises with offset but stays < 25% at worst case *within one lattice step* | Refinement helps but is not sufficient. Two-part job; the widened grid's behaviour beyond one step becomes the informative part. |
| BER flat across the whole widened surface | Offset is not the mechanism at any scale; demodulation is the whole story. Row 4 is a demodulator rewrite and should be priced against row 5 accordingly. |
| **(new)** BER stays low well past one lattice step | Our demodulator is *more* offset-tolerant than the lattice requires, so offset cannot explain the miss population at all — and the inverse map will say so numerically. Points hard at detection (R.1b's territory), not estimation. |

**Cost:** still about half a QA session; the grid roughly doubles but each cell is cheap.

## 7. Sequencing revised — R.4 promoted ahead of R.3

**Original order:** R.1 → R.2 → (R.3 only if R.2 ambiguous) → R.4 last.
**Revised order:** R.1 ✅ → **R.1b** → **R.2** → **R.4** → **R.3 (now always run)**.

Two changes, each with its reason:

**(a) R.2 row 1 no longer licenses skipping R.3.** My §6.2 stop rule said a clean R.2 row-1 result
was "sufficient for the Captain's 4-vs-5 decision without R.3." That was only true because the
C-series was believed to have bounded the alternative explanations. R.1 removed that bound. R.2
measures whether a given offset is *sufficient* to destroy demodulation; it cannot say whether our
real candidates *carry* such offsets. Only R.3 — ground truth, no matcher anywhere in it — can, and
its D-miss / E-loss / X-loss split is now the only surviving route to a stage attribution.
**R.3 is therefore always run.** I am adding roughly one session to the study and I would rather
declare that than let a stale stop rule quietly under-deliver.

**(b) R.4 moves ahead of R.3.** Three reasons:

1. **R.4 is the arm the Captain's decision needs**, and it is a black-box end-to-end sensitivity
   measurement with **no matcher in it anywhere**. It is structurally immune to the exact defect
   class that just cost us two rulings. After R.1, that immunity is worth ordering priority.
2. **Attribution has proved to be the fragile half of this study; the cost signal has not.** If the
   schedule slips or the Captain calls the decision early, I would much rather have ΔSNR and the
   dB→messages curve in hand than a stage attribution.
3. **It removes a dependency rather than creating one.** R.4 step 1 as designed says "take R.3's
   synthetic buffers." Run R.4 first and it **generates and persists the shared buffer corpus**
   (B.2 harness, Arm A geometry, across B.2's SNR grid), which R.3 then reuses. This is strictly
   better than the original order: one buffer corpus, two analyses, and R.4's ΔSNR and R.3's stage
   split then refer to the *same* population and can be read against each other. In the original
   order the two arms would have shared buffers by accident; now they do by design.

R.4's method, reading rule and honest limits are **unchanged** from the 17:30 design §4 — including
that ΔSNR is reported with its Wilson interval and the dB→messages curve is reported for **both
corpora separately, never collapsed**, and that no single summary number is quoted without the curve
beside it. The CPFSK-vs-GFSK caveat (B.2 §5) carries forward unresolved and is most exposed here.

**Stop rules that survive unchanged:** any arm whose self-check fails is reported as a self-check
failure, not as a result (R.2's BER at (0,0) must land near zero; R.4's jt9 arm must reproduce B.1's
depth-1 behaviour on a shared buffer). Four self-corrections of this class have now been caught
mid-flight in this thread — B.1's anchor drift, B.2's clipping, C.4's `MaxPass0Candidates`
truncation, and now R.1. The pattern is established well enough to keep planning for.

## 8. What this does not authorise or settle

- **No native or `src/` change** (HK-011 untouched). R.1b is offline against frozen artefacts; R.2,
  R.3 and R.4 use already-shipped, default-off diagnostic exports at shim ≥20260035. If any arm
  turns out to need a native export, that is an escalation back through QA, not a call the running
  session makes.
- **No push, no merge** (HK-014 — committed locally, stops there).
- **No `pre_merge_check.py`** — Captain's trigger per HK-006, not run here.
- **Row 5 untouched.** No position taken on GPLv3; it remains the benchmark row per menu §3.5.
- **Rows 2 and 3 stay sequenced behind row 4**, per menu §3.2/§3.3 — unchanged.
- **The `libft8.dll` size question and this branch's disposition** remain open and blocking on the
  Captain. My ruling on whether the size delta still blocks merge is still owed and is still not in
  this document — it is not affected by R.1 either way.
- **NFR-021:** aggregates only. R.1b touches real callsigns solely inside git-ignored `artefacts/`
  and must print counts only; R.2/R.3/R.4 messages are Q-prefix by construction.
- **Per HK-015 this is a design, not a task.** `dev-tasks/` and `tasks.md` are QA's to author.

## 9. Honest caveats

- **I authored the ruling R.1 overturned, and I am now authoring its replacement plan.** The same
  mitigation applies and is the same partial one: reading rules for R.1b and revised R.2 are fixed
  above before any number exists, and QA runs them. That is a mitigation, not neutrality.
- **§5's tight-tolerance arithmetic reuses the uniform-placement assumption that R.1 was
  commissioned to test, and which is false.** It is a prompt for running R.1b, not a finding, and
  the anti-correlation reading must not be quoted until R.1b returns an empirical null.
- **R.2's widened grid is still a guess if R.1b returns no separation tolerance.** In the row-1 and
  row-2 branches of R.1b's table there is no τ to size it from, and two lattice steps is my
  judgement, not a measurement.
- **Everything here still measures one decoder, one implementation.** None of it measures how hard
  our front end would be to *improve*, which is what row 4 actually costs. R.4's dB curve remains
  the closest available proxy and remains a proxy.
- **Adding R.3 unconditionally and R.1b adds roughly 1.5 sessions to the study.** Given that R.1 cost
  one hour and overturned a ruling, I judge that trade worth making, but it is the Captain's clock
  and the Captain's call if the decision needs to come sooner.

## 10. Cross-references

- `2026-07-27-1830-qa-to-architect-r1-notification.md` — the notification this answers.
- `2026-07-27-r1-coincidence-null-findings.md` — R.1's result, accepted here.
- `2026-07-27-r1-coincidence-null-task-spec.md` / `r1_coincidence_null_analysis.py` — QA's spec and
  script; R.1b extends the script's Condition 1 across Condition 2's ladder.
- `2026-07-27-1730-architect-row4-scoping-design.md` — the design. §2's table row 4 and §3.3's
  protection list are **corrected by §3 above**; §4's R.2 is **revised by §6**; §6's sequencing is
  **revised by §7**. R.4 (§4) and the corpus ruling (§5) stand unchanged.
- `2026-07-26-1700-architect-c4-ruling-and-decomposition-revision.md` §5 — **withdrawn**.
- `2026-07-26-c2-phase2c-shrinkage-trial-and-ber-findings.md` §4.2, §7 — THE 135 / THE 567, whose
  interpretation §3.2 above revises.
- `2026-07-26-b2-synthetic-calibration-findings.md` — the harness R.2/R.3/R.4 extend.
- `2026-07-26-2359-architect-b3-costed-menu.md` §3.4 — row 4's cost, which §3 above makes less
  certain, not larger.

---

*Per HK-015 this is Architect → QA material: R.1b and the revised R.2 are a design for QA to scope
and author, not tasks issued by me. Per HK-014 this note is committed locally and goes no further.
Per HK-011 nothing here touches `src/` or native code. The decision the study feeds — row 4 vs.
row 5 — remains the Captain's, on the Captain's clock.*
