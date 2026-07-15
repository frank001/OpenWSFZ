using System.Net;
using System.Net.Sockets;
using FluentAssertions;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Tests for <see cref="DaemonStartup.StartWithBindRetryAsync"/> and the surrounding
/// relaunch/non-relaunch startup behaviour it exists to serve (remote-daemon-restart, task 3.5).
/// </summary>
[Trait("Category", "Integration")]
public sealed class DaemonStartupTests
{
    /// <summary>Binds a TCP listener on an OS-assigned ephemeral port and returns the port number.</summary>
    private static int ReserveEphemeralPort()
    {
        using var probe = new TcpListener(IPAddress.Loopback, 0);
        probe.Start();
        var port = ((IPEndPoint)probe.LocalEndpoint).Port;
        probe.Stop();
        return port;
    }

    private static WebApplication BuildMinimalApp(int port)
    {
        var builder = WebApplication.CreateBuilder();
        builder.WebHost.UseUrls($"http://127.0.0.1:{port}");
        builder.Logging.ClearProviders();
        return builder.Build();
    }

    [Fact(DisplayName =
        "remote-daemon-restart 3.5(a): a normal (non-relaunch) startup still fails fast on a port conflict")]
    public async Task NonRelaunchStartup_FailsFastOnPortConflict_NoRetry()
    {
        // This is the code path Program.cs takes when RelaunchedFromPid is null: app.StartAsync()
        // called directly, with no DaemonStartup wrapper — proving that path's behaviour is
        // completely unchanged (immediate failure, no retry delay) requires no wrapper at all.
        var port = ReserveEphemeralPort();
        using var blocker = new TcpListener(IPAddress.Loopback, port);
        blocker.Start();

        try
        {
            await using var app = BuildMinimalApp(port);

            var sw  = System.Diagnostics.Stopwatch.StartNew();
            var act = async () => await app.StartAsync();
            await act.Should().ThrowAsync<IOException>(
                "a bind conflict must surface immediately, exactly as before this change");
            sw.Stop();

            sw.ElapsedMilliseconds.Should().BeLessThan(DaemonStartup.DefaultRetryIntervalMs,
                "a non-relaunch startup must fail on the very first attempt — no retry delay");
        }
        finally
        {
            blocker.Stop();
        }
    }

    [Fact(DisplayName =
        "remote-daemon-restart 3.5(b): a relaunch-flagged startup retries and succeeds once the old instance's port is freed")]
    public async Task RelaunchStartup_RetriesAndSucceeds_OnceOldInstanceReleasesPort()
    {
        var port    = ReserveEphemeralPort();
        var blocker = new TcpListener(IPAddress.Loopback, port);
        blocker.Start();

        // Simulate "old instance still shutting down" — release the port shortly after the
        // retry loop has had a chance to observe at least one failed probe.
        _ = Task.Run(async () =>
        {
            await Task.Delay(300);
            blocker.Stop();
        });

        await using var app = BuildMinimalApp(port);

        var started = await DaemonStartup.StartWithBindRetryAsync(
            () => app.StartAsync(),
            port,
            NullLogger.Instance,
            retryIntervalMs: 100,
            totalBudgetMs:   5000);

        started.Should().BeTrue(
            "the retry loop must keep probing until the competing listener releases the port, " +
            "then perform the one real start");

        await app.StopAsync();
    }

    [Fact(DisplayName =
        "remote-daemon-restart 3.5(c): a relaunch-flagged startup gives up and reports failure once the retry budget is exhausted")]
    public async Task RelaunchStartup_GivesUp_WhenRetryBudgetExhausted()
    {
        var port = ReserveEphemeralPort();
        using var blocker = new TcpListener(IPAddress.Loopback, port);
        blocker.Start(); // never released during this test

        await using var app = BuildMinimalApp(port);

        var sw = System.Diagnostics.Stopwatch.StartNew();
        var started = await DaemonStartup.StartWithBindRetryAsync(
            () => app.StartAsync(),
            port,
            NullLogger.Instance,
            retryIntervalMs: 50,
            totalBudgetMs:   300); // short test-only budget — never wait the real 20 s
        sw.Stop();

        started.Should().BeFalse(
            "the retry loop must give up once the budget is exhausted, not retry forever");
        sw.ElapsedMilliseconds.Should().BeGreaterThanOrEqualTo(300,
            "the loop must have actually spent the configured budget probing");
    }

    [Fact(DisplayName =
        "remote-daemon-restart 3.5: retrying the bind probe never re-invokes startAsync more than once")]
    public async Task RetryLoop_NeverInvokesStartAsyncMoreThanOnce()
    {
        // Regression guard for the Kestrel "Server has already started" pitfall discovered while
        // writing this suite (design.md Decision 4 correction) — startAsync must be called at
        // most once per StartWithBindRetryAsync invocation, never once per probe attempt.
        var port    = ReserveEphemeralPort();
        var blocker = new TcpListener(IPAddress.Loopback, port);
        blocker.Start();
        _ = Task.Run(async () => { await Task.Delay(250); blocker.Stop(); });

        var startAsyncCalls = 0;
        Func<Task> fakeStart = () =>
        {
            Interlocked.Increment(ref startAsyncCalls);
            return Task.CompletedTask;
        };

        var started = await DaemonStartup.StartWithBindRetryAsync(
            fakeStart, port, NullLogger.Instance, retryIntervalMs: 50, totalBudgetMs: 5000);

        started.Should().BeTrue();
        startAsyncCalls.Should().Be(1, "startAsync must be invoked exactly once, after the probe succeeds");
    }
}
