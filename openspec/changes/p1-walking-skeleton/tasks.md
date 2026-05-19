## 1. Scaffolding

- [x] 1.1 Remove `src/OpenWSFZ.AotProbe/` from the repository and from `OpenWSFZ.slnx`.
- [x] 1.2 Create `src/OpenWSFZ.Daemon/OpenWSFZ.Daemon.csproj` — AOT-enabled executable targeting `net10.0` with `<PublishAot>true</PublishAot>`, `<Nullable>enable</Nullable>`, `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>`; add to `OpenWSFZ.slnx`.
- [x] 1.3 Create `src/OpenWSFZ.Web/OpenWSFZ.Web.csproj` — class library targeting `net10.0` with a framework reference to `Microsoft.AspNetCore.App`; add to `OpenWSFZ.slnx`.
- [x] 1.4 Create `tests/OpenWSFZ.Web.Tests/OpenWSFZ.Web.Tests.csproj` — xUnit project referencing `OpenWSFZ.Web`, `Microsoft.AspNetCore.Mvc.Testing`, and `coverlet.collector`; add to `OpenWSFZ.slnx`.
- [x] 1.5 Create `tests/OpenWSFZ.E2E.Tests/OpenWSFZ.E2E.Tests.csproj` — xUnit project with no project references (it drives the published binary as a subprocess); add to `OpenWSFZ.slnx`.
- [x] 1.6 Create `web/index.html` — minimal placeholder page that opens a WebSocket to `/api/v1/ws` and renders the received status object as JSON in a `<pre>` element.
- [x] 1.7 Add required package versions to `Directory.Packages.props`: `Microsoft.AspNetCore.Mvc.Testing` (for integration tests), `System.Net.WebSockets.Client` (for E2E WS tests) — pin to versions consistent with .NET 10.

## 2. Daemon host

- [x] 2.1 Add `Microsoft.Extensions.Hosting` to `OpenWSFZ.Daemon`; write `Program.cs` that builds and runs an `IHost`; signal handling (Ctrl-C / SIGTERM / SIGINT) is provided automatically by the generic host.
- [x] 2.2 Implement `LaunchOptions` record (in `OpenWSFZ.Daemon`) with a `Port` property defaulting to `8080`; wire a `--port <n>` CLI argument using `args` parsing before host construction.
- [x] 2.3 Implement `LoopbackBindPolicy : IBindPolicy` (in `OpenWSFZ.Web`) — overrides any non-loopback address to `127.0.0.1` and logs a `WARN` to the `ILogger` when it does so.
- [x] 2.4 Implement `NullAuthPolicy : IAuthPolicy` (in `OpenWSFZ.Web`) — pass-through no-op; exercises the auth seam without any real logic.
- [x] 2.5 Implement `WelcomeBannerEmitter` (in `OpenWSFZ.Daemon`) as an `IHostedService` that subscribes to `IHostApplicationLifetime.ApplicationStarted` and writes the banner line (containing `http://127.0.0.1:<port>` and an instruction to open it in a browser) to `Console.Out`.
- [x] 2.6 Register `LoopbackBindPolicy`, `NullAuthPolicy`, `WelcomeBannerEmitter`, and the `OpenWSFZ.Web` host in `Program.cs` via the DI container; pass `LaunchOptions` into the Kestrel configuration.

## 3. Web server

- [x] 3.1 Configure Kestrel in `OpenWSFZ.Web` to listen on `127.0.0.1:<port>` using the `LoopbackBindPolicy`; expose the configuration entry-point so `WebApplicationFactory` can use port 0 in tests.
- [x] 3.2 Add `app.UseStaticFiles()` middleware rooted at `<AppContext.BaseDirectory>/web/`; ensure the `web/` directory is copied alongside the executable on publish.
- [x] 3.3 Implement `GET /api/v1/status` minimal-API endpoint returning a `DaemonStatus` record (`{ state: "Running", version: <string> }`) serialised as JSON; verify AOT-safe source-generated JSON serialisation.
- [x] 3.4 Enable `app.UseWebSockets()` and implement `GET /api/v1/ws` — accepts the WebSocket upgrade; returns HTTP 400 to plain HTTP requests.
- [x] 3.5 Implement the WebSocket session loop: send one `status` JSON text-frame on connect; send a `heartbeat` JSON text-frame every 5 s; handle client-initiated close and `OperationCanceledException` from shutdown gracefully.

## 4. Integration tests

- [x] 4.1 Configure `WebApplicationFactory<Program>` in `OpenWSFZ.Web.Tests` to use a real Kestrel listener on an ephemeral port (not `TestServer`) so WebSocket upgrade tests exercise the real HTTP stack.
- [x] 4.2 Write `"FR-002, NFR-004: GET / returns index page on loopback"` — asserts HTTP 200 with an HTML body.
- [x] 4.3 Write `"FR-002: GET /api/v1/status returns DaemonStatus JSON"` — asserts HTTP 200, `Content-Type: application/json`, and `state` field present.
- [x] 4.4 Write `"FR-002: GET /api/v1/ws upgrades and delivers status event"` — asserts HTTP 101 upgrade and receives a JSON text frame containing `status` within 2 s.
- [x] 4.5 Write `"FR-002: heartbeat delivered within 6 seconds of connect"` — connects, receives the initial status event, then asserts a second frame arrives within 6 s.
- [x] 4.6 Write `"FR-002: path traversal attempt is rejected"` — `GET /../some-file` asserts HTTP 404 or 400.
- [x] 4.7 Write `"NFR-004: Kestrel listener address is 127.0.0.1"` — inspects the server's bound addresses and asserts none is non-loopback.

## 5. E2E tests

- [x] 5.1 Implement a `DaemonProcess` helper in `OpenWSFZ.E2E.Tests` that: resolves the published binary path for the current RID, starts the process with stdout and stderr piped, polls stdout until the banner appears (10-second timeout), and kills the process in a `finally` block.
- [x] 5.2 Write `"FR-007: welcome banner appears on stdout within 10 seconds"` — asserts the stdout output contains `http://127.0.0.1:` before the timeout.
- [x] 5.3 Write `"FR-002: HTTP status endpoint reachable after banner"` — issues `GET /api/v1/status` against the port parsed from the banner and asserts HTTP 200.

## 6. CI update

- [x] 6.1 Update the AOT-publish step in `.github/workflows/ci.yml` to target `src/OpenWSFZ.Daemon` instead of `src/OpenWSFZ.AotProbe`.
- [x] 6.2 Add `OpenWSFZ.Web.Tests.dll` and `OpenWSFZ.E2E.Tests.dll` to the TraceabilityCheck `--assembly` list in the G3 step of `ci.yml`.

## 7. Exit gate verification (M2)

- [x] 7.1 Run `dotnet build -c Release` from the repository root — confirm zero errors, zero warnings on all three OSes.
- [x] 7.2 Run `dotnet test -c Release --no-build` — confirm all tests pass (integration + E2E included).
- [x] 7.3 Run TraceabilityCheck locally — confirm FR-002, FR-007, and NFR-004 are mapped and no stale references introduced.
- [x] 7.4 Run LicenseInventoryCheck locally — confirm gate still passes with the new ASP.NET Core / `Microsoft.Extensions.*` dependencies.
- [ ] 7.5 Publish `OpenWSFZ.Daemon` for the current RID with AOT, launch the binary manually, open `http://127.0.0.1:8080/` in a browser, and confirm the placeholder page loads and the WebSocket status event arrives in DevTools.
