"""GAP-CENSUS-A ROW 0f -- confirm sub-f_min reference decodes sit on real
signal, not a reference-decoder artefact, using the RAW WAV SPECTRUM (HK-026:
an instrument may not bound its own blind spot; the reference decoder is the
enumerating instrument here and may not also be the confirming one).

Corpus: artefacts/20260803_live_run_1713/owsfz/wav -- the `owsfz` capture
chain, disclosed choice (not `wsjt-x`): this row is about what enters OUR
pipeline's own aperture, and 2026-08-12's G2(b) review-3 measurement (a
DIFFERENT corpus, 08-08) found the two chains agree to within ~0.4 dB in
exactly this band, so the choice is not load-bearing -- carried forward as a
documented assumption for 08-03, not re-derived from taste, per that review's
own scope note.
"""
from __future__ import annotations

import math
import os
import random
import statistics
import wave

import numpy as np

from common import OURS_WAV_DIR

BAND_LOW_HZ = (140.0, 200.0)         # the bucket-A band under test
NOISE_FLOOR_HZ = (5000.0, 5900.0)    # near Nyquist (fs=12kHz) -- no audio content expected
N_SAMPLE_WAVS = 60                   # matches the 2026-08-12 review-3 convention
SAMPLE_SEED = 20260823

# ROW 0f's own operational bar (the spec states the bar qualitatively --
# "measurably above the noise floor" -- this pins a number while drafting,
# per HK-021(m)): median band power in [140,200) must exceed the median noise
# floor power by at least this many dB.
MARGIN_BAR_DB = 3.0


def _band_power(freqs: np.ndarray, power: np.ndarray, lo: float, hi: float) -> float:
    mask = (freqs >= lo) & (freqs < hi)
    if not mask.any():
        return float("nan")
    return float(power[mask].mean())


def _file_band_powers(path: str) -> tuple[float, float]:
    with wave.open(path, "rb") as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
        fs = w.getframerate()
        raw = w.readframes(w.getnframes())
    x = np.frombuffer(raw, dtype="<i2").astype(np.float64)
    window = np.hanning(len(x))
    xw = x * window
    spec = np.fft.rfft(xw)
    power = (spec.real ** 2 + spec.imag ** 2)
    freqs = np.fft.rfftfreq(len(x), d=1.0 / fs)
    p_low = _band_power(freqs, power, *BAND_LOW_HZ)
    p_floor = _band_power(freqs, power, *NOISE_FLOOR_HZ)
    return p_low, p_floor


def row0f(log) -> tuple[bool, dict]:
    if not os.path.isdir(OURS_WAV_DIR):
        log("ROW 0f: VOID -- WAV directory not found: %s" % OURS_WAV_DIR)
        return False, {}

    all_wavs = sorted(f for f in os.listdir(OURS_WAV_DIR) if f.lower().endswith(".wav"))
    rng = random.Random(SAMPLE_SEED)
    sample = sorted(rng.sample(all_wavs, min(N_SAMPLE_WAVS, len(all_wavs))))

    db_low = []
    db_floor = []
    db_margin = []
    for fname in sample:
        p_low, p_floor = _file_band_powers(os.path.join(OURS_WAV_DIR, fname))
        if p_low <= 0 or p_floor <= 0:
            continue
        dl = 10.0 * math.log10(p_low)
        df = 10.0 * math.log10(p_floor)
        db_low.append(dl)
        db_floor.append(df)
        db_margin.append(dl - df)

    if not db_margin:
        log("ROW 0f: VOID -- no usable WAV files in sample")
        return False, {}

    median_low = statistics.median(db_low)
    median_floor = statistics.median(db_floor)
    median_margin = statistics.median(db_margin)

    log("ROW 0f: n_wavs_sampled=%d chain=owsfz" % len(sample))
    log("ROW 0f: median power [140,200) = %.2f dB (arbitrary ref)" % median_low)
    log("ROW 0f: median power [5000,5900) noise floor = %.2f dB (arbitrary ref)" % median_floor)
    log("ROW 0f: median margin ([140,200) - noise floor) = %.2f dB, bar = %.1f dB"
        % (median_margin, MARGIN_BAR_DB))

    ok = median_margin >= MARGIN_BAR_DB
    log("ROW 0f: %s" % ("PASS -- confirmed real signal" if ok
                         else "UNCONFIRMED -- bucket A routes to ROW A3"))
    detail = {
        "n_wavs_sampled": len(sample),
        "chain": "owsfz",
        "median_db_140_200": median_low,
        "median_db_noise_floor": median_floor,
        "median_margin_db": median_margin,
        "bar_db": MARGIN_BAR_DB,
    }
    return ok, detail


if __name__ == "__main__":
    ok, detail = row0f(print)
    print(detail)
    raise SystemExit(0 if ok else 1)
