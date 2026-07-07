using FluentAssertions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Regression guard for the git-committed <see cref="CallsignRegionDefaults"/> seed table
/// (region-lookup-data-refresh, f-006, design.md Decision 2). Protects the one hard constraint
/// this change enforces: <c>CallsignRegionDefaults.cs</c> — unlike the runtime
/// <c>callsign-regions.json</c>, which may carry individual-callsign exception entries
/// unfiltered — must never contain or be regenerated from an individual-callsign
/// (<c>ExactCallsign</c>-flagged) source row (NFR-021: no real third-party callsign in a
/// committed file).
/// </summary>
/// <remarks>
/// This is a plain, fast, in-memory unit test over the static compiled-in
/// <see cref="CallsignRegionDefaults.Entries"/> list — no network access, no corpus fixture, no
/// R&amp;R-harness replay, no off-air data, and no multi-hour run of any kind (task 4.3's scope
/// note). It MUST pass regardless of whether <c>CallsignRegionDefaults.cs</c> is expanded with
/// additional real prefix-block data in this change or a follow-up.
/// <para>
/// <b>Shape heuristic:</b> a genuine amateur-radio callsign always follows the ITU convention of
/// prefix letter(s) + a digit + suffix letter(s) — i.e. it has at least one letter <em>before</em>
/// its first digit <em>and</em> at least one letter <em>after</em> that same digit
/// (e.g. <c>W1AW</c>, <c>PD2FZ</c>, <c>4U1VIC</c> — the digit inside <c>4U1VIC</c> that has
/// letters on both sides is the second one, "1", not the leading "4"). A country-file prefix
/// block, by contrast, is deliberately an incomplete fragment that stops at-or-before where a
/// personal suffix would begin: it either has no digit at all (<c>K</c>, <c>VE</c>, <c>DL</c>), or
/// has letters before a trailing digit with no suffix after it (<c>HB9</c>), or starts at/before
/// its digit with no leading letters (<c>3A</c>, <c>4X</c>, <c>9A</c>). No entry in today's table,
/// nor any well-formed prefix-block conversion output, satisfies "letters before AND letters after
/// the same digit" — only a full personal callsign does.
/// </para>
/// </remarks>
public sealed class CallsignRegionDefaultsTests
{
    [Fact(DisplayName = "f-006 4.3: every entry carries the mandatory synthetic Q-series entry unchanged")]
    public void Entries_ContainsSyntheticQSeriesEntry()
    {
        CallsignRegionDefaults.Entries.Should().ContainSingle(
            e => e.PrefixStart == "Q" && e.PrefixEnd == "Q" && e.Synthetic &&
                 e.Entity == "Synthetic (R&R Study)");
    }

    [Fact(DisplayName = "f-006 4.3: no entry is shaped like an individual full callsign (letters both before and after the same digit)")]
    public void Entries_NoEntryIsShapedLikeAFullCallsign()
    {
        foreach (var entry in CallsignRegionDefaults.Entries)
        {
            IsShapedLikeAFullCallsign(entry.PrefixStart).Should().BeFalse(
                $"'{entry.PrefixStart}' (entity: {entry.Entity}) looks like an individual callsign, " +
                "not a prefix block — CallsignRegionDefaults.cs must never contain or be " +
                "regenerated from an ExactCallsign-flagged source row (NFR-021).");
            IsShapedLikeAFullCallsign(entry.PrefixEnd).Should().BeFalse(
                $"'{entry.PrefixEnd}' (entity: {entry.Entity}) looks like an individual callsign, " +
                "not a prefix block.");
        }
    }

    [Theory(DisplayName = "f-006 4.3: shape heuristic sanity check — known prefix-block shapes pass, known full-callsign shapes fail")]
    // Known-good: real DXCC prefix-block shapes (must NOT be flagged as full-callsign-shaped).
    [InlineData("K",    false)]
    [InlineData("VE",   false)]
    [InlineData("HB9",  false)]
    [InlineData("3A",   false)]
    [InlineData("4X",   false)]
    [InlineData("9A",   false)]
    [InlineData("UA9",  false)]
    // Known-bad: fictional Q-prefix placeholder callsign shapes (NFR-021 — no real callsigns
    // here either), which MUST be flagged as full-callsign-shaped by the heuristic.
    [InlineData("Q1ABC",  true)]
    [InlineData("Q9XYZ",  true)]
    [InlineData("Q1A",    true)]
    public void IsShapedLikeAFullCallsign_SanityCheck(string candidate, bool expected)
    {
        IsShapedLikeAFullCallsign(candidate).Should().Be(expected);
    }

    /// <summary>See class remarks for the rationale behind this heuristic.</summary>
    private static bool IsShapedLikeAFullCallsign(string prefix)
    {
        var firstDigitIndex = -1;
        for (var i = 0; i < prefix.Length; i++)
        {
            if (char.IsAsciiDigit(prefix[i]))
            {
                firstDigitIndex = i;
                break;
            }
        }

        if (firstDigitIndex < 0) return false; // no digit at all — never a full-callsign shape

        var hasLetterBefore = prefix[..firstDigitIndex].Any(char.IsAsciiLetter);
        var hasLetterAfter  = prefix[(firstDigitIndex + 1)..].Any(char.IsAsciiLetter);

        return hasLetterBefore && hasLetterAfter;
    }
}
