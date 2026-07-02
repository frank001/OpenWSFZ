## Purpose

This capability defines how OpenWSFZ supports access from other devices on the local network (LAN). It covers the bind-address policy (loopback vs. all-interfaces), passphrase authentication for non-loopback connections, and the policy-selection logic at daemon startup.
## Requirements
### Requirement: LAN bind policy
When `RemoteAccess.Enabled` is `true`, the daemon SHALL bind Kestrel to `0.0.0.0` (all IPv4 interfaces) at the configured port, making the web interface reachable from other devices on the local network. When `RemoteAccess.Enabled` is `false` (the default), the daemon SHALL bind to `127.0.0.1` only, preserving the Phase 1 loopback-only behaviour.

The bind address is resolved once at daemon startup via `IBindPolicy.Resolve`. Changing `RemoteAccess.Enabled` requires a daemon restart to take effect.

#### Scenario: LAN binding active when Enabled is true
- **WHEN** `RemoteAccess.Enabled` is `true` in the loaded config
- **THEN** `LanBindPolicy.Resolve` SHALL return an `IPEndPoint` with `IPAddress.Any` (0.0.0.0) and the configured port

#### Scenario: Loopback binding preserved when Enabled is false
- **WHEN** `RemoteAccess.Enabled` is `false` (the default)
- **THEN** `LoopbackBindPolicy.Resolve` SHALL return an `IPEndPoint` with `IPAddress.Loopback` (127.0.0.1) and the configured port

#### Scenario: Daemon startup selects LanBindPolicy when remote access enabled
- **WHEN** the daemon starts with `RemoteAccess.Enabled = true`
- **THEN** the registered `IBindPolicy` singleton SHALL be `LanBindPolicy`

#### Scenario: Daemon startup selects LoopbackBindPolicy when remote access disabled
- **WHEN** the daemon starts with `RemoteAccess.Enabled = false` (or `RemoteAccess` absent from config)
- **THEN** the registered `IBindPolicy` singleton SHALL be `LoopbackBindPolicy`

---

### Requirement: Passphrase authentication for non-loopback requests
When `RemoteAccess.Enabled` is `true` and `RemoteAccess.Passphrase` is a non-null, non-empty string, the daemon SHALL require all requests from non-loopback origins to present the passphrase. Requests that fail authentication are handled as follows: API paths (`/api/*`) receive HTTP 401; browser page-loads receive HTTP 302 to `/login.html?return=<original-path>`; static public paths (`/login.html`, `/css/*`, `/js/*`, `/favicon.ico`) are exempt and always served. See `specs/web-server/spec.md` for the full middleware rules.

The passphrase is carried differently by request type:
- **REST requests**: `X-Api-Key: <passphrase>` request header
- **WebSocket upgrade requests**: `?key=<passphrase>` query parameter on the WebSocket URL

#### Scenario: Correct passphrase in X-Api-Key header allows REST request
- **WHEN** a non-loopback client sends `GET /api/v1/status` with `X-Api-Key: correct-passphrase`
- **AND** `RemoteAccess.Passphrase` is `"correct-passphrase"`
- **THEN** the server SHALL respond with HTTP 200

#### Scenario: Wrong passphrase in X-Api-Key header returns 401
- **WHEN** a non-loopback client sends `GET /api/v1/status` with `X-Api-Key: wrong`
- **AND** `RemoteAccess.Passphrase` is `"correct-passphrase"`
- **THEN** the server SHALL respond with HTTP 401 and SHALL NOT process the request

#### Scenario: Missing X-Api-Key header returns 401
- **WHEN** a non-loopback client sends `GET /api/v1/status` with no `X-Api-Key` header
- **AND** `RemoteAccess.Passphrase` is a non-empty string
- **THEN** the server SHALL respond with HTTP 401

#### Scenario: Correct passphrase in ?key= query parameter allows WebSocket upgrade
- **WHEN** a non-loopback client sends a WebSocket upgrade to `/api/v1/ws?key=correct-passphrase`
- **AND** `RemoteAccess.Passphrase` is `"correct-passphrase"`
- **THEN** the server SHALL respond with HTTP 101 Switching Protocols

#### Scenario: Wrong passphrase in ?key= query parameter rejects WebSocket upgrade
- **WHEN** a non-loopback client sends a WebSocket upgrade to `/api/v1/ws?key=wrong`
- **AND** `RemoteAccess.Passphrase` is `"correct-passphrase"`
- **THEN** the server SHALL respond with HTTP 401

---

### Requirement: Loopback requests bypass passphrase check
Requests originating from `127.0.0.1` or `::1` SHALL always be authorised, regardless of whether a passphrase is configured or presented. This ensures the operator can always access the UI from their own machine, including during initial configuration.

#### Scenario: Loopback request with no passphrase header always succeeds
- **WHEN** a request arrives from `127.0.0.1` or `::1` with no `X-Api-Key` header
- **AND** `RemoteAccess.Passphrase` is a non-empty string
- **THEN** the server SHALL respond with HTTP 200 (not 401)

#### Scenario: Loopback WebSocket upgrade without ?key= always succeeds
- **WHEN** a WebSocket upgrade request arrives from `127.0.0.1` or `::1` with no `?key=` parameter
- **AND** `RemoteAccess.Passphrase` is a non-empty string
- **THEN** the server SHALL respond with HTTP 101 Switching Protocols

---

### Requirement: No authentication when passphrase is not configured
When `RemoteAccess.Passphrase` is `null` or empty, the daemon SHALL accept all requests from any origin without a passphrase, even if `RemoteAccess.Enabled` is `true`. This allows LAN access without a passphrase at the operator's explicit choice.

#### Scenario: LAN access without passphrase when Passphrase is null
- **WHEN** `RemoteAccess.Enabled` is `true` and `RemoteAccess.Passphrase` is `null`
- **THEN** `PassphraseAuthPolicy.IsAuthorized` SHALL return `true` for all origins

#### Scenario: NullAuthPolicy always authorises (backward-compatibility)
- **WHEN** the registered `IAuthPolicy` is `NullAuthPolicy`
- **THEN** `IsAuthorized(remoteIp, apiKeyHeader, keyQueryParam)` SHALL return `true` regardless of any parameter values

---

### Requirement: Policy selection at daemon startup
The daemon SHALL select the `IBindPolicy` and `IAuthPolicy` implementations at startup based on `RemoteAccessConfig`:

| `Enabled` | `Passphrase` | `IBindPolicy` | `IAuthPolicy` |
|---|---|---|---|
| `false` (or config absent) | any | `LoopbackBindPolicy` | `NullAuthPolicy` |
| `true` | `null` or empty | `LanBindPolicy` | `NullAuthPolicy` |
| `true` | non-empty string | `LanBindPolicy` | `PassphraseAuthPolicy` |

#### Scenario: Enabled=false → LoopbackBindPolicy + NullAuthPolicy
- **WHEN** the daemon starts with `RemoteAccess.Enabled = false`
- **THEN** the DI container SHALL resolve `IBindPolicy` as `LoopbackBindPolicy` and `IAuthPolicy` as `NullAuthPolicy`

#### Scenario: Enabled=true, no passphrase → LanBindPolicy + NullAuthPolicy
- **WHEN** the daemon starts with `RemoteAccess.Enabled = true` and `RemoteAccess.Passphrase = null`
- **THEN** the DI container SHALL resolve `IBindPolicy` as `LanBindPolicy` and `IAuthPolicy` as `NullAuthPolicy`

#### Scenario: Enabled=true, passphrase set → LanBindPolicy + PassphraseAuthPolicy
- **WHEN** the daemon starts with `RemoteAccess.Enabled = true` and `RemoteAccess.Passphrase = "secret"`
- **THEN** the DI container SHALL resolve `IBindPolicy` as `LanBindPolicy` and `IAuthPolicy` as `PassphraseAuthPolicy`
