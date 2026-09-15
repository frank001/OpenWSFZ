using FluentAssertions;
using NSubstitute;
using OpenWSFZ.TestSupport;
using Xunit;

namespace OpenWSFZ.TestSupport.Tests;

/// <summary>
/// Deterministic tests for <see cref="Poll"/> itself (design.md Decision 3, spec.md's
/// "The polling primitive itself is verified by deterministic tests" requirement). Every test here
/// either drives its condition to become true after a controlled, known number of poll iterations,
/// or uses an explicit short timeout against a condition engineered to never become true — neither
/// case relies on an unrelated fixed delay to determine pass/fail, which is the exact pattern this
/// whole change exists to eliminate everywhere else.
/// </summary>
public class PollTests
{
    // ── UntilAsync ──────────────────────────────────────────────────────────

    [Fact(DisplayName = "TestSupport: Poll.UntilAsync returns promptly once its condition becomes true")]
    public async Task UntilAsync_ReturnsPromptly_WhenConditionBecomesTrueAfterKnownTickCount()
    {
        var ticksUntilTrue = 3;
        var tickCount = 0;
        bool Condition()
        {
            tickCount++;
            return tickCount >= ticksUntilTrue;
        }

        var sw = System.Diagnostics.Stopwatch.StartNew();
        await Poll.UntilAsync(Condition, timeout: TimeSpan.FromSeconds(5), pollInterval: TimeSpan.FromMilliseconds(10));
        sw.Stop();

        tickCount.Should().BeGreaterThanOrEqualTo(ticksUntilTrue);
        // Generous upper bound (well under the 5s timeout) proves it returned as soon as the
        // condition became true rather than waiting out the full deadline.
        sw.Elapsed.Should().BeLessThan(TimeSpan.FromSeconds(1));
    }

    [Fact(DisplayName = "TestSupport: Poll.UntilAsync throws TimeoutException when its condition never becomes true")]
    public async Task UntilAsync_ThrowsTimeoutException_WhenConditionNeverBecomesTrue()
    {
        var timeout = TimeSpan.FromMilliseconds(100);

        var act = () => Poll.UntilAsync(() => false, timeout: timeout, pollInterval: TimeSpan.FromMilliseconds(10));

        await act.Should().ThrowAsync<TimeoutException>();
    }

    [Fact(DisplayName = "TestSupport: Poll.UntilAsync's timeout message reflects the caller-supplied timeoutMessage factory")]
    public async Task UntilAsync_TimeoutMessage_UsesCallerSuppliedFactory()
    {
        var act = () => Poll.UntilAsync(
            () => false,
            timeout: TimeSpan.FromMilliseconds(50),
            pollInterval: TimeSpan.FromMilliseconds(10),
            timeoutMessage: () => "custom diagnostic message");

        (await act.Should().ThrowAsync<TimeoutException>())
            .WithMessage("custom diagnostic message");
    }

    // ── IOException tolerance (dev-tasks/2026-09-14-cyclearchiveservicetests-manifestgapmarker-
    //    ioexception-repeat-flake.md) ─────────────────────────────────────────
    // Deterministic regression coverage for the transient-IOException-tolerance behavior itself,
    // added at QA's request during review: the flaky CycleArchiveServiceTests target test this fix
    // was written for has never reproduced on demand (0/several manual re-runs across both prior
    // occurrences), so a green run of that test is not a reliable regression guard for this specific
    // behavior. These tests drive the failure mode directly instead.

    [Fact(DisplayName = "TestSupport: Poll.UntilAsync tolerates a transient IOException from its condition and keeps polling")]
    public async Task UntilAsync_TreatsTransientIOException_AsNotYetTrue_AndKeepsPolling()
    {
        var throwsRemaining = 3;
        var tickCount = 0;
        bool Condition()
        {
            tickCount++;
            if (throwsRemaining > 0)
            {
                throwsRemaining--;
                throw new IOException("simulated transient sharing violation");
            }
            return true;
        }

        var act = () => Poll.UntilAsync(Condition, timeout: TimeSpan.FromSeconds(5), pollInterval: TimeSpan.FromMilliseconds(10));

        await act.Should().NotThrowAsync(
            "a transient IOException from the condition must be treated like a false result, not abort the poll");
        tickCount.Should().BeGreaterThanOrEqualTo(4, "three throwing ticks plus the succeeding tick");
    }

    [Fact(DisplayName = "TestSupport: Poll.UntilAsync still throws TimeoutException when the condition throws IOException on every tick, with the last IOException as InnerException")]
    public async Task UntilAsync_ThrowsTimeoutException_WhenConditionAlwaysThrowsIOException()
    {
        IOException? lastThrown = null;
        bool Condition()
        {
            lastThrown = new IOException($"simulated persistent sharing violation at {DateTime.UtcNow:O}");
            throw lastThrown;
        }

        var act = () => Poll.UntilAsync(Condition, timeout: TimeSpan.FromMilliseconds(100), pollInterval: TimeSpan.FromMilliseconds(10));

        var assertion = await act.Should().ThrowAsync<TimeoutException>(
            "a persistent IOException must still surface as a timeout, not hang or be swallowed forever");
        assertion.Which.InnerException.Should().BeSameAs(lastThrown,
            "the last transient IOException observed must be visible on the eventual TimeoutException, not silently discarded");
    }

    [Fact(DisplayName = "TestSupport: Poll.UntilAsync lets a non-IOException thrown by its condition propagate immediately, unchanged from prior behavior")]
    public async Task UntilAsync_LetsOtherExceptionTypes_PropagateImmediately_WithoutWaitingForTimeout()
    {
        var tickCount = 0;
        bool Condition()
        {
            tickCount++;
            throw new InvalidOperationException("not an IOException -- must not be tolerated");
        }

        var sw = System.Diagnostics.Stopwatch.StartNew();
        var act = () => Poll.UntilAsync(Condition, timeout: TimeSpan.FromSeconds(5), pollInterval: TimeSpan.FromMilliseconds(10));

        await act.Should().ThrowAsync<InvalidOperationException>(
            "only IOException is tolerated -- every other exception type must still escape the poll immediately");
        sw.Stop();

        tickCount.Should().Be(1, "the poll must abort on the very first tick, not retry a non-IOException");
        sw.Elapsed.Should().BeLessThan(TimeSpan.FromSeconds(1), "it must not wait out the 5s timeout for a non-tolerated exception");
    }

    // ── WaitForEqualAsync ───────────────────────────────────────────────────

    [Fact(DisplayName = "TestSupport: Poll.WaitForEqualAsync returns once the observed value equals the expected value")]
    public async Task WaitForEqualAsync_ReturnsPromptly_WhenValueReachesExpected()
    {
        var value = 0;
        _ = Task.Run(async () =>
        {
            await Task.Delay(30);
            value = 42;
        });

        await Poll.WaitForEqualAsync(() => value, 42, timeout: TimeSpan.FromSeconds(5));

        value.Should().Be(42);
    }

    [Fact(DisplayName = "TestSupport: Poll.WaitForEqualAsync throws TimeoutException when the value never reaches expected")]
    public async Task WaitForEqualAsync_ThrowsTimeoutException_WhenValueNeverReachesExpected()
    {
        var act = () => Poll.WaitForEqualAsync(() => 0, 42, timeout: TimeSpan.FromMilliseconds(100), what: "counter");

        await act.Should().ThrowAsync<TimeoutException>();
    }

    // ── WaitForCallAsync / WaitForCallCountAsync ───────────────────────────
    // These double as regression coverage for the Func<IEnumerable<ICall>> factory shape
    // (design.md Decision 1's correction): NSubstitute.ReceivedCalls() is a snapshot at call
    // time, not a live view, so the wrapper must re-invoke the factory on every poll tick to ever
    // observe a call made after polling starts. A plain captured IEnumerable<ICall> would freeze
    // at zero calls and these tests would time out.

    public interface IProbe
    {
        void DoThing();
    }

    [Fact(DisplayName = "TestSupport: Poll.WaitForCallAsync observes a call made after polling has already started")]
    public async Task WaitForCallAsync_ObservesCall_MadeAfterPollingStarted()
    {
        var probe = Substitute.For<IProbe>();
        _ = Task.Run(async () =>
        {
            await Task.Delay(30);
            probe.DoThing();
        });

        await Poll.WaitForCallAsync(() => probe.ReceivedCalls(), nameof(IProbe.DoThing), timeout: TimeSpan.FromSeconds(5));

        probe.ReceivedCalls().Should().ContainSingle(c => c.GetMethodInfo().Name == nameof(IProbe.DoThing));
    }

    [Fact(DisplayName = "TestSupport: Poll.WaitForCallAsync throws TimeoutException when no matching call is ever received")]
    public async Task WaitForCallAsync_ThrowsTimeoutException_WhenNoCallReceived()
    {
        var probe = Substitute.For<IProbe>();

        var act = () => Poll.WaitForCallAsync(() => probe.ReceivedCalls(), nameof(IProbe.DoThing), timeout: TimeSpan.FromMilliseconds(100));

        await act.Should().ThrowAsync<TimeoutException>();
    }

    [Fact(DisplayName = "TestSupport: Poll.WaitForCallCountAsync observes calls made incrementally after polling has already started")]
    public async Task WaitForCallCountAsync_ObservesCalls_MadeIncrementallyAfterPollingStarted()
    {
        var probe = Substitute.For<IProbe>();
        _ = Task.Run(async () =>
        {
            for (var i = 0; i < 3; i++)
            {
                await Task.Delay(20);
                probe.DoThing();
            }
        });

        await Poll.WaitForCallCountAsync(() => probe.ReceivedCalls(), nameof(IProbe.DoThing), expectedCount: 3, timeout: TimeSpan.FromSeconds(5));

        probe.ReceivedCalls().Count(c => c.GetMethodInfo().Name == nameof(IProbe.DoThing)).Should().BeGreaterThanOrEqualTo(3);
    }

    [Fact(DisplayName = "TestSupport: Poll.WaitForCallCountAsync throws TimeoutException when fewer than the expected count is ever received")]
    public async Task WaitForCallCountAsync_ThrowsTimeoutException_WhenCountNeverReached()
    {
        var probe = Substitute.For<IProbe>();
        probe.DoThing();

        var act = () => Poll.WaitForCallCountAsync(() => probe.ReceivedCalls(), nameof(IProbe.DoThing), expectedCount: 3, timeout: TimeSpan.FromMilliseconds(100));

        await act.Should().ThrowAsync<TimeoutException>();
    }
}
