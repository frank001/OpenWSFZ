#!/usr/bin/env python3
"""P2 -- does the shipped PCM normalisation scale cost decodes?

Spec: 2026-08-09-0129-architect-to-qa-spec-p2-pcm-scale-and-p3-sublattice-shift-union.md

Seven legs, RMS +/-18 dB about production's 0.20 in 6 dB steps.  Points were
fixed from the waterfall's uint8 dB window BEFORE any recovery number existed.

Process-parallel by contiguous chronological partition (spec 1.1: the shim's
256-slot hash table is process-global, so threads would race; every scale for a
given file is decoded consecutively inside one worker so hash state is
common-mode across the legs).

Resumable: each partition checkpoints to the scratch dir and is skipped on
restart.  NFR-021: message text lives only in scratch, outside the repo.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p23_common as C  # noqa: E402

SCALES = [0.025, 0.05, 0.1, 0.20, 0.4, 0.8, 1.6]
PROD_IDX = SCALES.index(C.PROD_TARGET_RMS)

_DEC = None


def _worker_init():
    global _DEC
    _DEC = C.Decoder()


def _run_partition(args):
    idx, files, scratch = args
    out_path = os.path.join(scratch, "p2_part_%04d.json" % idx)
    if os.path.exists(out_path):
        try:
            with open(out_path, encoding="utf-8") as fh:
                json.load(fh)
            return out_path, True          # resumed
        except Exception:
            os.remove(out_path)
    legs = {str(s): [] for s in SCALES}
    av = 0
    for ts, path in files:
        try:
            raw = C.read_wav(path)
        except Exception:
            continue
        for s in SCALES:                    # all scales of THIS file, consecutively
            res = _DEC.decode(C.normalise_rms(raw, s))
            if res is None:
                av += 1
                continue
            for r in res:
                legs[str(s)].append([ts, r["message"], r["freq_hz"]])
    C.write_json(out_path, {"idx": idx, "n_files": len(files), "av": av, "legs": legs})
    return out_path, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--partitions", type=int, default=64)
    ap.add_argument("--limit", type=int, default=0, help="smoke test: first N files")
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    os.makedirs(a.scratch, exist_ok=True)
    t_start = time.time()

    sha = C.dll_sha256()
    print("DLL sha256: %s" % sha, flush=True)
    if sha != C.DLL_SHA256:
        raise SystemExit("DLL identity mismatch -- refusing to run")

    files = C.in_window_files()
    if a.limit:
        files = files[:a.limit]
    print("in-window files: %d" % len(files), flush=True)

    ref = C.load_ref()
    print("REF: %d" % len(ref), flush=True)

    n_parts = min(a.partitions, max(1, len(files)))
    chunks = [files[i::n_parts] for i in range(n_parts)]
    # contiguous, not strided, so each worker sees chronological order
    chunks, lo = [], 0
    per = (len(files) + n_parts - 1) // n_parts
    while lo < len(files):
        chunks.append(files[lo:lo + per])
        lo += per
    tasks = [(i, ch, a.scratch) for i, ch in enumerate(chunks)]

    print("partitions: %d, workers: %d" % (len(tasks), a.workers), flush=True)
    done = 0
    paths = []
    with Pool(processes=a.workers, initializer=_worker_init) as pool:
        for path, resumed in pool.imap_unordered(_run_partition, tasks):
            paths.append(path)
            done += 1
            print("  partition %d/%d %s (%.1f min elapsed)"
                  % (done, len(tasks), "RESUMED" if resumed else "done",
                     (time.time() - t_start) / 60.0), flush=True)

    # ── aggregate ────────────────────────────────────────────────────────────
    leg_keys = {str(s): set() for s in SCALES}
    av_total = 0
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        av_total += d.get("av", 0)
        for s, rows in d["legs"].items():
            for ts, msg, _f in rows:
                leg_keys[s].add((ts, msg))

    ref_keys = set(ref)
    n_ref = len(ref_keys)
    R = {s: 100.0 * len(leg_keys[s] & ref_keys) / n_ref for s in leg_keys}
    r_prod = R[str(C.PROD_TARGET_RMS)]
    s_star = max(R, key=lambda k: R[k])
    p_val = R[s_star] - r_prod
    spread = max(R.values()) - min(R.values())
    argmax_is_endpoint = s_star in (str(SCALES[0]), str(SCALES[-1]))

    # ── pre-registered gate, spec 2.3, transcribed verbatim ──────────────────
    def p2_row0():
        if len(files) < 800:
            return "ROW 0a", "n_cycles %d < 800" % len(files)
        if n_ref != C.REF_EXPECTED:
            return "ROW 0b", "REF %d != %d" % (n_ref, C.REF_EXPECTED)
        if not (45.0 <= r_prod <= 70.0):
            return "ROW 0c", "R(0.20) = %.2f outside [45,70]" % r_prod
        if spread < 1.0:
            return "ROW 0d", "max-min R = %.2f pp < 1.0" % spread
        if argmax_is_endpoint and p_val >= 0.5:
            return "ROW 0e", "argmax at endpoint %s with P = %.2f" % (s_star, p_val)
        return None, None

    def p2_gate(p):
        if p >= 2.0:
            return "ROW 1"
        if p <= 0.5:
            return "ROW 2"
        return "ROW 3"

    row0, reason = p2_row0()
    final = row0 if row0 else p2_gate(p_val)

    boot = C.cluster_bootstrap(
        ref, {"R_%s" % s: (leg_keys[s] & ref_keys) for s in leg_keys}, n_draws=1000)

    result = {
        "arm": "P2", "spec": "2026-08-09-0129-architect-to-qa-spec-p2-pcm-scale-"
                             "and-p3-sublattice-shift-union.md",
        "dll_sha256": sha, "shim_version": C.SHIM_VERSION,
        "decode_params": {"kMinScorePass2": C.DECODE_PARAMS[0],
                          "osdCorrThreshold": C.DECODE_PARAMS[1],
                          "osdNhardMax": C.DECODE_PARAMS[2]},
        "n_cycles": len(files), "REF": n_ref, "native_av_count": av_total,
        "scales": SCALES, "R_by_scale": R,
        "R_prod": r_prod, "s_star": s_star, "P": p_val, "spread": spread,
        "argmax_is_endpoint": argmax_is_endpoint,
        "n_decodes_by_scale": {s: len(v) for s, v in leg_keys.items()},
        "row0": row0, "row0_reason": reason, "final_row": final,
        "bootstrap": boot,
        "wall_clock_min": (time.time() - t_start) / 60.0,
        "workers": a.workers, "partitions": len(tasks),
    }
    C.write_json(a.out, result)
    print(json.dumps({k: v for k, v in result.items() if k != "bootstrap"},
                     indent=2, sort_keys=True), flush=True)
    print("FINAL ROW: %s" % final, flush=True)


if __name__ == "__main__":
    main()
