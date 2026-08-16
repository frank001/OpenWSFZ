#!/usr/bin/env python3
"""Thin ctypes wrapper on the native ft8_extract_llrs_at diagnostic export
(n1-extract-llrs-at-position, shim 20260042).

Mirrors qa/rr-study/r1-sync-refiner/refiner_ctypes.py's Refiner class (the same
pattern already established for the sibling diagnostic-only sync-refiner export) and
qa/cycleframer-alignment-replay/p23_common.py's Decoder class (the production
ft8_decode_all pattern), but binds both ft8_decode_all AND ft8_extract_llrs_at from
the SAME loaded binary -- N1's harness needs a real candidate's own (freq_hz, dt) from
ft8_decode_all before it can ask ft8_extract_llrs_at to re-extract at that position (or
at grid + ft8_refine_candidate's (delta_f, delta_t)), on the identical PCM buffer.

Deliberately does NOT reuse p23_common.Decoder's own DLL_SHA256 pin -- that pin
identifies d001-c4-min-score-sweep's unmerged three-pass build (39aa1031...), not this
change's binary. Callers supply expected_sha256 explicitly (D4 pin discipline).
"""
from __future__ import annotations

import ctypes
import hashlib
import os

BUFFER_SAMPLES = 180_000  # FT8_EXPECTED_SAMPLES
FTX_LDPC_N = 174
MAX_RESULTS = 200


def dll_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class FT8Result(ctypes.Structure):
    _fields_ = [("freq_hz", ctypes.c_int), ("dt", ctypes.c_float),
                ("snr", ctypes.c_int), ("message", ctypes.c_char * 36)]


class ExtractLLRs:
    """One instance per PROCESS -- never share across threads (same discipline as
    p23_common.Decoder / refiner_ctypes.Refiner; the native shim's process/thread-scoped
    state is shared across every entry point in the same binary)."""

    def __init__(self, path: str, verify: bool = True, expected_sha256: "str | None" = None,
                 expected_shim_version: int = 20260042, check_version: bool = True):
        if verify:
            if expected_sha256 is None:
                raise ValueError("verify=True requires expected_sha256 (D4 pin discipline)")
            got = dll_sha256(path)
            if got != expected_sha256:
                raise RuntimeError(
                    "DLL SHA256 mismatch: expected %s got %s -- refusing to run "
                    "against an unidentified binary" % (expected_sha256, got))

        self.dll = ctypes.CDLL(os.path.abspath(path))
        d = self.dll

        d.ft8_lib_version_check.restype = ctypes.c_int

        d.ft8_extract_llrs_at.restype = ctypes.c_int
        d.ft8_extract_llrs_at.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.c_int,
            ctypes.c_float, ctypes.c_float,
            ctypes.POINTER(ctypes.c_float),
        ]

        d.ft8_decode_all.restype = ctypes.c_int
        d.ft8_decode_all.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_int,
                                      ctypes.POINTER(FT8Result), ctypes.c_int]
        d.ft8_set_decode_params.argtypes = [ctypes.c_int, ctypes.c_float, ctypes.c_int]
        d.ft8_encode_message.restype = ctypes.c_int
        d.ft8_encode_message.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint8), ctypes.c_int]

        ver = d.ft8_lib_version_check()
        if verify and check_version and ver != expected_shim_version:
            raise RuntimeError("shim version %s, expected %s" % (ver, expected_shim_version))
        self.version = ver
        self._decode_results = (FT8Result * MAX_RESULTS)()

    def extract_at(self, pcm, freq_hz: float, time_offset_s: float):
        """pcm: float32 ndarray, exactly BUFFER_SAMPLES.
        Returns (rc, llr174_list_or_None). llr174 is raw, pre-normalisation (design.md D2)."""
        import numpy as np  # noqa: PLC0415

        buf = np.ascontiguousarray(pcm, dtype=np.float32)
        assert buf.shape == (BUFFER_SAMPLES,), buf.shape

        out = (ctypes.c_float * FTX_LDPC_N)()
        rc = self.dll.ft8_extract_llrs_at(
            buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), BUFFER_SAMPLES,
            ctypes.c_float(freq_hz), ctypes.c_float(time_offset_s),
            out)
        if rc != 0:
            return rc, None
        return rc, [float(x) for x in out]

    def decode_all(self, pcm):
        """pcm: float32 ndarray, exactly BUFFER_SAMPLES. Returns list of dicts, or None on
        native AV (rc < 0)."""
        import numpy as np  # noqa: PLC0415

        buf = np.ascontiguousarray(pcm, dtype=np.float32)
        assert buf.shape == (BUFFER_SAMPLES,), buf.shape
        n = self.dll.ft8_decode_all(
            buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            BUFFER_SAMPLES, self._decode_results, MAX_RESULTS)
        if n < 0:
            return None
        return [{"freq_hz": self._decode_results[i].freq_hz,
                  "dt": float(self._decode_results[i].dt),
                  "snr": self._decode_results[i].snr,
                  "message": self._decode_results[i].message.decode("ascii", "replace").strip()}
                 for i in range(n)]

    def true_codeword(self, message: str):
        """Re-encode message text -> 174 true bits, in encode.c's own bit-value sense
        (matches c2_phase2c_ber_measurement.py's Encoder.true_codeword exactly)."""
        FT8_NN = 79
        SYNC_RANGES = [(0, 7), (36, 43), (72, 79)]
        GRAY_MAP = [0, 1, 3, 2, 5, 6, 4, 7]
        inv_gray = [0] * 8
        for i, v in enumerate(GRAY_MAP):
            inv_gray[v] = i

        def is_sync_index(i: int) -> bool:
            return any(lo <= i < hi for lo, hi in SYNC_RANGES)

        buf = (ctypes.c_uint8 * FT8_NN)()
        rc = self.dll.ft8_encode_message(message.encode("ascii", errors="replace"), buf, FT8_NN)
        if rc != FT8_NN:
            return None
        tones = list(buf)
        data_tones = [t for i, t in enumerate(tones) if not is_sync_index(i)]
        bits = []
        for tone in data_tones:
            b3 = inv_gray[tone]
            bits.append((b3 >> 2) & 1)
            bits.append((b3 >> 1) & 1)
            bits.append(b3 & 1)
        return bits


def hard_decision_ber(llr174, true_bits) -> float:
    """Identical sign convention to c2_phase2c_ber_measurement.py's hard_decision_ber:
    hd = 1 if llr > 0.0 else 0 (empirically verified against the matched-hit control
    population; NOT decode.c's own internal OSD-gate hd formula, which encodes a
    different, Hamming-closeness sense -- see that module's docstring)."""
    assert len(llr174) == FTX_LDPC_N and len(true_bits) == FTX_LDPC_N
    errors = sum(1 for llr, tb in zip(llr174, true_bits) if (1 if llr > 0.0 else 0) != tb)
    return errors / FTX_LDPC_N
