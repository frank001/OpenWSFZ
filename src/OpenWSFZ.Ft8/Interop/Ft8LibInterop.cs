using System.Runtime.InteropServices;

namespace OpenWSFZ.Ft8.Interop;


/// <summary>
/// P/Invoke binding layer between managed C# and the native <c>libft8.dll</c> shim.
///
/// <para>
/// The DLL is loaded lazily on the first call to <see cref="DecodeAll"/> via
/// <see cref="NativeLibrary.Load"/> from <c>AppContext.BaseDirectory</c>.
/// An ABI self-test (<c>ft8_lib_version_check</c>) runs immediately after loading;
/// a version mismatch throws <see cref="InvalidOperationException"/> before any
/// decode call is attempted.
/// </para>
///
/// <para>
/// This class is sealed, static-only (all members static), and thread-safe after
/// the lazy init completes.  <see cref="DecodeAll"/> must be called from a single
/// thread (matching <c>Ft8Decoder.DecodeAsync</c> which is already single-threaded
/// after the p12 rewrite).
/// </para>
/// </summary>
internal static class Ft8LibInterop
{
    /// <summary>
    /// The compile-time version constant embedded in the shim (<c>FT8_SHIM_VERSION</c>).
    /// Must match the value returned by <c>ft8_lib_version_check()</c>.
    /// History: 20240001 (single-pass), 20260001 (p15 iterative subtraction),
    /// 20260002 (R6 weak-signal correction removed — R&amp;R-001 linearity fix;
    ///           revert-pcm-sic: PCM-domain SIC reverted, two-pass spectrogram suppression restored),
    /// 20260004 (fix-d001-revised Option B: hard-zero tile suppression replaced with soft
    ///           SNR-scaled linear attenuation; version 20260003 skipped — was the reverted PCM-SIC),
    /// 20260005 (D-003 diagnostics: add ft8_get_last_noise_floor_db TLS getter; no decode change),
    /// 20260006 (D-002 fix: SNR bandwidth constant -26.0 → -26.5 dB; bias calibration).
    /// Note: 20260007 (diag-D001-three-pass-sic, K_MAX_PASSES 2→3) was tried and reverted —
    ///   S7 R&amp;R result −4.30 pp regression; H2 rejected. See results/2026-06-12-3ecf8ae/report-v2.md.
    /// 20260008 (diag-d001-pcm-sic, H3 diagnostic): PCM-domain SIC replaces spectrogram suppression
    ///   in the inter-pass stage.  For each pass-0 decoded signal a CP-FSK waveform is synthesised
    ///   (heap-allocated synth_buf, phase zero, no Gaussian shaping), scaled via least-squares
    ///   projection, and subtracted from a heap-allocated PCM residual.  Pass 1 operates on a
    ///   waterfall rebuilt from the residual via a second monitor_t.  No change to K_MAX_PASSES,
    ///   MaxDecodePasses, or MaxResults.  Version 20260007 slot skipped (was the reverted 3-pass SIC).
    ///   SUPERSEDED by 20260009 (H3b GFSK quadrature SIC).
    /// 20260009 (diag-d001-h3b-gfsk-sic, H3b diagnostic): GFSK quadrature SIC replaces CP-FSK
    ///   scalar SIC.  <c>synth_ft8_gfsk_quad</c> produces I (sin) and Q (cos) quadrature components
    ///   using a normalised Gaussian pulse (BT=2.0, 3-symbol span, matching the QA Python synthesiser).
    ///   <c>compute_quadrature_amplitude</c> estimates amplitude and phase analytically (O(N), exact
    ///   for any carrier phase).  Three additional heap buffers in the pass-1 SIC stage:
    ///   synth_buf_q, gfsk_kernel, gfsk_prefix; total PCM-domain SIC heap increases from
    ///   ~1.44 MB to ~2.21 MB.  No change to K_MAX_PASSES, MaxDecodePasses, or MaxResults.
    ///   REJECTED (H3b): S7 overall 37.63% vs 54.84% baseline (−17.21 pp); P0/P1 both 0/6.
    ///   PCM-domain SIC alone cannot match spectrogram suppression baseline.
    ///   SUPERSEDED by 20260010.
    /// 20260010 (diag-d001-h4-spectrogram-reinstate, H4): H3b PCM-domain GFSK quadrature SIC
    ///   call site removed; spectrogram-domain soft-SNR tile suppression reinstated as the sole
    ///   inter-pass mechanism (<c>suppress_candidate_tiles</c> loop, as in 20260006).  GFSK
    ///   helpers retained in shim source but not called.  D-003 TLS diagnostic retained.
    ///   Single-variable recovery experiment (H4) for D-001 co-channel decode gap.
    ///   ACCEPTED: S7 56.99% (53/93), +2.15 pp vs 54.84% pre-H4 baseline.
    ///   Active S7 baseline. FT8_SHIM_VERSION reverted to 20260010 after H5 rejection.
    /// 20260011 (diag-d001-h5-suppression-tuning, H5): suppression ramp shifted 10 dB toward
    ///   lower SNRs: <c>K_SOFT_SUPP_SNR_MIN_DB</c> −5.0 → −15.0 dB,
    ///   <c>K_SOFT_SUPP_SNR_MAX_DB</c> +15.0 → +5.0 dB.  At 0 dB SNR (S7 test condition)
    ///   suppression increases from 25% (H4) to 75% (H5).  No other shim logic, pass
    ///   configuration, or struct layout changed.  Single-variable diagnostic experiment (H5)
    ///   for D-001 co-channel decode gap.
    ///   REJECTED: S7 overall 43/93 = 46.24% (−10.75 pp vs H4 baseline).
    ///   Over-suppression confirmed.  FT8_SHIM_VERSION reverted to 20260010.
    /// 20260012 (fix-d004-local-noise-floor): per-signal local noise floor replaces the global
    ///   histogram-median in the SNR formula.  <c>compute_local_noise_floor_db</c> samples
    ///   waterfall bins in a K=32-bin sideband window on each side of the decoded signal's
    ///   8-tone span (200 Hz per sideband at 6.25 Hz/bin), taking the histogram median of
    ///   those samples across all time blocks and all time/freq sub-samples.  The global noise
    ///   floor is retained for per-cycle diagnostic logging (<c>ft8_get_last_noise_floor_db</c>)
    ///   but is no longer used in the per-signal SNR formula.  <c>FT8Result</c> struct layout
    ///   is unchanged (48 bytes); this is not an ABI break.  Resolves D-003 and D-004: the
    ///   audio-chain rolloff (up to −22 dB at 2800–3000 Hz) drove the global-noise-floor-based
    ///   SNR to be systematically under-reported at high frequencies; local noise tracks the
    ///   same rolloff and eliminates this frequency-dependent bias.
    ///   Version 20260011 slot used for H5 suppression diagnostic (REJECTED; reverted);
    ///   20260012 is the D-003/D-004 fix, not a D-001 hypothesis.
    /// 20260013 (fix-seh-av-containment): <c>__try/__except(EXCEPTION_EXECUTE_HANDLER)</c>
    ///   wrapper added around the body of <c>ft8_decode_all</c> (MSVC / Windows builds only).
    ///   On any access violation (0xC0000005) the shim now returns -2 instead of crashing
    ///   the process; the managed layer (<see cref="DecodeAll"/>) translates -2 into a
    ///   <see cref="NativeAccessViolationException"/>, which <see cref="Ft8Decoder"/> catches,
    ///   logs at WARNING, and converts to an empty-result skip.
    ///   Struct layout unchanged (48 bytes).  Return-code -2 is a semantic addition
    ///   (new contract term), hence the version bump.  Non-MSVC builds are unaffected
    ///   (no SEH; SIGSEGV behaviour unchanged on Linux/macOS).
    ///   Root cause of the AV (D-006) remains under investigation.
    /// 20260014 (diag-d006-minidump): MiniDumpWriteDump capture moved from the
    ///   <c>__except</c> body into a dedicated <c>ft8_av_exception_filter()</c> function
    ///   called in the filter-expression position.  <c>GetExceptionInformation()</c> is
    ///   valid only during filter evaluation (before stack unwind); the v20260013 approach
    ///   called MiniDumpWriteDump in the handler body after unwind, leaving
    ///   <c>EXCEPTION_POINTERS</c> stale and producing a dump with no ExceptionStream
    ///   (crash address unknown).  The filter writes <c>MiniDumpWithFullMemory</c> to
    ///   <c>C:\Dumps\</c> with valid <c>EXCEPTION_POINTERS</c> before returning
    ///   <c>EXCEPTION_EXECUTE_HANDLER</c>.  No ABI change; struct layout unchanged.
    /// 20260015 (fix-d006-ptr-truncation): Binary patch to message.obj fixing a 32-bit
    ///   pointer truncation in <c>ftx_message_decode()</c> (ft8/message.c, kgoba/ft8_lib
    ///   v2.0).  Crash-dump analysis of ft8_av_20260614_133145_28356.dmp (shim 20260014,
    ///   ExceptionAddress RVA 0x3D06) revealed: MSVC generated <c>MOVSXD RBX, EAX</c>
    ///   (sign-extend 32-bit) instead of <c>MOV RBX, RAX</c> (full 64-bit move) to
    ///   capture the <c>char*</c> return from an internal stpcpy() call.  When the thread
    ///   stack or caller-supplied buffer resides above the 4 GB VA boundary the upper 32
    ///   bits of the pointer are silently dropped, producing an invalid write address
    ///   (WRITE AV to 0x37E3B0BA; correct address 0x1737E3B0B6).  Only triggered by FT8
    ///   messages with the "R " reply-prefix (i3/n3 bit 0x20 set).  Fix: opcode byte at
    ///   message.obj offset 0x01B27 changed 0x63 (MOVSXD) to 0x8B (MOV); DLL rebuilt.
    ///   No ABI change; struct layout and return codes unchanged.  D-006 RESOLVED.
    /// 20260016 (fix-d006-cleanup + fix-rq2-signal-db-oob): Removed
    ///   <c>ft8_av_exception_filter()</c> and MiniDumpWriteDump infrastructure —
    ///   hardcoded <c>C:\Dumps\</c> path and WinAPI diagnostic code removed; the
    ///   <c>__try/__except</c> containment reverts to simple
    ///   <c>EXCEPTION_EXECUTE_HANDLER</c> (shim 20260013 form).  Also fixes RQ-2:
    ///   signal_db loop now guards <c>freq_offset + tone_col >= num_bins</c> for
    ///   signals ≥ 2956 Hz, skipping out-of-range samples rather than reading past
    ///   the waterfall row boundary.  No ABI change.
    /// 20260017 (ft8-qso-answerer-v1): Adds <c>ft8_encode_message</c> — the TX encode
    ///   entry point. Uses <c>ftx_message_encode()</c> + <c>ft8_encode()</c> to convert
    ///   text → 79 tone indices.  No change to existing entry points or struct layout.
    /// 20260018 (diag-d001-candidate-counts): Adds <c>ft8_get_last_candidate_counts</c> —
    ///   a TLS getter exposing the per-pass count of candidates returned by
    ///   <c>ftx_find_candidates()</c> before any LDPC decode attempt.  Compare with
    ///   <see cref="GetLastPassCounts"/> to distinguish candidate-generation failure
    ///   (result[i] is low) from LDPC convergence failure (result[i] is high but
    ///   GetLastPassCounts[i] is zero).  No change to decode logic or struct layout.
    /// 20260019 (diag-d001-llr-mean-abs): Adds <c>ft8_get_last_llr_stats</c> —
    ///   per-pass mean abs(LLR) across LDPC-failing candidates. Counterpart
    ///   function <c>ftx_compute_candidate_llr_mean_abs</c> added to decode.c
    ///   (non-static); replicates likelihood extraction + normalisation without
    ///   calling bp_decode.  No change to existing entry points or struct layout.
    /// 20260020 (diag-d001-h6-ap-probe): Two changes:
    ///   (A) Adds <c>ft8_set_ap_bits</c> — directed AP decode setter for H6.
    ///   Supplies known mycall/hiscall bits as hard LLR constraints (±40.0) to
    ///   the pass-0 LDPC input path via <c>ftx_decode_candidate_ap</c> in decode.c.
    ///   C# caller NOT yet wired (interop seam only; <see cref="SetApBits"/> exists
    ///   but <see cref="Ft8Decoder"/> does not call it yet).
    ///   (B) Redesigns <c>ft8_get_last_llr_stats</c>: adds a third output array for
    ///   pre-normalisation variance.  <c>ftx_compute_candidate_llr_mean_abs</c> renamed
    ///   to <c>ftx_compute_candidate_llr_stats</c> with updated signature.  <c>isfinite</c>
    ///   guard added to skip degenerate (NaN) candidates before accumulation.
    /// 20260021 (fix-d001-h6-ap-hiscall-offset): Corrects hiscall AP injection position.
    ///   Shim 20260020 injected hiscall bits at log174[28..55]; the correct positions
    ///   in a standard FT8 i3=1 message are log174[29..56] (bit 28 is the mycall ipa
    ///   suffix flag, not the first hiscall bit).  C# <see cref="Ft8CallsignPacker"/>
    ///   also corrected (wrong character-set ordering for positions 0 and 1, wrong
    ///   N28 offset).  C# AP wiring is now complete for H6.
    /// Note: versions 20260022–20260024 were used only on the unmerged diagnostic
    ///   branch diag/d001-ldpc-iter-hypothesis (H_ITER / H_ITER2 experiments).
    ///   Those version slots are permanently retired and are absent from main.
    /// 20260025 (fix-d001-osd): Ordered Statistics Decoding (OSD) fallback wired
    ///   into <c>ftx_decode_candidate</c> and <c>ftx_decode_candidate_ap</c> in
    ///   patched/ft8/decode.c.  When BP fails to converge (ldpc_errors > 0),
    ///   <c>osd_decode(llr_for_osd, ndeep=2, plain174)</c> is called with the
    ///   pre-BP normalised LLRs, matching WSJT-X's default maxosd=2 at ndepth=3
    ///   (osd174_91.f90, zsave(:,1) LLR snapshot).  Explores up to 529 trial
    ///   codewords (0-/1-/2-flips in the 32 least-reliable free bit positions) and
    ///   returns the first CRC-14 valid hit.  Stack per call: ≈18 KB.
    ///   Also raises <c>K_LDPC_ITERATIONS</c> from 25 → 50 (optimal flooding BP
    ///   count, established in H_ITER diagnostic; retired slots 20260022–20260024).
    ///   No ABI change; struct layout and all existing entry points unchanged.
    ///   Target: close D-001 blind co-channel decode gap to ≥80% MSG-01 at Δ7 Hz.
    /// 20260026 (fix-d009-r2): OSD correlation gate in decode.c (native, both call sites).
    ///   Rejects OSD candidates whose normalised correlation score (corr/norm) is below
    ///   OSD_CORR_THRESHOLD = 0.10.  Closes the text-level ceiling identified in D-009 R1
    ///   verification (d40b4cd, 2026-06-20).  Text-level D9-R3 Gap A and Gap C extensions
    ///   applied in Ft8Decoder.IsPlausibleMessage.
    /// 20260027 (fix-d009-r3): OSD_CORR_THRESHOLD raised 0.10 → 0.15 in decode.c.
    ///   S5 R2 verification (8eea3c4, 2026-06-20): 75.0% FP rate at 0.10 (9 events / 12 slots).
    ///   Category B residual (3-token structurally-valid FPs) and Category C (CQ &lt;...&gt;)
    ///   are not addressable by text filtering; gate calibration is the only lever.
    ///   Text-layer: 4-token non-CQ messages now rejected by IsPlausibleMessage (no shim change).
    /// 20260028 (fix-d009-r5): OSD two-feature gate — nhard Hamming-distance check added
    ///   alongside the existing corr/norm check (D-009 R5).  The R4 single-knob calibration
    ///   loop proved ceilinged: 0 FP on S5 required OSD_CORR_THRESHOLD &gt;= 0.40, which
    ///   conflicts with S7 co-channel decode (needs &lt;= 0.35).  The nhard discriminant is
    ///   orthogonal to corr/norm (magnitude-independent) and mirrors WSJT-X's nharderrors
    ///   metric (osd174_91.f90).  Genuine decodes are Hamming-close to the channel hard
    ///   decisions regardless of SNR; noise CRC-14 coincidences cluster near 87 (= 174/2).
    ///   OSD_CORR_THRESHOLD reverted to 0.10 (nhard carries noise rejection).
    ///   OSD_NHARD_MAX = 60 (calibrated against S5 noise and S7 genuine histograms).
    ///   Text-layer Rules A/B/C added to IsPlausibleMessage: single-token reject (Rule A);
    ///   5+-token reject (Rule B); &quot;CQ &lt;hash&gt;&quot; 2-token reject (Rule C).
    ///   NFR-021: real callsigns replaced with Q-prefix in D009FpFilterTests.cs.
    ///   No ABI change; struct layout unchanged (48 bytes).
    /// </summary>
    private const int ExpectedShimVersion = 20260028;

    /// <summary>
    /// Maximum number of decoded messages per two-pass decode cycle.
    /// Sized to the two-pass output capacity: K_MAX_CANDIDATES (pass 0, 140)
    /// + K_MAX_CANDIDATES_PASS2 (pass 1, 200) = 340.
    /// The <c>results[..count]</c> slice in <see cref="DecodeAll"/> returns only the
    /// populated portion.
    /// </summary>
    private const int MaxResults = 340;  // 140 + 200 (two-pass capacity)

    /// <summary>
    /// Number of decode passes executed by the native shim per cycle.
    /// Mirrors <c>K_MAX_PASSES</c> in <c>ft8_shim.c</c>; both are owned here
    /// so callers do not need to hard-code the pass count separately.
    /// Pass 0: full waterfall (unchanged).
    /// Pass 1: spectrogram-suppressed — for each pass-0 decoded signal the shim
    ///   attenuates that signal's energy in the waterfall using soft SNR-scaled tile
    ///   suppression (<c>suppress_candidate_tiles</c>) before re-running candidate
    ///   search and decode (shim 20260010, H4: ramp [−5, +15]; 25% suppression at 0 dB).
    /// </summary>
    internal const int MaxDecodePasses = 2;

    /// <summary>
    /// Number of tone indices produced by <see cref="EncodeMessage"/> / the native
    /// <c>ft8_encode_message</c> function (fixed by the FT8 specification: 79 symbols).
    /// </summary>
    public const int EncodedToneCount = 79;

    private static readonly object _initLock = new();
    private static volatile bool _initialized;
    // Resolver registration is a one-shot per-assembly operation.  Tracked
    // separately so that a failed verification attempt does not prevent the
    // resolver from being usable on the next retry (SetDllImportResolver throws
    // InvalidOperationException if called a second time on the same assembly).
    private static bool _resolverRegistered;

    // ── P/Invoke declarations ────────────────────────────────────────────

    /// <summary>
    /// ABI sentinel. Returns <see cref="ExpectedShimVersion"/> if the loaded DLL
    /// was compiled from the expected shim source.
    /// </summary>
    [DllImport("libft8.dll", EntryPoint = "ft8_lib_version_check", CallingConvention = CallingConvention.Cdecl)]
    private static extern int NativeVersionCheck();

    /// <summary>
    /// Decode all FT8 signals in a 15-second PCM buffer.
    /// </summary>
    /// <param name="pcm">Float32 samples, 12 kHz mono, normalised to [-1, 1].</param>
    /// <param name="pcmLen">Must be 180 000.</param>
    /// <param name="results">Caller-allocated output buffer.</param>
    /// <param name="maxResults">Size of the <paramref name="results"/> buffer.</param>
    /// <returns>
    /// Number of unique messages written (0..maxResults), or -1 if
    /// <paramref name="pcmLen"/> ≠ 180 000, or -2 if an access violation
    /// was caught by the native SEH wrapper (MSVC / Windows only).
    /// The public <see cref="DecodeAll"/> method translates -2 into
    /// <see cref="NativeAccessViolationException"/>.
    /// </returns>
    [DllImport("libft8.dll", EntryPoint = "ft8_decode_all", CallingConvention = CallingConvention.Cdecl)]
    private static extern int NativeDecodeAll(
        [In] float[]            pcm,
        int                     pcmLen,
        [Out] Ft8NativeResult[] results,
        int                     maxResults);

    /// <summary>
    /// Return per-pass new-decode counts from the most recent
    /// <see cref="NativeDecodeAll"/> call on this thread.
    /// </summary>
    /// <param name="counts">Caller-allocated output array.</param>
    /// <param name="capacity">Size of <paramref name="counts"/>.</param>
    /// <returns>Number of passes actually executed (≤ <paramref name="capacity"/>).</returns>
    [DllImport("libft8.dll", EntryPoint = "ft8_get_last_pass_counts", CallingConvention = CallingConvention.Cdecl)]
    private static extern int NativeGetLastPassCounts(
        [Out] int[] counts,
        int         capacity);

    /// <summary>
    /// Return per-pass candidate counts from the most recent
    /// <see cref="NativeDecodeAll"/> call on this thread.
    /// </summary>
    /// <param name="counts">Caller-allocated output array.</param>
    /// <param name="capacity">Size of <paramref name="counts"/>.</param>
    /// <returns>Number of passes actually executed (≤ <paramref name="capacity"/>).</returns>
    [DllImport("libft8.dll", EntryPoint = "ft8_get_last_candidate_counts", CallingConvention = CallingConvention.Cdecl)]
    private static extern int NativeGetLastCandidateCounts(
        [Out] int[] counts,
        int         capacity);

    /// <summary>
    /// Return per-pass LLR statistics (redesigned at shim 20260020):
    /// mean abs(LLR), pre-normalisation variance, and fail count for
    /// LDPC-failing candidates from the most recent <see cref="NativeDecodeAll"/>
    /// call on this thread.
    /// </summary>
    [DllImport("libft8.dll", EntryPoint = "ft8_get_last_llr_stats",
               CallingConvention = CallingConvention.Cdecl)]
    private static extern int NativeGetLastLlrStats(
        [Out] float[] outMeanAbs,
        [Out] float[] outPrenormVariance,
        [Out] int[]   outFailCount,
        int           capacity);

    /// <summary>
    /// Supply known AP bit constraints for the next decode cycle
    /// (H6 directed AP decode, shim 20260020).
    /// Bits are packed MSB-first; pass <paramref name="numMycallBits"/>==0 to disable.
    /// </summary>
    [DllImport("libft8.dll", EntryPoint = "ft8_set_ap_bits",
               CallingConvention = CallingConvention.Cdecl)]
    private static extern void NativeSetApBits(
        [In] byte[] mycallBits,   int numMycallBits,
        [In] byte[] hiscallBits,  int numHiscallBits);

    /// <summary>
    /// Return the compile-time <c>K_MAX_PASSES</c> constant from the native shim.
    /// Used at initialisation time to detect drift between the C and C# pass-count
    /// constants before any decode call is attempted.
    /// </summary>
    [DllImport("libft8.dll", EntryPoint = "ft8_get_max_passes", CallingConvention = CallingConvention.Cdecl)]
    private static extern int NativeGetMaxPasses();

    /// <summary>
    /// Return the histogram-median waterfall noise floor (dB) from the most recent
    /// <see cref="NativeDecodeAll"/> call on this thread.
    /// Value is <c>median_uint8 * 0.5f − 120.0f</c>, matching the noise_floor_db
    /// used in the SNR formula: <c>SNR = signal_db − noise_floor_db − 26</c>.
    /// Returns 0.0f if <see cref="NativeDecodeAll"/> has not yet been called on this thread.
    /// </summary>
    [DllImport("libft8.dll", EntryPoint = "ft8_get_last_noise_floor_db", CallingConvention = CallingConvention.Cdecl)]
    private static extern float NativeGetLastNoiseFloorDb();

    /// <summary>
    /// Encode a text message to 79 tone indices via <c>ft8_encode_message</c> in the native shim.
    /// </summary>
    /// <param name="message">FT8 message text string.</param>
    /// <param name="tonesOut">Caller-allocated output buffer; must have length ≥ 79.</param>
    /// <param name="tonesCapacity">Length of <paramref name="tonesOut"/>; must be ≥ 79.</param>
    /// <returns>
    /// 79 on success; -1 if capacity &lt; 79; -2 if the message text could not be packed.
    /// </returns>
    [DllImport("libft8.dll", EntryPoint = "ft8_encode_message", CallingConvention = CallingConvention.Cdecl)]
    private static extern int NativeEncodeMessage(
        [MarshalAs(UnmanagedType.LPStr)] string message,
        [Out] byte[] tonesOut,
        int          tonesCapacity);

    // ── Public API ───────────────────────────────────────────────────────

    /// <summary>
    /// Decode all FT8 signals from a 180 000-sample PCM buffer.
    /// Performs <c>K_MAX_PASSES</c> (currently 2) decode passes internally:
    /// pass 0 on the full waterfall; pass 1 on a waterfall with spectrogram-domain
    /// soft-SNR tile suppression applied — each pass-0 decoded signal's tile energy
    /// is attenuated in the waterfall via <c>suppress_candidate_tiles</c> before
    /// pass 1 candidate search begins
    /// (shim version 20260010, H4 suppression ramp [−5, +15]; 25% suppression at 0 dB SNR).
    /// </summary>
    /// <param name="pcm">12 kHz mono float32 PCM, normalised to [-1, 1].</param>
    /// <returns>Array of decoded results (may be empty; never null).</returns>
    /// <exception cref="ArgumentException">
    /// Thrown when <paramref name="pcm"/> does not contain exactly 180 000 samples.
    /// </exception>
    /// <exception cref="NativeAccessViolationException">
    /// Thrown when the native shim catches an access violation (-2 return code,
    /// Windows only).  Callers should catch this, log at WARNING, and skip the cycle.
    /// </exception>
    /// <exception cref="InvalidOperationException">
    /// Thrown if the native DLL cannot be loaded, the ABI version check fails,
    /// or the native shim returns an unexpected negative code other than -2.
    /// </exception>
    public static Ft8NativeResult[] DecodeAll(float[] pcm)
    {
        if (pcm.Length != 180_000)
            throw new ArgumentException(
                $"PCM buffer must be exactly 180 000 samples (15 s × 12 kHz). Got {pcm.Length}.",
                nameof(pcm));

        EnsureInitialized();

        var results = new Ft8NativeResult[MaxResults];
        int count = NativeDecodeAll(pcm, pcm.Length, results, MaxResults);

        // -2 = access violation caught by the SEH wrapper in ft8_decode_all
        //      (MSVC / Windows only).  Throw NativeAccessViolationException so
        //      the caller (Ft8Decoder) can log a WARNING and skip the cycle.
        //      DO NOT call GetLastPassCounts / GetLastNoiseFloorDb after this —
        //      TLS state is unreliable after an AV (R-1 guard).
        if (count == -2)
            throw new NativeAccessViolationException();

        if (count < 0)
            throw new InvalidOperationException(
                $"ft8_decode_all returned {count} — unexpected error from native shim.");

        if (count == 0) return [];

        // Return only the populated slice.
        return results[..count];
    }

    /// <summary>
    /// Return per-pass new-decode counts from the most recent
    /// <see cref="DecodeAll"/> call on this thread.
    /// Must be called on the same thread that called <see cref="DecodeAll"/>.
    /// </summary>
    /// <param name="maxPasses">Maximum number of passes to query (array capacity).</param>
    /// <returns>
    /// Array of length equal to the number of passes actually executed,
    /// where <c>result[i]</c> is the number of new (non-duplicate) messages
    /// decoded in pass <c>i</c> (0-indexed). Sum equals the total returned
    /// by <see cref="DecodeAll"/>.
    /// </returns>
    public static int[] GetLastPassCounts(int maxPasses)
    {
        EnsureInitialized();

        var counts = new int[maxPasses];
        int numPasses = NativeGetLastPassCounts(counts, maxPasses);
        if (numPasses <= 0) return [];
        return counts[..numPasses];
    }

    /// <summary>
    /// Return per-pass candidate counts from the most recent
    /// <see cref="DecodeAll"/> call on this thread.
    /// <para>
    /// <c>result[i]</c> is the number of candidates returned by
    /// <c>ftx_find_candidates</c> in pass <c>i</c>, before any LDPC decode
    /// attempt.  Compare with <see cref="GetLastPassCounts"/> to distinguish
    /// candidate-generation failure (result[i] is low) from LDPC convergence
    /// failure (result[i] is high but GetLastPassCounts[i] is zero).
    /// </para>
    /// Must be called on the same thread that called <see cref="DecodeAll"/>.
    /// </summary>
    public static int[] GetLastCandidateCounts(int maxPasses)
    {
        EnsureInitialized();

        var counts = new int[maxPasses];
        int numPasses = NativeGetLastCandidateCounts(counts, maxPasses);
        if (numPasses <= 0) return [];
        return counts[..numPasses];
    }

    /// <summary>
    /// Return per-pass LLR statistics from the most recent <see cref="DecodeAll"/>
    /// call on this thread (redesigned at shim 20260020).
    /// <para>
    /// <c>MeanAbs[i]</c> — post-normalisation mean absolute LLR across LDPC-failing
    /// candidates in pass <c>i</c>.  Returns 0.0f for passes with no failing candidates.
    /// </para>
    /// <para>
    /// <c>PrenormVariance[i]</c> — pre-normalisation variance of the raw log174 array,
    /// averaged across failing candidates in pass <c>i</c>.  A small value (≪1) confirms
    /// the D-001 root cause: near-zero LLRs due to equal-SNR mutual interference that
    /// cannot be rescued by normalisation (hypothesis H_LLR, inconclusive at post-norm
    /// mean; pre-norm variance is the correct discriminant).
    /// </para>
    /// <para>
    /// <c>FailCount[i]</c> — number of LDPC-failing candidates in pass <c>i</c>.
    /// </para>
    /// Must be called on the same thread that called <see cref="DecodeAll"/>.
    /// </summary>
    public static (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses)
    {
        EnsureInitialized();

        var meanAbs         = new float[maxPasses];
        var prenormVariance = new float[maxPasses];
        var failCount       = new int[maxPasses];
        int numPasses       = NativeGetLastLlrStats(meanAbs, prenormVariance, failCount, maxPasses);

        if (numPasses <= 0)
            return ([], [], []);

        return (meanAbs[..numPasses], prenormVariance[..numPasses], failCount[..numPasses]);
    }

    /// <summary>
    /// Supply known AP bit constraints for the next decode cycle (H6 directed AP decode,
    /// shim 20260020).
    /// <para>
    /// Bits are 28-bit packed callsign fields, MSB-first.  Pass an empty array for either
    /// parameter to disable that constraint.  Pass both empty to disable AP entirely
    /// (the default state; behaves identically to shim 20260019).
    /// </para>
    /// <para>
    /// The constraints are applied only during pass 0 (the primary decode pass).
    /// Pass 1 (spectrogram-suppressed) always uses waterfall-derived LLRs unchanged.
    /// </para>
    /// <para>
    /// <b>Note:</b> the <see cref="Ft8Decoder"/> caller integration is deferred to a
    /// follow-on change.  This method exposes the interop seam; calling it with non-empty
    /// arrays enables the native AP path.
    /// </para>
    /// </summary>
    /// <param name="mycallBits">28-bit packed mycall bits, MSB-first (4 bytes); empty to disable.</param>
    /// <param name="hiscallBits">28-bit packed hiscall bits, MSB-first (4 bytes); empty to disable.</param>
    public static void SetApBits(byte[] mycallBits, byte[] hiscallBits)
    {
        EnsureInitialized();

        int numMycall  = Math.Min(mycallBits.Length  * 8, 28);
        int numHiscall = Math.Min(hiscallBits.Length * 8, 28);

        // Ensure the arrays are at least 1 byte so the P/Invoke pointer is non-null.
        // If the caller passes an empty array we pass 0 for the bit count (AP disabled).
        byte[] mc = mycallBits.Length  > 0 ? mycallBits  : [0];
        byte[] hc = hiscallBits.Length > 0 ? hiscallBits : [0];

        NativeSetApBits(mc, numMycall, hc, numHiscall);
    }

    /// <summary>
    /// Return the histogram-median waterfall noise floor (dB) from the most recent
    /// <see cref="DecodeAll"/> call on this thread.
    /// <para>
    /// Value is <c>median_uint8 * 0.5f − 120.0f</c>, matching the <c>noise_floor_db</c>
    /// used in the native SNR formula: <c>SNR = signal_db − noise_floor_db − 26.5</c>.
    /// Logging this value per cycle allows D-003 (intermittent ~15 dB SNR under-report)
    /// to be diagnosed: if D-003 is caused by a noise-floor estimator anomaly, affected
    /// cycles will show this value elevated by ~15 dB relative to neighbouring cycles.
    /// </para>
    /// Must be called on the same thread that called <see cref="DecodeAll"/>.
    /// Returns 0.0f if <see cref="DecodeAll"/> has not yet been called on this thread.
    /// </summary>
    public static float GetLastNoiseFloorDb()
    {
        EnsureInitialized();
        return NativeGetLastNoiseFloorDb();
    }

    /// <summary>
    /// Encodes an FT8 message string to exactly <see cref="EncodedToneCount"/> (79) tone indices.
    /// </summary>
    /// <param name="message">FT8 message text, e.g. <c>"Q1OFZ Q1TST JO33"</c>.</param>
    /// <param name="tonesOut">
    /// Caller-allocated byte array; must have <see cref="Array.Length"/> ≥ 79.
    /// On success the first 79 elements are filled with tone indices in [0, 7].
    /// </param>
    /// <exception cref="ArgumentException">
    /// Thrown when <paramref name="tonesOut"/> has fewer than 79 elements.
    /// </exception>
    /// <exception cref="InvalidOperationException">
    /// Thrown when the native encoder rejects <paramref name="message"/> (invalid format,
    /// too long, unpackable callsign, etc.).
    /// </exception>
    public static void EncodeMessage(string message, byte[] tonesOut)
    {
        if (tonesOut.Length < EncodedToneCount)
            throw new ArgumentException(
                $"tonesOut must have at least {EncodedToneCount} elements; got {tonesOut.Length}.",
                nameof(tonesOut));

        EnsureInitialized();

        int rc = NativeEncodeMessage(message, tonesOut, tonesOut.Length);

        if (rc == -2)
            throw new InvalidOperationException(
                $"ft8_encode_message could not pack message '{message}'. " +
                "Check message format (max 35 chars, valid FT8 syntax).");

        if (rc != EncodedToneCount)
            throw new InvalidOperationException(
                $"ft8_encode_message returned unexpected code {rc} for message '{message}'.");
    }

    // ── Lazy initialisation ──────────────────────────────────────────────

    private static void EnsureInitialized()
    {
        if (_initialized) return;

        lock (_initLock)
        {
            if (_initialized) return;
            LoadAndVerify();
            _initialized = true;
        }
    }

    private static void LoadAndVerify()
    {
        // Step 1: register the DllImportResolver BEFORE any P/Invoke call fires.
        // The resolver intercepts the "libft8.dll" token and redirects it to the
        // platform-appropriate filename loaded from AppContext.BaseDirectory.
        //
        // NativeLibrary.SetDllImportResolver throws InvalidOperationException if
        // called a second time on the same assembly.  We guard with _resolverRegistered
        // (written inside _initLock) so that a failed verification attempt on a first
        // call does not prevent the resolver from remaining active on a retry — the
        // double-checked lock alone is insufficient because it resets when an exception
        // escapes LoadAndVerify() before _initialized is set.
        if (!_resolverRegistered)
        {
            NativeLibrary.SetDllImportResolver(
                typeof(Ft8LibInterop).Assembly,
                static (libraryName, assembly, searchPath) =>
                {
                    if (libraryName != "libft8.dll") return IntPtr.Zero;

                    string fileName = RuntimeInformation.IsOSPlatform(OSPlatform.Windows) ? "libft8.dll"
                                    : RuntimeInformation.IsOSPlatform(OSPlatform.OSX)     ? "libft8.dylib"
                                    : "libft8.so";

                    string fullPath = Path.Combine(AppContext.BaseDirectory, fileName);
                    return NativeLibrary.Load(fullPath);
                });
            _resolverRegistered = true;
        }

        // Step 2: existence check for the platform-appropriate binary.
        string libFileName = RuntimeInformation.IsOSPlatform(OSPlatform.Windows) ? "libft8.dll"
                           : RuntimeInformation.IsOSPlatform(OSPlatform.OSX)     ? "libft8.dylib"
                           : "libft8.so";

        string libPath = Path.Combine(AppContext.BaseDirectory, libFileName);

        if (!File.Exists(libPath))
            throw new DllNotFoundException(
                $"Native library not found at '{libPath}'. " +
                "Ensure the project was built and the native binary for this platform is present.");

        // Step 3: ABI self-test — resolver is now active, DllImport call is safe.
        int actual   = NativeVersionCheck();
        int expected = ExpectedShimVersion;
        if (actual != expected)
            throw new InvalidOperationException(
                $"Native library ABI mismatch at '{libPath}'. " +
                $"Expected FT8_SHIM_VERSION={expected}, got {actual}. " +
                "Rebuild the native library from the committed shim source (see src/OpenWSFZ.Ft8/Native/BUILD.md).");

        // Step 3b: K_MAX_PASSES / MaxDecodePasses drift check.
        // If the native shim is ever rebuilt with a different K_MAX_PASSES while
        // the managed constant stays at its old value, pass-count data would be
        // silently truncated or over-read.  Catch this mismatch immediately.
        int nativeMaxPasses = NativeGetMaxPasses();
        if (nativeMaxPasses != MaxDecodePasses)
            throw new InvalidOperationException(
                $"Native K_MAX_PASSES ({nativeMaxPasses}) does not match managed " +
                $"MaxDecodePasses ({MaxDecodePasses}). " +
                "Rebuild the native library or update the managed constant.");

        // Step 4: verify managed struct size matches native. Runs exactly once during lazy init
        // so the reflection cost (Marshal.SizeOf uses internal caching, not a compile-time
        // constant) is paid only at first load, not on every decode call.
        int managedSize = Marshal.SizeOf<Ft8NativeResult>();
        if (managedSize != Ft8NativeResult.ExpectedNativeSizeBytes)
            throw new InvalidOperationException(
                $"Ft8NativeResult managed struct size ({managedSize}) does not match " +
                $"native FT8Result size ({Ft8NativeResult.ExpectedNativeSizeBytes}). " +
                "This is a build configuration error — recheck [StructLayout].");
    }
}
