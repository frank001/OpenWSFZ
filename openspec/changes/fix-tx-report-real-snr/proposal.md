**User-facing:** yes

## Why

Every signal report `QsoCallerService`/`QsoAnswererService` transmits over the air is a fixed
placeholder — `+00` (caller) or `R+00` (answerer) — regardless of the actual measured signal
quality of the decode that triggered it. This was accepted as a named v1 trade-off (`TX-D04`) at
`qso-caller`'s original design time, but a live acceptance run reviewed 2026-07-18
(`dev-tasks/2026-07-18-live-run-tx-report-snr-and-reengagement-workflow.md`) showed it firing on
every single QSO — ten for ten — while the real measured `DecodeResult.Snr` for the exact same
exchange was sitting in scope, unused, at every TX-composition site. The Captain's own words: "the
application is able to measure the snr, it should report the correct value" — a real issue, no
design discussion needed, fix it as stated.

## What Changes

- All four TX-composition sites that currently hardcode a signal report now use the real,
  measured `DecodeResult.Snr` of the decode that triggered them, formatted as a standard FT8
  two-digit signed report (`+07`, `-13`, clamped to `±30`):
  - `QsoCallerService.ExecuteTxReportAsync` (both the `First` auto-engage and `None`-mode
    deferred/pending-responder paths).
  - `QsoCallerService.RetryOrAbortAsync`'s `WaitRr73` retry branch (resends the same value chosen
    above, not a freshly recomputed one).
  - `QsoAnswererService.HandleWaitReportAsync`'s normal report reply.
  - `QsoAnswererService.ExecuteJumpInAsync`'s `EngagePoint.SendReport` mid-exchange jump-in case —
    this requires threading the triggering decode's `Snr` through
    `POST /api/v1/tx/engage-decode` → `IQsoController.EngageAtAsync` → `QsoControllerRouter` →
    `QsoAnswererService`/`QsoCallerService` (stub, signature parity only), mirroring the exact
    pattern already used to thread `rawPayload` through the same call chain for
    `fix-jump-in-rr73-adif-capture`.
- The ADIF `RstSent` field written by both services now reflects the real value actually
  transmitted, instead of the fixed `"+00"`/`"R+00"` literal.
- `R`-prefix protocol-position logic (caller sends a bare report, answerer sends an
  `R`-prefixed roger-report) is untouched — only the numeric value changes.
- No behavior change to jump-in cases that never compose a report this session
  (`EngagePoint.SendRr73`, `EngagePoint.Send73`) — `RstSent` there remains the existing accepted
  `"R+00"` placeholder, documented as such, since there genuinely is no real value to report (the
  mid-exchange jump-in never observed the original exchange), mirroring the already-accepted
  `PartnerGrid = null` treatment on the same path.

**BREAKING**: none — `IQsoController.EngageAtAsync`'s signature gains a new parameter, but this
interface is entirely in-process (no external/wire-format consumers), matching the precedent set
by `fix-jump-in-rr73-adif-capture`'s `rawPayload` addition to the same method.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `qso-caller`: the `TxReport — transmitting the signal report` requirement no longer composes a
  fixed `+00`; it composes the real measured SNR of the triggering decode, and the retry
  retransmission reuses the same value rather than a hardcoded literal.
- `qso-answerer`: the report reply composed in `WaitReport` (and the `EngagePoint.SendReport`
  jump-in case) uses the real measured SNR instead of a fixed `R+00`; the `Answerer state machine`
  requirement's `TxReport` state description is updated to match. The ADIF `RstSent` field on both
  the normal-completion and jump-in-`SendReport` paths reflects the real value sent.

## Impact

- **Code**: `src/OpenWSFZ.Daemon/QsoCallerService.cs`, `src/OpenWSFZ.Daemon/QsoAnswererService.cs`,
  `src/OpenWSFZ.Daemon/QsoControllerRouter.cs`, `src/OpenWSFZ.Abstractions/IQsoController.cs`,
  `src/OpenWSFZ.Web/WebApp.cs` (`engage-decode` handler), `src/OpenWSFZ.Web/AppJsonContext.cs`
  (`EngageDecodeRequest` gains an `Snr` field), `web/js/api.js`/`web/js/main.js` (forward the
  decode row's already-known `snr` into the `engage-decode` POST body).
- **Tests**: `tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs`,
  `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs`,
  `tests/OpenWSFZ.Web.Tests/EngageDecodeEndpointTests.cs` (fake `IQsoController` gains the new
  parameter; new assertions on the forwarded value).
- **Specs**: `openspec/specs/qso-caller/spec.md`, `openspec/specs/qso-answerer/spec.md`.
- **Not in scope**: `D-CALLER-022` (the re-engagement/"confirm they got it" investigation from the
  same dev-task handoff) is a design/investigation task per the Captain's own framing — no code
  changes requested yet. Its output is a short design note, not part of this change's `tasks.md`.
  See `d-caller-022-investigation.md` in this change directory.
