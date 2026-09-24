using FluentAssertions;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Unit tests for <see cref="DataFlowMonitor"/>'s <c>LastChunkAgeMs</c> addition
/// (FR-068, capture-stall-detection-unattended #188, design.md Decision 2). The pre-existing
/// <c>ConsumeAndReset</c>/<c>Reset</c> flowing-flag behaviour is unchanged and untested here.
/// </summary>
public sealed class DataFlowMonitorTests
{
    /// <summary>
    /// Controllable <see cref="TimeProvider"/> so <c>LastChunkAgeMs</c> can be advanced
    /// deterministically without a real sleep (design D2, U4; gate G10). Overrides
    /// <see cref="GetTimestamp"/> (not just <see cref="GetUtcNow"/>) because
    /// <see cref="TimeProvider.GetElapsedTime(long)"/> — what <see cref="DataFlowMonitor"/>
    /// uses internally — is driven by <c>GetTimestamp()</c>/<c>TimestampFrequency</c>, which
    /// default to the real <see cref="System.Diagnostics.Stopwatch"/> unless overridden; a fake
    /// that only overrode <c>GetUtcNow()</c> would silently fall back to real elapsed time.
    /// </summary>
    private sealed class FakeTimeProvider(DateTimeOffset initial) : TimeProvider
    {
        private DateTimeOffset _now = initial;

        public override DateTimeOffset GetUtcNow() => _now;
        public override long TimestampFrequency => TimeSpan.TicksPerSecond;
        public override long GetTimestamp() => _now.Ticks;

        public void Advance(TimeSpan by) => _now += by;
    }

    [Fact(DisplayName = "FR-068: LastChunkAgeMs is null before the first chunk of the process")]
    public void LastChunkAgeMs_NullBeforeFirstChunk()
    {
        var monitor = new DataFlowMonitor(new FakeTimeProvider(DateTimeOffset.UtcNow));

        monitor.LastChunkAgeMs.Should().BeNull(
            "no chunk has been received yet — the field must not read as a stale zero");
    }

    [Fact(DisplayName = "FR-068: LastChunkAgeMs reads ~0 ms immediately after a chunk, and advances monotonically with the injected clock")]
    public void LastChunkAgeMs_AdvancesMonotonically_WithInjectedClock()
    {
        var fakeTime = new FakeTimeProvider(new DateTimeOffset(2026, 9, 24, 12, 0, 0, TimeSpan.Zero));
        var monitor  = new DataFlowMonitor(fakeTime);

        monitor.OnChunkReceived();
        monitor.LastChunkAgeMs.Should().Be(0, "a chunk was just received — no time has elapsed yet");

        fakeTime.Advance(TimeSpan.FromSeconds(3));
        monitor.LastChunkAgeMs.Should().Be(3000,
            "the injected clock — not DateTime.UtcNow — must drive the computed age");

        fakeTime.Advance(TimeSpan.FromMilliseconds(500));
        monitor.LastChunkAgeMs.Should().Be(3500, "the age must keep advancing as the clock advances");
    }

    [Fact(DisplayName = "FR-068: a second OnChunkReceived resets the age to ~0")]
    public void LastChunkAgeMs_ResetsToZero_OnEachNewChunk()
    {
        var fakeTime = new FakeTimeProvider(DateTimeOffset.UtcNow);
        var monitor  = new DataFlowMonitor(fakeTime);

        monitor.OnChunkReceived();
        fakeTime.Advance(TimeSpan.FromSeconds(10));
        monitor.LastChunkAgeMs.Should().Be(10_000, "precondition — 10 s elapsed since the first chunk");

        monitor.OnChunkReceived();
        monitor.LastChunkAgeMs.Should().Be(0, "a fresh chunk arrived — the age must reflect only its own arrival");
    }

    [Fact(DisplayName = "FR-068: Reset() does NOT clear LastChunkAgeMs — a restart that delivers nothing keeps ageing (design.md D2)")]
    public void Reset_DoesNotClear_LastChunkAgeMs()
    {
        // This is the specific defect design.md Decision 2 calls out by name: clearing the
        // timestamp on Reset() would hide a #187 failure (restart loop against a dead device)
        // from an HTTP-only poller, reading "unknown" instead of "ageing".
        var fakeTime = new FakeTimeProvider(DateTimeOffset.UtcNow);
        var monitor  = new DataFlowMonitor(fakeTime);

        monitor.OnChunkReceived();
        fakeTime.Advance(TimeSpan.FromSeconds(15));

        monitor.Reset();

        monitor.LastChunkAgeMs.Should().Be(15_000,
            "Reset() clears only the flowing flag (ConsumeAndReset's window), never the last-chunk timestamp");

        // And it keeps ageing afterward, exactly as if nothing had been reset.
        fakeTime.Advance(TimeSpan.FromSeconds(15));
        monitor.LastChunkAgeMs.Should().Be(30_000,
            "a restart that delivers no further chunks must keep ageing from the last real chunk");
    }

    [Fact(DisplayName = "FR-068: Reset() still clears ConsumeAndReset's flowing flag exactly as before (unchanged behaviour)")]
    public void Reset_StillClearsFlowingFlag()
    {
        var monitor = new DataFlowMonitor();
        monitor.OnChunkReceived();

        monitor.Reset();

        monitor.ConsumeAndReset().Should().BeFalse(
            "Reset() must still clear the flowing flag — only the new timestamp field is exempt");
    }

    [Fact(DisplayName = "FR-068: LastChunkAgeMs never reads negative even if the clock is driven backwards")]
    public void LastChunkAgeMs_NeverNegative()
    {
        // Defensive clamp (design D2: "a wall-clock step ... must not produce a negative or
        // inflated age") — exercised here via a deliberately-misbehaving fake clock, standing in
        // for whatever real-world clock anomaly the clamp is meant to absorb.
        var fakeTime = new FakeTimeProvider(DateTimeOffset.UtcNow);
        var monitor  = new DataFlowMonitor(fakeTime);

        monitor.OnChunkReceived();
        fakeTime.Advance(TimeSpan.FromSeconds(-5));

        monitor.LastChunkAgeMs.Should().Be(0, "age must clamp to 0 rather than surface as negative");
    }
}
