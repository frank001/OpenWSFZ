using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using FluentAssertions;
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
        var bus = new DecodeEventBus();
        bus.Publish([new OpenWSFZ.Abstractions.DecodeResult("15:30:00", -12, 0.3, 1234, "W1AW K1TTT EN43")]);

        // The decode event should arrive promptly.
        var frame = await ReadFrameAsync(ws, timeout: TimeSpan.FromSeconds(2));
        frame.Should().NotBeNull("decode event should be received");

        using var doc = JsonDocument.Parse(frame!);
        doc.RootElement.GetProperty("type").GetString().Should().Be("decode");

        var payload = doc.RootElement.GetProperty("payload");
        payload.ValueKind.Should().Be(JsonValueKind.Array);
        payload.GetArrayLength().Should().Be(1);
        payload[0].GetProperty("message").GetString().Should().Be("W1AW K1TTT EN43");

        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None);
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

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
