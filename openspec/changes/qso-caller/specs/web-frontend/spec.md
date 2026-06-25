## ADDED Requirements

### Requirement: TX panel message rows are role-aware

The TX panel message rows (`#tx-msg-1`, `#tx-msg-2`, `#tx-msg-3`) SHALL render
different content templates depending on the `role` field of the most recent `txState`
WebSocket event (or the `role` field from the initial `GET /api/v1/tx/status` response).

| Row  | Answerer template               | Caller template                |
|------|---------------------------------|--------------------------------|
| Tx 1 | `{partner} {callsign} {grid}`   | `CQ {callsign} {grid}`         |
| Tx 2 | `{partner} {callsign} R+00`     | `{partner} {callsign} +00`     |
| Tx 3 | `{partner} {callsign} 73`       | `{partner} {callsign} RR73`    |

The `{partner}` placeholder uses three em-dashes (`———`) when `partner` is `null`
(Idle state), consistent with the existing answerer behaviour.

Active-row state mapping SHALL be role-specific:

| State (Answerer) | Active row | State (Caller) | Active row |
|------------------|-----------|----------------|-----------|
| `TxAnswer`       | Tx 1      | `TxCq`         | Tx 1      |
| `TxReport`       | Tx 2      | `TxReport`     | Tx 2      |
| `Tx73`           | Tx 3      | `TxRr73`       | Tx 3      |

All other states (wait states, `Idle`) → no row highlighted.

The frontend SHALL default to `"answerer"` role rendering when the `role` field is
absent from a `txState` event (forward-compatibility).

#### Scenario: Caller role — Tx 1 shows CQ template in Idle state

- **WHEN** the active role is `Caller`, `callsign = "PD2FZ"`, `grid = "JO33"`, and
  the state is `Idle`
- **THEN** `#tx-msg-1` SHALL display `"CQ PD2FZ JO33"`
- **AND** `#tx-msg-2` SHALL display `"——— PD2FZ +00"`
- **AND** `#tx-msg-3` SHALL display `"——— PD2FZ RR73"`

#### Scenario: Caller role — Tx 1 highlighted during TxCq

- **WHEN** the `txState` event contains `role: "caller"` and `state: "TxCq"`
- **THEN** `#tx-msg-1` SHALL have CSS class `tx-msg-active`
- **AND** `#tx-msg-2` and `#tx-msg-3` SHALL NOT have `tx-msg-active`

#### Scenario: Caller role — Tx 3 shows partner and RR73 during WaitRr73

- **WHEN** the `txState` event contains `role: "caller"`, `state: "WaitRr73"`,
  and `partner: "Q1ABC"`
- **THEN** `#tx-msg-3` SHALL display `"Q1ABC PD2FZ RR73"`
- **AND** no row SHALL have `tx-msg-active` (wait state)

#### Scenario: Missing role field defaults to answerer rendering

- **WHEN** a `txState` event has no `role` field
- **THEN** the frontend SHALL render message rows using the answerer templates

---

### Requirement: Settings page — TX Mode selector

The Settings page General tab SHALL include a **TX Mode** control allowing the
operator to select between `Answerer` and `Caller` roles. The control SHALL be a
`<select id="general-tx-role">` element with two `<option>` elements:
- `value="Answerer"`: "Answerer (respond to CQ)"
- `value="Caller"`: "Caller (call CQ)"

The control SHALL be pre-populated from `config.tx.role` on page load. Changing the
value SHALL mark the form dirty (unsaved-changes indicator). Saving SHALL include
`tx.role` in the `POST /api/v1/config` payload.

#### Scenario: TX Mode selector pre-fills from config

- **WHEN** `GET /api/v1/config` returns `{ "tx": { "role": "Answerer" } }`
- **THEN** `#general-tx-role` SHALL have `"Answerer"` selected

#### Scenario: TX Mode selector change marks form dirty

- **WHEN** the operator changes `#general-tx-role`
- **THEN** the unsaved-changes indicator SHALL become visible

#### Scenario: Save includes tx.role

- **WHEN** the operator selects `"Caller"` and clicks Save
- **THEN** `POST /api/v1/config` SHALL include `"tx": { "role": "Caller", ... }`

---

### Requirement: Settings page — CallerPartnerSelect control

The Settings page General tab SHALL include a **Partner selection** control
(`<select id="general-caller-partner-select">`) with two options:
- `value="First"`: "First responder (automatic)"
- `value="None"`: "None (operator selects)"

This control SHALL be visible only when `#general-tx-role` is set to `"Caller"`, and
SHALL be hidden (or `display: none`) when `"Answerer"` is selected. The control SHALL
be pre-populated from `config.tx.callerPartnerSelect` on page load.

#### Scenario: CallerPartnerSelect hidden when role is Answerer

- **WHEN** `#general-tx-role` is set to `"Answerer"`
- **THEN** `#general-caller-partner-select` (and its label) SHALL NOT be visible

#### Scenario: CallerPartnerSelect visible when role is Caller

- **WHEN** `#general-tx-role` is changed to `"Caller"`
- **THEN** `#general-caller-partner-select` SHALL become visible without a page reload

#### Scenario: Save includes tx.callerPartnerSelect

- **WHEN** the operator selects `"Caller"` + `"None"` and clicks Save
- **THEN** `POST /api/v1/config` SHALL include `"tx": { "callerPartnerSelect": "None", ... }`

---

### Requirement: Settings page — restart notice after role change

If the operator changes `#general-tx-role` (to a value different from the currently
saved `config.tx.role`) and clicks Save, the page SHALL display a visible notice:
**"TX mode change saved. Restart the application for the change to take effect."**

The notice SHALL appear after the save succeeds (HTTP 200) and SHALL persist until
the page is navigated away from or reloaded.

#### Scenario: Restart notice appears after role change is saved

- **WHEN** the operator changes `#general-tx-role` from its current saved value and
  clicks Save and the response is HTTP 200
- **THEN** a visible restart notice SHALL appear on the Settings page

#### Scenario: Restart notice does not appear when role is unchanged

- **WHEN** the operator saves without changing `#general-tx-role`
- **THEN** no restart notice SHALL appear

---

### Requirement: Decode table — responder row highlighting (None mode)

When the active role is `Caller`, `CallerPartnerSelect = None`, and the controller is
in `WaitAnswer`, decode table rows that appear to be responses to our CQ SHALL receive
the CSS class `decode-responder`.

A row is a candidate response if its message contains `{our_callsign}` as the first
token AND a second token that is a valid callsign AND a third token that looks like a
Maidenhead grid (4-character alphanumeric starting with two letters). This matches
the FT8 format `{our_callsign} {their_callsign} {their_grid}`.

The `decode-responder` class SHALL use a visually distinct style (e.g. a warm green
or teal accent) that differentiates responders from `decode-cq` (warm amber) and
`decode-partner` (subdued red).

#### Scenario: Responder row highlighted during WaitAnswer (None mode)

- **WHEN** `role = "caller"`, `callerPartnerSelect = "None"`, the state is
  `"WaitAnswer"`, and a decode with message `"PD2FZ Q1ABC JO22"` is rendered
  (where `PD2FZ` is our callsign)
- **THEN** the row SHALL have CSS class `decode-responder`

#### Scenario: Non-response row not highlighted

- **WHEN** the state is `"WaitAnswer"` and a decode with message `"CQ Q1ABC JO22"`
  is rendered
- **THEN** the row SHALL NOT have CSS class `decode-responder`

#### Scenario: Responder rows not highlighted in Answerer role

- **WHEN** `role = "answerer"` and a decode with message `"PD2FZ Q1ABC JO22"` is
  rendered
- **THEN** the row SHALL NOT have CSS class `decode-responder`

---

### Requirement: Decode table — clickable responder rows (None mode)

When `role = "caller"` and `CallerPartnerSelect = None`, rows bearing the
`decode-responder` class SHALL be clickable. A click SHALL:

1. Extract the responding callsign (second token), audio frequency offset, and
   response cycle start time from the row.
2. Call `POST /api/v1/tx/select-responder` with
   `{ callsign, frequencyHz, responseCycleStartUtc }`.
3. On HTTP 200: call `renderTxPanel` with the returned status.
4. On HTTP 409 (controller not in `WaitAnswer`): log a console warning; no UI change.
5. On HTTP 405 (role is Answerer): log a console warning; no UI change.

The `responseCycleStartUtc` is derived from the row's decode timestamp using the
existing `parseFt8CycleStartUtc` function.

Double-click guard: the same 400 ms `inFlight` guard used for CQ rows SHALL apply to
responder rows to prevent accidental double-clicks.

#### Scenario: Clicking a responder row calls select-responder

- **WHEN** `role = "caller"`, `CallerPartnerSelect = None`, the state is
  `"WaitAnswer"`, and the operator clicks a row with message `"PD2FZ Q1ABC JO22"`,
  `offsetHz = 1500`, timestamp `"260625_142915"`
- **THEN** `POST /api/v1/tx/select-responder` SHALL be called with
  `{ "callsign": "Q1ABC", "frequencyHz": 1500, "responseCycleStartUtc": "2026-06-25T14:29:15Z" }`

#### Scenario: Non-responder row click has no effect

- **WHEN** the operator clicks a row that does not have `decode-responder` class
- **THEN** no `POST /api/v1/tx/select-responder` request SHALL be sent
