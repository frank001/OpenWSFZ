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
    /// </summary>
    private const int ExpectedShimVersion = 20260001;

    /// <summary>Maximum number of decoded messages per cycle.</summary>
    private const int MaxResults = 140;

    private static readonly object _initLock = new();
    private static volatile bool _initialized;

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

    // ── Public API ───────────────────────────────────────────────────────

    /// <summary>
    /// Decode all FT8 signals from a 180 000-sample PCM buffer.
    /// Performs <c>K_MAX_PASSES</c> (currently 2) decode passes internally:
    /// a first pass on the original waterfall and a second pass on the
    /// residual after suppressing decoded signal tiles.
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
        // NativeLibrary.SetDllImportResolver throws InvalidOperationException if called
        // more than once per assembly; the double-checked lock in EnsureInitialized()
        // guarantees this runs exactly once.
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
