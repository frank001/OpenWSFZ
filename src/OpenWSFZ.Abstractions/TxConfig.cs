using System.Text.Json.Serialization;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// TX (transmit) configuration for the FT8 QSO answerer (FR-050).
/// Null at the AppConfig level is treated as the default <c>new TxConfig()</c>
/// (TX subsystem present but not enabled / using all defaults).
/// </summary>
public sealed record TxConfig
{
    // ── Deserialization note (D-WFC-001) ─────────────────────────────────────
    //
    // STJ source-generation initialises all value-type fields from JSON using
    // CLR defaults (int → 0, bool → false) rather than C# property-initialiser
    // defaults.  Fields absent from the JSON file therefore silently receive 0
    // instead of 1500 for RxAudioOffsetHz / TxAudioOffsetHz.
    //
    // Fix: expose a [JsonConstructor] that carries the correct default values as
    // parameter defaults.  When the source-generated deserialiser calls this
    // constructor, absent JSON parameters use their declared defaults (1500),
    // so older config files (pre-waterfall-cursors) load correctly.
    // ─────────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Deserialization constructor used by the STJ source-generated context.
    /// Parameter defaults ensure that fields absent from older config files
    /// (written before the waterfall-cursor feature) load with correct values
    /// rather than CLR zero-defaults (D-WFC-001).
    /// </summary>
    [JsonConstructor]
    public TxConfig(
        bool                   autoAnswer           = false,
        string                 callsign             = "Q1OFZ",
        string                 grid                 = "JO33",
        int                    retryCount           = 3,
        int                    watchdogMinutes      = 4,
        int                    rxAudioOffsetHz      = 1500,
        int                    txAudioOffsetHz      = 1500,
        bool                   holdTxFreq           = false,
        TxRole                 role                 = TxRole.Answerer,
        CallerPartnerSelectMode callerPartnerSelect  = CallerPartnerSelectMode.First,
        // qso-log-dialog: QsoConfirmation defaults to true (lesson 6 / design R4).
        // STJ source-gen would deserialise a missing bool field as false; the constructor
        // parameter default of true ensures old config files (without this key) still
        // enable the confirmation dialog on first run after upgrade.
        bool                   qsoConfirmation      = true,
        string                 retainedTxPower      = "",
        string                 retainedComment      = "",
        string                 retainedPropMode     = "")
    {
        AutoAnswer          = autoAnswer;
        Callsign            = callsign;
        Grid                = grid;
        RetryCount          = retryCount;
        WatchdogMinutes     = watchdogMinutes;
        RxAudioOffsetHz     = rxAudioOffsetHz;
        TxAudioOffsetHz     = txAudioOffsetHz;
        HoldTxFreq          = holdTxFreq;
        Role                = role;
        CallerPartnerSelect = callerPartnerSelect;
        QsoConfirmation     = qsoConfirmation;
        RetainedTxPower     = retainedTxPower;
        RetainedComment     = retainedComment;
        RetainedPropMode    = retainedPropMode;
    }

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
    /// 0 = unlimited (watchdog is the backstop). Clamped to [0, 200] at load time.
    /// Default: 3.
    /// </summary>
    public int    RetryCount      { get; init; } = 3;

    /// <summary>
    /// Watchdog timeout in minutes.  If a QSO has been in progress for this
    /// many minutes without completing, the answerer aborts to <c>Idle</c>.
    /// Clamped to [1, 60] at load time.
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

    /// <summary>
    /// The TX role the daemon operates in.
    /// <c>Answerer</c> (default): responds to incoming CQ calls via <c>QsoAnswererService</c>.
    /// <c>Caller</c>: originates CQ calls via <c>QsoCallerService</c>.
    /// A daemon restart is required when this value changes.
    /// </summary>
    public TxRole Role { get; init; } = TxRole.Answerer;

    /// <summary>
    /// Determines how <c>QsoCallerService</c> selects a responding station while in
    /// <c>WaitAnswer</c>. Only relevant when <see cref="Role"/> is <c>Caller</c>.
    /// <c>First</c> (default): auto-engage the first responder.
    /// <c>None</c>: operator clicks a highlighted decode-table row.
    /// </summary>
    public CallerPartnerSelectMode CallerPartnerSelect { get; init; } = CallerPartnerSelectMode.First;

    // ── QSO confirmation dialog fields (qso-log-dialog) ───────────────────────

    /// <summary>
    /// When <c>true</c> (default), the browser confirmation dialog is shown when the last
    /// TX begins; ADIF is written only when the operator clicks OK.
    /// When <c>false</c>, the existing silent auto-log at <c>QsoComplete</c> is used.
    /// </summary>
    public bool QsoConfirmation { get; init; } = true;

    /// <summary>
    /// Last TX power value for which the operator checked "Retain".
    /// Pre-fills the Tx Power field in subsequent confirmation dialogs.
    /// Empty string when no value has been retained.
    /// </summary>
    public string RetainedTxPower { get; init; } = string.Empty;

    /// <summary>
    /// Last comment value for which the operator checked "Retain".
    /// Pre-fills the Comments field in subsequent confirmation dialogs.
    /// Empty string when no value has been retained.
    /// </summary>
    public string RetainedComment { get; init; } = string.Empty;

    /// <summary>
    /// Last propagation mode ADIF value for which the operator checked "Retain".
    /// Pre-fills the Prop Mode dropdown in subsequent confirmation dialogs.
    /// Empty string when no value has been retained.
    /// </summary>
    public string RetainedPropMode { get; init; } = string.Empty;
}
