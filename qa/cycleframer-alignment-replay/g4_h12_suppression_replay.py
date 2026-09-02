#!/usr/bin/env python3
"""G4 -- f001-h12-unique-match-suppression (Option A) replay.

QA's replay-based AC-1--AC-4 (openspec/changes/f001-h12-unique-match-suppression/tasks.md
Sec.7-8; dev-tasks/2026-09-01-f001-h12-unique-match-suppression.md Sec.8's handoff note).
Compares a pre-change (shim 20260048) decode set against a post-change (shim 20260049) decode
set of the SAME S-17M corpus, decode line by decode line.

Deliberately NOT an edit to g3_h12_replay.py (SUP-B's own ROW 0 instrument) -- that script's
job is the SUP-B counter-validity rows and stays pinned to the 20260046/20260047/20260048
lineage. This is a new script for a new question: "does 20260049 change ANY decode line other
than a suppressed 12-bit callsign token", per AC-1/AC-2/AC-3, plus AC-4's counter check. Shares
p23_common / g2_verification_replay's helpers exactly as g3 does, for the same reason (ROW-0-
style independence of the decode-replay producer from the comparator built on top of it).

The BASE (20260048) leg does NOT need to be re-run here: SUP-B's own ROW 0 Amendment-2 run
already produced a full S-17M decode set at shim 20260048, dll_sha256
e22524e8fb4964496e34a2c3f08d6e10d8f6f48eaadb0626fe6a8799fa84e33e (== main@68a014d's pin, verified
against openspec/changes/f001-h12-unique-match-suppression/design.md and the current
libft8.version.txt entry before reuse) --
artefacts/2026-08-30-sup-b-row0-amend2/s17m_inst_run1.json. Re-running it would just reproduce
the same 1,856-cycle, 29,696-decode JSON at a ~24-minute cost for no new information. Only the
CANDIDATE (20260049) leg is produced by this script.

NFR-021: `"m": message` on every decode carries real off-air callsign text. out_json MUST live
under artefacts/, never under qa/ -- enforced below, same guard as g3.

Usage:
    python g4_h12_suppression_replay.py <dll_path> <label> <out_json> \\
        --wav-dir artefacts/20260808_live_run_1154-8080-17m/owsfz/wav \\
        --window-lo 260808_115445 --window-hi 260808_193830 \\
        [--start-cycle 1] [--n-files 100] [--allow-short]
"""
from __future__ import annotations

import argparse
import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import p23_common as P  # noqa: E402
from g2_verification_replay import (  # noqa: E402
    counts, select_files, check_truncated, write_json_atomic,
    K_MAX_CANDIDATES, K_MAX_CANDIDATES_PASS2,
)


def build_decoder(dll_path):
    dec = P.Decoder(path=dll_path, verify=False)
    d = dec.dll
    d.ft8_get_last_candidate_counts.restype = ctypes.c_int
    d.ft8_get_last_candidate_counts.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int]
    d.ft8_get_hash_table_reject_count.restype = ctypes.c_int
    d.ft8_get_last_pass_counts.restype = ctypes.c_int
    d.ft8_get_last_pass_counts.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int]
    d.ft8_get_h12_displaying_count.restype = ctypes.c_int
    d.ft8_get_h12_ambiguous_count.restype = ctypes.c_int
    d.ft8_get_h12_divergent_count.restype = ctypes.c_int
    # New in shim 20260049 -- absent on 20260048 and earlier. This script is
    # only ever pointed at a 20260049+ candidate build, so bind unconditionally
    # (unlike g3's conditional h12_by_code bind for a getter that spans a
    # version boundary within the SAME run).
    d.ft8_get_h12_suppressed_count.restype = ctypes.c_int
    return dec


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dll_path")
    ap.add_argument("label")
    ap.add_argument("out_json")
    ap.add_argument("--wav-dir", required=True)
    ap.add_argument("--window-lo", required=True)
    ap.add_argument("--window-hi", required=True)
    ap.add_argument("--start-cycle", type=int, default=1)
    ap.add_argument("--n-files", type=int, default=0)
    ap.add_argument("--allow-short", action="store_true")
    args = ap.parse_args()

    if not os.path.realpath(args.out_json).startswith(
            os.path.join(P.REPO_ROOT, "artefacts") + os.sep):
        raise SystemExit(
            f"refusing to write {args.out_json}: NFR-021 requires out_json under artefacts/ "
            f"(message text is carried in every decode record) -- never under qa/")

    sha = P.dll_sha256(args.dll_path)
    dec = build_decoder(args.dll_path)

    files = select_files(args.wav_dir, args.window_lo, args.window_hi,
                          args.start_cycle, args.n_files, args.allow_short)
    if not files:
        return 1

    print(f"[{args.label}] dll={os.path.basename(args.dll_path)} sha={sha[:16]}... "
          f"shim={dec.version} wav_dir={args.wav_dir} "
          f"window=[{args.window_lo},{args.window_hi}] "
          f"start_cycle={args.start_cycle} files={len(files)}", flush=True)

    per_file = []
    t_start = time.perf_counter()

    for idx, (ts, path) in enumerate(files):
        pcm = P.normalise_rms(P.read_wav(path), P.PROD_TARGET_RMS)

        t0 = time.perf_counter()
        res = dec.decode(pcm)
        wall = time.perf_counter() - t0

        h12d = dec.dll.ft8_get_h12_displaying_count()
        h12a = dec.dll.ft8_get_h12_ambiguous_count()
        h12v = dec.dll.ft8_get_h12_divergent_count()
        h12s = dec.dll.ft8_get_h12_suppressed_count()

        if res is None:
            per_file.append({"ts": ts, "av": True, "truncated": False,
                             "wall_s": wall, "decodes": [], "cand": [], "pass": [],
                             "h12Displaying": h12d, "h12Ambiguous": h12a,
                             "h12Divergent": h12v, "h12Suppressed": h12s})
            continue

        truncated = check_truncated(res, args.label, ts)

        per_file.append({
            "ts": ts,
            "av": False,
            "truncated": truncated,
            "wall_s": wall,
            "decodes": [{"f": r["freq_hz"], "dt": round(r["dt"], 3),
                         "snr": r["snr"], "m": r["message"]} for r in res],
            "cand": counts(dec.dll.ft8_get_last_candidate_counts),
            "pass": counts(dec.dll.ft8_get_last_pass_counts),
            "h12Displaying": h12d,
            "h12Ambiguous": h12a,
            "h12Divergent": h12v,
            "h12Suppressed": h12s,
        })

        if (idx + 1) % 100 == 0:
            print(f"  [{args.label}] {idx + 1}/{len(files)} "
                  f"({time.perf_counter() - t_start:.0f}s)", flush=True)

    out = {
        "label": args.label,
        "dll_path": args.dll_path,
        "dll_sha256": sha,
        "shim_version": dec.version,
        "wav_dir": os.path.realpath(args.wav_dir),
        "window": [args.window_lo, args.window_hi],
        "start_cycle": args.start_cycle,
        "n_files": len(files),
        "total_wall_s": time.perf_counter() - t_start,
        "hash_table_reject_count": dec.dll.ft8_get_hash_table_reject_count(),
        "h12_displaying_count_final": dec.dll.ft8_get_h12_displaying_count(),
        "h12_ambiguous_count_final": dec.dll.ft8_get_h12_ambiguous_count(),
        "h12_divergent_count_final": dec.dll.ft8_get_h12_divergent_count(),
        "h12_suppressed_count_final": dec.dll.ft8_get_h12_suppressed_count(),
        "k_max_candidates": K_MAX_CANDIDATES,
        "k_max_candidates_pass2": K_MAX_CANDIDATES_PASS2,
        "per_file": per_file,
    }

    write_json_atomic(args.out_json, out)

    n_dec = sum(len(f["decodes"]) for f in per_file)
    n_av = sum(1 for f in per_file if f["av"])
    n_truncated = sum(1 for f in per_file if f.get("truncated"))
    print(f"[{args.label}] decodes={n_dec} av_cycles={n_av} "
          f"truncated_cycles={n_truncated} "
          f"rejects={out['hash_table_reject_count']} "
          f"h12Displaying={out['h12_displaying_count_final']} "
          f"h12Ambiguous={out['h12_ambiguous_count_final']} "
          f"h12Divergent={out['h12_divergent_count_final']} "
          f"h12Suppressed={out['h12_suppressed_count_final']} "
          f"wall={out['total_wall_s']:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
