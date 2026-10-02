"""#194 scan: the FREEZE. Per side x group thresholds from the 09-23 calibration run, the
mechanical DESCRIPTIVE test, and the flagging function used by every later stage.

    python scan_freeze.py --sidecars <_out/run dir> --out <thresholds.json>

Rules: spec section 5 (median + 6 x 1.4826 x MAD, floors) per side and group (ruling A5), tail
and head rules fixed by A2, clip at >= 1 (A6). A (side, group, metric) cell whose one-sided
flags (excluding slots classified BOTH on the same metric family) exceed 2 % of the group is
DESCRIPTIVE: reported, never used to flag, no PC1.  Audio-derived numbers only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scan_core as sc  # noqa: E402

SIDES = ("owsfz", "wsjtx")
NUM = {"slot", "cycle_utc", "scenario", "wav_sha256"}
CAL_METRICS = list(sc.RULES.keys())                        # thresholds computed from data
FIXED_METRICS = ["tail_zero_ms", "head_zero_ms"]           # rules fixed by A2
ALL_METRICS = CAL_METRICS + FIXED_METRICS

assert sc.K_SIGMA == 6.0 and sc.MAD_SCALE == 1.4826
assert (sc.RULES["step_db_max"][1], sc.RULES["g_db"][1], sc.RULES["drift_ppm"][1],
        sc.RULES["zero_run_ms"][1], sc.RULES["tile_excess_db"][1], sc.RULES["tau_ms"][1]) == (0.5, 0.5, 20.0, 5.0, 10.0, 2.0)
assert sc.CROSS_RULES["dg_db"][1] == 0.5 and sc.CROSS_RULES["dtau_ms"][1] == 2.0
assert sc.GROUPS == ("single", "multi", "noise", "tone2", "tone3")


CRLF, LF = bytes([13, 10]), bytes([10])


def sha_lf(path: Path) -> str:
    """SHA-256 of the file with CRLF normalised to LF (what git stores; stable across checkouts)."""
    return hashlib.sha256(Path(path).read_bytes().replace(CRLF, LF)).hexdigest()


def load(path: Path):
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            for k, v in list(r.items()):
                if k not in NUM:
                    try:
                        r[k] = float(v)
                    except ValueError:
                        pass
            r["group"] = sc.group_of(r["scenario"], r["part"])
            rows.append(r)
    return rows


def fixed_flag(side: str, metric: str, value: float) -> bool:
    if value != value:
        return False
    if metric == "head_zero_ms":
        return value > sc.TAIL_HEAD_TOL_MS
    if metric == "tail_zero_ms":
        if side == "wsjtx":
            return abs(value - sc.WSJTX_TAIL_MS) > sc.TAIL_HEAD_TOL_MS
        return value > sc.TAIL_HEAD_TOL_MS
    raise KeyError(metric)


def cell_flag(th: dict, side: str, group: str, metric: str, value: float) -> bool:
    """Raw flag (threshold exceeded) irrespective of DESCRIPTIVE status."""
    if metric in FIXED_METRICS:
        return fixed_flag(side, metric, value)
    row = th["sides"][side][group].get(metric)
    if row is None:          # no valid values in this group (e.g. tau/drift on all-ambiguous slots)
        return False
    return sc.flagged(value, row)


def slot_flags(th: dict, side: str, row: dict) -> dict:
    return {m: cell_flag(th, side, row["group"], m, row[m]) for m in ALL_METRICS}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sidecars", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--run", default="2026-09-23-5f17b43")
    ap.add_argument("--pc1", default=None, help="pc1.json: apply A7 (DESCRIPTIVE-ABOVE-RANGE)")
    ap.add_argument("--carry", default=None, help="previous thresholds.json: every threshold value except lag_lost is carried unchanged (A10)")
    ap.add_argument("--extra-above-range", default="", help="comma list of cells to mark DESCRIPTIVE-ABOVE-RANGE (A9 results)")
    a = ap.parse_args()
    d = Path(a.sidecars)
    carry = json.loads(Path(a.carry).read_text(encoding="utf-8")) if a.carry else None
    data = {s: [r for r in load(d / f"sidecar_{s}.csv") if not r["ref_mismatch"]] for s in SIDES}
    th = {"calibration_run": a.run, "k_sigma": sc.K_SIGMA, "mad_scale": sc.MAD_SCALE,
          "scan_core_py_sha256": sha_lf(Path(sc.__file__)),
          "descriptive_fraction": sc.DESCRIPTIVE_FRACTION, "min_group_n": sc.MIN_GROUP_N,
          "groups": {g: {s: sum(1 for r in data[s] if r["group"] == g) for s in SIDES} for g in sc.GROUPS},
          "tail_rule": {"wsjtx": "abs(tail_zero_ms - 600.0) > 5", "owsfz": "tail_zero_ms > 5"},
          "head_rule": "head_zero_ms > 5 (both sides)",
          "sides": {s: {g: {} for g in sc.GROUPS} for s in SIDES}, "cross": {g: {} for g in sc.GROUPS},
          "descriptive": [], "counts": {}}
    # 1. thresholds per side x group
    for s in SIDES:
        for g in sc.GROUPS:
            rows = [r for r in data[s] if r["group"] == g]
            for m, (kind, floor) in sc.RULES.items():
                vals = [r[m] for r in rows if r[m] == r[m] and abs(r[m]) != float("inf")]
                if not vals:
                    continue
                old = carry["sides"][s][g].get(m) if carry and m != "lag_lost" else None
                if old is not None:
                    row = {k: v for k, v in old.items() if k not in
                           ("DESCRIPTIVE", "DESCRIPTIVE_ABOVE_RANGE", "flagged_total", "flagged_one_sided")}
                else:
                    row = sc.threshold_row(vals, kind, floor)
                    row["n_values"] = len(vals)
                th["sides"][s][g][m] = row
    # cross-side (dg_db, dtau_ms) per group
    by = {s: {r["slot"]: r for r in data[s]} for s in SIDES}
    for g in sc.GROUPS:
        cross = {"dg_db": [], "dtau_ms": []}
        for k, o in by["owsfz"].items():
            w = by["wsjtx"].get(k)
            if w is None or o["group"] != g:
                continue
            cross["dg_db"].append(o["g_db"] - w["g_db"])
            if o["tau_ms"] == o["tau_ms"] and w["tau_ms"] == w["tau_ms"]:
                cross["dtau_ms"].append(o["tau_ms"] - w["tau_ms"])
        for m, (kind, floor) in sc.CROSS_RULES.items():
            if cross[m]:
                oldc = carry["cross"][g].get(m) if carry else None
                if oldc is not None:
                    row = {k: v for k, v in oldc.items() if k not in ("DESCRIPTIVE", "flagged_total")}
                else:
                    row = sc.threshold_row(cross[m], kind, floor)
                    row["n_values"] = len(cross[m])
                th["cross"][g][m] = row
    # 2. raw flags, BOTH classification by family, mechanical DESCRIPTIVE test
    flags = {s: {r["slot"]: slot_flags(th, s, r) for r in data[s]} for s in SIDES}

    def fam_flagged(side, slot, fam):
        return any(f and sc.FAMILIES[m] == fam for m, f in flags[side][slot].items())

    both = {s: set() for s in SIDES}          # (slot, metric) that are BOTH
    for s, o in (("owsfz", "wsjtx"), ("wsjtx", "owsfz")):
        for slot, fl in flags[s].items():
            for m, f in fl.items():
                if f and slot in flags[o] and fam_flagged(o, slot, sc.FAMILIES[m]):
                    both[s].add((slot, m))
    cells = []
    for s in SIDES:
        for g in sc.GROUPS:
            rows = [r for r in data[s] if r["group"] == g]
            n = len(rows)
            for m in ALL_METRICS:
                tot = [r["slot"] for r in rows if flags[s][r["slot"]][m]]
                one = [x for x in tot if (x, m) not in both[s]]
                desc = bool(n and len(one) / n > sc.DESCRIPTIVE_FRACTION)
                cell = {"side": s, "group": g, "metric": m, "n": n, "flagged_total": len(tot),
                        "flagged_both": len(tot) - len(one), "flagged_one_sided": len(one),
                        "one_sided_fraction": len(one) / n if n else 0.0, "DESCRIPTIVE": desc}
                cells.append(cell)
                if desc:
                    th["descriptive"].append(f"{s}:{g}:{m}")
                if m in th["sides"][s][g]:
                    th["sides"][s][g][m]["DESCRIPTIVE"] = desc
                    th["sides"][s][g][m]["flagged_total"] = len(tot)
                    th["sides"][s][g][m]["flagged_one_sided"] = len(one)
    # cross cells (family 'cross'; no BOTH exclusion applies)
    for g in sc.GROUPS:
        for m, row in th["cross"][g].items():
            vals = []
            for k, o in by["owsfz"].items():
                w = by["wsjtx"].get(k)
                if w is None or o["group"] != g:
                    continue
                v = (o["g_db"] - w["g_db"]) if m == "dg_db" else (o["tau_ms"] - w["tau_ms"])
                vals.append(v)
            fl = [v for v in vals if sc.flagged(v, row)]
            row["flagged_total"] = len(fl)
            row["DESCRIPTIVE"] = bool(vals and len(fl) / len(vals) > sc.DESCRIPTIVE_FRACTION)
            if row["DESCRIPTIVE"]:
                th["descriptive"].append(f"cross:{g}:{m}")
    # A7 (ruling 2026-10-02 1925): a cell whose 2x injection is not representable in ANY drawn copy
    # becomes DESCRIPTIVE-ABOVE-RANGE. A list change only: no threshold value changes.
    th["descriptive_above_range"] = list(carry.get("descriptive_above_range", [])) if carry else []
    for cell in [c for c in a.extra_above_range.split(",") if c]:
        if cell not in th["descriptive_above_range"]:
            th["descriptive_above_range"].append(cell)
    for cell in th["descriptive_above_range"]:
        if cell not in th["descriptive"]:
            th["descriptive"].append(cell)
        sd, gr, mt = cell.split(":")
        if mt in th["sides"][sd][gr]:
            th["sides"][sd][gr][mt]["DESCRIPTIVE"] = True
            th["sides"][sd][gr][mt]["DESCRIPTIVE_ABOVE_RANGE"] = True
    if a.pc1:
        for r in json.loads(Path(a.pc1).read_text(encoding="utf-8"))["results"]:
            rates = r.get("rates")
            if rates and "n_slots" in r and rates["2.0"]["of"] < r["n_slots"] and not r["cell"].endswith(":hiccup"):
                th["descriptive_above_range"].append(r["cell"])
                if r["cell"] not in th["descriptive"]:
                    th["descriptive"].append(r["cell"])
                side, group, metric = r["cell"].split(":")
                if metric in th["sides"][side][group]:
                    th["sides"][side][group][metric]["DESCRIPTIVE"] = True
                    th["sides"][side][group][metric]["DESCRIPTIVE_ABOVE_RANGE"] = True
        th["descriptive_above_range"].sort()
    th["descriptive"].sort()
    th["cells"] = cells
    th["counts"] = {
        "descriptive_cells": len(th["descriptive"]),
        "lag_ambiguous_by_group": {s: {g: sum(1 for r in data[s] if r["group"] == g and r["lag_ambiguous"])
                                       for g in sc.GROUPS} for s in SIDES},
        "ref_unverifiable_by_group": {s: {g: sum(1 for r in data[s] if r["group"] == g and r["nondiscriminating"])
                                          for g in sc.GROUPS} for s in SIDES},
    }
    th["flagged_slots_calibration"] = {
        s: {slot: sorted(m for m, f in fl.items() if f) for slot, fl in flags[s].items() if any(fl.values())}
        for s in SIDES}
    with open(a.out, "w", encoding="utf-8", newline=chr(10)) as fh:
        fh.write(json.dumps(th, indent=1, sort_keys=True))
    sha = sha_lf(Path(a.out))
    print(f"wrote {a.out}  sha256 {sha}")
    print("scan_core.py sha256", th["scan_core_py_sha256"])
    print("DESCRIPTIVE-ABOVE-RANGE (A7):", len(th["descriptive_above_range"]), th["descriptive_above_range"])
    print("DESCRIPTIVE cells:", len(th["descriptive"]))
    for x in th["descriptive"]:
        print("  ", x)
    print("groups n:", th["groups"])
    print("REF-UNVERIFIABLE:", th["counts"]["ref_unverifiable_by_group"])
    print("lag_ambiguous:", th["counts"]["lag_ambiguous_by_group"])


if __name__ == "__main__":
    main()
