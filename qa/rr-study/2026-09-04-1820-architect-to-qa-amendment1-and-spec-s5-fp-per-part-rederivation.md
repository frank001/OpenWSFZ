# `FP-REGRESSION` §6 -- Amendment 1 (two Architect errors corrected) + QA spec: S5 FP per-part re-derivation

**Architect, 2026-09-04 18:20Z** (`date -u`, HK-017). Amends
`2026-09-04-1811-architect-to-qa-ruling-row0a-accepted-and-composition-finding.md` §6 and specifies
the QA task the PO ratified ("QA re-derives per-part first"). PO also ratified the HK-031 extension.

**Status of §6: STRENGTHENED, not weakened.** Its denominators are now verified from each run's own
report rather than inferred from Section 6's summary column. Two errors in how I *supported* it are
corrected below, and one new data anomaly is disclosed that the QA task must handle.

---

## A. ARCHITECT ERROR 1 -- "R&R-009's own attribution machinery already exists" is WRONG

§6 told QA to "re-run" existing tooling. **There is no such tooling.** `58bc7ac` touched exactly
three files:

```
qa/rr-study/STUDY-SPEC.md           | 41 +++++
qa/rr-study/run_study.py            | 29 +++--
qa/rr-study/scenarios/s5-noise.json |  2 ++
```

No script was committed. The reconstruction was done ad hoc and only its **conclusion** (52/53) and
its **method** survive, as prose in STUDY-SPEC §16. **QA must implement the join, not re-run it.**
I asserted tooling existed without checking -- the same failure mode I corrected in the 15:07Z
ruling, committed by me, one document later.

✅ **The method is fully specified in STUDY-SPEC §16 and is correct** -- join each run's
`S5_matched.csv` false-positive rows against `truth.csv`'s per-slot `part_index`, **restricted to
`cycle_utc` values that actually belong to S5**, because `matcher.py`'s `main()` parses the entire
session `ALL.TXT` unscoped by time and an unfiltered join over-attributes decodes from other
scenarios.

✅ **Independently confirmed, so the join is genuinely required:** `part_index` is **empty on 100%
of false-positive rows in all nine runs** (checked directly). There is no shortcut groupby.

## B. ARCHITECT ERROR 2 -- I nearly refuted §6 on a STUDY-SPEC sentence that does not mean what it says

STUDY-SPEC §16 states:

> "The §10 false-positive gate's arithmetic (`4/60`, `1/60`, `3.3%/N=120`, etc.) is **unaffected**:
> it counts **AWGN slots (60 = 2 parts × 30 trials)**."

Read literally, that says the gate denominator was **always** 60 AWGN slots, which would mean there
is no composition change and §6 is void. **It is not what happened.** Each run's own report states
its denominator explicitly:

| Run | Date | Gate line, verbatim from that run's `report.md` |
|---|---|---|
| `7d36038` | 08-21 (pre) | `1/120 slots (event 0.8%; 95% UB 3.89%)` **PASS** |
| `f5dec23` | 08-22 | `4/120 slots (event 3.3%; 95% UB 7.47%)` **FAIL** |
| `35378b9` | 09-03 | `2/60 slots (event 3.3%; 95% UB 10.12%)` **FAIL** |

and `f5dec23`'s report says outright: *"it ran the full, unrestricted S5 (all four parts, 120
slots)."*

⇒ **The denominator was 120 (all four parts) before R&R-009 and 60 (AWGN only) after.** §16's
sentence describes the post-R&R-009 gate only and is **misleading when read against the N=120 era**.
🔴 **Follow-up (not part of this task): §16 needs that sentence scoped to the post-R&R-009 battery.**

⚠️ **Method note, load-bearing for anyone re-checking this:** Section 6's `S5 FP` column **mixes two
statistics** -- its own header says "95% UB where computed, else the plain event/decode rate for
older entries". `35378b9`'s `10.12%` is a **95% upper bound** on `2/60`, not a rate. **Per-sweep
event counts CANNOT be back-computed from that column.** Take counts from each run's own report.

## C. NEW ANOMALY -- disclosed, and it lands in the pre-window numerator

`S5_matched.csv` row counts across the nine sweeps:

| Run | rows | Run | rows |
|---|---|---|---|
| `2026-08-05-3bd4cd0` | 1,011 | `2026-08-29-872ba65` | 992 |
| 🔴 **`2026-08-15-8d6e1b1`** | **204,220** | `2026-08-30-2e60949` | 864 |
| `2026-08-21-7d36038` | 1,107 | `2026-09-02-3b52608` | 1,030 |
| `2026-08-22-f5dec23` | 1,143 | `2026-09-03-35378b9` | 1,024 |
| `2026-08-27-22b749c` | 1,016 | | |

🔴 **`8d6e1b1` is ~200x every other run** -- the signature of exactly the unscoped-`ALL.TXT`
over-attribution STUDY-SPEC §16 warns about, at scale. **It is a PRE-window sweep contributing 1 of
the 2 pre-window events.** If its event count is wrong, the pre-window numerator moves and **both**
`4.88x` and my `3.25x` move with it. This must be resolved, not noted.

🔴 **Also: `2026-08-31-2e60949/` has NO `S5_matched.csv`.** That run's S5 data is in
**`2026-08-30-2e60949/`** (864 rows). The 08-31 directory is the S7 re-run (Section 6 footnote 5).
Use the 08-30 directory for S5 and say which you used.

---

# QA SPEC -- S5 FP per-part re-derivation (`FP-COMPOSITION`)

**No decode. No capture. No `src/`/`native/` change.** Pure re-analysis of committed artefacts.
Nine run directories under `qa/rr-study/results/`. Ship the predicate as code (HK-021(r)).

## Inputs (all committed)

Per run: `S5_matched.csv` (`part_index`, `false_positive`, `cycle_utc`, `appraiser`) and `truth.csv`
(`scenario_id`, `part_index`, `trial_index`, `cycle_utc`). Runs: `2026-08-05-3bd4cd0`,
`2026-08-15-8d6e1b1`, `2026-08-21-7d36038`, `2026-08-22-f5dec23`, `2026-08-27-22b749c`,
`2026-08-29-872ba65`, **`2026-08-30-2e60949`**, `2026-09-02-3b52608`, `2026-09-03-35378b9`.

## Method

1. From `truth.csv`, take the set of `cycle_utc` values with `scenario_id == S5`, and the
   `cycle_utc -> part_index` map. **This is the scoping filter** -- without it the join
   over-attributes (STUDY-SPEC §16).
2. From `S5_matched.csv`, take `false_positive` rows for `appraiser == OpenWSFZ`, restricted to
   those `cycle_utc` values.
3. Collapse to the gate's own unit: **the per-slot EVENT** -- a slot with >= 1 unmatched decode --
   not the decode row. STUDY-SPEC §10: *"the per-slot FP event rate -- P(a signal-free S5 slot emits
   >= 1 decode)"*. **Reporting decode rows as events is the single most likely way to get this
   wrong.**
4. Attribute each event to its `part_index` via step 1's map.
5. Report per run: **N slots gated, event count, and the per-part split.** Also run the identical
   pipeline for `appraiser == WSJT-X` -- it should be 0 everywhere, and a non-zero is a **STOP**.

## ROW C1 -- reproduction gate, evaluated FIRST

**FIRES iff, for any of the nine runs, the recomputed OpenWSFZ event count and N do not equal that
run's own `report.md` gate line** (e.g. `7d36038` must reproduce exactly `1` event in `120` slots;
`f5dec23` `4`/`120`; `35378b9` `2`/`60`).

**Consequence if it FIRES: STOP and report.** A pipeline that cannot reproduce the ratified per-run
numbers has no standing to re-attribute them, and nothing downstream may be cited. **This row is the
whole reason the task is safe** -- it validates the instrument against nine independently ratified
readings before that instrument is used to move a figure. Report every run's pair either way.

## ROW C2 -- the `8d6e1b1` anomaly

**FIRES iff `8d6e1b1`'s recomputed event count differs from `1`, OR its scoped FP-row count exceeds
5x the median scoped FP-row count of the other eight runs.**

**Consequence if it FIRES: STOP.** Do not "fix" it, do not exclude the run, do not re-pool without
it. Report the count, the median, the ratio, and how many of its 204,220 rows survive the `cycle_utc`
scoping filter. **A pre-window numerator that moves changes the contrast for everyone, so it is the
PO's to rule on, not QA's to repair.**

## ROW C3 -- the composition claim itself

Evaluated **only if C1 and C2 both do not fire.**

Report, as counts and with no verdict attached:

| | events | slots gated | AWGN slots (parts 0,1) | events in parts 0/1 | events in parts 2/3 |
|---|---|---|---|---|---|
| Pre-window (3 runs, 08-05 → 08-21) | | 360 | 180 | | |
| Post-window (6 runs, 08-22 → 09-03) | | 480 | 360 | | |

**FIRES iff any FP event in either window attributes to part 2 or part 3.** That is the assumption
§6 rests on (52/53 all-time is a prior, not a measurement of *these* 15 events). If it fires, §6's
normalisation must be recomputed with those events kept in the numerator -- **which QA does not do;
report the counts and stop.**

🛑 **No verdict on the regression. No p-value. No ratio.** This task produces per-part counts and
the ROW C1 reproduction table. The re-derived contrast is the Architect's to compute and the PO's to
ratify -- QA supplying the arithmetic here would fuse measurement and adjudication in one step, which
is what put the original `4.88x` where it is.

## Reporting

Per HK-001. Include: every run's C1 pair (recomputed vs report.md); the C2 numbers; the C3 table if
reached; which `2e60949` directory was used; NFR-021 `scan()` on every new file **before** commit
(these CSVs are `ALL.TXT`-derived and the 8d6e1b1 file is 204k rows -- real callsigns from other
scenarios are expected in it, so **scan, and never paste raw rows into the report**).

🛑 **HARD STOP: commit locally and hand back after this task.** Do not proceed to any re-scope.
