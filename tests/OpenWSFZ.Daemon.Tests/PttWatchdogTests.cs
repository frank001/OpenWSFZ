using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.TestSupport;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="PttWatchdog"/> (FR-056, design.md Decision 4, task 12.8).
/// Deliberately has no dependency on WASAPI or a real PTT-assertion mechanism — a plain
/// timer + callback, so these run without <c>WASAPI_SUPPORTED</c> or Windows.
/// </summary>
[Trait("Category", "Unit")]
public sealed class PttWatchdogTests
{
    [Fact(DisplayName = "CatTx-Ptt: watchdog forces release and logs Error when KeyUpAsync never arrives")]
    public async Task Fires_WhenNeverDisarmed_InvokesCallbackAndLogsError()
    {
        var logger   = new CapturingLogger();
        var watchdog = new PttWatchdog(logger, "TestController");
        var released = new TaskCompletionSource();

        watchdog.Arm(50, () =>
        {
            released.TrySetResult();
            return Task.CompletedTask;
        });

        await Poll.WaitForEqualAsync(() => released.Task.IsCompleted, true,
            timeout: TimeSpan.FromSeconds(2), what: "the forced-release callback");

        // Poll for the log entry to land instead of assuming a fixed delay is enough —
        // logging happens just before the callback runs, on the same callback invocation,
        // so this settles almost immediately in practice, but polling removes any assumption
        // about exactly how immediately.
        await Poll.UntilAsync(
            () => logger.Entries.Any(e => e.Level == LogLevel.Error && e.Message.Contains("watchdog fired")),
            timeout: TimeSpan.FromSeconds(1));
        logger.Entries.Should().Contain(e => e.Message.Contains("TestController"),
            "the log line must name the owning controller");
    }

    [Fact(DisplayName = "CatTx-Ptt: watchdog does not fire when Disarm is called before the timeout elapses")]
    public async Task Disarm_BeforeTimeout_CallbackNeverInvoked()
    {
        var logger   = new CapturingLogger();
        var watchdog = new PttWatchdog(logger, "TestController");
        var fired    = false;

        watchdog.Arm(200, () =>
        {
            fired = true;
            return Task.CompletedTask;
        });

        // Disarm back-to-back with Arm — deliberately no delay in between. The original test
        // inserted a fixed 30-millisecond delay here to simulate "PTT held briefly", racing it
        // against the watchdog's own 200ms timer. Under CI load that delay could itself overrun
        // past 200ms (thread-pool contention/GC pauses), letting the watchdog fire before
        // Disarm() ever ran — this exact mechanism is the confirmed flake this task fixes
        // (dev-tasks/2026-07-20-flaky-waitreport-retry-delay-sync.md's sibling case). Removing
        // the artificial gap removes the race: Arm() and Disarm() now execute as two adjacent
        // statements with nothing in between for the scheduler to exploit.
        watchdog.Disarm();

        // Prove it never fires, even well past the original 200ms timeout. Polling for "fired
        // becomes true" and asserting the poll times out is the shared library's idiom for a
        // "this must never happen" assertion (see OpenWSFZ.TestSupport.Tests.PollTests, which
        // proves Poll.UntilAsync's own timeout behavior the same way).
        var act = () => Poll.WaitForEqualAsync(() => fired, true, timeout: TimeSpan.FromMilliseconds(300));
        await act.Should().ThrowAsync<TimeoutException>();

        logger.Entries.Should().NotContain(e => e.Level == LogLevel.Error);
    }

    [Fact(DisplayName = "CatTx-Ptt: watchdog fires even when the forced-release callback itself represents a hung operation")]
    public async Task Fires_EvenWhenGuardedOperationHangs()
    {
        // The watchdog has no knowledge of what KeyDownAsync/playback is doing — it fires
        // purely on elapsed time since Arm(), independent of whether the thing it is
        // guarding (e.g. a hung WASAPI playback) ever completes.
        var logger      = new CapturingLogger();
        var watchdog    = new PttWatchdog(logger, "TestController");
        var callbackRan = new TaskCompletionSource();

        watchdog.Arm(50, () =>
        {
            callbackRan.TrySetResult();
            return Task.CompletedTask;
        });

        // Never call Disarm() — simulates KeyDownAsync/playback hanging indefinitely.
        await Poll.WaitForEqualAsync(() => callbackRan.Task.IsCompleted, true,
            timeout: TimeSpan.FromSeconds(2),
            what: "the watchdog firing on elapsed time alone, regardless of what it is guarding");
    }

    [Fact(DisplayName = "CatTx-Ptt: re-arming an already-armed watchdog replaces the pending timer")]
    public async Task Arm_WhileAlreadyArmed_ReplacesPendingTimer()
    {
        var logger    = new CapturingLogger();
        var watchdog  = new PttWatchdog(logger, "TestController");
        var fireCount = 0;

        watchdog.Arm(500, () => { Interlocked.Increment(ref fireCount); return Task.CompletedTask; });

        // Re-arm back-to-back with the first Arm — no delay in between (same rationale as
        // Disarm_BeforeTimeout_CallbackNeverInvoked above: a fixed delay here would race
        // against the first timer's own 500ms window under CI load, for no benefit — the test
        // only cares that re-arming replaces the pending timer, not that any particular amount
        // of it elapsed first).
        var secondFired = new TaskCompletionSource();
        watchdog.Arm(30, () =>
        {
            Interlocked.Increment(ref fireCount);
            secondFired.TrySetResult();
            return Task.CompletedTask;
        });

        await Poll.WaitForEqualAsync(() => secondFired.Task.IsCompleted, true, timeout: TimeSpan.FromSeconds(2));

        // Prove the original (replaced) 500ms timer never also fires — same
        // wait-for-it-to-happen-and-assert-timeout idiom as the Disarm test above.
        var act = () => Poll.WaitForEqualAsync(() => fireCount, 2, timeout: TimeSpan.FromMilliseconds(600));
        await act.Should().ThrowAsync<TimeoutException>();
        fireCount.Should().Be(1, "only the most recent Arm() call should ever fire");
    }

    // ── Test logger ───────────────────────────────────────────────────────────

    private sealed class CapturingLogger : ILogger
    {
        public List<(LogLevel Level, string Message)> Entries { get; } = new();

        public IDisposable BeginScope<TState>(TState state) where TState : notnull => NullScope.Instance;
        public bool IsEnabled(LogLevel logLevel) => true;

        public void Log<TState>(
            LogLevel logLevel, EventId eventId, TState state, Exception? exception,
            Func<TState, Exception?, string> formatter)
        {
            lock (Entries) Entries.Add((logLevel, formatter(state, exception)));
        }

        private sealed class NullScope : IDisposable
        {
            public static readonly NullScope Instance = new();
            public void Dispose() { }
        }
    }
}
