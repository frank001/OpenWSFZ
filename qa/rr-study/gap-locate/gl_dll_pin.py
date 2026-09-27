#!/usr/bin/env python3
"""GAP-LOCATE: pinned DLL loader.

Spec: qa/rr-study/2026-09-22-1807-architect-to-qa-spec-gap-locate.md
Amendment 1: qa/rr-study/2026-09-27-1325-architect-to-qa-gap-locate-go-and-amendment-1.md

Amendment 1 item 1: copy artefacts/density-remedy-stage1-accept/bin/libft8_NEW.dll into
THIS run's own artefact dir as bin/libft8_C3.dll, then load THAT copy -- never the dev
or w-di-run bin/ dirs (build outputs, overwritten silently by the next build).

D4 pin discipline: this arm pins its own value explicitly, reusing
r2-coherent-llr-instrument.ldpc_decode_ctypes.LdpcDecodeLLRs (HK-018) for the ctypes
binding (ft8_extract_llrs_at, ft8_decode_all, ft8_ldpc_decode_llrs, ft8_encode_message /
true_codeword, a91_to_bits), but NOT its module-level PINNED_DLL_SHA256 (that pins a
DIFFERENT arm's binary, f-nbr-a's own S8HN session build).
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

# Pinned by the Architect's Amendment 1 / the spec's own ROW 0a, verified independently
# this session (full-file hash match, all 3 entry points resolve) -- same binary that
# produced the C3 corpus itself (README.md: shim 20260054, decoding_improvement 84cac119
# containing fa8a56ae).
PINNED_DLL_SHA256 = "38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba"
PINNED_SHIM_VERSION = 20260054

# Production decode params (k, corr, nhard) -- reused from passband-140/dll_pin.py's own
# "BASE" leg convention (140,3075) passband, nhard 40. Suppression left at compiled
# default (-5, 15, 1), matching row0.json's own supp_default -- never touched here.
PROD_PARAMS = (10, 0.10, 40)

K_LDPC_ITERATIONS = 50   # ft8_shim.c:509 -- f-nbr-a/dll_common.py, reused verbatim
OSD_DEPTH = 2            # decode.c:666 -- osd_decode(llr_for_osd, 2, plain174)

SYMBOL_PERIOD_S = 0.16   # f-nbr-a/dll_common.py's confirmed waterfall-origin offset,
                          # applied inside row0._forced_success -- do NOT add a second one.


def extraction_time_offset_s(true_dt_s: float) -> float:
    """dt_true -> the time_offset_s to pass to ft8_extract_llrs_at. Identical formula
    to f-nbr-a/dll_common.py's own function (same confirmed one-symbol waterfall-origin
    displacement, a shim-level constant, not tied to any one pinned binary)."""
    return float(true_dt_s) + SYMBOL_PERIOD_S


def run_dir_dll_path(run_dir: str) -> str:
    return os.path.join(run_dir, "bin", "libft8_C3.dll")


def load_decoder(run_dir: str, verify: bool = True) -> LdpcDecodeLLRs:
    path = run_dir_dll_path(run_dir)
    dec = LdpcDecodeLLRs(
        path, verify=verify,
        expected_sha256=PINNED_DLL_SHA256,
        expected_shim_version=PINNED_SHIM_VERSION,
        check_version=True,
    )
    dec.dll.ft8_set_decode_params(PROD_PARAMS[0], PROD_PARAMS[1], PROD_PARAMS[2])
    return dec


def identity_check(run_dir: str) -> dict:
    """ROW 0a: loaded DLL sha256 == pin; the three entry points resolve."""
    path = run_dir_dll_path(run_dir)
    got_sha = dll_sha256(path)
    dec = load_decoder(run_dir, verify=True)
    resolves = {
        "ft8_decode_all": hasattr(dec.dll, "ft8_decode_all"),
        "ft8_extract_llrs_at": hasattr(dec.dll, "ft8_extract_llrs_at"),
        "ft8_ldpc_decode_llrs": hasattr(dec.dll, "ft8_ldpc_decode_llrs"),
    }
    ok = (got_sha == PINNED_DLL_SHA256) and all(resolves.values()) and dec.version == PINNED_SHIM_VERSION
    return {
        "loaded_dll": path,
        "sha256": got_sha,
        "pin": PINNED_DLL_SHA256,
        "shim_reported": dec.version,
        "shim_pin": PINNED_SHIM_VERSION,
        "resolves": resolves,
        "pass": bool(ok),
    }
