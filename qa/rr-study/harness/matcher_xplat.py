"""Cross-platform decode log matcher for the OpenWSFZ R&R study.

Usage:
    python harness/matcher_xplat.py --run-dir <dir> --scenario <id>
    python harness/matcher_xplat.py --truth t.csv --windows win.txt --linux lin.txt

Like harness/matcher.py but uses "Windows" and "Linux" as appraiser names
and looks for windows-all.txt / linux-all.txt in the run directory.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Resolve qa/rr-study as package root
_QA_ROOT = Path(__file__).resolve().parent.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))

from harness.common import parse_all_txt

# ---------------------------------------------------------------------------
# Widen frequency tolerance for cross-platform matching
#
# The base matcher uses FREQ_TOLERANCE_HZ = 4.0 Hz, appropriate for same-
# platform studies.  The Linux/WSL2 audio path introduces a systematic
# frequency offset of ~16 Hz at 1500 Hz (attributed to PulseAudio sample-rate
# handling in the ft8combined combine-sink).  Without a wider tolerance, Linux
# decodes at ~1484 Hz would never match truth at 1500 Hz, producing 0%
# recovery for any single-frequency scenario.
#
# 20 Hz covers the observed offset (~16 Hz) with a 4 Hz margin.  The actual
# frequency bias is still measured and reported by analyse_xplat.py via the
# platform-bias gate; widening the match tolerance does not suppress that
# measurement.
#
# Must be set BEFORE importing from harness.matcher — _freq_matches() looks
# up FREQ_TOLERANCE_HZ in the harness.matcher module globals at call time.
# ---------------------------------------------------------------------------
import harness.matcher as _matcher_module
XPLAT_FREQ_TOLERANCE_HZ = 20.0
_matcher_module.FREQ_TOLERANCE_HZ = XPLAT_FREQ_TOLERANCE_HZ

# Import matching/output helpers from matcher.py (appraiser-name-agnostic)
from harness.matcher import (
    _load_truth,
    _match_appraiser,
    _write_matched,
    _print_summary,
)

# ---------------------------------------------------------------------------
# Appraisers for this study
# ---------------------------------------------------------------------------

APPRAISERS = ("Windows", "Linux")


# ---------------------------------------------------------------------------
# Path resolution (replaces matcher._resolve_paths)
# ---------------------------------------------------------------------------

def _resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    """Return (truth_path, windows_path, linux_path), resolving from --run-dir."""
    if args.run_dir:
        run_dir = Path(args.run_dir)
        truth_path = run_dir / "truth.csv"
        windows_path = run_dir / "windows-all.txt"
        linux_path = run_dir / "linux-all.txt"
    else:
        truth_path = Path(args.truth) if args.truth else None
        windows_path = Path(args.windows) if args.windows else None
        linux_path = Path(args.linux) if args.linux else None

    # Explicit overrides take precedence
    if args.windows:
        windows_path = Path(args.windows)
    if args.linux:
        linux_path = Path(args.linux)
    if args.truth:
        truth_path = Path(args.truth)

    if not truth_path or not truth_path.exists():
        sys.exit(f"ERROR: truth.csv not found: {truth_path}")
    if not windows_path or not windows_path.exists():
        sys.exit(f"ERROR: Windows ALL.TXT not found: {windows_path}")
    if not linux_path or not linux_path.exists():
        sys.exit(f"ERROR: Linux ALL.TXT not found: {linux_path}")

    return truth_path, windows_path, linux_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cross-platform R&R decode matcher (Windows vs Linux)"
    )
    parser.add_argument("--run-dir", help="Run directory (resolves default paths)")
    parser.add_argument("--scenario", help="Scenario ID to filter (e.g. S1)")
    parser.add_argument("--truth", help="Explicit path to truth.csv")
    parser.add_argument("--windows", help="Explicit path to Windows daemon ALL.TXT")
    parser.add_argument("--linux", help="Explicit path to Linux daemon ALL.TXT")
    args = parser.parse_args()

    if not args.run_dir and not (args.truth and args.windows and args.linux):
        parser.error("Provide --run-dir OR all of --truth, --windows, --linux")

    truth_path, windows_path, linux_path = _resolve_paths(args)

    scenario_filter = args.scenario
    truth_rows = _load_truth(truth_path, scenario_filter)
    if not truth_rows:
        sys.exit(
            "ERROR: no truth rows found"
            + (f" for scenario '{scenario_filter}'" if scenario_filter else "")
        )

    scenario_id = scenario_filter or truth_rows[0]["scenario_id"]
    print(f"Matching scenario {scenario_id} — {len(truth_rows)} truth rows")

    run_dir = Path(args.run_dir) if args.run_dir else truth_path.parent

    # Parse ALL.TXT files
    win_records, win_skipped = parse_all_txt(windows_path)
    lin_records, lin_skipped = parse_all_txt(linux_path)
    print(f"  Windows:  {len(win_records)} FT8 lines parsed, {win_skipped} skipped")
    print(f"  Linux:    {len(lin_records)} FT8 lines parsed, {lin_skipped} skipped")

    # Match each appraiser
    win_rows = _match_appraiser(truth_rows, win_records, "Windows", scenario_id)
    lin_rows = _match_appraiser(truth_rows, lin_records, "Linux", scenario_id)
    all_rows = win_rows + lin_rows

    out_path = _write_matched(run_dir, scenario_id, all_rows)
    print(f"  Written: {out_path}")

    print("\nMatch summary:")
    _print_summary("Windows", win_rows, win_skipped)
    _print_summary("Linux", lin_rows, lin_skipped)


if __name__ == "__main__":
    main()
