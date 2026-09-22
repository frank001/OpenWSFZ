#!/usr/bin/env python
"""Detached launcher for the R&R S1-S8 study (HK-023: detached + a disposable log tail is
how you watch an unattended run, not a durable scheduler; HK-016 dated output dir).

WHY THIS EXISTS: a full S1-S8 battery, and especially --scenarios S3b/S8HN, runs unattended
for hours (S3b alone is ~4.2h at its corrected sizing) -- run_study.py's own code comment has
said since 2026-08-19 that this "needs an HK-013 supervisor -- not something the default
batch should trigger blind", and none existed until this script.

This wraps run_study.py (or resume_study.py, via --resume) as a DETACHED background process
so the battery survives the terminal/session closing, and logs everything so it can be
checked on later without babysitting it.

WHAT THIS DELIBERATELY DOES NOT DO: automatic restart-on-crash. The endurance-run supervisor
(qa/endurance/endurance_supervisor.py) restarts a crashed daemon because a live capture
session has one long-lived process whose job is "keep listening" -- restarting it loses at
most a few seconds. An R&R battery is different: run_scenario.py plays a precisely-timed
synthesized scene into a live decoder, and truth.csv is built incrementally, scenario by
scenario. A crash mid-scenario needs a human (or at least a deliberate decision) to pick the
correct resume point, which is exactly what resume_study.py already does, reading truth.csv
back to find out which scenarios actually landed rather than assuming. Blindly restarting the
whole run_study.py process would re-run already-completed scenarios and/or diverge from the
project's own established handoff convention (see qa/rr-study/2026-08-15-1931-qa-session-
handoff-s1s8-restart-required.md for a real incident this shape). So: this script supervises
(detached, logged, a clear DONE/FAILED status), it does not decide how to recover -- that
stays a human call, using resume_study.py, same as today.

Application settings, audio routing and the RUNBOOK's one-time/per-session setup are NOT this
script's business -- see qa/rr-study/RUNBOOK.md sections 1-2 for the current, authoritative
procedure; this script does not duplicate or embed a snapshot of it.

Usage (from qa/rr-study/):
    python run_study_detached.py                              # python run_study.py, no extra args
    python run_study_detached.py --skip-s8 --device "Line 1"   # args forwarded to run_study.py
    python run_study_detached.py --resume --from-scenario S4   # forwarded to resume_study.py instead

    powershell -Command "Get-Content <printed supervisor.log path> -Wait -Tail 20"   # HK-023 watch
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SUPERVISOR_RUNS_DIR = os.path.join(HERE, "results", "_supervisor_runs")


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--resume", action="store_true",
                     help="launch resume_study.py instead of run_study.py")
    ap.add_argument("--poll", action="store_true",
                     help="internal: run the target script directly and write status.json "
                          "as it finishes (this is what the detached child actually runs; "
                          "not for interactive use)")
    ap.add_argument("--supervisor-dir", default=None,
                     help="internal: paired with --poll, the dir to write status into")
    a, forwarded = ap.parse_known_args()
    target = "resume_study.py" if a.resume else "run_study.py"

    if a.poll:
        # This branch IS the detached child (launched below). It runs the target script to
        # completion and writes status.json with the outcome -- the one piece of HK-013-style
        # discipline that applies here (log + a clear final status), without the restart loop
        # that doesn't fit this failure model (see module docstring).
        #
        # The grandchild's (run_study.py's) stdout/stderr are opened and passed EXPLICITLY
        # here, not left to inherit through two levels of Popen -- found live, first smoke
        # test: relying on the launcher's own stdout=<file> redirect to implicitly pass
        # through to a subprocess.call() inside THIS already-redirected process produced a
        # completely empty supervisor.log (a real Windows handle-inheritance gap across
        # nested Popen levels, not a flushing issue -- the dummy target's own flush=True
        # prints never landed). Opening the log file directly in this process and passing it
        # as this call's own stdout= fixed it; re-verified with the same dummy target.
        sup_dir = a.supervisor_dir
        status_path = os.path.join(sup_dir, "status.json")
        log_path = os.path.join(sup_dir, "supervisor.log")
        started = datetime.datetime.now(datetime.timezone.utc)
        status = {"phase": "RUNNING", "target": target, "started_utc": iso(started),
                  "pid": os.getpid(), "args": forwarded}
        with open(status_path, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=1)
        with open(log_path, "ab") as logf:
            rc = subprocess.call([sys.executable, target] + forwarded, cwd=HERE,
                                  stdout=logf, stderr=subprocess.STDOUT)
        ended = datetime.datetime.now(datetime.timezone.utc)
        status.update(phase="DONE" if rc == 0 else "FAILED", exit_code=rc, ended_utc=iso(ended))
        with open(status_path, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=1)
        return rc

    # ---------------- launcher: spawn the --poll child, fully detached
    os.makedirs(SUPERVISOR_RUNS_DIR, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc)
    sup_dir = os.path.join(SUPERVISOR_RUNS_DIR, now.strftime("%Y%m%d_%H%M") + ("_resume" if a.resume else "_run"))
    os.makedirs(sup_dir, exist_ok=True)

    cmd = [sys.executable, os.path.abspath(__file__), "--poll", "--supervisor-dir", sup_dir]
    if a.resume:
        cmd.append("--resume")
    cmd += forwarded

    log_path = os.path.join(sup_dir, "supervisor.log")
    out = open(log_path, "ab")
    DETACHED, NEWGROUP, BREAKAWAY = 0x00000008, 0x00000200, 0x01000000
    try:
        p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                              cwd=HERE, creationflags=DETACHED | NEWGROUP | BREAKAWAY, close_fds=True)
        how = "detached + job breakaway"
    except OSError:
        p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                              cwd=HERE, creationflags=DETACHED | NEWGROUP, close_fds=True)
        how = "detached (no job breakaway available)"

    with open(os.path.join(sup_dir, "launcher.pid"), "w") as f:
        f.write(str(p.pid))
    print("SUPERVISOR_DIR=" + sup_dir)
    print("LAUNCHER_PID=%d (%s)" % (p.pid, how))
    print("TARGET=" + target + (" (forwarded args: %s)" % " ".join(forwarded) if forwarded else ""))
    print("watch: powershell -Command \"Get-Content '%s' -Wait -Tail 20\"" % log_path)
    print()
    print("This does NOT auto-restart on a crash (see module docstring). If it dies mid-")
    print("battery, check status.json + supervisor.log, find the actual run dir under")
    print("results/, and resume deliberately: python run_study_detached.py --resume ...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
