## Context

The daemon already serves static files from a `web/` directory co-located with the executable (`AppContext.BaseDirectory + "web/"`). P1 established the static-file middleware; P2 wired REST and WebSocket APIs. What is missing is the actual content of `web/` — today it contains only a stub placeholder. P3 delivers real pages that let an operator use the application.

Constraints:
- Vanilla HTML/CSS/JS only — no bundler, no Node toolchain, no frameworks.
- All files are plain files on disk, user-editable (FR-015).
- Every visible control must be backed by a working endpoint (FR-016).
- Waterfall (FR-008) and decoded-messages population (FR-009) are structural placeholders in P3; real data arrives in P5 (FT8 decoder).

## Goals / Non-Goals

**Goals:**
- Deliver `index.html` (main page) and `settings.html` (Settings page) with correct layout and dark theme.
- Wire Settings page to `GET /api/v1/audio/devices`, `GET /api/v1/config`, `POST /api/v1/config`.
- Wire status bar on main page to `GET /api/v1/status` and the `/api/v1/ws` WebSocket.
- Establish the frontend file structure that Phase 5 will extend without restructuring.
- Ensure build/publish copies `web/` to the output directory automatically.

**Non-Goals:**
- Painting real waterfall data (audio rendering is Phase 5).
- Populating decoded-messages rows (FT8 decoder is Phase 5).
- Multi-page routing (there are two pages — plain `<a>` links suffice).
- Authentication, TLS, or non-loopback concerns (deferred per NFR-004).
- Any CSS theme other than the default dark theme (FR-013 — operator edits files directly).

## Decisions

### 1. Source location: repo-root `web/` folder, MSBuild copies to output

The `web/` directory lives at the repository root, satisfying FR-014 ("own top-level folder"). The `OpenWSFZ.Daemon.csproj` includes a glob that copies the entire tree to the output directory at build time:

```xml
<ItemGroup>
  <Content Include="$(MSBuildThisFileDirectory)..\..\web\**"
           CopyToOutputDirectory="PreserveNewest"
           Link="web\%(RecursiveDir)%(Filename)%(Extension)" />
</ItemGroup>
```

This keeps frontend files user-editable in place (FR-015) while ensuring `dotnet run`, `dotnet build`, and AOT publish all have the correct `web/` alongside the binary.

*Alternatives considered:*
- Embedding assets as resources: rejected — prevents user editing (violates FR-015).
- Placing `web/` inside `src/OpenWSFZ.Daemon/`: rejected — not a "top-level folder" (violates FR-014).

### 2. Two-page structure: `index.html` + `settings.html`

No client-side router. The main page and Settings page are separate HTML documents linked with `<a href="/settings.html">` and `<a href="/">`. This is the simplest approach consistent with no bundler and no framework.

*Alternatives considered:* Single-page hash routing — unnecessary complexity for two pages.

### 3. CSS custom properties for theming

The dark theme is implemented via CSS custom properties in `css/app.css`:

```css
:root {
  --color-bg:        #0d1117;
  --color-surface:   #161b22;
  --color-border:    #30363d;
  --color-text:      #e6edf3;
  --color-accent:    #58a6ff;
  --color-success:   #3fb950;
  --color-danger:    #f85149;
  --color-muted:     #8b949e;
}
```

An operator who wants to change the theme edits these properties in the file — no in-app switcher (FR-013).

### 4. Waterfall panel: `<canvas>` placeholder

The main page includes a `<canvas id="waterfall">` that fills its container. In P3, `js/main.js` paints it with a solid dark background and centred placeholder text ("Waterfall — awaiting audio input"). The canvas element and its sizing CSS are final; Phase 5 only adds the painting logic.

### 5. Decoded-messages panel: `<table>` with empty body

A `<table>` with columns **Time**, **dB**, **DT**, **Freq**, **Message** matches the WSJT-X layout. In P3 the `<tbody>` contains a single no-data row ("No decodes yet — waiting for FT8 signal"). Phase 5 inserts `<tr>` rows without touching the table structure.

### 6. JavaScript module structure

Four ES-module files, no bundler:

| File | Responsibility |
|------|---------------|
| `js/api.js` | Thin fetch wrappers around all REST endpoints (`getStatus`, `getDevices`, `getConfig`, `postConfig`). |
| `js/ws.js` | WebSocket client — connects to `/api/v1/ws`, dispatches `status`/`heartbeat` events, auto-reconnects with exponential back-off (initial 1 s, max 30 s, factor 2). |
| `js/main.js` | Main-page logic — initialises canvas placeholder, connects WebSocket, updates status bar on `status` events. |
| `js/settings.js` | Settings-page logic — loads config and device list on `DOMContentLoaded`, populates select, handles Save click. |

All files use `<script type="module">` — no global namespace pollution.

### 7. Settings page Save flow

1. `DOMContentLoaded`: fetch `GET /api/v1/config` (populate port field) + `GET /api/v1/audio/devices` (populate device selector; pre-select `audioDeviceName` from config).
2. Save click: disable button, `POST /api/v1/config` with `{ audioDeviceName, port }`.
   - HTTP 200 → show "Saved ✓" feedback for 2 s.
   - HTTP 400 / network error → show inline error message.

### 8. WebSocket reconnect strategy

`js/ws.js` uses a simple doubling back-off: 1 s → 2 s → 4 s … → 30 s (capped). On reconnect the status bar updates its indicator. No reconnect attempt is made if the page is hidden (`document.visibilityState === 'hidden'`) — reconnect is deferred until the page becomes visible again.

### 9. Integration tests for static assets

The existing `AudioConfigIntegrationTests` class in `OpenWSFZ.Web.Tests` is extended with a small set of static-asset tests: verify `GET /`, `GET /index.html`, `GET /settings.html`, `GET /css/app.css`, and `GET /js/main.js` all return HTTP 200 with correct `Content-Type` headers. These tests use `WebApplicationFactory` with a `web/` directory pointed at the repo root's real `web/` folder.

## Risks / Trade-offs

- **`web/` path in tests**: Integration tests need the real `web/` directory at runtime. The `WebApplicationFactory` will need `AppContext.BaseDirectory` to include the `web/` folder — ensured by the MSBuild `Content` glob above. If tests break because the folder is missing, check that `<CopyToOutputDirectory>` is set and `dotnet build` was run.

- **ES module support**: `type="module"` requires a server (modules cannot load from `file://`). Since the app always runs behind Kestrel this is fine, but developers cannot simply open `index.html` from disk. Document this in the README.

- **Canvas scaling on HiDPI**: Not addressed in P3. Phase 5 (real waterfall) will need to handle `devicePixelRatio`. The placeholder just uses CSS sizing.

- **Settings page with no audio devices**: If `GET /api/v1/audio/devices` returns `[]`, the selector shows a single disabled `<option>` with text "No devices found". Saving with no device selected sends `audioDeviceName: null`.

## Open Questions

*(none — all decisions are made above)*
