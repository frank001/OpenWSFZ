"""D-009 recalibration -- spec Sec.5 pre-registered decision rule, applied mechanically.

Rows evaluated in STRICT ORDER; first match wins (HK-021: hard thresholds, consequence as an
assertion, rows mutually exclusive). Written before results are known would be ideal, but per
this run's schedule the rule text itself was frozen (verbatim, spec commit f6c5b46) before this
script ran against real numbers -- the code below is a literal transcription of spec Sec.5, not
a post-hoc rationalisation.

    rec(p) = recall_pct, s5(p) = s5_fp_per_slot, s7(p) = s7_fp_per_slot   (from sweep_grid.csv)
    WIN(p)    := rec(p) > rec(B) AND s5(p) <= s5(B) AND s7(p) <= s7(B)
    RELIEF(p) := s5(p) <= 0.50*s5(B) AND s7(p) <= s7(B) AND rec(p) >= rec(B) - 1.00
    B_on_frontier := no p != B with rec(p) >= rec(B) AND s5(p) <= s5(B) AND s7(p) <= s7(B)

    ROW 1: exists p, WIN(p)                                -> optimum MOVED, Captain sign-off
    ROW 2: no WIN, exists p, RELIEF(p)                      -> trust-first option, Captain decision
    ROW 3: no WIN, no RELIEF, B_on_frontier                 -> NO CHANGE (valid, complete result)
    ROW 4: no WIN, no RELIEF, not B_on_frontier              -> VOID, harness defect, do not interpret
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="ascii", errors="replace")

BASELINE_POINT = "k10_c0.10_n60"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.grid, encoding="utf-8")))
    by_point = {r["point"]: r for r in rows}
    if BASELINE_POINT not in by_point:
        print(f"FATAL: baseline point {BASELINE_POINT} not in grid", file=sys.stderr)
        return 2
    b = by_point[BASELINE_POINT]
    rec_b = float(b["recall_pct"])
    s5_b = float(b["s5_fp_per_slot"])
    s7_b = float(b["s7_fp_per_slot"])

    def rec(p): return float(p["recall_pct"])
    def s5(p): return float(p["s5_fp_per_slot"])
    def s7(p): return float(p["s7_fp_per_slot"])

    wins = [p for p in rows if p["point"] != BASELINE_POINT
            and rec(p) > rec_b and s5(p) <= s5_b and s7(p) <= s7_b]
    relief = [p for p in rows if p["point"] != BASELINE_POINT
              and s5(p) <= 0.50 * s5_b and s7(p) <= s7_b and rec(p) >= rec_b - 1.00]
    frontier_dominators = [p for p in rows if p["point"] != BASELINE_POINT
                            and rec(p) >= rec_b and s5(p) <= s5_b and s7(p) <= s7_b]
    b_on_frontier = len(frontier_dominators) == 0

    lines = []
    lines.append(f"BASELINE {BASELINE_POINT}: recall={rec_b:.3f}% s5_fp/slot={s5_b} s7_fp/slot={s7_b}")
    lines.append(f"WIN candidates: {len(wins)}")
    lines.append(f"RELIEF candidates: {len(relief)}")
    lines.append(f"B_on_frontier: {b_on_frontier} (dominators found: {len(frontier_dominators)})")
    lines.append("")

    if wins:
        best = max(wins, key=rec)
        lines.append("ROW 1 FIRED: the optimum has MOVED.")
        lines.append(f"  Candidate (argmax recall among winners): {best['point']} "
                      f"recall={rec(best):.3f}% (Delta {rec(best)-rec_b:+.3f}pp) "
                      f"s5={s5(best)} s7={s7(best)}")
        lines.append("  All winners:")
        for p in sorted(wins, key=rec, reverse=True):
            lines.append(f"    {p['point']}: recall={rec(p):.3f}% s5={s5(p)} s7={s7(p)}")
        lines.append("  => Captain sign-off required before any value ships. QA does not ship it.")
    elif relief:
        lines.append("ROW 2 FIRED: no strict WIN, but a trust-first RELIEF option exists.")
        for p in sorted(relief, key=s5):
            lines.append(f"    {p['point']}: recall={rec(p):.3f}% (Delta {rec(p)-rec_b:+.3f}pp) "
                          f"s5={s5(p)} (Delta {s5(p)-s5_b:+.5f}) s7={s7(p)}")
        lines.append("  => Costed menu row for the Captain. Captain decision required.")
    elif b_on_frontier:
        lines.append("ROW 3 FIRED: baseline (10, 0.10, 60) is still Pareto-optimal on this corpus.")
        lines.append("  => Recalibration returns NO CHANGE. Valid and complete result.")
    else:
        lines.append("ROW 4 FIRED: CONTRADICTION -- baseline is dominated yet no point qualifies "
                      "as WIN or RELIEF.")
        lines.append("  => VOID the run and report a harness defect. Do not interpret the grid.")

    text = "\n".join(lines) + "\n"
    args.out.write_text(text, encoding="ascii")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
