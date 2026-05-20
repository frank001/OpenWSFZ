using System.Net;
using FluentAssertions;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Integration tests verifying that all frontend static assets are served
/// with the correct HTTP status codes and Content-Type headers.
///
/// These tests require the <c>web/</c> directory to be present in the test
/// output directory (ensured by the &lt;None&gt; Content glob in the .csproj).
/// </summary>
public sealed class StaticAssetsIntegrationTests : IClassFixture<WebTestFactory>
{
    private readonly HttpClient _client;

    public StaticAssetsIntegrationTests(WebTestFactory factory)
    {
        // Task 9.2: fail early with a useful message if web/ is missing from output,
        // rather than silently returning 404 on every asset request.
        var webDir = Path.Combine(AppContext.BaseDirectory, "web");
        webDir.Should().NotBeNull();
        Directory.Exists(webDir).Should().BeTrue(
            $"the 'web/' directory must exist at '{webDir}' — " +
            $"run 'dotnet build' to trigger the <None CopyToOutputDirectory> glob in the .csproj");

        _client = factory.CreateClient(new WebApplicationFactoryClientOptions
        {
            BaseAddress     = new Uri("http://127.0.0.1"),
            AllowAutoRedirect = true,
        });
    }

    [Fact(DisplayName = "FR-014, FR-015: GET / returns 200 text/html (default file served from disk)")]
    public async Task GetRoot_Returns200Html()
    {
        var response = await _client.GetAsync("/");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        response.Content.Headers.ContentType?.MediaType.Should().Be("text/html");
        var body = await response.Content.ReadAsStringAsync();
        body.Should().Contain("<html", "GET / must serve the index page");
    }

    [Fact(DisplayName = "FR-014, FR-015: GET /index.html returns 200 text/html (plain file on disk)")]
    public async Task GetIndexHtml_Returns200Html()
    {
        var response = await _client.GetAsync("/index.html");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        response.Content.Headers.ContentType?.MediaType.Should().Be("text/html");
    }

    [Fact(DisplayName = "FR-010, FR-014: GET /settings.html returns 200 text/html (settings page reachable)")]
    public async Task GetSettingsHtml_Returns200Html()
    {
        var response = await _client.GetAsync("/settings.html");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        response.Content.Headers.ContentType?.MediaType.Should().Be("text/html");
        var body = await response.Content.ReadAsStringAsync();
        body.Should().Contain("settings",
            because: "settings.html must contain the settings page content");
    }

    [Fact(DisplayName = "FR-012, FR-014: GET /css/app.css returns 200 with dark theme CSS variables")]
    public async Task GetAppCss_Returns200Css()
    {
        var response = await _client.GetAsync("/css/app.css");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        response.Content.Headers.ContentType?.MediaType.Should().Be("text/css");
        var body = await response.Content.ReadAsStringAsync();
        body.Should().Contain("--color-bg", "app.css must define CSS custom properties for the dark theme");
    }

    [Fact(DisplayName = "FR-014, FR-015: GET /js/main.js returns 200 text/javascript (plain file on disk)")]
    public async Task GetMainJs_Returns200JavaScript()
    {
        var response = await _client.GetAsync("/js/main.js");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        // Browsers and Kestrel may return "text/javascript" or "application/javascript".
        var mediaType = response.Content.Headers.ContentType?.MediaType ?? string.Empty;
        mediaType.Should().ContainAny(["text/javascript", "application/javascript"],
            "main.js must be served with a JavaScript content type");
    }

    [Fact(DisplayName = "FR-014, FR-015: GET /js/api.js returns 200 text/javascript (plain file on disk)")]
    public async Task GetApiJs_Returns200JavaScript()
    {
        var response = await _client.GetAsync("/js/api.js");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var mediaType = response.Content.Headers.ContentType?.MediaType ?? string.Empty;
        mediaType.Should().ContainAny(["text/javascript", "application/javascript"]);
    }
}
