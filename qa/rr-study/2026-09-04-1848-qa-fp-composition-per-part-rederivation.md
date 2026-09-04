# `FP-COMPOSITION` -- S5 FP per-part re-derivation (QA task result)

**QA, 2026-09-04 18:48Z** (`date -u`, HK-017). Runs the spec in
`qa/rr-study/2026-09-04-1820-architect-to-qa-amendment1-and-spec-s5-fp-per-part-rederivation.md`
("QA SPEC -- S5 FP per-part re-derivation (`FP-COMPOSITION`)").

**No decode. No capture. No `src/`/`native/` change.** `git diff --stat -- src/ native/` is empty.
Pure re-analysis of the nine already-committed run directories under `qa/rr-study/results/`, via a
new script, `qa/rr-study/fp_composition_per_part.py`, that ships the join as code rather than as
prose (HK-021(r)) so it can be re-run by anyone.

`2e60949` note: S5 data was taken from **`2026-08-30-2e60949/`** (864-row `S5_matched.csv`). The
`2026-08-31-2e60949/` directory has no `S5_matched.csv` -- it is the S7 re-run (Section 6 footnote 5)
-- and was not used.

---

## Method (restated from the spec; full detail in the script's docstring)

1. From each run's `truth.csv`, take rows with `scenario_id == "S5"` → the set of `cycle_utc` values
   that genuinely belong to S5, and the `cycle_utc -> part_index` map. This is the scoping filter;
   without it the join over-attributes, because `matcher.py` parses the whole session `ALL.TXT`
   unscoped by time.
2. From `S5_matched.csv`, take `false_positive == True` rows for a given `appraiser`, restricted to
   those `cycle_utc` values.
3. Collapse decode rows to the gate's own unit -- the **per-slot event**: a slot (`cycle_utc`) with
   ≥1 unmatched decode is one event, not one event per decode row.
4. Attribute each event to its `part_index` via step 1's map.

Run with: `python qa/rr-study/fp_composition_per_part.py`

---

## ROW C1 -- reproduction gate: **does not fire**

Recomputed (event count, N) vs. each run's own ratified `report.md` §10 gate line, both appraisers,
all nine runs:

| Run | Appraiser | Recomputed | report.md | Match |
|---|---|---|---|---|
| `2026-08-05-3bd4cd0` | OpenWSFZ | 0/120 | 0/120 | OK |
| `2026-08-05-3bd4cd0` | WSJT-X | 0/120 | 0/120 | OK |
| `2026-08-15-8d6e1b1` | OpenWSFZ | 1/120 | 1/120 | OK |
| `2026-08-15-8d6e1b1` | WSJT-X | 0/120 | 0/120 | OK |
| `2026-08-21-7d36038` | OpenWSFZ | 1/120 | 1/120 | OK |
| `2026-08-21-7d36038` | WSJT-X | 0/120 | 0/120 | OK |
| `2026-08-22-f5dec23` | OpenWSFZ | 4/120 | 4/120 | OK |
| `2026-08-22-f5dec23` | WSJT-X | 0/120 | 0/120 | OK |
| `2026-08-27-22b749c` | OpenWSFZ | 0/60 | 0/60 | OK |
| `2026-08-27-22b749c` | WSJT-X | 0/60 | 0/60 | OK |
| `2026-08-29-872ba65` | OpenWSFZ | 1/60 | 1/60 | OK |
| `2026-08-29-872ba65` | WSJT-X | 0/60 | 0/60 | OK |
| `2026-08-30-2e60949` | OpenWSFZ | 2/120 | 2/120 | OK |
| `2026-08-30-2e60949` | WSJT-X | 0/120 | 0/120 | OK |
| `2026-09-02-3b52608` | OpenWSFZ | 4/60 | 4/60 | OK |
| `2026-09-02-3b52608` | WSJT-X | 0/60 | 0/60 | OK |
| `2026-09-03-35378b9` | OpenWSFZ | 2/60 | 2/60 | OK |
| `2026-09-03-35378b9` | WSJT-X | 0/60 | 0/60 | OK |

18/18 pairs reproduce exactly. **The join has standing to re-attribute the ratified per-run numbers.**

Side note, not a spec deliverable but a consistency check: the WSJT-X column sums to **0/840** across
all nine runs (120×5 + 60×4 = 840) -- matches the standing "WSJT-X `0/840` control" figure on record.
Not re-measured as new evidence; cited here only because the reproduction happened to touch it.

## ROW C2 -- `2026-08-15-8d6e1b1` anomaly: **does not fire**

| Quantity | Value |
|---|---|
| Recomputed events (OpenWSFZ), scoped to S5 `cycle_utc` | 1 (expected 1) |
| Scoped FP decode rows (OpenWSFZ), post `cycle_utc` filter | 1 |
| Raw `S5_matched.csv` row count, unscoped | 204,220 |
| Median scoped FP rows across the other 8 runs | 1.5 |
| Ratio (this run's scoped rows ÷ median of the other 8) | 0.67x |

Fire condition was: recomputed events ≠ 1, **OR** scoped-row ratio > 5x. Neither holds. The
204,220-row bloat is confirmed to be **entirely outside** the S5 scoping filter -- essentially none of
those rows carry a `cycle_utc` that belongs to S5's own 120-slot window. Scoping alone neutralises the
anomaly for this metric; it says nothing about whether that bloat matters elsewhere (out of scope for
this task).

## ROW C3 -- composition table: **does not fire**

Evaluated because C1 and C2 both cleared.

| | events | slots gated | AWGN slots (parts 0,1) | events in parts 0/1 | events in parts 2/3 |
|---|---|---|---|---|---|
| Pre-window (3 runs: `3bd4cd0`, `8d6e1b1`, `7d36038`) | 2 | 360 | 180 | 2 | 0 |
| Post-window (6 runs: `f5dec23`, `22b749c`, `872ba65`, `2e60949`, `3b52608`, `35378b9`) | 13 | 480 | 360 | 13 | 0 |

Fire condition was: any event attributes to part 2 or 3. **Zero of the 15 events do.** All 15 fall in
parts 0/1 (AWGN), matching the 52/53 all-time prior cited in STUDY-SPEC §16 and R&R-009's own
rationale.

Per-run detail (OpenWSFZ, for the record):

| Run | N slots | Events | By part |
|---|---|---|---|
| `2026-08-05-3bd4cd0` | 120 | 0 | -- |
| `2026-08-15-8d6e1b1` | 120 | 1 | part 0: 1 |
| `2026-08-21-7d36038` | 120 | 1 | part 0: 1 |
| `2026-08-22-f5dec23` | 120 | 4 | part 0: 3, part 1: 1 |
| `2026-08-27-22b749c` | 60 | 0 | -- |
| `2026-08-29-872ba65` | 60 | 1 | part 1: 1 |
| `2026-08-30-2e60949` | 120 | 2 | part 0: 1, part 1: 1 |
| `2026-09-02-3b52608` | 60 | 4 | part 0: 2, part 1: 2 |
| `2026-09-03-35378b9` | 60 | 2 | part 0: 1, part 1: 1 |

---

## 🛑 No verdict, no ratio, no p-value

Per the spec: this task reports per-part counts and the ROW C1 reproduction table only. The
re-derived contrast (whatever `2/180` vs `13/360` etc. computes to) and its ratification are the
Architect's and the PO's, not QA's, to produce here.

## NFR-021

`scan()` (imported from `qa/rr-study/nfr021_pre_merge_scan.py`, not a raw directory walk, per
memory's standing instruction) run against both new files before commit:

- `qa/rr-study/fp_composition_per_part.py` -- 0 flagged, 0 grid-excluded.
- This report (`2026-09-04-1848-qa-fp-composition-per-part-rederivation.md`) -- 0 flagged, 0
  grid-excluded.

No raw decode rows are pasted anywhere in this report or in the script's fixed literals -- only
counts, run names, and part indices.

---

## Hard stop

Per the spec's closing instruction: **commit locally and hand back.** Not proceeding to any re-scope.
`main` is local-only (unpushed); this task adds no `src/`/`native/` diff, so HK-029's push exception
is not evaluated here.
