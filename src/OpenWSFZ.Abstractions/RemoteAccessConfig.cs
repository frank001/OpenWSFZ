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
    /// other devices on the local network. Requires a daemon restart to take effect.
    /// Default: <c>false</c>.
    /// </summary>
    public bool    Enabled    { get; init; } = false;

    /// <summary>
    /// Shared passphrase for non-loopback access.
    /// <c>null</c> or empty means no authentication is required (open LAN access).
    /// Stored as plaintext in <c>app.json</c>; acceptable for a home LAN threat model.
    /// Default: <c>null</c>.
    /// </summary>
    public string? Passphrase { get; init; } = null;
}
