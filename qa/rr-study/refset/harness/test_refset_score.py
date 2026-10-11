"""Tests for refset_score: the same cases as the W-pilot harness's --selftest (so the Python port and the C# original agree), plus readers.
Only synthetic Q-prefix calls appear here (NFR-021).
Run:  python -s -E -m unittest test_refset_score   (from this folder)"""
import os
import tempfile
import unittest

import refset_score as rs


class TestScoreCycle(unittest.TestCase):
    def test_key_and_hashed(self):
        self.assertEqual(rs.key_of("CQ <...> JO33"), "CQ <HASH> JO33")
        self.assertEqual(rs.key_of("CQ  <Q1AW>  JO33"), "CQ <HASH> JO33")
        self.assertTrue(rs.is_hashed("Q1ABC <Q9XYZ> R-08"))
        self.assertTrue(rs.is_hashed("<...> Q1ABC RR73"))
        self.assertFalse(rs.is_hashed("CQ Q1ABC FN42"))

    def test_pilot_selftest_case_1(self):
        c = rs.score_cycle(["CQ Q1ABC FN42", "<Q9XYZ> Q1AW -10", "<...> Q1ABC RR73", "Q1ABC Q1AW R-05"],
                           ["CQ Q1ABC FN42", "<...> Q1AW -10", "<...> Q1ABC RR73", "Q1ZZZ Q1AW 73"])
        self.assertEqual((c.live_rows, c.live_non_hashed, c.live_hashed, c.live_hashed_dots), (4, 2, 2, 1))
        self.assertEqual((c.repro_all, c.repro_non_hashed, c.repro_hashed_key), (3, 1, 2))
        self.assertEqual((c.repro_hashed_exact, c.render_live_resolved_own_dots, c.render_live_dots_own_resolved), (1, 1, 0))
        self.assertEqual((c.own_rows, c.extra_all, c.extra_non_hashed, c.extra_hashed_key), (4, 1, 1, 0))

    def test_duplicates_not_double_counted(self):
        d = rs.score_cycle(["CQ Q1ABC FN42", "CQ Q1ABC FN42"], ["CQ Q1ABC FN42"])
        self.assertEqual((d.repro_all, d.extra_all, d.live_rows), (1, 0, 2))

    def test_own_has_both_renderings(self):
        e = rs.score_cycle(["<Q9XYZ> Q1AW -10"], ["<...> Q1AW -10", "<Q9XYZ> Q1AW -10"])
        self.assertEqual((e.repro_hashed_key, e.repro_hashed_exact, e.extra_hashed_key), (1, 1, 1))

    def test_live_dots_own_resolved(self):
        f = rs.score_cycle(["<...> Q1AW -10"], ["<Q9XYZ> Q1AW -10"])
        self.assertEqual((f.repro_hashed_key, f.repro_hashed_exact, f.render_live_dots_own_resolved), (1, 0, 1))


class TestReaders(unittest.TestCase):
    def test_all_txt_and_work_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "ALL.TXT")
            with open(p, "w", encoding="ascii") as fh:
                fh.write("261009_175245     7.074 Rx FT8     -3 -0.7 1878 CQ Q1ABC FN42\n")
                fh.write("261009_175300     7.074 Rx FT8      3  0.1 2275 Q1ABC Q1AW R-05\n")
            got = rs.read_all_txt(p, ["261009_175245"])
            self.assertEqual(got, {"261009_175245": ["CQ Q1ABC FN42"]})
            w = os.path.join(d, "b.decodes.tsv")
            with open(w, "w", encoding="utf-8") as fh:
                fh.write("stamp\tsnr\tdt\tfreq_hz\ttext\n261009_175245\t-3\t-0.70\t1878\tCQ Q1ABC FN42\n")
            self.assertEqual(dict(rs.read_work(w)), {"261009_175245": ["CQ Q1ABC FN42"]})

    def test_score_block_equal_rowcount(self):
        r = rs.score_block({"a": ["CQ Q1ABC FN42"], "b": ["CQ Q1ABC FN42", "CQ Q1AW FN42"]},
                           {"a": ["CQ Q1ABC FN42"], "b": ["CQ Q1ABC FN42"]}, ["a", "b"])
        self.assertEqual((r["cycles_equal_rowcount"], r["sum_abs_rowdiff"]), (1, 1))
        sh = rs.rsv2_shares(r["counts"])
        self.assertAlmostEqual(sh["repro_nonhashed_share"], 2 / 3)
        self.assertEqual(sh["extra_nonhashed_share"], 0.0)

    def test_bootstrap_interval_contains_point(self):
        lo, hi = rs.cluster_bootstrap_share([9] * 50, [10] * 50)
        self.assertTrue(lo <= 0.9 <= hi)


if __name__ == "__main__":
    unittest.main()
