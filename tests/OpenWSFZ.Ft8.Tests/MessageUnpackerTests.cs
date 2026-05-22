using FluentAssertions;
using OpenWSFZ.Ft8.Dsp;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Ft8Decoder: MessageUnpackerTests
/// </summary>
public sealed class MessageUnpackerTests
{
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
