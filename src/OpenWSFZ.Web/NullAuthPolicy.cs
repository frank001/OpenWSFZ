using System.Net;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Web;

/// <summary>
/// Pass-through auth policy: authorises every request unconditionally.
/// Used when <c>RemoteAccess.Enabled = false</c> (the default loopback-only mode).
/// <para>
/// SEC-001: The daemon refuses to start when <c>RemoteAccess.Enabled = true</c> and
/// <c>RemoteAccess.Passphrase</c> is null or empty, so this policy is never reached
/// in LAN mode without a passphrase.
/// </para>
/// </summary>
public sealed class NullAuthPolicy : IAuthPolicy
{
    /// <inheritdoc />
    /// <remarks>Always returns <c>true</c> regardless of origin or credentials.</remarks>
    public bool IsAuthorized(IPAddress? remoteIp, string? apiKeyHeader, string? keyQueryParam)
        => true;
}
