# QA → Architect — results: D-009 parameter recalibration

**Author:** QA, 2026-08-06 (00:24 UTC, `date -u`, per HK-017).
**Executes:** `qa/rr-study/2026-08-05-2003-architect-to-qa-spec-d009-recalibration.md` (`f6c5b46`),
via QA's own task breakdown `qa/rr-study/2026-08-05-2018-qa-tasks-d009-recalibration.md` (HK-015).
**Full report:** `qa/rr-study/results/2026-08-05-f6c5b46-d009-recalibration/report.md`
(`sweep_grid.csv`, `fp_by_density.csv`, `row_verdict.txt`, `orchestration.log` alongside it).
**Status:** ROW 1 fired. **Reported to the Captain; nothing shipped, nothing merged** (HK-010/
HK-014). This note is informational for you — it does not ask for a design decision, but flags
two things your spec didn't anticipate and one open question that's yours, not QA's, to settle.

---

## 1. Headline result

Mechanical rule evaluation (`apply_row_rule.py`, your Sec.5 transcribed verbatim): **ROW 1 —
the optimum has moved.** 6 points strictly `WIN(p)` over `B=(10,0.10,60)` on the restricted
decisive epoch (4,551 owsfz WAVs, `260803_185914` onward) plus the S5/S7 synthetic arms
(regenerated from seed this run, per your Sec.3.3 "why not 07-06" reasoning).

Baseline: recall 41.508% / S5 1-FP-in-120 / S7 8-FP-in-105 / S7 recovery 84.651%.
Best winner (`k5_c0.10_n40`): recall +0.109pp, S5 FP → 0, S7 FP → 1.

## 2. Two things worth your attention that the spec's language didn't distinguish

**2.1 — `WIN(p)` (relative to B) and "the full Pareto frontier" are different sets, and your
Sec.5's "report every winner, the full Pareto frontier" phrasing reads as if reporting one covers
the other. It doesn't.** The 6 `WIN` points are all `k in {5,7}` at `nhard=40`. The global
non-dominated frontier (computed separately, not part of your rule) swaps the `k=7` triple for a
`k=10` triple: `k10_*_n40` ties baseline's recall exactly (`recall_dpp=0.000`, correctly excluded
from `WIN` by the strict `>` in your rule) but posts **zero FP on both synthetic arms** — strictly
dominates `B`. Both facts are true and both are in the report (Sec.3.2/3.3), but a reader who
only checks "did ROW 1 fire, what's the nominee" would miss that the *cleanest* point in the grid
(one parameter changed, zero FP on 225 slots) isn't the nominee your own rule produces. Worth
deciding, for the next spec that uses this rule shape, whether `RELIEF`-style ties-on-recall
should be surfaced automatically alongside `WIN` rather than requiring a separate frontier
computation to notice them.

**2.2 — `corr` (`osd_corr_threshold`) is inert at `nhard=40`.** Across every `k`, all three
`corr` values (0.10/0.15/0.25) give byte-identical recall and FP rates once `nhard=40`. Its
effect is real but only visible at `nhard in {60,80}` (e.g. `k5_c0.25_n60` more than halves
`k5_c0.10_n60`'s FP rate). If a future sweep wants to isolate `corr`'s effect specifically, it
needs to hold `nhard` at a value where the effect hasn't saturated away — `nhard=40` is the wrong
anchor for that question, which the 45-point grid can't flag on its own (it just returns flat
numbers with no note that they're saturated).

## 3. Sec.5.4 delivered, with a confound flagged in the report (Sec.3.4)

Density stratification reproduces Finding 1 directly: baseline's leak concentrates in the
25-49/50-99 candidate buckets (co-channel regime), 9.09% FP rate in S7's densest populated
bucket, near-zero elsewhere — the same mechanism, now under controlled synthetic conditions
rather than inferred from a live log. At `nhard=40` it's gone (0 FP across both arms at every
bucket, for the points checked).

**Caveat for anyone reusing `density_stratify.py`:** the bucket variable (candidates found) is
itself a function of `k_min_score_pass2`, which also varies across the grid — at `k=5` every
single slot in both S5 and S7 falls in the `100+` bucket (vs. baseline `k=10`'s spread across
10-24/25-49). The stratification is real and reproducible *within* a fixed `k`, but the report
explicitly does not claim it isolates a density effect *across* `k` values, since `k` moves the
bucket assignment on its own. A genuine density-varying study (your spec's own eventual purpose
for this table) would need to hold `k` fixed and vary signal density directly — S5/S7 each carry
one candidate-load profile, so this run couldn't do that regardless.

## 4. Execution notes, not findings

- One harness bug, found and fixed during the run: Phase G's per-point loop built its list via
  `python -c "..." ` piped straight into `for pd in $(...)`; on this Windows box Python emits
  `\r\n`, and bash's `$(...)` word-splitting doesn't strip `\r`, so the first point's decode-log
  path grew a literal `\r` in it and the script crashed on point 1 of 45. Fixed with `| tr -d
  '\r'` at that one call site; reran Phase G only (no decode needed, all inputs already on disk)
  and got a clean 450-row `fp_by_density.csv` with no duplication. Recorded here in case anyone
  reuses `density_stratify.py`'s loop pattern elsewhere on Windows.
- The Captain asked mid-run to throttle from 16 to 12 shards (75% of cores) to keep the box usable.
  Phase D was ~6 minutes in and restarted clean from scratch — Phases B/C (already-cached FP arm)
  weren't touched. No data was lost or reused stale; noted only so the `orchestration.log`'s
  `FATAL: a decode shard failed` line (from the deliberate kill, not a real failure) doesn't read
  as an unexplained error to a future reader.

## 5. What's still open — yours, not QA's, to decide

- **`be5960a` attribution stays unresolved.** This harness bypasses `CycleFramer` (decodes
  per-slot WAVs directly), so it recalibrates *against* post-drift-fix framing but cannot itself
  confirm the drift fix moved the optimum from whatever it was pre-fix. Your spec's Sec.7.1
  already said this; repeating it here because it's the natural next question once a number
  actually exists to compare against. Arm A (Sec.3.4 of your spec, 07-06 corpus, not authorised)
  is still the only way to close it, and it's specced but costed-not-run by your own design.
- Everything your spec put out of scope (Sec.1) is still out of scope: bisecting the three
  flagged commits, the density term on the gate, the two managed-filter rule gaps (Sec.6.3),
  `K_MAX_CANDIDATES_PASS2`. Not reopened, just confirming none of them got pulled in by accident.
- The actual parameter decision (Option A / B / C, `report.md` Sec.5) is the Captain's per spec
  Sec.6.2. Not raised here as something for you to weigh in on unless he asks.
