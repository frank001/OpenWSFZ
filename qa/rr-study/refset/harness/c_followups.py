#!/usr/bin/env python
"""Architect ruling 2026-10-13 16:10Z, corrections C1, C4, C5 (QA; analysis only, no decoding; aggregates only).

  python c_followups.py --corpus <corpus> --passdir <first-run dir> --out <json>

C1  legs B and A WITHOUT every block whose source run is 20260803_live_run_1713 (named before the burst check was read, so it is the second
    REPORTED form; the burst-cycle exclusion stays a third, post hoc sensitivity): matched share (non-hashed and by key, cycle-clustered CI),
    OWS-only rows and share of WSJT-X's rows, and the by-band shares (20 m included).
C4  leg B: band x union-crowding cut (descriptive, no bar): matched share and OWS-only per cell.
C5  paired per-cycle B minus A on the same cycles: difference of matched shares (and of OWS-only counts), cycle-clustered bootstrap CI
    (the SAME resampled cycles for both legs), non-hashed and by key. Scores prediction RS3.
Message text is read inside score_vs_wsjtx's readers and never leaves; the output is counts and shares.
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import burst_check as bc  # noqa: E402
import refset_score as rs  # noqa: E402
import score_vs_wsjtx as sv  # noqa: E402

EXCLUDED_NIGHT = "20260803_live_run_1713"
BOOT_N, BOOT_SEED = 2000, 20261013


def share_block(sel, nonhashed):
    num = [sum(1 for (_, h, m) in c["live"] if m and (not nonhashed or not h)) for c in sel]
    den = [sum(1 for (_, h, _m) in c["live"] if (not nonhashed or not h)) for c in sel]
    ext = sum(1 for c in sel for (_, h, m) in c["own"] if (not m) and (not nonhashed or not h))
    return {"matched_share_of_wsjtx_rows": sv.ci(num, den),
            "owsonly_rows": int(ext), "owsonly_share_of_wsjtx_rows": round(ext / max(1, sum(den)), 4),
            "owsonly_per_cycle": round(ext / len(sel), 3) if sel else None}


def form(sel):
    out = {"cycles": len(sel), "wsjtx_rows": sum(c["n_live"] for c in sel), "ows_rows": sum(c["n_own"] for c in sel),
           "nonhashed": share_block(sel, True), "all_by_key": share_block(sel, False), "by_band": {}}
    for band in sorted({c["band"] for c in sel}):
        out["by_band"][band] = share_block([c for c in sel if c["band"] == band], True)
    return out


def paired(B, A, nonhashed):
    assert [(c["block"], c["stamp"]) for c in B] == [(c["block"], c["stamp"]) for c in A], "legs not on the same cycles"
    def vec(cyc):
        num = np.array([sum(1 for (_, h, m) in c["live"] if m and (not nonhashed or not h)) for c in cyc], float)
        den = np.array([sum(1 for (_, h, _m) in c["live"] if (not nonhashed or not h)) for c in cyc], float)
        ext = np.array([sum(1 for (_, h, m) in c["own"] if (not m) and (not nonhashed or not h)) for c in cyc], float)
        return num, den, ext
    nb, db, eb = vec(B)
    na, da, ea = vec(A)
    assert (db == da).all(), "WSJT-X denominators differ between legs"
    n = len(B)
    rng = np.random.default_rng(BOOT_SEED)
    idx = rng.integers(0, n, size=(BOOT_N, n))
    d = db[idx].sum(axis=1)
    diff = (nb[idx].sum(axis=1) - na[idx].sum(axis=1)) / np.where(d > 0, d, 1)
    ediff = eb[idx].sum(axis=1) - ea[idx].sum(axis=1)
    lo, hi = np.percentile(diff, [2.5, 97.5])
    elo, ehi = np.percentile(ediff, [2.5, 97.5])
    cyc_diff = nb - na
    return {"cycles": n, "wsjtx_rows": int(db.sum()),
            "matched_rows_B": int(nb.sum()), "matched_rows_A": int(na.sum()), "matched_rows_B_minus_A": int(nb.sum() - na.sum()),
            "share_B": round(float(nb.sum() / db.sum()), 4), "share_A": round(float(na.sum() / db.sum()), 4),
            "share_B_minus_A_pp": round(float((nb.sum() - na.sum()) / db.sum() * 100), 3),
            "ci95_pp": [round(float(lo) * 100, 3), round(float(hi) * 100, 3)],
            "owsonly_B_minus_A_rows": int(eb.sum() - ea.sum()), "owsonly_B_minus_A_ci95_rows": [round(float(elo), 1), round(float(ehi), 1)],
            "cycles_B_gt_A": int((cyc_diff > 0).sum()), "cycles_B_lt_A": int((cyc_diff < 0).sum()), "cycles_equal": int((cyc_diff == 0).sum())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--passdir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    man = rs.load_json(os.path.join(a.corpus, "manifest.json"))
    pins = [json.loads(l) for l in open(os.path.join(a.passdir, "pins.jsonl")) if l.strip()]
    order = []
    for p in pins:
        if p.get("leg") == "A" and p["block"] not in order:
            order.append(p["block"])
    by_id = {b["id"]: b for b in man["blocks"]}
    blocks = [by_id[b] for b in order]
    B = bc.load(a.corpus, a.passdir, "B", blocks)
    A = bc.load(a.corpus, a.passdir, "A", blocks)
    night_blocks = [b for b in blocks if b["run"] == EXCLUDED_NIGHT]
    assert night_blocks, "the excluded night is not in the drawn blocks"
    res = {"label": "first run, OpenWSFZ legs only (A, D, B); leg E pending. Analysis of the working files, no new decoding. Architect ruling 2026-10-13 C1, C4, C5.",
           "excluded_night": EXCLUDED_NIGHT,
           "excluded_night_blocks": len(night_blocks), "excluded_night_bands": sorted({b["band"] for b in night_blocks}),
           "excluded_night_cycles": sum(1 for c in B if c["run"] == EXCLUDED_NIGHT), "blocks_total": len(blocks), "cycles_total": len(B)}
    res["C1_all_nights"] = {"leg_B": form(B), "leg_A": form(A)}
    res["C1_without_night"] = {"leg_B": form([c for c in B if c["run"] != EXCLUDED_NIGHT]),
                               "leg_A": form([c for c in A if c["run"] != EXCLUDED_NIGHT])}
    res["C1_night_only"] = {"leg_B": form([c for c in B if c["run"] == EXCLUDED_NIGHT])}
    # C4: band x union crowding, leg B
    res["C4_band_x_union_crowding_leg_B"] = {}
    for band in sorted({c["band"] for c in B}):
        row = {}
        for name, lo, hi in sv.CROWD_BINS:
            sel = [c for c in B if c["band"] == band and lo <= c["union"] <= hi]
            if sel:
                s = share_block(sel, True)
                row[name] = {"matched": s["matched_share_of_wsjtx_rows"], "owsonly_rows": s["owsonly_rows"]}
        res["C4_band_x_union_crowding_leg_B"][band] = row
    res["C4_band_x_union_crowding_leg_B_without_night"] = {}
    for band in sorted({c["band"] for c in B}):
        row = {}
        for name, lo, hi in sv.CROWD_BINS:
            sel = [c for c in B if c["run"] != EXCLUDED_NIGHT and c["band"] == band and lo <= c["union"] <= hi]
            if sel:
                s = share_block(sel, True)
                row[name] = {"matched": s["matched_share_of_wsjtx_rows"], "owsonly_rows": s["owsonly_rows"]}
        res["C4_band_x_union_crowding_leg_B_without_night"][band] = row
    # C5: paired B - A
    res["C5_paired_B_minus_A"] = {"nonhashed": paired(B, A, True), "all_by_key": paired(B, A, False),
                                  "nonhashed_without_night": paired([c for c in B if c["run"] != EXCLUDED_NIGHT], [c for c in A if c["run"] != EXCLUDED_NIGHT], True)}
    with open(a.out, "w") as fh:
        json.dump(res, fh, indent=1)
    wn = res["C1_without_night"]["leg_B"]
    print("night blocks", len(night_blocks), "cycles", res["excluded_night_cycles"])
    print("B without night: matched", wn["nonhashed"]["matched_share_of_wsjtx_rows"], "owsonly", wn["nonhashed"]["owsonly_rows"], wn["nonhashed"]["owsonly_share_of_wsjtx_rows"])
    print("paired nonhashed", res["C5_paired_B_minus_A"]["nonhashed"])


if __name__ == "__main__":
    main()
