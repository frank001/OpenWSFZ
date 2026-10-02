#!/usr/bin/env python
"""Detached watchdog for the offline flag-OFF/ON replay orchestrator (HK-013, HK-019, HK-023).

WHY THIS EXISTS: the orchestrator restarts a crashed HARNESS (up to 3 times) but nothing restarted the ORCHESTRATOR itself, and an
in-session cron monitor is not durable (HK-023). This is a separate OS process, not tied to any Claude session. It is a WATCHDOG,
not the launcher of the first run (the first launch is done by hand, as for every run); it only recovers a dead or hung run.

Behaviour (HK-013 shape):
  1. Failure triggers, checked every --period seconds:
       - the run is not DONE and NO orchestrator process exists (died, reboot, killed);
       - the run is not DONE and status.json has not been updated for > --stale seconds while a process still exists (HUNG:
         silence itself is the signal, not only an explicit error).
  2. On a trigger: kill the orchestrator tree and any orphan harness, LOG the event (UTC time + reason) to a persistent file
     (watchdog.log in the run directory), wait --cooldown seconds, relaunch the SAME command (the orchestrator is resumable:
     the harness skips cycles already in its CSV and partial rows of an interrupted cycle are repaired).
  3. Confirm the new instance is healthy: within --confirm seconds status.json must show an update NEWER than the relaunch and
     the process must still exist. A relaunch that dies at pre-flight (e.g. a competing process refused by the orchestrator)
     counts as a failed attempt.
  4. Cap: after --retries relaunches the watchdog logs 'GIVING UP' and exits; it never loops forever on a systemic problem.
  5. Teardown (HK-019): the watchdog EXITS by itself when status.json says DONE, or when a file named watchdog.stop appears in
     the run directory, and logs why. It leaves no child behind.

One caveat the report must carry: a relaunch repeats the harness's one discarded warm-up cycle, so the process-global callsign
hash table restarts its history at that point (numeric rows, V4 and V6 are unaffected; text matching of hashed callsigns may differ
in that stretch). Every relaunch is in watchdog.log, so the report can say how many there were.

  python onoff_replay_watchdog.py --out <run dir> --cwd <dir> --match onoff_replay_run.py -- python qa\\rr-study\\sub-feas\\onoff_replay_run.py
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time

DETACHED = 0x00000008          # DETACHED_PROCESS
NEW_GROUP = 0x00000200         # CREATE_NEW_PROCESS_GROUP
NO_WINDOW = 0x08000000         # CREATE_NO_WINDOW


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def stamp():
    return now().strftime("%Y-%m-%dT%H:%M:%SZ")


def log(path, msg):
    line = f"{stamp()} {msg}"
    print(line, flush=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def list_processes(match):
    """PIDs of processes whose command line contains `match` (never this watchdog: its own command line is excluded)."""
    # The PowerShell doing the lookup carries the match text in its OWN command line, so it must exclude itself ($PID).
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -and $_.CommandLine -like '*" +
          match.replace("'", "''") + "*' } | ForEach-Object { $_.ProcessId }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    return [int(x) for x in out.split() if x.strip().isdigit() and int(x) != os.getpid()]


def kill_tree(pid):
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, stdin=subprocess.DEVNULL)


def read_status(path):
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        t = datetime.datetime.strptime(d["updated_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        return d.get("phase"), t
    except Exception:
        return None, None


def launch(cmd, cwd, out):
    so = open(os.path.join(out, "orchestrator.stdout.txt"), "a")
    se = open(os.path.join(out, "orchestrator.stderr.txt"), "a")
    return subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=so, stderr=se, creationflags=DETACHED | NEW_GROUP | NO_WINDOW)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--cwd", required=True)
    ap.add_argument("--match", required=True, help="substring of the orchestrator's command line")
    ap.add_argument("--orphan-match", default="Replay81.dll", help="substring of the harness's command line (orphan cleanup)")
    ap.add_argument("--period", type=float, default=300)
    ap.add_argument("--stale", type=float, default=300)
    ap.add_argument("--cooldown", type=float, default=300)
    ap.add_argument("--confirm", type=float, default=240)
    ap.add_argument("--retries", type=int, default=5)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    cmd = [c for c in a.cmd if c != "--"]
    wlog = os.path.join(a.out, "watchdog.log")
    status_path = os.path.join(a.out, "status.json")
    stop_path = os.path.join(a.out, "watchdog.stop")
    log(wlog, f"watchdog start pid={os.getpid()} period={a.period}s stale={a.stale}s cooldown={a.cooldown}s retries={a.retries} cmd={cmd}")
    relaunches = 0
    while True:
        if os.path.exists(stop_path):
            log(wlog, "watchdog.stop present: exiting")
            return 0
        phase, updated = read_status(status_path)
        if phase == "DONE":
            log(wlog, f"status DONE: run complete, watchdog exiting after {relaunches} relaunch(es)")
            return 0
        pids = list_processes(a.match)
        age = (now() - updated).total_seconds() if updated else float("inf")
        reason = None
        if not pids:
            reason = f"no orchestrator process (phase={phase}, status age {age:.0f}s)"
        elif age > a.stale:
            reason = f"orchestrator hung: pid(s) {pids} alive but status.json stale {age:.0f}s > {a.stale:.0f}s (phase={phase})"
        if reason:
            if relaunches >= a.retries:
                log(wlog, f"GIVING UP after {relaunches} relaunch(es); last trigger: {reason}")
                return 2
            log(wlog, f"TRIGGER: {reason}")
            for p in pids:
                kill_tree(p)
            for p in list_processes(a.orphan_match):
                kill_tree(p)
            log(wlog, f"killed orchestrator tree and orphan harness; cooling down {a.cooldown:.0f}s")
            time.sleep(a.cooldown)
            relaunches += 1
            t_launch = now()
            proc = launch(cmd, a.cwd, a.out)
            log(wlog, f"relaunch {relaunches}/{a.retries}: pid={proc.pid}")
            healthy = False
            deadline = time.time() + a.confirm
            while time.time() < deadline:
                time.sleep(min(5, max(0.2, a.confirm / 10)))
                ph, up = read_status(status_path)
                if ph == "DONE" or (up is not None and up > t_launch and list_processes(a.match)):
                    healthy = True
                    break
                if proc.poll() is not None and not list_processes(a.match):
                    break
            log(wlog, "relaunch " + ("HEALTHY (fresh status, process alive)" if healthy else "NOT healthy (died or no fresh status)"))
            continue
        time.sleep(a.period)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
