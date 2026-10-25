using FluentAssertions;
using OpenWSFZ.Daemon.PskReporter;
using Xunit;

namespace OpenWSFZ.Daemon.Tests.PskReporter;

/// <summary>FR-090 (issue #262): strict sender extraction by classifying tokens. Q-prefix callsigns only (NFR-021).</summary>
public sealed class PskSenderExtractorTests
{
    private const string Own = "Q9OWN";

    public static TheoryData<string, string, string?> Reported => new()
    {
        { "CQ Q1ABC JO22",       "Q1ABC",   "JO22" },
        { "CQ DX Q1ABC JO22",    "Q1ABC",   "JO22" },
        { "CQ DX Q1ABC",         "Q1ABC",   null },
        { "CQ POTA Q1ABC JO22",  "Q1ABC",   "JO22" },
        { "CQ 123 Q1ABC",        "Q1ABC",   null },
        { "CQ Q1ABC/P",          "Q1ABC/P", null },
        { "CQ Q1ABC",            "Q1ABC",   null },
        { "Q2DEF Q1ABC -12",     "Q1ABC",   null },
        { "Q2DEF Q1ABC R-05",    "Q1ABC",   null },
        { "Q2DEF Q1ABC RR73",    "Q1ABC",   null },   // RR73 matches the grid pattern but is never a grid
        { "Q2DEF Q1ABC JO22",    "Q1ABC",   "JO22" },
        { "Q2DEF Q1ABC/P -07",   "Q1ABC/P", null },
        { "Q2DEF Q1ABC 73",      "Q1ABC",   null },
        { "Q2DEF Q1ABC RRR",     "Q1ABC",   null },
    };

    [Theory(DisplayName = "FR-090: T4: the sender table - the call and the grid (only in the grid position) are extracted, never token 0")]
    [MemberData(nameof(Reported))]
    public void T4_Reported(string message, string call, string? grid)
    {
        PskSenderExtractor.TryExtract(message, Own, out var sender, out _).Should().BeTrue(message);
        sender!.Callsign.Should().Be(call);
        sender.Locator.Should().Be(grid);
    }

    public static TheoryData<string, string> NotReported => new()
    {
        { "Q2DEF <...> -12",                       "Hashed" },
        { "<...> Q1ABC 73",                        "Hashed" },
        { "<Q1ABC> Q2DEF -12",                     "Hashed" },
        { "CQ DX",                                 "Unparseable" },
        { "TNX BILL 73 GL",                        "Unparseable" },
        { "0123456789ABCDEF01",                    "Unparseable" },   // telemetry: one hex token
        { "Q1ABC RR73; Q2DEF <Q3GHI> -08",         "Hashed" },
        { "Q2DEF Q1ABC HELLO",                     "Unparseable" },
        { "Q2DEF Q1ABC",                           "Unparseable" },
        { "CQ Q1ABC JO22 EXTRA",                   "Unparseable" },
        { "Q9OWN Q9OWN -05",                       "OwnCall" },
        { "Q2DEF Q9OWN/P -05",                     "OwnCall" },
        { "Q2DEF q9own -05",                       "OwnCall" },
        { "CQ Q9OWN JO33",                         "OwnCall" },
    };

    [Theory(DisplayName = "FR-090: T4: hashed, keyword, free-text, telemetry, unparseable and own-call senders are not reported, with their reason")]
    [MemberData(nameof(NotReported))]
    public void T4_NotReported(string message, string reason)
    {
        PskSenderExtractor.TryExtract(message, Own, out var sender, out var why).Should().BeFalse(message);
        sender.Should().BeNull();
        why.ToString().Should().Be(reason, message);
    }

    [Fact(DisplayName = "FR-090: T4: the own-call check compares the BASE call (prefix and suffix stripped), case-insensitively, not the full string")]
    public void T4_OwnCall_IsComparedOnTheBaseCall()
    {
        PskSenderExtractor.TryExtract("Q2DEF DL/Q9OWN -05", "q9own", out _, out var a).Should().BeFalse();
        a.Should().Be(PskSenderRejection.OwnCall);
        PskSenderExtractor.TryExtract("Q2DEF Q9OWN/P -05", "Q9OWN/QRP", out _, out var b).Should().BeFalse();
        b.Should().Be(PskSenderRejection.OwnCall);
        PskSenderExtractor.TryExtract("Q2DEF Q9OWM -05", "Q9OWN", out var other, out _).Should().BeTrue("a different call is not the own call");
        other!.Callsign.Should().Be("Q9OWM");
    }

    [Fact(DisplayName = "FR-090: T4: no case falls back to token 0 - the addressee is never reported")]
    public void T4_NoTokenZeroFallback()
    {
        foreach (var message in new[] { "Q2DEF <...> -12", "Q2DEF Q1ABC", "Q2DEF Q1ABC HELLO", "Q2DEF TEXT HERE", "Q2DEF" })
        {
            PskSenderExtractor.TryExtract(message, Own, out var sender, out _);
            sender?.Callsign.Should().NotBe("Q2DEF", message);
        }
    }
}
