"""Unit tests for ows_shift_test.py (synthetic audio only)."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import archive_xcorr as X  # noqa: E402
import ows_shift_test as T  # noqa: E402

FS = X.FS


def ramp(offset):
    return (np.arange(T.WIN) + offset).astype(np.int64) % 30000


def test_stamp_plus_crosses_midnight():
    assert T.stamp_plus("261016_235945", 1) == "261017_000000"
    assert T.stamp_plus("261016_000000", -1) == "261015_235945"


def test_identity_shift_is_bit_identical():
    cur = ramp(0).astype(np.int16)
    win, filled = T.shift_window(None, cur, None, 0.0)
    assert np.array_equal(win, cur) and not filled


def test_positive_shift_starts_later_and_reads_the_next_slot():
    prev, cur, nxt = ramp(-T.WIN).astype(np.int16), ramp(0).astype(np.int16), ramp(T.WIN).astype(np.int16)
    win, filled = T.shift_window(prev, cur, nxt, 0.5)            # 0.5 s later = 6000 samples
    assert np.array_equal(win, ramp(6000).astype(np.int16)) and not filled
    win, filled = T.shift_window(prev, cur, nxt, -0.25)
    assert np.array_equal(win, ramp(-3000).astype(np.int16)) and not filled


def test_missing_neighbour_is_zero_filled_and_counted_only_when_reached():
    cur = np.full(T.WIN, 7, dtype=np.int16)
    win, filled = T.shift_window(None, cur, None, 0.5)
    assert filled and np.all(win[-6000:] == 0) and np.all(win[:-6000] == 7)
    win, filled = T.shift_window(None, cur, None, -0.5)
    assert filled and np.all(win[:6000] == 0)
    nxt = np.full(T.WIN, 9, dtype=np.int16)
    win, filled = T.shift_window(None, cur, nxt, 0.5)            # prev missing but not reached
    assert not filled and np.all(win[-6000:] == 9)


def test_constant_shifts_are_the_wav_mean():
    plan = [{"index": i, "wav_id": "w%d" % (i // 3)} for i in range(6)]
    d = {0: 0.1, 1: 0.3, 2: 0.5, 3: -0.2, 4: 0.0, 5: 0.2}
    k = T.constant_shifts(plan, d)
    assert [round(k[i], 6) for i in range(6)] == [0.3, 0.3, 0.3, 0.0, 0.0, 0.0]


def test_shift_sign_matches_archive_xcorr_convention(tmp_path):
    """The shifted window must carry source time nominal + (e_O - e_W): archive_xcorr must read e_W + d on it."""
    rng = np.random.default_rng(3)
    boundary = "2026-10-16T01:00:00.000000Z"
    t0 = X.parse_utc(boundary)
    play = (rng.standard_normal(13 * FS) * 3000).astype(np.float32)
    origin = t0 - 30
    tl = X.build_timeline([{"wav_id": "w", "boundary_utc": boundary}], origin, 120, lambda w: play)
    e_w = 0.05
    i0 = int(round((t0 + e_w - origin) * FS))                      # the WSJT-X save window carries e_W
    cur = np.zeros(T.WIN, dtype=np.int16)
    seg = tl[i0:i0 + T.WIN]
    cur[:len(seg)] = seg.astype(np.int16)
    for d in (0.0, 0.4, -0.15):
        win, _ = T.shift_window(None, cur, None, d)
        ch = X.analyse_window(win.astype(np.float32), t0, tl, origin)
        es = [c["e_s"] for c in ch if c["e_s"] is not None]
        assert len(es) >= 3                                          # a late shift drops the tail into the zero-filled region; the head still matches
        assert abs(float(np.median(es)) - (e_w + d)) < 0.002, (d, np.median(es))
