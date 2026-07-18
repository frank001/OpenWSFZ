## MODIFIED Requirements

### Requirement: TX panel — QSO Transcript section

The TX panel SHALL contain a **QSO Transcript** section, occupying the same DOM location
previously used by the "TX History" abort-reason list (`FR-062`, superseding the unspecified
`FR-UX-002` abort-only behaviour), rendered as `<ol id="tx-transcript-log">` inside
`<div id="tx-transcript-section">`. The section SHALL remain hidden until its first entry is
appended, exactly as the prior TX History section did.

The section SHALL record, as a single unified, newest-on-top, chronological list:

1. **Sent** entries — every standard FT8 message the operator's own station actually transmits.
2. **Received** entries — every decoded message belonging to the operator's own tracked
   conversation (matched by callsign token against the operator's own callsign or the active
   partner), sourced from the raw `decode` WebSocket feed **before** any `decode-panel-filtering`
   column-filter or `decode-noise-suppression` gating is applied to it.
3. **Abort** entries — an abort reason string, exactly as previously produced by `FR-UX-002`,
   now folded inline into this same list instead of a separate one.
4. **Partner-change** entries — a separator noting the tracked partner has changed, whenever
   `currentTxPartner` transitions to a new non-null value from a different previous value.

The list SHALL be capped at 100 entries; when a new entry would exceed the cap, the oldest
entry SHALL be dropped.

Sent and received entries SHALL be visually distinguished by direction: sent entries SHALL carry
CSS class `transcript-sent`; received entries SHALL carry CSS class `transcript-received`. Abort
and partner-change entries SHALL carry CSS class `transcript-event` and SHALL NOT be colorized
by direction.

#### Scenario: Section is hidden until first entry

- **WHEN** the page loads and no transcript entry has yet been recorded
- **THEN** `#tx-transcript-section` SHALL be `hidden`

#### Scenario: Sent message is recorded once per transmission step, using the real transmitted text when available

- **WHEN** a `txState` event is received with `state: "TxAnswer"`, the previous state was
  `"Idle"` (answerer role), and the event's `lastTxMessage` field is `"Q2XYZ Q1OFZ JO33"`
- **THEN** exactly one new entry with CSS class `transcript-sent` SHALL be appended to
  `#tx-transcript-log`, containing that real `lastTxMessage` text (`fix-tx-transcript-real-message`
  — previously this entry always contained the per-state template text regardless of what was
  actually transmitted; see the new "TX panel message rows prefer the real transmitted message
  over the template" requirement for the fallback behaviour when `lastTxMessage` is absent)

#### Scenario: Repeated push of the same state does not duplicate the entry

- **WHEN** two consecutive `txState` events are received both carrying `state: "TxAnswer"` with
  no state change in between
- **THEN** only one `transcript-sent` entry for that transmission step SHALL exist in
  `#tx-transcript-log`

#### Scenario: A retried transmission is logged again

- **WHEN** the state machine re-enters `"TxReport"` after having left it for `"WaitRr73"` and
  timing out back to `"TxReport"` (a retry)
- **THEN** a second `transcript-sent` entry for the report message SHALL be appended, distinct
  from the first

#### Scenario: Received message from the tracked partner is recorded even when column-filtered

- **WHEN** a `decode` WebSocket event arrives whose message tokens include the active partner's
  callsign, and the current `decode-panel-filtering` column filter would hide that decode's row
  in `#decodes-table` (`tr.hidden === true`)
- **THEN** a `transcript-received` entry for that message SHALL still be appended to
  `#tx-transcript-log`

#### Scenario: Unrelated traffic is not recorded

- **WHEN** a `decode` WebSocket event arrives whose message tokens include neither the operator's
  own callsign nor the active partner's callsign
- **THEN** no entry SHALL be appended to `#tx-transcript-log` for that decode

#### Scenario: Partner change appends a separator entry

- **WHEN** `currentTxPartner` changes from `"Q2XYZ"` to `"Q3ABC"`
- **THEN** a `transcript-event` separator entry noting the new partner SHALL be appended before
  any further `transcript-sent`/`transcript-received` entries for `"Q3ABC"`

#### Scenario: Abort reason appears inline in the transcript

- **WHEN** the daemon reports a `txState` event transitioning to `"Idle"` with a non-null
  `abortReason`
- **THEN** a `transcript-event` entry containing that reason SHALL be appended to
  `#tx-transcript-log`, in chronological order alongside any sent/received entries for that QSO

#### Scenario: List is capped at 100 entries

- **WHEN** a 101st transcript entry (of any kind) is appended
- **THEN** the oldest entry SHALL be removed from `#tx-transcript-log`, leaving exactly 100

---

### Requirement: Main page handles txState WebSocket event

The main page WebSocket handler SHALL process `txState` events (previously unhandled)
and update the TX panel accordingly. A `txState` event carries:
- `state` — the new `QsoState` as a string
- `partner` — the active partner callsign, or `null`
- `autoAnswerEnabled` — the current armed/disarmed state (added for D-TX-UI-003,
  2026-06-22; allows QSO completion and abort to disarm the panel without a separate
  HTTP call)
- `lastTxMessage` — the real text of the most recently transmitted message, or `null` if
  nothing has been transmitted yet this process lifetime (`fix-tx-transcript-real-message`)

Wire format example (active state):
`{"type":"txState","state":"TxAnswer","partner":"Q2XYZ","autoAnswerEnabled":true,"lastTxMessage":"Q2XYZ Q1OFZ JO33"}`

Wire format example (idle / disarmed):
`{"type":"txState","state":"Idle","partner":null,"autoAnswerEnabled":false,"lastTxMessage":null}`

The frontend SHALL read `autoAnswerEnabled` from the event and pass it to `renderTxPanel`.
If the field is absent (forward-compatibility), the frontend SHALL fall back to the last
known local `currentAutoAnswerEnabled` value.

#### Scenario: txState event updates state display and message rows

- **WHEN** the WebSocket receives `{ "type": "txState", "state": "WaitReport", "partner": "Q2XYZ", "autoAnswerEnabled": true }`
- **THEN** `#tx-state-display` SHALL update to "Working Q2XYZ"
- **AND** no message row SHALL have the `tx-msg-active` class (wait state — no row active)
- **AND** all message rows SHALL show `Q2XYZ` as the partner token

#### Scenario: Idle txState event disarms the panel (D-TX-UI-003)

- **WHEN** the WebSocket receives `{ "type": "txState", "state": "Idle", "partner": null, "autoAnswerEnabled": false }`
- **THEN** `#tx-enable-btn` SHALL NOT have the `tx-btn-armed` class
- **AND** `#tx-state-display` SHALL show "Idle"
- **AND** all message rows SHALL have the `tx-msg-muted` class

#### Scenario: Missing lastTxMessage field is forward-compatible

- **WHEN** a `txState` event has no `lastTxMessage` field (older cached backend, or a state prior
  to this change)
- **THEN** the frontend SHALL treat this identically to `lastTxMessage: null` — message rows fall
  back to the per-state template exactly as they did before this change

## ADDED Requirements

### Requirement: TX panel message rows prefer the real transmitted message over the template

Once a `txState` event's `lastTxMessage` field is non-null, the frontend SHALL remember it against
the row corresponding to the state that was active at the moment it arrived (the same
transition-into-active-state moment `hasEnteredNewActiveTxState` already detects). For each of
`#tx-msg-1`/`#tx-msg-2`/`#tx-msg-3`, rendering SHALL use that remembered real text if one has been
recorded for that row this tracked QSO, and SHALL fall back to the existing per-state/per-role
template (`TX panel — standard message rows`, `TX panel message rows are role-aware`) only for a
row that has not yet had a real message recorded.

The remembered real text for all three rows SHALL be cleared whenever `currentTxPartner` changes to
a different non-null value, or the state returns to `Idle` — consistent with how `currentTxPartner`
itself is already reset at those points — so a previous QSO's real text SHALL NOT leak into a new
QSO's row display before that new QSO has transmitted anything of its own.

#### Scenario: A row shows its real transmitted text once available

- **WHEN** a `txState` event transitions into `"TxReport"` with `lastTxMessage: "Q2XYZ Q1OFZ -07"`
- **THEN** `#tx-msg-2` SHALL display `"Q2XYZ Q1OFZ -07"`, not the template `"Q2XYZ Q1OFZ R+00"`

#### Scenario: A row not yet transmitted still shows the template

- **WHEN** the current QSO has transmitted `#tx-msg-1` (with a real recorded message) but has not
  yet reached `TxReport`
- **THEN** `#tx-msg-2` SHALL still display its per-state/per-role template text, since no real
  message has been recorded for that row yet

#### Scenario: A row keeps showing its real text after the QSO advances past it

- **WHEN** `#tx-msg-2` has recorded real text `"Q2XYZ Q1OFZ -07"` and the state subsequently
  advances to `"WaitRr73"` and then `"TxRr73"`
- **THEN** `#tx-msg-2` SHALL continue to display `"Q2XYZ Q1OFZ -07"` (not revert to the template),
  even though the backend's `LastTxMessage` field itself has since moved on to the row 3 text

#### Scenario: Real text is cleared when the tracked partner changes

- **WHEN** `#tx-msg-2` has recorded real text from a QSO with `"Q2XYZ"`, and `currentTxPartner`
  then changes to `"Q3ABC"`
- **THEN** `#tx-msg-2` SHALL revert to showing its template text (with the new partner token) until
  a real message is recorded for that row in the new QSO

#### Scenario: Real text is cleared on return to Idle

- **WHEN** the state returns to `"Idle"` after a completed or aborted QSO
- **THEN** all three rows' remembered real text SHALL be cleared
