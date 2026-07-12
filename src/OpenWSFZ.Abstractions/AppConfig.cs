namespace OpenWSFZ.Abstractions;

/// <summary>
/// Operator configuration persisted to the config file.
/// </summary>
public sealed record AppConfig(
    /// <summary>OS-internal device identifier (WASAPI GUID, ALSA hw: string, etc.).</summary>
    string? AudioDeviceId             = null,
    /// <summary>Human-readable device label shown in the UI and logs.</summary>
    string? AudioDeviceFriendlyName   = null,
    /// <summary>OS-internal render (output) device identifier for the TX audio pipeline.</summary>
    string? AudioOutputDeviceId       = null,
    /// <summary>Human-readable render device label shown in the UI.</summary>
    string? AudioOutputFriendlyName   = null,
    int     Port                      = 8080,
    bool    ShowCycleCountdown      = false,
    /// <summary>
    /// Whether the FT8 decode pipeline is enabled (FR-017).
    /// Defaults to <c>true</c> — existing config files without this field
    /// deserialise to <c>true</c>, preserving the current unconditional-start behaviour.
    /// </summary>
    bool    DecodingEnabled         = true,
    /// <summary>
    /// Minimum log level for the console sink.
    /// One of: Trace, Debug, Information, Warning, Error, Critical, None.
    /// Default: "Information".
    /// </summary>
    string  LogLevel                = "Information")
{
    /// <summary>File logging configuration. Always non-null; defaults to file logging disabled.</summary>
    public LoggingConfig    Logging   { get; init; } = new();

    /// <summary>
    /// WSJT-X compatible ALL.TXT decode log configuration (FR-027, FR-028).
    /// Always non-null; defaults to decode logging disabled.
    /// </summary>
    public DecodeLogConfig  DecodeLog { get; init; } = new();

    /// <summary>
    /// CAT rig connection configuration (FR-031).
    /// Defaults to <c>null</c> (equivalent to <c>enabled = false</c>) so that
    /// existing config files without a <c>cat</c> key deserialise without error.
    /// Consumers SHALL treat a <c>null</c> value as <c>new CatConfig()</c> (disabled).
    /// </summary>
    public CatConfig?       Cat       { get; init; } = null;

    /// <summary>
    /// PTT (push-to-talk) keying configuration (FR-056). Always non-null; defaults to
    /// <c>Method = "AudioVox"</c>, which is byte-for-byte today's pre-<c>cat-tx-ptt</c>
    /// behaviour. A sibling of <see cref="Cat"/>, not nested inside it — PTT method
    /// selection is orthogonal to whether CAT is even enabled (an operator can run
    /// <c>SerialRtsDtr</c> PTT with <c>cat.enabled = false</c>).
    /// </summary>
    public PttConfig        Ptt       { get; init; } = new();

    /// <summary>
    /// TX / QSO answerer configuration (FR-046).
    /// Defaults to <c>null</c> so that existing config files without a <c>tx</c> key
    /// deserialise without error.
    /// Consumers SHALL treat a <c>null</c> value as <c>new TxConfig()</c> (all defaults).
    /// </summary>
    public TxConfig?           Tx           { get; init; } = null;

    /// <summary>
    /// LAN remote-access configuration (lan-remote-access phase).
    /// Always non-null; defaults to <c>Enabled = false</c>, <c>Passphrase = null</c>
    /// so that existing config files without a <c>remoteAccess</c> key deserialise
    /// without error and the web interface remains loopback-only.
    /// </summary>
    public RemoteAccessConfig  RemoteAccess { get; init; } = new();

    /// <summary>
    /// Runtime-configurable OSD gate parameters (decoder-settings-page, shim 20260030).
    /// Defaults to <c>null</c> so that existing config files without a <c>decoder</c>
    /// key deserialise without error.  A <c>null</c> value is treated by all consumers
    /// as equivalent to <c>new DecoderConfig()</c> (D-009 calibrated defaults:
    /// <c>kMinScorePass2=10</c>, <c>osdCorrThreshold=0.10</c>, <c>osdNhardMax=60</c>).
    /// </summary>
    public DecoderConfig?      Decoder      { get; init; } = null;

    /// <summary>
    /// Operator-controlled, persisted decode-noise suppression settings
    /// (<c>decode-noise-suppression</c> capability).
    /// Always non-null; defaults to <c>SuppressUnknownRegion: null</c> (auto, resolved from
    /// region-data presence) and <c>SuppressSynthetic: true</c> (R&amp;R-synthetic decodes
    /// suppressed by default).
    /// </summary>
    public DecodeNoiseSuppressionConfig DecodeNoiseSuppression { get; init; } = new();

    /// <summary>
    /// GridTracker2/WSJT-X-compatible UDP reporting configuration
    /// (<c>external-reporting</c> capability, gridtracker-udp-reporting change).
    /// Always non-null; defaults to <c>Enabled = false</c>, <c>Targets = []</c> so that
    /// existing config files without an <c>externalReporting</c> key deserialise without
    /// error and remain fully inert (no sockets opened) until an operator opts in.
    /// </summary>
    public ExternalReportingConfig ExternalReporting { get; init; } = new();
}
