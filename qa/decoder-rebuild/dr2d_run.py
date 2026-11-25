#!/usr/bin/env python3
"""DR-2 step 2d replay runner (decoder rebuild, spec-dr2-lean-decoder.md section 1): the lean engine on Slice 40, scored exactly as DR-0's A6 was.

  python -I dr2d_run.py <arm L1|L2> <n_cycles> [--tag pilot]
  L1 = lean, effort normal (the T1 to T4 measurement); L2 = lean, effort fast (informational only).

Replays the first <n_cycles> of Slice 40 (test-set.md) through the QA replay harness (Ft8.FitProbe.exe = Replay81 built with HasLean over
feat/lean-2d 6c746029) with the arm's configuration, measures the harness process's CPU seconds (user + kernel, read from the process
handle after exit) and scores it with the same code as dr0_run.py. Aggregates only go to stdout and arm.json; the text-bearing nc.tsv stays
under _qa-scratch (HK-037, KEEP). Refuses to run when a competing process is up or the binary is not the pinned build (HK-022).
The lean engine ignores the classic keys that are passed (cohfb, late-round, threads, xc-defaults); it reads the audio mode, ungated,
residual candidates, cq-ap and the cross-cycle settings, which are the same flags as A6's.
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
BIN = SC + r"\dr2d-replay\bin_lean"                       # harness over feat/lean-2d 6c746029, built with HasLean
PIN = "7f0e36d2da93d299783edab6b66934ea79d2453a6e479cee00bad934d23e9108"   # libft8.dll of 6c746029 (shim 20260076): the Developer's report, re-hashed by QA
NIGHT = "20261114_2312"
SRC_SEL = SC + r"\xc-live-free\sel_full.json"
SLICE_START = "261115_072930"
SLICE_CYCLES = 240
SLICE_CYCLES_USED = 170                                    # DR-0's length (dr0-result.md): the bars are only comparable at this n
WSJTX_DECODES_FULL_SLICE = 9431                            # test-set.md: ALL.TXT lines stamped inside the 240-cycle window
WSJTX_DECODES_170 = 6773                                   # dr0-result.md line 7: the same count for the 170 cycles DR-0 used
OUT_ROOT = SC + r"\dr2d"
TE = "3.076041980658299"                                   # XC frozen threshold, as the station's config (readback line)

# DR-0's A6 baseline (dr0-result.md line 44, Slice 40, 170 cycles) and the plan's bars (spec-dr2-lean-decoder.md section 1), as assertions in the code (HK-038).
A6 = {"cpu_net": 25.247, "rate": 84.39, "ours_only": 3.77, "last_p95": 7332}
BARS = {"T1_cpu_max": 6.31, "T2_rate_min": 83.39, "T3_ours_only_max": 4.27, "T4_p95_max_ms": 3000}
assert abs(A6["cpu_net"] * 0.25 - BARS["T1_cpu_max"]) < 0.01
assert abs((A6["rate"] - 1.00) - BARS["T2_rate_min"]) < 0.01
assert abs((A6["ours_only"] + 0.50) - BARS["T3_ours_only_max"]) < 0.01

# A6's flags unchanged (the classic keys are ignored by the lean engine); --threads 8 is the subtraction thread key, also ignored by lean.
COMMON = ["--nhard", "24", "--osd-sign-fix", "1", "--cohms", "1", "--cohaudio", "Both", "--kmin", "5", "--osd-corr", "0.05",
          "--ungated", "1", "--cq-ap", "1", "--cohrescand", "1", "--xc-shadow", "0", "--xc-defaults", "1"]
ARMS = {
    "L1": ["--engine", "lean", "--lean-threads", "2", "--effort", "normal"],
    "L2": ["--engine", "lean", "--lean-threads", "2", "--effort", "fast"],
}
THREADS_DEFAULT = ["--threads", "8"]


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
    assert arm in ARMS, "arm must be one of %s" % sorted(ARMS)
    assert SLICE_CYCLES == 240 and WSJTX_DECODES_FULL_SLICE == 9431 and WSJTX_DECODES_170 == 6773   # inherited constants as assertions, not prose
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
    sel = {"note": "DR-2d slice 40 first %d cycles" % n, "run": NIGHT, "runs": {NIGHT: {"warmup": warm, "FULL": sel_cycles}},
           "outage_dropped": src.get("outage_dropped", [])}
    selp = os.path.join(out, "sel.json")
    json.dump(sel, open(selp, "w"))

    g = ART + "\\%s_endurance_run-gathered" % NIGHT
    args = [BIN + r"\Ft8.FitProbe.exe", "--selection", selp, "--run", NIGHT, "--stratum", "FULL", "--wav-root", ART,
            "--wav-dir", g + r"\owsfz\wav", "--out", out + r"\run.csv", "--log", out + r"\log.log", "--mode", "three1",
            "--cohfb", "1", "--late-round", "1", "--xc-prior", "1"] + COMMON + THREADS_DEFAULT + ARMS[arm] + [
            "--xc-out", out + r"\xc.csv", "--xc-probe-out", out + r"\probe.csv", "--cohfb-out", out + r"\coh.csv",
            "--label", "dr2d:%s" % arm, "--wsjtx-alltxt", g + r"\wsjt-x\ALL.TXT", "--matched-out", out + r"\matched.csv",
            "--outcomes", out + r"\outcomes.csv", "--nc-dump", out + r"\nc.tsv", "--testb-out", out + r"\testb.csv",
            "--matched-batch-out", out + r"\matchedbatch.csv", "--third-out", out + r"\third.csv",
            "--abandon-out", out + r"\abandon.csv", "--late-out", out + r"\late.csv", "--lean-out", out + r"\lean.csv"]
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
    if n == SLICE_CYCLES_USED:
        assert w_slice == WSJTX_DECODES_170, "ALL.TXT count %d differs from dr0-result.md" % w_slice
    last, abandoned_cycles = [], 0
    with open(out + r"\run.csv", newline="") as fh:
        for row in csv.DictReader(fh):
            tbs = [float(row[k]) for k in row if k.startswith("tb") and k.endswith("_ms") and row[k] not in ("", None)]
            last.append(max(tbs) if tbs else -1.0)
    # The lean engine's own per-cycle line: abandoned flag, native error, S3 CPU split (counts and ms only).
    lean_rows = parse_failed = err_cycles = 0
    s3_cpu = fit_cpu = 0.0
    with open(out + r"\lean.csv", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("abandoned") == "parse-failed" or row.get("error") is None:
                parse_failed += 1
                continue
            lean_rows += 1
            if int(row["abandoned"]) > 0:
                abandoned_cycles += 1
            if int(row["error"]) != 0:
                err_cycles += 1
            s3_cpu += float(row["s3_cpu_ms"])
            fit_cpu += float(row["fit_cpu_ms"])
    last.sort()
    p95 = last[min(len(last) - 1, int(0.95 * len(last)))] if last else -1.0
    res = {"arm": arm, "tag": tag, "cycles": n, "rc": p.returncode, "wall_s": round(wall, 1), "cpu_total_s": round(cpu, 1),
           "cpu_s_per_cycle": round(cpu / n, 3), "last_p95_ms": round(p95), "abandoned_cycles": abandoned_cycles,
           "ours": ours, "matched": matched, "wsjtx_decodes": w_slice,
           "rate_pct": round(100.0 * matched / w_slice, 3), "ours_only_pct": round(100.0 * (ours - matched) / w_slice, 3),
           "lean_rows": lean_rows, "lean_parse_failed": parse_failed, "lean_error_cycles": err_cycles,
           "s3_cpu_s_per_cycle": round(s3_cpu / 1000.0 / n, 3), "fit_cpu_s_per_cycle": round(fit_cpu / 1000.0 / n, 3),
           "flags": " ".join(a for a in args[1:] if not a.startswith(("D:", "C:")) and not a.startswith("\\")), "bin_pin": PIN[:16]}
    if n == SLICE_CYCLES_USED:
        res["bars"] = {"T1": res["cpu_s_per_cycle"] <= BARS["T1_cpu_max"], "T2": res["rate_pct"] >= BARS["T2_rate_min"],
                       "T3": res["ours_only_pct"] <= BARS["T3_ours_only_max"],
                       "T4": res["last_p95_ms"] <= BARS["T4_p95_max_ms"] and abandoned_cycles == 0}
    json.dump(res, open(out + r"\arm.json", "w"), indent=1)
    print(json.dumps(res))


if __name__ == "__main__":
    main()
