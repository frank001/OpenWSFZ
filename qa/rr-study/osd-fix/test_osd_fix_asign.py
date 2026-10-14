"""Tests for osd_fix_asign.py's comparison predicates: they must FIRE on a doctored pair (the instrument is not blind)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osd_fix_asign as A  # noqa: E402

A91 = bytes(range(12))


def res(path=1, crc=1, ldpc=0, a91=A91, rc=0):
    return {"rc": rc, "path": path, "crc_ok": crc, "ldpc_errors": ldpc, "a91": a91}


class ComparisonTests(unittest.TestCase):
    def test_same_osd_equal_accepts(self):
        self.assertTrue(A.same_osd(res(), res()))

    def test_same_osd_fires_on_payload_difference(self):
        self.assertFalse(A.same_osd(res(), res(a91=bytes(12))))

    def test_same_osd_fires_on_path_or_crc_difference(self):
        self.assertFalse(A.same_osd(res(path=1), res(path=-1, crc=0, a91=None)))
        self.assertFalse(A.same_osd(res(crc=1), res(crc=0)))

    def test_same_osd_ignores_bp_residual_only_when_not_accepted(self):
        self.assertTrue(A.same_osd(res(path=-1, crc=0, ldpc=7, a91=None), res(path=-1, crc=0, ldpc=21, a91=None)))
        self.assertFalse(A.same_osd(res(path=1, ldpc=0), res(path=1, ldpc=3)))

    def test_strict_same_fires_on_any_field(self):
        self.assertTrue(A.same(res(), res()))
        for k, v in (("rc", 1), ("path", 0), ("crc_ok", 0), ("ldpc_errors", 5), ("a91", bytes(12))):
            d = res()
            d[k] = v
            self.assertFalse(A.same(res(), d), k)

    def test_verdict_rows(self):
        v = A.verdict(0, 0, 3, 0, 40)
        self.assertTrue(all(v[k] for k in ("ii_a", "ii_b", "iii", "iv")))
        self.assertFalse(A.verdict(1, 0, 3, 0, 40)["ii_a"])
        self.assertFalse(A.verdict(0, 1, 3, 0, 40)["iii"])
        self.assertFalse(A.verdict(0, 0, 0, 0, 40)["iv"])
        self.assertFalse(A.verdict(0, 0, 3, 1, 40)["ii_b"])
        self.assertFalse(A.verdict(0, 0, 3, 0, 0)["ii_a"], "nothing compared must not read as a pass")


if __name__ == "__main__":
    unittest.main()
