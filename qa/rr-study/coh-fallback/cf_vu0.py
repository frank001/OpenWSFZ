#!/usr/bin/env python3
"""COH-FALLBACK step 3, validity row V-U0 (spec section 11, A11.3): the Stage 2 build's OWN OFF arm, on the frozen selection, must decode exactly what `main` 5229beec decoded.
Per cycle, the multiset of (batch kind, freq, dt, snr) of the Stage 2 OFF arm (outcomes file, 7th field = path ignored) equals the multiset of the main OFF arm (outcomes_OFF.csv, no path field).
N/N  => the frozen U_max (0.078) stands.   Any differing cycle => V-U0 FAILS: U_max is re-frozen from the Stage 2 OFF arm by the same rule, in a dated note, BEFORE any ON decode.
Also reports: cycle sets equal, the number of differing cycles, and the first few stamps. Numbers only.
  python cf_vu0.py <main outcomes_OFF.csv> <stage2 outcomes.csv> <out json>
"""
import collections
import csv
import json
import sys


def load(path):
    d = collections.defaultdict(collections.Counter)
    for row in csv.reader(open(path, newline="", encoding="utf-8")):
        if len(row) < 6:
            continue
        stamp, kind, _idx, freq, dt, snr = row[:6]                  # the 7th field (path, or the text hash if asked for) is not compared
        d[stamp][(kind, freq, dt, snr)] += 1
    return d


def main():
    a, b, out = sys.argv[1:4]
    main_off, s2_off = load(a), load(b)
    stamps = sorted(set(main_off) | set(s2_off))
    diff = [s for s in stamps if main_off.get(s, collections.Counter()) != s2_off.get(s, collections.Counter())]
    res = {"cycles_main": len(main_off), "cycles_stage2": len(s2_off), "cycle_sets_equal": set(main_off) == set(s2_off), "differing_cycles": len(diff),
           "first_differing": diff[:10], "decodes_main": sum(sum(c.values()) for c in main_off.values()), "decodes_stage2": sum(sum(c.values()) for c in s2_off.values()),
           "V-U0": "PASS" if (not diff and set(main_off) == set(s2_off) and len(main_off) > 0) else "FAIL"}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
