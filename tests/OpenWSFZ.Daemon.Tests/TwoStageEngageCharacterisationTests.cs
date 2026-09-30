using FluentAssertions;
using NSubstitute;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using OpenWSFZ.TestSupport;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// S3 (g), sub-feas-speed-redesign two-stage publish (design.md D9): CHARACTERISES what a manual (double-click)
/// engage of a CQ row that arrived as <b>batch 2</b> does, without changing any behaviour.
///
/// <para>
/// The facts this pins (verified in code at <c>ca0bcd9b</c>, <c>QsoAnswererService.cs</c>):
/// <list type="bullet">
///   <item>The double-click path (<c>AnswerCqAsync</c>) takes the callsign, frequency and CQ cycle start from the
///   browser row and does <b>not</b> consult the answerer's decode-batch snapshot (<c>_lastIdleDecodeBatch</c>). So a
///   batch-2 row is engageable by double-click even though the answerer never received batch 2 (P-5).</item>
///   <item>It arms a pending target on the OPPOSITE phase to the CQ's cycle and pushes a wake-up batch stamped for the
///   cycle that is running NOW. Batch 2 arrives about 20.5 s after the CQ's cycle started, i.e. roughly 5.5 s into the
///   opposite-phase cycle, which is that cycle: the phase matches, so the answerer fires the reply IMMEDIATELY, mid
///   slot, with no lateness rejection (D-CALLER-021: <c>TransmitAsync</c> truncates the audio buffer to fit the
///   window). What is unverified here, and left for the on-air decision, is how usable a reply started that late is.</item>
/// </list>
/// The operator-facing summary stays "visible, logged and spotted, not actionable by the automation": the automation
/// (auto-answer, the caller) never sees batch 2; only a deliberate click can act on it.
/// </para>
/// 🔒 NFR-021: synthetic Q-prefix callsigns.
/// </summary>
[Trait("Category", "Unit")]
public sealed class TwoStageEngageCharacterisationTests
{
    private const string BatchTwoStation = "Q1DEF";
    private const int    AudioFreqHz     = 2100;

    [Fact(DisplayName = "S3(g): a double-click on a batch-2 CQ row arms the reply and fires it in the running cycle; the snapshot is never consulted")]
    public async Task ManualEngage_OnBatch2Row_Characterised()
    {
        await using var sut = await DecodePumpTests.AnswererHarness.CreateAsync();

        // The answerer has NEVER been given batch 2 (or any batch): nothing to consult.
        typeof(QsoAnswererService).GetField("_lastIdleDecodeBatch",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)!
            .GetValue(sut.Service).Should().BeNull();

        // Realistic timing: the CQ was decoded in the cycle that has just ended, the click comes early in the next one.
        await WaitUntilSecondsIntoCycleAsync(min: 1.0, max: 9.0);
        var now          = DateTimeOffset.UtcNow;
        var cqCycleStart = RoundDownTo15s(now) - TimeSpan.FromSeconds(15);

        await sut.Service.AnswerCqAsync(BatchTwoStation, AudioFreqHz, cqCycleStart, CancellationToken.None);

        // The reply target was armed from the click alone, on the opposite phase to the CQ's cycle...
        // ...and, because that phase is the cycle running now, the wake-up batch fires it straight away.
        await Poll.WaitForEqualAsync(() => sut.Service.State, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));
        sut.Service.Partner.Should().Be(BatchTwoStation);
        await sut.Ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());
        sut.Log.Entries.Should().Contain(e => e.Contains("pending CQ target") && e.Contains("answering at"),
            "the answerer's own pending-target line records the immediate reply; no lateness gate exists");
    }

    private static DateTimeOffset RoundDownTo15s(DateTimeOffset t)
        => new(t.Ticks - (t.Ticks % TimeSpan.FromSeconds(15).Ticks), TimeSpan.Zero);

    /// <summary>Waits until the wall clock is between <paramref name="min"/> and <paramref name="max"/> seconds into a 15 s cycle, so the cycle-relative arithmetic cannot straddle a boundary mid-test.</summary>
    private static async Task WaitUntilSecondsIntoCycleAsync(double min, double max)
    {
        while (true)
        {
            var now = DateTimeOffset.UtcNow;
            double into = (now - RoundDownTo15s(now)).TotalSeconds;
            if (into >= min && into <= max) return;
            await Task.Delay(100);
        }
    }
}
