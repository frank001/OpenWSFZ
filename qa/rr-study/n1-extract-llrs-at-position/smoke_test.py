#!/usr/bin/env python3
"""Task 5.1 (n1-extract-llrs-at-position): native smoke test for ft8_extract_llrs_at,
against the real, newly-rebuilt libft8.dll (shim 20260042).

Exercises the export against a real-binary decode, per design.md's Open Questions
("either satisfies this... Python is cheaper given the Python harness will exercise
this export directly anyway"):

  (a) a valid position (a real candidate's own reported freq_hz/dt) returns rc=0 and
      174 finite floats.
  (b) a pcm_len mismatch returns -1.
  (c) a frequency far outside [200, 3000) Hz returns -3, WITHOUT writing to out_llr174
      (checked by pre-poisoning the output buffer and confirming it is untouched).
  (d) task 2.4's round-trip-against-a-REAL-candidate check, captured here as a
      repeatable test rather than a one-off manual run: take a real candidate
      ft8_decode_all reports for a real capture (its own freq_hz/dt), feed that back
      into ft8_extract_llrs_at on the IDENTICAL pcm buffer, re-encode the decoded
      message's true 174-bit codeword (ft8_encode_message, same pattern
      c2_phase2c_ber_measurement.py already established and empirically validated),
      and confirm the hard-decision BER is near-zero -- the mechanical proof that the
      new inverse mapping lands on the SAME lattice point production already used to
      decode this exact message, not an adjacent one off by a rounding convention. A
      wrong lattice point would extract a DIFFERENT candidate's likelihoods entirely,
      which reads as ~50% BER (uncorrelated garbage), not near-zero.

Uses p23_common's read_wav/normalise_rms/in_window_files (same production
preprocessing pipeline the rest of the D-001 programme runs) purely for audio I/O --
does NOT use p23_common's own DLL_SHA256 pin (that identifies a different, unmerged
build). The DLL path/SHA256 used here are supplied on the command line.

NFR-021: aggregate statistics and pass/fail only -- no callsign or message text is
ever printed. ASCII-only console output (HK-009).
"""
from __future__ import annotations

import argparse
import ctypes
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="ascii", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "cycleframer-alignment-replay"))
import p23_common as P  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
from extract_llrs_ctypes import ExtractLLRs, FTX_LDPC_N, hard_decision_ber  # noqa: E402

BER_NEAR_ZERO_THRESHOLD = 0.05  # matches c2_phase2c_ber_measurement.py's own self-check bound


def find_real_decode(ex: ExtractLLRs, max_files: int = 40):
    """Scan real WAV files until ft8_decode_all yields at least one decoded message.
    Returns (pcm, result_dict) or (None, None) if none found in max_files tries."""
    files = P.in_window_files()
    for _, path in files[:max_files]:
        pcm = P.read_wav(path)
        pcm = P.normalise_rms(pcm, P.PROD_TARGET_RMS)
        results = ex.decode_all(pcm)
        if results:
            return pcm, results[0]
    return None, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll-path", required=True)
    ap.add_argument("--dll-sha256", required=True)
    ap.add_argument("--expected-shim-version", type=int, default=20260042)
    args = ap.parse_args()

    print("=" * 78)
    print("Task 5.1 smoke test: ft8_extract_llrs_at")
    print("=" * 78)

    ex = ExtractLLRs(args.dll_path, verify=True, expected_sha256=args.dll_sha256,
                      expected_shim_version=args.expected_shim_version)
    print("Loaded shim version %d (SHA256 %s...)" % (ex.version, args.dll_sha256[:16]))

    failures = 0

    # (b) pcm_len mismatch -> -1
    import numpy as np
    short_pcm = np.zeros(179_999, dtype=np.float32)
    rc = ex.dll.ft8_extract_llrs_at(
        short_pcm.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), 179_999,
        ctypes.c_float(1500.0), ctypes.c_float(1.0),
        (ctypes.c_float * FTX_LDPC_N)())
    ok_b = (rc == -1)
    print("(b) pcm_len mismatch -> rc=%d [%s]" % (rc, "PASS" if ok_b else "FAIL"))
    failures += 0 if ok_b else 1

    # (c) frequency far outside [200, 3000) Hz -> -3, out buffer untouched
    full_pcm = np.zeros(180_000, dtype=np.float32)
    poison = (ctypes.c_float * FTX_LDPC_N)(*([-999.0] * FTX_LDPC_N))
    rc_c = ex.dll.ft8_extract_llrs_at(
        full_pcm.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), 180_000,
        ctypes.c_float(9000.0), ctypes.c_float(1.0),
        poison)
    untouched = all(x == -999.0 for x in poison)
    ok_c = (rc_c == -3) and untouched
    print("(c) freq_hz=9000 (far out-of-band) -> rc=%d, out_llr174 untouched=%s [%s]"
          % (rc_c, untouched, "PASS" if ok_c else "FAIL"))
    failures += 0 if ok_c else 1

    # (a) + (d): find a real decoded candidate, extract at its own position, check
    #     rc=0 + 174 finite floats, and the round-trip BER against the true codeword.
    print("Scanning real WAV corpus for a decoded candidate...")
    pcm, result = find_real_decode(ex)
    if result is None:
        print("(a)/(d) SKIP: no decoded candidate found in the scanned window -- "
              "cannot run the real-candidate round-trip check.")
        failures += 1
    else:
        rc_a, llr174 = ex.extract_at(pcm, float(result["freq_hz"]), float(result["dt"]))
        finite = llr174 is not None and all(np.isfinite(x) for x in llr174)
        ok_a = (rc_a == 0) and finite and llr174 is not None and len(llr174) == FTX_LDPC_N
        print("(a) real candidate (freq_hz=%d, dt=%.3f) -> rc=%d, 174 finite floats=%s [%s]"
              % (result["freq_hz"], result["dt"], rc_a, finite, "PASS" if ok_a else "FAIL"))
        failures += 0 if ok_a else 1

        if ok_a:
            true_bits = ex.true_codeword(result["message"])
            if true_bits is None:
                print("(d) SKIP: message text could not be re-encoded (unusual format).")
                failures += 1
            else:
                ber = hard_decision_ber(llr174, true_bits)
                ok_d = ber < BER_NEAR_ZERO_THRESHOLD
                print("(d) round-trip hard-decision BER at this candidate's own grid "
                      "position: %.1f%% (near-zero threshold %.0f%%) [%s]"
                      % (ber * 100.0, BER_NEAR_ZERO_THRESHOLD * 100.0, "PASS" if ok_d else "FAIL"))
                print("    (near-zero confirms the inverse mapping lands on the SAME "
                      "lattice point production used -- a wrong point would read as "
                      "~50%% BER, uncorrelated garbage, not near-zero.)")
                failures += 0 if ok_d else 1

    print()
    if failures:
        print("RESULT: FAIL -- %d check(s) failed" % failures)
        return 1
    print("RESULT: PASS -- all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
