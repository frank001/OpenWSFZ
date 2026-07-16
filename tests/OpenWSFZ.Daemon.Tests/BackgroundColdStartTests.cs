using FluentAssertions;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="BackgroundColdStart.SpawnAndConfirmAsync"/> (daemon-background-mode,
/// task 5.4): the confirmed-within-budget path (fake/short-circuited status probe), the
/// budget-exhausted path (a short test-only budget override, never the real 5 s), and the
/// spawn-failure path (a resolved executable that does not exist).
/// </summary>
[Trait("Category", "Unit")]
public sealed class BackgroundColdStartTests
{
    private const int TestPort = 59321; // arbitrary — the fake statusProbe never actually connects.

    [Fact(DisplayName =
        "FR-059: daemon-background-mode 5.4: confirmed within the budget reports success and exits 0")]
    public async Task SpawnAndConfirmAsync_ConfirmedWithinBudget_ReportsSuccessAndExitsZero()
    {
        var result = await BackgroundColdStart.SpawnAndConfirmAsync(
            fileName:           RealNoOpExecutable(),
            arguments:          RealNoOpArguments(),
            port:               TestPort,
            logDirectory:       "logs",
            statusProbe:        (_, _) => Task.FromResult(true), // short-circuited: confirmed immediately
            confirmationBudget: TimeSpan.FromSeconds(5),
            pollInterval:       TimeSpan.FromMilliseconds(50));

        result.SpawnSucceeded.Should().BeTrue();
        result.ExitCode.Should().Be(0);
        result.Message.Should().Contain("confirmed listening");
        result.Message.Should().NotContain("could not confirm");
    }

    [Fact(DisplayName =
        "FR-059: daemon-background-mode 5.4: budget exhausted (never confirmed) reports the caveat but still exits 0")]
    public async Task SpawnAndConfirmAsync_BudgetExhausted_ReportsCaveat_StillExitsZero()
    {
        var sw = System.Diagnostics.Stopwatch.StartNew();

        var result = await BackgroundColdStart.SpawnAndConfirmAsync(
            fileName:           RealNoOpExecutable(),
            arguments:          RealNoOpArguments(),
            port:               TestPort,
            logDirectory:       "logs",
            statusProbe:        (_, _) => Task.FromResult(false), // never confirms
            confirmationBudget: TimeSpan.FromMilliseconds(300),   // short test-only budget — never the real 5s
            pollInterval:       TimeSpan.FromMilliseconds(50));

        sw.Stop();

        result.SpawnSucceeded.Should().BeTrue(
            "the spawn itself succeeded — only confirmation timed out");
        result.ExitCode.Should().Be(0,
            "an unconfirmed-but-spawned child still exits 0 (design.md Decision 5)");
        result.Message.Should().Contain("could not confirm");
        sw.ElapsedMilliseconds.Should().BeGreaterThanOrEqualTo(300,
            "the poll loop must have actually spent the configured budget");
    }

    [Fact(DisplayName =
        "FR-059: daemon-background-mode 5.4: a resolved executable that does not exist fails the spawn and exits non-zero without a false success")]
    public async Task SpawnAndConfirmAsync_SpawnFailure_ExitsNonZero_NoFalseSuccess()
    {
        var result = await BackgroundColdStart.SpawnAndConfirmAsync(
            fileName:     "this-executable-definitely-does-not-exist-xyz123",
            arguments:    [],
            port:         TestPort,
            logDirectory: "logs",
            statusProbe:  (_, _) => Task.FromResult(true)); // must never even be reached

        result.SpawnSucceeded.Should().BeFalse();
        result.ExitCode.Should().NotBe(0, "a spawn failure must never report a successful background launch");
        result.Message.Should().Contain("Failed to spawn");
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    /// <summary>
    /// A real, always-available, near-instant executable to spawn for the "spawn succeeds"
    /// test cases — this project's CI matrix runs ubuntu-latest/macos-latest/windows-latest, so
    /// the choice is platform-branched (mirroring SubprocessAudioDeviceProviderTests's existing
    /// convention) rather than hardcoding a single platform's shell.
    /// </summary>
    private static string RealNoOpExecutable() =>
        OperatingSystem.IsWindows() ? "cmd" : "/bin/sh";

    private static string[] RealNoOpArguments() =>
        OperatingSystem.IsWindows() ? ["/c", "exit 0"] : ["-c", "exit 0"];
}
