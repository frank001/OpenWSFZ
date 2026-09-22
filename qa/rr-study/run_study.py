#!/usr/bin/env python3
"""Master R&R study runner.

Runs scenarios in sequence (live playback into VB-CABLE), then collects
the WSJT-X and OpenWSFZ ALL.TXT logs and runs the matcher for every scenario.

Analysis (harness/analyse.py -- the ANOVA-style stats/verdict computation and report.md
generation) is a SEPARATE step, printed at the end, not run automatically (Captain's
standardisation instruction, 2026-09-22: "any analysis shall be separate from the
run-script" -- same principle already applied to the endurance side).

Application settings (audio device, Monitor/decode state, logging) are the operator's own
setup, done BEFORE running this script -- see qa/rr-study/RUNBOOK.md section 2 for the
current, authoritative settings table; this script does not duplicate or enforce it.

Run from qa/rr-study/:
    python run_study.py                          # full run (prompts for S8)
    python run_study.py --skip-s8                # full run, S8 excluded
    python run_study.py --scenarios S1,S1b       # targeted run
    python run_study.py --wsjt-all-txt <path> --owsfz-all-txt <path>   # non-default ALL.TXT locations
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Resolve qa/rr-study as a package root so ``harness`` is importable, same
# convention as harness/run_scenario.py.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from harness.common import make_run_dir  # noqa: E402

# ── Timing ─────────────────────────────────────────────────────────────────
# Pause after each scenario to let the final cycle's decodes propagate into
# ALL.TXT before the log-collection step reads it.
_POST_SCENARIO_SETTLE_S: int = 5

# ── Paths ──────────────────────────────────────────────────────────────────
_VENV_PYTHON = _HERE / ".venv" / "Scripts" / "python.exe"
_SCENARIOS = _HERE / "scenarios"
_RESULTS = _HERE / "results"

# Defaults only -- both are overridable via --wsjt-all-txt/--owsfz-all-txt (Captain's
# standardisation instruction, 2026-09-22, same principle applied to the endurance side first:
# "configured before the run", not hardcoded in the script). The values below are this
# project's current standard setup and stay as the default so no existing invocation changes
# behaviour; see qa/rr-study/RUNBOOK.md section 2 for the current, authoritative app settings this
# script does not itself duplicate or enforce.
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

# R&R-009 (2026-08-23) restricted S5's routine battery to parts 0,1, reasoning
# that parts 2 (steady carrier @1500Hz) and 3 (multi-carrier "birdies") had
# detected only 1 false positive between them across history versus 52+ from
# parts 0/1 (AWGN). SUPERSEDED 2026-09-06 (S5-GATE-SIZING spec, Amendment 1,
# PO ruling Option 3): that restriction silently halved the ratified AWGN
# gate's own N (120->60, STUDY-SPEC.md Section 16) and removed the routine
# battery's only coverage of the narrowband-hallucination failure mode on an
# HK-026 argument (a zero-event history cannot bound its own future
# usefulness). Parts 2/3 are restored to the default battery -- their trial
# count now comes from scenarios/s5-noise.json itself (parts 0/1 carry a
# per-part "trials": 60 override; parts 2/3 use the file's default of 30),
# and harness/analyse.py scores the two populations as separate, never-pooled
# verdict rows (Gate A / Check B). This dict is left in place, empty, as the
# mechanism for any FUTURE default-battery part restriction -- do not repopulate
# it for S5 without a new spec revisiting the population question the way this
# one did.
_DEFAULT_BATTERY_PART_OVERRIDES: dict[str, str] = {}


def _py(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command via the venv Python, streaming output in real time."""
    cmd = [str(_VENV_PYTHON), *args]
    print(f"\n>>> {' '.join(cmd)}\n", flush=True)
    result = subprocess.run(cmd, cwd=str(_HERE), check=check)
    return result


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
    parser.add_argument("--wsjt-all-txt", default=str(WSJT_ALL_TXT), metavar="PATH",
                        help=f"Path to WSJT-X's ALL.TXT. Default: {WSJT_ALL_TXT} "
                             "(this project's current standard profile; override if yours "
                             "differs -- see RUNBOOK.md section 2).")
    parser.add_argument("--owsfz-all-txt", default=str(OWSFZ_ALL_TXT), metavar="PATH",
                        help=f"Path to OpenWSFZ's ALL.TXT. Default: {OWSFZ_ALL_TXT}.")
    args = parser.parse_args()
    wsjt_all_txt = Path(args.wsjt_all_txt)
    owsfz_all_txt = Path(args.owsfz_all_txt)

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

    # Pin the run directory ONCE, before any scenario runs, and pass it
    # explicitly to every harness/run_scenario.py invocation below (Item 1,
    # 2026-08-27 Architect work order). run_scenario.py otherwise resolves
    # its own output directory fresh from the *live* git HEAD SHA on every
    # invocation -- a commit landing mid-battery (however unrelated to src/)
    # silently splits the run's truth data across two directories and
    # crashes the matcher on whichever scenario falls on the wrong side of
    # the split. This bit a real run on 2026-08-27; see that run's report.md
    # Section 1 and qa/rr-study/2026-08-27-2141-architect-to-qa-outstanding-
    # work-order.md Item 1.
    run_dir = make_run_dir(_RESULTS)

    print("=" * 70)
    print("OpenWSFZ R&R Study -- live run")
    print("=" * 70)
    print(f"  WSJT-X ALL.TXT  : {wsjt_all_txt}")
    print(f"  OpenWSFZ ALL.TXT: {owsfz_all_txt}")
    print(f"  Device          : {args.device}")
    print(f"  Scenarios       : {', '.join(scenario_ids)}")
    print(f"  Run directory   : {run_dir.relative_to(_HERE)}  (pinned for the whole battery)")
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
        run_args = [
            "harness/run_scenario.py", str(sf),
            "--device", args.device,
            "--run-dir", str(run_dir),
        ]
        parts_for_this = args.parts or scenario_part_overrides.get(sid)
        if parts_for_this:
            run_args += ["--parts", parts_for_this]
        _py(*run_args)
        print(f"  [OK] {sf.name} complete\n", flush=True)
        time.sleep(_POST_SCENARIO_SETTLE_S)

    print(f"\nRun directory: {run_dir.relative_to(_HERE)}")

    # ── Step 3: Collect log files ──────────────────────────────────────────
    print("\nCollecting decode logs ...")
    if not wsjt_all_txt.exists():
        sys.exit(
            f"ERROR: WSJT-X ALL.TXT not found at {wsjt_all_txt}\n"
            "       Was Monitor ON and did WSJT-X decode anything?"
        )
    if not owsfz_all_txt.exists():
        sys.exit(
            f"ERROR: OpenWSFZ ALL.TXT not found at {owsfz_all_txt}\n"
            "       Is decodeLog.enabled = true in config?"
        )

    wsjt_dest  = run_dir / "wsjt-all.txt"
    owsfz_dest = run_dir / "owsfz-all.txt"
    shutil.copy2(wsjt_all_txt,  wsjt_dest)
    shutil.copy2(owsfz_all_txt, owsfz_dest)
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

    # Analysis is a SEPARATE step (Captain's standardisation instruction, 2026-09-22, same
    # principle already applied to the endurance side: "any analysis shall be separate from
    # the run-script"). matcher.py above stays here -- it builds each scenario's own
    # matched.csv, which is data preparation for THIS run, the same role the endurance
    # gatherer plays -- but harness/analyse.py (the ANOVA-style stats/verdict computation and
    # report.md generation) does not run automatically any more.
    print("\n" + "=" * 70)
    print("Study data collection complete (scenarios run, logs collected, matched).")
    print(f"Run directory: {run_dir}")
    print()
    print("Analysis is a separate step -- run it explicitly:")
    print(f"    python harness/analyse.py --run-dir {run_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
