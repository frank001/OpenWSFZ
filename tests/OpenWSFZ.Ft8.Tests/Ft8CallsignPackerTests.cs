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

    // NOTE (f-003-ap-assist-nonstandard-callsigns): "QABC" (no digit) and "1QABC" (digit at
    // index 0) no longer return an empty array — both are 3–11 character, hash-alphabet-valid
    // strings that don't match either standard pattern, so they now pack via the nonstandard/
    // compound-callsign hash sub-range instead (see the "Nonstandard/compound callsign hashing"
    // region below for the corresponding positive-path tests). The two tests below use inputs
    // that are still genuinely unsupported after this change.

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

    [Fact(DisplayName = "Pack28 returns empty array for a 2-character string with no digit (too short to hash)")]
    public void Pack28_TooShortForHashAndNoDigit_ReturnsEmptyArray()
    {
        // "QA" has no digit (not a standard callsign) and is shorter than the 3-character
        // minimum ihashcall's hash sub-range accepts — genuinely unsupported, not just
        // "not yet implemented".
        Ft8CallsignPacker.Pack28("QA").Should().BeEmpty(
            "a 2-character string with no digit is neither a standard callsign nor long enough to hash");
    }

    [Fact(DisplayName = "Pack28 returns empty array for input longer than 11 characters")]
    public void Pack28_LongerThan11Characters_ReturnsEmptyArray()
    {
        // 18 characters — exceeds ihashcall's 11-character field width, so it cannot fall back
        // to the nonstandard-callsign hash sub-range either.
        Ft8CallsignPacker.Pack28("NOTAVALIDCALLSIGN").Should().BeEmpty(
            "a string longer than 11 characters cannot be hash-encoded");
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

    // ── Special-token packing (f-003-ap-assist-nonstandard-callsigns) ────────

    [Fact(DisplayName = "Pack28('CQ'): plain CQ token packs to n28 = 2")]
    public void Pack28_Cq_PacksToN28Two()
    {
        byte[] result = Ft8CallsignPacker.Pack28("CQ");

        result.Should().HaveCount(4);
        Unpack(result).Should().Be(2L);
    }

    [Fact(DisplayName = "Pack28('DE'): DE token packs to n28 = 0")]
    public void Pack28_De_PacksToN28Zero()
    {
        byte[] result = Ft8CallsignPacker.Pack28("DE");

        result.Should().HaveCount(4);
        Unpack(result).Should().Be(0L);
    }

    [Fact(DisplayName = "Pack28('QRZ'): QRZ token packs to n28 = 1")]
    public void Pack28_Qrz_PacksToN28One()
    {
        byte[] result = Ft8CallsignPacker.Pack28("QRZ");

        result.Should().HaveCount(4);
        Unpack(result).Should().Be(1L);
    }

    [Fact(DisplayName = "Pack28('CQ 123'): 3-digit numeral CQ packs to n28 = 3 + 123 = 126")]
    public void Pack28_CqNumeralSuffix_PacksToNTokenBasePlusNumeral()
    {
        byte[] result = Ft8CallsignPacker.Pack28("CQ 123");

        result.Should().HaveCount(4);
        Unpack(result).Should().Be(126L);
    }

    [Fact(DisplayName = "Pack28('CQ 000'): lowest 3-digit numeral CQ packs to n28 = 3")]
    public void Pack28_CqNumeralSuffixZero_PacksToNTokenBase()
    {
        byte[] result = Ft8CallsignPacker.Pack28("CQ 000");

        result.Should().HaveCount(4);
        Unpack(result).Should().Be(3L);
    }

    [Fact(DisplayName = "Pack28('CQ DX'): directed CQ with a non-numeric suffix is not yet supported")]
    public void Pack28_DirectedCqNonNumericSuffix_ReturnsEmptyArray()
    {
        // Tracked as a follow-up (design D3) — the exact c28 encoding for this form is not yet
        // confirmed against the vendored ft8_lib source, so it must not be guessed at.
        Ft8CallsignPacker.Pack28("CQ DX").Should().BeEmpty();
    }

    [Fact(DisplayName = "Pack28 special tokens are case-insensitive")]
    public void Pack28_SpecialTokens_CaseInsensitive()
    {
        Ft8CallsignPacker.Pack28("cq").Should().BeEquivalentTo(Ft8CallsignPacker.Pack28("CQ"));
        Ft8CallsignPacker.Pack28("de").Should().BeEquivalentTo(Ft8CallsignPacker.Pack28("DE"));
        Ft8CallsignPacker.Pack28("qrz").Should().BeEquivalentTo(Ft8CallsignPacker.Pack28("QRZ"));
    }

    // ── Nonstandard/compound-callsign hashing (f-003-ap-assist-nonstandard-callsigns) ────────

    [Fact(DisplayName = "Pack28('PJ4/K1ABC'): 9-character compound callsign hashes instead of returning empty")]
    public void Pack28_CompoundCallsign_HashesInsteadOfEmpty()
    {
        // Expected n28 = NTOKENS + ihashcall("PJ4/K1ABC", bits: 22) = 2,063,592 + 1,420,834
        // = 3,484,426 (cross-checked against qa/rr-study/synth/packing.py's independent
        // ihashcall implementation — task 2.3).
        byte[] result = Ft8CallsignPacker.Pack28("PJ4/K1ABC");

        result.Should().HaveCount(4).And.NotBeEmpty();
        Unpack(result).Should().Be(3_484_426L);
    }

    [Fact(DisplayName = "Pack28('QABC'): 4-character callsign with no digit hashes instead of returning empty")]
    public void Pack28_NoDigitShortCallsign_HashesInsteadOfEmpty()
    {
        long expected = 2_063_592L + Ft8CallsignPacker.Ihashcall("QABC");
        byte[] result = Ft8CallsignPacker.Pack28("QABC");

        result.Should().HaveCount(4);
        Unpack(result).Should().Be(expected);
    }

    [Fact(DisplayName = "Pack28('1QABC'): digit-at-position-0 callsign hashes instead of returning empty")]
    public void Pack28_DigitAtPosition0_HashesInsteadOfEmpty()
    {
        long expected = 2_063_592L + Ft8CallsignPacker.Ihashcall("1QABC");
        byte[] result = Ft8CallsignPacker.Pack28("1QABC");

        result.Should().HaveCount(4);
        Unpack(result).Should().Be(expected);
    }

    [Fact(DisplayName = "Pack28 standard-basecall path is byte-for-byte unchanged (regression guard)")]
    public void Pack28_StandardBasecall_RegressionUnchanged()
    {
        // Same input/expected pair as Pack28_Q1ABC_ProducesCorrectBytes above — restated here as
        // an explicit regression guard for design D1's "no behavioural change to the existing
        // path" goal, now that Pack28 has two additional branches ahead of the standard-basecall
        // check.
        Unpack(Ft8CallsignPacker.Pack28("Q1ABC")).Should().Be(N28_Q1ABC);
    }

    // ── Ihashcall — 22/12/10-bit callsign hash (f-003-ap-assist-nonstandard-callsigns) ────────
    //
    // Shared test vector: fictional Q-prefix nonstandard callsign "Q0ABCDEF" (8 chars,
    // GDPR-compliant synthetic callsign per MEMORY.md's privacy/callsign policy). Expected hash
    // values are the same shared vector already validated by
    // qa/rr-study/tests/test_packing.py's TestIhashcall (task 2.2/2.3) — an independently
    // hand-derived value from the published ihashcall formula, not copied from this port.

    private const int Q0ABCDEF_H22 = 2_523_336;
    private const int Q0ABCDEF_H12 = 2_464;
    private const int Q0ABCDEF_H10 = 616;

    [Fact(DisplayName = "Ihashcall('Q0ABCDEF', bits: 22) matches the shared known-vector table")]
    public void Ihashcall_SharedVector_H22()
    {
        Ft8CallsignPacker.Ihashcall("Q0ABCDEF", bits: 22).Should().Be(Q0ABCDEF_H22);
    }

    [Fact(DisplayName = "Ihashcall('Q0ABCDEF', bits: 12) matches the shared known-vector table")]
    public void Ihashcall_SharedVector_H12()
    {
        Ft8CallsignPacker.Ihashcall("Q0ABCDEF", bits: 12).Should().Be(Q0ABCDEF_H12);
    }

    [Fact(DisplayName = "Ihashcall('Q0ABCDEF', bits: 10) matches the shared known-vector table")]
    public void Ihashcall_SharedVector_H10()
    {
        Ft8CallsignPacker.Ihashcall("Q0ABCDEF", bits: 10).Should().Be(Q0ABCDEF_H10);
    }

    [Fact(DisplayName = "Ihashcall h12 is the top bits of h22")]
    public void Ihashcall_H12IsTopBitsOfH22()
    {
        Ft8CallsignPacker.Ihashcall("Q0ABCDEF", bits: 12).Should().Be(
            Ft8CallsignPacker.Ihashcall("Q0ABCDEF", bits: 22) >> 10);
    }

    [Fact(DisplayName = "Ihashcall h10 is the top bits of h22")]
    public void Ihashcall_H10IsTopBitsOfH22()
    {
        Ft8CallsignPacker.Ihashcall("Q0ABCDEF", bits: 10).Should().Be(
            Ft8CallsignPacker.Ihashcall("Q0ABCDEF", bits: 22) >> 12);
    }

    [Fact(DisplayName = "Ihashcall is deterministic")]
    public void Ihashcall_Deterministic()
    {
        Ft8CallsignPacker.Ihashcall("Q0ABCDEF").Should().Be(Ft8CallsignPacker.Ihashcall("Q0ABCDEF"));
        Ft8CallsignPacker.Ihashcall("PJ4/K1ABC").Should().Be(Ft8CallsignPacker.Ihashcall("PJ4/K1ABC"));
    }

    [Fact(DisplayName = "Ihashcall is case-insensitive")]
    public void Ihashcall_CaseInsensitive()
    {
        Ft8CallsignPacker.Ihashcall("q0abcdef").Should().Be(Ft8CallsignPacker.Ihashcall("Q0ABCDEF"));
    }

    [Fact(DisplayName = "Ihashcall result fits within the requested bit width")]
    public void Ihashcall_FitsInRequestedBits()
    {
        int h22 = Ft8CallsignPacker.Ihashcall("Q0ABCDEF", bits: 22);
        h22.Should().BeInRange(0, (1 << 22) - 1);
    }

    [Fact(DisplayName = "Ihashcall throws for a callsign longer than 11 characters")]
    public void Ihashcall_TooLong_Throws()
    {
        var act = () => Ft8CallsignPacker.Ihashcall("Q0ABCDEFGHIJ"); // 12 chars
        act.Should().Throw<ArgumentException>();
    }

    [Fact(DisplayName = "Ihashcall throws for a character outside the 38-character hash alphabet")]
    public void Ihashcall_InvalidCharacter_Throws()
    {
        var act = () => Ft8CallsignPacker.Ihashcall("Q0AB#DEF"); // '#' is not in the hash alphabet
        act.Should().Throw<ArgumentException>();
    }

    [Fact(DisplayName = "Ihashcall throws for an unsupported bit width")]
    public void Ihashcall_UnsupportedBitWidth_Throws()
    {
        var act = () => Ft8CallsignPacker.Ihashcall("Q0ABCDEF", bits: 8);
        act.Should().Throw<ArgumentOutOfRangeException>();
    }
}
