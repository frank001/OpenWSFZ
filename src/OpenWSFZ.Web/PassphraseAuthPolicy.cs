using System.Net;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Web;

/// <summary>
/// Passphrase-based auth policy for LAN remote access.
/// <para>
/// A request is authorised if <em>any</em> of the following is true:
/// <list type="bullet">
///   <item>The remote IP is loopback (<c>127.0.0.1</c> or <c>::1</c>) — always trusted (D1).</item>
///   <item>The configured passphrase is <c>null</c> or empty — no auth required (open LAN).</item>
///   <item>The <c>X-Api-Key</c> header matches the passphrase (REST clients).</item>
///   <item>The <c>?key=</c> query parameter matches the passphrase (WebSocket clients).</item>
/// </list>
/// </para>
/// </summary>
public sealed class PassphraseAuthPolicy : IAuthPolicy
{
    private readonly string? _passphrase;

    /// <param name="passphrase">
    /// Configured shared passphrase. <c>null</c> or empty means no authentication is required.
    /// </param>
    public PassphraseAuthPolicy(string? passphrase)
        => _passphrase = passphrase;

    /// <inheritdoc />
    public bool IsAuthorized(IPAddress? remoteIp, string? apiKeyHeader, string? keyQueryParam)
    {
        // Loopback origin: always trusted (D1 — bootstrapping safety).
        if (remoteIp is not null && IPAddress.IsLoopback(remoteIp))
            return true;

        // No passphrase configured: open LAN access.
        if (string.IsNullOrEmpty(_passphrase))
            return true;

        // REST path: X-Api-Key header must match.
        if (apiKeyHeader == _passphrase)
            return true;

        // WebSocket path: ?key= query parameter must match.
        if (keyQueryParam == _passphrase)
            return true;

        return false;
    }
}
