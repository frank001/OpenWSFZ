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
using OpenWSFZ.TestSupport;
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

    // ── 8.3d — F1 regression: Upgrade header on non-WS path must NOT bypass auth ─

    [Fact(DisplayName = "SEC-002: 8.3d: 'Upgrade: websocket' header on REST path from non-loopback → 401 (F1 regression)")]
    public async Task PassphraseAuth_UpgradeHeaderOnRestPath_Returns401()
    {
        // Regression guard for F1 (QA review R1): the isWebSocketUpgrade bypass in the
        // auth middleware must be scoped to /api/v1/ws only.  A plain REST endpoint
        // (e.g. /api/v1/config) that carries 'Upgrade: websocket' must still return 401
        // from a non-loopback origin — not 200.
        using var client = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{_spoofedPort}") };
        using var request = new HttpRequestMessage(HttpMethod.Get, "/api/v1/config");
        request.Headers.TryAddWithoutValidation("Upgrade", "websocket");

        var response = await client.SendAsync(request);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized,
            "a REST endpoint with 'Upgrade: websocket' header must still require auth from a non-loopback origin");
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

    // ── 8.5 — API paths still return 401, not redirect ───────────────────────

    [Fact(DisplayName = "8.5: PassphraseAuthPolicy — GET /api/v1/status without key from non-loopback → 401 (not 302)")]
    public async Task PassphraseAuth_ApiPath_NoKey_Returns401NotRedirect()
    {
        // Regression guard: the redirect-to-login behaviour added for browser page-loads
        // must NOT apply to /api/ paths — JS needs a plain 401 to detect auth failure.
        using var client = new HttpClient(new HttpClientHandler { AllowAutoRedirect = false })
        {
            BaseAddress = new Uri($"http://127.0.0.1:{_spoofedPort}"),
        };

        var response = await client.GetAsync("/api/v1/status");

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized,
            "/api/ paths must return 401 (not a redirect) so JavaScript can handle auth failure");
    }

    // ── 8.6 — Non-API page-loads redirect to /login.html ─────────────────────

    [Fact(DisplayName = "8.6: PassphraseAuthPolicy — GET / without key from non-loopback → 302 to /login.html?return=%2F")]
    public async Task PassphraseAuth_RootPath_NoKey_RedirectsToLogin()
    {
        // AllowAutoRedirect = false so we can inspect the 302 response directly.
        using var client = new HttpClient(new HttpClientHandler { AllowAutoRedirect = false })
        {
            BaseAddress = new Uri($"http://127.0.0.1:{_spoofedPort}"),
        };

        var response = await client.GetAsync("/");

        response.StatusCode.Should().Be(HttpStatusCode.Redirect,
            "a browser page-load for / from a non-loopback origin without a key must redirect to /login.html");
        response.Headers.Location?.OriginalString.Should().Be("/login.html?return=%2F",
            "the redirect target must include ?return=%2F so login.html can navigate back to /");
    }

    // ── 8.7 — /login.html is served without auth (middleware whitelist) ───────

    [Fact(DisplayName = "8.7: PassphraseAuthPolicy — GET /login.html without key from non-loopback → 200")]
    public async Task PassphraseAuth_LoginPage_NoKey_Returns200()
    {
        // The auth middleware must whitelist /login.html so the browser can reach it
        // without a passphrase.  web/login.html is copied to the test output directory
        // by the ItemGroup in OpenWSFZ.Web.Tests.csproj (same mechanism as index.html).
        using var client = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{_spoofedPort}") };

        var response = await client.GetAsync("/login.html");

        response.StatusCode.Should().Be(HttpStatusCode.OK,
            "/login.html must be served without auth so a remote browser can reach the login page");
    }

    // ── 8.8 — Static assets are exempt from auth (D-LAN-004) ─────────────────

    [Theory(DisplayName = "8.8: PassphraseAuthPolicy — static asset paths without key from non-loopback → not 302/401")]
    [InlineData("/css/app.css")]
    [InlineData("/js/main.js")]
    [InlineData("/favicon.ico")]
    public async Task StaticAssets_AreServed_WithoutKey_OnNonLoopback(string path)
    {
        // Browsers do not propagate ?key= to sub-resource requests.  After the
        // initial authenticated page-load, every <link rel="stylesheet"> and
        // <script type="module"> fetch arrives without a key.  The auth middleware
        // must whitelist /css/, /js/, and /favicon.ico so the page can render.
        //
        // web/ files are copied to the test output directory by the csproj ItemGroup,
        // so the assets exist and must return 200.  Asserting "not 302 / not 401" is
        // the critical gate; the 200 assertion provides belt-and-braces coverage.
        using var client = new HttpClient(new HttpClientHandler { AllowAutoRedirect = false })
        {
            BaseAddress = new Uri($"http://127.0.0.1:{_spoofedPort}"),
        };

        var response = await client.GetAsync(path);

        response.StatusCode.Should().NotBe(HttpStatusCode.Redirect,
            $"{path} must not be auth-redirected to /login.html — browsers cannot carry ?key= into sub-resource requests");
        response.StatusCode.Should().NotBe(HttpStatusCode.Unauthorized,
            $"{path} must not return 401");
        response.StatusCode.Should().Be(HttpStatusCode.OK,
            $"{path} is a static asset present in the test web root and must be served without auth");
    }

    // ── 8.9 — Non-root page-load redirect preserves original path (D-LAN-005) ─

    [Fact(DisplayName = "8.9: PassphraseAuthPolicy — GET /settings.html without key from non-loopback → 302 with return=%2Fsettings.html")]
    public async Task PassphraseAuth_SettingsPage_NoKey_RedirectsToLoginWithReturn()
    {
        // D-LAN-005: when the operator navigates directly to /settings.html without a
        // key, the auth middleware must include ?return=%2Fsettings.html in the redirect
        // so that login.html can land on the originally-requested page after login.
        using var client = new HttpClient(new HttpClientHandler { AllowAutoRedirect = false })
        {
            BaseAddress = new Uri($"http://127.0.0.1:{_spoofedPort}"),
        };

        var response = await client.GetAsync("/settings.html");

        response.StatusCode.Should().Be(HttpStatusCode.Redirect,
            "/settings.html from a non-loopback origin without a key must redirect to the login page");
        response.Headers.Location?.OriginalString.Should().Be("/login.html?return=%2Fsettings.html",
            "the redirect must include ?return=%2Fsettings.html so post-login navigation lands on Settings");
    }

    // ── 8.10 — SEC-002B: WS auth-frame protocol for non-loopback connections ──

    [Fact(DisplayName = "SEC-002: 8.10a: WS auth-frame — correct key from non-loopback → connection stays open")]
    public async Task WsAuthFrame_CorrectKey_NonLoopback_ConnectionRemainsOpen()
    {
        // SEC-002B: Browser WS clients no longer send ?key= in the URL.
        // Instead, the first WS frame carries {"type":"auth","key":"..."}.
        // The server must accept it and proceed with normal heartbeats.
        var wsUri = new Uri($"ws://127.0.0.1:{_spoofedPort}/api/v1/ws");
        using var ws = new System.Net.WebSockets.ClientWebSocket();
        await ws.ConnectAsync(wsUri, CancellationToken.None);

        // Send auth frame immediately (mirrors ws.js behaviour after SEC-002B).
        var authFrame = System.Text.Json.JsonSerializer.SerializeToUtf8Bytes(
            new { type = "auth", key = "secret" });
        await ws.SendAsync(authFrame, System.Net.WebSockets.WebSocketMessageType.Text,
            endOfMessage: true, CancellationToken.None);

        // The connection must STAY open (a wrong key would close it with 4001). Poll for a
        // non-Open state and require it never occurs within the window, instead of a bare fixed
        // delay (fix-flaky-test-delay-synchronization) — equivalent to the original "wait, then
        // assert still Open" check but bounded by a real condition.
        var closed = async () => await Poll.UntilAsync(
            () => ws.State != System.Net.WebSockets.WebSocketState.Open,
            timeout: TimeSpan.FromMilliseconds(500));
        await closed.Should().ThrowAsync<TimeoutException>();

        ws.State.Should().Be(System.Net.WebSockets.WebSocketState.Open,
            "a correct auth frame from a non-loopback origin must keep the connection open");

        await ws.CloseAsync(System.Net.WebSockets.WebSocketCloseStatus.NormalClosure,
            "done", CancellationToken.None);
    }

    [Fact(DisplayName = "SEC-002: 8.10b: WS auth-frame — wrong key from non-loopback → close code 4001")]
    public async Task WsAuthFrame_WrongKey_NonLoopback_ClosedWith4001()
    {
        // SEC-002B: A wrong key in the auth frame must cause the server to close
        // the socket with application-defined close code 4001.
        var wsUri = new Uri($"ws://127.0.0.1:{_spoofedPort}/api/v1/ws");
        using var ws = new System.Net.WebSockets.ClientWebSocket();
        await ws.ConnectAsync(wsUri, CancellationToken.None);

        var authFrame = System.Text.Json.JsonSerializer.SerializeToUtf8Bytes(
            new { type = "auth", key = "wrong-key" });
        await ws.SendAsync(authFrame, System.Net.WebSockets.WebSocketMessageType.Text,
            endOfMessage: true, CancellationToken.None);

        // Drain until close.
        var buffer = new byte[256];
        System.Net.WebSockets.WebSocketReceiveResult result;
        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(5));
        try
        {
            do
            {
                result = await ws.ReceiveAsync(buffer, cts.Token);
            } while (result.MessageType != System.Net.WebSockets.WebSocketMessageType.Close);
        }
        catch (OperationCanceledException)
        {
            throw new TimeoutException("Server did not close the WS connection within 5 seconds.");
        }

        ((int)ws.CloseStatus!.Value).Should().Be(4001,
            "SEC-002B: wrong auth key must cause a close with code 4001");
    }

    [Fact(DisplayName = "SEC-002: 8.10c: WS auth-frame — no frame sent from non-loopback → close code 4001 within 5 s")]
    public async Task WsAuthFrame_NoFrame_NonLoopback_ClosedWith4001()
    {
        // SEC-002B: A non-loopback connection that never sends an auth frame
        // must be closed with 4001 after the server's 5-second timeout.
        var wsUri = new Uri($"ws://127.0.0.1:{_spoofedPort}/api/v1/ws");
        using var ws = new System.Net.WebSockets.ClientWebSocket();
        await ws.ConnectAsync(wsUri, CancellationToken.None);

        // Do NOT send an auth frame — just wait for the server to close us out.
        var buffer = new byte[256];
        System.Net.WebSockets.WebSocketReceiveResult result;
        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(8));
        try
        {
            do
            {
                result = await ws.ReceiveAsync(buffer, cts.Token);
            } while (result.MessageType != System.Net.WebSockets.WebSocketMessageType.Close);
        }
        catch (OperationCanceledException)
        {
            throw new TimeoutException("Server did not close the WS connection within 8 seconds.");
        }

        ((int)ws.CloseStatus!.Value).Should().Be(4001,
            "SEC-002B: missing auth frame must cause a close with code 4001");
    }
}
