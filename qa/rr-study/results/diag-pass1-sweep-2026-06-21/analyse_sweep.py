"""
analyse_sweep.py — Pass-1 K_MIN_SCORE_PASS2 trade-curve analysis.

Reads per-point truth.csv + owsfz-s5-all.txt + owsfz-s7-all.txt and
computes:
  - S5 FP decodes / slots  (D-009 cost axis)
  - S7 P0-2 co_channel decode rate  (D-001 benefit axis)

Usage (from qa/rr-study/):
  python results/diag-pass1-sweep-2026-06-21/analyse_sweep.py
"""
from __future__ import annotations

import csv
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_QA_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))

from harness.common import parse_all_txt, normalise_slot

# ── Sweep points ─────────────────────────────────────────────────────────────
POINTS = [
    ("p0-minscore1",  1),
    ("p1-minscore3",  3),
    ("p2-minscore5",  5),
    ("p3-minscore7",  7),
    ("p4-minscore10", 10),
]

_SWEEP_DIR = Path(__file__).resolve().parent
_FREQ_TOL_HZ = 4.0
_SLOT_S = 15


def _parse_cycle_utc(s: str) -> datetime | None:
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def analyse_point(point_dir: Path) -> dict | None:
    """Return metrics dict for one sweep point, or None if data missing."""

    # ── S5 analysis ──────────────────────────────────────────────────────────
    s5_dir  = point_dir / "s5"
    s5_truth  = s5_dir / "truth.csv"
    s5_all    = s5_dir / "owsfz-s5-all.txt"

    if not s5_truth.exists() or not s5_all.exists():
        print(f"  [SKIP] {point_dir.name}/s5 — data missing")
        return None

    # Load S5 truth rows → set of slot datetimes
    s5_slots: list[datetime] = []
    with open(s5_truth, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("scenario_id", "").strip() == "S5":
                dt = _parse_cycle_utc(row["cycle_utc"])
                if dt is not None:
                    s5_slots.append(dt)

    n_s5_slots = len(s5_slots)
    s5_slot_set = set(s5_slots)

    # Parse OpenWSFZ ALL.TXT for S5 run
    owsfz_s5_recs, _ = parse_all_txt(s5_all)

    # Group OpenWSFZ decodes by normalised slot
    s5_decodes_by_slot: dict[datetime, int] = {}
    for rec in owsfz_s5_recs:
        slot = rec.utc   # already normalised by parse_all_txt
        if slot in s5_slot_set:
            s5_decodes_by_slot[slot] = s5_decodes_by_slot.get(slot, 0) + 1

    n_fp_decodes = sum(s5_decodes_by_slot.values())
    n_fp_slots   = len(s5_decodes_by_slot)
    fp_per_slot  = n_fp_decodes / n_s5_slots if n_s5_slots > 0 else float("nan")

    # ── S7 P0-2 analysis ─────────────────────────────────────────────────────
    s7_dir   = point_dir / "s7"
    s7_truth = s7_dir / "truth.csv"
    s7_all   = s7_dir / "owsfz-s7-all.txt"

    if not s7_truth.exists() or not s7_all.exists():
        print(f"  [SKIP] {point_dir.name}/s7 — data missing")
        return None

    # Load S7 truth rows for parts 0, 1, 2
    s7_truth_rows: list[dict] = []
    with open(s7_truth, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("scenario_id", "").strip() != "S7":
                continue
            try:
                pi = int(row.get("part_index", -1))
            except ValueError:
                continue
            if pi not in (0, 1, 2):
                continue
            dt = _parse_cycle_utc(row["cycle_utc"])
            if dt is None:
                continue
            s7_truth_rows.append({
                "slot": dt,
                "msg":  row["message_text"].strip(),
                "freq": float(row["true_freq_hz"]) if row["true_freq_hz"] else None,
            })

    # Parse OpenWSFZ ALL.TXT for S7 run
    owsfz_s7_recs, _ = parse_all_txt(s7_all)

    # Group S7 decodes by slot
    s7_dec_by_slot: dict[datetime, list] = {}
    for rec in owsfz_s7_recs:
        s7_dec_by_slot.setdefault(rec.utc, []).append(rec)

    # Match each truth row
    consumed: set = set()
    matched_count = 0
    for tr in s7_truth_rows:
        slot = tr["slot"]
        cands = s7_dec_by_slot.get(slot, [])
        for idx, cand in enumerate(cands):
            key = (slot, idx)
            if key in consumed:
                continue
            # Text match (whitespace-normalised)
            t_msg = " ".join(tr["msg"].split())
            c_msg = " ".join(cand.message.split())
            if t_msg != c_msg:
                continue
            # Freq match (±4 Hz)
            if tr["freq"] is not None and abs(cand.freq_hz - tr["freq"]) > _FREQ_TOL_HZ:
                continue
            consumed.add(key)
            matched_count += 1
            break

    n_s7_injected = len(s7_truth_rows)
    co_channel_rate = (100.0 * matched_count / n_s7_injected
                       if n_s7_injected > 0 else float("nan"))

    return {
        "n_fp_decodes": n_fp_decodes,
        "n_fp_slots":   n_fp_slots,
        "n_s5_slots":   n_s5_slots,
        "fp_per_slot":  fp_per_slot,
        "co_channel_pct": co_channel_rate,
        "s7_matched":     matched_count,
        "s7_injected":    n_s7_injected,
    }


def main() -> None:
    print("=== Pass-1 sweep analysis ===\n")

    results: list[tuple[int, dict | None]] = []
    for name, k in POINTS:
        point_dir = _SWEEP_DIR / name
        print(f"Point {name} (K_MIN_SCORE_PASS2={k}):")
        m = analyse_point(point_dir)
        results.append((k, m))
        if m:
            print(f"  S5 FP: {m['n_fp_decodes']} decodes in {m['n_s5_slots']} slots "
                  f"→ {m['fp_per_slot']:.3f} FP/slot ({m['n_fp_slots']} FP-event slots)")
            print(f"  S7:    {m['s7_matched']}/{m['s7_injected']} = {m['co_channel_pct']:.1f}%")
        print()

    # ── Trade-curve table ────────────────────────────────────────────────────
    print("\n=== TRADE CURVE ===")
    print(f"{'K_MIN_SCORE_PASS2':>20} {'S5 FP/slot':>12} {'S5 FP cnt/slots':>17} {'S7 co_ch %':>12}")
    print("-" * 66)
    for k, m in results:
        if m:
            fp_str    = f"{m['fp_per_slot']:.3f}"
            cnt_str   = f"{m['n_fp_decodes']}/{m['n_s5_slots']}"
            coch_str  = f"{m['co_channel_pct']:.1f}%"
        else:
            fp_str = cnt_str = coch_str = "N/A"
        print(f"{k:>20} {fp_str:>12} {cnt_str:>17} {coch_str:>12}")

    # Write pass1_sweep.md
    md_lines = [
        "# D-009 — Pass-1 `K_MIN_SCORE_PASS2` Trade-Curve",
        "",
        f"**Date:** 2026-06-21  ",
        f"**Branch:** fix/d009-fp-callsign-filter  ",
        "**Shim:** 20260028 (OSD_NHARD_MAX=60, OSD_CORR_THRESHOLD=0.10 unchanged throughout)  ",
        "**Metric method:** OpenWSFZ-only; no WSJT-X comparator required for this diagnostic axis.  ",
        "",
        "## Trade-curve table",
        "",
        "| `K_MIN_SCORE_PASS2` | S5 FP/slot | S5 FP count / slots | S7 co_channel_sweep % |",
        "|---|---|---|---|",
    ]
    for k, m in results:
        if m:
            fp_str   = f"{m['fp_per_slot']:.3f}"
            cnt_str  = f"{m['n_fp_decodes']} / {m['n_s5_slots']}"
            coch_str = f"{m['co_channel_pct']:.1f}%"
        else:
            fp_str = cnt_str = coch_str = "N/A"
        label = "1 (baseline)" if k == 1 else str(k)
        md_lines.append(f"| {label} | {fp_str} | {cnt_str} | {coch_str} |")

    md_lines += [
        "",
        "## Reading (to be completed after all data collected)",
        "",
        "*(Architect fills in after reviewing the table.)*",
        "",
        "---",
        "",
        f"**NFR-021 compliance:** No real callsigns appear in this document.  ",
        "S5 FP counts are numeric only; S7 uses Q-prefix synthetic callsigns (MSG-01/02/03).  ",
    ]

    out_path = _SWEEP_DIR / "pass1_sweep.md"
    out_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
