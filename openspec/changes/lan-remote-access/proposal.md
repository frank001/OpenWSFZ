## Why

OpenWSFZ currently binds exclusively to 127.0.0.1, making it accessible only from the operator's own machine. Operators with a shack PC want to monitor decodes, control the QSO answerer, and tune the rig from a tablet or phone on the same local network — without re-running the application remotely or setting up port forwarding. A single shared passphrase is sufficient security for a home LAN; internet exposure is out of scope for this phase.

## What Changes

- New `RemoteAccessConfig` record added to `OpenWSFZ.Abstractions` (`Enabled` bool, `Passphrase` string?), surfaced as an `init` property on `AppConfig`.
- `IAuthPolicy` gains a method: `bool IsAuthorized(HttpContext context)`. `NullAuthPolicy` returns `true` (no behaviour change for existing callers).
- New `LanBindPolicy` in `OpenWSFZ.Web` — binds Kestrel to `0.0.0.0` instead of `127.0.0.1`.
- New `PassphraseAuthPolicy` in `OpenWSFZ.Web` — checks `X-Api-Key` header (REST) or `?key=` query parameter (WebSocket upgrades). Loopback origins (`127.0.0.1`, `::1`) are always trusted.
- Auth middleware wired into `WebApp.Create` before static files and routing; calls `IAuthPolicy.IsAuthorized` on every request.
- `OpenWSFZ.Daemon` selects the correct bind + auth policy pair at startup based on `RemoteAccessConfig`.
- New Remote Access settings page in the web frontend with enable toggle, passphrase field, restart-required warning, and legal disclaimer.
- Legal disclaimer embedded in the UI (displayed when remote access is enabled).

## Capabilities

### New Capabilities

- `remote-access`: LAN binding, passphrase authentication middleware, `LanBindPolicy`, `PassphraseAuthPolicy`, `RemoteAccessConfig` — the complete remote-access feature.

### Modified Capabilities

- `web-server`: Kestrel bind-address selection now driven by config; auth middleware added to request pipeline; `IAuthPolicy` interface extended with `IsAuthorized` method.
- `configuration`: `AppConfig` gains `RemoteAccess` property; `RemoteAccessConfig` record added.
- `web-frontend`: New Remote Access settings section on the Settings page.

## Impact

- **`OpenWSFZ.Abstractions`** — `IAuthPolicy.cs`, `AppConfig.cs` (new `RemoteAccess` property), new `RemoteAccessConfig.cs`.
- **`OpenWSFZ.Web`** — new `LanBindPolicy.cs`, new `PassphraseAuthPolicy.cs`, `WebApp.cs` (auth middleware, policy selection), `AppJsonContext.cs` (STJ source-gen registration for `RemoteAccessConfig`).
- **`OpenWSFZ.Daemon`** — startup DI wiring for bind/auth policy selection.
- **Web frontend** — new Remote Access section in `settings.js` / Settings HTML.
- **`OpenWSFZ.Web.Tests`** — new integration tests for auth middleware; new unit tests for both new policies.
- **`OpenWSFZ.Config.Tests`** — round-trip tests for `RemoteAccessConfig` / `AppConfig` with new field.
- **No breaking changes** — `NullAuthPolicy.IsAuthorized` returns `true`; all existing tests pass unchanged. Loopback-only behaviour is preserved when `RemoteAccess.Enabled = false` (the default).
