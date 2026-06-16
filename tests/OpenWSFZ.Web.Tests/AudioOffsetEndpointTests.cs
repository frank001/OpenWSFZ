using FluentAssertions;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Integration tests for the <c>POST /api/v1/audio-offset</c> endpoint.
/// Verifies validation, config persistence, and response body (Tasks 8.3, 8.4).
/// </summary>
[Trait("Category", "Integration")]
public sealed class AudioOffsetEndpointTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public AudioOffsetEndpointTests(WebTestFactory factory) => _factory = factory;

    // ── Task 8.3 — Valid request updates config and returns 200 ──────────────

    [Fact(DisplayName = "Task 8.3: POST /api/v1/audio-offset with valid body returns 200 and accepted values")]
    public async Task PostAudioOffset_ValidBody_Returns200WithAcceptedValues()
    {
        var client = _factory.CreateClient();

        var payload = new { rxHz = 900, txHz = 1500, holdTxFreq = false };
        var response = await client.PostAsJsonAsync("/api/v1/audio-offset", payload);

        response.StatusCode.Should().Be(HttpStatusCode.OK,
            "a valid audio-offset body must return HTTP 200");

        var json = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);

        doc.RootElement.GetProperty("rxHz").GetInt32().Should().Be(900,
            "response rxHz must match the accepted value");
        doc.RootElement.GetProperty("txHz").GetInt32().Should().Be(1500,
            "response txHz must match the accepted value");
        doc.RootElement.GetProperty("holdTxFreq").GetBoolean().Should().BeFalse(
            "response holdTxFreq must match the accepted value");
    }

    [Fact(DisplayName = "Task 8.3: POST /api/v1/audio-offset updates IConfigStore")]
    public async Task PostAudioOffset_ValidBody_UpdatesConfig()
    {
        var client = _factory.CreateClient();

        // POST the audio offset.
        var payload = new { rxHz = 750, txHz = 1200, holdTxFreq = true };
        var postResponse = await client.PostAsJsonAsync("/api/v1/audio-offset", payload);
        postResponse.StatusCode.Should().Be(HttpStatusCode.OK);

        // Verify the config was updated via GET /api/v1/config.
        var getResponse = await client.GetAsync("/api/v1/config");
        getResponse.StatusCode.Should().Be(HttpStatusCode.OK);
        var configJson = await getResponse.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(configJson);

        doc.RootElement.GetProperty("tx").GetProperty("rxAudioOffsetHz").GetInt32()
            .Should().Be(750, "rxAudioOffsetHz must be persisted after POST /api/v1/audio-offset");
        doc.RootElement.GetProperty("tx").GetProperty("txAudioOffsetHz").GetInt32()
            .Should().Be(1200, "txAudioOffsetHz must be persisted after POST /api/v1/audio-offset");
        doc.RootElement.GetProperty("tx").GetProperty("holdTxFreq").GetBoolean()
            .Should().BeTrue("holdTxFreq must be persisted after POST /api/v1/audio-offset");
    }

    // ── Task 8.4 — Out-of-range values rejected with 400 ─────────────────────

    [Theory(DisplayName = "Task 8.4: POST /api/v1/audio-offset with out-of-range rxHz returns 400")]
    [InlineData(-1,   1500)]
    [InlineData(3001, 1500)]
    public async Task PostAudioOffset_OutOfRangeRxHz_Returns400(int rxHz, int txHz)
    {
        var client = _factory.CreateClient();

        var payload  = new { rxHz, txHz, holdTxFreq = false };
        var response = await client.PostAsJsonAsync("/api/v1/audio-offset", payload);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest,
            $"rxHz={rxHz} is out of range [0, 3000] and must return HTTP 400");
    }

    [Theory(DisplayName = "Task 8.4: POST /api/v1/audio-offset with out-of-range txHz returns 400")]
    [InlineData(1500, -1)]
    [InlineData(1500, 3001)]
    public async Task PostAudioOffset_OutOfRangeTxHz_Returns400(int rxHz, int txHz)
    {
        var client = _factory.CreateClient();

        var payload  = new { rxHz, txHz, holdTxFreq = false };
        var response = await client.PostAsJsonAsync("/api/v1/audio-offset", payload);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest,
            $"txHz={txHz} is out of range [0, 3000] and must return HTTP 400");
    }

    [Fact(DisplayName = "Task 8.4: POST /api/v1/audio-offset with boundary values 0 and 3000 returns 200")]
    public async Task PostAudioOffset_BoundaryValues_Returns200()
    {
        var client   = _factory.CreateClient();
        var payload  = new { rxHz = 0, txHz = 3000, holdTxFreq = false };
        var response = await client.PostAsJsonAsync("/api/v1/audio-offset", payload);

        response.StatusCode.Should().Be(HttpStatusCode.OK,
            "boundary values 0 and 3000 are valid and must return HTTP 200");
    }
}
