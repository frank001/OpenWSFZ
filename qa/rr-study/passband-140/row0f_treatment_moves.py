#!/usr/bin/env python3
"""PASSBAND-140 ROW 0f: the treatment moves (HK-021(q)), as amended.

Spec section 3.2 ROW 0f, as revised by Amendment 1 (both edges now in scope,
per the Architect's amendment message): W40's C2 output != B40's; W40 emits
>=1 post-chain decode with freq_hz < 200 on C2 AND >=1 post-chain decode
with freq_hz > 2959 on C2; B40 emits 0 of either. On failure: STOP (the
wrong DLL loaded, or f_min/f_max never reached the waterfall). Paste one
W40 decode's (ts, freq_hz, snr) per edge into the report as the exhibit
(no message text, NFR-021).
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(_HERE, "..", "..", "..", "artefacts", "passband-140", "_out")

LOW_EDGE_HZ = 200   # < 200 Hz = below the OLD f_min (new band, low edge)
HIGH_EDGE_HZ = 2959  # > 2959 Hz = above the true 8-tone top base tone at the OLD f_max


def load(path):
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            ts = rec["ts"]
            for r in rec["results"]:
                out.append((ts, r["freq_hz"], r["snr"]))
    return out


def main():
    b40 = load(os.path.join(OUT_DIR, "B40_C2_chained.jsonl"))
    w40 = load(os.path.join(OUT_DIR, "W40_C2_chained.jsonl"))

    b40_low = [t for t in b40 if t[1] < LOW_EDGE_HZ]
    b40_high = [t for t in b40 if t[1] > HIGH_EDGE_HZ]
    w40_low = [t for t in w40 if t[1] < LOW_EDGE_HZ]
    w40_high = [t for t in w40 if t[1] > HIGH_EDGE_HZ]

    print("B40 (post-chain, C2): %d decodes total, %d < %dHz, %d > %dHz" %
          (len(b40), len(b40_low), LOW_EDGE_HZ, len(b40_high), HIGH_EDGE_HZ))
    print("W40 (post-chain, C2): %d decodes total, %d < %dHz, %d > %dHz" %
          (len(w40), len(w40_low), LOW_EDGE_HZ, len(w40_high), HIGH_EDGE_HZ))

    b40_zero_both_edges = (len(b40_low) == 0 and len(b40_high) == 0)
    w40_moves_both_edges = (len(w40_low) >= 1 and len(w40_high) >= 1)
    outputs_differ = set(b40) != set(w40)

    passed = b40_zero_both_edges and w40_moves_both_edges and outputs_differ

    print()
    print("B40 emits 0 outside [200,2959]:", b40_zero_both_edges)
    print("W40 emits >=1 below 200 AND >=1 above 2959:", w40_moves_both_edges)
    print("W40 output != B40 output:", outputs_differ)
    print("ROW 0f:", "PASS" if passed else "STOP")

    if w40_low:
        ts, freq, snr = sorted(w40_low)[0]
        print("exhibit (low edge): ts=%s freq_hz=%s snr=%s" % (ts, freq, snr))
    if w40_high:
        ts, freq, snr = sorted(w40_high, key=lambda t: -t[1])[0]
        print("exhibit (high edge): ts=%s freq_hz=%s snr=%s" % (ts, freq, snr))

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
