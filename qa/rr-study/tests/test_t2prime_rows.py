"""Tests for the Stage B T2' predicate (Amendment 5). One test per rule of tasks 15.12, on synthetic cycles.

Run (after the Engineer's #122 hold lifts): python -m pytest qa/rr-study/tests/test_t2prime_rows.py -v
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "sub-feas"))
import replay_t2prime_rows as T  # noqa: E402


def cyc(stamp="261003_120000", ran=True, abandoned=False, tb1=500.0, res=2, el=1000.0):
    return T.Cycle(stamp=stamp, ran=ran, abandoned=abandoned, tb1_ms=tb1, residual_decodes=res, elapsed_ms=el)


def test_constants_are_the_specs():
    assert (T.DECODE_START_S, T.T2_BAR_S, T.SAME_SLOT_S, T.KEYING_MARGIN_S) == (0.032, 2.50, 2.95, 0.45)
    assert T.SELECTION_SHA256.startswith("55a951c8") and T.SELECTION_SHA256.endswith("53c977cf") and len(T.SELECTION_SHA256) == 64
    assert T.LIST_STRIDE == 4


def test_rule_iii_finite_t2_is_decode_start_plus_batch1_plus_residual():
    assert math.isclose(T.t2_of(cyc(tb1=530.0, el=1938.0)), 0.032 + 0.530 + 1.938)


def test_rule_i_abandoned_is_infinite_whatever_its_residual_count():
    assert T.t2_of(cyc(abandoned=True, res=5)) == math.inf and T.t2_of(cyc(abandoned=True, res=0)) == math.inf


def test_rule_ii_completed_with_zero_residual_decodes_is_excluded():
    assert T.t2_of(cyc(res=0)) is None


def test_a_pass_that_did_not_run_is_excluded_and_not_in_the_abandon_denominator():
    r = T.evaluate([cyc(ran=False), cyc(stamp="261003_120015", abandoned=True), cyc(stamp="261003_120030")])
    assert r["pass_did_not_run_excluded"] == 1 and r["abandon_fraction"] == 0.5 and r["population"] == 2


def test_rule_iv_equal_to_the_bar_passes_and_just_above_fails():
    at_bar = [cyc(tb1=0.0, el=2468.0)]                      # 0.032 + 0 + 2.468 = 2.500 s (float arithmetic gives 2.5000000000000004)
    assert T.evaluate(at_bar)["verdict"] == T.PASS
    assert T.evaluate([cyc(tb1=0.0, el=2469.0)])["verdict"] == T.FAIL   # 1 ms above the bar


def test_rule_iv_median_is_taken_over_finite_and_infinite_together():
    # 3 fast, 2 abandoned: median of [fast, fast, fast, inf, inf] is the 3rd = fast -> PASS
    fast = [cyc(stamp=f"261003_1200{i:02d}", tb1=500, el=800) for i in range(3)]
    ab = [cyc(stamp=f"261003_1201{i:02d}", abandoned=True) for i in range(2)]
    assert T.evaluate(fast + ab)["verdict"] == T.PASS


def test_rule_vi_more_than_half_abandoned_makes_the_median_infinite_and_fails():
    fast = [cyc(stamp=f"261003_1200{i:02d}", tb1=500, el=800) for i in range(2)]
    ab = [cyc(stamp=f"261003_1201{i:02d}", abandoned=True) for i in range(3)]
    r = T.evaluate(fast + ab)
    assert r["verdict"] == T.FAIL and r["median_t2_s"] == "inf"


def test_even_population_with_one_infinite_middle_is_infinite_not_nan():
    fast = [cyc(stamp="261003_120000", tb1=500, el=800)]
    ab = [cyc(stamp="261003_120015", abandoned=True)]
    assert T.median([T.t2_of(c) for c in fast + ab]) == math.inf
    assert T.evaluate(fast + ab)["verdict"] == T.FAIL


def test_rule_v_an_empty_population_is_undefined_never_pass():
    for cycles in ([], [cyc(res=0)], [cyc(ran=False)]):
        assert T.evaluate(cycles)["verdict"] == T.UNDEFINED


def test_the_survivorship_bias_is_real_without_the_rule():
    """Why the rule exists: medianing only the finished cycles would PASS where the +inf rule FAILS."""
    fast = [cyc(stamp=f"261003_1200{i:02d}", tb1=500, el=800) for i in range(2)]
    ab = [cyc(stamp=f"261003_1201{i:02d}", abandoned=True) for i in range(3)]
    finished_only = [T.t2_of(c) for c in fast]
    assert T.median(finished_only) <= T.T2_BAR_S and T.evaluate(fast + ab)["verdict"] == T.FAIL


def test_rule_vii_output_prints_counts_abandon_fraction_percentiles_and_hours():
    cycles = [cyc(stamp="261003_120000", tb1=500, el=800), cyc(stamp="261003_130000", tb1=500, el=3000),
              cyc(stamp="261003_130015", abandoned=True), cyc(stamp="261003_130030", res=0)]
    r = T.evaluate(cycles)
    assert r["population"] == 3 and r["finite"] == 2 and r["abandoned_inf"] == 1 and r["completed_zero_residual_excluded"] == 1
    assert math.isclose(r["abandon_fraction"], 1 / 4)
    assert r["by_utc_hour_le_2p95"]["12"] == {"n": 1, "le_2p95": 1} and r["by_utc_hour_le_2p95"]["13"] == {"n": 2, "le_2p95": 0}
    assert r["p5_s"] is not None and r["p95_s"] is not None and r["max_finite_s"] is not None
    assert "k_PC" in r["reading_the_bar"]


def test_a_completed_pass_without_timings_raises_instead_of_guessing():
    import pytest
    with pytest.raises(ValueError):
        T.t2_of(T.Cycle(stamp="261003_120000", ran=True, abandoned=False, tb1_ms=None, residual_decodes=1, elapsed_ms=None))
