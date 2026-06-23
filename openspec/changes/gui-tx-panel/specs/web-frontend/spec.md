## ADDED Requirements

### Requirement: TX panel — layout alongside decoded-messages panel

The main page SHALL be restructured so that the area below the waterfall controls
contains a horizontal flex row with two panels:

- `#decodes-panel` — existing decoded-messages table; `flex: 1 1 0` (grows to fill)
- `#tx-panel` — new TX control panel; `flex: 0 0 320px` (fixed width, right-hand side)

Both panels SHALL fill the full height of the content area below the waterfall controls.
The `#tx-panel` SHALL be always rendered and visible regardless of TX configuration state.
A wrapper `<div id="content-row">` SHALL enclose both panels and be the flex-row container.

#### Scenario: TX panel is present on the main page at all times

- **WHEN** a browser loads `GET /`
- **THEN** the DOM SHALL contain `<div id="tx-panel">` as a sibling of `#decodes-panel`
  inside `#content-row`

#### Scenario: Panels are side-by-side

- **WHEN** a browser loads `GET /` on a desktop-width viewport
- **THEN** `#decodes-panel` and `#tx-panel` SHALL be rendered in the same horizontal row
  (computed `display` value is consistent with a flex-row container)

---

### Requirement: TX panel — Enable TX toggle button

The TX panel SHALL contain a single `<button id="tx-enable-btn">` that reflects and
controls the `tx.autoAnswer` state:

- **Disarmed** (`autoAnswer = false`): label reads **"Enable TX"**; standard neutral
  button styling.
- **Armed** (`autoAnswer = true`): label reads **"Enable TX"** (label does not change);
  the button SHALL have a visually alarming style (red/danger background, bold weight —
  CSS class `tx-btn-armed`) so the operator cannot overlook that autonomous transmission
  is active. The label is intentionally kept as "Enable TX" in both states; the red
  background alone signals the armed condition (D-TX-UI-002 — UAT decision 2026-06-22).

Clicking the button in the disarmed state SHALL call `POST /api/v1/tx/enable` and
apply the armed CSS class on HTTP 200. Clicking in the armed state SHALL call
`POST /api/v1/tx/disable` and remove the armed CSS class on HTTP 200. The button
SHALL be disabled for the duration of the pending request.

#### Scenario: Button shows Enable TX and is disarmed when autoAnswer is false

- **WHEN** the page loads and `GET /api/v1/tx/status` returns `autoAnswerEnabled: false`
- **THEN** `#tx-enable-btn` SHALL have text content "Enable TX"
- **AND** SHALL NOT have the `tx-btn-armed` CSS class

#### Scenario: Button shows Enable TX with armed style when autoAnswer is true

- **WHEN** the page loads and `GET /api/v1/tx/status` returns `autoAnswerEnabled: true`
- **THEN** `#tx-enable-btn` SHALL have text content "Enable TX"
- **AND** SHALL have the `tx-btn-armed` CSS class applied

#### Scenario: Clicking Enable TX (disarmed) calls /tx/enable and applies armed style

- **WHEN** `#tx-enable-btn` is clicked while in the disarmed state
- **THEN** `POST /api/v1/tx/enable` SHALL be called
- **AND** on HTTP 200, the `tx-btn-armed` CSS class SHALL be applied; label remains "Enable TX"

#### Scenario: Clicking Enable TX (armed) calls /tx/disable and removes armed style

- **WHEN** `#tx-enable-btn` is clicked while in the armed state
- **THEN** `POST /api/v1/tx/disable` SHALL be called
- **AND** on HTTP 200, the `tx-btn-armed` CSS class SHALL be removed; label remains "Enable TX"

#### Scenario: Button is disabled during pending request

- **WHEN** a click on `#tx-enable-btn` triggers a request that has not yet resolved
- **THEN** `#tx-enable-btn` SHALL be `disabled` until the response (success or error) is
  received

---

### Requirement: TX panel — Abort TX button

The TX panel SHALL contain a `<button id="tx-abort-btn">` labelled **"Abort TX"**.
Clicking it SHALL call `POST /api/v1/tx/abort`. The button SHALL always be present and
enabled regardless of TX state (it is a safety control; disabling it would defeat its
purpose). The button SHALL be disabled for the duration of the pending request.

`POST /api/v1/tx/abort` returns a `TxStatusResponse` JSON body (HTTP 200). On receipt,
the frontend SHALL call `renderTxPanel` immediately with `autoAnswerEnabled: false` to
disarm the button without waiting for a subsequent `txState` WebSocket event
(D-TX-UI-001 — supervised single-QSO model, UAT decision 2026-06-22).

#### Scenario: Abort TX button is always present and enabled

- **WHEN** a browser loads `GET /` and the TX state is `Idle`
- **THEN** `#tx-abort-btn` SHALL be present in the DOM and SHALL NOT be `disabled`

#### Scenario: Clicking Abort TX calls the abort endpoint and disarms the panel

- **WHEN** `#tx-abort-btn` is clicked
- **THEN** `POST /api/v1/tx/abort` SHALL be called
- **AND** on HTTP 200 the TX panel SHALL update to the disarmed / Idle appearance
  immediately (the `tx-btn-armed` class SHALL be removed from `#tx-enable-btn`)
- **AND** `#tx-abort-btn` SHALL be re-enabled

---

### Requirement: TX panel — state and partner status display

The TX panel SHALL contain a `<span id="tx-state-display">` that shows the current QSO
controller state in a human-readable form:

- `Idle` state: shows **"Idle"** with muted styling
- Any non-Idle state: shows **"Working \<callsign\>"** (e.g. `Working Q2XYZ`) with
  prominent/accent styling

The display SHALL update on every `txState` WebSocket event.

#### Scenario: Display shows Idle at startup

- **WHEN** the page loads and the initial TX status is `Idle`
- **THEN** `#tx-state-display` SHALL contain the text "Idle"

#### Scenario: Display updates to Working on txState event

- **WHEN** a `txState` event is received with `{ "state": "TxAnswer", "partner": "Q2XYZ" }`
- **THEN** `#tx-state-display` SHALL contain the text "Working Q2XYZ"

#### Scenario: Display reverts to Idle on txState Idle event

- **WHEN** a `txState` event is received with `{ "state": "Idle", "partner": null }`
- **THEN** `#tx-state-display` SHALL contain the text "Idle"

---

### Requirement: TX panel — standard message rows

The TX panel SHALL display three message rows, identified by `id` attributes
`tx-msg-1`, `tx-msg-2`, and `tx-msg-3`, each containing a read-only text representation
of the standard FT8 message for that slot:

| Row  | Message template                         | Active QSO state(s)         |
|------|------------------------------------------|-----------------------------|
| Tx 1 | `{partner} {callsign} {grid}`            | `TxAnswer`                  |
| Tx 2 | `{partner} {callsign} R+00`              | `TxReport`                  |
| Tx 3 | `{partner} {callsign} 73`                | `Tx73`                      |

Values for `{callsign}` and `{grid}` SHALL be read from `config.tx.callsign` and
`config.tx.grid` obtained via `GET /api/v1/config` on page load. The `{partner}` token
SHALL be populated from the `partner` field of the most recent `txState` WebSocket event.

When `State == Idle` (partner is `null`), the partner slot SHALL be rendered as `———`
(three em-dashes) so the row still previews the operator's own callsign and grid.

**Active row highlighting:** When the current `txState.state` matches a row's active
states, that row SHALL receive the CSS class `tx-msg-active` and be rendered with an
accent colour. All other rows SHALL have muted styling.

**Greyed-out when disarmed:** When `autoAnswer` is `false`, all three rows SHALL receive
the CSS class `tx-msg-muted` (greyed/dimmed). When `autoAnswer` becomes `true`, the
`tx-msg-muted` class SHALL be removed.

#### Scenario: Message rows show operator callsign and grid in Idle state

- **WHEN** the page loads with `config.tx.callsign = "Q1OFZ"`, `config.tx.grid = "JO33"`,
  and the TX state is `Idle`
- **THEN** `#tx-msg-1` SHALL display text matching `——— Q1OFZ JO33`
- **AND** `#tx-msg-2` SHALL display text matching `——— Q1OFZ R+00`
- **AND** `#tx-msg-3` SHALL display text matching `——— Q1OFZ 73`

#### Scenario: Message rows populate partner on active QSO

- **WHEN** a `txState` event is received with `partner: "Q2XYZ"`
- **THEN** `#tx-msg-1` SHALL display `Q2XYZ Q1OFZ JO33`
- **AND** `#tx-msg-2` SHALL display `Q2XYZ Q1OFZ R+00`
- **AND** `#tx-msg-3` SHALL display `Q2XYZ Q1OFZ 73`

#### Scenario: Active row is highlighted during TxAnswer

- **WHEN** a `txState` event is received with `state: "TxAnswer"`
- **THEN** `#tx-msg-1` SHALL have CSS class `tx-msg-active`
- **AND** `#tx-msg-2` and `#tx-msg-3` SHALL NOT have `tx-msg-active`

#### Scenario: Active row is highlighted during TxReport

- **WHEN** a `txState` event is received with `state: "TxReport"`
- **THEN** `#tx-msg-2` SHALL have CSS class `tx-msg-active`

#### Scenario: Active row is highlighted during Tx73

- **WHEN** a `txState` event is received with `state: "Tx73"`
- **THEN** `#tx-msg-3` SHALL have CSS class `tx-msg-active`

#### Scenario: No row highlighted in wait states

- **WHEN** a `txState` event is received with `state: "WaitReport"` or `"WaitRr73"`
- **THEN** no row SHALL have CSS class `tx-msg-active`

#### Scenario: Message rows greyed out when TX is disarmed

- **WHEN** `autoAnswerEnabled` is `false`
- **THEN** `#tx-msg-1`, `#tx-msg-2`, and `#tx-msg-3` SHALL each have CSS class
  `tx-msg-muted`

#### Scenario: Message rows normal when TX is armed

- **WHEN** `autoAnswerEnabled` is `true`
- **THEN** none of `#tx-msg-1`, `#tx-msg-2`, `#tx-msg-3` SHALL have CSS class
  `tx-msg-muted`

---

### Requirement: Main page handles txState WebSocket event

The main page WebSocket handler SHALL process `txState` events (previously unhandled)
and update the TX panel accordingly. A `txState` event carries:
- `state` — the new `QsoState` as a string
- `partner` — the active partner callsign, or `null`
- `autoAnswerEnabled` — the current armed/disarmed state (added for D-TX-UI-003,
  2026-06-22; allows QSO completion and abort to disarm the panel without a separate
  HTTP call)

Wire format example (active state):
`{"type":"txState","state":"TxAnswer","partner":"Q2XYZ","autoAnswerEnabled":true}`

Wire format example (idle / disarmed):
`{"type":"txState","state":"Idle","partner":null,"autoAnswerEnabled":false}`

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

---

### Requirement: Main page fetches initial TX status on load

On page load (inside `DOMContentLoaded`), the main page JavaScript SHALL call
`GET /api/v1/tx/status` to seed the TX panel with the current `state`, `partner`, and
`autoAnswerEnabled` before the first `txState` WebSocket event arrives.

#### Scenario: Panel is seeded from GET /api/v1/tx/status on load

- **WHEN** the main page is loaded and `GET /api/v1/tx/status` returns
  `{ "state": "Idle", "partner": null, "autoAnswerEnabled": false }`
- **THEN** `#tx-enable-btn` SHALL show "Enable TX" without the `tx-btn-armed` class (disarmed style)
- **AND** `#tx-state-display` SHALL show "Idle"
- **AND** message rows SHALL be greyed out (`tx-msg-muted`)

#### Scenario: TX status fetch failure is non-fatal

- **WHEN** `GET /api/v1/tx/status` fails (network error or non-200 response) on page load
- **THEN** the TX panel SHALL remain visible with default disarmed / Idle appearance
- **AND** no unhandled exception or console error stack SHALL prevent subsequent
  WebSocket operation

---

### Requirement: Decode table — CQ row highlighting

Decode table rows whose message text begins with `"CQ "` SHALL receive the CSS class
`decode-cq`. The styling SHALL use a visually distinct warm accent colour that draws the
operator's attention to stations calling CQ without overwhelming the table. The class
SHALL be applied at row-creation time when the decode row is rendered.

#### Scenario: CQ message row receives decode-cq class

- **WHEN** a decode with message `"CQ Q1ABC JO33"` is rendered in the decode table
- **THEN** the corresponding table row SHALL have CSS class `decode-cq`

#### Scenario: Non-CQ message row does not receive decode-cq class

- **WHEN** a decode with message `"Q1ABC Q2XYZ +05"` is rendered in the decode table
- **THEN** the corresponding table row SHALL NOT have CSS class `decode-cq`

---

### Requirement: Decode table — clickable CQ rows (TX-D01)

CQ decode table rows SHALL be clickable. Clicking a CQ row while the TX controller is
`Idle` SHALL:

1. Extract the partner callsign, audio frequency offset, and CQ cycle start time from
   the decode row.
2. Call `POST /api/v1/tx/answer-cq` with `{ callsign, frequencyHz, cqCycleStartUtc }`.
3. On HTTP 200: call `renderTxPanel` with the returned status (system is now armed and
   waiting for the correct FT8 answer phase; TX fires within 0–30 s at most).
4. On HTTP 409 (controller not Idle): log a console warning; no UI change.
5. On other error: log to console; no UI change.

**Callsign extraction** from the CQ message:
- 3-token CQ (`CQ callsign grid`): token at index 1
- 4-token CQ (`CQ modifier callsign grid`): token at index 2

**Frequency:** the `offsetHz` value of the decode row (the audio frequency in Hz at
which the signal was detected).

**`cqCycleStartUtc`:** the UTC cycle-start timestamp of the decode row, formatted as an
ISO 8601 string (e.g. `"2026-06-22T17:29:15Z"`). The decode row's timestamp column
contains this value; the frontend SHALL parse it from the row data at render time and
store it as a data attribute or in a closure for retrieval when the row is clicked.

Decode row timestamp format: `YYMMDD_HHMMSS` (UTC). Parsing:
```javascript
function parseFt8CycleStartUtc(ft8Ts) {
  // ft8Ts example: "260622_172915"
  const [date, time] = ft8Ts.split('_');
  return `20${date.slice(0,2)}-${date.slice(2,4)}-${date.slice(4,6)}` +
         `T${time.slice(0,2)}:${time.slice(2,4)}:${time.slice(4,6)}Z`;
}
```

Clicking a CQ row while the controller is NOT Idle SHALL have no effect (the click is
silently ignored; a 409 response is swallowed with a console warning).

#### Scenario: Clicking a CQ row calls answer-cq with phase info and arms the TX panel

- **WHEN** the controller is `Idle` and the operator clicks a CQ row with
  message `"CQ Q1ABC JO33"`, `offsetHz = 1500`, and row timestamp `"260622_172915"`
- **THEN** `POST /api/v1/tx/answer-cq` SHALL be called with
  `{ "callsign": "Q1ABC", "frequencyHz": 1500, "cqCycleStartUtc": "2026-06-22T17:29:15Z" }`
- **AND** on HTTP 200 the TX panel SHALL update to the armed appearance

#### Scenario: Clicking a 4-token CQ row extracts the callsign correctly

- **WHEN** the operator clicks a CQ row with message `"CQ DX Q9XYZ FN42"`
- **THEN** `POST /api/v1/tx/answer-cq` SHALL be called with `callsign = "Q9XYZ"`

#### Scenario: Clicking a CQ row when not Idle has no effect

- **WHEN** the controller state is `TxAnswer` (active QSO) and the operator clicks
  a CQ row
- **THEN** no `POST /api/v1/tx/answer-cq` request SHALL be sent
  (or the resulting 409 SHALL be silently swallowed)

---

### Requirement: Decode table — partner interaction highlighting

Decode table rows that are part of the active QSO exchange SHALL receive the CSS class
`decode-partner`. The styling SHALL use a subdued red colour that is clearly readable
but not harsh (e.g. a muted rose or dark salmon; specific shade is a developer
decision within the constraint of legibility).

A row is "part of the active QSO exchange" if and only if:
- `currentTxPartner` is not `null`, **AND**
- The message contains the operator's callsign (from `config.tx.callsign`) as a
  space-delimited token, **AND**
- The message contains the partner's callsign (from `currentTxPartner`) as a
  space-delimited token.

A token matches a callsign if the token equals the callsign exactly, **OR** the token
equals the callsign followed by `/` and one or more suffix characters (e.g. token
`PD2FZ/P` matches callsign `PD2FZ`).

The class SHALL be applied or removed when each decode row is created. Rows rendered
while no QSO is active (partner is null) SHALL NOT have `decode-partner`.

Note: rows from a previous QSO that are already in the table are not retroactively
reclassified when the partner changes. Only newly rendered rows are evaluated.

#### Scenario: QSO exchange row receives decode-partner class

- **WHEN** `currentTxPartner = "Q1ABC"`, `txCallsign = "Q9XYZ"`, and a decode with
  message `"Q1ABC Q9XYZ +05"` is rendered
- **THEN** the row SHALL have CSS class `decode-partner`

#### Scenario: Third-party message does not receive decode-partner class

- **WHEN** `currentTxPartner = "Q1ABC"`, `txCallsign = "Q9XYZ"`, and a decode with
  message `"Q2OTHER Q1ABC +12"` is rendered (partner present, operator's callsign absent)
- **THEN** the row SHALL NOT have CSS class `decode-partner`

#### Scenario: CQ row does not receive decode-partner class

- **WHEN** `currentTxPartner = "Q1ABC"` and a decode with message `"CQ Q1ABC JO33"`
  is rendered
- **THEN** the row SHALL NOT have CSS class `decode-partner`
  (operator's callsign is not present in the message)

#### Scenario: Partner suffix variant is matched

- **WHEN** `currentTxPartner = "Q1ABC"`, `txCallsign = "Q9XYZ/P"`, and a decode with
  message `"Q1ABC Q9XYZ/P RR73"` is rendered
- **THEN** the row SHALL have CSS class `decode-partner`
  (token `Q9XYZ/P` matches callsign `Q9XYZ/P` exactly)
