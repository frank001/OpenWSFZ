using FluentAssertions;
using OpenWSFZ.Ft8;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Unit tests for <see cref="Ft8Decoder.IsPlausibleMessage"/> (R4 — false-positive guard).
///
/// <para>
/// FT8 false LDPC convergences that pass CRC-14 by chance (≈ 1/16 384 per candidate)
/// can produce Standard QSO messages whose 15-bit grid/report field encodes an impossible
/// value.  <see cref="Ft8Decoder.IsPlausibleMessage"/> filters these out before they
/// reach the caller or ALL.TXT.
/// </para>
///
/// <para>
/// Validation rules applied to 3-token Standard QSO messages:
/// <list type="bullet">
///   <item>Maidenhead grid: first two letters must be in [A-R] (indices 0–17).</item>
///   <item>dB report: [+-][0-9][0-9] or R[+-][0-9][0-9] form.</item>
///   <item>Terminal tokens: <c>RRR</c>, <c>73</c>, <c>RR73</c>.</item>
///   <item>Hash notation (<c>&lt;HASH&gt;</c>) for unresolved Type 4 callsigns.</item>
/// </list>
/// All other message forms (CQ, ≠3 tokens, all-digit contest serials) are accepted
/// unconditionally.
/// </para>
/// </summary>
public sealed class Ft8DecoderPlausibilityTests
{
    // ── Valid messages — must be accepted ─────────────────────────────────────

    [Theory(DisplayName = "R4: IsPlausibleMessage accepts valid Standard QSO messages")]
    [InlineData("W1AW K1ABC FN31",   "standard grid")]
    [InlineData("W1AW K1ABC AA00",   "minimum Maidenhead grid")]
    [InlineData("W1AW K1ABC RR99",   "maximum valid Maidenhead grid (R=17)")]
    [InlineData("W1AW K1ABC -15",    "negative dB report")]
    [InlineData("W1AW K1ABC +05",    "positive dB report")]
    [InlineData("W1AW K1ABC -30",    "minimum dB report")]
    [InlineData("W1AW K1ABC +49",    "near-maximum dB report")]
    [InlineData("W1AW K1ABC R-12",   "received dB report with R prefix")]
    [InlineData("W1AW K1ABC R+05",   "received positive dB report")]
    [InlineData("W1AW K1ABC RRR",    "terminal RRR")]
    [InlineData("W1AW K1ABC 73",     "terminal 73")]
    [InlineData("W1AW K1ABC RR73",   "terminal RR73")]
    public void IsPlausibleMessage_ValidStandardQso_ReturnsTrue(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeTrue(
               $"'{text}' is a valid FT8 Standard QSO message ({reason})");

    [Theory(DisplayName = "R4: IsPlausibleMessage accepts CQ messages unconditionally")]
    [InlineData("CQ W1AW FN31",      "standard CQ")]
    [InlineData("CQ DX W1AW FN31",   "CQ DX — 4 tokens, accepted unconditionally")]
    [InlineData("CQ NA W1AW FN31",   "CQ NA — 4 tokens, accepted unconditionally")]
    public void IsPlausibleMessage_CqMessages_ReturnsTrue(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeTrue(
               $"'{text}' is a valid CQ message ({reason})");

    [Theory(DisplayName = "R4: IsPlausibleMessage accepts hash notation and non-3-token forms")]
    [InlineData("W1AW K1ABC <XYZ>",  "Type 4 hash notation in last token")]
    [InlineData("W1AW <XYZ>",        "2-token message — accepted unconditionally")]
    [InlineData("CQ W1AW FN31 NA",   "4-token message — accepted unconditionally")]
    [InlineData("DE W1AW",           "2-token message")]
    public void IsPlausibleMessage_HashAndNonStandardQso_ReturnsTrue(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeTrue(
               $"'{text}' should pass the filter ({reason})");

    [Theory(DisplayName = "R4: IsPlausibleMessage accepts contest serial numbers")]
    [InlineData("W1AW K1ABC 00000",  "contest serial zero")]
    [InlineData("W1AW K1ABC 12345",  "typical contest serial")]
    [InlineData("W1AW K1ABC 97799",  "maximum contest serial")]
    public void IsPlausibleMessage_ContestSerials_ReturnsTrue(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeTrue(
               $"'{text}' should pass the filter ({reason})");

    // ── Invalid messages — must be rejected ───────────────────────────────────

    [Theory(DisplayName = "R4: IsPlausibleMessage rejects impossible Maidenhead letter values")]
    [InlineData("W1AW K1ABC SN31",   "first letter 'S' > 'R' (index 18 > 17)")]
    [InlineData("W1AW K1ABC TN31",   "first letter 'T' > 'R' (index 19 > 17)")]
    [InlineData("W1AW K1ABC ZA99",   "first letter 'Z' > 'R' (index 25 > 17)")]
    [InlineData("W1AW K1ABC AS31",   "second letter 'S' > 'R' (index 18 > 17)")]
    [InlineData("W1AW K1ABC XY99",   "both letters 'X','Y' > 'R'")]
    [InlineData("W1AW K1ABC ZZ00",   "both letters 'Z','Z' > 'R' — maximum impossible grid")]
    public void IsPlausibleMessage_ImpossibleGrid_ReturnsFalse(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeFalse(
               $"'{text}' has an impossible Maidenhead letter value ({reason})");

    [Theory(DisplayName = "R4: IsPlausibleMessage rejects unrecognisable 3-token last fields")]
    [InlineData("W1AW K1ABC STUB",   "4-char token: positions [2]/[3] are not digits so grid letter check is never reached; no other pattern matches")]
    [InlineData("W1AW K1ABC WXYZ",   "4-char token: positions [2]/[3] are not digits so grid letter check is never reached; no other pattern matches")]
    public void IsPlausibleMessage_UnrecognisableField_ReturnsFalse(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeFalse(
               $"'{text}' has an unrecognisable last field ({reason})");
}
