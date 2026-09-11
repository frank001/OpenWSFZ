#!/usr/bin/env python3
"""OSD-FA-A Amendment 1, Part 0 -- one LEG of the S1/S2/C same-harness A/B.

Spec: qa/rr-study/2026-09-11-1540-architect-to-qa-osd-fa-a-amendment-1-current-binary-and-fp-decision.md
Sec.1.2/1.3. Settles citation guard (g) / the ROW 0r "246 of 4,000" contradiction: is that a
same-harness A/B, or an artefact of comparing two different test classes/processes (Sec.1.1)?

Run this script ONCE PER LEG, as a SEPARATE OS PROCESS each time (spec: "each a separate OS
process, so each starts with a fresh session table"; p23_common.py Sec.1.1: the shim's callsign
hash table is process-global and never re-initialised). Three invocations:
    S1: current main's shim 20260050 (src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll)
    S2: the SAME binary, a second fresh process
    C:  shim 20260049 (artefacts/2026-09-03-f001-l3-shim-rebuild/libft8-20260049-prechange.dll)

Instrument: extract_llrs_ctypes.ExtractLLRs (via ldpc_decode_ctypes' import chain), NOT
p23_common.Decoder -- reused verbatim (HK-018), not reimplemented, because ExtractLLRs.__init__
binds ft8_decode_all but never CALLS ft8_set_decode_params, which is exactly spec Sec.1.2's
"default decode params (ft8_set_decode_params not called)". Extended additively here with an
ft8_set_ap_bits binding (ExtractLLRs does not bind it), called with a clearing (empty) constraint
before EVERY decode -- spec Sec.1.2 "AP bits cleared per slot" -- mirroring
fp-regression/row0a_instrument_sensitivity.py's own "Mirrors Ft8LibInterop.SetApBits([], [])"
zero-buffer convention.

Population: the 4,000 WAVs named S5_p{part:03d}_t{trial:03d}_s{seed}.wav, read in sorted filename
order (spec Sec.1.2) -- fixed-width part/trial zero-padding makes filename-string sort equivalent
to (part,trial) numeric sort; one file per (part,trial) pair, confirmed (2 parts x 2,000 trials =
4,000). Read IN PLACE by absolute path -- population lives in the Architect worktree root
(gitignored, not copied here per spec's explicit instruction).

NFR-021: message text is real decoder output over AWGN-only synthetic scenes -- the ROW 0r noise
CSV carried 361 callsign-shaped tokens (spec Sec.7), so this is scanned, not assumed clean. Output
JSON (message text, per slot) MUST live under artefacts/ (blanket-gitignored), mirroring
g3_h12_replay.py's own out_json discipline -- enforced below, not just documented.

Usage:
    python part0_runner.py <dll_path> <label> <expected_sha256> <expected_shim_version> <out_json>
"""
from __future__ import annotations

import argparse
import ctypes
import os
import re
import sys
import time
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))

from extract_llrs_ctypes import ExtractLLRs  # noqa: E402

POP_DIR = r"D:\Projects\claude\OpenWSFZ\qa\rr-study\awgn-fp-replay\_work\m1m4_s5"
FNAME_RE = re.compile(r"^S5_p(\d+)_t(\d+)_s(\d+)\.wav$")
# NOTE (disclosed, caught by a 200-file smoke test that undercounted 2,000/4,000): trial indices
# run 0..1999, NOT zero-padded to a fixed 3-digit width past 999 (t999 -> t1000, one digit
# wider), so a naive \d{3} pattern silently dropped half the population. "Sorted file order"
# (spec Sec.1.2) is therefore plain Python sorted() over these variable-width filename STRINGS,
# not numeric (part,trial) order -- e.g. ".../t1000_..." sorts before ".../t999_..." lexically.
# Applied IDENTICALLY across all three legs (same function, same file set), so P0-R1's
# determinism check and the S1-vs-C comparison are unaffected: the callsign-table build-up
# history is whatever this one fixed order produces, but it is the SAME order on every leg.

BUFFER_SAMPLES = 180_000  # 15 s @ 12 kHz, matches p23_common.py / ExtractLLRs


def read_wav_unnormalised(path: str) -> np.ndarray:
    """Mono 16-bit 12 kHz -> float32 in [-1, 1] (int16 / 32768.0), padded/truncated to buffer.

    NOT p23_common.read_wav's convention (that function keeps raw int16-scale magnitude and
    relies on a SUBSEQUENT normalise_rms(..., PROD_TARGET_RMS=0.20) call to reach the decoder's
    expected operating range -- skipping that second step, as this arm's spec requires, leaves
    PCM ~32768x too large and silently yields zero decodes; caught by a 200-slot smoke test
    before committing to a full run).

    Matches tests/OpenWSFZ.Ft8.Tests/WavReader.cs's Read() exactly: `s / 32768.0f` per sample,
    int16 -> float, no further rescaling -- the convention AwgnFpReplayTests.cs / the harness
    behind ROW 0r's own "before" CSVs uses (SetApBits([],[]) then DecodeAll(pcm) directly, no
    NormalisePcm call). Spec Sec.1.2 "no PCM normalisation, matching M1 and ROW 0r" means: do
    this basic int16->float conversion (production does the same first step), then stop --
    skip the additional RMS-targeting rescale production applies on top."""
    with wave.open(path, "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2 or w.getframerate() != 12000:
            raise RuntimeError("unexpected WAV format: %s" % path)
        a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    if a.size < BUFFER_SAMPLES:
        a = np.pad(a, (0, BUFFER_SAMPLES - a.size))
    return a[:BUFFER_SAMPLES]


def bind_ap_bits(dll) -> None:
    dll.ft8_set_ap_bits.argtypes = [
        ctypes.POINTER(ctypes.c_uint8), ctypes.c_int,
        ctypes.POINTER(ctypes.c_uint8), ctypes.c_int,
    ]
    dll.ft8_set_ap_bits.restype = None


def clear_ap_bits(dll, zero_buf) -> None:
    dll.ft8_set_ap_bits(zero_buf, 0, zero_buf, 0)


def write_json_atomic(path: str, obj) -> None:
    import json
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dll_path")
    ap.add_argument("label")
    ap.add_argument("expected_sha256")
    ap.add_argument("expected_shim_version", type=int)
    ap.add_argument("out_json")
    args = ap.parse_args()

    if not os.path.realpath(args.out_json).startswith(
            os.path.join(REPO_ROOT, "artefacts") + os.sep):
        raise SystemExit(
            f"refusing to write {args.out_json}: NFR-021 requires out_json under "
            f"artefacts/ (message text is carried in every decode record) -- never under qa/")

    if not os.path.isdir(POP_DIR):
        raise SystemExit(f"population directory not found: {POP_DIR}")

    files = sorted(fn for fn in os.listdir(POP_DIR) if FNAME_RE.match(fn))
    print(f"[{args.label}] population: {len(files)} files (sorted filename order)", flush=True)

    # P0-0a: SHA/version assertion is IN the construction call (HK-021(p)) -- ExtractLLRs
    # raises RuntimeError on any mismatch, before a single WAV is touched.
    dec = ExtractLLRs(args.dll_path, verify=True,
                       expected_sha256=args.expected_sha256,
                       expected_shim_version=args.expected_shim_version,
                       check_version=True)
    bind_ap_bits(dec.dll)
    zero_buf = (ctypes.c_uint8 * 1)(0)

    print(f"[{args.label}] dll={os.path.basename(args.dll_path)} "
          f"sha256={args.expected_sha256[:16]}... shim={dec.version}", flush=True)

    slots = []
    t_start = time.perf_counter()
    lt_count = 0  # count of decodes whose message contains the literal "<...>" hash-miss token

    for idx, fn in enumerate(files):
        m = FNAME_RE.match(fn)
        part, trial, seed = int(m.group(1)), int(m.group(2)), int(m.group(3))
        path = os.path.join(POP_DIR, fn)
        pcm = read_wav_unnormalised(path)  # no normalisation (spec Sec.1.2)

        clear_ap_bits(dec.dll, zero_buf)  # AP bits cleared per slot (spec Sec.1.2)
        t0 = time.perf_counter()
        res = dec.decode_all(pcm)
        wall = time.perf_counter() - t0

        if res is None:  # native AV contained by the shim's SEH
            slots.append({"part": part, "trial": trial, "seed": seed,
                          "av": True, "wall_s": wall, "decodes": []})
            continue

        for r in res:
            if "<...>" in r["message"]:
                lt_count += 1

        slots.append({
            "part": part, "trial": trial, "seed": seed, "av": False, "wall_s": wall,
            "decodes": [{"f": r["freq_hz"], "dt": round(r["dt"], 3),
                         "snr": r["snr"], "m": r["message"]} for r in res],
        })

        if (idx + 1) % 500 == 0:
            print(f"  [{args.label}] {idx + 1}/{len(files)} "
                  f"({time.perf_counter() - t_start:.0f}s)", flush=True)

    total_wall = time.perf_counter() - t_start
    n_dec = sum(len(s["decodes"]) for s in slots)
    n_av = sum(1 for s in slots if s["av"])

    out = {
        "label": args.label,
        "dll_path": os.path.abspath(args.dll_path),
        "dll_sha256": args.expected_sha256,
        "shim_version": dec.version,
        "pop_dir": POP_DIR,
        "n_files": len(files),
        "total_wall_s": total_wall,
        "n_decodes": n_dec,
        "n_av_slots": n_av,
        "n_lt_ellipsis_decodes": lt_count,
        "slots": slots,
    }
    write_json_atomic(args.out_json, out)

    print(f"[{args.label}] DONE slots={len(slots)} decodes={n_dec} av_slots={n_av} "
          f"lt_ellipsis={lt_count} wall={total_wall:.1f}s -> {args.out_json}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
