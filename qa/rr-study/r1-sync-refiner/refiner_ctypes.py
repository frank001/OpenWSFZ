#!/usr/bin/env python3
"""Thin ctypes wrapper on the native ft8_refine_candidate diagnostic export.

Mirrors qa/cycleframer-alignment-replay/p23_common.py's Decoder class (the pattern the
rest of the D-001 programme already uses to drive the production shim in-process via
ctypes), but binds the r1-sync-refiner-instrument-validation diagnostic export instead
of ft8_decode_all.
"""
from __future__ import annotations

import ctypes
import hashlib
import os

BUFFER_SAMPLES = 180_000  # FT8_EXPECTED_SAMPLES


def dll_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Refiner:
    """One instance per PROCESS -- never share across threads (same discipline as
    p23_common.Decoder; the native shim's callsign hash table and TLS pass-count state
    are process/thread-scoped, and this diagnostic export shares the same binary)."""

    def __init__(self, path: str, verify: bool = True, expected_sha256: "str | None" = None,
                 expected_shim_version: int = 20260040, check_version: bool = True):
        if verify:
            if expected_sha256 is None:
                raise ValueError("verify=True requires expected_sha256 (D4 pin discipline)")
            got = dll_sha256(path)
            if got != expected_sha256:
                raise RuntimeError(
                    "DLL SHA256 mismatch: expected %s got %s -- refusing to run "
                    "the validation harness against an unidentified binary"
                    % (expected_sha256, got))

        self.dll = ctypes.CDLL(os.path.abspath(path))
        d = self.dll

        d.ft8_lib_version_check.restype = ctypes.c_int
        d.ft8_refine_candidate.restype = ctypes.c_int
        d.ft8_refine_candidate.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.c_int,
            ctypes.c_int, ctypes.c_float,
            ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_float),
        ]

        ver = d.ft8_lib_version_check()
        if verify and check_version and ver != expected_shim_version:
            raise RuntimeError("shim version %s, expected %s" % (ver, expected_shim_version))
        self.version = ver

    def refine(self, pcm, coarse_freq_hz: int, coarse_time_offset_s: float):
        """pcm: float32 ndarray, exactly BUFFER_SAMPLES.
        Returns (delta_freq_hz, delta_time_s, sync_score, rc)."""
        import numpy as np  # noqa: PLC0415

        buf = np.ascontiguousarray(pcm, dtype=np.float32)
        assert buf.shape == (BUFFER_SAMPLES,), buf.shape

        out_df = ctypes.c_float(0.0)
        out_dt = ctypes.c_float(0.0)
        out_score = ctypes.c_float(0.0)

        rc = self.dll.ft8_refine_candidate(
            buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), BUFFER_SAMPLES,
            ctypes.c_int(coarse_freq_hz), ctypes.c_float(coarse_time_offset_s),
            ctypes.byref(out_df), ctypes.byref(out_dt), ctypes.byref(out_score))

        return float(out_df.value), float(out_dt.value), float(out_score.value), rc
