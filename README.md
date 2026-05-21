# OpenWSFZ

An open-source, cross-platform, MIT-licensed weak-signal amateur-radio
application for HAM operators — covering the WSJT-X family of modes (FT8, FT4,
JS8, JT9, JT65, WSPR, and related).

## Project intent

- **For HAM operators**, designed to be something they would prefer over
  existing software.
- **Cross-platform** (Windows, Linux, macOS) and **free of restrictions**.
- **MIT-licensed**, clean-room implementation derived from public protocol
  specifications. No code, algorithms, or assets are taken from the GPL-3.0
  WSJT-X or JS8Call source trees.
- **Spec-driven and incrementally delivered**: every behavioural change goes
  through a written proposal ([OpenSpec](openspec/)) before implementation.

## Status

> **Pre-release — source only.** No binaries are distributed yet. v1 is a
> tightly scoped proof of concept: FT8 receive-only decoding, loopback-only
> web UI, single operator. Transmit, rig control, LAN/remote operation, and
> the wider mode menu are deferred to later versions.

Active v1 development. Five phases are complete or merged; FT8 decoding is
in progress.

| Phase | Deliverable | State |
|---|---|---|
| p0 — Foundation | Build pipeline, CI quality gates, tooling | ✅ merged |
| p1 — Walking skeleton | Daemon, embedded web server, WebSocket | ✅ merged |
| p2 — Audio config | Device enumeration, TOML config, Settings REST round-trip | ✅ merged |
| p3 — Web UI | Dark-theme frontend, Settings page, waterfall placeholder | ✅ merged |
| p4 — Audio pipeline | PCM capture (WASAPI / arecord / sox), STA fix | ✅ merged |
| p5 — FT8 decoder | Live decoded messages from real audio or fixtures | 🔧 in progress |
| p6 — Waterfall | Live spectrogram | ⬜ planned |
| p7 — UI polish | Theme + strict UI visibility gate | ⬜ planned |
| p8 — Hardening | Performance budgets, soak, release candidate | ⬜ planned |

## What works today

- **Daemon** starts, emits a welcome banner, and serves the UI at
  `http://127.0.0.1:8080` (port is configurable).
- **Audio device enumeration** returns real devices on Windows (WASAPI),
  Linux (ALSA), and macOS (sox).
- **PCM audio capture** streams 32-bit float mono at 12 000 Hz from the
  selected device into the decode pipeline.
- **Settings page** loads and saves configuration (device selection, port)
  with a REST round-trip; changes are persisted to a TOML config file.
- **WebSocket** pushes live status events to connected browser tabs.
- **Dark-theme UI** with a waterfall panel (placeholder — no live data yet).

FT8 decoding is not yet functional.

## Prerequisites

| Requirement | Version |
|---|---|
| [.NET SDK](https://dotnet.microsoft.com/download) | 10.0 (pinned in `global.json`) |
| Windows | WASAPI audio capture (full support) |
| Linux | `arecord` (`alsa-utils`) for audio capture |
| macOS | `sox` for audio capture |

## Build & run

```bash
# Clone
git clone https://github.com/Frank0x01/OpenWSFZ.git
cd OpenWSFZ

# Build everything (daemon + web + tools + tests)
dotnet build

# Run the tests
dotnet test

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

## Architecture

OpenWSFZ v1 is a single native executable with three concurrent roles:

1. **Audio capture & decode pipeline** — captures PCM from a USB audio device,
   frames it for FT8's 15-second cycle, decodes once per cycle, publishes results.
2. **Embedded web server** — serves the browser UI over loopback (Kestrel),
   REST for config, WebSocket for live events.
3. **Configuration manager** — reads and writes a TOML config file; propagates
   changes to the running daemon without a restart.

See [`TECHNICAL_SPEC.md`](TECHNICAL_SPEC.md) for the full architecture and
[`REQUIREMENTS.md`](REQUIREMENTS.md) for the v1 scope.

## Contributing

This project follows the [OpenSpec workflow](openspec/): every behavioural
change is proposed and reviewed before implementation begins. Please open an
issue to discuss any contribution before raising a pull request.

All code is reviewed against the spec before merge. The CI pipeline enforces
build cleanliness, test coverage, and requirement traceability on every PR.

## License

MIT — see [LICENSE](LICENSE).
