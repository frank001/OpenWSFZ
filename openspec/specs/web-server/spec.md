## Requirements

### Requirement: Self-hosted web page served on loopback

The daemon SHALL serve its web UI as static files from `http://127.0.0.1:<port>/`. A request to `GET /` SHALL return the `index.html` placeholder page with HTTP 200. No external web server or proxy SHALL be required.

#### Scenario: GET / returns the index page

- **WHEN** a client sends `GET /` to `http://127.0.0.1:<port>/`
- **THEN** the server SHALL respond with HTTP 200 and an HTML body

#### Scenario: Static files are served from the web directory

- **WHEN** a client requests a static asset (e.g., `GET /index.html`)
- **THEN** the server SHALL serve the file from the `web/` directory co-located with the executable

#### Scenario: Missing static file returns 404

- **WHEN** a client requests a path that does not correspond to a file under `web/`
- **THEN** the server SHALL respond with HTTP 404

---

### Requirement: Status REST endpoint

The daemon SHALL expose `GET /api/v1/status` returning a JSON `DaemonStatus` object. In Phase 1 this is a stub; its fields will be populated by later phases.

#### Scenario: Status endpoint returns 200 with JSON

- **WHEN** a client sends `GET /api/v1/status`
- **THEN** the server SHALL respond with HTTP 200, `Content-Type: application/json`, and a JSON body containing at minimum a `state` field with value `"Running"`

#### Scenario: Status endpoint is reachable immediately after banner

- **WHEN** the welcome banner has been printed on stdout
- **THEN** `GET /api/v1/status` SHALL return HTTP 200 without further delay

---

### Requirement: WebSocket endpoint

The daemon SHALL expose `GET /api/v1/ws` that accepts WebSocket upgrade requests. On connect, the server SHALL immediately push one `status` JSON event. The server SHALL push a `heartbeat` event every 5 seconds while the connection is open.

#### Scenario: WebSocket upgrade is accepted

- **WHEN** a client sends an HTTP Upgrade request to `GET /api/v1/ws`
- **THEN** the server SHALL respond with HTTP 101 Switching Protocols and establish the WebSocket connection

#### Scenario: Status event pushed on connect

- **WHEN** a WebSocket connection is established
- **THEN** the server SHALL send a JSON text frame containing a `status` event within 1 second of connect

#### Scenario: Heartbeat event pushed periodically

- **WHEN** a WebSocket connection has been open for 5 seconds
- **THEN** the server SHALL have sent at least one additional JSON frame (the heartbeat) to the client

#### Scenario: Non-WebSocket request to WS endpoint returns 400

- **WHEN** a plain HTTP GET (no Upgrade header) is sent to `/api/v1/ws`
- **THEN** the server SHALL respond with HTTP 400

---

### Requirement: Path traversal rejected by static file middleware

The static-file middleware SHALL NOT serve files outside the `web/` root directory. Path traversal attempts SHALL be rejected with HTTP 404 or 400.

#### Scenario: Path traversal attempt is rejected

- **WHEN** a client requests a path containing `..` segments (e.g., `GET /../appsettings.json`)
- **THEN** the server SHALL respond with HTTP 404 or 400 and SHALL NOT return any file contents from outside `web/`

---

### Requirement: Status endpoint includes active audio device

The `GET /api/v1/status` response SHALL include an `audioDevice` field containing the name of the currently configured audio capture device, or `null` if no device has been configured.

#### Scenario: Status includes configured device name

- **WHEN** a client sends `GET /api/v1/status` and an audio device is configured
- **THEN** the JSON response SHALL include an `audioDevice` field with the configured device's name as a non-empty string

#### Scenario: Status includes null when no device configured

- **WHEN** a client sends `GET /api/v1/status` and no audio device has been configured
- **THEN** the JSON response SHALL include an `audioDevice` field with a `null` value

#### Scenario: WebSocket status event includes audioDevice field

- **WHEN** a WebSocket connection is established
- **THEN** the initial `status` event's `payload` SHALL include an `audioDevice` field (either a string or `null`)
