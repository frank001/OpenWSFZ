using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using FluentAssertions;
using Xunit;

namespace OpenWSFZ.E2E.Tests;

/// <summary>
/// Regression test for a defect the Captain found during `daemon-background-mode`'s manual
/// acceptance gate (tasks.md section 8): the `--background` cold-start orchestrator originally
/// ran through the full logging pipeline bootstrap before reaching its own spawn-and-exit
/// branch, so every `--background` invocation created its own throwaway log file (three lines:
/// "Config: ...", "Log level: ...", "--background: Spawned...") that was then abandoned forever
/// the moment the orchestrator exited — alongside the actual `--background-worker` child's own,
/// correctly-active log file. An operator inspecting the log directory saw two files per
/// invocation, one of which looked permanently broken.
///
/// <para>
/// Fixed by moving the cold-start branch to run immediately after <c>JsonConfigStore</c> loads
/// (which happens synchronously at construction — see its own doc comment) and before the
/// "── Logging setup ──" section, so the orchestrator never touches <c>LoggingPipeline</c> at
/// all. This test spawns the real AOT-published binary (this project's CI already publishes it
/// before running the E2E suite — see ci.yml) with <c>--background</c> and asserts exactly one
/// log file appears, not two.
/// </para>
/// </summary>
[Trait("Category", "E2E")]
public sealed class BackgroundColdStartE2ETests
{
    [Fact(DisplayName =
        "daemon-background-mode defect fix: --background cold start creates exactly one log file, not an abandoned orchestrator file plus the worker's")]
    public async Task ColdStartBackground_CreatesExactlyOneLogFile_NoAbandonedOrchestratorFile()
    {
        var binaryPath = DaemonProcess.ResolveBinaryPath();
        var port       = ReserveEphemeralPort();

        var tempDir = Path.Combine(Path.GetTempPath(), "openwsfz-bg-e2e-" + Path.GetRandomFileName());
        Directory.CreateDirectory(tempDir);
        var configPath = Path.Combine(tempDir, "config.json");

        Process? worker = null;
        try
        {
            var psi = new ProcessStartInfo(binaryPath)
            {
                RedirectStandardOutput = true,
                RedirectStandardError  = true,
                UseShellExecute        = false,
                WorkingDirectory       = tempDir, // so the default relative "logs" dir lands here, isolated
            };
            psi.ArgumentList.Add("--background");
            psi.ArgumentList.Add("--port");
            psi.ArgumentList.Add(port.ToString());
            psi.ArgumentList.Add("--config");
            psi.ArgumentList.Add(configPath);

            using var orchestrator = Process.Start(psi)
                ?? throw new InvalidOperationException($"Failed to start process: {binaryPath}");

            // Read stdout line-by-line looking for the confirmation, rather than
            // ReadToEndAsync() (deliberately never used here): the orchestrator's own spawned
            // worker inherits its stdout pipe handle (BackgroundColdStart.SpawnAndConfirmAsync
            // spawns it with no explicit redirection of its own, matching DaemonRelauncher's
            // existing Process.Start pattern) — so the pipe's write end stays open in that
            // long-running grandchild even after the orchestrator itself exits, and
            // ReadToEndAsync would block forever waiting for EOF that never comes. This exact
            // hang was hit while writing this test (6-minute stuck run, only unblocked by
            // manually killing the leaked worker) — mirrors DaemonProcess.ReadBannerAsync's own
            // line-at-a-time-with-a-deadline approach for the identical reason.
            var confirmationLine = await ReadLineContainingAsync(
                orchestrator.StandardOutput, "Spawned background daemon", TimeSpan.FromSeconds(15));
            confirmationLine.Should().NotBeNull(
                "the orchestrator must report a successful spawn within a reasonable time");

            worker = TryFindWorkerProcess(confirmationLine!);

            // Safe to wait for the orchestrator's own exit now — WaitForExitAsync watches the
            // process handle, not the (still-open-in-the-grandchild) stdout pipe, so it cannot
            // hit the same hang.
            var exited = await WaitForExitAsync(orchestrator, TimeSpan.FromSeconds(10));
            exited.Should().BeTrue("the --background orchestrator must exit on its own once it has spawned and confirmed the worker");

            var logsDir = Path.Combine(tempDir, "logs");
            Directory.Exists(logsDir).Should().BeTrue("the worker forces file logging on regardless of the (freshly-created, default) config");

            var logFiles = Directory.GetFiles(logsDir, "openswfz-*.log");
            logFiles.Should().HaveCount(1,
                "exactly one log file must exist — the orchestrator's own throwaway file " +
                "(the reported defect) must no longer be created; only the worker's real, " +
                "actively-written file should appear");

            var content = ReadWithSharing(logFiles[0]);
            content.Should().Contain("OpenWSFZ started on port",
                "the single log file present must be the worker's real, active log — not an " +
                "abandoned 3-line orchestrator artifact");
        }
        finally
        {
            if (worker is not null)
            {
                try { if (!worker.HasExited) worker.Kill(entireProcessTree: true); } catch { /* best-effort */ }
                worker.Dispose();
            }

            try { Directory.Delete(tempDir, recursive: true); } catch { /* best-effort */ }
        }
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    private static int ReserveEphemeralPort()
    {
        using var probe = new TcpListener(IPAddress.Loopback, 0);
        probe.Start();
        var port = ((IPEndPoint)probe.LocalEndpoint).Port;
        probe.Stop();
        return port;
    }

    private static async Task<bool> WaitForExitAsync(Process process, TimeSpan timeout)
    {
        using var cts = new CancellationTokenSource(timeout);
        try
        {
            await process.WaitForExitAsync(cts.Token);
            return true;
        }
        catch (OperationCanceledException)
        {
            return false;
        }
    }

    /// <summary>
    /// Reads lines from <paramref name="reader"/> one at a time (never <c>ReadToEndAsync</c> —
    /// see the caller's comment for why) until one containing <paramref name="marker"/> is
    /// found or <paramref name="timeout"/> elapses. Mirrors
    /// <c>DaemonProcess.ReadBannerAsync</c>'s existing pattern in this same test project.
    /// </summary>
    private static async Task<string?> ReadLineContainingAsync(
        StreamReader reader, string marker, TimeSpan timeout)
    {
        using var cts = new CancellationTokenSource(timeout);
        try
        {
            while (true)
            {
                var line = await reader.ReadLineAsync(cts.Token);
                if (line is null) return null; // EOF
                if (line.Contains(marker, StringComparison.Ordinal)) return line;
            }
        }
        catch (OperationCanceledException)
        {
            return null;
        }
    }

    /// <summary>
    /// Parses "(pid 12345)" out of the orchestrator's confirmation line and returns a handle to
    /// that worker process, so the test can clean it up afterward. Returns null (best-effort)
    /// if parsing fails — cleanup then simply relies on the OS/CI runner tearing it down.
    /// </summary>
    private static Process? TryFindWorkerProcess(string confirmationLine)
    {
        const string marker = "(pid ";
        var idx = confirmationLine.IndexOf(marker, StringComparison.Ordinal);
        if (idx < 0) return null;

        var start = idx + marker.Length;
        var end   = confirmationLine.IndexOf(')', start);
        if (end < 0) return null;

        if (!int.TryParse(confirmationLine[start..end], out var pid)) return null;

        try { return Process.GetProcessById(pid); }
        catch (ArgumentException) { return null; } // already exited
    }

    /// <summary>Reads a file while it may still be open for writing by the Serilog file sink.</summary>
    private static string ReadWithSharing(string path)
    {
        using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
        using var sr = new StreamReader(fs);
        return sr.ReadToEnd();
    }
}
