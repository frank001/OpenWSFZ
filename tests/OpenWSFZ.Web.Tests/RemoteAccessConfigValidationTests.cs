using FluentAssertions;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Net.Http.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Integration tests for the remote-access passphrase validation rule (D-LAN-006).
/// Verifies that <c>POST /api/v1/config</c> rejects an enabled remote-access
/// configuration that has no passphrase, and accepts all valid combinations.
/// </summary>
[Trait("Category", "Integration")]
public sealed class RemoteAccessConfigValidationTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public RemoteAccessConfigValidationTests(WebTestFactory factory) => _factory = factory;

    // ── 400 cases ────────────────────────────────────────────────────────────

    [Fact(DisplayName = "D-LAN-006a: POST with remote access enabled and null passphrase returns 400")]
    public async Task PostConfig_RemoteAccessEnabled_NullPassphrase_Returns400()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            RemoteAccess = new RemoteAccessConfig(enabled: true, passphrase: null)
        };

        var response = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest,
            "Enabled remote access with no passphrase must be rejected");

        var body = await response.Content.ReadAsStringAsync();
        body.Should().Contain("passphrase is required",
            "the error message must identify the missing passphrase as the cause");
    }

    [Fact(DisplayName = "D-LAN-006b: POST with remote access enabled and whitespace passphrase returns 400")]
    public async Task PostConfig_RemoteAccessEnabled_WhitespacePassphrase_Returns400()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            RemoteAccess = new RemoteAccessConfig(enabled: true, passphrase: "   ")
        };

        var response = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest,
            "Enabled remote access with a whitespace-only passphrase must be rejected");

        var body = await response.Content.ReadAsStringAsync();
        body.Should().Contain("passphrase is required",
            "the error message must identify the missing passphrase as the cause");
    }

    // ── 200 cases ────────────────────────────────────────────────────────────

    [Fact(DisplayName = "D-LAN-006c: POST with remote access enabled and valid passphrase returns 200")]
    public async Task PostConfig_RemoteAccessEnabled_ValidPassphrase_Returns200()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            RemoteAccess = new RemoteAccessConfig(enabled: true, passphrase: "hunter2")
        };

        var response = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        response.StatusCode.Should().Be(HttpStatusCode.OK,
            "Enabled remote access with a non-empty passphrase must be accepted");
    }

    [Fact(DisplayName = "D-LAN-006d: POST with remote access disabled and null passphrase returns 200")]
    public async Task PostConfig_RemoteAccessDisabled_NullPassphrase_Returns200()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            RemoteAccess = new RemoteAccessConfig(enabled: false, passphrase: null)
        };

        var response = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        response.StatusCode.Should().Be(HttpStatusCode.OK,
            "Disabled remote access without a passphrase is a valid configuration");
    }
}
