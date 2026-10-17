using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using FluentAssertions;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// capture-loss-instrument 1.8: the three capture-loss counters appear on
/// <c>GET /api/v1/status</c> and on the initial WebSocket <c>status</c> event, read live from a
/// provider, and default to 0 when no provider is wired.  JSON names follow the camelCase of
/// <c>cycleArchiveDroppedCycles</c>.
/// </summary>
public sealed class CaptureLossStatusTests
{
    private static readonly CaptureLossSnapshot Sample = new(OverrunCount: 7, OverrunReportedMs: 1234, ChannelDroppedChunks: 55);

    private static async Task<(Microsoft.AspNetCore.Builder.WebApplication App, int Port)> StartAsync(
        Func<CaptureLossSnapshot>? provider)
    {
        var app = OpenWSFZ.Web.WebApp.Create(port: 0, appScope: Guid.NewGuid(), captureLossProvider: provider);
        await app.StartAsync();
        var feature = app.Services.GetRequiredService<IServer>().Features.Get<IServerAddressesFeature>()!;
        return (app, new Uri(feature.Addresses.First()).Port);
    }

    private static async Task<JsonDocument> GetRestStatusAsync(int port)
    {
        using var http = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{port}") };
        return JsonDocument.Parse(await http.GetStringAsync("/api/v1/status"));
    }

    private static async Task<JsonDocument> GetInitialWsStatusAsync(int port)
    {
        using var ws = new ClientWebSocket();
        await ws.ConnectAsync(new Uri($"ws://127.0.0.1:{port}/api/v1/ws"), CancellationToken.None);
        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(5));
        var buffer = new byte[16 * 1024];
        var result = await ws.ReceiveAsync(buffer, cts.Token);
        var doc = JsonDocument.Parse(Encoding.UTF8.GetString(buffer, 0, result.Count));
        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None);
        return doc;
    }

    [Fact(DisplayName = "capture-loss 1.8: GET /api/v1/status carries the three counters from the provider")]
    public async Task RestStatus_CarriesTheProviderValues()
    {
        var (app, port) = await StartAsync(() => Sample);
        try
        {
            using var doc = await GetRestStatusAsync(port);
            doc.RootElement.GetProperty("captureOverrunCount").GetInt64().Should().Be(7);
            doc.RootElement.GetProperty("captureOverrunReportedMs").GetInt64().Should().Be(1234);
            doc.RootElement.GetProperty("captureChannelDroppedChunks").GetInt64().Should().Be(55);
        }
        finally { await app.StopAsync(); await app.DisposeAsync(); }
    }

    [Fact(DisplayName = "capture-loss 1.8: the initial WebSocket status event carries the three counters from the provider")]
    public async Task WebSocketStatus_CarriesTheProviderValues()
    {
        var (app, port) = await StartAsync(() => Sample);
        try
        {
            using var doc = await GetInitialWsStatusAsync(port);
            doc.RootElement.GetProperty("type").GetString().Should().Be("status");
            var payload = doc.RootElement.GetProperty("payload");
            payload.GetProperty("captureOverrunCount").GetInt64().Should().Be(7);
            payload.GetProperty("captureOverrunReportedMs").GetInt64().Should().Be(1234);
            payload.GetProperty("captureChannelDroppedChunks").GetInt64().Should().Be(55);
        }
        finally { await app.StopAsync(); await app.DisposeAsync(); }
    }

    [Fact(DisplayName = "capture-loss 1.8: with no provider all three counters read 0 on both surfaces")]
    public async Task NoProvider_AllCountersReadZero_OnBothSurfaces()
    {
        var (app, port) = await StartAsync(provider: null);
        try
        {
            using var rest = await GetRestStatusAsync(port);
            using var ws   = await GetInitialWsStatusAsync(port);
            var payload = ws.RootElement.GetProperty("payload");
            foreach (var name in new[] { "captureOverrunCount", "captureOverrunReportedMs", "captureChannelDroppedChunks" })
            {
                rest.RootElement.GetProperty(name).GetInt64().Should().Be(0, $"REST {name}");
                payload.GetProperty(name).GetInt64().Should().Be(0, $"WebSocket {name}");
            }
        }
        finally { await app.StopAsync(); await app.DisposeAsync(); }
    }
}
