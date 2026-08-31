#!/usr/bin/env python3
"""Resume an R&R study run from a specified scenario.

Use this script when a run was interrupted after S1 has already been played.
It plays the remaining scenarios, then collects logs, matches every scenario
already present in the run directory's truth.csv (whatever combination of
S8/S1/S1b/S2/... completed before the interruption, plus whatever this
invocation replays), and runs the analyser.

Usage (from qa/rr-study/):
    python resume_study.py                         # resume from S2 (default)
    python resume_study.py --from-scenario S4      # resume from S4 onwards
    python resume_study.py --device "Line 1"       # custom audio device
"""
from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VENV_PYTHON = _HERE / ".venv" / "Scripts" / "python.exe"
_SCENARIOS = _HERE / "scenarios"
_RESULTS = _HERE / "results"

WSJT_ALL_TXT  = Path(r"C:\Users\Frank\AppData\Local\WSJT-X - FT991A\ALL.TXT")
OWSFZ_ALL_TXT = Path(r"D:\Projects\claude\OpenWSFZ\ALL.TXT")

# Full controlled order, excluding S1 (already played before a resume) and S8
# (opted-in separately via run_study.py).  Insertion order is the play order.
_RESUMABLE_ORDER = ["S2", "S3", "S4", "S5", "S7"]

_SCENARIO_FILES = {
    "S2": _SCENARIOS / "s2-freq-sweep.json",
    "S3": _SCENARIOS / "s3-dt-offset.json",
    "S4": _SCENARIOS / "s4-density.json",
    "S5": _SCENARIOS / "s5-noise.json",
    "S7": _SCENARIOS / "s7-compounding.json",
}


def run(*args: str, device: str) -> None:
    cmd = [str(_VENV_PYTHON)] + list(args) + ["--device", device]
    print(f"\n>>> {' '.join(cmd)}\n", flush=True)
    subprocess.run(cmd, cwd=str(_HERE), check=True)


def find_run_dir() -> Path:
    dirs = sorted(
        (d for d in _RESULTS.iterdir() if d.is_dir()),
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    if not dirs:
        sys.exit("ERROR: no run directory found.")
    return dirs[0]


# Print/match order only -- matcher.py does not care what order it's called
# in. Anything present in truth.csv but not listed here sorts after, so an
# unrecognised future scenario ID still gets matched, just last.
_CANONICAL_SCENARIO_ORDER = ["S8", "S1", "S1b", "S2", "S3", "S4", "S5", "S7"]


def _scenario_ids_in_truth(run_dir: Path) -> list[str]:
    """Read truth.csv back and return the distinct scenario_id values it
    actually holds, canonically ordered. This is the ground truth for what
    needs matching -- not an assumption about which scenarios preceded a
    resume point, which varies run to run (S8 opt-in, S1b, and how far a
    prior interruption got before it happened)."""
    truth_path = run_dir / "truth.csv"
    if not truth_path.exists():
        sys.exit(f"ERROR: no truth.csv in {run_dir}")
    with open(truth_path, newline="", encoding="utf-8") as fh:
        ids = {row["scenario_id"] for row in csv.DictReader(fh)}
    if not ids:
        sys.exit(f"ERROR: truth.csv in {run_dir} has no rows")
    ordered = [s for s in _CANONICAL_SCENARIO_ORDER if s in ids]
    ordered += sorted(ids - set(ordered))
    return ordered


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--device", default="CABLE Input",
        help="Audio output device name substring (default: 'CABLE Input')",
    )
    parser.add_argument(
        "--from-scenario",
        default="S2",
        choices=_RESUMABLE_ORDER,
        metavar="ID",
        help=(
            "First scenario that has NOT yet been played — the resume point. "
            f"Valid values: {', '.join(_RESUMABLE_ORDER)}. Default: S2"
        ),
    )
    args = parser.parse_args()

    # Derive the play set from the resume point. The match set is NOT
    # derived here -- see the comment above Step 4 below. A resume can
    # follow a partial run that already carries S1b and/or S8 (opted in
    # separately via run_study.py, or already complete before the
    # interruption, as with S2 here on 2026-08-30); those must also be
    # matched, and hardcoding "S1 + play_ids" (the original logic) silently
    # drops them from the report every time the resume point isn't S2.
    resume_idx = _RESUMABLE_ORDER.index(args.from_scenario)
    play_ids   = _RESUMABLE_ORDER[resume_idx:]          # from resume point to end

    print("=" * 70, flush=True)
    print("R&R Study -- resuming", flush=True)
    print("=" * 70, flush=True)
    print(f"  Resume from  : {args.from_scenario}", flush=True)
    print(f"  Will play    : {', '.join(play_ids)}", flush=True)
    print(f"  Device       : {args.device}", flush=True)
    print()

    # Step 1: Play remaining scenarios
    for scen_id in play_ids:
        sf = _SCENARIO_FILES[scen_id]
        run("harness/run_scenario.py", str(sf), device=args.device)
        print(f"[OK] {sf.name} complete", flush=True)
        time.sleep(5)

    # Step 2: Locate run directory
    run_dir = find_run_dir()
    print(f"\nRun directory: {run_dir.relative_to(_HERE)}", flush=True)

    # Step 3: Collect logs
    print("\nCollecting decode logs ...", flush=True)
    if not WSJT_ALL_TXT.exists():
        sys.exit(f"ERROR: WSJT-X ALL.TXT not found at {WSJT_ALL_TXT}")
    if not OWSFZ_ALL_TXT.exists():
        sys.exit(f"ERROR: OpenWSFZ ALL.TXT not found at {OWSFZ_ALL_TXT}")

    wsjt_dest  = run_dir / "wsjt-all.txt"
    owsfz_dest = run_dir / "owsfz-all.txt"
    shutil.copy2(WSJT_ALL_TXT,  wsjt_dest)
    shutil.copy2(OWSFZ_ALL_TXT, owsfz_dest)
    print(f"  Copied WSJT-X   -> {wsjt_dest.name}", flush=True)
    print(f"  Copied OpenWSFZ -> {owsfz_dest.name}", flush=True)

    ver_path = run_dir / "wsjt-version.txt"
    ver_path.write_text(
        "WSJT-X 2.7.0 (inferred from binary date 2025-02-04)", encoding="utf-8"
    )

    # Step 4: Match every scenario actually present in this run directory's
    # truth.csv -- read back off disk rather than assumed, so a run that
    # entered the interruption mid-battery (any subset of S8/S1/S1b/S2
    # already complete, not just "S1") still gets every one of its legs
    # matched, not just S1 plus whatever this invocation replayed.
    print("\nRunning matcher ...", flush=True)
    match_ids = _scenario_ids_in_truth(run_dir)
    print(f"  Scenarios present in truth.csv: {', '.join(match_ids)}", flush=True)
    for scen_id in match_ids:
        subprocess.run(
            [
                str(_VENV_PYTHON),
                "harness/matcher.py",
                "--run-dir", str(run_dir),
                "--scenario", scen_id,
                "--wsjt",  str(wsjt_dest),
                "--owsfz", str(owsfz_dest),
            ],
            cwd=str(_HERE),
            check=True,
        )
        print(f"[OK] {scen_id} matched", flush=True)

    # Step 5: Analyse
    print("\nRunning analyser ...", flush=True)
    subprocess.run(
        [str(_VENV_PYTHON), "harness/analyse.py", "--run-dir", str(run_dir)],
        cwd=str(_HERE),
        check=True,
    )

    print("\n" + "=" * 70, flush=True)
    print(f"Study complete.  Report: {run_dir / 'report.md'}", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    main()
