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
> The current release is **v0.21**. v0.x scope: FT8 receive and transmit,
> CAT rig control, loopback-only web UI, single operator.
> v1.0 is reached when the software can complete a confirmed two-way contact
> end-to-end over RF (RX + CAT rig control + TX on-air). LAN/remote operation
> and the wider mode menu are deferred to v1.0+.

All development phases to date are merged and archived. FT8 decoding
**and transmitting** are fully functional against live audio and recorded fixtures.
A complete automated six-message FT8 QSO exchange has been validated via
VoiceMeeter software loopback.

| Phase | Deliverable | State |
|---|---|---|
| p0 — Foundation | Build pipeline, CI quality gates, tooling | ✅ merged |
| p1 — Walking skeleton | Daemon, embedded web server, WebSocket | ✅ merged |
| p2 — Audio config | Device enumeration, JSON config, Settings REST round-trip | ✅ merged |
| p3 — Web frontend | Dark-theme UI, Settings page, real-time waterfall | ✅ merged |
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
| p16 — CAT control | `IRadioConnection` abstraction; `SerialCatConnection`; `RigctldConnection`; `CatPollingService`; CAT config section; Settings CAT UI and status-bar indicator | ✅ merged |
| p17 — Settings UX & freq persistence | Tabbed Settings page; serial port enumeration; three-tier effective-frequency resolution; dial frequency persisted across restarts (FR-035–FR-039) | ✅ merged |
| p18 — Settings dirty state | "Unsaved changes" badge and breadcrumb/browser navigation guard (FR-040, FR-041) | ✅ merged |
| p19 — Frequency management | Configurable FT8 frequency list; `FrequencyStore`; REST tune endpoint; dial-frequency selector on main page (FR-042–FR-045) | ✅ merged |
| p20 — FA digit width | Self-calibrating digit-width computation in `SerialCatConnection` FA tune command | ✅ merged |
| ft8-qso-answerer-v1 — FT8 TX & QSO answerer | FT8 TX pipeline (native encode, GFSK synthesis, WASAPI playback); `IPttController` abstraction; QSO answerer state machine (auto-answer CQ, 6-message exchange, retry, watchdog, operator abort); ADIF 3.x log writer; `tx` config section; Settings TX fields | ✅ merged |

## Decoder Measurement System Analysis (Gage R&R)

OpenWSFZ runs a continuous **Gage R&R / Measurement System Analysis** against WSJT-X to
quantify decoder quality across four dimensions:

| Scenario | What is measured | Method |
|---|---|---|
| **S1** SNR ladder | How accurately and consistently does each app report signal-to-noise ratio? | Crossed two-way ANOVA; %GR&R and ndc vs defined tolerance |
| **S1b** Low-SNR threshold | At what SNR does each app stop decoding? | Attribute decode-rate study at −24 to −15 dB |
| **S2** Frequency sweep | Reported audio frequency accuracy and consistency | %GR&R vs ±50 Hz tolerance |
| **S3** DT offset | Reported timing accuracy and consistency | %GR&R vs ±1.5 s tolerance; DT convention correction applied |
| **S4/S5** Density & noise | Decode detection and false-positive rate | Attribute Agreement Analysis; Cohen's κ |
| **S7** Compounding | Co-channel / pileup recovery | Informational; per-overlap-family recovery rates |

The harness is fully decoupled from OpenWSFZ source: it shares no assemblies and interacts
only with a shared **VB-CABLE** virtual audio device and the two applications' `ALL.TXT`
log files. Signals are synthesised by an independent clean-room FT8 encoder (text → tones
→ PCM) so that truth is exactly known for every trial. Each trial draws a fresh seeded
noise realisation, giving non-zero repeatability variance.

### Latest validated results — S1–S8: [`815b652`](qa/rr-study/results/2026-06-14-815b652/report.md) (2026-06-14, shim 20260016)

| Scenario | Metric | Value | Verdict |
|---|---|---|---|
| S1 SNR | %GR&R | 0.3% | ✅ PASS |
| S1 SNR | ndc | 27 | ✅ PASS |
| S1 SNR | OpenWSFZ bias | +1.42 dB | ✅ PASS |
| S1b Low-SNR threshold | Decode rate (both apps) | 0% @ −21 dB | ℹ️ Informational |
| S2 Frequency | %GR&R | 0.0% | ✅ PASS |
| S2 Frequency | ndc | 1 536 | ✅ PASS |
| S3 DT | %GR&R | 3.0% | ✅ PASS |
| S3 DT | ndc | 7 | ✅ PASS |
| S4/S5 Detection | κ (OpenWSFZ vs truth) | 1.000 | ✅ PASS |
| S5 False positives | FP rate (OpenWSFZ) | 0.0% | ✅ PASS |
| S7 Co-channel | Overall recovery | 50.54% vs WSJT-X 77.42% | ℹ️ Informational |

**Overall: PASS.**  Full S1–S8 regression gate run at `815b652` (2026-06-14, shim 20260016):
all metric gates pass.  S7 co-channel gap remains informational (D-001, open);
five shim-level hypotheses exhausted; current H4 variability band 43–57%.

See [`qa/rr-study/STUDY-SPEC.md`](qa/rr-study/STUDY-SPEC.md) for the full study design
and [`qa/rr-study/RUNBOOK.md`](qa/rr-study/RUNBOOK.md) for the operating procedure.

---

## WSJT-X decode parity

> **Key metric:** how well OpenWSFZ recovers the same signals as WSJT-X on
> identical recordings. Measured against a fixed 42-cycle corpus (887 total
> WSJT-X decodes, 40 m band, real off-air recordings). Higher is better;
> false-positive rate must stay ≤ 6%.

| Version | Phase | Recovery rate | Raw | False-positive rate | Approach |
|---|---|---|---|---|---|
| v0.10 | p10 baseline | 66.6% | 591 / 887 | 3.9% (24 / 615) | Single-pass ft8_lib decode |
| v0.15 | p15 | **69.1%** | 613 / 887 | 3.8% (24 / 637) | + spectrogram-domain second-pass (±1-bin suppression) |

The spectrogram-domain approach plateaus at ~69%: the FFT waterfall stores
carrier frequency at ±3.125 Hz resolution, which prevents coherent
PCM-domain waveform cancellation. Closing the remaining gap to ≥ 80%
requires sub-Hz carrier-frequency estimation and PCM-domain waveform
subtraction, planned for a future change.

## What works today

- **Daemon** starts, emits a welcome banner, and serves the UI at
  `http://127.0.0.1:8080` (port is configurable).
- **FT8 decoding** is fully operational: the daemon decodes received signals
  each 15-second cycle and logs messages in WSJT-X all.txt format.
- **FT8 transmit** — the daemon can encode and transmit FT8 messages via
  any WASAPI output device. Audio is synthesised in managed C# from native
  FT8 tone sequences (continuous-phase GFSK, 48 kHz, ±0.5 peak amplitude).
- **QSO answerer** — an automated state machine listens for decoded CQs and
  conducts the full six-message FT8 exchange (answer → signal report →
  roger report → RR73/RRR → 73). Configurable retry count (default 3) and
  watchdog timer (default 4 minutes). Operator abort is available via
  `POST /api/v1/tx/abort`. State is exposed via `GET /api/v1/tx/status` and
  pushed in real time over WebSocket. Auto-answer is off by default and
  must be enabled explicitly in Settings. Validated via VoiceMeeter
  software loopback against WSJT-X (three complete QSOs logged).
- **ADIF logging** — a completed QSO appends one ADIF 3.x record to
  `ADIF.log` (beside `ALL.TXT`), with correct `TIME_ON`/`TIME_OFF` in
  `HHMMSS` format, ITU band derivation from dial frequency, and graceful
  handling of write failures.
- **Audio device enumeration** returns real devices on Windows (WASAPI),
  Linux (ALSA via `arecord`), and macOS (sox).
- **PCM audio capture** streams 32-bit float mono at 12 000 Hz from the
  selected device into the decode pipeline.
- **FT8 decode start/stop** — the decode pipeline can be started and stopped
  at runtime without restarting the daemon.
- **Settings page** loads and saves configuration across four tabs — Radio
  hardware, Logging, Advanced, and Frequencies — with a REST round-trip;
  changes are persisted to a JSON config file. Available serial ports are
  enumerated automatically and presented as a dropdown. An "Unsaved changes"
  badge appears when the form is dirty, and a navigation guard prevents
  accidental loss of edits. TX fields (callsign, grid, auto-answer toggle,
  watchdog minutes, retry count) are pre-populated from the loaded config.
- **CAT rig control** — live dial frequency readout via two selectable
  transports: `SerialCatConnection` (direct serial, `FA;` command) and
  `RigctldConnection` (TCP client to a running `rigctld` daemon). CAT status
  (Connected / Disabled / Error) is shown in the status bar. The last
  successfully-polled frequency is persisted and restored at next startup.
- **Frequency management** — a configurable list of FT8 working frequencies
  (15 defaults covering common bands) is stored in `frequencies.json` and
  managed via the Frequencies tab CRUD table. When CAT is active the
  dial-frequency indicator on the main page becomes a selector; choosing a
  frequency tunes the rig. When CAT is disabled the selection updates the
  config directly.
- **File logging** — per-session log files are written to a configurable
  directory with automatic retention enforcement.
- **WebSocket** pushes live status events (including `audioActive`,
  `catStatus`, and `txState`) to connected browser tabs.
- **Dark-theme UI** with a real-time waterfall displaying live spectrogram
  data from the active audio device (visual polish is ongoing).
- **Cross-platform native decoder**: pre-built `libft8` binaries are bundled
  for Windows x64, Linux x64, and macOS ARM64. No native toolchain is required
  to build or run on Windows or Linux. On macOS the committed dylib is a local-
  development reference; CI always rebuilds it from source using Clang so that
  shim changes are picked up automatically.

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
| Windows x64 | ✅ 0 warnings | ✅ 442 passed | ✅ GitHub Actions |
| Linux x64 (Debian 13, WSL2, .NET 10.0.300) | ✅ 0 warnings | ✅ 442 passed | ✅ GitHub Actions |
| macOS ARM64 | ✅ | ✅ | ✅ GitHub Actions |

All five CI gates pass on every platform:

- **G1** — `dotnet build` with zero warnings
- **G3** — Requirement traceability (every FR/NFR ID mapped to a test)
- **G5** — Dependency licence inventory (MIT / Apache-2.0 / BSD only)
- **G6** — Real off-air signal recovery: three committed 40 m band fixture WAVs decoded against WSJT-X answer keys on Windows x64, Linux x64, and macOS ARM64
- **G7** — Secrets scan (gitleaks over full commit history; any credential finding fails the build)

## Architecture

OpenWSFZ v0.x is a single native executable with four concurrent roles:

1. **Audio capture & decode pipeline** — captures PCM from a USB audio device,
   frames it for FT8's 15-second cycle, decodes once per cycle via the bundled
   `ft8_lib` native library, and publishes decoded messages.
2. **FT8 TX pipeline** — encodes FT8 messages via the native shim, synthesises
   GFSK audio at 48 kHz, and plays it through the configured WASAPI output device.
   The `QsoAnswererService` drives a six-state FSM (Idle → TxAnswer → WaitReport
   → TxReport → WaitRr73 → Tx73 → QsoComplete) and writes ADIF records on
   completion.
3. **Embedded web server** — serves the browser UI over loopback (Kestrel),
   REST for config and TX control, WebSocket for live events.
4. **Configuration manager** — reads and writes a JSON config file; propagates
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
