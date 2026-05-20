using FluentAssertions;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

// ── Test stubs ────────────────────────────────────────────────────────────────

/// <summary>In-memory <see cref="IConfigStore"/> for test isolation.</summary>
internal sealed class TestConfigStore : IConfigStore
{
    private AppConfig _current = new();
    public AppConfig Current => _current;
    public Task SaveAsync(AppConfig config, CancellationToken ct = default)
    {
        _current = config;
        return Task.CompletedTask;
    }
}

/// <summary><see cref="IAudioDeviceProvider"/> that returns a fixed device list.</summary>
internal sealed class TestAudioProvider : IAudioDeviceProvider
{
    private readonly IReadOnlyList<AudioDeviceInfo> _devices;
    public TestAudioProvider(params AudioDeviceInfo[] devices) => _devices = devices;
    public Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)
        => Task.FromResult(_devices);
}

// ── Fixture ───────────────────────────────────────────────────────────────────

/// <summary>
/// Starts a real Kestrel instance via <see cref="WebApp.Create"/> with controlled
/// <see cref="IConfigStore"/> and <see cref="IAudioDeviceProvider"/> services.
/// Used for audio/config integration tests that must not touch the real config file.
/// </summary>
public sealed class AudioConfigFixture : IAsyncLifetime
{
    internal readonly TestConfigStore    ConfigStore   = new();
    internal readonly TestAudioProvider  AudioProvider = new(
        new AudioDeviceInfo("hw:0,0", "HDA Intel PCH"),
        new AudioDeviceInfo("hw:1,0", "USB Audio"));

    private Microsoft.AspNetCore.Builder.WebApplication? _app;

    public HttpClient Client   { get; private set; } = null!;
    public int        Port     { get; private set; }

    public async Task InitializeAsync()
    {
        _app = OpenWSFZ.Web.WebApp.Create(
            port:          0,
            configStore:   ConfigStore,
            audioProvider: AudioProvider);

        await _app.StartAsync();

        var feature = _app.Services
            .GetRequiredService<IServer>()
            .Features.Get<IServerAddressesFeature>()!;

        var addr = feature.Addresses.First();
        Port   = new Uri(addr).Port;
        Client = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{Port}") };
    }

    public async Task DisposeAsync()
    {
        Client.Dispose();
        if (_app is not null)
        {
            await _app.StopAsync();
            await _app.DisposeAsync();
        }
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

/// <summary>Integration tests for the audio-device and config endpoints (P2 tasks 9.1–9.6).</summary>
public sealed class AudioConfigIntegrationTests : IClassFixture<AudioConfigFixture>
{
    private readonly AudioConfigFixture _fixture;
    private readonly HttpClient         _client;

    public AudioConfigIntegrationTests(AudioConfigFixture fixture)
    {
        _fixture = fixture;
        _client  = fixture.Client;
    }

    // ── Task 9.1 ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-003: GET /api/v1/audio/devices returns 200 with JSON array")]
    public async Task GetAudioDevices_Returns200WithJsonArray()
    {
        var response = await _client.GetAsync("/api/v1/audio/devices");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        response.Content.Headers.ContentType?.MediaType.Should().Be("application/json");

        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.ValueKind.Should().Be(JsonValueKind.Array,
            "the endpoint must return a JSON array of audio devices");

        // The fixture wires up two known devices.
        doc.RootElement.GetArrayLength().Should().Be(2);
        var first = doc.RootElement[0];
        first.GetProperty("id").GetString().Should().Be("hw:0,0");
        first.GetProperty("name").GetString().Should().Be("HDA Intel PCH");
    }

    // ── Task 9.2 ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-004: GET /api/v1/config returns 200 with current config")]
    public async Task GetConfig_Returns200WithConfigFields()
    {
        var response = await _client.GetAsync("/api/v1/config");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        response.Content.Headers.ContentType?.MediaType.Should().Be("application/json");

        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);

        // Both fields must be present (values may vary depending on test order).
        doc.RootElement.TryGetProperty("audioDeviceName", out _).Should().BeTrue(
            "audioDeviceName field must be present in the config response");
        doc.RootElement.TryGetProperty("port", out var portProp).Should().BeTrue(
            "port field must be present in the config response");
        portProp.GetInt32().Should().BePositive("port must be a positive integer");
    }

    // ── Task 9.3 ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-004: POST /api/v1/config persists and returns updated config")]
    public async Task PostConfig_PersistsUpdatedConfig_AndSubsequentGetReflectsChange()
    {
        // Reset to known state before this test — the fixture store is shared across tests
        // in the class (IClassFixture) so previous tests may have mutated it.
        await _fixture.ConfigStore.SaveAsync(new AppConfig());

        var payload = """{"audioDeviceName":"NewMic","port":9090}""";
        using var body = new StringContent(payload, Encoding.UTF8, "application/json");

        var postResponse = await _client.PostAsync("/api/v1/config", body);

        postResponse.StatusCode.Should().Be(HttpStatusCode.OK);

        var postBody = await postResponse.Content.ReadAsStringAsync();
        using var postDoc = JsonDocument.Parse(postBody);
        postDoc.RootElement.GetProperty("audioDeviceName").GetString().Should().Be("NewMic");
        postDoc.RootElement.GetProperty("port").GetInt32().Should().Be(9090);

        // Subsequent GET must reflect the persisted values.
        var getResponse = await _client.GetAsync("/api/v1/config");
        var getBody     = await getResponse.Content.ReadAsStringAsync();
        using var getDoc = JsonDocument.Parse(getBody);
        getDoc.RootElement.GetProperty("audioDeviceName").GetString().Should().Be("NewMic");
        getDoc.RootElement.GetProperty("port").GetInt32().Should().Be(9090);
    }

    // ── Task 9.4 ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-004: POST /api/v1/config returns 400 for malformed JSON")]
    public async Task PostConfig_Returns400_ForMalformedJson()
    {
        using var body = new StringContent("{ broken", Encoding.UTF8, "application/json");
        var response = await _client.PostAsync("/api/v1/config", body);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest,
            "a malformed JSON body must be rejected with HTTP 400");
    }

    // ── Task 9.5 ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-002: GET /api/v1/status includes audioDevice field")]
    public async Task GetStatus_IncludesAudioDeviceField()
    {
        var response = await _client.GetAsync("/api/v1/status");

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);

        doc.RootElement.TryGetProperty("audioDevice", out _).Should().BeTrue(
            "the status response must include the audioDevice field (may be null)");

        // Version must not expose raw build metadata.
        doc.RootElement.GetProperty("version").GetString()
            .Should().NotContain("+",
                "the version field must not expose raw build metadata (full git SHA)");
    }

    // ── Task 9.6 ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-002: WebSocket status event payload includes audioDevice field")]
    public async Task WebSocketStatus_PayloadIncludesAudioDeviceField()
    {
        using var ws = new ClientWebSocket();
        await ws.ConnectAsync(
            new Uri($"ws://127.0.0.1:{_fixture.Port}/api/v1/ws"),
            CancellationToken.None);

        ws.State.Should().Be(WebSocketState.Open);

        // Read the initial status frame.
        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(5));
        var buffer = new byte[4096];
        var result = await ws.ReceiveAsync(new ArraySegment<byte>(buffer), cts.Token);
        var frame  = Encoding.UTF8.GetString(buffer, 0, result.Count);

        using var doc = JsonDocument.Parse(frame);
        doc.RootElement.GetProperty("type").GetString().Should().Be("status");

        var payload = doc.RootElement.GetProperty("payload");
        payload.TryGetProperty("audioDevice", out _).Should().BeTrue(
            "the WebSocket status payload must include the audioDevice field (may be null)");

        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None);
    }
}
