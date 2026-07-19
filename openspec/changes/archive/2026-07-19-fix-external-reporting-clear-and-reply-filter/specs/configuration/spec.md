## MODIFIED Requirements

### Requirement: externalReporting configuration schema

`AppConfig` SHALL gain an `externalReporting` object with:
- `enabled` (bool, default `false`) — master switch; when `false`, `ExternalReportingService` opens
  no sockets
- `targets` (array, default `[]`) — each entry `{ name: string, host: string, port: int, enabled:
  bool }`; `name` is a free-text operator label (e.g. `"GridTracker2"`), not used on the wire
- `honourInboundCommands` (bool, default `false`) — whether inbound Reply/Free Text datagrams are
  acted upon; Halt Tx is unaffected by this flag (see `external-reporting` capability)
- `restrictExternalRepliesToDecodeFilter` (bool, default `false`) — when `false` (default), an
  inbound Reply naming a callsign currently hidden under the operator's decode-panel filter
  (`DecodeFilterState`) is still honoured by `qso-answerer`/`qso-caller`'s external-reply engagement
  paths; when `true`, such a Reply is rejected, matching the decode panel's own visibility exactly.
  Only meaningful when `honourInboundCommands` is also `true` (see `external-reporting` capability).

An entry with `port` outside `1`–`65535` SHALL be rejected on save with the same validation-error
pattern used elsewhere in `POST /api/v1/config` (HTTP 400, no partial persistence).

#### Scenario: Missing externalReporting key uses defaults

- **WHEN** the config file has no `externalReporting` key
- **THEN** `AppConfig.ExternalReporting.Enabled` SHALL be `false` and `Targets` SHALL be an empty
  list, and `RestrictExternalRepliesToDecodeFilter` SHALL be `false`

#### Scenario: externalReporting object round-trips correctly

- **WHEN** a config file contains an `externalReporting` object with `enabled: true`, two target
  entries, `honourInboundCommands: true`, and `restrictExternalRepliesToDecodeFilter: true`
- **THEN** `GET /api/v1/config` SHALL return those exact values and a subsequent `POST
  /api/v1/config` with a modified target list SHALL persist the change

#### Scenario: Out-of-range port rejected

- **WHEN** `POST /api/v1/config` includes an `externalReporting.targets` entry with `port: 70000`
- **THEN** the daemon SHALL return HTTP 400 and SHALL NOT persist any part of the request

#### Scenario: Default config includes externalReporting object with enabled false

- **WHEN** the daemon creates a default config file on first run
- **THEN** the written file SHALL include an `externalReporting` object with at minimum
  `"enabled": false, "targets": []`

#### Scenario: Missing restrictExternalRepliesToDecodeFilter key on an existing externalReporting object defaults to false

- **WHEN** a config file contains an `externalReporting` object from before this field existed
  (e.g. `{ "enabled": true, "targets": [...], "honourInboundCommands": true }` with no
  `restrictExternalRepliesToDecodeFilter` key)
- **THEN** `AppConfig.ExternalReporting.RestrictExternalRepliesToDecodeFilter` SHALL deserialise to
  `false`, preserving the new default (external Reply honoured regardless of the decode-panel
  filter) for any pre-existing installation

---

### Requirement: externalReporting configuration exposed via Settings REST API

`GET /api/v1/config` and `POST /api/v1/config` SHALL include the `externalReporting` object in their
request and response bodies alongside the existing config fields.

#### Scenario: GET /api/v1/config includes externalReporting section

- **WHEN** a client sends `GET /api/v1/config`
- **THEN** the response SHALL include an `externalReporting` object with `enabled`, `targets`,
  `honourInboundCommands`, and `restrictExternalRepliesToDecodeFilter` fields

#### Scenario: POST /api/v1/config with a new target persists and takes effect

- **WHEN** a client sends `POST /api/v1/config` with `{ "externalReporting": { "enabled": true,
  "targets": [{ "name": "GridTracker2", "host": "127.0.0.1", "port": 2237, "enabled": true }],
  "honourInboundCommands": false, "restrictExternalRepliesToDecodeFilter": false } }`
- **THEN** the daemon SHALL persist the change and `ExternalReportingService` SHALL begin sending
  outbound datagrams to `127.0.0.1:2237` without requiring a daemon restart
