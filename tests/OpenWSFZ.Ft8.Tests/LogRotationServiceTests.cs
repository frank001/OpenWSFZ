using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon.Logging;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>Unit tests for <see cref="LogRotationService.CalculateNextBoundary"/>.</summary>
public sealed class LogRotationServiceTests
{
    private static LoggingConfig Cfg(string schedule, string time = "00:00", string day = "Monday") =>
        new() { FileEnabled = true, RotationSchedule = schedule, RotationTime = time, RotationDayOfWeek = day };

    [Fact(DisplayName = "FR-023: CalculateNextBoundary hourly returns next full UTC hour")]
    public void Hourly_ReturnsNextFullHour()
    {
        var now    = new DateTime(2026, 5, 25, 2, 47, 0, DateTimeKind.Utc);
        var result = LogRotationService.CalculateNextBoundary(now, Cfg("hourly"));

        result.Should().Be(new DateTime(2026, 5, 25, 3, 0, 0, DateTimeKind.Utc));
    }

    [Fact(DisplayName = "FR-023: CalculateNextBoundary daily before rotation time returns same day")]
    public void Daily_BeforeRotationTime_ReturnsSameDay()
    {
        var now    = new DateTime(2026, 5, 25, 2, 59, 0, DateTimeKind.Utc);
        var result = LogRotationService.CalculateNextBoundary(now, Cfg("daily", "03:00"));

        result.Should().Be(new DateTime(2026, 5, 25, 3, 0, 0, DateTimeKind.Utc));
    }

    [Fact(DisplayName = "FR-023: CalculateNextBoundary daily after rotation time returns next day")]
    public void Daily_AfterRotationTime_ReturnsNextDay()
    {
        var now    = new DateTime(2026, 5, 25, 3, 1, 0, DateTimeKind.Utc);
        var result = LogRotationService.CalculateNextBoundary(now, Cfg("daily", "03:00"));

        result.Should().Be(new DateTime(2026, 5, 26, 3, 0, 0, DateTimeKind.Utc));
    }

    [Fact(DisplayName = "FR-023: CalculateNextBoundary weekly returns correct next occurrence")]
    public void Weekly_ReturnsNextOccurrenceOfConfiguredDay()
    {
        // It is Monday 00:01 — next Monday 00:00 is 7 days away.
        var now    = new DateTime(2026, 5, 25, 0, 1, 0, DateTimeKind.Utc); // Monday
        var result = LogRotationService.CalculateNextBoundary(now, Cfg("weekly", "00:00", "Monday"));

        result.Should().Be(new DateTime(2026, 6, 1, 0, 0, 0, DateTimeKind.Utc));
    }

    [Fact(DisplayName = "FR-023: CalculateNextBoundary always returns a strictly future time")]
    public void AlwaysReturnsFutureTime()
    {
        // Clock is exactly at a daily rotation boundary.
        var exactBoundary = new DateTime(2026, 5, 25, 3, 0, 0, DateTimeKind.Utc);
        var result        = LogRotationService.CalculateNextBoundary(exactBoundary, Cfg("daily", "03:00"));

        result.Should().BeAfter(exactBoundary,
            "the next rotation must always be in the future, never at or before now");
    }
}
