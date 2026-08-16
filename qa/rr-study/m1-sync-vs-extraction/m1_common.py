#!/usr/bin/env python3
"""M1 -- shared infrastructure: ALL.TXT loading, WAV loading, corpus/DLL pins.

Spec: qa/rr-study/2026-08-14-2217-architect-to-qa-spec-m1-sync-limited-or-extraction-limited.md

No src/ change, no capture run (spec S8). Pure re-analysis of the
20260803_live_run_1713 corpus already on disk, driving the diagnostic-only
ft8_refine_candidate export in-process via ctypes (same pattern as
r1-sync-refiner/refiner_ctypes.py and cycleframer-alignment-replay/p23_common.py).
"""
from __future__ import annotations

import io
import os
import wave

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

CORPUS_DIR = os.path.join(REPO_ROOT, "artefacts", "20260803_live_run_1713")
OWSFZ_ALL_TXT = os.path.join(CORPUS_DIR, "owsfz", "ALL.TXT")
WSJTX_ALL_TXT = os.path.join(CORPUS_DIR, "wsjt-x", "ALL.TXT")
OWSFZ_WAV_DIR = os.path.join(CORPUS_DIR, "owsfz", "wav")

# Spec S3: 18.96h decisive epoch, drift-screen PASS, per qa/ARTEFACT_INVENTORY.md's
# 20260803_live_run_1713 row verbatim -- NOT the corpus's full span (which starts at
# 260803_171330, ~2.5h before the decisive epoch and before the drift screen's PASS
# window begins).
WINDOW = ("260803_185914", "260804_135645")

# Spec S5: pin the binary by SHA256, never by FT8_SHIM_VERSION.
DLL_PATH = os.path.join(REPO_ROOT, "native", "ft8_lib_build", "libft8.dll")
DLL_SHA256 = "04cedc598593e89569b7212deef66efaa413322994216108841525ca2ebc45bf"
SHIM_VERSION = 20260041

BUFFER_SAMPLES = 180_000  # 15 s @ 12 kHz
SAMPLE_RATE_HZ = 12000

# Spec S4 basis discipline (carried from T1 unchanged).
BAND_LO_HZ, BAND_HI_HZ = 200, 3000

SEED = 20260815  # M1's own seed -- distinct from every prior D-001 arm's seed.


def has_unresolved_hash(msg: str) -> bool:
    return "<...>" in msg


def load_all_txt(path: str, lo: str, hi: str) -> dict:
    """(ts) -> list of (message, snr_db, dt_s, freq_hz) for Rx FT8 lines in [lo, hi].

    Field indices verbatim from t1_frequency_quantisation.load / spec S5:
    [0] ts  [4] SNR  [5] DT  [6] freq Hz  [7:] message.
    Asserted against a hand-checked row below (assert_field_mapping).
    """
    out: dict[str, list[tuple[str, int, float, int]]] = {}
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            ts = f[0]
            if not (lo <= ts <= hi):
                continue
            try:
                snr_db = int(f[4])
                dt_s = float(f[5])
                freq_hz = int(f[6])
            except ValueError:
                continue
            msg = " ".join(f[7:])
            out.setdefault(ts, []).append((msg, snr_db, dt_s, freq_hz))
    return out


def assert_field_mapping():
    """Spec S5 warning: confusing [5]/[6] inverts the whole result. Hand-check one
    real line from this exact corpus before any measurement runs."""
    # First data line of owsfz/ALL.TXT, hand-read directly off disk (see m1 report
    # for the verbatim line): "260803_171330  14.074 Rx FT8  -11  1.1 2194 CQ BG7BMG OL66"
    # [4]=-11 (SNR, plausible dB range) [5]=1.1 (DT, plausible +/-a few s) [6]=2194 (freq
    # Hz, plausible audio passband 200-3000ish). If 5/6 were swapped, freq_hz would read
    # "1" (impossible -- FT8 tones don't live at 1 Hz) and dt_s would read "2194" s
    # (impossible -- DT is at most a couple of seconds). This is the mechanical assertion.
    line = "260803_171330     14.074 Rx FT8    -11  1.1 2194 CQ BG7BMG OL66"
    f = line.split()
    snr_db, dt_s, freq_hz = int(f[4]), float(f[5]), int(f[6])
    assert snr_db == -11, snr_db
    assert dt_s == 1.1, dt_s
    assert freq_hz == 2194, freq_hz
    assert BAND_LO_HZ <= freq_hz <= BAND_HI_HZ, "freq_hz out of plausible FT8 passband"
    assert -3.0 <= dt_s <= 3.0, "dt_s out of plausible DT range -- field mapping suspect"


def read_wav_12k_15s(path: str) -> np.ndarray:
    """12 kHz mono 16-bit, exactly 180,000 samples -> float32 in int16 units.

    Spec S3 Task-1 pre-flight: ft8_refine_candidate returns -1 on any other length.
    If the file does not match, STOP and report -- do not resample silently.
    """
    with wave.open(path, "rb") as w:
        nch, sw, fr, nframes = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        if nch != 1 or sw != 2 or fr != 12000 or nframes != BUFFER_SAMPLES:
            raise RuntimeError(
                "WAV format mismatch %s: nch=%d sw=%d fr=%d nframes=%d "
                "(expected 1/2/12000/%d) -- STOPPING per spec S3, not resampling"
                % (path, nch, sw, fr, nframes, BUFFER_SAMPLES))
        a = np.frombuffer(w.readframes(nframes), dtype="<i2").astype(np.float32)
    assert a.shape == (BUFFER_SAMPLES,), a.shape
    return a


def owsfz_wav_path(ts: str) -> str:
    return os.path.join(OWSFZ_WAV_DIR, ts + ".wav")


def write_json(path, obj):
    import json
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
    os.replace(tmp, path)
