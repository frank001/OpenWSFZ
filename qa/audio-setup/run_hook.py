"""#194 section 5: the hook the run tooling calls. NOTHING here may fail a run.

    h = run_hook.start(out_dir, wsjtx_ini)      # >= LEAD_S before the first played / measured cycle
    ...the run...
    info = run_hook.stop(h)                     # explicit teardown (HK-019) + orphan check
    md = run_hook.finish(h, gathered_dir)       # copies audio_setup.jsonl, writes the summary, returns markdown

Every function swallows its own errors and returns None / a note: a sampler problem is a PARTIAL
sampler output, never a failed run (architect ruling 2026-10-03, section 3.2).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEAD_S = 12.0                         # Amendment 1: start >= 10 s before the first played/measured cycle (margin 2 s)
VERIFIED_WAIT_MAX_S = 60.0            # how long start() will wait for the first 'verified' record
STOP_WAIT_S = 40.0
JSONL_NAME = "audio_setup.jsonl"
SUMMARY_NAME = "audio_setup_summary.md"
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class Handle:
    def __init__(self, proc, stopfile: Path, pidfile: Path, jsonl: Path):
        self.proc, self.stopfile, self.pidfile, self.jsonl = proc, stopfile, pidfile, jsonl
        self.stop_info: dict | None = None


def _note(msg: str) -> None:
    print(f"  [audio-setup] {msg}", flush=True)


def start(out_dir, wsjtx_ini: str | None = None, lead_s: float = LEAD_S, period: float | None = None) -> Handle | None:
    try:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        jsonl, stop, pid = out_dir / JSONL_NAME, out_dir / "audio_setup.stop", out_dir / "audio_setup.pid"
        stop.unlink(missing_ok=True)                     # the CALLER owns the stop file; clear a stale one here
        cmd = [sys.executable, str(HERE / "sampler.py"), "--out", str(jsonl), "--stopfile", str(stop),
               "--pidfile", str(pid)]
        if wsjtx_ini:
            cmd += ["--wsjtx-ini", wsjtx_ini]
        if period:
            cmd += ["--period", str(period)]
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, creationflags=NOWIN)
        t0 = time.time()
        time.sleep(lead_s)
        while time.time() - t0 < VERIFIED_WAIT_MAX_S and proc.poll() is None:
            if jsonl.exists() and '"type": "verified"' in jsonl.read_text(encoding="utf-8", errors="replace"):
                break
            time.sleep(1.0)
        _note(f"sampler running (pid {proc.pid}), lead {time.time() - t0:.0f} s, log {jsonl.name}")
        return Handle(proc, stop, pid, jsonl)
    except Exception:
        _note("COULD NOT START (the run continues without it): " + traceback.format_exc().splitlines()[-1])
        return None


def _sampler_pids() -> list[int]:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
         "Where-Object { $_.CommandLine -match 'audio-setup.sampler\.py' } | Select-Object -ExpandProperty ProcessId"],
        capture_output=True, text=True, stdin=subprocess.DEVNULL, creationflags=NOWIN).stdout
    return [int(x) for x in out.split() if x.strip().isdigit()]


def stop(h: Handle | None) -> dict | None:
    if h is None:
        return None
    if h.stop_info is not None:                          # idempotent: atexit and the normal path may both call
        return h.stop_info
    try:
        h.stopfile.write_text("")
        try:
            rc = h.proc.wait(timeout=STOP_WAIT_S)
            killed = False
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(h.proc.pid)], capture_output=True,
                           stdin=subprocess.DEVNULL, creationflags=NOWIN)
            rc, killed = None, True
        orphans = _sampler_pids()
        h.stop_info = {"returncode": rc, "force_killed": killed, "pidfile_removed": not h.pidfile.exists(),
                       "orphans": orphans}
        _note(f"sampler stopped: {h.stop_info}")
        for pid in orphans:                              # HK-019: an orphan is killed and reported, never left
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True,
                           stdin=subprocess.DEVNULL, creationflags=NOWIN)
        return h.stop_info
    except Exception:
        _note("STOP FAILED: " + traceback.format_exc().splitlines()[-1])
        return None


def finish(h: Handle | None, dest_dir) -> str | None:
    """Copy the log into the gathered directory (HK-016) and write the run-report block."""
    if h is None:
        return None
    try:
        import summarize
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        recs = summarize.load(h.jsonl)
        md = summarize.markdown(summarize.summarise(recs))
        if h.stop_info:
            md += (f"- Teardown: return code {h.stop_info['returncode']}, force-killed {h.stop_info['force_killed']}, "
                   f"pidfile removed {h.stop_info['pidfile_removed']}, orphans found {h.stop_info['orphans']}.\n")
        if Path(h.jsonl).resolve() != (dest / JSONL_NAME).resolve():
            shutil.copy2(h.jsonl, dest / JSONL_NAME)
        (dest / SUMMARY_NAME).write_text(md, encoding="utf-8")
        _note(f"gathered into {dest.name}: {JSONL_NAME}, {SUMMARY_NAME}")
        return md
    except Exception:
        _note("FINISH FAILED: " + traceback.format_exc().splitlines()[-1])
        return None
