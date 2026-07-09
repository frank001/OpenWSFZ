using System.Linq;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using FluentAssertions;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Integration tests for the WebSocket endpoint.
/// Uses <see cref="RealServerFixture"/> because WebSocket upgrades require
/// a real TCP socket — <c>TestServer</c>'s in-memory transport does not support them.
/// </summary>
public sealed class WebSocketTests : IClassFixture<RealServerFixture>
{
    private readonly RealServerFixture _fixture;

    public WebSocketTests(RealServerFixture fixture) => _fixture = fixture;

    [Fact(DisplayName = "FR-002: GET /api/v1/ws upgrades and delivers status event")]
    public async Task WebSocket_ConnectDeliversStatusEvent()
    {
        using var ws = new ClientWebSocket();
        await ws.ConnectAsync(WsUri("/api/v1/ws"), CancellationToken.None);

        ws.State.Should().Be(WebSocketState.Open);

        var frame = await ReadFrameAsync(ws, timeout: TimeSpan.FromSeconds(2));
        frame.Should().NotBeNull();

        using var doc = JsonDocument.Parse(frame!);
        doc.RootElement.GetProperty("type").GetString().Should().Be("status");

        var payload = doc.RootElement.GetProperty("payload");
        payload.GetProperty("state").GetString().Should().Be("Running");
        var version = payload.GetProperty("version").GetString();
        version.Should().NotBeNullOrEmpty(
            "version must be set via <Version> in Directory.Build.props");
        version.Should().NotBe("0.0.0",
            "fallback sentinel must not reach the wire; set <Version> in Directory.Build.props");

        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None);
    }

    [Fact(DisplayName = "FR-002: heartbeat delivered within 6 seconds of connect")]
    public async Task WebSocket_HeartbeatDeliveredWithinSixSeconds()
    {
        using var ws = new ClientWebSocket();
        await ws.ConnectAsync(WsUri("/api/v1/ws"), CancellationToken.None);

        // Consume the initial status frame.
        await ReadFrameAsync(ws, timeout: TimeSpan.FromSeconds(2));

        // Loop until a heartbeat arrives, skipping any decode or other frames.
        // WebSocketHub.ActiveSockets is process-wide, so a concurrent decode test
        // may broadcast a decode frame to this socket before the heartbeat arrives.
        // Do not shorten the deadline; 6 seconds exists to absorb CI jitter.
        string? heartbeat = null;
        var deadline = TimeSpan.FromSeconds(6);
        while (heartbeat is null)
        {
            var frame = await ReadFrameAsync(ws, timeout: deadline);
            frame.Should().NotBeNull("heartbeat must arrive within 6 s");
            using var doc = JsonDocument.Parse(frame!);
            if (doc.RootElement.GetProperty("type").GetString() == "heartbeat")
                heartbeat = frame;
        }

        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None);
    }

    [Fact(DisplayName = "FR-020: heartbeat frame carries audioActive boolean field")]
    public async Task WebSocket_HeartbeatCarriesAudioActiveField()
    {
        using var ws = new ClientWebSocket();
        await ws.ConnectAsync(WsUri("/api/v1/ws"), CancellationToken.None);

        // Consume the initial status frame.
        await ReadFrameAsync(ws, timeout: TimeSpan.FromSeconds(2));

        // Wait for the first heartbeat, skipping any decode frames.
        string? heartbeat = null;
        var deadline = TimeSpan.FromSeconds(6);
        while (heartbeat is null)
        {
            var frame = await ReadFrameAsync(ws, timeout: deadline);
            frame.Should().NotBeNull("heartbeat must arrive within 6 s");
            using var doc = JsonDocument.Parse(frame!);
            if (doc.RootElement.GetProperty("type").GetString() == "heartbeat")
                heartbeat = frame;
        }

        // The heartbeat payload must contain 'audioActive' as a boolean.
        using var heartbeatDoc = JsonDocument.Parse(heartbeat);
        var payload = heartbeatDoc.RootElement.GetProperty("payload");
        payload.ValueKind.Should().Be(JsonValueKind.Object,
            "FR-020 requires the heartbeat payload to be an object");
        payload.TryGetProperty("audioActive", out var audioActiveProp).Should().BeTrue(
            "FR-020 requires heartbeat payload to include 'audioActive'");
        audioActiveProp.ValueKind.Should().Be(JsonValueKind.False,
            "no audio capture is running in tests so audioActive must be false");

        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None);
    }

    [Fact(DisplayName = "FR-020: status event payload carries audioActive boolean field")]
    public async Task WebSocket_StatusEventCarriesAudioActiveField()
    {
        using var ws = new ClientWebSocket();
        await ws.ConnectAsync(WsUri("/api/v1/ws"), CancellationToken.None);

        var frame = await ReadFrameAsync(ws, timeout: TimeSpan.FromSeconds(2));
        frame.Should().NotBeNull("status event must arrive on connect");

        using var doc = JsonDocument.Parse(frame!);
        doc.RootElement.GetProperty("type").GetString().Should().Be("status");

        var payload = doc.RootElement.GetProperty("payload");
        payload.TryGetProperty("audioActive", out var audioActiveProp).Should().BeTrue(
            "FR-020 requires the status payload to include 'audioActive'");
        audioActiveProp.ValueKind.Should().Be(JsonValueKind.False,
            "no audio capture is running in tests so audioActive must be false");

        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None);
    }

    [Fact(DisplayName = "f-005: initial status event payload carries hashTableRejectCount field")]
    public async Task WebSocket_StatusEventCarriesHashTableRejectCountField()
    {
        // f-005-hash-table-saturation-diagnostic: the initial WS status handshake carries the
        // native hash-table reject count (a snapshot at connect time), the same field served
        // live on GET /api/v1/status. This is the surface with no sibling-field precedent to
        // copy (the shimVersion tests are HTTP-only), so it mirrors the audioActive status test
        // above. Presence — not a specific value — is the guarantee under test (Risk 1).
        using var ws = new ClientWebSocket();
        await ws.ConnectAsync(WsUri("/api/v1/ws"), CancellationToken.None);

        var frame = await ReadFrameAsync(ws, timeout: TimeSpan.FromSeconds(2));
        frame.Should().NotBeNull("status event must arrive on connect");

        using var doc = JsonDocument.Parse(frame!);
        doc.RootElement.GetProperty("type").GetString().Should().Be("status");

        var payload = doc.RootElement.GetProperty("payload");
        payload.TryGetProperty("hashTableRejectCount", out var rejectCountProp).Should().BeTrue(
            "f-005 requires the initial WS status payload to include 'hashTableRejectCount'");
        rejectCountProp.GetInt32().Should().BeGreaterThanOrEqualTo(0,
            "the reject count is a non-negative session-lifetime counter, present even at 0");

        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None);
    }

    [Fact(DisplayName = "FR-002: plain HTTP GET to /api/v1/ws returns 400")]
    public async Task WebSocket_PlainHttpReturns400()
    {
        using var client = new HttpClient();
        var response = await client.GetAsync($"http://127.0.0.1:{_fixture.Port}/api/v1/ws");
        ((int)response.StatusCode).Should().Be(400);
    }

    [Fact(DisplayName = "NFR-004: server is bound to 127.0.0.1 loopback only")]
    public void Server_IsBoundToLoopback()
    {
        var ip = System.Net.IPAddress.Parse(_fixture.BoundHost);
        System.Net.IPAddress.IsLoopback(ip).Should()
            .BeTrue($"LoopbackBindPolicy must bind to 127.0.0.1, but got {_fixture.BoundHost}");
    }

    [Fact(DisplayName = "FR-009: connected WebSocket client receives decode event after BroadcastDecodes")]
    public async Task WebSocket_DecodeEventReceived_AfterBroadcast()
    {
        using var ws = new ClientWebSocket();
        await ws.ConnectAsync(WsUri("/api/v1/ws"), CancellationToken.None);

        // Drain the initial status frame.
        await ReadFrameAsync(ws, timeout: TimeSpan.FromSeconds(2));

        // Inject a decode result via the public DecodeEventBus.
        // Await Publish so the send completes before we call ReadFrameAsync — without this,
        // the fire-and-forget send races against the receive timeout and fails on loaded CI runners.
        // N6: must carry _fixture.AppScope — the scope guard means an unscoped (default) bus
        // would no longer reach this fixture's socket at all.
        var bus = new DecodeEventBus(_fixture.AppScope);
        await bus.Publish([new OpenWSFZ.Abstractions.DecodeResult("15:30:00", -12, 0.3, 1234, "Q1AW Q1TTT EN43")]);

        // The decode event must now be in the socket's receive buffer. Loop-and-skip any
        // non-decode frame (e.g. a heartbeat) — same defense-in-depth pattern already used by
        // WebSocket_HeartbeatDeliveredWithinSixSeconds and
        // TxState_BroadcastIncludesAutoAnswerEnabledField, as a second line of defense should a
        // future unscoped broadcast path (BroadcastQsoReview/BroadcastSpectrum) ever interleave
        // a frame here (N6 §4.3).
        string? frame = null;
        var deadline = TimeSpan.FromSeconds(3);
        while (frame is null)
        {
            var candidate = await ReadFrameAsync(ws, timeout: deadline);
            candidate.Should().NotBeNull("decode event should be received");
            using var candidateDoc = JsonDocument.Parse(candidate!);
            if (candidateDoc.RootElement.GetProperty("type").GetString() == "decode")
                frame = candidate;
        }

        using var doc = JsonDocument.Parse(frame!);
        doc.RootElement.GetProperty("type").GetString().Should().Be("decode");

        var payload = doc.RootElement.GetProperty("payload");
        payload.ValueKind.Should().Be(JsonValueKind.Array);
        payload.GetArrayLength().Should().Be(1);
        payload[0].GetProperty("message").GetString().Should().Be("Q1AW Q1TTT EN43");

        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None);
    }

    [Fact(DisplayName = "D-TX-UI-003: txState broadcast includes autoAnswerEnabled field")]
    public async Task TxState_BroadcastIncludesAutoAnswerEnabledField()
    {
        using var ws = new ClientWebSocket();
        await ws.ConnectAsync(WsUri("/api/v1/ws"), CancellationToken.None);
        ws.State.Should().Be(WebSocketState.Open);

        // Drain the initial status frame.
        await ReadFrameAsync(ws, timeout: TimeSpan.FromSeconds(2));

        // Broadcast a txState event via TxEventBus (same path as the daemon uses).
        // N6: must carry _fixture.AppScope — see WebSocket_DecodeEventReceived_AfterBroadcast.
        var bus = new TxEventBus(_fixture.AppScope);
        bus.Publish(state: "TxAnswer", role: "answerer", partner: "Q1TST", autoAnswerEnabled: true);

        // Read frames until we get a txState (skip heartbeats / decode frames from other tests).
        string? txFrame = null;
        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(3);
        while (txFrame is null && DateTime.UtcNow < deadline)
        {
            var frame = await ReadFrameAsync(ws, timeout: TimeSpan.FromSeconds(2));
            if (frame is null) break;
            using var doc = JsonDocument.Parse(frame);
            if (doc.RootElement.GetProperty("type").GetString() == "txState")
                txFrame = frame;
        }

        txFrame.Should().NotBeNull("txState frame must be received within the deadline");

        using var txDoc = JsonDocument.Parse(txFrame!);
        txDoc.RootElement.TryGetProperty("autoAnswerEnabled", out var prop)
            .Should().BeTrue("txState event must include autoAnswerEnabled field");
        prop.GetBoolean().Should().BeTrue("active-state broadcast must carry autoAnswerEnabled = true");

        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None);
    }

    // ── FR-UX-002: txState abort reason wire format ───────────────────────────

    [Fact(DisplayName = "FR-UX-002: abortReason property is omitted from txState frame when null")]
    public async Task TxState_AbortReasonOmittedWhenNull()
    {
        using var ws = new ClientWebSocket();
        await ws.ConnectAsync(WsUri("/api/v1/ws"), CancellationToken.None);
        await ReadFrameAsync(ws, timeout: TimeSpan.FromSeconds(2));   // drain initial status

        // Broadcast a normal (non-abort) txState — abortReason should be absent entirely.
        // N6: must carry _fixture.AppScope — see WebSocket_DecodeEventReceived_AfterBroadcast.
        var bus = new TxEventBus(_fixture.AppScope);
        bus.Publish(state: "TxAnswer", role: "answerer", partner: "Q1TST", autoAnswerEnabled: true, abortReason: null);

        string? txFrame = null;
        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(3);
        while (txFrame is null && DateTime.UtcNow < deadline)
        {
            var frame = await ReadFrameAsync(ws, timeout: TimeSpan.FromSeconds(2));
            if (frame is null) break;
            using var doc = JsonDocument.Parse(frame);
            if (doc.RootElement.GetProperty("type").GetString() == "txState")
                txFrame = frame;
        }

        txFrame.Should().NotBeNull("txState frame must be received within the deadline");

        using var txDoc = JsonDocument.Parse(txFrame!);
        // With JsonIgnore(WhenWritingNull) the property must be absent, not "abortReason":null.
        txDoc.RootElement.TryGetProperty("abortReason", out _)
            .Should().BeFalse("abortReason must be absent from the wire frame when null (WhenWritingNull policy)");

        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None);
    }

    [Fact(DisplayName = "FR-UX-002: abortReason is included in txState frame when non-null")]
    public async Task TxState_AbortReasonIncludedWhenNonNull()
    {
        using var ws = new ClientWebSocket();
        await ws.ConnectAsync(WsUri("/api/v1/ws"), CancellationToken.None);
        await ReadFrameAsync(ws, timeout: TimeSpan.FromSeconds(2));   // drain initial status

        // Broadcast an abort-transition txState with a reason string.
        // N6: must carry _fixture.AppScope — see WebSocket_DecodeEventReceived_AfterBroadcast.
        var bus = new TxEventBus(_fixture.AppScope);
        bus.Publish(state: "Idle", role: "answerer", partner: null, autoAnswerEnabled: false, abortReason: "Watchdog timeout");

        string? txFrame = null;
        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(3);
        while (txFrame is null && DateTime.UtcNow < deadline)
        {
            var frame = await ReadFrameAsync(ws, timeout: TimeSpan.FromSeconds(2));
            if (frame is null) break;
            using var doc = JsonDocument.Parse(frame);
            if (doc.RootElement.GetProperty("type").GetString() == "txState")
                txFrame = frame;
        }

        txFrame.Should().NotBeNull("txState frame must be received within the deadline");

        using var txDoc = JsonDocument.Parse(txFrame!);
        txDoc.RootElement.TryGetProperty("abortReason", out var prop)
            .Should().BeTrue("abortReason must be present in the wire frame when non-null");
        prop.GetString().Should().Be("Watchdog timeout",
            "abortReason must carry the exact reason string");

        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None);
    }

    // ── N6: cross-instance broadcast scope guard ──────────────────────────────

    [Fact(DisplayName = "N6: a second WebApp instance's decode/audioOffset/txState broadcasts do not reach this fixture's socket")]
    public async Task Broadcast_FromDifferentAppInstance_DoesNotReachThisFixturesSocket()
    {
        // Stand up a second, independent WebApp instance (own Kestrel listener, own
        // app-instance scope) in the same test process — the exact contamination shape
        // N6 diagnosed: WebSocketTests' RealServerFixture host running concurrently with
        // a second in-process WebApp instance sharing the same static WebSocketHub.
        var otherApp = WebApp.Create(port: 0);
        await otherApp.StartAsync();

        try
        {
            var otherPort = BoundPort(otherApp);

            using var mySocket    = new ClientWebSocket();
            using var otherSocket = new ClientWebSocket();
            await mySocket.ConnectAsync(WsUri("/api/v1/ws"), CancellationToken.None);
            await otherSocket.ConnectAsync(
                new Uri($"ws://127.0.0.1:{otherPort}/api/v1/ws"), CancellationToken.None);

            // Drain each socket's initial status frame.
            await ReadFrameAsync(mySocket, timeout: TimeSpan.FromSeconds(2));
            await ReadFrameAsync(otherSocket, timeout: TimeSpan.FromSeconds(2));

            // Broadcast a decode event scoped to THIS fixture's app instance.
            var myBus = new DecodeEventBus(_fixture.AppScope);
            await myBus.Publish([new DecodeResult("15:30:00", -12, 0.3, 1234, "Q1AW Q1TTT EN43")]);

            // It must arrive on this fixture's socket…
            var mineFrame = await ReadFrameAsync(mySocket, timeout: TimeSpan.FromSeconds(2));
            mineFrame.Should().NotBeNull("the scoped broadcast must reach its own instance's socket");
            using (var doc = JsonDocument.Parse(mineFrame!))
                doc.RootElement.GetProperty("type").GetString().Should().Be("decode");

            // …but must NOT arrive on the other (differently-scoped) instance's socket.
            // Note: ReadFrameAsync's deliberate timeout cancels the pending ReceiveAsync via
            // its CancellationToken, which — per the same behaviour documented in
            // WebSocketHub.AuthenticateViaFrameAsync — causes ManagedWebSocket to Abort() the
            // client socket rather than leaving it Open. So otherSocket is expected to end up
            // Aborted here; only attempt a graceful CloseAsync where the state still allows it.
            var leakedFrame = await ReadFrameAsync(otherSocket, timeout: TimeSpan.FromSeconds(1));
            leakedFrame.Should().BeNull(
                "N6: BroadcastDecodes must not deliver to sockets registered under a different app scope");

            if (mySocket.State == WebSocketState.Open)
                await mySocket.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None);
            if (otherSocket.State == WebSocketState.Open)
                await otherSocket.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None);
        }
        finally
        {
            await otherApp.StopAsync();
            await otherApp.DisposeAsync();
        }
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    private static int BoundPort(WebApplication app)
    {
        var feature = app.Services
            .GetRequiredService<IServer>()
            .Features.Get<IServerAddressesFeature>()!;
        return new Uri(feature.Addresses.First()).Port;
    }


    private Uri WsUri(string path) =>
        new($"ws://127.0.0.1:{_fixture.Port}{path}");

    private static async Task<string?> ReadFrameAsync(ClientWebSocket ws, TimeSpan timeout)
    {
        using var cts = new CancellationTokenSource(timeout);
        var buffer = new byte[4096];
        try
        {
            var result = await ws.ReceiveAsync(new ArraySegment<byte>(buffer), cts.Token);
            if (result.MessageType == WebSocketMessageType.Close) return null;
            return Encoding.UTF8.GetString(buffer, 0, result.Count);
        }
        catch (OperationCanceledException)
        {
            return null;
        }
    }
}
