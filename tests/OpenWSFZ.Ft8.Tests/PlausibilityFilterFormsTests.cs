using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Tests for the <c>plausibility-filter-forms</c> change (#226, #227, #228): the filter now
/// accepts <c>PREFIX/CALL</c>, <c>CQ &lt;modifier&gt; &lt;call&gt;</c> and
/// <c>CALL CALL R GRID</c>. The change is acceptance-only; the pre-existing plausibility tests
/// are the guard that nothing accepted today is rejected. Synthetic Q-prefix calls only (NFR-021).
/// </summary>
public sealed class PlausibilityFilterFormsTests
{
    [Theory(DisplayName = "#226/#227/#228: new forms are plausible")]
    [InlineData("CQ QA4/Q1ABC")]
    [InlineData("Q2ABC QA4/Q1ABC")]
    [InlineData("Q2ABC QA4/Q1ABC RR73")]
    [InlineData("CQ DX Q1ABC")]
    [InlineData("CQ POTA Q1ABC")]
    [InlineData("CQ 123 Q1ABC")]
    [InlineData("Q1ABC Q2XYZ R FN42")]
    [InlineData("<...> Q2XYZ R FN42")]
    [InlineData("Q1ABC <...> R FN42")]
    public void NewForms_ArePlausible(string text) =>
        Ft8Decoder.IsPlausibleMessage(text).Should().BeTrue();

    [Theory(DisplayName = "#226/#227/#228: near-miss forms stay rejected")]
    [InlineData("Q1ABC Q2XYZ R SS42")]
    [InlineData("Q1ABC Q2XYZ X FN42")]
    [InlineData("Q1ABC Q2XYZ R FN4")]
    [InlineData("CQ DXDXD Q1ABC")]
    [InlineData("CQ DX 3AG9672ATCH")]
    [InlineData("CQ 1234 Q1ABC")]
    [InlineData("CQ 12 Q1ABC")]
    [InlineData("CQ DX1 Q1ABC")]
    [InlineData("QA4/3AG9672ATCH Q1ABC R FN42")]
    [InlineData("Q1ABC Q2XYZ R FN42 EXTRA")]
    public void NearMissForms_StayRejected(string text) =>
        Ft8Decoder.IsPlausibleMessage(text).Should().BeFalse();

    [Theory(DisplayName = "#226: IsCallsignShapeInvalid accepts PREFIX/CALL, rejects bad halves")]
    [InlineData("QA4/Q1ABC", false)]
    [InlineData("Q1ABC/P", false)]            // today's left-base form, unchanged
    [InlineData("QA4/3AG9672ATCH", true)]     // right half is not a callsign
    [InlineData("12/Q1ABC", true)]            // prefix without a letter
    [InlineData("/Q1ABC", true)]              // empty left half
    [InlineData("QA4/", true)]                // empty right half
    [InlineData("QA4/Q1ABC/P", true)]         // two slashes: unchanged
    [InlineData("QABCDE/Q1ABC", true)]        // left half longer than a prefix
    public void CompoundCall_Shape(string token, bool expectedInvalid) =>
        Ft8Decoder.IsCallsignShapeInvalid(token).Should().Be(expectedInvalid);

    [Theory(DisplayName = "#226: a reserved prefix in the left position stays rejected")]
    [InlineData("ZZ/Q1ABC")]
    [InlineData("ZZ4/Q1ABC")]
    public void ReservedPrefixInLeftPosition_StaysRejected(string token)
    {
        var config = new CallsignGrammarConfig(
            DigitRunMax:     3,
            TotalLengthMax:  11,
            SuffixLengthMax: 6,
            ReservedPrefixExclusions:
            [
                new CallsignPrefixExclusion("ZZ", SyntheticCarveOut: false,
                    Note: "Fictional test-only exclusion entry — not a real ITU-reserved series.")
            ]);
        var store = new FixedCallsignGrammarStore(config);

        Ft8Decoder.IsCallsignShapeInvalid(token, store).Should().BeTrue();
        Ft8Decoder.IsCallsignShapeInvalid("QA4/Q1ABC", store).Should().BeFalse();
    }
}
