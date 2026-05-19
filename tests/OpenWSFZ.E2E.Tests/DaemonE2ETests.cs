using System.Net;
using FluentAssertions;
using Xunit;

namespace OpenWSFZ.E2E.Tests;

/// <summary>
/// End-to-end tests that launch the AOT-published daemon binary as a subprocess.
/// These tests verify the production artefact works, not just the in-process build.
/// </summary>
[Trait("Category", "E2E")]
public sealed class DaemonE2ETests
{
    [Fact(DisplayName = "FR-007: welcome banner appears on stdout within 10 seconds")]
    public async Task WelcomeBanner_AppearsOnStdoutWithinTimeout()
    {
        await using var daemon = await DaemonProcess.StartAsync(
            startupTimeout: TimeSpan.FromSeconds(10));

        daemon.Port.Should().BeInRange(1, 65535,
            because: "port must be parsed from the welcome banner");
    }

    [Fact(DisplayName = "FR-002: HTTP status endpoint reachable after banner")]
    public async Task StatusEndpoint_ReachableAfterBanner()
    {
        await using var daemon = await DaemonProcess.StartAsync(
            startupTimeout: TimeSpan.FromSeconds(10));

        using var client = new HttpClient
        {
            BaseAddress = new Uri($"http://127.0.0.1:{daemon.Port}"),
        };

        var response = await client.GetAsync("/api/v1/status");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }
}
