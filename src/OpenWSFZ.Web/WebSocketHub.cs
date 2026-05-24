using System.Collections.Concurrent;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Audio;

namespace OpenWSFZ.Web;

/// <summary>
/// Manages all active WebSocket connections and handles per-connection lifecycle.
///
/// Each connection runs a loop that:
///   - Sends an initial <c>status</c> event on connect.
///   - Sends a <c>heartbeat</c> event every 5 seconds (carrying <c>audioActive</c>).
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

    // Static logger for the fire-and-forget BroadcastDecodes path.
    // Initialised by WebApp.Create after the DI container is built (via SetBroadcastLogger).
    private static ILogger _broadcastLogger = Microsoft.Extensions.Logging.Abstractions.NullLogger.Instance;

    /// <summary>
    /// Sets the logger used by the static <see cref="BroadcastDecodes"/> path.
    /// Called once at application start from <c>WebApp.Create</c>.
    /// </summary>
    internal static void SetBroadcastLogger(ILogger logger) => _broadcastLogger = logger;

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

    /// <summary>
    /// Handles a single WebSocket connection: sends the initial status event, then
    /// pumps heartbeats every 5 seconds until the client disconnects or <paramref name="ct"/>
    /// is cancelled.
    /// </summary>
    /// <param name="ws">Accepted WebSocket.</param>
    /// <param name="configStore">Config store for the initial status event.</param>
    /// <param name="audioMonitor">
    /// Tracks audio activity since the last heartbeat. May be <c>null</c> in tests.
    /// </param>
    /// <param name="logger">Per-connection logger.</param>
    /// <param name="ct">Cancellation token tied to the HTTP request lifetime.</param>
    public static async Task HandleAsync(
        WebSocket ws,
        IConfigStore configStore,
        AudioActivityMonitor? audioMonitor,
        DataFlowMonitor? dataFlowMonitor,
        CaptureManager? captureManager,
        AudioWatchdog? watchdog,
        ILogger logger,
        CancellationToken ct)
    {
        RegisterSocket(ws);
        logger.LogInformation("WebSocket connection accepted.");

        // B3: watchdog is a singleton constructed once in WebApp.Create and injected here.
        // Do not construct per-connection — multiple clients sharing independent watchdogs
        // would each trigger a restart after the threshold, causing N concurrent restarts.

        try
        {
            // Build initial status event. AudioActive mirrors IsCapturing for consistency
            // with the heartbeat: audioActive is true whenever WASAPI is delivering buffers,
            // not when amplitude exceeds an arbitrary threshold.
            var status    = new DaemonStatus(
                State:         "Running",
                Version:       AssemblyVersion.Get(),
                AudioDevice:   configStore.Current.AudioDeviceName,
                CaptureActive: captureManager?.IsCapturing ?? false,
                AudioActive:   captureManager?.IsCapturing ?? false);
            var statusMsg = new WsMessage(Type: "status", Payload: status);

            await SendStatusAsync(ws, statusMsg, ct);

            using var timer     = new PeriodicTimer(HeartbeatInterval);
            var       receiveTask = ReceiveUntilCloseAsync(ws, ct);

            while (!ct.IsCancellationRequested)
            {
                try
                {
                    var timerTask = timer.WaitForNextTickAsync(ct).AsTask();
                    var completed = await Task.WhenAny(timerTask, receiveTask);

                    if (completed == receiveTask || ws.State != WebSocketState.Open)
                        break;

                    // Reset the amplitude window each tick — result is no longer used for
                    // audioActive; kept so AudioActivityMonitor doesn't accumulate stale state.
                    audioMonitor?.ConsumeAndReset();

                    // B18 / B21: watchdog and audioActive both use data-flow (any chunk
                    // received), not amplitude. A quiet radio band is not an application
                    // failure — audioActive must be true whenever WASAPI is delivering buffers.
                    var dataFlowing = dataFlowMonitor?.ConsumeAndReset() ?? false;
                    var active      = dataFlowing; // audioActive = WASAPI is delivering data

                    // P-2 (DIAG): log heartbeat state to the server log so the distinction
                    // between a silent-but-running capture and a genuinely stopped capture
                    // is visible without needing to watch the browser WebSocket stream.
                    logger.LogInformation(
                        "Heartbeat: captureActive={CaptureActive}, audioActive={AudioActive}, dataFlowing={DataFlowing}",
                        captureManager?.IsCapturing ?? false, active, dataFlowing);

                    // S6: tick the watchdog with the data-flow flag.
                    // Fire-and-forget — does not block heartbeat emission.
                    if (watchdog is not null)
                        _ = watchdog.TickAsync(dataFlowing);

                    var heartbeatMsg = new WsHeartbeatMessage(
                        Type:    "heartbeat",
                        Payload: new HeartbeatPayload(
                            AudioActive:   active,
                            CaptureActive: captureManager?.IsCapturing ?? false));

                    await SendHeartbeatAsync(ws, heartbeatMsg, ct);
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
            logger.LogInformation("WebSocket connection closed.");
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
    /// True when at least one WebSocket client is currently connected.
    /// Used to gate FFT computation and serialisation when no clients exist.
    /// </summary>
    internal static bool HasClients => !ActiveSockets.IsEmpty;

    /// <summary>
    /// Broadcasts a <c>spectrum</c> event carrying the given magnitude bins to all
    /// currently connected WebSocket clients. Stale connections are closed and removed.
    /// </summary>
    /// <param name="bins">
    /// Array of 512 integers in [0, 255], mapping 0–2994 Hz frequency bins.
    /// </param>
    internal static void BroadcastSpectrum(int[] bins)
    {
        if (ActiveSockets.IsEmpty) return;

        var msg     = new WsSpectrumMessage(Type: "spectrum", Payload: bins);
        var json    = JsonSerializer.Serialize(msg, AppJsonContext.Default.WsSpectrumMessage);
        var bytes   = Encoding.UTF8.GetBytes(json);
        var segment = new ArraySegment<byte>(bytes);

        foreach (var (ws, _) in ActiveSockets)
            _ = SendWithTimeoutAsync(ws, segment);
    }

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
            // Abort immediately — CloseAsync with default CT would block indefinitely
            // on an already-unresponsive socket (R2).
            _broadcastLogger.LogWarning("WebSocket send timeout waiting for lock — dropping connection.");
            UnregisterSocket(ws);
            try { ws.Abort(); } catch { /* best-effort */ }
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
            // Send itself timed out — abort immediately rather than attempting a
            // graceful close handshake on an already-unresponsive socket (R2).
            _broadcastLogger.LogWarning("WebSocket send timed out during broadcast — dropping connection.");
            UnregisterSocket(ws);
            try { ws.Abort(); } catch { /* best-effort */ }
        }
        catch (WebSocketException ex)
        {
            _broadcastLogger.LogDebug(ex, "WebSocket exception during broadcast — removing connection.");
            UnregisterSocket(ws);
        }
        finally
        {
            try { sem.Release(); } catch (ObjectDisposedException) { /* already disposed on unregister */ }
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static async Task SendStatusAsync(WebSocket ws, WsMessage message, CancellationToken ct)
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

    private static async Task SendHeartbeatAsync(WebSocket ws, WsHeartbeatMessage message, CancellationToken ct)
    {
        if (!SendLocks.TryGetValue(ws, out var sem)) return;

        var json    = JsonSerializer.Serialize(message, AppJsonContext.Default.WsHeartbeatMessage);
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
