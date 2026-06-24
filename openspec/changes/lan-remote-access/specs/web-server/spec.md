## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Authentication middleware applied to all requests
The web server SHALL apply authentication to every incoming HTTP request (including WebSocket upgrade requests and static file requests) by calling `IAuthPolicy.IsAuthorized(context)` before any routing or static-file middleware executes. If `IsAuthorized` returns `false`, the server SHALL respond with HTTP 401 and SHALL NOT forward the request to the application pipeline.

#### Scenario: Authorised request proceeds to handler
- **WHEN** `IAuthPolicy.IsAuthorized(context)` returns `true`
- **THEN** the request SHALL proceed normally through the middleware pipeline to the appropriate handler

#### Scenario: Unauthorised request returns 401 and halts
- **WHEN** `IAuthPolicy.IsAuthorized(context)` returns `false`
- **THEN** the server SHALL respond with HTTP 401
- **AND** SHALL NOT invoke any route handler, static file handler, or subsequent middleware

#### Scenario: NullAuthPolicy authorises all requests (existing behaviour)
- **WHEN** the registered `IAuthPolicy` is `NullAuthPolicy`
- **THEN** all requests SHALL be authorised and no 401 responses SHALL be emitted (existing tests unaffected)
