#!/usr/bin/env python3
"""SPEC.md section 2.5 item 10's zero-free-parameter model, and section 5.2's mandatory
three-part falsification criterion for Phase 1b.

Model (nothing fitted): recall(delta) = P( DT_true in [delta - LOW, delta + HIGH] ), where
[LOW, HIGH] = [1.60, 3.12] is the decoder's own hardcoded time-search bound read from
native/ft8_lib_build/patched/ft8/decode.c:279 (see SPEC.md section 2.5 item 10), and
DT_true is drawn from arm A's own reference decode population (pooled across cycles, one
DT value per decoded signal -- this is how the Architect's own 12-point validation table
was built, reproduced here as a self-check before trusting this script for Phase 1b's
gate).

Falsification criterion (SPEC.md section 5.2, "state the verdict before looking"):
  1. |measured - predicted| <= 0.10 outside cliff transitions, <= 0.25 inside them, at
     every measured point.
  2. positive-cliff 50% crossing within +/-0.15s of DT_med + HIGH.
  3. negative-cliff 50% crossing within +/-0.15s of DT_med - LOW.
If any fails: fall back to the full 27-point grid before quoting deliverables #2/#5.

"Inside a cliff transition" has no exact numeric definition in SPEC.md -- operationally
defined here as predicted recall in (0.05, 0.95), i.e. the region where the CDF is
actually transitioning, rather than a hardcoded distance from the crossing. Flagged
explicitly so this choice can be checked, not silently assumed.

HK-009: reconfigure stdout to UTF-8.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_recall import parse_all_txt  # noqa: E402

LOW = 1.60   # decoder search bound, negative side: DT_obs >= delta - LOW
HIGH = 3.12  # decoder search bound, positive side: DT_obs <= delta + HIGH
OUTSIDE_TOL = 0.10
INSIDE_TOL = 0.25
CROSSING_TOL = 0.15
TRANSITION_LO, TRANSITION_HI = 0.05, 0.95  # operational "inside a cliff transition" band


def load_dt_population(all_txt_path: Path) -> list[float]:
    rows = parse_all_txt(all_txt_path)
    dts = []
    for r in rows:
        try:
            dts.append(float(r["dt"]))
        except ValueError:
            pass
    return dts


def predict_recall(delta: float, dt_population: list[float]) -> float:
    if not dt_population:
        return float("nan")
    lo, hi = delta - LOW, delta + HIGH
    n_in = sum(1 for dt in dt_population if lo <= dt <= hi)
    return n_in / len(dt_population)


def dt_median(dt_population: list[float]) -> float:
    return statistics.median(dt_population)


def crossing(points: list[tuple[float, float]], target: float = 0.5) -> float | None:
    """Linear-interpolated delta where measured recall crosses `target`, scanning points
    sorted by delta. Returns None if no crossing is bracketed by the given points."""
    pts = sorted(points, key=lambda p: p[0])
    for (d0, r0), (d1, r1) in zip(pts, pts[1:]):
        if (r0 - target) == 0:
            return d0
        if (r0 - target) * (r1 - target) < 0:
            frac = (target - r0) / (r1 - r0)
            return d0 + frac * (d1 - d0)
    return None


def cmd_check(args: argparse.Namespace) -> None:
    dt_pop = load_dt_population(Path(args.ref_all_txt))
    dmed = dt_median(dt_pop)
    print(f"DT population: n={len(dt_pop)}, median={dmed:.4f}")
    print(f"Search bound: DT_obs in [delta-{LOW}, delta+{HIGH}] -> tolerance interval "
          f"[{dmed - HIGH:.3f}, {dmed + LOW:.3f}] (delta frame)")
    print(f"Predicted cliff centres: negative={dmed - HIGH:.3f}  positive={dmed + LOW:.3f}\n")

    measured = []
    with open(args.measured, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            d = float(row["delta"])
            med = float(row["median"])
            measured.append((d, med))
    measured.sort()

    print(f"{'delta':>8} {'measured':>10} {'predicted':>10} {'resid':>8} {'zone':>10} {'tol':>6} {'ok':>4}")
    all_ok = True
    resid_sq = []
    for d, meas in measured:
        pred = predict_recall(d, dt_pop)
        resid = meas - pred
        resid_sq.append(resid * resid)
        inside = TRANSITION_LO < pred < TRANSITION_HI
        tol = INSIDE_TOL if inside else OUTSIDE_TOL
        ok = abs(resid) <= tol
        all_ok = all_ok and ok
        print(f"{d:8.3f} {meas:10.4f} {pred:10.4f} {resid:+8.4f} "
              f"{'inside' if inside else 'outside':>10} {tol:6.2f} {'OK' if ok else 'FAIL':>4}")
    rms = statistics.mean(resid_sq) ** 0.5 if resid_sq else float("nan")
    print(f"\nRMS error: {rms:.4f}")

    pos_cross = crossing(measured)
    # crossing() finds the FIRST bracketed 0.5-crossing scanning delta ascending; for a
    # two-cliff curve (recall high in the middle, low at both extremes) we need the
    # positive-side crossing (high->low going up in delta, at the high-delta end) and the
    # negative-side crossing (low->high going up in delta, at the low-delta end)
    # separately. Split the point list at its recall-maximum to disambiguate.
    if measured:
        peak_delta = max(measured, key=lambda p: p[1])[0]
        neg_side = [(d, r) for d, r in measured if d <= peak_delta]
        pos_side = [(d, r) for d, r in measured if d >= peak_delta]
        neg_crossing = crossing(neg_side)
        pos_crossing = crossing(pos_side)
    else:
        neg_crossing = pos_crossing = None

    pred_pos_centre = dmed + LOW
    pred_neg_centre = dmed - HIGH

    print(f"\nPositive 50% crossing: measured={pos_crossing}  predicted={pred_pos_centre:.3f}  "
          f"tol=+/-{CROSSING_TOL}")
    crit2_ok = pos_crossing is not None and abs(pos_crossing - pred_pos_centre) <= CROSSING_TOL
    print(f"  criterion 2: {'PASS' if crit2_ok else 'FAIL (or not bracketed by measured points)'}")

    print(f"Negative 50% crossing: measured={neg_crossing}  predicted={pred_neg_centre:.3f}  "
          f"tol=+/-{CROSSING_TOL}")
    crit3_ok = neg_crossing is not None and abs(neg_crossing - pred_neg_centre) <= CROSSING_TOL
    print(f"  criterion 3: {'PASS' if crit3_ok else 'FAIL (or not bracketed by measured points)'}")

    print(f"\nCriterion 1 (per-point tolerance): {'PASS' if all_ok else 'FAIL'}")
    verdict = all_ok and crit2_ok and crit3_ok
    print(f"\n{'='*60}\nOVERALL VERDICT: {'MODEL SURVIVES' if verdict else 'MODEL FALSIFIED -- fall back to the full 27-point grid'}\n{'='*60}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref-all-txt", required=True, help="arm A's ALL.TXT (DT population source)")
    ap.add_argument("--measured", required=True, help="summary CSV from run_phase.py (delta,median,...)")
    ap.set_defaults(fn=cmd_check)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
