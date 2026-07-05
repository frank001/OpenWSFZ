# tx-state-indicators Specification

## Purpose

This capability defines the visual (colour) states of the TX control buttons —
`#tx-enable-btn` and `#tx-call-cq-btn` — derived entirely from existing `txState` WebSocket
payload fields (`state`, `autoAnswerEnabled`, `role`), with no additional server-side signal.
It distinguishes "armed but idle" from "armed and actively transmitting", and reflects
Call-CQ engagement independent of which sub-state the Caller state machine currently
occupies.

## Requirements

---

### Requirement: TX-enable button distinguishes armed-idle from armed-transmitting

`#tx-enable-btn` SHALL render in one of three visually distinct states, derived from the existing
`txState` WebSocket payload's `state` and `autoAnswerEnabled` fields, with no additional
server-side signal:

- Not armed (`autoAnswerEnabled` is `false`): background/neutral colour.
- Armed, not currently transmitting (`autoAnswerEnabled` is `true` and `state` is one of the
  non-transmitting sub-states — `Idle`, any `Wait*` state, or `QsoComplete`, for either the
  Answerer's `QsoState` or the Caller's `CallerState`): dark red.
- Armed and currently transmitting (`autoAnswerEnabled` is `true` and `state` is one of the
  transmitting sub-states — any state whose name begins with `Tx`): bright red.

#### Scenario: Not armed renders background colour

- **WHEN** `autoAnswerEnabled` is `false`
- **THEN** `#tx-enable-btn` SHALL show its neutral background colour, regardless of `state`

#### Scenario: Armed and idle renders dark red

- **WHEN** `autoAnswerEnabled` is `true` and `state` is `"Idle"`
- **THEN** `#tx-enable-btn` SHALL render dark red

#### Scenario: Armed and waiting renders dark red

- **WHEN** `autoAnswerEnabled` is `true` and `state` is `"WaitReport"`, `"WaitRr73"`, or
  `"WaitAnswer"`
- **THEN** `#tx-enable-btn` SHALL render dark red (not bright red — no audio is being transmitted
  in a waiting state)

#### Scenario: Armed and transmitting renders bright red

- **WHEN** `autoAnswerEnabled` is `true` and `state` is one of `"TxAnswer"`, `"TxReport"`,
  `"Tx73"`, `"TxCq"`, or `"TxRr73"`
- **THEN** `#tx-enable-btn` SHALL render bright red

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
