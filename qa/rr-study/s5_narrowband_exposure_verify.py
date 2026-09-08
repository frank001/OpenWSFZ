#!/usr/bin/env python3
"""s5_narrowband_exposure_verify.py -- A1.2 ROW 0 precondition (2026-09-06).

Architect's `arch/s5-gate-sizing` Amendment 1 derives Check B's threshold
(T=2) from a base rate stated as "1 of 53 all-time FP events" for S5 parts
2/3 (narrowband: steady carrier + multi-carrier birdies). That is an EVENT
SHARE, not a rate per narrowband slot -- its denominator (how many parts-2/3
slots have ever actually been run) was not computed, and the Architect's
commit states this as an explicit ROW 0 stop: T=2 is not final until QA
verifies the exposure count, and T must be re-derived if the measured
per-slot rate exceeds ~1%.

Method, mirroring fp_composition_per_part.py's join (STUDY-SPEC.md
Section 16) but extended to EVERY committed qa/rr-study/results/* directory,
not just the nine named in FP-COMPOSITION:

  1. For each results/<run>/truth.csv, take rows with scenario_id == "S5".
     This gives cycle_utc -> part_index for that run's S5 slots.
  2. For each results/<run>/S5_matched.csv (appraiser == "OpenWSFZ"), take
     false_positive == True rows scoped to that run's S5 cycle_utc set.
  3. Collapse decode rows to per-slot events (Section 10's unit is
     "slot emits >= 1 decode", not "decode row").
  4. Sum slots and events separately for part_index in {2, 3} across every
     run that ever included them.

Data-recovery note: 11 of 16 historical runs that included parts 2/3 do not
have S5_matched.csv committed (NFR-021 -- raw appraiser decode logs are
gitignored: qa/rr-study/results/*/*_matched.csv). Those files exist only as
local, gitignored artefacts and did not travel when this worktree was split
from the Architect's on 2026-09-06 (a known gap, see the memory dir's
operational-note-persona-worktrees-2026-09-06.md). They were recovered by a
Captain-approved local filesystem copy from the Architect's worktree
(D:\\Projects\\claude\\OpenWSFZ) for the 11 runs not already committed;
already-committed (redaction-mapped) matched.csv files were never touched.
No git operation is involved and nothing here is staged -- these files match
the existing gitignore pattern in every run directory.

ROW C1 (reproduction gate): recomputed (events, n_slots) for the nine
FP-COMPOSITION runs must equal fp_composition_per_part.py's REPORTED_GATE,
transcribed from each run's own committed report.md. This is the same
predicate as fp_composition_per_part.py's ROW C1 -- reproduced here rather
than imported, so this script has no hidden dependency on that file's own
correctness.

Usage:
  python qa/rr-study/s5_narrowband_exposure_verify.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "qa" / "rr-study" / "results"

# Transcribed verbatim from fp_composition_per_part.py -- the nine runs named
# in the 2026-09-04 FP-COMPOSITION spec, OpenWSFZ (events, n_slots) per that
# run's own committed report.md gate line.
REPORTED_GATE_OPENWSFZ = {
    "2026-08-05-3bd4cd0": (0, 120),
    "2026-08-15-8d6e1b1": (1, 120),
    "2026-08-21-7d36038": (1, 120),
    "2026-08-22-f5dec23": (4, 120),
    "2026-08-27-22b749c": (0, 60),
    "2026-08-29-872ba65": (1, 60),
    "2026-08-30-2e60949": (2, 120),
    "2026-09-02-3b52608": (4, 60),
    "2026-09-03-35378b9": (2, 60),
}

NARROWBAND_PARTS = {"2", "3"}


def is_true(val: str) -> bool:
    return val.strip().lower() in ("true", "1")


def load_s5_part_map(run_dir: Path) -> dict[str, str]:
    part_map: dict[str, str] = {}
    truth = run_dir / "truth.csv"
    if not truth.exists():
        return part_map
    with truth.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "scenario_id" not in reader.fieldnames:
            return part_map
        for row in reader:
            if row["scenario_id"] != "S5":
                continue
            part_map[row["cycle_utc"]] = row["part_index"]
    return part_map


def scoped_fp_events_by_part(run_dir: Path, part_map: dict[str, str]) -> dict[str, int]:
    """events_by_part for appraiser == OpenWSFZ, scoped to this run's S5 slots."""
    matched = run_dir / "S5_matched.csv"
    events_by_part: dict[str, int] = {}
    if not matched.exists() or not part_map:
        return events_by_part
    seen_slots: set[str] = set()
    with matched.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        if not {"appraiser", "false_positive", "cycle_utc"} <= set(fields):
            return events_by_part
        for row in reader:
            if row["appraiser"] != "OpenWSFZ":
                continue
            if not is_true(row["false_positive"]):
                continue
            cyc = row["cycle_utc"]
            if cyc not in part_map or cyc in seen_slots:
                continue
            seen_slots.add(cyc)
            events_by_part[part_map[cyc]] = events_by_part.get(part_map[cyc], 0) + 1
    return events_by_part


def main() -> int:
    dirs = sorted(p for p in RESULTS.iterdir() if p.is_dir())

    # ---- ROW C1: reproduction gate against the nine known-good runs ----
    print("=== ROW C1 -- reproduction gate (fp_composition_per_part.py's REPORTED_GATE) ===")
    c1_fires = False
    for name, expected in REPORTED_GATE_OPENWSFZ.items():
        run_dir = RESULTS / name
        part_map = load_s5_part_map(run_dir)
        events_by_part = scoped_fp_events_by_part(run_dir, part_map)
        recomputed = (sum(events_by_part.values()), len(part_map))
        ok = recomputed == expected
        if not ok:
            c1_fires = True
        print(f"  {name:24s} recomputed={recomputed} reported={expected} "
              f"{'OK' if ok else '*** MISMATCH ***'}")
    print(f"ROW C1: {'FIRES -- STOP' if c1_fires else 'does not fire'}")
    if c1_fires:
        print("Per spec convention: STOP. Nothing downstream may be cited.")
        return 1

    # ---- Full-history narrowband (parts 2/3) exposure ----
    print()
    print("=== Full-history S5 parts 2/3 exposure, every committed results/ dir ===")
    total_slots_23 = 0
    total_events_23 = 0
    runs_with_23 = []
    for d in dirs:
        part_map = load_s5_part_map(d)
        n23 = sum(1 for p in part_map.values() if p in NARROWBAND_PARTS)
        if n23 == 0:
            continue
        events_by_part = scoped_fp_events_by_part(d, part_map)
        e23 = sum(c for p, c in events_by_part.items() if p in NARROWBAND_PARTS)
        total_slots_23 += n23
        total_events_23 += e23
        runs_with_23.append(d.name)
        print(f"  {d.name:40s} slots_2/3={n23:3d} events_2/3={e23}")

    print()
    print(f"Runs that ever ran parts 2/3: {len(runs_with_23)}")
    print(f"TOTAL parts 2/3: slots={total_slots_23} events={total_events_23}")
    rate = total_events_23 / total_slots_23 if total_slots_23 else float("nan")
    print(f"Per-slot narrowband base rate = {total_events_23}/{total_slots_23} = {100*rate:.4f}%")
    print()
    print("A1.2's ROW 0 trigger: re-derive T if the measured per-slot rate exceeds ~1%.")
    if rate > 0.01:
        print(f"*** TRIGGERED: {100*rate:.4f}% > 1% -- T=2 must be re-derived from A1.2's table. ***")
        return 2
    print(f"NOT triggered: {100*rate:.4f}% <= 1% -- T=2 stands as derived.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
