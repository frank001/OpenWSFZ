#!/usr/bin/env python3
"""N3 -- mandatory sign unit test (spec Sec.4.4: "Inject a known df_inject into a
synthetic buffer, extract across the sweep, and assert the curve's minimum lands at
df = -df_inject ... at >=2 distinct injected values of opposite sign. The harness
refuses to arm without it.").

Sign convention this proves: a REAL row's `anchor_freq_hz` is itself the (possibly
wrong) reference the sweep's df_hz is added to (coherent_extract.extract_variants's own
`carrier = anchor_freq_hz + df_hz`). So "the anchor carries a +df_inject error" is
modelled here by rendering the TRUE signal at a fixed frequency and then calling
extract_variants_ext with anchor_freq_hz DELIBERATELY OFFSET by +df_inject from that
truth -- exactly mirroring a real row whose recorded anchor sits df_inject away from
the true carrier. The sweep's best-fit correction must then be df_hz = -df_inject (that
is what brings anchor_freq_hz + df_hz back to the true carrier). Getting this backwards
(minimum at +df_inject) is precisely the class of bug the N2 ruling's Sec.1 anchor-
rounding defect and this file's own existence are both about -- a sign flip here would
silently invert every W_n and df*_n the real harness reports.

CALIBRATION NOTE, empirically derived before this test's tolerance was fixed (not
guessed): a NOISELESS synthetic buffer saturates hard-decision BER at 0.0% over several
Hz around the true offset (no dynamic range at all -- the test could not have failed on
a sign flip, which would defeat its own purpose). A single noisy realisation is too
noisy to pin the minimum within one grid step. The fix, mirroring the real gate's own
method (median BER over many independent observations, not one): render N_SEEDS
independent noise realisations of the SAME message at a fixed SNR chosen so the median-
BER curve has genuine dynamic range, and read df* off the MEDIAN curve, exactly as
run_n3.py reads df* off its 171-row median curve. At SNR_DB=-18, N_SEEDS=48, this
recovers an injected offset with the CENTROID tie-break (n3_stats.argmin_curve) to
within 0.125 Hz (half a grid step) for V1 and V3_cum alike, at four independent offsets
of both signs -- comfortably inside the spec's one-grid-step (0.25 Hz) tolerance.

No DLL, no WAV corpus -- pure synth + coherent_extract_ext. ~2-3 min (48 realisations x
33 df points x 4 offsets, one extract_variants_ext call per (realisation, df) covering
ALL five curves at once -- the same "one call yields every curve" economy Sec.4.2 gates
the real harness's own cost on).

run_n3.py calls this module's main() directly and refuses to run the real harness
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
from n3_stats import DF_GRID_STEP_HZ, DF_SWEEP_HZ, argmin_curve  # noqa: E402

SYNTH_MESSAGE = "CQ Q1SG JO22"    # NFR-021: synthetic Q-prefix callsign, distinct from
                                  # N2's ROW 0a message so the two tests never share a
                                  # cached buffer by accident.
SYNTH_TRUE_FREQ_HZ = 1200.0
SYNTH_DT_S = 0.48                 # exact multiple of 0.08s (native lattice step)

DF_INJECT_VALUES = (-1.75, -0.50, 0.50, 1.25)   # >=2 opposite-sign values (spec minimum
                                                  # is 2; four here, two per sign, all
                                                  # exact multiples of the 0.25 Hz grid
                                                  # step so the expected minimum lands
                                                  # exactly on a sampled grid point)
TOLERANCE_HZ = DF_GRID_STEP_HZ    # spec: "within one grid step"
SNR_DB = -18.0                    # calibration note above
N_SEEDS = 48
CHECK_VARIANTS = ("V1", "V3_cum")


def _render_seeds(tones, true_bits_ignored=None):
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
    print("N3 mandatory sign unit test (spec Sec.4.4)")
    print("=" * 78)
    t0 = time.time()

    tones = synth_encoder.message_to_tones(SYNTH_MESSAGE)
    true_bits = true_bits_from_tones(tones)
    anchor_dt = SYNTH_DT_S + SYMBOL_PERIOD_S  # real-candidate time-origin convention

    failures = 0
    curves_by_variant: dict[str, dict[float, list[float]]] = {v: {} for v in CHECK_VARIANTS}

    for df_inject in DF_INJECT_VALUES:
        wrong_anchor_freq_hz = SYNTH_TRUE_FREQ_HZ + df_inject
        pcms = _render_seeds(tones)

        # ONE extract_variants_ext call per (realisation, df) covers every curve --
        # read out only the variants this test checks (Sec.4.2's own cost economy).
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
            print("  df_inject=%+.2f -> argmin df*=%+.3f (want %+.2f, tol %.2f) "
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
          "cumulative order 3. Real harness may be armed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
