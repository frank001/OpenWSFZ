using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Web;

/// <summary>
/// Abstraction for broadcasting <c>txState</c> WebSocket events to connected clients.
/// Separating the interface from the concrete <see cref="TxEventBus"/> allows
/// <c>QsoAnswererService</c> unit tests to substitute a recording implementation
/// without requiring a live WebSocket hub (FR-UX-002).
/// </summary>
public interface ITxEventBus
{
    /// <summary>
    /// Broadcasts a <c>txState</c> event carrying the new QSO state,
    /// active partner callsign, arm state, and optional abort reason.
    /// </summary>
    /// <param name="state">New QSO answerer state.</param>
    /// <param name="partner">Active partner callsign, or <c>null</c> when transitioning to Idle.</param>
    /// <param name="autoAnswerEnabled">Whether the auto-answerer is currently armed.</param>
    /// <param name="abortReason">
    /// Human-readable abort reason, or <c>null</c> for normal completion and routine Idle pushes.
    /// </param>
    void Publish(
        QsoState state,
        string?  partner,
        bool     autoAnswerEnabled,
        string?  abortReason = null);
}
