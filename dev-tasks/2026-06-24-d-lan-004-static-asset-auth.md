# Dev Handoff — D-LAN-004: Static assets auth-gated on LAN address

**Date:** 2026-06-24
**Branch:** `fix/lan-remote-access-browser-auth` (continue on current branch — same change set)
**Defect ID:** D-LAN-004
**Severity:** Blocker — the LAN URL is entirely non-functional

---

## Context

The `lan-remote-access` feature gates the LAN binding behind a passphrase supplied as a
`?key=` query parameter. Commit `c59219d` introduced an auth middleware in `WebApp.cs`
whose whitelist exempts only `/login.html`. Every other request — including static assets
(`/css/app.css`, `/js/main.js`, etc.) — must pass `IAuthPolicy.IsAuthorized`.

**Browsers do not propagate query parameters to sub-resource requests.** The initial
page load at `http://10.0.1.35:8080/?key=ek4430pl` passes auth and delivers the HTML.
The browser then fetches `css/app.css` and `js/main.js` as plain relative URLs *without*
`?key=`. Both are `302`-redirected to `/login.html`; the login page HTML is served in
their place. The browser discards the CSS (wrong MIME for `<link rel="stylesheet">`) and
refuses to execute the JS modules (wrong MIME for `<script type="module">`). The page
renders as an unstyled, non-interactive shell.

Confirmed programmatically:
```
GET http://10.0.1.35:8080/css/app.css  (no key)  →  302 /login.html
GET http://10.0.1.35:8080/js/main.js   (no key)  →  302 /login.html
```

---

## Root cause — file and line

**`src/OpenWSFZ.Web/WebApp.cs` lines 135–143 (auth middleware whitelist):**

```csharp
app.Use(async (ctx, next) =>
{
    // Whitelist: the login page is always served without auth so that
    // a remote browser can reach it before it has a passphrase.
    if (ctx.Request.Path.StartsWithSegments("/login.html", StringComparison.OrdinalIgnoreCase))
    {
        await next(ctx);
        return;
    }
    // ... auth check for everything else
```

Only `/login.html` is whitelisted. `/css/`, `/js/`, `/favicon.ico` and any other static
assets are not.

---

## Actions

### 1. Extend the auth middleware whitelist in `WebApp.cs`

In the auth middleware lambda (lines 135–168 of `WebApp.cs`), replace the single
`/login.html` check with a helper that also exempts static asset directories:

```csharp
// Static assets that must be reachable before authentication (browser
// cannot carry ?key= into sub-resource requests):
//   /login.html  — the auth UI itself
//   /css/        — stylesheets
//   /js/         — ES module scripts
//   /favicon.ico — browser chrome (avoids a spurious 302 in the console)
// API paths are never in this list — they must always be gated.
static bool IsPublicPath(PathString path) =>
    path.StartsWithSegments("/login.html",  StringComparison.OrdinalIgnoreCase) ||
    path.StartsWithSegments("/css",         StringComparison.OrdinalIgnoreCase) ||
    path.StartsWithSegments("/js",          StringComparison.OrdinalIgnoreCase) ||
    path.Equals("/favicon.ico",             StringComparison.OrdinalIgnoreCase);

app.Use(async (ctx, next) =>
{
    if (IsPublicPath(ctx.Request.Path))
    {
        await next(ctx);
        return;
    }

    var remoteIp      = ctx.Connection.RemoteIpAddress;
    var apiKeyHeader  = ctx.Request.Headers["X-Api-Key"].ToString();
    var keyQueryParam = ctx.Request.Query["key"].ToString();

    if (!authPolicy.IsAuthorized(
            remoteIp,
            apiKeyHeader.Length  > 0 ? apiKeyHeader  : null,
            keyQueryParam.Length > 0 ? keyQueryParam : null))
    {
        if (ctx.Request.Path.StartsWithSegments("/api", StringComparison.OrdinalIgnoreCase))
        {
            ctx.Response.StatusCode = StatusCodes.Status401Unauthorized;
            return;
        }

        ctx.Response.Redirect("/login.html");
        return;
    }

    await next(ctx);
});
```

If the `web/` directory contains any other top-level static paths (images, fonts, etc.),
extend `IsPublicPath` accordingly.

> **Security note:** Exempting `/css/` and `/js/` from auth is acceptable here — these
> files contain no sensitive data, and a LAN-access attacker who knows the path gets only
> the application shell without any data or control. The auth boundary is correctly on
> the API and WebSocket endpoints.

### 2. Update (or add) the auth middleware integration test

In `tests/OpenWSFZ.Web.Tests/AuthMiddlewareTests.cs`, add test cases verifying that static
assets are served without a key on the LAN binding:

```csharp
[Theory]
[InlineData("/css/app.css")]
[InlineData("/js/main.js")]
[InlineData("/favicon.ico")]
public async Task StaticAssets_Arve_ServedWithoutKey_OnLanAddress(string path)
{
    // Arrange: use a test factory configured with PassphraseAuthPolicy and LAN bind.
    // (Reuse the existing LAN-bind test fixture pattern from AuthMiddlewareTests.cs.)

    // Act: GET the asset with no key, from a non-loopback remote IP.

    // Assert: response is NOT 302 and NOT 401.
    //         (The asset itself may be 200 or 404 depending on whether the web root
    //          is wired in tests — asserting "not a redirect" is sufficient.)
}
```

### 3. Verify manually

With the app running on `10.0.1.35:8080`:

1. Open `http://10.0.1.35:8080/?key=ek4430pl` in a browser.
2. Confirm the page renders with the dark theme (CSS loaded).
3. Confirm the WebSocket connects — status bar shows "Connected" and audio device name.
4. Confirm decodes arrive if a signal is present, or "No decodes yet" is shown (not
   the static placeholder text).
5. Open DevTools → Network: confirm `css/app.css` and `js/main.js` return `200`, not `302`.

---

## Acceptance criteria (QA review)

- [ ] `GET /css/app.css` on LAN address without `?key=` → `200` (not `302`)
- [ ] `GET /js/main.js` on LAN address without `?key=` → `200` (not `302`)
- [ ] `GET /` on LAN address without any key → `302 /login.html` (still gated)
- [ ] `GET /api/v1/status` on LAN address without key → `401` (API still gated)
- [ ] `http://10.0.1.35:8080/?key=ek4430pl` in browser → fully styled, WebSocket connects
- [ ] All existing `AuthMiddlewareTests` tests remain green
- [ ] New static-asset exemption tests green
- [ ] Full test suite green: `dotnet test OpenWSFZ.slnx -c Release`

---

## References

- OpenSpec change: `openspec/changes/lan-remote-access/`
- Implementing commits: `81cf2ac` (feat), `c59219d` (fix), `9a6e1bb` (test isolation)
- Auth middleware: `src/OpenWSFZ.Web/WebApp.cs` lines 134–168
- Auth policy: `src/OpenWSFZ.Web/PassphraseAuthPolicy.cs`
- Client-side key bootstrap: `web/js/api.js` lines 26–39 (`bootstrapApiKeyFromUrl`)
- WebSocket key propagation: `web/js/ws.js` lines 29–33 (`wsUrl`)
