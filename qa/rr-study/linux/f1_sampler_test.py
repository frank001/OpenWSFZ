#!/usr/bin/env python3
"""f1_sampler_test.py - checks on sol that f1_sampler.py can tell the two states apart (QA 2026-10-17; HK-026: prove the instrument responds before believing it).

  A: arecord writes into a pipe nobody reads (the L2 shape)            -> expect state S with a wchan containing 'pipe'
  B: arecord pinned to one CPU, niced, with busy loops on that CPU,     -> expect state R samples and a rising run-queue delay (the L1 shape)
     stdout drained
Both use a short-lived parent process as the 'daemon' so nothing of the rig's is touched.  Prints counts only.
"""
import json
import os
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
ENV = dict(os.environ, ALSA_PLUGIN_DIR=HOME + "/local/lib/alsa-lib")
AR = ["/usr/bin/arecord", "-D", "rr_in", "-f", "FLOAT_LE", "-r", "12000", "-c", "1", "-t", "raw", "-"]


def run(label, popen_kw, extra, secs, out):
    parent = subprocess.Popen([sys.executable, "-c", """
import subprocess, sys, time, os
kw = %r
ar = subprocess.Popen(%r, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=%r, **kw)
drain = %r
t0 = time.time()
while time.time() - t0 < %r:
    if drain:
        os.read(ar.stdout.fileno(), 65536)
    else:
        time.sleep(0.2)
ar.kill()
""" % ({}, popen_kw["cmd"], ENV, popen_kw["drain"], secs)])
    time.sleep(0.5)
    samp = subprocess.Popen([sys.executable, HOME + "/f1_sampler.py", "--daemon-pid", str(parent.pid), "--out", out])
    busy = [subprocess.Popen(["taskset", "-c", "3", "sh", "-c", "while :; do :; done"]) for _ in range(extra)]
    parent.wait()
    for b in busy:
        b.kill()
    samp.wait(timeout=10)
    s = [json.loads(l) for l in open(out)]
    s = [x for x in s if x.get("state")]
    states = {}
    for x in s:
        k = x["state"] + ("/pipe" if "pipe" in x.get("wchan", "") else "")
        states[k] = states.get(k, 0) + 1
    delay = (s[-1]["wait_ns"] - s[0]["wait_ns"]) / 1e9 if s else None
    el = (s[-1]["t"] - s[0]["t"]) if s else None
    print(label, "samples", len(s), "states", states, "run-queue delay %.2f s over %.2f s" % (delay or 0, el or 0), "wchan sample", sorted({x.get("wchan") for x in s})[:4])


run("A pipe-blocked", {"cmd": AR, "drain": False}, 0, 6, HOME + "/qa-scratch/capture-loss/f1/sampler-test-A.jsonl")
run("B cpu-starved ", {"cmd": ["taskset", "-c", "3", "nice", "-n", "15"] + AR, "drain": True}, 3, 6, HOME + "/qa-scratch/capture-loss/f1/sampler-test-B.jsonl")
