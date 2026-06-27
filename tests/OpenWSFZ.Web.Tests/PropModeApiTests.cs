using FluentAssertions;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

// ── Test double ───────────────────────────────────────────────────────────────

/// <summary>
/// In-memory <see cref="IPropModeStore"/> for prop-mode API tests.
/// Mirrors <see cref="TestFrequencyStore"/> in pattern.
/// </summary>
internal sealed class TestPropModeStore : IPropModeStore
{
    private IReadOnlyList<PropModeEntry> _entries;

    public TestPropModeStore(IReadOnlyList<PropModeEntry>? initial = null)
        => _entries = initial ?? [];

    public IReadOnlyList<PropModeEntry> Entries => _entries;

    public Task SaveAsync(IEnumerable<PropModeEntry> entries, CancellationToken ct = default)
    {
        _entries = entries.ToList();
        return Task.CompletedTask;
    }
}

// ── Integration tests for GET/POST /api/v1/prop-modes (qso-log-dialog, task 3.7) ──

/// <summary>
/// Integration tests for <c>GET /api/v1/prop-modes</c> and
/// <c>POST /api/v1/prop-modes</c> (qso-log-dialog, task 3.7).
///
/// Uses a real Kestrel instance with a <see cref="TestPropModeStore"/> so no
/// file I/O occurs during the tests.
/// </summary>
[Trait("Category", "Integration")]
public sealed class PropModeApiTests : IAsyncLifetime
{
    private static readonly IReadOnlyList<PropModeEntry> DefaultSeed =
    [
        new PropModeEntry("FT8", "",         "Not specified"),
        new PropModeEntry("FT8", "TR",       "Tropospheric Ducting"),
        new PropModeEntry("FT8", "ES",       "Sporadic E"),
        new PropModeEntry("FT8", "F2",       "F2 Reflection"),
        new PropModeEntry("FT8", "EME",      "Earth-Moon-Earth"),
        new PropModeEntry("FT8", "MS",       "Meteor Scatter"),
        new PropModeEntry("FT8", "TEP",      "Trans-Equatorial"),
        new PropModeEntry("FT8", "SAT",      "Satellite"),
        new PropModeEntry("FT8", "LOS",      "Line of Sight"),
        new PropModeEntry("FT8", "INTERNET", "Internet-assisted"),
    ];

    private readonly TestPropModeStore _pmStore;
    private readonly TestConfigStore   _configStore = new();

    private Microsoft.AspNetCore.Builder.WebApplication? _app;
    private HttpClient _client = null!;

    public PropModeApiTests()
    {
        _pmStore = new TestPropModeStore(DefaultSeed);
    }

    public async Task InitializeAsync()
    {
        _app = WebApp.Create(
            port:          0,
            configStore:   _configStore,
            propModeStore: _pmStore);

        await _app.StartAsync();

        var feature = _app.Services
            .GetRequiredService<IServer>()
            .Features.Get<IServerAddressesFeature>()!;

        var port = new Uri(feature.Addresses.First()).Port;
        _client = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{port}") };
    }

    public async Task DisposeAsync()
    {
        _client.Dispose();
        if (_app is not null)
        {
            await _app.StopAsync();
            await _app.DisposeAsync();
        }
    }

    // ── GET /api/v1/prop-modes ────────────────────────────────────────────────

    [Fact(DisplayName = "3.7a: GET /api/v1/prop-modes returns default FT8 seed (10 entries)")]
    public async Task GetPropModes_DefaultSeed_ReturnsTenEntries()
    {
        var response = await _client.GetAsync("/api/v1/prop-modes");

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var entries = await response.Content.ReadFromJsonAsync<List<PropModeEntry>>(
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true });

        entries.Should().NotBeNull().And.HaveCount(10);
        entries![0].Value.Should().Be("");             // "not specified"
        entries[1].Value.Should().Be("TR");            // tropospheric
        entries[4].Value.Should().Be("EME");           // earth-moon-earth
    }

    [Fact(DisplayName = "3.7b: GET /api/v1/prop-modes returns empty array when store is empty")]
    public async Task GetPropModes_EmptyStore_ReturnsEmptyArray()
    {
        // Create a separate app with empty store rather than modifying the shared one.
        var emptyStore = new TestPropModeStore([]);
        var emptyApp   = WebApp.Create(
            port:          0,
            configStore:   new TestConfigStore(),
            propModeStore: emptyStore);

        await emptyApp.StartAsync();
        var emptyFeature = emptyApp.Services
            .GetRequiredService<IServer>()
            .Features.Get<IServerAddressesFeature>()!;

        var emptyPort   = new Uri(emptyFeature.Addresses.First()).Port;
        var emptyClient = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{emptyPort}") };

        try
        {
            var response = await emptyClient.GetAsync("/api/v1/prop-modes");
            response.StatusCode.Should().Be(HttpStatusCode.OK);

            var entries = await response.Content.ReadFromJsonAsync<List<PropModeEntry>>(
                new JsonSerializerOptions { PropertyNameCaseInsensitive = true });

            entries.Should().NotBeNull().And.BeEmpty();
        }
        finally
        {
            emptyClient.Dispose();
            await emptyApp.StopAsync();
            await emptyApp.DisposeAsync();
        }
    }

    // ── POST /api/v1/prop-modes ───────────────────────────────────────────────

    [Fact(DisplayName = "3.7c: POST /api/v1/prop-modes replaces list and returns updated entries")]
    public async Task PostPropModes_ValidList_ReplacesAndReturns()
    {
        var newEntries = new[]
        {
            new { protocol = "FT8", value = "ES", description = "Sporadic E" },
            new { protocol = "FT8", value = "F2", description = "F2 Reflection" },
        };

        var body = new StringContent(
            JsonSerializer.Serialize(newEntries),
            Encoding.UTF8,
            "application/json");

        var response = await _client.PostAsync("/api/v1/prop-modes", body);

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var returned = await response.Content.ReadFromJsonAsync<List<PropModeEntry>>(
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true });

        returned.Should().NotBeNull().And.HaveCount(2);
        returned![0].Value.Should().Be("ES");
        returned[1].Value.Should().Be("F2");

        // The in-memory store should also reflect the update.
        _pmStore.Entries.Should().HaveCount(2);
        _pmStore.Entries[0].Value.Should().Be("ES");
    }

    [Fact(DisplayName = "3.7d: POST /api/v1/prop-modes with malformed JSON returns 400")]
    public async Task PostPropModes_MalformedJson_Returns400()
    {
        var bad = new StringContent("{not valid}", Encoding.UTF8, "application/json");
        var response = await _client.PostAsync("/api/v1/prop-modes", bad);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }
}
