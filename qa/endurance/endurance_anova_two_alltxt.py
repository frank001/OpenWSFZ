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
    args = ap.parse_args()

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

    a_rows = ac.filter_rows_by_window(ac.parse_all_txt(args.a_all_txt), start, end)
    b_rows = ac.filter_rows_by_window(ac.parse_all_txt(args.b_all_txt), start, end)
    print(f"{args.a_label} decodes in window: {len(a_rows)}")
    print(f"{args.b_label} decodes in window: {len(b_rows)}")

    pairs = ac.match_pairs(a_rows, b_rows)
    print(f"matched pairs: {len(pairs)}")

    window_note = f" ({start} -> {end})" if (start or end) else ""
    run_label = args.run_label or (
        f"{args.a_all_txt} vs {args.b_all_txt}{window_note}"
    )
    meta = {
        "run_label": run_label,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "a_label": args.a_label,
        "b_label": args.b_label,
        "n_a": len(a_rows),
        "n_b": len(b_rows),
        "n_pairs": len(pairs),
        "method_note": args.method_note,
    }

    out_dir = os.path.dirname(os.path.abspath(args.out)) or "."
    out_stem = os.path.splitext(os.path.basename(args.out))[0]

    response_results = ac.run_responses(pairs, out_dir, out_stem, args.a_label, args.b_label)

    report = ac.render_report(response_results, meta)
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
