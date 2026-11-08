#!/usr/bin/env python3
"""Cycle-stamp duplicate counter for the #266 live check (K2, QA).

Reads a daemon log and reports COUNTS ONLY (NFR-021 / HK-037: no message text leaves the reading function):

  windows            number of 'Window emitted (... cycle HH:MM:SS)' lines
  distinct_stamps    number of distinct cycle stamps among them
  duplicated_stamps  number of distinct stamps that occur two or more times      <- the L1 quantity
  extra_windows      windows minus distinct stamps (a window whose stamp was already emitted)
  framer_starts      number of 'CycleFramer started' lines
  pipeline_starts    number of 'Starting FT8 pipeline' lines
  pipeline_started   number of 'Pipeline started on' lines (R5; 0 on builds before the fix)
  pipeline_stopped   number of 'Pipeline stopped (reason' lines (R5)
  clamps             number of 'Cycle-grid realignment clamped' lines
  decodes_per_cycle  list of N from 'Cycle <time>: N decode(s) found' lines, in order (counts, not text)

Usage:  python -I dup_stamp_counter.py <logfile> [--after-line N] [--json]
Stdlib only. Read-only. Never prints a log line.
"""
import json
import re
import sys

WINDOW = re.compile(r"Window emitted \(\d+ samples, cycle (\d{2}:\d{2}:\d{2})\)")
DECODE = re.compile(r"Cycle \S+: (\d+) decode\(s\) found")


def count(path, after_line=0):
    stamps = []
    out = dict(framer_starts=0, pipeline_starts=0, pipeline_started=0, pipeline_stopped=0, clamps=0)
    decodes = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for n, line in enumerate(fh, 1):
            if n <= after_line:
                continue
            m = WINDOW.search(line)
            if m:
                stamps.append(m.group(1))
                continue
            d = DECODE.search(line)
            if d:
                decodes.append(int(d.group(1)))
                continue
            if "CycleFramer started" in line:
                out["framer_starts"] += 1
            elif "Starting FT8 pipeline" in line:
                out["pipeline_starts"] += 1
            elif "Pipeline started on" in line:
                out["pipeline_started"] += 1
            elif "Pipeline stopped (reason" in line:
                out["pipeline_stopped"] += 1
            elif "Cycle-grid realignment clamped" in line:
                out["clamps"] += 1
    seen = {}
    for s in stamps:
        seen[s] = seen.get(s, 0) + 1
    out.update(
        windows=len(stamps),
        distinct_stamps=len(seen),
        duplicated_stamps=sum(1 for v in seen.values() if v >= 2),
        extra_windows=len(stamps) - len(seen),
        decodes_per_cycle=decodes,
    )
    return out


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    after = 0
    if "--after-line" in argv:
        after = int(argv[argv.index("--after-line") + 1])
    res = count(argv[1], after)
    if "--json" in argv:
        print(json.dumps(res))
    else:
        for k, v in res.items():
            if k == "decodes_per_cycle":
                print(f"{k}: n={len(v)} total={sum(v)} first10={v[:10]}")
            else:
                print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
