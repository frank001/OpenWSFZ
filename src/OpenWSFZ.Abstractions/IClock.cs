namespace OpenWSFZ.Abstractions;

/// <summary>
/// Provides the current UTC time; injected so FT8 cycle alignment is unit-testable.
/// Implemented in Phase 1 (Walking skeleton) by a trivial <c>SystemClock</c> wrapper
/// over <see cref="System.DateTime.UtcNow"/>.
/// </summary>
public interface IClock
{
}
