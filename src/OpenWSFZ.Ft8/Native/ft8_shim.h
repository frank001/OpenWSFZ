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
 *              and existing return codes unchanged.
 *   20260018 — diag-d001-candidate-counts: add ft8_get_last_candidate_counts()
 *              TLS getter exposing the per-pass count of candidates returned by
 *              ftx_find_candidates() (before LDPC decode attempt).  Together with
 *              ft8_get_last_pass_counts() (which counts successful decodes) this
 *              lets the managed diagnostic layer distinguish candidate-generation
 *              failure from LDPC convergence failure in D-001 co-channel scenarios.
 *              No change to decode logic, struct layout, or existing entry points.
 *   20260019 — diag-d001-llr-mean-abs: add ft8_get_last_llr_stats() exposing
 *              per-pass mean abs(LLR) across LDPC-failing candidates.
 *              ftx_compute_candidate_llr_mean_abs() added to decode.c (non-static)
 *              computes likelihood + normalisation without calling bp_decode.
 *              No change to existing entry points, struct layout, or return codes.
 *   20260020 — diag-d001-h6-ap-probe: two changes in one shim bump:
 *              (A) ft8_set_ap_bits() — directed AP decode setter.  Supplies known
 *              mycall/hiscall bit constraints to the pass-0 LDPC input path.
 *              Known bits are injected as ±LLR_HARD (40.0) into the log174 array
 *              after waterfall likelihood extraction and before normalisation.
 *              This anchors LDPC belief-propagation on ~36% of the payload bits,
 *              improving convergence when the remaining LLRs are near-zero due to
 *              equal-SNR co-channel interference (D-001 root cause, H6 hypothesis).
 *              Applied only during pass 0; disabled for pass 1.
 *              C# caller NOT yet wired — interop seam only for this shim.
 *              (B) ft8_get_last_llr_stats() redesigned: adds a third output array
 *              out_prenorm_variance for per-pass pre-normalisation variance of
 *              the raw log174 array.  ftx_compute_candidate_llr_mean_abs renamed
 *              to ftx_compute_candidate_llr_stats with new signature.  isfinite()
 *              guard added before accumulation to skip degenerate (NaN) candidates.
 *              Pre-normalisation variance distinguishes degraded LLRs from healthy
 *              ones; post-normalisation mean|LLR| is a near-constant ~3.91 for any
 *              non-degenerate distribution (H_LLR hypothesis inconclusive, shim 20260019).
 *   20260021 — fix-d001-h6-ap-hiscall-offset: correct hiscall AP injection position.
 *              In shim 20260020 the hiscall bits were injected at log174[28..55]
 *              (off by one — position 28 is the mycall /P or /R suffix flag ipa,
 *              not the first hiscall bit).  The correct positions for hiscall N28
 *              bits 27..0 in a standard FT8 i3=1 message are log174[29..56].
 *              Fixed by changing loop base from 28 to 29.  No change to mycall
 *              injection (log174[0..27]) or any other decode path.
 *              C# Ft8CallsignPacker.Pack28 also corrected (wrong character-set
 *              ordering for positions 0 and 1, wrong offset 2 064 592 instead of
 *              NTOKENS+MAX22 = 6 257 896); C# AP wiring now complete (H6).
 *   20260025 — fix-d001-osd: Ordered Statistics Decoding (OSD) fallback added to
 *              ftx_decode_candidate and ftx_decode_candidate_ap in
 *              patched/ft8/decode.c.  When bp_decode() fails to converge
 *              (ldpc_errors > 0), osd_decode(llr_for_osd, ndeep=2, plain174) is
 *              called with the pre-BP normalised LLRs, matching WSJT-X's default
 *              maxosd=2 at ndepth=3 (osd174_91.f90, zsave(:,1) snapshot).
 *
 *              Algorithm (static osd_decode + osd_try_codeword in decode.c, C11):
 *              (1) Sort 174 bits by |LLR| descending (insertion sort, O(N^2)).
 *              (2) Build permuted parity-check matrix H_perm[83][174] on stack.
 *              (3) GF(2) Gaussian elimination → reduced row echelon form;
 *                  track pivot column per row (normally 83 pivots for rank-83 H).
 *              (4) Free columns (≈91) carry information bits; base values from
 *                  hard decisions (sign of sorted LLRs).
 *              (5) Enumerate flip trials in the 32 least-reliable free positions:
 *                  0-flip (1), single-flip (32), double-flip (496) = 529 trials.
 *              (6) For each trial: compute pivot bits from parity equations,
 *                  un-permute to original domain, run CRC-14 check.
 *
 *              Stack per osd_decode call: ≈18 KB (H[83][174]=14 KB dominant).
 *              Also raises K_LDPC_ITERATIONS from 25 → 50 (optimal flooding BP
 *              count established by H_ITER diagnostic on diag/d001-ldpc-iter-
 *              hypothesis; versions 20260022–24 were on that unmerged branch;
 *              those version slots are permanently retired here).
 *              No change to ABI, struct layout, or any existing entry points.
 *              Target: close D-001 blind co-channel decode gap (≈40%→≥80% MSG-01
 *              at Δ7 Hz, S7 P16).
 *   20260026 — fix-d009-r2: OSD correlation gate at both osd_decode call sites in
 *              patched/ft8/decode.c.  Rejects OSD candidates whose normalised
 *              inner-product score (corr/norm) is below OSD_CORR_THRESHOLD = 0.10.
 *              Text-layer D9-R3 Gap A and Gap C extensions in IsPlausibleMessage
 *              (C# only, no native change).  S5 R2 verification showed 75.0% FP
 *              rate at threshold 0.10 — insufficient; raised in 20260027.
 *   20260027 — fix-d009-r3: OSD_CORR_THRESHOLD raised 0.10 → 0.15 in decode.c.
 *              Category B (structurally-valid 3-token FPs) and Category C (CQ <...>)
 *              cannot be addressed by text filtering; only the gate threshold can
 *              suppress them.  Text-layer: 4-token non-CQ messages now rejected by
 *              IsPlausibleMessage (C# only, no additional native change).
 *   20260028 — fix-d009-r5: OSD two-feature gate — nhard Hamming-distance check
 *              added alongside the existing corr/norm check at both OSD sites in
 *              patched/ft8/decode.c (ftx_decode_candidate and
 *              ftx_decode_candidate_ap).  The R4 single-knob loop proved ceilinged
 *              (0 FP on S5 required threshold >= 0.40; S7 co-channel needs <= 0.35).
 *              nhard = Σ(plain174[i] != (LLR[i] > 0 ? 0 : 1)) for i in 0..173.
 *              Genuine decodes are Hamming-close to the channel hard decisions
 *              regardless of SNR; noise CRC-14 coincidences cluster near 87.
 *              OSD_CORR_THRESHOLD reverted to 0.10 (nhard carries noise rejection);
 *              OSD_NHARD_MAX = 60 (calibrated against S5/S7 histograms).
 *              No ABI change; struct layout unchanged (48 bytes).
 *   20260029 — fix-d009-k10: K_MIN_SCORE_PASS2 raised 1 → 10 (D-009 production
 *              fix).  Pass-1 sweep (diag-pass1-sweep-2026-06-21) showed K=10
 *              cuts S5 FP rate by 94% (0.675 → 0.042 FP/slot) while improving
 *              S7 co-channel recovery over the K=1 baseline (+8.5 pp on hard
 *              P0–P2 subset).  All other shim-20260028 gate values unchanged:
 *              OSD_NHARD_MAX=60, OSD_CORR_THRESHOLD=0.10, text Rules A/B/C.
 *              No ABI change; struct layout unchanged (48 bytes).
 *   20260030 — decoder-settings-page: runtime-configurable OSD gate parameters via
 *              ft8_set_decode_params(k, corr, nhard).  K_MIN_SCORE_PASS2 promoted from
 *              compile-time #define to module-level int s_k_min_score_pass2 (default 10).
 *              OSD_CORR_THRESHOLD and OSD_NHARD_MAX in decode.c replaced by extern globals
 *              s_osd_corr_threshold (default 0.10f) and s_osd_nhard_max (default 60)
 *              owned by ft8_shim.c.  No change to decode logic, ABI, struct layout (48 bytes),
 *              or any existing entry points.  Default values identical to shim 20260029;
 *              omitting ft8_set_decode_params produces identical behaviour.
 *   20260031 — f-001-hashed-callsign-resolution: the per-call stack-local callsign hash
 *              table in ft8_decode_all is replaced by a process-global, session-scoped
 *              static (g_session_hash_table), initialised once and reused by every
 *              subsequent call for the life of the process.  A Type 4 message's full-text
 *              nonstandard callsign, once decoded in any cycle, now resolves correctly
 *              when referenced by 22-bit hash in a Type 1/2/3 message in a later cycle —
 *              previously the table was destroyed at the end of every call, so cross-cycle
 *              resolution could never succeed.  tls_hash_table (thread-local) is unchanged
 *              in nature: it is still cleared to NULL on both the normal-return and the
 *              __except (SEH) path, but now merely detaches from the shared global instead
 *              of pointing at a per-call local; the global's *contents* survive a caught
 *              access violation untouched (D2 — neither documented AV root cause touches
 *              this table's memory region).  Eviction policy is unchanged: hash_table_add
 *              still rejects new entries once the existing 256-slot table is full (D3 —
 *              true FIFO eviction deferred, not required for this change).
 *              ft8_encode_message's own per-call local table is untouched — encoding does
 *              not depend on prior session state.  No ABI change; struct layout unchanged
 *              (48 bytes); no new exported entry points.
 *   20260032 — f-005-hash-table-saturation-diagnostic: adds one exported read-only getter,
 *              ft8_get_hash_table_reject_count(), returning the existing process-global
 *              g_hash_table_reject_count (the reject-when-full counter added at 20260031 but
 *              not previously exposed).  Observability-only: no change to resolution
 *              behaviour, the 256-slot capacity, or the eviction policy.  Struct layout
 *              unchanged (48 bytes); the only ABI change is the single added export.
 *   20260033 — fix-d012-hash-table-add-overcounting: hash_table_add's full-table guard
 *              ran BEFORE the "already known" linear-probe check, so once the 256-slot
 *              table saturated every subsequent call incremented g_hash_table_reject_count
 *              and returned immediately — including re-announcements of callsigns already
 *              resolvable in the table.  A real 9.5h corpus replay (42,429 total decodes)
 *              exposed a reject-count delta of 73,627, an arithmetic impossibility.  Fixed
 *              by reordering: a bounded linear probe (mirroring hash_table_lookup's existing
 *              guard) now always runs first; an already-known callsign is a no-op regardless
 *              of table fullness; the tbl->count >= HASH_TABLE_SIZE reject-and-count only
 *              fires after a full probe confirms the callsign is genuinely new.  No change
 *              to the 256-slot capacity or eviction policy.  No ABI or struct layout change;
 *              no new exported entry points.
 *
 *   20260038 (g2-hash-table-sizing-and-candidate-passband): two independent native
 *              constant changes, shipped together.  (a) HASH_TABLE_SIZE 256 → 4096:
 *              the table keys on a 10-bit bucket (1024 values) placed at
 *              (h10 * 23) % HASH_TABLE_SIZE, injective up to N = 1024, so N = 256
 *              collided 4:1 by construction before the table was full.  Buys message
 *              TEXT only (fewer <...>); CANNOT change the decode count.  (b) the
 *              ft8_decode_all monitor_config_t candidate passband widened from
 *              [200, 3000) Hz to [140, 3030) Hz, covering 99.90% of the pooled
 *              three-corpus reference decode-frequency distribution (was ~99.09%);
 *              a signal outside the passband is missed by construction, 100% of the
 *              time.  Width +3.2%.  No ABI or struct layout change (FT8Result stays
 *              48 bytes); no new exported entry points.  ONE bump covers both items:
 *              20260034-20260037 are unavailable and 20260039-20260041 are reserved
 *              for the R0/R1/R2 programme.
 *
 * r0-reproducible-native-build (FT8_SHIM_VERSION 20260039):
 *
 *   Provenance/reproducibility marker only -- no ABI, struct layout, or decode-
 *   behaviour change.  All eleven linked translation units now compile from a
 *   vendored, version-controlled source tree (native/ft8_lib_vendor/) instead
 *   of linking nine pre-built, untracked .obj files of unknown provenance.
 *   AC-1 (mechanical diff, 250 contiguous cycles, artefacts/20260808_live_run_
 *   0016-8080/wsjt-x/wav, 260808_004000..260808_014215): zero differences
 *   against the previously-shipped 20260038 binary (SHA256 c559a049d103c1f3...).
 *   AC-2 (two independent clean builds): zero differences against each other.
 *
 *   One genuine finding surfaced and fixed during this rebuild: ft8/message.c
 *   (vendored, upstream-unmodified) calls stpcpy() with no prototype in scope
 *   under MSVC, which silently falls back to "implicit extern returning int"
 *   and truncates the returned char* to 32 bits -- MECHANICALLY CONFIRMED to
 *   reproduce D-006's exact root cause (the fatal 32-bit pointer truncation
 *   fixed at FT8_SHIM_VERSION 20260015 by hand-patching a single opcode byte
 *   directly in the pre-built message.obj, with no source-level fix ever
 *   written, because message.c was never recompiled until this change). Fixed
 *   by force-including a correct prototype
 *   (native/ft8_lib_build/patched/stpcpy_msvc_compat.h) only at compile time,
 *   via rebuild_shim.bat's /FI flag on message.c -- zero bytes of the vendored
 *   tree are touched. Verified at the disassembly level: both call-sites now
 *   follow `call stpcpy` with a full 64-bit `mov`, not the truncating 32-bit
 *   `movsxd` MSVC emits without the prototype.
 *
 *   r0-review-followup (folded into this same 20260039, per the Captain's
 *   ruling -- this build had not yet been pushed or merged, so this is
 *   amending R0's own not-yet-shipped work rather than a separately versioned
 *   change): native/ft8_lib_build/patched/common/monitor.c had carried
 *   `#define LOG_LEVEL LOG_INFO` since its first port commit, dormant because
 *   monitor.c was never actually compiled until this change made it so --
 *   its four LOG_INFO calls (monitor_init's Block/Subblock/N_FFT/N_iFFT size
 *   prints) started firing via fprintf(stderr, ...) on every single
 *   ft8_decode_all call, interleaving into the daemon's structured stderr log
 *   channel (StderrLoggerProvider.cs, FR-019) on every ~15s decode cycle,
 *   forever. Raised to LOG_WARN (monitor.c has zero LOG_WARN/ERROR/FATAL call
 *   sites today, so this silences exactly the noise while leaving LOG() live
 *   for any future LOG_WARN-or-above diagnostic). ft8/debug.h itself is
 *   untouched -- genuinely vendored, upstream-unmodified, correct as-is.
 *   Re-verified AC-1/AC-2 on the same 250-cycle range against both the
 *   pre-fix 20260039 build and the original 20260038 baseline: zero decode-
 *   output differences either way (log-output-only change). DLL SHA256:
 *   897f81dda95b83b24156a905b3aeec4a1cb98c64e5243564e6d0eb6b60643cb3.
 *
 * r1-sync-refiner-instrument-validation (FT8_SHIM_VERSION 20260040):
 *
 *   Adds ft8_refine_candidate() -- a new DIAGNOSTIC-ONLY export implementing
 *   a per-candidate coherent sync-refinement stage: downconverts the
 *   candidate's region of PCM to complex baseband (phase retained, not the
 *   existing uint8_t magnitude-only waterfall), correlates coherently
 *   against the three Costas 7x7 sync arrays (complex values summed first,
 *   magnitude taken last -- explicitly not the ft8_decode_multi_symbols()
 *   shape, which is dead code that sums dB magnitudes), and searches
 *   two-dimensionally (coarse time -> frequency -> fine time) to produce a
 *   refined (delta_f, delta_t) plus a sync quality score. Implemented in the
 *   new native/ft8_lib_vendor/refine/sync_refiner.c (OpenWSFZ-original code,
 *   additive to the vendor tree per design.md D7 -- not a modification of
 *   any byte-identical-to-upstream file).
 *
 *   Clean-room: written directly from this change's spec.md/design.md method
 *   description; no WSJT-X source was available in or consulted during this
 *   session (see sync_refiner.c's header comment).
 *
 *   No production call site: ft8_refine_candidate is reachable only from the
 *   validation harness and test code introduced by this change.
 *   ftx_decode_candidate() and ft8_decode_all's production decode path
 *   remain byte-for-byte unchanged -- this bump exists purely so the startup
 *   ABI check catches a native binary built without the new export. No
 *   struct layout change (FT8Result stays 48 bytes).
 *
 * r1b-sync-refiner-instrument-correction (FT8_SHIM_VERSION 20260041):
 *
 *   D1: ft8_refine_candidate() gains two new out-parameters,
 *   out_coarse_dt_samp and out_fine_dt_samp, exposing the Stage A+B coarse-
 *   time selection (best_dt_samp, @200 Hz, range [-12, 12]) and the Stage C
 *   fine-time selection (best_fine_samp, @2000 Hz, range [-20, 20]) that the
 *   search already computed internally but did not, prior to this change,
 *   make observable -- only their sum left the function via out_delta_time_s.
 *   Pure instrumentation of the existing search/correlation logic in
 *   native/ft8_lib_vendor/refine/sync_refiner.c -- no algorithm change. The
 *   three pre-existing out-parameters (out_delta_freq_hz, out_delta_time_s,
 *   out_sync_score) continue to be populated identically to the 20260040
 *   build. Diagnostic-only, no production call site -- identical boundary to
 *   r1-sync-refiner-instrument-validation. Motivated by the Captain's ruling
 *   on R1 (qa/rr-study/2026-08-14-2028-architect-to-qa-r1-ruling-and-r1b-
 *   instrument-scope.md): AC-3's time-dimension FAIL could not be localised
 *   to a search stage because the decomposition was unobservable; this
 *   export makes it testable (see evaluate_acs.py's reflection_symmetry_test,
 *   run separately on the combined, coarse-only, and fine-only values).
 *
 * n1-extract-llrs-at-position (FT8_SHIM_VERSION 20260042):
 *
 *   Adds ft8_extract_llrs_at() -- a new DIAGNOSTIC-ONLY export that runs the
 *   existing, unmodified ft8_extract_likelihood() extraction path at a
 *   caller-supplied (freq_hz, time_offset_s) position instead of one
 *   ftx_find_candidates() already located. Builds the waterfall exactly as
 *   ft8_decode_all does, snaps the requested position to the nearest point on
 *   the same K_FREQ_OSR/K_TIME_OSR lattice every existing candidate already
 *   lives on, and delegates to a new non-static probe in decode.c,
 *   ftx_extract_likelihood_at() (following the exact non-static-probe pattern
 *   ftx_compute_candidate_llr_stats already established). Returns the raw,
 *   pre-normalisation 174 log-likelihoods -- ftx_normalize_logl() is
 *   deliberately not applied, matching the sign-convention discipline
 *   c2_phase2c_ber_measurement.py's hard_decision_ber() already documents and
 *   depends on.
 *
 *   N1 (qa/rr-study/2026-08-15-1840-architect-to-qa-N1-ber-at-refined-position-
 *   spec.md) needs this to extract LLRs twice per row -- once at a candidate's
 *   own grid position (control), once at grid + ft8_refine_candidate's
 *   (delta_f, delta_t) (treatment) -- on identical audio, which neither
 *   ft8_decode_all's own output nor any existing export can do; both only
 *   read back LLRs a decode run already captured at its own grid position.
 *
 *   No production call site: ft8_extract_llrs_at is reachable only from test
 *   code and QA harnesses invoking it directly (e.g. Python ctypes).
 *   ft8_decode_all, ft8_get_last_pass_counts, ft8_set_decode_params, and
 *   ft8_refine_candidate all remain byte-for-byte unchanged -- this bump
 *   exists purely so the startup ABI check catches a binary built without the
 *   new export. No struct layout change (FT8Result stays 48 bytes). No C#
 *   Ft8LibInterop/IFt8NativeInterop wiring added (design.md D5) -- the
 *   consumer is the Python QA harness, the same pattern the raw-LLR-capture
 *   export family already established without managed bindings.
 *
 * r2-coherent-llr-instrument (FT8_SHIM_VERSION 20260043), Route B2 Phase 1,
 * tasks 1.1-1.5:
 *
 *   Adds ft8_coherent_llr_at() -- a new DIAGNOSTIC-ONLY export implementing
 *   per-candidate coherent multi-symbol LLR formation AT THE CANDIDATE'S
 *   EXISTING, UNREFINED GRID POSITION (design.md D1: NEVER calls
 *   ft8_refine_candidate or any other position-search routine -- Route B2's
 *   limb 1, candidate position refinement, is dead three times over (M4,
 *   N1, P-LIVE Stage 2); this export tests limb 2, coherent multi-symbol LLR
 *   formation, in isolation so a null result cannot be blamed on a bad
 *   position estimate). Downconverts to complex baseband at the candidate's
 *   grid frequency (phase retained), reusing sync_refiner.c's own
 *   downconvert_decimate()/design_lowpass_hann() (now non-static, shared via
 *   the new native/ft8_lib_vendor/refine/refine_common.h -- a linkage-only
 *   change to sync_refiner.c, no algorithm/constant/logic changed); for each
 *   of the 58 data symbols, coherently correlates against each of the 8 tone
 *   hypotheses (complex accumulation across the symbol, magnitude last);
 *   forms 1-, 2- and 3-symbol coherent metrics over every Costas-block-
 *   boundary-respecting window; combines into 174 per-bit LLRs via max-log
 *   over tone hypotheses (this file's own bit-index convention, NOT decode.c's
 *   unreachable ft8_decode_multi_symbols convention -- see coherent_llr.c's
 *   own header comment for the full derivation and rationale); normalises to
 *   the same scale ftx_normalize_logl() produces (formula duplicated locally
 *   in coherent_llr.c -- decode.c has ZERO edits from this change).
 *   Implemented in the new native/ft8_lib_vendor/refine/coherent_llr.c
 *   (OpenWSFZ-original, clean-room -- no WSJT-X source was consulted).
 *
 *   Signature deliberately matches ft8_extract_llrs_at's own shape --
 *   (pcm, pcm_len, freq_hz, time_offset_s, out_log174), not the proposal's
 *   illustrative (freq_idx, time_idx, out_diag) sketch -- so the Phase 1
 *   gate harness satisfies the candidate-identity requirement (spec.md
 *   "Candidate identity between the grid and coherent extractions") simply
 *   by calling both exports with the identical two floats. See
 *   coherent_llr.c's own header comment, "SIGNATURE CHOICE", for the full
 *   rationale.
 *
 *   No production call site: reachable only from test code and the Phase 1
 *   gate harness (this change's own tasks.md §4.3, not yet built).
 *   ftx_decode_candidate(), ft8_decode_all's production decode path, and
 *   every other existing exported symbol (including ft8_refine_candidate and
 *   ft8_extract_llrs_at) remain byte-for-byte unchanged -- decode.c has zero
 *   edits from this change, and the bump exists purely so the startup ABI
 *   check catches a binary built without the new export. No struct layout
 *   change (FT8Result stays 48 bytes).
 *
 *   UNVALIDATED: this is a new correlator with no prior measurement. Per
 *   design.md's own Risks section, this export's own ROW 0c (a mandatory
 *   two-sided sign unit test, run once by the Phase 1 gate harness) is the
 *   guard against a sign or bit-attribution defect -- nothing from this
 *   export should be trusted for any downstream measurement until that test
 *   passes.
 *
 * r2-coherent-llr-instrument Phase B + Amendment 1 (FT8_SHIM_VERSION
 * 20260044): asserted unused across all branches (local and origin) before
 * adoption, per task 10.1.
 *
 *   B1 -- fixes ft8_coherent_llr_at's raw-PCM correlation origin
 *   (coherent_llr.c): the lattice-snapped time_offset_s_grid names the
 *   START of the waterfall analysis window, not its centre; the analysis
 *   window's own look-back buffer + multi-symbol span means the true
 *   correlation origin sits (freq_osr/2 + 0.5 - 1/time_osr) symbols earlier
 *   -- one full symbol (-0.16 s) at production's own K_TIME_OSR =
 *   K_FREQ_OSR = 2. Derived at runtime from mon.wf.time_osr/mon.wf.freq_osr/
 *   mon.symbol_period (never hardcoded). Root cause: qa/rr-study/2026-08-21-
 *   1412-architect-to-qa-origin-convention-finding-and-spec-b-orig-a.md.
 *   Confirmed against known ground truth (B-orig-A, ROW 1: mode(coherent)
 *   moved 0 -> +2 quanta, agreeing with the grid path's own mode; the grid
 *   path's own mode was unchanged, confirming this fix touches only the
 *   coherent path). Does not amend design.md D1 -- the candidate position
 *   used is still the existing grid position, unrefined; this is a unit
 *   conversion of that position's own representation, not a position
 *   search.
 *
 *   B2 -- fixes ft8_coherent_llr_at's cross-window fusion comparison
 *   (coherent_llr.c): the 1-/2-/3-symbol coherent windows were compared by
 *   raw fabsf() magnitude, which structurally favours the longest window
 *   (a coherent sum's magnitude scales with window length) regardless of
 *   its actual reliability. Each window's per-bit LLRs are now divided by
 *   that window's own magnitude standard deviation (coh_window_scale)
 *   before the comparison, guarded against a degenerate zero-spread window
 *   (left unscaled rather than divided by zero). n_syms is NOT restricted
 *   -- all three window sizes remain in the comparison; only the scale
 *   they are compared at changes. Mandatory unit test: task 8.2.
 *
 *   B4 (Amendment 1) -- adds ft8_ldpc_decode_llrs(), a new DIAGNOSTIC-ONLY
 *   export that decodes a caller-supplied 174-element raw LLR vector
 *   through production's own ftx_normalize_logl -> bp_decode -> OSD
 *   (conditional) -> CRC-14 sequence, mirroring ftx_decode_candidate
 *   (patched/ft8/decode.c:641-713) exactly. Forced placement: the
 *   decode.c-resident implementation, ftx_ldpc_decode_llrs, lives in
 *   patched/ft8/decode.c (ftx_normalize_logl and osd_decode are both
 *   static there), with this thin wrapper the only code in ft8_shim.c --
 *   the established two-file pattern ft8_extract_llrs_at/
 *   ftx_extract_likelihood_at already set. Lets a future analysis arm (C2,
 *   specced later, not this change) convert a diagnostic LLR vector into a
 *   CRC-verified decode count instead of a modelled BER-threshold
 *   crossing.
 *
 *   No production call site: reachable only from test code and QA
 *   harnesses. ftx_decode_candidate(), ft8_decode_all's production decode
 *   path, and every other existing exported symbol (including
 *   ft8_extract_llrs_at and the pre-Phase-B behaviour of
 *   ft8_coherent_llr_at's own call signature) remain byte-for-byte
 *   unchanged in ABI -- B1/B2 change the VALUES ft8_coherent_llr_at
 *   returns, not its signature; B4 is a wholly new export. No struct
 *   layout change (FT8Result stays 48 bytes). No C# Ft8LibInterop/
 *   IFt8NativeInterop wiring added for ft8_ldpc_decode_llrs (design.md
 *   D10) -- the consumer is the Python QA harness and this session's own
 *   native/Python smoke tests, the same pattern ft8_extract_llrs_at
 *   already established.
 *
 * r2-coherent-llr-instrument Amendment 2 (corrected by Amendment 3),
 * FT8_SHIM_VERSION 20260045, task 16.1: asserted unused across all branches
 * (local and origin) before adoption. Two changes in one rebuild ("one
 * rebuild, not two"):
 *
 *   (1) Widens ftx_ldpc_decode_llrs's degenerate-variance guard
 *   (patched/ft8/decode.c:940, added by B4) from exact-equality
 *   `variance == 0.0f` to `!(variance > 0.0f)`, matching coh_window_scale's
 *   own guard (coherent_llr.c, added by B2) -- also catches a
 *   float-cancellation NEGATIVE variance the exact-equality check alone
 *   would miss, which could otherwise let a near-constant-but-not-bit-exact
 *   input slip past the guard into ftx_normalize_logl's sqrtf(24.0f/
 *   variance) and produce NaN. B4-d re-run after the edit: still negative
 *   rc, still no crash, no NaN, on the same all-3.5f zero-variance input.
 *   ftx_ldpc_decode_llrs has no production call site (grep-confirmed) and
 *   no C# binding, so this is provably off the production decode path.
 *
 *   (2) Adds ft8_get_last_snr_terms() -- a new diagnostic-only TLS getter
 *   exposing signal_db/local_noise_db (the SNR formula's two terms,
 *   ft8_shim.c:1474) for every decode from the most recent ft8_decode_all
 *   call on this thread, index-aligned with results[]/FT8Result[] from
 *   that same call. Two new _Thread_local float arrays (tls_signal_db,
 *   tls_local_noise_db) plus a count, written at the same pre-increment
 *   index results[] uses for each decode -- read-only, no control-flow,
 *   ordering, or value change to any existing decode-path computation.
 *   Built to localise a large, conditional SNR-reporting error (measured
 *   against the true_dt == 0 vs true_dt > 0 split, arm B-dt-A) to one of
 *   its two terms. Unlike B4, this export DOES get a C# Ft8LibInterop/
 *   IFt8NativeInterop binding (Ft8LibInterop.GetLastSnrTerms).
 *
 *   No production call site for either change. ftx_decode_candidate(),
 *   ft8_decode_all's production decode path, and every other existing
 *   exported symbol remain byte-for-byte unchanged in ABI. No struct
 *   layout change (FT8Result stays 48 bytes).
 *
 * fix-negative-time-offset-snr-collapse (FT8_SHIM_VERSION 20260046):
 * corrects a defect in ft8_decode_all's production signal_db loop
 * (ft8_shim.c:1485-1513) -- unlike every prior entry above, this DOES
 * touch the production decode path.
 *
 *   Defect: for any candidate whose time_offset < 0 (an ordinary outcome
 *   of ftx_find_candidates()'s -10..+19 search range, meaning the signal's
 *   true sync position precedes the nominal 15 s decode window), the
 *   per-block symbol index used to read tones[] was derived as
 *   tones[b - b0] where b0 is time_offset CLAMPED to a non-negative floor
 *   -- not the true, unclamped time_offset. This silently re-anchored
 *   symbol 0 to the wrong absolute block, so every one of the up to 79
 *   averaged samples was read from the wrong tone bin, under-reporting
 *   SNR by roughly 15-20 dB. The loop's upper bound (b1 = b0 + FT8_NN)
 *   was computed from the same clamped b0, so no iterations were skipped
 *   either -- the corruption was total, not partial.
 *
 *   Fix: b1 is now computed from the unclamped time_offset
 *   (time_offset + FT8_NN, then clipped to mon.wf.num_blocks as before),
 *   and the per-iteration symbol index is tones[b - time_offset]
 *   (unclamped). b0 itself is unchanged -- it still exists solely to
 *   keep the waterfall block read non-negative. Both bounds move
 *   together: fixing the index alone without narrowing b1 to match would
 *   let tone_col run past FT8_NN - 1, an out-of-bounds read of the
 *   79-element tones[] array. ft8_lib's own convention
 *   (patched/ft8/decode.c:160,226: `if (block_abs < 0) continue;`,
 *   computed from the unclamped time_offset) already handles this
 *   correctly; this shim now mirrors it.
 *
 *   Confirmed mechanically: qa/rr-study/2026-08-22-1454-qa-to-architect-
 *   b-dt-c3-results.md (arm B-dt-C3) measured a 17.4 dB step in reported
 *   SNR co-located exactly with the block at which time_offset turns
 *   negative -- ~210x larger than the largest deficit a benign "signal
 *   partly outside the window" explanation could produce there (0.083 dB).
 *
 *   cnt (the sample count signal_db is averaged over) may now legitimately
 *   be smaller than 79 for early-arriving signals -- thinned by missing
 *   leading blocks, which is correct, rather than corrupted by wrong
 *   ones, which was the prior behaviour. No change to
 *   compute_local_noise_floor_db (the SNR formula's other term, unaffected
 *   by this defect). No ABI break, no struct layout change (FT8Result
 *   stays 48 bytes), no new export -- this is a correctness fix to an
 *   always-active production code path.
 *
 *   20260047 — f001-sup-b-instrumented-suppression-sizing: adds three new
 *              exported read-only getters -- ft8_get_h12_displaying_count(),
 *              ft8_get_h12_ambiguous_count(), ft8_get_h12_divergent_count() --
 *              counting how many EMITTED decodes resolved via the 12-bit
 *              nonstandard-callsign hash path, how many of those hit an
 *              ambiguous (>=2-entry) probe chain, and how many of THOSE had
 *              their most-recently-announced match differ from the first
 *              (displayed) one. Adds a uint32_t announce_stamp field to
 *              callsign_entry_t (64 KB -> 80 KB table, not ABI-visible --
 *              never marshalled to C#), stamped in hash_table_add only, never
 *              in hash_table_lookup. MEASURE-ONLY: hash_table_lookup's return
 *              value and the callsign it writes are byte-for-byte unchanged;
 *              the new counting walk is a separate, read-only function.
 *              hash_table_add's existing reject-on-full and already-known
 *              no-op behaviour is unchanged. No change to the 4096-slot
 *              capacity or eviction policy.
 *
 *   20260048 — f001-sup-b-amendment-2-cluster-instrumentation: adds one new
 *              exported read-only getter, ft8_get_h12_by_code(), returning a
 *              complete 4096-row per-code (n12) breakdown of the three
 *              20260047 scalars -- displaying/ambiguous/divergent counts
 *              indexed by the 12-bit callsign-hash code itself, plus an
 *              out-of-range violation count. Backs spec Sec.6.2's clustered
 *              95% bootstrap, which needs cluster IDENTITY, not just
 *              cumulative totals. Mechanism: one new thread-local
 *              (tls_h12_code, set unconditionally in cb_lookup_hash's
 *              existing 12-bit branch) and one new fixed 4096 x 3 static
 *              table incremented alongside the existing scalars, inside the
 *              SAME unchanged guard condition, at the SAME emission site.
 *              hash_table_lookup and cb_lookup_hash's return/output values
 *              are unaffected. No struct layout change, no ABI break to any
 *              existing export. The three 20260047 scalars are unchanged and
 *              remain the sufficient-statistic source for anything that does
 *              not need cluster identity.
 *
 *   20260049 — f001-h12-unique-match-suppression: implements the Option A decision
 *              ("NO NAME BEATS A WRONG NAME", qa/rr-study 2026-09-01) that SUP-B's
 *              instrumentation was built to size. UNLIKE 20260047 and 20260048, THIS
 *              BUMP CHANGES DECODE OUTPUT: cb_lookup_hash now returns "not found" for a
 *              12-bit callsign-hash lookup whose probe chain holds >=2 matching entries
 *              (tls_h12_multiplicity >= 2), so an ambiguous match renders the existing
 *              "<...>" placeholder instead of a (possibly wrong) name. The decode itself
 *              is never affected -- native/ft8_lib_vendor/ is not modified, and its
 *              lookup_callsign already handles a "not found" 12-bit result as a normal,
 *              non-error render path (message.c:594-614,431). hash_table_lookup,
 *              hash_table_add and announce_stamp are byte-for-byte unchanged; the 22-bit
 *              and 10-bit hash paths are untouched. Adds one new exported read-only
 *              getter, ft8_get_h12_suppressed_count(), incremented at the SAME emission
 *              site as the three SUP-B scalars (never inside cb_lookup_hash -- that would
 *              count decode attempts, not displays). The three SUP-B scalars
 *              (displaying/ambiguous/divergent) are UNCHANGED in meaning and continue to
 *              report what *would* have been displayed, so every reading already taken
 *              under 20260047/20260048 stays comparable to a run at this version.
 */
#define FT8_SHIM_VERSION 20260049

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
 * ft8_get_hash_table_reject_count — return the process-lifetime count of Type 4
 * callsign announcements discarded because the session-scoped callsign hash table
 * (g_session_hash_table) was already at its HASH_TABLE_SIZE capacity (4096 since shim
 * 20260038; 256 before) (f-005-hash-table-saturation-diagnostic).
 *
 * Read-only and side-effect-free: reading it never resets the counter or alters the
 * hash table.  Unlike the per-thread noise-floor / pass-count getters this reflects a
 * process-global counter, so it may be read from any thread (e.g. the daemon's
 * shutdown path) regardless of which thread last called ft8_decode_all.
 * Returns 0 if the table has never reached capacity this session.
 */
int ft8_get_hash_table_reject_count(void);

/*
 * ft8_get_h12_displaying_count / ft8_get_h12_ambiguous_count /
 * ft8_get_h12_divergent_count — SUP-B (shim 20260047). See ft8_shim.c for the
 * full doc comment. Process-global, read-only, process-lifetime cumulative,
 * zero on daemon restart. MEASURE-ONLY: no effect on decode output.
 */
int ft8_get_h12_displaying_count(void);
int ft8_get_h12_ambiguous_count(void);
int ft8_get_h12_divergent_count(void);

/*
 * ft8_get_h12_suppressed_count — f001-h12-unique-match-suppression (shim 20260049). See
 * ft8_shim.c for the full doc comment. Process-global, read-only, process-lifetime cumulative,
 * zero on daemon restart. UNLIKE its three siblings above, this getter's underlying counter
 * corresponds to a change in decode OUTPUT (a suppressed callsign renders "<...>").
 */
int ft8_get_h12_suppressed_count(void);

/*
 * ft8_get_h12_by_code — SUP-B Amendment 2 (shim 20260048). See ft8_shim.c for
 * the full doc comment. Process-global, read-only, process-lifetime
 * cumulative, zero on daemon restart. MEASURE-ONLY: no effect on decode
 * output. Returns H12_CODE_SPACE (4096) on success, -1 on any bad argument.
 */
int ft8_get_h12_by_code(int* displaying, int* ambiguous, int* divergent,
                         int capacity, int* out_of_range);

/*
 * ft8_get_last_candidate_counts — return per-pass candidate counts from the
 * most recent ft8_decode_all call on this thread.
 *
 * out_counts[i] = number of candidates returned by ftx_find_candidates() in
 * pass i, BEFORE any LDPC decode attempt.  Compare with ft8_get_last_pass_counts
 * (which counts successful decodes) to distinguish candidate-generation failure
 * from LDPC convergence failure.
 *
 * Parameters and threading contract identical to ft8_get_last_pass_counts.
 */
int ft8_get_last_candidate_counts(int* out_counts, int capacity);

/*
 * ft8_get_last_llr_stats — return per-pass LLR statistics from the most recent
 * ft8_decode_all call on this thread (redesigned at shim 20260020).
 *
 * out_mean_abs[i]        — post-normalisation mean abs(LLR) across all
 *                          LDPC-failing candidates in pass i.  0.0f if none.
 * out_prenorm_variance[i]— pre-normalisation variance of the raw log174 array,
 *                          averaged across LDPC-failing candidates in pass i.
 *                          A small value (near 0) indicates near-zero bit confidence
 *                          and cannot be rescued by normalisation — the confirmed
 *                          root cause of D-001 equal-SNR co-channel failures.
 *                          0.0f if no candidates failed in that pass.
 * out_fail_count[i]      — count of LDPC-failing candidates in pass i.
 * capacity               — size of all three output arrays; ≥ K_MAX_PASSES.
 *
 * Returns: number of passes actually executed (≤ capacity).
 * Threading contract: identical to ft8_get_last_pass_counts.
 */
int ft8_get_last_llr_stats(
    float* out_mean_abs,
    float* out_prenorm_variance,
    int*   out_fail_count,
    int    capacity);

/*
 * ft8_get_last_snr_terms — return the two terms of the per-signal SNR
 * formula for every decode returned by the most recent ft8_decode_all call
 * on THIS thread (Amendment 2, corrected by Amendment 3, shim 20260045).
 *
 *   snr = signal_db - local_noise_db - 26.5f      (ft8_shim.c:1474)
 *
 * out_signal_db[i] / out_local_noise_db[i] correspond to results[i] from
 * that same call -- INDEX-ALIGNED, same order (AC-N3, the count contract:
 * this function's own return value must equal ft8_decode_all's own return
 * value for the same call).
 *
 * Either out pointer may be NULL to request only the other array. If BOTH
 * are NULL, the function writes nothing and returns the count it would
 * have written (Amendment 3 correction 4(c)).
 * Writes at most `capacity` entries; returns the number written.
 * Returns -1 if capacity < 0.
 *
 * Read-only diagnostic getter: no production call site anywhere calls this
 * function; it is reachable only from test code and QA harnesses, exactly
 * like ft8_get_last_pass_counts / ft8_get_last_candidate_counts /
 * ft8_get_last_llr_stats.
 *
 * Threading: same contract as ft8_get_last_pass_counts -- must be called
 * from the thread that called ft8_decode_all.
 */
int ft8_get_last_snr_terms(
    float* out_signal_db,
    float* out_local_noise_db,
    int    capacity);

/*
 * ft8_set_ap_bits — supply known AP bit constraints for the next decode cycle
 * (H6 directed AP decode, shim 20260020).
 *
 * Call before ft8_decode_all.  The AP bits are applied only during pass 0
 * (the primary pass); pass 1 (spectrogram-suppressed) always uses the
 * waterfall-derived LLRs unchanged.
 *
 * Parameters:
 *   mycall_bits      — 28-bit packed mycall (MSB first, one bit per bit position
 *                      in the FT8 77-bit payload).  log174[0..27] are overridden.
 *   num_mycall_bits  — number of valid bits in mycall_bits (0..28).
 *                      Pass 0 to disable AP constraints entirely (default state).
 *   hiscall_bits     — 28-bit packed hiscall.  log174[28..55] are overridden.
 *   num_hiscall_bits — number of valid bits in hiscall_bits (0..28).
 *
 * Bits are packed MSB-first in each byte: bit 0 is the MSB of mycall_bits[0],
 * bit 7 is the LSB of mycall_bits[0], bit 8 is the MSB of mycall_bits[1], etc.
 * This matches the pack_callsign() convention in ft8_lib/ft8/message.c.
 *
 * Thread-safe when called from the same thread that calls ft8_decode_all
 * (the C# caller serialises these calls — no mutex needed).
 */
void ft8_set_ap_bits(
    const uint8_t* mycall_bits,  int num_mycall_bits,
    const uint8_t* hiscall_bits, int num_hiscall_bits);

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
 * Thread-safe (per-thread): saves and restores the TLS hash-table pointer for the
 * duration of the call; each OS thread has its own TLS slot so concurrent calls
 * on separate threads do not interfere with each other.
 */
int ft8_encode_message(const char* message, uint8_t* tones_out, int tones_capacity);

/*
 * ft8_set_decode_params — update the three runtime-configurable OSD gate parameters
 * (decoder-settings-page, shim 20260030).
 *
 * Parameters:
 *   k_min_score_pass2  — pass-1 candidate score floor (default 10, valid [5, 30]).
 *                        Lower values admit more pass-1 candidates (higher sensitivity
 *                        and more false positives); higher values are more selective.
 *   osd_corr_threshold — OSD normalised correlation gate (default 0.10f, valid [0.05, 0.40]).
 *                        Candidates whose normalised inner-product score is below this
 *                        threshold are rejected as likely noise CRC-14 coincidences.
 *   osd_nhard_max      — OSD maximum Hamming-distance gate (default 60, valid [30, 100]).
 *                        Candidates with more hard-decision bit errors than this are rejected.
 *
 * Values take effect on the next ft8_decode_all call.  The default values (10, 0.10f, 60)
 * match the D-009 calibrated operating point established at shim 20260029; calling this
 * function with those defaults produces identical behaviour to shim 20260029.
 *
 * Thread safety: module-level write vs. thread-pool reads; a missed update means one decode
 * cycle uses old values, which is acceptable.  No mutex needed in practice.
 *
 * Safe to call before the first ft8_decode_all invocation.
 */
void ft8_set_decode_params(int k_min_score_pass2, float osd_corr_threshold, int osd_nhard_max);

/*
 * ft8_refine_candidate -- diagnostic-only per-candidate coherent sync
 * refinement (r1-sync-refiner-instrument-validation, shim 20260040).
 *
 * Given the cycle's retained PCM and a candidate's coarse (freq_hz,
 * time_offset) as reported by ftx_find_candidates()/ft8_decode_all's own
 * freq_hz/dt convention, returns a refined (delta_f, delta_t) RELATIVE TO
 * that coarse position, plus a sync quality score.
 *
 * Implemented in native/ft8_lib_vendor/refine/sync_refiner.c -- see that
 * file for the three-stage search (coarse time -> frequency -> fine time)
 * and the coherent-correlation method. NOT called from ft8_decode_all or
 * any other production entry point in this file; reachable only from the
 * validation harness and test code.
 *
 * Parameters:
 *   pcm                    -- float32 samples, 12 kHz mono, normalised to [-1, 1]
 *   pcm_len                -- must be 180 000 (15 s x 12 000 Hz)
 *   coarse_freq_hz         -- coarse candidate frequency (Hz), i.e. tone 0's
 *                             estimated frequency from the waterfall lattice
 *   coarse_time_offset_s   -- coarse candidate time offset (s) from cycle start
 *   out_delta_freq_hz      -- refined frequency correction (Hz), ADD to
 *                             coarse_freq_hz for the refined estimate
 *   out_delta_time_s       -- refined time correction (s), ADD to
 *                             coarse_time_offset_s for the refined estimate
 *   out_sync_score         -- coherent Costas correlation magnitude at the
 *                             refined (delta_f, delta_t); larger = stronger
 *                             sync confidence. Not calibrated against any
 *                             existing score; diagnostic use only.
 *   out_coarse_dt_samp     -- (r1b, shim 20260041) Stage A+B's own coarse-
 *                             time selection, sample index at the ~200 Hz
 *                             working rate, range [-12, 12]. Diagnostic only.
 *   out_fine_dt_samp       -- (r1b, shim 20260041) Stage C's own fine-time
 *                             selection, sample index at the ~2000 Hz working
 *                             rate, range [-20, 20]. Diagnostic only.
 *
 *                             out_coarse_dt_samp / 200.0 + out_fine_dt_samp /
 *                             2000.0 SHALL equal out_delta_time_s to within
 *                             float32 rounding tolerance (the two new
 *                             parameters are the decomposition of the
 *                             existing out_delta_time_s sum, not a
 *                             replacement for it).
 *
 * Returns: 0 on success.
 *          -1 if pcm_len != 180 000, or any pointer parameter is NULL.
 *          -2 if an internal heap allocation failed.
 */
int ft8_refine_candidate(
    const float* pcm, int pcm_len,
    int   coarse_freq_hz, float coarse_time_offset_s,
    float* out_delta_freq_hz,
    float* out_delta_time_s,
    float* out_sync_score,
    int*   out_coarse_dt_samp,
    int*   out_fine_dt_samp);

/*
 * ft8_extract_llrs_at -- diagnostic-only extract-LLRs-at-position export
 * (n1-extract-llrs-at-position, shim 20260042).
 *
 * Builds a waterfall from the supplied PCM exactly as ft8_decode_all does,
 * snaps the caller-supplied (freq_hz, time_offset_s) to the nearest point on
 * the SAME frequency/time lattice production candidates already live on
 * (K_FREQ_OSR / K_TIME_OSR, unchanged), and runs the existing, unmodified
 * ft8_extract_likelihood() extraction path at that position -- the exact
 * logic production uses for every candidate, unmodified.
 *
 * Returns the RAW, PRE-NORMALISATION 174 log-likelihoods -- ftx_normalize_logl()
 * is deliberately NOT applied. Normalisation is a positive scale factor and does
 * not change hard-decision sign, but N1's harness (c2_phase2c_ber_measurement.py's
 * hard_decision_ber()) documents and depends on the raw, unnormalised value.
 *
 * Not a continuous-position extractor: the waterfall itself is discretised at
 * K_FREQ_OSR / K_TIME_OSR; this export snaps to the nearest lattice point
 * exactly as every existing candidate already does.
 *
 * No production call site: reachable only from test code and QA harnesses
 * invoking it directly (e.g. Python ctypes). ft8_decode_all's production
 * decode path, candidate selection, and every existing exported symbol are
 * unaffected.
 *
 * Parameters:
 *   pcm            -- float32 samples, 12 kHz mono, normalised to [-1, 1]
 *   pcm_len        -- must be 180 000 (15 s x 12 000 Hz)
 *   freq_hz        -- requested centre frequency, Hz
 *   time_offset_s  -- requested time offset from cycle start, seconds
 *   out_llr174     -- caller-allocated FTX_LDPC_N (174) floats; receives the
 *                     raw log-likelihoods on success, untouched otherwise
 *
 * Returns: 0 on success.
 *          -1 if pcm_len != 180 000, or out_llr174 is NULL.
 *          -2 if an access violation or other SEH fault occurs inside the
 *             waterfall/extraction pipeline (MSVC / Windows builds only).
 *          -3 if the resolved frequency bin falls outside the waterfall's
 *             valid range [0, num_bins) -- rejected, not silently clamped:
 *             a caller-supplied position, unlike ftx_find_candidates()'s own
 *             output, carries no guarantee of being in-band.
 */
int ft8_extract_llrs_at(
    const float* pcm, int pcm_len,
    float freq_hz, float time_offset_s,
    float* out_llr174);

/*
 * ft8_coherent_llr_at -- diagnostic-only per-candidate coherent multi-symbol
 * LLR formation (r2-coherent-llr-instrument, Route B2 Phase 1, shim 20260043).
 *
 * Given the cycle's retained PCM and a candidate's EXISTING, UNREFINED grid
 * position (freq_hz, time_offset_s -- the same physical-unit convention
 * ft8_extract_llrs_at already uses, snapped to the identical K_FREQ_OSR/
 * K_TIME_OSR lattice), forms 174 coherent per-bit LLRs by downconverting to
 * complex baseband (phase retained, reusing sync_refiner.c's own
 * downconvert_decimate), correlating coherently against each of the 8 tone
 * hypotheses per data symbol (complex accumulation across the symbol,
 * magnitude last), combining 1-, 2- and 3-symbol coherent windows via
 * max-log per bit, and normalising to the scale ftx_normalize_logl produces.
 * Implemented in native/ft8_lib_vendor/refine/coherent_llr.c -- see that
 * file for the full algorithm, the bit-index convention (deliberately NOT
 * decode.c's own unreachable ft8_decode_multi_symbols convention), and the
 * signature-choice rationale.
 *
 * NEVER calls ft8_refine_candidate() or any other position-search routine
 * (design.md D1) -- the position given is used as-is. Reachable only from
 * test code and the Phase 1 gate harness; ftx_decode_candidate() and
 * ft8_decode_all's production decode path are unaffected.
 *
 * Calling this with the SAME (freq_hz, time_offset_s) already passed to
 * ft8_extract_llrs_at guarantees both extractions ran at the identical
 * candidate position (spec.md's own candidate-identity requirement) with no
 * extra bookkeeping.
 *
 * Parameters:
 *   pcm            -- float32 samples, 12 kHz mono, normalised to [-1, 1]
 *   pcm_len        -- must be 180 000 (15 s x 12 000 Hz)
 *   freq_hz        -- requested centre frequency, Hz (tone 0's frequency)
 *   time_offset_s  -- requested time offset from cycle start, seconds
 *   out_log174     -- caller-allocated FTX_LDPC_N (174) floats; receives the
 *                     normalised coherent log-likelihoods on success,
 *                     untouched otherwise
 *
 * Returns: 0 on success.
 *          -1 if pcm_len != 180 000, or pcm/out_log174 is NULL.
 *          -2 if a heap allocation failed.
 *          -3 if the resolved frequency bin falls outside the waterfall's
 *             valid range -- rejected, not silently clamped (same discipline
 *             ft8_extract_llrs_at already uses for a caller-supplied
 *             position with no ftx_find_candidates()-style in-band
 *             guarantee).
 *
 * UNVALIDATED: a new correlator with no prior measurement -- see this
 * file's r2-coherent-llr-instrument changelog entry above.
 */
int ft8_coherent_llr_at(
    const float* pcm, int pcm_len,
    float freq_hz, float time_offset_s,
    float* out_log174);

/*
 * ft8_ldpc_decode_llrs -- diagnostic-only LLR-vector decode probe (B4,
 * r2-coherent-llr-instrument Phase B Amendment 1, shim 20260044).
 *
 * Decodes a caller-supplied 174-element RAW (pre-normalisation) LLR vector
 * through production's own bp_decode -> OSD (conditional) -> CRC-14
 * sequence, mirroring ftx_decode_candidate (patched/ft8/decode.c:641-713)
 * exactly, so a diagnostic LLR vector (from ft8_extract_llrs_at or
 * ft8_coherent_llr_at) can be converted into a CRC-verified decode count
 * rather than a modelled BER-threshold crossing. See
 * patched/ft8/decode.c's ftx_ldpc_decode_llrs (this function's underlying
 * implementation -- this is a thin wrapper, ft8_shim.c has no logic of its
 * own beyond a NULL check) for the full 7-step sequence and a note on why
 * its control flow mirrors decode.c's own literal branch structure rather
 * than the Amendment 1 spec's plain-English paraphrase of it.
 *
 * Reachable only from test code and QA harnesses invoking it directly
 * (e.g. Python ctypes) -- no production call site in ft8_decode_all or
 * anywhere else in this file. No C# Ft8LibInterop/IFt8NativeInterop
 * binding is added for this export (design.md D10).
 *
 * Parameters:
 *   llr174           -- IN: 174 RAW, pre-normalisation LLRs. Never
 *                        modified (B4-c) -- copied internally before
 *                        bp_decode, which writes through its argument.
 *   max_iters        -- IN: bp_decode iteration cap.
 *   osd_depth        -- IN: OSD ndeep passed to osd_decode; < 0 disables
 *                        the OSD fallback entirely (BP-only probe run).
 *   out_a91          -- OUT: 91 bits (12 bytes), payload+CRC; may be NULL
 *                        if the caller only needs crc_ok/out_path.
 *   out_ldpc_errors  -- OUT: bp_decode's own error count (reset to 0 if
 *                        the OSD fallback is the path that succeeded).
 *   out_path         -- OUT: 0 = BP converged, 1 = OSD fallback succeeded,
 *                        -1 = neither (no CRC-valid codeword found).
 *   out_crc_ok       -- OUT: 1 iff the extracted CRC-14 equals the
 *                        computed CRC-14 on the accepted codeword; 0
 *                        otherwise (including when out_path == -1).
 *
 * Returns: 0 on success -- a decode was attempted and every output
 *          parameter is valid; out_crc_ok is the actual answer, this
 *          return code only reports whether the probe ran.
 *          -1 if llr174 or any non-optional OUT pointer is NULL.
 *          -2 if the input LLR vector has zero variance (degenerate;
 *             ftx_normalize_logl would divide by zero) -- no
 *             normalisation attempted, no crash, no NaN (B4-d).
 */
int ft8_ldpc_decode_llrs(
    const float* llr174,
    int          max_iters,
    int          osd_depth,
    uint8_t*     out_a91,
    int*         out_ldpc_errors,
    int*         out_path,
    int*         out_crc_ok);

#ifdef __cplusplus
}
#endif

#endif /* FT8_SHIM_H */
