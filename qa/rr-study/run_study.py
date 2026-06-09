#!/usr/bin/env python3
"""Master R&R study runner.

Runs scenarios in sequence (live playback into VB-CABLE), then collects
the WSJT-X and OpenWSFZ ALL.TXT logs, runs the matcher for every scenario,
and runs the analyser.

Run from qa/rr-study/:
    python run_study.py                          # full run (prompts for S8)
    python run_study.py --skip-s8                # full run, S8 excluded
    python run_study.py --scenarios S1,S1b       # targeted run
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

# Full registry — used for --scenarios filtering and validation.
# Insertion order defines the default run order (S8 is prepended when selected).
_SCENARIO_REGISTRY: dict[str, Path] = {
    "S1":  _SCENARIOS / "s1-snr-ladder.json",
    "S1b": _SCENARIOS / "s1b-snr-threshold.json",
    "S2":  _SCENARIOS / "s2-freq-sweep.json",
    "S3":  _SCENARIOS / "s3-dt-offset.json",
    "S4":  _SCENARIOS / "s4-density.json",
    "S5":  _SCENARIOS / "s5-noise.json",
    "S7":  _SCENARIOS / "s7-compounding.json",
    "S8":  _SCENARIOS / "s8-band-scene.json",
}

# Controlled scenarios run by default (S8 handled separately via prompt / --skip-s8)
_CONTROLLED_SCENARIO_IDS = ["S1", "S1b", "S2", "S3", "S4", "S5", "S7"]


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
    parser.add_argument("--skip-s8", action="store_true",
                        help="Skip the S8 realistic band scene (no prompt). "
                             "Ignored when --scenarios is given.")
    parser.add_argument("--scenarios", default=None,
                        metavar="ID[,ID...]",
                        help="Comma-separated list of scenario IDs to run "
                             "(e.g. S1,S1b). Bypasses the S8 prompt. "
                             f"Valid IDs: {', '.join(_SCENARIO_REGISTRY)}")
    args = parser.parse_args()

    # ── Build scenario list ────────────────────────────────────────────────
    if args.scenarios:
        requested = [s.strip() for s in args.scenarios.split(",")]
        unknown   = [s for s in requested if s not in _SCENARIO_REGISTRY]
        if unknown:
            sys.exit(
                f"ERROR: unknown scenario ID(s): {', '.join(unknown)}\n"
                f"       Valid IDs: {', '.join(_SCENARIO_REGISTRY)}"
            )
        scenario_ids   = requested
        scenario_files = [_SCENARIO_REGISTRY[s] for s in requested]
        print(f"  Targeted run: {', '.join(scenario_ids)}\n")
    else:
        scenario_ids   = list(_CONTROLLED_SCENARIO_IDS)
        scenario_files = [_SCENARIO_REGISTRY[s] for s in scenario_ids]

        if not args.skip_s8:
            ans = input("Run S8 realistic band scene first? [Y/n]: ").strip().lower()
            if ans in ("", "y", "yes"):
                scenario_files.insert(0, _SCENARIO_REGISTRY["S8"])
                scenario_ids.insert(0, "S8")
                print("  S8 included.\n")
            else:
                print("  S8 skipped.\n")

    print("=" * 70)
    print("OpenWSFZ R&R Study -- live run")
    print("=" * 70)
    print(f"  WSJT-X ALL.TXT  : {WSJT_ALL_TXT}")
    print(f"  OpenWSFZ ALL.TXT: {OWSFZ_ALL_TXT}")
    print(f"  Device          : {args.device}")
    print(f"  Scenarios       : {', '.join(scenario_ids)}")
    print()

    # ── Step 1: Run all scenarios ──────────────────────────────────────────
    for sf in scenario_files:
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
    for scen_id in scenario_ids:
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
