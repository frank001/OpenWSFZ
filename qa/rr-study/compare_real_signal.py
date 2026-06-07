#!/usr/bin/env python3
"""Compare two ALL.TXT decode logs against a WSJT-X reference.

Quantifies the real-signal recall change between a baseline (pre-fix) and a
fix-version decode run. Designed to pair with batch_decode.py: run the pre-fix
DLL over the same WAV files that the live fix session produced, then run this
script to produce an evidence-based comparison.

Usage:
    python qa/rr-study/compare_real_signal.py \\
        --wsjt     "D001-pcm-sic_items/WSJT-X ALL.TXT" \\
        --baseline  D001-pcm-sic_items/baseline_all.txt \\
        --fix      "D001-pcm-sic_items/OpenWSFZ ALL.TXT" \\
        [--out      qa/rr-study/QA-FINDINGS-D001-real-signal-comparison.md] \\
        [--baseline-label "pre-fix (20260002)"] \\
        [--fix-label      "PCM-SIC fix (20260003)"]

If --out is omitted the markdown is written to stdout.

Matching strategy:
    A decode is counted as matching if the message text is identical at the same
    slot timestamp. SNR, DT, and audio frequency are not considered — these vary
    between apps even for the same physical signal.  Hashed callsigns (reported
    as <...> by one app but decoded by the other) will therefore count as misses;
    this is a known limitation and is documented in the output.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

# ── Parsing ───────────────────────────────────────────────────────────────────

# Matches both WSJT-X and OpenWSFZ ALL.TXT lines:
#   YYMMDD_HHMMSS  <whitespace>  <freq_mhz>  Rx FT8  <snr>  <dt>  <audio_hz>  <message>
_LINE_RE = re.compile(
    r"^(\d{6}_\d{6})\s+"         # group 1: timestamp
    r"[\d.]+\s+Rx FT8\s+"        # freq + mode
    r"([-\d]+)\s+"               # group 2: SNR
    r"([-\d.]+)\s+"              # group 3: DT
    r"(\d+)\s+"                  # group 4: audio freq Hz
    r"(.+)$"                     # group 5: message text
)


def _parse_log(path: Path) -> dict[str, list[str]]:
    """Parse an ALL.TXT into {timestamp: [message, ...]}.

    Returns a defaultdict so missing keys give an empty list.
    """
    slots: dict[str, list[str]] = defaultdict(list)
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _LINE_RE.match(line.strip())
        if m:
            ts  = m.group(1)
            msg = m.group(5).strip()
            slots[ts].append(msg)
    return slots


# ── Statistics ────────────────────────────────────────────────────────────────

def _per_slot_stats(
    wsjt:  dict[str, list[str]],
    query: dict[str, list[str]],
) -> tuple[int, int, int, int, int]:
    """Compute recall statistics for *query* relative to *wsjt* reference.

    Both dicts are restricted to slots present in both (common slots).

    Returns:
        common_slots   — number of slots present in both logs
        wsjt_total     — WSJT-X decodes in common slots
        query_total    — query decodes in common slots
        matched        — exact message matches
        query_only     — query decodes not in WSJT-X (bonus finds or FP)
    """
    common = set(wsjt.keys()) & set(query.keys())
    wsjt_total  = 0
    query_total = 0
    matched     = 0
    query_only  = 0

    for ts in common:
        w_msgs = wsjt[ts]
        q_msgs = query[ts]
        wsjt_total  += len(w_msgs)
        query_total += len(q_msgs)
        for qm in q_msgs:
            if qm in w_msgs:
                matched += 1
            else:
                query_only += 1

    return len(common), wsjt_total, query_total, matched, query_only


# ── Markdown report ───────────────────────────────────────────────────────────

def _build_report(
    wsjt_path:  Path,
    base_path:  Path,
    fix_path:   Path,
    base_label: str,
    fix_label:  str,
    wsjt:       dict[str, list[str]],
    base:       dict[str, list[str]],
    fix:        dict[str, list[str]],
) -> str:
    # Common-slot stats for each decoder vs WSJT-X
    b_common, b_wsjt, b_total, b_matched, b_only = _per_slot_stats(wsjt, base)
    f_common, f_wsjt, f_total, f_matched, f_only = _per_slot_stats(wsjt, fix)

    b_recall = b_matched / b_wsjt * 100 if b_wsjt else 0.0
    f_recall = f_matched / f_wsjt * 100 if f_wsjt else 0.0
    delta_recall = f_recall - b_recall

    # Slots present in fix but not baseline (crash slots etc.)
    fix_only_slots  = set(fix.keys()) - set(base.keys())
    base_only_slots = set(base.keys()) - set(fix.keys())

    # Slots present in all three
    three_common = set(wsjt.keys()) & set(base.keys()) & set(fix.keys())
    # Per-three-common-slot: base matched, fix matched, both matched, fix-only finds
    t_b_matched = t_f_matched = t_both = t_fix_bonus = 0
    for ts in three_common:
        w = wsjt[ts]; b = base[ts]; fx = fix[ts]
        bm = sum(1 for m in b  if m in w)
        fm = sum(1 for m in fx if m in w)
        t_b_matched += bm
        t_f_matched += fm
        t_both      += sum(1 for m in b  if m in w and m in fx)
        # Fix finds something WSJT-X also found, that baseline missed
        t_fix_bonus += sum(1 for m in fx if m in w and m not in b)

    wsjt_three = sum(len(wsjt[ts]) for ts in three_common)
    b3_recall  = t_b_matched / wsjt_three * 100 if wsjt_three else 0.0
    f3_recall  = t_f_matched / wsjt_three * 100 if wsjt_three else 0.0

    lines = [
        "# D001 Real-Signal Comparison — Baseline vs PCM-SIC Fix",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| WSJT-X log | `{wsjt_path.name}` |",
        f"| Baseline log | `{base_path.name}` — {base_label} |",
        f"| Fix log | `{fix_path.name}` — {fix_label} |",
        f"| WSJT-X total slots | {len(wsjt)} |",
        f"| Baseline slots | {len(base)} |",
        f"| Fix slots | {len(fix)} |",
        "",
        "## Recall vs WSJT-X — per decoder (own common slots)",
        "",
        "Each decoder is compared against WSJT-X over the slots that *it* ran "
        "(not necessarily identical slot sets — crash-lost slots are excluded from "
        "the denominator for the affected decoder).",
        "",
        "| Metric | Baseline | Fix | Δ |",
        "|---|---|---|---|",
        f"| Common slots with WSJT-X | {b_common} | {f_common} | — |",
        f"| WSJT-X decodes (common) | {b_wsjt:,} | {f_wsjt:,} | — |",
        f"| Decoder decodes (common) | {b_total:,} | {f_total:,} | {f_total - b_total:+,} |",
        f"| Matched (= TP) | {b_matched:,} | {f_matched:,} | {f_matched - b_matched:+,} |",
        f"| **Recall of WSJT-X** | **{b_recall:.1f}%** | **{f_recall:.1f}%** | **{delta_recall:+.1f} pp** |",
        f"| Decoder-only (bonus/FP) | {b_only:,} | {f_only:,} | {f_only - b_only:+,} |",
        "",
        "## Recall vs WSJT-X — three-way common slots only",
        "",
        f"Restricted to the {len(three_common)} slots where all three logs have data "
        "(eliminates slot-count differences between baseline and fix).",
        "",
        "| Metric | Baseline | Fix | Δ |",
        "|---|---|---|---|",
        f"| WSJT-X decodes | {wsjt_three:,} | {wsjt_three:,} | — |",
        f"| Matched | {t_b_matched:,} | {t_f_matched:,} | {t_f_matched - t_b_matched:+,} |",
        f"| **Recall** | **{b3_recall:.1f}%** | **{f3_recall:.1f}%** | **{f3_recall - b3_recall:+.1f} pp** |",
        f"| Fix-only TP (fix found, baseline missed, WSJT-X confirms) | — | {t_fix_bonus:,} | — |",
        "",
        "## Slot coverage",
        "",
        f"| | Count |",
        f"|---|---|",
        f"| Slots in all three logs | {len(three_common)} |",
        f"| Fix-only slots (not in baseline — crash losses etc.) | {len(fix_only_slots)} |",
        f"| Baseline-only slots (not in fix) | {len(base_only_slots)} |",
        "",
        "## Interpretation",
        "",
        "- **Recall Δ (pp)** is the primary metric. Positive → fix improves real-signal decode rate.",
        "- **Fix-only TP** counts messages that: (a) WSJT-X decoded, (b) the fix decoded, but (c) the",
        "  baseline missed. These are the candidates attributable to the PCM-SIC extra passes.",
        "- **Decoder-only** decodes are messages not in WSJT-X — a mix of genuine SIC bonus finds and",
        "  false positives. Without an independent oracle these cannot be separated.",
        "",
        "> **Note on hashed callsigns:** WSJT-X may decode `<HB10GBT>` (full hash) where OpenWSFZ",
        "> reports `<...>` (generic placeholder). These will count as misses in both decoders even if",
        "> the underlying message was correctly decoded. Recall figures are therefore lower-bounds.",
        "",
        "---",
        "_Generated by `qa/rr-study/compare_real_signal.py`_",
    ]
    return "\n".join(lines) + "\n"


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--wsjt",     required=True, type=Path,
                        help="WSJT-X ALL.TXT reference log")
    parser.add_argument("--baseline", required=True, type=Path,
                        help="Pre-fix baseline ALL.TXT (from batch_decode.py)")
    parser.add_argument("--fix",      required=True, type=Path,
                        help="Post-fix ALL.TXT (from live session or batch_decode.py)")
    parser.add_argument("--out",      type=Path, default=None,
                        help="Output markdown path (default: stdout)")
    parser.add_argument("--baseline-label", default="pre-fix (shim 20260002)",
                        help="Human label for the baseline decoder")
    parser.add_argument("--fix-label",      default="PCM-SIC fix (shim 20260003)",
                        help="Human label for the fix decoder")
    args = parser.parse_args()

    for p, name in [(args.wsjt, "--wsjt"), (args.baseline, "--baseline"), (args.fix, "--fix")]:
        if not p.exists():
            sys.exit(f"ERROR: {name} file not found: {p}")

    print("Parsing logs ...", file=sys.stderr)
    wsjt = _parse_log(args.wsjt)
    base = _parse_log(args.baseline)
    fix  = _parse_log(args.fix)
    print(f"  WSJT-X  : {len(wsjt)} slots, {sum(len(v) for v in wsjt.values()):,} decodes",
          file=sys.stderr)
    print(f"  Baseline: {len(base)} slots, {sum(len(v) for v in base.values()):,} decodes",
          file=sys.stderr)
    print(f"  Fix     : {len(fix)} slots, {sum(len(v) for v in fix.values()):,} decodes",
          file=sys.stderr)

    report = _build_report(
        args.wsjt, args.baseline, args.fix,
        args.baseline_label, args.fix_label,
        wsjt, base, fix,
    )

    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"Report written to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(report)


if __name__ == "__main__":
    main()
