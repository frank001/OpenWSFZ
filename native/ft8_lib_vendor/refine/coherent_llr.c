/*
 * coherent_llr.c -- per-candidate coherent multi-symbol LLR formation,
 * diagnostic-only (r2-coherent-llr-instrument, Route B2 Phase 1,
 * FT8_SHIM_VERSION 20260043; corrected under Phase B, FT8_SHIM_VERSION
 * 20260044 -- see "PHASE B" note below).
 *
 * PHASE B (FT8_SHIM_VERSION 20260044, design.md D8/D9): two defects
 * diagnosed after Phase 1's own ROW 0g fired against the as-shipped
 * 20260043 binary (near-chance bit error on real audio) are fixed in this
 * revision, both in-place -- this function's signature and its "no
 * ft8_refine_candidate call" contract (design.md D1) are UNCHANGED:
 *   B1 -- the raw-PCM correlation origin (origin_sample_f) applies a
 *         runtime-derived unit-conversion correction; see the comment at
 *         its own computation site below.
 *   B2 -- the cross-n_syms fusion comparison standardises each window's
 *         per-bit LLRs by that window's own magnitude spread before
 *         comparing; see coh_window_scale's header comment.
 *
 * PLACEMENT (task 1.2, design.md Open Question 1): placed under
 * native/ft8_lib_vendor/refine/, alongside sync_refiner.c, exactly the
 * "likely placement" the change's own design.md named -- a new sibling FILE
 * rather than a new function appended to sync_refiner.c itself, so that
 * file (already reviewed and gated three times over: R1/R1b/M1/M2) stays
 * completely untouched apart from the two `static`-removal edits documented
 * in its own header comment. The two files share downconvert_decimate() /
 * design_lowpass_hann() via refine_common.h (HK-018 -- reuse, not
 * reimplementation) but own separate entry points and separate diagnostic
 * histories.
 *
 * PROVENANCE / CLEAN-ROOM NOTE: as with sync_refiner.c, this file is written
 * directly from the method description in this change's spec.md / design.md
 * (downconvert to complex baseband at the candidate's existing grid
 * frequency, phase retained -> per-symbol coherent tone-hypothesis
 * correlation, complex accumulation across the symbol with magnitude taken
 * last -> 1-/2-/3-symbol coherent window combination -> max-log per-bit LLR
 * formation). No WSJT-X source was available in or consulted during this
 * session. The downconversion/correlation mathematics are standard DSP
 * technique (coherent matched-filter demodulation, max-log soft-decision
 * extraction), derived independently and shared with sync_refiner.c's own
 * already-reviewed implementation.
 *
 * DESIGN.MD D1 (binding, restated here): this file's only entry point,
 * ft8_coherent_llr_at(), NEVER calls ft8_refine_candidate() or any other
 * position-search routine. The candidate position it is given (via
 * freq_hz/time_offset_s, snapped to the existing production lattice exactly
 * as ft8_extract_llrs_at already does) is used AS-IS.
 *
 * SIGNATURE CHOICE (recorded per task 1.2's "or record the placement/choice
 * actually made and why if different" instruction -- this is a signature
 * choice, not a placement one, but the same discipline applies): the
 * proposal.md illustrative signature was
 * `ft8_coherent_llr_at(pcm, num_samples, cand_freq_idx, cand_time_idx,
 * out_log174, out_diag)`. This implementation instead matches
 * ft8_extract_llrs_at's own established signature shape exactly --
 * `(pcm, pcm_len, freq_hz, time_offset_s, out_log174)`, continuous physical
 * units, no out_diag -- for two reasons: (1) the Phase 1 gate's own
 * candidate-identity requirement (spec.md "Candidate identity between the
 * grid and coherent extractions") is satisfied FOR FREE when the harness
 * calls both exports with the literal same two floats, with no extra
 * plumbing to keep a separate (freq_idx, time_idx) pair in sync between two
 * independently-built waterfalls; (2) this function performs the identical
 * snap-to-lattice + out-of-band rejection ft8_extract_llrs_at already
 * performs (see the lattice-snap block at the top of ft8_coherent_llr_at
 * below), so a caller-visible
 * freq_idx/time_idx pair would just be this function's own internal state
 * leaking out for no benefit. out_diag is omitted for the same reason
 * ft8_extract_llrs_at has no diagnostic out-param: this is a single-purpose
 * diagnostic instrument, not a production stage; the gate harness (task 4.3,
 * QA's future work) needs only the 174 LLRs.
 *
 * ALGORITHM (spec.md's own four steps, expanded):
 *
 *   (1) Downconvert the full 15 s PCM to complex baseband at the candidate's
 *       EXISTING grid frequency (tone 0's frequency, unrefined), reusing
 *       sync_refiner.c's downconvert_decimate() at its own Stage-1 working
 *       rate (200 Hz, 90 Hz cutoff) -- already sized for an 8-tone x 6.25 Hz
 *       span (43.75 Hz) with margin under the resulting 100 Hz Nyquist.
 *
 *   (2) For each of the FT8_ND (58) data symbols, correlate coherently
 *       against each of the 8 tone hypotheses: complex-accumulate the
 *       downconverted baseband against a continuous-phase reference over the
 *       symbol's own 32-sample (@200 Hz) duration, magnitude taken last.
 *       This is the n_syms=1 case of (3) below and, by construction, reduces
 *       exactly to decode.c's own ft8_extract_symbol() max-log formula (see
 *       coh_bits_from_window's derivation comment) -- the only difference is
 *       that THIS correlation is against phase-retaining complex baseband,
 *       not decode.c's precomputed magnitude-only FFT bins.
 *
 *   (3) Form 1-, 2- and 3-symbol coherent metrics: for a window of n_syms
 *       CONSECUTIVE data symbols starting at logical data-symbol index k0,
 *       enumerate all 8^n_syms joint tone-hypothesis combinations and, for
 *       each, complex-accumulate ACROSS the whole window (phase continuity
 *       held across the symbol boundaries WITHIN the window -- valid because
 *       FT8 is continuous-phase FSK and every symbol in the window is a
 *       HYPOTHESISED, hence fully computable, tone; magnitude taken once at
 *       the end of the whole window, not per-symbol). A window may not cross
 *       the mid-frame Costas block boundary (data symbols 0-28 and 29-57 are
 *       two separate contiguous real-time runs, split by a 7-symbol Costas
 *       block whose own tones are known but are NOT part of this per-bit
 *       hypothesis space) -- windows that would cross it are simply not
 *       formed; edge symbols fall back to shorter (or, at the very ends,
 *       only the n_syms=1) windows. This is the coherent analogue of
 *       decode.c's own (dead-code, magnitude-only) ft8_decode_multi_symbols
 *       n_syms grouping shape -- generalised to complex accumulation, and
 *       with this file's OWN bit-index convention (see (4)).
 *
 *   (4) Combine into per-bit LLRs via max-log over the tone hypotheses
 *       consistent with each bit (coh_bits_from_window: for symbol-in-window
 *       offset s and within-symbol bit b, max(window magnitude where that
 *       bit's hypothesis is 1) minus max(... is 0) -- the same max-log shape
 *       ft8_extract_symbol/ft8_decode_multi_symbols already use, but with
 *       THIS file's own, non-reversed bit<->window-position convention
 *       (documented at coh_bits_from_window) rather than reused verbatim,
 *       because decode.c's own convention there was never validated end to
 *       end (that code has no call site) and re-deriving it cleanly here was
 *       both safer and no more code). Every data symbol's 3 bits receive a
 *       candidate LLR from every VALID window (of every size 1/2/3) that
 *       contains it; the FINAL per-bit LLR is the candidate with the
 *       LARGEST MAGNITUDE across all of them -- an explicit, documented
 *       fusion choice (design.md D3's own latitude: "What is fixed is the
 *       method ... not its numeric constants" extends, for a diagnostic
 *       instrument with no prior art to match, to this one fusion rule too).
 *       Finally, normalised to the same scale ftx_normalize_logl() produces
 *       (formula duplicated locally as coh_normalize_logl -- six lines of
 *       pure arithmetic; NOT exposed non-static from decode.c, unlike
 *       ftx_extract_likelihood_at/ftx_compute_candidate_llr_stats, because
 *       ftx_normalize_logl is an EXISTING function already called by
 *       ftx_decode_candidate() on the production path -- changing its
 *       linkage risks codegen/inlining differences to that production call
 *       even though the logic is untouched; duplicating six lines of
 *       arithmetic here is strictly lower-risk than that, and decode.c is
 *       left with ZERO edits by this change).
 *
 * VALIDITY: this is a NEW, UNVALIDATED correlator. Per design.md's own Risks
 * section, this file's future ROW 0c (a mandatory two-sided sign unit test,
 * run by the Phase 1 gate harness once this export exists -- see this
 * change's tasks.md §4.3, task not yet run) is the guard against a sign or
 * bit-attribution defect in the above; nothing here should be trusted for
 * any downstream measurement until that test passes.
 *
 * No production call site: reachable only from test code and the Phase 1
 * gate harness this change's own tasks.md §4.3 will build. ftx_decode_candidate()
 * and ft8_decode_all's production decode path are untouched by this file's
 * addition -- decode.c has zero edits, and neither ft8_shim.c's ft8_decode_all
 * nor any other production entry point calls ft8_coherent_llr_at.
 */

#include "ft8_shim.h"       /* ft8_coherent_llr_at() prototype */
#include "refine_common.h"  /* downconvert_decimate / design_lowpass_hann (task 1.1, reused) */

#include <ft8/constants.h>  /* FTX_LDPC_N, FT8_SYMBOL_PERIOD, FT8_ND, kFT8_Gray_map */
#include <ft8/decode.h>     /* ftx_waterfall_t -- only its dimension fields (num_bins/freq_osr/
                              * time_osr), which monitor_init() populates from monitor_config_t
                              * alone; monitor_process() (the actual FFT waterfall build) is
                              * never called here -- see the lattice-snap block below. */
#include <common/monitor.h> /* monitor_t, monitor_config_t, monitor_init/monitor_free */

#include <math.h>
#include <stdlib.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/* ── Locally-redefined constants (ft8_shim.c-internal values, not re-exported
 * via ft8_shim.h) -- same discipline sync_refiner.c's REFINE_EXPECTED_SAMPLES
 * already established: redefined here under a distinct name rather than
 * shared, since ft8_shim.h does not export them. Values match ft8_shim.c's
 * own #defines (FT8_SAMPLE_RATE, FT8_EXPECTED_SAMPLES, K_FREQ_OSR, K_TIME_OSR)
 * and ft8_extract_llrs_at's own literal monitor_config_t (f_min/f_max). */
#define COH_SAMPLE_RATE_HZ   12000.0f
#define COH_EXPECTED_SAMPLES 180000
#define COH_FREQ_OSR         2
#define COH_TIME_OSR         2
#define COH_F_MIN_HZ         200.0f
#define COH_F_MAX_HZ         3000.0f
#define COH_TONE_SPACING_HZ  6.25f     /* FT8 tone spacing, Hz */
#define COH_SYMBOL_PERIOD_S  0.160f    /* FT8_SYMBOL_PERIOD */

/* Working-rate downconversion: reuse sync_refiner.c's own Stage-1 parameters
 * (200 Hz rate, 90 Hz cutoff) -- already sized for an 8-tone x 6.25 Hz span
 * (43.75 Hz) with margin under the 100 Hz Nyquist this decimation implies. */
#define COH_DECIM        60
#define COH_RATE_HZ       (COH_SAMPLE_RATE_HZ / (float)COH_DECIM)
#define COH_LP_TAPS       121
#define COH_LP_CUTOFF_HZ  90.0f

/* Data-symbol block split (decode.c's own ft8_extract_likelihood: symbols
 * 0-28 precede the second Costas block by a +7 real-time offset, symbols
 * 29-57 by +14 -- i.e. two contiguous real-time runs of 29 symbols each,
 * split by the mid-frame 7-symbol Costas block). */
#define COH_BLOCK1_LAST  28  /* last logical data-symbol index of block 1 */
#define COH_BLOCK2_FIRST 29  /* first logical data-symbol index of block 2 */

#define COH_MAX_NSYMS  3
#define COH_MAX_NTONES 512  /* 8^COH_MAX_NSYMS */

typedef struct { float re, im; } coh_cplx_t;

/*
 * coh_sym_time_index -- real-time symbol position (0..78) for logical
 * data-symbol index p (0..57). Mirrors decode.c's ft8_extract_likelihood:
 * "Skip either 7 or 14 sync symbols."
 */
static int coh_sym_time_index(int p)
{
    return p + ((p < 29) ? 7 : 14);
}

/*
 * coh_window_valid -- true iff the n_syms-symbol window starting at logical
 * data-symbol k0 stays within a single contiguous real-time block (does not
 * straddle the mid-frame Costas block boundary), and stays within [0, 58).
 */
static int coh_window_valid(int k0, int n_syms)
{
    int k_last = k0 + n_syms - 1;
    if (k0 < 0 || k_last >= FT8_ND) return 0;
    int crosses = (k0 <= COH_BLOCK1_LAST) && (k_last >= COH_BLOCK2_FIRST);
    return !crosses;
}

/*
 * coh_window_metrics -- coherent correlation across n_syms consecutive data
 * symbols starting at logical data-symbol index k0, against every one of the
 * 8^n_syms joint tone-hypothesis combinations. Writes n_tones magnitudes to
 * out_mag (caller-sized COH_MAX_NTONES). See this file's header comment,
 * ALGORITHM step (3), for the coherence argument.
 *
 * Combination index j decomposes symbol-major, LSB = window's FIRST symbol
 * (offset s=0, i.e. k0 itself): bits_s = (j >> (3*s)) & 7 for s = 0..n_syms-1.
 * bits_s is the pre-Gray-map 3-bit hypothesis value for symbol k0+s; the
 * physical tone correlated against is kFT8_Gray_map[bits_s] (same lookup
 * ft8_extract_symbol/ft8_decode_multi_symbols already use).
 *
 * PERFORMANCE: the phase reference is advanced by REPEATED COMPLEX
 * MULTIPLICATION against a per-tone rotation increment (tone_drc/tone_drs,
 * an 8-entry table the caller precomputes ONCE per ft8_coherent_llr_at call
 * -- cosf/sinf depend only on `fs` and the 8 possible tone frequencies, not
 * on window/combination/sample), rather than calling cosf/sinf per sample as
 * sync_refiner.c's costas_coherent_sum does. costas_coherent_sum runs at
 * most 3*7=21 trig calls total per candidate; a naive port of that pattern
 * here would cost up to 168 windows x 512 combinations x 3 symbols x ~32
 * samples x 2 trig calls -- tens of millions of transcendental calls per
 * candidate, impractical at the P-LIVE population's ~15,000-candidate scale
 * (task 4.3). Repeated unit-complex multiplication accumulates negligible
 * float32 drift over the <=96-sample windows here (nowhere near the
 * thousands of steps needed for visible drift), so no renormalisation is
 * needed. Numerically this computes the identical rotating reference
 * costas_coherent_sum's per-sample cosf/sinf would, to float32 rounding.
 */
static void coh_window_metrics(
    const float* bb_re, const float* bb_im, int n_bb,
    float origin_sample_f, float sps,
    const float* tone_drc, const float* tone_drs, /* [8], caller-precomputed */
    int k0, int n_syms,
    float* out_mag /* [8^n_syms] */)
{
    int n_tones = 1;
    for (int i = 0; i < n_syms; i++) n_tones *= 8;

    for (int j = 0; j < n_tones; j++)
    {
        coh_cplx_t sum = { 0.0f, 0.0f };
        /* Rotator starts at phase 0 (unit vector) at the WINDOW's own start:
         * the transmitter's absolute phase there is a free constant
         * magnitude-taking absorbs -- same discipline as
         * costas_coherent_sum's per-block reset in sync_refiner.c,
         * generalised here to per-window since every symbol inside one
         * window is a hypothesised (hence phase-trackable) tone. */
        float rc = 1.0f, rs = 0.0f;

        for (int s = 0; s < n_syms; s++)
        {
            int bits_s = (j >> (3 * s)) & 0x07;
            int tone   = (int)kFT8_Gray_map[bits_s];
            float drc = tone_drc[tone];
            float drs = tone_drs[tone];

            int   p = k0 + s;
            float sym_start_f = origin_sample_f + (float)coh_sym_time_index(p) * sps;

            int i0 = (int)floorf(sym_start_f);
            int i1 = (int)floorf(sym_start_f + sps);

            for (int idx = i0; idx < i1; idx++)
            {
                /* Advance the rotator BEFORE use (matches sync_refiner.c's
                 * own cumsum-inclusive convention): even when idx is out of
                 * bounds, phase continuity across the whole window is
                 * unaffected by boundary clipping. */
                float new_rc = rc * drc - rs * drs;
                float new_rs = rc * drs + rs * drc;
                rc = new_rc;
                rs = new_rs;
                if (idx < 0 || idx >= n_bb) continue;
                /* correlate = baseband * conj(rotator) */
                float re = bb_re[idx] * rc + bb_im[idx] * rs;
                float im = bb_im[idx] * rc - bb_re[idx] * rs;
                sum.re += re;
                sum.im += im;
            }
        }

        out_mag[j] = sqrtf(sum.re * sum.re + sum.im * sum.im);
    }
}

/*
 * coh_bits_from_window -- max-log per-bit LLR extraction from an n_syms-
 * window's 8^n_syms magnitudes.
 *
 * BIT-INDEX CONVENTION (this file's own, NOT decode.c's ft8_decode_multi_symbols
 * convention -- see this file's header comment for why): output index
 * 3*s+b (s = symbol offset within the window, 0..n_syms-1; b = within-symbol
 * bit, 0..2, MSB-first matching ft8_extract_symbol's own bit order) tests
 * mask = 1 << (3*s + (2-b)) against combination index n. For n_syms=1, s=0
 * this reduces EXACTLY to ft8_extract_symbol's own three mask values (4, 2,
 * 1 for b=0,1,2) -- i.e. this function, called with n_syms=1, computes
 * identically-defined LLRs to decode.c's own single-symbol extraction,
 * verified by construction (the mask formula collapses to n_tones>>(b+1)
 * when n_syms=1, decode.c's own formula).
 */
static void coh_bits_from_window(const float* mag, int n_syms, float* out_bit_llr /* [3*n_syms] */)
{
    int n_tones = 1;
    for (int i = 0; i < n_syms; i++) n_tones *= 8;

    for (int s = 0; s < n_syms; s++)
    {
        for (int b = 0; b < 3; b++)
        {
            int mask = 1 << (3 * s + (2 - b));
            float max_zero = -1.0e30f, max_one = -1.0e30f;
            for (int n = 0; n < n_tones; n++)
            {
                float v = mag[n];
                if (n & mask) { if (v > max_one)  max_one  = v; }
                else          { if (v > max_zero) max_zero = v; }
            }
            out_bit_llr[3 * s + b] = max_one - max_zero;
        }
    }
}

/*
 * coh_window_scale -- B2 (design.md D9, Phase B): this window's own magnitude
 * spread, used to standardise its per-bit LLRs to a common, window-size-
 * independent scale before the cross-n_syms fusion comparison. A coherent
 * sum's magnitude scales with window length (more symbols accumulated ==
 * larger sums), so comparing raw fabsf() magnitude across differently-sized
 * windows is a near-constant structural preference for the longest window,
 * not a reliability comparison (2026-08-21 15:25Z spec §1.2). Population
 * standard deviation of this window's own n_tones magnitudes -- same
 * variance formula as coh_normalize_logl/ftx_normalize_logl, applied here to
 * mag[] instead of log174[]. Returns 0.0f for a degenerate (zero-spread)
 * window; the caller leaves that window's LLRs unscaled rather than divide
 * by zero (design.md D9's own guard).
 */
static float coh_window_scale(const float* mag, int n_tones)
{
    float sum = 0.0f, sum2 = 0.0f;
    for (int n = 0; n < n_tones; n++)
    {
        sum  += mag[n];
        sum2 += mag[n] * mag[n];
    }
    float inv_n = 1.0f / (float)n_tones;
    float variance = (sum2 - (sum * sum * inv_n)) * inv_n;
    if (!(variance > 0.0f)) return 0.0f; /* degenerate: caller leaves this window's LLRs unscaled */
    return sqrtf(variance);
}

/*
 * coh_normalize_logl -- same formula as decode.c's static ftx_normalize_logl
 * (compute the population variance of log174, scale by sqrt(24/variance)).
 * Deliberately DUPLICATED rather than exposed non-static from decode.c --
 * see this file's header comment, ALGORITHM step (4), for why: decode.c is
 * left with zero edits by this change.
 */
static void coh_normalize_logl(float* log174)
{
    float sum = 0.0f, sum2 = 0.0f;
    for (int i = 0; i < FTX_LDPC_N; ++i)
    {
        sum  += log174[i];
        sum2 += log174[i] * log174[i];
    }
    float inv_n = 1.0f / (float)FTX_LDPC_N;
    float variance = (sum2 - (sum * sum * inv_n)) * inv_n;
    if (!(variance > 0.0f)) return; /* degenerate (all-equal) candidate: leave unscaled rather than divide-by-zero */
    float norm_factor = sqrtf(24.0f / variance);
    for (int i = 0; i < FTX_LDPC_N; ++i)
        log174[i] *= norm_factor;
}

/*
 * ft8_coherent_llr_at -- see ft8_shim.h for the full ABI contract.
 *
 * Returns: 0 on success.
 *          -1 if pcm_len != COH_EXPECTED_SAMPLES, or pcm/out_log174 is NULL.
 *          -2 if a heap allocation failed.
 *          -3 if the resolved frequency bin falls outside the valid
 *             passband -- rejected, not silently clamped (same discipline
 *             ft8_extract_llrs_at already uses for a caller-supplied
 *             position with no ftx_find_candidates()-style in-band
 *             guarantee).
 */
int ft8_coherent_llr_at(
    const float* pcm, int pcm_len,
    float freq_hz, float time_offset_s,
    float* out_log174)
{
    if (pcm_len != COH_EXPECTED_SAMPLES || pcm == NULL || out_log174 == NULL) return -1;

    /* ── Snap (freq_hz, time_offset_s) to the SAME K_FREQ_OSR/K_TIME_OSR
     * lattice production candidates already live on, and reject an
     * out-of-band frequency -- reusing monitor_init() (not reimplementing
     * its arithmetic) purely to read back min_bin/symbol_period/num_bins,
     * exactly the fields ft8_extract_llrs_at's own inverse mapping uses.
     * monitor_process() is deliberately NOT called: those fields are pure
     * functions of monitor_config_t, not of the PCM, so building the actual
     * FFT waterfall here would be wasted work -- this function correlates
     * directly against raw PCM, not against a magnitude waterfall. */
    monitor_t mon;
    monitor_config_t cfg = {
        .f_min = COH_F_MIN_HZ, .f_max = COH_F_MAX_HZ,
        .sample_rate = (int)COH_SAMPLE_RATE_HZ,
        .time_osr = COH_TIME_OSR, .freq_osr = COH_FREQ_OSR,
        .protocol = FTX_PROTOCOL_FT8
    };
    monitor_init(&mon, &cfg);

    float symbol_period = mon.symbol_period;
    int   min_bin       = mon.min_bin;
    int   num_bins       = mon.wf.num_bins;
    int   freq_osr        = mon.wf.freq_osr;
    int   time_osr         = mon.wf.time_osr;

    float raw_freq_bin = freq_hz * symbol_period - (float)min_bin;
    float raw_time_bin = time_offset_s / symbol_period;

    long total_freq_sub = lroundf(raw_freq_bin * (float)freq_osr);
    long total_time_sub = lroundf(raw_time_bin * (float)time_osr);

    long freq_offset = total_freq_sub / freq_osr;
    long freq_sub     = total_freq_sub % freq_osr;
    long time_offset  = total_time_sub / time_osr;
    long time_sub      = total_time_sub % time_osr;
    if (freq_sub < 0) { freq_sub += freq_osr; freq_offset--; }
    if (time_sub  < 0) { time_sub  += time_osr;  time_offset--; }

    monitor_free(&mon);

    if (freq_offset < 0 || freq_offset >= num_bins) return -3;

    float freq_hz_grid = ((float)min_bin + (float)freq_offset + (float)freq_sub / (float)freq_osr) / symbol_period;
    float time_offset_s_grid = ((float)time_offset + (float)time_sub / (float)time_osr) * symbol_period;

    /* ── Downconvert the full cycle to complex baseband at the candidate's
     * OWN grid frequency (unrefined) -- design.md D1: no refined position
     * anywhere in this path. */
    int n_bb = pcm_len / COH_DECIM;
    float* bb_re = (float*)malloc(sizeof(float) * (size_t)n_bb);
    float* bb_im = (float*)malloc(sizeof(float) * (size_t)n_bb);
    if (!bb_re || !bb_im) { free(bb_re); free(bb_im); return -2; }

    float taps[COH_LP_TAPS];
    design_lowpass_hann(taps, COH_LP_TAPS, COH_LP_CUTOFF_HZ, COH_SAMPLE_RATE_HZ);

    downconvert_decimate(pcm, pcm_len, COH_SAMPLE_RATE_HZ,
                          freq_hz_grid, taps, COH_LP_TAPS,
                          COH_DECIM, bb_re, bb_im);

    float fs  = COH_RATE_HZ;
    float sps = fs * COH_SYMBOL_PERIOD_S;              /* 32 samples/symbol @ 200 Hz, exact */

    /* ── B1 (design.md D8, Phase B): waterfall-origin correction ──
     * time_offset_s_grid names the START of the analysis window at the
     * waterfall's own quantisation, but monitor_process's sliding look-back
     * buffer (nfft = block_size * freq_osr, Hann-windowed, peak at nfft/2)
     * means waterfall cell (block b, sub s) actually analyses PCM samples
     * centred at symbol-time b + (s+1)/time_osr - freq_osr/2, not b + s/time_osr
     * as a naive lattice-time-to-seconds conversion (used directly, as this
     * origin was before this fix) assumes. The correction below is the
     * resulting displacement, derived at runtime from mon.wf.time_osr /
     * mon.wf.freq_osr / mon.symbol_period (captured above before
     * monitor_free(&mon)) -- never hardcoded, since a hardcoded literal would
     * silently go wrong if K_TIME_OSR/K_FREQ_OSR ever changed. Evaluates to
     * exactly -1.0 symbol (-0.16 s) at production's own K_TIME_OSR =
     * K_FREQ_OSR = 2, matching qa/rr-study/n2-coherent-llr-extractor/
     * coherent_extract.py:227's independently, empirically-calibrated
     * TIME_ORIGIN_CORRECTION_SAMPLES_2K = -SPS_2K constant (task 7.3). Full
     * derivation: qa/rr-study/2026-08-21-1412-architect-to-qa-origin-
     * convention-finding-and-spec-b-orig-a.md. */
    float correction_symbols = 1.0f / (float)time_osr - (float)freq_osr / 2.0f - 0.5f;
    float origin_sample_f = (time_offset_s_grid + correction_symbols * symbol_period) * fs;

    /* Per-tone rotation increment, precomputed ONCE (8 entries; depends only
     * on fs and the 8 fixed tone frequencies -- see coh_window_metrics'
     * PERFORMANCE note). */
    float tone_drc[8], tone_drs[8];
    {
        float phase_step_per_hz = 2.0f * (float)M_PI / fs;
        for (int t = 0; t < 8; t++)
        {
            float phase_step = (float)t * COH_TONE_SPACING_HZ * phase_step_per_hz;
            tone_drc[t] = cosf(phase_step);
            tone_drs[t] = sinf(phase_step);
        }
    }

    /* ── Form 1-, 2- and 3-symbol coherent metrics for every valid window;
     * fuse into per-bit LLRs by taking, for every bit, the largest-magnitude
     * candidate across every window (of every size) that covers it. ── */
    memset(out_log174, 0, sizeof(float) * (size_t)FTX_LDPC_N);

    for (int n_syms = 1; n_syms <= COH_MAX_NSYMS; n_syms++)
    {
        int n_tones = 1;
        for (int i = 0; i < n_syms; i++) n_tones *= 8;

        int n_starts = FT8_ND - n_syms + 1;
        for (int k0 = 0; k0 < n_starts; k0++)
        {
            if (!coh_window_valid(k0, n_syms)) continue;

            float mag[COH_MAX_NTONES];
            coh_window_metrics(bb_re, bb_im, n_bb, origin_sample_f, sps,
                                tone_drc, tone_drs, k0, n_syms, mag);

            float bit_llr[3 * COH_MAX_NSYMS];
            coh_bits_from_window(mag, n_syms, bit_llr);

            /* B2 (design.md D9): standardise THIS window's per-bit LLRs to
             * a common, window-size-independent scale before the
             * cross-n_syms comparison below -- see coh_window_scale's own
             * header comment. n_syms is NOT restricted to defeat this (the
             * 1-, 2- and 3-symbol windows all remain in the comparison,
             * unchanged from before this fix); only the SCALE each
             * window's candidate is compared at changes. */
            float scale = coh_window_scale(mag, n_tones);
            if (scale > 0.0f)
            {
                float inv_scale = 1.0f / scale;
                for (int i = 0; i < 3 * n_syms; i++)
                    bit_llr[i] *= inv_scale;
            }
            /* else: degenerate window (zero magnitude spread) -- leave its
             * bit_llr unscaled rather than divide by zero (design.md D9). */

            for (int s = 0; s < n_syms; s++)
            {
                int p = k0 + s;
                for (int b = 0; b < 3; b++)
                {
                    int gb = 3 * p + b;
                    if (gb >= FTX_LDPC_N) continue; /* defensive; FT8_ND*3 == FTX_LDPC_N exactly */
                    float candidate = bit_llr[3 * s + b];
                    if (n_syms == 1 || fabsf(candidate) > fabsf(out_log174[gb]))
                        out_log174[gb] = candidate;
                }
            }
        }
    }

    free(bb_re);
    free(bb_im);

    coh_normalize_logl(out_log174);

    return 0;
}
