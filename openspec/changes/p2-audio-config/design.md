## Context

Phase 1 delivered a working daemon with a web UI, WebSocket push, and the full CI/CD pipeline. The skeleton has no notion of audio hardware or user preferences: every launch behaves identically and forgets everything. Phase 2 must add the two lowest-level plumbing layers that every higher phase depends on:

1. **Audio device layer** — know what capture devices the OS exposes and which one the operator has chosen (FR-003).
2. **Configuration layer** — persist that choice (and future settings) to disk, load it on startup, and accept an operator-supplied path override (FR-004, FR-005, FR-006).

Existing code lives in four projects: `OpenWSFZ.Abstractions`, `OpenWSFZ.Web`, `OpenWSFZ.Daemon`, and the test suite. The abstraction-first pattern established in Phase 1 (`IBindPolicy`, `IAuthPolicy`) scales naturally to two new interfaces.

## Goals / Non-Goals

**Goals:**
- Expose `IAudioDeviceProvider` and `IConfigStore` interfaces in `OpenWSFZ.Abstractions`.
- Implement both on all three target OSes (Windows, Linux, macOS) to the extent needed to satisfy FR-003–FR-006 with automated tests.
- Add `GET /api/v1/audio/devices`, `GET /api/v1/config`, and `POST /api/v1/config` endpoints to the web server.
- Include the active audio device name in the `/api/v1/status` response.
- Accept `--config <path>` CLI flag and `OPENWSFZ_CONFIG` environment variable in the daemon (FR-005).
- Auto-create a minimal default config file on first run (FR-006).
- Remove FR-003, FR-004, FR-005, FR-006 from `traceability-debt.md`.

**Non-Goals:**
- Actual audio capture or signal processing (Phase 3).
- A UI for device selection (Phase 4 — FR-016 prohibits showing controls before the backend is ready, and the frontend settings page is a Phase 4 concern).
- TOML or YAML config format (JSON is sufficient and avoids a new dependency).
- Remote config (loopback-only in v1).

## Decisions

### D1 — Two new class-library projects, not inline expansion

`src/OpenWSFZ.Audio/` and `src/OpenWSFZ.Config/` are created as separate class libraries rather than adding code to `OpenWSFZ.Web` or `OpenWSFZ.Daemon`. Rationale: each subsystem will grow (capture in Phase 3, FT8 decode parameters in Phase 5), and the seams between them matter for testability and future extensibility (NFR-008, NFR-011). Each library has a corresponding test project.

**Rejected:** Putting audio and config code inside `OpenWSFZ.Web` — creates a circular concern (the web project would own business logic) and makes unit-testing without a running server awkward.

### D2 — Cross-platform audio enumeration strategy

Audio device enumeration requires OS-specific APIs. The chosen approach:

- **Windows:** NAudio's `MMDeviceEnumerator` (via `NAudio.Wasapi`) — mature, well-tested, enumerates WASAPI capture endpoints including USB devices.
- **Linux:** Parse `arecord --list-devices` subprocess output — fragile but zero-dependency and sufficient for Phase 2 enumeration. Phase 3 (capture) will replace this with a proper ALSA or PortAudio binding.
- **macOS:** Parse `system_profiler SPAudioDataType -json` subprocess output — same rationale as Linux.

All three paths are hidden behind `IAudioDeviceProvider` (`GetDevicesAsync()` returning `IReadOnlyList<AudioDeviceInfo>`). The platform implementation is selected at runtime via `RuntimeInformation.IsOSPlatform`. Compile-time conditional compilation is avoided to keep the solution tree simple.

**Rejected:** PortAudio / PortAudioSharp — requires a native shared library (`portaudio.dll` / `libportaudio.so`) to be present at runtime. Source-only distribution (NFR-005) means the operator must install it themselves; that is an unacceptable first-run friction for Phase 2 enumeration-only work. Phase 3 will revisit if NAudio cross-platform capture proves inadequate.

**Rejected:** OpenAL (OpenTK) — designed for audio playback and positional sound; capture/enumeration is a secondary concern. The API surface is heavier than needed.

### D3 — JSON config with System.Text.Json source generators

Config format is JSON. The file is read and written using `System.Text.Json` with a `[JsonSerializable]` source-generated context (already the pattern in `OpenWSFZ.Web`, required for AOT). No new NuGet dependency. The schema is kept flat and minimal for Phase 2:

```json
{
  "audioDeviceName": null,
  "port": 8080
}
```

`audioDeviceName: null` means "not yet configured" — the daemon starts without audio (Phase 3 will enforce a non-null device before capture begins). `port` lets the operator persist their preferred port so they do not have to pass `--port` every launch.

**Rejected:** TOML (Tomlyn) — friendlier for hand-editing but adds a NuGet dependency and requires a non-trivial source-gen setup for AOT. Revisit post-v1 if operators request it.

### D4 — Default config-file path follows XDG / platform convention

| OS      | Default path |
|---------|-------------|
| Windows | `%APPDATA%\OpenWSFZ\config.json` |
| Linux   | `$XDG_CONFIG_HOME/openwsfz/config.json` (falls back to `~/.config/openwsfz/config.json`) |
| macOS   | `~/Library/Application Support/OpenWSFZ/config.json` |

Resolved via `Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData)` which returns the correct platform path. Directory is created if it does not exist. This is the same pattern used by most cross-platform CLI tools.

**Rejected:** Placing config next to the executable — executable may be read-only after install; pollutes the source tree during development.

### D5 — Config resolution order (highest wins)

1. `--config <path>` CLI flag
2. `OPENWSFZ_CONFIG` environment variable
3. Platform default path (D4)

Implemented in `LaunchOptions` alongside the existing `Port` property. The resolved path is logged at startup at INFO level.

### D6 — `IConfigStore` is synchronous for reads, async for writes

Config reads happen once at startup on the hot path before the host starts; making them async would complicate `Program.cs` pre-host initialisation. Writes (`SaveAsync`) are async because they are triggered by the HTTP endpoint and must not block the request thread.

### D7 — `DaemonStatus` extended, not replaced

The existing `DaemonStatus(State, Version)` record in `OpenWSFZ.Web` gains an `AudioDevice` field (`string?`, nullable). The WebSocket status event and the REST status endpoint already carry this type. Existing tests pass `null` for `AudioDevice` which is correct pre-configuration.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| `arecord` / `system_profiler` unavailable on a minimal Linux install or in a CI container | The `IAudioDeviceProvider` implementation returns an empty list (not an exception) when the subprocess exits non-zero or the tool is absent. Tests mock the interface rather than spawning subprocesses. A future `PortAudioDeviceProvider` can replace this in Phase 3. |
| NAudio `MMDeviceEnumerator` requires COM initialisation on Windows | `NAudio.Wasapi` handles this internally. Integration test runs on the Windows CI leg where COM is available. |
| Config file corruption on write (partial write / crash) | Write to a temp file in the same directory, then `File.Move(..., overwrite: true)`. Atomic on Windows (same-volume move) and Linux/macOS. |
| AOT trimming removes `JsonSerializable` types from `OpenWSFZ.Config` | Add a `[JsonSerializable(typeof(AppConfig))]` context in the Config project and include it in the chain in `OpenWSFZ.Daemon`'s AOT publish. Pattern is identical to the existing `AppJsonContext` in `OpenWSFZ.Web`. |
| `POST /api/v1/config` accepts any JSON — invalid device names accepted | Phase 2 validates only that the JSON parses and the fields are the right types. Device-existence validation (ensuring `audioDeviceName` matches an enumerated device) is a Phase 3 concern when capture is wired. |

## Open Questions

1. **Should `port` live in the config file?** It overlaps with `--port`. Current plan: yes, but `--port` overrides the file value (same resolution order as `--config`). The daemon logs the active port and its source (flag / file / default) at startup.
2. **Config schema versioning** — not needed for Phase 2 (single flat object). Phase 5 (FT8 parameters) will introduce a `"version"` field and a migration path. No action required now.
