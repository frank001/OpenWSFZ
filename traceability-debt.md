# Traceability Debt

Requirement IDs listed here are explicitly acknowledged as pending their
implementing phase. They are excluded from the missing-mapping gate (G3)
until the phase that covers them lands tests.

**Rule:** Remove an ID from this file once its implementing phase's tests arrive.
An ID that is listed here but no longer exists in `REQUIREMENTS.md` is a stale
debt entry and will fail the traceability check.

## Pending — Phase 1 (Walking skeleton / daemon bootstrap)

FR-007  # Terminal welcome banner printed on startup
NFR-001  # Portability — builds and runs on Windows, Linux, macOS from one source tree
NFR-004  # Security — binds only to loopback 127.0.0.1 in v1
NFR-006  # Test coverage — every requirement maps to at least one automated test
NFR-007  # Test discipline — failing tests block progress
NFR-009  # Extensibility — deployment lifecycle seam (IHostLifecycle)
NFR-010  # Extensibility — bind/auth policy seam (IBindPolicy, IAuthPolicy)
NFR-011  # Extensibility — architecture iterative and easy to extend
NFR-014  # Process — four AI-assisted roles: ANALYST, ARCHITECT, DEVELOPER, QA

## Pending — Phase 4 (Decoder)

# FR-001 removed — implemented in p5-ft8-decoder (Ft8Decoder, CycleFramer)
NFR-003  # Real-time decoding — each 15-second FT8 cycle fully decoded before next cycle
NFR-008  # Extensibility — protocol layer plugin point (IModeDecoder / IModeRegistry)

## Pending — Phase 5 (HTTP / WebSocket / Waterfall)

FR-002  # Self-hosted web UI served on http://127.0.0.1:<port>
# FR-008 removed — implemented in p5-ft8-decoder (SpectrumAnalyser + WaterfallRenderer; tests in SpectrumAnalyserTests)
# FR-009 removed — implemented in p5-ft8-decoder (decode event → #decodes-table UI)
FR-011  # Save action on Settings page writes changes to the active config file
# FR-019 removed — implemented in p6-file-logging (console level, Serilog pipeline); tested via FR-019: LogLevel round-trips via POST/GET /api/v1/config
FR-020  # Audio activity indicator in heartbeat — audioActive bool in heartbeat + status WS payloads
NFR-012  # Accessibility — semantic HTML, keyboard navigation, sufficient contrast

## Pending — Phase 6 (Polish / UX)

FR-030  # Logging configuration hot-reload — all logging settings changes take effect
        # immediately on save without requiring a restart. Planned for p16.

FR-013  # CSS-file-based theming — edit CSS files on disk; no in-app switcher in v1
FR-016  # Strict UI visibility rule — no placeholders, no greyed-out future controls
FR-018  # Cycle countdown timer (testing aid) — Settings toggle, persisted in AppConfig.ShowCycleCountdown
NFR-013  # UX competitive bar — HAM operators prefer OpenWSFZ over existing software

## Pending — Phase 7 (Hardening / release prep)

NFR-002  # Performance — user experience comparable to WSJT-X
NFR-005  # Distribution — source-only via GitHub repository
NFR-015  # Stability — no crash or memory leak for a normal operating session

## Pending — Phase 16 (CAT control)

FR-033  # CAT status indicator in UI — JavaScript/HTML status bar and badge;
        # verified manually via hardware acceptance gates (tasks 15 & 16).
        # No unit test references this ID. Remove when a UI-layer test is added.

NFR-017 # Secrets scan gate G7 — the gate itself IS the test (gitleaks in CI);
        # no unit test references this ID. Remove when a test with prefix
        # "NFR-017:" is added (or if the gate is ever made a unit-testable concern).

NFR-018 # Decode parity — v1.0 release gate; enforced by the real-signal fixture
        # integration tests (FR-029). No separate "NFR-018:" test exists.
        # Remove when a test explicitly prefixes "NFR-018:".

NFR-019 # Brand neutrality — policy requirement; no automated test is feasible.
        # Enforced by code review. Remove if a lint/grep-based test is added.

## Pending — Phase 17 (Settings UX — p17-settings-ux)

FR-035  # Settings page tabbed layout — UI-layer only; no automated test yet.
        # Verified manually. Remove when a browser/UI test covers tab switching.
FR-036  # Cycle countdown visibility: hidden not display:none — CSS/JS behaviour.
        # No automated test yet. Remove when a DOM assertion test is added.
FR-037  # Dial frequency input disabled when CAT enabled — JS dynamic locking.
        # No automated test yet. Remove when a DOM assertion test is added.

## Pending — Process requirements (no automated test feasible)

NFR-020  # Pre-merge traceability debt review — process/checklist requirement;
         # enforced by the QA reviewer role, not by an automated test.
         # Remove if a lint step is added that validates debt-file coverage
         # as part of the PR pipeline.

NFR-021  # Privacy / GDPR — no real third-party callsign in version control;
         # use ITU-unallocated Q-prefix calls. Policy requirement enforced by
         # code review (like NFR-019 brand neutrality). Remove when a grep/lint
         # gate is added that fails CI on a non-Q real callsign in committed files.

## Pending — Phase 18 (Settings dirty-state — p18-settings-dirty-state)

FR-040  # Unsaved-changes indicator — JS dirty-state engine; UI-layer only.
        # Verified manually. Remove when a browser/UI test covers dirty detection.
FR-041  # Navigation guard — beforeunload + confirm() interception; UI-layer only.
        # Verified manually. Remove when a browser/UI test covers the guard.

## Pending — Phase 19 (Frequency management — p19-frequency-management)

FR-043  # Frequencies settings tab — JS/HTML table CRUD; UI-layer only.
        # Verified manually. Remove when a browser/UI test covers the Frequencies tab.
FR-044  # Frequency selector in main GUI — JS conditional #dial-freq rendering; UI-layer only.
        # Verified manually. Remove when a browser/UI test covers the CAT state transitions.

## Pending — Phase 10 (Decoder ground truth — p10-decoder-ground-truth)

# FR-029 is fully covered: WavReaderTests (unit) + RealSignalFixtureTests (oracle integration)
# + ReplayHarnessTests all cite FR-029 in their display-name prefixes. Removed from debt.
NFR-016  # Decoder-correctness gate G6 — real-signal fixture integration test runs in CI on
         # every push/PR to main, blocking merges that regress real-signal recovery.
         # The gate runs inside the G1 dotnet test step; G6 is the named label for
         # RealSignalFixtureTests within that step. NFR-016 stays in debt until a test
         # explicitly prefixes its display name "NFR-016: ..." per the TraceabilityCheck
         # convention (currently only FR-029 appears in the prefix; NFR-016 appears in
         # the suffix as "(G6 gate — NFR-016)"). Remove when that prefix test is added.

## Pending — QA harness process requirements (NFR-022, NFR-023)

NFR-022  # QA harness — Windows terminal encoding. This requirement governs Python scripts
         # in qa/rr-study/harness/, which are outside the .NET solution and have no
         # corresponding xUnit/NUnit test assembly. Compliance is verified by: (a) code
         # review confirming sys.stdout.reconfigure() is present in harness/common.py and
         # in any script that does not import common; (b) no UnicodeEncodeError raised
         # during any study run on a Windows cp1252 console. Remove when a pytest suite
         # for the QA harness is introduced that can assert the reconfigure call.

NFR-023  # QA study report structure. This requirement governs the content and section
         # order of report.md files produced by Python analysis scripts in qa/rr-study/.
         # No xUnit/NUnit test can assert Markdown document structure. Compliance is
         # verified by: (a) QA review of every committed report.md confirming the five
         # mandatory sections are present; (b) code review of _write_report() in
         # analyse.py and analyse_corpus.py confirming each section is emitted.
         # Remove when a pytest suite for the harness asserts report structure programmatically.

NFR-024  # QA harness — compliant report generation. This requirement mandates that
         # analyse.py and analyse_corpus.py produce a fully NFR-023-compliant report.md
         # without any manual post-processing step. No xUnit/NUnit test can enforce
         # Python script output format. Compliance is verified by: (a) QA review of every
         # committed report.md against the NFR-023 five-section checklist before merge;
         # (b) code review of _write_report() in both analysis scripts confirming all five
         # sections are populated with correct content (not placeholder text or empty tables).
         # A non-compliant report.md in a merge commit is a blocking defect per NFR-024.
         # Remove when a pytest suite for the harness validates report.md structure and
         # verdict correctness programmatically (at which point NFR-023 entry can also be removed).

## Pending — D-001 OSD test coverage gaps (fix/d001-osd-fallback)

# AP+OSD combined path: ftx_decode_candidate_ap with OSD fallback is not covered
# by an integration test. Rationale and risk assessment in D001H6ApDecodeTests.cs
# class-level <remarks>. Not a requirement ID; tracked here for completeness.
# Remove when a deterministic fixture for the AP+OSD combined path is engineered
# (requires either a weaker SetApConstraints API or a new fixture geometry).
D001-AP-OSD-GAP

## Pending — Security hardening (fix/security-lan-hardening, 2026-06-24)

SEC-003  # XSS guard — settings.js appendFreqRow DOM construction.
         # The fix (replacing innerHTML with createElement/textContent) is confined
         # to the browser JS layer. No xUnit/NUnit test can assert DOM construction
         # technique; the absence of innerHTML for server-derived data is enforced
         # by code review (grep confirms no innerHTML assignment receives server data).
         # Remove when a browser-automation test (e.g. Playwright) asserts that
         # inserting a description containing <script> does not execute JS.
