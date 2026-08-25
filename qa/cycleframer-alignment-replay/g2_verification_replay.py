#!/usr/bin/env python3
"""G2 verification replay -- item (a) hash-table sizing, item (b) candidate passband.

Drives a NAMED libft8.dll in-process via ctypes over a WSJT-X WAV corpus,
recording everything the dev-task's verification sections ask for:

  dev-tasks/2026-08-10-g2-hash-table-sizing-and-candidate-passband.md
    section 1.4 item 2 -- decode count unchanged across item (a)
    section 1.4 item 3 -- hashTableRejectCount on a full leg replay
    section 2.4 item 1 -- decodes gained by (b), and WHERE they fall in frequency
    section 2.4 item 2 -- per-cycle decode wall time against the 15 s budget
    section 2.4 item 3 -- candidate-cap saturation per pass, before/after
    section 3.3       -- FP proxy instrumented, NOT gated (Captain's ruling)

Reuses p23_common's Decoder/read_wav/normalise_rms machinery rather than writing new
replay plumbing, per the dev-task's explicit instruction. The SHA/version pins in
p23_common are deliberately bypassed (verify=False): the whole point here is to run
several DIFFERENT binaries and compare them, so this script pins by recording the
SHA256 of whatever it was handed and refusing to proceed without one.

NFR-021: message text stays in memory and in the scratch output file, which callers
MUST keep outside the repo. Only counts and rates may be quoted upward.

---
EXTRACTION NOTICE (2026-08-12, per the Architect's ruling of 19:24Z, finding B4):

This file previously existed ONLY inside item (b)'s own held commit (`79ea12a` on
`feat/g2-hash-table-sizing-and-candidate-passband`) -- the instrument that would
measure the change lived inside the change, had never been reviewed, and could not
produce three of the four corpora the G2(b) pre-registration's data table names.
It is extracted here onto its own branch, independent of whether item (b) ever
ships, per the ruling's explicit instruction (qa-tooling, so HK-011 does not apply;
QA may do this directly).

Two structural defects are fixed as part of the extraction, both required before
this producer can serve the pre-registration at all:

  1. `files = P.in_window_files()[:n_files]` was PREFIX-ONLY -- there was no offset,
     no `--from`, no skip. "20m cycles 251+" (the held-out remainder of the burned
     leg) was not producible. Replaced by --start-cycle/--n-files, a genuine SLICE
     into the sorted in-window population (see select_files() below).
  2. `in_window_files()` defaulted to WINDOW_20M and p23_common.WAV_DIR was
     HARD-CODED to the 08-08 corpus -- the 08-03, 17m and 80m corpora were not
     reachable without editing the module. Replaced by required --wav-dir/
     --window-lo/--window-hi flags. p23_common.py itself is NOT edited (it carries
     its own, deliberately separate, uncommitted fix noted on the board); this file
     overrides P.WAV_DIR at the module-attribute level, at call time, which is
     exactly what p23_common.in_window_files() reads.

The output JSON gains `wav_dir`, `window` and `start_cycle` fields it did not carry
before, so that a downstream consumer (g2b_gate.py's B2 fix) can tell WHICH corpus
and WHICH slice a leg was drawn from, mechanically, rather than trusting an
operator-supplied label.

STATUS: extracted and parameterised, not yet used to produce any gate leg. Awaiting
its own review (the ruling's step 1, ahead of any further g2b_gate.py work). No
decode has been run with this revision of the file.

---
REVIEW NOTICE (2026-08-12, per the Architect's third review of G2(b),
`2026-08-12-2015-architect-to-qa-g2b-review-3-and-wav-dir-ruling.md`, S5):

Two producer defects fixed:

  C3 (SERIOUS) -- counts() indexed buf[i] for i in range(max(0, n)) without
     bounding n by capacity. If a native getter ever returned n > capacity,
     this raised ctypes IndexError and killed the whole leg mid-run with no
     checkpointing -- unattended-run-hostile for a two-character bug. Fixed:
     range(min(max(n, 0), capacity)), with a stderr warning (not a crash) if
     n > capacity is ever observed.
  C4 (MODERATE) -- --n-files silently narrowed a leg when the corpus ran out
     early (WARNING to stderr, which is nobody's eyes on an unattended
     overnight run), producing a leg quietly narrower than the one specced.
     Fixed: fails closed (SystemExit) on a short corpus unless --allow-short
     is passed explicitly.

Plus the one-line MAX_RESULTS assertion the Architect asked for regardless of
finding. The Architect's own review-3 measurement against the 08-08 owsfz
ALL.TXT already cleared this (mean 16.5 decodes/cycle, p95=23, max=28, zero
cycles >= 150 -- seven times headroom; recorded so it is not re-derived as a
finding later) -- the assertion is added anyway because it is free, and it
guards specifically the leg most likely to grow: the widened rung.

---
REVIEW NOTICE (2026-08-12, per the Architect's fourth review of G2(b),
`2026-08-12-2052-architect-to-qa-g2b-review-4.md`, S4, finding D3):

D3 (SERIOUS) -- the bare `assert` above CONTRADICTED the C3 fix immediately
above it, in the same file, on the same hazard: C3's own argument was "no
checkpointing exists, so a mid-run exception discards the whole leg; clamp
and warn, do not crash." A bare `assert` crashes mid-run and discards every
completed cycle to report one suspect one -- the exact treatment C3 rejected
-- and is additionally stripped entirely under `python -O`, so it was never a
reliable safety check to begin with. Fixed: producer RECORDS (`"truncated":
True` on the cycle, alongside `"av"`, plus a stderr warning), the leg
CONTINUES, and g2b_gate.py's P2 now ROW 0s any leg carrying a truncated
cycle -- same fail-closed guarantee, no lost work, and the fact lands in the
artefact rather than only in a console nobody was watching. The 7x-headroom
measurement above stands; this is not a reason to keep the wrong treatment.

D4 (MINOR) -- `args.wav_dir` was recorded in the output JSON AS TYPED.
g2b_gate.py's C2 fix calls realpath() on this field before comparing it, but
realpath() resolves a RELATIVE path against whatever directory the GATE
happens to be started in, not the producer's -- the gate's own usage example
is relative, so this was a live convention, not a hypothetical. C2(b)
(all three legs carrying the same string) survives it, but the
--burned-corpus comparison (D1) does not: running the gate from a different
directory could silently flip whether the held-out floor applies -- D1's
hazard reached by a second route. Fixed: `os.path.realpath(args.wav_dir)` is
now taken at the source, once, against the PRODUCER's own CWD -- the only
CWD that is actually correct for resolving what the operator typed. The
recorded value is CWD-independent from that point on, regardless of where
the gate is later invoked from.

Not yet used to produce any gate leg. No decode has been run with this
revision of the file beyond the Architect's own independent verification pass.

Usage:
    python g2_verification_replay.py <dll_path> <label> <out_json> \
        --wav-dir artefacts/20260803_live_run_1713/wsjt-x/wav \
        --window-lo 260803_171330 --window-hi 260804_135645 \
        [--start-cycle 251] [--n-files 0]
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import p23_common as P  # noqa: E402

K_MAX_PASSES_CAP = 8          # generous upper bound for the getters' capacity
K_MAX_CANDIDATES = 140        # pass 1 cap (ft8_shim.c) -- for saturation reporting
K_MAX_CANDIDATES_PASS2 = 200  # pass 2 cap


def build_decoder(dll_path):
    """p23_common.Decoder, but unpinned, plus the two diagnostic getters it lacks."""
    dec = P.Decoder(path=dll_path, verify=False)
    d = dec.dll
    d.ft8_get_last_candidate_counts.restype = ctypes.c_int
    d.ft8_get_last_candidate_counts.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int]
    d.ft8_get_hash_table_reject_count.restype = ctypes.c_int
    d.ft8_get_last_pass_counts.restype = ctypes.c_int
    d.ft8_get_last_pass_counts.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int]
    return dec


def counts(fn, capacity=K_MAX_PASSES_CAP):
    """C3 fix: n was previously used unclamped -- range(max(0, n)) with n >
    capacity raises ctypes IndexError on buf[i] and kills the whole leg
    mid-run (no checkpointing exists). K_MAX_PASSES_CAP is described as
    "generous", but a getter returning more than its own buffer's capacity is
    exactly the kind of thing an SEH-guarded native call should not be trusted
    not to do. Clamp instead of crash; warn so the fact is visible without
    losing hours of unattended work over it.
    """
    buf = (ctypes.c_int * capacity)()
    n = fn(buf, capacity)
    if n > capacity:
        print(f"WARNING: native getter returned n={n} > capacity={capacity} "
              f"-- clamping to {capacity}; entries beyond the buffer are not "
              f"observable through this call", file=sys.stderr)
    return [buf[i] for i in range(min(max(n, 0), capacity))]


def select_files(wav_dir, window_lo, window_hi, start_cycle, n_files,
                  allow_short=False):
    """A genuine SLICE into the sorted in-window file list (B4 fix), never a
    bare prefix. --start-cycle is 1-based, matching the pre-registration's own
    cycle numbering ("cycle 251" means --start-cycle 251). --n-files is a count
    from there; 0 (default) means everything to the end of the in-window
    population -- the held-out-remainder case, which the old prefix-only
    version could never produce (it could only ever start at cycle 1).

    wav_dir/window are CLI-supplied, never a module-level default. p23_common's
    own WAV_DIR is overridden here at the module-attribute level rather than
    edited in p23_common.py, which carries an unrelated, deliberately
    uncommitted fix (standing memory) that must not be entangled with this
    extraction.

    C4 fix: a short corpus (fewer cycles remaining than --n-files asked for)
    previously only warned to stderr and proceeded -- nobody's eyes on an
    unattended overnight run, and the result is a leg quietly narrower than
    the one specced, with cross-leg inconsistency the only thing that would
    ever catch it (P2's n_files equality). Fails closed by default now;
    allow_short=True (--allow-short) opts back into the old warn-and-proceed
    behaviour for a caller that has actually decided a short leg is fine.
    """
    P.WAV_DIR = wav_dir
    all_files = P.in_window_files((window_lo, window_hi))
    if not all_files:
        print(f"no in-window files found under {wav_dir} for window "
              f"[{window_lo}, {window_hi}]", file=sys.stderr)
        return []
    if start_cycle < 1:
        raise SystemExit(f"--start-cycle must be >= 1 (got {start_cycle})")
    offset = start_cycle - 1
    if offset >= len(all_files):
        raise SystemExit(
            f"--start-cycle {start_cycle} is beyond the {len(all_files)} "
            f"in-window cycles available under {wav_dir}")
    tail = all_files[offset:]
    if n_files and n_files > 0:
        if len(tail) < n_files:
            msg = (f"--n-files {n_files} requested from cycle {start_cycle}, "
                   f"but only {len(tail)} in-window cycles remain under "
                   f"{wav_dir}")
            if not allow_short:
                raise SystemExit(
                    f"{msg} -- refusing to silently produce a leg narrower "
                    f"than specced (C4). Pass --allow-short to proceed "
                    f"anyway.")
            print(f"WARNING: {msg} -- replaying all {len(tail)} "
                  f"(--allow-short)", file=sys.stderr)
        return tail[:n_files]
    return tail


def check_truncated(res, label, ts):
    """D3 fix (Architect review 4): a cycle returning >= MAX_RESULTS is
    indistinguishable from a truncated one, which would censor the WIDENED
    leg preferentially (it is the one that grows) and manufacture a G_new
    loss. A bare `assert` here previously contradicted C3's own fix twenty
    lines above it, in the same file, on the same hazard: C3's argument was
    "no checkpointing exists, so a mid-run exception discards the whole leg;
    clamp and warn, do not crash." `assert` does exactly that, and is
    additionally stripped entirely under `python -O`. Producer RECORDS, gate
    ADJUDICATES: this function only marks and warns, never raises -- the leg
    always continues, and g2b_gate.py's P2 ROW 0s any leg carrying a
    truncated cycle. Extracted to its own function (matching counts()/
    select_files() above) so the marking logic is directly testable against
    the real code, not a re-implementation of it.
    """
    truncated = len(res) >= P.MAX_RESULTS
    if truncated:
        print(f"WARNING: [{label}] cycle {ts}: decoder returned "
              f"{len(res)} >= MAX_RESULTS ({P.MAX_RESULTS}) results -- "
              f"truncation cannot be ruled out for this cycle; marked "
              f"truncated, leg continues (D3)", file=sys.stderr)
    return truncated


def write_json_atomic(path, obj):
    """tmp+replace, not a bare open/dump: a crash partway through a multi-hour
    unattended leg must not leave a partially-written JSON masquerading as a
    complete one downstream. Deliberately NOT p23_common.write_json -- that
    helper pretty-prints with indent=2/sort_keys=True, which would meaningfully
    bloat a file carrying thousands of per-cycle decode records for no reader
    that needs it human-formatted.
    """
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dll_path")
    ap.add_argument("label")
    ap.add_argument("out_json")
    ap.add_argument("--wav-dir", required=True,
                     help="e.g. artefacts/20260803_live_run_1713/wsjt-x/wav -- "
                          "REQUIRED, never inherited from p23_common's own "
                          "hard-coded 08-08 default (B4 fix)")
    ap.add_argument("--window-lo", required=True,
                     help="ts floor, inclusive, e.g. 260803_171330")
    ap.add_argument("--window-hi", required=True,
                     help="ts ceiling, inclusive, e.g. 260804_135645")
    ap.add_argument("--start-cycle", type=int, default=1,
                     help="1-based index into the SORTED in-window file list "
                          "(default 1). 'cycle 251' means --start-cycle 251.")
    ap.add_argument("--n-files", type=int, default=0,
                     help="cycles to replay from --start-cycle; 0 (default) "
                          "means everything to the end of the in-window "
                          "population -- not a prefix (B4 fix)")
    ap.add_argument("--allow-short", action="store_true",
                     help="proceed (warn only) when --n-files exceeds the "
                          "cycles actually available, instead of failing "
                          "closed (C4 fix; default is fail closed)")
    args = ap.parse_args()

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

        if res is None:                       # -2: native AV contained by the shim's SEH
            per_file.append({"ts": ts, "av": True, "truncated": False,
                             "wall_s": wall, "decodes": [], "cand": [], "pass": []})
            continue

        # D3 fix: see check_truncated()'s own docstring above for the full
        # reasoning. Already measured cleared with 7x headroom (max 28/cycle
        # observed against the 08-08 owsfz ALL.TXT) -- this should never
        # fire; that is not a reason to crash if it does.
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
        })

        if (idx + 1) % 100 == 0:
            print(f"  [{args.label}] {idx + 1}/{len(files)} "
                  f"({time.perf_counter() - t_start:.0f}s)", flush=True)

    out = {
        "label": args.label,
        "dll_path": args.dll_path,
        "dll_sha256": sha,
        "shim_version": dec.version,
        # D4 fix (Architect review 4): args.wav_dir was recorded AS TYPED.
        # g2b_gate.py's C2 fix calls realpath() on this field before
        # comparing it -- but realpath() resolves a RELATIVE path against
        # whatever directory the GATE happens to be started in, not the
        # producer's, so the same leg's recorded wav_dir could silently mean
        # two different absolute directories depending on where the gate was
        # invoked from (the gate's own usage example is relative, so this is
        # a live convention, not a hypothetical). That is D1's hazard --
        # --burned-wav-dir matching zero legs -- reached by a second route.
        # Fixed at the source: realpath() here, once, at producer run time,
        # against the PRODUCER's own CWD (the only CWD that is actually
        # correct for resolving args.wav_dir as the operator typed it). The
        # recorded value is then CWD-independent and self-describing in the
        # artefact from this point on, regardless of where the gate runs.
        "wav_dir": os.path.realpath(args.wav_dir),
        "window": [args.window_lo, args.window_hi],
        "start_cycle": args.start_cycle,
        "n_files": len(files),
        "total_wall_s": time.perf_counter() - t_start,
        # Process-global and never re-initialised, so this is the session total --
        # exactly the read the daemon performs at graceful shutdown.
        "hash_table_reject_count": dec.dll.ft8_get_hash_table_reject_count(),
        "k_max_candidates": K_MAX_CANDIDATES,
        "k_max_candidates_pass2": K_MAX_CANDIDATES_PASS2,
        "per_file": per_file,
    }

    write_json_atomic(args.out_json, out)

    n_dec = sum(len(f["decodes"]) for f in per_file)
    n_av = sum(1 for f in per_file if f["av"])
    # D3 fix: reported alongside av_cycles rather than left inferable only
    # from a stderr warning nobody was watching -- same discipline as D1's
    # "print the outcome either way".
    n_truncated = sum(1 for f in per_file if f.get("truncated"))
    print(f"[{args.label}] decodes={n_dec} av_cycles={n_av} "
          f"truncated_cycles={n_truncated} "
          f"rejects={out['hash_table_reject_count']} "
          f"wall={out['total_wall_s']:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
