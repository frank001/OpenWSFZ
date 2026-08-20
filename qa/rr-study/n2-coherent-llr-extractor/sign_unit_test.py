#!/usr/bin/env python3
"""N2 -- mandatory sign unit test (spec Sec.5: "Mandatory sign unit test asserting both
ends on synthetic extremes before arming; the harness must refuse to run without it" --
N1's sign_unit_test.py is the named pattern, reused here unchanged in structure).

Pure statistics test -- no DLL, no WAV corpus, no candidate data, no coherent-extractor
DSP. Exercises exactly the same shared code path run_n2.py's gate reads (n2_stats via
n1_stats: d_ber_row, f_cross_row, cluster_bootstrap_median_diff) on synthetic BER pairs,
so a sign error in that SHARED code is caught here before a single real row is measured.
Identical statistics module to N1 (n2_stats.py is a thin re-export) -- this test is
mechanically the same test, renamed to N2's own V0/V3 vocabulary for clarity.

run_n2.py calls this module's main() directly and refuses to run the real harness unless
it returns 0.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from n2_stats import B50_THRESHOLD, cluster_bootstrap_median_diff, d_ber_row, f_cross_row  # noqa: E402

N_SYNTH_CLUSTERS = 30
N_ROWS_PER_CLUSTER = 4
TOLERANCE = 1e-9


def _synthetic_rows(ber_v0: float, ber_v3: float) -> list[dict]:
    rows = []
    for c in range(N_SYNTH_CLUSTERS):
        ts = "SYNTH_%03d" % c
        for _ in range(N_ROWS_PER_CLUSTER):
            rows.append({
                "ts": ts,
                "ber_v0": ber_v0,
                "ber_v3": ber_v3,
                "d_ber": d_ber_row(ber_v0, ber_v3),
            })
    return rows


def main() -> int:
    print("=" * 78)
    print("N2 mandatory sign unit test (spec Sec.5)")
    print("=" * 78)
    failures = 0

    # (1) Every V3 row perfect (BER=0), every V0 row maximally wrong (BER=1.0):
    #     d_ber must be +1.0-equivalent (positive = the coherent metric helps).
    rows_pos = _synthetic_rows(ber_v0=1.0, ber_v3=0.0)
    stats_pos = cluster_bootstrap_median_diff(rows_pos, n_draws=500, seed=1)
    ok1 = abs(stats_pos["point_estimate"] - 1.0) < TOLERANCE
    ok1_ci = stats_pos["ci95"][0] > 0.0
    ok1_p = stats_pos["p_two_sided"] < 0.01
    print("(1) V0=1.0 (maximally wrong), V3=0.0 (perfect) -> "
          "d_ber point_estimate=%+.6f (want +1.000000) [%s]"
          % (stats_pos["point_estimate"], "PASS" if ok1 else "FAIL"))
    print("    CI95=%s (want CI_lo > 0) [%s]; p=%.4f (want < 0.01) [%s]"
          % (stats_pos["ci95"], "PASS" if ok1_ci else "FAIL",
             stats_pos["p_two_sided"], "PASS" if ok1_p else "FAIL"))
    failures += 0 if (ok1 and ok1_ci and ok1_p) else 1

    # (2) Negation reversed: every V0 row perfect, every V3 row maximally wrong.
    #     d_ber must be -1.0-equivalent (negative = the coherent metric HURTS) -- NOT
    #     abs(1.0).
    rows_neg = _synthetic_rows(ber_v0=0.0, ber_v3=1.0)
    stats_neg = cluster_bootstrap_median_diff(rows_neg, n_draws=500, seed=1)
    ok2 = abs(stats_neg["point_estimate"] - (-1.0)) < TOLERANCE
    ok2_ci = stats_neg["ci95"][1] < 0.0
    ok2_p = stats_neg["p_two_sided"] < 0.01
    print("(2) V0=0.0 (perfect), V3=1.0 (maximally wrong) -> "
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

    # (4) f_cross is signed too: V0-above -> V3-below must count; the reverse (harmful)
    #     direction must NOT count, and must not cancel against it either.
    above, below = B50_THRESHOLD + 0.10, B50_THRESHOLD - 0.10
    helps = f_cross_row(ber_grid=above, ber_refined=below)   # V0 above -> V3 below
    hurts = f_cross_row(ber_grid=below, ber_refined=above)   # V0 below -> V3 above
    neither_up = f_cross_row(ber_grid=above, ber_refined=above)
    ok4 = helps is True and hurts is False and neither_up is False
    print("(4) f_cross: V0above->V3below=%s (want True), V0below->V3above=%s (want "
          "False), V0above->V3above=%s (want False) [%s]"
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
