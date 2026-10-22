#!/usr/bin/env python3
"""Third-pass (#240) SMOKE test: does Deep work at all? (QA; Captain, 2026-10-18: "a real small sample of the busiest cycles ... 10 to 20 minutes").

THIS IS NOT THE MEASUREMENT. The cycles are the busiest ones (chosen by how many lines the LIVE WSJT-X logged, which is independent of any
Deep output), so any yield seen here is an upper-end illustration for a few cycles and MUST NOT be cited as NET_3. It exercises the build, the
harness (batch 3 as its own kind) and the validity rows V0-V4 on a handful of cycles, so the long run is not wasted on a broken arm.

Corpus: artefacts/20261009_1752_endurance_run-gathered (40 m, OSD-fix era). Arms (each a fresh Replay81 process, same cycles, same order,
subtraction ON, nhard 24, OSD sign fix 1, 8 threads, production 13 s budget on this PC):
  MAIN    Replay81 built against origin/main 535661a2, mode two1 (DecodeTwoStageAsync)
  NORMAL  Replay81 built against feat/third-pass-deep a329cea9, mode three0 (DecodeStagedAsync, depth Normal)
  DEEP    same build, mode three1 (depth Deep)
  DEEP2   a second Deep run (V3: determinism)
Rows: V1 NORMAL == MAIN (outcomes + matched per cycle); V2 DEEP's batch 1+2 == NORMAL's; V3 DEEP == DEEP2 (all batches); V4 cycles abandoned in
ANY pass in EITHER arm are excluded pairwise and counted (fail above 5 % of the cycles). The OSD-sign-OFF control is NOT run in the smoke (it
needs the long run); that means V1 is "equal on these cycles", with no proof the comparison can fail, and says so in the output.
HK-037: aggregates and numeric files only; the harness matches against WSJT-X in-process and writes no message text.

Usage: python third_pass_smoke.py prep | run | compare   [--n 20]
"""
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ART = r"D:\Projects\claude\OpenWSFZ\artefacts"
RUN = "20261009_1752"
GATH = os.path.join(ART, f"{RUN}_endurance_run-gathered")
WAV_DIR = os.path.join(GATH, "owsfz", "wav")
WS_ALLTXT = os.path.join(GATH, "wsjt-x", "ALL.TXT")
CSPROJ = os.path.join(REPO, "qa", "rr-study", "sub-feas", "replay81", "Replay81.csproj")
SCR = r"D:\Projects\claude\_qa-scratch\third-pass-verify"
OUT = os.path.join(SCR, "smoke")
BUILD = {"MAIN": "535661a2", "NORMAL": "a329cea9", "DEEP": "a329cea9", "DEEP2": "a329cea9"}
MODE = {"MAIN": "two1", "NORMAL": "three0", "DEEP": "three1", "DEEP2": "three1"}
ARMS = ["MAIN", "NORMAL", "DEEP", "DEEP2"]
STRATUM = "SMK"
ABANDON_FAIL_SHARE = 0.05          # spec Amendment 1, A2: the Architect's judgement, not data


def sh(*a, cwd=REPO):
    return subprocess.run(list(a), cwd=cwd, capture_output=True, text=True)


def n_arg():
    return int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 20


def prep():
    """Selection: the N cycles with the most live WSJT-X FT8 lines that also have a WAV. Counts only."""
    have = {f[:-4] for f in os.listdir(WAV_DIR) if f.endswith(".wav")}
    cnt = Counter()
    for line in open(WS_ALLTXT, encoding="utf-8", errors="replace"):
        f = line.split()
        if len(f) >= 8 and f[2] == "Rx" and f[3] == "FT8" and f[0] in have:
            cnt[f[0]] += 1
    top = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[: n_arg()]
    stamps = sorted(s for s, _ in top)                       # decode in time order (callsign hash history is process-global)
    warm = sorted(have - set(stamps))[0]
    os.makedirs(SCR, exist_ok=True)
    sel = os.path.join(SCR, "selection_smoke.json")
    json.dump({"runs": {RUN: {"warmup": warm, STRATUM: stamps}}}, open(sel, "w"))
    print("selected", len(stamps), "cycles; live WSJT-X lines per selected cycle: min", min(c for _, c in top), "max", max(c for _, c in top),
          "mean %.1f" % (sum(c for _, c in top) / len(top)), "| selection sha256", hashlib.sha256(open(sel, "rb").read()).hexdigest()[:16])


def build(arm):
    commit = BUILD[arm]
    key = commit
    co = os.path.join(SCR, "co_" + key)
    out = os.path.join(SCR, "out_" + ("main" if arm == "MAIN" else "third"))
    if arm in ("DEEP", "DEEP2", "NORMAL") and arm != "NORMAL":
        return out                                           # one build for the three third-pass arms
    if not os.path.isdir(co):
        r = sh("git", "worktree", "add", "--detach", co, commit)
        assert r.returncode == 0, r.stderr
    assert sh("git", "rev-parse", "HEAD", cwd=co).stdout.startswith(commit)
    flags = ["-p:HasSubfeas=true", "-p:HasMaxThreads=true", "-p:HasTwoStage=true", "-p:HasOsdSignFix=true"]
    if arm != "MAIN":
        flags.append("-p:HasThirdPass=true")
    r = sh("dotnet", "build", CSPROJ, "-c", "Release", f"-p:RepoRoot={co}", *flags, "-o", out, "-nologo", "-v", "q")
    assert r.returncode == 0, r.stdout[-800:]
    sh("dotnet", "build-server", "shutdown")
    return out


def run_all():
    os.makedirs(OUT, exist_ok=True)
    sel = os.path.join(SCR, "selection_smoke.json")
    assert os.path.exists(sel), "run prep first"
    pins = []
    for arm in ARMS:
        hout = build(arm)
        dll = hashlib.sha256(open(os.path.join(hout, "libft8.dll"), "rb").read()).hexdigest()
        pins.append({"arm": arm, "commit": BUILD[arm], "mode": MODE[arm], "libft8_sha256": dll})
        f = {k: os.path.join(OUT, f"{k}_{arm}.csv") for k in ("run", "outcomes", "abandon", "matched", "matchedbatch", "testb", "third")}
        if os.path.exists(f["run"]) and sum(1 for _ in open(f["run"])) > 1:
            continue
        cmd = ["dotnet", os.path.join(hout, "Replay81.dll"), "--selection", sel, "--run", RUN, "--stratum", STRATUM, "--wav-root", ART,
               "--wav-dir", WAV_DIR, "--out", f["run"], "--log", os.path.join(OUT, f"log_{arm}.log"), "--mode", MODE[arm], "--threads", "8",
               "--nhard", "24", "--osd-sign-fix", "1", "--label", f"third-pass-smoke:{arm}", "--wsjtx-alltxt", WS_ALLTXT,
               "--outcomes", f["outcomes"], "--abandon-out", f["abandon"], "--matched-out", f["matched"],
               "--matched-batch-out", f["matchedbatch"], "--testb-out", f["testb"], "--third-out", f["third"]]
        r = subprocess.run(cmd, capture_output=True, text=True)
        print(arm, "rc", r.returncode, r.stderr[-200:], flush=True)
        assert r.returncode == 0
    json.dump(pins, open(os.path.join(OUT, "pins.json"), "w"), indent=1)


def rows(path, key=0):
    d = {}
    if not os.path.exists(path):
        return d
    with open(path, encoding="utf-8") as fh:
        rd = csv.reader(fh)
        next(rd, None)
        for row in rd:
            d.setdefault(row[key], []).append(tuple(row))
    return d


def outcomes(arm):
    d = {}
    p = os.path.join(OUT, f"outcomes_{arm}.csv")
    for line in open(p, encoding="utf-8"):
        s = line.rstrip("\n").split(",")
        d.setdefault(s[0], []).append(tuple(s[1:]))          # (kind, idx, freq, dt, snr)
    return d


def abandoned(arm):
    ab = set()
    for s, r in rows(os.path.join(OUT, f"abandon_{arm}.csv")).items():
        if r[0][2] == "1" or r[0][3] == "1":
            ab.add(s)
    for s, r in rows(os.path.join(OUT, f"third_{arm}.csv")).items():
        if r[0][1] in ("abandoned", "failed"):
            ab.add(s)
    return ab


def kinds(o, ks):
    return {s: [r for r in v if r[0] in ks] for s, v in o.items()}


def compare():
    O = {a: outcomes(a) for a in ARMS}
    M = {a: rows(os.path.join(OUT, f"matched_{a}.csv")) for a in ARMS}
    AB = {a: abandoned(a) for a in ARMS}
    stamps = sorted(json.load(open(os.path.join(SCR, "selection_smoke.json")))["runs"][RUN][STRATUM])
    n = len(stamps)

    def pair(a, b, ks, label):
        ex = AB[a] | AB[b]
        use = [s for s in stamps if s not in ex]
        diff = [s for s in use if kinds(O[a], ks).get(s, []) != kinds(O[b], ks).get(s, [])]
        return {"row": label, "pair": f"{a} vs {b}", "cycles": n, "excluded_abandoned": len(ex & set(stamps)), "compared": len(use),
                "cycles_differing": len(diff), "differing_first5": diff[:5]}

    # V1: NORMAL's batch 1+2 equal MAIN's (MAIN has no batch 3)
    v1 = pair("MAIN", "NORMAL", {"b1", "b2"}, "V1 NORMAL == MAIN (batches 1+2)")
    v1m = [s for s in stamps if s not in (AB["MAIN"] | AB["NORMAL"]) and M["MAIN"].get(s) != M["NORMAL"].get(s)]
    v1["matched_cycles_differing"] = len(v1m)
    v1["normal_has_batch3_rows"] = sum(1 for v in O["NORMAL"].values() for r in v if r[0] == "b3")
    v2 = pair("NORMAL", "DEEP", {"b1", "b2"}, "V2 DEEP batches 1+2 == NORMAL")
    v3 = pair("DEEP", "DEEP2", {"b1", "b2", "b3"}, "V3 DEEP == DEEP2 (all batches)")
    v3m = [s for s in stamps if s not in (AB["DEEP"] | AB["DEEP2"]) and M["DEEP"].get(s) != M["DEEP2"].get(s)]
    v3["matched_cycles_differing"] = len(v3m)
    anyab = set()
    for a in ARMS:
        anyab |= AB[a] & set(stamps)
    v4 = {"row": "V4 abandoned in any pass, any arm (excluded pairwise)", "cycles": n, "abandoned_cycles_union": len(anyab),
          "share": round(len(anyab) / n, 3), "fail_above": ABANDON_FAIL_SHARE, "result": "PASS" if len(anyab) / n <= ABANDON_FAIL_SHARE else "FAIL"}
    # SMOKE view of the third pass (NOT NET_3): outcomes, timing, batch-3 decode counts, how many were WSJT-X-matched
    th = rows(os.path.join(OUT, "third_DEEP.csv"))
    oc = Counter(r[0][1] for r in th.values())
    ms = sorted(int(r[0][3]) for r in th.values() if r[0][1] == "ran")
    b3n = sum(1 for v in O["DEEP"].values() for r in v if r[0] == "b3")
    mb = rows(os.path.join(OUT, "matchedbatch_DEEP.csv"))
    b3m = 0
    for v in mb.values():
        for cell in v[0][1].split(";") if len(v[0]) > 1 and v[0][1] else []:
            if cell.endswith(":3"):
                b3m += 1
    b1n = sum(1 for v in O["DEEP"].values() for r in v if r[0] == "b1")
    b2n = sum(1 for v in O["DEEP"].values() for r in v if r[0] == "b2")
    q = lambda xs, f: xs[min(len(xs) - 1, int(f * len(xs)))] if xs else None
    smoke = {"note": "SMOKE ONLY: busiest cycles, tiny sample, production budget on this PC. Not NET_3. Do not cite.",
             "third_pass_outcomes_by_cycle": dict(oc), "ran_ms_median_p90_max": [q(ms, .5), q(ms, .9), ms[-1] if ms else None],
             "batch1_decodes": b1n, "batch2_decodes": b2n, "batch3_decodes": b3n, "batch3_matched_to_WSJTX": b3m,
             "batch3_OWS_only": b3n - b3m}
    pins = json.load(open(os.path.join(OUT, "pins.json")))
    rep = {"pins": pins, "cycles": n, "rows": [v1, v2, v3, v4], "smoke": smoke,
           "control": "NOT RUN in the smoke (OSD-sign-OFF control): V1 is 'equal on these cycles', not proof that the check can fail"}
    d = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-18-third-pass-smoke")
    os.makedirs(d, exist_ok=True)
    json.dump(rep, open(os.path.join(d, "report.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    {"prep": prep, "run": run_all, "compare": compare}[sys.argv[1]]()
