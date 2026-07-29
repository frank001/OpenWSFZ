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
        bool                                    enabled                                = false,
        IReadOnlyList<ExternalReportingTarget>? targets                                = null,
        bool                                    honourInboundCommands                  = false,
        bool                                    restrictExternalRepliesToDecodeFilter  = false,
        string                                  instanceId                             = "OpenWSFZ",
        string                                  role                                   = "leader",
        string?                                 leaderUrl                              = null,
        IReadOnlyList<string>?                  followerUrls                           = null)
    {
        Enabled                                = enabled;
        Targets                                = targets ?? [];
        HonourInboundCommands                  = honourInboundCommands;
        RestrictExternalRepliesToDecodeFilter  = restrictExternalRepliesToDecodeFilter;
        InstanceId                             = instanceId;
        Role                                   = role;
        LeaderUrl                              = leaderUrl;
        FollowerUrls                           = followerUrls ?? [];
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

    /// <summary>
    /// When <c>false</c> (the default), an inbound Reply naming a callsign that is currently
    /// hidden under the operator's decode-panel filter (<c>DecodeFilterState</c>) is still
    /// honoured — an explicit external command is treated as authoritative regardless of what the
    /// operator happens to have filtered from their own view. When <c>true</c>, the pre-existing
    /// stricter behaviour is preserved: a filtered-out callsign is rejected exactly as an
    /// unrecognised one would be. Only meaningful when <see cref="HonourInboundCommands"/> is also
    /// <c>true</c> — Reply is discarded entirely before this flag is ever consulted otherwise.
    /// Applies symmetrically to both the Answerer (<c>QsoAnswererService.TryEngageExternal</c>) and
    /// Caller (<c>QsoCallerService.TryEngageExternalResponder</c>) external-reply engagement paths;
    /// never affects the manual/browser engagement paths or the internal auto-answer/auto-call
    /// automation scans, both of which continue to respect the decode-panel filter unconditionally
    /// regardless of this flag (fix-external-reporting-clear-and-reply-filter change).
    /// </summary>
    public bool RestrictExternalRepliesToDecodeFilter { get; init; } = false;

    /// <summary>
    /// WSJT-X-protocol "Id" field sent in every outbound Heartbeat/Status/Decode/QSOLogged/
    /// Clear/Close datagram. Companion programs (GridTracker, JTAlert, N1MM+, etc.) key off this
    /// field to distinguish multiple simultaneously-running protocol-compatible instances.
    /// Defaults to <c>"OpenWSFZ"</c> for single-instance sessions (unchanged, backward-compatible
    /// behaviour). Operators running more than one simultaneous instance (e.g. two bands captured
    /// via a split antenna) MUST give each instance a distinct value here, or companion programs
    /// will not be able to tell the instances apart — observed as a companion program's live
    /// decode view resetting every FT8 cycle and dropped forwarding to services such as
    /// PSKReporter (2026-07-28 dual-receiver session finding,
    /// fix-external-reporting-appid-collision change).
    /// </summary>
    public string InstanceId { get; init; } = "OpenWSFZ";

    /// <summary>
    /// <c>"leader"</c> (default) or <c>"follower"</c> (<c>external-reporting-single-connection</c>
    /// change). A <c>"leader"</c> instance behaves exactly as this service always has: it opens its
    /// own outbound/inbound sockets and speaks the WSJT-X protocol directly to <see cref="Targets"/>.
    /// A <c>"follower"</c> instance opens no sockets to <see cref="Targets"/> at all — every
    /// datagram it would have sent is instead relayed to <see cref="LeaderUrl"/> via
    /// <c>POST /api/v1/external-reporting/relay</c>, so that multiple local instances present as a
    /// single logical WSJT-X-protocol connection to companion programs such as GridTracker2 (and,
    /// through it, PSK Reporter). Any value other than the literal <c>"follower"</c> is treated as
    /// <c>"leader"</c> — this keeps every pre-existing config (no <c>role</c> key at all) byte-for-
    /// byte unchanged. Default: <c>"leader"</c>.
    /// </summary>
    public string Role { get; init; } = "leader";

    /// <summary>
    /// The leader daemon's own local HTTP base URL (e.g. <c>"http://127.0.0.1:8080"</c>), required
    /// and meaningful only when <see cref="Role"/> is <c>"follower"</c>. <c>POST /api/v1/config</c>
    /// rejects (HTTP 400, no partial persistence) a save with <c>role: "follower"</c> and a missing
    /// or empty <see cref="LeaderUrl"/>. Default: <c>null</c>.
    /// </summary>
    public string? LeaderUrl { get; init; } = null;

    /// <summary>
    /// Local base URLs (e.g. <c>["http://127.0.0.1:8081"]</c>) of follower instances this leader
    /// forwards an inbound <c>Halt Tx</c> to, in addition to acting on it itself. Meaningful only
    /// when <see cref="Role"/> is <c>"leader"</c>. Default: <c>[]</c> (empty — no broadcast).
    /// </summary>
    public IReadOnlyList<string> FollowerUrls { get; init; } = [];
}
