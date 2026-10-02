#!/usr/bin/env python
"""SUB-FEAS §8.1 real-band runtime replay: unattended orchestrator (detached, resumable).

Spec: qa/rr-study/2026-09-29-2010-architect-sub-feas-8-1-real-band-runtime-replay-spec.md
      + Amendment 1 (R0 through the producing DLL) + Amendment 2 (build under test 2b39cf18).

This script RUNS the replay and records raw per-cycle rows. It does NOT analyse them: rows R1..R7 are
computed afterwards by replay81_rows.py, so nothing can be tuned while the run is in progress. The one
predicate it does evaluate is R0 (instrument validity), because the spec makes R0 a STOP gate.

Phases
  P0 preflight: selection.json SHA-256 == the frozen value, the three harness builds carry the expected
     libft8.dll SHA-256, the QA tree holding this harness is clean, environment snapshot.
  P1 R0: per run, replay the 20-cycle pilot through the build that PRODUCED that run's archive
     (84cac119 for 20260922_2056 and 20260923_1730; 51e40b55 for 20260925_2010; all three used
     libft8.dll 38a21f84...) and compare the replay's decode COUNT with the archived ALL.TXT count for
     that cycle: |delta| <= 1 on >= 95 % of the pilot cycles. Any run failing => STOP (no timing).
  P2 timing: per run, strata H then M through the build under test (2b39cf18), each cycle decoded
     OFF and ON with order alternated by cycle-index parity; then R6 (synthetic pair-sum stress, ON only).
  P3 orphan check + end-of-run environment snapshot.

Resume: re-running this script continues; the harness skips rows already in each CSV.

HK-037 / NFR-021: ALL.TXT is read only for its first field (the cycle stamp) in this file.
HK-013/019/023: detached, logged, status.json heartbeat; sleep prevented for the process lifetime.
"""
import collections
import ctypes
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SELECTION = os.path.join(REPO, "qa", "rr-study", "results", "2026-09-29-sub-feas-8-1-replay", "selection.json")
SELECTION_SHA256 = "730d6ea61f25ba8cad90520a17266b3efe0e1e476b1bd1ce29d1a6cbcc3b1f15"
ART = os.path.join(REPO, "artefacts")
OUT = os.path.join(ART, "rr_2026-09-29_replay81")
RUNS = ["20260922_2056", "20260923_1730", "20260925_2010"]

BUILDS = {  # label -> (harness output dir, expected libft8.dll sha256)
    "2b39cf18": (r"C:\Users\Frank\w-replay81-out-2b39cf18",
                 "5a6a4dc04a2cf6fbd987c12ce7635a968f4c9b69f73cacebe422af62827e38c5"),
    "84cac119": (r"C:\Users\Frank\w-replay81-out-84cac119",
                 "38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba"),
    "51e40b55": (r"C:\Users\Frank\w-replay81-out-51e40b55",
                 "38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba"),
}
PRODUCING_BUILD = {"20260922_2056": "84cac119", "20260923_1730": "84cac119", "20260925_2010": "51e40b55"}
R0_MAX_DELTA = 1
R0_MIN_FRACTION = 0.95
MAX_RESTARTS = 3
STAMP = re.compile(r"^\d{6}_\d{6}$")


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


LOGF = None


def log(msg):
    line = f"{now()} {msg}"
    print(line, flush=True)
    if LOGF:
        LOGF.write(line + "\n")
        LOGF.flush()


def status(phase, **kw):
    d = {"phase": phase, "updated_utc": now(), **kw}
    with open(os.path.join(OUT, "status.json"), "w") as fh:
        json.dump(d, fh, indent=1)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def env_snapshot(name):
    ps = ("Get-Process | Sort-Object CPU -Descending | Select-Object -First 25 "
          "Name,Id,@{n='CPU_s';e={[math]::Round($_.CPU,1)}},@{n='WS_MB';e={[math]::Round($_.WS/1MB)}} | Format-Table -AutoSize | Out-String -Width 200")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    mem = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "(Get-CimInstance Win32_OperatingSystem | Select-Object FreePhysicalMemory,TotalVisibleMemorySize | Format-List | Out-String)"],
                         capture_output=True, text=True)
    cpu = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | Format-List | Out-String)"],
                         capture_output=True, text=True)
    with open(os.path.join(OUT, name), "w") as fh:
        fh.write(f"# {now()}\n{cpu.stdout}\n{mem.stdout}\n# top processes by cumulative CPU (names only)\n{r.stdout}")


def archived_counts(run):
    c = collections.Counter()
    p = os.path.join(ART, f"{run}_endurance_run-gathered", "owsfz", "ALL.TXT")
    with open(p, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            head = line.split(None, 1)
            if head and STAMP.match(head[0]):
                c[head[0]] += 1
    return c


def run_harness(build, run, stratum, mode, tag, wav_root=ART):
    exe_dir = BUILDS[build][0]
    outdir = os.path.join(OUT, "r0" if tag.startswith("r0") else "time")
    os.makedirs(outdir, exist_ok=True)
    csvp = os.path.join(outdir, f"{tag}.csv")
    logp = os.path.join(outdir, f"{tag}.log")
    cmd = ["dotnet", os.path.join(exe_dir, "Replay81.dll"), "--selection", SELECTION, "--run", run,
           "--stratum", stratum, "--wav-root", wav_root, "--out", csvp, "--log", logp, "--mode", mode,
           "--label", f"{build}:{tag}"]
    restarts = 0
    while True:
        t0 = time.time()
        rc = subprocess.run(cmd, capture_output=True, text=True).returncode
        log(f"harness {tag} build={build} rc={rc} in {time.time() - t0:.0f}s (restart {restarts})")
        with open(os.path.join(OUT, "process_exits.log"), "a") as fh:
            fh.write(f"{now()} {tag} rc={rc} restart={restarts}\n")
        if rc == 0:
            return csvp, logp
        restarts += 1
        if restarts > MAX_RESTARTS:
            log(f"harness {tag}: giving up after {MAX_RESTARTS} restarts; continuing with the next block")
            return csvp, logp


def expected_rows(sel, run, stratum, alt):
    n = len(sel["runs"][run][stratum])
    return n * (2 if alt else 1)


def main():
    global LOGF
    os.makedirs(OUT, exist_ok=True)
    LOGF = open(os.path.join(OUT, "orchestrator.log"), "a", encoding="utf-8")
    # keep the machine awake for this process's lifetime (ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    log("orchestrator start")

    # ---- P0 preflight ---------------------------------------------------------------------
    chk = subprocess.run(["git", "check-ignore", "-q", os.path.join(OUT, "x")], cwd=REPO)
    assert chk.returncode == 0, "OUT is not gitignored"
    tracked = subprocess.run(["git", "ls-files", "--", OUT], cwd=REPO, capture_output=True, text=True).stdout.strip()
    assert tracked == "", "OUT contains tracked files"
    sel_sha = sha256(SELECTION)
    assert sel_sha == SELECTION_SHA256, ("selection.json changed", sel_sha)
    pre = {"selection_sha256": sel_sha, "utc": now(), "builds": {}}
    for b, (d, want) in BUILDS.items():
        got = sha256(os.path.join(d, "libft8.dll"))
        assert got == want, (b, got, want)
        pre["builds"][b] = {"libft8_sha256_actual": got, "expected": want,
                            "harness_dll_sha256": sha256(os.path.join(d, "Replay81.dll"))}
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "qa/rr-study/sub-feas/replay81",
                            "qa/rr-study/sub-feas/replay81_run.py", "qa/rr-study/sub-feas/select_81.py"],
                           cwd=REPO, capture_output=True, text=True).stdout.strip()
    assert dirty == "", "harness/orchestrator files are not committed"
    pre["harness_commit"] = head
    pre["harness_tree_clean"] = True
    sel = json.load(open(SELECTION, encoding="utf-8"))
    pre["totals"] = sel["totals"]
    json.dump(pre, open(os.path.join(OUT, "preflight.json"), "w"), indent=1)
    env_snapshot("env_start.txt")
    log(f"preflight ok: selection {sel_sha[:12]}..., harness commit {head[:8]}")

    # ---- P1 R0 ---------------------------------------------------------------------------
    r0 = {}
    for run in RUNS:
        status("R0", run=run)
        build = PRODUCING_BUILD[run]
        csvp, _ = run_harness(build, run, "pilot", "off", f"r0_pilot_{run}")
        arch = archived_counts(run)
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
                if p[7] == "" and abs(d) <= R0_MAX_DELTA:
                    ok += 1
        r0[run] = {"producing_build": build, "libft8_sha256": BUILDS[build][1], "cycles": tot,
                   "within_1": ok, "fraction": (ok / tot if tot else 0.0), "pass": tot > 0 and ok / tot >= R0_MIN_FRACTION,
                   "delta_histogram": dict(sorted(collections.Counter(deltas).items()))}
        log(f"R0 {run}: {ok}/{tot} within +-{R0_MAX_DELTA}  pass={r0[run]['pass']}")
    json.dump(r0, open(os.path.join(OUT, "r0.json"), "w"), indent=1)
    if not all(v["pass"] for v in r0.values()):
        status("STOPPED_R0_FAILED", r0=r0)
        log("R0 FAILED for at least one run: STOP, no timing is taken (spec: do not adjust the tolerance)")
        return 2

    # ---- P2 timing ------------------------------------------------------------------------
    for run in RUNS:
        for stratum in ("H", "M"):
            status("TIMING", run=run, stratum=stratum)
            run_harness("2b39cf18", run, stratum, "alt", f"time_{stratum}_{run}")
    status("TIMING", run="R6", stratum="R6")
    run_harness("2b39cf18", RUNS[0], "R6", "alt", "time_R6")

    # ---- P3 -------------------------------------------------------------------------------
    env_snapshot("env_end.txt")
    orphans = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-Process | Where-Object { $_.ProcessName -match 'Replay81|OpenWSFZ' } | Select-Object Id,ProcessName | Out-String)"],
                             capture_output=True, text=True).stdout.strip()
    open(os.path.join(OUT, "orphan_check.txt"), "w").write(orphans + "\n")
    status("DONE", orphan_check="empty" if not orphans else "NON-EMPTY")
    log("orchestrator DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
