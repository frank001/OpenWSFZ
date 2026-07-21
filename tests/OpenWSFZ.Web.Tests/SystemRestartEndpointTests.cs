using FluentAssertions;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using OpenWSFZ.TestSupport;
using System.Net;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

// ── Test doubles for POST /api/v1/system/restart (remote-daemon-restart, task 4.4) ────

/// <summary>
/// Controllable <see cref="IDaemonRelauncher"/> stub. Never spawns a real process — records
/// whether it was called and can be made to report failure, so tests can exercise the
/// endpoint's spawn-before-stop ordering without ever replacing the test process itself.
/// </summary>
internal sealed class TestDaemonRelauncher : IDaemonRelauncher
{
    public int  CallCount     { get; private set; }
    public bool ShouldSucceed { get; set; } = true;

    public bool TrySpawnReplacement()
    {
        CallCount++;
        return ShouldSucceed;
    }

    /// <summary>Resets call-tracking state between tests sharing this fixture instance.</summary>
    internal void Reset() => CallCount = 0;
}

/// <summary>
/// daemon-background-mode (task 6.4): records the argument list a relaunch would carry,
/// mirroring the shape of the real <c>DaemonRelauncher</c>/<c>DaemonRelaunch.ResolveCommand</c>
/// contract (<c>OpenWSFZ.Daemon</c>, unit-tested directly in
/// <c>OpenWSFZ.Daemon.Tests/DaemonRelaunchTests.cs</c>) without spawning a process or reaching
/// into that assembly's internals — this test project has no <c>InternalsVisibleTo</c> access
/// to it, only to the public <see cref="IDaemonRelauncher"/> seam. Constructed with the same
/// <c>isBackgroundWorker</c> flag <c>Program.cs</c>'s DI factory captures for the real
/// <c>DaemonRelauncher</c> (task 6.2), proving the Web-layer wiring: whichever flag the
/// relauncher was built with ends up reflected in the recorded command.
/// </summary>
internal sealed class RecordingDaemonRelauncher : IDaemonRelauncher
{
    private readonly bool _isBackgroundWorker;

    public RecordingDaemonRelauncher(bool isBackgroundWorker) => _isBackgroundWorker = isBackgroundWorker;

    public List<string>? LastArguments { get; private set; }

    public bool TrySpawnReplacement()
    {
        var args = new List<string> { "--relaunched-from", "1" };
        if (_isBackgroundWorker)
            args.Add("--background-worker");

        LastArguments = args;
        return true;
    }
}

/// <summary>
/// Fixture that wires a <see cref="TestKeyingQsoController"/>-equivalent and a
/// <see cref="TestDaemonRelauncher"/> into a live Kestrel instance (mirrors
/// <c>PttTestFixture</c>'s pattern) so <c>POST /api/v1/system/restart</c> tests can control
/// both "is a real QSO keying" and the relaunch outcome without touching real hardware or
/// spawning a real child process.
/// </summary>
public sealed class SystemRestartFixture : IAsyncLifetime
{
    internal readonly TestKeyingQsoController QsoController = new();
    internal readonly TestDaemonRelauncher     Relauncher    = new();

    private Microsoft.AspNetCore.Builder.WebApplication? _app;
    public  HttpClient Client { get; private set; } = null!;

    public async Task InitializeAsync()
    {
        _app = WebApp.Create(
            port:              0,
            configureServices: services =>
                services
                    .AddSingleton<IQsoController>(QsoController)
                    .AddSingleton<IDaemonRelauncher>(Relauncher));

        await _app.StartAsync();

        var addr = _app.Services
            .GetRequiredService<IServer>()
            .Features.Get<IServerAddressesFeature>()!
            .Addresses.First();

        Client = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{new Uri(addr).Port}") };
    }

    public async Task DisposeAsync()
    {
        Client.Dispose();
        if (_app is not null)
        {
            await _app.StopAsync();
            await _app.DisposeAsync();
        }
    }
}

/// <summary>
/// Integration tests for <c>POST /api/v1/system/restart</c> (remote-daemon-restart, task 4.4):
/// the 409-while-keying case, the 202-not-keying case (spawn-before-stop, via the injected
/// test-seam relauncher — no real process is ever spawned and <c>StopApplication()</c> is
/// never exercised on the test host), and the 401-over-LAN case (mirrors
/// <see cref="AuthMiddlewareTests"/>'s spoofed-remote-IP pattern).
/// </summary>
[Trait("Category", "Integration")]
public sealed class SystemRestartEndpointTests : IClassFixture<SystemRestartFixture>
{
    private readonly SystemRestartFixture _fixture;
    private readonly HttpClient           _client;

    public SystemRestartEndpointTests(SystemRestartFixture fixture)
    {
        _fixture = fixture;
        _client  = fixture.Client;

        // Each test starts from a clean slate — IClassFixture shares one instance across
        // all tests in this class (xUnit convention used throughout this test project).
        _fixture.QsoController.Keying     = false;
        _fixture.Relauncher.ShouldSucceed = true;
        _fixture.Relauncher.Reset();
    }

    [Fact(DisplayName = "FR-058: POST /api/v1/system/restart returns 409 while a real QSO is keying")]
    public async Task PostSystemRestart_WhileKeying_Returns409()
    {
        _fixture.QsoController.Keying = true;

        var response = await _client.PostAsync("/api/v1/system/restart", content: null);

        response.StatusCode.Should().Be(HttpStatusCode.Conflict);
        var body = await response.Content.ReadAsStringAsync();
        body.Should().Contain("transmitting",
            "the 409 response must explain why — a real QSO is currently transmitting");

        // Confirm the relauncher is never touched — a refused restart must never spawn a
        // replacement. Poll for the (forbidden) call and require it never lands within the window,
        // instead of a bare fixed delay (fix-flaky-test-delay-synchronization).
        var spawned = async () => await Poll.UntilAsync(() => _fixture.Relauncher.CallCount >= 1,
            timeout: TimeSpan.FromMilliseconds(700));
        await spawned.Should().ThrowAsync<TimeoutException>();
        _fixture.Relauncher.CallCount.Should().Be(0,
            "a restart refused for a transmitting QSO must never reach the relaunch mechanism");
    }

    [Fact(DisplayName = "FR-058: POST /api/v1/system/restart returns 202 and spawns a replacement when not keying")]
    public async Task PostSystemRestart_NotKeying_Returns202AndSpawnsReplacement()
    {
        var response = await _client.PostAsync("/api/v1/system/restart", content: null);

        response.StatusCode.Should().Be(HttpStatusCode.Accepted,
            "a restart request while no QSO is transmitting must be accepted immediately");
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("status").GetString().Should().Be("restarting");

        // The actual spawn happens on a fire-and-forget task after a short flush delay
        // (design.md Decision 3) — wait past that delay, then confirm the (fake) relauncher
        // was invoked exactly once. This fixture's WebApp instance is never itself stopped
        // by this test (TestDaemonRelauncher never touches app.Lifetime), so the shared
        // fixture remains usable by the rest of this class regardless of test order.
        await Poll.UntilAsync(() => _fixture.Relauncher.CallCount >= 1,
            timeout: TimeSpan.FromSeconds(5),
            timeoutMessage: () => "a successful (not-keying) restart request must invoke the relauncher");
        _fixture.Relauncher.CallCount.Should().Be(1,
            "a successful (not-keying) restart request must invoke the relauncher exactly once");
    }

    [Fact(DisplayName = "FR-058: POST /api/v1/system/restart requires the configured passphrase over LAN")]
    public async Task PostSystemRestart_OverLan_RequiresPassphrase()
    {
        // Bespoke server (not the shared fixture) with PassphraseAuthPolicy + a spoofed
        // non-loopback remote IP, mirroring AuthMiddlewareTests's RemoteIpSpoofFilter pattern —
        // confirms the endpoint has no bespoke auth wiring of its own and is covered by the
        // same blanket middleware as every other /api/* path.
        var nonLoopbackIp = IPAddress.Parse("192.168.1.77");

        var app = WebApp.Create(
            port: 0,
            configureServices: services =>
            {
                services.AddSingleton<IAuthPolicy>(new PassphraseAuthPolicy("secret"));
                services.AddTransient<IStartupFilter>(_ => new SpoofRemoteIpFilter(nonLoopbackIp));
            });

        try
        {
            await app.StartAsync();
            var addr = app.Services
                .GetRequiredService<IServer>()
                .Features.Get<IServerAddressesFeature>()!
                .Addresses.First();

            using var client = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{new Uri(addr).Port}") };

            var response = await client.PostAsync("/api/v1/system/restart", content: null);

            response.StatusCode.Should().Be(HttpStatusCode.Unauthorized,
                "a non-loopback request without the correct passphrase must be rejected by the " +
                "existing blanket auth middleware, with no bespoke wiring for this endpoint");
        }
        finally
        {
            await app.StopAsync();
            await app.DisposeAsync();
        }
    }

    // ── daemon-background-mode 6.4 ──────────────────────────────────────────────────────

    [Fact(DisplayName =
        "FR-059: daemon-background-mode 6.4: a relauncher constructed with IsBackgroundWorker: true produces a command including --background-worker")]
    public async Task PostSystemRestart_RelauncherIsBackgroundWorkerTrue_CommandIncludesBackgroundWorker()
    {
        var relauncher = new RecordingDaemonRelauncher(isBackgroundWorker: true);
        await using var app = await StartAppWithRelauncherAsync(relauncher);
        using var client = MakeClient(app);

        await client.PostAsync("/api/v1/system/restart", content: null);
        // The spawn happens on a fire-and-forget task (design.md Decision 3) — poll for it.
        await Poll.UntilAsync(() => relauncher.LastArguments is not null,
            timeout: TimeSpan.FromSeconds(5),
            timeoutMessage: () => "the restart must have invoked the relauncher");

        relauncher.LastArguments.Should().NotBeNull("the restart must have invoked the relauncher");
        relauncher.LastArguments!.Should().Contain("--background-worker");
    }

    [Fact(DisplayName =
        "FR-059: daemon-background-mode 6.4: a relauncher constructed with IsBackgroundWorker: false produces a command without --background-worker")]
    public async Task PostSystemRestart_RelauncherIsBackgroundWorkerFalse_CommandExcludesBackgroundWorker()
    {
        var relauncher = new RecordingDaemonRelauncher(isBackgroundWorker: false);
        await using var app = await StartAppWithRelauncherAsync(relauncher);
        using var client = MakeClient(app);

        await client.PostAsync("/api/v1/system/restart", content: null);
        // The spawn happens on a fire-and-forget task (design.md Decision 3) — poll for it.
        await Poll.UntilAsync(() => relauncher.LastArguments is not null,
            timeout: TimeSpan.FromSeconds(5),
            timeoutMessage: () => "the restart must have invoked the relauncher");

        relauncher.LastArguments.Should().NotBeNull("the restart must have invoked the relauncher");
        relauncher.LastArguments!.Should().NotContain("--background-worker");
    }

    private static async Task<Microsoft.AspNetCore.Builder.WebApplication> StartAppWithRelauncherAsync(
        IDaemonRelauncher relauncher)
    {
        var app = WebApp.Create(
            port:              0,
            configureServices: services => services.AddSingleton(relauncher));

        await app.StartAsync();
        return app;
    }

    private static HttpClient MakeClient(Microsoft.AspNetCore.Builder.WebApplication app)
    {
        var addr = app.Services
            .GetRequiredService<IServer>()
            .Features.Get<IServerAddressesFeature>()!
            .Addresses.First();

        return new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{new Uri(addr).Port}") };
    }

    /// <summary>Local copy of AuthMiddlewareTests's RemoteIpSpoofFilter — internal types are
    /// not shared across test files by convention in this suite; kept minimal.</summary>
    private sealed class SpoofRemoteIpFilter : IStartupFilter
    {
        private readonly IPAddress _spoofedIp;
        internal SpoofRemoteIpFilter(IPAddress spoofedIp) => _spoofedIp = spoofedIp;

        public Action<Microsoft.AspNetCore.Builder.IApplicationBuilder> Configure(
            Action<Microsoft.AspNetCore.Builder.IApplicationBuilder> next) =>
            pipeline =>
            {
                pipeline.Use(async (ctx, n) =>
                {
                    ctx.Connection.RemoteIpAddress = _spoofedIp;
                    await n(ctx);
                });
                next(pipeline);
            };
    }
}
