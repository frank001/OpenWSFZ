# Dev Handoff — D-LAN-005: Post-login redirect ignores original destination

**Date:** 2026-06-24  
**Branch:** `fix/lan-remote-access-browser-auth` (continue on current branch)  
**Defect ID:** D-LAN-005  
**Severity:** High — Settings page is unreachable from the LAN address  

---

## 1. Context

The `fix/lan-remote-access-browser-auth` branch correctly implements the login page
(D-LAN-003) and static asset exemption (D-LAN-004). However, a new defect exists:

**When the operator clicks ⚙ Settings from the main page, they are redirected to the
login page; after entering the correct passphrase, they land on the main page again —
not on the Settings page they requested.**

Root cause: the D-LAN-003 handoff specified that `login.html` always navigates to
`/?key=...` after login. That was implemented faithfully. Multi-page navigation within
an authenticated session was never addressed.

Two contributing issues, both requiring a fix:

**Issue A — Server does not preserve the originally-requested URL when redirecting to
`/login.html`.** The login page has no information about the user's original destination.

**Issue B — `login.html` always navigates to `/` after login.** The destination is
unconditional regardless of where the user came from.

**Issue C — Navigation links are not key-aware.** The `<a href="/settings.html">` link
in `index.html` and the `<a href="/">` back-link in `settings.html` do not include
`?key=`, so every page transition from an authenticated session triggers an unnecessary
auth challenge.

Issue C is not a blocker on its own (Issues A+B alone would produce correct — if
cumbersome — behaviour), but all three must be fixed for acceptable UX.

---

## 2. Branch Name

Continue on `fix/lan-remote-access-browser-auth`. No new branch required.

---

## 3. Actions

### 3.1 — `src/OpenWSFZ.Web/WebApp.cs`: pass `?return=` when redirecting to login

**Current code (line 176):**
```csharp
ctx.Response.Redirect("/login.html");
```

**Replace with:**
```csharp
var returnUrl = Uri.EscapeDataString(ctx.Request.Path.Value ?? "/");
ctx.Response.Redirect($"/login.html?return={returnUrl}");
```

No other changes to `WebApp.cs` are required.

---

### 3.2 — `web/login.html`: use `?return=` as the post-login destination

**Current code (the form submit handler, line ~159):**
```javascript
window.location.href = '/?key=' + encodeURIComponent(passphrase);
```

**Replace with:**
```javascript
var loginParams   = new URLSearchParams(window.location.search);
var returnPath    = loginParams.get('return') || '/';
// Guard: returnPath must start with '/' to prevent open-redirect abuse.
if (!returnPath.startsWith('/')) returnPath = '/';
var sep = returnPath.includes('?') ? '&' : '?';
window.location.href = returnPath + sep + 'key=' + encodeURIComponent(passphrase);
```

The open-redirect guard (`if (!returnPath.startsWith('/'))`) is mandatory — without it,
a malicious link of the form `/login.html?return=https://evil.example/` could redirect
the operator to an external site with the passphrase in the URL.

The security note on `settings.html` itself is that it is a static HTML page that loads
no secrets other than what the user typed — the passphrase appears in `?key=` only long
enough for `bootstrapApiKeyFromUrl()` in `api.js` to strip it via `history.replaceState`.

---

### 3.3 — `web/js/main.js`: update the Settings link to carry the key

In the `DOMContentLoaded` listener, add the following block **after** the existing
initialisation calls (`startCycleTimerIfEnabled()`, `getTxStatus().then(...)`, etc.):

```javascript
// D-LAN-005: update the Settings nav link to carry the API key so the browser
// navigation does not trigger an unnecessary auth challenge.
// getApiKey() is already imported from './api.js'; bootstrapApiKeyFromUrl() has
// already run at module load time (before DOMContentLoaded), so the key is present.
const settingsNavLink = document.querySelector('nav a[href="/settings.html"]');
if (settingsNavLink) {
  const key = getApiKey();
  if (key) {
    settingsNavLink.href = '/settings.html?key=' + encodeURIComponent(key);
  }
}
```

`getApiKey` is already imported in `main.js` at line 12 — no new import is required.

---

### 3.4 — `web/js/settings.js`: update the back-link to carry the key

**Add `getApiKey` to the existing import at the top of `settings.js`:**

Current (line 10):
```javascript
import { getConfig, getDevices, getOutputDevices, postConfig, getStatus, getSerialPorts, getFrequencies, postFrequencies, postCatRetry } from './api.js';
```

Replace with:
```javascript
import { getConfig, getDevices, getOutputDevices, postConfig, getStatus, getSerialPorts, getFrequencies, postFrequencies, postCatRetry, getApiKey } from './api.js';
```

**Add the following block at module scope** (not inside DOMContentLoaded — `backLink` is
already captured at module scope at line 20, so this can run immediately):

```javascript
// D-LAN-005: update the back-link to carry the API key so navigating back to the
// main page does not trigger an auth redirect.
// `backLink` is already captured at module scope above.
(function () {
  const key = getApiKey();
  if (key && backLink) {
    backLink.href = '/?key=' + encodeURIComponent(key);
  }
})();
```

Place this block immediately after the block of `const` declarations at module scope
(i.e., after the `const remoteAccessDisclaimer` line, before the `// ── Tab switching`
comment). This ensures `backLink.href` is updated before the `backLink.addEventListener`
click handler is registered, so the dirty-state guard (which calls `event.preventDefault()`
to block navigation) can still read the correct destination from `backLink.href`.

---

## 4. Acceptance Criteria

The QA engineer will verify the following:

**AC-1 — Settings page reachable without re-authentication (manual):**  
From `http://10.0.1.35:8080/` (after logging in), click ⚙ Settings.
The Settings page SHALL load directly — the login page SHALL NOT appear.

**AC-2 — Back-link returns to main without re-authentication (manual):**  
From Settings, click ← Back to main.
The main page SHALL load directly — the login page SHALL NOT appear.

**AC-3 — Login redirect preserves destination (manual/automated):**  
Navigate directly to `http://10.0.1.35:8080/settings.html` (no key in URL).
The browser SHALL be redirected to `/login.html?return=/settings.html`.
After entering the correct passphrase, the browser SHALL land on `/settings.html`
(not on the main page).

**AC-4 — Open-redirect guard prevents external redirect (code review):**  
In `login.html`, confirm that if `?return=https://evil.example/`, the guard
`if (!returnPath.startsWith('/')) returnPath = '/';` causes the redirect to go to
`/?key=...` rather than the external URL.

**AC-5 — `AuthMiddlewareTests` updated (automated):**  
Existing test 8.6 (`GET / from non-loopback → 302 /login.html`) SHALL now assert that
the `Location` header is `/login.html?return=%2F` (not just `/login.html`).
Add a new test **8.8**: `GET /settings.html from non-loopback without key → 302 with
Location = /login.html?return=%2Fsettings.html`.

**AC-6 — Full test suite green:**  
`dotnet test OpenWSFZ.slnx -c Release` passes with ≥ 412 tests, 0 failures.

---

## 5. References

- Defect discovered during: manual testing of `fix/lan-remote-access-browser-auth`
- Parent handoff: `dev-tasks/2026-06-23-lan-browser-auth.md` (D-LAN-003 — introduced the
  unconditional `/?key=...` redirect that this task corrects)
- Auth middleware: `src/OpenWSFZ.Web/WebApp.cs` line 176
- Login redirect: `web/login.html` (form submit handler, `window.location.href = ...`)
- Settings link: `web/index.html` line 38 (`<a href="/settings.html">`)
- Back-link: `web/settings.html` line 14 / `web/js/settings.js` line 20 (`backLink`)
- `getApiKey` export: `web/js/api.js` line 16
