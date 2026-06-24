using System.Net;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// Invoked on every incoming HTTP request and WebSocket upgrade to determine authorization.
/// <para>
/// Implemented in Phase 1 (Walking skeleton) by <c>NullAuthPolicy</c> (always returns
/// <c>true</c>); replaced in the LAN remote-access phase by <c>PassphraseAuthPolicy</c>.
/// </para>
/// </summary>
public interface IAuthPolicy
{
    /// <summary>
    /// Returns <c>true</c> if the request should be forwarded to the application pipeline;
    /// <c>false</c> if it should be rejected with HTTP 401.
    /// </summary>
    /// <param name="remoteIp">
    /// The remote IP address from <c>HttpContext.Connection.RemoteIpAddress</c>.
    /// May be <c>null</c> for in-process test requests.
    /// </param>
    /// <param name="apiKeyHeader">
    /// Value of the <c>X-Api-Key</c> request header, or <c>null</c> if absent.
    /// Used by REST clients.
    /// </param>
    /// <param name="keyQueryParam">
    /// Value of the <c>?key=</c> query parameter, or <c>null</c> if absent.
    /// Used by WebSocket upgrade requests (browsers cannot set custom headers on WS connects).
    /// </param>
    bool IsAuthorized(IPAddress? remoteIp, string? apiKeyHeader, string? keyQueryParam);
}
