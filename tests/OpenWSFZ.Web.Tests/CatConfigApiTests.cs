using FluentAssertions;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Integration tests for the CAT configuration REST API (FR-031).
/// Verifies that the <c>cat</c> object (including rigctldHost and rigctldPort)
/// round-trips correctly through GET/POST /api/v1/config.
/// </summary>
[Trait("Category", "Integration")]
public sealed class CatConfigApiTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public CatConfigApiTests(WebTestFactory factory) => _factory = factory;

    // ── GET /api/v1/config includes cat section ───────────────────────────────

    [Fact(DisplayName = "FR-031: GET /api/v1/config response includes cat object")]
    public async Task GetConfig_IncludesCatSection()
    {
        var client   = _factory.CreateClient();
        var response = await client.GetAsync("/api/v1/config");

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var json = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);

        // "cat" key is present (may be null or an object).
        doc.RootElement.TryGetProperty("cat", out _).Should().BeTrue(
            "GET /api/v1/config must always include the cat key");
    }

    // ── POST round-trip (all seven fields) ────────────────────────────────────

    [Fact(DisplayName = "FR-031: POST /api/v1/config with full cat object round-trips all seven fields")]
    public async Task PostConfig_WithFullCatObject_RoundTrips()
    {
        var client  = _factory.CreateClient();

        var payload = new AppConfig() with
        {
            Cat = new CatConfig
            {
                Enabled             = true,
                RigModel            = "RigCtld",
                SerialPort          = "/dev/ttyUSB1",
                BaudRate            = 4800,
                RigctldHost         = "10.0.0.1",
                RigctldPort         = 9999,
                PollIntervalSeconds = 3,
            }
        };

        var postResp = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        postResp.StatusCode.Should().Be(HttpStatusCode.OK);

        // Confirm the GET response reflects the saved values.
        var getResp = await client.GetAsync("/api/v1/config");
        var loaded  = await getResp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);

        loaded.Should().NotBeNull();
        loaded!.Cat.Should().NotBeNull();
        loaded.Cat!.Enabled.Should().BeTrue();
        loaded.Cat.RigModel.Should().Be("RigCtld");
        loaded.Cat.SerialPort.Should().Be("/dev/ttyUSB1");
        loaded.Cat.BaudRate.Should().Be(4800);
        loaded.Cat.RigctldHost.Should().Be("10.0.0.1");
        loaded.Cat.RigctldPort.Should().Be(9999);
        loaded.Cat.PollIntervalSeconds.Should().Be(3);
    }

    // ── pollIntervalSeconds clamping ──────────────────────────────────────────

    [Fact(DisplayName = "FR-031: POST /api/v1/config clamps pollIntervalSeconds > 60 to 60")]
    public async Task PostConfig_PollIntervalTooHigh_IsClamped()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            Cat = new CatConfig { PollIntervalSeconds = 999 }
        };

        var postResp = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        postResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var loaded = await postResp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Cat!.PollIntervalSeconds.Should().Be(60);
    }

    [Fact(DisplayName = "FR-031: POST /api/v1/config clamps pollIntervalSeconds < 1 to 1")]
    public async Task PostConfig_PollIntervalTooLow_IsClamped()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            Cat = new CatConfig { PollIntervalSeconds = 0 }
        };

        var postResp = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        postResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var loaded = await postResp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Cat!.PollIntervalSeconds.Should().Be(1);
    }

    // ── Malformed JSON still returns 400 ─────────────────────────────────────

    [Fact(DisplayName = "FR-031: POST /api/v1/config with malformed JSON returns 400")]
    public async Task PostConfig_MalformedJson_Returns400()
    {
        var client   = _factory.CreateClient();
        var content  = new StringContent("{not valid json", System.Text.Encoding.UTF8,
                                         "application/json");
        var response = await client.PostAsync("/api/v1/config", content);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    // ── POST /api/v1/cat/retry ────────────────────────────────────────────────

    [Fact(DisplayName = "FR-034: POST /api/v1/cat/retry returns 204 No Content")]
    public async Task PostCatRetry_Returns204()
    {
        var client   = _factory.CreateClient();
        var response = await client.PostAsync("/api/v1/cat/retry", null);

        response.StatusCode.Should().Be(HttpStatusCode.NoContent,
            "retry endpoint must acknowledge the request with 204 No Content");
    }

    [Fact(DisplayName = "FR-034: POST /api/v1/cat/retry invokes TriggerRetry on ICatController")]
    public async Task PostCatRetry_InvokesTriggerRetry()
    {
        var client = _factory.CreateClient();
        var before = _factory.CatController.RetryCount;

        await client.PostAsync("/api/v1/cat/retry", null);

        _factory.CatController.RetryCount.Should().Be(before + 1,
            "the endpoint must delegate to ICatController.TriggerRetry()");
    }
}
