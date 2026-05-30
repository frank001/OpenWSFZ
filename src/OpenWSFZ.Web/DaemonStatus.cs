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
    bool    DecodingEnabled = false);
