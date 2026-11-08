#!/usr/bin/env python3
"""Tests for ms_gates.py: each predicate fires AND does not fire (HK-021 (k)); analyse() on a fabricated row set whose answers are known.
Run: python -I qa/rr-study/coh-multiset/test_ms_gates.py"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ms_gates as G  # noqa: E402

COLS = ["cycle_index", "stamp", "widx", "snr", "load", "live_hit", "fault", "g_out", "g_right", "c3_run", "c3_out", "c3_right", "c3_df", "c3_dt", "c3_edge", "consulted",
        "c3_osd_out", "c3_osd_right"] + [f"{s}_{k}" for s in G.ORDER for k in ("bp_out", "bp_right", "osd_out", "osd_right")] + list(G.TIMING)


def rec(ci, widx, **kw):
    r = {c: "0" for c in COLS}
    r.update({"cycle_index": str(ci), "stamp": f"s{ci}", "widx": str(widx), "snr": "-10", "load": "20"})
    r.update({k: str(v) for k, v in kw.items()})
    return r


class Rows(unittest.TestCase):
    def test_l1_row_fires_and_does_not_fire(self):
        self.assertEqual(G.l1_row(0.5, 0.9), "L1-GO")                  # CI_lo == bar is GO (>=)
        self.assertEqual(G.l1_row(0.49, 0.9), "L1-OPEN")
        self.assertEqual(G.l1_row(0.1, 0.499), "L1-STOP")
        self.assertEqual(G.l1_row(0.1, 0.5), "L1-OPEN")                # CI_hi == bar is NOT stop (<)
        self.assertEqual(G.l1_row(0.0, 0.0), "L1-STOP")

    def test_w_fail(self):
        self.assertTrue(G.w_fail(0.30, 0.284))
        self.assertFalse(G.w_fail(0.284, 0.284))
        self.assertFalse(G.w_fail(0.10, 0.284))

    def test_wilson(self):
        lo, hi = G.wilson(50, 100)
        self.assertAlmostEqual(lo, 0.4038, places=3)
        self.assertAlmostEqual(hi, 0.5962, places=3)
        self.assertTrue(all(x != x for x in G.wilson(0, 0)))

    def test_x_outcome_fixed_order_and_blocking(self):
        self.assertEqual(G.x_outcome(rec(1, 0)), ("none", ""))
        self.assertEqual(G.x_outcome(rec(1, 0, J3_bp_out=1, J3_bp_right=1)), ("right", "J3"))
        # C1 wrong precedes J2 right: X is the wrong one (the earlier set blocks the later)
        self.assertEqual(G.x_outcome(rec(1, 0, C1_bp_out=1, C1_bp_right=0, J2_bp_out=1, J2_bp_right=1)), ("wrong", "C1"))
        self.assertEqual(G.x_outcome(rec(1, 0, J2_bp_out=1, J2_bp_right=1, N1_bp_out=1, N1_bp_right=0)), ("right", "J2"))

    def test_block_ci_deterministic_and_point(self):
        num, den = [1, 0, 0, 2] * 4, [10] * 16
        a, b = G.block_ci(num, den), G.block_ci(num, den)
        self.assertEqual(a, b)
        self.assertAlmostEqual(a[0], 100.0 * 12 / 160, places=9)
        self.assertLessEqual(a[1], a[0] + 1e-9)
        self.assertGreaterEqual(a[2], a[0] - 1e-9)

    def test_analyse_known_answer(self):
        # 2 cycles x 4 rows. cycle 0: G right; C3 right; consulted X right (J2); consulted X wrong (C1); cycle 1: G wrong-output (not consulted); consulted none; consulted X right (N1); G right
        all_rows = [[0, "s0", w, 1000 + w, 0.0, -10, 4, 0, 1] for w in range(4)] + [[1, "s1", w, 1000 + w, 0.0, -10, 4, 0, 1] for w in range(4)]
        recs = [
            rec(0, 0, g_out=1, g_right=1),
            rec(0, 1, c3_run=1, c3_out=1, c3_right=1),
            rec(0, 2, c3_run=1, consulted=1, J2_bp_out=1, J2_bp_right=1),
            rec(0, 3, c3_run=1, consulted=1, C1_bp_out=1, C1_bp_right=0, J2_bp_out=1, J2_bp_right=1),
            rec(1, 0, g_out=1, g_right=0, c3_run=1),
            rec(1, 1, c3_run=1, consulted=1),
            rec(1, 2, c3_run=1, consulted=1, N1_bp_out=1, N1_bp_right=1),
            rec(1, 3, g_out=1, g_right=1),
        ]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "rows.json")
            json.dump({"rows": all_rows}, open(p, "w"))
            out = G.analyse(p, recs)
        self.assertEqual(out["N_all_rows_incl_unencodable"], 8)
        self.assertEqual(out["consulted_rows"], 4)
        self.assertEqual(out["X"], {"right": 2, "wrong": 1, "f_X": 1 / 3, "f_X_wilson95": list(G.wilson(1, 3))})
        self.assertAlmostEqual(out["NET_X_pp"], 25.0, places=9)             # 2 right of N = 8
        self.assertEqual(out["G_wrong_rows_not_consulted"], 1)
        self.assertEqual(out["earlier_wrong_blocks_later_right_rows"], 1)
        self.assertEqual(out["first_success_by_set"], {"J2": 1, "N1": 1})
        self.assertEqual(out["any_set_right_rows"], 3)
        self.assertEqual(out["f_C3_same_night"]["c3_right"], 1)
        self.assertEqual(out["f_C3_same_night"]["c3_wrong"], 0)

    def test_v5_detects_a_difference_and_ignores_timing(self):
        a = [rec(1, 0, g_right=1, t_g=0.5), rec(1, 1, c3_out=1)]
        b = [rec(1, 0, g_right=1, t_g=0.9), rec(1, 1, c3_out=1)]
        self.assertTrue(G.v5_compare(a, b)["pass"])
        b2 = [rec(1, 0, g_right=1), rec(1, 1, c3_out=0)]
        r = G.v5_compare(a, b2)
        self.assertFalse(r["pass"])
        self.assertEqual(r["rows_with_any_difference"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
