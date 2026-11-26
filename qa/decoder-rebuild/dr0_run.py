#!/usr/bin/env python3
"""DR-0 arm runner (decoder rebuild, spec-dr0-dr1-measure-and-relief.md section 2).

  python -I dr0_run.py <arm A1..A9> <n_cycles> [--tag pilot]

Replays the first <n_cycles> of Slice 40 (test-set.md) through the QA replay harness (Ft8.FitProbe.exe = Replay81 over the shipped
decoder; the binary dir below) with the arm's configuration, measures the harness process's CPU seconds (user + kernel, read from the
process handle after exit) and scores it. Aggregates only go to stdout and arm.json; the text-bearing nc.tsv stays under
_qa-scratch (HK-037, KEEP). Refuses to run when a competing process is up or the binary is not the pinned build (HK-022).
"""
import ctypes
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes

SC = r"D:\Projects\claude\_qa-scratch"
ART = r"D:\Projects\claude\OpenWSFZ\artefacts"
BIN = SC + r"\xc-chain\bin_defaults"                      # harness over the shipped 66b3ddf1 (the decoder is identical at v1.0)
PIN = "bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528"   # libft8.dll, as LR-BUILD's arms
NIGHT = "20261114_2312"
SRC_SEL = SC + r"\xc-live-free\sel_full.json"
SLICE_START = "261115_072930"
SLICE_CYCLES = 240
WSJTX_DECODES_FULL_SLICE = 9431                           # test-set.md: ALL.TXT lines stamped inside the 240-cycle window
OUT_ROOT = SC + r"\dr0"
TE = "3.076041980658299"                                   # XC frozen threshold, as the station's config (readback line)

# A6 = the station's configuration today (the LR-BUILD V-OFF base flags). Each arm = a delta, cumulative as in spec 2.2.
COMMON = ["--nhard", "24", "--osd-sign-fix", "1", "--cohms", "1", "--cohaudio", "Both", "--kmin", "5", "--osd-corr", "0.05",
          "--ungated", "1", "--cq-ap", "1", "--cohrescand", "1", "--xc-shadow", "0", "--xc-defaults", "1"]
ARMS = {
    # name: (mode, cohfb, late-round, xc-prior, extra)
    "A1": ("two0",   "0", "0", "0", []),                   # primary only: subtraction off, fallback off, XC off
    "A2": ("two1",   "0", "0", "0", []),                   # + residual pass (Normal)
    "A3": ("three0", "1", "0", "0", []),                   # + coherent fallback at today's defaults (Normal)
    "A4": ("three1", "1", "0", "0", []),                   # Deep (adds the third pass)
    "A5": ("three1", "1", "1", "0", []),                   # + late round
    "A6": ("three1", "1", "1", "1", []),                   # + XC = today's station = BASELINE
    "A7": ("three1", "1", "1", "1", ["--nhard", "0"]),     # A6 with OSD off (nhard 0, programme step 2); last --nhard wins in the harness
    "A9": ("three1", "1", "1", "1", ["--threads", "2"]),   # A6 with worker threads capped at 2
}
THREADS_DEFAULT = ["--threads", "8"]                        # the station's resolved thread count in LR-BUILD's arms


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def busy():
    out = subprocess.run(["tasklist"], capture_output=True, text=True).stdout.lower()
    return [n for n in ("openwsfz.daemon", "testhost", "msbuild", "vbcscompiler", "ft8.fitprobe") if n in out]


def process_cpu_s(handle):
    ft = [wintypes.FILETIME() for _ in range(4)]
    ok = ctypes.windll.kernel32.GetProcessTimes(wintypes.HANDLE(int(handle)), *[ctypes.byref(f) for f in ft])
    if not ok:
        raise OSError("GetProcessTimes failed")
    val = lambda f: ((f.dwHighDateTime << 32) | f.dwLowDateTime) / 1e7
    return val(ft[2]) + val(ft[3])                          # kernel + user


def main():
    arm, n = sys.argv[1], int(sys.argv[2])
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "run"
    assert arm in ARMS or arm == "A6", "arm must be one of %s" % sorted(ARMS)
    assert SLICE_CYCLES == 240 and WSJTX_DECODES_FULL_SLICE == 9431        # inherited constants as assertions, not prose
    assert sha(BIN + r"\libft8.dll") == PIN, "libft8.dll is not the pin"
    b = busy()
    assert not b, "competing process running: %s" % b

    src = json.load(open(SRC_SEL))
    full = src["runs"][NIGHT]["FULL"]
    i0 = full.index(SLICE_START)
    sel_cycles = full[i0:i0 + n]
    assert len(sel_cycles) == n and n <= SLICE_CYCLES
    warm = full[i0 - 1]                                      # the cycle before the slice primes the callsign table (cold start otherwise)
    out = os.path.join(OUT_ROOT, "%s_%s_n%d" % (tag, arm, n))
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):                                # gitignored scratch; never under a tracked results folder
        os.remove(os.path.join(out, f))
    sel = {"note": "DR-0 slice 40 first %d cycles" % n, "run": NIGHT, "runs": {NIGHT: {"warmup": warm, "FULL": sel_cycles}},
           "outage_dropped": src.get("outage_dropped", [])}
    selp = os.path.join(out, "sel.json")
    json.dump(sel, open(selp, "w"))

    mode, cohfb, late, xc, extra = ARMS[arm]
    g = ART + "\\%s_endurance_run-gathered" % NIGHT
    args = [BIN + r"\Ft8.FitProbe.exe", "--selection", selp, "--run", NIGHT, "--stratum", "FULL", "--wav-root", ART,
            "--wav-dir", g + r"\owsfz\wav", "--out", out + r"\run.csv", "--log", out + r"\log.log", "--mode", mode,
            "--cohfb", cohfb, "--late-round", late, "--xc-prior", xc] + COMMON + THREADS_DEFAULT + extra + [
            "--xc-out", out + r"\xc.csv", "--xc-probe-out", out + r"\probe.csv", "--cohfb-out", out + r"\coh.csv",
            "--label", "dr0:%s" % arm, "--wsjtx-alltxt", g + r"\wsjt-x\ALL.TXT", "--matched-out", out + r"\matched.csv",
            "--outcomes", out + r"\outcomes.csv", "--nc-dump", out + r"\nc.tsv", "--testb-out", out + r"\testb.csv",
            "--matched-batch-out", out + r"\matchedbatch.csv", "--third-out", out + r"\third.csv",
            "--abandon-out", out + r"\abandon.csv", "--late-out", out + r"\late.csv"]
    t0 = time.time()
    p = subprocess.Popen(args, stdout=open(out + r"\stdout.txt", "w"), stderr=subprocess.STDOUT)
    p.wait()
    wall = time.time() - t0
    cpu = process_cpu_s(p._handle)
    assert sha(BIN + r"\libft8.dll") == PIN, "dll changed during the arm"

    ours = matched = 0
    seen = set()
    with open(out + r"\nc.tsv", encoding="utf-8", errors="replace") as fh:   # read by code only (HK-037); no text leaves this block
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) < 11:
                continue
            key = (c[0], c[10])
            if key in seen:
                continue
            seen.add(key)
            ours += 1
            matched += 1 if c[2] == "1" else 0
    stamps = set(sel_cycles)
    w_slice = 0
    with open(g + r"\wsjt-x\ALL.TXT", encoding="utf-8", errors="replace") as fh:   # counts per stamp only (HK-037)
        for line in fh:
            if line[:13] in stamps:
                w_slice += 1
    if n == SLICE_CYCLES:
        assert w_slice == WSJTX_DECODES_FULL_SLICE, "ALL.TXT count %d differs from test-set.md" % w_slice
    last, abandoned_cycles = [], 0
    with open(out + r"\run.csv", newline="") as fh:
        for row in csv.DictReader(fh):
            tbs = [float(row[k]) for k in row if k.startswith("tb") and k.endswith("_ms") and row[k] not in ("", None)]
            last.append(max(tbs) if tbs else -1.0)
    with open(out + r"\abandon.csv", newline="") as fh:
        for row in csv.DictReader(fh):
            if int(row["abandoned"] or 0) > 0 or int(row["contained"] or 0) > 0:
                abandoned_cycles += 1
    last.sort()
    p95 = last[min(len(last) - 1, int(0.95 * len(last)))] if last else -1.0
    res = {"arm": arm, "tag": tag, "cycles": n, "rc": p.returncode, "wall_s": round(wall, 1), "cpu_total_s": round(cpu, 1),
           "cpu_s_per_cycle": round(cpu / n, 3), "last_p95_ms": round(p95), "abandoned_cycles": abandoned_cycles,
           "ours": ours, "matched": matched, "wsjtx_decodes": w_slice,
           "rate_pct": round(100.0 * matched / w_slice, 3), "ours_only_pct": round(100.0 * (ours - matched) / w_slice, 3),
           "flags": " ".join(a for a in args[1:] if not a.startswith(("D:", "C:")) and not a.startswith("\\")), "bin_pin": PIN[:16]}
    json.dump(res, open(out + r"\arm.json", "w"), indent=1)
    print(json.dumps(res))


if __name__ == "__main__":
    main()
