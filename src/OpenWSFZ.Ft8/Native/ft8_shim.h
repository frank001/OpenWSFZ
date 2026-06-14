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

#include <stdint.h>  /* uint8_t */

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
 *              assumption drove cancellation amplitude to near-zero.
 *              REJECTED (H3b): S7 overall 37.63% vs 54.84% baseline (−17.21 pp);
 *              P0/P1 both 0/6.  PCM-domain SIC alone cannot match spectrogram
 *              suppression baseline.  SUPERSEDED by 20260010.
 *   20260010 — diag-d001-h4-spectrogram-reinstate: H3b PCM-domain GFSK quadrature
 *              SIC call site removed from ft8_decode_all; spectrogram-domain
 *              soft-SNR tile suppression reinstated as the sole inter-pass mechanism
 *              (suppress_candidate_tiles loop, as in 20260006).  GFSK helpers
 *              (build_gfsk_kernel, synth_ft8_gfsk_quad, compute_quadrature_amplitude)
 *              retained in source but not called; D-003 TLS diagnostic
 *              (tls_last_noise_floor_db, ft8_get_last_noise_floor_db) retained.
 *              Single-variable recovery experiment (H4) for D-001 co-channel gap.
 *   20260011 — diag-d001-h5-suppression-tuning: suppression ramp shifted 10 dB
 *              toward lower SNRs: K_SOFT_SUPP_SNR_MIN_DB −5.0 → −15.0 dB,
 *              K_SOFT_SUPP_SNR_MAX_DB +15.0 → +5.0 dB.  At 0 dB SNR (S7 test
 *              condition) suppression increases from 25% (H4) to 75% (H5).
 *              No other shim logic, pass configuration, or struct layout changed.
 *              Single-variable diagnostic experiment (H5) for D-001.
 *              REJECTED: S7 overall 43/93 = 46.24% (−10.75 pp vs H4 56.99%
 *              baseline).  Over-suppression confirmed — 75% attenuation at 0 dB
 *              SNR removes shared tile energy in time_freq scenarios and the weak
 *              signal's contribution in capture scenarios.
 *              FT8_SHIM_VERSION reverted to 20260010 (H4 baseline restored).
 *   20260012 — fix-d004-local-noise-floor: per-signal local noise floor replaces
 *              the global histogram-median in the SNR formula.
 *              `compute_local_noise_floor_db` samples waterfall bins in a K=32-bin
 *              sideband window on each side of the decoded signal's 8-tone span
 *              (200 Hz per sideband at 6.25 Hz/bin).  Makes SNR invariant to
 *              audio-chain frequency response.  Global noise floor retained for
 *              per-cycle diagnostic logging.  Resolves D-003 and D-004.
 *              Version 20260011 slot used for H5 suppression-tuning diagnostic
 *              (REJECTED; reverted).  20260012 is the D-003/D-004 fix.
 *   20260013 — fix-seh-av-containment: __try/__except(EXCEPTION_EXECUTE_HANDLER)
 *              wrapper added around the body of ft8_decode_all (MSVC / Windows
 *              only).  On any access violation (0xC0000005) the shim now returns
 *              -2 instead of crashing the process.  The managed layer translates
 *              -2 into NativeAccessViolationException, which Ft8Decoder catches,
 *              logs at WARNING, and converts to an empty-result skip.
 *              Struct layout unchanged (48 bytes).  Return code -2 is a new
 *              semantic term in the contract, hence the version bump.
 *              Non-MSVC builds (Linux / macOS) are unaffected — no SEH;
 *              SIGSEGV behaviour unchanged.  Root cause (D-006) still unknown.
 *   20260014 — diag-d006-minidump: MiniDumpWriteDump capture moved from
 *              __except body into a dedicated ft8_av_exception_filter() function
 *              called in the filter-expression position.  GetExceptionInformation()
 *              is only valid during filter evaluation (before stack unwind); the
 *              v20260013 approach called MiniDumpWriteDump in the handler body
 *              after stack unwind, leaving s_av_ep stale and producing a dump
 *              with no ExceptionStream (crash address unknown).  The filter now
 *              writes MiniDumpWithFullMemory to C:\Dumps\ with valid
 *              EXCEPTION_POINTERS before returning EXCEPTION_EXECUTE_HANDLER.
 *              No ABI change; struct layout and return codes unchanged.
 *   20260016 — fix-d006-cleanup: ft8_av_exception_filter() and MiniDumpWriteDump
 *              infrastructure removed (diagnostic, one-shot; served its purpose).
 *              __except reverts to simple EXCEPTION_EXECUTE_HANDLER.  Also fixes
 *              RQ-2: signal_db computation now guards against out-of-bounds
 *              waterfall access for signals ≥ 2956 Hz (freq_offset + tone_col
 *              >= num_bins skips the sample rather than reading past row end).
 *              No ABI change; struct layout and return codes unchanged.
 *   20260015 — fix-d006-ptr-truncation: binary patch to message.obj fixing a
 *              32-bit pointer truncation in ftx_message_decode() (ft8/message.c).
 *              The function called an internal stpcpy() and captured its char*
 *              return via MSVC-generated `movsxd rbx, eax` (sign-extend 32-bit)
 *              instead of `mov rbx, rax` (full 64-bit move).  When the caller-
 *              provided buffers reside above the 4 GB VA boundary — as they do
 *              when the .NET managed heap or the thread stack is allocated above
 *              0x100000000 — the upper 32 bits of the returned pointer are
 *              silently dropped, producing an invalid write address and an
 *              access violation (0xC0000005).  The crash manifested only for
 *              FT8 messages with the "R " reply-prefix (bit 0x20 of the i3/n3
 *              type field set), which triggers the stpcpy code path.  Confirmed
 *              by crash dump analysis: ExceptionAddress 0x7FFA1A613D06 (RVA
 *              0x3D06 in libft8.dll), WRITE to 0x37E3B0BA; RCX=0x1737E3B0B6
 *              (correct 64-bit), RBX=0x37E3B0B6 (truncated).  Fix: change the
 *              single opcode byte at message.obj offset 0x01B27 from 0x63
 *              (MOVSXD) to 0x8B (MOV), then rebuild DLL.  Struct layout and
 *              return codes unchanged.
 *   20260017 — ft8-qso-answerer-v1: add ft8_encode_message() entry point.
 *              Exposes the TX encode path (text → ftx_message_t payload →
 *              79 tone indices) so the managed layer can synthesise GFSK audio
 *              for QSO answerer transmissions.  Uses ftx_message_encode() from
 *              ft8/message.h and ft8_encode() from ft8/encode.h — both already
 *              linked.  Returns FT8_NN (79) on success; negative error code on
 *              failure.  No ABI change to existing entry points; struct layout
 *              and existing return codes unchanged. */
#define FT8_SHIM_VERSION 20260017

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
 *          Returns -2 if an access violation or other SEH fault occurs
 *          inside the decode pipeline (MSVC / Windows builds only).  The
 *          managed layer should treat -2 as a recoverable skip: log the
 *          event and return empty results for that cycle.  Non-MSVC builds
 *          (Linux / macOS) do not trap SEH faults and will SIGSEGV instead.
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

/*
 * ft8_encode_message — encode an FT8 text message to 79 tone indices.
 *
 * Parameters:
 *   message        — null-terminated FT8 message text (e.g. "Q1OFZ Q1TST JO33")
 *   tones_out      — caller-allocated output array; receives 79 tone indices
 *                    in the range [0, 7]
 *   tones_capacity — size of tones_out; must be >= FT8_NN (79)
 *
 * Returns:
 *   FT8_NN (79) on success.
 *   -1 if tones_capacity < FT8_NN.
 *   -2 if the message text cannot be packed (invalid format, too long, etc.);
 *      the native error code (ftx_message_rc_t) is NOT returned separately —
 *      the managed wrapper should throw InvalidOperationException.
 *
 * Thread-safe: uses a local callsign table on the stack; no TLS state modified.
 */
int ft8_encode_message(const char* message, uint8_t* tones_out, int tones_capacity);

#ifdef __cplusplus
}
#endif

#endif /* FT8_SHIM_H */
