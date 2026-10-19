#!/usr/bin/env python3
"""f1_sampler.py - passive 10 Hz sampler of the daemon's arecord child (QA 2026-10-17; Architect F1 amendment 1, section D / A7 D-b').

    f1_sampler.py --daemon-pid PID --out FILE.jsonl [--hz 10] [--stop-file FILE]

One JSON line per sample: {"t": epoch s (float), "pid": arecord pid or null, "state": "R"|"S"|"D"|"T"|..., "wchan": str, "wait_ns": cumulative run-queue delay (schedstat field 2),
"run_ns": field 1}.  The arecord child is looked up through the daemon's children and re-found when it changes.  Reads /proc only; never signals, never ptraces, never writes
anywhere except FILE.  No message text is touched (HK-037).  Stops when --stop-file exists or the daemon is gone.
"""
from __future__ import annotations

import argparse
import json
import os
import time


def arecord_child(daemon_pid: int):
    """The daemon's arecord child, by scanning /proc for ppid == daemon (this kernel has no /proc/<pid>/task/<tid>/children)."""
    try:
        names = os.listdir("/proc")
    except OSError:
        return None
    for n in names:
        if not n.isdigit():
            continue
        try:
            with open("/proc/%s/stat" % n) as fh:
                st = fh.read()
            rest = st[st.rindex(")") + 2:].split()
            comm = st[st.index("(") + 1:st.rindex(")")]
            if comm == "arecord" and int(rest[1]) == daemon_pid:
                return int(n)
        except (OSError, ValueError, IndexError):
            continue
    return None


def read_sample(pid: int):
    try:
        with open("/proc/%d/stat" % pid) as fh:
            st = fh.read()
        state = st[st.rindex(")") + 2:].split()[0]
        try:
            with open("/proc/%d/wchan" % pid) as fh:
                wchan = fh.read().strip()
        except OSError:
            wchan = "?"
        with open("/proc/%d/schedstat" % pid) as fh:
            run_ns, wait_ns, _ = fh.read().split()
        return {"state": state, "wchan": wchan, "run_ns": int(run_ns), "wait_ns": int(wait_ns)}
    except (OSError, ValueError, IndexError):
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--daemon-pid", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--hz", type=float, default=10.0)
    ap.add_argument("--stop-file", default=None)
    a = ap.parse_args()
    period = 1.0 / a.hz
    pid = None
    nxt = time.monotonic()
    with open(a.out, "w", encoding="utf8", newline="\n") as out:
        while True:
            if a.stop_file and os.path.exists(a.stop_file):
                break
            if not os.path.exists("/proc/%d" % a.daemon_pid):
                break
            t = time.time()
            if pid is None or not os.path.exists("/proc/%d" % pid):
                pid = arecord_child(a.daemon_pid)
            s = read_sample(pid) if pid else None
            rec = {"t": round(t, 3), "pid": pid}
            if s:
                rec.update(s)
            out.write(json.dumps(rec) + "\n")
            out.flush()
            nxt += period
            d = nxt - time.monotonic()
            if d > 0:
                time.sleep(d)
            else:
                nxt = time.monotonic()


if __name__ == "__main__":
    main()
