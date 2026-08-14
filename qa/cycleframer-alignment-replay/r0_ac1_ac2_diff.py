#!/usr/bin/env python3
"""Mechanical diff of two r0_ac1_ac2_replay.py output files.

Exit 0 iff every cycle's decode output (same ts, same set of
(freq_hz, dt, snr, message) results, same order) is byte-identical between
the two runs. Any difference -> exit 1, and the specific differing cycles are
printed BEFORE any diagnosis is attempted (spec requirement -- do not adjust
vendored sources to force a match).

Usage: python r0_ac1_ac2_diff.py A.json B.json
"""
from __future__ import annotations

import json
import sys


def main():
    a_path, b_path = sys.argv[1], sys.argv[2]
    with open(a_path, encoding="utf-8") as fh:
        a = json.load(fh)
    with open(b_path, encoding="utf-8") as fh:
        b = json.load(fh)

    diffs = []
    if a["n_cycles"] != b["n_cycles"] or a["first_ts"] != b["first_ts"] or a["last_ts"] != b["last_ts"]:
        print("REFUSED: runs cover different cycle ranges -- A: %s..%s (%d), B: %s..%s (%d)"
              % (a["first_ts"], a["last_ts"], a["n_cycles"],
                 b["first_ts"], b["last_ts"], b["n_cycles"]))
        sys.exit(2)

    for ca, cb in zip(a["cycles"], b["cycles"]):
        if ca["ts"] != cb["ts"]:
            diffs.append(("ts-mismatch", ca["ts"], cb["ts"]))
            continue
        if ca["results"] != cb["results"]:
            diffs.append((ca["ts"], ca["results"], cb["results"]))

    print("=== %s ===" % a_path)
    print("  dll_sha256=%s shim=%s" % (a["dll_sha256"][:16], a["shim_version"]))
    print("=== %s ===" % b_path)
    print("  dll_sha256=%s shim=%s" % (b["dll_sha256"][:16], b["shim_version"]))
    print("n_cycles=%d range=%s..%s" % (a["n_cycles"], a["first_ts"], a["last_ts"]))

    if not diffs:
        print("RESULT: PASS -- zero differences across %d cycles" % a["n_cycles"])
        sys.exit(0)

    print("RESULT: FAIL -- %d cycle(s) differ:" % len(diffs))
    for ts, ra, rb in diffs:
        print("  ts=%s" % ts)
        print("    A: %s" % ra)
        print("    B: %s" % rb)
    sys.exit(1)


if __name__ == "__main__":
    main()
