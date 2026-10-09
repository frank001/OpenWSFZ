#!/usr/bin/env python3
"""DI sync 5 decode-identity check: the synced build must decode EXACTLY what plain `main` decodes on the same recorded cycles.

Why: the Developer's sync (merge commit 421e3ce2: origin/decoding_improvement 87dcc387 + origin/main 9fe32e8d) is meant to change no decoder
output; DI's extras (pass-1 probe tap, decoder-parameter table, runtime suppression setter, named constants) are diagnostic.
This script TESTS that claim instead of reading it from commit subjects.

Arms (each a fresh Replay81 process, ascending stamp order, same selection, same settings; recorded audio of the 2026-09-30 night):
  MAIN   Replay81 built against a checkout of 9fe32e8d
  SYNC   Replay81 built against a checkout of 421e3ce2
  CTRL   Replay81 built against 9fe32e8d with ONE setting changed (--nhard 30): the SENSITIVITY CONTROL. The comparison must flag it;
         if it did not, an "identical" result between MAIN and SYNC would mean nothing (HK-026).
Cells: mode two0 (flag OFF) on stratum S10 (430 cycles) and mode two1 (flag ON, 8 threads) on stratum S40 (every 4th of S10, 108 cycles).
Compared per cycle, numerically: the harness's outcomes file (stamp, kind, idx, freq, dt, snr per decode: no message text) and its matched-out file
(WSJT-X line indices matched, which depends on the text). A cycle abandoned in either arm of a pair is excluded and counted (CPU-load artefact).
HK-037: nothing here reads or writes message text.

Usage: python di_sync_identity.py run     (builds, runs all arms; resumable per arm)
       python di_sync_identity.py compare (writes results/<date>-di-sync-5/report.json)
"""
import csv
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ART = os.path.join(REPO, "artefacts")
RUN = "20260930_1930"
SCR = r"D:\Projects\claude\_qa-scratch\di-sync-verify"
SEL10 = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-09-density-sub", "selection.json")
SEL10_SHA = "04bb0818aed05142beb7c1cad1a365d01e3f77705573c1e91a201c16dfe58e5f"
WAV_DIR = os.path.join(ART, f"{RUN}_endurance_run-gathered", "owsfz", "wav")
WS_ALLTXT = os.path.join(ART, f"{RUN}_endurance_run-gathered", "wsjt-x", "ALL.TXT")
CSPROJ = os.path.join(REPO, "qa", "rr-study", "sub-feas", "replay81", "Replay81.csproj")
OUT = os.path.join(ART, "rr_2026-10-09_di_sync_identity")
BUILDS = {"MAIN": "9fe32e8d", "SYNC": "421e3ce2", "CTRL": "9fe32e8d", "CTRL2": "9fe32e8d"}
NHARD = {"MAIN": 24, "SYNC": 24, "CTRL": 30, "CTRL2": 24}
SIGN = {"MAIN": 1, "SYNC": 1, "CTRL": 1, "CTRL2": 0}   # CTRL2: the OSD sign switch OFF (the old inverted behaviour): a LARGE, known difference
CELLS = [("two0", "S10"), ("two1", "S40")]


def sha_lf(p):
    return hashlib.sha256(open(p, "rb").read().replace(b"\r\n", b"\n")).hexdigest()


def sh(*a, cwd=REPO):
    return subprocess.run(list(a), cwd=cwd, capture_output=True, text=True)


def selection():
    assert sha_lf(SEL10) == SEL10_SHA, "S10 selection changed"
    d = json.load(open(SEL10))
    s10 = d["runs"][RUN]["S10"]
    d["runs"][RUN]["S40"] = s10[::4]
    p = os.path.join(SCR, "selection_s40.json")
    os.makedirs(SCR, exist_ok=True)
    json.dump(d, open(p, "w"))
    return p, len(s10), len(s10[::4])


def build(label):
    co = os.path.join(SCR, "co_" + label.lower())
    out = os.path.join(SCR, "out_" + label.lower())
    if label in ("CTRL", "CTRL2"):           # the controls reuse MAIN's build
        return os.path.join(SCR, "out_main")
    if not os.path.isdir(co):
        r = sh("git", "worktree", "add", "--detach", co, BUILDS[label])
        assert r.returncode == 0, r.stderr
    assert sh("git", "rev-parse", "HEAD", cwd=co).stdout.startswith(BUILDS[label])
    assert sh("git", "status", "--porcelain", cwd=co).stdout.strip() == ""
    r = sh("dotnet", "build", CSPROJ, "-c", "Release", f"-p:RepoRoot={co}", "-p:HasSubfeas=true", "-p:HasMaxThreads=true",
           "-p:HasTwoStage=true", "-p:HasOsdSignFix=true", "-o", out, "-nologo", "-v", "q")
    assert r.returncode == 0, r.stdout[-800:]
    sh("dotnet", "build-server", "shutdown")
    return out


def run_all():
    os.makedirs(OUT, exist_ok=True)
    sel, n10, n40 = selection()
    assert (n10, n40) == (430, 108), (n10, n40)
    pins = []
    for label in ("MAIN", "SYNC", "CTRL", "CTRL2"):
        hout = build(label)
        dll = hashlib.sha256(open(os.path.join(hout, "libft8.dll"), "rb").read()).hexdigest()
        pins.append({"arm": label, "commit": BUILDS[label], "libft8_sha256": dll})
        for mode, stratum in (CELLS[:1] if label == "CTRL2" else CELLS):
            tag = f"{label}_{mode}"
            f = {k: os.path.join(OUT, f"{k}_{tag}.csv") for k in ("run", "outcomes", "abandon", "matched", "testb")}
            if os.path.exists(f["run"]) and sum(1 for _ in open(f["run"])) > 1:
                continue                      # already done
            cmd = ["dotnet", os.path.join(hout, "Replay81.dll"), "--selection", sel, "--run", RUN, "--stratum", stratum,
                   "--wav-root", ART, "--wav-dir", WAV_DIR, "--out", f["run"], "--log", os.path.join(OUT, f"log_{tag}.log"),
                   "--mode", mode, "--threads", "8", "--nhard", str(NHARD[label]), "--osd-sign-fix", str(SIGN[label]),
                   "--label", f"disync5:{tag}", "--wsjtx-alltxt", WS_ALLTXT, "--outcomes", f["outcomes"],
                   "--abandon-out", f["abandon"], "--matched-out", f["matched"], "--testb-out", f["testb"]]
            r = subprocess.run(cmd, capture_output=True, text=True)
            print(tag, "rc", r.returncode, r.stderr[-200:], flush=True)
            assert r.returncode == 0
    json.dump(pins, open(os.path.join(OUT, "pins.json"), "w"), indent=1)


def read_by_stamp(path, has_header, key_col=0):
    d = {}
    with open(path, encoding="utf-8") as fh:
        rd = csv.reader(fh)
        if has_header:
            next(rd)
        for row in rd:
            d.setdefault(row[key_col], []).append(tuple(row))
    return d


def abandoned(path):
    ab = set()
    with open(path, encoding="utf-8") as fh:
        rd = csv.reader(fh)
        next(rd)
        for row in rd:
            if row[2] == "1":
                ab.add(row[0])
    return ab


def compare_pair(a, b, mode):
    """Per cycle: outcomes rows and matched indices must be EXACTLY equal. Abandoned-in-either cycles are excluded and counted."""
    oa = read_by_stamp(os.path.join(OUT, f"outcomes_{a}_{mode}.csv"), False)
    ob = read_by_stamp(os.path.join(OUT, f"outcomes_{b}_{mode}.csv"), False)
    ma = read_by_stamp(os.path.join(OUT, f"matched_{a}_{mode}.csv"), True)
    mb = read_by_stamp(os.path.join(OUT, f"matched_{b}_{mode}.csv"), True)
    ab = abandoned(os.path.join(OUT, f"abandon_{a}_{mode}.csv")) | abandoned(os.path.join(OUT, f"abandon_{b}_{mode}.csv"))
    stamps = sorted(set(ma) | set(mb))
    differ, compared = [], 0
    for s in stamps:
        if s in ab:
            continue
        compared += 1
        if oa.get(s, []) != ob.get(s, []) or ma.get(s, []) != mb.get(s, []):
            differ.append(s)
    return {"pair": f"{a} vs {b}", "mode": mode, "cycles_in_files": len(stamps), "excluded_abandoned": len(ab & set(stamps)),
            "compared": compared, "cycles_differing": len(differ), "differing_stamps_first10": differ[:10],
            "decodes_a": sum(len(v) for v in oa.values()), "decodes_b": sum(len(v) for v in ob.values())}


def compare():
    out = ([compare_pair("MAIN", "SYNC", m) for m, _ in CELLS] + [compare_pair("MAIN", "CTRL", m) for m, _ in CELLS]
           + [compare_pair("MAIN", "CTRL2", "two0")])
    pins = json.load(open(os.path.join(OUT, "pins.json")))
    rep = {"pins": pins, "pairs": out}
    main_sync = [p for p in out if p["pair"] == "MAIN vs SYNC"]
    ctrl = [p for p in out if p["pair"] == "MAIN vs CTRL2"]      # CTRL (nhard 30) proved too weak a control: it moves 1 decode in 430 cycles; reported, not used
    rep["identical_main_sync"] = all(p["cycles_differing"] == 0 and p["compared"] > 0 for p in main_sync)
    rep["control_detects_difference"] = all(p["cycles_differing"] > 0 for p in ctrl)
    rep["valid"] = rep["control_detects_difference"]            # an identity reading means nothing unless the control fires
    d = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-09-di-sync-5")
    os.makedirs(d, exist_ok=True)
    json.dump(rep, open(os.path.join(d, "report.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    {"run": run_all, "compare": compare}[sys.argv[1]]()
