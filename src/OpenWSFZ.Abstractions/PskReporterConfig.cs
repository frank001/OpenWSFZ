using System.Text.Json.Serialization;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// Opt-in upload of this station's own decodes to PSK Reporter (<c>psk-reporter-upload</c> capability, issue #262).
/// Always non-null on <see cref="AppConfig"/>; a missing <c>pskReporter</c> key loads as the inert defaults
/// (<see cref="Enabled"/> <c>false</c>), so nothing leaves the machine until the operator ticks the box.
/// </summary>
public sealed record PskReporterConfig
{
    /// <summary>The public PSK Reporter collector host name.</summary>
    public const string DefaultHost = "report.pskreporter.info";

    /// <summary>The collector's production UDP port (the test listener is 14739).</summary>
    public const int DefaultPort = 4739;

    // STJ source-generation initialises value-type fields from JSON with CLR defaults (bool -> false, int -> 0), not the
    // property initialisers, so a [JsonConstructor] gives absent JSON fields the intended defaults (same pattern as
    // ExternalReportingTarget / TxConfig).

    /// <summary>Deserialization constructor used by the STJ source-generated context.</summary>
    [JsonConstructor]
    public PskReporterConfig(
        bool   enabled            = false,
        string antennaInformation = "",
        string host               = DefaultHost,
        int    port               = DefaultPort)
    {
        Enabled            = enabled;
        AntennaInformation = antennaInformation;
        Host               = host;
        Port               = port;
    }

    /// <summary>Master switch. <c>false</c> (the default): no socket, no DNS lookup, no timer work, nothing queued.</summary>
    public bool Enabled { get; init; } = false;

    /// <summary>Free-text antenna description sent in the receiver record. Default <c>""</c> (the field is then omitted).</summary>
    public string AntennaInformation { get; init; } = "";

    /// <summary>Collector host. Configuration-file only (not on the Settings page): the test listener is <c>pskreporter.info</c>.</summary>
    public string Host { get; init; } = DefaultHost;

    /// <summary>Collector UDP port. Configuration-file only: 4739 production, 14739 for the test listener.</summary>
    public int Port { get; init; } = DefaultPort;
}
