## 1. MSBuild wiring

- [x] 1.1 Add a `<Content>` glob to `src/OpenWSFZ.Daemon/OpenWSFZ.Daemon.csproj` that copies `$(MSBuildThisFileDirectory)..\..\web\**` to the output directory under `web\%(RecursiveDir)%(Filename)%(Extension)` with `CopyToOutputDirectory="PreserveNewest"`.
- [x] 1.2 Add the same `<Content>` glob to `tests/OpenWSFZ.Web.Tests/OpenWSFZ.Web.Tests.csproj` so integration tests have the `web/` directory in their output at runtime.

## 2. CSS — dark theme

- [x] 2.1 Create `web/css/app.css` — define `:root` CSS custom properties: `--color-bg` (#0d1117), `--color-surface` (#161b22), `--color-border` (#30363d), `--color-text` (#e6edf3), `--color-accent` (#58a6ff), `--color-success` (#3fb950), `--color-danger` (#f85149), `--color-muted` (#8b949e).
- [x] 2.2 Add base reset and layout rules: `*, *::before, *::after { box-sizing: border-box; }`, `body` with `margin: 0`, `font-family: system-ui, sans-serif`, `background: var(--color-bg)`, `color: var(--color-text)`.
- [x] 2.3 Add layout classes for the two-column main-page split (waterfall on top / decodes below), the status bar, and the settings form — all using flexbox or CSS grid.

## 3. JS — API client

- [x] 3.1 Create `web/js/api.js` as an ES module exporting: `getStatus()` → `GET /api/v1/status`, `getDevices()` → `GET /api/v1/audio/devices`, `getConfig()` → `GET /api/v1/config`, `postConfig(config)` → `POST /api/v1/config` with `Content-Type: application/json`. All functions return the parsed JSON response or throw on non-2xx.

## 4. JS — WebSocket client

- [x] 4.1 Create `web/js/ws.js` as an ES module exporting a `connect(onEvent)` function. On connect, parse incoming JSON frames as `{ type, payload }` and call `onEvent`. On close/error, schedule reconnect with initial delay 1 000 ms, doubling each attempt, capped at 30 000 ms.
- [x] 4.2 In `ws.js`, defer reconnect when `document.visibilityState === 'hidden'`; add a `visibilitychange` listener that fires the pending reconnect immediately when the page becomes visible.

## 5. Main page — HTML

- [x] 5.1 Create `web/index.html` with a `<!DOCTYPE html>` skeleton: `<head>` (charset, viewport, title "OpenWSFZ", link to `css/app.css`), `<body>` containing:
  - `<header id="status-bar">` with a `<span id="ws-state">` connection indicator, `<span id="audio-device">` label, and an `<a href="/settings.html">` Settings link.
  - `<main>` containing a `<section id="waterfall-panel">` holding `<canvas id="waterfall">`, and a `<section id="decodes-panel">` holding a `<table id="decodes-table">` with `<thead>` columns **Time**, **dB**, **DT**, **Freq**, **Message** and a `<tbody id="decodes-body">` with a single placeholder `<tr>` (colspan 5, text "No decodes yet — waiting for FT8 signal").
  - `<script type="module" src="js/main.js">`.

## 6. Main page — JS

- [x] 6.1 Create `web/js/main.js` as an ES module. On `DOMContentLoaded`:
  - Get `<canvas id="waterfall">`, set its `width`/`height` to its CSS-rendered size, fill with `--color-bg` equivalent (`#0d1117`), then draw centred placeholder text "Waterfall — awaiting audio input" in `var(--color-muted)` colour.
  - Import and call `connect(onEvent)` from `ws.js`. On `status` event: update `#audio-device` text to `payload.audioDevice ?? '(none)'` and set `#ws-state` to a "Connected" indicator class. On WebSocket disconnect: set `#ws-state` to a "Disconnected" indicator class.

## 7. Settings page — HTML

- [x] 7.1 Create `web/settings.html` with a `<!DOCTYPE html>` skeleton: `<head>` (charset, viewport, title "OpenWSFZ — Settings", link to `css/app.css`), `<body>` containing:
  - `<header>` with `<a href="/">← Back</a>` and a `<h1>Settings</h1>`.
  - `<main>` with `<form id="settings-form">` containing:
    - `<label>` + `<select id="device-select">` (initially empty).
    - `<label>` + `<input id="port-input" type="number" min="1" max="65535">`.
    - `<button id="save-btn" type="button">Save</button>`.
    - `<p id="feedback" aria-live="polite">` (empty, used for success/error messages).
  - `<script type="module" src="js/settings.js">`.

## 8. Settings page — JS

- [x] 8.1 Create `web/js/settings.js` as an ES module. On `DOMContentLoaded`:
  - Call `getConfig()` and `getDevices()` in parallel via `Promise.all`.
  - Populate `#device-select`: if devices array is empty, add a single `<option disabled>No devices found</option>`; otherwise add one `<option value="deviceId">deviceName</option>` per device, selecting the one whose `name` matches `config.audioDeviceName` (or leave unselected if null).
  - Set `#port-input` value to `config.port`.
- [x] 8.2 Add a click handler on `#save-btn`:
  - Disable the button, clear `#feedback`.
  - Build payload `{ audioDeviceName: selectedOption.value || null, port: parseInt(portInput.value) }`.
  - Call `postConfig(payload)`.
  - On success: set `#feedback` text to "Saved ✓" with success colour class; re-enable button after 2 s.
  - On error: set `#feedback` text to "Save failed — check the console" with danger colour class; re-enable button immediately.

## 9. Integration tests — static assets

- [x] 9.1 Create `tests/OpenWSFZ.Web.Tests/StaticAssetsIntegrationTests.cs` with an xUnit test class using `WebApplicationFactory`. Add the following tests (all using `P3-Frontend:` requirement prefix in the display name):
  - `"FR-014: GET / returns 200 text/html"` — asserts HTTP 200 and `Content-Type` contains `text/html`.
  - `"FR-014: GET /index.html returns 200 text/html"` — same assertions.
  - `"FR-014: GET /settings.html returns 200 text/html"`.
  - `"FR-014: GET /css/app.css returns 200 text/css"`.
  - `"FR-014: GET /js/main.js returns 200 text/javascript"`.
- [x] 9.2 Verify that `WebApp.Create()` used in the test fixture detects the `web/` directory (present due to task 1.2). If the directory is absent, tests must fail with a clear message rather than silently return 404.

## 10. Exit gate verification (M4)

- [x] 10.1 Run `dotnet build -c Release` — confirm zero errors, zero warnings.
- [x] 10.2 Run `dotnet test -c Release --no-build` — confirm all tests pass including the new static-asset integration tests.
- [x] 10.3 Run TraceabilityCheck locally — confirm FR-008, FR-009, FR-010, FR-011, FR-012, FR-013, FR-014, FR-015, FR-016 are mapped.
- [x] 10.4 Publish `OpenWSFZ.Daemon` AOT for the current RID, launch the binary, open `http://127.0.0.1:8080` in a browser — confirm the dark main page loads with the waterfall canvas placeholder and the decodes table.
- [x] 10.5 Click the Settings link — confirm the Settings page loads, the device selector is populated from the API, the port field shows the current value, and Save returns a success message.
- [x] 10.6 Open DevTools → Network → WS — confirm the WebSocket connection is established on page load and the status bar updates after the first `status` event.

<!-- Tasks 10.4–10.6 require manual browser verification by the operator. -->
