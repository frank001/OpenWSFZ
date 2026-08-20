#!/usr/bin/env python3
"""N3 -- one-shot cross-check: coherent_extract_ext.extract_variants_ext()'s V1/V2_cum/
V3_cum must be BIT-IDENTICAL to N2's own coherent_extract.extract_variants()'s V1/V2/V3,
at df_hz=0.0, on real audio. Catches a copy/refactor drift in the new module before a
single sweep row is measured (HK-018: verify against the already-gathered instrument,
don't re-derive by inspection). Not part of the main harness's hot path (real audio,
DLL not needed) -- run standalone, once, before run_n3.py.
"""
from __future__ import annotations

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
N1_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "n1-ber-at-refined-position")
N2_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "n2-coherent-llr-extractor")
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "r1-sync-refiner"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))
sys.path.insert(0, N2_DIR)
# N1_DIR MUST be inserted LAST (i.e. end up at sys.path[0]): r1-sync-refiner has its OWN,
# unrelated population.py (build_signal_population, not build_matched_hit_control) --
# inserted earlier above, it would otherwise shadow N1's. run_n2.py hits this same trap
# and escapes it only as a side effect of n2_stats.py's own N1_DIR insert running first;
# made explicit and intentional here rather than relying on that accident.
sys.path.insert(0, N1_DIR)
sys.path.insert(0, HERE)

import p23_common as P  # noqa: E402
import coherent_extract as CE  # noqa: E402
from coherent_extract_ext import extract_variants_ext  # noqa: E402
from population import build_matched_hit_control  # noqa: E402
from run_n1 import _anchor  # noqa: E402


def main() -> int:
    control = build_matched_hit_control()
    sample = control[::max(1, len(control) // 12)][:12]
    print("Cross-checking %d control rows (spread across the population): "
          "extract_variants_ext(df=0) vs coherent_extract.extract_variants() must "
          "agree numerically and on every hard decision." % len(sample))
    failures = 0
    from population import WAV68_DIR
    for row in sample:
        pcm = P.read_wav(os.path.join(WAV68_DIR, row["ts"] + ".wav"))
        pcm = P.normalise_rms(pcm, P.PROD_TARGET_RMS)
        anchor_freq, anchor_dt = _anchor(row["grid_freq_hz"], row["grid_dt"])
        pcm64 = np.asarray(pcm, dtype=np.float64)

        ref = CE.extract_variants(pcm64, float(anchor_freq), anchor_dt)
        ext = extract_variants_ext(pcm64, float(anchor_freq), anchor_dt, df_hz=0.0)

        # Numeric (not bit-exact) equality: the two implementations sum the same order-2/
        # order-3 per-symbol contributions in a different association (mine accumulates
        # into a local var first, N2's accumulates straight into the output array across
        # two separate += calls) -- mathematically identical, but floating-point addition
        # is not bit-associative, so a np.array_equal HERE would fail on ~1e-13-relative
        # rounding noise that has zero effect on any hard decision. Checked directly:
        # allclose to a tolerance many orders tighter than any LLR near zero, AND exact
        # hard-decision agreement (the only thing BER actually reads).
        ok_v1 = np.array_equal(ref["V1"], ext["V1"])  # order 1 has no summation at all
        ok_v2 = np.allclose(ref["V2"], ext["V2_cum"], rtol=1e-9, atol=1e-9)
        ok_v3 = np.allclose(ref["V3"], ext["V3_cum"], rtol=1e-9, atol=1e-9)
        hd_v2 = np.array_equal((ref["V2"] > 0.0), (ext["V2_cum"] > 0.0))
        hd_v3 = np.array_equal((ref["V3"] > 0.0), (ext["V3_cum"] > 0.0))
        ok = ok_v1 and ok_v2 and ok_v3 and hd_v2 and hd_v3
        print("  [%s] V1=%s V2_cum(close/hd)=%s/%s V3_cum(close/hd)=%s/%s -> %s"
              % (row["ts"], ok_v1, ok_v2, hd_v2, ok_v3, hd_v3, "PASS" if ok else "FAIL"))
        if not ok:
            failures += 1

    print()
    if failures:
        print("RESULT: FAIL -- %d/%d row(s) diverged. DO NOT proceed to run_n3.py."
              % (failures, len(sample)))
        return 1
    print("RESULT: PASS -- extract_variants_ext reproduces N2's V1/V2/V3 numerically "
          "and on every hard decision, at df=0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
