using System.Collections.Concurrent;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Web;

/// <summary>
/// Manages all active WebSocket connections and handles per-connection lifecycle.
///
/// Each connection runs a loop that:
///   - Sends an initial <c>status</c> event on connect.
///   - Sends a <c>heartbeat</c> event every 5 seconds.
///   - Receives and discards incoming frames until the client closes.
///
/// The static <see cref="BroadcastDecodes"/> method sends a <c>decode</c> event
/// to every currently-open connection.  Connections that cannot accept the frame
/// within 1 second are closed and removed.
/// </summary>
internal static class WebSocketHub
{
    private static readonly TimeSpan HeartbeatInterval = TimeSpan.FromSeconds(5);
    private static readonly TimeSpan SendTimeout        = TimeSpan.FromSeconds(1);

    // Thread-safe set of all active connections.
    private static readonly ConcurrentDictionary<WebSocket, byte> ActiveSockets = new();

    // ── Per-connection handler ────────────────────────────────────────────────

    public static async Task HandleAsync(WebSocket ws, IConfigStore configStore, CancellationToken ct)
    {
        ActiveSockets.TryAdd(ws, 0);
        try
        {
            var status    = new DaemonStatus(
                State:       "Running",
                Version:     AssemblyVersion.Get(),
                AudioDevice: configStore.Current.AudioDeviceName);
            var statusMsg = new WsMessage(Type: "status", Payload: status);

            // Send initial status event on connect.
            await SendJsonAsync(ws, statusMsg, ct);

            using var timer = new PeriodicTimer(HeartbeatInterval);
            var heartbeatMsg = new WsMessage(Type: "heartbeat");
            var receiveTask  = ReceiveUntilCloseAsync(ws, ct);

            while (!ct.IsCancellationRequested)
            {
                try
                {
                    var timerTask = timer.WaitForNextTickAsync(ct).AsTask();
                    var completed = await Task.WhenAny(timerTask, receiveTask);

                    if (completed == receiveTask || ws.State != WebSocketState.Open)
                        break;

                    await SendJsonAsync(ws, heartbeatMsg, ct);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (WebSocketException)
                {
                    break;
                }
            }
        }
        finally
        {
            ActiveSockets.TryRemove(ws, out _);

            if (ws.State is WebSocketState.Open or WebSocketState.CloseReceived)
            {
                try
                {
                    await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "Server shutdown", default);
                }
                catch { /* best-effort */ }
            }
        }
    }

    // ── Broadcast ────────────────────────────────────────────────────────────

    /// <summary>
    /// Broadcasts a <c>decode</c> event to all currently connected WebSocket clients.
    /// Stale connections (those that cannot accept the frame within 1 second) are closed
    /// and removed silently.
    /// </summary>
    public static void BroadcastDecodes(IReadOnlyList<DecodeResult> results)
    {
        if (ActiveSockets.IsEmpty) return;

        var msg   = new WsDecodeMessage(Type: "decode", Payload: [.. results]);
        var json  = JsonSerializer.Serialize(msg, AppJsonContext.Default.WsDecodeMessage);
        var bytes = Encoding.UTF8.GetBytes(json);
        var segment = new ArraySegment<byte>(bytes);

        foreach (var (ws, _) in ActiveSockets)
        {
            _ = SendWithTimeoutAsync(ws, segment);
        }
    }

    private static async Task SendWithTimeoutAsync(WebSocket ws, ArraySegment<byte> data)
    {
        if (ws.State != WebSocketState.Open) return;

        using var cts = new CancellationTokenSource(SendTimeout);
        try
        {
            await ws.SendAsync(data, WebSocketMessageType.Text, endOfMessage: true, cts.Token);
        }
        catch (OperationCanceledException)
        {
            // Timeout — close and remove.
            ActiveSockets.TryRemove(ws, out _);
            try { await ws.CloseAsync(WebSocketCloseStatus.EndpointUnavailable, "Send timeout", default); }
            catch { /* best-effort */ }
        }
        catch (WebSocketException)
        {
            ActiveSockets.TryRemove(ws, out _);
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static async Task SendJsonAsync(WebSocket ws, WsMessage message, CancellationToken ct)
    {
        var json  = JsonSerializer.Serialize(message, AppJsonContext.Default.WsMessage);
        var bytes = Encoding.UTF8.GetBytes(json);
        await ws.SendAsync(
            new ArraySegment<byte>(bytes),
            WebSocketMessageType.Text,
            endOfMessage: true,
            ct);
    }

    private static async Task ReceiveUntilCloseAsync(WebSocket ws, CancellationToken ct)
    {
        var buffer = new byte[256];
        while (ws.State == WebSocketState.Open && !ct.IsCancellationRequested)
        {
            var result = await ws.ReceiveAsync(new ArraySegment<byte>(buffer), ct);
            if (result.MessageType == WebSocketMessageType.Close)
                return;
        }
    }
}
