## ADDED Requirements

### Requirement: TX configuration schema

The `AppConfig` schema SHALL include a `Tx` property of type `TxConfig`. If the `tx` key is absent from the config file, the daemon SHALL behave as if `tx` were the default `TxConfig()` — no TX behaviour changes and the system remains receive-only.

`TxConfig` SHALL be a record with the following fields and defaults:

| Field | Type | Default | Description |
|---|---|---|---|
| `AutoAnswer` | bool | `false` | Master enable for the QSO auto-answerer. When `false` the state machine remains in `Idle` regardless of decoded CQs and no transmission occurs. The operator must set this to `true` via Settings before any auto-answer TX takes place. |
| `Callsign` | string | `"Q1OFZ"` | Our station callsign. Default is a Q-prefix ITU-unallocated call per NFR-021. |
| `Grid` | string | `"JO33"` | Our Maidenhead grid locator (4-character minimum). |
| `RetryCount` | int | `3` | Number of retransmits per waiting state before aborting the QSO. |
| `WatchdogMinutes` | int | `4` | Watchdog timer duration in minutes. Matching WSJT-X default. |

All fields SHALL have defaults so that a partial or absent `tx` object loads without error.

#### Scenario: Missing tx key uses defaults

- **WHEN** the config file has no `tx` key
- **THEN** `AppConfig.Tx.AutoAnswer` SHALL be `false`, `Tx.Callsign` SHALL be `"Q1OFZ"`, `Tx.Grid` SHALL be `"JO33"`, `Tx.RetryCount` SHALL be `3`, and `Tx.WatchdogMinutes` SHALL be `4`

#### Scenario: AutoAnswer defaults to false — no transmission without explicit opt-in

- **WHEN** the config file has no `tx` key, or `tx.autoAnswer` is absent or `false`
- **THEN** the `QsoAnswererService` SHALL remain in `Idle` regardless of decoded CQ messages and SHALL NOT transmit

#### Scenario: tx object round-trips correctly

- **WHEN** a config file contains `{ "tx": { "callsign": "Q9XYZ", "grid": "IO91", "retryCount": 5, "watchdogMinutes": 8 } }`
- **THEN** `GET /api/v1/config` SHALL return those exact values and `POST /api/v1/config` with a modified `tx` object SHALL persist the change

#### Scenario: Default config file includes tx object

- **WHEN** the daemon creates a default config file on first run
- **THEN** the written file SHALL include a `tx` object with all four fields set to their default values

#### Scenario: RetryCount below 1 is clamped to 1

- **WHEN** `tx.retryCount` is set to `0` or a negative value
- **THEN** the daemon SHALL clamp it to `1`, log a Warning, and use the clamped value

#### Scenario: WatchdogMinutes below 1 is clamped to 1

- **WHEN** `tx.watchdogMinutes` is set to `0` or a negative value
- **THEN** the daemon SHALL clamp it to `1`, log a Warning, and use the clamped value

---

### Requirement: TX configuration exposed via Settings REST API

`GET /api/v1/config` and `POST /api/v1/config` SHALL include the `tx` object in their request and response bodies alongside existing config fields.

#### Scenario: GET /api/v1/config includes tx section

- **WHEN** a client sends `GET /api/v1/config`
- **THEN** the response SHALL include a `tx` object with `autoAnswer`, `callsign`, `grid`, `retryCount`, and `watchdogMinutes` fields

#### Scenario: POST /api/v1/config with updated callsign persists change

- **WHEN** a client sends `POST /api/v1/config` with `{ "tx": { "autoAnswer": true, "callsign": "Q9XYZ", "grid": "IO91", "retryCount": 3, "watchdogMinutes": 4 } }`
- **THEN** the daemon SHALL persist the change and subsequent calls to `QsoAnswererService` SHALL use `Q9XYZ` as the station callsign with auto-answer enabled
