"""Tests for s1_snr_replay.py: the join, the exact-equality rows, the verdict rows, the pins that make the cross non-blind (HK-025(k))."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s1_snr_replay as S  # noqa: E402

TRUTH = [("261008_194100", 1500.0, -12.0), ("261008_194130", 1500.0, -21.0), ("261008_194145", 1500.0, -3.0)]


class JoinTests(unittest.TestCase):
    def test_stamp_conversion(self):
        self.assertEqual(S.stamp_of("2026-10-08T19:41:00Z"), "261008_194100")
        self.assertEqual(S.prev_stamp("261008_194100"), "261008_194045")
        self.assertEqual(S.prev_stamp("261009_000000"), "261008_235945")

    def test_match_within_4_hz_and_extras(self):
        out = S.parse_outcomes(["261008_194100,b1,0,1499,0.2,-11", "261008_194100,b2,0,900,0.1,-20", "261008_194130,b1,0,1507,0.2,-19"])
        m = S.match_rows(out, TRUTH)
        self.assertEqual(m["261008_194100"], {"decoded": True, "snr": -11, "extra": 1})
        self.assertFalse(m["261008_194130"]["decoded"])          # 7 Hz away: not the row's decode
        self.assertEqual(m["261008_194130"]["extra"], 1)
        self.assertFalse(m["261008_194145"]["decoded"])

    def test_live_rows_use_openwsfz_s1_only(self):
        rows = [{"scenario_id": "S1", "appraiser": "OpenWSFZ", "matched": "True", "reported_snr_db": "-11.0", "cycle_utc": "2026-10-08T19:41:00Z"},
                {"scenario_id": "S1", "appraiser": "WSJT-X", "matched": "True", "reported_snr_db": "-12.0", "cycle_utc": "2026-10-08T19:41:00Z"},
                {"scenario_id": "S2", "appraiser": "OpenWSFZ", "matched": "True", "reported_snr_db": "-5.0", "cycle_utc": "2026-10-08T19:50:00Z"},
                {"scenario_id": "S1", "appraiser": "OpenWSFZ", "matched": "False", "reported_snr_db": "", "cycle_utc": "2026-10-08T19:41:30Z"}]
        self.assertEqual(S.live_rows(rows), {"261008_194100": {"decoded": True, "snr": -11}, "261008_194130": {"decoded": False, "snr": None}})

    def test_same_rows_is_exact(self):
        a = {"s1": {"decoded": True, "snr": -11}, "s2": {"decoded": False, "snr": None}}
        self.assertEqual(S.same_rows(a, dict(a)), (True, []))
        b = {"s1": {"decoded": True, "snr": -10}, "s2": {"decoded": False, "snr": None}}
        self.assertEqual(S.same_rows(a, b), (False, ["s1"]))                    # one dB on one row is a difference
        c = {"s1": {"decoded": True, "snr": -11}, "s2": {"decoded": True, "snr": -22}}
        self.assertEqual(S.same_rows(a, c), (False, ["s2"]))

    def test_bias_and_build_diff(self):
        r = {"261008_194100": {"decoded": True, "snr": -11}, "261008_194130": {"decoded": False, "snr": None}, "261008_194145": {"decoded": True, "snr": -2}}
        self.assertAlmostEqual(S.bias(r, TRUTH), (1 + 1) / 2)
        f = {k: dict(v) for k, v in r.items()}
        self.assertEqual(S.build_diff(r, f), [])
        f["261008_194145"]["snr"] = -1
        self.assertEqual(S.build_diff(r, f), ["261008_194145"])
        f["261008_194130"] = {"decoded": True, "snr": -20}                      # decoded by one build only: not an SNR difference
        self.assertEqual(S.build_diff(r, f), ["261008_194145"])


class VerdictTests(unittest.TestCase):
    def test_build_row_fires_on_one_differing_row(self):
        self.assertEqual(S.verdict(True, True, ["s1"], [], 0.6, 0.6), "SR-BUILD")
        self.assertEqual(S.verdict(True, True, [], ["s9"], 0.6, 0.6), "SR-BUILD")

    def test_audio_row_needs_both_gaps_at_the_bar(self):
        self.assertEqual(S.verdict(True, True, [], [], 0.60, 0.60), "SR-AUDIO")
        self.assertEqual(S.verdict(True, True, [], [], 0.40, 0.40), "SR-AUDIO")     # boundary inclusive (>= 0.40)
        self.assertEqual(S.verdict(True, True, [], [], 0.60, 0.39), "SR-NEITHER")
        self.assertEqual(S.verdict(True, True, [], [], 0.10, 0.10), "SR-NEITHER")

    def test_validity_failure_withholds_everything(self):
        self.assertTrue(S.verdict(False, True, ["s1"], [], 0.6, 0.6).startswith("WITHHELD (SV1-SV3"))

    def test_sv4_failure_withholds_the_zero_rows_predicate(self):
        self.assertTrue(S.verdict(True, False, [], [], 0.6, 0.6).startswith("WITHHELD (SV4"))


class NonBlindTests(unittest.TestCase):
    def test_the_two_builds_are_distinguishable_by_their_pins(self):
        self.assertNotEqual(S.BUILDS["M"]["dll"], S.BUILDS["F"]["dll"])
        self.assertNotEqual(S.BUILDS["M"]["harness"], S.BUILDS["F"]["harness"])
        self.assertTrue(S.BUILDS["F"]["sign_flag"] and not S.BUILDS["M"]["sign_flag"])

    def test_cells_cover_the_design(self):
        self.assertEqual(S.CELLS["A04.M"][1:], ("M", 40))
        self.assertEqual(S.CELLS["A08.F"][1:], ("F", 40))
        self.assertEqual(S.CELLS["A08.F24"][1:], ("F", 24))
        self.assertEqual(S.CELLS["A04.M.rep"], S.CELLS["A04.M"])
        self.assertEqual(len(S.CELLS), 12)

    def test_bar_is_two_thirds_of_the_live_difference(self):
        self.assertAlmostEqual(S.BAR_DB, 0.40)

    @unittest.skipUnless(os.path.isdir(S.RES_ROOT + "/2026-10-08-0a1ff63"), "run folders not present")
    def test_truth_gives_thirty_s1_cycles_per_audio_set(self):
        for a in S.AUDIO:
            t = S.truth_of(a)
            self.assertEqual(len(t), 30)
            self.assertTrue(all(f == 1500.0 for _s, f, _n in t))


if __name__ == "__main__":
    unittest.main()
