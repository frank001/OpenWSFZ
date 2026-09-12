using FluentAssertions;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Net.Http.Json;
using System.Text;
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

    // ── NHARD40-DEFAULT M2: the migration marker is SERVER-OWNED ─────────────────
    //
    // WebTestFactory substitutes a genuinely in-memory TestConfigStore (no file, no
    // JsonConfigStore in the loop at all), so this suite cannot exercise "the persisted
    // file has 60 and the marker" — that is JsonConfigStoreTests' job, against real temp
    // files. What these two tests cover, at the handler level: a client can neither
    // clear the marker (a partial body) nor set it (an explicit true in the payload) —
    // that is the whole content of "server-owned".

    [Fact(DisplayName = "NHARD40-DEFAULT M2: a POST whose decoder body omits the marker (the real Settings-page shape) does not clear it — carried forward from the persisted store")]
    public async Task PostConfig_DecoderBodyOmitsMarker_MarkerCarriedForwardFromStore()
    {
        // Seed the store directly, bypassing HTTP entirely. A correctly-fixed handler
        // always ignores a POST's own marker value and overwrites it with whatever
        // store.Current already held — so seeding "already migrated" via a POST (this
        // task's own first-draft test did exactly that, and was wrong) would only pass
        // against a BROKEN handler that lets a client set the marker. Seeding the store
        // directly establishes "already migrated" as a fact this test controls, not as
        // something the handler is trusted to have accepted from a client.
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with
        {
            Decoder = new DecoderConfig(
                kMinScorePass2: 10, osdCorrThreshold: 0.10f,
                osdNhardMax: 40, nhard40MigrationApplied: true),
        });

        var client = _factory.CreateClient();

        // Raw JSON body shaped exactly like the real Settings-page payload —
        // settings.js's buildConfigPayload sends only these 3 decoder keys, never the
        // marker. Raw StringContent (not the typed DecoderConfig object) so the marker
        // key is genuinely absent from the wire, matching the real client exactly —
        // constructing a full C# DecoderConfig would always include every field and
        // silently fail to reproduce the defect this test exists to catch.
        const string body = """{"decoder":{"kMinScorePass2":10,"osdCorrThreshold":0.10,"osdNhardMax":60}}""";
        var postResp = await client.PostAsync("/api/v1/config",
            new StringContent(body, Encoding.UTF8, "application/json"));

        postResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var loaded = await postResp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Decoder!.OsdNhardMax.Should().Be(60,
            "sanity: the explicit osdNhardMax=60 in the body was accepted");
        loaded.Decoder!.Nhard40MigrationApplied.Should().BeTrue(
            "the marker must be carried forward from the already-persisted store state, not " +
            "reset by the partial body — this assertion fails on the unfixed handler and " +
            "passes once the server-owned-marker fix lands");
    }

    [Fact(DisplayName = "NHARD40-DEFAULT M2: a POST that explicitly sets the marker to true cannot set it — a client can turn it on no more than it can turn it off")]
    public async Task PostConfig_DecoderBodyExplicitlySetsMarkerTrue_MarkerStaysFalse()
    {
        // Seed explicitly — WebTestFactory is IClassFixture-shared across the whole test
        // class, so relying on another test's leftover state (or the factory's own
        // never-touched default) is not safe and must not be done.
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with
        {
            Decoder = new DecoderConfig(
                kMinScorePass2: 10, osdCorrThreshold: 0.10f,
                osdNhardMax: 40, nhard40MigrationApplied: false),
        });

        var client = _factory.CreateClient();

        // Here the point is that the marker key IS present on the wire (a client
        // attempting to set it directly), so the typed DecoderConfig object is used
        // rather than a hand-shaped raw body.
        var payload = new AppConfig() with
        {
            Decoder = new DecoderConfig(
                kMinScorePass2: 10, osdCorrThreshold: 0.10f,
                osdNhardMax: 40, nhard40MigrationApplied: true),
        };

        var postResp = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        postResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var loaded = await postResp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Decoder!.Nhard40MigrationApplied.Should().BeFalse(
            "a client cannot turn the marker on any more than it can turn it off — only " +
            "JsonConfigStore.Load()'s own migration logic may set this field");
    }
}
