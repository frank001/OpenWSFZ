namespace OpenWSFZ.Daemon;

/// <summary>
/// Pure backoff-delay computation for automatic capture restarts (capture-device-reresolution
/// #187, design.md Decision 4; FR-071). No I/O, no clock dependency — deliberately, so the exact
/// schedule is trivially table-tested without any real or injected time source (gate G10: nothing
/// here ever sleeps).
/// </summary>
public static class CaptureBackoffSchedule
{
    /// <summary>Floor of the schedule — the delay before automatic attempt 1.</summary>
    public static readonly TimeSpan Floor = TimeSpan.FromSeconds(5);

    /// <summary>Ceiling of the schedule — the backoff never exceeds this, and never stops.</summary>
    public static readonly TimeSpan Cap = TimeSpan.FromSeconds(60);

    /// <summary>
    /// The delay before consecutive automatic attempt <paramref name="consecutiveFailures"/>
    /// (k, 1-indexed): <c>min(5 × 2^(k−1), 60)</c> s — 5, 10, 20, 40, 60, 60, 60, ...
    /// A value of 0 or less is treated the same as 1 (the floor), so a caller can pass a
    /// freshly-incremented-or-not counter defensively without a special case at the boundary.
    /// </summary>
    public static TimeSpan DelayFor(int consecutiveFailures)
    {
        var k = Math.Max(consecutiveFailures, 1);
        // Math.Pow(2, k-1) grows unbounded for a device that stays absent for a very long time
        // (k keeps incrementing at the 60 s cadence indefinitely, design D4 — "no retry cap,
        // ever") — it is fine for this to overflow toward double.PositiveInfinity for a very
        // large k; Math.Min against Cap still returns exactly Cap in that case, no exception.
        var seconds = Math.Min(5.0 * Math.Pow(2, k - 1), Cap.TotalSeconds);
        return TimeSpan.FromSeconds(seconds);
    }
}
