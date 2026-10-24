#!/usr/bin/env python3
"""COH-MULTISET A1.7 / A1.8: (1) the anchor offset delta on the PILOT cycles' exact OWS/WSJT-X matches, from ALL.TXT numbers only (no decode);
(2) the counted structure of the SAMPLE (rows per cycle, blocks of 8), for the D3 half-width as a function of the unknown NET_X.

delta = median(OWS_DT - WS_DT) over exact matches (same cycle, same text, |df| <= 10 Hz, one-to-one nearest-first: COH-GAIN's Test B rule, reused unchanged
from cg_select). Pass rule (A1.7): |delta - 0.7| <= 0.05 s.

HK-037 / NFR-021: message text exists only inside cg_select.read_alltxt / test_b_matches; this script persists and prints numbers only. No audio is opened.
"""
from __future__ import annotations

import json
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "coh-gain"))
sys.path.insert(0, os.path.join(HERE, "..", "nhard-rep"))
import cg_select as SEL  # noqa: E402

REPO = SEL.REPO
RUN_DIR = os.path.join(os.environ.get("OPENWSFZ_ARTEFACTS", "D:/Projects/claude/OpenWSFZ/artefacts"), "20261022_1949_endurance_run-gathered")
WS = os.path.join(RUN_DIR, "wsjt-x", "ALL.TXT")
OWS = os.path.join(RUN_DIR, "owsfz", "ALL.TXT")
SELECTION = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-24-coh-multiset", "selection.json")
OUT = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-24-coh-multiset", "delta_and_structure.json")
DELTA_NOMINAL_S = 0.7
DELTA_TOL_S = 0.05
BLOCK_CYCLES = 8
COH_GAIN_ROWS = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-06-coh-gain", "rows.json")
assert (DELTA_NOMINAL_S, DELTA_TOL_S, BLOCK_CYCLES) == (0.7, 0.05, 8)


def main():
    sel = json.load(open(SELECTION))
    ws, ows = SEL.read_alltxt(WS), SEL.read_alltxt(OWS)
    # (1) delta on the pilot
    diffs, pilot_lines = [], 0
    for _, stamp in sel["pilot"]:
        wl, ol = ws.get(stamp, []), ows.get(stamp, [])
        pilot_lines += len(wl)
        used_o = set()
        cands = sorted((abs(o[2] - w[2]), oi, wi) for oi, o in enumerate(ol) for wi, w in enumerate(wl) if abs(o[2] - w[2]) <= SEL.CORROBORATION_DELTA_HZ and o[3] == w[3])
        used_w = set()
        for _, oi, wi in cands:
            if oi in used_o or wi in used_w:
                continue
            used_o.add(oi)
            used_w.add(wi)
            diffs.append(ol[oi][1] - wl[wi][1])
    delta = statistics.median(diffs)
    q = statistics.quantiles(diffs, n=4)
    delta_res = {"pilot_cycles": len(sel["pilot"]), "pilot_wsjtx_lines": pilot_lines, "exact_matches": len(diffs), "median_s": round(delta, 4),
                 "q1_s": round(q[0], 4), "q3_s": round(q[2], 4), "abs_dev_from_0.7_s": round(abs(delta - DELTA_NOMINAL_S), 4), "tolerance_s": DELTA_TOL_S,
                 "pass": bool(abs(delta - DELTA_NOMINAL_S) <= DELTA_TOL_S)}
    # (2) structure of the sample
    per_cycle = [len(ws.get(s, [])) for _, s in sel["sample"]]
    n_rows = sum(per_cycle)
    n_blocks = math.ceil(len(per_cycle) / BLOCK_CYCLES)
    struct = {"sample_cycles": len(per_cycle), "wsjtx_rows_incl_unencodable": n_rows, "rows_per_cycle_mean": round(n_rows / len(per_cycle), 2),
              "rows_per_cycle_median": statistics.median(per_cycle), "rows_per_cycle_max": max(per_cycle), "cycles_with_zero_rows": per_cycle.count(0),
              "blocks_of_8": n_blocks}
    # calibration of the design effect from COH-GAIN's published G-union-C3 NET (+5.25 [4.69, 5.77], 309 cycles): half-width 0.54 pp vs binomial on its row count
    cg = json.load(open(COH_GAIN_ROWS))
    n_cg = len(cg["rows"])
    p_cg = 0.0525
    binom_cg = 1.96 * math.sqrt(p_cg * (1 - p_cg) / n_cg) * 100
    deff = (0.54 / binom_cg) ** 2
    table = {}
    for p in (0.002, 0.005, 0.0075, 0.01, 0.015, 0.02):
        binom = 1.96 * math.sqrt(p * (1 - p) / n_rows) * 100
        table[f"{p * 100:.2f}"] = {"binomial_half_width_pp": round(binom, 3), "with_COH_GAIN_design_effect_pp": round(binom * math.sqrt(deff), 3)}
    calib = {"coh_gain_rows_json_rows": n_cg, "coh_gain_binomial_half_width_pp_at_5.25": round(binom_cg, 3), "coh_gain_published_half_width_pp": 0.54,
             "design_effect": round(deff, 3), "note": "indicative: calibrated on G-union-C3 NET, a different statistic and a different night; rows.json may be only part of the 5.25 pp sample"}
    out = {"delta": delta_res, "structure": struct, "half_width_by_true_net_x_pp": table, "calibration": calib}
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
