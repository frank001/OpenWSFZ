#!/usr/bin/env python3
"""Cross-platform R&R study runner — Windows daemon vs Linux/WSL2 daemon.

Design (D3 amendment, 2026-07-01 — ft8combined sink):
  A SINGLE synthesiser runs in WSL2 and plays to the PulseAudio ft8combined
  sink, which simultaneously delivers audio to two slaves:

    ft8loopback  → Linux daemon (captures ft8loopback.monitor via arecord)
    RDPSink      → Windows audio via WSLg → Voicemeeter AUX Input → B2
                   → Windows daemon (captures Voicemeeter Out B2)

  Both daemons receive the SAME physical audio signal (same bytes, same timing),
  making this a true shared-signal R&R with no seed-equivalence assumptions.

  Inherent DT bias: Linux DT ≈ −1 s relative to Windows due to the longer
  audio routing path through WSLg/Voicemeeter. Both are within the decoder's
  ±2 s search range. The bias is characterised in S3 results.

Pre-flight (once per WSL2 session):
    pactl load-module module-null-sink sink_name=ft8loopback \\
          sink_properties=device.description=FT8Loopback
    pactl load-module module-combine-sink sink_name=ft8combined \\
          sink_properties=device.description=FT8Combined \\
          slaves=ft8loopback,RDPSink
    pactl set-default-sink ft8combined
    pactl set-default-source ft8loopback.monitor

Both daemons must be running BEFORE this script is launched:
  Windows:  OpenWSFZ.Daemon, WASAPI capture from Voicemeeter Out B2
  WSL2:     OpenWSFZ.Daemon, arecord -D pulse (PulseAudio → ft8loopback.monitor)
            Config: audioDeviceId="pulse", decodeLog.path="/mnt/d/.../linux-all.txt"

Run from qa/rr-study/ on WINDOWS (uses .venv/Scripts/python.exe):
    python run_study_xplat.py
    python run_study_xplat.py --scenarios S1,S2,S3
    python run_study_xplat.py --scenarios S1 --parts 0,1,2
    python run_study_xplat.py --skip-warmup
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
sys.path.insert(0, str(_HERE))

from harness.common import make_run_dir  # noqa: E402 (import after sys.path)

_VENV_PYTHON   = _HERE / ".venv" / "Scripts" / "python.exe"
_SCENARIOS     = _HERE / "scenarios"
_RESULTS       = _HERE / "results"

# Windows daemon writes ALL.TXT relative to its working directory (project root)
_DEFAULT_WINDOWS_ALL_TXT = Path(r"D:\Projects\claude\OpenWSFZ\ALL.TXT")
# Linux daemon writes to this Windows-accessible path (set in daemon config)
_DEFAULT_LINUX_ALL_TXT   = Path(r"D:\Projects\claude\OpenWSFZ\linux-all.txt")

# The WSL2 scenario runner writes truth.csv to the study run_dir (via --run-dir).
# The Windows daemon receives audio passively via RDPSink/Voicemeeter — no
# Windows-side scenario runner process is needed.

# ── Timing ─────────────────────────────────────────────────────────────────
_POST_SCENARIO_SETTLE_S: int = 5

# Scenario registry — identical set to run_study.py, minus S8 (Windows-only)
_SCENARIO_REGISTRY: dict[str, Path] = {
    "S1":  _SCENARIOS / "s1-snr-ladder.json",
    "S1b": _SCENARIOS / "s1b-snr-threshold.json",
    "S2":  _SCENARIOS / "s2-freq-sweep.json",
    "S3":  _SCENARIOS / "s3-dt-offset.json",
    "S3b": _SCENARIOS / "s3b-dt-boundary.json",
    "S4":  _SCENARIOS / "s4-density.json",
    "S5":  _SCENARIOS / "s5-noise.json",
    "S7":  _SCENARIOS / "s7-compounding.json",
}

# Default run order (S1b and S3b are decode-rate companions; run after S1/S3)
_CONTROLLED_SCENARIO_IDS = ["S1", "S1b", "S2", "S3", "S4", "S5", "S7"]


# ---------------------------------------------------------------------------
# Path conversion helpers
# ---------------------------------------------------------------------------

def _win_to_wsl(p: Path) -> str:
    """Convert a Windows absolute path to its WSL2 /mnt/<drive>/... equivalent.

    Example: Path(r'D:\\foo\\bar') → '/mnt/d/foo/bar'
    """
    drive = p.drive.rstrip("\\:").lower()   # 'D:\' → 'd'
    rest  = "/".join(p.parts[1:])           # ('Projects', 'foo') → 'Projects/foo'
    return f"/mnt/{drive}/{rest}"


def _wsl_qa_root() -> str:
    """WSL2 path to the qa/rr-study directory."""
    return _win_to_wsl(_HERE)


def _wsl_python() -> str:
    """WSL2 path to the Linux venv Python interpreter."""
    return f"{_wsl_qa_root()}/.venv-linux/bin/python"


# ---------------------------------------------------------------------------
# Subprocess launchers
# ---------------------------------------------------------------------------

def _wsl_run(
    scenario_file: Path,
    linux_device: str,
    parts: str | None,
    run_dir: Path,
) -> None:
    """Run one scenario via the WSL2 synthesiser.

    Plays audio to ft8combined (ft8loopback + RDPSink), which delivers the
    SAME signal to both daemons simultaneously.  truth.csv is written to
    run_dir (Windows-accessible path).
    """
    wsl_root     = _wsl_qa_root()
    wsl_python   = _wsl_python()
    wsl_scenario = _win_to_wsl(scenario_file)
    wsl_run_dir  = _win_to_wsl(run_dir)

    cmd_parts: list[str] = [
        wsl_python,
        "harness/run_scenario.py",
        wsl_scenario,
        "--device", linux_device,
        "--run-dir", wsl_run_dir,
    ]
    if parts:
        cmd_parts += ["--parts", parts]

    def _q(s: str) -> str:
        return f'"{s}"' if (" " in s or "(" in s) else s

    bash_cmd = f"cd {wsl_root} && {' '.join(_q(p) for p in cmd_parts)}"
    wsl_cmd  = ["wsl", "-e", "bash", "-c", bash_cmd]

    print(f"\n[WSL2] >>> {bash_cmd}\n", flush=True)
    result = subprocess.run(wsl_cmd, cwd=str(_HERE))
    if result.returncode != 0:
        print(f"\n[WSL2] ERROR: scenario runner exited {result.returncode}", flush=True)
        sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--linux-device", default="pulse",
        dest="linux_device",
        help="WSL2 PulseAudio output device name (substring match). "
             "Default: 'pulse'  (matches ft8combined, the default PulseAudio sink).",
    )
    parser.add_argument(
        "--skip-warmup", action="store_true",
        help="Skip the interactive pre-flight confirmation prompt.",
    )
    parser.add_argument(
        "--scenarios", default=None, metavar="ID[,ID...]",
        help="Comma-separated scenario IDs. "
             f"Valid: {', '.join(_SCENARIO_REGISTRY)}",
    )
    parser.add_argument(
        "--parts", default=None, metavar="IDX[,IDX...]",
        help="Comma-separated part indices (0-based) within each scenario.",
    )
    parser.add_argument(
        "--windows-all-txt", default=str(_DEFAULT_WINDOWS_ALL_TXT),
        help="Path to Windows daemon ALL.TXT "
             f"(default: {_DEFAULT_WINDOWS_ALL_TXT})",
    )
    parser.add_argument(
        "--linux-all-txt", default=str(_DEFAULT_LINUX_ALL_TXT),
        help="Path to Linux daemon ALL.TXT — must be a Windows-accessible "
             "path (e.g. D:\\...\\linux-all.txt, which the WSL2 daemon "
             f"writes as /mnt/d/.../linux-all.txt). Default: {_DEFAULT_LINUX_ALL_TXT}",
    )
    args = parser.parse_args()

    win_path = Path(args.windows_all_txt)
    lin_path = Path(args.linux_all_txt)

    # ── Build scenario list ─────────────────────────────────────────────────
    if args.scenarios:
        requested     = [s.strip() for s in args.scenarios.split(",")]
        unknown       = [s for s in requested if s not in _SCENARIO_REGISTRY]
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
        scenario_files = [_SCENARIO_REGISTRY[s] for s in scenario_ids
                          if _SCENARIO_REGISTRY[s].exists()]
        scenario_ids   = [sid for sid in scenario_ids
                          if _SCENARIO_REGISTRY[sid].exists()]

    if args.parts and len(scenario_ids) > 1:
        print(
            f"  WARNING: --parts '{args.parts}' applied to every selected scenario "
            f"({', '.join(scenario_ids)}). Use with care.\n"
        )

    print("=" * 70)
    print("OpenWSFZ Cross-Platform R&R Study — Windows vs Linux/WSL2")
    print("Design D3 (ft8combined, 2026-07-01): single WSL2 synthesiser → both daemons")
    print("=" * 70)
    print(f"  Windows ALL.TXT  : {win_path}")
    print(f"  Linux ALL.TXT    : {lin_path}")
    print(f"  WSL2 device      : {args.linux_device}  (ft8combined → ft8loopback + RDPSink)")
    print(f"  Scenarios        : {', '.join(scenario_ids)}")
    if args.parts:
        print(f"  Parts filter     : {args.parts}")
    print()

    # ── Step 0: Pre-flight confirmation ─────────────────────────────────────
    if not args.skip_warmup:
        print("Pre-flight checklist:")
        print("  [ ] Windows daemon running, capturing from Voicemeeter Out B2")
        print("  [ ] Linux daemon running in WSL2 (arecord -D pulse, audioDeviceId=pulse)")
        print("  [ ] WSL2 sinks: ft8loopback, ft8combined, RDPSink all present")
        print("            pactl list sinks short")
        print("  [ ] WSL2 default sink = ft8combined, default source = ft8loopback.monitor")
        print("            pactl info | grep -E 'Default Sink:|Default Source:'")
        print("  [ ] Voicemeeter: AUX Input routed to B2")
        print("  [ ] Linux daemon config: audioDeviceId=pulse, decodeLog.path to Windows path")
        print("            (do NOT save settings via UI — see D-LINUX-001 in RUNBOOK.md §1.5)")
        print("  [ ] Both daemons on same shim version: GET /api/v1/status")
        print("  [ ] Audio chain verified: python smoke_test_null_sink.py  →  PASSED (both)")
        print()
        ans = input("All items confirmed? [Y/n]: ").strip().lower()
        if ans not in ("", "y", "yes"):
            sys.exit("Aborted. Complete the pre-flight checklist and re-run.")
        print()

    # ── Pre-create the run directory ────────────────────────────────────────
    # One directory shared across all scenarios; the Windows-side run_scenario.py
    # accumulates truth.csv rows here.  The Linux side writes to /tmp/rr-linux-scratch
    # and its truth.csv is discarded (we use only the daemon's linux-all.txt).
    run_dir = make_run_dir(_RESULTS)
    print(f"Run directory: {run_dir.relative_to(_HERE)}\n")

    # ── Step 1: Run all scenarios via WSL2 synthesiser ───────────────────────
    # A single WSL2 run_scenario.py plays audio to ft8combined, which delivers
    # the same signal to both daemons simultaneously.
    for scen_id, sf in zip(scenario_ids, scenario_files):
        if not sf.exists():
            print(f"  WARNING: scenario file not found, skipping: {sf}", flush=True)
            continue
        print(f"\n{'─' * 70}")
        print(f"  Scenario {scen_id}  →  {sf.name}")
        print(f"{'─' * 70}\n")
        _wsl_run(
            scenario_file=sf,
            linux_device=args.linux_device,
            parts=args.parts,
            run_dir=run_dir,
        )
        print(f"\n  [OK] {scen_id} complete.\n", flush=True)
        time.sleep(_POST_SCENARIO_SETTLE_S)

    # ── Step 2: Collect log files ─────────────────────────────────────────────
    print("\nCollecting decode logs ...")
    if not win_path.exists():
        sys.exit(
            f"ERROR: Windows daemon ALL.TXT not found: {win_path}\n"
            "       Confirm decodeLog.enabled = true in Windows daemon config.\n"
            "       Confirm the daemon was running throughout the scenario run."
        )
    if not lin_path.exists():
        wsl_hint = str(lin_path).replace("D:\\", "/mnt/d/").replace("\\", "/")
        sys.exit(
            f"ERROR: Linux daemon ALL.TXT not found: {lin_path}\n"
            "       Confirm decodeLog.enabled = true and decodeLog.path set to a\n"
            f"       Windows-accessible path in the Linux daemon config.\n"
            f"       WSL2 path would be: {wsl_hint}"
        )

    win_dest = run_dir / "windows-all.txt"
    lin_dest = run_dir / "linux-all.txt"
    shutil.copy2(win_path, win_dest)
    shutil.copy2(lin_path, lin_dest)
    print(f"  Copied Windows  → {win_dest.name}")
    print(f"  Copied Linux    → {lin_dest.name}")

    # ── Step 3: Run cross-platform matcher for each scenario ─────────────────
    print("\nRunning cross-platform matcher ...")
    for scen_id in scenario_ids:
        subprocess.run(
            [
                str(_VENV_PYTHON), "harness/matcher_xplat.py",
                "--run-dir",  str(run_dir),
                "--scenario", scen_id,
                "--windows",  str(win_dest),
                "--linux",    str(lin_dest),
            ],
            cwd=str(_HERE),
            check=True,
        )
        print(f"  [OK] {scen_id} matched\n", flush=True)

    # ── Step 4: Analyse ───────────────────────────────────────────────────────
    print("\nRunning cross-platform analyser ...")
    subprocess.run(
        [str(_VENV_PYTHON), "harness/analyse_xplat.py", "--run-dir", str(run_dir)],
        cwd=str(_HERE),
        check=True,
    )

    print("\n" + "=" * 70)
    print(f"Study complete.  Report: {run_dir / 'report.md'}")
    print(f"Run directory:   {run_dir}")
    print("=" * 70)
    print()
    print("Next steps (HK-001):")
    print("  1. Complete report.md §1 (study hypothesis) and §5 (recommendations)")
    print("  2. Run: python qa/rr-study/render_report.py <run_dir>/report.md")
    print("  3. Update STUDY-SPEC-XPLAT.md §13 run history table")
    print("  4. git add qa/rr-study/results/<run_dir>/ && git commit")


if __name__ == "__main__":
    main()
