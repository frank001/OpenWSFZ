using FluentAssertions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="QsoMessageParsing"/> — the shared L2 (bracket-strip) helper for
/// F-001 R5's L1+L2 developer slice
/// (<c>dev-tasks/2026-08-27-1645-f001-r5-l1l2-developer-slice.md</c>).
///
/// NFR-021: all callsigns use ITU-unallocated Q-prefix synthetic calls.
/// </summary>
[Trait("Category", "Unit")]
public sealed class QsoMessageParsingTests
{
    // ── StripBrackets ─────────────────────────────────────────────────────────

    [Fact(DisplayName = "StripBrackets: strips one leading '<' and one trailing '>'")]
    public void StripBrackets_RemovesSurroundingBrackets()
        => QsoMessageParsing.StripBrackets("<Q1OFZ>").Should().Be("Q1OFZ");

    [Fact(DisplayName = "StripBrackets: a plain (unbracketed) token is returned unchanged")]
    public void StripBrackets_PlainToken_Unchanged()
        => QsoMessageParsing.StripBrackets("Q1OFZ").Should().Be("Q1OFZ");

    // ── AC-2: the all-dot / empty unresolved-hash marker never matches anything ─────────

    [Fact(DisplayName = "AC-2: bracket-wrapped all-dot marker (<...>) never matches our own callsign")]
    public void DestMatchesOwnCallsign_AllDotMarker_NeverMatches()
        => QsoMessageParsing.DestMatchesOwnCallsign("<...>", "Q1OFZ").Should().BeFalse();

    [Fact(DisplayName = "AC-2 degenerate edge: all-dot marker never matches even when the hypothetical own-call is itself '...'")]
    public void DestMatchesOwnCallsign_AllDotMarker_DoesNotMatchAllDotOwnCallsign()
        => QsoMessageParsing.DestMatchesOwnCallsign("<...>", "...").Should().BeFalse();

    [Fact(DisplayName = "AC-2: an empty dest after stripping never matches anything")]
    public void DestMatchesOwnCallsign_EmptyAfterStrip_NeverMatches()
        => QsoMessageParsing.DestMatchesOwnCallsign("<>", "Q1OFZ").Should().BeFalse();

    [Fact(DisplayName = "IsUnresolvedHashMarker: true for an all-dot string")]
    public void IsUnresolvedHashMarker_AllDots_ReturnsTrue()
        => QsoMessageParsing.IsUnresolvedHashMarker("...").Should().BeTrue();

    [Fact(DisplayName = "IsUnresolvedHashMarker: true for an empty string")]
    public void IsUnresolvedHashMarker_Empty_ReturnsTrue()
        => QsoMessageParsing.IsUnresolvedHashMarker("").Should().BeTrue();

    [Fact(DisplayName = "IsUnresolvedHashMarker: false for a real callsign")]
    public void IsUnresolvedHashMarker_RealCallsign_ReturnsFalse()
        => QsoMessageParsing.IsUnresolvedHashMarker("Q1OFZ").Should().BeFalse();

    // ── AC-3: bracket-wrapped dest exact-match boundary ──────────────────────

    [Fact(DisplayName = "AC-3: bracket-wrapped dest matching our own callsign returns true")]
    public void DestMatchesOwnCallsign_BracketWrappedExactMatch_ReturnsTrue()
        => QsoMessageParsing.DestMatchesOwnCallsign("<Q1OFZ>", "Q1OFZ").Should().BeTrue();

    [Fact(DisplayName = "AC-3: bracket-wrapped dest is case-insensitive against our own callsign")]
    public void DestMatchesOwnCallsign_BracketWrappedCaseInsensitive_ReturnsTrue()
        => QsoMessageParsing.DestMatchesOwnCallsign("<q1ofz>", "Q1OFZ").Should().BeTrue();

    [Fact(DisplayName = "AC-3: a near-miss own-call (superstring) does not match — exact-match boundary, not substring-contains")]
    public void DestMatchesOwnCallsign_NearMissSuperstring_ReturnsFalse()
        => QsoMessageParsing.DestMatchesOwnCallsign("<Q1OFZ>", "Q1OFZQ").Should().BeFalse();

    [Fact(DisplayName = "AC-3: a near-miss own-call (substring) does not match — exact-match boundary, not substring-contains")]
    public void DestMatchesOwnCallsign_NearMissSubstring_ReturnsFalse()
        => QsoMessageParsing.DestMatchesOwnCallsign("<Q1OFZQ>", "Q1OFZ").Should().BeFalse();

    [Fact(DisplayName = "An unbracketed dest matching our own callsign still returns true (pre-existing L2-unaffected path)")]
    public void DestMatchesOwnCallsign_PlainExactMatch_ReturnsTrue()
        => QsoMessageParsing.DestMatchesOwnCallsign("Q1OFZ", "Q1OFZ").Should().BeTrue();
}
