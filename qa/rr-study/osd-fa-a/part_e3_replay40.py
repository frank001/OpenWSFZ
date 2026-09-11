#!/usr/bin/env python3
"""OSD-FA-A E3 (Amendment 1 sec.5.3) -- the nhard=40 full-corpus replay leg.

The nhard=60 leg is NOT re-run: F-001 L3's own subject replay
(artefacts/2026-09-10-f001-l3-live-measurement/subject_20260050.json, SHA re-asserted
here) already IS a full-corpus decode at PRODUCTION DEFAULTS -- p23_common.Decoder's
own DECODE_PARAMS=(10,0.10,60), set unconditionally at construction (p23_common.py:111).
Same binary (6b2e16a6...4f85c, shim 20260050), same window
([260908_193645,260909_172200)), same 5,222-file population, same input contract
(p23_common.read_wav + normalise_rms(0.20) -- p23_common.py's own g3_h12_replay.py
caller). Reusing it (HK-018) instead of re-decoding cuts this leg's own runtime
roughly in half.

This script produces ONLY the nhard=40 leg, same harness mechanics as g3_h12_replay.py
(select_files for the sorted in-window population, p23_common.Decoder/read_wav/
normalise_rms) but with decode params overridden to (10,0.10,40) via
ft8_set_decode_params AFTER construction (p23_common.Decoder's own __init__ hard-codes
60; overridden once, before the first decode_all call, never mid-run -- same one-
setting-per-run scheme as Part A/B, disclosed as the OTHER of the two schemes the E1
acceptance ruling accepts).

NFR-021: message text held in memory only for wildcard matching -- never printed,
logged, or written. Output JSON goes under artefacts/ (blanket-gitignored, same
discipline as g3_h12_replay.py's own out_json).

Usage:
    python part_e3_replay40.py <wav_dir> <window_lo> <window_hi> <out_json>
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))

import p23_common as P  # noqa: E402
from g2_verification_replay import select_files  # noqa: E402

NHARD_TREATMENT = 40
K_MIN_SCORE_PASS2 = 10
OSD_CORR_THRESHOLD = 0.10

# p23_common.py's own module-level DLL_SHA256/SHIM_VERSION defaults (39aa1031...,
# 20260035) are STALE -- a different arm's own pin (D001-c4-min-score-sweep). Do NOT
# rely on them (g3_h12_replay.py's own build_decoder passes verify=False for the same
# reason). Pin explicitly to the current binary, matching every other leg in this arm.
DLL_PATH = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")
PINNED_SHA256 = "6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c"
PINNED_SHIM_VERSION = 20260050


def main() -> int:
    wav_dir, window_lo, window_hi, out_json = sys.argv[1:5]
    if not os.path.realpath(out_json).startswith(
            os.path.join(REPO_ROOT, "artefacts") + os.sep):
        raise SystemExit("refusing to write outside artefacts/ (NFR-021)")

    sha = P.dll_sha256(DLL_PATH)
    dec = P.Decoder(path=DLL_PATH, verify=True,
                     expected_sha256=PINNED_SHA256, expected_shim_version=PINNED_SHIM_VERSION)
    dec.dll.ft8_set_decode_params.argtypes = [ctypes.c_int, ctypes.c_float, ctypes.c_int]
    dec.dll.ft8_set_decode_params.restype = None
    dec.dll.ft8_set_decode_params(K_MIN_SCORE_PASS2, OSD_CORR_THRESHOLD, NHARD_TREATMENT)
    print(f"dll_sha256={sha[:16]}... shim={dec.version} nhard={NHARD_TREATMENT} "
          f"(overridden once, before the first decode -- never mid-run)", flush=True)

    files = select_files(wav_dir, window_lo, window_hi, 1, 0, allow_short=False)
    print(f"population: {len(files)} files, window=[{window_lo},{window_hi})", flush=True)

    per_file = []
    t0 = time.perf_counter()
    n_av = 0
    for idx, (ts, path) in enumerate(files):
        pcm = P.normalise_rms(P.read_wav(path), P.PROD_TARGET_RMS)
        res = dec.decode(pcm)
        if res is None:
            n_av += 1
            per_file.append({"ts": ts, "av": True, "decodes": []})
            continue
        per_file.append({
            "ts": ts, "av": False,
            "decodes": [{"f": r["freq_hz"], "dt": round(r["dt"], 3), "m": r["message"]}
                        for r in res],
        })
        if (idx + 1) % 500 == 0:
            print(f"  {idx + 1}/{len(files)} ({time.perf_counter() - t0:.0f}s)", flush=True)

    total_wall = time.perf_counter() - t0
    out = {
        "label": "E3-40", "dll_sha256": sha, "shim_version": dec.version,
        "nhard": NHARD_TREATMENT, "window": [window_lo, window_hi],
        "n_files": len(files), "n_av": n_av, "total_wall_s": total_wall,
        "per_file": per_file,
    }
    tmp = out_json + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f)
    os.replace(tmp, out_json)

    n_dec = sum(len(f["decodes"]) for f in per_file)
    print(f"DONE files={len(files)} av={n_av} decodes={n_dec} wall={total_wall:.0f}s "
          f"-> {out_json}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
