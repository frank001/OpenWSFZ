#!/usr/bin/env python3
"""Thin ctypes wrapper on the native ft8_coherent_llr_at diagnostic export
(r2-coherent-llr-instrument, Route B2 Phase 1, FT8_SHIM_VERSION 20260043).

Extends n1-extract-llrs-at-position/extract_llrs_ctypes.ExtractLLRs (reused verbatim,
not reimplemented -- HK-018) with a binding for the new export this change's Developer
session added (tasks.md 1.1-1.5, merged to main 2026-08-21, PR #128). Same
process/thread-scoping discipline as the parent class: one instance per PROCESS, never
shared across threads.

Signature is identical in shape to ft8_extract_llrs_at (pcm, pcm_len, freq_hz,
time_offset_s, out_log174[174]) -- see src/OpenWSFZ.Ft8/Native/ft8_shim.h's own
changelog entry (r2-coherent-llr-instrument, FT8_SHIM_VERSION 20260043) for the full
contract. Coherent LLRs form at the candidate's EXISTING, UNREFINED grid position
(design.md D1) -- this export never calls ft8_refine_candidate.

Both bindings (grid + coherent) load from the SAME DLL instance, so a caller can extract
both paths against byte-identical process state at the SAME (freq_hz, time_offset_s) --
the candidate-identity requirement the Phase 1 spec's ROW 0e (and this file's own ROW 0g)
both depend on.
"""
from __future__ import annotations

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))

from extract_llrs_ctypes import BUFFER_SAMPLES, FTX_LDPC_N, ExtractLLRs  # noqa: E402

# The binary this change's own task 5.2 rebuilt and QA's 2026-08-21 10:22Z merge review
# verified as MERGED TO MAIN (PR #128, a420016) -- re-hashed from disk this session
# (matches src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt's recorded SHA256
# byte-for-byte). Deliberately NOT run_stage1.DEFAULT_DLL_SHA256/EXPECTED_SHIM_VERSION,
# which pin the PRE-merge binary (shim 20260042) -- ROW 0g's own precondition (spec
# Sec.0) is that it runs against the CURRENT merged binary.
CURRENT_DLL_SHA256 = "1889408787a2c7ea545dbe8477691b090417a74fc81116cbf1ea52413bfbdb3a"
CURRENT_SHIM_VERSION = 20260043


class CoherentExtractLLRs(ExtractLLRs):
    """Adds ft8_coherent_llr_at alongside ExtractLLRs's existing ft8_extract_llrs_at
    binding. Raises AttributeError at construction if the loaded DLL does not export
    ft8_coherent_llr_at -- i.e. this class refuses to run silently against a
    pre-Phase-1 binary that lacks the symbol."""

    def __init__(self, path: str, verify: bool = True, expected_sha256: "str | None" = None,
                 expected_shim_version: int = CURRENT_SHIM_VERSION, check_version: bool = True):
        super().__init__(path, verify=verify, expected_sha256=expected_sha256,
                          expected_shim_version=expected_shim_version, check_version=check_version)
        self.dll.ft8_coherent_llr_at.restype = ctypes.c_int
        self.dll.ft8_coherent_llr_at.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.c_int,
            ctypes.c_float, ctypes.c_float,
            ctypes.POINTER(ctypes.c_float),
        ]

    def coherent_extract_at(self, pcm, freq_hz: float, time_offset_s: float):
        """Same contract as ExtractLLRs.extract_at, against the new coherent export.
        Returns (rc, llr174_list_or_None)."""
        import numpy as np  # noqa: PLC0415

        buf = np.ascontiguousarray(pcm, dtype=np.float32)
        assert buf.shape == (BUFFER_SAMPLES,), buf.shape

        out = (ctypes.c_float * FTX_LDPC_N)()
        rc = self.dll.ft8_coherent_llr_at(
            buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), BUFFER_SAMPLES,
            ctypes.c_float(freq_hz), ctypes.c_float(time_offset_s),
            out)
        if rc != 0:
            return rc, None
        return rc, [float(x) for x in out]
