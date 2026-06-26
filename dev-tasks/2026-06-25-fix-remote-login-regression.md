# Fix: Remote Login Regression (SEC-002B login.html defect)

**Date:** 2026-06-25
**Raised by:** QA engineer — post-merge regression reported by Captain
**Branch:** `fix/remote-login-regression`
**Priority:** BLOCKER — LAN remote access is completely unusable; login loops infinitely

---

## Context

The `fix/security-lan-hardening` merge (`33c5f75`, 2026-06-24) introduced a regression in the LAN login flow. After a successful login, remote users are immediately redirected back to the login page in an infinite loop. Loopback access (`127.0.0.1`) is unaffected.

**Root cause:** The SEC-002B change in `web/login.html` removed `?key=` from the post-login redirect URL. The intent was correct — keep the passphrase out of URLs — but it broke the server-side auth check that must happen *before* any JavaScript runs on the page.

### Failure chain

1. LAN user visits `http://<host>/` — middleware returns 401, redirects to `/login.html?return=/`
2. User enters passphrase, clicks login
3. `login.html` JS stores key in `sessionStorage`, then navigates to `/` (no `?key=`)
4. Browser issues `GET /` — plain GET, no custom headers, no `?key=` in URL
5. Middleware: not loopback, not WS upgrade, no `X-Api-Key` header, no `?key=` → 401 → `/login.html?return=/`
6. **Loop.** User never reaches the application.

### Why the original flow worked

The original `login.html` redirected to `/?key=<passphrase>`. The middleware's `PassphraseAuthPolicy.IsAuthorized` found the `?key=` parameter and authorised the page load. Once the page loaded, `api.js`'s `bootstrapApiKey()` function stripped `?key=` from the URL bar immediately via `history.replaceState` and moved the value into `sessionStorage` for all subsequent REST calls. This strip function still exists and works correctly — it just never fires when the page load is rejected before the script runs.

### What to keep from SEC-002B

The WebSocket change in `ws.js` (auth frame instead of `?key=` in the WS URL) is correct and must **not** be reverted. The `?key=` exposure in the WS URL was the higher-impact finding: it appeared in every WebSocket connection frame in browser DevTools and in any proxy log for the entire session lifetime. A one-time `?key=` in a login redirect — which is immediately stripped from the URL bar by `api.js` — is a much lower-exposure pattern and acceptable.

---

## Actions

### 1. Restore `?key=` in the login redirect — `web/login.html`

Find the block added by SEC-002B (around line 158–166):

```js
sessionStorage.setItem(SESSION_KEY, passphrase);
var loginParams = new URLSearchParams(window.location.search);
var returnPath  = loginParams.get('return') || '/';
// Guard: returnPath must start with '/' to prevent open-redirect abuse.
if (!returnPath.startsWith('/')) returnPath = '/';
// SEC-002B: navigate to the return path WITHOUT the passphrase in the URL.
// The key lives in sessionStorage; api.js reads it for REST calls via
// the X-Api-Key header, and ws.js sends it as the first WebSocket frame.
window.location.href = returnPath;
```

Replace the final assignment and its comment with:

```js
sessionStorage.setItem(SESSION_KEY, passphrase);
var loginParams = new URLSearchParams(window.location.search);
var returnPath  = loginParams.get('return') || '/';
// Guard: returnPath must start with '/' to prevent open-redirect abuse.
if (!returnPath.startsWith('/')) returnPath = '/';
// The server-side auth middleware must authorise the page load before any
// JavaScript runs, so ?key= must be present in the redirect URL.
// api.js bootstrapApiKey() strips it from the URL bar immediately via
// history.replaceState and moves the value into sessionStorage.
// This is a one-time occurrence; the key does NOT appear in subsequent
// navigation or in the WebSocket URL (ws.js uses the auth-frame protocol).
var sep = returnPath.indexOf('?') === -1 ? '?' : '&';
window.location.href = returnPath + sep + 'key=' + encodeURIComponent(passphrase);
```

### 2. No other files require changes

- `web/js/ws.js` — already correct; keep auth-frame protocol, no `?key=` in WS URL
- `src/OpenWSFZ.Web/PassphraseAuthPolicy.cs` — already checks `?key=` query param; no change needed
- `src/OpenWSFZ.Web/WebApp.cs` — no change needed
- `web/js/api.js` — `bootstrapApiKey()` already strips `?key=` from URL; no change needed

---

## Acceptance Criteria

QA will verify the following before approving merge to `main`:

- [ ] From a LAN address (non-loopback), navigating to `http://<host>/` redirects to the login page.
- [ ] Entering the correct passphrase and submitting successfully loads the main application page (no redirect loop).
- [ ] After the page loads, the URL bar does **not** contain `?key=` (stripped by `api.js` `bootstrapApiKey()`).
- [ ] The WebSocket connection in DevTools → Network → WS shows **no** `?key=` query parameter in the connection URL.
- [ ] From loopback (`127.0.0.1`), login is not required (unaffected).
- [ ] Entering an incorrect passphrase shows an error on the login page (no crash or loop).
- [ ] Unit test added or noted: verify `PassphraseAuthPolicy.IsAuthorized` returns `true` when `?key=` is present and correct (existing coverage in `PassphraseAuthPolicyTests.cs` — confirm the `?key=` path is exercised).

---

## References

- Regression introduced: `240fec0` (fix/security-lan-hardening, SEC-002B `login.html` change)
- `api.js` `bootstrapApiKey()`: `web/js/api.js` lines 21–35
- `PassphraseAuthPolicy.IsAuthorized`: `src/OpenWSFZ.Web/PassphraseAuthPolicy.cs`
- Middleware page-load redirect: `src/OpenWSFZ.Web/WebApp.cs` line ~198
- QA review: R5-SEC (2026-06-24) — F4 and login flow were not acceptance-tested post-merge; regression exposed by first real LAN login attempt
