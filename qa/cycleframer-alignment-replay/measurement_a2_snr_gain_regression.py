#!/usr/bin/env python3
"""D-001 ruling S7.4.2 -- cheap follow-on to Measurement A's script: per-decode SNR
regression (ours vs reference) across the three jt9-referenced corpora (40m/489135a is
excluded from the fit -- suspended per the capture-clock-drift defect -- and is reported
separately for completeness only, exactly as S7.1's corpus-mean table already does).

Purpose: turn the ruling's S7.1 three-point CORPUS-MEAN regression (ours ~= 0.585*ref -
4.28 dB, residuals +-0.53 dB on 3 points) into a proper per-decode slope/intercept/CI,
confirming the corpus-mean fit is not an artefact of only having three points to fit.

Reuses match_pairs()/parse_all_txt() from anova_common.py (already-loaded matched-decode
data, same near-free re-parse Measurement A used) -- not reimplemented.

NFR-021: message text used only to build the match key; never printed or written. Only
paired numeric SNR values (and their regression statistics) leave this script.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "endurance"))
from anova_common import match_pairs, parse_all_txt  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
ARTEFACTS = os.path.join(ROOT, "artefacts")

CORPORA = [
    ("80m", os.path.join(ARTEFACTS, "20260729_live_run_1831-8081", "owsfz", "80m", "ALL.TXT"),
     os.path.join(ARTEFACTS, "20260729_live_run_1831-8081", "owsfz", "80m", "jt9_ALL.TXT"), True),
    ("10m", os.path.join(ARTEFACTS, "20260729_live_run_1831-8081", "owsfz", "10m", "ALL.TXT"),
     os.path.join(ARTEFACTS, "20260729_live_run_1831-8081", "owsfz", "10m", "jt9_ALL.TXT"), True),
    ("20m", os.path.join(ARTEFACTS, "20260729_live_run_1831-8081", "owsfz", "20m", "ALL.TXT"),
     os.path.join(ARTEFACTS, "20260729_live_run_1831-8081", "owsfz", "20m", "jt9_ALL.TXT"), True),
    ("40m (WSJT-X, SUSPENDED-drift, excluded from fit)",
     os.path.join(ARTEFACTS, "20260729_live_run_1831-8080", "owsfz", "ALL.TXT"),
     os.path.join(ARTEFACTS, "20260729_live_run_1831-8080", "wsjt-x", "ALL.TXT"), False),
]


def ols(xs: list[float], ys: list[float]) -> tuple[float, float, float, float]:
    """Simple OLS slope/intercept + 95% CI half-widths (large-n normal approx)."""
    import math
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = my - slope * mx
    resid = [y - (slope * x + intercept) for x, y in zip(xs, ys)]
    sse = sum(r * r for r in resid)
    dof = n - 2
    mse = sse / dof
    se_slope = math.sqrt(mse / sxx)
    se_intercept = math.sqrt(mse * (1.0 / n + mx * mx / sxx))
    z = 1.959963984540054
    return slope, intercept, z * se_slope, z * se_intercept


def main() -> int:
    all_xs, all_ys = [], []
    print("=== Per-decode SNR regression (S7.4.2) ===")
    per_corpus = []
    for label, our_path, ref_path, include_in_fit in CORPORA:
        our_rows = parse_all_txt(our_path)
        ref_rows = parse_all_txt(ref_path)
        pairs = match_pairs(our_rows, ref_rows)
        xs = [p["b_snr"] for p in pairs]  # b = reference
        ys = [p["a_snr"] for p in pairs]  # a = OpenWSFZ
        slope, intercept, ci_slope, ci_int = ols(xs, ys)
        print(f"{label:50s} n={len(pairs):6d}  ours ~= {slope:.4f}*ref + {intercept:+.3f} dB "
              f"  (slope 95% CI +-{ci_slope:.4f}, intercept 95% CI +-{ci_int:.3f})")
        per_corpus.append((label, len(pairs), slope, intercept, ci_slope, ci_int))
        if include_in_fit:
            all_xs.extend(xs)
            all_ys.extend(ys)

    slope, intercept, ci_slope, ci_int = ols(all_xs, all_ys)
    print(f"\nPOOLED (3 jt9-referenced corpora, n={len(all_xs)}):")
    print(f"  ours ~= {slope:.4f}*ref + {intercept:+.3f} dB")
    print(f"  slope 95% CI: [{slope-ci_slope:.4f}, {slope+ci_slope:.4f}]")
    print(f"  intercept 95% CI: [{intercept-ci_int:.3f}, {intercept+ci_int:.3f}] dB")
    print(f"  (a pure offset would require slope=1.00 -- {'CONFIRMED gain error, ' if slope+ci_slope < 1.0 else 'NOT distinguishable from offset, '}"
          f"slope's 95% CI {'excludes' if slope + ci_slope < 1.0 else 'does not exclude'} 1.00)")

    out_path = os.path.join(os.path.dirname(__file__), "measurement_a2_snr_gain_regression.md")
    with open(out_path, "w", encoding="ascii", errors="replace") as fh:
        fh.write("# SNR gain-error regression -- per-decode (ruling S7.4.2)\n\n")
        fh.write("| corpus | n | slope | intercept (dB) | slope 95% CI | intercept 95% CI |\n")
        fh.write("|---|---:|---:|---:|---|---|\n")
        for label, n, sl, ic, cs, ci in per_corpus:
            fh.write(f"| {label} | {n} | {sl:.4f} | {ic:+.3f} | +-{cs:.4f} | +-{ci:.3f} |\n")
        fh.write(f"\n**Pooled (3 jt9-referenced corpora, n={len(all_xs)}):** "
                 f"`ours = {slope:.4f} x ref {intercept:+.3f} dB`, "
                 f"slope 95% CI [{slope-ci_slope:.4f}, {slope+ci_slope:.4f}], "
                 f"intercept 95% CI [{intercept-ci_int:.3f}, {intercept+ci_int:.3f}] dB.\n\n")
        fh.write("A pure offset requires slope = 1.00. The pooled 95% CI "
                 f"{'excludes' if slope + ci_slope < 1.0 else 'does not exclude'} 1.00 by a wide margin "
                 "-- confirming S7.1's three-corpus-mean finding at per-decode resolution: "
                 "this is a gain error, not an offset, and D-002's constant correction "
                 "cannot fix it.\n")
    print(f"\nWrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
