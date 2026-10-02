"""#194 scan: calibrate thresholds on ONE run (2026-09-23) by the spec's section-5 rule.

    python scan_calibrate.py --sidecars <_out/run dir> --out <thresholds.json> [--report <txt>]

T_m = median + 6 x 1.4826 x MAD (one-sided upward; two-sided on the deviation from the median
for g_db, tau_ms, dg_db, dtau_ms; |drift_ppm| for drift), never below the spec's floors.
The calibration run's own flagged slots and the per-metric flagged fraction are reported.
Audio-derived numbers only.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scan_core as sc  # noqa: E402

# Inherited constants, asserted so a silent edit cannot change them (spec section 5).
assert sc.K_SIGMA == 6.0 and sc.MAD_SCALE == 1.4826
assert sc.RULES["step_db_max"][1] == 0.5 and sc.RULES["g_db"][1] == 0.5
assert sc.RULES["drift_ppm"][1] == 20.0 and sc.RULES["zero_run_ms"][1] == 5.0
assert sc.RULES["tile_excess_db"][1] == 10.0 and sc.RULES["clip_n"][1] == 1.0
assert sc.RULES["tau_ms"][1] == 2.0
assert sc.CROSS_RULES["dg_db"][1] == 0.5 and sc.CROSS_RULES["dtau_ms"][1] == 2.0

SIDES = ("owsfz", "wsjtx")


def load(path: Path):
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k, v in list(r.items()):
            if k in ("slot", "cycle_utc", "scenario", "wav_sha256"):
                continue
            try:
                r[k] = float(v)
            except ValueError:
                pass
    return [r for r in rows if not r["ref_mismatch"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sidecars", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--run", default="2026-09-23-5f17b43")
    a = ap.parse_args()
    d = Path(a.sidecars)
    data = {s: load(d / f"sidecar_{s}.csv") for s in SIDES}
    th = {"calibration_run": a.run, "k_sigma": sc.K_SIGMA, "mad_scale": sc.MAD_SCALE,
          "n_scanned": {s: len(data[s]) for s in SIDES}, "sides": {}, "cross": {}}
    flagged_by = {}
    for s in SIDES:
        th["sides"][s] = {}
        for m, (kind, floor) in sc.RULES.items():
            vals = [r[m] for r in data[s] if r[m] == r[m] and abs(r[m]) != float("inf")]
            row = sc.threshold_row(vals, kind, floor)
            row["n_values"] = len(vals)
            fl = [r["slot"] for r in data[s] if sc.flagged(r[m], row)]
            row["n_flagged_calibration"] = len(fl)
            row["flagged_fraction"] = len(fl) / max(1, len(vals))
            th["sides"][s][m] = row
            flagged_by[(s, m)] = fl
    by_slot = {s: {r["slot"]: r for r in data[s]} for s in SIDES}
    common = [k for k in by_slot["owsfz"] if k in by_slot["wsjtx"]]
    cross = {"dg_db": [], "dtau_ms": []}
    for k in common:
        o, w = by_slot["owsfz"][k], by_slot["wsjtx"][k]
        cross["dg_db"].append((k, o["g_db"] - w["g_db"]))
        if o["tau_ms"] == o["tau_ms"] and w["tau_ms"] == w["tau_ms"]:
            cross["dtau_ms"].append((k, o["tau_ms"] - w["tau_ms"]))
    for m, (kind, floor) in sc.CROSS_RULES.items():
        vals = [v for _, v in cross[m]]
        row = sc.threshold_row(vals, kind, floor)
        row["n_values"] = len(vals)
        fl = [k for k, v in cross[m] if sc.flagged(v, row)]
        row["n_flagged_calibration"] = len(fl)
        row["flagged_fraction"] = len(fl) / max(1, len(vals))
        th["cross"][m] = row
        flagged_by[("cross", m)] = fl
    th["flagged_slots_calibration"] = {f"{s}:{m}": v for (s, m), v in flagged_by.items() if v}
    th["metrics_over_1pct"] = sorted(f"{s}:{m}" for s in list(SIDES) + ["cross"]
                                     for m, row in (th["sides"].get(s, {}) if s != "cross" else th["cross"]).items()
                                     if row["flagged_fraction"] > 0.01)
    Path(a.out).write_text(json.dumps(th, indent=1, sort_keys=True), encoding="utf-8")
    print(f"wrote {a.out}")
    for s in SIDES:
        print(s)
        for m, row in th["sides"][s].items():
            print(f"  {m:15s} med {row['median']:10.3f} mad {row['mad']:8.3f} T {row['T']:10.3f} "
                  f"floor {row['floor']} applied {row['floor_applied']} flagged {row['n_flagged_calibration']}"
                  f" ({100 * row['flagged_fraction']:.1f}%)")
    for m, row in th["cross"].items():
        print(f"  cross {m:9s} med {row['median']:8.3f} mad {row['mad']:7.3f} T {row['T']:8.3f} "
              f"flagged {row['n_flagged_calibration']} ({100 * row['flagged_fraction']:.1f}%)")
    print("metrics over 1 %:", th["metrics_over_1pct"])


if __name__ == "__main__":
    main()
