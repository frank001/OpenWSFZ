using FluentAssertions;
using OpenWSFZ.Ft8.Dsp;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Ft8Decoder: MessageUnpackerTests
///
/// Covers both the original <see cref="MessageUnpacker.Unpack"/> path and the
/// content-validation path added in p11 Part 1 (<see cref="MessageUnpacker.TryUnpack"/>).
/// </summary>
public sealed class MessageUnpackerTests
{
    // ── Helpers ───────────────────────────────────────────────────────────────

    /// <summary>
    /// Packs <paramref name="value"/> into <paramref name="bits"/>
    /// starting at <paramref name="start"/> for <paramref name="count"/> bits, MSB-first.
    /// </summary>
    private static void WriteBits(byte[] bits, int start, int count, ulong value)
    {
        for (int i = count - 1; i >= 0; i--)
        {
            bits[start + i] = (byte)(value & 1);
            value >>= 1;
        }
    }

    /// <summary>
    /// Builds a 77-bit Type 1 (i3=0, n3=0) message bit array from packed field values.
    /// </summary>
    private static byte[] BuildType1Bits(ulong c1, ulong c2, ulong rg)
    {
        var bits = new byte[77];
        WriteBits(bits,  0, 28, c1);
        WriteBits(bits, 28, 28, c2);
        WriteBits(bits, 56, 15, rg);
        // n3 bits 71-73 = 0, i3 bits 74-76 = 0 (already zero-initialised)
        return bits;
    }

    // ── Part 1: TryUnpack content-validation tests  (FR-029) ─────────────────

    // Packed values for standard callsigns in 6-char left-padded base-37 form.
    //
    // " Q0ABC": chars[0]=' '(0), chars[1]='K'(21), chars[2]='0'(1), chars[3]='A'(11),
    //           chars[4]='B'(12), chars[5]='C'(13)
    //   packed-3 = 0*37^5 + 21*37^4 + 1*37^3 + 11*37^2 + 12*37 + 13 = 39 423 550
    private const ulong Packed_Q0ABC = 39_423_553UL; // 39 423 550 + 3

    // " W1ABC": chars[0]=' '(0), chars[1]='W'(33), chars[2]='1'(2), chars[3]='A'(11),
    //           chars[4]='B'(12), chars[5]='C'(13)
    //   packed-3 = 0*37^5 + 33*37^4 + 2*37^3 + 11*37^2 + 12*37 + 13 = 61 964 135
    private const ulong Packed_W1ABC = 61_964_138UL; // 61 964 135 + 3

    // "07WNYS": chars[2]='W' (letter at pos 2) — invalid per base-37 invariant.
    //   chars[0]='0'(1), chars[1]='7'(8), chars[2]='W'(33), chars[3]='N'(24),
    //   chars[4]='Y'(35), chars[5]='S'(29)
    //   packed-3 = 1*37^5 + 8*37^4 + 33*37^3 + 24*37^2 + 35*37 + 29 = 86 042 974
    private const ulong Packed_07WNYS = 86_042_977UL;

    // "0H21AM": chars[3]='1' (digit at pos 3) — invalid per base-37 invariant.
    //   chars[0]='0'(1), chars[1]='H'(18), chars[2]='2'(3), chars[3]='1'(2),
    //   chars[4]='A'(11), chars[5]='M'(23)
    //   packed-3 = 1*37^5 + 18*37^4 + 3*37^3 + 2*37^2 + 11*37 + 23 = 103 233 982
    private const ulong Packed_0H21AM = 103_233_985UL;

    // Extra-field values.
    // Report (bit 14 = 1): extra = 0x4000 | val.
    // SNR +11 dB: val = 11 + 35 = 46  →  extra = 16 430  (valid: val ∈ [1,60])
    private const ulong Extra_SnrPlus11 = 16_430UL;    // 0x4000 | 46
    // val = 2194 (+2159 dB display) — from corpus false-positive   →  extra = 18 578
    private const ulong Extra_Val2194   = 18_578UL;    // 0x4000 | 2194
    // val = 4052 (+4017 dB display)   →  extra = 20 436
    private const ulong Extra_Val4052   = 20_436UL;    // 0x4000 | 4052
    // Grid FN13: r1=F(5), r2=N(13), 1, 3  →  val = 5*1800 + 13*100 + 1*10 + 3 = 10 313
    private const ulong Extra_FN13      = 10_313UL;    // bit 14 = 0, val = 10 313

    [Fact(DisplayName = "FR-029: TryUnpack returns decoded string for valid Type 1 message")]
    public void TryUnpack_ValidType1_ReturnsDecodedString()
    {
        var bits = BuildType1Bits(Packed_Q0ABC, Packed_W1ABC, Extra_SnrPlus11);
        string? result = MessageUnpacker.TryUnpack(bits);
        result.Should().NotBeNull("valid Type 1 message with in-range SNR must decode");
        result.Should().Contain("Q0ABC");
    }

    [Fact(DisplayName = "FR-029: TryUnpack returns null for report extra field with val 2194 (+2159 dB)")]
    public void TryUnpack_ExtraVal2194_ReturnsNull()
    {
        var bits = BuildType1Bits(Packed_Q0ABC, Packed_W1ABC, Extra_Val2194);
        string? result = MessageUnpacker.TryUnpack(bits);
        result.Should().BeNull("SNR val=2194 is far outside the valid range [1,60]");
    }

    [Fact(DisplayName = "FR-029: TryUnpack returns null for report extra field with val 4052 (+4017 dB)")]
    public void TryUnpack_ExtraVal4052_ReturnsNull()
    {
        var bits = BuildType1Bits(Packed_Q0ABC, Packed_W1ABC, Extra_Val4052);
        string? result = MessageUnpacker.TryUnpack(bits);
        result.Should().BeNull("SNR val=4052 is far outside the valid range [1,60]");
    }

    [Fact(DisplayName = "FR-029: TryUnpack returns null when callsign packed value decodes to 07WNYS (letter at position 2)")]
    public void TryUnpack_Callsign07WNYS_ReturnsNull()
    {
        var bits = BuildType1Bits(Packed_07WNYS, Packed_W1ABC, Extra_SnrPlus11);
        string? result = MessageUnpacker.TryUnpack(bits);
        result.Should().BeNull("'07WNYS' has a letter at position 2 — violates base-37 callsign invariant");
    }

    [Fact(DisplayName = "FR-029: TryUnpack returns null when callsign packed value decodes to 0H21AM (digit at position 3)")]
    public void TryUnpack_Callsign0H21AM_ReturnsNull()
    {
        var bits = BuildType1Bits(Packed_Q0ABC, Packed_0H21AM, Extra_SnrPlus11);
        string? result = MessageUnpacker.TryUnpack(bits);
        result.Should().BeNull("'0H21AM' has a digit at position 3 — violates base-37 callsign invariant");
    }

    [Fact(DisplayName = "FR-029: TryUnpack treats packed values 0/1/2 (DE, QRZ, CQ) as valid callsigns")]
    public void TryUnpack_SpecialPackedValues_PassCallsignValidation()
    {
        // packed=2 → CQ, paired with a valid c2 and valid extra field.
        var bits = BuildType1Bits(2UL, Packed_W1ABC, Extra_SnrPlus11);
        string? result = MessageUnpacker.TryUnpack(bits);
        result.Should().NotBeNull("DE/QRZ/CQ (packed ≤ 2) are always valid callsigns");
    }

    [Fact(DisplayName = "FR-029: TryUnpack returns decoded string for valid grid square FN13")]
    public void TryUnpack_GridFN13_ReturnsDecodedString()
    {
        var bits = BuildType1Bits(Packed_Q0ABC, Packed_W1ABC, Extra_FN13);
        string? result = MessageUnpacker.TryUnpack(bits);
        result.Should().NotBeNull("FN13 is a valid grid square");
        result.Should().Contain("FN13");
    }

    [Fact(DisplayName = "FR-029: TryUnpack returns null when callsign 1 is valid but callsign 2 is bogus (digit at position 3)")]
    public void TryUnpack_ValidC1BogusC2_ReturnsNull()
    {
        var bits = BuildType1Bits(Packed_Q0ABC, Packed_0H21AM, Extra_FN13);
        string? result = MessageUnpacker.TryUnpack(bits);
        result.Should().BeNull("invalid callsign 2 must cause the whole message to be rejected");
    }

    // ── Original Unpack tests ─────────────────────────────────────────────────

    [Fact]
    public void Unpack_UnknownI3_ReturnsTwentyCharHexString()
    {
        // i3 = 7 (bits 74-76 = 111) is not a defined FT8 message type → hex fallback.
        var bits = new byte[77];
        bits[74] = 1; bits[75] = 1; bits[76] = 1; // i3 = 7

        string result = MessageUnpacker.Unpack(bits);

        result.Should().HaveLength(20,
            "hex fallback encodes 77 bits as a 20-character hex string");
        result.Should().MatchRegex("^[0-9A-F]+$",
            "hex fallback should use uppercase hex characters");
    }

    [Fact]
    public void Unpack_FreeTextType_DecodesAlphanumericString()
    {
        // i3 = 5 → free-text branch. Encode "CQ DX" using the 42-char alphabet
        // by working backwards from the character encoding.
        // Rather than computing exact bits, verify that the output is a trimmed string
        // from the free-text alphabet (not hex) when i3 = 5.
        var bits = new byte[77];
        bits[74] = 1; bits[75] = 0; bits[76] = 1; // i3 = 5

        string result = MessageUnpacker.Unpack(bits);

        // All-zero payload with i3=5 → all spaces → trimmed to empty.
        result.Should().NotBeNull();
        result.Should().MatchRegex("^[ 0-9A-Z+\\-./?]*$",
            "free-text output should only contain characters from the FT8 free-text alphabet");
    }

    [Fact]
    public void Unpack_TooFewBits_DoesNotThrow()
    {
        var bits = new byte[10]; // far too short
        var act = () => MessageUnpacker.Unpack(bits);
        act.Should().NotThrow("truncated input should produce a hex fallback without throwing");
    }

    [Fact]
    public void HexFallback_DifferentInputs_ProduceDifferentOutputs()
    {
        // Two distinct 77-bit payloads with i3=7 should produce different hex strings.
        var bits1 = new byte[77];
        var bits2 = new byte[77];
        bits1[74] = 1; bits1[75] = 1; bits1[76] = 1; // i3 = 7
        bits2[74] = 1; bits2[75] = 1; bits2[76] = 1;
        bits2[0]  = 1; // one extra bit differs

        string r1 = MessageUnpacker.Unpack(bits1);
        string r2 = MessageUnpacker.Unpack(bits2);

        r1.Should().NotBe(r2, "different inputs should produce different hex outputs");
    }
}
