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
    /// </summary>
    private const int ExpectedShimVersion = 20260009;

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
    /// Pass 1: PCM-residual waterfall — each pass-0 decoded signal is synthesised
    ///   using the GFSK quadrature synthesiser (BT=2.0, 3-symbol Gaussian; H3b) and
    ///   subtracted from a heap-allocated PCM copy using the analytic quadrature
    ///   amplitude estimator; the waterfall is rebuilt from the residual before pass 1.
    ///   If any heap allocation fails, pass 1 falls back to the original waterfall.
    /// </summary>
    internal const int MaxDecodePasses = 2;

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
    /// <paramref name="pcmLen"/> ≠ 180 000.
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

    // ── Public API ───────────────────────────────────────────────────────

    /// <summary>
    /// Decode all FT8 signals from a 180 000-sample PCM buffer.
    /// Performs <c>K_MAX_PASSES</c> (currently 2) decode passes internally:
    /// pass 0 on the full waterfall; pass 1 on a waterfall rebuilt from the
    /// PCM residual after GFSK quadrature PCM-domain SIC — each pass-0 signal
    /// is synthesised via <c>synth_ft8_gfsk_quad</c> (BT=2.0, 3-symbol Gaussian
    /// pulse, I/Q quadrature components) and subtracted from a heap-allocated
    /// PCM copy using the analytic quadrature amplitude estimator
    /// (<c>compute_quadrature_amplitude</c>, O(N), phase-agnostic); the waterfall
    /// is rebuilt from the residual before pass 1 runs
    /// (shim version 20260009, H3b diagnostic).
    /// </summary>
    /// <param name="pcm">12 kHz mono float32 PCM, normalised to [-1, 1].</param>
    /// <returns>Array of decoded results (may be empty; never null).</returns>
    /// <exception cref="ArgumentException">
    /// Thrown when <paramref name="pcm"/> does not contain exactly 180 000 samples.
    /// </exception>
    /// <exception cref="InvalidOperationException">
    /// Thrown if the native DLL cannot be loaded or the ABI version check fails.
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
