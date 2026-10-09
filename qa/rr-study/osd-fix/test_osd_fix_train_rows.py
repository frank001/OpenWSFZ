"""Tests for osd_fix_train_rows.py: NET / dU arithmetic, the interim n* rule (grid, ties, FIX-NO-GATE, <4 rounds), blind-instrument behaviour."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osd_fix_train_rows as S  # noqa: E402


def cyc(i, W=30, M=20, n1=22, c1=18, n2=4, c2=2):
    return {"stamp": f"s{i}", "W": W, "M": M, "n1": n1, "c1": c1, "n2": n2, "c2": c2}


class StatsTests(unittest.TestCase):
    def test_identical_arms_are_zero(self):
        ref = [cyc(i) for i in range(89)]
        r = S.compare(ref, [dict(c) for c in ref])
        self.assertEqual(r["NET"]["point"], 0.0)
        self.assertEqual(r["NET"]["ci"], [0.0, 0.0])
        self.assertEqual(r["dU"]["point"], 0.0)

    def test_known_difference(self):
        ref = [cyc(i) for i in range(80)]
        fix = [dict(c, M=c["M"] + 1, c1=c["c1"] + 1) for c in ref]
        r = S.compare(ref, fix)
        self.assertAlmostEqual(r["NET"]["point"], 100.0 * 80 / (30 * 80))
        self.assertAlmostEqual(r["NET_b1"]["point"], r["NET"]["point"])
        self.assertEqual(r["NET_b2"]["point"], 0.0)
        # not-confirmed: n unchanged, c +1 => dU = -1 per cycle (batch 1)
        self.assertAlmostEqual(r["dU"]["point"], -1.0)
        self.assertAlmostEqual(r["dU_b1"]["point"], -1.0)

    def test_blocks_of_40_and_short_round(self):
        ref = [cyc(i) for i in range(89)]
        self.assertEqual(S.compare(ref, [dict(c, M=c["M"] + 1) for c in ref])["NET"]["blocks"], 3)
        short = [cyc(i) for i in range(20)]
        self.assertEqual(S.compare(short, [dict(c, M=c["M"] + 1) for c in short])["NET"]["blocks"], 1)

    def test_w_mismatch_refused(self):
        a, b = [cyc(0)], [cyc(0, W=31)]
        with self.assertRaises(AssertionError):
            S.compare(a, b)


def res(**kw):
    base = {f"FIX{n}": {"NET": {"point": 0.0}, "dU": {"point": 0.0}} for n in (0,) + S.GRID}
    for k, (net, du) in kw.items():
        base[k] = {"NET": {"point": net}, "dU": {"point": du}}
    return base


class RuleTests(unittest.TestCase):
    def test_fewer_than_4_rounds(self):
        self.assertIsNone(S.would_pick(res(), 3)["n_star"])

    def test_picks_largest_net_among_du_le_0(self):
        r = res(FIX40=(0.3, 0.1), FIX30=(0.2, -0.1), FIX50=(0.1, 0.0))
        self.assertEqual(S.would_pick(r, 4)["n_star"], 30)

    def test_ties_go_to_the_lower_n(self):
        r = res(FIX30=(0.2, 0.0), FIX50=(0.2, 0.0), FIX24=(0.1, 0.0), FIX40=(0.0, 0.0), FIX60=(0.0, 0.0))
        self.assertEqual(S.would_pick(r, 4)["n_star"], 30)

    def test_no_gate(self):
        r = res(**{f"FIX{n}": (0.5, 0.2) for n in S.GRID})
        self.assertIn("FIX-NO-GATE", S.would_pick(r, 5)["note"])

    def test_fix0_outside_rule_but_reported(self):
        r = res(FIX24=(0.1, -0.1), FIX0=(0.4, -0.2))
        out = S.would_pick(r, 4)
        self.assertEqual(out["n_star"], 24)
        self.assertIn("B1_fix0_net_exceeds_nstar", out)
        self.assertEqual(out["edge"], "lower edge 24")


if __name__ == "__main__":
    unittest.main()
