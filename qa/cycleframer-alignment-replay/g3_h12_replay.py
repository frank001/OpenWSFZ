#!/usr/bin/env python3
"""G3 -- SUP-B 12-bit hash-path instrumentation replay.

Drives a NAMED libft8.dll in-process via ctypes over a WAV corpus, recording
per cycle the same decode-set fields `g2_verification_replay.py` records
(so the two are directly diffable for ROW 0b), PLUS the three cumulative
counters SUP-B adds: h12Displaying / h12Ambiguous / h12Divergent.

Spec:
  qa/rr-study/2026-08-30-1149-architect-to-qa-spec-f001-sup-b-instrumented-suppression-sizing.md
  qa/rr-study/2026-08-30-1432-architect-to-qa-spec-f001-sup-b-amendment-1-row0-pre-merge.md
  Sec.A3.2 -- "QA adds [the three getters]. Do it as a new script or a
  flagged addition, not an edit that changes the behaviour of the existing
  G2(b) call path."

This file is that new script, deliberately NOT an edit to
g2_verification_replay.py. The two files share no code beyond p23_common's
Decoder/read_wav/normalise_rms (existing, unmodified) -- ROW 0b's "two
independent means" requirement (Sec.A5) needs the DECODE REPLAY of BASE and
INST to already be independent producers; the comparators built on top of
their JSON outputs supply the second independence axis (means 1 vs means 2).

The three new getters exist ONLY on the INST build (shim 20260047+). Running
this script against BASE's DLL (shim 20260046, no h12_* exports) will fail
to resolve the symbols -- that is correct and expected: BASE's own decode-set
leg is produced by the unmodified g2_verification_replay.py, exactly as
Sec.A5's fold-the-work note describes (INST's ROW 0b leg *is* the S-17M
reading leg; BASE needs one extra decode-set-only replay).

Counters are PROCESS-LIFETIME CUMULATIVE (spec Sec.3.3) -- record the raw
cumulative value every cycle, never a derived delta, so a dropped cycle is
visible as a jump rather than silently lost (Sec.A3.2).

NFR-021 (Sec.A3.3): `"m": message` on every decode carries real off-air
callsign text. out_json MUST live under artefacts/ (blanket-gitignored),
NEVER under qa/. This script does not enforce the destination path -- the
caller must pass an artefacts/ path. Counts, cycle timestamps and integers
derived from this file may be quoted upward; message text may not.

Usage:
    python g3_h12_replay.py <dll_path> <label> <out_json> \\
        --wav-dir artefacts/.../owsfz/wav \\
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
    """p23_common.Decoder, unpinned, plus the candidate/pass getters
    g2_verification_replay's own build_decoder wires, PLUS the three h12
    getters this arm adds. Deliberately NOT a call into g2's build_decoder --
    Sec.A3.2 asks for the h12 wiring to sit outside the existing G2(b) call
    path, and importing g2's function here would put this script's own
    behaviour behind an edit to that path the moment g2 changes it.
    """
    dec = P.Decoder(path=dll_path, verify=False)
    d = dec.dll
    d.ft8_get_last_candidate_counts.restype = ctypes.c_int
    d.ft8_get_last_candidate_counts.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int]
    d.ft8_get_hash_table_reject_count.restype = ctypes.c_int
    d.ft8_get_last_pass_counts.restype = ctypes.c_int
    d.ft8_get_last_pass_counts.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int]
    # The three new SUP-B getters (ft8_shim.h:745-747). No args, c_int return,
    # process-lifetime cumulative, never reset (spec Sec.3.3) -- same contract
    # as ft8_get_hash_table_reject_count above.
    d.ft8_get_h12_displaying_count.restype = ctypes.c_int
    d.ft8_get_h12_ambiguous_count.restype = ctypes.c_int
    d.ft8_get_h12_divergent_count.restype = ctypes.c_int
    # Amendment 2 (execution pack Sec.C3.1, shim 20260048+): per-code cluster
    # table getter. BASE (20260046) and the pre-Amendment-2 INST pin
    # (20260047) do not export this symbol -- binding it unconditionally
    # would raise a ctypes AttributeError at bind time on those builds. Bind
    # only when the loaded shim actually carries it; do NOT wrap this in a
    # bare try/except (Sec.C3.2's explicit instruction) -- that would let a
    # silently-unbound getter make ROW 0c-ii/0c-iii unevaluable while still
    # looking green.
    if dec.version >= 20260048:
        d.ft8_get_h12_by_code.restype = ctypes.c_int
        d.ft8_get_h12_by_code.argtypes = [ctypes.POINTER(ctypes.c_int),
                                           ctypes.POINTER(ctypes.c_int),
                                           ctypes.POINTER(ctypes.c_int),
                                           ctypes.c_int,
                                           ctypes.POINTER(ctypes.c_int)]
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
            f"refusing to write {args.out_json}: NFR-021 (Sec.A3.3) requires "
            f"out_json under artefacts/ (message text is carried in every "
            f"decode record) -- never under qa/")

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

        # h12 counters are read AFTER dec.decode(pcm) regardless of AV, so a
        # native AV (caught by the shim's SEH) cannot desync the cumulative
        # series from the cycle index -- every logged cycle carries a reading,
        # exactly like hashTableRejectCount's own per-cycle log line
        # (Ft8Decoder.cs:447).
        h12d = dec.dll.ft8_get_h12_displaying_count()
        h12a = dec.dll.ft8_get_h12_ambiguous_count()
        h12v = dec.dll.ft8_get_h12_divergent_count()

        if res is None:                       # -2: native AV contained by the shim's SEH
            per_file.append({"ts": ts, "av": True, "truncated": False,
                             "wall_s": wall, "decodes": [], "cand": [], "pass": [],
                             "h12Displaying": h12d, "h12Ambiguous": h12a,
                             "h12Divergent": h12v})
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
        })

        if (idx + 1) % 100 == 0:
            print(f"  [{args.label}] {idx + 1}/{len(files)} "
                  f"({time.perf_counter() - t_start:.0f}s)", flush=True)

    # Amendment 2 (execution pack Sec.C3.2): read the per-code cluster table
    # ONCE, at end of run -- never per cycle (48 KB x 1,856 cycles would add
    # ~90 MB of copying per leg for nothing; the per-cycle trajectory already
    # comes from the three scalars above). None on BASE/pre-Amendment-2 INST
    # (no export bound); populated on shim 20260048+.
    h12_by_code = None
    h12_code_out_of_range = None
    if dec.version >= 20260048:
        H12_CODE_SPACE = 4096
        Buf = ctypes.c_int * H12_CODE_SPACE
        _disp, _amb, _div = Buf(), Buf(), Buf()
        _oor = ctypes.c_int(-1)  # not 0 -- a getter that silently fails to
                                  # write it must not look clean (Sec.C3.2).
        _n = dec.dll.ft8_get_h12_by_code(_disp, _amb, _div, H12_CODE_SPACE,
                                          ctypes.byref(_oor))
        if _n != H12_CODE_SPACE:
            raise RuntimeError(
                f"ft8_get_h12_by_code returned {_n}, expected {H12_CODE_SPACE}")
        h12_by_code = {"displaying": list(_disp), "ambiguous": list(_amb),
                        "divergent": list(_div)}
        h12_code_out_of_range = _oor.value

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
        "h12_by_code": h12_by_code,
        "h12_code_out_of_range": h12_code_out_of_range,
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
          f"wall={out['total_wall_s']:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
