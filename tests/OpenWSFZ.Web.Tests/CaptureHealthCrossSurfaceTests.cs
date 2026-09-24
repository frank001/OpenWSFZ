using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using FluentAssertions;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging.Abstractions;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// U6 (tasks.md §5.3, capture-stall-detection-unattended #188): REST <c>audioActive</c> ==
/// initial WebSocket <c>status.audioActive</c> == the next WebSocket <c>heartbeat.audioActive</c>,
/// for the same window — proving <c>GET /api/v1/status</c>, the initial WS event, and the
/// recurring WS heartbeat frame all read the one <see cref="CaptureHealthMonitor"/> snapshot
/// (design.md Decisions 4 and 6), rather than three independently-computed values that could
/// disagree.
///
/// <para>
/// Drives <see cref="CaptureHealthMonitor.TickOnceAsync"/> directly (no <c>Start()</c> call) so
/// the window boundary is deterministic — the real per-connection heartbeat loop still runs its
/// own genuine 5 s <c>PeriodicTimer</c> (design.md Decision 6 leaves that timer unchanged), so
/// this test still waits a real handful of seconds for a heartbeat frame, same budget as
/// <c>WebSocketTests.WebSocket_HeartbeatDeliveredWithinSixSeconds</c>.
/// </para>
/// </summary>
public sealed class CaptureHealthCrossSurfaceTests : IAsyncLifetime
{
    private Microsoft.AspNetCore.Builder.WebApplication? _app;
    private HttpClient       _http   = null!;
    private CaptureHealthMonitor _captureHealth = null!;
    private DataFlowMonitor  _dataFlow = null!;
    private int              _port;
    private readonly Guid    _scope = Guid.NewGuid();

    public async Task InitializeAsync()
    {
        _dataFlow = new DataFlowMonitor();
        // No AudioWatchdog needed — this test only exercises the published snapshot's agreement
        // across surfaces, not restart behaviour (that is AudioWatchdogTests/CaptureHealthMonitorTests).
        _captureHealth = new CaptureHealthMonitor(
            isCapturing:     () => false,
            dataFlowMonitor: _dataFlow,
            watchdog:        null,
            logger:          NullLogger.Instance);
        // Deliberately NOT calling _captureHealth.Start() — the test ticks it manually so the
        // window boundary this test asserts across is deterministic, not raced against a real
        // 5 s production timer.

        _app = OpenWSFZ.Web.WebApp.Create(port: 0, appScope: _scope,
            dataFlowMonitor: _dataFlow, captureHealthMonitor: _captureHealth);
        await _app.StartAsync();

        var feature = _app.Services.GetRequiredService<IServer>()
            .Features.Get<IServerAddressesFeature>()!;
        _port = new Uri(feature.Addresses.First()).Port;
        _http = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{_port}") };
    }

    public async Task DisposeAsync()
    {
        _http.Dispose();
        if (_app is not null)
        {
            await _app.StopAsync();
            await _app.DisposeAsync();
        }
    }

    [Fact(DisplayName = "U6: REST audioActive == initial WS status.audioActive == the next WS heartbeat.audioActive, for the same window")]
    public async Task AudioActive_AgreesAcrossAllThreeSurfaces()
    {
        // Drive one window with a chunk received, so audioActive is deterministically true
        // everywhere for the remainder of this test (no further ticks occur — Start() was never
        // called — so the value cannot drift between the three reads below).
        _dataFlow.OnChunkReceived();
        await _captureHealth.TickOnceAsync();

        // ── REST ──
        var statusResponse = await _http.GetAsync("/api/v1/status");
        using var statusDoc = JsonDocument.Parse(await statusResponse.Content.ReadAsStringAsync());
        var restAudioActive = statusDoc.RootElement.GetProperty("audioActive").GetBoolean();
        restAudioActive.Should().BeTrue("precondition — a chunk was fed before this read");

        // ── Initial WS status event ──
        using var ws = new ClientWebSocket();
        await ws.ConnectAsync(new Uri($"ws://127.0.0.1:{_port}/api/v1/ws"), CancellationToken.None);
        var initialFrame = await ReadFrameAsync(ws, TimeSpan.FromSeconds(2));
        initialFrame.Should().NotBeNull();
        using var initialDoc = JsonDocument.Parse(initialFrame!);
        initialDoc.RootElement.GetProperty("type").GetString().Should().Be("status");
        var wsInitialAudioActive = initialDoc.RootElement.GetProperty("payload")
            .GetProperty("audioActive").GetBoolean();

        // ── Next WS heartbeat frame (real 5 s timer — same budget as WebSocketTests) ──
        string? heartbeatFrame = null;
        var deadline = TimeSpan.FromSeconds(6);
        while (heartbeatFrame is null)
        {
            var frame = await ReadFrameAsync(ws, deadline);
            frame.Should().NotBeNull("heartbeat must arrive within 6 s");
            using var frameDoc = JsonDocument.Parse(frame!);
            if (frameDoc.RootElement.GetProperty("type").GetString() == "heartbeat")
                heartbeatFrame = frame;
        }
        using var heartbeatDoc = JsonDocument.Parse(heartbeatFrame);
        var wsHeartbeatAudioActive = heartbeatDoc.RootElement.GetProperty("payload")
            .GetProperty("audioActive").GetBoolean();

        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None);

        // ── Agreement ──
        restAudioActive.Should().Be(wsInitialAudioActive,
            "REST and the initial WS status event must read the same CaptureHealthMonitor snapshot");
        restAudioActive.Should().Be(wsHeartbeatAudioActive,
            "the recurring WS heartbeat frame must carry the same value too — none of the three latches");
    }

    [Fact(DisplayName = "U6: audioActive falls to false on REST and the initial WS event together, in the same window")]
    public async Task AudioActive_FallsOnBothSurfaces_InTheSameWindow()
    {
        // Establish true, then let a window pass with no chunk — audioActive must fall on both
        // surfaces simultaneously (no surface may still report the stale true value).
        _dataFlow.OnChunkReceived();
        await _captureHealth.TickOnceAsync();
        await _captureHealth.TickOnceAsync(); // silent window — dataFlowing/audioActive fall

        var statusResponse = await _http.GetAsync("/api/v1/status");
        using var statusDoc = JsonDocument.Parse(await statusResponse.Content.ReadAsStringAsync());
        statusDoc.RootElement.GetProperty("audioActive").GetBoolean().Should().BeFalse();
        statusDoc.RootElement.GetProperty("dataFlowing").GetBoolean().Should().BeFalse();

        using var ws = new ClientWebSocket();
        await ws.ConnectAsync(new Uri($"ws://127.0.0.1:{_port}/api/v1/ws"), CancellationToken.None);
        var initialFrame = await ReadFrameAsync(ws, TimeSpan.FromSeconds(2));
        using var initialDoc = JsonDocument.Parse(initialFrame!);
        initialDoc.RootElement.GetProperty("payload").GetProperty("audioActive").GetBoolean()
            .Should().BeFalse("both surfaces must agree — audioActive does not latch on either");

        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None);
    }

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
