using FluentAssertions;
using System.Net;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Integration tests for <c>GET /api/v1/serial/ports</c> (FR-038).
/// </summary>
[Trait("Category", "Integration")]
public sealed class SerialPortsApiTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public SerialPortsApiTests(WebTestFactory factory) => _factory = factory;

    // ── GET /api/v1/serial/ports returns HTTP 200 ─────────────────────────────

    [Fact(DisplayName = "FR-038: GET /api/v1/serial/ports returns HTTP 200")]
    public async Task GetSerialPorts_ReturnsOk()
    {
        var client   = _factory.CreateClient();
        var response = await client.GetAsync("/api/v1/serial/ports");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    // ── Content-Type is application/json ─────────────────────────────────────

    [Fact(DisplayName = "FR-038: GET /api/v1/serial/ports returns application/json content type")]
    public async Task GetSerialPorts_ContentTypeIsJson()
    {
        var client   = _factory.CreateClient();
        var response = await client.GetAsync("/api/v1/serial/ports");

        response.Content.Headers.ContentType?.MediaType
            .Should().Be("application/json");
    }

    // ── Response is a JSON array of strings ──────────────────────────────────

    [Fact(DisplayName = "FR-038: GET /api/v1/serial/ports returns a JSON array of strings (may be empty)")]
    public async Task GetSerialPorts_ReturnsStringArray()
    {
        var client   = _factory.CreateClient();
        var response = await client.GetAsync("/api/v1/serial/ports");

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);

        doc.RootElement.ValueKind.Should().Be(JsonValueKind.Array,
            "the response must be a JSON array");

        // Each element must be a string (empty array is also valid on CI runners
        // where no serial ports are present).
        foreach (var element in doc.RootElement.EnumerateArray())
        {
            element.ValueKind.Should().Be(JsonValueKind.String,
                "each port entry must be a JSON string");
        }
    }

    // ── Endpoint does not throw even when GetPortNames() might fail ───────────

    [Fact(DisplayName = "FR-038: GET /api/v1/serial/ports does not return 5xx even in edge environments")]
    public async Task GetSerialPorts_DoesNotThrowFiveHundred()
    {
        var client   = _factory.CreateClient();
        var response = await client.GetAsync("/api/v1/serial/ports");

        // The endpoint catches all exceptions and falls back to an empty array.
        ((int)response.StatusCode).Should().BeLessThan(500,
            "the endpoint must not propagate exceptions to the caller");
    }
}
