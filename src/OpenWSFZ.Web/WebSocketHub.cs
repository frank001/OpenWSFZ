using System.Collections.Concurrent;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Audio;
using System.Net;

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
    // Value is the app-scope ID assigned when the connection's WebApp.Create was called,
    // so AbortAll(scope) can target only the connections belonging to a specific app instance.
    // This prevents a test-infrastructure app (e.g. WebApplicationFactory) from aborting
    // sockets owned by a different app instance sharing the same static hub.
    private static readonly ConcurrentDictionary<WebSocket, Guid> ActiveSockets = new();

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

    // ── Auth frame validation (SEC-002B) ──────────────────────────────────────

    /// <summary>
    /// Authenticates a non-loopback WebSocket connection by expecting a
    /// <c>{"type":"auth","key":"..."}</c> frame as the very first message.
    /// <para>
    /// Called from the <c>/api/v1/ws</c> MapGet handler in <see cref="WebApp.Create"/>
    /// immediately after <see cref="System.Net.WebSockets.WebSocket.AcceptWebSocketAsync()"/>
    /// completes, but only for connections whose <c>RemoteIpAddress</c> is not loopback.
    /// </para>
    /// <para>
    /// Closes the socket with application-defined close code 4001 and returns <c>false</c>
    /// when the frame is absent (timeout), malformed (wrong type or missing key), or
    /// carries an invalid key according to <paramref name="authPolicy"/>.
    /// Loopback connections bypass this method entirely at the call site.
    /// </para>
    /// </summary>
    /// <param name="ws">Accepted WebSocket (not yet registered in the hub).</param>
    /// <param name="authPolicy">The active auth policy to validate the key against.</param>
    /// <param name="ct">Cancellation token tied to the HTTP request lifetime.</param>
    /// <returns><c>true</c> if authentication succeeded; <c>false</c> if the socket was closed.</returns>
    internal static async Task<bool> AuthenticateViaFrameAsync(
        WebSocket ws, IAuthPolicy authPolicy, CancellationToken ct)
    {
        const WebSocketCloseStatus InvalidAuth = (WebSocketCloseStatus)4001;
        const int AuthTimeoutMs = 5_000;

        // Use Task.WhenAny rather than a linked CancellationToken for the auth
        // timeout.  Canceling a ReceiveAsync via a CancellationToken causes
        // ManagedWebSocket to call Abort(), which drops the TCP connection without
        // sending a WS close frame — the client then sees an ungraceful disconnect
        // and cannot inspect the close code.  Keeping the socket Open while the
        // timeout delay fires lets us call CloseAsync(4001, ...) cleanly.
        var buffer      = new byte[512];
        var receiveTask = ws.ReceiveAsync(new ArraySegment<byte>(buffer), ct);
        var timeoutTask = Task.Delay(AuthTimeoutMs, ct);

        if (await Task.WhenAny(receiveTask, timeoutTask) == timeoutTask)
        {
            // Timeout: socket is still Open — send a proper close frame.
            await TryCloseAsync(ws, InvalidAuth, "Authentication timeout", ct);
            return false;
        }

        // receiveTask completed — inspect the result.
        WebSocketReceiveResult result;
        try
        {
            result = await receiveTask;
        }
        catch (WebSocketException)
        {
            // Connection was dropped before the auth frame arrived.
            return false;
        }
        catch (OperationCanceledException)
        {
            // HTTP request was cancelled (e.g., server shutdown).
            return false;
        }

        if (result.MessageType != WebSocketMessageType.Text)
        {
            await TryCloseAsync(ws, InvalidAuth, "Authentication required", ct);
            return false;
        }

        WsAuthFrame? frame;
        try
        {
            frame = JsonSerializer.Deserialize(
                buffer.AsSpan(0, result.Count),
                AppJsonContext.Default.WsAuthFrame);
        }
        catch (JsonException)
        {
            frame = null;
        }

        if (frame is null ||
            !string.Equals(frame.Type, "auth", StringComparison.Ordinal) ||
            string.IsNullOrEmpty(frame.Key))
        {
            await TryCloseAsync(ws, InvalidAuth, "Authentication required", ct);
            return false;
        }

        // Validate the key using the active auth policy.
        // Pass remoteIp = null so the loopback bypass is not triggered —
        // the call site already confirmed the connection is non-loopback.
        if (!authPolicy.IsAuthorized(remoteIp: null, apiKeyHeader: frame.Key, keyQueryParam: null))
        {
            await TryCloseAsync(ws, InvalidAuth, "Authentication failed", ct);
            return false;
        }

        return true;
    }

    private static async Task TryCloseAsync(
        WebSocket ws, WebSocketCloseStatus status, string description, CancellationToken ct)
    {
        if (ws.State is WebSocketState.Open or WebSocketState.CloseReceived)
        {
            try
            {
                using var closeCts = CancellationTokenSource.CreateLinkedTokenSource(ct);
                closeCts.CancelAfter(TimeSpan.FromSeconds(2));
                await ws.CloseAsync(status, description, closeCts.Token);
            }
            catch { /* best-effort */ }
        }
    }

    /// <summary>
    /// Aborts all currently-open WebSocket connections that belong to the given
    /// <paramref name="scope"/> (i.e., the connections accepted by the <see cref="WebApp"/>
    /// instance that was created with that scope ID).
    ///
    /// <para>
    /// Called at the start of application shutdown so the browser UI goes dark at once,
    /// rather than continuing to receive heartbeats for the duration of the shutdown sequence.
    /// The scope guard prevents a test-infrastructure app (e.g. <c>WebApplicationFactory</c>)
    /// from accidentally aborting sockets owned by a concurrently-running integration-test server.
    /// </para>
    ///
    /// Each connection's <see cref="HandleAsync"/> loop detects the aborted socket state via
    /// <see cref="ReceiveUntilCloseAsync"/> and exits without attempting a graceful close handshake.
    /// </summary>
    internal static void AbortAll(Guid scope)
    {
        foreach (var (ws, socketScope) in ActiveSockets)
        {
            if (socketScope != scope) continue;
            try { ws.Abort(); } catch { /* best-effort */ }
        }
    }

    // ── Socket registration ───────────────────────────────────────────────────

    private static void RegisterSocket(WebSocket ws, Guid scope)
    {
        ActiveSockets.TryAdd(ws, scope);
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
    /// <param name="scope">
    /// App-instance scope ID generated by <see cref="WebApp.Create"/>.
    /// Tagged on the socket so <see cref="AbortAll(Guid)"/> can target only this app's connections.
    /// </param>
    /// <param name="ct">Cancellation token tied to the HTTP request lifetime.</param>
    public static async Task HandleAsync(
        WebSocket ws,
        IConfigStore configStore,
        AudioActivityMonitor? audioMonitor,
        DataFlowMonitor? dataFlowMonitor,
        CaptureManager? captureManager,
        AudioWatchdog? watchdog,
        ICatState? catState,
        ILogger logger,
        Guid scope,
        CancellationToken ct)
    {
        RegisterSocket(ws, scope);
        logger.LogInformation("WebSocket connection accepted.");

        // B3: watchdog is a singleton constructed once in WebApp.Create and injected here.
        // Do not construct per-connection — multiple clients sharing independent watchdogs
        // would each trigger a restart after the threshold, causing N concurrent restarts.

        try
        {
            // Build initial status event. AudioActive mirrors IsCapturing for consistency
            // with the heartbeat: audioActive is true whenever WASAPI is delivering buffers,
            // not when amplitude exceeds an arbitrary threshold.
            var effectiveFreq = WebApp.ResolveEffectiveFrequency(catState, configStore.Current);
            var txCfg     = configStore.Current.Tx ?? new TxConfig();
            var status    = new DaemonStatus(
                State:               "Running",
                Version:             AssemblyVersion.Get(),
                AudioDevice:         configStore.Current.AudioDeviceFriendlyName ?? configStore.Current.AudioDeviceId,
                CaptureActive:       captureManager?.IsCapturing ?? false,
                AudioActive:         captureManager?.IsCapturing ?? false,
                DecodingEnabled:     configStore.Current.DecodingEnabled,
                DialFrequencyMHz:    effectiveFreq,
                CatConnectionStatus: catState?.Status.ToString() ?? "Disabled",
                RxAudioOffsetHz:     txCfg.RxAudioOffsetHz,
                TxAudioOffsetHz:     txCfg.TxAudioOffsetHz,
                HoldTxFreq:          txCfg.HoldTxFreq);
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
    /// <returns>
    /// A <see cref="Task"/> that completes when all per-socket sends have finished (or been
    /// dropped due to timeout).  Production callers may discard the task for fire-and-forget
    /// behaviour; test callers should await it to avoid the race between the send completing
    /// and the assertion reading the frame.
    /// </returns>
    public static Task BroadcastDecodes(IReadOnlyList<DecodeResult> results)
    {
        if (ActiveSockets.IsEmpty) return Task.CompletedTask;

        var msg   = new WsDecodeMessage(Type: "decode", Payload: [.. results]);
        var json  = JsonSerializer.Serialize(msg, AppJsonContext.Default.WsDecodeMessage);
        var bytes = Encoding.UTF8.GetBytes(json);
        var segment = new ArraySegment<byte>(bytes);

        var tasks = new List<Task>(ActiveSockets.Count);
        foreach (var (ws, _) in ActiveSockets)
            tasks.Add(SendWithTimeoutAsync(ws, segment));

        return Task.WhenAll(tasks);
    }

    /// <summary>
    /// Broadcasts a <c>cat_status</c> event to all WebSocket clients connected to the
    /// <see cref="WebApp"/> instance identified by <paramref name="scope"/> (FR-033, D5).
    ///
    /// <para>
    /// The scope guard matches the pattern already used in <see cref="AbortAll"/>:
    /// only sockets whose registered scope equals <paramref name="scope"/> receive the
    /// frame.  This prevents <c>CatPollingService</c> instances from one in-process
    /// <c>WebApp</c> (e.g. a <c>WebApplicationFactory</c> test host) from broadcasting
    /// to sockets belonging to a concurrently running integration-test server.
    /// </para>
    /// </summary>
    internal static void BroadcastCatStatus(
        Guid scope, CatConnectionStatus status, double? dialFrequencyMHz)
    {
        if (ActiveSockets.IsEmpty) return;

        var payload = new CatStatusPayload(status.ToString(), dialFrequencyMHz);
        var msg     = new WsCatStatusMessage(Type: "cat_status", Payload: payload);
        var json    = JsonSerializer.Serialize(msg, AppJsonContext.Default.WsCatStatusMessage);
        var bytes   = Encoding.UTF8.GetBytes(json);
        var segment = new ArraySegment<byte>(bytes);

        foreach (var (ws, socketScope) in ActiveSockets)
        {
            if (socketScope != scope) continue;   // scope guard — same pattern as AbortAll
            _ = SendWithTimeoutAsync(ws, segment);
        }
    }

    /// <summary>
    /// Broadcasts a <c>txState</c> event to all currently connected WebSocket clients (FR-047).
    /// Mirrors the <see cref="BroadcastDecodes"/> pattern: no scope guard since TX state
    /// is daemon-global (there is only one QSO controller per process).
    /// </summary>
    /// <param name="state">Raw enum name from <c>QsoState</c> or <c>CallerState</c>.</param>
    /// <param name="role"><c>"answerer"</c> or <c>"caller"</c>.</param>
    /// <param name="abortReason">
    /// Human-readable abort reason, or <c>null</c> for normal QSO completion and routine
    /// Idle pushes. Non-null only for abnormal terminations (FR-UX-002).
    /// </param>
    internal static void BroadcastTxState(
        string  state,
        string  role,
        string? partner,
        bool    autoAnswerEnabled,
        string? abortReason = null)
    {
        if (ActiveSockets.IsEmpty) return;

        var msg     = new WsTxStateMessage(Type: "txState", Role: role, State: state,
                                           Partner: partner, AutoAnswerEnabled: autoAnswerEnabled,
                                           AbortReason: abortReason);
        var json    = JsonSerializer.Serialize(msg, AppJsonContext.Default.WsTxStateMessage);
        var bytes   = Encoding.UTF8.GetBytes(json);
        var segment = new ArraySegment<byte>(bytes);

        foreach (var (ws, _) in ActiveSockets)
            _ = SendWithTimeoutAsync(ws, segment);
    }

    /// <summary>
    /// Broadcasts an <c>audioOffset</c> event to all currently connected WebSocket clients.
    /// Called when the operator updates the RX/TX cursor positions (via the waterfall or
    /// the <c>POST /api/v1/audio-offset</c> endpoint) or when the QSO answerer
    /// auto-updates the TX cursor (Hold TX = OFF, CQ answered).
    /// </summary>
    internal static void BroadcastAudioOffset(int rxHz, int txHz, bool holdTxFreq)
    {
        if (ActiveSockets.IsEmpty) return;

        var payload = new AudioOffsetPayload(rxHz, txHz, holdTxFreq);
        var msg     = new WsAudioOffsetMessage(Type: "audioOffset", Payload: payload);
        var json    = JsonSerializer.Serialize(msg, AppJsonContext.Default.WsAudioOffsetMessage);
        var bytes   = Encoding.UTF8.GetBytes(json);
        var segment = new ArraySegment<byte>(bytes);

        foreach (var (ws, _) in ActiveSockets)
            _ = SendWithTimeoutAsync(ws, segment);
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
