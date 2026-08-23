"""F-NBR-A: pinned DLL loader.

Reuses r2-coherent-llr-instrument.ldpc_decode_ctypes.LdpcDecodeLLRs verbatim
(HK-018) -- it already binds ft8_extract_llrs_at, ft8_decode_all,
ft8_ldpc_decode_llrs, ft8_encode_message/true_codeword and a91_to_bits. That
module's own CURRENT_DLL_SHA256/CURRENT_SHIM_VERSION module constants pin ITS
OWN session's rebuilt binary (a3d32b78..., 20260044) -- NOT this arm's binary.
This arm pins its own values explicitly (D4 pin discipline) rather than
inheriting those defaults.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "r2-coherent-llr-instrument"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))

from ldpc_decode_ctypes import (  # noqa: E402
    LdpcDecodeLLRs, FTX_LDPC_N, FTX_LDPC_K, FT8_PAYLOAD_BITS, a91_to_bits,
)
from extract_llrs_ctypes import dll_sha256  # noqa: E402

# Verified 2026-08-23 (this session) by hashing BOTH copies on disk (§0.6 of the
# spec) -- byte-identical to the S8HN run's own binary.
PINNED_DLL_SHA256 = "bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f"
PINNED_SHIM_VERSION = 20260046  # read from ft8_lib_version_check() this session

DLL_PATH = os.path.join(REPO_ROOT, "native", "ft8_lib_build", "libft8.dll")
DLL_PATH_SRC_COPY = os.path.join(
    REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")

K_LDPC_ITERATIONS = 50   # ft8_shim.c:509
OSD_DEPTH = 2            # decode.c:666 -- osd_decode(llr_for_osd, 2, plain174)

# ── Waterfall-origin-convention correction, DISCLOSED per the spec's own closing
# instruction (Sec.8: "If a ROW 0 check needs correcting to be runnable, correct
# it and disclose the correction in full ... A disclosed correction is a
# result; a silent one voids the arm.") ──────────────────────────────────────
#
# The spec's Sec.4.1 step 2 calls for ft8_extract_llrs_at(..., time_offset_s=0.0)
# literally (station F's true dt_s), and Sec.3 ROW 0c's positive control
# likewise names "station A (450 Hz, dt 0.0)" and "station E (1150 Hz, dt 0.0)".
# Run literally, ROW 0c VOIDs: 0/25 for BOTH positive controls (measured this
# session). This is not a real decoder failure -- ft8_decode_all decodes both
# stations 25/25 in the SAME rendered PCM, reporting dt ~= 0.1599999964237213 for
# EVERY true-dt=0 station (bit-identical across stations), which is exactly
# SYMBOL_PERIOD_S below. Forcing extraction at that decoder-reported dt instead
# of the literal truth dt makes ROW 0c's positive controls succeed immediately
# (measured: crc_ok=1, exact payload match, ldpc_errors=0).
#
# This is NOT a new finding -- it is r2-coherent-llr-instrument's own
# B-orig-A arm (qa/rr-study/2026-08-21-1412-architect-to-qa-origin-convention-
# finding-and-spec-b-orig-a.md, CONFIRMED, gated ROW 1 fired): "the waterfall
# index that ft8_extract_llrs_at reads is NOT raw-PCM time -- it runs exactly
# ONE FT8 symbol AHEAD of it" (monitor.c's look-back window). Reused verbatim
# (HK-018) rather than re-derived: the correction is a fixed, additive
# SYMBOL_PERIOD_S applied to every ft8_extract_llrs_at call's time_offset_s
# argument, dt_true + SYMBOL_PERIOD_S, regardless of station or frequency.
#
# Applied uniformly (ROW 0c's positive controls AND Part A's forced extraction
# at station F) -- selectively correcting only the controls while leaving F at
# the spec's literal 0.0 would extract F from a DIFFERENT relative position
# than the position validated by the controls, which defeats ROW 0c's entire
# purpose ("uses station F's own near neighbour as one of the two controls").
SYMBOL_PERIOD_S = 0.16


def extraction_time_offset_s(true_dt_s: float) -> float:
    """dt_true -> the time_offset_s to pass to ft8_extract_llrs_at, correcting
    for the confirmed one-symbol waterfall-origin displacement (see above)."""
    return float(true_dt_s) + SYMBOL_PERIOD_S


def load_decoder(verify: bool = True) -> LdpcDecodeLLRs:
    return LdpcDecodeLLRs(
        DLL_PATH, verify=verify,
        expected_sha256=PINNED_DLL_SHA256,
        expected_shim_version=PINNED_SHIM_VERSION,
        check_version=True,
    )


def both_copies_match_pin() -> tuple[bool, bool, str, str]:
    a = dll_sha256(DLL_PATH)
    b = dll_sha256(DLL_PATH_SRC_COPY)
    return (a == PINNED_DLL_SHA256, b == PINNED_DLL_SHA256, a, b)
