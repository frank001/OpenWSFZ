# OpenWSFZ

An open-source, cross-platform, MIT-licensed weak-signal amateur-radio
application for HAM operators — covering the WSJT-X family of modes (FT8, FT4,
JS8, JT9, JT65, WSPR, and related).

## Project intent

- **For HAM operators**, as a flexible alternative for existing software.
- **Cross-platform** (Windows, Linux, macOS) and **free of restrictions**.
- **MIT-licensed**, clean-room implementation derived from public protocol
  specifications. No code, algorithms, or assets are taken from the GPL-3.0
  WSJT-X or JS8Call source trees.
- **Spec-driven and incrementally delivered**: every behavioural change goes
  through a written proposal ([OpenSpec](openspec/)) before implementation.

## Status

> **Pre-release — source only.** No binaries are distributed yet.
> The current release is **v0.15**. v0.x scope: FT8 receive and transmit,
> CAT rig control, loopback-only web UI, single operator.
> v1.0 is reached when the software can complete a confirmed two-way contact
> end-to-end (RX + CAT rig control + TX). LAN/remote operation and the wider
> mode menu are deferred to v1.0+.

All fifteen development phases to date are merged and archived. FT8 decoding
is **fully functional** against live audio and recorded fixtures.

| Phase | Deliverable | State |
|---|---|---|
| p0 — Foundation | Build pipeline, CI quality gates, tooling | ✅ merged |
| p1 — Walking skeleton | Daemon, embedded web server, WebSocket | ✅ merged |
| p2 — Audio config | Device enumeration, JSON config, Settings REST round-trip | ✅ merged |
| p3 — Web frontend | Dark-theme UI, Settings page, waterfall placeholder | ✅ merged |
| p4 — Audio pipeline | PCM capture (WASAPI / arecord / sox), STA threading fix | ✅ merged |
| p5 — FT8 decoder | Cycle framer, spectrum analyser, initial decode pipeline | ✅ merged |
| p6 — File logging | Per-session log files, retention, log-level config | ✅ merged |
| p7 — Device display name | Friendly device names; legacy config migration | ✅ merged |
| p8 — FT8 decode performance | kgoba/ft8_lib submodule, P/Invoke shim, SNR calibration | ✅ merged |
| p9 — Decode logging | all.txt-style per-cycle decode log | ✅ merged |
| p10 — Ground truth | Replay harness; G6 gate; WSJT-X corpus recovery-rate test | ✅ merged |
| p12 — ft8_lib port | Production P/Invoke decoder; full UAT-01 sign-off | ✅ merged |
| p13 — Cross-platform decoder | libft8.so (Linux x64) + libft8.dylib (macOS ARM64) | ✅ merged |
| p14 — Decode start/stop | FR-017: controlled decode lifecycle; CancellationToken wiring | ✅ merged |
| p15 — Iterative subtraction | Spectrogram-domain second-pass decoder; 69.1% recovery rate | ✅ merged |

## What works today

- **Daemon** starts, emits a welcome banner, and serves the UI at
  `http://127.0.0.1:8080` (port is configurable).
- **FT8 decoding** is fully operational: the daemon decodes received signals
  each 15-second cycle and logs messages in WSJT-X all.txt format.
- **Audio device enumeration** returns real devices on Windows (WASAPI),
  Linux (ALSA via `arecord`), and macOS (sox).
- **PCM audio capture** streams 32-bit float mono at 12 000 Hz from the
  selected device into the decode pipeline.
- **FT8 decode start/stop** — the decode pipeline can be started and stopped
  at runtime without restarting the daemon.
- **Settings page** loads and saves configuration (device selection, port,
  log level) with a REST round-trip; changes are persisted to a JSON config
  file.
- **File logging** — per-session log files are written to a configurable
  directory with automatic retention enforcement.
- **WebSocket** pushes live status events (including `audioActive` state) to
  connected browser tabs.
- **Dark-theme UI** with a waterfall panel (placeholder — no live spectrogram
  data yet).
- **Cross-platform native decoder**: pre-built `libft8` binaries are bundled
  for Windows x64, Linux x64, and macOS ARM64; no native toolchain is required
  to build or run.

## Prerequisites

| Requirement | Version |
|---|---|
| [.NET SDK](https://dotnet.microsoft.com/download) | 10.0 (pinned in `global.json`) |
| Windows | WASAPI audio capture (full support) |
| Linux | `arecord` (`alsa-utils`) for audio capture |
| macOS | `sox` for audio capture |

## Build & run

```bash
# Clone (including the ft8_lib submodule)
git clone --recurse-submodules https://github.com/Frank0x01/OpenWSFZ.git
cd OpenWSFZ

# Build everything (daemon + web + tools + tests)
dotnet build -c Release

# Run the unit and integration tests
dotnet test -c Release --no-build

# Start the daemon
dotnet run --project src/OpenWSFZ.Daemon

# Then open http://127.0.0.1:8080 in your browser
```

Optional flags:

```
--port <n>        Override the HTTP port (default: 8080)
--config <path>   Override the config file path
```

The config file is created automatically on first run at the platform default
location (`%APPDATA%\OpenWSFZ\config.json` on Windows,
`~/.config/OpenWSFZ/config.json` on Linux,
`~/Library/Application Support/OpenWSFZ/config.json` on macOS).

### Running the E2E tests

The end-to-end tests launch the daemon as a real subprocess and require a
self-contained published binary to be present first. Run this once before
`dotnet test`, substituting your target runtime identifier:

```bash
# Windows
dotnet publish src/OpenWSFZ.Daemon -c Release -r win-x64 --self-contained

# Linux
dotnet publish src/OpenWSFZ.Daemon -c Release -r linux-x64 --self-contained

# macOS (Apple Silicon)
dotnet publish src/OpenWSFZ.Daemon -c Release -r osx-arm64 --self-contained
```

`dotnet test` without a prior publish will still succeed for all unit and
integration tests; only the two E2E tests (`FR-002`, `FR-007`) will fail with a
`FileNotFoundException` indicating the missing binary.

## Cross-platform verification

The build and test suite has been verified on all three target platforms:

| Platform | Build | Tests | CI |
|---|---|---|---|
| Windows x64 | ✅ 0 warnings | ✅ 213 passed, 4 skipped | ✅ GitHub Actions |
| Linux x64 (Debian 13, WSL2, .NET 10.0.300) | ✅ 0 warnings | ✅ 213 passed, 4 skipped | ✅ GitHub Actions |
| macOS ARM64 | ✅ | ✅ | ✅ GitHub Actions |

The 4 skipped tests in `OpenWSFZ.Ft8.Tests` are intentional and documented:
the synthetic encoder used in those fixtures emits free-text FT8 frames (i3=0)
which `ft8_lib` correctly rejects; correctness for real signals is covered by
the `RealSignalFixtureTests` ground-truth suite (G6 gate).

All four CI gates pass on every platform:

- **G1** — `dotnet build` with zero warnings
- **G3** — Requirement traceability (every FR/NFR ID mapped to a test)
- **G5** — Dependency licence inventory (MIT / Apache-2.0 / BSD only)
- **G6** — Real off-air signal recovery: three committed 40 m band fixture WAVs decoded against WSJT-X answer keys on Windows x64, Linux x64, and macOS ARM64

## Architecture

OpenWSFZ v0.x is a single native executable with three concurrent roles:

1. **Audio capture & decode pipeline** — captures PCM from a USB audio device,
   frames it for FT8's 15-second cycle, decodes once per cycle via the bundled
   `ft8_lib` native library, and publishes decoded messages.
2. **Embedded web server** — serves the browser UI over loopback (Kestrel),
   REST for config, WebSocket for live events.
3. **Configuration manager** — reads and writes a JSON config file; propagates
   changes to the running daemon without a restart.

The FT8 decode engine is [kgoba/ft8_lib](https://github.com/kgoba/ft8_lib),
included as a git submodule and accessed via P/Invoke through a thin C shim
(`native/ft8_lib/ft8_shim.c`). Pre-built shared libraries for Windows, Linux,
and macOS are committed to the repository so that building from source requires
no native toolchain.

See [`TECHNICAL_SPEC.md`](TECHNICAL_SPEC.md) for the full architecture and
[`REQUIREMENTS.md`](REQUIREMENTS.md) for the v0.x scope and versioning scheme.

## Contributing

This project follows the [OpenSpec workflow](openspec/): every behavioural
change is proposed and reviewed before implementation begins. Please open an
issue to discuss any contribution before raising a pull request.

All code is reviewed against the spec before merge. The CI pipeline enforces
build cleanliness, test coverage, and requirement traceability on every PR.

## License

MIT — see [LICENSE](LICENSE).
