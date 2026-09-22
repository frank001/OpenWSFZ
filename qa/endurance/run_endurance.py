#!/usr/bin/env python
"""Standard endurance run -- the single script to kick off and let go.

Captain's instruction (2026-09-22): "It will be always the same, save the datetime stamp...
It should be a single script to kick off and let go." Only the corpus directory name varies
by timestamp; everything else about HOW the run happens is the standard machinery in
endurance_supervisor.py.

Creates the dated corpus dir (HK-016 naming), copies the supervisor INTO it (so a branch
switch can never pull the running file away, per the LIVE-GAP-MAP precedent), and starts it
fully detached (HK-023: detached + a disposable log tail is how you watch it, not a durable
scheduler). Prints the corpus dir and the supervisor pid.

Requires the operator to have ALREADY started OpenWSFZ.Daemon.exe (any port, any config, any
decoder settings -- "configured before the run", agreed beforehand) and WSJT-X, on the band
already agreed. This script and its supervisor never start, stop, or edit either.

Usage:
    python run_endurance.py --wsjtx-ini "C:\\...\\WSJT-X - FT991A.ini" [--hours 24] [--port 8080]
    tail -f <printed corpus>/supervisor.stdout.log     # HK-023 watch, not a poll loop
"""
import argparse, datetime, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wsjtx-ini", required=True)
    ap.add_argument("--hours", type=float, default=24.0)
    ap.add_argument("--port", type=int, default=8080)
    a = ap.parse_args()

    now = datetime.datetime.now(datetime.timezone.utc)
    corpus = os.path.join(REPO, "artefacts", now.strftime("%Y%m%d_%H%M") + "_endurance_run")
    os.makedirs(os.path.join(corpus, "tools"), exist_ok=True)
    shutil.copy2(os.path.join(HERE, "endurance_supervisor.py"),
                 os.path.join(corpus, "tools", "endurance_supervisor.py"))

    cmd = [sys.executable, os.path.join(corpus, "tools", "endurance_supervisor.py"),
           "--corpus", corpus, "--hours", str(a.hours), "--port", str(a.port),
           "--wsjtx-ini", a.wsjtx_ini]
    out = open(os.path.join(corpus, "supervisor.stdout.log"), "ab")
    DETACHED, NEWGROUP, BREAKAWAY = 0x00000008, 0x00000200, 0x01000000
    try:
        p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                              cwd=corpus, creationflags=DETACHED | NEWGROUP | BREAKAWAY, close_fds=True)
        how = "detached + job breakaway"
    except OSError:
        p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                              cwd=corpus, creationflags=DETACHED | NEWGROUP, close_fds=True)
        how = "detached (no job breakaway available)"
    with open(os.path.join(corpus, "supervisor.pid"), "w") as f:
        f.write(str(p.pid))
    print("CORPUS=" + corpus)
    print("SUPERVISOR_PID=%d (%s)" % (p.pid, how))
    print("watch: powershell -Command \"Get-Content '%s' -Wait -Tail 20\""
          % os.path.join(corpus, "supervisor.log"))


if __name__ == "__main__":
    main()
