#!/usr/bin/env python3
"""Resume an R&R study run from a specified scenario.

Use this script when a run was interrupted after S1 has already been played.
It plays the remaining scenarios, then collects logs, matches all scenarios
from S1 through the last resumed one, and runs the analyser.

Usage (from qa/rr-study/):
    python resume_study.py                         # resume from S2 (default)
    python resume_study.py --from-scenario S4      # resume from S4 onwards
    python resume_study.py --device "Line 1"       # custom audio device
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VENV_PYTHON = _HERE / ".venv" / "Scripts" / "python.exe"
_SCENARIOS = _HERE / "scenarios"
_RESULTS = _HERE / "results"

WSJT_ALL_TXT  = Path(r"C:\Users\Frank\AppData\Local\WSJT-X\ALL.TXT")
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

    # Derive play and match sets from the resume point.
    resume_idx = _RESUMABLE_ORDER.index(args.from_scenario)
    play_ids   = _RESUMABLE_ORDER[resume_idx:]          # from resume point to end
    match_ids  = ["S1"] + play_ids                      # S1 was already injected

    print("=" * 70, flush=True)
    print("R&R Study -- resuming", flush=True)
    print("=" * 70, flush=True)
    print(f"  Resume from  : {args.from_scenario}", flush=True)
    print(f"  Will play    : {', '.join(play_ids)}", flush=True)
    print(f"  Will match   : {', '.join(match_ids)}", flush=True)
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

    # Step 4: Match all scenarios from S1 through last resumed
    print("\nRunning matcher ...", flush=True)
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
