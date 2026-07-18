## Why

`QsoAnswererService.ExecuteJumpInAsync`'s `EngagePoint.SendRr73` case transmits RR73 and aborts
to `Idle` without ever writing an ADIF record — even when the jump-in is completing a QSO the
daemon itself originated (e.g. `QsoCallerService` sent the CQ, got the answer, sent the report,
and only lost the exchange to its own watchdog before the partner's `RRR`/`R±NN` reply arrived).
This was a deliberate, documented Phase-1 tradeoff when `D-CALLER-012` shipped (see AC-4, "No
ADIF write (partial QSO — expected)"), but that framing conflated "we don't have a grid square"
(true) with "this isn't a real, completed QSO" (not true). Found 2026-07-16 by QA against a real,
Captain-confirmed completed QSO with a partner station that silently never appeared in
`ADIF.log` (`dev-tasks/2026-07-16-jump-in-sendrr73-no-adif-record.md`).

A second, smaller data-quality defect lives in the same code path: `ExecuteJumpInAsync`
hardcodes `_rstRcvd = "+00"` regardless of what the partner actually sent. Fixing the ADIF gap
without also fixing this would write a plausible-looking but fabricated `RST_RCVD` value.

## What Changes

- `EngagePoint.SendRr73`'s jump-in case in `QsoAnswererService.ExecuteJumpInAsync` writes an ADIF
  record on completion, mirroring the existing `ExecuteTx73Async` pattern (same
  `QsoConfirmation`-gated publish-vs-direct-write branch, same field population, same
  `QsoComplete` state ordering ahead of the abort-to-idle).
- The raw decoded payload text (already available at the `POST /api/v1/tx/engage-decode` call
  site in `WebApp.cs`) is threaded through `IQsoController.EngageAtAsync` →
  `QsoControllerRouter.EngageAtAsync` (pass-through) → `QsoAnswererService.EngageAtAsync` so that
  `ExecuteJumpInAsync` can derive a real `RstRcvd` (stripping a leading `R` from an `R±NN` report,
  or using a bare `RRR` as-is) instead of the current hardcoded `"+00"`.
  `QsoCallerService.EngageAtAsync` remains a no-op stub; it gains the new parameter for signature
  parity only.
- `PartnerGrid` on this path remains `null` — explicitly out of scope, and correct as-is (a
  mid-exchange jump-in never saw the original CQ, the only FT8 message type carrying a grid).
- **Explicitly out of scope:** the watchdog/retry interaction that caused tonight's exchange to
  need a jump-in at all is correct, already-tested behaviour from `D-008` and is not touched by
  this change.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `qso-answerer`: adds a new requirement documenting that a `SendRr73` jump-in completion writes
  an ADIF record (previously undocumented — the spec was silent on jump-in ADIF behaviour
  entirely) and that the recorded `RstRcvd` is derived from the actual decoded payload rather
  than a fixed placeholder.

## Impact

- `src/OpenWSFZ.Daemon/QsoAnswererService.cs` — `ExecuteJumpInAsync`'s `EngagePoint.SendRr73`
  case gains ADIF-write logic; `_rstRcvd` derivation changes from a hardcoded literal to payload
  parsing; `EngageAtAsync` gains a new parameter to receive the raw payload.
- `src/OpenWSFZ.Daemon/QsoCallerService.cs` — `EngageAtAsync` stub gains the same parameter, for
  signature parity only (still a no-op).
- `src/OpenWSFZ.Daemon/IQsoController.cs`, `QsoControllerRouter` — `EngageAtAsync` signature
  gains the new parameter, threaded straight through.
- `src/OpenWSFZ.Web/WebApp.cs` — `POST /api/v1/tx/engage-decode` passes its already-available
  `info` payload text into the new `EngageAtAsync` parameter instead of discarding it.
- No public wire-format change (the endpoint's request/response shapes are unchanged; only an
  in-process parameter is added). No change to `AdifLogWriter` — it already correctly conditions
  `GRIDSQUARE` on a null `PartnerGrid`.
