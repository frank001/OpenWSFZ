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
