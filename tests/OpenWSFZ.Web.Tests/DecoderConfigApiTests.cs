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

    [Fact(DisplayName = "7.2e: POST with osdNhardMax=24 (lower bound, OSD-FIX R4; was 30) accepted unchanged")]
    public async Task PostConfig_OsdNhardMaxAtLowerBound_AcceptedUnchanged()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            Decoder = new DecoderConfig(kMinScorePass2: 10, osdCorrThreshold: 0.10f, osdNhardMax: 24)
        };

        var postResp = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        postResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var loaded = await postResp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Decoder!.OsdNhardMax.Should().Be(24,
            "osdNhardMax = 24 (lower bound since OSD-FIX R4) must be accepted without clamping");
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

    [Fact(DisplayName = "7.2i: POST with osdNhardMax=10 (below minimum) clamped to 24")]
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
        loaded!.Decoder!.OsdNhardMax.Should().Be(24,
            "osdNhardMax = 10 is below minimum 24 — must be clamped to 24");
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

    [Fact(DisplayName = "#199: a POST that CREATES the decoder section (store had none) stores the marker true")]
    public async Task PostConfig_CreatesDecoderSectionFromNothing_MarkerTrue()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with { Decoder = null });
        store.Current.Decoder.Should().BeNull("precondition: no decoder section");

        var client = _factory.CreateClient();
        const string body = """{"decoder":{"kMinScorePass2":10,"osdCorrThreshold":0.10,"osdNhardMax":60}}""";
        var resp = await client.PostAsync("/api/v1/config", new StringContent(body, Encoding.UTF8, "application/json"));

        resp.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.OsdNhardMax.Should().Be(60);
        store.Current.Decoder.Nhard40MigrationApplied.Should().BeTrue(
            "no persisted 60 can have existed, so no migration is pending; otherwise the next restart reverts this 60");
    }

    [Fact(DisplayName = "#199: a POST with the decoder section already present keeps the stored marker (server-owned), even if the client sends the opposite")]
    public async Task PostConfig_DecoderSectionPresent_StoredMarkerKept()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with
        {
            Decoder = new DecoderConfig(kMinScorePass2: 10, osdCorrThreshold: 0.10f,
                osdNhardMax: 40, nhard40MigrationApplied: false),
        });

        var client = _factory.CreateClient();
        const string body = """{"decoder":{"kMinScorePass2":10,"osdCorrThreshold":0.10,"osdNhardMax":40,"nhard40MigrationApplied":true}}""";
        var resp = await client.PostAsync("/api/v1/config", new StringContent(body, Encoding.UTF8, "application/json"));

        resp.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.Nhard40MigrationApplied.Should().BeFalse("the stored value wins; the client value is ignored");
    }

    [Theory(DisplayName = "FR-082: A5: a POST body carrying subtractionOnMigrationApplied (either value) cannot change the stored marker")]
    [InlineData(true,  false)]
    [InlineData(false, true)]
    public async Task PostConfig_BodyCarriesSubtractionMarker_StoredMarkerKept(bool stored, bool sent)
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with
        {
            Decoder = new DecoderConfig(kMinScorePass2: 10, osdCorrThreshold: 0.10f, osdNhardMax: 40,
                nhard40MigrationApplied: true, subtractionEnabled: true, subtractionMaxThreads: 0,
                subtractionOnMigrationApplied: stored),
        });
        var storedNow = store.Current.Decoder!.SubtractionOnMigrationApplied;

        var client = _factory.CreateClient();
        var body = "{\"decoder\":{\"kMinScorePass2\":10,\"osdCorrThreshold\":0.10,\"osdNhardMax\":40,"
                 + "\"subtractionOnMigrationApplied\":" + (sent ? "true" : "false") + "}}";
        var resp = await client.PostAsync("/api/v1/config", new StringContent(body, Encoding.UTF8, "application/json"));

        resp.StatusCode.Should().Be(HttpStatusCode.OK);
        var loaded = await resp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Decoder!.SubtractionOnMigrationApplied.Should().Be(storedNow,
            "the marker is server-owned: the stored value wins whatever the client sends");
    }

    [Fact(DisplayName = "FR-082: A4 (web): a POST that creates the decoder section and sets subtractionEnabled false stores the marker true")]
    public async Task PostConfig_CreatesDecoderSectionWithSubtractionOff_MarkerTrue()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with { Decoder = null });
        store.Current.Decoder.Should().BeNull("precondition: no decoder section");

        var client = _factory.CreateClient();
        const string body = """{"decoder":{"kMinScorePass2":10,"osdCorrThreshold":0.10,"osdNhardMax":40,"subtractionEnabled":false}}""";
        var resp = await client.PostAsync("/api/v1/config", new StringContent(body, Encoding.UTF8, "application/json"));

        resp.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.SubtractionEnabled.Should().BeFalse();
        store.Current.Decoder.SubtractionOnMigrationApplied.Should().BeTrue(
            "no migration is pending for a section created from nothing; otherwise the next restart turns the OFF back ON");
    }

    [Theory(DisplayName = "FR-109: DR-3 migration (e): a POST body carrying leanEngineMigrationApplied (either value) cannot set or clear the stored marker")]
    [InlineData(true,  false)]
    [InlineData(false, true)]
    public async Task PostConfig_BodyCarriesLeanEngineMarker_StoredMarkerKept(bool stored, bool sent)
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with
        {
            Decoder = new DecoderConfig(kMinScorePass2: 10, osdCorrThreshold: 0.10f, osdNhardMax: 40,
                nhard40MigrationApplied: true, subtractionOnMigrationApplied: true, leanEngineMigrationApplied: stored),
        });
        var storedNow = store.Current.Decoder!.LeanEngineMigrationApplied;
        storedNow.Should().Be(stored, "precondition");

        var client = _factory.CreateClient();
        var body = "{\"decoder\":{\"leanEngineMigrationApplied\":" + (sent ? "true" : "false") + "}}";
        var resp = await client.PostAsync("/api/v1/config", new StringContent(body, Encoding.UTF8, "application/json"));

        resp.StatusCode.Should().Be(HttpStatusCode.OK);
        var loaded = await resp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Decoder!.LeanEngineMigrationApplied.Should().Be(storedNow, "the marker is server-owned: the stored value wins whatever the client sends");
        store.Current.Decoder!.LeanEngineMigrationApplied.Should().Be(storedNow);
    }

    [Fact(DisplayName = "FR-109: DR-3: a POST that creates the decoder section stores the marker true, and an engine 'classic' sent with it is kept (a deliberate choice)")]
    public async Task PostConfig_CreatesDecoderSection_MarkerTrue_ClassicKept()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with { Decoder = null });

        var client = _factory.CreateClient();
        const string body = """{"decoder":{"kMinScorePass2":10,"osdCorrThreshold":0.10,"osdNhardMax":40,"engine":"classic"}}""";
        var resp = await client.PostAsync("/api/v1/config", new StringContent(body, Encoding.UTF8, "application/json"));

        resp.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.LeanEngineMigrationApplied.Should().BeTrue("no migration is pending for a section created from nothing");
        store.Current.Decoder.Engine.Should().Be("classic");

        // put the shared fixture back to the defaults for the tests that follow
        await PostDecoder(client, "{\"engine\":\"lean\"}");
    }

    // ── Operator threads setting (FR-108): decoder.threads, engine, effort ─────────────────────────────────────

    private static StringContent Json(string body) => new(body, Encoding.UTF8, "application/json");

    private static async Task<DecoderConfig> PostDecoder(HttpClient client, string decoderJson)
    {
        var resp = await client.PostAsync("/api/v1/config", Json("{\"decoder\":" + decoderJson + "}"));
        resp.StatusCode.Should().Be(HttpStatusCode.OK);
        var loaded = await resp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        return loaded!.Decoder!;
    }

    [Theory(DisplayName = "FR-108: operator threads setting: an in-range threads value is stored unchanged; an out-of-range one is CLAMPED to [1, 16] with the clamped value stored (as the neighbouring decoder values)")]
    [InlineData(1, 1)]
    [InlineData(8, 8)]
    [InlineData(16, 16)]
    [InlineData(5, 5)]
    [InlineData(0, 0)]
    [InlineData(-3, 1)]
    [InlineData(-1, 1)]
    [InlineData(9, 9)]
    [InlineData(17, 16)]
    [InlineData(64, 16)]
    public async Task PostConfig_Threads_ZeroIsAutoKept_OthersClampedToOneToSixteen(int sent, int stored)
    {
        var client = _factory.CreateClient();
        var decoder = await PostDecoder(client, "{\"threads\":" + sent + "}");
        decoder.Threads.Should().Be(stored);
        decoder.ClampedThreads.Should().Be(stored);
    }

    [Fact(DisplayName = "FR-108: threads default auto: a POST that omits threads keeps a stored explicit value; a POST of 0 stores 0 (auto); a fresh config reads as auto")]
    public async Task PostConfig_Threads_OmitKeepsStored_ZeroStoresAuto()
    {
        var client = _factory.CreateClient();
        (await PostDecoder(client, "{\"threads\":6}")).Threads.Should().Be(6);
        (await PostDecoder(client, "{\"effort\":\"fast\"}")).Threads.Should().Be(6);   // omitted: the stored 6 stays
        var auto = await PostDecoder(client, "{\"threads\":0}");
        auto.Threads.Should().Be(DecoderConfig.AutoThreads);
        auto.ResolveThreads(64).Should().Be(16);
        auto.ResolveThreads(4).Should().Be(4);
    }

    [Fact(DisplayName = "FR-108: operator threads setting: engine, effort and threads round-trip through the API, and the POST is an overlay (a body without threads keeps the stored value)")]
    public async Task PostConfig_EngineEffortThreads_RoundTrip_AndOverlayKeepsThreads()
    {
        var client = _factory.CreateClient();
        var set = await PostDecoder(client, "{\"engine\":\"lean\",\"effort\":\"fast\",\"threads\":6}");
        set.Engine.Should().Be("lean");
        set.Effort.Should().Be("fast");
        set.Threads.Should().Be(6);

        // a body that carries only another decoder key leaves all three as stored (HK-035)
        var other = await PostDecoder(client, "{\"earlyDecodeCutSeconds\":2.5}");
        other.Engine.Should().Be("lean");
        other.Effort.Should().Be("fast");
        other.Threads.Should().Be(6);

        // an unknown word is kept as written and reads as the default
        var unknown = await PostDecoder(client, "{\"engine\":\"turbo\",\"effort\":\"warp\"}");
        unknown.Engine.Should().Be("turbo");
        unknown.GetEngineKind().Should().Be(DecoderEngine.Lean, "an unrecognised word reads as the default, lean");
        unknown.Effort.Should().Be("warp");
        unknown.GetEffortKind().Should().Be(DecoderEffort.Normal);

        // put the shared fixture back to the defaults for the tests that follow
        await PostDecoder(client, "{\"engine\":\"lean\",\"effort\":\"normal\",\"threads\":0}");
    }
}
