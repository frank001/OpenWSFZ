using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Validates the LAN remote-access configuration at daemon startup (SEC-001).
/// <para>
/// When <c>RemoteAccess.Enabled = true</c>, a passphrase is mandatory.
/// An empty passphrase would cause <c>NullAuthPolicy</c> to be registered, leaving
/// every REST endpoint and WebSocket connection open to any device on the LAN.
/// The daemon refuses to start in this state.
/// </para>
/// </summary>
public static class LanModeValidator
{
    /// <summary>
    /// Returns <c>true</c> when the configuration is safe to start with.
    /// Returns <c>false</c> and a human-readable <paramref name="errorMessage"/> when
    /// LAN mode is enabled but no passphrase has been configured.
    /// </summary>
    public static bool IsValid(RemoteAccessConfig remoteAccess, out string? errorMessage)
    {
        if (remoteAccess.Enabled && string.IsNullOrWhiteSpace(remoteAccess.Passphrase))
        {
            errorMessage =
                "LAN remote access is enabled but no passphrase is configured. " +
                "Set RemoteAccess.Passphrase in config.json before enabling LAN mode. " +
                "Refusing to start.";
            return false;
        }

        errorMessage = null;
        return true;
    }
}
