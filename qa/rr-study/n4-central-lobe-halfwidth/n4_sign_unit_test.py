#!/usr/bin/env python3
"""N4 -- mandatory sign unit test (spec Sec.4.4: "Spec Sec.4.4's test from N3, reused
verbatim including QA's 48-realisation / -18 dB correction. The harness refuses to arm
without it. Re-run it -- do not inherit the pass.").

Identical method and calibration to n3_sign_unit_test.py (N3's own DSP-level sign test,
distinct from the generic stats sign test N1/N2 also ran): render N_SEEDS=48 independent
noise realisations of the same message at SNR_DB=-18 (the empirically-derived level at
which a NOISELESS single realisation would saturate hard-decision BER at 0.0% over
several Hz and could not detect a sign flip at all), inject a known df_inject by
deliberately offsetting the synthetic anchor_freq_hz away from the true carrier, sweep,
and assert the resulting median-BER curve's minimum lands at df = -df_inject.

The only change from N3: this test now runs on N4's own two-resolution grid
(n4_stats.DF_SWEEP_HZ) rather than N3's uniform 0.25 Hz grid, and the tolerance is one
CORE grid step (n4_stats.DF_CORE_STEP_HZ = 0.125 Hz) -- all four injected offsets are
exact multiples of 0.125 Hz and sit well inside the +-2.5 Hz core, so they land on
sampled core grid points exactly as N3's did on its own uniform grid.

No DLL, no WAV corpus -- pure synth + coherent_extract_ext. ~2-3 min.

run_n4.py calls this module's main() directly and refuses to run the real harness
unless it returns 0.
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study"))  # `synth` package
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n2-coherent-llr-extractor"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n3-frequency-requirement"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-ber-at-refined-position"))
sys.path.insert(0, HERE)

import p23_common as P  # noqa: E402
from coherent_extract_ext import (  # noqa: E402
    BUFFER_SAMPLES,
    SAMPLE_RATE_HZ,
    SYMBOL_PERIOD_S,
    extract_variants_ext,
    true_bits_from_tones,
)
from extract_llrs_ctypes import hard_decision_ber  # noqa: E402
from n4_stats import DF_CORE_STEP_HZ, DF_SWEEP_HZ, argmin_curve  # noqa: E402

SYNTH_MESSAGE = "CQ Q1SG JO22"    # NFR-021: same synthetic call as N3's own sign test
                                  # (this test never shares a cached buffer with a real
                                  # harness row, and this file's cache is process-local).
SYNTH_TRUE_FREQ_HZ = 1200.0
SYNTH_DT_S = 0.48                 # exact multiple of 0.08s (native lattice step)

DF_INJECT_VALUES = (-1.75, -0.50, 0.50, 1.25)   # unchanged from N3: all four are exact
                                                  # multiples of 0.125 Hz and sit inside
                                                  # the +-2.5 Hz core region.
TOLERANCE_HZ = DF_CORE_STEP_HZ    # one core grid step (spec: "within one grid step")
SNR_DB = -18.0
N_SEEDS = 48
CHECK_VARIANTS = ("V1", "V3_cum")


def _render_seeds(tones):
    from synth import encoder as synth_encoder  # noqa: PLC0415

    pcms = []
    for seed in range(N_SEEDS):
        clean = synth_encoder.render_tones(tones, base_freq_hz=SYNTH_TRUE_FREQ_HZ,
                                            dt_s=SYNTH_DT_S, snr_db=SNR_DB, seed=seed,
                                            sample_rate_hz=int(SAMPLE_RATE_HZ))
        pcm = np.asarray(clean, dtype=np.float64)
        assert pcm.shape == (BUFFER_SAMPLES,), pcm.shape
        pcm = P.normalise_rms(pcm, P.PROD_TARGET_RMS)
        pcms.append(pcm)
    return pcms


def main() -> int:
    from synth import encoder as synth_encoder  # noqa: PLC0415

    print("=" * 78)
    print("N4 mandatory sign unit test (spec Sec.4.4, reused verbatim from N3)")
    print("=" * 78)
    t0 = time.time()

    tones = synth_encoder.message_to_tones(SYNTH_MESSAGE)
    true_bits = true_bits_from_tones(tones)
    anchor_dt = SYNTH_DT_S + SYMBOL_PERIOD_S  # real-candidate time-origin convention

    failures = 0
    curves_by_variant: "dict[str, dict[float, list[float]]]" = {v: {} for v in CHECK_VARIANTS}

    for df_inject in DF_INJECT_VALUES:
        wrong_anchor_freq_hz = SYNTH_TRUE_FREQ_HZ + df_inject
        pcms = _render_seeds(tones)

        per_variant_curve = {v: [] for v in CHECK_VARIANTS}
        for df in DF_SWEEP_HZ:
            per_seed = {v: [] for v in CHECK_VARIANTS}
            for pcm in pcms:
                variants = extract_variants_ext(pcm, wrong_anchor_freq_hz, anchor_dt, df_hz=df)
                for v in CHECK_VARIANTS:
                    per_seed[v].append(hard_decision_ber(list(variants[v]), true_bits))
            for v in CHECK_VARIANTS:
                per_variant_curve[v].append(float(np.median(per_seed[v])))

        for v in CHECK_VARIANTS:
            curves_by_variant[v][df_inject] = per_variant_curve[v]

    for variant in CHECK_VARIANTS:
        print("\n-- variant %s --" % variant)
        signs_seen = set()
        for df_inject in DF_INJECT_VALUES:
            curve = curves_by_variant[variant][df_inject]
            df_star = argmin_curve(list(DF_SWEEP_HZ), curve)
            expected = -df_inject
            err = abs(df_star - expected)
            ok = err <= TOLERANCE_HZ + 1e-9
            same_sign = (df_star == 0.0) or (expected == 0.0) or \
                ((df_star > 0) == (expected > 0))
            print("  df_inject=%+.2f -> argmin df*=%+.3f (want %+.2f, tol %.3f) "
                  "min_median_BER=%.2f%% [%s]"
                  % (df_inject, df_star, expected, TOLERANCE_HZ, min(curve) * 100,
                     "PASS" if ok and same_sign else "FAIL"))
            if not (ok and same_sign):
                failures += 1
            signs_seen.add(df_inject > 0)
        if len(signs_seen) < 2:
            print("  INTERNAL ERROR: DF_INJECT_VALUES did not exercise both signs.")
            failures += 1

    print("\n(%.1fs elapsed)" % (time.time() - t0))
    if failures:
        print("RESULT: FAIL -- %d check(s) failed. DO NOT ARM the real harness." % failures)
        return 1
    print("RESULT: PASS -- the sweep's minimum tracks a known frequency error with the "
          "correct sign, at >=2 opposite-sign injected offsets, for both order 1 and "
          "cumulative order 3, on N4's own two-resolution grid. Real harness may be armed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
