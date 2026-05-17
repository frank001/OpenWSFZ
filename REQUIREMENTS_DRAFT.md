# OpenWSFZ &mdash; Requirements Interview State

**Status:** In progress &mdash; Phase 4 essentially complete; Phase 5 starting.
**Last updated:** 2026-05-17
**Role of the AI assistant:** Requirements Analyst &mdash; see `prompts/ANALYST.md`.

> **This is NOT the final REQUIREMENTS.md.** It is a working scratch file
> so the interview can resume across sessions without losing context.
> The final `REQUIREMENTS.md` will only be produced after **all six phases
> are covered and the user explicitly confirms the interview is complete.**
> No implementation work should be derived from this draft.

---

## How to resume in a future session

1. The AI assistant should read `prompts/ANALYST.md` first to adopt the
   Requirements Analyst role (one focused question at a time, no document
   until the user confirms completion).
2. Then read this file end-to-end.
3. Confirm with the user that the captured material below is still
   accurate &mdash; offer to revise any item.
4. Continue the interview from the **Pending question** section at the
   bottom of this file.

---

## Captured so far

### Phase 1 &mdash; Project Overview

- **Name:** OpenWSFZ.
- **What it is:** An open-source, MIT-licensed alternative to the WSJT-X
  weak-signal amateur-radio application family, with the user interface
  delivered as a web page rather than a native desktop app.
- **Type:** Greenfield. Clean-room from public protocol specifications
  (K1JT et al.). The GPL-3.0 WSJT-X and JS8Call source trees may be
  consulted as behavioural references but **must not** be used as a
  source of implementation &mdash; that would force OpenWSFZ to GPL-3.0.
- **Primary motivations (co-equal):**
  1. Desire for a **web-controlled UI** instead of a desktop Qt app.
  2. **Cross-platform reach** from a single source tree (Windows,
     Linux, macOS).
- **Stakeholders:** Solo developer for v1. Aspirational community
  audience after release ("see if we can pull it off and make it
  available to anyone who wants to toy with it").

### Phase 2 &mdash; Users & Personas

- **Primary audience:** Not a specific slice. The framing is
  *"build the thing and see who shows up."* This pushes design toward
  *easy to try* and *broad appeal* over feature-completeness for any
  one slice.
- **User profile:** **Licensed radio operators.** Assumed technically
  competent (*"they know what they're doing"*) &mdash; but the UX still
  has to be friendly enough not to fight them.
- **Concurrency model:** **Single operator per install** in v1. Multi-
  operator is "maybe later." Architect should keep abstractions clean
  enough that a future auth layer is not a rewrite, but should not
  build auth, roles, or per-user state for v1.

### Phase 3 &mdash; Functional Requirements

**Configuration & persistence**
- Web UI lists **USB audio devices** so the operator can pick the
  capture device(s).
- Selected settings persist to a **configuration file**.
- The config-file path is **configurable** &mdash; default location plus a
  CLI flag / env override to point at a different file.
- A **minimal default config** ships with the app so a fresh install
  is in a known state on first run.

**Web UI presentation**
- **Dark theme by default.**
- Theming is done by **editing the CSS files on disk** (the chosen
  option from a/b/c). No in-app theme switcher in v1.
- **Frontend lives in its own top-level folder**, with conventional
  subfolders for HTML, CSS, and JS. Architect picks the exact names.
- All frontend files are **user-editable on disk** so a tinkerer can
  rework the UI without rebuilding the application.

**Operating modes (v1 scope)**
- **FT8 only** for v1.
- Other WSJT-X modes (FT4, JT9, JT65, WSPR, Q65, MSK144, Echo) are
  deferred. The user's reasoning: *"if FT8 is covered, other decodings
  should be trivial."* &mdash; this is the basis for the **derived NFR**
  on protocol-plugin architecture (see below).

**Decode / transmit scope (v1)**
- **Decode only.** Receive monitor.
- **No transmit, no QSO state machine, no audio output, no PTT** in v1.

**Rig control**
- **Out of scope for v1.** The operator sets the radio's mode and
  frequency manually. The application deals only in audio offsets
  (e.g. *"+1234 Hz"*) &mdash; not absolute frequencies.
- Future rig-control support (CAT via serial / USB / network) is
  noted under deferred features.

**Process model (v1)**
- **Terminal-launched, foreground app** on all three platforms.
- The terminal shows a live log stream plus a **welcome banner**
  stating the IP and port the web UI is reachable on, e.g.
  *"OpenWSFZ listening on http://127.0.0.1:8080 &mdash; open this in your
  browser."*

**Critical user journey (happy path)**

1. Operator launches `openwsfz` in a terminal.
2. Terminal prints log lines and a welcome banner with IP + port.
3. Operator opens that URL in a browser.
4. Lands on the **main page**: waterfall (spectrogram), decoded
   messages list, status indicators. Exact composition is an **open
   question for the architect**.
5. Operator can navigate to a **Settings page** from the main page
   (affordance &mdash; gear icon, menu, tab &mdash; is the architect's call).
   The Settings page contains everything configurable, with a **Save**
   action that writes to the configuration file.
6. Decodes appear in the on-screen list as they arrive. **In v1 they
   are display-only** &mdash; ephemeral, not persisted, not exported, no
   log file. Persistence and export are deferred to a later version.

**Build sequencing (development discipline)**
- The architect should **prioritise the web UI** so the application's
  functionality is testable as it is developed. Each backend slice
  must light up something in the UI.

**Strict UI visibility rule** (also recorded in the user's memory file)
- Any control visible in the web UI **must** be fully implemented and
  bound to a working backend.
- **No "coming soon" placeholders. No greyed-out future buttons.**
- Features ship UI-and-backend together or not at all.

### Phase 4 &mdash; Non-Functional Requirements

**Network exposure (v1)**
- **Loopback only** (`127.0.0.1`). The browser must run on the same
  machine as the daemon.
- No authentication in v1 (single operator + loopback &rArr; threat
  model is whoever has a local shell).
- Remote / LAN operation is **explicitly on the roadmap for a future
  version** and is the user's longer-term personal use case.

**Target hardware (v1)**
- **Modern x86_64 desktop or laptop** running Windows, Linux, or macOS.
- No need to optimise for sub-Pi-class hardware.
- ARM64, Raspberry Pi-class, and the user's personal **Banana Pi
  BPI-R4 8G** deployment are **all deferred to v2** (resolved by
  trading off against loopback-only &mdash; see "Note on requirement
  conflict resolved" below).

**Performance bar (v1)**
- *"Match the WSJT-X user-perceived experience"* &mdash; no hard numbers
  from the requirements phase.
- Architect to define reasonable defaults for decode latency,
  waterfall refresh, and CPU/RAM footprint that align with the WSJT-X
  reference.
- The hard real-time constraint of FT8 (each 15-second cycle must be
  fully decoded before the next begins) is an inherent property of the
  protocol and applies regardless.

**Distribution (v1)**
- **Source-only.** Tagged releases on GitHub; users build from source
  themselves.
- No native installers, no code-signing, no auto-update mechanism in
  v1.
- Pre-built binaries can be added later if the project gathers
  traction; not a v1 commitment.

**Availability, scalability, compliance, data retention**
- Not explicitly addressed by the user; effectively **N/A for v1**:
  - Single-user desktop app, not a service &mdash; no SLA.
  - No persisted data &mdash; no retention obligations.
  - No external network calls &mdash; no privacy posture beyond what the
    OS provides for the audio device.
  - No regulated data &mdash; GDPR / HIPAA / PCI-DSS not applicable.

**Note on requirement conflict resolved during interview**
- The user initially named the BPI-R4 8G as their personal
  deployment target. That conflicts with v1 being loopback-only,
  because the BPI-R4 is headless and reached over SSH. **Resolution:
  the BPI-R4 / headless / remote case is deferred to v2 in full.** v1
  is desktop / laptop only.

### Derived NFRs for the architect

These are constraints inferred from things the user said, that the
architect must respect even though v1 doesn't directly build them:

1. **Protocol-plugin architecture.** The protocol / decoder layer
   must be designed as a plugin point so additional modes (FT4, WSPR,
   etc.) can be added without redesigning audio I/O, scheduling, UI,
   or logbook. FT8 is the first plugin. *Basis: user's reasoning
   when scoping v1 to FT8 only ("if FT8 is covered, other decodings
   should be trivial").*
2. **Deployment-model flexibility.** The deployment abstraction must
   not foreclose a future **Windows service mode** running alongside
   the standalone executable. v1 is terminal-launched everywhere;
   service mode is deferred but must remain reachable without a
   rewrite. *Basis: user named this requirement explicitly.*
3. **Network-exposure abstraction.** The bind / authentication
   abstraction must support a future LAN / remote operation mode
   without rewrite. v1 only binds to loopback. *Basis: user named
   remote operation as a future feature and as their longer-term
   personal use case.*

### Features explicitly deferred to v2+

This is the consolidated "not in v1" list:

- Multi-operator support, authentication, per-user state.
- Transmit (modulation, audio output, PTT, QSO state machine).
- Non-FT8 modes (FT4, JT9, JT65, WSPR, Q65, MSK144, Echo).
- Decode persistence (log files) and export (ADIF, CSV, etc.).
- Rig control / CAT integration (serial, USB, network).
- Remote / LAN operation: server bind to non-loopback addresses,
  authentication, TLS.
- Windows-service deployment mode.
- ARM64 builds, Raspberry Pi-class hardware, Banana Pi BPI-R4
  deployment, any headless deployment.
- Native installers (`.msi`, `.pkg`, `.deb`, `.rpm`) and code-signing
  certificates.
- Pre-built binary distribution.
- Auto-update / in-app update checking.

---

## Open questions / items flagged for the architect

1. **Upgrade story for user-edited frontend files** &mdash; when the
   project ships a new version, how are user edits to the HTML / CSS
   / JS handled? Overwrite, leave-alone-with-backup, three-way merge?
2. **Main-page composition** &mdash; beyond *"waterfall and what not"*,
   confirm during design the exact set of panels: decoded messages
   list, status indicators, audio-offset display, band selector
   (if any, even though no rig control), etc.
3. **Windows service mode** &mdash; deferred for v1 but explicitly on the
   roadmap. Architecture must keep the door open.
4. **IP/port discovery for headless deployments** &mdash; the v1 model
   prints the URL to the terminal, which assumes terminal access.
   Future headless / Pi / BPI-R4 deployments will need an alternative
   discovery story (mDNS, fixed port + documented, etc.).
5. **CSS theming granularity** &mdash; will theming use a variables-only
   pattern (CSS custom properties) so an operator can re-skin without
   touching layout, or is full CSS rewrite the expectation? The user's
   phrasing favours full-file edits, but worth confirming during
   design.

---

## Phases still to cover

- **Phase 4 &mdash; close-out.** Substantively complete. May reopen if
  performance / availability concerns surface later.
- **Phase 5 &mdash; Constraints & Assumptions.** Partially known
  (MIT-only, no Qt/Fortran/Node, cross-platform x86_64, source-only).
  Still to capture: any preferred or excluded **implementation
  language**, timeline / deadline expectations, any budget or tooling
  constraints, and the user's own assumptions that might turn out to
  be wrong.
- **Phase 6 &mdash; Open Questions & Risks.** Untouched as a dedicated
  pass. Items above will feed in, but the user needs to be asked
  directly what *they* think is risky or uncertain.

---

## Pending question (resume here)

The next question to ask the user, verbatim:

> **What constraints (if any) does the architect have on the
> implementation language?**
>
> You've already excluded **Qt, Fortran, and Node.js** by name.
> Within MIT-compatible language ecosystems, the field is still wide:
>
> - **C++** &mdash; closest to the WSJT-X reference and most common in
>   audio/DSP work.
> - **Rust** &mdash; safety and concurrency story; strong cross-compile
>   tooling; growing DSP ecosystem.
> - **Go** &mdash; easy cross-compile, good HTTP/WS stdlib, weaker DSP
>   ecosystem.
> - **C (C99/C11)** &mdash; smallest binary, matches the style of existing
>   MIT FT8 reference implementations such as `kgoba/ft8_lib`.
> - **Zig, Nim, Crystal, etc.** &mdash; less common but plausible.
>
> Do you have a preferred or required language for v1, a list of
> languages that are off-limits, or is the choice entirely the
> architect's within "MIT-compatible, no Qt/Fortran/Node"?

---

## Note on premature implementation work

Before the analyst phase began, scaffolding work was done on a feature
branch (`feature/project-skeleton`):

- Local git repo with `main` (MIT LICENSE, README, `.gitignore`,
  `prompts/`) and a feature branch containing CMake / Drogon / web
  placeholder / OpenSpec change proposal / GitHub Actions workflow.
- An OpenSpec change `openspec/changes/add-project-skeleton/` with
  proposal, design, capability specs, and tasks.
- A partial Windows build that got stuck on a Drogon &rarr; system-zlib
  dependency.

**This work is preliminary and not approved.** Decisions baked in
(C++17 + Drogon, port 8080, WebSocket envelope shape, FetchContent
deps, etc.) were made before the requirements were gathered and may
not survive review. The architect should not act on any of it until
`REQUIREMENTS.md` exists and has been approved.

The branch can either be kept for reference, discarded, or partially
salvaged once the requirements document is final. **It should not be
pushed to a public GitHub repo before that decision is made** &mdash;
publishing it implicitly signals that the baked-in decisions are
committed.
