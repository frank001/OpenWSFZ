namespace OpenWSFZ.Abstractions;

/// <summary>
/// TX (transmit) configuration for the FT8 QSO answerer (FR-050).
/// Null at the AppConfig level is treated as the default <c>new TxConfig()</c>
/// (TX subsystem present but not enabled / using all defaults).
/// </summary>
public sealed record TxConfig
{
    /// <summary>
    /// Master enable for the QSO auto-answerer.
    /// When <c>false</c> (the default) the state machine remains in <c>Idle</c>
    /// regardless of decoded CQ calls; no transmission occurs.
    /// The operator must set this to <c>true</c> (via Settings) to activate TX.
    /// </summary>
    public bool   AutoAnswer      { get; init; } = false;

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
    public int    WatchdogMinutes    { get; init; } = 4;

    /// <summary>
    /// RX audio frequency cursor position in Hz (0–3000).
    /// Indicates the operator-selected receive offset within the 0–3 kHz audio passband.
    /// Default: 1500.
    /// </summary>
    public int    RxAudioOffsetHz    { get; init; } = 1500;

    /// <summary>
    /// TX audio frequency cursor position in Hz (0–3000).
    /// Used as the transmit offset when <see cref="HoldTxFreq"/> is <c>true</c>;
    /// auto-updated to the caller's <c>freqHz</c> when <see cref="HoldTxFreq"/> is <c>false</c>.
    /// Default: 1500.
    /// </summary>
    public int    TxAudioOffsetHz    { get; init; } = 1500;

    /// <summary>
    /// When <c>true</c>, the QSO answerer transmits at <see cref="TxAudioOffsetHz"/>
    /// regardless of the caller's audio frequency.
    /// When <c>false</c> (the default), the answerer uses the caller's decoded
    /// <c>freqHz</c> and auto-updates <see cref="TxAudioOffsetHz"/> so the waterfall
    /// cursor always reflects the actual TX position.
    /// </summary>
    public bool   HoldTxFreq         { get; init; } = false;
}
