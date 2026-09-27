#!/usr/bin/env python3
"""GAP-LOCATE: WAV reading + RMS normalisation, same convention as
g2a-remeasure-a/decode_corpus.py / cycleframer-alignment-replay/p23_common.py
(Ft8Decoder.cs's own NormalisePcm, mirrored exactly -- production target RMS 0.20,
silence guard 1e-6)."""
from __future__ import annotations

import wave

import numpy as np

BUFFER_SAMPLES = 180_000  # 15 s @ 12 kHz
PROD_TARGET_RMS = 0.20
SILENCE_RMS_THRESHOLD = 1e-6


def read_wav(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2 or w.getframerate() != 12000:
            raise RuntimeError("unexpected WAV format: %s" % path)
        a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32)
    if a.size < BUFFER_SAMPLES:
        a = np.pad(a, (0, BUFFER_SAMPLES - a.size))
    return a[:BUFFER_SAMPLES]


def normalise_rms(pcm: np.ndarray, target_rms: float = PROD_TARGET_RMS) -> np.ndarray:
    src = float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2)))
    if src < SILENCE_RMS_THRESHOLD:
        return pcm
    return (pcm * (target_rms / src)).astype(np.float32)


def load_cycle_pcm(path: str) -> np.ndarray:
    return normalise_rms(read_wav(path), PROD_TARGET_RMS)
