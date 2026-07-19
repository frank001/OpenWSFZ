**User-facing:** yes

## Why

`fix-tx-report-real-snr` (TX-D04, merged `092c42a`) made `QsoCallerService`/`QsoAnswererService`
transmit the real measured signal report instead of a fixed `+00`/`R+00` placeholder — confirmed
correct by the resulting ADIF records. Immediately after, the Captain made a live QSO and reported
the on-screen TX message rows and QSO Transcript panel still showed `+00` throughout, asking "what
is real?" Traced to source (`dev-tasks/2026-07-19-tx-d05-transcript-and-message-rows-show-stale-template.md`,
`openspec/qa-backlog.md` N12): `renderMessageRows()` in `web/js/main.js` has always been a
client-side template keyed off `txState` alone, never wired to real transmitted content. That
template happened to match reality only because the real value really was always `+00` before
TX-D04 shipped. Now that the backend sends real values, the display is stale — a predictable,
scoped follow-on that TX-D04's own (correctly backend-only) scope could not have caught.

## What Changes

- `QsoCallerService` gains a persisted last-sent-message field, mirroring `QsoAnswererService`'s
  existing (but never externally surfaced) `_lastTxMessage`.
- `TxStatusResponse` (`GET /api/v1/tx/status` and related endpoints) and the `txState` WebSocket
  push (`WsTxStateMessage`) each gain a new field carrying the real last-transmitted message text,
  threaded from whichever service (`QsoCallerService`/`QsoAnswererService`) is currently active via
  `QsoControllerRouter`. `null`/absent when nothing has been transmitted yet this session.
- `renderMessageRows()` (`web/js/main.js`) prefers the real transmitted text for any row already
  sent this session, falling back to the existing template only for rows not yet reached (there is
  no real content to show for a message that hasn't been transmitted yet — the template remains
  correct and honest there).
- The QSO Transcript's `appendTranscriptEntry('sent', ...)` call (`web/js/main.js`) logs the real
  transmitted text once available, instead of unconditionally logging the synthetic template.
- No change to `qso-transcript-panel`'s received-message capture, matching/aggregation logic, or
  rolling-log behaviour (`web/js/qsoTranscript.js`) — this is purely about what text a `sent` entry
  carries, not how entries are captured or displayed structurally.

**BREAKING**: none — both new fields are purely additive to existing response/event shapes; an
older cached frontend bundle that doesn't read the new field continues to work exactly as it does
today (falls back to the template, which is still correct for not-yet-transmitted rows and merely
stale, not wrong, for already-transmitted ones).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `qso-caller`: `QsoCallerService` persists the real text of its last transmitted message
  (previously only `QsoAnswererService` did this internally, and neither service exposed it).
- `qso-answerer`: `QsoAnswererService`'s existing `_lastTxMessage` is now exposed externally via
  the status/event contract rather than staying internal-only.
- `qso-controller`: `TxStatusResponse` and the `txState` WebSocket event gain a new
  last-transmitted-message field.
- `web-frontend`: `renderMessageRows()` and the QSO Transcript's sent-entry logging prefer the real
  transmitted message over the static per-state template once one has actually been sent this
  session.

## Impact

- **Code**: `src/OpenWSFZ.Daemon/QsoCallerService.cs`, `src/OpenWSFZ.Daemon/QsoAnswererService.cs`,
  `src/OpenWSFZ.Daemon/QsoControllerRouter.cs`, `src/OpenWSFZ.Abstractions/IQsoController.cs` (if a
  new accessor is needed), `src/OpenWSFZ.Web/AppJsonContext.cs` (`TxStatusResponse`,
  `WsTxStateMessage`), `src/OpenWSFZ.Web/WebApp.cs` (status endpoint handlers), `web/js/main.js`
  (`renderMessageRows`, the transcript sent-entry call site).
- **Tests**: `tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs`,
  `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs`, `tests/OpenWSFZ.Web.Tests/*` (status
  endpoint / WebSocket push assertions), `web/js/main.test.js` and/or `web/js/qsoTranscript.test.js`
  (check for any assertions pinned to the old always-template `sent` text — TX-D05's own dev-task
  flagged this as a thing to check, not yet confirmed either way).
- **Specs**: `openspec/specs/qso-caller/spec.md`, `openspec/specs/qso-answerer/spec.md`,
  `openspec/specs/qso-controller/spec.md`, `openspec/specs/web-frontend/spec.md`.
- **Not in scope**: `D-CALLER-022` (the re-engagement/"confirm they got it" workflow investigation
  from the same review session) — separate, already tracked (`openspec/qa-backlog.md` N11,
  `dev-tasks/2026-07-18-live-run-tx-report-snr-and-reengagement-workflow.md` §3), investigation-only
  per the Captain's own framing, no code changes requested yet.
