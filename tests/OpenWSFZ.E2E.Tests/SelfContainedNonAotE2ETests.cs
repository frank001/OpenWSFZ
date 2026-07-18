using System.Net;
using System.Text.Json;
using FluentAssertions;
using Xunit;

namespace OpenWSFZ.E2E.Tests;

/// <summary>
/// End-to-end tests that launch the same self-contained, non-AOT published daemon binary as
/// <see cref="DaemonE2ETests"/> (the default <c>publish/</c> output — see
/// dev-tasks/2026-07-18-self-contained-non-aot-working-binary.md), specifically to exercise the
/// audio-device endpoints as a targeted regression guard.
///
/// <para>
/// Root cause this guards against: <c>OpenWSFZ.Daemon.csproj</c> switches on
/// <c>PublishAot</c> for <b>any</b> RID-targeted publish, self-contained or not. NAudio's
/// <c>[ComImport]</c> WASAPI COM activation is incompatible with Native AOT and throws
/// <c>"Common Language Runtime detected an invalid program"</c> from
/// <c>MMDeviceEnumeratorComObject..ctor()</c> the instant real WASAPI code runs in an
/// AOT-compiled binary. The audio-device endpoint calls below are the check that actually
/// matters: they force the WASAPI COM-activation path to run, proving it doesn't crash — the
/// exact failure mode reported the night this task was written. The Native AOT structural
/// prove-out binary (a separate <c>publish-aot/</c> output — see
/// dev-tasks/2026-07-18-aot-comwrappers-audio-migration.md, deferred) is known-broken for this
/// and is deliberately never launched by any E2E test.
/// </para>
///
/// <para>
/// Each test spawns its own daemon on a reserved ephemeral port with its own isolated temp
/// config file (<see cref="DaemonProcess.ReserveEphemeralPort"/> + a per-test temp directory),
/// rather than the shared default port/config <see cref="DaemonE2ETests"/> uses. xUnit runs
/// different test classes in separate collections that may execute concurrently — this class and
/// <see cref="DaemonE2ETests"/> both spawn a live daemon, and without isolation they raced each
/// other for the same default port and the same default config file, causing spurious welcome
/// banner timeouts when the full suite ran (`dotnet test OpenWSFZ.slnx`) despite each class
/// passing individually. Discovered and fixed while writing this test.
/// </para>
/// </summary>
[Trait("Category", "E2E")]
public sealed class SelfContainedNonAotE2ETests
{
    [Fact(DisplayName =
        "self-contained non-AOT publish: welcome banner appears on stdout within 10 seconds")]
    public async Task WelcomeBanner_AppearsOnStdoutWithinTimeout()
    {
        using var isolation = new IsolatedDaemonEnvironment();
        await using var daemon = await isolation.StartAsync();

        daemon.Port.Should().BeInRange(1, 65535,
            because: "port must be parsed from the welcome banner");
    }

    [Fact(DisplayName =
        "self-contained non-AOT publish: HTTP status endpoint reachable after banner")]
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

    [Theory(DisplayName =
        "self-contained non-AOT publish: audio device endpoint returns 200 with a JSON array " +
        "(proves WASAPI COM activation doesn't crash the process)")]
    [InlineData("/api/v1/audio/devices")]
    [InlineData("/api/v1/audio/output-devices")]
    public async Task AudioDeviceEndpoint_ReturnsOkJsonArray(string path)
    {
        using var isolation = new IsolatedDaemonEnvironment();
        await using var daemon = await isolation.StartAsync();

        using var client = new HttpClient
        {
            BaseAddress = new Uri($"http://127.0.0.1:{daemon.Port}"),
        };

        var response = await client.GetAsync(path);

        response.StatusCode.Should().Be(HttpStatusCode.OK,
            because: "a 500 or a crashed process here is exactly the AOT-publish COM-activation " +
                     "failure mode this task fixes — regardless of whether real capture hardware " +
                     "is attached, since the defect is in COM activation itself, not enumeration " +
                     "results");

        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.ValueKind.Should().Be(JsonValueKind.Array,
            because: "an empty array is an acceptable pass — CI runners have no real capture " +
                     "hardware");
    }

    /// <summary>
    /// Reserves an ephemeral port and an isolated temp config directory for one test's daemon,
    /// so it cannot collide with another concurrently-running test class's daemon on the shared
    /// default port/config file (see this class's own doc comment). Cleans up the temp
    /// directory on <see cref="Dispose"/>.
    /// </summary>
    private sealed class IsolatedDaemonEnvironment : IDisposable
    {
        private readonly string _tempDir = Path.Combine(
            Path.GetTempPath(), "openwsfz-selfcontained-e2e-" + Path.GetRandomFileName());

        public Task<DaemonProcess> StartAsync()
        {
            Directory.CreateDirectory(_tempDir);
            var configPath = Path.Combine(_tempDir, "config.json");
            var port = DaemonProcess.ReserveEphemeralPort();

            return DaemonProcess.StartAsync(
                startupTimeout: TimeSpan.FromSeconds(10),
                explicitPort: port,
                configPath: configPath);
        }

        public void Dispose()
        {
            try { Directory.Delete(_tempDir, recursive: true); } catch { /* best-effort */ }
        }
    }
}
