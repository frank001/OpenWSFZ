"""Tests for the pure parts of old_cpu_profile: the Amdahl solve and the median helper. (perf itself is exercised on sol by the smoke stage.)"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import old_cpu_profile as O  # noqa: E402


def timing(p, n, t1=100.0):
    return t1 * ((1 - p) + p / n)


def test_amdahl_recovers_the_parallel_fraction_from_any_pair():
    for p in (0.5, 0.8, 0.95, 1.0):
        t = {n: timing(p, n) for n in (1, 4, 8)}
        assert abs(O.amdahl_parallel_fraction(t[1], t[4], 1, 4) - p) < 1e-9
        assert abs(O.amdahl_parallel_fraction(t[1], t[8], 1, 8) - p) < 1e-9
        assert abs(O.amdahl_parallel_fraction(t[4], t[8], 4, 8) - p) < 1e-9


def test_amdahl_degenerate_inputs_give_none():
    assert O.amdahl_parallel_fraction(0, 5, 1, 4) is None and O.amdahl_parallel_fraction(5, 5, 4, 4) is None


def test_median_ignores_missing_and_negative():
    assert O.median([None, -1, 3, 1, 2]) == 2 and O.median([None, -1]) is None


def test_constants_follow_the_spec():
    assert (O.SAMPLE_HZ, O.OC1_BAR, O.OC2_BAR, O.THREAD_SETTINGS, O.SCALING_RANGE) == (499, 0.999, 10.0, (1, 4, 8), "8:8")
    assert (O.BLOCK_SLOW, O.BLOCK_MEDIAN) == ("9dbe42bc46d9", "822498b61291")
