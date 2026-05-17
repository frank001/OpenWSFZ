## Why

OpenWSFZ has nothing but a `LICENSE` and `README` on `main`. Before any
protocol or DSP work can begin, the project needs an end-to-end skeleton that
proves the chosen architecture works: a single C++ daemon that builds and
runs cross-platform, serves a browser-based UI, and exchanges live messages
over WebSocket. Everything else &mdash; audio, FFT, decoders, rig control &mdash;
plugs into this spine. Landing this slice first de-risks all subsequent work
and gives reviewers something runnable to evaluate.

## What Changes

- Introduce a CMake-driven C++17 project. Drogon (MIT) is vendored via
  `FetchContent` for HTTP and WebSocket. No Qt, no Fortran, no Node at
  build time.
- Add `CMakePresets.json` with presets for `windows-msvc`, `linux-gcc`, and
  `macos-clang`, giving a uniform build invocation across platforms.
- Add a daemon entry point (`src/main.cpp`) that:
  - Listens on `127.0.0.1:8080` by default.
  - Serves the static UI from `web/` at the root.
  - Exposes `GET /api/health` returning daemon status JSON.
  - Exposes `WS /ws` as an echo + heartbeat endpoint, with a documented
    JSON envelope (`{type, id, ts, payload}`).
- Add a vanilla-JS web UI (`web/index.html`, `web/app.js`, `web/style.css`)
  that connects to `/ws`, displays connection status, sends a heartbeat,
  and reserves placeholder panels for the future spectrogram, decoded
  messages list, and transmit controls. Per the UI-visibility rule, no
  control surfaces are wired up that don't yet have backend support.
- Add `.github/workflows/build.yml` with a matrix CI build on
  `windows-latest`, `ubuntu-latest`, and `macos-latest`. No tests yet.
- Add `docs/ARCHITECTURE.md` describing the daemon/web split, the message
  envelope, and how future capabilities slot in.

## Capabilities

### New Capabilities

- `daemon-core`: Process lifecycle, configuration loading, structured
  logging, signal handling, and the HTTP+WebSocket transport that hosts
  all future control surfaces.
- `web-control-api`: The wire contract between the daemon and any
  browser UI &mdash; static-asset serving, the `/api/health` shape, the
  `/ws` JSON envelope, and the message-type registry future capabilities
  extend.

### Modified Capabilities

_None &mdash; no specs exist yet._

## Impact

- **New top-level directories**: `src/`, `include/`, `web/`, `cmake/`,
  `docs/`, `.github/workflows/`.
- **New build-time dependency**: Drogon (MIT) fetched at configure time
  via CMake `FetchContent`. Transitively pulls `trantor` (also MIT) and
  optionally OpenSSL/zlib (system-provided on Linux/macOS; bundled or
  optional on Windows for this first slice &mdash; WS over plain `http://`
  is sufficient until rig control or remote operation needs TLS).
- **New runtime artefact**: a single `openwsfz` binary that owns the
  HTTP server and serves the UI; no separate web server required.
- **No impact on existing code**: there is none.
- **License posture**: All added code and the chosen dependency are
  MIT-compatible. No GPL-3.0 code from WSJT-X or JS8Call is consulted
  for implementation &mdash; only the public protocol specifications are
  used as references in later changes.
