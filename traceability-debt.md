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
FR-008  # Waterfall display — live spectrogram of audio input in the main UI
# FR-009 removed — implemented in p5-ft8-decoder (decode event → #decodes-table UI)
FR-011  # Save action on Settings page writes changes to the active config file
NFR-012  # Accessibility — semantic HTML, keyboard navigation, sufficient contrast

## Pending — Phase 6 (Polish / UX)

FR-013  # CSS-file-based theming — edit CSS files on disk; no in-app switcher in v1
FR-016  # Strict UI visibility rule — no placeholders, no greyed-out future controls
FR-018  # Cycle countdown timer (testing aid) — Settings toggle, persisted in AppConfig.ShowCycleCountdown
NFR-013  # UX competitive bar — HAM operators prefer OpenWSFZ over existing software

## Pending — Phase 7 (Hardening / release prep)

NFR-002  # Performance — user experience comparable to WSJT-X
NFR-005  # Distribution — source-only via GitHub repository
NFR-015  # Stability — no crash or memory leak for a normal operating session
