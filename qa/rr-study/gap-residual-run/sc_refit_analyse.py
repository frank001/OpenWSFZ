#!/usr/bin/env python3
"""CS-REFIT analysis (spec `arch/cs-refit` ad74a8a0 + Amendment 1 5a971659). Rows and the decision rule are the code below; SUB-COVER's analysis (sc_analyse.py) is reused, not changed.

    python sc_refit_analyse.py main     after repro.json, legs.json and the three forced runs.

Definitions (frozen):
  "decodable" = forced primary found OR forced coherent v3_match (sc_analyse.either; an unencodable row is not decodable).
  subtraction SET (A1.1) = the matched batch-1 decodes, and the matched batch-2 decodes in the 382 cycles with a stored R3, whose own text is re-encodable and encodes (what the product subtracted).
  L-REPRO : from repro.json: the builder with the procedure "as the product" reproduces the stored R3 (382 cycles) and the stored R2 (400): bit-identical or max |diff| <= 1e-5 x peak. Fails => STOP.
  L-CTRL  : per leg, SET hits still decodable, paired against R3B on the same rows: CI_hi(share_leg - share_R3B) <= +2.0 pp, batch-1 and batch-2 separately (cycle bootstrap).
  L-LOSS  : per leg, rows NOT in the set that are decodable on R3B and not on the leg (counted), and NET_all (A1.3) = rows not in the set decodable on the leg minus decodable on R3B, pp of n_ref.
  L-FZ    : fit-zero share per leg beside the product-procedure rebuild's; REPORT ONLY.
  G_CS(leg) : CS rows (NR-TAX tag cat == CS, the 700) decodable on the leg and NOT decodable on O u R2 u R3 (forced_all.jsonl records; where R3 has none, R2 covers); pp of n_ref 12,124. THE decision number.
  DECISION (each leg valid only if L-REPRO and that leg's L-CTRL pass):
     BUILD-WORTH if for at least one leg CI_lo(G_CS) >= 1.0 pp AND CI_lo(NET_all) > 0;  CLOSE if for both legs CI_hi(G_CS) < 0.5 pp;  BETWEEN otherwise.
Bootstrap: B = 2000 cycle resamples, seed 20261109. Counts only leave this script (HK-037)."""
from __future__ import annotations

import collections
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "gap-relocate-run"))
import sc_analyse as A      # noqa: E402
import sc_build as B        # noqa: E402
import nrtax_defs as D      # noqa: E402

CS = "D:/Projects/claude/_qa-scratch/cs-refit"
A.SEED = 20261109
BUILD_WORTH_LO, CLOSE_HI, CTRL_MARGIN_PP, NET_LO = 1.0, 0.5, 2.0, 0.0
assert (A.B, A.SEED, BUILD_WORTH_LO, CLOSE_HI, CTRL_MARGIN_PP, NET_LO) == (2000, 20261109, 1.0, 0.5, 2.0, 0.0)
LEGS = ("S", "I")


def main():
    B._init()
    pop, tags = A.pop_and_tags()
    stamps = pop["stamps"]
    rows = pop["rows"]
    assert len(rows) == 12124
    boot = A.Boot(stamps)
    denall = boot.arr(collections.Counter(r["stamp"] for r in rows))
    fall = A.load_forced(A.GR + "/forced_all.jsonl")
    fk = {k: A.load_forced(f"{CS}/forced_{k}.jsonl") for k in ("R3B",) + LEGS}
    rep = json.load(open(f"{CS}/repro.json"))["summary"]
    legs = json.load(open(f"{CS}/legs.json"))
    ls = legs["summary"]
    has_r3 = {c["stamp"]: c["has_r3"] for c in legs["cycles"]}
    res = {"n_ref": len(rows), "L-REPRO": rep["L-REPRO"] | {k: rep[k] for k in ("R2_bit_identical", "R3_cycles", "R3_bit_identical", "R3_max_rel", "R2_max_rel", "no_r3_cycles", "no_r3_batch2_candidates_descriptive")}}
    # the subtraction set: matched batch-1/2 decodes whose own text re-encodes (batch 2 only where the cycle has a stored R3)
    pubs = B.load_published()
    ptext = {}
    for s in stamps:
        for pk in pubs.get(s, []):
            ptext[(s, pk["kind"], pk["f"], round(pk["dt"], 1), pk["snr"])] = pk["text"].rstrip()
    in_set = set()
    for r in rows:
        if not r["matched"] or r["kind"] not in (1, 2) or (r["kind"] == 2 and not has_r3[r["stamp"]]):
            continue
        t = ptext.get((r["stamp"], r["kind"], r["ows_freq"], round(r["ows_dt"], 1), r["ows_snr"]))
        if t is not None and D.reencodable(t) and B.encode(t) is not None:
            in_set.add((r["stamp"], r["idx"]))
    res["set_rows"] = {"batch1": sum(1 for r in rows if (r["stamp"], r["idx"]) in in_set and r["kind"] == 1), "batch2": sum(1 for r in rows if (r["stamp"], r["idx"]) in in_set and r["kind"] == 2)}
    rb1 = [r for r in rows if (r["stamp"], r["idx"]) in in_set and r["kind"] == 1]
    rb2 = [r for r in rows if (r["stamp"], r["idx"]) in in_set and r["kind"] == 2]
    nonset = [r for r in rows if (r["stamp"], r["idx"]) not in in_set]
    # CS rows and their old-buffer decodability
    nr = [r for r in rows if tags.get((r["stamp"], r["idx"]), {}).get("pop") == "NR"]
    assert len(nr) == 1589
    by_cycle = collections.defaultdict(list)
    for r in rows:
        by_cycle[r["stamp"]].append({"idx": r["idx"], "snr": r["snr"], "freq": r["freq"], "decoded": bool(r["matched"])})

    def old_dec(k):
        return any(A.either(fall.get(k, {}).get(b)) for b in ("O", "R2", "R3"))

    cs = [r for r in nr if tags[(r["stamp"], r["idx"])]["cat"] == "CS"]
    assert len(cs) == 700, len(cs)
    gaps = {}
    for r in cs:
        st = [n["snr"] - r["snr"] for n in by_cycle[r["stamp"]] if n["idx"] != r["idx"] and abs(n["freq"] - r["freq"]) < 50.0 and n["snr"] >= r["snr"] and n["decoded"]]
        gaps[(r["stamp"], r["idx"])] = max(st) if st else None
    gv = [g for g in gaps.values() if g is not None]
    qedges = [float(np.percentile(gv, p)) for p in (25, 50, 75)] if gv else []
    res["CS_gap_quartile_edges_dB"] = qedges
    res["legs"] = {}
    for leg in LEGS:
        fl = fk[leg]
        out = {}
        # L-CTRL
        c1 = A.share_pair(rb1, fk["R3B"], fl, "R3B", leg, boot)
        c2 = A.share_pair(rb2, fk["R3B"], fl, "R3B", leg, boot)
        out["L-CTRL"] = {"batch1": c1, "batch2": c2, "margin_pp": CTRL_MARGIN_PP, "PASS": c1["diff_pp"]["CI"][1] <= CTRL_MARGIN_PP and c2["diff_pp"]["CI"][1] <= CTRL_MARGIN_PP}
        # NET_all / L-LOSS over rows not in the set
        gain, loss = collections.Counter(), collections.Counter()
        for r in nonset:
            k = (r["stamp"], r["idx"])
            dl = A.either(fl.get(k, {}).get(leg))
            db = A.either(fk["R3B"].get(k, {}).get("R3B"))
            gain[r["stamp"]] += (dl and not db)
            loss[r["stamp"]] += (db and not dl)
        g, l = boot.arr(gain), boot.arr(loss)
        out["L-LOSS"] = {"rows_lost": int(l.sum()), "rows_gained": int(g.sum()), "NET_all": boot.pp(g - l, denall), "population_rows": len(nonset)}
        # G_CS and the strata
        cat_new = collections.defaultdict(collections.Counter)
        cat_den = collections.Counter()
        wrong = collections.Counter()
        new_cs = collections.Counter()
        qn = collections.defaultdict(collections.Counter)
        qd = collections.Counter()
        for r in nr:
            k = (r["stamp"], r["idx"])
            rec = fl.get(k, {}).get(leg)
            new = A.either(rec) and not old_dec(k)
            cat = tags[k]["cat"]
            cat_den[cat] += 1
            cat_new[cat][r["stamp"]] += new
            wrong[r["stamp"]] += A.anywrong(rec)
            if cat == "CS":
                new_cs[r["stamp"]] += new
                gp = gaps[k]
                q = "no-gap" if gp is None else ("Q1" if gp <= qedges[0] else "Q2" if gp <= qedges[1] else "Q3" if gp <= qedges[2] else "Q4")
                qd[q] += 1
                qn[q][r["stamp"]] += new
        gcs = boot.arr(new_cs)
        out["G_CS"] = {"rows": int(gcs.sum()), **boot.pp(gcs, denall)}
        out["G_by_category"] = {c: {"nr_rows": cat_den[c], "new_rows": int(boot.arr(cat_new[c]).sum()), **boot.pp(boot.arr(cat_new[c]), denall)} for c in sorted(cat_den)}
        out["G_CS_by_gap_quartile"] = {q: {"cs_rows": qd[q], "new_rows": int(boot.arr(qn[q]).sum())} for q in sorted(qd)}
        out["rows_with_wrong_payload_at_NR"] = int(boot.arr(wrong).sum())
        out["valid"] = bool(res["L-REPRO"]["PASS"] and out["L-CTRL"]["PASS"])
        out["BUILD_WORTH_row"] = bool(out["G_CS"]["CI"][0] >= BUILD_WORTH_LO and out["L-LOSS"]["NET_all"]["CI"][0] > NET_LO)
        out["CLOSE_row"] = bool(out["G_CS"]["CI"][1] < CLOSE_HI)
        res["legs"][leg] = out
    # L-FZ and time (descriptive)
    res["L-FZ_report_only"] = {"product_rebuild": {"fits": ls["fits_product"], "fit_zero": ls["fit_zero_product"], "share": ls["fit_zero_product"] / ls["fits_product"]},
                               "S": {"fits": ls["members_total"], "fit_zero": ls["fit_zero_S"], "share": ls["fit_zero_S"] / ls["members_total"]},
                               "I": {"fits": ls["members_total"], "fit_zero": ls["fit_zero_I"], "share": ls["fit_zero_I"] / ls["members_total"]}}
    res["time_descriptive"] = {"ratio_S_over_product_rebuild": ls["ratio_S_over_product"], "ratio_I_over_product_rebuild": ls["ratio_I_over_product"],
                               "note": "both on the same worker pool; the product rebuild here is sequential too, not the product's parallel fit (A1.4): the ratio only"}
    valid_all = all(res["legs"][g]["valid"] for g in LEGS)
    bw = any(res["legs"][g]["valid"] and res["legs"][g]["BUILD_WORTH_row"] for g in LEGS)
    close = all(res["legs"][g]["CLOSE_row"] for g in LEGS)
    reading = "BUILD-WORTH" if bw else "CLOSE" if close else "BETWEEN"
    res["decision"] = reading if (valid_all or bw) else f"NO DECISION (a validity row failed for a leg); numbers would read {reading}"
    json.dump(res, open(f"{CS}/refit_result.json", "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
