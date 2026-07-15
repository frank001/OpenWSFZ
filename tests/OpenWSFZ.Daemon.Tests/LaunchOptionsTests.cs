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
}
