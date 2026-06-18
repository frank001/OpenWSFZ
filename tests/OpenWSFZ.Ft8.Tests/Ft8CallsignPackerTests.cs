using FluentAssertions;
using OpenWSFZ.Ft8;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Unit tests for <see cref="Ft8CallsignPacker.Pack28"/> (H6, D-001).
///
/// <para>
/// All callsigns use ITU-unallocated Q-prefix (NFR-021).
/// Expected N28 values are derived from the canonical ft8_lib (kgoba/ft8_lib v2)
/// mixed-radix formula as implemented in <c>ft8/message.c pack_basecall()</c>:
/// <code>
///   n = ((((n0 * 36 + n1) * 10 + n2) * 27 + n3) * 27 + n4) * 27 + n5
///   N28 = NTOKENS + MAX22 + n  (= 6,257,896 + n)
/// </code>
/// where the character-set indices are (from ft8/text.h):
///   pos 0: FT8_CHAR_TABLE_ALPHANUM_SPACE — space=0, '0'=1…'9'=10, 'A'=11…'Z'=36
///   pos 1: FT8_CHAR_TABLE_ALPHANUM      — '0'=0…'9'=9, 'A'=10…'Z'=35 (no space)
///   pos 2: FT8_CHAR_TABLE_NUMERIC       — '0'=0…'9'=9
///   pos 3-5: FT8_CHAR_TABLE_LETTERS_SPACE — space=0, 'A'=1…'Z'=26
/// </para>
/// </summary>
public sealed class Ft8CallsignPackerTests
{
    // ── Helper ────────────────────────────────────────────────────────────────

    /// <summary>
    /// Unpacks a 4-byte Pack28 array back to N28 for round-trip verification.
    /// N28 = (byte[0]<<20) | (byte[1]<<12) | (byte[2]<<4) | (byte[3]>>4)
    /// </summary>
    private static long Unpack(byte[] b)
    {
        b.Should().HaveCount(4);
        return ((long)b[0] << 20) | ((long)b[1] << 12) | ((long)b[2] << 4) | (long)(b[3] >> 4);
    }

    // ── Expected N28 values (derived from ft8_lib pack_basecall source) ───────

    // "Q1ABC" → normalised " Q1ABC"
    //   pos 0: ' '=0, pos 1: 'Q'=10+16=26, pos 2: '1'=1
    //   pos 3: 'A'=1, pos 4: 'B'=2, pos 5: 'C'=3
    //   n = ((((0*36+26)*10+1)*27+1)*27+2)*27+3 = 5,138,049
    //   N28 = 6,257,896 + 5,138,049 = 11,395,945
    private const long N28_Q1ABC = 11_395_945L;

    // "Q9XYZ" → normalised " Q9XYZ"
    //   pos 0: ' '=0, pos 1: 'Q'=26, pos 2: '9'=9
    //   pos 3: 'X'=24, pos 4: 'Y'=25, pos 5: 'Z'=26
    //   n = ((((0*36+26)*10+9)*27+24)*27+25)*27+26 = 5,312,924
    //   N28 = 6,257,896 + 5,312,924 = 11,570,820
    private const long N28_Q9XYZ = 11_570_820L;

    // "QA1BC" → normalised "QA1BC " (digit at index 2, pad one trailing space)
    //   pos 0: 'Q'=11+16=27, pos 1: 'A'=0+10=10, pos 2: '1'=1
    //   pos 3: 'B'=2, pos 4: 'C'=3, pos 5: ' '=0
    //   n = ((((27*36+10)*10+1)*27+2)*27+3)*27+0 = 193,308,282
    //   N28 = 6,257,896 + 193,308,282 = 199,566,178
    private const long N28_QA1BC = 199_566_178L;

    // "Q1OFZ" → normalised " Q1OFZ"
    //   pos 0: ' '=0, pos 1: 'Q'=26, pos 2: '1'=1
    //   pos 3: 'O'=15, pos 4: 'F'=6, pos 5: 'Z'=26
    //   n = ((((0*36+26)*10+1)*27+15)*27+6)*27+26 = 5,148,386
    //   N28 = 6,257,896 + 5,148,386 = 11,406,282
    private const long N28_Q1OFZ = 11_406_282L;

    // ── Happy-path tests ──────────────────────────────────────────────────────

    [Fact(DisplayName = "Pack28('Q1ABC'): 1-prefix Q-callsign packs to correct 4-byte N28")]
    public void Pack28_Q1ABC_ProducesCorrectBytes()
    {
        byte[] result = Ft8CallsignPacker.Pack28("Q1ABC");

        result.Should().HaveCount(4,
            "Pack28 must return exactly 4 bytes for a valid standard callsign");
        Unpack(result).Should().Be(N28_Q1ABC,
            "N28 for 'Q1ABC' (normalised ' Q1ABC') must equal 11,395,945");
    }

    [Fact(DisplayName = "Pack28('Q9XYZ'): 9-prefix Q-callsign packs to correct 4-byte N28")]
    public void Pack28_Q9XYZ_ProducesCorrectBytes()
    {
        byte[] result = Ft8CallsignPacker.Pack28("Q9XYZ");

        result.Should().HaveCount(4);
        Unpack(result).Should().Be(N28_Q9XYZ,
            "N28 for 'Q9XYZ' (normalised ' Q9XYZ') must equal 11,570,820");
    }

    [Fact(DisplayName = "Pack28('QA1BC'): 2-prefix Q-callsign with digit at position 2 packs correctly")]
    public void Pack28_QA1BC_DigitAtPosition2_ProducesCorrectBytes()
    {
        // "QA1BC" has the district digit at index 2 — no leading space is prepended.
        // The 6-char normalised form is "QA1BC " (one trailing space).
        byte[] result = Ft8CallsignPacker.Pack28("QA1BC");

        result.Should().HaveCount(4);
        Unpack(result).Should().Be(N28_QA1BC,
            "N28 for 'QA1BC' (normalised 'QA1BC ') must equal 199,566,178");
    }

    [Fact(DisplayName = "Pack28('Q1OFZ'): QSO-answerer own-callsign packs to correct N28")]
    public void Pack28_Q1OFZ_ProducesCorrectBytes()
    {
        byte[] result = Ft8CallsignPacker.Pack28("Q1OFZ");

        result.Should().HaveCount(4);
        Unpack(result).Should().Be(N28_Q1OFZ,
            "N28 for 'Q1OFZ' must equal 11,406,282 (used as mycall in H6 integration test)");
    }

    [Fact(DisplayName = "Pack28 is case-insensitive — lowercase produces same bytes as uppercase")]
    public void Pack28_LowercaseCallsign_SameResultAsUppercase()
    {
        Ft8CallsignPacker.Pack28("q1abc").Should().BeEquivalentTo(
            Ft8CallsignPacker.Pack28("Q1ABC"),
            "Pack28 must normalise to uppercase before encoding");
    }

    // ── Failure cases ─────────────────────────────────────────────────────────

    [Fact(DisplayName = "Pack28 returns empty array for non-standard callsign (no digit)")]
    public void Pack28_NoDigit_ReturnsEmptyArray()
    {
        // "QABC" has no digit — cannot be a standard callsign.
        Ft8CallsignPacker.Pack28("QABC").Should().BeEmpty(
            "a callsign with no district digit is not a standard callsign");
    }

    [Fact(DisplayName = "Pack28 returns empty array for empty string input")]
    public void Pack28_EmptyString_ReturnsEmptyArray()
    {
        Ft8CallsignPacker.Pack28("").Should().BeEmpty();
    }

    [Fact(DisplayName = "Pack28 returns empty array for whitespace-only input")]
    public void Pack28_WhitespaceOnly_ReturnsEmptyArray()
    {
        Ft8CallsignPacker.Pack28("   ").Should().BeEmpty();
    }

    [Fact(DisplayName = "Pack28 returns empty array for callsign with digit at position 0")]
    public void Pack28_DigitAtPosition0_ReturnsEmptyArray()
    {
        // "1QABC" has digit at index 0 — neither ft8_lib pattern matches.
        Ft8CallsignPacker.Pack28("1QABC").Should().BeEmpty(
            "a callsign with a digit at index 0 does not match either standard pattern");
    }

    [Fact(DisplayName = "Pack28 does not throw on any input — returns empty for invalid")]
    public void Pack28_AlwaysReturnsArrayNotThrows()
    {
        // No call to Pack28 should ever throw; callers rely on empty-array → disabled AP.
        var act1 = () => Ft8CallsignPacker.Pack28("NOTAVALIDCALLSIGN");
        var act2 = () => Ft8CallsignPacker.Pack28("CQ");
        var act3 = () => Ft8CallsignPacker.Pack28("DE");

        act1.Should().NotThrow();
        act2.Should().NotThrow();
        act3.Should().NotThrow();
    }

    // ── Byte-layout tests ─────────────────────────────────────────────────────

    [Fact(DisplayName = "Pack28 MSB-first byte layout: byte[0] carries bits 27..20 of N28")]
    public void Pack28_ByteLayout_MsbFirstPacking()
    {
        // N28 for "Q9XYZ" = 11,570,820 = 0x00B08E84
        // As a 28-bit MSB-first field:
        //   byte[0] = (N28 >> 20) & 0xFF = 11  = 0x0B
        //   byte[1] = (N28 >> 12) & 0xFF = 8   = 0x08
        //   byte[2] = (N28 >>  4) & 0xFF = 232 = 0xE8
        //   byte[3] = (N28 <<  4) & 0xF0 = 64  = 0x40  (N28 & 0x0F = 4, shifted to high nibble)
        byte[] b = Ft8CallsignPacker.Pack28("Q9XYZ");

        b.Should().HaveCount(4);
        b[0].Should().Be(0x0B, "bits 27..20 of N28(Q9XYZ)=11,570,820");
        b[1].Should().Be(0x08, "bits 19..12 of N28(Q9XYZ)");
        b[2].Should().Be(0xE8, "bits 11..4  of N28(Q9XYZ)");
        b[3].Should().Be(0x40, "bits 3..0   of N28(Q9XYZ) in high nibble of byte[3]");
    }
}
