"""Tests for osd_fix_test_select.py: the frozen TEST selection is the pinned one, systematic, disjoint, never contains the warm-up, and is deterministic."""
import hashlib
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osd_fix_test_select as S  # noqa: E402

SELECTION_SHA256 = "84b3d8849ea9da0ee989892a1b7de6ef2a2b3f8e68b0d47c4e477e6dc96f78b0"   # frozen 2026-10-09, before any TEST decode


class SelectionTests(unittest.TestCase):
    def test_pinned_output(self):
        self.assertEqual(hashlib.sha256(S.render(S.build())).hexdigest(), SELECTION_SHA256)

    def test_counts_and_order(self):
        o = S.build()
        self.assertEqual((o["counts"]["included"], o["counts"]["SAMPLE"], o["counts"]["SAMPLE_B"], o["counts"]["TEST"]), (4298, 430, 430, 860))
        self.assertEqual(o["TEST"], sorted(o["TEST"]))
        self.assertGreaterEqual(len(o["SAMPLE"]), S.MIN_CYCLES)

    def test_residues_are_systematic_and_disjoint(self):
        o = S.build()
        pos = {s: i for i, s in enumerate(json.load(open(S.SRC, encoding="utf-8"))["runs"][S.RUN]["ALL"])}
        self.assertTrue(all(pos[s] % 10 == 0 for s in o["SAMPLE"]))
        self.assertTrue(all(pos[s] % 10 == 5 for s in o["SAMPLE_B"]))
        self.assertFalse(set(o["SAMPLE"]) & set(o["SAMPLE_B"]))
        self.assertEqual(set(o["TEST"]), set(o["SAMPLE"]) | set(o["SAMPLE_B"]))

    def test_warmup_and_edges_are_not_scored(self):
        o = S.build()
        self.assertNotIn(o["warmup"], o["TEST"])
        self.assertFalse(set(o["excluded"]["window_edge"]) & set(o["TEST"]))

    def test_not_the_train_night(self):
        self.assertNotEqual(S.RUN, "20261004_1634")

    def test_wrong_source_refused(self):
        import tempfile
        with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as f:
            f.write(b"{}")
        try:
            with self.assertRaises(AssertionError):
                S.build(f.name)
        finally:
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
