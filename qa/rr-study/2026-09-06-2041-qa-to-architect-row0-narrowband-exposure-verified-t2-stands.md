# ROW 0 cleared — S5 narrowband exposure verified, T=2 stands

**From:** QA
**For:** Architect, and the record
**Date:** 2026-09-06 20:41 UTC
**Concerns:** `arch/s5-gate-sizing` Amendment 1, §A1.2's ROW 0 precondition on Check B's threshold.

---

## The precondition

Amendment 1 derived Check B's `T=2` from a base rate stated as "1 of 53 all-time FP events" for S5
parts 2/3 (narrowband: steady carrier + multi-carrier birdies) — an **event share**, not a **rate per
narrowband slot**. The denominator (how many parts-2/3 slots have actually been run across history)
was flagged as unverified, with an explicit stop: *"if the true per-slot base rate exceeds ~1%, T=2's
false-alarm rate rises above 12% and the threshold must be re-derived."*

## Method

`qa/rr-study/s5_narrowband_exposure_verify.py` (committed alongside this report), joining every
committed `results/<run>/truth.csv` (`scenario_id == "S5"` rows give `cycle_utc -> part_index`)
against that run's `S5_matched.csv` (`appraiser == "OpenWSFZ"`, `false_positive == True`, collapsed to
one event per slot, never per decode row) — the same method `fp_composition_per_part.py` uses,
extended from its nine named runs to **every** results directory that ever ran parts 2/3.

**ROW C1 (reproduction gate, run first):** recomputed `(events, n_slots)` against
`fp_composition_per_part.py`'s `REPORTED_GATE_OPENWSFZ` — transcribed from each of the nine runs' own
committed `report.md` gate line — for all nine. **All nine reproduce exactly.** Confidence the join
logic is sound before trusting the full-history number.

## Data-recovery note (disclosed, not buried)

11 of the 16 historical runs that ever included parts 2/3 do not have `S5_matched.csv` committed
(NFR-021: `qa/rr-study/results/*/*_matched.csv` is gitignored — raw appraiser decode logs). Those
files existed only as local, gitignored artefacts and **did not travel** when this worktree split
from the Architect's on 2026-09-06 — the exact gap the memory dir already flagged for `.venv`.
Confirmed present, untouched, in the Architect's worktree (`D:\Projects\claude\OpenWSFZ`).

**Captain-approved** local filesystem copy (asked first; classifier declined the cross-worktree read
until approved) of the 11 missing `S5_matched.csv` files from the Architect's worktree into this one.
No git operation involved — `git status --porcelain qa/rr-study/results` is empty after the copy,
confirming these land exactly where the existing gitignore pattern already expects them. The five
already-committed (redaction-mapped) `S5_matched.csv` files were never touched or overwritten.

Note for the record: the slot-count (denominator) side of this check did **not** depend on the
recovered files at all — `truth.csv` is committed for every run and was already sufficient to count
parts-2/3 slots. The recovery was needed only to locate the (small number of) FP events among those
slots, i.e. the numerator.

## Result

```
TOTAL parts 2/3 (16 runs, all history): slots=426  events=1
Per-slot narrowband base rate = 1/426 = 0.2347%
```

**0.2347% ≤ 1%** — the ROW 0 trigger does not fire. `T=2` is **not** re-derived; it stands as specified
in A1.2. For context, this is even below the Architect's illustrative "~0.3%" column in A1.2's table,
so Check B's actual false-alarm rate at `T=2` is ≤ the cited 1.4%, not higher.

The single historical narrowband event sits in `2026-06-20-d40b4cd` (part 2, pre-R&R-006 era, 6
slots) — not the 2026-06-20 OSD FAIL (`D-009`), which STUDY-SPEC already records as driven entirely
by parts 0/1. No revision to that attribution.

**Amendment 1's design (Gate A / Check B, T=2) is now fully cleared for execution.** Proceeding with
§6 tasks 1–5.
