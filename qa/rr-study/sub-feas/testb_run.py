#!/usr/bin/env python
"""SUB-FEAS Test B: WSJT-X corroboration of the flag-ON extra decodes, on the 161 E1 cycles. Orchestrator.

Plan: qa/rr-study/2026-09-30-post-s2b-schedule.md section 2 (Architect's HK-037 ruling: STRICT route). The decoded message text
stays in the harness process's memory; WSJT-X's ALL.TXT is read in the SAME process and the match is done there; only COUNTS and
stamps are written (per cycle, per SNR band). No message text, callsign or text-derived hash exists in any file this run writes.

Method (pre-registered; committed before the run):
  build  = 247ac391 (two-stage), libft8.dll ee00d118...  (harness mode two1: flag ON, DecodeTwoStageAsync, ONE call per cycle)
  cycles = the 161 E1 cycles (e1_selection.json, SHA f58c0c7b...), per run, in the same order as S1
  match  = a decode is CORROBORATED iff WSJT-X decoded the SAME message text in the SAME cycle within 10 Hz (Amendment 1 / Stage 2
           convention), paired ONE-TO-ONE nearest-first across both batches
  bands  = OpenWSFZ SNR: A >= 0, B -10..-1, C -15..-11, D <= -16 dB
  kinds  = b1 (pass-0, the CONTROL rate) and b2 (the residual decodes, the question)
Text equality is stricter than Stage 2's payload match in one respect (a hashed-callsign placeholder rendered differently by the two
decoders counts as NOT corroborated), so the not-corroborated share is an UPPER BOUND on false positives, nothing more.
"""
import ctypes
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay81_run as R

REPO = R.REPO
ART = R.ART
OUT = os.path.join(ART, "sub_feas_testb")
R.OUT = OUT
E1SEL = os.path.join(REPO, "qa", "rr-study", "results", "2026-09-30-sub-feas-speed-e1", "e1_selection.json")
E1SEL_SHA = "f58c0c7bd3ed34855f5db24277b941202813831b0f088a34944f5ba97c6879e2"
DERIVED = os.path.join(ART, "sub_feas_stage_a_e3_baseline", "e1_derived_selection.json")
CHECKOUT = r"C:\Users\Frank\w-twostage-review"
HOUT = r"C:\Users\Frank\w-testb-out"
DLL = "ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c"
RUNS = R.RUNS
GUARDED = ["qa/rr-study/sub-feas/replay81", "qa/rr-study/sub-feas/testb_run.py", "qa/rr-study/sub-feas/testb_rows.py"]


def sh(*a, cwd=REPO):
    return subprocess.run(list(a), cwd=cwd, capture_output=True, text=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    R.LOGF = open(os.path.join(OUT, "orchestrator.log"), "a", encoding="utf-8")
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    R.log("orchestrator start (Test B)")
    assert sh("git", "check-ignore", "-q", os.path.join(OUT, "x")).returncode == 0, "OUT not gitignored"
    assert sh("git", "ls-files", "--", OUT).stdout.strip() == ""
    assert R.sha256(E1SEL) == E1SEL_SHA
    assert os.path.isfile(DERIVED)
    assert sh("git", "status", "--porcelain", "--", *GUARDED).stdout.strip() == "", "harness/scripts not committed"
    head = sh("git", "rev-parse", "HEAD", cwd=CHECKOUT).stdout.strip()
    assert head.startswith("247ac391"), head
    r = sh("dotnet", "build", os.path.join(REPO, "qa", "rr-study", "sub-feas", "replay81", "Replay81.csproj"), "-c", "Release",
           f"-p:RepoRoot={CHECKOUT}", "-p:HasSubfeas=true", "-p:HasMaxThreads=true", "-p:HasTwoStage=true", "-o", HOUT, "-nologo", "-v", "q")
    assert r.returncode == 0, r.stdout[-600:]
    got = R.sha256(os.path.join(HOUT, "libft8.dll"))
    assert got == DLL, got
    pre = {"utc": R.now(), "e1_selection": E1SEL_SHA, "libft8_sha256": got, "build": "247ac391",
           "harness_commit": sh("git", "rev-parse", "HEAD").stdout.strip(),
           "harness_dll_sha256": R.sha256(os.path.join(HOUT, "Replay81.dll"))}
    json.dump(pre, open(os.path.join(OUT, "preflight.json"), "w"), indent=1)
    ps = subprocess.run(["powershell", "-NoProfile", "-Command",
                         "(Get-Process | Where-Object { $_.ProcessName -match '^(wsjtx|jt9|OpenWSFZ)' } | "
                         "Select-Object -ExpandProperty ProcessName) -join ','"], capture_output=True, text=True).stdout.strip()
    assert ps == "", ("WSJT-X / jt9 / OpenWSFZ is running", ps)

    for run in RUNS:
        R.status("TESTB", run=run)
        for f in ("testb_%s.csv" % run, "run_%s.csv" % run, "run_%s.log" % run):
            p = os.path.join(OUT, f)
            if os.path.exists(p):
                os.remove(p)
        ws = os.path.join(ART, f"{run}_endurance_run-gathered", "wsjt-x", "ALL.TXT")
        assert os.path.isfile(ws)
        cmd = ["dotnet", os.path.join(HOUT, "Replay81.dll"), "--selection", DERIVED, "--run", run, "--stratum", "E1",
               "--wav-root", ART, "--out", os.path.join(OUT, f"run_{run}.csv"), "--log", os.path.join(OUT, f"run_{run}.log"),
               "--mode", "two1", "--label", f"247ac391:testb_{run}", "--wsjtx-alltxt", ws,
               "--testb-out", os.path.join(OUT, f"testb_{run}.csv")]
        rc = subprocess.run(cmd, capture_output=True, text=True).returncode
        R.log(f"harness testb_{run} rc={rc}")
        assert rc == 0, f"harness rc={rc}"
    orphans = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-Process | Where-Object { $_.ProcessName -match 'Replay81' } | Select-Object Id | Out-String)"],
                             capture_output=True, text=True).stdout.strip()
    open(os.path.join(OUT, "orphan_check.txt"), "w").write(orphans + "\n")
    R.status("DONE", orphan_check="empty" if not orphans else "NON-EMPTY")
    R.log("orchestrator DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
