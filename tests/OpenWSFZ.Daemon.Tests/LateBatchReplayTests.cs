using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// late-batches-in-qso AC1 / R4: with no supplementary batches the transmitted message sequence and slot starts equal
/// origin/main <c>0c7124db</c>'s, as exact lists, and an identical script that also feeds EMPTY batches 2 and 3 after every
/// batch 1 gives the same lists. The "before" lists below were recorded by running <c>QsoReplayScripts</c> (the same file, no
/// post-change API) in a throwaway worktree of <c>0c7124db</c>; their SHA-256 are in the test names' remarks.
/// </summary>
[Trait("Category", "Unit")]
public sealed class LateBatchReplayTests
{
    // Recorded on 0c7124db. answerer.txt SHA-256 21183fded9435b8c76c17240aeed9d731a66c63b1ee26b66c7fb34c07cbb317a
    private static readonly string[] AnswererOnMain =
    [
        "00:00:16.000 Q1TST Q1OFZ JO33",
        "00:00:46.000 Q1TST Q1OFZ R-05",
        "00:01:16.000 Q1TST Q1OFZ 73",
        "00:01:31.000 Q1ABC Q1OFZ JO33",
        "00:02:01.000 Q1ABC Q1OFZ JO33",
        "00:02:31.000 Q1ABC Q1OFZ R-12",
        "00:03:01.000 Q1ABC Q1OFZ R-12",
        "00:03:31.000 Q1ABC Q1OFZ 73",
        "00:03:46.000 Q1DEF Q1OFZ JO33",
        "00:04:31.000 Q1GHI Q1OFZ JO33",
        "00:05:01.000 Q1GHI Q1OFZ JO33",
        "00:05:31.000 Q1GHI Q1OFZ JO33",
        "end state=Idle retry=0",
    ];

    // Recorded on 0c7124db. caller.txt SHA-256 19e7bbab70c251697cdb27f121a8300ad4585b86f1a9db6024c3896ee8490747
    private static readonly string[] CallerOnMain =
    [
        "00:00:16.000 CQ Q1OFZ JO33",
        "00:00:46.000 Q1TST Q1OFZ -05",
        "00:01:16.000 Q1TST Q1OFZ RR73",
        "00:01:31.000 CQ Q1OFZ JO33",
        "00:02:01.000 CQ Q1OFZ JO33",
        "00:02:31.000 Q1ABC Q1OFZ -05",
        "00:03:01.000 Q1ABC Q1OFZ -05",
        "00:03:31.000 Q1ABC Q1OFZ RR73",
        "00:03:46.000 CQ Q1OFZ JO33",
        "00:04:16.000 Q1DEF Q1OFZ -05",
        "end state=Idle retry=0",
    ];

    /// <summary>Empty batch 2 and batch 3 after every batch 1 (subtraction on, nothing found).</summary>
    private static IEnumerable<(TimeSpan After, DecodeBatch Batch)> EmptyLate(int cycle)
    {
        yield return (TimeSpan.FromSeconds(3.0), new DecodeBatch(Cy.At(cycle), [], 2));
        yield return (TimeSpan.FromSeconds(4.5), new DecodeBatch(Cy.At(cycle), [], 3));
    }

    [Fact(DisplayName = "AC1/R4: answerer, batch 1 only — transmitted messages and slot starts equal 0c7124db (exact list)")]
    public async Task Answerer_Batch1Only_EqualsMain()
        => (await QsoReplayScripts.AnswererAsync()).Should().Equal(AnswererOnMain);

    [Fact(DisplayName = "AC1/R4: answerer, EMPTY batches 2 and 3 after every batch 1 — the same exact list")]
    public async Task Answerer_EmptyLateBatches_EqualsMain()
        => (await QsoReplayScripts.AnswererAsync(EmptyLate)).Should().Equal(AnswererOnMain);

    [Fact(DisplayName = "AC1/R4: caller, batch 1 only — transmitted messages and slot starts equal 0c7124db (exact list)")]
    public async Task Caller_Batch1Only_EqualsMain()
        => (await QsoReplayScripts.CallerAsync()).Should().Equal(CallerOnMain);

    [Fact(DisplayName = "AC1/R4: caller, EMPTY batches 2 and 3 after every batch 1 — the same exact list")]
    public async Task Caller_EmptyLateBatches_EqualsMain()
        => (await QsoReplayScripts.CallerAsync(EmptyLate)).Should().Equal(CallerOnMain);
}
