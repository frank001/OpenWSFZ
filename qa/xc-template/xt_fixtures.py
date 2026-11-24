#!/usr/bin/env python3
"""XC-BUILD fixtures for the Developer's unit tests (dev task 2026-11-13-xc-template-build).  Deterministic, language-neutral: a 12 kHz, 180,000-sample buffer built from a xorshift32 noise source and a phase-continuous
8-FSK message, plus the expected S_E* / argmax from the desk detector (xt_lib.search, the reference implementation) for several cases, the 61 low-pass taps, and a few baseband checkpoints.
    python xt_fixtures.py   -> dev-tasks/2026-11-13-xc-template-fixtures.json    (all numbers; no message text: the 'message' is a tone list)"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "rr-study", "n2-coherent-llr-extractor"))
import coherent_extract as CE   # noqa: E402
import xt_lib as L              # noqa: E402

FS, N, SPSYM = 12000, 180000, 1920
CALIB = 0.48
SEED_NOISE = 20261113
NOISE_STD, SIG_AMP = 1.0, 0.5
F0, DT0 = 1000.0, 0.52          # base frequency (tone 0) and WSJT-X-convention dt: start = (DT0 + CALIB) * 12000 = 12,000 samples
TONES_SEED = 12345


def xorshift32(state):
    state ^= (state << 13) & 0xFFFFFFFF
    state ^= state >> 17
    state ^= (state << 5) & 0xFFFFFFFF
    return state & 0xFFFFFFFF


def tones(seed):
    s, out = seed, []
    for _ in range(79):
        s = xorshift32(s)
        out.append(int(s % 8))
    return out


def build_pcm(tn, signal=True):
    s = SEED_NOISE
    x = np.empty(N, dtype=np.float64)
    for i in range(N):
        s = xorshift32(s)
        u = (s + 0.5) / 4294967296.0
        x[i] = (u - 0.5) * 2.0 * np.sqrt(3.0) * NOISE_STD          # uniform with the stated standard deviation
    if signal:
        start = int(round((DT0 + CALIB) * FS))
        ph = 0.0
        for k, t in enumerate(tn):
            f = F0 + 6.25 * t
            i = np.arange(SPSYM)
            x[start + k * SPSYM:start + (k + 1) * SPSYM] += SIG_AMP * np.cos(ph + 2 * np.pi * f * i / FS)
            ph = (ph + 2 * np.pi * f * SPSYM / FS) % (2 * np.pi)
    return x.astype(np.float32)


def main():
    tn = tones(TONES_SEED)
    wrong = tones(TONES_SEED + 1)
    pcm = build_pcm(tn)
    noise_only = build_pcm(tn, signal=False)
    cases = []

    def case(name, buf, tones_, fc, dtc):
        S, arg = L.search(CE, buf, fc, dtc, tones_, CALIB)
        cases.append({"name": name, "buffer": "signal" if buf is pcm else "noise_only", "tones": "message" if tones_ is tn else "wrong_message", "centre_freq_hz": fc, "centre_dt_s": dtc,
                      "expected_S_E_star": S, "expected_argmax_freq_hz": arg[0], "expected_argmax_dt_s": arg[1]})

    case("found_inside_window", pcm, tn, F0 + 1.5, DT0 + 0.05)
    case("found_at_centre", pcm, tn, F0, DT0)
    case("window_corner", pcm, tn, F0 + 3.0, DT0 + 0.12)
    case("wrong_message_same_place", pcm, wrong, F0 + 1.5, DT0 + 0.05)
    case("noise_only", noise_only, tn, F0, DT0)
    case("outside_window_frequency", pcm, tn, F0 + 12.5, DT0)
    case("outside_window_time", pcm, tn, F0, DT0 + 0.40)
    # per-symbol bin powers at the exact position (centre = truth): (79, 8), for locating a porting error
    bb = CE.downconvert_decimate(pcm, F0)
    X = CE.correlate_symbols(bb, int(round((DT0 + CALIB) * L.FS_OUT)))
    P = (X.real ** 2 + X.imag ** 2)
    ck = [100, 5000, 12000, 20000]
    fx = {"description": "Fixtures for XC-BUILD R5: buffer = xorshift32 uniform noise (std 1.0) + a phase-continuous 8-FSK message; all expected values from qa/xc-template/xt_lib.py (the desk detector), computed in float64 from the float32 buffer.",
          "sample_rate_hz": FS, "samples": N, "samples_per_symbol": SPSYM, "tone_spacing_hz": 6.25, "decimation": 6, "baseband_rate_hz": FS // 6,
          "noise": {"generator": "xorshift32: s ^= s << 13; s ^= s >> 17; s ^= s << 5 (all 32-bit, unsigned); u = (s + 0.5) / 2^32; sample = (u - 0.5) * 2 * sqrt(3) * 1.0; the state advances once per sample, starting from the seed, sample 0 uses the first advance",
                    "seed": SEED_NOISE},
          "signal": {"base_freq_hz": F0, "dt_wsjtx_s": DT0, "start_sample": int(round((DT0 + CALIB) * FS)), "amplitude": SIG_AMP,
                     "synthesis": "for symbol k at samples [start + k*1920, start + (k+1)*1920): x += amp * cos(phase + 2*pi*(F0 + 6.25*tone[k]) * i / 12000), i = 0..1919; after each symbol phase = (phase + 2*pi*(F0 + 6.25*tone[k]) * 1920 / 12000) mod 2*pi (float64)",
                     "tone_generator": "xorshift32 from the tone seed, 79 draws, tone = s % 8 (state advanced before each draw)", "tone_seed_message": TONES_SEED, "tone_seed_wrong_message": TONES_SEED + 1,
                     "message_tones": tn, "wrong_message_tones": wrong},
          "calibration_start_minus_dt_s": CALIB, "start_sample_2khz_formula": "round((dt_centre + dt_offset + calibration) * 2000)",
          "search": {"df_hz": L.df_grid(), "dt_s": [round(x, 2) for x in L.dt_grid()], "statistic": "S_E = mean over 79 symbols of P[tone_k] / (sum_b P[b] / 8); a symbol with no power counts 1; S_E* = the maximum over the 13 x 25 grid"},
          "lowpass_taps_61": [float(x) for x in CE._TAPS_FINE],
          "lowpass_design": "Hann-windowed sinc, 61 taps, cutoff 900 Hz at fs 12000 Hz, unit DC gain: see coherent_extract.design_lowpass_hann",
          "baseband_checkpoints": {"carrier_hz": F0, "note": "downconvert_decimate(pcm, 1000.0): output index m of the 2 kHz stream (complex)", "indices": ck, "values_re_im": [[float(bb[i].real), float(bb[i].imag)] for i in ck]},
          "per_symbol_bin_powers_at_truth": {"note": "P[k][b] = |X_k[b]|^2 at start sample 2000*(dt0 + calibration), carrier F0; 79 x 8", "P": [[float(v) for v in row] for row in P]},
          "cases": cases, "tolerance": {"S_E_star_relative": 1e-3, "argmax_freq_hz": 0.0, "argmax_dt_s": 0.0}}
    out = os.path.join(HERE, "..", "..", "dev-tasks", "2026-11-13-xc-template-fixtures.json")
    json.dump(fx, open(out, "w"), indent=1)
    print("written", os.path.abspath(out), len(json.dumps(fx)) // 1024, "KB")
    for c in cases:
        print(c["name"], round(c["expected_S_E_star"], 4), c["expected_argmax_freq_hz"], round(c["expected_argmax_dt_s"], 2))


if __name__ == "__main__":
    main()
