using FluentAssertions;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Unit tests for <see cref="AudioWatchdog"/> (S6).
/// </summary>
public sealed class AudioWatchdogTests
{
    [Fact(DisplayName = "S6: Watchdog triggers restart after 3 consecutive silent windows while capturing")]
    public async Task Watchdog_TriggersRestart_AfterThresholdSilentWindows()
    {
        // Arrange
        var restarts = 0;

        var watchdog = new AudioWatchdog(
            isCapturing: () => true,
            onRestart:   () => { restarts++; return Task.CompletedTask; },
            threshold:   3);

        // Act — await each tick so onRestart completes before assertion
        await watchdog.TickAsync(dataWasFlowing: false);
        await watchdog.TickAsync(dataWasFlowing: false);
        await watchdog.TickAsync(dataWasFlowing: false);

        // Assert — deterministic: onRestart is awaited inside TickAsync
        restarts.Should().Be(1, "watchdog must trigger exactly once after threshold is reached");
    }

    [Fact(DisplayName = "S6: Watchdog does not trigger when not capturing")]
    public async Task Watchdog_DoesNotTrigger_WhenNotCapturing()
    {
        // Arrange
        var restarts = 0;

        var watchdog = new AudioWatchdog(
            isCapturing: () => false,   // pipeline not running
            onRestart:   () => { restarts++; return Task.CompletedTask; },
            threshold:   3);

        // Act
        await watchdog.TickAsync(dataWasFlowing: false);
        await watchdog.TickAsync(dataWasFlowing: false);
        await watchdog.TickAsync(dataWasFlowing: false);

        // Assert
        restarts.Should().Be(0, "watchdog must not restart a pipeline that is not running");
    }

    [Fact(DisplayName = "B18: Watchdog does not restart when data flows but amplitude is below threshold")]
    public async Task Watchdog_DoesNotTrigger_WhenDataFlowingButAmplitudeSilent()
    {
        // Simulates: WASAPI device delivering buffers but the radio frequency is quiet.
        // dataWasFlowing=true must prevent any restart, even across multiple ticks.
        var restarts = 0;

        var watchdog = new AudioWatchdog(
            isCapturing: () => true,
            onRestart:   () => { restarts++; return Task.CompletedTask; },
            threshold:   3);

        // Flow present (chunks arriving) but amplitude would have been below 1e-6.
        // Old amplitude-based logic would have fired; new flow-based logic must not.
        await watchdog.TickAsync(dataWasFlowing: true);
        await watchdog.TickAsync(dataWasFlowing: true);
        await watchdog.TickAsync(dataWasFlowing: true);

        restarts.Should().Be(0,
            "a working pipeline delivering data must never trigger a restart, " +
            "even when the audio amplitude is below the FT8 signal threshold");
    }

    // ── T3: Singleton shared across multiple heartbeat callers ────────────────

    [Fact(DisplayName = "T3: Singleton AudioWatchdog accumulates ticks from multiple callers and fires only once at threshold")]
    public async Task Watchdog_SharedAcrossCallers_FiresOnceAtThreshold()
    {
        // Validates the B3 fix: a single watchdog instance must accumulate ticks from
        // all connected clients' heartbeat loops and fire exactly once at the threshold.
        // With the old per-connection design, two clients each reaching the threshold
        // independently would trigger two concurrent restarts.
        var restartCount = 0;

        var watchdog = new AudioWatchdog(
            isCapturing: () => true,
            onRestart:   () => { restartCount++; return Task.CompletedTask; },
            threshold:   3);

        // Simulate two heartbeat loops sharing one singleton — interleaved, sequential.
        await watchdog.TickAsync(dataWasFlowing: false); // client A, window 1
        await watchdog.TickAsync(dataWasFlowing: false); // client B, window 1
        await watchdog.TickAsync(dataWasFlowing: false); // client A, window 2 → threshold

        restartCount.Should().Be(1,
            "a singleton watchdog accumulates ticks across all callers and fires exactly once, " +
            "not once per connected client");
    }

    [Fact(DisplayName = "S6: Watchdog resets counter when data flows in an intervening window")]
    public async Task Watchdog_ResetsCounter_WhenDataFlowing()
    {
        // Arrange
        var restarts = 0;

        var watchdog = new AudioWatchdog(
            isCapturing: () => true,
            onRestart:   () => { restarts++; return Task.CompletedTask; },
            threshold:   3);

        // Act — two no-flow windows, then one window with data arriving resets
        // the counter; two more no-flow windows do not reach the threshold again
        await watchdog.TickAsync(dataWasFlowing: false);  // no-flow window 1
        await watchdog.TickAsync(dataWasFlowing: false);  // no-flow window 2
        await watchdog.TickAsync(dataWasFlowing: true);   // data flowing → counter resets to 0
        await watchdog.TickAsync(dataWasFlowing: false);  // no-flow window 1 again
        await watchdog.TickAsync(dataWasFlowing: false);  // no-flow window 2

        // Assert
        restarts.Should().Be(0, "counter must reset on any data-flowing window before threshold is reached");
    }
}
