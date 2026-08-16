#!/usr/bin/env python3
"""N1 -- mandatory sign unit test (spec Sec.4: "Sign unit test, mandatory before arming:
d_ber == +1.0-equivalent on synthetic input where every refined row is perfect and every
grid row is maximally wrong, and the negation reversed. Do not arm until it passes.").

Pure statistics test -- no DLL, no WAV corpus, no candidate data. Exercises exactly the
same code path run_n1.py's gate reads (n1_stats.d_ber_row, f_cross_row,
cluster_bootstrap_median_diff) on synthetic BER pairs, so a sign error in that shared
code is caught here before a single real row is measured.

HK-021 sibling (l): a positional/BER statistic must be signed. This is the durable
finding M5 (withdrawn) carried forward into this spec -- this test is what makes that
finding operational rather than a note in a document.

run_n1.py calls this module's main() directly and refuses to run the real harness unless
it returns 0 (belt-and-braces on top of "run this script first").
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from n1_stats import B50_THRESHOLD, cluster_bootstrap_median_diff, d_ber_row, f_cross_row  # noqa: E402

N_SYNTH_CLUSTERS = 30
N_ROWS_PER_CLUSTER = 4
TOLERANCE = 1e-9


def _synthetic_rows(ber_grid: float, ber_refined: float) -> list[dict]:
    rows = []
    for c in range(N_SYNTH_CLUSTERS):
        ts = "SYNTH_%03d" % c
        for _ in range(N_ROWS_PER_CLUSTER):
            rows.append({
                "ts": ts,
                "ber_grid": ber_grid,
                "ber_refined": ber_refined,
                "d_ber": d_ber_row(ber_grid, ber_refined),
            })
    return rows


def main() -> int:
    print("=" * 78)
    print("N1 mandatory sign unit test (spec Sec.4)")
    print("=" * 78)
    failures = 0

    # (1) Every refined row perfect (BER=0), every grid row maximally wrong (BER=1.0):
    #     d_ber must be +1.0-equivalent (positive = refinement helps).
    rows_pos = _synthetic_rows(ber_grid=1.0, ber_refined=0.0)
    stats_pos = cluster_bootstrap_median_diff(rows_pos, n_draws=500, seed=1)
    ok1 = abs(stats_pos["point_estimate"] - 1.0) < TOLERANCE
    ok1_ci = stats_pos["ci95"][0] > 0.0  # CI entirely positive: unambiguously "refinement helps"
    ok1_p = stats_pos["p_two_sided"] < 0.01
    print("(1) grid=1.0 (maximally wrong), refined=0.0 (perfect) -> "
          "d_ber point_estimate=%+.6f (want +1.000000) [%s]"
          % (stats_pos["point_estimate"], "PASS" if ok1 else "FAIL"))
    print("    CI95=%s (want CI_lo > 0) [%s]; p=%.4f (want < 0.01) [%s]"
          % (stats_pos["ci95"], "PASS" if ok1_ci else "FAIL",
             stats_pos["p_two_sided"], "PASS" if ok1_p else "FAIL"))
    failures += 0 if (ok1 and ok1_ci and ok1_p) else 1

    # (2) Negation reversed: every grid row perfect, every refined row maximally wrong.
    #     d_ber must be -1.0-equivalent (negative = refinement hurts) -- NOT abs(1.0).
    rows_neg = _synthetic_rows(ber_grid=0.0, ber_refined=1.0)
    stats_neg = cluster_bootstrap_median_diff(rows_neg, n_draws=500, seed=1)
    ok2 = abs(stats_neg["point_estimate"] - (-1.0)) < TOLERANCE
    ok2_ci = stats_neg["ci95"][1] < 0.0  # CI entirely negative
    ok2_p = stats_neg["p_two_sided"] < 0.01
    print("(2) grid=0.0 (perfect), refined=1.0 (maximally wrong) -> "
          "d_ber point_estimate=%+.6f (want -1.000000) [%s]"
          % (stats_neg["point_estimate"], "PASS" if ok2 else "FAIL"))
    print("    CI95=%s (want CI_hi < 0) [%s]; p=%.4f (want < 0.01) [%s]"
          % (stats_neg["ci95"], "PASS" if ok2_ci else "FAIL",
             stats_neg["p_two_sided"], "PASS" if ok2_p else "FAIL"))
    failures += 0 if (ok2 and ok2_ci and ok2_p) else 1

    # (3) A naive abs()-based implementation would give the SAME magnitude for (1) and
    #     (2); confirm they differ in SIGN, not just that each individually looks right.
    ok3 = (stats_pos["point_estimate"] > 0) and (stats_neg["point_estimate"] < 0) and \
          abs(stats_pos["point_estimate"] + stats_neg["point_estimate"]) < TOLERANCE
    print("(3) the two point estimates are exact sign-mirrors of each other "
          "(%+.6f / %+.6f) [%s]" % (stats_pos["point_estimate"], stats_neg["point_estimate"],
                                     "PASS" if ok3 else "FAIL"))
    failures += 0 if ok3 else 1

    # (4) f_cross is signed too: a row crossing ABOVE->BELOW the bar must count; a row
    #     crossing BELOW->ABOVE (the harmful direction) must NOT count as a positive
    #     f_cross, and must not cancel against it either (f_cross is not net-signed, it
    #     is one-directional by construction -- verify both directions explicitly).
    above, below = B50_THRESHOLD + 0.10, B50_THRESHOLD - 0.10
    helps = f_cross_row(ber_grid=above, ber_refined=below)   # crosses the helpful way
    hurts = f_cross_row(ber_grid=below, ber_refined=above)   # crosses the harmful way
    neither_up = f_cross_row(ber_grid=above, ber_refined=above)
    ok4 = helps is True and hurts is False and neither_up is False
    print("(4) f_cross: above->below=%s (want True), below->above=%s (want False), "
          "above->above=%s (want False) [%s]"
          % (helps, hurts, neither_up, "PASS" if ok4 else "FAIL"))
    failures += 0 if ok4 else 1

    print()
    if failures:
        print("RESULT: FAIL -- %d check(s) failed. DO NOT ARM the real harness." % failures)
        return 1
    print("RESULT: PASS -- all sign checks passed. Real harness may be armed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
