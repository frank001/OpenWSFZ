#!/usr/bin/env python3
"""N3 -- statistics: the frequency-accuracy requirement width W_n and its argmin df*_n.

Spec: qa/rr-study/2026-08-16-1608-architect-to-qa-n2-ruling-and-n3-frequency-requirement-spec.md
Sec.4.2's primary statistic: "W_n = the total width in Hz of the df window within which
order-n's median BER stays below B50=11.3%." B50_THRESHOLD is reused UNCHANGED from N1's
n1_stats (spec Sec.4.2 itself defines B50 as "the measured correction threshold" -- the
same constant every prior round in this thread has gated on).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "n1-ber-at-refined-position"))
from n1_stats import B50_THRESHOLD  # noqa: E402,F401

# Spec Sec.4.2: "a common df applied to all rows, df in [-4.0,+4.0] Hz, step 0.25 Hz =
# 33 points. Wide by construction: +-2.06 Hz is the anchor error, and the curve must be
# seen to flatten on both sides of it." Shared by run_n3.py and n3_sign_unit_test.py so
# the sign test exercises the EXACT grid the real gate reads, not a proxy.
import numpy as _np  # noqa: E402

DF_SWEEP_HZ = tuple(round(float(x), 2) for x in _np.arange(-4.0, 4.0 + 1e-9, 0.25))
assert len(DF_SWEEP_HZ) == 33, len(DF_SWEEP_HZ)
assert DF_SWEEP_HZ[0] == -4.0 and DF_SWEEP_HZ[-1] == 4.0
DF_GRID_STEP_HZ = 0.25


def width_below_threshold(xs: "list[float]", ys: "list[float]", threshold: float) -> float:
    """Total measure, in the same units as `xs`, of {x : the piecewise-LINEAR
    interpolant through (xs, ys) is < threshold}, over the sampled range only (nothing
    outside [xs[0], xs[-1]] is claimed). `xs` must be sorted ascending.

    Deliberately does NOT assume the curve is unimodal (single dip) -- a multi-region
    below-threshold curve is summed across every region it appears in. Crossing points
    within a segment are found by linear interpolation between the two samples that
    bracket the crossing; this is the correct measure of a REQUIREMENT gate whose
    boundaries (0.5 Hz / 2.0 Hz) are far coarser than the 0.25 Hz sample step, so the
    interpolation error is a small fraction of a grid cell either way.
    """
    assert len(xs) == len(ys) and len(xs) >= 2
    total = 0.0
    for i in range(len(xs) - 1):
        x0, x1 = xs[i], xs[i + 1]
        y0, y1 = ys[i], ys[i + 1]
        seg = x1 - x0
        b0, b1 = y0 < threshold, y1 < threshold
        if b0 and b1:
            total += seg
        elif b0 and not b1:
            frac = (threshold - y0) / (y1 - y0)
            total += seg * frac
        elif b1 and not b0:
            frac = (threshold - y1) / (y0 - y1)
            total += seg * frac
        # neither below threshold: contributes 0
    return total


def argmin_curve(xs: "list[float]", ys: "list[float]") -> float:
    """The grid point `x` at which `y` is smallest. A median-of-samples curve routinely
    ties EXACTLY across several adjacent grid points near its minimum (a real plateau,
    not noise: order-1's own near-zero-offset response is close to flat over roughly a
    Hz, per Sec.1(e)'s "V0 is a deliberately broad response" and the sign unit test's own
    empirical calibration -- n3_sign_unit_test.py, which validates exactly this
    reduction). Breaking the tie at either EDGE of that plateau (e.g. "closest to df=0")
    is a biased estimator of the true offset by construction; the CENTROID of the tied
    set is not, and the sign unit test confirms it recovers an injected offset exactly
    where an edge-based tie-break would have been off by most of a Hz. The spec does not
    prescribe a tie-break; this one is documented and empirically validated rather than
    left to dict/list iteration order."""
    y_min = min(ys)
    tied = [x for x, y in zip(xs, ys) if y == y_min]
    return float(sum(tied) / len(tied))


def edge_flat(xs: "list[float]", ys: "list[float]", span_hz: float = 1.0,
              tol_pp: float = 0.01) -> tuple[bool, bool, float, float]:
    """ROW 0b's flattening check: has the curve stopped moving over the outermost
    `span_hz` at EACH end? Returns (left_flat, right_flat, left_change, right_change),
    change = |y(edge) - y(edge - span_hz inward)|, in absolute BER units (0-1 scale;
    the CALLER converts to pp for logging). `xs` assumed sorted ascending and to
    contain an exact grid point `span_hz` in from each edge (true for the N3 33-point
    -4.0..+4.0 step-0.25 grid: 1.0 Hz = 4 grid steps)."""
    lo_target = xs[0] + span_hz
    hi_target = xs[-1] - span_hz
    i_lo = next(i for i, x in enumerate(xs) if abs(x - lo_target) < 1e-9)
    i_hi = next(i for i, x in enumerate(xs) if abs(x - hi_target) < 1e-9)
    left_change = abs(ys[0] - ys[i_lo])
    right_change = abs(ys[-1] - ys[i_hi])
    return left_change < tol_pp, right_change < tol_pp, left_change, right_change
