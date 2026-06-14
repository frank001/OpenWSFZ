using FluentAssertions;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

// ── Test stub ─────────────────────────────────────────────────────────────────

/// <summary><see cref="IAudioOutputDeviceProvider"/> that returns a fixed device list.</summary>
internal sealed class TestAudioOutputProvider : IAudioOutputDeviceProvider
{
    private readonly IReadOnlyList<AudioDeviceInfo> _devices;
    public TestAudioOutputProvider(params AudioDeviceInfo[] devices) => _devices = devices;
    public Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)
        => Task.FromResult(_devices);
}

// ── Fixture ───────────────────────────────────────────────────────────────────

/// <summary>
/// Starts a real Kestrel instance with a controlled <see cref="IAudioOutputDeviceProvider"/>
/// for testing the <c>GET /api/v1/audio/output-devices</c> endpoint.
/// </summary>
public sealed class AudioOutputDevicesFixture : IAsyncLifetime
{
    internal readonly TestAudioOutputProvider OutputProvider = new(
        new AudioDeviceInfo("{render-guid-1}", "Speakers (Realtek HD Audio)"),
        new AudioDeviceInfo("{render-guid-2}", "Headphones (USB Audio)"));

    private Microsoft.AspNetCore.Builder.WebApplication? _app;

    public HttpClient Client { get; private set; } = null!;

    public async Task InitializeAsync()
    {
        _app = OpenWSFZ.Web.WebApp.Create(
            port:               0,
            audioOutputProvider: OutputProvider);

        await _app.StartAsync();

        var feature = _app.Services
            .GetRequiredService<IServer>()
            .Features.Get<IServerAddressesFeature>()!;

        var addr = feature.Addresses.First();
        Client = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{new Uri(addr).Port}") };
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

// ── Fixture — empty list ──────────────────────────────────────────────────────

/// <summary>
/// Same as <see cref="AudioOutputDevicesFixture"/> but the provider returns an empty list.
/// </summary>
public sealed class AudioOutputDevicesEmptyFixture : IAsyncLifetime
{
    private Microsoft.AspNetCore.Builder.WebApplication? _app;

    public HttpClient Client { get; private set; } = null!;

    public async Task InitializeAsync()
    {
        _app = OpenWSFZ.Web.WebApp.Create(
            port:               0,
            audioOutputProvider: new TestAudioOutputProvider());   // no devices

        await _app.StartAsync();

        var feature = _app.Services
            .GetRequiredService<IServer>()
            .Features.Get<IServerAddressesFeature>()!;

        var addr = feature.Addresses.First();
        Client = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{new Uri(addr).Port}") };
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

/// <summary>
/// Integration tests for <c>GET /api/v1/audio/output-devices</c> (task 8.4).
/// </summary>
public sealed class AudioOutputDevicesEndpointTests : IClassFixture<AudioOutputDevicesFixture>
{
    private readonly HttpClient _client;

    public AudioOutputDevicesEndpointTests(AudioOutputDevicesFixture fixture)
        => _client = fixture.Client;

    // ── Task 8.4 — one device ────────────────────────────────────────────────

    [Fact(DisplayName = "FR-NEW: GET /api/v1/audio/output-devices returns 200 with JSON array of render devices")]
    public async Task GetOutputDevices_Returns200WithDeviceArray()
    {
        var response = await _client.GetAsync("/api/v1/audio/output-devices");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        response.Content.Headers.ContentType?.MediaType.Should().Be("application/json");

        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.ValueKind.Should().Be(JsonValueKind.Array,
            "the endpoint must return a JSON array");

        doc.RootElement.GetArrayLength().Should().Be(2,
            "the fixture wires up two known render devices");

        var first = doc.RootElement[0];
        first.GetProperty("id").GetString().Should().Be("{render-guid-1}");
        first.GetProperty("name").GetString().Should().Be("Speakers (Realtek HD Audio)");
    }
}

/// <summary>
/// Integration test for the empty-list case (task 8.4).
/// </summary>
public sealed class AudioOutputDevicesEmptyEndpointTests : IClassFixture<AudioOutputDevicesEmptyFixture>
{
    private readonly HttpClient _client;

    public AudioOutputDevicesEmptyEndpointTests(AudioOutputDevicesEmptyFixture fixture)
        => _client = fixture.Client;

    // ── Task 8.4 — empty list ────────────────────────────────────────────────

    [Fact(DisplayName = "FR-NEW: GET /api/v1/audio/output-devices returns 200 with empty array when no render devices")]
    public async Task GetOutputDevices_Returns200WithEmptyArray_WhenNoDevices()
    {
        var response = await _client.GetAsync("/api/v1/audio/output-devices");

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.ValueKind.Should().Be(JsonValueKind.Array);
        doc.RootElement.GetArrayLength().Should().Be(0,
            "an empty provider must produce an empty JSON array []");
    }
}
