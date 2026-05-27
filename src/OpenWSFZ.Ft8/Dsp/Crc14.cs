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

    /// <summary>
    /// Verifies the CRC-14 of an FT8 91-bit information block
    /// (77 message bits followed by 14 CRC bits).
    ///
    /// <para>
    /// The FT8 standard (Franke &amp; Taylor 2019 / kgoba ft8_lib) computes the CRC over
    /// <b>82 bits</b>: the 77 message bits followed by 5 implicit zero-padding bits.
    /// The resulting 14-bit CRC is stored at bit positions [77..90] of the 91-bit block.
    /// </para>
    ///
    /// <para>
    /// Reference: kgoba/ft8_lib <c>crc.c</c> — <c>ftx_compute_crc(a91, 96 − 14)</c>
    /// (96 − 14 = 82 bits).  Using <see cref="Verify"/> with <c>totalBits=91</c>
    /// computes the CRC over only 77 bits and will always fail for live on-air signals
    /// because the stored CRC covers the additional 5 zero-padding bits.
    /// </para>
    /// </summary>
    /// <param name="bits91">
    /// Exactly 91 bits in flat (one byte per bit) format:
    /// bits[0..76] = 77 message bits, bits[77..90] = 14 stored CRC bits.
    /// </param>
    /// <returns>
    /// <c>true</c> if the stored 14-bit CRC matches the CRC computed over
    /// the 77 message bits with 5 zero-padding bits appended (82 bits total).
    /// </returns>
    public static bool VerifyFt8(ReadOnlySpan<byte> bits91)
    {
        if (bits91.Length < 91) return false;

        // Build 82-bit input: 77 message bits + 5 zero-padding bits.
        // stackalloc is safe here — 82 bytes is well within stack limits.
        Span<byte> buf = stackalloc byte[82]; // zero-initialised by stackalloc
        bits91[..77].CopyTo(buf);
        // buf[77..81] remain 0 — the 5 implicit zero-padding bits.

        uint expected = Compute(buf, 82);

        // Extract the 14-bit CRC stored MSB-first at bits[77..90].
        uint stored = 0u;
        for (int i = 0; i < Bits; i++)
            stored = (stored << 1) | (bits91[77 + i] & 1u);

        return expected == stored;
    }
}
