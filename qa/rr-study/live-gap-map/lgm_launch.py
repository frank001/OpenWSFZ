#!/usr/bin/env python
"""Create the C3 corpus dir (HK-016 naming), copy the supervisor (and the harness, if present) INTO it so a branch switch can never pull the running file away,
and start the supervisor fully detached from this session (job breakaway first, plain detach as the fallback).  Prints the corpus dir and the supervisor pid."""
import datetime, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
now = datetime.datetime.now(datetime.timezone.utc)
corpus = os.path.join(REPO, "artefacts", now.strftime("%Y%m%d_%H%M") + "_live_run-live-gap-map")
os.makedirs(os.path.join(corpus, "tools"), exist_ok=True)
for f in ("lgm_supervisor.py", "lgm_harness.py"):
    if os.path.exists(os.path.join(HERE, f)):
        shutil.copy2(os.path.join(HERE, f), os.path.join(corpus, "tools", f))
cmd = [sys.executable, os.path.join(corpus, "tools", "lgm_supervisor.py"), "--corpus", corpus]
out = open(os.path.join(corpus, "supervisor.stdout.log"), "ab")
DETACHED, NEWGROUP, BREAKAWAY = 0x00000008, 0x00000200, 0x01000000
try:
    p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=corpus, creationflags=DETACHED | NEWGROUP | BREAKAWAY, close_fds=True)
    how = "detached + job breakaway"
except OSError:
    p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=corpus, creationflags=DETACHED | NEWGROUP, close_fds=True)
    how = "detached (no job breakaway available)"
with open(os.path.join(corpus, "supervisor.pid"), "w") as f:
    f.write(str(p.pid))
print("CORPUS=" + corpus)
print("SUPERVISOR_PID=%d (%s)" % (p.pid, how))
