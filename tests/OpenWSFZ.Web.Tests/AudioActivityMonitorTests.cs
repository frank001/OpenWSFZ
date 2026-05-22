using FluentAssertions;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Unit tests for <see cref="AudioActivityMonitor"/> (FR-020).
/// </summary>
public sealed class AudioActivityMonitorTests
{
    // ── Observation ──────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-020: AudioActivityMonitor starts inactive")]
    public void Monitor_StartsInactive()
    {
        var monitor = new AudioActivityMonitor();

        monitor.IsActive.Should().BeFalse(
            "a freshly-created monitor has seen no samples");
    }

    [Fact(DisplayName = "FR-020: ObserveSamples flags active when a sample exceeds the threshold")]
    public void ObserveSamples_SetsActive_WhenSampleExceedsThreshold()
    {
        var monitor = new AudioActivityMonitor();

        // 1×10⁻⁶ is the threshold; any value strictly greater triggers activity.
        monitor.ObserveSamples([0.0f, 0.0f, 2e-6f]);

        monitor.IsActive.Should().BeTrue(
            "a sample of 2×10⁻⁶ is above the 1×10⁻⁶ threshold");
    }

    [Fact(DisplayName = "FR-020: ObserveSamples leaves inactive when all samples are at or below threshold")]
    public void ObserveSamples_LeavesInactive_WhenAllSamplesBelowThreshold()
    {
        var monitor = new AudioActivityMonitor();

        // Exactly at the threshold must NOT count as active.
        monitor.ObserveSamples([0.0f, 1e-6f, -1e-6f, 0.5e-6f]);

        monitor.IsActive.Should().BeFalse(
            "samples at exactly 1×10⁻⁶ do not exceed the threshold");
    }

    [Fact(DisplayName = "FR-020: ObserveSamples detects negative samples whose absolute value exceeds threshold")]
    public void ObserveSamples_SetsActive_OnNegativeSampleAboveThreshold()
    {
        var monitor = new AudioActivityMonitor();

        monitor.ObserveSamples([-5e-6f]);

        monitor.IsActive.Should().BeTrue(
            "the absolute value of -5×10⁻⁶ exceeds 1×10⁻⁶");
    }

    [Fact(DisplayName = "FR-020: ObserveSamples on an empty chunk leaves state unchanged")]
    public void ObserveSamples_EmptyChunk_LeavesStateUnchanged()
    {
        var monitor = new AudioActivityMonitor();

        monitor.ObserveSamples([]);

        monitor.IsActive.Should().BeFalse(
            "an empty chunk carries no samples and cannot trigger activity");
    }

    // ── ConsumeAndReset ──────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-020: ConsumeAndReset returns current state and resets the window")]
    public void ConsumeAndReset_ReturnsTrueAndResetsToFalse()
    {
        var monitor = new AudioActivityMonitor();
        monitor.ObserveSamples([1.0f]);

        var first = monitor.ConsumeAndReset();

        first.Should().BeTrue("activity was flagged by ObserveSamples");
        monitor.IsActive.Should().BeFalse("the window resets after ConsumeAndReset");
    }

    [Fact(DisplayName = "FR-020: ConsumeAndReset returns false when no activity was observed")]
    public void ConsumeAndReset_ReturnsFalse_WhenNoActivity()
    {
        var monitor = new AudioActivityMonitor();

        var value = monitor.ConsumeAndReset();

        value.Should().BeFalse("no samples were observed");
        monitor.IsActive.Should().BeFalse();
    }

    [Fact(DisplayName = "FR-020: IsActive reads without resetting (used for status event)")]
    public void IsActive_DoesNotReset()
    {
        var monitor = new AudioActivityMonitor();
        monitor.ObserveSamples([1.0f]);

        _ = monitor.IsActive; // read without reset
        _ = monitor.IsActive; // second read

        monitor.IsActive.Should().BeTrue(
            "IsActive must not consume the flag — only ConsumeAndReset does");
    }

    // ── Reset ────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-020: Reset clears active flag (used on pipeline restart)")]
    public void Reset_ClearsActiveFlag()
    {
        var monitor = new AudioActivityMonitor();
        monitor.ObserveSamples([1.0f]);
        monitor.IsActive.Should().BeTrue("precondition");

        monitor.Reset();

        monitor.IsActive.Should().BeFalse("Reset must clear the active flag");
    }

    [Fact(DisplayName = "FR-020: monitor can be reused across windows after ConsumeAndReset")]
    public void Monitor_CanBeReusedAcrossWindows()
    {
        var monitor = new AudioActivityMonitor();

        // Window 1 — silent
        monitor.ObserveSamples([0.0f, 0.0f]);
        monitor.ConsumeAndReset().Should().BeFalse("window 1 is silent");

        // Window 2 — active
        monitor.ObserveSamples([1.0f]);
        monitor.ConsumeAndReset().Should().BeTrue("window 2 has activity");

        // Window 3 — silent again
        monitor.ObserveSamples([0.0f]);
        monitor.ConsumeAndReset().Should().BeFalse("window 3 is silent again");
    }
}
