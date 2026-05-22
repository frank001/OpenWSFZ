using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Test double for <see cref="IClock"/> with a directly settable <see cref="UtcNow"/>.
/// </summary>
internal sealed class FakeClock : IClock
{
    public DateTime UtcNow { get; set; }

    public FakeClock(DateTime utcNow) => UtcNow = utcNow;

    /// <summary>Advances the clock by the given duration.</summary>
    public void Advance(TimeSpan by) => UtcNow += by;
}
