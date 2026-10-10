#!/usr/bin/env python
"""SUB-FEAS two-stage publish acceptance: S1 (split changes timing only), S2 (batch-1 latency), and the managed
flag-OFF control (tasks.md 14.1, 14.2, 14.4). Detached, resumable-by-file. Records raw outcomes and timings; rows are
computed afterwards by twostage_rows.py so nothing can be tuned while the run is in progress.

Spec: qa/rr-study/2026-09-30-0641-architect-to-qa-spec-sub-feas-speed-redesign.md sections 5b, 5c (Amendments 2, 3).

Builds (all harness builds are the SAME Replay81 source, committed before this run):
  base  = 2b39cf18   libft8.dll 5a6a4dc0...  managed flag-OFF reference
  ref   = ca0bcd9b   libft8.dll ee00d118...  Stage A single-batch reference for S1 (flag ON, DecodeAsync)
  two   = 247ac391   libft8.dll ee00d118...  two-stage build under test

S1 method (Amendment 3): each build runs in a FRESH process per run, over the SAME cycles in the SAME order (the 161
E1 cycles, e1_selection.json order per run), ONE call per cycle, so the native call sequence, and with it the
process-global callsign hash table, is identical between "ref on" and "two1". Outcome keys are numeric fields plus an
8-hex-digit hash of the message text (never the text).
  ref   mode on    -> single-batch flag-ON outcomes
  two   mode two1  -> batch 1 and batch 2 outcomes
  two   mode off   -> flag-OFF outcomes of the new build
  base  mode off   -> flag-OFF outcomes of the base build (the managed flag-OFF control, 14.4)
S2 method: two build, mode "two" (alt: OFF DecodeAsync and ON DecodeTwoStageAsync, order alternated by cycle parity) over
H and M per run; time to batch 1 vs the same-session flag-OFF whole call.

HK-037 / NFR-021: stamps, integers, timings and hashes only. WSJT-X closed (asserted). Output untracked (asserted).
HK-013/019/023: detached, logged, status.json heartbeat.
"""
import ctypes
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay81_run as R

REPO = R.REPO
ART = R.ART
OUT = os.path.join(ART, "sub_feas_twostage_acceptance")
R.OUT = OUT
E1SEL = os.path.join(REPO, "qa", "rr-study", "results", "2026-09-30-sub-feas-speed-e1", "e1_selection.json")
E1SEL_SHA = "f58c0c7bd3ed34855f5db24277b941202813831b0f088a34944f5ba97c6879e2"
DERIVED = os.path.join(ART, "sub_feas_stage_a_e3_baseline", "e1_derived_selection.json")
RUNS = R.RUNS

BUILDS = {
    "base": {"commit": "2b39cf18", "checkout": r"D:\Projects\claude\_qa-scratch\w-replay81-2b39cf18", "out": r"D:\Projects\claude\_qa-scratch\w-ts-out-base",
             "props": ["-p:HasSubfeas=true"], "dll": "5a6a4dc04a2cf6fbd987c12ce7635a968f4c9b69f73cacebe422af62827e38c5"},
    "ref": {"commit": "ca0bcd9b", "checkout": r"D:\Projects\claude\_qa-scratch\w-speed-review", "out": r"D:\Projects\claude\_qa-scratch\w-ts-out-ref",
            "props": ["-p:HasSubfeas=true", "-p:HasMaxThreads=true"],
            "dll": "ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c"},
    "two": {"commit": "247ac391", "checkout": r"D:\Projects\claude\_qa-scratch\w-twostage-review", "out": r"D:\Projects\claude\_qa-scratch\w-ts-out-two",
            "props": ["-p:HasSubfeas=true", "-p:HasMaxThreads=true", "-p:HasTwoStage=true"],
            "dll": "ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c"},
}
GUARDED = ["qa/rr-study/sub-feas/replay81", "qa/rr-study/sub-feas/replay81_run.py", "qa/rr-study/sub-feas/replay81_rows.py",
           "qa/rr-study/sub-feas/twostage_run.py", "qa/rr-study/sub-feas/twostage_rows.py"]


def sh(*a, cwd=REPO):
    return subprocess.run(list(a), cwd=cwd, capture_output=True, text=True)


def build_all():
    for tag, b in BUILDS.items():
        if not os.path.isdir(b["checkout"]):
            r = sh("git", "worktree", "add", "--detach", b["checkout"], b["commit"])
            assert r.returncode == 0, r.stderr
        head = sh("git", "rev-parse", "HEAD", cwd=b["checkout"]).stdout.strip()
        assert head.startswith(b["commit"]), (tag, head)
        proj = os.path.join(REPO, "qa", "rr-study", "sub-feas", "replay81", "Replay81.csproj")
        r = sh("dotnet", "build", proj, "-c", "Release", f"-p:RepoRoot={b['checkout']}", *b["props"], "-o", b["out"], "-nologo", "-v", "q")
        assert r.returncode == 0, (tag, r.stdout[-800:], r.stderr[-800:])
        got = R.sha256(os.path.join(b["out"], "libft8.dll"))
        assert got == b["dll"], (tag, got, b["dll"])
        R.log(f"build {tag} {b['commit']} libft8.dll actual={got[:12]}... pinned match")


def harness(build, run, stratum, mode, tag, selection, extra=None, sub="time"):
    b = BUILDS[build]
    outdir = os.path.join(OUT, sub)
    os.makedirs(outdir, exist_ok=True)
    csvp = os.path.join(outdir, tag + ".csv")
    logp = os.path.join(outdir, tag + ".log")
    for p in (csvp, logp) + tuple(os.path.join(outdir, tag + ".outcomes.txt") for _ in [0]):
        if os.path.exists(p) and sub == "s1":
            os.remove(p)  # a fresh S1 file every time: never resume into a stale outcome list
    cmd = ["dotnet", os.path.join(b["out"], "Replay81.dll"), "--selection", selection, "--run", run, "--stratum", stratum,
           "--wav-root", ART, "--out", csvp, "--log", logp, "--mode", mode, "--label", f"{build}:{tag}"] + (extra or [])
    rc = subprocess.run(cmd, capture_output=True, text=True).returncode
    R.log(f"harness {tag} build={build} mode={mode} rc={rc}")
    with open(os.path.join(OUT, "process_exits.log"), "a") as fh:
        fh.write(f"{R.now()} {tag} rc={rc}\n")
    assert rc == 0, f"harness {tag} rc={rc}"


def main():
    os.makedirs(OUT, exist_ok=True)
    R.LOGF = open(os.path.join(OUT, "orchestrator.log"), "a", encoding="utf-8")
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    R.log("orchestrator start (two-stage acceptance)")
    assert sh("git", "check-ignore", "-q", os.path.join(OUT, "x")).returncode == 0, "OUT not gitignored"
    assert sh("git", "ls-files", "--", OUT).stdout.strip() == ""
    assert R.sha256(R.SELECTION) == R.SELECTION_SHA256
    assert R.sha256(E1SEL) == E1SEL_SHA
    assert os.path.isfile(DERIVED), "derived E1 selection missing (run stage_a_e3_baseline.py first)"
    assert sh("git", "status", "--porcelain", "--", *GUARDED).stdout.strip() == "", "harness/scripts not committed"
    ps = subprocess.run(["powershell", "-NoProfile", "-Command",
                         "(Get-Process | Where-Object { $_.ProcessName -match '^(wsjtx|jt9|OpenWSFZ)' } | "
                         "Select-Object -ExpandProperty ProcessName) -join ','"], capture_output=True, text=True).stdout.strip()
    assert ps == "", ("WSJT-X / jt9 / OpenWSFZ is running", ps)
    build_all()
    pre = {"utc": R.now(), "selection81": R.SELECTION_SHA256, "e1_selection": E1SEL_SHA,
           "harness_commit": sh("git", "rev-parse", "HEAD").stdout.strip(),
           "builds": {t: {"commit": b["commit"], "libft8_sha256": R.sha256(os.path.join(b["out"], "libft8.dll")),
                          "harness_dll_sha256": R.sha256(os.path.join(b["out"], "Replay81.dll"))} for t, b in BUILDS.items()}}
    json.dump(pre, open(os.path.join(OUT, "preflight.json"), "w"), indent=1)
    R.env_snapshot("env_start.txt")

    # ---- S1 + managed flag-OFF control: outcomes, fresh process per (build, run), one call per cycle -------------
    for run in RUNS:
        R.status("S1", run=run)
        oc = lambda name: ["--outcomes", os.path.join(OUT, "s1", f"{name}_{run}.outcomes.txt")]
        for name in ("ref_on", "two1", "two_off", "base_off"):
            p = os.path.join(OUT, "s1", f"{name}_{run}.outcomes.txt")
            if os.path.exists(p):
                os.remove(p)
        harness("ref", run, "E1", "on", f"ref_on_{run}", DERIVED, oc("ref_on"), sub="s1")
        harness("two", run, "E1", "two1", f"two1_{run}", DERIVED, oc("two1"), sub="s1")
        harness("two", run, "E1", "off", f"two_off_{run}", DERIVED, oc("two_off"), sub="s1")
        harness("base", run, "E1", "off", f"base_off_{run}", DERIVED, oc("base_off"), sub="s1")

    # ---- S2: batch-1 latency vs the same-session flag-OFF whole call --------------------------------------------
    for run in RUNS:
        for stratum in ("H", "M"):
            R.status("S2", run=run, stratum=stratum)
            harness("two", run, stratum, "two", f"two_{stratum}_{run}", R.SELECTION, sub="time")

    R.env_snapshot("env_end.txt")
    orphans = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-Process | Where-Object { $_.ProcessName -match 'Replay81|OpenWSFZ' } | Select-Object Id,ProcessName | Out-String)"],
                             capture_output=True, text=True).stdout.strip()
    open(os.path.join(OUT, "orphan_check.txt"), "w").write(orphans + "\n")
    R.status("DONE", orphan_check="empty" if not orphans else "NON-EMPTY")
    R.log("orchestrator DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
