#!/usr/bin/env python
"""NHARD-REP Amendment 3 (OSD-OFF, Architect 2026-10-06 18:19Z, spec section 14): the single arm N0 at --nhard 0, PAIRED with the existing N40.

Why: production OSD is sign-inverted (#215), so every OSD accept is a chance-CRC false decode. At nhard 0 the OSD gate rejects every codeword, so OSD is effectively off.
Question: what do those false decodes cost the shipped decoder, and is OSD-off a safe setting?

Same harness (qa/rr-study/sub-feas/replay81, now admitting 0), build be3cc5ac, pin 2fa6d993...f365, flag ON, threads 8, Test B rule, the SAME 311 sampled cycles (selection.json,
LF SHA pinned in nhard_rep_rows.py). N40 is NOT re-run: it is read from artefacts/rr_2026-10-06_nhard_rep/. The only setting that differs is --nhard.
This script RUNS the arm only; nhard_rep_n0_rows.py scores it afterwards (rows V1'..V5, V2'', NET_0, O-HARM / O-GAIN / O-SAFE / O-OPEN), so nothing can be tuned during the run.

Pre-flight (asserted; any failure aborts before a decode): selection and probe-vector SHAs; harness, scripts and tests COMMITTED; clean build checkout at be3cc5ac; libft8.dll == the pin;
the harness refuses --nhard 50; no WSJT-X / jt9 / daemon / other replay running. The first V2'' probe point is checked by the harness itself (exit 5 before any cycle if P_lo is NOT rejected
at 0). HK-037: ALL.TXT is read only inside the harness' matching function; every output is numeric.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "sub-feas"))
import replay81_run as R  # noqa: E402
import nhard_rep_rows as ROWS  # noqa: E402

REPO = R.REPO
ART = os.environ.get("OPENWSFZ_ARTEFACTS", os.path.join(REPO, "artefacts"))
RUN = "20261004_1634"
OUT = os.path.join(ART, "rr_2026-10-06_nhard_rep_n0")
SELECTION = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-06-nhard-rep", "selection.json")
CHECKOUT = r"D:\Projects\claude\_qa-scratch\nhard-rep\tree"
BUILD_COMMIT = "be3cc5ac"
HOUT = r"D:\Projects\claude\_qa-scratch\nhard-rep\out_n0"
DLL = ROWS.DLL_PIN
WAV_DIR = os.path.join(ART, f"{RUN}_endurance_run-gathered", "owsfz", "wav")
WS_ALLTXT = os.path.join(ART, f"{RUN}_endurance_run-gathered", "wsjt-x", "ALL.TXT")
PROBES = os.path.join(HERE, "probe_vectors.json")
THREADS = ROWS.THREADS
ARM, NHARD, STRATUM = "N0", 0, "SAMPLE"
V2PP_FAIL_RC = 5
MAX_ATTEMPTS = 3
BLOCKING_RE = r"^(wsjtx|jt9|OpenWSFZ|Replay81)"
GUARDED = ["qa/rr-study/sub-feas/replay81", "qa/rr-study/nhard-rep", "qa/tests/test_nhard_rep_rows.py", "qa/tests/test_nhard_rep_n0_rows.py",
           "qa/rr-study/results/2026-10-06-nhard-rep/selection.json"]


def sh(*a, cwd=REPO):
    return subprocess.run(list(a), cwd=cwd, capture_output=True, text=True)


def competitors():
    ps = ("Get-Process | Where-Object { $_.ProcessName -match '" + BLOCKING_RE + "' } | ForEach-Object { '{0},{1}' -f $_.ProcessName, $_.Id }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    return [l.strip() for l in out.splitlines() if "," in l]


def preflight():
    os.makedirs(OUT, exist_ok=True)
    art_repo = os.path.dirname(ART)
    assert sh("git", "check-ignore", "-q", os.path.join(OUT, "x"), cwd=art_repo).returncode == 0, "OUT not gitignored"
    assert R.sha256(SELECTION) and ROWS.SELECTION_SHA256 == __import__("hashlib").sha256(open(SELECTION, "rb").read().replace(b"\r\n", b"\n")).hexdigest(), "selection.json differs"
    assert __import__("hashlib").sha256(open(PROBES, "rb").read().replace(b"\r\n", b"\n")).hexdigest() == ROWS.PROBE_SHA256, "probe vectors differ"
    assert sh("git", "status", "--porcelain", "--", *GUARDED).stdout.strip() == "", "harness/scripts not committed"
    assert sh("git", "rev-parse", "HEAD", cwd=CHECKOUT).stdout.strip().startswith(BUILD_COMMIT)
    assert sh("git", "status", "--porcelain", cwd=CHECKOUT).stdout.strip() == "", "build checkout not clean"
    r = sh("dotnet", "build", os.path.join(REPO, "qa", "rr-study", "sub-feas", "replay81", "Replay81.csproj"), "-c", "Release", f"-p:RepoRoot={CHECKOUT}",
           "-p:HasSubfeas=true", "-p:HasMaxThreads=true", "-p:HasTwoStage=true", "-o", HOUT, "-nologo", "-v", "q")
    assert r.returncode == 0, r.stdout[-600:]
    sh("dotnet", "build-server", "shutdown")
    got = R.sha256(os.path.join(HOUT, "libft8.dll"))
    assert got == DLL, got
    reject_dir = os.path.join(OUT, "_reject_probe")
    rj = sh("dotnet", os.path.join(HOUT, "Replay81.dll"), "--selection", SELECTION, "--run", RUN, "--stratum", STRATUM, "--wav-root", ART, "--wav-dir", WAV_DIR,
            "--out", os.path.join(reject_dir, "x.csv"), "--log", os.path.join(reject_dir, "x.log"), "--mode", "two1", "--threads", THREADS, "--nhard", "50")
    assert rj.returncode != 0 and not os.path.exists(reject_dir), ("harness accepted --nhard 50", rj.returncode)
    comp = competitors()
    assert not comp, ("WSJT-X / jt9 / the daemon / another replay must not be running", comp)
    pre = {"utc": R.now(), "spec": "NHARD-REP Amendment 3 (OSD-OFF)", "arm": ARM, "nhard": NHARD, "libft8_sha256": got, "build_commit": BUILD_COMMIT,
           "harness_commit": sh("git", "rev-parse", "HEAD").stdout.strip(), "replay81_dll_sha256": R.sha256(os.path.join(HOUT, "Replay81.dll")),
           "selection_sha256_lf": ROWS.SELECTION_SHA256, "probe_vectors_sha256_lf": ROWS.PROBE_SHA256, "threads": THREADS, "harness_rejects_nhard_50": True,
           "paired_with": "artefacts/rr_2026-10-06_nhard_rep (N40, not re-run)"}
    json.dump(pre, open(os.path.join(OUT, "preflight.json"), "w"), indent=1)
    return pre


def files():
    return {k: os.path.join(OUT, f"{k}_{ARM}.{ext}") for k, ext in (("run", "csv"), ("testb", "csv"), ("outcomes", "csv"), ("abandon", "csv"), ("matched", "csv"),
                                                                     ("probe", "csv"), ("log", "log"))}


def pin(when):
    got = R.sha256(os.path.join(HOUT, "libft8.dll"))
    with open(os.path.join(OUT, "pins.jsonl"), "a") as fh:
        fh.write(json.dumps({"utc": R.now(), "arm": ARM, "when": when, "libft8_sha256": got, "pinned": DLL, "match": got == DLL}) + "\n")
    assert got == DLL


def run_arm():
    f = files()
    rc = None
    for attempt in range(MAX_ATTEMPTS):
        for p in f.values():
            if os.path.exists(p):
                os.remove(p)
        pin("start")
        cmd = ["dotnet", os.path.join(HOUT, "Replay81.dll"), "--selection", SELECTION, "--run", RUN, "--stratum", STRATUM, "--wav-root", ART, "--wav-dir", WAV_DIR,
               "--out", f["run"], "--log", f["log"], "--mode", "two1", "--threads", THREADS, "--nhard", str(NHARD), "--label", f"{BUILD_COMMIT}:nhardrep_{ARM}",
               "--outcomes", f["outcomes"], "--abandon-out", f["abandon"], "--wsjtx-alltxt", WS_ALLTXT, "--testb-out", f["testb"], "--matched-out", f["matched"],
               "--probe-vectors", PROBES, "--probe-out", f["probe"]]
        t0 = time.time()
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        rc = proc.returncode
        pin("end")
        with open(os.path.join(OUT, "process_exits.log"), "a") as fh:
            fh.write(f"{R.now()} {ARM} rc={rc} attempt={attempt} wall_s={time.time() - t0:.0f}\n")
        if rc == 0 or rc == V2PP_FAIL_RC:
            break
    return rc


def main():
    os.makedirs(OUT, exist_ok=True)
    R.OUT = OUT
    R.LOGF = open(os.path.join(OUT, "orchestrator.log"), "a", encoding="utf-8")
    R.log("N0 start (OSD-OFF)")
    pre = preflight()
    R.log(f"preflight OK harness {pre['harness_commit'][:8]} DLL {pre['libft8_sha256'][:8]}")
    if "--preflight-only" in sys.argv:
        return 0
    R.env_snapshot("env_start.txt")
    rc = run_arm()
    R.env_snapshot("env_end.txt")
    orphans = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-Process | Where-Object { $_.ProcessName -match 'Replay81' } | Select-Object Id | Out-String)"],
                             capture_output=True, text=True).stdout.strip()
    open(os.path.join(OUT, "orphan_check.txt"), "w").write(orphans + "\n")
    R.status("DONE", rc=rc, stopped=("V2PP_FAIL" if rc == V2PP_FAIL_RC else None), orphan_check="empty" if not orphans else "NON-EMPTY")
    R.log(f"N0 DONE rc={rc} orphan_check={'empty' if not orphans else 'NON-EMPTY'}")
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
