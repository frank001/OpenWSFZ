#!/usr/bin/env python3
"""N3 -- extends N2's coherent_extract.py with the two PURE (non-cumulative) variants
the requirement measurement needs.

Spec: qa/rr-study/2026-08-16-1608-architect-to-qa-n2-ruling-and-n3-frequency-requirement-spec.md
Sec.4.2: "order 2 cumulative (V2 as implemented) and order 2 pure (order-2 max-log
alone)... order 3 cumulative (V3 as implemented) and order 3 pure. The pure/cumulative
pair is what separates Sec.2.2's confound. Both are required."

Sec.2.2's confound: N2's V1<V2<V3 ladder conflates (i) frequency sensitivity genuinely
growing with coherent order and (ii) V3 = V1 + pairs + triples inheriting V1's and V2's
already-corrupted terms on top of its own. A PURE order-n statistic (the order-n
contribution ALONE, with no lower-order terms summed in) cannot inherit anything -- if
its own W_n is still narrower than order 1's, that isolates (i); if PURE and CUMULATIVE
report near-identical W_n, (ii) was the dominant driver of N2's ladder, not (i).

This module does NOT modify coherent_extract.py (N2's own file, already gated and
reported on) -- it re-derives the identical per-symbol correlation matrix X via
coherent_extract's OWN building blocks (downconvert_decimate, correlate_symbols,
_order1_llr, _order2_llr_contrib, _order3_llr_contrib) so a second, independently-
typed implementation cannot drift from N2's (the exact failure mode BOARD.md's N2
ruling Sec.1(b)/(c) just diagnosed for a DIFFERENT reused helper, _anchor -- reusing
the CORRELATION MATH here is safe because df_hz folds into the downconversion carrier
BEFORE this point, per coherent_extract.py's own Sec.4.1 docstring, so there is no
lattice-snap boundary inside this function for a reused helper to silently cross).

Cross-check (see coherent_extract_ext_selftest.py): at df_hz=0.0, this module's V1/
V2_cum/V3_cum must be bit-identical to coherent_extract.extract_variants()'s V1/V2/V3
on the same input -- run once, at import time is too expensive (needs real audio), so
it is a standalone script, not an assertion baked into the hot path.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "n2-coherent-llr-extractor"))
import numpy as np

import coherent_extract as CE  # noqa: E402 -- N2's own module, reused unmodified

# Re-exported so callers (run_n3.py, the sign unit test) need only import this module.
SAMPLE_RATE_HZ = CE.SAMPLE_RATE_HZ
BUFFER_SAMPLES = CE.BUFFER_SAMPLES
SYMBOL_PERIOD_S = CE.SYMBOL_PERIOD_S
RATE_FINE_HZ = CE.RATE_FINE_HZ
N_SYM = CE.N_SYM
DATA_SYM_IDX = CE.DATA_SYM_IDX
TIME_ORIGIN_CORRECTION_SAMPLES_2K = CE.TIME_ORIGIN_CORRECTION_SAMPLES_2K
true_bits_from_tones = CE.true_bits_from_tones

VARIANT_NAMES = ("V1", "V2_cum", "V2_pure", "V3_cum", "V3_pure")


def extract_variants_ext(pcm: np.ndarray, anchor_freq_hz: float, anchor_dt_s: float,
                          df_hz: float = 0.0) -> dict[str, np.ndarray]:
    """Returns {"V1", "V2_cum", "V2_pure", "V3_cum", "V3_pure"} -> float64 arr174 RAW
    (pre-normalisation) LLRs, 174-bit ordering identical to coherent_extract.extract_
    variants(). V1/V2_cum/V3_cum are bit-identical to that function's V1/V2/V3 (same
    math, same call order) -- V2_pure and V3_pure are the new quantities Sec.4.2 needs:
    the order-n contribution ALONE, with no lower-order terms summed in."""
    carrier = anchor_freq_hz + df_hz
    bb = CE.downconvert_decimate(pcm, carrier)
    start = int(round(anchor_dt_s * RATE_FINE_HZ)) + TIME_ORIGIN_CORRECTION_SAMPLES_2K
    X = CE.correlate_symbols(bb, start)

    v1 = np.zeros(174, dtype=np.float64)
    v2_cum = np.zeros(174, dtype=np.float64)
    v2_pure = np.zeros(174, dtype=np.float64)
    v3_cum = np.zeros(174, dtype=np.float64)
    v3_pure = np.zeros(174, dtype=np.float64)

    for k, sym in enumerate(DATA_SYM_IDX):
        b0 = 3 * k
        l0, l1, l2 = CE._order1_llr(X, sym)
        v1[b0:b0 + 3] = (l0, l1, l2)
        v2_cum[b0:b0 + 3] = (l0, l1, l2)
        v3_cum[b0:b0 + 3] = (l0, l1, l2)

        pair0 = pair1 = pair2 = 0.0
        for other in (sym - 1, sym + 1):
            if 0 <= other < N_SYM:
                dl0, dl1, dl2 = CE._order2_llr_contrib(X, sym, other)
                pair0 += dl0; pair1 += dl1; pair2 += dl2
        v2_cum[b0] += pair0; v2_cum[b0 + 1] += pair1; v2_cum[b0 + 2] += pair2
        v3_cum[b0] += pair0; v3_cum[b0 + 1] += pair1; v3_cum[b0 + 2] += pair2
        v2_pure[b0:b0 + 3] = (pair0, pair1, pair2)

        trip0 = trip1 = trip2 = 0.0
        for a, b, c, self_pos in (
            (sym - 2, sym - 1, sym, 2),
            (sym - 1, sym, sym + 1, 1),
            (sym, sym + 1, sym + 2, 0),
        ):
            if 0 <= a < N_SYM and 0 <= c < N_SYM:
                dl0, dl1, dl2 = CE._order3_llr_contrib(X, a, b, c, self_pos)
                trip0 += dl0; trip1 += dl1; trip2 += dl2
        v3_cum[b0] += trip0; v3_cum[b0 + 1] += trip1; v3_cum[b0 + 2] += trip2
        v3_pure[b0:b0 + 3] = (trip0, trip1, trip2)

    return {"V1": v1, "V2_cum": v2_cum, "V2_pure": v2_pure,
            "V3_cum": v3_cum, "V3_pure": v3_pure}
