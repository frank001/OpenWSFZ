#!/usr/bin/env python3
"""PASSBAND-140 ROW 0b fallback: K60 vs B60 tuple-identity check.

Spec (qa/rr-study/2026-09-14-1542-architect-to-qa-spec-g2b-140-passband-rearm.md)
section 3.2 ROW 0b: SHA(BASE) == 6b2e16a6991ae953... OR K60 and B60 give
identical full tuples (ts, freq_hz, dt, snr, message) on C2's first 500
cycles.

Context: the Developer's freshly-built BASE (rebuild_shim.bat, unedited tree,
2026-09-14) hashes to db31d351484046e9f2430e2536d68850c13adba9c7e74f6c911f96345a85627a,
NOT the pin (6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c).
Independently re-verified by QA (both DLLs re-hashed directly, this session).
The committed origin/main blob DOES match the pin (git show + sha256, also
re-verified independently). Likely cause: rebuild_shim.bat's link step has no
/Brepro; BOARD.md already records the link step as non-reproducible across
invocations. This script checks whether the mismatch is cosmetic (identical
decode behaviour) or substantive (a real tree/toolchain divergence), per the
spec's own fallback branch.

NFR-021: message text stays in memory; only counts and (ts, freq_hz, dt, snr)
are ever printed.
"""
from __future__ import annotations

import ctypes
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "live-gap-now"))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "cycleframer-alignment-replay"))

import corpus       # noqa: E402  (live-gap-now's own corpus module -- c2_cycles())
import p23_common    # noqa: E402

BIN_DIR = os.path.join(_HERE, "..", "..", "..", "artefacts", "passband-140", "bin")

K60_PATH = os.path.join(BIN_DIR, "libft8_K60_committed.dll")
K60_SHA = "6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c"

B60_PATH = os.path.join(BIN_DIR, "libft8_PB140_BASE_dev.dll")
B60_SHA = "db31d351484046e9f2430e2536d68850c13adba9c7e74f6c911f96345a85627a"

SHIM_VERSION = 20260050
N_CYCLES = 500


def load(path, sha):
    dec = p23_common.Decoder(
        path=path, verify=True, expected_sha256=sha,
        expected_shim_version=SHIM_VERSION, check_version=True)
    dec.dll.ft8_set_decode_params(10, ctypes.c_float(0.10), 60)
    return dec


def decode_all(dec, cycles, label):
    out = {}
    for i, (ts, wav_path) in enumerate(cycles):
        pcm = p23_common.read_wav(wav_path)
        pcm = p23_common.normalise_rms(pcm, p23_common.PROD_TARGET_RMS)
        results = dec.decode(pcm)
        out[ts] = results or []
        if (i + 1) % 100 == 0:
            print("[%s] %d/%d" % (label, i + 1, len(cycles)), flush=True)
    return out


def tuples(d):
    s = set()
    for ts, results in d.items():
        for r in results:
            s.add((ts, r["freq_hz"], round(r["dt"], 4), r["snr"], r["message"]))
    return s


def main():
    c2, dup_report = corpus.c2_cycles()
    first = c2[:N_CYCLES]
    print("C2 dup report: %s" % dup_report)
    print("decoding K60 (committed origin/main DLL, sha=%s...) over %d cycles"
          % (K60_SHA[:12], len(first)))
    k60 = load(K60_PATH, K60_SHA)
    k60_out = decode_all(k60, first, "K60")

    print("decoding B60 (Developer's fresh BASE build, sha=%s...) over %d cycles"
          % (B60_SHA[:12], len(first)))
    b60 = load(B60_PATH, B60_SHA)
    b60_out = decode_all(b60, first, "B60")

    tk, tb = tuples(k60_out), tuples(b60_out)
    only_k, only_b = tk - tb, tb - tk

    print()
    print("K60: %d cycles, %d decode tuples" % (len(k60_out), len(tk)))
    print("B60: %d cycles, %d decode tuples" % (len(b60_out), len(tb)))
    print("only in K60: %d" % len(only_k))
    print("only in B60: %d" % len(only_b))
    identical = not only_k and not only_b
    print("IDENTICAL:", identical)

    if not identical:
        print()
        print("first 10 only-in-K60 (ts, freq_hz, dt, snr -- message withheld, NFR-021):")
        for t in sorted(only_k)[:10]:
            print("  ts=%s freq=%s dt=%s snr=%s" % (t[0], t[1], t[2], t[3]))
        print("first 10 only-in-B60:")
        for t in sorted(only_b)[:10]:
            print("  ts=%s freq=%s dt=%s snr=%s" % (t[0], t[1], t[2], t[3]))

    return 0 if identical else 1


if __name__ == "__main__":
    sys.exit(main())
