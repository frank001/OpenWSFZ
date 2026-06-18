using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Web;

/// <summary>
/// Public façade that allows <c>OpenWSFZ.Daemon</c> to publish decoded FT8 results
/// to all connected WebSocket clients without depending on the internal
/// <see cref="WebSocketHub"/> class directly.
/// </summary>
public sealed class DecodeEventBus
{
    /// <summary>
    /// Broadcasts a <c>decode</c> event carrying <paramref name="results"/> to every
    /// currently connected WebSocket client.
    /// </summary>
    /// <returns>
    /// A <see cref="Task"/> that completes when all per-socket sends have finished.
    /// Production callers may discard this for fire-and-forget; test callers should await it.
    /// </returns>
    public Task Publish(IReadOnlyList<DecodeResult> results)
        => WebSocketHub.BroadcastDecodes(results);
}
