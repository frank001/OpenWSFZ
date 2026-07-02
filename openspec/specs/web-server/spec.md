## Purpose

This capability defines the daemon's self-hosted web surface served on loopback: static page hosting with path-traversal protection, the status REST endpoint, and the WebSocket endpoint that streams live state to the frontend.
## Requirements
### Requirement: Self-hosted web page served on loopback

The daemon SHALL serve its web UI as static files from `http://<host>:<port>/`, where `<host>` is `127.0.0.1` when `RemoteAccess.Enabled` is `false` (the default), and `0.0.0.0` (all interfaces) when `RemoteAccess.Enabled` is `true`. A request to `GET /` SHALL return the `index.html` placeholder page with HTTP 200. No external web server or proxy SHALL be required.

#### Scenario: GET / returns the index page

- **WHEN** a client sends `GET /` to the bound address and port
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

### Requirement: Frequency list REST endpoints

The web server SHALL expose `GET /api/v1/frequencies` and `POST /api/v1/frequencies` endpoints to allow the UI to read and write the operator's frequency list.

#### Scenario: GET /api/v1/frequencies returns the full entry list

- **WHEN** a client sends `GET /api/v1/frequencies`
- **THEN** the server SHALL respond with HTTP 200, `Content-Type: application/json`, and the current in-memory frequency list as a JSON array of frequency entry objects, each with `protocol`, `frequencyMHz`, and `description` fields

#### Scenario: GET /api/v1/frequencies returns an empty array when list is empty

- **WHEN** a client sends `GET /api/v1/frequencies` and `IFrequencyStore.Entries` is empty
- **THEN** the server SHALL respond with HTTP 200 and a JSON body of `[]`

#### Scenario: POST /api/v1/frequencies accepts and persists a new list

- **WHEN** a client sends `POST /api/v1/frequencies` with a valid JSON array of frequency entry objects
- **THEN** the server SHALL call `IFrequencyStore.SaveAsync` with the provided list, respond with HTTP 200, and return the saved list as the response body

#### Scenario: POST /api/v1/frequencies with malformed JSON returns 400

- **WHEN** a client sends `POST /api/v1/frequencies` with a body that is not a valid JSON array of frequency entries
- **THEN** the server SHALL respond with HTTP 400 and SHALL NOT modify or persist the frequency list

#### Scenario: POST /api/v1/frequencies with an empty array clears the list

- **WHEN** a client sends `POST /api/v1/frequencies` with a body of `[]`
- **THEN** the server SHALL accept it, persist an empty list, and respond with HTTP 200

---

### Requirement: Tune action endpoint

The web server SHALL expose `POST /api/v1/tune` to allow the UI to change the active dial frequency. The endpoint abstracts the two possible outcomes based on current CAT state:

- **CAT active** (`ICatState.Status` is `Connected` or `Connecting`): the endpoint SHALL call `IRadioConnection.SetDialFrequencyMhzAsync` and update `ICatState.DialFrequencyMHz` optimistically with the requested value
- **CAT inactive** (`ICatState.Status` is `Disabled` or `Error`): the endpoint SHALL update `AppConfig.DecodeLog.DialFrequencyMHz` to the requested value and call `IConfigStore.SaveAsync()`

The response SHALL always return HTTP 200 with `{ "effectiveFrequencyMHz": <number> }` so the caller does not need to know which path was taken.

#### Scenario: POST /api/v1/tune with CAT active commands the rig

- **WHEN** `ICatState.Status` is `Connected` and a client sends `POST /api/v1/tune` with `{ "frequencyMHz": 14.074 }`
- **THEN** the server SHALL call `IRadioConnection.SetDialFrequencyMhzAsync(14.074)`
- **AND** `ICatState.DialFrequencyMHz` SHALL be updated to `14.074` optimistically
- **AND** the response SHALL be HTTP 200 with `{ "effectiveFrequencyMHz": 14.074 }`

#### Scenario: POST /api/v1/tune with CAT disabled updates config

- **WHEN** `ICatState.Status` is `Disabled` and a client sends `POST /api/v1/tune` with `{ "frequencyMHz": 7.074 }`
- **THEN** `AppConfig.DecodeLog.DialFrequencyMHz` SHALL be updated to `7.074` and persisted via `IConfigStore.SaveAsync()`
- **AND** the response SHALL be HTTP 200 with `{ "effectiveFrequencyMHz": 7.074 }`

#### Scenario: POST /api/v1/tune with missing or invalid frequencyMHz returns 400

- **WHEN** a client sends `POST /api/v1/tune` with a body lacking `frequencyMHz` or with a non-numeric value
- **THEN** the server SHALL respond with HTTP 400 and SHALL NOT modify any state

#### Scenario: POST /api/v1/tune with negative frequencyMHz returns 400

- **WHEN** a client sends `POST /api/v1/tune` with `{ "frequencyMHz": -1.0 }`
- **THEN** the server SHALL respond with HTTP 400

#### Scenario: POST /api/v1/tune CAT set failure returns 502

- **WHEN** `ICatState.Status` is `Connected` and `IRadioConnection.SetDialFrequencyMhzAsync` throws an exception
- **THEN** the server SHALL log a Warning with the exception detail and respond with HTTP 502 (Bad Gateway) without updating `ICatState.DialFrequencyMHz`

---

### Requirement: Authentication middleware applied to all requests
The web server SHALL apply authentication to every incoming HTTP request (including WebSocket upgrade requests and static file requests) by calling `IAuthPolicy.IsAuthorized(remoteIp, apiKeyHeader, keyQueryParam)` before any routing or static-file middleware executes. The middleware extracts these three values from `HttpContext` and passes them through.

**Public paths** — the following paths are exempt from authentication so that a remote browser can load the login page and its dependent resources without presenting a key:
- `/login.html` — the passphrase form itself
- `/css/*` — stylesheets (browsers cannot carry `?key=` into `<link rel="stylesheet">` requests)
- `/js/*` — ES module scripts (same constraint)
- `/favicon.ico` — browser chrome

All other paths (API endpoints, WebSocket upgrade, root `/`, and all HTML pages) are subject to the auth check.

**When `IsAuthorized` returns `false`:**
- For **API and WebSocket paths** (path starts with `/api`): the server SHALL respond with HTTP 401 so that JavaScript callers can detect the failure and redirect programmatically.
- For **all other paths** (browser page-loads): the server SHALL respond with HTTP 302 redirecting to `/login.html?return=<percent-encoded-original-path>` so the browser can present the passphrase form and return to the originally-requested page after login.

#### Scenario: Authorised request proceeds to handler
- **WHEN** `IAuthPolicy.IsAuthorized(remoteIp, apiKeyHeader, keyQueryParam)` returns `true`
- **THEN** the request SHALL proceed normally through the middleware pipeline to the appropriate handler

#### Scenario: Unauthorised API request returns 401
- **WHEN** `IAuthPolicy.IsAuthorized` returns `false` for a request whose path starts with `/api`
- **THEN** the server SHALL respond with HTTP 401
- **AND** SHALL NOT invoke any route handler or subsequent middleware

#### Scenario: Unauthorised browser page-load redirects to login page
- **WHEN** `IAuthPolicy.IsAuthorized` returns `false` for a non-API, non-public request (e.g. `GET /`, `GET /settings.html`)
- **THEN** the server SHALL respond with HTTP 302 and a `Location` header of `/login.html?return=<percent-encoded-path>`

#### Scenario: Public static assets are served without auth
- **WHEN** a request path matches a public path (`/login.html`, `/css/*`, `/js/*`, `/favicon.ico`)
- **THEN** the server SHALL serve the resource without invoking `IAuthPolicy.IsAuthorized`

#### Scenario: NullAuthPolicy authorises all requests (existing behaviour)
- **WHEN** the registered `IAuthPolicy` is `NullAuthPolicy`
- **THEN** all requests SHALL be authorised and no 401 or 302 auth responses SHALL be emitted (existing tests unaffected)

