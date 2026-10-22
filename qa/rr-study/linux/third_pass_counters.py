#!/usr/bin/env python3
"""Third pass (#240): per-sweep counters from a sweep's daemon log, computed ON sol, aggregates only (HK-037: counts and milliseconds, no message text).

    python3 - <daemon.stdout.log> < third_pass_counters.py        (pull-series.sh feeds it over ssh; nothing is deployed on sol)

Reads the 'Third pass: newDecodes=N elapsedMs=M outcome=O fittedSignals=F' lines (one per cycle in which pass 0 had decodes, written only when the decoder's
decoding depth is Deep) and prints, for the WHOLE sweep and for the LAST daemon (= the S6 pass-O daemon, the one the S6 figures belong to): the outcome counts,
the number STARTED (ran + abandoned + failed), the abandon share over started (Amendment 1, A1: started is the primary denominator), the wall time of the cycles
where it ran (median / p90 / max), and the batch-3 decode count. A sweep with the depth Normal prints 'no third-pass lines'.
"""
import re
import sys
from collections import Counter

LINE = re.compile(r"Third pass: newDecodes=(\d+) elapsedMs=(\d+) outcome=(ran|skipped-no-new|skipped-abandoned|abandoned|failed) fittedSignals=(\d+)")
START = "arecord stdout pipe enlarged"
path = sys.argv[1]
lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
starts = [i for i, x in enumerate(lines) if START in x]
last = starts[-1] if starts else 0


def summarise(label, chunk):
    recs = [m.groups() for m in (LINE.search(x) for x in chunk) if m]
    if not recs:
        print(f"third pass ({label}): no third-pass lines")
        return
    oc = Counter(r[2] for r in recs)
    started = oc["ran"] + oc["abandoned"] + oc["failed"]
    ms = sorted(int(r[1]) for r in recs if r[2] == "ran")
    q = lambda xs, f: xs[min(len(xs) - 1, int(f * len(xs)))] if xs else None
    new = sum(int(r[0]) for r in recs)
    share = "%.1f %%" % (100.0 * (oc["abandoned"] + oc["failed"]) / started) if started else "n/a"
    print(f"third pass ({label}): cycles with a line {len(recs)}; started {started}; outcomes {dict(oc)}; abandon+failed over started {share}; "
          f"raw new decodes {new}")
    if ms:
        print(f"  wall time where it ran: n={len(ms)} median={q(ms, .5)} ms p90={q(ms, .9)} ms max={ms[-1]} ms (bar for context: the 13 s cycle budget; sol T-REF 2026-10-18: median 1607, p90 2286, max 3189)")


summarise("whole sweep", lines)
summarise("LAST daemon = S6 pass O", lines[last:])
