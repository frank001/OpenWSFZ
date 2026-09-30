#!/usr/bin/env python
"""SUB-FEAS pre-arm check: the REAL residual pass at subtractionMaxThreads = 8 on the 161 E1 cycles (Architect, 2026-09-30).

Why: the Stage B fit profile showed throughput peaks at 12 workers and 14 is slightly worse; 8 (the physical core count) gives
~82 % of peak and leaves 8 logical processors for WSJT-X/jt9. The Captain prefers running tonight on half the threads; the Architect
advised 8, provided this check passes first. The prediction (waves x per-fit wall: ~7.6 s for up to 32 signals) is from isolated fits;
this run tests the real pass.

PRE-REGISTERED BAR (Architect's ruling, fixed before the run; thresholds are constants below, NOT tuned):
  PASS iff  (1) 0 deadline abandons over the 161 cycles,  AND  (2) max whole-call <= 13 000 ms,
            (3) 0 access violations / 0 contained exceptions / 0 CSV rows with an exception.
  Reported with it (no bar): p50/p95/max of the whole call, of the time to batch 1 and of the residual pass elapsedMs; the
  residual-decode total (a sanity check: at 0 abandons it must equal the Stage A E3 baseline of 795, because the fits are bit-identical
  to Stage A regardless of the thread count); the same cycles' numbers at 14 workers where they exist (S2 H/M strata), descriptive.
  If (1) or (2) fails: fall back to 12 workers with the same check; do not loosen the bar.

Build: 247ac391 (two-stage), libft8.dll ee00d118...; harness mode two1 (flag ON, DecodeTwoStageAsync, ONE call per cycle, the production
path); --threads 8 sets decoder.subtractionMaxThreads via SetSubtractionMaxThreads. WSJT-X closed (asserted).
HK-037: stamps, integers, timings only.
"""
import csv
import ctypes
import json
import math
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay81_run as R
import replay81_rows as B

REPO = R.REPO
ART = R.ART
OUT = os.path.join(ART, "sub_feas_threads8")
R.OUT = OUT
THREADS = int(os.environ.get("SUBFEAS_THREADS", "8"))
DERIVED = os.path.join(ART, "sub_feas_stage_a_e3_baseline", "e1_derived_selection.json")
HOUT = r"C:\Users\Frank\w-testb-out"
DLL = "ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c"
E3_BASELINE_RESIDUAL = 795   # Stage A, 14 workers, 161 cycles, 0 abandons (report 2026-09-30-sub-feas-stage-b-baseline)
MAX_WHOLE_CALL_MS = 13_000
GUARDED = ["qa/rr-study/sub-feas/replay81", "qa/rr-study/sub-feas/threads8_run.py"]
RUNS = R.RUNS


def sh(*a, cwd=REPO):
    return subprocess.run(list(a), cwd=cwd, capture_output=True, text=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    R.LOGF = open(os.path.join(OUT, "orchestrator.log"), "a", encoding="utf-8")
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    R.log(f"orchestrator start (threads={THREADS})")
    assert sh("git", "check-ignore", "-q", os.path.join(OUT, "x")).returncode == 0
    assert sh("git", "ls-files", "--", OUT).stdout.strip() == ""
    assert R.sha256(os.path.join(HOUT, "libft8.dll")) == DLL, "DLL pin mismatch"
    assert sh("git", "status", "--porcelain", "--", *GUARDED).stdout.strip() == "", "harness/script not committed"
    ps = subprocess.run(["powershell", "-NoProfile", "-Command",
                         "(Get-Process | Where-Object { $_.ProcessName -match '^(wsjtx|jt9|OpenWSFZ)' } | "
                         "Select-Object -ExpandProperty ProcessName) -join ','"], capture_output=True, text=True).stdout.strip()
    if os.environ.get("ANALYSE_ONLY") != "1":
        assert ps == "", ("WSJT-X / jt9 / OpenWSFZ is running", ps)
    json.dump({"utc": R.now(), "threads": THREADS, "libft8_sha256": DLL, "build": "247ac391",
               "harness_commit": sh("git", "rev-parse", "HEAD").stdout.strip(),
               "harness_dll_sha256": R.sha256(os.path.join(HOUT, "Replay81.dll"))},
              open(os.path.join(OUT, "preflight.json"), "w"), indent=1)
    if os.environ.get("ANALYSE_ONLY") != "1":
        R.env_snapshot("env_start.txt")

    per = {}
    for run in RUNS:
        R.status("RUN", run=run, threads=THREADS)
        csvp = os.path.join(OUT, f"run_{run}.csv")
        logp = os.path.join(OUT, f"run_{run}.log")
        if os.environ.get("ANALYSE_ONLY") != "1":   # added after the harness runs, before any result was read
            for p in (csvp, logp):
                if os.path.exists(p):
                    os.remove(p)
        cmd = ["dotnet", os.path.join(HOUT, "Replay81.dll"), "--selection", DERIVED, "--run", run, "--stratum", "E1",
               "--wav-root", ART, "--out", csvp, "--log", logp, "--mode", "two1", "--threads", str(THREADS),
               "--label", f"247ac391:t{THREADS}_{run}"]
        if os.environ.get("ANALYSE_ONLY") == "1":
            rc = 0
        else:
            rc = subprocess.run(cmd, capture_output=True, text=True).returncode
        R.log(f"harness run_{run} rc={rc}")
        assert rc == 0
        rows = list(csv.DictReader(open(csvp, newline="")))
        sub, av, cw, other = B.parse_log(logp)
        per[run] = {"rows": rows, "sub": sub, "av": av, "cw": cw}
    if os.environ.get("ANALYSE_ONLY") != "1":
        R.env_snapshot("env_end.txt")

    whole = [float(r["elapsed_ms"]) for run in RUNS for r in per[run]["rows"]]
    tb1 = [float(r["tb1_ms"]) for run in RUNS for r in per[run]["rows"]]
    sub_all = [s for run in RUNS for s in per[run]["sub"]]
    n_ab = sum(1 for s in sub_all if s["abandoned"])
    n_co = sum(1 for s in sub_all if s["contained"])
    av = sum(per[run]["av"] for run in RUNS)
    cw = sum(per[run]["cw"] for run in RUNS)
    exc = sum(1 for run in RUNS for r in per[run]["rows"] if r["exception"])
    residual = sum(s["residual"] for s in sub_all)
    st = lambda v: {"n": len(v), "p50": B.med(v), "p95": B.pct(v, .95), "max": max(v) if v else None}
    res = {"threads": THREADS, "cycles": len(whole), "bar": {"abandons": 0, "max_whole_call_ms": MAX_WHOLE_CALL_MS},
           "whole_call_ms": st(whole), "time_to_batch1_ms": st(tb1), "pass_elapsedMs": st([s["elapsed_ms"] for s in sub_all]),
           "abandoned": n_ab, "contained_lines": n_co, "av_warnings": av, "contained_warnings": cw, "rows_with_exception": exc,
           "log_lines_equal_cycles": len(sub_all) == len(whole),
           "residualDecodes_total": residual, "e3_baseline_residual": E3_BASELINE_RESIDUAL,
           "residual_equals_baseline": residual == E3_BASELINE_RESIDUAL,
           "fittedSignals_max": max((s["fit"] for s in sub_all), default=None)}
    res["PASS"] = (len(whole) == 161 and n_ab == 0 and max(whole) <= MAX_WHOLE_CALL_MS and n_co == 0 and av == 0
                   and cw == 0 and exc == 0)
    json.dump(res, open(os.path.join(OUT, "rows.json"), "w"), indent=1)
    R.status("DONE", PASS=res["PASS"])
    R.log("orchestrator DONE")
    print(json.dumps(res, indent=1))
    return 0 if res["PASS"] else 1


if __name__ == "__main__":
    sys.exit(main())
