#!/usr/bin/env python3
"""slave-probe.py - read-only probe (QA 2026-10-17): what client buffer and period does arecord get, for a given dsnoop slave period/buffer, with the planned product arguments?
Uses a PRIVATE ALSA config (a copy of the rig's .asoundrc with the slave numbers changed, another ipc_key, ALSA_CONFIG_PATH for this process only). Touches nothing of the rig's.
Needs no audio program running.  Prints one line per combination."""
import os
import re
import subprocess
import sys

HOME = os.path.expanduser("~")
D = HOME + "/qa-scratch/capture-loss/f1"
RIG = open(HOME + "/.asoundrc").read()
BASE = open(D + "/alsa-f1.conf").read()
ARGS = sys.argv[1].split() if len(sys.argv) > 1 else ["--buffer-time=4000000", "--period-time=20000"]
COMBOS = [(1200, 9600), (1200, 38400), (1200, 192000), (2400, 76800), (3000, 96000), (6400, 192000)]


def grab(out, head, stop, key):
    m = re.search(head + r".*?" + stop, out, re.S)
    seg = m.group(0) if m else ""
    k = re.search(key + r"\s*:\s*(\d+)", seg)
    return int(k.group(1)) if k else None


for i, (per, buf) in enumerate(COMBOS):
    rc = RIG.replace("ipc_key 51234", "ipc_key %d" % (51240 + i)).replace("period_size 1200", "period_size %d" % per).replace("buffer_size 9600", "buffer_size %d" % buf)
    open(D + "/asoundrc-probe", "w").write(rc)
    open(D + "/alsa-probe.conf", "w").write(BASE.replace(D + "/asoundrc-f1", D + "/asoundrc-probe"))
    env = dict(os.environ, ALSA_PLUGIN_DIR=HOME + "/local/lib/alsa-lib", ALSA_CONFIG_PATH=D + "/alsa-probe.conf")
    r = subprocess.run(["/usr/bin/arecord", "-v"] + ARGS + ["-D", "rr_in", "-f", "FLOAT_LE", "-r", "12000", "-c", "1", "-t", "raw", "-d", "2", "/dev/null"],
                       capture_output=True, text=True, env=env, timeout=30)
    out = r.stderr
    cb = grab(out, r"Plug PCM", r"Slave: Rate", "buffer_size")
    cp = grab(out, r"Plug PCM", r"Slave: Rate", "period_size")
    sp = grab(out, r"Slave: Direct Snoop", r"$(?!\n)|\Z", "period_size")
    err = "" if cb else " ERROR: " + out.strip().splitlines()[-1][:100] if out.strip() else " no output"
    print("slave period %5d buffer %6d (%d periods) -> client buffer %s frames = %s s, client period %s frames = %s ms, dsnoop period %s%s" % (
        per, buf, buf // per, cb, round(cb / 12000, 3) if cb else None, cp, round(cp / 12.0, 1) if cp else None, sp, err))
for f in ("asoundrc-probe", "alsa-probe.conf"):
    os.remove(D + "/" + f)
