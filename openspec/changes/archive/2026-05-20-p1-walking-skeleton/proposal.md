## Why

Phase 0 delivered a working CI pipeline and tooling foundation, but no product code exists yet. Phase 1 establishes the minimal end-to-end skeleton: the daemon boots, prints a welcome banner, serves a placeholder web page, accepts a WebSocket connection, and shuts down cleanly. This is Milestone M2 — the first moment the daemon serves a browser — and it proves the core architectural seams (`IBindPolicy`, `IAuthPolicy`, `IHostLifecycle`, WebSocket hub) work together before any audio or decode complexity is added.

## What Changes

- **New project `OpenWSFZ.Daemon`** — the AOT-enabled executable and composition root, replacing `OpenWSFZ.AotProbe` as the primary AOT publish prove-out. Implements `WelcomeBannerEmitter`, Ctrl-C / SIGTERM / SIGINT handling, and DI wiring via `Microsoft.Extensions.Hosting`.
- **New project `OpenWSFZ.Web`** — Kestrel HTTP server bound to `127.0.0.1` with: static-files middleware rooted at `<exe-dir>/web/`; `GET /api/v1/status` returning a stub `DaemonStatus`; `GET /api/v1/ws` WebSocket endpoint that pushes one `status` event on connect and a heartbeat every 5 s.
- **`LoopbackBindPolicy : IBindPolicy`** — first and only v1 bind policy; forces `127.0.0.1` and logs a warning on any other config.
- **`NullAuthPolicy : IAuthPolicy`** — no-op pass-through; exercises the auth seam even in v1.
- **Placeholder `/web/index.html`** — minimal page that opens the WebSocket and renders the received status.
- **New project `OpenWSFZ.Web.Tests`** — integration tests via `WebApplicationFactory<Program>` covering FR-002, FR-007, NFR-004.
- **New project `OpenWSFZ.E2E.Tests`** — end-to-end test that sub-processes the published binary, reads stdout for the welcome banner, sends an HTTP request, and upgrades a WebSocket.
- **Remove `OpenWSFZ.AotProbe`** — retired; AOT publish responsibility transfers to `OpenWSFZ.Daemon`, which carries `<PublishAot>true</PublishAot>` for the same purpose.

## Capabilities

### New Capabilities

- `daemon-host`: Daemon lifecycle — process boot, welcome banner emission, loopback-only bind enforcement, signal handling, and clean shutdown. Covers FR-007 and NFR-004.
- `web-server`: Embedded HTTP and WebSocket server — Kestrel configuration, static-file serving, REST status endpoint, and WebSocket hub. Covers FR-002.

### Modified Capabilities

- `build-pipeline`: The AOT-publish prove-out project changes from the stub `OpenWSFZ.AotProbe` to the real `OpenWSFZ.Daemon`. The spec requirement remains (AOT publish is verified on all three OSes per CI), but the project name and purpose must be updated to reflect the production executable.

## Impact

- **New projects:** `src/OpenWSFZ.Daemon/`, `src/OpenWSFZ.Web/`, `tests/OpenWSFZ.Web.Tests/`, `tests/OpenWSFZ.E2E.Tests/`
- **New frontend:** `web/index.html` (and the `web/` top-level directory, per FR-014 / FR-015)
- **Removed:** `src/OpenWSFZ.AotProbe/`
- **New NuGet dependencies:** `Microsoft.Extensions.Hosting`, `Microsoft.AspNetCore.App` (framework reference)
- **Traceability:** after this phase FR-002, FR-007, and NFR-004 will be mapped; no existing mappings are disturbed
- **Licence gate:** Microsoft.Extensions.* and ASP.NET Core are MIT-licensed; gate remains green
