#!/usr/bin/env python3
"""NHARD40-DEFAULT `NT` analysis -- ROW 0b/0d verdicts, the gate (S1/S2/S3), and the
descriptive picture (spec Sec.3.4/3.5/3.6/3.7). Pure computation over part_nt.py's
persisted JSON -- no decoding here, so this can be re-run freely as data is topped up.

Definitions (spec Sec.3.4, predicates as code -- HK-021(r)):
  p60(r)/p40(r)/p0(r) = share of rung-r cycles with a genuine decode at that leg.
  Band B = { r : p60(r) < 0.95 }, from the 60-leg ONLY, computed BEFORE any
           60-vs-40/0 comparison (HK-021(y): the split is not outcome-chosen).
  G_B = genuine@60 count, summed over band-B rungs.
  K_B = of those, absent@40 (killed by the change).
  C_B = of those, absent@0 (the OSD-dependent ceiling -- base ROW 0b: osd 1->0).
  L_B = K_B/G_B, L0_B = C_B/G_B, each with an exact Clopper-Pearson 95% CI
        (single station per cycle -- no clustering, spec Sec.3.1's own reasoning).

Gate (spec Sec.3.6, first match wins):
  S2: CP95_lo(L_B) >= BAR_S  -- measurable genuine loss near threshold.
  S1: CP95_hi(L_B) <  BAR_S  -- no genuine loss detected at this resolution.
  S3: otherwise, or ROW 0d short.

ROW 0b (ratified as PART of part_nt.py's own run -- re-verified here independently
from the persisted rung set, not re-trusted) and ROW 0d (G_B >= 300, else this script
prints the exact --topup command for the rungs that need it; part_nt.py --topup adds
the block(s), then this script is re-run) are both checked before the gate is read.

Report-only (spec Sec.3.5, evaluated both ways per HK-021(k) -- it cannot move the
row: L_B counts a genuine loss whether or not nhard=0 also finds it): count of cycles
where genuine@60=1, genuine@40=0, genuine@0=1 ("killed at 40 but present at 0").

Usage:
    python part_nt_analysis.py <nt_json>
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "f-nbr-a"))

from stats_common import clopper_pearson  # noqa: E402

BAR_S = 0.05  # PO-ratified, frozen, 2026-09-12 09:15Z, before any NT datum (spec Sec.5)
BAND_B_BAR = 0.95
G_B_FLOOR = 300


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)
    rungs = {int(k): v for k, v in state["rungs"].items()}
    return state, rungs


def per_rung_stats(rungs: dict):
    """Returns {ridx: {db, n, p60, p40, p0, k60, k40, k0}} sorted-friendly dict."""
    out = {}
    for ridx, rec in rungs.items():
        trials = rec["trials"]
        n = len(trials)
        if n == 0:
            continue
        k60 = sum(1 for t in trials if t["60"]["genuine"])
        has40 = "40" in trials[0]
        k40 = sum(1 for t in trials if t["40"]["genuine"]) if has40 else None
        k0 = sum(1 for t in trials if t["0"]["genuine"]) if has40 else None
        out[ridx] = {
            "db": rec["db"], "n": n,
            "p60": k60 / n, "p40": (k40 / n) if has40 else None,
            "p0": (k0 / n) if has40 else None,
            "k60": k60, "k40": k40, "k0": k0,
        }
    return out


def row0b_check(state, stats, nominal_lo_db, nominal_hi_db):
    lo_idx = min(r for r in stats if stats[r]["db"] == nominal_lo_db) \
        if any(stats[r]["db"] == nominal_lo_db for r in stats) else None
    hi_idx = min(r for r in stats if stats[r]["db"] == nominal_hi_db) \
        if any(stats[r]["db"] == nominal_hi_db for r in stats) else None
    p60_lo = stats[lo_idx]["p60"] if lo_idx is not None else None
    p60_hi = stats[hi_idx]["p60"] if hi_idx is not None else None
    ext = state.get("extension", {})
    void = ext.get("void", False)
    return {
        "p60_at_nominal_lo": p60_lo, "p60_at_nominal_hi": p60_hi,
        "low_extension_rungs_added": ext.get("low_added", 0),
        "high_extension_rungs_added": ext.get("high_added", 0),
        "void": void,
        "pass": (not void) and p60_lo is not None and p60_hi is not None
        and p60_lo <= 0.05 and p60_hi >= BAND_B_BAR,
    }


def band_b(stats):
    """Band B rungs -- computed from the 60-leg ONLY, before any comparison."""
    return sorted(r for r, s in stats.items() if s["p60"] < BAND_B_BAR)


def gate(rungs, band):
    """G_B, K_B, C_B, L_B/L0_B with CP95, over band-B rungs. Also the report-only
    anomaly count (killed@40, present@0) -- evaluated, never gating (HK-021(k))."""
    G_B = K_B = C_B = anomaly = 0
    for ridx in band:
        for t in rungs[ridx]["trials"]:
            if not t["60"]["genuine"]:
                continue
            G_B += 1
            g40 = t["40"]["genuine"]
            g0 = t["0"]["genuine"]
            if not g40:
                K_B += 1
                if g0:
                    anomaly += 1
            if not g0:
                C_B += 1
    L_B = (K_B / G_B) if G_B else None
    L0_B = (C_B / G_B) if G_B else None
    lo, hi = clopper_pearson(K_B, G_B) if G_B else (None, None)
    lo0, hi0 = clopper_pearson(C_B, G_B) if G_B else (None, None)
    return {
        "G_B": G_B, "K_B": K_B, "C_B": C_B, "L_B": L_B, "L_B_ci": [lo, hi],
        "L0_B": L0_B, "L0_B_ci": [lo0, hi0],
        "killed_at_40_present_at_0_report_only": anomaly,
    }


def gate_row(g):
    G_B, ci = g["G_B"], g["L_B_ci"]
    if G_B < G_B_FLOOR:
        return "S3", "ROW 0d short: G_B < %d" % G_B_FLOOR
    lo, hi = ci
    if lo >= BAR_S:
        return "S2", "CP95_lo(L_B)=%.4f >= BAR_S=%.2f" % (lo, BAR_S)
    if hi < BAR_S:
        return "S1", "CP95_hi(L_B)=%.4f < BAR_S=%.2f" % (hi, BAR_S)
    return "S3", "CP95=[%.4f,%.4f] straddles BAR_S=%.2f" % (lo, hi, BAR_S)


def fifty_pct_point(stats, leg_key: str):
    """Linear-interpolated dB at which the leg's p crosses 0.5, scanning rungs in
    ascending dB order for the first upward crossing. None if no crossing exists
    (curve entirely above or below 0.5, or the leg has no data)."""
    rows = sorted((s["db"], s[leg_key]) for s in stats.values() if s[leg_key] is not None)
    for (db_a, p_a), (db_b, p_b) in zip(rows, rows[1:]):
        if p_a < 0.5 <= p_b and p_b != p_a:
            frac = (0.5 - p_a) / (p_b - p_a)
            return db_a + frac * (db_b - db_a)
    return None


def false_decodes_per_cycle(rungs, leg_key: str):
    total_false = 0
    total_n = 0
    for rec in rungs.values():
        for t in rec["trials"]:
            if leg_key in t:
                total_false += t[leg_key]["n_false"]
                total_n += 1
    return (total_false / total_n) if total_n else None


def main() -> int:
    path = sys.argv[1]
    state, rungs = load(path)
    stats = per_rung_stats(rungs)

    row0b = row0b_check(state, stats, state["nominal_lo_db"], state["nominal_hi_db"])
    print("ROW 0b:", json.dumps(row0b, indent=2))
    if row0b["void"]:
        print("VOID -- escalate per spec Sec.3.5. Not computing the gate.")
        return 1

    band = band_b(stats)
    print(f"Band B: {len(band)} rungs -> dB values "
          f"{[round(stats[r]['db'], 1) for r in band]}")

    g = gate(rungs, band)
    print("Gate stats:", json.dumps(g, indent=2))

    if g["G_B"] < G_B_FLOOR:
        # ROW 0d: name the exact top-up command, spec Sec.3.5 (blocks of 250,
        # <=2 blocks, band still fixed from the 60-leg only).
        topup_rungs = [round(stats[r]["db"], 1) for r in band]
        print(f"ROW 0d: G_B={g['G_B']} < {G_B_FLOOR}. Top up with:\n"
              f"  python part_nt.py {path} --topup "
              f"{','.join(str(x) for x in topup_rungs)}")

    row, reason = gate_row(g)
    print(f"GATE ROW: {row} ({reason})")

    p50_60 = fifty_pct_point(stats, "p60")
    p50_40 = fifty_pct_point(stats, "p40")
    shift_db = (p50_40 - p50_60) if (p50_60 is not None and p50_40 is not None) else None

    desc = {
        "per_rung": {round(s["db"], 1): {"p60": s["p60"], "p40": s["p40"], "p0": s["p0"],
                                          "n": s["n"]}
                     for s in sorted(stats.values(), key=lambda x: x["db"])},
        "fifty_pct_db_60": p50_60, "fifty_pct_db_40": p50_40,
        "sensitivity_shift_db_60_to_40": shift_db,
        "false_decodes_per_cycle_60": false_decodes_per_cycle(rungs, "60"),
        "false_decodes_per_cycle_40": false_decodes_per_cycle(rungs, "40"),
        "false_decodes_per_cycle_0": false_decodes_per_cycle(rungs, "0"),
    }
    print("Descriptive (Sec.3.7):", json.dumps(desc, indent=2))

    out = {"row0b": row0b, "band_b_rungs_db": [round(stats[r]["db"], 1) for r in band],
           "gate": g, "gate_row": row, "gate_reason": reason, "descriptive": desc}
    out_path = path.rsplit(".json", 1)[0] + "_analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"-> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
