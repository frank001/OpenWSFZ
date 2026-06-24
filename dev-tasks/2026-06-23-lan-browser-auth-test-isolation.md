# Handoff: LAN Browser Auth — Test Isolation Regression (WebTestFactory)

**Date:** 2026-06-23  
**Parent task:** `dev-tasks/2026-06-23-lan-browser-auth.md`  
**Branch:** `fix/lan-remote-access-browser-auth` (already in progress)

---

## 1. Context

24 of 124 tests in `OpenWSFZ.Web.Tests` fail after the browser-auth fix was applied. The failures are a test isolation regression — the operator's live `config.json` (which currently has `RemoteAccess.Enabled = true` with a passphrase) now causes `Program.cs` to register `PassphraseAuthPolicy` into the DI container. `WebTestFactory` inherits that registration because it does not override `IAuthPolicy`.

The in-process `TestServer` transport used by `WebApplicationFactory` presents `null` as `HttpContext.Connection.RemoteIpAddress`. The loopback bypass in `PassphraseAuthPolicy` is guarded by `remoteIp is not null`, so `null` falls through the bypass and the policy rejects all requests.

**Symptom A** — tests with `AllowAutoRedirect = true` (`StaticAssetsIntegrationTests`): requests to `/css/app.css`, `/js/main.js`, `/js/api.js` are redirected to `/login.html` by the new middleware and return `text/html` instead of the expected content type.

**Symptom B** — tests with `AllowAutoRedirect = false` (all other `WebTestFactory`-based tests): requests to `/api/v1/*` receive 401; requests to `/` receive 302.

---

## 2. Branch

Continue on `fix/lan-remote-access-browser-auth`. No new branch required.

---

## 3. Actions

### 3.1 — Add `IAuthPolicy` override to `WebTestFactory.ConfigureWebHost`

In `tests/OpenWSFZ.Web.Tests/WebTestFactory.cs`, inside the `builder.ConfigureServices(services => { ... })` lambda, add two lines alongside the existing `RemoveAll` / `AddSingleton` overrides:

```csharp
// Restore NullAuthPolicy so tests are isolated from the operator's live
// auth configuration.  PassphraseAuthPolicy (registered by Program.cs when
// RemoteAccess is enabled in the live config) would reject all in-process
// TestServer requests because RemoteIpAddress is null on the test transport,
// defeating the loopback bypass.  Auth-middleware behaviour is already tested
// in AuthMiddlewareTests using its own bespoke server instances.
services.RemoveAll<IAuthPolicy>();
services.AddSingleton<IAuthPolicy, NullAuthPolicy>();
```

That is the entire code change. No other file requires modification.

### 3.2 — Verify

Run:

```
dotnet test OpenWSFZ.slnx -c Release
```

Expected outcome: 0 failures. The `AuthMiddlewareTests` tests (8.1–8.7) continue to exercise `PassphraseAuthPolicy` using their own isolated server instances with `configureServices` overrides; they are unaffected by this change.

---

## 4. Acceptance Criteria

**AC-1:** `dotnet test OpenWSFZ.slnx -c Release` reports 0 failures and ≥ 412 passed (388 prior baseline + new auth tests + 24 previously failing).

**AC-2:** `StaticAssetsIntegrationTests.GetApiJs_Returns200JavaScript` passes — `text/javascript` is returned, not `text/html`.

**AC-3:** `StatusAndBindingTests.GetRoot_Returns200WithHtmlBody` passes — `GET /` returns 200 with HTML body from `WebTestFactory`.

**AC-4:** All `AuthMiddlewareTests` (8.1–8.7) still pass — the auth middleware fix is not compromised by this isolation change.

---

## 5. References

- Regression introduced by: `dev-tasks/2026-06-23-lan-browser-auth.md`, task 3.1 (auth middleware changes)
- Affected fixture: `tests/OpenWSFZ.Web.Tests/WebTestFactory.cs`, `ConfigureWebHost`
- Existing pattern to follow: the same file already does `RemoveAll<IConfigStore>()` / `RemoveAll<IFrequencyStore>()` for the same reason — test isolation from the live operator config
- QA investigation log: `logs/openswfz-20260623T211446Z.log`
