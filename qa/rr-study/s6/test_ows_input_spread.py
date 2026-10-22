"""Unit tests for ows_input_spread.py on a toy set (synthetic noise; no callsigns)."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import archive_xcorr as X  # noqa: E402
import ows_input_spread as I  # noqa: E402

FS = X.FS


def noise(seconds, seed):
    return (np.random.default_rng(seed).standard_normal(int(seconds * FS)) * 3000).astype(np.float32)


def test_offset_is_recovered_from_a_shifted_window(tmp_path):
    play = noise(13, 1)
    # one play at boundary 100 s after the origin; window start S = boundary; a capture that started d seconds LATE sees the source d seconds ahead
    boundary = "2026-10-16T01:00:00.000000Z"
    t0 = X.parse_utc(boundary)
    for d in (0.0, 0.35, -0.2):
        tl_len = 120
        p = {"wav_id": "w0", "boundary_utc": boundary}
        tl = X.build_timeline([p], t0 - 30, tl_len, lambda wid: play)
        i0 = int(round((t0 + d - (t0 - 30)) * FS))
        win = np.zeros(180000, dtype=np.float32)
        seg = tl[i0:i0 + 180000]
        win[:len(seg)] = seg
        ch = X.analyse_window(win, t0, tl, t0 - 30)
        es = [c["e_s"] for c in ch if c["e_s"] is not None]
        assert len(es) >= 5, es
        assert abs(float(np.median(es)) - d) < 0.002


def test_wav_spreads_and_exclusion():
    plan = [{"index": i, "wav_id": "w%d" % (i // 3), "trial": i % 3} for i in range(9)]
    off = {i: {"e_med": 0.1 * (i % 3) + (0.05 if i // 3 == 1 else 0.0)} for i in range(9)}
    off[6] = {"e_med": None}                                                  # w2 trial 0 has no offset -> excluded
    sp, ex = I.wav_spreads(plan, off, ["w0", "w1", "w2"])
    assert abs(sp[0] - 0.2) < 1e-12 and abs(sp[1] - 0.2) < 1e-12 and np.isnan(sp[2]) and ex == 1


def test_split_at_median_and_group_diff_separates_and_does_not():
    sp = np.array([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09])
    sg = I.split_at_median(sp)
    assert sg["median"] == 0.05 and list(sg["equal"]) == [4] and len(sg["lower"]) == 4 and len(sg["upper"]) == 4
    # a decoder whose consistency falls with the spread: upper group clearly lower
    own = np.full(9, 20.0)
    all_ = np.array([19, 19, 18, 18, 14, 10, 9, 8, 8], dtype=float)
    g = I.group_diff(own, all_, sg["lower"], sg["upper"], n_boot=500)
    assert g["upper_minus_lower"] < 0 and g["separates"] and g["lower_n_wavs"] == 4
    # no relationship: identical groups
    all_flat = np.full(9, 15.0)
    g2 = I.group_diff(own, all_flat, sg["lower"], sg["upper"], n_boot=500)
    assert g2["upper_minus_lower"] == 0.0 and not g2["separates"]
    rho = I.spearman_rho(sp, own, all_)
    assert rho["rho"] < -0.9 and rho["n"] == 9
