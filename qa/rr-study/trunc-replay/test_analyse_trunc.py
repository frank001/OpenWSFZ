"""Test of V4' (Amendment 1, 2026-10-03 13:53Z) on synthetic per-cycle counts. No decoder, no corpus, no message text.

  python -m unittest qa/rr-study/trunc-replay/test_analyse_trunc.py     (from the repository root; about 1 s of one core)
"""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyse_trunc as A  # noqa: E402

A.BOOT_B = 400   # the test needs the sign of a CI bound, not its precision


def cycles(n=200, per=20):
    stamps = [f"c{i:04d}" for i in range(n)]
    return stamps, {s: per for s in stamps}


class V4Prime(unittest.TestCase):
    def test_uncut_signature_fails_on_clause_i(self):
        # the failure V4' exists to catch: the cut never reaches the decoder, so C(x) = 1.000 at every x
        stamps, den = cycles()
        r = A.v4_rows(stamps, dict(den), dict(den), den)
        self.assertEqual((r["c05"], r["c4"], r["d"]), (1.0, 1.0, 0.0))
        self.assertFalse(r["i"])
        self.assertFalse(r["pass"])

    def test_real_loss_passes(self):
        # the smoke-test shape: C(0.5) ~ 1.0, C(4.0) ~ 0.78 -- fails the superseded V4 margin only barely or not at all,
        # and passes V4' comfortably
        stamps, den = cycles()
        rnd = random.Random(1)
        num4 = {s: sum(rnd.random() < 0.78 for _ in range(20)) for s in stamps}
        r = A.v4_rows(stamps, dict(den), num4, den)
        self.assertTrue(r["i"] and r["ii"] and r["pass"])
        self.assertGreater(r["d_lo"], 0)

    def test_small_loss_passes_when_the_ci_excludes_zero(self):
        # C(4.0) = 0.95: the superseded V4 (needs a 0.20 gap) would FAIL, V4' passes
        stamps, den = cycles()
        num4 = {s: 19 for s in stamps}
        r = A.v4_rows(stamps, dict(den), num4, den)
        self.assertTrue(r["pass"])
        self.assertFalse(r["old_v4_pass"])

    def test_no_reliable_difference_fails_on_clause_ii(self):
        # C(4.0) <= 0.98 but the loss is noise: half the blocks lose, half gain, so the CI of D straddles 0
        stamps, den = cycles()
        num05 = {s: 19 for s in stamps}
        num4 = {s: (18 if i % 20 < 10 else 20) for i, s in enumerate(stamps)}
        r = A.v4_rows(stamps, num05, num4, den)
        self.assertTrue(r["i"])
        self.assertFalse(r["ii"])
        self.assertFalse(r["pass"])

    def test_boundary_098_is_inclusive(self):
        stamps, den = cycles(n=100, per=50)   # 5000 decodes; C(4.0) = 4900/5000 = 0.98 exactly
        num4 = {s: 49 for s in stamps}
        r = A.v4_rows(stamps, dict(den), num4, den)
        self.assertEqual(r["c4"], 0.98)
        self.assertTrue(r["i"])

    def test_same_blocks_and_seed_is_deterministic(self):
        stamps, den = cycles()
        num4 = {s: 15 for s in stamps}
        a, b = A.v4_rows(stamps, dict(den), num4, den), A.v4_rows(stamps, dict(den), num4, den)
        self.assertEqual((a["d_lo"], a["d_hi"]), (b["d_lo"], b["d_hi"]))
        self.assertEqual(A.BOOT_SEED, 20261003)
        self.assertEqual(A.BLOCK, 10)


if __name__ == "__main__":
    unittest.main()
