using System.Diagnostics;
using FluentAssertions;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Tests for <see cref="ConsoleDetacher.Detach"/> (daemon-background-mode, task 3.3).
///
/// <para>
/// <see cref="Detach_DoesNotThrow_OnCurrentPlatform"/> runs on every CI platform and covers the
/// "does not throw" half of task 3.3's Windows requirement (calling the real
/// <c>FreeConsole()</c> P/Invoke from a test process) — it also harmlessly exercises the POSIX
/// <see cref="System.Runtime.InteropServices.PosixSignalRegistration"/> branch when run on
/// Linux/macOS.
/// </para>
///
/// <para>
/// <see cref="PosixSigHupIgnore_RealSubprocessSurvivesSigHup_ControlWithoutHandlerDoesNotSurvive"/>
/// proves the actual mechanism end-to-end on Linux/macOS: a real child process (SigHupProbe,
/// <c>tools/SigHupProbe</c>) registers the identical <c>PosixSignalRegistration</c> call
/// <see cref="ConsoleDetacher.Detach"/> makes, receives a real <c>SIGHUP</c> (sent via the
/// system <c>kill</c> command, matching this project's existing "spin up a real subprocess and
/// observe it" integration-test convention, e.g. <c>DaemonStartupTests</c>), and is confirmed
/// still running afterward; a control case with no handler confirms the same signal would
/// otherwise terminate it. No-ops with a passing assertion on Windows, where SIGHUP does not
/// exist — that platform's detach mechanism (<c>FreeConsole</c>) is covered by the test above.
/// </para>
/// </summary>
[Trait("Category", "Integration")]
public sealed class ConsoleDetacherTests
{
    [Fact(DisplayName = "daemon-background-mode 3.3: Detach() does not throw when called from a test process")]
    public void Detach_DoesNotThrow_OnCurrentPlatform()
    {
        var act = () => ConsoleDetacher.Detach();

        act.Should().NotThrow();
    }

    [Fact(DisplayName =
        "daemon-background-mode 3.3: a real subprocess with SIGHUP ignored survives a real SIGHUP; " +
        "a control subprocess without the handler does not")]
    public async Task PosixSigHupIgnore_RealSubprocessSurvivesSigHup_ControlWithoutHandlerDoesNotSurvive()
    {
        if (OperatingSystem.IsWindows())
            return; // SIGHUP does not exist on Windows — FreeConsole is covered above.

        var probePath = ResolveSigHupProbePath();

        // ── Treatment: --ignore registers the SIGHUP-ignore handler ──────────────────────
        await using (var treated = await SigHupProbeProcess.StartAsync(probePath, ignore: true))
        {
            await SendSigHupAsync(treated.Process.Id);

            // Give the signal a moment to be delivered and (if unhandled) take effect.
            await Task.Delay(TimeSpan.FromSeconds(1));

            treated.Process.HasExited.Should().BeFalse(
                "a process that registered a SIGHUP-ignore handler must survive a real SIGHUP");
        }

        // ── Control: no handler registered — default SIGHUP disposition terminates it ────
        await using (var control = await SigHupProbeProcess.StartAsync(probePath, ignore: false))
        {
            await SendSigHupAsync(control.Process.Id);

            await Task.Delay(TimeSpan.FromSeconds(1));

            control.Process.HasExited.Should().BeTrue(
                "without a handler, SIGHUP's default disposition must terminate the process — " +
                "this confirms the treatment case above is actually testing something");
        }
    }

    // ── Helpers ──────────────────────────────────────────────────────────────────────────

    private static async Task SendSigHupAsync(int pid)
    {
        using var kill = Process.Start(new ProcessStartInfo("kill", $"-HUP {pid}")
        {
            UseShellExecute = false,
        })!;
        await kill.WaitForExitAsync();
    }

    private static string ResolveSigHupProbePath()
    {
        // SigHupProbe.csproj is referenced by this test project purely so its build output
        // (dll/deps.json/runtimeconfig.json) is copied alongside this assembly's own output —
        // see OpenWSFZ.Daemon.Tests.csproj's ProjectReference comment.
        var dllPath = Path.Combine(AppContext.BaseDirectory, "SigHupProbe.dll");
        if (!File.Exists(dllPath))
            throw new FileNotFoundException(
                $"SigHupProbe.dll not found at '{dllPath}' — expected it to be copied " +
                "alongside the test assembly via the ProjectReference in " +
                "OpenWSFZ.Daemon.Tests.csproj.", dllPath);

        return dllPath;
    }

    /// <summary>Launches SigHupProbe via <c>dotnet exec</c> and waits for its "READY" line.</summary>
    private sealed class SigHupProbeProcess : IAsyncDisposable
    {
        public Process Process { get; }

        private SigHupProbeProcess(Process process) => Process = process;

        public static async Task<SigHupProbeProcess> StartAsync(string dllPath, bool ignore)
        {
            var args = ignore ? $"exec \"{dllPath}\" --ignore" : $"exec \"{dllPath}\"";
            var psi = new ProcessStartInfo("dotnet", args)
            {
                RedirectStandardOutput = true,
                RedirectStandardError  = true,
                UseShellExecute        = false,
            };

            var process = Process.Start(psi)
                ?? throw new InvalidOperationException("Failed to start SigHupProbe.");

            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(15));
            string? line;
            do
            {
                line = await process.StandardOutput.ReadLineAsync(cts.Token);
            } while (line is not null && !line.Contains("READY"));

            if (line is null)
            {
                process.Kill(entireProcessTree: true);
                throw new TimeoutException("SigHupProbe never printed READY.");
            }

            return new SigHupProbeProcess(process);
        }

        public async ValueTask DisposeAsync()
        {
            if (!Process.HasExited)
                Process.Kill(entireProcessTree: true);

            await Process.WaitForExitAsync();
            Process.Dispose();
        }
    }
}
