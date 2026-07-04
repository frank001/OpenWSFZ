using FluentAssertions;
using OpenWSFZ.Abstractions;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Unit tests for the ITU Radio Regulations Article 19-derived callsign shape grammar
/// (<c>f-002-callsign-structure-region-lookup</c>) — <see cref="Ft8Decoder.IsCallsignShapeInvalid"/>,
/// which replaces the length-only D9-R3 oversized-callsign guard covered by
/// <see cref="D009FpFilterTests"/> and <see cref="D011NonstandardCallsignFpGuardTests"/>.
///
/// <para>
/// D-011 raised the length ceiling to 11 chars to admit genuine Type 4 nonstandard-callsign
/// literals, but reopened a false-positive hole for callsign-<em>shaped</em> OSD noise ≤ 11
/// chars (the live <c>3AG9672ATCH</c> failure, D-011 §6). This file exercises the shape
/// grammar (design.md Decision 1) that closes that hole: a trailing digit-run cap (default
/// 3) applied to the <em>maximal contiguous run of digits ending at the last digit in the
/// string</em> — not an arbitrary regex split — so <c>3AG9672ATCH</c>'s 4-digit run
/// (<c>9672</c>) is rejected while <c>Q0D011ABCDE</c>'s 3-digit run (<c>011</c>) survives.
/// </para>
///
/// <para>
/// All callsigns are fictional Q-prefix synthetic calls (NFR-021) or fictional placeholders
/// shaped to match observed/hypothesised failure modes; none are real third-party callsigns.
/// </para>
/// </summary>
public sealed class CallsignShapeGrammarTests
{
    private static readonly ICallsignGrammarStore DefaultStore = FixedCallsignGrammarStore.Default;

    // ── 5.1: the live 3AG9672ATCH failure mode ────────────────────────────────

    [Theory(DisplayName = "f-002 5.1: IsCallsignShapeInvalid rejects a token whose trailing digit-run exceeds the cap (3AG9672ATCH-shaped)")]
    [InlineData("3AG9672ATCH", "fictional placeholder matching the live D-011 §6 failure mode — trailing run '9672' is 4 digits, over the default cap of 3")]
    [InlineData("Q1AB9672XYZ", "fictional placeholder — trailing run '9672' is 4 digits, same failure shape with a different prefix")]
    public void IsCallsignShapeInvalid_OverLongTrailingDigitRun_ReturnsTrue(string token, string reason)
        => Ft8Decoder.IsCallsignShapeInvalid(token, DefaultStore).Should().BeTrue(
               $"'{token}' has a trailing digit-run exceeding the configured cap and must be rejected ({reason})");

    [Fact(DisplayName = "f-002 5.1 integration: IsPlausibleMessage rejects a CQ message carrying the 3AG9672ATCH-shaped token")]
    public void IsPlausibleMessage_CqWithOverLongDigitRunToken_ReturnsFalse()
        => Ft8Decoder.IsPlausibleMessage("CQ 3AG9672ATCH", DefaultStore).Should().BeFalse(
               "the containing message must be treated as implausible per the ADDED requirement's first scenario");

    // ── 5.2: genuine nonstandard / special-event literal still accepted ──────

    [Theory(DisplayName = "f-002 5.2: IsCallsignShapeInvalid accepts a genuine nonstandard/special-event-shaped literal within the digit-run cap")]
    [InlineData("Q0D011ABCDE", "D-011's own regression fixture — trailing run '011' is 3 digits, at the cap")]
    [InlineData("Q100ABC",     "fictional 3-digit special-event number — trailing run '100' is 3 digits, at the cap")]
    [InlineData("Q1ABC",       "standard shape — trailing run '1' is 1 digit, well within cap")]
    public void IsCallsignShapeInvalid_GenuineNonstandardLiteral_ReturnsFalse(string token, string reason)
        => Ft8Decoder.IsCallsignShapeInvalid(token, DefaultStore).Should().BeFalse(
               $"'{token}' is a genuine nonstandard/standard-shaped literal and must not be rejected ({reason})");

    [Fact(DisplayName = "f-002 5.2 integration: IsPlausibleMessage accepts a CQ announcement for a genuine special-event-shaped literal")]
    public void IsPlausibleMessage_CqWithGenuineSpecialEventLiteral_ReturnsTrue()
        => Ft8Decoder.IsPlausibleMessage("CQ Q100ABC", DefaultStore).Should().BeTrue(
               "a genuine special-event-shaped literal within the digit-run cap must not regress the D-011 fix");

    // ── Total-length ceiling still applies (unchanged from D-011) ────────────

    [Theory(DisplayName = "f-002: IsCallsignShapeInvalid still rejects tokens exceeding the total-length ceiling")]
    [InlineData("Q0D011ABCDEF", "12 chars — one over the default 11-char ceiling")]
    public void IsCallsignShapeInvalid_OverLengthToken_ReturnsTrue(string token, string reason)
        => Ft8Decoder.IsCallsignShapeInvalid(token, DefaultStore).Should().BeTrue(
               $"'{token}' exceeds the total-length ceiling and must be rejected regardless of shape ({reason})");

    // ── Exempt cases unchanged ─────────────────────────────────────────────────

    [Theory(DisplayName = "f-002: IsCallsignShapeInvalid still exempts hash references and short pseudo-callsigns")]
    [InlineData("<...>", "hash reference")]
    [InlineData("CQ",    "short pseudo-callsign")]
    [InlineData("DE",    "short pseudo-callsign")]
    public void IsCallsignShapeInvalid_ExemptTokens_ReturnsFalse(string token, string reason)
        => Ft8Decoder.IsCallsignShapeInvalid(token, DefaultStore).Should().BeFalse(
               $"'{token}' is exempt from the shape grammar ({reason})");

    // ── Decision 2: reserved-prefix exclusion list is exclusionary, not a positive allow-list ──

    [Fact(DisplayName = "f-002: IsCallsignShapeInvalid accepts the synthetic Q-prefix carve-out despite Q being reserved")]
    public void IsCallsignShapeInvalid_SyntheticQPrefixCarveOut_ReturnsFalse()
        => Ft8Decoder.IsCallsignShapeInvalid("Q1ABC", DefaultStore).Should().BeFalse(
               "the Q-series carve-out (NFR-021) must be treated as shape-valid despite being reserved");

    [Fact(DisplayName = "f-002: IsCallsignShapeInvalid does not reject a shape-valid token whose prefix is absent from the exclusion table")]
    public void IsCallsignShapeInvalid_PrefixAbsentFromTable_ReturnsFalse()
        => Ft8Decoder.IsCallsignShapeInvalid("VK9AA", DefaultStore).Should().BeFalse(
               "the exclusion table is not a positive allow-list — an unlisted prefix is never rejected on that basis alone");

    [Fact(DisplayName = "f-002: IsCallsignShapeInvalid rejects a shape-valid token whose prefix matches a reserved, non-carved-out exclusion entry")]
    public void IsCallsignShapeInvalid_ReservedNonCarvedOutPrefix_ReturnsTrue()
    {
        // Fictional test-only exclusion entry (not a real ITU-reserved series) — this
        // scenario is only exercised via a custom fixture store, never shipped in the
        // default callsign-grammar.json (which only carries the real Q-series carve-out).
        var config = new CallsignGrammarConfig(
            DigitRunMax:    3,
            TotalLengthMax: 11,
            SuffixLengthMax: 6,
            ReservedPrefixExclusions:
            [
                new CallsignPrefixExclusion("ZZ", SyntheticCarveOut: false,
                    Note: "Fictional test-only exclusion entry — not a real ITU-reserved series.")
            ]);
        var store = new FixedCallsignGrammarStore(config);

        // "ZZ1ABC" parses to prefix "ZZ", digit-run "1", suffix "ABC" — shape-valid on its
        // own, but the ZZ prefix is excluded here with no carve-out.
        Ft8Decoder.IsCallsignShapeInvalid("ZZ1ABC", store).Should().BeTrue(
            "a reserved prefix with no synthetic (or other) carve-out must be rejected even though the token is otherwise shape-valid");
    }

    // ── No grammar store supplied: falls back to built-in defaults ──────────

    [Fact(DisplayName = "f-002: IsCallsignShapeInvalid falls back to CallsignGrammarConfig.BuiltInDefault when no store is supplied")]
    public void IsCallsignShapeInvalid_NoStoreSupplied_FallsBackToBuiltInDefault()
    {
        Ft8Decoder.IsCallsignShapeInvalid("3AG9672ATCH", grammarStore: null).Should().BeTrue(
            "the default fallback must apply the same digit-run cap as the built-in default config");
        Ft8Decoder.IsCallsignShapeInvalid("Q1ABC", grammarStore: null).Should().BeFalse(
            "the default fallback must accept a standard-shaped literal");
    }
}
