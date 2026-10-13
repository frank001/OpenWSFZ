"""Is WSJT-X running? (QA tooling; the PRECHECK row "WSJT-X alive", 2026-10-13.)

Why it exists: the three Linux repeats of 2026-10-11 ran 3 x 1 h 53 min with WSJT-X NOT decoding (its ALL.TXT gained no line), and nothing
stopped the battery: every matcher logged "WSJT-X: 0/30 matched" and the run went to the end as an OpenWSFZ-only reading. HK-020: verify a run's
critical configuration before arming. This module is the cheap half (a process exists; no audio, no decoder); the decode half is
harness/warmup_check.py, run before scenario 1.

    wsjtx_pids()  -> sorted list of process ids of WSJT-X (Linux: /proc/<pid>/comm == "wsjtx"; Windows: tasklist wsjtx.exe)
    check()       -> {"wsjtx_running": bool, "count": int, "pids": [...]}   (ids only, never a command line: NFR-021)
"""
from __future__ import annotations

import csv
import io
import os
import subprocess
import sys

COMM = "wsjtx"                 # /proc/<pid>/comm of the WSJT-X binary (not "jt9", the decoder child)
WIN_IMAGE = "wsjtx.exe"


def _linux_pids(proc_dir: str = "/proc") -> list:
    out = []
    for d in os.listdir(proc_dir):
        if d.isdigit():
            try:
                with open(os.path.join(proc_dir, d, "comm")) as fh:
                    if fh.read().strip() == COMM:
                        out.append(int(d))
            except OSError:
                pass
    return sorted(out)


def _windows_pids(run=subprocess.run) -> list:
    r = run(["tasklist", "/FI", "IMAGENAME eq " + WIN_IMAGE, "/FO", "CSV", "/NH"], capture_output=True, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=30)
    out = []
    for row in csv.reader(io.StringIO(r.stdout)):
        if len(row) >= 2 and row[0].lower() == WIN_IMAGE and row[1].isdigit():
            out.append(int(row[1]))
    return sorted(out)


def wsjtx_pids() -> list:
    return _windows_pids() if sys.platform == "win32" else _linux_pids()


def check() -> dict:
    pids = wsjtx_pids()
    return {"wsjtx_running": bool(pids), "count": len(pids), "pids": pids}


if __name__ == "__main__":
    r = check()
    print(r)
    sys.exit(0 if r["wsjtx_running"] else 1)
