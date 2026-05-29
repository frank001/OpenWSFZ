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

    // Packed values for standard callsigns using FT8 mixed-radix encoding.
    //
    // " Q0ABC": pos0=' '(0), pos1='K'(21), pos2='0'(0), pos3='A'(1), pos4='B'(2), pos5='C'(3)
    //   n = (0*37+21)*10*27^3 + 0*27^3 + 1*27^2 + 2*27 + 3 = 4 134 216
    private const ulong Packed_Q0ABC = 4_134_219UL;  // 4 134 216 + 3

    // " W1ABC": pos0=' '(0), pos1='W'(33), pos2='1'(1), pos3='A'(1), pos4='B'(2), pos5='C'(3)
    //   n = (0*37+33)*10*27^3 + 1*27^3 + 1*27^2 + 2*27 + 3 = 6 515 859
    private const ulong Packed_W1ABC = 6_515_862UL;  // 6 515 859 + 3

    // Extra-field values.
    // Report (bit 14 = 1): extra = 0x4000 | val.
    // SNR +11 dB (plain): val = 11 + 35 = 46  →  extra = 16 430  (valid: val ∈ [4,63])
    private const ulong Extra_SnrPlus11 = 16_430UL;    // 0x4000 | 46
    // R-prefix report "R-11": val = 64 + (-11 + 35) = 88  →  extra = 16 472
    private const ulong Extra_RMinus11  = 16_472UL;    // 0x4000 | 88  (R-prefix, valid: val ∈ [64,127])
    // R-prefix report "R+08" (near-ceiling): val = 64 + (8 + 35) = 107  →  extra = 16 491
    private const ulong Extra_RPlus08   = 16_491UL;    // 0x4000 | 107  (R-prefix, valid)
    // val = 128: first value ABOVE the valid R-prefix range  →  extra = 16 512
    private const ulong Extra_Val128    = 16_512UL;    // 0x4000 | 128  (val > 127, rejected)
    // val = 2194 (+2159 dB display) — from corpus false-positive   →  extra = 18 578
    private const ulong Extra_Val2194   = 18_578UL;    // 0x4000 | 2194  (val > 127, rejected)
    // val = 4052 (+4017 dB display)   →  extra = 20 436
    private const ulong Extra_Val4052   = 20_436UL;    // 0x4000 | 4052  (val > 127, rejected)
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

    [Fact(DisplayName = "FR-029: TryUnpack returns decoded string containing 'R-11' for R-prefix report val 88")]
    public void TryUnpack_RPrefix_Minus11_ReturnsDecodedString()
    {
        var bits = BuildType1Bits(Packed_Q0ABC, Packed_W1ABC, Extra_RMinus11);
        string? result = MessageUnpacker.TryUnpack(bits);
        result.Should().NotBeNull("val=88 is a valid R-prefix SNR report (val 64–127)");
        result.Should().Contain("R-11", "val=88 should decode as R-prefix SNR −11 dB");
    }

    [Fact(DisplayName = "FR-029: TryUnpack returns decoded string containing 'R+08' for R-prefix report val 107")]
    public void TryUnpack_RPrefix_Plus08_ReturnsDecodedString()
    {
        var bits = BuildType1Bits(Packed_Q0ABC, Packed_W1ABC, Extra_RPlus08);
        string? result = MessageUnpacker.TryUnpack(bits);
        result.Should().NotBeNull("val=107 is a valid R-prefix SNR report (val 64–127)");
        result.Should().Contain("R+08", "val=107 should decode as R-prefix SNR +8 dB");
    }

    [Fact(DisplayName = "FR-029: TryUnpack returns null for report extra field with val 128 (above valid R-prefix ceiling)")]
    public void TryUnpack_ExtraVal128_ReturnsNull()
    {
        var bits = BuildType1Bits(Packed_Q0ABC, Packed_W1ABC, Extra_Val128);
        string? result = MessageUnpacker.TryUnpack(bits);
        result.Should().BeNull("val=128 exceeds the valid R-prefix ceiling of 127");
    }

    [Fact(DisplayName = "FR-029: TryUnpack returns null for report extra field with val 2194 (+2159 dB)")]
    public void TryUnpack_ExtraVal2194_ReturnsNull()
    {
        var bits = BuildType1Bits(Packed_Q0ABC, Packed_W1ABC, Extra_Val2194);
        string? result = MessageUnpacker.TryUnpack(bits);
        result.Should().BeNull("SNR val=2194 is far outside the valid range [1,127]");
    }

    [Fact(DisplayName = "FR-029: TryUnpack returns null for report extra field with val 4052 (+4017 dB)")]
    public void TryUnpack_ExtraVal4052_ReturnsNull()
    {
        var bits = BuildType1Bits(Packed_Q0ABC, Packed_W1ABC, Extra_Val4052);
        string? result = MessageUnpacker.TryUnpack(bits);
        result.Should().BeNull("SNR val=4052 is far outside the valid range [1,127]");
    }

    // NOTE: The callsign validator (IsValidCallsign28) is intentionally NOT called in
    // the decode path. With the FT8 mixed-radix decoder, position 2 is always a digit
    // and positions 3-5 are always letters/space by construction, so the check is a
    // no-op. The SNR range check (IsValidExtra15) is the correct and sufficient filter —
    // all 281 false positives in the p10 corpus had impossible SNR values (> +25 dB).

    [Fact(DisplayName = "FR-029: TryUnpack returns decoded string for Type 1 message with CQ special value")]
    public void TryUnpack_CqSpecialValue_ReturnsDecodedString()
    {
        // packed=2 → CQ, paired with a valid c2 and valid extra field.
        var bits = BuildType1Bits(2UL, Packed_W1ABC, Extra_SnrPlus11);
        string? result = MessageUnpacker.TryUnpack(bits);
        result.Should().NotBeNull("CQ (packed=2) is a valid special callsign value");
    }

    [Fact(DisplayName = "FR-029: TryUnpack returns decoded string for valid grid square FN13")]
    public void TryUnpack_GridFN13_ReturnsDecodedString()
    {
        var bits = BuildType1Bits(Packed_Q0ABC, Packed_W1ABC, Extra_FN13);
        string? result = MessageUnpacker.TryUnpack(bits);
        result.Should().NotBeNull("FN13 is a valid grid square; grid extras always pass the 14-bit-constrained validator");
        result.Should().Contain("FN13");
    }

    [Fact(DisplayName = "FR-029: TryUnpack returns null for i3=1 message with impossible SNR report")]
    public void TryUnpack_I3_1_ImpossibleSnr_ReturnsNull()
    {
        // Build an i3=1 message with val=2194 (+2159 dB SNR) — plugs the legacy-format bypass.
        var bits = new byte[77];
        WriteBits(bits,  0, 28, Packed_Q0ABC);
        WriteBits(bits, 28, 28, Packed_W1ABC);
        WriteBits(bits, 56, 15, Extra_Val2194);
        // n3=0 (bits 71-73=0), i3=1 (bits 74-76=001)
        bits[76] = 1; // i3 = 1
        string? result = MessageUnpacker.TryUnpack(bits);
        result.Should().BeNull("i3=1 message with val=2194 must be rejected by SNR range check (valid range [1,127])");

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
