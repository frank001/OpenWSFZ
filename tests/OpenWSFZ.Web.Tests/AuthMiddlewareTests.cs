using System.Net;
using System.Net.WebSockets;
using System.Text;
using FluentAssertions;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Web;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Integration tests for the auth middleware wired in <see cref="WebApp.Create"/>
/// (tasks 8.1 – 8.4, lan-remote-access).
/// </summary>
/// <remarks>
/// <para>
/// The <see cref="WebApplicationFactory{TProgram}"/>-based test client always presents
/// <c>127.0.0.1</c> (loopback) as its remote address.  To exercise non-loopback
/// rejection (401 scenarios), tests that require a non-loopback origin use a
/// <see cref="RemoteIpSpoofFilter"/> — an <c>IStartupFilter</c> that prepends a
/// middleware shim overriding <c>HttpContext.Connection.RemoteIpAddress</c> to a
/// LAN address before the auth middleware runs.
/// </para>
/// <para>
/// Tests that verify the loopback bypass (8.4) require no such shim and use a plain
/// loopback origin.
/// </para>
/// </remarks>
public sealed class AuthMiddlewareTests : IAsyncLifetime
{
    // One real-server instance per test class (started once, stopped in DisposeAsync).
    private WebApplication? _spoofedApp;
    private int             _spoofedPort;

    private WebApplication? _loopbackPassApp;
    private int             _loopbackPassPort;

    private static readonly IPAddress NonLoopbackIp = IPAddress.Parse("192.168.1.99");

    // ── IStartupFilter: prepend middleware that spoofs RemoteIpAddress ─────────

    /// <summary>
    /// Prepends a middleware shim to the request pipeline that overrides
    /// <c>HttpContext.Connection.RemoteIpAddress</c> so that auth tests can
    /// simulate non-loopback origins without a real LAN client.
    /// </summary>
    private sealed class RemoteIpSpoofFilter : IStartupFilter
    {
        private readonly IPAddress _spoofedIp;

        internal RemoteIpSpoofFilter(IPAddress spoofedIp) => _spoofedIp = spoofedIp;

        public Action<IApplicationBuilder> Configure(Action<IApplicationBuilder> next) =>
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

    // ── Fixture setup ─────────────────────────────────────────────────────────

    public async Task InitializeAsync()
    {
        // Server A: PassphraseAuthPolicy + spoofed non-loopback remote IP.
        // Used by test 8.2 (REST 401) and 8.3 (WS 401).
        _spoofedApp = WebApp.Create(
            port: 0,
            configureServices: services =>
            {
                // Override default NullAuthPolicy — last-wins in .NET DI.
                services.AddSingleton<IAuthPolicy>(new PassphraseAuthPolicy("secret"));
                // Spoof every request's remote IP to a non-loopback address.
                services.AddTransient<IStartupFilter>(_ =>
                    new RemoteIpSpoofFilter(NonLoopbackIp));
            });
        await _spoofedApp.StartAsync();
        _spoofedPort = BoundPort(_spoofedApp);

        // Server B: PassphraseAuthPolicy + no IP spoof (loopback client — loopback bypass).
        // Used by test 8.4 (loopback bypass always-200).
        _loopbackPassApp = WebApp.Create(
            port: 0,
            configureServices: services =>
            {
                services.AddSingleton<IAuthPolicy>(new PassphraseAuthPolicy("secret"));
            });
        await _loopbackPassApp.StartAsync();
        _loopbackPassPort = BoundPort(_loopbackPassApp);
    }

    public async Task DisposeAsync()
    {
        if (_spoofedApp    is not null) { await _spoofedApp.StopAsync();    await _spoofedApp.DisposeAsync(); }
        if (_loopbackPassApp is not null) { await _loopbackPassApp.StopAsync(); await _loopbackPassApp.DisposeAsync(); }
    }

    private static int BoundPort(WebApplication app)
    {
        var feature = app.Services
            .GetRequiredService<IServer>()
            .Features.Get<IServerAddressesFeature>()!;
        return new Uri(feature.Addresses.First()).Port;
    }

    // ── 8.1 — NullAuthPolicy: existing tests unaffected ──────────────────────
    // Covered by StaticAssetsIntegrationTests and StatusAndBindingTests which use
    // the default NullAuthPolicy (via WebTestFactory / RealServerFixture).
    // This test provides an explicit smoke-check for the auth middleware not blocking
    // when NullAuthPolicy is registered.

    [Fact(DisplayName = "8.1: NullAuthPolicy — GET /api/v1/status returns 200 (no regression)")]
    public async Task NullAuthPolicy_StatusReturns200()
    {
        // Use a standalone server with default NullAuthPolicy (no overrides).
        var app = WebApp.Create(port: 0);
        await app.StartAsync();
        var port   = BoundPort(app);
        using var client = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{port}") };

        try
        {
            var response = await client.GetAsync("/api/v1/status");
            response.StatusCode.Should().Be(HttpStatusCode.OK,
                "NullAuthPolicy must not block any request — existing tests must be unaffected");
        }
        finally
        {
            await app.StopAsync();
            await app.DisposeAsync();
        }
    }

    // ── 8.2 — PassphraseAuthPolicy: REST endpoint auth ───────────────────────

    [Fact(DisplayName = "8.2a: PassphraseAuthPolicy — GET /api/v1/status with X-Api-Key: secret → 200")]
    public async Task PassphraseAuth_CorrectHeader_Returns200()
    {
        using var client = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{_spoofedPort}") };
        using var req    = new HttpRequestMessage(HttpMethod.Get, "/api/v1/status");
        req.Headers.Add("X-Api-Key", "secret");

        var response = await client.SendAsync(req);

        response.StatusCode.Should().Be(HttpStatusCode.OK,
            "correct X-Api-Key must be accepted even from non-loopback origin");
    }

    [Fact(DisplayName = "8.2b: PassphraseAuthPolicy — GET /api/v1/status with X-Api-Key: wrong → 401")]
    public async Task PassphraseAuth_WrongHeader_Returns401()
    {
        using var client = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{_spoofedPort}") };
        using var req    = new HttpRequestMessage(HttpMethod.Get, "/api/v1/status");
        req.Headers.Add("X-Api-Key", "wrong");

        var response = await client.SendAsync(req);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized,
            "wrong X-Api-Key from non-loopback must return 401");
    }

    [Fact(DisplayName = "8.2c: PassphraseAuthPolicy — GET /api/v1/status with no X-Api-Key → 401")]
    public async Task PassphraseAuth_NoHeader_Returns401()
    {
        using var client = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{_spoofedPort}") };

        var response = await client.GetAsync("/api/v1/status");

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized,
            "request without X-Api-Key from non-loopback must return 401");
    }

    // ── 8.3 — PassphraseAuthPolicy: WebSocket auth ───────────────────────────
    // WebSocket upgrade requests are HTTP GETs — the auth middleware intercepts them
    // before the socket is accepted.  Test the 401 cases via plain HTTP GET so that
    // we can inspect the status code before any WS handshake occurs.

    [Fact(DisplayName = "8.3a: PassphraseAuthPolicy — /api/v1/ws?key=secret from loopback → 101")]
    public async Task PassphraseAuth_WsCorrectKey_Loopback_UpgradeSucceeds()
    {
        // Use the loopback server (no IP spoof) — loopback bypass + correct key → 101.
        var wsUri = new Uri($"ws://127.0.0.1:{_loopbackPassPort}/api/v1/ws?key=secret");
        using var ws = new ClientWebSocket();
        await ws.ConnectAsync(wsUri, CancellationToken.None);

        ws.State.Should().Be(WebSocketState.Open,
            "WebSocket upgrade with correct key from loopback must succeed (loopback bypass)");

        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None);
    }

    [Fact(DisplayName = "8.3b: PassphraseAuthPolicy — /api/v1/ws?key=wrong from non-loopback → 401")]
    public async Task PassphraseAuth_WsWrongKey_Returns401()
    {
        // Use plain HTTP GET to test auth middleware rejection before any WS handshake.
        // Auth middleware returns 401 before the WebSocket handler runs, so the
        // server returns a normal HTTP 401 response.
        using var client = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{_spoofedPort}") };

        var response = await client.GetAsync("/api/v1/ws?key=wrong");

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized,
            "wrong ?key= from non-loopback must return 401 before WS upgrade is attempted");
    }

    [Fact(DisplayName = "8.3c: PassphraseAuthPolicy — /api/v1/ws (no key) from non-loopback → 401")]
    public async Task PassphraseAuth_WsNoKey_Returns401()
    {
        using var client = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{_spoofedPort}") };

        var response = await client.GetAsync("/api/v1/ws");

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized,
            "WebSocket upgrade without ?key= from non-loopback must return 401");
    }

    // ── 8.4 — Loopback bypass ─────────────────────────────────────────────────

    [Fact(DisplayName = "8.4: PassphraseAuthPolicy — GET /api/v1/status from 127.0.0.1 without key → 200")]
    public async Task PassphraseAuth_LoopbackNoKey_Returns200()
    {
        // Client connects from loopback (127.0.0.1 — no IP spoof).
        // PassphraseAuthPolicy must allow this regardless of missing X-Api-Key (D1).
        using var client = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{_loopbackPassPort}") };

        var response = await client.GetAsync("/api/v1/status");

        response.StatusCode.Should().Be(HttpStatusCode.OK,
            "loopback origin must bypass passphrase check and always receive 200 (D1)");
    }
}
