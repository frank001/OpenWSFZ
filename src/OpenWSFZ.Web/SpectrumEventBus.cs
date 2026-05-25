namespace OpenWSFZ.Web;

/// <summary>
/// Public façade that allows <c>OpenWSFZ.Daemon</c> to broadcast spectrum data
/// to all connected WebSocket clients without depending on the internal
/// <see cref="WebSocketHub"/> class directly.
/// </summary>
public sealed class SpectrumEventBus
{
    /// <summary>
    /// True when at least one WebSocket client is currently connected.
    /// Used to gate FFT serialisation when no clients exist.
    /// </summary>
    public bool HasClients => WebSocketHub.HasClients;

    public void Publish(int[] bins) => WebSocketHub.BroadcastSpectrum(bins);
}
