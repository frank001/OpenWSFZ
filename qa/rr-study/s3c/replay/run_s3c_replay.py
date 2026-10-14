"""S3c separating replay driver (QA, test-only). Architect ruling 2026-10-05 15:40Z section 4.

    python -X utf8 run_s3c_replay.py build          # build the harness against both checkouts
    python -X utf8 run_s3c_replay.py run            # arm 1; if it reproduces 32 +- 2, arms 2 and 3

Arms (each a FRESH process over the SAME 12 archived S3c cycles of battery 3, flag ON, nhard 40):
  1  build 766f9cc2, --early on     (replay check: should reproduce battery 3's 32/32 at E -2.00)
  2  build 766f9cc2, --early off
  3  build cddd7e34, no early       (baseline-194 build)
STOP RULE (ruling section 4): if arm 1's E -2.00 count is not within 32 +- 2 the replay is not the live path for this
cell and arms 2 and 3 are NOT RUN and NOT READ. The rule is code below, applied before arms 2 and 3 start.
Scoring = the battery's own scorer (s3c_score.score) over an ALL.TXT-format file the harness writes from planted synthetic
texts only; the WSJT-X side is battery 3's own WSJT-X ALL.TXT (unchanged; it is there so the scorer can run).
HK-022: the DLL SHA-256 each process LOADED is asserted against the pin at start and end; the exact command lines are logged.
NFR-021 / HK-037: outputs go to the gitignored artefacts folder; planted synthetic texts only; counts are what is reported.
"""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
RR = HERE.parent.parent
REPO = RR.parent.parent
sys.path[:0] = [str(RR / "s3c"), str(RR), str(RR / "lateness-edge")]
import s3c_score as SC  # noqa: E402

SCRATCH = Path(r"D:\Projects\claude\_qa-scratch")
NEW_TREE, NEW_SHA, NEW_DLL = SCRATCH / "rr-main" / "tree", "766f9cc2", \
    "2fa6d99302c6c602231c870c1e61755aeeddb7ad1b9ce392fb98a4bdbd94f365"
OLD_TREE, OLD_SHA, OLD_DLL = SCRATCH / "baseline-194" / "tree", "cddd7e34", \
    "ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c"
BIN = SCRATCH / "s3c-replay"
WAV_DIR = Path(r"D:\Projects\claude\OpenWSFZ\artefacts\_rr_main766f9cc2_daemon_output\cycle-audio")
BATTERY = RR / "results" / "2026-10-04-766f9cc"
SCENARIO = RR / "scenarios" / "s3c-edge-guard.json"
OUT = REPO / "artefacts" / "20261005_s3c_replay"   # the worktree's junction to the one artefacts folder; gitignored
TARGET_PART, BATTERY3_X, TOLERANCE = "S3c-E50", 32, 2   # E -2.00 is part S3c-E50 (L = -2.0 in s3c_result.json)
HARNESS_PROJ = HERE / "S3cReplay.csproj"


def run(cmd, **kw):
    print("$", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], text=True, capture_output=True, **kw)


def git(tree, *args):
    return run(["git", "-C", tree, *args]).stdout.strip()


def preflight():
    for tree, sha in ((NEW_TREE, NEW_SHA), (OLD_TREE, OLD_SHA)):
        head = git(tree, "rev-parse", "--short=8", "HEAD")
        assert head == sha, f"{tree} is at {head}, expected {sha}"
        assert git(tree, "status", "--short", "--", "src", "native") == "", f"{tree}: src/native not clean"
    assert git(REPO, "status", "--short", "--", HERE) == "", "harness sources are not committed: commit BEFORE decoding"
    assert run(["git", "-C", REPO, "check-ignore", "-q", OUT / "x"]).returncode == 0, "OUT is not gitignored"
    print("preflight ok: trees", NEW_SHA, OLD_SHA, "src/native clean; harness committed:", git(REPO, "log", "-1", "--format=%h", "--", HERE))


def stamps():
    out = []
    with open(BATTERY / "s3c" / "playback_log.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            out.append(datetime.strptime(r["boundary_utc"], "%Y-%m-%dT%H:%M:%SZ").strftime("%y%m%d_%H%M%S"))
    assert len(out) == 12, len(out)
    for s in out:
        assert (WAV_DIR / (s + ".wav")).exists(), s
    return out


def build():
    preflight()
    for name, tree, extra in (("bin_new", NEW_TREE, ["-p:HasEarly=true"]), ("bin_old", OLD_TREE, [])):
        r = run(["dotnet", "build", HARNESS_PROJ, "-c", "Release", f"-p:RepoRoot={tree}", *extra, "-o", BIN / name, "-nologo", "-v", "q"])
        print(r.stdout[-600:], r.stderr[-600:])
        assert r.returncode == 0, "build failed " + name


def run_arm(n, exe_dir, early, pin):
    d = OUT / f"arm{n}"
    d.mkdir(parents=True, exist_ok=True)
    cmd = [exe_dir / "S3cReplay.exe", "--wav-dir", WAV_DIR, "--scenario", SCENARIO, "--stamps", ",".join(stamps()),
           "--early", early, "--out-alltxt", d / "ALL.TXT", "--out-counts", d / "counts.csv"]
    procs = run(["powershell", "-NoProfile", "-Command",
                 "Get-Process | Where-Object {$_.Name -match 'dotnet|testhost|MSBuild|VBCSCompiler|OpenWSFZ|wsjtx|jt9'} | "
                 "Select-Object -ExpandProperty Name | Sort-Object | Get-Unique"]).stdout.split()
    r = run(cmd)
    (d / "stdout.txt").write_text(r.stdout + r.stderr, encoding="utf-8")
    (d / "cmdline.txt").write_text(" ".join(str(c) for c in cmd) + "\ncompeting processes at start: " + ",".join(procs) + "\n", encoding="utf-8")
    assert r.returncode == 0, f"arm {n} rc {r.returncode}: {r.stdout[-300:]} {r.stderr[-300:]}"
    loaded = [ln for ln in r.stdout.splitlines() if "dllSha256=" in ln]
    assert all(pin in ln for ln in loaded) and len(loaded) == 2, f"arm {n}: DLL pin mismatch: {loaded}"
    return d


def score_arm(d):
    scen = json.loads(SCENARIO.read_text(encoding="utf-8"))
    res = SC.score(scen, BATTERY / "wsjt-all.txt", d / "ALL.TXT", BATTERY / "s3c" / "playback_log.csv")
    parts = res["decoders"]["OpenWSFZ"]["parts"]
    row = {p: parts[p]["X"] for p in SC.PARTS}
    (d / "score.json").write_text(json.dumps({"parts": row, "L": {p: parts[p]["L"] for p in SC.PARTS},
                                              "wrong_cycle": res["decoders"]["OpenWSFZ"]["wrong_cycle_decodes"]}, indent=1), encoding="utf-8")
    return row


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "build":
        return build()
    assert mode == "run"
    preflight()
    results = {}
    d1 = run_arm(1, BIN / "bin_new", "on", NEW_DLL)
    results[1] = score_arm(d1)
    print("ARM 1 (766f9cc2, early ON):", results[1], flush=True)
    x = results[1][TARGET_PART]
    if abs(x - BATTERY3_X) > TOLERANCE:
        print(f"STOP RULE: arm 1 {TARGET_PART} = {x}, not within {BATTERY3_X} +- {TOLERANCE}: arms 2 and 3 NOT RUN, NOT READ.")
        (OUT / "STOPPED.txt").write_text(f"arm1 {TARGET_PART}={x}\n", encoding="utf-8")
        return
    results[2] = score_arm(run_arm(2, BIN / "bin_new", "off", NEW_DLL))
    results[3] = score_arm(run_arm(3, BIN / "bin_old", "na", OLD_DLL))
    (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    for n in (1, 2, 3):
        print("ARM", n, results[n])


if __name__ == "__main__":
    main()
