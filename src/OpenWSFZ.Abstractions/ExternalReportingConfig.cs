using System.Text.Json.Serialization;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// A single outbound/inbound WSJT-X-protocol UDP target configured by the operator
/// (<c>external-reporting</c> capability, e.g. GridTracker2, JTAlert, N1MM+).
/// </summary>
public sealed record ExternalReportingTarget
{
    // ── Deserialization note ──────────────────────────────────────────────────
    //
    // STJ source-generation initialises value-type fields from JSON using CLR
    // defaults (int → 0, bool → false) rather than C# property-initialiser
    // defaults. Expose a [JsonConstructor] so absent JSON fields resolve to the
    // intended defaults — same pattern as TxConfig/RemoteAccessConfig.
    // ─────────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Deserialization constructor used by the STJ source-generated context.
    /// </summary>
    [JsonConstructor]
    public ExternalReportingTarget(
        string name    = "",
        string host    = "127.0.0.1",
        int    port    = 2237,
        bool   enabled = true)
    {
        Name    = name;
        Host    = host;
        Port    = port;
        Enabled = enabled;
    }

    /// <summary>
    /// Free-text operator label (e.g. <c>"GridTracker2"</c>). Not used on the wire.
    /// Default: <c>""</c>.
    /// </summary>
    public string Name { get; init; } = "";

    /// <summary>
    /// Destination hostname or IP address. Default: <c>"127.0.0.1"</c> (loopback).
    /// </summary>
    public string Host { get; init; } = "127.0.0.1";

    /// <summary>
    /// Destination UDP port. Must be in the range 1–65535; <c>POST /api/v1/config</c>
    /// rejects (HTTP 400, no partial persistence) any target outside this range.
    /// Default: <c>2237</c> (WSJT-X convention).
    /// </summary>
    public int Port { get; init; } = 2237;

    /// <summary>
    /// When <c>true</c> (default), this target receives every outbound datagram.
    /// When <c>false</c>, the target is configured but skipped without error.
    /// </summary>
    public bool Enabled { get; init; } = true;
}

/// <summary>
/// GridTracker2/WSJT-X-compatible UDP reporting configuration
/// (<c>external-reporting</c> capability, gridtracker-udp-reporting change).
/// Always non-null on <see cref="AppConfig"/>; a missing <c>externalReporting</c> key in the
/// config file deserialises to a fully-inert default (<c>Enabled = false</c>,
/// <c>Targets = []</c>, <c>HonourInboundCommands = false</c>) — identical to today's behaviour
/// (nothing is sent, nothing is listened for).
/// </summary>
public sealed record ExternalReportingConfig
{
    /// <summary>
    /// Deserialization constructor used by the STJ source-generated context.
    /// Parameter defaults ensure that fields absent from older config files load with
    /// the intended fully-inert values rather than CLR zero-defaults.
    /// </summary>
    [JsonConstructor]
    public ExternalReportingConfig(
        bool                                    enabled               = false,
        IReadOnlyList<ExternalReportingTarget>? targets               = null,
        bool                                    honourInboundCommands = false)
    {
        Enabled               = enabled;
        Targets               = targets ?? [];
        HonourInboundCommands = honourInboundCommands;
    }

    /// <summary>
    /// Master enable switch. When <c>false</c> (the default), <c>ExternalReportingService</c>
    /// opens no sockets, sends no datagrams, and listens for none.
    /// </summary>
    public bool Enabled { get; init; } = false;

    /// <summary>
    /// Configured outbound/inbound targets. Default: <c>[]</c> (empty — inert even if
    /// <see cref="Enabled"/> is <c>true</c>). Supports multiple simultaneous destinations.
    /// </summary>
    public IReadOnlyList<ExternalReportingTarget> Targets { get; init; } = [];

    /// <summary>
    /// Whether inbound <c>Reply</c>/<c>Free Text</c> datagrams are acted upon.
    /// <c>Halt Tx</c> is <em>not</em> gated by this flag — it is always honoured whenever the
    /// inbound listener is running (see <c>external-reporting</c> capability's spec for the
    /// rationale: a third-party program forcing TX <em>off</em> is safe by construction; forcing
    /// it <em>on</em> requires explicit operator consent). Default: <c>false</c>.
    /// </summary>
    public bool HonourInboundCommands { get; init; } = false;
}
