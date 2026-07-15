using System.Text.Json.Serialization;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// LAN remote-access configuration persisted to the config file (lan-remote-access phase).
/// <para>
/// Defaults to <c>Enabled = false</c>, <c>Passphrase = null</c> so that existing config
/// files without a <c>remoteAccess</c> key deserialise without error and the web interface
/// remains loopback-only with no authentication change.
/// </para>
/// </summary>
public sealed record RemoteAccessConfig
{
    // ── Deserialization note ──────────────────────────────────────────────────
    //
    // STJ source-generation initialises value-type fields from JSON using CLR
    // defaults (bool → false) rather than C# property-initialiser defaults.
    // Expose a [JsonConstructor] so that absent JSON fields resolve to the
    // intended defaults rather than CLR zeroes — same pattern as TxConfig.
    // ─────────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Deserialization constructor used by the STJ source-generated context.
    /// Parameter defaults ensure that fields absent from config files (e.g.
    /// a pre-LAN-access <c>app.json</c>) load with the intended values.
    /// </summary>
    [JsonConstructor]
    public RemoteAccessConfig(bool enabled = false, string? passphrase = null)
    {
        Enabled    = enabled;
        Passphrase = passphrase;
    }

    /// <summary>
    /// When <c>true</c>, Kestrel binds to <c>0.0.0.0</c> (all IPv4 interfaces)
    /// instead of <c>127.0.0.1</c>, making the web interface reachable from
    /// other devices on the local network. Requires a daemon restart to take effect —
    /// since <c>remote-daemon-restart</c>, that no longer requires physical/console access:
    /// see <c>POST /api/v1/system/restart</c> and the Settings → Advanced "Restart Daemon"
    /// action.
    /// Default: <c>false</c>.
    /// </summary>
    public bool    Enabled    { get; init; } = false;

    /// <summary>
    /// Shared passphrase for non-loopback access.
    /// <para>
    /// <strong>Required</strong> when <see cref="Enabled"/> is <c>true</c>.
    /// The daemon refuses to start (<c>LanModeValidator</c>, SEC-001) and
    /// <c>POST /api/v1/config</c> returns 400 when this is null or whitespace
    /// with <see cref="Enabled"/> set.
    /// </para>
    /// Stored as plaintext in <c>app.json</c>; acceptable for a home LAN threat model.
    /// Default: <c>null</c> (safe only when <see cref="Enabled"/> is <c>false</c>).
    /// </summary>
    public string? Passphrase { get; init; } = null;
}
