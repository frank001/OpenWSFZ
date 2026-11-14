#!/usr/bin/env python3
"""XC-BUILD remedy fixtures (Amendment 6, R15): numbers only, no message text.  The buffer recipe, the tone generator, the low-pass taps and the S_E cases are in dev-tasks/2026-11-13-xc-template-fixtures.json (unchanged);
this file adds S_P (the R5 statistic over frame symbols 43..71 only, at the S_E* argmax, no separate search) for the same cases, plus a STALE case: the buffer carries message B, the template is message A, and B
equals A in the sync symbols and in data block 1 (frame symbols 7..35) but is re-drawn from its own xorshift32 seed in data block 2 (frame symbols 43..71).
    python xc_remedy_fixtures.py   -> dev-tasks/2026-11-14-xc-remedy-fixtures.json"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
XT = os.path.join(HERE, "..", "xc-template")
sys.path.insert(0, XT)
sys.path.insert(0, os.path.join(HERE, "..", "rr-study", "n2-coherent-llr-extractor"))
import coherent_extract as CE   # noqa: E402
import xt_fixtures as FX        # noqa: E402
import xt_lib as L              # noqa: E402

BLOCK2 = list(range(43, 72))
BLOCK1 = list(range(7, 36))
SYNC = list(range(0, 7)) + list(range(36, 43)) + list(range(72, 79))
STALE_SEED = 777
assert len(BLOCK2) == 29 and len(BLOCK1) == 29 and len(SYNC) == 21


def stat(X, tones, idx):
    P = X.real ** 2 + X.imag ** 2
    den = P.sum(axis=1) / L.N_TONES
    i = np.asarray(idx)
    num = P[i, np.asarray(tones)[i]]
    d = den[i]
    return float(np.where(d > 0, num / np.where(d > 0, d, 1.0), 1.0).mean())


def search_sp(buf, tones, fc, dtc):
    """S_E* with its argmax and S_P at that argmax (R15), the same 13 x 25 grid as xt_lib.search."""
    bb = CE.downconvert_decimate(buf, float(fc))
    best, arg, sp = -1.0, None, None
    for d in L.df_grid():
        sb = L.shift_baseband(bb, d)
        for e in L.dt_grid():
            X = CE.correlate_symbols(sb, int(round((dtc + e + FX.CALIB) * L.FS_OUT)))
            v = stat(X, tones, range(79))
            if v > best:
                best, arg, sp = v, (fc + d, dtc + e), stat(X, tones, BLOCK2)
    return best, arg, sp


def main():
    tn = FX.tones(FX.TONES_SEED)
    wrong = FX.tones(FX.TONES_SEED + 1)
    other = FX.tones(STALE_SEED)
    stale = list(tn)
    for k in BLOCK2:
        stale[k] = other[k]                      # message B: A's sync and data block 1, its own block 2
    assert [stale[k] for k in SYNC + BLOCK1] == [tn[k] for k in SYNC + BLOCK1]
    pcm = FX.build_pcm(tn)
    pcm_stale = FX.build_pcm(stale)
    noise = FX.build_pcm(tn, signal=False)
    cases = []

    def case(name, buf, tones_, fc, dtc, buffer_name, tones_name):
        S, arg, sp = search_sp(buf, tones_, fc, dtc)
        cases.append({"name": name, "buffer": buffer_name, "tones": tones_name, "centre_freq_hz": fc, "centre_dt_s": dtc,
                      "expected_S_E_star": S, "expected_S_P_at_argmax": sp, "expected_argmax_freq_hz": arg[0], "expected_argmax_dt_s": arg[1]})

    case("found_at_centre", pcm, tn, FX.F0, FX.DT0, "signal", "message")
    case("found_inside_window", pcm, tn, FX.F0 + 1.5, FX.DT0 + 0.05, "signal", "message")
    case("wrong_message_same_place", pcm, wrong, FX.F0 + 1.5, FX.DT0 + 0.05, "signal", "wrong_message")
    case("noise_only", noise, tn, FX.F0, FX.DT0, "noise_only", "message")
    case("STALE_next_message_same_position", pcm_stale, tn, FX.F0, FX.DT0, "signal_stale", "message")
    case("stale_buffer_with_its_own_tones", pcm_stale, stale, FX.F0, FX.DT0, "signal_stale", "stale_message")
    fx = {"description": "Remedy fixtures for XC-BUILD Amendment 6 (R15). Same buffer recipe, noise, taps and grid as dev-tasks/2026-11-13-xc-template-fixtures.json. New: buffer 'signal_stale' = the same recipe with message B's tones "
                         "(B = A in frame symbols 0..6, 7..35, 36..42, 72..78, and re-drawn in 43..71 from xorshift32 seed 777 by the generator 'tone_generator'). S_P = the S_E statistic over frame symbols 43..71 only, "
                         "computed from the same correlations at the S_E* argmax (no separate search). All expected values from qa/xc-build/xc_remedy_fixtures.py (xt_lib grid).",
          "frame_indices": {"sync": SYNC, "data_block_1": BLOCK1, "data_block_2": BLOCK2},
          "stale_message_tones": stale, "stale_seed": STALE_SEED, "cases": cases,
          "tolerance": {"S_E_star_relative": 1e-3, "S_P_relative": 1e-3, "argmax_freq_hz": 0.0, "argmax_dt_s": 0.0}}
    out = os.path.join(HERE, "..", "..", "dev-tasks", "2026-11-14-xc-remedy-fixtures.json")
    json.dump(fx, open(out, "w"), indent=1)
    print("written", os.path.abspath(out))
    for c in cases:
        print("%-36s S_E*=%.3f S_P=%.3f arg=(%.2f, %.2f)" % (c["name"], c["expected_S_E_star"], c["expected_S_P_at_argmax"], c["expected_argmax_freq_hz"], c["expected_argmax_dt_s"]))


if __name__ == "__main__":
    main()
