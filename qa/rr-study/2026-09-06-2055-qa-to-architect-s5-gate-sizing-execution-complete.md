# S5-GATE-SIZING §6 execution complete — Gate A / Check B live, never pooled

**From:** QA
**For:** Architect, and the Captain (merge sign-off, HK-010)
**Date:** 2026-09-06 20:55 UTC
**Concerns:** `arch/s5-gate-sizing` Amendment 1, §6 tasks 1–5. Branch:
`qa/2026-09-06-s5-gate-sizing-execution` (built directly on the Architect's three commits).

---

## ROW 0 — cleared (separate report, same branch)

See `2026-09-06-2041-qa-to-architect-row0-narrowband-exposure-verified-t2-stands.md`: measured
all-history narrowband base rate 0.2347% (426 slots, 1 event), below the ~1% trigger. `T=2` stands.

## §6 tasks — status

**1. `scenarios/s5-noise.json`.** Parts 0/1 carry a new per-part `"trials": 60` override (Gate A,
120 AWGN slots); parts 2/3 use the file's existing default of 30 (Check B, 60 narrowband slots).
`description`, `trials_note`, and `parts_note` updated to record the supersession of R&R-009's
restriction.

**2. `harness/analyse.py`.** Gate A and Check B are now two independently computed, independently
reported, independently gated rows — never pooled:

- `_s5_cycle_part_map` / `_fp_rate_for_parts` — see the defect below for why this is cycle_utc-scoped
  rather than filtered on the matched CSV's own `part_index` column.
- `_verdict_s5_narrowband` — `FAIL iff events ≥ THRESH_S5_NARROWBAND_FAIL (2)`, no
  `MIN_N_FOR_FP_GATE` demotion (not a Clopper–Pearson gate; the threshold sits on the readout
  quantum, HK-021(o)).
- Two verdict rows (`_collect_verdicts`), two report tables (`_write_report`), each with its own
  note text. `trend.csv`'s existing `fp_rate_s5` column is untouched in meaning (always Gate A);
  Check B has no trend-line column yet — flagged as follow-up, not silently bolted onto an
  already-committed CSV's header without a migration.

🔴 **A second defect found and fixed during execution, not present in the spec.** S5's
false-positive DECODE rows never carry a usable `part_index` in `S5_matched.csv` — confirmed
directly against `results/2026-08-22-f5dec23/S5_matched.csv`: every `false_positive == True` row has
`part_index = NaN` (matcher.py cannot attribute an unmatched extra decode to any specific truth
row). My first implementation filtered the matched dataframe on its own `part_index` column before
computing each check's rate — which silently discarded **every** FP event from both Gate A and
Check B (a sanity run against `f5dec23` showed 0/60 events where 4 were expected). Caught by testing
against a known historical figure before trusting the code, not by inspection. Fixed by building the
cycle_utc → part_index map from the (correctly labelled) per-slot baseline rows and scoping by
`cycle_utc` membership instead — the same method `fp_composition_per_part.py` already uses, for the
same reason. Re-verified against `f5dec23` (Gate A now correctly reports 4/60 for OpenWSFZ, matching
the historical record) and `2026-06-20-d40b4cd` (Check B correctly reports 1/6, the one all-time
narrowband event).

**3. `STUDY-SPEC.md`.** §10's threshold table now lists Gate A and Check B as separate rows, with an
amendment note under the false-positive gate definition. §16 gets a new entry, **R&R-010**,
recording the split, the ROW 0 clearance, and the second (part_index) defect; the R&R-009 entry is
marked SUPERSEDED (kept unedited as the historical record, per this codebase's convention of not
rewriting history).

**4. Section 6 footnote.** Not applied retroactively to `results/2026-09-03-35378b9/report.md` —
that table is a dated, per-sweep record and this design postdates it; editing it now would be
anachronistic. Instead, STUDY-SPEC.md's R&R-010 entry carries an explicit note for whoever next
appends a row: the `S5 FP` column now spans three denominator classes, give the new row the same
class of footnote the S1/S3 redesigns already carry, and normalise per AWGN slot first (HK-031).

**5. Re-verify §2's event counts independently.** All nine of the Architect's normalised FP-series
rows reproduce exactly:

- Eight (`3bd4cd0` through `35378b9`) via `s5_narrowband_exposure_verify.py`'s ROW C1, which
  recomputes `(events, n_slots)` against `fp_composition_per_part.py`'s own `REPORTED_GATE` —
  transcribed from each run's committed `report.md` gate line — and matches on all eight.
- The ninth (`4c7d5ad`, 2026-09-06) independently, direct from its `S5_matched.csv` (no `truth.csv`
  was ever generated for this run — the analysis/report step of my own 164650d sweep was never
  run): **OpenWSFZ 3/60, WSJT-X 0/60**, matching the Architect's cited figure of 3 exactly.

## Verification

- `git diff --stat -- src/ native/` empty on this branch — HK-011 not engaged.
- Full `qa/rr-study` test suite: **181 passed**, no regressions from the `_fp_rate_for_parts` split
  or the `run_scenario.py` per-part trials change (no existing scenario uses a part-level `"trials"`
  key, confirmed by scanning every `scenarios/*.json`, so the change is additive-only).
- Manual sanity runs of `harness/analyse.py --scenario S5` against two historical run directories
  (`f5dec23`, `d40b4cd`) before and after the part_index fix, reproducing known figures both times
  after the fix.

## What this does NOT do

Same list as the spec's own §7: does not lower the FP rate, does not reopen `FP-PARITY` P4b (still
PARKED), does not make the board green, does not touch the suspended S7 figures. This is a gate
*design* correction, not a decoder finding.

## Next

Branch pushed for PR; **merge to `main` needs the Captain's explicit sign-off (HK-010)**, separate
from the take/push/PR discretion already granted for the Architect's commits (HK-014,
PO-directed). The next real S1–S8 sweep will exercise Gate A/Check B live for the first time and
should be the one to add the next Section 6 row with its footnote.
