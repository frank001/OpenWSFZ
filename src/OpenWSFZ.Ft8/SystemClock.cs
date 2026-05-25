using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Ft8;

/// <summary>
/// Production <see cref="IClock"/> implementation backed by <see cref="DateTime.UtcNow"/>.
/// </summary>
public sealed class SystemClock : IClock
{
    /// <inheritdoc/>
    public DateTime UtcNow => DateTime.UtcNow;
}
