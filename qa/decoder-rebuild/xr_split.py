#!/usr/bin/env python3
"""XC-ROUND: where does the rise in `ours` (+55 / +161 / +238) come from?  Data on disk only, no new run (the Architect's request, 2026-11-27).

  (a) batch 4: the decodes of the round itself, matched / unmatched
  (b) the CHAINED rows: decodes in batches 1-3 of the new run that the PAYLOAD-FIT run did not have (the prior-store / hash-table feed from batch 4), matched / unmatched
  (c) the rest: the net of everything else (decodes of the PAYLOAD-FIT run that the new run lost, and any other difference)
For (a) and (b): how many have the same message in WSJT-X's own decodes of the SAME cycle (same text, any frequency / within +-10 Hz) - a stronger statement than 'matched' for the unmatched ones.
Message text is read INSIDE `split_slice` and never leaves it (HK-037): only counts return.
"""
import json
import os
from collections import Counter

SC = r"D:\Projects\claude\_qa-scratch"
ART = r"D:\Projects\claude\OpenWSFZ\artefacts"
SL = {"S40": (170, "20261114_2312_endurance_run-gathered"), "H40": (240, "20261028_2233_endurance_run-gathered"), "H20": (240, "20260808_live_run_0016-8080")}
FREQ_TOL_HZ = 10.0
AP_TAIL = ("?",)


def norm(text):
    t = text.split()
    while t and (t[-1] in AP_TAIL or (len(t[-1]) == 2 and t[-1][0] == "a" and t[-1][1].isdigit())):
        t.pop()
    return " ".join(t)


def split_slice(name):
    n, folder = SL[name]
    od, nd = SC + r"\lc-base\runs\pf_%s_L_n%d" % (name, n), SC + r"\lc-base\runs\xr_%s_L_n%d" % (name, n)
    sel = json.load(open(nd + r"\sel.json"))
    stamps = set(sel["runs"][sel["run"]]["FULL"])

    def load(d):
        rows = {}
        with open(d + r"\nc.tsv", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                c = line.rstrip("\n").split("\t")
                if len(c) < 11:
                    continue
                k = (c[0], norm(c[10]))
                if k not in rows:
                    rows[k] = (int(c[1]), float(c[3]), c[2] == "1")              # batch, freq, matched
        return rows
    old, new = load(od), load(nd)
    wsj = {}                                                                      # stamp -> [(freq, text)]
    with open(os.path.join(ART, folder, "wsjt-x", "ALL.TXT"), encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line[:13] not in stamps:
                continue
            f = [x for x in line.split(" ") if x]
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            try:
                wsj.setdefault(f[0], []).append((float(f[6]), norm(" ".join(f[7:]))))
            except ValueError:
                continue

    def wsjtx_same(k, fr):
        same_text = [ff for (ff, t) in wsj.get(k[0], []) if t == k[1]]
        return (bool(same_text), any(abs(ff - fr) <= FREQ_TOL_HZ for ff in same_text))

    groups = {"a_batch4": [], "b_chained_in_b123": [], "c_lost": []}
    for k, (b, fr, m) in new.items():
        if k in old and old[k][0] == b:
            continue
        if b == 4:
            groups["a_batch4"].append((k, fr, m))
        elif b in (1, 2, 3) and k not in old:
            groups["b_chained_in_b123"].append((k, fr, m))
        elif k in old:
            groups["c_lost"].append((k, fr, m))                                   # present in both runs but in another batch
    lost = [(k, v[1], v[2]) for k, v in old.items() if k not in new]
    out = {}
    for g, rows in list(groups.items()) + [("c_dropped_from_the_baseline_run", lost)]:
        c = Counter()
        for k, fr, m in rows:
            c["decodes"] += 1
            c["matched" if m else "unmatched"] += 1
            st, near = wsjtx_same(k, fr)
            if not m:
                c["unmatched_with_same_text_in_wsjtx_same_cycle_any_freq"] += st
                c["unmatched_with_same_text_in_wsjtx_same_cycle_within_10hz"] += near
        out[g] = dict(c)
    out["rise_in_ours"] = len(new) - len(old)
    out["batches_of_the_chained_rows"] = dict(Counter(new[k][0] for k, _, _ in groups["b_chained_in_b123"]))
    return out


if __name__ == "__main__":
    res = {s: split_slice(s) for s in SL}
    json.dump(res, open(os.path.join(SC, "lc-base", "xr_split.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
