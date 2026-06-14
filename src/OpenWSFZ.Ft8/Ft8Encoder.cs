using OpenWSFZ.Ft8.Interop;

namespace OpenWSFZ.Ft8;

/// <summary>
/// Public façade for FT8 message encoding.
///
/// <para>
/// Delegates to <see cref="Ft8LibInterop.EncodeMessage"/> (internal P/Invoke binding)
/// so that callers in other assemblies (e.g. <c>OpenWSFZ.Daemon</c>) can encode FT8
/// messages without requiring access to the internal interop layer.
/// </para>
/// </summary>
public static class Ft8Encoder
{
    /// <summary>
    /// Number of tone symbols produced by one FT8 encode (79 symbols × 7680 samples each
    /// at 48 kHz = 606 720 output samples from <see cref="Ft8AudioSynthesiser"/>).
    /// </summary>
    public const int ToneCount = Ft8LibInterop.EncodedToneCount;

    /// <summary>
    /// Encodes an FT8 text message into 79 tone indices in [0, 7].
    /// </summary>
    /// <param name="message">
    /// FT8 message text (up to 35 characters, standard FT8 syntax — e.g.
    /// <c>"Q1TST Q1OFZ JO33"</c> or <c>"Q1TST Q1OFZ RR73"</c>).
    /// </param>
    /// <param name="tonesOut">
    /// Output buffer.  Must have at least <see cref="ToneCount"/> (79) elements.
    /// </param>
    /// <exception cref="ArgumentException">
    /// Thrown when <paramref name="tonesOut"/> is too short.
    /// </exception>
    /// <exception cref="InvalidOperationException">
    /// Thrown when <paramref name="message"/> cannot be packed into FT8 bit fields
    /// (e.g. too long or uses unsupported syntax).
    /// </exception>
    public static void EncodeMessage(string message, byte[] tonesOut)
        => Ft8LibInterop.EncodeMessage(message, tonesOut);
}
