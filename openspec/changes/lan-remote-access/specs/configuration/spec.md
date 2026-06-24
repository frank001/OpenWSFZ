## ADDED Requirements

### Requirement: Remote access configuration schema
The `AppConfig` schema SHALL include a `remoteAccess` object that controls LAN binding and passphrase authentication. If the `remoteAccess` key is absent from the config file, the daemon SHALL behave as if `remoteAccess` were `{ "enabled": false, "passphrase": null }` — the web interface remains loopback-only with no authentication change.

`RemoteAccessConfig` SHALL be a record with the following fields and defaults:

| Field | Type | Default | Description |
|---|---|---|---|
| `Enabled` | bool | `false` | When `true`, Kestrel binds to `0.0.0.0` instead of `127.0.0.1`. Requires daemon restart to take effect. |
| `Passphrase` | string? | `null` | Shared passphrase for non-loopback access. `null` or empty = no auth required. Stored as plaintext. |

All fields SHALL have defaults so that a partial or absent `remoteAccess` object loads without error.

#### Scenario: Missing remoteAccess key uses defaults
- **WHEN** the config file has no `remoteAccess` key
- **THEN** `AppConfig.RemoteAccess.Enabled` SHALL be `false` and `AppConfig.RemoteAccess.Passphrase` SHALL be `null`

#### Scenario: remoteAccess object with both fields round-trips correctly
- **WHEN** a config file contains `{ "remoteAccess": { "enabled": true, "passphrase": "test" } }`
- **THEN** `GET /api/v1/config` SHALL return `remoteAccess.enabled = true` and `remoteAccess.passphrase = "test"`
- **AND** `POST /api/v1/config` with a modified `remoteAccess` object SHALL persist the change

#### Scenario: remoteAccess.enabled false with passphrase set is valid
- **WHEN** the config file contains `{ "remoteAccess": { "enabled": false, "passphrase": "secret" } }`
- **THEN** the daemon SHALL start normally, bind to loopback, and ignore the passphrase

#### Scenario: Config file without remoteAccess field deserialises without error
- **WHEN** the daemon starts and `app.json` contains no `remoteAccess` key (i.e. a pre-LAN-access config file)
- **THEN** the daemon SHALL deserialise successfully with `RemoteAccess.Enabled = false` and SHALL start normally

#### Scenario: Default config created on first run includes remoteAccess with defaults
- **WHEN** the daemon creates a default config file on first run
- **THEN** the written file SHALL include a `remoteAccess` object with `enabled: false` and `passphrase: null`
