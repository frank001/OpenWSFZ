#!/usr/bin/env python3
"""R0 (reproducible-native-build) AC-1 / AC-2 replay.

Decodes a >=200-contiguous-cycle subset of the pinned 20m corpus
(artefacts/20260808_live_run_0016-8080/wsjt-x/wav) through a given libft8.dll
and serialises the per-cycle decode output to JSON, in replay order.

Usage:
    python r0_ac1_ac2_replay.py --dll-path PATH --dll-sha256 SHA --out OUT.json
                                 [--n-cycles 250] [--start-index 0]

Two runs' JSON outputs are diffed mechanically by r0_ac1_ac2_diff.py -- this
script only produces one run's serialised output. Reuses p23_common's
Decoder/read_wav/normalise_rms/in_window_files (same production preprocessing
and decode-params pipeline the rest of the D-001 programme already runs on),
but does NOT use p23_common's DLL_SHA256 pin (that pin identifies the
d001-rc4-decode-depth unmerged three-pass build, not any binary this change
is comparing) -- the SHA to verify against is supplied explicitly by the
caller for each of the two DLLs under comparison.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import p23_common as P  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll-path", required=True)
    ap.add_argument("--dll-sha256", required=True,
                     help="Expected SHA256 of --dll-path; run refuses on mismatch (D4).")
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-cycles", type=int, default=250)
    ap.add_argument("--start-index", type=int, default=0)
    args = ap.parse_args()

    files = P.in_window_files()  # WINDOW_20M default, sorted chronologically
    subset = files[args.start_index: args.start_index + args.n_cycles]
    if len(subset) < args.n_cycles:
        print("REFUSED: only %d files available from start-index %d, need %d"
              % (len(subset), args.start_index, args.n_cycles), file=sys.stderr)
        sys.exit(2)

    # D4/--assert-dll-sha (task 5.3): self-verify via the harness's own pinning capability
    # rather than trusting whatever binary happens to be on disk at --dll-path. check_version
    # is deliberately off: this script compares DLLs across shim versions by design (baseline
    # 20260038 vs the R0 candidate 20260039) -- SHA256 is the actual identity check.
    try:
        dec = P.Decoder(path=args.dll_path, verify=True, expected_sha256=args.dll_sha256,
                         check_version=False)
    except RuntimeError as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        sys.exit(2)
    got = P.dll_sha256(args.dll_path)

    cycles = []
    for ts, path in subset:
        pcm = P.read_wav(path)
        pcm = P.normalise_rms(pcm, P.PROD_TARGET_RMS)
        results = dec.decode(pcm)
        cycles.append({
            "ts": ts,
            "results": results if results is not None else "AV_CAUGHT",
        })

    out = {
        "dll_path": os.path.abspath(args.dll_path),
        "dll_sha256": got,
        "shim_version": dec.version,
        "window": "WINDOW_20M",
        "start_index": args.start_index,
        "n_cycles": args.n_cycles,
        "first_ts": subset[0][0],
        "last_ts": subset[-1][0],
        "cycles": cycles,
    }
    P.write_json(args.out, out)
    print("WROTE %s (%d cycles, %s .. %s, dll_sha256=%s..., shim=%d)"
          % (args.out, len(cycles), subset[0][0], subset[-1][0], got[:16], dec.version))


if __name__ == "__main__":
    main()
