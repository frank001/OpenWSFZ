using System.Net;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Web;

/// <summary>
/// Pass-through auth policy: authorises every request unconditionally.
/// Used when <c>RemoteAccess.Enabled = false</c> (the default) or when
/// <c>RemoteAccess.Passphrase</c> is null/empty (LAN access without a passphrase).
/// </summary>
public sealed class NullAuthPolicy : IAuthPolicy
{
    /// <inheritdoc />
    /// <remarks>Always returns <c>true</c> regardless of origin or credentials.</remarks>
    public bool IsAuthorized(IPAddress? remoteIp, string? apiKeyHeader, string? keyQueryParam)
        => true;
}
