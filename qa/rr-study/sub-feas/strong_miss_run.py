#!/usr/bin/env python
"""STRONG-MISS replay orchestrator (QA, 2026-10-10).

Spec: qa/rr-study/2026-10-10-1015-architect-to-qa-spec-strong-miss-replay.md + amendment 1 (arch/strong-miss 22e46d8f).
Protocol and frozen bars: qa/rr-study/2026-10-10-1130-qa-strong-miss-run-protocol.md (committed before the run).

This script launches the ONE-PROCESS harness (qa/rr-study/sub-feas/strongmiss) and wraps it with the checks the spec asks for.
It never reads message text: the harness derives T and C from the two ALL.TXT files, replays, scores and writes AGGREGATES only
(HK-037, amendment 1: nothing per message on disk, not even a temp file).

Pre-flight (all asserted; any failure aborts before a single decode):
  - the harness sources, this script and the protocol note are COMMITTED (git status of GUARDED is empty): no decode before the commit;
  - the build under test is the checkout at 421e3ce2 (DI sync 5, the on-air build) and the harness output libft8.dll == the pin a14fe354...;
  - the harness self-test passes;
  - the run directory is gitignored (artefacts/), so no data can be committed by accident.
Row SM-V1: the DLL SHA is written at the START and at the END of the arm (pins.jsonl), and the harness logs a readback of the settings
(subtraction ON, threads 8, nhard 24, sign fix on) at start and end.
A sampler records competing processes (names and pids only) at start and end; WSJT-X was resident during the live night, so it is allowed
and merely recorded; no timing is compared in this spec.
"""
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
ART = os.environ.get("OPENWSFZ_ARTEFACTS", r"D:\Projects\claude\OpenWSFZ\worktrees\qa\artefacts")
RUN = "20261009_1752"
GATHERED = os.path.join(ART, f"{RUN}_endurance_run-gathered")
PROBE = "--probe" in sys.argv        # step 2 (amendments 2 and 3): the same process also runs the probe on the SM-DECODER set
OUT = os.path.join(ART, "rr_2026-10-10_strong_miss_probe" if PROBE else "rr_2026-10-10_strong_miss")
CHECKOUT = r"D:\Projects\claude\_qa-scratch\endur-sync5\tree"
BUILD_COMMIT = "421e3ce2af84dff57db9e26250f371e6f9cc029b"
HARNESS_OUT = r"D:\Projects\claude\_qa-scratch\strong-miss\out2" if "--probe" in sys.argv else r"D:\Projects\claude\_qa-scratch\strong-miss\out"
DLL_PIN = "a14fe354b88dbc30c4c13fb2610a8d16769684afec70b826bc30756591fd7610"
NHARD, SIGN_FIX, THREADS = "24", "1", "8"       # arm_readback.json of the live run: osdNhardMax 24, subtractionMaxThreads 8
GUARDED = [
    "qa/rr-study/sub-feas/strongmiss",
    "qa/rr-study/sub-feas/strong_miss_run.py",
    "qa/rr-study/2026-10-10-1130-qa-strong-miss-run-protocol.md",
    "qa/rr-study/2026-10-10-1330-qa-strong-miss-step2-protocol.md",
]
COMPETITORS_PS = ("Get-Process | Where-Object { $_.ProcessName -match '^(wsjtx|jt9|OpenWSFZ|testhost|MSBuild|dotnet|VBCSCompiler)' } | "
                  "ForEach-Object { '{0},{1}' -f $_.ProcessName, $_.Id }")


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sh(*a, cwd=REPO):
    return subprocess.run(list(a), cwd=cwd, capture_output=True, text=True)


def competitors():
    out = subprocess.run(["powershell", "-NoProfile", "-Command", COMPETITORS_PS], capture_output=True, text=True).stdout
    return [l.strip() for l in out.splitlines() if "," in l]


def pin(when):
    sha = sha256(os.path.join(HARNESS_OUT, "libft8.dll"))
    row = {"utc": now(), "when": when, "libft8_sha256": sha, "pinned": DLL_PIN, "match": sha == DLL_PIN}
    with open(os.path.join(OUT, "pins.jsonl"), "a") as fh:
        fh.write(json.dumps(row) + "\n")
    return row["match"]


def preflight():
    os.makedirs(OUT, exist_ok=True)
    st = sh("git", "status", "--porcelain", "--", *GUARDED)
    assert st.stdout.strip() == "", "guarded files are not committed:\n" + st.stdout
    head = sh("git", "rev-parse", "HEAD").stdout.strip()
    co = sh("git", "rev-parse", "HEAD", cwd=CHECKOUT).stdout.strip()
    assert co == BUILD_COMMIT, f"build checkout is {co}, expected {BUILD_COMMIT}"
    assert sha256(os.path.join(HARNESS_OUT, "libft8.dll")) == DLL_PIN, "harness libft8.dll != pin"
    assert sha256(os.path.join(CHECKOUT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")) == DLL_PIN, "checkout dll != pin"
    ig = sh("git", "check-ignore", "-q", OUT)
    assert ig.returncode == 0, "run directory is not gitignored"
    for p in (os.path.join(GATHERED, "owsfz", "ALL.TXT"), os.path.join(GATHERED, "wsjt-x", "ALL.TXT"),
              os.path.join(GATHERED, "owsfz", "wav"), os.path.join(GATHERED, "wsjt-x", "wav")):
        assert os.path.exists(p), "missing input " + p
    exe = os.path.join(HARNESS_OUT, "StrongMiss.dll")
    t = subprocess.run(["dotnet", exe, "--selftest", "true"], capture_output=True, text=True)
    assert t.returncode == 0 and "SELFTEST PASS" in t.stdout, "harness self-test failed"
    if PROBE:
        t2 = subprocess.run(["dotnet", exe, "--probe-selftest", "true"], capture_output=True, text=True)
        assert t2.returncode == 0 and "PROBE-SELFTEST" in t2.stdout, "probe self-test failed"
    with open(os.path.join(OUT, "preflight.json"), "w") as fh:
        json.dump({"utc": now(), "repo_head": head, "build_commit": co, "libft8_sha256": DLL_PIN, "harness_dll_sha256": sha256(exe),
                   "nhard": NHARD, "osd_sign_fix": SIGN_FIX, "threads": THREADS, "gathered": GATHERED,
                   "competitors_at_start": competitors()}, fh, indent=1)
    return exe


def main():
    exe = preflight()
    assert pin("start"), "DLL pin mismatch at start"
    res = os.path.join(OUT, "result.json")
    if os.path.exists(res):
        sys.exit("result.json already exists: this arm has run (no re-run without a new protocol)")
    cmd = ["dotnet", exe,
           "--ows-alltxt", os.path.join(GATHERED, "owsfz", "ALL.TXT"), "--wsjt-alltxt", os.path.join(GATHERED, "wsjt-x", "ALL.TXT"),
           "--ows-wav-dir", os.path.join(GATHERED, "owsfz", "wav"), "--wsjt-wav-dir", os.path.join(GATHERED, "wsjt-x", "wav"),
           "--out-json", res, "--log", os.path.join(OUT, "harness.log"), "--status", os.path.join(OUT, "status.json"),
           "--nhard", NHARD, "--osd-sign-fix", SIGN_FIX, "--threads", THREADS, "--label", "STRONG-MISS-20261009_1752" + ("-PROBE" if PROBE else "")]
    if PROBE:
        cmd += ["--probe", "true"]
    with open(os.path.join(OUT, "harness.stdout"), "w") as so, open(os.path.join(OUT, "harness.stderr"), "w") as se:
        rc = subprocess.run(cmd, stdout=so, stderr=se).returncode
    ok_end = pin("end")
    with open(os.path.join(OUT, "run_end.json"), "w") as fh:
        json.dump({"utc": now(), "harness_exit": rc, "dll_pin_match_at_end": ok_end, "competitors_at_end": competitors()}, fh, indent=1)
    sys.exit(0 if rc == 0 and ok_end else 1)


if __name__ == "__main__":
    main()
