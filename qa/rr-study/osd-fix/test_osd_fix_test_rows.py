"""Tests for osd_fix_test_rows.py: the verdict rows as code (spec 5.3), the blind-instrument guard (HK-025(k)), and refusal before TEST is complete."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osd_fix_test_rows as V  # noqa: E402
import osd_fix_train_rows as R  # noqa: E402


def row(i, M=30, n1=2, c1=1, n2=1, c2=0, W=32):
    return {"stamp": f"s{i:04d}", "W": W, "M": M, "n1": n1, "c1": c1, "n2": n2, "c2": c2}


def ci(point, lo, hi):
    return {"point": point, "ci": [lo, hi]}


class VerdictTests(unittest.TestCase):
    def test_f_fail_when_du_lower_bound_positive(self):
        self.assertEqual(V.classify(ci(0.2, 0.1, 0.3), ci(0.05, 0.01, 0.09)), "F-FAIL")

    def test_f_go_needs_both_conditions(self):
        self.assertEqual(V.classify(ci(0.16, 0.10, 0.22), ci(-0.07, -0.09, -0.05)), "F-GO")
        self.assertEqual(V.classify(ci(0.16, 0.10, 0.22), ci(-0.07, -0.09, 0.02)), "F-NEUTRAL")   # CI_hi(dU) > 0
        self.assertEqual(V.classify(ci(0.04, -0.02, 0.10), ci(-0.07, -0.09, -0.05)), "F-NEUTRAL")  # CI_lo(NET) <= 0

    def test_dU_hi_exactly_zero_still_go(self):
        self.assertEqual(V.classify(ci(0.1, 0.05, 0.15), ci(-0.03, -0.06, 0.0)), "F-GO")

    def test_f_fail_takes_precedence(self):
        self.assertEqual(V.classify(ci(0.3, 0.2, 0.4), ci(0.1, 0.02, 0.2)), "F-FAIL")

    def test_blind_instrument_is_never_go_or_neutral(self):
        ref = [row(i) for i in range(120)]
        fix = [dict(r) for r in ref]
        self.assertTrue(V.is_blind(ref, fix))
        cmp_ = R.compare(ref, fix)
        self.assertEqual(cmp_["NET"]["point"], 0.0)
        self.assertEqual(cmp_["NET"]["ci"], [0.0, 0.0])
        self.assertEqual(cmp_["dU"]["ci"], [0.0, 0.0])
        self.assertTrue(V.classify(cmp_["NET"], cmp_["dU"], True).startswith("BLIND-INSTRUMENT"))

    def test_a_real_difference_is_not_blind(self):
        ref = [row(i) for i in range(120)]
        fix = [dict(r) for r in ref]
        fix[7]["M"] += 1
        self.assertFalse(V.is_blind(ref, fix))

    def test_refuses_before_both_arms_complete(self):
        import osd_fix_test as X
        X.configure("TEST")
        out = X.T.OUT
        if os.path.exists(os.path.join(out, "r1", "REF", "process_ok.json")):
            self.skipTest("TEST has started")
        self.assertEqual(V.main("TEST"), 1)


if __name__ == "__main__":
    unittest.main()
