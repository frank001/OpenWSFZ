## Why

The decode table's CQ-row click-to-answer interaction (TX-D01) currently arms live TX on a single
click. Operators scanning, scrolling, or simply reading the decode table can easily click a CQ row
by accident, immediately calling `POST /api/v1/tx/answer-cq` and arming the TX controller for a
transmission that fires within 0–30 seconds — with no confirmation step. The Captain reports this
as "much too sensitive" during real operation. Requiring a double-click instead of a single click
adds deliberate friction against accidental engagement while remaining a fast, single-gesture
action for an operator who genuinely intends to answer that CQ.

## What Changes

- **BREAKING** (behavioural, operator-facing): a single click on a CQ decode-table row no longer
  arms TX. A double-click (`dblclick`) is required to call `POST /api/v1/tx/answer-cq` and arm the
  TX panel.
- Single-click on a CQ row becomes a no-op with respect to TX arming — the row keeps its existing
  hover/cursor affordance (via `.decode-cq:hover` / `cursor: pointer`) so it still reads as
  clickable, but no network call and no TX-arming action fires until the second click completes the
  double-click gesture.
- The existing in-flight guard (`inFlight` boolean, `pointerEvents = 'none'`, D-TX-UI-005's
  post-success 400 ms cooldown) is retargeted from "suppress an accidental repeat single-click" to
  "suppress an accidental repeat double-click" — same mechanism, new trigger event.
- Update the ratified `web-frontend` spec's TX-D01 requirement and all four of its scenarios to
  describe double-click instead of single-click as the triggering gesture.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `web-frontend`: the "Decode table — clickable CQ rows (TX-D01)" requirement changes its
  triggering gesture from a single click to a double-click. Scenario text updated accordingly; no
  other part of the requirement (callsign extraction, frequency/cycle-start derivation, the
  `answer-cq` payload shape, 200/409/other-error handling) changes.

`qso-controller`'s `AnswerCqAsync` requirement (also tagged TX-D01) is backend-only — phase
derivation, pending-target fields, `autoAnswer` persistence — and contains no reference to click
cardinality. It is unaffected and needs no delta spec.

## Impact

- **Frontend:** `web/js/main.js:727`–`764` (the CQ-row click handler) — the only implementation
  file touched.
- **Backend:** none. `POST /api/v1/tx/answer-cq` and `QsoAnswererService.AnswerCqAsync` are
  unchanged; the request they receive on trigger is identical to today's.
- **Spec:** `openspec/specs/web-frontend/spec.md`, TX-D01 requirement and its four scenarios.
- **Tests:** any existing frontend test/coverage asserting single-click arms TX must be updated to
  assert double-click instead; a new test should assert a single click alone does *not* arm TX.
- **Operator-visible behaviour change:** operators must be told (release notes / changelog) that
  answering a CQ from the decode table now requires a double-click, not a single click — this is a
  workflow habit change for anyone already using the app.
