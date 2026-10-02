#!/usr/bin/env python3
"""Step 5 (final) of the standard post-endurance-run routine -- promotes the reviewed,
aggregate-only report subset from the gitignored artefacts/<run>-gathered/ staging
directory into the TRACKED qa/endurance/results/<run>/, so reports reach GitHub instead of
sitting only in artefacts/ (Captain, 2026-09-26: "I would like to have the reports available
on github though").

Mirrors qa/rr-study/results/'s own tracked-with-exclusions convention (see .gitignore's
"Endurance run reports" section) rather than inventing a new pattern: the destination
directory is tracked by default, and only specific raw-data filenames/subdirectories are
excluded within it -- this script simply never copies those in the first place, and never
copies anything this script doesn't explicitly list (allow-list, not a deny-list -- a new,
unanticipated raw-data filename from a future tool version fails safe by not being copied,
rather than needing a new .gitignore rule to catch it).

NEVER copies: owsfz/, wsjt-x/ (raw ALL.TXT + WAVs), cycle-audio/, daemon-logs/, contents.md/
.html (the gatherer's own manifest, which self-declares "Not committed to VCS"), *.stdout.log/
*.stderr.log (operational logs, not reports).

Runs the same NFR-021 callsign scan RUNBOOK.md Sec.4.4 specifies (grep for the amateur-
callsign shape) over every .md/.html file it's about to copy, BEFORE copying -- refuses and
copies nothing if it finds a hit, per this project's own "never let it become the committer's
job to remember" rule (HK-037 spirit).

Usage:
    python publish_report.py --run-dir artefacts/<run>-gathered --dest-name <run-name>
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import sys

# Amateur-callsign shape, same regex RUNBOOK.md Sec.4.4 uses for its own pre-commit scan.
# A synthetic Q-prefix call (Q1ABC, Q2XYZ, ...) also matches this shape by design (it's
# built to look like a real callsign) -- so a hit here is not automatically a violation, it
# just means a human must look at the specific line before this ever ships. This script
# still refuses on any hit rather than trying to tell Q-prefix apart from real inline (the
# NFR-021 policy's own exceptions, PD2FZ and public figures, are equally not safe to
# auto-allow here).
CALLSIGN_RE = re.compile(r"\b[A-Z]{1,2}[0-9][A-Z]{1,3}\b")

# Allow-list, not a deny-list (see module docstring). Glob patterns, relative to --run-dir.
COMMITTABLE_GLOBS = [
    "FINAL_REPORT.md", "FINAL_REPORT.html", "FINAL_REPORT_dossier.html",
    "anova_report.md", "anova_report.html", "anova_report.meta.json",
    "anova_report_*.png",
    "spectrum_scan_*.png", "spectral_trace.png",
    "spectrum_scan.json", "spectrum_scan_summary.json", "findings.json",
    "snr_gap_mix*.py", "snr_gap_mix*_output.txt",
]


def scan_for_callsigns(paths: list[str]) -> list[tuple[str, int, str]]:
    """Returns (path, line_no, matched_token) for every hit -- the caller decides whether to
    print the token (only ever into a QA-facing refusal message on this operator's own
    machine, never into a committed file); this function itself commits nothing."""
    hits = []
    for p in paths:
        if p.endswith(".png"):
            continue  # binary; text scan doesn't apply
        with open(p, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                m = CALLSIGN_RE.search(line)
                if m:
                    hits.append((p, i, m.group(0)))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True, help="artefacts/<run>-gathered directory")
    ap.add_argument("--dest-name", required=True,
                     help="Destination directory name under qa/endurance/results/ "
                          "(usually the run's own date-based name, no '-gathered' suffix)")
    ap.add_argument("--force", action="store_true",
                     help="Overwrite an existing destination directory's matching files")
    a = ap.parse_args()

    run_dir = os.path.abspath(a.run_dir)
    if not os.path.isdir(run_dir):
        print(f"[ERROR] {run_dir} not found", file=sys.stderr)
        return 2

    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(os.path.dirname(here))  # qa/endurance -> qa -> repo root
    dest = os.path.join(repo_root, "qa", "endurance", "results", a.dest_name)

    to_copy = []
    for pattern in COMMITTABLE_GLOBS:
        to_copy.extend(sorted(glob.glob(os.path.join(run_dir, pattern))))
    to_copy = [p for p in to_copy if os.path.isfile(p)]
    if not to_copy:
        print(f"[ERROR] nothing matched the committable allow-list in {run_dir} -- "
              "has the standard pipeline actually run yet?", file=sys.stderr)
        return 2

    hits = scan_for_callsigns(to_copy)
    if hits:
        print("[REFUSED] possible callsign-shaped token(s) found -- nothing copied. "
              "Review each line by hand (a synthetic Q-prefix call also matches this shape "
              "by design, so a hit here is not automatically a violation, but this script "
              "does not try to tell the difference):", file=sys.stderr)
        for p, i, tok in hits:
            print(f"  {p}:{i}: {tok}", file=sys.stderr)
        return 1

    os.makedirs(dest, exist_ok=True)
    for src in to_copy:
        name = os.path.basename(src)
        dst = os.path.join(dest, name)
        if os.path.isfile(dst) and not a.force:
            print(f"[SKIP] {dst} already exists (pass --force to overwrite)", file=sys.stderr)
            continue
        shutil.copy2(src, dst)
        print(f"copied {name}")

    print(f"\n{len(to_copy)} file(s) considered, written to {dest}")
    print("NFR-021 scan: clean (no callsign-shaped token found in any .md/.html copied).")
    print("Next: git add the destination directory by path (never git add -A), review "
          "`git status`, then commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
