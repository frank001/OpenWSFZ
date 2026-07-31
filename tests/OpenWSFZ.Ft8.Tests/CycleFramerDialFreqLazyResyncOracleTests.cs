using System.Threading.Channels;
using FluentAssertions;
using OpenWSFZ.Ft8;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Ft8Decoder: CycleFramer dial-frequency lazy-resync consistency oracle.
///
/// <para>
/// Regression oracle for
/// <c>dev-tasks/2026-07-31-fix-cycleframer-dial-freq-lazy-resync-consistency.md</c> — a
/// second-order consequence of the clock-drift fix in
/// <c>dev-tasks/2026-07-31-fix-cycleframer-clock-drift-boundary-resync.md</c>. That fix made
/// <c>cycleStart</c> lazy: it is re-derived from <see cref="OpenWSFZ.Abstractions.IClock.UtcNow"/>
/// at the instant the next window actually begins accumulating its first sample, not eagerly at
/// the previous window's close. <c>windowDialFreq</c> was left behind, still captured eagerly in
/// the emission block. Whenever a real gap opens between window-close and the next window's true
/// open — the exact scenario the drift fix exists to handle — a band change during that gap is
/// attributed to the wrong window: <c>cycleStart</c> reflects "after", <c>DialFrequencyMHz</c>
/// reflects "before".
/// </para>
///
/// <para>
/// This test is expected to FAIL against the current branch (eager snapshot) before the fix and
/// PASS after it moves the snapshot into the same <c>needsResync</c> block as <c>cycleStart</c>.
/// Uses a mutable-flag provider, not a call-count provider like the FR-032 tests in
/// <c>CycleFramerTests.cs</c>: call count can't distinguish "eager at close" from "lazy at open"
/// because those tests have no real gap for the two to diverge over.
/// </para>
/// </summary>
public sealed class CycleFramerDialFreqLazyResyncOracleTests
{
    private const int SampleRate      = 12_000;
    private const int SamplesPerCycle = SampleRate * 15; // 180 000

    [Fact(DisplayName =
        "Oracle (dial-freq lazy resync): a dial-frequency change during the close-open gap must " +
        "be attributed to the next window, not the one just closed — must be red against the " +
        "eager snapshot on the current branch")]
    public async Task RunAsync_DialFreqChangesDuringCloseOpenGap_Window1CarriesPostChangeValue()
    {
        var startUtc = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc); // boundary-aligned
        var clock    = new FakeClock(startUtc);

        // Mutable flag the test flips directly, not a call counter — see class summary.
        double dialFreq = 14.074;
        double? Provider() => dialFreq;

        var source = Channel.CreateUnbounded<float[]>();
        var output = Channel.CreateUnbounded<(float[], DateTime, double?)>();
        var framer = new CycleFramer(source.Reader, clock, dialFreqProvider: Provider);

        using var cts  = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        var framerTask = Task.Run(() => framer.RunAsync(output.Writer, cts.Token));

        // Feed window 0's samples and drain its emission — this is the synchronization point:
        // the framer cannot have done anything for window 1 that depends on an await past this
        // point yet.
        await source.Writer.WriteAsync(new float[SamplesPerCycle], cts.Token);
        var (_, _, freq0) = await output.Reader.ReadAsync(cts.Token);

        // Simulated "operator changed bands during the gap" — strictly after window 0's
        // emission has been observed and strictly before window 1's samples are fed.
        dialFreq = 7.074;

        await source.Writer.WriteAsync(new float[SamplesPerCycle], cts.Token);
        var (_, _, freq1) = await output.Reader.ReadAsync(cts.Token);

        source.Writer.Complete();
        cts.Cancel();
        try { await framerTask; } catch (OperationCanceledException) { /* expected teardown */ }

        freq0.Should().Be(14.074, "window 0's snapshot predates the flip and must be unaffected");
        freq1.Should().Be(7.074,
            "window 1 must carry the post-flip dial frequency — the flip happens strictly " +
            "between window 0's close and window 1's open, and per CycleFramer's own class-" +
            "summary contract the snapshot must reflect the instant the window actually begins " +
            "accumulating, not the instant the previous one closed. On the current branch the " +
            "snapshot is still taken eagerly in the emission block, synchronously with no " +
            "intervening await, so it necessarily fires before this test gets to flip the flag " +
            "and window 1 wrongly carries the pre-flip value. See dev-tasks/2026-07-31-fix-" +
            "cycleframer-dial-freq-lazy-resync-consistency.md.");
    }
}
