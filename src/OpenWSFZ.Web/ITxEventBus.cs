namespace OpenWSFZ.Web;

/// <summary>
/// Abstraction for broadcasting <c>txState</c> WebSocket events to connected clients.
/// Separating the interface from the concrete <see cref="TxEventBus"/> allows
/// QSO controller unit tests to substitute a recording implementation
/// without requiring a live WebSocket hub (FR-UX-002).
/// </summary>
public interface ITxEventBus
{
    /// <summary>
    /// Broadcasts a <c>txState</c> event carrying the new QSO state,
    /// active role, partner callsign, arm state, and optional abort reason.
    /// </summary>
    /// <param name="state">New state as a string (raw enum name from either <c>QsoState</c> or <c>CallerState</c>).</param>
    /// <param name="role">Role string: <c>"answerer"</c> or <c>"caller"</c>.</param>
    /// <param name="partner">Active partner callsign, or <c>null</c> when transitioning to Idle.</param>
    /// <param name="autoAnswerEnabled">Whether the auto-answerer is currently armed.</param>
    /// <param name="abortReason">
    /// Human-readable abort reason, or <c>null</c> for normal completion and routine Idle pushes.
    /// </param>
    void Publish(
        string  state,
        string  role,
        string? partner,
        bool    autoAnswerEnabled,
        string? abortReason = null);
}
