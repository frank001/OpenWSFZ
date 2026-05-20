## Why

Phase 1 proved the daemon starts, serves the web UI, and pushes live data over WebSocket. Phase 2 lays the two foundations every subsequent phase depends on: knowing which audio device to capture from (FR-003), and remembering that choice between sessions (FR-004 – FR-006). Without these, FT8 decode has nowhere to read audio from and no way to recall the operator's device preference on the next launch.

## What Changes

- **Audio device enumeration** — a new `OpenWSFZ.Audio` class library enumerates USB audio capture devices on the host OS (via NAudio on Windows, cross-platform via a thin abstraction) and exposes them through a new REST endpoint.
- **Configuration subsystem** — a new `OpenWSFZ.Config` class library owns the config-file lifecycle: load on startup, write on Save, default-file creation on first run. A `--config <path>` CLI flag and `OPENWSFZ_CONFIG` environment variable override the default path.
- **API surface** — two new REST endpoints in the web server: `GET /api/v1/audio/devices` (list capture devices) and `GET /api/v1/config` / `POST /api/v1/config` (read and write the configuration).
- **Daemon wiring** — `Program.cs` loads config at startup, registers the audio and config services in DI, passes the resolved audio device name into the status object so the WebSocket status event carries it.
- **traceability-debt.md update** — remove FR-003, FR-004, FR-005, FR-006 from the grace-period file as tests will now cover them.

## Capabilities

### New Capabilities

- `audio-device`: USB audio capture device enumeration — OS-level device list, REST API to expose it, abstraction layer keeping NAudio/CoreAudio/ALSA behind an interface.
- `configuration`: Config-file persistence — TOML or JSON config file, default-file creation on first run, `--config` CLI flag and `OPENWSFZ_CONFIG` env-var override, REST API to read and write it.

### Modified Capabilities

- `daemon-host`: Gains `--config <path>` CLI flag and `OPENWSFZ_CONFIG` env-var support (FR-005); loads and validates config at startup; emits a log line naming the active config file; creates the default config on first run (FR-006).
- `web-server`: Gains three new REST endpoints (`GET /api/v1/audio/devices`, `GET /api/v1/config`, `POST /api/v1/config`) and returns the active audio device name in the `/api/v1/status` response.

## Impact

- **New projects:** `src/OpenWSFZ.Audio/` (class library), `src/OpenWSFZ.Config/` (class library), `tests/OpenWSFZ.Audio.Tests/`, `tests/OpenWSFZ.Config.Tests/`.
- **Modified projects:** `src/OpenWSFZ.Daemon/` (config loading, DI wiring), `src/OpenWSFZ.Web/` (new endpoints, updated status DTO), `tests/OpenWSFZ.Web.Tests/` (new integration tests).
- **New NuGet dependencies:** NAudio (audio enumeration on Windows), a cross-platform audio abstraction or PortAudio binding for Linux/macOS, a config-file serialiser (System.Text.Json sufficient if JSON; Tomlyn if TOML).
- **Abstractions layer:** `IBindPolicy` and `IAuthPolicy` already exist in `OpenWSFZ.Abstractions`; two new interfaces join them: `IAudioDeviceProvider` and `IConfigStore`.
- **traceability-debt.md:** FR-003, FR-004, FR-005, FR-006 removed from debt once tests ship.
