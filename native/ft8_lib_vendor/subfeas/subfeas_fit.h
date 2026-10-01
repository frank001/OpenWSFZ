/*
 * subfeas_fit.h -- data-aided fit + time-varying-envelope subtraction.
 *
 * sub-feas-native-subtraction (design.md Decision 1/2): OpenWSFZ-ORIGINAL
 * code, not part of the byte-identical-to-upstream ft8_lib vendor tree --
 * deliberately placed in this sibling `subfeas/` directory, same provenance
 * footing as `refine/` (design.md D7 precedent): additive to the vendor
 * tree, not a modification of any byte-identical-to-upstream file.
 *
 * PROVENANCE: this is a direct, line-traceable port of this repo's OWN prior
 * work -- qa/rr-study/sub-feas/fitter.py (`fine_fit_with_drift`,
 * `lp_envelope`, `subtract`) and qa/rr-study/synth/modulator.py
 * (`instantaneous_phase`, GFSK Gaussian-pulse synthesis) -- both already
 * clean-room implementations per their own docstrings/history (fitter.py:
 * "every line below is a from-scratch numpy implementation... rather than
 * transcribing anything from the QEX paper or WSJT-X"). Porting this
 * project's own validated Python to C carries no additional licence
 * question beyond the project's own licence.
 *
 * Two entry points, per design.md's Decision 2 addendum (C#-orchestrated
 * parallelism, one native call per signal, each independently
 * __try/__except-wrapped like ft8_decode_all):
 *
 *   ft8_subfeas_compute_analytic() -- ONE call per cycle (not per signal).
 *     Computes the analytic signal (Hilbert transform) of the real PCM
 *     buffer once; the result is read-only and shared (unchanged) across
 *     every subsequent per-signal fit call for that cycle.
 *
 *   ft8_subfeas_fit_signal() -- ONE call per pass-0 decoded, re-encodable
 *     signal, called concurrently from C# (Task/Parallel.ForEach). Runs the
 *     full data-aided fit (fine_fit_with_drift) + time-varying envelope
 *     (lp_envelope) + subtract pipeline for exactly one signal against the
 *     shared analytic buffer, and writes that signal's full-cycle-length,
 *     zero-padded subtraction waveform (s_hat, positioned at its fitted
 *     location) into a caller-allocated output buffer. Does NOT touch any
 *     shared/global state (no g_session_hash_table, no existing TLS
 *     getters) -- self-contained, per design.md's Decision 2 addendum.
 */
#ifndef SUBFEAS_FIT_H
#define SUBFEAS_FIT_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Fixed protocol/method constants -- inherited from fitter.py/modulator.py,
 * NOT independently re-derived (design.md Decision 1 Non-Goal). */
#define SUBFEAS_FS_HZ            12000.0
#define SUBFEAS_NUM_SYMBOLS      79
#define SUBFEAS_SPS              1920      /* samples per symbol @ 12kHz: round(0.16*12000) */
#define SUBFEAS_N_TX             151680    /* SUBFEAS_NUM_SYMBOLS * SUBFEAS_SPS */
#define SUBFEAS_TONE_SPACING_HZ  6.25
#define SUBFEAS_GFSK_BT          2.0       /* Gaussian shaping BT product, FT8 standard */
#define SUBFEAS_TAU0_S           (-0.1600) /* nominal fit position offset */
#define SUBFEAS_DT_RANGE_MS      100.0
#define SUBFEAS_DT_STEP_MS       1.0
#define SUBFEAS_DF_RANGE_HZ      2.0
#define SUBFEAS_N_FFT            262144
#define SUBFEAS_FDOT_RANGE_HZ_S  0.10
#define SUBFEAS_FDOT_STEP_HZ_S   0.005
#define SUBFEAS_ENVELOPE_W_S     0.32      /* W*, lp_envelope window width */

/* PCM buffer size this module fits against -- matches FT8_EXPECTED_SAMPLES
 * (ft8_shim.c-internal, redefined here under a distinct name per that
 * file's own existing convention, see sync_refiner.c). */
#define SUBFEAS_PCM_LEN          180000

/*
 * ft8_subfeas_compute_analytic -- Hilbert-transform a real PCM buffer to its
 * analytic signal. ONE call per cycle; result is shared read-only input to
 * every subsequent ft8_subfeas_fit_signal call for that cycle.
 *
 * Parameters:
 *   pcm         -- float32 samples, SUBFEAS_PCM_LEN long
 *   out_re/out_im -- caller-allocated, SUBFEAS_PCM_LEN long each; receive the
 *                    analytic signal's real/imaginary parts
 *
 * Returns: 0 on success, -1 on bad arguments, -2 on SEH fault (MSVC/Windows
 * builds only; matches ft8_decode_all's existing containment discipline).
 */
int ft8_subfeas_compute_analytic(
    const float* pcm,
    float* out_re,
    float* out_im
);

/*
 * ft8_subfeas_fit_signal -- fit and synthesize one signal's subtraction
 * waveform against the cycle's precomputed analytic signal.
 *
 * Parameters:
 *   x_a_re/x_a_im  -- analytic signal from ft8_subfeas_compute_analytic,
 *                     SUBFEAS_PCM_LEN long each (read-only, not mutated)
 *   tones          -- SUBFEAS_NUM_SYMBOLS (79) tone indices, each in [0,7],
 *                     from ft8_encode_message() on this signal's decoded text
 *   decoded_dt_s   -- this signal's decoded DT (seconds)
 *   decoded_freq_hz -- this signal's decoded frequency (Hz)
 *   cancel_flag    -- NULL (no deadline) or a pointer to an int owned by the caller and valid for the
 *                     whole call. The caller sets it non-zero (volatile write) to cancel; the fit reads
 *                     it through a volatile pointer. NULL keeps the no-deadline path bit-identical.
 *   out_shat       -- caller-allocated, SUBFEAS_PCM_LEN long; on success,
 *                     receives the full-cycle-length subtraction waveform
 *                     (s_hat, zero outside the fitted signal's ~12.64s
 *                     window). Caller subtracts this from a copy of the
 *                     original PCM to build the residual. Zeroed by this
 *                     function unconditionally, including on failure.
 *
 * Returns: 0 on success (out_shat populated).
 *          -1 on bad arguments (NULL pointer, tone index out of [0,7]).
 *          -2 on SEH fault (MSVC/Windows builds only) -- caller must treat
 *             this exactly as ft8_decode_all's -2: log and skip. Per
 *             design.md Decision 4, a -2 from ANY signal in a cycle means
 *             the WHOLE cycle's residual pass is abandoned (fall back to
 *             pass-0-only) -- do not silently keep other signals' results.
 *          -4 cancelled by deadline (sub-feas-speed-redesign A5): *cancel_flag was non-zero on
 *             entry or became non-zero during the fit (checked at the top of every dt, fdot and
 *             envelope iteration). out_shat is all-zero, the workspace is returned to the pool,
 *             no other in-flight fit is disturbed. This is a normal deadline outcome, NOT an error.
 *          -3 if every fit candidate position ran off the buffer edge (no
 *             valid fit found for this signal -- matches fitter.py's
 *             `fine_fit`/`fine_fit_with_drift` returning None). out_shat is
 *             all-zero; this is a normal, expected outcome for a signal near
 *             a cycle boundary, not a failure requiring cycle fallback.
 *
 * Self-contained: allocates and frees its own heap buffers (FFT config,
 * working buffers, templates, envelope array) within this call, per
 * design.md Decision 4 / the Decision 2 addendum's "no shared pool" note.
 * Touches no shared/global/TLS state -- safe to call concurrently from
 * multiple threads, each with its own read-only x_a_re/x_a_im and its own
 * out_shat.
 */
int ft8_subfeas_fit_signal(
    const float* x_a_re,
    const float* x_a_im,
    const uint8_t* tones,
    float decoded_dt_s,
    float decoded_freq_hz,
    float* out_shat,
    const volatile int* cancel_flag
);

/* ---- Workspace pool (sub-feas-speed-redesign A3; see subfeas_fit.c and design.md D2) ---------- */

#define SUBFEAS_POOL_MAX_BOUND      64  /* hard cap on the pool bound (array size) */
#define SUBFEAS_POOL_DEFAULT_BOUND   4  /* bound if the caller never configures one: the pre-change
                                         * MaxDegreeOfParallelism cap, so an unconfigured caller behaves
                                         * as before */
#define SUBFEAS_POOL_STATS_LEN       7

/*
 * ft8_subfeas_pool_configure -- set the pool bound (clamped to [1, SUBFEAS_POOL_MAX_BOUND]) and
 * (re)open the pool. Call at a cycle boundary with no fit in flight; shrinking frees the surplus
 * idle workspaces now and leased ones as they come back.
 */
void ft8_subfeas_pool_configure(int bound);

/*
 * ft8_subfeas_pool_shutdown -- free every idle workspace now; leased ones are freed as they are
 * returned, so this never frees a workspace a fit is using. A later ft8_subfeas_pool_configure
 * reopens the pool.
 */
void ft8_subfeas_pool_shutdown(void);

/*
 * ft8_subfeas_pool_get_stats -- counters for tests and diagnostics. out[] has SUBFEAS_POOL_STATS_LEN
 * ints: [0] bound, [1] live (idle + leased), [2] idle, [3] leased, [4] peak leased since the last configure,
 * [5] lease refusals since the last configure (pool at its bound; never expected at matching parallelism), [6] bytes per workspace.
 */
void ft8_subfeas_pool_get_stats(int* out);

#ifdef __cplusplus
}
#endif

#endif /* SUBFEAS_FIT_H */
