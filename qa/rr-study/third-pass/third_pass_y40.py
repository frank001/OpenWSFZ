#!/usr/bin/env python3
"""Third pass (#240) Y-40: the pre-registered yield run (spec 2026-10-18-1205 + Amendment 1; QA corpus note 2026-10-18-1234).

Corpus: artefacts/20261009_1752_endurance_run-gathered (40 m, OSD-fix era). Selection RULE (fixed before any Deep data): every 8th WAV of the
sorted list starting at the first (`NR%8==1`), 455 cycles. Arms (each a fresh Replay81 process, same cycles in the same order, subtraction ON,
nhard 24, 8 threads, the production 13 s budget on this PC; no live daemon running):
  MAIN    origin/main 535661a2, mode two1                         (V1 reference)
  NORMAL  feat/third-pass-deep a329cea9, mode three0              (decoding depth Normal)
  DEEP    same build, mode three1                                 (depth Deep)
  DEEP2   a second Deep run                                       (V3)
  CTRL    origin/main 535661a2, mode two1, OSD sign switch OFF    (V1's sensitivity control: it must move >= 1 cycle, HK-026)
Validity rows (Amendment 1): V0 pins + read-back, V1 NORMAL == MAIN and CTRL != MAIN, V2 DEEP batches 1+2 == NORMAL, V3 DEEP == DEEP2 on cycles with
no abandon in either run, V4 cycles abandoned in ANY pass in EITHER arm are excluded pairwise and counted; V4 FAILS above 5 % (the Architect's
judgement, stated as such). Measurement rows M1 (NET_3, cycle-clustered bootstrap CI), M2, M3 (PC timing), M4: reported, no pass/fail.
HK-037: aggregates and numeric files only; the harness matches against WSJT-X in-process.

Usage: python third_pass_y40.py prep | run | compare
"""
import csv
import hashlib
import json
import os
import platform
import random
import re
import statistics
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
OUT = os.path.join(SCR, "y40")
STRATUM = "Y40"
EVERY = 8                                            # the pre-registered subsample rule
EXPECTED_CYCLES = 455                                # asserted: ceil(3634 / 8)
BUILD = {"MAIN": "535661a2", "NORMAL": "a329cea9", "DEEP": "a329cea9", "DEEP2": "a329cea9", "CTRL": "535661a2"}
MODE = {"MAIN": "two1", "NORMAL": "three0", "DEEP": "three1", "DEEP2": "three1", "CTRL": "two1"}
SIGN = {"MAIN": 1, "NORMAL": 1, "DEEP": 1, "DEEP2": 1, "CTRL": 0}
ARMS = ["MAIN", "NORMAL", "DEEP", "DEEP2", "CTRL"]
ABANDON_FAIL_SHARE = 0.05                            # Amendment 1 A2: the Architect's judgement, not data
BOOT_N, BOOT_SEED = 2000, 20261018


def sh(*a, cwd=REPO):
    return subprocess.run(list(a), cwd=cwd, capture_output=True, text=True)


def prep():
    wavs = sorted(f[:-4] for f in os.listdir(WAV_DIR) if f.endswith(".wav"))
    stamps = wavs[::EVERY]
    assert len(stamps) == EXPECTED_CYCLES, len(stamps)
    warm = sorted(set(wavs) - set(stamps))[0]
    os.makedirs(SCR, exist_ok=True)
    sel = os.path.join(SCR, "selection_y40.json")
    json.dump({"runs": {RUN: {"warmup": warm, STRATUM: stamps}}}, open(sel, "w"))
    print("selected", len(stamps), "cycles of", len(wavs), "| first", stamps[0], "last", stamps[-1], "| selection sha256",
          hashlib.sha256(open(sel, "rb").read()).hexdigest()[:16])


def build(arm):
    commit = BUILD[arm]
    co = os.path.join(SCR, "co_" + commit)
    out = os.path.join(SCR, "out_third" if commit == "a329cea9" else "out_main")
    if os.path.exists(os.path.join(out, "Replay81.dll")):
        return out
    if not os.path.isdir(co):
        r = sh("git", "worktree", "add", "--detach", co, commit)
        assert r.returncode == 0, r.stderr
    assert sh("git", "rev-parse", "HEAD", cwd=co).stdout.startswith(commit)
    flags = ["-p:HasSubfeas=true", "-p:HasMaxThreads=true", "-p:HasTwoStage=true", "-p:HasOsdSignFix=true"]
    if commit == "a329cea9":
        flags.append("-p:HasThirdPass=true")
    r = sh("dotnet", "build", CSPROJ, "-c", "Release", f"-p:RepoRoot={co}", *flags, "-o", out, "-nologo", "-v", "q")
    assert r.returncode == 0, r.stdout[-800:]
    sh("dotnet", "build-server", "shutdown")
    return out


def procs_running():
    r = sh("powershell.exe", "-NoProfile", "-Command",
           "(Get-Process | Where-Object { $_.ProcessName -match 'OpenWSFZ|wsjt|jt9' }).Count")
    return r.stdout.strip()


def run_all():
    os.makedirs(OUT, exist_ok=True)
    sel = os.path.join(SCR, "selection_y40.json")
    assert os.path.exists(sel), "run prep first"
    env = {"cpu": platform.processor(), "cores": os.cpu_count(), "threads_arg": 8, "daemon_or_wsjtx_processes_at_start": procs_running()}
    pins = []
    for arm in ARMS:
        hout = build(arm)
        dll = hashlib.sha256(open(os.path.join(hout, "libft8.dll"), "rb").read()).hexdigest()
        pins.append({"arm": arm, "commit": BUILD[arm], "mode": MODE[arm], "osd_sign_fix": SIGN[arm], "libft8_sha256": dll})
        f = {k: os.path.join(OUT, f"{k}_{arm}.csv") for k in ("run", "outcomes", "abandon", "matched", "matchedbatch", "testb", "third")}
        if os.path.exists(f["run"]) and sum(1 for _ in open(f["run"])) - 1 >= EXPECTED_CYCLES:
            continue                                   # arm complete; a partial arm resumes inside the harness
        cmd = ["dotnet", os.path.join(hout, "Replay81.dll"), "--selection", sel, "--run", RUN, "--stratum", STRATUM, "--wav-root", ART,
               "--wav-dir", WAV_DIR, "--out", f["run"], "--log", os.path.join(OUT, f"log_{arm}.log"), "--mode", MODE[arm], "--threads", "8",
               "--nhard", "24", "--osd-sign-fix", str(SIGN[arm]), "--label", f"third-pass-y40:{arm}", "--wsjtx-alltxt", WS_ALLTXT,
               "--outcomes", f["outcomes"], "--abandon-out", f["abandon"], "--matched-out", f["matched"],
               "--matched-batch-out", f["matchedbatch"], "--testb-out", f["testb"], "--third-out", f["third"]]
        r = subprocess.run(cmd, capture_output=True, text=True)
        print(arm, "rc", r.returncode, r.stderr[-200:], flush=True)
        assert r.returncode == 0
    env["daemon_or_wsjtx_processes_at_end"] = procs_running()
    json.dump({"pins": pins, "env": env}, open(os.path.join(OUT, "pins.json"), "w"), indent=1)


# ------------------------------------------------------------------------------------------------ compare

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
    for line in open(os.path.join(OUT, f"outcomes_{arm}.csv"), encoding="utf-8"):
        s = line.rstrip("\n").split(",")
        d.setdefault(s[0], []).append(tuple(s[1:]))
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


def matched_count(arm):
    d = {}
    for s, r in rows(os.path.join(OUT, f"matched_{arm}.csv")).items():
        cell = r[0][1] if len(r[0]) > 1 else ""
        d[s] = len([x for x in cell.split(";") if x != ""])
    return d


def ws_total(arm):
    d = {}
    for s, r in rows(os.path.join(OUT, f"testb_{arm}.csv"), 1).items():
        for x in r:
            if x[2] == "ws":
                d[s] = int(x[4])
    return d


def kinds(o, ks):
    return {s: [r for r in v if r[0] in ks] for s, v in o.items()}


def readbacks(arm):
    out = []
    for line in open(os.path.join(OUT, f"log_{arm}.log"), encoding="utf-8", errors="replace"):
        if line.startswith("# readback"):
            out.append(line.strip())
    return out


def bootstrap(per_cycle, stamps, num, den, seed=BOOT_SEED, n=BOOT_N):
    rnd = random.Random(seed)
    vals = []
    for _ in range(n):
        draw = [stamps[rnd.randrange(len(stamps))] for _ in stamps]
        d = sum(per_cycle[s][den] for s in draw)
        vals.append(100.0 * sum(per_cycle[s][num] for s in draw) / d if d else 0.0)
    vals.sort()
    return vals[int(0.025 * n)], vals[int(0.975 * n)]


def compare():
    sel = json.load(open(os.path.join(SCR, "selection_y40.json")))["runs"][RUN][STRATUM]
    stamps = sorted(sel)
    n = len(stamps)
    O = {a: outcomes(a) for a in ARMS}
    M = {a: rows(os.path.join(OUT, f"matched_{a}.csv")) for a in ARMS}
    AB = {a: abandoned(a) & set(stamps) for a in ARMS}
    meta = json.load(open(os.path.join(OUT, "pins.json")))
    pins = meta["pins"]

    def pair(a, b, ks, label):
        ex = AB[a] | AB[b]
        use = [s for s in stamps if s not in ex]
        diff = [s for s in use if kinds(O[a], ks).get(s, []) != kinds(O[b], ks).get(s, [])]
        mdiff = [s for s in use if M[a].get(s) != M[b].get(s)]
        return {"row": label, "pair": f"{a} vs {b}", "cycles": n, "excluded_abandoned": len(ex), "compared": len(use),
                "cycles_differing": len(diff), "matched_cycles_differing": len(mdiff), "differing_first5": diff[:5]}

    # V0
    rb = {a: readbacks(a) for a in ARMS}
    v0_ok, v0_notes = True, []
    for a in ARMS:
        pin = next(p for p in pins if p["arm"] == a)
        starts = [x for x in rb[a] if " start " in x]
        ends = [x for x in rb[a] if " end " in x]
        strip = lambda x: re.sub(r"^# readback (start|end) ", "", x)
        same = bool(starts) and bool(ends) and strip(starts[0]) == strip(ends[0])
        has = bool(starts) and "nhard=24" in starts[0] and f"osdSignFixRead={SIGN[a]}" in starts[0] and "subtractionEnabled=True" in starts[0]
        depth_ok = True
        if MODE[a].startswith("three"):
            want = "Deep" if MODE[a] == "three1" else "Normal"
            depth_ok = bool(starts) and f"decodingDepth={want}" in starts[0]
        ok = same and has and depth_ok
        v0_ok &= ok
        v0_notes.append({"arm": a, "start_equals_end": same, "settings_ok": has, "depth_ok": depth_ok, "dll_sha256_16": pin["libft8_sha256"][:16]})
    dlls = {p["libft8_sha256"] for p in pins}
    v0 = {"row": "V0 pins and read-back", "result": "PASS" if v0_ok and len(dlls) == 1 else "FAIL", "one_dll_for_all_arms": len(dlls) == 1, "arms": v0_notes}

    v1 = pair("MAIN", "NORMAL", {"b1", "b2"}, "V1 NORMAL == MAIN (batches 1+2)")
    v1["normal_has_batch3_rows"] = sum(1 for v in O["NORMAL"].values() for r in v if r[0] == "b3")
    ctrl = pair("MAIN", "CTRL", {"b1", "b2"}, "V1 control: OSD sign OFF must move >= 1 cycle")
    v1["control_cycles_differing"] = ctrl["cycles_differing"]
    v1["result"] = "PASS" if v1["cycles_differing"] == 0 and v1["matched_cycles_differing"] == 0 and ctrl["cycles_differing"] >= 1 else "FAIL"
    v2 = pair("NORMAL", "DEEP", {"b1", "b2"}, "V2 DEEP batches 1+2 == NORMAL")
    # The matched-out files of DEEP include the WSJT-X lines matched by BATCH 3 by construction, so comparing them whole against NORMAL's is not a test of "batches 1+2 are
    # untouched" (QA error in the first compare, 2026-10-18 14:07Z: it reported 53 differing cycles). The matched component of V2 compares only the matches attributed to
    # batch 1 or 2 (matched-batch-out, idx:batch); the decode-set component (outcomes) is the spec's V2 as written.
    def m12(arm):
        d = {}
        for s_, r_ in rows(os.path.join(OUT, f"matchedbatch_{arm}.csv")).items():
            cells = r_[0][1].split(";") if len(r_[0]) > 1 and r_[0][1] else []
            d[s_] = sorted(c for c in cells if c.endswith(":1") or c.endswith(":2"))
        return d
    mN12, mD12 = m12("NORMAL"), m12("DEEP")
    v2["matched_cycles_differing_whole_file_NOT_a_valid_test"] = v2["matched_cycles_differing"]
    v2["matched_cycles_differing"] = len([s_ for s_ in stamps if s_ not in (AB["NORMAL"] | AB["DEEP"]) and mN12.get(s_, []) != mD12.get(s_, [])])
    v2["result"] = "PASS" if v2["cycles_differing"] == 0 and v2["matched_cycles_differing"] == 0 else "FAIL"
    v3 = pair("DEEP", "DEEP2", {"b1", "b2", "b3"}, "V3 DEEP == DEEP2 (cycles with no abandon in either)")
    v3["result"] = "PASS" if v3["cycles_differing"] == 0 and v3["matched_cycles_differing"] == 0 else "FAIL"
    anyab = set()
    for a in ["MAIN", "NORMAL", "DEEP", "DEEP2"]:
        anyab |= AB[a]
    v4 = {"row": "V4 abandoned in any pass, any arm", "cycles": n, "abandoned_cycles_union": len(anyab), "share": round(len(anyab) / n, 4),
          "fail_above": ABANDON_FAIL_SHARE, "result": "PASS" if len(anyab) / n <= ABANDON_FAIL_SHARE else "FAIL"}
    valid = all(r["result"] == "PASS" for r in (v0, v1, v2, v3, v4))

    rep = {"corpus": f"{RUN} (40 m), every {EVERY}th WAV = {n} cycles", "pins": pins, "env": meta["env"], "rows": [v0, v1, ctrl, v2, v3, v4],
           "all_validity_rows_pass": valid}

    # Measurement rows (reported whatever the validity result, but flagged WITHHELD when a V-row failed: Amendment 1 stop scope)
    use = [s for s in stamps if s not in (AB["NORMAL"] | AB["DEEP"])]
    mN, mD, ws = matched_count("NORMAL"), matched_count("DEEP"), ws_total("DEEP")
    per = {s: {"net": mD.get(s, 0) - mN.get(s, 0), "ws": ws.get(s, 0)} for s in use}
    wsum = sum(p["ws"] for p in per.values())
    net_pp = 100.0 * sum(p["net"] for p in per.values()) / wsum if wsum else 0.0
    lo, hi = bootstrap(per, use, "net", "ws")
    b3_rows = [r for s in use for r in O["DEEP"].get(s, []) if r[0] == "b3"]
    tb3 = {"matched": 0, "n": 0}
    band = {k: [0, 0] for k in "ABCD"}
    for s in use:
        for x in rows(os.path.join(OUT, "testb_DEEP.csv"), 1).get(s, []):
            if x[2] == "b3":
                tb3["n"] += int(x[4]); tb3["matched"] += int(x[5])
                band[x[3]][0] += int(x[4]); band[x[3]][1] += int(x[5])
    th = rows(os.path.join(OUT, "third_DEEP.csv"))
    oc_all = Counter(r[0][1] for s, r in th.items() if s in use)
    started = oc_all["ran"] + oc_all["abandoned"] + oc_all["failed"]
    ms = sorted(int(r[0][3]) for s, r in th.items() if s in use and r[0][1] == "ran")
    q = lambda xs, f: xs[min(len(xs) - 1, int(f * len(xs)))] if xs else None
    runN = {r[2]: float(r[5]) for r in csv.reader(open(os.path.join(OUT, "run_NORMAL.csv"))) if r[0] != "run"}
    runD = {r[2]: float(r[5]) for r in csv.reader(open(os.path.join(OUT, "run_DEEP.csv"))) if r[0] != "run"}
    cyc_n = [runN[s] for s in use if s in runN]
    cyc_d = [runD[s] for s in use if s in runD]
    rep["measurement"] = {
        "status": "REPORTED" if valid else "WITHHELD: a validity row failed on Y-40 (Amendment 1: its rows are withheld)",
        "cycles_used_pairwise": len(use), "NET_3_pp_of_WSJTX_decodes": round(net_pp, 3), "NET_3_95CI_cycle_bootstrap": [round(lo, 3), round(hi, 3)],
        "bootstrap": f"{BOOT_N} cycle draws, seed {BOOT_SEED}", "wsjtx_decodes_in_cycles": wsum,
        "M2_batch3_decodes": len(b3_rows), "M2_per_cycle": round(len(b3_rows) / len(use), 3) if use else None,
        "M2_wsjtx_matched": tb3["matched"], "M2_ows_only_FP_upper_bound": tb3["n"] - tb3["matched"],
        "M2_by_snr_band_n_matched": band,
        "M3_third_pass_ms_median_p90_max_PC": [q(ms, .5), q(ms, .9), ms[-1] if ms else None],
        "M3_cycle_wall_ms_mean_normal_deep_PC": [round(statistics.mean(cyc_n)), round(statistics.mean(cyc_d))] if cyc_n and cyc_d else None,
        "M4_outcomes_all_cycles": dict(oc_all),
        "M4_started": started, "M4_abandon_share_over_started": round((oc_all["abandoned"] + oc_all["failed"]) / started, 4) if started else None,
        "citation_guard": "NET_3 only with this corpus (Y-40, PC, production 13 s budget, abandoned cycles excluded pairwise) and its CI; never add to or difference from SUB-FEAS +8.89 / +11.73 pp; PC timings are the PC's, not sol's or the station's",
    }
    d = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-18-third-pass-y40")
    os.makedirs(d, exist_ok=True)
    json.dump(rep, open(os.path.join(d, "report.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    {"prep": prep, "run": run_all, "compare": compare}[sys.argv[1]]()
