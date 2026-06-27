namespace OpenWSFZ.Web;

/// <summary>
/// Public façade that allows QSO controller services to broadcast
/// <c>txState</c> WebSocket events to all connected clients without depending on the
/// internal <see cref="WebSocketHub"/> class directly (FR-047).
/// </summary>
public sealed class TxEventBus : ITxEventBus
{
    /// <summary>
    /// Broadcasts a <c>txState</c> event carrying the new state, active role, partner
    /// callsign, arm state, and optional abort reason to every WebSocket client
    /// currently connected.
    /// </summary>
    /// <param name="state">Raw enum name from <c>QsoState</c> or <c>CallerState</c>.</param>
    /// <param name="role"><c>"answerer"</c> or <c>"caller"</c>.</param>
    /// <param name="partner">
    /// Active partner callsign, or <c>null</c> when transitioning to Idle.
    /// </param>
    /// <param name="abortReason">
    /// Human-readable abort reason, or <c>null</c> for normal completion and routine
    /// Idle pushes (FR-UX-002).
    /// </param>
    public void Publish(
        string  state,
        string  role,
        string? partner,
        bool    autoAnswerEnabled,
        string? abortReason = null)
        => WebSocketHub.BroadcastTxState(state, role, partner, autoAnswerEnabled, abortReason);

    /// <inheritdoc/>
    public void PublishQsoReview(
        OpenWSFZ.Abstractions.QsoRecord record,
        string retainedTxPower,
        string retainedComment,
        string retainedPropMode)
    {
        var msg = new WsQsoReviewMessage(
            Type:              "qsoReview",
            Callsign:          record.PartnerCallsign,
            Grid:              record.PartnerGrid,
            RstSent:           record.RstSent,
            RstRcvd:           record.RstRcvd,
            StartUtc:          record.QsoStartUtc.ToString("O"),
            EndUtc:            record.QsoEndUtc.ToString("O"),
            FreqMHz:           record.DialFrequencyMHz,
            OperatorCallsign:  record.OperatorCallsign,
            RetainedTxPower:   retainedTxPower,
            RetainedComment:   retainedComment,
            RetainedPropMode:  retainedPropMode);

        WebSocketHub.BroadcastQsoReview(msg);
    }
}
