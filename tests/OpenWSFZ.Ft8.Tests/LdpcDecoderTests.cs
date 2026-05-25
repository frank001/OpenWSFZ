using FluentAssertions;
using OpenWSFZ.Ft8.Dsp;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Ft8Decoder: LdpcDecoderTests
/// </summary>
public sealed class LdpcDecoderTests
{
    // ── CRC-14 tests ─────────────────────────────────────────────────────────

    [Fact]
    public void Crc14_KnownVector_AllZeroMessage_ProducesZeroCrc()
    {
        // Standard CRC-14 of an all-zero 77-bit message is 0:
        // feedback is always (0 >> 13) ^ 0 = 0, so the polynomial is never applied
        // and the register remains 0 throughout. This is the canonical reference
        // vector that distinguishes the correct WSJT-X algorithm from incorrect ones.
        var bits = new byte[77]; // all zero
        uint crc = Crc14.Compute(bits, 77);
        crc.Should().Be(0u,
            "standard CRC-14 of an all-zero message must be 0 per the FT8 specification");
    }

    [Fact]
    public void Crc14_RoundTrip_Verifies()
    {
        // Build a random 77-bit message, compute CRC, append it, verify.
        var rng  = new Random(123);
        var msg  = new byte[91];
        for (int i = 0; i < 77; i++) msg[i] = (byte)(rng.Next(2));

        uint crc = Crc14.Compute(msg, 77);
        // Append 14 CRC bits MSB-first.
        for (int i = 0; i < 14; i++)
            msg[77 + i] = (byte)((crc >> (13 - i)) & 1);

        bool ok = Crc14.Verify(msg, 91);
        ok.Should().BeTrue("appended CRC should verify against its own message");
    }

    [Fact]
    public void Crc14_FlippedBit_Fails()
    {
        var rng = new Random(456);
        var msg = new byte[91];
        for (int i = 0; i < 77; i++) msg[i] = (byte)(rng.Next(2));

        uint crc = Crc14.Compute(msg, 77);
        for (int i = 0; i < 14; i++)
            msg[77 + i] = (byte)((crc >> (13 - i)) & 1);

        // Flip one message bit.
        msg[10] ^= 1;

        bool ok = Crc14.Verify(msg, 91);
        ok.Should().BeFalse("flipping a message bit should invalidate the CRC");
    }

    // ── LDPC decoder tests ───────────────────────────────────────────────────

    [Fact]
    public void LdpcDecoder_StrongLlrs_ConvergesAndPassesParity()
    {
        // Build strong LLRs (large magnitude → confident bits) for a zero codeword.
        // A zero codeword (all bits = 0) always satisfies any linear parity-check code.
        var llr = new float[LdpcDecoder.CodeLength];
        for (int i = 0; i < llr.Length; i++)
            llr[i] = 10f; // strong positive → bit 0

        var result = LdpcDecoder.Decode(llr);

        result.Should().NotBeNull("strong LLRs for an all-zero codeword should converge");
        result!.Length.Should().Be(LdpcDecoder.InfoBits);
        result.Should().AllSatisfy(b => b.Should().Be(0));
    }

    [Fact]
    public void LdpcDecoder_RandomNoiseLlrs_FalsePositiveRateBelow1In1000()
    {
        // Generate 1 000 random LLR vectors; check how many pass parity + CRC.
        var rng         = new Random(789);
        int falsePasses = 0;

        for (int trial = 0; trial < 1000; trial++)
        {
            var llr = new float[LdpcDecoder.CodeLength];
            for (int i = 0; i < llr.Length; i++)
                llr[i] = (float)(rng.NextDouble() * 4.0 - 2.0); // ±2 — weak/noisy

            var result = LdpcDecoder.Decode(llr);
            if (result is not null)
            {
                // Count only those that also pass CRC-14 (91-bit block).
                // For a random 87-bit decode, build the 91-bit block and check CRC.
                // (A result that passes parity but fails CRC is the realistic false-positive.)
                var block = new byte[91];
                Array.Copy(result, block, Math.Min(result.Length, 91));
                if (Crc14.Verify(block, 91)) falsePasses++;
            }
        }

        falsePasses.Should().BeLessThan(1,
            "random noise should almost never produce a valid LDPC+CRC decode");
    }
}
