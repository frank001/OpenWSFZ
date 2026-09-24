using FluentAssertions;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Unit tests for <see cref="CaptureRecoveryState"/> (capture-device-reresolution #187,
/// design.md Decisions 4–5; FR-071/FR-072).
/// </summary>
public sealed class CaptureRecoveryStateTests
{
    /// <summary>
    /// Controllable <see cref="TimeProvider"/> so the recovery Warning's "seconds without audio"
    /// can be asserted deterministically without a real sleep.
    /// </summary>
    private sealed class FakeTimeProvider(DateTimeOffset initial) : TimeProvider
    {
        private DateTimeOffset _now = initial;
        public override DateTimeOffset GetUtcNow() => _now;
        public void Advance(TimeSpan by) => _now += by;
    }

    // ── Initial state ────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-072: a freshly-constructed state is all-zero/null")]
    public void FreshState_IsAllZero()
    {
        var state = new CaptureRecoveryState();

        state.CaptureRestartCount.Should().Be(0);
        state.ConsecutiveCaptureFailures.Should().Be(0);
        state.LastCaptureError.Should().BeNull();
    }

    // ── RecordFailedAttempt ──────────────────────────────────────────────────

    [Fact(DisplayName = "FR-072: RecordFailedAttempt increments both CaptureRestartCount and ConsecutiveCaptureFailures")]
    public void RecordFailedAttempt_IncrementsBothCounters()
    {
        var state = new CaptureRecoveryState();

        state.RecordFailedAttempt("boom", deviceUnavailable: false);
        state.CaptureRestartCount.Should().Be(1);
        state.ConsecutiveCaptureFailures.Should().Be(1);

        state.RecordFailedAttempt("boom again", deviceUnavailable: false);
        state.CaptureRestartCount.Should().Be(2);
        state.ConsecutiveCaptureFailures.Should().Be(2);
    }

    [Fact(DisplayName = "FR-072: RecordFailedAttempt sets LastCaptureError to the given message")]
    public void RecordFailedAttempt_SetsLastCaptureError()
    {
        var state = new CaptureRecoveryState();

        state.RecordFailedAttempt("device not found", deviceUnavailable: true);

        state.LastCaptureError.Should().Be("device not found");
    }

    [Fact(DisplayName = "FR-072: LastCaptureError is truncated to 500 characters")]
    public void RecordFailedAttempt_TruncatesLongMessage()
    {
        var state = new CaptureRecoveryState();
        var longMessage = new string('x', 600);

        state.RecordFailedAttempt(longMessage, deviceUnavailable: false);

        state.LastCaptureError.Should().HaveLength(500);
        state.LastCaptureError.Should().Be(new string('x', 500));
    }

    [Fact(DisplayName = "FR-072: an attempt exactly 500 characters is not truncated")]
    public void RecordFailedAttempt_ExactlyMaxLength_NotTruncated()
    {
        var state = new CaptureRecoveryState();
        var message = new string('y', 500);

        state.RecordFailedAttempt(message, deviceUnavailable: false);

        state.LastCaptureError.Should().Be(message);
    }

    // ── RecordChunkReceived ──────────────────────────────────────────────────

    [Fact(DisplayName = "FR-071: RecordChunkReceived resets ConsecutiveCaptureFailures to 0")]
    public void RecordChunkReceived_ResetsConsecutiveFailures()
    {
        var state = new CaptureRecoveryState();
        state.RecordFailedAttempt("boom", deviceUnavailable: false);
        state.RecordFailedAttempt("boom", deviceUnavailable: false);
        state.ConsecutiveCaptureFailures.Should().Be(2, "precondition");

        state.RecordChunkReceived();

        state.ConsecutiveCaptureFailures.Should().Be(0);
    }

    [Fact(DisplayName = "FR-072: RecordChunkReceived does NOT reset CaptureRestartCount or clear LastCaptureError")]
    public void RecordChunkReceived_DoesNotResetRestartCountOrClearLastError()
    {
        var state = new CaptureRecoveryState();
        state.RecordFailedAttempt("the last failure", deviceUnavailable: false);

        state.RecordChunkReceived();

        state.CaptureRestartCount.Should().Be(1, "restart count is a process-lifetime counter, never reset");
        state.LastCaptureError.Should().Be("the last failure",
            "design D5: the last failure stays visible after recovery — it is never cleared");
    }

    [Fact(DisplayName = "FR-071: RecordChunkReceived returns null when there was no active failure streak (the common healthy case)")]
    public void RecordChunkReceived_ReturnsNull_WhenAlreadyHealthy()
    {
        var state = new CaptureRecoveryState();

        var recovery1 = state.RecordChunkReceived(); // never failed at all
        recovery1.Should().BeNull();

        state.RecordFailedAttempt("boom", deviceUnavailable: false);
        state.RecordChunkReceived(); // ends the streak
        var recovery2 = state.RecordChunkReceived(); // already healthy again
        recovery2.Should().BeNull("a second chunk while already healthy must not report a second recovery");
    }

    [Fact(DisplayName = "FR-071/design D6: RecordChunkReceived returns Attempts + Downtime when ending a genuine failure streak")]
    public void RecordChunkReceived_ReturnsRecoveryInfo_WhenEndingAStreak()
    {
        var fakeTime = new FakeTimeProvider(new DateTimeOffset(2026, 9, 24, 12, 0, 0, TimeSpan.Zero));
        var state = new CaptureRecoveryState(fakeTime);

        state.RecordFailedAttempt("attempt 1", deviceUnavailable: false);
        fakeTime.Advance(TimeSpan.FromSeconds(5));
        state.RecordFailedAttempt("attempt 2", deviceUnavailable: false);
        fakeTime.Advance(TimeSpan.FromSeconds(10));
        state.RecordFailedAttempt("attempt 3", deviceUnavailable: false);
        fakeTime.Advance(TimeSpan.FromSeconds(20));

        var recovery = state.RecordChunkReceived();

        recovery.Should().NotBeNull();
        recovery!.Attempts.Should().Be(3, "three consecutive failed attempts occurred during the streak");
        recovery.Downtime.Should().Be(TimeSpan.FromSeconds(35),
            "downtime is measured from the FIRST failure of the streak, not the most recent one");
    }

    [Fact(DisplayName = "FR-071: a second, independent failure streak reports its own Attempts/Downtime, not accumulated from the first")]
    public void RecordChunkReceived_SecondStreak_ReportsOwnAttemptsAndDowntime()
    {
        var fakeTime = new FakeTimeProvider(DateTimeOffset.UtcNow);
        var state = new CaptureRecoveryState(fakeTime);

        // First streak: 2 attempts, 10 s.
        state.RecordFailedAttempt("a1", deviceUnavailable: false);
        fakeTime.Advance(TimeSpan.FromSeconds(10));
        state.RecordFailedAttempt("a2", deviceUnavailable: false);
        state.RecordChunkReceived();

        // Second, independent streak: 1 attempt, 3 s.
        fakeTime.Advance(TimeSpan.FromSeconds(100)); // healthy interval in between — must not count
        state.RecordFailedAttempt("b1", deviceUnavailable: false);
        fakeTime.Advance(TimeSpan.FromSeconds(3));
        var recovery = state.RecordChunkReceived();

        recovery.Should().NotBeNull();
        recovery!.Attempts.Should().Be(1);
        recovery.Downtime.Should().Be(TimeSpan.FromSeconds(3));
    }

    // ── DeriveCaptureState (design D5's four-value table) ───────────────────

    [Fact(DisplayName = "FR-072: DeriveCaptureState returns Idle when device/decoding are not configured, regardless of counters")]
    public void DeriveCaptureState_ReturnsIdle_WhenNotConfigured()
    {
        var state = new CaptureRecoveryState();
        state.RecordFailedAttempt("boom", deviceUnavailable: true); // even mid-failure

        state.DeriveCaptureState(deviceConfiguredAndDecodingEnabled: false, isCapturing: true)
            .Should().Be("Idle", "Idle overrides every other input, including isCapturing=true");
    }

    [Fact(DisplayName = "FR-072: DeriveCaptureState returns Capturing when a session is running with zero consecutive failures")]
    public void DeriveCaptureState_ReturnsCapturing_WhenRunningAndHealthy()
    {
        var state = new CaptureRecoveryState();

        state.DeriveCaptureState(deviceConfiguredAndDecodingEnabled: true, isCapturing: true)
            .Should().Be("Capturing");
    }

    [Fact(DisplayName = "FR-072: DeriveCaptureState returns Recovering after a UseConfigured/Adopt/CannotResolve-class failure")]
    public void DeriveCaptureState_ReturnsRecovering_AfterNonDeviceUnavailableFailure()
    {
        var state = new CaptureRecoveryState();
        state.RecordFailedAttempt("a real capture exception", deviceUnavailable: false);

        state.DeriveCaptureState(deviceConfiguredAndDecodingEnabled: true, isCapturing: false)
            .Should().Be("Recovering");
    }

    [Fact(DisplayName = "FR-072: DeriveCaptureState returns DeviceUnavailable after a NotFound/Ambiguous resolution")]
    public void DeriveCaptureState_ReturnsDeviceUnavailable_AfterDeviceUnavailableFailure()
    {
        var state = new CaptureRecoveryState();
        state.RecordFailedAttempt("no matching device", deviceUnavailable: true);

        state.DeriveCaptureState(deviceConfiguredAndDecodingEnabled: true, isCapturing: false)
            .Should().Be("DeviceUnavailable");
    }

    [Fact(DisplayName = "FR-072: DeriveCaptureState returns Capturing again once a chunk arrives after a DeviceUnavailable streak")]
    public void DeriveCaptureState_ReturnsCapturing_AfterRecoveryFromDeviceUnavailable()
    {
        var state = new CaptureRecoveryState();
        state.RecordFailedAttempt("no matching device", deviceUnavailable: true);
        state.DeriveCaptureState(true, false).Should().Be("DeviceUnavailable", "precondition");

        state.RecordChunkReceived();

        state.DeriveCaptureState(deviceConfiguredAndDecodingEnabled: true, isCapturing: true)
            .Should().Be("Capturing", "RecordChunkReceived clears the DeviceUnavailable flag too, not just the failure count");
    }

    [Fact(DisplayName = "FR-072: a session running but with consecutive failures > 0 still reads Recovering, not Capturing")]
    public void DeriveCaptureState_IsCapturingTrue_ButFailuresNonZero_StillRecovering()
    {
        // E.g. mid-restart: the old session's IsCapturing flag hasn't flipped false yet, but a
        // failure was already recorded for the attempt now in flight.
        var state = new CaptureRecoveryState();
        state.RecordFailedAttempt("transient", deviceUnavailable: false);

        state.DeriveCaptureState(deviceConfiguredAndDecodingEnabled: true, isCapturing: true)
            .Should().Be("Recovering", "Capturing requires BOTH isCapturing AND zero consecutive failures");
    }
}
