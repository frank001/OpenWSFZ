using FluentAssertions;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="DaemonRelaunch.ResolveCommand"/> (remote-daemon-restart, task 3.2),
/// covering both the framework-dependent (<c>dotnet</c> muxer) and self-contained (apphost)
/// launch branches described in design.md Decision 2. All process-path/entry-assembly-location
/// inputs are injected fakes — this file never touches the real test runner's own process path.
/// </summary>
[Trait("Category", "Unit")]
public sealed class DaemonRelaunchTests
{
    [Fact(DisplayName = "remote-daemon-restart 3.2: dotnet-muxer launch prepends the entry assembly location")]
    public void ResolveCommand_DotnetMuxer_PrependsEntryAssemblyLocation()
    {
        // processPath is deliberately a bare filename with no directory component: this
        // project's test suite runs cross-platform (ubuntu-latest/macos-latest/windows-latest
        // CI matrix), and Path.GetFileNameWithoutExtension only treats '\' as a directory
        // separator on Windows — a hardcoded Windows-style directory prefix here (as this test
        // originally had) silently fails the muxer-filename detection on Linux/macOS, which is
        // a test-portability artifact, not a real scenario: production always calls this with
        // Environment.ProcessPath, which is already OS-natively formatted by the runtime it's
        // actually running on.
        var cmd = DaemonRelaunch.ResolveCommand(
            processPath:            "dotnet.exe",
            originalArgs:           ["--port", "8080"],
            entryAssemblyLocation:  @"C:\app\OpenWSFZ.Daemon.dll",
            currentPid:             4242);

        cmd.FileName.Should().Be("dotnet.exe",
            "the dotnet muxer itself must be relaunched, not the managed assembly directly");
        cmd.Arguments.Should().Equal(
            @"C:\app\OpenWSFZ.Daemon.dll", "--port", "8080", "--relaunched-from", "4242");
    }

    [Fact(DisplayName = "remote-daemon-restart 3.2: dotnet-muxer detection is case-insensitive and extension-agnostic")]
    public void ResolveCommand_DotnetMuxerDetection_IsCaseInsensitive()
    {
        var cmd = DaemonRelaunch.ResolveCommand(
            processPath:            "/usr/share/dotnet/DOTNET",
            originalArgs:           [],
            entryAssemblyLocation:  "/app/OpenWSFZ.Daemon.dll",
            currentPid:             1);

        cmd.Arguments.Should().StartWith("/app/OpenWSFZ.Daemon.dll",
            "the muxer branch must trigger regardless of case or a missing extension (Linux/macOS)");
    }

    [Fact(DisplayName = "remote-daemon-restart 3.2: self-contained apphost launch relaunches that executable directly")]
    public void ResolveCommand_SelfContainedApphost_RelaunchesExecutableDirectly()
    {
        var cmd = DaemonRelaunch.ResolveCommand(
            processPath:            @"C:\app\OpenWSFZ.Daemon.exe",
            originalArgs:           ["--config", @"C:\data\app.json"],
            entryAssemblyLocation:  @"C:\app\OpenWSFZ.Daemon.dll", // unused on this branch
            currentPid:             99);

        cmd.FileName.Should().Be(@"C:\app\OpenWSFZ.Daemon.exe",
            "a self-contained apphost is already the real executable — relaunch it directly");
        cmd.Arguments.Should().Equal(
            "--config", @"C:\data\app.json", "--relaunched-from", "99");
        cmd.Arguments.Should().NotContain(@"C:\app\OpenWSFZ.Daemon.dll",
            "the entry-assembly-location parameter must be ignored on the apphost branch");
    }

    [Fact(DisplayName = "remote-daemon-restart 3.2: relaunch flag and original args are all present regardless of branch")]
    public void ResolveCommand_RelaunchFlagAndOriginalArgs_AlwaysPresent()
    {
        var muxerCmd = DaemonRelaunch.ResolveCommand(
            "dotnet", ["--port", "9090"], "/app/OpenWSFZ.Daemon.dll", 7);
        var apphostCmd = DaemonRelaunch.ResolveCommand(
            "/app/OpenWSFZ.Daemon", ["--port", "9090"], "/app/OpenWSFZ.Daemon.dll", 7);

        muxerCmd.Arguments.Should().Contain(["--port", "9090", "--relaunched-from", "7"]);
        apphostCmd.Arguments.Should().Contain(["--port", "9090", "--relaunched-from", "7"]);
    }

    [Fact(DisplayName = "remote-daemon-restart 3.2: no original args still appends the relaunch flag")]
    public void ResolveCommand_NoOriginalArgs_StillAppendsRelaunchFlag()
    {
        var cmd = DaemonRelaunch.ResolveCommand(
            "/app/OpenWSFZ.Daemon", [], "/app/OpenWSFZ.Daemon.dll", 555);

        cmd.Arguments.Should().Equal("--relaunched-from", "555");
    }

    // ── daemon-background-mode 6.3 ──────────────────────────────────────────────
    // OS-agnostic bare-filename processPath inputs throughout — a hardcoded Windows-style path
    // literal broke this exact test file's cross-platform portability once already this session
    // (see ResolveCommand_DotnetMuxer_PrependsEntryAssemblyLocation's comment above).

    [Fact(DisplayName =
        "FR-059: daemon-background-mode 6.3: propagateBackgroundWorker: true appends --background-worker on the dotnet-muxer branch")]
    public void ResolveCommand_PropagateBackgroundWorkerTrue_AppendsOnDotnetMuxerBranch()
    {
        var cmd = DaemonRelaunch.ResolveCommand(
            processPath:               "dotnet",
            originalArgs:              ["--port", "8080"],
            entryAssemblyLocation:     "OpenWSFZ.Daemon.dll",
            currentPid:                4242,
            propagateBackgroundWorker: true);

        cmd.Arguments.Should().Equal(
            "OpenWSFZ.Daemon.dll", "--port", "8080", "--relaunched-from", "4242", "--background-worker");
    }

    [Fact(DisplayName =
        "FR-059: daemon-background-mode 6.3: propagateBackgroundWorker: true appends --background-worker on the apphost branch")]
    public void ResolveCommand_PropagateBackgroundWorkerTrue_AppendsOnApphostBranch()
    {
        var cmd = DaemonRelaunch.ResolveCommand(
            processPath:               "OpenWSFZ.Daemon",
            originalArgs:              ["--config", "app.json"],
            entryAssemblyLocation:     "OpenWSFZ.Daemon.dll", // unused on this branch
            currentPid:                99,
            propagateBackgroundWorker: true);

        cmd.Arguments.Should().Equal(
            "--config", "app.json", "--relaunched-from", "99", "--background-worker");
    }

    [Fact(DisplayName =
        "daemon-background-mode 6.3: propagateBackgroundWorker: false (default/unchanged case) never appends --background-worker")]
    public void ResolveCommand_PropagateBackgroundWorkerFalse_NeverAppends()
    {
        var muxerCmd = DaemonRelaunch.ResolveCommand(
            "dotnet", ["--port", "9090"], "OpenWSFZ.Daemon.dll", 7, propagateBackgroundWorker: false);
        var apphostCmd = DaemonRelaunch.ResolveCommand(
            "OpenWSFZ.Daemon", ["--port", "9090"], "OpenWSFZ.Daemon.dll", 7, propagateBackgroundWorker: false);
        // Also confirm the default parameter value (no argument passed at all) behaves identically.
        var defaultCmd = DaemonRelaunch.ResolveCommand(
            "OpenWSFZ.Daemon", ["--port", "9090"], "OpenWSFZ.Daemon.dll", 7);

        muxerCmd.Arguments.Should().NotContain("--background-worker");
        apphostCmd.Arguments.Should().NotContain("--background-worker");
        defaultCmd.Arguments.Should().NotContain("--background-worker");
    }

    [Fact(DisplayName =
        "daemon-background-mode 6.3: --background-worker is appended alongside --relaunched-from, not in place of it")]
    public void ResolveCommand_PropagateBackgroundWorkerTrue_RelaunchedFromStillPresent()
    {
        var cmd = DaemonRelaunch.ResolveCommand(
            "OpenWSFZ.Daemon", [], "OpenWSFZ.Daemon.dll", 123, propagateBackgroundWorker: true);

        cmd.Arguments.Should().Equal("--relaunched-from", "123", "--background-worker");
    }

    // ── daemon-background-mode defect fix: no duplicate flags across successive restarts ────
    // Found live: restarting a background instance twice in a row produced
    // "--relaunched-from 28368 --background-worker --relaunched-from 23596 --background-worker"
    // — originalArgs (this process's own command line) already carried the flags from its own
    // spawn, and the pre-fix ResolveCommand appended a fresh pair on top unconditionally.

    [Fact(DisplayName =
        "daemon-background-mode defect fix: a stale --relaunched-from in originalArgs is replaced, not duplicated")]
    public void ResolveCommand_OriginalArgsContainStaleRelaunchedFrom_IsReplacedNotDuplicated()
    {
        var cmd = DaemonRelaunch.ResolveCommand(
            processPath:   "OpenWSFZ.Daemon",
            originalArgs:  ["--port", "8080", "--relaunched-from", "111"],
            entryAssemblyLocation: "OpenWSFZ.Daemon.dll",
            currentPid:    222);

        // The stale --relaunched-from 111 must be stripped, leaving exactly one occurrence
        // naming the CURRENT process being replaced.
        cmd.Arguments.Should().Equal("--port", "8080", "--relaunched-from", "222");
    }

    [Fact(DisplayName =
        "daemon-background-mode defect fix: a stale --background-worker in originalArgs is not duplicated")]
    public void ResolveCommand_OriginalArgsContainStaleBackgroundWorker_IsNotDuplicated()
    {
        var cmd = DaemonRelaunch.ResolveCommand(
            processPath:   "OpenWSFZ.Daemon",
            originalArgs:  ["--relaunched-from", "111", "--background-worker"],
            entryAssemblyLocation: "OpenWSFZ.Daemon.dll",
            currentPid:    222,
            propagateBackgroundWorker: true);

        // Exactly one --relaunched-from and one --background-worker must be present,
        // regardless of how many times this instance has already been relaunched before.
        cmd.Arguments.Should().Equal("--relaunched-from", "222", "--background-worker");
        cmd.Arguments.Count(a => a == "--background-worker").Should().Be(1);
        cmd.Arguments.Count(a => a == "--relaunched-from").Should().Be(1);
    }

    [Fact(DisplayName =
        "daemon-background-mode defect fix: repeated relaunches never accumulate flags across multiple ResolveCommand calls")]
    public void ResolveCommand_SimulatedRepeatedRestarts_NeverAccumulatesFlags()
    {
        // Simulates three successive restarts of a background instance, each feeding the
        // previous call's resolved arguments back in as the next call's originalArgs — exactly
        // how a real process's own Environment.GetCommandLineArgs() would look after being
        // relaunched multiple times in a row.
        var args = new[] { "--port", "8080" };

        for (var pid = 100; pid <= 300; pid += 100)
        {
            var cmd = DaemonRelaunch.ResolveCommand(
                "OpenWSFZ.Daemon", args, "OpenWSFZ.Daemon.dll", pid, propagateBackgroundWorker: true);
            args = cmd.Arguments;
        }

        args.Count(a => a == "--relaunched-from").Should().Be(1,
            "three successive restarts must never leave more than one --relaunched-from behind");
        args.Count(a => a == "--background-worker").Should().Be(1,
            "three successive restarts must never leave more than one --background-worker behind");
        // The final command must reflect only the most recent PID being replaced.
        args.Should().Equal("--port", "8080", "--relaunched-from", "300", "--background-worker");
    }

    [Fact(DisplayName =
        "daemon-background-mode defect fix: originalArgs with no pre-existing flags is unaffected")]
    public void ResolveCommand_OriginalArgsWithoutPriorFlags_Unaffected()
    {
        var cmd = DaemonRelaunch.ResolveCommand(
            "OpenWSFZ.Daemon", ["--port", "8080", "--config", "app.json"], "OpenWSFZ.Daemon.dll", 42);

        cmd.Arguments.Should().Equal(
            "--port", "8080", "--config", "app.json", "--relaunched-from", "42");
    }
}
