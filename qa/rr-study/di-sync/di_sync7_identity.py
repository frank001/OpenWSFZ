#!/usr/bin/env python3
"""DI sync 7 decode-identity check: the synced build (DI + main, shim 20260070) must decode EXACTLY what plain `main` decodes on the same recorded cycles.

Derived from di_sync_identity.py (sync 5/6). What is new in sync 7: `main` now carries the coherent fallback (batch 4 on Deep) and DI's pass-1 probe tap
shares ft8_decode_all with the fallback's candidate retention, so the cells run the THIRD-PASS (Deep) modes with the fallback flag OFF and ON.

Arms (each a fresh Replay81 process, ascending stamp order, same selection, same settings; recorded audio of the 2026-09-22 night, the step-4 frozen selection):
  MAIN   Replay81 built against a checkout of 74c75792 (origin/main after PR #254, v0.59, shim 20260069)
  SYNC   Replay81 built against a checkout of 56736264 (the Developer's DI sync 7, shim 20260070)
  CTRL2  Replay81 built against 74c75792 with the OSD sign switch OFF (--osd-sign-fix 0): a LARGE, known difference; the SENSITIVITY CONTROL (HK-026)
Cells (mode three1 = Deep, nhard 24, OSD fix on, 8 threads; every 8th cycle of the frozen 961-cycle selection, 121 cycles):
  F0 = --cohfb 0   F1 = --cohfb 1
Pairs compared per cycle, numerically: the harness's outcomes file (stamp, kind, idx, freq, dt, snr, path: no message text) and its matched-out file (WSJT-X line
indices matched). A cycle in which an ORDINARY pass, the third pass or the FALLBACK was abandoned in either arm of a pair is excluded and counted (CPU-load artefact).
  MAIN vs SYNC in F0 and in F1                  expected identical
  MAIN F1 vs SYNC F0 (and MAIN F1 vs MAIN F0)   FALLBACK control: must DIFFER in the cycles with a batch 4 (proves F1 compares something)
  MAIN vs CTRL2 in F0                           OSD control: must DIFFER
VALID only if both controls fire. HK-037: nothing here reads or writes message text.

Usage: python di_sync7_identity.py run | compare
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
RUN = "20260922_2056"
SCR = r"D:\Projects\claude\_qa-scratch\di-sync-verify-7"
SEL = r"D:\Projects\claude\_qa-scratch\coh-fallback\step4\selection.json"
SEL_SHA = "9ce4fbb4b94ae7328bc62697224cc8db918ca03f234d4401830f3501e25f7c28"
WS_ALLTXT = os.path.join(ART, f"{RUN}_endurance_run-gathered", "wsjt-x", "ALL.TXT")
CSPROJ = os.path.join(REPO, "qa", "rr-study", "sub-feas", "replay81", "Replay81.csproj")
OUT = os.path.join(ART, "rr_2026-10-22_di_sync7_identity")
BUILDS = {"MAIN": "74c75792", "SYNC": "56736264", "CTRL2": "74c75792"}
SIGN = {"MAIN": 1, "SYNC": 1, "CTRL2": 0}
CELLS = [("F0", 0), ("F1", 1)]
EVERY = 8


def sha_lf(p):
    return hashlib.sha256(open(p, "rb").read().replace(b"\r\n", b"\n")).hexdigest()


def sh(*a, cwd=REPO):
    return subprocess.run(list(a), cwd=cwd, capture_output=True, text=True)


def selection():
    assert sha_lf(SEL) == SEL_SHA, "the frozen selection changed"
    d = json.load(open(SEL))
    y = d["runs"][RUN]["Y40"]
    assert len(y) == 961
    d["runs"][RUN]["Y40"] = y[::EVERY]
    p = os.path.join(SCR, "selection_every8.json")
    os.makedirs(SCR, exist_ok=True)
    json.dump(d, open(p, "w"))
    return p, len(y[::EVERY])


def build(label):
    if label == "CTRL2":
        return os.path.join(SCR, "out_main")
    co = os.path.join(SCR, "co_" + label.lower())
    out = os.path.join(SCR, "out_" + label.lower())
    if not os.path.isdir(co):
        r = sh("git", "worktree", "add", "--detach", co, BUILDS[label])
        assert r.returncode == 0, r.stderr
    assert sh("git", "rev-parse", "HEAD", cwd=co).stdout.startswith(BUILDS[label])
    assert sh("git", "status", "--porcelain", cwd=co).stdout.strip() == ""
    r = sh("dotnet", "build", CSPROJ, "-c", "Release", f"-p:RepoRoot={co}", "-p:HasSubfeas=true", "-p:HasMaxThreads=true", "-p:HasTwoStage=true",
           "-p:HasOsdSignFix=true", "-p:HasThirdPass=true", "-p:HasCohFb=true", "-p:HasCohFb4=true", "-o", out, "-nologo", "-v", "q")
    assert r.returncode == 0, r.stdout[-800:]
    sh("dotnet", "build-server", "shutdown")
    return out


def run_all():
    os.makedirs(OUT, exist_ok=True)
    sel, n = selection()
    assert n == 121, n
    pins = []
    for label in ("MAIN", "SYNC", "CTRL2"):
        hout = build(label)
        dll = hashlib.sha256(open(os.path.join(hout, "libft8.dll"), "rb").read()).hexdigest()
        pins.append({"arm": label, "commit": BUILDS[label], "libft8_sha256": dll})
        for cell, flag in (CELLS[:1] if label == "CTRL2" else CELLS):
            tag = f"{label}_{cell}"
            f = {k: os.path.join(OUT, f"{k}_{tag}.csv") for k in ("run", "outcomes", "abandon", "matched", "testb", "third", "coh")}
            if os.path.exists(f["run"]) and sum(1 for _ in open(f["run"])) > 1:
                continue
            cmd = ["dotnet", os.path.join(hout, "Replay81.dll"), "--selection", sel, "--run", RUN, "--stratum", "Y40",
                   "--wav-root", ART, "--out", f["run"], "--log", os.path.join(OUT, f"log_{tag}.log"),
                   "--mode", "three1", "--threads", "8", "--nhard", "24", "--osd-sign-fix", str(SIGN[label]), "--cohfb", str(flag),
                   "--cohfb-out", f["coh"], "--label", f"disync7:{tag}", "--wsjtx-alltxt", WS_ALLTXT, "--outcomes", f["outcomes"],
                   "--abandon-out", f["abandon"], "--matched-out", f["matched"], "--testb-out", f["testb"], "--third-out", f["third"]]
            r = subprocess.run(cmd, capture_output=True, text=True)
            print(tag, "rc", r.returncode, r.stderr[-200:], flush=True)
            assert r.returncode == 0
    json.dump(pins, open(os.path.join(OUT, "pins.json"), "w"), indent=1)


def read_by_stamp(path, has_header):
    d = {}
    with open(path, encoding="utf-8") as fh:
        rd = csv.reader(fh)
        if has_header:
            next(rd)
        for row in rd:
            d.setdefault(row[0], []).append(tuple(row))
    return d


def abandoned(tag):
    """Cycles where an ordinary pass (residual), the third pass or the fallback was abandoned in this arm/cell."""
    ab = set()
    with open(os.path.join(OUT, f"abandon_{tag}.csv"), encoding="utf-8") as fh:
        rd = csv.reader(fh)
        next(rd)
        for row in rd:
            if row[2] == "1":
                ab.add(row[0])
    with open(os.path.join(OUT, f"third_{tag}.csv"), encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("outcome") in ("abandoned", "skipped-abandoned"):
                ab.add(row["stamp"])
    with open(os.path.join(OUT, f"coh_{tag}.csv"), encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if int(row.get("abandoned") or 0) > 0:
                ab.add(row["stamp"])
    return ab


def compare_pair(a, b, what):
    oa = read_by_stamp(os.path.join(OUT, f"outcomes_{a}.csv"), False)
    ob = read_by_stamp(os.path.join(OUT, f"outcomes_{b}.csv"), False)
    ma = read_by_stamp(os.path.join(OUT, f"matched_{a}.csv"), True)
    mb = read_by_stamp(os.path.join(OUT, f"matched_{b}.csv"), True)
    ab = abandoned(a) | abandoned(b)
    stamps = sorted(set(ma) | set(mb))
    differ, compared = [], 0
    for s in stamps:
        if s in ab:
            continue
        compared += 1
        if oa.get(s, []) != ob.get(s, []) or ma.get(s, []) != mb.get(s, []):
            differ.append(s)
    return {"pair": f"{a} vs {b}", "what": what, "cycles_in_files": len(stamps), "excluded_abandoned": len(ab & set(stamps)), "compared": compared,
            "cycles_differing": len(differ), "differing_stamps_first10": differ[:10],
            "decodes_a": sum(len(v) for v in oa.values()), "decodes_b": sum(len(v) for v in ob.values())}


def compare():
    ident = [compare_pair("MAIN_F0", "SYNC_F0", "identity, fallback OFF"), compare_pair("MAIN_F1", "SYNC_F1", "identity, fallback ON")]
    ctrl_fb = [compare_pair("MAIN_F1", "SYNC_F0", "fallback control (ON vs OFF)"), compare_pair("MAIN_F1", "MAIN_F0", "fallback control (ON vs OFF, same build)")]
    ctrl_osd = [compare_pair("MAIN_F0", "CTRL2_F0", "OSD control")]
    pins = json.load(open(os.path.join(OUT, "pins.json")))
    rep = {"pins": pins, "identity": ident, "fallback_control": ctrl_fb, "osd_control": ctrl_osd}
    rep["identical_main_sync"] = all(p["cycles_differing"] == 0 and p["compared"] > 0 for p in ident)
    rep["fallback_control_detects"] = all(p["cycles_differing"] > 0 for p in ctrl_fb)
    rep["osd_control_detects"] = all(p["cycles_differing"] > 0 for p in ctrl_osd)
    rep["valid"] = rep["fallback_control_detects"] and rep["osd_control_detects"]       # an identity reading means nothing unless both controls fire
    d = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-22-di-sync-7")
    os.makedirs(d, exist_ok=True)
    json.dump(rep, open(os.path.join(d, "report.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    {"run": run_all, "compare": compare}[sys.argv[1]]()
