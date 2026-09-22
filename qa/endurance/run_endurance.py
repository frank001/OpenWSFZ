#!/usr/bin/env python
"""Standard endurance run -- the single script to kick off and let go.

Captain's instruction (2026-09-22): "It will be always the same, save the datetime stamp...
It should be a single script to kick off and let go." Only the corpus directory name varies
by timestamp; everything else about HOW the run happens is the standard machinery in
endurance_supervisor.py.

This script (via the supervisor it launches) STARTS OpenWSFZ.Daemon.exe itself -- the daemon
exe path, its config file and its port are INPUT to this script (CLI args), not something the
script decides. Whatever decoder settings, audio device and band the given config.json names
are entirely the operator's own choice, prepared beforehand -- this script and its supervisor
never construct or edit that file.

Creates the dated corpus dir (HK-016 naming), copies the supervisor INTO it (so a branch
switch can never pull the running file away, per the LIVE-GAP-MAP precedent), and starts it
fully detached (HK-023: detached + a disposable log tail is how you watch it, not a durable
scheduler). Prints the corpus dir and the supervisor pid.

Requires WSJT-X already running on the agreed band/profile -- this script never starts or
edits WSJT-X.

Usage:
    python run_endurance.py --daemon-exe "C:\\...\\OpenWSFZ.Daemon.exe" --config "C:\\...\\config.json" \\
        --port 8080 --wsjtx-ini "C:\\...\\WSJT-X - FT991A.ini" [--hours 24]
    tail -f <printed corpus>/supervisor.stdout.log     # HK-023 watch, not a poll loop
"""
import argparse, datetime, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--daemon-exe", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--wsjtx-ini", required=True)
    ap.add_argument("--hours", type=float, default=24.0)
    a = ap.parse_args()

    now = datetime.datetime.now(datetime.timezone.utc)
    corpus = os.path.join(REPO, "artefacts", now.strftime("%Y%m%d_%H%M") + "_endurance_run")
    os.makedirs(os.path.join(corpus, "tools"), exist_ok=True)
    shutil.copy2(os.path.join(HERE, "endurance_supervisor.py"),
                 os.path.join(corpus, "tools", "endurance_supervisor.py"))

    cmd = [sys.executable, os.path.join(corpus, "tools", "endurance_supervisor.py"),
           "--corpus", corpus, "--daemon-exe", a.daemon_exe, "--config", a.config,
           "--port", str(a.port), "--hours", str(a.hours), "--wsjtx-ini", a.wsjtx_ini]
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
