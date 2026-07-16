using FluentAssertions;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="LaunchOptions.Parse"/>, focused on the
/// <c>--relaunched-from &lt;pid&gt;</c> flag added by <c>remote-daemon-restart</c> (task 2.1).
/// The pre-existing <c>--port</c>/<c>--config</c> parsing has no test coverage of its own to
/// extend here — this file's scope is deliberately limited to the new flag.
/// </summary>
[Trait("Category", "Unit")]
public sealed class LaunchOptionsTests
{
    [Fact(DisplayName = "remote-daemon-restart 2.2: --relaunched-from with a valid integer parses correctly")]
    public void Parse_RelaunchedFromWithValidInteger_ParsesCorrectly()
    {
        var options = LaunchOptions.Parse(["--relaunched-from", "12345"]);

        options.RelaunchedFromPid.Should().Be(12345);
    }

    [Fact(DisplayName = "remote-daemon-restart 2.2: absent --relaunched-from parses to null")]
    public void Parse_AbsentRelaunchedFrom_ParsesToNull()
    {
        var options = LaunchOptions.Parse(["--port", "8080"]);

        options.RelaunchedFromPid.Should().BeNull();
    }

    [Fact(DisplayName = "remote-daemon-restart 2.2: no arguments at all parses --relaunched-from to null")]
    public void Parse_NoArguments_RelaunchedFromIsNull()
    {
        var options = LaunchOptions.Parse([]);

        options.RelaunchedFromPid.Should().BeNull();
    }

    [Fact(DisplayName = "remote-daemon-restart 2.2: malformed --relaunched-from value is ignored without throwing, matching --port's tolerance")]
    public void Parse_MalformedRelaunchedFromValue_IgnoredWithoutThrowing()
    {
        var act = () => LaunchOptions.Parse(["--relaunched-from", "not-a-pid"]);

        act.Should().NotThrow();
        LaunchOptions.Parse(["--relaunched-from", "not-a-pid"]).RelaunchedFromPid.Should().BeNull();
    }

    [Fact(DisplayName = "remote-daemon-restart 2.2: --relaunched-from combines with --port and --config unaffected")]
    public void Parse_RelaunchedFromCombinesWithOtherFlags()
    {
        var options = LaunchOptions.Parse(
            ["--port", "9090", "--config", "/tmp/app.json", "--relaunched-from", "42"]);

        options.Port.Should().Be(9090);
        options.ConfigPath.Should().Be("/tmp/app.json");
        options.RelaunchedFromPid.Should().Be(42);
    }

    // ── daemon-background-mode 2.2 ──────────────────────────────────────────────

    [Fact(DisplayName = "daemon-background-mode 2.2: --background present sets Background true")]
    public void Parse_BackgroundPresent_SetsBackgroundTrue()
    {
        var options = LaunchOptions.Parse(["--background"]);

        options.Background.Should().BeTrue();
        options.IsBackgroundWorker.Should().BeFalse();
    }

    [Fact(DisplayName = "daemon-background-mode 2.2: --background-worker present sets IsBackgroundWorker true")]
    public void Parse_BackgroundWorkerPresent_SetsIsBackgroundWorkerTrue()
    {
        var options = LaunchOptions.Parse(["--background-worker"]);

        options.IsBackgroundWorker.Should().BeTrue();
        options.Background.Should().BeFalse();
    }

    [Fact(DisplayName = "daemon-background-mode 2.2: absence of both flags leaves both false")]
    public void Parse_AbsentBackgroundFlags_BothFalse()
    {
        var options = LaunchOptions.Parse(["--port", "8080"]);

        options.Background.Should().BeFalse();
        options.IsBackgroundWorker.Should().BeFalse();
    }

    [Fact(DisplayName = "daemon-background-mode 2.2: no arguments at all leaves both background flags false")]
    public void Parse_NoArguments_BothBackgroundFlagsFalse()
    {
        var options = LaunchOptions.Parse([]);

        options.Background.Should().BeFalse();
        options.IsBackgroundWorker.Should().BeFalse();
    }

    [Fact(DisplayName = "daemon-background-mode 2.2: --background and --background-worker present together both set")]
    public void Parse_BothBackgroundFlagsPresent_BothSet()
    {
        var options = LaunchOptions.Parse(["--background", "--background-worker"]);

        options.Background.Should().BeTrue();
        options.IsBackgroundWorker.Should().BeTrue();
    }

    [Fact(DisplayName = "daemon-background-mode 2.2: --background combines with --port, --config and --relaunched-from")]
    public void Parse_BackgroundCombinesWithOtherFlags()
    {
        var options = LaunchOptions.Parse(
            ["--port", "9090", "--config", "/tmp/app.json", "--relaunched-from", "42",
             "--background", "--background-worker"]);

        options.Port.Should().Be(9090);
        options.ConfigPath.Should().Be("/tmp/app.json");
        options.RelaunchedFromPid.Should().Be(42);
        options.Background.Should().BeTrue();
        options.IsBackgroundWorker.Should().BeTrue();
    }

    [Fact(DisplayName = "daemon-background-mode 2.2: --background as the sole/last argument is still recognised")]
    public void Parse_BackgroundAsLastArgument_StillRecognised()
    {
        // Regression guard: the original parse loop bounded iteration at args.Length - 1
        // (safe only because every pre-existing flag consumes a following value, so the
        // last array element was never a flag worth inspecting on its own). A boolean
        // presence flag like --background has no such value and must be recognised even
        // when it is the very last (or only) argument.
        var options = LaunchOptions.Parse(["--port", "8080", "--background"]);

        options.Background.Should().BeTrue();
        options.Port.Should().Be(8080);
    }

    [Fact(DisplayName = "daemon-background-mode 2.2: duplicate --background occurrences do not throw")]
    public void Parse_DuplicateBackgroundOccurrences_DoesNotThrow()
    {
        var act = () => LaunchOptions.Parse(["--background", "--background"]);

        act.Should().NotThrow();
        LaunchOptions.Parse(["--background", "--background"]).Background.Should().BeTrue();
    }
}
