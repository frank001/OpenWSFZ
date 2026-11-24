#!/usr/bin/env python3
"""XC-TEMPLATE scorer (spec 2e133bc0 + A1 section 10).  Inputs: the frozen row lists (_qa-scratch\\xc-prior\\xc_rowlist.json), N24's matched file, WSJT-X's ALL.TXT, the TA-RES capture of arm B
(_qa-scratch\\ta-res\\cap_run\\cap: buffers O/R2/R3 and capture_index.tsv, level = column 10).  QA tooling; not PC-exclusive (8 workers for minutes).
    python xt_score.py prep    P rows (matched exact repeats), the null pool, K, FA*, buffer files; the pilot draw (seed 20261113)                              -> frozen\\xt_tasks.json (no text)
    python xt_score.py pilot   30 E1 + 30 P + 1,000 null tests, scored                                                                                          -> pilot.json
    python xt_score.py null    every acceptance null test (pilot tests excluded): T_E, its bootstrap interval, the split-half check                              -> nulls.json, frozen\\te.json
    python xt_score.py own     REFUSES without frozen\\te.json: E1 (residual primary, O descriptive) and P (O for V-POS, residual descriptive), acceptance rows only  -> own.json
HK-037: text is read in this process for tones, hashed flags and shape classes only; every file written holds stamp:index keys and numbers."""
from __future__ import annotations

import collections
import csv
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "..", "xc-prior"), os.path.join(HERE, "..", "ta-check"), os.path.join(HERE, "..", "rr-study", "n2-coherent-llr-extractor")):
    sys.path.insert(0, p)
import xt_lib as L          # noqa: E402
import xc_lib as XL         # noqa: E402
import xc_count as XC       # noqa: E402
import xc_rowlist as XR     # noqa: E402
import tc_groups as G       # noqa: E402
import tc_lib as TCL        # noqa: E402

OUT = "D:/Projects/claude/_qa-scratch/xc-template"
CAP = "D:/Projects/claude/_qa-scratch/ta-res/cap_run/cap"
ROWLIST = "D:/Projects/claude/_qa-scratch/xc-prior/xc_rowlist.json"
CALIB_S = 0.48                    # TA-CHECK's frozen start-minus-dt (asserted against tc_calib.json)
N_PILOT_E1, N_PILOT_P, N_PILOT_NULL = 30, 30, 1000
_W = {}


# ------------------------------------------------------------------------------------------------ workers
def _init():
    import coherent_extract as CE
    _W["CE"] = CE
    _W["buf"] = {}
    U = G.U
    F, _ = U.load_instrument()
    _W["F"] = F


def _load(path):
    b = _W["buf"]
    if path not in b:
        if len(b) > 4:
            b.clear()
        b[path] = np.fromfile(path, dtype=np.float32)
    return b[path]


def work(task):
    """task: dict(path, f, dt, tones, own=(f, dt) or None, tone_baseline=bool) -> dict(S, arg_f, arg_dt, truth, base)."""
    CE, F = _W["CE"], _W["F"]
    pcm = _load(task["path"])
    S, arg = L.search(CE, pcm, task["f"], task["dt"], task["tones"], CALIB_S)
    out = {"S": S, "af": arg[0], "adt": arg[1]}
    if task.get("own"):
        out["truth"] = bool(L.truth_ok(arg, task["own"][0], task["own"][1]))
        sync = [task["tones"][k] for k in F.SYNC_IDX]
        _, sh = F.locate_and_score({}, pcm, task["own"][0], task["own"][1] + CALIB_S, F.DT_HALF_WINDOW_S, sync, [task["tones"]])
        out["base"] = float(sh[0])
    return out


def run_tasks(tasks, workers=8):
    with mp.Pool(workers, initializer=_init) as pool:
        return list(pool.imap(work, tasks, chunksize=32))


# ------------------------------------------------------------------------------------------------ prep
def level_of():
    lv = {}
    for l in open(CAP + "/capture_index.tsv", encoding="utf-8"):
        p = l.rstrip("\n").split("\t")
        if len(p) >= 11:
            lv[p[0]] = p[9]
    return lv


def prep():
    assert abs(float(json.load(open(G.OUT + "/frozen/tc_calib.json"))["start_minus_dt_median_s"]) - CALIB_S) < 1e-9
    stamps = [l.strip()[:-4] for l in open(XC.LIST) if l.strip()]
    ref = G.load_ref_night(set(stamps))
    F, _ = G.U.load_instrument()
    enc = F.encoder(G.DLL)
    mb = {}
    for r in csv.reader(open(XC.N24)):
        if r and r[0] != "stamp":
            mb[r[0]] = {int(a.split(":")[0]): int(a.split(":")[1]) for a in r[1].split(";") if a}
    lv = level_of()
    assert all(lv.get(s) in ("R3", "R2") for s in stamps), "a cycle has no residual level"
    resid = {s: f"{CAP}/buffers/{s}_{lv[s]}.f32" for s in stamps}
    orig = {s: f"{CAP}/buffers/{s}_O.f32" for s in stamps}
    assert all(os.path.isfile(resid[s]) and os.path.isfile(orig[s]) for s in stamps)
    mcyc, mb_idx = [], []
    for s in stamps:
        rows = ref.get(s, [])
        ks = sorted(mb.get(s, {}))
        mcyc.append([(rows[j][3], rows[j][2], mb[s][j]) for j in ks])
        mb_idx.append(ks)
    # K: the median over cycles of the distinct matched texts in the 3 preceding same-parity cycles
    txt = [set(t for t, _, _ in mcyc[i]) for i in range(len(stamps))]
    Ks = [len(txt[i - 2] | txt[i - 4] | txt[i - 6]) for i in range(6, len(stamps))]
    K = float(np.median(Ks))
    fa = L.fa_star(K)
    tones_cache = {}

    def tones_of(text):
        if text not in tones_cache:
            t = enc(text)
            tones_cache[text] = None if t is None else [int(x) for x in t]
        return tones_cache[text]

    # E1 rows (frozen list) and P rows (matched exact repeats, same code, with their prior)
    e1_list = json.load(open(ROWLIST))["E1"]
    assert len(e1_list) == L.N_E1_FULL
    E1, P, skipped = [], [], collections.Counter()
    sidx = {s: i for i, s in enumerate(stamps)}
    for r in e1_list:
        s, j = r["stamp"], r["idx"]
        snr, dt, f, text = ref[s][j]
        ps, pj = r["prior_stamp"], r["prior_idx"]
        pf, pdt = ref[ps][pj][2], ref[ps][pj][1]
        tn = tones_of(text)
        rows = [(x[0], x[1], x[2]) for x in ref[s]]
        E1.append({"stamp": s, "idx": j, "snr": snr, "hashed": "<" in text, "tones": tn, "own": [f, dt], "centre": [pf, pdt], "prior_stamp": ps, "prior_idx": pj, "prior_batch": r["prior_batch"], "lag_s": r["lag_s"],
                   "kind": F.shape_class(text), "buried": bool(TCL.is_buried(j, rows)), "unencodable": tn is None})
    for i, s in enumerate(stamps):
        for j, b in sorted(mb.get(s, {}).items()):
            snr, dt, f, text = ref[s][j]
            hit = XL.prior_hit((text, f), i, XL.SAME_LAGS, mcyc)
            if hit[0] != "E1":
                continue
            lag = hit[1]
            found = XR.find_prior(text, f, i, XL.SAME_LAGS, mcyc, stamps, mb_idx)
            _, ps, pj, pb = found
            if "<" in text:
                skipped["P_hashed_excluded"] += 1
                continue
            tn = tones_of(text)
            if tn is None:
                skipped["P_unencodable"] += 1
                continue
            P.append({"stamp": s, "idx": j, "snr": snr, "batch": b, "tones": tn, "own": [f, dt], "centre": [ref[ps][pj][2], ref[ps][pj][1]], "prior_stamp": ps, "prior_idx": pj, "lag_s": lag * XL.CYCLE_S})
    # the null pool: every matched message at the opposite-parity cycles s - 15 s and s + 15 s, dropping tests whose text is present in that cycle's ALL.TXT
    NL, drops = [], 0
    for i, s in enumerate(stamps):
        for j, b in sorted(mb.get(s, {}).items()):
            snr, dt, f, text = ref[s][j]
            tn = tones_of(text)
            if tn is None:
                skipped["null_unencodable"] += 1
                continue
            for d in (-1, 1):
                k = i + d
                if not 0 <= k < len(stamps):
                    continue
                if any(r[3] == text for r in ref[stamps[k]]):
                    drops += 1
                    continue
                NL.append({"cyc": k, "stamp": stamps[k], "src": [s, j], "tones": tn, "centre": [f, dt]})
    rng = np.random.default_rng(L.SEED)
    pil_e1 = sorted(int(x) for x in rng.permutation(len(E1))[:N_PILOT_E1])
    pil_p = sorted(int(x) for x in rng.permutation(len(P))[:N_PILOT_P])
    pil_n = sorted(int(x) for x in rng.permutation(len(NL))[:N_PILOT_NULL])
    summ = {"K_median": K, "K_mean": float(np.mean(Ks)), "FA_star": fa, "V_NULL_N_floor": L.n_null_min(fa), "null_pool": len(NL), "null_drops_text_present": drops, "skipped": dict(skipped),
            "E1_rows": len(E1), "E1_hashed": sum(1 for r in E1 if r["hashed"]), "E1_unencodable": sum(1 for r in E1 if r["unencodable"]), "P_rows": len(P), "buffer_levels": dict(collections.Counter(lv[s] for s in stamps)),
            "pilot": {"E1": N_PILOT_E1, "P": N_PILOT_P, "null": N_PILOT_NULL, "seed": L.SEED}}
    json.dump({"E1": E1, "P": P, "NL": NL, "pilot": {"E1": pil_e1, "P": pil_p, "NL": pil_n}, "stamps": stamps, "resid": resid, "orig": orig, "summary": summ}, open(OUT + "/frozen/xt_tasks.json", "w"))
    print(json.dumps(summ, indent=1))


def mk(row, path, own=True):
    return {"path": path, "f": row["centre"][0], "dt": row["centre"][1], "tones": row["tones"], "own": row["own"] if own else None}


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    if stage not in ("prep", "pilot", "null", "own"):
        sys.exit(__doc__)
    os.makedirs(OUT + "/frozen", exist_ok=True)
    if stage == "prep":
        prep()
        return
    T = json.load(open(OUT + "/frozen/xt_tasks.json"))
    E1, P, NL, pil, resid, orig = T["E1"], T["P"], T["NL"], T["pilot"], T["resid"], T["orig"]
    fa = T["summary"]["FA_star"]
    if stage == "pilot":
        t0 = time.time()
        e1 = [E1[i] for i in pil["E1"] if E1[i]["tones"] is not None and not E1[i]["hashed"]]
        pp = [P[i] for i in pil["P"]]
        nl = [NL[i] for i in pil["NL"]]
        tasks = [mk(r, resid[r["stamp"]]) for r in e1] + [mk(r, orig[r["stamp"]]) for r in e1] + [mk(r, orig[r["stamp"]]) for r in pp] + [mk(r, resid[r["stamp"]]) for r in pp] \
            + [mk(r, resid[r["stamp"]], own=False) for r in nl]
        res = run_tests(tasks)
        n1, n2 = len(e1), len(pp)
        out = {"E1_resid": res[:n1], "E1_O": res[n1:2 * n1], "P_O": res[2 * n1:2 * n1 + n2], "P_resid": res[2 * n1 + n2:2 * n1 + 2 * n2], "null": res[2 * n1 + 2 * n2:], "seconds": time.time() - t0, "tests": len(tasks),
               "E1_pilot_rows_scored": n1, "E1_pilot_hashed_skipped": sum(1 for i in pil["E1"] if E1[i]["hashed"])}
        json.dump(out, open(OUT + "/pilot.json", "w"))
        print("pilot tests", len(tasks), "in", round(out["seconds"], 1), "s")
        return
    pilnl = set(pil["NL"])
    if stage == "null":
        idxs = [i for i in range(len(NL)) if i not in pilnl]
        res = run_tests([mk(NL[i], resid[NL[i]["stamp"]], own=False) for i in idxs])
        sc = np.array([r["S"] for r in res])
        cyc = np.array([NL[i]["cyc"] for i in idxs])
        te = L.threshold_te(sc, fa)
        idx = L.boot_idx(len(T["stamps"]))
        bt = L.boot_te(sc, cyc, len(T["stamps"]), fa, idx)
        sh = L.split_half(sc, cyc, fa)
        out = {"T_E": te, "FA_star": fa, "n_null": int(sc.size), "V_NULL_N": {"floor": L.n_null_min(fa), "PASS": bool(sc.size >= L.n_null_min(fa))}, "V_FA_exceedance_at_T_E": L.exceed(sc, te),
               "T_E_bootstrap_CI": L.ci(bt), "split_half": sh, "null_S_quantiles_50_90_99_99.9_max": [float(x) for x in np.percentile(sc, [50, 90, 99, 99.9, 100])]}
        json.dump({"S": sc.tolist(), "cyc": cyc.tolist(), "idx": idxs}, open(OUT + "/nulls.json", "w"))
        json.dump(out, open(OUT + "/frozen/te.json", "w"), indent=1)
        print(json.dumps(out, indent=1))
        return
    if not os.path.isfile(OUT + "/frozen/te.json"):
        sys.exit("REFUSED: frozen/te.json (T_E) does not exist: the null stage must run and be committed first")
    pe1, pp_ = set(pil["E1"]), set(pil["P"])
    e1i = [i for i in range(len(E1)) if i not in pe1]
    pi = [i for i in range(len(P)) if i not in pp_]
    tasks = [mk(E1[i], resid[E1[i]["stamp"]]) for i in e1i if E1[i]["tones"] is not None and not E1[i]["hashed"]]
    e1_scored = [i for i in e1i if E1[i]["tones"] is not None and not E1[i]["hashed"]]
    tasks += [mk(E1[i], orig[E1[i]["stamp"]]) for i in e1_scored]
    tasks += [mk(P[i], orig[P[i]["stamp"]]) for i in pi] + [mk(P[i], resid[P[i]["stamp"]]) for i in pi]
    res = run_tests(tasks)
    a = len(e1_scored)
    out = {"E1_idx": e1_scored, "E1_resid": res[:a], "E1_O": res[a:2 * a], "P_idx": pi, "P_O": res[2 * a:2 * a + len(pi)], "P_resid": res[2 * a + len(pi):]}
    json.dump(out, open(OUT + "/own.json", "w"))
    print("acceptance tests scored:", len(tasks))


def run_tests(tasks):
    return run_tasks(tasks)


if __name__ == "__main__":
    mp.freeze_support()
    main()
