namespace OpenWSFZ.Web;

/// <summary>
/// Returned by <c>GET /api/v1/status</c> and pushed as the first WebSocket event payload.
/// </summary>
public sealed record DaemonStatus(
    string  State,
    string  Version,
    string? AudioDevice    = null,
    bool    CaptureActive  = false);
