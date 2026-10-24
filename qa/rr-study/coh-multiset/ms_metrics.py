#!/usr/bin/env python3
"""COH-MULTISET: the three new coherent bit-metric sets J2, J3, N1 (spec section 3.1) and the order-1 set C1, from the per-symbol spectra X.

Written from the PROSE method of the spec (Architect, 2026-10-24) and FT8's public constants. No WSJT-X source was opened, copied or transliterated
(licence policy; Captain 2026-10-24: method only).

Input is the complex matrix X[79, 8] that coherent_extract.correlate_symbols already returns (the SAME estimate C3 uses; one estimate per row).
Output is 174 raw values in the extractor's bit order: data symbol k = 0..57 (raw index DATA_SYM_IDX[k]), three bits each, gray-index bit2, bit1, bit0.
Sign convention: positive = bit 1 (ldpc.c:149). No scaling beyond the export's own normalisation (ftx_ldpc_decode_llrs step 3).

  groups     the 58 data symbols form two halves of 29 (raw 7-35 and 43-71). J2: consecutive non-overlapping pairs, the 29th symbol of a half is a group of one.
             J3: consecutive non-overlapping triples, the last two symbols of a half form a pair. Groups never straddle a Costas block.
  score      for a group of n symbols and each of the 8**n tone hypotheses: |sum_j X[s_j][tone_j]|  (the MAGNITUDE of the coherent sum, not its power).
  bit value  max over hypotheses where the bit is 1 minus max over hypotheses where it is 0, with the gray map applied to each symbol's tone.
             A group of one is plain order-1 on magnitudes.
  N1         order-1 on magnitudes; each bit's value divided by the larger of its two maxima (0 if both are 0).
  C1         the extractor's own V1: order-1 on POWER (|X|**2), unchanged (imported, not re-implemented).

`gray` is a parameter only so that V2b (the mutation check: identity map) can break it on purpose.
"""
from __future__ import annotations

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "n2-coherent-llr-extractor"))
sys.path.insert(0, os.path.join(HERE, "..", "coh-gain"))
import coherent_extract as CE  # noqa: E402

GRAY_MAP = CE.GRAY_MAP                  # (0, 1, 3, 2, 5, 6, 4, 7): public protocol constant
DATA_SYM_IDX = CE.DATA_SYM_IDX
N_DATA = CE.FT8_ND
HALF = 29
assert GRAY_MAP == (0, 1, 3, 2, 5, 6, 4, 7) and N_DATA == 58 and HALF * 2 == N_DATA
assert DATA_SYM_IDX[0] == 7 and DATA_SYM_IDX[HALF - 1] == 35 and DATA_SYM_IDX[HALF] == 43 and DATA_SYM_IDX[-1] == 71
IDENTITY_MAP = tuple(range(8))


def partition(group_size: int) -> list[list[int]]:
    """Groups of data-symbol indices k (0..57) for J2 (group_size 2) or J3 (group_size 3). Each half is split on its own, so no group straddles a Costas block."""
    assert group_size in (2, 3)
    groups = []
    for h in range(2):
        ks = list(range(h * HALF, (h + 1) * HALF))
        i = 0
        while i < len(ks):
            n = min(group_size, len(ks) - i)
            groups.append(ks[i:i + n])
            i += n
    return groups


def _group_bits(X: np.ndarray, ks: list[int], gray) -> np.ndarray:
    """The 3*len(ks) values of one group, in (symbol, bit2, bit1, bit0) order."""
    n = len(ks)
    syms = [DATA_SYM_IDX[k] for k in ks]
    joint = X[syms[0], :]
    for s in syms[1:]:
        joint = joint[..., None] + X[s, :]
    score = np.abs(joint)                      # shape (8,)*n, indexed by TONE on every axis
    for ax in range(n):                        # re-index each axis by GRAY index j: score_g[..., j, ...] = score[..., gray[j], ...]
        score = np.take(score, list(gray), axis=ax)
    out = np.zeros(3 * n)
    for p in range(n):
        other = tuple(ax for ax in range(n) if ax != p)
        by_j = score.max(axis=other) if other else score          # (8,) maximum over the other members' hypotheses, per gray index j of member p
        for b, shift in enumerate((2, 1, 0)):
            ones = [j for j in range(8) if (j >> shift) & 1]
            zeros = [j for j in range(8) if not (j >> shift) & 1]
            out[3 * p + b] = by_j[ones].max() - by_j[zeros].max()
    return out


def grouped(X: np.ndarray, group_size: int, gray=GRAY_MAP) -> np.ndarray:
    """J2 (group_size 2) or J3 (3): the 174 raw values."""
    v = np.zeros(3 * N_DATA)
    for ks in partition(group_size):
        vals = _group_bits(X, ks, gray)
        for p, k in enumerate(ks):
            v[3 * k:3 * k + 3] = vals[3 * p:3 * p + 3]
    return v


def j2(X, gray=GRAY_MAP):
    return grouped(X, 2, gray)


def j3(X, gray=GRAY_MAP):
    return grouped(X, 3, gray)


def n1(X: np.ndarray, gray=GRAY_MAP) -> np.ndarray:
    """Order-1 on magnitudes, each bit divided by the larger of its two maxima."""
    v = np.zeros(3 * N_DATA)
    for k in range(N_DATA):
        by_j = np.abs(X[DATA_SYM_IDX[k], :])[list(gray)]
        for b, shift in enumerate((2, 1, 0)):
            m1 = by_j[[j for j in range(8) if (j >> shift) & 1]].max()
            m0 = by_j[[j for j in range(8) if not (j >> shift) & 1]].max()
            den = max(m1, m0)
            v[3 * k + b] = 0.0 if den == 0 else (m1 - m0) / den
    return v


def c1(X: np.ndarray) -> np.ndarray:
    """The extractor's own V1 (order 1, power), imported unchanged."""
    v = np.zeros(3 * N_DATA)
    for k, sym in enumerate(DATA_SYM_IDX):
        v[3 * k:3 * k + 3] = CE._order1_llr(X, sym)
    return v


def spectra(pcm: np.ndarray, anchor_f: float, anchor_t: float, est: dict) -> np.ndarray:
    """X[79, 8] at C3's own fine-sync estimate: exactly the steps of coherent_extract.extract_variants up to correlate_symbols (the arms share one estimate per row)."""
    import fine_sync as FS
    t = FS.anchor_dt_for_step(anchor_t, est["dt_step"])
    bb = CE.downconvert_decimate(pcm, anchor_f + est["est_df_hz"])
    start = int(round(t * CE.RATE_FINE_HZ)) + CE.TIME_ORIGIN_CORRECTION_SAMPLES_2K
    return CE.correlate_symbols(bb, start)


SETS = {"C1": c1, "J2": j2, "J3": j3, "N1": n1}      # X's fixed order (Architect Amendment 1 / A1.3): C1 > J2 > J3 > N1
ORDER = ("C1", "J2", "J3", "N1")
assert tuple(SETS) == ORDER
