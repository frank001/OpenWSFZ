#!/usr/bin/env python
"""SUB-FEAS on-air arm: detached memory sampler and config-flag watcher (companion to endurance_supervisor.py).

Not a supervisor: it never kills, restarts or edits anything. Every SAMPLE_MIN minutes (default 30), and once at
start and once at the end, it records
  * the daemon's process working set, private bytes, thread and handle counts (PID found from the listening port, so a
    supervisor restart is followed and logged as an event), and
  * the daemon's LIVE config flags read from GET /api/v1/config: decoder.subtractionEnabled,
    decoder.subtractionMaxThreads, decoder.osdNhardMax, tx.autoAnswer, cycleAudioArchive.mode.
It compares them with what the run was armed with and writes a loud event for any difference (a Settings-page save
resets the flag and the archive while #193 is unmerged). It does NOT restore anything.

Ends at the first of: a file named STOP in the sampler directory, or --hours elapsed. It takes a final sample either
way, so "the flag re-checked at the end" is a record, not an inference.

HK-013/019/023: run it detached (nohup ... & disown); its own PID is written to sampler.pid so teardown can find it
(HK-019). HK-037/NFR-021: it reads only numeric process counters and the four config flags above. It never reads or
writes a callsign, a message, or any other config value.

Output (in <run-dir>/subfeas_arm/): memory_samples.jsonl, events.jsonl, sampler.log, sampler.pid.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time
import urllib.request

NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


def iso(t=None):
    return (t or utcnow()).strftime("%Y-%m-%dT%H:%M:%SZ")


def ps(cmd, timeout=30):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True,
                       timeout=timeout, creationflags=NOWIN)
    return r.stdout.strip()


def daemon_pid(port):
    out = ps("(Get-NetTCPConnection -LocalPort %d -State Listen -ErrorAction SilentlyContinue | "
             "Select-Object -First 1 -ExpandProperty OwningProcess)" % port)
    return int(out) if out.isdigit() else None


def proc_counters(pid):
    out = ps("$p = Get-Process -Id %d -ErrorAction SilentlyContinue; if ($p) { "
             "'{0},{1},{2},{3},{4}' -f $p.WorkingSet64, $p.PrivateMemorySize64, $p.Threads.Count, $p.HandleCount, $p.ProcessName }"
             % pid)
    if not out or "," not in out:
        return None
    ws, priv, thr, hnd, name = out.split(",", 4)
    return {"working_set_bytes": int(ws), "private_bytes": int(priv), "threads": int(thr), "handles": int(hnd),
            "process_name": name}


def live_flags(port):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/v1/config" % port, timeout=8) as r:
            c = json.loads(r.read().decode("utf-8"))
    except Exception as ex:
        return {"error": type(ex).__name__}
    dec = c.get("decoder") or {}
    return {"subtractionEnabled": dec.get("subtractionEnabled", "absent"),
            "subtractionMaxThreads": dec.get("subtractionMaxThreads", "absent"),
            "osdNhardMax": dec.get("osdNhardMax", "absent"),
            "autoAnswer": (c.get("tx") or {}).get("autoAnswer", "absent"),
            "cycleAudioArchiveMode": (c.get("cycleAudioArchive") or {}).get("mode", "absent")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--interval-min", type=float, default=30.0)
    ap.add_argument("--hours", type=float, required=True, help="hard stop (sampler TTL, HK-019)")
    ap.add_argument("--expect-subtraction", default="true", choices=["true", "false"])
    ap.add_argument("--expect-archive-mode", default="all")
    ap.add_argument("--expect-nhard", type=int, default=40)
    ap.add_argument("--expect-threads", type=int, default=8,
                    help="decoder.subtractionMaxThreads the run is armed with (2026-09-30: 8, Architect/Captain); asserted at every sample")
    a = ap.parse_args()

    d = os.path.join(a.run_dir, "subfeas_arm")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "sampler.pid"), "w").write(str(os.getpid()))
    expect = {"subtractionEnabled": a.expect_subtraction == "true", "subtractionMaxThreads": a.expect_threads,
              "autoAnswer": False,
              "cycleAudioArchiveMode": a.expect_archive_mode, "osdNhardMax": a.expect_nhard}
    end = utcnow() + datetime.timedelta(hours=a.hours)
    log = open(os.path.join(d, "sampler.log"), "a", encoding="utf-8")

    def L(m):
        log.write("%s %s\n" % (iso(), m))
        log.flush()

    def event(kind, **kw):
        with open(os.path.join(d, "events.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"utc": iso(), "event": kind, **kw}) + "\n")
        L("EVENT " + kind + " " + json.dumps(kw))

    last_pid = None
    last_flags_bad = False
    n = 0

    def sample(tag):
        nonlocal last_pid, last_flags_bad, n
        pid = daemon_pid(a.port)
        rec = {"utc": iso(), "tag": tag, "seq": n, "pid": pid}
        if pid is None:
            event("NO_DAEMON_ON_PORT", port=a.port)
        else:
            c = proc_counters(pid)
            rec.update(c or {"counters": "unavailable"})
            if last_pid is not None and pid != last_pid:
                event("DAEMON_PID_CHANGED", old=last_pid, new=pid)
            last_pid = pid
        fl = live_flags(a.port)
        rec["flags"] = fl
        if "error" in fl:
            event("CONFIG_READ_FAILED", error=fl["error"])
        else:
            diffs = {k: {"expected": v, "actual": fl.get(k)} for k, v in expect.items() if fl.get(k) != v}
            if diffs and not last_flags_bad:
                event("FLAG_MISMATCH", diffs=diffs)
            if not diffs and last_flags_bad:
                event("FLAGS_BACK_TO_EXPECTED")
            last_flags_bad = bool(diffs)
            rec["flags_ok"] = not diffs
        with open(os.path.join(d, "memory_samples.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        n += 1
        L("sample %s pid=%s ws=%s priv=%s flags_ok=%s" % (tag, pid, rec.get("working_set_bytes"), rec.get("private_bytes"),
                                                         rec.get("flags_ok")))

    event("SAMPLER_START", interval_min=a.interval_min, hours=a.hours, expect=expect)
    sample("start")
    next_t = time.time() + a.interval_min * 60
    while utcnow() < end and not os.path.exists(os.path.join(d, "STOP")):
        time.sleep(5)
        if time.time() >= next_t:
            sample("periodic")
            next_t = time.time() + a.interval_min * 60
    sample("final")
    event("SAMPLER_END", reason="STOP file" if os.path.exists(os.path.join(d, "STOP")) else "TTL")
    try:
        os.remove(os.path.join(d, "sampler.pid"))
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
