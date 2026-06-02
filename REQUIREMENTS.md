# OpenWSFZ &mdash; Requirements Document

**Version:** 1.15
**Date:** 2026-05-31
**Status:** Draft
**Prepared by:** Requirements Analyst (AI-assisted)
**For:** Architecture & Planning Team

---

## 1. Executive Summary

OpenWSFZ is an open-source, MIT-licensed, cross-platform alternative
to the WSJT-X weak-signal amateur-radio application family. Where
WSJT-X is a Qt desktop application under GPL-3.0, OpenWSFZ is
controlled entirely from a web page served by the application itself,
letting licensed radio operators run it on whatever desktop hardware
they prefer (Windows, Linux, macOS) and reach it from a local browser.
**The project uses the following versioning scheme: v0.x covers all
work prior to a confirmed QSO; v1.0 is reached when the software can
make a confirmed two-way contact (RX + CAT control + TX); each
user-facing feature shipped increments the minor version.
The current release is v0.11.** The v0.x body of work is a tightly
scoped proof of concept: FT8 receive-only decoding, loopback-only web
UI, single operator, source-only distribution. Transmit, rig control,
the wider mode menu, remote / LAN operation, and headless deployment
are all explicitly deferred to v1.0+ on the way to a public release.

---

## 2. Project Context

### 2.1 Background & Motivation

The project exists to give licensed amateur-radio operators an
alternative to WSJT-X that is:

- **Web-controlled** rather than tied to a desktop Qt UI.
- **Cross-platform** from a single source tree.
- **MIT-licensed**, removing the GPL-3.0 restrictions of the
  reference application.

The aspirational bar is competitive: **the project's goal is to be
software that HAM operators would prefer over the existing options**,
not merely match them. Solo developer initially; intended for wider
community use once public-release readiness is reached.

### 2.2 Scope

**In Scope (v0.x)**

- Receive-only **FT8** decoding from a chosen audio source.
- A self-hosted **web UI** served by the application itself, reachable
  on `http://127.0.0.1:<port>` from a browser on the same machine.
- **USB audio device** enumeration and selection from the UI.
- **Configuration file** persistence, loaded by default, with a
  CLI/environment override for an alternative file path.
- A **minimal default config file** that ships with the application
  so first-run is in a known state.
- **Dark default theme**, themable by editing CSS files on disk.
- **Frontend** in its own top-level folder with conventional
  subfolders for HTML, CSS, JS; all files user-editable.
- **Terminal-launched, foreground** process model on all three
  platforms, printing a welcome banner with the bind URL.
- **Cross-platform builds** for Windows, Linux, and macOS on
  **x86_64** from one source tree.
- **Source-only distribution** via the project's GitHub repository
  (private until public-release readiness is reached).

**Out of Scope (v0.x, deferred to v1.0+)**

- Transmit (modulation, audio output, PTT, QSO state machine).
- Non-FT8 modes (FT4, JT9, JT65, WSPR, Q65, MSK144, Echo).
- Decode persistence (log files) and export (ADIF, CSV, etc.).
- Rig control / CAT integration (serial, USB, network).
- Remote / LAN operation: non-loopback bind, authentication, TLS.
- Multi-operator support, per-user state.
- Windows-service deployment mode.
- ARM64 builds, Raspberry Pi-class hardware, Banana Pi BPI-R4
  deployment, and any other headless deployment.
- Native installers (`.msi`, `.pkg`, `.deb`, `.rpm`) and the
  associated code-signing.
- Pre-built binary distribution.
- Auto-update / in-app update checking.

### 2.3 Stakeholders

| Role                          | Name / Team                           | Interest                                                                                  |
|-------------------------------|---------------------------------------|-------------------------------------------------------------------------------------------|
| Product Owner / Sponsor       | The project author (solo)             | All product decisions, scope, direction.                                                  |
| Primary user (v0.x)           | The project author                    | Personal use, end-to-end testing on their own gear.                                       |
| Aspirational user community   | Licensed amateur-radio operators (HAMs) worldwide | Future adoption after the project goes public.                                |
| Future contributors           | TBD post-public-release               | Source contributions, issue reports, peer review.                                         |
| ANALYST role (AI-assisted)    | See `prompts/ANALYST.md`              | Requirements gathering and documentation.                                                 |
| ARCHITECT role (AI-assisted)  | Prompt to be written                  | System design from this document.                                                         |
| DEVELOPER role (AI-assisted)  | Prompt to be written                  | Implementation from architectural artifacts.                                              |
| QA role (AI-assisted)         | Prompt to be written                  | Test design, coverage discipline, gating of merges on green builds.                       |

---

## 3. User Personas

Only one persona is in scope for v0.x.

### 3.1 Licensed Amateur-Radio Operator (HAM)

- **Role:** Solo operator running FT8 reception on their own equipment.
- **Goals:**
  - Decode FT8 signals on the band they are tuned to.
  - See decoded messages with audio offset in real time, comparable
    to the WSJT-X experience.
  - Configure their audio device(s) once and have those choices
    persist between sessions.
  - Eventually prefer OpenWSFZ over WSJT-X for cross-platform reach
    and web-UI flexibility.
- **Pain Points:**
  - Existing WSJT-X is Qt-bound and not naturally controlled from a
    non-local browser.
  - Cross-platform support for hobby radio software is uneven.
  - GPL-3.0 restrictions limit what they can do with the source.
- **Technical Proficiency:**
  - Holds a valid amateur-radio licence (regulator exam passed);
    therefore familiar with radio operation, modes, frequencies,
    callsigns.
  - Comfortable with building from source &mdash; v0.x ships source-only.
  - Comfortable editing configuration files and CSS.
  - Assumed technically literate but not necessarily a professional
    software engineer.

---

## 4. Functional Requirements

### 4.1 Core Features (MVP)

| ID     | Feature                                                | Description                                                                                                                                                                       | Priority    |
|--------|--------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|
| FR-001 | FT8 receive-only decode                                | The application SHALL decode FT8 transmissions present in the configured audio input and surface the decoded messages to the UI in real time.                                     | Must Have   |
| FR-002 | Self-hosted web UI                                     | The application SHALL serve its full user interface as a web page on `http://127.0.0.1:<port>`. No external web server is required.                                               | Must Have   |
| FR-003 | USB audio device selection                             | The UI SHALL enumerate available USB audio capture devices on the host OS and let the operator choose which to use.                                                               | Must Have   |
| FR-004 | Configuration persistence                              | The application SHALL persist the operator's settings (audio device choice, etc.) to a configuration file. Changes made in the UI SHALL be written via a Save action.             | Must Have   |
| FR-005 | Configurable config-file path                          | The default config-file path SHALL be overridable via a CLI flag and/or environment variable, letting an operator point the app at an alternative file.                           | Must Have   |
| FR-006 | Default config ships with app                          | A minimal default configuration file SHALL be available on first start so a fresh install is in a known runnable state.                                                           | Must Have   |
| FR-007 | Terminal welcome banner                                | On startup the application SHALL print a welcome banner to stderr/stdout stating the IP address and port where the web UI is reachable.                                           | Must Have   |
| FR-008 | Waterfall display                                      | The main UI SHALL render a live waterfall (spectrogram) of the audio input.                                                                                                       | Must Have   |
| FR-009 | Decoded messages list                                  | The main UI SHALL display decoded FT8 messages as they arrive, with at minimum the decoded text and the audio offset.                                                             | Must Have   |
| FR-010 | Settings page navigable from main page                 | The web UI SHALL provide a Settings page reachable from the main page (affordance is the architect's choice) that exposes all user-configurable values.                           | Must Have   |
| FR-011 | Save action on Settings                                | The Settings page SHALL provide a Save action that writes changes to the active configuration file.                                                                               | Must Have   |
| FR-012 | Dark theme by default                                  | The web UI SHALL ship with a dark theme as its default visual style.                                                                                                              | Must Have   |
| FR-013 | CSS-file-based theming                                 | Theming SHALL be done by editing the CSS files on disk. No in-app theme switcher is required in v1.                                                                               | Must Have   |
| FR-014 | Frontend folder layout                                 | The frontend SHALL live in its own top-level folder with conventional subfolders for HTML, CSS, and JS.                                                                           | Must Have   |
| FR-015 | Frontend files user-editable                           | All frontend files (HTML, CSS, JS) SHALL be plain files on disk that an operator can edit without rebuilding the application.                                                     | Must Have   |
| FR-016 | Strict UI visibility rule                              | Any control visible in the web UI MUST be fully implemented and bound to a working backend. No "coming soon" placeholders and no greyed-out future controls are permitted.        | Must Have   |
| FR-017 | Decode start/stop control                              | The main UI SHALL provide a control (button or toggle) that starts and stops the FT8 decode pipeline. Activating **stop** SHALL halt audio capture and decode processing immediately. Activating **start** SHALL resume both, subject to a configured audio device being present. The current decode state (active / stopped) SHALL be clearly indicated in the status area of the main UI. The decode state SHALL persist to the configuration file so that a session explicitly stopped by the operator does not auto-resume on the next application launch. | Must Have   |
| FR-018 | Cycle countdown timer (testing aid)                   | When enabled, the main UI SHALL display a countdown timer showing the time remaining until the next FT8 cycle boundary (i.e. the next UTC second divisible by 15). When the countdown reaches zero a **GO** indicator SHALL be shown for approximately 8 seconds — the window during which starting a 15-second test recording will place the signal within the decoder's time-domain sweep range. After the GO window the timer SHALL resume counting down to the subsequent cycle. The timer SHALL be hidden by default. A checkbox on the Settings page (labelled clearly as a testing aid, e.g. *"Show cycle countdown"*) SHALL enable or disable it; this setting SHALL be persisted to the configuration file (`ShowCycleCountdown`, default: `false`). The 8-second GO window is derived from the decoder's time-domain sweep limit and SHALL be updated if that limit changes. | Nice to Have |
| FR-019 | Configurable application logging                      | The application SHALL implement structured logging using the .NET `Microsoft.Extensions.Logging` infrastructure. The seven standard log levels defined by `Microsoft.Extensions.Logging.LogLevel` SHALL be supported: **Trace**, **Debug**, **Information**, **Warning**, **Error**, **Critical**, **None**. The active minimum level SHALL be selectable from a dropdown on the Settings page and persisted to the configuration file (`AppConfig.LogLevel`, default: `"Information"`). Setting a minimum level shows that level and all more severe levels (e.g. `Warning` shows Warning, Error, and Critical); `None` suppresses all output. The levels map to operational intent as follows — **Trace**: internal loop counters, per-sample values, raw Goertzel energies; **Debug**: framer offsets, Costas scores, LLR magnitudes, time-domain sweep positions; **Information**: pipeline start/stop, device selection, decode cycle results, configuration changes; **Warning**: recoverable anomalies such as buffer overflows, slow decode cycles, or device reconnects; **Error**: operation failures that do not terminate the application (e.g. a single cycle decode error); **Critical**: unrecoverable failures requiring operator intervention; **None**: all output suppressed. Log output SHALL be written to the console sink in a consistent format. When `FR-022` file logging is enabled, output is additionally written to a timestamped file. Every component of the application — audio capture pipeline, FT8 decode pipeline (CycleFramer, Ft8Decoder, symbol extraction, Costas synchronisation, LDPC), WebSocket event bus, HTTP API, and configuration store — SHALL emit log entries at the appropriate level at key operational points sufficient to diagnose the application state without a debugger attached. The console log level takes effect immediately when the operator saves settings. | Must Have   |
| FR-020 | Audio activity indicator in heartbeat                 | Each WebSocket heartbeat frame SHALL carry a JSON payload containing a boolean field `audioActive`. The field SHALL be `true` if at least one audio sample with absolute value greater than 1×10⁻⁶ was received from the capture pipeline in the interval since the previous heartbeat (or since application start for the first heartbeat); it SHALL be `false` if the capture session is not running, no samples were received in the interval, or every received sample was at or below the threshold. The activity window resets at each heartbeat emission — it reflects the most recent 5-second interval only. The heartbeat frame format SHALL be: `{"type":"heartbeat","payload":{"audioActive":true}}`. The threshold value (1×10⁻⁶) matches the RMS silence guard in `Ft8Decoder.DecodeAsync` and SHALL be kept in sync if that guard changes. The `audioActive` field SHALL also be present in the initial `status` event payload alongside the existing `DaemonStatus` fields, reflecting audio activity since the previous application-start or pipeline restart. The main UI SHALL display the current `audioActive` state visibly in the status area (e.g. a distinct indicator alongside the existing device name and decoding-state badge). | Must Have   |
| FR-021 | Capture stop logging                                  | The audio capture pipeline SHALL emit a log entry every time a capture session terminates, regardless of the reason. The entry SHALL include the device identifier and a clear description of why the session ended. The **reason** SHALL be classified into exactly three cases, each with its own log level: **(1) Operator-stopped** — the session was ended by an explicit `StopAsync` call (operator action or application shutdown); logged at **Information** level. **(2) Unexpected end** — the capture source ended without a cancellation signal (e.g. WASAPI `RecordingStopped` fired with no exception, indicating a driver-level or audio-engine-level stop that was not requested by the application); logged at **Warning** level with a message that clearly distinguishes this from a normal stop, so the operator knows the device did not stop on instruction. **(3) Error** — the session terminated because an exception was thrown by the capture source or the audio driver; logged at **Error** level. The log entry SHALL include the full exception details: type, message, and complete stack trace on subsequent lines, using the same `[OpenWSFZ] YYYY-MM-DD HH:MM:SS [LEVEL]  ComponentName — …` format defined in FR-019. A silent termination — one where the capture stops but no log entry appears — is a violation of this requirement regardless of the cause. | Must Have   |
| FR-022 | File logging sink                                     | When `logging.fileEnabled` is true, the daemon SHALL write log events to a timestamped file in `logging.directory` (default: `logs/` beside the executable) in addition to the console sink. The file sink SHALL use an independent `logging.fileLogLevel` threshold. An invalid or unwritable directory SHALL produce a console Warning and the daemon SHALL continue without a file sink. | Must Have |
| FR-023 | Log rotation                                          | Each application start SHALL open a new file (`openswfz-<yyyyMMddTHHmmssZ>.log`). The operator MAY configure scheduled rotation: `"session"` (startup only), `"hourly"` (each UTC hour boundary), `"daily"` (at `logging.rotationTime` UTC), or `"weekly"` (on `logging.rotationDayOfWeek` at `logging.rotationTime` UTC). Rotation timers SHALL recalculate from `DateTime.UtcNow` after each firing. | Must Have |
| FR-024 | Log file retention                                    | After each rotation, the daemon SHALL delete the oldest `openswfz-*.log` files in the configured directory until at most `logging.maxFiles` (default: 7) files remain. `maxFiles` ≤ 0 SHALL be clamped to 1 with a Warning. Deletion failures SHALL be logged at Warning and SHALL NOT abort rotation. | Must Have |
| FR-025 | Audio device friendly name display                    | The daemon SHALL persist the human-readable audio device label (`audioDeviceFriendlyName`) alongside the OS identifier (`audioDeviceId`). Wherever the active device is displayed — status bar, WebSocket events, log messages — the friendly name SHALL be shown when available; the OS identifier SHALL be the fallback. | Must Have |
| FR-026 | FT8 decode throughput                                 | The FT8 decoder SHALL complete each 15-second decode cycle within 13 seconds of wall-clock time. No more than 2 Goertzel candidates SHALL be evaluated per (time-position, base-frequency) sweep pair. | Must Have |
| FR-027 | Dial frequency configuration                          | The operator SHALL be able to configure the radio dial frequency (in MHz) via a `decodeLog.dialFrequencyMHz` field (double, default `0.0`) in `AppConfig`. The value is used when writing the ALL.TXT decode log. | Must Have |
| FR-028 | WSJT-X compatible ALL.TXT decode log                  | When `decodeLog.enabled` is `true`, the daemon SHALL append one line per decoded FT8 message to `decodeLog.path` (default `ALL.TXT` beside the executable) after each decode cycle in WSJT-X format: `YYMMDD_HHMMSS     D.DDD Rx FT8 {snr,6} {dt,4:F1} {freq,4} {message}`. Each line SHALL be terminated with CRLF. File write failures SHALL be logged at Warning and SHALL NOT interrupt the decode pipeline. | Must Have |
| FR-029 | Reproducible real-signal decode verification          | The project SHALL maintain a corpus of real off-air FT8 recordings as 12 kHz mono WAV files, each paired with the set of FT8 messages WSJT-X decoded from that recording (the "answer key"). The test infrastructure SHALL provide: **(1)** a WAV-to-PCM reader converting 12 kHz mono int16 WAV files into the `float[]` PCM buffer accepted by `Ft8Decoder.DecodeAsync`, normalised to `[-1, 1]`, rejecting non-12 kHz/non-mono/non-PCM inputs with a clear error; **(2)** an offline replay harness that decodes each corpus file through `Ft8Decoder.DecodeAsync` and reports, per recording and in aggregate, the count of matched, missed, and false-positive messages relative to the answer key (the "recovery rate"); **(3)** at least two representative WAV fixtures committed as embedded test resources, each with an asserted answer-key subset, and an integration test asserting those subsets decode. The real-signal fixture integration test SHALL be the authoritative correctness oracle for the FT8 decoder. The synthetic-encoder round-trip test (encoding using the same constants the decoder uses) SHALL be treated as an internal-consistency check only and SHALL NOT be accepted as evidence that the decoder decodes real off-air signals. | Must Have |
| FR-030 | Logging configuration hot-reload                      | All changes to logging configuration made via the Settings page SHALL take effect in the running application immediately when the operator saves, without requiring a restart. Specifically: **(1) Console log level** — the very next log event emitted after the save completes SHALL use the updated level; **(2) File sink enabled/disabled** — if toggled to enabled, a new timestamped log file SHALL be opened in the configured directory immediately; if toggled to disabled, the current file sink SHALL be flushed and closed; **(3) File log level** — the new threshold SHALL apply to events written after the save; **(4) Log directory** — if changed while file logging is enabled, the current file is closed and a new file is opened in the new directory; **(5) Rotation schedule and max files** — rotation timers SHALL be recalculated from the new schedule immediately; the new max-files limit SHALL apply at the next rotation. No setting in the logging section of the Settings page SHALL display or imply that a restart is required. | Must Have |
| FR-031 | CAT connection configuration                          | The application SHALL support an optional `cat` configuration object that controls connection to a CAT-capable rig. The `cat` object SHALL include: `enabled` (bool, default `false`), `rigModel` (string: `"SerialCat"` or `"RigCtld"`), `serialPort` (string), `baudRate` (int), `rigctldHost` (string, default `"127.0.0.1"`), `rigctldPort` (int, default `4532`), `pollIntervalSeconds` (int, 1–60, default `1`). When `cat.enabled` is `false` (the default), no serial port or TCP connection SHALL be opened and the daemon SHALL behave exactly as before this feature was introduced. The `cat` object SHALL be exposed in full via `GET /api/v1/config` and accepted via `POST /api/v1/config`. | Must Have |
| FR-032 | Live rig frequency readout via CAT                    | When CAT is enabled and a rig connection is established, the daemon SHALL poll `VFO-A` frequency from the rig at the configured interval using a read-only command (`FA;` for serial CAT, `\get_freq` for `rigctld`). The polled frequency SHALL be used as the effective dial frequency for ALL.TXT logging and the UI status bar, taking precedence over the operator's manually configured `decodeLog.dialFrequencyMHz`. When CAT is disabled or in error, components SHALL fall back to `decodeLog.dialFrequencyMHz` transparently. No frequency-set, mode-set, or PTT commands SHALL be sent by this feature. | Must Have |
| FR-033 | CAT connection status indicator in UI                 | The main-page status bar SHALL display the current effective dial frequency (formatted to three decimal places followed by `MHz`) and a CAT connection status badge. The badge SHALL reflect the live CAT state: **Connected** (green), **Error** (red/amber), or absent when **Disabled**. The status bar frequency and badge SHALL update in real time via the `cat_status` WebSocket event without a page reload. The Settings page SHALL display a read-only CAT status indicator and a note when `RigCtld` mode is selected that `rigctld` must be running before enabling. This requirement is subject to FR-016: these controls SHALL appear only from this change onwards when the backend CAT capability is fully implemented. | Must Have |
| FR-034 | CAT graceful degradation                              | A CAT connection failure (serial port in use, rig unplugged, `rigctld` not running, response timeout) SHALL NOT crash the daemon or interrupt the FT8 decode pipeline. On any connection or polling failure the daemon SHALL: log a Warning with the port/host and exception message, set `ICatState.Status` to `Error`, wait 2 seconds, and automatically retry. ALL.TXT logging SHALL fall back to `decodeLog.dialFrequencyMHz` whenever `ICatState.DialFrequencyMHz` is `null`. Config changes saved via `POST /api/v1/config` (e.g. new port, baud rate, or toggling `enabled`) SHALL be applied within two poll intervals without requiring a daemon restart. | Must Have |

### 4.2 User Journeys

#### Journey 1: Routine FT8 monitoring session (v1 happy path)

1. The operator manually tunes their radio to the band and frequency
   they want to monitor (no rig control in v1).
2. The operator launches `openwsfz` in a terminal on their desktop or
   laptop (Windows, Linux, or macOS).
3. The terminal shows a live log stream and a **welcome banner** of
   the form *"OpenWSFZ listening on http://127.0.0.1:8080 &mdash; open this
   in your browser."*
4. The operator opens that URL in a browser on the same machine.
5. The browser lands on the **main page**: waterfall (spectrogram),
   decoded-messages list, basic status indicators. *(Exact panel
   composition is an open architectural detail &mdash; see &sect;8.)*
6. The operator navigates to the **Settings** page from the main page,
   confirms or changes their USB audio device selection, and clicks
   **Save**. The configuration is written to the active config file.
7. The operator returns to the main page. Decoded FT8 messages
   appear in the list as they arrive, each labelled with at minimum
   the decoded text and the audio offset (e.g. *"+1234 Hz"*).
8. Decodes are **display-only**: not persisted to disk, not exported.
   They are ephemeral to the session.
9. The operator closes the browser tab when finished. They stop the
   application with Ctrl-C in the terminal.

#### Journey 2: First-run setup

1. The operator obtains the source from the project's GitHub
   repository (private until public-release readiness).
2. The operator builds from source per the project's README.
3. The operator launches `openwsfz` from a terminal. A minimal default
   configuration file is found on disk (or created in its default
   location).
4. The welcome banner appears as in Journey 1.
5. The operator opens the URL, navigates to Settings, picks an audio
   device, and Saves.
6. From this point the system behaves as Journey 1 on subsequent
   launches.

### 4.3 Integrations

| System / Integration                | Type           | Direction | Notes                                                                                                                            |
|-------------------------------------|----------------|-----------|----------------------------------------------------------------------------------------------------------------------------------|
| Host OS audio subsystem             | Native API     | Inbound   | USB audio capture. Implementation details (WASAPI / ALSA / CoreAudio / PortAudio / etc.) are the architect's call.               |
| Host OS filesystem                  | Native API     | Both      | Read the configuration file at startup; write it on Save. Serve frontend assets read-only.                                       |
| Web browser on the same machine     | HTTP + WebSocket | Both    | Only client of the application in v0.x. Loopback bind only.                                                                      |
| **Future** rig control (v1.0)       | Serial / USB / network CAT | Both | Required for v1.0 (confirmed QSO); architecture must keep this door open.                                                    |
| **Future** PSK Reporter / DX cluster | HTTPS / telnet | Outbound  | Not in v0.x, but typical for HAM tools and worth noting for the architect.                                                       |
| **Future** logbook formats (ADIF, Cabrillo) | File I/O | Outbound | Not in v0.x; deferred with decode persistence.                                                                                |

### 4.4 Data Requirements

The application creates, reads, updates, or deletes the following
data in v0.x:

| Data                       | Lifecycle in v0.x                            | Persistence                                                       |
|----------------------------|----------------------------------------------|-------------------------------------------------------------------|
| Audio input stream         | Read in real time during a session.          | Not persisted.                                                    |
| Configuration              | Read on startup; written when the operator Saves from Settings, toggles the decode start/stop control, or changes the cycle-countdown visibility. | A configuration file at a default or overridden path. Fields include (non-exhaustive): audio device name, `DecodingEnabled`, `ShowCycleCountdown`, `LogLevel`. |
| Decoded FT8 messages       | Created in real time; displayed in the UI.   | **Not persisted**; ephemeral to the session.                       |
| Frontend assets (HTML/CSS/JS) | Read-only when serving the web UI.        | Plain files on disk; user-editable.                               |
| Log output                 | Written to stderr / stdout during a session. | Not persisted by the application itself (operator may redirect).  |

---

## 5. Non-Functional Requirements

| ID      | Category           | Requirement                                                                                                                                                          | Target / Metric                                                                                                                       |
|---------|--------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------|
| NFR-001 | Portability        | The application SHALL build and run on Windows, Linux, and macOS from a single source tree.                                                                          | Three reference platforms: Windows + MSVC, Linux + GCC or Clang, macOS + Clang. x86_64 only in v0.x.                                  |
| NFR-002 | Performance        | The application SHALL provide a perceived user experience comparable to WSJT-X for decode latency, waterfall refresh rate, and resource footprint on modern hardware. | *"Match the WSJT-X user-perceived experience."* No hard numbers specified by the user; architect to set reasonable defaults.          |
| NFR-003 | Real-time decoding | Each 15-second FT8 cycle's worth of audio SHALL be fully decoded before the next cycle ends, on the target hardware.                                                 | Hard real-time deadline. (Inherent property of the FT8 protocol.)                                                                     |
| NFR-004 | Security (v0.x)    | The application SHALL bind only to the loopback interface (`127.0.0.1`) in v0.x.                                                                                     | No external network listener exposed.                                                                                                 |
| NFR-005 | Distribution       | v0.x SHALL be distributed as source only, via the project's GitHub repository.                                                                                       | Tagged source releases. No installer toolchain, no code-signing, no auto-update mechanism in v0.x.                                    |
| NFR-006 | Test coverage      | Every behavioural requirement (functional and non-functional) SHALL have at least one automated test that fails when the behaviour is broken.                        | Coverage-tool reports are informational. The bar is **meaningful behaviour coverage**, not line coverage.                             |
| NFR-007 | Test discipline    | Tests SHALL be respected: a failing test blocks progress (merge / release).                                                                                          | Red builds gate everything downstream. No "merge over a failing test" exceptions.                                                     |
| NFR-008 | Extensibility &mdash; protocol layer | The protocol / decoder layer SHALL be designed as a plugin point so additional modes (FT4, WSPR, etc.) can be added without redesigning audio, scheduling, UI, or logbook. | FT8 is the first plugin.                                                                                                              |
| NFR-009 | Extensibility &mdash; deployment    | The deployment abstraction SHALL not foreclose a future Windows-service deployment mode running alongside the standalone executable.                                  | v0.x is terminal-launched on all platforms; service mode is deferred but must remain reachable without a rewrite.                     |
| NFR-010 | Extensibility &mdash; network       | The bind / authentication abstraction SHALL support a future LAN / remote operation mode without rewrite.                                                              | v0.x only binds to loopback. Future remote operation may bind to LAN / public addresses, add authentication, and add TLS.             |
| NFR-011 | Extensibility &mdash; general       | The architecture SHALL be iterative and easy to extend as requirements arrive.                                                                                         | A new feature should be addable without rewriting unrelated subsystems.                                                               |
| NFR-012 | Accessibility (web UI) | The web UI SHALL use standard sensible web accessibility patterns: semantic HTML, working keyboard navigation, and sufficient contrast in the default dark theme.       | No formal WCAG conformance target for v0.x.                                                                                           |
| NFR-013 | UX competitive bar (aspirational) | The user experience SHALL aim to be one that licensed HAM operators prefer over existing software.                                                                  | Subjective; informs UX, stability, and documentation effort. Not gated on a numeric metric.                                           |
| NFR-014 | Process &mdash; multi-role workflow | The development process SHALL operate across four AI-assisted roles: **ANALYST**, **ARCHITECT**, **DEVELOPER**, **QA**, with requirements cycling between them as needed. | The ANALYST persona's `prompts/ANALYST.md` already exists. Equivalent prompt files for ARCHITECT, DEVELOPER, QA are expected to follow. |
| NFR-015 | Stability          | The application SHALL run for the duration of a normal operating session without crash or memory leak.                                                                | "Normal operating session" left to the architect to quantify; comparable to a WSJT-X session in practice.                             |
| NFR-016 | Test quality &mdash; decoder-correctness gate (G6) | A decoder defect "root cause" SHALL be substantiated by a failing reproducible test over a committed real-signal WAV fixture before a corresponding fix is accepted. Live hardware smoke tests SHALL serve as acceptance/confirmation only and SHALL NOT be the primary diagnostic instrument. The CI workflow SHALL enforce gate **G6** &mdash; the real-signal fixture integration test (FR-029) runs on every push and every pull-request targeting `main`; a failure SHALL block merge. This gate makes it structurally impossible to re-enter a speculative defect loop driven by non-reproducible live observations. | Must Have |
| NFR-018 | Decode parity &mdash; v1.0 release gate | Before v1.0 may be released, the FT8 decoder SHALL achieve a WSJT-X decode parity recovery rate of **≥ 80%** measured against the fixed 42-cycle reference corpus (887 total WSJT-X decodes, 40 m band, real off-air recordings at 7.074 MHz), with a false-positive rate of **≤ 5%**. The measurement methodology is defined by FR-029 and the corpus is maintained locally in `p10-decoder-ground-truth_items/`. Meeting this threshold is a hard prerequisite for v1.0 release; work on other v1.0 features (CAT control, TX) may proceed concurrently, but no v1.0 release tag SHALL be cut until this gate is green. As of v0.15 the recovery rate stands at **69.1%** (613 / 887); reaching ≥ 80% requires PCM-domain waveform subtraction with sub-Hz carrier-frequency estimation, planned as a future change. | Must Have |
| NFR-019 | Brand neutrality | No radio hardware manufacturer name, product model number, or trademarked hardware term SHALL appear in requirements documents, architectural specifications, design documents, source code identifiers (class names, method names, variable names, constants), comments, or user-facing UI text. Radio protocols and command sets SHALL be described by their technical characteristics rather than their brand origin (e.g., "serial CAT `FA;` frequency query" not "[Brand] CAT"). This requirement applies to all project artefacts from first introduction; a brand name that slips through is a merge-blocking defect. **Permitted exceptions:** names of third-party software libraries and tools (e.g., Hamlib, NAudio, LibVLCSharp, WSJT-X) MAY appear in dependency documentation, licence inventory, and behavioural-reference contexts where they identify a specific external dependency or reference implementation. | Must Have |
| NFR-017 | Security &mdash; secrets scan gate (G7) | No secret material (API keys, credentials, private keys, certificate files, or other sensitive data) SHALL be introduced into version control. The CI workflow SHALL enforce gate **G7** &mdash; a `gitleaks` scan of the full commit history on every push and every pull-request targeting `main`; any finding SHALL block merge. The `.gitignore` SHALL include patterns covering certificate and key files (`*.pfx`, `*.p12`, `*.pem`, `*.key`, `*.cer`, `*.crt`), ASP.NET local-environment overrides (`appsettings.Local.json`, `appsettings.*.Local.json`), and ad-hoc secrets files (`secrets.json`). | Must Have |

### 5.1 Compliance & Regulatory

- **Not applicable for v0.x.** Specifically:
  - v0.x does **not transmit**, so FCC / Ofcom / IARU / national
    regulator transmit rules do not bind the application.
  - No persisted user data, no external network calls &mdash; **GDPR /
    HIPAA / PCI-DSS / SOC2 are not applicable.**
- **License compliance** is the one active concern: every dependency
  must be license-compatible with MIT redistribution. **Clean-room**
  implementation from public protocol specifications is mandatory;
  GPL-3.0 source from WSJT-X or JS8Call must not be used as a source
  of implementation, to preserve the project's MIT license.

---

## 6. Technical Constraints

| Constraint                                | Detail                                                                                                                            | Reason                                                                            |
|-------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------|
| License                                   | MIT                                                                                                                               | Project goal: free of restrictions.                                               |
| Disallowed frameworks / toolchains        | **Qt**, **Fortran**, **Node.js** (at build time)                                                                                  | User-stated exclusions.                                                           |
| Preferred implementation language         | **C#**                                                                                                                            | User preference.                                                                  |
| Acceptable fallback language              | **C++**                                                                                                                           | If C# proves impractical for FT8 DSP, cross-platform audio I/O, or packaging.    |
| Implementation provenance                 | Clean-room from public protocol specifications. GPL-3.0 source (WSJT-X / JS8Call) may be a behavioural reference only, never a source of code, algorithms, or assets. | Maintain MIT licensing.                                            |
| Target OSes (v0.x)                        | Windows, Linux, macOS &mdash; **x86_64** only                                                                                     | Cross-platform driver, scoped to desktop x86_64 for v0.x.                        |
| Distribution model (v0.x)                 | Source only, via the project's GitHub repository.                                                                                 | User preference; minimises packaging / code-signing complexity for v0.x.         |
| Bind address (v0.x)                       | `127.0.0.1` loopback only.                                                                                                        | Proof-of-concept simplicity, no auth required.                                    |
| Web frontend                              | Vanilla HTML / CSS / JS. No bundler. No build-time Node toolchain.                                                                | User-stated.                                                                      |
| Frontend layout                           | Own top-level folder with conventional subfolders for HTML, CSS, JS. All files plain on disk and user-editable.                   | User-stated.                                                                      |
| Process model (v0.x)                      | Terminal-launched, foreground.                                                                                                    | User-stated.                                                                      |
| Development workflow                      | Four-role AI-assisted workflow: ANALYST, ARCHITECT, DEVELOPER, QA. Requirements cycle through whichever role needs to weigh in.    | User-stated methodology.                                                          |
| Development tooling                       | **Serena MCP server** SHALL be wired into Claude Code for the **DEVELOPER** role. To be brought into the workflow at a convenient point chosen by the ARCHITECT. | User-stated.                                                                      |

---

## 7. Assumptions

1. **C# is practical** for FT8 DSP at the v0.x performance bar on
   modern x86_64 desktop hardware (decode-only, real-time within the
   15-second FT8 cycle). The ARCHITECT should validate this in design
   and choose C++ as the fallback if invalidated.
2. **Modern x86_64 desktop hardware** has sufficient headroom for
   FT8 decode plus waterfall rendering plus an embedded web server
   in a single process without aggressive optimisation.
3. **Source-only distribution is acceptable** to the licensed-operator
   audience for v0.x. Non-builders self-select out of v0.x.
4. **No bundler is needed** for the vanilla-JS web UI; modern browsers
   handle ES modules and other standards-track features natively.
5. **CSS file edits on disk** are an acceptable UX for theming. No
   in-app theme switcher is required in v0.x.
6. **Three further AI-role prompts will be authored** for ARCHITECT,
   DEVELOPER, and QA, following the same pattern as
   `prompts/ANALYST.md`. These are not yet in the repository.
7. **Public-release readiness is gated on TX + rig control** working,
   not on v0.x. v0.x is an internal milestone reached privately.
8. **The current scaffolding work on the `feature/project-skeleton`
   branch is preliminary**, not approved, and may not survive design
   review by the ARCHITECT.

---

## 8. Open Questions & Risks

| #  | Question / Risk                                                                                                                              | Owner             | Priority      |
|----|-----------------------------------------------------------------------------------------------------------------------------------------------|-------------------|---------------|
| 1  | DSP correctness in a clean-room FT8 decoder &mdash; achieving decode accuracy parity with WSJT-X without reading GPL-3.0 source.              | ARCHITECT         | High          |
| 2  | C# practicality for FT8 real-time DSP and cross-platform audio I/O &mdash; trigger for falling back to C++.                                   | ARCHITECT         | High          |
| 3  | Cross-platform audio capture strategy in C# (PortAudio bindings, OpenAL via OpenTK, native interop to WASAPI/ALSA/CoreAudio, etc.).           | ARCHITECT         | High          |
| 4  | Test-framework and CI selection consistent with NFR-006 ("meaningful behaviour coverage") and NFR-007 (red builds block progress).            | ARCHITECT, QA     | Medium        |
| 5  | Upgrade story for user-edited frontend files (CSS / HTML / JS): overwrite, leave-alone-with-backup, three-way merge.                          | ARCHITECT         | Medium        |
| 6  | Main-page composition beyond "waterfall + decoded messages list" &mdash; confirm exact panels with the user during design.                    | ARCHITECT         | Medium        |
| 7  | What counts as "meaningful" for NFR-006 in practice: define the rubric (per-requirement, per-acceptance-criterion, both).                     | QA                | Medium        |
| 8  | UX competitive bar (NFR-013) is subjective. Architecture / QA should propose a concrete way to evaluate it before release.                    | ARCHITECT, QA     | Medium        |
| 9  | CSS theming granularity &mdash; CSS-custom-property pattern for skin-only changes, full-file edits, or both.                                  | ARCHITECT         | Low           |
| 10 | Future-mode IP/port discovery for headless / LAN / remote deployment (mDNS, fixed port, etc.).                                                | ARCHITECT         | Low (deferred) |
| 11 | Future Windows-service deployment without rewrite of the v0.x lifecycle abstraction.                                                          | ARCHITECT         | Low (deferred) |
| 12 | Repo posture &mdash; the project's GitHub repo exists; confirm public/private state and whether contribution model (issues, PRs) is live yet. | Product Owner     | Low           |
| 13 | The `feature/project-skeleton` scaffolding pre-dates this document; the ARCHITECT should decide what to keep, discard, or revise.             | ARCHITECT         | Medium        |
| 14 | Performance NFR-002 / NFR-003 have no numeric targets; the ARCHITECT should propose concrete budgets aligned with WSJT-X behaviour.            | ARCHITECT         | Medium        |
| 15 | **Serena tooling integration** &mdash; the **Serena MCP server** will be wired into **Claude Code for the DEVELOPER role**. The ARCHITECT should identify a convenient point to bring it into the workflow (e.g. before DEVELOPER work begins, alongside the DEVELOPER prompt under `prompts/`). | ARCHITECT         | Medium        |

---

## 9. Glossary

| Term                | Definition                                                                                                                       |
|---------------------|----------------------------------------------------------------------------------------------------------------------------------|
| ADIF                | Amateur Data Interchange Format &mdash; the standard log file format used to exchange QSO records between logging applications. |
| ARCHITECT           | One of the four AI-assisted roles in this project. Owns system design from this document.                                       |
| ARM64 / aarch64     | 64-bit ARM CPU architecture. Examples: Raspberry Pi 4/5, Banana Pi BPI-R4, Apple Silicon Macs. Out of scope for v0.x.           |
| Analyst             | This role; produces and maintains `REQUIREMENTS.md`.                                                                            |
| BPI-R4              | Banana Pi BPI-R4 8G &mdash; MediaTek MT7988 router-class single-board computer. Stated as the user's future personal deployment target; deferred to v1.0+. |
| CAT                 | Computer-Aided Transceiver &mdash; the protocol family for controlling a radio over a wire.                                     |
| CSS                 | Cascading Style Sheets &mdash; the styling language for the web UI.                                                              |
| Cabrillo            | A contest log file format.                                                                                                       |
| DSP                 | Digital Signal Processing.                                                                                                       |
| DX cluster          | A networked feed of "spots" &mdash; operator reports of stations heard on the air. Not in v0.x.                                  |
| DEVELOPER           | One of the four AI-assisted roles. Owns implementation.                                                                          |
| FT4                 | A faster variant of FT8 with shorter transmission cycles. Out of scope for v0.x.                                                |
| FT8                 | A weak-signal digital amateur-radio mode with 15-second transmission cycles. The only mode in v0.x scope.                        |
| HAM                 | Licensed amateur-radio operator.                                                                                                 |
| K1JT                | Callsign of Joe Taylor, the principal author of the WSJT family of weak-signal modes.                                            |
| MIT License         | The permissive open-source licence selected by the project.                                                                      |
| OpenSpec            | Spec-driven development tool published by Fission-AI. Used during the premature-scaffolding work on `feature/project-skeleton`; status TBD post-design. |
| PSK Reporter        | A crowdsourced propagation reporting service for received signals. Not in v0.x.                                                  |
| PTT                 | Push-To-Talk &mdash; the signal that keys a transmitter. Not in v0.x.                                                            |
| QA                  | One of the four AI-assisted roles. Owns test design and the discipline around NFR-006 / NFR-007.                                |
| QSO                 | A two-way radio contact between licensed operators.                                                                              |
| Rig control         | Software control of a radio (frequency, mode, PTT) via CAT.                                                                      |
| TX                  | Transmit. Required for v1.0; out of scope for v0.x.                                                                             |
| WSJT-X              | The reference application by K1JT et al. for weak-signal modes. GPL-3.0. Behavioural reference only.                            |
| Waterfall           | A scrolling spectrogram of audio energy versus frequency over time. Standard view for weak-signal operating.                     |
| WebSocket / WS      | A standard browser-server bidirectional channel; expected to carry decode events and other live updates from the daemon to the UI. |

---

## 10. Revision History

| Version | Date       | Author                                | Changes                                                |
|---------|------------|---------------------------------------|--------------------------------------------------------|
| 1.0     | 2026-05-17 | Requirements Analyst (AI-assisted)    | Initial draft. Interview conducted across all six phases; defaults accepted for Phase 2 accessibility, Phase 5 timeline, Phase 5 assumptions, and Phase 6 risks. |
| 1.1     | 2026-05-18 | Requirements Analyst (AI-assisted)    | Added development-tooling constraint in &sect;6 &mdash; **Serena MCP server wired into Claude Code for the DEVELOPER role** &mdash; and open question #15 in &sect;8 asking the ARCHITECT to choose a convenient integration point. |
| 1.2     | 2026-05-22 | QA (AI-assisted)                      | Added **FR-017** (decode start/stop control) following operator observation that there is no way to pause decoding without changing the audio device or restarting the application. Updated &sect;4.4 data requirements to note that decode state is now persisted. |
| 1.3     | 2026-05-22 | QA (AI-assisted)                      | Added **FR-018** (cycle countdown timer, testing aid) — countdown to the next 15-second UTC cycle boundary with an 8-second GO window, controlled by `AppConfig.ShowCycleCountdown` (default: `false`) and exposed via a Settings checkbox. Updated &sect;4.4 configuration field list. |
| 1.4     | 2026-05-22 | QA (AI-assisted)                      | Added **FR-019** (configurable application logging) — seven standard `Microsoft.Extensions.Logging.LogLevel` levels (Trace / Debug / Information / Warning / Error / Critical / None), output to stderr, format `[OpenWSFZ] YYYY-MM-DD HH:MM:SS [LEVEL]  Component — message`, persisted as `AppConfig.LogLevel` (default `"Information"`), exposed via Settings dropdown. Updated &sect;4.4 configuration field list. |
| 1.5     | 2026-05-22 | QA (AI-assisted)                      | Added **FR-020** (audio activity indicator in heartbeat) — heartbeat and status WebSocket frames carry `audioActive: bool`; true if any sample with \|value\| &gt; 1×10⁻⁶ was received since the previous heartbeat; resets each 5-second heartbeat interval. UI must surface the indicator in the status area. |
| 1.6     | 2026-05-23 | QA (AI-assisted)                      | Added **FR-021** (capture stop logging) — every capture session termination SHALL produce a log entry at the appropriate level: Information for operator-stopped, Warning for unexpected end (driver stopped without being asked), Error for exception-driven termination with full stack trace. A silent stop is a violation. |
| 1.7     | 2026-05-25 | QA (AI-assisted)                      | Added **FR-022** (file logging sink), **FR-023** (log rotation), **FR-024** (log file retention), **FR-025** (audio device friendly name display). Amended **FR-019** to remove the "exclusively to stderr" constraint and update the log-level-change timing to "immediately on settings save". |
| 1.8     | 2026-05-28 | QA (AI-assisted)                      | Added **FR-026** (FT8 decode throughput — already implemented in p8 tests, now formally recorded), **FR-027** (dial frequency configuration), **FR-028** (WSJT-X compatible ALL.TXT decode log). |
| 1.9     | 2026-05-29 | ARCHITECT (AI-assisted)               | Added **FR-029** (reproducible real-signal decode verification — WAV corpus, WAV→PCM reader, replay harness, real-signal fixture integration test as the authoritative oracle) and **NFR-016** (decoder-correctness CI gate G6 — reproducible-evidence rule, real-signal fixture test gates every PR). These requirements are the output of `RECOVERY_PLAN.md` Phase 1 and are implemented by `p10-decoder-ground-truth`. |
| 1.10    | 2026-05-31 | QA (AI-assisted)                      | Updated versioning language throughout. The project version scheme is now formalised: **v0.x** covers all work prior to a confirmed QSO; **v1.0** is reached when the software can make a confirmed two-way contact (RX + CAT control + TX); each user-facing feature shipped increments the minor version. All prior references to "v1" (the receive-only proof of concept) updated to "v0.x"; all references to "v2+" updated to "v1.0+". Current release tagged **v0.11**. |
| 1.11    | 2026-05-31 | QA (AI-assisted)                      | Added **FR-030** (logging configuration hot-reload) — all logging settings changes (console level, file sink enable/disable, file log level, log directory, rotation schedule, max files) SHALL take effect immediately on save without requiring a restart. Added following operator observation that the current implementation requires a restart for log settings to apply. |
| 1.14    | 2026-06-02 | QA (AI-assisted)                      | Added **NFR-019** (brand neutrality): radio hardware manufacturer names, product model numbers, and trademarked hardware terms are prohibited in all project artefacts; violation is merge-blocking. Third-party software library and tool names remain permitted in dependency and reference contexts. |
| 1.13    | 2026-06-02 | QA (AI-assisted)                      | Added **NFR-018** (decode parity — v1.0 release gate): FT8 decoder MUST achieve ≥ 80% recovery rate and ≤ 5% false-positive rate on the reference corpus before v1.0 may be released. Added **NFR-017** (secrets scan gate G7): `gitleaks` scan on every push and PR; `.gitignore` hardened with certificate/key and local-settings patterns. Both requirements are hard v1.0 prerequisites; NFR-018 allows concurrent CAT control and TX work. |
