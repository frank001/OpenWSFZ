"""L6 — 16-bit mono PCM WAV writer/reader (stdlib `wave`, no third-party deps)."""
from __future__ import annotations

import wave

import numpy as np

from .constants import DEFAULT_SAMPLE_RATE_HZ

_FULL_SCALE = 32767.0


def write_wav(path: str, samples: np.ndarray, sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
              headroom_db: float = 6.0) -> None:
    """Write float samples to a 16-bit mono WAV, peak-normalised with headroom."""
    peak = float(np.max(np.abs(samples))) or 1.0
    scale = (10.0 ** (-headroom_db / 20.0)) * _FULL_SCALE / peak
    pcm = np.clip(np.round(samples * scale), -32768, 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate_hz)
        w.writeframes(pcm.tobytes())


def read_wav(path: str) -> tuple[np.ndarray, int]:
    """Read a 16-bit mono WAV back to float samples in [-1, 1] and its sample rate."""
    with wave.open(path, "rb") as r:
        fs = r.getframerate()
        frames = r.readframes(r.getnframes())
    pcm = np.frombuffer(frames, dtype="<i2").astype(np.float64) / _FULL_SCALE
    return pcm, fs
