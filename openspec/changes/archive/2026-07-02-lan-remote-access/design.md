## Context

OpenWSFZ's web interface is currently bound exclusively to `127.0.0.1` via `LoopbackBindPolicy`. The DI container already carries `IBindPolicy` and `IAuthPolicy` seams anticipating exactly this phase — `LoopbackBindPolicy` and `NullAuthPolicy` are the Phase 1 stubs; this change delivers the Phase 2 implementations.

`IAuthPolicy` is currently a marker interface with no methods. It is registered in DI and wired into `WebApp.Create`, but never actually called. The `IBindPolicy` is used at Kestrel startup only; the bind address cannot be changed without a daemon restart (Kestrel limitation).

This change is LAN-only. Internet exposure (DDNS, port forwarding, VPN) is the operator's responsibility and is explicitly out of scope. No HTTPS in this phase.

## Goals / Non-Goals

**Goals:**
- Allow the operator to opt in to LAN binding (`0.0.0.0`) via a config flag.
- Protect LAN access with a single shared passphrase, verified per request.
- Loopback callers (the operator's own machine) are always trusted — no passphrase required regardless of config.
- Preserve current loopback-only behaviour when the feature is disabled (default).
- All existing tests pass unchanged; `NullAuthPolicy.IsAuthorized` returns `true`.
- AOT-compatible throughout (no reflection-based middleware).

**Non-Goals:**
- HTTPS / TLS — deferred; operator must not expose the service to the public internet without external TLS termination.
- Per-user accounts, OIDC, or JWT — explicitly deferred; passphrase is a single shared secret.
- Internet access / DDNS / NAT traversal — operator's responsibility; unsupported.
- Passphrase encryption at rest — plaintext in `app.json`; acceptable for a home LAN station.
- Rate-limiting or brute-force protection — out of scope for this phase.

## Decisions

### D1 — Loopback requests always bypass passphrase check

**Decision:** If `HttpContext.Connection.RemoteIpAddress` is `127.0.0.1` or `::1`, `PassphraseAuthPolicy.IsAuthorized` returns `true` regardless of the configured passphrase.

**Rationale:** Eliminates the bootstrapping problem (how does the operator configure the passphrase if the UI requires it?). Loopback access implies physical or OS-level access to the machine, which is a stronger trust guarantee than any passphrase. Precedent: many embedded devices use the same model.

**Alternative considered:** Require passphrase from all origins. Rejected — the operator would be locked out the moment they enabled the feature before configuring the passphrase in a remote browser.

---

### D2 — REST: `X-Api-Key` header; WebSocket: `?key=` query parameter

**Decision:** The passphrase is presented as `X-Api-Key: <passphrase>` for REST requests. For WebSocket upgrade requests, it is presented as a `?key=<passphrase>` query parameter on the URL.

**Rationale:** The browser `WebSocket` constructor does not accept custom HTTP headers. The only practical options are query parameter, `Sec-WebSocket-Protocol` subprotocol hack, or a cookie. Query parameter is the most transparent. The WS upgrade is still an HTTP GET, so the auth middleware intercepts it before the socket is accepted.

**Risk:** The `?key=` value appears in server logs and browser history. Documented below. Acceptable for a home LAN; the operator is advised to treat the passphrase accordingly.

**Alternative considered:** First-frame auth (send passphrase as first WebSocket message after connect). Rejected — more complex, and the connection would be briefly open before auth is validated.

---

### D3 — Auth middleware placed before static files and routing

**Decision:** `app.Use(...)` auth middleware is registered first in `WebApp.Create`, before `UseStaticFiles`, `UseDefaultFiles`, and `MapGet`/`MapPost` routes.

**Rationale:** This ensures every request — including index.html, CSS, and JS assets — requires authentication when `PassphraseAuthPolicy` is active. An unauthenticated request to `/index.html` returns 401 rather than the page, preventing a partial information leak.

**AOT note:** The middleware uses a plain `app.Use(async (ctx, next) => ...)` lambda, which is AOT-compatible. No reflection, no attribute-based filters.

---

### D4 — Passphrase stored plaintext in `app.json`

**Decision:** `RemoteAccessConfig.Passphrase` is serialised as a plain string in `app.json`. No encryption, no hashing.

**Rationale:** The config file lives on the operator's own machine. Hashing would prevent the operator from reading their own passphrase back. A home LAN threat model does not require at-rest encryption of a shared passphrase. This is documented clearly in the UI disclaimer.

**Alternative considered:** Store a bcrypt hash, validate at auth time. Rejected — overkill for the threat model; adds a dependency; prevents recovery if the operator forgets the passphrase (no way to display it in settings).

---

### D5 — `IAuthPolicy` gains `bool IsAuthorized(HttpContext context)`

**Decision:** The existing marker interface gains a single method. `NullAuthPolicy` returns `true`; `PassphraseAuthPolicy` implements the loopback bypass + header/query-param check.

**Rationale:** The seam already exists for exactly this purpose. Adding one method is the minimal change; it avoids introducing a new interface or a parallel mechanism. All existing tests use `NullAuthPolicy` and are unaffected.

**AOT note:** `IAuthPolicy` is resolved from DI as a singleton; no `HttpContext` reflection. The `HttpContext` parameter is passed through the middleware lambda directly.

---

### D6 — Policy selection at daemon startup (not at request time)

**Decision:** `OpenWSFZ.Daemon` reads `RemoteAccessConfig` from the loaded config at startup and registers the appropriate `IBindPolicy` and `IAuthPolicy` singletons *before* `WebApp.Create` is called. The Kestrel bind address is set once at startup from the registered `IBindPolicy`.

**Implication:** Changing `RemoteAccess.Enabled` requires a daemon restart to take effect. The passphrase can be changed at runtime (the `PassphraseAuthPolicy` reads it from the registered `RemoteAccessConfig` instance at request time), but the bind address is fixed at startup.

**UI obligation:** The Remote Access settings page MUST display a prominent warning: "A restart is required for binding changes to take effect."

---

### D7 — Bind address: `IPAddress.Any` (0.0.0.0), not IPv4-mapped IPv6

**Decision:** `LanBindPolicy` resolves to `new IPEndPoint(IPAddress.Any, port)` (0.0.0.0). IPv6 dual-stack (`::`) is not used in this phase.

**Rationale:** Most home routers assign IPv4 addresses. IPv6 LAN is uncommon in the target environment. Dual-stack adds complexity for no practical gain at this stage. An operator on a pure-IPv6 network can contribute this in a future change.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Passphrase visible in server logs via `?key=` query parameter | Document in UI disclaimer; log the WS upgrade URL at Debug level only (not Info); note risk in design.md |
| Passphrase stored plaintext in `app.json`; readable by any process with filesystem access | Document risk; advise operator to restrict file permissions; treat as acceptable for home LAN |
| No HTTPS: passphrase transmitted in plaintext over LAN | Acceptable for home LAN; prominently documented; HTTPS deferred |
| Operator enables LAN binding without a passphrase | Permitted (null passphrase = open LAN access); UI warns clearly with disclaimer; operator's explicit choice |
| Restart required to change bind address | UI warns; this is a hard Kestrel constraint, not a design flaw |
| Brute-force attack over LAN | No rate-limiting in this phase; home LAN threat model does not require it; log 401 responses so suspicious activity is visible |

## Migration Plan

1. Default config (`Enabled = false`, `Passphrase = null`) preserves current behaviour exactly — no operator action required on upgrade.
2. Config files without a `remoteAccess` key deserialise to the default `RemoteAccessConfig()` via the STJ `JsonConstructor` pattern (same as `TxConfig`, `CatConfig`).
3. No data migration required; no breaking changes.

## Open Questions

None outstanding. All design decisions above are resolved.
