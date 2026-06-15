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
    /// TX / QSO answerer configuration (FR-046).
    /// Defaults to <c>null</c> so that existing config files without a <c>tx</c> key
    /// deserialise without error.
    /// Consumers SHALL treat a <c>null</c> value as <c>new TxConfig()</c> (all defaults).
    /// </summary>
    public TxConfig?        Tx        { get; init; } = null;
}
