# Handoff: LAN Remote Access — Browser Authentication Flow (D-LAN-001/002/003)

**Date:** 2026-06-23  
**QA Investigation:** `logs/openswfz-20260623T211446Z.log`  
**Branch to build from:** `feat/lan-remote-access`

---

## 1. Context

The `lan-remote-access` branch implements backend passphrase authentication correctly: `PassphraseAuthPolicy`, `LanBindPolicy`, and the auth middleware in `WebApp.cs` all function as specified. However, a remote browser (tablet, phone) cannot authenticate at all — it receives an empty 401 with zero bytes and no redirect. Three defects were identified:

- **D-LAN-001**: `api.js` — no `X-Api-Key` header in any `fetch()` call.
- **D-LAN-002**: `ws.js` — no `?key=` parameter in the WebSocket URL.
- **D-LAN-003**: No browser-compatible authentication flow (no login page, no passphrase prompt, no redirect).

The Captain has approved **Option B**: a `/login.html` page that accepts the passphrase, stores it in `sessionStorage`, and navigates to `/?key=<passphrase>`. The auth middleware redirects unauthorized browser page-loads to `/login.html` and bypasses auth for the login page itself.

---

## 2. Branch Name

`fix/lan-remote-access-browser-auth`

Branch from `feat/lan-remote-access`. Do NOT branch from `main` — `main` does not yet contain the remote-access backend work that this fix builds upon.

---

## 3. Actions

### 3.1 — Auth middleware: redirect browser page-loads; whitelist `/login.html`

In `src/OpenWSFZ.Web/WebApp.cs`, modify the auth middleware lambda (lines 135–151 in the current source) to add two behaviours before returning 401:

**a) Whitelist `/login.html`:**  
If the request path is `/login.html`, call `await next(ctx)` and return. Do not run the auth check.

**b) Redirect non-API unauthorized requests to `/login.html`:**  
If auth fails AND the path does NOT start with `/api/`, redirect the client to `/login.html` instead of returning a bare 401.

If auth fails AND the path DOES start with `/api/`, continue to return HTTP 401 as before (so the JavaScript `api.js` 401-handler can detect it rather than the browser following a redirect).

The updated middleware logic (replacing the current `if (!authPolicy.IsAuthorized(...))` block) SHALL be:

```csharp
app.Use(async (ctx, next) =>
{
    // Whitelist: login page is always served without auth.
    if (ctx.Request.Path.StartsWithSegments("/login.html", StringComparison.OrdinalIgnoreCase))
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
        // API paths and WebSocket upgrades return 401 so JS can handle them.
        // Browser page-loads (everything else) redirect to the login page.
        if (ctx.Request.Path.StartsWithSegments("/api/", StringComparison.OrdinalIgnoreCase))
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

### 3.2 — Create `web/login.html`

Create a new file `web/login.html`. This page MUST be self-contained (no external CSS or JS files — inline only) so it loads without requiring auth on any dependent asset. It SHALL:

- Display a simple form with a `<input type="password" id="passphrase" autocomplete="current-password">` and a "Connect" submit button.
- Show a brief title: "OpenWSFZ — Remote Access".
- On form submit:
  1. Validate the passphrase field is non-empty; if empty, show an inline error and do NOT navigate.
  2. Store the passphrase in `sessionStorage`: `sessionStorage.setItem('owsfz-api-key', passphrase)`.
  3. Navigate to `/?key=` + `encodeURIComponent(passphrase)` so the auth middleware accepts the initial page load.
- On load, if `sessionStorage.getItem('owsfz-api-key')` is already set (i.e., the user was redirected after a 401 mid-session), clear it and show the message: "Session expired — please reconnect."
- Style must be minimal and readable on a phone screen (dark background matching the main app is acceptable but not required; functional clarity is sufficient).

No external fonts, no `<link>` tags, no `<script src="...">` tags.

### 3.3 — Update `web/js/api.js`: inject `X-Api-Key` and handle 401

Modify `api.js` to introduce a shared passphrase accessor and wire it into `fetchJson`.

**Add at the top of the module (before any exports):**

```javascript
// ── Remote access passphrase (lan-remote-access) ─────────────────────────
const API_KEY_SESSION_KEY = 'owsfz-api-key';

/**
 * Returns the stored API passphrase, or null if none is present
 * (loopback access or no passphrase configured).
 * @returns {string|null}
 */
export function getApiKey() {
  return sessionStorage.getItem(API_KEY_SESSION_KEY);
}

/**
 * Stores the passphrase extracted from the URL's ?key= parameter into
 * sessionStorage, then removes the parameter from the browser history so
 * the passphrase is not visible in the URL bar or the back-button history.
 * Called once at module load time.
 */
function bootstrapApiKeyFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const key    = params.get('key');
  if (key) {
    sessionStorage.setItem(API_KEY_SESSION_KEY, key);
    params.delete('key');
    const clean = params.toString()
      ? `${window.location.pathname}?${params}`
      : window.location.pathname;
    history.replaceState(null, '', clean);
  }
}

bootstrapApiKeyFromUrl();
```

**Modify `fetchJson`** to add the `X-Api-Key` header when a key is present, and to redirect to `/login.html` on 401:

```javascript
async function fetchJson(url, init) {
  const key = getApiKey();
  const extraHeaders = key ? { 'X-Api-Key': key } : {};
  const mergedInit = {
    ...init,
    headers: { ...(init?.headers ?? {}), ...extraHeaders },
  };

  const res = await fetch(url, mergedInit);

  if (res.status === 401) {
    // Passphrase rejected or session expired — return to login.
    sessionStorage.removeItem(API_KEY_SESSION_KEY);
    window.location.href = '/login.html';
    // Return a never-resolving promise so callers don't see a thrown error
    // while the navigation is in progress.
    return new Promise(() => {});
  }

  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${res.statusText} — ${url}`);
  }
  return res.json();
}
```

Also update **`postCatRetry`** (which currently uses a raw `fetch` rather than `fetchJson`) to follow the same pattern: add `X-Api-Key` header if a key is present; redirect on 401.

### 3.4 — Update `web/js/ws.js`: append `?key=` to WebSocket URL; handle auth failure

**Modify `wsUrl()`** to append the passphrase as a query parameter when one is stored:

```javascript
function wsUrl() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const key      = sessionStorage.getItem('owsfz-api-key');
  const keyParam = key ? `?key=${encodeURIComponent(key)}` : '';
  return `${protocol}//${location.host}${WS_URL_PATH}${keyParam}`;
}
```

**Handle WebSocket auth failure** — when the server rejects the WS upgrade with 401, the browser fires `close` without ever firing `open`. Detect this and redirect to login:

In the `open()` function, track whether the connection was ever successfully opened:

```javascript
function open() {
  if (destroyed) return;
  reconnectTimer = null;

  let everOpened = false;   // ← add this

  ws = new WebSocket(wsUrl());

  ws.addEventListener('open', () => {
    everOpened = true;      // ← set flag on successful open
    delay = DELAY_INITIAL;
    onEvent({ type: '__state', payload: 'connected' });
  });

  // ... (message and error handlers unchanged) ...

  ws.addEventListener('close', () => {
    ws = null;
    onEvent({ type: '__state', payload: 'disconnected' });

    // If the connection closed before ever opening AND we have a stored key,
    // assume auth failure (server returned 401 on the WS upgrade).
    // Clear the key and redirect to the login page.
    if (!everOpened && sessionStorage.getItem('owsfz-api-key')) {
      sessionStorage.removeItem('owsfz-api-key');
      window.location.href = '/login.html';
      return;
    }

    scheduleReconnect();
  });
}
```

### 3.5 — Ensure `api.js` is imported by `index.html` early enough

The `bootstrapApiKeyFromUrl()` call in `api.js` must run before any API calls are made. Verify that `index.html` imports `api.js` (directly or transitively via `main.js`) early in the `<head>` or at the top of the module graph. If `api.js` is only imported by `settings.js`, the bootstrap will not run on the main page. Add an explicit `import './api.js'` to `main.js` if it is not already there, or move `bootstrapApiKeyFromUrl()` to `main.js`.

Check the current `main.js` import structure and ensure `getApiKey` / `bootstrapApiKeyFromUrl` are accessible on the main page. The simplest change: import `getApiKey` in `main.js` and call `bootstrapApiKeyFromUrl()` explicitly from `main.js` if it is not auto-called at module load. (If `api.js` is imported as a module and `bootstrapApiKeyFromUrl()` is at module scope, it will run automatically on first import — verify this is the case.)

### 3.6 — Update `AuthMiddlewareTests.cs`

Add three new test cases to `AuthMiddlewareTests.cs`:

**Test 8.5 — Non-loopback `GET /api/v1/status` without key still returns 401 (not redirect):**
- This is a regression guard confirming that the API-path exception in the new middleware is working. The existing test 8.2c already covers this; add a comment referencing the new behaviour if needed, but a new test explicitly asserting `StatusCode == 401` (not `302`) for `/api/v1/status` from a non-loopback origin is preferred.

**Test 8.6 — Non-loopback `GET /` without key returns 302 redirect to `/login.html`:**
- Use `_spoofedApp` (non-loopback IP) with an `HttpClient` configured NOT to follow redirects (`AllowAutoRedirect = false`).
- `GET /` SHALL return `302` with a `Location` header of `/login.html`.

**Test 8.7 — Non-loopback `GET /login.html` without key returns 200:**
- Use `_spoofedApp` (non-loopback IP).
- `GET /login.html` SHALL return `200` (auth middleware whitelist in effect).
- Note: this test will fail if `web/login.html` is not present in the test output directory. Confirm the file is copied to `web/` alongside `index.html` by the Daemon build process.

---

## 4. Acceptance Criteria

The QA engineer will verify the following before approving merge to `main`:

**AC-1 — Login redirect (middleware, automated):**  
`AuthMiddlewareTests` 8.6: `GET /` from non-loopback without key → 302 to `/login.html`. Test passes.

**AC-2 — Login page bypass (middleware, automated):**  
`AuthMiddlewareTests` 8.7: `GET /login.html` from non-loopback without key → 200. Test passes.

**AC-3 — API paths unchanged (middleware, automated):**  
`AuthMiddlewareTests` 8.2c / 8.5: `GET /api/v1/status` from non-loopback without key → 401 (not redirect). Test passes.

**AC-4 — Existing tests unchanged:**  
All 388+ existing tests pass; no regressions.

**AC-5 — Login page reachable from a remote browser (manual / log inspection):**  
A browser navigating to `http://<lan-ip>:8080/` receives a 302 to `/login.html`; `/login.html` returns 200 with a passphrase form. The server log SHALL NOT show a 401 for `/login.html`.

**AC-6 — Successful login grants full access (manual):**  
After entering the correct passphrase on `/login.html` and clicking Connect, the browser reaches `index.html`, the WebSocket connects (heartbeat messages appear in log), and all API calls succeed (200 responses visible in log).

**AC-7 — Wrong passphrase returns to login (manual):**  
Entering an incorrect passphrase on `/login.html` causes the page to redirect back to `/login.html` (either directly from JS validation or via the 401 redirect from the middleware). The user is not left on a broken page.

**AC-8 — Loopback access unchanged (manual / log inspection):**  
The operator's own browser at `http://127.0.0.1:8080/` reaches `index.html` directly with no login redirect. The server log SHALL NOT show a 302 for loopback-origin requests to `/`.

**AC-9 — No passphrase (NullAuthPolicy) unaffected (manual):**  
When `RemoteAccess.Passphrase` is null/empty (`NullAuthPolicy` registered), remote browsers reach `index.html` directly with no login page involvement. `getApiKey()` returns null; no `X-Api-Key` header is sent; no `?key=` appended to WS URL.

**AC-10 — `postCatRetry` sends `X-Api-Key` (code review):**  
`postCatRetry` in `api.js` includes the `X-Api-Key` header when a key is stored. The raw `fetch` call must be updated consistently with the pattern in `fetchJson`.

**AC-11 — `?key=` removed from URL after login (code review + manual):**  
After the browser navigates to `/?key=<passphrase>` and `index.html` loads, the URL bar shall show `/` (not `/?key=...`). `history.replaceState` is called correctly in `bootstrapApiKeyFromUrl()`.

---

## 5. References

- **OpenSpec change:** `openspec/changes/lan-remote-access/` (proposal, design, specs)
- **Design decisions in scope:** D1 (loopback bypass), D2 (`X-Api-Key` / `?key=`), D3 (auth before static files)
- **Defects:** D-LAN-001 (`api.js`), D-LAN-002 (`ws.js`), D-LAN-003 (missing browser auth flow)
- **Log file:** `logs/openswfz-20260623T211446Z.log` — see lines 79–84, 212–217, 234–239
- **Auth middleware source:** `src/OpenWSFZ.Web/WebApp.cs` lines 135–151 (current)
- **Existing auth tests:** `tests/OpenWSFZ.Web.Tests/AuthMiddlewareTests.cs`
- **Captain's decision:** Option B (login page) — 2026-06-23
