# Phase 1a findings — asymmetry probe locates the negative cliff, and the model that predicted
# its location is wrong

> **Superseded 2026-07-26.** Closed alignment-replay work, retained as history; no live D-001
> lead. See `2026-07-26-0015-d001-consolidation-and-clean-slate.md`.

**Author:** QA session, 2026-07-25. **Scope:** SPEC.md section 9 Phase 1a (asymmetry probe),
plus an unplanned refinement pass once the initial probe didn't land where predicted.
25 cycles (segment 0, k=0..24 — the same cycles as Phase 0), all scored with
`--normalize-hash-tokens` (2026-07-25-phase0b-findings.md).

## The probe

SPEC.md section 2.5 item 9 predicted the negative cliff near delta ~= -1.7 ("roughly half the
positive side's tolerance," reasoning that negative delta has only ~1.7 s of headroom before
clipping the signal tail, versus ~3.3 s on the positive side before clipping the head). Section 9
specified 5 points to test this: delta in {-1.00, -1.375, -1.75, -2.125, -2.50}.

| delta | median recall | IQR |
|---|---|---|
| -1.000 | 0.9565 | 0.902-0.981 |
| -1.375 | 0.9091 | 0.878-0.959 |
| -1.750 | 0.8846 | 0.863-0.952 |
| -2.125 | 0.8333 | 0.765-0.875 |
| -2.500 | 0.1154 | 0.075-0.136 |

**Recall is still 0.83 at delta=-2.125** — nowhere near a cliff at -1.7. It only craters by
-2.500. This falsifies the specific prediction, so per SPEC.md section 9's own contingency
("if the negative cliff lands outside the predicted -2.5...-1.0 window, amend section 5.2's grid
before running 1b") the location needed pinning down before treating Phase 1a as closed. Added
two refinement points to bracket where between -2.125 and -2.500 the drop actually happens:

| delta | median recall | IQR |
|---|---|---|
| -2.125 | 0.8333 | 0.765-0.875 |
| -2.250 | 0.7692 | 0.681-0.800 |
| -2.375 | 0.4231 | 0.333-0.471 |
| -2.500 | 0.1154 | 0.075-0.136 |

**The steep part of the negative cliff sits between delta=-2.25 and delta=-2.50, centred close
to -2.3 to -2.4** — not -1.7.

## Combining with Phase 0's positive-side data

| delta | median recall |
|---|---|
| -2.500 | 0.115 |
| -2.375 | 0.423 |
| -2.250 | 0.769 |
| -2.125 | 0.833 |
| -1.750 | 0.885 |
| -1.375 | 0.909 |
| -1.000 | 0.957 |
| 0.000 | 1.000 (identity anchor) |
| 2.000 | 0.920 |
| 3.000 | 0.077 |
| 5.000 | 0.000 |
| 7.500 | 0.000 |

## What this means for section 2.5 item 9's model

**The cliff *locations* are close to symmetric, not "roughly half."** The negative cliff
(steepest between -2.25 and -2.50) sits about as far from zero as the positive cliff (steepest
between +2.0 and +3.0, per Phase 0) — both in the same ~2.3-3.0 s range, not a 2:1 ratio. The
predicted mechanism (search-bound versus symbol-loss headroom) got the *ratio* wrong.

**But the model wasn't wrong about there being an asymmetry — it's the wrong asymmetry.** The
*shape* differs sharply between sides, and this is the more interesting finding:

- Positive side (Phase 0): recall holds flat at 0.92-1.00 all the way to delta=+2.0, then falls
  off a cliff to 0.077 by +3.0. A plateau, then a wall.
- Negative side (Phase 1a): recall declines *gradually and monotonically* from 1.00 at delta=0
  down through 0.96, 0.91, 0.88, 0.83, 0.77 by delta=-2.25 — already losing ground well inside
  the theoretical ~1.56 s "no-clipping" headroom from DT_true=+0.80 (section 2.5 item 6) — before
  a much steeper final drop between -2.25 and -2.50.

A plausible physical account (not yet verified against per-cycle DT the way section 2.5 item 8
verified the positive cliff): positive delta clips the signal's *head*, which ft8_lib's sync
search and LDPC error correction tolerate well right up to its own search-range bound, producing
a plateau-then-wall shape. Negative delta clips the *tail*, and per-cycle spread in real DT
(section 2.5's own p10-p90 = +0.60...+1.10 for the +0.80 median) means different cycles start
losing tail symbols at slightly different delta, smearing what might be a per-cycle step function
into a gradual decline in the aggregate median — before the decoder's own search-range bound
still produces a real cliff further out. This explanation is offered as a hypothesis for the
Architect to weigh, not asserted as settled, in keeping with this study's own standing rule about
recording provenance and not overclaiming.

## Consequence for SPEC.md section 5.2's Phase 1b grid — needs revision before 1b runs

The current grid's negative-cliff region is "-2.50 ... -1.00, step 0.125, 13 points" — built
around the (now falsified) -1.7 prediction. Two problems this data surfaces:

1. The dense 0.125 s resolution is centred on -1.75, where recall is still a gentle 0.88 — not
   where the actual structure is (-2.25 to -2.50).
2. The grid's negative edge stops exactly at -2.50, which is inside the steep part of the drop
   (0.42 at -2.375, 0.12 at -2.50) — the true bottom of the cliff is not yet bracketed at all.
   The S-wide arm only extends to -4.0 as a single point, too coarse to resolve it.

Recommend, subject to Architect/Captain sign-off (this is a SPEC change, same category as the
five defects already found in this study, so not mine to apply unilaterally): shift the dense
0.125 s region to roughly -2.75...-2.00, and add at least one point beyond -2.75 to confirm the
curve has bottomed out on the negative side too, before committing to Phase 1b's ~10,800-decode
budget built on the current grid.

## Cost so far

Phase 1a + refinement: 175 decodes (25 x 7 delta values, including the shared identity anchor
counted once). Well within the "~125" original estimate plus the unplanned refinement pass.
**Phase 1b (~10,800 decodes) has deliberately NOT been started** — per this task's own brief, a
grid built on a falsified prediction is not something to commit that budget to without review.
