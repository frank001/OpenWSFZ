#!/usr/bin/env python3
"""Endurance-session ANOVA: OpenWSFZ vs the real WSJT-X application's own ALL.TXT.

USE THIS SCRIPT WHEN A REAL WSJT-X APPLICATION HAS BEEN RUNNING THE WHOLE SESSION ON THE
SAME PHYSICAL/AUDIO FEED as the OpenWSFZ instance you're analysing (true for the 40m
instance in this repo's live-run setup). WSJT-X's own ALL.TXT is already a complete decode
log for the session -- there is nothing to re-decode. This script just parses both
already-existing ALL.TXT files and runs the same matched-Part ANOVA as
endurance_anova_jt9.py, with no jt9 invocation, no WAV directory, and no subprocess calls
at all -- it should complete in well under a second even for a 24h session.

If there is NO live WSJT-X application covering the feed you're analysing (e.g. an SDR-fed
instance retuned across bands with no WSJT-X of its own), use endurance_anova_jt9.py
instead, which re-decodes the archived WAVs via jt9 to obtain a second appraiser's opinion
-- there's no live log to read in that case.

Split 2026-07-30 (Captain's instruction) from a single endurance_anova.py that used jt9
for both cases; see anova_common.py's module docstring for the full rationale. Re-decoding
~24h of archived WAVs through jt9 to reproduce data WSJT-X's own ALL.TXT already has on
disk was identified as pure waste -- this script is the fix.

RECOMMENDED INPUTS: the two ALL.TXT files produced by
tools/gather_live_run_artefacts.py's own session-window filtering
(artefacts/<run>/owsfz/ALL.TXT and artefacts/<run>/wsjt-x/ALL.TXT) -- both are already
restricted to the session's actual time window, so this script needs no further
filtering. Pointing it at the LIVE, still-growing ALL.TXT files directly also works; pass
--start/--end (same formats as the gather script) if you need to restrict to a sub-window
yourself in that case.

NFR-021: message text (real third-party callsigns) is read only to build the match key; it
is never printed to stdout/stderr and never written to any output file. Only aggregate
counts and statistics reach the rendered report.

Usage:
    # Normal case: point at the already-gathered, already-windowed session artefacts.
    python endurance_anova_wsjtx.py \\
        --ours-all-txt artefacts/20260730_live_run_1821-8080/owsfz/ALL.TXT \\
        --wsjtx-all-txt artefacts/20260730_live_run_1821-8080/wsjt-x/ALL.TXT \\
        --out artefacts/20260730_live_run_1821-8080/anova_report.md \\
        --run-label "2026-07-30 40m endurance (OpenWSFZ vs live WSJT-X)"

    # Standalone against the live files, restricted to a sub-window:
    python endurance_anova_wsjtx.py \\
        --ours-all-txt D:/Projects/claude/OpenWSFZ-40m-capture/ALL.TXT \\
        --wsjtx-all-txt C:/Users/Frank/AppData/Local/WSJT-X/ALL.TXT \\
        --start "2026-07-29 18:21" --end "2026-07-30 18:21" \\
        --out anova_report.md
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
    ap.add_argument("--ours-all-txt", required=True,
                     help="Path to OpenWSFZ's ALL.TXT (ideally the session-windowed copy "
                          "from tools/gather_live_run_artefacts.py's owsfz/ALL.TXT).")
    ap.add_argument("--wsjtx-all-txt", required=True,
                     help="Path to the real WSJT-X application's ALL.TXT (ideally the "
                          "session-windowed copy from wsjt-x/ALL.TXT).")
    ap.add_argument("--out", required=True, help="Output path for anova_report.md")
    ap.add_argument("--run-label", default=None)
    ap.add_argument("--start", help="Restrict both files to this window's start "
                                     "(HH:MM[:SS], or 'YYYY-MM-DD HH:MM[:SS]'). Only "
                                     "needed when pointing at live, not pre-gathered, "
                                     "ALL.TXT files -- an already-gathered pair needs no "
                                     "further filtering.")
    ap.add_argument("--end", help="Same formats as --start.")
    ap.add_argument("--date", help="Date (YYYYMMDD) to combine with a bare HH:MM "
                                    "--start/--end. Default: today.")
    ap.add_argument("--method-note", default=None,
                     help="Override the report's default method_note sentence, which "
                          "assumes both appraisers hear the SAME physical radio hardware. "
                          "That's true for a single-receiver leader/follower pairing but "
                          "false for a split-antenna, different-receiver comparison (e.g. "
                          "OpenWSFZ on an SDR-fed instance vs a WSJT-X instance on a "
                          "separate radio sharing only the antenna) -- pass an accurate "
                          "note in that case rather than letting the default overstate "
                          "how identical the two feeds actually are (Captain/QA, "
                          "2026-08-02, multi-day 8080/8081 live run).")
    ap.add_argument("--a-snap-grid", action="store_true",
                     help="Grid-snap OpenWSFZ's timestamps (floor to the enclosing 15s FT8 "
                          "boundary) before matching. Opt-in only -- see the 2026-08-02 "
                          "grid-artefact correction for why this exists. The gate "
                          "(compute_grid_gate) is always run and reported regardless of "
                          "this flag; use it to decide whether snapping is even needed.")
    ap.add_argument("--b-snap-grid", action="store_true",
                     help="Same as --a-snap-grid, for the WSJT-X side.")
    ap.add_argument("--stratum", type=int, default=None,
                     help="After matching, keep only pairs whose snapped side's ORIGINAL "
                          "(pre-snap) offset equals this many seconds (e.g. 0 for the "
                          "on-grid stratum). Requires --a-snap-grid or --b-snap-grid. "
                          "Omitting this while snapping is active is legal but the report "
                          "will show a per-stratum breakdown instead of a single pooled "
                          "ANOVA table -- pooling across drift strata is not allowed by "
                          "this script without an explicit acknowledgement via --stratum.")
    args = ap.parse_args()

    if args.stratum is not None and not (args.a_snap_grid or args.b_snap_grid):
        print("[ERROR] --stratum requires --a-snap-grid or --b-snap-grid (nothing to "
              "stratify by otherwise)", file=sys.stderr)
        return 2

    if not os.path.isfile(args.ours_all_txt):
        print(f"[ERROR] {args.ours_all_txt} not found", file=sys.stderr)
        return 2
    if not os.path.isfile(args.wsjtx_all_txt):
        print(f"[ERROR] {args.wsjtx_all_txt} not found", file=sys.stderr)
        return 2

    start = ac.parse_time_arg(args.start, args.date) if args.start else None
    end = ac.parse_time_arg(args.end, args.date) if args.end else None
    if start and end and end < start:
        print(f"[ERROR] --end ({end}) is before --start ({start})", file=sys.stderr)
        return 2

    ours_rows_raw = ac.filter_rows_by_window(ac.parse_all_txt(args.ours_all_txt), start, end)
    wsjtx_rows_raw = ac.filter_rows_by_window(ac.parse_all_txt(args.wsjtx_all_txt), start, end)
    print(f"OpenWSFZ decodes in window: {len(ours_rows_raw)}")
    print(f"WSJT-X decodes in window: {len(wsjtx_rows_raw)}")

    # Gate: always computed on the raw (pre-snap) rows and always reported, per the
    # 2026-08-02 correction's §6 ("run first and reported at the top of every output") --
    # independent of whether --a-snap-grid/--b-snap-grid were passed, so a caller always
    # knows whether pooling would have been safe without snapping at all.
    gate_a = ac.compute_grid_gate(ours_rows_raw)
    gate_b = ac.compute_grid_gate(wsjtx_rows_raw)
    print(f"grid gate -- OpenWSFZ: G={gate_a['g']:.4f} (ROW {gate_a['row']}, {gate_a['verdict']})")
    print(f"grid gate -- WSJT-X:   G={gate_b['g']:.4f} (ROW {gate_b['row']}, {gate_b['verdict']})")

    ours_rows = ac.apply_grid_snap(ours_rows_raw) if args.a_snap_grid else ours_rows_raw
    wsjtx_rows = ac.apply_grid_snap(wsjtx_rows_raw) if args.b_snap_grid else wsjtx_rows_raw

    pairs = ac.match_pairs(ours_rows, wsjtx_rows)
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
        f"{args.ours_all_txt} vs {args.wsjtx_all_txt}{window_note}"
    )) + stratum_label
    meta = {
        "run_label": run_label,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "a_label": "OpenWSFZ",
        "b_label": "WSJT-X",
        "n_a": len(ours_rows_raw),
        "n_b": len(wsjtx_rows_raw),
        "n_pairs": len(pairs),
        "method_note": args.method_note or (
            "Both appraisers' decode logs come from the same live session already on "
            "disk -- OpenWSFZ's own ALL.TXT and the real WSJT-X application's own "
            "ALL.TXT, both listening to the same physical radio feed throughout. No "
            "re-decoding was performed (contrast endurance_anova_jt9.py, used when there "
            "is no live third-party log to read)."
        ),
    }

    out_dir = os.path.dirname(os.path.abspath(args.out)) or "."
    out_stem = os.path.splitext(os.path.basename(args.out))[0]

    gate_section = ac.render_gate_section(gate_a, "OpenWSFZ", gate_b, "WSJT-X")

    if unstratified_snap:
        # Table-A shape: coverage is safe to pool (recall doesn't carry the same
        # cross-stratum-averaging trap SNR/DT/freq do), but no pooled ANOVA table is
        # rendered at all -- only the mandatory per-stratum breakdown, per the spec's rule.
        side = "a" if args.a_snap_grid else "b"
        coverage_meta = dict(meta)
        report = gate_section + ac.render_report([], coverage_meta).rsplit(
            "## Caveat", 1)[0]
        report += ac.render_stratum_breakdown(pairs, side, "OpenWSFZ", "WSJT-X")
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(report)
        print(f"wrote {args.out} (coverage + per-stratum breakdown, no pooled ANOVA)")
        ac.render_markdown_html(args.out)
        return 0

    response_results = ac.run_responses(pairs, out_dir, out_stem, "OpenWSFZ", "WSJT-X")

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
