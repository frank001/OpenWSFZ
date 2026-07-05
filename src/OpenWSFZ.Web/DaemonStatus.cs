namespace OpenWSFZ.Web;

/// <summary>
/// Returned by <c>GET /api/v1/status</c> and pushed as the first WebSocket event payload.
/// </summary>
public sealed record DaemonStatus(
    string  State,
    string  Version,
    string? AudioDevice    = null,
    bool    CaptureActive  = false,
    /// <summary>
    /// True if at least one audio sample with |value| > 1×10⁻⁶ was received
    /// since application start or the last pipeline restart (FR-020).
    /// </summary>
    bool    AudioActive    = false,
    /// <summary>
    /// Whether the FT8 decode pipeline is currently enabled (FR-017).
    /// Reflects <c>AppConfig.DecodingEnabled</c> — the authoritative persisted state.
    /// </summary>
    bool    DecodingEnabled = false,
    /// <summary>
    /// Effective dial frequency in MHz using the CAT precedence rule (FR-032):
    /// <c>ICatState.DialFrequencyMHz ?? AppConfig.DecodeLog.DialFrequencyMHz</c>.
    /// </summary>
    double  DialFrequencyMHz = 0.0,
    /// <summary>
    /// Current CAT connection state as a string (FR-033): <c>"Disabled"</c>, <c>"Connecting"</c>,
    /// <c>"Connected"</c>, or <c>"Error"</c>.  Defaults to <c>"Disabled"</c> when CAT is not wired up.
    /// </summary>
    string  CatConnectionStatus = "Disabled",
    /// <summary>
    /// Current RX audio frequency cursor position in Hz (0–3000).
    /// Included in the initial <c>status</c> WebSocket event so newly-connected clients
    /// can initialise their waterfall cursor without waiting for an <c>audioOffset</c> event.
    /// </summary>
    int     RxAudioOffsetHz = 1500,
    /// <summary>
    /// Current TX audio frequency cursor position in Hz (0–3000).
    /// </summary>
    int     TxAudioOffsetHz = 1500,
    /// <summary>
    /// Whether the QSO answerer is locked to the operator-set TX frequency.
    /// </summary>
    bool    HoldTxFreq = false,
    /// <summary>
    /// The native FT8 decoder shim's actual loaded ABI version
    /// (f-004-operator-visibility-improvements, daemon-status-visibility). Stable for the
    /// process lifetime once the native library has been initialised. Defaults to 0 for
    /// callers that do not wire up the native shim (e.g. minimal test fixtures).
    /// </summary>
    int     ShimVersion = 0);
