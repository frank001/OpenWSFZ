using FluentAssertions;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Net.Http.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Integration tests for the <c>externalReporting.targets[].port</c> validation rule
/// (gridtracker-udp-reporting, <c>specs/configuration/spec.md</c> "Out-of-range port rejected").
/// Verifies that <c>POST /api/v1/config</c> rejects a target whose port falls outside
/// 1–65535 with no partial persistence, and accepts valid configurations.
/// </summary>
[Trait("Category", "Integration")]
public sealed class ExternalReportingConfigValidationTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public ExternalReportingConfigValidationTests(WebTestFactory factory) => _factory = factory;

    [Fact(DisplayName = "POST with target port 70000 returns 400 and does not persist")]
    public async Task PostConfig_TargetPortOutOfRange_Returns400()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget(name: "GridTracker2", host: "127.0.0.1", port: 70000, enabled: true)])
        };

        var response = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest,
            "a target port outside 1-65535 must be rejected");

        // No partial persistence: a fresh GET must not reflect the rejected target.
        var current = await client.GetFromJsonAsync(
            "/api/v1/config", AppJsonContext.Default.AppConfig);
        current!.ExternalReporting.Targets.Should().NotContain(
            t => t.Port == 70000, "a rejected POST must not persist any part of its payload");
    }

    [Fact(DisplayName = "POST with target port 0 returns 400")]
    public async Task PostConfig_TargetPortZero_Returns400()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget(name: "GridTracker2", host: "127.0.0.1", port: 0, enabled: true)])
        };

        var response = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact(DisplayName = "POST with a valid target port persists and round-trips")]
    public async Task PostConfig_ValidTarget_Returns200AndPersists()
    {
        var client  = _factory.CreateClient();
        var payload = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget(name: "GridTracker2", host: "127.0.0.1", port: 2237, enabled: true)],
                honourInboundCommands: false)
        };

        var response = await client.PostAsJsonAsync("/api/v1/config", payload,
            AppJsonContext.Default.AppConfig);

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var current = await client.GetFromJsonAsync(
            "/api/v1/config", AppJsonContext.Default.AppConfig);
        current!.ExternalReporting.Enabled.Should().BeTrue();
        current.ExternalReporting.Targets.Should().ContainSingle(t => t.Port == 2237);
    }
}
