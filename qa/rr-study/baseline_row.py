"""Compute a run's Section 6 (historical trend) row from the run's own files. Counts and rates only.

    python baseline_row.py results/<run-dir> [--label TEXT]

Reads report.md (analyser output: %GR&R per stage, S5 Gate A / Check B, S7 'all', S8 overall) and
S7_matched.csv / S8_matched.csv (the pooled OpenWSFZ-as-%-of-WSJT-X column; matched=True and not a
false positive). Prints a markdown table row in the format of the existing Section 6 table.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


def pct_grr(text: str, stage: str) -> str:
    m = re.search(r"\|\s*%GR&R\s*\|\s*" + stage + r"\s*\|\s*([\d.]+)%", text)
    return f"{float(m.group(1)):.2f}%" if m else "n/a"


def matched_counts(run: Path):
    out = {"WSJT-X": 0, "OpenWSFZ": 0}
    for sc in ("S7", "S8"):
        with open(run / f"{sc}_matched.csv", newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r["matched"] == "True" and r["false_positive"] != "True" and r["appraiser"] in out:
                    out[r["appraiser"]] += 1
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--label", default=None)
    a = ap.parse_args()
    run = Path(a.run)
    t = (run / "report.md").read_text(encoding="utf-8")
    s7 = re.search(r"\|\s*\*\*all\*\*\s*\|\s*\*\*([\d.]+)%\*\*\s*\|\s*\*\*([\d.]+)%\*\*", t)
    s8 = re.search(r"\|\s*WSJT-X\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)%\s*\|\s*\|\s*OpenWSFZ\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)%", t.replace("\n", " "))
    ga = re.findall(r"\|\s*(WSJT-X|OpenWSFZ)\s*\|\s*(\d+) / (\d+)\s*\|\s*[\d.]+%\s*\|\s*[\d.]+%\s*\|\s*[\d.]+%\s*\|\s*INFO", t)
    cb = re.search(r"Check B.*?\|\s*WSJT-X\s*\|\s*(\d+) / (\d+)\s*\|.*?\|\s*OpenWSFZ\s*\|\s*(\d+) / (\d+)", t, re.S)
    gaw = re.search(r"Gate A-W\*\*[^|]*\|\s*(\d+)/(\d+) = ([\d.]+)%", t)
    mc = matched_counts(run)
    pooled = 100.0 * mc["OpenWSFZ"] / mc["WSJT-X"] if mc["WSJT-X"] else float("nan")
    fp = {d: f"{n}/{s}" for d, n, s in ga}
    row = {
        "label": a.label or run.name,
        "s1": pct_grr(t, "S1"), "s2": pct_grr(t, "S2"), "s3": pct_grr(t, "S3"),
        "s5": f"{fp.get('WSJT-X', '?')} / {fp.get('OpenWSFZ', '?')} (Gate A-W {gaw.group(1)}/{gaw.group(2)})" if gaw else "?",
        "checkb": f"{cb.group(1)}/{cb.group(2)} / {cb.group(3)}/{cb.group(4)}" if cb else "?",
        "s7": f"{s7.group(1)}% / {s7.group(2)}%" if s7 else "?",
        "s8": f"{s8.group(3)}% / {s8.group(6)}%" if s8 else "?",
        "pooled": f"{pooled:.2f}% ({mc['OpenWSFZ']}/{mc['WSJT-X']})",
    }
    print(row)


if __name__ == "__main__":
    main()
