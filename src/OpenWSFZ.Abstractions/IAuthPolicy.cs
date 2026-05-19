namespace OpenWSFZ.Abstractions;

/// <summary>
/// Invoked on every incoming HTTP request and WebSocket upgrade to determine authorization.
/// Implemented in Phase 1 (Walking skeleton) by <c>OpenWSFZ.Host.NullAuthPolicy</c>;
/// replaced in v2 by token / OIDC policies.
/// </summary>
public interface IAuthPolicy
{
}
