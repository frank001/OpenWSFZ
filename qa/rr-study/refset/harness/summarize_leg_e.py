#!/usr/bin/env python
"""Per-replicate summary of leg E (QA, 2026-10-12; REFERENCE-SET amendment 10, section 2o). Aggregates only: counts and times, no message text.

  python summarize_leg_e.py --scratch <dir with <block>.rep<N>.json> --rep N --legB <first-run B dir> --out <summary.json>

Measures (scored cycles only; warm-up excluded): T_wsjtx_span, T_wsjtx_busy_sum, T_wsjtx_last (median, P90, max), late = T_wsjtx_last > 17.0 s,
dropped = leg E decodes - live WSJT-X ALL.TXT count, DT shift (leg E - live), and the pairing with leg B's whole-decode T_ows by stamp
(share with T_ows > 15 s against the share late; by live-count density bin <=10, 11-20, 21-30, >30). Descriptive, no bars.
Label: T_ows is compute time from a file replay; T_wsjtx is real-time decoding of played audio. They are not the same quantity.
"""
import argparse
import glob
import json
import os
import random

LATE_S = 17.0
CYCLE_S = 15.0
BINS = [("<=10", 0, 10), ("11-20", 11, 20), ("21-30", 21, 30), (">30", 31, 10 ** 9)]
BOOT_N = 2000
BOOT_SEED = 20261012


def q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p * (len(v) - 1) + 0.5))] if v else None


def dist(v):
    v = [x for x in v if x is not None]
    return {"n": len(v), "median": q(v, .5), "p90": q(v, .9), "max": max(v) if v else None}


def share_ci(flags_by_block):
    """Share of cycles with the flag, 95% CI clustered by block (bootstrap over blocks)."""
    blocks = [b for b in flags_by_block if b]
    tot = sum(len(b) for b in blocks)
    if not tot:
        return None
    est = sum(sum(b) for b in blocks) / tot
    rng = random.Random(BOOT_SEED)
    s = []
    for _ in range(BOOT_N):
        pick = [blocks[rng.randrange(len(blocks))] for _ in blocks]
        t = sum(len(b) for b in pick)
        s.append(sum(sum(b) for b in pick) / t if t else 0.0)
    s.sort()
    return {"share": round(est, 4), "ci95": [round(s[int(.025 * BOOT_N)], 4), round(s[int(.975 * BOOT_N)], 4)], "n": tot, "blocks": len(blocks)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--rep", type=int, required=True)
    ap.add_argument("--legB", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.scratch, f"*.rep{a.rep}.json")))
    allc, per_block_late, per_block_slow, rows = [], [], [], []
    for f in files:
        d = json.load(open(f))
        bj = os.path.join(a.legB, d["block"] + ".json")
        ows = {}
        if os.path.exists(bj):
            ows = {c["stamp"]: c["ms"] / 1000.0 for c in json.load(open(bj))["cycles"] if c.get("scored")}
        sc = [c for c in d["cycles"] if not c["warmup"]]
        late, slow = [], []
        for c in sc:
            c["T_ows"] = ows.get(c["stamp"])
            c["late"] = int(c["T_wsjtx_last"] is not None and c["T_wsjtx_last"] > LATE_S)
            late.append(c["late"])
            if c["T_ows"] is not None:
                slow.append(int(c["T_ows"] > CYCLE_S))
            rows.append(c)
        per_block_late.append(late)
        per_block_slow.append(slow)
        allc += sc
    out = {"rep": a.rep, "blocks": len(files), "scored_cycles": len(allc),
           "T_wsjtx_span": dist([c["T_wsjtx_span"] for c in allc]),
           "T_wsjtx_busy_sum": dist([c["T_wsjtx_busy_sum"] for c in allc]),
           "T_wsjtx_last": dist([c["T_wsjtx_last"] for c in allc]),
           "late_gt_17s": share_ci(per_block_late),
           "T_ows_gt_15s": share_ci(per_block_slow),
           "T_ows": dist([c["T_ows"] for c in allc]),
           "decodes_leg_E": sum(c["n_decodes"] for c in allc), "decodes_live_wsjtx": sum(c["n_live"] for c in allc),
           "dropped": dist([c["dropped"] for c in allc]),
           "dt_shift_vs_live": dist([c["dt_median"] - c["dt_live_median"] for c in allc if c["dt_median"] is not None and c["dt_live_median"] is not None]),
           "by_density_bin": {},
           "label": "T_ows is compute time from a file replay; T_wsjtx is real-time decoding of played audio. Not the same quantity. Descriptive, no bars. Linux, one FX-8350, WSJT-X 2.7.0, lead 0.0 s."}
    for name, lo, hi in BINS:
        cs = [c for c in allc if lo <= c["n_live"] <= hi]
        out["by_density_bin"][name] = {"cycles": len(cs), "T_wsjtx_span": dist([c["T_wsjtx_span"] for c in cs]),
                                       "T_wsjtx_last": dist([c["T_wsjtx_last"] for c in cs]),
                                       "late_share": round(sum(c["late"] for c in cs) / len(cs), 4) if cs else None,
                                       "T_ows": dist([c["T_ows"] for c in cs]),
                                       "T_ows_gt_15s_share": round(sum(1 for c in cs if c["T_ows"] is not None and c["T_ows"] > CYCLE_S) / max(1, sum(1 for c in cs if c["T_ows"] is not None)), 4) if cs else None,
                                       "dropped_median": q([c["dropped"] for c in cs], .5)}
    with open(a.out, "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({k: out[k] for k in ("rep", "blocks", "scored_cycles", "T_wsjtx_span", "T_wsjtx_last", "late_gt_17s", "T_ows_gt_15s")}))


if __name__ == "__main__":
    main()
