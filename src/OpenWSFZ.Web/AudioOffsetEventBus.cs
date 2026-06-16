namespace OpenWSFZ.Web;

/// <summary>
/// Public façade that allows <c>OpenWSFZ.Daemon</c> components (e.g.
/// <c>QsoAnswererService</c> and the <c>POST /api/v1/audio-offset</c> endpoint)
/// to broadcast <c>audioOffset</c> WebSocket events to all connected clients
/// without depending on the internal <see cref="WebSocketHub"/> class directly.
/// </summary>
public sealed class AudioOffsetEventBus
{
    /// <summary>
    /// Broadcasts an <c>audioOffset</c> event carrying the new RX Hz, TX Hz, and
    /// Hold TX Freq state to every WebSocket client currently connected to any
    /// <see cref="WebApp"/> instance.
    /// </summary>
    /// <param name="rxHz">New RX audio frequency cursor position in Hz (0–3000).</param>
    /// <param name="txHz">New TX audio frequency cursor position in Hz (0–3000).</param>
    /// <param name="holdTxFreq">
    /// Whether the QSO answerer is locked to the operator-set TX frequency.
    /// </param>
    public void Publish(int rxHz, int txHz, bool holdTxFreq)
        => WebSocketHub.BroadcastAudioOffset(rxHz, txHz, holdTxFreq);
}
