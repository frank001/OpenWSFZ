namespace OpenWSFZ.Ft8;

/// <summary>
/// A <see cref="System.Diagnostics.Stopwatch"/>-shaped elapsed-time source over a <see cref="TimeProvider"/> (COH-FB-AUDIO N-1). Production
/// uses <see cref="TimeProvider.System"/>, whose timestamps are the same monotonic ticks a <c>Stopwatch</c> reads, so the arithmetic is unchanged;
/// a test passes a fake provider and spends the cycle budget by advancing it, never by sleeping. Internal: a test-only seam.
/// </summary>
internal sealed class BudgetClock
{
    private readonly TimeProvider _provider;
    private readonly long _start;
    private TimeSpan? _stopped;

    private BudgetClock(TimeProvider provider)
    {
        _provider = provider;
        _start = provider.GetTimestamp();
    }

    /// <summary>Starts a clock on <paramref name="provider"/> (<see cref="TimeProvider.System"/> when <c>null</c>).</summary>
    public static BudgetClock StartNew(TimeProvider? provider = null) => new(provider ?? TimeProvider.System);

    /// <summary>Time since the start, or the time at <see cref="Stop"/> once stopped (as a <c>Stopwatch</c>).</summary>
    public TimeSpan Elapsed => _stopped ?? _provider.GetElapsedTime(_start);

    /// <summary>Whole milliseconds of <see cref="Elapsed"/> (as <c>Stopwatch.ElapsedMilliseconds</c>).</summary>
    public long ElapsedMilliseconds => (long)Elapsed.TotalMilliseconds;

    /// <summary>Freezes <see cref="Elapsed"/>.</summary>
    public void Stop() => _stopped ??= _provider.GetElapsedTime(_start);
}
