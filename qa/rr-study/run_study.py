#!/usr/bin/env python3
"""Master R&R study runner.

Runs all five scenarios in sequence (live playback into VB-CABLE), then
collects the WSJT-X and OpenWSFZ ALL.TXT logs, runs the matcher for every
scenario, and runs the analyser.

Run from qa/rr-study/:
    python run_study.py [--device "CABLE Input"]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_VENV_PYTHON = _HERE / ".venv" / "Scripts" / "python.exe"
_SCENARIOS = _HERE / "scenarios"
_RESULTS = _HERE / "results"

WSJT_ALL_TXT    = Path(r"C:\Users\Frank\AppData\Local\WSJT-X\ALL.TXT")
OWSFZ_ALL_TXT   = Path(r"D:\Projects\claude\OpenWSFZ\ALL.TXT")

# Scenario JSON files in play order
SCENARIO_FILES = [
    _SCENARIOS / "s1-snr-ladder.json",
    _SCENARIOS / "s2-freq-sweep.json",
    _SCENARIOS / "s3-dt-offset.json",
    _SCENARIOS / "s4-density.json",
    _SCENARIOS / "s5-noise.json",
    _SCENARIOS / "s7-compounding.json",
]

# Scenario IDs in the same order (for matcher invocation)
SCENARIO_IDS = ["S1", "S2", "S3", "S4", "S5", "S7"]


def _py(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command via the venv Python, streaming output in real time."""
    cmd = [str(_VENV_PYTHON), *args]
    print(f"\n>>> {' '.join(cmd)}\n", flush=True)
    result = subprocess.run(cmd, cwd=str(_HERE), check=check)
    return result


def _find_run_dir() -> Path:
    """Return the most-recently-modified run directory in results/."""
    dirs = sorted(
        (d for d in _RESULTS.iterdir() if d.is_dir()),
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    if not dirs:
        sys.exit("ERROR: no run directory found after scenario run.")
    return dirs[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="CABLE Input",
                        help="Audio output device name substring")
    args = parser.parse_args()

    print("=" * 70)
    print("OpenWSFZ R&R Study -- live run")
    print("=" * 70)
    print(f"  WSJT-X ALL.TXT  : {WSJT_ALL_TXT}")
    print(f"  OpenWSFZ ALL.TXT: {OWSFZ_ALL_TXT}")
    print(f"  Device          : {args.device}")
    print()

    # ── Step 1: Run all scenarios ──────────────────────────────────────────
    for sf in SCENARIO_FILES:
        if not sf.exists():
            sys.exit(f"ERROR: scenario file not found: {sf}")
        _py("harness/run_scenario.py", str(sf), "--device", args.device)
        print(f"  [OK] {sf.name} complete\n", flush=True)
        # Small pause to let the last cycle's decodes propagate into ALL.TXT
        time.sleep(5)

    # ── Step 2: Locate run directory ───────────────────────────────────────
    run_dir = _find_run_dir()
    print(f"\nRun directory: {run_dir.relative_to(_HERE)}")

    # ── Step 3: Collect log files ──────────────────────────────────────────
    print("\nCollecting decode logs ...")
    if not WSJT_ALL_TXT.exists():
        sys.exit(
            f"ERROR: WSJT-X ALL.TXT not found at {WSJT_ALL_TXT}\n"
            "       Was Monitor ON and did WSJT-X decode anything?"
        )
    if not OWSFZ_ALL_TXT.exists():
        sys.exit(
            f"ERROR: OpenWSFZ ALL.TXT not found at {OWSFZ_ALL_TXT}\n"
            "       Is decodeLog.enabled = true in config?"
        )

    wsjt_dest  = run_dir / "wsjt-all.txt"
    owsfz_dest = run_dir / "owsfz-all.txt"
    shutil.copy2(WSJT_ALL_TXT,  wsjt_dest)
    shutil.copy2(OWSFZ_ALL_TXT, owsfz_dest)
    print(f"  Copied WSJT-X   -> {wsjt_dest.name}")
    print(f"  Copied OpenWSFZ -> {owsfz_dest.name}")

    # Record WSJT-X version
    ver_path = run_dir / "wsjt-version.txt"
    ver_path.write_text("WSJT-X 2.7.0 (inferred from binary date 2025-02-04)", encoding="utf-8")

    # ── Step 4: Run matcher for each scenario ──────────────────────────────
    print("\nRunning matcher ...")
    for scen_id in SCENARIO_IDS:
        _py(
            "harness/matcher.py",
            "--run-dir", str(run_dir),
            "--scenario", scen_id,
            "--wsjt",  str(wsjt_dest),
            "--owsfz", str(owsfz_dest),
        )
        print(f"  [OK] {scen_id} matched\n", flush=True)

    # ── Step 5: Analyse ────────────────────────────────────────────────────
    print("\nRunning analyser ...")
    _py("harness/analyse.py", "--run-dir", str(run_dir))

    print("\n" + "=" * 70)
    print(f"Study complete.  Report: {run_dir / 'report.md'}")
    print("=" * 70)


if __name__ == "__main__":
    main()
