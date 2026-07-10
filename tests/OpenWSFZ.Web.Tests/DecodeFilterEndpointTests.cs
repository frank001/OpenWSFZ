using System.Net;
using System.Net.Http.Json;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using FluentAssertions;
using OpenWSFZ.Abstractions;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Integration tests for <c>GET</c>/<c>POST /api/v1/decode-filter</c>
/// (<c>decode-panel-filtering</c> capability, task 2.4).
/// </summary>
[Trait("Category", "Integration")]
public sealed class DecodeFilterEndpointTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public DecodeFilterEndpointTests(WebTestFactory factory) => _factory = factory;

    [Fact(DisplayName = "GET /api/v1/decode-filter returns the unfiltered default on a fresh daemon")]
    public async Task GetDecodeFilter_FreshDaemon_ReturnsUnfilteredDefault()
    {
        // Deliberately a standalone factory instance (not the shared _factory fixture): the
        // shared fixture's DecodeFilterStore singleton is mutated by the POST tests below, and
        // xUnit does not guarantee test execution order within a class — this test must observe
        // a genuinely fresh store, not whatever the shared fixture happens to hold at the time.
        using var freshFactory = new WebTestFactory();
        var client = freshFactory.CreateClient();

        var response = await client.GetAsync("/api/v1/decode-filter");
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var json = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);

        foreach (var axis in new[]
                 {
                     "allowedEntities", "allowedContinents", "allowedCqZones", "allowedItuZones",
                     "contactStates", "countryStates", "continentStates", "cqZoneStates", "ituZoneStates",
                 })
        {
            doc.RootElement.TryGetProperty(axis, out var prop).Should().BeTrue($"axis '{axis}' must be present");
            prop.ValueKind.Should().Be(JsonValueKind.Null, $"axis '{axis}' must default to null (no restriction)");
        }
    }

    [Fact(DisplayName = "POST /api/v1/decode-filter updates the store and is reflected on the next GET")]
    public async Task PostDecodeFilter_UpdatesStore_ReflectedOnNextGet()
    {
        var client = _factory.CreateClient();

        var payload = new
        {
            allowedEntities = new[] { "Monaco" },
            contactStates   = new[] { "never" },
        };
        var postResponse = await client.PostAsJsonAsync("/api/v1/decode-filter", payload);
        postResponse.StatusCode.Should().Be(HttpStatusCode.OK);

        var getResponse = await client.GetAsync("/api/v1/decode-filter");
        getResponse.StatusCode.Should().Be(HttpStatusCode.OK);

        var json = await getResponse.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);

        doc.RootElement.GetProperty("allowedEntities").EnumerateArray()
            .Select(e => e.GetString()).Should().BeEquivalentTo(["Monaco"]);
        doc.RootElement.GetProperty("contactStates").EnumerateArray()
            .Select(e => e.GetString()).Should().BeEquivalentTo(["never"]);
        doc.RootElement.GetProperty("allowedContinents").ValueKind.Should().Be(JsonValueKind.Null,
            "an axis not included in the POST body must remain unrestricted");
    }

    [Fact(DisplayName = "POST /api/v1/decode-filter with an explicit empty array filters everything on that axis")]
    public async Task PostDecodeFilter_ExplicitEmptyArray_IsDistinctFromNull()
    {
        var client = _factory.CreateClient();

        var payload = new { allowedEntities = Array.Empty<string>() };
        var postResponse = await client.PostAsJsonAsync("/api/v1/decode-filter", payload);
        postResponse.StatusCode.Should().Be(HttpStatusCode.OK);

        var json = await postResponse.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);

        var entities = doc.RootElement.GetProperty("allowedEntities");
        entities.ValueKind.Should().Be(JsonValueKind.Array,
            "an explicit empty selection must round-trip as an empty array, not null");
        entities.GetArrayLength().Should().Be(0);
    }

    [Fact(DisplayName = "A fresh IDecodeFilterStore instance does not retain state from a previous instance")]
    public void FreshStoreInstance_DoesNotRetainPriorState()
    {
        // Simulates a daemon restart: DecodeFilterStore is purely in-memory and always
        // constructed fresh — no persistence layer exists to carry state across instances.
        var first = new DecodeFilterStore();
        first.Set(new DecodeFilterState(AllowedEntities: new HashSet<string> { "Monaco" }));
        first.Current.AllowedEntities.Should().NotBeNull();

        var second = new DecodeFilterStore();
        second.Current.Should().Be(DecodeFilterState.Unfiltered,
            "a freshly constructed store must default to Unfiltered regardless of any prior instance's state");
    }
}

/// <summary>
/// Integration test verifying <c>POST /api/v1/decode-filter</c> broadcasts a
/// <c>decodeFilterChanged</c> WebSocket event to connected clients (task 2.4).
/// Uses <see cref="RealServerFixture"/> because WebSocket upgrades require a real TCP socket.
/// </summary>
[Trait("Category", "Integration")]
public sealed class DecodeFilterWebSocketBroadcastTests : IClassFixture<RealServerFixture>
{
    private readonly RealServerFixture _fixture;

    public DecodeFilterWebSocketBroadcastTests(RealServerFixture fixture) => _fixture = fixture;

    [Fact(DisplayName = "POST /api/v1/decode-filter broadcasts decodeFilterChanged to connected clients")]
    public async Task PostDecodeFilter_BroadcastsDecodeFilterChangedEvent()
    {
        using var ws = new ClientWebSocket();
        await ws.ConnectAsync(new Uri($"ws://127.0.0.1:{_fixture.Port}/api/v1/ws"), CancellationToken.None);

        // Drain the initial status frame.
        await ReadFrameAsync(ws, timeout: TimeSpan.FromSeconds(2));

        using var http = new HttpClient();
        var payload = new { allowedContinents = new[] { "EU" } };
        var response = await http.PostAsJsonAsync(
            $"http://127.0.0.1:{_fixture.Port}/api/v1/decode-filter", payload);
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        string? filterFrame = null;
        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(3);
        while (filterFrame is null && DateTime.UtcNow < deadline)
        {
            var frame = await ReadFrameAsync(ws, timeout: TimeSpan.FromSeconds(2));
            if (frame is null) break;
            using var doc = JsonDocument.Parse(frame);
            if (doc.RootElement.GetProperty("type").GetString() == "decodeFilterChanged")
                filterFrame = frame;
        }

        filterFrame.Should().NotBeNull("decodeFilterChanged frame must be received within the deadline");

        using var filterDoc = JsonDocument.Parse(filterFrame!);
        filterDoc.RootElement.GetProperty("payload").GetProperty("allowedContinents")
            .EnumerateArray().Select(e => e.GetString()).Should().BeEquivalentTo(["EU"]);

        if (ws.State == WebSocketState.Open)
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
