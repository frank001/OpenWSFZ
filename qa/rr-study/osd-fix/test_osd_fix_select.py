"""Tests for osd_fix_select.py: the frozen TRAIN selection is the pinned one, disjoint from the TEST reserve, and deterministic."""
import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osd_fix_select as S  # noqa: E402

SELECTION_SHA256 = "27bb840f45c77da6e65f18f855ade547e9a002a253c2946bf723a6eaa53db11e"   # frozen 2026-10-08, before any decode


class SelectionTests(unittest.TestCase):
    def test_pinned_output(self):
        self.assertEqual(hashlib.sha256(S.render(S.build())).hexdigest(), SELECTION_SHA256)

    def test_counts_and_disjoint(self):
        o = S.build()
        self.assertEqual((o["counts"]["train"], o["counts"]["full"]), (621, 3104))
        self.assertFalse(set(o["TRAIN"]) & set(o["TEST_RESERVE"]))
        self.assertEqual(o["TRAIN"], sorted(o["TRAIN"]))

    def test_residues_are_systematic(self):
        o = S.build()
        pos = {s: i for i, s in enumerate(S.json.load(open(S.SRC, encoding="utf-8"))["runs"][S.RUN]["FULL"])}
        self.assertTrue(all(pos[s] % 10 in (0, 5) for s in o["TRAIN"]))
        self.assertTrue(all(pos[s] % 10 in (1, 2, 4, 6, 8, 9) for s in o["TEST_RESERVE"]))

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
