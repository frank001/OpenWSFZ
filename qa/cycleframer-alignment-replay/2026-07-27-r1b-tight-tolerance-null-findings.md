# D-001 R.1b — the unfilled cell: findings

**Author:** QA, 2026-07-27. **Executes:**
`2026-07-27-1900-architect-r1-acceptance-and-r2-revision.md` §5. Reading rule applied verbatim from
that table, fixed by the Architect before this session ran.
**Result: row 2 fires at K=4@2000 — anti-correlation, not imprecise detection. Directionally
consistent but underpowered at K=10@600.**

---

## 1. Self-check

`compute_648_population` reproduced C.3's published split exactly (648/648) before any other number
was trusted, same as R.1.

## 2. Method, exactly as specified

One change to the existing R.1 harness: compute the frequency-displaced null (8 displacements,
±150/300/450/600 Hz, same wrap) across the full 4×3 tolerance ladder, not only at the published
±10 Hz/±0.5 s. True and null reported side by side in every cell, both settings. No new instrument.

## 3. Full results

### K=10@600

| freq tol | dt tol | TRUE | null mean | true−null | null range (8 trials) |
|---:|---:|---:|---:|---:|---|
| 10 | 0.5 | 16.2% | 16.6% | −0.4 | 13.0–21.0% |
| 10 | 0.16 | 3.5% | 5.7% | −2.2 | 4.2–8.2% |
| 10 | 0.08 | 1.4% | 3.4% | −2.0 | 2.3–5.6% |
| 5 | 0.5 | 6.0% | 9.7% | −3.6 | 6.6–12.3% |
| 5 | 0.16 | 1.1% | 3.0% | −1.9 | 2.2–3.9% |
| 5 | 0.08 | 0.5% | 1.7% | −1.2 | 0.9–2.5% |
| 3.125 | 0.5 | 3.5% | 7.0% | −3.4 | 4.0–8.6% |
| 3.125 | 0.16 | 0.8% | 2.4% | −1.6 | 1.5–3.2% |
| 3.125 | 0.08 | 0.3% | 1.3% | −1.0 | 0.5–2.2% |
| 1.5625 | 0.5 | 2.0% | 4.0% | −2.0 | 2.8–5.1% |
| 1.5625 | 0.16 | 0.6% | 1.3% | −0.7 | 0.9–2.0% |
| 1.5625 | 0.08 | 0.3% | 0.7% | −0.4 | 0.2–0.9% |

**12 of 12 cells negative** (true below null mean). Only 2 cells put true below the null's own
*minimum* (5 Hz/0.5 s: 6.0% vs. floor 6.6%; 3.125 Hz/0.5 s: 3.5% vs. floor 4.0% — both by less than
one point). The rest sit inside the null's 8-trial spread. At this candidate density (~220/cycle)
the null itself is noisy enough that most cells cannot be distinguished from it individually, even
though the direction is consistent across all 12.

### K=4@2000

| freq tol | dt tol | TRUE | null mean | true−null | null range (8 trials) | true vs. null floor |
|---:|---:|---:|---:|---:|---|---|
| 10 | 0.5 | 95.4% | 90.8% | **+4.5** | 90.3–91.8% | above ceiling |
| 10 | 0.16 | 52.9% | 57.0% | −4.1 | 53.2–61.1% | below floor by 0.3 |
| 10 | 0.08 | 29.3% | 38.2% | −8.9 | 36.1–40.1% | below floor by 6.8 |
| 5 | 0.5 | 67.1% | 73.9% | −6.8 | 71.1–75.9% | below floor by 4.0 |
| 5 | 0.16 | 22.2% | 35.6% | −13.4 | 31.8–38.1% | below floor by 9.6 |
| 5 | 0.08 | 11.6% | 21.5% | −10.0 | 20.2–23.6% | below floor by 8.6 |
| 3.125 | 0.5 | 49.8% | 60.1% | −10.3 | 57.9–63.1% | below floor by 8.1 |
| 3.125 | 0.16 | 14.7% | 25.9% | −11.2 | 21.9–28.2% | below floor by 7.2 |
| 3.125 | 0.08 | 8.0% | 15.2% | −7.2 | 13.4–16.5% | below floor by 5.4 |
| 1.5625 | 0.5 | 32.6% | 39.2% | −6.6 | 38.0–43.5% | below floor by 5.4 |
| 1.5625 | 0.16 | 8.5% | 14.9% | −6.4 | 12.5–17.3% | below floor by 4.0 |
| 1.5625 | 0.08 | 4.5% | 8.4% | −3.9 | 6.9–10.3% | below floor by 2.4 |

**11 of 12 cells negative, and 10 of those 11 put the true rate below the *minimum* of all 8
individual displacement trials** — not just below the null's mean, below its entire observed range.
Only the published ±10 Hz/±0.5 s cell (R.1's original result) shows separation in the other
direction. Every cell strictly tighter than that flips and stays negative, by margins up to 9.6
points on bases of 20–75%.

## 4. Reading (Architect's §5 table, applied)

**At K=4@2000: row 2 fires — anti-correlation, not row 3 (imprecise detection).**

> True materially below null at tight tolerance → **Anti-correlation.** The detector systematically
> does not fire where these signals are. Strongest available pointer at the sync scoring metric;
> R.3's D-miss class is expected to dominate and R.3 becomes the confirmatory arm, not the
> exploratory one.

This is not a marginal read. The effect is not "true sits a bit low against a noisy null" — in 10 of
12 tightened cells the true rate sits outside the *entire spread* of 8 independent null trials, each
constructed from the same population at the same candidate density with only the target frequency
moved. There is no tolerance at which true rate ever separates *above* the null once you leave the
published ±10 Hz/±0.5 s window — which is itself the cell R.1 already flagged as measuring density,
not detection.

**At K=10@600: directionally consistent, statistically underpowered.** All 12 cells are negative,
but only 2 clear the null's own floor, and by less than a point. With ~220 candidates/cycle (9x
fewer than K=4@2000) the null's 8-trial spread is wide enough to swallow a real but smaller effect.
This setting cannot confirm or refute row 2 on its own; it does not contradict it either.

## 5. What this changes for R.2/R.3, stated for the Architect to rule on rather than assumed here

Per the Architect's own §5 table, this reading — not row 3 ("imprecise detection")— is the one that
fires. Two consequences follow from his own pre-committed logic, stated here as observations, not
QA judgement calls on the study's direction (that stays his per HK-015):

- **No separation tolerance τ exists to size R.2's grid from** — row 3 (which would have handed R.2
  an empirical τ) did not fire. §6's widened grid (two lattice steps) is confirmed to still be a
  judgement call, not a measurement, exactly as his §9 caveat already flagged.
- **The anti-correlation reading points at the sync scoring metric itself**, not at estimator
  precision — a different mechanism than "our candidate lands near the signal but off by a bin or
  two." R.2 (which plants signals at *controlled offsets from a known lattice point* and measures
  demodulation) does not test this mechanism at all — it tests what an offset costs, not whether our
  detector produces offset candidates in the first place near weak signals, versus not firing near
  them at all. R.3's D-miss/E-loss/X-loss split is the arm that can actually see this, which is
  consistent with the Architect's own reading — flagging it because R.2 running before R.3 (current
  §7 sequencing) means the grid gets built before the mechanism it's meant to test is confirmed to
  be the right one.

## 6. Honest caveats

- **The "materially below" / "≈ null" boundary was not numerically pre-specified** by the Architect's
  own §5 table (nor was R.1's "within a few points" for row 1) — both are qualitative judgement
  calls applied after the fact, consistent with this thread's established practice, not a deviation
  from it. To keep that judgement call auditable rather than asserted, this findings doc reports the
  full null range per cell (not just the mean), and the headline claim (10 of 11 negative cells at
  K=4@2000 fall outside the *entire* 8-trial null range) does not depend on where exactly that
  boundary is drawn.
- **Same uniform-placement-adjacent caveat as R.1**: the null is a same-density, same-neighbourhood
  displaced control, not a true uniform-random null — this is a strength (§2 of the Architect's 19:00
  note explains why it makes the result conservative), not a weakness, but it means "anti-correlated
  with the 648's locations" is relative to nearby real spectrum, not to empty spectrum.
- **This does not identify *why* the detector is anti-correlated with these locations** — only that
  it is. Mechanism (scoring metric tuned against strong-signal statistics, e.g.) is domain
  speculation, not measured here.

## 7. Self-check discipline note

Per this thread's convention and the Architect's own §5/§9, this result is routed back to him before
R.2 is scoped or run, since it changes what R.2's grid is being built to test (§5 above) rather than
merely sizing it.

## 8. Cross-references

- `2026-07-27-1900-architect-r1-acceptance-and-r2-revision.md` §5 — the design and reading rule this executes.
- `2026-07-27-r1-coincidence-null-findings.md` — R.1, whose Condition 1 (±10 Hz/±0.5 s only) this extends.
- `r1b_tight_tolerance_null_analysis.py` — script, reusing `r1_coincidence_null_analysis.py` and
  `c4_min_score_sweep_analysis.py` verbatim.
