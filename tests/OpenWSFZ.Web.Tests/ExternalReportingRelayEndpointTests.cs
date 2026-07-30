using FluentAssertions;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Net.Http.Json;
using System.Text;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Integration tests for <c>POST /api/v1/external-reporting/relay</c>
/// (<c>external-reporting-single-connection</c>, tasks 3.1/3.3). <see cref="WebTestFactory"/> boots
/// the real <c>OpenWSFZ.Daemon</c> startup, so <c>ExternalReportingService</c> is genuinely wired up
/// as <see cref="IExternalReportingRelayTarget"/> here — these tests exercise the real gating logic,
/// not a test double.
/// </summary>
[Trait("Category", "Integration")]
public sealed class ExternalReportingRelayEndpointTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public ExternalReportingRelayEndpointTests(WebTestFactory factory) => _factory = factory;

    private static async Task ResetExternalReportingAsync(HttpClient client) =>
        await client.PostAsJsonAsync("/api/v1/config",
            new AppConfig() with { ExternalReporting = new ExternalReportingConfig() },
            AppJsonContext.Default.AppConfig);

    [Fact(DisplayName =
        "FR-065: relay endpoint returns 503 and sends nothing when externalReporting is disabled (default)")]
    public async Task PostRelay_Returns503_WhenDisabled()
    {
        var client = _factory.CreateClient();
        await ResetExternalReportingAsync(client);

        var body = new RelayBatchRequest("Follower1",
            [new RelayDatagramDto("Heartbeat", Convert.ToBase64String("fake"u8.ToArray()))]);

        var response = await client.PostAsJsonAsync(
            "/api/v1/external-reporting/relay", body, AppJsonContext.Default.RelayBatchRequest);

        response.StatusCode.Should().Be(HttpStatusCode.ServiceUnavailable);
    }

    [Fact(DisplayName = "FR-065: relay endpoint returns 503 when this instance's own role is not \"leader\"")]
    public async Task PostRelay_Returns503_WhenRoleIsFollower()
    {
        var client = _factory.CreateClient();
        try
        {
            await client.PostAsJsonAsync("/api/v1/config",
                new AppConfig() with
                {
                    ExternalReporting = new ExternalReportingConfig(
                        enabled: true, role: "follower", leaderUrl: "http://127.0.0.1:8080"),
                },
                AppJsonContext.Default.AppConfig);

            var body = new RelayBatchRequest("Follower1",
                [new RelayDatagramDto("Heartbeat", Convert.ToBase64String("fake"u8.ToArray()))]);

            var response = await client.PostAsJsonAsync(
                "/api/v1/external-reporting/relay", body, AppJsonContext.Default.RelayBatchRequest);

            response.StatusCode.Should().Be(HttpStatusCode.ServiceUnavailable,
                "a follower is not itself an acceptable relay target — only a role: \"leader\" instance is");
        }
        finally
        {
            await ResetExternalReportingAsync(client);
        }
    }

    [Fact(DisplayName = "FR-065: relay endpoint accepts a batch when this instance is an enabled leader")]
    public async Task PostRelay_Returns200_WhenEnabledLeader()
    {
        var client = _factory.CreateClient();
        try
        {
            await client.PostAsJsonAsync("/api/v1/config",
                new AppConfig() with
                {
                    ExternalReporting = new ExternalReportingConfig(enabled: true, role: "leader"),
                },
                AppJsonContext.Default.AppConfig);

            var body = new RelayBatchRequest("Follower1",
            [
                new RelayDatagramDto("Heartbeat", Convert.ToBase64String("fake-heartbeat"u8.ToArray())),
                new RelayDatagramDto("Decode",    Convert.ToBase64String("fake-decode"u8.ToArray())),
            ]);

            var response = await client.PostAsJsonAsync(
                "/api/v1/external-reporting/relay", body, AppJsonContext.Default.RelayBatchRequest);

            response.StatusCode.Should().Be(HttpStatusCode.OK);
        }
        finally
        {
            await ResetExternalReportingAsync(client);
        }
    }

    [Fact(DisplayName = "FR-065: relay endpoint returns 400 for an empty datagrams array (even as an enabled leader)")]
    public async Task PostRelay_Returns400_ForEmptyDatagramsArray()
    {
        var client = _factory.CreateClient();
        try
        {
            await client.PostAsJsonAsync("/api/v1/config",
                new AppConfig() with
                {
                    ExternalReporting = new ExternalReportingConfig(enabled: true, role: "leader"),
                },
                AppJsonContext.Default.AppConfig);

            var body = new RelayBatchRequest("Follower1", []);

            var response = await client.PostAsJsonAsync(
                "/api/v1/external-reporting/relay", body, AppJsonContext.Default.RelayBatchRequest);

            response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        }
        finally
        {
            await ResetExternalReportingAsync(client);
        }
    }

    [Fact(DisplayName = "FR-065: relay endpoint returns 400 for malformed base64 in a datagram")]
    public async Task PostRelay_Returns400_ForMalformedBase64()
    {
        var client = _factory.CreateClient();
        try
        {
            await client.PostAsJsonAsync("/api/v1/config",
                new AppConfig() with
                {
                    ExternalReporting = new ExternalReportingConfig(enabled: true, role: "leader"),
                },
                AppJsonContext.Default.AppConfig);

            var content = new StringContent(
                """{ "followerInstanceId": "Follower1", "datagrams": [{ "type": "Heartbeat", "bytesBase64": "not-valid-base64!!!" }] }""",
                Encoding.UTF8, "application/json");

            var response = await client.PostAsync("/api/v1/external-reporting/relay", content);

            response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        }
        finally
        {
            await ResetExternalReportingAsync(client);
        }
    }
}
