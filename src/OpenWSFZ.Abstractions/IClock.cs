namespace OpenWSFZ.Abstractions;

/// <summary>
/// Provides the current UTC time. Injected so FT8 cycle alignment is unit-testable
/// without depending on the real wall clock.
/// </summary>
public interface IClock
{
    /// <summary>Gets the current UTC date and time.</summary>
    DateTime UtcNow { get; }
}
