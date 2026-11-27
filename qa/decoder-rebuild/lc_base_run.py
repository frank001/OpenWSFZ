#!/usr/bin/env python3
"""LC-BASE runner (spec-lc-base-lean-vs-classic.md): classic (arm C = DR-0's A6) and lean (arm L = DR-2e's L5) on one slice, scored as DR-0 was.

  python -I lc_base_run.py <slice S40|H40|H20> <arm C|L> <n_cycles> [--tag pilot]

One build for both arms (harness over main 546ad125, HasLean): the engine is chosen per run with --engine. Arm C = dr0_run.py's A6 flags exactly
(--mode three1 --cohfb 1 --late-round 1 --xc-prior 1, COMMON, --threads 8) plus --engine classic (required by a HasLean harness); arm L = dr2d_run.py's L5
(the same flags plus --engine lean --lean-threads 16 --effort normal). Aggregates go to stdout and arm.json; the text-bearing nc.tsv stays under _qa-scratch
(HK-037, KEEP). Refuses to run when a competing process is up or the dll is not the pin (HK-022); S40 is replayed here ONLY for the 10-cycle reproduction check.
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
BIN = SC + r"\lc-base\bin"                                 # Ft8.FitProbe.exe over main 546ad125, built with HasLean
PIN = "eab11ec9a456169b96bde734ef319e8b74555acea4c09f9096661f6082190ea2"   # libft8.dll of main 546ad125 (shim 20260078): same file as fc4fb788 / 9027616e
OUT_ROOT = SC + r"\lc-base\runs"
SRC_SEL_S40 = SC + r"\xc-live-free\sel_full.json"

SLICES = {
    # name: (night label for --run, artefacts folder, selection source, start stamp or None = the file's own list)
    "S40": ("20261114_2312", "20261114_2312_endurance_run-gathered", SRC_SEL_S40, "261115_072930"),
    "H40": ("20261028_2233", "20261028_2233_endurance_run-gathered", SC + r"\lc-base\sel_H40.json", None),
    "H20": ("20260808_live_run_0016-8080", "20260808_live_run_0016-8080", SC + r"\lc-base\sel_H20.json", None),
}
# DR-0's A6 for the first 10 cycles of S40 is checked by the caller against a 10-cycle C run; the 170-cycle A6 numbers are asserted here as inherited constants.
A6_170 = {"cpu_net": 25.247, "rate": 84.39, "ours_only": 3.77, "last_p95": 7332, "wsjtx": 6773}
L5_170 = {"cpu_net": 13.405, "rate": 81.515, "ours_only": 3.824, "last_p95": 2053}
assert A6_170["wsjtx"] == 6773 and abs(L5_170["rate"] - 81.515) < 1e-9

COMMON = ["--nhard", "24", "--osd-sign-fix", "1", "--cohms", "1", "--cohaudio", "Both", "--kmin", "5", "--osd-corr", "0.05",
          "--ungated", "1", "--cq-ap", "1", "--cohrescand", "1", "--xc-shadow", "0", "--xc-defaults", "1"]
THREADS_C = ["--threads", "8"]                              # A6's thread count
ARMS = {
    "C": ["--engine", "classic"],
    "L": ["--engine", "lean", "--lean-threads", "16", "--effort", "normal"],
}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def busy():
    out = subprocess.run(["tasklist"], capture_output=True, text=True).stdout.lower()
    return [n for n in ("openwsfz.daemon", "testhost", "msbuild", "vbcscompiler", "ft8.fitprobe") if n in out]


def process_cpu_s(handle):
    ft = [wintypes.FILETIME() for _ in range(4)]
    if not ctypes.windll.kernel32.GetProcessTimes(wintypes.HANDLE(int(handle)), *[ctypes.byref(f) for f in ft]):
        raise OSError("GetProcessTimes failed")
    val = lambda f: ((f.dwHighDateTime << 32) | f.dwLowDateTime) / 1e7
    return val(ft[2]) + val(ft[3])                          # kernel + user


def main():
    sl, arm, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "run"
    assert sl in SLICES and arm in ARMS
    global BIN, PIN
    if "--bin" in sys.argv:                                  # a later build (DR-3 replay): --bin <harness dir> --pin <libft8.dll sha256>
        BIN = sys.argv[sys.argv.index("--bin") + 1]
        PIN = sys.argv[sys.argv.index("--pin") + 1]
    night, folder, selsrc, start = SLICES[sl]
    assert sha(BIN + r"\libft8.dll") == PIN, "libft8.dll is not the pin"
    b = busy()
    assert not b, "competing process running: %s" % b

    src = json.load(open(selsrc))
    key = night if night in src["runs"] else list(src["runs"])[0]
    full = src["runs"][key]["FULL"]
    if start is not None:
        i0 = full.index(start)
        warm = full[i0 - 1]
        cycles = full[i0:i0 + n]
    else:
        warm = src["runs"][key]["warmup"]
        cycles = full[:n]
    assert len(cycles) == n and n <= 240
    out = os.path.join(OUT_ROOT, "%s_%s_%s_n%d" % (tag, sl, arm, n))
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        os.remove(os.path.join(out, f))
    sel = {"note": "LC-BASE %s first %d cycles" % (sl, n), "run": night, "runs": {night: {"warmup": warm, "FULL": cycles}}, "outage_dropped": []}
    selp = os.path.join(out, "sel.json")
    json.dump(sel, open(selp, "w"))

    g = os.path.join(ART, folder)
    args = [BIN + r"\Ft8.FitProbe.exe", "--selection", selp, "--run", night, "--stratum", "FULL", "--wav-root", ART,
            "--wav-dir", g + r"\owsfz\wav", "--out", out + r"\run.csv", "--log", out + r"\log.log", "--mode", "three1",
            "--cohfb", "1", "--late-round", "1", "--xc-prior", "1"] + COMMON + THREADS_C + ARMS[arm] + [
            "--xc-out", out + r"\xc.csv", "--xc-probe-out", out + r"\probe.csv", "--cohfb-out", out + r"\coh.csv",
            "--label", "lcbase:%s:%s" % (sl, arm), "--wsjtx-alltxt", g + r"\wsjt-x\ALL.TXT", "--matched-out", out + r"\matched.csv",
            "--outcomes", out + r"\outcomes.csv", "--nc-dump", out + r"\nc.tsv", "--testb-out", out + r"\testb.csv",
            "--matched-batch-out", out + r"\matchedbatch.csv", "--third-out", out + r"\third.csv",
            "--abandon-out", out + r"\abandon.csv", "--late-out", out + r"\late.csv", "--lean-out", out + r"\lean.csv"]
    if "--probe" in sys.argv:                                # SUB-PROBE (feat/sub-probe): the harness build must have HasProbe; probe.tsv = numbers only
        assert arm == "L"
        args += ["--lean-probe", "1", "--probe-out", out + r"\probe.tsv"]
    t0 = time.time()
    p = subprocess.Popen(args, stdout=open(out + r"\stdout.txt", "w"), stderr=subprocess.STDOUT)
    p.wait()
    wall = time.time() - t0
    cpu = process_cpu_s(p._handle)
    assert sha(BIN + r"\libft8.dll") == PIN, "dll changed during the run"

    ours = matched = 0
    seen = set()
    with open(out + r"\nc.tsv", encoding="utf-8", errors="replace") as fh:   # read by code only (HK-037); no text leaves this block
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) < 11:
                continue
            k = (c[0], c[10])
            if k in seen:
                continue
            seen.add(k)
            ours += 1
            matched += 1 if c[2] == "1" else 0
    stamps = set(cycles)
    w_slice = 0
    with open(g + r"\wsjt-x\ALL.TXT", encoding="utf-8", errors="replace") as fh:   # counts per stamp only (HK-037)
        for line in fh:
            if line[:13] in stamps:
                w_slice += 1
    if sl == "S40" and n == 170:
        assert w_slice == A6_170["wsjtx"]
    last, abandoned_cycles = [], 0
    with open(out + r"\run.csv", newline="") as fh:
        for row in csv.DictReader(fh):
            tbs = [float(row[k]) for k in row if k.startswith("tb") and k.endswith("_ms") and row[k] not in ("", None)]
            last.append(max(tbs) if tbs else -1.0)
    if arm == "C":
        with open(out + r"\abandon.csv", newline="") as fh:
            for row in csv.DictReader(fh):
                if int(row["abandoned"] or 0) > 0 or int(row["contained"] or 0) > 0:
                    abandoned_cycles += 1
    else:
        lean_rows = err_cycles = parse_failed = 0
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
    last.sort()
    p95 = last[min(len(last) - 1, int(0.95 * len(last)))] if last else -1.0
    res = {"slice": sl, "arm": arm, "tag": tag, "cycles": n, "first_cycle": cycles[0], "last_cycle": cycles[-1], "rc": p.returncode,
           "wall_s": round(wall, 1), "cpu_total_s": round(cpu, 1), "cpu_s_per_cycle": round(cpu / n, 3), "last_p95_ms": round(p95),
           "last_median_ms": round(last[len(last) // 2]) if last else -1, "last_max_ms": round(last[-1]) if last else -1,
           "abandoned_cycles": abandoned_cycles, "ours": ours, "matched": matched, "wsjtx_decodes": w_slice,
           "rate_pct": round(100.0 * matched / w_slice, 3), "ours_only_pct": round(100.0 * (ours - matched) / w_slice, 3),
           "flags": " ".join(a for a in args[1:] if not a.startswith(("D:", "C:")) and not a.startswith("\\")), "bin_pin": PIN[:16]}
    if arm == "L":
        res.update({"lean_rows": lean_rows, "lean_parse_failed": parse_failed, "lean_error_cycles": err_cycles})
    json.dump(res, open(out + r"\arm.json", "w"), indent=1)
    print(json.dumps(res))


if __name__ == "__main__":
    main()
