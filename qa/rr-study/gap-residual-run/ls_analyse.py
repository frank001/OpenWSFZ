#!/usr/bin/env python3
"""LATE-SUB analysis (spec 5c33391f + Amendment 1 e2f7c5b2). usage: ls_analyse.py off|on
NET (combined one-to-one nearest-first matching with the arm rows, minus the baseline's), dU' (U' instrument, classes frozen from the Original arm), H-SHARE, verdict rows, decomposition,
TRAIN mechanism check, timing. Cycles 1-400 TRAIN (descriptive), 401-1200 TEST (the verdict; OFF decides). Counts and rates only; text is read in memory.
Bars (COH-GATE-G, re-used with the Captain's 'agreed', relayed by the Architect 2026-10-29): BAR_G 0.5 pp, U_bar_G 0.021 (tested_absent only), h 0.5. Bootstrap by cycle, B = 2000, seed 20261030."""
from __future__ import annotations

import collections
import importlib.util
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gap-relocate-run"))
import gr_common as C       # noqa: E402
import gg_lib as L          # noqa: E402

cfg = sys.argv[1]
S = "D:/Projects/claude/_qa-scratch/late-sub"
R4 = "D:/Projects/claude/_qa-scratch/coh-gate-r-f4"
CF = "D:/Projects/claude/OpenWSFZ/worktrees/qa/qa/rr-study/coh-fallback"
DLL = S + "/bin/libft8.dll"
WAV_ROOT = "D:/Projects/claude/OpenWSFZ/artefacts"
RUN = "20260925_2010"
CLASSES = "D:/Projects/claude/_qa-scratch/coh-gate-g/u/uprime_orig_classes.json"
BAR_G, U_BAR_G, H = 0.5, 0.021, 0.5
B, SEED = 2000, 20261030
N_TRAIN = 400
assert (BAR_G, U_BAR_G, H, B, SEED) == (0.5, 0.021, 0.5, 2000, 20261030)
VARIANTS = {"C": ["C"], "C+L1": ["C", "L1"], "L": ["C", "L1", "L2"]}
KIND = {"C": 5, "L1": 6, "L2": 7}


def main():
    sel = json.load(open(R4 + "/selection1200.json"))["runs"][RUN]["FULL"]
    stamps = [e if isinstance(e, str) else e[0] for e in sel]
    assert len(stamps) == 1200
    import csv
    cyc = {r["stamp"]: r for r in csv.DictReader(open(f"{S}/ls/{cfg}/ls_cycle.tsv", encoding="utf-8"), delimiter="	")}
    stamps = stamps[:len(cyc)]                       # a full run holds all 1,200; a pilot file holds fewer (smoke test only: the TEST block is then skipped)
    assert list(cyc) == stamps, "ls_cycle.tsv is not the selection's cycles in order"
    ref = C.load_ref(set(stamps))
    refc = np.array([float(len(ref.get(s, []))) for s in stamps])
    w = np.array([1.0 if ref.get(s) else 0.0 for s in stamps])
    nc = collections.defaultdict(list)
    for r in C.load_tsv(f"{S}/scratch/{cfg}/nc_dump.tsv"):
        if len(r) >= 11:
            nc[r[0]].append((int(r[1]), int(r[2]), int(r[3]), float(r[4]), int(r[5]), int(r[9]), r[10]))
    arm_rows = collections.defaultdict(lambda: collections.defaultdict(list))        # stamp -> arm -> [(freq, dt, snr, text)]
    for line in open(f"{S}/ls/{cfg}/ls_rows.tsv", encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        arm_rows[p[0]][p[1]].append((int(p[2]), float(p[3]), int(p[4]), p[5]))
    spec = importlib.util.spec_from_file_location("cf_uprime_mod", CF + "/cf_uprime.py")
    U = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(U)
    F, _ = U.load_instrument()
    enc = F.encoder(DLL)
    frozen = json.load(open(CLASSES))
    c_off = float(frozen["start_minus_dt_median_s"])
    testable = set(frozen["testable_classes"])
    pcms = {}

    def pcm_of(st):
        if st not in pcms:
            pcms[st] = F.wavio.load_cycle_pcm(os.path.join(WAV_ROOT, f"{RUN}_endurance_run-gathered", "owsfz", "wav", st + ".wav"))
        return pcms[st]
    cache = {}

    def status(stamp, text, freq, dt):
        key = (stamp, text, freq, dt)
        if key in cache:
            return cache[key]
        tones = enc(text)
        if any(x.startswith("<") for x in text.split()) or tones is None:
            r = "hashed_or_unencodable"
        elif F.shape_class(text) not in testable:
            r = "untestable_class"
        else:
            sh, outs = F.locate_and_score({}, pcm_of(stamp), freq, dt + c_off, F.DT_HALF_WINDOW_S, [tones[i] for i in F.SYNC_IDX], [tones])
            r = "tested_present" if outs[0] >= U.T_FROZEN else "tested_absent"
        cache[key] = r
        return r

    n = len(stamps)
    cols = {v: {k: np.zeros(n) for k in ("net", "ta", "hu", "pres", "unt", "out", "conf", "hashed")} for v in VARIANTS}
    sub = {a: np.zeros(n) for a in KIND}                       # rows published per arm batch
    newly = {v: collections.defaultdict(set) for v in VARIANTS}  # stamp -> REF idx newly matched (mechanism check)
    for ci, s in enumerate(stamps):
        base = [(x[0], x[2], x[6]) for x in nc.get(s, [])]
        uw0, _ = L.match(ref.get(s, []), base)
        for a in KIND:
            sub[a][ci] = len(arm_rows[s][a])
        for v, arms in VARIANTS.items():
            extra = []
            for a in arms:
                extra += [(KIND[a], f, t) for f, dt, snr, t in arm_rows[s][a]]
            uw, uo = L.match(ref.get(s, []), base + extra)
            cols[v]["net"][ci] = len(uw) - len(uw0)
            newly[v][s] = set(uw) - set(uw0)
            k0 = 0
            for a in arms:
                for f, dt, snr, t in arm_rows[s][a]:
                    idx = len(base) + k0
                    k0 += 1
                    cols[v]["out"][ci] += 1
                    if "<" in t:
                        cols[v]["hashed"][ci] += 1
                    if idx in uo:
                        cols[v]["conf"][ci] += 1
                    else:
                        sx = status(s, t, f, dt)
                        cols[v][{"tested_absent": "ta", "hashed_or_unencodable": "hu", "tested_present": "pres", "untestable_class": "unt"}[sx]][ci] += 1
    out = {"config": cfg, "cycles": n, "arm_rows_published": {a: int(sub[a].sum()) for a in KIND},
           "level_counts": dict(collections.Counter(r["level"] for r in cyc.values())),
           "l_outcomes": dict(collections.Counter(r["l_outcome"] for r in cyc.values())),
           "fit_list": {"entries": int(sum(int(r["fit_n"]) for r in cyc.values())), "refused_by_IsReencodable_or_Encode": int(sum(int(r["fit_refused"]) for r in cyc.values()))}}
    rng = np.random.default_rng(SEED)

    def block(lo, hi, name):
        m = hi - lo
        idx = rng.integers(lo, hi, size=(B, m))
        den = refc[idx].sum(axis=1)
        wc = w[idx].sum(axis=1)
        pc = lambda a: [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]
        res = {}
        net_by = {}
        for v in VARIANTS:
            c = cols[v]
            net = 100.0 * c["net"][idx].sum(axis=1) / den
            net_by[v] = net
            ta = c["ta"][idx].sum(axis=1) / wc
            outs = c["out"][lo:hi].sum()
            res[v] = {"NET_pp": 100.0 * c["net"][lo:hi].sum() / refc[lo:hi].sum(), "NET_CI": pc(net),
                      "dU_ta": c["ta"][lo:hi].sum() / w[lo:hi].sum(), "dU_ta_CI": pc(ta),
                      "dU_hu": c["hu"][lo:hi].sum() / w[lo:hi].sum(), "dU_present": c["pres"][lo:hi].sum() / w[lo:hi].sum(),
                      "dU_untestable_class": c["unt"][lo:hi].sum() / w[lo:hi].sum(),
                      "added_outputs": int(outs), "added_corroborated": int(c["conf"][lo:hi].sum()),
                      "hashed_share_of_added": float(c["hashed"][lo:hi].sum() / outs) if outs else None}
        res["decomposition"] = {
            "NET_L_minus_NET_C_pp": res["L"]["NET_pp"] - res["C"]["NET_pp"], "NET_L_minus_NET_C_CI": pc(net_by["L"] - net_by["C"]),
            "NET_L1_pp": res["C+L1"]["NET_pp"] - res["C"]["NET_pp"], "NET_L1_CI": pc(net_by["C+L1"] - net_by["C"]),
            "NET_L2_pp": res["L"]["NET_pp"] - res["C+L1"]["NET_pp"], "NET_L2_CI": pc(net_by["L"] - net_by["C+L1"]),
            "rows_published": {a: int(sub[a][lo:hi].sum()) for a in KIND}}
        for v, tag in (("C", "C"), ("L", "L")):
            r = res[v]
            go = r["NET_CI"][0] >= BAR_G
            ok = r["dU_ta_CI"][1] <= U_BAR_G and (r["hashed_share_of_added"] or 0.0) <= H
            res[v]["verdict"] = (f"{tag}-GO" if go and ok else f"{tag}-COST" if go else f"{tag}-STOP" if r["NET_CI"][1] < BAR_G else f"{tag}-OPEN")
        res["n_ref"] = float(refc[lo:hi].sum())
        return res
    if n > N_TRAIN:
        out["TEST_401_1200"] = block(N_TRAIN, n, "TEST")
    out["TRAIN_1_400"] = block(0, min(n, N_TRAIN), "TRAIN")

    # ── TRAIN mechanism check (descriptive): NR-TAX CU-d / CU-u NR rows and GAP-RESIDUAL's never-offered rows, outcome-matched by each arm ──
    mech = {}
    try:
        tags = [json.loads(l) for l in open("D:/Projects/claude/_qa-scratch/gap-residual/nrtax_row_tags.jsonl", encoding="utf-8")]
        cls = {(r["stamp"], r["idx"]): r["cls"] for r in (json.loads(l) for l in open("D:/Projects/claude/_qa-scratch/gap-residual/class_rows.jsonl", encoding="utf-8"))}
        pop = json.load(open(C.S + "\\population.json", encoding="utf-8"))
        prow = {(r["stamp"], r["idx"]): r for r in pop["rows"]}
        train = set(stamps[:N_TRAIN])
        sets = {"NR_CU-d": [(t["stamp"], t["idx"]) for t in tags if t["pop"] == "NR" and t["cat"] == "CU-d" and t["stamp"] in train],
                "NR_CU-u": [(t["stamp"], t["idx"]) for t in tags if t["pop"] == "NR" and t["cat"] == "CU-u" and t["stamp"] in train]}
        nev = []
        for (s, i), c in cls.items():
            if c not in ("RC", "RG", "RW"):
                continue
            r = prow[(s, i)]
            pl = [tuple(map(float, l.split("\t"))) for l in open(f"D:/Projects/claude/_qa-scratch/gap-residual/cap/off/plan/{s}.tsv", encoding="utf-8")]
            if not any(abs(f - r["freq"]) <= 2.0 and abs(d - (r["dt"] + 0.7)) <= 0.12 for f, d in pl):
                nev.append((s, i))
        sets["never_offered_RC_RG_RW"] = nev
        for name, keys in sets.items():
            mech[name] = {"rows": len(keys), **{v: sum(1 for (s, i) in keys if i in newly[v][s]) for v in VARIANTS}}
    except FileNotFoundError as e:
        mech["unavailable"] = str(e)
    out["TRAIN_mechanism_check"] = mech

    # ── timing (descriptive; the PC) ──
    log = open(f"{S}/raw/{cfg}/log.log", encoding="utf-8", errors="replace").read()
    fb = [(int(a), int(b_)) for a, b_ in re.findall(r"fbStartMs=(-?\d+), fbWallMs=(-?\d+)", log)]
    res_ms = [int(x) for x in re.findall(r"Sub-feas residual pass: residualDecodes=\d+ elapsedMs=(\d+)", log)]
    thr_ms = [int(x) for x in re.findall(r"Third pass: newDecodes=\d+ elapsedMs=(\d+) outcome=ran", log)]
    q = lambda v: {"median": float(np.median(v)), "p90": float(np.percentile(v, 90)), "max": float(np.max(v)), "n": len(v)} if len(v) else None
    ms_c = np.array([float(r["ms_C"]) for r in cyc.values() if r["level"] != "O"])
    ms_l = np.array([float(r["ms_Lround"]) + float(r["ms_L2"]) for r in cyc.values() if r["level"] != "O"])
    out["timing_ms"] = {"T1_arm_C_fallback_run": q(ms_c), "T1_arm_L_round_subtract_decode_plus_fallback": q(ms_l),
                        "T1_L_split": {"subtract_and_decode": q(np.array([float(r["ms_Lround"]) for r in cyc.values() if r["level"] != "O"])),
                                       "fallback_on_R4": q(np.array([float(r["ms_L2"]) for r in cyc.values() if r["level"] != "O"]))},
                        "T3_product_residual_pass": q(res_ms), "T3_product_third_pass_ran": q(thr_ms)}
    if len(fb) == n:
        end = np.array([a + b_ for a, b_ in fb], dtype=float)
        out["timing_ms"]["T2_end_of_work_vs_13s"] = {"product_fallback_end": q(end), "with_arm_C": q(end + ms_c[:n] if len(ms_c) == n else end),
                                                    "with_arm_L": q(end + ms_c[:n] + ms_l[:n] if len(ms_c) == n else end), "budget_ms": 13000}
    json.dump(out, open(f"{S}/result_{cfg}.json", "w"), indent=1, default=float)
    print(json.dumps({k: out[k] for k in out if k not in ("TRAIN_1_400",)}, indent=1, default=float))


if __name__ == "__main__":
    main()
