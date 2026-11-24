#!/usr/bin/env python3
"""TA-CHECK analysis (spec 2006 + Amendment 1 `4336a281`).  Reads the frozen groups and the scores; writes numbers only.
    python tc_analyse.py ctrl      V-CTRL on B1 and B1m (+ V-NULL, calibration): needs only scores_ctrl.json; reads NO target row.
    python tc_analyse.py main      the full readout and the mechanical decision (A1.2): needs scores_ctrl.json AND scores_tgt.json.  Run ONCE per frozen scoring."""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tc_lib as L          # noqa: E402

OUT = "D:/Projects/claude/_qa-scratch/ta-check"
CRC2 = "D:/Projects/claude/_qa-scratch/coh-res-cand-v2/crc2_result.json"


def load():
    g = json.load(open(OUT + "/frozen/tc_groups.json"))
    sc = json.load(open(OUT + "/scores_ctrl.json"))
    return g, sc


def present(share):
    return share >= L.T_FROZEN


def group_rows(rows, scores, sel):
    return [(r["stamp"], r["band"], present(scores[f"{r['stamp']}:{r['idx']}"]), scores[f"{r['stamp']}:{r['idx']}"], r) for r in rows if sel(r)]


def pr_ci(tl, idx):
    p = L.rate(tl, idx)
    return float(tl[1].sum() / tl[0].sum()), L.ci(p), p


def ctrl_only():
    g, sc = load()
    stamps = g["stamps"]
    cix = {s: i for i, s in enumerate(stamps)}
    idx = L.boot_idx(len(stamps))
    out = {"calibration_c_off_s": sc["c_off"], "V_NULL": sc["null_this_night"]}
    keys = set(sc["scores"])
    for name, flag in (("B1", "in_B1"), ("B1m", "in_B1m")):
        rows = [r for r in g["rows"] if r[flag]]
        assert all(f"{r['stamp']}:{r['idx']}" in keys for r in rows), "ctrl scores miss rows of " + name
        tl = L.tally([(s, b, p) for s, b, p, _, _ in group_rows(g["rows"], sc["scores"], lambda r: r[flag])], len(stamps), cix)
        pt, c, _ = pr_ci(tl, idx)
        out[name] = {"rows": int(tl[0].sum()), "PR": pt, "CI": c, "by_band": {b: {"n": int(tl[2][b].sum()), "PR": (float(tl[3][b].sum() / tl[2][b].sum()) if tl[2][b].sum() else None)} for b in L.BANDS}}
    out["V_CTRL_B1_ge_0.80"] = bool(out["B1"]["CI"][0] >= L.BAR)
    out["TC_6_B1m_CI_lo_ge_0.80"] = bool(out["B1m"]["CI"][0] >= L.BAR)
    return out


def deciles(v):
    return [float(x) for x in np.percentile(v, range(10, 100, 10))] if len(v) else None


def main_readout():
    g, sc = load()
    st = json.load(open(OUT + "/scores_tgt.json"))
    scores = dict(sc["scores"])
    scores.update(st["scores"])
    assert len(scores) == len(sc["scores"]) + len(st["scores"]), "ctrl and tgt scores overlap"
    rows = g["rows"]
    assert all(f"{r['stamp']}:{r['idx']}" in scores for r in rows), "a pooled row has no score"
    stamps = g["stamps"]
    cix = {s: i for i, s in enumerate(stamps)}
    idx = L.boot_idx(len(stamps))
    G = lambda sel: group_rows(rows, scores, sel)
    tl = lambda sel: L.tally([(s, b, p) for s, b, p, _, _ in G(sel)], len(stamps), cix)
    B1, B1m = tl(lambda r: r["in_B1"]), tl(lambda r: r["in_B1m"])
    T, Tbur, Tiso = tl(lambda r: r["in_T"]), tl(lambda r: r["in_Tbur"]), tl(lambda r: r["in_T"] and not r["bur"])
    T4, T5 = tl(lambda r: r["batch"] == 4), tl(lambda r: r["batch"] == 5)
    res = {}
    for name, t in (("B1", B1), ("B1m", B1m), ("T", T), ("T_bur", Tbur), ("T_iso", Tiso), ("T4", T4), ("T5", T5)):
        pt, c, _ = pr_ci(t, idx)
        res[name] = {"rows": int(t[0].sum()), "PR": pt, "CI": c, "by_band": {b: {"n": int(t[2][b].sum()), "PR": (float(t[3][b].sum() / t[2][b].sum()) if t[2][b].sum() else None)} for b in L.BANDS}}
    pB1m, pT = L.rate(B1m, idx), L.rate(T, idx)
    bands, w, left_out = L.std_bands(Tiso, Tbur)
    iso, bur, diff = L.pr_std_contrast(Tiso, Tbur, idx, bands, w)
    res["B1m_minus_T"] = {"point": res["B1m"]["PR"] - res["T"]["PR"], "CI": L.ci(pB1m - pT)}
    res["std_contrast"] = {"bands": bands, "weights": w, "T_bur_rows_left_out": left_out, "PR_std_T_iso": {"point": float(np.nanmean(iso)), "CI": L.ci(iso)},
                           "PR_T_bur_in_bands": {"point": float(np.nanmean(bur)), "CI": L.ci(bur)}, "diff_T_iso_std_minus_T_bur": {"CI": L.ci(diff)}, "replicates_nan": int(np.sum(~np.isfinite(diff)))}
    rr = {"n_T": res["T"]["rows"], "n_Tbur": res["T_bur"]["rows"], "ci_B1": res["B1"]["CI"], "ci_B1m": res["B1m"]["CI"], "ci_T": res["T"]["CI"], "ci_Tbur": res["T_bur"]["CI"],
          "ci_B1m_minus_T": res["B1m_minus_T"]["CI"], "ci_std_diff": res["std_contrast"]["diff_T_iso_std_minus_T_bur"]["CI"]}
    verdict = L.decide(rr)
    # descriptives
    bur_rows = G(lambda r: r["in_Tbur"])
    desc = {"PR_by_batch": {}, "T_by_band": res["T"]["by_band"]}
    for b in (1, 2, 3, 4, 5):
        rs = [(p, sh) for _, _, p, sh, r in G(lambda r, b=b: r["batch"] == b and (r["in_B1"] if b == 1 else True))]
        desc["PR_by_batch"][str(b)] = {"n": len(rs), "PR": (sum(p for p, _ in rs) / len(rs)) if rs else None, "note": "batch 1 = the B1 draw" if b == 1 else ""}
    for name, key in (("nbr_dsnr", 0), ("nbr_abs_df", 1)):
        vals = [r["nbr"][key] for _, _, _, _, r in bur_rows]
        q = np.percentile(vals, [25, 50, 75])
        desc["T_bur_PR_by_" + name + "_quartile"] = {"cuts": [float(x) for x in q], "q": {str(k): {"n": sum(1 for _, _, _, _, r in bur_rows if int(np.searchsorted(q, r["nbr"][key], side="right")) == k),
                                                                                              "PR": (lambda xs: (sum(xs) / len(xs)) if xs else None)([p for _, _, p, _, r in bur_rows if int(np.searchsorted(q, r["nbr"][key], side="right")) == k])} for k in range(4)}}
    desc["tone_share_deciles_T_bur"] = deciles([sh for _, _, _, sh, _ in bur_rows])
    desc["tone_share_deciles_B1"] = deciles([sh for _, _, _, sh, _ in G(lambda r: r["in_B1"])])
    desc["tone_share_deciles_B1m"] = deciles([sh for _, _, _, sh, _ in G(lambda r: r["in_B1m"])])
    try:
        c2 = json.load(open(CRC2))
        sp = c2["descriptive"]["not_corroborated_new_text_split_per_cycle"]
        n_cyc = c2["cycles"]
        tested = (sp["tested_absent"] + sp["tested_present"]) * n_cyc
        desc["arithmetic_check_v2_new_text_rows"] = {"tested_rows": tested, "observed_tested_absent": sp["tested_absent"] * n_cyc, "expected_tested_absent_if_every_tested_row_real": (1 - res["T"]["PR"]) * tested}
    except Exception as e:                  # noqa: BLE001
        desc["arithmetic_check_v2_new_text_rows"] = {"error": type(e).__name__}
    return {"verdict": verdict, "rule_inputs": rr, "V_N": {"n_T": rr["n_T"], "n_Tbur": rr["n_Tbur"], "n_T5": res["T5"]["rows"]}, "results": res, "descriptives": desc,
            "V_NULL": sc["null_this_night"], "calibration_c_off_s": sc["c_off"], "limits": ["not-corroborated rows are not in the test", f"PR(T5) rests on {res['T5']['rows']} rows", "WSJT-X's dt may lower every PR slightly (B1 / B1m measure it)"]}


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "ctrl":
        r = ctrl_only()
        json.dump(r, open(OUT + "/ctrl_result.json", "w"), indent=1)
    elif mode == "main":
        r = main_readout()
        json.dump(r, open(OUT + "/tc_result.json", "w"), indent=1)
    else:
        sys.exit(__doc__)
    print(json.dumps(r, indent=1))
