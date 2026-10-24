#!/usr/bin/env python3
"""Tests for ms_metrics.py (COH-MULTISET). Run: python -I qa/rr-study/coh-multiset/test_ms_metrics.py
Synthetic spectra only; no audio, no DLL, no message text."""
from __future__ import annotations

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ms_metrics as M  # noqa: E402

COSTAS_RAW = set(range(0, 7)) | set(range(36, 43)) | set(range(72, 79))


def make_X(rng, amp=1.0, noise=0.05, phase=0.7):
    """A clean FT8 spectrum: every symbol carries one tone at constant carrier phase. Returns (X, truth_bits[174])."""
    X = noise * (rng.standard_normal((79, 8)) + 1j * rng.standard_normal((79, 8)))
    truth = np.zeros(174, dtype=int)
    for k, sym in enumerate(M.DATA_SYM_IDX):
        j = int(rng.integers(0, 8))                       # gray index = the three coded bits
        X[sym, M.GRAY_MAP[j]] += amp * np.exp(1j * phase)
        truth[3 * k:3 * k + 3] = ((j >> 2) & 1, (j >> 1) & 1, j & 1)
    return X, truth


def bit_errors(v, truth):
    return int(np.sum((v > 0).astype(int) != truth))


class Grouping(unittest.TestCase):
    """A1.4: J2 = 14 pairs + 1 single per half; J3 = 9 triples + 1 pair per half; no group touches a Costas symbol or straddles a half."""

    def check(self, size, full, tail):
        groups = M.partition(size)
        self.assertEqual(sorted(k for g in groups for k in g), list(range(58)), "every data symbol exactly once")
        for h in range(2):
            gh = [g for g in groups if g[0] // 29 == h]
            self.assertTrue(all(g[-1] // 29 == h for g in gh), "no group straddles the halves")
            self.assertEqual([len(g) for g in gh], [size] * full + [tail])
        for g in groups:
            raw = [M.DATA_SYM_IDX[k] for k in g]
            self.assertFalse(set(raw) & COSTAS_RAW, "no Costas symbol in a group")
            self.assertEqual(raw, list(range(raw[0], raw[0] + len(raw))), "raw-consecutive")

    def test_j2(self):
        self.check(2, 14, 1)
        self.assertEqual(len(M.partition(2)), 30)

    def test_j3(self):
        self.check(3, 9, 2)
        self.assertEqual(len(M.partition(3)), 20)


class CleanSignal(unittest.TestCase):
    def test_all_sets_decode_clean_bits(self):
        rng = np.random.default_rng(20261024)
        for _ in range(20):
            X, truth = make_X(rng)
            for name, fn in M.SETS.items():
                self.assertEqual(bit_errors(fn(X), truth), 0, name)

    def test_identity_gray_map_breaks_the_joint_sets(self):
        """V2b in miniature: a wrong bit map must break a correct metric (HK-021 (k))."""
        rng = np.random.default_rng(1)
        X, truth = make_X(rng)
        for fn in (M.j2, M.j3):
            self.assertEqual(bit_errors(fn(X), truth), 0)
            self.assertGreater(bit_errors(fn(X, gray=M.IDENTITY_MAP), truth), 30)

    def test_single_symbol_group_is_order_one_on_magnitudes(self):
        rng = np.random.default_rng(2)
        X, _ = make_X(rng)
        v = M.j2(X)
        k = 28                                                         # last data symbol of the first half: a group of one
        by_j = np.abs(X[M.DATA_SYM_IDX[k], :])[list(M.GRAY_MAP)]
        want = [by_j[[j for j in range(8) if (j >> s) & 1]].max() - by_j[[j for j in range(8) if not (j >> s) & 1]].max() for s in (2, 1, 0)]
        np.testing.assert_allclose(v[3 * k:3 * k + 3], want)

    def test_joint_pair_uses_magnitude_of_coherent_sum(self):
        """Two symbols with opposite phase and one hypothesis each: |a + b| is small, so a mis-phased pair scores low (the magnitude, not a power sum)."""
        X = np.zeros((79, 8), dtype=complex)
        k = 0
        s0, s1 = M.DATA_SYM_IDX[0], M.DATA_SYM_IDX[1]
        X[s0, M.GRAY_MAP[7]] = 1.0
        X[s1, M.GRAY_MAP[7]] = -1.0
        v = M.j2(X)
        self.assertAlmostEqual(abs(v[0]), 0.0, places=9)               # cancelling pair: |1 + (-1)| = 0 on the best hypotheses
        X[s1, M.GRAY_MAP[7]] = 1.0
        self.assertAlmostEqual(M.j2(X)[0], 1.0, places=9)              # in-phase pair: best 1-hypothesis |1 + 1| = 2, best 0-hypothesis |1 + 0| = 1, so 2 - 1


class N1(unittest.TestCase):
    def test_bounded_and_zero_safe(self):
        rng = np.random.default_rng(3)
        X, _ = make_X(rng)
        v = M.n1(X)
        self.assertTrue(np.all(np.abs(v) <= 1.0 + 1e-12))
        np.testing.assert_array_equal(M.n1(np.zeros((79, 8), dtype=complex)), np.zeros(174))

    def test_sets_have_174_values_and_fixed_order(self):
        rng = np.random.default_rng(4)
        X, _ = make_X(rng)
        self.assertEqual(M.ORDER, ("C1", "J2", "J3", "N1"))
        for fn in M.SETS.values():
            self.assertEqual(fn(X).shape, (174,))


if __name__ == "__main__":
    unittest.main(verbosity=2)
