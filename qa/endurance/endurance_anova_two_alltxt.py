#!/usr/bin/env python3
"""Endurance-session ANOVA: two arbitrary ALL.TXT-format decode logs, generic labels.

USE THIS SCRIPT for any matched-decode comparison that isn't "OpenWSFZ vs jt9" or
"OpenWSFZ vs the live WSJT-X application" -- those two have their own dedicated,
purpose-documented entry points (endurance_anova_jt9.py, endurance_anova_wsjtx.py). The
case this was written for (2026-08-02): comparing two OpenWSFZ instances against each
other (8080/FT-991A vs 8081/SDR Uno, same split antenna, same decoder, different receiver
hardware and audio chain) -- isolating the hardware/capture-chain variable the two
WSJT-X-side reports (anova_report_8080_vs_wsjtx.md / anova_report_8081_vs_wsjtx.md) can't
cleanly separate on their own, since each of those also changes decoder identity for one
side. Works for any two ALL.TXT-format files with arbitrary display labels -- no
"OpenWSFZ"/"WSJT-X" assumption baked in anywhere, unlike the other two scripts.

Both inputs are parsed as already-complete decode logs, exactly like
endurance_anova_wsjtx.py -- no re-decoding, no jt9, no WAV directory needed. Reuses every
other bit of shared machinery (parsing, Part-matching, the two-way-ANOVA-without-
replication design, chart rendering, report rendering) from anova_common.py; see that
module's docstring for the full design rationale.

--method-note is REQUIRED (not optional, unlike endurance_anova_wsjtx.py's overridable
default) -- this script has no way to guess what relationship the two inputs actually
have to each other, and a wrong assumed method note is worse than none at all (the exact
mistake found live 2026-08-02 in endurance_anova_wsjtx.py's hardcoded "same physical radio
feed" text when pointed at a cross-hardware pair).

NFR-021: message text (real third-party callsigns) is read only to build the match key; it
is never printed to stdout/stderr and never written to any output file. Only aggregate
counts and statistics reach the rendered report.

Usage:
    python endurance_anova_two_alltxt.py \\
        --a-all-txt artefacts/20260731_live_run_2004-8080/owsfz/ALL.TXT --a-label "OpenWSFZ-8080" \\
        --b-all-txt artefacts/20260731_live_run_2004-8081/owsfz/ALL.TXT --b-label "OpenWSFZ-8081" \\
        --out anova_report_8080_vs_8081.md \\
        --run-label "..." --method-note "..."
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys

import anova_common as ac

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a-all-txt", required=True, help="Path to appraiser A's ALL.TXT.")
    ap.add_argument("--a-label", required=True, help="Display label for appraiser A.")
    ap.add_argument("--b-all-txt", required=True, help="Path to appraiser B's ALL.TXT.")
    ap.add_argument("--b-label", required=True, help="Display label for appraiser B.")
    ap.add_argument("--out", required=True, help="Output path for anova_report.md")
    ap.add_argument("--run-label", default=None)
    ap.add_argument("--method-note", required=True,
                     help="REQUIRED -- describes the actual relationship between the two "
                          "inputs (same/different hardware, same/different decoder, "
                          "same/different antenna feed, etc). No default is provided; see "
                          "module docstring for why.")
    ap.add_argument("--start", help="Restrict both files to this window's start "
                                     "(HH:MM[:SS], or 'YYYY-MM-DD HH:MM[:SS]').")
    ap.add_argument("--end", help="Same formats as --start.")
    ap.add_argument("--date", help="Date (YYYYMMDD) to combine with a bare HH:MM "
                                    "--start/--end. Default: today.")
    ap.add_argument("--a-snap-grid", action="store_true",
                     help="Grid-snap appraiser A's timestamps (floor to the enclosing 15s "
                          "FT8 boundary) before matching. Opt-in only -- see the 2026-08-02 "
                          "grid-artefact correction. The gate is always run and reported "
                          "regardless of this flag.")
    ap.add_argument("--b-snap-grid", action="store_true",
                     help="Same as --a-snap-grid, for appraiser B.")
    ap.add_argument("--stratum", type=int, default=None,
                     help="After matching, keep only pairs whose snapped side's ORIGINAL "
                          "(pre-snap) offset equals this many seconds. Requires --a-snap-"
                          "grid or --b-snap-grid. Omitting this while snapping is active "
                          "renders a per-stratum breakdown instead of a pooled ANOVA table.")
    args = ap.parse_args()

    if args.stratum is not None and not (args.a_snap_grid or args.b_snap_grid):
        print("[ERROR] --stratum requires --a-snap-grid or --b-snap-grid (nothing to "
              "stratify by otherwise)", file=sys.stderr)
        return 2

    if not os.path.isfile(args.a_all_txt):
        print(f"[ERROR] {args.a_all_txt} not found", file=sys.stderr)
        return 2
    if not os.path.isfile(args.b_all_txt):
        print(f"[ERROR] {args.b_all_txt} not found", file=sys.stderr)
        return 2

    start = ac.parse_time_arg(args.start, args.date) if args.start else None
    end = ac.parse_time_arg(args.end, args.date) if args.end else None
    if start and end and end < start:
        print(f"[ERROR] --end ({end}) is before --start ({start})", file=sys.stderr)
        return 2

    a_rows_raw = ac.filter_rows_by_window(ac.parse_all_txt(args.a_all_txt), start, end)
    b_rows_raw = ac.filter_rows_by_window(ac.parse_all_txt(args.b_all_txt), start, end)
    print(f"{args.a_label} decodes in window: {len(a_rows_raw)}")
    print(f"{args.b_label} decodes in window: {len(b_rows_raw)}")

    gate_a = ac.compute_grid_gate(a_rows_raw)
    gate_b = ac.compute_grid_gate(b_rows_raw)
    print(f"grid gate -- {args.a_label}: G={gate_a['g']:.4f} (ROW {gate_a['row']}, {gate_a['verdict']})")
    print(f"grid gate -- {args.b_label}: G={gate_b['g']:.4f} (ROW {gate_b['row']}, {gate_b['verdict']})")

    a_rows = ac.apply_grid_snap(a_rows_raw) if args.a_snap_grid else a_rows_raw
    b_rows = ac.apply_grid_snap(b_rows_raw) if args.b_snap_grid else b_rows_raw

    pairs = ac.match_pairs(a_rows, b_rows)
    print(f"matched pairs: {len(pairs)}")

    stratum_label = ""
    unstratified_snap = False
    if args.stratum is not None:
        side = "a" if args.a_snap_grid else "b"
        before = len(pairs)
        pairs = [p for p in pairs if p.get(f"{side}_offset") == args.stratum]
        print(f"stratum filter: +{args.stratum}s only -- {len(pairs)}/{before} pairs kept")
        stratum_label = f" -- GRID-SNAPPED, +{args.stratum}s STRATUM ONLY"
    elif args.a_snap_grid or args.b_snap_grid:
        stratum_label = " -- GRID-SNAPPED, ALL STRATA (see breakdown, do not cite a pooled number)"
        unstratified_snap = True

    window_note = f" ({start} -> {end})" if (start or end) else ""
    run_label = (args.run_label or (
        f"{args.a_all_txt} vs {args.b_all_txt}{window_note}"
    )) + stratum_label
    meta = {
        "run_label": run_label,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "a_label": args.a_label,
        "b_label": args.b_label,
        "n_a": len(a_rows_raw),
        "n_b": len(b_rows_raw),
        "n_pairs": len(pairs),
        "method_note": args.method_note,
    }

    out_dir = os.path.dirname(os.path.abspath(args.out)) or "."
    out_stem = os.path.splitext(os.path.basename(args.out))[0]

    gate_section = ac.render_gate_section(gate_a, args.a_label, gate_b, args.b_label)

    if unstratified_snap:
        side = "a" if args.a_snap_grid else "b"
        report = gate_section + ac.render_report([], meta).rsplit("## Caveat", 1)[0]
        report += ac.render_stratum_breakdown(pairs, side, args.a_label, args.b_label)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(report)
        print(f"wrote {args.out} (coverage + per-stratum breakdown, no pooled ANOVA)")
        ac.render_markdown_html(args.out)
        return 0

    response_results = ac.run_responses(pairs, out_dir, out_stem, args.a_label, args.b_label)

    report = gate_section + ac.render_report(response_results, meta)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(report)
    print(f"wrote {args.out}")
    ac.render_markdown_html(args.out)
    for resp, _stats, chart_files in response_results:
        if chart_files[0]:
            print(f"wrote {os.path.join(out_dir, chart_files[0])}")
            print(f"wrote {os.path.join(out_dir, chart_files[1])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
