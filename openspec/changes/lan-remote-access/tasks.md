## 1. Abstractions — RemoteAccessConfig and IAuthPolicy

- [x] 1.1 Create `src/OpenWSFZ.Abstractions/RemoteAccessConfig.cs` — a `sealed record RemoteAccessConfig(bool Enabled = false, string? Passphrase = null)` decorated with `[JsonConstructor]` so STJ source-gen respects the parameter defaults for absent JSON fields (same pattern as TxConfig)
- [x] 1.2 Add `public RemoteAccessConfig RemoteAccess { get; init; } = new();` init property to `AppConfig` in `src/OpenWSFZ.Abstractions/AppConfig.cs`
- [x] 1.3 Extend `IAuthPolicy` in `src/OpenWSFZ.Abstractions/IAuthPolicy.cs` — add method `bool IsAuthorized(Microsoft.AspNetCore.Http.HttpContext context)` (add the `using` or fully qualify to keep the Abstractions project free of web references — alternatively use `System.Net.IPAddress` plus a raw `bool IsAuthorized(System.Net.IPAddress? remoteIp, string? apiKeyHeader, string? keyQueryParam)` signature to avoid an ASP.NET Core dependency in Abstractions; see D5 in design.md)

> **Note on IAuthPolicy signature:** Abstractions must not take a direct dependency on `Microsoft.AspNetCore.Http`. Use a decoupled signature: `bool IsAuthorized(System.Net.IPAddress? remoteIp, string? apiKeyHeader, string? keyQueryParam)`. The middleware in `WebApp.Create` extracts these three values from `HttpContext` and passes them through.

- [x] 1.4 Update `NullAuthPolicy` in `src/OpenWSFZ.Web/NullAuthPolicy.cs` to implement the new method — return `true` unconditionally

## 2. Web — LanBindPolicy and PassphraseAuthPolicy

- [x] 2.1 Create `src/OpenWSFZ.Web/LanBindPolicy.cs` — implements `IBindPolicy`; `Resolve(desired, port)` returns `new IPEndPoint(IPAddress.Any, port)` and logs an Info message with the effective address
- [x] 2.2 Create `src/OpenWSFZ.Web/PassphraseAuthPolicy.cs` — implements `IAuthPolicy`; constructor takes `string passphrase`; `IsAuthorized(remoteIp, apiKeyHeader, keyQueryParam)` returns `true` if: (a) `remoteIp` is loopback (`IPAddress.IsLoopback`), OR (b) `passphrase` is null/empty, OR (c) `apiKeyHeader == passphrase`, OR (d) `keyQueryParam == passphrase`; otherwise returns `false`

## 3. Web — Auth middleware wiring in WebApp.Create

- [x] 3.1 In `src/OpenWSFZ.Web/WebApp.cs`, resolve `IAuthPolicy` from DI after `var app = builder.Build()` and before `app.UseWebSockets()`
- [x] 3.2 Add `app.Use(async (ctx, next) => { ... })` middleware immediately after resolving the policy: extract `ctx.Connection.RemoteIpAddress`, `ctx.Request.Headers["X-Api-Key"]`, and `ctx.Request.Query["key"]`; call `authPolicy.IsAuthorized(...)`; if false, set `ctx.Response.StatusCode = 401` and return; otherwise call `await next(ctx)`
- [x] 3.3 Ensure the middleware is placed BEFORE `app.UseDefaultFiles(...)`, `app.UseStaticFiles(...)`, and all `app.MapGet`/`app.MapPost` registrations
- [x] 3.4 Register `RemoteAccessConfig` in `AppJsonContext` (`src/OpenWSFZ.Web/AppJsonContext.cs`) so STJ source-gen includes it — add `[JsonSerializable(typeof(RemoteAccessConfig))]`

## 4. Daemon — Policy selection at startup

- [x] 4.1 In `OpenWSFZ.Daemon` startup (locate the service registration file where `IConfigStore`, `IBindPolicy`, and `IAuthPolicy` are currently registered), read `loadedConfig.RemoteAccess` after the config is loaded
- [x] 4.2 Register `IBindPolicy`: if `RemoteAccess.Enabled` is `true`, register `LanBindPolicy`; otherwise register `LoopbackBindPolicy` (the existing default)
- [x] 4.3 Register `IAuthPolicy`: if `RemoteAccess.Enabled` is `true` and `Passphrase` is non-null/non-empty, register `PassphraseAuthPolicy(passphrase)`; otherwise register `NullAuthPolicy`
- [x] 4.4 Remove the hardcoded `IAuthPolicy → NullAuthPolicy` and `IBindPolicy → LoopbackBindPolicy` registrations from `WebApp.Create` fallback defaults where they conflict with the daemon's explicit registrations (keep the DI fallback in `WebApp.Create` for test compatibility — tests that do not pass an explicit `bindPolicy` still get `LoopbackBindPolicy` via the existing DI fallback)

## 5. Web frontend — Remote Access settings section

- [x] 5.1 Add a Remote Access sub-section to the Advanced tab in `web/settings.html` containing: checkbox `id="remote-access-enabled"`, password input `id="remote-access-passphrase"` with a show/hide toggle button, a restart-required warning banner (`id="remote-access-restart-warning"`), and the legal disclaimer block (`id="remote-access-disclaimer"`)
- [x] 5.2 In `web/js/settings.js`, populate `#remote-access-enabled` and `#remote-access-passphrase` from `config.remoteAccess` on page load (or defaults if the field is absent)
- [x] 5.3 Wire the toggle's `change` event to show/hide `#remote-access-passphrase`, `#remote-access-restart-warning`, and `#remote-access-disclaimer` based on the checked state
- [x] 5.4 Wire the passphrase show/hide button to toggle `#remote-access-passphrase`'s `type` attribute between `password` and `text`
- [x] 5.5 Include `remoteAccess: { enabled: <bool>, passphrase: <string|null> }` in the `POST /api/v1/config` body assembled by the Save handler; post `null` for `passphrase` when the input is empty
- [x] 5.6 Add `#remote-access-enabled` and `#remote-access-passphrase` to the dirty-state snapshot so unsaved-changes detection covers the new controls

## 6. Config — Default file includes remoteAccess

- [x] 6.1 Confirm that the daemon's default-config creation path (wherever `new AppConfig()` is written to disk on first run) results in a `remoteAccess` object with `enabled: false` and `passphrase: null` in the output JSON — verify this works without code changes given the new `AppConfig.RemoteAccess` default, or add explicit serialisation if the default-config writer hard-codes fields

## 7. Tests — Unit tests

- [x] 7.1 `LanBindPolicy` unit test: `Resolve(IPAddress.Loopback, 8080)` returns endpoint with `IPAddress.Any` and port 8080; `Resolve(IPAddress.Any, 9000)` returns endpoint with `IPAddress.Any` and port 9000
- [x] 7.2 `PassphraseAuthPolicy` unit tests (all non-loopback, passphrase = "secret"):
  - `IsAuthorized(nonLoopback, "secret", null)` → true
  - `IsAuthorized(nonLoopback, "wrong", null)` → false
  - `IsAuthorized(nonLoopback, null, "secret")` → true (WS path)
  - `IsAuthorized(nonLoopback, null, "wrong")` → false
  - `IsAuthorized(nonLoopback, null, null)` → false
- [x] 7.3 `PassphraseAuthPolicy` loopback bypass tests:
  - `IsAuthorized(IPAddress.Loopback, null, null)` → true
  - `IsAuthorized(IPAddress.IPv6Loopback, null, null)` → true
- [x] 7.4 `PassphraseAuthPolicy` null/empty passphrase config: `new PassphraseAuthPolicy(null)` and `new PassphraseAuthPolicy("")` both return `true` for any origin
- [x] 7.5 `RemoteAccessConfig` JSON round-trip test: serialise `new RemoteAccessConfig(true, "test")` via `AppJsonContext.Default`, deserialise, verify `Enabled = true`, `Passphrase = "test"`
- [x] 7.6 `AppConfig` backward-compat test: deserialise JSON with no `remoteAccess` key → `RemoteAccess.Enabled = false`, `RemoteAccess.Passphrase = null`

## 8. Tests — Integration tests (WebApp.Tests)

- [x] 8.1 Integration test: `WebApp.Create` with `NullAuthPolicy` — `GET /api/v1/status` returns 200 (verifies existing tests are unaffected; this may already be covered, confirm no regressions)
- [x] 8.2 Integration test: `WebApp.Create` with `PassphraseAuthPolicy("secret")` registered as `IAuthPolicy`:
  - `GET /api/v1/status` with `X-Api-Key: secret` → 200
  - `GET /api/v1/status` with `X-Api-Key: wrong` → 401
  - `GET /api/v1/status` with no header → 401
- [x] 8.3 Integration test: WebSocket upgrade with `PassphraseAuthPolicy("secret")`:
  - Connect to `/api/v1/ws?key=secret` → 101 (upgrade succeeds)
  - Connect to `/api/v1/ws?key=wrong` → 401
  - Connect to `/api/v1/ws` (no param) → 401
- [x] 8.4 Integration test: loopback bypass — configure `PassphraseAuthPolicy("secret")`; send `GET /api/v1/status` from a test client whose `RemoteIpAddress` is `127.0.0.1` with no `X-Api-Key` header → 200

> **Test infrastructure note:** To simulate non-loopback remote IP in integration tests, `WebApplicationFactory`'s test client always presents `127.0.0.1`. Consider using a custom `TestServer` with a middleware shim that overrides `context.Connection.RemoteIpAddress` for the non-loopback 401 scenarios, or test `PassphraseAuthPolicy.IsAuthorized` directly with a mocked IP (unit test approach, already covered in task 7.2).
