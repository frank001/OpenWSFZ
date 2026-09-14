#!/usr/bin/env python3
"""PASSBAND-140 ROW 0e: determinism check.

Spec section 3.2 ROW 0e: B40r's full tuples equal B40's on C2's first 300
cycles, mechanically diffed. On failure: VOID (a paired contrast on a
non-deterministic instrument is noise).

Reads the two already-decoded JSONL legs (decode_leg.py output) rather than
re-decoding -- B40r IS B40 re-run on the first 300 cycles by construction
(same binary, same params, dll_pin.py LEGS table), so this is a pure diff.
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(_HERE, "..", "..", "..", "artefacts", "passband-140", "_out")

N_CYCLES = 300


def load_tuples(path, limit=None):
    out = []
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if limit and i >= limit:
                break
            rec = json.loads(line)
            ts = rec["ts"]
            for r in rec["results"]:
                out.append((ts, r["freq_hz"], round(r["dt"], 4), r["snr"], r["message"]))
    return out


def main():
    b40r_path = os.path.join(OUT_DIR, "B40r_C2.jsonl")
    b40_path = os.path.join(OUT_DIR, "B40_C2.jsonl")

    b40r = load_tuples(b40r_path)
    b40 = load_tuples(b40_path, limit=N_CYCLES)

    sb40r, sb40 = set(b40r), set(b40)
    only_r = sb40r - sb40
    only_b = sb40 - sb40r
    identical = not only_r and not only_b

    print("ROW 0e: B40r tuples=%d, B40(first %d cycles) tuples=%d" %
          (len(b40r), N_CYCLES, len(b40)))
    print("only in B40r=%d, only in B40=%d" % (len(only_r), len(only_b)))
    print("IDENTICAL:", identical)
    print("PASS" if identical else "VOID")
    return 0 if identical else 1


if __name__ == "__main__":
    sys.exit(main())
