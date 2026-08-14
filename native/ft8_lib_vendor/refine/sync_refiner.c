/*
 * sync_refiner.c -- per-candidate coherent sync-refinement stage.
 *
 * r1-sync-refiner-instrument-validation (FT8_SHIM_VERSION 20260040):
 *
 * OpenWSFZ-ORIGINAL code, not part of the byte-identical-to-upstream ft8_lib
 * vendor tree (design.md D7) -- deliberately placed in this sibling `refine/`
 * directory (design.md Open Question 1) so R0's provenance guarantee for
 * common/, fft/ and ft8/ stays untouched.
 *
 * PROVENANCE / CLEAN-ROOM NOTE: this file was written directly from the
 * method description in this change's spec.md / design.md (downconvert to
 * complex baseband with phase retained -> coherent Costas correlation,
 * summing complex values across the three 7-symbol sync arrays and taking
 * the magnitude of the sum last -> two-dimensional coarse/fine search).
 * No WSJT-X source (ft8_downsample / sync8d / ft8b) was available in or
 * consulted during this session -- this implementation is clean-room by
 * construction, which satisfies the Captain's binding licence ruling
 * (2026-08-11: WSJT-X may be read for method, never copied) more strongly
 * than the ruling requires. The downconversion/correlation mathematics below
 * are standard DSP technique (coherent matched-filter demodulation), derived
 * independently.
 *
 * D2 (design.md): correlation sums COMPLEX values across all 21 Costas
 * symbols first, and takes the magnitude of that sum LAST -- explicitly not
 * the ft8_decode_multi_symbols() shape elsewhere in this codebase (dead code
 * that sums dB magnitudes, i.e. magnitude-then-sum, which would defeat the
 * entire point of retaining phase here).
 *
 * Diagnostic-only: this file's only entry point, ft8_refine_candidate(), has
 * no call site anywhere in decode.c or ft8_shim.c's ft8_decode_all -- it is
 * reachable only from the validation harness and test code (task 1.6).
 */

#include "ft8_shim.h"       /* FT8_EXPECTED_SAMPLES, ft8_refine_candidate() prototype */
#include <ft8/constants.h>  /* kFT8_Costas_pattern */

#include <math.h>
#include <stdlib.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/* ── Fixed protocol constants (mirrors ft8/constants.h; not redefined there) ── */
#define REFINE_SAMPLE_RATE_HZ  12000.0f
#define REFINE_TONE_SPACING_HZ 6.25f     /* FT8 tone spacing, Hz */
#define REFINE_SYMBOL_PERIOD_S 0.160f    /* FT8_SYMBOL_PERIOD */

/* FT8_EXPECTED_SAMPLES is ft8_shim.c-internal (not re-exported via ft8_shim.h), so it
 * is redefined here under a distinct name -- same value (15 s x 12 kHz), same contract
 * as ft8_decode_all's pcm_len check. */
#define REFINE_EXPECTED_SAMPLES 180000

/* Stage 1/2 working rate: 12000 / 60 = 200 Hz (spec: "on the order of 200 Hz"). */
#define REFINE_DECIM_COARSE   60
#define REFINE_RATE_COARSE_HZ (REFINE_SAMPLE_RATE_HZ / (float)REFINE_DECIM_COARSE)

/* Stage 3c (fine time, re-derived baseband) working rate: 12000 / 6 = 2000 Hz. */
#define REFINE_DECIM_FINE     6
#define REFINE_RATE_FINE_HZ   (REFINE_SAMPLE_RATE_HZ / (float)REFINE_DECIM_FINE)

#define REFINE_LP_TAPS_COARSE      121
#define REFINE_LP_CUTOFF_COARSE_HZ 90.0f   /* > 8*6.25=50 Hz tone span, < 100 Hz Nyquist@200Hz */

#define REFINE_LP_TAPS_FINE        61
#define REFINE_LP_CUTOFF_FINE_HZ   900.0f  /* well under 1000 Hz Nyquist@2000Hz */

/* Search ranges -- design.md D3: WSJT-X's published ranges are a *starting
 * point* tunable to hit AC-1, not a hard requirement. The coarse time range
 * is deliberately widened past WSJT-X's +/-4-sample figure so the search
 * covers this change's own pre-registered time-offset grid
 * (+/-0.039 s, spec Requirement "Validation population...") with margin. */
#define REFINE_COARSE_TIME_HALF_SAMPLES 12   /* +/-12 @ 200 Hz = +/-60 ms */
#define REFINE_FREQ_HALF_HZ    2.5f
#define REFINE_FREQ_STEP_HZ    0.5f
#define REFINE_FINE_TIME_HALF_MS 10.0f
#define REFINE_FINE_TIME_STEP_MS 0.5f

typedef struct { float re, im; } refine_cplx_t;

/* Hann-windowed-sinc lowpass FIR, unit DC gain. Standard filter design,
 * derived independently (no external source consulted). */
static void design_lowpass_hann(float* taps, int ntaps, float cutoff_hz, float fs_hz)
{
    int   mid = ntaps / 2;
    float fc  = cutoff_hz / fs_hz; /* normalised cutoff, cycles/sample */
    float sum = 0.0f;
    for (int i = 0; i < ntaps; i++)
    {
        int   k    = i - mid;
        float sinc = (k == 0)
                   ? (2.0f * fc)
                   : sinf(2.0f * (float)M_PI * fc * (float)k) / ((float)M_PI * (float)k);
        float w    = 0.5f - 0.5f * cosf(2.0f * (float)M_PI * (float)i / (float)(ntaps - 1));
        taps[i] = sinc * w;
        sum += taps[i];
    }
    if (sum != 0.0f)
        for (int i = 0; i < ntaps; i++) taps[i] /= sum;
}

/*
 * downconvert_decimate -- mix `pcm` (n samples @ fs_in Hz) down by `carrier_hz`
 * (baseband = pcm * exp(-j*2*pi*carrier_hz*t)), apply the FIR lowpass `taps`,
 * and decimate by `decim`, all fused into one pass per output sample (a
 * direct-form polyphase-equivalent evaluation -- no full-rate intermediate
 * array is materialised).
 *
 * Writes floor(n/decim) complex samples to out_re/out_im. Zero-padded at the
 * buffer edges. Returns the number of output samples written.
 */
static int downconvert_decimate(
    const float* pcm, int n, float fs_in,
    float carrier_hz,
    const float* taps, int ntaps,
    int decim,
    float* out_re, float* out_im)
{
    int   half   = ntaps / 2;
    int   n_out  = n / decim;
    float w      = 2.0f * (float)M_PI * carrier_hz / fs_in; /* rad/sample */

    for (int m = 0; m < n_out; m++)
    {
        int   center = m * decim;
        float acc_re = 0.0f, acc_im = 0.0f;
        for (int t = 0; t < ntaps; t++)
        {
            int idx = center + (t - half);
            if (idx < 0 || idx >= n) continue;
            float s     = pcm[idx];
            float phase = w * (float)idx;
            float c     = cosf(phase);
            float sgn   = sinf(phase);
            /* baseband sample = pcm[idx] * exp(-j*phase) */
            acc_re += taps[t] * s * c;
            acc_im += taps[t] * (-s * sgn);
        }
        out_re[m] = acc_re;
        out_im[m] = acc_im;
    }
    return n_out;
}

/*
 * costas_coherent_sum -- coherent correlation of the complex baseband against
 * the three Costas 7x7 sync arrays (pattern kFT8_Costas_pattern at symbol
 * offsets 0, 36, 72), at a given time origin and additional frequency trial.
 *
 * DESIGN CORRECTIONS discovered during implementation (empirically diagnosed via
 * REFINE_DEBUG instrumentation -- envelope dumps, per-block magnitude dumps, and
 * cross-checks against an independent Python re-implementation and idealised
 * noiseless toy signals -- not asserted from re-reading the code twice, per
 * design.md's own sign-error mitigation guidance applied here to two sibling
 * defect classes):
 *
 * (1) Cross-block combining must be non-coherent (magnitude-domain), not
 *     complex-domain. FT8 is continuous-phase FSK (CPFSK): the transmitter's
 *     phase at the start of sync block 1 (symbol 36) and block 2 (symbol 72)
 *     carries the accumulated phase contribution of the ~29 DATA symbols
 *     between each pair of sync blocks -- symbols whose tones are message-
 *     dependent and UNKNOWN to this diagnostic stage (decoding has not
 *     happened yet). Complex-summing all three blocks introduces an
 *     arbitrary, message-dependent relative phase rotation between them.
 *
 * (2) WITHIN one block, the reference must itself be a properly
 *     phase-INTEGRATED replica of the known 7-symbol Costas tone sequence --
 *     NOT seven independent "ref_hz * absolute_sample_index" terms. This is
 *     the defect that actually dominated (found only after (1) alone barely
 *     changed the measured peak location): even with all 7 tones known
 *     in advance, a per-symbol reference phase of `2*pi*ref_hz*idx/fs2`
 *     implicitly assumes tone(j) had been running since idx=0, when the REAL
 *     (CPFSK) signal's phase at symbol j is offset by the accumulated phase
 *     contribution of tones(0..j-1) -- a KNOWN, computable quantity for
 *     Costas symbols, but one the old per-symbol-independent formula never
 *     computed. Verified with an idealised, noiseless, hand-built 7-symbol
 *     CPFSK toy signal (bypassing downconvert_decimate, the Python synth, and
 *     GFSK shaping entirely): the old formula peaked several samples away
 *     from the true (and only) alignment; a running phase accumulator that
 *     integrates each symbol's own `2*pi*ref_hz/fs2` step CONTINUOUSLY across
 *     the block (matching the same cumsum-inclusive convention
 *     qa/rr-study/synth/modulator.py's own phase integration uses) peaks
 *     exactly at the true alignment, symmetric to the sample.
 *
 * Net effect: coherent (complex) integration is retained WITHIN each 7-symbol
 * block using a true continuous-phase reference (still up to ~7x coherent
 * gain per block, genuinely exploiting phase -- unlike the fully-incoherent
 * per-symbol-magnitude ft8_decode_multi_symbols() dead code this refiner
 * replaces); the three blocks' own magnitudes are combined non-coherently
 * across blocks per (1). This is the standard "block-coherent, cross-block-
 * noncoherent" combining strategy for continuous-phase modulation with
 * unknown intervening symbols, and is squarely within design.md D3's latitude
 * ("What is fixed is the *method* ... not its numeric constants") -- the
 * method (coherent, phase-retaining correlation) is preserved; only which
 * SCOPE stays complex (per-block, with true phase integration) changed once
 * the defects were found.
 */
static float costas_coherent_sum(
    const float* bb_re, const float* bb_im, int n_bb, float fs2,
    float origin_sample_f, float delta_hz, float sps_f)
{
    static const int block_start[3] = { 0, 36, 72 };
    float total_mag = 0.0f;
    float phase_step_per_hz = 2.0f * (float)M_PI / fs2; /* rad/sample per Hz of ref_hz */

    for (int b = 0; b < 3; b++)
    {
        /* Coherent (complex) sum WITHIN this one block, using a running phase
         * accumulator that tracks the KNOWN Costas tone sequence's true
         * continuous phase (design correction (2) above) -- valid because all
         * 7 symbols here are known Costas tones with no unknown data between
         * them, so their relative phase contribution IS fully computable. */
        refine_cplx_t block_sum  = { 0.0f, 0.0f };
        float         ref_phase  = 0.0f; /* resets per block: unknown absolute
                                           * transmitter phase is a free constant
                                           * that magnitude-taking absorbs. */

        for (int j = 0; j < 7; j++)
        {
            int   p        = block_start[b] + j;
            int   tone     = (int)kFT8_Costas_pattern[j];
            float ref_hz   = (float)tone * REFINE_TONE_SPACING_HZ + delta_hz;
            float phase_step = ref_hz * phase_step_per_hz;
            float sym_start_f = origin_sample_f + (float)p * sps_f;

            int i0 = (int)floorf(sym_start_f);
            int i1 = (int)floorf(sym_start_f + sps_f);

            for (int idx = i0; idx < i1; idx++)
            {
                /* Increment BEFORE use: matches modulator.py's cumsum-inclusive
                 * convention (cumsum[0] is the first symbol's own contribution,
                 * not 0) -- see design correction (2). Advances even when idx is
                 * out of bounds so phase continuity across the whole block is
                 * unaffected by boundary clipping. */
                ref_phase += phase_step;
                if (idx < 0 || idx >= n_bb) continue;
                float rc = cosf(ref_phase);
                float rs = sinf(ref_phase);
                /* correlate = baseband * conj(exp(j*ref_phase)) */
                float re = bb_re[idx] * rc + bb_im[idx] * rs;
                float im = bb_im[idx] * rc - bb_re[idx] * rs;
                block_sum.re += re;
                block_sum.im += im;
            }
        }

        /* Cross-block combining: magnitude-domain (non-coherent) -- design
         * correction (1) above. */
        float bmag = sqrtf(block_sum.re * block_sum.re + block_sum.im * block_sum.im);
        total_mag += bmag;
    }
    return total_mag;
}

/*
 * ft8_refine_candidate -- see ft8_shim.h for the full ABI contract.
 *
 * Three-stage search (spec: "coarse time -> frequency -> fine time"):
 *   A. Coarse TIME search at the input coarse frequency (delta_hz = 0),
 *      +/-REFINE_COARSE_TIME_HALF_SAMPLES @ 200 Hz.
 *   B. FREQUENCY search at the coarse-time estimate from (A),
 *      +/-REFINE_FREQ_HALF_HZ in REFINE_FREQ_STEP_HZ steps.
 *   C. Fine TIME search: baseband is RE-DERIVED at the refined carrier
 *      (coarse_freq_hz + best_df) at a higher working rate (2000 Hz),
 *      +/-REFINE_FINE_TIME_HALF_MS in REFINE_FINE_TIME_STEP_MS steps.
 *
 * Returns 0 on success, -1 on invalid input, -2 on allocation failure.
 */
int ft8_refine_candidate(
    const float* pcm, int pcm_len,
    int coarse_freq_hz, float coarse_time_offset_s,
    float* out_delta_freq_hz,
    float* out_delta_time_s,
    float* out_sync_score)
{
    if (pcm_len != REFINE_EXPECTED_SAMPLES) return -1;
    if (!pcm || !out_delta_freq_hz || !out_delta_time_s || !out_sync_score) return -1;

    /* ── Stage 1: downconvert + decimate to ~200 Hz working rate ─────────── */
    int n_bb1 = pcm_len / REFINE_DECIM_COARSE;
    float* bb1_re = (float*)malloc(sizeof(float) * (size_t)n_bb1);
    float* bb1_im = (float*)malloc(sizeof(float) * (size_t)n_bb1);
    if (!bb1_re || !bb1_im) { free(bb1_re); free(bb1_im); return -2; }

    float taps_coarse[REFINE_LP_TAPS_COARSE];
    design_lowpass_hann(taps_coarse, REFINE_LP_TAPS_COARSE,
                         REFINE_LP_CUTOFF_COARSE_HZ, REFINE_SAMPLE_RATE_HZ);

    downconvert_decimate(pcm, pcm_len, REFINE_SAMPLE_RATE_HZ,
                          (float)coarse_freq_hz, taps_coarse, REFINE_LP_TAPS_COARSE,
                          REFINE_DECIM_COARSE, bb1_re, bb1_im);

    float fs1   = REFINE_RATE_COARSE_HZ;
    float sps1  = fs1 * REFINE_SYMBOL_PERIOD_S; /* 32 samples/symbol @ 200 Hz */
    float base_origin1 = coarse_time_offset_s * fs1;

    /* ── Stage A+B: JOINT coarse TIME x FREQUENCY search ──────────────────── */
    /*
     * DESIGN CORRECTION (found via the same empirical diagnosis as
     * costas_coherent_sum's corrections above, once those fixes still left
     * AC-1-scale RMS errors for true offsets beyond roughly +/-0.7 Hz): a
     * SEQUENTIAL search -- coarse time at delta_hz=0 fixed, THEN frequency at
     * that time fixed -- implicitly assumes the true frequency offset is near
     * zero while estimating time. When the true offset is large enough
     * (empirically, confirmed from the validation population itself: accurate
     * to <=1 ms / <=0.1 Hz for |true df| <= 0.4 Hz, but RMS(df) jumping to
     * several Hz for |true df| = 0.8 Hz), that assumption is false, Stage A
     * locks onto a suboptimal time origin using badly-mismatched-frequency
     * scoring, and Stage B's subsequent frequency search -- now anchored to a
     * wrong time -- cannot recover. Spec text describes "coarse time ->
     * frequency -> fine time" as the two-dimensional search's stage order;
     * design.md D3 grants the Developer session latitude on numeric/search
     * parameters as long as the method (coherent, phase-retaining Costas
     * correlation, three-stage coarse/fine search culminating in a
     * frequency-refined fine-time pass) is preserved -- which a JOINT 2-D
     * coarse grid search still satisfies (still "coarse time -> frequency",
     * just evaluated jointly rather than sequentially, before the fine-time
     * stage) while removing the false independence assumption. The grid is
     * small (25 time steps x 11 freq steps = 275 evaluations) and cheap.
     */
    int   best_dt_samp  = 0;
    float best_df        = 0.0f;
    float best_score_ab  = -1.0f;
    int   n_freq_steps    = (int)roundf((2.0f * REFINE_FREQ_HALF_HZ) / REFINE_FREQ_STEP_HZ);
    for (int d = -REFINE_COARSE_TIME_HALF_SAMPLES; d <= REFINE_COARSE_TIME_HALF_SAMPLES; d++)
    {
        for (int k = 0; k <= n_freq_steps; k++)
        {
            float df  = -REFINE_FREQ_HALF_HZ + (float)k * REFINE_FREQ_STEP_HZ;
            float mag = costas_coherent_sum(bb1_re, bb1_im, n_bb1, fs1,
                                             base_origin1 + (float)d, df, sps1);
            if (mag > best_score_ab) { best_score_ab = mag; best_dt_samp = d; best_df = df; }
        }
    }

    free(bb1_re); free(bb1_im);

    /* ── Stage C: fine TIME search, baseband re-derived @ refined carrier ── */
    /*
     * KNOWN UNRESOLVED FINDING (r1-sync-refiner-instrument-validation, AC-3
     * time-dimension, escalated per design.md D5 -- NOT a "fix it here"
     * comment; recorded so the next session does not have to re-derive this):
     * on PURE NOISE input, best_fine_samp below shows a strong, reproducible
     * bias toward negative values (observed ~90%+ of trials in one sample) --
     * but ONLY when base_origin2 is built from a (best_dt_samp, best_df) pair
     * that was ITSELF selected by the Stage A+B argmax on the SAME underlying
     * noise. Confirmed NOT caused by: costas_coherent_sum's own math (a
     * constant-DC synthetic input over a huge buffer gives a perfectly flat,
     * unbiased score curve across the full d range); downconvert_decimate
     * (an independent Python re-implementation reproduces the same bias);
     * best_dt_samp or best_df being individually biased (each looks
     * reasonably balanced across many independent trials); or a fixed/forced
     * (non-selected) frequency or time offset (bias disappears when d/df are
     * held fixed rather than argmax-selected). The mechanism appears to be a
     * selection-bias / "double-dipping" interaction specific to feeding an
     * ALREADY-NOISE-OPTIMISED (best_dt_samp, best_df) pair from Stage A+B into
     * Stage C's own re-derivation and search over the SAME PCM, not a simple
     * sign or indexing defect. This does not affect AC-1/AC-2 (both PASS on
     * real signal trials, where the true signal dominates any noise-selection
     * artifact) or AC-3's frequency sub-check (PASSES, p=0.94). Per D5, this
     * is escalated rather than iterated on further in this session -- see the
     * QA report's AC-3 section for the full empirical trail.
     */
    int n_bb2 = pcm_len / REFINE_DECIM_FINE;
    float* bb2_re = (float*)malloc(sizeof(float) * (size_t)n_bb2);
    float* bb2_im = (float*)malloc(sizeof(float) * (size_t)n_bb2);
    if (!bb2_re || !bb2_im) { free(bb2_re); free(bb2_im); return -2; }

    float taps_fine[REFINE_LP_TAPS_FINE];
    design_lowpass_hann(taps_fine, REFINE_LP_TAPS_FINE,
                         REFINE_LP_CUTOFF_FINE_HZ, REFINE_SAMPLE_RATE_HZ);

    float refined_carrier = (float)coarse_freq_hz + best_df;
    downconvert_decimate(pcm, pcm_len, REFINE_SAMPLE_RATE_HZ,
                          refined_carrier, taps_fine, REFINE_LP_TAPS_FINE,
                          REFINE_DECIM_FINE, bb2_re, bb2_im);

    float fs2  = REFINE_RATE_FINE_HZ;
    float sps2 = fs2 * REFINE_SYMBOL_PERIOD_S; /* 320 samples/symbol @ 2000 Hz */
    float dt_coarse_s   = (float)best_dt_samp / fs1;
    float base_origin2  = (coarse_time_offset_s + dt_coarse_s) * fs2;

    int fine_half_samp = (int)roundf(REFINE_FINE_TIME_HALF_MS / (1000.0f / fs2));
    int fine_step_samp = (int)roundf(REFINE_FINE_TIME_STEP_MS / (1000.0f / fs2));
    if (fine_step_samp < 1) fine_step_samp = 1;

    int   best_fine_samp = 0;
    float best_score_c   = -1.0f;
    for (int d = -fine_half_samp; d <= fine_half_samp; d += fine_step_samp)
    {
        float mag = costas_coherent_sum(bb2_re, bb2_im, n_bb2, fs2,
                                         base_origin2 + (float)d, 0.0f, sps2);
        if (mag > best_score_c) { best_score_c = mag; best_fine_samp = d; }
    }

    free(bb2_re); free(bb2_im);

    float dt_fine_s = (float)best_fine_samp / fs2;

    *out_delta_freq_hz = best_df;
    *out_delta_time_s  = dt_coarse_s + dt_fine_s;
    *out_sync_score    = best_score_c;

    return 0;
}
