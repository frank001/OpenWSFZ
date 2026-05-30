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
    private const int ExpectedShimVersion = 20240001;

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
        [In] float[]        pcm,
        int                 pcmLen,
        [Out] Ft8NativeResult[] results,
        int                 maxResults);

    // ── Public API ───────────────────────────────────────────────────────

    /// <summary>
    /// Decode all FT8 signals from a 180 000-sample PCM buffer.
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

        // libft8.dll is Windows x64 only in p12. On other platforms return empty rather than
        // crashing — the decoder reports "no decodes" which is correct: the native backend is
        // not available. Cross-platform support is deferred to a future change.
        if (!RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
            return [];

        EnsureInitialized();

        // Verify managed struct size matches native at runtime (catches accidental layout drift).
        // This is a quick constant comparison — only the first call evaluates it.
        int managedSize = Marshal.SizeOf<Ft8NativeResult>();
        if (managedSize != Ft8NativeResult.ExpectedNativeSizeBytes)
            throw new InvalidOperationException(
                $"Ft8NativeResult managed struct size ({managedSize}) does not match " +
                $"native FT8Result size ({Ft8NativeResult.ExpectedNativeSizeBytes}). " +
                "This is a build configuration error — recheck [StructLayout].");

        var results = new Ft8NativeResult[MaxResults];
        int count = NativeDecodeAll(pcm, pcm.Length, results, MaxResults);

        if (count < 0)
            throw new InvalidOperationException(
                $"ft8_decode_all returned {count} — unexpected error from native shim.");

        if (count == 0) return [];

        // Return only the populated slice.
        return results[..count];
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
        // NativeLibrary.Load resolves libft8.dll from AppContext.BaseDirectory first,
        // matching the CopyToOutputDirectory="Always" MSBuild directive.
        string dllPath = Path.Combine(AppContext.BaseDirectory, "libft8.dll");

        if (!File.Exists(dllPath))
            throw new InvalidOperationException(
                $"libft8.dll not found at '{dllPath}'. " +
                "Ensure the project is built (dotnet build) so the DLL is copied to the output directory.");

        // NativeLibrary.Load verifies the DLL can be loaded and resolves imports.
        // If it fails (wrong architecture, missing CRT, etc.) it throws DllNotFoundException.
        NativeLibrary.Load(dllPath);

        // ABI self-test: call the sentinel function and compare the embedded constant.
        int actual = NativeVersionCheck();
        if (actual != ExpectedShimVersion)
            throw new InvalidOperationException(
                $"libft8.dll ABI mismatch at '{dllPath}'. " +
                $"Expected FT8_SHIM_VERSION={ExpectedShimVersion}, got {actual}. " +
                "Rebuild libft8.dll from the committed shim source (see src/OpenWSFZ.Ft8/Native/BUILD.md).");
    }
}
