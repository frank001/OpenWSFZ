using System.Net;
using FluentAssertions;
using Xunit;

namespace OpenWSFZ.E2E.Tests;

/// <summary>
/// End-to-end tests that launch the AOT-published daemon binary as a subprocess.
/// These tests verify the production artefact works, not just the in-process build.
/// Each daemon runs on an ephemeral port with an isolated temp <c>--config</c>
/// (<see cref="IsolatedDaemonEnvironment"/>): it must never touch the machine's real per-user
/// config file, which on the station is the live config.
/// </summary>
[Trait("Category", "E2E")]
public sealed class DaemonE2ETests
{
    [Fact(DisplayName = "FR-007: welcome banner appears on stdout within 10 seconds")]
    public async Task WelcomeBanner_AppearsOnStdoutWithinTimeout()
    {
        using var isolation = new IsolatedDaemonEnvironment();
        await using var daemon = await isolation.StartAsync();

        daemon.Port.Should().BeInRange(1, 65535,
            because: "port must be parsed from the welcome banner");
    }

    [Fact(DisplayName = "FR-002: HTTP status endpoint reachable after banner")]
    public async Task StatusEndpoint_ReachableAfterBanner()
    {
        using var isolation = new IsolatedDaemonEnvironment();
        await using var daemon = await isolation.StartAsync();

        using var client = new HttpClient
        {
            BaseAddress = new Uri($"http://127.0.0.1:{daemon.Port}"),
        };

        var response = await client.GetAsync("/api/v1/status");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }
}
