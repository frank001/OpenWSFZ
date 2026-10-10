"""#194 captured-audio scan: the post-run step (after the gather, on that run only).

    python post_run_scan.py --run <name> --truth <truth.csv> --audio <...-captured-audio dir> \
        --results <results/<run> dir> --harness-commit <sha> [--registered a11|freeze3] [--force-start]

Rules (Architect ruling 2026-10-02 2055, section 4.3):
  * 🛑 It NEVER deletes anything of the run: it reads the captured audio and writes only `captured-audio-scan/`
    under --results (and a scratch checkout of the harness commit under D:\\Projects\\claude\\_qa-scratch\\scan-<run>\\,
    which it removes itself at the end: the Captain's rule that a job deletes its own scratch).
  * 🔴 A scan failure NEVER fails or blocks the run or the next one: every error is caught, written into
    scan_report.md, and the exit status is 0.
  * 🔴 CPU rule: it starts only when no timing run or live/overnight run is running (about 5 min of one core).
    A busy machine writes a SKIPPED report and exits 0; rerun it later. `--force-start` skips the check (QA's call).
  * Read-only on the station: no decoder, daemon, playback or ALL.TXT.
The frozen thresholds are `results/2026-09-23-5f17b43/captured-audio-scan/thresholds.json` (+ FREEZE.sha256).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
RR = HERE.parent
REPO = RR.parent.parent
FROZEN = RR / "results" / "2026-09-23-5f17b43" / "captured-audio-scan" / "thresholds.json"
SCRATCH_ROOT = Path(r"D:\Projects\claude\_qa-scratch")

# command-line fragments that mean "a timing run or a live/overnight run is going"
BUSY_MARKERS = ("run_study", "run_scenario", "resume_study", "play_session", "supervise", "endurance",
                "run_h6_probe", "corpus_replay", "OpenWSFZ.Daemon", "live_run")


def busy_reason(cmdlines: list[str], own_pid_marker: str = "post_run_scan") -> str | None:
    """First marker found in any other process's command line, or None. Pure, so it can be tested."""
    for line in cmdlines:
        if own_pid_marker in line:
            continue
        for m in BUSY_MARKERS:
            if m.lower() in line.lower():
                return m
    return None


def list_cmdlines() -> list[str]:
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | ForEach-Object { $_.CommandLine }"],
            capture_output=True, text=True, timeout=60).stdout
        return [ln for ln in out.splitlines() if ln.strip()]
    except Exception:
        return []


def write_report(results: Path, text: str) -> None:
    d = results / "captured-audio-scan"
    d.mkdir(parents=True, exist_ok=True)
    (d / "scan_report.md").write_text(text, encoding="utf-8", newline="\n")


def run_step(args: list[str], what: str) -> None:
    flags = 0x00004000 if os.name == "nt" else 0          # BELOW_NORMAL_PRIORITY_CLASS: keep the PC free
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, creationflags=flags,
                       env={**os.environ, "PYTHONUTF8": "1"})
    if r.returncode != 0:
        raise RuntimeError(f"{what} failed (exit {r.returncode}): {(r.stderr or r.stdout)[-1500:]}")


def scan(a) -> None:
    run, results = a.run, Path(a.results)
    scratch = SCRATCH_ROOT / f"scan-{run}"
    wt = scratch / "wt"
    try:
        scratch.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "worktree", "add", "--detach", str(wt), a.harness_commit], cwd=REPO,
                       check=True, capture_output=True)
        ref_dir = scratch / "ref"
        out_dir = HERE / "_out" / run
        run_step([str(HERE / "render_reference.py"), "--harness-root", str(wt / "qa" / "rr-study"),
                  "--truth", a.truth, "--out", str(ref_dir)], "reference render")
        run_step([str(HERE / "scan_run.py"), "measure", "--run", run, "--truth", a.truth, "--ref", str(ref_dir),
                  "--audio", a.audio, "--out", str(out_dir)], "measure")
        dest = results / "captured-audio-scan"
        dest.mkdir(parents=True, exist_ok=True)
        for f in ("sidecar_owsfz.csv", "sidecar_wsjtx.csv", "files.csv", "r0c.json"):
            shutil.copy2(out_dir / f, dest / f)
        run_step([str(HERE / "scan_apply.py"), "--run", run, "--sidecars", str(out_dir), "--thresholds", str(FROZEN),
                  "--audio", a.audio, "--out", str(dest), "--registered", a.registered], "apply")
    finally:
        try:
            subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=REPO, capture_output=True)
            shutil.rmtree(scratch, ignore_errors=True)       # only this job's own scratch directory
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--truth", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--harness-commit", required=True)
    ap.add_argument("--registered", choices=("a11", "freeze3"), default="a11")
    ap.add_argument("--force-start", action="store_true")
    a = ap.parse_args(argv)
    try:
        if not a.force_start:
            why = busy_reason(list_cmdlines())
            if why:
                write_report(Path(a.results), f"# Captured-audio scan: SKIPPED ({a.run})\n\nA timing or live run appears to be "
                             f"running (matched `{why}`), so the scan did not start (CPU rule). The run is unaffected. "
                             f"Rerun `post_run_scan.py` when the machine is free.\n")
                print("scan skipped: busy")
                return 0
        scan(a)
        print("scan done")
    except Exception as exc:                                  # a scan failure never fails the run
        write_report(Path(a.results), f"# Captured-audio scan: FAILED ({a.run})\n\nThe scan raised an error and wrote nothing "
                     f"else. The run itself is unaffected.\n\n```\n{type(exc).__name__}: {exc}\n{traceback.format_exc()[-1500:]}\n```\n")
        print("scan failed (reported in scan_report.md); exit 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
