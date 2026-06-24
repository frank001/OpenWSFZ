using System.Net;
using System.Security.Cryptography;
using System.Text;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Web;

/// <summary>
/// Passphrase-based auth policy for LAN remote access.
/// <para>
/// A request is authorised if <em>any</em> of the following is true:
/// <list type="bullet">
///   <item>The remote IP is loopback (<c>127.0.0.1</c> or <c>::1</c>) — always trusted (D1).</item>
///   <item>The <c>X-Api-Key</c> header matches the passphrase (REST clients).</item>
///   <item>The <c>?key=</c> query parameter matches the passphrase (backward-compat / non-browser clients).</item>
/// </list>
/// </para>
/// <para>
/// SEC-001 ensures this policy is only registered when a non-empty passphrase is configured.
/// SEC-002A: Comparisons use <see cref="CryptographicOperations.FixedTimeEquals"/> (UTF-8 bytes)
/// to eliminate timing side-channels.
/// </para>
/// </summary>
public sealed class PassphraseAuthPolicy : IAuthPolicy
{
    private readonly string _passphrase;

    /// <param name="passphrase">
    /// Configured shared passphrase. Must be non-null and non-empty (enforced by SEC-001 startup guard).
    /// </param>
    public PassphraseAuthPolicy(string passphrase)
        => _passphrase = passphrase;

    /// <inheritdoc />
    public bool IsAuthorized(IPAddress? remoteIp, string? apiKeyHeader, string? keyQueryParam)
    {
        // Loopback origin: always trusted (D1 — bootstrapping safety).
        if (remoteIp is not null && IPAddress.IsLoopback(remoteIp))
            return true;

        // REST path: X-Api-Key header must match (constant-time comparison — SEC-002A).
        if (ConstantTimeEquals(apiKeyHeader, _passphrase))
            return true;

        // WebSocket / backward-compat path: ?key= query parameter must match (SEC-002A).
        // Browser clients now use the WS auth-frame protocol (SEC-002B); ?key= is kept
        // for non-browser clients that cannot set an initial auth frame.
        if (ConstantTimeEquals(keyQueryParam, _passphrase))
            return true;

        return false;
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    /// <summary>
    /// Compares two strings in constant time (SEC-002A).
    /// Returns <c>false</c> immediately if either argument is null (length is not secret),
    /// then delegates to <see cref="CryptographicOperations.FixedTimeEquals"/> on UTF-8 bytes.
    /// Length mismatch short-circuits before <c>FixedTimeEquals</c> (length is not secret).
    /// </summary>
    private static bool ConstantTimeEquals(string? a, string? b)
    {
        if (a is null || b is null) return false;

        var aBytes = Encoding.UTF8.GetBytes(a);
        var bBytes = Encoding.UTF8.GetBytes(b);

        // Different lengths: bail out early — lengths are not secret data.
        if (aBytes.Length != bBytes.Length) return false;

        return CryptographicOperations.FixedTimeEquals(aBytes, bBytes);
    }
}
