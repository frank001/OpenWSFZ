#!/usr/bin/env python3
"""P3 -- does sub-lattice placement cost decodes?

Spec: 2026-08-09-0129-architect-to-qa-spec-p2-pcm-scale-and-p3-sublattice-shift-union.md

Five legs on identical audio: base, +/-1.0417 Hz (= 3.125/3), +/-0.0267 s
(= 0.08/3, 320 samples).  Union the decodes and ask how much of REF only the
shifted copies recover.  S_time is the point -- the time axis is not
identifiable from ALL.TXT at all, so nothing has ever measured it.

ROW 0d shift control runs FIRST (spec 3.3).  DEVIATION FROM SPEC, disclosed:
the spec proposed a synthetic signal from qa/rr-study/synth.  This implements
the control on REAL audio instead -- decode a file unshifted and shifted, match
messages decoded in both, and require the mean change in reported freq_hz to
equal the applied shift within 0.25 Hz.  Same purpose, same tolerance, and it
exercises the actual signal path rather than an encoder oracle.  Both the
deviation and the measured value go in the report.

Process-parallel by contiguous partition; every leg of a given file is decoded
consecutively in one worker so hash-table state is common-mode (spec 1.1).
NFR-021: message text lives only in scratch, outside the repo.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p23_common as C  # noqa: E402

FREQ_DELTA = 3.125 / 3.0        # 1.041666... Hz
TIME_SAMPLES = 320              # 0.08/3 s at 12 kHz = 0.02667 s
LEGS = ["base", "Fp", "Fm", "Tp", "Tm"]

_DEC = None


def _worker_init():
    global _DEC
    _DEC = C.Decoder()


def _variants(pcm):
    return {
        "base": pcm,
        "Fp": C.freq_shift(pcm, +FREQ_DELTA),
        "Fm": C.freq_shift(pcm, -FREQ_DELTA),
        "Tp": C.time_shift(pcm, +TIME_SAMPLES),
        "Tm": C.time_shift(pcm, -TIME_SAMPLES),
    }


def _run_partition(args):
    idx, files, scratch = args
    out_path = os.path.join(scratch, "p3_part_%04d.json" % idx)
    if os.path.exists(out_path):
        try:
            with open(out_path, encoding="utf-8") as fh:
                json.load(fh)
            return out_path, True
        except Exception:
            os.remove(out_path)
    legs = {lg: [] for lg in LEGS}
    av = 0
    seen_ts = []
    for ts, path in files:
        try:
            pcm = C.normalise_rms(C.read_wav(path), C.PROD_TARGET_RMS)
        except Exception:
            continue
        seen_ts.append(ts)
        for lg, buf in _variants(pcm).items():   # all legs of THIS file, consecutively
            res = _DEC.decode(buf)
            if res is None:
                av += 1
                continue
            for r in res:
                legs[lg].append([ts, r["message"], r["freq_hz"]])
    C.write_json(out_path, {"idx": idx, "n_files": len(files), "av": av,
                            "seen_ts": seen_ts, "legs": legs})
    return out_path, False


def shift_control(files, n=20):
    """ROW 0d pre-flight on real audio. Returns (mean_delta_hz, n_matched)."""
    dec = C.Decoder()
    deltas = []
    for ts, path in files[:n]:
        pcm = C.normalise_rms(C.read_wav(path), C.PROD_TARGET_RMS)
        a = dec.decode(pcm)
        b = dec.decode(C.freq_shift(pcm, +FREQ_DELTA))
        if not a or not b:
            continue
        fa = {r["message"]: r["freq_hz"] for r in a}
        fb = {r["message"]: r["freq_hz"] for r in b}
        for m in fa.keys() & fb.keys():
            deltas.append(fb[m] - fa[m])
    if not deltas:
        return None, 0
    return float(np.mean(deltas)), len(deltas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--partitions", type=int, default=64)
    ap.add_argument("--limit", type=int, default=0)
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

    print("ROW 0d shift control (real audio, %.4f Hz applied)..." % FREQ_DELTA, flush=True)
    ctl_mean, ctl_n = shift_control(files)
    ctl_err = abs((ctl_mean if ctl_mean is not None else 99.0) - FREQ_DELTA)
    print("  mean reported delta = %s Hz over %d matched messages, error %.4f Hz"
          % ("%.4f" % ctl_mean if ctl_mean is not None else "None", ctl_n, ctl_err),
          flush=True)

    ref = C.load_ref()
    print("REF: %d" % len(ref), flush=True)

    per = (len(files) + a.partitions - 1) // a.partitions
    chunks, lo = [], 0
    while lo < len(files):
        chunks.append(files[lo:lo + per])
        lo += per
    tasks = [(i, ch, a.scratch) for i, ch in enumerate(chunks)]
    print("partitions: %d, workers: %d" % (len(tasks), a.workers), flush=True)

    done, paths = 0, []
    with Pool(processes=a.workers, initializer=_worker_init) as pool:
        for path, resumed in pool.imap_unordered(_run_partition, tasks):
            paths.append(path)
            done += 1
            print("  partition %d/%d %s (%.1f min elapsed)"
                  % (done, len(tasks), "RESUMED" if resumed else "done",
                     (time.time() - t_start) / 60.0), flush=True)

    leg_keys = {lg: set() for lg in LEGS}
    av_total = 0
    replayed = []
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        av_total += d.get("av", 0)
        replayed.extend(d.get("seen_ts", []))
        for lg, rows in d["legs"].items():
            for ts, msg, _f in rows:
                leg_keys[lg].add((ts, msg))

    ref = C.restrict_ref(ref, replayed)      # AMENDMENT 1 A1.2
    ref_keys = set(ref)
    n_ref = len(ref_keys)
    base = leg_keys["base"]
    union = set().union(*(leg_keys[lg] for lg in LEGS))
    gained = union - base
    f_gained = (leg_keys["Fp"] | leg_keys["Fm"]) - base
    t_gained = (leg_keys["Tp"] | leg_keys["Tm"]) - base

    S_all = 100.0 * len(gained & ref_keys) / n_ref
    S_freq = 100.0 * len(f_gained & ref_keys) / n_ref
    S_time = 100.0 * len(t_gained & ref_keys) / n_ref
    X = (len(gained - ref_keys) / len(gained)) if gained else 0.0
    r_base = 100.0 * len(base & ref_keys) / n_ref

    boot = C.cluster_bootstrap(ref, {
        "S_all": gained & ref_keys, "S_freq": f_gained & ref_keys,
        "S_time": t_gained & ref_keys, "R_base": base & ref_keys,
    }, n_draws=1000)
    se_s_all = boot["S_all"]["se"]

    # ── pre-registered gate, spec 3.3, transcribed verbatim ──────────────────
    def p3_row0():
        if len(files) < 800:
            return "ROW 0a", "n_cycles %d < 800" % len(files)
        if n_ref != C.REF_EXPECTED:
            return "ROW 0b", "REF %d != %d" % (n_ref, C.REF_EXPECTED)
        if not (45.0 <= r_base <= 70.0):
            return "ROW 0c", "R_base = %.2f outside [45,70]" % r_base
        if ctl_err > 0.25:
            return "ROW 0d", "shift control error %.4f Hz > 0.25" % ctl_err
        if union == base:
            return "ROW 0e", "union added nothing: shifts not applied"
        if se_s_all > 1.0:
            return "ROW 0f", "SE(S_all) = %.3f pp > 1.0 -- underpowered" % se_s_all
        return None, None

    def p3_gate(s_all, x_guard):
        if s_all >= 3.0 and x_guard <= 0.50:
            return "ROW 1"
        if s_all <= 1.0:
            return "ROW 2"
        return "ROW 3"

    row0, reason = p3_row0()
    final = row0 if row0 else p3_gate(S_all, X)

    result = {
        "arm": "P3", "spec": "2026-08-09-0129-architect-to-qa-spec-p2-pcm-scale-"
                             "and-p3-sublattice-shift-union.md",
        "dll_sha256": sha, "shim_version": C.SHIM_VERSION,
        "n_cycles": len(files), "n_replayed": len(set(replayed)),
        "REF": n_ref, "native_av_count": av_total,
        "freq_delta_hz": FREQ_DELTA, "time_shift_samples": TIME_SAMPLES,
        "shift_control": {"mean_reported_delta_hz": ctl_mean, "n_matched": ctl_n,
                          "error_hz": ctl_err, "tolerance_hz": 0.25,
                          "deviation_from_spec": "real audio, not qa/rr-study/synth"},
        "n_decodes_by_leg": {lg: len(v) for lg, v in leg_keys.items()},
        "n_union": len(union), "n_base": len(base), "n_gained": len(gained),
        "R_base": r_base, "S_all": S_all, "S_freq": S_freq, "S_time": S_time,
        "X_guard": X, "SE_S_all": se_s_all,
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
