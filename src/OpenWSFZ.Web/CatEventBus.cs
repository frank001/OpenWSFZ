using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Web;

/// <summary>
/// Public façade that allows <c>OpenWSFZ.Daemon.Cat.CatPollingService</c> to
/// broadcast <c>cat_status</c> WebSocket events to all connected clients
/// without depending on the internal <see cref="WebSocketHub"/> class directly
/// (FR-033).
/// </summary>
public sealed class CatEventBus
{
    /// <summary>
    /// Broadcasts a <c>cat_status</c> event to every currently connected
    /// WebSocket client.
    /// </summary>
    /// <param name="status">Current CAT connection state.</param>
    /// <param name="dialFrequencyMHz">
    /// Latest polled VFO-A frequency in MHz, or <c>null</c> when unavailable.
    /// </param>
    public void Publish(CatConnectionStatus status, double? dialFrequencyMHz)
        => WebSocketHub.BroadcastCatStatus(status, dialFrequencyMHz);
}
