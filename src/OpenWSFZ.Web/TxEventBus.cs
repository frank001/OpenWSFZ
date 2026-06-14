using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Web;

/// <summary>
/// Public façade that allows <c>OpenWSFZ.Daemon.QsoAnswererService</c> to broadcast
/// <c>txState</c> WebSocket events to all connected clients without depending on the
/// internal <see cref="WebSocketHub"/> class directly (FR-047).
/// </summary>
public sealed class TxEventBus
{
    /// <summary>
    /// Broadcasts a <c>txState</c> event carrying the new answerer state and active
    /// partner callsign to every WebSocket client currently connected to any
    /// <see cref="WebApp"/> instance.
    /// </summary>
    /// <param name="state">New QSO answerer state.</param>
    /// <param name="partner">
    /// Active partner callsign, or <c>null</c> when transitioning to
    /// <see cref="QsoState.Idle"/>.
    /// </param>
    public void Publish(QsoState state, string? partner)
        => WebSocketHub.BroadcastTxState(state, partner);
}
