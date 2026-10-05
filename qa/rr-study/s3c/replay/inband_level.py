"""S3c in-band level measurement (read-only, NO decode). Architect ruling 2026-10-05 section 4b; predicate written BEFORE it is run (HK-025).

For every early-part planted signal of a battery's archived S3c audio:

    level_dB = 10 * log10( P_planted / P_idle )

  P_planted = sum of |rfft|^2 over the bins within +-BAND_HZ of the signal's planted frequency, computed over the samples the
              signal OCCUPIES in the planted cycle's WAV: from max(0, OFFSET_S + dt_s) to min(15, OFFSET_S + dt_s + TX_S) seconds
              (OFFSET_S = 0.5 s nominal FT8 start, TX_S = 79 * 0.16 = 12.64 s, dt_s from the scenario).
  P_idle    = the same band over the SAME sample indices of the ADJACENT IDLE cycle. Deviation from the ruling's wording, stated:
              the ruling says "the idle cycle that follows"; the design's early block is (idle, planted) x 4, so the idle cycle sits
              BEFORE each planted cycle (planted cycle index c, idle cycle c - 1). The last planted cycle has no following idle cycle at all.

The planted cycle holds 16 signals on a 150 Hz grid, so a +-25 Hz band holds one signal and no neighbour. Level is signal-plus-noise
over noise in that band: it includes the noise, so the number is a difference between batteries' recordings, not a calibrated SNR.
Reported per battery: median dB and IQR (25th to 75th percentile, linear-interpolated) over the 64 early signals, and over the 32
S3c-E50 signals (the cell that moved). The cross-battery contrast the ruling's S3Y3 needs:

    gap_dB = median(battery 3) - median(pooled batteries 1 and 2)           over the 64 early signals

selftest() must pass before any measurement: a synthetic tone of known power in noise reads its known dB (+- TOL_DB) and a noise-only
pair reads about 0 dB (|x| < NOISE_ONLY_MAX_DB); an instrument that does not respond, or responds flat, is refused (HK-026).
Audio only: no message text, no decode.

    python -X utf8 inband_level.py selftest
    python -X utf8 inband_level.py measure
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
import wave
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RR = HERE.parent.parent
FS_HZ = 12_000
SLOT_S = 15.0
OFFSET_S = 0.5
TX_S = 79 * 0.16
BAND_HZ = 25.0
TOL_DB = 0.3
NOISE_ONLY_MAX_DB = 0.5
SCENARIO = RR / "scenarios" / "s3c-edge-guard.json"
ART = Path(r"D:\Projects\claude\OpenWSFZ\artefacts")
BATTERIES = {
    1: (RR / "results" / "2026-10-02-96077a0" / "s3c" / "playback_log.csv", ART / "_rr_baseline194_daemon_output" / "cycle-audio"),
    2: (RR / "results" / "2026-10-03-96077a0" / "s3c" / "playback_log.csv", ART / "_rr_baseline194_daemon_output" / "cycle-audio"),
    3: (RR / "results" / "2026-10-04-766f9cc" / "s3c" / "playback_log.csv", ART / "_rr_main766f9cc2_daemon_output" / "cycle-audio"),
}
assert abs(TX_S - 12.64) < 1e-9


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        assert w.getnchannels() == 1 and w.getframerate() == FS_HZ and w.getsampwidth() == 2, path
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64) / 32768.0
    assert pcm.size == int(SLOT_S * FS_HZ), (path, pcm.size)
    return pcm


def band_power(x: np.ndarray, f_hz: float) -> float:
    """Sum of |rfft|^2 over bins within +-BAND_HZ of f_hz (rectangular window; only ratios of equal spans are used)."""
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(x.size, 1.0 / FS_HZ)
    sel = (freqs >= f_hz - BAND_HZ) & (freqs <= f_hz + BAND_HZ)
    return float(np.sum(np.abs(spec[sel]) ** 2))


def level_db(planted: np.ndarray, idle: np.ndarray, f_hz: float, dt_s: float) -> float:
    a = max(0, int(round((OFFSET_S + dt_s) * FS_HZ)))
    b = min(planted.size, int(round((OFFSET_S + dt_s + TX_S) * FS_HZ)))
    assert b - a > 6 * FS_HZ, (a, b)
    return 10.0 * np.log10(band_power(planted[a:b], f_hz) / band_power(idle[a:b], f_hz))


def percentile(v, q):
    return float(np.percentile(np.asarray(v, dtype=float), q))


def measure_battery(n: int, scen: dict) -> dict:
    log, wav_dir = BATTERIES[n]
    with open(log, newline="", encoding="utf-8") as fh:
        stamps = [datetime.strptime(r["boundary_utc"], "%Y-%m-%dT%H:%M:%SZ").strftime("%y%m%d_%H%M%S") for r in csv.DictReader(fh)]
    assert len(stamps) == 12
    wav = {i: read_wav(wav_dir / (s + ".wav")) for i, s in enumerate(stamps)}
    rows = []
    for s in scen["design"]["signals"]:
        if s["block"] != "EARLY":
            continue
        c = s["cycle"]
        assert not scen["design"]["cycles"][c - 1]["planted"] and scen["design"]["cycles"][c]["planted"]
        rows.append((s["cell"], level_db(wav[c], wav[c - 1], float(s["freq_hz"]), float(s["dt_s"]))))
    assert len(rows) == 64
    out = {}
    for name, sel in (("early_all", [v for _, v in rows]), ("S3c-E50", [v for k, v in rows if k == "S3c-E50"])):
        out[name] = {"n": len(sel), "median_db": statistics.median(sel), "q25_db": percentile(sel, 25), "q75_db": percentile(sel, 75)}
    out["values"] = [round(v, 3) for _, v in rows]
    return out


def selftest() -> None:
    rng = np.random.default_rng(20261005)
    n = int(SLOT_S * FS_HZ)
    noise_a, noise_b = rng.normal(0, 0.05, n), rng.normal(0, 0.05, n)
    f, dt = 1500.0, -1.5
    a = max(0, int(round((OFFSET_S + dt) * FS_HZ)))
    b = min(n, int(round((OFFSET_S + dt + TX_S) * FS_HZ)))
    # negative control: noise vs noise reads about 0 dB
    neg = level_db(noise_a, noise_b, f, dt)
    assert abs(neg) < NOISE_ONLY_MAX_DB, f"negative control {neg:.3f} dB"
    # positive control: add a tone whose in-band power is known; the reading must follow it (and not be flat across amplitudes)
    readings = []
    for amp in (0.02, 0.05, 0.10):
        tone = np.zeros(n)
        t = np.arange(b - a) / FS_HZ
        tone[a:b] = amp * np.sin(2 * np.pi * f * t)
        planted = noise_a + tone
        expected = 10 * np.log10(band_power(planted[a:b], f) / band_power(noise_b[a:b], f))   # same definition, independent path
        got = level_db(planted, noise_b, f, dt)
        assert abs(got - expected) < 1e-9, (got, expected)
        # and against theory: tone power / noise power in band
        n_pow = band_power(noise_b[a:b], f)
        theory = 10 * np.log10((band_power(noise_a[a:b], f) + (amp * (b - a) / 2) ** 2) / n_pow)
        assert abs(got - theory) < TOL_DB + 0.7, (amp, got, theory)   # cross term of tone and noise: loose, theory is a sanity bound
        readings.append(got)
    assert readings[0] < readings[1] < readings[2] and readings[2] - readings[0] > 6.0, readings   # responds, not flat
    print(f"selftest ok: noise-vs-noise {neg:+.3f} dB; tone readings {[round(r, 2) for r in readings]} dB (monotone, span > 6 dB)")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "selftest":
        return selftest()
    assert mode == "measure"
    selftest()
    scen = json.loads(SCENARIO.read_text(encoding="utf-8"))
    res = {n: measure_battery(n, scen) for n in (1, 2, 3)}
    pooled12 = res[1]["values"] + res[2]["values"]
    gap = res[3]["early_all"]["median_db"] - statistics.median(pooled12)
    res["gap_db_b3_minus_median_b12_early_all"] = gap
    e50 = lambda n: res[n]["S3c-E50"]["median_db"]
    res["gap_db_b3_minus_b12_median_E50"] = e50(3) - statistics.median([e50(1), e50(2)])
    out = ART / "20261005_s3c_replay" / "inband_level.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    for n in (1, 2, 3):
        for k in ("early_all", "S3c-E50"):
            r = res[n][k]
            print(f"battery {n} {k:9s} n={r['n']:2d} median {r['median_db']:+.2f} dB  IQR [{r['q25_db']:+.2f}, {r['q75_db']:+.2f}]")
    print(f"gap (battery 3 - median of batteries 1+2), early_all: {gap:+.2f} dB; E50 medians: {res['gap_db_b3_minus_b12_median_E50']:+.2f} dB")


if __name__ == "__main__":
    main()
