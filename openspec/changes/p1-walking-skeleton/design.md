## Context

Phase 0 delivered a working CI pipeline and empty solution structure. No product code exists yet. This design covers the minimal walking skeleton: a daemon that boots, serves a placeholder web page, accepts a WebSocket connection, and shuts down cleanly. The design's primary constraint is AOT compatibility — `OpenWSFZ.Daemon` carries `<PublishAot>true</PublishAot>` from day one, so every library choice must be AOT-safe.

`OpenWSFZ.Abstractions` already defines `IBindPolicy`, `IAuthPolicy`, and `IHostLifecycle`. Phase 1 provides their first concrete implementations.

## Goals / Non-Goals

**Goals:**
- Daemon boots, emits a welcome banner, serves `GET /`, handles `GET /api/v1/status`, upgrades `GET /api/v1/ws` to WebSocket, and exits cleanly on Ctrl-C / SIGTERM.
- Integration tests using `WebApplicationFactory<Program>` validate every HTTP and WS behaviour without real network I/O.
- E2E test sub-processes the AOT-published binary on the host OS to prove the production artifact actually works.
- `OpenWSFZ.AotProbe` is retired; `OpenWSFZ.Daemon` becomes the AOT prove-out project.
- FR-002, FR-007, and NFR-004 are fully mapped in the traceability report.

**Non-Goals:**
- TOML configuration (Phase 2).
- Audio capture or FT8 decoding (Phases 3–4).
- Waterfall (Phase 5).
- Settings page or any persistent state (Phase 2+).

## Decisions

### D1 — Generic host via `Microsoft.Extensions.Hosting`

**Chosen:** `IHost` / `IHostApplicationLifetime` from `Microsoft.Extensions.Hosting`.

**Rationale:** Provides DI container, hosted-service lifetime, and Ctrl-C / SIGTERM / SIGINT handling for free. It is AOT-compatible as of .NET 8 and is the standard .NET host abstraction. `IHostLifecycle` (already in Abstractions) maps cleanly onto `IHostApplicationLifetime`.

**Alternative considered:** Manual `CancellationToken` + `Console.CancelKeyPress`. Rejected because it duplicates infrastructure the runtime already provides and would require reimplementing graceful drain logic.

---

### D2 — `OpenWSFZ.Web` as a separate project from `OpenWSFZ.Daemon`

**Chosen:** Two projects — `OpenWSFZ.Daemon` (composition root, executable) and `OpenWSFZ.Web` (Kestrel config, controllers, WebSocket hub).

**Rationale:** `WebApplicationFactory<Program>` tests reference `OpenWSFZ.Web` in-process without launching the daemon binary. This gives full integration coverage at unit-test speed. The Daemon only wires Web into the host and is tested via the E2E project.

**Alternative considered:** Single-project executable with all web code inside. Rejected because `WebApplicationFactory` requires a project reference (not a subprocess), so splitting is required for in-process integration tests.

---

### D3 — ASP.NET Core minimal-API + built-in WebSocket middleware

**Chosen:** ASP.NET Core minimal API for `GET /api/v1/status` and `app.UseWebSockets()` + a dedicated WebSocket handler for `GET /api/v1/ws`.

**Rationale:** Both are AOT-compatible in .NET 10. No external WebSocket library is needed. Minimal API produces less AOT trimming surface than MVC controllers.

**Alternative considered:** SignalR for the WebSocket layer. Rejected — SignalR has AOT limitations in v1 and is heavier than necessary for a single-channel status stream.

---

### D4 — Port selection for Phase 1

**Chosen:** A `LaunchOptions` record parsed from CLI args (`--port <n>`, default `8080`) passed to Kestrel at startup. `WebApplicationFactory` uses port 0 (ephemeral) automatically via its `TestServer`.

**Rationale:** Phase 2 replaces `--port` with the full TOML config; `LaunchOptions` becomes a thin bridge. Hard-coding 8080 without a CLI override would make local testing awkward.

**Migration to Phase 2:** `LaunchOptions.Port` is superseded by `IConfigSnapshot.Port` once the config system exists; the `--port` flag remains as a runtime override above config (per FR-005 precedence).

---

### D5 — E2E tests via subprocess

**Chosen:** `OpenWSFZ.E2E.Tests` sub-processes the AOT-published binary for the current RID, reads stdout for the banner, issues an HTTP request, and upgrades a WebSocket.

**Rationale:** Proves the production artifact (not just the in-process build) works on the actual host OS. This catches AOT-specific failures that `WebApplicationFactory` cannot surface (e.g., missing IL2026 suppressions, dynamic code paths).

**Alternative considered:** Run the binary inside the integration test suite using `WebApplicationFactory`. Rejected because `WebApplicationFactory` exercises the .NET assembly, not the AOT-compiled native binary.

---

### D6 — Welcome banner on stdout

**Chosen:** `WelcomeBannerEmitter` writes to `Console.Out` (stdout), bound to ASP.NET's `IHostApplicationLifetime.ApplicationStarted`.

**Rationale:** The E2E test reads stdout via `Process.StandardOutput`; using stdout is the simplest testable contract. Structured log output continues on stderr as normal.

**Alternative considered:** stderr only. The implementation plan's E2E test description ("reads stdout via a piped redirect") makes stdout the correct target.

---

### D7 — `LoopbackBindPolicy` as an `IBindPolicy` implementation

**Chosen:** `LoopbackBindPolicy` forces `127.0.0.1` in `KestrelServerOptions.Listen(...)`. Logs a `WARN` if config requests a non-loopback address and overrides it silently (fail-safe, not fail-open).

**Rationale:** NFR-004 is a hard requirement, not a preference. Encoding it in the bind policy rather than in Kestrel configuration directly keeps the enforcement in the right abstraction layer and exercises the `IBindPolicy` seam from day one.

---

### D8 — `OpenWSFZ.AotProbe` retirement

**Chosen:** Delete `src/OpenWSFZ.AotProbe/` and remove it from the solution. `OpenWSFZ.Daemon` inherits its `<PublishAot>true</PublishAot>` flag.

**Rationale:** AotProbe was a placeholder whose only purpose was to prove AOT publish works. That role is now filled by Daemon. Keeping both would double the CI AOT-publish time with no benefit.

## Risks / Trade-offs

- **AOT + ASP.NET Core WebSocket** — WebSocket in ASP.NET Core minimal API is AOT-compatible since .NET 8. The risk is low, but the E2E test on CI is the safety net if a trimming regression surfaces. Mitigation: run E2E on all three OS runners.
- **`WebApplicationFactory` and real WebSocket** — by default `WebApplicationFactory` uses `TestServer`, which does not test the real WebSocket upgrade path over the network. Mitigation: configure the factory to use a real Kestrel listener on ephemeral port for WS tests, or use `HttpClient.GetAsync` with `WebSocketHandshakeException` handling to verify the upgrade is accepted.
- **Port 8080 conflict** — a hardcoded default of 8080 may clash with other services on the developer's machine. Mitigation: the `--port` flag lets anyone override it; this is a P1 temporary concern resolved by P2 config.
- **Subprocess E2E test reliability** — spawning a published binary in CI can be flaky if the binary takes too long to start. Mitigation: poll `GET /api/v1/status` with a 10-second timeout before sending assertions; kill the process in a `finally` block.

## Open Questions

- **Heartbeat interval** — the implementation plan specifies 5 s. This is hardcoded as a constant in P1 (no config). Confirm this is acceptable before P1 is closed.
- **`DaemonStatus` shape** — the status object returned by `GET /api/v1/status` and pushed on WebSocket connect is a stub in P1. Agree on the minimal field set (e.g. `version`, `uptime`, `state: "Running"`) so the P2 and P3 shape changes are incremental rather than breaking.
