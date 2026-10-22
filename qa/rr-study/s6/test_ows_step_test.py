"""Unit tests for ows_step_test.py (synthetic audio only)."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import archive_xcorr as X  # noqa: E402
import ows_shift_test as T  # noqa: E402
import ows_step_test as P  # noqa: E402

FS = X.FS


def ramp(offset):
    return (np.arange(P.WIN) + offset).astype(np.int64) % 30000


def test_fill_nearest_leading_trailing_and_ties():
    e = [None, None, 0.1, None, 0.5, None, None]
    assert P.fill_nearest(e) == [0.1, 0.1, 0.1, 0.1, 0.5, 0.5, 0.5]            # chunk 3 is equidistant: the earlier chunk wins
    assert P.fill_nearest([0.2] * 3) == [0.2] * 3


def test_steps_only_between_consecutive_matched_chunks():
    e = [0.0, 0.0, 0.25, 0.25, None, 0.0, 0.0]
    st = P.steps_of(e, 0.05)
    assert st == [(1, 0.25)]                                                    # the drop across the unmatched chunk 4 is NOT claimed
    assert P.chunk_deltas([0.0, None, 0.3]) == []


def test_threshold_j_is_the_percentile_of_matched_deltas():
    w = {0: [0.0, 0.001, 0.0, 0.002], 1: [0.0, None, 0.0, 0.0]}
    j = P.threshold_j(w)
    d = [0.001, 0.001, 0.002, 0.0]                                              # window 1's two pairs across the unmatched chunk are skipped; only its (2, 3) pair counts
    assert abs(j - float(np.percentile(d, 99.9))) < 1e-12


def test_piecewise_with_constant_d_equals_the_constant_shift():
    prev, cur, nxt = ramp(-P.WIN).astype(np.int16), ramp(0).astype(np.int16), ramp(P.WIN).astype(np.int16)
    win, filled = P.piecewise_window(prev, cur, nxt, [0.5] * P.N_CHUNKS)
    ref, _ = T.shift_window(prev, cur, nxt, 0.5)
    assert np.array_equal(win, ref) and not filled


def test_piecewise_step_repeats_and_discards_audio_at_the_chunk_boundary():
    prev, cur, nxt = ramp(-P.WIN).astype(np.int16), ramp(0).astype(np.int16), ramp(P.WIN).astype(np.int16)
    d = [0.0] * 5 + [-0.25] * 10                                               # e steps back 0.25 s at chunk 5: 3000 samples of source are REPEATED
    win, _ = P.piecewise_window(prev, cur, nxt, d)
    assert np.array_equal(win[:5 * FS], ramp(0).astype(np.int16)[:5 * FS])
    assert np.array_equal(win[5 * FS:6 * FS], ramp(5 * FS - 3000).astype(np.int16)[:FS])
    assert np.array_equal(win[4 * FS + FS - 3000:5 * FS], win[5 * FS:5 * FS + 3000])   # the last 3000 samples of chunk 4 appear again at the start of chunk 5
    d = [0.0] * 5 + [0.25] * 10                                                # a forward step DISCARDS 3000 samples
    win, _ = P.piecewise_window(prev, cur, nxt, d)
    assert np.array_equal(win[5 * FS:6 * FS], ramp(5 * FS + 3000).astype(np.int16)[:FS])


def test_missing_neighbour_reached_is_counted():
    cur = np.full(P.WIN, 5, dtype=np.int16)
    _, filled = P.piecewise_window(None, cur, None, [0.0] * P.N_CHUNKS)
    assert not filled
    win, filled = P.piecewise_window(None, cur, None, [0.0] * 14 + [0.5])
    assert filled and np.all(win[:14 * FS] == 5)


def test_describe_steps_reports_share_sizes_and_positions():
    chunks = {0: [0.0] * 6 + [0.25] * 9, 1: [0.0] * 15, 2: [0.0] * 3 + [-0.5] * 12}
    r = P.describe_steps(chunks, 0.05)
    assert r["windows"] == 3 and r["windows_with_step"] == 2 and r["steps"] == 2
    assert r["step_size_s"]["positive"] == 1 and r["step_size_s"]["negative"] == 1
    assert r["step_size_s"]["share_within_0.05s_of_a_multiple_of_0.25s"] == 1.0
    assert r["position_chunk_index_histogram"]["6"] == 1 and r["position_chunk_index_histogram"]["3"] == 1
