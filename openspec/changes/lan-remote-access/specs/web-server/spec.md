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
