#!/usr/bin/env python3
"""G2A-REMEASURE-A -- offline single-process replay of the 2026-08-03 corpus's
OWSFZ-side WAVs through one pinned DLL, in strict chronological order.

Spec: qa/rr-study/2026-08-23-2127-architect-to-qa-spec-g2a-remeasure-a.md
Amendment: qa/rr-study/2026-08-25-1550-architect-to-qa-null-validity-finding-and-g2a-remeasure-amendment.md

Deliberately single-process, single-threaded, strict chronological order --
NOT chunked/parallelised across workers. The callsign hash table is
process-global and never re-initialised (confirmed: no reset export exists
on any candidate DLL), and hash-marker resolution is exactly the
order-dependent, whole-session-stateful behaviour this arm measures. Chunked
parallel replay would let one worker's chunk never see a callsign another
worker's chunk resolved first, systematically INFLATING the unresolved-hash
rate relative to a true single continuous process (which is what both the
live daemon and this arm's L0 historical capture are) -- that would bias
Part A's H statistic and Part B's B1 bucket directly, not just add a
descriptive caveat. Slow (~1s/cycle empirically) is the honest cost of
measuring this correctly; see the arm's report for the wall-clock accounting.

NFR-021: output goes to artefacts/ (blanket-gitignored), not qa/. Message
text lives in this process and that output file only; the results/ JSON
under qa/rr-study/g2a-remeasure-a/ that summarises this leg contains counts
and rates only, never message text -- enforced by analyse.py reading THIS
file fresh and discarding text after deriving message_norm/has_hash, exactly
as qa/rr-study/gap-census-a/common.py does for L0.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import sys
import time
import wave

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
WAV_DIR = os.path.join(REPO_ROOT, "artefacts", "20260803_live_run_1713", "owsfz", "wav")

BUFFER_SAMPLES = 180_000  # 15 s @ 12 kHz
PROD_TARGET_RMS = 0.20  # Ft8Decoder.cs:52
SILENCE_RMS_THRESHOLD = 1e-6  # Ft8Decoder.cs:51
DECODE_PARAMS = (10, 0.10, 60)  # kMinScorePass2, osdCorrThreshold, osdNhardMax -- production defaults
MAX_RESULTS = 200


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_wav(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2 or w.getframerate() != 12000:
            raise RuntimeError("unexpected WAV format: %s" % path)
        a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32)
    if a.size < BUFFER_SAMPLES:
        a = np.pad(a, (0, BUFFER_SAMPLES - a.size))
    return a[:BUFFER_SAMPLES]


def normalise_rms(pcm: np.ndarray, target_rms: float) -> np.ndarray:
    src = float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2)))
    if src < SILENCE_RMS_THRESHOLD:
        return pcm
    return (pcm * (target_rms / src)).astype(np.float32)


class Decoder:
    def __init__(self, path: str, expected_sha256: str, expected_shim_version: int):
        got = sha256_of(path)
        if got != expected_sha256:
            raise RuntimeError("DLL SHA256 mismatch: expected %s got %s (%s)"
                                % (expected_sha256, got, path))
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
        if ver != expected_shim_version:
            raise RuntimeError("shim version %s, expected %s" % (ver, expected_shim_version))
        self.version = ver
        self.sha256 = got
        d.ft8_set_decode_params(DECODE_PARAMS[0], ctypes.c_float(DECODE_PARAMS[1]), DECODE_PARAMS[2])
        self._results = (FT8Result * MAX_RESULTS)()

        self._has_reject_ctr = hasattr(d, "ft8_get_hash_table_reject_count")
        if self._has_reject_ctr:
            d.ft8_get_hash_table_reject_count.restype = ctypes.c_int

    def decode(self, pcm: np.ndarray):
        buf = np.ascontiguousarray(pcm, dtype=np.float32)
        assert buf.shape == (BUFFER_SAMPLES,), buf.shape
        n = self.dll.ft8_decode_all(
            buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            BUFFER_SAMPLES, self._results, MAX_RESULTS)
        if n < 0:
            return None  # -2 == native AV caught by the shim's SEH
        return [{"freq_hz": self._results[i].freq_hz,
                  "dt": float(self._results[i].dt),
                  "snr": self._results[i].snr,
                  "message": self._results[i].message.decode("ascii", "replace").strip()}
                 for i in range(n)]

    def reject_count(self):
        if not self._has_reject_ctr:
            return None
        return int(self.dll.ft8_get_hash_table_reject_count())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll", required=True)
    ap.add_argument("--sha256", required=True)
    ap.add_argument("--shim-version", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=None,
                     help="debug only -- decode only the first N files (chronological)")
    args = ap.parse_args()

    wavs = sorted(f for f in os.listdir(WAV_DIR) if f.endswith(".wav"))
    if args.limit:
        wavs = wavs[: args.limit]

    dec = Decoder(args.dll, args.sha256, args.shim_version)
    print("Decoder loaded: %s  sha256=%s  shim=%d  reject_ctr_export=%s"
          % (args.dll, dec.sha256, dec.version, dec._has_reject_ctr), flush=True)
    print("WAV_DIR=%s  n_wavs=%d" % (WAV_DIR, len(wavs)), flush=True)

    native_av_count = 0
    per_av_files = []
    records = []  # list of {ts, freq_hz, dt, snr, message}
    n_av = 0
    t0 = time.time()
    for i, fn in enumerate(wavs):
        ts = fn[:-4]
        path = os.path.join(WAV_DIR, fn)
        pcm = read_wav(path)
        pcm = normalise_rms(pcm, PROD_TARGET_RMS)
        res = dec.decode(pcm)
        if res is None:
            n_av += 1
            per_av_files.append(fn)
            continue
        for r in res:
            records.append({"ts": ts, "freq_hz": r["freq_hz"], "dt": r["dt"],
                             "snr": r["snr"], "message": r["message"]})
        if (i + 1) % 200 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta_s = (len(wavs) - (i + 1)) / rate if rate > 0 else float("nan")
            print("  [%d/%d] %s  decodes_so_far=%d  elapsed=%.0fs  eta=%.0fs"
                  % (i + 1, len(wavs), fn, len(records), elapsed, eta_s), flush=True)

    elapsed = time.time() - t0
    final_reject = dec.reject_count()
    out = {
        "dll_path": os.path.abspath(args.dll),
        "dll_sha256": dec.sha256,
        "shim_version": dec.version,
        "n_wavs": len(wavs),
        "n_decodes": len(records),
        "n_native_av": n_av,
        "native_av_files": per_av_files,
        "final_hash_table_reject_count": final_reject,
        "wall_seconds": elapsed,
        "records": records,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    os.replace(tmp, args.out)
    print("DONE. n_wavs=%d n_decodes=%d n_native_av=%d final_reject=%s wall=%.0fs -> %s"
          % (len(wavs), len(records), n_av, final_reject, elapsed, args.out), flush=True)


if __name__ == "__main__":
    main()
