"""Tests for archive_xcorr on synthetic streams: a window cut from the played timeline is matched at the right time; an injected gap (lost audio) and a repeat (overlap) are found with their sizes."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import archive_xcorr as X  # noqa: E402

ORIGIN = 1_760_000_000.0


def timeline(seconds=120, seed=1):
    rng = np.random.default_rng(seed)
    return rng.standard_normal(int(seconds * X.FS)).astype(np.float32) * 1000


def cut(tl, t_start_s, n=X.WINDOW):
    i = int(round(t_start_s * X.FS))
    return tl[i:i + n].copy()


def test_a_clean_window_matches_at_its_nominal_time_with_a_constant_offset():
    tl = timeline()
    eps = 0.1                                                  # the chain's own delay: the window content is 0.1 s AHEAD of its label
    win = cut(tl, 30 + eps)
    ch = X.analyse_window(win, ORIGIN + 30, tl, ORIGIN)
    es = [c["e_s"] for c in ch]
    assert all(e is not None for e in es) and all(abs(e - eps) < 0.001 for e in es)
    assert min(c["peak"] for c in ch) > 0.9


def test_an_injected_gap_is_a_positive_step_of_its_size_at_the_right_chunk():
    tl = timeline()
    a, lost = 6.0, 7.2                                          # 6 s of audio, then 7.2 s lost, then the rest
    win = np.concatenate([cut(tl, 30, int(a * X.FS)), tl[int((30 + a + lost) * X.FS):int((30 + a + lost) * X.FS) + X.WINDOW - int(a * X.FS)]])
    assert len(win) == X.WINDOW
    ch = X.analyse_window(win, ORIGIN + 30, tl, ORIGIN)
    steps = X.find_steps([{"slot": "10:00:30", "chunks": [dict(c) for c in ch]}])
    assert len(steps) == 1 and steps[0]["kind"] == "inside_window"
    assert abs(steps[0]["step_s"] - lost) < 0.01 and steps[0]["chunk"] == int(a)


def test_overlapping_successive_windows_read_as_the_realignment_step():
    tl = timeline()
    w1 = X.analyse_window(cut(tl, 30), ORIGIN + 30, tl, ORIGIN)
    w2 = X.analyse_window(cut(tl, 30 + 15 - 0.25), ORIGIN + 45, tl, ORIGIN)   # the next window starts 0.25 s EARLIER in the source (repeated audio)
    steps = X.find_steps([{"slot": "a", "chunks": w1}, {"slot": "b", "chunks": w2}])
    assert len(steps) == 1 and steps[0]["kind"] == "window_boundary_realign" and abs(steps[0]["step_s"] + 0.25) < 0.01


def test_silence_and_unrelated_audio_do_not_match_and_break_the_step_chain():
    tl = timeline()
    tl[int(60 * X.FS):int(90 * X.FS)] = 0                      # an idle stretch
    win = cut(tl, 62)
    ch = X.analyse_window(win, ORIGIN + 62, tl, ORIGIN)
    assert all(c["e_s"] is None for c in ch)
    noise = np.random.default_rng(9).standard_normal(X.WINDOW).astype(np.float32) * 1000
    assert all(c["e_s"] is None for c in X.analyse_window(noise, ORIGIN + 30, timeline(), ORIGIN))
    # two matched chunks separated by an unmatched one are not compared
    steps = X.find_steps([{"slot": "a", "chunks": [{"j": 0, "e_s": 0.1, "peak": 1}, {"j": 1, "e_s": None, "peak": 0}, {"j": 2, "e_s": 5.0, "peak": 1}]}])
    assert steps == []


def test_play_timeline_places_each_wav_at_its_boundary():
    wav = np.arange(10, dtype=np.float32) + 1
    tl = X.build_timeline([{"wav_id": "w", "boundary_utc": "2026-10-13T18:09:15.000000Z"}], X.parse_utc("2026-10-13T18:09:00"), 40, lambda _id: wav)
    i0 = 15 * X.FS
    assert np.array_equal(tl[i0:i0 + 10], wav) and not tl[:i0].any() and not tl[i0 + 10:].any()


def test_correlation_values_stay_in_range_and_silence_reads_zero():
    tl = timeline()
    tl[int(40 * X.FS):int(70 * X.FS)] = 0
    k, peak = X.best_lag(cut(tl, 100, X.CHUNK), tl[int(36 * X.FS):int(75 * X.FS)])      # the chunk (from elsewhere) against a mostly silent segment
    assert peak <= 1.0 + 1e-6
    seg = np.zeros(10 * X.FS, dtype=np.float32)
    k2, peak2 = X.best_lag(cut(tl, 100, X.CHUNK), seg)
    assert peak2 == 0.0
