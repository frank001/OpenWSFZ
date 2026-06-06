using System.Runtime.InteropServices;

namespace OpenWSFZ.Ft8.Interop;

/// <summary>
/// Blittable struct mirroring the C <c>FT8Result</c> struct from <c>ft8_shim.h</c>.
///
/// Layout (must match sizeof(FT8Result) = 48 bytes in the native shim):
/// <code>
///   offset  0 : int   FreqHz   (4 bytes)
///   offset  4 : float Dt       (4 bytes)
///   offset  8 : int   Snr      (4 bytes)
///   offset 12 : char  Message  (36 bytes, null-terminated, max 35 chars)
///   total     : 48 bytes — no padding
/// </code>
/// </summary>
[StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
internal struct Ft8NativeResult
{
    /// <summary>Centre frequency of the decoded signal, in Hz.</summary>
    public int FreqHz;

    /// <summary>Time offset from cycle start, in seconds.</summary>
    public float Dt;

    /// <summary>
    /// SNR estimate in dB, referenced to a 2500 Hz noise bandwidth (WSJT-X convention).
    /// Computed as: average of per-symbol max-over-8-tones waterfall magnitude minus the
    /// global noise-floor median, minus 26 dB (= 10·log₁₀(2500/6.25)).
    /// No post-correction is applied (R6 weak-signal correction removed; see R&amp;R-001).
    /// </summary>
    public int Snr;

    /// <summary>
    /// Decoded message text, null-terminated, max 35 chars (FTX_MAX_MESSAGE_LENGTH).
    /// Fixed-length 36-byte ANSI buffer matches the C struct's <c>char message[36]</c>.
    /// </summary>
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 36)]
    public string Message;

    /// <summary>
    /// The C struct <c>sizeof(FT8Result)</c> = 48.
    /// This constant is verified at startup by <see cref="Ft8LibInterop"/>.
    /// </summary>
    public const int ExpectedNativeSizeBytes = 48;
}
