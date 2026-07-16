using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;

namespace OpenWSFZ.E2E.Tests;

/// <summary>
/// Launches the AOT-published <c>OpenWSFZ.Daemon</c> binary as a subprocess,
/// waits for the welcome banner on stdout, and exposes the bound port for tests.
/// Disposes the process (with SIGKILL / Kill) in a <see langword="finally"/> block.
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
    public static async Task<DaemonProcess> StartAsync(
        TimeSpan? startupTimeout = null,
        CancellationToken ct = default)
    {
        var timeout = startupTimeout ?? TimeSpan.FromSeconds(10);
        var binaryPath = ResolveBinaryPath();

        var psi = new ProcessStartInfo(binaryPath)
        {
            RedirectStandardOutput = true,
            RedirectStandardError  = true,
            UseShellExecute        = false,
        };

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
    internal static string ResolveBinaryPath()
    {
        // Published binary lives at:
        // src/OpenWSFZ.Daemon/bin/Release/net10.0/<rid>/publish/OpenWSFZ.Daemon[.exe]
        var rid = GetRid();
        var repoRoot = FindRepoRoot();
        var exeName  = RuntimeInformation.IsOSPlatform(OSPlatform.Windows)
            ? "OpenWSFZ.Daemon.exe"
            : "OpenWSFZ.Daemon";

        var path = Path.Combine(
            repoRoot, "src", "OpenWSFZ.Daemon", "bin", "Release", "net10.0", rid, "publish", exeName);

        if (!File.Exists(path))
        {
            throw new FileNotFoundException(
                $"Published binary not found at '{path}'. " +
                "Run: dotnet publish src/OpenWSFZ.Daemon -c Release -r <rid> --self-contained before running E2E tests.",
                path);
        }

        return path;
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
