#!/usr/bin/env python3
"""
C.5a -- calibrate this codebase's LDPC/OSD correction threshold.

The question, first asked 2026-07-26 and never answered:

    How many bit errors can THIS codebase's BP+OSD actually correct?

Every BER reading in the D-001 thread -- including two Architect rulings -- has been
read against a threshold nobody measured.  This measures it.

METHOD (no native change; verified 2026-08-07 that none is needed)
    The spec's literal form ("drive bp_decode on arbitrary LLR input") is NOT
    possible through the shipped exports -- ft8_shim.h exposes no LLR entry point;
    ft8_decode_all takes audio.  An equivalent route exists through exports that DO
    exist, and it is the one used here:

        message -> pack -> +CRC -> LDPC encode        (qa/rr-study clean-room synth)
                -> 174-bit codeword
                -> FLIP k BITS                        <-- the injected damage
                -> assemble_symbols() -> 79 tones
                -> GFSK modulate at high SNR
                -> ft8_decode_all()                   <-- our shipped decoder
                -> did the ORIGINAL message come back?

    At high SNR the demodulator recovers the transmitted (corrupted) codeword
    faithfully, so exactly k bit errors reach LDPC/OSD.  The k=0 column is the
    instrument check: it must be ~100% or the measurement is void.

WHAT THIS MEASURES, AND THE ONE DIRECTION IT IS BIASED
    An injected bit flip becomes a CONFIDENTLY WRONG soft LLR.  Real demodulation
    errors at low SNR are UNCERTAIN LLRs near zero, which BP finds easier to fix.
    So this waterfall is the pessimistic case, and the bias direction is stateable:

        the true correction capability is AT LEAST what this measures.

    That is the safe direction for C.5b's ROW 1 ("we are dropping correctable
    codewords"): a candidate whose BER sits below this threshold was definitely
    correctable, so the defect count that follows is a LOWER bound, never inflated.

ERROR PATTERNS
    uniform   -- k bit positions drawn uniformly from 0..173
    clustered -- k bits drawn within whole 3-bit symbol groups (bit i lives in
                 symbol i//3).  Real demodulation errors are symbol-correlated, so
                 clustered is PRIMARY per the 2117 spec; uniform is secondary.

NFR-021: only Q-prefix synthetic callsigns (ITU-unallocated).  ASCII-only output
per HK-009.  Read-only with respect to src/ -- nothing is rebuilt or modified.
"""
from __future__ import annotations

import ctypes
import json
import os
import random
import sys
import time

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "qa", "rr-study"))

from synth import crc, encoder, ldpc, packing, symbols  # noqa: E402

SAMPLE_RATE = 12000
BUFFER_LEN = 180000          # 15 s * 12 kHz -- ft8_decode_all rejects anything else
SNR_DB = 20.0                # high enough that demodulation adds no errors of its own
DT_S = 0.5
BASE_FREQ_START = 400.0
FREQ_SPACING = 200.0         # FT8 occupies ~50 Hz; 200 Hz apart is non-interfering
MAX_RESULTS = 64

K_VALUES = list(range(0, 46))
TRIALS_PER_K = 204           # 17 buffers x 12 signals
SEED = 20260807

# Distinct messages are REQUIRED, not cosmetic: the shim dedups by message hash
# (ft8_shim.c:1387), so the same message at 12 frequencies would collapse to one
# decode and every trial but the first would read as a failure.
MESSAGES = ["CQ Q1ABC %s" % g for g in
            ["AA00", "AB01", "AC02", "AD03", "AE04", "AF05",
             "AG06", "AH07", "AI08", "AJ09", "AK10", "AL11"]]
SIGNALS_PER_BUFFER = len(MESSAGES)


class FT8Result(ctypes.Structure):
    _fields_ = [("freq_hz", ctypes.c_int),
                ("dt", ctypes.c_float),
                ("snr", ctypes.c_int),
                ("message", ctypes.c_char * 36)]


def load_native():
    dll = os.path.join(REPO, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")
    lib = ctypes.CDLL(dll)
    lib.ft8_lib_version_check.restype = ctypes.c_int
    lib.ft8_decode_all.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_int,
                                   ctypes.POINTER(FT8Result), ctypes.c_int]
    lib.ft8_decode_all.restype = ctypes.c_int
    return lib, lib.ft8_lib_version_check()


def codeword_for(message):
    return ldpc.encode_ldpc(crc.append_crc(packing.pack_message(message)))


def corrupt(codeword, k, pattern, rng):
    """Return a copy of `codeword` with exactly k bits flipped."""
    bits = list(codeword)
    if k == 0:
        return bits
    if pattern == "uniform":
        positions = rng.sample(range(174), k)
    else:  # clustered within 3-bit symbol groups
        groups = list(range(58))
        rng.shuffle(groups)
        positions, gi = [], 0
        while len(positions) < k:
            g = groups[gi]
            gi += 1
            for b in range(3):
                if len(positions) < k:
                    positions.append(g * 3 + b)
    for p in positions:
        bits[p] ^= 1
    return bits


def build_buffer(k, pattern, rng):
    """One 15 s buffer carrying SIGNALS_PER_BUFFER independently-corrupted signals."""
    buf = np.zeros(BUFFER_LEN, dtype=np.float64)
    for i, msg in enumerate(MESSAGES):
        bits = corrupt(codeword_for(msg), k, pattern, rng)
        tones = symbols.assemble_symbols(bits)
        audio = encoder.render_tones(tones, BASE_FREQ_START + i * FREQ_SPACING,
                                     dt_s=DT_S, snr_db=SNR_DB, seed=rng.randrange(1 << 30),
                                     sample_rate_hz=SAMPLE_RATE)
        n = min(len(audio), BUFFER_LEN)
        buf[:n] += audio[:n]
    peak = np.abs(buf).max()
    if peak > 0:
        buf = buf / peak * 0.9      # ft8_decode_all expects [-1, 1]
    return buf.astype(np.float32)


def decode(lib, buf):
    arr = (ctypes.c_float * BUFFER_LEN).from_buffer_copy(buf.tobytes())
    res = (FT8Result * MAX_RESULTS)()
    n = lib.ft8_decode_all(arr, BUFFER_LEN, res, MAX_RESULTS)
    if n < 0:
        raise RuntimeError("ft8_decode_all returned %d" % n)
    return {res[i].message.decode("ascii", "replace").strip() for i in range(n)}


def run(lib):
    rng = random.Random(SEED)
    out = {}
    for pattern in ("clustered", "uniform"):
        rows = []
        for k in K_VALUES:
            ok = tot = 0
            t0 = time.time()
            for _ in range(TRIALS_PER_K // SIGNALS_PER_BUFFER):
                got = decode(lib, build_buffer(k, pattern, rng))
                for msg in MESSAGES:
                    tot += 1
                    if msg in got:
                        ok += 1
            rate = ok / float(tot)
            rows.append(dict(k=k, ok=ok, n=tot, rate=rate))
            print("  %-9s k=%2d  %4d/%4d  %6.2f%%   (%.1fs)"
                  % (pattern, k, ok, tot, rate * 100, time.time() - t0))
            sys.stdout.flush()
            if rate == 0.0 and k >= 3 and rows[-2]["rate"] == 0.0:
                print("  %-9s ... zero twice running, stopping this arm" % pattern)
                break
        out[pattern] = rows
    return out


def k50(rows):
    """Largest k whose success rate is >= 0.50. None if even k=0 fails it."""
    good = [r["k"] for r in rows if r["rate"] >= 0.50]
    return max(good) if good else None


def main():
    lib, ver = load_native()
    print("C.5a -- LDPC/OSD correction threshold")
    print("=" * 64)
    print("shim version : %d   (shipped config; 20260033 = main)" % ver)
    print("trials per k : %d   (%d buffers x %d signals)"
          % (TRIALS_PER_K, TRIALS_PER_K // SIGNALS_PER_BUFFER, SIGNALS_PER_BUFFER))
    print("SNR          : %.1f dB    seed %d" % (SNR_DB, SEED))
    print()

    results = run(lib)

    print()
    print("=" * 64)
    summary = {}
    for pattern in ("clustered", "uniform"):
        rows = results[pattern]
        zero = next((r["k"] for r in rows if r["rate"] == 0.0), None)
        summary[pattern] = dict(k50=k50(rows), first_zero=zero,
                                k0_rate=rows[0]["rate"], rows=rows)
        print("%-9s  k_50 = %-5s  first zero at k = %-5s  k0 = %.3f"
              % (pattern, summary[pattern]["k50"], zero, rows[0]["rate"]))

    k0_ok = all(summary[p]["k0_rate"] >= 0.99 for p in summary)
    verdict = "VALID" if k0_ok else "VOID -- k=0 must decode ~100%; the instrument is broken"
    print()
    print("instrument   : %s" % verdict)
    print("PRIMARY k_50 : %s  (clustered-within-symbol)" % summary["clustered"]["k50"])

    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), "c5a_waterfall_result.json")
    with open(dest, "w") as fh:
        json.dump(dict(shim_version=ver, snr_db=SNR_DB, seed=SEED,
                       trials_per_k=TRIALS_PER_K, instrument=verdict,
                       primary_pattern="clustered", summary=summary), fh, indent=2)
    print("wrote %s" % dest)


if __name__ == "__main__":
    main()
