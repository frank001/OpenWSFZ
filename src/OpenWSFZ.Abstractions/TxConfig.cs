namespace OpenWSFZ.Abstractions;

/// <summary>
/// TX (transmit) configuration for the FT8 QSO answerer (FR-046).
/// Null at the AppConfig level is treated as the default <c>new TxConfig()</c>
/// (TX subsystem present but not enabled / using all defaults).
/// </summary>
public sealed record TxConfig
{
    /// <summary>
    /// Operator callsign used in outgoing FT8 messages.
    /// Must be a valid FT8 callsign (≤ 11 characters).
    /// Default: <c>"Q1OFZ"</c> (ITU-unallocated Q-prefix placeholder — replace before operating).
    /// </summary>
    public string Callsign        { get; init; } = "Q1OFZ";

    /// <summary>
    /// Operator Maidenhead grid locator (4-character) used in outgoing FT8 messages.
    /// Default: <c>"JO33"</c> (placeholder — replace before operating).
    /// </summary>
    public string Grid            { get; init; } = "JO33";

    /// <summary>
    /// Maximum number of retry cycles per QSO state before the answerer aborts.
    /// A "retry" occurs when a partner does not respond within one FT8 period.
    /// Minimum effective value is 1 (clamped at load time).
    /// Default: 3.
    /// </summary>
    public int    RetryCount      { get; init; } = 3;

    /// <summary>
    /// Watchdog timeout in minutes.  If a QSO has been in progress for this
    /// many minutes without completing, the answerer aborts to <c>Idle</c>.
    /// Minimum effective value is 1 (clamped at load time).
    /// Default: 4.
    /// </summary>
    public int    WatchdogMinutes { get; init; } = 4;
}
