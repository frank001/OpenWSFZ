using System.Net;
using System.Text.Json;
using FluentAssertions;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Integration tests for <c>GET /api/v1/decoder/params</c> (decoder-param-readout, shim 20260054,
/// FR-076): the native decoder's parameter table, read-only.
/// <para>
/// Most cases start a small <see cref="WebApp"/> with a FAKE provider, so the test controls exactly
/// what "the native library" says (and can make it throw). One case goes through the real composed
/// daemon (<see cref="WebTestFactory"/>) so the wiring in <c>Program.cs</c> is exercised too.
/// </para>
/// </summary>
[Trait("Category", "Integration")]
public sealed class DecoderParamsEndpointTests : IClassFixture<WebTestFactory>
{
    private const string Route = "/api/v1/decoder/params";
    private const int    FakeShimVersion = 20260054;

    private readonly WebTestFactory _factory;
    public DecoderParamsEndpointTests(WebTestFactory factory) => _factory = factory;

    // ── Host helper ──────────────────────────────────────────────────────────

    private sealed class Host : IAsyncDisposable
    {
        private readonly WebApplication _app;
        public HttpClient Client { get; }

        private Host(WebApplication app, HttpClient client) { _app = app; Client = client; }

        public static async Task<Host> StartAsync(
            Func<IReadOnlyList<DecoderParamEntry>>? provider,
            IConfigStore? store = null,
            Action<IServiceCollection>? configureServices = null)
        {
            var app = WebApp.Create(
                port:                  0,
                configStore:           store,
                configureServices:     configureServices,
                shimVersion:           FakeShimVersion,
                decoderParamsProvider: provider);
            await app.StartAsync();
            var addr = app.Services.GetRequiredService<IServer>().Features.Get<IServerAddressesFeature>()!.Addresses.First();
            return new Host(app, new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{new Uri(addr).Port}") });
        }

        public async ValueTask DisposeAsync()
        {
            Client.Dispose();
            await _app.StopAsync();
            await _app.DisposeAsync();
        }
    }

    private static DecoderParamEntry[] Sample() =>
    [
        new("osd_nhard_max",  DecoderParamKind.Runtime,     40,  60),
        new("osd_corr_threshold", DecoderParamKind.Runtime, 0.1, 0.1),
        new("K_MAX_CANDIDATES", DecoderParamKind.CompileTime, 140, 140),
    ];

    private static async Task<JsonDocument> Json(HttpResponseMessage r)
        => JsonDocument.Parse(await r.Content.ReadAsStringAsync());

    // ── 200: shape, order, values ────────────────────────────────────────────

    [Fact(DisplayName = "FR-076: GET /api/v1/decoder/params returns 200 with shimVersion and every entry as name/kind/value/default, in order")]
    public async Task Get_Returns200_WithShimVersionAndEntries()
    {
        await using var host = await Host.StartAsync(Sample);

        var response = await host.Client.GetAsync(Route);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        response.Content.Headers.ContentType?.MediaType.Should().Be("application/json");
        using var doc = await Json(response);

        doc.RootElement.GetProperty("shimVersion").GetInt32().Should().Be(FakeShimVersion);
        var entries = doc.RootElement.GetProperty("entries").EnumerateArray().ToArray();
        entries.Should().HaveCount(3);
        entries.Select(e => e.GetProperty("name").GetString()).Should().Equal("osd_nhard_max", "osd_corr_threshold", "K_MAX_CANDIDATES");

        var nhard = entries[0];
        nhard.GetProperty("kind").GetString().Should().Be("runtime");
        nhard.GetProperty("value").GetDouble().Should().Be(40);
        nhard.GetProperty("default").GetDouble().Should().Be(60);
        entries[2].GetProperty("kind").GetString().Should().Be("compile-time");
        entries[1].GetProperty("value").GetDouble().Should().Be(0.1, "a float reaches the wire as the number that was set");
    }

    [Fact(DisplayName = "FR-076: the response carries the native decoder's values, NOT app.json's (osd_nhard_max 40 while the config says 55)")]
    public async Task Get_ShowsTheProvidersValues_NotTheConfigs()
    {
        var store = new TestConfigStore();
        await store.SaveAsync(new AppConfig { Decoder = new DecoderConfig { OsdNhardMax = 55 } });

        await using var host = await Host.StartAsync(Sample, store);
        var body = await host.Client.GetStringAsync(Route);

        using var doc = JsonDocument.Parse(body);
        var nhard = doc.RootElement.GetProperty("entries").EnumerateArray().Single(e => e.GetProperty("name").GetString() == "osd_nhard_max");
        nhard.GetProperty("value").GetDouble().Should().Be(40, "the readout is what the native decoder reports");
        body.Should().NotContain("55", "nothing from AppConfig may leak into the readout");
    }

    [Fact(DisplayName = "FR-076: the provider is read on EVERY request and the result is never cached")]
    public async Task Get_ReadsTheProviderOnEveryRequest()
    {
        int calls = 0;
        await using var host = await Host.StartAsync(() =>
        {
            int n = Interlocked.Increment(ref calls);
            return [new DecoderParamEntry("osd_nhard_max", DecoderParamKind.Runtime, n == 1 ? 40 : 55, 60)];
        });

        static double NhardOf(JsonDocument d) =>
            d.RootElement.GetProperty("entries")[0].GetProperty("value").GetDouble();

        using var first  = await Json(await host.Client.GetAsync(Route));
        using var second = await Json(await host.Client.GetAsync(Route));

        NhardOf(first).Should().Be(40);
        NhardOf(second).Should().Be(55, "a value changed natively between requests must be visible: no cache");
        calls.Should().Be(2);
    }

    // ── 405: read-only ───────────────────────────────────────────────────────

    [Theory(DisplayName = "FR-076: every mutating verb on the route returns 405")]
    [InlineData("POST")]
    [InlineData("PUT")]
    [InlineData("PATCH")]
    [InlineData("DELETE")]
    public async Task MutatingVerbs_Return405(string verb)
    {
        int calls = 0;
        await using var host = await Host.StartAsync(() => { Interlocked.Increment(ref calls); return Sample(); });

        using var request = new HttpRequestMessage(new HttpMethod(verb), Route) { Content = new StringContent("{}") };
        var response = await host.Client.SendAsync(request);

        response.StatusCode.Should().Be(HttpStatusCode.MethodNotAllowed, $"{verb} must not be accepted on a read-only route");
        calls.Should().Be(0, "a rejected verb must never reach the native library");
    }

    // ── 503: an unavailable native library is an error, never an empty table ─

    [Fact(DisplayName = "FR-076: a provider that throws yields 503 with a message, never an empty table")]
    public async Task ProviderThrows_Returns503_NotAnEmptyTable()
    {
        await using var host = await Host.StartAsync(() => throw new DllNotFoundException("libft8 could not be loaded"));

        var response = await host.Client.GetAsync(Route);
        var body = await response.Content.ReadAsStringAsync();

        response.StatusCode.Should().Be(HttpStatusCode.ServiceUnavailable);
        body.Should().Contain("libft8 could not be loaded", "the caller is told WHY");
        body.Should().NotContain("\"entries\"", "an empty table would read as 'the decoder has no parameters'");
    }

    [Fact(DisplayName = "FR-076: no provider wired (a minimal fixture) yields 503, not an empty table")]
    public async Task NoProvider_Returns503()
    {
        await using var host = await Host.StartAsync(provider: null);

        var response = await host.Client.GetAsync(Route);

        response.StatusCode.Should().Be(HttpStatusCode.ServiceUnavailable);
        (await response.Content.ReadAsStringAsync()).Should().NotContain("\"entries\"");
    }

    [Fact(DisplayName = "FR-076: a provider that returns NO parameters yields 503, not an empty table")]
    public async Task ProviderReturnsEmpty_Returns503()
    {
        await using var host = await Host.StartAsync(() => []);

        var response = await host.Client.GetAsync(Route);

        response.StatusCode.Should().Be(HttpStatusCode.ServiceUnavailable);
        (await response.Content.ReadAsStringAsync()).Should().NotContain("\"entries\"");
    }

    // ── authentication: the same as the other /api/v1 routes ─────────────────

    private sealed class SpoofRemoteIpFilter(IPAddress ip) : IStartupFilter
    {
        public Action<IApplicationBuilder> Configure(Action<IApplicationBuilder> next) => pipeline =>
        {
            pipeline.Use(async (ctx, n) => { ctx.Connection.RemoteIpAddress = ip; await n(ctx); });
            next(pipeline);
        };
    }

    [Fact(DisplayName = "FR-076: the route is behind the same authentication as the other /api/v1 routes (401 without the key, 200 with it)")]
    public async Task Route_IsBehindTheSameAuthentication()
    {
        await using var host = await Host.StartAsync(Sample, configureServices: services =>
        {
            services.AddSingleton<IAuthPolicy>(new PassphraseAuthPolicy("secret"));
            services.AddTransient<IStartupFilter>(_ => new SpoofRemoteIpFilter(IPAddress.Parse("192.168.1.99")));
        });

        // the reference route, to prove the rig really is enforcing auth for a non-loopback caller
        (await host.Client.GetAsync("/api/v1/status")).StatusCode.Should().Be(HttpStatusCode.Unauthorized);

        (await host.Client.GetAsync(Route)).StatusCode.Should().Be(HttpStatusCode.Unauthorized,
            "the decoder table must not be readable by an unauthenticated non-loopback caller");

        using var withKey = new HttpRequestMessage(HttpMethod.Get, Route);
        withKey.Headers.Add("X-Api-Key", "secret");
        (await host.Client.SendAsync(withKey)).StatusCode.Should().Be(HttpStatusCode.OK);
    }

    // ── end to end through Program.cs ────────────────────────────────────────

    [Fact(DisplayName = "FR-076: through the composed daemon the endpoint serves the REAL native table (osd_nhard_max default 60) and the same shimVersion as /api/v1/status")]
    public async Task ComposedDaemon_ServesTheRealNativeTable()
    {
        using var client = _factory.CreateClient(new WebApplicationFactoryClientOptions { BaseAddress = new Uri("http://127.0.0.1") });

        var response = await client.GetAsync(Route);
        response.StatusCode.Should().Be(HttpStatusCode.OK,
            "Program.cs must wire decoderParamsProvider to the real decoder (a 503 here means it is not wired)");
        using var doc = await Json(response);
        using var status = JsonDocument.Parse(await client.GetStringAsync("/api/v1/status"));

        doc.RootElement.GetProperty("shimVersion").GetInt32().Should().BeGreaterThanOrEqualTo(20260054)
            .And.Be(status.RootElement.GetProperty("shimVersion").GetInt32());

        var entries = doc.RootElement.GetProperty("entries").EnumerateArray().ToArray();
        entries.Select(e => e.GetProperty("kind").GetString()).Distinct().Should().BeEquivalentTo("runtime", "compile-time");
        entries.Where(e => e.GetProperty("kind").GetString() == "runtime").Select(e => e.GetProperty("name").GetString())
               .Should().Contain(["k_min_score_pass2", "osd_corr_threshold", "osd_nhard_max", "supp_snr_min_db", "supp_snr_max_db", "supp_side_weight"]);

        var nhard = entries.Single(e => e.GetProperty("name").GetString() == "osd_nhard_max");
        nhard.GetProperty("default").GetDouble().Should().Be(60, "the compiled-in default, whatever the daemon applied on top");
        entries.Single(e => e.GetProperty("name").GetString() == "K_MAX_PASSES").GetProperty("value").GetDouble().Should().Be(2);
    }
}
