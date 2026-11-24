using System.Runtime.InteropServices;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Ft8.Interop;

/// <summary>
/// Blittable struct mirroring the C <c>FT8Result</c> struct from <c>ft8_shim.h</c>: the WIRE layout the
/// <c>ft8_decode_all</c> P/Invoke fills. It is exactly 48 bytes and has not changed since the shim's first release
/// (Python ctypes harnesses allocate arrays of it), so cq-ap does NOT widen it: the per-decode <c>apKind</c> comes from
/// the index-aligned getter <c>ft8_get_last_ap_kinds</c> and is joined onto <see cref="Ft8NativeResult"/> in
/// <see cref="Ft8LibInterop.DecodeAll"/>.
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
internal struct Ft8NativeResultWire
{
    /// <summary>Centre frequency of the decoded signal, in Hz.</summary>
    public int FreqHz;

    /// <summary>Time offset from cycle start, in seconds.</summary>
    public float Dt;

    /// <summary>SNR estimate in dB (see <see cref="Ft8NativeResult.Snr"/>).</summary>
    public int Snr;

    /// <summary>Decoded message text, null-terminated, max 35 chars (FTX_MAX_MESSAGE_LENGTH); fixed 36-byte ANSI buffer.</summary>
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 36)]
    public string Message;

    /// <summary>
    /// The C struct <c>sizeof(FT8Result)</c> = 48.
    /// This constant is verified at startup by <see cref="Ft8LibInterop"/>.
    /// </summary>
    public const int ExpectedNativeSizeBytes = 48;
}

/// <summary>
/// One decode as the managed layer carries it: the fields of the native <c>FT8Result</c> (see
/// <see cref="Ft8NativeResultWire"/>) plus the cq-ap provenance tag. This struct is NOT marshalled; the P/Invoke fills
/// <see cref="Ft8NativeResultWire"/> and <see cref="Ft8LibInterop.DecodeAll"/> copies it here.
/// </summary>
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

    /// <summary>Decoded message text (the native buffer, null terminator dropped; may carry trailing padding spaces).</summary>
    public string Message;

    /// <summary>
    /// cq-ap (shim 20260072): <see cref="Abstractions.ApKind.Cq"/> if this decode came from the CQ a-priori attempt,
    /// otherwise <see cref="Abstractions.ApKind.None"/> (the default, and always the value with <c>cqApEnabled</c> off).
    /// </summary>
    public ApKind ApKind;
}
