#!/usr/bin/env python3
"""GAP-RESIDUAL main run (spec 74a38158 + Amendment 1 section 9 ea7496d1). The Captain's go after the pilot: "go" (2026-10-29).

  force   : freeze the REF-SNR tercile cut points from the N rows (BEFORE any forcing), then force (a) every class-N row and (b) every control row (K and, descriptively, all
            b23 / fb_res rows) on R2 and R3 with GAP-RELOCATE's own legs (gr_forced.force_cycle; only the PCM argument changes).
  analyse : classes RP-native / RP-search / RC / RG / RW / NR (+ NR?), D1-R .. D8, row 0d per stratum / band / tercile, routing rows. Counts, rates and CIs only.
Message text is read in memory (REF text for the codeword, native text for RP-native, station keys) and never persisted outside D:\\Projects\\claude\\_qa-scratch.
"""
from __future__ import annotations

import collections
import json
import math
import multiprocessing as mp
import os
import re
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "gap-relocate-run"))
import gr_common as C       # noqa: E402
import gr_forced as F       # noqa: E402
import gr_item2 as I2       # noqa: E402
import gres_pilot as P      # noqa: E402  (the patched loader and the job runner)

NEW = "D:/Projects/claude/_qa-scratch/gap-residual"
CAP = NEW + "/cap/off"
MAIN_TREE = NEW + "/main-tree"
PILOT_CYCLES = 40
SEED, B = 20261029, 2000
BAR_L_PP = 0.5
P_BAR, BAND_P, TERCILE_P, MIN_N = 0.90, 0.80, 0.80, 50
T1 = 17.552446
WIN_DF, WIN_DT_HALF, WIN_DF_S, WIN_DT_HALF_S = 2.0, 0.12, 2.5, 0.17            # A1.3: native window, and the sensitivity window
DELTA_C = 0.7
assert (SEED, B, BAR_L_PP, P_BAR, BAND_P, TERCILE_P, MIN_N) == (20261029, 2000, 0.5, 0.90, 0.80, 0.80, 50)


def check_native_window():
    """A1.3: assert the two constants against the native source (not prose)."""
    t = open(MAIN_TREE + "/native/ft8_lib_vendor/refine/coherent_fallback.c", encoding="utf-8").read()
    assert re.search(r"#define CF_DF_MAX_HZ\s+2\.0\b", t), "CF_DF_MAX_HZ is not 2.0"
    assert re.search(r"#define CF_DT_STEP_S\s+0\.005\b", t), "CF_DT_STEP_S is not 0.005"
    assert "the search window (+-0.12 s, +-2 Hz)" in t, "window comment changed"
    assert abs(24 * 0.005 - WIN_DT_HALF) < 1e-12                       # 49 dt windows = 24 steps either side of the lattice position


def load_old():
    pop = json.load(open(C.S + "\\population.json", encoding="utf-8"))
    recs = {}
    for fn in ("forced_pilot.jsonl", "forced_main.jsonl"):
        for line in open(C.S + "\\" + fn, encoding="utf-8"):
            r = json.loads(line)
            recs[(r["stamp"], r["idx"])] = r
    return pop, recs


def wilson(k, n, z=1.96):
    return P.wilson(k, n, z)


# ── force ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def cmd_force():
    pop, recs = load_old()
    rows = pop["rows"]
    M = [r for r in rows if not r["matched"]]
    cls = {(r["stamp"], r["idx"]): I2.classify(r, recs.get((r["stamp"], r["idx"]))) for r in M}
    cnt = collections.Counter(cls.values())
    print("GAP-RELOCATE classes on M:", dict(cnt))
    N = [r for r in M if cls[(r["stamp"], r["idx"])] == "N"]
    assert len(N) == 1860 and len(M) == 2193 and cnt["XU"] == 164, (len(N), len(M), cnt)
    snr = np.array([r["snr"] for r in N], dtype=float)
    cuts = [float(np.percentile(snr, 100.0 / 3)), float(np.percentile(snr, 200.0 / 3))]
    json.dump({"tercile_cuts_ref_snr_db": cuts, "n_N_rows": len(N), "frozen_before_forcing": True}, open(NEW + "/cuts.json", "w"), indent=1)
    print("frozen REF-SNR tercile cuts (from the N rows):", cuts)
    ctrl = [r for r in rows if r["tag"] in ("b23", "fb_res")]
    for fn in ("forced_N.jsonl", "forced_ctrl.jsonl"):
        if os.path.exists(f"{NEW}/{fn}"):
            os.remove(f"{NEW}/{fn}")
    n1, s1 = P.run_kind({"R2": N, "R3": N}, f"{NEW}/forced_N.jsonl")
    print(f"N rows: {n1} (row, buffer) records in {s1:.1f}s", flush=True)
    n2, s2 = P.run_kind({"R2": ctrl, "R3": ctrl}, f"{NEW}/forced_ctrl.jsonl")
    print(f"control rows: {n2} (row, buffer) records in {s2:.1f}s")


# ── analyse ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def load_forced(path):
    d = collections.defaultdict(dict)
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        d[(r["stamp"], r["idx"])][r["buf"]] = r
    return d


def leg_flags(bufs):
    """per-row legs over the buffers that exist: fp / v3 (any gate) / v3 gated=1 / walk / wrong counts."""
    f = {"fp": False, "v3": False, "v3_g1": False, "v3_g0": False, "walk": False, "unenc": False, "fp_cell": None}
    for b, r in bufs.items():
        if r.get("unencodable"):
            f["unenc"] = True
            continue
        if r["fp"]["found"]:
            f["fp"] = True
            if f["fp_cell"] != "centre":
                f["fp_cell"] = r["fp"]["cell"]
        if r["fc"]["v3_match"] and r["fc"]["gated"] is not None:
            f["v3"] = True
            if r["fc"]["gated"] == 1:
                f["v3_g1"] = True
            else:
                f["v3_g0"] = True
        if r["walk"]["match"]:
            f["walk"] = True
    return f


def main_analyse():
    check_native_window()
    pop, old = load_old()
    rows = pop["rows"]
    key = {(r["stamp"], r["idx"]): r for r in rows}
    stamps = pop["stamps"]
    pilot = set(stamps[:PILOT_CYCLES])
    cyc_idx = {s: i for i, s in enumerate(stamps)}
    ref = C.load_ref(set(stamps))
    n_ref = pop["n_ref"]
    cuts = json.load(open(NEW + "/cuts.json"))["tercile_cuts_ref_snr_db"]

    def terc(snr):
        return 1 if snr <= cuts[0] else (2 if snr <= cuts[1] else 3)
    M = [r for r in rows if not r["matched"]]
    cls_old = {(r["stamp"], r["idx"]): I2.classify(r, old.get((r["stamp"], r["idx"]))) for r in M}
    N = [r for r in M if cls_old[(r["stamp"], r["idx"])] == "N"]
    fN, fC = load_forced(NEW + "/forced_N.jsonl"), load_forced(NEW + "/forced_ctrl.jsonl")
    out = {"n_ref": n_ref, "N_rows": len(N), "tercile_cuts": cuts}

    # ── ROW 0d: per stratum, on the 360 non-pilot cycles (K rows), + pilot, + all rows (descriptive) ──
    def stratum(tag, legs, sel):
        ks = [r for r in rows if r["tag"] == tag and sel(r)]
        n = hit = 0
        for r in ks:
            f = leg_flags(fC.get((r["stamp"], r["idx"]), {}))
            if f["unenc"] or not fC.get((r["stamp"], r["idx"])):
                continue
            n += 1
            hit += any(f[l] for l in legs)
        lo, hi = wilson(hit, n)
        return {"n": n, "recovered": hit, "P": hit / n if n else None, "wilson95": [lo, hi]}
    nonpilot = lambda r: r["K"] and r["stamp"] not in pilot
    out["0d"] = {"i_b23_primary": stratum("b23", ("fp",), nonpilot), "ii_fb_res_coherent": stratum("fb_res", ("v3", "walk"), nonpilot),
                 "pilot_i": stratum("b23", ("fp",), lambda r: r["K"] and r["stamp"] in pilot),
                 "pilot_ii": stratum("fb_res", ("v3", "walk"), lambda r: r["K"] and r["stamp"] in pilot),
                 "descriptive_all_rows_i": stratum("b23", ("fp",), lambda r: r["stamp"] not in pilot),
                 "descriptive_all_rows_ii": stratum("fb_res", ("v3", "walk"), lambda r: r["stamp"] not in pilot)}
    fam_ok = {"primary": out["0d"]["i_b23_primary"]["P"] is not None and out["0d"]["i_b23_primary"]["P"] >= P_BAR,
              "coherent": out["0d"]["ii_fb_res_coherent"]["P"] is not None and out["0d"]["ii_fb_res_coherent"]["P"] >= P_BAR}
    out["0d"]["leg_family_established"] = fam_ok
    # per band / tercile: control rows (K, non-pilot, both strata), union of all legs
    ctrl_np = [r for r in rows if r["tag"] in ("b23", "fb_res") and nonpilot(r) and fC.get((r["stamp"], r["idx"]))]
    def pstat(sel):
        n = hit = 0
        for r in sel:
            f = leg_flags(fC[(r["stamp"], r["idx"])])
            if f["unenc"]:
                continue
            n += 1
            hit += (f["fp"] or f["v3"] or f["walk"])
        return {"n": n, "P": hit / n if n else None}
    by_band = {b: pstat([r for r in ctrl_np if r["band"] == b]) for b in "ABCD"}
    by_terc = {t: pstat([r for r in ctrl_np if terc(r["snr"]) == t]) for t in (1, 2, 3)}
    band_ne = [b for b, v in by_band.items() if v["n"] >= MIN_N and v["P"] < BAND_P]
    terc_ne = [t for t, v in by_terc.items() if v["n"] == 0 or (v["n"] >= MIN_N and v["P"] < TERCILE_P)]
    out["0d"].update({"by_band": by_band, "by_tercile": {str(k): v for k, v in by_terc.items()}, "bands_not_established": band_ne,
                      "terciles_not_established": [int(t) for t in terc_ne],
                      "control_snr_range": [min(r["snr"] for r in ctrl_np), max(r["snr"] for r in ctrl_np)],
                      "N_snr_range": [min(r["snr"] for r in N), max(r["snr"] for r in N)]})

    # ── native payload match for RP-native ──
    dec = F.load_dec()
    import comparator as CMP
    nat = collections.defaultdict(list)
    for stamp in {r["stamp"] for r in N}:
        for line in open(f"{CAP}/native/{stamp}.tsv", encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if len(p) >= 5 and p[0] in ("R2", "R3"):
                nat[stamp].append(p[4])
    cw_cache = {}
    def cw(text):
        if text not in cw_cache:
            x = dec.true_codeword(text)
            cw_cache[text] = None if x is None else x[:F.FT8_PAYLOAD_BITS]
        return cw_cache[text]
    def native_has(stamp, idx):
        snr, dt, freq, text = ref[stamp][idx]
        X = cw(text)
        if X is None:
            return False
        for nt in nat.get(stamp, []):
            Y = cw(nt)
            if Y is not None and CMP.payload_match(X, Y, text, F.V_STAR):
                return True
        return False

    # ── classes on the N rows ──
    cls = {}
    legs = {}
    for r in N:
        k = (r["stamp"], r["idx"])
        f = leg_flags(fN.get(k, {}))
        legs[k] = f
        if f["unenc"] or not fN.get(k):
            cls[k] = "X"
        elif native_has(*k):
            cls[k] = "RP-native"
        elif f["fp"]:
            cls[k] = "RP-search"
        elif f["v3_g1"]:
            cls[k] = "RC"
        elif f["v3_g0"]:
            cls[k] = "RG"
        elif f["walk"]:
            cls[k] = "RW"
        else:
            cls[k] = "NR"
    classes = ["RP-native", "RP-search", "RC", "RG", "RW", "NR"]
    cnt = collections.Counter(cls.values())
    out["D1_R"] = {c: cnt.get(c, 0) for c in classes}
    out["D1_R"]["X_unforced_or_unencodable"] = cnt.get("X", 0)
    out["D1_R"]["sum"] = sum(cnt.values())
    out["D1_R_pp_of_n_ref"] = {c: 100.0 * cnt.get(c, 0) / n_ref for c in classes}
    old_cnt = collections.Counter(cls_old.values())
    out["D1_R_whole_map"] = {"P": old_cnt["P"], "FP": old_cnt["FP"], "FC": old_cnt["FC"], "G": old_cnt["G"], "FCw": old_cnt["FCw"], "U": old_cnt["XU"],
                             **{c: cnt.get(c, 0) for c in classes}}
    out["D1_R_whole_map"]["sum_equals_M"] = sum(out["D1_R_whole_map"].values()) - cnt.get("X", 0) == len(M)

    # ── NR? marking ──
    def nr_unestablished(r):
        k = (r["stamp"], r["idx"])
        why = []
        if not fam_ok["primary"]:
            why.append("primary_leg_family")
        if not fam_ok["coherent"]:
            why.append("coherent_leg_family")
        if r["band"] in band_ne:
            why.append("band")
        if terc(r["snr"]) in terc_ne:
            why.append("tercile")
        return why
    nrq = {}
    for r in N:
        k = (r["stamp"], r["idx"])
        if cls[k] == "NR":
            w = nr_unestablished(r)
            nrq[k] = w
    nrq_n = sum(1 for w in nrq.values() if w)
    out["NR_split"] = {"NR_total": cnt.get("NR", 0), "NR_not_established": nrq_n, "NR_established": cnt.get("NR", 0) - nrq_n,
                       "reasons": dict(collections.Counter(x for w in nrq.values() for x in w))}

    # ── D2-R, D3-R, D4-R ──
    out["D2_R_RP_cell"] = {c: dict(collections.Counter(legs[(r["stamp"], r["idx"])]["fp_cell"] for r in N if cls[(r["stamp"], r["idx"])] == c)) for c in ("RP-native", "RP-search")}
    out["D3_R_by_band"] = {c: {b: sum(1 for r in N if cls[(r["stamp"], r["idx"])] == c and r["band"] == b) for b in "ABCD"} for c in classes}
    loads = np.array([len(ref[s]) for s in stamps])
    qedges = np.percentile(loads, [20, 40, 60, 80])
    quint = lambda n: int(np.searchsorted(qedges, n, side="right")) + 1
    out["D4_R_by_load_quintile"] = {c: {q: sum(1 for r in N if cls[(r["stamp"], r["idx"])] == c and quint(r["n_cycle_ref"]) == q) for q in range(1, 6)} for c in classes}
    out["D4_R_quintile_edges"] = [float(x) for x in qedges]
    # NR standardised q1 -> q5 as DENS (descriptive, never a DENSITY result)
    ncyc = len(stamps)
    refc = np.array([len(ref[s]) for s in stamps], dtype=float)
    order = sorted(range(ncyc), key=lambda i: (refc[i], i))
    groups = [order[i * 80:(i + 1) * 80] for i in range(5)]
    BANDS = list("ABCD")
    keep = [b for b in BANDS if b not in band_ne]
    band_w = {b: sum(1 for r in rows if r["band"] == b) for b in BANDS}
    wsum = sum(band_w[b] for b in keep)
    wts = {b: band_w[b] / wsum for b in keep}
    cellR = collections.Counter((cyc_idx[r["stamp"]], r["band"]) for r in rows)
    cellNR = collections.Counter((cyc_idx[r["stamp"]], r["band"]) for r in N if cls[(r["stamp"], r["idx"])] == "NR")
    def std_rate(cl):
        Rb = {b: sum(cellR[(i, b)] for i in cl) for b in BANDS}
        Xb = {b: sum(cellNR[(i, b)] for i in cl) for b in BANDS}
        for b in ("D", "C", "B"):
            if Rb[b] < 30:
                nb = BANDS[BANDS.index(b) - 1]
                Rb[nb] += Rb[b]; Xb[nb] += Xb[b]; Rb[b] = 0; Xb[b] = 0
        tot = wsm = 0.0
        for b in keep:
            if Rb[b] > 0:
                tot += wts[b] * Xb[b] / Rb[b]; wsm += wts[b]
        return tot / wsm if wsm else float("nan")
    out["D4_R_NR_std_rate_q1_to_q5"] = [std_rate(g) for g in groups]
    # ── D5-R: F_wrong per leg and buffer; W rows ──
    fw = collections.Counter()
    for r in N:
        for b, rec in fN.get((r["stamp"], r["idx"]), {}).items():
            if rec.get("unencodable"):
                continue
            if rec["fp"]["wrong"] > 0 and not rec["fp"]["found"]:
                fw[(b, "FP_wrong")] += 1
            if rec["fc"]["v3_wrong"]:
                fw[(b, "V3_wrong")] += 1
            if rec["walk"]["wrong"]:
                fw[(b, "walk_wrong")] += 1
    out["D5_R_F_wrong"] = {f"{k[0]}|{k[1]}": v for k, v in fw.items()}
    Wrows = [r for r in N if I2.wrong_any(old[(r["stamp"], r["idx"])])]
    notW = [r for r in N if not I2.wrong_any(old[(r["stamp"], r["idx"])])]
    rec_ = lambda sel: sum(1 for r in sel if cls[(r["stamp"], r["idx"])] not in ("NR", "X"))
    out["D5_R_W_rows"] = {"W_n": len(Wrows), "W_recovered": rec_(Wrows), "W_share": rec_(Wrows) / len(Wrows) if Wrows else None,
                          "otherN_n": len(notW), "otherN_recovered": rec_(notW), "otherN_share": rec_(notW) / len(notW) if notW else None}
    # ── D6-R: offered / never offered for RC, RG, RW ──
    plan = {}
    for stamp in {r["stamp"] for r in N}:
        pth = f"{CAP}/plan/{stamp}.tsv"
        plan[stamp] = [tuple(map(float, l.split("\t"))) for l in open(pth, encoding="utf-8")] if os.path.exists(pth) else None
    def offered(r, df, dth):
        pl = plan[r["stamp"]]
        if pl is None:
            return None
        return any(abs(f - r["freq"]) <= df and abs(d - (r["dt"] + DELTA_C)) <= dth for f, d in pl)
    d6 = {}
    for c in ("RC", "RG", "RW"):
        sel = [r for r in N if cls[(r["stamp"], r["idx"])] == c]
        o1 = [offered(r, WIN_DF, WIN_DT_HALF) for r in sel]
        o2 = [offered(r, WIN_DF_S, WIN_DT_HALF_S) for r in sel]
        d6[c] = {"n": len(sel), "offered": sum(1 for x in o1 if x), "never_offered": sum(1 for x in o1 if x is False), "no_plan": sum(1 for x in o1 if x is None),
                 "sens_offered": sum(1 for x in o2 if x), "sens_never_offered": sum(1 for x in o2 if x is False)}
    tot = {k: sum(d6[c][k] for c in d6) for k in ("n", "offered", "never_offered", "sens_offered", "sens_never_offered")}
    d6["all"] = {**tot, "never_offered_share": tot["never_offered"] / tot["n"] if tot["n"] else None,
                 "sens_never_offered_share": tot["sens_never_offered"] / tot["n"] if tot["n"] else None}
    out["D6_R"] = d6
    # ── D7-R: F1b of RG rows relative to T1 ──
    f1b = []
    for r in N:
        k = (r["stamp"], r["idx"])
        if cls[k] != "RG":
            continue
        for b, rec in fN[k].items():
            if rec["fc"]["v3_match"] and rec["fc"]["gated"] == 0 and rec["fc"]["f1b_db"] is not None:
                f1b.append(rec["fc"]["f1b_db"]); break
    out["D7_R"] = {"n": len(f1b), "median_f1b": float(np.median(f1b)) if f1b else None, "within_1dB_above_T1": sum(1 for v in f1b if T1 < v <= T1 + 1.0),
                   "within_3dB_above_T1": sum(1 for v in f1b if T1 < v <= T1 + 3.0)}
    # ── per-station clustering ──
    stn = {}
    for c in classes:
        keys = collections.Counter(I2.station_key(ref[r["stamp"]][r["idx"]][3]) for r in N if cls[(r["stamp"], r["idx"])] == c)
        t = sum(keys.values())
        stn[c] = {"rows": t, "distinct_senders": len(keys), "top_sender_share": (max(keys.values()) / t) if t else None,
                  "top5_share": (sum(v for _, v in keys.most_common(5)) / t) if t else None}
    out["per_station_clustering"] = stn

    # ── routing rows: bootstrap the 400 cycles ──
    rng = np.random.default_rng(SEED)
    per = {c: np.zeros(ncyc) for c in classes + ["NRq"]}
    for r in N:
        k = (r["stamp"], r["idx"])
        c = cls[k]
        if c in per:
            per[c][cyc_idx[r["stamp"]]] += 1
        if c == "NR" and nrq.get(k):
            per["NRq"][cyc_idx[r["stamp"]]] += 1
    idx = rng.integers(0, ncyc, size=(B, ncyc))
    den = refc[idx].sum(axis=1)
    def ci(arr):
        v = 100.0 * arr[idx].sum(axis=1) / den
        return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
    pt = lambda arr: 100.0 * arr.sum() / refc.sum()
    comb = per["RC"] + per["RG"] + per["RW"]
    rp_all = per["RP-native"] + per["RP-search"]
    nr_est = per["NR"] - per["NRq"]
    out["routing"] = {
        "RP-search": {"pp": pt(per["RP-search"]), "CI": ci(per["RP-search"])},
        "RP-native": {"pp": pt(per["RP-native"]), "CI": ci(per["RP-native"])},
        "RC+RG+RW": {"pp": pt(comb), "CI": ci(comb)},
        "RC": {"pp": pt(per["RC"]), "CI": ci(per["RC"])}, "RG": {"pp": pt(per["RG"]), "CI": ci(per["RG"])}, "RW": {"pp": pt(per["RW"]), "CI": ci(per["RW"])},
        "NR": {"pp": pt(per["NR"]), "CI": ci(per["NR"])}, "NR?": {"pp": pt(per["NRq"]), "CI": ci(per["NRq"])},
        "NR_minus_NR?": {"pp": pt(nr_est), "CI": ci(nr_est)}}
    sum_points = pt(rp_all) + pt(per["RC"]) + pt(per["RG"]) + pt(per["RW"])
    r_rp = out["routing"]["RP-search"]["CI"][0] >= BAR_L_PP
    r_rc = out["routing"]["RC+RG+RW"]["CI"][0] >= BAR_L_PP
    r_nr = out["routing"]["NR_minus_NR?"]["CI"][0] >= sum_points
    out["routing"]["sum_of_points_RP_RC_RG_RW"] = sum_points
    out["routing"]["rows"] = {"R-RP": bool(r_rp), "R-RC": bool(r_rc), "R-NR": bool(r_nr), "R-0": not (r_rp or r_rc or r_nr)}
    out["routing"]["note"] = "R-NR sum uses RP-native + RP-search (all RP), the harder reading; no multiplicity adjustment"
    # R-RC wording: never-offered share (A1.3): native window
    out["routing"]["R-RC_never_offered_at_least_half"] = bool(d6["all"]["never_offered_share"] is not None and d6["all"]["never_offered_share"] >= 0.5)
    out["routing"]["R-RC_never_offered_at_least_half_sensitivity"] = bool(d6["all"]["sens_never_offered_share"] is not None and d6["all"]["sens_never_offered_share"] >= 0.5)
    # ── D8: the ON arm tag (if present) ──
    on_nc = NEW + "/scratch/on/nc_dump.tsv"
    if os.path.exists(on_nc):
        nc = collections.defaultdict(list)
        for r in C.load_tsv(on_nc):
            if len(r) >= 11:
                nc[r[0]].append((int(r[1]), int(r[2]), int(r[3]), float(r[4]), int(r[5]), int(r[9]), r[10]))
        match_on = F.rebuild_matching(ref, nc)
        pub = {(s, i) for s, m in match_on.items() for i in m}
        pubN = [r for r in N if (r["stamp"], r["idx"]) in pub]
        ck = collections.Counter(cls[(r["stamp"], r["idx"])] for r in pubN)
        out["D8"] = {"N_rows_published_by_ON_arm": len(pubN), "by_class": dict(ck),
                     "D1_R_with_those_rows_removed": {c: cnt.get(c, 0) - ck.get(c, 0) for c in classes}}
    json.dump(out, open(NEW + "/result_main.json", "w"), indent=1, sort_keys=True, default=str)
    print(json.dumps(out, indent=1, sort_keys=True, default=str))


if __name__ == "__main__":
    mp.freeze_support()
    {"force": cmd_force, "analyse": main_analyse}[sys.argv[1]]()
