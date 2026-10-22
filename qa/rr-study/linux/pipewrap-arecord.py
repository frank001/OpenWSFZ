#!/usr/bin/python3
"""pipewrap-arecord.py - TEST-ONLY wrapper installed as `arecord` in a directory placed first on the DAEMON's PATH (QA 2026-10-17; Architect amendment 1 to the reliable-capture spec).

Sets the pipe on its own stdout (the pipe to the daemon) to 1 MiB with F_SETPIPE_SZ, writes "pipe size N" to stderr (the daemon logs it through the P3 stderr reader), then os.execv's the
real arecord with the SAME arguments.  After the exec this process IS arecord (same pid, comm 'arecord'); no python is left in the chain.  Changes nothing else.
"""
import fcntl
import os
import sys

F_SETPIPE_SZ = 1031
F_GETPIPE_SZ = 1032
WANTED = 1048576

try:
    fcntl.fcntl(1, F_SETPIPE_SZ, WANTED)
    msg = "pipe size %d" % fcntl.fcntl(1, F_GETPIPE_SZ)
except OSError as e:
    msg = "pipe size FAILED: %s" % e
sys.stderr.write(msg + "\n")
sys.stderr.flush()
os.execv("/usr/bin/arecord", ["arecord"] + sys.argv[1:])
