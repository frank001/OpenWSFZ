"""
analyse_ablation.py — Gate-isolation ablation analysis (D-009, 2026-06-21).

Reads per-config truth.csv + owsfz-all.txt and computes:
  - co_channel (P0–P2 equal-stack) decode rate
  - co_channel_sweep (P15–P20 offset-sweep) decode rate + P15 / P16 per-part
  - S5 FP decodes / slots

Usage (from qa/rr-study/):
  python results/d009-ablation-2026-06-21/analyse_ablation.py

Writes results/d009-ablation-2026-06-21/ablation.md.
"""
from __future__ import annotations

import csv
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_QA_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))

from harness.common import parse_all_txt, normalise_slot

# ---------------------------------------------------------------------------
# Config table
# ---------------------------------------------------------------------------

# Config 3 S5 result is known from d009-k10-confirm-s7-clean/confirm_summary.md
# (5/120 FPs = 0.042/slot). Config 3 S7 data is in d009-k10-confirm-s7-clean/.
CONFIGS = [
    {"id": 1, "K": 1,  "gates": "off", "s7_dir": None, "s5_dir": None,
     "s7_override": None, "s5_override": None},
    {"id": 2, "K": 10, "gates": "off", "s7_dir": None, "s5_dir": None,
     "s7_override": None, "s5_override": None},
    {"id": 3, "K": 10, "gates": "on",  "s7_dir": None, "s5_dir": None,
     "s7_override": None,
     "s5_override": {"fp_decodes": 5, "n_slots": 120}},
    {"id": 4, "K": 5,  "gates": "off", "s7_dir": None, "s5_dir": None,
     "s7_override": None, "s5_override": None},
]

_ABLATION_DIR = Path(__file__).resolve().parent
_RESULTS_DIR  = _ABLATION_DIR.parent

# S7 P0-P2 (co_channel) and P15-P20 (co_channel_sweep)
CO_CHANNEL_PARTS       = {0, 1, 2}
CO_CHANNEL_SWEEP_PARTS = {15, 16, 17, 18, 19, 20}

_FREQ_TOL_HZ = 4.0


def _parse_cycle_utc(s: str) -> datetime | None:
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def _resolve_cfg_dirs(cfg: dict) -> tuple[Path | None, Path | None]:
    """Return (s7_dir, s5_dir) for a config."""
    n = cfg["id"]
    if n == 3:
        # Reuse gate-confirmation run directories
        s7 = _RESULTS_DIR / "d009-k10-confirm-s7-clean"
        s5 = None  # use s5_override
        return s7, s5
    s7 = _ABLATION_DIR / f"cfg{n}-s7"
    s5 = _ABLATION_DIR / f"cfg{n}-s5"
    return s7, s5


def analyse_s7(s7_dir: Path) -> dict | None:
    """Compute S7 family decode rates from truth.csv + owsfz-all.txt."""
    truth_path = s7_dir / "truth.csv"
    all_txt    = s7_dir / "owsfz-all.txt"

    if not truth_path.exists():
        print(f"  [SKIP] S7 truth.csv missing: {truth_path}")
        return None
    if not all_txt.exists():
        print(f"  [SKIP] S7 owsfz-all.txt missing: {all_txt}")
        return None

    # ── Load truth rows ──────────────────────────────────────────────────────
    truth_rows_raw: list[dict] = []
    with open(truth_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("scenario_id", "").strip() != "S7":
                continue
            try:
                pi = int(row.get("part_index", -1))
            except ValueError:
                continue
            dt = _parse_cycle_utc(row.get("cycle_utc", ""))
            if dt is None:
                continue
            freq = None
            try:
                freq = float(row["true_freq_hz"]) if row.get("true_freq_hz") else None
            except ValueError:
                pass
            truth_rows_raw.append({
                "part":  pi,
                "slot":  dt,
                "msg":   row.get("message_text", "").strip(),
                "freq":  freq,
            })

    # Deduplicate truth rows by (part, slot, msg) — appended runs produce
    # duplicate injections; dedup ensures injected count is correct.
    seen: set[tuple] = set()
    truth_rows: list[dict] = []
    for tr in truth_rows_raw:
        key = (tr["part"], tr["slot"], tr["msg"])
        if key not in seen:
            seen.add(key)
            truth_rows.append(tr)
    if len(truth_rows) < len(truth_rows_raw):
        dupes = len(truth_rows_raw) - len(truth_rows)
        print(f"  [NOTE] Removed {dupes} duplicate truth rows "
              f"(appended-run artefact); {len(truth_rows)} unique rows remain.")

    # ── Parse owsfz-all.txt ──────────────────────────────────────────────────
    owsfz_recs, _ = parse_all_txt(all_txt)
    dec_by_slot: dict[datetime, list] = {}
    for rec in owsfz_recs:
        dec_by_slot.setdefault(rec.utc, []).append(rec)

    # ── Match per truth row ──────────────────────────────────────────────────
    consumed: set = set()

    def _count_family(part_set: set[int]) -> tuple[int, int]:
        matched = 0
        injected = 0
        for tr in truth_rows:
            if tr["part"] not in part_set:
                continue
            injected += 1
            cands = dec_by_slot.get(tr["slot"], [])
            for idx, cand in enumerate(cands):
                key = (tr["slot"], idx)
                if key in consumed:
                    continue
                if " ".join(tr["msg"].split()) != " ".join(cand.message.split()):
                    continue
                if tr["freq"] is not None and abs(cand.freq_hz - tr["freq"]) > _FREQ_TOL_HZ:
                    continue
                consumed.add(key)
                matched += 1
                break
        return matched, injected

    # Must process in a consistent order (no shared consumed set across families)
    # Actually co_channel and co_channel_sweep are disjoint parts → safe to share.
    consumed.clear()
    all_parts = CO_CHANNEL_PARTS | CO_CHANNEL_SWEEP_PARTS
    # Compute per-part for sweep
    per_part: dict[int, tuple[int, int]] = {}
    for pi in sorted(all_parts):
        m, inj = _count_family({pi})
        per_part[pi] = (m, inj)
        consumed.clear()   # reset for each part (non-overlapping slots)

    # Total families (reset consumed for clean run)
    consumed.clear()
    co_ch_m, co_ch_inj = _count_family(CO_CHANNEL_PARTS)
    consumed.clear()
    sw_m, sw_inj = _count_family(CO_CHANNEL_SWEEP_PARTS)

    return {
        "co_channel_matched":   co_ch_m,
        "co_channel_injected":  co_ch_inj,
        "co_channel_pct":       100.0 * co_ch_m / co_ch_inj if co_ch_inj else float("nan"),
        "sweep_matched":        sw_m,
        "sweep_injected":       sw_inj,
        "sweep_pct":            100.0 * sw_m / sw_inj if sw_inj else float("nan"),
        "per_part":             per_part,
    }


def analyse_s5(s5_dir: Path) -> dict | None:
    """Compute S5 FP rate from truth.csv + owsfz-all.txt."""
    truth_path = s5_dir / "truth.csv"
    all_txt    = s5_dir / "owsfz-all.txt"

    if not truth_path.exists():
        print(f"  [SKIP] S5 truth.csv missing: {truth_path}")
        return None
    if not all_txt.exists():
        print(f"  [SKIP] S5 owsfz-all.txt missing: {all_txt}")
        return None

    # Load slot timestamps from truth
    s5_slots: list[datetime] = []
    with open(truth_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("scenario_id", "").strip() != "S5":
                continue
            dt = _parse_cycle_utc(row.get("cycle_utc", ""))
            if dt is not None:
                s5_slots.append(dt)

    n_slots = len(s5_slots)
    slot_set = set(s5_slots)

    owsfz_recs, _ = parse_all_txt(all_txt)
    fp_count = sum(1 for r in owsfz_recs if r.utc in slot_set)

    return {
        "fp_decodes": fp_count,
        "n_slots":    n_slots,
        "fp_per_slot": fp_count / n_slots if n_slots else float("nan"),
    }


def main() -> None:
    print("=== D-009 Gate-Isolation Ablation Analysis ===\n")

    rows: list[dict] = []

    for cfg in CONFIGS:
        n     = cfg["id"]
        K     = cfg["K"]
        gates = cfg["gates"]
        print(f"--- Config {n}: K={K}, corr/nhard={gates} ---")

        s7_dir, s5_dir = _resolve_cfg_dirs(cfg)

        # ── S7 ────────────────────────────────────────────────────────────────
        if cfg.get("s7_override") is not None:
            s7 = cfg["s7_override"]
        elif s7_dir is not None:
            print(f"  S7 dir: {s7_dir}")
            s7 = analyse_s7(s7_dir)
        else:
            s7 = None

        if s7:
            co_ch_pct = f"{s7['co_channel_pct']:.1f}%  ({s7['co_channel_matched']}/{s7['co_channel_injected']})"
            sw_pct    = f"{s7['sweep_pct']:.1f}%  ({s7['sweep_matched']}/{s7['sweep_injected']})"
            p15_m, p15_i = s7["per_part"].get(15, (0, 0))
            p16_m, p16_i = s7["per_part"].get(16, (0, 0))
            p15_str = f"{100*p15_m/p15_i:.0f}%  ({p15_m}/{p15_i})" if p15_i else "—"
            p16_str = f"{100*p16_m/p16_i:.0f}%  ({p16_m}/{p16_i})" if p16_i else "—"
            print(f"  co_channel:       {co_ch_pct}")
            print(f"  co_channel_sweep: {sw_pct}")
            print(f"  P15 (Δ5 Hz):      {p15_str}")
            print(f"  P16 (Δ7 Hz):      {p16_str}")
        else:
            co_ch_pct = "—"
            sw_pct    = "—"
            p15_str   = "—"
            p16_str   = "—"
            print("  S7: no data")

        # ── S5 ────────────────────────────────────────────────────────────────
        if cfg.get("s5_override") is not None:
            s5 = cfg["s5_override"]
            fp_str = (f"{s5['fp_decodes']}/{s5['n_slots']}  "
                      f"({s5['fp_decodes']/s5['n_slots']:.3f}/slot)")
            print(f"  S5 FP:            {fp_str}  [from prior run]")
        elif s5_dir is not None:
            print(f"  S5 dir: {s5_dir}")
            s5 = analyse_s5(s5_dir)
            if s5:
                fp_str = (f"{s5['fp_decodes']}/{s5['n_slots']}  "
                          f"({s5['fp_per_slot']:.3f}/slot)")
                print(f"  S5 FP:            {fp_str}")
            else:
                fp_str = "—"
                print("  S5: no data")
        else:
            s5 = None
            fp_str = "—"
        print()

        # Collect for table
        rows.append({
            "id":        n,
            "K":         K,
            "gates":     gates,
            "co_ch_pct": (f"{s7['co_channel_pct']:.1f}%"
                          if s7 else "—"),
            "sw_pct":    (f"{s7['sweep_pct']:.1f}%"
                          if s7 else "—"),
            "p15":       p15_str if s7 else "—",
            "p16":       p16_str if s7 else "—",
            "fp_slot":   (f"{s5['fp_decodes']/s5['n_slots']:.3f}"
                          if s5 else "—"),
            "fp_raw":    (f"{s5['fp_decodes']}/{s5['n_slots']}"
                          if s5 else "—"),
            # Gate thresholds for decision rule
            "co_ch_val": s7["co_channel_pct"] if s7 else None,
            "sw_val":    s7["sweep_pct"] if s7 else None,
            "fp_val":    (s5["fp_decodes"] / s5["n_slots"]) if s5 else None,
        })

    # ── Print decision rule evaluation ───────────────────────────────────────
    print("=== DECISION RULE (from ablation-decision-arch.md §3) ===")
    print("SHIP the simplest config that satisfies ALL THREE:")
    print("  (1) co_channel_sweep >= 89%")
    print("  (2) co_channel (P0-P2) >= 45%")
    print("  (3) S5 FP <= 0.10/slot")
    print()

    for r in rows:
        passes = []
        if r["sw_val"] is not None:
            passes.append("PASS" if r["sw_val"] >= 89.0 else "FAIL")
        else:
            passes.append("?")
        if r["co_ch_val"] is not None:
            passes.append("PASS" if r["co_ch_val"] >= 45.0 else "FAIL")
        else:
            passes.append("?")
        if r["fp_val"] is not None:
            passes.append("PASS" if r["fp_val"] <= 0.10 else "FAIL")
        else:
            passes.append("?")
        verdict = ("✅ SHIP" if all(p == "PASS" for p in passes)
                   else "❌ FAIL" if "FAIL" in passes else "?")
        print(f"  Config {r['id']} (K={r['K']}, gates={r['gates']}): "
              f"sweep={passes[0]}, co_ch={passes[1]}, FP={passes[2]}  → {verdict}")

    # ── Write ablation.md ─────────────────────────────────────────────────────
    md = _build_ablation_md(rows)
    out_path = _ABLATION_DIR / "ablation.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"\nWrote {out_path}")


def _build_ablation_md(rows: list[dict]) -> str:
    lines = [
        "# D-009 Gate-Isolation Ablation — Results",
        "",
        f"**Date:** 2026-06-21  ",
        "**Branch:** fix/d009-fp-callsign-filter  ",
        "**Architect decision:** dev-tasks/2026-06-21-d009-ablation-decision-arch.md  ",
        "**Developer handoff:** dev-tasks/2026-06-21-d009-ablation-dev.md  ",
        "",
        "## Ablation table",
        "",
        "| Config | K | corr/nhard | co_channel % | co_channel_sweep % | P15 (Δ5 Hz) | P16 (Δ7 Hz) | S5 FP/slot |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for r in rows:
        label = f"cfg{r['id']}"
        if r["id"] == 3:
            label += " (ref)"
        lines.append(
            f"| {label} | {r['K']} | {r['gates']} "
            f"| {r['co_ch_pct']} | {r['sw_pct']} "
            f"| {r['p15']} | {r['p16']} | {r['fp_slot']} ({r['fp_raw']}) |"
        )

    lines += [
        "",
        "## Decision-rule evaluation",
        "",
        "**SHIP criteria (pre-committed, from §3 of ablation-decision-arch.md):**",
        "- co_channel_sweep ≥ 89%",
        "- co_channel (P0–P2) ≥ 45%",
        "- S5 FP ≤ 0.10/slot",
        "",
        "Ship the **simplest** qualifying config (fewest active gates, then lowest K).",
        "",
        "| Config | sweep ≥ 89%? | co_ch ≥ 45%? | FP ≤ 0.10? | Verdict |",
        "|---|---|---|---|---|",
    ]

    for r in rows:
        sw = ("✅" if r["sw_val"] is not None and r["sw_val"] >= 89.0
              else "❌" if r["sw_val"] is not None else "?")
        co = ("✅" if r["co_ch_val"] is not None and r["co_ch_val"] >= 45.0
              else "❌" if r["co_ch_val"] is not None else "?")
        fp = ("✅" if r["fp_val"] is not None and r["fp_val"] <= 0.10
              else "❌" if r["fp_val"] is not None else "?")
        all_pass = (r["sw_val"] is not None and r["sw_val"] >= 89.0 and
                    r["co_ch_val"] is not None and r["co_ch_val"] >= 45.0 and
                    r["fp_val"] is not None and r["fp_val"] <= 0.10)
        verdict = "✅ **SHIP**" if all_pass else "❌ no"
        lines.append(
            f"| cfg{r['id']} (K={r['K']}, {r['gates']}) "
            f"| {sw} | {co} | {fp} | {verdict} |"
        )

    lines += [
        "",
        "## Reading",
        "",
        "*(Architect fills in after reviewing the table — see ablation-decision-arch.md §5 pre-committed rule.)*",
        "",
        "---",
        "",
        "**NFR-021 compliance:** No real callsigns appear in this document.  ",
        "S5 FP counts are numeric only; S7 uses Q-prefix synthetic callsigns (MSG-01/02/03).  ",
    ]

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
