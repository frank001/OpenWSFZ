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

# ── Timing ─────────────────────────────────────────────────────────────────
# Pause after each scenario to let the final cycle's decodes propagate into
# ALL.TXT before the log-collection step reads it.
_POST_SCENARIO_SETTLE_S: int = 5

# ── Paths ──────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_VENV_PYTHON = _HERE / ".venv" / "Scripts" / "python.exe"
_SCENARIOS = _HERE / "scenarios"
_RESULTS = _HERE / "results"

WSJT_ALL_TXT    = Path(r"C:\Users\Frank\AppData\Local\WSJT-X - FT991A\ALL.TXT")
# 2026-08-05 (repeat of 2026-06-22-f11f438 on newest build): the Captain now runs WSJT-X
# under the multi-instance "WSJT-X - FT991A" profile (three-decoder antenna-split setup),
# not the bare default profile this constant used to point at. See
# qa/rr-study/results/2026-08-05-<sha>/ run notes.
OWSFZ_ALL_TXT   = Path(r"D:\Projects\claude\OpenWSFZ\ALL.TXT")

# Full registry — used for --scenarios filtering and validation.
# Insertion order defines the default run order (S8 is prepended when selected).
_SCENARIO_REGISTRY: dict[str, Path] = {
    "S1":  _SCENARIOS / "s1-snr-ladder.json",
    "S1b": _SCENARIOS / "s1b-snr-threshold.json",
    "S2":  _SCENARIOS / "s2-freq-sweep.json",
    "S3":  _SCENARIOS / "s3-dt-offset.json",
    # C4 (Route B, 2026-08-19): registered so a TARGETED run (--scenarios S3b) can reach
    # it. Deliberately NOT added to _CONTROLLED_SCENARIO_IDS below -- like S8, it is not
    # part of the default batch. It is an attribute (decode-rate) study, not a Gage R&R
    # (see its own "analysis": "attribute_decode_rate" and harness_note), it needs
    # --device "Voicemeeter AUX Input" explicitly (this module's --device default below is
    # still "CABLE Input", which is unreliable on this machine per HK-020/the standing
    # capture-endpoint note), and at its corrected sizing (100 trials/part, see
    # scenarios/s3b-dt-boundary.json's _sizing_note) a full run is ~4.2h unattended and
    # needs an HK-013 supervisor -- not something the default batch should trigger blind.
    "S3b": _SCENARIOS / "s3b-dt-boundary.json",
    "S4":  _SCENARIOS / "s4-density.json",
    "S5":  _SCENARIOS / "s5-noise.json",
    "S7":  _SCENARIOS / "s7-compounding.json",
    "S8":  _SCENARIOS / "s8-band-scene.json",
    # C-ASYM-A Part C (2026-08-23): High-N copy of S8 (trials 5 -> 25) so M_syn's 95%
    # half-width resolves the spec's 0.10 gate bar (HK-021(m)). Reached only via
    # --scenarios S8HN, like S3b -- deliberately NOT in _CONTROLLED_SCENARIO_IDS and does
    # NOT touch S8's own entry above or s8-band-scene.json itself.
    "S8HN": _SCENARIOS / "s8hn-band-scene-highn.json",
}

# Controlled scenarios run by default (S8 handled separately via prompt / --skip-s8)
_CONTROLLED_SCENARIO_IDS = ["S1", "S1b", "S2", "S3", "S4", "S5", "S7"]

# R&R-009 (2026-08-23): per-scenario part restriction applied ONLY to the default
# controlled battery (--scenarios bypasses this entirely -- a targeted
# `--scenarios S5` run still gets all four parts unless --parts is also given).
# S5 parts 2 (steady carrier @1500Hz) and 3 (multi-carrier "birdies") have
# detected exactly 1 false positive between them across every historical S1-S8
# run in qa/rr-study/results/ -- parts 0/1 (AWGN) account for the other 52+
# events, including the one real regression this scenario ever caught (the
# 2026-06-20 OSD FAIL, D-009). Restricting the routine battery to parts 0,1
# (60 slots, still comfortably above MIN_N_FOR_FP_GATE=49) saves ~30 min/run
# without touching the gate's statistical validity. Parts 2/3 remain available
# for an occasional targeted recheck: `--scenarios S5 --parts 2,3`.
_DEFAULT_BATTERY_PART_OVERRIDES: dict[str, str] = {
    "S5": "0,1",
}


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
    parser.add_argument("--skip-warmup", action="store_true",
                        help="Skip the pre-flight warm-up check (not recommended). "
                             "Use only when both apps are already confirmed active.")
    parser.add_argument("--scenarios", default=None,
                        metavar="ID[,ID...]",
                        help="Comma-separated list of scenario IDs to run "
                             "(e.g. S1,S1b). Bypasses the S8 prompt. "
                             f"Valid IDs: {', '.join(_SCENARIO_REGISTRY)}")
    parser.add_argument("--parts", default=None,
                        metavar="IDX[,IDX...]",
                        help="Comma-separated list of part indices (0-based) to run "
                             "within each selected scenario. Useful for targeted runs "
                             "of a single scenario (e.g. --scenarios S7 --parts 0,1,2). "
                             "Applied to every scenario when multiple are selected — use "
                             "with care. Not applicable to S8 (silently ignored).")
    args = parser.parse_args()

    # ── Build scenario list ────────────────────────────────────────────────
    scenario_part_overrides: dict[str, str] = {}
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
        scenario_part_overrides = dict(_DEFAULT_BATTERY_PART_OVERRIDES)

        if not args.skip_s8:
            ans = input("Run S8 realistic band scene first? [Y/n]: ").strip().lower()
            if ans in ("", "y", "yes"):
                scenario_files.insert(0, _SCENARIO_REGISTRY["S8"])
                scenario_ids.insert(0, "S8")
                print("  S8 included.\n")
            else:
                print("  S8 skipped.\n")

    # Warn when --parts is combined with multiple scenarios — it is applied to
    # all of them, which is rarely the intent.
    if args.parts and len(scenario_ids) > 1:
        print(
            f"  WARNING: --parts '{args.parts}' will be applied to every selected "
            f"scenario ({', '.join(scenario_ids)}).  Part indices must be valid for "
            f"all of them, or you will get an error mid-run.  "
            f"Prefer --scenarios <single-id> --parts <indices> for targeted work.\n"
        )

    print("=" * 70)
    print("OpenWSFZ R&R Study -- live run")
    print("=" * 70)
    print(f"  WSJT-X ALL.TXT  : {WSJT_ALL_TXT}")
    print(f"  OpenWSFZ ALL.TXT: {OWSFZ_ALL_TXT}")
    print(f"  Device          : {args.device}")
    print(f"  Scenarios       : {', '.join(scenario_ids)}")
    if args.parts:
        print(f"  Parts filter    : {args.parts}")
    elif scenario_part_overrides:
        for sid, parts in scenario_part_overrides.items():
            if sid in scenario_ids:
                print(f"  Parts filter    : {sid} restricted to parts {parts} "
                      f"(R&R-009 default-battery override; see run_study.py)")
    print()

    # ── Step 0: Pre-flight warm-up check ──────────────────────────────────
    # Play one FT8 cycle at +6 dB SNR and ask the operator to confirm both
    # WSJT-X and OpenWSFZ decoded it.  This catches routing failures before
    # any study data is recorded.  The cycle is NOT written to truth.csv.
    if args.skip_warmup:
        print("  WARNING: pre-flight warm-up check skipped (--skip-warmup).")
        print("  Ensure both apps are in Monitor/decode mode before proceeding.")
        print()
    else:
        _py("harness/warmup.py", "--device", args.device)

    # ── Step 1: Run all scenarios ──────────────────────────────────────────
    for sid, sf in zip(scenario_ids, scenario_files):
        if not sf.exists():
            sys.exit(f"ERROR: scenario file not found: {sf}")
        run_args = ["harness/run_scenario.py", str(sf), "--device", args.device]
        parts_for_this = args.parts or scenario_part_overrides.get(sid)
        if parts_for_this:
            run_args += ["--parts", parts_for_this]
        _py(*run_args)
        print(f"  [OK] {sf.name} complete\n", flush=True)
        time.sleep(_POST_SCENARIO_SETTLE_S)

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
