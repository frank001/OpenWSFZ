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
- `instanceId` (string, default `"OpenWSFZ"`) — the WSJT-X-protocol `Id` field sent in every
  outbound Heartbeat/Status/Decode/QSOLogged/Clear/Close datagram (see `external-reporting`
  capability). Operators running more than one simultaneous `OpenWSFZ.Daemon` instance (e.g. two
  bands captured via a split antenna) MUST give each instance a distinct value here, or companion
  programs that key off this field to distinguish multiple protocol-compatible instances (e.g.
  GridTracker) will not be able to tell them apart. Still meaningful under `role: "leader"`; a
  relaying `"follower"`'s own `instanceId` is read (relayed datagrams are already encoded using it
  before the leader ever sees them) but never appears on the leader's own outbound wire — see `role`.
- `role` (string enum `"leader"` | `"follower"`, default `"leader"`) — `"leader"` behaves exactly as
  this service always has: it opens its own outbound/inbound sockets to `targets` directly.
  `"follower"` opens no sockets to `targets` at all; every datagram it would have sent is instead
  relayed to `leaderUrl` (see `external-reporting` capability's leader/follower relay requirements).
- `leaderUrl` (nullable string, default `null`) — required and meaningful only when `role` is
  `"follower"`: the base URL of the leader daemon's own local HTTP host (e.g.
  `"http://127.0.0.1:8080"`) that this instance relays its datagrams to.
- `followerUrls` (array of string, default `[]`) — meaningful only when `role` is `"leader"`: base
  URLs of local follower instances this leader forwards an inbound Halt Tx to, in addition to acting
  on it itself.

An entry with `port` outside `1`–`65535` SHALL be rejected on save with the same validation-error
pattern used elsewhere in `POST /api/v1/config` (HTTP 400, no partial persistence).

#### Scenario: Missing externalReporting key uses defaults

- **WHEN** the config file has no `externalReporting` key
- **THEN** `AppConfig.ExternalReporting.Enabled` SHALL be `false` and `Targets` SHALL be an empty
  list, `RestrictExternalRepliesToDecodeFilter` SHALL be `false`, `InstanceId` SHALL be
  `"OpenWSFZ"`, `Role` SHALL be `"leader"`, `LeaderUrl` SHALL be `null`, and `FollowerUrls` SHALL be
  an empty list

#### Scenario: externalReporting object round-trips correctly

- **WHEN** a config file contains an `externalReporting` object with `enabled: true`, two target
  entries, `honourInboundCommands: true`, `restrictExternalRepliesToDecodeFilter: true`,
  `instanceId: "OpenWSFZ-20m"`, `role: "follower"`, and `leaderUrl: "http://127.0.0.1:8080"`
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

#### Scenario: Missing instanceId key on an existing externalReporting object defaults to "OpenWSFZ"

- **WHEN** a config file contains an `externalReporting` object from before this field existed
  (e.g. `{ "enabled": true, "targets": [...], "honourInboundCommands": true }` with no
  `instanceId` key)
- **THEN** `AppConfig.ExternalReporting.InstanceId` SHALL deserialise to `"OpenWSFZ"`, not `null` or
  an empty string, preserving single-instance behaviour for any pre-existing installation

#### Scenario: Settings-page-shaped save without instanceId preserves the previously-persisted value

- **WHEN** `POST /api/v1/config` includes an `externalReporting` object with `enabled`, `targets`,
  `honourInboundCommands`, and `restrictExternalRepliesToDecodeFilter` — the exact shape
  `web/js/settings.js`'s External Programs tab sends, which has no field for `instanceId` — and a
  non-default `InstanceId` was already persisted from an earlier, targeted save
- **THEN** the persisted `InstanceId` SHALL be unchanged; an ordinary, unrelated Settings-page save
  SHALL NOT silently revert it to `"OpenWSFZ"` (fix-external-reporting-appid-collision)

#### Scenario: Explicit instanceId reset to the literal default is honoured

- **WHEN** `POST /api/v1/config` includes `externalReporting.instanceId: "OpenWSFZ"` explicitly,
  regardless of whatever value was previously persisted
- **THEN** `AppConfig.ExternalReporting.InstanceId` SHALL be saved as `"OpenWSFZ"` — presence of the
  key in the request body, not its value, is what distinguishes an intentional reset from omission

#### Scenario: Missing role/leaderUrl/followerUrls keys on an existing externalReporting object default to leader behaviour

- **WHEN** a config file contains an `externalReporting` object from before these fields existed
  (e.g. `{ "enabled": true, "targets": [...], "instanceId": "OpenWSFZ-20m" }` with no `role`,
  `leaderUrl`, or `followerUrls` keys)
- **THEN** `AppConfig.ExternalReporting.Role` SHALL deserialise to `"leader"`, `LeaderUrl` SHALL
  deserialise to `null`, and `FollowerUrls` SHALL deserialise to an empty list, reproducing this
  instance's pre-existing direct-send behaviour exactly

#### Scenario: Settings-page-shaped save without role/leaderUrl/followerUrls preserves the previously-persisted values

- **WHEN** `POST /api/v1/config` includes an `externalReporting` object in the current
  `web/js/settings.js` shape (no `role`, `leaderUrl`, or `followerUrls` keys) and non-default values
  for those three fields were already persisted from an earlier, targeted save
- **THEN** the persisted `Role`, `LeaderUrl`, and `FollowerUrls` SHALL be unchanged — the same
  presence-in-source-JSON guard `instanceId` already uses (fix-external-reporting-appid-collision)
  applies identically to all three new fields

---

### Requirement: externalReporting configuration exposed via Settings REST API

`GET /api/v1/config` and `POST /api/v1/config` SHALL include the `externalReporting` object in their
request and response bodies alongside the existing config fields.

#### Scenario: GET /api/v1/config includes externalReporting section

- **WHEN** a client sends `GET /api/v1/config`
- **THEN** the response SHALL include an `externalReporting` object with `enabled`, `targets`,
  `honourInboundCommands`, `restrictExternalRepliesToDecodeFilter`, `instanceId`, `role`,
  `leaderUrl`, and `followerUrls` fields

#### Scenario: POST /api/v1/config with a new target persists and takes effect

- **WHEN** a client sends `POST /api/v1/config` with `{ "externalReporting": { "enabled": true,
  "targets": [{ "name": "GridTracker2", "host": "127.0.0.1", "port": 2237, "enabled": true }],
  "honourInboundCommands": false, "restrictExternalRepliesToDecodeFilter": false } }`
- **THEN** the daemon SHALL persist the change and `ExternalReportingService` SHALL begin sending
  outbound datagrams to `127.0.0.1:2237` without requiring a daemon restart

#### Scenario: POST /api/v1/config setting role to follower with a leaderUrl takes effect without restart

- **WHEN** a client sends `POST /api/v1/config` with `{ "externalReporting": { "enabled": true,
  "role": "follower", "leaderUrl": "http://127.0.0.1:8080", "targets": [...] } }` on an instance
  previously running as `"leader"`
- **THEN** the daemon SHALL persist the change and `ExternalReportingService` SHALL close its own
  direct sockets to `targets` and begin relaying to `leaderUrl` instead, without requiring a daemon
  restart
