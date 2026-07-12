using FluentAssertions;
using Microsoft.Extensions.Logging;
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

        var completed = await Task.WhenAny(released.Task, Task.Delay(2000));
        completed.Should().Be(released.Task, "the watchdog must force a release when never disarmed");

        // Give the log call (which happens just before invoking the callback) a moment
        // to land — same thread, so this is a formality rather than a real race.
        await Task.Delay(20);
        logger.Entries.Should().Contain(e =>
            e.Level == LogLevel.Error && e.Message.Contains("watchdog fired"),
            "the watchdog must log at Error including 'watchdog fired'");
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

        await Task.Delay(30);
        watchdog.Disarm();

        // Wait well past the original timeout to prove it never fires late.
        await Task.Delay(300);

        fired.Should().BeFalse("Disarm before the timeout must prevent the forced-release callback");
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
        var completed = await Task.WhenAny(callbackRan.Task, Task.Delay(2000));
        completed.Should().Be(callbackRan.Task,
            "the watchdog must fire on elapsed time alone, regardless of what it is guarding");
    }

    [Fact(DisplayName = "CatTx-Ptt: re-arming an already-armed watchdog replaces the pending timer")]
    public async Task Arm_WhileAlreadyArmed_ReplacesPendingTimer()
    {
        var logger    = new CapturingLogger();
        var watchdog  = new PttWatchdog(logger, "TestController");
        var fireCount = 0;

        watchdog.Arm(500, () => { Interlocked.Increment(ref fireCount); return Task.CompletedTask; });
        await Task.Delay(20);

        // Re-arm with a much shorter timeout — only the second timer should ever fire.
        var secondFired = new TaskCompletionSource();
        watchdog.Arm(30, () =>
        {
            Interlocked.Increment(ref fireCount);
            secondFired.TrySetResult();
            return Task.CompletedTask;
        });

        var completed = await Task.WhenAny(secondFired.Task, Task.Delay(2000));
        completed.Should().Be(secondFired.Task);

        await Task.Delay(600); // past the original (replaced) 500 ms timer too
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
