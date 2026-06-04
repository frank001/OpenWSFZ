using FluentAssertions;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

// ── Shared test helpers ───────────────────────────────────────────────────────

/// <summary>
/// In-memory <see cref="IFrequencyStore"/> used by frequency API tests.
/// </summary>
internal sealed class TestFrequencyStore : IFrequencyStore
{
    private IReadOnlyList<FrequencyEntry> _entries;

    public TestFrequencyStore(IReadOnlyList<FrequencyEntry>? initial = null)
        => _entries = initial ?? [];

    public IReadOnlyList<FrequencyEntry> Entries => _entries;

    public Task SaveAsync(IReadOnlyList<FrequencyEntry> entries, CancellationToken ct = default)
    {
        _entries = entries;
        return Task.CompletedTask;
    }
}

/// <summary>
/// Fake <see cref="ICatState"/> for tune API tests.
/// </summary>
internal sealed class FakeCatStateForTune : ICatState
{
    public FakeCatStateForTune(CatConnectionStatus status, double? freq = null)
    {
        Status           = status;
        DialFrequencyMHz = freq;
    }

    public CatConnectionStatus Status           { get; }
    public double?              DialFrequencyMHz { get; }
}

/// <summary>
/// Spy <see cref="ICatTuner"/> that records calls and optionally throws.
/// </summary>
internal sealed class SpyCatTuner : ICatTuner
{
    private readonly Exception? _throwOn;

    public double?            LastFrequency { get; private set; }
    public int                CallCount     { get; private set; }

    public SpyCatTuner(Exception? throwOn = null) => _throwOn = throwOn;

    public Task SetDialFrequencyAsync(double frequencyMHz, CancellationToken cancellationToken = default)
    {
        CallCount++;
        LastFrequency = frequencyMHz;
        if (_throwOn is not null) throw _throwOn;
        return Task.CompletedTask;
    }
}

// ── Frequency list endpoint tests (FR-042) ───────────────────────────────────

/// <summary>
/// Integration tests for <c>GET /api/v1/frequencies</c> and
/// <c>POST /api/v1/frequencies</c> (FR-042).
/// </summary>
[Trait("Category", "Integration")]
public sealed class FrequencyApiTests : IAsyncLifetime
{
    private readonly TestFrequencyStore _freqStore;
    private readonly TestConfigStore    _configStore = new();
    private Microsoft.AspNetCore.Builder.WebApplication? _app;
    private HttpClient _client = null!;

    public FrequencyApiTests()
    {
        _freqStore = new TestFrequencyStore(
        [
            new FrequencyEntry("FT8",  7.074, "40m"),
            new FrequencyEntry("FT8", 14.074, "20m"),
        ]);
    }

    public async Task InitializeAsync()
    {
        _app = OpenWSFZ.Web.WebApp.Create(
            port:           0,
            configStore:    _configStore,
            frequencyStore: _freqStore);

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

    // ── GET /api/v1/frequencies ───────────────────────────────────────────────

    [Fact(DisplayName = "FR-042: GET /api/v1/frequencies returns full entry list as JSON array")]
    public async Task GetFrequencies_ReturnsEntryList()
    {
        var response = await _client.GetAsync("/api/v1/frequencies");

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var entries = await response.Content.ReadFromJsonAsync<List<FrequencyEntry>>(
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true });

        entries.Should().HaveCount(2);
        entries![0].FrequencyMHz.Should().Be(7.074);
        entries[1].FrequencyMHz.Should().Be(14.074);
    }

    [Fact(DisplayName = "FR-042: GET /api/v1/frequencies returns empty array when store is empty")]
    public async Task GetFrequencies_EmptyStore_ReturnsEmptyArray()
    {
        // Create a fresh app with an empty store.
        var emptyStore = new TestFrequencyStore([]);
        var emptyApp   = OpenWSFZ.Web.WebApp.Create(
            port:           0,
            configStore:    new TestConfigStore(),
            frequencyStore: emptyStore);

        await emptyApp.StartAsync();
        var feature = emptyApp.Services
            .GetRequiredService<IServer>()
            .Features.Get<IServerAddressesFeature>()!;
        using var client = new HttpClient
        {
            BaseAddress = new Uri($"http://127.0.0.1:{new Uri(feature.Addresses.First()).Port}")
        };

        var response = await client.GetAsync("/api/v1/frequencies");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var json = await response.Content.ReadAsStringAsync();
        json.Trim().Should().Be("[]");

        await emptyApp.StopAsync();
        await emptyApp.DisposeAsync();
    }

    // ── POST /api/v1/frequencies ──────────────────────────────────────────────

    [Fact(DisplayName = "FR-042: POST /api/v1/frequencies with valid list returns 200 and persists")]
    public async Task PostFrequencies_ValidList_Returns200AndPersists()
    {
        var payload = new[]
        {
            new { protocol = "FT8",  frequencyMHz = 10.136, description = "30m" },
            new { protocol = "FT8",  frequencyMHz = 21.074, description = "15m" },
            new { protocol = "FT4",  frequencyMHz = 14.080, description = "20m FT4" },
        };

        var response = await _client.PostAsJsonAsync("/api/v1/frequencies", payload);

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        // Store should be updated.
        _freqStore.Entries.Should().HaveCount(3);
        _freqStore.Entries[0].FrequencyMHz.Should().Be(10.136);

        // Response body should match saved list.
        var returned = await response.Content.ReadFromJsonAsync<List<FrequencyEntry>>(
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
        returned.Should().HaveCount(3);
    }

    [Fact(DisplayName = "FR-042: POST /api/v1/frequencies with malformed JSON returns 400")]
    public async Task PostFrequencies_MalformedJson_Returns400()
    {
        var content = new StringContent("{ not valid json !!",
            System.Text.Encoding.UTF8, "application/json");

        var response = await _client.PostAsync("/api/v1/frequencies", content);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);

        // Store must NOT be modified.
        _freqStore.Entries.Should().HaveCount(2, "original entries must be preserved");
    }

    [Fact(DisplayName = "FR-042: POST /api/v1/frequencies with empty array clears the list")]
    public async Task PostFrequencies_EmptyArray_ClearsList()
    {
        var response = await _client.PostAsJsonAsync("/api/v1/frequencies", Array.Empty<object>());

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        _freqStore.Entries.Should().BeEmpty();
    }
}

// ── Tune endpoint tests (FR-045) ─────────────────────────────────────────────

/// <summary>
/// Integration tests for <c>POST /api/v1/tune</c> (FR-045).
/// </summary>
[Trait("Category", "Integration")]
public sealed class TuneApiTests
{
    // ── CAT disabled path ─────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-045: POST /api/v1/tune with CAT disabled updates config and returns 200")]
    public async Task PostTune_CatDisabled_UpdatesConfigAndReturns200()
    {
        var configStore = new TestConfigStore();
        var app = OpenWSFZ.Web.WebApp.Create(
            port:        0,
            configStore: configStore,
            catState:    new FakeCatStateForTune(CatConnectionStatus.Disabled));

        await app.StartAsync();
        var feature = app.Services.GetRequiredService<IServer>()
                        .Features.Get<IServerAddressesFeature>()!;
        using var client = new HttpClient
        {
            BaseAddress = new Uri($"http://127.0.0.1:{new Uri(feature.Addresses.First()).Port}")
        };

        var response = await client.PostAsJsonAsync("/api/v1/tune",
            new { frequencyMHz = 7.074 });

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("effectiveFrequencyMHz").GetDouble()
           .Should().BeApproximately(7.074, 0.0001);

        // Config should be updated.
        configStore.Current.DecodeLog?.DialFrequencyMHz.Should().BeApproximately(7.074, 0.0001);

        await app.StopAsync();
        await app.DisposeAsync();
    }

    [Fact(DisplayName = "FR-045: POST /api/v1/tune with negative frequencyMHz returns 400")]
    public async Task PostTune_NegativeFrequency_Returns400()
    {
        var app = OpenWSFZ.Web.WebApp.Create(
            port:     0,
            catState: new FakeCatStateForTune(CatConnectionStatus.Disabled));

        await app.StartAsync();
        var feature = app.Services.GetRequiredService<IServer>()
                        .Features.Get<IServerAddressesFeature>()!;
        using var client = new HttpClient
        {
            BaseAddress = new Uri($"http://127.0.0.1:{new Uri(feature.Addresses.First()).Port}")
        };

        var response = await client.PostAsJsonAsync("/api/v1/tune",
            new { frequencyMHz = -1.0 });

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);

        await app.StopAsync();
        await app.DisposeAsync();
    }

    [Fact(DisplayName = "FR-045: POST /api/v1/tune with missing frequencyMHz returns 400")]
    public async Task PostTune_MissingFrequency_Returns400()
    {
        var app = OpenWSFZ.Web.WebApp.Create(port: 0);

        await app.StartAsync();
        var feature = app.Services.GetRequiredService<IServer>()
                        .Features.Get<IServerAddressesFeature>()!;
        using var client = new HttpClient
        {
            BaseAddress = new Uri($"http://127.0.0.1:{new Uri(feature.Addresses.First()).Port}")
        };

        // Post a body with no frequencyMHz field.
        var response = await client.PostAsJsonAsync("/api/v1/tune", new { other = "field" });

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);

        await app.StopAsync();
        await app.DisposeAsync();
    }

    // ── CAT active path ───────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-045: POST /api/v1/tune with CAT connected calls tuner and returns 200")]
    public async Task PostTune_CatConnected_CallsTunerAndReturns200()
    {
        var tuner = new SpyCatTuner();

        var app = OpenWSFZ.Web.WebApp.Create(
            port:              0,
            catState:          new FakeCatStateForTune(CatConnectionStatus.Connected, 14.074),
            configureServices: services =>
            {
                // Register the ICatTuner stub so the tune endpoint can resolve it.
                services.AddSingleton<ICatTuner>(tuner);
            });

        await app.StartAsync();
        var feature = app.Services.GetRequiredService<IServer>()
                        .Features.Get<IServerAddressesFeature>()!;
        using var client = new HttpClient
        {
            BaseAddress = new Uri($"http://127.0.0.1:{new Uri(feature.Addresses.First()).Port}")
        };

        var response = await client.PostAsJsonAsync("/api/v1/tune",
            new { frequencyMHz = 7.074 });

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        tuner.CallCount.Should().Be(1);
        tuner.LastFrequency.Should().BeApproximately(7.074, 0.0001);

        await app.StopAsync();
        await app.DisposeAsync();
    }

    [Fact(DisplayName = "FR-045: POST /api/v1/tune — SetDialFrequencyAsync throws returns 502")]
    public async Task PostTune_TunerThrows_Returns502()
    {
        var tuner = new SpyCatTuner(throwOn: new InvalidOperationException("rig not responding"));

        var app = OpenWSFZ.Web.WebApp.Create(
            port:              0,
            catState:          new FakeCatStateForTune(CatConnectionStatus.Connected, 14.074),
            configureServices: services =>
            {
                services.AddSingleton<ICatTuner>(tuner);
            });

        await app.StartAsync();
        var feature = app.Services.GetRequiredService<IServer>()
                        .Features.Get<IServerAddressesFeature>()!;
        using var client = new HttpClient
        {
            BaseAddress = new Uri($"http://127.0.0.1:{new Uri(feature.Addresses.First()).Port}")
        };

        var response = await client.PostAsJsonAsync("/api/v1/tune",
            new { frequencyMHz = 14.074 });

        response.StatusCode.Should().Be(HttpStatusCode.BadGateway);

        await app.StopAsync();
        await app.DisposeAsync();
    }
}
