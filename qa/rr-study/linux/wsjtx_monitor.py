"""M1: WSJT-X monitor for the Linux R&R batteries (QA tooling; aggregates and kernel/process state only, no message text).

    python wsjtx_monitor.py --save-dir <WSJT-X save/> --out-dir <run supervisor dir> [--owsfz-archive <cycle-audio dir>] [--interval 15] [--stall-s 45]
                            [--abort-on-stall] [--stop-file <path>]

Every `--interval` seconds one JSON line is appended to `<out-dir>/monitor.jsonl`: UTC time, the PIDs, state, RSS and thread count of the REAL `wsjtx`
and `jt9` binaries (by /proc/<pid>/comm, never the xvfb-run wrapper the first watcher logged), the age and count of the newest save WAV, the
OpenWSFZ cycle-audio archive's newest age, ALSA PCM states, the capture PCM's kernel `hw_ptr` (frames; advances 48,000 per second while the sound hardware delivers) and every `wsjtx` thread's CPU ticks (a
thread that works advances; one blocked does not), the number of live `aplay` processes (and the oldest one's age), and the suspended time
since boot (CLOCK_BOOTTIME - CLOCK_MONOTONIC), so a stall can be tied to a sleep or cleared of one.

On a STALL (no new save WAV for more than `--stall-s`, or no `wsjtx` process) it writes ONE snapshot folder `<out-dir>/stall-<UTC>/` per episode: for
every `wsjtx`, `jt9` and `Xvfb` process /proc/<pid>/{status,stat,wchan,syscall,limits}, every thread's comm/stat/wchan/syscall, the open-file list, the ALSA
PCM status and hw_params files, `ps -eLf`, and the last 40 monitor lines. The WAIT CHANNEL of the audio thread separates "blocked in snd_pcm_read
(ALSA)" from a Qt or jt9 wedge. With `--abort-on-stall` (default OFF) it then sends SIGABRT to the hung `wsjtx` so a core dump is written (needs
`ulimit -c unlimited` in the launching shell); it never restarts anything. It stops when `--stop-file` appears or on SIGTERM/SIGINT.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from harness import liveness as LV  # noqa: E402

SNAPSHOT_COMMS = (LV.WSJTX_COMM, LV.JT9_COMM, "Xvfb")
TAIL_LINES = 40


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read(path: str, limit: int = 4000) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError as e:
        return "<unreadable: %s>" % e.__class__.__name__


def proc_state(pid: int, proc_root: str = "/proc") -> dict:
    st = _read(os.path.join(proc_root, str(pid), "status"))
    kv = {}
    for line in st.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            kv[k.strip()] = v.strip()
    return {"pid": pid, "state": kv.get("State"), "rss_kb": kv.get("VmRSS"), "threads": kv.get("Threads")}


def alsa_states(alsa_root: str = "/proc/asound") -> dict:
    out = {}
    for p in sorted(glob.glob(os.path.join(alsa_root, "card*", "pcm*", "sub*", "status"))):
        key = os.path.relpath(p, alsa_root).replace(os.sep, "/")
        first = _read(p, 200).strip().splitlines()
        out[key] = first[0] if first else ""
    return out


HW_PTR = re.compile(r"hw_ptr\s*:\s*(\d+)")


def alsa_capture_hw_ptr(alsa_root: str = "/proc/asound") -> dict:
    """The kernel's hardware pointer (frames) of every capture substream: it advances 48,000 per second while the sound hardware delivers, whether or not the
    application reads (2026-10-14: the 19:35Z stall could not tell 'device stopped' from 'app stopped'; the status fields appl_ptr/avail do not, a healthy WSJT-X reads the same)."""
    out = {}
    for p in sorted(glob.glob(os.path.join(alsa_root, "card*", "pcm*c", "sub*", "status"))):
        m = HW_PTR.search(_read(p, 600))
        if m:
            out[os.path.relpath(p, alsa_root).replace(os.sep, "/")] = int(m.group(1))
    return out


def thread_cpu_ticks(pid: int, proc_root: str = "/proc") -> dict:
    """{tid: [comm, utime + stime clock ticks]} for every thread of `pid`: a thread that is alive and working has ticks that advance; one blocked or idle does not."""
    out = {}
    base = os.path.join(proc_root, str(pid), "task")
    try:
        tids = os.listdir(base)
    except OSError:
        return out
    for tid in tids:
        if not tid.isdigit():
            continue
        st = _read(os.path.join(base, tid, "stat"), 600)
        try:
            comm = st[st.index("(") + 1:st.rindex(")")]
            f = st[st.rindex(")") + 2:].split()
            out[tid] = [comm, int(f[11]) + int(f[12])]
        except (ValueError, IndexError):
            continue
    return out


def aplay_info(proc_root: str = "/proc") -> dict:
    pids = LV.pids_by_comm("aplay", proc_root)
    oldest = None
    for pid in pids:
        try:
            with open(os.path.join(proc_root, str(pid), "stat"), encoding="utf-8") as fh:
                start_ticks = int(fh.read().rsplit(")", 1)[1].split()[19])
            with open(os.path.join(proc_root, "uptime"), encoding="utf-8") as fh:
                up = float(fh.read().split()[0])
            age = up - start_ticks / os.sysconf("SC_CLK_TCK")
            oldest = age if oldest is None else max(oldest, age)
        except (OSError, ValueError, IndexError):
            continue
    return {"count": len(pids), "oldest_s": None if oldest is None else round(oldest, 1)}


def suspended_s() -> float:
    try:
        return round(time.clock_gettime(time.CLOCK_BOOTTIME) - time.clock_gettime(time.CLOCK_MONOTONIC), 1)
    except (AttributeError, OSError):
        return -1.0


def sample(save_dir: str, archive_dir: str | None, now: float, stall_s: float, proc_root: str = "/proc", alsa_root: str = "/proc/asound") -> dict:
    lv = LV.check_liveness(save_dir, stall_s, now, proc_root, True)
    wavs = LV.list_wav_slots(save_dir)
    s = {"t": utc_now(), "ok": lv.ok, "reason": lv.reason, "wav_age_s": None if lv.age_s is None else round(lv.age_s, 1), "wav_count": len(wavs),
         "wsjtx": [proc_state(p, proc_root) for p in lv.pids], "jt9": [proc_state(p, proc_root) for p in LV.pids_by_comm(LV.JT9_COMM, proc_root)],
         "aplay": aplay_info(proc_root), "alsa": alsa_states(alsa_root), "suspended_s": suspended_s(),
         "capture_hw_ptr": alsa_capture_hw_ptr(alsa_root), "wsjtx_cpu_ticks": {str(p): thread_cpu_ticks(p, proc_root) for p in lv.pids}}
    try:
        s["load1"] = round(os.getloadavg()[0], 2)          # host load: the decoders share the CPU with everything else on the box
    except (AttributeError, OSError):
        pass
    if archive_dir:
        a = LV.newest_wav_age_s(archive_dir, now)
        s["owsfz_archive_age_s"] = None if a is None else round(a, 1)
    return s


def snapshot(out_dir: str, tail: list, proc_root: str = "/proc", alsa_root: str = "/proc/asound") -> str:
    """One snapshot folder; returns its path. Everything is best effort: an unreadable file is recorded as such, never an error."""
    path = os.path.join(out_dir, "stall-" + utc_now().replace(":", ""))
    os.makedirs(path, exist_ok=True)
    for comm in SNAPSHOT_COMMS:
        for pid in LV.pids_by_comm(comm, proc_root):
            d = os.path.join(path, "%s-%d" % (comm, pid))
            os.makedirs(d, exist_ok=True)
            base = os.path.join(proc_root, str(pid))
            for f in ("status", "stat", "wchan", "syscall", "limits"):
                with open(os.path.join(d, f + ".txt"), "w", encoding="utf-8") as fh:
                    fh.write(_read(os.path.join(base, f)))
            try:
                fds = []
                for fd in sorted(os.listdir(os.path.join(base, "fd")), key=lambda x: int(x) if x.isdigit() else 0):
                    try:
                        fds.append("%s -> %s" % (fd, os.readlink(os.path.join(base, "fd", fd))))
                    except OSError:
                        fds.append("%s -> <unreadable>" % fd)
                text = "\n".join(fds)
            except OSError as e:
                text = "<unreadable: %s>" % e.__class__.__name__
            with open(os.path.join(d, "fd.txt"), "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
            lines = []
            try:
                for tid in sorted(os.listdir(os.path.join(base, "task")), key=lambda x: int(x) if x.isdigit() else 0):
                    tb = os.path.join(base, "task", tid)
                    lines.append("tid %s comm=%s wchan=%s syscall=%s" % (tid, _read(os.path.join(tb, "comm"), 64).strip(), _read(os.path.join(tb, "wchan"), 64).strip(),
                                                                         _read(os.path.join(tb, "syscall"), 200).strip()))
                    lines.append("   stat: " + _read(os.path.join(tb, "stat"), 400).strip())
            except OSError as e:
                lines.append("<task list unreadable: %s>" % e.__class__.__name__)
            with open(os.path.join(d, "threads.txt"), "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
    with open(os.path.join(path, "alsa.txt"), "w", encoding="utf-8") as fh:
        for p in sorted(glob.glob(os.path.join(alsa_root, "card*", "pcm*", "sub*", "status")) + glob.glob(os.path.join(alsa_root, "card*", "pcm*", "sub*", "hw_params"))):
            fh.write("== %s\n%s\n" % (os.path.relpath(p, alsa_root), _read(p, 1500)))
    try:
        ps = subprocess.run(["ps", "-eLf"], capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        ps = "<ps unavailable>"
    with open(os.path.join(path, "ps.txt"), "w", encoding="utf-8") as fh:
        fh.write(ps)
    with open(os.path.join(path, "tail.jsonl"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(json.dumps(x) for x in tail[-TAIL_LINES:]) + "\n")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--owsfz-archive")
    ap.add_argument("--interval", type=float, default=LV.POLL_S)
    ap.add_argument("--stall-s", type=float, default=LV.STALL_S)
    ap.add_argument("--abort-on-stall", action="store_true", help="send SIGABRT to the hung wsjtx after the snapshot, so a core is written (needs ulimit -c unlimited); default off")
    ap.add_argument("--stop-file", default=None)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    stop = a.stop_file or os.path.join(a.out_dir, "monitor.stop")
    halt = {"flag": False}
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: halt.update(flag=True))
    log = os.path.join(a.out_dir, "monitor.jsonl")
    # SEQUENTIAL S6 (Captain 2026-10-15): while OpenWSFZ plays its pass alone, WSJT-X is switched off ON PURPOSE. The launcher's phase hook creates this flag file for that
    # time; a sample taken while it exists is tagged `expected_off` and is neither a stall nor a snapshot. The summary counts those samples apart.
    expected_off_flag = os.path.join(a.out_dir, "wsjtx.expected_off")
    tail: list = []
    in_stall = False
    print("monitor started %s: save-dir=%s interval=%.0fs stall=%.0fs abort_on_stall=%s" % (utc_now(), a.save_dir, a.interval, a.stall_s, a.abort_on_stall), flush=True)
    while not halt["flag"] and not os.path.exists(stop):
        s = sample(a.save_dir, a.owsfz_archive, time.time(), a.stall_s)
        if os.path.exists(expected_off_flag):
            s["expected_off"] = True
        tail.append(s)
        tail[:] = tail[-TAIL_LINES:]
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(s) + "\n")
        stalled = (not s["ok"]) and not s.get("expected_off")
        if stalled and not in_stall:
            in_stall = True
            d = snapshot(a.out_dir, tail)
            with open(os.path.join(a.out_dir, "stall_events.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"t": utc_now(), "reason": s["reason"], "snapshot": d, "suspended_s": s["suspended_s"]}) + "\n")
            print("STALL %s: %s -> snapshot %s" % (utc_now(), s["reason"], d), flush=True)
            if a.abort_on_stall:
                for p in LV.pids_by_comm(LV.WSJTX_COMM):
                    try:
                        os.kill(p, signal.SIGABRT)
                        print("SIGABRT sent to wsjtx %d (core dump needs ulimit -c unlimited)" % p, flush=True)
                    except OSError as e:
                        print("SIGABRT failed for %d: %s" % (p, e), flush=True)
        elif not stalled:
            in_stall = False
        for _ in range(int(a.interval * 2)):
            if halt["flag"] or os.path.exists(stop):
                break
            time.sleep(0.5)
    print("monitor stopped %s" % utc_now(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
