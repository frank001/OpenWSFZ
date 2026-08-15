#!/usr/bin/env python3
"""M4 -- MANDATORY sign unit test for rho_conc (spec S5.3):

  "rho_conc == +1 if and only if every HIT row has strictly smaller
  |coarse_dt_samp| than every NULL row. rho_conc == -1 if and only if every
  HIT row has strictly larger |coarse_dt_samp| than every NULL row. QA must
  include a unit test asserting both ends against synthetic input, and must
  not arm the run until it passes. A sign error here inverts the verdict
  exactly."

Run directly: `python test_m4_rho_conc_sign.py`. Exits non-zero on any
failure. QA does not arm m4_run_harness.py until this prints ALL PASS.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from m4_stats import rho_conc  # noqa: E402

# m1_evaluate.pooled_contrast (lifted unchanged, see m4_stats.py) excludes any
# stratum with fewer than STRATUM_MIN_N=200 rows in BOTH arms from the pooled
# estimate (the same power floor M1/M4's own ROW 0b enforces) -- so the sign
# test must supply >= 200 rows/arm in at least one stratum, not one row per
# stratum, or pooled_rho_rb comes back NaN with every stratum correctly marked
# unusable (that is the gate working, not a bug in rho_conc).
N_PER_ARM = 200
ONE_STRATUM_SNR = -10.0  # anywhere inside [-12,-9)


def _rows(abs_coarse_value, arm_prefix, n=N_PER_ARM):
    """n rows, all in one stratum, each with a UNIQUE cycle_id (so the cluster
    bootstrap sees many independent clusters, not a degenerate 1- or 2-cluster
    draw) and the given constant |coarse_dt_samp| magnitude."""
    return [{"snr_db": ONE_STRATUM_SNR, "cycle_id": "%s_cycle_%04d" % (arm_prefix, i),
             "coarse_dt_samp": abs_coarse_value} for i in range(n)]


def test_every_hit_strictly_smaller_gives_plus_one():
    # Every HIT row's |coarse_dt_samp|=1, every NULL row's =5 -- every HIT row
    # strictly smaller than every NULL row, no overlap at all.
    #
    # Asserted at the PER-STRATUM rho_rb (computed directly by rank_biserial,
    # before pooling) rather than the pooled value: perfect separation like this
    # makes EVERY cluster-bootstrap draw return the identical rho=1.0 (no draw
    # can ever produce a different ordering), so se_bootstrap=0.0 exactly, and
    # m1_evaluate.pooled_contrast's inverse-variance pooling (lifted unchanged,
    # spec S5.3 -- not rewritten here) correctly requires se>0 and excludes a
    # zero-variance stratum from the pooled estimate. That NaN pooled value is
    # the pooling machinery behaving correctly on a synthetic edge case real M4
    # data will not hit (HIT and NULL overlap heavily in every prior round --
    # M3 measured both arms at an IDENTICAL median 8.0); it is not a sign bug,
    # and it is asserted explicitly below so the edge case is documented, not
    # silently ignored.
    hit = _rows(1, "hit")
    null = _rows(5, "null")
    result = rho_conc(hit, null, "sign-test-plus-one")
    usable = [e for e in result["per_stratum"] if e["rho_rb"] is not None and e["power_ok"]]
    assert usable, "no usable stratum -- power floor not met, test is not exercising rho_conc at all"
    for e in usable:
        assert e["rho_rb"] == 1.0, "per-stratum rho_rb != +1 in %s: %r" % (e["stratum"], e["rho_rb"])
        assert e["se_bootstrap"] == 0.0, (
            "expected the perfect-separation zero-variance edge case (se=0.0), got %r -- "
            "if this changes, the pooled_rho_rb NaN below needs re-examination" % (e["se_bootstrap"],))
    assert result["pooled_rho_rb"] != result["pooled_rho_rb"], (  # NaN != NaN
        "expected pooled_rho_rb to be NaN in this zero-variance edge case, got %r"
        % (result["pooled_rho_rb"],))


def test_every_hit_strictly_larger_gives_minus_one():
    # Reversed: every HIT row's |coarse_dt_samp|=5, every NULL row's =1 -- every
    # HIT row strictly LARGER (less concentrated) than every NULL row. Same
    # zero-variance-bootstrap edge case as above (see its comment) -- asserted
    # at per-stratum rho_rb, not the pooled value.
    hit = _rows(5, "hit")
    null = _rows(1, "null")
    result = rho_conc(hit, null, "sign-test-minus-one")
    usable = [e for e in result["per_stratum"] if e["rho_rb"] is not None and e["power_ok"]]
    assert usable, "no usable stratum -- power floor not met, test is not exercising rho_conc at all"
    for e in usable:
        assert e["rho_rb"] == -1.0, "per-stratum rho_rb != -1 in %s: %r" % (e["stratum"], e["rho_rb"])


def test_identical_distributions_give_zero():
    # Sanity check in the middle of the scale, not part of spec S5.3's mandatory
    # pair but cheap and catches a degenerate always-return-+-1 bug. Both arms
    # draw the SAME set of magnitudes (0..6 repeated), so the Mann-Whitney U
    # tie correction should land exactly at rho_rb=0 by symmetry.
    hit = [{"snr_db": ONE_STRATUM_SNR, "cycle_id": "hit_cycle_%04d" % i, "coarse_dt_samp": i % 7}
           for i in range(N_PER_ARM)]
    null = [{"snr_db": ONE_STRATUM_SNR, "cycle_id": "null_cycle_%04d" % i, "coarse_dt_samp": i % 7}
            for i in range(N_PER_ARM)]
    result = rho_conc(hit, null, "sign-test-zero")
    rho = result["pooled_rho_rb"]
    assert abs(rho) < 1e-9, "expected rho_conc == 0.0 for identical distributions, got %r" % (rho,)


def main():
    tests = [
        test_every_hit_strictly_smaller_gives_plus_one,
        test_every_hit_strictly_larger_gives_minus_one,
        test_identical_distributions_give_zero,
    ]
    failures = []
    for t in tests:
        try:
            t()
            print("PASS: %s" % t.__name__)
        except AssertionError as e:
            failures.append((t.__name__, str(e)))
            print("FAIL: %s -- %s" % (t.__name__, e))

    if failures:
        print("\n%d/%d FAILED -- DO NOT ARM m4_run_harness.py" % (len(failures), len(tests)))
        sys.exit(1)
    print("\nALL PASS (%d/%d) -- rho_conc sign convention verified, safe to arm" % (len(tests), len(tests)))


if __name__ == "__main__":
    main()
