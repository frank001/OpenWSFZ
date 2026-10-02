namespace OpenWSFZ.E2E.Tests;

/// <summary>
/// Reserves an ephemeral port and an isolated temp config directory for one test's daemon, so it
/// can neither collide with another concurrently-running test class's daemon on the shared default
/// port, nor read, migrate or rewrite the machine's REAL per-user config file
/// (<c>%APPDATA%\OpenWSFZ\config.json</c> on Windows), which on the station is the station's live
/// config. Every E2E test that starts a daemon uses this (<see cref="DaemonProcess.StartAsync"/>
/// refuses to start one without an explicit <c>--config</c>). Deletes the temp directory on
/// <see cref="Dispose"/>.
/// </summary>
internal sealed class IsolatedDaemonEnvironment : IDisposable
{
    private readonly string _tempDir = Path.Combine(
        Path.GetTempPath(), "openwsfz-e2e-" + Path.GetRandomFileName());

    /// <summary>The isolated <c>--config</c> path this environment passes to the daemon.</summary>
    public string ConfigPath => Path.Combine(_tempDir, "config.json");

    /// <summary>Starts the daemon with the isolated config and a freshly reserved ephemeral port.</summary>
    /// <param name="environment">Optional environment-variable overrides for the daemon process.</param>
    public Task<DaemonProcess> StartAsync(IReadOnlyDictionary<string, string>? environment = null)
    {
        Directory.CreateDirectory(_tempDir);
        var port = DaemonProcess.ReserveEphemeralPort();

        return DaemonProcess.StartAsync(
            startupTimeout: TimeSpan.FromSeconds(10),
            explicitPort: port,
            configPath: ConfigPath,
            environment: environment);
    }

    public void Dispose()
    {
        try { Directory.Delete(_tempDir, recursive: true); } catch { /* best-effort */ }
    }
}
