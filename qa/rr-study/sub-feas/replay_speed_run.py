#!/usr/bin/env python
"""SUB-FEAS speed-redesign acceptance (Stage A): unattended timing orchestrator (detached, resumable).

Spec: qa/rr-study/2026-09-30-0641-architect-to-qa-spec-sub-feas-speed-redesign.md section 2 + Amendment 1.
Instrument: the section 8.1 harness (Replay81, committed cd36bb42) and the frozen selection.json, with ONE change
to the harness: an optional --threads argument (decoder.subtractionMaxThreads), candidate build only.

Order (spec): E1 first. This script REFUSES to start unless E1 has been run and PASSED (`e1_summary.json`).
Then R0, then timing. This script RUNS and records raw rows; rows R1'..R7 are computed afterwards by
replay_speed_rows.py, so nothing can be tuned while the run is in progress.

Blocks, adjacent in time per (run, stratum) so machine state is shared (Amendment 1, R5' baseline):
  base  = 2b39cf18 DLL, flag OFF only ("off" mode)         -> R5' baseline, re-measured THIS session
  cand  = ca0bcd9b DLL, OFF and ON, order alternated       -> R1'..R4', R5', R7
  R6    = cand, synthetic pair-sum stress, ON only
  T     = cand at --threads 4, stratum H only (report only)

Requirements checked here, not assumed: WSJT-X closed (no wsjtx/jt9 process), every DLL pinned by SHA-256,
harness/orchestrator/rows files committed, output dir gitignored and untracked.

HK-037 / NFR-021: only stamps, counts and timings are read or written. HK-013/019/023: detached, logged,
status.json heartbeat; sleep prevented for the process lifetime.
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay81_run as R  # helpers only: log(), status(), sha256(), env_snapshot(), archived_counts()

REPO = R.REPO
ART = R.ART
OUT = os.path.join(ART, "sub_feas_speed_acceptance")
E1_SUMMARY = os.path.join(ART, "sub_feas_speed_e1", "e1_summary.json")
R.OUT = OUT

BUILDS = {  # label -> (harness output dir, expected libft8.dll sha256)
    "2b39cf18": (r"C:\Users\Frank\w-replay81-out-2b39cf18",
                 "5a6a4dc04a2cf6fbd987c12ce7635a968f4c9b69f73cacebe422af62827e38c5"),
    "ca0bcd9b": (r"C:\Users\Frank\w-speed-out-ca0bcd9b",
                 "ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c"),
    "84cac119": (r"C:\Users\Frank\w-replay81-out-84cac119",
                 "38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba"),
    "51e40b55": (r"C:\Users\Frank\w-replay81-out-51e40b55",
                 "38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba"),
}
RUNS = R.RUNS
PRODUCING_BUILD = R.PRODUCING_BUILD
THREADS_T = "4"
GUARDED_FILES = ["qa/rr-study/sub-feas/replay81", "qa/rr-study/sub-feas/replay81_run.py",
                 "qa/rr-study/sub-feas/replay_speed_run.py", "qa/rr-study/sub-feas/replay_speed_rows.py",
                 "qa/rr-study/sub-feas/select_81.py"]


def run_harness(build, run, stratum, mode, tag, extra=None):
    exe_dir = BUILDS[build][0]
    outdir = os.path.join(OUT, "r0" if tag.startswith("r0") else "time")
    os.makedirs(outdir, exist_ok=True)
    csvp = os.path.join(outdir, f"{tag}.csv")
    logp = os.path.join(outdir, f"{tag}.log")
    cmd = ["dotnet", os.path.join(exe_dir, "Replay81.dll"), "--selection", R.SELECTION, "--run", run,
           "--stratum", stratum, "--wav-root", ART, "--out", csvp, "--log", logp, "--mode", mode,
           "--label", f"{build}:{tag}"] + (extra or [])
    restarts = 0
    while True:
        t0 = time.time()
        rc = subprocess.run(cmd, capture_output=True, text=True).returncode
        R.log(f"harness {tag} build={build} rc={rc} in {time.time() - t0:.0f}s (restart {restarts})")
        with open(os.path.join(OUT, "process_exits.log"), "a") as fh:
            fh.write(f"{R.now()} {tag} rc={rc} restart={restarts}\n")
        if rc == 0:
            return csvp
        restarts += 1
        if restarts > R.MAX_RESTARTS:
            R.log(f"harness {tag}: giving up after {R.MAX_RESTARTS} restarts; continuing with the next block")
            return csvp


def main():
    os.makedirs(OUT, exist_ok=True)
    R.LOGF = open(os.path.join(OUT, "orchestrator.log"), "a", encoding="utf-8")
    import ctypes
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    R.log("orchestrator start (speed acceptance)")

    # ---- P0 preflight ----------------------------------------------------------------------
    chk = subprocess.run(["git", "check-ignore", "-q", os.path.join(OUT, "x")], cwd=REPO)
    assert chk.returncode == 0, "OUT is not gitignored"
    assert subprocess.run(["git", "ls-files", "--", OUT], cwd=REPO, capture_output=True, text=True).stdout.strip() == ""
    sel_sha = R.sha256(R.SELECTION)
    assert sel_sha == R.SELECTION_SHA256, ("selection.json changed", sel_sha)

    # E1 comes first: no timing unless it PASSED.
    e1 = json.load(open(E1_SUMMARY))
    assert e1.get("e1_pass") is True, "E1 did not pass: STOP, read no timing row"
    assert e1["selection_sha256"] == "f58c0c7bd3ed34855f5db24277b941202813831b0f088a34944f5ba97c6879e2"

    # WSJT-X must be closed (Architect: run with WSJT-X closed this time).
    ps = subprocess.run(["powershell", "-NoProfile", "-Command",
                         "(Get-Process | Where-Object { $_.ProcessName -match '^(wsjtx|jt9|OpenWSFZ)' } | "
                         "Select-Object -ExpandProperty ProcessName) -join ','"], capture_output=True, text=True).stdout.strip()
    assert ps == "", ("WSJT-X / jt9 / OpenWSFZ is running", ps)

    pre = {"selection_sha256": sel_sha, "utc": R.now(), "e1_selection_sha256": e1["selection_sha256"], "builds": {}}
    for b, (d, want) in BUILDS.items():
        got = R.sha256(os.path.join(d, "libft8.dll"))
        assert got == want, (b, got, want)
        pre["builds"][b] = {"libft8_sha256_actual": got, "expected": want,
                            "harness_dll_sha256": R.sha256(os.path.join(d, "Replay81.dll"))}
    pre["harness_commit"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", *GUARDED_FILES], cwd=REPO,
                           capture_output=True, text=True).stdout.strip()
    assert dirty == "", "harness/orchestrator/rows files are not committed"
    pre["harness_tree_clean"] = True
    pre["totals"] = json.load(open(R.SELECTION, encoding="utf-8"))["totals"]
    json.dump(pre, open(os.path.join(OUT, "preflight.json"), "w"), indent=1)
    R.env_snapshot("env_start.txt")
    R.log(f"preflight ok: selection {sel_sha[:12]}..., harness/orchestrator commit {pre['harness_commit'][:8]}, E1 PASSED")

    # ---- P1 R0 (same predicate as 8.1) -----------------------------------------------------
    import collections
    r0 = {}
    for run in RUNS:
        R.status("R0", run=run)
        build = PRODUCING_BUILD[run]
        csvp = run_harness(build, run, "pilot", "off", f"r0_pilot_{run}")
        arch = R.archived_counts(run)
        ok = tot = 0
        deltas = []
        with open(csvp) as fh:
            next(fh)
            for line in fh:
                p = line.rstrip("\n").split(",")
                if len(p) < 8:
                    continue
                tot += 1
                d = int(p[6]) - arch.get(p[2], 0)
                deltas.append(d)
                if p[7] == "" and abs(d) <= R.R0_MAX_DELTA:
                    ok += 1
        r0[run] = {"producing_build": build, "libft8_sha256": BUILDS[build][1], "cycles": tot, "within_1": ok,
                   "fraction": (ok / tot if tot else 0.0), "pass": tot > 0 and ok / tot >= R.R0_MIN_FRACTION,
                   "delta_histogram": dict(sorted(collections.Counter(deltas).items()))}
        R.log(f"R0 {run}: {ok}/{tot} within +-{R.R0_MAX_DELTA}  pass={r0[run]['pass']}")
    json.dump(r0, open(os.path.join(OUT, "r0.json"), "w"), indent=1)
    if not all(v["pass"] for v in r0.values()):
        R.status("STOPPED_R0_FAILED", r0=r0)
        R.log("R0 FAILED: STOP, no timing is taken (do not adjust the tolerance)")
        return 2

    # ---- P2 timing: base OFF and candidate alt, adjacent per (run, stratum) -----------------
    for run in RUNS:
        for stratum in ("H", "M"):
            R.status("TIMING", run=run, stratum=stratum)
            run_harness("2b39cf18", run, stratum, "off", f"base_{stratum}_{run}")
            run_harness("ca0bcd9b", run, stratum, "alt", f"time_{stratum}_{run}")
    R.status("TIMING", run="R6", stratum="R6")
    run_harness("ca0bcd9b", RUNS[0], "R6", "alt", "time_R6")
    for run in RUNS:
        R.status("TIMING_T", run=run, stratum="H", threads=THREADS_T)
        run_harness("ca0bcd9b", run, "H", "alt", f"T4_H_{run}", extra=["--threads", THREADS_T])

    # base flag-OFF measured AGAIN at the end: the noise floor of the R5' comparison (same DLL, same cycles,
    # later in the session). Report only.
    for run in RUNS:
        for stratum in ("H", "M"):
            R.status("TIMING_BASE_REPEAT", run=run, stratum=stratum)
            run_harness("2b39cf18", run, stratum, "off", f"baseB_{stratum}_{run}")

    # ---- P3 -------------------------------------------------------------------------------
    R.env_snapshot("env_end.txt")
    orphans = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-Process | Where-Object { $_.ProcessName -match 'Replay81|OpenWSFZ|Ft8.FitProbe' } | "
                              "Select-Object Id,ProcessName | Out-String)"], capture_output=True, text=True).stdout.strip()
    open(os.path.join(OUT, "orphan_check.txt"), "w").write(orphans + "\n")
    R.status("DONE", orphan_check="empty" if not orphans else "NON-EMPTY")
    R.log("orchestrator DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
