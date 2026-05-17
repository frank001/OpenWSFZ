## ADDED Requirements

### Requirement: Daemon serves the bundled web UI at the root

The daemon SHALL serve the contents of the `web/` directory as static
assets, with `GET /` returning `web/index.html`. Content types MUST be
inferred from file extension for at minimum `.html`, `.css`, `.js`,
`.json`, `.svg`, `.png`.

#### Scenario: Root request returns the UI shell

- **WHEN** an HTTP client issues `GET /` against the daemon
- **THEN** the response status is 200
- **AND** the response body is the content of `web/index.html`
- **AND** the `Content-Type` header begins with `text/html`

#### Scenario: Nested asset served with correct type

- **WHEN** an HTTP client issues `GET /app.js`
- **THEN** the response status is 200
- **AND** the `Content-Type` header is `application/javascript` or
  `text/javascript`

#### Scenario: Missing asset returns 404

- **WHEN** an HTTP client requests a path that does not resolve to a
  file under `web/`
- **THEN** the response status is 404

### Requirement: Health endpoint reports daemon liveness and version

The daemon SHALL expose `GET /api/health` returning HTTP 200 with a
JSON body that includes the daemon's semantic version, uptime in
seconds, and a status string equal to `"ok"` while the daemon is
serving traffic.

#### Scenario: Health probe shape

- **WHEN** an HTTP client issues `GET /api/health`
- **THEN** the response status is 200
- **AND** the `Content-Type` is `application/json`
- **AND** the body parses as a JSON object containing the keys
  `status`, `version`, and `uptime_seconds`
- **AND** `status` equals `"ok"`
- **AND** `uptime_seconds` is a non-negative number

### Requirement: WebSocket endpoint accepts JSON envelopes

The daemon SHALL expose a WebSocket endpoint at `/ws` that accepts and
emits text frames containing a JSON object with the keys `type`
(string), `id` (string or number), `ts` (ISO-8601 timestamp string),
and an optional `payload` object. Frames that fail to parse as JSON
or that omit `type` or `id` MUST be rejected with a `type: "error"`
reply carrying the original `id` if it was parsed, plus a human-
readable `payload.message`.

#### Scenario: Well-formed envelope accepted

- **WHEN** a client connects to `/ws` and sends a text frame
  `{"type":"ping","id":"abc","ts":"2026-05-17T10:00:00.000Z"}`
- **THEN** the daemon does not close the connection
- **AND** the daemon emits a reply envelope within 1 second

#### Scenario: Malformed JSON rejected

- **WHEN** a client connects to `/ws` and sends the text frame `not json`
- **THEN** the daemon emits a reply with `type: "error"` and a non-empty
  `payload.message`
- **AND** the connection remains open

#### Scenario: Missing required field rejected

- **WHEN** a client sends `{"type":"ping"}` (no `id`, no `ts`)
- **THEN** the daemon emits a reply with `type: "error"` describing
  the missing field(s)
- **AND** the connection remains open

### Requirement: Ping and echo are the only registered types in the skeleton

In this change the daemon SHALL handle exactly two envelope types and
reserve the registry for later capabilities. `type: "ping"` MUST be
answered with `type: "pong"` carrying the same `id`, a fresh `ts`,
and a `payload.echoed` equal to the request's `payload` if any.
Envelopes with any other recognised `type` value SHALL be answered
with `type: "echo"` containing the entire received envelope under
`payload.original`. The registry of recognised types is open for
extension by later capabilities.

#### Scenario: Ping receives pong

- **WHEN** a client sends `{"type":"ping","id":"42","ts":"...","payload":{"n":1}}`
- **THEN** the reply has `type: "pong"`
- **AND** the reply's `id` equals `"42"`
- **AND** the reply's `payload.echoed` equals `{"n":1}`

#### Scenario: Unknown type returns echo

- **WHEN** a client sends an envelope with `type: "future-feature"`
- **THEN** the reply has `type: "echo"`
- **AND** the reply's `payload.original` is the full original envelope
