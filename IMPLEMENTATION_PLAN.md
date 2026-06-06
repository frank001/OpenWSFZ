# OpenWSFZ &mdash; Implementation Plan

**Version:** 1.0
**Date:** 2026-05-18
**Status:** Draft &mdash; pending Product Owner approval
**Author:** ARCHITECT role (AI-assisted)
**Source documents:**
* [`REQUIREMENTS.md`](./REQUIREMENTS.md) v1.1
* [`TECHNICAL_SPEC.md`](./TECHNICAL_SPEC.md) v1.0
* [`TESTING_STRATEGY.md`](./TESTING_STRATEGY.md) v1.0

> **Reading order for someone new to the project**
> 1. `REQUIREMENTS.md` &mdash; what we're building and why.
> 2. `TECHNICAL_SPEC.md` &mdash; how it is structured.
> 3. `TESTING_STRATEGY.md` &mdash; what "tested" means.
> 4. **This document** &mdash; the phased path to v1 and the immediate next actions.

---

## 1. Purpose

This document turns the technical specification into an actionable sequence of phases that the DEVELOPER role can execute, with QA gating each step. It is the final architecture-phase artefact &mdash; once approved, no further architecture work is needed before implementation begins, beyond per-phase OpenSpec change proposals.

---

## 2. Phasing Philosophy

Three rules shape the plan:

1. **Each phase ends with a working, testable, demoable artefact.** No "we'll wire it up at the end" phases.
2. **Risky and foundational work goes early.** CI gates land before any feature; the FT8 decoder (the highest-risk component) lands in the middle of v1, not at the end.
3. **One phase = one OpenSpec change proposal.** This replaces the deleted `add-project-skeleton` proposal with a sequence of smaller, reviewable changes, each scoped to fit a single proposal / branch / PR.

---

## 3. Phases at a glance

| # | Phase | Deliverable artefact | Closes requirements |
|---|---|---|---|
| **0** | Foundation | Empty solution + CI gates + role prompts + Serena MCP | (gates only) |
| **1** | Walking skeleton | Daemon boots, serves a placeholder page, opens WS, banner emits | FR-002, FR-007, NFR-004 |
| **2** | Configuration &amp; Settings | TOML config end-to-end with a Settings page round-trip | FR-004, FR-005, FR-006, FR-010, FR-011 |
| **3** | Audio capture | USB devices enumerable; selected device captures into a ring buffer | FR-003 |
| **4** | FT8 decoder | Live decoded messages from real audio (or fixtures) | FR-001, FR-009 |
| **5** | Waterfall | Live spectrogram on the main page | FR-008 |
| **6** | Theme &amp; UI polish | Dark theme + theming via CSS variables + strict UI visibility gate green | FR-012, FR-013, FR-014, FR-015, FR-016, NFR-012 |
| **7** | Hardening | Performance budgets met; soak passes; release candidate cut | NFR-001, NFR-002, NFR-003, NFR-005, NFR-015 |
| **8** | v1 release | `v1.0.0` tagged and released on GitHub | All remaining v1 requirements |

Detailed phase content follows in &sect;5.

---

## 4. Milestones

A milestone is a moment with external significance &mdash; worth tagging in git, demoing, or announcing. Not every phase boundary is a milestone.

| ID | Milestone | At end of phase | Why it matters |
|---|---|---|---|
| **M1** | Foundation complete | P0 | CI gates active; every later phase is enforceable |
| **M2** | End-to-end pipe | P1 | First time the daemon serves a browser; smallest possible E2E demo |
| **M3** | First FT8 decode | P4 | The single most important moment in v1; OpenWSFZ actually decodes FT8 |
| **M4** | First waterfall | P5 | The UI now looks and feels like radio software |
| **M5** | `v1.0.0-rc1` | P7 | First release candidate; all gates green; performance budgets met |
| **M6** | `v1.0.0` | P8 | The v1 target |

---

## 5. Phase Detail

Each phase below uses the same template:

* **Goal** &mdash; one sentence.
* **Deliverable artefacts** &mdash; what lands in the repo.
* **Requirements covered.**
* **Exit gate** &mdash; the boolean check that says "phase is done."

### 5.0 Phase 0 &mdash; Foundation

**Goal:** establish the build, the CI gates, the role prompts, and the tooling that every later phase will be judged by, before any behaviour is written.

**Deliverable artefacts:**
* `OpenWSFZ.sln` and `global.json` pinning the .NET 10 SDK feature band.
* `Directory.Packages.props` for centralised NuGet version pinning.
* `OpenWSFZ.Abstractions` project (empty class library; placeholders for the interfaces named in `TECHNICAL_SPEC` &sect;3.1).
* `prompts/DEVELOPER.md` &mdash; the DEVELOPER role prompt.
* `prompts/QA.md` &mdash; the QA role prompt.
* `tools/TraceabilityCheck/` &mdash; first-party console tool enforcing the rubric in `TESTING_STRATEGY` &sect;3 criteria C1+C4.
* `tools/LicenseInventoryCheck/` &mdash; first-party console tool enforcing the licence policy in `TECHNICAL_SPEC` &sect;7.1.
* `.github/workflows/ci.yml` &mdash; matrix build (Windows / Linux / macOS) plus Linux-only traceability and licence gates.
* GitHub branch-protection rules on `main` (G1&ndash;G6 in `TESTING_STRATEGY` &sect;7).
* Serena MCP server wired into Claude Code alongside the DEVELOPER prompt.

**Requirements covered:** none directly. This phase sets up the gates everything else is judged by.

**Exit gate:**
* Empty solution builds green on all three OSes.
* CI workflow runs to completion and reports green.
* Traceability check passes against an empty test suite **and** against `REQUIREMENTS.md` (the latter check is expected to report "all IDs unmapped" but should not error; it surfaces the work to be done in later phases).
* Licence inventory check passes against the empty solution.

### 5.1 Phase 1 &mdash; Walking skeleton

**Goal:** the daemon boots, prints its welcome banner, serves an empty web page, accepts a WebSocket connection, and shuts down cleanly on Ctrl-C.

**Deliverable artefacts:**
* `OpenWSFZ.Daemon` project (AOT-enabled executable, .NET 10, generic host).
* `OpenWSFZ.Web` project: Kestrel configured for `127.0.0.1:0` (ephemeral port for tests) / `127.0.0.1:<configured>` for real runs; static-files middleware; WebSocket hub.
* `LoopbackBindPolicy : IBindPolicy` (v1's only implementation; forces loopback regardless of config).
* `NullAuthPolicy : IAuthPolicy` (no-op, but exercised by tests).
* `WelcomeBannerEmitter` bound to the ASP.NET listener-started event.
* Signal handling for Ctrl-C / SIGINT / SIGTERM via `IHostApplicationLifetime`.
* Minimal `index.html` placeholder under `/web/` &mdash; just enough to assert the static-file pipeline works.
* `GET /api/v1/status` returning a stub `DaemonStatus`.
* `GET /api/v1/ws` accepting WebSocket upgrades and pushing one `status` event on connect.
* Integration tests using `WebApplicationFactory<Program>` covering FR-002, FR-007, NFR-004.
* End-to-end test launching the published binary as a subprocess.

**Requirements covered:** FR-002, FR-007, NFR-004.

**Exit gate (M2):**
* All Phase 0 gates plus:
* Integration tests pass: start daemon &rarr; `GET /` &rarr; open WS &rarr; receive `status` &rarr; Ctrl-C &rarr; process exits 0.
* E2E test passes on all three OSes: the published binary launches, emits the banner on stdout, accepts an HTTP request, accepts a WS upgrade.
* Traceability check confirms FR-002, FR-007, NFR-004 are mapped.

### 5.2 Phase 2 &mdash; Configuration &amp; Settings

**Goal:** TOML configuration round-trips through disk via a Settings page in the browser.

**Deliverable artefacts:**
* `OpenWSFZ.Configuration` project: schema types, Tomlyn-based parser, atomic save, default bootstrap on first run, CLI `--config` flag, `OPENWSFZ_CONFIG` env var.
* `GET /api/v1/config` and `PUT /api/v1/config` endpoints.
* `/web/settings.html` with a single placeholder field (audio device list is added in Phase 3) that exercises the round-trip.
* Validation errors return HTTP 400 with line/column info; parse errors at startup print to stderr and exit non-zero.
* Tests for happy path, error paths, override precedence (CLI &gt; env &gt; default).

**Requirements covered:** FR-004, FR-005, FR-006, FR-010, FR-011.

**Exit gate:**
* Integration test: edit a value via Settings &rarr; Save &rarr; restart daemon &rarr; value is persisted.
* All Phase 0 + Phase 1 gates remain green.

### 5.3 Phase 3 &mdash; Audio capture

**Goal:** the operator can choose a USB audio device from the Settings page and the daemon captures from it; the decoder consumer slot is empty (audio flows into the ring buffer and is dropped on the floor).

**Deliverable artefacts:**
* `/native/portaudio/` &mdash; PortAudio submodule, pinned by commit SHA.
* `/native/build.cmake` &mdash; cross-platform native build helper.
* `OpenWSFZ.Audio` project: `IAudioSource`, `IAudioDeviceEnumerator`, `PortAudioSource`, `WavFileAudioSource` (for tests).
* `GET /api/v1/audio/devices` endpoint.
* Settings page now lists real USB audio devices on the host; selection persists.
* Status push reflects `Capturing` / `Lost` / `Paused` / `NotConfigured`.
* Per-OS integration test of the enumerator (lists at least one device on each runner).

**Requirements covered:** FR-003.

**Exit gate:**
* Selecting a fixture device transitions status to `Capturing`.
* Simulating device removal transitions status to `Lost`.
* All earlier-phase gates remain green.

### 5.4 Phase 4 &mdash; FT8 decoder (M3)

**Goal:** the daemon decodes real FT8 from the captured audio (or a fixture) and pushes decoded messages to the browser in real time.

**Deliverable artefacts:**
* `/native/ft8_lib/` &mdash; `ft8_lib` submodule, pinned by commit SHA.
* `OpenWSFZ.Decoding` project: `IModeDecoder`, `IModeRegistry`, `DecodeResult`, `Ft8DecodeMessage`.
* `OpenWSFZ.Decoding.Ft8` project: `Ft8Decoder : IModeDecoder` with P/Invoke wrapper.
* Decoder worker thread aligned to the FT8 15-second cycle clock via `IClock`.
* WAV-fixture corpus seeded under `tests/OpenWSFZ.Decoding.Ft8.Tests/Fixtures/Wav/`, sourced per `TESTING_STRATEGY` &sect;5.1.
* `decode` event push over WebSocket.
* Decoded-messages list on `/web/index.html` rendering live events.
* Performance test asserting decode latency budget (&leq; 1500 ms p95) on Linux.

**Requirements covered:** FR-001, FR-009.

**Exit gate (M3):**
* Decoder-fixture suite is green &mdash; every fixture WAV produces its expected decode payloads within tolerance.
* Performance test green on Linux runner.
* E2E test green: published binary fed a fixture WAV produces the expected `decode` WS events.
* All earlier-phase gates remain green.

### 5.5 Phase 5 &mdash; Waterfall (M4)

**Goal:** the main page shows a live spectrogram above the decoded-messages list.

**Deliverable artefacts:**
* `OpenWSFZ.Waterfall` project: FFT framing (SIMD-accelerated), dB conversion, frame producer at 10 Hz.
* Binary WebSocket frame schema as specified in `TECHNICAL_SPEC` &sect;5.2.
* `<canvas>` renderer in `/web/js/waterfall.js`.
* Performance test asserting 10 Hz cadence and &leq; 20 ms jitter.

**Requirements covered:** FR-008.

**Exit gate (M4):**
* Integration test asserts the WS binary frame schema is correct.
* Performance test green on Linux runner.
* All earlier-phase gates remain green.

### 5.6 Phase 6 &mdash; Theme &amp; UI polish

**Goal:** the UI looks finished, theming works as designed, and the strict UI visibility gate is green against the full UI.

**Deliverable artefacts:**
* `/web/css/variables.css` &mdash; theme tokens.
* `/web/css/theme-dark.css` &mdash; the v1 default theme.
* `/web/css/layout.css` &mdash; layout rules.
* Accessibility pass: semantic HTML on all pages, working keyboard navigation, sufficient contrast.
* The strict-UI-visibility test (FR-016) passes against the full UI.

**Requirements covered:** FR-012, FR-013, FR-014, FR-015, FR-016, NFR-012.

**Exit gate:**
* UI visibility test green.
* Manual accessibility checklist completed and committed under `/docs/accessibility-checklist-v1.md`.
* All earlier-phase gates remain green.

### 5.7 Phase 7 &mdash; Hardening (M5)

**Goal:** every performance budget is met, the 8-hour soak passes, the release workflow produces clean per-OS binaries, and a release candidate is cut.

**Deliverable artefacts:**
* Performance suite (Linux only) covers every budget in `TECHNICAL_SPEC` &sect;11.
* Nightly soak workflow (`.github/workflows/soak-nightly.yml`) running the 8-hour test on Linux.
* `.github/workflows/release.yml` producing AOT-published binaries for `win-x64`, `linux-x64`, and `osx-x64` on tag push.
* `BUILDING.md` &mdash; instructions for building from source.
* `OPERATING.md` &mdash; instructions for launching, configuring, and using the daemon.
* Release-candidate tag `v1.0.0-rc1`.

**Requirements covered:** NFR-001, NFR-002, NFR-003, NFR-005, NFR-015.

**Exit gate (M5):**
* All CI gates G1&ndash;G5 green.
* Release gates R1 (latest nightly soak green) and R2 (extended-corpus decoder run green) both green.
* `release.yml` produces a clean artefact set on the `v1.0.0-rc1` tag.
* Traceability check confirms every FR-### / NFR-### is mapped.

### 5.8 Phase 8 &mdash; v1 release (M6)

**Goal:** v1 is publicly tagged and downloadable from GitHub (still source-only per NFR-005, with the AOT binaries as build artefacts for convenience).

**Deliverable artefacts:**
* Final README pass.
* Release notes for `v1.0.0`.
* Product Owner confirmed two-way FT8 QSO on their own station using OpenWSFZ (release gate R3); operator attestation documented in the release notes.
* `v1.0.0` tag.
* GitHub release published with binaries attached.

**Requirements covered:** all remaining v1 requirements signed off.

**Exit gate (M6):**
* Release gate R3 (confirmed QSO, operator-attested) completed and documented.
* Tag and release published.
* Traceability report from CI shows 100% requirement coverage.

---

## 6. Dependency Map

### 6.1 Phase dependency graph

```
P0 (Foundation)
  +-> P1 (Walking skeleton)
        +-> P2 (Config & Settings)
              +-> P3 (Audio capture)
                    +-> P4 (FT8 decoder)
                          +-> P5 (Waterfall)
                                +-> P6 (Theme & polish)
                                      +-> P7 (Hardening)
                                            +-> P8 (Release)
```

A few cross-phase dependencies worth calling out:

* **P4 (Decoder) also depends on P1** for the WebSocket hub it pushes events into.
* **P5 (Waterfall) depends only on P3** for its input, not on P4, so a parallel track is possible. Sequenced after P4 deliberately (see &sect;2 rule 2 &mdash; risky work first).
* **P6 depends on P4 and P5** because the strict-UI-visibility gate needs the full UI in place.
* **P7 depends on every prior phase** because hardening targets the complete pipeline.

### 6.2 Component dependency graph (from TECHNICAL_SPEC)

```
                  +---------------------------+
                  |  OpenWSFZ.Abstractions    |  (P0)
                  +-------------+-------------+
                                ^
        +-----------+-----------+-----------+----------+-----------+
        |           |           |           |          |           |
   Configuration   Audio    Decoding    Waterfall   Web    Daemon (host)
        (P2)       (P3)       (P4)        (P5)     (P1)      (P1, host)
                                ^
                                |
                       Decoding.Ft8 (P4)
                                ^
                                |
                          /native/ft8_lib   /native/portaudio
                              (P4)              (P3)
```

Every arrow above is "depends on the interface side of." Implementations depend on `OpenWSFZ.Abstractions`; consumers depend on the abstraction, never the implementation.

---

## 7. Phase 0 Task Breakdown (start here)

Tasks are sequenced so each one can be a single commit, and each leaves the repo green.

| # | Task | Owner role | Notes |
|---|---|---|---|
| T0.1 | Author `prompts/DEVELOPER.md` | ARCHITECT (handing to DEVELOPER role) | Format follows `prompts/ANALYST.md` and `prompts/ARCHITECT.md`. References this document, the spec, and the testing strategy. |
| T0.2 | Author `prompts/QA.md` | ARCHITECT (handing to QA role) | Likewise. Encodes `TESTING_STRATEGY` &sect;12. |
| T0.3 | Wire Serena MCP server into Claude Code config | DEVELOPER | Adds to `.claude/` or equivalent. See `REQUIREMENTS` &sect;6, &sect;8 Q15. |
| T0.4 | Create `OpenWSFZ.sln`, `global.json`, `Directory.Packages.props` | DEVELOPER | Pin .NET 10 SDK feature band; configure central package versions. |
| T0.5 | Create `OpenWSFZ.Abstractions` class library project | DEVELOPER | Empty placeholder file per interface group (`IAudioSource.cs`, `IModeDecoder.cs`, `IBindPolicy.cs`, ...) with `// TODO: P<phase>` markers. Real definitions land in their owning phases. |
| T0.6 | Create `tools/TraceabilityCheck/` console project | DEVELOPER | Implements `TESTING_STRATEGY` &sect;6.2. ~150 lines of C#. Returns non-zero on a missing or stale requirement ID. |
| T0.7 | Create `tools/LicenseInventoryCheck/` console project | DEVELOPER | Walks `obj/project.assets.json` for every project plus the submodule manifests; emits a JSON report; returns non-zero on a non-MIT-redistributable licence. |
| T0.8 | Author `.github/workflows/ci.yml` | DEVELOPER | Matrix `{ windows-latest, ubuntu-latest, macos-latest }`; restore + build + test + coverage upload; Linux-only traceability + licence + UI-visibility (latter stays inert until P6). |
| T0.9 | Enable GitHub branch protection on `main` | Product Owner (GitHub admin) | Require all six gates G1&ndash;G6 from `TESTING_STRATEGY` &sect;7. |
| T0.10 | Verify exit gate: empty CI run green on all OSes; trace + licence gates green | QA | Closing review. |

**Phase 0 OpenSpec change proposal:** `openspec/changes/p0-foundation/` &mdash; authored as the first task once this plan is approved.

---

## 8. Phase 1 Task Breakdown

| # | Task | Notes |
|---|---|---|
| T1.1 | Create `OpenWSFZ.Daemon` project (AOT-enabled executable, .NET 10) | `<PublishAot>true</PublishAot>` from day one to surface AOT incompatibilities while the codebase is small. |
| T1.2 | Add `Microsoft.Extensions.Hosting` and wire `IHostApplicationLifetime` | Provides Ctrl-C / SIGTERM handling for free. |
| T1.3 | Implement `WelcomeBannerEmitter` | Bind to listener-started event; print `OpenWSFZ listening on http://127.0.0.1:<port>` and the trailing operator-instruction line. |
| T1.4 | Create `OpenWSFZ.Web` project; configure Kestrel; add static-files middleware rooted at `<exe-dir>/web/` | Static-files behaviour rejects path traversal by default. |
| T1.5 | Implement `LoopbackBindPolicy : IBindPolicy` | Force `127.0.0.1`; log warning if config asks for anything else. |
| T1.6 | Implement `NullAuthPolicy : IAuthPolicy` | Pass-through; ensures the seam is exercised even in v1 (`TECHNICAL_SPEC` &sect;6.2). |
| T1.7 | Implement `GET /api/v1/status` endpoint returning a stub `DaemonStatus` | Status fields are mostly placeholder until later phases populate them. |
| T1.8 | Implement `GET /api/v1/ws` WebSocket endpoint | On connect, push one `status` JSON envelope. Heartbeat every 5 s. |
| T1.9 | Create placeholder `/web/index.html` | Minimal page that opens a WebSocket and renders the received status. |
| T1.10 | Create `OpenWSFZ.Web.Tests` project | `WebApplicationFactory<Program>` harness. |
| T1.11 | Write integration tests for FR-002, FR-007, NFR-004 | Display names follow `TESTING_STRATEGY` &sect;6.1. |
| T1.12 | Create `OpenWSFZ.E2E.Tests` project | Driver subprocesses the published binary on the current OS. |
| T1.13 | Write E2E test asserting the welcome banner on stdout | Reads stdout via a piped redirect. |
| T1.14 | Verify exit gate (M2): all integration + E2E tests pass; traceability check confirms FR-002, FR-007, NFR-004 mapped | QA review. |

**Phase 1 OpenSpec change proposal:** `openspec/changes/p1-walking-skeleton/` &mdash; authored after P0 is merged.

---

## 9. Risk Register

Risks are scored High / Medium / Low for **likelihood** (probability it happens) and **impact** (consequence if it does).

### 9.1 Technical risks

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | `ft8_lib` P/Invoke is awkward (callbacks, struct marshalling) | Medium | Medium | Spike P/Invoke integration as the **first** task in P4. Fallback: a thin C wrapper exposing a simplified C ABI, vendored under `/native/`. |
| R2 | .NET 10 AOT incompatibility with ASP.NET Core minimal APIs, Tomlyn, or xUnit harness | Medium | High | Enable AOT **from P0**, not at the end. Discover incompatibilities while the codebase is small enough to refactor cheaply. |
| R3 | PortAudio cross-platform parity bugs (WASAPI vs. ALSA vs. CoreAudio device enumeration semantics) | Medium | Medium | Per-OS integration tests in P3 exercise the enumerator on each CI runner; document the host-API selection per OS in the spec; use PortAudio's stable host-API selection flags rather than relying on defaults. |
| R4 | FT8 decode accuracy parity gaps vs. WSJT-X on weak signals | Medium | Medium | Tolerances in `TESTING_STRATEGY` &sect;4.2 are reasonable for `ft8_lib`'s known capability envelope. If real corpus tests show systematic failures, treat as upstream issue; curate the corpus to fixtures known to be in `ft8_lib`'s envelope, with exclusions documented and a tracking issue filed for any excluded class. |
| R5 | Waterfall 10 Hz too aggressive under AOT + browser load | Low | Low | Measure early in P5. Fall back to 5 Hz if necessary; spec calls 10 Hz a default, not a hard requirement. |
| R6 | Test suite slips past the 60-second budget | Medium | Low | Each phase's exit gate includes a re-check of the test runtime; phase fails if breached. Move slow tests to nightly tier (`TESTING_STRATEGY` &sect;4.6). |
| R7 | Soak test flake from OS-level noise (memory pressure, journal rotation) | Medium | Low | Soak runs nightly, not per-PR. Single flake does not block; pattern of flakes triggers investigation. Soak failures gate release tags, not PRs. |
| R8 | Native submodule upstream re-licences or vendors incompatible code | Low | High | Submodules pinned by commit SHA; licence inventory gate (G5) catches drift; updates are explicit PRs with a fresh licence audit. |

### 9.2 Process risks

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R9 | Knowledge held by solo developer + AI; loss if the project pauses | Medium | Medium | `REQUIREMENTS.md`, `TECHNICAL_SPEC.md`, `TESTING_STRATEGY.md`, this plan, and per-phase OpenSpec proposals together serve as the project's externalised memory. Re-onboarding is a documented path, not a tribal one. |
| R10 | Scope creep into v2 features mid-v1 build (TX, rig, LAN) | Medium | High | Extension seams already designed; any new feature not on the v1 phase list goes into an OpenSpec proposal for v2 and stays there. ARCHITECT review of any v1 scope change. |
| R11 | AI role boundaries blur (ARCHITECT writing code, DEVELOPER editing requirements) | Medium | Low | Each role has its own prompt under `/prompts/`; PR descriptions reference which role authored which file; cross-role edits require explicit role handoff. |
| R12 | Solo-developer + ambitious-scope schedule slip | High | Low (no external deadline) | Phasing keeps each phase small enough to finish in a single working session. Phase exit gates are clear so abandonment vs. partial completion is visible. The project optimises for *finishing* v1 small and tight, not for any calendar target. |

### 9.3 Closing the risk register

The risk register is reviewed at each phase exit. New risks discovered during a phase are added; risks that have been retired are marked closed. The register is the source of truth for "what could still go wrong" at any point during v1.

---

## 10. Next Action After Approval

Once this plan is approved:

1. **ARCHITECT** authors the first OpenSpec change proposal under `openspec/changes/p0-foundation/`. It draws its task list from &sect;7 of this document.
2. **DEVELOPER** picks up T0.1 (authoring `prompts/DEVELOPER.md`). All subsequent tasks proceed through the standard branch-per-feature OpenSpec workflow described in `TECHNICAL_SPEC` &sect;13.2.
3. **QA** is invoked as a gate on the first PR (the one that lands `prompts/QA.md` itself), and on every PR thereafter.

After this plan is signed off, **the ARCHITECT role's standing engagement is complete for v1.** It returns only when:

* a requirement change in `REQUIREMENTS.md` invalidates a design decision, or
* a new OpenSpec change proposal raises an architectural question the current docs don't answer, or
* a phase exit gate reveals that the design needs revision.

---

## 11. Items Carried Forward

Items from `REQUIREMENTS.md` &sect;8 that this plan does **not** resolve, with their resolution path:

| # | Item | Resolution path |
|---|---|---|
| 1 | DSP correctness parity | Verified in P4 by the decoder-fixture suite. Tracked here as R4. |
| 5 | Upgrade story for user-edited frontend files | Deferred to v2 release-engineering work; not relevant at v1 source-only distribution. |
| 6 | Main-page composition beyond waterfall + decoded-messages list | Resolved by P6 (Theme & polish) OpenSpec proposal, after the v1 surface is otherwise locked. |
| 8 | UX competitive bar (NFR-013) | v1 does not gate on this; the Product Owner manual smoke (R3) plus operator feedback once the repo opens publicly are the inputs to the post-v1 plan. |
| 12 | Repo posture (public / private) | Operational, Product-Owner-owned. Re-evaluated at M5 (release candidate) and M6 (release). |
| 13 | The pre-existing `feature/project-skeleton` scaffolding | Resolved: removed in full at the start of this engagement. Re-established phase by phase via this plan. |

---

**End of IMPLEMENTATION_PLAN.md v1.0 (draft).**
