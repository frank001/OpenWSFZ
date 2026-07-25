# Phase 1b findings — confirm-and-cut: the model survives its first out-of-sample test

**Author:** QA session, 2026-07-25. **Scope:** SPEC.md section 9 Phase 1b (`tasks.md` 11.5-11.6),
run via `run_phase1b.py` on the full `artefacts/20260724_live_run_2227/wav/` corpus (2,827 files,
all 15 segments). ~7,624 decodes total (2,827 baseline + 4,797 across 11 sweep arms — slightly
under the ~7,200 estimate's sweep half because a handful of near-boundary cycles couldn't be cut
at the largest offsets, exactly as anticipated).

## Headline result

**PHASE 1B FALSIFICATION VERDICT: MODEL SURVIVES.** All three parts of SPEC.md section 5.2's
mandatory criterion pass, stated and evaluated in that order (verdict not looked at until all 11
points were in):

1. **Per-point tolerance:** 11/11 points within tolerance (|resid| <= 0.10 outside cliff
   transitions, <= 0.25 inside). RMS error **0.056** — better than Phase 0/1a's own 0.085-0.088,
   on a sample 16x larger and, critically, **not the same 25 cycles the model was built from.**
   This is the first genuinely out-of-sample check §2.5 item 10 has had.
2. **Positive 50% crossing:** measured 2.434, predicted 2.400 (`DT_med + 1.60`), within +/-0.15. PASS.
3. **Negative 50% crossing:** measured -2.345, predicted -2.320 (`DT_med - 3.12`), within +/-0.15. PASS.

## Session-wide baseline

- **DT_med = +0.80** across all 51,862 signals in the full 2,827-cycle baseline — identical to
  segment 0's estimate from Phase 0/1a (n=585). No revision needed to deliverable #5's reference
  point; the earlier 25-cycle sample was not, in this respect, unrepresentative.
- **Every one of the 2,827 cycles qualified** under the `|ref(k)| >= 5` filter — zero exclusions.
  The band was active enough all night that no stratification bias was introduced by that filter.
- **`hashTableRejectCount` (full baseline, all 2,827 cycles) = 73,490.** The 256-slot table
  saturates early and keeps rejecting new callsigns for the rest of an 11h51m session on a busy
  band — a real, session-scale phenomenon, not a smoke-test artefact (the 2-segment smoke test
  already showed 11,846 after just 1/15th of the session).

## Measured vs. predicted (11 points, session-wide DT_med)

| delta | measured | predicted | resid | zone | tol | verdict |
|---|---|---|---|---|---|---|
| -2.750 | 0.045 | 0.044 | +0.001 | outside | 0.10 | OK |
| -2.500 | 0.091 | 0.107 | -0.016 | inside | 0.25 | OK |
| -2.250 | 0.750 | 0.591 | **+0.159** | inside | 0.25 | OK |
| -2.000 | 0.875 | 0.896 | -0.021 | inside | 0.25 | OK |
| -1.000 | 0.939 | 0.986 | -0.046 | outside | 0.10 | OK |
| +2.000 | 0.902 | 0.956 | -0.054 | outside | 0.10 | OK |
| +2.250 | 0.850 | 0.893 | -0.043 | inside | 0.25 | OK |
| +2.500 | 0.375 | 0.409 | -0.034 | inside | 0.25 | OK |
| +2.750 | 0.100 | 0.104 | -0.004 | inside | 0.25 | OK |
| +3.000 | 0.056 | 0.076 | -0.020 | inside | 0.25 | OK |
| +3.500 | 0.000 | 0.020 | -0.020 | outside | 0.10 | OK |

The largest residual, delta=-2.25 (+0.159), reproduces the same sign and roughly the same
location as Phase 1a's largest residual (delta=-2.375, +0.236 there) — a consistent pattern
across both an independent 25-cycle sample and this 400-cycle one, not noise. The model
slightly *under*-predicts recall in that specific stretch of the negative cliff both times.
Still comfortably inside the inside-transition tolerance (0.25), so it does not affect the
verdict, but it is a specific, reproducible discrepancy worth carrying into the report rather
than averaging away.

## The left tail persists at scale (SPEC.md section 5.3's amendment, confirmed)

Zero-recall cycle counts and p10, alongside the median, for all 11 points:

| delta | median | p10 | zero_recall_n / 400 |
|---|---|---|---|
| -2.750 | 0.045 | 0.000 | 158 (39.5%) |
| -2.500 | 0.091 | 0.000 | 73 (18.3%) |
| -2.250 | 0.750 | 0.600 | 3 |
| -2.000 | 0.875 | 0.769 | 3 |
| -1.000 | 0.939 | 0.846 | 3 |
| +2.000 | 0.902 | 0.810 | 1 |
| +2.250 | 0.850 | 0.727 | 1 |
| +2.500 | 0.375 | 0.227 | 2 |
| +2.750 | 0.100 | 0.000 | 59 (14.8%) |
| +3.000 | 0.056 | 0.000 | 116 (29.0%) |
| +3.500 | 0.000 | 0.000 | 271 (67.8%) |

Even at delta=-1.00, comfortably inside the tolerance band with median 0.939, **3 of 400 cycles
still decode nothing at all.** This is expected under section 2.5 item 10's population-statistic
framing (every station is in or out on its own DT), not a defect, but it is exactly why deliverable
#5 must be quoted against a stated percentile and not the median alone.

## Guards — both held, and the second one now has an actual explanation, not just a number

- **Collision assertion (section 7.4(b-i)):** triggered zero times across the full run (baseline
  + 11 sweep arms, ~7,600 decodes, every cycle re-checked). `check_no_collisions()` would have
  raised a hard `SystemExit` on the first merge; none occurred.
- **Reject-count recording (section 7.4(b-ii)):** recorded per arm as required. Went further than
  "record it" — checked whether it actually behaves as a confound. Correlated total decoded-message
  count per arm (from each arm's own `ALL.TXT` line count) against `hashTableRejectCount`:
  **Pearson r = 0.998** across the 11 sweep arms. Reject count is essentially fully explained by
  how many messages that arm decoded, with no independent delta-specific anomaly. Combined with
  the source-level finding reported earlier this session (`ft8_shim.c` lines 608-612: a reject
  only affects whether a callsign later *displays* resolved or as `<HASH>` — "no crash, no hang, no
  data corruption" — which `normalize_hash_tokens()` already neutralizes), this guard is now closed
  with an actual mechanistic answer, not merely a recorded-and-hoped-inert number.

## Consequence

Per SPEC.md section 9, a surviving model means the curve is now **derived** from the session-wide
DT distribution and the decoder's own search bound, rather than requiring further tracing. This
unblocks, per `tasks.md`:
- **11.7** (deliverables, in particular #5's asymmetric interval) — has the data it needs now.
- **10.6** (DT-offset-vs-correction-sum comparison) and **11.10** (D-001 absolute-gap sizing) —
  both explicitly sequenced to start after 11.5, which is now done.

Not done in this pass, deliberately: 11.7's actual deliverable writeup, 11.8's report.md, and
starting 10.6/11.10. Reporting this verdict first rather than proceeding straight through.

## Raw outputs

`_work/phase1b/phase1b_summary.csv` (11-row measured table), `phase1b_verdict.json` (criterion
booleans + RMS + crossings), `baseline_dt_population.json` (51,862-signal DT distribution),
`selection.json` (the 400 stratified cycle IDs). All local/git-ignored per NFR-021 — contain real
third-party callsigns via the underlying `ALL.TXT` files they were derived from.
