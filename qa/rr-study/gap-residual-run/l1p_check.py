#!/usr/bin/env python3
"""LATE-SUB L1' validity rows (spec 8152d4ce + Amendment 1 e3fd391e): V0, V2, V3, V5, V6, V7, V8; V1 descriptive. Counts and flags only.
usage:
  l1p_check.py arm <name> <night> [--freeze <freeze record .md>]   rows for one arm's output (ls/l1p_<name>, raw/l1p_<name>)
  l1p_check.py v7                                                   V7: the l1p mode on refset cycles 1-40 against the old LATE-SUB pilot (arm name l1p_reg40 must exist)
  l1p_check.py v8                                                   V8: n_ref of the verdict selection == 20,753 (ALL.TXT of the night; no decode needed)"""
import collections
import csv
import hashlib
import json
import os
import re
import subprocess
import sys

S = "D:/Projects/claude/_qa-scratch/late-sub"
R4 = "D:/Projects/claude/_qa-scratch/coh-gate-r-f4"
ART = "D:/Projects/claude/OpenWSFZ/artefacts"
PIN = "1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914"
SEL_2N, SEL_2N_SHA = R4 + "/selection_2n.json", "cf9908a5dcc66ef8966693b2d29ae5bd04fc357d3e1af5058b0e35d7eea6726e"
CLS_2N, CLS_2N_SHA = R4 + "/u2/orig_classes.json", "0d83d685db2aee961211b022d5b563c0b5b24a83e51f16c126d0f6cff870ab25"
N_REF_2N, CYC_WSJTX_2N = 20753, 799
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
tsv = lambda p: list(csv.DictReader(open(p, encoding="utf-8"), delimiter="\t"))


def v8():
    sys.path.insert(0, os.path.join(HERE, "..", "gap-relocate-run"))
    import gr_common as C
    C.ALLTXT = f"{ART}/20261022_1949_endurance_run-gathered/wsjt-x/ALL.TXT"
    sel = json.load(open(SEL_2N))["runs"]["20261022_1949"]["FULL"]
    st = [e if isinstance(e, str) else e[0] for e in sel]
    ref = C.load_ref(set(st))
    n = sum(len(v) for v in ref.values())
    r = {"selection_sha_matches_freeze": sha(SEL_2N) == SEL_2N_SHA, "cycles": len(st), "n_ref": n, "cycles_with_wsjtx": len(ref), "expected_n_ref": N_REF_2N, "expected_cycles_with_wsjtx": CYC_WSJTX_2N}
    r["PASS"] = r["selection_sha_matches_freeze"] and len(st) == 800 and n == N_REF_2N and len(ref) == CYC_WSJTX_2N
    return r


def v7():
    new, old = tsv(f"{S}/ls/l1p_reg40/ls_cycle.tsv"), tsv(f"{S}/ls/pilot-off/ls_cycle.tsv")
    assert len(new) == len(old) == 40
    same_cols = ["stamp", "level", "calls", "v2_b1", "v2_b2", "v2_b3", "v2_r3_bytes", "v3_b4", "snapB"]
    diff_cols = [i for i, (a, b) in enumerate(zip(new, old)) if [a[c] for c in same_cols] != [b[c] for c in same_cols]]
    # fit list: the old fit = batch 3 + batch 4 + C rows, so fit_new == fit_old - pubC_old (same cycle)
    diff_fit = [i for i, (a, b) in enumerate(zip(new, old)) if int(a["fit_n"]) != int(b["fit_n"]) - int(b["pubC"])]
    cols = ["decodes", "b1_n", "b2_n", "b3_n", "b4_n"]
    ra = {r["stamp"]: r for r in csv.DictReader(open(f"{S}/raw/l1p_reg40/run.csv"))}
    rb = {r["stamp"]: r for r in csv.DictReader(open(f"{S}/raw/pilot-off/run.csv"))}
    diff_run = [s for s in rb if [ra[s][c] for c in cols] != [rb[s][c] for c in cols]]
    la = {}
    for l in open(f"{S}/scratch/l1p_reg40/nc_dump.tsv", encoding="utf-8", errors="replace"):
        la.setdefault(l.split("\t", 1)[0], []).append(l)
    lb = {}
    for l in open(f"{S}/scratch/pilot-off/nc_dump.tsv", encoding="utf-8", errors="replace"):
        lb.setdefault(l.split("\t", 1)[0], []).append(l)
    diff_nc = [s for s in lb if la.get(s) != lb.get(s)]
    no_c = all(int(r["pubC"]) == 0 and int(r["pubL2"]) == 0 for r in new)
    r = {"cycles": 40, "v2_v3_level_calls_snapB_differing_cycles": len(diff_cols), "fit_n_not_old_minus_pubC": len(diff_fit), "run_csv_batch_counts_differing": len(diff_run),
         "nc_dump_cycles_differing": len(diff_nc), "no_C_or_L2_rows_in_new_mode": no_c}
    r["PASS"] = not diff_cols and not diff_fit and not diff_run and not diff_nc and no_c
    return r


def arm(name, night, freeze):
    ls, raw, scr = f"{S}/ls/l1p_{name}", f"{S}/raw/l1p_{name}", f"{S}/scratch/l1p_{name}"
    cyc = tsv(f"{ls}/ls_cycle.tsv")
    out = {"arm": name, "night": night, "cycles": len(cyc)}
    out["V0"] = {"dll_sha_matches_pin": sha(f"{S}/bin_l1p/libft8.dll") == PIN}
    out["V0"]["PASS"] = out["V0"]["dll_sha_matches_pin"]
    f = lambda k: sum(1 for r in cyc if r[k] == "0")
    out["V2"] = {"b1_not_reproduced": f("v2_b1"), "b2_not_reproduced": f("v2_b2"), "b3_not_reproduced": f("v2_b3"), "B_bytes_not_equal": f("v2_r3_bytes")}
    out["V2"]["PASS"] = all(v == 0 for v in out["V2"].values())
    out["V3"] = {"b4_not_reproduced": f("v3_b4"), "PASS": f("v3_b4") == 0}
    ab = [r for r in csv.DictReader(open(f"{raw}/abandon.csv"), fieldnames=["stamp", "ran", "abandoned", "contained"]) if r["stamp"][:1].isdigit()]
    th = collections.Counter(r["outcome"] for r in csv.DictReader(open(f"{raw}/third.csv")))
    log = open(f"{raw}/log.log", encoding="utf-8", errors="replace").read()
    out["V5"] = {"residual_abandoned": sum(int(r["abandoned"]) for r in ab), "residual_contained": sum(int(r["contained"]) for r in ab),
                 "third_abandoned_or_failed": th.get("abandoned", 0) + th.get("failed", 0), "fallback_lines": len(re.findall("Coherent fallback:", log)),
                 "fallback_lines_abandoned_gt0": len(re.findall(r"abandoned=[1-9]", log))}
    out["V5"]["PASS"] = out["V5"]["residual_abandoned"] == 0 and out["V5"]["residual_contained"] == 0 and out["V5"]["third_abandoned_or_failed"] == 0 and out["V5"]["fallback_lines_abandoned_gt0"] == 0
    # V6: the freeze record is committed, its stated hashes equal the files', the scripts are unchanged since its code commit, and its commit time precedes the first output file.
    v6 = {"freeze_given": bool(freeze)}
    if freeze:
        txt = open(freeze, encoding="utf-8").read()
        g = lambda k: (re.search(k + r"=([0-9a-f]{40,64})", txt) or [None, ""])[1]
        v6["selection_sha_in_record"] = g("selection_sha256") == SEL_2N_SHA == sha(SEL_2N) if night == "20261022_1949" else None
        v6["classes_sha_in_record"] = g("classes_sha256") == CLS_2N_SHA == sha(CLS_2N)
        v6["dll_sha_in_record"] = g("dll_sha256") == PIN
        code = g("code_commit")
        rel = os.path.relpath(freeze, REPO).replace("\\", "/")
        ct = subprocess.run(["git", "-C", REPO, "log", "--diff-filter=A", "--format=%ct", "--", rel], capture_output=True, text=True).stdout.split()
        v6["record_commit_time"] = int(ct[-1]) if ct else None
        files = ["qa/rr-study/gap-residual-run/l1p_arm.sh", "qa/rr-study/gap-residual-run/l1p_check.py", "qa/rr-study/gap-residual-run/l1p_analyse.py",
                 "qa/rr-study/sub-feas/replay81/LateSub.cs", "qa/rr-study/sub-feas/replay81/Program.cs"]
        d = subprocess.run(["git", "-C", REPO, "diff", "--quiet", code, "--"] + files).returncode if code else 1
        v6["code_unchanged_since_code_commit"] = d == 0
        mt = [os.path.getmtime(os.path.join(dp, fn)) for base in (ls, raw, scr) for dp, _, fns in os.walk(base) for fn in fns]
        v6["first_output_mtime"] = int(min(mt)) if mt else None
        v6["record_commit_before_first_output"] = bool(v6["record_commit_time"] and mt and v6["record_commit_time"] < min(mt))
        ok = [v6["classes_sha_in_record"], v6["dll_sha_in_record"], v6["code_unchanged_since_code_commit"], v6["record_commit_before_first_output"]]
        if night == "20261022_1949":
            ok.append(v6["selection_sha_in_record"])
        v6["PASS"] = all(ok)
    else:
        v6["PASS"] = False
    out["V6"] = v6
    out["V4_info"] = {"level_counts": dict(collections.Counter(r["level"] for r in cyc)), "l_outcomes": dict(collections.Counter(r["l_outcome"] for r in cyc)),
                      "fit_entries": sum(int(r["fit_n"]) for r in cyc), "fit_refused": sum(int(r["fit_refused"]) for r in cyc),
                      "snapB_bad": sum(1 for r in cyc if r["level"] != "O" and r["snapB"] != "1")}
    # V1 is DESCRIPTIVE on the verdict night (the R-F4 2N arms ran on sol): the cycles where this PC's product batch counts differ from sol's OFF (or ON) arm.
    sol = {"off": f"{R4}/sol/raw/off/run.csv", "on": f"{R4}/sol/raw/on/run.csv"}
    key = "on" if name.startswith("on") else "off"
    if night == "20261022_1949" and os.path.exists(sol[key]):
        ra = {r["stamp"]: r for r in csv.DictReader(open(f"{raw}/run.csv"))}
        rb = {r["stamp"]: r for r in csv.DictReader(open(sol[key]))}
        cols = ["decodes", "b1_n", "b2_n", "b3_n", "b4_n"]
        common = [s for s in ra if s in rb]
        dif = [s for s in common if [ra[s][c] for c in cols] != [rb[s][c] for c in cols]]
        out["V1_descriptive_pointer_vs_sol"] = {"reference": f"sol {key}", "cycles_compared": len(common), "cycles_batch_counts_differ": len(dif), "share": len(dif) / max(1, len(common))}
    rows = ["V0", "V2", "V3", "V5", "V6"]
    out["ALL_PASS"] = all(out[k]["PASS"] for k in rows)
    json.dump(out, open(f"{S}/l1p_check_{name}.json", "w"), indent=1)
    return out


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "v7":
        r = v7(); json.dump(r, open(f"{S}/l1p_check_v7.json", "w"), indent=1)
    elif c == "v8":
        r = v8(); json.dump(r, open(f"{S}/l1p_check_v8.json", "w"), indent=1)
    else:
        fr = sys.argv[sys.argv.index("--freeze") + 1] if "--freeze" in sys.argv else None
        r = arm(sys.argv[2], sys.argv[3], fr)
    print(json.dumps(r, indent=1))
