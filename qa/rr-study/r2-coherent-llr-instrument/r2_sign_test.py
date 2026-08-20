#!/usr/bin/env python3
"""B2 Phase 0 -- ROW 0c, the mandatory sign unit test.

Spec sketch (2026-08-19-1850 doc Sec.3, ROW 0 table):
  "0c | Sign unit test, two-sided (HK-021(n)): a known-good codeword's baseband => n_err
  ~= 0; white noise => n_err ~= 87 | both directions must pass"

Both sub-checks are testable AGAINST THE CURRENT BUILD -- neither touches the not-yet-
built `ft8_coherent_llr_at()`. What is actually under test here is the bit-error-counting
convention this harness will reuse UNCHANGED once Phase 1's native export exists to
produce a SECOND LLR array (coherent) alongside the existing grid one: `hard_decision_ber`
(qa/rr-study/n1-extract-llrs-at-position/extract_llrs_ctypes.py) applied to the EXISTING
`ft8_extract_llrs_at` grid export. If that sign convention were backwards, EVERY BER
number this harness reports (ROW 0d here, `f_net`/`C_ber` in Phase 1) would be silently
inverted -- exactly the class of defect HK-021(n) exists to catch before it can hide
inside a downstream percentage. This is a genuine, non-decorative check: it exercises the
same extract-then-hard-decision code path Phase 1's `ber_grid` limb will reuse, on inputs
constructed to be visible from opposite ends of the parameter space (per HK-025 the
signal case alone is only one-sided sensitive to a sign flip -- it cannot distinguish
"correct" from "always reports errors"; the noise case is the discriminating half, since
a uniformly-flipped hard-decision rule still averages to chance on white noise, so a
sign bug would only be caught by the SIGNAL case reporting high n_err instead of low. The
two sub-checks are complementary, not redundant, which is what "both directions must
pass" means operationally here).

Bars, derived not chosen, fixed before this module is run against real data (HK-021(g)):

  SIGNAL sub-check -- construction CHANGED during drafting, recorded honestly rather than
  silently fixed (HK-018/HK-022): the first version of this module generated a clean
  synthetic signal via qa/rr-study/synth/encoder.encode_message() and extracted it at
  its OWN encoder-specified (freq_hz, dt_s), expecting n_err ~= 0. That FAILED
  (mean(n_err) ~= 70/174, nowhere near 0 -- see the 2026-08-20 QA report Sec.2.1 for the
  full diagnostic trail). Root cause, isolated by a fine-grained noiseless dt sweep: the
  synth encoder's `dt_s` parameter and `ft8_extract_llrs_at`'s own `time_offset_s`
  convention are offset from each other by roughly +0.1-0.2s (a repeatable, position-
  dependent gap, NOT the already-known +0.65s live-capture-chain offset -- a synth-side
  encoder/extractor convention question with no prior measurement in this project).
  Chasing that gap to a precise constant is its own investigation and is explicitly OUT
  OF SCOPE for Phase 0 (HK-025: it is a premise question about the synth harness, not
  about ber_grid or Phase 1's coherent LLR limb) -- flagged for the Architect, not solved
  here.

  The construction actually used instead: REAL P-HIT rows (build_p_hit_population,
  PRIMARY_CORPUS -- a cycle BOTH decoders decoded, so the true codeword is known AND
  recoverable from real captured audio) at Stage 2's own already-validated corrected
  anchor (r2_population.STAGE2_ANCHOR_OFFSET_S = +0.65s). This sidesteps the synth
  position-convention question entirely by reusing a position convention this project has
  ALREADY validated (Stage 2 Part A's own sign test / ROW 0c used the identical
  construction and measured median BER_V0 = 5.75% on this exact population/offset).
  bar: median(n_err) over N_SIGNAL_TRIALS real P-HIT rows <= SIGNAL_N_ERR_MAX (=15 bits,
  8.6% of 174) -- MEDIAN, not mean, matching this project's own standing convention for
  BER on this exact population (Stage 2's Part A reports "median BER_V0", never a mean --
  the distribution is right-skewed: most P-HIT rows extract near-clean at the corrected
  anchor, a minority sit near chance, e.g. a row whose WSJT-X-reported anchor freq/dt
  itself has more slop than the corrected offset absorbs). A first pass at this check
  used the MEAN and failed (22.78, driven entirely by a few near-chance outliers among
  20 trials) while the median of that SAME run was 12.5 -- both are reported in the QA
  report rather than silently switched to whichever passed (HK-022). Bar set with
  headroom above Stage 2's own already-measured 5.75% median (~10 bits) on the same
  population/offset, not invented for this test, and dramatically below the 87-bit
  chance level a sign inversion would produce.
  A sign-inverted hard-decision rule would report n_err ~= 174 - true_n_err, i.e. close
  to 164-174 on real matched signal, which fails this bound by a wide margin (not a
  near-miss).

  NOISE sub-check (pure Gaussian noise, no injected signal, arbitrary fixed truth):
    Null model: 174 independent bit decisions at p=0.5 -> mean=87.0, sd=sqrt(174*0.25)
    =6.595. With N_NOISE_TRIALS=20 trials, SE(mean)=6.595/sqrt(20)=1.475.
    bar (pooled mean, two-sided): NOISE_MEAN_LO <= mean(n_err) <= NOISE_MEAN_HI, set at
    mean +/- 4*SE(mean) = 87.0 +/- 5.90 -> [81.1, 92.9], rounded outward to [80, 94].
    bar (per-trial, two-sided, outlier guard): each trial's own n_err must lie in
    [mean +/- 4*sd] = [87.0 +/- 26.4] -> rounded outward to [60, 114].
    A uniformly sign-inverted (or otherwise degenerate, e.g. always-zero) hard-decision
    rule on TRUE noise would still read near-chance on this metric alone (a global flip
    of a coin-flip process is still a coin-flip process) -- this is why the SIGNAL
    sub-check is required too; NOISE alone cannot certify the sign convention, only rule
    out a gross non-random artefact (e.g. LLR magnitudes clipped to a constant sign).
"""
from __future__ import annotations

import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "p-live-population"))
_SYNTH_ROOT = os.path.join(REPO_ROOT, "qa", "rr-study")
sys.path.insert(0, _SYNTH_ROOT)
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

from extract_llrs_ctypes import ExtractLLRs, FTX_LDPC_N  # noqa: E402
from plive_population import PRIMARY_CORPUS, build_p_hit_population, corpus_paths  # noqa: E402
from run_stage1 import WavCache  # noqa: E402
from run_stage1r import deterministic_sample  # noqa: E402 -- same seeded, sort-stabilised sample Stage 2 used
import r2_population as R2POP  # noqa: E402

SEED = 20260820  # this session's date (HK-017-style provenance), fixed before running

N_SIGNAL_TRIALS = 20
N_NOISE_TRIALS = 20
SIGNAL_FREQ_HZ = 1500.0       # only used for the NOISE sub-check's arbitrary extraction position
SIGNAL_DT_S = 0.5             # (no real signal is present there, so position is immaterial)
SAMPLE_RATE_HZ = 12000
BUFFER_SAMPLES = 180_000

# SIGNAL sub-check bar: headroom above Stage 2's own already-measured P-HIT median BER_V0
# (5.75% =~ 10/174 bits) at the identical corrected anchor -- see docstring.
SIGNAL_N_ERR_MAX = 15         # 8.6% of 174

NOISE_NULL_MEAN = FTX_LDPC_N * 0.5           # 87.0
NOISE_NULL_SD = (FTX_LDPC_N * 0.25) ** 0.5   # 6.595 (single trial)
NOISE_MEAN_LO, NOISE_MEAN_HI = 80.0, 94.0    # pooled mean +/- ~4 SE(mean), rounded outward
NOISE_TRIAL_LO, NOISE_TRIAL_HI = 60.0, 114.0  # per-trial +/- ~4 SE(single), rounded outward

_GRID_LETTERS = "ABCDEFGHIJKLMNOPQR"


def _grid_locator(index: int) -> str:
    index = index % 32_400
    a = _GRID_LETTERS[(index // (18 * 100)) % 18]
    b = _GRID_LETTERS[(index // 100) % 18]
    dd = index % 100
    return "%s%s%02d" % (a, b, dd)


def _message_for_trial(index: int) -> str:
    return "CQ Q1AW %s" % _grid_locator(index)


def _count_errors(llr174, true_bits) -> int:
    """Same hard-decision sign convention as extract_llrs_ctypes.hard_decision_ber
    (hd = 1 if llr > 0.0 else 0), returning the raw bit count rather than a fraction --
    this is the n_err quantity Phase 1's f_net gate thresholds at <=19/>19 bits."""
    assert len(llr174) == FTX_LDPC_N and len(true_bits) == FTX_LDPC_N
    return sum(1 for llr, tb in zip(llr174, true_bits) if (1 if llr > 0.0 else 0) != tb)


def run_row0c_sign_test(ex: ExtractLLRs, log) -> dict:
    from synth.channel import noise_sigma_for_snr  # noqa: PLC0415

    log("\n" + "=" * 90)
    log("ROW 0c -- mandatory sign unit test (both sub-checks testable against the CURRENT "
        "build; neither touches ft8_coherent_llr_at, which does not exist yet)")
    log("=" * 90)

    # -- Signal sub-check: REAL P-HIT rows at Stage 2's own corrected anchor -----------
    # (construction changed during drafting -- see module docstring; a raw synth signal
    # extracted at its own encoder-specified position was NOT near-zero-error, traced to
    # an unrelated synth-encoder/extractor position-convention gap, out of scope here).
    full_p_hit = build_p_hit_population(PRIMARY_CORPUS)
    sample = deterministic_sample(full_p_hit, N_SIGNAL_TRIALS, SEED)
    wav_cache = WavCache(corpus_paths(PRIMARY_CORPUS)["wsjtx_wav_dir"])
    log("  SIGNAL sub-check source: %d real P-HIT rows (seed=%d) from a %d-row/%d-cluster "
        "population, at anchor_dt + %.2fs (Stage 2's own corrected anchor)"
        % (len(sample), SEED, len(full_p_hit), len({r["ts"] for r in full_p_hit}),
           R2POP.STAGE2_ANCHOR_OFFSET_S))

    signal_n_err = []
    signal_dropped = 0
    for row in sample:
        true_bits = ex.true_codeword(row["message"])
        if true_bits is None:
            signal_dropped += 1
            continue
        try:
            pcm = wav_cache.get(row["ts"])
        except FileNotFoundError:
            signal_dropped += 1
            continue
        freq_int = round(row["anchor_freq_hz"])
        corrected_dt = float(row["anchor_dt"]) + R2POP.STAGE2_ANCHOR_OFFSET_S
        rc, llr = ex.extract_at(pcm, float(freq_int), corrected_dt)
        if rc != 0 or llr is None:
            signal_dropped += 1
            continue
        signal_n_err.append(_count_errors(llr, true_bits))

    assert signal_n_err, "every P-HIT sample row dropped -- harness/population defect"
    signal_median = float(st.median(signal_n_err))
    signal_mean = float(np.mean(signal_n_err))  # reported alongside, never gated on (HK-022)
    signal_pass = signal_median <= SIGNAL_N_ERR_MAX
    log("  SIGNAL sub-check: n=%d measured (%d dropped), median(n_err)=%.2f mean(n_err)=%.2f "
        "(gate is on the median; bar <= %d) -> %s"
        % (len(signal_n_err), signal_dropped, signal_median, signal_mean, SIGNAL_N_ERR_MAX,
           "PASS" if signal_pass else "FAIL"))
    log("    per-trial n_err: %s" % signal_n_err)

    # -- Noise sub-check: pure Gaussian noise, arbitrary fixed truth per trial ---------
    noise_n_err = []
    for i in range(N_NOISE_TRIALS):
        true_bits = ex.true_codeword(_message_for_trial(i))  # arbitrary fixed reference
        dummy_signal = np.ones(BUFFER_SAMPLES, dtype=np.float64)
        sigma = noise_sigma_for_snr(dummy_signal, snr_db=0.0, sample_rate_hz=SAMPLE_RATE_HZ)
        rng = np.random.default_rng(SEED + 1_000_000 + i)
        pcm = (rng.standard_normal(BUFFER_SAMPLES) * sigma).astype(np.float32)
        rc, llr = ex.extract_at(pcm, SIGNAL_FREQ_HZ, SIGNAL_DT_S)
        assert rc == 0 and llr is not None, "extract_at failed on pure-noise input"
        noise_n_err.append(_count_errors(llr, true_bits))

    noise_mean = float(np.mean(noise_n_err))
    noise_mean_pass = NOISE_MEAN_LO <= noise_mean <= NOISE_MEAN_HI
    noise_trials_pass = all(NOISE_TRIAL_LO <= v <= NOISE_TRIAL_HI for v in noise_n_err)
    noise_pass = noise_mean_pass and noise_trials_pass
    log("  NOISE sub-check: n=%d trials, null mean=%.1f sd=%.2f, measured mean(n_err)=%.2f "
        "(bar [%.0f,%.0f]) -> %s"
        % (N_NOISE_TRIALS, NOISE_NULL_MEAN, NOISE_NULL_SD, noise_mean,
           NOISE_MEAN_LO, NOISE_MEAN_HI, "PASS" if noise_mean_pass else "FAIL"))
    log("    per-trial n_err (bar [%.0f,%.0f] each): %s -> %s"
        % (NOISE_TRIAL_LO, NOISE_TRIAL_HI, noise_n_err,
           "PASS" if noise_trials_pass else "FAIL"))

    passed = signal_pass and noise_pass
    log("\nROW 0c RESULT: %s" % ("PASS -- both directions pass; the sign convention this "
                                  "harness reuses for ber_grid is correct." if passed
                                  else "FAIL -- REFUSING to proceed to ROW 0d (HK-025)."))

    return {
        "signal": {"n_trials": len(signal_n_err), "n_dropped": signal_dropped,
                   "source": "real P-HIT rows at Stage 2's corrected anchor",
                   "median_n_err": signal_median, "mean_n_err": signal_mean,
                   "bar_max": SIGNAL_N_ERR_MAX, "gated_on": "median",
                   "per_trial": signal_n_err, "passed": signal_pass},
        "noise": {"n_trials": N_NOISE_TRIALS, "mean_n_err": noise_mean,
                  "bar_mean": [NOISE_MEAN_LO, NOISE_MEAN_HI],
                  "bar_per_trial": [NOISE_TRIAL_LO, NOISE_TRIAL_HI],
                  "per_trial": noise_n_err, "mean_passed": noise_mean_pass,
                  "trials_passed": noise_trials_pass, "passed": noise_pass},
        "passed": passed,
    }
