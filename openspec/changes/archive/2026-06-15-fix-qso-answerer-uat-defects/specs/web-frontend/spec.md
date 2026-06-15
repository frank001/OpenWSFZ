## ADDED Requirements

### Requirement: Settings page pre-fills TX numeric fields from loaded config

When the Settings page loads and fetches `GET /api/v1/config`, the TX tab's `watchdogMinutes` and `retryCount` number inputs SHALL be assigned the values returned in `config.tx.watchdogMinutes` and `config.tx.retryCount` respectively, in the same callback that populates all other TX form fields (callsign, grid, output device). This ensures that saving without modification preserves the existing values rather than submitting the browser default of `0`.

#### Scenario: Settings page pre-fills watchdogMinutes from config

- **WHEN** a browser loads `GET /settings.html` and `GET /api/v1/config` returns `{ "tx": { "watchdogMinutes": 4, ... } }`
- **THEN** the `watchdogMinutes` number input SHALL display `4` before the operator edits anything

#### Scenario: Settings page pre-fills retryCount from config

- **WHEN** a browser loads `GET /settings.html` and `GET /api/v1/config` returns `{ "tx": { "retryCount": 3, ... } }`
- **THEN** the `retryCount` number input SHALL display `3` before the operator edits anything

#### Scenario: Saving without changes does not trigger clamp warnings

- **WHEN** the operator opens the Settings page, makes no changes, and clicks Save
- **THEN** `POST /api/v1/config` SHALL submit `watchdogMinutes` ≥ 1 and `retryCount` ≥ 1, and the daemon SHALL NOT log a WRN clamp message
