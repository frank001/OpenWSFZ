#!/usr/bin/env python3
"""COH-GATE-G TRAIN descriptive census of the ceiling (admit every GATED_OUT row): D2 splits, H-SHARE inputs (hashed share, type-4 confirmed share),
D3 overlap with GAP-RELOCATE's class-G rows, per-station clustering. Counts only; text in memory only."""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gr_common as C
import gg_lib as L

NONE = lambda r: False
ALL = lambda r: True


def station_key(text):
    t = text.split()
    if not t:
        return ""
    if t[0] == "CQ":
        return t[2] if len(t) > 3 and t[1].isalpha() and len(t[1]) <= 4 else (t[1] if len(t) > 1 else "")
    return t[1] if len(t) > 1 else t[0]


def main():
    stamps = C.selection_stamps()
    ref = C.load_ref(set(stamps))
    n_ref = sum(len(v) for v in ref.values())
    arm = L.load_arm("both")
    new_total = collections.Counter()
    by = {k: collections.Counter() for k in ("band", "i3", "run", "hashed", "prov", "edge")}
    conf_by = {k: collections.Counter() for k in by}
    stations = collections.Counter()
    newly_matched = set()            # (stamp, ref idx) newly corroborated by the ceiling
    for s in stamps:
        base13 = [(x[0], x[2], x[6]) for x in arm["nc"].get(s, []) if x[0] in (1, 2, 3)]
        none = L.publish(arm, s, NONE)
        mn, _ = L.match(ref[s], base13 + [(4, f, t) for f, t, _ in none])
        allp = L.publish(arm, s, ALL)
        ma, mo = L.match(ref[s], base13 + [(4, f, t) for f, t, _ in allp])
        for j in ma - mn:
            newly_matched.add((s, j))
        base_texts = {t for _, t, _ in [(f, t, r) for f, t, r in none]}
        nb = len(base13)
        for k, (f, t, r) in enumerate(allp):
            if t in base_texts or r["state"] != "G":
                continue
            new_total["outputs"] += 1
            conf = (nb + k) in mo
            keys = {"band": "ABCD"["ABCD".index(next(b for b in "ABCD" if b == ("A" if r["snr"] >= 0 else "B" if r["snr"] >= -10 else "C" if r["snr"] >= -15 else "D")))],
                    "i3": str(r["i3"]), "run": "residual" if (r["run"] == 0 and arm["runs"].get(s, 0) == 2) else "original",
                    "hashed": "hashed" if "<" in t else "plain", "prov": "V3" if r["prov"] == 0 else "walk", "edge": "edge" if r["edge"] else "no_edge"}
            for kk, vv in keys.items():
                by[kk][vv] += 1
                if conf:
                    conf_by[kk][vv] += 1
            if conf:
                new_total["confirmed"] += 1
                stations[station_key(t)] += 1
    # D3: overlap with GAP-RELOCATE class-G rows (M rows)
    g_rows = set()
    try:
        pop = json.load(open(r"D:\Projects\claude\_qa-scratch\gap-relocate\population.json"))
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import gr_item2 as I2
        recs = {}
        for fn in ("forced_pilot.jsonl", "forced_main.jsonl"):
            for line in open(r"D:\Projects\claude\_qa-scratch\gap-relocate\\" + fn, encoding="utf-8"):
                r = json.loads(line)
                recs[(r["stamp"], r["idx"])] = r
        for r in pop["rows"]:
            if not r["matched"] and I2.classify(r, recs.get((r["stamp"], r["idx"]))) == "G":
                g_rows.add((r["stamp"], r["idx"]))
    except FileNotFoundError:
        pass
    tot = sum(stations.values())
    res = {"n_ref": n_ref, "added_outputs_new_text": new_total["outputs"], "added_confirmed": new_total["confirmed"],
           "newly_corroborated_ref_rows": len(newly_matched), "newly_corroborated_pp": 100.0 * len(newly_matched) / n_ref,
           "added_by": {k: dict(v) for k, v in by.items()}, "confirmed_by": {k: dict(v) for k, v in conf_by.items()},
           "type4_confirmed_share": (conf_by["i3"].get("4", 0) / by["i3"]["4"]) if by["i3"].get("4") else None,
           "hashed_share_of_added": by["hashed"].get("hashed", 0) / max(1, new_total["outputs"]),
           "D3_gap_relocate_G_rows": len(g_rows), "D3_of_which_newly_corroborated": len(g_rows & newly_matched),
           "stations_confirmed": {"distinct": len(stations), "top_share": (max(stations.values()) / tot) if tot else None,
                                  "top5_share": (sum(v for _, v in stations.most_common(5)) / tot) if tot else None},
           "batch4_confirmed_share_product": 1227 / 1350}
    json.dump(res, open(L.S + "\\train_census.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
