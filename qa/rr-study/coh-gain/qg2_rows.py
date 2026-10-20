#!/usr/bin/env python3
"""Q-GATE-2 analysis: validity rows V-K, V-P, V-T2 and the rows G2-OK / G2-FAIL / G2-OPEN (spec section 7 + Amendment 1), plus the descriptive tables.

  python qg2_rows.py main  --rows <rows_main.json>  --run <run dir> --out <analysis.json>
  python qg2_rows.py pilot --rows <rows_pilot.json> --run <run dir> --out <analysis.json>   # V-T2 pilot (cycles in order until n >= 200) + projected CI half-widths

Definitions (all pre-registered in the spec; nothing is tuned here):
  D        = number of encodable WSJT-X rows in the sampled cycles (live-hit rows included)
  P        = rows with live_hit = 0 AND G not RIGHT at any of the 9 cells (g_right = 0)
  output   = a C3 BP-only CRC-valid output on a P row;   kept = output with F1b <= T1 (17.552446 dB)
  RIGHT    = class right_i | right_ii;   unexplained = class ows | none  (near and far are NOT unexplained)
  KG = 100 * kept RIGHT / D (pp of WSJT-X decodes);   UPC = kept unexplained / sampled cycles
  CI: blocks of 8 consecutive sampled cycles, numerator and denominator resampled together, B = 10,000, seed 20261020, 95 % percentile.
  G2-OK  = CI_lo(KG) >= BAR_G AND CI_hi(UPC) <= U_max;  G2-FAIL = CI_hi(KG) < BAR_G OR CI_lo(UPC) > U_max;  else G2-OPEN
Only numbers are read and written (the rows file holds no text).
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "endurance"))
import qg2  # noqa: E402
import anova_common as ac  # noqa: E402

BANDS = (("<=-16", -99, -16), ("-15..-6", -15, -6), ("-5..+4", -5, 4), (">=+5", 5, 99))
RIGHT = ("right_i", "right_ii")
POOL_JSON = None


def phi_ok(upper):
    return upper <= 0.02


def wilson(k, n, z=1.96):
    if not n:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def load(rows_json, run_dir):
    spec = json.load(open(rows_json))
    sample = spec["sample"]
    cols = sample["columns"]
    meta = {(r[0], r[2]): dict(zip(cols, r)) for r in sample["rows"]}
    recs = list(csv.DictReader(open(os.path.join(run_dir, "rows_part.csv"), newline="", encoding="utf-8")))
    for r in recs:
        r["_ci"], r["_w"] = int(float(r["cycle_index"])), int(float(r["widx"]))
        r["_m"] = meta[(r["_ci"], r["_w"])]
    ctl = [json.loads(l) for l in open(os.path.join(run_dir, "control.jsonl"))]
    return spec, sample, recs, ctl


def blocks_of(cycles_sorted):
    return {c: i // qg2.BLOCK_CYCLES for i, c in enumerate(cycles_sorted)}


def boot(block_stats, field_num, field_den, seed=qg2.SEED, B=qg2.B_RESAMPLES):
    """block_stats: list of dicts; ratio of sums resampled. -> (point, lo, hi)."""
    nb = len(block_stats)
    num = [b[field_num] for b in block_stats]
    den = [b[field_den] for b in block_stats]
    point = sum(num) / sum(den) if sum(den) else float("nan")
    rng = random.Random(seed)
    vals = []
    for _ in range(B):
        sn = sd = 0
        for _k in range(nb):
            j = rng.randrange(nb)
            sn += num[j]
            sd += den[j]
        vals.append(sn / sd if sd else float("nan"))
    vals.sort()
    return point, vals[int(0.025 * (B - 1))], vals[int(0.975 * (B - 1))]


def analyse_main(rows_json, run_dir):
    spec, sample, recs, ctl = load(rows_json, run_dir)
    T1 = qg2.T1
    cycles = sorted({r["_ci"] for r in recs})
    N = len(cycles)
    bmap = blocks_of(cycles)
    nblocks = max(bmap.values()) + 1
    enc_rows = [r for r in sample["rows"] if r[8]]
    D_by_c = collections.Counter(r[0] for r in enc_rows)
    faults = sum(int(r["fault"]) for r in recs)

    def stats(sel_pop, gate):
        """sel_pop(r) -> bool for population membership; gate(r) -> kept?  Returns per-block stats and totals."""
        bs = [dict(kr=0, ku=0, D=0, cyc=0, outs=0, kept=0) for _ in range(nblocks)]
        tot = collections.Counter()
        by_band = collections.defaultdict(collections.Counter)
        kept_right_cycles = collections.Counter()
        for c in cycles:
            bs[bmap[c]]["D"] += D_by_c[c]
            bs[bmap[c]]["cyc"] += 1
        for r in recs:
            if int(r["fault"]) or not sel_pop(r) or int(r["c3_out"]) != 1:
                continue
            b = bmap[r["_ci"]]
            snr = int(float(r["snr"]))
            band = next(n for n, lo, hi in BANDS if lo <= snr <= hi)
            bs[b]["outs"] += 1
            tot["outputs"] += 1
            cls = r["c3_class"]
            if gate(r):
                bs[b]["kept"] += 1
                tot["kept"] += 1
                if cls in RIGHT:
                    bs[b]["kr"] += 1
                    tot["kept_right"] += 1
                    tot["kept_right_ii"] += int(cls == "right_ii")
                    kept_right_cycles[r["_ci"]] += 1
                    by_band[band]["kr"] += 1
                elif cls in ("ows", "none"):
                    bs[b]["ku"] += 1
                    tot["kept_unexplained"] += 1
                    by_band[band]["ku"] += 1
                elif cls == "near":
                    tot["kept_near"] += 1
                elif cls == "far":
                    tot["kept_far"] += 1
        return bs, tot, by_band, kept_right_cycles

    live_miss_g_fail = lambda r: int(r["live_hit"]) == 0 and int(r["g_right"]) == 0
    g_fail_only = lambda r: int(r["g_right"]) == 0
    kept = lambda r: r["f1b"] != "" and float(r["f1b"]) <= T1
    anyr = lambda r: True

    out = {"cycles": N, "blocks_of_8": nblocks, "fault_rows": faults, "D_encodable_rows": sum(D_by_c[c] for c in cycles)}
    # population sizes
    P = [r for r in recs if not int(r["fault"]) and live_miss_g_fail(r)]
    out["P_rows"] = len(P)
    out["rows_run"] = len(recs)
    out["g_right_rows"] = sum(int(r["g_right"]) for r in recs)
    out["g_right_rule_ii_rows"] = sum(1 for r in recs if r["g_rule"] == "ii")
    out["live_hit_rows_among_run"] = sum(int(r["live_hit"]) for r in recs)

    def result(name, pop, gate):
        bs, tot, by_band, krc = stats(pop, gate)
        D_total = sum(b["D"] for b in bs)
        kg = boot([dict(n=b["kr"], d=b["D"]) for b in bs], "n", "d")
        upc = boot([dict(n=b["ku"], d=b["cyc"]) for b in bs], "n", "d")
        res = {"outputs": tot["outputs"], "kept": tot["kept"], "kept_right": tot["kept_right"], "kept_right_rule_ii": tot["kept_right_ii"],
               "kept_unexplained": tot["kept_unexplained"], "kept_near": tot["kept_near"], "kept_far": tot["kept_far"],
               "KG_pp": [round(100 * x, 4) for x in kg], "UPC": [round(x, 5) for x in upc],
               "distinct_cycles_with_kept_right": len(krc)}
        top5 = sorted(range(nblocks), key=lambda i: -bs[i]["kr"])[:5]
        res["share_of_KG_in_top5_blocks"] = round(sum(bs[i]["kr"] for i in top5) / tot["kept_right"], 4) if tot["kept_right"] else None
        res["by_snr_band"] = {n: {"kept_right": by_band[n]["kr"], "kept_unexplained": by_band[n]["ku"]} for n, _, _ in BANDS}
        return res, kg, upc

    gated, kg, upc = result("gated", live_miss_g_fail, kept)
    ung, _, _ = result("ungated", live_miss_g_fail, anyr)
    bridge, _, _ = result("bridge", g_fail_only, kept)
    bridge_ung, _, _ = result("bridge_ungated", g_fail_only, anyr)
    out["gated_GA_on_P"] = gated
    out["ungated_fallback_on_P"] = ung
    out["bridge_Q-GATE_population_gated_DESCRIPTIVE_never_difference_against_Q-GATE_TEST"] = bridge
    out["bridge_ungated"] = bridge_ung
    # ---- rows
    kg_lo, kg_hi = kg[1] * 100, kg[2] * 100
    u_lo, u_hi = upc[1], upc[2]
    if kg_lo >= qg2.BAR_G and u_hi <= qg2.U_MAX:
        verdict = "G2-OK"
    elif kg_hi < qg2.BAR_G or u_lo > qg2.U_MAX:
        verdict = "G2-FAIL"
    else:
        verdict = "G2-OPEN"
    out["ROW"] = {"verdict": verdict, "KG_pp_point_lo_hi": [round(kg[0] * 100, 4), round(kg_lo, 4), round(kg_hi, 4)], "BAR_G_pp": qg2.BAR_G,
                  "UPC_point_lo_hi": [round(upc[0], 5), round(u_lo, 5), round(u_hi, 5)], "U_max": qg2.U_MAX}
    # ---- validity: V-K (non-vacuity of the gate on P), V-P, V-T2
    n_out = ung["outputs"]
    n_kept = gated["kept"]
    out["V-K"] = {"outputs_on_P": n_out, "kept_by_GA": n_kept, "result": "PASS" if 0 < n_kept < n_out else "FAIL"}
    out["V-P"] = {"even": sample["even"], "odd": sample["odd"], "diff_pct": round(100 * abs(sample["even"] - sample["odd"]) / sample["cycles"], 3),
                  "result": "PASS" if abs(sample["even"] - sample["odd"]) <= 0.02 * sample["cycles"] else "FAIL"}
    items = [(it[0], it[1]) for c in ctl if c["n_enc_rows"] >= 2 for it in c["items"]]
    n, m = len(items), sum(x[1] for x in items)
    lo, hi = wilson(m, n)
    pool = json.load(open(POOL_JSON)) if POOL_JSON and os.path.exists(POOL_JSON) else {"control_n": 0, "matches": 0}
    pn, pm = n + pool["control_n"], m + pool["matches"]
    plo, phi = wilson(pm, pn)
    out["V-T2"] = {"main_n": n, "main_matches": m, "main_rate": round(m / n, 5) if n else None, "main_wilson95": [round(lo, 5), round(hi, 5)],
                   "pilot_pool_n": pool["control_n"], "pilot_pool_matches": pool["matches"], "pooled_n": pn, "pooled_matches": pm, "pooled_rate": round(pm / pn, 5) if pn else None,
                   "pooled_wilson95": [round(plo, 5), round(phi, 5)], "cycles_excluded_lt2_rows_main": sum(1 for c in ctl if c["n_enc_rows"] < 2),
                   "rule": "Amendment 2 A2.2: PASS iff main point rate <= 2 % AND pooled Wilson upper <= 2 %",
                   "result": "PASS" if (n and m / n <= 0.02 and phi_ok(phi)) else "FAIL"}
    # ---- descriptive: rule (ii) share, live OWS-only per sampled cycle
    ung_pop = [r for r in P if int(r["c3_out"]) == 1]
    r2 = sum(1 for r in ung_pop if r["c3_class"] == "right_ii")
    un = sum(1 for r in ung_pop if r["c3_class"] in ("ows", "none"))
    out["rule_ii_share_of_old_rule_unexplained_ungated"] = {"right_ii": r2, "unexplained_now": un, "share": round(r2 / (r2 + un), 4) if (r2 + un) else None}
    ours = ac.parse_all_txt(qg2.OWS_ALLTXT)
    ws = ac.parse_all_txt(qg2.WS_ALLTXT)
    okeys = collections.Counter((r["ts"], ac.normalize_hash_tokens(r["message"])) for r in ours)
    wkeys = collections.Counter((r["ts"], ac.normalize_hash_tokens(r["message"])) for r in ws)
    sampled = {sample_stamp for sample_stamp in {r["_m"]["stamp"] for r in recs}}
    only = 0
    for (ts, msg), n_o in okeys.items():
        if ts in sampled:
            only += max(0, n_o - wkeys.get((ts, msg), 0))
    out["live_OWS_only_rows_per_sampled_cycle"] = {"ows_only_rows": only, "cycles": len(sampled), "per_cycle": round(only / len(sampled), 4)}
    out["wording_G2_OK"] = "necessary, not sufficient, for the step-3 build: UPC counts false outputs at real-signal positions only; it does not establish the step-3 false-decode rate."
    return out


def analyse_pilot(rows_json, run_dir):
    """V-T2 pilot: cycles in index order until n >= 200 type-4 control items (cycles with < 2 encodable rows excluded and counted). STOP if rate > 1 %."""
    spec, sample, recs, ctl = load(rows_json, run_dir)
    ctl = sorted(ctl, key=lambda c: c["cycle_index"])
    n = m = used = excl = 0
    for c in ctl:
        if c["n_enc_rows"] < 2:
            excl += 1
            continue
        used += 1
        for _s, mt in c["items"]:
            n += 1
            m += mt
        if n >= 200:
            break
    lo, hi = wilson(m, n)
    res = {"cycles_used": used, "cycles_excluded_lt2": excl, "control_n": n, "matches": m, "rate": round(m / n, 5) if n else None, "wilson95": [round(lo, 5), round(hi, 5)],
           "reached_n200": n >= 200, "STOP_rule": "STOP if rate > 1 % (>= 3 matches at n = 200) or the residue runs out before n = 200"}
    res["pilot_V-T2"] = "STOP" if (n < 200 or (n and m / n > 0.01)) else "PASS"
    # projected CI half-widths for KG and UPC (descriptive): the pilot's per-cycle rates under the same definitions, scaled to the main sample's block count
    cycles = sorted({r["_ci"] for r in recs})
    bmap = blocks_of(cycles)
    nblocks = max(bmap.values()) + 1
    D_by_c = collections.Counter(r[0] for r in sample["rows"] if r[8])
    bs = [dict(kr=0, ku=0, D=0, cyc=0) for _ in range(nblocks)]
    for c in cycles:
        bs[bmap[c]]["D"] += D_by_c[c]
        bs[bmap[c]]["cyc"] += 1
    for r in recs:
        if int(r["fault"]) or int(r["live_hit"]) or int(r["g_right"]) or int(r["c3_out"]) != 1 or r["f1b"] == "" or float(r["f1b"]) > qg2.T1:
            continue
        b = bmap[r["_ci"]]
        if r["c3_class"] in RIGHT:
            bs[b]["kr"] += 1
        elif r["c3_class"] in ("ows", "none"):
            bs[b]["ku"] += 1
    kg = boot([dict(n=b["kr"], d=b["D"]) for b in bs], "n", "d")
    upc = boot([dict(n=b["ku"], d=b["cyc"]) for b in bs], "n", "d")
    scale = math.sqrt(nblocks / (933 / qg2.BLOCK_CYCLES))
    res["pilot_full_residue_DESCRIPTIVE"] = {"KG_pp_point_lo_hi": [round(100 * x, 4) for x in kg], "UPC_point_lo_hi": [round(x, 5) for x in upc],
                                              "pilot_blocks": nblocks, "projected_main_halfwidth_KG_pp": round(100 * (kg[2] - kg[1]) / 2 * scale, 4),
                                              "projected_main_halfwidth_UPC": round((upc[2] - upc[1]) / 2 * scale, 5)}
    return res


def analyse_pool(runs):
    """Amendment 2 A2.1: the pilot control pooled over residues in order (3, then 2, then 4): cycles in index order within each residue, added until the pooled n >= 200.
    runs = [rows_json:run_dir, ...]. STOP if the pooled rate > 1 % or all residues run out before n = 200."""
    n = m = 0
    detail = []
    for spec_ in runs:
        rows_json, run_dir = spec_.split("::")
        ctl = sorted((json.loads(l) for l in open(os.path.join(run_dir, "control.jsonl"))), key=lambda c: c["cycle_index"])
        used = excl = take_n = take_m = 0
        if n >= 200:
            detail.append({"run": os.path.basename(run_dir.rstrip("/\\")), "cycles_used": 0, "n_added": 0, "skipped_n_already_200": True})
            continue
        for c in ctl:
            if c["n_enc_rows"] < 2:
                excl += 1
                continue
            used += 1
            for _s, mt in c["items"]:
                n += 1; m += mt; take_n += 1; take_m += mt
            if n >= 200:
                break
        detail.append({"run": os.path.basename(run_dir.rstrip("/\\")), "cycles_used": used, "cycles_excluded_lt2": excl, "n_added": take_n, "matches_added": take_m})
    lo, hi = wilson(m, n)
    return {"control_n": n, "matches": m, "rate": round(m / n, 5) if n else None, "wilson95": [round(lo, 5), round(hi, 5)], "reached_n200": n >= 200,
            "per_residue": detail, "pilot_pool_result": "STOP" if (n < 200 or (n and m / n > 0.01)) else "PASS", "rule": "STOP if pooled rate > 1 % or n < 200 after all residues"}


def main():
    global POOL_JSON
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["main", "pilot", "pilotpool"])
    ap.add_argument("--pool-json", default=None, help="main mode: pilot_pool.json from pilotpool (Amendment 2 A2.2)")
    ap.add_argument("--runs", nargs="*", help="pilotpool mode: rows_json::run_dir pairs, in pooling order")
    ap.add_argument("--rows")
    ap.add_argument("--run")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    POOL_JSON = a.pool_json
    res = analyse_pool(a.runs) if a.mode == "pilotpool" else (analyse_main if a.mode == "main" else analyse_pilot)(a.rows, a.run)
    json.dump(res, open(a.out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
