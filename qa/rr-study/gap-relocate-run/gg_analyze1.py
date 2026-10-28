#!/usr/bin/env python3
"""COH-GATE-G TRAIN, part 1: V1 (replay), V2 (record complete), V4, the CEILING (admit every GATED_OUT row), and a G-row census.
Counts only. The U' part (V5, DU') is gg_analyze2.py (needs the Original arm's frozen classes)."""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gr_common as C
import gg_lib as L

NONE = lambda r: False
ALL = lambda r: True


def main():
    stamps = C.selection_stamps()
    ref = C.load_ref(set(stamps))
    n_ref = sum(len(v) for v in ref.values())
    arm = L.load_arm("both")
    res = {"n_ref": n_ref}
    v1_b4 = v2_bad = 0
    matched_prod = matched_none = matched_all = 0
    census = collections.Counter()
    for s in stamps:
        prod4 = [(x[2], x[6]) for x in arm["nc"].get(s, []) if x[0] == 4]
        v1_b4 += len(prod4)
        base, _ = L.cycle_outputs(arm, s, NONE)
        # product's own outputs
        ows_prod = [(x[0], x[2], x[6]) for x in arm["nc"].get(s, [])]
        mp, _ = L.match(ref[s], ows_prod)
        matched_prod += len(mp)
        fb_none = L.publish(arm, s, NONE)
        if [(f, t) for f, t, _ in fb_none] != prod4:
            v2_bad += 1
        mn, _ = L.match(ref[s], base + [(4, f, t) for f, t, _ in fb_none])
        matched_none += len(mn)
        fb_all = L.publish(arm, s, ALL)
        ma, _ = L.match(ref[s], base + [(4, f, t) for f, t, _ in fb_all])
        matched_all += len(ma)
        for r in arm["rows"].get(s, []):
            census[(r["state"], "run%d" % r["run"])] += 1
    res["V1"] = {"batch4_published": v1_b4, "corroborated": matched_prod, "pct": round(100.0 * matched_prod / n_ref, 2),
                 "expected_batch4": C.B2_BOTH_BATCH4, "expected_pct": C.B2_BOTH_PCT,
                 "PASS": v1_b4 == C.B2_BOTH_BATCH4 and round(100.0 * matched_prod / n_ref, 2) == C.B2_BOTH_PCT}
    res["V2"] = {"cycles_not_reproduced": v2_bad, "corroborated_offline_none": matched_none, "corroborated_product": matched_prod,
                 "PASS": v2_bad == 0 and matched_none == matched_prod}
    res["ceiling"] = {"corroborated_admit_all": matched_all, "NET_all_pp": 100.0 * (matched_all - matched_none) / n_ref,
                      "STOP_CEIL_fires": 100.0 * (matched_all - matched_none) / n_ref < 0.5}
    res["row_census"] = {f"{k[0]}|{k[1]}": v for k, v in census.items()}
    json.dump(res, open(L.S + "\\train1.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
