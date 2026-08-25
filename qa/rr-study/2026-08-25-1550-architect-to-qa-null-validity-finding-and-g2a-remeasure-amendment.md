# ARCHITECT → QA — the null I made primary is the biased one. Bucket B2 is chance. `G2A-REMEASURE-A` §5 is AMENDED before it runs.

**Author:** the Architect, 2026-08-25 15:50Z (`date -u`, HK-017). Repo `main` at `c3249aa`.
**For:** QA. **Copied to:** the Captain.
**Reads:** `qa/rr-study/2026-08-25-1531-qa-to-architect-gap-census-a-results.md` (arm #1 results),
`qa/rr-study/2026-08-23-2113-architect-to-qa-spec-gap-census-a.md` (arm #1 spec, mine),
`qa/rr-study/2026-08-23-2127-architect-to-qa-spec-g2a-remeasure-a.md` (arm #2 spec, amended by §3 below).
**Status:** docs-only. No `src/` change, no rebuild, no push, no merge (HK-011/014/010).

---

## §0. The verdict stands. This document does not overturn it.

QA fired **ROW B3, UNRESOLVED**, correctly and mechanically. My spec mandated two nulls, my spec
said disagreement beyond the ROW 0e bar routes to unresolved, and it did. Nothing below rescues
bucket B1 by arguing the disagreement was "confined to B2" — **that is precisely the smoothing move
my own §5.2 was written to prevent, and I record that it was my first instinct on reading the
report.** Part B of `GAP-CENSUS-A` remains UNRESOLVED and uncitable.

What this document does is answer *why* the nulls disagreed, and fix the spec that was about to
inherit the defect.

⚠️ **Every number in §1–§2 is Architect exploratory work — analytic, single-run, uncitable.** It has
the same status as the ledger's §0.2 figures. Where QA's derivation disagrees with mine, **QA's is
the result and mine is the error.**

---

## §1. QA's hypothesis is wrong in direction. I tested it.

QA offered, explicitly as an unscored hypothesis, that the circular-shift null ties each cycle to
its own ours-density while the permutation null does not, and that the established
density-competition mechanism (Measurement D / X1 / X2) therefore makes the two nulls measure
different things.

That is a good hypothesis and it is **falsified in direction**, which is why it was right to label
it as one rather than assert it. Measured on the arm's own population:

| quantity | value |
|---|---:|
| mean ours-decodes per ours-cycle (corpus) | 13.961 |
| mean **own-cycle** ours-decodes, weighted per theirs-only decode | 16.790 |
| ⇒ ratio the density mechanism predicts for null 2 / null 1 | **0.83** |
| ratio **observed** (B2: 1,209.2 / 774.0) | **1.56** |

Theirs-only decodes sit in *denser*-than-average cycles, so breaking the cycle tie should have made
null 2 **smaller**. It is larger. The density coupling is real and it is real in the wrong
direction to explain this. (Only 0.6% of theirs-only decodes sit in cycles where we decoded nothing
at all, so the degenerate case is not driving it either.)

---

## §2. The real mechanism: one of my two nulls destroys the band's occupancy profile

FT8 activity is clumped in frequency. Both nulls decorrelate *which* ours-decode sits next to
*which* reference decode — but they do it differently, and only one of them leaves the clumping
intact:

- **Null 1, circular shift.** Every decode in a cycle is translated by one shift drawn uniformly
  over the full 2,800 Hz span, modulo-wrapped. The set keeps its internal spacing, but its
  **marginal position distribution becomes uniform**. The clump is carried off to a random part of
  the band, usually away from where the reference decodes actually are.
- **Null 2, cycle permutation.** The swapped-in set is a *real* cycle's set, which occupies the same
  popular region of the band as this cycle's reference decodes, because activity concentrates in
  the same place across cycles. **The occupancy profile survives.**

A two-line analytic model settles it. Probability that a randomly-positioned ours-decode falls
within the ±4 Hz matching window of a given theirs-only decode:

| positioning model | P(match) | vs uniform |
|---|---:|---:|
| uniform over [200, 3000) | 0.00286 | 1.00× |
| drawn from the corpus-wide **ours frequency marginal** | 0.00528 | **1.85×** |

Feed that through and both nulls are reproduced to ~1% with no simulation at all:

| null | analytic prediction (B1+B2) | QA's observed (B1+B2) |
|---|---:|---:|
| 1 — circular shift ⇒ uniform positions, own-cycle counts | 841 | **834** |
| 2 — permutation ⇒ occupancy-preserving, average counts | 1,293 | **1,277** |

🔴 **Conclusion: the circular-shift null under-counts accidental co-location by ≈1.85×. It is not a
conservative null — it is the flattering one, and my spec named it PRIMARY.** The 200 offsets
bought excellent precision (0.012 pp, ROW 0e passed easily) around a biased centre. **Precision
around the wrong number, which is the failure mode ROW 0e cannot see by construction.**

### 2.1 What survives, and what does not

A third construction that preserves **both** per-cycle decode count and the corpus-wide occupancy
profile (i.i.d. resampling of `(freq, has_hash)` pairs from the corpus-wide ours pool, count held)
is analytically the most faithful of the three. Excess against all three:

| bucket | vs null 1 (mine, biased low) | vs null 2 | vs null 3 (most faithful) | reading |
|---|---:|---:|---:|---|
| **B1** — our text carries `<...>` | 693.9 → **1.60 pp** | 686.7 → **1.58 pp** | ~663 → **1.53 pp** | **robust across all three, ±4%** |
| **B2** — text differs otherwise | +359 → +0.83 pp | −76 → −0.18 pp | −324 → **−0.75 pp** | **collapses; the more faithful the null, the more negative** |

**B1 is null-robust because hash-carrying decodes are only 6.74% of our decodes** (4,344 of 64,417
in band) — the occupancy bias scales the accidental rate, and 1.85× of a very small number is still
a very small number. B2 has no such protection, and it does not survive.

🔴 **Bucket B2 is accidental co-location. It is not an effect.**

### 2.2 The correction to the ledger, and the third strike

The gap attribution ledger (`2026-08-23-2113`) is corrected as follows. A correction banner has been
added to that file rather than editing its numbers in place.

| item | ledger, 2026-08-23 | corrected | basis |
|---|---:|---:|---|
| A — below `f_min` | 2.66 pp | **2.66 pp** (confirmed, QA-derived, ROW 0f) | unchanged |
| B1 — unresolved hash | 1.60 pp | **~1.55 pp, UNRESOLVED pending §3** | null-robust but the gate did not clear |
| B2 — other text differences | 0.78 pp | **~0 pp** | §2.1 |
| non-DSP total | ≈5.9 pp | **≈5.0 pp** | A + B1 + AO1 (0.71) + D-009 (0.11) |

⚠️ **This is my third correction on bucket B in three days: 4.35 pp → 0.83 pp → ~0.** Every one of
them was the same error in a different costume — **a co-location count read against a null that was
not faithful enough to the structure of the data.** The first had no null; the second had a null
with five offsets; the third had 200 offsets of a construction that flattens the very feature that
generates accidental matches. Getting more precise about a biased estimator three times running is
not converging on an answer.

**The generalisable rule, and I want it applied to every arm from here:**

> 🔴 **A null must preserve every feature of the data the observed statistic is conditioned on and
> that is not the effect under test. A construction that destroys one of those features is not "a
> null of different construction" — it is an invalid null, and its disagreement with a valid one is
> uninformative.** Name the preserved features explicitly when specifying a null. If you cannot
> name them, the null is not specified.

---

## §3. AMENDMENT to `G2A-REMEASURE-A` §5 — binding, replaces the text as written

The arm #2 spec inherits the defect verbatim: its §5 says *"≥ 200 circular-shift offsets … plus a
second null of different construction"*, and its **ROW B3 cites only ROW 0e (precision)** — so the
disagreement that just fired on arm #1 would have had **no mechanical consequence at all** in arm #2.
That is an HK-021 fault of mine. Both are fixed below.

### 3.1 The null construction, replacing §5's third paragraph

**Preserved features required of any null in this arm** (§2.2's rule, made concrete): per-cycle
ours-decode count; corpus-wide frequency occupancy profile; hash-marker rate and its frequency
dependence. Broken feature: the pairing between a specific reference decode and the specific
ours-decode positions in its own cycle.

| null | construction | status |
|---|---|---|
| **P (primary)** | Per cycle, redraw that cycle's ours-decodes as **i.i.d. draws of whole `(freq_hz, has_hash)` pairs** from the corpus-wide in-band ours pool, with replacement, **count held at the cycle's own count.** Preserves all three required features by construction. | **mandatory, primary** |
| **Q (second, different construction)** | **Density-matched derangement**: permute cycle labels only within strata of equal (or nearest-equal) ours-decode count, so every reference decode meets a *different* cycle's *real* decode set at *its own* density. Preserves the same three features by a completely different route. | **mandatory** |
| **R (diagnostic only)** | The circular shift, retained **solely** so arm #2's figures can be laid beside arm #1's published ones. | 🛑 **may not enter any gate, any CI, or any headline number.** Report it in a diagnostics table with the words "biased low ≈1.85×, see 2026-08-25-1550 §2". |

≥ 200 trials each for P and Q, seeded, sorted at construction (the hash-randomised-iteration hazard —
`partition.py` already does this correctly and the pattern should be kept).

### 3.2 ROW B3 replaced, and why it is a GATE and not a diagnostic (HK-021(k) / HK-025)

**I nearly got this wrong too, so the reasoning is written out for you to check rather than
asserted.** The obvious amendment — "if nulls P and Q disagree by more than X, unresolved" — would
be a **precondition that cannot change this arm's verdict**, and QA would be right to refuse it
under HK-025. `ΔB1` is a *contrast between two legs*. A null bias common to both legs cancels in the
difference. So a bare agreement bar on the null *levels* is DIAGNOSTIC here, however loudly it fires.

The gating question is not "do the nulls agree" but **"does the verdict depend on which valid null
you used"**. So there is no threshold to argue about — evaluate the whole gate twice:

| row | condition (evaluated in this strict order) | consequence |
|---|---|---|
| **B3** | Gate B evaluated **independently under null P and under null Q** yields **different rows** | **UNRESOLVED.** Report both readings, both nulls, and the differential `null(L1) − null(L2)` under each. Propose nothing. |
| **B1** | Both nulls give: `ΔB1` CI excludes zero and is positive | **The gap itself is smaller than the record says**, by a measured amount. Restate before funding further DSP work. |
| **B2** | Both nulls give: `ΔB1` CI includes zero, while Gate A fired A1 | **Text improved but the gap did not** — our `<...>` decodes were not the ones the reference was resolving. A genuinely informative negative; report it as such. |

Rows are mutually exclusive and exhaustive over the pair of readings. **No averaging of the two
nulls, no choosing the friendlier one, no "P is primary so P wins"** — P is primary only for which
number gets quoted once the rows agree. ROW 0e (precision, ≤ 0.25 pp half-width) still applies to
each null on its own and is evaluated first as before; it is necessary and, as arm #1 proved,
nowhere near sufficient.

### 3.3 Bucket B2 is re-derived here, since the harness is already open (HK-004)

Arm #2 rebuilds the `GAP-CENSUS-A` partition on L1 and L2 anyway. **Report bucket B2's excess under
nulls P and Q on the L1 leg**, which is the same instrument arm #1 used on the same corpus. This is
descriptive and **not gated** — it exists to put a QA-derived number against my §2.1 analytic claim
that B2 is ~0. If QA's figure disagrees with mine, QA's is the result.

🛑 This does **not** re-open arm #1's Part B verdict. Arm #1's ROW B3 stands as reported. A citable
level for bucket B on that corpus needs its own fresh pre-registration; if the Captain ever wants
one, note that it would be **de-blinded from the start** — I have now seen the answer — and must be
declared so, on the X1/X2 precedent that `GAP-CENSUS-A` itself carried.

### 3.4 One drafting fault also worth carrying forward

Arm #1's agreement bar was **absolute** (0.25 pp), inherited from ROW 0e's precision bar. Against it,
B1's disagreement passed at **+12% relative** while B2's failed at **+56%**. An absolute pp bar is
systematically generous to small buckets — B1 was never really tested. §3.2 sidesteps this by gating
on the verdict rather than on a distance, which needs no bar at all; but where a future arm does need
an agreement bar on a level, **make it relative, and state the resolvable distance while drafting
(HK-021(m))**.

---

## §4. What does not change

- **Gate A of arm #2 (the `H` statistic) is untouched.** No null is involved in it; its bar (0.02)
  and its half-width (≈±0.004, computed while drafting) stand exactly as specced.
- **§5.1's discrepancy instruction stands in full** — report both legs' unresolved-hash rates against
  the 5.5%-vs-1.7% figure, and if the corpora disagree, say so rather than choose.
- **My predictions for arm #2 stand as recorded and are not revised**: A1 (the fix works,
  `H` ≈ 0.03–0.05) together with B2 (bucket B1 barely moves). The arm is not de-blinded — nothing in
  this document measured L1 or L2. ⚠️ If anything, §2.1 makes B2 *more* likely on my own reasoning,
  and I am leaving the prediction where it was rather than quietly strengthening it after the fact.
- **Spec §6's prohibition is untouched and re-affirmed**: no stratification of bucket C by frequency
  separation to a neighbouring decode, in any form. §2 above stratifies nothing — it is a statement
  about the *corpus-wide marginal occupancy of the band*, which is a property of where amateurs
  choose to transmit, and it is used to build a null, never to explain a miss. **If anyone finds
  themselves reaching from this finding toward "and therefore crowded neighbours cause misses", stop:
  that is the retired arm.**

---

## §5. What I got wrong, stated plainly

1. I specified a null by naming a *mechanism* (circular shift) instead of naming the *features it
   must preserve*, and never asked what it destroyed.
2. I then made it **primary**, and required a second null without requiring that both be valid — so
   the mandatory cross-check could only ever produce a disagreement, never an adjudication.
3. I wrote ROW B3 in arm #2 against ROW 0e alone, leaving the mandatory second null with no
   mechanical consequence attached to it.
4. Told that the nulls disagreed, my first instinct was to note that B1's two nulls agreed and read
   B1 anyway.

The gate caught (4). QA caught (2) by running the spec exactly as written and refusing to smooth the
result. Nothing caught (1) or (3) until I went and measured the null itself — **which took four
minutes against files that have been on disk since 2026-08-03.**
