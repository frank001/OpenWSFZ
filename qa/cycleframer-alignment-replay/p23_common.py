#!/usr/bin/env python3
"""Shared infrastructure for P2 (PCM scale) and P3 (sub-lattice shift union).

Spec: 2026-08-09-0129-architect-to-qa-spec-p2-pcm-scale-and-p3-sublattice-shift-union.md

Both arms drive the PRODUCTION libft8.dll in-process via ctypes, exactly as
w1_sec5_calibration.py does, over WSJT-X FT991A's own WAVs for the 20m clean
window.  REF/MISS populations come from t1_frequency_quantisation.load so they
are provably the same 69 222 the whole programme uses.

NFR-021: this module handles message TEXT in memory and in a scratch directory
outside the repo.  Nothing here writes text into a tracked artefact -- callers
must emit counts and rates only.

Spec 1.1: the shim's 256-slot callsign hash table is process-global and never
re-initialised, so parallelism MUST use processes, never threads, and each
worker must decode a contiguous chronological partition, running every variant
of a file consecutively before moving on.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sys
import wave

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.dirname(__file__))

from t1_frequency_quantisation import load, WINDOW_20M, LEG_20M  # noqa: E402

# ── Pinned decoder identity (spec 1) ─────────────────────────────────────────
DLL_REL = os.path.join("native", "ft8_lib_build", "libft8.dll")
DLL_PATH = os.path.join(REPO_ROOT, DLL_REL)
DLL_SHA256 = "39aa1031ad63fd7c882ae9093a3d6c4d681f1c45e2a4f3b4336ff6c3f45e0aba"
SHIM_VERSION = 20260035

WAV_DIR = os.path.join(REPO_ROOT, "artefacts", "20260808_live_run_0016-8080",
                       "wsjt-x", "wav")

BUFFER_SAMPLES = 180_000          # 15 s @ 12 kHz
SAMPLE_RATE = 12_000.0
PROD_TARGET_RMS = 0.20            # Ft8Decoder.cs:52
SILENCE_RMS_THRESHOLD = 1e-6      # Ft8Decoder.cs:51
DECODE_PARAMS = (10, 0.10, 60)    # kMinScorePass2, osdCorrThreshold, osdNhardMax
MAX_RESULTS = 200

REF_EXPECTED = 69222
SEED = 20260809


def dll_sha256(path=DLL_PATH):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Decoder:
    """Thin ctypes wrapper on the production shim.

    One instance per PROCESS.  Never share across threads (spec 1.1).
    """

    def __init__(self, path=DLL_PATH, verify=True):
        if verify:
            got = dll_sha256(path)
            if got != DLL_SHA256:
                raise RuntimeError(
                    "DLL SHA256 mismatch: expected %s got %s -- five unmerged "
                    "branches carry rebuilt DLLs and FT8_SHIM_VERSION collides "
                    "twice, so refusing to run on an unidentified binary"
                    % (DLL_SHA256, got))
        self.dll = ctypes.CDLL(os.path.abspath(path))
        d = self.dll

        class FT8Result(ctypes.Structure):
            _fields_ = [("freq_hz", ctypes.c_int), ("dt", ctypes.c_float),
                        ("snr", ctypes.c_int), ("message", ctypes.c_char * 36)]

        self.FT8Result = FT8Result
        d.ft8_lib_version_check.restype = ctypes.c_int
        d.ft8_set_decode_params.argtypes = [ctypes.c_int, ctypes.c_float, ctypes.c_int]
        d.ft8_decode_all.restype = ctypes.c_int
        d.ft8_decode_all.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_int,
                                     ctypes.POINTER(FT8Result), ctypes.c_int]

        ver = d.ft8_lib_version_check()
        if verify and ver != SHIM_VERSION:
            raise RuntimeError("shim version %s, expected %s" % (ver, SHIM_VERSION))
        self.version = ver
        d.ft8_set_decode_params(DECODE_PARAMS[0], ctypes.c_float(DECODE_PARAMS[1]),
                                DECODE_PARAMS[2])
        self._results = (FT8Result * MAX_RESULTS)()

    def decode(self, pcm: np.ndarray):
        """pcm: float32 ndarray, exactly BUFFER_SAMPLES. Returns list of dicts."""
        buf = np.ascontiguousarray(pcm, dtype=np.float32)
        assert buf.shape == (BUFFER_SAMPLES,), buf.shape
        n = self.dll.ft8_decode_all(
            buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            BUFFER_SAMPLES, self._results, MAX_RESULTS)
        if n < 0:
            return None                      # -2 == native AV caught by the shim's SEH
        return [{"freq_hz": self._results[i].freq_hz,
                 "dt": float(self._results[i].dt),
                 "snr": self._results[i].snr,
                 "message": self._results[i].message.decode("ascii", "replace").strip()}
                for i in range(n)]


# ── Audio ────────────────────────────────────────────────────────────────────

def read_wav(path) -> np.ndarray:
    """Mono 16-bit 12 kHz -> float32 in int16 units, padded/truncated to buffer."""
    with wave.open(path, "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2 or w.getframerate() != 12000:
            raise RuntimeError("unexpected WAV format: %s" % path)
        a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32)
    if a.size < BUFFER_SAMPLES:
        a = np.pad(a, (0, BUFFER_SAMPLES - a.size))
    return a[:BUFFER_SAMPLES]


def normalise_rms(pcm: np.ndarray, target_rms: float) -> np.ndarray:
    """Mirror Ft8Decoder.NormalisePcm exactly, including the silence guard."""
    src = float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2)))
    if src < SILENCE_RMS_THRESHOLD:
        return pcm
    return (pcm * (target_rms / src)).astype(np.float32)


def freq_shift(pcm: np.ndarray, delta_hz: float) -> np.ndarray:
    """Translate the whole buffer by delta_hz via the analytic signal.

    Real -> Hilbert -> multiply by exp(2*pi*i*delta*t) -> real part.
    """
    if delta_hz == 0.0:
        return pcm
    from scipy.signal import hilbert
    n = pcm.size
    t = np.arange(n, dtype=np.float64) / SAMPLE_RATE
    analytic = hilbert(pcm.astype(np.float64))
    return np.real(analytic * np.exp(2j * np.pi * delta_hz * t)).astype(np.float32)


def time_shift(pcm: np.ndarray, samples: int) -> np.ndarray:
    """Integer sample shift with ZERO fill (never wraparound)."""
    if samples == 0:
        return pcm
    out = np.zeros_like(pcm)
    if samples > 0:
        out[samples:] = pcm[:-samples]
    else:
        out[:samples] = pcm[-samples:]
    return out


# ── Populations ──────────────────────────────────────────────────────────────

def in_window_files(window=WINDOW_20M):
    lo, hi = window
    out = []
    for fn in sorted(os.listdir(WAV_DIR)):
        if not fn.endswith(".wav"):
            continue
        ts = fn[:-4]
        if lo <= ts <= hi:
            out.append((ts, os.path.join(WAV_DIR, fn)))
    return out


def load_ref(window=WINDOW_20M):
    """REF = intersection of the two WSJT-X instances; also returns freq map."""
    a = load(os.path.join(REPO_ROOT, LEG_20M["wsjtx_a"]), *window)
    b = load(os.path.join(REPO_ROOT, LEG_20M["wsjtx_b"]), *window)
    ref = {k: a[k] for k in a.keys() & b.keys()}
    return ref


def cluster_bootstrap(ref_freq, member_fns, n_draws=1000, seed=SEED):
    """Frequency-clustered bootstrap (HK-021(i)), PAIRED across metrics.

    ref_freq   : {key -> freq_hz} for every REF key
    member_fns : {name -> set(keys)} numerator sets, all over the same REF
    Resamples distinct frequencies ONCE per draw and recomputes every named
    metric on that same cluster set, so differences between them are paired.
    Returns {name: {mean, se, ci95}}.
    """
    byf = {}
    for k, f in ref_freq.items():
        byf.setdefault(f, []).append(k)
    freqs = list(byf)
    rng = np.random.default_rng(seed)
    acc = {name: [] for name in member_fns}
    for _ in range(n_draws):
        pick = rng.choice(len(freqs), size=len(freqs), replace=True)
        keys = []
        for i in pick:
            keys.extend(byf[freqs[i]])
        denom = len(keys)
        if denom == 0:
            continue
        for name, s in member_fns.items():
            acc[name].append(100.0 * sum(1 for k in keys if k in s) / denom)
    out = {}
    for name, vals in acc.items():
        v = np.array(vals)
        out[name] = {"mean": float(v.mean()), "se": float(v.std(ddof=1)),
                     "ci95": [float(np.percentile(v, 2.5)),
                              float(np.percentile(v, 97.5))],
                     "n_draws": len(v), "n_distinct_freq": len(freqs), "seed": seed}
    return out


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
    os.replace(tmp, path)
