#!/usr/bin/env python3
"""Thin ctypes wrapper on the native ft8_ldpc_decode_llrs diagnostic export
(r2-coherent-llr-instrument, Route B2 Phase B Amendment 1, FT8_SHIM_VERSION 20260044).

Mirrors coherent_llr_ctypes.CoherentExtractLLRs's own pattern -- extends
n1-extract-llrs-at-position/extract_llrs_ctypes.ExtractLLRs (reused verbatim, not
reimplemented -- HK-018) with a binding for this session's own new export.

ft8_ldpc_decode_llrs takes a caller-supplied 174-element RAW (pre-normalisation) LLR
vector and decodes it through production's own bp_decode -> OSD (conditional) -> CRC-14
sequence (patched/ft8/decode.c's ftx_ldpc_decode_llrs, mirroring
ftx_decode_candidate:641-713 exactly). See src/OpenWSFZ.Ft8/Native/ft8_shim.h's own
r2-coherent-llr-instrument Phase B + Amendment 1 changelog entry for the full contract.

Diagnostic-only, no production call site, no C# binding (design.md D10) -- this Python
ctypes harness and this session's own native/Python smoke tests are the only consumers.
"""
from __future__ import annotations

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))

from extract_llrs_ctypes import FTX_LDPC_N, ExtractLLRs  # noqa: E402

FTX_LDPC_K = 91
FTX_LDPC_K_BYTES = (FTX_LDPC_K + 7) // 8  # 12

# decode.c:707-713 (mirrored verbatim by ftx_ldpc_decode_llrs, task 9.2 step 6) zeroes
# a91's CRC-14 region (a91[9] &= 0xF8; a91[10] &= 0x00) BEFORE computing crc_calculated,
# and returns that same, now-zeroed buffer as a91 -- exactly what production's own
# message->payload[] receives. Only the first FT8_PAYLOAD_BITS (77) of a91 are the
# actual message payload and are meaningful to compare bit-for-bit against a
# true_codeword() encoding; bits [77, 91) are always zero in a91 regardless of the
# real transmitted CRC value (the CRC value itself is separately reported via
# out_crc_ok, not readable back out of a91).
FT8_PAYLOAD_BITS = 77

# The binary this session's own task 10.2 rebuilt (Phase B: B1 origin fix, B2 fusion
# fix, B4 ft8_ldpc_decode_llrs export). Re-hashed from disk this session -- read the
# actual file, never copied from a report (task 10.4's own discipline, applied here
# too since this module is one of the four harnesses task 10.4 names).
CURRENT_DLL_SHA256 = "a3d32b7839a0fd73dcc8d35bd514d60f962f3267179fd77cbd8a1ebd6ecc8d45"
CURRENT_SHIM_VERSION = 20260044


class LdpcDecodeLLRs(ExtractLLRs):
    """Adds ft8_ldpc_decode_llrs alongside ExtractLLRs's existing ft8_extract_llrs_at /
    ft8_decode_all / true_codeword / ft8_encode_message bindings. Raises AttributeError
    at construction if the loaded DLL does not export ft8_ldpc_decode_llrs -- i.e. this
    class refuses to run silently against a pre-Phase-B binary that lacks the symbol."""

    def __init__(self, path: str, verify: bool = True, expected_sha256: "str | None" = None,
                 expected_shim_version: int = CURRENT_SHIM_VERSION, check_version: bool = True):
        super().__init__(path, verify=verify, expected_sha256=expected_sha256,
                          expected_shim_version=expected_shim_version, check_version=check_version)
        self.dll.ft8_ldpc_decode_llrs.restype = ctypes.c_int
        self.dll.ft8_ldpc_decode_llrs.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
        ]

    def ldpc_decode_llrs(self, llr174, max_iters: int = 50, osd_depth: int = 2):
        """llr174: length-174 sequence of RAW (pre-normalisation) LLRs.
        osd_depth < 0 disables the OSD fallback (BP-only probe run).

        Returns a dict: {rc, path, crc_ok, ldpc_errors, a91 (bytes, 12, or None if
        out_a91 was not requested -- always requested here)}."""
        assert len(llr174) == FTX_LDPC_N, len(llr174)

        buf = (ctypes.c_float * FTX_LDPC_N)(*[float(x) for x in llr174])
        out_a91 = (ctypes.c_uint8 * FTX_LDPC_K_BYTES)()
        out_ldpc_errors = ctypes.c_int(-1)
        out_path = ctypes.c_int(-2)
        out_crc_ok = ctypes.c_int(-1)

        rc = self.dll.ft8_ldpc_decode_llrs(
            buf, ctypes.c_int(max_iters), ctypes.c_int(osd_depth),
            out_a91, ctypes.byref(out_ldpc_errors), ctypes.byref(out_path), ctypes.byref(out_crc_ok))

        return {
            "rc": rc,
            "path": out_path.value,
            "crc_ok": out_crc_ok.value,
            "ldpc_errors": out_ldpc_errors.value,
            "a91": bytes(out_a91) if rc == 0 else None,
        }


def a91_to_bits(a91: bytes, num_bits: int = FTX_LDPC_K) -> list[int]:
    """Inverse of decode.c's pack_bits: MSB-first per byte. Returns num_bits 0/1 ints."""
    bits = []
    for i in range(num_bits):
        byte = a91[i // 8]
        mask = 0x80 >> (i % 8)
        bits.append(1 if (byte & mask) else 0)
    return bits
