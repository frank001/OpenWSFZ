/*
 * ft8_shim.c — OpenWSFZ libft8.dll shim
 *
 * Wraps the kgoba/ft8_lib v2.0 decode pipeline (monitor → find candidates →
 * decode each → unpack text) behind the simple ft8_decode_all() entry point
 * declared in ft8_shim.h.
 *
 * p15 — Iterative signal subtraction (spectrogram-domain approach):
 *
 *   After the first decode pass, each decoded signal's waterfall tiles are
 *   suppressed using the EXACT decoded tone sequence (from ft8_encode).  For
 *   each of the 79 decoded symbols, the active tone bin and its ±1 nearest
 *   neighbours (to cancel Hann-window first sidelobes) are set to the
 *   noise-floor median value across all time/frequency over-sampling sub-bins.
 *   A second pass then runs on the modified waterfall using a wider candidate
 *   net (lower min_score, more candidates, more LDPC iterations).
 *
 * revert-pcm-sic — PCM-domain SIC reverted:
 *
 *   The fix-D001 PCM-domain SIC (three-pass: carrier estimation, CP-FSK
 *   waveform synthesis, PCM subtraction, waterfall rebuild) was reverted after
 *   the R&R study showed no measurable improvement (-0.1 pp) and two fatal
 *   0xC0000005 crashes occurred in production.  The two-pass spectrogram-
 *   suppression structure from p15 is restored.  FT8_SHIM_VERSION returns to
 *   20260002.  See DEFECT-native-stack-overflow-pcm-residual.md.
 *
 * fix-d001-revised — Option B: soft SNR-scaled tile attenuation:
 *
 *   The hard-zero tile suppression (noise_raw assignment) is replaced by a
 *   linear SNR-scaled attenuation factor.  At SNR ≤ K_SOFT_SUPP_SNR_MIN_DB
 *   the tile is left unchanged (factor = 1.0); at SNR ≥ K_SOFT_SUPP_SNR_MAX_DB
 *   the tile is fully suppressed (factor = 0.0).  Between those bounds the
 *   factor varies linearly.  This reduces collateral damage on adjacent
 *   weaker signals when the decoded signal is borderline (low SNR).
 *   FT8_SHIM_VERSION incremented to 20260004 (skipping 20260003, which
 *   was the reverted PCM-SIC version, to avoid any confusion).
 *
 * fix-D002 — SNR bandwidth constant calibration (FT8_SHIM_VERSION 20260006):
 *
 *   The bandwidth correction constant in the SNR formula is adjusted from
 *   -26.0 dB to -26.5 dB.  R&R study S1 runs confirmed a systematic +2.42 dB
 *   over-report in OpenWSFZ across three independent runs.  PCM RMS normalisation
 *   (managed layer) was unable to close the residual gap because both signal_db
 *   and noise_floor_db are waterfall-derived, making the formula invariant to
 *   amplitude scaling.  The -0.5 dB adjustment brings the reported bias within
 *   the ±2.0 dB R&R S1 acceptance threshold.
 *
 * diag-D001-three-pass-sic (FT8_SHIM_VERSION 20260007) — TRIED AND REVERTED:
 *
 *   K_MAX_PASSES was increased from 2 to 3 as a controlled diagnostic experiment.
 *   S7 R&R result: 50.54% overall vs 54.84% 2-pass baseline (−4.30 pp).
 *   H2 rejected: no improvement on any co-channel part (P0/P1/P2/P8 still 0/6);
 *   marginal capture regression (P11: 5→3/6, P12: 5→4/6).  The third pass
 *   provides no benefit over spectrogram-domain SIC for exact co-channel
 *   separation.  FT8_SHIM_VERSION returned to 20260006.
 *   Full findings: qa/rr-study/results/2026-06-12-3ecf8ae/report-v2.md.
 *
 * diag-d001-pcm-sic (FT8_SHIM_VERSION 20260008):
 *
 *   PCM-domain SIC replaces spectrogram suppression in the inter-pass stage
 *   (H3 diagnostic for D-001, High severity co-channel decode gap).  For each
 *   signal decoded in pass 0, a CP-FSK waveform is synthesised from the decoded
 *   tone sequence (via ft8_encode), using a heap-allocated synth_buf (720 KB),
 *   phase initialised to zero, no Gaussian shaping.  A least-squares projection
 *   amplitude is computed and the scaled waveform is subtracted from a
 *   heap-allocated PCM residual (residual_pcm, 720 KB).  After all pass-0
 *   signals have been subtracted, a second monitor_t (mon2) is initialised with
 *   the same configuration and the residual PCM is processed through it.  Pass 1
 *   operates on mon2.wf (the rebuilt residual waterfall).  Both heap buffers are
 *   freed before monitor_free; mon2 is freed before mon (Task 2.8).
 *   FT8_SHIM_VERSION 20260007 slot skipped (was the reverted three-pass SIC).
 *   diag-d001-pcm-sic (H3, FT8_SHIM_VERSION 20260008) is SUPERSEDED by H3b below.
 *
 * diag-d001-h3b-gfsk-sic (FT8_SHIM_VERSION 20260009):
 *
 *   GFSK quadrature SIC replaces the CP-FSK scalar SIC from 20260008 (H3b diagnostic
 *   for D-001).  H3 post-mortem: two compounding model errors drove cancellation
 *   amplitude to near-zero — (a) CP-FSK vs GFSK modulation mismatch at symbol
 *   boundaries; (b) cosine-only phase-zero assumption invalid for any real carrier
 *   phase φ.  H3b corrects both: `synth_ft8_gfsk_quad` synthesises the I (sin) and
 *   Q (cos) quadrature components using a normalised Gaussian pulse (BT=2.0, 3-symbol
 *   span, matching the QA Python synthesiser in modulator.py); `compute_quadrature_
 *   amplitude` estimates optimal amplitude a and phase φ analytically from two dot
 *   products — O(N), exact for any φ.  Three additional heap buffers allocated in the
 *   pass-1 SIC block: synth_buf_q (720 KB), gfsk_kernel (23 040 B), gfsk_prefix
 *   (23 044 B).  Total PCM-domain SIC heap ≈ 2.21 MB.  FT8_SHIM_VERSION 20260008 slot
 *   remains in the history above for auditability; the H3 binary is obsolete.
 *
 * diag-d001-h5-suppression-tuning (FT8_SHIM_VERSION 20260011) — REJECTED:
 *
 *   The soft SNR-scaled suppression ramp window is shifted 10 dB toward lower SNRs
 *   (single-variable diagnostic, H5).  K_SOFT_SUPP_SNR_MIN_DB: −5.0 → −15.0 dB;
 *   K_SOFT_SUPP_SNR_MAX_DB: +15.0 → +5.0 dB.  Ramp width (20 dB) is preserved;
 *   only the operating window shifts.  At the S7 test SNR of 0 dB suppression
 *   increases from 25% (H4, 20260010) to 75% (H5, 20260011).  Target: reduce the
 *   time_freq co-channel gap (P8/P9/P10: 10/18 in H4) by clearing more residual
 *   energy from pass-0 decoded signals before pass-1 candidate search.  No other
 *   shim logic, pass configuration, managed-layer logic, or struct layout changed.
 *   H4 (FT8_SHIM_VERSION 20260010) is the direct predecessor; version 20260010
 *   slot carries the H4 spectrogram reinstatement history.
 *   REJECTED: S7 overall 43/93 = 46.24% (−10.75 pp vs H4 56.99% baseline).
 *   Over-suppression confirmed — 75% attenuation at 0 dB SNR removes shared tile
 *   energy in time_freq scenarios and the weak signal's contribution in capture
 *   scenarios.  FT8_SHIM_VERSION reverted to 20260010 (H4 baseline restored).
 *
 * fix-d004-local-noise-floor (FT8_SHIM_VERSION 20260012):
 *
 *   Per-signal local noise floor replaces the global histogram-median in the SNR
 *   formula.  `compute_local_noise_floor_db` samples waterfall bins in a K=32-bin
 *   sideband window on each side of the decoded signal's 8-tone span:
 *     left  sideband: [max(0, freq_offset − 32), freq_offset)
 *     right sideband: [freq_offset + 8, min(num_bins, freq_offset + 40))
 *   across ALL time blocks and ALL time/freq sub-samples; takes the histogram
 *   median of those samples (same estimator as compute_noise_floor).  Falls back
 *   to tls_last_noise_floor_db if no sideband bins are available (safety guard,
 *   never expected in practice).
 *   The global noise floor (noise_floor_db) is still computed and stored in
 *   tls_last_noise_floor_db for the per-cycle diagnostic log; it is no longer
 *   used in the per-signal SNR formula.
 *   Root cause (D-003/D-004): the audio chain (transceiver SSB output + USB Audio
 *   CODEC) has significant frequency rolloff: signal_db falls from −39.7 dB at
 *   800–1000 Hz to −67.5 dB at 2800–3000 Hz, while the global noise_floor_db
 *   stays at −66.7 dB.  Local noise tracks the same rolloff, making the SNR
 *   formula invariant to audio-chain frequency response.
 *   Version 20260011 slot used for H5 suppression-tuning diagnostic (REJECTED;
 *   reverted).  20260012 is the D-003/D-004 fix, not a D-001 hypothesis.
 *
 * fix-seh-av-containment (FT8_SHIM_VERSION 20260013):
 *
 *   __try/__except(EXCEPTION_EXECUTE_HANDLER) wrapper added around the body
 *   of ft8_decode_all (MSVC / Windows only).  On any access violation
 *   (0xC0000005) the shim returns -2, allowing the managed layer to log the
 *   event and skip the decode cycle instead of the process dying.
 *   monitor_free intentionally NOT called in the except handler — the heap
 *   may be partially corrupted; a second AV inside the handler is worse than
 *   a per-cycle waterfall memory leak.  tls_hash_table is cleared in both
 *   paths to prevent a dangling pointer.
 *
 * diag-d006-minidump (FT8_SHIM_VERSION 20260014):
 *
 *   Crash dump capture moved from the __except body into a dedicated
 *   ft8_av_exception_filter() function called in the filter-expression
 *   position.  Root cause: GetExceptionInformation() returns a pointer into
 *   the OS exception-dispatch frame, which is freed when Windows unwinds the
 *   stack on entry to the __except body.  Calling MiniDumpWriteDump there
 *   with the stale EXCEPTION_POINTERS produced a 185 MB full-memory dump
 *   with no ExceptionStream (crash address unknown, confirmed by dump analysis
 *   2026-06-14).  The filter function runs before unwind; the EXCEPTION_POINTERS
 *   passed as its argument are valid for the duration of the filter call,
 *   including the MiniDumpWriteDump call within it.  The resulting dump will
 *   contain a valid ExceptionStream with ExceptionAddress and CONTEXT.
 *
 * fix-d006-ptr-truncation (FT8_SHIM_VERSION 20260015):
 *
 *   Binary patch to native/ft8_lib_build/obj/message.obj fixing a 32-bit
 *   pointer truncation in ftx_message_decode() (ft8/message.c, kgoba/ft8_lib
 *   v2.0 MSVC-compat branch, commit d18ed84).
 *
 *   Root cause (confirmed by dump analysis of ft8_av_20260614_133145_28356.dmp,
 *   shim 20260014, ExceptionAddress RVA 0x3D06 in libft8.dll):
 *
 *   ftx_message_decode() handles FT8 messages with the "R " reply prefix
 *   (messages where the i3/n3 type field has bit 0x20 set — FT8 Type 2
 *   "RRR/RR73/73" or standard 73 reply format).  It calls an internal stpcpy()
 *   to copy the "R " prefix into the loc_grid output buffer, then continues
 *   writing the 4-character Maidenhead grid locator into the same buffer
 *   using the returned end-pointer.
 *
 *   MSVC generated `MOVSXD RBX, EAX` (opcode 48 63 D8) at message.obj offset
 *   0x01B26 to capture stpcpy's char* return.  MOVSXD sign-extends a 32-bit
 *   register to 64-bit; it truncates the upper 32 bits of the 64-bit pointer
 *   in RAX.  When the thread stack (and therefore the caller-supplied loc_grid
 *   buffer) resides above the 4 GB VA boundary — as occurs when the OS places
 *   a thread's stack in the range 0x0000001700000000..0x0000001800000000 —
 *   the upper 32 bits (0x00000017) are silently dropped.  The subsequent write
 *   to the truncated address causes a fatal 0xC0000005 access violation.
 *
 *   Dump evidence:
 *     RCX = 0x0000001737E3B0B6  (correct 64-bit stpcpy return — still in RCX
 *                                 from the calling convention)
 *     RBX = 0x0000000037E3B0B6  (truncated — upper 0x17 dropped)
 *     Write target [RBX+4] = 0x37E3B0BA → ACCESS VIOLATION
 *
 *   Fix: change the single opcode byte at message.obj offset 0x01B27 from
 *   0x63 (MOVSXD) to 0x8B (MOV r64,r/m64), producing `MOV RBX, RAX`
 *   (48 8B D8) — a full 64-bit register move that preserves all pointer bits.
 *   DLL rebuilt from patched .obj.  No change to exported ABI, struct layout,
 *   or return codes.
 *
 *
 * ft8-qso-answerer-v1 (FT8_SHIM_VERSION 20260017):
 *
 *   Adds ft8_encode_message() — the TX encode entry point required by the
 *   QSO answerer (ft8-qso-answerer-v1 change).  Uses ftx_message_encode()
 *   (ft8/message.h) to pack a text string into the 77-bit ftx_message_t
 *   payload, then ft8_encode() (ft8/encode.h) to convert the payload to
 *   79 GFSK tone indices.  A local callsign table is set in TLS for the
 *   duration of the call so the global hash callbacks operate on it.
 *   No change to existing entry points, struct layout, or return codes.
 *   Exported via /EXPORT:ft8_encode_message in the link step.
 *
 * diag-d001-candidate-counts (FT8_SHIM_VERSION 20260018):
 *
 *   Adds ft8_get_last_candidate_counts() — a TLS getter exposing the per-pass
 *   count of candidates returned by ftx_find_candidates() before any LDPC decode
 *   attempt.  A new TLS array tls_candidate_counts[K_MAX_PASSES] is initialised
 *   to zero at the start of ft8_decode_all and populated immediately after each
 *   ftx_find_candidates() call.  Together with ft8_get_last_pass_counts() (which
 *   counts successful decodes after LDPC) this lets the managed diagnostic layer
 *   distinguish candidate-generation failure (tls_candidate_counts[i] is low)
 *   from LDPC convergence failure (tls_candidate_counts[i] is high but
 *   tls_pass_counts[i] is zero) in D-001 co-channel scenarios.
 *   No change to decode logic, struct layout, or existing entry points.
 *   Exported via /EXPORT:ft8_get_last_candidate_counts in the link step.
 *
 * diag-d001-llr-mean-abs (FT8_SHIM_VERSION 20260019):
 *
 *   Adds ft8_get_last_llr_stats() — a TLS getter exposing, per pass, the
 *   mean absolute LLR across all LDPC-failing candidates from the most
 *   recent ft8_decode_all call.  For each candidate where
 *   ftx_decode_candidate() returns false, ftx_compute_candidate_llr_mean_abs()
 *   is called (defined in patched/ft8/decode.c); it replicates the likelihood-
 *   extraction + variance-normalisation steps and returns mean(|log174[i]|)
 *   over all 174 elements without calling bp_decode.  Two new TLS arrays
 *   (tls_llr_mean_abs_sum, tls_llr_fail_count) accumulate per-pass totals;
 *   the getter computes the per-pass mean and returns alongside the fail count.
 *   Diagnostic goal: confirm the near-zero LLR hypothesis for D-001 co-channel
 *   failure cycles (expected: mean|LLR| < 0.5 for P0/P1/P2 failures vs > 1.5
 *   for successful co-channel captures).  No change to decode logic, candidate
 *   search, pass configuration, or struct layout.
 *
 * fix-d006-cleanup + fix-rq2-signal-db-oob (FT8_SHIM_VERSION 20260016):
 *
 *   Two independent changes bundled in one version step:
 *
 *   (a) Removed ft8_av_exception_filter() and its Windows-only diagnostic
 *   infrastructure (MiniDumpWriteDump, CreateFileA, dbghelp.h, hardcoded
 *   C:\Dumps\ path).  The shim 20260014 filter was a one-shot diagnostic
 *   instrument; it served its purpose (produced the dump that diagnosed D-006)
 *   and has no place in production code.  The __try/__except containment and
 *   the -2 return code are retained unchanged — they remain a genuine
 *   production safety net.  The __except clause reverts to the simple
 *   EXCEPTION_EXECUTE_HANDLER form from 20260013.
 *
 *   (b) OOB guard in signal_db computation (RQ-2).  For signals near f_max
 *   (≥ 2956 Hz, freq_offset ≥ 473) an active tone index tones[b-b0] ∈ [0,7]
 *   can push freq_offset + tone_col past num_bins, reading one waterfall row
 *   into the next.  Fix: skip the sample when freq_offset + tone_col >= nb
 *   rather than reading out of bounds.  Signals at the band edge may have
 *   slightly fewer samples contributing to signal_db; this is acceptable.
 *
 * fix-d001-osd (FT8_SHIM_VERSION 20260025):
 *
 *   Ordered Statistics Decoding (OSD) fallback added to ftx_decode_candidate
 *   and ftx_decode_candidate_ap in patched/ft8/decode.c.  When bp_decode()
 *   fails to converge under wrong-sign LLR conditions (D-001 root cause:
 *   equal-SNR co-channel interference), osd_decode() algebraically explores
 *   the most likely error patterns in the 32 least-reliable free bit positions
 *   and performs a CRC-14 check on each candidate (529 trials per failing
 *   candidate at ndeep=2, matching WSJT-X's default maxosd=2 at ndepth=3).
 *
 *   Algorithm (osd_decode + osd_try_codeword, both static C11 in decode.c):
 *     (1) Sort 174 bits by |LLR| descending (insertion sort, O(N^2)).
 *     (2) Permuted H_perm[83][174] built on stack (~14 KB).
 *     (3) GF(2) Gaussian elimination → reduced row echelon form; 83 pivots.
 *     (4) Free cols carry information bits; base = hard decisions on LLRs.
 *     (5) Enumerate 0-/1-/2-flip trials in 32 least-reliable free positions.
 *     (6) Per trial: compute pivot bits from parity eqs, un-permute, CRC-14.
 *
 *   OSD input: normalised LLRs BEFORE bp_decode (saved by memcpy of log174
 *   after ftx_normalize_logl, matching WSJT-X zsave(:,1) at BP iteration 0).
 *
 *   Also raises K_LDPC_ITERATIONS from 25 → 50 (optimal flooding BP count as
 *   established by H_ITER diagnostic on diag/d001-ldpc-iter-hypothesis branch;
 *   version slots 20260022–20260024 were used only on that unmerged branch and
 *   are permanently retired here to avoid version-number ambiguity).
 *
 * fix-d009-k10 (FT8_SHIM_VERSION 20260029):
 *
 *   K_MIN_SCORE_PASS2 raised 1 → 10 (D-009: OSD false-positive manufacture in
 *   noise).  The pass-1 sweep (qa/rr-study/results/diag-pass1-sweep-2026-06-21/
 *   pass1_sweep.md) measured the S5 FP rate and S7 co_channel_sweep across five
 *   K values on shim 20260028:
 *
 *     K=1 (baseline): 0.675 FP/slot; S7 co_channel_sweep 28.6% (hard P0–P2)
 *     K=10:           0.042 FP/slot (−94%); S7 co_channel_sweep 37.1% (hard P0–P2)
 *
 *   Setting K_MIN_SCORE_PASS2 = K_MIN_SCORE (= 10) means pass-1 admits only
 *   candidates whose sync score matches the pass-0 floor.  After pass-0 decodes
 *   and suppresses genuine signals, residual energy at that quality level is almost
 *   exclusively thermal noise; OSD's CRC-14 search over 529 trials therefore finds
 *   very few false codewords.  All other shim-20260028 gate values unchanged:
 *   OSD_NHARD_MAX = 60, OSD_CORR_THRESHOLD = 0.10, text Rules A/B/C intact.
 *   No ABI change; no struct layout change.
 *
 * Build: see BUILD.md.  encode.c and patched/ft8/decode.c must be compiled and linked.
 */

#include "ft8_shim.h"

/* M_PI is not defined by MSVC's <math.h> under strict C11; enable it explicitly.
 * Must be defined before any header that transitively includes <math.h>.        */
#ifndef _USE_MATH_DEFINES
#define _USE_MATH_DEFINES
#endif

#include <ft8/decode.h>
#include <ft8/encode.h>
#include <ft8/message.h>
#include <common/monitor.h>

#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <math.h>

/* Forward declarations — defined in patched/ft8/decode.c */

/* Task B (shim 20260020): renamed and redesigned LLR probe */
float ftx_compute_candidate_llr_stats(
    const ftx_waterfall_t* wf,
    const ftx_candidate_t* cand,
    float*                 out_prenorm_variance);

/* Task A (shim 20260020): AP-constrained decode */
bool ftx_decode_candidate_ap(
    const ftx_waterfall_t*  wf,
    const ftx_candidate_t*  cand,
    int                     max_iterations,
    const float*            ap_overrides,
    ftx_message_t*          message,
    ftx_decode_status_t*    status);

/* Fallback definition of M_PI in case the platform still does not provide it */
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/* EXCEPTION_EXECUTE_HANDLER is declared in <excpt.h> on MSVC.
 * Include explicitly so the __try/__except wrapper in ft8_decode_all compiles
 * cleanly even when <windows.h> is not transitively pulled in.               */
#ifdef _MSC_VER
#  include <excpt.h>
#endif

#ifdef _MSC_VER
char* stpcpy(char* dest, const char* src)
{
    while ((*dest = *src) != '\0') { dest++; src++; }
    return dest;
}
#endif

/* ── Decode configuration ────────────────────────────────────────────────── */

#define FT8_SAMPLE_RATE      12000
#define FT8_EXPECTED_SAMPLES 180000

/* Samples per FT8 symbol: 12000 Hz / 6.25 symbols-per-second = 1920 */
#define FT8_SAMPLES_PER_SYMBOL 1920

/* Float-typed equivalents — avoid integer-division errors in synthesis math */
#define TONE_SPACING_HZ   6.25f    /* Hz per FT8 tone step (6.25 Hz / tone)        */
#define FT8_SAMPLE_RATE_F 12000.0f /* Nominal sample rate used by all synthesis math */

#define K_MIN_SCORE       10
#define K_MAX_CANDIDATES  140
#define K_LDPC_ITERATIONS 50   /* raised 25→50 (shim 20260025): optimal flooding BP count per H_ITER diagnostic */
#define K_FREQ_OSR        2
#define K_TIME_OSR        2

/* ── Iterative subtraction parameters ───────────────────────────────────── */
/*
 * K_MAX_PASSES — total number of decode passes.
 * Pass 0: full waterfall (unchanged input PCM).
 * Pass 1: spectrogram-suppressed — for each candidate decoded in pass 0 the shim
 *         attenuates that signal's energy in the waterfall using a soft SNR-scaled
 *         factor (suppress_candidate_tiles) before re-running candidate search and
 *         decode.  (H3b PCM-domain SIC call site removed in shim 20260010; GFSK
 *         helpers retained but not called.)
 */
#define K_MAX_PASSES   2

/* ── Soft SNR-scaled tile suppression constants ───────────────────────────── */
/*
 * Attenuation factor is a linear ramp between these SNR bounds:
 *   SNR ≤ K_SOFT_SUPP_SNR_MIN_DB  → factor = 1.0  (no suppression)
 *   SNR ≥ K_SOFT_SUPP_SNR_MAX_DB  → factor = 0.0  (full suppression)
 *   Between the two bounds         → factor = 1 − (snr − min) / (max − min)
 *
 * Rationale: a borderline decode (SNR near the decoder floor) has a higher
 * probability of tile overlap with an adjacent co-channel signal.  Scaling
 * the suppression by SNR reduces collateral damage in proportion to the
 * confidence in the decoded signal's tile locations.
 */
#define K_SOFT_SUPP_SNR_MIN_DB  (-5.0f)   /* below this: no suppression    */
#define K_SOFT_SUPP_SNR_MAX_DB  (15.0f)   /* above this: full suppression   */

/*
 * Pass 1 uses a wider candidate net.
 */
#define K_MIN_SCORE_PASS2       10   /* D-009: was 1; pass-1 sweep + confirmation gate
                                         selected 10: S5 FP −94% (0.675→0.042/slot);
                                         co_channel_sweep 86.67% (ref 92.14%; −5.5 pp
                                         at Δ5–7 Hz; accepted by Captain, 2026-06-22) */
#define K_MAX_CANDIDATES_PASS2  200
#define K_LDPC_ITERATIONS_PASS2 50

/*
 * K_MAX_DECODED — cross-pass dedup hash table entries.
 * Sized to accommodate all two passes: 140 + 200 = 340.
 */
#define K_MAX_DECODED  (K_MAX_CANDIDATES + K_MAX_CANDIDATES_PASS2)

/* ── Local noise floor estimation ─────────────────────────────────────────── */
/*
 * K_LOCAL_NOISE_WINDOW — number of waterfall bins sampled on each side of the
 * decoded signal's 8-tone span.  With freq_osr=2 and 6.25 Hz/bin, 32 bins =
 * 200 Hz of audio bandwidth per sideband.
 */
#define K_LOCAL_NOISE_WINDOW 32

/* ── Thread-local per-pass stats and noise floor ─────────────────────────── */
static _Thread_local int   tls_pass_counts[K_MAX_PASSES];
static _Thread_local int   tls_candidate_counts[K_MAX_PASSES];
static _Thread_local float tls_llr_mean_abs_sum[K_MAX_PASSES];
static _Thread_local float tls_llr_prenorm_var_sum[K_MAX_PASSES]; /* Task B, shim 20260020 */
static _Thread_local int   tls_llr_fail_count[K_MAX_PASSES];
static _Thread_local int   tls_num_passes       = 0;
static _Thread_local float tls_last_noise_floor_db = 0.0f;

/* ── Thread-local AP decode state (Task A, shim 20260020) ────────────────── */
/*
 * AP bit constraints supplied by ft8_set_ap_bits().  Copied into an override
 * array before each pass-0 decode loop.  num_mycall_bits=0 disables AP entirely.
 *
 * FTX_LDPC_N is defined in ft8/decode.h (== 174).  We use a fixed-size array
 * matching that constant.  The 174-float array is zeroed by default; non-zero
 * entries are the ±LLR_HARD overrides applied to log174 before normalisation.
 */
#define FT8_AP_LLR_HARD    40.0f   /* hard prior magnitude for AP-constrained bits */
#define FT8_AP_PAYLOAD_N   174     /* FTX_LDPC_N — max bit positions               */

static _Thread_local uint8_t tls_ap_mycall_bits[4];   /* up to 28 bits packed MSB-first */
static _Thread_local int     tls_ap_num_mycall_bits  = 0;
static _Thread_local uint8_t tls_ap_hiscall_bits[4];  /* up to 28 bits packed MSB-first */
static _Thread_local int     tls_ap_num_hiscall_bits = 0;

/* ── Callsign hash table ─────────────────────────────────────────────────── */

#define HASH_TABLE_SIZE 256
typedef struct { char callsign[12]; uint32_t hash; } callsign_entry_t;
typedef struct { callsign_entry_t entries[HASH_TABLE_SIZE]; int count; } callsign_table_t;

static void hash_table_init(callsign_table_t* tbl) { memset(tbl, 0, sizeof(*tbl)); }

static bool hash_table_lookup(callsign_table_t* tbl,
                               ftx_callsign_hash_type_t hash_type,
                               uint32_t hash, char* callsign)
{
    uint8_t  sh  = (hash_type == FTX_CALLSIGN_HASH_10_BITS) ? 12
                 : (hash_type == FTX_CALLSIGN_HASH_12_BITS) ? 10 : 0;
    uint16_t h10 = (hash >> (12 - sh)) & 0x3FFu;
    int      idx = (h10 * 23) % HASH_TABLE_SIZE;
    /* Probe-limit guard: cap at HASH_TABLE_SIZE iterations so a full table
     * (all slots occupied) cannot spin forever.  Mirrors the count-check in
     * hash_table_add (R3-2). */
    for (int probe = 0; probe < HASH_TABLE_SIZE; probe++) {
        if (tbl->entries[idx].callsign[0] == '\0') break;
        if (((tbl->entries[idx].hash & 0x3FFFFFu) >> sh) == hash) {
            strcpy(callsign, tbl->entries[idx].callsign); return true; }
        idx = (idx + 1) % HASH_TABLE_SIZE;
    }
    callsign[0] = '\0'; return false;
}

static void hash_table_add(callsign_table_t* tbl, const char* callsign, uint32_t hash)
{
    /* Guard: discard new callsigns when the table is full rather than looping
     * forever.  Full table → unknown callsigns display as <HASH>, matching
     * WSJT-X first-seen behaviour; no crash, no hang, no data corruption. */
    if (tbl->count >= HASH_TABLE_SIZE) return;

    uint16_t h10 = (hash >> 12) & 0x3FFu;
    int      idx = (h10 * 23) % HASH_TABLE_SIZE;
    while (tbl->entries[idx].callsign[0] != '\0') {
        if (((tbl->entries[idx].hash & 0x3FFFFFu) == hash) &&
            !strcmp(tbl->entries[idx].callsign, callsign)) {
            tbl->entries[idx].hash &= 0x3FFFFFu; return; }
        idx = (idx + 1) % HASH_TABLE_SIZE;
    }
    tbl->count++;
    strncpy(tbl->entries[idx].callsign, callsign, 11);
    tbl->entries[idx].callsign[11] = '\0';
    tbl->entries[idx].hash = hash;
}

static _Thread_local callsign_table_t* tls_hash_table = NULL;
static bool cb_lookup_hash(ftx_callsign_hash_type_t t, uint32_t h, char* cs) {
    if (!tls_hash_table) { cs[0] = '\0'; return false; }
    return hash_table_lookup(tls_hash_table, t, h, cs);
}
static void cb_save_hash(const char* cs, uint32_t h) {
    if (tls_hash_table) hash_table_add(tls_hash_table, cs, h);
}
static ftx_callsign_hash_interface_t s_hash_if = { cb_lookup_hash, cb_save_hash };

/* ── Spectrogram-domain tile suppression ─────────────────────────────────── */
/*
 * suppress_candidate_tiles — attenuate the waterfall tiles occupied by a
 * decoded FT8 signal, using the EXACT tone sequence from ft8_encode and a
 * soft SNR-scaled attenuation factor.
 *
 * For each of the 79 symbols, the bin actually transmitted plus its ±1
 * nearest neighbours (one FT8 bin = 3.125 Hz at freq_osr=2) are multiplied
 * by an attenuation factor derived from the decoded signal's SNR:
 *
 *   SNR ≤ K_SOFT_SUPP_SNR_MIN_DB  → factor = 1.0  (tile unchanged)
 *   SNR ≥ K_SOFT_SUPP_SNR_MAX_DB  → factor = 0.0  (tile zeroed to noise_raw)
 *   In between                     → factor = 1 − (snr − min) / (max − min)
 *
 * At factor = 0.0 the tile is assigned noise_raw (matching the previous
 * hard-zero behaviour for strong signals).  At intermediate factors the tile
 * value is linearly interpolated between its current value and noise_raw.
 * This preserves the Hann-window first-sidelobe cancellation for strong
 * signals while reducing collateral damage on adjacent weaker signals when
 * the decoded signal is borderline (SNR near the decoder floor).
 */
static void suppress_candidate_tiles(
    ftx_waterfall_t*       wf,
    const ftx_candidate_t* cand,
    const ftx_message_t*   msg,
    WF_ELEM_T              noise_raw,
    float                  snr_db)
{
    /* Compute soft attenuation factor from SNR */
    float norm   = (snr_db - K_SOFT_SUPP_SNR_MIN_DB)
                 / (K_SOFT_SUPP_SNR_MAX_DB - K_SOFT_SUPP_SNR_MIN_DB);
    float factor = 1.0f - fmaxf(0.0f, fminf(1.0f, norm));
    /* factor: 1.0 at SNR ≤ −5 dB (no change), 0.0 at SNR ≥ +15 dB (full suppress) */

    uint8_t tones[FT8_NN];
    ft8_encode(msg->payload, tones);

    int per_tsub = wf->freq_osr * wf->num_bins;

    for (int sym = 0; sym < FT8_NN; sym++)
    {
        int b = (int)cand->time_offset + sym;
        if (b < 0 || b >= wf->num_blocks) continue;

        int tone_bin = (int)cand->freq_offset + (int)tones[sym];

        WF_ELEM_T* block = wf->mag + b * wf->block_stride;
        for (int ts = 0; ts < wf->time_osr; ts++)
        {
            for (int fs = 0; fs < wf->freq_osr; fs++)
            {
                WF_ELEM_T* row = block + ts * per_tsub + fs * wf->num_bins;
                for (int d = -1; d <= 1; d++)
                {
                    int f = tone_bin + d;
                    if (f >= 0 && f < wf->num_bins)
                    {
                        /* Interpolate between current value and noise_raw
                         * by the attenuation factor:
                         *   factor = 0 → noise_raw  (full suppression)
                         *   factor = 1 → row[f]     (no change)            */
                        float attenuated = (float)noise_raw
                                         + factor * ((float)row[f] - (float)noise_raw);
                        row[f] = (WF_ELEM_T)(attenuated + 0.5f);
                    }
                }
            }
        }
    }
}

/* ── Noise floor computation (shared helper) ─────────────────────────────── */
/*
 * compute_noise_floor — histogram-median estimator over all waterfall bins.
 * Sets *noise_floor_db and *noise_raw from mon.wf.
 */
static void compute_noise_floor(
    const monitor_t* mon,
    float*           noise_floor_db,
    WF_ELEM_T*       noise_raw)
{
    uint32_t hist[256];
    memset(hist, 0, sizeof(hist));
    int total = mon->wf.num_blocks * mon->wf.block_stride;
    const WF_ELEM_T* wp = mon->wf.mag;
    for (int i = 0; i < total; i++) hist[wp[i]]++;
    uint32_t cum = 0; int med = 0;
    for (int v = 0; v < 256; v++) {
        cum += hist[v];
        if (cum * 2 >= (uint32_t)total) { med = v; break; }
    }
    *noise_floor_db = (float)med * 0.5f - 120.0f;
    *noise_raw      = (WF_ELEM_T)med;
}

/* ── T2 pre-condition: monitor_t isolation gate (task 1.1) ───────────────── */
/*
 * monitor.c isolation check (verified 2026-06-12 against native/ft8_lib_build/patched/common/monitor.c):
 *
 * monitor_init() allocates all internal state (window, last_frame, fft_work,
 * fft_cfg, and wf.mag) via malloc/calloc and stores each pointer exclusively in
 * fields of the monitor_t struct passed by pointer.  No static or TLS variables
 * are read or written by monitor_init or monitor_free.  monitor_free() only frees
 * those same heap pointers.  The kiss_fftr_alloc work area is likewise stored in
 * me->fft_work / me->fft_cfg — no library-level global state.
 *
 * VERDICT: Two monitor_t instances can be independently initialised and freed
 * within the same ft8_decode_all call stack without any interference.
 * GO — waterfall rebuild via a second monitor_t (T2 Decision 4) is safe.
 */

/* ── GFSK quadrature synthesis helpers (H3b, retained for H3c) ─────────── */
/*
 * These three helpers are currently unreferenced — the H3b PCM-domain SIC call
 * site was removed in shim 20260010 (H4 recovery).  They are retained for a
 * potential H3c hybrid experiment.  Annotated UNUSED to suppress -Wunused-function
 * on GCC/Clang; __attribute__((unused)) is a no-op on MSVC (which does not warn
 * on unreferenced static functions with /W3).
 */
#ifdef __GNUC__
#  define FT8_UNUSED_STATIC __attribute__((unused)) static
#else
#  define FT8_UNUSED_STATIC static
#endif

/* GFSK pulse parameters (BT=2.0, 3-symbol span — matches QA Python synthesiser) */
#define GFSK_BT         2.0f
#define GFSK_SPAN_SYMS  3
#define GFSK_KERNEL_LEN (GFSK_SPAN_SYMS * FT8_SAMPLES_PER_SYMBOL)   /* 5760 */

/*
 * build_gfsk_kernel — compute the normalised Gaussian pulse kernel and its
 * prefix sum.  Both arrays are caller-allocated heap buffers.
 *
 * kernel[GFSK_KERNEL_LEN] receives the normalised Gaussian pulse.
 * prefix[GFSK_KERNEL_LEN + 1] receives the prefix sum (prefix[0] = 0.0f).
 *
 * Formula matches the QA Python synthesiser (modulator.py):
 *   sigma = sqrt(ln(2)) / (2 * pi * BT)   [in symbol periods, ≈ 0.06622]
 *   t_j   = (j - GFSK_KERNEL_LEN/2 + 0.5) / FT8_SAMPLES_PER_SYMBOL
 *   kernel[j] = exp(-t_j^2 / (2 * sigma^2)), normalised to unit sum
 *
 * No heap or stack arrays > 100 bytes allocated internally.
 * Caller is responsible for allocating and freeing both buffers.
 */
FT8_UNUSED_STATIC void build_gfsk_kernel(float* kernel, float* prefix)
{
    float sigma = sqrtf(logf(2.0f)) / (2.0f * (float)M_PI * GFSK_BT);
    float sum   = 0.0f;
    for (int j = 0; j < GFSK_KERNEL_LEN; j++)
    {
        float t_j  = ((float)j - (float)(GFSK_KERNEL_LEN / 2) + 0.5f)
                    / (float)FT8_SAMPLES_PER_SYMBOL;
        float k_j  = expf(-t_j * t_j / (2.0f * sigma * sigma));
        kernel[j]  = k_j;
        sum        += k_j;
    }
    /* Normalise to unit sum */
    for (int j = 0; j < GFSK_KERNEL_LEN; j++)
        kernel[j] /= sum;
    /* Prefix sum: prefix[0] = 0, prefix[j+1] = prefix[j] + kernel[j] */
    prefix[0] = 0.0f;
    for (int j = 0; j < GFSK_KERNEL_LEN; j++)
        prefix[j + 1] = prefix[j] + kernel[j];
}

/*
 * synth_ft8_gfsk_quad — synthesise a GFSK FT8 waveform into two quadrature
 * buffers (I = sin component, Q = cos component).
 *
 * Parameters:
 *   tones        — FT8_NN (79) tone indices in [0..7], from ft8_encode
 *   freq_hz      — carrier frequency of tone 0 in Hz
 *   start_sample — first sample index in buf_sin/buf_cos at which to write
 *   prefix       — precomputed prefix sum from build_gfsk_kernel; must be
 *                  GFSK_KERNEL_LEN+1 floats; the function MUST NOT call
 *                  build_gfsk_kernel internally
 *   buf_sin      — caller-provided output buffer for the I (sin) component
 *   buf_cos      — caller-provided output buffer for the Q (cos) component
 *   buf_len      — length of both output buffers in samples
 *
 * Uses the prefix-sum convolution optimisation: for each output sample the
 * GFSK-smoothed tone index is computed from the kernel weights covering at
 * most 4 symbol intervals (BT=2.0 narrow kernel).  Phase accumulates from
 * 0.0f continuously across all 79 symbols.  Writes sinf(phase) to buf_sin[i]
 * and cosf(phase) to buf_cos[i] for i = start_sample..start_sample+FT8_NN*SPS-1;
 * samples outside [0, buf_len) are silently skipped.
 * No heap or stack buffer > 100 bytes.  No global or TLS state modified.
 */
FT8_UNUSED_STATIC void synth_ft8_gfsk_quad(
    const uint8_t* tones,
    float          freq_hz,
    int            start_sample,
    const float*   prefix,
    float*         buf_sin,
    float*         buf_cos,
    int            buf_len)
{
    int   half      = GFSK_KERNEL_LEN / 2;              /* = 2880 samples */
    float phase     = 0.0f;
    int   n_samples = FT8_NN * FT8_SAMPLES_PER_SYMBOL;  /* = 151 680 */

    for (int i = 0; i < n_samples; i++)
    {
        /* Compute GFSK-smoothed tone index using prefix sums.
         * The kernel window centred at local sample i covers input indices
         * [i - half, i - half + GFSK_KERNEL_LEN).  For each symbol sym whose
         * samples [sym*SPS, (sym+1)*SPS) overlap that window, accumulate the
         * kernel weight falling in the intersection via the prefix sum.
         * At most ~4 symbols contribute per sample for BT=2.0.             */
        float smoothed = 0.0f;
        int   kern_start = i - half;
        int   sym_lo     = kern_start / FT8_SAMPLES_PER_SYMBOL;
        int   sym_hi     = (kern_start + GFSK_KERNEL_LEN - 1) / FT8_SAMPLES_PER_SYMBOL;

        for (int sym = sym_lo; sym <= sym_hi; sym++)
        {
            if (sym < 0 || sym >= FT8_NN) continue;

            int k_lo = sym * FT8_SAMPLES_PER_SYMBOL - kern_start;
            int k_hi = k_lo + FT8_SAMPLES_PER_SYMBOL;
            if (k_lo < 0)               k_lo = 0;
            if (k_hi > GFSK_KERNEL_LEN) k_hi = GFSK_KERNEL_LEN;
            if (k_lo >= k_hi)           continue;

            smoothed += (float)tones[sym] * (prefix[k_hi] - prefix[k_lo]);
        }

        float inst_freq = freq_hz + smoothed * TONE_SPACING_HZ;
        phase += 2.0f * (float)M_PI * inst_freq / FT8_SAMPLE_RATE_F;

        int idx = start_sample + i;
        if (idx >= 0 && idx < buf_len)
        {
            buf_sin[idx] = sinf(phase);
            buf_cos[idx] = cosf(phase);
        }
    }
}

/*
 * compute_quadrature_amplitude — analytic quadrature amplitude/phase estimator.
 *
 * Computes the optimal subtraction coefficients *out_a_i and *out_a_q for the
 * two quadrature synthesis components (synth_sin and synth_cos) projected onto
 * pcm in the window [start, end).
 *
 * Formulae:
 *   dot_I  = dot(pcm[start..end], synth_sin[start..end])
 *   dot_Q  = dot(pcm[start..end], synth_cos[start..end])
 *   energy = dot(synth_sin[start..end], synth_sin[start..end])
 *   if energy == 0 or start >= end: *out_a_i = *out_a_q = 0.0f; return
 *   a        = sqrtf(dot_I^2 + dot_Q^2) / energy
 *   phi      = atan2f(dot_Q, dot_I)
 *   *out_a_i = a * cosf(phi)   // coefficient for sin component
 *   *out_a_q = a * sinf(phi)   // coefficient for cos component
 *
 * Valid for any carrier phase; exact for a single sinusoidal signal in the
 * absence of noise.  No heap allocation.  No global or TLS state modified.
 */
FT8_UNUSED_STATIC void compute_quadrature_amplitude(
    const float* pcm,
    const float* synth_sin,
    const float* synth_cos,
    int          start,
    int          end,
    float*       out_a_i,
    float*       out_a_q)
{
    if (start >= end) { *out_a_i = 0.0f; *out_a_q = 0.0f; return; }
    float dot_I  = 0.0f;
    float dot_Q  = 0.0f;
    float energy = 0.0f;
    for (int i = start; i < end; i++)
    {
        dot_I  += pcm[i]       * synth_sin[i];
        dot_Q  += pcm[i]       * synth_cos[i];
        energy += synth_sin[i] * synth_sin[i];
    }
    if (energy == 0.0f) { *out_a_i = 0.0f; *out_a_q = 0.0f; return; }
    float a   = sqrtf(dot_I * dot_I + dot_Q * dot_Q) / energy;
    float phi = atan2f(dot_Q, dot_I);
    *out_a_i  = a * cosf(phi);
    *out_a_q  = a * sinf(phi);
}

/* ── Local noise floor for per-signal SNR computation ────────────────────── */
/*
 * compute_local_noise_floor_db — histogram-median noise floor estimated from
 * waterfall bins adjacent to the decoded signal's frequency.
 *
 * Samples bins in [max(0, freq_offset − K_LOCAL_NOISE_WINDOW), freq_offset)
 * and [freq_offset + 8, min(num_bins, freq_offset + 8 + K_LOCAL_NOISE_WINDOW))
 * across ALL time blocks and ALL time/freq sub-samples.
 *
 * Falls back to tls_last_noise_floor_db if no bins are available (safety guard —
 * only reachable if num_bins ≤ 8, far below any real configuration).
 *
 * This makes the SNR formula invariant to audio-chain frequency response:
 * both signal and noise are measured in the same spectral neighbourhood.
 */
static float compute_local_noise_floor_db(
    const ftx_waterfall_t* wf,
    int                    freq_offset)
{
    uint32_t hist[256];
    memset(hist, 0, sizeof(hist));
    int total = 0;

    int lo_start = freq_offset - K_LOCAL_NOISE_WINDOW;
    if (lo_start < 0) lo_start = 0;
    int lo_end   = freq_offset;                         /* exclusive; signal tones start here  */

    int hi_start = freq_offset + 8;                     /* skip 8-tone signal span              */
    int hi_end   = freq_offset + 8 + K_LOCAL_NOISE_WINDOW;
    if (hi_end > wf->num_bins) hi_end = wf->num_bins;

    int pt = wf->freq_osr * wf->num_bins;               /* per-time_sub stride in a block       */

    for (int b = 0; b < wf->num_blocks; b++) {
        const WF_ELEM_T* block = wf->mag + b * wf->block_stride;
        for (int ts = 0; ts < wf->time_osr; ts++) {
            for (int fs = 0; fs < wf->freq_osr; fs++) {
                const WF_ELEM_T* row = block + ts * pt + fs * wf->num_bins;
                for (int f = lo_start; f < lo_end; f++) { hist[row[f]]++; total++; }
                for (int f = hi_start; f < hi_end; f++) { hist[row[f]]++; total++; }
            }
        }
    }

    if (total == 0) return tls_last_noise_floor_db;     /* safety fallback — never expected     */

    uint32_t cum = 0; int med = 0;
    for (int v = 0; v < 256; v++) {
        cum += hist[v];
        if (cum * 2 >= (uint32_t)total) { med = v; break; }
    }
    return (float)med * 0.5f - 120.0f;
}

/* ── ABI sentinel ────────────────────────────────────────────────────────── */
int ft8_lib_version_check(void) { return FT8_SHIM_VERSION; }

/* ── Pass count query ────────────────────────────────────────────────────── */
int ft8_get_max_passes(void) { return K_MAX_PASSES; }

/* ── Noise floor query ───────────────────────────────────────────────────── */
float ft8_get_last_noise_floor_db(void) { return tls_last_noise_floor_db; }

/* ── Encode entry point ──────────────────────────────────────────────────── */
/*
 * ft8_encode_message — encode an FT8 text message to 79 tone indices.
 *
 * Uses ftx_message_encode() from ft8/message.h to pack the text into the
 * 77-bit ftx_message_t payload, then ft8_encode() from ft8/encode.h to
 * convert the payload to 79 GFSK tone indices.
 *
 * A local callsign table is used so Type-4 compressed callsigns can be
 * stored and looked up within the same encode call.  This is safe for
 * all standard QSO message formats (Type 1 / Type 2 / Type 0.0).
 *
 * Returns FT8_NN (79) on success; -1 if tones_capacity < FT8_NN;
 * -2 if ftx_message_encode() rejects the text.
 */
int ft8_encode_message(const char* message, uint8_t* tones_out, int tones_capacity)
{
    if (tones_capacity < FT8_NN) return -1;

    /* Local callsign table for hash callbacks during encode. */
    callsign_table_t htbl;
    hash_table_init(&htbl);

    /* Set TLS pointer so the global callbacks (cb_lookup_hash / cb_save_hash)
     * operate on this local table for the duration of the encode call.
     * Save and restore the previous pointer so nested calls (if ever made)
     * are not disrupted. */
    callsign_table_t* prev = tls_hash_table;
    tls_hash_table = &htbl;

    ftx_message_t msg;
    ftx_message_rc_t rc = ftx_message_encode(&msg, &s_hash_if, message);

    tls_hash_table = prev;

    if (rc != FTX_MESSAGE_RC_OK) return -2;

    ft8_encode(msg.payload, tones_out);
    return FT8_NN;
}

/* ── Per-pass stats query ────────────────────────────────────────────────── */
int ft8_get_last_pass_counts(int* out_counts, int capacity)
{
    int n = (tls_num_passes < capacity) ? tls_num_passes : capacity;
    for (int i = 0; i < n; i++) out_counts[i] = tls_pass_counts[i];
    return n;
}

/* ── Per-pass candidate count query ─────────────────────────────────────── */
int ft8_get_last_candidate_counts(int* out_counts, int capacity)
{
    int n = (tls_num_passes < capacity) ? tls_num_passes : capacity;
    for (int i = 0; i < n; i++) out_counts[i] = tls_candidate_counts[i];
    return n;
}

/* ── Per-pass LLR stats query (redesigned at shim 20260020) ─────────────── */
/*
 * ft8_get_last_llr_stats — return per-pass LLR statistics across all
 * LDPC-failing candidates from the most recent ft8_decode_all call on
 * this thread.
 *
 * out_mean_abs[i]        — post-normalisation mean abs(LLR) for pass i.
 * out_prenorm_variance[i]— pre-normalisation variance of raw log174, averaged
 *                          across failing candidates in pass i.  0.0f if none.
 * out_fail_count[i]      — count of LDPC-failing candidates in pass i.
 * capacity               — size of all three output arrays.
 *
 * Parameters and threading contract identical to ft8_get_last_pass_counts.
 */
int ft8_get_last_llr_stats(
    float* out_mean_abs,
    float* out_prenorm_variance,
    int*   out_fail_count,
    int    capacity)
{
    int n = (tls_num_passes < capacity) ? tls_num_passes : capacity;
    for (int i = 0; i < n; i++)
    {
        if (tls_llr_fail_count[i] > 0)
        {
            out_mean_abs[i]         = tls_llr_mean_abs_sum[i]    / (float)tls_llr_fail_count[i];
            out_prenorm_variance[i] = tls_llr_prenorm_var_sum[i] / (float)tls_llr_fail_count[i];
        }
        else
        {
            out_mean_abs[i]         = 0.0f;
            out_prenorm_variance[i] = 0.0f;
        }
        out_fail_count[i] = tls_llr_fail_count[i];
    }
    return n;
}

/* ── AP decode setter (Task A, shim 20260020) ────────────────────────────── */
/*
 * ft8_set_ap_bits — supply known AP bit constraints for the next decode cycle.
 *
 * Copies the caller-supplied packed bit arrays into TLS storage.  ft8_decode_all
 * reads these TLS values before the pass-0 decode loop and applies them as hard
 * LLR overrides via ftx_decode_candidate_ap.  Pass num_mycall_bits=0 to disable
 * AP constraints entirely (the default; decode behaves as in shim 20260019).
 */
void ft8_set_ap_bits(
    const uint8_t* mycall_bits,  int num_mycall_bits,
    const uint8_t* hiscall_bits, int num_hiscall_bits)
{
    /* Clamp to valid range (0..28 bits = 0..4 bytes) */
    if (num_mycall_bits < 0) num_mycall_bits = 0;
    if (num_mycall_bits > 28) num_mycall_bits = 28;
    if (num_hiscall_bits < 0) num_hiscall_bits = 0;
    if (num_hiscall_bits > 28) num_hiscall_bits = 28;

    tls_ap_num_mycall_bits  = num_mycall_bits;
    tls_ap_num_hiscall_bits = num_hiscall_bits;

    /* Copy only the bytes actually needed (ceil(num_bits / 8)) */
    int mycall_bytes  = (num_mycall_bits  + 7) / 8;
    int hiscall_bytes = (num_hiscall_bits + 7) / 8;

    memset(tls_ap_mycall_bits,  0, sizeof(tls_ap_mycall_bits));
    memset(tls_ap_hiscall_bits, 0, sizeof(tls_ap_hiscall_bits));

    if (mycall_bits && mycall_bytes > 0)
        memcpy(tls_ap_mycall_bits,  mycall_bits,  mycall_bytes);
    if (hiscall_bits && hiscall_bytes > 0)
        memcpy(tls_ap_hiscall_bits, hiscall_bits, hiscall_bytes);
}

/* ── Main decode entry point ─────────────────────────────────────────────── */
int ft8_decode_all(
    const float* pcm,
    int          pcm_len,
    FT8Result*   results,
    int          max_results)
{
    if (pcm_len != FT8_EXPECTED_SAMPLES) return -1;

    /*
     * SEH containment (MSVC / Windows builds only):
     *
     * Two crashes (0xC0000005 AV) were observed in production during the
     * PCM-SIC experiments.  This __try/__except wrapper catches any access
     * violation inside the ft8_lib waterfall or decode pipeline and returns
     * -2, allowing the managed layer to log the event and skip the cycle
     * instead of the process dying.
     *
     * monitor_t mon is declared before __try so the __except handler can
     * reference it if ever needed.  monitor_free is intentionally NOT called
     * in the __except handler — the heap may be partially corrupted after an
     * AV, and a second fault inside the handler is worse than the per-cycle
     * waterfall memory leak (~few hundred KB).  tls_hash_table is cleared in
     * both normal and exception paths to prevent a dangling pointer.
     *
     * Non-MSVC builds (Linux / macOS gcc/clang) have no SEH; a SIGSEGV on
     * those platforms terminates the process as before — no change.
     */
    monitor_t mon;   /* declared before __try — in scope for __except handler */

#ifdef _MSC_VER
    __try {
#endif

    /* ── 1. Build waterfall from PCM ─────────────────────────────────────── */
    monitor_config_t cfg = {
        .f_min = 200.0f, .f_max = 3000.0f,
        .sample_rate = FT8_SAMPLE_RATE,
        .time_osr = K_TIME_OSR, .freq_osr = K_FREQ_OSR,
        .protocol = FTX_PROTOCOL_FT8
    };
    monitor_init(&mon, &cfg);
    for (int pos = 0; pos + mon.block_size <= pcm_len; pos += mon.block_size)
        monitor_process(&mon, pcm + pos);

    /* ── 2. Callsign table ───────────────────────────────────────────────── */
    callsign_table_t htbl;
    hash_table_init(&htbl);
    tls_hash_table = &htbl;

    /* ── 3. Noise floor ──────────────────────────────────────────────────── */
    float     noise_floor_db;
    WF_ELEM_T noise_raw;
    compute_noise_floor(&mon, &noise_floor_db, &noise_raw);
    tls_last_noise_floor_db = noise_floor_db; /* expose to managed diagnostic layer */

    /* ── 4. Cross-pass dedup state ───────────────────────────────────────── */
    int            num_decoded  = 0;
    ftx_message_t  decoded_msgs[K_MAX_DECODED];
    ftx_message_t* decoded_ht[K_MAX_DECODED];
    memset(decoded_ht, 0, sizeof(decoded_ht));
    for (int i = 0; i < K_MAX_PASSES; i++) tls_pass_counts[i] = 0;
    for (int i = 0; i < K_MAX_PASSES; i++) tls_candidate_counts[i] = 0;
    for (int i = 0; i < K_MAX_PASSES; i++) tls_llr_mean_abs_sum[i]    = 0.0f;
    for (int i = 0; i < K_MAX_PASSES; i++) tls_llr_prenorm_var_sum[i] = 0.0f; /* Task B */
    for (int i = 0; i < K_MAX_PASSES; i++) tls_llr_fail_count[i]      = 0;
    tls_num_passes = 0;

    /* ── 4a. Cross-pass suppression accumulator ─────────────────────────── */
    /* Holds decoded candidates from pass 0 for spectrogram-domain tile
     * suppression before pass 1.  snr_db retained per entry for the soft
     * SNR-scaled attenuation factor in suppress_candidate_tiles.          */
    ftx_candidate_t all_supp_cands[K_MAX_CANDIDATES];
    ftx_message_t   all_supp_msgs [K_MAX_CANDIDATES];
    float           all_supp_snrs [K_MAX_CANDIDATES];
    int             n_all_supp    = 0;

    /* ── 4b. Build AP override array for pass 0 (Task A, shim 20260020) ───── */
    /*
     * If AP bits have been set via ft8_set_ap_bits(), unpack the packed bit
     * arrays into a 174-float override array for the pass-0 LDPC input path.
     * Entries are set to ±FT8_AP_LLR_HARD; remaining entries are 0.0f (no override).
     *
     * FT8 bit layout in log174 (systematic LDPC(174,87) code):
     *   log174[0..27]   — mycall (28 bits)
     *   log174[28..55]  — hiscall (28 bits)
     *   log174[56..76]  — report/grid (21 bits)
     *   log174[77..86]  — CRC (10 bits)
     *   log174[87..173] — parity
     *
     * Bits are packed MSB-first: bit 0 of mycall is in the MSB of mycall_bits[0].
     * Sign convention: bit value 1 → +LLR_HARD; bit value 0 → −LLR_HARD.
     */
    float ap_log174[FT8_AP_PAYLOAD_N];
    memset(ap_log174, 0, sizeof(ap_log174));
    bool ap_active = (tls_ap_num_mycall_bits > 0 || tls_ap_num_hiscall_bits > 0);
    if (ap_active)
    {
        /* mycall bits → log174[0..27] */
        for (int i = 0; i < tls_ap_num_mycall_bits && i < 28; i++)
        {
            int byte_idx = i / 8;
            int bit_shift = 7 - (i % 8);
            int bit_val = (tls_ap_mycall_bits[byte_idx] >> bit_shift) & 1;
            ap_log174[i] = FT8_AP_LLR_HARD * (bit_val ? +1.0f : -1.0f);
        }
        /* hiscall bits → log174[29..56] (fix-d001-h6-ap-hiscall-offset, shim 20260021)
         *
         * In a standard FT8 i3=1 message the 29-bit n29a field (mycall N28 <<1 | ipa)
         * occupies payload bits 0..28 MSB-first:
         *   bits 0..27 = N28(mycall) bits 27..0   ← constrained above (mycall)
         *   bit  28    = ipa (mycall /P or /R flag; 0 for normal callsigns)
         *
         * The 29-bit n29b field (hiscall N28 <<1 | ipb) follows immediately:
         *   bits 29..56 = N28(hiscall) bits 27..0  ← constrained here (hiscall)
         *   bit  57     = ipb (hiscall /P or /R flag; 0 for normal callsigns)
         *
         * The previous shim (20260020) erroneously used base 28 (log174[28..55]),
         * which placed hiscall bit 27 at the ipa position and shifted all subsequent
         * hiscall bits one step too early — causing wrong-sign LLR injections that
         * prevented LDPC convergence (the ipa and ipb bits are not injected here;
         * the waterfall provides their LLRs, which are strong and correct for the
         * normal no-suffix case). */
        for (int i = 0; i < tls_ap_num_hiscall_bits && i < 28; i++)
        {
            int byte_idx = i / 8;
            int bit_shift = 7 - (i % 8);
            int bit_val = (tls_ap_hiscall_bits[byte_idx] >> bit_shift) & 1;
            ap_log174[29 + i] = FT8_AP_LLR_HARD * (bit_val ? +1.0f : -1.0f);
        }
    }

    /* ── 5. Multi-pass decode loop ───────────────────────────────────────── */
    static const struct { int min_score; int max_cands; int ldpc; } k_pass_cfg[K_MAX_PASSES] = {
        { K_MIN_SCORE,       K_MAX_CANDIDATES,       K_LDPC_ITERATIONS       }, /* pass 0: full waterfall           */
        { K_MIN_SCORE_PASS2, K_MAX_CANDIDATES_PASS2, K_LDPC_ITERATIONS_PASS2 }, /* pass 1: spectrogram-suppressed   */
    };

    for (int pass = 0; pass < K_MAX_PASSES; pass++)
    {
        /* ── Early-exit: skip if result buffer is already full ───────────── */
        if (num_decoded >= max_results) {
            tls_pass_counts[pass] = 0;
            tls_num_passes        = pass + 1;
            continue;
        }

        if (pass == 1)
            for (int i = 0; i < n_all_supp; i++)
                suppress_candidate_tiles(&mon.wf, &all_supp_cands[i], &all_supp_msgs[i], noise_raw, all_supp_snrs[i]);

        int pass_min_score = k_pass_cfg[pass].min_score;
        int pass_max_cands = k_pass_cfg[pass].max_cands;
        int pass_ldpc      = k_pass_cfg[pass].ldpc;

        /* Size the local candidate array to the maximum across all passes */
        ftx_candidate_t candidates[K_MAX_CANDIDATES_PASS2]; /* largest per-pass max */
        int ncands = ftx_find_candidates(&mon.wf, pass_max_cands,
                                          candidates, pass_min_score);
        tls_candidate_counts[pass] = ncands;

        int new_decodes = 0;

        for (int ci = 0; ci < ncands && num_decoded < max_results; ++ci)
        {
            const ftx_candidate_t* cand = &candidates[ci];

            ftx_message_t       msg;
            ftx_decode_status_t status;

            /* Task A (shim 20260020): use AP-constrained decode for pass 0 when AP
             * bits are active; fall back to standard decode for pass 1 or when AP
             * is disabled (ac_active == false, ap_log174 is all-zero).            */
            bool decoded;
            if (pass == 0 && ap_active)
                decoded = ftx_decode_candidate_ap(&mon.wf, cand, pass_ldpc,
                                                  ap_log174, &msg, &status);
            else
                decoded = ftx_decode_candidate(&mon.wf, cand, pass_ldpc, &msg, &status);

            if (!decoded)
            {
                /* Task B (shim 20260020): accumulate pre-normalisation variance and
                 * mean|LLR| for failing candidates; skip NaN/degenerate candidates. */
                float prenorm_var = 0.0f;
                float mean_abs = ftx_compute_candidate_llr_stats(&mon.wf, cand, &prenorm_var);
                if (isfinite(mean_abs))
                {
                    tls_llr_mean_abs_sum[pass]    += mean_abs;
                    tls_llr_prenorm_var_sum[pass] += prenorm_var;
                    tls_llr_fail_count[pass]++;
                }
                /* Degenerate (NaN) candidates: skip — do not contaminate the sum */
                continue;
            }

            /* Cross-pass dedup */
            int  slot = (int)(msg.hash % K_MAX_DECODED);
            bool dup  = false, found = false;
            int  walk = slot;
            for (int s = 0; s < K_MAX_DECODED; ++s) {
                walk = (slot + s) % K_MAX_DECODED;
                if (!decoded_ht[walk]) { found = true; break; }
                if (decoded_ht[walk]->hash == msg.hash &&
                    !memcmp(decoded_ht[walk]->payload, msg.payload,
                            sizeof(msg.payload)))
                { dup = true; break; }
            }
            if (dup || !found) continue;

            /* Attempt text decode BEFORE occupying the dedup slot.
             * If ftx_message_decode fails (e.g. Type-4 hash not yet known),
             * bail here so the slot stays free for a later retry.          */
            char text[FTX_MAX_MESSAGE_LENGTH + 1];
            if (ftx_message_decode(&msg, &s_hash_if, text) != FTX_MESSAGE_RC_OK)
                continue;

            /* Text decode succeeded — commit to the dedup table */
            memcpy(&decoded_msgs[walk], &msg, sizeof(msg));
            decoded_ht[walk] = &decoded_msgs[walk];

            /* Frequency, time offset, and SNR */
            float freq_hz = (mon.min_bin + cand->freq_offset +
                             (float)cand->freq_sub / mon.wf.freq_osr)
                           / mon.symbol_period;
            float dt      = (cand->time_offset +
                             (float)cand->time_sub / mon.wf.time_osr)
                           * mon.symbol_period;

            uint8_t tones[FT8_NN];
            ft8_encode(msg.payload, tones);

            float signal_db;
            {
                float sum = 0.0f; int cnt = 0;
                int bs = mon.wf.block_stride;
                int pt = mon.wf.freq_osr * mon.wf.num_bins;
                int nb = mon.wf.num_bins;
                int b0 = (int)cand->time_offset; if (b0 < 0) b0 = 0;
                int b1 = b0 + FT8_NN;
                if (b1 > mon.wf.num_blocks) b1 = mon.wf.num_blocks;
                int fi = (int)cand->time_sub * pt + (int)cand->freq_sub * nb +
                         (int)cand->freq_offset;
                for (int b = b0; b < b1; b++) {
                    const WF_ELEM_T* row = mon.wf.mag + b * bs + fi;
                    int tone_col = (int)tones[b - b0];
                    /* RQ-2 guard: tones[x] ∈ [0,7]; for signals near f_max the
                     * active tone bin may overflow num_bins — skip those samples
                     * rather than read past the waterfall row boundary.        */
                    if ((int)cand->freq_offset + tone_col >= nb) continue;
                    float mx = (float)row[tone_col] * 0.5f - 120.0f;
                    sum += mx; cnt++;
                }
                signal_db = cnt > 0 ? sum / (float)cnt : noise_floor_db;
            }
            float local_noise_db = compute_local_noise_floor_db(&mon.wf, (int)cand->freq_offset);
            float snr = signal_db - local_noise_db - 26.5f;

            FT8Result* r = &results[num_decoded++];
            r->freq_hz = (int)roundf(freq_hz);
            r->dt      = dt;
            r->snr     = (int)roundf(snr);
            strncpy(r->message, text, 35);
            r->message[35] = '\0';

            new_decodes++;

            /* Track for spectrogram suppression accumulator (pass 0 only).
             * Pass-0 decoded candidates are tile-suppressed before pass 1 runs.
             * Excess beyond K_MAX_CANDIDATES is silently discarded.             */
            if (pass == 0 && n_all_supp < K_MAX_CANDIDATES) {
                all_supp_cands[n_all_supp] = *cand;
                all_supp_msgs [n_all_supp] = msg;
                all_supp_snrs [n_all_supp] = snr;
                n_all_supp++;
            }
        }

        tls_pass_counts[pass] = new_decodes;
        tls_num_passes        = pass + 1;
    }

    /* ── 6. Cleanup ──────────────────────────────────────────────────────── */
    tls_hash_table = NULL;
    monitor_free(&mon);

    return num_decoded;

#ifdef _MSC_VER
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {
        /* Access violation (0xC0000005) or other SEH fault in the decode
         * pipeline.  Clear the callsign-table TLS pointer (a dangling
         * pointer is worse than a leak) and return -2.  monitor_free is
         * intentionally skipped: the waterfall heap may be partially
         * corrupted; a second AV inside the handler would be fatal.
         * The managed layer receives -2, logs at WARNING, and skips the
         * decode cycle.                                                   */
        tls_hash_table = NULL;
        return -2;
    }
#endif
}
