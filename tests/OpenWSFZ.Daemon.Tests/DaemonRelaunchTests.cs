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
        var cmd = DaemonRelaunch.ResolveCommand(
            processPath:            @"C:\Program Files\dotnet\dotnet.exe",
            originalArgs:           ["--port", "8080"],
            entryAssemblyLocation:  @"C:\app\OpenWSFZ.Daemon.dll",
            currentPid:             4242);

        cmd.FileName.Should().Be(@"C:\Program Files\dotnet\dotnet.exe",
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
}
