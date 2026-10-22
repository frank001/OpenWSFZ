#!/usr/bin/env python
"""Per-block comparison for the 70 min WSJT-X keep-up run (QA, 2026-10-13; analysis only, aggregates only; HK-037: text stays inside the readers).

  python leg_e_subset_compare.py --corpus <corpus> --legB <first-run B dir> --rep <leg-e-subset rep dir> --out <json> [--rep-num 1]

Three row sets per block, scored cycles only, non-hashed rows, sm_01 key (text with <...> collapsed, paired in order within a cycle):
  LIVE    the station's own WSJT-X ALL.TXT for the recorded cycles (what the live run decoded)
  E       the SAME WSJT-X 2.7.0 on sol, playing WSJT-X's own recording in real time (leg E; decodes from its UDP messages)
  B       OpenWSFZ (first run, leg B: the same WSJT-X-side recording, budget unlimited)
Reported per block and in total: row counts; share of LIVE rows that E reproduces (and E-only rows); share of LIVE rows that B reproduces (and
B-only); share of E rows that B reproduces (and B-only). The question it answers: is live WSJT-X thin on the burst night because of the AUDIO
(then E would be thin as well) or because of the live run's conditions (then E decodes about as many rows as OpenWSFZ does)?
"""
import argparse
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import refset_score as rs  # noqa: E402
import score_vs_wsjtx as sv  # noqa: E402


def read_leg_e(path: str, scored: set) -> dict:
    out = defaultdict(list)
    with open(path, "r", encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            p = line.rstrip("\n").split("\t", 5)
            if len(p) == 6 and p[0] in scored:
                out[p[0]].append((int(float(p[2])), p[5]))
    return out


def nonhashed(rows):
    return [(s, t) for s, t in rows if not rs.is_hashed(t)]


def compare(a_rows: dict, b_rows: dict, scored: list) -> dict:
    """share of A's rows that B reproduces, and B's rows left unmatched (counts)."""
    n_a = n_b = m = 0
    for s in scored:
        A, B = nonhashed(a_rows.get(s, [])), nonhashed(b_rows.get(s, []))
        lm, om = sv.match_cycle(A, B)
        n_a += len(A)
        n_b += len(B)
        m += sum(lm)
    return {"a_rows": n_a, "b_rows": n_b, "matched": m, "a_reproduced_share": round(m / n_a, 4) if n_a else None, "b_only_rows": n_b - m}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--legB", required=True)
    ap.add_argument("--rep", required=True)
    ap.add_argument("--rep-num", type=int, default=1)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    man = rs.load_json(os.path.join(a.corpus, "manifest.json"))
    by_id = {b["id"]: b for b in man["blocks"]}
    ids = sorted(f.split(".")[0] for f in os.listdir(a.rep) if f.endswith(".rep%d.json" % a.rep_num))
    res = {"blocks": {}, "label": "70 min WSJT-X keep-up run, one replicate; analysis of the working files, no new decoding",
           "sets": "LIVE = station WSJT-X ALL.TXT; E = WSJT-X 2.7.0 real-time replay on sol; B = OpenWSFZ leg B (first run)"}
    tot = {"LE": [0, 0, 0], "LB": [0, 0, 0], "EB": [0, 0, 0]}
    for bid in ids:
        blk = by_id[bid]
        scored = rs.block_scored_stamps(blk)
        live = sv.read_live(os.path.join(a.corpus, "wsjt-x", blk["run"], "ALL.TXT"), scored)
        e = read_leg_e(os.path.join(a.rep, "%s.rep%d.decodes.tsv" % (bid, a.rep_num)), set(scored))
        b = sv.read_own(os.path.join(a.legB, bid + ".decodes.tsv"))
        row = {"run": blk["run"], "band": blk["band"], "sun": blk["sun"], "scored_cycles": len(scored),
               "live_vs_E": compare(live, e, scored), "live_vs_B": compare(live, b, scored), "E_vs_B": compare(e, b, scored),
               "rows_nonhashed": {"live": sum(len(nonhashed(live.get(s, []))) for s in scored), "E": sum(len(nonhashed(e.get(s, []))) for s in scored),
                                  "B": sum(len(nonhashed(b.get(s, []))) for s in scored)}}
        row["rows_per_cycle"] = {k: round(v / len(scored), 2) for k, v in row["rows_nonhashed"].items()}
        res["blocks"][bid] = row
        for k, key in (("LE", "live_vs_E"), ("LB", "live_vs_B"), ("EB", "E_vs_B")):
            tot[k][0] += row[key]["a_rows"]; tot[k][1] += row[key]["matched"]; tot[k][2] += row[key]["b_only_rows"]
    res["total"] = {k: {"a_rows": v[0], "matched": v[1], "a_reproduced_share": round(v[1] / v[0], 4) if v[0] else None, "b_only_rows": v[2]} for k, v in tot.items()}
    res["total"]["note"] = "LE: live rows reproduced by E; LB: live rows reproduced by B; EB: E rows reproduced by B. Descriptive; 7 blocks, one replicate."
    with open(a.out, "w") as fh:
        json.dump(res, fh, indent=1)
    for bid, r in res["blocks"].items():
        print(bid, r["band"], r["sun"], "rows/cycle live %.1f E %.1f B %.1f" % (r["rows_per_cycle"]["live"], r["rows_per_cycle"]["E"], r["rows_per_cycle"]["B"]),
              "| live reproduced by E %s B %s | E reproduced by B %s" % (r["live_vs_E"]["a_reproduced_share"], r["live_vs_B"]["a_reproduced_share"], r["E_vs_B"]["a_reproduced_share"]))
    print("TOTAL", res["total"])


if __name__ == "__main__":
    main()
