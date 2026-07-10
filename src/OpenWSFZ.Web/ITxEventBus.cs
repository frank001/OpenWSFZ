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
    /// <param name="keying">
    /// Current value of <see cref="OpenWSFZ.Abstractions.IQsoController.Keying"/> — true only
    /// while the publishing controller is inside its <c>TransmitAsync</c> helper's
    /// <c>KeyDownAsync</c> call. Defaults to <see langword="false"/> so existing call sites
    /// that broadcast a state transition (not a keying transition) need no change. Drives
    /// <c>#tx-enable-btn</c>'s bright-red/dark-red colour (dev-task
    /// 2026-07-10-tx-btn-live-verify-and-settings-tab-wrap.md item A).
    /// </param>
    void Publish(
        string  state,
        string  role,
        string? partner,
        bool    autoAnswerEnabled,
        string? abortReason = null,
        bool    keying = false);

    /// <summary>
    /// Broadcasts a <c>qsoReview</c> event to all connected WebSocket clients,
    /// carrying the full QSO record plus retained field values (qso-log-dialog).
    /// The browser uses this event to open the QSO confirmation dialog.
    /// </summary>
    void PublishQsoReview(
        OpenWSFZ.Abstractions.QsoRecord record,
        string retainedTxPower,
        string retainedComment,
        string retainedPropMode);
}
