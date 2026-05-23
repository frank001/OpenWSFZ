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
        await watchdog.TickAsync(audioWasActive: false);
        await watchdog.TickAsync(audioWasActive: false);
        await watchdog.TickAsync(audioWasActive: false);

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
        await watchdog.TickAsync(audioWasActive: false);
        await watchdog.TickAsync(audioWasActive: false);
        await watchdog.TickAsync(audioWasActive: false);

        // Assert
        restarts.Should().Be(0, "watchdog must not restart a pipeline that is not running");
    }

    [Fact(DisplayName = "S6: Watchdog resets counter when audio is active")]
    public async Task Watchdog_ResetsCounter_WhenAudioActive()
    {
        // Arrange
        var restarts = 0;

        var watchdog = new AudioWatchdog(
            isCapturing: () => true,
            onRestart:   () => { restarts++; return Task.CompletedTask; },
            threshold:   3);

        // Act — two silent windows then one active window resets the counter;
        // two more silent windows do not reach the threshold again
        await watchdog.TickAsync(audioWasActive: false);  // silent window 1
        await watchdog.TickAsync(audioWasActive: false);  // silent window 2
        await watchdog.TickAsync(audioWasActive: true);   // active → counter resets to 0
        await watchdog.TickAsync(audioWasActive: false);  // silent window 1 again
        await watchdog.TickAsync(audioWasActive: false);  // silent window 2

        // Assert
        restarts.Should().Be(0, "counter must reset on any active window before threshold is reached");
    }
}
