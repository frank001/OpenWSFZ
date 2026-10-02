using FluentAssertions;
using Xunit;

namespace OpenWSFZ.E2E.Tests;

/// <summary>
/// Proves that a test-started daemon cannot touch the machine's real per-user config
/// (2026-10-02: <c>DaemonE2ETests</c> ran the published daemon with no <c>--config</c>, so the
/// default-ON migration rewrote the station's live <c>%APPDATA%\OpenWSFZ\config.json</c>).
/// The proof never touches the real file: the per-user config roots (<c>APPDATA</c>,
/// <c>XDG_CONFIG_HOME</c>, <c>HOME</c>, <c>USERPROFILE</c>) of the daemon process are pointed at a
/// throwaway sentinel directory, and the test asserts nothing was created there.
/// </summary>
[Trait("Category", "E2E")]
public sealed class DaemonConfigIsolationTests
{
    [Fact(DisplayName = "an isolated daemon with a sentinel APPDATA creates nothing under the sentinel; its config is the temp --config")]
    public async Task IsolatedDaemon_LeavesSentinelUserConfigRootUntouched()
    {
        var sentinel = Path.Combine(Path.GetTempPath(), "openwsfz-e2e-sentinel-" + Path.GetRandomFileName());
        Directory.CreateDirectory(sentinel);
        try
        {
            var env = new Dictionary<string, string>
            {
                ["APPDATA"]         = sentinel,
                ["XDG_CONFIG_HOME"] = sentinel,
                ["HOME"]            = sentinel,
                ["USERPROFILE"]     = sentinel,
                ["LOCALAPPDATA"]    = sentinel,
            };

            using var isolation = new IsolatedDaemonEnvironment();
            await using (var daemon = await isolation.StartAsync(env))
            {
                using var client = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{daemon.Port}") };
                (await client.GetAsync("/api/v1/status")).IsSuccessStatusCode.Should().BeTrue();
            }

            File.Exists(isolation.ConfigPath).Should().BeTrue("the daemon must use the isolated --config path");
            Directory.EnumerateFileSystemEntries(sentinel, "*", SearchOption.AllDirectories)
                .Should().BeEmpty("nothing may be created or modified under the per-user config root");
        }
        finally
        {
            try { Directory.Delete(sentinel, recursive: true); } catch { /* best-effort */ }
        }
    }

    [Fact(DisplayName = "DaemonProcess.StartAsync refuses to start a daemon without an explicit --config")]
    public async Task StartAsync_WithoutConfigPath_Throws()
    {
        var act = () => DaemonProcess.StartAsync(startupTimeout: TimeSpan.FromSeconds(10), explicitPort: 1);

        await act.Should().ThrowAsync<ArgumentNullException>()
            .WithMessage("*explicit --config*");
    }
}
