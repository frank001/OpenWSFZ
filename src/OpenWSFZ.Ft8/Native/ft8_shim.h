/*
 * ft8_shim.h — Public ABI for the OpenWSFZ libft8.dll shim
 *
 * This header declares the two symbols exported by libft8.dll:
 *   ft8_lib_version_check()  — ABI sentinel; must return FT8_SHIM_VERSION
 *   ft8_decode_all()         — decode FT8 signals from a 15-second PCM buffer
 *
 * The managed caller (Ft8LibInterop.cs) P/Invokes both functions.
 * Marshal.SizeOf<Ft8NativeResult>() MUST equal sizeof(FT8Result) = 48 bytes.
 *
 * Layout:
 *   offset  0 : int   freq_hz  (4 bytes)
 *   offset  4 : float dt       (4 bytes)
 *   offset  8 : int   snr      (4 bytes)
 *   offset 12 : char  message  (36 bytes, null-terminated, max 35 chars)
 *   total     : 48 bytes — no padding
 */

#ifndef FT8_SHIM_H
#define FT8_SHIM_H

#ifdef __cplusplus
extern "C" {
#endif

/* Bump this constant whenever the ABI changes (struct layout, function
 * signatures). The managed loader checks it matches FT8_SHIM_VERSION.
 * History:
 *   20240001 — initial release (single-pass decode)
 *   20260001 — p15: iterative subtraction; ft8_get_last_pass_counts added
 *   20260002 — R6 weak-signal post-correction removed (R&R-001 linearity fix)
 *              revert-pcm-sic: PCM-domain SIC reverted; back to two-pass
 *              spectrogram-suppression (no net improvement, two P1 crashes)
 *   20260004 — fix-d001-revised Option B: hard-zero tile suppression replaced
 *              with soft SNR-scaled linear attenuation (K_SOFT_SUPP_SNR_MIN_DB
 *              to K_SOFT_SUPP_SNR_MAX_DB range); suppress_candidate_tiles now
 *              takes snr_db parameter; suppress accumulator stores per-decode
 *              SNR.  Version 20260003 skipped (was the reverted PCM-SIC).
 *   20260005 — D-003 diagnostics: add ft8_get_last_noise_floor_db() TLS getter
 *              exposing the histogram-median noise floor computed by
 *              compute_noise_floor() within the most recent ft8_decode_all call.
 *              No change to decode logic or struct layout.
 *   20260006 — D-002 fix: SNR calibration; bandwidth constant -26.0 → -26.5 dB
 *              to bring OpenWSFZ SNR bias within ±2.0 dB (R&R S1 gate).
 *   20260007 — diag-D001-three-pass-sic: K_MAX_PASSES increased 2→3 as a
 *              controlled diagnostic experiment to quantify pass-count contribution
 *              to co-channel recovery (D-001, High). Pass 2 reuses pass-1 params.
 *              K_MAX_DECODED raised to 140+200+200=540. Suppression accumulator
 *              guard extended to cover pass 0 and pass 1. No algorithm change.
 *              REVERTED (revert-diag-d001): S7 R&R result −4.30 pp vs 2-pass
 *              baseline (50.54% vs 54.84%).  H2 rejected — no co-channel
 *              improvement; marginal capture regression.  See results/
 *              2026-06-12-3ecf8ae/report-v2.md.
 *   20260008 — diag-d001-pcm-sic: PCM-domain SIC replaces spectrogram suppression
 *              in the inter-pass stage.  For each signal decoded in pass 0, a
 *              CP-FSK waveform is synthesised (heap-allocated synth_buf, phase zero,
 *              no Gaussian shaping), scaled via least-squares projection amplitude,
 *              and subtracted from a heap-allocated copy of the input PCM
 *              (residual_pcm).  Pass 1 operates on a waterfall rebuilt from
 *              residual_pcm using a second monitor_t (mon2).  Version 20260007 slot
 *              skipped (was the reverted three-pass SIC) to avoid confusion.
 *              SUPERSEDED by 20260009 (H3b GFSK quadrature SIC — see below).
 *   20260009 — diag-d001-h3b-gfsk-sic: GFSK quadrature synthesiser replaces CP-FSK
 *              scalar synthesiser; analytic quadrature amplitude estimator replaces
 *              scalar projection; two additional heap buffers (synth_buf_q,
 *              gfsk_kernel) plus GFSK kernel prefix sum (gfsk_prefix) allocated in
 *              the pass-1 SIC block; total PCM-domain SIC heap ≈ 2.21 MB.
 *              H3 root-cause: CP-FSK vs GFSK modulation mismatch + phase-zero
 *              assumption drove cancellation amplitude to near-zero. */
#define FT8_SHIM_VERSION 20260009

/* One decoded FT8 message. sizeof(FT8Result) == 48. */
typedef struct
{
    int   freq_hz;      /* Centre frequency of the signal, Hz                  */
    float dt;           /* Time offset from cycle start, seconds               */
    int   snr;          /* SNR estimate, dB — noise-floor based (R5)            */
    char  message[36];  /* Null-terminated text, max 35 chars (FTX_MAX_MESSAGE_LENGTH) */
} FT8Result;

/*
 * ft8_lib_version_check — ABI sentinel.
 * Returns the compile-time constant FT8_SHIM_VERSION.
 * The managed loader calls this immediately after NativeLibrary.Load and
 * throws InvalidOperationException if the value does not match.
 */
int ft8_lib_version_check(void);

/*
 * ft8_decode_all — decode all FT8 signals from a 15-second PCM buffer.
 *
 * Parameters:
 *   pcm         — float32 samples, 12 kHz mono, normalised to [-1, 1]
 *   pcm_len     — must be 180 000 (15 s × 12 000 Hz)
 *   results     — caller-allocated array of FT8Result; receives the decoded messages
 *   max_results — size of the results array; at most this many messages are written
 *
 * Returns: number of unique messages written to results (0..max_results).
 *          Returns -1 if pcm_len != 180 000.
 */
int ft8_decode_all(
    const float* pcm,
    int          pcm_len,
    FT8Result*   results,
    int          max_results
);

/*
 * ft8_get_last_pass_counts — return per-pass new-decode counts from the
 * most recent ft8_decode_all call on this thread.
 *
 * Parameters:
 *   out_counts — caller-allocated array; receives one int per pass executed
 *   capacity   — size of out_counts; must be ≥ K_MAX_PASSES for full data
 *
 * Returns: number of passes actually executed (≤ capacity).
 *          out_counts[i] = number of new (non-duplicate) decodes in pass i.
 *
 * Thread-safe: stored in thread-local storage; concurrent callers on
 * different threads do not interfere.
 */
int ft8_get_last_pass_counts(int* out_counts, int capacity);

/*
 * ft8_get_max_passes — return the number of decode passes executed per
 * ft8_decode_all call (compile-time constant K_MAX_PASSES).
 *
 * The managed loader verifies this matches its own MaxDecodePasses constant
 * at initialisation time, detecting K_MAX_PASSES / MaxDecodePasses drift
 * before any decode call is attempted.
 */
int ft8_get_max_passes(void);

/*
 * ft8_get_last_noise_floor_db — return the histogram-median waterfall noise
 * floor (dB) computed during the most recent ft8_decode_all call on this thread.
 *
 * Value is (median_uint8 * 0.5) − 120.0, matching the noise_floor_db used in
 * the SNR formula: SNR = signal_db − noise_floor_db − 26.5.
 *
 * Thread-safe: stored in thread-local storage; must be called on the same
 * thread that called ft8_decode_all (same constraint as ft8_get_last_pass_counts).
 * Returns 0.0f if ft8_decode_all has not yet been called on this thread.
 */
float ft8_get_last_noise_floor_db(void);

#ifdef __cplusplus
}
#endif

#endif /* FT8_SHIM_H */
