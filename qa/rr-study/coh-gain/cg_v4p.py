#!/usr/bin/env python
"""COH-GAIN Amendment 3 (Architect 2026-10-06, spec section 13): the batch-labelled validity replay behind V4'.

V4' = G success >= 0.90 on P1, the COH-GAIN rows that THIS replay matched in BATCH 1 (decodes the live path gets from the ORIGINAL audio, which is what G reads).
The replay is the NHARD-REP arm N40 over the 309 sampled cycles: the same harness (plus --matched-batch-out), the same build and pin, flag ON, threads 8,
nhard 40, DecodeTwoStageAsync one call per cycle, Test B's rule. Nothing about G or the COH-GAIN rows is read here.

Order (Amendment 3): this script runs the replay and then writes a MANIFEST (SHA-256 and counts of every output) to the tracked results folder. The manifest is
COMMITTED BEFORE V4' IS COMPUTED (cg_rows.py computes it, from these outputs, afterwards).

HK-037 / NFR-021: ALL.TXT is passed to the harness (read inside its matching function); every output is numeric (stamps, counts, indices, batch numbers).
  python qa/rr-study/coh-gain/cg_v4p.py --preflight-only
  python qa/rr-study/coh-gain/cg_v4p.py            (preflight, replay, manifest)
"""
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "nhard-rep"))
sys.path.insert(0, os.path.join(HERE, "..", "sub-feas"))
import cg_common as CG  # noqa: E402
import cg_select as SEL  # noqa: E402
import nhard_rep_rows as NR  # noqa: E402
import replay81_run as R  # noqa: E402  (sha256)

REPO = CG.REPO_ROOT
ART = SEL.ART
RUN = SEL.RUN
OUT = os.path.join(ART, "rr_2026-10-06_coh_gain", "v4p")
RESULTS = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-06-coh-gain")
MANIFEST = os.path.join(RESULTS, "v4p_replay_manifest.json")
CHECKOUT = r"D:\Projects\claude\_qa-scratch\nhard-rep\tree"
BUILD_COMMIT = "be3cc5ac"
HOUT = r"D:\Projects\claude\_qa-scratch\nhard-rep\out_v4p"
DLL = NR.DLL_PIN
PROBES = os.path.join(HERE, "..", "nhard-rep", "probe_vectors.json")
THREADS = "8"
BLOCKING_RE = r"^(wsjtx|jt9|OpenWSFZ|Replay81)"
GUARDED = ["qa/rr-study/sub-feas/replay81", "qa/rr-study/nhard-rep", "qa/rr-study/coh-gain", "qa/tests/test_cg_rows.py", "qa/tests/test_cg_fine_sync.py",
           "qa/rr-study/results/2026-10-06-coh-gain/rows.json"]


def sh(*a, cwd=REPO):
    return subprocess.run(list(a), cwd=cwd, capture_output=True, text=True)


def competitors():
    ps = ("Get-Process | Where-Object { $_.ProcessName -match '" + BLOCKING_RE + "' } | ForEach-Object { '{0},{1}' -f $_.ProcessName, $_.Id }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    return [l.strip() for l in out.splitlines() if "," in l]


def sampled_cycles():
    """The 309 cycles of the frozen COH-GAIN row list, in cycle order (the replay's list; derivable from rows.json)."""
    spec = json.load(open(SEL.ROWS_JSON))
    seen = {}
    for r in spec["rows"]:
        seen.setdefault(r[0], r[1])
    return [seen[i] for i in sorted(seen)]


def preflight():
    os.makedirs(OUT, exist_ok=True)
    art_repo = os.path.dirname(ART)
    assert sh("git", "check-ignore", "-q", os.path.join(OUT, "x"), cwd=art_repo).returncode == 0, "OUT not gitignored"
    assert CG.sha256_lf(SEL.ROWS_JSON) == CG.ROWS_JSON_SHA256, "frozen rows.json differs from its pin"
    assert sh("git", "status", "--porcelain", "--", *GUARDED).stdout.strip() == "", "harness/scripts not committed"
    assert sh("git", "rev-parse", "HEAD", cwd=CHECKOUT).stdout.strip().startswith(BUILD_COMMIT)
    assert sh("git", "status", "--porcelain", cwd=CHECKOUT).stdout.strip() == "", "build checkout not clean"
    r = sh("dotnet", "build", os.path.join(REPO, "qa", "rr-study", "sub-feas", "replay81", "Replay81.csproj"), "-c", "Release", f"-p:RepoRoot={CHECKOUT}",
           "-p:HasSubfeas=true", "-p:HasMaxThreads=true", "-p:HasTwoStage=true", "-o", HOUT, "-nologo", "-v", "q")
    assert r.returncode == 0, r.stdout[-600:]
    sh("dotnet", "build-server", "shutdown")
    got = R.sha256(os.path.join(HOUT, "libft8.dll"))
    assert got == DLL, got
    comp = competitors()
    assert not comp, ("WSJT-X / jt9 / the daemon / another replay must not be running", comp)
    nh_sel = json.load(open(NR_SELECTION))
    cycles = sampled_cycles()
    assert len(cycles) == 309, len(cycles)
    sel = {"note": "COH-GAIN V4' replay list: the cycles of the frozen COH-GAIN row list", "run": RUN,
           "runs": {RUN: {"warmup": nh_sel["runs"][RUN]["warmup"], "V4P": cycles}}}
    sel_path = os.path.join(OUT, "v4p_selection.json")
    json.dump(sel, open(sel_path, "w"), indent=1, sort_keys=True)
    pre = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "spec": "COH-GAIN Amendment 3", "libft8_sha256": got, "build_commit": BUILD_COMMIT,
           "harness_commit": sh("git", "rev-parse", "HEAD").stdout.strip(), "replay81_dll_sha256": R.sha256(os.path.join(HOUT, "Replay81.dll")),
           "cycles": len(cycles), "rows_json_sha256_lf": CG.ROWS_JSON_SHA256, "threads": THREADS, "nhard": 40}
    json.dump(pre, open(os.path.join(OUT, "preflight.json"), "w"), indent=1)
    return pre, sel_path


NR_SELECTION = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-06-nhard-rep", "selection.json")


def pin(when):
    got = R.sha256(os.path.join(HOUT, "libft8.dll"))
    with open(os.path.join(OUT, "pins.jsonl"), "a") as fh:
        fh.write(json.dumps({"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "when": when, "libft8_sha256": got, "pinned": DLL, "match": got == DLL}) + "\n")
    assert got == DLL


def run_replay(sel_path):
    files = {k: os.path.join(OUT, n) for k, n in (("run", "run.csv"), ("log", "log.log"), ("testb", "testb.csv"), ("matched", "matched.csv"),
                                                  ("mb", "matched_batch.csv"), ("abandon", "abandon.csv"), ("probe", "probe.csv"))}
    for f in files.values():
        if os.path.exists(f):
            os.remove(f)
    pin("start")
    cmd = ["dotnet", os.path.join(HOUT, "Replay81.dll"), "--selection", sel_path, "--run", RUN, "--stratum", "V4P", "--wav-root", ART, "--wav-dir", SEL.WAV_DIR,
           "--out", files["run"], "--log", files["log"], "--mode", "two1", "--threads", THREADS, "--nhard", "40", "--label", f"{BUILD_COMMIT}:cg_v4p",
           "--wsjtx-alltxt", SEL.WS_ALLTXT, "--testb-out", files["testb"], "--matched-out", files["matched"], "--matched-batch-out", files["mb"],
           "--abandon-out", files["abandon"], "--probe-vectors", PROBES, "--probe-out", files["probe"]]
    t0 = time.time()
    rc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True).returncode
    pin("end")
    return rc, time.time() - t0, files


def write_manifest(rc, secs, files, pre):
    m = {"spec": "COH-GAIN Amendment 3 (V4' replay)", "harness_rc": rc, "wall_s": round(secs), "preflight": pre,
         "outputs": {k: {"sha256": R.sha256(p), "bytes": os.path.getsize(p)} for k, p in files.items() if os.path.exists(p)},
         "rows_in_run_csv": sum(1 for _ in open(files["run"])) - 1 if os.path.exists(files["run"]) else 0,
         "note": "committed BEFORE V4' is computed (Amendment 3 item 5)"}
    os.makedirs(RESULTS, exist_ok=True)
    json.dump(m, open(MANIFEST, "w"), indent=1, sort_keys=True)
    return m


def main():
    pre, sel_path = preflight()
    print("preflight OK: harness commit", pre["harness_commit"][:8], "DLL", pre["libft8_sha256"][:8], "cycles", pre["cycles"], flush=True)
    if "--preflight-only" in sys.argv:
        return 0
    rc, secs, files = run_replay(sel_path)
    m = write_manifest(rc, secs, files, pre)
    print("replay rc", rc, "wall", round(secs), "s; rows", m["rows_in_run_csv"], "; manifest", MANIFEST, flush=True)
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
