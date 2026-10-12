#!/usr/bin/env python
"""Burst check on the leg B / leg A vs live WSJT-X comparison (QA, 2026-10-12, Architect request; analysis only, aggregates only).

  python burst_check.py --corpus <corpus> --passdir <first-run dir> --out <json>

(a) crowding re-binned by the per-cycle UNION of distinct sm_01 keys (live WSJT-X + leg B OWS), same 4 bins;
(b) burst cycles = leg B cycles with >= 3 OWS-only NON-HASHED rows: counts per block, night (source run) and UTC hour, runs of consecutive cycles,
    and each burst cycle's live WSJT-X row count beside the leg B row count (counts only);
(c) sensitivity: headline matched share / OWS-only with the burst cycles excluded (POST HOC, labelled), beside the full figure.
Message text is read inside score_vs_wsjtx's readers and never leaves; the output is counts and shares.
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import refset_score as rs  # noqa: E402
import score_vs_wsjtx as sv  # noqa: E402

BURST_MIN = 3


def load(corpus, passdir, leg, blocks):
    cyc = []
    for blk in blocks:
        scored = rs.block_scored_stamps(blk)
        live = sv.read_live(os.path.join(corpus, "wsjt-x", blk["run"], "ALL.TXT"), scored)
        own = sv.read_own(os.path.join(passdir, leg, blk["id"] + ".decodes.tsv"))
        for idx, s in enumerate(scored):
            L, O = live.get(s, []), own.get(s, [])
            lm, om = sv.match_cycle(L, O)
            keys = {rs.key_of(t) for _, t in L} | {rs.key_of(t) for _, t in O}
            cyc.append({"block": blk["id"], "run": blk["run"], "band": blk["band"], "idx": idx, "stamp": s, "n_live": len(L), "n_own": len(O),
                        "union": len(keys),
                        "live": [(snr, rs.is_hashed(t), m) for (snr, t), m in zip(L, lm)],
                        "own": [(snr, rs.is_hashed(t), m) for (snr, t), m in zip(O, om)]})
    return cyc


def owsonly_nh(c):
    return sum(1 for (_, h, m) in c["own"] if (not m) and (not h))


def headline(sel):
    num = [sum(1 for (_, h, m) in c["live"] if m and not h) for c in sel]
    den = [sum(1 for (_, h, _m) in c["live"] if not h) for c in sel]
    ext = sum(owsonly_nh(c) for c in sel)
    return {"matched_nonhashed": sv.ci(num, den), "owsonly_nonhashed_rows": int(ext),
            "owsonly_share_of_wsjtx_nonhashed_rows": round(ext / max(1, sum(den)), 4), "cycles": len(sel)}


def stats(v):
    v = sorted(v)
    return {"n": len(v), "median": v[len(v) // 2] if v else None, "p90": v[int(0.9 * (len(v) - 1))] if v else None, "max": v[-1] if v else None}


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
    B = load(a.corpus, a.passdir, "B", blocks)
    A = load(a.corpus, a.passdir, "A", blocks)
    res = {"label": "first run, OpenWSFZ legs only (A, D, B); leg E pending. Analysis of working files, no new decoding. Burst exclusion is POST HOC.",
           "burst_definition": f"leg B cycles with >= {BURST_MIN} OWS-only non-hashed rows"}

    # (a) crowding by the union of distinct keys
    res["a_union_crowding_leg_B"] = {}
    for name, lo, hi in sv.CROWD_BINS:
        sel = [c for c in B if lo <= c["union"] <= hi]
        if not sel:
            continue
        v = [owsonly_nh(c) for c in sel]
        h = headline(sel)
        h["owsonly_per_cycle_mean"] = round(sum(v) / len(v), 3)
        h["owsonly_per_cycle"] = stats(v)
        res["a_union_crowding_leg_B"][name] = h
    res["a_union_vs_live_count_cross_tab_cycles"] = {}
    for ln, llo, lhi in sv.CROWD_BINS:
        row = {}
        for un, ulo, uhi in sv.CROWD_BINS:
            row[un] = sum(1 for c in B if llo <= c["n_live"] <= lhi and ulo <= c["union"] <= uhi)
        res["a_union_vs_live_count_cross_tab_cycles"]["live " + ln] = row

    # (b) burst cycles
    burst = [c for c in B if owsonly_nh(c) >= BURST_MIN]
    bset = {(c["block"], c["stamp"]) for c in burst}
    res["b_bursts"] = {"cycles": len(burst), "of": len(B), "total_owsonly_nonhashed_rows": sum(owsonly_nh(c) for c in B),
                       "owsonly_rows_in_bursts": sum(owsonly_nh(c) for c in burst)}
    per_block = Counter(c["block"] for c in burst)
    per_run = Counter(c["run"] for c in burst)
    per_hour = Counter(c["stamp"][7:9] for c in burst)           # UTC hour HH of YYMMDD_HHMMSS
    blk_meta = {b["id"]: (b["band"], b["sun"], b["run"]) for b in blocks}
    res["b_bursts"]["per_block"] = {k: {"bursts": v, "band": blk_meta[k][0], "sun": blk_meta[k][1], "block_scored_cycles": 32} for k, v in sorted(per_block.items(), key=lambda kv: -kv[1])}
    res["b_bursts"]["blocks_with_any_burst"] = len(per_block)
    res["b_bursts"]["blocks_total"] = len(blocks)
    res["b_bursts"]["per_night_source_run"] = dict(sorted(per_run.items(), key=lambda kv: -kv[1]))
    res["b_bursts"]["per_utc_hour"] = dict(sorted(per_hour.items()))
    # runs of consecutive burst cycles inside a block
    runs = []
    for bid in per_block:
        idxs = sorted(c["idx"] for c in burst if c["block"] == bid)
        start = prev = idxs[0]
        for i in idxs[1:] + [None]:
            if i is not None and i == prev + 1:
                prev = i
                continue
            runs.append(prev - start + 1)
            if i is not None:
                start = prev = i
    res["b_bursts"]["runs_of_consecutive_burst_cycles"] = {"runs": len(runs), "length_distribution": dict(sorted(Counter(runs).items())), "longest": max(runs) if runs else 0}
    # the burst cycles' live count next to leg B's row count (counts only)
    res["b_bursts"]["burst_cycles_live_vs_ows_rows"] = {
        "live_wsjtx_rows": stats([c["n_live"] for c in burst]), "leg_B_rows": stats([c["n_own"] for c in burst]),
        "share_with_live_rows_below_half_of_ows_rows": round(sum(1 for c in burst if c["n_live"] < 0.5 * c["n_own"]) / max(1, len(burst)), 3)}
    rest = [c for c in B if (c["block"], c["stamp"]) not in bset]
    res["b_bursts"]["non_burst_cycles_live_vs_ows_rows"] = {
        "live_wsjtx_rows": stats([c["n_live"] for c in rest]), "leg_B_rows": stats([c["n_own"] for c in rest]),
        "share_with_live_rows_below_half_of_ows_rows": round(sum(1 for c in rest if c["n_live"] < 0.5 * c["n_own"]) / max(1, len(rest)), 3)}
    res["b_bursts"]["cycles_list_counts_only"] = [
        {"block": c["block"], "band": c["band"], "cycle_in_block": c["idx"], "utc_hour": c["stamp"][7:9], "live_wsjtx_rows": c["n_live"], "leg_B_rows": c["n_own"],
         "owsonly_nonhashed": owsonly_nh(c)} for c in sorted(burst, key=lambda c: (c["block"], c["idx"]))]
    # do leg A's extras burst on the same cycles?
    a_burst = {(c["block"], c["stamp"]) for c in A if owsonly_nh(c) >= BURST_MIN}
    res["b_bursts"]["same_cycles_burst_in_leg_A"] = {"leg_A_burst_cycles": len(a_burst), "both": len(a_burst & bset)}

    # (c) sensitivity
    res["c_sensitivity_post_hoc"] = {
        "leg_B_full": headline(B), "leg_B_without_burst_cycles": headline(rest),
        "leg_A_full": headline(A), "leg_A_without_burst_cycles": headline([c for c in A if (c["block"], c["stamp"]) not in bset]),
        "note": "the FULL figure is the headline; the exclusion is post hoc and only shows how much of the OWS-only count the burst cycles carry"}
    with open(a.out, "w") as fh:
        json.dump(res, fh, indent=1)
    print("bursts", res["b_bursts"]["cycles"], "blocks with any", res["b_bursts"]["blocks_with_any_burst"], "of", len(blocks))


if __name__ == "__main__":
    main()
