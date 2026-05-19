namespace OpenWSFZ.Web;

/// <summary>
/// Returned by <c>GET /api/v1/status</c> and pushed as the first WebSocket event.
/// Fields will be populated by later phases; Phase 1 returns stubs only.
/// </summary>
public sealed record DaemonStatus(
    string State,
    string Version);
