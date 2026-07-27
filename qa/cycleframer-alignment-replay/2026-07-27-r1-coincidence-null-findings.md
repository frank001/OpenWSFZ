# D-001 R.1 — the coincidence null: findings

**Author:** QA, 2026-07-27. **Executes:** `2026-07-27-r1-coincidence-null-task-spec.md`, operationalising
`2026-07-27-1730-architect-row4-scoping-design.md` §4 (R.1). Reading rule applied verbatim from
that table, fixed before this session ran.
**Result: Row 1 of the reading table fires, at both settings, unambiguously.**

---

## 1. Self-check (design doc §6 stop rule)

`compute_648_population` reproduced C.3's published split exactly against the frozen artefacts:
`shared_hit=1235 matched_missed_failed=135 near_decoded=10 no_candidate_anywhere=648`. Population
size = 648, matching C.3's published count. Machinery trusted; numbers below stand.

## 2. Condition 1 — frequency-displaced null vs. true, at the published tolerance (±10 Hz / ±0.5 s)

| setting | TRUE recov648 | null mean (8 displacements, ±150/300/450/600 Hz) | true − null |
|---|---:|---:|---:|
| **k10 (K=10@600)** | 105/648 = **16.2%** | **16.6%** | **−0.4 pts** |
| **k4_cap2000 (K=4@2000)** | 618/648 = **95.4%** | **90.8%** | **+4.5 pts** |

At K=10@600, the true rate sits *at* the null — statistically indistinguishable, and if anything a
hair below it, consistent with §3.2's coherent explanation that the 648 are weak-signal locations
depleted of candidates relative to a uniform spectral neighbourhood.

At K=4@2000, the true rate exceeds the null mean by 4.5 points on a 90.8% base — well inside "a few
points," and the null itself (a same-density, same-neighbourhood control with the real signal
removed by construction) is already at 90.8%, not far below the true 95.4%. The 8 individual
displacement cells range 90.3%–91.8%, tightly clustered — this is not noise in the null estimate,
it is a stable finding.

## 3. Condition 2 — tolerance ladder, true population only

| freq tol | dt≤0.5s | dt≤0.16s | dt≤0.08s |
|---:|---:|---:|---:|
| **k10 (K=10@600)** |||
| 10 Hz | 16.2% | 3.5% | 1.4% |
| 5 Hz | 6.0% | 1.1% | 0.5% |
| 3.125 Hz (1 lattice step) | 3.5% | 0.8% | 0.3% |
| 1.5625 Hz (half step) | 2.0% | 0.6% | 0.3% |
| **k4_cap2000 (K=4@2000)** |||
| 10 Hz | 95.4% | 52.9% | 29.3% |
| 5 Hz | 67.1% | 22.2% | 11.6% |
| 3.125 Hz (1 lattice step) | 49.8% | 14.7% | 8.0% |
| 1.5625 Hz (half step) | 32.6% | 8.5% | 4.5% |

At both settings the match rate collapses monotonically and steeply as the tolerance tightens
toward the actual candidate lattice (3.125 Hz × 0.08 s). At K=4@2000, going from the published
±10 Hz/±0.5 s window down to one lattice step at the tightest time tolerance takes the rate from
95.4% to 8.0% — a 12x fall for a tolerance that is still generous (one full lattice cell, not a
point match). This is the signature of a densely-populated candidate set filling a coarse window,
not of precisely-located detections.

## 4. Reading (design doc §4, R.1 table, applied verbatim)

**Row 1 fires: "Null ≈ true within a few points at K=4@2000."**

> The published `recov648` series measures candidate density, not detection. My 17:00 §5 inference
> is withdrawn; sync accuracy is un-eliminated and R.2/R.3 become the main event.

This is not a marginal call. Both the displacement-null comparison (Condition 1) and the
independent tolerance-ladder comparison (Condition 2) point the same direction at both settings:
- K=10@600's true rate cannot be distinguished from its own null (−0.4 pts).
- K=4@2000's true rate exceeds its null by only 4.5 points, and that entire 95.4% figure evaporates
  to single digits once the match tolerance approaches the decoder's actual lattice resolution.

The design doc's own order-of-magnitude arithmetic (§3.2: 96.6% predicted vs. 95.4% observed at
K=4@2000 under a uniform-placement chance model) is now confirmed empirically rather than by
assumption — the empirical null (90.8%) sits almost exactly where that arithmetic predicted, without
needing the uniform-placement assumption at all.

## 5. What this settles and what it does not

**Settled by this arm alone:**
- The `recov648` metric as published in the C.4 findings does not measure whether a genuine
  candidate exists near a missed signal — it measures how much of the 449×2×30×2 grid a given
  setting's candidate population covers, full stop.
- `2026-07-26-1700-architect-c4-ruling-and-decomposition-revision.md` §5's claim that at K=4 "we
  can place a sync candidate at the exact frequency and time where WSJT-X decodes a message... and
  still fail" is not supported by the evidence cited for it. "Exact" was doing work the tolerance
  could not carry.

**Not settled by this arm** (per the design's own scope, §3.3):
- C.4's +2 matched-decode result stands — untouched, it is a decode count, no tolerance involved.
- Phase 2c Part A (shrinkage, 0/135) stands — no tolerance dependence.
- B.2's E = 5.69 stands, with its `nearest_candidate` caveat (§3.3) now more clearly live — R.2
  measures this directly, next.
- C.3's SNR-gap population split stands — that was never a matching claim.
- **Whether sync accuracy or the demodulator is the actual mechanism is still open.** R.1 only
  establishes that the *evidence for "sync is fine, demodulation is broken"* does not hold up — it
  does not itself establish that sync is the problem. R.2/R.3 answer that.

## 6. Self-check discipline note

Per the design's §6 stop rule and this thread's established convention, this result invalidates a
standing ruling of the Architect's own, made explicit and pre-committed by him for exactly this
reason. Per the design doc's closing line ("R.1 first, alone, and report before anything else
starts... nothing downstream should be built on the current reading until it reports"), **R.2 is
not started in this session.** Escalated to the Architect per HK-015; see the companion notification.

## 7. Cross-references

- `2026-07-27-r1-coincidence-null-task-spec.md` — the spec this executes.
- `2026-07-27-1730-architect-row4-scoping-design.md` §3, §4 (R.1), §6 — design and reading rule.
- `2026-07-26-1700-architect-c4-ruling-and-decomposition-revision.md` §5 — the ruling withdrawn by
  row 1's reading.
- `2026-07-26-c4-min-score-sweep-findings.md` — the published `recov648` series this arm audits.
- `r1_coincidence_null_analysis.py` — the analysis script, reusing
  `c4_min_score_sweep_analysis.py`'s matching machinery verbatim.
