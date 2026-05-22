# OpenWSFZ &mdash; Requirements Document

**Version:** 1.1
**Date:** 2026-05-18
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
**v1 is a tightly scoped proof of concept: FT8 receive-only decoding,
loopback-only web UI, single operator, source-only distribution.**
Transmit, rig control, the wider mode menu, remote / LAN operation,
and headless deployment are all explicitly deferred to subsequent
versions on the way to a public release.

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

**In Scope (v1)**

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

**Out of Scope (v1, deferred to v2+)**

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
| Primary user (v1)             | The project author                    | Personal use, end-to-end testing on their own gear.                                       |
| Aspirational user community   | Licensed amateur-radio operators (HAMs) worldwide | Future adoption after the project goes public.                                |
| Future contributors           | TBD post-public-release               | Source contributions, issue reports, peer review.                                         |
| ANALYST role (AI-assisted)    | See `prompts/ANALYST.md`              | Requirements gathering and documentation.                                                 |
| ARCHITECT role (AI-assisted)  | Prompt to be written                  | System design from this document.                                                         |
| DEVELOPER role (AI-assisted)  | Prompt to be written                  | Implementation from architectural artifacts.                                              |
| QA role (AI-assisted)         | Prompt to be written                  | Test design, coverage discipline, gating of merges on green builds.                       |

---

## 3. User Personas

Only one persona is in scope for v1.

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
  - Comfortable with building from source &mdash; v1 ships source-only.
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
| FR-019 | Configurable application logging                      | The application SHALL implement structured logging using the .NET `Microsoft.Extensions.Logging` infrastructure. The seven standard log levels defined by `Microsoft.Extensions.Logging.LogLevel` SHALL be supported: **Trace**, **Debug**, **Information**, **Warning**, **Error**, **Critical**, **None**. The active minimum level SHALL be selectable from a dropdown on the Settings page and persisted to the configuration file (`AppConfig.LogLevel`, default: `"Information"`). Setting a minimum level shows that level and all more severe levels (e.g. `Warning` shows Warning, Error, and Critical); `None` suppresses all output. The levels map to operational intent as follows — **Trace**: internal loop counters, per-sample values, raw Goertzel energies; **Debug**: framer offsets, Costas scores, LLR magnitudes, time-domain sweep positions; **Information**: pipeline start/stop, device selection, decode cycle results, configuration changes; **Warning**: recoverable anomalies such as buffer overflows, slow decode cycles, or device reconnects; **Error**: operation failures that do not terminate the application (e.g. a single cycle decode error); **Critical**: unrecoverable failures requiring operator intervention; **None**: all output suppressed. Log output SHALL be written exclusively to the application's standard error stream in a consistent single-line format: `[OpenWSFZ] YYYY-MM-DD HH:MM:SS [LEVEL]  ComponentName — message`, where `LEVEL` is the four-character abbreviation used by the .NET console logger (`trce`, `dbug`, `info`, `warn`, `fail`, `crit`). Every component of the application — audio capture pipeline, FT8 decode pipeline (CycleFramer, Ft8Decoder, symbol extraction, Costas synchronisation, LDPC), WebSocket event bus, HTTP API, and configuration store — SHALL emit log entries at the appropriate level at key operational points sufficient to diagnose the application state without a debugger attached. The log level setting SHALL take effect on the next application start. | Must Have   |

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
| Web browser on the same machine     | HTTP + WebSocket | Both    | Only client of the application in v1. Loopback bind only.                                                                        |
| **Future** rig control (v2+)        | Serial / USB / network CAT | Both | Explicitly deferred; architecture must keep this door open.                                                                  |
| **Future** PSK Reporter / DX cluster | HTTPS / telnet | Outbound  | Not in v1, but typical for HAM tools and worth noting for the architect.                                                         |
| **Future** logbook formats (ADIF, Cabrillo) | File I/O | Outbound | Not in v1; deferred with decode persistence.                                                                                  |

### 4.4 Data Requirements

The application creates, reads, updates, or deletes the following
data in v1:

| Data                       | Lifecycle in v1                              | Persistence                                                       |
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
| NFR-001 | Portability        | The application SHALL build and run on Windows, Linux, and macOS from a single source tree.                                                                          | Three reference platforms: Windows + MSVC, Linux + GCC or Clang, macOS + Clang. x86_64 only in v1.                                    |
| NFR-002 | Performance        | The application SHALL provide a perceived user experience comparable to WSJT-X for decode latency, waterfall refresh rate, and resource footprint on modern hardware. | *"Match the WSJT-X user-perceived experience."* No hard numbers specified by the user; architect to set reasonable defaults.          |
| NFR-003 | Real-time decoding | Each 15-second FT8 cycle's worth of audio SHALL be fully decoded before the next cycle ends, on the target hardware.                                                 | Hard real-time deadline. (Inherent property of the FT8 protocol.)                                                                     |
| NFR-004 | Security (v1)      | The application SHALL bind only to the loopback interface (`127.0.0.1`) in v1.                                                                                       | No external network listener exposed.                                                                                                 |
| NFR-005 | Distribution       | v1 SHALL be distributed as source only, via the project's GitHub repository.                                                                                         | Tagged source releases. No installer toolchain, no code-signing, no auto-update mechanism in v1.                                      |
| NFR-006 | Test coverage      | Every behavioural requirement (functional and non-functional) SHALL have at least one automated test that fails when the behaviour is broken.                        | Coverage-tool reports are informational. The bar is **meaningful behaviour coverage**, not line coverage.                             |
| NFR-007 | Test discipline    | Tests SHALL be respected: a failing test blocks progress (merge / release).                                                                                          | Red builds gate everything downstream. No "merge over a failing test" exceptions.                                                     |
| NFR-008 | Extensibility &mdash; protocol layer | The protocol / decoder layer SHALL be designed as a plugin point so additional modes (FT4, WSPR, etc.) can be added without redesigning audio, scheduling, UI, or logbook. | FT8 is the first plugin.                                                                                                              |
| NFR-009 | Extensibility &mdash; deployment    | The deployment abstraction SHALL not foreclose a future Windows-service deployment mode running alongside the standalone executable.                                  | v1 is terminal-launched on all platforms; service mode is deferred but must remain reachable without a rewrite.                       |
| NFR-010 | Extensibility &mdash; network       | The bind / authentication abstraction SHALL support a future LAN / remote operation mode without rewrite.                                                              | v1 only binds to loopback. Future remote operation may bind to LAN / public addresses, add authentication, and add TLS.               |
| NFR-011 | Extensibility &mdash; general       | The architecture SHALL be iterative and easy to extend as requirements arrive.                                                                                         | A new feature should be addable without rewriting unrelated subsystems.                                                               |
| NFR-012 | Accessibility (web UI) | The web UI SHALL use standard sensible web accessibility patterns: semantic HTML, working keyboard navigation, and sufficient contrast in the default dark theme.       | No formal WCAG conformance target for v1.                                                                                             |
| NFR-013 | UX competitive bar (aspirational) | The user experience SHALL aim to be one that licensed HAM operators prefer over existing software.                                                                  | Subjective; informs UX, stability, and documentation effort. Not gated on a numeric metric.                                           |
| NFR-014 | Process &mdash; multi-role workflow | The development process SHALL operate across four AI-assisted roles: **ANALYST**, **ARCHITECT**, **DEVELOPER**, **QA**, with requirements cycling between them as needed. | The ANALYST persona's `prompts/ANALYST.md` already exists. Equivalent prompt files for ARCHITECT, DEVELOPER, QA are expected to follow. |
| NFR-015 | Stability          | The application SHALL run for the duration of a normal operating session without crash or memory leak.                                                                | "Normal operating session" left to the architect to quantify; comparable to a WSJT-X session in practice.                             |

### 5.1 Compliance & Regulatory

- **Not applicable for v1.** Specifically:
  - v1 does **not transmit**, so FCC / Ofcom / IARU / national
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
| Target OSes (v1)                          | Windows, Linux, macOS &mdash; **x86_64** only                                                                                     | Cross-platform driver, scoped to desktop x86_64 for v1.                          |
| Distribution model (v1)                   | Source only, via the project's GitHub repository.                                                                                 | User preference; minimises packaging / code-signing complexity for v1.           |
| Bind address (v1)                         | `127.0.0.1` loopback only.                                                                                                        | Proof-of-concept simplicity, no auth required.                                    |
| Web frontend                              | Vanilla HTML / CSS / JS. No bundler. No build-time Node toolchain.                                                                | User-stated.                                                                      |
| Frontend layout                           | Own top-level folder with conventional subfolders for HTML, CSS, JS. All files plain on disk and user-editable.                   | User-stated.                                                                      |
| Process model (v1)                        | Terminal-launched, foreground.                                                                                                    | User-stated.                                                                      |
| Development workflow                      | Four-role AI-assisted workflow: ANALYST, ARCHITECT, DEVELOPER, QA. Requirements cycle through whichever role needs to weigh in.    | User-stated methodology.                                                          |
| Development tooling                       | **Serena MCP server** SHALL be wired into Claude Code for the **DEVELOPER** role. To be brought into the workflow at a convenient point chosen by the ARCHITECT. | User-stated.                                                                      |

---

## 7. Assumptions

1. **C# is practical** for FT8 DSP at the v1 performance bar on
   modern x86_64 desktop hardware (decode-only, real-time within the
   15-second FT8 cycle). The ARCHITECT should validate this in design
   and choose C++ as the fallback if invalidated.
2. **Modern x86_64 desktop hardware** has sufficient headroom for
   FT8 decode plus waterfall rendering plus an embedded web server
   in a single process without aggressive optimisation.
3. **Source-only distribution is acceptable** to the licensed-operator
   audience for v1. Non-builders self-select out of v1.
4. **No bundler is needed** for the vanilla-JS web UI; modern browsers
   handle ES modules and other standards-track features natively.
5. **CSS file edits on disk** are an acceptable UX for theming. No
   in-app theme switcher is required in v1.
6. **Three further AI-role prompts will be authored** for ARCHITECT,
   DEVELOPER, and QA, following the same pattern as
   `prompts/ANALYST.md`. These are not yet in the repository.
7. **Public-release readiness is gated on TX + rig control** working,
   not on v1. v1 is an internal milestone reached privately.
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
| 11 | Future Windows-service deployment without rewrite of the v1 lifecycle abstraction.                                                            | ARCHITECT         | Low (deferred) |
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
| ARM64 / aarch64     | 64-bit ARM CPU architecture. Examples: Raspberry Pi 4/5, Banana Pi BPI-R4, Apple Silicon Macs. Out of scope for v1.             |
| Analyst             | This role; produces and maintains `REQUIREMENTS.md`.                                                                            |
| BPI-R4              | Banana Pi BPI-R4 8G &mdash; MediaTek MT7988 router-class single-board computer. Stated as the user's future personal deployment target; deferred to v2+. |
| CAT                 | Computer-Aided Transceiver &mdash; the protocol family for controlling a radio over a wire.                                     |
| CSS                 | Cascading Style Sheets &mdash; the styling language for the web UI.                                                              |
| Cabrillo            | A contest log file format.                                                                                                       |
| DSP                 | Digital Signal Processing.                                                                                                       |
| DX cluster          | A networked feed of "spots" &mdash; operator reports of stations heard on the air. Not in v1.                                    |
| DEVELOPER           | One of the four AI-assisted roles. Owns implementation.                                                                          |
| FT4                 | A faster variant of FT8 with shorter transmission cycles. Out of scope for v1.                                                  |
| FT8                 | A weak-signal digital amateur-radio mode with 15-second transmission cycles. The only mode in v1 scope.                          |
| HAM                 | Licensed amateur-radio operator.                                                                                                 |
| K1JT                | Callsign of Joe Taylor, the principal author of the WSJT family of weak-signal modes.                                            |
| MIT License         | The permissive open-source licence selected by the project.                                                                      |
| OpenSpec            | Spec-driven development tool published by Fission-AI. Used during the premature-scaffolding work on `feature/project-skeleton`; status TBD post-design. |
| PSK Reporter        | A crowdsourced propagation reporting service for received signals. Not in v1.                                                    |
| PTT                 | Push-To-Talk &mdash; the signal that keys a transmitter. Not in v1.                                                              |
| QA                  | One of the four AI-assisted roles. Owns test design and the discipline around NFR-006 / NFR-007.                                |
| QSO                 | A two-way radio contact between licensed operators.                                                                              |
| Rig control         | Software control of a radio (frequency, mode, PTT) via CAT.                                                                      |
| TX                  | Transmit. Out of scope for v1.                                                                                                   |
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
