#!/usr/bin/env python3
"""Thin ctypes wrapper on the native ft8_get_last_snr_terms diagnostic export
(r2-coherent-llr-instrument, Amendment 2, corrected by Amendment 3,
FT8_SHIM_VERSION 20260045, tasks.md 14.2/14.3).

Extends n1-extract-llrs-at-position/extract_llrs_ctypes.ExtractLLRs (reused verbatim,
not reimplemented -- HK-018) with a binding for the new getter this Amendment's
Developer session added. Built for QA's own tasks.md Sec.17 acceptance run
(AC-N2/AC-N3/AC-N4 gating, AC-N5 reported).

Same process/thread-scoping discipline as the parent class and every sibling ctypes
wrapper in this programme: one instance per PROCESS, never shared across threads --
ft8_get_last_snr_terms's own contract requires it be called from the same thread that
called ft8_decode_all, and must be read IMMEDIATELY after that decode_all call, before
any other ft8_decode_all call on this thread overwrites the TLS state it exposes.
"""
from __future__ import annotations

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))

from extract_llrs_ctypes import ExtractLLRs  # noqa: E402

# Amendment 2/3 pin (task 16.4) -- read from disk this session, matches
# coherent_llr_ctypes.py's own pin byte-for-byte (both modules re-pin independently
# rather than importing one from the other, so each stays importable standalone).
CURRENT_DLL_SHA256 = "f0c081b968b04515f3fe76b853b423c77be1495d8e645115ceb3434f9e81fe58"
CURRENT_SHIM_VERSION = 20260045


class SnrTermsDecoder(ExtractLLRs):
    """Adds ft8_get_last_snr_terms alongside ExtractLLRs's existing ft8_decode_all
    binding. Raises AttributeError at construction if the loaded DLL does not export
    ft8_get_last_snr_terms -- refuses to run silently against a pre-Amendment-2 binary."""

    def __init__(self, path: str, verify: bool = True, expected_sha256: "str | None" = None,
                 expected_shim_version: int = CURRENT_SHIM_VERSION, check_version: bool = True):
        super().__init__(path, verify=verify, expected_sha256=expected_sha256,
                          expected_shim_version=expected_shim_version, check_version=check_version)
        self.dll.ft8_get_last_snr_terms.restype = ctypes.c_int
        self.dll.ft8_get_last_snr_terms.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float), ctypes.c_int,
        ]

    def get_last_snr_terms(self, capacity: int, want_signal: bool = True,
                            want_noise: bool = True, buf_size: int = 500):
        """Calls ft8_get_last_snr_terms(capacity) against the TLS state left by the
        most recent decode_all() call on this instance. want_signal/want_noise=False
        passes NULL for that output pointer (AC-N4's NULL-pointer cases).

        Returns (n, signal_db_list_or_None, local_noise_db_list_or_None). n mirrors
        the native return value exactly (may be -1 on capacity<0). buf_size is an
        internal allocation size unrelated to capacity -- large enough that any
        overrun beyond `capacity` would be observable by a caller inspecting the raw
        buffer directly (see AC-N4's own no-overrun check, which bypasses this
        wrapper's trim-to-n behaviour deliberately).
        """
        sig_buf   = (ctypes.c_float * buf_size)()
        noise_buf = (ctypes.c_float * buf_size)()
        sig_ptr   = ctypes.cast(sig_buf, ctypes.POINTER(ctypes.c_float)) if want_signal else None
        noise_ptr = ctypes.cast(noise_buf, ctypes.POINTER(ctypes.c_float)) if want_noise else None

        n = self.dll.ft8_get_last_snr_terms(sig_ptr, noise_ptr, capacity)

        if n < 0:
            return n, None, None
        written = min(n, buf_size)
        sig_list   = [float(x) for x in sig_buf[:written]] if want_signal else None
        noise_list = [float(x) for x in noise_buf[:written]] if want_noise else None
        return n, sig_list, noise_list
