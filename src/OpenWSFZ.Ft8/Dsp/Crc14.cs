namespace OpenWSFZ.Ft8.Dsp;

/// <summary>
/// CRC-14 computation and verification for FT8 messages.
///
/// Polynomial: 0x2757 (x¹⁴ + x¹³ + x¹⁰ + x⁹ + x⁸ + x⁶ + x⁴ + x² + x + 1)
/// Source: Franke &amp; Taylor 2019.
/// The CRC covers the 77-bit message; the 14 check bits are appended to form the
/// 91-bit protected block that enters the LDPC encoder.
/// </summary>
internal static class Crc14
{
    private const uint Poly = 0x2757u;
    private const int  Bits = 14;
    private const uint Mask = (1u << Bits) - 1u; // 0x3FFF

    /// <summary>
    /// Computes the CRC-14 of the supplied bits.
    /// </summary>
    /// <param name="bits">
    /// The message bits, MSB-first. Bits beyond <paramref name="bitCount"/> are ignored.
    /// </param>
    /// <param name="bitCount">Number of bits to process (77 for a standard FT8 message).</param>
    /// <returns>14-bit CRC value.</returns>
    public static uint Compute(ReadOnlySpan<byte> bits, int bitCount)
    {
        uint crc = 0u;

        for (int i = 0; i < bitCount; i++)
        {
            uint bit = bits[i] & 1u;
            // Standard FT8 CRC-14 (Franke & Taylor 2019 / WSJT-X):
            // feedback = old MSB XOR incoming bit; then shift left discarding old MSB.
            uint feedback = ((crc >> (Bits - 1)) ^ bit) & 1u;
            crc           = (crc << 1) & Mask;
            if (feedback != 0)
                crc ^= Poly;
        }

        // No flush — the register state after bitCount iterations is the CRC.
        return crc;
    }

    /// <summary>
    /// Verifies that the last 14 bits of <paramref name="bits"/> are the correct CRC
    /// of the preceding <c><paramref name="totalBits"/> - 14</c> message bits.
    /// </summary>
    public static bool Verify(ReadOnlySpan<byte> bits, int totalBits)
    {
        int messageBits = totalBits - Bits;
        if (messageBits < 0) return false;

        uint expected = Compute(bits, messageBits);

        // Extract the appended CRC bits.
        uint appended = 0u;
        for (int i = messageBits; i < totalBits; i++)
        {
            appended = (appended << 1) | (bits[i] & 1u);
        }

        return expected == appended;
    }
}
