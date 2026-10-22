#!/usr/bin/env python
"""OLD-CPU SPEED step 0 driver (QA tooling; spec 2026-10-13-1630-architect-to-qa-spec-old-cpu-profile.md + amendment 1). Runs on `sol`.

    python old_cpu_profile.py --stage smoke|profile|scaling --bin <profile build dir> --corpus <frozen corpus> \
        --first-run <first-run pass dir> --scratch <job dir OUTSIDE git> --jit-wav <synthetic wav> [--blocks 9dbe42bc46d9,822498b61291]

  smoke    2 scored cycles of block 822498b61291 under perf; checks the perf map is written and prints the frame vocabulary (OC-V2 early)
  profile  both blocks, leg A, whole block, `perf record -F 499 -g`; phase split, kiss_fft/trig shares, top-15 self symbols, wall overhead,
           fitted signals per cycle, OC-V1 (decodes equal to the first run's leg A, >= 99.9 % both ways), OC-V2 (unresolved <= 10 %),
           OC-V3 (0 abandonments), OC-V4 (.so SHA equal at start and end and equal to the profile pin)
  scaling  4b: block 822498b61291, the first 8 scored cycles (index 8:8), NO warm-up, no perf, subtractionMaxThreads 1 / 4 / 8;
           residual-pass median per setting, speed-ups and the Amdahl parallel fraction

Settings are the first run's: budget unlimited, nhard 24, OSD sign fix on, subtraction on. ONE decode process at a time; refuses to start while
another job is on. Aggregates only; the working files (message text) stay under --scratch and are deleted at job close (HK-037).
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "corpus"))
import perf_phase_split as PS  # noqa: E402
import refset_score as rs  # noqa: E402

NHARD, SIGN_FIX = 24, 1
SAMPLE_HZ = 499
BLOCK_SLOW, BLOCK_MEDIAN = "9dbe42bc46d9", "822498b61291"
OC1_BAR = 0.999            # OC-V1: decodes equal to the first run's, share both ways (spec: >= 99.9 %)
OC2_BAR = 10.0             # OC-V2: unresolved samples <= 10 % of on-CPU samples per block
THREAD_SETTINGS = (1, 4, 8)
SCALING_RANGE = "8:8"      # 4b: the first 8 scored cycles (indices 8..15), no warm-up (the W pilot: history changes only hashed rendering)
BUSY = "run_refset|run_leg_e|OpenWSFZ.Daemon|aplay|bin/wsjtx|bin/jt9|queue_|RefSet.dll"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def amdahl_parallel_fraction(t_ref: float, t_n: float, n_ref: int, n: int):
    """Parallel fraction p from two timings: T(n) = T1 ((1 - p) + p / n)  =>  T(n)/T(ref) = ((1-p) + p/n) / ((1-p) + p/ref). Solved for p."""
    if t_ref <= 0 or t_n <= 0 or n == n_ref:
        return None
    r = t_n / t_ref
    # r * (1 - p + p/ref) = 1 - p + p/n   =>   p * (r*(1/ref - 1) - (1/n - 1)) = 1 - r
    den = r * (1.0 / n_ref - 1.0) - (1.0 / n - 1.0)
    return None if abs(den) < 1e-12 else (1.0 - r) / den


def median(v):
    v = [x for x in v if x is not None and x >= 0]
    return statistics.median(v) if v else None


def busy() -> bool:
    return subprocess.run(["pgrep", "-f", BUSY], capture_output=True, text=True).stdout.strip() != ""


def oc_v1(first_run_tsv: str, new_tsv: str, scored: list) -> dict:
    """Leg-A decodes of the profile build against the first run's, non-hashed, sm_01 key (refset_score's own scorer)."""
    r = rs.score_block(rs.read_work(first_run_tsv), rs.read_work(new_tsv), scored)
    r.pop("_per_cycle", None)
    sh = rs.rsv2_shares(r["counts"])
    ok = sh["repro_nonhashed_share"] >= OC1_BAR and sh["extra_nonhashed_share"] <= 1 - OC1_BAR
    return {"result": "PASS" if ok else "FAIL", "reproduced_share": round(sh["repro_nonhashed_share"], 5), "extra_share": round(sh["extra_nonhashed_share"], 5), "bar": OC1_BAR}


def harness_cmd(a, block: str, pass_name: str, threads: int, cycle_range: str | None) -> list:
    cmd = ["dotnet", os.path.join(a.bin, "RefSet.dll"), "--manifest", os.path.join(a.corpus, "manifest.json"), "--corpus", a.corpus, "--block", block,
           "--leg", "A", "--out-dir", a.scratch, "--pass", pass_name, "--jit-wav", a.jit_wav, "--nhard", str(NHARD), "--osd-sign-fix", str(SIGN_FIX),
           "--threads", str(threads), "--label", "old-cpu profile build"]
    return cmd + (["--cycle-range", cycle_range] if cycle_range else [])


def run_one(a, block: str, pass_name: str, threads: int, cycle_range: str | None, perf: bool) -> dict:
    env = dict(os.environ, OPENWSFZ_SUBTRACTION_BUDGET="unlimited", DOTNET_PerfMapEnabled="1" if perf else "0")
    cmd = harness_cmd(a, block, pass_name, threads, cycle_range)
    perf_data = os.path.join(a.scratch, pass_name + ".perf.data")
    if perf:
        cmd = ["perf", "record", "-F", str(SAMPLE_HZ), "-g", "-o", perf_data, "--"] + cmd
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    wall = time.time() - t0
    if p.returncode != 0:
        raise SystemExit("FAILED rc=%d: %s" % (p.returncode, (p.stderr or p.stdout).strip()[-300:]))
    s = rs.load_json(os.path.join(a.scratch, pass_name, "A", block + ".json"))
    return {"summary": s, "driver_wall_s": round(wall, 1), "perf_data": perf_data if perf else None}


def perf_report(a, pass_name: str, perf_data: str, vocab: int = 0) -> dict:
    dump = os.path.join(a.scratch, pass_name + ".perf.dump")
    with open(dump, "w") as fh:
        subprocess.run(["perf", "script", "-i", perf_data, "-F", "ip,sym,dso"], stdout=fh, stderr=subprocess.DEVNULL, check=True)
    with open(dump, encoding="utf-8", errors="replace") as fh:
        res = PS.summarise(PS.parse_dump(fh), vocab_n=vocab)
    res["perf_data_bytes"] = os.path.getsize(perf_data)
    res["perf_dump_bytes"] = os.path.getsize(dump)
    return res


def first_run_numbers(a, block: str) -> dict:
    s = rs.load_json(os.path.join(a.first_run, "A", block + ".json"))
    pins = [json.loads(x) for x in open(os.path.join(a.first_run, "pins.jsonl")) if x.strip()]
    wall = [p["wall_s"] for p in pins if p.get("leg") == "A" and p.get("block") == block]
    return {"wall_s": wall[-1] if wall else s.get("wall_s"), "cpu_s": s.get("cpu_s"),
            "residual_ms_median": median([c["residual_ms"] for c in s["cycles"] if c["scored"]])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["smoke", "profile", "scaling"])
    ap.add_argument("--bin", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--first-run", required=True)
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--jit-wav", required=True)
    ap.add_argument("--blocks", default=BLOCK_SLOW + "," + BLOCK_MEDIAN)
    a = ap.parse_args()
    os.makedirs(a.scratch, exist_ok=True)
    if busy():
        raise SystemExit("REFUSED: another job is on this machine (one decode process at a time)")
    so = os.path.join(a.bin, "libft8.so")
    pin = open(os.path.join(os.path.dirname(a.bin.rstrip("/")), "PIN.txt")).read().split()[0] if os.path.exists(os.path.join(os.path.dirname(a.bin.rstrip("/")), "PIN.txt")) else None
    sha0 = sha256(so)
    if pin and sha0 != pin:
        raise SystemExit("PIN FAILED: libft8.so %s != PIN.txt %s" % (sha0, pin))
    out = {"stage": a.stage, "started_utc": now(), "profile_so_sha256": sha0, "pin_file": pin, "settings": {"budget": "unlimited", "nhard": NHARD, "osd_sign_fix": SIGN_FIX, "sample_hz": SAMPLE_HZ},
           "host_load_before": os.getloadavg()}
    manifest = rs.load_json(os.path.join(a.corpus, "manifest.json"))
    by_id = {b["id"]: b for b in manifest["blocks"]}

    if a.stage == "smoke":
        r = run_one(a, BLOCK_MEDIAN, "smoke", 8, "8:2", True)
        maps = [m for m in glob.glob("/tmp/perf-*.map") if os.path.getmtime(m) >= time.time() - 600]
        rep = perf_report(a, "smoke", r["perf_data"], vocab=80)
        out.update({"perf_map_files_written": len(maps), "report": rep, "residual_ms": [c["residual_ms"] for c in r["summary"]["cycles"]],
                    "fitted": [c.get("fitted") for c in r["summary"]["cycles"]], "unresolved_pct": rep["phase_pct"]["unresolved"]})
    elif a.stage == "profile":
        out["blocks"] = {}
        for block in a.blocks.split(","):
            r = run_one(a, block, "profile-" + block[:6], 8, None, True)
            s = r["summary"]
            rep = perf_report(a, "profile-" + block[:6], r["perf_data"])
            scored = rs.block_scored_stamps(by_id[block])
            fr = first_run_numbers(a, block)
            cyc = [c for c in s["cycles"] if c["scored"]]
            sha1 = sha256(so)
            out["blocks"][block] = {
                "report": rep, "wall_s": s["wall_s"], "cpu_s": s["cpu_s"], "first_run": fr,
                "wall_overhead_vs_first_run_pct": round(100.0 * (s["wall_s"] / fr["wall_s"] - 1.0), 1) if fr["wall_s"] else None,
                "residual_ms_median": median([c["residual_ms"] for c in cyc]), "residual_ms_max": max(c["residual_ms"] for c in cyc),
                "fitted_signals_per_cycle": {"median": median([c.get("fitted") for c in cyc]), "max": max((c.get("fitted") or 0) for c in cyc), "total": sum(max(0, c.get("fitted") or 0) for c in cyc)},
                "parallel_tail": "longest single-fit wall NOT measured (no instrumentation); fits per cycle and elapsed come from the residual-pass log line",
                "OC-V1": oc_v1(os.path.join(a.first_run, "A", block + ".decodes.tsv"), os.path.join(a.scratch, "profile-" + block[:6], "A", block + ".decodes.tsv"), scored),
                "OC-V2": {"result": "PASS" if rep["phase_pct"]["unresolved"] <= OC2_BAR else "FAIL", "unresolved_pct": rep["phase_pct"]["unresolved"], "bar_pct": OC2_BAR, "samples": rep["samples"]},
                "OC-V3": {"result": "PASS" if s["residual_pass"]["abandoned"] == 0 else "FAIL", "abandoned": s["residual_pass"]["abandoned"], "ran": s["residual_pass"]["ran"]},
                "OC-V4": {"result": "PASS" if s["native_sha256_start"] == s["native_sha256_end"] == sha0 == sha1 else "FAIL", "start": s["native_sha256_start"], "end": s["native_sha256_end"]}}
    else:
        runs = {}
        for n in THREAD_SETTINGS:
            r = run_one(a, BLOCK_MEDIAN, "scaling-t%d" % n, n, SCALING_RANGE, False)
            s = r["summary"]
            cyc = s["cycles"]
            runs[n] = {"residual_ms_median": median([c["residual_ms"] for c in cyc]), "wall_s": s["wall_s"], "cpu_s": s["cpu_s"], "cycles": len(cyc),
                       "threads_configured": s["readback_start"].get("threadsConfigured"), "cores": s["readback_start"].get("cores"),
                       "abandoned": s["residual_pass"]["abandoned"], "fitted_median": median([c.get("fitted") for c in cyc]),
                       "decode_rows_sha": hashlib.sha256(open(os.path.join(a.scratch, "scaling-t%d" % n, "A", BLOCK_MEDIAN + ".decodes.tsv"), "rb").read()).hexdigest()[:16]}
        t = {n: runs[n]["residual_ms_median"] for n in runs}
        out["runs"] = runs
        out["speedup"] = {"4_vs_1": round(t[1] / t[4], 3), "8_vs_4": round(t[4] / t[8], 3), "8_vs_1": round(t[1] / t[8], 3)}
        out["amdahl_parallel_fraction"] = {"from_1_to_4": amdahl_parallel_fraction(t[1], t[4], 1, 4), "from_1_to_8": amdahl_parallel_fraction(t[1], t[8], 1, 8),
                                           "from_4_to_8": amdahl_parallel_fraction(t[4], t[8], 4, 8)}
        out["decode_rows_equal_across_thread_settings"] = len({runs[n]["decode_rows_sha"] for n in runs}) == 1
        out["no_warmup_note"] = "cycle indices %s of the block, no warm-up cycles (the W pilot: history changes only the rendering of hashed calls)" % SCALING_RANGE
    out["finished_utc"] = now()
    out["so_sha256_end"] = sha256(so)
    with open(os.path.join(a.scratch, "RESULT-%s.json" % a.stage), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k not in ("blocks", "report", "runs")}, indent=1)[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
