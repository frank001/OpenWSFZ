using System.Net;
using System.Text.Json;
using FluentAssertions;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>Integration tests covering the HTTP API and loopback-bind guarantee.</summary>
public sealed class StatusAndBindingTests : IClassFixture<WebTestFactory>
{
    private readonly HttpClient _client;
    private readonly WebTestFactory _factory;

    public StatusAndBindingTests(WebTestFactory factory)
    {
        _factory = factory;
        _client  = factory.CreateClient(new WebApplicationFactoryClientOptions
        {
            BaseAddress = new Uri($"http://127.0.0.1"),
            AllowAutoRedirect = false,
        });
    }

    [Fact(DisplayName = "FR-002, NFR-004: GET / returns index page on loopback")]
    public async Task GetRoot_Returns200WithHtmlBody()
    {
        var response = await _client.GetAsync("/");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        response.Content.Headers.ContentType?.MediaType.Should().Be("text/html");

        var body = await response.Content.ReadAsStringAsync();
        body.Should().Contain("<html", "the response body must be an HTML page");
    }

    [Fact(DisplayName = "FR-002: GET /api/v1/status returns DaemonStatus JSON")]
    public async Task GetStatus_Returns200WithJson()
    {
        var response = await _client.GetAsync("/api/v1/status");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        response.Content.Headers.ContentType?.MediaType.Should().Be("application/json");

        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("state").GetString().Should().Be("Running");
    }

    [Fact(DisplayName = "NFR-004: Kestrel listener address is 127.0.0.1")]
    public async Task ServerAddresses_AreLoopbackOnly()
    {
        // Hit any endpoint to ensure the server is started.
        await _client.GetAsync("/api/v1/status");

        var addresses = _factory.Server.Features
            .Get<Microsoft.AspNetCore.Hosting.Server.Features.IServerAddressesFeature>()
            ?.Addresses ?? [];

        foreach (var addr in addresses)
        {
            var uri = new Uri(addr);
            var ip = System.Net.IPAddress.Parse(uri.Host);
            System.Net.IPAddress.IsLoopback(ip).Should()
                .BeTrue($"Kestrel bound to {addr} but NFR-004 requires loopback only");
        }
    }

    [Fact(DisplayName = "FR-002: path traversal attempt is rejected")]
    public async Task PathTraversal_IsRejected()
    {
        // Some HTTP clients normalise the path before sending; use a raw request.
        using var request = new HttpRequestMessage(HttpMethod.Get, "/..%2F..%2Fsome-file");
        var response = await _client.SendAsync(request);

        var sc = (int)response.StatusCode;
        sc.Should().Match(s => s == 400 || s == 404,
            "path traversal must not return file contents");
    }
}
