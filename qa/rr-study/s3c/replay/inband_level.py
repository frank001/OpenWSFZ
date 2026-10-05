"""S3c in-band level measurement (read-only, NO decode). Architect ruling 2026-10-05 section 4b; predicate written BEFORE it is run (HK-025).

PREDICATE (version 2; version 1 is in commit 4211342e and failed, see DEVIATION):

For every early-part planted signal of a battery's archived S3c audio (planted cycle c, frequency f, DT dt_s from the scenario):

    SIGNAL WINDOW = samples [a, b) of the planted cycle's WAV, a = max(0, round((OFFSET_S + dt_s) * FS)),
                    b = min(N, round((OFFSET_S + dt_s + TX_S) * FS))        (OFFSET_S 0.5 s nominal start, TX_S = 79 * 0.16 = 12.64 s)
    NOISE WINDOW  = samples [b + MARGIN, N) of the SAME planted cycle (after the transmission has ended), required >= MIN_NOISE_S long
    power(x, f)   = mean-square power of x inside f +- BAND_HZ = 2 * sum |rfft(x)|^2 over those bins / len(x)^2   (length-independent)
    level_dB      = 10 * log10( power(signal window, f) / power(noise window, f) )     i.e. signal-plus-noise over noise in the band

Also reported, per battery, as context: the absolute in-band power of the signal window and of the noise window in dBFS.
The planted cycle holds 16 signals on a 150 Hz grid, so a +-25 Hz band holds one signal and no neighbour.
Reported per battery: median dB and IQR (25th to 75th percentile) over the 64 early signals, and over the 32 S3c-E50 signals.
Cross-battery contrast for S3Y3 (ruling 4b): gap_dB = median(battery 3) - median(pooled batteries 1 and 2), over the 64 early signals.

DEVIATION FROM THE RULING (stated, with the evidence): the ruling asks for the power "in the idle cycle that follows at the same frequency".
Version 1 implemented the nearest reading of that (the adjacent idle cycle, which in the design's (idle, planted) x 4 early block sits
BEFORE each planted cycle) and FAILED on its first run with a division by zero: the "idle" cycles are about 78 % exact digital zeros (RMS
0.07 against 0.16 in planted cycles) in ALL THREE batteries, because the playback is silent there and only its last ~3.3 s carries the
early-armed audio. There is no noise reference in them. No level number had been seen when the reference was changed. The replacement,
the same planted cycle's own post-transmission tail, is the same continuous noise at the same frequency. The Architect rules on it.

selftest() must pass before any measurement (HK-026: the instrument must respond, and must read about 0 dB on noise alone).
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
MARGIN_S = 0.2
MIN_NOISE_S = 2.0
THEORY_TOL_DB = 1.0
NOISE_ONLY_MAX_DB = 0.7
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
    """Mean-square power of x inside f_hz +- BAND_HZ (rectangular window); independent of len(x)."""
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(x.size, 1.0 / FS_HZ)
    sel = (freqs >= f_hz - BAND_HZ) & (freqs <= f_hz + BAND_HZ)
    return float(2.0 * np.sum(np.abs(spec[sel]) ** 2) / x.size ** 2)


def windows(n: int, dt_s: float) -> tuple[int, int, int]:
    a = max(0, int(round((OFFSET_S + dt_s) * FS_HZ)))
    b = min(n, int(round((OFFSET_S + dt_s + TX_S) * FS_HZ)))
    c = b + int(round(MARGIN_S * FS_HZ))
    assert b - a > 6 * FS_HZ and (n - c) >= MIN_NOISE_S * FS_HZ, (a, b, c, n)
    return a, b, c


def level_db(cyc: np.ndarray, f_hz: float, dt_s: float) -> tuple[float, float, float]:
    """(level dB, signal-window power dBFS, noise-window power dBFS)."""
    a, b, c = windows(cyc.size, dt_s)
    ps, pn = band_power(cyc[a:b], f_hz), band_power(cyc[c:], f_hz)
    return 10 * np.log10(ps / pn), 10 * np.log10(ps), 10 * np.log10(pn)


def percentile(v, q):
    return float(np.percentile(np.asarray(v, dtype=float), q))


def summarise(vals):
    return {"n": len(vals), "median_db": statistics.median(vals), "q25_db": percentile(vals, 25), "q75_db": percentile(vals, 75)}


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
        assert scen["design"]["cycles"][s["cycle"]]["planted"]
        rows.append((s["cell"],) + level_db(wav[s["cycle"]], float(s["freq_hz"]), float(s["dt_s"])))
    assert len(rows) == 64
    out = {"early_all": summarise([r[1] for r in rows]),
           "S3c-E50": summarise([r[1] for r in rows if r[0] == "S3c-E50"]),
           "signal_window_dbfs_median": statistics.median(r[2] for r in rows),
           "noise_window_dbfs_median": statistics.median(r[3] for r in rows),
           "values": [round(r[1], 3) for r in rows]}
    return out


def selftest() -> None:
    rng = np.random.default_rng(20261005)
    n = int(SLOT_S * FS_HZ)
    sigma, f, dt = 0.05, 1500.0, -1.5
    a, b, c = windows(n, dt)
    noise_pow = sigma ** 2 * (2 * BAND_HZ) / (FS_HZ / 2)               # white noise: variance x band width / (fs / 2)
    # negative control: noise alone reads about 0 dB (averaged over frequencies, single reads scatter by ~ +-0.4 dB)
    negs = [level_db(rng.normal(0, sigma, n), fq, dt)[0] for fq in (300, 600, 900, 1200, 1500, 1800, 2100, 2400)]
    assert abs(float(np.mean(negs))) < NOISE_ONLY_MAX_DB and max(abs(v) for v in negs) < 1.5, negs
    # positive control: a tone of known amplitude inside the signal window reads its known level, and the readings rise with it
    readings = []
    for amp in (0.01, 0.02, 0.05):
        x = rng.normal(0, sigma, n)
        t = np.arange(b - a) / FS_HZ
        x[a:b] += amp * np.sin(2 * np.pi * f * t)
        got = level_db(x, f, dt)[0]
        theory = 10 * np.log10((noise_pow + amp ** 2 / 2) / noise_pow)
        assert abs(got - theory) < THEORY_TOL_DB, (amp, got, theory)
        readings.append(got)
    assert readings[0] < readings[1] < readings[2] and readings[2] - readings[0] > 6.0, readings
    print(f"selftest ok: noise-only mean {np.mean(negs):+.3f} dB (max |x| {max(abs(v) for v in negs):.2f}); "
          f"tone readings {[round(float(r), 2) for r in readings]} dB vs theory, monotone, span > 6 dB")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "selftest":
        return selftest()
    assert mode == "measure"
    selftest()
    scen = json.loads(SCENARIO.read_text(encoding="utf-8"))
    res = {n: measure_battery(n, scen) for n in (1, 2, 3)}
    pooled12 = res[1]["values"] + res[2]["values"]
    res["gap_db_b3_minus_median_b12_early_all"] = res[3]["early_all"]["median_db"] - statistics.median(pooled12)
    res["gap_db_b3_minus_b12_median_E50"] = res[3]["S3c-E50"]["median_db"] - statistics.median(
        [res[1]["S3c-E50"]["median_db"], res[2]["S3c-E50"]["median_db"]])
    out = ART / "20261005_s3c_replay" / "inband_level.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    for n in (1, 2, 3):
        for k in ("early_all", "S3c-E50"):
            r = res[n][k]
            print(f"battery {n} {k:9s} n={r['n']:2d} median {r['median_db']:+.2f} dB  IQR [{r['q25_db']:+.2f}, {r['q75_db']:+.2f}]")
        print(f"          context: signal window {res[n]['signal_window_dbfs_median']:.2f} dBFS, noise window {res[n]['noise_window_dbfs_median']:.2f} dBFS (medians)")
    print(f"gap (battery 3 - median of batteries 1+2): early_all {res['gap_db_b3_minus_median_b12_early_all']:+.2f} dB; "
          f"E50 {res['gap_db_b3_minus_b12_median_E50']:+.2f} dB")


if __name__ == "__main__":
    main()
