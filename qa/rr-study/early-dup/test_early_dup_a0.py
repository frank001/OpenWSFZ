"""Tests for early_dup_a0.py: the truth table, the frame-time mapping, and the non-vacuous A0-b / A0-c rows (HK-025(k))."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import early_dup_a0 as A  # noqa: E402


def trow(cycle, text, f):
    return {"scenario_id": "S4", "cycle_utc": cycle, "message_text": text, "true_freq_hz": str(f)}


TRUTH = [trow("2026-10-08T21:48:30Z", "T1", 500)] + \
        [trow("2026-10-08T21:51:00Z", "T1", 500), trow("2026-10-08T21:51:00Z", "T1", 1763), trow("2026-10-08T21:51:00Z", "T2", 900), trow("2026-10-08T21:51:00Z", "T2", 2163)] + \
        [trow("2026-10-08T21:51:15Z", f"T{i}", 400 + 827.5 * k) for i in (1,) for k in (0, 1, 2)]


class TruthTests(unittest.TestCase):
    def test_cycle_table(self):
        c = A.s4_cycles(TRUTH)
        self.assertEqual(c["2026-10-08T21:48:30Z"], {"signals": 1, "distinct": 1, "copies": [1], "spacings": []})
        self.assertEqual(c["2026-10-08T21:51:00Z"]["distinct"], 2)
        self.assertEqual(c["2026-10-08T21:51:00Z"]["copies"], [2, 2])
        self.assertEqual(c["2026-10-08T21:51:00Z"]["spacings"], [1263.0])
        self.assertEqual(c["2026-10-08T21:51:15Z"]["spacings"], [827.5, 1655.0])

    def test_texts_never_leave(self):
        self.assertFalse(any("T1" in str(v) for v in A.s4_cycles(TRUTH).values()))


class FrameMappingTests(unittest.TestCase):
    STARTS = {"2026-10-08T21:51:00Z", "2026-10-08T21:51:15Z"}

    def test_early_and_final_frames_map_to_their_cycle(self):
        self.assertEqual(A.cycle_of("2026-10-08T21:51:13.100000Z", self.STARTS), "2026-10-08T21:51:00Z")   # early, 13 s in
        self.assertEqual(A.cycle_of("2026-10-08T21:51:15.100000Z", self.STARTS), "2026-10-08T21:51:00Z")   # its final, just after the boundary
        self.assertEqual(A.cycle_of("2026-10-08T21:51:28.200000Z", self.STARTS), "2026-10-08T21:51:15Z")
        self.assertIsNone(A.cycle_of("2026-10-08T21:40:00.000000Z", self.STARTS))


class A0bTests(unittest.TestCase):
    CYC = A.s4_cycles(TRUTH)

    def test_true_when_all_in_repeated_cycles(self):
        self.assertEqual(A.a0b({"2026-10-08T21:51:00Z": 2}, self.CYC), (True, 2, 0))

    def test_false_when_a_row_is_in_a_cycle_without_repeats(self):
        ok, rows, out = A.a0b({"2026-10-08T21:51:00Z": 2, "2026-10-08T21:48:30Z": 1}, self.CYC)
        self.assertEqual((ok, rows, out), (False, 3, 1))

    def test_zero_rows_is_not_true(self):                       # non-vacuity
        self.assertEqual(A.a0b({"2026-10-08T21:51:00Z": 0}, self.CYC)[0], False)
        self.assertEqual(A.a0b({}, self.CYC)[0], False)


class A0cTests(unittest.TestCase):
    CYC = A.s4_cycles(TRUTH)

    @staticmethod
    def fr(df):
        return {"kind": "cycle", "utc": "2026-10-08T21:51:13.5Z", "labels": {"FREQ_MISS": len(df)}, "df_this_hz": df}

    def test_true_within_three_hz_of_a_spacing(self):
        ok, n, d = A.a0c([self.fr([1262, 1263])], set(self.CYC), self.CYC)
        self.assertEqual((ok, n), (True, 2))

    def test_false_when_one_row_is_far_from_every_spacing(self):
        ok, n, d = A.a0c([self.fr([1262, 828])], set(self.CYC), self.CYC)    # 828 is not a spacing of a 2-copy cycle
        self.assertEqual((ok, n), (False, 2))

    def test_zero_rows_is_not_true(self):
        self.assertEqual(A.a0c([self.fr([])], set(self.CYC), self.CYC)[0], False)
        self.assertEqual(A.a0c([], set(self.CYC), self.CYC)[:2], (False, 0))


if __name__ == "__main__":
    unittest.main()
