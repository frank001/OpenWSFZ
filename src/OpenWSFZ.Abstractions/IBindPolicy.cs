using System.Net;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// Decides the listener address that Kestrel binds to.
/// Implemented in Phase 1 (Walking skeleton) by <c>LoopbackBindPolicy</c>;
/// replaced in v2 by <c>LanBindPolicy</c> / <c>AnyBindPolicy</c>.
/// </summary>
public interface IBindPolicy
{
    /// <summary>
    /// Returns the <see cref="IPEndPoint"/> to actually bind to, given a requested
    /// address and port.  Implementations may override <paramref name="desired"/>
    /// (e.g. force loopback) and MUST log a warning when they do so.
    /// </summary>
    IPEndPoint Resolve(IPAddress desired, int port);
}
