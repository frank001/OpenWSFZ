namespace OpenWSFZ.Abstractions;

/// <summary>
/// Decides the listener addresses that Kestrel binds to.
/// Implemented in Phase 1 (Walking skeleton) by <c>OpenWSFZ.Host.LoopbackBindPolicy</c>;
/// replaced in v2 by <c>LanBindPolicy</c> / <c>AnyBindPolicy</c>.
/// </summary>
public interface IBindPolicy
{
}
