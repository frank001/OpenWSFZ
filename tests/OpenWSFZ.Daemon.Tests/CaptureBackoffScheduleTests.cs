using FluentAssertions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// FR-071 (capture-device-reresolution #187, design.md Decision 4): the exact backoff schedule.
/// <see cref="CaptureBackoffSchedule.DelayFor"/> is pure (no clock, no I/O), so the schedule is
/// asserted directly with no waiting at all — gate G10 has nothing to flag here.
/// </summary>
public sealed class CaptureBackoffScheduleTests
{
    [Fact(DisplayName = "FR-071: backoff schedule is exactly 5, 10, 20, 40, 60, 60, 60 s for attempts 1-7")]
    public void DelayFor_MatchesExactSchedule_ForFirstSevenAttempts()
    {
        var expectedSeconds = new[] { 5, 10, 20, 40, 60, 60, 60 };

        for (var k = 1; k <= expectedSeconds.Length; k++)
        {
            CaptureBackoffSchedule.DelayFor(k).Should().Be(
                TimeSpan.FromSeconds(expectedSeconds[k - 1]),
                $"attempt {k} must be delayed by exactly {expectedSeconds[k - 1]} s");
        }
    }

    [Fact(DisplayName = "FR-071: the schedule never exceeds the 60 s cap, however large k grows (no retry cap, ever)")]
    public void DelayFor_NeverExceedsCap_ForVeryLargeK()
    {
        // A device absent for hours keeps retrying at the 60 s cadence indefinitely — k keeps
        // growing without bound, and must never produce anything above the cap (design D4: "no
        // retry cap, ever").
        foreach (var k in new[] { 8, 20, 100, 10_000, int.MaxValue })
        {
            CaptureBackoffSchedule.DelayFor(k).Should().Be(CaptureBackoffSchedule.Cap,
                $"k={k} must still clamp to the 60 s cap, not overflow or throw");
        }
    }

    [Fact(DisplayName = "FR-071: DelayFor(0) and DelayFor(negative) both treat k as 1 (the floor) defensively")]
    public void DelayFor_ZeroOrNegative_TreatedAsFloor()
    {
        CaptureBackoffSchedule.DelayFor(0).Should().Be(CaptureBackoffSchedule.Floor);
        CaptureBackoffSchedule.DelayFor(-5).Should().Be(CaptureBackoffSchedule.Floor);
    }

    [Fact(DisplayName = "FR-071: Floor and Cap constants match the schedule's own endpoints")]
    public void FloorAndCap_MatchScheduleEndpoints()
    {
        CaptureBackoffSchedule.Floor.Should().Be(TimeSpan.FromSeconds(5));
        CaptureBackoffSchedule.Cap.Should().Be(TimeSpan.FromSeconds(60));
    }
}
