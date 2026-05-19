using System.Net.WebSockets;
using System.Text;
using System.Text.Json;

namespace OpenWSFZ.Web;

/// <summary>
/// Handles a single WebSocket connection:
/// sends one <c>status</c> event on connect, then a <c>heartbeat</c> every 5 s.
/// </summary>
internal static class WebSocketHub
{
    private static readonly TimeSpan HeartbeatInterval = TimeSpan.FromSeconds(5);

    public static async Task HandleAsync(WebSocket ws, CancellationToken ct)
    {
        var status = new DaemonStatus(State: "Running", Version: GetVersion());
        var statusMsg = new WsMessage(Type: "status", Payload: status);

        // Send initial status event on connect.
        await SendJsonAsync(ws, statusMsg, ct);

        // Heartbeat loop.
        using var timer = new PeriodicTimer(HeartbeatInterval);
        var heartbeatMsg = new WsMessage(Type: "heartbeat");

        while (!ct.IsCancellationRequested)
        {
            try
            {
                // Wait for the next tick or until the client closes.
                var timerTask = timer.WaitForNextTickAsync(ct).AsTask();
                var receiveTask = ReceiveUntilCloseAsync(ws, ct);

                var completed = await Task.WhenAny(timerTask, receiveTask);

                if (completed == receiveTask || ws.State != WebSocketState.Open)
                {
                    break;
                }

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

        // Complete the close handshake if still open, or echo back the close if
        // we received a client-initiated Close frame (CloseReceived state).
        if (ws.State is WebSocketState.Open or WebSocketState.CloseReceived)
        {
            await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "Server shutdown", default);
        }
    }

    private static async Task SendJsonAsync(WebSocket ws, WsMessage message, CancellationToken ct)
    {
        var json = JsonSerializer.Serialize(message, AppJsonContext.Default.WsMessage);
        var bytes = Encoding.UTF8.GetBytes(json);
        await ws.SendAsync(
            new ArraySegment<byte>(bytes),
            WebSocketMessageType.Text,
            endOfMessage: true,
            ct);
    }

    /// <summary>
    /// Drains incoming frames until the client sends a close frame or the socket faults.
    /// Returns when the connection should be considered closed from the client side.
    /// </summary>
    private static async Task ReceiveUntilCloseAsync(WebSocket ws, CancellationToken ct)
    {
        var buffer = new byte[256];
        while (ws.State == WebSocketState.Open && !ct.IsCancellationRequested)
        {
            var result = await ws.ReceiveAsync(new ArraySegment<byte>(buffer), ct);
            if (result.MessageType == WebSocketMessageType.Close)
            {
                return;
            }
        }
    }

    private static string GetVersion()
    {
        var asm = typeof(WebSocketHub).Assembly;
        return asm.GetName().Version?.ToString() ?? "0.0.0";
    }
}
