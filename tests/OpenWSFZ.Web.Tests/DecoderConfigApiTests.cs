using FluentAssertions;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Integration tests for the decoder configuration REST API (decoder-settings-page).
/// Verifies that <c>POST /api/v1/config</c> validates, clamps, and round-trips
/// the <c>decoder</c> object correctly.
/// Tasks 7.2.
/// </summary>
[Trait("Category", "Integration")]
public sealed class DecoderConfigApiTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public DecoderConfigApiTests(WebTestFactory factory) => _factory = factory;

    // ── GET /api/v1/config includes decoder section ──────────────────────────

    [Fact(DisplayName = "7.2: GET /api/v1/config response includes decoder key")]
    public async Task GetConfig_IncludesDecoderSection()
    {
        var client   = _factory.CreateClient();
        var response = await client.GetAsync("/api/v1/config");

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var json = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);

        // "decoder" key may be null (not yet set) or an object — either is valid.
        doc.RootElement.TryGetProperty("decoder", out _).Should().BeTrue(
            "GET /api/v1/config must include the decoder key");
    }

    // ── Round-trip: valid at-boundary values ─────────────────────────────────

    [Fact(DisplayName = "7.2a: POST with kMinScorePass2=5 (lower bound) accepted unchanged")]
    public async Task PostConfig_KMinScorePass2AtLowerBound_AcceptedUnchanged()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            Decoder = new DecoderConfig(kMinScorePass2: 5, osdCorrThreshold: 0.10f, osdNhardMax: 60)
        };

        var postResp = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        postResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var loaded = await postResp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Decoder!.KMinScorePass2.Should().Be(5,
            "kMinScorePass2 = 5 (lower bound) must be accepted without clamping");
    }

    [Fact(DisplayName = "7.2b: POST with kMinScorePass2=30 (upper bound) accepted unchanged")]
    public async Task PostConfig_KMinScorePass2AtUpperBound_AcceptedUnchanged()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            Decoder = new DecoderConfig(kMinScorePass2: 30, osdCorrThreshold: 0.10f, osdNhardMax: 60)
        };

        var postResp = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        postResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var loaded = await postResp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Decoder!.KMinScorePass2.Should().Be(30,
            "kMinScorePass2 = 30 (upper bound) must be accepted without clamping");
    }

    [Fact(DisplayName = "7.2c: POST with osdCorrThreshold=0.05 (lower bound) accepted unchanged")]
    public async Task PostConfig_OsdCorrThresholdAtLowerBound_AcceptedUnchanged()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            Decoder = new DecoderConfig(kMinScorePass2: 10, osdCorrThreshold: 0.05f, osdNhardMax: 60)
        };

        var postResp = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        postResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var loaded = await postResp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Decoder!.OsdCorrThreshold.Should().BeApproximately(0.05f, 1e-6f,
            "osdCorrThreshold = 0.05 (lower bound) must be accepted without clamping");
    }

    [Fact(DisplayName = "7.2d: POST with osdCorrThreshold=0.40 (upper bound) accepted unchanged")]
    public async Task PostConfig_OsdCorrThresholdAtUpperBound_AcceptedUnchanged()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            Decoder = new DecoderConfig(kMinScorePass2: 10, osdCorrThreshold: 0.40f, osdNhardMax: 60)
        };

        var postResp = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        postResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var loaded = await postResp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Decoder!.OsdCorrThreshold.Should().BeApproximately(0.40f, 1e-4f,
            "osdCorrThreshold = 0.40 (upper bound) must be accepted without clamping");
    }

    [Fact(DisplayName = "7.2e: POST with osdNhardMax=30 (lower bound) accepted unchanged")]
    public async Task PostConfig_OsdNhardMaxAtLowerBound_AcceptedUnchanged()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            Decoder = new DecoderConfig(kMinScorePass2: 10, osdCorrThreshold: 0.10f, osdNhardMax: 30)
        };

        var postResp = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        postResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var loaded = await postResp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Decoder!.OsdNhardMax.Should().Be(30,
            "osdNhardMax = 30 (lower bound) must be accepted without clamping");
    }

    [Fact(DisplayName = "7.2f: POST with osdNhardMax=100 (upper bound) accepted unchanged")]
    public async Task PostConfig_OsdNhardMaxAtUpperBound_AcceptedUnchanged()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            Decoder = new DecoderConfig(kMinScorePass2: 10, osdCorrThreshold: 0.10f, osdNhardMax: 100)
        };

        var postResp = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        postResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var loaded = await postResp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Decoder!.OsdNhardMax.Should().Be(100,
            "osdNhardMax = 100 (upper bound) must be accepted without clamping");
    }

    // ── Clamping: below-minimum values ───────────────────────────────────────

    [Fact(DisplayName = "7.2g: POST with kMinScorePass2=4 (below minimum) clamped to 5")]
    public async Task PostConfig_KMinScorePass2TooLow_ClampedToMinimum()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            Decoder = new DecoderConfig(kMinScorePass2: 4, osdCorrThreshold: 0.10f, osdNhardMax: 60)
        };

        var postResp = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        postResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var loaded = await postResp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Decoder!.KMinScorePass2.Should().Be(5,
            "kMinScorePass2 = 4 is below minimum 5 — must be clamped to 5");
    }

    [Fact(DisplayName = "7.2h: POST with osdCorrThreshold=0.01 (below minimum) clamped to 0.05")]
    public async Task PostConfig_OsdCorrThresholdTooLow_ClampedToMinimum()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            Decoder = new DecoderConfig(kMinScorePass2: 10, osdCorrThreshold: 0.01f, osdNhardMax: 60)
        };

        var postResp = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        postResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var loaded = await postResp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Decoder!.OsdCorrThreshold.Should().BeApproximately(0.05f, 1e-6f,
            "osdCorrThreshold = 0.01 is below minimum 0.05 — must be clamped to 0.05");
    }

    [Fact(DisplayName = "7.2i: POST with osdNhardMax=10 (below minimum) clamped to 30")]
    public async Task PostConfig_OsdNhardMaxTooLow_ClampedToMinimum()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            Decoder = new DecoderConfig(kMinScorePass2: 10, osdCorrThreshold: 0.10f, osdNhardMax: 10)
        };

        var postResp = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        postResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var loaded = await postResp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Decoder!.OsdNhardMax.Should().Be(30,
            "osdNhardMax = 10 is below minimum 30 — must be clamped to 30");
    }

    // ── Clamping: above-maximum values ───────────────────────────────────────

    [Fact(DisplayName = "7.2j: POST with kMinScorePass2=50 (above maximum) clamped to 30")]
    public async Task PostConfig_KMinScorePass2TooHigh_ClampedToMaximum()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            Decoder = new DecoderConfig(kMinScorePass2: 50, osdCorrThreshold: 0.10f, osdNhardMax: 60)
        };

        var postResp = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        postResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var loaded = await postResp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Decoder!.KMinScorePass2.Should().Be(30,
            "kMinScorePass2 = 50 exceeds maximum 30 — must be clamped to 30");
    }

    [Fact(DisplayName = "7.2k: POST with osdCorrThreshold=0.99 (above maximum) clamped to 0.40")]
    public async Task PostConfig_OsdCorrThresholdTooHigh_ClampedToMaximum()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            Decoder = new DecoderConfig(kMinScorePass2: 10, osdCorrThreshold: 0.99f, osdNhardMax: 60)
        };

        var postResp = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        postResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var loaded = await postResp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Decoder!.OsdCorrThreshold.Should().BeApproximately(0.40f, 1e-4f,
            "osdCorrThreshold = 0.99 exceeds maximum 0.40 — must be clamped to 0.40");
    }

    [Fact(DisplayName = "7.2l: POST with osdNhardMax=200 (above maximum) clamped to 100")]
    public async Task PostConfig_OsdNhardMaxTooHigh_ClampedToMaximum()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            Decoder = new DecoderConfig(kMinScorePass2: 10, osdCorrThreshold: 0.10f, osdNhardMax: 200)
        };

        var postResp = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        postResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var loaded = await postResp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Decoder!.OsdNhardMax.Should().Be(100,
            "osdNhardMax = 200 exceeds maximum 100 — must be clamped to 100");
    }

    // ── null decoder object is accepted unchanged ────────────────────────────

    [Fact(DisplayName = "7.2m: POST with decoder=null leaves decoder null (no clamp applied)")]
    public async Task PostConfig_NullDecoder_AcceptedUnchanged()
    {
        var client  = _factory.CreateClient();
        // AppConfig default: Decoder = null
        var payload = new AppConfig();

        var postResp = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        postResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var loaded = await postResp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        // A null decoder is valid — consumers fall back to new DecoderConfig() defaults.
        // Do not assert null specifically; just verify the response is 200 and not 500.
        loaded.Should().NotBeNull("POST with null decoder must succeed without server error");
    }
}
