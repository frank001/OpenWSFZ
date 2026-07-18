using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Text;

namespace OpenWSFZ.E2E.Tests;

/// <summary>
/// Launches the self-contained, non-AOT <c>OpenWSFZ.Daemon</c> binary (the default
/// <c>publish/</c> output — see dev-tasks/2026-07-18-self-contained-non-aot-working-binary.md)
/// as a subprocess, waits for the welcome banner on stdout, and exposes the bound port for
/// tests. Disposes the process (with SIGKILL / Kill) in a <see langword="finally"/> block.
/// </summary>
public sealed class DaemonProcess : IAsyncDisposable
{
    private readonly Process _process;

    private DaemonProcess(Process process, int port)
    {
        _process = process;
        Port     = port;
    }

    /// <summary>The port the daemon bound to, parsed from the welcome banner.</summary>
    public int Port { get; }

    /// <summary>
    /// Resolves the published binary path for the current RID, starts the process,
    /// and waits up to <paramref name="startupTimeout"/> for the welcome banner.
    /// </summary>
    /// <param name="startupTimeout">How long to wait for the welcome banner before failing.</param>
    /// <param name="ct">Cancellation token for the banner wait.</param>
    /// <param name="publishSubdir">
    /// Which publish output to launch — defaults to <c>"publish"</c> (the self-contained,
    /// non-AOT binary this project actually ships; see
    /// dev-tasks/2026-07-18-self-contained-non-aot-working-binary.md). Pass
    /// <c>"publish-aot"</c> to launch the Native AOT structural-prove-out binary instead —
    /// a distinct output directory so the two publishes never clobber each other. The AOT
    /// binary is known-broken for Windows WASAPI audio (see
    /// dev-tasks/2026-07-18-aot-comwrappers-audio-migration.md, deferred); no current E2E
    /// test launches it, this option exists for completeness/future use.
    /// </param>
    /// <param name="explicitPort">
    /// Explicit <c>--port</c> to pass the daemon, or <see langword="null"/> to let it fall back
    /// to the persisted config value (the default). Pass an ephemeral port (see
    /// <see cref="ReserveEphemeralPort"/>) whenever a test's daemon must not collide with
    /// another test class's daemon — xUnit runs different test classes in separate
    /// collections, which may execute concurrently (see <see cref="SelfContainedNonAotE2ETests"/>,
    /// which shares no collection with <c>DaemonE2ETests</c> and would otherwise race it for the
    /// same default port and default config file).
    /// </param>
    /// <param name="configPath">
    /// Explicit <c>--config</c> path, or <see langword="null"/> to use the platform default
    /// config location. Pass an isolated temp path alongside a non-null
    /// <paramref name="explicitPort"/> for the same cross-test-class isolation reason.
    /// </param>
    public static async Task<DaemonProcess> StartAsync(
        TimeSpan? startupTimeout = null,
        CancellationToken ct = default,
        string publishSubdir = "publish",
        int? explicitPort = null,
        string? configPath = null)
    {
        var timeout = startupTimeout ?? TimeSpan.FromSeconds(10);
        var binaryPath = ResolveBinaryPath(publishSubdir);

        var psi = new ProcessStartInfo(binaryPath)
        {
            RedirectStandardOutput = true,
            RedirectStandardError  = true,
            UseShellExecute        = false,
        };
        if (explicitPort is not null)
        {
            psi.ArgumentList.Add("--port");
            psi.ArgumentList.Add(explicitPort.Value.ToString());
        }
        if (configPath is not null)
        {
            psi.ArgumentList.Add("--config");
            psi.ArgumentList.Add(configPath);
        }

        var process = Process.Start(psi)
            ?? throw new InvalidOperationException($"Failed to start process: {binaryPath}");

        // Poll stdout for the banner line.
        var bannerLine = await ReadBannerAsync(process, timeout, ct);
        if (bannerLine is null)
        {
            process.Kill(entireProcessTree: true);
            throw new TimeoutException(
                $"Daemon did not emit welcome banner on stdout within {timeout.TotalSeconds} s.");
        }

        var port = ParsePort(bannerLine);
        return new DaemonProcess(process, port);
    }

    public async ValueTask DisposeAsync()
    {
        if (!_process.HasExited)
        {
            _process.Kill(entireProcessTree: true);
        }

        await _process.WaitForExitAsync();
        _process.Dispose();
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    /// <summary>
    /// Resolves the published binary path (internal rather than private so
    /// <c>BackgroundColdStartE2ETests</c> can spawn it directly with custom CLI arguments,
    /// e.g. <c>--background</c>, rather than via <see cref="StartAsync"/>'s
    /// no-arguments/wait-for-welcome-banner shape).
    /// </summary>
    /// <param name="publishSubdir">
    /// Publish output directory name under <c>&lt;rid&gt;/</c> — <c>"publish"</c> for the
    /// self-contained, non-AOT binary (default, matches
    /// <see cref="BackgroundColdStartE2ETests"/>'s no-arguments call), or
    /// <c>"publish-aot"</c> for the Native AOT structural-prove-out binary. See
    /// dev-tasks/2026-07-18-self-contained-non-aot-working-binary.md — the two publish
    /// outputs are kept in separate directories deliberately so one publish can never
    /// silently clobber the other's binary.
    /// </param>
    internal static string ResolveBinaryPath(string publishSubdir = "publish")
    {
        // Published binary lives at:
        // src/OpenWSFZ.Daemon/bin/Release/net10.0/<rid>/<publishSubdir>/OpenWSFZ.Daemon[.exe]
        var rid = GetRid();
        var repoRoot = FindRepoRoot();
        var exeName  = RuntimeInformation.IsOSPlatform(OSPlatform.Windows)
            ? "OpenWSFZ.Daemon.exe"
            : "OpenWSFZ.Daemon";

        var path = Path.Combine(
            repoRoot, "src", "OpenWSFZ.Daemon", "bin", "Release", "net10.0", rid, publishSubdir, exeName);

        if (!File.Exists(path))
        {
            var publishCommand = publishSubdir == "publish-aot"
                ? "dotnet publish src/OpenWSFZ.Daemon -c Release -r <rid> --self-contained -p:PublishAot=true " +
                  $"-o src/OpenWSFZ.Daemon/bin/Release/net10.0/<rid>/{publishSubdir}/"
                : "python3 tools/publish_selfcontained.py --rid <rid> before running E2E tests.";

            throw new FileNotFoundException(
                $"Published binary not found at '{path}'. Run: {publishCommand}",
                path);
        }

        return path;
    }

    /// <summary>
    /// Reserves a free TCP port on loopback and immediately releases it, for tests that need to
    /// pass an explicit <c>--port</c> so their daemon doesn't collide with another concurrently
    /// running test class's daemon on the shared default port. Mirrors
    /// <c>BackgroundColdStartE2ETests.ReserveEphemeralPort</c> (kept as a separate private copy
    /// there rather than refactored to call this one, to avoid touching an already-passing test
    /// file for this change).
    /// </summary>
    internal static int ReserveEphemeralPort()
    {
        using var probe = new TcpListener(IPAddress.Loopback, 0);
        probe.Start();
        var port = ((IPEndPoint)probe.LocalEndpoint).Port;
        probe.Stop();
        return port;
    }

    private static string FindRepoRoot()
    {
        // Walk up from the test output directory until we find OpenWSFZ.slnx.
        var dir = AppContext.BaseDirectory;
        while (dir is not null)
        {
            if (File.Exists(Path.Combine(dir, "OpenWSFZ.slnx")))
                return dir;
            dir = Path.GetDirectoryName(dir);
        }

        throw new DirectoryNotFoundException("Could not locate repository root (OpenWSFZ.slnx not found).");
    }

    private static string GetRid()
    {
        var arch = RuntimeInformation.ProcessArchitecture;
        var archSuffix = arch == Architecture.Arm64 ? "arm64" : "x64";

        if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows)) return $"win-{archSuffix}";
        if (RuntimeInformation.IsOSPlatform(OSPlatform.Linux))   return $"linux-{archSuffix}";
        if (RuntimeInformation.IsOSPlatform(OSPlatform.OSX))     return $"osx-{archSuffix}";
        throw new PlatformNotSupportedException("Unsupported OS for E2E tests.");
    }

    private static async Task<string?> ReadBannerAsync(
        Process process, TimeSpan timeout, CancellationToken ct)
    {
        using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        cts.CancelAfter(timeout);

        try
        {
            while (true)
            {
                var line = await process.StandardOutput.ReadLineAsync(cts.Token);
                if (line is null) return null;                        // EOF
                if (line.Contains("http://127.0.0.1:")) return line; // banner found
            }
        }
        catch (OperationCanceledException)
        {
            return null;
        }
    }

    private static int ParsePort(string bannerLine)
    {
        // Banner format: "OpenWSFZ listening on http://127.0.0.1:<port> — ..."
        const string prefix = "http://127.0.0.1:";
        var idx = bannerLine.IndexOf(prefix, StringComparison.Ordinal);
        if (idx < 0) return 8080;

        var portStart = idx + prefix.Length;
        var portEnd   = portStart;
        while (portEnd < bannerLine.Length && char.IsDigit(bannerLine[portEnd]))
            portEnd++;

        return int.TryParse(bannerLine.AsSpan(portStart, portEnd - portStart), out var port)
            ? port
            : 8080;
    }
}
