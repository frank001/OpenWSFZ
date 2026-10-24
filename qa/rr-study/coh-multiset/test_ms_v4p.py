#!/usr/bin/env python3
"""Tests for ms_v4p.evaluate: the row fires and does not fire. Run: python -I qa/rr-study/coh-multiset/test_ms_v4p.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ms_v4p as V  # noqa: E402


def rec(stamp, widx, g, fault=0):
    return {"stamp": stamp, "widx": str(widx), "g_right": str(g), "fault": str(fault)}


class V4p(unittest.TestCase):
    def test_pass(self):
        recs = [rec("a", i, 1) for i in range(9)] + [rec("a", 9, 0)]
        mb = {"a": {i: 1 for i in range(10)}}
        r = V.evaluate(recs, mb, {"a": 10}, {"a": 10})
        self.assertTrue(r["pass"])
        self.assertEqual(r["P1_n"], 10)
        self.assertAlmostEqual(r["G_success_on_P1"], 0.9)

    def test_fails_below_bar(self):
        recs = [rec("a", i, 1) for i in range(8)] + [rec("a", 8, 0), rec("a", 9, 0)]
        r = V.evaluate(recs, {"a": {i: 1 for i in range(10)}}, {"a": 10}, {"a": 10})
        self.assertFalse(r["pass"])

    def test_fails_on_ws_count_mismatch_even_if_g_is_perfect(self):
        recs = [rec("a", i, 1) for i in range(10)]
        r = V.evaluate(recs, {"a": {i: 1 for i in range(10)}}, {"a": 11}, {"a": 10})
        self.assertFalse(r["pass"])
        self.assertEqual(r["ws_count_mismatch_cycles"], 1)

    def test_empty_p1_fails_and_batch2_rows_are_excluded_from_p1(self):
        r = V.evaluate([rec("a", 0, 1)], {"a": {0: 2}}, {"a": 1}, {"a": 1})
        self.assertFalse(r["pass"])
        self.assertEqual(r["batch2plus_rows_n"], 1)

    def test_faults_are_dropped(self):
        recs = [rec("a", 0, 0, fault=1)] + [rec("a", i, 1) for i in range(1, 10)]
        r = V.evaluate(recs, {"a": {i: 1 for i in range(10)}}, {"a": 10}, {"a": 10})
        self.assertEqual(r["P1_n"], 9)
        self.assertTrue(r["pass"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
