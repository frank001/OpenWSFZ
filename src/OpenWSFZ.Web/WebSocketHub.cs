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
///
/// <para>
/// A per-socket <see cref="SemaphoreSlim"/>(1,1) serialises all <c>SendAsync</c> calls
/// on the same socket, preventing concurrent-send violations when heartbeat and broadcast
/// decode events overlap (required for WAV fixture tests and any high-throughput scenario).
/// </para>
/// </summary>
internal static class WebSocketHub
{
    private static readonly TimeSpan HeartbeatInterval = TimeSpan.FromSeconds(5);
    private static readonly TimeSpan SendTimeout        = TimeSpan.FromSeconds(1);

    // Thread-safe set of all active connections.
    private static readonly ConcurrentDictionary<WebSocket, byte> ActiveSockets = new();

    // Per-socket send serialiser: SemaphoreSlim(1,1) ensures at most one SendAsync
    // is in-flight on any given socket at any time.
    private static readonly ConcurrentDictionary<WebSocket, SemaphoreSlim> SendLocks = new();

    // ── Socket registration ───────────────────────────────────────────────────

    private static void RegisterSocket(WebSocket ws)
    {
        ActiveSockets.TryAdd(ws, 0);
        SendLocks.TryAdd(ws, new SemaphoreSlim(1, 1));
    }

    private static void UnregisterSocket(WebSocket ws)
    {
        ActiveSockets.TryRemove(ws, out _);
        if (SendLocks.TryRemove(ws, out var sem))
            sem.Dispose();
    }

    // ── Per-connection handler ────────────────────────────────────────────────

    public static async Task HandleAsync(WebSocket ws, IConfigStore configStore, CancellationToken ct)
    {
        RegisterSocket(ws);
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
            UnregisterSocket(ws);

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
    /// and removed silently.  Concurrent calls from the decode pump are safe: each socket
    /// has its own send semaphore that serialises overlapping sends.
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
        if (!SendLocks.TryGetValue(ws, out var sem)) return;

        using var cts = new CancellationTokenSource(SendTimeout);

        // Acquire the per-socket send lock with the same timeout budget.
        try
        {
            await sem.WaitAsync(cts.Token);
        }
        catch (OperationCanceledException)
        {
            // Timed out waiting for the lock (another send is stuck).
            UnregisterSocket(ws);
            try { await ws.CloseAsync(WebSocketCloseStatus.EndpointUnavailable, "Send timeout", default); }
            catch { /* best-effort */ }
            return;
        }
        catch (ObjectDisposedException)
        {
            // Socket was unregistered and semaphore disposed between TryGetValue and WaitAsync.
            return;
        }

        try
        {
            if (ws.State == WebSocketState.Open)
                await ws.SendAsync(data, WebSocketMessageType.Text, endOfMessage: true, cts.Token);
        }
        catch (OperationCanceledException)
        {
            // Send itself timed out — close and remove.
            UnregisterSocket(ws);
            try { await ws.CloseAsync(WebSocketCloseStatus.EndpointUnavailable, "Send timeout", default); }
            catch { /* best-effort */ }
        }
        catch (WebSocketException)
        {
            UnregisterSocket(ws);
        }
        finally
        {
            try { sem.Release(); } catch (ObjectDisposedException) { /* already disposed on unregister */ }
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static async Task SendJsonAsync(WebSocket ws, WsMessage message, CancellationToken ct)
    {
        if (!SendLocks.TryGetValue(ws, out var sem)) return;

        var json    = JsonSerializer.Serialize(message, AppJsonContext.Default.WsMessage);
        var bytes   = Encoding.UTF8.GetBytes(json);
        var segment = new ArraySegment<byte>(bytes);

        try
        {
            await sem.WaitAsync(ct);
        }
        catch (OperationCanceledException) { return; }
        catch (ObjectDisposedException)    { return; }

        try
        {
            if (ws.State == WebSocketState.Open)
                await ws.SendAsync(segment, WebSocketMessageType.Text, endOfMessage: true, ct);
        }
        finally
        {
            try { sem.Release(); } catch (ObjectDisposedException) { }
        }
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
