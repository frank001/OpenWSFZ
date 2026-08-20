#!/usr/bin/env python3
"""N2 -- statistics: thin re-export of N1's n1_stats (spec Sec.5: "reuse the modules, do
not re-derive"). d_ber_row/f_cross_row/cluster_bootstrap_median_diff are generic over any
two paired BER values -- only the CALLER's argument order carries the sign convention.

N2's own sign convention (spec Sec.5, load-bearing):
    d_ber = BER_V0 - BER_V3, POSITIVE = the coherent metric HELPS
which is exactly d_ber_row(ber_v0, ber_v3) using n1_stats' own
"d_ber_row(a, b) = a - b" definition -- no reimplementation, no drift risk.

Spec: qa/rr-study/2026-08-16-1408-architect-to-qa-N2-coherent-llr-extractor-spec.md Sec.5.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "n1-ber-at-refined-position"))

from n1_stats import (  # noqa: E402,F401
    B50_THRESHOLD,
    SEED,
    cluster_bootstrap_median_diff,
    d_ber_row,
    f_cross_row,
)
