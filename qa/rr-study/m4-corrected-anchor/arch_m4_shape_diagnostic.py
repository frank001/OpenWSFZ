#!/usr/bin/env python3
"""ARCHITECT diagnostic, written while ruling on M4 -- NOT a QA harness, NOT a
re-read of M4's gate with a better metric.

Purpose, and the only purpose: M4's report (S4) claims HIT/MISS carry a coherent
POSITIVE residual bias in signed coarse_dt_samp that NULL does not share, and
offers "the corrected anchor is still ~35-40ms short for real signals" as a
hypothesis. Neither the report nor the spec contains the DISTRIBUTION SHAPE, and
the hypothesis is a claim about shape: a locating refiner under a short anchor
produces a TIGHT INTERIOR MODE at +delta; a non-locating refiner produces a
BROAD ramp. Those are distinguishable from data already on disk.

This establishes whether a VALIDITY precondition of ROW 1/2/3 held. It is the
same move as the M2 ruling's recomputation from committed m2_results.json.

DELIBERATELY NOT COMPUTED HERE: any HIT-vs-NULL contrast on a RE-CENTRED
statistic. That is the next round's question and it must be pre-registered
before anyone sees it (the same discipline as the M4 spec's own S5.5 note).
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

RESULTS = os.path.join(os.path.dirname(__file__), "results", "m4_results.json")
RAIL = 12


def median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return float("nan")
    return float(s[n // 2]) if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def main():
    with open(RESULTS, encoding="utf-8") as fh:
        blob = json.load(fh)
    rows = blob["results"]
    print("rows=%d  anchor_correction_s=%s  shim=%s"
          % (len(rows), blob["anchor_correction_s"], blob["shim_version"]))

    by_arm = defaultdict(list)
    for r in rows:
        by_arm[r["arm"]].append(r)

    # ---- 1. Full signed histogram, all 25 coarse bins -----------------------
    print("\n=== 1. SIGNED coarse_dt_samp HISTOGRAM (pct of arm) ===")
    hdr = "  d   " + "".join("%8s" % a for a in ("HIT", "MISS", "NULL", "CONTROL"))
    print(hdr)
    for d in range(-RAIL, RAIL + 1):
        line = " %+3d  " % d
        for a in ("HIT", "MISS", "NULL", "CONTROL"):
            arm = by_arm[a]
            n = sum(1 for r in arm if r["coarse_dt_samp"] == d)
            line += "%7.2f%%" % (100.0 * n / max(len(arm), 1))
        print(line)

    # ---- 2. Interior shape: is there a MODE strictly inside the aperture? ---
    print("\n=== 2. INTERIOR SHAPE (rail bins |d|=12 EXCLUDED) ===")
    print("A locating refiner under a short anchor => sharp interior mode at +delta.")
    print("A non-locating refiner => no interior mode above the uniform floor.")
    for a in ("HIT", "MISS", "NULL", "CONTROL"):
        arm = by_arm[a]
        interior = [r["coarse_dt_samp"] for r in arm if abs(r["coarse_dt_samp"]) < RAIL]
        if not interior:
            continue
        counts = {d: interior.count(d) for d in range(-RAIL + 1, RAIL)}
        mode_d = max(counts, key=lambda k: counts[k])
        n_int = len(interior)
        uni = 100.0 / 23.0  # 23 interior bins
        peak_pct = 100.0 * counts[mode_d] / n_int
        # mass within +/-2 bins of the mode
        near = sum(counts.get(mode_d + k, 0) for k in (-2, -1, 0, 1, 2))
        near_pct = 100.0 * near / n_int
        uni_near = 100.0 * 5 / 23.0
        print("  %-8s n_interior=%6d  mode d=%+3d  peak=%5.2f%% (uniform %.2f%%, %.2fx)"
              "  within +/-2 of mode=%5.2f%% (uniform %.2f%%, %.2fx)"
              % (a, n_int, mode_d, peak_pct, uni, peak_pct / uni,
                 near_pct, uni_near, near_pct / uni_near))

    # ---- 3. One-sided rail asymmetry ---------------------------------------
    print("\n=== 3. RAIL ASYMMETRY (ROW 0c gated on |d|==12, sign-blind) ===")
    print("One-sided uniform floor = 1/25 = 4.00%; two-sided = 8.00%")
    for a in ("HIT", "MISS", "NULL", "CONTROL"):
        arm = by_arm[a]
        n = len(arm)
        pos = sum(1 for r in arm if r["coarse_dt_samp"] == RAIL)
        neg = sum(1 for r in arm if r["coarse_dt_samp"] == -RAIL)
        print("  %-8s n=%6d  +12=%6d (%5.2f%%, %.2fx one-sided floor)  -12=%5d (%5.2f%%)  ratio=%s"
              % (a, n, pos, 100.0 * pos / n, (100.0 * pos / n) / 4.0, neg, 100.0 * neg / n,
                 ("%.1f:1" % (pos / neg)) if neg else "inf"))

    # ---- 4. Is the centre SNR-flat? (anchor-convention signature) -----------
    print("\n=== 4. MEDIAN SIGNED coarse_dt_samp BY SNR STRATUM ===")
    print("A fixed CONVENTION offset is SNR-FLAT (M3's signature). A signal-dependent")
    print("effect scales with SNR.")
    edges = [(-24, -21), (-21, -18), (-18, -15), (-15, -12), (-12, -9), (-9, -6), (-6, 999)]
    print("  %-12s %8s %8s %8s" % ("stratum", "HIT", "MISS", "NULL"))
    for lo, hi in edges:
        line = "  [%3d,%4s) " % (lo, hi if hi != 999 else "inf")
        for a in ("HIT", "MISS", "NULL"):
            xs = [r["coarse_dt_samp"] for r in by_arm[a] if lo <= r["snr_db"] < hi]
            line += "%8s" % (("%+.1f" % median(xs)) if xs else "-")
        print(line)

    # ---- 5. Interior mode by stratum (same question, mode not median) ------
    print("\n=== 5. INTERIOR MODE BY SNR STRATUM (rail excluded) ===")
    print("  %-12s %14s %14s %14s" % ("stratum", "HIT", "MISS", "NULL"))
    for lo, hi in edges:
        line = "  [%3d,%4s) " % (lo, hi if hi != 999 else "inf")
        for a in ("HIT", "MISS", "NULL"):
            xs = [r["coarse_dt_samp"] for r in by_arm[a]
                  if lo <= r["snr_db"] < hi and abs(r["coarse_dt_samp"]) < RAIL]
            if not xs:
                line += "%14s" % "-"
                continue
            counts = {d: xs.count(d) for d in set(xs)}
            m = max(counts, key=lambda k: counts[k])
            line += "%14s" % ("%+d (%.1f%%)" % (m, 100.0 * counts[m] / len(xs)))
        print(line)

    # ---- 6. CONTROL as the reference shape ---------------------------------
    print("\n=== 6. CONTROL (known truth, correctly anchored) -- what a LOCK looks like ===")
    ctl = [r["coarse_dt_samp"] for r in by_arm["CONTROL"]]
    if ctl:
        for k in (0, 1, 2, 3):
            n = sum(1 for d in ctl if abs(d) <= k)
            print("    |d| <= %d : %6.2f%%" % (k, 100.0 * n / len(ctl)))

    # ---- 7. Concentration ABOUT EACH ARM'S OWN CENTRE -- NOT COMPUTED ------
    print("\n=== 7. RE-CENTRED HIT-vs-NULL CONTRAST: DELIBERATELY NOT COMPUTED ===")
    print("  That is the next round's pre-registered question. Computing it here")
    print("  would be the M1 error (reading a fork the gate did not license) and")
    print("  would destroy the next gate's pre-registration.")


if __name__ == "__main__":
    main()
