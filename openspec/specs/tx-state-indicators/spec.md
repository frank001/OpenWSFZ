# tx-state-indicators Specification

## Purpose

This capability defines the visual (colour) states of the TX control buttons —
`#tx-enable-btn` and `#tx-call-cq-btn`.

`#tx-call-cq-btn`'s colour is still derived entirely from existing `txState` WebSocket
payload fields (`autoAnswerEnabled`, `role`), with no additional server-side signal.

`#tx-enable-btn`'s colour is derived from `autoAnswerEnabled` plus a dedicated `keying`
signal (see below) — **not** from the `state` field. This supersedes this capability's
original Decision 2 (`autoAnswerEnabled` + `state`-prefix, "no additional server-side
signal"), decided in the archived `f-004-operator-visibility-improvements` change. The
reversal was made deliberately, on the Captain's explicit instruction, by dev-task
`2026-07-10-tx-btn-live-verify-and-settings-tab-wrap.md` item A: live verification found the
`state`-prefix rule under-reported real transmission windows whenever a TX call site
retransmitted audio without first re-broadcasting a `Tx*` sub-state (e.g. the answerer's
retry path before it was fixed) — a class of bug that recurs any time a new TX call site
forgets to bracket itself with a state broadcast. `keying` instead is instrumented at the
single shared choke point per role service that every transmission passes through
(`TransmitAsync`'s one `KeyDownAsync` call), so it cannot be forgotten at a future call site
the way a state-broadcast bracket can.

It distinguishes "armed but idle" from "armed and actively transmitting", and reflects
Call-CQ engagement independent of which sub-state the Caller state machine currently
occupies.

## Requirements

---

### Requirement: TX-enable button distinguishes armed-idle from armed-keying

`#tx-enable-btn` SHALL render in one of three visually distinct states, derived from the
`txState` WebSocket payload's (and `GET /api/v1/tx/status`'s) `autoAnswerEnabled` and
`keying` fields:

- Not armed (`autoAnswerEnabled` is `false`): background/neutral colour, regardless of
  `keying`.
- Armed, not currently keying (`autoAnswerEnabled` is `true` and `keying` is `false`): dark
  red. This is also the default "armed but idle" state before the first ever transmission in
  a session — `keying` starts `false` and only becomes `true` once the controller actually
  enters `TransmitAsync`'s `KeyDownAsync` call.
- Armed and currently keying (`autoAnswerEnabled` is `true` and `keying` is `true`): bright
  red.

`keying` mirrors the daemon's `IQsoController.Keying` signal: `true` from the moment the
active QSO controller's `TransmitAsync` helper enters `IPttController.KeyDownAsync` until
that call returns (normally, via cancellation, or via a concurrent `KeyUpAsync`
interrupting it); `false` at all other times. It is independent of `state` — a controller may
retransmit (keying `true`) without a preceding `SetStateAndNotify` call, and the button
colour reflects that correctly.

#### Scenario: Not armed renders background colour

- **WHEN** `autoAnswerEnabled` is `false`
- **THEN** `#tx-enable-btn` SHALL show its neutral background colour, regardless of `keying`

#### Scenario: Armed and idle renders dark red

- **WHEN** `autoAnswerEnabled` is `true` and `keying` is `false`
- **THEN** `#tx-enable-btn` SHALL render dark red

#### Scenario: Armed before any transmission renders dark red

- **WHEN** `autoAnswerEnabled` is `true` and the QSO controller has not yet entered
  `KeyDownAsync` in the current session (`keying` is `false` by construction)
- **THEN** `#tx-enable-btn` SHALL render dark red, not an unstyled/unknown state

#### Scenario: Armed and keying renders bright red

- **WHEN** `autoAnswerEnabled` is `true` and `keying` is `true`
- **THEN** `#tx-enable-btn` SHALL render bright red, regardless of which `state` value
  accompanies the event (including during a retransmit that does not itself carry a new
  `Tx*` state broadcast)

---

### Requirement: Call-CQ button reflects engagement independent of transmit sub-state

`#tx-call-cq-btn` SHALL render bright green whenever Call-CQ mode is engaged (`role` is
`"caller"` and `autoAnswerEnabled` is `true`), regardless of which sub-state the Caller state
machine currently occupies, and SHALL render its neutral background colour otherwise. This colour
rule is independent of, and governed separately from, the button's `disabled` attribute and label,
which are specified by the `web-frontend` capability's "TX panel — Call CQ button" requirement —
under that requirement, an engaged button (`role === 'caller' && state !== 'Idle'`) is always
enabled (labelled "Stop CQ"), so a disabled button never coincides with the engaged/green state in
practice; this requirement's colour rule holds regardless.

#### Scenario: Call-CQ engaged renders bright green regardless of sub-state

- **WHEN** `role` is `"caller"`, `autoAnswerEnabled` is `true`, and `state` is any of `"Idle"`,
  `"TxCq"`, `"WaitAnswer"`, `"TxReport"`, `"WaitRr73"`, `"TxRr73"`, or `"QsoComplete"`
- **THEN** `#tx-call-cq-btn` SHALL render bright green in every case, and SHALL be enabled in every
  non-`"Idle"` case among them (see `web-frontend`)

#### Scenario: Call-CQ not engaged renders background colour

- **WHEN** `autoAnswerEnabled` is `false`, or `role` is not `"caller"`
- **THEN** `#tx-call-cq-btn` SHALL render its neutral background colour
