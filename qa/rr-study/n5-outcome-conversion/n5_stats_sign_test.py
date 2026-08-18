#!/usr/bin/env python3
"""N5 -- mandatory sign unit test for the NEW statistics this spec introduces (f_break,
f_net). n1_stats.f_cross_row/d_ber_row are reused VERBATIM (Amendment A1.2: "reuse it
VERBATIM; do not redefine it") and already carry N1's own sign unit test; this file
does not re-litigate those. What is new here is f_break_row and the paired bootstrap
(n5_stats.cluster_bootstrap_f_cross_break_net), and HK-021(l) requires a new signed
statistic to carry its own sign test before it gates anything.

Pure statistics test -- no DLL, no WAV corpus, no candidate data. run_n5.py calls this
module's main() directly (alongside n4_sign_unit_test.py's DSP-level check, re-run, not
inherited, per spec ROW 0d) and refuses to arm the real harness unless BOTH return 0.

Case (3) below is the load-bearing one: it directly encodes the defect Amendment 1
exists to catch -- a treatment that converts half the crossable rows while breaking
half the breakable rows must NOT look like a 100% success under f_cross alone.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from n5_stats import (  # noqa: E402
    B50_THRESHOLD, cluster_bootstrap_f_cross_break_net, f_break_row, f_cross_row,
)

N_SYNTH_CLUSTERS = 30
N_ROWS_PER_CLUSTER = 4
TOLERANCE = 1e-9
ABOVE = B50_THRESHOLD + 0.10
BELOW = B50_THRESHOLD - 0.10


def _rows(ber_v0: float, ber_v3: float, n_clusters: int = N_SYNTH_CLUSTERS,
          start: int = 0) -> list[dict]:
    rows = []
    for c in range(start, start + n_clusters):
        ts = "SYNTH_%03d" % c
        for _ in range(N_ROWS_PER_CLUSTER):
            rows.append({
                "ts": ts, "ber_v0": ber_v0,
                "crosses": f_cross_row(ber_v0, ber_v3),
                "breaks": f_break_row(ber_v0, ber_v3),
            })
    return rows


def main() -> int:
    print("=" * 78)
    print("N5 mandatory sign unit test for f_break/f_net (new statistics, Amendment A1.2)")
    print("=" * 78)
    failures = 0

    # (1) Every row crosses (V0 above bar, V3 at/below): f_cross point=1.0, f_break
    #     undefined (no breakable rows -- n_breakable=0), f_net point=+1.0.
    rows1 = _rows(ber_v0=ABOVE, ber_v3=BELOW)
    b1 = cluster_bootstrap_f_cross_break_net(rows1, n_draws=500, seed=1)
    ok1 = (abs(b1["point"]["f_cross"] - 1.0) < TOLERANCE
           and b1["point"]["n_breakable"] == 0
           and abs(b1["point"]["f_net"] - 1.0) < TOLERANCE
           and b1["f_cross"]["ci95"][0] > 0.0)
    print("(1) all rows cross (V0=%.2f V3=%.2f) -> f_cross=%.6f (want 1.0) "
          "n_breakable=%d (want 0) f_net=%.6f (want +1.0) CI_lo(f_cross)=%.4f (want >0) [%s]"
          % (ABOVE, BELOW, b1["point"]["f_cross"], b1["point"]["n_breakable"],
             b1["point"]["f_net"], b1["f_cross"]["ci95"][0], "PASS" if ok1 else "FAIL"))
    failures += 0 if ok1 else 1

    # (2) Negation: every row breaks (V0 at/below bar, V3 above). f_break point=1.0,
    #     f_cross undefined (n_crossable=0), f_net point=-1.0 -- NOT +1.0 (sign, not
    #     magnitude, must differ from case 1).
    rows2 = _rows(ber_v0=BELOW, ber_v3=ABOVE)
    b2 = cluster_bootstrap_f_cross_break_net(rows2, n_draws=500, seed=1)
    ok2 = (abs(b2["point"]["f_break"] - 1.0) < TOLERANCE
           and b2["point"]["n_crossable"] == 0
           and abs(b2["point"]["f_net"] - (-1.0)) < TOLERANCE
           and b2["f_break"]["ci95"][0] > 0.0
           and b2["f_net"]["ci95"][1] < 0.0)
    print("(2) all rows break (V0=%.2f V3=%.2f) -> f_break=%.6f (want 1.0) "
          "n_crossable=%d (want 0) f_net=%.6f (want -1.0) CI_hi(f_net)=%.4f (want <0) [%s]"
          % (BELOW, ABOVE, b2["point"]["f_break"], b2["point"]["n_crossable"],
             b2["point"]["f_net"], b2["f_net"]["ci95"][1], "PASS" if ok2 else "FAIL"))
    failures += 0 if ok2 else 1

    # (3) THE LOAD-BEARING CASE: half the clusters cross, half break, in EQUAL numbers.
    #     f_cross alone (of its own crossable-only denominator) reads 1.0 -- a naive
    #     unamended gate reading f_cross alone would call this a clean win. f_net must
    #     read ~0.0 (net nothing converted) and its CI must NOT clear >0 -- this is
    #     exactly the un-amended-ROW-1 failure mode Amendment A1.2 was written to close.
    half = N_SYNTH_CLUSTERS // 2
    rows3 = (_rows(ber_v0=ABOVE, ber_v3=BELOW, n_clusters=half, start=0)
             + _rows(ber_v0=BELOW, ber_v3=ABOVE, n_clusters=half, start=half))
    b3 = cluster_bootstrap_f_cross_break_net(rows3, n_draws=2000, seed=1)
    f_cross_looks_perfect = abs(b3["point"]["f_cross"] - 1.0) < TOLERANCE
    f_break_also_perfect = abs(b3["point"]["f_break"] - 1.0) < TOLERANCE
    f_net_reads_zero = abs(b3["point"]["f_net"]) < TOLERANCE
    ci_does_not_clear_zero = not (b3["f_net"]["ci95"][0] > 0.0)
    ok3 = f_cross_looks_perfect and f_break_also_perfect and f_net_reads_zero and ci_does_not_clear_zero
    print("(3) half cross, half break (equal N) -> f_cross(own-denom)=%.6f (=1.0, "
          "looks like a clean win) f_break(own-denom)=%.6f (=1.0, equally bad) "
          "f_net=%.6f (want ~0.0) CI(f_net)=%s (must NOT clear 0) [%s]"
          % (b3["point"]["f_cross"], b3["point"]["f_break"], b3["point"]["f_net"],
             b3["f_net"]["ci95"], "PASS" if ok3 else "FAIL"))
    print("    (this is the exact un-amended-ROW-1 failure Amendment A1.2 exists to "
          "close: f_cross alone reads a 100%% win here, f_net correctly reads zero)")
    failures += 0 if ok3 else 1

    # (4) f_cross and f_break are never pooled into a single number -- confirm both
    #     remain independently readable (non-cancelling) even when both are nonzero and
    #     of opposite sign in their contribution to f_net.
    ok4 = ("f_cross" in b3 and "f_break" in b3
           and b3["point"]["f_cross"] != b3["point"]["f_net"]
           and b3["point"]["f_break"] != b3["point"]["f_net"])
    print("(4) f_cross (%.4f) and f_break (%.4f) remain separately reported, neither "
          "equals f_net (%.4f) -- not silently pooled [%s]"
          % (b3["point"]["f_cross"], b3["point"]["f_break"], b3["point"]["f_net"],
             "PASS" if ok4 else "FAIL"))
    failures += 0 if ok4 else 1

    print()
    if failures:
        print("RESULT: FAIL -- %d check(s) failed. DO NOT ARM the real harness." % failures)
        return 1
    print("RESULT: PASS -- f_break/f_net sign behaviour verified, including the "
          "converts-while-breaking case Amendment A1.2 exists to catch. Real harness "
          "may be armed (pending n4_sign_unit_test.py's DSP-level pass too).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
