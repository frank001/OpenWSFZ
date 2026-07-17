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

/// <summary>Fake <see cref="ICountryFileSource"/> that returns canned XML or throws a canned exception.</summary>
internal sealed class FakeCountryFileSource : ICountryFileSource
{
    private readonly string?                    _xml;
    private readonly CountryFileFetchException? _exception;

    public static FakeCountryFileSource Success(string xml) => new(xml, null);
    public static FakeCountryFileSource Failure(CountryFileFetchException ex) => new(null, ex);

    private FakeCountryFileSource(string? xml, CountryFileFetchException? exception)
    {
        _xml       = xml;
        _exception = exception;
    }

    public Task<string> FetchAsync(CancellationToken cancellationToken = default) =>
        _exception is not null ? throw _exception : Task.FromResult(_xml!);
}

/// <summary>Fake <see cref="ICountryFileConverter"/> that returns canned entries or throws a canned exception.</summary>
internal sealed class FakeCountryFileConverter : ICountryFileConverter
{
    private readonly IReadOnlyList<CallsignRegionEntry>? _entries;
    private readonly CountryFileConversionException?     _exception;

    public static FakeCountryFileConverter Success(IReadOnlyList<CallsignRegionEntry> entries) => new(entries, null);
    public static FakeCountryFileConverter Failure(CountryFileConversionException ex) => new(null, ex);

    private FakeCountryFileConverter(IReadOnlyList<CallsignRegionEntry>? entries, CountryFileConversionException? exception)
    {
        _entries   = entries;
        _exception = exception;
    }

    public IReadOnlyList<CallsignRegionEntry> Convert(string xml, bool prefixBlocksOnly = false) =>
        _exception is not null ? throw _exception : _entries!;
}

/// <summary>
/// In-memory <see cref="ICallsignRegionStore"/> used by region-data-refresh endpoint tests.
/// <see cref="TryGetRegion"/> implements the same longest-prefix-match semantics as
/// <see cref="OpenWSFZ.Daemon.CallsignRegionStore"/> (mirroring
/// <c>FixedCallsignRegionStore</c> in <c>OpenWSFZ.Ft8.Tests</c>) so lookup-endpoint tests exercise
/// real matching, not a stub.
/// </summary>
internal sealed class TestCallsignRegionStore : ICallsignRegionStore
{
    public TestCallsignRegionStore(IReadOnlyList<CallsignRegionEntry>? initialEntries = null) =>
        Entries = initialEntries ?? [];

    public IReadOnlyList<CallsignRegionEntry> Entries { get; private set; }
    public int SaveAsyncCallCount { get; private set; }
    public bool IsSeedData { get; private set; }

    public RegionInfo? TryGetRegion(string callsignToken) => TryMatchPrefix(callsignToken)?.Region;

    public CallsignRegionMatch? TryMatchPrefix(string callsignToken)
    {
        if (string.IsNullOrEmpty(callsignToken)) return null;
        var token = callsignToken.ToUpperInvariant();

        CallsignRegionEntry? best = null;
        foreach (var entry in Entries)
        {
            var len = entry.PrefixStart.Length;
            if (len == 0 || entry.PrefixEnd.Length != len) continue;
            if (token.Length < len) continue;

            var candidate = token[..len];
            if (string.CompareOrdinal(candidate, entry.PrefixStart) < 0 ||
                string.CompareOrdinal(candidate, entry.PrefixEnd) > 0)
                continue;

            if (best is null || len > best.PrefixStart.Length)
                best = entry;
        }

        if (best is null) return null;
        var region = new RegionInfo(best.Continent, best.Entity, best.Synthetic, best.CqZone, best.ItuZone);
        return new CallsignRegionMatch(region, best.PrefixStart.Length);
    }

    public Task SaveAsync(IReadOnlyList<CallsignRegionEntry> entries, CancellationToken cancellationToken = default)
    {
        SaveAsyncCallCount++;
        Entries      = entries;
        IsSeedData   = false; // engagement-target-validation: a successful save is real data.
        return Task.CompletedTask;
    }
}

/// <summary>
/// <see cref="ICallsignRegionStore"/> whose <see cref="SaveAsync"/> always throws
/// <see cref="IOException"/> — used to verify the refresh endpoint's write-failure handling
/// (f-006 §6.2/§2.4: <c>SaveAsync</c> must be wrapped the same way as the fetch/convert steps).
/// </summary>
internal sealed class FailingSaveCallsignRegionStore : ICallsignRegionStore
{
    public IReadOnlyList<CallsignRegionEntry> Entries => [];
    public bool IsSeedData => true;

    public RegionInfo? TryGetRegion(string callsignToken) => null;
    public CallsignRegionMatch? TryMatchPrefix(string callsignToken) => null;

    public Task SaveAsync(IReadOnlyList<CallsignRegionEntry> entries, CancellationToken cancellationToken = default)
        => throw new IOException("simulated disk write failure");
}

// ── POST /api/v1/region-data/refresh (region-lookup-data-refresh, f-006) ─────

[Trait("Category", "Integration")]
public sealed class RegionDataRefreshApiTests
{
    private static async Task<(Microsoft.AspNetCore.Builder.WebApplication App, HttpClient Client)> StartAppAsync(
        Action<IServiceCollection> configureServices)
    {
        var app = OpenWSFZ.Web.WebApp.Create(
            port:              0,
            configStore:       new TestConfigStore(),
            configureServices: configureServices);

        await app.StartAsync();
        var feature = app.Services.GetRequiredService<IServer>()
                         .Features.Get<IServerAddressesFeature>()!;
        var client = new HttpClient
        {
            BaseAddress = new Uri($"http://127.0.0.1:{new Uri(feature.Addresses.First()).Port}")
        };
        return (app, client);
    }

    [Fact(DisplayName = "f-006 3.6: successful refresh replaces region data and returns 200 with entry count")]
    public async Task Refresh_Success_ReturnsOkAndSavesEntries()
    {
        var regionStore = new TestCallsignRegionStore();
        var converted = new List<CallsignRegionEntry>
        {
            new("Q9", "Q9", "Fictional Land", "EU", 40, 41, Synthetic: false),
            new("VER20260629", "VER20260629", "Fictional Marker", "NA", 1, 2, Synthetic: false),
        };

        var (app, client) = await StartAppAsync(services =>
        {
            services.AddSingleton<ICountryFileSource>(FakeCountryFileSource.Success("<plist/>"));
            services.AddSingleton<ICountryFileConverter>(FakeCountryFileConverter.Success(converted));
            services.AddSingleton<ICallsignRegionStore>(regionStore);
        });

        try
        {
            var response = await client.PostAsync("/api/v1/region-data/refresh", content: null);

            response.StatusCode.Should().Be(HttpStatusCode.OK);
            regionStore.SaveAsyncCallCount.Should().Be(1);
            regionStore.Entries.Should().HaveCount(2);

            var body = await response.Content.ReadFromJsonAsync<JsonElement>();
            body.GetProperty("success").GetBoolean().Should().BeTrue();
            body.GetProperty("entryCount").GetInt32().Should().Be(2);
            body.GetProperty("releaseVersion").GetString().Should().Be("20260629");
        }
        finally
        {
            await app.StopAsync();
            await app.DisposeAsync();
        }
    }

    [Fact(DisplayName = "f-006 3.6: fetch failure returns a non-success response and does not touch region data")]
    public async Task Refresh_FetchFailure_ReturnsNonSuccessAndDoesNotSave()
    {
        var regionStore = new TestCallsignRegionStore();

        var (app, client) = await StartAppAsync(services =>
        {
            services.AddSingleton<ICountryFileSource>(
                FakeCountryFileSource.Failure(new CountryFileFetchException("simulated fetch failure")));
            services.AddSingleton<ICountryFileConverter>(
                FakeCountryFileConverter.Success([])); // must not even be reached
            services.AddSingleton<ICallsignRegionStore>(regionStore);
        });

        try
        {
            var response = await client.PostAsync("/api/v1/region-data/refresh", content: null);

            ((int)response.StatusCode).Should().BeGreaterThanOrEqualTo(400,
                "a fetch failure must be reported as a non-success response");
            regionStore.SaveAsyncCallCount.Should().Be(0, "existing region data must be left untouched");
        }
        finally
        {
            await app.StopAsync();
            await app.DisposeAsync();
        }
    }

    [Fact(DisplayName = "f-006 3.6: conversion failure returns a non-success response and does not touch region data")]
    public async Task Refresh_ConversionFailure_ReturnsNonSuccessAndDoesNotSave()
    {
        var regionStore = new TestCallsignRegionStore();

        var (app, client) = await StartAppAsync(services =>
        {
            services.AddSingleton<ICountryFileSource>(FakeCountryFileSource.Success("<plist/>"));
            services.AddSingleton<ICountryFileConverter>(
                FakeCountryFileConverter.Failure(new CountryFileConversionException("simulated conversion failure")));
            services.AddSingleton<ICallsignRegionStore>(regionStore);
        });

        try
        {
            var response = await client.PostAsync("/api/v1/region-data/refresh", content: null);

            ((int)response.StatusCode).Should().BeGreaterThanOrEqualTo(400,
                "a conversion failure must be reported as a non-success response");
            regionStore.SaveAsyncCallCount.Should().Be(0, "existing region data must be left untouched");
        }
        finally
        {
            await app.StopAsync();
            await app.DisposeAsync();
        }
    }

    [Fact(DisplayName = "f-006 §6.2: a SaveAsync failure is logged/reported the same way as fetch and conversion failures")]
    public async Task Refresh_SaveAsyncFailure_ReturnsNonSuccess()
    {
        var converted = new List<CallsignRegionEntry>
        {
            new("Q9", "Q9", "Fictional Land", "EU", 40, 41, Synthetic: false),
        };

        var (app, client) = await StartAppAsync(services =>
        {
            services.AddSingleton<ICountryFileSource>(FakeCountryFileSource.Success("<plist/>"));
            services.AddSingleton<ICountryFileConverter>(FakeCountryFileConverter.Success(converted));
            services.AddSingleton<ICallsignRegionStore>(new FailingSaveCallsignRegionStore());
        });

        try
        {
            var response = await client.PostAsync("/api/v1/region-data/refresh", content: null);

            ((int)response.StatusCode).Should().BeGreaterThanOrEqualTo(400,
                "a SaveAsync failure must be reported as a non-success response, not an unhandled 500");
        }
        finally
        {
            await app.StopAsync();
            await app.DisposeAsync();
        }
    }
}

// ── GET /api/v1/region-data/status (f-006 §6.1) ──────────────────────────────

[Trait("Category", "Integration")]
public sealed class RegionDataStatusApiTests
{
    private static async Task<(Microsoft.AspNetCore.Builder.WebApplication App, HttpClient Client, TestCallsignRegionStore Store)> StartAppAsync(
        IReadOnlyList<CallsignRegionEntry>? initialEntries = null,
        ICountryFileSource?    source    = null,
        ICountryFileConverter? converter = null)
    {
        var regionStore = new TestCallsignRegionStore(initialEntries);

        var app = OpenWSFZ.Web.WebApp.Create(
            port:              0,
            configStore:       new TestConfigStore(),
            configureServices: services =>
            {
                services.AddSingleton<ICountryFileSource>(
                    source ?? FakeCountryFileSource.Failure(new CountryFileFetchException("unused")));
                services.AddSingleton<ICountryFileConverter>(
                    converter ?? FakeCountryFileConverter.Success([]));
                services.AddSingleton<ICallsignRegionStore>(regionStore);
            });

        await app.StartAsync();
        var feature = app.Services.GetRequiredService<IServer>()
                         .Features.Get<IServerAddressesFeature>()!;
        var client = new HttpClient
        {
            BaseAddress = new Uri($"http://127.0.0.1:{new Uri(feature.Addresses.First()).Port}")
        };
        return (app, client, regionStore);
    }

    [Fact(DisplayName = "f-006 §6.1: status before any refresh reflects the active entry count and hasRefreshedThisSession = false")]
    public async Task Status_BeforeAnyRefresh_ReflectsActiveCountAndNoRefreshFlag()
    {
        var seedEntries = new List<CallsignRegionEntry>
        {
            new("3A", "3A", "Monaco", "EU", 14, 27, Synthetic: false),
            new("Q",  "Q",  "Synthetic (R&R Study)", null, null, null, Synthetic: true),
        };
        var (app, client, _) = await StartAppAsync(seedEntries);

        try
        {
            var body = await client.GetFromJsonAsync<JsonElement>("/api/v1/region-data/status");

            body.GetProperty("entryCount").GetInt32().Should().Be(2);
            body.GetProperty("hasRefreshedThisSession").GetBoolean().Should().BeFalse();
            body.GetProperty("lastRefreshUtc").ValueKind.Should().Be(JsonValueKind.Null);
            body.GetProperty("lastRefreshSucceeded").ValueKind.Should().Be(JsonValueKind.Null);
            body.GetProperty("lastReleaseVersion").ValueKind.Should().Be(JsonValueKind.Null);
            body.GetProperty("lastErrorMessage").ValueKind.Should().Be(JsonValueKind.Null);
        }
        finally
        {
            await app.StopAsync();
            await app.DisposeAsync();
        }
    }

    [Fact(DisplayName = "f-006 §6.1: status after a successful refresh reports the new count, release version, and a timestamp")]
    public async Task Status_AfterSuccessfulRefresh_ReportsSuccessDetails()
    {
        var converted = new List<CallsignRegionEntry>
        {
            new("Q9",          "Q9",          "Fictional Land",   "EU", 40, 41, Synthetic: false),
            new("VER20260629", "VER20260629", "Fictional Marker", "NA", 1,  2,  Synthetic: false),
        };
        var (app, client, _) = await StartAppAsync(
            source:    FakeCountryFileSource.Success("<plist/>"),
            converter: FakeCountryFileConverter.Success(converted));

        try
        {
            var refreshResponse = await client.PostAsync("/api/v1/region-data/refresh", content: null);
            refreshResponse.StatusCode.Should().Be(HttpStatusCode.OK);

            var body = await client.GetFromJsonAsync<JsonElement>("/api/v1/region-data/status");

            body.GetProperty("entryCount").GetInt32().Should().Be(2);
            body.GetProperty("hasRefreshedThisSession").GetBoolean().Should().BeTrue();
            body.GetProperty("lastRefreshSucceeded").GetBoolean().Should().BeTrue();
            body.GetProperty("lastReleaseVersion").GetString().Should().Be("20260629");
            body.GetProperty("lastRefreshUtc").ValueKind.Should().Be(JsonValueKind.String);
            body.GetProperty("lastErrorMessage").ValueKind.Should().Be(JsonValueKind.Null);
        }
        finally
        {
            await app.StopAsync();
            await app.DisposeAsync();
        }
    }

    [Fact(DisplayName = "f-006 §6.1: status after a failed refresh reports failure and an error message, without claiming success")]
    public async Task Status_AfterFailedRefresh_ReportsFailureDetails()
    {
        var (app, client, _) = await StartAppAsync(
            source: FakeCountryFileSource.Failure(new CountryFileFetchException("simulated fetch failure")));

        try
        {
            var refreshResponse = await client.PostAsync("/api/v1/region-data/refresh", content: null);
            ((int)refreshResponse.StatusCode).Should().BeGreaterThanOrEqualTo(400);

            var body = await client.GetFromJsonAsync<JsonElement>("/api/v1/region-data/status");

            body.GetProperty("hasRefreshedThisSession").GetBoolean().Should().BeTrue();
            body.GetProperty("lastRefreshSucceeded").GetBoolean().Should().BeFalse();
            body.GetProperty("lastErrorMessage").GetString().Should().Contain("simulated fetch failure");
        }
        finally
        {
            await app.StopAsync();
            await app.DisposeAsync();
        }
    }
}

// ── GET /api/v1/region-data/lookup (f-006 §6.4) ──────────────────────────────

[Trait("Category", "Integration")]
public sealed class RegionDataLookupApiTests
{
    private static readonly IReadOnlyList<CallsignRegionEntry> LookupFixture =
    [
        new("3A", "3A", "Monaco",               "EU", 14, 27, Synthetic: false),
        new("Q",  "Q",  "Synthetic (R&R Study)", null, null, null, Synthetic: true),
    ];

    private static async Task<(Microsoft.AspNetCore.Builder.WebApplication App, HttpClient Client)> StartAppAsync()
    {
        var regionStore = new TestCallsignRegionStore(LookupFixture);

        var app = OpenWSFZ.Web.WebApp.Create(
            port:              0,
            configStore:       new TestConfigStore(),
            configureServices: services =>
            {
                services.AddSingleton<ICountryFileSource>(
                    FakeCountryFileSource.Failure(new CountryFileFetchException("unused")));
                services.AddSingleton<ICountryFileConverter>(FakeCountryFileConverter.Success([]));
                services.AddSingleton<ICallsignRegionStore>(regionStore);
            });

        await app.StartAsync();
        var feature = app.Services.GetRequiredService<IServer>()
                         .Features.Get<IServerAddressesFeature>()!;
        var client = new HttpClient
        {
            BaseAddress = new Uri($"http://127.0.0.1:{new Uri(feature.Addresses.First()).Port}")
        };
        return (app, client);
    }

    [Fact(DisplayName = "f-006 §6.4: lookup resolves a known real prefix, including CQ/ITU zones")]
    public async Task Lookup_KnownPrefix_ResolvesEntityAndZones()
    {
        var (app, client) = await StartAppAsync();

        try
        {
            var body = await client.GetFromJsonAsync<JsonElement>("/api/v1/region-data/lookup?callsign=3A2XYZ");

            body.GetProperty("matched").GetBoolean().Should().BeTrue();
            body.GetProperty("entity").GetString().Should().Be("Monaco");
            body.GetProperty("continent").GetString().Should().Be("EU");
            body.GetProperty("cqZone").GetInt32().Should().Be(14);
            body.GetProperty("ituZone").GetInt32().Should().Be(27);
            body.GetProperty("synthetic").GetBoolean().Should().BeFalse();
        }
        finally
        {
            await app.StopAsync();
            await app.DisposeAsync();
        }
    }

    [Fact(DisplayName = "f-006 §6.4: lookup resolves the synthetic Q-series entry with null zones")]
    public async Task Lookup_SyntheticPrefix_ResolvesSyntheticWithNullZones()
    {
        var (app, client) = await StartAppAsync();

        try
        {
            var body = await client.GetFromJsonAsync<JsonElement>("/api/v1/region-data/lookup?callsign=Q1ABC");

            body.GetProperty("matched").GetBoolean().Should().BeTrue();
            body.GetProperty("synthetic").GetBoolean().Should().BeTrue();
            body.GetProperty("entity").GetString().Should().Be("Synthetic (R&R Study)");
            body.GetProperty("cqZone").ValueKind.Should().Be(JsonValueKind.Null);
            body.GetProperty("ituZone").ValueKind.Should().Be(JsonValueKind.Null);
        }
        finally
        {
            await app.StopAsync();
            await app.DisposeAsync();
        }
    }

    [Fact(DisplayName = "f-006 §6.4: lookup reports no match for an unrecognised prefix")]
    public async Task Lookup_UnmatchedPrefix_ReportsNoMatch()
    {
        var (app, client) = await StartAppAsync();

        try
        {
            var body = await client.GetFromJsonAsync<JsonElement>("/api/v1/region-data/lookup?callsign=ZZ1ABC");

            body.GetProperty("matched").GetBoolean().Should().BeFalse();
            body.GetProperty("entity").ValueKind.Should().Be(JsonValueKind.Null);
            body.GetProperty("continent").ValueKind.Should().Be(JsonValueKind.Null);
            body.GetProperty("synthetic").GetBoolean().Should().BeFalse();
        }
        finally
        {
            await app.StopAsync();
            await app.DisposeAsync();
        }
    }
}
