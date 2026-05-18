# OpenWSFZ &mdash; Technical Specification

**Version:** 1.0
**Date:** 2026-05-18
**Status:** Draft &mdash; pending Product Owner approval
**Author:** ARCHITECT role (AI-assisted)
**Source of requirements:** [`REQUIREMENTS.md`](./REQUIREMENTS.md) v1.1
**Scope:** OpenWSFZ v1 (FT8 receive-only, loopback-only, single operator, source-only distribution) with explicit extension seams for the v2+ deferred capabilities.

> **Reading order for someone new to the project**
> 1. [`REQUIREMENTS.md`](./REQUIREMENTS.md) &mdash; what we're building and why.
> 2. This document &mdash; how it is structured and what every component does.
> 3. `IMPLEMENTATION_PLAN.md` (separate deliverable) &mdash; the phased path to get there.

---

## 1. System Overview

OpenWSFZ v1 is a single native executable that performs three roles concurrently in one process:

1. **Audio capture &amp; decode pipeline.** Captures a real-time PCM stream from a USB audio device chosen by the operator, framed and decimated to FT8's canonical 12 kHz mono input, decoded once per 15-second FT8 cycle, and surfaced as discrete decoded-message events. A live spectrogram (waterfall) is produced from the same stream.
2. **Embedded web server.** Serves the operator's UI as a web page from `http://127.0.0.1:<port>`, with HTTP for static assets and REST, and WebSocket for live events (decodes, waterfall frames, status). The web stack is ASP.NET Core (Kestrel).
3. **Configuration manager.** Reads a TOML configuration file on startup (default path or CLI/env override), supplies the running daemon with operator preferences, and writes back when the operator clicks **Save** on the Settings page.

### 1.1 Architecture diagram

```
+-------------------------------------------------------------+
| Browser (same machine -- loopback only)                     |
| vanilla HTML / CSS / JS, no bundler, no framework           |
+--------------+--------------------------------+-------------+
               | HTTP/1.1                       | WebSocket
               | (static assets, REST)          | (live events)
               v                                v
+-------------------------------------------------------------+
| OpenWSFZ.Web         ASP.NET Core: Kestrel . WS hub         |
+-------------------------------------------------------------+
| OpenWSFZ.Daemon      host . lifecycle . banner . DI root    |
+----------------------+--------------------------------------+
| OpenWSFZ.Audio       | OpenWSFZ.Decoding                    |
|  IAudioSource        |  IModeDecoder  --->  FT8 plugin      |
|   +- PortAudio       |  IModeRegistry        P/Invoke       |
|      (P/Invoke)      |                       ft8_lib        |
|                      | OpenWSFZ.Waterfall                   |
+----------+-----------+-----------------+--------------------+
           |                             |
           v                             v
   Host OS audio                   Native libs (vendored)
   WASAPI / ALSA / CoreAudio       ft8_lib   (MIT)
   via PortAudio                   PortAudio (MIT-style)
```

### 1.2 Process model

* One process, single executable. No services, no IPC, no database.
* Three principal threads of execution:
  * **Audio capture thread.** Owned by PortAudio's callback. Pushes PCM frames into a lock-free ring buffer.
  * **Decoder worker thread.** Wakes on each 15-second FT8 cycle boundary, drains a full cycle's worth of PCM, invokes the active `IModeDecoder`, and publishes results to the event bus.
  * **ASP.NET Core thread pool.** Serves HTTP, hosts WebSocket connections, publishes live events to connected clients.
* A **waterfall worker** runs on a low-priority timer thread, producing one frame every 100 ms from a tap on the same PCM stream that feeds the decoder.

### 1.3 Threading and back-pressure

* The audio ring buffer is sized for &geq; 30 s of PCM (two FT8 cycles) so a momentary decoder stall never drops audio.
* If a decoder run exceeds its cycle (it must not under NFR-003 &mdash; see &sect;11), the decoder thread logs a `warn` event and drops the cycle. The audio thread is unaffected.
* WebSocket clients that fall behind (slow renderers, dev tools open) have a per-client bounded queue. On overflow the oldest waterfall frames are dropped first, decoded-message events are never dropped.

---

## 2. Architectural Principles

These are the rules that govern every detail design decision below.

1. **One process, many subsystems.** v1 does not split into services. Subsystem boundaries are enforced at the assembly / interface level, not the OS-process level.
2. **Subsystem isolation via interfaces.** Each subsystem exposes a public interface in `OpenWSFZ.Abstractions`. Consumers depend only on the abstraction, never on the implementation. This is what makes mocking trivial, makes the v2 features bolt on, and makes the strict UI visibility rule (FR-016) enforceable.
3. **The decoder is plugin-shaped from day one (NFR-008).** FT8 is the first `IModeDecoder` implementation. FT4 and others arrive later as siblings.
4. **The deployment lifecycle, bind policy, and auth policy are also abstractions (NFR-009, NFR-010).** v1 ships trivial implementations (terminal foreground, loopback only, no-op auth). v2 swaps them without touching subsystem code.
5. **No persisted state beyond the configuration file.** Decoded messages are session-only (FR-021 / Data Requirements). Recovery from any failure is "restart the process."
6. **The UI is a strict consumer.** No business logic in the browser. The frontend renders state pushed over WebSocket and issues intents over HTTP/WS. This keeps the architecture honest for future deployments where the UI may not be co-located with the daemon (web-service deployment, v2+).
7. **No silent fallbacks.** Misconfiguration, missing audio devices, or port conflicts produce a clear stderr message and a non-zero exit. We never paper over operator errors.
8. **License hygiene is gated in CI.** Every transitive dependency is enumerated and verified MIT-redistributable on every build. A non-compatible licence fails the build.

---

## 3. Component Breakdown

Each component is one .NET project / assembly. Names use the `OpenWSFZ.*` namespace.

### 3.1 `OpenWSFZ.Abstractions`

Pure interface library. No implementation, no runtime dependencies beyond BCL.

Contains:

* `IAudioSource`, `IAudioDeviceEnumerator`, `AudioDevice`, `AudioFrame`
* `IModeDecoder`, `IModeRegistry`, `DecodeResult`, `Ft8DecodeMessage`, `WaterfallFrame`
* `IBindPolicy`, `IAuthPolicy`, `IHostLifecycle` (extension seams)
* `IConfigStore`, `IConfigSnapshot`
* `IClock` (testability)

Every other project depends on this one. This one depends on nothing in the solution.

### 3.2 `OpenWSFZ.Daemon`

The executable. Contains `Program.cs`, the composition root, the welcome banner emitter, signal handling (Ctrl-C / SIGTERM / SIGINT), and the wiring of all subsystems via Microsoft.Extensions.DependencyInjection.

Responsibilities:

* Parse CLI args and environment variables (config path override per FR-005).
* Bootstrap the default config if none exists (FR-006).
* Compose the audio pipeline, decoder registry, waterfall pipeline, and ASP.NET host.
* Emit the welcome banner (FR-007) once the HTTP listener is bound and the WS hub is ready.
* Wait for shutdown signal, then drain workers cleanly.

This is the only project that produces an executable.

### 3.3 `OpenWSFZ.Configuration`

TOML schema, load/save, validation. See &sect;4 for the schema.

* Implements `IConfigStore` and `IConfigSnapshot`.
* `Tomlyn` is the parser.
* On parse failure, throws a typed `ConfigInvalidException` with line/column info. The daemon propagates this to stderr and exits non-zero (no silent fallback).
* Save operation is atomic (write to `<path>.tmp`, fsync, rename) to survive a crash mid-write.

### 3.4 `OpenWSFZ.Audio`

Cross-platform audio capture.

* Implements `IAudioSource` (the per-session capture handle) and `IAudioDeviceEnumerator` (the list endpoint that powers Settings).
* `PortAudioSource` uses `PortAudioSharp` (a thin P/Invoke binding to the vendored PortAudio native library).
* Produces frames as `Span<short>` blocks at the source rate, downsampled to **12 kHz mono signed-16-bit** by an internal resampler. 12 kHz is FT8's canonical input rate; staying at this rate lets `ft8_lib` consume the buffer directly with no extra copy.
* Maintains a lock-free ring buffer (`System.Threading.Channels` or a hand-rolled SPMC buffer) sized for 30 s of audio.
* Surfaces health state (`Capturing`, `Lost`, `Paused`) via an event consumed by `OpenWSFZ.Web` for status push.

### 3.5 `OpenWSFZ.Decoding`

The decoder abstraction layer.

* `IModeDecoder.Decode(ReadOnlySpan<short> pcm12kMono, DateTime cycleUtc) -> IReadOnlyList<DecodeResult>`
* `IModeRegistry` lists the active mode implementations. In v1 the registry returns exactly one entry: the FT8 decoder.
* `DecodeResult` is mode-agnostic; `Ft8DecodeMessage` is the FT8-specific subtype with `audio_offset_hz`, `snr_db`, `time_offset_s`, `decoded_text`, `confidence`.

### 3.6 `OpenWSFZ.Decoding.Ft8`

The FT8 plugin.

* `Ft8Decoder : IModeDecoder`
* P/Invoke layer for `ft8_lib`. The C ABI surface we depend on is small (decoder entry point, result struct marshalling). The wrapper allocates from `ArrayPool<byte>` to keep GC pressure low.
* Native binary is built once per OS by the CMake helper under `/native/build.cmake` and is copied next to the .NET executable during `dotnet publish`.
* **Clean-room provenance is preserved**: `ft8_lib` is MIT and is itself a clean-room implementation outside the GPL-3.0 WSJT-X tree. The dependency is declared in the licence inventory and gated by the CI licence check.

### 3.7 `OpenWSFZ.Waterfall`

Spectrogram producer.

* Subscribes to the audio ring buffer at a sibling tap (does not steal frames from the decoder).
* Computes a sliding-window FFT (default 2048-point, Hann window, 50% overlap) and converts magnitudes to dB.
* Emits `WaterfallFrame` events at a configurable cadence (default 10 Hz).
* SIMD-accelerated via `System.Numerics.Vector<T>` where the FFT library supports it.

### 3.8 `OpenWSFZ.Web`

The ASP.NET Core host.

* Configures Kestrel with the bind address from `IBindPolicy` (which v1 forces to `127.0.0.1`).
* Serves static files from a configurable web root (default: `./web/` relative to the executable; see &sect;9 on layout).
* Exposes the REST endpoints in &sect;5.1.
* Exposes a single WebSocket endpoint and dispatches subscribed clients to per-client send queues. See &sect;5.2 for the message envelope.
* Sets the CSP header on every HTML response (see &sect;8.4).

### 3.9 Frontend (top-level `/web`)

Per FR-014 and FR-015 the frontend lives in its **own top-level folder**, not embedded as resources, and every file is plain on disk.

Layout:

```
/web
  index.html               main page (waterfall + decoded messages list + status)
  settings.html            settings page (audio device, save action)
  /css/
    variables.css          theme tokens (CSS custom properties)
    theme-dark.css         the v1 default theme (FR-012); imports variables.css
    layout.css             page layout rules
  /js/
    main.js                index.html bootstrap (ES module)
    settings.js            settings.html bootstrap (ES module)
    websocket.js           shared WS client (ES module)
    waterfall.js           canvas renderer (ES module)
    api.js                 REST client wrappers (ES module)
```

* Pages link CSS files with `<link rel="stylesheet">` and JS files with `<script type="module" src="...">`. No bundler is involved at any stage (NFR-001 implicit via the Node prohibition).
* Theming (FR-013 / NFR-Q9): edit `variables.css` for skin-only changes (recommended for most operators), or edit the layout/theme files directly for deeper changes.

---

## 4. Data Models

### 4.1 Configuration file (TOML)

Default location:

* **Windows:** `%APPDATA%\OpenWSFZ\openwsfz.toml`
* **Linux:** `$XDG_CONFIG_HOME/openwsfz/openwsfz.toml` (fallback `~/.config/openwsfz/openwsfz.toml`)
* **macOS:** `~/Library/Application Support/OpenWSFZ/openwsfz.toml`

Override: `--config <path>` CLI flag, or `OPENWSFZ_CONFIG=<path>` env var. CLI wins over env.

Default content shipped with the application (FR-006):

```toml
# OpenWSFZ configuration file.
# Edit while the application is stopped, or use the Settings page.

[audio]
# Opaque device identifier returned by /api/v1/audio/devices.
# Leave empty on first run; pick a device from the Settings page.
device_id = ""

[web]
# v1 is loopback-only. Changing this will be silently corrected to 127.0.0.1
# until LAN/auth support arrives in v2.
bind_address = "127.0.0.1"
port = 8073

[logging]
# trace | debug | info | warn | error
level = "info"
```

The default port **8073** is chosen to be memorable (FT8's two characters in ASCII octal are 70, 56 -- no, simpler: it is just an unused-enough port likely to avoid clashes with common dev servers on 8080, 3000, 5000, 8000).

### 4.2 In-memory entities

```csharp
public record AudioDevice(
    string Id,                   // opaque, stable across enumerations on same host
    string Name,                 // human-readable
    int Channels,
    int DefaultSampleRateHz,
    string HostApi);             // "WASAPI", "ALSA", "CoreAudio", ...

public record Ft8DecodeMessage(
    DateTime CycleUtc,           // start of the 15s cycle, UTC
    int AudioOffsetHz,           // e.g. +1234 Hz, displayed per FR-009
    double SnrDb,                // signal-to-noise in dB
    double TimeOffsetSec,        // dt vs. cycle start
    string DecodedText,          // e.g. "CQ K1JT FN42"
    double Confidence);          // 0..1, decoder-internal

public record WaterfallFrame(
    DateTime FrameUtc,
    float BinHzStep,             // Hz per FFT bin
    float MinDb,
    float MaxDb,
    Memory<float> BinDb);        // length = FFT size / 2

public record DaemonStatus(
    AudioState AudioState,       // Capturing | Lost | Paused | NotConfigured
    DecoderState DecoderState,   // Idle | Decoding
    WebState WebState,           // Listening
    TimeSpan Uptime);
```

---

## 5. API Design

All API responses are JSON unless otherwise noted. Timestamps are ISO-8601 UTC.

### 5.1 HTTP endpoints

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `/` | Serves `index.html` | Cache: `no-cache` |
| GET | `/settings` | Serves `settings.html` | Cache: `no-cache` |
| GET | `/css/*`, `/js/*` | Static assets | Cache: `max-age=0, must-revalidate` (operators edit on disk) |
| GET | `/api/v1/status` | Returns `DaemonStatus` | |
| GET | `/api/v1/audio/devices` | Returns `AudioDevice[]` | Triggered when Settings opens |
| GET | `/api/v1/config` | Returns the current in-memory config as JSON | Mirrors the TOML schema |
| PUT | `/api/v1/config` | Writes the supplied config to disk and rebinds audio if `audio.device_id` changed | Atomic write; validates before persist; returns 400 with line/column on schema violation |
| GET | `/api/v1/ws` | Upgrades to WebSocket | See &sect;5.2 |

### 5.2 WebSocket protocol

Envelope (server &rarr; client and client &rarr; server):

```json
{ "type": "<message-type>", "payload": { ... } }
```

#### Server &rarr; client message types

| Type | Payload shape | Cadence |
|---|---|---|
| `status` | `DaemonStatus` | On change, plus every 5 s heartbeat |
| `decode` | `Ft8DecodeMessage` | One per decoded message |
| `waterfall` | Binary frame (see below) | Default 10 Hz |
| `log` | `{ level, message, timestamp_utc }` | Per emitted log line at &geq; configured level |

**Waterfall binary frame format** (to avoid JSON overhead at 10 Hz, all values little-endian):

```
byte  0    : message-type tag (0x01 = waterfall)
bytes 1-8  : frame_utc_unix_ms (uint64)
bytes 9-12 : bin_count        (uint32)
bytes 13-16: bin_hz_step      (float32)
bytes 17-20: min_db           (float32)
bytes 21-24: max_db           (float32)
bytes 25-..: bin_db[]         (float32, bin_count entries)
```

The browser sends this on the WebSocket as a binary frame; all other messages travel as JSON text frames.

#### Client &rarr; server message types (v1, minimal)

| Type | Payload | Effect |
|---|---|---|
| `ping` | `{}` | Server responds with `pong`. Keepalive. |

All meaningful actions (save config, list devices) are HTTP, not WS. This keeps the WS channel for live data flow only.

---

## 6. Authentication and Authorisation

### 6.1 v1: no authentication, loopback only

* Kestrel is configured by the composition root to listen on `127.0.0.1:<port>` and nowhere else.
* Even if a future operator hand-edits `web.bind_address` in the TOML to a non-loopback value, v1's `LoopbackBindPolicy` ignores the config and rebinds to `127.0.0.1`, with a `warn` log line. This prevents accidental exposure during v1.
* No cookies, no sessions, no CSRF tokens, no auth tokens. Any local process running as the operator can connect; this is documented as the v1 threat model in &sect;8.

### 6.2 v2+ seam (sketch, not designed in detail)

* `IBindPolicy` decides the listener addresses. v2 implementations: `LanBindPolicy`, `AnyBindPolicy`. Selected from config.
* `IAuthPolicy` is invoked on every incoming HTTP request and WebSocket upgrade. v2 implementations: `LocalTokenAuthPolicy` (operator-issued token in a header / query string), and optionally `OidcAuthPolicy` for a richer deployment. v1 ships `NullAuthPolicy` which is exercised by tests so the seam is real, not nominal.
* TLS is Kestrel's native feature; enabling it in v2 is a configuration matter, not a code matter.

---

## 7. External Integrations and Dependencies

### 7.1 Dependency inventory

| Dependency | Kind | Licence | Source / pin |
|---|---|---|---|
| .NET 10 SDK + runtime | Toolchain + runtime | MIT | `global.json` pins SDK feature band |
| ASP.NET Core 10 | NuGet (transitive via .NET 10) | MIT | Pinned with SDK |
| `System.IO.Ports` (future, v2 rig CAT) | NuGet | MIT | Not in v1; mentioned for inventory continuity |
| Tomlyn | NuGet | BSD-2-Clause | Exact version pinned in csproj |
| xUnit / xUnit.runner.visualstudio | NuGet | Apache-2.0 / MIT | Pinned |
| Coverlet.collector | NuGet | MIT | Pinned |
| ReportGenerator | NuGet | Apache-2.0 | Pinned |
| Microsoft.AspNetCore.Mvc.Testing (WebApplicationFactory) | NuGet | MIT | Pinned |
| PortAudio | Native, git submodule under `/native/portaudio` | MIT-style (PortAudio licence) | Submodule pinned at a specific tag |
| ft8_lib | Native, git submodule under `/native/ft8_lib` | MIT | Submodule pinned at a specific tag |

A CI step (see &sect;9.4) walks the full transitive graph and fails the build if any licence is not MIT-redistributable.

### 7.2 Host OS integrations

| Integration | API surface used |
|---|---|
| Audio capture | PortAudio host APIs (WASAPI on Windows, ALSA on Linux, CoreAudio on macOS) |
| Filesystem | Config read/write; serving the frontend folder read-only |
| Process signals | Ctrl-C / SIGINT / SIGTERM via .NET's `Console.CancelKeyPress` and `IHostApplicationLifetime` |
| Wall clock | .NET `DateTime.UtcNow` via `IClock`; FT8 cycle alignment depends on host clock accuracy &mdash; not synchronised by the daemon itself |

### 7.3 Browser integration

* HTTP/1.1 and WebSocket only. No HTTP/2, no HTTP/3, no Server-Sent Events.
* No third-party origins. CSP forbids cross-origin connections.
* Targets evergreen browsers (Chrome / Edge / Firefox / Safari on their currently-supported versions). No IE / legacy Edge.

---

## 8. Error Handling, Resilience, and Security

### 8.1 Failure modes and responses

| Failure | Detection | Response |
|---|---|---|
| Configured audio device not present at startup | Enumerator returns no match | Daemon starts in `AudioState.NotConfigured`; UI shows the state; Settings still works |
| Audio device removed mid-session | PortAudio stream-stopped callback | Transition to `AudioState.Lost`; emit status; operator picks a new device |
| Decoder exception on a cycle | Try/catch in decoder worker | Log `warn`, drop the cycle, continue with next |
| Decoder exceeds 15 s on a cycle (NFR-003 breach) | Stopwatch in decoder worker | Log `error`, drop the cycle, increment a counter exposed in status; if breaches exceed N consecutive cycles, set `DecoderState.Stalled` |
| Config file parse error at startup | Tomlyn throws | Print clear stderr with line / column; exit code 2 |
| Config save validation error | Schema validator | HTTP 400 with `{ "errors": [...] }`; file on disk untouched |
| Port already in use at startup | Kestrel bind exception | Print clear stderr; exit code 3 |
| WebSocket client disconnect | Kestrel notification | Drop the client's send queue; daemon state unaffected |
| Slow WebSocket client | Send-queue depth threshold | Drop oldest waterfall frames first; never drop decode events |

### 8.2 Logging

* Structured logging via `Microsoft.Extensions.Logging`, console provider only in v1.
* Log lines are plain text optimised for terminal readability: `2026-05-18T19:42:13Z  info  audio    captured device "..."`.
* Welcome banner (FR-007) is emitted at `info` level and also written to stdout as a separate plain line for grep-ability.

### 8.3 Security model (v1)

In-scope threats: accidental exposure on the network; static-file path traversal; corrupt config.
Out-of-scope threats (v1, accepted): malicious local processes running as the operator.

| Control | v1 implementation |
|---|---|
| Network exposure | Hard-pinned loopback bind, regardless of config |
| Path traversal in static-file serving | ASP.NET's `StaticFileMiddleware` with a single explicit `FileProvider` rooted at the configured web root; default behaviour rejects `..` traversal |
| Cross-origin requests | CSP `default-src 'self'; connect-src 'self' ws://127.0.0.1:<port>;` on every served HTML page |
| Secrets in logs | No secrets exist in v1; logger has no special redaction |
| Config tampering | The config file is read on startup and on explicit save only; no live-reload in v1, so a tampered file affects only the next startup |
| Dependency supply chain | CI licence check + version pinning + submodule pinning by commit SHA |

### 8.4 Resilience targets

* No crash for the duration of a normal operating session (NFR-015). "Normal" defined here as **&geq; 8 hours of continuous capture without process restart**. Acceptance: a 9-hour integration run in CI on Linux (nightly) drives synthetic audio through the full pipeline and asserts process health throughout.
* No unbounded memory growth. The pipeline allocates from pools and uses ring buffers; an integration test measures GC heap size over a 30-minute run and fails the build on a growth slope above a small threshold.

---

## 9. Repository Layout

```
/                              Repository root
  README.md
  LICENSE                      MIT
  REQUIREMENTS.md
  TECHNICAL_SPEC.md            (this file)
  IMPLEMENTATION_PLAN.md       (separate deliverable)
  global.json                  Pins the .NET SDK feature band
  OpenWSFZ.sln                 Solution file
  /src
    /OpenWSFZ.Abstractions
    /OpenWSFZ.Daemon           (executable; AOT-published)
    /OpenWSFZ.Audio
    /OpenWSFZ.Decoding
    /OpenWSFZ.Decoding.Ft8
    /OpenWSFZ.Configuration
    /OpenWSFZ.Waterfall
    /OpenWSFZ.Web
  /tests
    /OpenWSFZ.Daemon.Tests
    /OpenWSFZ.Audio.Tests
    /OpenWSFZ.Decoding.Ft8.Tests        (WAV fixture corpus lives here)
    /OpenWSFZ.Configuration.Tests
    /OpenWSFZ.Web.Tests                 (WebApplicationFactory-based integration)
    /OpenWSFZ.E2E.Tests                 (boots the built binary on each OS)
  /web                                  (frontend, FR-014 top-level location)
    index.html
    settings.html
    /css/
    /js/
  /native
    /ft8_lib                            (git submodule, MIT)
    /portaudio                          (git submodule, MIT-style)
    build.cmake                         (cross-platform native build helper)
  /openspec                             (proposals, specs, archived changes)
  /prompts                              (role prompts -- ANALYST, ARCHITECT, ...)
  /.github/workflows/
    ci.yml                              (matrix build + test + coverage + licence)
    release.yml                         (tagged release: AOT publish per OS)
```

### 9.1 Why a single solution

A single `OpenWSFZ.sln` lets `dotnet build` / `dotnet test` operate over the whole codebase from one command, and lets IDEs offer cross-project refactoring. The cost is negligible at this size.

### 9.2 Why the native libs are submodules

* Pins to a specific upstream commit, audited at PR time.
* Reproducible builds: no network fetch during a regular build other than the initial clone.
* Clear licence-attribution path: the submodule contents are unmodified upstream code, which makes the MIT clean-room story easy to evidence in the licence inventory.

### 9.3 Build flow

1. Native: `cmake -S /native -B build/native -DCMAKE_BUILD_TYPE=Release` then `cmake --build build/native`. Produces `libft8.{dll,so,dylib}` and `libportaudio.{dll,so,dylib}` and copies them into `/src/OpenWSFZ.Daemon/runtimes/<rid>/native/`.
2. .NET: `dotnet build` then `dotnet test`. Native binaries are picked up via the standard .NET runtime-folder mechanism.
3. Publish: `dotnet publish -c Release -r <rid> --self-contained --p:PublishAot=true` produces the single-file AOT binary per OS.

### 9.4 CI workflow (GitHub Actions, `.github/workflows/ci.yml`)

* Matrix: `{ windows-latest, ubuntu-latest, macos-latest }`.
* Per OS: checkout (with submodules); cache .NET and CMake; build native; build .NET; run all tests; collect Coverlet coverage; upload coverage as an artifact.
* Single OS (Linux) additionally runs:
  * The **licence inventory check** (walks every NuGet reference and every submodule, asserts MIT-redistributable).
  * The **traceability check** (every requirement ID FR-### / NFR-### appears in at least one test name; see &sect;10).
* Branch protection on `main` requires green CI on all three OSes plus the Linux-only checks (NFR-007).

---

## 10. Testing Approach (overview)

A full Testing Strategy document is **Deliverable 4** and will sit alongside this spec. This section establishes the high-level approach the spec depends on.

* **Unit tests** &mdash; per-class, no I/O, fast. xUnit.
* **Decoder fixture tests** &mdash; the linchpin of FT8 correctness. A corpus of WAV files with known expected decode payloads (sourced from the WSJT-X reference corpus and `ft8_lib`'s own test suite, both freely available) is replayed through `Ft8Decoder`; tests assert exact decode payloads.
* **Integration tests** &mdash; `WebApplicationFactory<Program>` boots the daemon in-process, with mock `IAudioSource` injecting WAV fixtures; tests exercise the full HTTP/WS surface.
* **End-to-end tests** &mdash; CI launches the published binary on each OS, opens the HTTP root, opens the WebSocket, asserts the welcome banner and a known decode against a fixture.
* **Traceability** &mdash; **every requirement ID FR-### / NFR-### maps to at least one test by name**. A CI gate enforces this. This is what "meaningful coverage" means in this project (NFR-006); coverage percentage is informational only.
* **Strict UI visibility** (FR-016) &mdash; an integration test parses the served HTML, enumerates every interactive control, and asserts each one resolves to a wired handler. A "coming soon" or no-op control fails the build.

---

## 11. Performance Targets

These are the v1 concrete budgets for NFR-002 / NFR-003 / NFR-015. They are stated as targets and verified by a small performance test suite that runs in CI on Linux only (avoiding macOS / Windows GitHub-runner variability).

| Metric | Target |
|---|---|
| Decode latency (cycle close &rarr; UI display) | &leq; 1500 ms p95 |
| FT8 decode CPU time per 15 s cycle | &leq; 1500 ms p95 (NFR-003 hard deadline is 15000 ms; this leaves &gt;90% headroom) |
| Waterfall frame rate | 10 Hz, jitter &leq; 20 ms |
| WS event end-to-end latency (loopback) | &leq; 50 ms p95 |
| Daemon idle CPU (capturing, no decodes) | &leq; 2% on a mid-range modern desktop |
| Daemon RSS at steady state | &leq; 200 MB |
| Cold start to "listening" banner | &leq; 1500 ms |
| Test suite full run | &leq; 60 s on each CI runner |
| Continuous uptime without crash / unbounded growth | &geq; 8 h (nightly integration run on Linux) |

### How they're achieved

* AOT-compiled binary &mdash; no JIT warm-up, smaller working set.
* Dedicated threads for audio capture and decoder; ASP.NET's thread pool for web.
* Lock-free ring buffer between audio and consumers; no inter-thread allocation in the hot path.
* `Span<short>` / `Memory<float>` and `ArrayPool<byte>` for decoder/waterfall buffers.
* Waterfall FFT uses SIMD via `System.Numerics.Vector<T>`.
* WebSocket waterfall frames are binary-encoded (see &sect;5.2) so 10 Hz costs &lt; 100 KB/s on loopback.

---

## 12. Extension Seams (for v2+, sketched only)

Per the agreed scope (v1 deep, future sketched), this section names the seams that v1 must put in place &mdash; not the v2 designs.

| Capability (deferred) | NFR | Seam(s) in v1 | What v2 plugs in |
|---|---|---|---|
| Additional modes (FT4, JT9, WSPR, ...) | NFR-008 | `IModeDecoder`, `IModeRegistry`, mode-tagged `DecodeResult` | Sibling assemblies: `OpenWSFZ.Decoding.Ft4`, `.Wspr`, ... |
| Windows-service deployment | NFR-009 | `IHostLifecycle` + CLI `--service` flag handling in `Program.cs` (in v1 only `TerminalLifecycle` is registered) | `WindowsServiceLifecycle` implementation registered under same interface |
| LAN / remote operation | NFR-010 | `IBindPolicy` (v1 forces loopback), `IAuthPolicy` (v1 no-op but exercised) | `LanBindPolicy` + `TokenAuthPolicy` + Kestrel TLS config |
| Transmit (TX) | new in v2 | Audio output is *not* in v1 at all; the seam is the absence of opinions: `IAudioSource` is purely a capture abstraction, and `IModeDecoder` is decode-only. The v2 TX path is a separate `IAudioSink` + `IModeModulator` pair. | New abstractions, new subsystems &mdash; no v1 code change |
| Rig control (CAT) | new in v2 | Not designed in v1. v1 leaves `IRigControl`-shaped space in `OpenWSFZ.Abstractions` empty. | `OpenWSFZ.Rig` subsystem added later |
| Decode persistence / logbook (ADIF, Cabrillo) | new in v2 | Not designed in v1. v1 emits decodes as events; persistence is a downstream subscriber added later. | New `OpenWSFZ.Logbook` subsystem subscribes to the same decode event stream |

The **principle** behind these seams: anything v2 might add is structured as a *new* subsystem implementing an interface that already exists (or, where v1 has no opinion yet, slotting cleanly under a *new* interface that does not require touching existing subsystems). No v1 implementation file should need to be edited to enable a v2 feature; v2 work should be **additive**.

---

## 13. Tooling and Workflow

### 13.1 Serena MCP server (REQUIREMENTS &sect;8 Q15)

The Serena MCP server is wired into Claude Code for the **DEVELOPER** role. Recommended integration point: **at the start of Phase 1 implementation**, alongside the DEVELOPER prompt under `/prompts`. The architect's view is that Serena's symbol-aware tools materially help the developer agent navigate a multi-project .NET solution, and bringing it in before the first line of code is written avoids re-learning the codebase later. Implementation Plan Phase 1 includes this as a setup step.

### 13.2 OpenSpec workflow

The four-role workflow (ANALYST / ARCHITECT / DEVELOPER / QA) communicates through written artifacts:

* `REQUIREMENTS.md` &mdash; analyst's output.
* `TECHNICAL_SPEC.md` and `IMPLEMENTATION_PLAN.md` &mdash; architect's output.
* OpenSpec change proposals under `/openspec/changes/<change-id>/` &mdash; per-feature design + tasks, written by the architect (or analyst), implemented by the developer, reviewed by QA.
* Branches: `feature/<change-id>` off `main`. `main` only takes reviewed and tested merges (NFR-007).

---

## 14. Items Resolved in the Implementation Plan, Not Here

* Exact phasing and milestone definitions.
* Per-phase task lists.
* Risk register.
* CI configuration file content.
* Initial OpenSpec change proposal that bootstraps the v1 build (replacing the now-deleted `add-project-skeleton` proposal).

These belong in `IMPLEMENTATION_PLAN.md`, which is the next deliverable.

---

## 15. Open Questions Carried Forward

Items from `REQUIREMENTS.md` &sect;8 that this spec does *not* resolve and that will surface in the Implementation Plan or downstream OpenSpec proposals:

| # | Item | Where it will be addressed |
|---|---|---|
| 1 | DSP correctness parity | Verified by the WAV-fixture corpus in `OpenWSFZ.Decoding.Ft8.Tests`. Implementation plan includes corpus sourcing as a Phase 1 task. |
| 5 | Upgrade story for user-edited frontend files | Deferred to v2 release-engineering work; not relevant at v1 source-only distribution. |
| 6 | Main-page composition beyond waterfall + decode list | Resolved in a Phase 2 OpenSpec proposal once the v1 daemon is running. |
| 7 | "Meaningful coverage" rubric for QA | Resolved by Deliverable 4 (Testing Strategy). |
| 8 | UX competitive bar (NFR-013) | Acceptance criteria deferred to pre-public-release milestone. v1 does not gate on this. |
| 9 | CSS theming granularity | Resolved here in &sect;3.9: variables.css for skin-only, full files for deeper changes. |
| 12 | GitHub repo posture | Operational, owned by the Product Owner; not architectural. |
| 14 | Performance numeric targets | Resolved here in &sect;11. |
| 15 | Serena integration point | Resolved here in &sect;13.1. |

---

**End of TECHNICAL_SPEC.md v1.0 (draft).**
